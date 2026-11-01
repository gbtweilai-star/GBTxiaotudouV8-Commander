/* GBT小土豆V8 · 3D 触手星图（Three.js）
 * 主人口径：**"我们的触手是亿万根啊"** —— 参考图那种密集网络。
 *   骨架：385 个能力位分 30 域聚簇（簇核黄色发光，簇内放射线）；
 *   触手：每个能力位向外展开 40 根视觉触手（细线+端点），合计 15,400 根；
 *   外圈：2,000 点球壳 + 3,000 深层星尘；域间弦线成网。
 *   **口径诚实**：视觉触手是"展开示意"，真实触手由 run_task 调用时按需展开、审计留痕。
 * 交互：OrbitControls 拖拽/滚轮，慢速自转；标签只标域核心。
 * 标记：data-space3d = "ok:<能力位>+<域>+<触手>" / "no-webgl" / "error"。
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

document.documentElement.dataset.space3d = "imported";
window.__space3dModule = "imported";

const HOST_ID = "space3d-canvas";
const TENTACLES_PER_CAP = 40;

let inited = false, running = false, raf = 0;
let renderer, scene, camera, controls, composer, bloomPass;
let hubs = [], caps = 0, tentacleCount = 0;
let capRanges = {};        // cap 名 → [startVert, endVert)
let activeCaps = [];       // 最近真实调用过的能力位（来自 audit pulse）
let pulseOverlay = null;
let liveLayer = new Map();     // cap → {obj, until}
let liveCount = 0;
let es = null;

function has3d() {
  const host = document.getElementById(HOST_ID);
  if (!host) return null;
  try { return host.getContext("webgl2") || host.getContext("webgl"); } catch (e) { return null; }
}

function glowSprite(color, size, opacity) {
  const c = document.createElement("canvas");
  c.width = 128; c.height = 128;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
  g.addColorStop(0, "rgba(255,255,255,.95)");
  g.addColorStop(0.3, "rgba(255,255,255,.28)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  const mat = new THREE.SpriteMaterial({ map: tex, color: color, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false, opacity: opacity || 0.9 });
  const s = new THREE.Sprite(mat);
  s.scale.set(size, size, 1);
  return s;
}

function labelSprite(text, color) {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 96;
  const ctx = c.getContext("2d");
  ctx.font = "600 42px 'JetBrains Mono', monospace";
  ctx.fillStyle = color; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, 256, 48);
  const tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  const m = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
  const sp = new THREE.Sprite(m);
  sp.scale.set(3.2, 0.6, 1);
  return sp;
}

function data() {
  const d = window.GBT_CONSOLE || {};
  return { caps: (d.caps && d.caps.items) || [], doms: d.domains || [] };
}

function fibSphere(i, n, radius, squashY) {
  const y = 1 - (i / Math.max(1, n - 1)) * 2;
  const rad = Math.sqrt(Math.max(0, 1 - y * y));
  const th = i * Math.PI * (3 - Math.sqrt(5));
  return new THREE.Vector3(Math.cos(th) * rad, y * (squashY || 1), Math.sin(th) * rad).multiplyScalar(radius);
}

function init() {
  if (inited) return true;
  const host = document.getElementById(HOST_ID);
  if (!has3d()) { document.documentElement.dataset.space3d = "no-webgl"; return false; }
  try {
    renderer = new THREE.WebGLRenderer({ canvas: host, antialias: true, alpha: true,
      preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x04070d, 0.008);
    camera = new THREE.PerspectiveCamera(48, 1, 0.1, 600);
    camera.position.set(2, 9, 48);

    const { caps: capList, doms } = data();
    caps = capList.length;
    const byDom = {};
    capList.forEach(function (c) { (byDom[c.domain] = byDom[c.domain] || []).push(c); });

    const list = doms.length ? doms : Object.keys(byDom).map(function (k) {
      return { domain: k, count: byDom[k].length };
    });
    const N = Math.max(1, list.length);
    const R_HUB = 6.6;
    const maxCount = Math.max(1, ...list.map(function (x) { return x.count || 1; }));

    // ── 触手：全部线段 + 端点的合并 geometry（性能友好） ──
    const tentVerts = [];
    const tentColors = [];
    const tipPos = [];
    const tipColors = [];
    const hubGeo = new THREE.SphereGeometry(1, 20, 20);

    list.forEach(function (d, i) {
      const pos = fibSphere(i, N, R_HUB, 0.88);
      const hue = (0.06 + (d.count || 1) / maxCount * 0.62) % 1;
      const coreCol = new THREE.Color().setHSL(hue, 0.9, 0.6);

      // 簇核
      const core = new THREE.Mesh(hubGeo, new THREE.MeshBasicMaterial({ color: 0xffd166 }));
      core.scale.setScalar(0.22 + (d.count || 1) / maxCount * 0.38);
      core.position.copy(pos);
      scene.add(core);
      const gl = glowSprite(0xffd166, 1.2 + (d.count || 1) / maxCount * 0.9, 0.38);
      gl.position.copy(pos); scene.add(gl);
      const lb = labelSprite(d.domain + " " + (d.count || 0), "#ffe6a3");
      lb.position.copy(pos).add(new THREE.Vector3(0, 0.8, 0)); scene.add(lb);
      hubs.push({ pos: pos, domain: d.domain, count: d.count || 0 });

      const members = byDom[d.domain] || [];
      members.forEach(function (c, k) {
        const a1 = k * 2.399963, a2 = k * 1.618;
        const rr = 0.9 + (k / Math.max(1, members.length - 1)) * 2.0;
        const off = new THREE.Vector3(
          Math.cos(a1) * Math.sin(a2), Math.cos(a2) * 0.8, Math.sin(a1) * Math.sin(a2)
        ).multiplyScalar(rr);
        const mp = pos.clone().add(off);
        const mc = new THREE.Color().setHSL(hue, 0.55, 0.62);

        // 簇核→能力位
        tentVerts.push(pos.x, pos.y, pos.z, mp.x, mp.y, mp.z);
        tentColors.push(coreCol.r, coreCol.g, coreCol.b, mc.r, mc.g, mc.b);

        // 能力位→外圈：40 根"触手"（弯曲细线，端点小点）
        const rangeStart = tentVerts.length;
        for (let t = 0; t < TENTACLES_PER_CAP; t++) {
          const dir = new THREE.Vector3(
            Math.sin(t * 1.7 + k), Math.cos(t * 2.3 + k * 0.7), Math.sin(t * 0.9 + k * 1.3)
          ).normalize();
          const len = 2.2 + ((t * 37 + k * 11) % 100) / 100 * 5.5;
          const mid = mp.clone().add(dir.clone().multiplyScalar(len * 0.5))
            .add(new THREE.Vector3((t % 5 - 2) * 0.12, (t % 3 - 1) * 0.12, 0));
          const end = mp.clone().add(dir.clone().multiplyScalar(len));
          // 两点折线近似曲线
          tentVerts.push(mp.x, mp.y, mp.z, mid.x, mid.y, mid.z);
          tentVerts.push(mid.x, mid.y, mid.z, end.x, end.y, end.z);
          const fade = 0.45;
          tentColors.push(mc.r * 0.55, mc.g * 0.55, mc.b * 0.55, mc.r * fade * 0.55, mc.g * fade * 0.55, mc.b * fade * 0.55);
          tentColors.push(mc.r * fade * 0.55, mc.g * fade * 0.55, mc.b * fade * 0.55, mc.r * 0.15, mc.g * 0.15, mc.b * 0.15);
          tipPos.push(end.x, end.y, end.z);
          tipColors.push(mc.r, mc.g, mc.b);
          tentacleCount++;
        }
        capRanges[c.name] = [rangeStart, tentVerts.length];
      });
    });

    const tg = new THREE.BufferGeometry();
    tg.setAttribute("position", new THREE.Float32BufferAttribute(tentVerts, 3));
    tg.setAttribute("color", new THREE.Float32BufferAttribute(tentColors, 3));
    scene.add(new THREE.LineSegments(tg, new THREE.LineBasicMaterial({
      vertexColors: true, transparent: true, opacity: 0.16,
      blending: THREE.NormalBlending, depthWrite: false })));

    const tipG = new THREE.BufferGeometry();
    tipG.setAttribute("position", new THREE.Float32BufferAttribute(tipPos, 3));
    tipG.setAttribute("color", new THREE.Float32BufferAttribute(tipColors, 3));
    scene.add(new THREE.Points(tipG, new THREE.PointsMaterial({
      size: 0.085, vertexColors: true, transparent: true, opacity: 0.55,
      blending: THREE.NormalBlending, depthWrite: false })));

    // ── 最近真实调用过的能力位：触手点亮（数据来自 audit.jsonl 的 pulse） ──
    const pulse = ((window.GBT_CONSOLE || {}).pulse) || [];
    const capNames = new Set(Object.keys(capRanges));
    activeCaps = pulse.filter(function (x) { return capNames.has(x.cap); })
      .slice(0, 12).map(function (x) { return x.cap; });
    if (activeCaps.length) {
      const pv = [];
      const pc = [];
      activeCaps.forEach(function (nm) {
        const rg = capRanges[nm];
        if (!rg) return;
        for (let i = rg[0]; i < rg[1]; i += 3) {
          pv.push(tentVerts[i], tentVerts[i + 1], tentVerts[i + 2]);
          pc.push(1.0, 0.72, 0.25);       // 暖金
        }
      });
      if (pv.length) {
        const pg = new THREE.BufferGeometry();
        pg.setAttribute("position", new THREE.Float32BufferAttribute(pv, 3));
        pg.setAttribute("color", new THREE.Float32BufferAttribute(pc, 3));
        pulseOverlay = new THREE.LineSegments(pg, new THREE.LineBasicMaterial({
          vertexColors: true, transparent: true, opacity: 0.6,
          blending: THREE.AdditiveBlending, depthWrite: false }));
        scene.add(pulseOverlay);
      }
    }

    // ── 域间弦线 ──
    const chord = new THREE.LineBasicMaterial({ color: 0x4f8cff, transparent: true,
      opacity: 0.07, blending: THREE.AdditiveBlending, depthWrite: false });
    for (let i = 0; i < hubs.length; i++) {
      for (let j = i + 1; j < hubs.length; j++) {
        if ((i * 7 + j * 3) % 3 !== 0) continue;
        scene.add(new THREE.Line(
          new THREE.BufferGeometry().setFromPoints([hubs[i].pos, hubs[j].pos]), chord));
      }
    }

    // ── 外圈球壳（冷蓝/暖黄交替，2000 点） ──
    const SHELL_N = 2000, R_SHELL = 14.2;
    const sp2 = new Float32Array(SHELL_N * 3), sc2 = new Float32Array(SHELL_N * 3);
    for (let i = 0; i < SHELL_N; i++) {
      const v = fibSphere(i, SHELL_N, R_SHELL, 0.95);
      sp2[i * 3] = v.x; sp2[i * 3 + 1] = v.y; sp2[i * 3 + 2] = v.z;
      const col = new THREE.Color(i % 3 === 0 ? 0xffd166 : 0x6fa8ff);
      sc2[i * 3] = col.r; sc2[i * 3 + 1] = col.g; sc2[i * 3 + 2] = col.b;
    }
    const shellG = new THREE.BufferGeometry();
    shellG.setAttribute("position", new THREE.BufferAttribute(sp2, 3));
    shellG.setAttribute("color", new THREE.BufferAttribute(sc2, 3));
    scene.add(new THREE.Points(shellG, new THREE.PointsMaterial({
      size: 0.15, vertexColors: true, transparent: true, opacity: 0.8, depthWrite: false })));

    // ── 深层星尘 ──
    const DUST = 3000;
    const dp = new Float32Array(DUST * 3);
    for (let i = 0; i < DUST; i++) {
      const r = 18 + Math.random() * 40;
      const v = fibSphere(i, DUST, r, 1);
      dp[i * 3] = v.x; dp[i * 3 + 1] = v.y; dp[i * 3 + 2] = v.z;
    }
    const dustG = new THREE.BufferGeometry();
    dustG.setAttribute("position", new THREE.BufferAttribute(dp, 3));
    scene.add(new THREE.Points(dustG, new THREE.PointsMaterial({
      color: 0x8fa6c4, size: 0.1, transparent: true, opacity: 0.4, depthWrite: false })));

    // 中心：她的头像（画到深底圆盘上，避免白底被 Bloom 炸成白团）
    const avatarBall = new THREE.Mesh(
      new THREE.SphereGeometry(1.7, 48, 48),
      new THREE.MeshBasicMaterial({ color: 0x1b2230, toneMapped: false }));
    avatarBall.position.set(0, 0.2, 0.6);
    avatarBall.renderOrder = 999;
    scene.add(avatarBall);
    (function makeAvatarTexture() {
      const img = new Image();
      img.onload = function () {
        const c = document.createElement("canvas");
        c.width = 512; c.height = 512;
        const ctx = c.getContext("2d");
        ctx.fillStyle = "#0b1120"; ctx.fillRect(0, 0, 512, 512);
        const s = Math.min(img.width, img.height);
        const sx = (img.width - s) / 2, sy = (img.height - s) / 2;
        ctx.save();
        ctx.beginPath();
        ctx.arc(256, 256, 232, 0, Math.PI * 2);
        ctx.clip();
        ctx.globalCompositeOperation = "multiply";
        ctx.drawImage(img, sx, sy, s, s, 26, 26, 460, 460);
        ctx.globalCompositeOperation = "source-over";
        ctx.restore();
        ctx.strokeStyle = "rgba(255,207,107,.45)";
        ctx.lineWidth = 6;
        ctx.beginPath(); ctx.arc(256, 256, 232, 0, Math.PI * 2); ctx.stroke();
        const tex = new THREE.CanvasTexture(c);
        tex.colorSpace = THREE.SRGBColorSpace;
        avatarBall.material.map = tex;
        avatarBall.material.color = new THREE.Color(0xffffff);
        avatarBall.material.needsUpdate = true;
        document.documentElement.dataset.space3dAvatar = "ok";
      };
      img.onerror = function () {
        document.documentElement.dataset.space3dAvatar = "load-failed";
      };
      img.src = "../../icons/avatar.png";
    })();
    const avGlow = glowSprite(0xffcf6b, 7.2, 0.30);
    avGlow.renderOrder = 997;
    scene.add(avGlow);
    scene.userData.avatarBall = avatarBall;

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    scene.add(new THREE.PointLight(0xffd166, 2.2, 120));

    // OrbitControls 绑整个 3D 区域（整块都能拖；比只绑 canvas 好抓）
    const wrap = document.querySelector(".space3d-wrap") || host;
    controls = new OrbitControls(camera, wrap);
    controls.rotateSpeed = 0.75;
    controls.zoomSpeed = 0.9;
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.22;
    controls.enablePan = false;
    controls.minDistance = 16;
    controls.maxDistance = 90;

    // 后处理：Bloom 辉光
    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    bloomPass = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.75, 0.65, 0.55);
    composer.addPass(bloomPass);

    resize();
    inited = true;
    document.documentElement.dataset.space3d =
      "ok:" + caps + "+" + hubs.length + "+" + tentacleCount + "+" + activeCaps.length;
    connectLive();
    if (new URLSearchParams(location.search).get("selftest") === "1") {
      setTimeout(selfTestDrag, 400);
    }
    draw();
    try {
      if (new URLSearchParams(location.search).get("snap") === "1") {
        controls.autoRotate = false;
        draw();
        document.title = "SNAP:" + renderer.domElement.toDataURL("image/png");
      }
    } catch (e) { /* ignore */ }
    return true;
  } catch (e) {
    document.documentElement.dataset.space3d = "error:" + String(e && e.message || e).slice(0, 120);
    return false;
  }
}

