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
    for m in ("secrets", "build", "image", "signer", "atecc", "chipcfg", "ceremony_ui", "keyflow", "provision", "setup_s", "chipapp"):
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


class Clock:
    """time for provision and signer, moved by hand: the holds and the arm to the millisecond."""
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


def case_arm_left():
    """A hold starts only with provision.ARM_LEFT of the arm to go. Chip 3, 2026-10-22: C6's hold
    started with about 4 s left, the arm ran out during its test signature and the lock was refused.
    With less, A held does nothing and the screen says arm again; on the knob, the hold arms again."""
    import splash, time
    secrets()
    fresh_chip()
    c, S, P = ceremony()
    for st in ("C1", "C2"):
        c.run(st)
    T = Clock()
    import ceremony_ui as CU
    P.time = S.time = CU.time = T
    try:
        class K:
            down = set()

            def held(self, k):
                return k in self.down
        keys = K()
        d = splash.begin()
        drawn = []
        real = d.text

        def text(s, x, y, col):
            drawn.append(s)
            return real(s, x, y, col)
        d.text = text
        ui = P.UI(d, keys, c.sig, "dark", c)

        def hold(k, ms):
            keys.down = {k}
            for _ in range(ms // 100):
                T.now += 100
                ui.tick([])
            keys.down = set()
            ui.tick([])

        def said():
            drawn[:] = []
            ui.dirty = True
            ui.draw()
            return " ".join(drawn)
        S.arm()
        T.now += 51000                                  # 9 s left
        hold("A", 4000)
        check(c.step() == "C3" and ui.result is None and "arm again" in said(),
              "9 s of the arm left: A held 4 s locks nothing, and the screen says arm again")
        S.arm()
        T.now += 50000                                  # 10 s left
        hold("A", 3100)
        check(ui.result and ui.result[:2] == ("C3", True), "10 s left: A held 3 s locks the config")
        ui.result, ui.knob = None, True
        S.arm()
        T.now += 51000
        hold("press", 3100)
        check(c.step() == "C4" and ui.result is None and S.armed() == 60,
              "the knob, 9 s left: the hold arms again for 60 s, and makes no key")
        hold("press", 3100)
        check(ui.result and ui.result[:2] == ("C4", True), "the knob, armed again: the next hold makes the key")
    finally:
        P.time = S.time = CU.time = time


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
    import splash, setup_s, chipapp, ceremony_ui
    T = Clock()
    for m in (P, S, setup_s, ceremony_ui):
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
            if st == "C6":
                check(arm() > 50, "C6: armed")
                T.now += 51000                                   # 9 s left, as chip 3's first try
                tick()
                ui.dirty = True
                ui.draw()
                said = " ".join(s for s, _, _ in drawn)
                fits("C6")
                check("Arm again" in said and not hold_d2(3500) and c.step() == "C6",
                      "C6 with 9 s of the arm left: says arm again, and D2 held 3.5 s seals nothing")
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
    ui.result = ("C6", False, [], "lock refused: not armed: hold B+Y 3 s")       # signer.gate's words
    ui.dirty = True
    ui.draw()
    said = " ".join(s for s, _, _ in drawn)
    fits("refusal")
    check("D0+D1" in said and "B+Y" not in said, "a refusal names D0+D1, not the Pico's B+Y")
    ui.c.picture = lambda st, result=False: "0x" + "ab" * 20
    for res in (None, ("C10", True, [("x" * 30, True)] * 9, "owner 0x" + "ab" * 20 + " and some more words")):
        ui.result = res
        ui.dirty = True
        ui.draw()
        fits("picture")
    check(not bad, "every screen fits 240x135, and left of the rail only the rail's words" + ("" if not bad else ": %r" % bad[:4]))


def case_knob():
    """The ceremony on the knob Feather (board "feather-knob", setup_s.UI): Boot is D0, a detent
    clockwise D1, anticlockwise D1L, the push D2. A turn can't be held, so Boot held 3 s alone is the
    arm; a detent back is back; the push does a step and, armed, held 3 s does a permanent or GenKey
    one. The push never arms, Boot let go at 2 s is no arm, Boot and the push held together run no
    step, and with ALLOW_LOCK off nothing happens. C1-C10 on a 608C through tick alone, every screen
    within 240x135, and the words are Boot and push. Run in a device of its own (main_knob)."""
    import board
    check(board.DIAL and board.THREE and (board.W, board.H) == (240, 135), "the knob Feather: Boot and the knob, 240x135")
    secrets(extra='BOARD = "feather-knob"\n')
    fresh_chip("608c")
    c, S, P = ceremony()
    import splash, setup_s, chipapp, ceremony_ui
    T = Clock()
    for m in (P, S, setup_s, ceremony_ui):
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
            rail = where != "banner" and x < setup_s.RAIL and len(s) > 4
            if x + 8 * len(s) > 240 or y + 8 > 135 or x < 0 or y < 0 or rail:
                bad.append((where, s, x, y))
        drawn[:] = []

    chipapp.d, chipapp.keys, chipapp.sig = d, keys, c.sig
    chipapp.identify()
    chipapp.banner()
    said = " ".join(s for s, _, _ in drawn)
    fits("banner")
    keys.queue = ["D2"]
    chipapp.tick(None)
    check("push: PROVISION" in said and isinstance(chipapp.prov, setup_s.UI), "the banner: the push opens PROVISION")
    ui = setup_s.UI(d, keys, c.sig, "dark", c)

    def tick(*pressed):
        r = ui.tick(list(pressed))
        ui.dirty = True
        ui.draw()
        fits(c.step())
        return r

    def down(k):
        keys.down.add(k)
        return tick(k)

    def up(k):
        keys.down.discard(k)
        return tick()

    def wait(ms):
        for _ in range(ms // 100):
            T.now += 100
            tick()

    def arm(ms=3100):
        down("D0")
        wait(ms)
        up("D0")
        return S.armed()

    def hold_push(ms):
        st = c.step()
        down("D2")
        wait(ms)
        up("D2")
        return c.step() != st or ui.result is not None

    def push():
        st = c.step()
        down("D2")
        up("D2")
        return ui.result is not None and ui.result[0] == st

    def dismiss():
        push()
        T.now += 61000
    order = []
    for want in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10"):
        st = c.step()
        order.append(st)
        if st in c.PERMANENT or st in c.GENKEY:
            check(not hold_push(3500) and not S.armed(), "%s: the push held 3.5 s, not armed: nothing, and no arm" % st)
            check(not arm(2000) and c.step() == st, "%s: Boot let go at 2 s: not armed" % st)
            T.now += 2000
            tick()
            down("D2")
            down("D0")
            wait(3500)
            up("D0")
            up("D2")
            check(c.step() == st and not ui.result, "%s: Boot and the push held together: no step" % st)
            S.disarm()
            T.now += 2000
            tick()
            if st == "C3":
                real_flag = S.flag
                S.flag = lambda name: False
                try:
                    check(arm() and not hold_push(3500) and c.step() == "C3" and not ui.result,
                          "C3 with ALLOW_LOCK off: armed, the push held 3.5 s, nothing locked")
                finally:
                    S.flag = real_flag
                S.disarm()
                down("D0")
                check(up("D0") is None, "C3: Boot tapped is not back")
                check(tick("D1L") == "back", "C3: a detent back is back")
            if st == "C6":
                check(arm() > 50, "C6: armed")
                T.now += 51000
                tick()
                ui.dirty = True
                ui.draw()
                said = " ".join(s for s, _, _ in drawn)
                fits("C6")
                check("Arm again: Boot 3 s" in said and not hold_push(3500) and c.step() == "C6",
                      "C6 with 9 s of the arm left: says arm again with Boot, and the push held 3.5 s seals nothing")
            check(arm() > 50, "%s: Boot held 3 s: armed for 60 s" % st)
            check(not hold_push(2900) and c.step() == st, "%s: the push held 2.9 s: not yet" % st)
            ok = hold_push(3100) and ui.result and ui.result[0] == st and ui.result[1]
        else:
            ok = push() and ui.result[1]
        check(st == want and ok, "%s %s on the knob%s" % (want, P.TITLES[want], "" if ok else ": %r" % (ui.result,)))
        dismiss()
    sim = atecc_sim.chip()
    cfg = bytes(sim.cfg)
    check(order == ["C%d" % i for i in range(1, 11)] and cfg[86] == 0 and cfg[87] == 0 and cfg[88] == 0xFE,
          "the knob Feather walks C1-C10: locks 00 00, slot 0 sealed (FE FF)")
    ui.result = ("C6", False, [], "lock refused: not armed: hold B+Y 3 s")
    ui.dirty = True
    ui.draw()
    said = " ".join(s for s, _, _ in drawn)
    fits("refusal")
    check("hold Boot 3 s" in said and "B+Y" not in said and "D0" not in said, "a refusal names Boot, not B+Y or D0+D1")
    check(not bad, "every screen fits 240x135, and left of the rail only the rail's words" + ("" if not bad else ": %r" % bad[:4]))


def main_knob():
    """case_knob, alone in a fresh device."""
    with open("secrets.py", "w") as f:
        f.write('BOARD = "feather-knob"\n')
    for m in ("board", "lcd", "splash", "bootmark", "setup_s", "chipapp"):
        sys.modules.pop(m, None)
    print("-- knob")
    try:
        case_knob()
    except Exception as e:
        failed[0] += 1
        print("FAIL  case_knob raised")
        sys.print_exception(e)
    print("knob: %d failed" % failed[0])
    return failed[0]


# ----------------------------------------------------------------------------- console-rp's own key
def prepared(rev="608c"):
    """A chip as console-rp's bench leaves it: C1-C3 by provision (ALLOW_LOCK and the arm, on a dev
    board), then nothing. quorum v1, config locked, data zone open, no key."""
    secrets()
    fresh_chip(rev)
    c, S, P = ceremony()
    for st in ("C1", "C2", "C3"):
        got, ok, bad, msg = run(c, st)
        if got != st or not ok:
            raise Exception("prepare %s: %s %s" % (st, bad, msg))
    S.disarm()
    return atecc_sim.chip()


def as_image(name):
    """This board as tools/fw build makes the image: build.py names it, secrets.py has no ALLOW_*.
    -> (ChipSigner, signer, keyflow)."""
    with open("secrets.py", "w") as f:
        f.write('BOARD = "console-rp"\n')
    with open("build.py", "w") as f:
        f.write('IMAGE = "%s"\nBUILD = "test"\nDATE = 1793000000\n' % name)
    for m in ("secrets", "build", "image", "signer", "atecc", "chipcfg", "ceremony_ui", "keyflow", "provision", "policy", "chips"):
        sys.modules.pop(m, None)
    import signer, keyflow
    return signer.ChipSigner(), signer, keyflow


def no_files():
    for f in ("pin.json", "keyflow.json"):
        try:
            os.remove(f)
        except OSError:
            pass


def refused(fn):
    try:
        fn()
    except Exception as e:
        return "refused" in str(e)
    return False


def rp_route():
    """main_rp.route() on the chip as it is: "key" or "console"."""
    src = open("main_rp.py").read()
    ns = {"__name__": "main_rp_route"}
    exec(src[:src.index("_quorum = None")], ns)
    return ns["route"]()[0]


def case_own_key_gate():
    """signer.own_key_step: on console-rp, the screen's arm alone may make the owner's key, seal it and
    lock the data zone, in that order, on a chip the bench prepared, and nothing else ever."""
    no_files()
    fresh_chip("608c")
    s, S, K = as_image("console-rp")
    S.arm()
    check(refused(lambda: s.genkey(0)), "console-rp, a factory chip, armed: GenKey refused")
    check(rp_route() == "key", "a factory chip and no pin: the key flow, which says Not prepared")
    check(K.OwnKey(s).step() == "unprepared", "the key flow on a factory chip: unprepared, nothing to do")
    sim = prepared()
    s, S, K = as_image("console-rp")
    check(rp_route() == "key", "a prepared chip and no pin: the key flow")
    S.disarm()
    check(refused(lambda: s.genkey(0)), "console-rp, a prepared chip, not armed: GenKey refused")
    S.arm(10)
    try:
        s.genkey(0)
        made = 0 in sim.keys
    except Exception as e:
        made = False
        print("   genkey:", e)
    check(made, "console-rp, a prepared chip, armed: GenKey in slot 0")
    check(refused(lambda: s.genkey(1)) and refused(lambda: s.lock_slot(1)) and refused(lambda: s.lock_config())
          and refused(lambda: s.lock_data()), "armed: GenKey in slot 1, slot 1's lock, the config lock, the plain data lock: refused")
    check(refused(lambda: K.lock_data_crc(s, 0x1234)) and sim.cfg[86] == 0x55, "armed: the data lock refused while slot 0 is open")
    S.disarm()
    check(refused(lambda: s.lock_slot(0)), "not armed: the seal refused")
    S.arm(10)
    try:
        s.lock_slot(0)
    except Exception as e:
        print("   seal:", e)
    check(sim.slot_locked(0), "armed: slot 0 sealed")
    S.arm(10)
    check(refused(lambda: s.genkey(0)) and refused(lambda: s.lock_slot(0)), "sealed: GenKey and the seal again refused, armed")
    c = K.Ceremony(s)
    c.run("C7")
    c.run("C8")
    got, ok, bad, msg = run(c, "C9", arm=False)
    check(got == "C9" and not ok and sim.cfg[86] == 0x55, "sealed, not armed: the data lock refused")
    got, ok, bad, msg = run(c, "C9")
    check(ok and sim.cfg[86] == 0x00, "sealed, armed: the data lock, the chip checking its CRC" + ("" if ok else " (%s %s)" % (bad, msg)))
    S.arm(10)
    check(refused(lambda: s.genkey(0)) and refused(lambda: s.lock_slot(0)) and refused(lambda: K.lock_data_crc(s, c.summary)),
          "locked: everything refused, armed")
    for img in ("console", "dual", "ceremony"):
        sim = prepared()
        s, S, K = as_image(img)
        S.arm(10)
        check(refused(lambda: s.genkey(0)) and 0 not in sim.keys, "the %s image, a prepared chip, armed: GenKey refused" % img)
    secrets()
    fresh_chip("608c")
    import signer, provision, chipcfg
    s0 = signer.ChipSigner()
    provision.write_table(s0, chipcfg.QUORUM_V3)
    signer.arm()
    provision.lock_config_crc(s0, chipcfg.QUORUM_V3)
    s, S, K = as_image("console-rp")
    S.arm(10)
    check(refused(lambda: s.genkey(0)) and refused(lambda: s.lock_slot(0)), "console-rp, a chip locked as quorum v3 (data open), armed: refused")
    check(rp_route() == "console", "a chip locked as something else: the console, not the key flow")
    no_files()


class Keys:
    """lcd.Keys by hand: what is down, and the presses since the last look."""

    def __init__(self):
        self.down, self.queue = set(), []

    def held(self, k):
        return k in self.down

    def pressed(self):
        out, self.queue = self.queue, []
        return out


def case_own_key():
    """The owner makes the key on console-rp (keyflow.OwnKey on keypick_rp.UI), through tick alone on
    a fake clock: K0, Make (replacing a key written in before), Replace, Full, Seal, the hold that
    seals and locks, the pin, and the console on that pin. Then what a restart in between finds."""
    no_files()
    sim = prepared()
    planted = p256.rand_scalar()
    sim.keys[0] = planted                   # written in while the data zone was open
    sim.save()
    s, S, K = as_image("console-rp")
    import crt, keypick_s, keypick_rp, splash
    crt.FX = False
    T = Clock()
    keypick_s.time = T
    keys = Keys()
    c = K.OwnKey(s)
    ui = keypick_rp.UI(splash.begin(), keys, s, c)

    def tick(*pressed):
        r = ui.tick(list(pressed))
        ui.draw()
        return r

    def hold(ms=3100):
        keys.down.add("D2")
        for _ in range(ms // 100 + 1):
            tick()
            T.now += 100
        keys.down.discard("D2")
        tick()

    import fonts
    said, text0 = [], fonts.text

    def text(d, t, *a):
        said.append(t)
        return text0(d, t, *a)

    def shown():
        """Every string the page draws now, in order: a paragraph's lines join back with spaces, so a
        cut one (quorum_ui.para stops at its bottom with no sign) is missing its end."""
        said[:] = []
        ui.dirty = True
        ui.draw()
        return said[:]
    fonts.text = text

    check(c.step() == "K0", "first: K0, read only")
    tick()
    check(c.step() == "C4" and c.had_key and c.checked and not all(k for _, k in c.checked),
          "K0 says a key is in slot 0 already, and Make comes before anything else")
    on = shown()
    check("it never leaves it. Each try replaces the last." in " ".join(on) and "Make" in on,
          "the first page whole: each try replaces the last")
    hold()
    check(sim.cfg[88] & 1 and c.step() == "C4", "a hold on Make does nothing: Make is one press")
    tick("D2")
    k1 = sim.keys.get(0)
    check(k1 not in (None, planted) and c.step() == "C5" and ui.tries == 1, "Make (D2): GenKey replaced the key that was there")
    on = shown()
    check("Like it? Seal it in your signer. Or replace it." in " ".join(on) and "Replace" in on and "Seal" in on
          and "New" not in on, "the pick page whole: Seal (D2), or Replace (D0), not New")
    tick("D0")
    check(sim.keys.get(0) not in (None, k1, planted) and ui.tries == 2, "Replace (D0): another key in its place")
    tick("D1")
    full = ui.page
    on = shown()
    tick("D1")
    check(full == "full" and ui.page == "pic" and "Replace" in on and "Seal" in on, "Full (D1), the same Replace and Seal, and back")
    keys.down.add("D2")
    tick("D2")
    check(ui.page == "keep", "Seal (D2): the red page")
    on = shown()
    fonts.text = text0
    check("Seal this key?" in on and "Hold Seal 3 s" in on and "Seal" in on and "Keep" not in " ".join(on),
          "the red page says Seal: its title, the hold and D2")
    for _ in range(40):
        T.now += 100
        tick()
    check(sim.cfg[88] & 1 and ui.held_since is None, "the press that chose doesn't roll into Keep's hold: let go first")
    keys.down.discard("D2")
    tick("D0")
    check(ui.page == "pic" and sim.cfg[88] & 1, "Back (D0) on Keep: the picture again, nothing sealed")
    tick("D2")
    keys.down.add("D2")
    tick()
    T.now += 1500
    tick()
    keys.down.discard("D2")
    tick()
    T.now += 2000
    tick()
    check(sim.cfg[88] & 1, "Keep let go at 1.5 s: nothing sealed")
    before = sim.counters[0]
    import board, qlog
    unix = board.unix
    board.unix = lambda: 1609459200         # an RP2350's clock at start: 2021, no RTC and no network
    lines, tap = [], qlog.TAP
    qlog.TAP = lines.append
    busy = []                               # each busy page as the steps saw it: its steps, passed
    run = ui.step_run
    def seen(step):
        busy.append((step, ui._busy, [s for s, _ in ui._todo], sorted(ui._ok)))
        return run(step)
    ui.step_run = seen
    reads = []                              # public-key reads once the data zone is locked: each counts
    pub = c.chip.pubkey
    def pubkey(slot):
        reads.append(sim.cfg[86] == 0x00)
        return pub(slot)
    c.chip.pubkey = pubkey
    hold()
    del ui.step_run, c.chip.pubkey
    qlog.TAP = tap
    board.unix = unix
    tag = " key %s " % c.serial              # after the stamp: "+12s" on a board, a date and time here
    logged = [l.split(tag, 1)[1].split(" ")[:2] for l in lines if tag in l]
    check([s for s, _ in logged] == ["C5", "C6", "C7", "C8", "C9", "C10"] and all(k == "ok:" for _, k in logged),
          "each step of the hold in the log, ok: %s" % " ".join(s for s, _ in logged))
    check(all(b and todo == ["C5", "C6", "C8", "C9", "C10"] for _, b, todo, _ in busy) and busy[-1][3] == ["C5", "C6", "C7", "C8", "C9"],
          "the busy page up for every step, its list Keep's five, ticked as they passed")
    check(ui._tm is None and not ui._busy, "the chip's timer stopped once the steps ran (FX off here: never started)")
    fb, mv = crt.tile(keypick_rp.TS, keypick_rp.TS)
    r = ui.draw_chip(fb, 0, 0, 5)
    lit = fb.pixel(*keypick_rp.LEGS[5][:2]) == ui.colours()[2][0]
    check(len(r) == 4 and lit and len(mv) == keypick_rp.TS * keypick_rp.TS * 2 <= len(crt._noise),
          "the chip's frame: on the noise strip's memory, the light on leg 5 at frame 5")
    check(not sim.cfg[88] & 1 and sim.cfg[86] == 0x00 and c.step() == "done" and ui.result is None,
          "Keep held 3 s: test signatures, the seal, the record and the data lock, then the pin")
    import policy, chipcfg
    pin = policy.pin_file()
    x, y = p256.pubkey(sim.keys[0])
    rec = chipcfg.record_decode(bytes(sim.otp))
    check(pin == {"serial": c.serial, "slot": 0, "owner": c.owner(), "locked": True} and chipcfg.record_matches(rec, x, y),
          "pin.json names this chip, slot 0 and the key's owner; the OTP record names the key")
    check(rec["date"] == 1793000000, "a clock still in 2021: the record is dated from the build (image.DATE)")
    after_lock = sum(reads)
    check(sim.counters[0] == before + 5 + after_lock and after_lock == 3,
          "counter 0 went up %d: C5's two signatures, C6's two, C9's one, and %d public-key reads after the "
          "data lock (silicon counts those: atecc_sim)" % (sim.counters[0] - before, after_lock))
    check(tick("D2") == "console", "Done: D2 starts the console")
    check(rp_route() == "console", "pinned: the console from now on")
    sys.path.insert(0, "/")
    import console_test as CT
    Q = CT.fresh(expect=None)
    check(Q.pin_ok and Q.state == "home" and Q.EXPECT and Q.EXPECT["owner"] == pin["owner"], "the console starts on the pin the key flow wrote")
    with open("pin.json", "w") as f:
        f.write('{"serial": "0123ffffffffffffff", "slot": 0, "owner": "%s", "locked": true}' % pin["owner"])
    Q = CT.fresh(expect=None, keep=True)
    check(Q.state == "pinfail" and not Q.pin_ok, "a pin for another chip: pinfail")
    check(rp_route() == "console", "a pin for another chip: the console (pinfail), never the key flow again")
    no_files()

    # a restart between the seal and the data lock, and the chip sealed by something else
    sim = prepared()
    s, S, K = as_image("console-rp")
    c = K.OwnKey(s)
    c.run("K0")
    S.arm(10)
    c.run("C4")
    c.run("C5")
    S.arm(10)
    c.run("C6")
    check(not sim.cfg[88] & 1 and K.read_json(K.STATE_FILE) and c.step() == "C7", "sealed here: keyflow.json names it, C7 next")
    s, S, K = as_image("console-rp")
    c = K.OwnKey(s)
    check(c.step() == "C7", "after a restart: Finish (C7-C9), keyflow.json matches")
    no_files()
    s, S, K = as_image("console-rp")
    check(K.OwnKey(s).step() == "elsewhere", "the same chip, keyflow.json gone: sealed elsewhere, nothing locks it here")
    with open("keyflow.json", "w") as f:
        f.write('{"serial": "%s", "key": "%s"}' % (c.serial, "00" * 32))
    s, S, K = as_image("console-rp")
    check(K.OwnKey(s).step() == "elsewhere", "keyflow.json for another key: elsewhere")
    no_files()


def bench_image(lock=True):
    """prepare-rp as swdload.py loads it on the bench: build.py names the image, and the bench secrets.py
    holds ALLOW_LOCK and nothing else. -> (ChipSigner, signer, prepare)."""
    with open("secrets.py", "w") as f:
        f.write('BOARD = "console-rp"\n' + ("ALLOW_LOCK = True\n" if lock else ""))
    with open("build.py", "w") as f:
        f.write('IMAGE = "prepare-rp"\nBUILD = "test"\nDATE = 1793000000\n')
    for m in ("secrets", "build", "image", "signer", "atecc", "chipcfg", "ceremony_ui", "keyflow", "provision", "prepare",
              "setup_s", "policy", "chips"):
        sys.modules.pop(m, None)
    import signer, prepare
    return signer.ChipSigner(), signer, prepare


def case_prepare():
    """prepare-rp on a factory 608C, through setup_s's screen on console-rp alone, as on the bench: C1 and
    C2 a D2 press each, C3 the D0+D1 arm and D2 held 3 s, then P4 reads the chip. No key is made, the
    public key is never asked for, and the customer image takes the chip from there."""
    no_files()
    for f in ("prep-log.txt",):
        try:
            os.remove(f)
        except OSError:
            pass
    fresh_chip("608c")
    sim = atecc_sim.chip()
    s, S, PR = bench_image()
    import setup_s, ceremony_ui, splash
    T = Clock()
    for m in (setup_s, ceremony_ui, S):
        m.time = T
    keys = Keys()
    c = PR.Ceremony(s)
    d = splash.begin()
    ui = setup_s.UI(d, keys, s, "dark", c)
    bad, real = [], d.text

    def text(t, x, y, col):
        row = y == 135 - 9              # the buttons' words along the bottom
        if x < 0 or x + 8 * len(t) > 240 or y < 0 or (not row and y + 8 > setup_s.FOOT):
            bad.append((c.step(), t, x, y))
        return real(t, x, y, col)
    d.text = text

    def tick(*pressed):
        r = ui.tick(list(pressed))
        ui.dirty = True
        ui.draw()
        return r

    def down(k):
        keys.down.add(k)
        return tick(*([] if k == "D1" else [k]))

    def up(k):
        keys.down.discard(k)
        return tick(*(["D1"] if k == "D1" else []))

    def wait(ms):
        for _ in range(ms // 100):
            T.now += 100
            tick(*(["D1L"] if "D1" in keys.down else []))

    def press_d2():
        down("D2")
        up("D2")

    def dismiss():
        press_d2()

    check(c.step() == "C1", "a factory chip: C1 first")
    press_d2()
    check(ui.result and ui.result[0] == "C1" and ui.result[1], "C1, D2: pre-flight passes, the factory config saved")
    dismiss()
    press_d2()
    check(ui.result and ui.result[0] == "C2" and ui.result[1] and sim.cfg[87] == 0x55, "C2, D2: quorum v1 written, still open")
    dismiss()
    check(c.step() == "C3", "then C3")
    press_d2()
    down("D2")
    wait(3500)
    up("D2")
    check(sim.cfg[87] == 0x55 and not ui.result, "C3, D2 held 3.5 s, not armed: nothing locked")
    down("D0")
    down("D1")
    wait(3100)
    up("D1")
    up("D0")
    check(S.armed() > 0, "D0+D1 held 3 s: armed")
    down("D2")
    wait(1500)
    up("D2")
    check(sim.cfg[87] == 0x55, "C3, D2 let go at 1.5 s: nothing locked")
    down("D2")
    wait(3200)
    up("D2")
    check(ui.result and ui.result[0] == "C3" and ui.result[1] and sim.cfg[87] == 0x00, "C3, armed, D2 held 3 s: the config locked")
    dismiss()
    check(c.step() == "P4", "then P4, the no-key check")
    press_d2()
    ok = ui.result and ui.result[0] == "P4" and ui.result[1]
    check(ok and c.step() == "ready", "P4, D2: config locked as quorum v1, data open, slot 0 open, KeyValid 0, counter 0 at 0" +
          ("" if ok else " (%s)" % (ui.result,)))
    dismiss()
    press_d2()
    check(ui.result and ui.result[0] == "ready" and ui.result[1] and c.step() == "ready", "ready, D2: the same check again")
    dismiss()
    S.arm()
    for _ in range(3):
        press_d2()
        dismiss()
    check(not sim.keys and sim.cfg[86] == 0x55 and sim.cfg[88] == 0xFF and sim.counters[0] == 0,
          "after it all, armed and pressed again: no key, data zone open, no slot sealed, counter 0 at 0")
    check(not bad, "every line on the screen, none under the buttons' row" + (" (%s)" % bad[:3] if bad else ""))
    d.text = real
    log = open("prep-log.txt").read().splitlines()
    check(len(log) >= 5 and [l.split()[2] for l in log[:4]] == ["C1", "C2", "C3", "P4"] and all(" ok: " in l for l in log),
          "prep-log.txt: a line for each step, every one ok")
    s2, S2, K = as_image("console-rp")
    o = K.OwnKey(s2)
    check(o.step() == "K0" and rp_route() == "key", "the customer image takes it: the key flow, K0 first")
    o.run("K0")
    check(o.checked and all(k for _, k in o.checked), "and K0 finds it as P4 left it")

    # P4 on a chip with a key in slot 0 (written in while the data zone was open): not ready
    sim = prepared()
    sim.keys[0] = p256.rand_scalar()
    sim.save()
    s, S, PR = bench_image()
    c = PR.Ceremony(s)
    ok, checks, msg = c.run("P4")
    check(not ok and c.step() == "P4" and [l for l, k in checks if not k] == ["slot 0 empty (KeyValid 1)"],
          "P4 on a chip with a key in slot 0: not ready, and it says why")
    fresh_chip("608c")
    s, S, PR = bench_image(lock=False)
    c = PR.Ceremony(s)
    for st in ("C1", "C2"):
        c.run(st)
    S.arm()
    ok, checks, msg = c.run("C3")
    check(not ok and atecc_sim.chip().cfg[87] == 0x55, "no ALLOW_LOCK in the bench secrets.py: C3 refused, armed")
    no_files()


def main_rp():
    """console-rp's own key, in a device of its own: board.py read as console-rp."""
    with open("secrets.py", "w") as f:
        f.write('BOARD = "console-rp"\n')
    for m in ("board", "lcd", "splash", "bootmark"):
        sys.modules.pop(m, None)
    for case in (case_own_key_gate, case_own_key, case_prepare):
        print("--", case.__name__[5:])
        try:
            case()
        except Exception as e:
            failed[0] += 1
            print("FAIL  %s raised" % case.__name__)
            sys.print_exception(e)
    print("rp: %d failed" % failed[0])
    return failed[0]


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
    for case in (case_full, case_seal_gate, case_refusals, case_console, case_dual, case_ui, case_arm_left):
        print("--", case.__name__[5:])
        try:
            case()
        except Exception as e:
            failed[0] += 1
            print("FAIL  %s raised" % case.__name__)
            sys.print_exception(e)
    print("ceremony: %d failed" % failed[0])
    return failed[0]
