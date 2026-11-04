# The ceremony as practice, on the console: the ten steps of provision.py with their screens, the
# B+Y arm and the holds, and nothing written. The real ceremony is the organizer's, before the board
# is handed over: the ceremony image and `tools/fw ceremony start` on a computer
# (docs/PROVISIONING.md). Here C1 reads the chip's config zone, as the real C1 does, and says what it
# found; every other step only says what it would have done. The arm is this module's own 60 s
# clock, never signer.arm, and no step needs ALLOW_*. Device -> Practice opens it (quorum.py).
import time
import ceremony_ui as CU

ARM_S = 60
DID = {
    "C2": "For real, the quorum v1 table would now be in the config zone, read back and compared.",
    "C3": "For real, the config zone would now be locked for good.",
    "C4": "For real, slot 0 would now hold a new key, made inside the chip.",
    "C5": "For real, two test signatures would be checked here, and counter 0 would be up by 2.",
    "C6": "For real, slot 0 would now be sealed: its key could never change.",
    "C7": "For real, the owner address would show here, as text and a picture, to compare on the computer.",
    "C8": "For real, slots 1-15 would hold zeros and the OTP zone the record.",
    "C9": "For real, the data and OTP zones would now be locked for good.",
    "C10": "Practice done. The real ceremony runs on the ceremony image, on a computer: tools/fw ceremony start.",
}


class Practice:
    """A ceremony for ceremony_ui.UI (see provision.Ceremony) that never writes."""
    HEADER = "PRACTICE ceremony"
    NSTEPS = 10
    PERMANENT = CU.PERMANENT
    GENKEY = CU.GENKEY
    FINAL = ("C10",)
    TITLES = CU.TITLES
    WHAT = dict(CU.WHAT, C1="Reads the chip and checks it is fresh. The real C1 saves its config too; this saves nothing.",
                C10="The end. For real, the chip would be sealed now, and its owner address would go on the Safe.")
    key = None
    counter = None

    def __init__(self, sig):
        self.sig = sig
        self.n = 1
        self.until = None

    def index(self, st):
        return int(st[1:])

    def picture(self, st, result=False):
        return None

    def subtitle(self):
        return "Practice: writes nothing"

    def note(self):
        return ""

    def step(self):
        return "C%d" % self.n

    def run(self, st):
        """(ok, checks, message), and on to the next step."""
        if st == "C1":
            ok, checks, msg = self.look()
        else:
            ok, checks, msg = True, [("nothing written", True)], DID[st]
        self.n = min(self.NSTEPS, self.n + 1)
        return ok, checks, msg

    def look(self):
        """C1's checks, from a read of the config zone. Nothing else is asked of the chip."""
        s = self.sig
        if s is None or s.name != "atecc608":
            return False, [("an ATECC608 answers", False)], \
                "The real C1 reads an ATECC608. This console's key is %s; the practice goes on." % (s.name if s else "none")
        import chipcfg
        try:
            cfg = s.config()
            serial = s.serial()
        except Exception as e:
            return False, [("the chip answers", False)], "%s" % e
        rev = "".join("%02x" % b for b in cfg[4:8])
        prof = chipcfg.identify(cfg)
        checks = [("serial ..%s" % serial[-8:], True),
                  ("rev %s %s" % (rev, chipcfg.REVISIONS.get(rev, "?")), rev in chipcfg.REVISIONS),
                  ("zones unlocked (55 55)", cfg[86] == 0x55 and cfg[87] == 0x55),
                  ("no slot locked (FF FF)", cfg[88] == 0xFF and cfg[89] == 0xFF),
                  ("table: %s" % prof, prof == "factory")]
        ok = all(k for _, k in checks)
        return ok, checks, ("A fresh chip: the real ceremony would start here." if ok else
                            "Not a fresh chip: its ceremony already ran. The practice goes on.")

    # --- the arm: this practice's own clock -------------------------------------------
    def arm(self):
        self.until = time.ticks_add(time.ticks_ms(), ARM_S * 1000)

    def armed(self):
        if self.until is None:
            return 0
        left = time.ticks_diff(self.until, time.ticks_ms())
        return (left + 999) // 1000 if left > 0 else 0

    def need(self, st):
        if (st in self.PERMANENT or st in self.GENKEY) and not self.armed():
            return "not armed: hold B+Y 3 s"
        return ""


def ui(d, keys, sig, theme="dark"):
    """The ceremony's own screen (setup_s.py's on three buttons) on a Practice, arming its clock."""
    import lcd as L
    if L.THREE:
        import setup_s
        base = setup_s.UI
    else:
        base = CU.UI

    class UI(base):
        def arm(self):
            self.c.arm()

        def armed(self):
            return self.c.armed()

        def need(self, st):
            return self.c.need(st)

    return UI(d, keys, sig, theme, Practice(sig))
