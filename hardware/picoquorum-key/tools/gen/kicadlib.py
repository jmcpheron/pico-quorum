"""Load symbols from KiCad's bundled libraries, flattening `extends`."""
import copy
import os
from sexp import parse, QStr, find, find_all

KICAD_SYMBOLS = os.environ.get(
    "KICAD_SYMBOL_DIR", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")

_cache = {}


def _lib(lib):
    if lib not in _cache:
        path = os.path.join(KICAD_SYMBOLS, lib + ".kicad_sym")
        tree = parse(open(path).read())
        _cache[lib] = {s[1]: s for s in find_all(tree, "symbol")}
    return _cache[lib]


def load_symbol(lib_id):
    """Return a flattened symbol s-expr named 'Lib:Name', ready for lib_symbols."""
    lib, name = lib_id.split(":", 1)
    syms = _lib(lib)
    sym = copy.deepcopy(syms[name])
    ext = find(sym, "extends")
    if ext:
        parent = load_symbol(lib + ":" + ext[1])
        pname = parent[1].split(":", 1)[1]
        # parent's attributes and units, child's properties overriding the parent's by name
        child_props = {str(x[1]): x for x in find_all(sym, "property")}
        props = []
        for x in find_all(parent, "property"):
            props.append(child_props.pop(str(x[1]), x))
        props += list(child_props.values())
        head = [x for x in parent[2:] if isinstance(x, list) and x[0] not in ("property", "symbol", "embedded_fonts")]
        units = []
        for u in find_all(parent, "symbol"):
            u = copy.deepcopy(u)
            u[1] = QStr(u[1].replace(pname, name, 1))
            units.append(u)
        tail = find_all(parent, "embedded_fonts")
        sym = ["symbol", QStr(name)] + head + props + units + tail
    sym[1] = QStr(lib_id)
    return sym


def pins(sym):
    """[(number, name, type, x, y, angle)] across all units, in library coordinates."""
    out = []
    for u in find_all(sym, "symbol"):
        for p in find_all(u, "pin"):
            at = find(p, "at")
            out.append((str(find(p, "number")[1]), str(find(p, "name")[1]), p[1],
                        float(at[1]), float(at[2]), int(float(at[3]))))
    return out
