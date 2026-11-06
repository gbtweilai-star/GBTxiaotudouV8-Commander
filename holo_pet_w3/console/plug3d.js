/* GBT小土豆V8 · 万能插（Three.js）v2 —— 插口接真数据 · 可点 · 只读
 * 参考主人视频：数字覆盖的结状管道（数据在交错触手里流动）。
 * 映射（这次是真的映射，不是装饰）：
 *   · 三叶结管道 = 万能插触手本体（任何能力都能插进任何域）；
 *   · 管道表面流动的数字 = 实时 token/事件（数字纹理沿管道流动）；
 *   · 插口 = 能力域，**按 /api/data 的 domains 动态生成**（名称 + 真实计数），不再写死 8 个；
 *   · 每个插口有一根自动插合的触手，尖端脉冲往复（插进/拔出）；
 *   · 中心核 = 调度器（本机指挥官）。
 * 交互：拖动旋转 / 滚轮缩放；**点插口** → 该域能力清单 + 插座状态 + 改动影响（op=impact）。
 * 安全：只调 /api/data、/api/omni?op=sockets、/api/omni?op=impact 三个只读探针；
 *       永不调用 op=fullopen（那会真起进程/真调模型）。插拔与执行仍归主人会话与能力位门。
 * 标记 data-plug3d：imported / ok:N插口+数字结 / error:原因
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

document.documentElement.dataset.plug3d = "imported";

/* 网络不通时的降级名单（保持旧观感，但会明确标注“离线名单”） */
const FALLBACK_SOCKETS = [
  { name: "system", count: null }, { name: "llm", count: null }, { name: "security", count: null },
  { name: "tentacle", count: null }, { name: "mind", count: null }, { name: "recon", count: null },
  { name: "pipeline", count: null }, { name: "video", count: null },
];

const DATA = { domains: [], caps: [], sockets: null, totalDomains: 0, fallback: true };

let renderer, scene, camera, controls, composer, bloom;
let inited = false, initing = null, running = false, raf = 0;
let knotTex, tips = [], picks = [], wrapEl = null;
let currentDomain = "";

