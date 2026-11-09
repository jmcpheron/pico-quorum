# 4. Inside the console

*Draft script, 2026-11-09. Not recorded.*

| | |
|---|---|
| for | hardware and security people, and anyone who asks "why not just a hardware wallet?" |
| length | about 3:00 (460 words) |
| the one idea | The console is not a dumb signer: it rebuilds the transaction and shows it on a stack of its own. And it can't be a wallet: all it can do is sign the hash it worked out. |

This is the one for detail. It names parts and files. It also says plainly what is not done yet.

## Script

*Shows: the board from above, parts labelled as they are named.*

This is a Picoquorum console. A microcontroller, a small screen, three buttons, and a secure
element: the chip that holds the key. That is the whole computer.

**Not a dumb signer**

*Shows: a hash on a small screen, "Sign?" under it.*

A dumb signer is handed a hash and asked to sign it. You see 64 characters, or nothing, and you
trust the laptop that sent them.

*Shows: the fields of a Safe transaction flowing into the console, and a hash coming out inside it.*

The console never signs a hash it is handed. It takes the transaction's fields: who it pays, how
much, the call data, the nonce. It rebuilds the Safe transaction hash from those fields, for the
chain and the Safe it was set up for. If the service's hash is different, it refuses.

*Shows: the approve page, then a red owner-change page.*

The same fields go on the screen, decoded into plain language. Anything that changes who controls
the Safe, or can't be undone, is a red page.

*Shows: paging through, then the hold bar.*

You page through every screen before Sign is allowed. Then you hold it: two seconds, three if a
page was red. Reject is one press.

**Not a wallet either**

*Shows: `quorum.sign_it` in the source.*

One function in the image asks the chip to sign, and it signs that one hash. There is no command to
sign a message someone sends. Nothing in the image can make a key, replace one or lock the chip.

*Shows: the chip, a key drawn inside it, arrows bouncing off.*

The key is made inside the secure element. The chip has no command that reads a private key out.
There is no seed phrase and no backup.

**An independent stack**

*Shows: a laptop and the console side by side, each with its own column: hardware, code, screen, person.*

Why bother, when a laptop can show the same thing? Because a second check is only worth something
if it fails differently from the first. Different hardware. Different code: about eleven thousand
lines of MicroPython you can read. A different screen. A fake web page has to fool the laptop and
this.

**The cable**

*Shows: console-rp's USB-C, a line to the serial chip, a gap, then the microcontroller.*

On the console-rp board, the USB-C port doesn't reach the microcontroller's USB at all. It goes to
a serial chip. The computer passes the Safe's queue in and carries signatures out. The lines that
could reset the board or put it in its bootloader are not connected.

So the computer it is plugged into can't write new firmware. That takes a header that isn't fitted,
and the board in someone's hands.

**What isn't done**

*Shows: a checklist, with these lines unticked.*

Secure boot is not on. The RP2350 can be set to run only signed firmware, and its debug port can be
locked. Both are burned in for good, so they get tried on a spare board first. Until then, someone
holding the board can write firmware to it, and new firmware could make the chip sign anything.

That costs one owner's signature, never the Safe. Which is the point of the last line.

*Shows: the console among other owners.*

The console is one owner. The threshold is the real control. Always keep owners on the Safe that
are not this console.

*Shows: picoquorum.app, the source link.*

It is open source and experimental. The firmware, the board files and the tests are all at
picoquorum.app.

## Check before recording

This script goes out of date fastest. Read each of these on the day.

- **Secure boot.** Not done on any board as of 2026-11-09 ([SECURITY.md](../SECURITY.md),
  [STATUS.md](../STATUS.md)). If it has been turned on since, rewrite "What isn't done". Don't
  record the old lines.
- **console-rp runs a bench script, not the console's firmware**, as of 2026-11-09
  ([hardware/console-rp/README.md](../../hardware/console-rp/README.md)). The console's screens
  today are on a Pico 2 W, an ESP32-S3 and the emulator. Record this video after the firmware is on
  console-rp, or say on screen which board each shot is.
- **"The cable" is about console-rp** (and console-usb). On a Pico 2 W or a bare ESP32-S3, whatever
  holds the USB port can reflash the board ([USB-LINK.md](../USB-LINK.md), "Anything holding the USB
  port"). Don't show a Pico during this part.
- "Three buttons", "1.14-inch screen", "no radio": console-rp. The Pico 2 W build has a 1.3-inch
  screen, a joystick and four buttons, and Wi-Fi.
- "If the service's hash is different, it refuses", the hold times, the red pages:
  [SECURITY.md](../SECURITY.md), and `test-vectors/run-console.mjs` checks the refusals.
- "One function": `quorum.sign_it`, checked by `test-vectors/manifest.mjs`.
- "About eleven thousand lines": the README's table for the console page. Count again.
- "Could make the chip sign anything": anyone with the chip's bus can have it sign a digest. It
  shows in the chip's counter ([SECURITY.md](../SECURITY.md), "The counter").

## For X

> "Why not just a hardware wallet?"
>
> A Picoquorum console never signs a hash it's handed. It rebuilds the Safe transaction hash from
> the fields on its own screen, and its key signs only that. Three minutes on how, and on what isn't
> done yet:
>
> picoquorum.app/learn

The cut: "Not a dumb signer", about 60 seconds. It stands alone.
