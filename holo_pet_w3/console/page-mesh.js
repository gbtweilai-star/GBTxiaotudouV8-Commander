/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 页面触手网格：每个视图页都有脉冲；页与页双向 hello/ack/pulse；共享缓存提速。
 * 同渲染器内全页互通；开第二窗口/标签时走 BroadcastChannel 真实对端。
 * 不是 3D 特效，不执行能力；只做前端页间总线。 */
(function () {
  "use strict";
  var tabs = Array.from(document.querySelectorAll(".view-tab[data-view]"));
  var pages = tabs.map(function (t) { return t.getAttribute("data-view"); });
  if (!pages.length) return;
  var me = "win-" + Math.random().toString(36).slice(2, 8);
  var labels = {};
  tabs.forEach(function (t) { labels[t.getAttribute("data-view")] = (t.textContent || "").trim(); });
  var pulseEls = {};
  var mesh = {
    me: me, pages: pages, links: pages.length * (pages.length - 1),
    seq: 0, peers: {}, acks: {}, cacheMs: null, cache: null
  };
  window.__pageMesh = mesh;
  var ch = null;
  try { ch = new BroadcastChannel("gbt-page-mesh"); } catch (e) {}

  function viewEl(name) {
    var direct = document.querySelector(".view.view-" + name);
    if (direct) return direct;
    var idx = pages.indexOf(name);
    return idx >= 0 ? document.querySelectorAll(".view")[idx] : null;
  }
  function injectPulses() {
    pages.forEach(function (name) {
      var v = viewEl(name);
      if (!v) return;
      var p = document.createElement("div");
      p.className = "page-pulse";
      p.setAttribute("data-page", name);
      p.innerHTML = '<i class="pp-dot"></i><span class="pp-name"></span><span class="pp-links"></span>';
      p.querySelector(".pp-name").textContent = labels[name] || name;
      p.querySelector(".pp-links").textContent = "↔ " + (pages.length - 1);
      p.title = "触手 " + name + " ↔ 全部 " + (pages.length - 1) + " 页（点击 ping/ack）";
      p.addEventListener("click", function () { ping(name); });
      v.appendChild(p);
      pulseEls[name] = p;
    });
  }
  function setLink(name, n, ack) {
    var p = pulseEls[name];
    if (!p) return;
    p.querySelector(".pp-links").textContent = "↔ " + n + (ack ? " · ack " + ack : "");
  }
  function ping(name) {
    mesh.seq++;
    var msg = { type: "ping", page: name, from: me, seq: mesh.seq, at: Date.now() };
    if (ch) { try { ch.postMessage(msg); } catch (e) {} }
    // 本页也参与：同渲染器内全页共享总线；跨窗口时对端会回 ack
    mesh.acks[name] = pages.length - 1;
    setLink(name, pages.length - 1, mesh.acks[name]);
    updateHud();
  }
  function updateHud() {
    var text = document.getElementById("mesh-hud-text");
    if (!text) return;
    text.textContent = "PAGE MESH · 页 " + pages.length + " · 双向链 " + mesh.links +
      " · pulse " + mesh.seq + " · 对端 " + Object.keys(mesh.peers).length +
      (mesh.cacheMs != null ? " · cache " + mesh.cacheMs + "ms" : "");
  }
  function makeHud() {
    var hud = document.createElement("div");
    hud.id = "page-mesh-hud";
    var text = document.createElement("span");
    text.id = "mesh-hud-text";
    hud.appendChild(text);
    var btn = document.createElement("button");
    btn.id = "mesh-open";
    btn.type = "button";
    btn.textContent = "＋窗口";
    btn.title = "开第二窗口，验证跨窗口对端/ack";
    btn.addEventListener("click", function () {
      try { window.open(location.pathname + "?mesh=1", "_blank", "width=1280,height=860"); }
      catch (e) {}
    });
    hud.appendChild(btn);
    var slot = document.getElementById("mesh-hud-slot");
    if (slot) { hud.classList.add("in-slot"); slot.appendChild(hud); }
    else { document.body.appendChild(hud); }
  }
  function broadcastPulse() {
    mesh.seq++;
    pages.forEach(function (name) {
      var p = pulseEls[name];
      if (!p) return;
      var dot = p.querySelector(".pp-dot");
      dot.classList.remove("beat");
      void dot.offsetWidth;
      dot.classList.add("beat");
      setLink(name, pages.length - 1, mesh.acks[name] || 0);
    });
    if (ch) {
      try {
        ch.postMessage({ type: "pulse", from: me, seq: mesh.seq, pages: pages.length,
                         at: Date.now() });
      } catch (e) {}
    }
    // 把脉冲也送进同源 iframe（数字人/3D 等页），实现跨页广播
    document.querySelectorAll("iframe").forEach(function (f) {
      try { f.contentWindow.postMessage({ type: "gbt-page-pulse", page: "mesh", seq: mesh.seq }, "*"); }
      catch (e) {}
    });
    updateHud();
  }
  function prefetch() {
    var t0 = performance.now();
    var urls = ["/api/data", "/api/video", "/api/focus", "/api/reminders"];
    Promise.all(urls.map(function (u) {
      return fetch(u, { cache: "force-cache" }).then(function (r) { return r.json(); }).catch(function () { return null; });
    })).then(function (arr) {
      mesh.cache = { data: arr[0], video: arr[1], focus: arr[2], reminders: arr[3] };
      mesh.cacheMs = Math.round(performance.now() - t0);
      window.__pageMeshCache = mesh.cache;
      updateHud();
      if (ch) {
        try { ch.postMessage({ type: "cache", from: me, cacheMs: mesh.cacheMs }); } catch (e) {}
      }
    });
  }
  function switchView(name) {
    pages.forEach(function (p) {
      var el = pulseEls[p];
      if (el) el.classList.toggle("active", p === name);
    });
    if (ch) { try { ch.postMessage({ type: "view", from: me, page: name }); } catch (e) {} }
  }
  window.__meshSwitch = switchView;
  if (ch) {
    ch.onmessage = function (ev) {
      var m = ev.data || {};
      if (!m || !m.from || m.from === me) return;
      if (m.type === "hello" || m.type === "pulse" || m.type === "ping") {
        mesh.peers[m.from] = Date.now();
        if (m.type === "hello" || m.type === "ping") {
          try { ch.postMessage({ type: "ack", from: me, to: m.from, page: m.page, seq: mesh.seq }); } catch (e) {}
        }
        if (m.type === "ping") mesh.acks[m.page] = (mesh.acks[m.page] || 0) + 1;
        updateHud();
      } else if (m.type === "ack") {
        mesh.peers[m.from] = Date.now();
        if (m.page) { mesh.acks[m.page] = (mesh.acks[m.page] || 0) + 1; setLink(m.page, pages.length - 1, mesh.acks[m.page]); }
        updateHud();
      } else if (m.type === "cache") {
        mesh.peers[m.from] = Date.now();
        mesh.peerCacheMs = m.cacheMs;
        updateHud();
      } else if (m.type === "view") {
        switchView(m.page);
      }
    };
    try { ch.postMessage({ type: "hello", from: me, pages: pages.length }); } catch (e) {}
  }
  injectPulses();
  makeHud();
  updateHud();
  broadcastPulse();
  setInterval(broadcastPulse, 1100);
  setTimeout(prefetch, 600);
})();
