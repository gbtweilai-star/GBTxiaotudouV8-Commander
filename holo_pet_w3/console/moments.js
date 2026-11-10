/* AI 朋友圈 · 全能力（2026-11-02）
 * 动态 / 广播 / 投票 / 点赞 / 评论 / 私密评论 / 私信 / 转发 / 置顶 / 删除 / 通知 / 关注
 * 后端：gbt_allinone/moments_hub.py · 落盘 state/moments.json
 */
(function () {
  if (window.__gbtMoments) return;
  window.__gbtMoments = true;
  var $ = function (id) { return document.getElementById(id); };
  var S = { data: null, tab: "feed", mode: "moment", dm: null, open: {} };

  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function fmt(at) {
    var s = String(at || "");
    return s.length >= 16 ? s.slice(5, 16).replace("T", " ") : s;
  }
  function api(body) {
    return fetch("/api/moments", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body) }).then(function (r) { return r.json(); });
  }
  function load() {
    fetch("/api/moments").then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.ok) { S.data = d; render(); }
    }).catch(function () {});
  }
  function avatar(p, small) {
    var prof = p || {};
    var ch = String(prof.name || "?").slice(0, 1);
    var color = prof.color || "#666";
    return "<span class='m-avatar" + (small ? " sm" : "") + "' style='background:" +
      esc(color) + "'>" + esc(ch) + "</span>";
  }

  function pollHtml(p) {
    if (!p.poll) return "";
    var voted = (p.poll.voted || []).indexOf("me") >= 0;
    var max = 1;
    (p.poll.options || []).forEach(function (o) { max = Math.max(max, +o.votes || 0); });
    return "<div class='m-poll' data-pid='" + esc(p.id) + "'>" + (p.poll.options || []).map(function (o, i) {
      var pct = Math.round((+o.votes || 0) / max * 100);
      return "<button class='m-vote" + (voted ? " voted" : "") + "' data-id='" + esc(p.id) +
        "' data-index='" + i + "' type='button'><i style='width:" + pct + "%'></i><span>" +
        esc(o.text) + "</span><b>" + (+o.votes || 0) + "</b></button>";
    }).join("") + "</div>";
  }

  function commentsHtml(p) {
    var list = (p.comments || []).map(function (c) {
      return "<div class='m-comment'><b>" + esc(c.author) + "</b>" + esc(c.text) +
        "<button class='m-private' data-id='" + esc(p.id) + "' data-contact='" +
        esc(c.author_id || "") + "' data-author='" + esc(c.author) + "' type='button'>私聊</button></div>";
    }).join("");
    return "<div class='m-comments'>" + (list || "<div class='m-no-comment'>还没有评论</div>") +
      "<form class='m-comment-form' data-id='" + esc(p.id) + "'>" +
      "<input placeholder='写评论…' class='m-comment-input' autocomplete='off'>" +
      "<button type='submit' data-kind='public'>评论</button>" +
      "<button type='button' class='m-comment-private' data-id='" + esc(p.id) + "'>私密评论</button>" +
      "</form></div>";
  }

  function card(p, opts) {
    var prof = p.author_profile || { name: p.author, color: "#666" };
    var kindBadge = p.kind === "broadcast" ? "<span class='m-badge broadcast'>广播</span>" :
      (p.kind === "poll" ? "<span class='m-badge'>投票</span>" :
      (p.kind === "repost" ? "<span class='m-badge'>转发</span>" : ""));
    var pin = p.pinned ? "<span class='m-badge pin'>置顶</span>" : "";
    var mc = p.broadcast ? "<div class='m-broadcast-info'>送达 " + (p.broadcast.recipients || 0) +
      " 位 · 已读 " + (p.broadcast.read || 0) + " 位</div>" : "";
    var tags = (p.tags || []).map(function (t) { return "<span class='m-tag'>#" + esc(t) + "</span>"; }).join("");
    var commentsOpen = S.open[p.id];
    return "<article class='m-card' data-pid='" + esc(p.id) + "'>" +
      "<header>" + avatar(prof) + "<div class='m-who'><b>" + esc(prof.name || p.author) +
      "</b><span>" + esc(prof.role || "") + " · " + fmt(p.at) + "</span></div>" +
      "<div class='m-badges'>" + kindBadge + pin + "</div></header>" +
      "<div class='m-text'>" + esc(p.text || "").replace(/\n/g, "<br>") + "</div>" +
      (tags ? "<div class='m-tags'>" + tags + "</div>" : "") + pollHtml(p) + mc +
      "<footer>" +
      "<button class='m-act m-like" + (p.liked ? " on" : "") + "' data-id='" + esc(p.id) + "' type='button'>" +
      (p.liked ? "♥" : "♡") + " " + (p.likes || 0) + "</button>" +
      "<button class='m-act m-comment-toggle' data-id='" + esc(p.id) + "' type='button'>💬 " +
      (p.comment_count || 0) + "</button>" +
      "<button class='m-act m-repost' data-id='" + esc(p.id) + "' type='button'>↗ 转发</button>" +
      "<button class='m-act m-pin' data-id='" + esc(p.id) + "' type='button'>" +
      (p.pinned ? "取消置顶" : "📌 置顶") + "</button>" +
      (p.author_id === "me" ? "<button class='m-act m-del' data-id='" + esc(p.id) + "' type='button'>删除</button>" : "") +
      "</footer>" +
      (commentsOpen ? commentsHtml(p) : "") + "</article>";
  }

  function renderFeed() {
    var box = $("moments-feed");
    if (!box) return;
    var posts = (S.data && S.data.posts) || [];
    var vis = posts.filter(function (p) { return p.visibility !== "private" || p.author_id === "me"; });
    box.innerHTML = vis.length ? vis.map(function (p) { return card(p); }).join("") :
      "<div class='moments-empty'>还没有动态，发第一条。</div>";
  }

  function renderBroadcast() {
    var box = $("moments-broadcast");
    if (!box) return;
    var posts = ((S.data && S.data.posts) || []).filter(function (p) { return p.kind === "broadcast"; });
    box.innerHTML = posts.length ? posts.map(function (p) { return card(p); }).join("") :
      "<div class='moments-empty'>还没有广播。切到「动态」把发布模式改成广播。</div>";
  }

  function renderDmList() {
    var box = $("dm-list");
    if (!box || !S.data) return;
    var sum = S.data.dm_summary || {};
    box.innerHTML = (S.data.contacts || []).map(function (c) {
      var d = sum[c.id] || {};
      var active = S.dm && S.dm.contact && S.dm.contact.id === c.id;
      return "<button class='dm-item" + (active ? " active" : "") + "' data-contact='" + esc(c.id) + "' type='button'>" +
        avatar(c, true) + "<span class='dm-meta'><b>" + esc(c.name) + "</b><i>" +
        esc(d.last || c.role) + "</i></span>" +
        (d.unread ? "<em class='dm-unread'>" + d.unread + "</em>" : "") + "</button>";
    }).join("");
  }

  function renderDmThread() {
    var box = $("dm-thread");
    var head = $("dm-head");
    if (!box || !head) return;
    if (!S.dm || !S.dm.contact) {
      head.textContent = "选择好友私信";
      box.innerHTML = "<div class='dm-empty'>点左边好友，开始私信；评论区的「私聊」会直接带到这里。</div>";
      return;
    }
    head.innerHTML = avatar(S.dm.contact, true) + "<b>" + esc(S.dm.contact.name) + "</b><span>" +
      esc(S.dm.contact.role || "") + "</span>";
    var msgs = S.dm.messages || [];
    box.innerHTML = msgs.length ? msgs.map(function (m) {
      return "<div class='dm-msg " + (m.from === "me" ? "me" : "them") + "'><div>" + esc(m.text) +
        "</div><time>" + fmt(m.at) + "</time></div>";
    }).join("") : "<div class='dm-empty'>还没有消息，先说一句。</div>";
    box.scrollTop = box.scrollHeight;
  }

  function renderNotify() {
    var box = $("moments-notify");
    if (!box || !S.data) return;
    var ns = S.data.notifications || [];
    box.innerHTML = (ns.length ? "<div class='notify-head'><span>通知 " + ns.length +
      " 条</span><button id='notify-readall' type='button'>全部已读</button></div>" : "") +
      (ns.map(function (n) {
        return "<div class='notify-item" + (n.read ? "" : " unread") + "' data-id='" + esc(n.id) + "'>" +
          "<b>" + esc(n.type) + "</b><span>" + esc(n.text) + "</span><time>" + fmt(n.at) + "</time></div>";
      }).join("") || "<div class='moments-empty'>没有通知。</div>");
  }

  function render() {
    if (!S.data) return;
    var st = S.data.stats || {};
    $("moments-sub").textContent = "动态 " + (st.posts || 0) + " · 广播 " + (st.broadcasts || 0) +
      " · 评论 " + (st.comments || 0) + " · 好友 " + (st.contacts || 0) + " · 数据落 state/moments.json";
    var dmUnread = 0;
    var sum = S.data.dm_summary || {};
    Object.keys(sum).forEach(function (k) { dmUnread += sum[k].unread || 0; });
    $("badge-dm").textContent = dmUnread ? String(dmUnread) : "";
    $("badge-notify").textContent = st.unread ? String(st.unread) : "";
    renderFeed(); renderBroadcast(); renderDmList(); renderDmThread(); renderNotify();
  }

  function setTab(tab) {
    S.tab = tab;
    document.querySelectorAll(".moments-tab").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-mtab") === tab);
    });
    document.querySelectorAll(".moments-panel").forEach(function (p) {
      p.classList.toggle("active", p.id === "mpanel-" + tab);
    });
    if (tab === "dm" && !S.dm) {
      var c = (S.data && S.data.contacts || [])[0];
      if (c) openDm(c.id, null, true);
    }
    if (tab === "notify") { renderNotify(); }
  }

  function openDm(contactId, prefill, noTab) {
    if (!noTab && S.tab !== "dm") setTab("dm");
    api({ op: "dm_open", contact: contactId }).then(function (d) {
      if (!d.ok) return;
      S.data = d;
      S.dm = d.dm;
      var prof = (d.contacts || []).filter(function (c) { return c.id === contactId; })[0] || {};
      S.dm.contact = S.dm.contact || prof;
      renderDmList(); renderDmThread(); render();
      if (prefill) { $("dm-input").value = prefill; $("dm-input").focus(); }
    });
  }

  function publish() {
    var text = $("moments-input").value.trim();
    if (!text) { $("moments-input").focus(); return; }
    var mode = S.mode;
    var body = { op: mode === "broadcast" ? "broadcast" : "post", text: text,
      kind: mode === "broadcast" ? "broadcast" : (mode === "poll" ? "poll" : "moment"),
      visibility: $("moments-visibility").value,
      pinned: $("moments-pinned").checked,
      tags: (text.match(/#([^\s#]{1,12})/g) || []).map(function (t) { return t.slice(1); }) };
    if (mode === "poll") {
      body.options = [$("poll-a").value.trim(), $("poll-b").value.trim(), $("poll-c").value.trim()]
        .filter(function (x) { return !!x; });
    }
    if (!body.pinned && mode === "broadcast") body.pinned = true;
    $("moments-publish").disabled = true;
    api(body).then(function (d) {
      $("moments-publish").disabled = false;
      if (!d.ok) { alert(d.error || "发布失败"); return; }
      S.data = d;
      $("moments-input").value = "";
      $("poll-a").value = $("poll-b").value = $("poll-c").value = "";
      S.open = {};
      render(); setTab(mode === "broadcast" ? "broadcast" : "feed");
    }).catch(function () { $("moments-publish").disabled = false; });
  }

  function onFeedClick(e) {
    var t = e.target;
    var b = t.closest ? t.closest("button") : null;
    if (!b) return;
    var pid = b.getAttribute("data-id");
    if (b.classList.contains("m-like")) {
      api({ op: "like", id: pid }).then(function (d) { if (d.ok) { S.data = d; render(); } });
    } else if (b.classList.contains("m-comment-toggle")) {
      S.open[pid] = !S.open[pid]; render();
    } else if (b.classList.contains("m-repost")) {
      api({ op: "repost", id: pid }).then(function (d) { if (d.ok) { S.data = d; render(); } });
    } else if (b.classList.contains("m-pin")) {
      api({ op: "pin", id: pid }).then(function (d) { if (d.ok) { S.data = d; render(); } });
    } else if (b.classList.contains("m-del")) {
      if (!confirm("删除这条动态？")) return;
      api({ op: "delete", id: pid }).then(function (d) { if (d.ok) { S.data = d; render(); } });
    } else if (b.classList.contains("m-vote")) {
      api({ op: "vote", id: pid, index: b.getAttribute("data-index") })
        .then(function (d) { if (d.ok) { S.data = d; render(); } });
    } else if (b.classList.contains("m-private")) {
      var cid = b.getAttribute("data-contact");
      openDm(cid, "关于动态的私密评论：");
    } else if (b.classList.contains("m-comment-private")) {
      var input = b.parentElement.querySelector(".m-comment-input");
      var text = (input.value || "").trim();
      if (!text) { input.focus(); return; }
      api({ op: "comment_private", id: pid, text: text }).then(function (d) {
        if (!d.ok) return;
        S.data = d;
        render();
        if (d.dm && d.dm.contact) {
          S.dm = d.dm;
          setTab("dm");
          renderDmList(); renderDmThread();
        }
        load();
      });
    }
  }

  function onCommentSubmit(e) {
    var f = e.target.closest ? e.target.closest(".m-comment-form") : null;
    if (!f) return;
    e.preventDefault();
    var pid = f.getAttribute("data-id");
    var input = f.querySelector(".m-comment-input");
    var text = (input.value || "").trim();
    if (!text) return;
    api({ op: "comment", id: pid, text: text }).then(function (d) {
      if (!d.ok) return;
      S.data = d; S.open[pid] = true; render(); load();
    });
  }

  function wire() {
    if (!$("moments-feed")) return;
    document.querySelectorAll(".moments-tab").forEach(function (b) {
      b.addEventListener("click", function () { setTab(b.getAttribute("data-mtab")); });
    });
    document.querySelectorAll(".mc-mode").forEach(function (b) {
      b.addEventListener("click", function () {
        S.mode = b.getAttribute("data-mode");
        document.querySelectorAll(".mc-mode").forEach(function (x) { x.classList.toggle("active", x === b); });
        $("mc-poll").style.display = S.mode === "poll" ? "flex" : "none";
        $("moments-input").placeholder = S.mode === "broadcast" ? "发广播给全部 AI 好友…" :
          (S.mode === "poll" ? "投票主题…" : "以主人身份发一条…");
        $("moments-pinned").checked = S.mode === "broadcast";
      });
    });
    $("moments-publish").addEventListener("click", publish);
    $("moments-refresh").addEventListener("click", load);
    document.addEventListener("click", onFeedClick);
    document.addEventListener("submit", onCommentSubmit);
    document.addEventListener("click", function (e) {
      var n = e.target.closest ? e.target.closest(".notify-item") : null;
      if (n) { api({ op: "notification_read", id: n.getAttribute("data-id") }).then(function (d) { if (d.ok) { S.data = d; render(); } }); }
      var all = e.target.closest ? e.target.closest("#notify-readall") : null;
      if (all) { api({ op: "notification_read" }).then(function (d) { if (d.ok) { S.data = d; render(); } }); }
      var dm = e.target.closest ? e.target.closest(".dm-item") : null;
      if (dm) openDm(dm.getAttribute("data-contact"));
    });
    $("dm-form").addEventListener("submit", function (e) {
      e.preventDefault();
      if (!S.dm || !S.dm.contact) return;
      var text = $("dm-input").value.trim();
      if (!text) return;
      $("dm-input").value = "";
      api({ op: "dm_send", contact: S.dm.contact.id, text: text }).then(function (d) {
        if (!d.ok) return;
        S.data = d; S.dm = d.dm; renderDmList(); renderDmThread(); render();
      });
    });
    load();
    setInterval(load, 20000);
    // 数字人 iframe 懒加载（2026-11-07：视图名/iframe id 已从 dh 改为 teardown，旧选择器导致整页空白）
    function loadAvatarFrame() {
      var f = $("teardown-frame") || $("dh-frame");
      if (f && !f.getAttribute("src")) f.src = f.getAttribute("data-src");
    }
    document.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest(".view-tab[data-view='teardown'], .view-tab[data-view='dh']");
      if (b) loadAvatarFrame();
    }, true);
    window.addEventListener("gbt:view", function (e) {
      if (e.detail === "teardown" || e.detail === "dh") loadAvatarFrame();
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();
})();
