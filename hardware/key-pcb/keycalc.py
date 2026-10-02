# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib>=3.8", "numpy>=1.26"]
# ///
"""The numbers behind the key PCB, worked out on the command line. A companion to LEARN.md.

    tools/keypcb calc insert                  which finger touches when, as the key goes in
    tools/keypcb calc rise [--pullup 4.7k,10k] [--extra 20p]
                                              I2C rise time from the pull-up and the bus capacitance
    tools/keypcb calc power [--drive 12]      key VCC from a GPIO: how far it sags while the chip signs
    tools/keypcb calc spice rise|backpower    the same in ngspice, plotted to hardware/key-pcb/out/

Every datasheet number lives in DATA below, with where it came from. An estimate, not a
datasheet value, is marked "est". The finger geometry is imported from gen.py, so this file
can't disagree with the board.
"""
import argparse, math, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
import gen  # noqa: E402  (only its constants: gen.py touches pcbnew and kicad-cli inside main() alone)


# (value, where it came from). Looked up 2026-10-02 in the PDFs themselves:
#   ATECC  Microchip ATECC608C summary datasheet DS40002513B
#   ST     USBLC6-2 datasheet, Doc ID 11265 rev 5 (2011): check it against ST's current revision
#   RP     RP2350 datasheet, release 8, section 14.9.4, table 1683 (IOVDD = 3.3 V)
#   I2C    NXP UM10204 rev 7.0 (the I2C-bus specification)
# "est" marks an estimate, not a datasheet value; change it when you measure something better.
DATA = {
    "vdd": (3.3, "console 3V3 and switched key VCC"),
    # the chip
    "atecc_vcc_min": (2.0, "ATECC table 3-5, p.13"),
    "atecc_i_sleep": (150e-9, "ATECC table 3-5: ISLEEP max, VCC <= 3.6 V, <= 55 °C"),
    "atecc_i_idle": (3e-3, "ATECC table 3-5: ICC max, awake, waiting for I/O"),
    "atecc_i_active": (14e-3, "ATECC table 3-5: ICC max during ECC, clock divider 0x0"),
    "atecc_tr": (300e-9, "ATECC table 3-4: input rise time max, at any clock"),
    "atecc_t_sign": (120e-3, "est: the wait firmware/atecc.py allows for a Sign; the real figure is in the NDA datasheet"),
    "atecc_cin": (10e-12, "est: not in the datasheet; I2C's 10 pF per-pin max (UM10204 table 10)"),
    # the ESD array
    "usblc6_cio": (3.5e-12, "ST table 2: Ci/o-GND max, VR = 1.65 V"),
    "usblc6_diode": ((2.5e-9, 1.75), "est: a generic small-signal diode, VF ~0.69 V at 10 mA (ST's max is 1.1 V)"),
    # the Pico
    "rp2350_cin": (10e-12, "est: not in the datasheet; I2C's 10 pF per-pin max (UM10204 table 10)"),
    "rp2350_voh_drop": (0.68, "RP table 1683: VOH >= 2.62 V at the drive setting's own current"),
    "rp2350_pulldown": (113e3, "RP table 1683: RPD max, the weakest pull-down"),
    # wiring (estimates)
    "wire_c": (10e-12, "est: ~10 cm of jumper wire at ~1 pF/cm"),
    "socket_c": (2e-12, "est: one card-edge socket contact"),
    "trace_c": (1.5e-12, "est: ~15 mm of 0.2 mm trace over ground on 1.6 mm FR-4"),
    # the I2C spec
    "i2c_vol": (0.4, "I2C table 10: VOL max at 3 mA"),
    "i2c_iol": (3e-3, "I2C table 10: IOL, Standard and Fast mode"),
    "i2c_tr_100k": (1000e-9, "I2C table 11: tr max, Standard mode"),
    "i2c_tr_400k": (300e-9, "I2C table 11: tr max, Fast mode"),
}


