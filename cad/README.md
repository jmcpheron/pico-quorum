# cad

The printed parts, each drawn by a CadQuery script. `tools/case list` shows every design, what it
runs and what it writes; `tools/case build <name>` rebuilds one.

| folder | what | build |
|---|---|---|
| **[consoles/](consoles/README.md)** | **Mono's case** ([`mono.py`](consoles/mono.py)) **its industrial variant** ([`mono_ind.py`](consoles/mono_ind.py)) and **the monolith**, for two colours ([`mono_lith.py`](consoles/mono_lith.py)); console-rp's case, the slate; and the two early prototypes' cases, the stick and the badge. One script, `shell.py`, makes them all | `tools/case build mono-industrial` (or `mono`, `mono-monolith`, `rp`, `stick`, `badge`) |
| [mono/](mono/README.md) | Mono's board as a print, to hold: not a case | `uv run … python cad/mono/board.py` |
| [key/](key/README.md) | a snap-lid case for the ATECC608 breakout | `tools/case build key-tray` |
| [fonts/](fonts/README.md) | the typeface the console cases' letters are cut from: Atkinson Hyperlegible Next, two TTF files | |

The cases for the archived builds (the prism, the handheld, the Feather pigtail's tray) are with
their builds, in [`hardware/archive/builds/`](../hardware/archive/README.md#builds).

Nothing here is checked by CI. A case is up to date when `tools/case check <name>` lists nothing.
