# Firmware releases

A release is **year.month.n**: the n-th of that month. The number is in `firmware/manifest.json`
(`"version"`). `tools/fw build` writes it into the board's `build.py` next to the commit, the Device
screen shows `2026.10.1 · <commit>`, and the boot line in `log.txt` carries both. Each release has a
git tag, `fw-<version>`.

**The release fingerprint** names what a board runs: the SHA-256 of the image's source files
(`tools/release/fingerprint.mjs`; [`releases/`](releases/README.md) has the definition). `tools/fw build`
writes it into `build.py` as `RELEASE`, and the Device screen shows its blockie and first 8 hex
digits (`4c86·c754`). The emulator computes it over the files it runs, so the same release shows
the same picture in the browser. The app's Releases page lists each release's fingerprint.

**To make one:**
1. Set `"version"` and commit.
2. `tools/fw push console --all`, which pushes every board on USB in turn.
3. `git tag fw-<version>` on that commit, then push the tag.

## 2026.10.5 (2026-10-02)

**Fix: Build 1 froze at "screen: ok" on boot.**
- **The cause:** with two Wi-Fi networks saved (one from Wi-Fi setup, one from `secrets.py`),
  the boot asked the radio to scan for the one in range at the moment the boot art started
  drawing on its timer. The scan never came back, and the board stopped answering on USB too.
- **Now:** the boot joins the newest saved network with no scan. If that one is out of range, the
  console's retry walks the others, one every 30 s.
- This is the merge of Wi-Fi setup (#18) with the quick boot.

## 2026.10.4 (2026-10-01)

**Home is a grid to browse when nothing waits for this key:** each Safe, Recent (the last
signatures sent, kept in `recent.json`), the chip and the device. When a request arrives, home is
the queue list as before. The chip's blockie also sits small in the header. Walkthrough:
[quorum-ui/v2](quorum-ui/v2/README.md).

## 2026.10.3 (2026-10-01)

**The loaded chip's blockie on the boot screen.** Once the console has read its chip, the owner's
blockie appears under the tagline, with the chip's name and short address. It's red if the chip
isn't the pinned one. The walkthrough: [quorum-ui/v2](quorum-ui/v2/README.md).

## 2026.10.2 (2026-10-01)

**The fix:** Device → Wi-Fi on Build 1.
- **What went wrong:** the knob's press that chose Wi-Fi is also Build 1's maintenance key at power-up. The console restarted while the knob was still down, so the board came up in maintenance (a blank screen).
- **The console now waits** for the knob to be let go before it restarts, and says so on screen.
- **At boot, a pending Wi-Fi request outranks a held key.** The request is taken once, and the `maint` file still wins.

## 2026.10.1 (2026-10-01)

The first numbered release. It brings three lines of work together on the production console:

- **The quick boot:** the boot art draws on a timer while WiFi joins and the console starts.
  - The Trust M's certificate checks are remembered between boots (`tmproof.txt`).
  - It also has the boot mark and taglines.
- **Wi-Fi setup at power-up:** the console's own hotspot with a QR code, or the on-screen
  keyboard (the joystick, or the knob).
  - Networks are kept in `wifi.json`.
  - Hold Y while plugging in, or pick **Device → Wi-Fi**, the way in on Build 1's knob.
- **The Trust M, ready for the mainnet work:**
  - **T9 freezes the 23 spares and Infineon's own three objects.** TM2 showed those three can
    otherwise be rewritten.
  - **T8 checks live** that the factory key is still the certificate's.
  - **The Chip page** shows the spares.
  - `tools/fw ceremony start|finish`, `tools/fw attest` and `tools/quorum verify`, with a live
    challenge.
  - The details: [TRUSTM.md](TRUSTM.md) and [mainnet/](mainnet/README.md).

**Boards:**
- The Waveshare (`025997e6…`), with TM1.
- Build 1 (`aee390c5…`), with ATECC chip 2.
