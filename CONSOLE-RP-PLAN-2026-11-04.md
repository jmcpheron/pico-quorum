# The console-rp plan (2026-11-04)

Where Picoquorum stands the night the first console-rp came up, why this board is the one to build
on, and a plan for the next two weeks and after: the firmware, a batch of 20, the brand's root key,
and selling the first boards. It's a plan to argue with, not a decision record. The decisions it
needs are marked **Decide**.

## In one paragraph

Picoquorum is a small cosigner for Safe multisigs. It is an ATECC608 secure chip that holds one
owner's key and can't give it up, and a screen and three buttons on which the owner checks every
transaction before it signs. It doesn't trust the computer, the app or Safe's service for what it
signs: it works out the transaction's hash from the fields it shows. The console-rp is the version to
build on. It has a Raspberry Pi RP2350 with no radio, a USB-C that reaches only a serial chip, and
parts that cost about $10–12 a board at a hundred. It's the main version. The Pico 2 W boards, with
Wi-Fi, are the premium version: they keep working, but the work goes here.

## Where we are

**The boards on hand:**
- **5 console-rp**, rev A, assembled by JLCPCB. Ordered 2026-10-29 for $164.28 (about $33 a board),
  received 2026-11-04: six days door to door
  ([the order](buildlog/2026-10-29-console-rp-order.md)).
- **About 5 of each earlier build** on the castellated Pico 2 W, with its radio: the premium version.
- **100 panels** (ER-TFT1.14-2) on order from BuyDisplay since 2026-11-03
  ([the order](buildlog/2026-11-03-panels-order.md)). They were bought for console-s3's J2. Check one
  in a console-rp's ZIF before counting on them here.

**The first board, tonight.** Every part answered
([hardware/console-rp/bench/BRINGUP.md](hardware/console-rp/bench/BRINGUP.md) has how):
- the RP2350, its crystal and its flash;
- the screen, edge to edge, colours right, the right way up;
- D0, D1, D2, the LED and the backlight;
- the key, a fresh ATECC608 with both zones open;
- the link: USB-C, the CH343P serial chip and UART1, both ways.

Two things are still open:
- **J3's USB pins:** the Mac never saw the chip through them.
- **A 1.4 V reading** on the chip's core supply, which should be 1.1 V. The chip runs fine, so it may
  just be the meter. Measure again.

**How it was loaded.** Not over the USB-C. That can't load a board, by design (below). A spare
Pico 2 W became a debug probe on J3's CLK, DIO and GND, and `probe-rs` wrote MicroPython and our
files into the flash, about 20 seconds a board. The screen was black at first. That was a bug of
ours: SPI1's default data-in pin is the screen's DC line. It's fixed in the bring-up script.

**What's in the repo for it:**
- the board and its fab files (`hardware/console-rp/`), and the rev B concept with a flat panel
  (`console-rp-b/`, on branch `claude/console-rp-concept`);
- the bring-up script and the SWD loader (`hardware/console-rp/bench/`);
- everything the other consoles already have: the transaction review and its hash, the key
  ceremony, pick-your-key, the app, the emulator, signed releases and the project Safe's approval.

**What isn't:** a console-rp profile in the firmware, and the relay (next section).

## Why no radio

- **Cost.** The RP2350A is about $1.13 at a hundred. The radio module and its antenna cost more than
  the rest of the logic.
- **Licensing.** A board with a radio needs radio certification, or a pre-certified module and its
  rules. A board with no radio is only an unintentional radiator (a footnote below).
- **Less to attack.** No Wi-Fi password on the device, no network stack, no TLS on a small heap
  (that was most of our memory trouble on the Pico 2 W), and nothing to reach over the air.
- **One cable.** The person plugs it in. There's no Wi-Fi to set up on a 240×135 screen.

The price is that the console can't fetch Safe's queue by itself. The computer has to pass it on.

## Talking to Safe without a radio: the relay

### How it would work

The computer (the app's Device page in Chrome, which already talks to consoles over Web Serial, or a
small command-line tool) does the network part:
1. It fetches the queue from Safe's service, and the Safe's owners, threshold and nonce from the
   chain.
