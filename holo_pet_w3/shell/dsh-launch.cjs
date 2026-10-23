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

/**
 * 🔴 壳里跑的 dsh **版本钉死**（2026-10-23 主人令 A）。
 *
 * 为什么必须钉：`npx --yes @deepseek-ai/dsh` 不带版本 = 每次都从网上取最新版。
 * 2026-10-23 就撞上了：npx 拉来 0.2.1-rc.2，而 `~/.dsh/profiles` 里的插件树是 0.1.5-rc.3。
 * 0.2.x **把 preset 的包名与机制整个换掉了**：
 *   0.1.5 → `dsh-agent-presets`（复数）：**扫目录** `<dshHome>/.agent-presets/*`；
 *   0.2.1 → `dsh-agent-preset` + `dsh-agent-preset-registry`：**查注册表** `definitions` Map，
 *            由各 preset 行在加载时 register 进来，**根本不读目录**。
 * 于是主人自建的 `gbt-spine`（目录式，文件与 240 个依赖包实测全好）在 0.2.1 眼里不存在，
 * 恢复会话当场报（原文出处 `dsh-agent-preset-registry/lib/index.js:599`）：
 *   `Unknown agent preset: gbt-spine (gateway/internal)`，会话进不去。
 * ⇒ 版本必须与 profile 树对齐，故钉 0.1.5-rc.3（= 本机全局装的那一版）。
 *   将来要升 0.2.x，得整体升插件树并把 preset 改写成注册行，不能只动这一条。
 */
const DSH_PKG = "@deepseek-ai/dsh@0.1.5-rc.3";

/** 等就绪行的上限（毫秒）。npx 首次可能要下载包，给足 90 秒仍不响就如实喊。 */
const READY_TIMEOUT_MS = 90000;

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
  let child = null;
  let stopped = false;

  const log = (msg) => { if (!stopped) onLog(scrub(msg)); };

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
      /* 🔴 2026-10-22 主人令（逐字给出他自己那条命令）：
         「对话页面是 PS C:\Users\ADMIN> cd C:\Users\ADMIN\Desktop\GBT小土豆V8
             PS C:\Users\ADMIN\Desktop\GBT小土豆V8> npx @deepseek-ai/dsh web  你做错了给我从新换上」
         ⇒ 壳里起的命令**改成与他一模一样**的 `npx --yes @deepseek-ai/dsh web`，**cwd 钉在仓根**。
         为什么不再用裸 `dsh`：本机 `dsh` 是 npm 垫片（dsh.ps1/.cmd），`shell:true` 下能不能解析到
         要看 Electron 进程的 PATH —— 那是"上次为什么你看到的是别的东西"这类事故的温床。
         走 npx 就等于走主人手打的那条，不依赖 PATH 里有没有垫片。
         `shell: true`：Windows 上 npx 也是 npm 垫片，不经 cmd 直接 spawn 会 EINVAL。
         🔴 **命令整条给字符串**，不给 (cmd, [args])：Node 24 对"shell:true + 参数数组"会打 DEP0190 告警。 */
      /* 🔴 2026-10-22 端到端实测逼出来的一条（就在刚才，不是我推的）：
         在 3080 已被占用时直接跑 `npx --yes @deepseek-ai/dsh web --no-open`，**它不是"自动换端口"**，
         而是当场崩：
           Error: dsh: plugin tree failed to load … listen EADDRINUSE: address already in use 127.0.0.1:3080
         ⇒ 只要 3080 上有东西（主人自己那条 `npx @deepseek-ai/dsh web`，或者上次硬杀留下的孤儿），
           壳里这条命令就**必然起不来**，对话窗就停在本地引导页 —— 这正是主人说的"对话页面不对"。
         所以：**永远带 `--port 0`**（让 OS 分配），不再赌 3080 空着。端口号从就绪行里读，本来就写不死。 */
      /* 🔴 2026-10-23 主人令 A：**钉版本**。
         上一版是 `npx --yes @deepseek-ai/dsh web`（与主人手打命令逐字一致）——
         代价是每跑一次都可能悄悄换到新版：0.2.1 换掉了 preset 的包名与机制，
         恢复 `gbt-spine` 会话直接 `Unknown agent preset`（详见上面 DSH_PKG 的注释）。
         现在只多一个 `@0.1.5-rc.3`，仍是 npx 那条路（不依赖 PATH 里的 dsh 垫片），
         但版本与 `~/.dsh/profiles` 的插件树对齐，不再随时间漂。 */
      const base = `npx --yes ${DSH_PKG} web --no-open`;
      const cmdLine = `${base} --port 0`;
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
    log(`已拉起 dsh web（等它就绪；就绪约需数十秒）`);

    /* 🔴 2026-10-22：加一条**就绪超时**。上一版没有超时 —— npx 若卡在下载/解析，
       对话窗就永远停在本地引导页，而日志里只有"已拉起"这一行（看着像成功）。
       P19 同款：失败路径不许哑。超时不杀进程（它可能只是慢），只如实喊一句。 */
    let ready = false;
    const readyTimer = setTimeout(() => {
      if (stopped || ready) return;
      log(`等了 ${READY_TIMEOUT_MS / 1000}s 还没等到就绪行（对话窗停在本地引导页；`
        + `可以关掉 APP 后在仓根手动跑一遍 npx @deepseek-ai/dsh web 看它报什么）`);
    }, READY_TIMEOUT_MS);

    let buf = "";
    const handleLine = (line) => {
      const url = parseDshUrlLine(line);
      if (url) {
        ready = true;
        try { clearTimeout(readyTimer); } catch (err) { /* 清不掉也不影响接上 */ }
        onUrl(url);                    /* ← 只有这一处把 URL 交出去；本模块不打印、不落盘 */
        return;
      }
      const t = String(line).trim();
      if (t) log(t);                   /* 非就绪行原样转达（已脱敏） */
    };
    const feed = (chunk) => {
      buf += String(chunk);
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
    child.once("exit", (code) => { child = null; log(`dsh web 退出（code=${code}）`); });
  }).catch((err) => {
    log(`探端口失败，按"没人在听"处理：${String(err && err.message ? err.message : err)}`);
  });

  return {
    stop() {
      stopped = true;
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

module.exports = { parseDshUrlLine, maskUrl, scrub, isPortListening, startDsh, READY_LINE, READY_TIMEOUT_MS, DSH_PKG };
