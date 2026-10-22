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


def secrets(lock=True, genkey=True, extra=""):
    with open("secrets.py", "w") as f:
        f.write('WIFI_SSID = "emulator"\nWIFI_PASS = ""\nHOSTNAME = "emu"\nALLOW_LOCK = %s\nALLOW_GENKEY = %s\n' % (lock, genkey) + extra)
    try:
        os.remove("build.py")
    except OSError:
        pass
    for m in ("secrets", "build", "image", "signer", "atecc", "chipcfg", "provision", "setup_s", "chipapp"):
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
    check(sim.counters[0] >= 5, "%s: counter 0 = %d: C5's two test signatures, C6's two, C9's, and the public-key reads after the data lock" % (rev, sim.counters[0]))
    return c


def case_full():
    walk("608a")
    walk("608b")
    walk("608c")                        # the key-c's part, revision 00006005, same factory table


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
    check(Q.row["limitedUse"] and not Q.row["intSign"] and Q.counter == sim.counters[0] == 1,
          "slot 0 reads as LimitedUse, external sign only; the count is 1, the boot's own public-key read")
    check(Q.outside == 0, "first boot on the sealed chip: no uses flagged (its own public-key read is not one)")
    Q = T.fresh(expect={"serial": T.SERIAL, "slot": 0, "owner": owner, "locked": True}, keep=True)
    check(Q.outside == 0 and Q.pin_ok, "a reboot: still none flagged, though the boot read the key again")
    before = sim.counters[0]
    T.serve(Q, [T.tx(Q, 0)])
    check(T.sign(Q, Q.queue[0], 2100) and sim.counters[0] == before + 1 and Q.counter == before + 1 and Q.outside == 0,
          "a signature: exactly one use (the slot is sealed, so the check before it reads only the serial), none flagged")
    Q2 = T.fresh(expect={"serial": "0123ffffffffffffff", "slot": 0, "owner": owner, "locked": True}, keep=True)
    Q2.handle("A")
    Q2.handle("A")                          # "Check again" twice on the pin-fail screen: two more reads of the key
    Q = T.fresh(expect={"serial": T.SERIAL, "slot": 0, "owner": owner, "locked": True}, keep=True)
    check(Q.outside == 0, "Check again on the pin-fail screen reads the key; the next boot does not flag it")
    sim.counters[0] += 1                    # something else on the bus uses the key
    sim.save()
    Q = T.fresh(expect={"serial": T.SERIAL, "slot": 0, "owner": owner, "locked": True}, keep=True)
    check(Q.outside == 1, "a use the console did not make: flagged at the next boot")


def case_dual():
    """The dual image picks the console or the ceremony from the chip on the bus, at every boot."""
    import quorum_cfg, webauthn

    def boot(expect=None):
        secrets()
        with open("secrets.py", "a") as f:
            if expect:
                f.write("QUORUM_EXPECT = %r\n" % expect)
        with open("build.py", "w") as f:
            f.write('IMAGE = "dual"\nBUILD = "test"\nDATE = 0\n')
        for m in ("build", "image", "main_dual"):
            sys.modules.pop(m, None)
        import main_dual
        return main_dual
    atecc_sim.provision(0)                  # chip 1: the test table, pinned
    atecc_sim.chip().cfg[88] &= 0xFE
    x, y = p256.pubkey(atecc_sim.chip().keys[0])
    serial = "".join("%02x" % b for b in bytes(atecc_sim.chip().cfg[0:4]) + bytes(atecc_sim.chip().cfg[8:13]))
    pin = {"serial": serial, "slot": 0, "owner": webauthn.owner_address("0x%064x" % x, "0x%064x" % y, quorum_cfg.CFG["signer"]), "locked": True}
    D = boot(pin)
    check(D.which()[0] == "console", "dual, the pinned chip: the console")
    import image
    check(image.PRODUCTION, "dual: the console's production rules unless the ceremony is chosen")
    def fresh_other():
        fresh_chip()
        atecc_sim.chip().cfg[8:13] = bytes([0x42, 0x42, 0x42, 0x42, 0xEE])   # a real fresh chip has its own serial
        atecc_sim.chip().save()
    fresh_other()
    D = boot(pin)
    w = D.which()
    check(w[0] == "ceremony" and w[2] == "factory", "dual, a fresh chip: the ceremony")
    D = boot(None)
    c, S, P = ceremony()
    for st in ("C1", "C2", "C3"):
        run(c, st)
    check(D.which()[0] == "ceremony", "dual, a quorum v1 chip half way (data zone open): the ceremony again")
    atecc_sim.provision_v1()
    check(D.which()[0] == "console", "dual, a sealed quorum v1 chip, not pinned yet: the console (it says Not pinned)")
    atecc_sim.present = False
    try:
        check(D.which()[0] == "console", "dual, no chip: the console (it says No chip)")
    finally:
        atecc_sim.present = True
    fresh_other()
    D = boot(pin)
    D.run()
    import signer, chipapp
    image = sys.modules["image"]
    check(not image.PRODUCTION and signer.flag("ALLOW_LOCK") and "chipapp" in sys.modules and chipapp.profile == "factory",
          "dual, run() on a fresh chip: the ceremony app, with ALLOW_* honoured")
    chipapp.stop()
    os.remove("build.py")


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


