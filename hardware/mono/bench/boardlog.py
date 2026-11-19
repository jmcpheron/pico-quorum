# One Mono's history, kept in the repository: hardware/mono/boards/NN/LOG.md, an entry a step, with the
# files that step left (a prepare's log, the chip's config) beside it. Python's standard library only.
#
#   python3 hardware/mono/bench/boardlog.py 1 "what was done" [--state "where it stands now"] [--keep FILE ...]
#   python3 hardware/mono/bench/boardlog.py --table       write BOARDS.md's table of states again
#
# Each entry gets the date and time, and the commit the repository was at. --keep copies each FILE into
# the board's folder and lists it with its SHA-256. --state is the board's line in BOARDS.md's "Where
# each stands", which is written again from every board's last state.
#
# What goes in: what the bench did and read, and public things from the chip (its serial, its config, a
# prepare's log). What stays out: secrets.py, pin.json, keyflow.json, safes.json, raw relay logs
# (KEEP_OUT refuses the first four by name), and an owner's address once a board is someone's.
import fnmatch
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BOARDS = os.path.normpath(os.path.join(HERE, "..", "boards"))
INDEX = os.path.join(HERE, "BOARDS.md")
KEEP_OUT = ("secrets*", "pin.json*", "keyflow.json*", "safes.json*", "wifi.json*", ".env*")
BEGIN, END = "<!-- states: boardlog.py writes between these lines -->", "<!-- /states -->"


def folder(n):
    return os.path.join(BOARDS, "%02d" % n)


def commit():
    try:
        return subprocess.run(["git", "-C", HERE, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or "?"
    except OSError:
        return "?"


def add(n, what, state=None, keep=(), now=None):
    """Append one entry to board n's log. -> the log's path."""
    d = folder(n)
    os.makedirs(d, exist_ok=True)
    lines = []
    for src in keep:
        name = os.path.basename(src)
        if any(fnmatch.fnmatch(name, p) for p in KEEP_OUT):
            sys.exit("%s is not kept in the repository (KEEP_OUT)" % name)
        dst = os.path.join(d, name)
        if os.path.abspath(src) != os.path.abspath(dst):
            if os.path.exists(dst) and open(dst, "rb").read() != open(src, "rb").read():
                sys.exit("%s is already in %s and differs: give this one another name" % (name, d))
            shutil.copyfile(src, dst)
        lines.append("- kept [`%s`](%s), sha256 `%s`" % (name, name, hashlib.sha256(open(dst, "rb").read()).hexdigest()))
    log = os.path.join(d, "LOG.md")
    if not os.path.exists(log):
        open(log, "w").write("# Mono board %d\n\nWritten by [`boardlog.py`](../../bench/boardlog.py), an entry a step, the newest last.\n" % n)
    when = time.strftime("%Y-%m-%d %H:%M", now or time.localtime())
    entry = ["", "## %s" % when, "", what.strip(), ""] + lines + ["- repository at `%s`" % commit()]
    if state:
        entry.append("- state: %s" % state.strip())
    open(log, "a").write("\n".join(entry) + "\n")
    return log


def states():
    """-> [(n, when, state)] from each board's last state line."""
    out = []
    for name in sorted(os.listdir(BOARDS)) if os.path.isdir(BOARDS) else []:
        log = os.path.join(BOARDS, name, "LOG.md")
        if not (name.isdigit() and os.path.exists(log)):
            continue
        when = state = None
        for line in open(log):
            m = re.match(r"## (\d{4}-\d\d-\d\d)", line)
            if m:
                cur = m.group(1)
            if line.startswith("- state: "):
                when, state = cur, line[9:].strip()
        if state:
            out.append((int(name), when, state))
    return out


def table():
    """Write BOARDS.md's table of states again."""
    rows = ["| board | since | state | its log |", "|---|---|---|---|"]
    rows += ["| %d | %s | %s | [boards/%02d](../boards/%02d/LOG.md) |" % (n, when, state, n, n) for n, when, state in states()]
    text = open(INDEX).read()
    a, b = text.find(BEGIN), text.find(END)
    if a < 0 or b < a:
        sys.exit("%s has no %s ... %s" % (INDEX, BEGIN, END))
    open(INDEX, "w").write(text[:a + len(BEGIN)] + "\n" + "\n".join(rows) + "\n" + text[b:])


def main(argv):
    argv = list(argv)
    if argv == ["--table"]:
        return table()
    state, keep = None, []
    if "--keep" in argv:
        i = argv.index("--keep")
        j = next((k for k in range(i + 1, len(argv)) if argv[k].startswith("--")), len(argv))
        keep = argv[i + 1:j]
        del argv[i:j]
    if "--state" in argv:
        i = argv.index("--state")
        state = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) != 2 or not argv[0].isdigit():
        sys.exit('usage: boardlog.py N "what was done" [--state "..."] [--keep FILE ...]   |   boardlog.py --table')
    print("added to " + os.path.relpath(add(int(argv[0]), argv[1], state, keep)))
    table()


if __name__ == "__main__":
    main(sys.argv[1:])
