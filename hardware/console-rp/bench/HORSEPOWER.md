# console-rp: how much there is to work with

Measured on the first board on 2026-11-04, on the stock Pico 2 MicroPython 1.26.1 at the RP2350's
default 150 MHz. Bench scripts in this folder did it. None opens the key's bus.
- `horsepower.py`: the CPU, the heap, the Safe hash, drawing, SPI1, DMA, and five kinds of animation.
- `pio_screen.py`: the screen driven by PIO instead of SPI1.
- `linkbench.py`, with `linkhost.py` on the computer: the link on UART1 at 460800 (below).

All ran through `rawrepl.py`. `put.py` copied `keccak.py`, `safe_tx.py`, `qf_bold18.bin` and
`qf_sans14.bin` from `firmware/` onto the board first. Each number is a mean of 3 to 20 runs.

## In short

The screen has room for animation. The hash is what's slow.
- A full frame of drawing costs about 13 ms in C.
- Sending a frame costs 26 ms over SPI1, or 9 ms over PIO.
- Rebuilding a Safe transaction hash costs **564 ms** of pure-Python Keccak, longer than any of that.

## The board

| what | measured |
|---|---|
| CPU | RP2350, Cortex-M33 at 150 MHz; MicroPython uses one core |
| heap free at start | 390 KB |
| largest single block | 328 KB: room for five full frames (64.8 KB each) |
| filesystem | 3,072 KB, 3,028 KB free. The flash is 16 MB; the Pico 2 image uses the first 4 MB of it |
| heap free after every test | 371 KB |

The RP2040 boards had to allocate their framebuffer before anything else or fail with MemoryError
(`firmware/lcd.py`). This board has room for two whole frames and a sprite sheet beside them.

## The CPU

| what | measured |
|---|---|
| a `for` loop adding ints, plain Python | 0.16 M a second |
| the same, `@micropython.native` | 0.20 M a second |
| the same, `@micropython.viper` | 6.21 M a second, 39 times plain Python |
| `keccak256` of 32 bytes (one block) | 91 ms |
| `keccak256` of 1 KB (8 blocks) | 740 ms |
| `safe_tx_hash` of a USDC transfer (68 bytes of data, the domain not cached) | 564 ms |

The hash is `firmware/keccak.py`, pure Python on 64-bit ints. Every lane is a bignum on a 32-bit
CPU. A batch of a few kilobytes of calldata would take seconds.

## Drawing (framebuf, in C)

| what | measured |
|---|---|
| fill the whole frame | 1.3 ms |
| 16 lines of 8×8 text, 30 characters each | 4.9 ms |
| 50 blits of a 32×32 sprite | 24 ms |
| a review page in the console's own anti-aliased fonts: a bold18 title, five sans14 lines, a footer | 13 ms |
| every pixel worked out in Viper (a plasma) | 21 ms |

## Sending it to the screen

**SPI1 stops at 24 MHz.** MicroPython runs the RP2350's peripheral clock at 48 MHz, and SPI can't go
past half of it. Asking for 25, 37.5, 62.5 or 75 MHz all gave 24 MHz (`repr(spi)`). So `board.py`'s
`SPI_BAUD` doesn't matter above 24 MHz on an RP2350.

**PIO isn't held to that.** A two-instruction PIO program runs from the 150 MHz system clock, on the
same pins, with DMA feeding it.

| how | clock | one full frame | most frames a second |
|---|---|---|---|
| SPI1, `spi.write` | 24 MHz | 26.0 ms | 38 |
| SPI1, DMA | 24 MHz | 26.3 ms, the CPU free meanwhile | 38 |
| PIO, DMA | 37.5 MHz | 14.4 ms | 69 |
| PIO, DMA | 50 MHz | 10.9 ms | 91 |
| PIO, DMA | 62.5 MHz | 8.9 ms | 113 |
| PIO, DMA | 75 MHz | 7.5 ms | 134 |

The person at the bench watched a test card at each PIO rate: the big rate, red, green and blue
swatches, one-pixel lines and a dotted row. All four looked clean, and the same. The ST7789's
datasheet asks for a write cycle of 16 ns or more, which is 62.5 MHz; 75 MHz is past it, so don't
count on 75 MHz across panels.

## Animation

| kind | measured |
|---|---|
| the whole frame redrawn and sent each time (a page sliding), SPI1 | 21 fps |
| the same, two buffers, frame n going out by DMA while n+1 is drawn, SPI1 | 38.5 fps |
| the same, two buffers, PIO at 62.5 MHz | 112 fps |
| only what moved: a 44×44 block, sent as its own window, SPI1 | 523 fps |
| a 32×32 busy spinner, 8 dots | 1.7 ms a frame: 5% of the CPU at 30 fps |
| every pixel in Viper, sent each frame, SPI1 | 21.5 fps |

