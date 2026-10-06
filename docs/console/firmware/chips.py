# The chips this board has seen, by serial: a number, a name and a screen theme for each, so a
# glance at the screen says which chip is in. The first chip seen is chip 1 (dark), the next chip 2
# (light), then dark again. chips.json on flash; every push keeps it (manifest "preserve").
#
# Cosmetic only. Nothing here decides what gets signed: the console's pin (secrets.QUORUM_EXPECT)
# does, from the chip itself, whatever this file says. A chip swapped for another with a doctored
# chips.json still fails the pin.
#
#   entry, new = seen(serial, profile, owner=...)
#   entry: {"n": 2, "name": "chip 2", "theme": "light", "first": unix, "profile": "quorum-v1", ...}
import json
import time

FILE = "chips.json"
THEMES = ("dark", "light")


def load():
    try:
        with open(FILE) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}       # none yet, or a damaged file: start again (it is only names and colours)


def save(d):
    try:
        with open(FILE + ".tmp", "w") as f:
            json.dump(d, f)
        import os
        os.rename(FILE + ".tmp", FILE)      # whole or not at all
    except OSError as e:
        print("chips:", e)


def _now():
    t = time.time()
    return t if time.gmtime(t)[0] >= 2025 else 0


def seen(serial, profile=None, **extra):
    """This chip's entry, registered the first time it is seen; profile and any extra fields
    (owner, provisioned) brought up to date. -> (entry, new)."""
    if not serial:
        return None, False
    d = load()
    e = d.get(serial)
    new = e is None
    if new:
        n = max([v.get("n", 0) for v in d.values() if isinstance(v, dict)] + [0]) + 1
        e = {"n": n, "name": "chip %d" % n, "theme": THEMES[(n - 1) % 2], "first": _now()}
    changed = new
    for k, v in (("profile", profile),) + tuple(extra.items()):
        if v is not None and e.get(k) != v:
            e[k] = v
            changed = True
    if changed:
        d[serial] = e
        save(d)
    return e, new


PROFILE_SHORT = {"quorum-v1": "quorum v1", "legacy-test": "test table", "factory": "fresh", "unknown": "unknown table",
                 "quorum-tm1": "Trust M", "quorum-tm1-open": "Trust M, open"}
