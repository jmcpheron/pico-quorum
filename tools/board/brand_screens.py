# Mockups of the branded-key ceremony (docs/BRANDED-KEYS.md) in the console's own look: the
# drawing kit, fonts and colours of quorum_ui.py. Run on the emulator by tools/board/shots_brand.mjs.
# Not firmware: no image carries this file, and nothing here touches a chip.
#
# Every step shows the chip under its header: the package, the OTP zone with the brand, the sixteen
# slots, and a padlock for the config and data zones. What the step writes is outlined, so the
# wizard reads as the chip filling in: brand, signature, locks, then your key and its seal.
import quorum_ui as U
import blockies

# The kit is the firmware's own (brand_ui.py), so the mockups and the board draw the same chip.
from brand_ui import W, M, BRAND, KEY, BODY, CHIP_Y, BODY_Y, logo_mark, chip, head, fact, card, hints, hold_bar, red_card


def armed(d, frac, red=False):
    U.txt(d, "Armed · hold A for 3 s", M, 188, "sans12", "ok")
    hold_bar(d, frac, red)
    hints(d, (("Y", "Back"),))


# the chip at each point of the wizard
FACTORY = {}
BRANDING = {"cfg": "locked", "otp": "brand", "dead": "zero", "focus": "otp"}
LOCKING = {"cfg": "locked", "otp": "brand", "dead": "zero", "s8": "sig", "focus": "data"}
SHIPPED = {"cfg": "locked", "data": "locked", "otp": "brand", "dead": "zero", "s8": "sig"}


def at(base, **kw):
    s = dict(base)
    s.update(kw)
    return s



# ----------------------------------------------------------------------------- the user: claim
def u0_welcome(d, number, batch):
    head(d, "New key", 1, 6)
    chip(d, CHIP_Y, SHIPPED, number)
    U.txt(d, "A PicoQuorum key", M, BODY_Y, "bold18")
    U.txt(d, "Key %s · batch %d" % (number, batch), M, BODY_Y + 24, "sans14", "muted")
    card(d, 134, 64)
    U.txt(d, "No key inside it yet.", M + 12, 140, "bold14", "text", "surface")
    U.para(d, "This console makes your key in the chip, in about a minute.", M + 12, 160, W - 2 * M - 24,
           "sans12", "muted", "surface", 16, 196)
    hints(d, (("A", "Start"), ("Y", "Not now")))
    d.show()


def u1_brand(d, number, brand):
    head(d, "Check the brand", 2, 6)
    chip(d, CHIP_Y, at(SHIPPED, focus="otp"), number)
    U.mark(d, True, M + 10, BODY_Y + 10, 10)
    U.txt(d, "Made by PicoQuorum", M + 26, BODY_Y, "bold18")
    for i, s in enumerate(("Signed by PicoQuorum key 0000", "Locked at the bench", "Never used: 0 signatures")):
        fact(d, True, s, BODY_Y + 26 + i * 19, bg="bg")
    blockie(d, brand, M, 172, 5)
    U.txt(d, "Your label says", M + 50, 170, "sans12", "muted")
    U.txt(d, number, M + 50, 184, "bold18", "text")
    U.txt(d, "?", M + 50 + U.F.width(number, "bold18") + 4, 184, "bold18", "muted")
    hints(d, (("A", "It matches"), ("Y", "It doesn't")))
    d.show()


def u2_make(d):
    head(d, "Make your key", 3, 6)
    chip(d, CHIP_Y, at(SHIPPED, s0="filling", focus="s0"))
    U.txt(d, "Made inside the chip", M, BODY_Y, "bold18")
    card(d, BODY_Y + 26, 74)
    fact(d, True, "Signs your Safe's approvals", BODY_Y + 32)
    fact(d, False, "Can't hold ETH, tokens or funds", BODY_Y + 54)
    fact(d, False, "Can't be copied or read out", BODY_Y + 76)
    armed(d, 0.45)
    d.show()


