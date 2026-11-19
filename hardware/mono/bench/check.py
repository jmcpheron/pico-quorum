# One Mono's bring-up, as a row for BOARDS.md: what stage0.py says over the USB-C, and what only the
# person at the bench can see. Python's standard library only (termios, as tools/relay): a Mac or Linux.
#
#   python3 hardware/mono/bench/check.py /dev/cu.usbmodemXXXX --board 1 [--log hardware/mono/bench/BOARDS.md]
#
# It asks stage0 for its facts, and the answer coming back is the link working both ways. It waits
# for D0, D1 and D2 to be pressed, asks what eyes must check, prints the row, and appends it to
# --log. The only thing it sends is the word `facts`. It exits 1 if anything failed.
import os
import re
import select
import sys
import termios
import time

EYES = ("a white line along all four edges of the screen",
        "red, green and blue squares at the top right, in that order",
        "the text the right way up, with D0's box over the left button",
        "each box green while its button was held, and the red LED lit with it")
HEAD = "| board | date | USB serial | RP2350 id | key chip | key | KEY 2 | buttons | by eye | result |"


def open_serial(path):
    """The CH343P, raw, 8N1, 115200, no flow control (tools/relay/relay.py's, at stage0's rate)."""
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(fd)
    iflag &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP | termios.INLCR | termios.IGNCR
               | termios.ICRNL | termios.IXON | termios.IXOFF | termios.IXANY)
    oflag &= ~termios.OPOST
    lflag &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
    cflag &= ~(termios.CSIZE | termios.PARENB | termios.CSTOPB | getattr(termios, "CRTSCTS", 0))
    cflag |= termios.CS8 | termios.CREAD | termios.CLOCAL
    cc[termios.VMIN], cc[termios.VTIME] = 0, 0
    termios.tcsetattr(fd, termios.TCSANOW, [iflag, oflag, cflag, lflag, termios.B115200, termios.B115200, cc])
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


class Lines:
    """Whole lines from the port as they come."""

    def __init__(self, fd):
        self.fd, self.buf = fd, b""

    def read(self, wait):
        """-> the lines that arrive within wait seconds, as soon as there are any."""
        end = time.time() + wait
        while b"\n" not in self.buf and time.time() < end:
            if select.select([self.fd], [], [], 0.1)[0]:
                self.buf += os.read(self.fd, 4096)
        *whole, self.buf = self.buf.split(b"\n")
        return [l.decode("latin1").strip() for l in whole]


def facts(port, say):
    """Ask, three times at most. -> the fact lines of one whole answer, or None."""
    for _ in range(3):
        os.write(port.fd, b"facts\r\n")
        got, end = [], time.time() + 3
        while time.time() < end:
            for l in port.read(0.5):
                if l.startswith(("fact: ", "FAIL: ")):
                    got.append(l)
                elif l.startswith("facts: "):
                    if l == "facts: %d" % len(got):
                        return got
                    got = []            # the tail of an answer that began before we listened
        say("  no answer yet, asking again")
    return None


def counts(port, wait):
    """-> D0, D1 and D2's counts from stage0's next 2 s line, or None when none comes within wait."""
    end = time.time() + wait
    while time.time() < end:
        for l in port.read(0.5):
            m = re.match(r"Mono bring-up \d+: D0 (\d+) D1 (\d+) D2 (\d+)$", l)
            if m:
                return [int(v) for v in m.groups()]
    return None


def pressed(port, say, wait=60):
    """Wait for each of D0, D1, D2 to count up from where it stood. -> the names that never did."""
    names = ["D0", "D1", "D2"]
    base = counts(port, 5)
    if base is None:
        return names
    left, end = list(names), time.time() + wait
    say("press D0, D1 and D2, once each (%d s)" % wait)
    while left and time.time() < end:
        now = counts(port, 1) or base
        for i, name in enumerate(names):
            if name in left and now[i] > base[i]:
                left.remove(name)
                say("  %s" % name)
    return left


def main(argv, ask=input, say=print):
    argv = list(argv)
    opt = {}
    for name in ("--board", "--log"):
        if name in argv:
            i = argv.index(name)
            opt[name] = argv[i + 1]
            del argv[i:i + 2]
    if len(argv) != 1:
        sys.exit("usage: check.py PORT [--board N] [--log BOARDS.md]")
    path = argv[0]
    port = Lines(open_serial(path))
    wrong = []
    got = facts(port, say)
    if got is None:
        sys.exit("nothing from stage0 on %s: is it the board's main.py, and is this the board's port?" % path)
    for l in got:
        say("  " + l)
    wrong += [l[6:] for l in got if l.startswith("FAIL: ")]
    f = [l[6:] for l in got]
    pick = lambda start: next((l[len(start):] for l in f if l.startswith(start)), "-")
    left = pressed(port, say)
    if left:
        wrong.append("no press from " + " ".join(left))
    unseen = []
    for q in EYES:
        a = ask("%s? [y/n] " % q).strip().lower()
        if a not in ("y", "yes"):
            unseen.append(q)
    wrong += unseen
    usb = re.search(r"usbmodem(\w+)$", path)
    row = "| %s | %s | `%s` | `%s` | `%s` | rev %s, %s | %s | %s | %s | %s |" % (
        opt.get("--board", "?"), time.strftime("%Y-%m-%d"), usb.group(1) if usb else os.path.basename(path),
        pick("id "), pick("serial "), pick("ATECC608 rev "), next((l for l in f if l.startswith("data ")), "-"),
        pick("KEY 2: "), "D0 D1 D2" if not left else "not " + " ".join(left),
        "as it should be" if not unseen else "%d of %d" % (len(EYES) - len(unseen), len(EYES)),
        "pass" if not wrong else "FAIL: " + "; ".join(wrong))
    say(HEAD)
    say(row)
    if "--log" in opt:
        with open(opt["--log"], "a") as log:
            log.write(row + "\n")
        say("added to " + opt["--log"])
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
