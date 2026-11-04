/* GBT小土豆V8 · 思维导图任务指引（Three.js · 霓虹 HUD 版）
 *
 * 2026-11-02 重做（参考主人给的那张霓虹网络图）：
 *   · 黑蓝底 + 发光环节点 + 橙/青双色光缆 + 悬浮步骤卡 + 中央玻璃面板；
 *   · 接到任务先做**意图分析**，再把任务拆成**一步一动作**的精细步骤（注册邮箱这种要细到"打开哪个页、点哪个按钮、填什么"）；
 *   · 每步都带 做法 / 判定 / 卡点 / 备用通道；
 *   · **卡点回路**：标记卡点 → 回「大脑执行层」→ 查资料/核心论文 → 吸收 → 重生成指引 → 触手继续推进。
 *
 * 数据口径（不编）：
 *   · 默认模式 = 框架真在用的六步（理解/计划/执行/验证/留痕/交付，18 条动作）；
 *   · 输入任务后 = 离线意图模板（内置、可审计）+ 可选模型生成（/api/chat，慢，失败会如实说）；
 *   · 模型不可用/超时 ⇒ 明确标注"离线模板"，不假装是模型给的。
 *
 * 交互：拖动旋转 / 滚轮缩放；点步骤节点看详情；标记 data-mindmap。
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

document.documentElement.dataset.mindmap = "imported";

var ORANGE = 0xff9f1c, CYAN = 0x38d2ff, DIMBLUE = 0x2a4d7a;

var TREE = [
  { name: "理解需求", leaves: ["读架构/契约", "危险=终端·转账", "先定验收数字"] },
  { name: "拆解计划", leaves: ["套七步链", "写任务账本", "排好依赖"] },
  { name: "执行落地", leaves: ["run_task 派单", "五处落位", "可用即测"] },
  { name: "验证取证", leaves: ["真跑读数字", "截图/哈希", "失败即修"] },
  { name: "留痕固化", leaves: ["orchestration-ledger", "docs 编号", "CHANGELOG"] },
  { name: "交付报告", leaves: ["给数字不空话", "说清差距", "写剩余阻塞"] }
];

/* ═══ 离线意图模板（可审计：不是神秘猜测，就是规则命中） ═══ */
var INTENT_RULES = [
  {
    re: /(邮箱|email|mailbox|注册账号|注册账户|sign ?up)/i,
    name: "注册邮箱",
    provider: "Gmail / Outlook / QQ邮箱 / 163（按网络可达性选）",
    steps: [
      { title: "定用途与验收", detail: "先写清：这个邮箱干什么用（工作/注册第三方/收验证码）；验收=能登录 + 能收发一封测试邮件。", check: "用途与验收标准写在纸上/账本里。", blocker: "用途说不清", fallback: "按最小用途选：只收验证码就选国内可达的 QQ/163。" },
      { title: "选服务商与网络", detail: "依次试 mail.google.com、outlook.live.com；打不开就换 mail.qq.com 或 mail.163.com。记录哪个页面能加载出注册表单。", check: "注册页出现「创建账号/注册」按钮。", blocker: "页面打不开/地区限制/一直转圈", fallback: "换服务商，或换网络（手机热点）；把失败页面标题记下来。" },
      { title: "打开注册入口", detail: "在服务商首页点「创建账号 / 注册 / Sign up」；QQ邮箱在 mail.qq.com 点右上角「注册」。", check: "出现注册表单（姓名/生日/用户名/密码）。", blocker: "按钮点了没反应/跳到下载 App", fallback: "改用桌面浏览器无痕窗口；或被强制跳 App 就换服务商。" },
      { title: "填写基本信息", detail: "用户名用「名字+数字」避免重名；密码用 12 位以上大小写字母+数字+符号；生日按真实填（找回账号要用）。", check: "每个字段都没有红字报错。", blocker: "用户名总被占用/密码强度不够", fallback: "用户名加年份后缀；密码加到 14 位并避开常见词。" },
      { title: "手机号/备用邮箱验证", detail: "按页面提示填手机号或备用邮箱，接验证码；验证码有时效（通常 5–10 分钟），别重复点发送。", check: "页面提示验证通过或进入下一步。", blocker: "收不到验证码/提示号码已注册", fallback: "等 60 秒重发一次；换备用邮箱验证；不行就换服务商。" },
      { title: "同意条款并提交", detail: "勾选服务条款（先扫一眼隐私条款里数据用途），点「下一步/创建账号」。", check: "出现「账号已创建」或直接进收件箱。", blocker: "提交后白屏/报错码", fallback: "截图报错码，按错误码搜官方帮助页；换浏览器重试一次。" },
      { title: "真发一封测试邮件", detail: "用新邮箱给自己另一个邮箱发一封标题 test 的邮件，再从对方回一封。", check: "收件箱和发件箱都能看到这封 test 邮件。", blocker: "能登录但收不到/发不出", fallback: "查垃圾箱；看服务商状态页；换 SMTP/网页端各试一次。" },
      { title: "安全加固与留痕", detail: "开启两步验证（2FA），绑定恢复邮箱/手机号，保存恢复码；把账号用途写进密码管理器（不要明文贴聊天）。", check: "2FA 已开启，恢复码已存，账号记录可查。", blocker: "2FA 绑定失败/恢复码没保存", fallback: "先保存恢复码再开 2FA；或用备用验证方式。" }
    ]
  },
  {
    re: /(生图|画图|出图|图片|海报|封面|logo|插画)/i,
    name: "生图任务",
    provider: "本地 t2i / 远端 API（先看哪个在线）",
    steps: [
      { title: "定需求与尺寸", detail: "写清主体/风格/尺寸/用途；找 2 张参考图。", check: "需求四要素齐全。", blocker: "风格说不清", fallback: "给参考图代替形容词。" },
      { title: "选通道", detail: "先探本地 t2i 是否在线；离线再走远端 API。", check: "通道返回可用。", blocker: "都离线", fallback: "先出草图，记录阻塞。" },
      { title: "起稿并出图", detail: "按提示词模板写：主体+风格+光线+构图。", check: "出图不糊、主体完整。", blocker: "构图崩", fallback: "降分辨率/换模型重试。" },
      { title: "验收与留痕", detail: "按用途验收（清晰度/文字/版权），落 outputs 并记来源。", check: "文件与来源可追。", blocker: "有版权风险", fallback: "换自有权重/素材。" }
    ]
  },
  {
    re: /(部署|上线|发布|deploy|服务器|端口)/i,
    name: "部署上线",
    provider: "本机服务 / 远端主机",
    steps: [
      { title: "确认目标环境", detail: "写清：部署到哪台机、哪个端口、用什么进程托管。", check: "环境与入口都有名字。", blocker: "环境不明", fallback: "先本地跑通再上远端。" },
      { title: "本地跑通", detail: "启动、健康检查、核心接口冒烟。", check: "/api/ping 或等价健康检查 200。", blocker: "起不来", fallback: "看日志按报错修。" },
      { title: "发布并观测", detail: "传产物/拉镜像，起进程，观测 5 分钟。", check: "关键接口延迟与错误率正常。", blocker: "端口冲突", fallback: "换端口或停旧进程。" },
      { title: "回滚预案与留痕", detail: "写回滚命令；把版本号/时间/负责人落账。", check: "回滚命令可执行。", blocker: "没备份", fallback: "先备份再发布。" }
    ]
  }
];

