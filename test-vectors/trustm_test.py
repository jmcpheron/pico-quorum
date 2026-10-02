# The OPTIGA Trust M beside the ATECC608, on real MicroPython (WebAssembly) with the emulator's
# virtual Trust M (trustm_sim.py): which chip the board finds, the metadata and certificate of the
# real chip read on 2026-09-28, the quorum-tm1 ceremony (provision_tm.py) from a factory-fresh part
# to a sealed one, what must be refused, the console signing with the result and saying what the
# chip is while it does, and the dual image's choice. Run by test-vectors/run-trustm.mjs.
import sys, os, json, hashlib
import atecc_sim
import trustm_sim
import p256

failed = [0]


def check(ok, what):
    print(("pass  " if ok else "FAIL  ") + what)
    if not ok:
        failed[0] += 1


def secrets(lock=True, genkey=True, extra=""):
    with open("secrets.py", "w") as f:
        f.write('WIFI_SSID = "emulator"\nWIFI_PASS = ""\nHOSTNAME = "emu"\nALLOW_LOCK = %s\nALLOW_GENKEY = %s\n%s' % (lock, genkey, extra))
    try:
        os.remove("build.py")
    except OSError:
        pass
    for m in ("secrets", "build", "image", "signer", "provision", "provision_tm"):
        sys.modules.pop(m, None)


def only_trustm(fresh=True):
    trustm_sim.bus(trustm=True, atecc=False)
    if fresh:
        trustm_sim.wipe()
    for f in os.listdir():
        if f.startswith("snapshot-tm-") or f == "chips.json":
            os.remove(f)


def ceremony():
    import signer, provision_tm
    s = signer.TrustMSigner()
    return provision_tm.Ceremony(s), signer, provision_tm


def run(c, step, arm=True):
    import signer
    if arm:
        signer.arm()
    else:
        signer.disarm()
    got = c.step()
    ok, checks, msg = c.run(step)
    return got, ok, [l for l, k in checks if not k], msg


# ----------------------------------------------------------------------------- the real chip
# Read off the Adafruit 4351 on this board, 2026-09-28 (chips/trustm-0a091b5c000b0062006c-probe.txt)
REAL_UID = "cd16338401001c000100000a091b5c000b0062006c801010710809"
REAL_META = {
    0xE0F0: "200fc00101d001ffd30100e00103e10101",
    0xE0F1: "200bc00101d003e1fc07d30100",
    0xF1D0: "2011c00101c4018cc50164d003e1fc07d10100",
    0xE140: "201dc00101c40140c50140d007e1fc07fe20e140d103e1fc07d30100e80122",
    0xE0C5: "2009c40101d001ffd10100",
}
REAL_CERT = ("c001e20001df0001dc308201d83082017ea00302010202041d560a9b300a06082a8648ce3d0403023072310b30090603550406130244"
             "453121301f060355040a0c18496e66696e656f6e20546563686e6f6c6f6769657320414731133011060355040b0c0a4f5054494741"
             "28544d29312b302906035504030c22496e66696e656f6e204f505449474128544d29205472757374204d20434120313031301e170d"
             "3139303730313135303431345a170d3339303730313135303431345a301c311a301806035504030c11496e66696e656f6e20496f54"
             "204e6f64653059301306072a8648ce3d020106082a8648ce3d03010703420004eaf401d300d9dadbce9fbef2c782ffe3ac87c88ae7"
             "c32fb88a0893ef1b387acd876de8a19315cde4318416ede9f8e1879e32bdcb273f1daffd91a1bce58b2fa0a3583056300e0603551d"
             "0f0101ff040403020080300c0603551d130101ff0402300030150603551d20040e300c300a06082a82140044011401301f0603551d"
             "230418301680143c308c5cd58ae8a35d3280e45483b2ffcd864d23300a06082a8648ce3d04030203480030450220427b43282aa6bc"
             "3c586fe11cdca5649c3bd69cfde7a9eb38f2eb171e0be573a4022100b300cada9f40add28acf32107a726c78a275db6bb18a7eaef7"
             "a5996aced39b2a")


