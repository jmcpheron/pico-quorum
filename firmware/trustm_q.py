# PicoQuorum's commands for the OPTIGA Trust M, on top of upstream's firmware/trustm.py (kept as it
# came: docs/UPSTREAM-TRACKING.md). trustm.py has the physical and data-link layers, GetDataObject,
# CalcSign and GetRandom; this adds what the console and the ceremony need:
#   present()                    is a Trust M at 0x30 (it NACKs while asleep, so i2c.scan() misses it)
#   TrustM().uid() / serial()    the 27-byte UID, and tmcfg.serial of it
#   meta(oid)                    parsed metadata (tmcfg.parse_meta)
#   gen_keypair(oid)             GenKeyPair: a NEW P-256 key in oid -> (x, y)      replaces any key there
#   set_data(oid, data)          SetDataObject                                     rewritable until sealed
#   set_lifecycle(oid, lcs)      SetDataObject(metadata) with only LcsO            PERMANENT: never goes down
#   sign(oid, digest)            CalcSign -> (r, s) as the chip gives it (not low-s)
# Command codes and layouts: OPTIGA Trust M Solution Reference Manual, "Command definitions".
# One I2C0 bus with the ATECC608 (GP4/GP5): the same pins, 100 kHz, built by atecc.make_i2c.
import trustm
import tmcfg

GET, SET, CALC_SIGN, GEN_KEYPAIR, GET_RANDOM = 0x01, 0x02, 0x31, 0x38, 0x0C
SET_DATA, SET_META, ERASE_WRITE = 0x00, 0x01, 0x40
ECC_P256 = 0x03
ERR_CODES = 0xF1C2      # the chip's last error code, read after a refusal


def bus(sda=None, scl=None):
    """Point upstream's module at the shared I2C0 bus."""
    import atecc
    trustm.i2c = atecc.make_i2c(atecc.SDA if sda is None else sda, atecc.SCL if scl is None else scl, 100_000)
    return trustm.i2c


def present(tries=40):
    """A Trust M answers at 0x30. Asleep it NACKs its address for a moment after the first try, so
    poll its state register like trustm.py does, a little."""
    import time
    if trustm.i2c is None:
        bus()
    for _ in range(tries):
        try:
            trustm.i2c.writeto(trustm.ADDR, b"\x82")
            time.sleep_us(trustm.GUARD_US)
            s = trustm.i2c.readfrom(trustm.ADDR, 4)
            return len(s) == 4
        except OSError:
            time.sleep_ms(1)
    return False


class Refused(OSError):
    """The chip answered and said no (an access condition, a bad OID): not a bus problem."""


class TrustM:
    def __init__(self):
        if trustm.i2c is None:
            bus()
        self.s = None
        self.trace = False

    def _session(self):
        if self.s is None:
            self.s = trustm.Session()
        return self.s

    def command(self, cmd, param, data, retry=True):
        """One APDU. A bus or framing error reopens the session and tries once more (upstream's
        Session has no retransmit); a refusal by the chip raises Refused at once."""
        try:
            return self._session().command(cmd, param, data)
        except OSError as e:
            msg = str(e)
            if "failed, status" in msg:
                raise Refused(msg + self._last_error())
            self.s = None
            if not retry:
                raise
            return self._session().command(cmd, param, data)

    def _last_error(self):
        try:
            code = self._session().command(GET, 0x00, ERR_CODES.to_bytes(2, "big"))
            return " (error code %s)" % "".join("%02x" % b for b in code)
        except Exception:
            self.s = None
            return ""

    # --- reads ------------------------------------------------------------------------
    def get(self, oid, offset=None, length=None):
        d = oid.to_bytes(2, "big")
        if length is not None:
            d += offset.to_bytes(2, "big") + length.to_bytes(2, "big")
        return self.command(GET, 0x00, d)

    def get_all(self, oid, step=200):
        out = b""
        while True:
            part = self.get(oid, len(out), step)
            out += part
            if len(part) < step:
                return out

    def metadata(self, oid):
        return self.command(GET, 0x01, oid.to_bytes(2, "big"))

    def meta(self, oid):
        return tmcfg.parse_meta(self.metadata(oid))

    def uid(self):
        return bytes(self.get(tmcfg.UID))

    def serial(self):
        return tmcfg.serial(self.uid())

    def sec(self):
        """The security event counter (E0C5): 0 on a quiet chip."""
        return self.get(tmcfg.SEC)[0]

    def lcsa(self):
        return self.get(tmcfg.LCSA)[0]

    def random(self, n=32):
        return self.command(GET_RANDOM, 0x00, n.to_bytes(2, "big"))

    # --- the key ----------------------------------------------------------------------
    def sign(self, oid, digest):
        """CalcSign (ECDSA over a 32-byte digest) with the key at oid -> (r, s), s as the chip made it."""
        d = b"\x01" + len(digest).to_bytes(2, "big") + bytes(digest) + b"\x03\x00\x02" + oid.to_bytes(2, "big")
        r = self.command(CALC_SIGN, 0x11, d)
        if r[0] == 0x30:                    # some builds wrap r,s in a SEQUENCE
            r = r[2:]
        out = []
        while r:
            n = r[1]
            out.append(int.from_bytes(r[2:2 + n], "big"))
            r = r[2 + n:]
        return out[0], out[1]

    def gen_keypair(self, oid, usage=tmcfg.USAGE_SIGN):
        """GenKeyPair: a NEW P-256 key in oid, replacing any key there (the chip checks oid's Change
        condition). -> (x, y), which the chip gives only now: keep it (F1D0)."""
        d = b"\x01\x00\x02" + oid.to_bytes(2, "big") + b"\x02\x00\x01" + bytes([usage])
        r = bytes(self.command(GEN_KEYPAIR, ECC_P256, d, retry=False))
        pub = r[-65:]                       # tag 02, length, then the key as a BIT STRING: 03 42 00 04 X Y
        if len(pub) != 65 or pub[0] != 0x04:
            raise OSError("trustm: GenKeyPair answered %s" % "".join("%02x" % b for b in r))
        return int.from_bytes(pub[1:33], "big"), int.from_bytes(pub[33:65], "big")

    # --- data objects -----------------------------------------------------------------
    def set_data(self, oid, data, offset=0, erase=True):
        """SetDataObject: write data at offset (erase: the object is cleared first, so a shorter
        write leaves nothing behind). The chip checks oid's Change condition."""
        d = oid.to_bytes(2, "big") + offset.to_bytes(2, "big") + bytes(data)
        return self.command(SET, ERASE_WRITE if erase else SET_DATA, d)

    def set_lifecycle(self, oid, lcs=tmcfg.OPERATIONAL):
        """PERMANENT. Raise oid's LcsO. A lifecycle state never goes down: with the factory Change
        condition "LcsO < op", operational freezes the object for good."""
        d = oid.to_bytes(2, "big") + b"\x00\x00" + tmcfg.meta_tlv(lcso=lcs)
        return self.command(SET, SET_META, d, retry=False)
