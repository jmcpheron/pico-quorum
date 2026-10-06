# The boot screen's taglines: one under the name on the mark (bootmark.py), a cycle of them on the
# orbit (bootart.py). secrets.BOOT_TAGLINES picks the pool: "serious" (the default), "fun", "all"
# or "none". Each must fit 220 px in sans14 (test-vectors/run-bootmark.mjs checks).
# SERIOUS lines are claims about this console, so each must stay true of the firmware:
#   the hash: safe_tx.py rebuilds the safeTxHash from the fields shown, and the console refuses a
#     transaction whose hash the service lies about (txservice.py)
#   the key: made inside the chip (GenKey), never leaves it, never a seed phrase
#   the screen: decode.py turns calldata into plain words; red pages for the dangerous ones
#   the code: the hash's last 8 characters, to read to a co-signer (safe_tx.verify_code)
import random

SERIOUS = (
    "See what you sign",
    "Nothing signs unseen",
    "Every hash checked here",
    "Computes its own Safe hash",
    "If the service lies, it's refused",
    "Don't trust. Verify.",
    "Plain words, not hex",
    "Read it. Then sign it.",
    "Compare the code, then sign",
    "Keys born in silicon",
    "The key never leaves the chip",
    "No seed phrase. Ever.",
    "Your keys, your quorum",
    "Several keys, one Safe",
    "Hardware approvals for Safe",
    "Deliberate by design",
)

FUN = (
    "Hack the planet!",                     # Hackers (1995)
    "The bear is sticky with honey",        # Silicon Valley
    "Middle-out signing",                   # Silicon Valley
    "Making the world a better place",      # Silicon Valley
    "There is no seed phrase",              # The Matrix: there is no spoon (and there isn't)
    "Follow the white rabbit",              # The Matrix
    "Shall we play a game?",                # WarGames
    "The only winning move is to verify",   # WarGames
    "Too many secrets",                     # Sneakers
    "It's a Unix system! I know this!",     # Jurassic Park
    "Hello, friend.",                       # Mr. Robot
    "I'm in.",                              # every hacker film
    "All your keys are belong to you",      # Zero Wing
    "Trust no one. Verify everything.",     # The X-Files, roughly
    "In silicon we trust",
    "High tech, low trust",                 # cyberpunk: high tech, low life
    "Jack in. Sign off.",
    "Wetware approves, hardware signs",
    "Greetz to the quorum",                 # the demoscene
    "Not your keys, not your coins",
)


def pool():
    try:
        import secrets
        kind = getattr(secrets, "BOOT_TAGLINES", "serious")
    except ImportError:
        kind = "serious"
    return {"serious": SERIOUS, "fun": FUN, "all": SERIOUS + FUN}.get(kind, ())


def pick():
    """One tagline for this boot, or "" for none."""
    p = pool()
    return random.choice(p) if p else ""


def cycle():
    """The whole pool, from a random place in it (MicroPython's random has no shuffle)."""
    p = pool()
    if not p:
        return ("",)
    i = random.getrandbits(8) % len(p)
    return p[i:] + p[:i]
