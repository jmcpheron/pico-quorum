#!/usr/bin/env python3
"""Bootstrap the M1 console carrier using the installed KiCad Python and libraries.

Once the native CAD is edited, stop regenerating it. Refuses to overwrite without --force.
The external key adapter is a separate, unfinished design; see README.md.
"""
from pathlib import Path
import itertools
import json
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

import pcbnew as pcb

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'key-pcb'))
import gen

SHARE = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport')
if not SHARE.exists():
    SHARE = Path('/usr/share/kicad')
gen.KISYM = str(SHARE / 'symbols')
gen.DATE = '2026-10-07'
gen.HERE = str(HERE.parent)
counter = itertools.count()
gen.uid = lambda: str(uuid.uuid5(uuid.NAMESPACE_URL, 'picoquorum/console-m1/' + str(next(counter))))
if '--force' not in sys.argv and (HERE / 'm1.kicad_sch').exists():
    sys.exit('CAD exists. --force discards native schematic and PCB edits.')

BUTTONS = [('UP', 2, 4, 17, 69), ('DOWN', 18, 24, 17, 89),
           ('LEFT', 16, 21, 7, 79), ('RIGHT', 20, 26, 27, 79),
           ('SELECT', 3, 5, 43, 69), ('BACK', 17, 22, 59, 69),
           ('SIGN', 15, 20, 43, 89), ('REJECT', 21, 27, 59, 89)]
LCD = [('MOSI', 11, 15), ('SCK', 10, 14), ('CS', 9, 12),
       ('DC', 8, 11), ('RST', 12, 16), ('BL', 13, 17)]
KEY = ['GND', '+3V3', 'HOST_SDA', 'HOST_SCL', 'KEY_EN', 'KEY_FAULT', 'ATTACH_A', 'ATTACH_B']
PIN_NAMES = ['GP0', 'GP1', 'GND', 'GP2', 'GP3', 'GP4', 'GP5', 'GND', 'GP6', 'GP7',
             'GP8', 'GP9', 'GND', 'GP10', 'GP11', 'GP12', 'GP13', 'GND', 'GP14', 'GP15',
             'GP16', 'GP17', 'GND', 'GP18', 'GP19', 'GP20', 'GP21', 'GND', 'GP22', 'RUN',
             'GP26', 'GP27', 'AGND', 'GP28', 'ADC_VREF', '3V3_OUT', '3V3_EN', 'GND', 'VSYS', 'VBUS']
pin_nets = {str(pin): 'BTN_' + label for label, gp, pin, x, y in BUTTONS}
pin_nets.update({str(pin): 'MCU_' + label for label, gp, pin in LCD})
pin_nets.update({'6': 'HOST_SDA', '7': 'HOST_SCL', '9': 'KEY_EN', '10': 'KEY_FAULT',
                 '31': 'ATTACH_A', '32': 'ATTACH_B', '30': 'RUN', '36': '+3V3',
                 'D1': 'SWCLK', 'D2': 'GND', 'D3': 'SWDIO'})
for i, name in enumerate(PIN_NAMES, 1):
    if name in ('GND', 'AGND'):
        pin_nets[str(i)] = 'GND'

sh = gen.Sheet('m1')
for lib, name in [('Device', 'R'), ('Device', 'C'), ('Switch', 'SW_Push'),
                  ('power', 'PWR_FLAG'), ('power', 'GND')]:
    sh.lib(lib + ':' + name, gen.stock_symbol(lib, name))
pins = [(str(i), name, 'power_out' if i == 36 else ('power_in' if name in ('GND', 'AGND') else 'passive'),
         'L' if i <= 20 else 'R', 24.13 - 2.54 * ((i - 1) % 20)) for i, name in enumerate(PIN_NAMES, 1)]
pins += [('D1', 'SWCLK', 'input', 'B', -5.08), ('D2', 'GND', 'power_in', 'B', 0),
         ('D3', 'SWDIO', 'bidirectional', 'B', 5.08)]
pico = gen.box_symbol('Pico2W', 'U', 'Pico 2 W', 'console_m1:Pico2W_SMD',
                      'https://datasheets.raspberrypi.com/picow/pico-2-w-datasheet.pdf',
                      'Headerless Pico 2 W; power via its own USB socket; unused underside test pads voided',
                      10.16, 35.56, pins, mpn='SC1633')
def local_symbol(name, value, names, fp, desc):
    return gen.box_symbol(name, 'J', value, fp, '', desc, 5.08, 12.7,
                          [(str(i + 1), n, 'passive', 'R', 8.89 - 2.54 * i) for i, n in enumerate(names)])
