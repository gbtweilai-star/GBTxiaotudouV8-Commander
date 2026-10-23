/* GBT小土豆V8 · 窗口 6 赏金台（W8 · 阶段一 · 本机只读）
 * 只消费 main.cjs 的 w3:h1 只读口；取不到就不显示绿，灰态一律带原因。
 *
 * 2026-09-22 补第二条数据路（Owner：「还有这个要在面板上……我记得已经做了没接上」）：
 *   断点实测 —— 本页原来**只认 Electron IPC**（preload.cjs:31 `h1: () => invoke("w3:h1")`）。
 *   而 DSH 面板宿主是**浏览器 iframe，没有 Electron** ⇒ `window.gbtW3` 不存在 ⇒
 *   本文件原先走 `if (!api)` 打「桥断」，页做得再好也是空壳。
 *   现在：IPC 在就用 IPC（零回归），不在就走**同源 HTTP** `/api/h1`
 *   （面板服务 8765 提供；在 DSH 面板里由 host.js 的 API_SHIM 改写成同源 /gbt-master/api/h1）。
 *   两条路的信封形状**完全一致**（{ok,data} / {ok,error,panel}），所以 render 一份就够。
 *   判定原则一个字没松：**取不到就不显示绿**；只读声明两条路都要过。
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
(function () {
  "use strict";

  var bridge = window.gbtW3 || {};
  var api = typeof bridge.h1 === "function" ? bridge.h1 : null;
  /* 同源那条要按**当前处在哪个源**算（实测教训）：
       · 在 DSH 宿主里，页面挂在 /gbt-master/fs/… 下 → 走宿主插件的内嵌反代
         `/gbt-master/api/h1`。**不能写裸 `/api/h1`** —— 那是 DSH 自己的口，
         要鉴权，实测回的是 401（不是 404），只会白打一发还留个控制台红字。
       · 在面板端口 8765 上直接打开 → 裸 `/api/h1` 才是对的。 */
  var UNDER_HOST = location.pathname.indexOf("/gbt-master/") === 0;
  var HTTP_API = (UNDER_HOST ? "/gbt-master" : "") + "/api/h1";
  var LOOPBACK_API = "http://127.0.0.1:8765/api/h1";

  /* 🔴 2026-09-23 补一条**前提短路**（渲染取证器抓出来的）：
     上面那条"同源 `/api/h1`"只有**页面本身是从 http(s) 提供**时才可能成立。
     而桌面壳的窗是 `loadFile` ⇒ `file://`，此时 `/api/h1` 会被解析成 `file:///C:/api/h1`
     —— **必然失败**，而且是 `net::ERR_FAILED` + 一条控制台红字，每次开窗都白打一发。
     （实测：窗 6 首屏 2 条失败请求，其中 1 条就是它。）
     ⇒ `file:` 协议下**直接跳到回环那条**，前提不成立就别试。
     判据写在代码里而不是注释里：**前提是可机检的事实，不是给人读的心得。** */
  var SAME_ORIGIN_POSSIBLE = /^https?:$/.test(location.protocol);

  /* 实际走的是哪条通道 —— 要显示在页脚，不能让人以为看到的都是同一条来的 */
  var transport = api ? "Electron IPC" : "同源 HTTP";

  function getJson(url) {
    return fetch(url, { headers: { accept: "application/json" }, cache: "no-store" })
      .then(function (r) {
        if (!r.ok) {
          var e = new Error("HTTP " + r.status + " " + url);
          e.status = r.status;
          throw e;
        }
        return r.json();
      });
  }

  /* 兜底链：preload IPC → 同源 /api/h1 → 本机回环直连 127.0.0.1:8765/api/h1。
     三条都拿不到 ⇒ 如实报「取不到」，**不许绿**。
     🔴 2026-09-22 更正（原注释写着「内嵌反代当前实测 404」——**那句已经过期，别再照它推理**）：
     反代已修好，现读实测 `GET /gbt-master/api/capabilities` → 200、64433 字节，
     与直连 `127.0.0.1:8765/api/capabilities` **逐字节相同**。
     当初 404 的真因是**路由报名次**（静态前缀路由抢在反代前面），不是"反代不生效"。
     所以现在的实际走向是：宿主内**同源那条就是通的**，第三条（回环直连）只是留着的明面兜底。 */
  function callApi() {
    if (api) return api();
    /* 前提不成立就不试同源那条（`file://` 下它必然 ERR_FAILED）——
       顺带把 transport 标成实际走的那条，页脚读数才不撒谎。 */
    if (!SAME_ORIGIN_POSSIBLE) {
      transport = "本机直连 8765";
      return getJson(LOOPBACK_API);
    }
    return getJson(HTTP_API).catch(function () {
      return getJson(LOOPBACK_API).then(function (r) {
        transport = "本机直连 8765";
        return r;
      });
    });
  }

  function setTransport() {
    var el = $("h1-stage");
    if (el) el.textContent = "阶段一 · 本机只读 · 通道：" + transport;
  }

  function $(id) { return document.getElementById(id); }

  function setBadge(el, state, text) {
    if (!el) return;
    el.dataset.state = state || "gray";
    el.textContent = text || "";
  }

  function clear(node) { while (node && node.firstChild) node.removeChild(node.firstChild); }

  /* 🔴 **路径掩码**（2026-09-23 第 33 轮）：屏上不许出现**带用户名的本机绝对路径**。
     AGENTS.md「运行安全 · Exposure Protection」写着不要暴露内部地址、端口、配置；
     而 `C:\\Users\\<用户名>\\…` 里就带着主人的用户名。
     为什么做在**这两个渲染出口**上、而不是逐个字段：逐个字段靠人记得，迟早漏一个
     —— 实测就是这么漏的：`二进制` 与 `目录` 两处都直接铺了后端给的 path 字段。
     收在出口 ⇒ 以后新加字段**自动**被掩码，不需要谁记得。
     保留末三段的理由：掩码是"不给内部信息"，不是"不给信息" ——
     `…\\gbt_allinone\\bin\\h1mcp.exe` 仍然告诉人这是哪个二进制。 */
  function maskPath(v) {
    var t = String(v);
    if (!/[A-Za-z]:\\/.test(t)) return t;
    var parts = t.split("\\").filter(function (x) { return x !== ""; });
    if (parts.length <= 3) return "…\\" + parts.slice(-2).join("\\");
    return "…\\" + parts.slice(-3).join("\\");
  }

  function row(cells, dim) {
    var tr = document.createElement("tr");
    if (dim) tr.className = "gbt-dim";
    cells.forEach(function (v) {
      var td = document.createElement("td");
      td.textContent = maskPath((v === null || v === undefined || v === "") ? "—" : String(v));
      tr.appendChild(td);
    });
    return tr;
  }

  function kv(host, pairs) {
    if (!host) return;
    clear(host);
    pairs.forEach(function (p) {
      var k = document.createElement("div"); k.className = "h1-k"; k.textContent = p[0];
      var v = document.createElement("div"); v.className = "h1-v";
      v.textContent = maskPath(p[1]);
      host.appendChild(k); host.appendChild(v);
    });
  }

  function shaLabel(b) {
    if (!b.sha256) return "未读到";
    var tail = b.sha_match === true ? "（与侧车一致）"
      : b.sha_match === false ? "（与侧车不一致）" : "（无侧车可比）";
    return b.sha256.slice(0, 16) + "…" + tail;
  }

  function render(r) {
    var ok = r && r.ok === true;
    var body = ok ? r.data : (r && r.panel) || null;
    if (!body) {
      setBadge($("h1-badge"), "fault", "取不到");
      setBadge($("h1-foot-badge"), "fault", "取不到");
      if ($("h1-note")) $("h1-note").textContent = "取不到：" + ((r && r.error) || "面板无载荷");
      return;
    }
    var b = body.binary || {};
    /* 🔴 声明数据新鲜度（2026-09-23 第 34 轮）：本窗走 IPC 实时取数。
       写普通全局 `window.GBT_DATA`，**与铬的注入顺序无关**（铬每秒读一次）。 */
    window.GBT_DATA = { kind: "实时", at: new Date().toISOString() };
    var ready = body.badge === "ok";
    setBadge($("h1-badge"), body.badge || "gray",
      ready ? "就绪" : (b.present ? "部分就绪" : "未就绪"));
    setBadge($("h1-foot-badge"), body.badge || "gray", body.stage || "stage1");
    if ($("h1-note")) $("h1-note").textContent =
      maskPath((ok ? "" : "取不到：" + ((r && r.error) || "面板无载荷") + " —— ") + (body.note || ""));
    kv($("h1-binary"), [
      ["二进制", b.path || "—"],
      ["存在", b.present ? "是" : "否"],
      ["大小", b.bytes ? b.bytes + " B" : "—"],
      ["版本", b.tag || "未登记"],
      ["sha256", shaLabel(b)],
      ["状态", b.reason || (b.present ? "已就位" : "取不到")],
    ]);
    var credBody = $("h1-cred-body");
    clear(credBody);
    ((body.credentials && body.credentials.items) || []).forEach(function (c) {
      credBody.appendChild(row([c.name, c.role, c.configured ? "已配置" : "未配置",
        c.read_by ? ("读取者：" + c.read_by) : "备注：h1mcp v0.1.4 不读取此名"], false));
    });
    if (credBody && !credBody.firstChild) credBody.appendChild(row(["—", "—", "未取", "—"], true));
    if ($("h1-sensitive")) $("h1-sensitive").textContent = body.sensitive_note || "";
    (body.api_surfaces || []).forEach(function (s) {
      var el = $("h1-" + s.id);
      if (el) el.textContent = "○ " + (s.title || s.id) + "：" + (s.reason || s.state || "未接入");
    });
    var d = body.drafts || {};
    kv($("h1-drafts"), [
      ["目录", d.path || "—"],
      ["状态", d.initialized ? "已初始化" : (d.reason || "未初始化")],
      ["草稿数", d.initialized ? String(d.count) : "—"],
    ]);
    var db = $("h1-draft-body");
    clear(db);
    (d.files || []).forEach(function (f) {
      db.appendChild(row([f.name, f.title, f.program_handle, f.bytes,
        f.mtime ? f.mtime.replace("T", " ").slice(0, 19) : (f.parse_error || "")], false));
    });
    if (db && !db.firstChild) {
      db.appendChild(row([d.initialized ? "（空）" : "未取", "—", "—", "—", d.reason || "—"], true));
    }
  }

  function refresh() {
    setTransport();
    if (!api && typeof fetch !== "function") {
      setBadge($("h1-badge"), "fault", "无通道");
      setBadge($("h1-foot-badge"), "fault", "无通道");
      if ($("h1-note")) $("h1-note").textContent =
        "既没有 preload 的 h1() 只读口，也没有 fetch —— 判定为取不到，不显示绿。";
      return;
    }
    if (api && bridge.readonly !== true) {
      setBadge($("h1-badge"), "fault", "非只读");
      if ($("h1-note")) $("h1-note").textContent = "preload 未声明只读 —— 拒绝渲染。";
      return;
    }
    callApi().then(function (r) {
      setTransport();   /* 兜底链可能换了通道，落定后再刷页脚 —— 显示的必须是真走的那条 */
      /* 只读声明**两条路都要过**：IPC 看 bridge.readonly（上面已查），
         HTTP 看服务端回的 body.readonly。谁没声明就不给渲染。 */
      var body = (r && r.ok === true) ? r.data : (r && r.panel);
      if (body && body.readonly !== true) {
        setBadge($("h1-badge"), "fault", "非只读");
        setBadge($("h1-foot-badge"), "fault", "非只读");
        if ($("h1-note")) $("h1-note").textContent =
          "数据源未声明 readonly:true —— 拒绝渲染（通道：" + transport + "）。";
        return;
      }
      render(r);
    }).catch(function (err) {
      setBadge($("h1-badge"), "fault", "异常");
      setBadge($("h1-foot-badge"), "fault", "异常");
      if ($("h1-note")) $("h1-note").textContent =
        transport + " 调用异常：" + String((err && err.message) || err);
    });
  }

  var btn = $("btn-h1-refresh");
  if (btn) btn.addEventListener("click", refresh);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", refresh);
  else refresh();
})();
