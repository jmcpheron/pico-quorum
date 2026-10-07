# Mockups of the branded-key ceremony (docs/BRANDED-KEYS.md) in the console's own look: the
# drawing kit, fonts and colours of quorum_ui.py. Run on the emulator by tools/board/shots_brand.mjs.
# Not firmware: no image carries this file, and nothing here touches a chip.
import quorum_ui as U
import fonts as F
import blockies
from array import array

W = U.W
M = U.M


def logo_mark(d, cx, cy, s=1.0):
    """The PicoQuorum mark: five owners, three signed, their triangle (docs/brand/mark-dark.svg)."""
    p = lambda v: int(v * s)
    d.poly(cx, cy, array("h", [0, p(-12), p(7), p(9.7), p(-7), p(9.7)]), U.c((95, 222, 126)), True)
    for x, y, r, col in ((0, -12, 3, "ok"), (7, 9.7, 3, "ok"), (-7, 9.7, 3, "ok"), (11.4, -3.7, 2, "warn"), (-11.4, -3.7, 2, "warn")):
        d.ellipse(cx + p(x), cy + p(y), max(1, p(r)), max(1, p(r)), U.c(col), True)


def head(d, title, step, steps, accent="ok", bg="bg"):
    """The mark, the flow's name, and the step as dots."""
    d.fill(U.c(bg))
    logo_mark(d, 18, 16, 0.85)
    U.txt(d, title, 32, 6, "bold14", "text", bg)
    x = W - M - steps * 12 + 4
    for i in range(1, steps + 1):
        col = accent if i == step else ("muted" if i < step else "raised")
        r = 4 if i == step else 3
        d.ellipse(x + (i - 1) * 12, 16, r, r, U.c(col), True)


def fact(d, ok, s, y, bg="surface", font="sans14"):
    """One plain line with a check or a cross in front."""
    U.mark(d, ok, M + 17, y + 9, 7)
    U.txt(d, s, M + 30, y, font, "text", bg)


def card(d, y, h, col="surface", edge=None):
    if edge:
        U.rrect(d, M, y, W - 2 * M, h, 10, edge)
        U.rrect(d, M + 2, y + 2, W - 2 * M - 4, h - 4, 9, col)
    else:
        U.rrect(d, M, y, W - 2 * M, h, 10, col)


def hints(d, items, y=222, bg="bg"):
    x = M + 6
    for key, what in items:
        U.badge(d, key, x, y, "raised", "text")
        x = U.txt(d, what, x + 13, y - 8, "sans12", "muted", bg) + 14


def hold_bar(d, frac, red=False, y=196):
    U.rrect(d, M, y, W - 2 * M, 10, 5, "raised")
    w = int((W - 2 * M) * frac)
    if w >= 10:
        U.rrect(d, M, y, w, 10, 5, "bad_bar" if red else "ok")


def blockie(d, seed, x, y, scale):
    blockies.draw(d, seed, x, y, scale)