lcd_names = ['+3V3', 'GND', 'LCD_MOSI', 'LCD_SCK', 'LCD_CS', 'LCD_DC', 'LCD_RST', 'LCD_BL']
j_lcd = local_symbol('LCD8', 'S8B-PH-SM4-TB', lcd_names,
                     'Connector_JST:JST_PH_S8B-PH-SM4-TB_1x08-1MP_P2.00mm_Horizontal',
                     'Carrier cable order; continuity-check to LCD labels, not cable colours')
j_key = local_symbol('Adapter8', 'INTERNAL ADAPTER PADS', KEY, 'console_m1:AdapterPads8',
                     'Internal host interface only, not a protected external key port')
tp = gen.box_symbol('TestPad', 'TP', 'TestPad', 'TestPoint:TestPoint_Pad_D2.0mm', '',
                    'Service test pad', 1.27, 1.27, [('1', 'TP', 'passive', 'L', 0)])
custom = [('Pico2W', pico), ('LCD8', j_lcd), ('Adapter8', j_key), ('TestPad', tp)]
(HERE / 'console_m1.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "picoquorum")\n' + '\n'.join(s for _, s in custom) + '\n)\n')
for name, sym in custom:
    sh.lib('console_m1:' + name, sym.replace('(symbol "' + name + '"', '(symbol "console_m1:' + name + '"', 1))
(HERE / 'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "console_m1")(type "KiCad")(uri "${KIPRJMOD}/console_m1.kicad_sym")(options "")(descr "M1 carrier symbols")))\n')
(HERE / 'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "console_m1")(type "KiCad")(uri "${KIPRJMOD}/console_m1.pretty")(options "")(descr "M1 carrier footprints")))\n')
layout = {}
def component(lib, ref, value, x, y, nums, fp, xy, fields=(), **kw):
    sh.symbol(lib, ref, value, x, y, nums, fp=fp, fields=fields, **kw)
    layout[ref] = xy
def label_pin(x, y, net, left=False):
    ex = x + (-5.08 if left else 5.08)
    sh.wire(x, y, ex, y)
    sh.label(net, ex, y, left=left)

sh.text('M1 CONSOLE CARRIER - USB POWER ON PICO\nEight active-low controls. Separate key protection adapter required.\nNo external USB-C key connector or switched key supply on this PCB.', 15.24, 12.7)
component('console_m1:Pico2W', 'U1', 'Pico 2 W', 45.72, 78.74,
          [p[0] for p in pins], 'console_m1:Pico2W_SMD', (16, 25.5, 0),
          [('MPN', 'SC1633')], box_h=35.56)
for i in range(1, 41):
    x = 33.02 if i <= 20 else 58.42
    y = 78.74 - (24.13 - 2.54 * ((i - 1) % 20))
    if str(i) in pin_nets:
        label_pin(x, y, pin_nets[str(i)], i <= 20)
    else:
        sh.nc(x, y)
for num, x in [('D1', 40.64), ('D2', 45.72), ('D3', 50.8)]:
    sh.wire(x, 116.84, x, 121.92)
    sh.label(pin_nets[num], x, 121.92)
sh.power('GND', 22.86, 119.38)
sh.power('PWR_FLAG', 22.86, 119.38)

