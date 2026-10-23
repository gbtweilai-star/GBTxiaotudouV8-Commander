/* GBT小土豆V8 · AI 朋友圈 · 渲染层（W9）
 *
 * 为什么单独成文件：朋友圈有两个出口 —— 上帝视角窗口的「数字人」tab、以及独立窗
 * eigenflux/index.html。两处各写一份卡片，日子久了一定对不上，所以 DOM 构建器只留这一份。
 *
 * 本文件只做 DOM 构建：不取数据（数据一律由主进程 IPC 交来）、不写盘、不发网络、
 * 不含 fetch / fs / 任何写调用。字段契约真身在 shell/features.cjs（归一化那一段），
 * 这里只消费它 —— 字段名要改，改 features.cjs，不改这里。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
(function () {
  "use strict";

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  }

  /* 时间戳一律按**本机时区**上屏。原先 `String(v).replace("T"," ").slice(0,16)` 是拿
   * features.cjs::toIso 的 UTC ISO 串直接切前 16 位 —— 那串不但早于本地时间，
   * 还被切掉了末尾的 Z，屏上没有任何东西提示它是 UTC（实测 Shanghai 口径差 8 小时，
   * 且跨零点的 friend_since 会整整差一天）。坏值原样回显，不许编一个时间出来。 */
  function stamp(v) {
    if (!v) return null;
    var d = new Date(String(v));
    if (isNaN(d.getTime())) return String(v).slice(0, 16);
    return d.toLocaleString("zh-CN", {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hour12: false,
    }).replace(/\//g, "-");
  }

  function tag(text) { return el("span", "ef-tag", text); }

  function empty(host, reason) {
    if (!host) return;
    host.textContent = "";
    host.appendChild(el("div", "ef-empty", reason));
  }

  function item(row) {
    var card = el("div", "ef-item");
    var head = el("div", "ef-head");
    head.appendChild(el("span", "ef-name", row.author || "（未署名）"));
    if (row.type) head.appendChild(el("span", "ef-meta", row.type));
    if (row.relation) head.appendChild(el("span", "ef-meta", row.relation));
    if (stamp(row.created_at)) head.appendChild(el("span", "ef-meta", stamp(row.created_at)));
    if (row.redactions) head.appendChild(el("span", "ef-meta", "已脱敏 " + row.redactions + " 处"));
    card.appendChild(head);
    card.appendChild(el("div", "ef-content", row.content || "（空正文）"));
    var tags = el("div", "ef-tags");
    (row.domains || []).forEach(function (d) { tags.appendChild(tag(d)); });
    (row.keywords || []).forEach(function (k) { tags.appendChild(tag("#" + k)); });
    if (row.expected_response) tags.appendChild(tag("求：" + row.expected_response));
    if (row.truncated_at_source) tags.appendChild(tag("源自带截断"));
    if (tags.childNodes.length) card.appendChild(tags);
    return card;
  }

  function friend(row) {
    var card = el("div", "ef-item");
    var head = el("div", "ef-head");
    head.appendChild(el("span", "ef-name", row.agent_name || "（无名）"));
    if (row.agent_id) head.appendChild(el("span", "ef-meta", row.agent_id));
    card.appendChild(head);
    if (row.remark) card.appendChild(el("div", "ef-content", row.remark));
    card.appendChild(el("div", "ef-meta",
      row.friend_since
        ? ("成为好友 " + (stamp(row.friend_since) || "").slice(0, 10))
        : "成为好友时间：未记"));
    return card;
  }

  function message(row) {
    var card = el("div", "ef-item");
    var head = el("div", "ef-head");
    head.appendChild(el("span", "ef-name", row.sender_name || row.sender_id || "（无署名）"));
    if (row.is_official) head.appendChild(el("span", "ef-meta", "官方"));
    if (stamp(row.created_at)) head.appendChild(el("span", "ef-meta", stamp(row.created_at)));
    if (row.redactions) head.appendChild(el("span", "ef-meta", "已脱敏 " + row.redactions + " 处"));
    card.appendChild(head);
    card.appendChild(el("div", "ef-content", row.content || "（空正文）"));
    return card;
  }

  function profile(row) {
    var card = el("div", "ef-item");
    if (!row) {
      card.appendChild(el("div", "ef-empty", "档案取不到"));
      return card;
    }
    var head = el("div", "ef-head");
    head.appendChild(el("span", "ef-name", row.agent_name || "（无名）"));
    if (row.agent_id) head.appendChild(el("span", "ef-meta", row.agent_id));
    card.appendChild(head);
    card.appendChild(el("div", "ef-content", row.bio || "（没写简介）"));
    card.appendChild(el("div", "ef-meta", row.email_bound ? "邮箱：已绑定（值不回显）" : "邮箱：未绑定"));
    return card;
  }

  function list(host, rows, builder, emptyReason) {
    if (!host) return;
    host.textContent = "";
    if (!rows || !rows.length) { host.appendChild(el("div", "ef-empty", emptyReason)); return; }
    rows.forEach(function (r) { host.appendChild(builder(r)); });
  }

  function issues(host, rows) {
    if (!host) return;
    (rows || []).forEach(function (t) { host.appendChild(el("div", "ef-warn", "✕ " + t)); });
  }

  window.gbtEfRender = {
    el: el, empty: empty, item: item, friend: friend, message: message,
    profile: profile, list: list, issues: issues,
  };
}());