# Layer 5: a Safe transaction's fields in plain language, one item per thing it does. Pure (no
# screen, no network), so test-vectors/run.py checks it on CPython and on MicroPython.
#
# Everything here is decoded from the same to/value/data/operation that safe_tx.py hashes. The
# service's own "dataDecoded" is never read. Names come from the pinned config (quorum_cfg.py) and
# are hints: an item always carries the full address too.
#
#   ctx = context(quorum_cfg.CFG, safe)
#   review(tx, ctx) -> {"summary": "Send 1.5 ETH", "level": "ok" | "warn" | "red", "items": [...]}
#
# An item is a dict: title (one screen header), level, what (one line), and as needed amount,
# to and label (what that address is: "to", "new owner", "spender"...), frm and frm_label (an
# address being replaced or moved from), text (the explanation), and for calls nobody decoded
# selector, size and digest (ERC-8213's calldata digest, to compare with what the proposer sent).
# Items that call a contract carry it as "contract"; identify() says whether it is a known one.
# "red" is anything that can take the Safe away from its owners or pay out more than it shows:
# owner, threshold, module, guard and handler changes, delegatecall, gas refunds, unlimited
# approvals, and every call this file cannot decode.
from binascii import hexlify
from keccak import keccak256

CALL, DELEGATECALL = 0, 1
LEVELS = ("ok", "warn", "red")
ZERO = "0x0000000000000000000000000000000000000000"
UNLIMITED = 1 << 255    # approvals at or above this are "forever" (max uint256 is the usual one)

# selector -> signature. test-vectors/run.py checks every one against keccak.
SIGS = {
    "a9059cbb": "transfer(address,uint256)",
    "095ea7b3": "approve(address,uint256)",
    "23b872dd": "transferFrom(address,address,uint256)",
    "8d80ff0a": "multiSend(bytes)",
    "0d582f13": "addOwnerWithThreshold(address,uint256)",
    "f8dc5dd9": "removeOwner(address,address,uint256)",
    "e318b52b": "swapOwner(address,address,address)",
    "694e80c3": "changeThreshold(uint256)",
    "610b5925": "enableModule(address)",
    "e009cfde": "disableModule(address,address)",
    "e19a9dd9": "setGuard(address)",
    "f08a0323": "setFallbackHandler(address)",
    "22895118": "deposit(bytes,bytes,bytes,bytes32)",
}

DONT = "Don't sign unless you were told exactly what to expect."
AS_SAFE = "Runs this contract's code as the Safe itself: it could move everything and change the owners."


def hx(b):
    return "0x" + hexlify(b).decode()


def _bytes(h):
    if isinstance(h, (bytes, bytearray)):
        return bytes(h)
    h = h[2:] if h.startswith("0x") else h
    return bytes.fromhex(h)


def group(n):
    """12345678 -> 12,345,678"""
    s, out = str(n), ""
    while len(s) > 3:
        out = "," + s[-3:] + out
        s = s[:-3]
    return s + out


def units(n, decimals):
    """An integer amount in its token's units, every significant digit kept: 1500000, 6 -> 1.5"""
    whole, frac = divmod(int(n), 10 ** decimals)
    if not frac:
        return group(whole)
    f = str(frac)
    f = ("0" * (decimals - len(f)) + f).rstrip("0")
    return group(whole) + "." + f


def for_chain(cfg, key, chain):
    """One of cfg's per-chain lists ("tokens", "batchers", "contracts", "delegates") for this chain,
    lowercase: the "*" entries (the same contract everywhere) and the chain's own, or those of the
    chain it is the same as (cfg["sameAs"]: the Anvil fork of Base has Base's). None: every chain's."""
    lists = cfg.get(key, {})
    if chain is None:
        keys = list(lists)
    else:
        c = str(chain)
        keys = ["*", cfg.get("sameAs", {}).get(c, c)]
    out = {}
    for k in keys:
        for a, v in lists.get(k, {}).items():
            out[a.lower()] = v
    return out


def pinned_for(book, chain):
    """secrets.QUORUM_BOOK for this chain -> {address: (label, ens)}: the "*" entries and the
    chain's own. A name is "label", "name.eth", or ["label", "name.eth"]: the owner of this console
    pinned it (tools/quorum book add), after the laptop resolved the ENS name both ways."""
    out = {}
    for k in ("*", str(chain)):
        for a, v in (book or {}).get(k, {}).items():
            if isinstance(v, (list, tuple)):
                label, ens = str(v[0]), (str(v[1]) if len(v) > 1 and v[1] else None)
            else:
                v = str(v)
                label, ens = v, (v if v.endswith(".eth") else None)
            out[a.lower()] = (label, ens)
    return out


