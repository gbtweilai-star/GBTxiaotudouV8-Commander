/* AI 朋友圈（2026-11-02）：/api/moments 读动态流，发布 + 点赞，数字人 iframe 懒加载 */
(function () {
  if (window.__gbtMoments) return;
  window.__gbtMoments = true;
  var $ = function (id) { return document.getElementById(id); };
  var liked = {};
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function fmt(at) {
    var s = String(at || "");
    return s.length >= 16 ? s.slice(5, 16).replace("T", " ") : s;
  }
  function render(data) {
    var feed = $("moments-feed");
    if (!feed) return;
    var posts = (data && data.posts) || [];
    $("moments-sub").textContent = "她的日常 · " + posts.length + " 条 · " +
      ((data && data.stats && data.stats.likes) || 0) + " 赞 · 数据落 state/moments.json";
    if (!posts.length) { feed.innerHTML = "<div class='moments-empty'>还没有动态。</div>"; return; }
    feed.innerHTML = posts.map(function (p) {
      var isUser = p.kind === "user";
      var tags = (p.tags || []).map(function (t) {
        return "<span class='moment-tag'>" + esc(t) + "</span>";
      }).join("");
      return "<article class='moment-card'>" +
        "<div class='moment-head'><span class='moment-avatar'>" + (isUser ? "我" : "她") +
        "</span><div class='moment-who'><b>" + esc(p.author || "GBT小土豆V8") +
        "</b><span>" + esc(fmt(p.at)) + "</span></div></div>" +
        "<div class='moment-text'>" + esc(p.text || "") + "</div>" +
        (tags ? "<div class='moment-tags'>" + tags + "</div>" : "") +
        "<div class='moment-foot'><button class='moment-like" +
        (liked[p.id] ? " liked" : "") + "' data-id='" + esc(p.id) + "' type='button'>" +
        "♥ " + (p.likes || 0) + "</button></div></article>";
    }).join("");
    feed.querySelectorAll(".moment-like").forEach(function (b) {
      b.addEventListener("click", function () {
        var pid = b.getAttribute("data-id");
        fetch("/api/moments", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ op: "like", id: pid }) }).then(function (r) {
          return r.json();
        }).then(function (d) { if (d.ok) { liked[pid] = true; render(d); } });
      });
    });
  }
  function load() {
    fetch("/api/moments").then(function (r) { return r.json(); }).then(function (d) {
      if (d.ok) render(d);
    }).catch(function () {});
  }
  function wire() {
    var form = $("moments-form");
    if (!form) return;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var t = $("moments-input").value.trim();
      if (!t) return;
      fetch("/api/moments", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ op: "post", text: t }) }).then(function (r) {
        return r.json();
      }).then(function (d) {
        if (d.ok) { $("moments-input").value = ""; render(d); }
      });
    });
    $("moments-refresh").addEventListener("click", load);
    // 数字人 iframe 懒加载：第一次切到 dh 才加载
    document.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest(".view-tab[data-view='dh']");
      if (!b) return;
      var f = $("dh-frame");
      if (f && !f.getAttribute("src")) f.src = f.getAttribute("data-src");
    }, true);
    if (location.hash === "#dh") { var f2 = $("dh-frame"); if (f2) f2.src = f2.getAttribute("data-src"); }
    load();
    setInterval(load, 15000);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();
})();
