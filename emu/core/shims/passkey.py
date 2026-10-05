# The visitor's own passkey as the console's key: the browser emulator only. A Pico never has this
# module, and firmware/signer.py never loads it in a production image.
#
# The page (emu/web/app.js) makes the passkey with WebAuthn when the visitor picks "your passkey",
# and hands its public key over at boot (_emu.passkey_info). A passkey never signs a bare digest,
# so it can't stand in for a chip's sign(): it writes its own authenticatorData and clientDataJSON.
# quorum.sign_it asks it for a whole assertion over the safeTxHash computed on screen instead
# (asserts = True), and packs it exactly as it packs a chip's (webauthn.contract_signature). Safe's
# passkey signer checks both the same way; tools/vectors/passkey.mjs checks a real browser's on chain.
import json
from binascii import hexlify, unhexlify
import _emu

KINDS = {"platform": "this device's passkey", "hybrid": "a phone's passkey", "security-key": "a security key"}


class PasskeySigner:
    name = "passkey"
    asserts = True                      # quorum.sign_it: sig.assertion(safeTxHash), not sig.sign(digest)
    does = "Your passkey signs"         # the signing screen: "<does> the hash computed here"
    slot = 0

    def __init__(self, cred):
        self.cred = cred

    def pubkey(self, slot=None):
        return int(self.cred["x"], 16), int(self.cred["y"], 16)

    fresh_pubkey = pubkey

    def assertion(self, challenge):
        """(authenticatorData, clientDataFields, r, s) from the passkey, over this 32-byte challenge.
        The page waits for the person (Touch ID, a PIN, a phone); an error or a cancel raises."""
        import webauthn
        c = webauthn._b(challenge)
        if len(c) != 32:
            raise ValueError("challenge must be 32 bytes")
        out = json.loads(_emu.passkey_get(hexlify(c).decode()))
        if out.get("error"):
            raise Exception(out["error"])
        self.cred["count"] = out.get("signCount", 0)
        return unhexlify(out["ad"]), out["fields"], int(out["r"], 16), int(out["s"], 16)

    def sign(self, digest, slot=None):
        raise Exception("a passkey signs only WebAuthn assertions, never a bare digest")

    def genkey(self, slot=None):
        raise Exception("the page makes the passkey: its Key menu, Make a passkey")

    def serial(self, fresh=False):
        return self.cred.get("id", "")[:8]

    def kind(self):
        return KINDS.get(self.cred.get("attachment"), "a passkey")

    def info(self, row=None, counter=None, sec=None):
        """What the signing screen lists about the key."""
        return [
            "Your passkey: %s" % self.kind(),
            "Synced by your account" if self.cred.get("synced") else "Kept on that device",
            "Made for %s" % self.cred.get("rpId", "this site"),
            "The browser draws this screen",
        ]

    def details(self, row=None, counter=None, sec=None):
        """The Chip pages, for a passkey."""
        return [
            ("Your passkey", [
                ("Kind", self.kind()),
                ("Copies", "synced (your account)" if self.cred.get("synced") else "this device only"),
                ("Site", self.cred.get("rpId", "-")),
                ("Made", self.cred.get("made", "-")),
                ("Uses", str(self.cred.get("count", "-"))),
            ]),
            ("What it is", [
                ("Owns", "a Safe, like a chip"),
                ("Signs", "after Touch ID or PIN"),
                ("Screen", "this browser's"),
                ("Use", "below the threshold"),
            ]),
        ]


def signer():
    """The visitor's passkey, if the page picked one; else None (the console uses its chip)."""
    c = _emu.passkey_info()
    if not c:
        return None
    c = json.loads(c)
    return PasskeySigner(c) if c.get("x") and c.get("y") else None