SYSTEM_NAMES = {"withdraw": "Withdrawal requests", "consolidate": "Consolidations", "deposit": "Deposit contract"}


def validators_of(given):
    """secrets.QUORUM_VALIDATORS -> {pubkey hex (0x + 96, lowercase): (label, index or None)}. An
    entry is "label" or ["label", index]: the validators this Safe is the withdrawal address of."""
    out = {}
    for k, v in (given or {}).items():
        if isinstance(v, (list, tuple)):
            label, idx = str(v[0]), (int(v[1]) if len(v) > 1 and v[1] is not None else None)
        else:
            label, idx = str(v), None
        out[k.lower()] = (label, idx)
    return out


def context(cfg, safe, names=None, chain=None, pinned=None, seen=None, validators=None):
    """What review() needs from the pinned config, with lowercase keys, for a Safe on this chain.
    names: extra {address: name}, such as this console's own owner address. chain: the pinned
    address book (Alice, Bob...) is the laptop's Anvil accounts, so it names addresses only on the
    chains in cfg["bookChains"]; on Base mainnet those same addresses carry sweeper code
    (docs/LADDER.md). Tokens, batchers, contracts and delegates are this chain's (for_chain).
    pinned: secrets.QUORUM_BOOK, the console owner's own names (pinned_for). seen: {address: n},
    how many times this console signed a payment to each address on this chain (quorum.py keeps
    it on flash); the same dict, so a signature counts from the next review on."""
    book = {}
    if chain is None or chain in cfg.get("bookChains", [31337]):
        for a, n in cfg["book"].items():
            book[a.lower()] = n
    pin = pinned_for(pinned, chain)
    for a, (label, ens) in pin.items():
        book[a] = label
    for a, n in (names or {}).items():
        book[a.lower()] = n
    system = for_chain(cfg, "system", chain)
    contracts = for_chain(cfg, "contracts", chain)
    for a, kind in system.items():
        contracts[a] = [SYSTEM_NAMES[kind], "eth", {}]
    return {"safe": safe.lower(), "book": book, "pinned": pin, "seen": seen if seen is not None else {},
            "tokens": for_chain(cfg, "tokens", chain),
            "batchers": for_chain(cfg, "batchers", chain), "contracts": contracts,
            "delegates": for_chain(cfg, "delegates", chain), "system": system,
            "validators": validators_of(validators), "feeWarn": int(cfg.get("validatorFeeWarn", 10 ** 16))}


def name(ctx, a):
    return ctx["book"].get(a.lower())


def identify(ctx, a):
    """(name, logo, known) for an address: this Safe, a pinned contract, or a name from the
    address book (people have no logo). (None, None, False) for anything else."""
    a = a.lower()
    if a == ctx["safe"]:
        return "This Safe", "safe", True
    k = ctx["contracts"].get(a)
    if k:
        return k[0], k[1], True
    n = ctx["book"].get(a)
    if n:
        return n, None, True
    return None, None, False


def ens_of(ctx, a):
    """The ENS name pinned for this address, or None."""
    p = ctx.get("pinned", {}).get(a.lower())
    return p[1] if p else None


# ----------------------------------------------------------------------------- recipients
# Who gets paid is where a Safe loses money: to a stranger, or to an address made to look like one
# the owners use (address poisoning: the same first and last characters, which is all most people
# compare). Every item that pays or allows someone (label "to" or "spender") is checked against
# every address this console knows: the book, pinned contracts, this Safe, and the ones it has
# paid before.
PAYS = ("to", "spender")


def _looks(a, b):
    return a != b and a[2:6] == b[2:6] and a[-4:] == b[-4:]


def lookalike(ctx, a):
    """The name (or short form) of a known address that a differs from but looks like, or None."""
    a = a.lower()
    if a in ctx["book"] or a in ctx["contracts"] or a == ctx["safe"]:
        return None
    for k, n in ctx["book"].items():
        if _looks(a, k):
            return n
    for k, v in ctx["contracts"].items():
        if _looks(a, k):
            return v[0]
    if _looks(a, ctx["safe"]):
        return "This Safe"
    for k in ctx.get("seen", {}):
        if _looks(a, k):
            return k[:6] + "\u2026" + k[-4:]
    return None


