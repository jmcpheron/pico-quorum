---
name: pico-emu
description: Write and test MicroPython for the PicoQuorum console (Pico 2 W + Waveshare Pico-LCD-1.3, 240x240 screen, joystick + A/B/X/Y) on the emulator in emu/, then put it on a real board. Use for "build X for the Pico", "make a screen/animation/game for the console", "try this on the emulator", or "put it on the Pico".
---

# The PicoQuorum emulator

`emu/` runs the console in a browser: real MicroPython 1.26 (WebAssembly) running the same `.py`
files a board runs, the screen and buttons drawn flat with the keyboard mapped to them, and a CLI
so a bot can run code, press keys and look at the screen. Code that works here runs on the Pico
unchanged. The emulator started in Austin Griffith's
[picowallet](https://github.com/austintgriffith/picowallet) (MIT).

## The loop

1. Write a sketch: `emu/sketches/NAME.py` (module name = file name, no spaces, and not a firmware
   name like `lcd`, `quorum`, `net`, `signer`). `emu/sketches/snake.py` is a full example.
2. Run it: `tools/emu run NAME` (starts the server and opens the page if needed, reboots the
   device, imports the module, prints its output; exit 1 on a traceback). Running a module is
   `import NAME` on a fresh device, so a sketch must start itself at import: end the file with
   `start()` (that is also what puts it in the page's module menu). A module whose import never
   returns (a `while True`) is reported as "busy loop" after 2.5 s and keeps running.
3. Press keys: `tools/emu key A`, `tools/emu key right:300` (hold 300 ms),
   `tools/emu keys right,right,A`. Names: `A B X Y up down left right press`.
4. Look: `tools/emu shot [out.png]` saves the screen (480x480 PNG, default `emu/shots/latest.png`).
   Read the PNG. The built-in text is the 8x8 font, so check it is readable and inside 240x240.
5. Poke: `tools/emu exec 'NAME.some_state'` runs one REPL line and prints the result.
   `tools/emu log 60` shows recent console lines (print() output, tracebacks).
6. Iterate. `tools/emu reset` reboots into the main module; `tools/emu main NAME` sets it
   (default: `quorum`, the console).

No browser: `tools/emu headless NAME --wait 300 --key A --wait 100 --shot emu/shots/x.png --exec 'print(1)'`
runs a scripted session and exits (steps run in order). Good for quick checks and CI.

The person you're working with sees the page (http://localhost:4242): a module menu top left
(▶ run, ↻ reset and ⇪ send to Pico act on the picked module; Cmd/Ctrl+Enter runs the file in the
editor), the editor, the console, and the device. Keys on the page: W A S D = joystick, space =
joystick press, numpad 9 6 3 . = A B X Y (click the device first so the editor does not eat them).

## Ship it to a real Pico

`tools/emu devices` lists every board on this computer's USB: MicroPython boards, boards running
something else, and bootloader drives (plugged in with BOOTSEL held). `tools/emu flash --port P
[--wifi]` puts MicroPython on any of them (default 1.26.1, matching the console and the emulator;
`--wifi` picks the Pico W / Pico 2 W build, which the bootloader can't tell apart).

`tools/emu ship NAME [--port /dev/cu.usbmodemN] [--boot]` copies `NAME.py` and every file it
imports to the board, soft-resets so the old module's timers stop, imports the module fresh and
prints its output for a few seconds. That is a one-time run: at power-up MicroPython only runs
`main.py`. `--boot` (the page's "run at boot" box) also writes a `main.py` that imports the module.

**A board with a production image is tools/fw's.** `firmware/manifest.json` lists exactly what
goes on a console, and `tools/fw` (backup, push, verify, pin, logs, restore) puts it there, every
file hash-checked. `ship` and `tools/usb push` still work on a board whose `main.py` carries
`# picoquorum-image:` (since 2026-10-31), but they say so: a ship there copies past the manifest,
and its soft reset leaves the console's watchdog unfed, so the board may reset 8 s later. Neither
copies `secrets.py`. Never change `main.py` on someone's console unless asked.

## The hardware, as seen from Python

- Screen: 240x240, RGB565, ST7789 over SPI. `from lcd import LCD` then `lcd = LCD()`. `lcd` is a
  `framebuf.FrameBuffer`: `fill(c)`, `pixel(x,y[,c])`, `hline/vline(x,y,len,c)`, `line(x1,y1,x2,y2,c)`,
  `rect(x,y,w,h,c[,fill])`, `fill_rect(x,y,w,h,c)`, `ellipse(cx,cy,rx,ry,c[,fill[,quadrants]])`,
  `poly(x,y,coords,c[,fill])`, `text(s,x,y,c)` (8x8 font, one size), `blit(fb,x,y[,key])`,
  `scroll(dx,dy)`. Extras in lcd.py: `big_text(s,x,y,c,scale)`, `center_text(s,y,c,scale=1)`,
  `backlight(pct)`. Nothing appears until `lcd.show()`, which costs about 38 ms (SPI at 24 MHz),
  so full-frame animation tops out near 25 fps; `machine.freq(150_000_000, 150_000_000)` before
  `LCD()` lifts that to about 65 fps. Drawing is done in C and is fast; per-pixel Python loops are
  not. The console's anti-aliased fonts are in `fonts.py` (`qf_*.bin`).
- Colors: always `color(r, g, b)` from lcd.py (the panel wants byte-swapped RGB565; raw numbers
  come out wrong). Ready-made: `BLACK WHITE RED GREEN BLUE YELLOW GREY DARK`. The console's
  palettes are in `theme.py`.
- Keys: `keys = Keys()`; `keys.pressed()` returns names that went down since the last call;
  `keys.held("A")` for state. Layout: joystick on the left of the screen, buttons in a column on
  the right: A top, B, X, Y bottom. Console convention: A = yes/confirm (Sign is a held A),
  Y = no/back, X = quit a sketch.
- Loop styles. Timer: `Timer(period=40, mode=Timer.PERIODIC, callback=tick)`, return from the
  module, keep `tick` under ~30 ms, offer `stop()`; this is how the firmware runs, and it keeps the
  USB REPL free on the board. `while True` with `time.sleep_ms()` is fine for a game, but on the
  board it blocks the REPL until it returns, so always poll a quit key (X) inside the loop. Timer
  callbacks do not fire while a `while True` runs.
- Time: `time.ticks_ms()`, `time.ticks_diff(a, b)`, `time.sleep_ms()`. No `datetime`, no real clock.
- Memory: a few hundred KB of heap, no swap. Use `bytearray` for big tables, precompute palettes,
  avoid building large lists every frame, call `gc.collect()` between scenes. The emulator caps
  its heap at 448 KB so out-of-memory shows up here too.
- MicroPython, not CPython: no typing module, small stdlib (`math`, `random`, `struct`, `json`,
  `time`, `array`, `collections`), integer-first, f-strings ok. `@micropython.viper` speeds up
  per-pixel loops on the board (runs as plain bytecode in the emulator, slower).
- Firmware you can import: `quorum` (the console; `quorum.start()`), `chipapp` (the ceremony
  image's app: A provisions a fresh chip, X opens the chip map), `slots`, `chipmap`, `learn` and
  `snakelab` (the chip map's screens), `splash` (the boot screen), `icons` (16 px bitmaps,
  `icons.draw(d, "key", x, y, color, scale)`), `qrcode` (`qrcode.encode(text) -> (n, rows)`),
  `blockies`, `keccak`, `p256`, `signer`, `atecc`, `trustm`.
- The chip: a virtual ATECC608 answers at 0x60 on `machine.I2C`, speaking the real packet
  protocol, so `atecc.py` and `signer.ChipSigner` run unchanged. It starts as a BLANK part and
  keeps its state across reboots (server: `emu/chip.json`; headless: `--chip state.json`).
  `tools/emu chip ready` = config locked + key in slot 0, `fresh` = blank again, `show` = state,
  and `trustm-fresh|trustm-sealed|both|atecc` for the virtual Trust M. Permanent actions need
  `ALLOW_*` True (the emulator's secrets) AND the arm: hold B and Y for 3 s, or
  `--exec 'import signer; signer.arm()'` headless.

## Emulator vs board

Same: MicroPython version, framebuf, key names and pins, timers, SPI frame time, screen output
(pixel exact). Different: the CPU is much faster here (a loop that is smooth here may crawl on the
Pico: keep per-frame Python work small), viper is not native, the chips are models (no OTP, MAC or
encrypted transfers), the generated `secrets.py` sets `ALLOW_LOCK`/`ALLOW_GENKEY` True, `network`
is always connected, `requests` goes through the page, `machine.reset()` reboots the device, and
the flash is rebuilt from `firmware/` + `emu/sketches/` on every run (files a sketch writes vanish
at the next run).

## Files

`emu/server.mjs` (page + control API + service proxy, port 4242), `emu/web/` (page and worker),
`emu/core/runtime.mjs` (the device: pins, SPI display capture, timers), `emu/core/shims/*.py`
(`machine`, `network`, `requests`, `socket`, `rp2`, and the virtual chips `atecc_sim`, `trustm_sim`),
`emu/headless.mjs`, `emu/cli.mjs` (`tools/emu`), `emu/sketches/` (yours), `emu/shots/`
(screenshots, ignored by git).
