// The UI lab's map and explorer, from the real firmware on the emulator. For each board in
// flows.mjs it starts a console (walk.py: console_test's fake service and clock, the virtual chip),
// presses every flow's buttons through the console's own tick, and keeps each frame the panel got.
//   node tools/uilab/build.mjs            writes docs/quorum-ui/lab/MAP.md and docs/quorum-ui/lab/explore/
//   node tools/uilab/build.mjs --check    CI's: fails when what is committed is not what this writes
// It fails, either way, when a tick raises during a flow, or when the firmware can draw a screen that
// no flow reaches and flows.mjs gives no reason (NOT_WALKED).
//
// A frame's name is the first 12 hex digits of the SHA-256 of its pixels, so the same picture is one
// file and one place in the explorer, whichever flow reached it. --check compares every text file
// byte for byte and the set of PNG names; a PNG's bytes depend on the zlib that packed them.
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadMicroPython } from "../../emu/node_modules/@micropython/micropython-webassembly-pyscript/micropython.mjs";
import { createDevice, frameToRGBA } from "../../emu/core/runtime.mjs";
import { readWorkspace, readShims, ROOT } from "../../emu/core/workspace.mjs";
import { encodePNG } from "../../emu/core/png.mjs";
import { BOARDS, FLOWS, NOT_WALKED } from "./flows.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const LAB = join(ROOT, "docs/quorum-ui/lab");
const check = process.argv.includes("--check");
const read = (...p) => readFileSync(join(...p), "utf8");
const out = new Map();          // path under docs/quorum-ui/lab -> its bytes
const INPUTS = ["D0", "D1", "D1L", "D2", "hold D2"];
const LABEL = { D0: "D0", D1: "D1", D1L: "D1 held", D2: "D2", "hold D2": "D2 held", release: "let go" };

// ----------------------------------------------------------------------------- the walk
async function walk(b) {
  const dev = await createDevice({
    loadMicroPython, keys: new Int32Array(16), heapsize: 4 * 1024 * 1024,
    files: { ...readWorkspace(), "console_test.py": read(ROOT, "test-vectors/console_test.py"), "uilab_walk.py": read(HERE, "walk.py") },
    shims: readShims(), onStdout: (l) => { if (/Traceback|Error|assert/i.test(l)) console.log(l); },
  });
  const py = (code) => { dev.mp.runPython(`_r = ${code}`); return dev.mp.globals.get("_r"); };
  dev.mp.runPython(`with open("secrets.py", "w") as f:
    f.write('BOARD = "${b.id}"\\n')
from uilab_walk import *`);
  const board = { ...b, ...JSON.parse(py(`boot("${b.id}")`)), flows: [] };
  const take = (json) => {
    const t = JSON.parse(json);
    for (const [id, hex] of Object.entries(t.new)) out.set(`explore/shots/${id}.png`, encodePNG(board.w, board.h, frameToRGBA(Buffer.from(hex, "hex"))));
    delete t.new;
    return t;
  };
  for (const f of FLOWS) {
    const run = (code) => { dev.mp.globals.set("_code", code); dev.mp.runPython("run(_code)"); };
    run(f.setup);
    const t0 = take(py(`step("wait 50")`));          // one tick: the flow's first frame
    if (!t0.frames.length) throw new Error(`${f.id}: nothing drawn at its start`);
    const flow = { id: f.id, title: f.title, about: f.about, start: { frame: t0.frames.at(-1), view: t0.view, red: t0.red }, steps: [] };
    let frame = flow.start.frame, down = null;      // the key the flow has down, if any
    for (const [what, note] of f.steps) {
      const t = take(py(`step("${what}")`));
      down = what.startsWith("hold") ? what.slice(5) : what === "release" ? null : down;
      frame = t.frames.at(-1) || frame;
      flow.steps.push({ do: what, down, note, frames: t.frames, to: frame, view: t.view, red: t.red, fx: t.fx.at(-1) || null, msg: t.msg });
    }
    if (f.after) run(f.after);
    board.flows.push(flow);
    console.log(`${b.id}: ${f.id}, ${f.steps.length} steps`);
  }
  dev.dispose();
  return board;
}

