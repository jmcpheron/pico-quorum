// coi.js registers this. The folder's own responses get COOP/COEP (for SharedArrayBuffer) and the
// page's Content-Security-Policy, which then binds its worker too: it may reach this folder and
// Safe's service, nothing else. Everything else goes to the network untouched.
const CSP = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self' https://api.safe.global; worker-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  const r = e.request;
  if (new URL(r.url).origin !== self.location.origin) return;
  if (r.cache === "only-if-cached" && r.mode !== "same-origin") return;
  e.respondWith(fetch(r).then((res) => {
    if (!res || res.status === 0 || res.type === "opaqueredirect") return res;
    const h = new Headers(res.headers);
    h.set("Cross-Origin-Opener-Policy", "same-origin");
    h.set("Cross-Origin-Embedder-Policy", "require-corp");
    h.set("Cross-Origin-Resource-Policy", "same-origin");
    h.set("Content-Security-Policy", CSP);
    return new Response(res.body, { status: res.status, statusText: res.statusText, headers: h });
  }));
});
