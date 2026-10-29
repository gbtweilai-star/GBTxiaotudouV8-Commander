/* GBT小土豆V8 · 触手接管器（每页共用，唯一一份）
 *
 * 主人令（2026-10-21）：「每一页都要触手覆盖每一个代码啊，你以为就双向绑定就好了啊！」
 * 主人令（2026-10-26）：「使用量化APP和权重触手双向绑定触手覆盖每一页，
 *   每一页和所有页面互通按需激活，本地内存足够了」
 *
 * 这个文件干的事：**页面上每一个可交互点，点击/变更时都必须经触手（能力位）**，不许有"死控件"。
 *   ① 优先用元素自带的 `data-cap` / `data-op`；
 *   ② 没有就走**只读兜底** `health`（壳侧白名单只放只读能力位；越界一律被门拒，回执原话带回来）；
 *   ③ 每次调用都弹一条小回执（ok / 被拒原因 / 上游原话），**不许静默**；
 *   ④ 调完给元素盖 `data-tentacle="1"`，让判据能看见"这个代码点被触手接管了"。
 *
 * 2026-10-26 扩展：从"每页孤立接管控件"升级为"每页是触手网格的一个节点"：
 *   ⑤ **跨页唤起**（pageSummon）：页 A 让页 B 激活某能力位 —— 不只是"页 B 打开"，
 *      而是"页 B 以指定的能力位身份参与当前任务"。唤起方与被唤起方都会收到回执。
 *   ⑥ **跨页消息**（pageMessage）：给指定页发一条消息触发该页的动作 ——
 *      页面间不再只靠 showWindow/panelGoto 跳转，能直接"派活"。
 *   ⑦ **页面触手状态**（pageState）：查某页（或所有页）当前激活了哪些触手 ——
 *      每页在可见时自动注册自己，隐藏时自动注销（按需激活，不常驻）。
 *   ⑧ **按需激活/停用**：页面 visibilitychange 时自动连/断触手 ——
 *      不让隐藏页占着能力位不放（本地内存虽够，但"按需"= 不需要时不占）。
 *
 * 2026-10-26 二次扩展：**真正双向**（主人令里的"双向绑定"不是单向派活就算完）：
 *   ⑨ **请求-响应配对**（reqId + pending 表）：派活方能 await 目标页的结果，
 *      超时如实 reject，不许无限挂着。
 *   ⑩ **自动回执**：`onPageMessage(handler)` 的 handler 返回值**自动**回给发起页 ——
 *      目标页不需要自己记"我从谁那儿来"。返回 undefined = 这页不回话（合法的"读完就算"）。
 *   ⑪ **显式回执**（pageReply）：handler 里要异步干活时，可以自己拿 reqId 回。
 *
 * 2026-10-26 三次扩展：**把"必须回答"下沉到这里**（实测：26 页里 0 页注册 handler）：
 *   ⑫ **内置应答器**（selfDescribe）：所有业务 handler 都沉默时，由接管器回一段
 *      **只读自述**（我是谁/活没活着/接管了多少控件）。带 summon 而本页没实现 ⇒
 *      **如实答 `unsupported:true`**，绝不假装干过。⇒ 任何页都能被问到、都必须回答，
 *      "每页与所有页互通"才不是一句口号。（它排**最后**兜底，不许顶掉页面自己的 handler。）
 *   ⑬ **向所有页广播**（pageBroadcast）：`pageState()` 取名册 → 逐页 `pageMessage`；
 *      `activeOnly:true` 只叫醒活着的页 —— 这就是"按需激活"在跨页这一侧的落地。
 *
 * 三条纪律（不变）：
 *   · 一切走唯一门：只调 `window.gbtW3.cap(...)`（壳里转成 run_task），不自己拼后端；
 *   · 无桥（浏览器直开）时**如实说**"无桥"，不假装调用成功；
 *   · 不管成没成，都要把原因写出来 —— 安静≠坏了≠被拒。
 */