2. It sends each transaction's fields over the USB-C to the console.
3. The console works out the Safe transaction hash itself, from those fields and the Safe's address
   and chain. It draws every page: who, what, how much, any red flags. The person reads it and holds
   Sign, or presses Reject.
4. Only then does the chip sign the hash the console worked out. The signature goes back over the
   USB-C, and the app gives it to Safe's service.

### Why the isolation makes this safe enough to try

- **The USB-C reaches one thing: the CH343P serial chip.** Its DTR and RTS go nowhere. The computer
  can't reset the RP2350, put it into its loader, reach MicroPython's prompt, or change its
  firmware. New firmware needs J3 and the board in someone's hands.
- **What crosses the cable is data, never code.** The console reads a few kinds of JSON line and
  nothing else. A request it doesn't know is dropped.
- **The console never signs a hash it's handed.** It signs only the hash it worked out from what's
  on its screen. If the computer lies about the fields, the lie is what the person reads, and it's
  also exactly what would be signed. If the computer sends one thing and the page shows another,
  the signature doesn't match, and Safe rejects it.
- **The worst a hostile computer can do** is ask for signatures the person refuses, or send nothing.

### What gets weaker, said plainly

Today the Wi-Fi consoles trust Safe's service, over HTTPS, for context: the Safe's owners, its
threshold, its current nonce, and names for tokens and contracts. Through the relay, that context
comes through the computer. It can't change what gets signed, but it can mislead the person:
- **A stale or future nonce.** The transaction is still the one shown, but it may run later than
  the person expects.
- **A wrong owner list or threshold** on the status screen.
- **A friendly name for a contract** that isn't what it says.

