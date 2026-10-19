# The bench half of a branded key (firmware/brand.py) on the virtual ATECC608, with a public test
# key: a factory-fresh 608A, 608B and 608C branded B1-B7 on quorum v3 (the attestation key made and
# sealed at B4a-B4b), then a key made after the data lock, sealed and attested (S1-S4), with a reboot
# after every step. The attestation bundle checks, and what must not attest. Then what must go wrong: a table one bit off, no
# arm, no ALLOW_LOCK, the data lock without the signature, a test-bench brand taken for a real one.
# The knob alone walks the screen to B3. Then key 0000 pinned: B5 by a swap, one chip on the bus at a
# time, a restart that doesn't sign twice, and the claim (claim.py, U1-U5) with its refusals and the
# dual image's route. Run by test-vectors/run-brand.mjs.
import sys, os
import atecc_sim

failed = [0]


def check(ok, what):
    print(("pass  " if ok else "FAIL  ") + what)
    if not ok:
        failed[0] += 1


def secrets(lock=True, genkey=True):
    with open("secrets.py", "w") as f:
        f.write('WIFI_SSID = "emulator"\nWIFI_PASS = ""\nHOSTNAME = "emu"\nALLOW_LOCK = %s\nALLOW_GENKEY = %s\nBRAND_SEQ = 42\n' % (lock, genkey))
    try:
        os.remove("build.py")
    except OSError:
        pass
    for m in ("secrets", "build", "image", "signer", "atecc", "chipcfg", "provision", "brand", "claim"):
        sys.modules.pop(m, None)


def fresh_chip(rev="608a"):
    atecc_sim.wipe(rev)
    for f in os.listdir():
        if f.startswith("snapshot-") or f.startswith("brand-pending-"):
            os.remove(f)


def ceremony():
    import signer, brand
    return brand.Ceremony(signer.ChipSigner()), brand


def run(c, step, arm=True):
    import signer
    if arm:
        signer.arm()
    else:
        signer.disarm()
    got = c.step()
    ok, checks, msg = c.run(step)
    return got, ok, [l for l, k in checks if not k], msg


def carry(c, c2):
    """What a session knows that the chip can't say yet (OTP and slot 8 are unreadable before B6)."""
    c2.branded, c2.signed, c2.summary, c2.checked, c2.tested, c2.attested = c.branded, c.signed, c.summary, c.checked, c.tested, c.attested


def walk(rev):
    secrets()
    fresh_chip(rev)
    c, B = ceremony()
    sim = atecc_sim.chip()
    for want in ("B1", "B2", "B3", "B4", "B4a", "B4b", "B5", "B6", "B7", "S1", "S2", "S3", "S4", "S5"):
        got, ok, bad, msg = run(c, want)
        if want == "B7":
            check(sim.counters[0] == 0, "%s B7: counter 0 still 0, the empty slot 0 told by KeyValid, never read" % rev)
        check(got == want and ok, "%s %s: %s%s" % (rev, want, B.TITLES[want], "" if ok and got == want else " (step %s, %s, %s)" % (got, bad, msg)))
        c2, _ = ceremony()              # a reboot after every step
        carry(c, c2)
        check(c2.step() == c.step(), "%s after %s, a fresh look at the chip resumes at %s" % (rev, want, c2.step()))
    import chipcfg
    cfg = bytes(sim.cfg)
    check(chipcfg.identify(cfg) == "quorum-v3" and cfg[86] == 0 and cfg[87] == 0 and cfg[88] == 0xFC,
          "%s: quorum v3, locked 00 00, slots 0 and 1 sealed" % rev)
    c3, _ = ceremony()
    check(c3.branded == bytes(sim.otp), "%s: after a reboot the bench reads the record from the locked OTP (the screen's number)" % rev)
    rec = chipcfg.brand_decode(bytes(sim.otp))
    check(rec is not None and rec["version"] == 3 and rec["bench"] == chipcfg.TEST_BENCH and rec["seq"] == 42
          and rec["serial"] == c.serial and rec["zeros"], "%s: the OTP holds a v3 test-bench record, number 42, this serial" % rev)
    import p256
    x, y = p256.pubkey(sim.keys[1])
    slot8 = b"".join(bytes(c.chip.read_data(8, b)) for b in range(13))
    check(slot8[224:288] == x.to_bytes(32, "big") + y.to_bytes(32, "big") and slot8[288:] == bytes(128) and slot8[64:224] == bytes(160),
          "%s: slot 8 holds slot 1's public key at 224-287, zeros around it" % rev)
    check(rec is not None and rec["revision"] == {"608a": "00006002", "608b": "00006003", "608c": "00006005"}[rev],
          "%s: the record names this revision" % rev)
    return c


