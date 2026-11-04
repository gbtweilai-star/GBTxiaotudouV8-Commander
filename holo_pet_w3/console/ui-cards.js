/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * ACUI 卡片栈：只渲染纯文本，动作只 POST 回事件（不执行工具）。 */
(function () {
  "use strict";
  var stack = document.getElementById("ui-cards");
  if (!stack) return;
  var KIND_LABEL = { info: "消息", selfcheck: "自检", wake: "唤醒", image: "图片",
    video: "视频", confirm: "确认", weather: "天气" };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function api(body) {
    return fetch("/api/ui/cards", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); });
  }
  function refresh() {
    fetch("/api/ui/cards", { cache: "no-store" }).then(function (r) { return r.json(); })
      .then(function (j) { render((j && j.cards) || []); }).catch(function () {});
  }
  function render(cards) {
    stack.innerHTML = "";
    (cards || []).slice().reverse().forEach(function (c) {
      var box = el("div", "ui-card");
      box.setAttribute("data-kind", c.kind || "info");
      var head = el("div", "ui-card-head");
      head.appendChild(el("span", "ui-card-kind", KIND_LABEL[c.kind] || c.kind || "卡片"));
      var x = el("button", "ui-card-x", "×");
      x.type = "button"; x.title = "关闭";
      x.onclick = function () { api({ op: "close", id: c.id, reason: "user_close" }).then(refresh); };
      head.appendChild(x);
      box.appendChild(head);
      box.appendChild(el("div", "ui-card-title", c.title || ""));
      if (c.body) box.appendChild(el("div", "ui-card-body", c.body));
      var acts = (c.actions || []);
      if (acts.length) {
        var row = el("div", "ui-card-actions");
        acts.forEach(function (a) {
          var b = el("button", "ui-card-act", a.label || a.id);
          b.type = "button";
          b.onclick = function () {
            api({ op: "action", id: c.id, action: a.id }).then(function (j) {
              if (j && j.ok && j.event) {
                box.appendChild(el("div", "ui-card-event",
                  "已回发事件：" + j.event.action.label + "（只回事件，不执行）"));
                try {
                  window.dispatchEvent(new CustomEvent("gbt:ui-card-action", { detail: j.event }));
                } catch (e) {}
              }
              refresh();
            });
          };
          row.appendChild(b);
        });
        box.appendChild(row);
      }
      if (c.remaining != null) box.appendChild(el("div", "ui-card-ttl", "剩 " + c.remaining + "s"));
      stack.appendChild(box);
    });
  }
  window.__uiCardRefresh = refresh;
  setInterval(refresh, 8000);
  refresh();
})();
