/* GBT小土豆V8 · 思维导图任务指引（Three.js）
 *
 * 主人 2026-11-01：「以及思维导图任务指引」——把"接到任务怎么走"画成可转的思维导图。
 *
 * 内容不是装饰，是这套框架真在用的流程（chain_kernel 七步 + 五处落位 + 留痕要求）：
 *   · 中心「任务指引」  → 6 个分支 → 每支 3 片叶子（共 18 条具体指引）；
 *   · 分支 = 理解需求 / 拆解计划 / 执行落地 / 验证取证 / 留痕固化 / 交付报告；
 *   · 叶子 = 真实动作（读架构、写账本、run_task、真跑读数字、落 docs/CHANGELOG…）。
 * 交互：拖动旋转 / 滚轮缩放；标记 data-mindmap。
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

document.documentElement.dataset.mindmap = "imported";

const TREE = [
  { name: "理解需求", hue: 0.58, leaves: ["读架构/契约", "危险=终端·转账", "先定验收数字"] },
  { name: "拆解计划", hue: 0.50, leaves: ["套七步链", "写任务账本", "排好依赖"] },
  { name: "执行落地", hue: 0.08, leaves: ["run_task 派单", "五处落位", "可用即测"] },
  { name: "验证取证", hue: 0.33, leaves: ["真跑读数字", "截图/哈希", "失败即修"] },
  { name: "留痕固化", hue: 0.72, leaves: ["orchestration-ledger", "docs 编号", "CHANGELOG"] },
  { name: "交付报告", hue: 0.95, leaves: ["给数字不空话", "说清差距", "写剩余阻塞"] },
];

let renderer, scene, camera, controls, composer, bloom;
let inited = false, running = false, raf = 0;
let leafCount = 0;

function labelSprite(text, color, scale, size) {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 96;
  const ctx = c.getContext("2d");
  ctx.font = "600 " + (size || 40) + "px 'JetBrains Mono', monospace";
  ctx.fillStyle = color; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, 256, 48);
  const tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
  const s = scale || 2.6;
  sp.scale.set(s, s * 0.19, 1);
  return sp;
}

function glowSprite(color, size, opacity) {
  const c = document.createElement("canvas");
  c.width = 128; c.height = 128;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
  g.addColorStop(0, "rgba(255,255,255,.9)");
  g.addColorStop(0.32, "rgba(255,255,255,.22)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  const m = new THREE.SpriteMaterial({ map: tex, color: color, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false, opacity: opacity || 0.85 });
  const sp = new THREE.Sprite(m);
  sp.scale.set(size, size, 1);
  return sp;
}

function branchPos(i, n) {
  const a = (i / n) * Math.PI * 2;
  return new THREE.Vector3(Math.cos(a) * 6.4, (i % 2 === 0 ? 1 : -1) * 1.1, Math.sin(a) * 6.4);
}

function init() {
  if (inited) return true;
  const canvas = document.getElementById("mindmap-canvas");
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true,
      preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x03070d, 0.010);
    camera = new THREE.PerspectiveCamera(46, 1, 0.1, 400);
    camera.position.set(0, 10, 17);
    camera.lookAt(0, 0, 0);

    // 中心「任务指引」
    const core = new THREE.Mesh(new THREE.SphereGeometry(0.95, 40, 40),
      new THREE.MeshStandardMaterial({ color: 0xffb45c, emissive: 0xff8a1f,
        emissiveIntensity: 0.9, metalness: 0.3, roughness: 0.4 }));
    scene.add(core);
    scene.add(glowSprite(0xff9f1c, 7.5, 0.5));
    const coreLbl = labelSprite("任务指引", "#ffe6b8", 2.6, 44);
    coreLbl.position.set(0, 1.75, 0);
    scene.add(coreLbl);

    const branchMat = new THREE.MeshStandardMaterial({
      color: 0x9fb3d1, metalness: 0.7, roughness: 0.4,
      emissive: 0x12203a, emissiveIntensity: 0.5 });
    const linkMat = new THREE.LineBasicMaterial({ color: 0x6f86a8, transparent: true,
      opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false });

    TREE.forEach(function (b, i) {
      const bp = branchPos(i, TREE.length);
      const color = new THREE.Color().setHSL(b.hue, 0.8, 0.6);
      // 中心 → 分支（弯曲管道）
      const mid = bp.clone().multiplyScalar(0.55).add(new THREE.Vector3(0, 1.6, 0));
      const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(0, 0, 0), mid, bp], false,
                                              "catmullrom", 0.6);
      scene.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 60, 0.05, 8, false), branchMat));

      // 分支节点
      const node = new THREE.Mesh(new THREE.SphereGeometry(0.36, 24, 24),
        new THREE.MeshStandardMaterial({ color: color, emissive: color,
          emissiveIntensity: 0.9, metalness: 0.3, roughness: 0.4 }));
      node.position.copy(bp);
      scene.add(node);
      const gl = glowSprite(color.getHex(), 2.0, 0.7);
      gl.position.copy(bp);
      scene.add(gl);
      const bl = labelSprite(b.name, "#e6f0ff", 2.8, 42);
      bl.position.copy(bp).add(new THREE.Vector3(0, 0.85, 0));
      scene.add(bl);

      // 3 片叶子：绕分支向外散开
      b.leaves.forEach(function (leaf, k) {
        const ang = (k / b.leaves.length) * Math.PI * 2 + i * 0.7;
        const off = new THREE.Vector3(Math.cos(ang) * 2.0, 0.55 + (k - 1) * 0.28,
                                      Math.sin(ang) * 2.0);
        const lp = bp.clone().add(off);
        // 分支 → 叶子（细线）
        const lg = new THREE.BufferGeometry().setFromPoints([bp, lp]);
        scene.add(new THREE.Line(lg, linkMat));
        const ln = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 16),
          new THREE.MeshStandardMaterial({ color: color, emissive: color,
            emissiveIntensity: 0.7, metalness: 0.2, roughness: 0.5 }));
        ln.position.copy(lp);
        scene.add(ln);
        const ll = labelSprite(leaf, "#c9d8ee", 2.9, 34);
        ll.position.copy(lp).add(new THREE.Vector3(0, 0.42, 0));
        scene.add(ll);
        leafCount++;
      });
    });

    // 星尘
    const DUST = 1600;
    const arr = new Float32Array(DUST * 3);
    for (let i = 0; i < DUST; i++) {
      const r = 13 + Math.random() * 30;
      const th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
      arr[i * 3] = r * Math.sin(ph) * Math.cos(th);
      arr[i * 3 + 1] = r * Math.cos(ph) * 0.55;
      arr[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    }
    const dg = new THREE.BufferGeometry();
    dg.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    scene.add(new THREE.Points(dg, new THREE.PointsMaterial({
      color: 0x8fa6c4, size: 0.09, transparent: true, opacity: 0.32, depthWrite: false })));

    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const l1 = new THREE.PointLight(0xff9a3c, 2.0, 70); l1.position.set(4, 8, 6); scene.add(l1);
    const l2 = new THREE.PointLight(0x4f8cff, 1.4, 70); l2.position.set(-6, -4, -5); scene.add(l2);

    const wrap = document.querySelector(".view-mind") || canvas;
    controls = new OrbitControls(camera, wrap);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.28;
    controls.enablePan = false;
    controls.minDistance = 9;
    controls.maxDistance = 46;
    controls.rotateSpeed = 0.75;

    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.35, 0.45, 0.72);
    composer.addPass(bloom);

    resize();
    inited = true;
    document.documentElement.dataset.mindmap = "ok:" + TREE.length + "支+" + leafCount + "叶";
    draw();
    return true;
  } catch (e) {
    document.documentElement.dataset.mindmap = "error:" + String((e && e.message) || e).slice(0, 120);
    return false;
  }
}

function resize() {
  const c = document.getElementById("mindmap-canvas");
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
  controls.update();
  draw();
}

export function start() { if (!init()) return; if (running) return; running = true; loop(); }
export function stop() { running = false; if (raf) { cancelAnimationFrame(raf); raf = 0; } }

window.__mindmap = { start, stop, get ok() { return inited; } };
window.addEventListener("gbt:view", function (e) { if (e.detail === "mind") start(); else stop(); });
window.addEventListener("resize", function () { resize(); if (!running && renderer) draw(); });
if ((location.hash || "").replace("#", "") === "mind") setTimeout(start, 60);