var GENERIC = {
  name: "通用任务",
  provider: "内置通用模板（命中不到具体意图）",
  steps: [
    { title: "复述任务与验收", detail: "用一句话复述任务，写清验收标准（什么算完成）。", check: "验收标准能量化。", blocker: "需求含糊", fallback: "先做最小可验证版本。" },
    { title: "列信息与依赖", detail: "列出需要的账号/资料/权限/工具，标出先后依赖。", check: "依赖顺序能画成链。", blocker: "缺权限", fallback: "先做不需要权限的部分。" },
    { title: "分步执行", detail: "按依赖顺序一次只做一步，每步留结果。", check: "每步有可检查的产物。", blocker: "某步反复失败", fallback: "记错误→回大脑执行层查资料。" },
    { title: "真跑验证", detail: "按验收标准真跑一次，读数字/看截图。", check: "证据能支撑结论。", blocker: "跑不通", fallback: "缩小范围定位。" },
    { title: "留痕与交付", detail: "写账本/文档，给数字与剩余风险。", check: "别人能按记录复现。", blocker: "记录缺失", fallback: "补记录再交付。" }
  ]
};

var renderer, scene, camera, controls, composer, bloom;
var inited = false, running = false, raf = 0;
var planGroup = null;           // 所有可重建内容的父组
var treeLeaves = 0;
var current = { mode: "tree", intent: "", steps: [], selected: -1, model: false, blocked: {} };
var stepNodes = [];             // {group, data, index}
var treeNodes = [];             // 默认六步：{group, branch}
var cablesByStep = [];          // 每个步骤对应的光缆（执行到哪亮到哪）
var cables = [];                // {curve, mat, tube}
var flowDots = [];              // {dot, curve, t, speed}
var ringSprites = [];
var raycaster = null, pointer = null;
var ui = { input: null, run: null, next: null, model: null, blocker: null, state: null,
  detail: null, progress: null, seg: null };

function esc(s) {
  return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function glowSprite(color, size, opacity) {
  var c = document.createElement("canvas");
  c.width = 128; c.height = 128;
  var ctx = c.getContext("2d");
  var g = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
  g.addColorStop(0, "rgba(255,255,255,.92)");
  g.addColorStop(0.34, "rgba(255,255,255,.22)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
  var tex = new THREE.CanvasTexture(c);
  var m = new THREE.SpriteMaterial({ map: tex, color: color, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false, opacity: opacity || 0.85 });
  var sp = new THREE.Sprite(m);
  sp.scale.set(size, size, 1);
  return sp;
}

/* 悬浮卡：圆角玻璃卡片（标题 + 一行小字），对标参考图里那些浮窗 */
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

/* 卡面：768x288 的高清玻璃卡（左侧色条 + 圆角 + 自动换行的副标题） */
function cardSprite(title, sub, tint, w, h) {
  var W = 768, H = 288;
  var c = document.createElement("canvas");
  c.width = W; c.height = H;
  var ctx = c.getContext("2d");
  roundRect(ctx, 4, 4, W - 8, H - 8, 34);
  var bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "rgba(14, 30, 52, .94)");
  bg.addColorStop(1, "rgba(7, 16, 30, .86)");
  ctx.fillStyle = bg; ctx.fill();
  ctx.strokeStyle = tint; ctx.lineWidth = 3; ctx.stroke();
  // 左侧色条（参考图里每块面板都有一条亮边）
  var grd = ctx.createLinearGradient(0, 30, 0, H - 30);
  grd.addColorStop(0, tint);
  grd.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = grd;
  roundRect(ctx, 26, 30, 9, H - 60, 5); ctx.fill();
  // 顶部小标题
  ctx.font = "600 38px 'Microsoft YaHei', 'JetBrains Mono', sans-serif";
  ctx.fillStyle = "#eaf4ff"; ctx.textBaseline = "middle"; ctx.textAlign = "left";
  ctx.fillText(title, 60, 82);
  // 副标题：按宽度折行（最多两行）
  ctx.font = "400 27px 'Microsoft YaHei', 'JetBrains Mono', sans-serif";
  ctx.fillStyle = "rgba(168, 198, 232, .9)";
  var words = String(sub || "").split(""), line = "", lines = [], maxW = W - 120;
  for (var i = 0; i < words.length; i++) {
    var t = line + words[i];
    if (ctx.measureText(t).width > maxW) { lines.push(line); line = words[i]; if (lines.length >= 2) break; }
    else line = t;
  }
  if (lines.length < 2 && line) lines.push(line);
  lines.slice(0, 2).forEach(function (ln, k) { ctx.fillText(ln, 60, 154 + k * 44); });
  // 右下角小方块装饰（像参考图的 UI 收角）
  ctx.fillStyle = "rgba(255,255,255,.10)";
  ctx.fillRect(W - 96, H - 46, 24, 24);
  ctx.fillRect(W - 64, H - 46, 24, 24);
  var tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  var sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true,
    depthWrite: false, opacity: 0.99 }));
  sp.scale.set(w || 2.9, (h || 1.1), 1);
  return sp;
}

