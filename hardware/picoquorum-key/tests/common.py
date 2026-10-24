"""Shared helpers for the board tests. Standard library only.

Nothing here writes to hardware/picoquorum-key: the netlist export and every mutated board go to
hardware/out/scratch/test/ (gitignored).
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRJ = os.path.join(ROOT, "hardware", "picoquorum-key")
# CONSOLE_SCH / CONSOLE_PCB point the whole suite at another copy (a mutated board, a later rev).
SCH = os.environ.get("CONSOLE_SCH", os.path.join(PRJ, "picoquorum-key.kicad_sch"))
PCB = os.environ.get("CONSOLE_PCB", os.path.join(PRJ, "picoquorum-key.kicad_pcb"))
SCRATCH = os.path.join(ROOT, "hardware", "out", "scratch", "test")
KICAD_SYMBOLS = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"
KICAD_PYTHON = os.environ.get(
    "KICAD_PYTHON", "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3")

sys.path.insert(0, os.path.join(ROOT, "tools", "gen"))
from sexp import parse, find, find_all  # noqa: E402


def scratch(*parts):
    path = os.path.join(SCRATCH, *parts)
    os.makedirs(os.path.dirname(path) if os.path.splitext(path)[1] else path, exist_ok=True)
    return path


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def tree_of(path):
    with open(path) as f:
        return parse(f.read())


def pcb_pad_nets(pcb_path=PCB):
    """{(ref, pad): net} for every pad on the board."""
    out = {}
    for fp in find_all(tree_of(pcb_path), "footprint"):
        ref = next(p[2] for p in find_all(fp, "property") if p[1] == "Reference")
        for pad in find_all(fp, "pad"):
            net = find(pad, "net")
            out[(str(ref), str(pad[1]))] = str(net[1]) if net else ""
    return out


def sch_pad_nets(sch_path=SCH, tag="sch"):
    """{(ref, pin): net} from the schematic's own netlist (kicad-cli), ground truth for connectivity."""
    net_file = scratch(tag + ".net")
    r = run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", net_file, sch_path])
    if not os.path.exists(net_file):
        raise RuntimeError("netlist export failed: " + r.stdout + r.stderr)
    out = {}
    for net in find_all(find(tree_of(net_file), "nets"), "net"):
        name = str(find(net, "name")[1]).lstrip("/")
        for node in find_all(net, "node"):
            out[(str(find(node, "ref")[1]), str(find(node, "pin")[1]))] = name
    return out


def is_nc(net):
    return (not net) or net.startswith("unconnected-")


_SYMBOL_PINS = {}


def symbol_pins(lib, name):
    """{pin number: pin name} for a symbol in one of KiCad's stock libraries (e.g. 'Transistor_FET')."""
    key = (lib, name)
    if key not in _SYMBOL_PINS:
        tree = tree_of(os.path.join(KICAD_SYMBOLS, lib + ".kicad_sym"))
        sym = next(s for s in find_all(tree, "symbol") if s[1] == name)
        while find(sym, "extends"):                # derived symbols carry no pins of their own
            base = str(find(sym, "extends")[1])
            sym = next(s for s in find_all(tree, "symbol") if s[1] == base)
        pins = {}

        def walk(node):
            for x in node:
                if isinstance(x, list) and x:
                    if x[0] == "pin":
                        pins[str(find(x, "number")[1])] = str(find(x, "name")[1])
                    else:
                        walk(x)
        walk(sym)
        _SYMBOL_PINS[key] = pins
    return _SYMBOL_PINS[key]


def esp32s3_symbol_pins():
    """{module pin number: pin name} from KiCad's own RF_Module:ESP32-S3-WROOM-1 symbol."""
    return symbol_pins("RF_Module", "ESP32-S3-WROOM-1")


# Pins KiCad's symbol names by function rather than IOnn (ESP32-S3 datasheet, table 2-1).
_ALT_GPIO = {"USB_D-": 19, "USB_D+": 20, "TXD0": 43, "RXD0": 44}


def gpio_of_pin(pin):
    """GPIO number for a module pin, or None for power/EN/etc."""
    name = esp32s3_symbol_pins()[str(pin)]
    if name in _ALT_GPIO:
        return _ALT_GPIO[name]
    return int(name[2:]) if name.startswith("IO") and name[2:].isdigit() else None


def pin_of_gpio(gpio):
    return next(p for p in esp32s3_symbol_pins() if gpio_of_pin(p) == gpio)


def board_facts():
    """Geometry of the routed board as a dict (see pcb_facts.py); cached until the board changes."""
    import hashlib
    import json
    out = scratch("facts-%s.json" % hashlib.md5(PCB.encode()).hexdigest()[:8])
    extractor = os.path.join(ROOT, "tests", "pcb_facts.py")
    if not os.path.exists(out) or os.path.getmtime(out) < max(os.path.getmtime(PCB), os.path.getmtime(extractor)):
        r = run([KICAD_PYTHON, extractor, PCB, out])
        if not os.path.exists(out):
            raise RuntimeError(r.stdout + r.stderr)
    with open(out) as f:
        return json.load(f)


def pane_of(fp, pad):
    """A paste-only pad (no copper) inside one of its part's copper pads is one pane of that pad's
    window-pane aperture, as KiCad's DFN footprints paste an exposed pad. Returns the copper pad, or None."""
    if pad["copper"]:
        return None
    x, y = pad["pos"]
    return next((p for p in fp["pads"] if p["copper"] and p["bbox"][0] <= x <= p["bbox"][2] and p["bbox"][1] <= y <= p["bbox"][3]), None)