for i, (label, gp, pin, bx, by) in enumerate(BUTTONS, 1):
    sx = 99.06 + ((i - 1) % 4) * 45.72
    sy = 55.88 + ((i - 1) // 4) * 45.72
    fp = 'Button_Switch_SMD:SW_SPST_TL3305A'
    component('Switch:SW_Push', 'SW' + str(i), 'TL3305AF160QG', sx, sy, ['1', '2'], fp,
              (bx, by, 0), [('MPN', 'TL3305AF160QG'), ('Function', label)])
    label_pin(sx - 5.08, sy, 'BTN_' + label, True)
    label_pin(sx + 5.08, sy, 'GND')
    sh.text(label, sx - 5.08, sy - 12.7)
    component('Device:R', 'R' + str(i), '10k', sx - 10.16, sy - 20.32, ['1', '2'],
              'Resistor_SMD:R_0603_1608Metric', (bx + 5.5, by - 3.3, 0), [('MPN', 'RC0603FR-0710KL')])
    sh.label('+3V3', sx - 10.16, sy - 24.13)
    sh.label('BTN_' + label, sx - 10.16, sy - 16.51)

component('console_m1:LCD8', 'J1', 'S8B-PH-SM4-TB', 93.98, 157.48,
          [str(i) for i in range(1, 9)], 'Connector_JST:JST_PH_S8B-PH-SM4-TB_1x08-1MP_P2.00mm_Horizontal',
          (50, 57, 0), [('MPN', 'S8B-PH-SM4-TB')], box_h=12.7)
for i, net in enumerate(lcd_names):
    label_pin(101.6, 148.59 + 2.54 * i, net)
for i, (name, gp, pin) in enumerate(LCD, 9):
    sx, sy = 137.16 + (i - 9) % 3 * 48.26, 149.86 + (i - 9) // 3 * 22.86
    component('Device:R', 'R' + str(i), '33R', sx, sy, ['1', '2'],
              'Resistor_SMD:R_0603_1608Metric', (2.6, 1.37 + (pin - 1) * 2.54, 180),
              [('MPN', 'RC0603FR-0733RL')])
    sh.label('MCU_' + name, sx, sy - 3.81)
    sh.label('LCD_' + name, sx, sy + 3.81)
component('console_m1:Adapter8', 'J2', 'INTERNAL ADAPTER PADS', 43.18, 157.48,
          [str(i) for i in range(1, 9)], 'console_m1:AdapterPads8', (36, 79, 0),
          in_bom=False, on_board=True, box_h=12.7)
for i, net in enumerate(KEY):
    label_pin(50.8, 148.59 + 2.54 * i, net)
for i, (net, value, bx, by, other) in enumerate([
        ('HOST_SDA', '2.2k', 2.25, 13, '+3V3'), ('HOST_SCL', '2.2k', 2.25, 16.5, '+3V3'),
        ('KEY_EN', '100k', 2.25, 20, 'GND'), ('KEY_FAULT', '10k', 2.25, 23.5, '+3V3')], 15):
    sx, sy = 137.16 + (i - 15) * 35.56, 201.93
    mpn = {'2.2k': 'RC0603FR-072K2L', '100k': 'RC0603FR-07100KL', '10k': 'RC0603FR-0710KL'}[value]
    component('Device:R', 'R' + str(i), value, sx, sy, ['1', '2'],
              'Resistor_SMD:R_0603_1608Metric', (bx, by, 90), [('MPN', mpn)])
    sh.label(net, sx, sy - 3.81)
    sh.label(other, sx, sy + 3.81)
for i, (value, mpn, bx, by) in enumerate([('100n', 'GRM188R71C104KA01D', 64, 53),
                                        ('10u', 'GRM188R60J106ME47D', 64, 57)], 1):
    sx, sy = 271.78, 147.32 + (i - 1) * 22.86
    component('Device:C', 'C' + str(i), value, sx, sy, ['1', '2'],
              'Capacitor_SMD:C_0603_1608Metric', (bx, by, 90), [('MPN', mpn)])
    sh.label('+3V3', sx, sy - 3.81)
    sh.label('GND', sx, sy + 3.81)
for i, net in enumerate(['SWCLK', 'SWDIO', 'GND', 'RUN'], 1):
    sx, sy = 93.98 + (i - 1) * 27.94, 129.54
    component('console_m1:TestPad', 'TP' + str(i), net, sx, sy, ['1'],
              'TestPoint:TestPoint_Pad_D2.0mm', (31, 26 + (i - 1) * 4, 0),
              in_bom=False, on_board=True)
    label_pin(sx - 3.81, sy, net, True)
sh.text('J2: HOST PADS ONLY. Adapter must switch/limit/reverse-block key power, isolate bus,\nprotect sense paths and handle removal. KEY_EN has a 100k default-off pull-down.\nLCD cable: meter every conductor to module labels before power. 3V3 operation only.\nNo firmware, provisioning or key-lock changes. Reduce SPI clock for cable bring-up.', 17.78, 184.15)
sh.write(str(HERE / 'm1.kicad_sch'), 'PicoQuorum M1 prototype console carrier')
s = (HERE / 'm1.kicad_sch').read_text().replace('(rev "A")', '(rev "M1-draft")').replace(
    'The PCB is the plug: see hardware/key-pcb/README.md', 'Console carrier only; protected key adapter separate; see README.md')
s = s.replace('(paper "A4")', '(paper "A3")')
(HERE / 'm1.kicad_sch').write_text(s)

board = pcb.BOARD()
ds = board.GetDesignSettings()
ds.SetBoardThickness(pcb.FromMM(1.6))
ds.SetCopperLayerCount(2)
ds.m_CopperEdgeClearance = pcb.FromMM(.3)
ds.SetAuxOrigin(pcb.VECTOR2I(pcb.FromMM(50), pcb.FromMM(145)))
ds.m_TentViasFront = ds.m_TentViasBack = True
def mm(x, y):
    return pcb.VECTOR2I(pcb.FromMM(x + 50), pcb.FromMM(y + 50))
def shape(a, b, layer=pcb.Edge_Cuts, width=.05):
    s = pcb.PCB_SHAPE()
    s.SetShape(pcb.SHAPE_T_SEGMENT)
    s.SetStart(mm(*a)); s.SetEnd(mm(*b)); s.SetLayer(layer); s.SetWidth(pcb.FromMM(width)); board.Add(s)
def text(value, x, y, size=.9, layer=pcb.F_SilkS):
    t = pcb.PCB_TEXT(board); t.SetText(value); t.SetPosition(mm(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcb.VECTOR2I(pcb.FromMM(size), pcb.FromMM(size))); t.SetTextThickness(pcb.FromMM(.12)); board.Add(t)
outline = [(0, 0), (70, 0), (70, 95), (0, 95), (0, 64), (38, 64),
           (38, 51.5), (23.2, 51.5), (23.2, 42.3), (8.8, 42.3), (8.8, 51.5), (0, 51.5)]
for a, b in zip(outline, outline[1:] + outline[:1]):
    shape(a, b)

libdir = HERE / 'console_m1.pretty'
libdir.mkdir(exist_ok=True)
pico_fp = pcb.FootprintLoad(str(SHARE / 'footprints/Module.pretty'), 'RaspberryPi_Pico_W_SMD')
pico_fp.SetFPID(pcb.LIB_ID('console_m1', 'Pico2W_SMD'))
for item in list(pico_fp.GraphicalItems()):
    if item.GetLayer() == pcb.F_SilkS:
        item.SetLayer(pcb.F_Fab)
# Stock RF rules include paste layers and flag the manufacturer's last-row paste
# apertures. Apply these rules to copper layers; leave the recommended paste intact.
for zone in pico_fp.Zones():
    if zone.GetLayer() != pcb.Edge_Cuts:
        layers = pcb.LSET(); layers.AddLayer(pcb.F_Cu); layers.AddLayer(pcb.B_Cu)
        zone.SetLayerSet(layers)
# Unused underside test points: void copper and paste, per the official datasheet.
for pad in list(pico_fp.Pads()):
    if pad.GetNumber().startswith('TP'):
        pos, size = pad.GetPosition(), pad.GetSize()
        z = pcb.ZONE(pico_fp); z.SetIsRuleArea(True); z.SetLayer(pcb.F_Cu)
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowPads(True); z.SetDoNotAllowZoneFills(True)
        x, y = pcb.ToMM(pos.x), pcb.ToMM(pos.y)
        h = .75 + .3
        poly = z.Outline(); poly.NewOutline()
        for px, py in [(x-h, y-h), (x+h, y-h), (x+h, y+h), (x-h, y+h)]:
            poly.Append(pcb.FromMM(px), pcb.FromMM(py))
        pico_fp.Add(z); pico_fp.Remove(pad)
    elif not pad.GetNumber() and pad.IsOnLayer(pcb.F_Cu):
        pad.SetNumber('D2')  # USB shell solder lands are ground, like DEBUG_GND.
writer = pcb.PCB_IO_MGR.FindPlugin(pcb.PCB_IO_MGR.KICAD_SEXP)
writer.FootprintSave(str(libdir), pico_fp)
adapter = pcb.FOOTPRINT(None); adapter.SetFPID(pcb.LIB_ID('console_m1', 'AdapterPads8'))
adapter.SetAttributes(pcb.FP_EXCLUDE_FROM_BOM | pcb.FP_EXCLUDE_FROM_POS_FILES)
for i in range(8):
    pad = pcb.PAD(adapter); pad.SetNumber(str(i + 1)); pad.SetAttribute(pcb.PAD_ATTRIB_SMD)
    pad.SetShape(pcb.PAD_SHAPE_RECT); pad.SetSize(pcb.VECTOR2I(pcb.FromMM(2), pcb.FromMM(3)))
    layers = pcb.LSET(); layers.AddLayer(pcb.F_Cu); layers.AddLayer(pcb.F_Mask)
    pad.SetPosition(pcb.VECTOR2I(pcb.FromMM(i * 4), 0)); pad.SetLayerSet(layers); adapter.Add(pad)
writer.FootprintSave(str(libdir), adapter)
(HERE / 'm1.kicad_pro').write_text('{}\n')
with tempfile.TemporaryDirectory() as tmp:
    netpath = Path(tmp) / 'net.xml'
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml',
                    '-o', str(netpath), str(HERE / 'm1.kicad_sch')], check=True)
    root = ET.parse(netpath).getroot()