def case_real_chip():
    """tmcfg on the real chip's own bytes: the UID, the metadata, the Infineon certificate."""
    import tmcfg
    uid = bytes.fromhex(REAL_UID)
    check(tmcfg.serial(uid) == "0a091b5c000b0062006c", "serial: batch and wafer X/Y out of the UID")
    f = tmcfg.uid_fields(uid)
    check(f["build"] == "0809" and (f["x"], f["y"]) == (98, 108), "UID: firmware build 0809, wafer 98,108")
    k = tmcfg.parse_meta(bytes.fromhex(REAL_META[0xE0F1]))
    check(k["lcso"] == 1 and tmcfg.ac_text(k["change"]) == "LcsO<op" and tmcfg.ac_text(k["exec"]) == "ALW" and k["algo"] is None,
          "E0F1: creation, Change LcsO<op, Execute ALW, no key")
    e0 = tmcfg.parse_meta(bytes.fromhex(REAL_META[0xE0F0]))
    check(tmcfg.ac_text(e0["change"]) == "NEV" and e0["algo"] == 3 and e0["usage"] == 1, "E0F0: Change NEV, P-256, usage Auth")
    rec = tmcfg.parse_meta(bytes.fromhex(REAL_META[0xF1D0]))
    check(rec["max"] == 140 and rec["used"] == 100 and tmcfg.ac_text(rec["read"]) == "ALW", "F1D0: 140 bytes, 100 used, Read ALW")
    check(tmcfg.ac_text(tmcfg.parse_meta(bytes.fromhex(REAL_META[0xE140]))["change"]) == "LcsO<op || Conf(E140)",
          "E140: a compound condition reads as LcsO<op || Conf(E140)")
    check(tmcfg.identify(k, None) == "factory", "the real chip identifies as factory")
    der = tmcfg.cert_der(bytes.fromhex(REAL_CERT))
    c = tmcfg.cert_parse(der)
    check(c["issuer"] == "Infineon OPTIGA(TM) Trust M CA 101" and c["serial"] == "1d560a9b" and c["subject"] == "Infineon IoT Node",
          "the certificate: CA 101, serial 1d560a9b, Infineon IoT Node")
    ok, why = tmcfg.cert_check(c)
    check(ok, "the real certificate verifies under Infineon's CA 101 key, on MicroPython")
    bad = dict(c, tbs=c["tbs"][:-1] + bytes([c["tbs"][-1] ^ 1]))
    check(not tmcfg.cert_check(bad)[0], "one bit changed in the signed part: refused")
    check(tmcfg.ca_key("Infineon OPTIGA(TM) Trust M CA 999") is None, "an issuer not pinned: no key")


# ----------------------------------------------------------------------------- detection
def case_detect():
    import signer
    trustm_sim.bus(trustm=False, atecc=True)
    check(signer.detect() == [("atecc608", 0x60)], "ATECC alone: detected as before")
    only_trustm()
    check(signer.detect() == [("trustm", 0x30)], "Trust M alone: found though scan() does not list it (asleep, it NACKs)")
    s = signer.load(soft=False)
    check(s.name == "trustm" and signer.is_chip(s) and s.profile() == "factory", "Trust M alone: load() gives a TrustMSigner, factory")
    trustm_sim.bus(trustm=True, atecc=True)
    check([k for k, _ in signer.detect()] == ["atecc608", "trustm"], "both: both detected")
    check(signer.load(soft=False).name == "atecc608", "both, none pinned: the ATECC, as before the Trust M")
    tm = tmcfg_serial()
    check(signer.load(soft=False, pins=[{"serial": tm}]).name == "trustm", "both, the Trust M pinned: the Trust M")
    trustm_sim.bus(trustm=False, atecc=False)
    check(signer.detect() == [] and signer.load(soft=False).name == "none", "neither: NoSigner")
    trustm_sim.bus(trustm=False, atecc=True)


def tmcfg_serial():
    import tmcfg
    return tmcfg.serial(trustm_sim.chip().uid)


