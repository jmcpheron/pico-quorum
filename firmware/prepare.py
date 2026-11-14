# console-rp's bench step: a fresh ATECC608 made ready for the customer image, whose owner makes the key
# on the device (keyflow.OwnKey, keypick_rp.py). The ceremony's first three steps and a check, never a key.
#   C1  pre-flight: read-only checks, the factory config saved as snapshot-<serial>.bin
#   C2  write quorum v1 and read it back (reversible: the config zone is still open)
#   C3  lock the config zone, the chip checking a CRC of the reviewed table   PERMANENT
#   P4  read only: the config locked as quorum v1, the data zone open, slot 0 not sealed, no key in it
#       (KeyValid 0) and counter 0 at 0. The public key is never asked for: with no key in the slot that
#       is a GenKey command (mode 0), and nothing here sends GenKey.
#   ready  P4 passed: the chip is ready for the console-rp image. D2 checks it again.
# C3 needs ALLOW_LOCK in a bench secrets.py (swdload.py --secrets: never in the repository), the D0+D1
# arm and D2 held 3 s, on setup_s's screen. Nothing asks for ALLOW_GENKEY. Each step's result goes into
# prep-log.txt and the log (qlog: log.txt, and the computer over the link).
import provision
import qlog

LOG = "prep-log.txt"
TITLES = dict(provision.TITLES, P4="No-key check", ready="Prepared")
WHAT = dict(provision.WHAT,
            P4="Reads the chip: config locked as quorum v1, data zone open, slot 0 not sealed, no key, counter 0 at 0. Changes nothing.",
            ready="Ready for the console-rp image: its owner makes the key on it. D2 checks again.")


class Ceremony(provision.Ceremony):
    HEADER = "PREPARE console-rp"
    NSTEPS = 4
    PERMANENT = ("C3",)
    GENKEY = ()
    FINAL = ("P4", "ready", "other")
    TITLES = TITLES
    WHAT = WHAT

    def __init__(self, sig):
        self.checked = False        # P4 passed this start
        super().__init__(sig)

    def index(self, st):
        return int(st[1:]) if st[0] in ("C", "P") else 0

    def read_key(self):
        return None                 # never the public key (P4)

    def step(self):
        if not self.config_locked:
            return self.step_open()     # C1, C2, C3
        if self.profile != "quorum-v1":
            return "other"
        return "ready" if self.checked else "P4"

    def run(self, step):
        if step in ("P4", "ready"):
            try:
                out = self.p4()
            except Exception as e:
                out = (False, [], "%s" % e)
            self.read()
        elif step in ("C1", "C2", "C3"):
            out = super().run(step)
        else:
            out = self.cother()
        self.log(step, out)
        return out

    def p4(self):
        cfg = self.cfg
        valid = self.chip.info(1, 0)[0]
        checks = [("config locked (87 = 00)", cfg[87] == 0x00),
                  ("table: %s" % self.profile, self.profile == "quorum-v1"),
                  ("data zone open (86 = 55)", cfg[86] == 0x55),
                  ("slot 0 not sealed (88 = %02X)" % cfg[88], bool(cfg[88] & 1)),
                  ("slot 0 empty (KeyValid %d)" % valid, valid == 0),
                  ("counter 0 at %s" % self.counter, self.counter == 0)]
        self.checked = all(k for _, k in checks)
        return self.checked, checks, ("ready for the console-rp image" if self.checked
                                      else "not ready: keep this chip off a customer's board")

    def log(self, step, out):
        ok, checks, msg = out
        line = "prepare %s %s %s: %s | %s" % (self.serial, step, "ok" if ok else "STOPPED",
                                              "; ".join("%s %s" % (c, "ok" if k else "FAIL") for c, k in checks), msg)
        qlog.write(line)
        try:
            with open(LOG, "a") as f:
                f.write(line + "\n")
        except Exception as e:
            qlog.write("prep-log.txt: %r" % e)
