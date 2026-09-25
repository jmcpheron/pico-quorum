# Layer 4: the few calls the console makes to Safe's transaction service, at the real service's
# paths (api.safe.global/tx-service/<chain>), so the same code talks to tools/quorum's mock on the
# laptop and, later, to the real thing. Nothing here is trusted: quorum.py rehashes every
# transaction from its fields and refuses any whose hash or Safe differs from what it pinned.
#
#   s = Service(base_url, safe)
#   s.safe_info() -> {"nonce", "threshold", "owners", ...}
#   s.pending(nonce) -> [transaction, ...] oldest nonce first
#   s.confirm(safe_tx_hash, signature) -> (ok, detail)
from binascii import hexlify
import gc
import requests
from keccak import keccak256

TIMEOUT = 5            # the laptop's service, plain HTTP on the LAN
TIMEOUT_TLS = 15       # api.safe.global: a full TLS handshake on the Pico each call, 1-2 s, sometimes over 5
# HTTPS needs one buffer of about 16 KB in a single piece. The console's heap fragments as it
# decodes and draws: on the board, after a review, 154 KB were free but no block over 8 KB, and the
# confirmation's POST failed with OSError 12 (2026-09-25). So an https Service holds one block this
# size from the start and lets go of it only for the length of each call.
RESERVE = 32 * 1024


def checksum(a):
    """EIP-55 mixed case. Safe's service wants addresses in its paths spelled this way."""
    a = a.lower().replace("0x", "")
    h = hexlify(keccak256(a.encode())).decode()
    return "0x" + "".join(c.upper() if int(h[i], 16) >= 8 else c for i, c in enumerate(a))


class ServiceError(Exception):
    pass


class Service:
    def __init__(self, base, safe, api_key=None):
        self.base = base.rstrip("/")
        self.safe = safe
        self.headers = {"Authorization": "Bearer " + api_key} if api_key else {}
        self.timeout = TIMEOUT_TLS if self.base.startswith("https") else TIMEOUT
        self._room = None
        self.hold()

    def hold(self):
        """Take the reserve back (https only). Quietly does without if it no longer fits."""
        if self._room is None and self.base.startswith("https"):
            gc.collect()
            try:
                self._room = bytearray(RESERVE)
            except MemoryError:
                self._room = None

    def release(self):
        """Give the reserve back to the heap, for an HTTPS call or anything else that needs room."""
        self._room = None
        gc.collect()

    def _get(self, path):
        self.release()
        try:
            r = requests.get(self.base + path, headers=self.headers, timeout=self.timeout)
            try:
                if r.status_code != 200:
                    raise ServiceError("HTTP %d" % r.status_code)
                return r.json()
            finally:
                r.close()
        finally:
            self.hold()

    def _post(self, path, body):
        self.release()
        try:
            r = requests.post(self.base + path, json=body, headers=self.headers, timeout=self.timeout)
            try:
                try:
                    out = r.json()
                except ValueError:
                    out = {}
                return r.status_code, out
            finally:
                r.close()
        finally:
            self.hold()

    def safe_info(self):
        return self._get("/api/v1/safes/%s/" % self.safe)

    def pending(self, nonce, limit=10):
        q = "?executed=false&nonce__gte=%d&ordering=nonce&limit=%d" % (nonce, limit)
        return self._get("/api/v2/safes/%s/multisig-transactions/%s" % (self.safe, q)).get("results", [])

    def confirm(self, safe_tx_hash, signature):
        code, out = self._post("/api/v1/multisig-transactions/%s/confirmations/" % safe_tx_hash, {"signature": signature})
        return code in (200, 201), out.get("detail", "") if isinstance(out, dict) else str(out)

    # --- the simulation's own endpoints (tools/quorum); a real service answers 404, which is fine
    def announce(self, name, qx, qy):
        code, out = self._post("/sim/device", {"name": name, "qx": qx, "qy": qy})
        return out.get("owner") if code == 200 else None

    def declined(self, safe_tx_hash, by):
        try:
            self._post("/sim/declined", {"safeTxHash": safe_tx_hash, "by": by})
        except Exception:
            pass
