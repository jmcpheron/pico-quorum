# Releases

`index.json` lists every firmware release, newest first. `<version>.json` is each release's
manifest. `tools/release manifest` writes both (`docs/RELEASES.md` has the steps), and the
[app's Releases page](../app/#/releases) shows them.

**A release fingerprint** names the firmware a board runs: the SHA-256 over the image's source
files, as `name \0 sha256(file)` lines sorted by name (`tools/releases/fingerprint.mjs`;
`test-vectors/fingerprint_test.py` is a second implementation). It is taken over the source, not
the compiled `.mpy` files, so a Pico built from a commit and the emulator running that commit show
the same value:

- the console's **Device screen** (home grid, X) shows its blockie and first 8 hex digits, `4c86·c754`;
- the **Device tile** on the home grid carries the same blockie;
- `tools/fw build` and `tools/fw verify` print it.
- the repository's **README** shows each image's blockie with its first and last 8 digits
  ([`badges/`](badges/), written by `tools/releases/badge.mjs`).

Compare the picture on your console with the one on the Releases page. A fingerprint that matches
no release is a development build, or firmware that isn't one of ours.
