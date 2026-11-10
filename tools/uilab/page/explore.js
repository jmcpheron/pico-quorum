// The UI lab's explorer: map.json's flows, played by pressing the buttons. tools/uilab/build.mjs
// wrote every frame from the real firmware; this only shows them. A press is looked up: the flow's
// own next step first, then any flow that pressed the same button on the same picture.
const $ = (id) => document.getElementById(id);
const board = (await (await fetch("map.json")).json()).boards[0];
const KEYS = ["D0", "D1", "D2"];
const SAY = { D0: "press D0", D1: "press D1", D1L: "hold D1 for 1 s", D2: "press D2", "hold D2": "press D2 and keep it down", release: "let go" };
const LONG_MS = 1000;       // D1 held this long is D1L, as on the board
const FRAME_MS = 450;       // between the frames of one press (Signing, Sending, Signed)

let fi = 0, at = 0;         // the flow, and how many of its steps are done
let long = 0, auto = 0, play = [];
const held = new Set();     // the buttons down now

const frameAt = (f, i) => (i ? f.steps[i - 1].to : f.start.frame);
const viewAt = (f, i) => (i ? f.steps[i - 1] : f.start).view;
const waitOf = (s) => (s.do.startsWith("wait") ? +s.do.slice(5) : 0);
const sayOf = (s) => (waitOf(s) ? (s.down ? `keep it down ${waitOf(s) / 1000} s more` : "wait") : SAY[s.do]);

// (the picture, the input) -> the flow and step that walked it first
const edges = new Map();
board.flows.forEach((f, a) => f.steps.forEach((s, i) => {
  const k = frameAt(f, i) + "|" + s.do;
  if (!edges.has(k)) edges.set(k, [a, i]);
}));

function render(note) {
  const f = board.flows[fi], s = f.steps[at], last = at ? f.steps[at - 1] : null;
  const view = viewAt(f, at), red = (last || f.start).red;
  $("title").textContent = f.title;
  $("about").textContent = f.about;
  $("screen").alt = `The console's screen: ${view}`;
  $("device").classList.toggle("red", red);
  $("note").textContent = note ?? (last ? last.note : "");
  $("count").textContent = `Step ${at} of ${f.steps.length}`;
  $("step").textContent = s ? `Next: ${sayOf(s)}` : "Done";
  $("step").disabled = !s;
  $("back").disabled = !at;
  const facts = $("facts");
  facts.textContent = "Screen ";
  facts.append(Object.assign(document.createElement("code"), { textContent: view }));
  if (red) facts.append(" · ", Object.assign(document.createElement("span"), { className: "red", textContent: "red" }));
  if (last && last.fx) facts.append(` · arrived with the ${last.fx} effect`);
  for (const b of document.querySelectorAll("#flows button")) b.setAttribute("aria-current", String(+b.dataset.flow === fi));
  const list = $("flows"), cur = list.children[fi];       // on a phone the list is one row: keep the flow in view
  list.scrollLeft += cur.getBoundingClientRect().left - list.getBoundingClientRect().left - 8;
  for (const k of KEYS) $(k).classList.toggle("next", !!s && (s.do === k || s.do === "hold " + k || (k === "D1" && s.do === "D1L")));
  history.replaceState(null, "", `#${f.id}/${at}`);
}

function show(frames, every = FRAME_MS) {
  for (const t of play) clearTimeout(t);
  $("screen").src = `shots/${frames[0]}.png`;
  play = frames.slice(1).map((id, n) => setTimeout(() => { $("screen").src = `shots/${id}.png`; }, (n + 1) * every));
}

function go(flow, step, note) {
  clearTimeout(auto);
  fi = flow; at = step;
  show([frameAt(board.flows[fi], at)]);
  render(note);
  waits();
}

/** Do the flow's next step. A wait's frames fill its own time, and it is done only when that time
 *  has passed: let go before, and it never happened. now: at once (the Next button). */
function advance(now) {
  const s = board.flows[fi].steps[at];
  if (!s) return;
  clearTimeout(auto);
  const ms = now === true ? 0 : waitOf(s);
  const done = () => { at++; render(); waits(); };
  if (!ms) { show(waitOf(s) || !s.frames.length ? [s.to] : s.frames); return done(); }
  if (s.frames.length) show(s.frames, ms / s.frames.length);
  auto = setTimeout(done, ms);
}