# ----------------------------------------------------------------------------- the ceremony
def case_full():
    secrets()
    only_trustm()
    c, S, P = ceremony()
    sim = trustm_sim.chip()
    for want in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"):
        got, ok, bad, msg = run(c, want)
        check(got == want and ok, "%s %s%s" % (want, P.TITLES[want], "" if ok and got == want else " (step %s, %s, %s)" % (got, bad, msg)))
    check(all(sim.objs[o]["meta"]["lcso"] == 0x07 for o in (0xE0F1, 0xF1D0, 0xF1D1)), "E0F1, F1D0, F1D1 operational")
    import tmcfg
    rec = tmcfg.record_decode(sim.objs[0xF1D0]["data"])
    x, y = p256.pubkey(sim.objs[0xE0F1]["key"])
    check(rec and (rec["qx"], rec["qy"]) == (x, y) and rec["owner"] == c.owner(), "F1D0 names the key made in E0F1, and its owner")
    der = tmcfg.cert_der(sim.objs[0xE0E0]["data"])
    check(tmcfg.binding_check(tmcfg.binding_decode(sim.objs[0xF1D1]["data"]), der, tmcfg.cert_parse(der), sim.uid, 0xE0F1, x, y),
          "F1D1: E0F0's signature binds this key to this chip's certificate")
    import chips
    e = chips.load().get(c.serial) or {}
    check(e.get("profile") == "quorum-tm1" and e.get("kind") == "trustm" and e.get("owner") == rec["owner"],
          "chips.json has it as a quorum-tm1 Trust M, with its owner")
    check(c.step() == "T10", "a finished chip stays at T10")
    c2 = ceremony()[0]
    check(c2.step() == "T8" and run(c2, "T8")[1] and c2.step() == "T10", "a reboot: T8 checks the seal again, then straight to T10")
    check(all(sim.objs[o]["meta"]["lcso"] == 0x07 for o in tmcfg.SPARES), "T9: every spare (%d) operational" % len(tmcfg.SPARES))
    check(all(sim.objs[o]["meta"]["change"] == b"\xe1\xfc\x07" for o in tmcfg.SPARES), "T9 wrote only LcsO: every Change condition as it came")
    check(sim.objs[0xE140]["meta"]["lcso"] == 1 and sim.objs[0xE140]["data"] == bytes(64), "E140 (the binding secret) untouched")
    snap = json.load(open(P.snapshot_path(c.serial)))
    check(all("%04X" % o in snap["metadata"] for o in tmcfg.SPARES) and snap["metadata"]["E0F1"].startswith("20"),
          "T1's snapshot has every object's factory metadata, the 23 spares too")
    log = json.load(open(P.steps_path(c.serial)))
    t9 = [e for e in log if e["step"] == "T9"][-1]
    check([e["step"] for e in log][:10] == ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"] and all(e["ok"] for e in log[:10]),
          "the steps log has every step's result, in order")
    check(len(t9["metaBefore"]) == 23 and all(tmcfg.parse_meta(bytes.fromhex(t9["metaAfter"][k]))["lcso"] == 7 for k in t9["metaAfter"])
          and all(tmcfg.parse_meta(bytes.fromhex(v))["lcso"] == 1 for v in t9["metaBefore"].values()) and t9["refused"] == []
          and "secBefore" in t9 and t9["ms"] >= 0, "T9's entry keeps each spare's metadata before and after, the counter and the time")
    check(sim.objs[0xE0F0].get("key") and sim.objs[0xE0F0]["meta"]["lcso"] == 1 and tmcfg.cert_der(sim.objs[0xE0E0]["data"]) == der,
          "the factory key and certificate are untouched")


def case_resume():
    """A reboot at any point: the chip, not the session, says where the ceremony is."""
    secrets()
    only_trustm()
    c, S, P = ceremony()
    run(c, "T1")
    check(ceremony()[0].step() == "T2", "after T1, a reboot: T2 (the snapshot is on flash)")
    run(c, "T2")
    check(ceremony()[0].step() == "T2", "after T2, a reboot: T2 again (a Trust M gives a key's public half only at GenKeyPair)")
    for st in ("T3", "T4", "T5", "T6"):
        run(c, st)
    c2 = ceremony()[0]
    check(c2.step() == "T3" and c2.key == c.key, "after T6, a reboot: T3 with the key from the record (T3 proves they match)")
    for st in ("T3", "T4", "T5", "T6", "T7"):
        got, ok, bad, msg = run(c2, st)
        check(got == st and ok, "resumed %s %s" % (st, "" if ok else (bad, msg)))
    check(ceremony()[0].step() == "T8", "sealed: a reboot goes straight to T8")
    # started elsewhere (the laptop, 2026-09-28): key and record on the chip, no snapshot on this board
    secrets()
    only_trustm()
    c, S, P = ceremony()
    for st in ("T1", "T2", "T3", "T4", "T5", "T6"):
        run(c, st)
    for f in os.listdir():
        if f.startswith("snapshot-tm-"):
            os.remove(f)
    c3 = ceremony()[0]
    got, ok, bad, msg = run(c3, "T1")
    check(got == "T1" and ok and "resuming" in msg, "a ceremony started elsewhere: T1 accepts our own key and record (%s)" % (bad or msg))
    check(c3.step() == "T3" and c3.key == c.key, "and resumes at T3 with the record's key")
    trustm_sim.chip().objs[0xF1D0]["data"] = bytes(100)       # a key but no record: not ours
    trustm_sim.chip().save()
    for f in os.listdir():
        if f.startswith("snapshot-tm-"):
            os.remove(f)
    got, ok, bad, msg = run(ceremony()[0], "T1")
    check(not ok, "a key in E0F1 without our record: T1 stops")


