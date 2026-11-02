/* GBT小土豆V8 · 触手协作可视化（Three.js）
 *
 * 2026-11-02 重做：照主人给的参考视频（黑底 · 白色发光节点 · 细线网络 · 线会呼吸式淡出再长回来）。
 *
 * 映射（不是装饰）：
 *   · 8 个角色锚点（球面分布）= 8 个协作角色（感知/规划/执行/验证/审计/固化/报告/协同）；
 *   · 每角色 11 颗卫星节点 = 该角色手里的能力位（共 96 点）；
 *   · 细线 = 协作链：
 *       - 卫星→锚点 = 触手纤维（88 条）
 *       - 锚点→锚点 = 协作链（16 条，相邻 2 环 + 对角 1 环）
 *       - 跨角色长弦 = 临时协同（24 条）
 *   · 呼吸 = 每条线有自己的相位 + 全局呼吸 ⇒ 整片网络会"散开/收拢"（参考视频同款）；
 *   · 金色脉冲 = 真实事件（/api/events）点亮角色 + 沿协作链飞一颗光点 + 冲击波环。
 * 交互：拖动旋转 / 滚轮缩放；标记 data-team3d / team3dPulses / team3dLive。
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

document.documentElement.dataset.team3d = "imported";

var ROLES = [
  { name: "感知", desc: "读架构/契约" },
  { name: "规划", desc: "七步拆解" },
  { name: "执行", desc: "run_task 派单" },
  { name: "验证", desc: "真跑读数字" },
  { name: "审计", desc: "留痕对账" },
  { name: "固化", desc: "五处落位" },
  { name: "报告", desc: "给数字" },
  { name: "协同", desc: "交接回喂" }
];

var SATS_PER_ROLE = 11;          // 每角色卫星数
var CHORD_COUNT = 24;            // 跨角色长弦
var renderer, scene, camera, controls, composer, bloom;
var inited = false, running = false, raf = 0;
var pointsCrisp = null, pointsHalo = null, anchorPoints = null, lineSegs = null;
var nodes = [];                  // {role, base, pos, orbit, sat, phase}
var anchors = [];                // 角色锚点（nodes 的下标）
var edges = [];                  // {a, b, phase, speed, fiber}
var edgePos = null, edgeCol = null;
var linkCurves = [];             // 16 条协作链曲线（脉冲沿它走）
var linkByAnchor = {};           // anchorIndex -> [linkIndex...]
var pulses = [];                 // 环境光点 {dot, curve, t, speed}
var liveMsgs = [];               // 事件光点 {dot, trail, curve, t, speed, role}
var waves = [];                  // 冲击波环 {sprite, t, speed, maxScale}
var coreMesh = null, coreFlash = 0;
var litUntil = [];               // 每角色点亮截止时间
var es = null;

function dotTexture(size, blur) {
  var c = document.createElement("canvas");
  c.width = size; c.height = size;
  var ctx = c.getContext("2d");
  var g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(blur || 0.35, "rgba(255,255,255,.55)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(c);
}

function ringSprite(color, size, opacity) {
  var c = document.createElement("canvas");
  c.width = 256; c.height = 256;
  var ctx = c.getContext("2d");
  var g = ctx.createRadialGradient(128, 128, 40, 128, 128, 126);
  g.addColorStop(0.0, "rgba(255,255,255,0)");
  g.addColorStop(0.55, "rgba(255,255,255,0)");
  g.addColorStop(0.78, "rgba(255,255,255,.85)");
  g.addColorStop(0.9, "rgba(255,255,255,.25)");
  g.addColorStop(1.0, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(128, 128, 126, 0, Math.PI * 2); ctx.fill();
  var tex = new THREE.CanvasTexture(c);
  var m = new THREE.SpriteMaterial({ map: tex, color: color, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false, opacity: opacity || 0.9 });
  var sp = new THREE.Sprite(m);
  sp.scale.set(size, size, 1);
  return sp;
}

function glowSprite(color, size, opacity) {
  var c = document.createElement("canvas");
  c.width = 128; c.height = 128;
  var ctx = c.getContext("2d");
  var g = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
  g.addColorStop(0, "rgba(255,255,255,.92)");
  g.addColorStop(0.32, "rgba(255,255,255,.24)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
  var tex = new THREE.CanvasTexture(c);
  var m = new THREE.SpriteMaterial({ map: tex, color: color, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false, opacity: opacity || 0.85 });
  var sp = new THREE.Sprite(m);
  sp.scale.set(size, size, 1);
  return sp;
}

function buildNodes() {
  var N = ROLES.length;
  var golden = Math.PI * (3 - Math.sqrt(5));
  for (var i = 0; i < N; i++) {
    var y = 1 - (i / (N - 1)) * 2;
    var r = Math.sqrt(Math.max(0, 1 - y * y));
    var th = golden * i;
    var R = 5.6;
    var base = new THREE.Vector3(Math.cos(th) * r * R, y * R * 0.72, Math.sin(th) * r * R);
    anchors.push(nodes.length);
    nodes.push({ role: i, base: base.clone(), pos: base.clone(), sat: false,
      orbit: 0, phase: Math.random() * Math.PI * 2, size: 1.0 });
    for (var s = 0; s < SATS_PER_ROLE; s++) {
      var dir = new THREE.Vector3(Math.random() * 2 - 1, Math.random() * 2 - 1, Math.random() * 2 - 1);
      if (dir.lengthSq() < 1e-4) dir.set(1, 0, 0);
      dir.normalize().multiplyScalar(1.1 + Math.random() * 2.2);
      nodes.push({ role: i, base: base.clone().add(dir), pos: null, sat: true,
        orbit: 0, phase: Math.random() * Math.PI * 2, size: 0.55 + Math.random() * 0.7 });
    }
    litUntil.push(0);
  }
}

function buildEdges() {
  var byRole = {};
  nodes.forEach(function (n, idx) {
    if (!byRole[n.role]) byRole[n.role] = [];
    byRole[n.role].push(idx);
  });
  // 触手纤维：卫星 → 自己的锚点
  anchors.forEach(function (ai) {
    var role = nodes[ai].role;
    byRole[role].forEach(function (idx) {
      if (idx !== ai) edges.push({ a: idx, b: ai, fiber: true,
        phase: Math.random() * Math.PI * 2, speed: 0.5 + Math.random() * 0.7 });
    });
  });
  // 协作链：锚点之间（相邻 2 环 + 对角 1 环）—— 与旧版口径一致：16 条
  var N = anchors.length;
  var pairSeen = {};
  for (var i = 0; i < N; i++) {
    for (var j = i + 1; j < N; j++) {
      var d = Math.min(Math.abs(i - j), N - Math.abs(i - j));
      if (d !== 1 && d !== 2) continue;
      if (pairSeen[i + "-" + j]) continue;
      pairSeen[i + "-" + j] = 1;
      edges.push({ a: anchors[i], b: anchors[j], fiber: false,
        phase: Math.random() * Math.PI * 2, speed: 0.28 + Math.random() * 0.4 });
    }
  }
  // 跨角色长弦：卫星 ↔ 卫星
  var guard = 0;
  while (CHORD_COUNT > 0 && guard < 400 && edges.length < 200) {
    guard++;
    var x = nodes[1 + Math.floor(Math.random() * (nodes.length - 1))];
    var yi = 1 + Math.floor(Math.random() * (nodes.length - 1));
    var y = nodes[yi];
    if (!x || !y || x.role === y.role || !x.sat || !y.sat) continue;
    edges.push({ a: nodes.indexOf(x), b: yi, fiber: false,
      phase: Math.random() * Math.PI * 2, speed: 0.2 + Math.random() * 0.5 });
    CHORD_COUNT--;
  }
}

function buildLinkCurves() {
  var N = anchors.length;
  for (var i = 0; i < N; i++) {
    for (var j = i + 1; j < N; j++) {
      var d = Math.min(Math.abs(i - j), N - Math.abs(i - j));
      if (d !== 1 && d !== 2) continue;
      var a = nodes[anchors[i]].base;
      var b = nodes[anchors[j]].base;
      var mid = a.clone().add(b).multiplyScalar(0.5);
      mid.multiplyScalar(1.06);
      var c = new THREE.CatmullRomCurve3([a, mid, b], false, "catmullrom", 0.3);
      var li = linkCurves.length;
      linkCurves.push(c);
      (linkByAnchor[i] = linkByAnchor[i] || []).push(li);
      (linkByAnchor[j] = linkByAnchor[j] || []).push(li);
    }
  }
}

function init() {
  if (inited) return true;
  var canvas = document.getElementById("team3d-canvas");
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true,
      preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x02040a, 0.012);
    camera = new THREE.PerspectiveCamera(44, 1, 0.1, 200);
    camera.position.set(0, 2.6, 15.2);

    buildNodes();
    buildEdges();
    buildLinkCurves();

    // 共享任务核：中心一颗更亮的白点（转起来像参考视频里最亮的中心节点）
    // 中心核只做"一颗稍亮的节点"（不做太阳）：参考视频里没有中心亮斑
    coreMesh = new THREE.Mesh(new THREE.SphereGeometry(0.1, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0xfff6e0 }));
    scene.add(coreMesh);
    // 中心不放大光斑（参考视频是纯网络；核心只做"更亮的一颗白点"）

    // 节点：两层点云（清晰核心 + 大光晕）——参考视频里的"发光小圆点 + 景深散景"
    var pos = new Float32Array(nodes.length * 3);
    var sizes = new Float32Array(nodes.length);
    nodes.forEach(function (n, i) {
      pos[i * 3] = n.base.x; pos[i * 3 + 1] = n.base.y; pos[i * 3 + 2] = n.base.z;
      sizes[i] = n.size;
    });
    var geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    var texDot = dotTexture(64, 0.4);
    pointsCrisp = new THREE.Points(geo, new THREE.PointsMaterial({
      size: 0.15, map: texDot, transparent: true, opacity: 0.95,
      depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true }));
    scene.add(pointsCrisp);
    var geoHalo = new THREE.BufferGeometry();
    geoHalo.setAttribute("position", new THREE.BufferAttribute(pos.slice(0), 3));
    pointsHalo = new THREE.Points(geoHalo, new THREE.PointsMaterial({
      size: 0.5, map: dotTexture(128, 0.5), transparent: true, opacity: 0.16,
      depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true,
      color: 0xdfe9ff }));
    scene.add(pointsHalo);

    // 角色锚点：单独一层（更大、可点金）——参考视频里"少数亮点比周围更亮"
    var aPos = new Float32Array(anchors.length * 3);
    var aCol = new Float32Array(anchors.length * 3);
    anchors.forEach(function (ai, k) {
      var b = nodes[ai].base;
      aPos[k * 3] = b.x; aPos[k * 3 + 1] = b.y; aPos[k * 3 + 2] = b.z;
      aCol[k * 3] = 1; aCol[k * 3 + 1] = 1; aCol[k * 3 + 2] = 1;
    });
    var ag = new THREE.BufferGeometry();
    ag.setAttribute("position", new THREE.BufferAttribute(aPos, 3));
    ag.setAttribute("color", new THREE.BufferAttribute(aCol, 3));
    anchorPoints = new THREE.Points(ag, new THREE.PointsMaterial({
      size: 0.3, map: texDot, transparent: true, opacity: 1,
      depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true,
      vertexColors: true }));
    scene.add(anchorPoints);

    // 星尘（远景景深）
    var DUST = 900;
    var arr = new Float32Array(DUST * 3);
    for (var i = 0; i < DUST; i++) {
      var r = 16 + Math.random() * 30;
      var th = Math.random() * Math.PI * 2;
      var ph = Math.acos(2 * Math.random() - 1);
      arr[i * 3] = r * Math.sin(ph) * Math.cos(th);
      arr[i * 3 + 1] = r * Math.cos(ph) * 0.72;
      arr[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    }
    var dg = new THREE.BufferGeometry();
    dg.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    scene.add(new THREE.Points(dg, new THREE.PointsMaterial({
      color: 0x9fb4d6, size: 0.1, transparent: true, opacity: 0.28,
      depthWrite: false, blending: THREE.AdditiveBlending })));

    // 线：一次建满，逐帧改颜色做"呼吸"
    edgePos = new Float32Array(edges.length * 6);
    edgeCol = new Float32Array(edges.length * 6);
    var lg = new THREE.BufferGeometry();
    lg.setAttribute("position", new THREE.BufferAttribute(edgePos, 3));
    lg.setAttribute("color", new THREE.BufferAttribute(edgeCol, 3));
    var lineMat = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true,
      opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false });
    lineSegs = new THREE.LineSegments(lg, lineMat);
    scene.add(lineSegs);

    // 环境光点：沿协作链慢慢走（参考视频里"偶尔一颗亮点划过"）
    var pulseGeo = new THREE.SphereGeometry(0.05, 8, 8);
    var pulseMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    linkCurves.forEach(function (c) {
      for (var k = 0; k < 2; k++) {
        var dot = new THREE.Mesh(pulseGeo, pulseMat);
        scene.add(dot);
        pulses.push({ dot: dot, curve: c, t: Math.random(), speed: 0.05 + Math.random() * 0.08 });
      }
    });

    var wrap = document.querySelector(".view-team") || canvas;
    controls = new OrbitControls(camera, wrap);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.5;
    controls.enablePan = false;
    controls.minDistance = 7;
    controls.maxDistance = 42;
    controls.rotateSpeed = 0.7;

    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    // 参数口径（2026-11-02 试出来的）：radius 必须 0，否则宽 mip 会把中心亮像素糊成一大片灰盘；
    // threshold 抬高只让最亮的节点出辉光，细线保持锐利 —— 参考视频就是"点发光、线清晰"。
    bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.5, 0.0, 0.85);
    composer.addPass(bloom);

    resize();
    inited = true;
    document.documentElement.dataset.team3d = "ok:" + ROLES.length + "臂+" + (linkCurves.length) + "协作链";
    connectLive();
    if (new URLSearchParams(location.search).get("selftest") === "1") {
      setTimeout(function () { lightRole("inventory"); lightRole("selfscan"); }, 300);
    }
    if (new URLSearchParams(location.search).get("pulse") === "1") {
      var seq = ["inventory", "selfscan", "signature_guard", "recon", "report"];
      var pi = 0;
      setInterval(function () { lightRole(seq[pi % seq.length]); pi++; }, 900);
    }
    draw();
    return true;
  } catch (e) {
    document.documentElement.dataset.team3d = "error:" + String((e && e.message) || e).slice(0, 120);
    return false;
  }
}

/* 事件名 → 协作角色（真实映射：守卫/账本类落「审计」，执行类落「执行」，报告类落「报告」） */
var EVENT_ROLE = {
  selfscan: "审计", inventory: "审计", signature_guard: "审计", legacy_guard: "审计",
  cap_self: "审计", truth_scan: "审计", inventory_report: "审计",
  auth_denied: "协同", denied: "协同",
  call: "执行", run: "执行", ok: "执行",
  report: "报告", deliver: "报告",
  plan: "规划", kernel: "规划", chain_kernel: "规划",
  verify: "验证", test: "验证",
  docs: "固化", ledger: "固化", orchestration: "固化",
  recon: "感知", scan: "感知"
};