// ----------------------------------------------------------------------------- what the firmware can draw
/** The states named in a function's body: s == "x", state == "x", state in ("x", "y"). */
function statesIn(file, def) {
  const src = read(ROOT, "firmware", file);
  const at = src.indexOf(`\ndef ${def}(`);
  if (at < 0) throw new Error(`${file}: no def ${def}`);
  const end = src.indexOf("\ndef ", at + 1);
  const body = src.slice(at, end < 0 ? undefined : end);
  const found = new Set();
  for (const m of body.matchAll(/\b(?:s|state)\s*(?:==\s*("\w+")|in\s*\(([^)]*)\))/g))
    for (const q of (m[1] || m[2]).matchAll(/"(\w+)"/g)) found.add(q[1]);
  return found;
}

// ----------------------------------------------------------------------------- the map
const stateOf = (view) => view.split("/")[0];

function mapOf(board) {
  const views = new Map();        // view -> { frame, red, flows: Set }
  const edges = new Map();        // "from|input|to" -> { from, input, to, fx: Set, flows: Set, drew }
  const pressed = new Map();      // "state|input" -> true
  const see = (view, frame, red, flow) => {
    if (!views.has(view)) views.set(view, { frame, red, flows: new Set() });
    views.get(view).flows.add(flow);
  };
  for (const f of board.flows) {
    let from = f.start.view;
    see(from, f.start.frame, f.start.red, f.id);
    for (const s of f.steps) {
      const input = s.do.startsWith("wait") ? (s.down ? "held on" : "time passes") : s.do;
      const k = [from, input, s.view].join("|");
      if (!edges.has(k)) edges.set(k, { from, input, to: s.view, fx: new Set(), flows: new Set(), drew: false });
      const e = edges.get(k);
      e.flows.add(f.id);
      e.drew = e.drew || s.frames.length > 0;
      if (s.fx) e.fx.add(s.fx);
      pressed.set(stateOf(from) + "|" + s.do, true);
      see(s.view, s.to, s.red, f.id);
      from = s.view;
    }
  }
  return { views, edges, pressed };
}