def case_gates():
    """What the ceremony and the chip refuse."""
    import tmcfg
    secrets(lock=False, genkey=False)
    only_trustm()
    c, S, P = ceremony()
    run(c, "T1")
    got, ok, bad, msg = run(c, "T2")
    check(not ok and "ALLOW_GENKEY" in msg and trustm_sim.chip().objs[0xE0F1].get("key") is None, "T2 without ALLOW_GENKEY: no key")
    secrets(lock=False, genkey=True)
    c, S, P = ceremony()
    got, ok, bad, msg = run(c, "T2", arm=False)
    check(not ok and "not armed" in msg, "T2 not armed: refused")
    for st in ("T2", "T3", "T4", "T5", "T6"):
        run(c, st)
    got, ok, bad, msg = run(c, "T7")
    check(not ok and "ALLOW_LOCK" in msg and trustm_sim.chip().objs[0xE0F1]["meta"]["lcso"] == 1, "T7 without ALLOW_LOCK: nothing sealed")
    secrets()
    c2, S, P = ceremony()
    for st in ("T3", "T4", "T5", "T6", "T7"):
        run(c2, st)
    chip = c2.chip

    def refused(fn):
        try:
            fn()
            return False
        except Exception as e:
            return "failed" in str(e)
    rec = bytes(chip.get(tmcfg.RECORD))
    check(refused(lambda: chip.set_data(tmcfg.RECORD, rec)), "sealed: F1D0 cannot be written, not even with the same bytes")
    check(refused(lambda: chip.gen_keypair(tmcfg.KEY)), "sealed: GenKeyPair on E0F1 refused (as modeled)")
    check(refused(lambda: chip.set_lifecycle(tmcfg.KEY, 0x03)), "sealed: the lifecycle cannot go back down")
    check(bytes(chip.get(tmcfg.RECORD)) == rec, "and the record is as it was")
    secrets(lock=False)
    c4, S, P = ceremony()
    run(c4, "T8")
    got, ok, bad, msg = run(c4, "T9")
    check(got == "T9" and not ok and "ALLOW_LOCK" in msg and c4.sig.spares_open(), "T9 without ALLOW_LOCK: nothing frozen")
    secrets()
    c4, S, P = ceremony()
    run(c4, "T8")
    got, ok, bad, msg = run(c4, "T9", arm=False)
    check(not ok and "not armed" in msg and c4.sig.spares_open(), "T9 not armed: nothing frozen")
    got, ok, bad, msg = run(c4, "T9")
    check(ok and not c4.sig.spares_open(), "T9 armed: every spare frozen (%s)" % msg)
    check(refused(lambda: chip.set_data(0xF1D2, b"config")), "frozen: a spare data object cannot be written")
    check(refused(lambda: chip.gen_keypair(0xE0F2)), "frozen: no key can be made in E0F2")
    check(refused(lambda: chip.set_lifecycle(0xF1D3, 0x03)), "frozen: a spare's lifecycle cannot go back down")
    def code(fn):
        try:
            fn()
        except Exception as e:
            return str(e)[-3:-1]
    check(code(lambda: chip.set_lifecycle(0xF1D3, 0x03)) == "05" and code(lambda: chip.gen_keypair(0xE0F2)) == "07"
          and code(lambda: chip.set_data(0xF1D2, b"x")) == "07"
          and code(lambda: chip.command(0x02, 0x01, (0xF1D4).to_bytes(2, "big") + b"\x00\x00" + bytes([0x20, 3, 0xD0, 1, 0x00]), retry=False)) == "07",
          "the error codes TM2 gave: 05 lowering a lifecycle, 07 for every other refused write")
    only_trustm()
    c3, S, P = ceremony()
    trustm_sim.chip().sec = 40
    trustm_sim.chip().save()
    c3.read()
    got, ok, bad, msg = run(c3, "T1")
    check(not ok and any("security events" in b for b in bad), "T1 on a chip with security events: stop")


def case_keep_open():
    """TRUSTM_KEEP_OPEN leaves a spare open (a data object kept for a later config record)."""
    import tmcfg
    secrets(extra='TRUSTM_KEEP_OPEN = ["F1D2"]\n')
    only_trustm()
    c, S, P = ceremony()
    for st in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"):
        run(c, st)
    check("F1D2" in c.WHAT["T9"], "the T9 screen names what is kept open")
    got, ok, bad, msg = run(c, "T9")
    sim = trustm_sim.chip()
    check(ok and sim.objs[0xF1D2]["meta"]["lcso"] == 1 and all(sim.objs[o]["meta"]["lcso"] == 7 for o in tmcfg.SPARES if o != 0xF1D2),
          "T9 freezes every spare but F1D2 (%s)" % msg)
    check(c.step() == "T10" and run(c, "T10")[1], "and the ceremony finishes with F1D2 kept open")
    c.chip.set_data(0xF1D2, b"later")
    check(bytes(c.chip.get(0xF1D2))[:5] == b"later", "F1D2 can still be written")
    secrets()
    c2 = ceremony()[0]
    check(c2.step() == "T8" and run(c2, "T8")[1] and c2.step() == "T9", "without TRUSTM_KEEP_OPEN it is open again: T9 offers to freeze it")


