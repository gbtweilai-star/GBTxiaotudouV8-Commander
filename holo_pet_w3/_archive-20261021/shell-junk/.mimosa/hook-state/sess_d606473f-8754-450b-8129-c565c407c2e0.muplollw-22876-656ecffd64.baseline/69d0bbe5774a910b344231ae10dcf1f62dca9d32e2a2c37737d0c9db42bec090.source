/* GBT小土豆V8 · 上帝视角（W3）· **宿主内桥降级垫片**
 *
 * 为什么要有这一件：
 *   `window.js` 的全部读数走 `window.gbtW3` —— 那是 **Electron preload 暴露的只读 IPC 桥**
 *   （主进程侧 handler：`w3:state / tasks / env / ledger / health / matrix / mindmap / selfcheck`）。
 *   在 DSH 宿主里那条桥**根本不存在** ⇒ 六窗按 `noBridge()` 如实报「没有接上宿主进程 —— 取不到」，
 *   于是主人在宿主里看到的是一张**静态壳**。这不是它坏了，是那条桥只长在 Electron 里。
 *
 * 本件干什么：**只在桥缺失时**，用宿主 HTTP 端点补上**同名方法面**，形状与原桥一致（`{ok, data}`）。
 *   ⇒ `window.js` 一行都不用改；它既有的降级逻辑照旧生效（取不到就如实说取不到）。
 *
 * 🔴 铁律：**能对上的才接，对不上的如实报缺**。
 *   绝不拿"看起来像"的端点冒充 —— 那会把「没接上」伪装成「接上了」，比不接更坏。
 *
 * 映射（每条都注明为什么接得上 / 为什么接不上）：
 *   mindmap ← 宿主 `GET /gbt-master/w3/mindmap`  —— 与 Electron **同源**：
 *             同一份 `gbt_allinone/docs/GBT全项目思维导图.md` 里的同一个 markmap 块。
 *             （那份文件在 `DENY` 名单里，静态路由永远发不出去；由**宿主自己读**再发，
 *               所以静态面一个字节都没放宽。⚠️ 该路由住在 host.js，要等 DSH 重启才生效。）
 *   state   ← 宿主 `GET /gbt-master/api/state`    —— 形状合适（每键一个子系统读数）。
 *   tasks / env / ledger / matrix / health / selfcheck
 *           ← **如实报缺**：宿主端点里没有 `.cluster` 任务、没有 `{services:{名:{up}}}`、
 *             没有 `audit_tail`、没有矩阵 `rows`、没有健康 `records` —— 一条都没有对应读数。
 *
 * 本件**只读**：只做 GET，不发任何写请求；不含任何执行路径（不碰能力位、不碰 run_task）。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
(function () {
  'use strict';
  if (window.gbtW3) return;                    // Electron 壳里桥是真的 —— 一个字都不动它

  /* 同源那条要按**当前处在哪个源**算（与 `brain.html` / 其它面板同一条实测教训）：
     宿主里页面挂在 /gbt-master/fs/… 下 ⇒ 必须走 /gbt-master/…；写裸路径打到的是 DSH 自己的口。 */
  var UNDER_HOST = location.pathname.indexOf('/gbt-master/') === 0;
  var BASE = UNDER_HOST ? '/gbt-master' : '';
  var MODE = UNDER_HOST ? 'host-http' : 'no-host';

  /* 🔴 先读**本页自己的 CSP**，再决定发不发请求。
     为什么必须有这一步（我第一版漏了，实测吃了 8 条控制台错）：
       这一页的 CSP 是 `default-src 'none'; … connect-src 'none'` —— **离线自包含是它的硬保证**
       （设计上它走 Electron IPC，IPC 不受 CSP 管）。垫片一上来就 fetch ⇒ 浏览器**逐条拒绝**并
       往控制台喷红字；而"被 CSP 拒"与"端点没起"是两件事，混成一条会误导人。
     判据只能是**读 meta**，不能"先 fetch 试试看" —— 试一次就喷一条红字，页面不再干净。
     ⚠️ 要不要放宽这条 CSP 是**主人的安全口径决定**，不是垫片能自己定的：垫片只负责如实说明。 */
  var CSP_META = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
  var CSP = CSP_META ? String(CSP_META.getAttribute('content') || '') : '';
  var CONNECT_SELF_OK = /connect-src[^;]*('self'|\*|https?:|\/)/i.test(CSP);
  var HTTP_OK = UNDER_HOST && (CSP === '' || CONNECT_SELF_OK);

  function miss(name, why) {
    return Promise.resolve({
      ok: false,
      error: '宿主内没有这条数据路（' + name + '）：' + why +
             ' —— 如实报缺，不拿别的端点冒充。',
    });
  }

  /* 宿主注入的数据件（`<script src="…/w3/data.js">` 带进来的 `window.GBT_W3_DATA`）。
     它可能**晚于本件**到达（script 顺序由宿主包装路由决定）⇒ 取的时候现读，不缓存。 */
  function injected() {
    var d = window.GBT_W3_DATA;
    return (d && typeof d === 'object') ? d : null;
  }

  function cspBlocked(path) {
    return Promise.resolve({
      ok: false,
      error: '本页 CSP 是「' + (CSP || '(无 connect-src)') + '」⇒ 浏览器**拒绝任何网络取数**' +
             '（离线自包含是这一页的设计保证，所以它原生走 Electron IPC，不走 HTTP）。' +
             '要让它在宿主内取到数据，得先在**主人**那边定口径：' +
             '① 把 connect-src 放宽到 \'self\'（仅同源、不出网）；或 ' +
             '② 保持 CSP 不动，由**宿主把数据直接注进页面**（不产生任何 fetch）。' +
             '在那之前本垫片**不发请求**（不发就不会喷 CSP 红字）。目标端点：' + BASE + path,
    });
  }

  function getJson(path) {
    if (!UNDER_HOST) {
      return miss(path, '本页不在宿主路由下（' + location.pathname + '），Electron 桥也没注入');
    }
    if (!HTTP_OK) return cspBlocked(path);
    return fetch(BASE + path, { cache: 'no-store', headers: { accept: 'application/json' } })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + BASE + path);
        return r.json();
      })
      .catch(function (e) {
        return { ok: false, error: BASE + path + ' 取不到：' + ((e && e.message) || e) };
      });
  }

  window.gbtW3 = {
    /* 项目树：优先吃宿主注入的数据件（`window.GBT_W3_DATA`，来自 `/gbt-master/w3/data.js`）。
       为什么优先它：那是宿主**读盘读出来的同一份 markmap 块**，且页面**零 fetch**
       —— 本页 CSP `connect-src 'none'`，fetch 一律被浏览器拒。 */
    mindmap: function () {
      var d = injected();
      if (d && d.mindmap) return Promise.resolve(d.mindmap);
      // 回落 HTTP 那条在**本页 CSP 下必被拒**，所以措辞要说全：
      // 真因通常是"注入件里还没有这一块"（宿主路由要等 DSH 重启才生效），
      // 而不是"CSP 坏了"。**两件事分开说**，读的人才不会误判。
      if (!HTTP_OK) {
        return Promise.resolve({
          ok: false,
          error: '项目树取不到：宿主数据件里还没带 mindmap 块（宿主路由 `w3/data.js` 要等 DSH 重启生效）；' +
                 '回落 HTTP 那条又被本页 CSP（' + (CSP || 'connect-src none') + '）拒掉 —— 两条都不通，如实报缺。',
        });
      }
      return getJson('/w3/mindmap');
    },

    /* 面板 state：同上优先吃注入件；注入件里没有才回落 HTTP（会被 CSP 挡，届时如实说明） */
    state: function () {
      var d = injected();
      if (d && d.state) {
        if (d.state.ok === false) return Promise.resolve(d.state);
        return Promise.resolve({ ok: true, data: d.state.data });
      }
      return getJson('/api/state').then(function (j) {
        if (j && j.ok === false) return j;
        return { ok: true, data: j };
      });
    },

    /* 交流视野（第 56 轮 · 顾问席三栏之②）：本会话的**事件/工具流尾部**（只读）。
       来源与项目树同一份宿主数据件（`window.GBT_W3_DATA.stream`），页面**零 fetch**。 */
    stream: function () {
      var d = injected();
      if (d && d.stream) {
        var s = d.stream;
        return Promise.resolve(s && s.ok === false ? s : { ok: true, data: (s && s.data) || s });
      }
      return miss('交流视野', '宿主数据件里还没带 stream 块（要等宿主侧那一段上线）');
    },

    /* ↓ 下面这些**没有**对应读数 —— 如实报缺，每条写清缺的是什么形状 */
    tasks:     function () { return miss('任务清单', '宿主端点里没有 .cluster 那份任务的读数'); },
    env:       function () { return miss('受管服务', '宿主端点里没有 {services:{名:{up}}} 形状的读数'); },
    ledger:    function () { return miss('审计尾部', '宿主端点里没有 audit_tail 形状的读数'); },
    matrix:    function () { return miss('故障矩阵', '宿主端点里没有 rows 形状的读数'); },
    health:    function () { return miss('健康记录', '宿主端点里没有 records 形状的读数'); },
    selfcheck: function () { return miss('自检', '宿主内没有这条数据路'); },

    /* 交流视野 · 顾问席（第 43 轮）：读的是**只追加的建议账**
       （`gbt_allinone/store/advisor/<席位>.jsonl`），由宿主读盘后随数据件一起发下来。
       ⚠️ 契约是 **`{ok, data}` 两层**（`window.js` 的渲染一律过 `unpack()`）——
          我第一版把 `{ok, seats}` 一层就递过去，实测渲染成「无读数」（卡在页面上、
          0 报错，但读数是空的）。**结构对不上，比取不到还难发现。**
       本席**没有任何写口/执行口** —— 见 `tools/codex-scripts/advisor-audit.py` 的四条判据。 */
    advisors: function () {
      var d = injected();
      if (d && d.advisors) {
        var a = d.advisors;
        return Promise.resolve(a && a.ok === false
          ? a
          : { ok: true, data: (a && a.data) || a });
      }
      return miss('顾问席建议账', '宿主数据件里还没带 advisors 块（要等宿主侧那一段上线）');
    },

    /* 配置：不是读数，是**口径**（Engine 走 auto 探测，只读） */
    config: function () {
      return Promise.resolve({ ok: true, data: { engine: 'auto', readonly: true, mode: MODE } });
    },
  };

  /* 自报：让"这张页面跑的是哪条路、有没有被 CSP 挡住"一眼可见（截图/控制台都能读） */
  window.__gbtHostShim = { mounted: true, mode: MODE, base: BASE, http_ok: HTTP_OK, csp: CSP };
  try {
    document.documentElement.dataset.gbtBridge = MODE + (HTTP_OK ? '' : '-csp-blocked');
  } catch (e) { /* 拿不到 documentElement 就算了，不影响读数 */ }
})();
