# The provisioning ceremony for a fresh OPTIGA Trust M: PicoQuorum's profile quorum-tm1 (tmcfg.py;
# the reasoning and the runbook are in docs/TRUSTM.md). The same screen as the ATECC's
# (provision.UI); the step is worked out from the chip and this session every time.
#
#   T1  pre-flight: read-only checks; the factory certificate verified against Infineon's CA, the
#       factory key shown to match it; every object's metadata saved as snapshot-tm-<serial>.json
#   T2  GenKeyPair in E0F1: a new P-256 key (replaceable until T7)
#   T3  test signatures (a plain digest and a WebAuthn assertion), verified here
#   T4  the binding: the factory key E0F0 signs "this chip holds this key", verified here
#   T5  the owner address this key gets on the Safe, to compare on the laptop
#   T6  the record into F1D0 and the binding into F1D1, read back (rewritable until T7)
#   T7  seal: LcsO of F1D1, F1D0 and E0F1 raised to operational                       PERMANENT
#   T8  the seal checked: record, binding, the key still signs
#   T9  freeze the spares: LcsO operational on every object the profile does not use      PERMANENT
#       (tmcfg.SPARES; any named in secrets.TRUSTM_KEEP_OPEN are left open)
#   T10 final checks and the summary
#
# T7 and T9 need ALLOW_LOCK (T2 ALLOW_GENKEY) in secrets.py, the B+Y arm and A held 3 s, as on the
# ATECC. A chip sealed before T9 existed comes back at T8, then T9. Nothing here writes to E0F0,
# E0E0 or E140, nothing but LcsO is ever written outside E0F1, F1D0 and F1D1, no lifecycle goes to
# termination, and nothing tries a write that a sealed or factory object should refuse: a refusal
# test that failed would destroy what it tested. Logic (Ceremony) and screen (provision.UI) are apart so
# test-vectors/trustm_test.py walks the whole thing on the virtual chip.
import time
import hashlib
import json
import os
import tmcfg
import signer as S
import p256

PERMANENT = ("T7", "T9")
SEC_CALM = 16       # the security event counter below this: nothing but recent key uses (each is one, ~5 s each to fade)
TITLES = {"T1": "Pre-flight", "T2": "Make the key", "T3": "Test signatures", "T4": "Bind to the chip",
          "T5": "Owner address", "T6": "Record + binding", "T7": "Seal", "T8": "Sealed", "T9": "Freeze the spares", "T10": "Done",
          "other": "Not a fresh chip"}
WHAT = {
    "T1": "Reads the chip, checks its Infineon certificate and saves every object's metadata. Changes nothing.",
    "T2": "Makes a new P-256 key inside the chip, in E0F1. Until T7 it can be made again.",
    "T3": "Signs two test digests with the new key and checks both here.",
    "T4": "The factory key E0F0, certified by Infineon, signs 'this chip holds this key'. Checked here.",
    "T5": "The address this key gets as a Safe owner. Compare it on the laptop (getSigner) before T6.",
    "T6": "Writes the record (F1D0) and the binding (F1D1) and reads both back. Rewritable until T7.",
    "T7": "Raises the lifecycle of F1D1, F1D0 and E0F1 to operational: the key and both records are frozen for good.",
    "T8": "Checks the seal: the record, the binding, and that the key still signs. Changes nothing.",
    "T9": "Raises the lifecycle of every object the Safe key does not use to operational: nothing else on the chip can ever be written or get a key.",
    "T10": "Done. Enroll the owner address, then add it to the Safe.",
    "other": "E0F1 is sealed but holds no PicoQuorum record. The ceremony is for fresh chips.",
}


def snapshot_path(serial):
    return "snapshot-tm-%s.json" % serial


def steps_path(serial):
    """Every step's result on this board, newest last: what the screens showed, for the inventory
    and docs/TRUSTM.md. Kept across pushes like the snapshot (manifest "preserve")."""
    return "snapshot-tm-%s-steps.json" % serial


def _hex(b):
    return "".join("%02x" % x for x in b)


