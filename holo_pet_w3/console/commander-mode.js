(function () {
  "use strict";
  var LS = "gbt_commander_history_v1";
  function history(list) {
    if (list === undefined) {
      try { return JSON.parse(localStorage.getItem(LS) || "[]"); } catch (e) { return []; }
    }
    try { localStorage.setItem(LS, JSON.stringify(list.slice(-30))); } catch (e2) { }
  }
  var DANGER_RX = /转账|汇款|付款|支付|删库|清空|格式化|关机|重启|卸载|密码|密钥|secret/i;
  var INTENTS = [
    { rx: /自检|体检/, cap: "self_check" },
    { rx: /影响|会连动|波及/, cap: "impact_check" },
    { rx: /看屏|截屏|看桌面/, cap: "body_see" },
    { rx: /能力目录|能力位列表|能力清单/, cap: "caps_list" },
    { rx: /几点|时间/, cap: "time_now" },
    { rx: /状态|健康/, cap: "status_report" },
    { rx: /念|说一句/, cap: "voice", op: "tts" }
  ];
  function resolve(text) {
    var t = String(text || "");
    if (DANGER_RX.test(t)) {
      return { danger: true, reason: "危险/资金类操作必须人工在终端 YES，这里没有同意键，我不会替你过门" };
    }
    for (var i = 0; i < INTENTS.length; i++) {
      if (INTENTS[i].rx.test(t)) return { intent: INTENTS[i] };
    }
    return { reason: "这句还没接上能力位。已接：自检 / 影响面 / 看屏 / 能力目录 / 时间 / 状态 / 念一句话" };
  }
  function execute(text) {
    var v = resolve(text);
    if (v.danger || !v.intent) return Promise.resolve(v);
    var payload = {};
    if (v.intent.op) payload.op = v.intent.op;
    if (v.intent.cap === "voice" && !payload.text) payload.text = "收到，我在。";
    if (!window.gbtW3 || !window.gbtW3.cap) {
      return Promise.resolve({ reason: "无桥：本页没接能力位桥。开 tentacle-bridge 再来" });
    }
    return window.gbtW3.cap(v.intent.cap, payload).then(function (r) {
      history(history().concat([{ at: new Date().toISOString(), text: text, cap: v.intent.cap, ok: !!(r && r.ok) }]));
      var say = window.__gbtAvatarSay;
      if (r && r.ok) { say && say("干完了，走的是" + v.intent.cap + "位。"); return r; }
      say && say("没干成。" + ((r && r.error && r.error.message) || "能力位没说清原因"));
      return r;
    });
  }
  window.__gbtCommanderExecute = execute;
  window.__gbtCommanderHistory = history;

  function ensurePanel() {
    if (document.getElementById("gbt-commander")) return;
    var p = document.createElement("div");
    p.id = "gbt-commander";
    p.style.cssText =
      "position:fixed;z-index:2147483002;left:50%;top:14%;transform:translateX(-50%);" +
      "width:min(560px,86vw);display:none;font:13px/1.6 ui-monospace,Consolas,monospace;" +
      "background:rgba(8,11,16,.95);border:1px solid rgba(140,180,230,.25);" +
      "border-radius:14px;padding:12px;color:#dce6f2";
    p.innerHTML =
      '<b style="color:#9fc7ff">她说 · 命令台（Ctrl+K）</b>' +
      '<input id="gbt-commander-in" placeholder="说一句：小土豆 自检 / 看屏 / 影响面…"' +
      ' style="width:100%;margin-top:8px;padding:8px;border-radius:8px;' +
      'border:1px solid rgba(140,180,230,.35);background:rgba(255,255,255,.06);color:inherit" />' +
      '<div id="gbt-commander-out" style="margin-top:8px;color:#96a8bb;white-space:pre-wrap">' +
      "危险/资金必须终端 YES —— 这里没有同意键</div>";
    document.body.appendChild(p);
    var inp = p.querySelector("#gbt-commander-in"), out = p.querySelector("#gbt-commander-out");
    var busy = false;
    inp.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" || busy) return;
      var t = inp.value.trim(); if (!t) return;
      t = t.replace(/^(小土豆|土豆|嗨小土豆)[，,、\s]*/, "");
      out.textContent = "送出中…"; busy = true;
      execute(t).then(function (r) {
        busy = false;
        if (r && r.danger) out.textContent = "⛔ " + r.reason;
        else if (r && r.reason) out.textContent = "※ " + r.reason;
        else if (r && r.ok) out.textContent = "已交给 " + (r.cap || "能力位") + "，账在 commander_history";
        else out.textContent = "回执里没有 ok，原因看上面 / 控制台";
      }, function (err) {
        busy = false; out.textContent = "调用炸了：" + (err && err.message || err);
      });
    });
    document.addEventListener("keydown", function (e) {
      if (e.ctrlKey && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        var show = p.style.display !== "block";
        p.style.display = show ? "block" : "none";
        if (show) setTimeout(function () { inp.focus(); }, 40);
      } else if (e.key === "Escape") { p.style.display = "none"; }
    });
  }
  function boot() {
    if (!document.body) { document.addEventListener("DOMContentLoaded", boot); return; }
    ensurePanel();
  }
  boot();
})();