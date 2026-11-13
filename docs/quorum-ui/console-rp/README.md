# The console on console-rp

Written by `node tools/board/shots_rp.mjs`: the real firmware on the emulator, 240 × 135, its three
buttons under the screen (the grey caps below it: D0 ■, D1 ●, D2 ▲, as on the case). The screens
are `quorum_ui_s`'s pages in the CRT look (`firmware/quorum_ui_crt.py`, `firmware/crt.py`). Each shot
is the page once its effect has played. The effects are on the board only:
- **tear** (FX1): something arrives or changes. Opening a transaction, a new one on home, a tab.
  Strong for a red page, short for a page turn.
- **lock** (FX3): worked out here and checked. The verify code, the key's code, Signed.
- None on a redraw, and none while Sign is held. Any press stops an effect and still counts.

The board is [hardware/console-rp](../../../hardware/console-rp/). Its way out is the relay on the
computer ([tools/relay](../../../tools/relay/README.md)). The key pages (`key-`, from `key-make` on)
are the owner making the key on the device: `firmware/keyflow.py`'s OwnKey on `firmware/keypick_rp.py`.

### home

Home: four tabs, the Queue first. The footer names what each button under the screen does here: D0 ■ the next tab, D1 ● down the list, D2 ▲ what the bar above it says. A tab arrives with a short tear.

![01-home](01-home.png)

### home owners

The Owners tab.

![02-home-owners](02-home-owners.png)

### home key

The Key tab: this key's picture, fingerprint and owner address.

![03-home-key](03-home-key.png)

### home device

The Device tab. No Wi-Fi row: console-rp has no radio; the computer on its USB-C relays.

![04-home-device](04-home-device.png)

### review head

A transaction opens with a tear. D0 ■ rejects with one press on any page, D1 ● is the next page, D2 ▲ shows the next one not yet seen.

![05-review-head](05-review-head.png)

### review item

What it does. A page turn is a short tear.

![06-review-item](06-review-item.png)

### review to

Who it goes to, in full, and its blockie.

![07-review-to](07-review-to.png)

### review approvals

Who has approved.

![08-review-approvals](08-review-approvals.png)

### review verify

The code to compare with the proposer. It was worked out here, so it locks in (FX3).

![09-review-verify](09-review-verify.png)

### review hash

The whole Safe transaction hash. Every page seen: D2 ▲ says Sign.

![10-review-hash](10-review-hash.png)

### hold

D2 ▲ held: its slot fills, 2 s. No effect while it fills. D0 ■ still rejects.

![11-hold](11-hold.png)

### red head

An unknown call: red. It arrives with a strong tear, then stays red and still. Sign takes 3 s.

![12-red-head](12-red-head.png)

### red calldata

Its function selector and calldata size, on a red page.

![13-red-calldata](13-red-calldata.png)

### refused

A hash the fields don't produce: refused, from the relay as from the service.

![14-refused](14-refused.png)

### result signed

Signed and posted: it locks in. D2 ▲ OK.

![15-result-signed](15-result-signed.png)

### result unsent

Signed but not sent (the relay stopped): D2 ▲ sends it again, D0 ■ goes back.

![16-result-unsent](16-result-unsent.png)

### device

Device: the chip, its slot and key, the pin, uses, memory.

![17-device](17-device.png)

### key code

Key: the app's set-up link as a QR code, over the footer's left. It locks in.

![18-key-code](18-key-code.png)

### key full

The owner address in full.

![19-key-full](19-key-full.png)

### key make

The key, at the first start: K0 has read the chip (no key in slot 0, counter 0 at 0) and that locks in. D2 ▲ Make: the chip makes a key inside itself. The picture is random bytes, not a key.

![20-key-make](20-key-make.png)

### key making

Make: the chip at work, a light running round its legs and hex flickering in its body (a timer moves that corner alone while GenKey runs). Nothing to press.

![21-key-making](21-key-making.png)

### key pick

A key: its owner address's blockie and two ends, landed after a shuffle, locking in. D0 ■ Replace makes another in its place: the chip holds one key, so the one passed over is gone. D1 ● Full; D2 ▲ Seal.

![22-key-pick](22-key-pick.png)

### key pick full

Full: the whole owner address.

![23-key-pick-full](23-key-pick-full.png)

### key keep

Seal this key?: red, it arrives torn. D2 ▲ Seal held 3 s seals the key and locks the chip, for good. D0 ■ goes back.

![24-key-keep](24-key-keep.png)

### key keep hold

Seal, held: its slot fills. Let go before 3 s and nothing happens.

![25-key-keep-hold](25-key-keep-hold.png)

### key keeping

Seal, let go of at 3 s: the chip at work (Sealing it), and the steps beside it, ticked off as each one passes. The test signatures passed; the seal is running.

![26-key-keeping](26-key-keeping.png)

### key locking

Then the chip's record and its data lock, under the same list: the seal passed, the data lock is running. Then the pin.

![27-key-locking](27-key-locking.png)

### key done

Sealed and pinned: C5's test signatures, the seal, the record, the data lock, then pin.json. It locks in. D2 ▲ restarts into the console, on that pin.

![28-key-done](28-key-done.png)

### key make before

A chip with a key in slot 0 already (made at an earlier start, or written in at the bench): K0 says so, and Make replaces it before anything else.

![29-key-make-before](29-key-make-before.png)

### key finish

A restart between the seal and the data lock: keyflow.json says this console sealed it, so Finish, held 3 s.

![30-key-finish](30-key-finish.png)

### key elsewhere

The same chip with no keyflow.json: sealed elsewhere. Nothing here locks or pins it.

![31-key-elsewhere](31-key-elsewhere.png)

### key not prepared

A factory chip: never prepared at the bench. Nothing here can change it.

![32-key-not-prepared](32-key-not-prepared.png)