function esc(s) {
  return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function getJSON(url) {
  return fetch(url, { cache: "no-store" }).then(function (r) { return r.json(); });
}

/* ───────── 真数据：域 + 能力 + 已插插座（全部只读） ───────── */
function loadData() {
  var p1 = getJSON("/api/data").then(function (j) {
    var d = (j && j.data) || j || {};
    var all = (d.domains || []).slice().sort(function (a, b) { return (b.count || 0) - (a.count || 0); });
    DATA.totalDomains = all.length;
    var doms = (d.domains_top && d.domains_top.length ? d.domains_top : all).slice(0, 14);
    DATA.domains = doms.map(function (x) { return { name: x.domain, count: x.count }; })
      .filter(function (x) { return x.name; });
    DATA.caps = (d.caps && d.caps.items) || [];
  }).catch(function () {});

  var p2 = getJSON("/api/omni?op=sockets").then(function (j) {
    DATA.sockets = (j && j["插着"]) || null;
  }).catch(function () {});

  return Promise.all([p1, p2]).then(function () {
    DATA.fallback = DATA.domains.length === 0;
  });
}

function socketList() {
  return DATA.fallback ? FALLBACK_SOCKETS : DATA.domains;
}

function kindSummary() {
  var out = {}, s = DATA.sockets || {};
  Object.keys(s).forEach(function (k) {
    var kind = (s[k] && s[k].kind) || "?";
    out[kind] = (out[kind] || 0) + 1;
  });
  var keys = Object.keys(out);
  if (!keys.length) return "已插 0";
  return "已插 " + keys.length + " 类 · " + keys.map(function (k) { return k + " " + out[k]; }).join(" / ");
}

/* ───────── 纹理与小件 ───────── */
function digitsTexture() {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 512;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#05070b"; ctx.fillRect(0, 0, 512, 512);
  ctx.font = "500 20px 'JetBrains Mono', monospace";
  ctx.textBaseline = "middle";
  for (let row = 0; row < 22; row++) {
    for (let col = 0; col < 20; col++) {
      const d = String((row * 7 + col * 3 + (row * col) % 10) % 10);
      ctx.fillStyle = (row + col) % 4 === 0 ? "#eaf3ff" : "#9fb8d8";
      ctx.fillText(d, col * 26 + 3, row * 23 + 10);
    }
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = THREE.RepeatWrapping;
  t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(18, 3);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function labelSprite(text, color) {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 96;
  const ctx = c.getContext("2d");
  let size = 34;
  ctx.font = "600 " + size + "px 'JetBrains Mono', monospace";
  while (ctx.measureText(text).width > 492 && size > 18) {
    size -= 2;
    ctx.font = "600 " + size + "px 'JetBrains Mono', monospace";
  }
  ctx.fillStyle = color; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, 256, 48);
  const tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
  sp.scale.set(2.6, 0.5, 1);
  return sp;
}

function glowSprite(color, size, opacity) {
  const c = document.createElement("canvas");
  c.width = 128; c.height = 128;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
  g.addColorStop(0, "rgba(255,255,255,.9)");
  g.addColorStop(0.35, "rgba(255,255,255,.22)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  const m = new THREE.SpriteMaterial({ map: tex, color: color, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false, opacity: opacity || 0.85 });
  const sp = new THREE.Sprite(m);
  sp.scale.set(size, size, 1);
  return sp;
}

function trefoil(t) {
  const s = Math.sin(t), c = Math.cos(t);
  return new THREE.Vector3(
    s + 2 * Math.sin(2 * t),
    c - 2 * Math.cos(2 * t),
    -Math.sin(3 * t)
  ).multiplyScalar(1.15);
}

/* ───────── 兜底：3D 起不来时给字，不给白屏 ───────── */
function fail(msg) {
  var host = document.querySelector(".view-plug") || document.body;
  var fb = document.getElementById("plug3d-fallback");
  if (!fb) {
    fb = document.createElement("div");
    fb.id = "plug3d-fallback";
    fb.style.cssText = "position:absolute;left:50%;top:46%;transform:translate(-50%,-50%);" +
      "max-width:520px;padding:14px 16px;border:1px solid rgba(120,160,220,.35);border-radius:10px;" +
      "background:rgba(6,10,18,.9);color:#cfe0f5;font:13px/1.6 'JetBrains Mono',monospace;" +
      "white-space:pre-wrap;z-index:6;text-align:center";
    host.appendChild(fb);
  }
  fb.textContent = msg;
  fb.hidden = false;
}

/* ───────── 插口详情（DOM，不碰 app.css） ───────── */
function panel() {
  var host = document.querySelector(".view-plug") || document.body;
  var el = document.getElementById("plug-detail");
  if (!el) {
    el = document.createElement("div");
    el.id = "plug-detail";
    el.style.cssText = "position:absolute;left:16px;bottom:16px;width:340px;max-height:62%;overflow:auto;" +
      "padding:10px 12px;border:1px solid rgba(120,160,220,.35);border-radius:10px;" +
      "background:rgba(6,10,18,.9);color:#cfe0f5;font:12px/1.6 'JetBrains Mono',monospace;" +
      "display:none;z-index:6;backdrop-filter:blur(6px)";
    host.appendChild(el);
  }
  return el;
}

function capRows(domain) {
  var caps = DATA.caps.filter(function (c) { return c.domain === domain; });
  if (!caps.length) return "<div style='opacity:.6'>该域在 caps.items 里没有明细</div>";
  return caps.slice(0, 12).map(function (c) {
    return "<div class='pd-cap' data-cap='" + esc(c.name) + "' style='cursor:pointer;padding:2px 0;" +
      "border-bottom:1px dashed rgba(120,160,220,.15)'>" +
      "<u style='color:#9fc3ff;text-decoration:none'>" + esc(c.name) + "</u>" +
      (c.safe ? "" : " <i style='color:#ffb02e;font-style:normal'>非安全位</i>") + "</div>";
  }).join("");
}

function showDomain(name) {
  currentDomain = name;
  var p = panel();
  var dm = null;
  socketList().forEach(function (x) { if (x.name === name) dm = x; });
  var cnt = dm && dm.count != null ? " · " + dm.count + " 个能力" : "";
  p.style.display = "block";
  p.innerHTML = "<div style='display:flex;justify-content:space-between;align-items:center'>" +
    "<b style='color:#eaf3ff'>插口 · " + esc(name) + "</b>" +
    "<span id='pd-close' style='cursor:pointer;opacity:.7'>✕</span></div>" +
    "<div style='opacity:.75;margin:2px 0 6px'>能力域" + esc(cnt) + "</div>" +
    "<div style='opacity:.75;margin-bottom:6px'>插座：" + esc(kindSummary()) + "</div>" +
    "<div style='opacity:.5;margin-bottom:4px'>点能力名 → 看改动影响（1 跳/2 跳）</div>" +
    "<div id='pd-caps'>" + capRows(name) + "</div>" +
    "<div id='pd-impact' style='margin-top:8px'></div>" +
    "<div style='margin-top:8px;opacity:.5;border-top:1px solid rgba(120,160,220,.2);padding-top:6px'>" +
    (DATA.fallback ? "离线名单（/api/data 未取到，插口是旧的 8 个）"
      : "实读 /api/data · 共 " + DATA.totalDomains + " 域，插口显示前 " + socketList().length) +
    " · 只读探针，不触发 fullopen</div>";
  var cl = document.getElementById("pd-close");
  if (cl) cl.addEventListener("click", function () { p.style.display = "none"; });
  Array.prototype.forEach.call(p.querySelectorAll(".pd-cap"), function (row) {
    row.addEventListener("click", function () { showImpact(row.getAttribute("data-cap")); });
  });
}

function showImpact(capName) {
  var box = document.getElementById("pd-impact");
  if (!box) return;
  box.innerHTML = "<span style='opacity:.6'>查影响面 … " + esc(capName) + "</span>";
  getJSON("/api/omni?op=impact&target=" + encodeURIComponent("cap:" + capName) + "&n=6")
    .then(function (j) {
      if (!j || j.ok === false) {
        box.innerHTML = "<div style='color:#e0715c'>影响面不可用：" +
          esc((j && (j.error || j.detail)) || "未知") + "</div>";
        return;
      }
      var pr = j.probe || {};
      var vd = j.verdict || null;
      var colors = { red: "#e0715c", amber: "#ffb02e", green: "#5ad19a", grey: "#8fa6c4" };
      var color = colors[(vd && vd.level) || "grey"];
      var head = pr.in_graph
        ? "1 跳 " + pr.reach1 + " · 2 跳 " + pr.reach2
        : "不在 wiring 图里（新文件或不在扫描范围；撞不到别处 ≠ 安全）";
      var sample = (pr.sample || []).slice(0, 6);
      var rk = (j.ranking || []).slice(0, 3);

      function shortPath(p) {
        var t = String(p == null ? "" : p);
        return t.length > 34 ? "…" + t.slice(-33) : t;
      }

      box.innerHTML =
        "<div style='margin-bottom:4px'><b style='color:#eaf3ff'>" + esc(capName) +
        "</b> <span style='opacity:.7'>· " + esc(head) + "</span></div>" +
        (vd ? "<div style='color:" + color + ";margin-bottom:4px'>" + esc(vd.head) + "</div>" +
              "<div style='opacity:.75;margin-bottom:6px'>" + esc(vd.body) + "</div>" : "") +
        (sample.length
          ? "<div style='opacity:.55;margin-bottom:2px'>1 跳真撞到（前 " + sample.length + "）</div>" +
            sample.map(function (p) {
              return "<div style='opacity:.85'>· " + esc(shortPath(p)) + "</div>";
            }).join("")
          : "") +
        (rk.length
          ? "<div style='opacity:.55;margin:6px 0 2px'>全局最重部位（常驻风险排行，与本次探针无关）</div>" +
            rk.map(function (r) {
              return "<div style='opacity:.65'>· " + esc(r.label) +
                " <i style='opacity:.6;font-style:normal'>" + r.reach + "/" + r.total + "</i></div>";
            }).join("")
          : "") +
        "<div style='opacity:.45;margin-top:4px'>图 " +
        (j.graph ? j.graph.parts + " 节点 / " + j.graph.links + " 边" : "—") + " · 只读探针</div>";
    })
    .catch(function () {
      box.innerHTML = "<div style='color:#e0715c'>影响面请求失败（服务未起或超时）</div>";
    });
}

/* ───────── 场景 ───────── */
function build() {
  if (inited) return true;
  const canvas = document.getElementById("plug3d-canvas");
  if (!canvas) { document.documentElement.dataset.plug3d = "error:no-canvas"; fail("万能插：找不到 canvas。"); return false; }
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true,
      preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x02050a, 0.012);
    camera = new THREE.PerspectiveCamera(46, 1, 0.1, 400);
    camera.position.set(0, 2.5, 20);

    // ── 数字结：三叶结管道 + 流动数字纹理 ──
    const pts = [];
    for (let i = 0; i < 220; i++) pts.push(trefoil((i / 220) * Math.PI * 2));
    const curve = new THREE.CatmullRomCurve3(pts, true, "catmullrom", 0.5);
    knotTex = digitsTexture();
    const knotMat = new THREE.MeshStandardMaterial({
      map: knotTex, color: 0xdbe6f5, metalness: 0.45, roughness: 0.5,
      emissive: 0x9fb8d8, emissiveIntensity: 0.9, emissiveMap: knotTex,
    });
    const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 240, 0.62, 20, true), knotMat);
    scene.add(tube);
    scene.add(glowSprite(0x4f8cff, 6.2, 0.16));

    // ── 万能插口：能力域（实读 domains）→ 同心环座 + 可点拾取球 ──
    const socketMat = new THREE.MeshStandardMaterial({
      color: 0xb9c8dd, metalness: 0.9, roughness: 0.25,
      emissive: 0x1a2b46, emissiveIntensity: 0.6 });
    const tipMat = new THREE.MeshStandardMaterial({
      color: 0xff9a3c, emissive: 0xff6a00, emissiveIntensity: 1.4,
      metalness: 0.25, roughness: 0.35 });
    const pickMat = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false });

    const list = socketList();
    const N = Math.max(1, list.length);
    const R = list.length > 10 ? 7.4 : 6.2;

    list.forEach(function (s, i) {
      const a = (i / N) * Math.PI * 2;
      const pos = new THREE.Vector3(Math.cos(a) * R, Math.sin(a) * R * 0.82, 1.6);
      const socket = new THREE.Group();
      socket.position.copy(pos);
      socket.rotation.z = a;
      for (let r = 0; r < 3; r++) {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(0.46 + r * 0.2, 0.035, 10, 48), socketMat);
        ring.rotation.x = Math.PI / 2;
        socket.add(ring);
      }
      const disc = new THREE.Mesh(new THREE.CircleGeometry(0.42, 32),
        new THREE.MeshBasicMaterial({ color: 0x1d3352, transparent: true, opacity: 0.9 }));
      disc.rotation.x = -Math.PI / 2;
      socket.add(disc);
      const gl = glowSprite(0x5f9bff, 1.4, 0.5);
      gl.position.z = 0.1;
      socket.add(gl);
      const txt = s.name + (s.count != null ? "·" + s.count : "");
      const lb = labelSprite(txt, s.count ? "#cfe0f5" : "#8fa6c4");
      lb.position.set(0, 0, 0.95);
      socket.add(lb);
      lb.userData.domain = s.name;  // 点标签也算点插口
      picks.push(lb);
      scene.add(socket);

      // 拾取球：比环座大一圈，便于点中；不可见
      const pick = new THREE.Mesh(new THREE.SphereGeometry(1.35, 12, 12), pickMat);
      pick.position.copy(pos);
      pick.userData.domain = s.name;
      scene.add(pick);
      picks.push(pick);

      const p0 = new THREE.Vector3(0, 0, 0);
      const p1 = pos.clone().normalize().multiplyScalar(R * 0.5).add(new THREE.Vector3(0.4, -0.6, 0.2));
      const p2 = pos.clone().multiplyScalar(0.92);
      const path = new THREE.CatmullRomCurve3([p0, p1, p2], false, "catmullrom", 0.6);
      const tMat = new THREE.MeshStandardMaterial({
        color: 0x8fa6c4, metalness: 0.8, roughness: 0.3,
        emissive: 0x14213a, emissiveIntensity: 0.5 });
      scene.add(new THREE.Mesh(new THREE.TubeGeometry(path, 60, 0.055, 8, false), tMat));
      const tip = new THREE.Mesh(new THREE.SphereGeometry(0.18, 20, 20), tipMat);
      scene.add(tip);
      tips.push({ tip: tip, path: path, phase: i * 0.6 });
    });

    // ── 中心调度核 ──
    const core = new THREE.Mesh(new THREE.SphereGeometry(0.7, 32, 32),
      new THREE.MeshBasicMaterial({ color: 0xff9f1c }));
    scene.add(core);
    scene.add(glowSprite(0xff9f1c, 4.5, 0.55));

    // ── 外圈星尘 ──
    const DUST = 1200;
    const arr = new Float32Array(DUST * 3);
    for (let i = 0; i < DUST; i++) {
      const r = 11 + Math.random() * 26;
      const th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
      arr[i * 3] = r * Math.sin(ph) * Math.cos(th);
      arr[i * 3 + 1] = r * Math.cos(ph) * 0.8;
      arr[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    }
    const dg = new THREE.BufferGeometry();
    dg.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    scene.add(new THREE.Points(dg, new THREE.PointsMaterial({
      color: 0x6f86a8, size: 0.09, transparent: true, opacity: 0.35, depthWrite: false })));

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const l1 = new THREE.PointLight(0x4f8cff, 2.4, 60); l1.position.set(4, 4, 6); scene.add(l1);
    const l2 = new THREE.PointLight(0xff9a3c, 1.4, 60); l2.position.set(-5, -3, 4); scene.add(l2);

    wrapEl = document.querySelector(".view-plug") || canvas;
    controls = new OrbitControls(camera, wrapEl);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.45;
    controls.enablePan = false;
    controls.minDistance = 7;
    controls.maxDistance = 45;
    controls.rotateSpeed = 0.75;

    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.55, 0.5, 0.62);
    composer.addPass(bloom);

    wirePick();
    wireLegend();

    resize();
    inited = true;
    const fbx = document.getElementById("plug3d-fallback");
    if (fbx) fbx.hidden = true;  // 慢启动后真起来了，把提示收回
    document.documentElement.dataset.plug3d = "ok:" + list.length + "插口+数字结" +
      (DATA.fallback ? "（离线名单）" : "（实读 domains）");
    // HUD 文案跟着真数据走（也让“插口数对不对”在页面上可见，不必猜）
    const hint = document.querySelector(".view-plug .space3d-hint");
    if (hint) {
      hint.textContent = "按住鼠标左键拖动旋转 · 滚轮缩放 · 结=触手本体 · 数字=流动数据 · " +
        list.length + " 插口=能力域" +
        (DATA.fallback ? "（离线名单，/api/data 未取到）"
          : "（实读 /api/data · 共 " + DATA.totalDomains + " 域，插口显示前 " + list.length + "）") +
        " · 点插口看该域能力与改动影响";
    }
    draw();
    return true;
  } catch (e) {
    document.documentElement.dataset.plug3d = "error:" + String((e && e.message) || e).slice(0, 120);
    fail("万能插 3D 起不来：" + String((e && e.message) || e) +
      "\n可能是 WebGL 不可用（检查 chrome://gpu）或 three.js 模块没加载。" +
      "\n插口数据仍可用：多域监控面板与左侧能力面不受影响。");
    return false;
  }
}