def si(s):
    """'4.7k' -> 4700.0, '100n' -> 1e-07, '3p3' -> 3.3e-12, '12m' -> 0.012."""
    mult = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6}
    s = s.strip().rstrip("FfHzΩRrAaVv")
    for k, m in mult.items():
        if k in s:
            a, _, b = s.partition(k)
            if "." in a or not b:          # 2.2k, 100n
                return float(a) * m
            return float(f"{a or 0}.{b}") * m   # 4k7, 3p3
    return float(s)


def eng(x, unit=""):
    """1.2e-7 -> '120 n' style, for tables."""
    if x == 0:
        return f"0 {unit}".strip()
    for k, m in (("M", 1e6), ("k", 1e3), ("", 1), ("m", 1e-3), ("µ", 1e-6), ("n", 1e-9), ("p", 1e-12)):
        if abs(x) >= m * 0.9995:
            v = x / m
            return f"{v:.3g} {k}{unit}".strip()
    return f"{x:.3g} {unit}".strip()


# =================================================================================================
# insert: the mating sequence
# =================================================================================================
# Picture the socket's contact as a point that slides along the finger side of the board as the
# key goes in. Call p how far that point is from the board's leading edge. p grows from 0 (the
# edge just reaches the contact) to gen.CONTACT_DEPTH (fully seated). A finger connects once p
# passes its start, and stays connected until p passes FINGER_END, which it never does.

def cmd_insert(a):
    seated = a.contact if a.contact is not None else gen.CONTACT_DEPTH
    rows = sorted(gen.FINGERS, key=lambda f: gen.FINGER_START[f[3]])
    print(f"Contact point when seated: {seated:.2f} mm from the leading edge"
          f"{'  (EDAC drawing)' if a.contact is None else '  (your --contact)'}\n")
    print(f"{'finger':>6}  {'signal':<7} {'starts at':>9}  {'connects at':>11}  {'wipe when seated':>16}")
    for n, sig, net, cls, gpio in rows:
        start = gen.FINGER_START[cls]
        ok = start <= seated
        conn = f"{start:.2f} mm" if ok else "never"
        wipe = f"{seated - start:.2f} mm" if ok else "-"
        print(f"{n:>6}  {sig:<7} {start:>7.2f} mm  {conn:>11}  {wipe:>16}")
    det = gen.FINGER_START["short"]
    print()
    if seated < det:
        print(f"DETECT never touches: the console never sees the key, so it never powers it. The key is"
              f" inert, not damaged. Move the short finger's start below {seated:.2f} mm to fix it.")
    else:
        print(f"Order going in:  GND at {gen.FINGER_START['long']} mm, then SDA/SCL/VCC/ID/RST at "
              f"{gen.FINGER_START['mid']} mm, then DETECT at {det} mm.")
        print(f"Going out it reverses: DETECT lets go first, with {gen.FINGER_START['short'] - gen.FINGER_START['mid']:.2f}"
              f" mm of travel before the signals let go, and the console cuts VCC (GP6) the moment DETECT goes high.")
        print(f"After DETECT touches there are {seated - det:.2f} mm still to go: that's the margin for a key that"
              f" isn't pushed all the way.")
    if a.plot:
        _plot_insert(seated)


def _plot_insert(seated):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = sorted(gen.FINGERS, key=lambda f: -gen.FINGER_START[f[3]])
    fig, ax = plt.subplots(figsize=(8, 3.2))
    for i, (n, sig, net, cls, gpio) in enumerate(rows):
        s = gen.FINGER_START[cls]
        ax.barh(i, max(0, seated - s), left=s, height=0.55, color={"long": "#2a9d8f", "mid": "#8ab17d", "short": "#e76f51"}[cls])
        ax.text(-0.1, i, f"{n} {sig}", ha="right", va="center", fontsize=9)
    ax.axvline(seated, color="k", ls="--", lw=1)
    ax.text(seated, len(rows) - 0.3, " fully seated", fontsize=8, va="bottom")
    ax.set_yticks([]); ax.set_xlim(0, seated + 0.6)
    ax.set_xlabel("how far the contact has slid onto the board (mm from the leading edge)")
    ax.set_title("When each finger is touching, as the key goes in")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    path = _out("insert.png")
    fig.savefig(path, dpi=150)
    print(f"\nplot: {path}")