comps = {}
for node in root.findall('components/comp'):
    ref = node.get('ref')
    comps[ref] = dict(value=node.findtext('value'), footprint=node.findtext('footprint'),
                      path='/' + node.findtext('tstamps'), pads={},
                      fields={f.get('name'): f.text or '' for f in node.findall('fields/field') if f.get('name') in ('MPN', 'Function')})
for node in root.findall('nets/net'):
    for endpoint in node.findall('node'):
        comps[endpoint.get('ref')]['pads'][endpoint.get('pin')] = node.get('name')
nets = {}
for name in sorted({net for c in comps.values() for net in c['pads'].values()}):
    net = pcb.NETINFO_ITEM(board, name); board.Add(net); nets[name] = net
for ref, c in comps.items():
    if not c['footprint']:
        continue
    lib, name = c['footprint'].split(':')
    path = libdir if lib == 'console_m1' else SHARE / 'footprints' / (lib + '.pretty')
    f = pcb.FootprintLoad(str(path), name)
    f.SetFPID(pcb.LIB_ID(lib, name)); f.SetReference(ref); f.SetValue(c['value'])
    f.SetPath(pcb.KIID_PATH(c['path'])); f.SetSheetname('/'); f.SetSheetfile('m1.kicad_sch')
    for k, v in c['fields'].items():
        f.SetField(k, v); f.GetField(k).SetVisible(False)
    if ref.startswith(('TP', 'J2')):
        f.SetAttributes(f.GetAttributes() | pcb.FP_EXCLUDE_FROM_BOM | pcb.FP_EXCLUDE_FROM_POS_FILES)
    board.Add(f)
    x, y, angle = layout[ref]; f.SetPosition(mm(x, y)); f.SetOrientationDegrees(angle)
    f.Value().SetVisible(False); f.Reference().SetVisible(False)
    for pad in f.Pads():
        if pad.GetNumber() in c['pads']:
            pad.SetNet(nets[c['pads'][pad.GetNumber()]])