/* ───────── 点插口 ───────── */
function wirePick() {
  if (!wrapEl || !wrapEl.addEventListener) return;
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let down = null;

  wrapEl.addEventListener("pointerdown", function (e) {
    down = [e.clientX, e.clientY];
    if (controls) controls.autoRotate = false;  // 要瞄就停一下
  });
  wrapEl.addEventListener("pointerup", function () {
    if (controls) setTimeout(function () { controls.autoRotate = true; }, 1200);
  });
  wrapEl.addEventListener("pointerup", function (e) {
    if (!down) return;
    const dx = e.clientX - down[0], dy = e.clientY - down[1];
    down = null;
    if (Math.sqrt(dx * dx + dy * dy) > 6) return; // 拖动旋转不算点击
    if (!inited) return;
    const canvas = document.getElementById("plug3d-canvas");
    if (!canvas) return;
    const r = canvas.getBoundingClientRect();
    ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1;
    ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(picks, false);
    if (hit && hit.length) showDomain(hit[0].object.userData.domain);
  });
}

/* ───────── 图例联动：点 "llm 43" 也打开该域详情 ───────── */
function wireLegend() {
  const lg = document.getElementById("legend");
  if (!lg || lg.dataset.plugWired === "1") return;
  lg.dataset.plugWired = "1";
  lg.style.cursor = "pointer";
  lg.addEventListener("click", function (e) {
    let chip = e.target;
    while (chip && chip !== lg && !(chip.classList && chip.classList.contains("chip"))) chip = chip.parentNode;
    if (!chip || chip === lg) return;
    const name = String(chip.textContent || "").trim().split(/\s+/)[0];
    if (name) showDomain(name);
  });
}