/* 大玻璃面板：标题 + 迷你柱状图（对标参考图里那块 Social Engagement Charts） */
function panelSprite(title, sub, bars, tint, w, h) {
  var W = 1024, H = 512;
  var c = document.createElement("canvas");
  c.width = W; c.height = H;
  var ctx = c.getContext("2d");
  roundRect(ctx, 6, 6, W - 12, H - 12, 46);
  var bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "rgba(10, 24, 44, .94)");
  bg.addColorStop(1, "rgba(5, 12, 24, .88)");
  ctx.fillStyle = bg; ctx.fill();
  ctx.strokeStyle = "rgba(120, 200, 255, .55)"; ctx.lineWidth = 3; ctx.stroke();
  ctx.fillStyle = "#dff0ff"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
  ctx.font = "700 44px 'Microsoft YaHei', sans-serif";
  ctx.fillText(title, 56, 76);
  ctx.font = "400 28px 'Microsoft YaHei', sans-serif";
  ctx.fillStyle = "rgba(150, 185, 220, .9)";
  ctx.fillText(sub, 56, 132);
  // 柱状图
  var n = Math.max(1, bars.length);
  var bw = Math.min(58, (W - 200) / n - 18);
  var baseY = H - 96, maxH = 210;
  var max = Math.max.apply(null, bars) || 1;
  bars.forEach(function (v, i) {
    var bh = Math.max(10, (v / max) * maxH);
    var x = 100 + i * (bw + 18);
    var g2 = ctx.createLinearGradient(0, baseY - bh, 0, baseY);
    g2.addColorStop(0, i % 2 ? "rgba(56, 210, 255, .95)" : "rgba(255, 159, 28, .95)");
    g2.addColorStop(1, "rgba(56, 210, 255, .10)");
    ctx.fillStyle = g2;
    roundRect(ctx, x, baseY - bh, bw, bh, 8); ctx.fill();
  });
  ctx.strokeStyle = "rgba(120, 200, 255, .28)"; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(70, baseY + 2); ctx.lineTo(W - 70, baseY + 2); ctx.stroke();
  ctx.font = "400 24px 'Microsoft YaHei', sans-serif";
  ctx.fillStyle = "rgba(140, 180, 215, .75)";
  ctx.fillText("步骤进度（每格 = 一步）", 56, H - 44);
  var tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  var sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true,
    depthWrite: false, opacity: 0.98 }));
  sp.scale.set(w || 6.4, h || 3.2, 1);
  return sp;
}

/* 进度面板：柱=真实步骤状态（灰=未执行 / 琥珀=已执行 / 红=卡点），不是装饰图 */
function progressPanel(title, sub, states, w, h) {
  var W = 1024, H = 512;
  var c = document.createElement("canvas");
  c.width = W; c.height = H;
  var ctx = c.getContext("2d");
  var tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  function draw(st) {
    ctx.clearRect(0, 0, W, H);
    roundRect(ctx, 6, 6, W - 12, H - 12, 46);
    ctx.fillStyle = "#08121e"; ctx.fill();
    ctx.strokeStyle = "#1d3247"; ctx.lineWidth = 3; ctx.stroke();
    ctx.fillStyle = "#e8f1fb"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
    ctx.font = "600 44px 'Microsoft YaHei', sans-serif";
    ctx.fillText(title, 56, 76);
    ctx.font = "400 26px 'Microsoft YaHei', sans-serif";
    ctx.fillStyle = "#7e93ab";
    ctx.fillText(sub, 56, 128);
    var n = Math.max(1, st.length);
    var bw = Math.min(54, (W - 200) / n - 14);
    var baseY = H - 96, maxH = 210;
    var COL = { todo: "#1b2c3f", active: "#ffb02e", done: "#ffb02e", blocked: "#d2453f" };
    var BORD = { todo: "#24384d", active: "#ffb02e", done: "#ffb02e", blocked: "#d2453f" };
    st.forEach(function (s, i) {
      var bh = s === "todo" ? 46 : maxH * 0.55 + (i % 3) * 46;
      var x = 100 + i * (bw + 14);
      ctx.fillStyle = COL[s] || COL.todo;
      roundRect(ctx, x, baseY - bh, bw, bh, 6); ctx.fill();
      ctx.strokeStyle = BORD[s] || BORD.todo; ctx.lineWidth = 2;
      roundRect(ctx, x, baseY - bh, bw, bh, 6); ctx.stroke();
    });
    ctx.strokeStyle = "#1d3247"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(70, baseY + 2); ctx.lineTo(W - 70, baseY + 2); ctx.stroke();
    var started = st.filter(function (x) { return x !== "todo"; }).length;
    var done = st.filter(function (x) { return x === "done"; }).length;
    ctx.font = "400 24px 'Microsoft YaHei', sans-serif";
    ctx.fillStyle = "#7e93ab";
    ctx.fillText("已开始 " + started + " / " + st.length + " 步 · 完成 " + done, 56, H - 44);
    tex.needsUpdate = true;
  }
  draw(states || []);
  var sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true,
    depthWrite: false, opacity: 0.98 }));
  sp.scale.set(w || 6.4, h || 3.2, 1);
  return { sprite: sp, redraw: function (st) { draw(st); } };
}

/* 小气泡（参考图里那些浮动的评论/消息气泡） */
function bubbleSprite(txt, tint, w, h) {
  var W = 320, H = 160;
  var c = document.createElement("canvas");
  c.width = W; c.height = H;
  var ctx = c.getContext("2d");
  roundRect(ctx, 6, 6, W - 12, 112, 26);
  ctx.fillStyle = "rgba(10, 22, 40, .9)"; ctx.fill();
  ctx.strokeStyle = tint; ctx.lineWidth = 3; ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(80, 116); ctx.lineTo(70, 148); ctx.lineTo(112, 116);
  ctx.closePath(); ctx.fillStyle = "rgba(10, 22, 40, .9)"; ctx.fill();
  ctx.font = "600 30px 'Microsoft YaHei', sans-serif";
  ctx.fillStyle = tint; ctx.textAlign = "left"; ctx.textBaseline = "middle";
  ctx.fillText(txt, 30, 64);
  var tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  var sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true,
    depthWrite: false, opacity: 0.95 }));
  sp.scale.set(w || 1.5, h || 0.75, 1);
  return sp;
}

function ringNode(color, radius) {
  var R = radius || 0.34;
  var g = new THREE.Group();
  var torus = new THREE.Mesh(new THREE.TorusGeometry(R, 0.03, 10, 56),
    new THREE.MeshBasicMaterial({ color: color, transparent: true, opacity: 0.95,
      blending: THREE.AdditiveBlending }));
  torus.rotation.x = Math.PI * 0.5;
  g.add(torus);
  // 第二层细环（参考图里每个节点是"双环"）
  var ring2 = new THREE.Mesh(new THREE.TorusGeometry(R * 1.55, 0.012, 8, 56),
    new THREE.MeshBasicMaterial({ color: color, transparent: true, opacity: 0.45,
      blending: THREE.AdditiveBlending }));
  ring2.rotation.x = Math.PI * 0.5;
  g.add(ring2);
  var core = new THREE.Mesh(new THREE.SphereGeometry(R * 0.3, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0xffffff }));
  g.add(core);
  var glow = glowSprite(color, R * 6.4, 0.85);
  g.add(glow);
  // 绕行小火花（细节：让节点"在转"）
  var sparks = [];
  for (var s = 0; s < 3; s++) {
    var sp = new THREE.Mesh(new THREE.SphereGeometry(R * 0.09, 6, 6),
      new THREE.MeshBasicMaterial({ color: color }));
    g.add(sp);
    sparks.push({ mesh: sp, a: Math.random() * Math.PI * 2, r: R * 2.2 + s * 0.1,
      speed: 0.6 + Math.random() * 0.5 });
  }
  g.userData = { torus: torus, ring2: ring2, core: core, glow: glow, sparks: sparks, color: color };
  return g;
}

