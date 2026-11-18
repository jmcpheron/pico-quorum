# The cases' letters

The typeface the case scripts cut text with: the name on a face and a back, `picoquorum.app`.
[`consoles/shell.py`](../consoles/shell.py) reads these two files (`FONTS`, `font`) and stops if one
is missing or OpenCASCADE can't read it. It never asks the machine for a font. Before, it did, and the
same script cut the name 36 mm wide on one machine and 34.8 mm on another.

| file | what | sha256 |
|---|---|---|
| `AtkinsonHyperlegibleNext-Bold.ttf` | Atkinson Hyperlegible Next Bold, version 2.001, Latin | `79b587c44485f8d8e684597df483b917a9c092fda18b49c063ae1c7867439d4b` |
| `AtkinsonHyperlegibleNext-Regular.ttf` | the same, Regular | `b92a152f46a522143b40c07406a4c2251baad035e04daa28eb085ab4ceba5f87` |
| `OFL.txt` | their licence, the SIL Open Font License 1.1 | |

It is the brand's typeface for words ([BRAND.md](../../docs/BRAND.md#type)), and these are the site's
own two files, unpacked: `docs/app/fonts/next-700.woff2` and `next-400.woff2`, which
[`web/build.mjs`](../../web/build.mjs) copies from `@fontsource/atkinson-hyperlegible-next` 5.3.0.
OpenCASCADE reads TTF, not WOFF2, so each was opened and saved as TTF with fontTools 4.68.0, nothing
else changed. `OFL.txt` is the copy that package ships. Doing it twice gave the same file.

```sh
uv run --no-project --python 3.11 --with fonttools==4.68.0 --with brotli==1.2.1 python -c '
import sys; from fontTools.ttLib import TTFont
f = TTFont(sys.argv[1], recalcTimestamp=False); f.flavor = None; f.save(sys.argv[2], reorderTables=True)
' docs/app/fonts/next-700.woff2 cad/fonts/AtkinsonHyperlegibleNext-Bold.ttf
```

The files hold 247 glyphs, the Latin subset: enough for English words. A change of file changes every
case's letters: rebuild them all (`tools/case build mono mono-industrial rp stick badge`).

Not covered: [`key/tray.py`](../key/tray.py) and the archived builds' cases still take the machine's
font for their few labels.
