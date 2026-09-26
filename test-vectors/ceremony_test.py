# The quorum v1 ceremony (firmware/provision.py) on the virtual ATECC608, from a factory-fresh chip
# to a sealed one, then the console signing with it. Also what must go wrong: a table that is not
# the reviewed one, a data zone that is not what the CRC says, a step without the arm, a locked
# key asked to change, a chip at its counter's cap. Run by test-vectors/run-ceremony.mjs.
import sys, os, json, hashlib
import atecc_sim
import p256

failed = [0]


def check(ok, what):
    print(("pass  " if ok else "FAIL  ") + what)
    if not ok:
        failed[0] += 1


def secrets(lock=True, genkey=True):
    with open("secrets.py", "w") as f:
        f.write('WIFI_SSID = "emulator"\nWIFI_PASS = ""\nHOSTNAME = "emu"\nALLOW_LOCK = %s\nALLOW_GENKEY = %s\n' % (lock, genkey))
    try:
        os.remove("build.py")
    except OSError:
        pass
    for m in ("secrets", "build", "image", "signer", "atecc", "chipcfg", "provision"):
        sys.modules.pop(m, None)


def fresh_chip(rev="608a"):
    atecc_sim.wipe(rev)
    for f in os.listdir():
        if f.startswith("snapshot-"):
            os.remove(f)


def ceremony():
    import signer, provision
    s = signer.ChipSigner()
    return provision.Ceremony(s), signer, provision


def run(c, step, arm=True):
    import signer
    if arm:
        signer.arm()
    else:
        signer.disarm()
    got = c.step()
    ok, checks, msg = c.run(step)
    bad = [l for l, k in checks if not k]
    return got, ok, bad, msg


def walk(rev):
    secrets()
    fresh_chip(rev)
    c, S, P = ceremony()
    sim = atecc_sim.chip()
    order = []
    for want in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10"):
        got, ok, bad, msg = run(c, want)
        order.append(got)
        check(got == want and ok, "%s %s: %s%s" % (rev, want, P.TITLES[want], "" if ok and got == want else " (step %s, %s, %s)" % (got, bad, msg)))
        c2, _, _ = ceremony()           # a reboot after every step: the chip alone says where we are
        c2.owner_seen, c2.record, c2.summary, c2.tested = c.owner_seen, c.record, c.summary, c.tested
        nxt = c2.step()
        check(nxt == c.step(), "%s after %s, a fresh look at the chip resumes at %s" % (rev, want, nxt))
    cfg = bytes(sim.cfg)
    check(cfg[86] == 0 and cfg[87] == 0 and cfg[88] == 0xFE and cfg[89] == 0xFF, "%s: locks 00 00, slot 0 sealed (FE FF)" % rev)
    import chipcfg
    check(chipcfg.identify(cfg) == "quorum-v1", "%s: the chip holds quorum v1" % rev)
    rec = chipcfg.record_decode(bytes(sim.otp))
    x, y = p256.pubkey(sim.keys[0])
    check(chipcfg.record_matches(rec, x, y) and rec["owner"] == c.owner(), "%s: the OTP record names this key and its owner" % rev)
    import chips
    e = chips.load().get(c.serial) or {}
    check(e.get("profile") == "quorum-v1" and e.get("owner") == c.owner(), "%s: chips.json has it as quorum v1, with its owner" % rev)
    import webauthn, quorum_cfg
    check(c.owner() == webauthn.owner_address("0x%064x" % x, "0x%064x" % y, quorum_cfg.CFG["signer"]),
          "%s: the owner shown at C7 is the key's passkey signer" % rev)
    check(sim.counters[0] == 5, "%s: counter 0 = %d: C5's two test signatures, C6's before and after the seal, C9's" % (rev, sim.counters[0]))
    return c


def case_full():
    walk("608a")
    walk("608b")


def case_seal_gate():
    """The seal (C6) only after C5 passed, in this session."""
    secrets()
    fresh_chip()
    c, S, P = ceremony()
    for st in ("C1", "C2", "C3", "C4"):
        run(c, st)
    real = P.p256.verify
    P.p256.verify = lambda *a: False            # a key whose signatures do not verify
    try:
        got, ok, bad, msg = run(c, "C5")
    finally:
        P.p256.verify = real
    check(got == "C5" and not ok and c.step() == "C5", "C5 fails: the next step is C5 again, never the seal")
    got, ok, bad, msg = run(c, "C6")
    check(not ok and not c.slot0["locked"], "C6 asked for anyway: refused, slot 0 not sealed")
    run(c, "C5")
    c2, _, _ = ceremony()
    check(c.step() == "C6" and c2.step() == "C5", "C5 passes: C6 next; after a reboot, C5 again first")