function roleFor(cap) {
  var k = String(cap || "").toLowerCase();
  if (EVENT_ROLE[k]) return EVENT_ROLE[k];
  for (var key in EVENT_ROLE) {
    if (k.indexOf(key) >= 0) return EVENT_ROLE[key];
  }
  var h = 0;
  for (var i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) % 997;
  return ROLES[h % ROLES.length].name;
}

function roleAnchor(name) {
  for (var i = 0; i < ROLES.length; i++) if (ROLES[i].name === name) return i;
  return -1;
}

/* 真实事件：点亮角色（金色）+ 冲击波 + 沿协作链飞一颗金色光点 */
function lightRole(cap) {
  var name = roleFor(cap);
  var ai = roleAnchor(name);
  if (ai < 0 || !inited) return name;
  litUntil[ai] = performance.now() + 6000;
  var base = nodes[anchors[ai]].base;

  var wave = ringSprite(0xffd166, 1.2, 0.95);
  wave.position.copy(base);
  scene.add(wave);
  waves.push({ sprite: wave, t: 0, speed: 1.5, maxScale: 8.5, baseY: base.y });
  if (waves.length > 16) {
    var old = waves.shift();
    scene.remove(old.sprite);
    old.sprite.material.dispose();
  }

  var links = linkByAnchor[ai] || [];
  if (links.length) {
    var c = linkCurves[links[Math.floor(Math.random() * links.length)]];
    var dot = new THREE.Mesh(new THREE.SphereGeometry(0.09, 10, 10),
      new THREE.MeshBasicMaterial({ color: 0xffd166 }));
    scene.add(dot);
    var trail = glowSprite(0xffd166, 0.9, 0.85);
    scene.add(trail);
    var fromTip = Math.random() < 0.5;
    liveMsgs.push({ dot: dot, trail: trail, curve: c, t: 0, speed: 1.1, role: name, reverse: fromTip });
  }
  coreFlash = 1.0;
  updateLiveMarker();
  return name;
}