function liveBurst(cap) {
  if (!capRanges[cap] || !scene) return;
  const [a, b] = capRanges[cap];
  const pos = [];
  // 从已建的触手 geometry 里取该能力位的线段
  const g = scene.children.find(function (o) {
    return o.isLineSegments && o.geometry && o.geometry.attributes.position &&
      o.geometry.attributes.position.count > 10000;
  });
  if (!g) return;
  const arr = g.geometry.attributes.position.array;
  for (let i = a; i < b && i + 2 < arr.length; i += 3) {
    pos.push(arr[i], arr[i + 1], arr[i + 2]);
  }
  if (!pos.length) return;
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  const mat = new THREE.LineBasicMaterial({ color: 0xffcf6b, transparent: true,
    opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false });
  const mesh = new THREE.LineSegments(geo, mat);
  scene.add(mesh);
  const old = liveLayer.get(cap);
  if (old) { scene.remove(old.obj); old.obj.geometry.dispose(); old.obj.material.dispose(); }
  liveLayer.set(cap, { obj: mesh, until: performance.now() + 6000 });
  liveCount = liveLayer.size;
  updateLiveMarker();
}

function updateLiveMarker() {
  if (!document.documentElement.dataset.space3d) return;
  const parts = document.documentElement.dataset.space3d.split(":");
  if (parts[0] !== "ok") return;
  const nums = parts[1].split("+");
  nums[3] = String(liveCount);
  document.documentElement.dataset.space3d = "ok:" + nums.join("+");
}

