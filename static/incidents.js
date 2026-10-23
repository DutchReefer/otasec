// OTASEC incident map: continent filter + zoom, clickable blips, search.
// Progressive enhancement: without JS the full list and the map (blips link
// to #id anchors) still work. No inline scripts or styles (CSP); positions are
// set through SVG attributes and the CSSOM only.
(function () {
  "use strict";
  var svg = document.getElementById("inc-svg");
  var list = document.getElementById("incidents");
  var form = document.getElementById("inc-filters");
  if (!svg || !list || !form || !window.requestAnimationFrame) return;

  var mapBox = document.getElementById("inc-map");
  var tip = document.getElementById("inc-tip");
  var back = document.getElementById("inc-back");
  var status = document.getElementById("inc-status");
  var countEl = document.getElementById("inc-count");
  var reset = document.getElementById("inc-reset");
  var empty = document.getElementById("inc-empty");
  var L = JSON.parse(document.getElementById("inc-i18n").textContent);
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var items = Array.prototype.slice.call(list.querySelectorAll(".inc"));
  var blips = Array.prototype.slice.call(svg.querySelectorAll(".blip"));
  var lands = Array.prototype.slice.call(svg.querySelectorAll(".land"));
  var chips = Array.prototype.slice.call(form.querySelectorAll(".chip"));
  var blipById = {};
  blips.forEach(function (b) {
    b._tx = parseFloat(b.getAttribute("data-tx"));
    b._ty = parseFloat(b.getAttribute("data-ty"));
    b._dot = b.querySelector(".blip__dot");
    b._hit = b.querySelector(".blip__hit");
    blipById[b.getAttribute("data-id")] = b;
  });
  var itemById = {};
  items.forEach(function (li) {
    var id = li.getAttribute("data-id");
    itemById[id] = li;
    // Search covers everything on the card: title, place, summary, tags,
    // attribution, lesson and source titles.
    li._search = li.textContent.replace(/\s+/g, " ").toLowerCase();
    if (blipById[id]) blipById[id]._date = li.querySelector("time").getAttribute("datetime");
  });
  // Oldest first: long-known incidents keep their exact spot when blips collide.
  var byDate = blips.slice().sort(function (a, b) { return a._date < b._date ? -1 : a._date > b._date ? 1 : 0; });

  var WORLD = svg.getAttribute("data-world").split(" ").map(Number);
  var vb = WORLD.slice();
  var state = { q: "", c: "", sector: "", impact: "", id: "" };

  // ---------- filtering ----------
  function matchesFilters(li, ignoreContinent) {
    if (!ignoreContinent && state.c && li.getAttribute("data-c") !== state.c) return false;
    if (state.sector && li.getAttribute("data-sector") !== state.sector) return false;
    if (state.impact && li.getAttribute("data-impact") !== state.impact) return false;
    if (state.q) {
      var hay = li._search;
      var words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      for (var k = 0; k < words.length; k++) if (hay.indexOf(words[k]) === -1) return false;
    }
    return true;
  }

  function apply() {
    var shown = 0;
    items.forEach(function (li) {
      var id = li.getAttribute("data-id");
      var on = state.id ? id === state.id : matchesFilters(li, false);
      li.hidden = !on;
      li.classList.toggle("is-selected", id === state.id);
      if (on) shown++;
      var b = blipById[id];
      // Blips follow search/sector/impact; the continent filter only dims.
      var visible = matchesFilters(li, true);
      b.classList.toggle("is-off", !visible);
      b.classList.toggle("is-dim", visible && !!state.c && li.getAttribute("data-c") !== state.c);
      b.classList.toggle("is-selected", id === state.id);
      if (id === state.id) b.parentNode.appendChild(b);   // draw on top
    });
    lands.forEach(function (p) {
      var on = p.getAttribute("data-c") === state.c;
      p.classList.toggle("is-on", on);
      p.setAttribute("aria-pressed", String(on));
    });
    chips.forEach(function (ch) {
      ch.setAttribute("aria-pressed", String(ch.getAttribute("data-c") === state.c));
    });
    empty.hidden = shown > 0;
    countEl.textContent = L.showing.replace("{shown}", shown).replace("{total}", items.length);
    var filtered = state.q || state.c || state.sector || state.impact || state.id;
    reset.hidden = !filtered;
    status.hidden = false;
    back.hidden = !state.c;
    layout();
    syncUrl();
  }

  function syncUrl() {
    var p = new URLSearchParams();
    ["q", "c", "sector", "impact", "id"].forEach(function (k) { if (state[k]) p.set(k, state[k]); });
    var qs = p.toString();
    history.replaceState(null, "", (qs ? "?" + qs : location.pathname) + (state.id ? "#" + state.id : ""));
  }

  // ---------- map geometry ----------
  function pxPerUnit() {
    var r = svg.getBoundingClientRect();
    if (!r.width) return 1;
    return Math.min(r.width / vb[2], r.height / vb[3]);
  }

  // Same greedy spiral as otasec/geo.py spread(), but with distances in
  // screen pixels, so clusters (Ukraine, Iran, Tokyo) open up as you zoom.
  function layout() {
    var s = pxPerUnit();
    var rDot = (window.innerWidth < 600 ? 5.5 : 5) / s;
    var gap = rDot * 2 + 3 / s;
    var placed = [];
    var golden = Math.PI * (3 - Math.sqrt(5));
    byDate.forEach(function (b) {
      if (b.classList.contains("is-off")) return;
      var x = b._tx, y = b._ty, cx = x, cy = y, k = 0;
      function hits() {
        for (var i = 0; i < placed.length; i++) {
          var dx = cx - placed[i][0], dy = cy - placed[i][1];
          if (dx * dx + dy * dy < gap * gap) return true;
        }
        return false;
      }
      while (hits() && k < 400) {
        k++;
        var r = gap * 0.55 * Math.sqrt(k), a = k * golden;
        cx = x + r * Math.cos(a); cy = y + r * Math.sin(a);
      }
      placed.push([cx, cy]);
      var sel = b.classList.contains("is-selected");
      b._dot.setAttribute("cx", cx.toFixed(2)); b._dot.setAttribute("cy", cy.toFixed(2));
      b._dot.setAttribute("r", (sel ? rDot * 1.45 : rDot).toFixed(2));
      b._hit.setAttribute("cx", cx.toFixed(2)); b._hit.setAttribute("cy", cy.toFixed(2));
      b._hit.setAttribute("r", (rDot + 6 / s).toFixed(2));
    });
  }

  var anim = 0;
  function zoomTo(target) {
    cancelAnimationFrame(anim);
    hideTip();
    var from = vb.slice();
    if (reduceMotion) { vb = target.slice(); setVb(); layout(); return; }
    var t0 = performance.now(), dur = 520;
    function step(now) {
      var t = Math.min(1, (now - t0) / dur);
      var e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      for (var i = 0; i < 4; i++) vb[i] = from[i] + (target[i] - from[i]) * e;
      setVb();
      layout();
      if (t < 1) anim = requestAnimationFrame(step);
    }
    anim = requestAnimationFrame(step);
  }
  function setVb() { svg.setAttribute("viewBox", vb.map(function (v) { return v.toFixed(2); }).join(" ")); }

  function zoomFor(c) {
    if (!c) return WORLD;
    var land = svg.querySelector('.land[data-c="' + c + '"]');
    return land ? land.getAttribute("data-zoom").split(" ").map(Number) : WORLD;
  }

  // ---------- tooltip ----------
  function showTip(b) {
    var li = itemById[b.getAttribute("data-id")];
    tip.replaceChildren();
    var strong = document.createElement("strong");
    strong.textContent = li.querySelector(".inc__title").textContent;
    var meta = document.createElement("span");
    meta.textContent = li.querySelector("time").textContent + " · " + li.querySelector(".inc__place").textContent;
    tip.appendChild(strong); tip.appendChild(meta);
    tip.hidden = false;
    var d = b._dot.getBoundingClientRect(), m = mapBox.getBoundingClientRect();
    var x = d.left + d.width / 2 - m.left, y = d.top - m.top;
    var w = tip.offsetWidth;
    tip.style.left = Math.max(4, Math.min(m.width - w - 4, x - w / 2)) + "px";
    tip.style.top = Math.max(4, y - tip.offsetHeight - 8) + "px";
  }
  function hideTip() { tip.hidden = true; }

  // ---------- actions ----------
  function setContinent(c) {
    state.c = c; state.id = "";
    zoomTo(zoomFor(c));
    apply();
  }

  function select(id, scroll) {
    if (!itemById[id]) return;
    state.id = id;
    apply();
    var li = itemById[id];
    var det = li.querySelector("details");
    if (det) det.open = true;
    if (scroll) {
      var r = li.getBoundingClientRect();
      if (r.top < 0 || r.bottom > window.innerHeight) {
        li.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
      }
    }
  }

  lands.forEach(function (p) {
    function go() { setContinent(state.c === p.getAttribute("data-c") ? "" : p.getAttribute("data-c")); }
    p.addEventListener("click", go);
    p.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); }
    });
  });

  blips.forEach(function (b) {
    b.addEventListener("click", function (e) {
      e.preventDefault();
      var id = b.getAttribute("data-id");
      if (state.id === id) { state.id = ""; apply(); return; }
      select(id, true);
    });
    b.addEventListener("mouseenter", function () { showTip(b); });
    b.addEventListener("mouseleave", hideTip);
    b.addEventListener("focus", function () { showTip(b); });
    b.addEventListener("blur", hideTip);
  });

  chips.forEach(function (ch) {
    ch.addEventListener("click", function () { setContinent(ch.getAttribute("data-c")); });
  });
  back.addEventListener("click", function () { setContinent(""); });
  reset.addEventListener("click", function () {
    state = { q: "", c: "", sector: "", impact: "", id: "" };
    form.q.value = ""; form.sector.value = ""; form.impact.value = "";
    zoomTo(WORLD);
    apply();
  });

  var timer;
  form.q.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(function () { state.q = form.q.value.trim(); state.id = ""; apply(); }, 120);
  });
  form.sector.addEventListener("change", function () { state.sector = form.sector.value; state.id = ""; apply(); });
  form.impact.addEventListener("change", function () { state.impact = form.impact.value; state.id = ""; apply(); });
  form.addEventListener("submit", function (e) { e.preventDefault(); });

  if (window.ResizeObserver) new ResizeObserver(function () { layout(); }).observe(svg);
  else window.addEventListener("resize", layout);

  // ---------- restore from URL ----------
  var params = new URLSearchParams(location.search);
  state.q = params.get("q") || "";
  state.sector = params.get("sector") || "";
  state.impact = params.get("impact") || "";
  var c0 = params.get("c") || "";
  state.c = lands.some(function (p) { return p.getAttribute("data-c") === c0; }) ? c0 : "";
  form.q.value = state.q; form.sector.value = state.sector; form.impact.value = state.impact;
  form.hidden = false;
  svg.classList.add("is-live");
  if (state.c) { vb = zoomFor(state.c).slice(); setVb(); }
  var id0 = params.get("id") || decodeURIComponent(location.hash.slice(1));
  if (id0 && itemById[id0]) select(id0, false); else apply();
})();
