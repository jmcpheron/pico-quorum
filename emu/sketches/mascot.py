# Quo, the console's face: a v3 direction (docs/quorum-ui/v3/mascot/). A 16 x 16 pixel-art head on
# v3's palette, drawn in big pixels: 3 px in a review's band, 8 px on the face cards. Its antenna light
# takes the band's colour. Which face it wears is picked from the same review model as the band
# (face_for), never from anything Safe's service says, and it only ever adds to the band and the
# words. A design study: nothing here reads a chip or a service, and nothing signs.
#   import mascot; mascot.draw(lcd, "money", x, y, 3, light=(96, 206, 108))
import lcd as L

# v3's palette, plus a skin ramp for the head and the hands
INK, SHADE, LINE, DARK = (250, 240, 215), (206, 190, 176), (40, 30, 62), (24, 20, 37)
WHITE = (255, 255, 255)
GREEN, GREEN_D = (96, 206, 108), (34, 128, 84)
AMBER, AMBER_D, AMBER_HI = (247, 168, 52), (176, 104, 40), (255, 222, 120)
RED, RED_D = (238, 84, 100), (130, 30, 50)
BLUE, BLUE_HI = (110, 156, 240), (156, 212, 255)
PAL = {"o": LINE, "h": INK, "s": SHADE, "k": DARK, "w": WHITE, "g": GREEN, "G": GREEN_D,
       "a": AMBER, "A": AMBER_D, "y": AMBER_HI, "r": RED, "R": RED_D, "b": BLUE, "B": BLUE_HI}

# The head: an antenna whose light (L) is the band's colour, a rounded square, a shaded chin.
BASE = (
    ".......LL.......",
    ".......oo.......",
    "...oooooooooo...",
    "..ohhhhhhhhhho..",
    ".ohhhhhhhhhhhho.",
    ".ohhhhhhhhhhhho.",
    ".ohhhhhhhhhhhho.",
    ".ohhhhhhhhhhhho.",
    ".ohhhhhhhhhhhho.",
    ".ohhhhhhhhhhhho.",
    ".ohhhhhhhhhhhho.",
    ".ohhhhhhhhhhhho.",
    ".ohhhhhhhhhhhho.",
    ".oshhhhhhhhhhso.",
    "..osssssssssso..",
    "...oooooooooo...",
)

