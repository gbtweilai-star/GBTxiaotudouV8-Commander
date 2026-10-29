/* GBT小土豆V8 · 上帝视角 · preload（W3 / W9）
 * 只暴露只读 IPC：渲染进程**没有任何数据写口**（V6）—— 不写文件、不发网络、不碰 store。
 *
 * W9 补记：新增一个**动作口** `summon`（数字人召唤）。它不写任何数据，
 * 只让主进程起一个本机窗口；不 kill 任何进程。除它以外全部仍是只读口，
 * 所以 `readonly: true` 的语义限定为"数据面只读"，动作面另立一行如实登记：
 * `non_readonly_capability`。谁要再加动作口，必须同步改这一行，不许悄悄放宽。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const { contextBridge, ipcRenderer } = require("electron");

const invoke = (channel, payload) => ipcRenderer.invoke(channel, payload);

contextBridge.exposeInMainWorld("gbtW3", {
  readonly: true,
  non_readonly_capability: "summon（只起一个本机窗口：不写文件、不发网络、不 kill 进程）"
    + " · connectDsh（把主人**运行时**给的对话面 URL 交给窗口加载：只放行本机回环；"
    + "URL 只在内存，**不落盘、不回显**，返回值只给 host）"
    + " · openExternal（把**本机回环**页面交给系统浏览器打开：只放行回环，不落盘、只回 host）"
    + " · panelGoto（**面板内跳页**：让面板窗切到某注册窗的页面，不开新窗）"
    + " · capFrame（**取一帧触手视野**：走面板桥真调 tentacle see；只在内存回传，不落盘）"
    + " · heartbeat（**触手心跳派活**：按轮换给只读能力位派活，账本自己会记；关掉即停）"
    + " · showWindow（一体式 App 铬的跨窗跳转：**只认注册表里已有的窗 id**；"
    + "只改窗口可见性/焦点，不写文件、不出网、不 kill 进程）"
    + " · intercom（**开麦克风采集 + 让本机出声**。第 58 轮加。"
    + "口径：监听随页面生灭、不设开关；真跑的是 intercom.py，它走唯一门 run_task；"
    + "主进程不直接碰 voice_cap、不读凭据、不写文件；关页面即 kill 该子进程）"
    + " · pageMessage（**跨页派活**：给指定注册窗发一条消息，触发该页 onPageMessage 回调。"
    + "消息原样透传、不解析、不存；只认注册表 id；**不替目标页调能力位**——执行权在目标页）"
    + " · dshMount（**把对话引擎装进指定 webview**：只接受 webview 的 webContentsId，"
    + "入口 URL 由主进程 loadURL 直接装 —— **渲染进程拿不到带 token 的 URL**；"
    + "不过回环白名单的一律拒；回执只含 host，不含 token、不落盘）",
  config: () => invoke("w3:config"),
  state: () => invoke("w3:state"),
  tasks: () => invoke("w3:tasks"),
  env: () => invoke("w3:env"),
  ledger: () => invoke("w3:ledger"),
  health: () => invoke("w3:health"),
  matrix: () => invoke("w3:matrix"),
  mindmap: () => invoke("w3:mindmap"),
  selfcheck: () => invoke("w3:selfcheck"),
  introspect: () => invoke("w3:introspect"),
  tools: () => invoke("w3:tools"),
  h1: () => invoke("w3:h1"),
  pets: (payload) => invoke("w3:pets", payload),
  summon: (payload) => invoke("w3:summon", payload),
  connectDsh: (payload) => invoke("w3:connect-dsh", payload),
  /* 🔴 2026-10-09 主人令「必须镶嵌进去……统一品牌和Logo，我们是把她集成进我们」：
     取**对话引擎入口**给自己的本地页用（品牌框架页 / 面板内嵌页），
     这样引擎跑在**我们的门面**里，而不是她的整窗界面。
     口径不变：只放行本机回环；没有就如实说"还没接上"，不假装。 */
  /* 🔴 2026-10-26 换口：原来是 `dshEntry()` 把**带 token 的入口 URL** 交给页面
     （页面再 setAttribute("src", url) 载引擎）—— 那等于把凭据暴露给渲染进程 JS，
     守卫 B7 明令禁止回显。
     ⇒ 改成 `dshMount({ wcId })`：页面只报自己那个 <webview> 的 webContentsId，
        **由主进程直接 loadURL**。URL 全程不进渲染进程，回执只含 host。
        与 B4 一起变干净：壳里不再需要往页面里推脚本。 */
  dshMount: (payload) => invoke("w3:dsh-mount", payload),
  /* 数字人页的「文本→桥」受理口（2026-10-08）：页面是**离线自包含**的
     （CSP `connect-src 'none'`，自己发不出任何请求），所以由**壳替它跑这一趟**：
     页面只给文本，**目标由壳写死**（只可能打到本机面板桥 :8765 的 /api/message）
     ⇒ 页面构造不出别的地址，也就不用放开它的网络面。失败**带原文**回来，不静默。 */
  message: (payload) => invoke("w3:message", payload),
  showWindow: (payload) => invoke("w3:show-window", payload),
  /* 在系统浏览器里打开**本机回环**页面（动作口，2026-10-04）：页面固定的配套 ——
     窗不上跳，显式意图走浏览器。只放行回环；URL 只进内存，返回只有 host。 */
  openExternal: (payload) => invoke("w3:open-external", payload),
  /* 面板内跳页（主人令 2026-10-04「固定在 APP 面板上」）：让**面板窗**在内容区里切页，
     不再新建 OS 窗。只认得注册表里的窗 id（壳侧解析成页面路径）。 */
  panelGoto: (payload) => invoke("w3:panel-goto", payload),
  /* 触手视野**活体取帧**（动作口，2026-10-04）：真调 tentacle see 取一帧，
     只在内存回给页面渲染（不落盘、不缓存、不回显路径）。 */
  capFrame: () => invoke("w3:cap-frame"),
  /* 触手活动流（只读账本尾）与心跳派活开关（动作口：按轮换给**只读**能力位派活）。 */
  capActivity: () => invoke("w3:cap-activity"),
  heartbeat: (payload) => invoke("w3:heartbeat", payload),
  onPanelGoto: (handler) => ipcRenderer.on("panel:goto", (_e, msg) => handler(msg)),
  eigenflux: () => invoke("w3:eigenflux"),
  /* R-H295 新接的两只**只读**审计器（欠账：「覆盖审计接进上帝视角」「零调用点清单接进上帝视角」）。
     两者都是**实时现跑** —— 主进程侧走 /api/capability 真调框架审计器再等 cap_result，
     不是读快照、不是硬编码数字。仍然全部只读，`readonly: true` 语义不变。 */
  coverage: () => invoke("w3:coverage"),
  orphans: () => invoke("w3:orphans"),
  gene: () => invoke("w3:gene"),
  onEvent: (handler) => ipcRenderer.on("w3:event", (_e, msg) => handler(msg)),
  onStreamState: (handler) => ipcRenderer.on("w3:stream", (_e, st) => handler(st)),
  /* 🔴 窗口**真可见性**（2026-10-27）：只有主进程知道窗口是不是真的露在人眼前
     （`win.isVisible()`）。页面自己判不出来 —— 实测 Electron 对 `show:false` 的窗，
     `document.visibilityState` 仍可能报 "visible"（离屏渲染时尤其如此）。
     页面据此决定"没人看就别刷"，这是主窗被 5s 轮询吃满的修法。 */
  onWinVisibility: (handler) => ipcRenderer.on("w3:win-visibility", (_e, m) => handler(m)),
  /* 推送有竞态（注入脚本可能晚于那一次推送才订阅上）⇒ 再给个**主动问一次**的口。
     `GBT_W3_NO_VIS_PULL=1` 只是**取证开关**（默认关）：把它关掉就能单独复现"只有推送"那一版，
     用来证明「推送 + 不拉 = 主窗塌」不是猜的。 */
  winVisible: () => (process.env.GBT_W3_NO_VIS_PULL === "1"
    ? Promise.resolve({ ok: false, error: "取证：GBT_W3_NO_VIS_PULL=1 ⇒ 不提供真可见性" })
    : invoke("w3:win-visible")),
  /* 实时流的**现状**（只读拉取 · 2026-09-23 第 45 轮加）。
     上面那个 `onStreamState` 是**推**：只在状态变化时来一次。而窗口可能**在连接之后**才建
     （`startSse` 跑在建窗之前 —— 数据面先立那条规矩），推的那一次就没人听得到。
     ⇒ 补一个拉取口，谁建的窗都能问现状。**只读**，所以不进 `non_readonly_capability`。 */
  streamState: () => invoke("w3:stream-state"),
  /* W3 · **语音对讲**（2026-09-23 第 58 轮加）。这是**动作口**，不是数据面只读：
     它会①开麦克风采集、②让本机出声（TTS）。两件都不是"读"，所以**必须**
     同步登记进上面 `non_readonly_capability` 那一行，不许悄悄放宽。
     口径（主人令）：「打开页面就自动监听，关闭她也跟着关闭」⇒ **不设开关**；
     监听随**页面**生灭，不随进程常驻（大脑后台另算）。
     真跑的是 `tools/codex-scripts/intercom.py`，它内部走唯一门（`five-dim.py cap voice`
     = `api.run_task`）；**主进程不直接碰 voice_cap、不读凭据、不写数据**。 */
  intercom: (op, args) => invoke("w3:intercom", { op: op, args: args || {} }),
  onIntercom: (handler) => ipcRenderer.on("w3:intercom-event", (_e, msg) => handler(msg)),

  /* ── 2026-10-26 跨页触手网格（主人令：「每一页和所有页面互通按需激活」）──────
     三个口配合 `tentacle-kit.js` 的跨页网格：
       · pageMessage  —— 跨页派活（动作口，已登记进 non_readonly_capability）；
       · pageState    —— **只读**快照各窗可见性 + 页面自盖的 data-tentacle-active；
       · onPageMessage—— 渲染进程侧监听跨页消息（含回执）。
     ⚠️ 回执配对（reqId / replyTo）**全在渲染层**做，主进程只透传 —— 主进程不维护
     跨页会话状态，也就不会因为页面崩溃而留下幽灵请求。 */
  pageMessage: (payload) => invoke("w3:page-message", payload),
  pageState: (payload) => invoke("w3:page-state", payload),
  /* 按需激活**自报**口（2026-10-26）：页面在 visibilitychange 时把自己"可见/隐藏"告诉壳，
     壳只记录、不推断。这样「哪页活着」是页面自己说的，不是主进程去读 DOM 猜的。 */
  reportActive: (payload) => invoke("w3:page-active", payload),
  /* 页面心跳口（2026-10-27）：页面每 8s 报一次「我还在跑脚本」。
     🔴 键名**不能叫 heartbeat** —— 上面第 79 行已有 `heartbeat`（触手心跳派活，`w3:heartbeat`），
        同名键在对象字面量里会被后者覆盖 ⇒ 我会把那个功能悄悄弄坏（实测 grep 抓到）。
     为什么必须页面自报：脚本队列被堵时，主进程发过去的调用**永远不 settle**，
     Chromium 的挂起监视器也不报（靶子页确定性复现 + 四次真启动全 0 次触发）
     ⇒ 只有页面自己知道自己还活着。壳只记时间戳，超时就强崩重载（实测 294ms 恢复）。 */
  pageBeat: (payload) => invoke("w3:page-heartbeat", payload),
  onPageMessage: (handler) => ipcRenderer.on("w3:page-message", (_e, msg) => handler(msg)),
});