for i, (x, y) in enumerate([(33, 4), (66, 4), (4, 91), (67.5, 92)], 1):
    f = pcb.FootprintLoad(str(SHARE / 'footprints/MountingHole.pretty'), 'MountingHole_2.7mm_M2.5')
    f.SetReference('H' + str(i)); f.SetValue('M2.5'); f.SetPosition(mm(x, y))
    f.SetAttributes(pcb.FP_EXCLUDE_FROM_BOM | pcb.FP_EXCLUDE_FROM_POS_FILES | pcb.FP_BOARD_ONLY)
    f.Reference().SetVisible(False); f.Value().SetVisible(False); board.Add(f)
for label, gp, pin, x, y in BUTTONS:
    text(label, x, y + 4.7, .85)
for i, net in enumerate(['GND', '3V3', 'SDA', 'SCL', 'EN', 'FLT', 'A', 'B']):
    text(net, 36 + i * 4, 82.5, .8)
for a, b in [((37.5, 3), (68.5, 3)), ((68.5, 3), (68.5, 48)),
             ((68.5, 48), (37.5, 48)), ((37.5, 48), (37.5, 3))]:
    shape(a, b, pcb.Dwgs_User, .15)
text('LCD MODULE ENVELOPE 31 x 45\nCase support; exact mounting TBD', 53, 25, 1, pcb.Dwgs_User)
text('M1 CARRIER\nKEY ADAPTER REQUIRED', 53, 43, .85)
text('https://github.com/\njmcpheron/pico-quorum', 51, 34, .8)
text('3V3 HOST ONLY', 50, 84.5, .8)
text('USB POWER', 16, 4, .8, pcb.Dwgs_User)
text('No copper/components in antenna cutout or forward RF clearance.', 35, 101, 1, pcb.Dwgs_User)
tb = board.GetTitleBlock(); tb.SetTitle('PicoQuorum M1 prototype carrier'); tb.SetRevision('M1'); tb.SetDate(gen.DATE)
pcb.SaveBoard(str(HERE / 'm1.kicad_pcb'), board)
(HERE / 'm1.kicad_pro').write_text(json.dumps({'meta': {'filename': 'm1.kicad_pro', 'version': 1},
    'net_settings': {'classes': [{'name': 'Default', 'clearance': .2, 'track_width': .25,
                                 'via_diameter': .7, 'via_drill': .3}], 'meta': {'version': 4}}}, indent=2) + '\n')
print('Wrote native carrier schematic and netted PCB. Routing and verification follow.')
