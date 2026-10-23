/* GBT小土豆V8 · 紧凑导航（唯一一份 · 由 tools/codex-scripts/gen-nav-compact.py 生成，别手改）
 * 设计：品牌 + 7 个主入口 + 一个可折叠的「更多」，其余入口收进折叠区，永不丢。
 * 数据源：shell/nav-index.json（数据本行内联 —— file:// 下 fetch 会被 CORS 挡死）
 * 什么时候**不画**（2026-10-21 主人令「一堆东西推挤在一起」的根治）：
 *   ① 页面里先写 window.GBT_NAV_DISABLE = true        —— 例如控制面板，它有自己的左栏；
 *   ② window.gbtW3 在（= 运行在壳里）                  —— 壳的标题栏本来就有一条窗口切换条，
 *      再画一条 = 60px 内两条导航。壳外（普通浏览器打开）照旧画，页面照样能到处跳。
 *   想强行画回来：window.GBT_NAV_FORCE = true
 */
window.GBT_NAV_INDEX = {"schema":"gbt-nav/v1","links":[{"path":"panel/index.html","label":"GBT小土豆V8 · 控制面板","group":"窗","id":"panel"},{"path":"index.html","label":"GBT小土豆V8 · 上帝视角","group":"窗","id":"godview"},{"path":"eigenflux/index.html","label":"GBT小土豆V8 · AI 朋友圈","group":"窗","id":"eigenflux"},{"path":"h1/index.html","label":"GBT小土豆V8 · 赏金台","group":"窗","id":"h1"},{"path":"shell/connect.html","label":"GBT小土豆V8 · 对话","group":"窗","id":"dsh-chat"},{"path":"plugins-mesh/index.html","label":"GBT小土豆V8 · 云插件互绑拓扑","group":"窗","id":"plugins-mesh"},{"path":"code-deck/index.html","label":"GBT小土豆V8 · 代码台","group":"窗","id":"code-deck"},{"path":"eye/index.html","label":"GBT小土豆V8 · 触手视觉回传","group":"窗","id":"eye"},{"path":"logbook/index.html","label":"GBT小土豆V8 · 记录本","group":"窗","id":"logbook"},{"path":"blueprint/index.html","label":"GBT小土豆V8 · 项目蓝图","group":"窗","id":"blueprint"},{"path":"cloud-plugins/index.html","label":"GBT小土豆V8 · 云插件独立页","group":"窗","id":"cloud-plugins"},{"path":"cloud-status/index.html","label":"GBT小土豆V8 · 连接状态","group":"窗","id":"cloud-status"},{"path":"db-fleet/index.html","label":"GBT小土豆V8 · 数据库编队","group":"窗","id":"db-fleet"},{"path":"capabilities/index.html","label":"GBT小土豆V8 · 能力统计","group":"窗","id":"capabilities"},{"path":"energy/index.html","label":"GBT小土豆V8 · 能量与绑定","group":"窗","id":"energy"},{"path":"digital-human/index.html","label":"GBT小土豆V8 · 数字人","group":"窗","id":"digital-human"},{"path":"capability-bar/index.html","label":"GBT小土豆V8 · 能力栏","group":"窗","id":"capability-bar"},{"path":"voice-theater/index.html","label":"GBT小土豆V8 · 语音剧场","group":"窗","id":"voice-theater"}]};
(function () {
  if (window.GBT_NAV_FORCE) { /* 强行画：跳过下面两道闸 */ }
  else if (window.GBT_NAV_DISABLE) return;
  else if (window.gbtW3) return;   /* 壳里：标题栏已有窗口切换条，别再画一条 */
  var ME = document.currentScript;
  var ROOT = (ME && ME.src || '').replace(/\/shell\/nav-compact\.js.*$/, '');
  var PRIMARY = [["digital-human", "她"], ["dsh-chat", "对话"], ["panel", "面板"], ["capabilities", "能力"], ["energy", "能量"], ["logbook", "记录"], ["blueprint", "蓝图"]];

  function css() {
    return '' +
      '#gbt-nav{position:sticky;top:0;z-index:99;display:flex;align-items:center;gap:10px;' +
      'padding:6px 12px;font:13px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;' +
      'background:rgba(11,13,18,.92);backdrop-filter:blur(8px);color:#e8ecef;' +
      'border-bottom:1px solid rgba(255,255,255,.08)}' +
      '#gbt-nav .b{font-weight:700;letter-spacing:.5px;color:#f2c14e}' +
      '#gbt-nav a{color:#cfd6dd;text-decoration:none;padding:2px 8px;border-radius:8px}' +
      '#gbt-nav a:hover{background:rgba(242,193,78,.14);color:#fff}' +
      '#gbt-nav .sp{flex:1}' +
      '#gbt-nav details{position:relative}' +
      '#gbt-nav summary{cursor:pointer;list-style:none;padding:2px 10px;border-radius:8px;' +
      'border:1px solid rgba(255,255,255,.14);color:#cfd6dd}' +
      '#gbt-nav summary::-webkit-details-marker{display:none}' +
      '#gbt-nav .panel{position:absolute;right:0;top:130%;width:min(720px,86vw);max-height:60vh;' +
      'overflow:auto;background:#12151c;border:1px solid rgba(255,255,255,.12);border-radius:12px;' +
      'padding:10px 12px;box-shadow:0 18px 50px rgba(0,0,0,.55)}' +
      '#gbt-nav .panel h4{margin:8px 0 4px;font-size:12px;color:#8b97a5;font-weight:600}' +
      '#gbt-nav .panel a{display:inline-block;font-size:12px;margin:0 2px 2px 0}';
  }

  function short(label) {
    return String(label || '').replace(/^GBT小土豆V8\s*·\s*/, '');
  }

  function build(list) {
    var el = document.createElement('div');
    el.id = 'gbt-nav';
    var byId = {};
    (list || []).forEach(function (it) { if (it.id) byId[it.id] = it.path; });
    var h = '<span class="b">GBT小土豆V8</span>';
    PRIMARY.forEach(function (p) {
      var path = byId[p[0]];
      if (path) h += '<a data-id="' + p[0] + '" href="' + ROOT + '/' + path + '">' + p[1] + '</a>';
      else h += '<a data-id="' + p[0] + '" style="opacity:.45" title="这一版没有这个窗">' + p[1] + '</a>';
    });
    h += '<span class="sp"></span>';
    var groups = {};
    (list || []).forEach(function (it) {
      var g = it.group || '其他';
      (groups[g] = groups[g] || []).push(it);
    });
    var n = (list || []).length;
    h += '<details><summary>更多（' + n + '）</summary><div class="panel">';
    Object.keys(groups).sort().forEach(function (g) {
      h += '<h4>' + g + '</h4>';
      groups[g].forEach(function (it) {
        h += '<a href="' + ROOT + '/' + it.path + '">' + short(it.label) + '</a>';
      });
    });
    h += '</div></details>';
    el.innerHTML = h;
    return el;
  }

  function mount(list) {
    if (document.getElementById('gbt-nav')) return;   /* 只许挂一条 */
    var st = document.createElement('style');
    st.textContent = css();
    document.head.appendChild(st);
    var bar = build(list);
    var host = document.getElementById('gbt-direct-nav');
    if (host && host.parentNode) host.parentNode.replaceChild(bar, host);
    else document.body.insertBefore(bar, document.body.firstChild);
    window.__GBT_NAV = { count: (list || []).length, primary: PRIMARY.length };
  }

  /* 数据已内联 ⇒ 永远同步挂载，不再走 fetch（原 fetch 分支在 file:// 下必然失败，
     且是残件的来源）。这条路径就一条，跑几次都一样。 */
  mount(window.GBT_NAV_INDEX.links || []);
})();
