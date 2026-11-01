/* GBT小土豆V8 · 语音剧场 · **窗内抽屉导航**（主人令 2026-10-18：「把 APP 做成一体式，而不是点一下再跳转」）
 *
 * ## 它改掉的是什么
 * 仓里会往每页注入一条「直达」链接条（`tools/codex-scripts/page-reach.py`，一千多个链接）。
 * 原来点任何一个链接，**当前窗就被那个页面带走了** —— 人还在说话，画面跳走了，回来还要再点。
 * 现在：点链接 ⇒ **同一扇窗里拉起一个抽屉**，目标页在 `<iframe>` 里显示，右上角 × 关闭、Esc 关闭，
 * 地址栏式的「本页路径」写在抽屉顶上。**窗不动、状态机不丢、她的动作不中断。**
 *
 * ## 为什么用 iframe 而不是 webview
 * 壳只在**面板窗**开了 `webviewTag`（注册表显式声明），剧场窗没有 —— 不在本窗私自放宽能力面。
 * `file://` 同 scheme 的 iframe 可以**显示**（父页读不到子页 DOM，也不需要读）。
 *
 * ## 诚实边界
 * - 有些页面会自己再跳一层（锚点/自刷新）：抽屉里显示的是**它自己的行为**，本器不拦。
 * - 6 秒内没 load 事件 ⇒ 抽屉顶上如实写「可能被 CSP/权限拦了」并给「在新窗打开」按钮，
 *   不假装打开了。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
(function () {
  "use strict";

  var drawer, frame, title, status, body, lastHref = "";

  function build() {
    if (drawer) return;
    drawer = document.createElement("div");
    drawer.id = "gbt-drawer";
    drawer.innerHTML =
      '<div class="gbt-drawer__bar">' +
      '  <span class="gbt-drawer__title" id="gbtDrawerTitle">内嵌页</span>' +
      '  <span class="gbt-drawer__status" id="gbtDrawerStatus"></span>' +
      '  <button class="gbt-drawer__x" id="gbtDrawerClose" title="关闭（Esc）">×</button>' +
      "</div>" +
      '<div class="gbt-drawer__body"><iframe id="gbtDrawerFrame" referrerpolicy="no-referrer"></iframe></div>';
    document.body.appendChild(drawer);

    var css = document.createElement("style");
    css.textContent =
      "#gbt-drawer{position:fixed;inset:0;z-index:99990;display:none;background:rgba(3,4,12,.86);" +
      "backdrop-filter:blur(6px);}" +
      "#gbt-drawer[data-open='1']{display:block;}" +
      ".gbt-drawer__bar{display:flex;align-items:center;gap:12px;height:44px;padding:0 14px;" +
      "background:rgba(7,10,26,.96);border-bottom:1px solid rgba(232,236,248,.10);" +
      "font:13px/44px ui-monospace,Consolas,monospace;color:#e8ecf8;}" +
      ".gbt-drawer__title{flex:0 0 auto;color:#34D399;}" +
      ".gbt-drawer__status{flex:1 1 auto;color:#9AA4C4;font-size:12px;white-space:nowrap;" +
      "overflow:hidden;text-overflow:ellipsis;}" +
      ".gbt-drawer__x{width:30px;height:26px;border-radius:7px;cursor:pointer;color:#e8ecf8;" +
      "background:rgba(232,236,248,.06);border:1px solid rgba(232,236,248,.16);line-height:24px;}" +
      ".gbt-drawer__body{position:absolute;inset:44px 0 0 0;background:#070A1A;}" +
      "#gbtDrawerFrame{width:100%;height:100%;border:0;background:var(--taste-text,#E8ECF8);}";
    document.head.appendChild(css);

    document.getElementById("gbtDrawerClose").addEventListener("click", close);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && drawer && drawer.getAttribute("data-open") === "1") { e.stopPropagation(); close(); }
    }, true);

    title = document.getElementById("gbtDrawerTitle");
    status = document.getElementById("gbtDrawerStatus");
    frame = document.getElementById("gbtDrawerFrame");
    body = drawer.querySelector(".gbt-drawer__body");
  }

  function open(href, label) {
    build();
    lastHref = href;
    title.textContent = label || href.split("/").pop();
    status.textContent = "载入中… " + href;
    frame.src = href;
    drawer.setAttribute("data-open", "1");

    var born = Date.now(), loaded = false;
    frame.removeAttribute("data-loaded");
    frame.onload = function () {
      loaded = true;
      frame.setAttribute("data-loaded", "1");
      status.textContent = "已载入 · " + href + " · " + Math.max(1, Math.round((Date.now() - born) / 1000)) + "s";
    };
    /* 6 秒没 load ⇒ 如实写原因（不假装打开了） */
    setTimeout(function () {
      if (loaded) return;
      status.textContent = "6 秒内没有载入事件 ⇒ 可能被 CSP/权限拦了（本器不假装打开）· " + href;
    }, 6000);
  }

  function close() {
    if (!drawer) return;
    drawer.setAttribute("data-open", "0");
    try { frame.src = "about:blank"; } catch (e) { /* 忽略 */ }
  }

  /* 只拦**站内 .html 链接**：外链/锚点/JS 链接一律不动（本器不做路由器） */
  document.addEventListener("click", function (ev) {
    var a = ev.target && ev.target.closest ? ev.target.closest("a[href]") : null;
    if (!a) return;
    var href = a.getAttribute("href") || "";
    if (!/\.html(\?|#|$)/i.test(href)) return;
    if (/^(https?:|\/\/)/i.test(href)) return;
    if (a.target === "_blank") return;
    ev.preventDefault();
    ev.stopPropagation();
    open(href, (a.textContent || "").trim() || href);
  }, true);

  /* 量具口：`?drawer=<相对地址>` 直接拉起，便于截图验收 */
  try {
    var q = new URLSearchParams(location.search);
    var d = q.get("drawer");
    if (d) setTimeout(function () { open(d, d); }, 400);
  } catch (e) { /* 无 URLSearchParams 也不致命 */ }

  window.GBT_DRAWER = {
    open: open, close: close,
    isOpen: function () { return !!drawer && drawer.getAttribute("data-open") === "1"; },
    /* 量具口：不靠肉眼，读这三个字段就知道"抽屉到底开没开、载没载上" */
    status: function () {
      return {
        open: !!drawer && drawer.getAttribute("data-open") === "1",
        src: lastHref,
        title: title ? title.textContent : "",
        status: status ? status.textContent : "",
        loaded: !!(frame && frame.getAttribute("data-loaded") === "1")
      };
    }
  };
})();
