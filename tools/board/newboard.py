# A new ESP32-S3 board on the bench (PicoquorumKey, console-s3), checked from the Mac in four steps:
#   1. USB: does it stay on, or leave and come back (an empty flash does that every few seconds)
#   2. what it prints: the ROM's boot lines, MicroPython's prompt, or the console's USB link
#   3. the module, read by esptool: chip, flash size, PSRAM, MAC (only with no MicroPython yet)
#   4. under bare MicroPython, from RAM: buttons at rest and pressed, the key chip's bus and serial,
#      the screen, and a watch for restarts (tools/board/newboard_check.py)
#
#   uv run --no-project --with pyserial==3.5 python tools/board/newboard.py [--port P]
#       [--board picoquorum-key|console-s3] [--watch S] [--buttons S] [--soak S] [--flash BIN]
#
# Nothing is written to the board unless --flash BIN is given: then, if BIN's SHA-256 is MicroPython
# 1.26.1's below, the flash is erased and BIN written. The check runs from RAM (raw-paste, as
# mpremote run does) and saves no file; the ATECC608 is asked only for its public serial and lock
# bytes. A board already on the console image is only identified, never interrupted.
# DTR and RTS stay low (link.py): on the S3's own USB their edges reset the chip or start its loader.
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time

import serial
from serial.tools import list_ports

MICROPYTHON = "d6c48687f684cc7c002a0a4acd258f881c4b391f3ef121726a3b7cd285dcdbbc"  # ESP32_GENERIC_S3 1.26.1
ESPRESSIF = 0x303A
HERE = os.path.dirname(os.path.abspath(__file__))
results = []     # (step, status, detail)


def note(step, status, detail=""):
    results.append((step, status, detail))
    print("  %-16s %-5s %s" % (step, status, detail))
    sys.stdout.flush()


def say(*a):
    print(*a)
    sys.stdout.flush()


def s3_ports():
    return [(p.device, p.serial_number or "") for p in list_ports.comports() if p.vid == ESPRESSIF]


def find(port, wait):
    end = time.time() + wait
    while True:
        for dev, sn in s3_ports():
            if port in (None, dev):
                return dev, sn
        if time.time() > end:
            return None, None
        time.sleep(0.1)


# --- 1. USB, without opening the port --------------------------------------------------------
def watch(port, secs):
    say("\n1. USB, %d s, port not opened" % secs)
    t0, on, events, first = time.time(), None, [], None
    while time.time() - t0 < secs:
        now = [(d, s) for d, s in s3_ports() if port in (None, d)]
        if bool(now) != on:
            on = bool(now)
            events.append((time.time() - t0, on))
            say("  %5.1f s  %s" % (time.time() - t0, ("on USB  %s  %s" % now[0]) if on else "off USB"))
            if on and not first:
                first = now[0]
        time.sleep(0.1)
    offs = [t for t, o in events if not o]
    if not first:
        note("usb", "FAIL", "nothing from Espressif on USB in %d s: J1 and its joints, 3V3 (U3), the "
             "module's GND, 3V3 and EN pins, or the cable" % secs)
    elif not offs:
        note("usb", "ok", "stayed on USB %d s, MAC %s" % (secs, first[1]))
    else:
        ons = [t for t, o in events if o]
        gaps = [b - a for a, b in zip(ons, ons[1:])]
        every = " about every %.1f s" % (sum(gaps) / len(gaps)) if gaps else ""
        note("usb", "info", "left USB %d times in %d s%s, MAC %s (judged after step 2)" % (len(offs), secs, every, first[1]))
    return first, len(offs)


# --- 2. what it says -------------------------------------------------------------------------
def opened(dev):
    s = serial.Serial()
    s.port, s.baudrate, s.timeout = dev, 115200, 0.1
    s.dtr = s.rts = False
    s.open()
    return s