def _recipients(items, ctx):
    for it in items:
        a = it.get("to")
        if not a or it.get("label", "to") not in PAYS:
            continue
        a = a.lower()
        it["seen"] = ctx.get("seen", {}).get(a, 0)
        like = lookalike(ctx, a)
        if like:
            it["lookalike"] = like
            it["level"] = "red"
            it["text"] = ("Same start and end as %s, but a different address: address poisoning. " % like
                          + it.get("text", "")).strip()


def paid(r):
    """The addresses a reviewed transaction pays or allows, for quorum.py's count of them."""
    return [it["to"].lower() for it in r["items"] if it.get("to") and it.get("label", "to") in PAYS]


# ----------------------------------------------------------------------------- ABI words
def _word(args, i):
    w = args[32 * i:32 * i + 32]
    if len(w) != 32:
        raise ValueError("calldata too short")
    return int.from_bytes(w, "big")


def _addr(args, i):
    n = _word(args, i)
    if n >> 160:
        raise ValueError("not an address")
    return hx(n.to_bytes(20, "big"))


def unpack_multisend(data):
    """multiSend(bytes) calldata -> [(operation, to, value, data), ...]"""
    args = data[4:]
    off = _word(args, 0)
    n = int.from_bytes(args[off:off + 32], "big")
    p = args[off + 32:off + 32 + n]
    if len(p) != n:
        raise ValueError("batch too short")
    calls, i = [], 0
    while i < n:
        if i + 85 > n:
            raise ValueError("batch entry too short")
        op = p[i]
        to = hx(p[i + 1:i + 21])
        value = int.from_bytes(p[i + 21:i + 53], "big")
        ln = int.from_bytes(p[i + 53:i + 85], "big")
        if i + 85 + ln > n:
            raise ValueError("batch entry too short")
        calls.append((op, to, value, p[i + 85:i + 85 + ln]))
        i += 85 + ln
    return calls


def calldata_digest(data):
    """ERC-8213's Calldata Digest: keccak256(uint256(length) || calldata)."""
    return keccak256(len(data).to_bytes(32, "big") + data)


# ----------------------------------------------------------------------------- one call
def _unknown(to, data, why=""):
    sel = hx(data[:4]) if len(data) >= 4 else hx(data)
    return {"title": "UNKNOWN CALL", "level": "red", "what": "Unknown call", "to": to, "label": "contract",
            "text": (why + " " if why else "") + DONT, "selector": sel, "size": len(data), "contract": to,
            "digest": hx(calldata_digest(data))}


def _self_call(sel, args, ctx):
    """The Safe calling itself: its own settings. Every one of these is red."""
    if sel == "0d582f13":
        owner, t = _addr(args, 0), _word(args, 1)
        return {"title": "ADD OWNER", "level": "red", "what": "Add owner", "to": owner, "label": "new owner",
                "text": "Adds this address as an owner, with a vote on everything the Safe does. Approvals needed becomes %d." % t}
    if sel == "f8dc5dd9":
        owner, t = _addr(args, 1), _word(args, 2)
        return {"title": "REMOVE OWNER", "level": "red", "what": "Remove owner", "to": owner, "label": "owner",
                "text": "Removes this owner. Approvals needed becomes %d." % t}
    if sel == "e318b52b":
        old, new = _addr(args, 1), _addr(args, 2)
        return {"title": "SWAP OWNER", "level": "red", "what": "Replace owner", "to": new, "label": "new owner",
                "frm": old, "frm_label": "replaces",
                "text": "Removes one owner and puts the address below in its place, with the same vote."}
    if sel == "694e80c3":
        t = _word(args, 0)
        return {"title": "THRESHOLD", "level": "red", "what": "Approvals needed: %d" % t, "amount": "%d NEEDED" % t,
                "text": "Changes how many owners must approve every transaction from now on, to %d." % t}
    if sel == "610b5925":
        return {"title": "ADD MODULE", "level": "red", "what": "Add module", "to": _addr(args, 0), "label": "module",
                "text": "This contract will be able to move funds and change owners WITHOUT any owner approval."}
    if sel == "e009cfde":
        return {"title": "REMOVE MODULE", "level": "red", "what": "Remove module", "to": _addr(args, 1), "label": "module",
                "text": "Turns off this module; it can no longer act for the Safe."}
    if sel == "e19a9dd9":
        g = _addr(args, 0)
        if g == ZERO:
            return {"title": "REMOVE GUARD", "level": "red", "what": "Remove guard",
                    "text": "Turns off the transaction guard; nothing checks transactions after this."}
        return {"title": "SET GUARD", "level": "red", "what": "Set guard", "to": g, "label": "guard",
                "text": "This contract will check, and can block, every future transaction. A broken guard can lock the Safe for good."}
    if sel == "f08a0323":
        return {"title": "FALLBACK", "level": "red", "what": "Set fallback handler", "to": _addr(args, 0), "label": "handler",
                "text": "This contract answers calls the Safe does not know itself, including checks of messages the Safe has signed."}
    return None