def case_full():
    walk("608a")
    walk("608b")
    walk("608c")


def case_brand_check():
    """brand_check: the test key passes only when pinned, and a test bench is never a brand."""
    import chipcfg
    c = walk("608a")
    B = sys.modules["brand"]
    otp = bytes(atecc_sim.chip().otp)
    rec = chipcfg.brand_decode(otp)
    rec["_raw"] = otp
    slot8 = b"".join(bytes(c.chip.read_data(8, b)) for b in range(13))
    _, qx, qy = B.test_key()
    pinned = {chipcfg.key_id(qx, qy).hex(): (qx, qy)}
    att = slot8[224:288]
    got = dict(chipcfg.brand_check(rec, slot8, c.serial, c.revision, c.cfg, pinned, att))
    check(got["signed by a pinned brand key"] and got["quorum v3, config CRC matches"] and not got["bench 0, no certificate"]
          and got["attestation key in slot 8"] and got["slot 1 sealed, its key the one in slot 8"],
          "the test key's signature verifies when pinned; the test bench still fails 'bench 0'")
    got = dict(chipcfg.brand_check(rec, slot8, c.serial, c.revision, c.cfg, {}, att))
    check(not got["signed by a pinned brand key"], "with no brand key pinned (the console today): the signature is refused")
    bad = bytearray(slot8)
    bad[5] ^= 1
    got = dict(chipcfg.brand_check(rec, bytes(bad), c.serial, c.revision, c.cfg, pinned, att))
    check(not got["signed by a pinned brand key"], "one bit off in slot 8: refused")
    bad = bytearray(slot8)
    bad[230] ^= 1
    got = dict(chipcfg.brand_check(rec, bytes(bad), c.serial, c.revision, c.cfg, pinned, att))
    check(not got["signed by a pinned brand key"] and not got["slot 1 sealed, its key the one in slot 8"],
          "one bit off in slot 8's attestation key: the brand signature fails, and it isn't slot 1's")
    import p256
    other = p256.pubkey(p256.rand_scalar())
    got = dict(chipcfg.brand_check(rec, slot8, c.serial, c.revision, c.cfg, pinned, other[0].to_bytes(32, "big") + other[1].to_bytes(32, "big")))
    check(got["signed by a pinned brand key"] and not got["slot 1 sealed, its key the one in slot 8"],
          "a copied brand on a chip whose slot 1 holds another key: refused")
    got = dict(chipcfg.brand_check(rec, slot8, "0123ffffffffffffff", c.revision, c.cfg, pinned, att))
    check(not got["serial matches the chip"], "a copied record on another serial: refused")
    v2 = bytearray(otp)
    v2[2] = 2
    check(chipcfg.brand_digest(bytes(v2)) != chipcfg.brand_digest(otp, att), "a v3 brand's digest is never a v2 one's")


def unhex(raw):
    """A bundle as claim.log_bundle wrote it, back to bytes."""
    b = {k: (v if k == "serial" else bytes.fromhex(v)) for k, v in raw.items() if k != "nonce"}
    b["nonce"] = {k: (v if k == "mode" else bytes.fromhex(v)) for k, v in raw["nonce"].items()}
    return b


