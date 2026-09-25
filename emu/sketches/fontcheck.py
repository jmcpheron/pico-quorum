# Font check: every size on the dark and light backgrounds (tools/fonts/gen.py, firmware/fonts.py).
import lcd as L
import fonts as F
d = L.LCD()
BG, INK = (11, 13, 17), (242, 244, 247)
d.fill(L.color(*BG))
y = 4
for name, s in (("sans12", "sans12 captions 0O 1lI 8B 5S"), ("sans14", "sans14 body: Send 0.05 ETH to Carol"),
                ("bold14", "bold14 APPROVALS 1 of 2"), ("bold18", "bold18 Hold to sign"),
                ("bold26", "Send 0.05 ETH"), ("mono13", "0x7099 7970 c518 12dc 3a01"), ("monob28", "7f99 f59f")):
    F.text(d, s, 6, y, name, INK, BG)
    y += F.height(name)
d.fill_rect(0, y, 240, 240 - y, L.color(246, 247, 249))
F.text(d, "Light: Send 0.05 ETH", 6, y + 4, "bold18", (16, 19, 24), (246, 247, 249))
F.text(d, "0x90f7 9bf6 eb2c 4f87 0365", 6, y + 30, "mono13", (84, 92, 104), (246, 247, 249))
d.show()
print({n: (F.width("0x7099 7970 c518 12dc 3a01", n), F.height(n)) for n in F.FILES})


def start():
    pass
start()
