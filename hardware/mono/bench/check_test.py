# check.py against a made-up board on a pty: stage0's lines as the emulator run sent them
# (stage0_test.mjs), the facts answered when asked, and the counts rising as if pressed. No board.
#   python3 hardware/mono/bench/check_test.py
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check

GOOD = ["fact: Pico2, RP2350", "fact: MicroPython 1.26.1", "fact: 150 MHz, 440 KB free", "fact: id 656d750000000000",
        "fact: I2C0: 60", "fact: ATECC608 rev 00006002", "fact: serial 0123e100e1e1e1e1ee",
        "fact: data open, config open", "fact: KEY 2: off 00 on 11, empty"]
BAD = GOOD[:8] + ["FAIL: KEY 2: off 00 on 00, not scanned"]


def board(fd, lines, presses, stop):
    """stage0's side of the link: the facts when asked, and a count line (every 0.2 s here) on which
    each button in presses goes up once, one line apart, from a second after the facts went."""
    n, asked, counts, buf = 0, None, [0, 0, 0], b""
    os.set_blocking(fd, False)
    while not stop.is_set():
        try:
            buf += os.read(fd, 256)
        except (BlockingIOError, OSError):
            pass
        if b"facts" in buf:
            buf, asked = b"", n
            os.write(fd, ("\r\n".join(lines) + "\r\nfacts: %d\r\n" % len(lines)).encode())
        n += 1
        if asked is not None and 0 <= n - asked - 5 < len(presses):
            counts[presses[n - asked - 5]] += 1
        os.write(fd, ("Mono bring-up %d: D0 %d D1 %d D2 %d\r\n" % (n, *counts)).encode())
        time.sleep(0.2)


def run(lines, presses, answers, wait=60):
    master, slave = os.openpty()
    stop = threading.Event()
    t = threading.Thread(target=board, args=(master, lines, presses, stop))
    t.start()
    said, answers = [], list(answers)
    old = check.pressed.__defaults__
    check.pressed.__defaults__ = (wait,)
    with tempfile.NamedTemporaryFile("r", suffix=".md") as log:
        try:
            code = check.main([os.ttyname(slave), "--board", "7", "--log", log.name], ask=lambda q: answers.pop(0), say=said.append)
        finally:
            check.pressed.__defaults__ = old
            stop.set()
            t.join()
        return code, said, log.read()


failed = 0


def ok(what, cond):
    global failed
    print(("ok    " if cond else "FAIL  ") + what)
    failed += not cond


code, said, log = run(GOOD, [0, 1, 2], "yyyy")
ok("a good board passes", code == 0 and log.rstrip().endswith("| pass |"))
ok("its row names the board, its id, its key and KEY 2",
   log.startswith("| 7 | ") and "`656d750000000000`" in log and "`0123e100e1e1e1e1ee`" in log
   and "rev 00006002, data open, config open" in log and "off 00 on 11, empty" in log and "| D0 D1 D2 |" in log)
ok("the row has the header's columns", log.count("|") == check.HEAD.count("|"))

code, said, log = run(BAD, [0, 1, 2], "yyyy")
ok("stage0's FAIL line fails the board", code == 1 and "FAIL: KEY 2: off 00 on 00, not scanned" in log)

code, said, log = run(GOOD, [0, 2], "yyyy", wait=3)
ok("a button never pressed fails it", code == 1 and "no press from D1" in log and "| not D1 |" in log)

code, said, log = run(GOOD, [0, 1, 2], "ynyy")
ok("a no to what eyes check fails it", code == 1 and "3 of 4" in log and check.EYES[1] in log)

sys.exit(1 if failed else 0)
