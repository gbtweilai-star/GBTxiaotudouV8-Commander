/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 配对/证书：生成一次性码、claim 设备、撤销；不开监听/不生成证书。 */
(function () {
  "use strict";
  var list = document.getElementById("pair-list");
  var countEl = document.getElementById("pair-count");
  var codeEl = document.getElementById("pair-code");
  var note = document.getElementById("pair-note");
  if (!list) return;
  function el(tag, cls, text) {
    var n = document.createElement(tag); if (cls) n.className = cls;
    if (text != null) n.textContent = text; return n;
  }
  function render(j) {
    var rows = (j && j.devices) || [];
    list.innerHTML = "";
    if (!rows.length) list.appendChild(el("div", "pair-empty", "暂无已配对设备"));
    rows.slice(0, 8).forEach(function (d) {
      var row = el("div", "pair-item");
      row.appendChild(el("span", "pair-dot " + (d.status || "")));
      var main = el("div", "pair-main");
      main.appendChild(el("span", "pair-dev", d.name || d.id));
      main.appendChild(el("span", "pair-meta", (d.id || "") + " · " + (d.status || "")));
      row.appendChild(main);
      if (d.status === "active") {
        var x = el("button", "pair-revoke", "×");
        x.type = "button"; x.title = "撤销设备";
        x.onclick = function () {
          fetch("/api/pairing", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ op: "revoke", id: d.id }) }).then(refresh).catch(function () {});
        };
        row.appendChild(x);
      }
      list.appendChild(row);
    });
    if (countEl) countEl.textContent = (j && j.active != null ? j.active : rows.length) + "/" + ((j && j.max) || 32);
  }
  function refresh() {
    fetch("/api/pairing", { cache: "no-store" }).then(function (r) { return r.json(); })
      .then(render).catch(function () {});
  }
  function code() {
    fetch("/api/pairing", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ op: "code" }) }).then(function (r) { return r.json(); }).then(function (j) {
        if (j && j.ok && codeEl) {
          codeEl.textContent = j.code + " · " + j.ttl_s + "s";
          var ci = document.getElementById("pair-code-input"); if (ci) ci.value = j.code;
        } else if (note) note.textContent = "生成失败：" + ((j && j.error) || "未知");
      }).catch(function () {});
  }
  function claim() {
    var name = (document.getElementById("pair-name") || {}).value || "";
    var codeEl2 = document.getElementById("pair-code-input");
    var codeVal = codeEl2 ? codeEl2.value : "";
    fetch("/api/pairing", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ op: "claim", code: codeVal, name: name }) })
      .then(function (r) { return r.json(); }).then(function (j) {
        if (j && j.ok) {
          if (note) note.textContent = "已配对：" + j.device.name + " · token 只显示一次：" + j.device.token;
          refresh();
        } else if (note) note.textContent = "配对失败：" + ((j && j.error) || "未知");
      }).catch(function () {});
  }
  window.__pairingRefresh = refresh;
  var b = document.getElementById("pair-code-btn");
  if (b) b.addEventListener("click", code);
  var c = document.getElementById("pair-claim");
  if (c) c.addEventListener("click", claim);
  setInterval(refresh, 20000);
  refresh();

  /* ── 局域网监听（TLS 自签；只绑私有/回环；无远程命令）── */
  function lanRender(j) {
    var st = (j && j.status) || {};
    var stateEl = document.getElementById("pair-lan-state");
    var info = document.getElementById("pair-lan-info");
    if (stateEl) stateEl.textContent = st.running ? ("运行中 " + (st.mode || "")) : "未启动";
    if (!info) return;
    if (st.running) {
      info.textContent = (st.url || "") + " · 指纹 " + String(st.fingerprint || "").slice(0, 29) +
        "… · 只绑 " + (st.exposure || "") + " · 无远程命令";
    } else {
      info.textContent = "未启动；启动后会生成/复用 state/pairing-cert.pem，只绑私有 LAN 或回环。";
    }
  }
  function lanRefresh() {
    fetch("/api/lan", { cache: "no-store" }).then(function (r) { return r.json(); })
      .then(lanRender).catch(function () {});
  }
  function lanStart() {
    fetch("/api/lan", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ op: "start", host: "lan" }) })
      .then(function (r) { return r.json(); }).then(function (j) {
        var info = document.getElementById("pair-lan-info");
        if (info) info.textContent = j.ok ? ("已启动 " + j.url + " · 指纹 " + j.fingerprint) : ("启动失败：" + (j.error || "未知"));
        lanRefresh();
      }).catch(function () {});
  }
  function lanStop() {
    fetch("/api/lan", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ op: "stop" }) }).then(function (r) { return r.json(); })
      .then(function () { lanRefresh(); }).catch(function () {});
  }
  window.__pairingLanRefresh = lanRefresh;
  var ls = document.getElementById("pair-lan-start"), lx = document.getElementById("pair-lan-stop");
  if (ls) ls.addEventListener("click", lanStart);
  if (lx) lx.addEventListener("click", lanStop);
  lanRefresh();

})();
