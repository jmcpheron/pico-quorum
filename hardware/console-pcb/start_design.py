#!/usr/bin/env python3
"""Bootstrap the controls sheet and placement study with KiCad's Python.

Not a complete console design. Refuses to overwrite native CAD unless --force is given.
Once editing in KiCad, treat the CAD files as the source and stop regenerating them.
"""
from pathlib import Path
import itertools
import sys
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'key-pcb'))
import gen
import pcbnew as pcb

SHARE = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport')
if not SHARE.exists():
    SHARE = Path('/usr/share/kicad')
gen.KISYM = str(SHARE / 'symbols')
gen.DATE = '2026-10-07'
counter = itertools.count()
gen.uid = lambda: str(uuid.uuid5(uuid.NAMESPACE_URL, 'picoquorum/console-controls/' + str(next(counter))))

outputs = [HERE / 'controls.kicad_sch', HERE / 'placement-study.kicad_pcb']
if '--force' not in sys.argv and any(p.exists() for p in outputs):
    sys.exit('CAD already exists. Use --force only to discard edits to these two draft files.')

sheet = gen.Sheet('controls')
for lib, name in [('Device', 'R'), ('Switch', 'SW_Push'), ('power', '+3V3'), ('power', 'GND'), ('power', 'PWR_FLAG')]:
    sheet.lib(lib + ':' + name, gen.stock_symbol(lib, name))
enc = gen.box_symbol('PEC11J', 'SW', 'PEC11J-9215F-S0015', '',
    'https://www.bourns.com/docs/product-datasheets/pec11j.pdf',
    'Encoder with push switch; physical footprint pending independent dimension check',
    7.62, 10.16, [('A', 'A', 'passive', 'L', 5.08), ('B', 'B', 'passive', 'L', 0),
                 ('C', 'COM', 'passive', 'L', -5.08), ('D', 'SW', 'passive', 'R', 5.08),
                 ('E', 'SW', 'passive', 'R', -5.08)])
(HERE / 'console.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "picoquorum")\n' + enc + '\n)\n')
(HERE / 'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "console")(type "KiCad")(uri "${KIPRJMOD}/console.kicad_sym")(options "")(descr "Console draft symbols")))\n')
sheet.lib('console:PEC11J', enc.replace('(symbol "PEC11J"', '(symbol "console:PEC11J"', 1))
sheet.text('CONTROLS SUBCIRCUIT ONLY - NOT A COMPLETE CONSOLE\nNamed nets go to the Pico GPIOs shown. No MCU, display, supply or key-port circuit on this sheet.\nActive-low switches. External 10k pull-ups to console 3V3; never use 5V.\nPhysical encoder footprint and final resistor procurement codes are not assigned.', 20.32, 15.24)

signals = ['GP3_ENC_A', 'GP2_ENC_B', 'GP1_ENC_PUSH', 'GP15_SIGN', 'GP21_REJECT', 'GP17_BACK', 'GP19_DEVICE']
for i, net in enumerate(signals):
    x, y = 25.4 + i * 35.56, 55.88
    sheet.symbol('Device:R', 'R' + str(i + 1), '10k', x, y, ['1', '2'],
                 fp='Resistor_SMD:R_0603_1608Metric')
    sheet.power('+3V3', x, y - 6.35)
    sheet.wire(x, y - 6.35, x, y - 3.81)
    sheet.wire(x, y + 3.81, x, y + 8.89)
    sheet.label(net, x, y + 8.89)

sheet.symbol('console:PEC11J', 'SW1', 'PEC11J-9215F-S0015', 53.34, 106.68,
             ['A', 'B', 'C', 'D', 'E'], box_h=10.16)
for x,y,net,left in [(43.18,101.6,signals[0],True),(43.18,106.68,signals[1],True),
                     (63.5,101.6,signals[2],False)]:
    ex = x - 7.62 if left else x + 7.62
    sheet.wire(x,y,ex,y)
    sheet.label(net,ex,y,left=left)
for x in [43.18,63.5]:
    sheet.wire(x,111.76,x,121.92)
    sheet.power('GND',x,121.92)
sheet.text('A/B ordering follows board.py.\n30 detents / 15 pulses per turn:\nverify steps per detent (likely 2, not current 4).\nPush is navigation only, never Sign.', 22.86, 137.16)

for i,(net, label, x,y) in enumerate([(signals[3],'SIGN',119.38,99.06),(signals[4],'REJECT',210.82,99.06),
                                     (signals[5],'BACK',119.38,134.62),(signals[6],'DEVICE',210.82,134.62)]):
    sheet.symbol('Switch:SW_Push','SW'+str(i+2),'TL3305AF160QG',x,y,['1','2'],
        fp='Button_Switch_SMD:SW_SPST_TL3305A', fields=[('MPN','TL3305AF160QG'),('Function',label)])
    sheet.items[-1] = sheet.items[-1].replace(f'(at {x+2.54} {y+1.27} 0)', f'(at {x+2.54} {y-4.5} 0)')
    sheet.wire(x-5.08,y,x-12.7,y)
    sheet.label(net,x-12.7,y,left=True)
    sheet.wire(x+5.08,y,x+10.16,y)
    sheet.wire(x+10.16,y,x+10.16,y+7.62)
    sheet.power('GND',x+10.16,y+7.62)
    sheet.text(label,x-5.08,y-10.16)