def case_refusals():
    import chipcfg
    secrets()
    fresh_chip()
    c, S, P = ceremony()
    run(c, "C1")
    run(c, "C2")
    sim = atecc_sim.chip()
    sim.cfg[30] ^= 0x01                 # one bit of slot 5's SlotConfig, after the readback
    got, ok, bad, msg = run(c, "C3")
    check(not ok and sim.cfg[87] == 0x55, "a table one bit off the reviewed one: the CRC lock is refused, nothing is locked")
    sim.cfg[30] ^= 0x01
    got, ok, bad, msg = run(c, "C3", arm=False)
    check(not ok and "armed" in msg and sim.cfg[87] == 0x55, "C3 without the B+Y arm: refused")
    secrets(lock=False)
    c, S, P = ceremony()
    got, ok, bad, msg = run(c, "C3")
    check(not ok and "ALLOW_LOCK" in msg, "C3 with ALLOW_LOCK False: refused")
    secrets()
    c, S, P = ceremony()
    for st in ("C3", "C4", "C5", "C6", "C7"):
        run(c, st)
    check(c.slot0["locked"], "(the setup: slot 0 sealed)")
    x, y = c.key
    rec = chipcfg.record_encode(c.chip.serial(), 0, x, y, c.owner(), 0, "", 0)
    c.record, c.summary = rec, chipcfg.data_summary(chipcfg.QUORUM_V1, chipcfg.zero_slots(), rec)   # C8 skipped
    got, ok, bad, msg = run(c, "C9")
    check(not ok and sim.cfg[86] == 0x55, "the data lock without the zero fill: refused by the CRC, the zone stays open")
    import atecc
    try:
        c.chip.genkey_new(0)
        replaced = True
    except atecc.AteccError:
        replaced = False
    check(not replaced, "GenKey on the sealed slot 0: refused")
    run(c, "C8")
    got, ok, bad, msg = run(c, "C9")
    check(ok, "after C8 the same lock goes through")
    sim.counters[0] = atecc_sim.COUNTER_MAX
    try:
        c.chip.sign(bytes(32), 0)
        signed = True
    except atecc.AteccError:
        signed = False
    check(not signed, "at counter 0's cap the key signs no more")
    atecc_sim.provision(0)              # chip #1's table
    c, S, P = ceremony()
    check(c.step() == "other", "a chip with another locked table: the ceremony stops at 'not a fresh chip'")


def case_console():
    """The console image on a quorum v1 chip: pinned, and every signature counted."""
    atecc_sim.provision_v1()
    sys.path.insert(0, "/")
    import console_test as T
    import quorum_cfg, webauthn
    sim = atecc_sim.chip()
    x, y = p256.pubkey(sim.keys[0])
    owner = webauthn.owner_address("0x%064x" % x, "0x%064x" % y, quorum_cfg.CFG["signer"])
    Q = T.fresh(expect={"serial": T.SERIAL, "slot": 0, "owner": owner, "locked": True})
    check(Q.state == "home" and Q.pin_ok, "the console accepts the quorum v1 chip it is pinned to")
    check(Q.row["limitedUse"] and not Q.row["intSign"] and Q.counter == 0, "slot 0 reads as LimitedUse, external sign only, counter 0")
    T.serve(Q, [T.tx(Q, 0)])
    check(T.sign(Q, Q.queue[0], 2100) and Q.counter == 1, "it signs with it, and the count goes to 1")


def case_ui():
    """Every step's screen draws (the ceremony image's own framebuf text)."""
    import splash, provision
    secrets()
    fresh_chip()
    c, S, P = ceremony()

    class K:
        def held(self, k):
            return False
    ui = P.UI(splash.begin(), K(), c.sig)
    ok = True
    for st in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10"):
        try:
            ui.dirty = True
            ui.draw()
            S.arm()
            ui.result = (st,) + ui.c.run(st)
            if not ui.result[1]:
                print("   ui %s: %r" % (st, ui.result[1:]))
            ui.dirty = True
            ui.draw()
            ui.result = None
        except Exception as e:
            ok = False
            sys.print_exception(e)
    check(ok and ui.c.step() == "C10", "the ceremony screen draws every step and its result")


def main():
    for case in (case_full, case_seal_gate, case_refusals, case_console, case_ui):
        print("--", case.__name__[5:])
        try:
            case()
        except Exception as e:
            failed[0] += 1
            print("FAIL  %s raised" % case.__name__)
            sys.print_exception(e)
    print("ceremony: %d failed" % failed[0])
    return failed[0]