def u3_test(d):
    head(d, "Test it", 4, 6)
    chip(d, CHIP_Y, at(SHIPPED, s0="key", focus="s0"))
    U.rrect(d, U.OX + 70, BODY_Y + 16, 100, 8, 4, "raised")
    U.rrect(d, U.OX + 70, BODY_Y + 16, 64, 8, 4, "stake")
    U.txt_c(d, "Testing your key", BODY_Y + 38, "bold18")
    U.txt_c(d, "Two test signatures, checked here.", BODY_Y + 66, "sans14", "text")
    U.txt_c(d, "Nothing leaves this console.", BODY_Y + 88, "sans12", "muted")
    d.show()


def u4_seal(d, key):
    head(d, "Seal your key", 5, 6, accent="bad")
    chip(d, CHIP_Y, at(SHIPPED, s0="key", focus="s0", sealing=True))
    card(d, BODY_Y, 100, "bad_bg", "bad_head")
    U.warn_sign(d, M + 20, BODY_Y + 16, 9, "bad_bar", "on_bad")
    U.txt(d, "Permanent", M + 36, BODY_Y + 6, "bold18", "bad", "bad_bg")
    U.para(d, "Your key can never be changed after this.", M + 12, BODY_Y + 32, W - 2 * M - 24,
           "bold14", "bad_text", "bad_bg", 18, BODY_Y + 68)
    U.para(d, "Lose the chip: your Safe's other owners swap it out.", M + 12, BODY_Y + 68, W - 2 * M - 24,
           "sans12", "bad_muted", "bad_bg", 15, BODY_Y + 98)
    U.txt(d, "Armed · hold A for 3 s", M, 188, "sans12", "ok")
    U.txt_r(d, "key " + key, W - M, 188, "mono13", "muted")
    hold_bar(d, 0.7, red=True)
    hints(d, (("Y", "Back"),))
    d.show()


def u5_done(d, owner):
    head(d, "Your key", 6, 6)
    chip(d, CHIP_Y, at(SHIPPED, s0="key", sealed=True))
    U.mark(d, True, M + 10, BODY_Y + 10, 10)
    U.txt(d, "Your key is ready", M + 26, BODY_Y, "bold18")
    blockie(d, owner, M, BODY_Y + 28, 5)
    U.txt(d, "Safe owner address", M + 50, BODY_Y + 26, "sans12", "muted")
    U.txt(d, owner[:10] + "…" + owner[-6:], M + 50, BODY_Y + 44, "mono13", "text")
    card(d, BODY_Y + 72, 64, "warn_bg", "warn_head")
    U.txt(d, "A signer, not a wallet", M + 12, BODY_Y + 77, "bold14", "warn_text", "warn_bg")
    U.para(d, "Don't send ETH or tokens here. Funds go to your Safe.", M + 12, BODY_Y + 96, W - 2 * M - 24,
           "sans12", "warn_muted", "warn_bg", 15, BODY_Y + 134)
    hints(d, (("A", "Next: your Safe"),))
    d.show()


def u_bad(d):
    d.fill(U.c("bad_bg"))
    U.rrect(d, 0, 0, W, 24, 0, "bad_head")
    U.txt(d, "Check the brand", M, 4, "bold14", "on_bad", "bad_head")
    chip(d, CHIP_Y + 4, {"cfg": "locked", "data": "locked", "otp": "bad", "dead": "zero", "s8": "sig"})
    U.mark(d, False, M + 10, BODY_Y + 16, 10)
    U.txt(d, "Not a PicoQuorum key", M + 26, BODY_Y + 6, "bold18", "bad_text", "bad_bg")
    U.para(d, "Its brand doesn't verify. Nothing was written to it.", M, BODY_Y + 36, W - 2 * M,
           "sans14", "bad_text", "bad_bg", 18, BODY_Y + 76)
    U.para(d, "Don't use it. Tell the project the number on its label.", M, BODY_Y + 80, W - 2 * M,
           "sans12", "bad_muted", "bad_bg", 16, BODY_Y + 120)
    hints(d, (("A", "OK"),), bg="bad_bg")
    d.show()


# ----------------------------------------------------------------------------- the bench: brand
def b1_preflight(d):
    head(d, "Brand · bench", 1, 7, accent="stake")
    chip(d, CHIP_Y, FACTORY)
    U.txt(d, "A factory chip", M, BODY_Y, "bold18")
    for i, (ok, s) in enumerate(((True, "ATECC608C, self-test ok"), (True, "Nothing locked yet"),
                                 (True, "Factory table saved"))):
        fact(d, ok, s, BODY_Y + 26 + i * 19, bg="bg")
    U.txt(d, "Reads only. Changes nothing.", M, 188, "sans12", "muted")
    hints(d, (("A", "Next"), ("Y", "Stop")))
    d.show()


