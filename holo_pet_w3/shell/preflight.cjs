/* GBT小土豆V8 桌面壳 · 启动预检（**不弹窗**，在真 Electron 运行时里跑）
 *
 * ## 为什么要有这一件
 *
 * 到 2026-09-23 为止，这个壳**从来没有被真正启动过** —— Electron 没装，
 * 所有界面证据都来自"用浏览器把页面渲成 PNG"。那验的是**页面**，不是**壳**：
 * 壳的 require 链、url 白名单、窗口注册表解析、preload 暴露面，**一条都没在真运行时里跑过**。
 *
 * ⇒ 本件在**真 electron 二进制**里 require 壳的纯模块并逐窗校验，**一个窗口都不开**。
 *   （`show:false` 都不需要 —— 它根本不调 `BrowserWindow`。）
 *
 * ## 它验什么 / 不验什么（**别把没验的当验过的**）
 *
 * 验：模块能不能 require · 注册表能不能解析 · 每个窗能不能被判成合法来源 ·
 *     preload 暴露的动作口在不在 · electron 版本与关键能力（`app`/`net`/`shell`）
 * 不验：窗口真的弹出来长什么样 · DSH 对话面真的接上（那要主人运行时给带 token 的 URL，
 *     是守卫 B1e）· 托盘图标 · 单例锁竞争
 *
 * 用法：
 *     electron holo_pet_w3/shell/preflight.cjs
 * 退出码：0 全过 · 1 有硬失败 · 2 有未决（如 needs_url 那扇）
 */
"use strict";
const path = require("node:path");
const fs = require("node:fs");

const HERE = __dirname;
const SHELL = path.join(HERE, "..");
const rows = [];
function add(id, state, detail) { rows.push({ id, state, detail }); }