sheet.power('+3V3',22.86,175.26)
sheet.wire(22.86,175.26,35.56,175.26)
sheet.power('PWR_FLAG',35.56,175.26)
sheet.power('GND',48.26,175.26)
sheet.power('PWR_FLAG',48.26,175.26)
sheet.text('Power flags describe the host-supplied interface; they do not implement a power supply.\nPreserve firmware review gates and the single signing site. Reject remains one easy press.\nNo firmware, chip configuration or provisioning changes in this draft.',68.58,170.18)
sheet.write(str(outputs[0]), 'PicoQuorum controls - draft subcircuit')
s = outputs[0].read_text().replace('(rev "A")','(rev "D0")').replace(
    'The PCB is the plug: see hardware/key-pcb/README.md',
    'SUBCIRCUIT ONLY - hardware/console-pcb/RESEARCH.md - NOT FOR FABRICATION')
outputs[0].write_text(s)

# The placement study deliberately has no nets or copper routing. It is not the PCB
# counterpart of the controls subcircuit and must not be used for manufacturing exports.
board = pcb.BOARD()
board.GetDesignSettings().SetBoardThickness(pcb.FromMM(1.6))
origin = (50,50)
def mm(x,y):
    return pcb.VECTOR2I(pcb.FromMM(x+origin[0]),pcb.FromMM(y+origin[1]))
def line(x1,y1,x2,y2,layer=pcb.Dwgs_User,width=.15):
    s=pcb.PCB_SHAPE(); s.SetShape(pcb.SHAPE_T_SEGMENT); s.SetStart(mm(x1,y1)); s.SetEnd(mm(x2,y2))
    s.SetLayer(layer); s.SetWidth(pcb.FromMM(width)); board.Add(s)
def rect(x,y,w,h,layer=pcb.Dwgs_User):
    for a,b,c,d in [(x,y,x+w,y),(x+w,y,x+w,y+h),(x+w,y+h,x,y+h),(x,y+h,x,y)]: line(a,b,c,d,layer)
def text(s,x,y,size=1.3,layer=pcb.Dwgs_User):
    t=pcb.PCB_TEXT(board); t.SetText(s); t.SetPosition(mm(x,y)); t.SetTextSize(pcb.VECTOR2I(pcb.FromMM(size),pcb.FromMM(size)))
    t.SetTextThickness(pcb.FromMM(.18)); t.SetLayer(layer); board.Add(t)
def footprint(lib,name,ref,value,x,y,angle=0):
    f=pcb.FootprintLoad(str(SHARE/'footprints'/(lib+'.pretty')),name)
    if f is None: raise ValueError(name)
    f.SetReference(ref); f.SetValue(value); f.SetPosition(mm(x,y)); f.SetOrientationDegrees(angle)
    f.Value().SetVisible(False); board.Add(f); return f
rect(0,0,120,100,pcb.Edge_Cuts)
footprint('Module','RaspberryPi_Pico_W_SMD','U1','Pico 2 W',26.5,15,270)
for ref,label,x,y in [('SW2','SIGN',60,90),('SW3','REJECT',20,90),('SW4','BACK',92,90),('SW5','DEVICE',110,90)]:
    footprint('Button_Switch_SMD','SW_SPST_TL3305A',ref,'TL3305AF160QG',x,y)
    text(label,x,y+5,.9)
for i,(x,y) in enumerate([(58,6),(114,6),(5,95),(114,78),(90,52),(112,52)]):
    footprint('MountingHole','MountingHole_2.7mm_M2.5','H'+str(i+1),'M2.5 proposed',x,y)
rect(10,27,70,51); text('DISPLAY ENVELOPE ONLY',45,45); text('70 x 51 - ribbon exit TBD',45,49,1.1)
rect(90.5,56.5,19,19); text('SW1 ENCODER',100,63,1); text('No pads yet',100,69,1)
rect(89,5.5,22,25); text('DOCK',100,15,1.2); text('0.8 mm candidate',100,19,1)
rect(61,4,18,14); text('POWER',70,10,1); text('TBD',70,14,1)
text('DRAFT - NO NETS OR ROUTING - NOT FOR FABRICATION',62,98,.9,pcb.F_SilkS)
text('Not fabrication-ready. Screen, knob and dock are envelopes.',60,108,1)
text('https://github.com/jmcpheron/pico-quorum',60,81,1,pcb.F_SilkS)
pcb.SaveBoard(str(outputs[1]),board)
print('Wrote controls.kicad_sch and placement-study.kicad_pcb (draft only).')
