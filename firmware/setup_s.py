# The ceremony's screen on the Feather ESP32-S3 (board "feather-s3", 240x135, lcd.THREE): the same
# steps, checks and gates as provision.UI, on its three buttons. D0 is Y (back), D1 is B and D2 is
# A, so the arm is D0+D1 held 3 s together (the B+Y arm), and a permanent or GenKey step is D2 held
# 3 s once armed, started with provision.ARM_LEFT of the arm to go. D2 is never part of the arm:
# landing it first could run a step nobody gated (C5's test signatures raise the counter). ALLOW_*,
# the 60 s arm and the holds are provision.UI's own.
# A rail down the left edge names what each button does, level with it (board.RAIL_Y), and fills
# from the bottom while the arm or a hold runs. framebuf's 8 px font: 25 characters right of it.
# On the knob Feather (board.DIAL) Boot is D0, the push D2 and a detent D1, and a turn can't be held:
# so Boot held 3 s alone is the arm (it reads as B and Y together), a detent anticlockwise is back
# (Y), and the push does the step (A). The push is still never part of the arm.
import time
import board
import lcd as L
import provision
import signer as S

PRESSED = {"D0": "Y", "D1": "B", "D1L": "B", "D2": "A"}
HELD = {"A": "D2", "B": "D1", "Y": "D0"}
ARM, DO = "D0+D1", "D2"
if board.DIAL:
    PRESSED = {"D1L": "Y", "D2": "A"}
    HELD = {"A": "D2", "B": "D0", "Y": "D0"}
    ARM, DO = "Boot", "push"
RAIL = 36
X0 = RAIL + 3
COLS = (board.W - X0) // 8
H = board.H


def wrap(s, width):
    """s in lines of at most width characters; a word longer than that (an address) in pieces."""
    out, line = [], ""
    for w in s.split():
        while len(w) > width:
            if line:
                out.append(line)
                line = ""
            out.append(w[:width])
            w = w[width:]
        if line and len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        out.append(line)
    return out


class _Keys:
    """keys.held by the Pico's names, for provision.UI.tick: A is D2, B is D1, Y is D0, X is none."""

    def __init__(self, keys):
        self.keys = keys

    def held(self, k):
        return k in HELD and self.keys.held(HELD[k])