/** A wait is the console's own time: it passes by itself, while the key it needs is down. */
function waits() {
  const s = board.flows[fi].steps[at];
  if (!s || !waitOf(s)) return;
  if (s.down) { if (held.has(s.down)) advance(); } else auto = setTimeout(advance, 600);
}

/** One of these inputs, here: the flow's next step, or a flow that walked it from this picture. */
function input(...whats) {
  const f = board.flows[fi], s = f.steps[at], frame = frameAt(f, at);
  if (s && whats.includes(s.do)) return advance();
  for (const w of whats) {
    const e = edges.get(frame + "|" + w);
    if (e) { [fi, at] = e; return advance(); }
  }
  clearTimeout(auto);
  show([frame]);
  render(`No flow does this here yet (${SAY[whats[0]]}).`);
}

function press(k) {
  if (held.has(k)) return;
  held.add(k);
  $(k).classList.add("down");
  if (k === "D1") long = setTimeout(() => { long = 0; input("D1L"); }, LONG_MS);
  else input(k, "hold " + k);
}

function release(k) {
  if (!held.delete(k)) return;
  $(k).classList.remove("down");
  if (k === "D1") {
    if (long) { clearTimeout(long); long = 0; input("D1"); }
    return;
  }
  if (at && board.flows[fi].steps[at - 1].down === k) input("release");       // the flow had it down: letting go is an input
}

// ----------------------------------------------------------------------------- the page
$("board").textContent = `${board.name}: ${board.about}.`;
$("device").classList.toggle("under", !board.railY);
$("screen").width = board.w;
$("screen").height = board.h;
KEYS.forEach((k, n) => {
  const b = Object.assign(document.createElement("button"), { type: "button", id: k, className: "key", textContent: board.names[n] });
  b.setAttribute("aria-label", `${board.names[n]}, the console's button ${n + 1}`);
  if (board.railY) b.style.top = `clamp(26px, ${(board.railY[n] / board.h) * 100}%, 100% - 26px)`;     // level with its row, and all on the board
  b.addEventListener("pointerdown", (e) => { b.setPointerCapture(e.pointerId); press(k); });
  for (const up of ["pointerup", "pointercancel"]) b.addEventListener(up, () => release(k));
  b.addEventListener("keydown", (e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); press(k); } });
  b.addEventListener("keyup", (e) => { if (e.key === " " || e.key === "Enter") release(k); });
  $("keys").append(b);
});
addEventListener("keydown", (e) => { if ("123".includes(e.key) && !e.repeat && !e.ctrlKey && !e.metaKey && !e.altKey) press(KEYS[e.key - 1]); });
addEventListener("keyup", (e) => { if ("123".includes(e.key)) release(KEYS[e.key - 1]); });

board.flows.forEach((f, a) => {
  const b = Object.assign(document.createElement("button"), { type: "button", textContent: f.title });
  b.dataset.flow = a;
  b.addEventListener("click", () => go(a, 0));
  const li = document.createElement("li");
  li.append(b);
  $("flows").append(li);
});
$("step").addEventListener("click", () => advance(true));
$("back").addEventListener("click", () => go(fi, Math.max(0, at - 1)));
$("again").addEventListener("click", () => go(fi, 0));

const seen = new Set();
board.flows.forEach((f, a) => {
  for (let i = 0; i <= f.steps.length; i++) {
    const v = viewAt(f, i);
    if (seen.has(v)) continue;
    seen.add(v);
    const t = Object.assign(document.createElement("button"), { type: "button", className: "tile" });
    t.append(Object.assign(document.createElement("img"), { src: `shots/${frameAt(f, i)}.png`, width: board.w, height: board.h, alt: "", loading: "lazy" }),
      Object.assign(document.createElement("span"), { textContent: v }));
    t.addEventListener("click", () => { go(a, i); $("title").scrollIntoView({ block: "start" }); });
    $("grid").append(t);
  }
});

function fromHash() {
  const [id, n] = location.hash.slice(1).split("/");
  const a = board.flows.findIndex((f) => f.id === id);
  if (a < 0) return go(0, 0);
  go(a, Math.min(board.flows[a].steps.length, Math.max(0, n | 0)));
}
addEventListener("hashchange", fromHash);
fromHash();