function addCable(a, b, color, bend, thickness) {
  var mid = a.clone().add(b).multiplyScalar(0.5);
  mid.y += bend || 0.6;
  mid.z += (Math.random() - 0.5) * 0.35;
  var curve = new THREE.CatmullRomCurve3([a.clone(), mid, b.clone()], false, "catmullrom", 0.4);
  var dir = b.clone().sub(a);
  var perp = new THREE.Vector3(0, 1, 0).cross(dir).normalize();
  if (perp.lengthSq() < 0.01) perp.set(1, 0, 0);
  var mats = [];
  var offs = [0, 0.07, -0.07];
  offs.forEach(function (off, k) {
    var geo = new THREE.BufferGeometry().setFromPoints(
      curve.getPoints(28).map(function (p) {
        return p.clone().add(perp.clone().multiplyScalar(off)).add(
          new THREE.Vector3(0, 0, (k - 1) * 0.04));
      }));
    var mat = new THREE.LineBasicMaterial({ color: color, transparent: true,
      opacity: k === 1 ? 0.55 : 0.28, blending: THREE.AdditiveBlending, depthWrite: false });
    var line = new THREE.Line(geo, mat);
    planGroup.add(line);
    mats.push(mat);
  });
  // 亮芯
  var coreMat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true,
    opacity: 0.30, blending: THREE.AdditiveBlending, depthWrite: false });
  planGroup.add(new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(curve.getPoints(28)), coreMat));
  mats.push(coreMat);
  var cable = { curve: curve, mats: mats };
  cables.push(cable);
  return cable;
}

function addFlowDots(curve, color, n) {
  for (var i = 0; i < (n || 2); i++) {
    var dot = new THREE.Mesh(new THREE.SphereGeometry(0.045, 8, 8),
      new THREE.MeshBasicMaterial({ color: color }));
    planGroup.add(dot);
    flowDots.push({ dot: dot, curve: curve, t: Math.random(), speed: 0.12 + Math.random() * 0.12 });
  }
}

function clearGroup() {
  if (!planGroup) return;
  while (planGroup.children.length) {
    var o = planGroup.children.pop();
    if (o.geometry) o.geometry.dispose();
    if (o.material) {
      if (o.material.map) o.material.map.dispose();
      o.material.dispose();
    }
  }
  stepNodes = []; treeNodes = []; cablesByStep = []; cables = []; flowDots = []; ringSprites = [];
}

function buildSegs(n) {
  if (!ui.seg) return;
  ui.seg.innerHTML = "";
  for (var i = 0; i < n; i++) {
    var el = document.createElement("i");
    ui.seg.appendChild(el);
  }
  if (window.gsap && n) {
    window.gsap.fromTo(ui.seg.children, { scaleY: 0.3, opacity: 0 },
      { scaleY: 1, opacity: 1, duration: 0.3, stagger: 0.03, ease: "back.out(1.6)" });
  }
}

function updateProgressUI(animate) {
  var n = current.steps.length;
  var done = 0;
  if (ui.seg) {
    for (var i = 0; i < ui.seg.children.length; i++) {
      var el = ui.seg.children[i];
      var st = (current.states && current.states[i]) || "todo";
      if (st === "done") done++;
      el.className = st === "todo" ? "" : ("is-" + st);
    }
  }
  var started = 0;
  (current.states || []).forEach(function (s) { if (s !== "todo") started++; });
  if (ui.progress) ui.progress.textContent = started + " / " + n;
  if (animate && window.gsap && ui.progress) {
    window.gsap.fromTo(ui.progress, { scale: 1.18, color: "#ffb02e" },
      { scale: 1, color: "#e8f1fb", duration: 0.45, ease: "power2.out" });
  }
}

function setState(txt, isErr) {
  if (!ui.state) return;
  ui.state.textContent = txt;
  ui.state.style.color = isErr ? "#ff9f6b" : "";
}

function openPanel() {
  if (!ui.detail) return;
  ui.detail.classList.add("is-on");
  if (window.gsap) {
    window.gsap.fromTo(ui.detail, { y: 8, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.22, ease: "power2.out" });
  }
}

function showTreeDetail(b) {
  if (!ui.detail) return;
  openPanel();
  ui.detail.innerHTML =
    "<h3>" + esc(b.name) + "</h3>" +
    "<div class='idx'>框架六步 · 3 条动作</div>" +
    b.leaves.map(function (x, i) {
      return "<div class='row'><span>" + (i + 1) + "</span><p>" + esc(x) + "</p></div>";
    }).join("") +
    "<div class='row'><span>说明</span><p>默认是框架六步；输入任务会换成该任务的精细步骤。</p></div>";
}

function showDetail(step, idx) {
  if (!ui.detail) return;
  if (!step) { ui.detail.classList.remove("is-on"); return; }
  var blocked = current.blocked[idx];
  openPanel();
  ui.detail.innerHTML =
    "<h3>" + esc(step.title) + "</h3>" +
    "<div class='idx'>步骤 " + (idx + 1) + " / " + current.steps.length + " · " + esc(current.intent) + "</div>" +
    "<div class='row'><span>做法</span><p>" + esc(step.detail) + "</p></div>" +
    "<div class='row'><span>判定</span><p>" + esc(step.check) + "</p></div>" +
    "<div class='row'><span>卡点</span><p>" + esc(step.blocker) + "</p></div>" +
    "<div class='row'><span>备用</span><p>" + esc(step.fallback) + "</p></div>" +
    (blocked ? "<div class='row'><span>已处理</span><p>" + esc(blocked) + "</p></div>" : "");
}