def _token_call(sel, to, args, ctx):
    tok = ctx["tokens"].get(to)
    sym, dec = (tok[0], tok[1]) if tok else ("TOKEN", 0)
    note = "" if tok else " This token is not in the console's list, so the amount is in raw units."
    if sel == "a9059cbb":
        dest, amt = _addr(args, 0), _word(args, 1)
        return {"title": "SEND " + sym, "level": "ok" if tok else "warn", "what": "Send %s %s" % (units(amt, dec), sym),
                "amount": "%s %s" % (units(amt, dec), sym), "to": dest, "text": ("Token " + to + "." + note) if not tok else ""}
    if sel == "095ea7b3":
        sp, amt = _addr(args, 0), _word(args, 1)
        if amt >= UNLIMITED:
            return {"title": "APPROVE " + sym, "level": "red", "what": "Approve UNLIMITED " + sym, "amount": "UNLIMITED " + sym,
                    "to": sp, "label": "spender", "text": "The address below can take every %s this Safe holds, now and later, until someone revokes it.%s" % (sym, note)}
        return {"title": "APPROVE " + sym, "level": "ok" if tok else "warn", "what": "Approve %s %s" % (units(amt, dec), sym),
                "amount": "%s %s" % (units(amt, dec), sym), "to": sp, "label": "spender",
                "text": "The address below may take up to this much from the Safe." + note}
    if sel == "23b872dd":
        src, dest, amt = _addr(args, 0), _addr(args, 1), _word(args, 2)
        return {"title": "MOVE " + sym, "level": "ok" if tok else "warn", "what": "Move %s %s" % (units(amt, dec), sym),
                "amount": "%s %s" % (units(amt, dec), sym), "to": dest, "frm": src, "frm_label": "from",
                "text": "Moves tokens out of another address that approved this Safe." + note}
    return None


# ----------------------------------------------------------------------------- validators
# A Safe that is a validator's withdrawal address (credentials 0x01 or 0x02 naming it) manages the
# validator by calling the consensus layer's contracts (cfg "system"). Their calldata has no ABI:
#   withdraw (EIP-7002):    pubkey (48) || amount in Gwei (8, big-endian); amount 0 is a full exit
#   consolidate (EIP-7251): source pubkey (48) || target pubkey (48); the same key twice switches
#                           that validator to compounding (0x02) credentials
# and the value sent is the fee, burned, never refunded when overpaid. A deposit is the deposit
# contract's deposit(pubkey, withdrawal_credentials, signature, deposit_data_root): the value is
# the stake, and the credentials say who can ever withdraw it.
GWEI = 10 ** 9


def vname(ctx, pk):
    """(label, index) of a pinned validator, or None."""
    return ctx.get("validators", {}).get(pk.lower())


def wei(n):
    return "%d wei" % n if 0 < n < GWEI else units(n, 18) + " ETH"


def _fee(it, value, ctx):
    it["fee"] = value
    if value > ctx.get("feeWarn", 10 ** 16):
        it["level"] = "red" if it["level"] == "red" else "warn"
        it["text"] = "The fee is far above the usual 1 wei, and what is overpaid is burned."
    return it


def _not_yours(ctx, *pks):
    return [pk for pk in pks if not vname(ctx, pk)]


def _dyn(args, i):
    off = _word(args, i)
    n = int.from_bytes(args[off:off + 32], "big")
    b = args[off + 32:off + 32 + n]
    if off + 32 > len(args) or len(b) != n:
        raise ValueError("calldata too short")
    return b


