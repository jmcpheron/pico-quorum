# The provisioning ceremony for a fresh ATECC608: PicoQuorum's own config, quorum v1
# (chipcfg.py; the reasoning and the runbook are in docs/PROVISIONING.md). One linear screen in the
# ceremony image. The step is worked out from the chip's own state every time, so a reboot at any
# point resumes where the chip is.
#
#   C1  pre-flight: read-only checks, the factory config saved as snapshot-<serial>.bin
#   C2  write quorum v1 and read it back (reversible: the config zone is still open)
#   C3  lock the config zone, the chip checking a CRC of the reviewed table   PERMANENT
#   C4  GenKey in slot 0 (a new key; replaceable until C6)
#   C5  test signatures (a plain digest and a WebAuthn assertion), verified here
#   C6  lock slot 0: the key can never be replaced                            PERMANENT
#   C7  the owner address this key gets on the Safe, to compare on the laptop
#   C8  zeros into slots 1-15 and the record into the OTP zone (rewritable until C9)
#   C9  lock the data and OTP zones, the chip checking their CRC               PERMANENT
#   C10 final checks and the summary
#
# Permanent steps need ALLOW_LOCK (C4 ALLOW_GENKEY) in secrets.py, the B+Y arm (held 3 s) and A
# held 3 s, started with ARM_LEFT of the arm's 60 s to go. Nothing here signs anything but its own
# test digests. Logic (Ceremony, here) and screen (ceremony_ui.py, which the console's practice uses
# too) are apart so test-vectors/run-ceremony.mjs can walk the whole thing on the virtual chip.
# C4-C10 are keyflow.py's, which console-rp's image carries without this file: C1-C3 and the config
# writes are here only.
import time
import board
import atecc
import chipcfg
import signer as S
import p256  # noqa: F401 (tests, brand)
import keyflow
import ceremony_ui
from ceremony_ui import HOLD_MS, ARM_MS, ARM_LEFT, PERMANENT, TITLES, WHAT, palette  # noqa: F401 (brand, claim, chipapp)
from keyflow import write_record_and_fill, lock_data_crc  # noqa: F401 (brand, claim)

TABLE = chipcfg.QUORUM_V1

# ----------------------------------------------------------------------------- chip writes
# Here, not in signer.py, so the console image (which carries signer.py) holds none of them.
def write_table(sig, table):
    """REVERSIBLE while the config zone is open: write `table` with this chip's own bytes kept and
    read it back. The chip's original bytes are snapshotted first."""
    sig.save_snapshot()
    sig._slots = None
    cfg = sig.chip.read_config_all()
    return sig.chip.write_config(chipcfg.expected_image(cfg, table))


def lock_config_crc(sig, table):
    """PERMANENT. Lock the config zone with the CRC of exactly `table` (plus the chip's own bytes):
    the chip refuses if what it holds differs by one bit. Needs ALLOW_LOCK and the arm."""
    if not S._allowed("ALLOW_LOCK"):
        raise Exception(S._refused("lock"))
    sig._slots = None
    cfg = sig.chip.read_config_all()
    image = chipcfg.expected_image(cfg, table)
    sig.chip.lock_config(expect=image, summary=chipcfg.summary(image))
    return "config zone locked (CRC %04x)" % chipcfg.summary(image)


class Ceremony(keyflow.Ceremony):
    """C1-C3 on a fresh chip, then keyflow's C4-C10."""

    def step_open(self):
        if self.profile == "quorum-v1":
            return "C3"
        return "C1" if self.sig.snapshot() is None else "C2"

    def date(self):
        try:
            if time.gmtime()[0] < 2026:
                import ntptime      # the record's date; boot.py joined the WiFi
                ntptime.settime()
        except Exception:
            pass
        return board.unix()

    def c1(self):
        c = self.chip
        cfg = self.cfg
        rnd = c.random()
        checks = [("answers at 0x60", c.addr == 0x60),
                  ("rev %s %s" % (self.revision, chipcfg.REVISIONS.get(self.revision, "?")), self.revision in chipcfg.REVISIONS
                   and self.revision == "".join("%02x" % b for b in cfg[4:8])),
                  ("zones unlocked (55 55)", cfg[86] == 0x55 and cfg[87] == 0x55),
                  ("no slot locked (FF FF)", cfg[88] == 0xFF and cfg[89] == 0xFF),
                  ("I2C address byte C0", cfg[16] == 0xC0),
                  ("Random: unlocked pattern", rnd == bytes([0xFF, 0xFF, 0, 0]) * 8),
                  ("self-test passes", c.selftest() == 0),
                  ("table: %s" % self.profile, self.profile == "factory")]
        ok = all(k for _, k in checks)
        if ok:
            self.sig.save_snapshot()
        return ok, checks, "factory config saved as %s" % self.sig.snapshot_path() if ok else "stop here: this is not a fresh chip as expected"

    def c2(self):
        n = write_table(self.sig, TABLE)
        cfg = self.chip.read_config_all()
        crc = chipcfg.config_summary(cfg)
        checks = [("written, %d bytes changed" % n, True), ("reads back as quorum v1", chipcfg.identify(cfg) == "quorum-v1"),
                  ("config CRC %04x" % crc, True)]
        return all(k for _, k in checks), checks, "compare the CRC on the laptop: tools/check_config --summary <snapshot>"

    def c3(self):
        msg = lock_config_crc(self.sig, TABLE)
        cfg = self.chip.read_config_all()
        live = self.chip.random() != bytes([0xFF, 0xFF, 0, 0]) * 8
        s0 = atecc.decode_slot(cfg, 0)
        checks = [("config locked (87 = 00)", cfg[87] == 0x00), ("still quorum v1", chipcfg.identify(cfg) == "quorum-v1"),
                  ("Random is live", live), ("slot 0: P-256, ext sign", s0["kind"] == "P256" and s0["genKey"] and s0["extSign"] and not s0["intSign"])]
        return all(k for _, k in checks), checks, msg


# ----------------------------------------------------------------------------- the screen
class UI(ceremony_ui.UI):
    """ceremony_ui.UI on this module's Ceremony unless another is given (provision_tm's, brand's)."""

    def __init__(self, d, keys, sig, theme="dark", ceremony=None):
        super().__init__(d, keys, sig, theme, ceremony or Ceremony(sig))
