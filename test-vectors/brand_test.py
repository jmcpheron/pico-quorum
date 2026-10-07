# The bench half of a branded key (firmware/brand.py) on the virtual ATECC608, with a public test
# key: a factory-fresh 608A and 608B branded B1-B7, then a key made after the data lock and sealed
# (S1-S3), with a reboot after every step. Then what must go wrong: a table one bit off, no arm, no
# ALLOW_LOCK, the data lock without the signature, a test-bench brand taken for a real one. Last, the
# knob alone walks the screen to B3. Run by test-vectors/run-brand.mjs.
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
    for m in ("secrets", "build", "image", "signer", "atecc", "chipcfg", "provision", "brand"):
        sys.modules.pop(m, None)


def fresh_chip(rev="608a"):
    atecc_sim.wipe(rev)
    for f in os.listdir():
        if f.startswith("snapshot-"):
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
    c2.branded, c2.signed, c2.summary, c2.checked, c2.tested = c.branded, c.signed, c.summary, c.checked, c.tested


def walk(rev):
    secrets()
    fresh_chip(rev)
    c, B = ceremony()
    sim = atecc_sim.chip()
    for want in ("B1", "B2", "B3", "B4", "B5", "B6", "B7", "S1", "S2", "S3", "S4"):
        got, ok, bad, msg = run(c, want)
        check(got == want and ok, "%s %s: %s%s" % (rev, want, B.TITLES[want], "" if ok and got == want else " (step %s, %s, %s)" % (got, bad, msg)))
        c2, _ = ceremony()              # a reboot after every step
        carry(c, c2)
        check(c2.step() == c.step(), "%s after %s, a fresh look at the chip resumes at %s" % (rev, want, c2.step()))
    import chipcfg
    cfg = bytes(sim.cfg)
    check(chipcfg.identify(cfg) == "quorum-v2" and cfg[86] == 0 and cfg[87] == 0 and cfg[88] == 0xFE,
          "%s: quorum v2, locked 00 00, slot 0 sealed" % rev)
    c3, _ = ceremony()
    check(c3.branded == bytes(sim.otp), "%s: after a reboot the bench reads the record from the locked OTP (the screen's number)" % rev)
    rec = chipcfg.brand_decode(bytes(sim.otp))
    check(rec is not None and rec["bench"] == chipcfg.TEST_BENCH and rec["seq"] == 42 and rec["serial"] == c.serial
          and rec["zeros"], "%s: the OTP holds the test-bench record, number 42, this serial" % rev)
    return c


def case_full():
    walk("608a")
    walk("608b")


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
    pinned = {B.key_id(qx, qy).hex(): (qx, qy)}
    got = dict(B.brand_check(rec, slot8, c.serial, c.revision, c.cfg, pinned))
    check(got["signed by a pinned brand key"] and got["config CRC matches"] and not got["bench 0, no certificate"],
          "the test key's signature verifies when pinned; the test bench still fails 'bench 0'")
    got = dict(B.brand_check(rec, slot8, c.serial, c.revision, c.cfg, {}))
    check(not got["signed by a pinned brand key"], "with no brand key pinned (the console today): the signature is refused")
    bad = bytearray(slot8)
    bad[5] ^= 1
    got = dict(B.brand_check(rec, bytes(bad), c.serial, c.revision, c.cfg, pinned))
    check(not got["signed by a pinned brand key"], "one bit off in slot 8: refused")
    got = dict(B.brand_check(rec, slot8, "0123ffffffffffffff", c.revision, c.cfg, pinned))
    check(not got["serial matches the chip"], "a copied record on another serial: refused")


def case_refusals():
    secrets()
    fresh_chip()
    c, B = ceremony()
    run(c, "B1")
    run(c, "B2")
    sim = atecc_sim.chip()
    sim.cfg[36] ^= 0x80                 # slot 8 secret again: quorum v1, not v2
    got, ok, bad, msg = run(c, "B3")
    check(not ok and sim.cfg[87] == 0x55, "the table one bit off (quorum v1's slot 8): the CRC lock is refused")
    sim.cfg[36] ^= 0x80
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
    c.signed = B.slot8_bytes(bytes(64))
    slots = chipcfg.zero_slots(B.TABLE)
    slots[8] = B.slot8_bytes(b"\x01" * 64)
    c.summary = chipcfg.data_summary(B.TABLE, slots, c.branded)
    got, ok, bad, msg = run(c, "B6")
    check(not ok and sim.cfg[86] == 0x55, "the data lock with a CRC for a signature that isn't in slot 8: refused, still open")
    c.signed = None
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


def main():
    for case in (case_full, case_brand_check, case_refusals, case_knob):
        try:
            case()
        except Exception as e:
            sys.print_exception(e)
            check(False, "%s raised %r" % (case.__name__, e))
    print("%d failed" % failed[0])
    return failed[0]
