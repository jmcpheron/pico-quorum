# The proposed bag label for a branded key (docs/BRANDED-KEYS.md), drawn with the firmware's own
# blockies.py and qrcode.py, so the picture is the one the console draws.
#   python3 tools/board/brand_label.py [out.svg]
import os, sys, hashlib
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "firmware"))
import blockies, qrcode
SERIAL = "0123e100e1e1e1e1ee"          # the emulator's virtual chip, as in the mockups
BRAND = "0x" + hashlib.sha256(b"PicoQuorum brand v1" + bytes.fromhex(SERIAL)).digest()[:20].hex()
URL = "https://picoquorum.app/app/#/brand/" + SERIAL
data, fg, bg, spot = blockies.build(BRAND)
rgb = lambda hsl: "#%02x%02x%02x" % blockies.hsl_to_rgb(hsl)
n, rows = qrcode.encode(URL)
o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 300" width="600" height="300" font-family="Helvetica, Arial, sans-serif">',
     '<title>Proposed label for a branded PicoQuorum key: key 0042, batch 3, with the brand picture and a QR code</title>',
     '<rect x="1" y="1" width="598" height="298" rx="18" fill="#fff" stroke="#0B0D11" stroke-width="2"/>',
     '<g transform="translate(24,22) scale(1.6)"><polygon points="16.00,4.00 23.05,25.71 8.95,25.71" fill="#7AC191"/>'
     '<circle cx="16" cy="4" r="3" fill="#16963E"/><circle cx="27.41" cy="12.29" r="2" fill="#B78231"/>'
     '<circle cx="23.05" cy="25.71" r="3" fill="#16963E"/><circle cx="8.95" cy="25.71" r="3" fill="#16963E"/>'
     '<circle cx="4.59" cy="12.29" r="2" fill="#B78231"/></g>',
     '<text x="86" y="58" font-size="30" font-weight="700" fill="#0B0D11">PicoQuorum key</text>',
     '<text x="26" y="150" font-size="84" font-weight="700" fill="#0B0D11" font-family="Menlo, monospace">0042</text>',
     '<text x="28" y="186" font-size="20" fill="#3a3f47">batch 3 · ATECC608C</text>',
     '<text x="28" y="214" font-size="20" fill="#3a3f47" font-family="Menlo, monospace">serial …%s</text>' % SERIAL[-8:],
     '<text x="28" y="262" font-size="17" fill="#B00020">No key inside yet. Your console makes it.</text>']
s, x0, y0 = 12, 300, 92                                         # the brand blockie, 8 x 8 cells
for i, v in enumerate(data):
    col = rgb(bg) if v == 0 else rgb(fg) if v == 1 else rgb(spot)
    o.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (x0 + (i % 8) * s, y0 + (i // 8) * s, s, s, col))
o.append('<text x="348" y="212" font-size="15" text-anchor="middle" fill="#3a3f47">brand picture</text>')
m, qx, qy = 4, 428, 70                                          # the QR code with a 4-module quiet zone
o.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#fff"/>' % (qx, qy, (n + 8) * m, (n + 8) * m))
for r in range(n):
    for c in range(n):
        if rows[r] >> c & 1:
            o.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#000"/>' % (qx + (c + 4) * m, qy + (r + 4) * m, m, m))
o.append('<text x="%d" y="%d" font-size="15" text-anchor="middle" fill="#3a3f47">check it</text>' % (qx + (n + 8) * m // 2, qy + (n + 8) * m + 20))
o.append('</svg>')
open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs/branded-keys/label-0042.svg"), "w").write("\n".join(o))
print(BRAND, n)