def _out(name):
    os.makedirs(OUT, exist_ok=True)
    return os.path.join(OUT, name)


# =================================================================================================
# rise: the I2C rise time
# =================================================================================================
# I2C lines are open-drain: a chip can only pull a line low. When it lets go, the pull-up resistor
# charges the line's capacitance back up to VCC. That's an RC curve, so the time from 30 % to 70 %
# of VCC (the I2C spec's definition of rise time) is R*C*ln(0.7/0.3) = 0.8473*R*C. Every pin,
# trace, wire and ESD diode on the line adds capacitance, so the budget below adds them up.

def bus_items(extra):
    items = [
        ("Pico GP4/GP5 pin", DATA["rp2350_cin"]),
        ("wires, socket to Pico", DATA["wire_c"]),
        ("card-edge socket contact", DATA["socket_c"]),
        ("key trace, finger to chip", DATA["trace_c"]),
        ("USBLC6 I/O line (ESD)", DATA["usblc6_cio"]),
        ("ATECC608C pin", DATA["atecc_cin"]),
    ]
    if extra:
        items.append(("--extra", (extra, "your number")))
    return items


def cmd_rise(a):
    items = bus_items(si(a.extra))
    c = sum(v for _, (v, _) in items)
    print("Capacitance on SDA (SCL is the same):\n")
    for name, (v, src) in items:
        print(f"  {name:<28} {eng(v, 'F'):>9}   {src}")
    print(f"  {'total':<28} {eng(c, 'F'):>9}\n")

    vdd = DATA["vdd"][0]
    vol, iol = DATA["i2c_vol"][0], DATA["i2c_iol"][0]
    rmin = (vdd - vol) / iol
    limits = [("I2C 100 kHz", "i2c_tr_100k"), ("ATECC608C", "atecc_tr"), ("I2C 400 kHz", "i2c_tr_400k")]
    print(f"Smallest pull-up allowed: (VCC - VOL) / IOL = ({vdd} - {vol}) / {eng(iol, 'A')} = {eng(rmin, 'Ω')}")
    for name, key in limits:
        tr = DATA[key][0]
        print(f"Largest pull-up for {name + ':':<13} tr_max / (0.8473 * C) = {eng(tr, 's'):>7} / (0.8473 * {eng(c, 'F')})"
              f" = {eng(tr / (0.8473 * c), 'Ω'):>7}   ({DATA[key][1]})")
    print()
    head = "  ".join(f"{name + ' ' + eng(DATA[key][0], 's'):>22}" for name, key in limits)
    print(f"{'pull-up':>10}  {'rise time':>10}  {head}")
    for r in [si(x) for x in a.pullup.split(",")]:
        t = 0.8473 * r * c
        cells = []
        for _, key in limits:
            tr = DATA[key][0]
            cell = "too strong" if r < rmin else ("ok" if t <= tr else "TOO SLOW") + f" ({t / tr:.0%})"
            cells.append(f"{cell:>22}")
        print(f"{eng(r, 'Ω'):>10}  {eng(t, 's'):>10}  " + "  ".join(cells))
    print("\n(%) is the rise time as a share of each limit. The ATECC608 runs at 100 kHz, but the chip's own"
          " table asks for a 300 ns rise at any clock. A Trust M key runs at 400 kHz (firmware/trustm.py).")


# =================================================================================================
# power: key VCC straight from a GPIO
# =================================================================================================
# Build 1 powers the key from GP6. A GPIO is not a power supply: its output transistor has some
# resistance, so the more current the chip draws, the further VCC sags below 3.3 V. The RP2350
# datasheet promises VOH (the output-high voltage) only down to a stated current for each drive
# setting. Treating the pin as a resistor, R_out = (IOVDD - VOH_min) / I_rated, gives a worst-case
# estimate.