function updateLiveMarker() {
  var d = document.documentElement.dataset;
  if (!d.team3d || d.team3d.indexOf("ok:") !== 0) return;
  var parts = d.team3d.split("+");
  while (parts.length > 3) parts.pop();
  parts[2] = "脉冲" + waves.length;
  d.team3d = parts.join("+");
  d.team3dPulses = String(waves.length);
}

function connectLive() {
  if (es || typeof EventSource === "undefined") return;
  if (new URLSearchParams(location.search).get("nosse") === "1") {
    document.documentElement.dataset.team3dLive = "off-for-test";
    return;
  }
  if (!/^https?:/.test(location.protocol)) {
    document.documentElement.dataset.team3dLive = "unsupported";
    return;
  }
  try {
    es = new EventSource("/api/events");
    es.onmessage = function (e) {
      try {
        var d = JSON.parse(e.data);
        if (d && d.cap) {
          var role = lightRole(d.cap);
          document.documentElement.dataset.team3dLast = d.cap + "→" + role;
          document.documentElement.dataset.team3dLive = "on";
        }
      } catch (err) { /* ignore */ }
    };
    es.onerror = function () { document.documentElement.dataset.team3dLive = "reconnecting"; };
  } catch (e) {
    document.documentElement.dataset.team3dLive = "unsupported";
  }
}

