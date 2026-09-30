# Layer 4: the few calls the console makes to Safe's transaction service, at the real service's
# paths (api.safe.global/tx-service/<chain>), so the same code talks to tools/quorum's mock on the
# laptop and, later, to the real thing. Nothing here is trusted: quorum.py rehashes every
# transaction from its fields and refuses any whose hash or Safe differs from what it pinned.
#
#   s = Service(base_url, safe)
#   s.target(base_url, safe)   another Safe, maybe on another chain's service
#   s.safe_info() -> {"nonce", "threshold", "owners", ...}
#   s.pending(nonce) -> [transaction, ...] oldest nonce first
#   s.confirm(safe_tx_hash, signature) -> (ok, detail)
from binascii import hexlify
import gc
import sys
import requests
from keccak import keccak256
from policy import is_sim

TIMEOUT = 5            # the laptop's service, plain HTTP on the LAN
TIMEOUT_TLS = 15       # api.safe.global: a full TLS handshake on the Pico each call, 1-2 s, sometimes over 5
# HTTPS needs one buffer of about 16 KB in a single piece. The console's heap fragments as it
# decodes and draws: on the board, after a review, 154 KB were free but no block over 8 KB, and the
# confirmation's POST failed with OSError 12 (2026-09-25). So an https Service holds one block this
# size from the start and lets go of it only for the length of each call.
RESERVE = 32 * 1024
ON_BOARD = sys.platform == "rp2"     # the emulator's `requests` is the host's curl, which checks certificates itself
_early = None


def reserve_early():
    """Take the reserve at boot, before the console's modules load (main_console.py): a block
    taken then is whole; one taken after them may not exist any more. The first https Service
    keeps it."""
    global _early
    gc.collect()
    try:
        _early = bytearray(RESERVE)
    except MemoryError:
        _early = None


def checksum(a):
    """EIP-55 mixed case. Safe's service wants addresses in its paths spelled this way."""
    a = a.lower().replace("0x", "")
    h = hexlify(keccak256(a.encode())).decode()
    return "0x" + "".join(c.upper() if int(h[i], 16) >= 8 else c for i, c in enumerate(a))


class ServiceError(Exception):
    pass


def why(code, out):
    """What the service said, for the screen and the log: its `detail`, else the first message it gave
    under any other name (Safe's validation errors come as {"nonFieldErrors": [...]}, {"signature": [...]}),
    else the bare HTTP code. Kept short. It used to read only `detail`, so a rejected signature showed
    "the service said: " and nothing (2026-09-30)."""
    if code in (200, 201):
        return ""
    msg = ""
    if isinstance(out, dict):
        msg = out.get("detail") or ""
        if not msg:
            for k, v in out.items():
                v = v[0] if isinstance(v, (list, tuple)) and v else v
                if v and not isinstance(v, (dict, list, tuple)):
                    msg = "%s: %s" % (k, v) if k not in ("nonFieldErrors", "non_field_errors") else str(v)
                    break
    elif out:
        msg = str(out)
    return ("HTTP %s" % code + (": " + msg if msg else ""))[:120]


