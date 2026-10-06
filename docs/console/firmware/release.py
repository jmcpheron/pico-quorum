# A PicoQuorum release, as the project Safe approves it (docs/GOVERNANCE.md, docs/RELEASES.md).
# The Safe approves a release by signing its digest D as a Safe message: one ordinary Safe
# transaction, a delegatecall to Safe's SignMessageLib (signMessage(abi.encode(D))), which marks D
# signed for good. Anyone checks it with isValidSignature(D, "0x") on that Safe.
#
#   D = EIP-712 PicoQuorumRelease(string version, bytes32 firmware, bytes32 manifest)
#       domain {name: "PicoQuorum Release", version: "1"}
#   firmware: the console image's release fingerprint (tools/releases/fingerprint.mjs, image.RELEASE)
#   manifest: the SHA-256 of docs/releases/<version>.json, which lists every source file's hash and
#             the web builds' (written once by tools/release manifest, never changed after the tag)
#
# No chainId in this domain: the Safe's own message hash binds D to one Safe on one chain. The
# console learns the three fields from the transaction's origin note, which anyone can write, so
# decode.py recomputes D from them and refuses unless it is exactly the D in the calldata. Pure, so
# test-vectors/run.py checks it against viem on CPython and MicroPython.
from keccak import keccak256

_domain = None
VERSION_CHARS = "0123456789."


def _b32(h):
    if isinstance(h, (bytes, bytearray)):
        b = bytes(h)
    else:
        b = bytes.fromhex(h[2:] if h.startswith("0x") else h)
    if len(b) != 32:
        raise ValueError("not 32 bytes")
    return b


def digest(version, firmware, manifest):
    """D for this release. version: year.month.n; firmware, manifest: 32 bytes (or hex)."""
    global _domain
    if _domain is None:
        _domain = keccak256(keccak256(b"EIP712Domain(string name,string version)") + keccak256(b"PicoQuorum Release") + keccak256(b"1"))
    struct = keccak256(keccak256(b"PicoQuorumRelease(string version,bytes32 firmware,bytes32 manifest)")
                       + keccak256(version.encode()) + _b32(firmware) + _b32(manifest))
    return keccak256(b"\x19\x01" + _domain + struct)


def valid_version(v):
    """year.month.n, as firmware/manifest.json writes it."""
    p = v.split(".") if isinstance(v, str) else []
    return len(p) == 3 and all(x and all(ch in VERSION_CHARS for ch in x) for x in p) and len(p[0]) == 4 and len(v) <= 16


def from_origin(origin):
    """The release a transaction's origin note names: {"pq": {"v": version, "f": firmware, "m":
    manifest}} (short keys: Safe's service keeps 200 characters). -> (version, firmware, manifest)
    as given, or None when the note names no release."""
    import json
    if isinstance(origin, str):
        try:
            origin = json.loads(origin)
        except ValueError:
            return None
    if not isinstance(origin, dict) or not isinstance(origin.get("pq"), dict):
        return None
    r = origin["pq"]
    v, f, m = r.get("v"), r.get("f"), r.get("m")
    if not (isinstance(v, str) and isinstance(f, str) and isinstance(m, str)):
        return None
    return v, f, m