function resize() {
  var c = document.getElementById("team3d-canvas");
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
  var nowMs = performance.now();

  // ① 节点漂移：锚点绕中心慢转 + 卫星绕角色锚点微轨
  var NodeC = new THREE.Vector3();
  nodes.forEach(function (n, i) {
    var b = n.base;
    if (!n.sat) {
      var a = t * 0.06 + n.phase;
      var ox = Math.cos(a) * 0.35, oz = Math.sin(a * 0.9) * 0.35;
      var oy = Math.sin(t * 0.5 + n.phase) * 0.22;
      NodeC.set(b.x + ox, b.y + oy, b.z + oz);
    } else {
      var ai = anchors[n.role];
      var ab = nodes[ai].pos || nodes[ai].base;
      var a2 = t * (0.12 + (i % 5) * 0.02) + n.phase;
      var rr = 0.22;
      NodeC.set(ab.x + (b.x - nodes[ai].base.x) + Math.cos(a2) * rr,
        ab.y + (b.y - nodes[ai].base.y) + Math.sin(t * 0.7 + n.phase) * rr,
        ab.z + (b.z - nodes[ai].base.z) + Math.sin(a2) * rr);
    }
    n.pos = NodeC.clone();
    var pa = pointsCrisp.geometry.attributes.position.array;
    var ha = pointsHalo.geometry.attributes.position.array;
    pa[i * 3] = ha[i * 3] = n.pos.x;
    pa[i * 3 + 1] = ha[i * 3 + 1] = n.pos.y;
    pa[i * 3 + 2] = ha[i * 3 + 2] = n.pos.z;
  });
  pointsCrisp.geometry.attributes.position.needsUpdate = true;
  pointsHalo.geometry.attributes.position.needsUpdate = true;

  // ② 线的位置 + 呼吸亮度（全局呼吸 + 每线相位）——参考视频里线会整片淡出再长回来
  var gb = 0.08 + 0.92 * Math.pow(0.5 + 0.5 * Math.sin(t * 0.55 + 1.2), 2.2);
  for (var ei = 0; ei < edges.length; ei++) {
    var e = edges[ei];
    var A = nodes[e.a].pos, B = nodes[e.b].pos;
    var o = ei * 6;
    edgePos[o] = A.x; edgePos[o + 1] = A.y; edgePos[o + 2] = A.z;
    edgePos[o + 3] = B.x; edgePos[o + 4] = B.y; edgePos[o + 5] = B.z;
    var e1 = 0.28 + 0.72 * Math.pow(0.5 + 0.5 * Math.sin(t * e.speed + e.phase), 2);
    var br = (e.fiber ? 0.62 : 1.0) * e1 * gb;
    var warm = 0;
    for (var k = 0; k < 2; k++) {
      edgeCol[o + k * 3] = br * (1.0 + warm);
      edgeCol[o + k * 3 + 1] = br * (0.96 + warm * 0.85);
      edgeCol[o + k * 3 + 2] = br * (0.92 + warm * 0.5);
    }
  }
  if (lineSegs) {
    lineSegs.geometry.attributes.position.needsUpdate = true;
    lineSegs.geometry.attributes.color.needsUpdate = true;
  }

  // ③ 环境光点（沿协作链）
  pulses.forEach(function (p) {
    p.t += p.speed * 0.016;
    if (p.t > 1) p.t -= 1;
    p.dot.position.copy(p.curve.getPointAt(Math.min(0.999, p.t)));
  });

  // ④ 事件光点：沿协作链飞
  for (var i = liveMsgs.length - 1; i >= 0; i--) {
    var m = liveMsgs[i];
    m.t += m.speed * 0.016;
    if (m.t >= 1) {
      scene.remove(m.dot); m.dot.geometry.dispose(); m.dot.material.dispose();
      if (m.trail) { scene.remove(m.trail); m.trail.material.dispose(); }
      liveMsgs.splice(i, 1);
      updateLiveMarker();
      continue;
    }
    m.dot.position.copy(m.curve.getPointAt(Math.min(0.999, m.reverse ? 1 - m.t : m.t)));
  }
  liveMsgs.forEach(function (m) { if (m.trail) m.trail.position.copy(m.dot.position); });

  // ⑤ 冲击波
  for (var wi = waves.length - 1; wi >= 0; wi--) {
    var w = waves[wi];
    w.t += w.speed * 0.016;
    if (w.t >= 1) {
      scene.remove(w.sprite); w.sprite.material.dispose(); waves.splice(wi, 1);
      updateLiveMarker();
      continue;
    }
    var sc = 1.1 + w.t * w.maxScale;
    w.sprite.scale.set(sc, sc, 1);
    w.sprite.material.opacity = Math.max(0, (1 - w.t) * 0.95);
  }

  // ⑥ 核心：被事件点亮时闪一下
  if (coreMesh) {
    coreFlash = Math.max(0, coreFlash - 0.02);
    var kk = 1 + coreFlash * 0.7;
    coreMesh.scale.set(kk, kk, kk);
    coreMesh.material.color.setHex(coreFlash > 0.1 ? 0xffd166 : 0xffffff);
  }

  // ⑦ 角色锚点：位置跟漂移 + 点亮变金
  if (anchorPoints) {
    var ap = anchorPoints.geometry.attributes.position.array;
    var ac = anchorPoints.geometry.attributes.color.array;
    anchors.forEach(function (ai, k) {
      var p = nodes[ai].pos;
      ap[k * 3] = p.x; ap[k * 3 + 1] = p.y; ap[k * 3 + 2] = p.z;
      var lit = nowMs < litUntil[nodes[ai].role];
      ac[k * 3] = 1;
      ac[k * 3 + 1] = lit ? 0.8 : 1;
      ac[k * 3 + 2] = lit ? 0.42 : 1;
    });
    anchorPoints.geometry.attributes.position.needsUpdate = true;
    anchorPoints.geometry.attributes.color.needsUpdate = true;
  }

  controls.update();
  draw();
}

export function start() { if (!init()) return; if (running) return; running = true; loop(); }
export function stop() { running = false; if (raf) { cancelAnimationFrame(raf); raf = 0; } }

window.__team3d = { start: start, stop: stop, lightRole: function (cap) { return lightRole(cap); },
  // 只读调试口（排障用；页面逻辑不依赖它）
  get debug() { return { scene: scene, camera: camera, bloom: bloom }; },
  get ok() { return inited; }, get live() { return liveMsgs.length; },
  get pulses() { return waves.length; },
  roleFor: roleFor };
window.addEventListener("gbt:view", function (e) { if (e.detail === "team") start(); else stop(); });
window.addEventListener("resize", function () { resize(); if (!running && renderer) draw(); });
if ((location.hash || "").replace("#", "") === "team") setTimeout(start, 60);
