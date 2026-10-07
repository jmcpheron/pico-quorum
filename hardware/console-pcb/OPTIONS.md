# Console boards: the options

Today a console is hand-built: either the Waveshare dev console (a Pico 2 W, a Pico-LCD-1.3 and a
breakout, about $35) or Build 1's knob, screen and jacks on wires. That's fine for one or two. For
20–100 people it's too much soldering, and neither one has a port that key-c plugs into. This page
compares the boards that would fix that, and says why [console-a](README.md) is the one drawn.

Two facts shape every option:
- **The console needs Wi-Fi.** It talks to Safe's transaction service itself, over its own Wi-Fi
  and TLS (`firmware/txservice.py`). So it's a Pico 2 W, or an RP2350 with Raspberry Pi's RM2
  radio. A plain Pico 2 would mean redesigning how the console reaches the app.
- **The firmware already knows two boards.** `firmware/board.py` has "waveshare" (joystick,
  A/B/X/Y, 1.3″ screen) and "build1" (knob, A/B/X/Y, 2.8″ screen). A board that copies one of them
  pin for pin runs today's console image. A new pin map would be a firmware change, and so a new
  release fingerprint (AGENTS.md rule 2).

And one about the key: **key-c has a USB-C socket, not a plug.** So the console needs a male USB-C
plug. Board-mounted male plugs are less common than sockets, but JLCPCB stocks a vertical one
(C399939) that KiCad has a footprint for.

## The options

Costs are per console, for the board assembled by JLCPCB plus the parts you solder yourself. They
leave out the screen module, shipping, tax and a case. They are estimates, not a quote:
- part prices are JLCPCB's on 2026-10-07
- fees are key-c's: about $28 an order for setup, stencil and $3.09 per extended part type
- bare boards are guessed at about $10 for 5, $20 for 20 and $50 for 100

The real number comes from uploading the files.

| | option | 5 | 20 | 100 | |
|---|---|---|---|---|---|
| 0 | **No new console board.** Pico 2 W + Waveshare Pico-LCD-1.3 as today, plus a small key-port board wired to GP4/5/6/26/27 | ~$33 | ~$30 | ~$28 | includes its screen; still hand-assembled; still the 1.3″ screen |
| 1 | **Waveshare clone.** One board: Pico 2 W, a bare 1.3″ 240×240 panel on an FPC connector, a 5-way SMD joystick (Alps SKRHABE010, C139794, $0.77), four SMD buttons, the key port | ~$22 | ~$17 | ~$15 | all surface mount; `BOARD = "waveshare"`, no firmware change; the panel plugs in by hand |
| 2 | **console-a** (drawn). Pico 2 W, Build 1's 2.8″ module on a header, a knob, four buttons, the key port, an LED | ~$24 | ~$18 | ~$17 | `BOARD = "build1"`, no firmware change; the knob and the screen header are through-hole |
| 3 | **Our own RP2350 + RM2.** The chip, flash, crystal and regulator on the board, with the RM2 radio module and a USB-C power port | ~$27 | ~$18 | ~$15 | smallest; the most design risk; JLCPCB had 17 RM2s |
| 4 | **Battery deluxe.** console-a plus a LiPo charger, a power switch and the battery gauge on GP28 | ~$26 | ~$19 | ~$18 | plus the battery (~$5) and lithium shipping rules |

**The Pico is most of the cost.** JLCPCB sells the Pico 2 W for assembly (C42394205) at $11.68,
with 82 in stock on 2026-10-07. Retail is about $7. At 100 boards, buying Picos yourself and
sending them to JLCPCB (consigned parts) saves about $4.70 a console, and is needed anyway unless
their stock grows.

**Why not our own RP2350 (option 3) yet.** On 2026-10-07 the parts it replaces the Pico with cost about $10 at
JLCPCB: RP2350A $1.29, flash $0.60–1.58, RM2 $6.50, and a few cents of crystal, regulator and
inductor. That saves under $2 a console. In return the board takes on the RP2350's power design,
the crystal, the flash and the radio's antenna keep-out, and probably four layers. It makes sense
later, at higher volume or for a smaller case.

**Why console-a over the Waveshare clone.** The clone is a few dollars cheaper and all surface mount.
console-a has the bigger screen, which matters for reading addresses and amounts, and it is the
kickoff's console: a knob with Sign and Reject. The firmware's knob mode already drives every
screen (`firmware/quorum.py`, `knob()`). Either one runs today's console image.

## Surface mount or through-hole

JLCPCB's Economic assembly places surface-mount parts on the top side only. That covers everything
on console-a except two parts:
- **The knob.** Surface-mount encoders exist (Alps EC11J), but JLCPCB had none, and Alps' usual
  30-detent, 15-pulse parts would turn the menu every other click: `firmware/knob.py` counts 4
  steps a click. console-a uses a Bourns PEC11R-4215F-S0024 (24 detents, 24 pulses, push switch),
  through-hole. That's 5 pins and 2 tabs to solder, and the tabs take the knob's torque.
- **The screen's 8-pin header**, because the module is bought separately.

So each console needs 15 joints by hand. For 20–100 consoles, JLCPCB's Standard assembly can solder
both parts too: it costs more to set up (about $25 a side) but needs no hand work. The 5-way
joystick in option 1 is surface mount, so that board needs no hand soldering except the panel's
connector, if the panel is the plug-in kind.

## The key port, on every option

Every option needs the same console end of key-c, from
[PROPOSALS.md](../key-pcb/PROPOSALS.md#the-console-end-of-key-c):
- a current-limited, reverse-blocking switch on VBUS, enabled by GP6
- CC read on its own ADC pin or pins
- 2.2 kΩ pull-ups to the switched VBUS
- ESD on every line

console-a's port is in [README.md](README.md#the-key-port). It works as it is on options 1, 3 and
4, and as a small board of its own for option 0.