class UI(provision.UI):
    def __init__(self, d, keys, sig, theme="dark", ceremony=None):
        super().__init__(d, _Keys(keys), sig, theme, ceremony)
        self.knob = False

    def tick(self, pressed):
        return super().tick([PRESSED[k] for k in pressed if k in PRESSED])

    def rail(self, labels, fill=None):
        """labels: a word or None for D0, D1, D2; fill: (fraction, colour) up from the bottom."""
        d, p = self.d, self.p
        if board.DIAL:                  # Boot arms, the turn (D1's row) goes back
            labels = ("Arm" if "Arm" in labels[:2] else None, "Back" if labels[0] == "Back" else None, labels[2])
        d.fill_rect(0, 0, RAIL, H, p["dim"])
        if fill:
            h = int(H * min(1, max(0, fill[0])))
            d.fill_rect(0, H - h, RAIL, h, fill[1])
        for y, lab in zip(board.RAIL_Y, labels):
            if lab:
                d.text(lab, (RAIL - 8 * len(lab)) // 2, y - 4, p["fg"])

    def _busy(self, st):
        d, p = self.d, self.p
        d.fill(p["bg"])
        self.rail((None, None, None))
        d.text((st + " " + self.c.TITLES[st])[:COLS], X0, 52, p["accent"])
        d.text("working...", X0, 66, p["fg"])
        d.show()

    def _paint(self, st, why, subtitle, note, pic=None):
        d, c, p = self.d, self.c, self.p
        d.fill(p["bg"])
        if self.result:
            self._paint_result(pic)
            return
        n = c.index(st)
        perm = st in c.PERMANENT
        gated = perm or st in c.GENKEY
        head = ("%s/%d %s" % (st, c.NSTEPS, c.TITLES[st]) if n else c.TITLES[st])[:COLS]
        if perm:
            d.fill_rect(X0 - 2, 0, board.W - X0 + 2, 12, p["bad"])
            d.text(head, X0, 2, L.WHITE)
        else:
            d.text(head, X0, 2, p["fg"])
        step_w = (board.W - X0) // c.NSTEPS
        for i in range(1, c.NSTEPS + 1):
            d.fill_rect(X0 + (i - 1) * step_w, 14, step_w - 3, 3, p["ok"] if i < n else (p["accent"] if i == n else p["dim"]))
        d.text(subtitle[:COLS], X0, 20, p["muted"])
        y = 31
        tail = []
        if perm:
            tail.append(("PERMANENT: no undo.", p["bad"]))
        if c.key:
            k = "key " + c.fingerprint()
            tail += [(k + "  " + note, p["muted"])] if note and len(k) + 2 + len(note) <= COLS else \
                [(k, p["muted"])] + ([(note[:COLS], p["muted"])] if note else [])
        elif note:
            tail.append((note[:COLS], p["muted"]))
        room = (108 - y) // 10 - len(tail)
        for line in wrap(c.WHAT[st], COLS)[:room]:
            d.text(line, X0, y, p["fg"])
            y += 10
        for line, col in tail:
            d.text(line, X0, y, col)
            y += 10
        if pic:
            import blockies
            blockies.draw(d, pic, board.W - 34, 70, 4)      # 32 px: the picture to compare in the Safe app
        self._gate(st, why, gated)
        d.show()

    def _gate(self, st, why, gated):
        """The bottom two lines and the rail: what D0-D2 do now, the arm, the hold."""
        d, c, p = self.d, self.c, self.p
        now = time.ticks_ms()
        fill = None
        if self.armhold is not None:
            fill = (time.ticks_diff(now, self.armhold) / provision.ARM_MS, p["accent"])
        elif self.armdone:
            fill = (1, p["ok"])
        elif self.hold is not None:
            fill = (time.ticks_diff(now, self.hold) / provision.HOLD_MS, p["bad"])
        left = S.armed()
        if not gated:
            labels = ("Back", None, "Do")
            lines = [(DO + (": check" if st in c.FINAL else ": do it"), p["fg"])]
        elif why and not why.startswith("not armed"):
            labels = ("Back", None, None)
            lines = [(s, p["bad"]) for s in wrap(why, COLS)[:2]]       # an ALLOW_* flag is off
        elif self.armdone:
            labels = (None, None, None)
            lines = [("Armed: let go of " + ARM, p["ok"])]
        elif self.armhold is not None:
            labels = ("Arm", "Arm", None)
            lines = [("Arming: keep holding", p["accent"]), (ARM + " for 3 s", p["muted"])]
        elif self.armnote:
            labels = ("Back", "Arm", None)
            lines = [("Let go early: not armed", p["bad"])]
        elif 0 < left < provision.ARM_LEFT and self.hold is None:
            labels = ("Back", "Arm", None)
            lines = [("Armed %d s: too little" % left, p["accent"]), ("Arm again: %s 3 s" % ARM, p["fg"])]
        elif left:
            labels = ("Back", None, "Hold")
            lines = [("Armed %d s" % left, p["ok"]), ("Hold %s 3 s to do it" % DO, p["fg"])]
        else:
            labels = ("Back", "Arm", None)
            lines = [("Not armed", p["accent"]), ("Arm: hold %s 3 s" % ARM, p["fg"])]
        self.rail(labels, fill)
        y = 124 - 11 * (len(lines) - 1)
        for s, col in lines:
            d.text(s[:COLS], X0, y, col)
            y += 11

    def _paint_result(self, pic):
        d, c, p = self.d, self.c, self.p
        st, ok, checks, msg = self.result
        msg = msg.replace("B+Y", ARM)      # a refusal is signer.gate's text, written for the Pico
        self.rail((None, None, "OK"))
        head = st + (" OK" if ok else " STOPPED")
        d.text(head, X0, 2, p["ok"] if ok else p["bad"])
        d.text(c.TITLES[st][:COLS - len(head) - 1], X0 + 8 * (len(head) + 1), 2, p["muted"])
        y = 14
        for label, good in checks:
            if y > H - 22:
                break
            d.fill_rect(X0, y + 1, 6, 6, p["ok"] if good else p["bad"])
            d.text(label[:COLS - 1], X0 + 9, y, p["fg"] if good else p["bad"])
            y += 10
        y += 2
        for line in wrap(msg, COLS - 5 if pic else COLS)[:max(0, (H - y) // 10)]:
            d.text(line, X0, y, p["fg"])
            y += 10
        if pic:
            import blockies
            blockies.draw(d, pic, board.W - 34, H - 34, 4)
        d.show()
