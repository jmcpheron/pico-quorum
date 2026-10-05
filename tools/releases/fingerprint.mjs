// The release fingerprint: one SHA-256 that names the firmware a board runs, the same on the Pico
// and in the emulator. It is taken over the image's *source* files (firmware/manifest.json lists
// them), never over the .mpy the Pico runs, so a Pico built from a commit and the browser running
// that commit's files show the same fingerprint and the same blockie (seed "0x" + fingerprint).
//
//   fingerprint = sha256( for each file, sorted by name: name "\0" sha256(bytes) as hex "\n" )
//
// Used by tools/fw build (build.py RELEASE), the emulator (emu/core/workspace.mjs), tools/release
// and the web builds. test-vectors/fingerprint_test.py is a second, independent implementation.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
export const FIRMWARE = join(ROOT, "firmware");

const sha256 = (b) => createHash("sha256").update(b).digest("hex");

export function manifest() {
  return JSON.parse(readFileSync(join(FIRMWARE, "manifest.json"), "utf8"));
}

/** read(name) -> bytes (Buffer, Uint8Array or string) for each name; names: the image's files. */
export function fingerprint(names, read) {
  const lines = [...new Set(names)].sort().map((n) => {
    const b = read(n);
    if (b == null) throw new Error(`fingerprint: no file ${n}`);
    return `${n}\0${sha256(typeof b === "string" ? Buffer.from(b, "utf8") : b)}\n`;
  });
  return sha256(Buffer.from(lines.join(""), "utf8"));
}

/** The fingerprint of an image in firmware/manifest.json, from firmware/ (or another reader). */
export function imageFingerprint(image = "console", read = (n) => readFileSync(join(FIRMWARE, n)), m = manifest()) {
  const img = m.images[image];
  if (!img) throw new Error(`no image "${image}" in firmware/manifest.json`);
  return fingerprint(img.files, read);
}

/** How screens show it: the first 8 hex digits, two groups of four. */
export const short = (fp) => (fp ? `${fp.slice(0, 4)}·${fp.slice(4, 8)}` : "");

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const m = manifest();
  for (const image of process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(m.images))
    console.log(`${image.padEnd(9)} ${imageFingerprint(image, undefined, m)}  ${m.version}`);
}
