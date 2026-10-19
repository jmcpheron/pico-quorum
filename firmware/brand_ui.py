# The brand bench's screens (brand.py), and the claim's on a user's console (claim.py), in the console's own look: quorum_ui.py's drawing kit, fonts
# and colours, as docs/BRANDED-KEYS.md drew them. Every step shows the chip under its header: the
# package, the OTP zone with the brand, the sixteen slots, a padlock for each zone, and what the
# step writes ringed, so the wizard reads as the chip filling in.
#
# The kit (chip, head, card, red_card, hold_bar...) is also what tools/board/brand_screens.py draws
# the doc's mockups with. UI is provision.UI with this drawing: the same knob and A/B/X/Y handling,
# the same gates (ALLOW_*, the arm, a 3 s hold), only the pictures differ.
from array import array
import time
import quorum_ui as U
import chipcfg
import signer as S
import provision as P

W = U.W
M = U.M
BRAND = (122, 146, 255)         # Ether blue: written on the bench (the diagrams use it too)
KEY = (52, 199, 89)             # signed green: your key
BODY = (30, 35, 44)             # the package
CHIP_Y = 26
BODY_Y = 84                     # where a step's own content starts, under the chip


# ----------------------------------------------------------------------------- the kit
def logo_mark(d, cx, cy, s=1.0):
    """The PicoQuorum mark: five owners, three signed, their triangle (docs/brand/mark-dark.svg)."""
    p = lambda v: int(v * s)
    d.poly(cx, cy, array("h", [0, p(-12), p(7), p(9.7), p(-7), p(9.7)]), U.c((95, 222, 126)), True)
    for x, y, r, col in ((0, -12, 3, "ok"), (7, 9.7, 3, "ok"), (-7, 9.7, 3, "ok"), (11.4, -3.7, 2, "warn"), (-11.4, -3.7, 2, "warn")):
        d.ellipse(cx + p(x), cy + p(y), max(1, p(r)), max(1, p(r)), U.c(col), True)


def padlock(d, x, y, shut, col):
    """A 9 x 11 padlock: the shackle closed or swung open."""
    col = U.c(col)
    d.fill_rect(x, y + 5, 9, 6, col)
    if shut:
        d.rect(x + 2, y, 5, 6, col)
    else:
        d.rect(x + 5, y - 2, 5, 6, col)
        d.fill_rect(x + 5, y + 3, 1, 2, U.c(BODY))


def dashed(d, x, y, w, h, col):
    col = U.c(col)
    for i in range(x, x + w, 4):
        d.hline(i, y, 2, col)
        d.hline(i, y + h - 1, 2, col)
    for j in range(y, y + h, 4):
        d.vline(x, j, 2, col)
        d.vline(x + w - 1, j, 2, col)


def ring(d, x, y, w, h, col, thick=True):
    """The part this step writes: an outline around it (1 px around a slot)."""
    d.rect(x - 2, y - 2, w + 4, h + 4, U.c(col))
    if thick:
        d.rect(x - 3, y - 3, w + 6, h + 6, U.c(col))