function connectLive() {
  if (es || typeof EventSource === "undefined") return;
  // 无头巡检/截图时用 ?nosse=1 关掉长连接（否则 dump-dom 会等不到加载完成）
  if (new URLSearchParams(location.search).get("nosse") === "1") {
    document.documentElement.dataset.live = "off-for-test";
    return;
  }
  if (!/^https?:/.test(location.protocol)) return;
  try {
    es = new EventSource("/api/events");
    es.onmessage = function (e) {
      try {
        const d = JSON.parse(e.data);
        if (d && d.cap) liveBurst(d.cap);
      } catch (err) { /* ignore */ }
    };
    es.onerror = function () {
      // 断线由浏览器自动重连；这里只标记，不刷屏
      document.documentElement.dataset.live = "reconnecting";
    };
    document.documentElement.dataset.live = "on";
  } catch (e) {
    document.documentElement.dataset.live = "unsupported";
  }
}

let lastPrune = 0;
function pruneLive(now) {
  if (now - lastPrune < 200) return;
  lastPrune = now;
  let changed = false;
  liveLayer.forEach(function (v, k) {
    if (now > v.until) {
      scene.remove(v.obj);
      v.obj.geometry.dispose();
      v.obj.material.dispose();
      liveLayer.delete(k);
      changed = true;
    } else {
      const left = (v.until - now) / 6000;
      v.obj.material.opacity = Math.max(0.08, Math.min(0.95, left));
    }
  });
  if (changed) { liveCount = liveLayer.size; updateLiveMarker(); }
}

