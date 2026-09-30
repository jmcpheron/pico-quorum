# The console on the original Waveshare picowallet

The original hardware (Pico 2 W, Waveshare Pico-LCD-1.3 at 240x240, joystick and A/B/X/Y, an ATECC608A)
got the current firmware, to show PicoQuorum on a second device and to sign a step of the new 3-of-5 Safe with
chip 1.

## What was needed

Almost nothing in the firmware: `board.py`'s default *is* this hardware (240x240, one 115 KB framebuffer, buttons
and joystick, maintenance = hold B). Build 1's knob and 320x240 strips are the special case. The board was already
a Pico 2 W on MicroPython 1.26.1 with chip 1 pinned. `tools/fw push console` put the image on (backup first,
22 files copied, 8 ceremony files removed, `secrets.py`, counters and snapshots kept).

## What broke, and why

**The console crashed at boot: `MemoryError` in `bootart.render`.** The orbit loading screen (2026-09-26) is
written for build1's 19 KB strip buffer. On the 240x240 board the frame alone is 115 KB, and after importing
the console about 109 KB of heap is left, so the animation ran it out. The board sat at its REPL (not a boot loop).
First fix: `splash.begin` uses the animation only where `BANDS > 1` (the single-buffer panel keeps the checklist).
That got the console up, but it was not enough (below).

**The real fix: strip-buffer the 240x240 board too.** With the 115 KB frame, HTTPS could not find its 16 KB block on some
boots: `OSError 12` on every call, `svc.lost`, 100 KB free but the largest free block only ~15 KB, and the console's own
restart (at most one per 10 minutes) landing on the same layout. `board.py` now strips any panel whose frame is over
45 KB (`BANDS = 8`, 30 rows: 14,400 bytes at 240 wide), as Build 1 does. That returns about 100 KB of heap, and the
boot animation (which is width-generic) runs on this board again, in strips. The 1.8" (41 KB) keeps one frame.
All suites pass in the emulator with the 240x240 board banded (console 124, Trust M 101, ceremony 79, display, bootart).

**A config write from the laptop reset the board.** `tools/quorum live pico` sends a script with `mpremote exec` while
the console runs. On this board the spare heap is small (readings between 6 KB and 106 KB free depending on whether
a TLS call was in progress), and the console's own protection fired at 23:33:01: `restart: the HTTPS reserve could
not be taken back (heap in pieces)`. USB dropped, the tool crashed, and nothing had been written. So on this board
**config edits go through maintenance** (a `maint` file, reset, `mpremote fs cp`, remove `maint`, reset), with the file
checked by hash. Build 1 has ~145 KB free and has not shown this.

## Numbers

Free heap on the 240x240 board, measured step by step from a soft reset: 276 KB after boot.py, 240 KB with all fonts,
198 KB with the 32 KB HTTPS reserve, **109 KB after importing the console**. Build 1 sits at ~145 KB after boot
with its 19 KB strip buffer instead of a 115 KB frame.