def listen(dev, secs):
    say("\n2. what it prints, %d s with the port open (DTR and RTS low)" % secs)
    buf, lost = b"", False
    try:
        s = opened(dev)
    except (OSError, serial.SerialException) as e:
        note("flash-holds", "FAIL", "the port wouldn't open: %s" % str(e)[:80])
        return "gone", b"", True
    try:
        end = time.time() + secs
        while time.time() < end:
            buf += s.read(4096)
        if not re.search(rb">>> |invalid header|MicroPython v|\{\"pq\":", buf):
            s.write(b"\r\n")                # a bare REPL answers with its prompt
            end = time.time() + 1.5
            while time.time() < end:
                buf += s.read(4096)
        if not re.search(rb">>> |invalid header|MicroPython v|\{\"pq\":|waiting for download", buf):
            s.write(b'{"id":1,"op":"hello"}\n')    # the console's USB link (docs/USB-LINK.md)
            end = time.time() + 3
            while time.time() < end:
                buf += s.read(4096)
    except (OSError, serial.SerialException):
        lost = True
    finally:
        try:
            s.close()
        except (OSError, serial.SerialException):
            pass
    text = buf.decode(errors="replace")
    last, n = None, 0
    for line in [l.rstrip() for l in text.splitlines() if l.strip()] + [None]:
        if line == last:
            n += 1
            continue
        if n > 1:
            say("  |   (the same line %d times in all)" % n)
        if line is not None:
            say("  | " + line[:110])
        last, n = line, 1
    rst = re.findall(r"rst:(0x[0-9a-f]+) \((\w+)\)", text)
    boot = re.findall(r"boot:(0x[0-9a-f]+) \((\w+)\)", text)
    if boot and any("DOWNLOAD" in m for _, m in boot):
        note("strap", "FAIL", "boot:%s %s: GPIO0 was low at reset. BOOT held, or GPIO0 bridged "
             "(console-s3's D0 was, to GPIO35)" % boot[-1])
    elif boot:
        note("strap", "ok", "boot:%s %s: GPIO0 high at reset" % boot[-1])
    if rst:
        note("rom-reset", "info", "last reset %s %s" % rst[-1])
    m = re.search(r'\{"pq":.*\}', text)
    if m:
        kind = "console"
        try:
            a = json.loads(m.group(0))
            detail = "%s %s, release %s" % (a.get("board", "?"), a.get("version", "?"), a.get("fp", a.get("release", "?")))
        except ValueError:
            detail = m.group(0)[:80]
    elif "invalid header" in text:
        kind, detail = "empty", "the ROM finds no program: the flash is empty"
    elif "waiting for download" in text:
        kind, detail = "loader", "in the ROM's download mode"
    elif ">>> " in text or "MicroPython v" in text:
        kind, detail = "micropython", (re.findall(r"MicroPython v[\w.\-]+ on [\d-]+", text) or ["prompt answers"])[-1]
    else:
        kind, detail = "unknown", "nothing recognised" + (" (it left USB while listening)" if lost else "")
    note("flash-holds", "info" if kind != "unknown" else "FAIL", detail)
    return kind, buf, lost