def case_three():
    """The ceremony on the Feather's three buttons (board "feather-s3", setup_s.UI), C1-C10 on a
    608C through tick alone, on a fake clock. D0 is back, D0+D1 held 3 s arms, D2 does a step and,
    armed, held 3 s does a permanent or GenKey one. D2 never arms, D1+D2 is no arm, an arm let go
    early is none, and with ALLOW_LOCK off nothing happens. Every screen fits 240x135 right of the
    rail. Run in a device of its own (main_three): board.py is read once."""
    import board
    check(board.THREE and (board.W, board.H) == (240, 135), "the Feather: three buttons, 240x135")
    secrets(extra='BOARD = "feather-s3"\n')
    fresh_chip("608c")
    c, S, P = ceremony()
    import splash, setup_s, chipapp

    class Clock:
        now = 0

        def ticks_ms(self):
            return self.now

        def ticks_diff(self, a, b):
            return a - b

        def ticks_add(self, a, b):
            return a + b

        def sleep_ms(self, ms):
            self.now += ms

        def gmtime(self, *a):
            import time
            return time.gmtime(*a)
    T = Clock()
    for m in (P, S, setup_s):
        m.time = T

    class Keys:
        down = set()
        queue = []

        def held(self, k):
            return k in self.down

        def pressed(self):
            out, self.queue = self.queue, []
            return out
    keys = Keys()
    d = splash.begin()
    drawn, bad = [], []
    real = d.text

    def text(s, x, y, col):
        drawn.append((s, x, y))
        return real(s, x, y, col)
    d.text = text

    def fits(where):
        for s, x, y in drawn:
            rail = where != "banner" and x < setup_s.RAIL and len(s) > 4      # the banner has no rail
            if x + 8 * len(s) > 240 or y + 8 > 135 or x < 0 or y < 0 or rail:
                bad.append((where, s, x, y))
        drawn[:] = []

    # the banner: D2 opens PROVISION, in setup_s's screen
    chipapp.d, chipapp.keys, chipapp.sig = d, keys, c.sig
    chipapp.identify()
    chipapp.banner()
    fits("banner")
    keys.queue = ["D2"]
    chipapp.tick(None)
    check(isinstance(chipapp.prov, setup_s.UI) and [k for k, _ in chipapp.choices()] == ["PROVISION (quorum v1)"],
          "the banner: D2 opens PROVISION on the three-button screen; no button-driven chip map")
    ui = setup_s.UI(d, keys, c.sig, "dark", c)

    def tick(*pressed):
        r = ui.tick(list(pressed))
        ui.dirty = True
        ui.draw()
        fits(c.step())
        return r

    def down(k):
        keys.down.add(k)
        return tick(*([] if k == "D1" else [k]))       # D1 arrives as a press only once let go (lcd.Keys)

    def up(k):
        keys.down.discard(k)
        return tick(*(["D1"] if k == "D1" else []))

    def wait(ms):
        for _ in range(ms // 100):
            T.now += 100
            tick(*(["D1L"] if "D1" in keys.down else []))

    def arm(ms=3100):
        down("D0")
        down("D1")
        wait(ms)
        up("D1")
        up("D0")
        return S.armed()

    def hold_d2(ms):
        st = c.step()
        down("D2")
        wait(ms)
        up("D2")
        return c.step() != st or ui.result is not None

    def press_d2():
        st = c.step()
        down("D2")
        up("D2")
        return ui.result is not None and ui.result[0] == st

    def dismiss():
        down("D2")
        up("D2")
        T.now += 61000                                   # the arm runs out between steps
    order = []
    for want in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10"):
        st = c.step()
        order.append(st)
        if st in c.PERMANENT or st in c.GENKEY:
            check(not hold_d2(3500), "%s: D2 held 3.5 s, not armed: nothing" % st)
            down("D1")
            check(not hold_d2(3500) and not S.armed(), "%s: D1+D2 held: no arm, nothing done" % st)
            up("D1")
            check(not arm(2000) and c.step() == st, "%s: D0+D1 let go at 2 s: not armed" % st)
            T.now += 2000
            tick()
            if st == "C3":
                real_flag = S.flag
                S.flag = lambda name: False
                try:
                    check(arm() and not hold_d2(3500) and c.step() == "C3" and not ui.result,
                          "C3 with ALLOW_LOCK off: armed, D2 held 3.5 s, nothing locked")
                finally:
                    S.flag = real_flag
                S.disarm()
                down("D0")
                check(up("D0") == "back", "C3: D0 alone is back")
            check(arm() > 50, "%s: D0+D1 held 3 s: armed for 60 s" % st)
            check(not hold_d2(2900) and c.step() == st, "%s: D2 held 2.9 s: not yet" % st)
            ok = hold_d2(3100) and ui.result and ui.result[0] == st and ui.result[1]
        else:
            ok = press_d2() and ui.result[1]
        check(st == want and ok, "%s %s on three buttons%s" % (want, P.TITLES[want], "" if ok else ": %r" % (ui.result,)))
        dismiss()
    sim = atecc_sim.chip()
    cfg = bytes(sim.cfg)
    check(order == ["C%d" % i for i in range(1, 11)] and cfg[86] == 0 and cfg[87] == 0 and cfg[88] == 0xFE,
          "the Feather walks C1-C10: locks 00 00, slot 0 sealed (FE FF)")
    ui.c.picture = lambda st, result=False: "0x" + "ab" * 20
    for res in (None, ("C10", True, [("x" * 30, True)] * 9, "owner 0x" + "ab" * 20 + " and some more words")):
        ui.result = res
        ui.dirty = True
        ui.draw()
        fits("picture")
    check(not bad, "every screen fits 240x135, and left of the rail only the rail's words" + ("" if not bad else ": %r" % bad[:4]))


def main_three():
    """case_three, alone in a fresh device: secrets.py names the Feather before board.py is read."""
    with open("secrets.py", "w") as f:
        f.write('BOARD = "feather-s3"\n')
    for m in ("board", "lcd", "splash", "bootmark"):
        sys.modules.pop(m, None)
    print("-- three")
    try:
        case_three()
    except Exception as e:
        failed[0] += 1
        print("FAIL  case_three raised")
        sys.print_exception(e)
    print("three: %d failed" % failed[0])
    return failed[0]


def main():
    for case in (case_full, case_seal_gate, case_refusals, case_console, case_dual, case_ui):
        print("--", case.__name__[5:])
        try:
            case()
        except Exception as e:
            failed[0] += 1
            print("FAIL  %s raised" % case.__name__)
            sys.print_exception(e)
    print("ceremony: %d failed" % failed[0])
    return failed[0]
