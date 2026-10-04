# Troubleshooting

`tools/fw verify` answers most questions: the image, the `secrets.py` settings (without
secrets), the console's state, and each Safe's status. `tools/fw logs` copies the board's
`log.txt` and `error.log`.

## Display and firmware updates

The Build 1 2.8-inch display uses its full **320 × 240** landscape resolution. Set
`BOARD = "build1"` and `SCREEN = "2.8"` in the board's `secrets.py`. The console draws in
30-row strips, using 19,200 bytes of framebuffer memory without reducing resolution or colour depth.

Use `tools/fw push console` for the production image. It backs up the board and checks every
copied file by hash. Avoid interrupting it during the restart; boot needs time before USB
inspection can safely resume.

For recovery, hold the knob pressed while plugging in Build 1 (B on the Waveshare board),
until the Pico's onboard LED lights. Maintenance skips display and Wi-Fi initialization;
a blank display is expected. USB remains available even if the display cannot initialize.
The updater's `maint` file selects the same mode automatically. A failed update keeps that
file so another push can repair the image.

## Stop screens

These screens sign nothing.

| Screen | Meaning | What to do |
|---|---|---|
| **No Safe** | The board's `secrets.py` has no `QUORUM_SAFES` | [SETUP step 6](SETUP.md#6-point-the-console-at-your-safes) |
| **Not pinned** | No `QUORUM_EXPECT` | `tools/fw pin` |
| **Not the pinned key** / **Not a pinned chip** | The chip, slot or key isn't the one pinned. It shows what it found next to what is pinned. | The right chip back in; A checks again. A new chip gets `tools/fw pin` (and is a new owner on each Safe). |
| **No chip** | Nothing answers on I2C | Check the chip's wiring; A checks again |
| **Stopped** | 20 failures in a row | B restarts. `tools/fw logs` gets `error.log`. |

## Home says Offline, or `1 offline`

X (Device) shows the last error; with several Safes it names the Safe.

- **`no wifi`**: the console retries every 30 s, through every saved network in turn. To
  change the network, hold Y while plugging in: that opens Wi-Fi setup
  ([SETUP.md](SETUP.md#wi-fi-without-secretspy-the-setup-screen)). A network in `secrets.py`
  comes from `WIFI_SSID` and `WIFI_PASS`.
- **`HTTP 401` / `403`**: the API key is wrong or expired. Fix `QUORUM_API_KEY`.
- **`HTTP 404`**: the service doesn't know this Safe on that chain. Check the address and the
  chainId in `QUORUM_SAFES`, and that the Safe was made on that chain.
- **`HTTP 429`**: over quota. Raise `QUORUM_POLL_S`, or add an API key.
- **`no service for chain N`**: the console has no service for that chain. See
  [NETWORKS.md](NETWORKS.md#adding-a-chain).
- **`bad Safe info`**: the service's answer failed the console's checks (another Safe, a
  threshold larger than the owner list). The console won't show or sign anything for that Safe.
- **A certificate error**: the console only trusts the roots built into the image. It also
  refuses a clock set earlier than the build, so wait for NTP.

## "Can't sign: …" on a transaction

| Message | Why |
|---|---|
| `this key is not an owner` | The Safe's owners don't include this console's owner address. Add it in the web app ([SETUP step 5](SETUP.md#5-a-safe-on-each-chain)). |
| `already signed by you` | The service already has this key's signature. |
| `old Safe v…` | The Safe is older than 1.3.0; the console only hashes 1.3.0 and later. |
| `key doesn't match the pin` | The chip changed while the console was running. |
| `refused` | See the refused page: the console won't sign this one. |

## The service didn't take the signature (**Not sent**)

The signature is kept on the board. A on the result screen tries again, and the next boot sends
it. The usual cause is that **the key's signer isn't deployed on that chain**: the service checks
signatures through it. Run `tools/quorum live enroll --chain C`.

## The Safe web app fails with GS021

With a threshold of 2 or more, the Safe web app drops the console's signature data when it
executes, and the Safe reverts with GS021. Execute it in [the PicoQuorum app](../app/) instead,
which lays the signatures out right: open the Safe, then **Execute with wallet**. Proposing and
confirming work there too. From the terminal it's:

```sh
tools/quorum live exec --chain base <nonce>
```

The upstream report is in [docs/upstream/](../upstream/).

## Rejected on the console, still in the queue

Y only hides a transaction on this console. See [USING.md](USING.md#rejecting).

## "Key used N× outside this console"

The chip's use count went up while the console wasn't watching. On a sealed chip, reading the
public key over USB (`tools/fw verify --baseline`, `tools/fw pin`) counts as a use, so a count you
caused is harmless. One you didn't cause means someone had the board or the chip's bus: compare
the Safe's confirmations with what you signed.