function buildTree() {
  current = { mode: "tree", intent: "任务指引", steps: [], selected: -1, model: false,
    blocked: {}, states: [], active: 0, panel: null };
  clearGroup();
  treeLeaves = 0;
  var center = ringNode(ORANGE, 0.55);
  center.position.set(0, 0, 0);
  planGroup.add(center);
  ringSprites.push(center);
  var title = panelSprite("任务指引 · 框架六步", "理解 → 计划 → 执行 → 验证 → 留痕 → 交付",
    [3, 3, 3, 3, 3, 3], "#ff9f1c", 5.6, 2.8);
  title.position.set(0, 3.4, -1.2);
  planGroup.add(title);

  TREE.forEach(function (b, i) {
    var ang = (i / TREE.length) * Math.PI * 2;
    var bp = new THREE.Vector3(Math.cos(ang) * 7.4, Math.sin(ang) * 5.2 + 0.2,
      Math.sin(ang) * 1.1);
    var color = i % 2 ? CYAN : ORANGE;
    addCable(new THREE.Vector3(0, 0, 0), bp, color, 1.1);
    var node = ringNode(color, 0.26);
    node.position.copy(bp);
    node.userData.tree = b;
    planGroup.add(node);
    treeNodes.push({ group: node, branch: b });
    ringSprites.push(node);
    var lbl = cardSprite(b.name, "分支", i % 2 ? "#38d2ff" : "#ff9f1c", 1.9, 0.72);
    lbl.position.copy(bp).add(new THREE.Vector3(0, 0.85, 0));
    planGroup.add(lbl);
    b.leaves.forEach(function (leaf, k) {
      var la = (k / b.leaves.length) * Math.PI * 2 + i * 0.7;
      var lp = bp.clone().add(new THREE.Vector3(Math.cos(la) * 2.1, Math.sin(la) * 1.6,
        (k - 1) * 0.25));
      addCable(bp, lp, DIMBLUE, 0.3, 0.01);
      var ln = ringNode(0x9fc8ff, 0.1);
      ln.position.copy(lp);
      planGroup.add(ln);
      treeLeaves++;
    });
  });
  current.steps = [];
  var tb1 = bubbleSprite("六步闭环", "#ffb02e", 1.7, 0.85);
  tb1.position.set(-8.6, -1.2, 1.4);
  planGroup.add(tb1);
  var tb2 = bubbleSprite("留痕可追", "#38d2ff", 1.7, 0.85);
  tb2.position.set(8.4, 2.2, 1.2);
  planGroup.add(tb2);
  camera.position.set(0, 1.6, 24.5);
  controls.target.set(0, 0, 0);
  buildSegs(0);
  updateProgressUI(false);
  document.documentElement.dataset.mindmap = "ok:" + TREE.length + "支+" + treeLeaves + "叶";
  if (ui.detail) ui.detail.classList.remove("is-on");
  setState("默认：框架六步（" + treeLeaves + " 条动作）");
}

function layoutStep(i, n) {
  var perRow = 3;
  var row = Math.floor(i / perRow), col = i % perRow;
  var dir = row % 2 === 0 ? 1 : -1;
  var x = (dir === 1 ? -5.0 + col * 3.5 : 4.0 - col * 3.5);
  var y = 2.0 - row * 3.5;
  return new THREE.Vector3(x, y, 0.2 * dir);
}

function buildPlan(intentName, provider, steps, meta) {
  current = { mode: "plan", intent: intentName, steps: steps, selected: -1,
    model: !!(meta && meta.model), blocked: {}, states: steps.map(function () { return "todo"; }),
    active: 0, panel: null };
  clearGroup();
  var n = steps.length;
  var head = layoutStep(-1, n);
  var headPos = new THREE.Vector3(-6.8, 3.4, 0);
  var headNode = ringNode(ORANGE, 0.5);
  headNode.position.copy(headPos);
  planGroup.add(headNode);
  ringSprites.push(headNode);
  var headCard = cardSprite("意图 · " + intentName, provider, "#ff9f1c", 2.9, 1.0);
  headCard.position.copy(headPos).add(new THREE.Vector3(0, 1.35, 0));
  planGroup.add(headCard);

  var prev = headPos.clone();
  steps.forEach(function (s, i) {
    var pos = layoutStep(i, n);
    var color = i % 2 ? CYAN : ORANGE;
    var cable = addCable(prev, pos, color, 0.9 + (i % 3) * 0.2);
    cablesByStep.push(cable);
    addFlowDots(cable.curve, color, 1);
    var node = ringNode(color, 0.3);
    node.position.copy(pos);
    node.userData.step = s;
    node.userData.index = i;
    planGroup.add(node);
    ringSprites.push(node);
    var card = cardSprite("步骤 " + (i + 1) + " · " + s.title, s.check, i % 2 ? "#38d2ff" : "#ff9f1c",
      2.45, 0.88);
    card.position.copy(pos).add(new THREE.Vector3(0, 0.72, 0));
    planGroup.add(card);
    stepNodes.push({ group: node, data: s, index: i, card: card, pos: pos.clone() });
    prev = pos.clone();
  });

  // 卡点回路节点（右下）：卡点 → 大脑执行层 → 查资料/论文 → 吸收 → 重生成
  var blockerPos = new THREE.Vector3(3.0, -4.2, 0.8);
  var blockerNode = ringNode(0xff5c5c, 0.34);
  blockerNode.position.copy(blockerPos);
  planGroup.add(blockerNode);
  ringSprites.push(blockerNode);
  var bCard = cardSprite("卡点？→ 回大脑执行层", "查资料/核心论文 → 吸收 → 重生成指引", "#ff7a7a", 3.2, 1.05);
  bCard.position.copy(blockerPos).add(new THREE.Vector3(0, 0.9, 0));
  planGroup.add(bCard);
  addCable(prev, blockerPos, 0xff5c5c, 1.4);

  // 顶部大面板（对标参考图中央那块图表玻璃板）
  var pp = progressPanel("任务指引 · " + intentName, provider, current.states, 5.4, 2.7);
  pp.sprite.position.set(0, 5.6, -1.8);
  planGroup.add(pp.sprite);
  current.panel = pp;
  // 浮动气泡（参考图里那些小消息窗）
  var bub1 = bubbleSprite("按验收数字推进", "#ffb02e", 1.7, 0.85);
  bub1.position.set(-6.6, 0.9, 1.3);
  planGroup.add(bub1);
  var bub2 = bubbleSprite("卡点就回大脑", "#38d2ff", 1.7, 0.85);
  bub2.position.set(2.6, -2.4, 1.4);
  planGroup.add(bub2);

  camera.position.set(-0.6, 3.0, 22.0);
  controls.target.set(-0.4, -0.6, 0);
  document.documentElement.dataset.mindmap = "plan:" + intentName + ":" + n + "步" +
    (current.model ? ":model" : ":offline");
  // 初始全部灰色（还没执行），点「推进」才逐步点亮
  stepNodes.forEach(function (x, i) { setStepState(i, "todo", true); });
  buildSegs(n);
  updateProgressUI(false);
  setState("意图「" + intentName + "」→ " + n + " 步（" + (current.model ? "模型生成" : "离线模板") +
    "）· 未执行=灰，点「推进」逐步点亮");
  document.documentElement.dataset.mindmapProgress = "0/" + n;
}

