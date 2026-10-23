/* GBT小土豆V8 · AI 朋友圈（独立窗 · W9）
 *
 * 只读：数据全部经 window.gbtW3.eigenflux() 从主进程拿（本机 EigenFlux 缓存）。
 * 本文件不含 fetch / fs / 任何写调用，也不发消息、不调 API、不拉 scope。
 * 空态一律写**理由**，不写占位数字（《反空壳律》：取不到就显示取不到 + 原因）。
 *
 * 卡片 DOM 由 ../ef_render.js 提供（与上帝视角窗口共用一份，免得两处对不上）。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var bridge = window.gbtW3 || null;

  function show(name) {
    var views = document.querySelectorAll(".ef-view");
    for (var i = 0; i < views.length; i++) views[i].removeAttribute("data-active");
    var tabs = document.querySelectorAll(".gbt-tab");
    for (var j = 0; j < tabs.length; j++) tabs[j].removeAttribute("data-active");
    var v = $("efview-" + name);
    if (v) v.setAttribute("data-active", "true");
    var t = document.querySelector('.gbt-tab[data-ef="' + name + '"]');
    if (t) t.setAttribute("data-active", "true");
  }

  function render(r) {
    var R = window.gbtEfRender;
    var state = $("ef-state");
    var counts = $("ef-counts");
    var source = $("ef-source");

    if (!R) {
      if (state) { state.dataset.state = "fault"; state.textContent = "渲染层缺失"; }
      if (source) source.textContent = "ef_render.js 没加载 —— 取不到就显示取不到";
      return;
    }

    var d = (r && r.ok) ? r.data : null;
    if (!d) {
      var why = "取不到：" + ((r && r.error) || "原因未报");
      if (state) { state.dataset.state = "gray"; state.textContent = "取不到"; }
      /* 失败路径必须把上一轮的计数与通道行一并清掉：不清就是拿**上一次**的数字
       * 冒充这一次的结果 —— 四条 list 都写着"取不到"，右下角却还在报"好友 3 · 动态 20"，
       * 自相矛盾，而且屏上没有任何东西提示那是旧的。 */
      if (counts) { counts.dataset.state = "gray"; counts.textContent = "取不到"; }
      if (source) source.textContent = "通道：本机只读（取不到）";
      R.empty($("ef-feed-list"), why);
      R.empty($("ef-friend-list"), why);
      R.empty($("ef-msg-list"), why);
      R.empty($("ef-profile-list"), why);
      return;
    }

    /* 🔴 声明数据新鲜度（2026-09-23 第 34 轮）：本窗**不是实时** —— 它读的是
       本机 EigenFlux 的**缓存文件**（`source.feed.file`），所以要报那个文件的
       `mtime`（实测形如 `2026-09-23T04:35:22.531Z`），**不是 `new Date()`**。
       拿加载时刻冒充数据时刻，就是把几小时前的动态说成现在的 —— 那正是假绿。
       拿不到 mtime 就**不声明**（铬会显示「数据 未声明」），不编一个。 */
    var _mt = d.source && d.source.feed && d.source.feed.mtime;
    if (_mt) window.GBT_DATA = { kind: "快照", at: _mt };

    if (state) {
      state.dataset.state = d.initialized ? "ok" : "gray";
      state.textContent = d.initialized ? "本机只读 · 已接" : "未初始化";
    }
    if (counts) {
      counts.dataset.state = "gray";
      /* 主进程没报计数时不许编 0、也不许让 d.counts.friends 抛 TypeError
         —— 那一抛会被下面的 .catch 接走，整页被打成"取不到：Cannot read properties…"，
         用户看到的是内部异常文本。没报就写"未报"（《反空壳律》）。 */
      counts.textContent = d.counts
        ? ("好友 " + d.counts.friends + " · 动态 " + d.counts.feed +
           " · 私信 " + d.counts.messages)
        : "计数未报";
    }
    if (source) {
      source.textContent = "通道：本机只读 " + d.home_label +
        (d.source && d.source.feed
          ? (" · 动态源 " + d.source.feed.file + "（" + (d.source.feed.mtime || "—") + "）")
          : "");
    }

    /* 空态理由必须按**本机的真实状态**分叉。原来「好友 / 私信」两条写死
     * 「没有好友记录 / 没有私信记录」：未初始化时（本机根本没有 EigenFlux）
     * 那句话把"没读到"说成了"量到是空的"，与主进程那句
     * 「是未初始化，不是空数据」（shell/main.cjs §13b）直接打架 —— 同一块屏，
     * 动态流说"未初始化"，好友页说"没有记录"。
     * issues 原来只挂在动态流上 ⇒ 站在「私信」页的人看不到「私信文件解析失败」，
     * 只看得到一句"没有私信记录"：**理由不在它该在的那一页**。
     * 正解是主进程给 issues 带上频道字段；在那之前先把理由铺到四页 ——
     * 宁可四页重复，不可一页隐瞒。 */
    var notInit = "未初始化：本机还没有 EigenFlux（是未初始化，不是空数据）";
    var feed = $("ef-feed-list");
    var friends = $("ef-friend-list");
    var msgs = $("ef-msg-list");
    var prof = $("ef-profile-list");

    R.list(feed, d.feed, R.item,
      d.initialized ? "动态流是空的（本机缓存里确实没有条目）" : notInit);
    R.list(friends, d.friends, R.friend, d.initialized ? "没有好友记录" : notInit);
    R.list(msgs, d.messages, R.message, d.initialized ? "没有私信记录" : notInit);
    if (prof) {
      if (d.profile) { prof.textContent = ""; prof.appendChild(R.profile(d.profile)); }
      else R.empty(prof, d.initialized ? "档案取不到：profile.json 没读到" : notInit);
    }
    R.issues(feed, d.issues);
    R.issues(friends, d.issues);
    R.issues(msgs, d.issues);
    R.issues(prof, d.issues);
  }

  function load() {
    if (!bridge || typeof bridge.eigenflux !== "function") {
      render({ ok: false, error: "没有接上宿主进程（gbtW3 未注入）—— 取不到" });
      return;
    }
    var p;
    try { p = bridge.eigenflux(); }
    catch (err) { render({ ok: false, error: String(err) }); return; }
    Promise.resolve(p).then(render).catch(function (err) {
      render({ ok: false, error: String((err && err.message) || err) });
    });
  }

  function bind() {
    var tabs = document.querySelectorAll(".gbt-tab");
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener("click", function (ev) { show(ev.currentTarget.dataset.ef); });
    }
    var btn = $("ef-refresh");
    if (btn) btn.addEventListener("click", load);
  }

  function boot() { bind(); show("feed"); load(); }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
}());