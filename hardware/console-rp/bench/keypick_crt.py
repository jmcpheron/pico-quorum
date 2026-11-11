# console-rp: the owner's key pick (firmware/keypick_s.py's Make, Pick, Keep) in hackui.py's CRT look.
# Bench only, a demo: NO KEY IS MADE and the key chip is never touched. On a real board GenKey makes
# the key inside the ATECC608 and only its 64-byte public key comes out; this chip's config zone is
# still open, so it can't run GenKey, and locking it can't be undone.
#
# So every number on the screen is real, but the "key" isn't one:
#   the noise          os.urandom on the RP2350, read fresh each frame and shown as it comes
#   the "public key"   64 of those bytes, standing where GenKey's answer would be
#   the owner address  firmware/webauthn.py's owner_address over them, with quorum_cfg's signer: the
#                      Safe owner such a key would have. The screen shows the live Keccak lanes as it runs
#   the blockie        that address's, as the console draws it
# The buttons, as hackui.py's: D0 ■ New (another key), D1 ▶ Full (the address in full), D2 ● Keep,
# then a red page held 3 s to "seal" (a demo screen: nothing is written).
#   put.py PORT hackui.py firmware/{webauthn,quorum_cfg}.py (with what hackui.py needs), then
#   rawrepl.py PORT keypick_crt.py --follow 5      (RESET stops it)
import gc
import os
import time
import machine
from binascii import hexlify
import lcd as L
import fonts as F
import blockies
import hackui as H
import webauthn
import quorum_cfg

d, W, BODY0, FOOT = H.d, H.W, H.BODY0, H.FOOT
COLS, ROW0, ROWS = H.COLS, H.ROW0, H.ROWS
SIGNER = quorum_cfg.CFG["signer"]


def theme(red=False):
    H.th = H.RED if red else H.NORMAL


noise = H.noise                         # os.urandom as hex, each frame (hackui.py)


