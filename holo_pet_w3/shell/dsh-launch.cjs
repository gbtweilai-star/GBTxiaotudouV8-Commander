/* GBT小土豆V8 · 桌面壳 · DeepSeek Harness 自接入（**纯逻辑 + 一个 spawn**）
 *
 * 为什么单独抽成模块：这里有一条**必须能单测**的解析（对话面 URL 就绪行）。
 * 它要是留在 `main.cjs` 里，而 `main.cjs` 第一行就 `require("electron")` ——
 * 就只能靠"我看着对"。抽出来后 `tests/test_dsh_launch.cjs` 直接钉死每条接受/拒绝。
 *
 * 它做什么（主人令 2026-10-07「把 DeepSeek Harness 接进本壳」）：
 *   壳自己把 `dsh web` 拉起来（`--no-open`：不要在主人系统浏览器里再开一份），
 *   读它**就绪时打印的那一行**，把那条 URL 交给调用方去载。
 *
 * 🔴 三条纪律（与 `main.cjs` 的 `w3ConnectDsh` 同一套，别再写第二套）：
 *   ① **URL 只进内存**：本模块只 `onUrl(url)` 交出去，不落盘、不写回执；
 *   ② **不回显**：本模块自己打的每一行都过 `scrub()` —— 日志里永不带 token；
 *   ③ **不起第二个实例**：端口已在听就**不自起**（两个实例会抢同一份会话状态），
 *      让主人仍走原来那条"贴带 token 的 URL"的路。
 *
 * 不进 `main.cjs` 的 `SHELL_SOURCES` 守卫面 —— 它不监听、不注入、不代理对话协议；
 * 只 `spawn` 官方那条命令，与"URL + 公开 HTTP"同一条纪律。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const net = require("node:net");
const { spawn } = require("node:child_process");

/** `dsh web` 就绪那一行的形状（现读自 dsh-web-app：`console.log("dsh web: " + url)`）。 */
const READY_LINE = /dsh web:\s*(https?:\/\/\S+)/i;

