/* GBT小土豆V8 桌面壳 · 打包覆盖判据（**一处定义**，预检与回归测试共用）
 *
 * ## 为什么要有这一件（2026-09-23 第 31 轮，拿一个真缺口换的）
 *
 * `preflight.cjs` 的 `K:globs` 验的是「**每条** files 规则匹配得到实物」——
 * 方向是**反的**：它验不出「**有扇窗没被任何规则覆盖**」。
 * 实测就真发生了：第 30 轮加了第 8 扇窗（`eye`），把 `eye/` 目录加进了
 * `windows.json`，却**漏了把 `eye` 规则加进 `package.json` 的 `files` 白名单**
 * ⇒ 打出来的包里会**整整少一扇窗**，而当时预检**全绿**（13/0/3）。
 *
 * ⇒ 判据改成从**窗口注册表**出发，逐扇问「你在白名单里吗」；
 *   并且抽成这一份模块 —— 预检（Electron 里跑）与回归测试（node 里跑）**共用同一份**，
 *   不复制第二份（复制必然漂，本仓已经为"两份判据不一致"付过代价）。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";
const path = require("node:path");

/** glob → 正则。
 *
 * 🔴 **必须单趟替换**（2026-09-23 第 35 轮，被一条「按序裁决」的测试当场抓出来）：
 * 原来是链式三步 —— 先替 `双星+斜杠`、再替 `双星`、最后替 `单星`。
 * 第三步会**把第二步刚生成的那段 `点+星` 里的星号再吃一遍**：
 *     `a/**` → `a/点星` → `a/点[^/]*`   ⇒ 编出来既匹配不了子目录、也不是通配。
 * 实测影响：`a/**` 匹配不到 `a/b/c.txt`。真配置里各条都写成「双星斜杠单星」结尾，
 * 恰好绕过了这个坑，所以它一直没露头 —— 但 `!eye/frames/**`（以「双星」结尾）是**会**受影响的形状，
 * 只是恰好只用来排除 `frames/` 下的直接文件，才没出事。
 * ⇒ 一趟过，用**回调**按最长优先选替换，后面的规则不再吃到前面的产物。
 *
 * ⚠️ 本注释里**不许写那三个替换的字面量** —— 里面含 `星号+斜杠`，会把块注释当场结束掉
 * （第 35 轮真踩过：文件语法直接报 `Unexpected token ')'`）。
 */
function rx(pat) {
  const esc = String(pat).replace(/[.+^${}()|[\]\\]/g, "\\$&");
  const body = esc.replace(/\*\*\/|\*\*|\*/g, (m) =>
    (m === "**/" ? "(?:.*/)?" : (m === "**" ? ".*" : "[^/]*")));
  return new RegExp("^" + body + "$");
}