function resize() {
  const c = document.getElementById("plug3d-canvas");
  if (!c || !renderer) return;
  const w = c.clientWidth || 600, h = c.clientHeight || 400;
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
  const t = performance.now() / 1000;
  if (knotTex) { knotTex.offset.x = (t * 0.06) % 1; knotTex.offset.y = (t * 0.02) % 1; }
  tips.forEach(function (o) {
    const k = 0.72 + 0.26 * (0.5 + 0.5 * Math.sin(t * 1.6 + o.phase));
    o.tip.position.copy(o.path.getPointAt(Math.min(0.999, k)));
    o.tip.material.emissiveIntensity = 0.9 + 0.7 * (0.5 + 0.5 * Math.sin(t * 3 + o.phase));
  });
  controls.update();
  draw();
}

export function start() {
  const go = initing || (initing = loadData().then(function () { return build(); })
    .catch(function (e) {
      document.documentElement.dataset.plug3d = "error:" + String((e && e.message) || e).slice(0, 120);
      return false;
    }));
  go.then(function (ok) {
    if (!ok) return;
    if (running) return;
    running = true;
    loop();
  });
  setTimeout(function () {  // 看门狗：2.5s 还没到位就别让默认首页一片白
    if (!inited) fail("万能插 3D 未就绪（8s 未完成）。原因：" +
      (document.documentElement.dataset.plug3d || "未知") +
      "\n插口数据仍可用；可先看「多域监控」或左侧能力面。");
  }, 8000);
}

export function stop() { running = false; if (raf) { cancelAnimationFrame(raf); raf = 0; } }

export function refresh() {
  return loadData().then(function () { return DATA; });
}

window.__plug3d = { start, stop, refresh, get ok() { return inited; },
  get domains() { return socketList(); } };
window.addEventListener("gbt:view", function (e) { if (e.detail === "plug") start(); else stop(); });
window.addEventListener("resize", function () { resize(); if (!running && renderer) draw(); });
if ((location.hash || "").replace("#", "") === "plug") setTimeout(start, 60);