# ----------------------------------------------------------------------------- the user: claim
def u0_welcome(d, number, batch):
    head(d, "New key", 1, 6)
    logo_mark(d, W // 2, 62, 2.4)
    U.txt_c(d, "A PicoQuorum key", 92, "bold18")
    U.txt_c(d, "Key %s · batch %d" % (number, batch), 116, "sans14", "muted")
    card(d, 140, 66)
    U.txt(d, "No key inside it yet.", M + 12, 148, "bold14", "text", "surface")
    U.para(d, "This console makes your key in the chip, in about a minute.", M + 12, 168, W - 2 * M - 24,
           "sans12", "muted", "surface", 16, 204)
    hints(d, (("A", "Start"), ("Y", "Not now")))
    d.show()


def u1_brand(d, number, brand):
    head(d, "Check the brand", 2, 6)
    U.mark(d, True, M + 14, 46, 13)
    U.txt(d, "Made by PicoQuorum", M + 34, 36, "bold18")
    card(d, 66, 76)
    for i, s in enumerate(("Signed by PicoQuorum key 0000", "Locked at the bench", "Never used: 0 signatures")):
        fact(d, True, s, 72 + i * 22, font="sans12")
    blockie(d, brand, M, 152, 6)
    U.txt(d, "Your label says", M + 58, 152, "sans12", "muted")
    U.txt(d, number, M + 58, 168, "monob28", "text")
    hints(d, (("A", "It matches"), ("Y", "It doesn't")))
    d.show()


def u2_make(d):
    head(d, "Make your key", 3, 6)
    U.txt(d, "Your key is made", M, 30, "bold18")
    U.txt(d, "inside the chip", M, 52, "bold18")
    card(d, 80, 104)
    U.txt(d, "WHAT THIS KEY IS", M + 12, 86, "sans12", "faint", "surface")
    fact(d, True, "Signs your Safe's approvals", 104, font="sans12")
    fact(d, False, "Can't hold ETH, tokens or funds", 126, font="sans12")
    fact(d, False, "Can't be copied or read out", 148, font="sans12")
    U.txt(d, "Armed · hold A for 3 s", M, 188, "sans12", "ok")
    hold_bar(d, 0.45, y=205)
    hints(d, (("Y", "Back"),), y=228)
    d.show()


def u3_test(d):
    head(d, "Test it", 4, 6)
    U.rrect(d, U.OX + 70, 60, 100, 8, 4, "raised")
    U.rrect(d, U.OX + 70, 60, 64, 8, 4, "stake")
    U.txt_c(d, "Testing your key", 86, "bold26")
    U.txt_c(d, "Two test signatures, checked here.", 126, "sans14", "text")
    U.txt_c(d, "Nothing leaves this console.", 148, "sans12", "muted")
    d.show()


def u4_seal(d, key):
    head(d, "Seal your key", 5, 6, accent="bad")
    U.warn_sign(d, M + 14, 48, 13, "bad_bar", "on_bad")
    U.txt(d, "Permanent", M + 34, 36, "bold18", "bad")
    card(d, 70, 110, "bad_bg", "bad_head")
    U.para(d, "After this, your key can never be changed or replaced.", M + 12, 78, W - 2 * M - 24,
           "bold14", "bad_text", "bad_bg", 18, 136)
    U.para(d, "Lose the chip, and your Safe's other owners swap it out.", M + 12, 136, W - 2 * M - 24,
           "sans12", "bad_muted", "bad_bg", 16, 178)
    U.txt(d, "key " + key, M, 184, "mono13", "muted")
    hold_bar(d, 0.7, red=True, y=205)
    hints(d, (("Y", "Back"),), y=228)
    d.show()


def u5_done(d, owner):
    head(d, "Your key", 6, 6)
    U.mark(d, True, M + 14, 46, 13)
    U.txt(d, "Your key is ready", M + 34, 36, "bold18")
    blockie(d, owner, M, 70, 6)
    U.txt(d, "Safe owner address", M + 58, 70, "sans12", "muted")
    U.txt(d, owner[:12], M + 58, 86, "mono13", "text")
    U.txt(d, "…" + owner[-8:], M + 58, 102, "mono13", "text")
    card(d, 128, 74, "warn_bg", "warn_head")
    U.txt(d, "A signer, not a wallet", M + 12, 134, "bold14", "warn_text", "warn_bg")
    U.para(d, "Don't send ETH or tokens here. Funds go to your Safe.", M + 12, 154, W - 2 * M - 24,
           "sans12", "warn_muted", "warn_bg", 16, 200)
    hints(d, (("A", "Next: your Safe"),))
    d.show()


def u_bad(d):
    d.fill(U.c("bad_bg"))
    U.rrect(d, 0, 0, W, 30, 0, "bad_head")
    U.txt(d, "Check the brand", M, 6, "bold14", "on_bad", "bad_head")
    U.mark(d, False, W // 2, 70, 24)
    U.txt_c(d, "Not a PicoQuorum key", 104, "bold18", "bad_text", "bad_bg")
    U.para(d, "Its brand doesn't verify. Nothing was written to it.", M + 6, 136, W - 2 * M - 12,
           "sans14", "bad_text", "bad_bg", 18, 180)
    U.para(d, "Don't use it. Tell the project the number on its label.", M + 6, 176, W - 2 * M - 12,
           "sans12", "bad_muted", "bad_bg", 16, 212)
    hints(d, (("A", "OK"),), bg="bad_bg")
    d.show()


# ----------------------------------------------------------------------------- the bench: brand
def b4_brand(d, number, batch):
    head(d, "Brand · bench", 4, 7, accent="stake")
    U.txt(d, "Write the brand", M, 30, "bold18")
    card(d, 60, 92)
    U.txt(d, "INTO OTP AND SLOT 8", M + 12, 66, "sans12", "faint", "surface")
    U.txt(d, "PicoQuorum · quorum v2", M + 12, 84, "sans14", "text", "surface")
    U.txt(d, "%s · batch %d" % (number, batch), M + 12, 104, "mono13", "text", "surface")
    U.txt(d, "No key is made here.", M + 12, 126, "bold14", "stake", "surface")
    U.txt(d, "Rewritable until the data lock.", M, 162, "sans12", "muted")
    hints(d, (("A", "Write"), ("Y", "Back")))
    d.show()


def b6_lock(d):
    head(d, "Brand · bench", 6, 7, accent="bad")
    U.warn_sign(d, M + 14, 48, 13, "bad_bar", "on_bad")
    U.txt(d, "Lock the data", M + 34, 36, "bold18", "bad")
    card(d, 70, 106, "bad_bg", "bad_head")
    U.para(d, "The brand and every slot are frozen for good.", M + 12, 78, W - 2 * M - 24,
           "bold14", "bad_text", "bad_bg", 18, 130)
    U.para(d, "After this only the chip's own GenKey can fill slot 0.", M + 12, 120, W - 2 * M - 24,
           "sans12", "bad_muted", "bad_bg", 16, 170)
    U.txt(d, "Armed · hold A for 3 s", M, 186, "sans12", "ok")
    hold_bar(d, 0.3, red=True, y=205)
    hints(d, (("Y", "Back"),), y=228)
    d.show()


def b7_ready(d, number, brand):
    head(d, "Brand · bench", 7, 7, accent="stake")
    U.mark(d, True, M + 14, 46, 13)
    U.txt(d, "Ready to ship", M + 34, 36, "bold18")
    card(d, 66, 76)
    for i, (ok, s) in enumerate(((True, "Brand signed by key 0000"), (True, "Locked 00/00, checked"),
                                 (False, "No key inside: slot 0 empty"))):
        fact(d, ok, s, 72 + i * 22, font="sans12")
    blockie(d, brand, M, 152, 6)
    U.txt(d, "Print the label", M + 58, 152, "sans12", "muted")
    U.txt(d, number, M + 58, 168, "monob28", "text")
    hints(d, (("A", "Print"), ("B", "Next chip")))
    d.show()