def cmd_power(a):
    vdd = DATA["vdd"][0]
    voh_drop = DATA["rp2350_voh_drop"][0]
    vmin = DATA["atecc_vcc_min"][0]
    loads = [("sleep", DATA["atecc_i_sleep"]), ("awake", DATA["atecc_i_idle"]),
             ("signing (ECC)", DATA["atecc_i_active"])]
    drives = [int(d) for d in a.drive.split(",")]
    print(f"Pin model: VOH stays above IOVDD - {voh_drop} V at the drive setting's rated current"
          f"  ({DATA['rp2350_voh_drop'][1]})")
    print(f"ATECC608C needs VCC >= {vmin} V  ({DATA['atecc_vcc_min'][1]})\n")
    print(f"{'drive':>6}  {'R_out':>7}  " + "  ".join(f"{n + ' ' + eng(i, 'A'):>22}" for n, (i, _) in loads))
    for d in drives:
        rout = voh_drop / (d * 1e-3)
        cells = []
        for _, (i, _) in loads:
            v = vdd - i * rout
            flag = "" if v >= vmin else " LOW"
            over = " >rated" if i > d * 1e-3 else ""
            cells.append((f"{v:.2f} V" if v > 0 else "~0 V") + f"{flag}{over}".rjust(0))
            cells[-1] = cells[-1].rjust(22)
        print(f"{d:>4}mA  {eng(rout, 'Ω'):>7}  " + "  ".join(cells))
    print("\n'>rated' means the chip draws more than the drive setting is specified for, so the number is a"
          " straight-line guess past the datasheet. bench1.py uses Pin.DRIVE_3, the 12 mA setting.")

    c1 = si(a.cap)
    i = DATA["atecc_i_active"][0]
    print(f"\nWhat C1 ({eng(c1, 'F')}) does: it can hold up a {eng(i, 'A')} draw for only"
          f" C*dV/I = {eng(c1 * 0.3 / i, 's')} per 0.3 V of sag.")
    print("That covers the chip's nanosecond current spikes, which is its job. An ECC signature takes"
          f" tens of milliseconds (the driver allows {DATA['atecc_t_sign'][0] * 1e3:.0f} ms), so during"
          " signing the sag is set by the source, not the cap.")
    print(f"Charging C1 at power-on takes about C*V/I = {eng(c1 * vdd / (drives[-1] * 1e-3), 's')} at the"
          f" {drives[-1]} mA setting, well inside the 5 ms the console waits after switching VCC on.")


# =================================================================================================
# spice: the same circuits in ngspice
# =================================================================================================

def _ngspice(netlist, name):
    if not shutil.which("ngspice"):
        sys.exit("ngspice not found: brew install ngspice")
    path = _out(name + ".cir")
    with open(path, "w") as f:
        f.write(netlist)
    r = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True, cwd=OUT)
    if r.returncode:
        sys.exit(f"ngspice failed:\n{r.stdout}{r.stderr}")
    return r.stdout


def _wrdata(path):
    """ngspice's wrdata: pairs of columns (x, y) per vector."""
    import numpy as np
    d = np.loadtxt(path)
    return d[:, 0], d[:, 1::2]