def _validator_call(kind, to, value, data, ctx):
    """One call to a consensus-layer contract -> item."""
    base = {"contract": to, "to": to, "label": "contract"}
    if kind == "withdraw":
        if len(data) != 56:
            return dict(base, title="BAD REQUEST", level="red", what="Malformed withdrawal request",
                        text="A withdrawal request is exactly 56 bytes; this one is %d. It would fail or do something else. %s" % (len(data), DONT))
        pk, amt = hx(data[:48]), int.from_bytes(data[48:], "big")
        if amt == 0:
            it = dict(base, title="EXIT VALIDATOR", level="red", what="Exit validator", amount="FULL EXIT", keys=[("validator", pk)],
                      text="Stops it for good and pays out its whole balance. It can't be undone.")
        else:
            it = dict(base, title="WITHDRAW", level="ok", what="Withdraw %s ETH" % units(amt * GWEI, 18),
                      amount="%s ETH" % units(amt * GWEI, 18), keys=[("validator", pk)],
                      text="Pays this much out to the withdrawal address. The validator keeps running.")
    elif kind == "consolidate":
        if len(data) != 96:
            return dict(base, title="BAD REQUEST", level="red", what="Malformed consolidation",
                        text="A consolidation request is exactly 96 bytes; this one is %d. %s" % (len(data), DONT))
        src, dst = hx(data[:48]), hx(data[48:])
        if src == dst:
            it = dict(base, title="COMPOUNDING", level="warn", what="Switch to compounding", amount="0x01 to 0x02",
                      keys=[("validator", src)],
                      text="Rewards stay on the validator, up to 2,048 ETH, not paid out. No way back.")
        else:
            it = dict(base, title="CONSOLIDATE", level="red", what="Consolidate validators", keys=[("from", src), ("into", dst)],
                      text="Merges the first into the second and exits the first. The second's owner gets everything.")
    else:
        if data[:4] != b"\x22\x89\x51\x18":
            return None
        args = data[4:]
        pk, wc, sig = _dyn(args, 0), _dyn(args, 1), _dyn(args, 2)
        if len(pk) != 48 or len(wc) != 32 or len(sig) != 96:
            raise ValueError("deposit field sizes")
        pk = hx(pk)
        eth = units(value, 18)
        it = dict(base, title="DEPOSIT", level="ok", what="Deposit %s ETH" % eth, amount="%s ETH" % eth, keys=[("validator", pk)],
                  creds=hx(wc))
        if wc[0] in (1, 2) and wc[1:12] == bytes(11) and hx(wc[12:]) == ctx["safe"]:
            it.update(wto=ctx["safe"], text="0x%02x credentials. A validator that already exists keeps its own credentials." % wc[0])
        elif wc[0] in (1, 2) and wc[1:12] == bytes(11):
            it.update(level="red", wto=hx(wc[12:]),
                      text="NOT this Safe: whoever controls that address gets the stake and its rewards.")
        else:
            it.update(level="red", text="Withdrawal credentials of type 0x%02x: not an address, so not this Safe. The stake would be controlled by another key." % wc[0])
        return it       # the value is the stake, not a fee
    if _not_yours(ctx, *[k for _, k in it["keys"]]) and it["level"] == "ok":
        it["level"] = "warn"            # the page says which one is not in the list
    return _fee(it, value, ctx)


def _call(to, value, data, ctx):
    """One plain CALL -> [item]"""
    to = to.lower()
    kind = ctx.get("system", {}).get(to)
    if kind:
        try:
            it = _validator_call(kind, to, value, data, ctx)
        except ValueError as e:
            return [_unknown(to, data, "Could not read it (%s)." % e)]
        if it:
            return [it]
    if not data:
        if to == ctx["safe"] and value == 0:
            return [{"title": "REJECTION", "level": "ok", "what": "On-chain rejection",
                     "text": "Does nothing. Once executed it uses up this transaction number, cancelling every other transaction waiting on it."}]
        if value == 0:
            return [{"title": "EMPTY CALL", "level": "warn", "what": "Empty call", "to": to, "label": "address",
                     "text": "Sends nothing and calls nothing, unless the address is a contract."}]
        return [{"title": "SEND ETH", "level": "ok", "what": "Send %s ETH" % units(value, 18),
                 "amount": units(value, 18) + " ETH", "to": to}]
    if len(data) < 4:
        return [_unknown(to, data)]
    sel, args = hexlify(data[:4]).decode(), data[4:]
    try:
        it = _self_call(sel, args, ctx) if to == ctx["safe"] else _token_call(sel, to, args, ctx)
    except ValueError as e:
        return [_unknown(to, data, "Could not read it (%s)." % e)]
    if it is None:
        k = ctx["contracts"].get(to)
        call = k[2].get(sel) if k else None
        if not call:
            return [_unknown(to, data)]
        it = {"title": "CONTRACT CALL", "level": "warn", "what": call[1], "to": to, "label": "contract",
              "text": "Known contract, but this call isn't decoded here. Confirm what it does with the proposer.",
              "selector": hx(data[:4]), "size": len(data), "digest": hx(calldata_digest(data))}
    it["contract"] = to
    if value:
        it["text"] = (it.get("text", "") + " Also sends %s ETH with the call." % units(value, 18)).strip()
        if it["level"] == "ok":
            it["level"] = "warn"
    return [it]