(function () {
  if (window.__GBT_TENTACLE_KIT__) return;
  window.__GBT_TENTACLE_KIT__ = true;

  var SEL = 'button,[data-action],select,input,[role="button"],a[href^="#"]';
  var bound = 0, calls = 0;

  function toast(msg, color) {
    if (!document.body) return;
    var t = document.getElementById("gbt-tentacle-toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "gbt-tentacle-toast";
      t.setAttribute("data-kind", "tentacle-toast");
      t.style.cssText = "position:fixed;left:10px;bottom:44px;z-index:2147483001;max-width:min(560px,80vw);" +
        "font:12px/1.5 ui-monospace,Consolas,monospace;padding:4px 10px;border-radius:8px;" +
        "border:1px solid rgba(232,236,248,.18);background:rgba(7,10,26,.9);color:#E8ECF8;" +
        "opacity:0;transition:opacity .15s;white-space:pre-wrap;pointer-events:none";
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.color = color || "#E8ECF8";
    t.style.borderColor = color || "rgba(232,236,248,.18)";
    t.style.opacity = "1";
    clearTimeout(t.__h);
    t.__h = setTimeout(function () { t.style.opacity = "0"; }, 2600);
  }

  function labelOf(el) {
    var s = (el.getAttribute && (el.getAttribute("data-action") || el.getAttribute("aria-label")
      || el.getAttribute("id") || el.getAttribute("title"))) || "";
    s = s || (el.textContent || "").trim().slice(0, 18) || el.tagName.toLowerCase();
    return s.replace(/\s+/g, " ").slice(0, 24);
  }

  function call(el) {
    var kind = (el.getAttribute && el.getAttribute("data-cap")) || "health";
    var op = (el.getAttribute && el.getAttribute("data-op")) || "status";
    var api = window.gbtW3;
    calls++;
    if (!api || typeof api.cap !== "function") {
      toast("⚠ 无桥 · 浏览器直开 ⇒ 「" + labelOf(el) + "」没跑触手（" + kind + "." + op + "）", "#9AA4C4");
      return;
    }
    var p;
    try { p = api.cap({ kind: kind, op: op }); } catch (e) { p = Promise.reject(e); }
    Promise.resolve(p).then(function (r) {
      var ok = r && (r.ok === true || (r.result && r.result.status === "ok"));
      var why = r && (r.error || (r.missing_scopes && ("缺授权 " + r.missing_scopes))
        || r.why || (r.result && r.result.error));
      el.setAttribute("data-tentacle", "1");
      toast((ok ? "✓ 触手 " : "✗ 触手 ") + kind + "." + op + " ← 「" + labelOf(el) + "」"
        + (why ? " · 原因：" + String(why).slice(0, 120) : ""), ok ? "#22C55E" : "#EF4444");
    }).catch(function (e) {
      toast("✗ 触手调用抛错 " + kind + "." + op + " ⇒ " + String(e && e.message || e).slice(0, 120), "#EF4444");
    });
  }

  function bind() {
    var els = document.querySelectorAll(SEL);
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el.__tentacleBound) continue;
      el.__tentacleBound = true;
      bound++;
      if (el.tagName === "SELECT" || el.tagName === "INPUT") {
        el.addEventListener("change", function (e) { call(e.currentTarget); });
      } else {
        el.addEventListener("click", function (e) { call(e.currentTarget); });
      }
    }
    /* 🔴 页面固定（主人令 2026-10-27：「把所有页面固定好，不能再出现跳转页面」）：
       `[data-goto]` 元素**只许开窗、不许跳转** —— 点击走 `gbtW3.showWindow`（壳里唯一的
       开窗口，只认注册表里已有的窗 id），**当前窗的 URL 一个字节不动**。
       为什么不做成"留着 href 让壳去拦"：壳的 `will-navigate` 确实会拦下，但那是一次
       **先发起再撤回**的跳转 —— 页面会闪、历史栈会脏；静态上压根没有 href 才叫真固定。
       为什么写在本文件：本文件是每页共用的接管器，跨页意图是它的本职。页页各写一段
       = 二十几份实现，改一处其余不动（本仓最贵的教训）。 */
    var gos = document.querySelectorAll("[data-goto]");
    for (var j = 0; j < gos.length; j++) {
      var g = gos[j];
      if (g.__gotoBound) continue;
      g.__gotoBound = true;
      g.addEventListener("click", function (e) {
        if (e && e.preventDefault) e.preventDefault();
        var id = this.getAttribute("data-goto");
        var bridge = window.gbtW3;
        if (!bridge || typeof bridge.showWindow !== "function") {
          toast("不在桌面壳里（没有开窗口）—— 点不动是正常的", "#f5b041");
          return;
        }
        Promise.resolve(bridge.showWindow({ id: id })).then(function (r) {
          if (!r || r.ok !== true) toast("开窗没成功：" + id, "#EF4444");
        }, function (e2) {
          toast("开窗抛错：" + String((e2 && e2.message) || e2).slice(0, 100), "#EF4444");
        });
      });
    }
    // 页内动态新增的控件也要接管（简单 observer）
    if (window.MutationObserver) {
      var mo = new MutationObserver(function () { bind(); });
      mo.observe(document.body || document.documentElement, { childList: true, subtree: true });
    }
  }

  /* ── 2026-10-26 双向协议的内核：请求-响应配对 ──
   *   为什么必须配对：单向 pageMessage 只能"派活"，发起方永远不知道目标页做没做、
   *   做成什么样。"双向绑定"要求**结果必须回到发起方**，且**不许无限等**。
   *
   *   协议（消息里只多两个字段，IPC 侧原样透传、不解析）：
   *     请求：{ reqId: "panel#3", summon?: "tentacle.see", from: "panel", ... }
   *     回执：{ replyTo: "panel#3", from: "eye", result: {...} }   ← 由 replyTo 认配对
   *   · reqId 自带发起页前缀（`本页id#序号`）⇒ 回执路由不需要额外登记表；
   *   · 超时默认 8s（跨页唤起要等目标窗建起来，给足）；到点 reject 并写明"没回话"；
   *   · 页面卸载时清空 pending（否则关掉的页会把 promise 永远吊着）。 */
  var __pending = {};
  var __reqSeq = 0;
  var REPLY_TIMEOUT_MS = 8000;

  function myPageId() {
    var el = document.documentElement;
    return (el && el.getAttribute("data-page-id")) || "unknown";
  }

  function nextReqId() {
    __reqSeq++;
    return myPageId() + "#" + __reqSeq;
  }

  function settleReply(replyTo, result, error) {
    var slot = __pending[replyTo];
    if (!slot) return false;              // 没人等这条回执（或已超时）——丢掉，不算错
    delete __pending[replyTo];
    clearTimeout(slot.timer);
    if (error) slot.reject(error); else slot.resolve(result);
    return true;
  }

  /* ── 消息分发（**常驻**，与「页面有没有注册业务 handler」无关）──
   *   🔴 为什么必须常驻：回执是**发起方**在等的东西。如果只在页面主动调
   *   `onPageMessage()` 时才挂监听，那一个只想"派活、不想接活"的页面
   *   （典型：面板 → 眼睛）发起 awaitReply 后**永远收不到回执**，只能干等超时。
   *   ⇒ 初始化时就挂一个内部监听器：回执走 settleReply（总要有人接），
   *     请求才分发给业务 handler。业务 handler 只关心"别人让我干什么"。 */
  var __handlers = [];
  var __listening = false;

  /* ── 内置应答器：**只读自述**，不替页面干活 ──
   *
   * 🔴 为什么必须有（2026-10-26 实测缺口，不是推测）：
   *   管子全铺好了（主进程 `w3:page-message`/`w3:page-state` 都在、preload 四个口都注册、
   *   本文件 API 全暴露），但**全仓 26 个页面里，注册 onPageMessage 的 = 0、调 pageSummon 的 = 0**。
   *   ⇒ 任何页 `pageMessage(..., {awaitReply:true})` 必然干等 8 秒超时。主人令里的
   *   「每一页和所有页面互通」当时是**断的**，而且断得没有任何报错。
   *   修法不是给 26 个页面各抄一段 handler（抄 26 遍 = 必漏 = 本仓"两处判据不一致"的老病），
   *   而是把"能被问到、必须回答"这件事下沉到**唯一这一份**接管器里。
   *
   * 它回答什么、不回答什么（边界要写死，否则就成了"假装干了活"）：
   *   · 我是谁（pageTitle/路径）、我活没活着（document.hidden）、我接管了多少控件；
   *   · 认不出/没实现的 summon ⇒ **如实说"本页没有为该能力位注册 handler"**。
   * 这样发起方分得清三种情况 —— 这正是本仓"安静≠坏了≠被拒"的同一套口径：
   *     ① 页不通（超时 / no_bridge）
   *     ② 页通了，但这页不会干这活（ok:false + unsupported:true）← 本应答器
   *     ③ 页通了，也确实干了（页面自己 onPageMessage 的返回值） */
  function selfDescribe(msg) {
    var el = document.documentElement;
    var summon = (msg && msg.summon) || null;
    return {
      ok: !summon,                     /* 带 summon 就说明"这活我没接"，不许报 ok */
      page: myPageId(),
      title: String(document.title || "").slice(0, 80),
      active: !document.hidden,
      tentacle: { bound: bound, calls: calls,
                  active: el ? el.getAttribute("data-tentacle-active") : null },
      summon: summon,
      unsupported: !!summon,
      reason: summon
        ? ("本页可达，但没有为 " + summon + " 注册 handler（要它干活得在页面里调 onPageMessage）")
        : "本页可达（只读自述）",
      at: Date.now()
    };
  }

  function dispatch(payload) {
    /* 壳侧透传形状：{to, from, msg, at}；消息本体可能被摊平也可能在 msg 里。 */
    var msg = (payload && payload.msg) || payload || {};
    /* ① 回执分支：认 replyTo，配给 pending，**不惊动业务 handler**。 */
    if (msg.replyTo) { settleReply(msg.replyTo, msg.result); return; }
    /* ② 请求分支：分发给业务 handler；**第一个**返回非 undefined 的负责回执。 */
    var replied = false;
    for (var i = 0; i < __handlers.length; i++) {
      var out;
      try { out = __handlers[i](msg); } catch (e) {
        if (!replied && msg.reqId && msg.from) {
          replied = true;
          replyTo(msg.from, msg.reqId, { ok: false, error: String(e && e.message || e).slice(0, 200) });
        }
        continue;
      }
      if (out === undefined || replied || !msg.reqId || !msg.from) continue;
      replied = true;
      Promise.resolve(out).then(function (result) {
        replyTo(msg.from, msg.reqId, result);
      }, function (e) {
        replyTo(msg.from, msg.reqId, { ok: false, error: String(e && e.message || e).slice(0, 200) });
      });
    }
    /* ③ 兜底自述分支：所有业务 handler 都没认领 ⇒ 由内置应答器回话。
     *
     * 🔴 为什么必须放在**循环之后**，而不是把内置应答器当第一个 handler 注册：
     *   dispatch 的规则是"**第一个返回非 undefined 的 handler** 负责回执"。
     *   内置应答器若排前面，它永远先返回（它总能说话）⇒ 页面自己写的 handler
     *   **永远轮不到回执** —— 兜底会把正主顶掉，变成"每页都说我不会"。
     *   ⇒ 只在前面的都沉默时才由它兜底：正主优先，兜底不漏。 */
    if (!replied && msg.reqId && msg.from) {
      replyTo(msg.from, msg.reqId, selfDescribe(msg));
    }
  }

  function replyTo(toPage, reqId, result) {
    var api = window.gbtW3;
    if (!api || typeof api.pageMessage !== "function") return null;
    try {
      return api.pageMessage({ to: toPage, from: myPageId(),
                               msg: { replyTo: reqId, from: myPageId(), result: result, at: Date.now() } });
    } catch (e) { return null; }   // 发不出去时发起方会超时 —— 那边有兜底，这里不重复报
  }

  function ensureListener() {
    if (__listening) return;
    var api = window.gbtW3;
    if (!api || typeof api.onPageMessage !== "function") return;
    api.onPageMessage(dispatch);
    __listening = true;
  }

  window.GBT_TENTACLE = {
    cap: function (kind, op, args) {
      var api = window.gbtW3;
      if (!api || typeof api.cap !== "function") {
        return Promise.resolve({ ok: false, status: "no_bridge",
                                 reason: "不在桌面壳里（无 window.gbtW3），页面无法调能力位" });
      }
      return Promise.resolve(api.cap(Object.assign({ kind: kind, op: op || "status" }, args || {})));
    },
    state: function () {
      return { bound: bound, calls: calls, online: !!(window.gbtW3 && window.gbtW3.cap) };
    },
    /* ── 2026-10-26 跨页触手网格 ── */

    /* 跨页唤起：让目标页以指定的能力位身份参与当前任务，**并等它回话**。
     *   pageId = 注册表里的窗 id（如 "eye"/"logbook"/"capabilities"…）
     *   kind = 能力位域名（如 "tentacle"/"llm"/"vision"…）
     *   op = 操作名（如 "see"/"status"…）
     *   三步：① 让壳把目标窗显示出来（showWindow）
     *         ② 发一条带 reqId 的 pageMessage（{summon, from, reqId}）
     *         ③ **等目标页回执**（超时 8s 如实 reject，不无限挂）
     *   ⚠️ 这条路**不替目标页调能力位**——只是"唤起 + 派活"；执行权在目标页自己。
     *   目标页若用 `onPageMessage(handler)` 且 handler 有返回值，回执**自动**回来；
     *   返回 undefined = 这页选择不回话，此时本函数在超时后 reject。 */
    pageSummon: function (pageId, kind, op, opts) {
      var api = window.gbtW3;
      if (!api || typeof api.showWindow !== "function") {
        return Promise.resolve({ ok: false, reason: "无桥，跨页唤起走不了" });
      }
      var me = myPageId();
      var summon = (kind || "health") + "." + (op || "status");
      return Promise.resolve(api.showWindow({ id: pageId })).then(function (r) {
        if (!r || !r.ok) return { ok: false, reason: "目标页打不开：" + ((r && r.error) || "?") };
        if (typeof api.pageMessage !== "function") {
          return { ok: true, note: "唤起了但 pageMessage 口不在（旧壳？）", id: pageId };
        }
        return this.pageMessage(pageId, { summon: summon, from: me },
                                { awaitReply: true, timeout: (opts && opts.timeout) });
      }.bind(this));
    },
    /* 跨页消息：给指定页发一条消息，触发该页的 onPageMessage 回调。
     *   opts.awaitReply = true  ⇒ 返回一个**等回执**的 promise（带 reqId）；
     *   opts.timeout    = 毫秒   ⇒ 等多久（默认 8000）。
     *   不等回执时就是单向"派活"，返回发送回执 {ok, delivered}。 */
    pageMessage: function (pageId, msg, opts) {
      var api = window.gbtW3;
      if (!api || typeof api.pageMessage !== "function") {
        return Promise.resolve({ ok: false, reason: "无桥或旧壳，跨页消息走不了" });
      }
      var me = myPageId();
      var body = msg || {};
      var wantReply = !!(opts && opts.awaitReply);
      if (wantReply) body.reqId = body.reqId || nextReqId();
      body.from = body.from || me;
      body.at = Date.now();

      var sent = Promise.resolve(api.pageMessage({ to: pageId, from: me, msg: body }));
      if (!wantReply) return sent;

      /* 登记 pending：回执回来时由 settleReply 认 replyTo 配对。 */
      var reqId = body.reqId;
      return new Promise(function (resolve, reject) {
        var timer = setTimeout(function () {
          if (__pending[reqId]) {
            delete __pending[reqId];
            reject({ ok: false, timeout: true, reqId: reqId,
                     reason: "目标页 " + pageId + " 在超时内没回话（它可能没装 onPageMessage）" });
          }
        }, (opts && opts.timeout) || REPLY_TIMEOUT_MS);
        __pending[reqId] = { resolve: resolve, reject: reject, timer: timer, to: pageId };
        /* 发送本身失败要立刻失败，不许干等超时。 */
        sent.then(function (r) {
          if (!r || r.ok === false) {
            delete __pending[reqId];
            clearTimeout(timer);
            reject(r || { ok: false, reason: "发送失败" });
          }
        }, function (e) {
          if (__pending[reqId]) {
            delete __pending[reqId];
            clearTimeout(timer);
            reject({ ok: false, reason: String(e && e.message || e) });
          }
        });
      });
    },
    /* 显式回执：目标页异步处理完，把结果送回发起页。
     *   一般不用自己调 —— `onPageMessage(handler)` 的返回值会自动回执；
     *   只有"我要先回话、后面再补结果"的分段场景才显式调它。 */
    pageReply: function (toPage, reqId, result) {
      var api = window.gbtW3;
      if (!api || typeof api.pageMessage !== "function") {
        return Promise.resolve({ ok: false, reason: "无桥或旧壳，回执发不出去" });
      }
      if (!reqId) return Promise.resolve({ ok: false, reason: "没有 reqId，回执认不出配给谁" });
      return Promise.resolve(replyTo(toPage, reqId, result) || { ok: true });
    },
    /* 查某页（或所有页）的触手激活状态。
     *   pageId 省略 = 查所有页；返回 {pages: {id: {visible, active, caps:[...]}}}。 */
    pageState: function (pageId) {
      var api = window.gbtW3;
      if (!api || typeof api.pageState !== "function") {
        return Promise.resolve({ ok: false, reason: "无桥或旧壳，页面状态查不了" });
      }
      return Promise.resolve(api.pageState(pageId ? { id: pageId } : {}));
    },
    /* 向**所有页**广播（主人令「每一页和所有页面互通」的现成入口）。
     *   不用新开 IPC：两步都是已有零件 —— `pageState()` 取名单（主进程只读快照）
     *   → 逐页 `pageMessage`。既不扩大权限面，也不绕过白名单（只发注册表里真有的 id）。
     *   opts.activeOnly = true ⇒ **只发给活着的页**（`data-tentacle-active="1"`），
     *     这正是"按需激活"：不叫醒没在看的页、不为它占能力位。
     *   opts.awaitReply  = true ⇒ 逐页等回执（默认只发不等，避免 8s×N 的长等待）。
     *   返回逐页如实记账：{ok, sent:[{to, ok, result|reason}], skipped:[页id…]}，
     *   **不许把发失败的算成发成功的**。 */
    pageBroadcast: function (msg, opts) {
      var K = window.GBT_TENTACLE;
      var o = opts || {};
      return Promise.resolve(K.pageState()).then(function (st) {
        if (!st || st.ok === false) {
          return { ok: false, reason: "拿不到页面名单：" + ((st && st.reason) || "?") };
        }
        var pages = st.pages || {};
        var me = myPageId();
        var all = Object.keys(pages).filter(function (id) { return id && id !== me; });
        var send = o.activeOnly
          ? all.filter(function (id) { return pages[id] && pages[id].active === true; })
          : all;
        var skipped = all.filter(function (id) { return send.indexOf(id) < 0; });
        if (!send.length) {
          return { ok: true, sent: [], skipped: skipped,
                   note: "没有可发的页（" + (o.activeOnly ? "按需模式下只有活着的页算数" : "名单为空") + "）" };
        }
        return Promise.all(send.map(function (id) {
          var body = {};
          for (var k in (msg || {})) body[k] = msg[k];      /* 每页一份副本，别互相污染 */
          return Promise.resolve(K.pageMessage(id, body,
            { awaitReply: !!o.awaitReply, timeout: o.timeout }))
            .then(function (r) {
              return { to: id, ok: !!(r && r.ok !== false), result: r };
            }, function (e) {
              return { to: id, ok: false, reason: (e && (e.reason || e.message)) || String(e) };
            });
        })).then(function (rows) {
          return { ok: rows.every(function (x) { return x.ok; }), sent: rows, skipped: skipped };
        });
      });
    },
    /* 监听跨页消息（页被唤起 / 被派活时回调）。
     *   handler 收到 {summon?, from, reqId?, ...}；
     *   **handler 有返回值就自动回执给发起页**（这是双向的默认路径）：
     *     · 返回 Promise ⇒ 等它 resolve 再回执（异步干活也对）；
     *     · 返回 undefined ⇒ 不回话（合法的"读完就算"）；
     *     · 收到的是回执（有 replyTo）⇒ 根本不进 handler，内部监听器直接配给 pending。
     *   可以注册多个 handler；某条请求由**第一个**返回非 undefined 的 handler 负责回执。
     *   返回一个卸载函数（调它就把这个 handler 摘掉）。 */
    onPageMessage: function (handler) {
      if (typeof handler !== "function") return function () {};
      ensureListener();               // 业务 handler 与回执监听解耦：先保证回执有人接
      __handlers.push(handler);
      return function () {
        var i = __handlers.indexOf(handler);
        if (i >= 0) __handlers.splice(i, 1);
      };
    },
    /* 本页身份（诊断用）：`data-page-id` 没声明过就是 "unknown" —— 这时候跨页派活
     *   的回执路由会失准（from 认不出是谁），所以**每页都必须声明 data-page-id**。 */
    me: function () { return myPageId(); },
    /* 还挂着多少个待回执请求（诊断用；页面卸载时应为 0）。 */
    pending: function () { return Object.keys(__pending).length; }
  };

  /* ── 2026-10-26 按需激活：页面可见时连触手，隐藏时断开 ──
   *   本地内存虽够，但"按需"= 不需要时不占。页面 visibilitychange 时：
   *   · 可见 → 在 documentElement 上盖 data-tentacle-active="1"（判据能看见"这页活着"）
   *   · 隐藏 → 盖 data-tentacle-active="0"（不删属性，让判据区分"从没活过"和"曾活过但现在没"）
   *   不自动调能力位——"连"只意味着"我在听"，不意味着"我要干活"（干活走 pageSummon / 控件点击）。 */
  /* 🔴 **窗口真可见性以壳为准**（2026-10-27 实测）：页面自判不可靠 ——
     Electron 对 `show:false` 的窗，`document.hidden` 仍可能是 false（尤其离屏渲染时）。
     后果很具体：隐藏窗会向主进程上报 `active:true`，`pageState()` 于是回答"这页活着"——
     那是**把不知道说成了知道**。⇒ 有壳信号就用壳的（推 + 拉都认），没有才退回 document.hidden。
     默认 true：拿不到任何信号时按"可见"处理（宁可多报活，不许把页面冻成僵尸）。 */
  var WIN_VISIBLE = true;
  function syncActive() {
    var el = document.documentElement;
    if (!el) return;
    /* 两个信号都要认，**任一判隐藏即隐藏**：
       · 壳的 `win.isVisible()`（权威：页面自判在 Electron 里不可靠）；
       · `document.hidden`（浏览器直开时唯一信号；壳里它可能永远 false，那就以壳为准）。
       只认壳 ⇒ 浏览器里按需激活失效；只认 document ⇒ 壳里隐藏窗谎报"活着"。 */
    var visible = WIN_VISIBLE && !document.hidden;
    el.setAttribute("data-tentacle-active", visible ? "1" : "0");
    /* 🔴 2026-10-26 加：**主动上报给壳**（不只是盖个属性）。
       为什么必须报：壳的 `pageState()` 要能回答「哪页现在是活的」，而主进程去读页面 DOM
       是注入行为（守卫 B4 只许注入收口在 deepseek_loop.cjs）。
       ⇒ 改由页面自己说 —— 这也让判据更硬：状态是**页面真的发了**，不是主进程猜的。
       无桥（浏览器直开）时静默跳过：没壳就没有"上报"这回事，不是错误。 */
    var api = window.gbtW3;
    if (api && typeof api.reportActive === "function") {
      try { api.reportActive({ pageId: myPageId(), active: visible }); }
      catch (e) { /* 壳不在/口没就位：不上报，也不假装报过 */ }
    }
  }
  /* 壳的真可见性：**推 + 拉**都要（推送有竞态 —— 本文件加载常晚于壳那一次推送，
     只订阅会永远以为"可见"；2026-10-27 在铬注入上就是这么塌的）。 */
  (function bindWinVisibility() {
    var api = window.gbtW3;
    if (!api) return;
    if (typeof api.onWinVisibility === "function") {
      try {
        api.onWinVisibility(function (m) {
          var v = !!(m && m.visible === true);
          if (v === WIN_VISIBLE) return;
          WIN_VISIBLE = v;
          syncActive();
        });
      } catch (e) { /* 订阅失败：保持默认"可见" */ }
    }
    if (typeof api.winVisible === "function") {
      try {
        Promise.resolve(api.winVisible()).then(function (r) {
          if (!r || !r.ok || !r.data) return;
          var v = r.data.visible === true;
          if (v === WIN_VISIBLE) return;
          WIN_VISIBLE = v;
          syncActive();
        }).catch(function () { /* 问不到就按默认"可见" */ });
      } catch (e) { /* 同上 */ }
    }
  }());
  if (document.addEventListener) {
    /* 浏览器直开（无壳）时才靠它；壳里以壳信号为准，这条只是兜底重算一次。 */
    document.addEventListener("visibilitychange", syncActive, false);
  }
  syncActive();

  /* 🔴 一进来就挂回执监听（不等页面主动注册）—— 否则"只想派活、不想接活"的页面
   * 发起 awaitReply 后永远收不到回执（这条是本次单测 ③⑦ 抓出来的真缺陷）。 */
  ensureListener();

  /* ── 页面心跳（2026-10-27）──────────────────────────────────────────────
   * 干什么：每 2s 告诉壳「我还在跑脚本」+「这次比本应时刻晚了多少」，壳记时间戳；
   *         超出**该窗自己的预算**仍未报 ⇒ 壳强崩重载该窗。
   *
   * 为什么必须页面自己报（实测两条，都不是推测）：
   *   · `shell/hang-probe.cjs` 的靶子页把主线程忙等钉死 ⇒ 主进程发过去的脚本调用
   *     **永远不 settle**（2000ms 就超时），而且 **`unresponsive` 一次都不触发**
   *     （Chromium 那个事件盯的是"输入不 ack"，不管脚本队列被堵）；
   *   · 四次真启动探针同样 0 次触发。
   *   ⇒ 壳侧没有任何可靠手段"探"出来，只有页面自己知道。
   *
   * 节流与不打搅：`invoke` 是异步的、失败也不抛到这里；页面被隐藏时也照报
   * （隐藏≠卡死，停报会让看门狗误判）。无桥（浏览器直开）时静默跳过。
   *
   * 🔴 不变式（仍然是它，只是"阈值"换了形态）：
   *   周期必须**显著短于预算下限**，否则每扇窗都会在两次心跳之间被判死。
   *   实测踩过：心跳 8s、阈值 6s ⇒ 17 扇窗**同时**强崩重载（一次跑出 81 条失败留痕）。
   *   现在：2s 一报；看门狗侧强制 `预算下限 ≥ 3×周期`（下限默认 6000ms），
   *        并在此之上按**该窗实测迟到**抬预算，上限 60s（算式见 shell/beat-budget.cjs）。
   *   ⚠️ 别把"默认 10s"这类常数再写回注释里 —— 它已经不是一个常数了；
   *      要改就改 beat-budget.cjs，改完跑 `npm test`（那儿有纯函数判据 + 负对照）。
   * 代价：17 页 × 0.5 次/秒 ≈ 8.5 条 IPC/秒，都是极小的本地调用。 */
  var BEAT_MS = 2000;
  /* 🔴 迟到自报（2026-10-27 第二次修，实测逼出来的）。
     事实：24 轮真启动里看门狗强崩了 **72 次**（平均每轮 3 次），而同期探活说
     主窗 23/24 次都回话 —— 也就是说它打的是"心跳迟到"，不是"死"。
     72 条超时读数中位 12.7s，38% 落在 10~12s，全都只是**刚过线一点**；
     重页（3D 主窗 / eye）在软件渲染下渲染帧本身占满主线程，2s 的定时器晚到十几秒
     是**正常表现**，不是故障。
     ⇒ 主进程原来拿一个我拍的常数当阈值，判不了一扇我从没量过抖动的窗。
       改成：页面把"这次比本应时刻晚了多少"报上去，看门狗按**它自己交出来的证据**抬预算
       （算式在 `shell/beat-budget.cjs`，纯函数、可单测）。
     注意：`__beatDue` 每次从"现在"重算，**不累积** —— 否则一次长停顿会让后续每拍都
     算成迟到，把阈值一路抬到上限、自愈就永远不触发了。 */
  var __beatDue = Date.now();
  function beat() {
    var api = window.gbtW3;
    if (!api || typeof api.pageBeat !== "function") return;   /* 浏览器直开：没有壳，不报 */
    var now = Date.now();
    var lag = now - __beatDue;
    __beatDue = now + BEAT_MS;
    try { api.pageBeat({ pageId: myPageId(), at: now, lag: lag > 0 ? lag : 0 }); }
    catch (e) { /* 壳不在就不报 */ }
  }
  beat();                                        /* 立刻报一次：别等到第一个周期 */
  var __beatTimer = setInterval(beat, BEAT_MS);
  if (window.addEventListener) {
    var stopBeat = function () { clearInterval(__beatTimer); };
    window.addEventListener("pagehide", stopBeat, false);
    window.addEventListener("beforeunload", stopBeat, false);
  }

  /* 页面卸载时把还在等的 pending 全部结算掉 —— 否则"发起方先被关掉"会把 promise
   * 永远吊着（内存泄漏 + 调用方以为还在进行）。理由写清，不静默丢。 */
  function flushPending() {
    var keys = Object.keys(__pending);
    for (var i = 0; i < keys.length; i++) {
      var slot = __pending[keys[i]];
      delete __pending[keys[i]];
      clearTimeout(slot.timer);
      slot.reject({ ok: false, reason: "发起页已卸载，回执不可能再到了", reqId: keys[i] });
    }
  }
  if (window.addEventListener) {
    window.addEventListener("pagehide", flushPending, false);
    window.addEventListener("beforeunload", flushPending, false);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
