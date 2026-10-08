#!/usr/bin/env python3
"""Check the native M1 carrier and export local quote files. No ordering or network calls."""
from pathlib import Path
import csv
import hashlib
import re
import subprocess
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
SCH = HERE / 'm1.kicad_sch'
PCB = HERE / 'm1.kicad_pcb'
OUT = HERE / 'fab'
REVIEW = HERE / 'review'
OUT.mkdir(exist_ok=True)
REVIEW.mkdir(exist_ok=True)
def run(*args):
    result = subprocess.run(['kicad-cli', *map(str, args)], capture_output=True, text=True, check=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    return result

run('sch', 'erc', '--severity-all', '-o', OUT / 'erc.rpt', SCH)
erc = (OUT / 'erc.rpt').read_text()
if not re.search(r'ERC messages: 0\s+Errors 0\s+Warnings 0', erc):
    raise SystemExit('ERC findings: fabrication export stopped.')
run('pcb', 'drc', '--schematic-parity', '--severity-all', '-o', OUT / 'drc.rpt', PCB)
drc = (OUT / 'drc.rpt').read_text()
counts = re.findall(r'Found (\d+) (?:DRC violations|unconnected pads|Footprint errors)', drc)
if len(counts) != 3 or any(int(n) for n in counts):
    raise SystemExit('PCB, connectivity or parity findings: fabrication export stopped.')

def archive(path, files):
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    layers = 'F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'
    run('pcb', 'export', 'gerbers', '--layers', layers, '--subtract-soldermask',
        '--use-drill-file-origin', '-o', str(tmp) + '/', PCB)
    run('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th',
        '--drill-origin', 'plot', '-o', str(tmp) + '/', PCB)
    gerber_ext = {'.gtl', '.gbl', '.gtp', '.gbp', '.gto', '.gbo', '.gts', '.gbs', '.gm1'}
    gerbers = [(p.name, p.read_bytes()) for p in tmp.iterdir() if p.suffix in gerber_ext | {'.drl'}]
    if {p.suffix for p in tmp.iterdir() if p.suffix in gerber_ext} != gerber_ext:
        raise SystemExit('Unexpected Gerber layer count.')
    if {p.name for p in tmp.glob('*.drl')} != {'m1-PTH.drl', 'm1-NPTH.drl'}:
        raise SystemExit('Expected separate plated and non-plated drill files.')
    archive(OUT / 'm1-gerbers.zip', gerbers)

run('sch', 'export', 'bom', '--fields', 'Reference,Value,Footprint,MPN,QUANTITY',
    '--labels', 'Designator,Value,Footprint,MPN,Quantity', '--group-by', 'Value,Footprint,MPN',
    '--ref-range-delimiter', '', '--exclude-dnp', '-o', OUT / 'bom.csv', SCH)
with (OUT / 'bom.csv').open() as f:
    bom = list(csv.DictReader(f))
refs = {ref for row in bom for ref in row['Designator'].split(',')}
if len(refs) != 30 or any(not row['MPN'] for row in bom):
    raise SystemExit('Expected 30 fitted components, each with an MPN.')
run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both',
    '--exclude-dnp', '--use-drill-file-origin', '-o', OUT / 'cpl.csv', PCB)
with (OUT / 'cpl.csv').open() as f:
    cpl = list(csv.DictReader(f))
if {row['Ref'] for row in cpl} != refs:
    raise SystemExit('BOM and placement reference sets differ.')
if any(row['Side'] != 'top' for row in cpl):
    raise SystemExit('Expected single-side assembly.')
run('sch', 'export', 'pdf', '-o', OUT / 'schematic.pdf', SCH)
run('sch', 'export', 'svg', '-o', str(REVIEW) + '/', SCH)
run('pcb', 'export', 'svg', '--layers', 'F.Cu,F.Fab,F.SilkS,Edge.Cuts,Dwgs.User',
    '--page-size-mode', '2', '--mode-single', '-o', REVIEW / 'placement.svg', PCB)
run('pcb', 'export', 'svg', '--layers', 'F.Fab,F.SilkS,F.CrtYd,Edge.Cuts,Dwgs.User',
    '--sketch-pads-on-fab-layers', '--page-size-mode', '2', '--mode-single', '-o', OUT / 'assembly.svg', PCB)
run('pcb', 'export', 'step', '--board-only', '--drill-origin', '--force', '-o', OUT / 'board-only.step', PCB)
(OUT / 'README.md').write_text((HERE / 'ASSEMBLY.md').read_text())
files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in ('SHA256SUMS', 'm1-quote.zip'))
(OUT / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in files))
archive(OUT / 'm1-quote.zip', [(p.name, p.read_bytes()) for p in files + [OUT / 'SHA256SUMS']])
print('Checked carrier quote package: 30 top-side parts; Gerbers, drills, BOM and placement included.')