def cmd_spice_rise(a):
    import numpy as np
    vdd = DATA["vdd"][0]
    c = sum(v for _, (v, _) in bus_items(si(a.extra)))
    rs = [si(x) for x in a.pullup.split(",")]
    lines = [f"* I2C rise: a pull-up charges the bus after the chip lets go at t=1us. C = {eng(c, 'F')}",
             f"V1 vdd 0 {vdd}",
             "Vctl ctl 0 PWL(0 1 1u 1 1.001u 0)",
             ".model sw SW(Ron=10 Roff=1G Vt=0.5 Vh=0.1)"]
    for k, r in enumerate(rs):
        lines += [f"Rp{k} vdd bus{k} {r}", f"Cb{k} bus{k} 0 {c}", f"S{k} bus{k} 0 ctl 0 sw"]
    stop = max(3e-6 + 4 * r * c for r in rs)
    vecs = " ".join(f"v(bus{k})" for k in range(len(rs)))
    lines += [".control", f"tran {stop / 2000} {stop}", f"wrdata rise.dat {vecs}", ".endc", ".end"]
    _ngspice("\n".join(lines) + "\n", "rise")
    t, v = _wrdata(os.path.join(OUT, "rise.dat"))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4))
    print(f"ngspice, C = {eng(c, 'F')}:")
    for k, r in enumerate(rs):
        y = v[:, k]
        t30 = t[np.argmax(y >= 0.3 * vdd)]
        t70 = t[np.argmax(y >= 0.7 * vdd)]
        tr = t70 - t30
        print(f"  {eng(r, 'Ω'):>7}: rise time {eng(tr, 's'):>8}   (formula {eng(0.8473 * r * c, 's')})")
        ax.plot((t - 1e-6) * 1e9, y, label=f"{eng(r, 'Ω')}: tr = {eng(tr, 's')}")
    for label, key in (("I2C 100 kHz limit", "i2c_tr_100k"), ("ATECC608C and I2C 400 kHz limit", "i2c_tr_400k")):
        ax.axvline(DATA[key][0] * 1e9, color="grey", ls=":", lw=1)
        ax.text(DATA[key][0] * 1e9, 0.15, f" {label}", fontsize=8, color="grey", rotation=90)
    for frac in (0.3, 0.7):
        ax.axhline(frac * vdd, color="grey", lw=0.6)
    ax.set_xlim(-100, (stop - 1e-6) * 1e9); ax.set_ylim(0, vdd * 1.05)
    ax.set_xlabel("ns after the chip lets go of SDA"); ax.set_ylabel("SDA (V)")
    ax.set_title("I2C rise time: pull-up resistor charging the bus capacitance")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    path = _out("rise.png")
    fig.savefig(path, dpi=150)
    print(f"plot: {path}\nnetlist: {_out('rise.cir')}")