def chip(d, y, st, number="0042", title="ATECC608C"):
    """The chip as it stands. st: cfg/data "open"|"locked", otp "empty"|"brand"|"bad",
    s8 "empty"|"sig", dead "factory"|"zero", s0 "empty"|"filling"|"key", sealed bool,
    s1 (quorum v3) "empty"|"filling"|"key", sealed1 bool, focus None|"cfg"|"otp"|"s8"|"data"|"s0"|"s1"."""
    x0, w, h = M, W - 2 * M, 50
    U.rrect(d, x0, y, w, h, 6, "line")
    U.rrect(d, x0 + 1, y + 1, w - 2, h - 2, 5, BODY)
    d.ellipse(x0 + 7, y + 7, 2, 2, U.c("faint"), True)                     # pin 1
    branded = st.get("otp") == "brand"
    if branded:
        logo_mark(d, x0 + 20, y + 11, 0.5)
    U.txt(d, title, x0 + (30 if branded else 14), y + 2, "sans12", "muted", BODY)
    # the two zone locks, top right
    x = x0 + w - 8
    for name in ("data", "cfg"):
        shut = st.get(name) == "locked"
        x -= U.F.width(name, "sans12")
        U.txt(d, name, x, y + 2, "sans12", "text" if shut else "faint", BODY)
        padlock(d, x - 12, y + 5, shut, "text" if shut else "faint")
        if st.get("focus") == name:
            ring(d, x - 13, y + 3, U.F.width(name, "sans12") + 14, 13, "bad")
        x -= 22
    # OTP: the brand record
    ox, oy, ow, oh = x0 + 8, y + 24, 72, 19
    if branded:
        U.rrect(d, ox, oy, ow, oh, 4, BRAND)
        logo_mark(d, ox + 10, oy + 10, 0.42)
        U.txt(d, number, ox + 22, oy + 1, "bold14", (11, 13, 17), BRAND)
    elif st.get("otp") == "bad":
        U.rrect(d, ox, oy, ow, oh, 4, "bad_bar")
        U.txt(d, "brand ?", ox + 10, oy + 1, "bold14", "on_bad", "bad_bar")
    else:
        dashed(d, ox, oy, ow, oh, "faint")
        U.txt(d, "OTP", ox + 24, oy + 2, "sans12", "faint", BODY)
    if st.get("focus") == "otp":
        ring(d, ox, oy, ow, oh, "stake")
    # the sixteen slots: 0-7 on top, 8-15 below
    gx, gy, cw, ch = x0 + 90, y + 24, 14, 8
    for n in range(16):
        cx, cy = gx + (n % 8) * 16, gy + (n // 8) * 11
        if n == 0:
            s0 = st.get("s0", "empty")
            if s0 == "key":
                d.fill_rect(cx, cy, cw, ch, U.c(KEY))
            elif s0 == "filling":
                d.fill_rect(cx, cy, cw // 2, ch, U.c(KEY))
                d.rect(cx, cy, cw, ch, U.c(KEY))
            else:
                dashed(d, cx, cy, cw, ch, KEY)
            if st.get("sealed"):
                d.rect(cx - 1, cy - 1, cw + 2, ch + 2, U.c("text"))
            if st.get("focus") == "s0":
                ring(d, cx, cy, cw, ch, "bad" if st.get("sealing") else "ok", False)
        elif n == 1 and st.get("s1"):
            # quorum v3: the attestation key, made and sealed on the bench
            if st["s1"] == "key":
                d.fill_rect(cx, cy, cw, ch, U.c(BRAND))
            elif st["s1"] == "filling":
                d.fill_rect(cx, cy, cw // 2, ch, U.c(BRAND))
                d.rect(cx, cy, cw, ch, U.c(BRAND))
            else:
                dashed(d, cx, cy, cw, ch, BRAND)
            if st.get("sealed1"):
                d.rect(cx - 1, cy - 1, cw + 2, ch + 2, U.c("text"))
            if st.get("focus") == "s1":
                ring(d, cx, cy, cw, ch, "bad" if st.get("sealing") else "stake", False)
        elif n == 8:
            if st.get("s8") == "sig":
                d.fill_rect(cx, cy, cw, ch, U.c(BRAND))
            else:
                dashed(d, cx, cy, cw, ch, BRAND)
            if st.get("focus") == "s8":
                ring(d, cx, cy, cw, ch, "stake", False)
        else:
            if st.get("dead", "factory") == "zero":
                d.fill_rect(cx, cy, cw, ch, U.c((58, 65, 76)))
            else:
                d.rect(cx, cy, cw, ch, U.c((58, 65, 76)))


def head(d, title, step, steps, accent="ok", bg="bg"):
    """The mark, the step's name, and the step as dots."""
    d.fill(U.c(bg))
    logo_mark(d, 18, 14, 0.8)
    U.txt(d, title, 32, 4, "bold14", "text", bg)
    x = W - M - steps * 11 + 4
    for i in range(1, steps + 1):
        col = accent if i == step else ("muted" if i < step else "raised")
        r = 4 if i == step else 3
        d.ellipse(x + (i - 1) * 11, 14, r, r, U.c(col), True)


def fact(d, ok, s, y, bg="surface", font="sans12"):
    """One plain line with a check or a cross in front."""
    U.mark(d, ok, M + 17, y + 8, 7)
    U.txt(d, s, M + 30, y, font, "text", bg)


def card(d, y, h, col="surface", edge=None):
    if edge:
        U.rrect(d, M, y, W - 2 * M, h, 10, edge)
        U.rrect(d, M + 2, y + 2, W - 2 * M - 4, h - 4, 9, col)
    else:
        U.rrect(d, M, y, W - 2 * M, h, 10, col)


def hints(d, items, y=228, bg="bg"):
    x = M + 6
    for key, what in items:
        U.badge(d, key, x, y, "raised", "text")
        x = U.txt(d, what, x + 13, y - 8, "sans12", "muted", bg) + 14


def hold_bar(d, frac, red=False, y=205):
    U.rrect(d, M, y, W - 2 * M, 8, 4, "raised")
    w = int((W - 2 * M) * frac)
    if w >= 8:
        U.rrect(d, M, y, w, 8, 4, "bad_bar" if red else "ok")


def red_card(d, title, bold, sub):
    card(d, BODY_Y, 100, "bad_bg", "bad_head")
    U.warn_sign(d, M + 20, BODY_Y + 16, 9, "bad_bar", "on_bad")
    U.txt(d, title, M + 36, BODY_Y + 6, "bold18", "bad", "bad_bg")
    U.para(d, bold, M + 12, BODY_Y + 32, W - 2 * M - 24, "bold14", "bad_text", "bad_bg", 18, BODY_Y + 68)
    U.para(d, sub, M + 12, BODY_Y + 68, W - 2 * M - 24, "sans12", "bad_muted", "bad_bg", 15, BODY_Y + 98)


# ----------------------------------------------------------------------------- the bench's steps
# The red card's two lines on each permanent step
RED = {"B3": ("Slot rules fixed for good.", "The chip checks the table's CRC first."),
       "B6": ("The brand and every slot freeze for good.", "Then only the chip's own GenKey can fill slot 0."),
       "B4b": ("The attestation key can never be replaced.", "B5 signs its public half into the brand."),
       "S3": ("This key can never be replaced.", "A spare: its key is for tests only."),
       "U4": ("Your key can never be changed.", "Lose the chip, and your Safe's other owners swap it out.")}
FOCUS = {"B2": "cfg", "B3": "cfg", "B4": "otp", "B4a": "s1", "B4b": "s1", "B5": "s8", "B6": "data", "S1": "s0", "S2": "s0",
         "S3": "s0", "S4": "s1",
         "U1": "otp", "U2": "s0", "U3": "s0", "U4": "s0"}
SWAP = {"key0000": ("Unplug this chip", "Then plug in key 0000. It signs this chip's brand, and nothing else."),
        "back": ("Key 0000 signed", "Unplug key 0000, then plug this chip back in."),
        "wrong": ("Not that one", "Chip %s isn't the one asked for. Unplug it.")}


class _Q:
    msg = None          # quorum_ui.knob_choices reads q.msg


def chip_state(c, st):
    """What the chip graphic shows for ceremony c at step st."""
    out = {"cfg": "locked" if c.config_locked else "open", "data": "locked" if c.data_locked else "open"}
    if c.branded is not None or c.data_locked:
        out["otp"], out["dead"] = "brand", "zero"
    if c.signed is not None or c.data_locked:
        out["s8"] = "sig"
    if c.key is not None:
        out["s0"] = "key"
    elif st in ("S1", "U2"):
        out["s0"] = "filling"
    out["sealed"] = bool(c.slot0["locked"])
    if st in FOCUS:
        out["focus"] = FOCUS[st]
    out["sealing"] = st in ("S3", "U4", "B4b")
    if c.profile == "quorum-v3":
        s1 = chipcfg.decode_slot(c.cfg, chipcfg.ATT_SLOT)
        out["s1"] = "key" if s1["locked"] or getattr(c, "att", None) else ("filling" if st == "B4a" else "empty")
        out["sealed1"] = s1["locked"]
    return out


def number(c):
    rec = chipcfg.brand_decode(c.branded) if c.branded else None
    return chipcfg.brand_number(rec) if rec else "????"


BENCH = ("B1", "B2", "B3", "B4", "B4a", "B4b", "B5", "B6", "B7")


def place(st):
    """(header, dot, dots): the bench's nine steps, then the spare's four; the claim's five."""
    if st[0] == "U":
        return "Claim · your key", int(st[1:]), 5
    if st in BENCH:
        return "Brand · bench", BENCH.index(st) + 1, len(BENCH)
    if st[0] == "S" and st != "S5":
        return "Spare · tests", int(st[1:]), 4
    return "Brand · bench", 0, 0


class UI(P.UI):
    def __init__(self, d, keys, sig, theme="dark", ceremony=None):
        U.use(theme)
        P.UI.__init__(self, d, keys, sig, theme, ceremony)
        self.c.say = self._say

    def _say(self, what, serial=None):
        """B5 on a real bench: what to plug in next, while it polls the bus."""
        d, c = self.d, self.c
        title, text = SWAP[what]
        d.frames(self._paint_say, title, text % serial[-8:] if serial else text, chip_state(c, "B5"), number(c), self._part())

    def _paint_say(self, title, text, state, num, part):
        d = self.d
        self._top("B5", state, num, part)
        U.txt(d, title, M, BODY_Y, "bold18", "bad" if title == SWAP["wrong"][0] else "text")
        card(d, BODY_Y + 26, 74)
        U.para(d, text, M + 12, BODY_Y + 31, W - 2 * M - 24, "sans12", "text", "surface", 15, BODY_Y + 98)
        U.txt_c(d, "Waiting for the chip…", BODY_Y + 112, "sans14", "muted")
        d.show()

    def draw(self):
        if not self.dirty:
            return
        self.dirty = False
        c = self.c
        st = c.step()
        why = self.need(st) if st not in c.FINAL else ""
        # a result shows the chip with the part that step wrote ringed, not the next step's
        self.d.frames(self._paint, st, why, chip_state(c, self.result[0] if self.result else st), number(c), self._part())

    def _part(self):
        return chipcfg.REVISIONS.get(self.c.revision, "ATECC608")

    def _top(self, st, state, num, part, accent="stake"):
        title, n, steps = place(st)
        d = self.d
        if steps:
            head(d, title, n, steps, accent)
        else:
            d.fill(U.c("bg"))
            logo_mark(d, 18, 14, 0.8)
            U.txt(d, title, 32, 4, "bold14", "text", "bg")
        chip(d, CHIP_Y, state, num, part)

    def _paint(self, st, why, state, num, part):
        d, c = self.d, self.c
        if self.result:
            self._paint_result(state, num, part)
            d.show()
            return
        perm = st in c.PERMANENT
        self._top(st, state, num, part, "bad" if perm else "stake")
        if perm:
            bold, sub = RED[st]
            red_card(d, c.TITLES[st], bold, sub)
        else:
            U.txt(d, c.TITLES[st], M, BODY_Y, "bold18")
            card(d, BODY_Y + 26, 74)
            U.para(d, c.WHAT[st], M + 12, BODY_Y + 31, W - 2 * M - 24, "sans12", "text", "surface", 15, BODY_Y + 98)
        self._paint_foot(st, why)
        d.show()

    def _paint_foot(self, st, why):
        """The bottom: the gate and the hold bar on a gated step, then what the knob or keys do."""
        d, c = self.d, self.c
        gated = st in c.PERMANENT or st in c.GENKEY
        red = st in c.PERMANENT
        go = "Check" if st in c.FINAL else ("Lock" if red else ("Make" if gated else "Do it"))
        if gated and st not in c.FINAL:
            how = "the knob" if self.knob else "A"
            if why and not why.startswith("not armed"):
                U.txt(d, U.fit(why, W - 2 * M, "sans12"), M, 188, "sans12", "bad")
            else:
                left = S.armed()
                U.txt(d, "Armed %d s · hold %s 3 s" % (left, how) if left else
                      ("Not armed · hold the knob 3 s to arm" if self.knob else "Not armed · B+Y 3 s"),
                      M, 188, "sans12", "ok" if left else "warn")
                frac = 0
                if self.hold is not None:
                    frac = min(1, time.ticks_diff(time.ticks_ms(), self.hold) / P.HOLD_MS)
                elif self.armhold is not None:
                    frac = min(1, time.ticks_diff(time.ticks_ms(), self.armhold) / P.ARM_MS)
                hold_bar(d, frac, red and bool(left))
        if self.knob:
            # an ALLOW_* flag off: nothing to do here, so the go choice stays grey even in focus
            blocked = gated and st not in c.FINAL and why and not why.startswith("not armed")
            focus = ("go", "back")[self.choice]
            U.knob_choices(d, _Q, (("go", go), ("back", "Back")), None if blocked and focus == "go" else focus, "turn · press")
        else:
            hints(d, (("A", ("Hold " + go) if gated else go), ("Y", "Back")))

    def _paint_result(self, state, num, part):
        d, c = self.d, self.c
        st, ok, checks, msg = self.result
        self._top(st, state, num, part, "ok" if ok else "bad")
        U.mark(d, ok, M + 10, BODY_Y + 10, 10)
        U.txt(d, U.fit(c.TITLES[st] if ok else "Stopped: " + c.TITLES[st], W - 2 * M - 26, "bold18"), M + 26, BODY_Y, "bold18",
              "text" if ok else "bad")
        y = BODY_Y + 26
        rows = [r for r in checks if not r[1]] + [r for r in checks if r[1]]     # what failed first
        room = (180 - y) // 16
        if len(rows) > room:
            more = len(rows) - room + 1
            log = getattr(c, "LOG", "brand-log.txt")
            rows = rows[:room - 1] + [("+%d more ok (%s)" % (more, log) if all(k for _, k in rows[room - 1:]) else
                                       "+%d more (%s)" % (more, log), True)]
        for label, good in rows:
            U.mark(d, good, M + 7, y + 8, 6)
            U.txt(d, U.fit(label, W - 2 * M - 20, "sans12"), M + 18, y, "sans12", "text" if good else "bad")
            y += 16
        U.para(d, msg, M, y + 2, W - 2 * M, "sans12", "muted", "bg", 15, 212)
        if self.knob:
            U.knob_choices(d, _Q, (("ok", "Continue"),), "ok", "press")
        else:
            hints(d, (("A", "Continue"),))

    def _busy(self, st):
        d, c = self.d, self.c
        self._top(st, chip_state(c, st), number(c), self._part())
        U.txt(d, c.TITLES[st], M, BODY_Y, "bold18")
        U.rrect(d, U.OX + 70, BODY_Y + 40, 100, 8, 4, "raised")
        U.rrect(d, U.OX + 70, BODY_Y + 40, 60, 8, 4, "stake")
        U.txt_c(d, "Working with the chip…", BODY_Y + 58, "sans14", "muted")
        d.show()