# --- 3. the module ---------------------------------------------------------------------------
def esptool(*args):
    exe = shutil.which("esptool") or shutil.which("esptool.py")
    if not exe:
        raise SystemExit("esptool not found (BRINGUP.md: it comes with the Mac's setup)")
    p = subprocess.run([exe, "--chip", "esp32s3", *args], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def module(dev):
    say("\n3. the module, esptool flash-id (reads only; the S3 restarts after)")
    rc, out = esptool("--port", dev, "flash-id")
    keep = ("Chip type", "Features", "Crystal", "MAC", "Detected flash size", "Flash type set", "Manufacturer")
    for line in out.splitlines():
        if line.strip().startswith(keep) or "Chip is" in line:
            say("  | " + line.strip())
    if rc:
        note("module", "FAIL", "esptool couldn't reach the ROM loader. Hold BOOT, tap RESET, let go of "
             "BOOT, and run again. If that fails too: the module's USB pins (13, 14) or EN")
        return
    flash = re.search(r"Detected flash size:\s*(\S+)", out)
    psram = re.search(r"Embedded PSRAM (\d+MB)", out)
    note("module-flash", "ok" if flash and flash.group(1) == "8MB" else "FAIL", flash.group(1) if flash else "not read")
    note("module-psram", "ok" if psram and psram.group(1) == "2MB" else "FAIL",
         (psram.group(1) + " embedded") if psram else "no embedded PSRAM: not an N8R2")


def flash(dev, path):
    say("\n3b. MicroPython onto the board (--flash): erase, then write")
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if digest != MICROPYTHON:
        raise SystemExit("%s has SHA-256 %s, not MicroPython 1.26.1's %s: not written" % (path, digest, MICROPYTHON))
    for args in (("--port", dev, "erase-flash"), ("--port", dev, "--baud", "460800", "write-flash", "-z", "0", path)):
        rc, out = esptool(*args)
        say("  | " + (out.strip().splitlines() or ["?"])[-1])
        if rc:
            note("flash-write", "FAIL", "esptool %s failed" % args[2 if args[2] != "--baud" else 4])
            return False
    note("flash-write", "ok", "MicroPython 1.26.1 written and hash-verified by esptool")
    return True


# --- 4. the parts, from RAM ------------------------------------------------------------------
def raw_paste(s, code):
    """Run code from RAM: raw REPL, then raw-paste with the board's flow control (as mpremote)."""
    def until(tok, t=10):
        b, end = b"", time.time() + t
        while time.time() < end:
            b += s.read(1)
            if b.endswith(tok):
                return b
        raise OSError("no %r from the board (got %r)" % (tok, b[-120:]))
    s.write(b"\r\x03\x03")
    time.sleep(0.3)
    s.read(65536)
    s.write(b"\r\x01")
    until(b"raw REPL; CTRL-B to exit\r\n>")
    s.write(b"\x05A\x01")
    if s.read(2) != b"R\x01":
        raise OSError("this MicroPython has no raw-paste mode")
    win = int.from_bytes(s.read(2), "little")
    left, i = win, 0
    while i < len(code):
        while left == 0 or s.in_waiting:
            c = s.read(1)
            if c == b"\x01":
                left += win
            elif c == b"\x04":
                raise OSError("the board ended the paste early")
        n = min(left, 64, len(code) - i)    # 64-byte pieces: what this USB keeps whole (usblink.py)
        s.write(code[i:i + n])
        i, left = i + n, left - n
    s.write(b"\x04")
    until(b"\x04")


def parts(dev, board, buttons_s, soak_s):
    say("\n4. the parts, from RAM (nothing saved on the board)")
    cfg = {"board": board, "buttons_s": buttons_s, "soak_s": soak_s}
    code = ("CFG = %r\n" % cfg).encode() + open(os.path.join(HERE, "newboard_check.py"), "rb").read()
    looks, t0 = [], time.time()
    s = opened(dev)
    try:
        raw_paste(s, code)
        say("  running. Press D0, D1 and D2 (and BOOT on a PicoquorumKey) one at a time within %d s;" % buttons_s)
        say("  then %d s more watching for restarts: hold the board, flex it gently, press the buttons." % soak_s)
        line, end = b"", time.time() + buttons_s + soak_s + 40
        while time.time() < end:
            line += s.read(256)
            while b"\n" in line:
                l, line = line.split(b"\n", 1)
                l = l.decode(errors="replace").strip()
                if l.startswith("@ "):
                    step, status, detail = (l[2:].split(" ", 2) + ["", ""])[:3]
                    if step == "done":
                        say("  done in %s" % detail)
                        return looks
                    if status == "look":
                        looks.append((step, detail))
                        say("  %-16s look  %s" % (step, detail))
                    else:
                        note(step, status, detail)
                elif l.startswith("~ "):
                    say("    " + l[2:])
                elif l.startswith("Traceback") or "Error" in l:
                    say("  ! " + l)
                    note("check-ran", "FAIL", l[:100])
        note("check-ran", "FAIL", "no end from the board in time")
    except (OSError, serial.SerialException) as e:
        note("stable", "FAIL", "the board left USB %.1f s into step 4 (%s)" % (time.time() - t0, str(e)[:60]))
        back, _ = find(dev, 15)
        if back:
            try:
                s2 = opened(back)
                raw_paste(s2, b"import machine; print('cause', machine.reset_cause())\n")
                time.sleep(0.5)
                out = s2.read(4096).decode(errors="replace")
                s2.write(b"\x02")
                s2.close()
                m = re.search(r"cause (\d)", out)
                note("came-back", "info", "reset cause %s (1: power-on, RESET or brownout)" % (m.group(1) if m else "?"))
            except (OSError, serial.SerialException) as e2:
                note("came-back", "info", "on USB again, but didn't answer: %s" % e2)
        else:
            note("came-back", "FAIL", "not back on USB in 15 s: press RESET")
        return looks
    finally:
        try:
            s.write(b"\x02")                # leave the raw REPL for the friendly one
            s.close()
        except (OSError, serial.SerialException):
            pass
    return looks


def main():
    ap = argparse.ArgumentParser(description="check a new ESP32-S3 board's soldering")
    ap.add_argument("--port")
    ap.add_argument("--board", default="auto", choices=("auto", "picoquorum-key", "console-s3"))
    ap.add_argument("--watch", type=int, default=20, help="seconds watching USB, port closed")
    ap.add_argument("--buttons", type=int, default=60, help="seconds to press every button")
    ap.add_argument("--soak", type=int, default=20, help="seconds watching for restarts after")
    ap.add_argument("--flash", metavar="BIN", help="erase and write MicroPython 1.26.1 (writes the board)")
    a = ap.parse_args()

    first, drops = watch(a.port, a.watch)
    dev = a.port or (first and first[0])
    if not dev:
        return summary()
    dev, sn = find(dev, 15)
    kind, _, _ = listen(dev, 4) if dev else ("gone", b"", "")
    if drops:      # a restart loop is the ROM's own when the flash is empty, a fault otherwise
        if kind == "empty":
            note("usb", "ok", "the drops are the empty flash's restart loop, as on every new module")
        else:
            note("usb", "FAIL", "left USB %d times running %s: a joint (module GND/3V3/EN, J1), "
                 "the cable, or a short as the board flexes" % (drops, kind))
    if kind == "console":
        note("parts", "info", "the console image is on it: not interrupted. Its Device screen and "
             "the app's Device page show its parts")
        return summary()
    if kind != "micropython" or a.flash:    # under MicroPython, step 4 reads flash and PSRAM itself;
        module(find(dev, 15)[0] or dev)     # and esptool's reset there can lose the port on macOS
    if a.flash:
        time.sleep(1)
        if not flash(find(dev, 15)[0] or dev, a.flash):
            return summary()
        time.sleep(3)
        kind, _, _ = listen(find(dev, 15)[0] or dev, 3)
    elif kind != "micropython":
        time.sleep(3)              # esptool's restart
    if kind != "micropython":
        note("parts", "skip", "buttons, screen and key need MicroPython: run again with --flash "
             "ESP32_GENERIC_S3-20250911-v1.26.1.bin (writes the board's flash)")
        return summary()
    looks = parts(find(dev, 15)[0] or dev, a.board, a.buttons, a.soak)
    for step, detail in looks:
        if sys.stdin.isatty():
            ans = input("  did the %s show: %s? [y/n] " % (step, detail)).strip().lower()
            note(step, "ok" if ans.startswith("y") else "FAIL", "seen by you" if ans.startswith("y") else "not as described")
        else:
            results.append((step, "look", detail))     # shown above while it ran
    return summary()


def summary():
    fails = [r for r in results if r[1] == "FAIL"]
    say("\n%s: %d checks, %d failed" % ("PASS" if not fails else "FAIL", len(results), len(fails)))
    for step, status, detail in fails:
        say("  %-16s %s" % (step, detail))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
