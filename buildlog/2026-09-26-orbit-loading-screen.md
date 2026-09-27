# Orbit loading screen on Build 1

Pulled origin/claude/happy-carson-dzf85b (already current at d863ca1, iteration 6), then
returned to build1-console. Adapted its emulator sketch's selected orbit animation into
firmware/bootart.py rather than merging the branch's older firmware.

- Orbiting owners settle into a triangle, green fills upward, and the triangle becomes a
  rotating diamond behind PicoQuorum and cycling taglines.
- Geometry is centred on the real panel width. The 320×240 panel keeps its 19,200-byte strip
  buffer. Each frame's geometry is computed once. Drawing commands are assigned only to strips
  they intersect, and text is rendered only in those strips.
- The artwork is branding; its dots are not actual signature acknowledgements. The bottom
  line comes from the real splash status, not the demo's invented Safe or successful checks.
- Animation uses elapsed time (30 ms per source frame). A successful console boot holds until
  about 13.6 seconds from splash start (4 seconds black, then 9.6 seconds of animation), unless a button skips it. Startup errors skip the hold.
- Animation code is unloaded before normal console polling. Maintenance still skips display
  and network initialization entirely. The small 160×128 panel keeps its compact checklist.
- Font dependencies are included in all images that share splash. The emulator's RGB565-to-PNG
  helper now uses the input length, so native-width captures include all 240 rows.

Validation: nine representative animation frames matched full-frame references pixel for
pixel; rendered captures in emu/shots/boot-native were visually checked. Existing native
strip tests and maintenance tests passed. No keys or settings were changed.

Reproduce the native captures: node test-vectors/run-bootart.mjs

Installed through tools/fw with a verified backup and file hashes. Post-restart verification
matched all 41 image files; console reached Home, pinned chip matched, and the Safe was online
with verified TLS. Direct hardware check confirmed bootart was unloaded, the framebuffer
remained 19,200 bytes, and free heap after collection was 180,768 bytes. Console suite: 110 pass.

The four-second black lead-in clears the panel once and allows normal startup work to proceed.
The animation clock starts after that lead-in, preserving the full animation duration.


Optimization: replaced the all-commands-in-every-strip replay with commands grouped by their
vertical bounds. Text remains one command per label rather than many per-glyph commands.
The nine before/after PNG hashes are identical, and full-frame versus strip references pass.

## Optimized hardware measurements

Installed commit 5f1bcff2 and verified all 41 firmware files. The console returned to Home with
the pinned chip and Safe online. Timed the same six frames on the Pico, with garbage collection
before each sample and the console timer paused; restored Home and its timer afterward.

| Frame | Before (ms) | Optimized (ms) |
|---|---:|---:|
| 12 | 126 | 101 |
| 110 | 111 | 101 |
| 150 | 137 | 115 |
| 186 | 118 | 102 |
| 256 | 169 | 128 |
| 300 | 166 | 128 |

Mean frame time fell from 137.8 to 112.5 ms (18.4% less). The text-heavy frames improved about
24%. This remains roughly 8–10 FPS, limited in part by sending the full panel over SPI.

The optimized animation's code/data used 10,160 bytes while loaded. The largest sampled
free-heap drop was 35,280 bytes, versus 43,536 before. After unloading and collecting garbage,
free memory returned to within 80 bytes of baseline; the 32,768-byte TLS reserve stayed intact.
These are samples, not a guarantee of maximum memory use across every frame.
