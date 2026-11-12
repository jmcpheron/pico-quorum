#!/usr/bin/env python3
"""Placeholder: list the C-numbers in docs/BOM.md with their JLCPCB and LCSC URLs for a manual
stock/tier check. JLCPCB's part pages are JavaScript-rendered and refuse plain fetches, so this
prints links rather than scraping."""
import re, sys, pathlib
bom = pathlib.Path(__file__).resolve().parents[1] / "docs" / "BOM.md"
seen = []
for c in re.findall(r"\bC\d{3,9}\b", bom.read_text()):
    if c not in seen:
        seen.append(c)
for c in seen:
    print(f"{c:12} https://jlcpcb.com/partdetail/{c}   https://www.lcsc.com/product-detail/{c}.html")
print(f"{len(seen)} parts", file=sys.stderr)