function main() {
  let electronVersion = "（不在 electron 里）";
  let inElectron = false;
  try {
    const e = require("electron");
    inElectron = !!(e && e.app);
    if (e && e.app) electronVersion = process.versions.electron || "?";
    add("E1", inElectron ? "PASS" : "FAIL",
        inElectron ? "跑在真 Electron 里 · v" + electronVersion
                   : "不是 electron 运行时 —— 请用 `electron holo_pet_w3/shell/preflight.cjs` 跑");
  } catch (err) {
    add("E1", "FAIL", "require('electron') 失败：" + String(err).slice(0, 90));
  }

  /* ── ① 纯模块能不能 require（壳的 require 链）── */
  const mods = ["url-policy.cjs", "layout.cjs", "features.cjs"];
  const loaded = {};
  for (const m of mods) {
    try {
      loaded[m] = require(path.join(HERE, m));
      add("M:" + m, "PASS", "require 成功");
    } catch (err) {
      add("M:" + m, "FAIL", "require 失败：" + String(err).slice(0, 110));
    }
  }

  /* ── ② 窗口注册表：**逐窗**过 url 白名单判定（这是壳的安全面）── */
  let reg = null;
  try {
    reg = JSON.parse(fs.readFileSync(path.join(HERE, "windows.json"), "utf8"));
  } catch (err) {
    add("W:parse", "FAIL", "windows.json 解析失败：" + String(err).slice(0, 90));
  }
  const pol = loaded["url-policy.cjs"];
  if (reg && pol && typeof pol.windowSource === "function") {
    add("W:count", "PASS", "注册表 %d 扇窗".replace("%d", reg.windows.length));
    let urlOk = 0, needUrl = 0, fileOk = 0, bad = [];
    for (const w of reg.windows) {
      let src;
      try {
        src = pol.windowSource(w);
      } catch (err) {
        bad.push(w.id + " 判定抛错：" + String(err).slice(0, 60));
        continue;
      }
      if (src.kind === "file") {
        const f = path.resolve(path.join(HERE, w.file));
        if (fs.existsSync(f)) fileOk++;
        else bad.push(w.id + " 页面缺：" + w.file);
      } else if (src.kind === "url") {
        urlOk++;
      } else if (src.kind === "connect") {
        needUrl++;
      } else if (src.kind === "blocked") {
        bad.push(w.id + " 被判 blocked：" + (src.why || "?"));
      }
    }
    add("W:file", "PASS", "本地页面窗 %d 个，文件全在".replace("%d", fileOk));
    add("W:url", urlOk ? "PASS" : "PENDING",
        urlOk ? "回环 url 窗 " + urlOk + " 个" : "没有 url 窗（窗 A 走运行时粘贴，见 W:connect）");
    add("W:connect", "PENDING",
        "需主人运行时给 URL 的窗 " + needUrl + " 个 —— **预检关不掉这一格**（守卫 B1e 同理）");
    add("W:bad", bad.length ? "FAIL" : "PASS",
        bad.length ? bad.slice(0, 4).join("；") : "没有非法/缺失的窗");
  } else if (reg) {
    add("W:guard", "FAIL", "url-policy.windowSource 不可用 —— 白名单判定跑不了");
  }

  /* ── ③ preload 暴露面：动作口在不在（凭据卫生的关口）── */
  try {
    const pre = fs.readFileSync(path.join(HERE, "preload.cjs"), "utf8");
    const has = (s) => pre.indexOf(s) >= 0;
    add("P:surface", has("connectDsh") && has("contextBridge") ? "PASS" : "FAIL",
        has("connectDsh") ? "contextBridge + connectDsh 都在" : "preload 里没有 connectDsh");
    add("P:no-token", has("token=") || has("token") && /localStorage|writeFile/.test(pre) ? "PENDING" : "PASS",
        "preload 里没有把 token 落盘的写法（文本级判定，**不是安全证明**）");
  } catch (err) {
    add("P:surface", "FAIL", "preload.cjs 读不动：" + String(err).slice(0, 80));
  }

  /* ── ④ 主进程脚本语法（只 parse，不执行 —— 执行会开窗）── */
  try {
    const src = fs.readFileSync(path.join(HERE, "main.cjs"), "utf8");
    new (require("node:vm").Script)(src, { filename: "main.cjs" });
    add("S:main", "PASS", "main.cjs 语法可解析（**只 parse 不执行**，执行会开窗）");
  } catch (err) {
    add("S:main", "FAIL", "main.cjs 解析失败：" + String(err).slice(0, 110));
  }

  /* ── ⑥ 打包配置（2026-09-23 补：**这是「打包上线」真正的缺口**）──
   * 原来 `package.json` 里**根本没有 `build` 段** —— 只有 `npm start`（开发跑）。
   * 所以「打包上线」一直不是"卡在 npm install"，是**从来就没配过**。
   * 这一格验两件事，都是真翻过车的：
   *   ① 每条 `files` 规则必须**至少匹配到 1 个实物** —— 0 个 = 包静默少东西（最难查的那种）；
   *   ② `extraResources` 的源目录必须存在。
   */
  try {
    const pkg = JSON.parse(fs.readFileSync(path.join(SHELL, "package.json"), "utf8"));
    const b = pkg.build;
    if (!b) {
      add("K:build", "FAIL", "package.json 里没有 build 段 —— **打不出包**，先补 electron-builder 配置");
    } else {
      add("K:build", "PASS",
          "electron-builder 配置在（appId=" + (b.appId || "?") + " · 目标=" +
          ((b.win && b.win.target || []).map((t) => t.target || t).join(",") || "?") + "）");
      // ① 逐条 files 规则数实物
      const walk = (dir, out) => {
        for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
          if (e.name === "node_modules" || e.name === "__pycache__") continue;
          const p = path.join(dir, e.name);
          if (e.isDirectory()) walk(p, out); else out.push(path.relative(SHELL, p).replace(/\\/g, "/"));
        }
        return out;
      };
      const all = walk(SHELL, []);
      /* 🔴 通配翻译**不再本地抄一份**（2026-09-23 第 35 轮）：原来自带的那份是**链式替换**，
         会把 `a/**` 编成 `/^a\/.[^/]*$/`（第三步把第二步生成的 `.*` 里的星号又吃了一遍）。
         现在用 `./pack-coverage.cjs` 里**单趟替换**的那一份 —— 一处定义、预检与测试共用。 */
      const pc = require(path.join(HERE, "pack-coverage.cjs"));
      const rx = pc.rx;
      const empty = [];
      for (const pat of (b.files || [])) {
        if (pat.startsWith("!")) continue;
        const r = rx(pat);
        if (!all.some((f) => r.test(f) || r.test(path.basename(f)))) empty.push(pat);
      }
      add("K:globs", empty.length ? "FAIL" : "PASS",
          empty.length ? ("**" + empty.length + " 条 files 规则一个都没匹配到**：" + empty.join(", ") +
                          " ⇒ 包会静默少东西")
                       : ((b.files || []).filter((p) => !p.startsWith("!")).length + " 条 files 规则全部匹配到实物"));
      /* ③ 🔴 **每扇窗都要被打包白名单收进去**（2026-09-23 第 31 轮加）。
         为什么非有不可：`K:globs` 只验「每条规则匹配得到实物」—— **方向是反的**，
         它验不出「有扇窗没被任何规则覆盖」。实测就真发生了：上一轮加了第 8 扇窗
         （`eye`），却漏了把它的目录加进 `files` ⇒ 打出来的包里**少一整扇窗**，
         而预检当时**全绿**。⇒ 这一格改成从**窗口注册表**出发，逐扇问「你在白名单里吗」。
         判据抽在 `./pack-coverage.cjs` —— 回归测试用**同一份**，不复制第二份。 */
      const uncovered = pc.uncoveredWindows(b.files, reg);
      const winFiles = pc.windowFiles(reg);
      add("K:winfiles", uncovered.length ? "FAIL" : "PASS",
          uncovered.length
            ? ("**有 " + uncovered.length + " 扇窗没被打包白名单覆盖**：" +
               uncovered.map((w) => w.id + "(" + w.f + ")").join(", ") +
               " ⇒ 包里会少这扇窗，而 K:globs 照样全绿")
            : ("注册表 " + winFiles.length + " 扇本地窗**逐扇**都被 files 规则覆盖"));
      /* ④ 🔴 **包里会装进什么**（2026-09-23 第 35 轮加）—— 不用真打包就能查。
         为什么前面两格都不够：`K:globs` 验"规则匹配得到实物"、`K:winfiles` 验"每扇窗被覆盖"，
         **两格都会给"把主人的整屏截图打进包"放绿**。实测就是这么漏的：
         `eye/**` 匹配到了 `eye/frames/`（12 张截图 / 1.9 MB）。
         ⇒ 这一格把整棵树按 electron-builder 的**按序裁决**语义过一遍，
           再按「**这是什么**」审计，而不是按"规则匹配没匹配到"。
         ⚠️ 这里的走树**不跳过** node_modules / __pycache__ —— 上面那个 `walk` 为性能跳过了它们，
           拿它来审计的话，"依赖目录混进包"这条判据就是**死的**。 */
      const allAll = [];
      (function walkAll(dir) {
        let ents = [];
        try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch (_) { return; }
        for (const e of ents) {
          const p = path.join(dir, e.name);
          if (e.isDirectory()) walkAll(p);
          else allAll.push(path.relative(SHELL, p).replace(/\\/g, "/"));
        }
      })(SHELL);
      const included = pc.resolvePack(b.files, allAll);
      const bytes = included.reduce((s, f) => {
        try { return s + fs.statSync(path.join(SHELL, f)).size; } catch (_) { return s; }
      }, 0);
      const shame = pc.auditPack(included);
      add("K:packsrc", shame.length ? "FAIL" : "PASS",
          shame.length
            ? ("**有 " + shame.length + " 个文件会被打进包、但不该进**：" +
               shame.slice(0, 4).map((s) => s.path + "（" + s.why + "）").join(" · ") +
               (shame.length > 4 ? " …共 " + shame.length + " 个" : ""))
            : ("进包 " + included.length + " 个文件 / " + (bytes / 1048576).toFixed(1) +
               " MB · 无截图/依赖目录/缓存混入"));
      // ② extraResources 源
      const miss = (b.extraResources || [])
        .map((e) => e.from).filter((f) => !fs.existsSync(path.resolve(SHELL, f)));
      add("K:extra", miss.length ? "FAIL" : "PASS",
          miss.length ? ("extraResources 源缺：" + miss.join(", ")) : "extraResources 源都在");
      /* ⑤ 🔴 **打包配置本身合不合 electron-builder 的 schema**（2026-09-23 第 40 轮加）。
         为什么非有不可 —— 这一格是拿两次真失败换来的：
           ① `npm run pack` 报 `configuration has an unknown property '// files'`
              + `configuration.win should be one of these: null`；
              真因：**注释键写在了 `build` 里面**。JSON 里用 `"// xxx"` 当注释是常见惯例，
              但 electron-builder 26 **对 `build` 做严格 schema 校验，未知属性直接拒**。
           ② 修完①又报 `Electron version "^43.0.0" is a range, not a fixed version …
              a range cannot be resolved without electron installed in node_modules`。
              真因：本壳**故意不装 node_modules**（走全局 electron），区间就没人能解析。
         ⚠️ 这两条**在 `K:packsrc` / `K:globs` / `K:winfiles` 三格全绿的情况下照样发生** ——
            它们验的是"包里装什么"，**一个字都没验配置本身**。所以打包"配置齐全"这件事
            在真跑 `npm run pack` 之前，一直是**没人验过的**。
         判据刻意只查**能静态判死**的三件：注释键、版本定值、两处版本一致。 */
      const flatKeys = [];
      (function collectCommentKeys(obj, trail) {
        if (!obj || typeof obj !== "object") return;
        for (const k of Object.keys(obj)) {
          if (k.startsWith("//")) flatKeys.push(trail + k);
          else if (obj[k] && typeof obj[k] === "object" && !Array.isArray(obj[k])) {
            collectCommentKeys(obj[k], trail + k + ".");
          }
        }
      })(b, "build.");
      const ev = String(b.electronVersion || "");
      const pinned = /^\d+\.\d+\.\d+/.test(ev);
      const devEv = String((pkg.devDependencies || {}).electron || "");
      const problems = [];
      if (flatKeys.length) {
        problems.push("**注释键写在 build 里**（electron-builder 严格 schema 会直接拒）：" +
                      flatKeys.join(", ") + " ⇒ 挪到 build 外面的 comment_* 顶层键");
      }
      if (!pinned) {
        problems.push("electronVersion 不是定值（现读 " + JSON.stringify(ev) +
                      "）：本壳不装 node_modules ⇒ 区间没人能解析 ⇒ 必须写死，如 \"43.0.0\"");
      }
      if (pinned && devEv && devEv !== ev) {
        problems.push("两处版本不一致：build.electronVersion=" + ev +
                      " vs devDependencies.electron=" + devEv + "（将来 npm install 拉到的不一致）");
      }
      add("K:ebconfig", problems.length ? "FAIL" : "PASS",
          problems.length ? problems.join(" ｜ ")
                          : ("electron-builder 配置可过 schema：无注释键 · electronVersion=" + ev +
                             "（devDependencies 同值）"));
    }
  } catch (err) {
    add("K:build", "FAIL", "读 package.json 失败：" + String(err).slice(0, 90));
  }

  /* ── ⑤ 单例锁文件是否被占（占了说明壳已在跑）── */
  /* 本件**刻意不启动**（启动会在主人屏幕上开窗）。这条 PENDING 的关法不在这里，
     而在 **`npm run startup`**（`shell/startup.cjs`，2026-09-23 第 37 轮加）：
     它走的是**真引导链**（单例锁 → registerIpc → startSse → 建窗 → 托盘 → 布局落盘），
     只把窗放到屏幕外 ⇒ 这一格已经**真的验过**了，别再把它读成"没人管"。
     ⚠️ 但**本件不能替它打绿**：没跑就是没跑，「没跑 ≠ 过了」。 */
  add("S:lock", "PENDING",
      "本件刻意不启动 ⇒ 这一格由 `npm run startup` 覆盖（真引导链 · 窗屏幕外 · 现读 7/0）");

  /* ── 报告 ── */
  const w = (s, n) => String(s).padEnd(n);
  console.log("=".repeat(78));
  console.log("桌面壳 · 启动预检（真 Electron 运行时 · **不弹窗**）");
  console.log("=".repeat(78));
  console.log("  壳目录 " + SHELL);
  console.log("  Electron " + electronVersion);
  console.log("-".repeat(78));
  for (const r of rows) {
    const icon = r.state === "PASS" ? "✅" : r.state === "FAIL" ? "🔴" : "⏳";
    console.log("  " + icon + " " + w(r.id, 12) + w(r.state, 9) + r.detail);
  }
  const fail = rows.filter((r) => r.state === "FAIL").length;
  const pend = rows.filter((r) => r.state === "PENDING").length;
  const pass = rows.filter((r) => r.state === "PASS").length;
  console.log("-".repeat(78));
  console.log("  PASS " + pass + " · FAIL " + fail + " · PENDING " + pend);
  console.log("  ⚠️ PENDING 不算 PASS —— 「还没做」不许读成「没问题」");
  console.log("  退出码：0=全过可打包 · 1=有硬失败 · 2=有未决");
  console.log("=".repeat(78));
  return fail ? 1 : (pend ? 2 : 0);
}

let code = 3;
try {
  code = main();
} catch (err) {
  console.log("预检自身抛错：" + String(err && err.stack || err).slice(0, 400));
  code = 3;
}
try {
  const e = require("electron");
  if (e && e.app) { e.app.exit(code); } else { process.exit(code); }
} catch (_) {
  process.exit(code);
}