class Service:
    def __init__(self, base, safe, api_key=None, verify=True, floor=0):
        """verify: check the server's certificate against the pinned roots (vhttp.py). Only a
        development board may turn it off (QUORUM_TLS_VERIFY = False); the production image cannot.
        floor: the build's date; the clock is never trusted below it.
        One Service serves every Safe the console watches (target() switches between them), so
        the TLS context and the HTTPS reserve exist once, however many Safes there are."""
        self.api_key = api_key
        self.verify = verify
        self.requests = 0                # since boot, for the device screen (the real service has a monthly quota)
        self.floor = floor
        self._ctx = None
        self._room = None
        self.lost = False
        self.target(base, safe)
        global _early
        if self.base.startswith("https"):
            self._room, _early = _early, None
        self.hold()

    def target(self, base, safe):
        """Ask about this Safe at this service from now on (a Safe on another chain has another
        service: api.safe.global/tx-service/<chain>)."""
        self.base = base.rstrip("/")
        self.safe = safe
        self.sim = is_sim(self.base)     # tools/quorum on the laptop: its /sim endpoints exist
        https = self.base.startswith("https")
        if not https:
            self.tls = "plain"
        elif not ON_BOARD:
            self.tls = "host"
        elif self.verify:
            if self._ctx is None:
                import vhttp
                self._ctx = vhttp.context()      # the first https target: at start, while the heap is whole
            self.tls = "verified"
        else:
            self.tls = "UNVERIFIED"
        # the API key goes only to Safe's own service over HTTPS, never to a laptop on the LAN
        self.headers = {"Authorization": "Bearer " + self.api_key} if self.api_key and https else {}
        self.timeout = TIMEOUT_TLS if https else TIMEOUT

    def hold(self):
        """Take the reserve back (https only). If it no longer fits, `lost` says so: the heap has
        split where the reserve was, and the console restarts at its next quiet moment (quorum.py)
        rather than fail every call from then on (seen on the board, 2026-09-26)."""
        if self._room is None and self.base.startswith("https"):
            gc.collect()
            try:
                self._room = bytearray(RESERVE)
                self.lost = False
            except MemoryError:
                self._room = None
                self.lost = True

    def release(self):
        """Give the reserve back to the heap, for an HTTPS call or anything else that needs room."""
        self._room = None
        gc.collect()

    def _call(self, method, path, body=None):
        try:
            import watch
            # connect and the handshake (each socket step up to the timeout), then vhttp's 40 s
            # budget for the response: a slow call that is still alive must not reset the board
            watch.extend(4 * int(self.timeout * 1000) + 40000)
        except ImportError:
            pass
        if self._ctx is not None and self.base.startswith("https"):
            import vhttp
            vhttp.clock(self.floor)
            return vhttp.request(method, self.base + path, self._ctx, body=body, headers=self.headers, timeout=self.timeout)
        if method == "GET":
            return requests.get(self.base + path, headers=self.headers, timeout=self.timeout)
        return requests.post(self.base + path, json=body, headers=self.headers, timeout=self.timeout)

    def _fetch(self, method, path, body=None):
        """(status, body bytes). The reserve is lent for the call and taken back before anything
        is parsed: what the console keeps from a response must not land where the reserve goes."""
        self.release()
        self.requests += 1
        try:
            r = self._call(method, path, body)
            try:
                return r.status_code, r.content
            finally:
                r.close()
                r = None
        finally:
            self.hold()

    def _get(self, path):
        import json
        status, data = self._fetch("GET", path)
        if status != 200:
            raise ServiceError("HTTP %d" % status)
        return json.loads(data)

    def _post(self, path, body):
        import json
        status, data = self._fetch("POST", path, body)
        try:
            out = json.loads(data)
        except ValueError:
            out = {}
        return status, out

    def safe_info(self):
        return self._get("/api/v1/safes/%s/" % self.safe)

    def pending(self, nonce, limit=10):
        q = "?executed=false&nonce__gte=%d&ordering=nonce&limit=%d" % (nonce, limit)
        return self._get("/api/v2/safes/%s/multisig-transactions/%s" % (self.safe, q)).get("results", [])

    def confirm(self, safe_tx_hash, signature):
        code, out = self._post("/api/v1/multisig-transactions/%s/confirmations/" % safe_tx_hash, {"signature": signature})
        return code in (200, 201), why(code, out)

    # --- the simulation's own endpoints (tools/quorum). Never sent to a real service: they would
    # spend its quota and hand it this key's public key for nothing.
    def announce(self, name, qx, qy):
        if not self.sim:
            return None
        code, out = self._post("/sim/device", {"name": name, "qx": qx, "qy": qy})
        return out.get("owner") if code == 200 else None

    def declined(self, safe_tx_hash, by):
        if not self.sim:
            return
        try:
            self._post("/sim/declined", {"safeTxHash": safe_tx_hash, "by": by})
        except Exception:
            pass