def case_attest():
    """S4's bundle, checked from its public bytes alone as the app or a relay would, and what must not
    attest: another key, another serial, another brand key, a key not yet sealed."""
    import json, chipcfg, p256, claim
    c = walk("608c")
    B = sys.modules["brand"]
    lines = [l for l in open(B.LOG).read().split("\n") if l.startswith("  bundle ")]
    check(len(lines) > 0, "S4 put the bundle in brand-log.txt")
    bundle = unhex(json.loads(lines[-1][len("  bundle "):]))
    keys = c.keys()
    got = chipcfg.attest_check(bundle, keys)
    check(all(k for _, k in got) and bundle["nonce"]["mode"] == "input", "the bundle checks from its public bytes alone (%s)" % got)
    x, y = p256.pubkey(p256.rand_scalar())
    bad = dict(bundle, pub=x.to_bytes(32, "big") + y.to_bytes(32, "big"))
    check(not dict(chipcfg.attest_check(bad, keys))["slot 0's key attested, sealed, by slot 1"],
          "a copied brand and attestation with a software key in place of slot 0's: refused")
    bad = dict(bundle, serial="0123ffffffffffffff")
    got = dict(chipcfg.attest_check(bad, keys))
    check(not got["the serial is the record's"] and not got["slot 0's key attested, sealed, by slot 1"], "another serial: refused")
    check(not dict(chipcfg.attest_check(bundle, {}))["the brand signs the attestation key"], "no brand key to take: refused")
    nonce, pub, sig = c.chip.genkey_attest(0, 1, None, bytes(range(20)))
    got = chipcfg.attest_check(dict(bundle, nonce=nonce, pub=pub, sig=sig), keys)
    check(nonce["mode"] == "random" and all(k for _, k in got), "random-mode Nonce: the bundle checks too")
    # a key attested before its seal doesn't pass as sealed
    secrets()
    fresh_chip("608c")
    c, B = ceremony()
    for st in ("B1", "B2", "B3", "B4", "B4a", "B4b", "B5", "B6", "B7", "S1", "S2"):
        run(c, st)
    ok, checks, msg = claim.attest(c, c.keys(), B.LOG)
    check(not ok and not dict(checks)["slot 0's key attested, sealed, by slot 1"], "slot 0 not sealed yet: the attestation refuses it")


def case_refusals():
    secrets()
    fresh_chip()
    c, B = ceremony()
    run(c, "B1")
    run(c, "B2")
    sim = atecc_sim.chip()
    sim.cfg[36] ^= 0x80                 # slot 8 secret again: not quorum v3
    got, ok, bad, msg = run(c, "B3")
    check(not ok and sim.cfg[87] == 0x55, "the table one bit off (quorum v1's slot 8): the CRC lock is refused")
    sim.cfg[36] ^= 0x80
    sim.cfg[22] |= 0x01                 # slot 1 with external Sign: an arbitrary-digest signer
    got, ok, bad, msg = run(c, "B3")
    check(not ok and sim.cfg[87] == 0x55, "slot 1 one bit off (external Sign on): the CRC lock is refused")
    sim.cfg[22] &= 0xFE
    got, ok, bad, msg = run(c, "B3", arm=False)
    check(not ok and "armed" in msg and sim.cfg[87] == 0x55, "B3 without the arm: refused")
    secrets(lock=False)
    c, B = ceremony()
    got, ok, bad, msg = run(c, "B3")
    check(not ok and "ALLOW_LOCK" in msg, "B3 with ALLOW_LOCK False: refused")
    secrets()
    c, B = ceremony()
    run(c, "B3")
    run(c, "B4")
    import chipcfg
    c.signed = B.slot8_bytes(bytes(64), bytes(64))
    slots = chipcfg.zero_slots(B.TABLE)
    slots[8] = B.slot8_bytes(b"\x01" * 64, bytes(64))
    c.summary = chipcfg.data_summary(B.TABLE, slots, c.branded)
    got, ok, bad, msg = run(c, "B6")
    check(not ok and sim.cfg[86] == 0x55, "the data lock with a CRC for a signature that isn't in slot 8: refused, still open")
    c.signed = None
    got, ok, bad, msg = run(c, "B5")
    check(not ok and "nothing signed" in msg, "B5 before the attestation key: nothing signed")
    got, ok, bad, msg = run(c, "B4a", arm=False)
    check(got == "B4a" and not ok and 1 not in sim.keys, "B4a without the arm: refused, no key in slot 1")
    run(c, "B4a")
    first = sim.keys[1]
    c2, B = ceremony()
    check(c2.step() == "B4b", "a restart after B4a: B4b next (brand-pending holds slot 1's key)")
    sim.keys[1] = atecc_sim.chip().keys[1] + 1          # slot 1 isn't the key B4a made
    c2, B = ceremony()
    check(c2.step() == "B4a", "slot 1 not the key brand-pending holds: B4a again, not the seal")
    got, ok, bad, msg = run(c, "B4b")
    check(not ok and sim.cfg[88] == 0xFF, "B4b over a key that isn't B4a's: refused, slot 1 not locked")
    sim.keys[1] = first
    got, ok, bad, msg = run(c, "B4b", arm=False)
    check(not ok and sim.cfg[88] == 0xFF, "B4b without the arm: refused")
    got, ok, bad, msg = run(c, "B4b")
    check(ok and sim.cfg[88] == 0xFD and sim.keys[1] == first, "B4b: slot 1 sealed, GenKey and external Sign on it refused")
    run(c, "B5")
    got, ok, bad, msg = run(c, "B6", arm=False)
    check(not ok and sim.cfg[86] == 0x55, "B6 without the arm: refused")
    got, ok, bad, msg = run(c, "B6")
    check(ok, "after B5 the same lock goes through")
    import atecc
    try:
        c.chip.write_data(8, 0, bytes(32))
        rewritten = True
    except atecc.AteccError:
        rewritten = False
    check(not rewritten, "slot 8 after the data lock: the brand signature can't be written again")
    secrets(genkey=False)
    c, B = ceremony()
    run(c, "B7")
    got, ok, bad, msg = run(c, "S1")
    check(got == "S1" and not ok and "ALLOW_GENKEY" in msg, "S1 with ALLOW_GENKEY False: refused, no key made")
    atecc_sim.provision_v1()
    c, B = ceremony()
    check(c.step() == "other", "a sealed quorum v1 chip: this bench stops at 'not for this bench'")


