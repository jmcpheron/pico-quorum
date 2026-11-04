# The console on the Feather ESP32-S3 Reverse TFT

Written by `node tools/board/shots_feather.mjs`: the real firmware on the emulator, 240 × 135, three
buttons down the left edge (the grey dots: D0, D1, D2). The rail beside them says what each does here.

- **D0**: on home, the next tab (Queue, Owners, Key, Device); Reject on a review (one press, any page, even while Sign is held); Back anywhere else.
- **D1**: next page or row, round from the last to the first; held 1 s, the one before. On a review's first page, held: out without rejecting.
- **D2**: what the bar along the bottom says; on a review, the next page not yet seen, then Sign: held 2 s, 3 s when a page is red.

Each button works the strip level with it: D0 the tabs along the top, D1 the list, D2 the bar. The rail's icons:
→ next tab, ‹ back, ⌄ next, ● open or OK, ✕ reject, ✓ sign.

Every address on a review, and every owner, has its blockie: the picture Safe{Wallet} and Etherscan draw for it.
The Key tab shows the app's set-up link for the key as a QR code (docs/ONBOARDING.md).

### home

Home: four tabs, the Queue first. D0 moves to the next tab, D1 down the list and round (held: up), D2 does what the bar along the bottom says.

![01-home](01-home.png)

### home owners

The Owners tab: who can approve, each with a blockie. D2 shows the one in focus in full.

![02-home-owners](02-home-owners.png)

### owner

An owner in full, and its blockie. D0 back to the tab.

![03-owner](03-owner.png)

### home key

The Key tab: this key's fingerprint and picture, and whether the Safe lists it. D2 shows its code.

![04-home-key](04-home-key.png)

### home device

The Device tab: Chip, Wi-Fi, Practice and About, one row each.

![05-home-device](05-home-device.png)

### review head

A review opens on what it does. Rail: Reject (one press, any page), Next, and "See 5": D2 shows the next page not yet seen.

![06-review-head](06-review-head.png)

### review item

The send: the amount, big.

![07-review-item](07-review-item.png)

### review to

Who it goes to, the whole address in four-character chunks, and its blockie.

![08-review-to](08-review-to.png)

### review approvals

Who has approved, each owner's blockie beside it, and what this key's signature would make it.

![09-review-approvals](09-review-approvals.png)

### review verify

The code to compare with the proposer: the hash's last 8, and its blockie.

![10-review-verify](10-review-verify.png)

### review hash

The whole Safe transaction hash, worked out here. Every page seen: D2 says Sign.

![11-review-hash](11-review-hash.png)

### hold

D2 held: the rail fills from the bottom. 2 s to sign; let go early and nothing is signed.

![12-hold](12-hold.png)

### red head

An unknown call: red. Sign takes a 3 s hold.

![13-red-head](13-red-head.png)

### red calldata

Its function selector and calldata size, on a red page.

![14-red-calldata](14-red-calldata.png)

### red digest

The calldata's digest to compare.

![15-red-digest](15-red-digest.png)

### red hold

Holding Sign on a red transaction: the rail fills in red, 3 s.

![16-red-hold](16-red-hold.png)

### refused

A hash the fields don't produce: refused. Sign stays grey; D0 rejects.

![17-refused](17-refused.png)

### see every page

D2 before every page is seen: it shows the next one and says how many are left.

![18-see-every-page](18-see-every-page.png)

### result signed

Signed and posted. D2: OK.

![19-result-signed](19-result-signed.png)

### result unsent

Signed but not sent: D2 sends it again, D0 goes back.

![20-result-unsent](20-result-unsent.png)

### device

Device tab, About: the chip, its slot and key, the pin, uses, memory. D0 back to the tab.

![21-device](21-device.png)

### chip

The chip's own pages. D1 pages, D0 back.

![22-chip](22-chip.png)

### nochip

No chip on the bus: D2 checks again.

![23-nochip](23-nochip.png)

### pinfail

A chip that isn't pinned: nothing will be signed until tools/fw pin adds it. D2 checks again.

![24-pinfail](24-pinfail.png)

### key code

Key: the app's set-up link (#/k/<compressed key>) as a QR code, beside the owner address's start, end and picture, to compare with the page the phone opens. A signer, not a wallet. D1 shows the address in full, D0 goes back.

![25-key-code](25-key-code.png)

### key full

The owner address in full, the key's fingerprint and use count.

![26-key-full](26-key-full.png)

### home not owner

A Safe that doesn't list this key yet: Not an owner yet, and where its code is: the Key tab.

![27-home-not-owner](27-home-not-owner.png)

### ready

No Safe set yet, on a console being set up: the key is ready, D2 shows its code.

![28-ready](28-ready.png)

### token amount

A token: its amount, the token named from the console's own list, and the token contract's blockie.

![29-token-amount](29-token-amount.png)

### token to

Every address page has its blockie beside the short last line: the picture Safe{Wallet} and Etherscan draw for it.

![30-token-to](30-token-to.png)

### swap replaces

Replacing an owner, a red page: the owner going out, and its blockie...

![31-swap-replaces](31-swap-replaces.png)

### swap new owner

...and the one coming in, to compare with the owners list in the Safe app.

![32-swap-new-owner](32-swap-new-owner.png)

### batch to

A batch: each call has its own pages, and each address its own blockie.

![33-batch-to](33-batch-to.png)
