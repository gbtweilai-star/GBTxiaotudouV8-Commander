/* 主脑语音对讲 · **页面生命周期绑定**（主人令 2026-09-23）
 *
 * 主人的原话：「就是她的独立页面，我没打开的时候她是关闭的，我打开页面就自动监听了，
 *              关闭她也跟着关闭，但是大脑后台是在运行的。」
 *
 * ⇒ 口径（写死，别改）：
 *    · **打开本页 = 开始监听 · 关掉本页 = 停止监听**。页面本身就是那个开关，
 *      所以这里**一个开关控件都没有**（主人明说「不需要开关」）。
 *    · 页面不在时**本页什么都不做**（大脑后台照常跑，那是宿主的事，不归这一页管）。
 *    · 本页 CSP 是 `connect-src 'none'` ⇒ **不能 fetch/XHR**。所以只有两条路：
 *        ① Electron 桥 `window.gbtW3.intercom(op, args)`（IPC 不受 CSP 管，这是原生机制）；
 *        ② 桥不在 ⇒ **如实报「宿主桥未提供对讲通道」**，绝不假装在听。
 *
 * 🔴 三条腿**分开报**（本仓铁律：安静 ≠ 坏了 ≠ 被门拒，三件事不许混成一句）：
 *      采集（麦克风设备有没有）
 *      离线识别（本机有没有该语言的识别器）
 *      出声（走门，缺 audio_output 就如实报缺 + 给出主人那一条命令）
 *
 * ⚠️ 宿主侧必须做的一件事（写在这里，免得忘）：**把监听会话绑到发起它的 webContents 上**
 *    （Electron：`event.sender.once('destroyed', stop)`）。只靠本页 `pagehide` 发一句 stop
 *    是不够的 —— 页面被强杀时那句话发不出去，麦克风就留在那儿开了。
 */
