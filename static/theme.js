// OTASEC light/dark toggle. Loaded in <head> (not deferred) so the stored choice
// is applied before first paint, so there is no white flash. A separate file because the
// Content-Security-Policy does not allow inline scripts.
(function () {
  "use strict";
  var KEY = "otasec-theme";
  var root = document.documentElement;

  function stored() {
    try { var t = localStorage.getItem(KEY); return t === "light" || t === "dark" ? t : null; }
    catch (e) { return null; }
  }
  function store(t) {
    try { localStorage.setItem(KEY, t); } catch (e) { /* private mode etc. */ }
  }
  function effective() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  var initial = stored();
  if (initial) root.setAttribute("data-theme", initial);

  function sync(btn) {
    var dark = effective() === "dark";
    btn.setAttribute("aria-pressed", String(dark));
    btn.setAttribute("title", btn.getAttribute(dark ? "data-label-light" : "data-label-dark") || "");
    btn.setAttribute("aria-label", btn.getAttribute("title"));
  }

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.hidden = false;
    sync(btn);
    btn.addEventListener("click", function () {
      var next = effective() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      store(next);
      sync(btn);
    });
    if (window.matchMedia) {
      var mq = window.matchMedia("(prefers-color-scheme: dark)");
      var onChange = function () { if (!stored()) sync(btn); };
      if (mq.addEventListener) mq.addEventListener("change", onChange);
    }
  });
})();
