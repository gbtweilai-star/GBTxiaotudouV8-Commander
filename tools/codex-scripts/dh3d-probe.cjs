/* GBT小土豆V8 · 语音剧场 3D 舞台**数据探针**（真 Electron · 屏幕外 · 只读取证）
 *
 * ## 为什么不能只看截图
 * 截图能证明"画出来了"，但证明不了"模型到底多高、脚在哪、骨有几根" ——
 * 2026-10-18 我就在截图上把"腿进黑"读成了"模型缺腿"，白猜一轮。读数要能量。
 *
 * ## 做法
 * 起一扇**屏幕外**窗口（x=-20000 + skipTaskbar：真绘制、不打扰主人；隐藏窗在 Windows 上不绘制，
 * 截出来是空白帧 —— 那是 shots.cjs 里已经踩过的坑）载剧场页，轮询 `window.GBT_DH3D.info()`
 * 到 ready/failed，打印页面自报读数，再用页面暴露的 `_debug()` 量**当前姿势**下的蒙皮包围盒。
 *
 * ## 用法（在 holo_pet_w3 目录下）
 *   node_modules\electron\dist\electron.exe ..\tools\codex-scripts\dh3d-probe.cjs
 *   ... --pose bind      只看绑定姿势（判"缺件"还是"动作带坏"）
 *   ... --arms z         手臂垂放修正的轴（x|y|z）
 *   ... --shot <png>     同时落一张真壳画面（取证用）
 *   ... --json           机器可读
 * 退出码：0 舞台真就绪 · 1 没就绪/报错
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";
const path = require("node:path");
const fs = require("node:fs");
const url = require("node:url");
const { app, BrowserWindow } = require("electron");

/* 软渲染 WebGL：真 GPU 下 capturePage 偶发 UnknownVizError（实测），软渲染稳定且够量数据 */
app.commandLine.appendSwitch("use-angle", "swiftshader");
app.commandLine.appendSwitch("enable-unsafe-swiftshader");

const argv = process.argv.slice(2);
const arg = (n) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : null; };
const POSEBIND = argv.indexOf("--pose") >= 0;
const ARMS = arg("--arms");
const QUERY = arg("--query");   // 额外查询串（如 drawer=../brain/index.html）
const SHOT = arg("--shot");
const ASJSON = argv.indexOf("--json") >= 0;

const SHELL = path.join(__dirname, "..", "..", "holo_pet_w3");
const PAGE = path.join(SHELL, "voice-theater", "index.html");
const WAIT_MS = 30000;