(function () {
  "use strict";

  var POLL_MS = 1500;
  var el = null, timer = null, started = false;

  function $(id) { return document.getElementById(id); }

  function bridge() {
    var b = window.gbtW3;
    return (b && typeof b.intercom === "function") ? b : null;
  }

  /* 三条腿各自一行：**有读数就写读数，没有就写"未取到"**，不写"—"糊过去 */
  function row(k, v, state) {
    var d = document.createElement("div");
    d.className = "iv-row" + (state ? " iv-" + state : "");
    var a = document.createElement("span");
    a.className = "iv-k";
    a.textContent = k;
    var b = document.createElement("span");
    b.className = "iv-v";
    b.textContent = v;
    d.appendChild(a);
    d.appendChild(b);
    return d;
  }

  function render(raw) {
    if (!el) return;
    var kids = [];
    var b = bridge();

    /* ── 收件箱：**先渲染，且与桥无关** ─────────────────────────────────
       🔴 第 14 轮修的一个设计错：这一行原来放在"桥存在"的分支里 ⇒
          裸浏览器（无 preload）**永远看不到它**，而我恰恰是在裸浏览器里做验收的。
          可它读的是 `brain-data.js` 里的 `voice_inbox`（**数据**），
          跟"宿主桥在不在"根本无关 ⇒ 提到桥判断之前，两个环境都看得到。 */
    var vi = (globalThis.GBT_BRAIN || {}).voice_inbox;
    if (vi && vi.exists && (vi.last || []).length) {
      var lastRec = vi.last[vi.last.length - 1];
      kids.push(row("收件箱", "共 " + vi.n + " 条 · 最近（"
        + String(lastRec.at || "") + "）：" + String(lastRec.text || "").slice(0, 34), "ok"));
    } else if (vi && vi.exists === false) {
      kids.push(row("收件箱", "还没有听到过（收件箱文件还没生成）", "wait"));
    } else if (vi && vi.error) {
      kids.push(row("收件箱", "读不到：" + String(vi.error).slice(0, 40), "bad"));
    } else {
      kids.push(row("收件箱", "数据件里没有 voice_inbox 块", "wait"));
    }

    if (!b) {
      /* 桥不在：这是"宿主侧那一段还没上线"，不是"坏" —— 两件事分开说 */
      kids.push(row("对讲通道", "宿主桥未提供 intercom（等宿主侧那一段上线）", "wait"));
      kids.push(row("本页做法", "打开本页即请求开始监听 · 关掉即请求停止 · 无开关", null));
      el.replaceChildren.apply(el, kids);
      return;
    }

    /* 🔴 **真壳取证抓出来的错**（第 58 轮）：主进程回的是**信封** `{ok, data:{…}}`，
       我第一版直接当内层用 ⇒ 真壳里页面写"未在听 / 未取到"，而桥其实好着。
       ⇒ 统一拆一封（有 `data` 就用 `data`）。静态检查发现不了这种错，只有真壳能照出来。 */
    var st = (raw && raw.data) ? raw.data : raw;
    var lg = (st && st.status && st.status.legs) || null;

    kids.push(row("监听", (st && st.listening)
      ? ("在听（第 " + (st.rounds || 0) + " 轮" + ((st.heard || 0) ? " · 听到 " + st.heard + " 次" : "") + "）")
      : "未在听", (st && st.listening) ? "ok" : "wait"));

    /* 采集那条腿：**只有真听过一轮才知道**（设备在不在是运行时事实）⇒ 从 last 取；
       没轮次就如实写"还没听过一轮"，不编。 */
    var cap = "还没听过一轮", capState = "wait";
    if (st && st.last) {
      var s = st.last.status;
      if (s === "no_input") { cap = "没有可用录音设备"; capState = "bad"; }
      else if (s === "heard") { cap = "听到：" + String(st.last.text || "").slice(0, 30); capState = "ok"; }
      else if (s === "quiet") { cap = "安静（没听到，不是坏）"; capState = "wait"; }
      else { cap = String(s || "未取到"); }
    } else if (lg && lg.wavein_devices === 0) {
      /* 🔴 第 59 轮修（**一条假绿**）：没跑过一轮时，旧版只说"还没听过一轮"，
         页面看着像"还没轮到"，其实本机录音端点在场的 **0** 个 ⇒ **根本没得听**。
         现读判据来自 `voice·status` 的 `wavein_devices`（winmm 映射器能看见几个输入设备）。
         ⚠️ 这与"插不插麦克风"无关：硬件引脚在、端点没被激活，也一样是 0。 */
      cap = "没有可用录音端点（winmm 数 0，与插不插麦无关）";
      capState = "bad";
    }
    kids.push(row("采集", cap, capState));

    /* 离线识别：**识别器在位 ≠ 耳朵能听**。
       采集那格是死的时，这一格**不许标绿** —— 否则就是"识别器在、耳朵不在"的假绿。 */
    var rec = lg ? (lg.listen_local || "未取到") : "未取到";
    var recOk = !!(lg && /可用/.test(rec));
    var capDead = !!(lg && lg.wavein_devices === 0);
    kids.push(row("离线识别",
      capDead ? (rec + " —— 但采集那格是空的，现在听不到") : rec,
      capDead ? "bad" : (recOk ? "ok" : "bad")));

    var gate = (lg && lg.tts_gate) ? lg.tts_gate : null;
    var out = !lg ? "未取到"
                 : (gate && gate.denied)
                   ? ("缺 " + ((gate.missing_scopes || []).join("、") || "授权") + "（一次性消耗）")
                   : "授权在位";
    kids.push(row("出声", out, (gate && gate.denied) ? "wait" : (lg ? "ok" : "bad")));

    if (gate && gate.how_to_grant && gate.how_to_grant[0]) {
      kids.push(row("授权命令",
        String(gate.how_to_grant[0]).replace("终端运行: ", "").slice(0, 74), "wait"));
    }
    kids.push(row("口径", "打开本页即监听 · 关掉本页即停 · 页面不在时本页不做任何事", null));
    el.replaceChildren.apply(el, kids);
  }

  function call(op, args) {
    var b = bridge();
    if (!b) return Promise.resolve(null);
    try {
      return Promise.resolve(b.intercom(op, args || {}));
    } catch (e) {
      return Promise.resolve({ ok: false, error: String(e && e.message ? e.message : e) });
    }
  }

  function poll() {
    call("state").then(render, function () { render(null); });
  }

  function start() {
    if (started) return;
    started = true;
    /* 打开页面就**自动**开始 —— 不弹确认、不要按下任何东西 */
    call("start").then(function (r) {
      render(r && r.ok === false && r.state ? r.state : r);
      poll();
      timer = setInterval(poll, POLL_MS);
    });
  }

  function stop() {
    if (!started) return;
    started = false;
    if (timer) { clearInterval(timer); timer = null; }
    /* 关页面时**主动说一句停**（宿主还会用 webContents.destroyed 兜一道，双保险） */
    call("stop");
  }

  function boot() {
    el = $("rail-voice");
    if (!el) return;
    var note = document.createElement("p");
    note.className = "rail-empty";
    note.textContent = "读数据中…";
    el.replaceChildren(note);

    start();
    window.addEventListener("pagehide", stop);
    window.addEventListener("beforeunload", stop);
    /* 页面被切到后台（最小化/换标签）**不停** —— 主人说的是"关闭"，不是"切走"。
       但要看得出它还在跑：把可见性写进读数。 */
    if (document.addEventListener) {
      document.addEventListener("visibilitychange", function () {
        if (!el) return;
        el.dataset.hidden = document.hidden ? "true" : "false";
      });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  /* 只读自述：验收要能**量**"页面这一半有没有起来"，不靠看图说"有" */
  window.__brainIntercom = {
    get started() { return started; },
    has_bridge: function () { return !!bridge(); },
    poll_ms: POLL_MS,
  };
})();