def cmd_spice_backpower(a):
    """Pull-ups wired to the always-on 3V3 instead of switched key VCC, with the key unpowered."""
    vdd = DATA["vdd"][0]
    vmin = DATA["atecc_vcc_min"][0]
    r_pd = DATA["rp2350_pulldown"][0]
    rp = si(a.pullup)
    is_, n = DATA["usblc6_diode"][0]
    # How much an unpowered chip draws from its VCC pin isn't in any datasheet, and it changes the
    # answer a lot, so the run sweeps it: from the awake current down to the full-range sleep max.
    loads = [("as if awake, 3 mA", vdd / DATA["atecc_i_idle"][0]),
             ("100 µA (est)", vdd / 100e-6),
             ("as if asleep, 2 µA", vdd / 2e-6)]
    body = [f"* Back-power: SDA and SCL pulled up to 3V3 while key VCC (GP6) is off.",
            "* Each line leaks into VCC through the USBLC6's upper steering diode.",
            f"V3v3 v3 0 {vdd}",
            f".model desd D(Is={is_} N={n})"]
    for k, (_, rl) in enumerate(loads):
        body += [f"RpSDA{k} v3 sda{k} {rp}", f"RpSCL{k} v3 scl{k} {rp}",
                 f"DSDA{k} sda{k} vcc{k} desd", f"DSCL{k} scl{k} vcc{k} desd",
                 f"C1_{k} vcc{k} 0 100n IC=0", f"Rchip{k} vcc{k} 0 {rl}",
                 f"* GP6 an input with its pull-down, as after reset", f"Rgp6_{k} vcc{k} 0 {r_pd}"]
    vecs = " ".join(f"v(vcc{k}) v(sda{k})" for k in range(len(loads)))
    body += [".control", "op", "print " + vecs, "tran 5u 5m uic", f"wrdata backpower.dat {vecs}", ".endc", ".end"]
    out = _ngspice("\n".join(body) + "\n", "backpower")
    vals = dict(re_find(out))
    print(f"Pull-ups of {eng(rp, 'Ω')} to 3V3, key VCC switched off (GP6 an input with its pull-down).")
    print(f"Current leaks from SDA and SCL through the ESD array's diodes into key VCC:\n")
    print(f"  {'chip draws':<20} {'key VCC':>8} {'SDA':>8}")
    for k, (name, _) in enumerate(loads):
        v = vals[f"v(vcc{k})"]
        state = ("running from its I/O pins" if v >= vmin else
                 "brown-out zone: may wake half-working" if v >= 0.7 else "low, mostly harmless")
        print(f"  {name:<20} {v:>6.2f} V {vals[f'v(sda{k})']:>6.2f} V   {state}")
    print(f"\nThe chip needs {vmin} V to run. The lighter its load, the closer VCC creeps to 3V3 minus a diode drop,")
    print("and SDA can't reach a clean high either. With the pull-ups on switched VCC (BUILD1's rule) there is")
    print("no source at all, so VCC stays at 0 V. The diode model is a generic estimate; the shape holds, the exact volts don't.")

    t, v = _wrdata(os.path.join(OUT, "backpower.dat"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 3.8))
    for k, (name, _) in enumerate(loads):
        ax.plot(t * 1e3, v[:, 2 * k], label=f"key VCC, chip {name}")
    ax.axhline(vmin, color="grey", ls=":", lw=1)
    ax.text(0.05, vmin, "ATECC608C VCC min", va="bottom", fontsize=8, color="grey")
    ax.set_xlabel("ms after the key goes in"); ax.set_ylabel("key VCC (V), should be 0"); ax.set_ylim(0, vdd * 1.05)
    ax.set_title(f"Back-power: {eng(rp, 'Ω')} pull-ups on 3V3 feed an unpowered key through its ESD diodes")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    path = _out("backpower.png")
    fig.savefig(path, dpi=150)
    print(f"plot: {path}\nnetlist: {_out('backpower.cir')}")


def re_find(out):
    import re
    for m in re.finditer(r"^\s*(v\(\w+\)|i\(\w+\))\s*=\s*([-+0-9.eE]+)", out, re.M):
        yield m.group(1), float(m.group(2))


# =================================================================================================

def main():
    p = argparse.ArgumentParser(prog="tools/keypcb calc", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("insert", help="which finger touches when, as the key goes in")
    s.add_argument("--contact", type=float, help="where the socket's contact lands on a seated board, mm from the edge")
    s.add_argument("--plot", action="store_true", help=f"also draw it to {os.path.relpath(OUT)}/insert.png")
    s.set_defaults(fn=cmd_insert)
    s = sub.add_parser("rise", help="I2C rise time from the pull-up and the bus capacitance")
    s.add_argument("--pullup", default="2.2k,4.7k,10k,50k", help="comma-separated, e.g. 4.7k,10k (50k is the Pico's internal pull-up)")
    s.add_argument("--extra", default="0", help="capacitance to add, e.g. 20p for a longer cable")
    s.set_defaults(fn=cmd_rise)
    s = sub.add_parser("power", help="key VCC from a GPIO: the sag while the chip signs")
    s.add_argument("--drive", default="2,4,8,12", help="RP2350 drive settings in mA")
    s.add_argument("--cap", default="100n", help="the key's decoupling cap, C1")
    s.set_defaults(fn=cmd_power)
    s = sub.add_parser("spice", help="ngspice runs, plotted to out/")
    ss = s.add_subparsers(dest="what", required=True)
    t = ss.add_parser("rise", help="the rise-time edge for several pull-ups")
    t.add_argument("--pullup", default="4.7k,10k")
    t.add_argument("--extra", default="0")
    t.set_defaults(fn=cmd_spice_rise)
    t = ss.add_parser("backpower", help="pull-ups on 3V3 feeding an unpowered key through its ESD diodes")
    t.add_argument("--pullup", default="10k")
    t.set_defaults(fn=cmd_spice_backpower)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
