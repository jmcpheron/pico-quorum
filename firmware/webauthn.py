# Layer 3: the chip's P-256 signature packed the way the Safe checks it. A P-256 key cannot own a
# Safe by itself, so each chip key sits behind its own SafeWebAuthnSignerProxy (Safe's audited
# passkey signer, safe-modules passkey v0.2.1), deployed by the factory at an address fixed by the
# key. The Safe asks that proxy "is this a signature over the safeTxHash?", and the proxy checks a
# WebAuthn assertion, so the console produces one:
#
#   authenticatorData = sha256(RP_ID) || flags (UP|UV) || counter 0
#   clientDataJSON    = {"type":"webauthn.get","challenge":"<base64url(safeTxHash)>",<FIELDS>}
#   the chip signs      sha256(authenticatorData || sha256(clientDataJSON))
#
# The challenge is the safeTxHash safe_tx.py computed here from the fields on screen, so this is
# still no blind signature: every byte the chip signs is derived on the device. The contract
# requires the UV flag and ignores the rpIdHash and counter. Pure (no chip, no network), so
# test-vectors/run.py checks it on CPython and on MicroPython against viem and the deployed factory.
#
#   ad, fields, digest = assertion(safe_tx_hash)       the chip signs digest -> (r, s)
#   contract_signature(owner, ad, fields, r, s)         what the transaction service is sent
#   owner_address(qx, qy, CFG["signer"])                this key's Safe owner (the proxy's address)
import hashlib
from binascii import b2a_base64, hexlify
from keccak import keccak256

RP_ID = b"picoquorum"
FLAGS = 0x05                            # user present | user verified (the contract needs UV)
FIELDS = '"origin":"picoquorum"'        # the rest of clientDataJSON after the challenge


def _b(h):
    if isinstance(h, (bytes, bytearray)):
        return bytes(h)
    return bytes.fromhex(h[2:] if h.startswith("0x") else h)


def _u256(n):
    """A uint256 word from an int or a 0x hex string."""
    if isinstance(n, str):
        n = int(n, 16)
    return int(n).to_bytes(32, "big")


def _pad(b):
    return b + bytes(-len(b) % 32)


def b64url(b):
    """base64url without padding, as WebAuthn puts the challenge in clientDataJSON."""
    s = b2a_base64(b).decode().strip()
    return s.replace("+", "-").replace("/", "_").replace("=", "")


def client_json(challenge):
    return '{"type":"webauthn.get","challenge":"%s",%s}' % (b64url(challenge), FIELDS)


def assertion(challenge):
    """(authenticatorData, clientDataFields, the 32 bytes the chip signs) for a 32-byte safeTxHash."""
    challenge = _b(challenge)
    if len(challenge) != 32:
        raise ValueError("challenge must be 32 bytes")
    ad = hashlib.sha256(RP_ID).digest() + bytes([FLAGS]) + bytes(4)
    cd = hashlib.sha256(client_json(challenge).encode()).digest()
    return ad, FIELDS, hashlib.sha256(ad + cd).digest()


def encode(ad, fields, r, s):
    """abi.encode(bytes authenticatorData, string clientDataFields, uint256 r, uint256 s),
    canonical: the contract refuses trailing bytes."""
    f = fields.encode()
    tail_a = _u256(len(ad)) + _pad(ad)
    return _u256(128) + _u256(128 + len(tail_a)) + _u256(r) + _u256(s) + tail_a + _u256(len(f)) + _pad(f)


def contract_signature(owner, ad, fields, r, s):
    """One owner's confirmation in the Safe's signature layout for a contract owner (v = 0): the
    owner as r, the offset of its data as s (65, right after this one 65-byte slot), then the data
    with its length. The service stores it as sent and re-lays it out when it joins others."""
    data = encode(ad, fields, r, s)
    return bytes(12) + _b(owner) + _u256(65) + b"\x00" + _u256(len(data)) + data


def owner_address(qx, qy, signer):
    """The SafeWebAuthnSignerProxy the factory deploys for this key: CREATE2 with salt 0 over the
    proxy's creation code and its constructor arguments (singleton, x, y, verifiers). signer is
    quorum_cfg.CFG["signer"]; its verifiers are part of the address, so they can never change."""
    init = (_b(signer["proxyCode"]) + bytes(12) + _b(signer["singleton"]) + _u256(qx) + _u256(qy)
            + _u256(signer["verifiers"]))
    h = keccak256(b"\xff" + _b(signer["factory"]) + bytes(32) + keccak256(init))
    return "0x" + hexlify(h[12:]).decode()