def seal(sig):
    """PERMANENT. LcsO operational on the binding, the record, then the key. Needs ALLOW_LOCK and
    the arm. A lifecycle state never goes down."""
    if not S._allowed("ALLOW_LOCK"):
        raise Exception(S._refused("lock"))
    for oid in (tmcfg.BINDING, tmcfg.RECORD, tmcfg.KEY):
        if sig.chip.meta(oid)["lcso"] != tmcfg.OPERATIONAL:
            sig.chip.set_lifecycle(oid)
    sig.forget()
    return "sealed: F1D1, F1D0, E0F1 operational"


def freeze(sig, oids):
    """PERMANENT. LcsO operational on each of oids (spares T9 found open: below operational, Change
    LcsO<op). Only LcsO is written, never termination. Needs ALLOW_LOCK and the arm. -> the OIDs
    the chip refused, with why."""
    if not S._allowed("ALLOW_LOCK"):
        raise Exception(S._refused("lock"))
    refused = []
    for oid in oids:
        if tmcfg.spare_state(sig.chip.meta(oid)) != "open":
            continue                    # read again just before: only an object still as it came
        try:
            sig.chip.set_lifecycle(oid)
        except OSError as e:
            refused.append((oid, str(e)))
    return refused


class Ceremony:
    HEADER = "PROVISION Trust M"
    NSTEPS = 10
    PERMANENT = PERMANENT
    GENKEY = ("T2",)
    FINAL = ("T10", "other")
    TITLES = TITLES
    WHAT = WHAT

    def __init__(self, sig):
        self.sig = sig
        self.chip = sig.chip
        self.newkey = None          # T2's key this session (a Trust M gives it only at GenKeyPair)
        self.tested = False         # T3 passed this session
        self.binding = None         # T4's (r, s) this session
        self.owner_seen = False     # T5 was shown this session
        self.written = False        # T6 wrote and read back this session
        self.checked = False        # T8 passed this session: the seal checked before T9
        self.extra = None           # what the step running now keeps for the steps log (T9: the metadata)
        self.read()

    def index(self, st):
        return int(st[1:]) if st[0] == "T" else 0

    def picture(self, st, result=False):
        """The owner address's blockie (blockies.py), lowercase as the seed: on T5's result, and
        on the steps that follow it while the key can still be looked at."""
        if not self.key or st not in ("T5", "T6", "T7"):
            return None
        if st == "T5" and not result and not self.owner_seen:
            return None
        return self.owner().lower()

    def subtitle(self):
        f = tmcfg.uid_fields(self.uid)
        return "%s fw %s" % (self.serial[-12:], f["build"])

    def note(self):
        return "security events: %d" % self.sec if self.sec is not None else ""

    # --- where the chip is ---------------------------------------------------------
    def read(self):
        c = self.chip
        self.sig.forget()
        self.uid = c.uid()
        self.serial = tmcfg.serial(self.uid)
        self.meta = {oid: c.meta(oid) for oid in (tmcfg.KEY, tmcfg.RECORD, tmcfg.BINDING)}
        self.rec = tmcfg.record_decode(c.get(tmcfg.RECORD))
        self.profile = tmcfg.identify(self.meta[tmcfg.KEY], self.rec)
        self.sealed = self.meta[tmcfg.KEY]["lcso"] == tmcfg.OPERATIONAL
        try:
            self.sec = c.sec()
        except Exception:
            self.sec = None
        # the key: this session's, else the record's while E0F1 holds one (T3 proves they match)
        self.key = self.newkey
        if self.key is None and self.rec and self.meta[tmcfg.KEY]["algo"] is not None:
            self.key = (self.rec["qx"], self.rec["qy"])
        # the spares, once sealed (23 metadata reads): which T9 would freeze
        self.spares = self.sig.spares() if self.sealed and self.rec else {}
        self.open = [o for o, st in self.spares.items() if st == "open"]
        kept = ["%04X" % o for o, st in self.spares.items() if st == "kept"]
        self.WHAT = dict(WHAT, T9=WHAT["T9"] + (" Kept open (TRUSTM_KEEP_OPEN): %s." % " ".join(kept) if kept else ""))
        return self

    def step(self):
        if self.sealed:
            if not self.rec:
                return "other"
            if not self.checked:
                return "T8"
            return "T9" if self.open else "T10"
        if snapshot_path(self.serial) not in os.listdir():
            return "T1"
        if self.key is None:
            return "T2"
        if not self.tested:
            return "T3"
        if self.binding is None:
            return "T4"
        if not self.owner_seen:
            return "T5"
        if not self.written:
            return "T6"
        return "T7"

    def owner(self):
        import webauthn
        import quorum_cfg
        x, y = self.key
        return webauthn.owner_address("0x%064x" % x, "0x%064x" % y, quorum_cfg.CFG["signer"])

    def fingerprint(self):
        return "%08x" % (self.key[0] >> 224) if self.key else "none"

    # --- the steps: each returns (ok, [(check, ok), ...], message) -------------------
    def run(self, step):
        fn = getattr(self, "t" + step[1:]) if step.startswith("T") else self.tother
        self.extra = None
        try:
            out = fn()
        except Exception as e:
            out = (False, [], "%s" % e)
        self.read()
        self.log_step(step, out)
        return out

    def log_step(self, step, out):
        """Append this step's result to steps_path: ok, each check, the message, the security
        counter after it, and anything the step kept (T9: each spare's metadata before and after).
        A full flash costs the record, never the ceremony."""
        ok, checks, msg = out
        e = {"step": step, "ok": ok, "checks": [[l, bool(v)] for l, v in checks], "msg": msg, "sec": self.sec,
             "time": time.time(), "profile": self.profile}
        if self.extra:
            e.update(self.extra)
        try:
            try:
                with open(steps_path(self.serial)) as f:
                    log = json.load(f)
            except (OSError, ValueError):
                log = []
            log = log[-39:] + [e]
            with open(steps_path(self.serial), "w") as f:
                json.dump(log, f)
        except Exception as ex:
            print("steps log:", ex)

    def _cert(self):
        der, cert = self.sig.cert()
        return der, cert

    def t1(self):
        c = self.chip
        der, cert = self._cert()
        ca_ok, why = tmcfg.cert_check(cert)
        probe = hashlib.sha256(b"PicoQuorum pre-flight" + self.uid).digest()
        r, s = c.sign(tmcfg.FACTORY_KEY, probe)      # E0F0 signs: its key is the certificate's
        e0f0 = p256.verify(cert["qx"], cert["qy"], probe, r, s)
        k, rec, bnd = self.meta[tmcfg.KEY], self.meta[tmcfg.RECORD], self.meta[tmcfg.BINDING]
        lcs_op = "LcsO<op"
        # A ceremony started elsewhere (another board, or the laptop) and not sealed: E0F1 holds a
        # key and F1D0 our record for this chip. Resume: T3 then proves the key matches the record.
        ours = self.rec is not None and self.rec["serial"] == self.serial and self.rec["oid"] == tmcfg.KEY
        if ours:
            key_check = ("E0F1: the record's key, unsealed", k["algo"] == 0x03 and tmcfg.ac_text(k["change"]) == lcs_op
                         and k["lcso"] < tmcfg.OPERATIONAL)
            rec_check = ("record: ours, this serial", True)
        else:
            key_check = ("E0F1 empty, Change %s" % tmcfg.ac_text(k["change"]), k["algo"] is None and tmcfg.ac_text(k["change"]) == lcs_op
                         and k["lcso"] < tmcfg.OPERATIONAL)
            rec_check = ("no record yet", self.rec is None)
        checks = [("UID %s" % self.serial[-8:], len(self.uid) == 27),
                  ("LcsA operational", c.lcsa() == tmcfg.OPERATIONAL),
                  ("security events: %s" % self.sec, self.sec is not None and self.sec < SEC_CALM),
                  ("cert from %s" % tmcfg.short_ca(cert["issuer"]), ca_ok),
                  ("E0F0 matches the cert", e0f0),
                  key_check,
                  ("E0F1 Execute %s" % tmcfg.ac_text(k["exec"]), tmcfg.ac_text(k["exec"]) == "ALW"),
                  ("F1D0/F1D1 open, %d/%d bytes" % (rec["max"] or 0, bnd["max"] or 0),
                   tmcfg.ac_text(rec["change"]) == lcs_op and tmcfg.ac_text(bnd["change"]) == lcs_op and (rec["max"] or 0) >= 110
                   and (bnd["max"] or 0) >= 83 and rec["lcso"] < tmcfg.OPERATIONAL and bnd["lcso"] < tmcfg.OPERATIONAL),
                  rec_check]
        ok = all(v for _, v in checks)
        if ok:
            self.save_snapshot(der, cert, "resumed mid-ceremony" if ours else "factory")
        if ok and ours:
            return ok, checks, "resuming a ceremony started elsewhere: T3 checks the key matches the record"
        return ok, checks, ("metadata saved as %s" % snapshot_path(self.serial)) if ok else (why or "stop here: this is not a fresh chip as expected")

    def save_snapshot(self, der, cert, state="factory"):
        c = self.chip
        objs = {}
        for oid in (0xE0C0, 0xE0C5, 0xE0E0, 0xE0F0, 0xE0F1, 0xE140, 0xF1D0, 0xF1D1) + tmcfg.SPARES:
            try:
                objs["%04X" % oid] = _hex(c.metadata(oid))
            except Exception as e:
                objs["%04X" % oid] = "error %s" % e
        snap = {"uid": "".join("%02x" % b for b in self.uid), "serial": self.serial, "metadata": objs,
                "cert": "".join("%02x" % b for b in der), "issuer": cert["issuer"], "certSerial": cert["serial"],
                "sec": self.sec, "time": time.time(), "state": state}
        with open(snapshot_path(self.serial), "w") as f:
            json.dump(snap, f)

    def t2(self):
        x, y = self.sig.genkey(tmcfg.KEY)
        self.newkey = (x, y)
        self.tested = False
        self.binding = None
        self.written = False
        m = self.chip.meta(tmcfg.KEY)
        checks = [("new key %08x" % (x >> 224), True), ("E0F1: P-256", m["algo"] == 0x03),
                  ("key usage Sign", bool((m["usage"] or 0) & tmcfg.USAGE_SIGN)),
                  ("not sealed yet (%s)" % tmcfg.lcs_name(m["lcso"]), m["lcso"] < tmcfg.OPERATIONAL)]
        return all(v for _, v in checks), checks, "the key exists only inside the chip"

    def _sign_ok(self, digest):
        r, s = self.sig.sign(digest, tmcfg.KEY)
        x, y = self.key
        return p256.verify(x, y, digest, r, s) and s <= p256.N // 2

    def t3(self):
        import webauthn
        before = self.chip.sec()
        plain = self._sign_ok(hashlib.sha256(b"picowallet").digest())
        ad, fields, digest = webauthn.assertion(bytes(32))
        wa = self._sign_ok(digest)
        after = self.chip.sec()
        checks = [("plain digest verifies, low s", plain), ("WebAuthn digest verifies", wa),
                  ("security events %d -> %d (2 signatures)" % (before, after), after <= before + 2)]
        self.tested = all(v for _, v in checks)
        return self.tested, checks, "E0F1 signs with the key T2 made" if self.tested else "the key does not match: T2 again"

    def t4(self):
        der, cert = self._cert()
        x, y = self.key
        digest = tmcfg.binding_digest(self.uid, tmcfg.KEY, x, y)
        r, s = self.chip.sign(tmcfg.FACTORY_KEY, digest)
        if s > p256.N // 2:
            s = p256.N - s
        ok = p256.verify(cert["qx"], cert["qy"], digest, r, s)
        if ok:
            self.binding = (r, s)
        checks = [("E0F0 signed the binding", True), ("verifies under cert %s" % cert["serial"][-8:], ok)]
        return ok, checks, "anyone with the certificate can check this chip holds this key"

    def t5(self):
        self.owner_seen = True
        return True, [("key %s" % self.fingerprint(), True)], "owner %s. Compare it on the laptop before T6." % self.owner()

    def t6(self):
        import image
        try:
            if time.gmtime()[0] < 2026:
                import ntptime
                ntptime.settime()
        except Exception:
            pass
        der, cert = self._cert()
        x, y = self.key
        rec = tmcfg.record_encode(self.serial, tmcfg.KEY, x, y, self.owner(), time.time(), image.BUILD)
        bnd = tmcfg.binding_encode(self.binding[0], self.binding[1], der)
        self.chip.set_data(tmcfg.RECORD, rec)
        self.chip.set_data(tmcfg.BINDING, bnd)
        self.sig.forget()
        back_r = self.chip.get(tmcfg.RECORD)
        back_b = self.chip.get(tmcfg.BINDING)
        dec = tmcfg.record_decode(back_r)
        checks = [("F1D0 reads back", bytes(back_r[:len(rec)]) == rec),
                  ("F1D1 reads back", bytes(back_b[:len(bnd)]) == bnd),
                  ("record names this key", dec is not None and (dec["qx"], dec["qy"]) == (x, y)),
                  ("binding verifies", tmcfg.binding_check(tmcfg.binding_decode(back_b), der, cert, self.uid, tmcfg.KEY, x, y))]
        self.written = all(v for _, v in checks)
        return self.written, checks, "rewritable until T7" if self.written else "stop: write T6 again"

    def t7(self):
        if not (self.tested and self.written) or not self._sign_ok(hashlib.sha256(b"before the seal").digest()):
            return False, [("the key signs and verifies", False)], "not sealed: run T3 again"
        msg = seal(self.sig)
        m = {oid: self.chip.meta(oid) for oid in (tmcfg.KEY, tmcfg.RECORD, tmcfg.BINDING)}
        checks = [("%04X operational" % oid, m[oid]["lcso"] == tmcfg.OPERATIONAL) for oid in (tmcfg.KEY, tmcfg.RECORD, tmcfg.BINDING)]
        checks.append(("signs + verifies, sealed", self._sign_ok(hashlib.sha256(b"sealed").digest())))
        return all(v for _, v in checks), checks, msg

    def tother(self):
        return False, [("profile: %s" % self.profile, False)], WHAT["other"]

    def t8(self):
        import chips
        der, cert = self._cert()
        rec = self.rec
        x, y = rec["qx"], rec["qy"]
        bound = tmcfg.binding_check(tmcfg.binding_decode(self.chip.get(tmcfg.BINDING)), der, cert, self.uid, tmcfg.KEY, x, y)
        row = self.sig.key_row()
        chips.seen(self.serial, "quorum-tm1", owner=rec["owner"], sealed=rec["date"], kind="trustm")
        checks = [("quorum-tm1, E0F1 sealed", self.profile == "quorum-tm1" and row["locked"]),
                  ("F1D0/F1D1 sealed", all(self.meta[o]["lcso"] == tmcfg.OPERATIONAL for o in (tmcfg.RECORD, tmcfg.BINDING))),
                  ("record: serial and key", rec["serial"] == self.serial and rec["oid"] == tmcfg.KEY),
                  ("binding verifies", bound),
                  ("signs + verifies", self._sign_ok(hashlib.sha256(b"done").digest())),
                  ("security events %s" % self.sec, True)]
        self.checked = all(v for _, v in checks[:5])
        return self.checked, checks, "owner %s. Spares: %s" % (rec["owner"], tmcfg.spares_text(self.spares))

    def t9(self):
        if not self.checked:
            return False, [("T8 passed this session", False)], "not frozen: T8 first"
        groups = (("key slots", tmcfg.SPARE_KEYS), ("cert slots", tmcfg.SPARE_CERTS),
                  ("counters", tmcfg.SPARE_COUNTERS), ("data", tmcfg.SPARE_DATA))
        before = self.chip.sec()
        was = {}
        for oid in tmcfg.SPARES:
            try:
                was["%04X" % oid] = _hex(self.chip.metadata(oid))
            except Exception as e:
                was["%04X" % oid] = "error %s" % e
        t0 = time.ticks_ms()
        refused = freeze(self.sig, self.open)
        took = time.ticks_diff(time.ticks_ms(), t0)
        self.sig.forget()
        now = self.sig.spares()
        after = self.chip.sec()
        checks = []
        for label, oids in groups:
            mine = [o for o in oids if now.get(o) != "absent"]
            left = [o for o in mine if now.get(o) == "open"]
            checks.append(("%s: %d of %d frozen" % (label, len([o for o in mine if now.get(o) == "frozen"]), len(mine)), not left))
        checks.append(("E0F1 still signs", self._sign_ok(hashlib.sha256(b"spares frozen").digest())))
        checks.append(("security events %d -> %d" % (before, after), True))
        after_meta = {}
        for oid in tmcfg.SPARES:
            try:
                after_meta["%04X" % oid] = _hex(self.chip.metadata(oid))
            except Exception as e:
                after_meta["%04X" % oid] = "error %s" % e
        self.extra = {"metaBefore": was, "metaAfter": after_meta, "refused": [["%04X" % o, why] for o, why in refused],
                      "secBefore": before, "secAfter": after, "ms": took,
                      "keptOpen": ["%04X" % o for o, st in now.items() if st == "kept"]}
        msg = tmcfg.spares_text(now)
        if refused:
            msg += ". Refused: " + ", ".join("%04X (%s)" % (o, why[-24:]) for o, why in refused)
        return all(v for _, v in checks), checks, msg

    def t10(self):
        rec = self.rec
        row = self.sig.key_row()
        checks = [("quorum-tm1, E0F1 sealed", self.profile == "quorum-tm1" and row["locked"]),
                  ("spares: %s" % tmcfg.spares_text(self.spares), not self.open),
                  ("signs + verifies", self._sign_ok(hashlib.sha256(b"done").digest())),
                  ("security events %s" % self.sec, True),
                  ("ALLOW_* off (tools/fw ceremony finish)", not (S.flag("ALLOW_LOCK") or S.flag("ALLOW_GENKEY")))]
        return all(v for _, v in checks[:3]), checks, "owner %s" % rec["owner"]


