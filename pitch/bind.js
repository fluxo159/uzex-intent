(function () {
  var P = window.PITCH || {};
  var NNBSP = " ";

  function get(path) {
    var cur = P;
    path.split(".").forEach(function (k) { cur = (cur == null) ? undefined : cur[k]; });
    return cur;
  }
  function fmt(n) {
    var s = String(Math.round(Math.abs(n)));
    return (n < 0 ? "−" : "") + s.replace(/\B(?=(\d{3})+(?!\d))/g, NNBSP);
  }
  function thin(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var nodes = [];
    while (walker.nextNode()) if (walker.currentNode.nodeValue.indexOf(NNBSP) >= 0) nodes.push(walker.currentNode);
    nodes.forEach(function (t) {
      var host = t.parentNode;
      if (host.classList && host.classList.contains("th")) return;
      var parts = t.nodeValue.split(NNBSP), frag = document.createDocumentFragment();
      parts.forEach(function (p, i) {
        if (i) { var s = document.createElement("span"); s.className = "th"; s.textContent = NNBSP; frag.appendChild(s); }
        if (p) frag.appendChild(document.createTextNode(p));
      });
      host.replaceChild(frag, t);
    });
  }

  document.querySelectorAll("[data-n]").forEach(function (el) {
    var v = get(el.getAttribute("data-n"));
    if (typeof v !== "number") { el.classList.add("missing"); el.textContent = "??"; el.style.color = "#FF6B6B"; return; }
    el.textContent = fmt(v);
    if (!el.classList.contains("big") && !el.closest(".big")) el.classList.add("m");
  });

  var lots = document.getElementById("lots");
  if (lots && Array.isArray(P.lots)) {
    var html = "";
    P.lots.slice().sort(function (a, b) { return b.qty_t - a.qty_t; }).forEach(function (l) {
      html += '<div class="lot"><div class="sq">' + new Array(l.n_mandates + 1).join("<i></i>") +
        '</div><span class="arr">→</span><div class="dest"><span class="n">' + l.seller +
        '</span><span class="q"><span class="big">' + fmt(l.qty_t) + '</span><span class="u">т</span></span></div></div>';
    });
    var wait = (P.n_buyers || 0) - (P.n_filled || 0);
    if (wait > 0) html += '<div class="lot wait"><div class="sq">' + new Array(wait + 1).join('<i class="off"></i>') +
      '</div><span class="arr">→</span><div class="dest"><span class="n">ждут следующую корзину</span></div></div>';
    lots.innerHTML = html;
  }

  document.querySelectorAll("[data-sq]").forEach(function (el) {
    var n = get(el.getAttribute("data-sq"));
    if (typeof n !== "number") { el.classList.add("missing"); return; }
    el.innerHTML = new Array(n + 1).join("<i></i>");
  });

  var url = document.getElementById("qr-url");
  if (url) url.textContent = String(window.PITCH_QR || "").replace(/^https?:\/\//, "");

  document.querySelectorAll(".m, .big, .mono").forEach(thin);

  function fit() {
    var k = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    document.documentElement.style.setProperty("--k", k);
  }
  fit(); window.addEventListener("resize", fit);

  var frames = Array.prototype.slice.call(document.querySelectorAll(".frame"));

  var APPEAR = {
    p1: ".clock, .cap, .receipt, h1, .src",
    p2: ".qr, .qr-cap, .qr-url, .path .label, .path li",
    p3: ".logo, h1, .claim, .chain > *, .rule",
    p4: ".o-head, .o-lab, .one, .o-was, .why, .src",
    p5: ".money, .tape .st, .day, .back, .demo, .plant h2, .dem, .lot, .today1, .src",
    p6: "h2, .sh-market, .sh-plant, .sh-phone, .facts .f",
    p7: "h2, thead tr, tbody tr",
    p8: ".now-c .head, .now-c li, .next-c .head, .next-c li, .ask",
    p9: ".motto, h1, .card"
  };
  Object.keys(APPEAR).forEach(function (id) {
    var s = document.getElementById(id);
    if (!s) return;
    s.querySelectorAll(APPEAR[id]).forEach(function (el, i) { el.setAttribute("data-a", ""); el.style.setProperty("--i", i); });
  });
  var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches || /[?&]static/.test(location.search);
  if (!still) document.documentElement.classList.add("anim");
  var active = -1;
  function activate(i) {
    if (i === active) return;
    active = i;
    frames.forEach(function (f, j) { f.classList.toggle("in", j === i); });
  }
  var t = null;
  window.addEventListener("scroll", function () { clearTimeout(t); t = setTimeout(function () { activate(current()); }, 80); }, { passive: true });

  function current() {
    var y = window.scrollY, h = window.innerHeight;
    return Math.max(0, Math.min(frames.length - 1, Math.round(y / h)));
  }
  function go(i) {
    i = Math.max(0, Math.min(frames.length - 1, i));
    frames[i].scrollIntoView({ behavior: "instant", block: "start" });
    activate(i);
  }
  document.addEventListener("keydown", function (e) {
    var k = e.key;
    if (k === "ArrowRight" || k === "ArrowDown" || k === " " || k === "PageDown") { e.preventDefault(); go(current() + 1); }
    else if (k === "ArrowLeft" || k === "ArrowUp" || k === "PageUp") { e.preventDefault(); go(current() - 1); }
    else if (k === "Home") { e.preventDefault(); go(0); }
    else if (k === "End") { e.preventDefault(); go(frames.length - 1); }
    else if (k === "f" || k === "F") {
      if (!document.fullscreenElement) document.documentElement.requestFullscreen && document.documentElement.requestFullscreen();
      else document.exitFullscreen && document.exitFullscreen();
    }
  });
  var start = (location.hash && /^#p\d+$/.test(location.hash)) ? parseInt(location.hash.slice(2), 10) - 1 : current();
  frames[Math.max(0, Math.min(frames.length - 1, start))].scrollIntoView({ behavior: "instant", block: "start" });
  requestAnimationFrame(function () { requestAnimationFrame(function () { activate(current()); }); });
  document.documentElement.setAttribute("data-ready", "1");
})();
