/* GBT小土豆V8 · 每页共用的「实时桥」（唯一一份，别手改）
 *
 * 三件事，一件都别省：
 *   ① **订阅推送**：onEvent / onStreamState / onIntercom（壳的 preload，IPC 不受页面 CSP 管）
 *   ② **每秒心跳**：`gbtW3.state()` → 面板 /api/state 真业务状态（心智/生命/感官/Codex…）
 *   ③ **把业务数字画出来**：
 *      · 统一「实时条」：每页都有，显示 心智/生命/感官/Codex + 更新时刻（真读数，不是装饰）
 *      · **业务读数条**（2026-10-21 加）：任务 / 矩阵 / 健康 / 审计 四个数,每 2s 拉一次
 *        （只读本地文件；窗不可见不轮询；取不到显示「—」，不拿 0 顶替）
 *      · 通用绑定契约：页里任意元素写 `data-live="mind.mood"`，心跳到就按点路径填值；
 *        写 `data-live="biz.tasks"` 绑业务读数（可用 tasks/matrix/health/audit）；
 *        写 `data-live-ts` 的元素每次心跳盖一次时间戳。**页面不用自己写轮询。**
 *
 * 三态（本仓纪律：安静≠坏了≠被拒，不许合并成一句）：
 *   ● LIVE 0.4s · hb12/ev3   —— 心跳 2.5s 内（桥活着，业务状态在拉）
 *   ○ 静默 12s               —— 桥在但心跳超时（不假装在线）
 *   ⚠ 无桥 · 浏览器直开       —— 不在壳里（preload 没给桥），只显示静态数据
 *
 * 对外：window.GBT_LIVE.{state(),latest(),on(fn),beat()}；(window.dispatchEvent('gbt-live'))
 */