## The boot animation

`bootanim.py` plays the console's own boot mark (`firmware/bootmark.py`, the default) with the
console's `lcd.py`, `fonts.py` and `splash.py`, unchanged. `board_rp.py` stands in for `board.py`.
At 240 × 135 the mark takes its small layout, the one drawn for the 1.8″ panel. It sends only what
changed each frame, over SPI1 at 24 MHz.

| how | frames a second | frame cost, median / max | longest gap |
|---|---|---|---|
| alone, three plays | 30.7, 31.6, 31.3 | 20 ms / 54 ms | 65 ms |
| on `splash.run()`'s timer while the console starts | 27.1 | 20 ms / 73 ms | **743 ms**, once |

The start was simulated as it would be with no Wi-Fi. It compiled a 25 KB module (720 ms), hashed an
owner address (two Keccaks) and collected.
- **The one freeze is the compile.** Compiling is C work, so the soft timer can't draw a frame until
  it ends. Nothing else held a frame up.
- **The Keccaks didn't freeze it.** They are Python, and frames went on between their bytecodes. But
  sharing the CPU with the animation, they took 1.6 s instead of about 0.2 s.

The other boards' hangs came from the same kinds of thing, with Wi-Fi and TLS added: both are long C
work, and `bootmark.py`'s header says the mark stops still because of them. Without Wi-Fi, what's
left is compiling, and that can move to before the first frame, or be done once ahead of time.

## Screens tried on the bench

Prototypes run on the first board with its buttons. None is the console's firmware, and none asks
the key for anything. `demo.py` puts the last three behind one menu.
- **`loaders.py`**: four loading screens after the boot mark, laid out for 240 × 135, looping until
  RESET. A quorum ring, the chip waking, the Ethereum logo turning, and a verify code with its
  blockie. 22 to 40 fps on SPI1, each sending only the regions that changed.
- **`hackui.py`**: a reimagined review on a terminal-and-CRT look, driven by the board's buttons as a
  VCR's: D0 ■ Reject, D1 ▶ Next, D2 ● Sign (held 2 s, 3 s on a red page, lit once every page is
  seen). Two made-up transactions, one a red page.
  - **The hash page.** While `firmware/safe_tx.py` works out the Safe hash, the screen shows the
    Keccak state live. Its first four lanes become the hash when the last pass ends. #7's hash on the
    board matched CPython's.
  - **The verify page.** Grey hex noise, then cells turning blue with the hash's characters, then the
    green code and the blockie locking in (FX3, below).
  - **What is a demo.** "Signed" is a demo screen, and the service match is a placeholder.