# ----------------------------------------------------------------------------- the metadata map
OIDS = ((0xE0F0, "factory key"), (0xE0F1, "Safe key"), (0xE0E0, "Infineon cert"), (0xF1D0, "record"),
        (0xF1D1, "binding"), (0xE0C5, "security events"), (0xE140, "binding secret"))


def draw_map(d, sig, p):
    """X on a Trust M (the knob's second choice on build1): each object's lifecycle and access
    conditions, read-only. Read once, then drawn strip by strip."""
    rows = []
    for oid, what in OIDS:
        try:
            m = sig.chip.meta(oid)
            rows.append(("%04X %s" % (oid, what), " %s ch %s ex %s" % (
                {0x01: "cre", 0x03: "init", 0x07: "OP", 0x0F: "term"}.get(m["lcso"], "-"),
                tmcfg.ac_text(m["change"])[:9], tmcfg.ac_text(m["exec"])[:6]), True))
        except Exception as e:
            rows.append(("%04X %s" % (oid, str(e)[:18]), "", False))
    d.frames(_paint_map, d, sig.serial()[-20:], rows, p)


def _paint_map(d, serial, rows, p):
    d.fill(p["bg"])
    d.text("TRUST M objects", 4, 4, p["accent"])
    d.text(serial, 4, 16, p["muted"])
    y = 32
    for top, sub, ok in rows:
        d.text(top, 4, y, p["fg"] if ok else p["bad"])
        d.text(sub, 4, y + 10, p["muted"])
        y += 25
    d.text("any key: back", 4, 228, p["muted"])
    d.show()
