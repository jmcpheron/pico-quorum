# cad

The printed parts, each drawn by a CadQuery script. `tools/case list` shows every design, what it
runs and what it writes; `tools/case build <name>` rebuilds one.

| folder | what | build |
|---|---|---|
| **[consoles/](consoles/README.md)** | **Mono's case** ([`mono.py`](consoles/mono.py)) and **its industrial variant** ([`mono_ind.py`](consoles/mono_ind.py)); console-rp's case, the slate, and its industrial variant ([`rp_ind.py`](consoles/rp_ind.py)); and the two early prototypes' cases, the stick and the badge. One script, `shell.py`, makes them all | `tools/case build mono-industrial` (or `mono`, `rp`, `rp-industrial`, `stick`, `badge`) |
| [mono/](mono/README.md) | Mono's board as a print, to hold: not a case | `uv run … python cad/mono/board.py` |
| [key/](key/README.md) | a snap-lid case for the ATECC608 breakout | `tools/case build key-tray` |

The cases for the archived builds (the prism, the handheld, the Feather pigtail's tray) are with
their builds, in [`hardware/archive/builds/`](../hardware/archive/README.md#builds).

Nothing here is checked by CI. A case is up to date when `tools/case check <name>` lists nothing.