/* ═══ 任务 → 步骤：规则意图 + 可选模型 ═══ */
function detectIntent(task) {
  for (var i = 0; i < INTENT_RULES.length; i++) {
    if (INTENT_RULES[i].re.test(task)) return INTENT_RULES[i];
  }
  return GENERIC;
}

function modelPlan(task) {
  var prompt = [
    "你是任务规划器。把用户任务拆成可执行步骤，只输出 JSON（不要解释、不要 markdown）。",
    '结构：{"intent":"意图名","steps":[{"title":"步骤名","detail":"具体到打开哪个网页/点哪个按钮/填什么","check":"怎么判定这一步成功","blocker":"这一步可能卡在哪","fallback":"卡了改走什么通道"}]}',
    "最多 8 步；每步必须具体，禁止空话；不确定的写清楚要查什么。",
    "任务：" + task
  ].join("\n");
  var ctrl = new AbortController();
  var timer = setTimeout(function () { ctrl.abort(); }, 90000);
  return fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: prompt, context: "mind-plan" }),
    signal: ctrl.signal
  }).then(function (r) { return r.json(); }).then(function (d) {
    clearTimeout(timer);
    var txt = String((d && d.text) || "");
    var m = txt.match(/\{[\s\S]*\}/);
    if (!m) throw new Error("模型没回 JSON");
    var j = JSON.parse(m[0]);
    if (!j || !j.steps || !j.steps.length) throw new Error("模型 JSON 缺 steps");
    return { intent: j.intent || detectIntent(task).name, steps: j.steps.slice(0, 8), model: true };
  }).catch(function (e) {
    clearTimeout(timer);
    throw e;
  });
}

function planTask(task) {
  task = String(task || "").trim();
  if (!task) { setState("先输入任务", true); return Promise.resolve(); }
  var useModel = !!(ui.model && ui.model.checked);
  var rule = detectIntent(task);
  setState("分析意图…" + (useModel ? "（等模型，最多 90s）" : ""));
  buildPlan(rule.name, rule.provider + " · 规则命中", rule.steps, { model: false });
  if (!useModel) return Promise.resolve(current);
  return modelPlan(task).then(function (out) {
    buildPlan(out.intent, "模型生成 · /api/chat", out.steps, { model: true });
    return current;
  }).catch(function (e) {
    buildPlan(rule.name, rule.provider + " · 规则命中（模型没回，已如实回退）", rule.steps,
      { model: false });
    setState("模型没回：" + String(e && e.message || e).slice(0, 60) + " → 用离线模板", true);
    return current;
  });
}

var STATE_COLOR = { todo: 0x46536a, active: 0xffb02e, done: 0xffd27a, blocked: 0xd2453f };
var STATE_CARD = { todo: 0xa2b2c6, active: 0xffffff, done: 0xffe9c0, blocked: 0xffb3ad };

/* 执行到哪里亮哪里：todo 灰 / active 暖金 / done 绿 / blocked 红 */
function setStepState(i, state, silent) {
  var sn = stepNodes[i];
  if (!sn) return;
  current.states[i] = state;
  var c = STATE_COLOR[state] || STATE_COLOR.todo;
  var ud = sn.group.userData;
  ud.torus.material.color.setHex(c);
  ud.ring2.material.color.setHex(c);
  ud.glow.material.color.setHex(c);
  (ud.sparks || []).forEach(function (sp) { sp.mesh.material.color.setHex(c); });
  sn.card.material.color.setHex(STATE_CARD[state] || STATE_CARD.todo);
  sn.card.material.opacity = state === "todo" ? 0.68 : 0.99;
  var sc = state === "active" ? 1.16 : (state === "blocked" ? 1.08 : 1);
  sn.group.scale.set(sc, sc, sc);
  setCableState(i, state);
  if (current.mode === "plan") {
    if (current.panel) current.panel.redraw(current.states);
    if (ui.seg) updateProgressUI(false);
  }
  if (!silent) document.documentElement.dataset.mindmapStep =
    "s" + (i + 1) + ":" + state;
}

function setCableState(i, state) {
  var cable = cablesByStep[i];
  if (!cable) return;
  var c = STATE_COLOR[state] || STATE_COLOR.todo;
  var dim = state === "todo" ? 0.35 : 1;
  (cable.mats || []).forEach(function (m, k) {
    m.color.setHex(k === cable.mats.length - 1 ? 0xffffff : c);
    m.opacity = (k === cable.mats.length - 1 ? 0.18 : 0.3) * dim;
  });
}

/* 推进下一步：当前 active 变 done，下一个变 active；全灰未执行的不亮 */
function advance() {
  if (current.mode !== "plan") { setState("先生成任务指引", true); return null; }
  var n = current.steps.length;
  var i = current.active;
  if (i >= n) { setState("全部执行完毕（" + n + "/" + n + "）"); return current; }
  if (current.states[i] === "todo") {
    // 第一步：从未开始 → 点亮（不直接算完成）
    setStepState(i, "active");
    selectStep(i);
    setState("开始执行 · 步骤 " + (i + 1) + "/" + n + "：" + current.steps[i].title);
    updateProgressUI(true);
    document.documentElement.dataset.mindmapProgress = (i + 1) + "/" + n;
    return current;
  }
  if (current.states[i] === "active" || current.states[i] === "blocked") setStepState(i, "done");
  current.active = i + 1;
  if (current.active < n) {
    setStepState(current.active, "active");
    selectStep(current.active);
    setState("执行中 · 步骤 " + (current.active + 1) + "/" + n + "：" + current.steps[current.active].title);
  } else {
    setState("全部执行完毕（" + n + "/" + n + "）");
  }
  updateProgressUI(true);
  if (window.gsap && ui.seg) {
    var seg = ui.seg.children[Math.min(current.active, n - 1)];
    if (seg) window.gsap.fromTo(seg, { scaleY: 1.8 }, { scaleY: 1, duration: 0.35, ease: "power2.out" });
  }
  document.documentElement.dataset.mindmapProgress =
    Math.min(current.active + 1, n) + "/" + n;
  return current;
}

function selectStep(idx) {
  if (idx < 0 || idx >= stepNodes.length) return;
  current.selected = idx;
  stepNodes.forEach(function (sn, i) {
    var data = sn.group.userData;
    var base = i % 2 ? CYAN : ORANGE;
    data.torus.material.color.setHex(i === idx ? 0xffd166 : base);
    data.glow.material.color.setHex(i === idx ? 0xffd166 : base);
    var sc = i === idx ? 1.25 : 1;
    sn.group.scale.set(sc, sc, sc);
  });
  showDetail(stepNodes[idx].data, idx);
}