function done(code, payload) {
  console.log(ASJSON ? JSON.stringify(payload, null, 1) : payload.report);
  app.exit(code);
}

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    x: -20000, y: 0, width: 1400, height: 900, show: true, skipTaskbar: true, frame: false,
    /* backgroundThrottling:false 是**量具能不能量**的关键：窗口挪到屏幕外时 Chromium 会节流
       requestAnimationFrame，动作一帧都不推进 ⇒ 量到的永远是绑定姿势（T-pose），
       而截图却是上一次画出来的姿势 —— 两个读数互相矛盾，人就会去修错的地方（本仓 P1 实录）。 */
    webPreferences: { contextIsolation: true, nodeIntegration: false, webSecurity: true,
                      backgroundThrottling: false, offscreen: false },
  });

  const qs = [];
  if (POSEBIND) qs.push("pose=bind");
  if (ARMS) qs.push("arms=" + ARMS);
  if (QUERY) qs.push(String(QUERY));
  const target = url.pathToFileURL(PAGE).href + (qs.length ? "?" + qs.join("&") : "");

  let loadErr = "";
  try { await win.loadURL(target); } catch (e) { loadErr = String(e && e.message || e); }

  const t0 = Date.now();
  let info = null;
  while (Date.now() - t0 < WAIT_MS) {
    try {
      const raw = await win.webContents.executeJavaScript(
        "window.GBT_DH3D ? JSON.stringify(window.GBT_DH3D.info()) : null", true);
      info = raw ? JSON.parse(raw) : null;      /* 先串化：info() 里有函数，直接回传会 clone 失败 */
    } catch (e) { loadErr = String(e && e.message || e); }
    if (info && (info.status === "ready" || String(info.status).indexOf("load-failed") === 0)) break;
    await new Promise((r) => setTimeout(r, 400));
  }

  /* 量具自证的第一关：动作必须真的被拨动过。
     `ready` 只代表模型进了场，那一刻 mixer 还没推第一帧，量到的是绑定姿势（T-pose）。 */
  await new Promise((r) => setTimeout(r, 1500));

  const BOUNDS_JS = `(function(){
      try {
        var d = window.GBT_DH3D && window.GBT_DH3D._debug ? window.GBT_DH3D._debug() : null;
        if (!d) return { err: "页面没暴露 _debug" };
        var T = window.THREE, box = new T.Box3(), n = 0, has = false;
        d.model.traverse(function (o) {
          if (!o.isMesh) return;
          n += 1;
          if (o.isSkinnedMesh && typeof o.computeBoundingBox === "function") o.computeBoundingBox();
          var bb = o.boundingBox || (o.geometry && o.geometry.boundingBox);
          if (!bb) return;
          has = true; box.union(bb.clone().applyMatrix4(o.matrixWorld));
        });
        if (!has) return { err: "没有可量的网格", meshes: n };
        var c = box.getCenter(new T.Vector3()), s = box.getSize(new T.Vector3());
        /* 地标量具：直接读骨头的世界坐标，判「站着」还是「腿折在头上」。
           判读线（人形常识，写死在这里当判据）：
             脚(y) ≈ 0（±0.05）· 头顶(y) 1.55~1.85 · 手(y) 低于肩 0.35 以上 ·
             手(y) 在 0.55~1.30 之间（垂在身侧，不是举过头顶） */
        var lm = {}, want = ["Hips", "Spine2", "Neck", "Head", "LeftArm", "RightArm",
                             "LeftHand", "RightHand", "LeftUpLeg", "RightUpLeg",
                             "LeftFoot", "RightFoot"];
        want.forEach(function (k) {
          var b = d.bones["mixamorig:" + k] || d.bones["mixamorig" + k] || d.bones[k];
          if (!b) return;
          var p = new T.Vector3();
          b.getWorldPosition(p);
          lm[k] = [+p.x.toFixed(3), +p.y.toFixed(3), +p.z.toFixed(3)];
        });
        return { meshes: n,
          min: [+box.min.y.toFixed(3), +box.max.y.toFixed(3)],
          bottom_y: +box.min.y.toFixed(3),
          top_y: +box.max.y.toFixed(3),
          size: [+s.x.toFixed(3), +s.y.toFixed(3), +s.z.toFixed(3)],
          center_y: +c.y.toFixed(3),
          landmarks: lm,
          cam: [+d.camera.position.x.toFixed(2), +d.camera.position.y.toFixed(2), +d.camera.position.z.toFixed(2)] };
      } catch (e) { return { err: String(e.message || e) }; }
    })()`;
  /* 量两次：t≈2.6s 与 t≈9.6s（同一段 4s 循环里的两个时刻）。
     两次都绿 = 不是"蒙对一帧"；两次差得多 = 动作把她甩得很厉害，也要人看一眼。 */
  async function measure() {
    try { return await win.webContents.executeJavaScript(BOUNDS_JS, true); }
    catch (e) { return { err: String(e && e.message || e) }; }
  }
  /* 确定性拨钟：把动作依次拨到 0 / 1 / 2 / 3 秒各量一次（4s 循环取四个相位）。
     这样不再依赖 rAF 快慢 —— 同一份资产量几次都是同一组读数。 */
  const POSE_JS = (t) => `(function(){
    var D = window.GBT_DH3D;
    if (!D || !D._pose) return { ok: false, why: "页面没暴露 _pose（旧版？）" };
    return { ok: !!D._pose(${t}), t: ${t} };
  })()`;
  const phases = [];
  for (const t of [0, 1, 2, 3]) {
    let applied = { ok: false, why: "未执行" };
    try { applied = await win.webContents.executeJavaScript(POSE_JS(t), true); }
    catch (e) { applied = { ok: false, why: String(e && e.message || e) }; }
    const m = await measure();
    phases.push({ t: t, applied: applied, m: m });
  }
  let bounds = phases[phases.length - 1].m;
  const boundsA = phases[0].m;
  const poseOk = phases.every((p) => p.applied && p.applied.ok === true);
  /* 动作有没有在推进：帧数仍然记下来（给读数留痕，但判据不再依赖它） */
  let liveInfo = null;
  try {
    const raw = await win.webContents.executeJavaScript(
      "window.GBT_DH3D ? JSON.stringify(window.GBT_DH3D.info()) : null", true);
    liveInfo = raw ? JSON.parse(raw) : null;
  } catch (e) { liveInfo = { err: String(e && e.message || e) }; }
  const liveFrames = liveInfo && typeof liveInfo.frames === "number" ? liveInfo.frames : -1;

  /* 抽屉要等：iframe 的 load 是异步的，而且本器要看到"6 秒兜底"那条也走完 */
  await new Promise((r) => setTimeout(r, 7000));
  let drawer = null;
  try {
    const rawD = await win.webContents.executeJavaScript(
      "window.GBT_DRAWER ? JSON.stringify(window.GBT_DRAWER.status()) : null", true);
    drawer = rawD ? JSON.parse(rawD) : null;
  } catch (e) { drawer = { err: String(e && e.message || e) }; }

  let shotOk = null;
  if (SHOT) {
    /* capturePage 在屏幕外窗口上偶发 UnknownVizError（Chromium 视觉层还没准备好）——
       重试三次；三次都不成就要把原话带出来，不许只报"失败"。 */
    let lastErr = "";
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        await new Promise((r) => setTimeout(r, 1200));
        bounds = await measure();                           /* 取数贴着截图，保证"看到的"和"量到的"是同一刻 */
        const img = await win.capturePage();
        fs.writeFileSync(SHOT, img.toPNG());
        shotOk = fs.statSync(SHOT).size;
        lastErr = "";
        break;
      } catch (e) {
        lastErr = String((e && (e.message || e.name)) || e) + "（第 " + attempt + " 次）";
      }
    }
    if (lastErr) shotOk = "失败：" + lastErr;
  }

  const ok = !!(info && info.ok === true);

  /* 地标判据（人形常识，写死；不靠"看着像"）：
       ① 脚踝高度 0 ~ 0.20（脚踩在地上，不是悬空/插地）
       ② 手比颈低 ≥ 0.30（垂在身侧，不是举过头顶）
       ③ 手的高度落在 0.45 ~ 1.35（胯到大臂，不是顶在头上）
       ④ **网格顶面** 1.55 ~ 1.85
     口径留痕（2026-10-19 翻过一次，理由写在这里）：④ 原来拿 `Head` **骨头关节**的高度判，
     但 Head 是颅底关节、静止时就在 1.52 附近，拿它跟"头顶"比永远差 20cm 左右 —— 判据本身错了尺
     （本仓 P1 那一族的第五次）。改成量**网格包围盒顶面**（`Box3.max.y`），那才是"头顶到地面"。
     四个相位（0/1/2/3 秒）全部全绿，才算"这段动作里她一直站得像个人"。 */
  function rowsOf(b) {
    const lm = (b && b.landmarks) || {};
    const g = (k) => (lm[k] ? lm[k][1] : null);
    const feet = [g("LeftFoot"), g("RightFoot")].filter((v) => v !== null);
    const hands = [g("LeftHand"), g("RightHand")].filter((v) => v !== null);
    const neck = g("Neck");
    const top = b && typeof b.top_y === "number" ? b.top_y : null;   /* 网格顶面（米） */
    if (!feet.length || !hands.length || neck === null) return null;
    const footY = Math.max(...feet);
    const handY = Math.max(...hands);
    return [
      ["① 脚踩地（脚踝 ≤0.20）", footY <= 0.20, footY.toFixed(3) + " m"],
      ["② 手比颈低 ≥0.30", neck - handY >= 0.30, "颈" + neck.toFixed(2) + " 手" + handY.toFixed(2)],
      ["③ 手在 0.45~1.35", handY >= 0.45 && handY <= 1.35, handY.toFixed(3) + " m"],
      ["④ 网格顶面 1.55~1.85", top !== null && top >= 1.55 && top <= 1.85, top === null ? "无" : top.toFixed(3) + " m"],
    ];
  }
  function verdict() {
    if (!poseOk) {
      const why = (phases.find((p) => !(p.applied && p.applied.ok)) || {}).applied;
      return "  地标判据：🔴 量具不可信 —— _pose 没把动作拨过去（" +
             JSON.stringify(why) + "），量到的不一定是动作姿势，不许据此判。";
    }
    const lines = [];
    let allGreen = true;
    phases.forEach((p) => {
      const rows = rowsOf(p.m);
      if (!rows) { lines.push("    🔴 t=" + p.t + "s 读不到骨头"); allGreen = false; return; }
      const bad = rows.filter((r) => !r[1]);
      const green = bad.length === 0;
      allGreen = allGreen && green;
      lines.push("    " + (green ? "✅" : "🔴") + " t=" + p.t + "s · " +
        rows.map((r) => r[2]).join(" · "));
      if (!green) bad.forEach((r) => lines.push("        └ 不过：" + r[0] + " = " + r[2]));
    });
    return ["  地标判据（四个相位全绿 = 整段动作都站得像个人；" + (allGreen ? "现在全绿 ✅" : "有红 🔴") + "）"]
      .concat(lines).join("\n");
  }

  const report = [
    "══════════════════════════════════════════════════════════════",
    "  语音剧场 · 3D 舞台探针（真 Electron · 屏幕外 · 只读）",
    "══════════════════════════════════════════════════════════════",
    "  页面     " + target,
    "  加载     " + (loadErr ? "🔴 " + loadErr.slice(0, 140) : "ok"),
    "  舞台     " + (info ? info.status + (info.ok ? " ✅" : " 🔴") : "未读到"),
    "  骨骼     " + (info ? info.bones : "-") + " 根 · 口型骨 " + (info && info.hasJaw ? "有" : "无"),
    "  动作     " + (info && info.clips && info.clips.length ? info.clips.join(" / ") : "无"),
    "  帧数     " + (liveFrames >= 0 ? liveFrames + " 帧（rAF 实跑帧数，仅供参考）" : "未读到"),
    "  拨钟     " + (poseOk ? "已拨到 0/1/2/3 秒（确定性量具）" : "🔴 _pose 拨不动，下面读数不可信"),
    "  量到的    " + (bounds && !bounds.err ? JSON.stringify(bounds) : "取不到：" + (bounds && bounds.err)),
    "  抽屉     " + (drawer ? JSON.stringify(drawer).slice(0, 300) : "（页面没有 GBT_DRAWER）"),
    "  截图     " + (SHOT ? (typeof shotOk === "number" ? SHOT + " · " + shotOk + " 字节" : "🔴 " + shotOk) : "（未要求）"),
    "──────────────────────────────────────────────────────────────",
    "  判读：min[1]/max[1] 是当前姿势下脚底/头顶（米）。头顶≈1.7 且脚底≈0 = 全身在位。",
    verdict()
  ].join("\n");

  done(ok ? 0 : 1, { ok: ok, info: info, bounds: bounds, shot: SHOT || null, report: report });
});
