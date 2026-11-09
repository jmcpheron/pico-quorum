# 5. Inside the console

*Draft script, 2026-11-09. Not recorded. Drawn on [Mono](../../hardware/mono/README.md), the board
planned for developer kits.*

| | |
|---|---|
| for | hardware and security people, and anyone who asks "why not just a hardware wallet?" |
| length | about 3:15 (490 words) |
| the one idea | The board has three zones: the cable, which is not trusted; the console, which rebuilds and shows the transaction; and the key, which signs. A transaction crosses all three, and each one checks or limits the one before. |

One picture carries the whole video: the board from above, with three zones that light up in turn.
The zones are amber for the cable, white for the console and green for the key: amber and green
are the brand's colours for waiting and signed ([BRAND.md](../BRAND.md)). The next video,
[When the hardware fails](hardware-failures.md), uses the same picture.

## Script

*Shows: Mono from above, turning slowly. Parts are named as they are said.*

This is Mono, a Picoquorum console. A bar of circuit board, four centimetres by nine. A screen.
Three buttons. A microcontroller. A secure element, the chip that holds the key. A USB-C socket at
the bottom. No Wi-Fi and no Bluetooth: the chip has no radio at all.

*Shows: the three zones light up one after another.*

Think of it as three zones.

**The cable**

*Shows: amber over the USB-C socket, the serial chip, and the computer at the far end.*

The first zone is everything on the far side of the cable: the computer, the internet, Safe's
service. The console trusts none of it.

The computer is a messenger. It fetches the transactions waiting in the Safe's queue and passes
them in. Later it carries a signature out. It holds no key and has no say in what gets signed.

*Shows: the socket's two data lines running to the serial chip and stopping there.*

And the wiring keeps it a messenger. The socket's data lines go to a serial chip and nowhere else.
The lines that could reset the microcontroller, or put it in its bootloader, are not connected. The
computer can send bytes. It can't send firmware.

**The console**

*Shows: white over the microcontroller, the flash, the screen and the buttons. A transaction's
fields arrive from the cable.*

The second zone is the microcontroller, its screen and its buttons. A transaction arrives as
fields: who it pays, how much, the call data, the nonce. And a hash that the service says is right.

*Shows: the fields go into a box marked "rebuild". A second hash comes out and is held up to the
first.*

The console doesn't take the hash. It rebuilds the hash from the fields, for the chain and the Safe
it was set up for. If the two differ, it refuses.

*Shows: the same fields flow up to the screen as plain words. A red page.*

The same fields go to the screen, decoded into plain language. Anything that changes who controls
the Safe is a red page. So what you read and what gets hashed come from the same place.

*Shows: a thumb pages through, then holds a button. The bar fills.*

You page through every screen. Then you hold Sign: two seconds, three if a page was red.

**The key**

*Shows: green over the secure element. The hash crosses two wires to it. A signature comes back.*

The third zone is one small chip. Only now does the hash cross to it. The key was made inside this
chip, and the chip has no command that reads it out. It signs, and the signature goes back the way
the transaction came: to the console, down the cable, to the queue.

**Two locks, two jobs**

*Shows: the back of the board, a row of nine pads.*

There is another way in. On the back are pads for a test jig, and through them a person holding the
board can write new firmware. That is how it gets its firmware in the first place.

*Shows: a padlock drawn over the white zone, dashed, labelled "not yet".*

Secure boot is the lock for that. The microcontroller can be set to run only firmware signed by one
key, for good. It is not turned on. It can't be undone, so it gets tried on a spare board first.

The two locks do different jobs. The cable's wiring stops the computer the console lives next to.
Secure boot would stop a person with the board in their hands from running their own code. Neither
covers the two wires between the console and the key.

*Shows: the console among other owners of a Safe.*

So the console is one owner, and the threshold is the real control. Keep owners on the Safe that
are not this console.

*Shows: picoquorum.app.*

Mono is open hardware and experimental. The board files, the firmware and the tests are at
picoquorum.app.

## Check before recording

This script goes out of date fastest. Read each of these on the day.

- **Mono is a design.** As of its README (2026-11-06) it is not ordered and nothing is built. Until
  a real board runs the console, every shot of it is a render, and the video says so on screen.
- **The firmware for the RP2350 boards.** As of 2026-11-09 console-rp runs a bench script, not the
  console's image ([hardware/console-rp/README.md](../../hardware/console-rp/README.md)), and Mono
  is meant to run console-rp's image unchanged. The screens exist today on a Pico 2 W, an ESP32-S3
  and the emulator. Record the screen shots on Mono once it runs them, or say which board each is.
- **The relay.** "The computer fetches the queue and passes it in" is the design for the boards with
  no radio. Check that the program that does it exists and what it is called before showing it.
- **Secure boot.** Not on, on any board ([SECURITY.md](../SECURITY.md), [STATUS.md](../STATUS.md);
  Mono's README lists it as open). If that has changed, rewrite "Two locks, two jobs". Raspberry
  Pi's RP2350-E24 erratum is about glitch attacks on the A2 stepping: check which stepping the
  boards carry before saying anything about how strong secure boot is.
- **"The computer can't send firmware"**: the CH343P's DTR and RTS go nowhere, and Mono has no RESET
  or BOOTSEL button. The generator checks the netlist
  ([hardware/mono/README.md](../../hardware/mono/README.md)). This is about Mono and console-rp. On
  a Pico 2 W or a bare ESP32-S3, whatever holds the USB port can reflash the board
  ([USB-LINK.md](../USB-LINK.md)). Don't show one in this video.
- **The jig's pads**: nine, on the back, with SWD, RUN, BOOT and the RP2350's own USB. As of
  2026-11-06 that USB path has not been seen working on console-rp; its first board was loaded over
  SWD. Say "write new firmware" without naming the way.
- **KEY 2**, the empty second key's site on the front, is in every shot of the board. The script
  doesn't mention it. If asked: nothing is fitted, and the firmware leaves it switched off.
- "If the two differ, it refuses", the hold times, the red pages: [SECURITY.md](../SECURITY.md);
  `test-vectors/run-console.mjs` checks the refusals.
- "The two wires between the console and the key": anyone on the chip's I2C bus can have it sign a
  digest, and on an ATECC608 that shows in its counter ([SECURITY.md](../SECURITY.md), "The
  counter").
- Sizes: 40 × 89.5 mm, a 1.14-inch screen, D0, D1 and D2, an RP2350A, an ATECC608C.

## For X

> A Picoquorum console in three zones.
>
> The cable: not trusted, and wired so it can't send firmware.
> The console: rebuilds the hash from the fields it shows you.
> The key: signs that hash, and can't be read out.
>
> And what isn't locked yet: picoquorum.app/learn

The cut: "The console" and "The key", about 70 seconds, the board lit zone by zone.
