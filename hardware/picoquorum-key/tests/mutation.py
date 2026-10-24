"""Fault injection on a scratch copy of the board: the machinery behind test_mutation.py.

Each mutator takes the parsed .kicad_pcb tree (sexp lists) and edits it in place. The original
project is never touched; the copy lives under hardware/out/scratch/test/mut/.
"""
import json
import os
import shutil

import common
from sexp import dumps, find, find_all, parse, QStr  # noqa: F401  (via common's sys.path)

MUT_DIR = os.path.join(common.SCRATCH, "mut")
ORIGIN = (100.0, 60.0)      # board top-left on the sheet (Edge.Cuts bounding box)


def fresh_project(name):
    """Copy the project beside a symlink to hardware/lib so ${KIPRJMOD}/../lib resolves."""
    root = os.path.join(MUT_DIR, name)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    shutil.copytree(common.PRJ, os.path.join(root, "picoquorum-key"),
                    ignore=shutil.ignore_patterns("*-backups", "*.lck", "_autosave*"))
    os.symlink(os.path.join(common.ROOT, "hardware", "lib"), os.path.join(root, "lib"))
    return os.path.join(root, "picoquorum-key")


def drc(prj_dir, tag):
    """Run kicad-cli DRC with schematic parity; return (exit code, set of violation types, count)."""
    out = os.path.join(os.path.dirname(prj_dir), tag + "-drc.json")
    r = common.run(["kicad-cli", "pcb", "drc", "--severity-all", "--schematic-parity", "--all-track-errors", "--format", "json",
                    "--exit-code-violations", "-o", out, os.path.join(prj_dir, "picoquorum-key.kicad_pcb")])
    with open(out) as f:
        rep = json.load(f)
    items = rep.get("violations", []) + rep.get("unconnected_items", []) + rep.get("schematic_parity", [])
    types = {v["type"] for v in items}
    return r.returncode, types, len(items)


def load_pcb(prj_dir):
    return parse(open(os.path.join(prj_dir, "picoquorum-key.kicad_pcb")).read())


def save_pcb(prj_dir, tree):
    with open(os.path.join(prj_dir, "picoquorum-key.kicad_pcb"), "w") as f:
        f.write(dumps(tree) + "\n")


# --- helpers over the tree ------------------------------------------------------------------
def footprint(tree, ref):
    for fp in find_all(tree, "footprint"):
        if any(p[1] == "Reference" and p[2] == ref for p in find_all(fp, "property")):
            return fp
    raise KeyError(ref)


def net_items(tree, net, kinds=("segment", "via")):
    return [x for k in kinds for x in find_all(tree, k) if find(x, "net") and str(find(x, "net")[1]) == net]


def set_net(item, net):
    find(item, "net")[1] = QStr(net)


def pad(fp, number):
    return next(p for p in find_all(fp, "pad") if str(p[1]) == str(number))


# --- the mutators ---------------------------------------------------------------------------
def delete_net_copper(net):
    def mutate(tree):
        for item in net_items(tree, net):
            tree.remove(item)
    mutate.__doc__ = "delete every track and via on net %s" % net
    return mutate


def delete_one_via(net):
    def mutate(tree):
        tree.remove(net_items(tree, net, ("via",))[0])
    mutate.__doc__ = "delete one via on net %s" % net
    return mutate


def bridge_tracks(net_a, net_b):
    """Join two nets with a new track between a point on a net_a track and a net_b track (a short).

    Relabelling an existing track is not a fault: KiCad re-derives a track's net from the copper
    it touches when it loads the board, so only added geometry counts.
    """
    def mutate(tree):
        a = net_items(tree, net_a, ("segment",))
        b = net_items(tree, net_b, ("segment",))
        sa = next(s for s in a if _horizontal(s) and _layer(s) == "B.Cu")
        sb = next(s for s in b if _horizontal(s) and _layer(s) == "B.Cu")
        x = (float(find(sa, "start")[1]) + float(find(sa, "end")[1])) / 2
        ya, yb = find(sa, "start")[2], find(sb, "start")[2]
        tree.insert(len(tree) - 1, parse(
            '(segment (start %s %s) (end %s %s) (width 0.3) (layer "B.Cu") (net "%s") '
            '(uuid "00000000-0000-4000-8000-000000000001"))' % (x, ya, x, yb, net_a)))
    mutate.__doc__ = "lay a B.Cu track between a %s and a %s track (a short)" % (net_a, net_b)
    return mutate


def _horizontal(seg):
    return find(seg, "start")[2] == find(seg, "end")[2]


def _layer(item):
    return str(find(item, "layer")[1])


def swap_pad_nets(ref, a, b):
    def mutate(tree):
        fp = footprint(tree, ref)
        pa, pb = find(pad(fp, a), "net"), find(pad(fp, b), "net")
        pa[1], pb[1] = pb[1], pa[1]
    mutate.__doc__ = "swap the nets on %s pads %s and %s" % (ref, a, b)
    return mutate


def remove_footprint(ref):
    def mutate(tree):
        tree.remove(footprint(tree, ref))
    mutate.__doc__ = "remove footprint %s" % ref
    return mutate


def thin_segment(net, width):
    def mutate(tree):
        find(net_items(tree, net, ("segment",))[0], "width")[1] = str(width)
    mutate.__doc__ = "thin one %s track to %s mm" % (net, width)
    return mutate


def move_footprint_onto(ref, other):
    def mutate(tree):
        find(footprint(tree, ref), "at")[1:3] = find(footprint(tree, other), "at")[1:3]
    mutate.__doc__ = "stack %s on top of %s" % (ref, other)
    return mutate


def track_into_antenna_band(net):
    def mutate(tree):
        seg = net_items(tree, net, ("segment",))[0]
        for end in ("start", "end"):
            find(seg, end)[2] = str(ORIGIN[1] + 3.5)   # 3.5 mm below the top edge: inside the antenna band
        find(seg, "layer")[1] = QStr("F.Cu")
    mutate.__doc__ = "route a %s track through the antenna band" % net
    return mutate


def via_into_antenna_band(net):
    def mutate(tree):
        find(net_items(tree, net, ("via",))[0], "at")[2] = str(ORIGIN[1] + 3.5)
    mutate.__doc__ = "put a %s via in the antenna band" % net
    return mutate


def move_hole_to_edge(ref):
    def mutate(tree):
        find(footprint(tree, ref), "at")[1:3] = [str(ORIGIN[0] + 0.4), str(ORIGIN[1] + 29)]
    mutate.__doc__ = "push mounting hole %s onto the board edge" % ref
    return mutate


def move_silk_text_onto_pad(text, ref, number):
    def mutate(tree):
        fp = footprint(tree, ref)
        fx, fy = (float(v) for v in find(fp, "at")[1:3])         # these switches are unrotated
        px, py = (float(v) for v in find(pad(fp, number), "at")[1:3])
        label = next(t for t in find_all(tree, "gr_text") if t[1] == text)
        find(label, "at")[1:3] = [str(fx + px), str(fy + py)]
    mutate.__doc__ = "drag the %r silk label onto %s pad %s" % (text, ref, number)
    return mutate
