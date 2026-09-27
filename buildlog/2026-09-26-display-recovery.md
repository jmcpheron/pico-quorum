# 2.8-inch display and update recovery

The connected Pico 2 W ran MicroPython 1.26.1 with Build 1's 320×240 ST7789 configuration.
The existing two-strip framebuffer used 76,800 bytes. Logs included HTTPS OSError 12 and
restarts when the 32 KB HTTPS reserve could not be reclaimed. Maintenance was checked only
in main.py, after boot.py had allocated the display and joined Wi-Fi. The host updater also
followed machine.reset() as a normal exec, waiting for output after USB disappeared.

Changes:

- Eight 30-row RGB565 strips: 19,200-byte framebuffer, full 320×240 resolution and colour depth.
- Check and latch maintenance before display/network imports; onboard LED indicates recovery.
- Use mpremote's delayed, no-follow reset shortcut and check its exit status.
- Clear the host's cached paused-app state after resetting into maintenance.

Validation:

- User confirmed the physical screen looks fine after installation.
- MicroPython emulator: all 76,800 pixels match a full framebuffer for boundary-crossing
  geometry; anti-aliased glyph seams and frame cleanup pass (`node test-vectors/run-display.mjs`).
- Console suite: 110 pass; manifest suite passes.
- Maintenance tests cover both a file and held key with display/network imports unavailable
  (`python3 test-vectors/boot_maintenance_test.py`).
- On hardware: framebuffer 19,200 bytes, free heap 197,136 bytes after collection, intact
  32,768-byte HTTPS reserve. A complete No chip screen redraw took 501 ms; this is a static
  console renderer, not a high-frame-rate animation path.
- Initial measurements were on No chip. After the second update the console reached Home,
  recognized the pinned chip, and reported the Safe online with verified TLS after two
  normal application requests. Free heap then was 77,584 bytes. No signing or provisioning
  was performed. Both update cycles succeeded; final verification matched every image file.
- An optional live HTTPS probe was rejected by automatic approval review; the application subsequently
  completed its own normal polls successfully. Long-term network stability under load remains
  unverified.

The updater saved verified backups under backups/aee390c50a540678/ before each installation.