function mapMd(boards) {
  const md = ["# The three-button console: every screen, and every way between them", "",
    "Written by `node tools/uilab/build.mjs`; don't edit it by hand. It pressed each flow in",
    "[`tools/uilab/flows.mjs`](../../../tools/uilab/flows.mjs) on the real firmware in the emulator and wrote down what the",
    "screen showed. Walk the same flows yourself in [the explorer](https://picoquorum.app/quorum-ui/lab/explore/).", "",
    "A screen is named by its state in `firmware/quorum.py` and, where a state has several, its tab or kind",
    "of page: `home/queue`, `review/verify`. The inputs are the ones `quorum.three` takes: D0, D1, D1 held",
    "1 s, D2, and D2 held.", ""];
  const drawn = new Set([...statesIn("quorum_ui_s.py", "draw"), ...statesIn("quorum.py", "three"), "home"]);
  drawn.delete("boot");            // home's tabs while the boot screen is still up: the same screens
  const problems = [];
  for (const board of boards) {
    const { views, edges, pressed } = mapOf(board);
    const fx = [...edges.values()].some((e) => e.fx.size);
    md.push(`## ${board.name} (\`${board.id}\`)`, "",
      `${board.about}. Its screens are drawn by \`firmware/${board.ui}.py\`.`,
      fx ? "The effect column is what its look asked for as each screen arrived." : "Its look has no effects: every screen arrives whole.", "");

    md.push("### Screens", "", "| screen | as first reached | flows |", "|---|---|---|");
    for (const [v, o] of views)
      md.push(`| \`${v}\`${o.red ? " (red)" : ""} | <img src="explore/shots/${o.frame}.png" width="240" alt="${v}"> | ${[...o.flows].join(", ")} |`);

    md.push("", "### What each button does", "",
      "From the flows. *stays* means the same screen, drawn again (a row moved, a message); *nothing* means no new frame.", "",
      `| on | ${INPUTS.map((i) => LABEL[i]).join(" | ")} |`, `|---|${INPUTS.map(() => "---").join("|")}|`);
    for (const v of views.keys()) {
      const cells = INPUTS.map((i) => {
        const to = [...edges.values()].filter((e) => e.from === v && e.input === i);
        if (!to.length) return "";
        return to.map((e) => (e.to !== v ? `\`${e.to}\`` : e.drew ? "stays" : "nothing")).join(", ");
      });
      if (cells.some(Boolean)) md.push(`| \`${v}\` | ${cells.join(" | ")} |`);
    }

    md.push("", "### Every transition walked", "",
      `| from | input | to |${fx ? " effect |" : ""} flows |`, `|---|---|---|${fx ? "---|" : ""}---|`);
    for (const e of edges.values()) {
      if (e.from === e.to && !e.drew) continue;
      md.push(`| \`${e.from}\` | ${LABEL[e.input] || e.input} | \`${e.to}\` |${fx ? ` ${[...e.fx].join(", ") || "none"} |` : ""} ${[...e.flows].join(", ")} |`);
    }

    const walked = new Set([...views.keys()].map(stateOf));
    const gaps = [];
    for (const s of walked) {
      const miss = INPUTS.filter((i) => !pressed.has(s + "|" + i)).map((i) => LABEL[i]);
      if (miss.length) gaps.push(`| \`${s}\` | ${miss.join(", ")} |`);
    }
    md.push("", "### Not walked yet", "",
      "A button no flow presses on a state. Most do nothing there; a flow that presses one puts that in the table above.", "",
      "| state | never pressed |", "|---|---|", ...gaps, "",
      "Left out on purpose:", "",
      ...Object.entries(NOT_WALKED.screens).map(([s, why]) => `- \`${s}\`: ${why}.`),
      ...Object.entries(NOT_WALKED.rows).map(([s, why]) => `- ${s}: ${why}.`), "");

    for (const s of drawn) if (!walked.has(s) && !NOT_WALKED.screens[s]) problems.push(`${board.id}: the firmware draws "${s}" and no flow reaches it`);
    for (const s of Object.keys(NOT_WALKED.screens)) {
      if (walked.has(s)) problems.push(`${board.id}: "${s}" is walked, so it does not belong in NOT_WALKED`);
      if (!drawn.has(s)) problems.push(`"${s}" in NOT_WALKED is no state the firmware draws`);
    }
  }
  if (problems.length) throw new Error(problems.join("\n") + "\nAdd a flow to tools/uilab/flows.mjs, or a reason to its NOT_WALKED.");
  return md.join("\n");
}

// ----------------------------------------------------------------------------- write, or compare
const boards = [];
for (const b of BOARDS) boards.push(await walk(b));
out.set("MAP.md", mapMd(boards));
out.set("explore/map.json", JSON.stringify({ note: "Written by tools/uilab/build.mjs from the real firmware on the emulator.", boards }, null, 1) + "\n");
for (const f of ["index.html", "explore.css", "explore.js"]) out.set(`explore/${f}`, read(HERE, "page", f));

const shots = join(LAB, "explore/shots");
const have = existsSync(shots) ? readdirSync(shots).map((f) => `explore/shots/${f}`) : [];
const stale = have.filter((f) => !out.has(f));
if (check) {
  const bad = stale.map((f) => `${f}: no flow shows it any more`);
  for (const [p, bytes] of out) {
    const at = join(LAB, p);
    if (!existsSync(at)) bad.push(`${p}: missing`);
    else if (!p.endsWith(".png") && readFileSync(at, "utf8") !== bytes) bad.push(`${p}: differs`);
  }
  if (bad.length) {
    console.error(bad.join("\n") + "\ndocs/quorum-ui/lab is not what tools/uilab/build.mjs writes. Run it, look at what changed, and commit.");
    process.exit(1);
  }
} else {
  mkdirSync(shots, { recursive: true });
  for (const f of stale) rmSync(join(LAB, f));
  for (const [p, bytes] of out) writeFileSync(join(LAB, p), bytes);
}
const n = boards.reduce((a, b) => a + b.flows.length, 0);
console.log(`${check ? "checked" : "wrote"} ${n} flows, ${[...out.keys()].filter((p) => p.endsWith(".png")).length} frames, docs/quorum-ui/lab`);
