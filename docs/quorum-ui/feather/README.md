# The console on the Feather ESP32-S3 Reverse TFT

Written by `node tools/board/shots_feather.mjs`: the real firmware on the emulator, 240 × 135, three
buttons down the left edge (the grey dots: D0, D1, D2). The rail beside them says what each does here.

- **D0**: Reject on a review (one press, any page, even while Sign is held); Back anywhere else.
- **D1**: next page or row; held 1 s, the one before. On a review's first page, held: out without rejecting.
- **D2**: open; on a review, the next page not yet seen, then Sign: held 2 s, 3 s when a page is red.

Key shows the key's owner address as a QR code (docs/ONBOARDING.md). The status home and the claim on three buttons come next.

### home

Home: the queue. D1 moves down it, D2 opens the one in focus. Past the list, D1 reaches Owners and Device.

![01-home](01-home.png)

### home device

D1 past the last row: the Owners and Device choices. D0 goes back onto the list.

![02-home-device](02-home-device.png)

### review head

A review opens on what it does. Rail: Reject (one press, any page), Next, and "See 5": D2 shows the next page not yet seen.

![03-review-head](03-review-head.png)

### review item

The send: the amount, big.

![04-review-item](04-review-item.png)

### review to

Who it goes to, and the whole address in four-character chunks.

![05-review-to](05-review-to.png)

### review approvals

Who has approved, and what this key's signature would make it.

![06-review-approvals](06-review-approvals.png)

### review verify

The code to compare with the proposer: the hash's last 8, and its blockie.

![07-review-verify](07-review-verify.png)

### review hash

The whole Safe transaction hash, worked out here. Every page seen: D2 says Sign.

![08-review-hash](08-review-hash.png)

### hold

D2 held: the rail fills from the bottom. 2 s to sign; let go early and nothing is signed.

![09-hold](09-hold.png)

### red head

An unknown call: red. Sign takes a 3 s hold.

![10-red-head](10-red-head.png)

### red calldata

Its function selector and calldata size, on a red page.

![11-red-calldata](11-red-calldata.png)

### red digest

The calldata's digest to compare.

![12-red-digest](12-red-digest.png)

### red hold

Holding Sign on a red transaction: the rail fills in red, 3 s.

![13-red-hold](13-red-hold.png)

### refused

A hash the fields don't produce: refused. Sign stays grey; D0 rejects.

![14-refused](14-refused.png)

### see every page

D2 before every page is seen: it shows the next one and says how many are left.

![15-see-every-page](15-see-every-page.png)

### result signed

Signed and posted. D2: OK.

![16-result-signed](16-result-signed.png)

### result unsent

Signed but not sent: D2 sends it again, D0 goes back.

![17-result-unsent](17-result-unsent.png)

### owners

Owners: who can approve. D0 back.

![18-owners](18-owners.png)

### device

Device: the chip, its slot and key, the pin, uses, memory. D1 moves along Chip, Wi-Fi, Back; D2 opens.

![19-device](19-device.png)

### chip

The chip's own pages. D1 pages, D0 back.

![20-chip](20-chip.png)

### nochip

No chip on the bus: D2 checks again.

![21-nochip](21-nochip.png)

### pinfail

A chip that isn't pinned: nothing will be signed until tools/fw pin adds it. D2 checks again.

![22-pinfail](22-pinfail.png)

### home key

Past Owners and Device, D1 reaches Key: this key's QR code.

![23-home-key](23-home-key.png)

### key code

Key: the owner address as a QR code, beside its start, end and picture. A signer, not a wallet. D1 shows it in full, D0 goes back.

![24-key-code](24-key-code.png)

### key full

The owner address in full, the key's fingerprint and use count.

![25-key-full](25-key-full.png)

### home not owner

A Safe that doesn't list this key yet: Not an owner yet, and where its code is.

![26-home-not-owner](26-home-not-owner.png)

### ready

No Safe set yet, on a console being set up: the key is ready, D2 shows its code.

![27-ready](27-ready.png)
