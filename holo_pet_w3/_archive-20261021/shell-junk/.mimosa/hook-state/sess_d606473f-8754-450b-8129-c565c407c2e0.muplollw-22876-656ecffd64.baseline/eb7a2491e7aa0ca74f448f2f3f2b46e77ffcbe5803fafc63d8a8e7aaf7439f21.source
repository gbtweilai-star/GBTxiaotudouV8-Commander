/* ══════════════════════════════════════════════════════════════════════════
   GBT小土豆V8 · 触手视觉回传窗 · 渲染层
   ──────────────────────────────────────────────────────────────────────────
   一帧都不画。本文件只做三件事：
     ① 把 `frames.js`（真抓帧器写的清单）读进来；
     ② 把**最新那一帧**显示出来，并把它的真实读数摊开；
     ③ 诚实标注状态：`live` / `stale` / `lost` —— **过期就说过期，没有就说没有**。

   三条硬约束（都是踩过的坑，别改回去）：
   · **经典脚本**，不是 ES module：`file://` 下 `<script type="module">` 被 CORS 挡死。
   · **不写任何内联样式**（`el.style.x` / `style="..."`）：本页 CSP 是 `style-src 'self'`。
     状态一律走 `data-*` 属性 + 类名，样式全在 eye.css 里。
   · **不 fetch**：`connect-src 'none'`。轮询靠**动态插入 `<script src="frames.js?t=...">`**
     —— 换 query 才能绕开浏览器对同一 URL 的缓存，否则永远显示第一帧。
   ══════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var POLL_MS = 1200;
  /* 超过这么多秒没有新帧就不叫"实时"了。
     取帧器默认 1.5s 一帧 ⇒ 4s ≈ 连丢三帧，够判"断"。 */
  var STALE_S = 4;

  var el = {
    signal: document.getElementById("signal"),
    signalText: document.getElementById("signal-text"),
    view: document.getElementById("view"),
    shot: document.getElementById("shot"),
    osd: document.querySelector(".eye-osd"),
    osdClock: document.getElementById("osd-clock"),
    osdSeq: document.getElementById("osd-seq"),
    osdTag: document.getElementById("osd-tag"),
    standbyTitle: document.getElementById("standby-title"),
    standbyBody: document.getElementById("standby-body"),
    telemetry: document.getElementById("telemetry"),
    film: document.getElementById("filmstrip"),
    detail: document.getElementById("detail"),
    ringNote: document.getElementById("ring-note"),
    chanSrc: document.getElementById("chan-src"),
    chanVia: document.getElementById("chan-via")
  };

  var inspecting = null;      // 正在回看的帧名（null = 看最新）
  var lastRendered = null;    // 上一次渲染用的清单内容指纹，防无谓重绘

  function escText(s) { return s === null || s === undefined ? "—" : String(s); }

  function hhmmss(iso) {
    if (!iso) return "--:--:--";
    var m = String(iso).match(/T(\d\d:\d\d:\d\d)/);
    return m ? m[1] : String(iso);
  }

  function ago(epoch) {
    if (!epoch) return "—";
    var d = Date.now() / 1000 - epoch;
    if (d < 0) return "0.0s";
    if (d < 60) return d.toFixed(1) + "s";
    if (d < 3600) return Math.floor(d / 60) + "m" + Math.floor(d % 60) + "s";
    return Math.floor(d / 3600) + "h" + Math.floor((d % 3600) / 60) + "m";
  }

  /* ── 小组件 ──────────────────────────────────────────────────────────── */
  function tile(label, value, unit, state) {
    var d = document.createElement("div");
    d.className = "mc-tile";
    var l = document.createElement("div");
    l.className = "mc-tile-label";
    l.textContent = label;
    var v = document.createElement("div");
    v.className = "mc-tile-value" + (state ? " " + state : "");
    v.textContent = escText(value);
    d.appendChild(l);
    d.appendChild(v);
    if (unit) {
      var u = document.createElement("span");
      u.className = "mc-tile-unit";
      u.textContent = unit;
      v.appendChild(u);
    }
    return d;
  }

  function kv(dl, k, v, dim) {
    var dt = document.createElement("dt");
    dt.textContent = k;
    var dd = document.createElement("dd");
    if (dim) dd.className = "dim";
    dd.textContent = escText(v);
    dl.appendChild(dt);
    dl.appendChild(dd);
  }

  function setState(viewState, chipState, chipText) {
    el.view.setAttribute("data-state", viewState);
    el.signal.setAttribute("data-state", chipState);
    el.signalText.textContent = chipText;
  }

  /* ── 主渲染 ──────────────────────────────────────────────────────────── */
  function render() {
    var d = window.GBT_EYE;

    /* ① 清单都没有 ⇒ 抓帧器没跑过。**不摆占位图**，直接说清楚怎么让它有画面。 */
    if (!d) {
      setState("empty", "lost", "未接上取帧器");
      el.standbyTitle.textContent = "还没有帧";
      el.standbyBody.textContent = "取帧器还没写过清单。跑一次： ";
      var c = document.createElement("code");
      c.textContent = "py -3.14 tools/codex-scripts/eye-feed.py --loop";
      el.standbyBody.appendChild(c);
      el.film.replaceChildren();
      var p = document.createElement("p");
      p.className = "eye-empty";
      p.textContent = "清单里没有帧。";
      el.film.appendChild(p);
      el.detail.replaceChildren();
      var p2 = document.createElement("p");
      p2.className = "eye-empty";
      p2.textContent = "没有帧就没有读数 —— 不编一个出来。";
      el.detail.appendChild(p2);
      return;
    }

    var frames = d.frames || [];
    var newest = frames[0] || null;
    var age = newest && newest.epoch ? (Date.now() / 1000 - newest.epoch) : null;
    var fresh = age !== null && age <= STALE_S;

    /* ② 取帧失败 / 还没成功过。**如实报失败原因**，并把"没有新帧"写在明面上。 */
    if (!d.ok || !newest) {
      setState("lost", "lost", d.ok === false ? "取帧失败" : "还没有帧");
      el.standbyTitle.textContent = d.ok === false ? "取帧失败" : "还没有帧";
      el.standbyBody.textContent = d.why
        ? String(d.why)
        : "清单是空的。跑一次取帧器。";
      renderTelemetry(d, newest, age, false);
      renderFilm(frames, null);
      renderDetail(d, null);
      return;
    }

    /* ③ 正常：有帧。过期与实时**必须一眼可分** —— 这是本窗唯一的信誉所在。 */
    var chip = fresh ? "live" : "stale";
    var chipText = fresh ? "实时" : ("静默 " + (age === null ? "" : Math.floor(age) + "s"));
    setState("ok", chip, chipText);

    var show = newest;
    if (inspecting) {
      for (var i = 0; i < frames.length; i++) {
        if (frames[i].name === inspecting) { show = frames[i]; break; }
      }
    }
    var isLive = show === newest && fresh;

    /* 🔴 声明数据新鲜度（2026-09-23 第 34 轮）：本窗是**文件轮询**取数，
       时刻用**这一帧的抓帧时刻**（`show.at`）—— 那才是"屏上这画面是什么时候的"。
       看回看旧帧时年龄自然变大、铬会跟着变黄变红：**这正是我们要它说的话。** */
    window.GBT_DATA = { kind: "实时", at: show.at };

    el.shot.setAttribute("src", "frames/" + show.name);
    el.osd.setAttribute("data-live", isLive ? "true" : "false");
    el.osdClock.textContent = hhmmss(show.at);
    el.osdSeq.textContent = "#" + show.seq;
    el.osdTag.hidden = isLive;

    renderTelemetry(d, show, age, fresh);
    renderFilm(frames, show.name);
    renderDetail(d, show);
  }

  function renderTelemetry(d, frame, age, fresh) {
    el.telemetry.replaceChildren();
    var st = fresh ? "ok" : "alert";
    el.telemetry.appendChild(tile("信号", fresh ? "实时" : "静默", "", st));
    if (frame) {
      el.telemetry.appendChild(tile("分辨率", frame.width + "×" + frame.height));
      el.telemetry.appendChild(tile("帧号", "#" + frame.seq));
      el.telemetry.appendChild(tile("帧大小", frame.kb, "KB"));
      el.telemetry.appendChild(tile("采集", d.capture_ms == null ? "—" : Math.round(d.capture_ms), "ms"));
      /* 🔴 采集 ≠ 整帧耗时。引擎量的只是 DXGI 抓那一帧（实测 5ms），
         真正花掉的是"抓帧 + JPEG 编码 + base64 + 落盘"（实测 ~350ms）。
         只报前者会让人以为这一路很轻 —— 两个都摆出来。 */
      el.telemetry.appendChild(tile("整帧耗时", d.wall_ms == null ? "—" : d.wall_ms, "ms"));
      el.telemetry.appendChild(tile("引擎", d.engine || "—"));
      el.telemetry.appendChild(tile("距现在", ago(frame.epoch), "", fresh ? "ok" : "alert"));
      el.telemetry.appendChild(tile("环形", (d.slots_filled || 0) + "/" + (d.ring || 0)));
    } else {
      el.telemetry.appendChild(tile("状态", "无帧", "", "alert"));
    }
  }

  function renderFilm(frames, currentName) {
    el.film.replaceChildren();
    if (!frames.length) {
      var p = document.createElement("p");
      p.className = "eye-empty";
      p.textContent = "清单里没有帧。";
      el.film.appendChild(p);
      return;
    }
    el.ringNote.textContent = frames.length + " 帧 · 环形覆盖";
    frames.forEach(function (f) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "eye-thumb";
      b.setAttribute("aria-current", f.name === currentName ? "true" : "false");
      b.title = "回看第 " + f.seq + " 帧（" + f.at + "）";
      var img = document.createElement("img");
      img.src = "frames/" + f.name;
      img.alt = "第 " + f.seq + " 帧";
      var sp = document.createElement("span");
      sp.textContent = "#" + f.seq + " " + hhmmss(f.at);
      b.appendChild(img);
      b.appendChild(sp);
      b.addEventListener("click", function () {
        /* 点最新那帧 = 回到实时；点旧帧 = 进入回看（页面会打「回看」标、REC 熄灭）。 */
        inspecting = (frames[0] && f.name === frames[0].name) ? null : f.name;
        render();
      });
      el.film.appendChild(b);
    });
  }

  function renderDetail(d, frame) {
    el.detail.replaceChildren();
    if (!frame) {
      var p = document.createElement("p");
      p.className = "eye-empty";
      p.textContent = "没有帧就没有读数 —— 不编一个出来。";
      el.detail.appendChild(p);
      return;
    }
    var dl = document.createElement("dl");
    dl.className = "eye-detail";
    kv(dl, "抓帧时刻", frame.at);
    kv(dl, "帧字节", frame.bytes.toLocaleString("en-US") + " B");
    kv(dl, "指纹", frame.hash);
    kv(dl, "槽位", "f-" + String(frame.slot).padStart(3, "0") + ".jpg");
    /* 🔴 这一行第一版写的是「画面变化：与上帧相同 / 有变化」—— **那是错的，已改**。
       `delta` 的真语义不是"画面变没变"，而是"**这一帧是脏矩形，不是整帧**"
       （见 omni_core._screen_capture：只有增量分支取到子矩形时才置 True）。
       本窗固定 `incremental=false` ⇒ `delta` 恒为 False，而屏幕明明一直在变 ——
       照旧标签念就是**这扇窗自己在撒谎**。改成按 `full_frame` 如实报画面模式。 */
    kv(dl, "画面模式", d.full_frame === false
      ? "⚠ 脏矩形（不是整帧）"
      : "整帧（增量已关）");
    kv(dl, "格式", d.fmt || "—");
    el.detail.appendChild(dl);

    el.chanSrc.textContent = "来源：" + (d.source || "—");
    el.chanVia.textContent = "取帧路径：" + (d.via || "—");
  }

  /* ── 轮询：动态插 `<script src="frames.js?t=...">` ───────────────────────
     🔴 **必须换 query**：浏览器对同一 `file://` URL 有缓存，不换就永远读第一帧
     （那会让这扇窗变成"看着在动、其实是死图"—— 比没有还坏）。 */
  var ticking = false;
  function poll() {
    var s = document.createElement("script");
    s.src = "frames.js?t=" + Date.now();
    s.onload = function () {
      var sig = JSON.stringify(window.GBT_EYE || null).slice(0, 400);
      if (sig !== lastRendered) {      // 内容真变了才重绘，别把 DOM 摇出闪烁
        lastRendered = sig;
        render();
      }
      s.remove();
      ticking = false;
    };
    s.onerror = function () {
      /* 清单读不到 ⇒ 明说，不静默假装还在跑 */
      setState("empty", "lost", "清单读不到");
      el.standbyTitle.textContent = "清单读不到";
      el.standbyBody.textContent = "frames.js 不在。跑一次： py -3.14 tools/codex-scripts/eye-feed.py";
      s.remove();
      ticking = false;
    };
    document.body.appendChild(s);
  }

  /* 首屏也走**同一条动态加载路径**（HTML 里没有静态 `<script src="frames.js">`）。
     理由：清单已排除出库（它描述的是主人的屏幕），静态引入会让全新检出必吃 404；
     走这里读不到时给的是结构化提示，不是一条无主的网络错。 */
  tick();
  setInterval(tick, POLL_MS);

  function tick() {
    if (!ticking) { ticking = true; poll(); }
  }
})();