/* 卡点回路：把"回大脑、查论文、吸收、重生成"画出来，并把备用通道写回步骤 */
function onBlocker() {
  if (current.mode !== "plan") { setState("先生成任务指引再标卡点", true); return; }
  var idx = current.selected >= 0 ? current.selected : 0;
  var step = current.steps[idx];
  if (!step) return;
  var p0 = stepNodes[idx].pos;
  var p1 = p0.clone().add(new THREE.Vector3(1.5, -1.6, -0.6));
  var p2 = p1.clone().add(new THREE.Vector3(2.2, -0.2, 0.4));
  var p3 = p2.clone().add(new THREE.Vector3(2.0, 1.0, 0.4));
  var stages = [
    { p: p1, color: 0xff5c5c, title: "卡点", sub: step.blocker },
    { p: p2, color: 0xffb02e, title: "回大脑执行层", sub: "定位卡点 / 查资料" },
    { p: p3, color: 0x38d2ff, title: "核心论文 · 资料", sub: "读并做知识卡片" }
  ];
  var prev = p0;
  stages.forEach(function (st) {
    addCable(prev, st.p, st.color, 0.8, 0.016);
    var node = ringNode(st.color, 0.22);
    node.position.copy(st.p);
    planGroup.add(node);
    ringSprites.push(node);
    var card = cardSprite(st.title, st.sub, st.color === 0xff5c5c ? "#ff7a7a" :
      (st.color === 0xffb02e ? "#ffb02e" : "#38d2ff"), 2.0, 0.74);
    card.position.copy(st.p).add(new THREE.Vector3(0, 0.6, 0));
    planGroup.add(card);
    prev = st.p;
  });
  // 吸收 → 重生成：一条回到下一步的线
  var nb = stepNodes[idx + 1];
  var back = nb ? nb.pos : p3;
  addCable(prev, back, 0x7dffb0, 1.2, 0.014);
  var absorb = ringNode(0x7dffb0, 0.2);
  absorb.position.copy(p3.clone().add(new THREE.Vector3(1.8, 0.6, 0.2)));
  planGroup.add(absorb);
  var ac = cardSprite("吸收 → 重生成指引", "回到步骤 " + (idx + 1) + " 继续推进", "#7dffb0", 2.0, 0.74);
  ac.position.copy(absorb.position).add(new THREE.Vector3(0, 0.6, 0));
  planGroup.add(ac);
  if (current.mode === "plan") {
    setStepState(idx, "blocked");
    setCableState(idx, "blocked");
    current.active = Math.max(current.active, idx);
  }
  current.blocked[idx] = "卡点已回大脑执行层：查资料/论文 → 吸收 → 重生成；备用通道：" + step.fallback;
  showDetail(step, idx);
  if (window.gsap && ui.detail) {
    window.gsap.fromTo(ui.detail, { x: 0 }, { x: 6, duration: 0.05, repeat: 5, yoyo: true,
      clearProps: "x" });
  }
  updateProgressUI(false);
  setState("卡点已处理：查资料 → 吸收 → 重生成，触手继续推进");
  document.documentElement.dataset.mindmapBlocker = step.title;
}

function wireUI() {
  ui.input = document.getElementById("mind-task");
  ui.run = document.getElementById("mind-run");
  ui.next = document.getElementById("mind-next");
  ui.model = document.getElementById("mind-model");
  ui.blocker = document.getElementById("mind-blocker");
  ui.state = document.getElementById("mind-state");
  ui.detail = document.getElementById("mind-detail");
  ui.progress = document.getElementById("mind-progress");
  ui.seg = document.getElementById("mind-seg");
  if (!ui.input || !ui.run) return;
  if (ui.run.getAttribute("data-wired") === "1") return;
  ui.run.setAttribute("data-wired", "1");
  ui.run.addEventListener("click", function () { planTask(ui.input.value); });
  if (ui.next) ui.next.addEventListener("click", advance);
  ui.input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") planTask(ui.input.value);
  });
  ui.blocker.addEventListener("click", onBlocker);
  setState("待命 · 默认显示框架六步");
}

