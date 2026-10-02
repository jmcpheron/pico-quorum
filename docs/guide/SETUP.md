# Setting up a console

From a board and a chip to a console that signs for your Safes. These steps use this repo's tools
on a Mac, with the board on USB. Each tool reads the board first and asks for a typed `yes`
before it writes.

**You need:**
- The console: a Pico 2 W, a Waveshare Pico-LCD-1.3 and an ATECC608
  ([build guide](../picowallet.md), [parts](../../hardware/bom/README.md)).
- A browser wallet (MetaMask, Rabby…) with a little ETH on each chain you'll use. It is the
  Safe's other owner, and it pays for the one-time signer deploy on each chain.
- A Safe API key from [developer.safe.global](https://developer.safe.global). It's free, and it
  raises the service's quota from 5,000 to 50,000 requests a month.

## 1. The key in the chip

A fresh chip goes through the ceremony once: it gets its settings, makes its key inside itself,
and has its key slot sealed. The steps and screens are in [PROVISIONING.md](../PROVISIONING.md)
and [the walkthrough](../firmware-production/README.md#the-ceremony-for-a-fresh-chip-quorum-v1).
Some steps are permanent: read them first.

At the end, the console shows the key's **owner address** (C7). That address is how the key
appears in a Safe. It's the same on every chain.

## 2. The console image

```sh
tools/fw push console      # backs the board up, shows the plan, asks "yes", copies and checks every file
tools/fw verify            # all green: the image matches this checkout
```

The production image boots straight into the console. It can't make, replace or lock a key. The
signing code is the only code on it that talks to the chip.

## 3. The board's secrets.py

The board keeps its own `secrets.py`, and no tool ever copies the laptop's over it. Start from
[`firmware/secrets.example.py`](../../firmware/secrets.example.py):

```python
WIFI_SSID = "your-network"        # optional: leave both out to set Wi-Fi on the console (below)
WIFI_PASS = "..."
QUORUM_API_KEY = "..."            # from developer.safe.global
QUORUM_SAFES = [                   # filled in at step 5
]
```

Put the file on the board with `tools/usb cp secrets.py :secrets.py` from a folder outside the
repo, then delete the local copy. The key and the WiFi password should never be in the repo or a
chat.

### Wi-Fi without secrets.py: the setup screen

A console with no Wi-Fi saved opens **Wi-Fi setup** at power-up, instead of the console. That makes
it possible to prepare a console for someone else (pin, Safes, API key) and let them put it on
their own Wi-Fi. Holding **Y** while plugging in opens the same screen on any console, for a new
router or a new password.

- **With a phone:** the console makes its own hotspot and shows a QR code. The phone's camera
  joins it, and the setup page opens by itself (or go to `http://192.168.4.1`). Pick the network,
  type the password, Connect.
- **On the console:** A (on Build 1: press the knob) lists the networks it can see. Pick one and
  type the password on the on-screen keyboard. The joystick moves around the keys; the knob steps
  through them in order. Press types; `del` on an empty field goes back.

Either way the console joins first and saves only if it worked. A wrong password comes back on
the screen (and on the phone's page) as **wrong password**. The networks go in `wifi.json` on the
board (up to 4, the newest first), which the console tries before `secrets.py`'s `WIFI_SSID`, and
which no push ever overwrites. The hotspot's page can set Wi-Fi and nothing else. The console isn't
running while it's up. The ceremony image works offline and never opens setup by itself.

## 4. Pin the chip

```sh
tools/fw pin
```

This reads the chip's serial and key, works out its owner address on the laptop, and writes
`QUORUM_EXPECT` into the board's `secrets.py`. The console then signs only with that chip and
that key. Another chip, a changed key or an unlocked slot stops it on **Not the pinned key**.

## 5. A Safe on each chain

A Safe exists on one chain. For each chain you want the console on (see
[NETWORKS.md](NETWORKS.md)):

1. **Deploy the key's signer on that chain**, once per chain, for about 110k gas:
   ```sh
   tools/quorum live key --usb                # the console's owner address, saved in live.json
   tools/quorum live enroll --chain base      # or basesep, eth
   ```
   The Safe checks the console's signatures through this small contract. Until it's deployed,
   the service refuses the console's signatures.
2. **Make the Safe, or add the console to one**, in app.safe.global on that chain. Add the owner
   address from `live key` as an owner. Keep your browser wallet as an owner too. With 2 of 3
   owners, the console alone can never move funds, and losing it never locks them.
3. **Check it**:
   ```sh
   tools/quorum live status --chain base --safe 0x...
   ```
   You should see the owners, the threshold, the Safe's version (1.3.0 or later) and its queue.

## 6. Point the console at your Safes

```sh
tools/quorum live pico --chain base                  # one Safe
tools/quorum live pico --chain base,eth              # a Safe on each chain, watched together
```

This writes `QUORUM_SAFES` into the board's `secrets.py` from the Safes recorded at step 5. It
keeps the old file as `secrets.bak`, restarts the console, and waits for it to report each Safe.
To write the list by hand instead:

```python
QUORUM_SAFES = [
    {"chainId": 8453, "address": "0x...", "name": "Family Safe"},
    {"chainId": 1, "address": "0x...", "name": "Vault"},
]
```

Leave `QUORUM_URL` out. Each Safe's service comes from its chain, so a Safe can't be pointed at
the wrong chain's service.

## 7. Check it

```sh
tools/fw verify
```

Under `console:`, each Safe should show `ok, owner`. On the device, home shows `2 synced` (or
`Synced` for a single Safe). X (Device) shows `Service verified`: the service's certificate was
checked against the roots built into the image.

**Before real money:**
- [ ] `tools/fw backup`, then copy the backup somewhere outside the repo (it holds `secrets.py`).
- [ ] The Safe has another owner besides the console.
- [ ] One small approval end to end on each chain: propose it in the web app, approve it on the
      console, then `tools/quorum live exec`.
