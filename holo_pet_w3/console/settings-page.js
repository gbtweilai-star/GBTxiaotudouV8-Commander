/* 设置中心：19 个面板（套餐那组不收录）· 数据来自 /api/settings-center */
(function () {
  const API = "/api/settings-center";
  const ACT = API + "/act";

  const ICONS = {
    appearance: '<circle cx="8" cy="8" r="5.6"/><path d="M8 5.2v3.1l2.1 1.4"/>',
    hotkeys: '<rect x="2" y="4.5" width="12" height="7" rx="1.4"/><path d="M4.4 9.4h7.2"/>',
    platforms: '<path d="M3 4.8h10v3.4H3zM3 10.2h10"/><circle cx="5" cy="6.5" r=".6"/>',
    stats: '<path d="M2.6 12.4V8.2M6 12.4V4.4M9.4 12.4V6.6M12.8 12.4V2.9"/>',
    device: '<rect x="2.2" y="3" width="11.6" height="7.4" rx="1.2"/><path d="M5.4 13h5.2M8 10.4V13"/>',
    env: '<path d="M3 4.2h10M3 8h10M3 11.8h6.4"/>',
    storage: '<ellipse cx="8" cy="4.2" rx="5.2" ry="1.9"/><path d="M2.8 4.2v7.6c0 1 2.3 1.9 5.2 1.9s5.2-.9 5.2-1.9V4.2"/>',
    notify: '<path d="M4.2 7.2a3.8 3.8 0 017.6 0v2.6l1.2 1.8H3l1.2-1.8zM6.6 12.6a1.5 1.5 0 002.8 0"/>',
    providers: '<circle cx="8" cy="8" r="5.6"/><path d="M8 4.6v6.8M4.6 8h6.8"/>',
    models: '<path d="M8 2.4l4.8 2.8v5.6L8 13.6 3.2 10.8V5.2z"/><path d="M8 8l4.8-2.8M8 8v5.6M8 8L3.2 5.2"/>',
    skills: '<path d="M3 4.4h4.4v4.4H3zM8.6 7.2h4.4v4.4H8.6z"/>',
    tags: '<path d="M2.6 3.4h6l4.8 4.8-5 5-5.8-5.8z"/><circle cx="5.4" cy="6.2" r=".8"/>',
    connectors: '<circle cx="4.4" cy="4.4" r="1.7"/><circle cx="11.6" cy="11.6" r="1.7"/><path d="M5.7 5.7l4.6 4.6"/>',
    memory: '<path d="M3.2 5.2h9.6v7.2H3.2z"/><path d="M5.6 5.2V3.2h4.8v2"/>',
    credentials: '<circle cx="5.4" cy="8" r="2.2"/><path d="M7.6 8H13M11 8v2.2M9.4 8v1.6"/>',
    proxy: '<circle cx="8" cy="8" r="5.6"/><path d="M2.4 8h11.2M8 2.4c2.2 2 2.2 9.2 0 11.2M8 2.4c-2.2 2-2.2 9.2 0 11.2"/>',
    tools: '<path d="M10.4 3.2l2.4 2.4-2 2-2.4-2.4zM4.2 9l3 3-1.8 1.8-3-3z"/>',
    datastore: '<ellipse cx="8" cy="4.4" rx="4.8" ry="1.8"/><path d="M3.2 4.4v7c0 1 2.1 1.8 4.8 1.8s4.8-.8 4.8-1.8v-7"/>',
    recycle: '<path d="M3.4 5.2h9.2M6 5.2V3.8h4v1.4M4.6 5.2l.7 7.4h5.4l.7-7.4"/>',
    about: '<circle cx="8" cy="8" r="5.6"/><path d="M8 7.2v3.6M8 5.4v.2"/>'
  };

  const NAV = [
    { group: "", items: [["appearance", "外观"], ["hotkeys", "快捷键"], ["platforms", "聊天平台"]] },
    { group: "个人", items: [["stats", "数据统计"], ["device", "设备"], ["env", "环境"], ["storage", "存储"], ["notify", "通知"]] },
    { group: "助手", items: [["providers", "AI 服务商"], ["models", "服务模型"], ["skills", "技能"], ["tags", "标签"], ["connectors", "连接器"], ["memory", "记忆设置"], ["credentials", "凭证管理"]] },
    { group: "系统", items: [["proxy", "网络代理"], ["tools", "系统工具"], ["datastore", "数据存储"], ["recycle", "回收站"], ["about", "关于"]] }
  ];

  let D = null, cur = "stats", root = null;

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const num = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));
  const kb = (n) => (n == null ? "—" : n >= 1e9 ? (n / 1e9).toFixed(1) + "B" : n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "k" : String(n));
  const sec = (k) => (D && D.sections && D.sections[k]) || { ok: false, error: "未加载" };

  function shell() {
    const rail = NAV.map((g) => [
      g.group ? '<div class="gs-grp">' + esc(g.group) + "</div>" : "",
      g.items.map(([id, label]) =>
        '<div class="gs-item" data-go="' + id + '"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round">'
        + (ICONS[id] || "") + "</svg><span>" + esc(label) + "</span></div>").join("")
    ].join("")).join("");

    root.innerHTML = [
      '<aside class="gs-rail"><div class="gs-brand"><b>设置</b><span>GBT小土豆V8</span></div>',
      rail,
      '<div class="gs-foot" id="gs-foot">读数据…</div></aside>',
      '<section class="gs-main"><header class="gs-head"><h2 id="gs-title">数据统计</h2>',
      '<span class="gs-sub" id="gs-sub"></span>',
      '<button class="gs-x" data-act="close" title="关闭">×</button></header>',
      '<div class="gs-body" id="gs-body"></div></section>'
    ].join("");
  }

  function titleOf(id) {
    for (const g of NAV) for (const [i, l] of g.items) if (i === id) return l;
    return id;
  }

  function markNav() {
    root.querySelectorAll(".gs-item").forEach((n) => n.classList.toggle("on", n.dataset.go === cur));
    root.querySelector("#gs-title").textContent = titleOf(cur);
  }

  function setSub(t) { root.querySelector("#gs-sub").textContent = t || ""; }

  /* ───────── 面板 ───────── */

  function paneStats() {
    const s = sec("stats");
    if (!s.ok) return cardErr(s);
    const heat = s.heat || {};
    // 近 7 天 vs 前 7 天
    const days = [];
    for (let i = 6; i >= 0; i--) { const d = new Date(Date.now() - i * 864e5); days.push(d.toISOString().slice(0, 10)); }
    const sum = (arr) => arr.reduce((a, d) => a + (heat[d] || 0), 0);
    const last7 = sum(days), prev7 = sum(days.map((d) => new Date(new Date(d).getTime() - 7 * 864e5).toISOString().slice(0, 10)));
    const pct = prev7 ? Math.round(((last7 - prev7) / prev7) * 100) : null;

    const cells = [];
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const start = new Date(today.getTime() - 52 * 7 * 864e5);
    start.setDate(start.getDate() - start.getDay());
    for (let w = 0; w < 53; w++) {
      for (let d = 0; d < 7; d++) {
        const day = new Date(start.getTime() + (w * 7 + d) * 864e5);
        if (day > today) { cells.push('<i style="opacity:.25"></i>'); continue; }
        const key = day.toISOString().slice(0, 10);
        const n = heat[key] || 0;
        const lv = n === 0 ? 0 : n < 2 ? 1 : n < 5 ? 2 : n < 15 ? 3 : 4;
        cells.push('<i data-l="' + lv + '" title="' + key + " · " + n + '"></i>');
      }
    }

    const totalMs = s.run_ms || 0;
    const peak = s.peak_day || ["", 0];
    return [
      '<div class="gs-hero"><h2>这是你与 GBT 一起记录协作的第 ' + Math.max(1, Math.round((Date.now() - new Date(s.first_at || Date.now()).getTime()) / 864e5) + 1) + " 天</h2>",
      '<div class="tiny">最近更新：' + esc((s.last_at || "").replace("T", " ").replace("Z", "")) + " · 数据源：state/projects.db + 触手审计</div>",
      '<div class="kpi">',
      kpiCell(num(s.projects), "项目数", null),
      kpiCell(num((s.tentacle || {}).calls), "触手调用", pct),
      kpiCell(num(s.artifacts), "产物", null),
      kpiCell(kb(totalMs) + " ms", "累计耗时", null),
      "</div>",
      '<div class="subkpi">',
      subCell(num(peak[1]), "峰值单日（" + esc(peak[0] || "—") + "）"),
      subCell(num(s.links), "登记链路"),
      subCell(num(s.runs_ok) + "/" + num(s.runs), "运行成功"),
      subCell(String(Object.keys(heat).length), "有记录的天数"),
      "</div></div>",
      '<div class="card"><div class="row"><h3 class="grow">过去一年活跃度</h3>',
      '<span class="tiny">近 7 天 ' + num(last7) + " 次</span></div>",
      '<div class="heat">' + cells.join("") + "</div>",
      '<div class="heat-legend"><span>较少</span><i style="background:var(--gs-panel-2)"></i><i style="background:color-mix(in srgb,var(--gs-accent) 42%,var(--gs-panel-2))"></i><i style="background:var(--gs-accent)"></i><span>较多</span></div></div>'
    ].join("");
  }

  function kpiCell(n, label, pct) {
    const d = pct == null ? "" : '<span class="d' + (pct < 0 ? " neg" : "") + '">' + (pct >= 0 ? "+" : "") + pct + "%</span>";
    return '<div><div class="l">' + esc(label) + " " + d + '</div><div class="n">' + n + "</div></div>";
  }
  function subCell(n, label) { return '<div><div class="n">' + n + '</div><div class="l">' + esc(label) + "</div></div>"; }
  function cardErr(s) { return '<div class="card"><h3>读不到</h3><div class="muted">' + esc(s.error || s.note || "未知") + "</div></div>"; }
  const kv = (rows) => '<table class="kv">' + rows.filter(Boolean).map((r) => "<tr><td>" + esc(r[0]) + '</td><td class="mono">' + (r[2] ? r[1] : esc(r[1])) + "</td></tr>").join("") + "</table>";
  const badge = (ok, t) => '<span class="badge ' + (ok ? "ok" : "bad") + '">' + esc(t) + "</span>";

  function paneAppearance() {
    const a = sec("appearance");
    const th = (a.themes || ["dark", "dim", "light"]).map((t) =>
      '<button class="gs-btn' + (a.theme === t ? " primary" : "") + '" data-set="theme:' + t + '">' + ({ dark: "深色", dim: "暗灰", light: "浅色" }[t] || t) + "</button>").join(" ");
    const ac = (a.accents || ["green", "blue", "violet", "amber"]).map((c) =>
      '<button class="gs-btn' + (a.accent === c ? " primary" : "") + '" data-set="accent:' + c + '">' + c + "</button>").join(" ");
    return '<div class="card"><h3>主题</h3><div class="muted tiny">只作用于设置中心；控制台其余界面沿用原主题。</div><div class="row" style="margin-top:12px">' + th + "</div></div>"
      + '<div class="card"><h3>强调色</h3><div class="row" style="margin-top:10px">' + ac + "</div></div>"
      + '<div class="card"><h3>密度</h3><div class="muted">列表间距沿用控制台；如需紧凑可后续加。</div></div>';
  }

  function paneHotkeys() {
    const h = sec("hotkeys");
    const b = h.bindings || {};
    const keys = Object.keys(b);
    return '<div class="card"><div class="row"><h3 class="grow">脉冲热键（F1–F12）</h3>' + badge(h.ok, h.ok ? (h.daemon && h.daemon.alive ? "守护在跑" : "守护未启") : "触手不可达") + "</div>"
      + (keys.length ? '<table class="kv">' + keys.sort().map((k) => "<tr><td>" + esc(k) + '</td><td class="mono">' + esc(typeof b[k] === "object" ? JSON.stringify(b[k]) : b[k]) + "</td></tr>").join("") + "</table>"
        : '<div class="muted" style="margin-top:10px">还没有绑定。绑定走触手：</div><div class="mono tiny" style="margin-top:6px">pulse_bind {"key":"F9","blueprint":"开搜索","confirm":true}</div>')
      + '<div class="tiny" style="margin-top:12px">触发守护：start-pulse.cmd；查看：pulse_list。</div></div>';
  }

  function panePlatforms() {
    const p = sec("platforms");
    const g = p.gateway || {};
    return '<div class="card"><div class="row"><h3 class="grow">MCP 服务器</h3>' + badge(g.up, g.up ? "网关在线 · " + (g.tools || "?") + " 工具" : "网关未启") + "</div>"
      + ((p.mcp_servers || []).length
        ? '<table class="kv">' + p.mcp_servers.map((s) => "<tr><td>" + esc(s.name) + '</td><td class="mono">' + esc(JSON.stringify(s.command)) + "<br><span class='tiny'>" + esc(s.cwd || "") + "</span></td></tr>").join("") + "</table>"
        : '<div class="muted" style="margin-top:8px">没登记 MCP 服务器。</div>')
      + "</div>"
      + '<div class="card"><h3>对话入口</h3>' + kv([
        ["控制台", "http://127.0.0.1:8766/"],
        ["触手网关", "http://127.0.0.1:7788/"],
        ["剪贴板桥", (p.bridge || {}).clipboard_bridge ? "已安装（start-bridge.cmd）" : "未安装"],
        ["HTTP 网关脚本", (p.bridge || {}).http_gateway ? "runtime/server.mjs 就绪" : "缺失"]
      ]) + "</div>";
  }

  function paneDevice() {
    const d = sec("device");
    if (!d.ok) return cardErr(d);
    return '<div class="card"><h3>设备</h3>' + kv([
      ["主机", d.host], ["系统", d.os], ["CPU", d.cpu], ["逻辑核心", d.cores],
      ["内存", d.mem_total_gb + " GB · 已用 " + d.mem_used_pct + "%"],
      ["开机时间", d.boot_at], ["已运行", d.uptime_h + " 小时"]
    ]) + "</div>"
      + '<div class="card"><div class="row"><h3 class="grow">内存占用</h3><span class="tiny">' + d.mem_used_pct + "%</span></div>"
      + '<div class="bar" style="margin-top:10px"><i style="width:' + d.mem_used_pct + '%"></i></div></div>';
  }

  function paneEnv() {
    const e = sec("env");
    if (!e.ok) return cardErr(e);
    return '<div class="card"><h3>运行时</h3>' + kv([
      ["Python", e.python], ["Node", e.node || "（没找到 node）"], ["仓库", e.repo], ["工作目录", e.cwd],
      ["端口", "console " + e.ports.console + " · 触手 " + e.ports.tentacle + " · 视觉 " + e.ports.llama]
    ]) + "</div>"
      + '<div class="card"><h3>环境变量槽位</h3><div class="chips" style="margin-top:10px">'
      + Object.entries(e.env_flags || {}).map(([k, v]) => '<span class="chip">' + esc(k) + " <b>" + (v ? "在" : "缺") + "</b></span>").join("")
      + "</div></div>";
  }

  function paneStorage() {
    const s = sec("storage");
    const diskRow = (k, d) => d ? '<div style="margin-bottom:12px"><div class="row"><span class="grow">' + k + '</span><span class="tiny">' + d.free_gb + " / " + d.total_gb + " GB 可用</span></div>"
      + '<div class="bar" style="margin-top:6px"><i style="width:' + d.used_pct + '%"></i></div></div>' : "";
    return '<div class="card"><h3>磁盘</h3>' + diskRow("C:", s.disks["C:"]) + diskRow("D:", s.disks["D:"]) + "</div>"
      + '<div class="card"><h3>仓内占用</h3>' + kv(Object.entries(s.dirs_mb || {}).map(([k, v]) => [k, v + " MB"]).concat([["projects.db", (s.db_mb || 0) + " MB"]])) + "</div>";
  }

  function paneNotify() {
    const n = sec("notify");
    return '<div class="card"><div class="row"><h3 class="grow">Windows 通知</h3>'
      + '<div class="sw ' + (n.enabled ? "on" : "") + '" data-toggle="notify"><i></i></div></div>'
      + '<div class="muted tiny" style="margin-top:8px">通道：' + esc(n.channel || "") + "；级别：" + esc(n.level || "info") + "</div>"
      + '<div class="row" style="margin-top:14px"><button class="gs-btn primary" data-act="notify-test">发一条测试通知</button><span class="tiny" id="gs-notify-out"></span></div></div>';
  }

  function paneProviders() {
    const p = sec("providers");
    const l = p.local || {};
    return '<div class="card"><div class="row"><h3 class="grow">' + esc(l.name || "本机") + "</h3>" + badge((l.health || {}).up, (l.health || {}).up ? "在线" : "离线") + "</div>"
      + kv([["端点", l.base || ""], ["模型", l.model || ""]]) + "</div>"
      + '<div class="card"><h3>云端（只看槽位）</h3><div style="margin-top:8px">'
      + (p.cloud || []).map((c) => '<div class="row" style="padding:6px 0"><span class="grow">' + esc(c.name) + '</span><span class="mono tiny">' + esc(c.env) + "</span>" + badge(c.configured, c.configured ? "已配" : "缺") + "</div>").join("")
      + '</div><div class="tiny" style="margin-top:8px">' + esc(p.note || "") + "</div></div>";
  }

  function paneModels() {
    const m = sec("models");
    return '<div class="card"><div class="row"><h3 class="grow">可用模型</h3><button class="gs-btn" data-act="reload">刷新</button></div>'
      + (m.ok ? (m.models || []).map((x) => '<div class="mono" style="padding:6px 0;border-bottom:1px solid var(--gs-line)">' + esc(x) + "</div>").join("")
        : '<div class="muted">' + esc(m.error || "读不到") + "</div>") + "</div>";
  }

  function paneSkills() {
    const s = sec("skills");
    const groups = {};
    (s.skills || []).forEach((k) => { (groups[k.group] = groups[k.group] || []).push(k); });
    return Object.keys(groups).map((g) =>
      '<div class="card"><h3>' + esc(g) + "（" + groups[g].length + "）</h3>"
      + groups[g].map((k) => '<div class="skill"><div><div class="nm">' + esc(k.name) + '</div><div class="ds">' + esc(k.description || "（无描述）") + "</div>"
        + (k.scripts.length ? '<div class="chips" style="margin-top:6px">' + k.scripts.map((x) => '<span class="chip">' + esc(x) + "</span>").join("") + "</div>" : "")
        + "</div></div>").join("") + "</div>").join("");
  }

  function paneTags() {
    const t = sec("tags");
    return '<div class="card"><h3>链路类型</h3><div class="chips" style="margin-top:10px">'
      + (t.link_kinds || []).map((k) => '<span class="chip">' + esc(k.kind) + " <b>" + k.n + "</b></span>").join("")
      + "</div></div>"
      + '<div class="card"><h3>项目角色</h3><div class="chips" style="margin-top:10px">'
      + (t.projects || []).map((p) => '<span class="chip">' + esc(p.name) + " <b>" + esc(p.role || "未标") + "</b></span>").join("")
      + '</div><div class="tiny" style="margin-top:10px">能力标签：' + num(t.cap_tags) + " 条（state/cap_tags.json）</div></div>";
  }

  function paneConnectors() {
    const c = sec("connectors");
    return '<div class="card"><h3>连接器</h3>' + kv([
      ["MCP 服务器", num(c.mcp)],
      ["触手网关", (c.gateway || {}).up ? "在线 · " + ((c.gateway || {}).tools || "?") + " 工具" : "离线"],
      ["剪贴板桥 outbox", num(c.outbox_files) + " 个文件"],
      ["start-bridge.cmd", c.bridge_cmd ? "在" : "缺"],
      ["start-pulse.cmd", c.pulse_cmd ? "在" : "缺"]
    ]) + "</div>";
  }

  function paneMemory() {
    const m = sec("memory");
    return '<div class="card"><h3>记忆</h3>' + kv([
      ["知识库文件", num(m.knowledge_files)], ["记忆库行数", num(m.memory_bank_lines)],
      ["知识地图", (m.know_map_kb || 0) + " KB"]
    ]) + '<div class="tiny" style="margin-top:10px">' + esc(m.note || "") + "</div></div>";
  }

  function paneCredentials() {
    const c = sec("credentials");
    return '<div class="card"><h3>钥匙槽</h3><div style="margin-top:8px">'
      + (c.slots || []).map((s) => '<div class="row" style="padding:6px 0"><span class="grow mono">' + esc(s.env) + "</span>" + badge(s.configured, s.configured ? "在" : "缺") + "</div>").join("")
      + '</div><div class="tiny" style="margin-top:10px">' + esc(c.note || "") + "</div></div>"
      + '<div class="card"><h3>本地保险箱</h3><div class="chips" style="margin-top:8px">'
      + ((c.vault_files || []).length ? c.vault_files.map((f) => '<span class="chip">' + esc(f) + "</span>").join("") : '<span class="muted">没有保险箱文件</span>')
      + "</div></div>";
  }

  function paneProxy() {
    const p = sec("proxy");
    const s = p.system || {};
    return '<div class="card"><h3>系统代理</h3>' + kv([
      ["启用", s.ProxyEnable ? "是" : "否"], ["服务器", s.ProxyServer || "（空）"],
      ["绕过", s.ProxyOverride || "（空）"], ["自动配置", s.AutoConfigURL || "（空）"]
    ]) + "</div>"
      + '<div class="card"><h3>环境变量</h3>' + kv(Object.entries(p.env || {}).map(([k, v]) => [k, v || "（空）"])) + "</div>";
  }

  function paneTools() {
    const t = sec("tools");
    return '<div class="card"><div class="row"><h3 class="grow">触手工具</h3>' + badge(t.tentacle_tools > 0, num(t.tentacle_tools) + " 个") + "</div>"
      + '<div class="chips" style="margin-top:10px">' + Object.entries(t.groups || {}).map(([g, n]) => '<span class="chip">' + esc(g) + " <b>" + n + "</b></span>").join("") + "</div></div>"
      + '<div class="card"><h3>自检</h3>' + kv([["开机自检", JSON.stringify(t.boot_selfcheck || {}).slice(0, 160)], ["命令", t.doctor]]) + "</div>";
  }

  function paneDatastore() {
    const d = sec("datastore");
    return '<div class="card"><h3>项目库</h3>' + kv([
      ["位置", d.db], ["大小", (d.db_mb || 0) + " MB"], ["备份目录", num(d.backups) + " 项"]
    ]) + '<div class="chips" style="margin-top:10px">' + Object.entries(d.tables || {}).map(([k, v]) => '<span class="chip">' + esc(k) + " <b>" + v + "</b></span>").join("") + "</div>"
      + '<div class="tiny" style="margin-top:10px">' + esc(d.policy || "") + "</div></div>";
  }

  function paneRecycle() {
    const r = sec("recycle");
    return '<div class="card"><div class="row"><h3 class="grow">回收站</h3><span class="badge">' + (r.count == null ? "读不到" : r.count + " 项") + "</span></div>"
      + '<div class="muted tiny" style="margin-top:8px">清空是不可逆动作，会删掉回收站里的全部内容。</div>'
      + '<div class="row" style="margin-top:14px"><button class="gs-btn" data-act="recycle-empty">清空回收站</button><span class="tiny" id="gs-recycle-out"></span></div></div>';
  }

  function paneAbout() {
    const a = sec("about");
    return '<div class="card"><h3>' + esc(a.name) + " · " + esc(a.version) + "</h3>"
      + kv([["开发者", a.developer], ["仓库", a.repo], ["控制台", a.console], ["触手", a.tentacle], ["开机自检", a.boot_selfcheck_at || "—"]])
      + '<div class="tiny" style="margin-top:10px">套餐 / 用量 / 积分 / 账单 / 推荐奖励：这一版不收录（不涉及付费）。</div></div>';
  }

  const PANES = {
    stats: paneStats, appearance: paneAppearance, hotkeys: paneHotkeys, platforms: panePlatforms,
    device: paneDevice, env: paneEnv, storage: paneStorage, notify: paneNotify,
    providers: paneProviders, models: paneModels, skills: paneSkills, tags: paneTags,
    connectors: paneConnectors, memory: paneMemory, credentials: paneCredentials,
    proxy: paneProxy, tools: paneTools, datastore: paneDatastore, recycle: paneRecycle, about: paneAbout
  };

  function draw() {
    markNav();
    root.querySelector("#gs-body").innerHTML = (PANES[cur] || (() => "<div class='card'>没有这个面板</div>"))();
    setSub(D ? "读取于 " + (D.iso || "").replace("T", " ") + " · " + Object.keys(D.sections || {}).length + " 个面板" : "");
  }

  async function load(force) {
    try {
      const r = await fetch(API + (force ? "?t=" + Date.now() : ""), { cache: "no-store" });
      D = await r.json();
    } catch (e) {
      D = { ok: false, sections: {}, iso: "", error: String(e).slice(0, 120) };
    }
    const f = root.querySelector("#gs-foot");
    if (f) f.textContent = D.ok ? "数据已就绪" : "读取失败：" + (D.error || "?");
    draw();
    applyTheme();
    return D;
  }

  function applyTheme() {
    const a = sec("appearance");
    root.dataset.theme = a.theme || "dark";
    root.dataset.accent = a.accent || "green";
  }

  async function act(kind, payload) {
    const r = await fetch(ACT, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ kind, ...(payload || {}) }) });
    return r.json().catch(() => ({ ok: false, error: "bad json" }));
  }

  async function open() {
    if (!root) {
      root = document.getElementById("gs-root");
      if (!root) { root = document.createElement("div"); root.id = "gs-root"; document.body.appendChild(root); }
      shell();
    }
    root.classList.add("open");
    await load();
  }
  const close = () => root && root.classList.remove("open");

  document.addEventListener("click", async (e) => {
    if (!root || !root.classList.contains("open")) return;
    const go = e.target.closest("[data-go]");
    if (go) { cur = go.dataset.go; draw(); root.querySelector(".gs-body").scrollTop = 0; return; }
    const btn = e.target.closest("[data-act],[data-set],[data-toggle]");
    if (!btn) return;

    if (btn.dataset.act === "close") return close();
    if (btn.dataset.act === "reload") { btn.textContent = "…"; await load(true); return; }
    if (btn.dataset.act === "notify-test") {
      const out = root.querySelector("#gs-notify-out"); out.textContent = "发送中…";
      const r = await act("notify", {});
      out.textContent = r.ok ? "已发送" : "失败：" + (r.error || "");
      return;
    }
    if (btn.dataset.act === "recycle-empty") {
      if (!confirm("清空回收站？删掉的项不可恢复。")) return;
      const out = root.querySelector("#gs-recycle-out"); out.textContent = "清空中…";
      const r = await act("recycle_empty", {});
      out.textContent = r.ok ? "已清空" : "失败：" + (r.error || r.stderr || "");
      await load(true);
      return;
    }
    if (btn.dataset.set) {
      const [k, v] = btn.dataset.set.split(":");
      await act("set_settings", { [k]: v });
      await load(true);
      return;
    }
    if (btn.dataset.toggle === "notify") {
      const on = !btn.classList.contains("on");
      await act("set_settings", { notify: on });
      btn.classList.toggle("on", on);
      return;
    }
  });

  // 接管控制台的 ⚙（原弹窗仍可用：window.__openSettingsLegacy()）
  function hook() {
    const prev = window.__openSettings;
    if (prev && !prev.__isNew) {
      window.__openSettingsLegacy = prev;
    }
    const fn = open; fn.__isNew = true;
    window.__openSettings = fn;
    window.GBT_SETTINGS = { open, close };
    // 深链：index.html?gs=stats 直接打开设置中心（headless 截图/外部跳转都用它）
    try {
      const q = new URLSearchParams(location.search).get("gs");
      if (q) { if (PANES[q]) cur = q; setTimeout(open, 60); }
    } catch (e) {}
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", hook);
  else hook();
})();