# ----------------------------------------------------------------------------- the address, live
def churn(_t=None):
    live = H.live
    if live["busy"]:
        return
    live["busy"] = True
    try:
        n = live["n"]
        H.bg(H.HY - 2, 112)
        H.hash_rows(H.lanes_hex(), "acc")
        H.t8("PASS %d  CREATE2 // OWNER" % n, H.HX, 94, "mute")
        d.fill_rect(H.HX, 106, 224, 3, H.c("dim"))
        d.fill_rect(H.HX, 106, 224 * min(n, 7) // 7, 3, H.c("acc"))
        H.push_rows(H.HY - 2, 112)
    except Exception as e:
        print("churn:", e)
    finally:
        live["busy"] = False


def derive(qx, qy):
    """webauthn.owner_address, with the Keccak state on the screen while it runs. -> (address, final hash hex)"""
    H.live["A"], H.live["n"] = None, 0
    tm = machine.Timer(period=60, mode=machine.Timer.PERIODIC, callback=churn)
    t0 = time.ticks_ms()
    try:
        a = webauthn.owner_address(qx, qy, SIGNER)
    finally:
        tm.deinit()
    while H.live["busy"]:
        pass
    ms = time.ticks_diff(time.ticks_ms(), t0)
    final = H.lanes_hex()
    print("owner %s (%d ms, %d passes)" % (a, ms, H.live["n"]))
    return a, final, ms


# ----------------------------------------------------------------------------- screens
def groups(a):
    """0x and the 40 digits in lines of three groups of four."""
    g = [a[2:6]] + [a[i:i + 4] for i in range(6, 42, 4)]
    g[0] = "0x" + g[0]
    return [" ".join(g[i:i + 3]) for i in range(0, len(g), 3)]


def draw_intro():
    theme()
    H.bg()
    H.header("> MAKE YOUR KEY", "")
    for i, (s, k) in enumerate((("THE CHIP MAKES THE KEY.", "ink"), ("IT NEVER LEAVES THE CHIP.", "ink"),
                                ("MAKE AS MANY AS YOU LIKE,", "mute"), ("KEEP THE ONE WHOSE", "mute"),
                                ("PICTURE YOU LIKE.", "mute"))):
        H.t8(s, 8, 22 + 13 * i, k)
    H.t8("DEMO: NO KEY IS MADE", 8, 100, "warn")
    H.footer((("MENU", "ink"), None, ("START", "acc")))


def draw_pick(st):
    theme()
    H.bg()
    H.header("> KEY #%d" % st["n"], "PICK")
    blockies.draw(d, st["addr"], 6, 18, 12)          # 96 px
    x = 110
    H.t8("OWNER ADDRESS", x, 20, "mute")
    for i, line in enumerate(groups(st["addr"])):
        H.tf(line, x, 32 + 15 * i, "mono13", "ink")
    H.t8("MADE IN %.1f S" % (st["ms"] / 1000), x, 100, "dim")
    H.footer((("NEW", "ink"), ("FULL", "ink"), ("KEEP", "ok")))


def draw_full(st):
    theme()
    H.bg()
    H.header("> KEY #%d" % st["n"], "FULL")
    H.t8("OWNER ADDRESS (EIP-55)", 8, 20, "mute")
    a = checksum(st["addr"])
    for i in range(3):
        H.tf(a[i * 14:(i + 1) * 14], 8, 34 + 18 * i, "mono13", "ink")
    blockies.draw(d, st["addr"], 192, 30, 5)
    H.t8("PUBLIC KEY " + st["pub"][:8] + ".." + st["pub"][-6:], 8, 96, "dim")
    H.footer((("NEW", "ink"), ("BACK", "ink"), ("KEEP", "ok")))


def checksum(a):
    from keccak import keccak256
    a = a.lower()[2:]
    h = hexlify(keccak256(a.encode())).decode()
    return "0x" + "".join(ch.upper() if int(h[i], 16) >= 8 else ch for i, ch in enumerate(a))


def draw_keep(st, hold=None):
    theme(True)
    H.bg()
    H.header("!! KEEP KEY #%d" % st["n"], "RED")
    for i, (s, k) in enumerate((("SEALING IS FOREVER.", "ink"), ("THIS CHIP WILL HOLD", "ink"),
                                ("THIS KEY AND NO OTHER.", "ink"), ("NO UNDO.", "bad"))):
        H.t8(s, 8, 22 + 13 * i, k)
    blockies.draw(d, st["addr"], 192, 22, 5)
    H.t8("HOLD", 8, 96, "ink")
    H.circ(44, 95, "bad")
    H.t8("3 S TO SEAL", 60, 96, "ink")
    H.footer((("BACK", "ink"), None, ("SEAL", "bad")), hold=hold)


def draw_done(st):
    theme()
    H.bg()
    H.header("> KEY #%d" % st["n"], "SEALED")
    H.tf("SEALED", 8, 22, "monob28", "ok")
    blockies.draw(d, st["addr"], 192, 20, 5)
    H.tf(st["addr"][:6] + "…" + st["addr"][-4:], 8, 64, "mono13", "ink")
    H.t8("DEMO: NOTHING WAS WRITTEN", 8, 88, "warn")
    H.t8("TO THE CHIP.", 8, 99, "warn")
    H.footer((None, ("AGAIN", "ink"), None))


def lock(draw, *args):
    """The finished page locking in over fresh noise (hackui's FX3): an address worked out here."""
    H.arrive(draw, *args, fx="lock")


# ----------------------------------------------------------------------------- making a key
def make(n):
    """The noise, the "public key" arriving out of it, the address worked out. -> state."""
    theme()
    H.bg()
    H.header("> GENKEY // SLOT 0", "KEY #%d" % n)
    H.footer((None, None, None))
    H.push_rows(0, H.H)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 1200:          # entropy
        noise()
        H.push_rows(BODY0, FOOT)
    pub_b = os.urandom(64)                                      # where GenKey's answer would be
    pub = hexlify(pub_b).decode()
    H.header("> PUBLIC KEY  64 B", "KEY #%d" % n)
    H.push_rows(0, BODY0)
    t0 = time.ticks_ms()
    while True:                                                 # its 128 digits landing in reading order
        el = time.ticks_diff(time.ticks_ms(), t0)
        shown = min(128, 128 * el // 900)
        noise(pub, shown)
        H.push_rows(BODY0, FOOT)
        if shown == 128:
            break
    time.sleep_ms(250)
    H.header("> KECCAK256 // OWNER", "KEY #%d" % n)
    H.bg(BODY0, FOOT)
    H.t8("THE SAFE OWNER THIS KEY GETS", H.HX, 19, "acc")
    H.push_rows(0, FOOT)
    qx, qy = "0x" + pub[:64], "0x" + pub[64:]
    addr, final, ms = derive(qx, qy)
    # The last 20 bytes of the final hash are the address: the rest dims, they light up green.
    for k in range(6):
        H.bg(H.HY - 2, 112)
        cw = F.width("0", "mono13")
        for r in range(4):
            x = H.HX
            for g in range(4):
                i0 = r * 16 + g * 4
                s = final[i0:i0 + 4]
                H.tf(s, x, H.HY + 15 * r, "mono13", "ok" if i0 >= 24 and k >= 2 else "dim" if k >= 2 else "ink")
                x += cw * 5
        H.t8("THE LAST 20 BYTES: THE ADDRESS" if k >= 2 else "", H.HX, 94, "ok")
        H.push_rows(H.HY - 2, 112)
        time.sleep_ms(120)
    time.sleep_ms(500)
    return {"n": n, "pub": pub, "addr": addr, "ms": ms}


def hold(st, need=3000):
    t0 = time.ticks_ms()
    while H.keys[2]() == 0:
        el = time.ticks_diff(time.ticks_ms(), t0)
        draw_keep(st, hold=min(1, el / need))
        d.fill_rect(8, 106, 224, 5, H.c("dim"))
        d.fill_rect(8, 106, 224 * min(el, need) // need, 5, H.c("bad"))
        H.push_rows(90, H.H)
        if el >= need:
            H._prev[2] = True
            return True
        time.sleep_ms(20)
    H._prev[2] = False
    draw_keep(st)
    H.push_rows(0, H.H)
    return False


def wait_key():
    while True:
        k = H.pressed()
        if k is not None:
            return k
        time.sleep_ms(10)


def main():
    """Make, pick, keep, until D0 (Menu) on the intro."""
    while True:
        H.arrive(draw_intro)
        while True:
            k = wait_key()
            if k == 0:
                return
            if k == 2:
                break
        n = 1
        st = make(n)
        lock(draw_pick, st)
        view = "pick"
        while True:
            k = wait_key()
            print("key D%d on %s, key #%d" % (k, view, st["n"]))
            if k == 0 and view != "keep":                       # another key
                n += 1
                H.glitch(6, 14)
                st = make(n)
                lock(draw_pick, st)
                view = "pick"
            elif k == 1 and view in ("pick", "full"):
                view = "full" if view == "pick" else "pick"
                (draw_full if view == "full" else draw_pick)(st)
                H.glitch(5, 8)
            elif k == 1 and view == "keep":
                pass
            elif k == 2 and view in ("pick", "full"):
                view = "keep"
                H.arrive(draw_keep, st, strong=True)
            elif k == 0 and view == "keep":
                pass
            elif k == 2 and view == "keep":
                if hold(st):
                    lock(draw_done, st)
                    while wait_key() != 1:
                        pass
                    break
            if view == "keep" and k == 0:
                view = "pick"
                draw_pick(st)
                H.glitch(5, 8)


if __name__ == "__main__":                 # run, not imported (glitchfx.py borrows its pages)
    gc.collect()
    print("keypick_crt: D0 new, D1 full, D2 keep (then hold 3 s on the red page); heap %d KB" % (gc.mem_free() // 1024))
    main()