(function () {
  if (window.__GBT_LIVE_BADGE__) return;
  window.__GBT_LIVE_BADGE__ = true;

  var api = window.gbtW3 || null;
  var counts = { event: 0, stream: 0, intercom: 0, heartbeat: 0 };
  var lastEventAt = 0, lastBeatAt = 0, latest = null, bootAt = Date.now();
  var HEARTBEAT_MS = 1000, LIVE_MS = 2500;

  /* ── 业务读数（2026-10-21 加：Owner 令「秒级感知所有状态」）────────────────────
     为什么单开一层：`/api/state` 只有 心智/生命/感官/Codex 这棵树，
     而页面上真正在讲业务的那几个数（任务 / 矩阵 / 健康 / 审计）在别的通道里。
     四条都**只读本地文件**（main.cjs 的 w3Tasks/w3Matrix/w3Health/w3Ledger），
     不跑能力位、不起 python ⇒ 每 2s 轮一次也压不垮。
     🔴 两条口径：
       · 取不到 = null（条上显示「—」），**绝不拿 0 冒充**（假绿比报错更坏）；
       · **窗不可见就不轮**（document.hidden）—— 42 页同时开着也只压一条。
     覆盖/orphans/gene 不在此列：它们要现跑 python 审计器（几十秒），
     按「秒级」轮会把机器拖死，页面上要用就显式调 cap，不进这条常驻轮询。 */
  var biz = { tasks: null, matrix: null, health: null, audit: null, at: 0 };
  var bizBox = null, bizErrs = [], BIZ_MS = 2000;

  function cnt(v) { return typeof v === "number" && isFinite(v) ? v : null; }

  function bizPull() {
    if (!api || document.hidden) return;
    var errs = [];
    function one(ch, key, pick) {
      if (typeof api[ch] !== "function") { errs.push(ch + ":通道不在"); return Promise.resolve(); }
      return Promise.resolve().then(function () { return api[ch](); }).then(function (r) {
        if (r && r.ok === false) throw new Error(r.error || "回执 ok:false");
        var d = r && r.data !== undefined ? r.data : r;
        var v = pick(d);
        if (v === null) throw new Error("形状里没有这个数");
        biz[key] = v;
      }).catch(function (e) {
        biz[key] = null;
        errs.push(ch + ":" + String((e && e.message) || e).slice(0, 40));
      });
    }
    Promise.all([
      one("tasks", "tasks", function (d) { return cnt(d && d.total); }),
      one("matrix", "matrix", function (d) {
        var rows = d && d.rows ? d.rows : (Array.isArray(d) ? d : null);
        return rows ? rows.length : null;
      }),
      one("health", "health", function (d) {
        return d && Array.isArray(d.records) ? d.records.length : null;
      }),
      one("ledger", "audit", function (d) {
        return d && Array.isArray(d.audit_tail) ? d.audit_tail.length : null;
      })
    ]).then(function () {
      biz.at = Date.now();
      bizErrs = errs;
      paintBiz();
      bindMarkers();
    });
  }

  function paintBiz() {
    if (!bizBox) return;
    if (!api) { bizBox.textContent = ""; bizBox.style.display = "none"; return; }
    bizBox.style.display = "";
    var got = 0;
    var parts = [["任务", biz.tasks], ["矩阵", biz.matrix], ["健康", biz.health], ["审计", biz.audit]]
      .map(function (x) {
        if (x[1] !== null) got += 1;
        return x[0] + " " + (x[1] === null ? "—" : x[1]);
      });
    if (!got) {
      bizBox.textContent = "○ 业务读数 · 未读到" + (bizErrs.length ? "（" + bizErrs.join("; ") + "）" : "");
      bizBox.style.color = "#8b97a8";
      return;
    }
    bizBox.textContent = parts.join(" · ")
      + " · " + ((Date.now() - biz.at) / 1000).toFixed(1) + "s 前"
      + (bizErrs.length ? " · 缺 " + bizErrs.join("; ") : "");
    bizBox.style.color = bizErrs.length ? "#f5b041" : "#cfd6dd";
  }

  var badge = null, strip = null;

  function mkBox(id, css) {
    var d = document.createElement("div");
    d.id = id;
    d.setAttribute("data-kind", id);
    d.style.cssText = css;
    document.body.appendChild(d);
    return d;
  }

  function ensureBoxes() {
    if (!document.body) return;
    if (!badge) {
      badge = mkBox("gbt-live-badge",
        "position:fixed;right:10px;bottom:10px;z-index:2147483000;" +
        "font:11.5px/1.4 ui-monospace,Consolas,monospace;padding:3px 8px;border-radius:999px;" +
        "border:1px solid rgba(255,255,255,.16);background:rgba(10,13,18,.82);color:#cfd6dd;" +
        "pointer-events:none;opacity:.92");
    }
    if (!strip) {
      strip = mkBox("gbt-live-strip",
        "position:fixed;left:10px;bottom:10px;z-index:2147482999;max-width:calc(100vw - 220px);" +
        "font:11.5px/1.5 ui-monospace,Consolas,monospace;padding:3px 9px;border-radius:8px;" +
        "border:1px solid rgba(255,255,255,.12);background:rgba(10,13,18,.78);color:#cfd6dd;" +
        "pointer-events:none;opacity:.92;white-space:nowrap;overflow:hidden;text-overflow:ellipsis");
      strip.textContent = "○ 实时条 · 等心跳";
    }
    if (!bizBox) {
      bizBox = mkBox("gbt-live-biz",
        "position:fixed;left:10px;bottom:34px;z-index:2147482998;max-width:calc(100vw - 220px);" +
        "font:11.5px/1.5 ui-monospace,Consolas,monospace;padding:3px 9px;border-radius:8px;" +
        "border:1px solid rgba(255,255,255,.12);background:rgba(10,13,18,.72);color:#cfd6dd;" +
        "pointer-events:none;opacity:.92;white-space:nowrap;overflow:hidden;text-overflow:ellipsis");
      bizBox.textContent = "○ 业务读数 · 等第一次拉取";
    }
  }

  function dig(obj, path) {
    if (!obj || !path) return undefined;
    var cur = obj;
    var parts = String(path).split(".");
    for (var i = 0; i < parts.length; i++) {
      if (cur == null) return undefined;
      cur = cur[parts[i]];
    }
    return cur;
  }

  function fmt(v) {
    if (v == null) return "—";
    if (typeof v === "number") return (Math.round(v * 100) / 100).toString();
    if (typeof v === "boolean") return v ? "是" : "否";
    if (typeof v === "object") return JSON.stringify(v).slice(0, 40);
    return String(v).slice(0, 40);
  }

  function paintStrip() {
    if (!strip) return;
    var d = latest && (latest.data || latest);
    if (!d || typeof d !== "object") {
      strip.textContent = api ? "○ 实时条 · 尚无业务状态" : "⚠ 无桥 · 浏览器直开（只有静态数据）";
      return;
    }
    var mind = d.mind || {}, life = d.life || {}, sen = d.sensory || {};
    var ev = (life.counts && (life.counts.events != null ? life.counts.events : life.counts)) || life.events || "—";
    var parts = [
      "心智 " + fmt(mind.mood) + (mind.valence != null ? "(" + fmt(mind.valence) + ")" : ""),
      "生命 " + fmt(ev),
      "感官 " + [["脑", sen.brain], ["眼", sen.eye], ["耳", sen.ear], ["嘴", sen.mouth], ["手", sen.hand]]
        .map(function (x) { return x[0] + (x[1] ? "✓" : "✗"); }).join(""),
      "Codex " + (d.codex_ready ? "就绪" : (d.codex && d.codex.connected ? "连上" : "未连")),
      "更新 " + (lastBeatAt ? ((Date.now() - lastBeatAt) / 1000).toFixed(1) + "s" : "—")
    ];
    strip.textContent = parts.join(" · ");
  }

  function paintBadge() {
    if (!badge) return;
    var now = Date.now(), txt, color;
    if (!api) {
      txt = "⚠ 无桥 · 浏览器直开"; color = "#8b97a8";
    } else if (!lastBeatAt) {
      txt = "○ 桥已接 · 等心跳 " + Math.round((now - bootAt) / 1000) + "s"; color = "#f5b041";
    } else if (now - lastBeatAt < LIVE_MS) {
      txt = "● LIVE " + ((now - lastBeatAt) / 1000).toFixed(1) + "s · hb" + counts.heartbeat + "/ev" + counts.event;
      color = "#34d399";
    } else {
      txt = "○ 静默 " + Math.round((now - lastBeatAt) / 1000) + "s · hb" + counts.heartbeat + "/ev" + counts.event;
      color = "#8b97a8";
    }
    badge.textContent = txt;
    badge.style.color = color;
    badge.style.borderColor = color;
  }

  // 通用绑定：页里 [data-live="path"] 每跳填一次；[data-live-ts] 盖时间戳
  // 路径两种命名空间（别混）：`biz.tasks` 走业务读数条那几个数；其余走 /api/state 那棵树。
  function bindMarkers() {
    var list = document.querySelectorAll("[data-live]");
    for (var i = 0; i < list.length; i++) {
      var path = list[i].getAttribute("data-live");
      var v = String(path || "").indexOf("biz.") === 0
        ? biz[String(path).slice(4)]
        : dig(latest && (latest.data || latest), path);
      if (v !== undefined && v !== null) list[i].textContent = fmt(v);
    }
    var ts = document.querySelectorAll("[data-live-ts]");
    var t = new Date();
    var hh = String(t.getHours()).padStart(2, "0");
    var mm = String(t.getMinutes()).padStart(2, "0");
    var ss = String(t.getSeconds()).padStart(2, "0");
    for (var j = 0; j < ts.length; j++) ts[j].textContent = hh + ":" + mm + ":" + ss;
  }

  function fire(kind, msg) {
    try {
      window.dispatchEvent(new CustomEvent("gbt-live", { detail: { kind: kind, msg: msg, at: Date.now() } }));
    } catch (e) { /* 老壳没有 CustomEvent 也不许炸页面 */ }
  }

  function hook(name, kind) {
    if (!api || typeof api[name] !== "function") return false;
    try {
      api[name](function (msg) { counts[kind] += 1; lastEventAt = Date.now(); fire(kind, msg); paintBadge(); });
      return true;
    } catch (e) { return false; }
  }

  if (api) { hook("onEvent", "event"); hook("onStreamState", "stream"); hook("onIntercom", "intercom"); }

  function beat() {
    ensureBoxes();
    if (!api || typeof api.state !== "function") { paintBadge(); paintStrip(); return; }
    try {
      Promise.resolve(api.state()).then(function (r) {
        counts.heartbeat += 1;
        lastBeatAt = Date.now();
        latest = r;
        fire("state", r);
        paintBadge(); paintStrip(); bindMarkers();
      }).catch(function () { paintBadge(); paintStrip(); });
    } catch (e) { paintBadge(); paintStrip(); }
  }

  window.GBT_LIVE = {
    online: !!api,
    state: function () {
      return { online: !!api, lastEventAt: lastEventAt, lastBeatAt: lastBeatAt,
               counts: counts, ageMs: lastBeatAt ? Date.now() - lastBeatAt : null };
    },
    latest: function () { return latest; },
    biz: function () { return { tasks: biz.tasks, matrix: biz.matrix, health: biz.health, audit: biz.audit,
                                at: biz.at, errs: bizErrs.slice(0) }; },
    on: function (fn) { window.addEventListener("gbt-live", function (e) { fn(e.detail); }); },
    beat: beat
  };

  function boot() { paintBadge(); paintStrip(); beat(); bizPull(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
  setInterval(function () { paintBadge(); paintStrip(); paintBiz(); }, 1000);
  setInterval(beat, HEARTBEAT_MS);
  setInterval(bizPull, BIZ_MS);
  // 切回来立刻补一次（不可见期间不轮询，看到的数不能是"停在切走那一刻"的）
  document.addEventListener("visibilitychange", function () { if (!document.hidden) bizPull(); });
})();