- **`keypick_crt.py`**: the key pick (`firmware/keypick_s.py`'s Make, Pick, Keep) in the same look.
  **No key is made.** This chip's config zone is open, so it can't run GenKey, and locking can't be
  undone.
  - **What is real.** The noise is `os.urandom`, read fresh each frame. 64 of those bytes stand where
    GenKey's public key would be. `webauthn.owner_address` works out the Safe owner they would have
    (about 1.8 s), with the Keccak state on screen, and the blockie is that address's.
  - **What is a demo.** "Sealed" is a demo screen: nothing is written.
- **`glitchfx.py`**: three ways a page can arrive out of the noise, compared by number on the
  board: FX1 tear & settle, FX2 block decode, FX3 signal lock.

The person at the bench kept FX1 and FX3, and `hackui.py` uses them as two meanings (`arrive`):
- **FX1 tear: something arrives or changes.** The menu, the queue, opening a transaction, the key's
  intro, and Rejected. Harder for a red page. Page turns get a short one.
- **FX3 lock: worked out here, and checked.** The verify code, a key's owner address, Signed and
  Sealed.

## The link on UART1, at 460800

Measured on 2026-11-04 with `linkbench.py` on the board and `linkhost.py` on the Mac, before
`link.py` was written. UART1 ran 8N1 at 460800 through the CH343P, with no flow control: its RTS and
CTS go nowhere. The computer sent lines of 1, 16 and 40 KB, each holding its own CRC-32. Each size was
sent three times, while the board was doing one of three things.

| while the line arrived | rxbuf 4 KB | rxbuf 16 KB | rxbuf 24 or 32 KB |
|---|---|---|---|
| reading it (`any`, `readinto`) | every line whole, 40 KB too | every line whole | every line whole |
| hashing (`safe_tx_hash` in a loop, never reading) | whole up to 4 KB; the rest lost | whole up to 16 KB | whole up to the rxbuf |
| writing flash (littlefs, 4 KB at a time) | 32-124 bytes of any line | 32-170 bytes | not tried |

- **Reading keeps up.** A Python loop on `readinto` takes 460800 with no loss, so a line can be
  far longer than the rxbuf as long as the board is reading it.
- **What arrives while the board is busy waits in the rxbuf.** The ring buffer keeps its first rxbuf
  bytes plus the FIFO's 32, and loses the rest. MicroPython 1.26.1 on the RP2350 refuses more than
  32766 bytes ("rxbuf too large").
- **Writing flash loses the line.** The RP2350 stops interrupts while it erases and programs, and
  then only the UART's 32-byte FIFO catches what comes. A 1 KB line kept 32 bytes, even with a 16 KB
  rxbuf.
- **The other way is clean.** The board wrote lines of 1, 16 and 40 KB, all whole. A 40 KB line took
  804 ms; a 4 KB txbuf holds the tail.

**The double parse.** A 40 KB Safe queue answer (32 transactions) wrapped as the relay sends it, a
43.6 KB line:
- the envelope parses in 241 ms;
- its body in 108 ms;
- 90 KB of heap goes while both exist;
- the parsed queue that stays is 12 KB.

**What `link.py` takes from this:**
- 460800 is fine.
- rxbuf 16 KB: an ask that comes in while the board is hashing is kept.
- Lines up to 48 KB, read into one buffer allocated at start.
- **Nothing writes flash while a request waits for its answer.**
- The computer must ask again when an ask gets no answer: one that lands while the board writes its
  log is lost.

## The heap with the whole console running

Measured on 2026-11-04 on the first board, with the console-rp image (`tools/fw build console-rp`,
loaded by `swdload.py --image`). The link's `status` collects and then reads `gc.mem_free()`.

| when | free |
|---|---|
| at start, before anything (above) | 390 KB |
| the console running, unconfigured (a factory 608C, no key), the relay saying hi | **70 KB** (70,192 bytes) |
| the key flow on the same chip (Not prepared), the CRT screens, the 24 KB line buffer | **84 KB** (84,064 bytes) |

What holds the rest: the 64.8 KB frame, the link's 48 KB line buffer, every font, and the console's
bytecode. An `.mpy` file is loaded into the heap on this port, not run from flash.

What it means:
- **A second whole frame doesn't fit.** It would leave about 5 KB. The CRT screens must draw into
  the one frame and send only the windows that change (523 fps for a 44×44 block, above).
- **A big queue answer is tight.** The relay's line is read into the line buffer. Then its body
  string and the parsed queue need heap of their own, about 30 KB for a queue of 10. A 40 KB answer,
  which needed 90 KB on the bench, would not fit. The relay should send no more than hello's `max`,
  and the console asks for a few transactions at a time.
- More room would come from a smaller line buffer (24 KB still holds a queue of 10), or from
  freezing the modules into the MicroPython image so their bytecode runs from flash. Freezing means
  building our own MicroPython. It is not done.
- The line buffer is now 24 KB (`link.MAX_LINE`), so hello's `max` is 24 KB. With it and the CRT
  screens, the console had 88 KB free (88,384 bytes, same chip, 2026-11-04).
- Size isn't the only limit; order matters too. The key flow first loaded its modules, then the fonts,
  and a 3 KB font block no longer fit. Then the effects' 7.5 KB noise strip, taken at the first effect,
  didn't fit either. Both are now taken first, while the heap is whole (`main_rp.py`, `crt.reserve`).

## What this means for the console

**There's room for animation, if it is used on purpose.**
- **Page changes can slide.** With two buffers and DMA, 38 fps on SPI1 as it stands, 112 fps with
  PIO. A slide of 8 frames is about 200 ms on SPI1, about 70 ms on PIO.
- **Spinners and progress cost nothing.** 5% of the CPU at 30 fps. A small window is all that is
  sent.
- **A boot animation fits.** Frames could stream from the 3 MB filesystem.

**What is slow is the hash.** The console waits half a second on the Safe hash, before anything is
drawn about it. A spinner could run during it only by splitting Keccak into steps, or by running it
on the second core.

**A faster Keccak would change this more than any screen work.** Viper ran a plain loop 39 times
faster than Python. A Keccak written that way would be faster too, but it is the hash the key signs.
It would need every test vector to pass, on CPython and on MicroPython. It is not written.

**Keep the screen rules.** Red pages stay red and still. Hold-to-sign shows the hold and nothing
competing with it. Nothing moves on a page that is asking for a decision.

## What wasn't measured

- A Keccak in Viper, or with the second core.
- Overclocking. The RP2350 is rated for 150 MHz; we stayed there.
- Whether `machine.freq()` or a register poke could put SPI1 on the system clock. Either would also
  move UART1's clock, the link.
- The 9 ms PIO frame on the other four boards, or on the 100 BuyDisplay panels.
- How much power animation costs on the USB-C.