def case_console():
    """The console image on a branded spare: pinned like any chip, it signs, and a sealed quorum v2
    chip boots the console in the dual image, never the ceremony."""
    walk("608a")
    sys.path.insert(0, "/")
    import console_test as T
    import quorum_cfg, webauthn, p256
    sim = atecc_sim.chip()
    x, y = p256.pubkey(sim.keys[0])
    owner = webauthn.owner_address("0x%064x" % x, "0x%064x" % y, quorum_cfg.CFG["signer"])
    pin = {"serial": T.SERIAL, "slot": 0, "owner": owner, "locked": True}
    Q = T.fresh(expect=pin)
    check(Q.state == "home" and Q.pin_ok, "the console accepts the branded spare it is pinned to")
    before = sim.counters[0]
    T.serve(Q, [T.tx(Q, 0)])
    check(T.sign(Q, Q.queue[0], 2100) and sim.counters[0] == before + 1, "it signs a Safe transaction: one use")
    import signer
    check(not signer.ChipSigner().needs_ceremony(), "a sealed quorum v2 chip needs no ceremony: dual boots the console")


class FakeKnob:
    def __init__(self):
        self.down = False

    def held(self, k):
        return k == "press" and self.down


def case_knob():
    """The knob alone (build1) on brand_ui's screen: press for B1 and B2; B3 takes a 3 s hold to arm,
    then another to lock."""
    import time
    import lcd as L
    secrets()
    fresh_chip()
    c, B = ceremony()
    P = B.P                             # the provision module brand.py runs on, after secrets() reloaded it
    import brand_ui
    k = FakeKnob()
    L.KNOB = True
    try:
        ui = brand_ui.UI(None, k, None, "dark", c)     # the bench's own screen, on provision.UI's handling
        ui.busy = lambda st: None
        for st in ("B1", "B2"):
            ui.tick(["press"])
            check(ui.result and ui.result[0] == st and ui.result[1], "knob: a press does %s" % st)
            ui.tick(["press"])          # dismiss
        check(c.step() == "B3", "knob: B3 next")
        ui.tick([])                     # the knob let go after the dismiss
        k.down = True
        ui.tick([])
        ui.hold = time.ticks_add(time.ticks_ms(), -P.HOLD_MS - 1)
        ui.tick([])
        import signer
        check(signer.armed() > 0 and atecc_sim.chip().cfg[87] == 0x55, "knob: the first 3 s hold arms, nothing locked")
        ui.tick([])                     # still held: no second hold until it is let go
        k.down = False
        ui.tick([])
        k.down = True
        ui.tick([])
        ui.hold = time.ticks_add(time.ticks_ms(), -P.HOLD_MS - 1)
        ui.tick([])
        check(ui.result and ui.result[0] == "B3" and ui.result[1] and atecc_sim.chip().cfg[87] == 0x00,
              "knob: let go, hold 3 s again: B3 locks the config")
    finally:
        L.KNOB = False


def serial_of(chip):
    return "".join("%02x" % b for b in chip.cfg[0:4] + chip.cfg[8:13])