def b3_config(d):
    head(d, "Brand · bench", 3, 7, accent="bad")
    chip(d, CHIP_Y, at(FACTORY, focus="cfg"))
    red_card(d, "Lock the config", "Slot rules fixed for good.",
             "The chip checks the table's CRC first.")
    armed(d, 0.55, red=True)
    d.show()


def b5_sign(d, number):
    head(d, "Brand · bench", 5, 7, accent="stake")
    chip(d, CHIP_Y, at(BRANDING, s8="sig", focus="s8"), number)
    U.txt(d, "Key 0000 signs it", M, BODY_Y, "bold18")
    card(d, BODY_Y + 26, 74)
    logo_mark(d, M + 22, BODY_Y + 50, 0.9)
    U.txt(d, "PicoQuorum key 0000", M + 40, BODY_Y + 32, "bold14", "text", "surface")
    U.txt(d, "the brand key, on I2C1", M + 40, BODY_Y + 50, "sans12", "muted", "surface")
    U.txt(d, "Signature into slot 8: ok", M + 40, BODY_Y + 72, "sans12", "stake", "surface")
    U.txt(d, "Rewritable until the data lock.", M, 188, "sans12", "muted")
    hints(d, (("A", "Next"), ("Y", "Back")))
    d.show()


def b4_brand(d, number, batch):
    head(d, "Brand · bench", 4, 7, accent="stake")
    chip(d, CHIP_Y, BRANDING, number)
    U.txt(d, "Write the brand", M, BODY_Y, "bold18")
    card(d, BODY_Y + 26, 74)
    U.txt(d, "PicoQuorum · quorum v2", M + 12, BODY_Y + 32, "sans14", "text", "surface")
    U.txt(d, "Key %s · batch %d · zeros elsewhere" % (number, batch), M + 12, BODY_Y + 52, "sans12", "muted", "surface")
    U.txt(d, "No key is made here.", M + 12, BODY_Y + 72, "bold14", "stake", "surface")
    U.txt(d, "Rewritable until the data lock.", M, 188, "sans12", "muted")
    hints(d, (("A", "Write"), ("Y", "Back")))
    d.show()


def b6_lock(d):
    head(d, "Brand · bench", 6, 7, accent="bad")
    chip(d, CHIP_Y, LOCKING)
    red_card(d, "Lock the data", "The brand and every slot freeze for good.",
             "Then only the chip's own GenKey can fill slot 0.")
    armed(d, 0.3, red=True)
    d.show()


def b7_ready(d, number, brand):
    head(d, "Brand · bench", 7, 7, accent="stake")
    chip(d, CHIP_Y, SHIPPED, number)
    U.mark(d, True, M + 10, BODY_Y + 10, 10)
    U.txt(d, "Ready to ship", M + 26, BODY_Y, "bold18")
    for i, (ok, s) in enumerate(((True, "Brand signed by key 0000"), (True, "Locked 00/00, checked"),
                                 (False, "No key inside: slot 0 empty"))):
        fact(d, ok, s, BODY_Y + 26 + i * 19, bg="bg")
    blockie(d, brand, M, 172, 5)
    U.txt(d, "Print the label", M + 50, 170, "sans12", "muted")
    U.txt(d, number, M + 50, 184, "bold18", "text")
    hints(d, (("A", "Print"), ("B", "Next chip")))
    d.show()


def stages(d, number="0042"):
    """One card for the doc: the chip at each point, from the factory to a sealed key."""
    d.fill(U.c("bg"))
    rows = (("1 Factory", FACTORY), ("2 Branded", SHIPPED),
            ("3 Key made", at(SHIPPED, s0="key")), ("4 Sealed", at(SHIPPED, s0="key", sealed=True)))
    for i, (label, st) in enumerate(rows):
        chip(d, 6 + i * 58, st, number, label)
    d.show()


def blockie(d, seed, x, y, scale):
    blockies.draw(d, seed, x, y, scale)
