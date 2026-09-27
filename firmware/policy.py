# The console's rules that need no screen, no network and no chip, so they are tested on their own
# (test-vectors/run-console.mjs). quorum.py calls these; nothing here draws or talks to anything.

HEX = "0123456789abcdef"


def is_address(a):
    return isinstance(a, str) and len(a) == 42 and a[:2] in ("0x", "0X") and all(c in HEX for c in a[2:].lower())


def pins(expect):
    """secrets.QUORUM_EXPECT as a list: one pinned chip (a dict) or several (a list of them)."""
    if not expect:
        return []
    return [p for p in (expect if isinstance(expect, (list, tuple)) else [expect]) if isinstance(p, dict)]


def pick(pinned, serial):
    """The pinned entry for the chip with this serial, or None: the board may pin several chips,
    and at boot the one on the bus says which entry applies."""
    for p in pinned:
        if serial and str(p.get("serial", "")).lower() == serial.lower():
            return p
    return None


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


MAX_SAFES = 4       # each one is a queue and a set of decoded transactions in RAM


def safes(many, one):
    """secrets.QUORUM_SAFES (a list) or QUORUM_SAFE (one) as a checked list of
    {"chainId", "address", "name"} (and "url" when one names its own service, overriding the
    chain's). -> (list, why): why says what was dropped, or ""."""
    given = many if many else ([one] if one else [])
    if not isinstance(given, (list, tuple)):
        return [], "QUORUM_SAFES is not a list"
    out, seen, why = [], set(), ""
    for s in given:
        try:
            c, a = int(s["chainId"]), str(s["address"]).lower()
        except (KeyError, TypeError, ValueError):
            why = why or "a Safe without chainId or address"
            continue
        if not is_address(a):
            why = why or "a Safe with a bad address"
            continue
        if (c, a) in seen:
            continue
        if len(out) == MAX_SAFES:
            why = why or "more than %d Safes: the rest are not watched" % MAX_SAFES
            break
        seen.add((c, a))
        e = {"chainId": c, "address": a, "name": str(s.get("name") or "Safe")[:24]}
        if isinstance(s.get("url"), str) and s["url"]:
            e["url"] = s["url"]         # this Safe's own service (a second simulated Safe on the laptop)
        out.append(e)
    return out, why


def service_url(cfg, chain, override=None):
    """Where to ask about a Safe on this chain: secrets.QUORUM_URL when set (the laptop's
    simulation or fork), else Safe's own service for the chain, pinned in cfg["services"]. None for
    a chain the console has no service for."""
    if override:
        return override
    return cfg.get("services", {}).get(str(chain))


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


MAX_BOOK = 64       # pinned names, all chains together


def book(given):
    """secrets.QUORUM_BOOK, the owner's own names, checked: {"<chainId>" or "*": {address: name}},
    a name being "label", "name.eth" or ["label", "name.eth"] (tools/quorum book add writes it).
    -> (book, why): why says what was dropped, or ""."""
    if not given:
        return {}, ""
    if not isinstance(given, dict):
        return {}, "QUORUM_BOOK is not a dict"
    out, n, why = {}, 0, ""
    for k, names in given.items():
        k = str(k)
        if k != "*" and not k.isdigit():
            why = why or "QUORUM_BOOK: %s is not a chain id" % k
            continue
        if not isinstance(names, dict):
            why = why or "QUORUM_BOOK[%s] is not a dict" % k
            continue
        for a, v in names.items():
            a = str(a).lower()
            if isinstance(v, (list, tuple)):
                v = [str(x)[:32] for x in v[:2] if x]
                ok = bool(v)
            else:
                v = str(v)[:32]
                ok = bool(v)
            if not is_address(a) or not ok:
                why = why or "QUORUM_BOOK: a bad entry for %s" % a[:12]
                continue
            if n == MAX_BOOK:
                return out, "more than %d names in QUORUM_BOOK: the rest are not used" % MAX_BOOK
            out.setdefault(k, {})[a] = v
            n += 1
    return out, why