function resize() {
  const host = document.getElementById(HOST_ID);
  if (!host || !renderer) return;
  const w = host.clientWidth || 600, h = host.clientHeight || 400;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  if (composer) composer.setSize(w, h);
  if (bloomPass) bloomPass.resolution.set(w, h);
}

function draw() {
  if (composer) composer.render();
  else renderer.render(scene, camera);
  if (pulseOverlay) {
    const t = (typeof performance !== "undefined" ? performance.now() : Date.now()) / 1000;
    pulseOverlay.material.opacity = 0.35 + 0.45 * (0.5 + 0.5 * Math.sin(t * 2.2));
  }
}

function loop() {
  if (!running) return;
  raf = requestAnimationFrame(loop);
  const ab = scene && scene.userData && scene.userData.avatarBall;
  if (ab) {
    ab.rotation.y += 0.006;
    ab.rotation.x = Math.sin(Date.now() / 4000) * 0.12;
  }
  controls.update();
  draw();
  pruneLive(typeof performance !== "undefined" ? performance.now() : Date.now());
}

/* 程序化拖拽自检：?selftest=1 时验证"鼠标转动"这条链路真的生效 */
function selfTestDrag() {
  const wrap = document.querySelector(".space3d-wrap");
  if (!wrap) { document.documentElement.dataset.space3dDrag = "no-wrap"; return; }
  const before = camera.position.clone();
  const opts = { bubbles: true, cancelable: true, pointerId: 1, pointerType: "mouse",
                 button: 0, buttons: 1, isPrimary: true, clientX: 400, clientY: 400 };
  try {
    wrap.dispatchEvent(new PointerEvent("pointerdown", opts));
    wrap.dispatchEvent(new PointerEvent("pointermove", Object.assign({}, opts, { clientX: 520, clientY: 430 })));
    wrap.dispatchEvent(new PointerEvent("pointerup", Object.assign({}, opts, { buttons: 0 })));
    controls.update();
    const moved = before.distanceTo(camera.position);
    document.documentElement.dataset.space3dDrag = moved > 0.001 ? ("ok:" + moved.toFixed(3)) : "still";
  } catch (e) {
    document.documentElement.dataset.space3dDrag = "error:" + String((e && e.message) || e).slice(0, 60);
  }
}

export function start() { if (!init()) return; if (running) return; running = true; loop(); }
export function stop() { running = false; if (raf) { cancelAnimationFrame(raf); raf = 0; } }

window.__space3d = { start, stop, selfTestDrag,
  get ok() { return inited; },
  get nodes() { return caps; },
  get tentacles() { return tentacleCount; } };
window.addEventListener("gbt:view", function (e) { if (e.detail === "space") start(); else stop(); });
window.addEventListener("resize", function () { resize(); if (!running && renderer) renderer.render(scene, camera); });
if ((location.hash || "").replace("#", "") === "space") setTimeout(start, 60);