/** 注册表里所有**本地文件窗**（`file` 字段）→ 相对壳根、正斜杠、去掉开头的 `../`。 */
function windowFiles(reg) {
  return ((reg && reg.windows) || [])
    .filter((w) => w && w.file)
    .map((w) => ({ id: w.id, f: String(w.file).replace(/^\.\.\//, "").replace(/\\/g, "/") }));
}

/**
 * 返回**没被任何正向规则覆盖、或被负向规则排除**的窗。
 * `files` 里以 `!` 开头的是排除规则 —— 被排除等于没覆盖（这一点 K:globs 也不管）。
 *
 * 🔴 **不许按文件名回退匹配**（2026-09-23 第 31 轮，被负对照当场抓住）：
 * 第一版照抄了 `K:globs` 的 `r.test(f) || r.test(path.basename(f))`，
 * 于是拿掉 `eye` 规则之后仍然报「全覆盖」—— 因为 `*.html` 命中了 basename `index.html`。
 * 而 electron-builder 的 `files` 是**按相对路径**匹配的（`*.html` 只管根层），
 * 所以那个回退在这里是**纯放水**：判据看着在判，其实一律判绿。
 * ⇒ 本件只按**相对路径**判。负对照（拿掉规则必须报得出）就是为这一条立的。
 */
function uncoveredWindows(files, reg) {
  const pos = (files || []).filter((p) => !String(p).startsWith("!")).map(rx);
  const neg = (files || []).filter((p) => String(p).startsWith("!")).map((p) => rx(String(p).slice(1)));
  const hit = (r, f) => r.test(f);
  return windowFiles(reg).filter((w) => !pos.some((r) => hit(r, w.f)) || neg.some((r) => hit(r, w.f)));
}

/**
 * 按 electron-builder 的语义判**一条相对路径会不会进包**。
 *
 * 语义：规则**按顺序**过，**最后一条命中的说了算**（负规则也是"命中"）。
 * 一条都没命中 ⇒ 不进包（白名单制）。
 *
 * ⚠️ 与 `uncoveredWindows` 的差别：那个只问"有没有正向规则盖住"，
 * 这个要**按序裁决**才能正确处理 `eye/**` 之后再来一条 `!eye/frames/**`。
 */
function includedIn(files, rel) {
  const p = String(rel).replace(/\\/g, "/");
  let verdict = false;
  for (const raw of (files || [])) {
    const neg = String(raw).startsWith("!");
    const pat = neg ? String(raw).slice(1) : String(raw);
    if (rx(pat).test(p)) verdict = !neg;
  }
  return verdict;
}

/** 把一棵树（相对路径数组）过成"会进包的清单"。 */
function resolvePack(files, allFiles) {
  return (allFiles || []).filter((f) => includedIn(files, f));
}

/**
 * 🔴 **内容审计：白名单能匹配到 ≠ 该进包。**
 *
 * 为什么必须有这一格（2026-09-23 第 35 轮实测）：
 * `files` 里有 `eye/**` —— 而 `eye/frames/` 装的是**触手拍的整屏截图**（12 张 / 1.9 MB）。
 * `.gitignore` 早就排除了它们，但**打包白名单从来没跟它同步过** ⇒
 * 打出来的安装包会**带着主人的桌面截图分发**。
 *
 * 判据是"**这是什么**"，不是"规则匹配没匹配到" —— 这也是为什么它得单独立一格：
 * `K:globs`（规则都匹配到实物）与 `K:winfiles`（每扇窗都被覆盖）**都会给它放绿**。
 */
const SHAME = [
  [/^eye\/frames\//, "触手拍的**整屏截图**（主人的屏幕）—— 绝不进包"],
  [/^eye\/frames\.js$/, "描述主人屏幕的帧清单 —— 绝不进包"],
  [/(^|\/)node_modules\//, "依赖目录不该进包（electron-builder 自会处理运行时依赖）"],
  [/(^|\/)__pycache__\//, "Python 编译缓存"],
  [/\.pyc$/, "Python 编译缓存"],
  [/(^|\/)\.git\//, "版本库元数据"],
  [/(^|\/)desktop\.ini$/i, "Windows 目录元数据"],
  [/(^|\/)Thumbs\.db$/i, "Windows 缩略图缓存"],
  [/\.log$/i, "运行日志"],
  [/\.(jpe?g|png)$/i, "位图资源 —— 逐张确认是不是主人的东西（本壳的图都是生成的，别把截图带出去）"],
];

/**
 * 已**逐张判过**「这是我方资产」的位图 —— 每一条都要写清：是什么、哪来的、怎么复核。
 *
 * 为什么要有这个名单，而不是把上面那条位图规则放宽：那条规则挡的是「主人的截图随包分发」
 * （2026-09-23 第 35 轮的真事故）。放宽一次，下次塞进来的截图就没人问了。
 * ⇒ 于是改成**点名制**：进来的位图必须在这里有一行，且带可复核的出处。
 */
const KNOWN_BITMAPS = {
  "build/tray-logo-32.png":
    "托盘/任务栏的品牌图 —— `assets/brand/logo-potato-32.png` 的**逐字节复制**"
    + "（主人令 2026-10-07「这里的 Logo」：原来托盘是 `trayIcon()` 现画的方块）。"
    + "同字节由 `tests/test_tray_logo.cjs` 钉住（含「随便换一张就报红」的负对照）。",
  "digital-human/reference-02.jpg":
    "数字人的**形象参考副本** —— 主人 2026-10-08 给的全身站立参考（736×1248 · 58,648 字节）"
    + "在页面同目录里的**逐字节复制**，页面用它做**1:1 叠加对照**（骨架照它复刻，不是另画一张）。"
    + "登记理由：`*.jpg` 是本仓 SHAME 名单拦的一类（防「主人的截图随包分发」），"
    + "这一张是**主人自己交办的形象件**、且只进数字人窗，故逐张登记放行。"
    + "负对照：任何**未登记**的位图仍会被 `K:packsrc` 判红。",
  "digital-human/digital-human-hero-front.jpg":
    "数字人 **HD 英雄静帧（正面）** —— 本仓生成物（不是截图）：绑骨线 `tools/codex-scripts/blender/dh_rig.py`"
    + "把主人的形象参考网格（`projects/digital-human/out/dh_rigged.glb`）渲染出的 1536×1920 静帧，"
    + "2026-10-08 12:29 落盘（183KB，页面用小件）。复核：同批 190 张帧在 `projects/digital-human/out/frames/`，"
    + "判据 `py -3.14 tools/codex-scripts/dh-rig-check-rig.py --check` C13（英雄静帧 3 张高 1920）。",
  "digital-human/digital-human-hero-3q.jpg":
    "数字人 **HD 英雄静帧（三分之四侧）** —— 同上生成物（168KB）；出处/复核同 front 一条（同一渲染批次）。",
  "digital-human/digital-human-hero-face.jpg":
    "数字人 **HD 英雄静帧（面部特写）** —— 同上生成物（270KB）；出处/复核同 front 一条（同一渲染批次）。",
};

/** 返回 `[{path, why}]`；空数组 = 干净。 */
function auditPack(included) {
  const out = [];
  for (const f of (included || [])) {
    const p = String(f).replace(/\\/g, "/");
    if (KNOWN_BITMAPS[p]) continue;          // 已逐张判过的我方资产（出处写在名单里）
    for (const [re, why] of SHAME) {
      if (re.test(p)) { out.push({ path: p, why: why }); break; }
    }
  }
  return out;
}

module.exports = { rx, windowFiles, uncoveredWindows, includedIn, resolvePack, auditPack, SHAME, KNOWN_BITMAPS };