function init() {
  if (inited) return true;
  var canvas = document.getElementById("mindmap-canvas");
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true,
      preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020814, 0.008);
    camera = new THREE.PerspectiveCamera(46, 1, 0.1, 300);
    camera.position.set(-0.6, 3.0, 22.0);
    camera.lookAt(-0.6, -0.6, 0);

    planGroup = new THREE.Group();
    scene.add(planGroup);

    // 六边形科技地面（对标参考图的透视地板）
    var hex = document.createElement("canvas");
    hex.width = 1024; hex.height = 1024;
    var hctx = hex.getContext("2d");
    var s = 44;
    hctx.strokeStyle = "rgba(70, 160, 230, .28)";
    hctx.lineWidth = 2;
    for (var row = 0; row < 20; row++) {
      for (var col = 0; col < 20; col++) {
        var cx = col * s * 1.5 + (row % 2 ? s * 0.75 : 0);
        var cy = row * s * 0.86;
        hctx.beginPath();
        for (var k = 0; k < 6; k++) {
          var a2 = Math.PI / 3 * k + Math.PI / 6;
          var px = cx + Math.cos(a2) * s * 0.5, py = cy + Math.sin(a2) * s * 0.5;
          if (k === 0) hctx.moveTo(px, py); else hctx.lineTo(px, py);
        }
        hctx.closePath(); hctx.stroke();
      }
    }
    var radial = hctx.createRadialGradient(512, 512, 60, 512, 512, 512);
    radial.addColorStop(0, "rgba(0,0,0,1)");
    radial.addColorStop(0.7, "rgba(0,0,0,.55)");
    radial.addColorStop(1, "rgba(0,0,0,0)");
    hctx.globalCompositeOperation = "destination-in";
    hctx.fillStyle = radial; hctx.fillRect(0, 0, 1024, 1024);
    var hexTex = new THREE.CanvasTexture(hex);
    hexTex.wrapS = hexTex.wrapT = THREE.RepeatWrapping;
    hexTex.repeat.set(3, 3);
    var floor = new THREE.Mesh(new THREE.PlaneGeometry(90, 90),
      new THREE.MeshBasicMaterial({ map: hexTex, transparent: true, opacity: 0.5,
        blending: THREE.AdditiveBlending, depthWrite: false }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -5.6;
    scene.add(floor);
    // 地平光晕
    var horizon = new THREE.Mesh(new THREE.PlaneGeometry(70, 14),
      new THREE.MeshBasicMaterial({ color: 0x0d3a63, transparent: true, opacity: 0.22,
        blending: THREE.AdditiveBlending, depthWrite: false }));
    horizon.position.set(0, -4.6, -18);
    scene.add(horizon);
    // 散景（大而虚的灰白点，参考图里前景的失焦光斑）
    var BOKEH = 70;
    var bpos = new Float32Array(BOKEH * 3);
    for (var bi = 0; bi < BOKEH; bi++) {
      bpos[bi * 3] = (Math.random() - 0.5) * 44;
      bpos[bi * 3 + 1] = (Math.random() - 0.5) * 22;
      bpos[bi * 3 + 2] = -4 - Math.random() * 16;
    }
    var bg2 = new THREE.BufferGeometry();
    bg2.setAttribute("position", new THREE.BufferAttribute(bpos, 3));
    scene.add(new THREE.Points(bg2, new THREE.PointsMaterial({
      size: 1.4, map: glowSprite(0x9fc8ff, 1, 0.5).material.map,
      transparent: true, opacity: 0.18, depthWrite: false,
      blending: THREE.AdditiveBlending, sizeAttenuation: true })));

    // 远景星点
    var DUST = 700;
    var arr = new Float32Array(DUST * 3);
    for (var i = 0; i < DUST; i++) {
      var r = 16 + Math.random() * 26;
      var th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
      arr[i * 3] = r * Math.sin(ph) * Math.cos(th);
      arr[i * 3 + 1] = Math.abs(r * Math.cos(ph)) * 0.5;
      arr[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    }
    var dg = new THREE.BufferGeometry();
    dg.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    scene.add(new THREE.Points(dg, new THREE.PointsMaterial({ color: 0x5f8fc0, size: 0.08,
      transparent: true, opacity: 0.45, depthWrite: false, blending: THREE.AdditiveBlending })));

    var wrap = document.querySelector(".view-mind") || canvas;
    controls = new OrbitControls(camera, wrap);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.22;
    controls.enablePan = false;
    controls.minDistance = 8;
    controls.maxDistance = 48;
    controls.rotateSpeed = 0.7;

    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.42, 0.0, 0.82);
    composer.addPass(bloom);

    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();
    canvas.addEventListener("click", function (e) {
      var r = canvas.getBoundingClientRect();
      pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1;
      pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      var picks = [];
      stepNodes.forEach(function (s) { picks.push(s.group); });
      treeNodes.forEach(function (s) { picks.push(s.group); });
      var hits = raycaster.intersectObjects(picks, true);
      if (hits.length) {
        var node = hits[0].object;
        while (node && node.userData.index === undefined && node.userData.tree === undefined) node = node.parent;
        if (node && node.userData.index !== undefined) selectStep(node.userData.index);
        else if (node && node.userData.tree) showTreeDetail(node.userData.tree);
      }
    });

    resize();
    inited = true;
    wireUI();
    buildTree();
    draw();
    return true;
  } catch (e) {
    document.documentElement.dataset.mindmap = "error:" + String((e && e.message) || e).slice(0, 120);
    return false;
  }
}

function resize() {
  var c = document.getElementById("mindmap-canvas");
  if (!c || !renderer) return;
  var w = c.clientWidth || 600, h = c.clientHeight || 400;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  if (composer) composer.setSize(w, h);
  if (bloom) bloom.resolution.set(w, h);
}

function draw() {
  if (composer) composer.render(); else renderer.render(scene, camera);
}

function loop() {
  if (!running) return;
  raf = requestAnimationFrame(loop);
  var t = performance.now() / 1000;
  // 环节点呼吸 + 轻微转动
  ringSprites.forEach(function (g, i) {
    if (!g.userData || !g.userData.torus) return;
    g.userData.torus.rotation.z = t * (0.4 + (i % 3) * 0.15) + i;
    if (g.userData.ring2) g.userData.ring2.rotation.z = -t * 0.5 + i;
    var k = 1 + 0.06 * Math.sin(t * 1.6 + i);
    g.userData.glow.scale.set(2.2 * k, 2.2 * k, 1);
    (g.userData.sparks || []).forEach(function (sp) {
      sp.a += sp.speed * 0.016;
      sp.mesh.position.set(Math.cos(sp.a) * sp.r, Math.sin(sp.a * 1.3) * sp.r * 0.5,
        Math.sin(sp.a) * sp.r * 0.6);
    });
  });
  // 光缆流光
  flowDots.forEach(function (f) {
    f.t += f.speed * 0.016;
    if (f.t > 1) f.t -= 1;
    f.dot.position.copy(f.curve.getPointAt(Math.min(0.999, f.t)));
  });
  // 执行中的节点：active 脉冲、blocked 红光（执行到哪里亮哪里）
  for (var si = 0; si < stepNodes.length; si++) {
    var sn = stepNodes[si];
    var st = (current.states && current.states[si]) || "todo";
    if (st === "active") {
      var pk = 1.16 + 0.09 * Math.sin(t * 4.2 + si);
      sn.group.scale.set(pk, pk, pk);
      sn.group.userData.glow.scale.set(2.4 * pk, 2.4 * pk, 1);
    } else if (st === "blocked") {
      var bk = 1.08 + 0.05 * Math.sin(t * 6.0);
      sn.group.scale.set(bk, bk, bk);
      sn.group.userData.glow.material.opacity = 0.55 + 0.35 * Math.abs(Math.sin(t * 3.2));
    } else if (st === "done") {
      sn.group.userData.glow.scale.set(2.2, 2.2, 1);
    }
  }

  // 光缆束呼吸
  cables.forEach(function (c, i) {
    var op = 0.16 + 0.26 * (0.5 + 0.5 * Math.sin(t * 0.8 + i * 0.7));
    var mats = c.mats || [];
    mats.forEach(function (m, k) {
      m.opacity = k === mats.length - 1 ? op * 0.7 : op;
    });
  });
  controls.update();
  draw();
}

export function start() { if (!init()) return; if (running) return; running = true; loop(); }
export function stop() { running = false; if (raf) { cancelAnimationFrame(raf); raf = 0; } }

window.__mindmap = {
  start: start, stop: stop,
  plan: planTask,
  advance: advance,
  select: selectStep,
  blocker: onBlocker,
  get ok() { return inited; },
  get current() { return current; },
  get steps() { return current.steps.slice(); }
};
window.addEventListener("gbt:view", function (e) { if (e.detail === "mind") start(); else stop(); });
window.addEventListener("resize", function () { resize(); if (!running && renderer) draw(); });
if ((location.hash || "").replace("#", "") === "mind") setTimeout(start, 60);
