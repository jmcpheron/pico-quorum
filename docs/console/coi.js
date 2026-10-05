// GitHub Pages can't send COOP/COEP headers, and the console needs SharedArrayBuffer (keys reach
// Python while it runs). sw.js adds them to this folder's own responses; the first visit reloads
// once, when the worker has taken over. Cross-origin requests (Safe's service) are left alone.
(function () {
  if (self.crossOriginIsolated || !("serviceWorker" in navigator)) return;
  var KEY = "coi-reloaded:" + location.pathname;
  var once = function () { try { if (sessionStorage.getItem(KEY)) return; sessionStorage.setItem(KEY, "1"); } catch (e) { return; } location.reload(); };
  navigator.serviceWorker.register("sw.js").then(function () {
    if (navigator.serviceWorker.controller) once();
    else navigator.serviceWorker.addEventListener("controllerchange", once);
  }, function (e) { console.warn("no service worker, so no SharedArrayBuffer:", e); });
})();