/** 把文本里的 token 抹掉 —— **任何**要出到日志/界面的行都必须先过这里。 */
function scrub(text) {
  return String(text == null ? "" : text).replace(/token=[^\s&"']+/gi, "token=***");
}

/**
 * 解析就绪行 → 带 token 的那条 URL；不是就绪行 / 缺 token 一律返回 `null`。
 * **缺 token 也当失败**：那条 URL 载进来只会回 401（实测），不如不接。
 */
function parseDshUrlLine(line) {
  const m = READY_LINE.exec(String(line == null ? "" : line));
  if (!m) return null;
  let u;
  try {
    u = new URL(m[1]);
  } catch (err) {
    return null;
  }
  if (!u.searchParams.get("token")) return null;
  return u.toString();
}

/** 给日志/回执用的脱敏形态：`http://127.0.0.1:3080/?token=***`。 */
function maskUrl(raw) {
  let u;
  try {
    u = new URL(String(raw == null ? "" : raw));
  } catch (err) {
    return "(非法 URL)";
  }
  return scrub(u.toString());
}

/** 本机某端口有没有人在听（`false` = 可以自起）。只连回环，不出网。 */
function isPortListening(port, host, timeoutMs) {
  return new Promise((resolve) => {
    const sock = net.connect({ port: Number(port), host: host || "127.0.0.1" });
    let done = false;
    const fin = (v) => {
      if (done) return;
      done = true;
      try { sock.destroy(); } catch (err) { /* 只为关连接，关不掉也不影响判定 */ }
      resolve(v);
    };
    sock.setTimeout(Number(timeoutMs) || 400);
    sock.once("connect", () => fin(true));
    sock.once("timeout", () => fin(false));
    sock.once("error", () => fin(false));
  });
}

/**
 * 起一条 `dsh web` 并等它就绪。
 *
 * @returns {{stop: Function}} —— 拿到的当下**还没起**（先探端口，异步），
 *   结果一律通过 `onUrl` / `onLog` 回报；`stop()` 幂等，关闭时调一次即可。
 *   `spawnImpl` / `probeImpl` 只为单测注入（生产不传）。
 */
function startDsh(opts) {
  const o = opts || {};
  const port = Number(o.port) || 3080;
  const host = o.host || "127.0.0.1";
  const onUrl = typeof o.onUrl === "function" ? o.onUrl : () => {};
  const onLog = typeof o.onLog === "function" ? o.onLog : () => {};
  const spawnImpl = o.spawnImpl || spawn;
  const probeImpl = o.probeImpl || isPortListening;
  /* 心跳间隔（可注入，只为单测能 30ms 跑一遍；生产用默认 15s） */
  const heartbeatMs = o.heartbeatMs === 0 ? 0 : (Number(o.heartbeatMs) || 15000);
  let child = null;
  let stopped = false;
  let gotBytes = 0;          /* 收到多少字节 —— 用来区分「在装依赖」与「真卡死」 */
  let waiting = true;        /* 还没命中就绪行 */
  let hb = null;
  const t0 = Date.now();

  const log = (msg) => { if (!stopped) onLog(scrub(msg)); };
  const stopHeartbeat = () => {
    waiting = false;
    if (hb) { clearInterval(hb); hb = null; }
  };

  probeImpl(port, host).then((busy) => {
    if (stopped) return;
    /* 🔴 端口已占用怎么办 —— 这一条是**实测逼出来的**，不是推演：
       2026-10-07 我第一次端到端实测就撞上了：上一次被**硬杀**（不是正常退出）的测试
       留下一个孤儿 `dsh web` 一直占着 3080，于是"已在听⇒不自起"这条兜底让脚本干等到超时。
       推理到壳上就是：主人某次强关过 APP ⇒ 孤儿占着 3080 ⇒ 本壳**永远**接不上对话面，
       而那个孤儿的 token 谁也拿不到（token 是进程内的，不落盘）。
       ⇒ 所以：**不去动**那个已在跑的，改用 OS 分配的端口（`--port 0`）起我们自己一个。
         代价是可能多一个**空闲**实例（它俩读的是同一个 ~/.dsh 会话库，官方 CLI 本身就带
         `--port` 可指定/可为 0）；收益是"对话面永远接得上"。这买卖划算。 */
    const busyNote = busy
      ? `${host}:${port} 上已经有服务在听（可能是我这边上次被硬杀留下的孤儿）—— 不去动它，改用 OS 分配的端口另起一个`
      : null;
    if (busyNote) log(busyNote);
    try {
      /* `shell: true`：Windows 上 `dsh` 是 npm 的 `dsh.cmd` 垫片，
         不经 cmd 直接 spawn 会 EINVAL（Node 对 .cmd 的改动）。
         🔴 **命令整条给字符串**，不给 (cmd, [args])：实测（2026-10-07 端到端）
         Node 24 对"shell:true + 参数数组"会打 DEP0190 弃用告警（参数不做转义，只拼接）——
         落进主人的控制台就是一行莫名其妙的警告。本命令的参数全是**写死的字面量**，
         但既然整条字符串同样正确且不告警，就用它。

         🔴🔴 2026-10-26 换成 `npx --yes @deepseek-ai/dsh`（主人令，逐字给的启动方式）。
           实测本机**版本割裂**：全局 `dsh` 是 **0.1.5-rc.3**，而 `npx @deepseek-ai/dsh`
           已是 **0.2.1-rc.2**。壳若继续用全局那条，就是拿旧 CLI 去连主人用新 CLI 起的实例 ——
           协议/配置不兼容（B2 那条「settings.yaml 从 684 键变 3 键」的架构迁移正是 0.2.x 做的）。
           ⇒ **版本对齐比省那 1~2 秒重要**：跟主人用同一条命令、同一个版本。

         🔴 `--yes` **不是可选项**：npx 首次见到未缓存的包会**交互式问**
            "Need to install the following packages … Ok to proceed? (y)"；
            而壳的 stdin 是 `ignore`，等不到那个 y ⇒ 进程挂在那儿、就绪行永远不来、
            对话面永远停在「等壳把引擎拉起来」。`--yes` 就是让它别问。
            （`tests/test_dsh_launch.cjs` 钉着这条，别把 `--yes` 顺手删掉。）

         🔴 **钉版本，不跟 latest**（2026-10-26 加）：
            不带版本号的 `npx @deepseek-ai/dsh` 会**拉 registry 的最新版** ——
            实测同一天里全局包是 0.1.5-rc.3、而 npx 拉到 0.2.1-rc.2；
            哪天官方发 0.3.0，壳会**自动跳过去**，行为和配置架构可能又变一次
            （0.2.x 就把 `~/.dsh/settings.yaml` 迁走了，B2 因此红过）。
            ⇒ 钉到主人 2026-10-26 实测确认可用的那一版；**主人升级 DSH 时改这里**。 */
      /* 🔴 2026-10-26（主人选定权限档后）加 `--profile gbt-official`：
           0.2.x 把配置迁进了 profile —— 全局 `~/.dsh/settings.yaml` 已不存在，
           `danger-full-access` 只剩在 `profiles/gbt-official/settings.yaml` 里。
           壳若还跑默认的 `web` profile，就等于**悄悄把主人的权限档降了**（他自己不知道），
           表现为对话里处处要授权。主人 2026-10-26 明确选：走 gbt-official。

         🔴 `web` 不是"子命令"，是 `--profile web` 的语法糖 —— 实测两条：
           `dsh web --help` 打出来的用法是 `Usage: dsh --profile web [options]`；
           而 `dsh --profile gbt-official web` 直接报
           `error: too many arguments. Expected 0 arguments but got 1: web`。
           ⇒ 换了 profile 就**不能再写 web**，否则起来就退。

         ⚠️ 已知代价（实测，不是推测）：gbt-official 里有两行插件是按 **0.1.5** 编的，
            在 0.2.1 下会被禁用并打印 `incompatible with dsh 0.2.1-rc.2`：
              插件行 `webhook-runtime`、插件行 `hooks-codex`
            🔴 包全名**故意不写在这里**：守卫 B5 不许壳源出现 DSH 内部包路径，写了就红
               （本注释真红过一次）。要看包名去
               `~/.dsh/profiles/gbt-official/cordis.patch.yml`。
            对照实测：改用**全局 dsh 0.1.5**（`dsh --profile gbt-official --no-open`）
            则两个插件全保留、11.0s 就绪。主人若在意这两个插件，就把下面 DSH_CLI
            那一行换成全局 `dsh` —— **只需改这一行**，其余逻辑不动。 */
      const DSH_PROFILE = "gbt-official";
      const DSH_PKG = "@deepseek-ai/dsh@0.2.1-rc.2";
      const DSH_CLI = "npx --yes " + DSH_PKG + " --profile " + DSH_PROFILE;
      const cmdLine = busy ? DSH_CLI + " --no-open --port 0" : DSH_CLI + " --no-open";
      child = spawnImpl(cmdLine, {
        shell: true,
        windowsHide: true,
        stdio: ["ignore", "pipe", "pipe"],
        env: o.env || process.env,
        cwd: o.cwd || undefined,
      });
    } catch (err) {
      log(`dsh 起不来：${String(err && err.message ? err.message : err).slice(0, 160)}`
        + `（对话窗停在本地引导页，主路照常）`);
      return;
    }
    log(`已拉起 dsh web（等它就绪；包已在缓存里约需数十秒，首次/缓存缺失时要装依赖，可能要几分钟）`);

    /* 🔴 心跳：**这一条是 2026-10-26 实测逼出来的**。
       现象：`npx … --version` 跑 60 秒**一个字节都不吐**，我一度判成"链路卡死"。
       查 npm 调试日志（`%LOCALAPPDATA%\npm-cache\_logs`）才看清：它在下 tarball，
       单个包 24s / 39s / 70s（npmmirror CDN），2400+ 行 packument 重新解析 ——
       **它在干活，只是不出声**。而壳这边没有任何进度，主人的观感就是"死了"。
       ⇒ 每 N 秒说一句"仍在等"，并把"零输出"这点讲明：
         零输出 = npx 还在装依赖（正常），有输出但没就绪行 = dsh 已在启动。
         两者的处置完全不同，所以必须分开报。 */
    if (heartbeatMs > 0) {
      hb = setInterval(() => {
        if (stopped || !waiting) { stopHeartbeat(); return; }
        const sec = Math.round((Date.now() - t0) / 1000);
        if (gotBytes === 0) {
          log(`仍在等就绪（已 ${sec}s，**一行输出都没有** —— npx 多半在装依赖，属正常，继续等；`
            + `想知道它在干什么就看 npm-cache\\_logs 最新那份日志是否还在增行）`);
        } else {
          log(`仍在等就绪（已 ${sec}s，已收到 ${gotBytes} 字节，还没出现就绪行）`);
        }
      }, heartbeatMs);
      if (hb.unref) hb.unref();        /* 不许因为一条心跳把测试/退出吊住 */
    }

    let buf = "";
    const handleLine = (line) => {
      const url = parseDshUrlLine(line);
      if (url) {
        stopHeartbeat();               /* 接上了就没必要再念 */
        onUrl(url);                    /* ← 只有这一处把 URL 交出去；本模块不打印、不落盘 */
        return;
      }
      const t = String(line).trim();
      if (t) log(t);                   /* 非就绪行原样转达（已脱敏） */
    };
    const feed = (chunk) => {
      const s = String(chunk);
      gotBytes += s.length;
      buf += s;
      let i;
      while ((i = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, i).replace(/\r$/, "");
        buf = buf.slice(i + 1);
        handleLine(line);
      }
      if (buf.length > 65536) buf = buf.slice(-4096);   /* 无换行的输出不许吃内存 */
    };
    child.stdout.on("data", feed);
    child.stderr.on("data", feed);
    child.once("error", (err) => log(`dsh 进程出错：${String(err && err.message ? err.message : err)}`));
    child.once("exit", (code) => { child = null; stopHeartbeat(); log(`dsh web 退出（code=${code}）`); });
  }).catch((err) => {
    log(`探端口失败，按"没人在听"处理：${String(err && err.message ? err.message : err)}`);
  });

  return {
    stop() {
      stopped = true;
      stopHeartbeat();
      const c = child;
      child = null;
      if (!c) return;
      try {
        /* 🔴 **必须收整棵进程树** —— 这条是实测逼出来的（2026-10-07 端到端）：
           `shell: true` 之下我们拿到的是 **cmd.exe** 的 pid，`child.kill()` 只杀那个外壳，
           真正的 `dsh`（node）是它的**孙进程**，会活下来变成孤儿 —— 而且它占着端口、
           token 又在它进程内谁也拿不到 ⇒ 下一次启动会撞上"端口已在听"。
           我就是这么把自己的测试搞出两个孤儿的（3080 与 18884 各一个，实测看见）。
           修法：Windows 上用 `taskkill /T`（T = 连子孙一起）；其他平台 kill 即可。 */
        if (process.platform === "win32" && c.pid) {
          spawnImpl("taskkill", ["/PID", String(c.pid), "/T", "/F"],
                    { windowsHide: true, stdio: "ignore" });
        } else if (!c.killed) {
          c.kill();
        }
      } catch (err) { /* 收不掉也不该拖垮退出；但这会留下孤儿，故把原因说出来 */ 
        try { log(`收 dsh 进程失败（可能留下孤儿）：${String(err && err.message ? err.message : err)}`); }
        catch (err2) { /* 连日志都失败就算了，别再抛 */ }
      }
    },
  };
}

module.exports = { parseDshUrlLine, maskUrl, scrub, isPortListening, startDsh, READY_LINE };