The answers:
- Decode the contracts the console knows (Safe's own calls, tokens it pins) from its firmware, not
  from the computer.
- Mark anything the console didn't check itself as coming from the computer.
- Keep red pages red whatever the computer says.

### What it changes in the rules

`AGENTS.md` rule 1 says the USB link never signs. The relay needs that rule rewritten, along these
lines:

> The link may carry a transaction in and a signature out. The console signs only the hash it worked
> out from the fields on its screen, after every page is seen and Sign is held. It never signs a
> hash or digest the link hands it.

That keeps what matters (`quorum.sign_it`, the hash rebuilt on the device, Sign held, Reject one
press) and lets the cable carry the result. `docs/USB-LINK.md` and the test that checks the signing
site (`test-vectors/manifest.mjs`) would change with it.

**Decide:** the relay, and this rewording. The console-rp can't sign anything until it's built.

## The firmware still to write

In this order, all on board #1, each checked in the emulator first:
1. **A `console-rp` profile** in `firmware/board.py`: its pins (all on the Pico's defaults but the
   buttons), the screen as tonight (MADCTL 0x60, 40/53), D0 D1 D2 in a row under the screen. The
   footer layout is the one drawn for the QT Py, whose buttons also sit under the screen (PR #91).
2. **The link on UART1** instead of USB stdin, so `usblink.py` speaks over the CH343P. MicroPython's
   own USB (J3 only) keeps the REPL for the bench.
3. **The relay**, in the app's Device page and on the console (needs the decision above).
4. **Pick-your-key on this board:** the same screens as the PicoquorumKey, on the footer.
5. **A `console-rp` image** in `firmware/manifest.json`, its release fingerprint, and the emulator's
   board for screenshots.
6. **The first signature:** a Base Sepolia transaction, start to finish, the console-rp as one owner.

## The five boards

| board | job |
|---|---|
| **#1** | The bench board, the one up now. Solder a 1×8 header into J3. All the firmware work happens here. |
| **#2** | Kept for permanent experiments: secure boot and locking SWD (below). Expect to spend it. |
| **#3** | A second development board on a blank key, for the key flows. Possibly key 0000 later. |
| **#4, #5** | The first boards in other hands, once #1 has signed a testnet transaction end to end. |

## The next two weeks

A fast plan. Every step can slip without breaking the next one.

| when | what |
|---|---|
| **Tonight** | Use board #1. Press everything, leave it on, see what bothers you. |
| **Days 1–4** | The console-rp profile, the link on UART1 and (with a yes) the relay, toward the first testnet signature. |
| **Days 2–5** | The design refresh: the buttons where you want them, the look. Rev B's flat panel is a starting point. |
| **Day 5–6** | Check the refresh: `tools/keypcb jlc`, DRC, the 3D fit, a printed 1:1 paper check of the buttons and the panel. Quote 20. |
| **Day 6–7** | **Order 20** if the testnet signature works on rev A. |
| **About day 13** | The 20 arrive (the five took six days). Bring one up with `swdload.py`, then all 20 on the jig. |
| **Day 14 on** | The first few go out, to people chosen by hand. |

### Moving the buttons, and the risk in it

The buttons are the safest thing to move: three switches and their lines to the RP2350, and
the silkscreen. The risks are elsewhere, so keep them where they are:
- **Keep, as tonight:**
  - the RP2350's corner, copied from Raspberry Pi: the crystal, the core regulator and L1, the flash;
  - the CH343P and the USB-C;
  - the key chip and its bus;
  - every GPIO, so tonight's firmware runs unchanged.
- **Change if wanted:** the buttons, the outline, the silkscreen, the panel's position, J3.
- **Add while the board is open:**
  - J3 as pads for a pogo jig, or a Tag-Connect footprint, with RESET on it;
  - J3's USB checked (or left off, if SWD is the way in for good);
  - the core supply's reading understood first.

Twenty boards is the right bet. If the refresh breaks something it costs one small order, and the
five rev A boards still work.

### What 20 might cost

Quote it. At five it was about $33 a board. The estimate for a hundred is about $11.50 a board,
before the panel ([the order's estimate](buildlog/2026-10-29-console-rp-order.md)). Twenty will sit
in between: JLCPCB's setup and stencil fees are spread over fewer boards. Then add a panel, a
case or bag, and postage.

## Loading boards in numbers

The USB-C won't load a board, so every way in is through J3, or before the flash is placed.
[BRINGUP.md](hardware/console-rp/bench/BRINGUP.md#loading-boards-in-numbers) has the detail. In
short:
1. **A pogo-pin jig on J3** (CLK, DIO, GND) with a debug probe and `swdload.py`. About 20 seconds a
   board. The same jig holds the USB-C, runs the test screen, and logs each board's key serial from
   the lines it sends. A Raspberry Pi Debug Probe is about $12; a Pico works too. Good for 20, and
   for a few hundred.
2. **The flash programmed before assembly.** Ask JLCPCB whether they'll do it for the W25Q128. It's
   fastest at volume, but only once the image is final.
3. **USB through J3**, Raspberry Pi's usual way, once J3's USB is proven.

Whichever way, loading is not the key ceremony. Each key chip arrives open, and nothing in loading
writes to it.

## The RP2350's own locks

The RP2350 can be set to run only firmware signed with our key (secure boot), and its SWD port can be
locked. Like the key chip's locks, these are one-time and can't be undone.
- **Secure boot covers the MicroPython image, not the `.py` files in its filesystem.** For it to
  mean anything, the console's code has to be built into our own MicroPython (frozen) and that image
  signed. That's a MicroPython build of our own, pinned like everything else.
- **Locking SWD after loading** stops someone with the board from rewriting its flash. It also stops
  us from fixing it on a jig, so updates would go through the signed loader.
- **Why it matters:** the key never leaves the chip either way. The attack these stop is someone with
  the board for a few minutes loading firmware that shows one thing and has the chip sign another.

**Decide** after trying both on board #2. The first 20 can ship without them, labelled as
development boards.

## The brand's root key

The design is in [docs/BRANDED-KEYS.md](docs/BRANDED-KEYS.md) and
[docs/ATTESTED-KEYS.md](docs/ATTESTED-KEYS.md):
- the bench writes Picoquorum's settings and a signed brand record into each chip, and locks them;
- the owner's console makes the key inside the chip, so nobody chose it, not even the bench;
- an attestation key in the chip lets anyone check the key was made there.

The record is signed by **key 0000**, the brand's root. It doesn't exist yet. The options:
- **A console-rp as key 0000.** One board, its chip made into the root, kept offline. It's hardware we
  have. But the chips are soldered, so the brand step can't swap two chips on one bus. The record
  would pass between two boards through the computer. That isn't designed yet.
- **The project Safe above key 0000.** The Safe publishes key 0000's address in a registry, and can
  replace it. That makes a lost or leaked key 0000 a bad day, not the end. Releases already work this
  way (`docs/GOVERNANCE.md`).
- **Later, at volume: Microchip's own provisioning.** Microchip provisions ATECC608s at the factory
  under its secure-provisioning programmes. Chips could arrive carrying our brand certificates. The
  owner would still make their own key.

If secure boot happens, there are two roots: the key that signs firmware, and key 0000. Both can sit
under the project Safe.

**For the first 20:** ship them unbranded. Each owner makes their own key on the device
(pick-your-key), as the PicoquorumKey does tonight. Branding can come with the next batch.

## Selling the first boards

Small and by hand at first. The board says EXPERIMENTAL HARDWARE COSIGNER on its face, and the
pitch matches: a development board for people who run multisigs, a cosigner alongside their other
owners, never the only one.

### Two doors

**The Ethereum door (the one to steer people to).**
- **Pay in ETH or USDC**, to an address published as **buy.picoquorum.eth**. That's a subname of
  picoquorum.eth, which we own (`docs/STATUS.md`); `.ens` isn't a name ending. Point it at the
  project Safe, or at a sales address the Safe controls.
- **The cart first.** A page on the site picks the board, the quantity and the US state, and shows
  the price. It makes an order code, and the person pays with the code in the transaction (or one
  payment per code). The site checks the payment on chain itself; the app already reads chains this
  way.
- **The address never touches the chain.** Not even encrypted: a chain is forever, and a key that
  leaks in five years would open every old order. The person sends their address off chain, by
  email or a form, tagged with the order code. It's used to print the label and deleted once it
  ships.
- **The promise, said plainly:** "We don't keep your address after it ships, and there's no
  database of orders to leak. You get no support beyond the docs." The carrier and the label service
  will still have the address. Say that too.
- **US only for now.** Simpler for tax and export (footnotes).

**The Stripe door (the easy one).**
- Stripe Checkout: a card, an address form, done. Stripe keeps the order and the address. That's the
  trade, and it's fine to say so: "the easy way, and Stripe keeps a record."
- Stripe also takes stablecoins for some US businesses. Check whether that's worth a third button.

### What to have ready before taking money

- **A page per board:** what it is, what it isn't (not audited, experimental), what's in the box, how
  setup goes, US only.
- **Terms:** sold as a development board, as is, no warranty past dead-on-arrival. Short, from a
  lawyer (below).
- **A label service and a bag:** the board, a card with the setup link (`#/k`), and the screen
  protected.
- **The bring-up jig**, so every board is tested before it ships, with its key serial logged
  against nothing but the order code.
- **Where the money goes:** the project Safe, or an account it feeds (`docs/ATTESTED-KEYS.md` has
  a treasury idea).

## Footnotes: business basics, to check, not researched

1. **A business entity.** An LLC keeps the project's risk off your personal assets. An hour with a
   lawyer to set it up and read the terms is worth it before the first sale.
2. **Liability for a security device.** The terms should say plainly: experimental, not audited, not
   to be the only owner of anything that matters. Ask the lawyer.
3. **Sales tax.** Selling from California usually means a seller's permit and sales tax on
   California orders. Stripe can add tax. Check the ETH door's side too.
4. **Crypto received is income** at its value the day it arrives. Keep a simple record of each
   payment: date, amount, the dollar value. Not the buyer's address.
5. **FCC.** A board with no radio is still a digital device under Part 15. Small runs of development
   kits sold to developers have their own rules. Ask before selling to the public at large.
6. **Export.** Devices with cryptography have export rules. US only avoids them for now; check
   before shipping abroad.
7. **The name.** `TRADEMARK.md` has where the name stands. Check before a bigger launch.
8. **Insurance.** Ask the lawyer whether a small product-liability policy makes sense once boards
   are in other people's hands.
