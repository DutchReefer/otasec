// OTASEC live feed: client-side filtering over /data/feed.json.
// Progressive enhancement — the server-rendered list works without JS.
(function () {
  "use strict";
  var PAGE = 40;
  var list = document.getElementById("items");
  var form = document.getElementById("filters");
  var empty = document.getElementById("empty");
  var more = document.getElementById("more");
  var i18nEl = document.getElementById("i18n");
  if (!list || !form || !i18nEl || !window.fetch) return;

  var L = JSON.parse(i18nEl.textContent);
  var items = [];
  var shown = PAGE;
  var state = { q: "", cat: "", sector: "", source: "" };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function safeUrl(u) {
    return /^https?:\/\//i.test(u || "") ? u : "";
  }

  function xLabel(n) {
    return (n === 1 ? L.x.one : L.x.other).replace("{n}", n);
  }

  function renderItem(i) {
    var li = el("li", "item");
    var meta = el("div", "item__meta");
    var time = el("time", null, i.time);
    time.setAttribute("datetime", i.published || "");
    meta.appendChild(time);
    meta.appendChild(el("span", "item__source", i.source));
    li.appendChild(meta);

    var body = el("div", "item__body");
    var h = el("h3", "item__title");
    var url = safeUrl(i.url);
    if (url) {
      var a = el("a", null, i.title);
      a.href = url;
      a.rel = "noopener noreferrer";
      a.target = "_blank";
      h.appendChild(a);
    } else {
      h.textContent = i.title;
    }
    body.appendChild(h);
    if (i.summary) body.appendChild(el("p", "item__summary", i.summary));

    var tags = el("ul", "tags");
    if (i.category && L.categories[i.category]) {
      tags.appendChild(el("li", "tag tag--cat tag--" + i.category, L.categories[i.category]));
    }
    (i.sectors || []).forEach(function (s) { if (L.sectors[s]) tags.appendChild(el("li", "tag", L.sectors[s])); });
    (i.vendors || []).forEach(function (v) { tags.appendChild(el("li", "tag tag--vendor", v)); });
    (i.cves || []).forEach(function (c) { tags.appendChild(el("li", "tag tag--cve", c)); });
    if (i.x) tags.appendChild(el("li", "tag tag--x", xLabel(i.x)));
    body.appendChild(tags);
    li.appendChild(body);
    return li;
  }

  function matches(i) {
    if (state.cat && i.category !== state.cat) return false;
    if (state.sector && (i.sectors || []).indexOf(state.sector) === -1) return false;
    if (state.source && i.source !== state.source) return false;
    if (state.q) {
      var hay = [i.title, i.summary, i.source].concat(i.vendors || [], i.cves || []).join(" ").toLowerCase();
      var words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      for (var k = 0; k < words.length; k++) if (hay.indexOf(words[k]) === -1) return false;
    }
    return true;
  }

  function render() {
    var hits = items.filter(matches);
    var frag = document.createDocumentFragment();
    hits.slice(0, shown).forEach(function (i) { frag.appendChild(renderItem(i)); });
    list.replaceChildren(frag);
    empty.hidden = hits.length > 0;
    more.hidden = hits.length <= shown;
  }

  function syncUrl() {
    var p = new URLSearchParams();
    Object.keys(state).forEach(function (k) { if (state[k]) p.set(k, state[k]); });
    var qs = p.toString();
    history.replaceState(null, "", qs ? "?" + qs : location.pathname);
  }

  function setCat(cat) {
    state.cat = cat;
    form.querySelectorAll(".chip").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-cat") === cat));
    });
  }

  function update() { shown = PAGE; render(); syncUrl(); }

  // Restore filters from the URL.
  var params = new URLSearchParams(location.search);
  state.q = params.get("q") || "";
  state.sector = params.get("sector") || "";
  state.source = params.get("source") || "";
  form.q.value = state.q;
  form.sector.value = state.sector;
  form.source.value = state.source;
  setCat(params.get("cat") || "");

  var timer;
  form.q.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(function () { state.q = form.q.value.trim(); update(); }, 120);
  });
  form.sector.addEventListener("change", function () { state.sector = form.sector.value; update(); });
  form.source.addEventListener("change", function () { state.source = form.source.value; update(); });
  form.addEventListener("submit", function (e) { e.preventDefault(); });
  form.querySelectorAll(".chip").forEach(function (b) {
    b.addEventListener("click", function () { setCat(b.getAttribute("data-cat")); update(); });
  });
  more.addEventListener("click", function () { shown += PAGE; render(); });

  fetch("/data/feed.json", { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (data) {
      items = data.items || [];
      form.hidden = false;
      render();
    })
    .catch(function () { /* keep the server-rendered list */ });
})();
