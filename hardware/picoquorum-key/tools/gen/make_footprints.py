"""Build the project footprint library hardware/lib/console.pretty from bundled and LCSC footprints.

  python3 tools/gen/make_footprints.py

  console:ESP32-S3-WROOM-1_HandSolder   bundled footprint, castellation pads lengthened 1.0 mm outward
                                        for an iron, 0.2 mm thermal-via holes under pad 41 removed
                                        (JLCPCB's 2-layer minimum drill is 0.3 mm)
  console:SW_Tact_4.5x4.5_C2897501      LCSC footprint; diagonal pads numbered 1 and 2, the other two
                                        unnumbered, so the switch works whichever way its pins pair
  console:FPC_0.5mm_8P_C2919492         LCSC footprint; the two hold-down tabs numbered MP
  console:USB_C_Receptacle_HRO_TYPE-C-31-M-12_Edge   bundled footprint, silk off the board edge,
                                        GND contacts solid, the shell slots' rings 0.25 mm
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sexp import parse, dumps, QStr, find, find_all  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
KICAD_FP = os.environ.get("KICAD_FOOTPRINT_DIR",
                          "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
JLC = os.path.join(ROOT, "hardware/lib/jlc.pretty")
OUT = os.path.join(ROOT, "hardware/lib/console.pretty")
os.makedirs(OUT, exist_ok=True)


def load(path):
    return parse(open(path).read())


def save(fp, name, descr):
    fp[1] = QStr(name)
    d = find(fp, "descr")
    if d:
        d[1] = QStr(descr)
    else:
        fp.insert(2, ["descr", QStr(descr)])
    with open(os.path.join(OUT, name + ".kicad_mod"), "w") as f:
        f.write(dumps(fp) + "\n")
    print("wrote", name)


def set_model(fp, filename):
    """Point the model at the project's console.3dshapes copy: easyeda2kicad's models moved onto
    z = 0 and cut to the fitted part's height by tools/gen/fix_models.py. The .wrl is named so that
    a STEP export with --subst-models picks up its .step twin; neither needs an offset or scale."""
    for m in find_all(fp, "model"):
        m[1] = QStr("${KIPRJMOD}/../lib/console.3dshapes/" + filename)


def trim_silk(fp, ymin=None, ymax=None):
    """Drop silk lines lying beyond ymin/ymax and clip the ones that cross them."""
    keep = []
    for x in fp:
        if isinstance(x, list) and x and x[0] == "fp_line" and str(find(x, "layer")[1]) in ("F.SilkS", "F.Silkscreen"):
            a, b = find(x, "start"), find(x, "end")
            ys = [float(a[2]), float(b[2])]
            lo, hi = (ymin if ymin is not None else -1e9), (ymax if ymax is not None else 1e9)
            if all(y < lo for y in ys) or all(y > hi for y in ys) or (ys[0] == ys[1] and not lo <= ys[0] <= hi):
                continue
            for pt in (a, b):
                pt[2] = min(max(float(pt[2]), lo), hi)
        keep.append(x)
    fp[:] = keep


def pad_number(p):
    return str(p[1])


# --- module -------------------------------------------------------------------------------------
fp = load(os.path.join(KICAD_FP, "RF_Module.pretty", "ESP32-S3-WROOM-1.kicad_mod"))
EXT = 1.0
keep = []
for x in fp:
    if isinstance(x, list) and x and x[0] == "pad":
        num, kind = pad_number(x), x[2]
        if num == "41" and kind == "thru_hole":
            continue                                   # 0.2 mm via holes under the exposed pad
        if num.isdigit() and 1 <= int(num) <= 40:
            at, size = find(x, "at"), find(x, "size")
            cx, cy = float(at[1]), float(at[2])
            ang = float(at[3]) if len(at) > 3 else 0.0
            w, h = float(size[1]), float(size[2])
            if int(ang) % 180 == 90:
                w, h = h, w
            x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
            n = int(num)
            if n <= 14:
                x0 -= EXT
            elif n <= 26:
                y1 += EXT
            else:
                x1 += EXT
            at[1:] = [round((x0 + x1) / 2, 4), round((y0 + y1) / 2, 4)]
            size[1:] = [round(x1 - x0, 4), round(y1 - y0, 4)]
    keep.append(x)
fp[:] = keep
trim_silk(fp, ymin=-12.4)            # the antenna end sits on the board edge
save(fp, "ESP32-S3-WROOM-1_HandSolder",
     "ESP32-S3-WROOM-1 for hand soldering: castellation pads +1.0 mm outward, no thermal vias under "
     "pad 41 (leave it unsoldered, datasheet section 9). Based on KiCad's RF_Module:ESP32-S3-WROOM-1.")

# --- tactile switch -----------------------------------------------------------------------------
fp = load(os.path.join(JLC, "SW-SMD_4P-L4.5-W4.5-P3.00-LS6.8.kicad_mod"))
for p in find_all(fp, "pad"):
    at = find(p, "at")
    x, y = float(at[1]), float(at[2])
    p[1] = QStr("1" if (x < 0 and y < 0) else "2" if (x > 0 and y > 0) else "")
set_model(fp, "SW_Tact_4.5x4.5x3.8.wrl")          # generic 6.5 mm model, cut to the part's 3.8 mm
save(fp, "SW_Tact_4.5x4.5_C2897501",
     "BOOMELE 4.5x4.5x3.8 SMD tact (LCSC C2897501). Diagonal pads are the switch terminals; "
     "the other two are mechanical, so either internal pairing works.")

# --- FPC / ZIF ----------------------------------------------------------------------------------
fp = load(os.path.join(JLC, "FPC-SMD_8P-P0.50_HDGC_0.5K-HX-8PWB.kicad_mod"))
for p in find_all(fp, "pad"):
    if pad_number(p) in ("9", "10"):
        p[1] = QStr("MP")
    else:
        p[1] = QStr(pad_number(p))
set_model(fp, "FPC_0.5mm_8P_closed.wrl")          # actuator closed: 1.0 mm
save(fp, "FPC_0.5mm_8P_C2919492",
     "HDGC 0.5K-HX-8PWB 8-pin 0.5 mm flip-lock FPC connector, double-sided contacts (LCSC C2919492). "
     "Front-insert, back-flip: the ribbon enters on the hold-down (MP) side, local +y; the actuator "
     "and the contact solder tails are at the rear, local -y.")

# --- USB-C receptacle: bundled footprint, silk kept off the board edge ----------------------------
fp = load(os.path.join(KICAD_FP, "Connector_USB.pretty", "USB_C_Receptacle_HRO_TYPE-C-31-M-12.kicad_mod"))
trim_silk(fp, ymax=3.2)              # the receptacle's face is flush with the board edge at y = 3.65
# the GND contacts sit at the board edge, where a thermal relief only finds room for one spoke:
# connect them solid (a 16-pin part does not tombstone)
for x in fp:
    if isinstance(x, list) and x and x[0] == "pad" and pad_number(x) in ("A1", "A12", "B1", "B12"):
        x.append(["zone_connect", "2"])
# the shell's plated slots: KiCad's pads leave a 0.20 mm ring, JLCPCB's least for a plated hole.
# 0.1 mm more each way makes it 0.25 (the same change as PicoQuorum's console-s3 made)
for x in fp:
    if isinstance(x, list) and x and x[0] == "pad" and pad_number(x) == "SH":
        size = find(x, "size")
        size[1], size[2] = round(float(size[1]) + 0.1, 3), round(float(size[2]) + 0.1, 3)
# KiCad ships no HRO model; GCT USB4105 is the same 16-pin top-mount shape (pads within 0.04 mm)
for m in find_all(fp, "model"):
    m[1] = QStr("${KICAD10_3DMODEL_DIR}/Connector_USB.3dshapes/"
                "USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step")
save(fp, "USB_C_Receptacle_HRO_TYPE-C-31-M-12_Edge",
     "HRO TYPE-C-31-M-12 (LCSC C165948), face flush with the board edge; silk trimmed back from the edge. "
     "Based on KiCad's Connector_USB footprint.")