def make_key0000():
    """A sealed quorum v1 chip on its own serial, pinned as the brand key in quorum_cfg. -> the sim chip."""
    import p256, chipcfg, quorum_cfg
    atecc_sim._chip = None
    atecc_sim.wipe("608c")
    atecc_sim.provision_v1()
    k0 = atecc_sim.chip()
    k0.cfg[8:13] = b"\x00\x00\x00\x00\xee"
    qx, qy = p256.pubkey(k0.keys[0])
    quorum_cfg.CFG["brandKeys"] = {chipcfg.key_id(qx, qy).hex(): {"qx": "%064x" % qx, "qy": "%064x" % qy, "serial": serial_of(k0)}}
    return k0


def plug(chip):
    """One chip on the bus: this one (None: nothing)."""
    atecc_sim.present = chip is not None
    if chip is not None:
        atecc_sim._chip = chip


def new_chip(rev="608c", tail=b"\xe1\xe1\xe1\xe1\xee"):
    atecc_sim._chip = None
    fresh_chip(rev)
    c = atecc_sim.chip()
    c.cfg[8:13] = tail
    return c


def brand_with_key0000(k0, seq=7, swap=None):
    """A fresh 608C through B1-B7 with key 0000 pinned; B5 swaps chips through c.say. -> (ceremony, sim chip, say log)."""
    secrets()
    import brand
    brand.SWAP_S = 5
    mine = new_chip()
    c, B = ceremony()
    seen = []

    def say(what, serial=None):
        seen.append(what)
        if swap:
            swap(what, mine)
        elif what == "key0000":
            plug(None)
            plug(k0)
        elif what == "back":
            plug(mine)
    c.say = say
    for want in ("B1", "B2", "B3", "B4", "B4a", "B4b", "B5", "B6", "B7"):
        got, ok, bad, msg = run(c, want)
        check(got == want and ok, "key 0000 pinned, %s: %s%s" % (want, B.TITLES[want], "" if ok and got == want else " (step %s, %s, %s)" % (got, bad, msg)))
        if not ok:
            break
    return c, mine, seen


def case_key0000():
    """Key 0000 pinned: B5 asks for this chip out and key 0000 in, signs, asks for it back. The
    record says bench 0, the brand checks as a console will, and the chip ships with no key."""
    import chipcfg, quorum_cfg
    try:
        k0 = make_key0000()
        before = k0.counters[0]
        c, mine, seen = brand_with_key0000(k0)
        check(seen == ["key0000", "back"], "B5 asked for key 0000, then this chip back (%s)" % seen)
        check(k0.counters[0] == before + 1, "key 0000 signed once: its counter %d -> %d" % (before, k0.counters[0]))
        rec = chipcfg.brand_decode(bytes(mine.otp))
        check(rec["bench"] == 0 and chipcfg.brand_number(rec) == "0042" and rec["revision"] == "00006005",
              "the record: bench 0, number 0042, a 608C")
        check(mine.counters[0] == 0 and 0 not in mine.keys, "the branded chip: no key, counter 0 = 0")
        check(c.step() == "B7", "a real brand stops at B7: no S steps, the claim makes the key")

        # a wrong chip plugged in first, then key 0000; and this chip only once it is back
        k0b = k0
        other = new_chip("608a", b"\x77\x77\x77\x77\xee")

        def swap(what, mine):
            if what == "key0000":
                plug(other)
            elif what == "wrong":
                plug(k0b)
            elif what == "back":
                plug(mine)
        c, mine2, seen = brand_with_key0000(k0, swap=swap)
        check(seen == ["key0000", "wrong", "back"], "a chip that isn't key 0000: shown as the wrong one, then key 0000 signs (%s)" % seen)

        # nothing comes: B5 stops, nothing written
        secrets()
        import brand
        brand.SWAP_S = 1
        mine3 = new_chip()
        c, B = ceremony()
        c.say = lambda what, serial=None: plug(mine3) if what == "back" else None
        for st in ("B1", "B2", "B3", "B4", "B4a", "B4b"):
            run(c, st)
        got, ok, bad, msg = run(c, "B5")
        check(got == "B5" and not ok and "didn't come" in msg and bytes(mine3.data[8][:64]) == bytes(64) and c.step() == "B5",
              "key 0000 never plugged in: B5 stops, slot 8 still B4's zeros")

        # a restart after B4, and one after B5 signed: no new record, no second signature
        brand.SWAP_S = 5
        plug(mine3)
        c2, B = ceremony()
        check(c2.step() == "B5" and c2.branded == bytes(c.branded), "a restart after B4b: B5 next, the same record (brand-pending)")
        c2.say = lambda what, serial=None: (plug(k0) if what == "key0000" else plug(mine3) if what == "back" else None)
        n = k0.counters[0]
        run(c2, "B5")
        c3, B = ceremony()
        said = []
        c3.say = lambda what, serial=None: said.append(what)
        got, ok, bad, msg = run(c3, "B5")
        check(got == "B5" and ok and not said and k0.counters[0] == n + 1,
              "a restart after B5: written again from brand-pending, no swap, key 0000 signed once")
    finally:
        quorum_cfg.CFG["brandKeys"] = {}
        plug(atecc_sim.chip())