# Each face is stamps on the head: (x, y, rows), a space keeps what is under it.
HAND = (" aAaA ", "aaAaAa", "aaAaAa", "aaaaaa", "oaaaao", " oooo ")
BIG_EYE = (" kkk ", "kwwwk", "kwkwk", "kwwwk", " kkk ")
EMPTY_EYE = (" kkk ", "kwwwk", "kwwwk", "kwwwk", " kkk ")
DOLLAR = (" g ", "ggg", "g  ", "ggg", "  g", "ggg", " g ")
FACES = {
    # home: calm, looking at you
    "idle": [(4, 6, ("kw", "kk", "kk")), (10, 6, ("kw", "kk", "kk")),
             (5, 11, ("k    k", " kkkk "))],
    # home, one step in 24: a blink
    "blink": [(4, 8, ("kk",)), (10, 8, ("kk",)), (5, 11, ("k    k", " kkkk "))],
    # green, pays out: a routine send or transfer
    "money": [(3, 4, DOLLAR), (10, 4, DOLLAR),
              (3, 11, ("k        k", " kwwwwwwk ", "  kkkkkk  "))],
    # amber, changes who can act: an owner added, removed or swapped, a threshold changed
    "scared": [(3, 3, ("  kk  kk  ", "kk      kk")), (2, 5, BIG_EYE), (9, 5, BIG_EYE),
               (4, 11, (" kk  kk ", "k  kk  k")), (14, 3, (" B", "Bb", "bb"))],
    # red, takes control: one key, or someone new, could move everything
    "panic": [(3, 3, ("   k  k   ", " kk    kk ")), (2, 5, EMPTY_EYE), (9, 5, EMPTY_EYE),
              (5, 10, (" kkkk ", "kRRRRk", "kRrrRk", " kkkk ")),
              (14, 6, (" B", "Bb", "bb")), (0, 6, ("B ", "bB", "bb"))],
    # red, code nobody here can read: a module, guard or handler not in the registry, a delegatecall,
    # an EIP-7702 delegation. It won't look.
    "nolook": [(1, 4, HAND), (9, 4, HAND), (4, 11, ("kkkkkkkk", "kwkwwkwk", "kkkkkkkk"))],
    # amber, the same kind of change on purpose: the code is known and the owners approved it.
    # One eye on it, through the fingers.
    "peek": [(1, 4, HAND), (9, 4, (" aa  a", "aaA  a", "aaAkwa", "aaAkka", "oaaaao", " oooo ")),
             (6, 11, (" kk ", "k  k", " kk "))],
    # a rule says no, however long Sign is held
    "refuse": [(3, 4, ("kk      kk", "  kk  kk  ")), (4, 7, ("kk    kk", "kk    kk")),
               (5, 11, ("kkkkkk",))],
    # the service's hash or a signature doesn't match what was worked out here
    "suspect": [(3, 5, ("kkk",)), (3, 7, ("kkk",)), (10, 4, ("kkk",)), (11, 6, ("wk", "kk", "kk")),
                (5, 11, ("    kk", "kkkk  "))],
    # blue, Sign held: concentrating, tongue out
    "focus": [(3, 6, ("kkk    kkk", " kk    kk ")), (6, 11, ("kkkk", "  rk"))],
    # green, signed
    "happy": [(3, 6, (" k      k ", "k k    k k")), (4, 10, ("k      k", " kRRRRk ", "  kkkk  ")),
              (14, 0, (" y", "y ")), (0, 1, ("y", " "))],
}
ORDER = ("idle", "blink", "money", "scared", "panic", "nolook", "peek", "refuse", "suspect", "focus", "happy")
_runs = {}


def _compile(face):
    g = [list(r) for r in BASE]
    for x, y, rows in FACES[face]:
        for j, r in enumerate(rows):
            for i, c in enumerate(r):
                if c != " ":
                    g[y + j][x + i] = c
    runs = []
    for y, r in enumerate(g):
        x = 0
        while x < 16:
            c = r[x]
            x0 = x
            while x < 16 and r[x] == c:
                x += 1
            if c != ".":
                runs.append((x0, y, x - x0, c))
    return runs


def draw(d, face, x, y, px=3, light=AMBER):
    """Quo at (x, y), px screen pixels to an art pixel: 48 px square at 3."""
    if face not in _runs:
        _runs[face] = _compile(face)
    cols = {}
    for a, b, w, c in _runs[face]:
        rgb = light if c == "L" else PAL[c]
        if rgb not in cols:
            cols[rgb] = L.color(*rgb)
        d.fill_rect(x + a * px, y + b * px, w * px, px, cols[rgb])


# Which face, from the review the band comes from. The worst call in the transaction sets both, in
# this order: a mismatch, code nobody here can read, a takeover, a known control change, a change to
# who can act, a payment. A page that refuses shows "refuse" whatever the class.
WORST = ("mismatch", "unknown_control", "takes_control", "known_control", "who_can_act", "pays", "routine")
FACE = {"mismatch": "suspect", "unknown_control": "nolook", "takes_control": "panic",
        "known_control": "peek", "who_can_act": "scared", "pays": "money", "routine": "idle"}
BAND = {"mismatch": "red", "unknown_control": "red", "takes_control": "red",
        "known_control": "amber", "who_can_act": "amber", "pays": "green", "routine": "green"}


def classify(calls):
    """calls: each call's class, as the review model gives it. The worst wins."""
    return min(calls, key=WORST.index)


def face_for(page, calls=()):
    """page: "review", "refused", "holding", "signed" or "home"."""
    if page == "home":
        return "idle"
    if page == "holding":
        return "focus"
    if page == "signed":
        return "happy"
    if page == "refused":
        return "suspect" if "mismatch" in calls else "refuse"
    return FACE[classify(calls)]