def case_other():
    """E0F1 sealed by someone else: not ours, the ceremony stops."""
    secrets()
    only_trustm()
    sim = trustm_sim.chip()
    sim.objs[0xE0F1]["meta"]["lcso"] = 0x07
    sim.save()
    c, S, P = ceremony()
    check(c.step() == "other" and c.profile == "unknown", "a sealed E0F1 without a record: other")


# ----------------------------------------------------------------------------- the console
def console(pin=True, owner=None, keep=False, atecc=True):
    sys.path.insert(0, "/")
    import console_test as T
    import tmcfg
    trustm_sim.bus(trustm=True, atecc=atecc)
    rec = tmcfg.record_decode(trustm_sim.chip().objs[0xF1D0]["data"])
    exp = {"serial": tmcfg.serial(trustm_sim.chip().uid), "slot": 0xE0F1, "owner": owner or rec["owner"], "locked": True,
           "chip": "trustm"} if pin else None
    return T, T.fresh(expect=exp, keep=keep)


def case_console():
    import quorum_ui
    only_trustm()
    trustm_sim.seal_as_quorum()
    T, Q = console()
    check(Q.state == "home" and Q.pin_ok and Q.sig.name == "trustm", "the console accepts the sealed Trust M it is pinned to (ATECC also on the bus)")
    check(Q.row["locked"] and Q.row["kind"] == "P256" and Q.counter is None and Q.profile == "quorum-tm1",
          "E0F1 reads as a sealed P-256 key, no use counter, quorum-tm1")
    check(Q.sig.bound is True, "the factory binding checked at boot")
    check(Q.slot_label() == "E0F1" and Q.sec is not None, "the Device screen's slot E0F1 and the security event count")
    seen = []
    real_draw = quorum_ui.draw_working

    def spy(q, title, sub):
        seen.append((title, list(q.work_info)))
        return real_draw(q, title, sub)
    quorum_ui.draw_working = spy
    sigs = []
    real_sign = Q.sig.sign

    def spy_sign(digest, slot=None):
        r, s = real_sign(digest, slot)
        sigs.append((digest, r, s))
        return r, s
    Q.sig.sign = spy_sign
    try:
        T.serve(Q, [T.tx(Q, 0), T.tx(Q, 1)])
        ok1 = T.sign(Q, Q.queue[0], 2100)
        T.serve(Q, [T.tx(Q, 1)])
        ok2 = T.sign(Q, Q.queue[0], 2100)
    finally:
        quorum_ui.draw_working = real_draw
    check(ok1 and ok2 and len(T.SVC.posted) == 2, "two signatures, both sent")
    x, y = Q.sig.pubkey()
    check(all(p256.verify(x, y, d, r, s) and s <= p256.N // 2 for d, r, s in sigs), "every signature verifies and has low s")
    sign_info = [i for t, i in seen if t == "Signing"]
    check(sign_info and any("Infineon OPTIGA Trust M" in l for l in sign_info[0]) and any("E0F1" in l and "sealed" in l for l in sign_info[0])
          and any("Bound to Infineon cert" in l for l in sign_info[0]) and any("Security event counter:" in l for l in sign_info[0]),
          "the Signing screen says what the chip is: Infineon Trust M, E0F1 sealed, the factory binding, its security events")
    sent_info = [i for t, i in seen if t == "Sending"]
    check(sent_info and any(l.startswith("Signed in") and "E0F1" in l for l in sent_info[0])
          and any(l.startswith("Security events:") and ("unchanged" in l or "+1" in l) for l in sent_info[0]),
          "the Sending screen: signed by E0F1 in n ms, and the counter after it (unchanged from idle credit, or +1)")
    check(not Q.work_info, "the lines are cleared after signing")
    # a security event during a signature: flagged on the result
    sim = trustm_sim.chip()
    real_calc = sim.calc_sign

    def noisy(param, data):
        sim.sec_event()                     # two suspect events besides the signature: more than
        sim.sec_event()                     # one signature can explain, credit or not
        return real_calc(param, data)
    sim.calc_sign = noisy
    try:
        T.serve(Q, [T.tx(Q, 2)])
        T.sign(Q, Q.queue[0], 2100)
    finally:
        sim.calc_sign = real_calc
    check(Q.result and Q.result[0] and any("besides this signature" in l for l in Q.result[2]),
          "the chip counted more than the signature itself: the result says so")
    # The console read the counter when it signed; the chip takes one count off every 5 s of wall
    # time, so one tick may have passed by now (it did once the factory checks were remembered and
    # the boot got faster). Anything else is wrong.
    _now = sim.sec_now()
    check(Q.sec in (_now, _now + 1), "and the Device screen shows the new count (%s, the chip now %s)" % (Q.sec, _now))


def case_proof():
    """The factory checks (two P-256 verifies) pass once and are remembered by the hash of the
    bytes they read (tmcfg.proof): the same bytes skip the math; one changed byte runs both again,
    and a failure is never remembered."""
    import signer, tmcfg
    only_trustm()
    trustm_sim.seal_as_quorum()
    try:
        os.remove(tmcfg.PROOF_FILE)
    except OSError:
        pass
    calls = [0]
    real = p256.verify

    def counted(*a):
        calls[0] += 1
        return real(*a)
    p256.verify = counted
    sim = trustm_sim.chip()
    saved = sim.objs[0xF1D1]["data"]
    try:
        s = signer.TrustMSigner()
        check(s.binding_ok() is True and s.ca_ok and not s.remembered and calls[0] == 2,
              "first boot: both verifies run and pass, and the pass is remembered")
        calls[0] = 0
        s = signer.TrustMSigner()
        check(s.binding_ok() is True and s.ca_ok and s.remembered and calls[0] == 0,
              "next boot, the same bytes: the pass is remembered, no verify")
        b = bytearray(saved)
        b[10] ^= 1                          # one bit of E0F0's signature
        sim.objs[0xF1D1]["data"] = bytes(b)
        calls[0] = 0
        s = signer.TrustMSigner()
        check(s.binding_ok() is False and not s.remembered and calls[0] == 2,
              "one bit of F1D1 changed: both checks run again, and the binding fails")
        calls[0] = 0
        s = signer.TrustMSigner()
        check(s.binding_ok() is False and calls[0] == 2, "and the failure is not remembered: checked again on the next boot")
        sim.objs[0xF1D1]["data"] = saved
        calls[0] = 0
        s = signer.TrustMSigner()
        check(s.binding_ok() is True and s.remembered and calls[0] == 0, "the original bytes back: remembered again")
    finally:
        p256.verify = real
        sim.objs[0xF1D1]["data"] = saved


def case_chip_pages():
    """Device -> Chip: the silicon, the factory certificate, the signing key, read off the chip,
    and on an ATECC its own page. Buttons and the knob both get there and back."""
    import quorum_ui
    only_trustm()
    trustm_sim.seal_as_quorum()
    T, Q = console()
    check(Q.sig.ca_ok is True and Q.sig.bound is True, "at boot: the certificate chains to the (emulator) CA, and the binding verifies")
    Q.handle("X")
    check(Q.state == "device", "X: the Device screen")
    quorum_ui.draw(Q)
    Q.handle("A")
    titles = []
    for t, _ in Q.chip_pages:
        if t not in titles:
            titles.append(t)
    check(Q.state == "chip" and titles == ["The chip", "Factory certificate", "Signing key"],
          "A on Device: the Chip pages (the chip, its factory certificate, the signing key)")
    pages = {}
    for t, r in Q.chip_pages:
        pages.setdefault(t, {}).update(dict(r))
    check(sum(len(r) for _, r in Q.chip_pages) == 8 + 6 + 7, "every row is on a page (long ones continue on the next): nothing cut")
    check(pages["The chip"]["Spares"].startswith("0 of 23 frozen; open E0E1 E0E8 E0EF E0F2 E0F3 E0FC +17"), "page 1: the spares, read off the chip (%s)" % pages["The chip"]["Spares"])
    check(pages["The chip"]["Part"] == "Infineon OPTIGA Trust M" and "CC EAL6+" in pages["The chip"]["Certified"],
          "page 1: Infineon OPTIGA Trust M, CC EAL6+")
    c = pages["Factory certificate"]
    check(c["Issuer"] == "PicoQuorum emulator CA (not Infineon)" and c["Valid"] == "2019-07-01 to 2039-07-01"
          and c["CA check"].startswith("verified"), "page 2: issuer, validity, the CA check done on the Pico")
    k = pages["Signing key"]
    check(k["Key"].startswith("E0F1") and k["Sealed"].startswith("yes") and k["Binding"].startswith("E0F0 signed")
          and k["Owner"] == Q.me, "page 3: E0F1 sealed, the factory binding, the owner")
    ok = True
    n = len(Q.chip_pages)
    for i in range(n):
        try:
            quorum_ui.draw(Q)
        except Exception as e:
            sys.print_exception(e)
            ok = False
        Q.handle("A")
    check(ok and Q.chip_page == 0, "every page draws; A pages through and wraps round (%d pages)" % n)
    Q.handle("B")
    check(Q.state == "device", "B: back to Device")
    Q.KNOB = True
    Q.knob("down")
    check(Q.dfoot == "back", "knob on Device: a turn chooses Back")
    Q.knob("up")
    Q.knob("press")
    check(Q.state == "chip", "knob: press on Chip opens the pages")
    for _ in range(len(Q.chip_pages) + 2):
        Q.knob("down")
    check(Q.chip_page == len(Q.chip_pages) - 1, "knob: turning pages, stopping at the last")
    Q.knob("press")
    check(Q.state == "device", "knob: press goes back to Device")
    Q.KNOB = False
    trustm_sim.bus(trustm=False, atecc=True)
    atecc_sim.provision_v1()
    import quorum_cfg, webauthn
    x, y = p256.pubkey(atecc_sim.chip().keys[0])
    owner = webauthn.owner_address("0x%064x" % x, "0x%064x" % y, quorum_cfg.CFG["signer"])
    Q = T.fresh(expect={"serial": T.SERIAL, "slot": 0, "owner": owner, "locked": True})
    Q.handle("X")
    Q.handle("A")
    rows = dict(Q.chip_pages[0][1])
    check(Q.state == "chip" and rows["Part"].startswith("Microchip ATECC608") and "sealed" in rows["Key"],
          "on an ATECC: its own Chip page (part, config, sealed slot 0)")
    quorum_ui.draw(Q)


def case_sec():
    """The security event counter as the real chip counts it: key uses paid from an idle credit
    first, then +1 each (2026-09-28: after idle, 8 signatures left it at 0, then it climbed)."""
    import hashlib, signer
    only_trustm()
    trustm_sim.seal_as_quorum()
    s = signer.load(soft=False)
    sim = trustm_sim.chip()
    import time
    sim.sec, sim.credit, sim.sec_t = 0, 3, time.ticks_ms()     # the clock too: idle time earns credit
    d = hashlib.sha256(b"sec").digest()
    seen = []
    for _ in range(5):
        s.sign(d)
        seen.append(s.sec())
    check(seen == [0, 0, 0, 1, 2], "three signatures from the idle credit, then +1 each (%r)" % seen)


def case_console_pin():
    only_trustm()
    trustm_sim.seal_as_quorum()
    T, Q = console(owner="0x" + "12" * 20)
    check(Q.state == "pinfail" and "owner" in Q.pin_why, "a Trust M whose record names another owner than the pin: nothing signed")
    T, Q = console(pin=False, atecc=False)
    check(Q.state == "pinfail", "the production console with no pin: nothing signed")
    only_trustm()                           # factory-fresh, no record
    T, Q = console(pin=False, atecc=False)
    check(Q.state == "pinfail" and not Q.qx, "a fresh Trust M: no key, not pinned")


def case_dual():
    import tmcfg

    def boot(expect=None, lock=True):
        secrets(lock=lock)
        with open("secrets.py", "a") as f:
            if expect:
                f.write("QUORUM_EXPECT = %r\n" % expect)
        with open("build.py", "w") as f:
            f.write('IMAGE = "dual"\nBUILD = "test"\nDATE = 0\n')
        for m in ("build", "image", "main_dual"):
            sys.modules.pop(m, None)
        import main_dual
        return main_dual
    only_trustm()
    D = boot()
    w = D.which()
    check(w[0] == "ceremony" and w[2] == "factory", "dual, a fresh Trust M: the ceremony")
    c, S, P = ceremony()
    for st in ("T1", "T2", "T3"):
        run(c, st)
    check(D.which()[0] == "ceremony", "dual, a Trust M half way (key made, not sealed): the ceremony again")
    only_trustm()
    trustm_sim.seal_as_quorum()
    D = boot(lock=False)
    check(D.which()[0] == "console", "dual, a sealed Trust M, not pinned yet: the console (it says Not pinned)")
    D = boot()
    check(D.which()[0] == "ceremony", "dual, a sealed Trust M with its spares open, ALLOW_LOCK on, not pinned: the ceremony (T9)")
    rec = tmcfg.record_decode(trustm_sim.chip().objs[0xF1D0]["data"])
    D = boot({"serial": tmcfg.serial(trustm_sim.chip().uid), "slot": 0xE0F1, "owner": rec["owner"], "locked": True})
    check(D.which()[0] == "console", "dual, the pinned Trust M: the console, ALLOW_LOCK or not")
    sim = trustm_sim.chip()
    for o in tmcfg.SPARES:
        sim.objs[o]["meta"]["lcso"] = 7
    sim.save()
    D = boot()
    check(D.which()[0] == "console", "dual, sealed and its spares frozen, not pinned: the console")
    os.remove("build.py")


def case_ui():
    """Every Trust M step's screen draws, and the object map."""
    import splash, provision
    secrets()
    only_trustm()
    c, S, P = ceremony()

    class K:
        def held(self, k):
            return False
    d = splash.begin()
    ui = provision.UI(d, K(), c.sig, "light", c)
    ok = True
    for st in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"):
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
    check(ok and ui.c.step() == "T10", "the ceremony screen draws every Trust M step and its result")
    only_trustm()
    c2, S2, P2 = ceremony()
    for st in ("T1", "T2", "T3", "T4"):
        run(c2, st)
    check(c2.picture("T5") is None, "T5 before the owner is shown: no picture on the step screen yet")
    run(c2, "T5")
    own = c2.owner().lower()
    check(c2.picture("T5", True) == own and c2.picture("T6") == own and c2.picture("T1") is None,
          "after T5: the owner's blockie seed is the lowercase owner address, on T5-T7 only")
    import blockies
    check(blockies.build(own, 8) == blockies.build(c2.owner().lower(), 8), "same address, same picture")
    try:
        P.draw_map(d, c.sig, provision.palette("dark"))
        check(True, "the Trust M object map draws")
    except Exception as e:
        sys.print_exception(e)
        check(False, "the Trust M object map draws")


def case_knob():
    """Build 1 has a knob, not A/B/X/Y: turn to choose, press to act, one 3 s hold arms and a second
    does a gated step. Every screen goes out strip by strip (d.frames), or a 320x240 panel stays black."""
    import splash, time
    secrets()
    only_trustm()
    c, S, P = ceremony()
    import provision                        # after secrets(): the same signer module as S
    S.disarm()

    class K:
        down = False

        def held(self, k):
            return k == "press" and self.down
    keys = K()
    d = splash.begin()
    framed = [0]
    real = d.frames

    def frames(fn, *a):
        framed[0] += 1
        return real(fn, *a)
    d.frames = frames
    ui = provision.UI(d, keys, c.sig, "dark", c)
    ui.knob = True
    ui.draw()
    check(framed[0] == 1, "the step screen is drawn through d.frames (every strip of a 320x240 panel)")
    ui.tick(["press"])
    check(ui.result and ui.result[0] == "T1" and ui.result[1] and framed[0] >= 2, "press: T1 runs (its working screen framed too)")
    ui.tick(["press"])
    check(ui.result is None and c.step() == "T2", "press again: back to the steps, at T2")

    def hold():
        keys.down = True
        ui.tick([])
        ui.hold = time.ticks_add(time.ticks_ms(), -3100)
        ui.tick([])
        keys.down = False
        ui.tick([])
    ui.tick(["press"])                      # a tap on a gated step does nothing
    check(ui.result is None and trustm_sim.chip().objs[0xE0F1].get("key") is None, "a tap on T2: nothing")
    hold()
    check(S.armed() > 0 and ui.result is None and trustm_sim.chip().objs[0xE0F1].get("key") is None, "the first 3 s hold arms, and makes no key")
    hold()
    check(ui.result and ui.result[0] == "T2" and ui.result[1] and trustm_sim.chip().objs[0xE0F1].get("key"), "the second 3 s hold does T2")
    ui.tick(["press"])
    ui.tick(["down"])
    check(ui.choice == 1, "a turn: back is chosen")
    check(ui.tick(["press"]) == "back", "press on back: leaves the ceremony")
    import chipapp
    chipapp.d, chipapp.keys, chipapp.sig = d, keys, c.sig
    chipapp.identify()
    before = framed[0]
    chipapp.banner()
    check(framed[0] == before + 1 and [w for _, w in chipapp.choices()] == ["prov", "map"], "the banner is framed; PROVISION and the objects")
    chipapp.open_choice("map")
    check(framed[0] == before + 2 and chipapp.ui == "map", "the object map is framed")
    chipapp.ui = None


def main():
    for case in (case_real_chip, case_detect, case_full, case_resume, case_gates, case_keep_open, case_other, case_console, case_proof, case_chip_pages, case_sec,
                 case_console_pin, case_dual, case_ui, case_knob):
        print("--", case.__name__[5:])
        try:
            case()
        except Exception as e:
            failed[0] += 1
            print("FAIL  %s raised" % case.__name__)
            sys.print_exception(e)
    trustm_sim.bus(trustm=False, atecc=True)
    print("trustm: %d failed" % failed[0])
    return failed[0]
