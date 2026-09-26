# The console's rules that need no screen, no network and no chip, so they are tested on their own
# (test-vectors/run-console.mjs). quorum.py calls these; nothing here draws or talks to anything.

HEX = "0123456789abcdef"


def is_address(a):
    return isinstance(a, str) and len(a) == 42 and a[:2] in ("0x", "0X") and all(c in HEX for c in a[2:].lower())


def expect_check(expect, serial, slot, row, owner):
    """Is this the chip, slot and key the board was pinned to (secrets.QUORUM_EXPECT)?
    expect: {"serial", "slot", "owner", "locked"}; row: atecc.decode_slot for the slot (None on a
    software key); owner: the owner address computed from the chip's public key. -> (ok, why)."""
    if not expect:
        return False, "no QUORUM_EXPECT in secrets.py"
    want = str(expect.get("serial", "")).lower()
    if not want or serial.lower() != want:
        return False, "another chip is in the board"
    if int(expect.get("slot", -1)) != slot:
        return False, "not the pinned slot"
    if row is None:
        return False, "no slot table"
    if row.get("kind") != "P256" or not row.get("extSign"):
        return False, "slot %d is not a signing key" % slot
    if expect.get("locked", True) and not row.get("locked"):
        return False, "slot %d is not locked" % slot
    want_owner = str(expect.get("owner", "")).lower()
    if not owner or owner.lower() != want_owner:
        return False, "its owner is not the pinned one"
    return True, ""


def valid_info(info, safe):
    """The service's view of the Safe, checked for shape before anything shows or uses it.
    -> (ok, why)."""
    if not isinstance(info, dict):
        return False, "not an object"
    if str(info.get("address", safe)).lower() != safe.lower():
        return False, "another Safe"
    owners = info.get("owners")
    if not isinstance(owners, list) or not owners or not all(is_address(o) for o in owners):
        return False, "bad owner list"
    try:
        t = int(info.get("threshold"))
        int(info.get("nonce"))
    except (TypeError, ValueError):
        return False, "bad threshold or nonce"
    if not 1 <= t <= len(owners):
        return False, "threshold %d of %d owners" % (t, len(owners))
    return True, ""


def counter_check(stored, now):
    """The chip's signature counter against the one this console last wrote down.
    -> ("first" | "same" | "outside" | "backwards", signatures made outside the console)."""
    if stored is None:
        return "first", 0
    if now == stored:
        return "same", 0
    if now > stored:
        return "outside", now - stored
    return "backwards", 0


def is_sim(base):
    """tools/quorum's simulated service on the laptop (plain HTTP on the LAN) has its own /sim
    endpoints; Safe's real service (HTTPS) must never be sent those."""
    return bool(base) and base.startswith("http://")


def poll_defaults(base, api_key):
    """(active, idle) poll periods in seconds. The real service counts requests against a monthly
    quota: 50,000 with an API key, 5,000 without (each poll is about one request)."""
    if is_sim(base):
        return 3, 120
    if api_key:
        return 20, 600
    return 60, 1800
