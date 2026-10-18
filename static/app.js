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

  function fmt(tpl, vars) {
    return tpl.replace(/\{(\w+)\}/g, function (_, k) { return vars[k] != null ? vars[k] : ""; });
  }

  // Same rule as build.py collapse(): >= 4 advisories from one source on one
  // day become one expandable row (e.g. Siemens patch day).
  function collapse(list) {
    var key = function (i) { return i.kind === "advisory" ? i.source_id + "|" + i.day : ""; };
    var counts = {};
    list.forEach(function (i) { var k = key(i); if (k) counts[k] = (counts[k] || 0) + 1; });
    var rows = [], groups = {};
    list.forEach(function (i) {
      var k = key(i);
      if (k && counts[k] >= 4) {
        if (!groups[k]) {
          groups[k] = { group: true, source: i.source, day_label: i.day_label, published: i.published,
                        category: i.category, items: [] };
          rows.push(groups[k]);
        }
        groups[k].items.push(i);
      } else {
        rows.push(i);
      }
    });
    return rows;
  }

  function renderGroup(g) {
    var li = el("li", "item item--group");
    var meta = el("div", "item__meta");
    var time = el("time", null, g.day_label);
    time.setAttribute("datetime", g.published || "");
    meta.appendChild(time);
    meta.appendChild(el("span", "item__source", g.source));
    li.appendChild(meta);
    var body = el("div", "item__body");
    body.appendChild(el("h3", "item__title", fmt(L.group_title, { n: g.items.length, source: g.source })));
    var det = el("details", "group");
    det.appendChild(el("summary", null, fmt(L.group_show, { n: g.items.length })));
    var ul = el("ul", "group__list");
    g.items.forEach(function (i) {
      var row = el("li");
      var url = safeUrl(i.url);
      if (url) {
        var a = el("a", null, i.title);
        a.href = url; a.rel = "noopener noreferrer"; a.target = "_blank";
        row.appendChild(a);
      } else {
        row.textContent = i.title;
      }
      ul.appendChild(row);
    });
    det.appendChild(ul);
    body.appendChild(det);
    var tags = el("ul", "tags");
    if (g.category && L.categories[g.category]) {
      tags.appendChild(el("li", "tag tag--cat tag--" + g.category, L.categories[g.category]));
    }
    var cves = [];
    g.items.forEach(function (i) { (i.cves || []).forEach(function (c) { if (cves.indexOf(c) === -1) cves.push(c); }); });
    cves.sort().slice(0, 6).forEach(function (c) { tags.appendChild(el("li", "tag tag--cve", c)); });
    if (cves.length > 6) tags.appendChild(el("li", "tag tag--x", "+" + (cves.length - 6) + " CVE"));
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
    // Searching or picking a source shows every advisory individually.
    if (!state.q && !state.source) hits = collapse(hits);
    var frag = document.createDocumentFragment();
    hits.slice(0, shown).forEach(function (r) { frag.appendChild(r.group ? renderGroup(r) : renderItem(r)); });
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