# ----------------------------------------------------------------------------- the transaction
def _gas(tx, ctx):
    gp = int(tx.get("gasPrice") or 0)
    token = (tx.get("gasToken") or ZERO).lower()
    rr = (tx.get("refundReceiver") or ZERO).lower()
    base, stg = int(tx.get("baseGas") or 0), int(tx.get("safeTxGas") or 0)
    if gp:
        if token == ZERO:
            price = units(gp, 18) + " ETH"
        elif token in ctx["tokens"]:
            sym, dec = ctx["tokens"][token]
            price = "%s %s" % (units(gp, dec), sym)
        else:
            price = "%d raw units of the token %s" % (gp, token)
        return {"title": "GAS REFUND", "level": "red", "what": "Pays a gas refund",
                "to": rr if rr != ZERO else None, "label": "paid to",
                "text": "Whoever executes this is paid by the Safe: %s for every unit of gas used, plus %d more units. Paid to %s." % (
                    price, base, "the address below" if rr != ZERO else "whoever sends it")}
    if base or stg or token != ZERO or rr != ZERO:
        return {"title": "GAS FIELDS", "level": "warn", "what": "Unusual gas fields",
                "text": "safeTxGas %d, baseGas %d. No refund is paid because gasPrice is 0." % (stg, base)}
    return None


def worst(items):
    return LEVELS[max([LEVELS.index(i["level"]) for i in items] + [0])]


def review(tx, ctx):
    """The screen's view of a transaction. "refuse" is set when the console must not sign it at
    all, however long A is held: an operation the Safe does not have, or a delegatecall anywhere
    except to a pinned batcher (cfg "batchers", for a multiSend) or a pinned delegate (cfg
    "delegates"). A delegatecall runs the target's code as the Safe itself, so an unpinned one could
    move everything and change the owners (the attack that emptied Bybit's Safe in 2025)."""
    op = int(tx["operation"])
    to = tx["to"].lower()
    value = int(tx["value"])
    data = _bytes(tx.get("data") or "0x")
    items = []
    refuse = ""
    if op not in (CALL, DELEGATECALL):
        refuse = "Operation %d is neither a call nor a delegatecall." % op
    elif op == DELEGATECALL and not (to in ctx["delegates"] or (to in ctx["batchers"] and data[:4] == b"\x8d\x80\xff\x0a")):
        refuse = "A delegatecall to a contract this console has not pinned. It would run that code as the Safe itself."
    if op == DELEGATECALL and to in ctx["batchers"] and data[:4] == b"\x8d\x80\xff\x0a":
        try:
            calls = unpack_multisend(data)
        except (ValueError, IndexError) as e:
            calls = None
            items.append(_unknown(to, data, "A batch that could not be read (%s)." % e))
        if calls is not None:
            for iop, ito, ival, idata in calls:
                if iop != CALL:
                    items.append({"title": "DELEGATECALL", "level": "red", "what": "Delegatecall inside a batch", "to": ito,
                                  "label": "contract", "text": AS_SAFE})
                    refuse = refuse or "A delegatecall inside the batch. It would run that code as the Safe itself."
                else:
                    items += _call(ito, ival, idata, ctx)
            summary = "Batch: %d action%s" % (len(calls), "" if len(calls) == 1 else "s")
        else:
            summary = "Unreadable batch"
    elif op == DELEGATECALL:
        items.append({"title": "DELEGATECALL", "level": "red", "what": "Delegatecall", "to": to, "label": "contract",
                      "text": AS_SAFE, "selector": hx(data[:4]), "size": len(data), "contract": to,
                      "digest": hx(calldata_digest(data))})
        summary = "Delegatecall"
    else:
        items += _call(to, value, data, ctx)
        summary = items[0]["what"]
    g = _gas(tx, ctx)
    if g:
        items.append(g)
    _recipients(items, ctx)
    # the contract the Safe calls first (a token, the batch helper, itself), for the header
    return {"summary": summary, "level": worst(items), "items": items, "contract": to if data else None,
            "refuse": refuse}