def claim_of():
    import signer, claim
    return claim.Ceremony(signer.ChipSigner())


def case_claim():
    """The claim on a branded 608C: U1-U5, then the refusals, each with nothing written."""
    import chipcfg, quorum_cfg, signer
    sys.path.insert(0, "/")
    import main_dual
    try:
        k0 = make_key0000()
        c, mine, seen = brand_with_key0000(k0)
        plug(mine)
        check(main_dual.which()[0] == "claim", "dual: a branded chip, locked 00/00, slot 0 not sealed -> the claim")
        cl = claim_of()
        for want in ("U1", "U2", "U3", "U4", "U5"):
            got, ok, bad, msg = run(cl, want)
            check(got == want and ok, "claim %s: %s%s" % (want, cl.TITLES[want], "" if ok and got == want else " (step %s, %s, %s)" % (got, bad, msg)))
        check(mine.cfg[88] == 0xFC and 0 in mine.keys, "claimed: a key in slot 0, sealed (and the bench's slot 1)")
        check("owner 0x" in msg, "U5 shows the owner address")
        check(main_dual.which()[0] == "console", "dual: a claimed chip goes to the console")
        check(claim_of().step() == "other", "a chip claimed before: refused, nothing to do")

        # a reboot in the middle: the key found at plug-in is made again
        c, mine, seen = brand_with_key0000(k0)
        plug(mine)
        cl = claim_of()
        run(cl, "U1")
        run(cl, "U2")
        first = mine.keys[0]
        cl = claim_of()
        got, ok, bad, msg = run(cl, "U1")
        check(ok and cl.step() == "U2", "after a reboot with an unsealed key: U1, then U2 again")
        run(cl, "U2")
        check(mine.keys[0] != first, "the key found at plug-in is replaced: only a key made this session is sealed")

        # refusals: nothing written
        c, mine, seen = brand_with_key0000(k0)
        plug(mine)
        mine.data[8][3] ^= 1
        cl = claim_of()
        got, ok, bad, msg = run(cl, "U1")
        check(not ok and "signed by a pinned brand key" in bad and cl.step() == "U1" and 0 not in mine.keys,
              "one bit off in slot 8: U1 refuses, no key")
        mine.data[8][3] ^= 1
        quorum_cfg.CFG["brandKeys"] = {}
        cl = claim_of()
        got, ok, bad, msg = run(cl, "U1")
        check(not ok and "signed by a pinned brand key" in bad and 0 not in mine.keys, "no brand key pinned: U1 refuses")
    finally:
        quorum_cfg.CFG["brandKeys"] = {}
        plug(atecc_sim.chip())
    walk("608c")                        # a test-bench spare, sealed by its S steps
    cl = claim_of()
    check(cl.step() == "other", "a sealed spare: not a key to claim")
    secrets()
    fresh_chip("608c")
    cl = claim_of()
    check(cl.step() == "other", "a factory chip: zones not locked, not a key to claim")
    # a spare branded with the test key, stopped at B7 (no key): U1 refuses a test bench
    secrets()
    fresh_chip("608c")
    c, B = ceremony()
    for st in ("B1", "B2", "B3", "B4", "B4a", "B4b", "B5", "B6", "B7"):
        run(c, st)
    cl = claim_of()
    got, ok, bad, msg = run(cl, "U1")
    check(got == "U1" and not ok and "bench 0, no certificate" in bad and cl.step() == "U1", "a test-key spare: U1 refuses it")
    check(main_dual.which()[0] == "claim", "(dual still routes it to the claim, which refuses it at U1)")


def main():
    for case in (case_full, case_brand_check, case_attest, case_refusals, case_knob, case_console, case_key0000, case_claim):
        try:
            case()
        except Exception as e:
            sys.print_exception(e)
            check(False, "%s raised %r" % (case.__name__, e))
    print("%d failed" % failed[0])
    return failed[0]
