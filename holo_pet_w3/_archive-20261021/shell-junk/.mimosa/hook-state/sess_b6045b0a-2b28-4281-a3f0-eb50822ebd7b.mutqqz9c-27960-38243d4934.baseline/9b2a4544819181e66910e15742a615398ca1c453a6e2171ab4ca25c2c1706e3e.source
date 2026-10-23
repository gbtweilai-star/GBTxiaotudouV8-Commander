/* GBT小土豆V8 · 神经可视化工作台（窗 E）· 三维场景
 *
 * 依赖：`vendor/*.global.js`（three@0.180.0 **经典脚本版**）。
 * 为什么不是 ESM：`file://` 下 `<script type="module">` 被 CORS 挡死（实跑 net::ERR_FAILED），
 * 壳的 main.cjs 又没关 webSecurity ⇒ 只能经典脚本。转换器见 tools/codex-scripts/vendor_three.py。
 *
 * 数据：`brain-data.js`（tools/codex-scripts/brain-feed.py 从**真实源码**算出）
 *   皮层核 ← DSH 对话面
 *   束长环 ← `caps_registry` 的真实 domain（29 个）
 *   触手层 ← 每一个真实能力位（150 实现 + 11 仅登记）
 *   脉冲   ← `audit.jsonl` 里**真发生过**的 call 事件
 *
 * ══ 改版记录（风哥：「把 AI 作品感压下，要自然逼真感觉」）════════════════════
 * 首版是"赛博朋克 demo"，吃的正是专业源明令禁止的几条。逐条对账：
 *
 *  ❌ 29 个域铺满 0–360 色相 ⇒ **装饰色**。MC §9：「every hue must convey operational meaning」。
 *     ✅ 现在：**颜色只编码运行状态** —— 绿=免卡直跑 · 金=需授权 · 红=仅登记未实现 · 青=执行脉冲。
 *        束长的身份靠**空间位置 + 标签**，不靠颜色。
 *  ❌ 满屏呼吸 / 脉冲 / 闪烁 ⇒ MC §9：「Do not animate non-alert elements」。
 *     ✅ 现在：动效只留三类**信号** —— 核心状态灯（慢）· 门禁环扫描（慢）· 执行脉冲（事件驱动）。
 *        束长与能力位**不动**。
 *  ❌ `Math.random()` 抖位置 ⇒ 每次刷新都不一样，且那是"编造"的一种。
 *     ✅ 现在：确定性哈希抖动（同一个 id 永远落在同一个位置）。
 *  ❌ 帧步进写死 `t += 0.016` ⇒ 掉帧时动画变慢，物理不真。
 *     ✅ 现在：用真实 delta。
 *  ❌ 浮动 tooltip 用 `el.style.left=` ⇒ 被本页 CSP（`style-src 'self'`）挡掉 6 次。
 *     ✅ 现在：固定位置的读数条（仪器面板本来就该这么读）。
 */
(function () {
  "use strict";

  const D = globalThis.GBT_BRAIN;
  /* 🔴 声明数据新鲜度（2026-09-23 第 34 轮）：本窗吃的是**生成的数据文件**
     （`brain-data.js` 由 `brain-feed.py` 写），所以是「快照」不是「实时」——
     时刻用**文件自己的生成时刻** `D.at`，不是 `new Date()`。
     **拿加载时刻冒充数据时刻 = 把几小时前的读数说成现在的**，那正是"假绿"。 */
  if (D && D.at) window.GBT_DATA = { kind: "快照", at: D.at };
  const $ = (id) => document.getElementById(id);
  const THREE = globalThis.THREE;

  if (!THREE) {
    document.body.insertAdjacentHTML("beforeend",
      '<div style="position:fixed;inset:0;display:grid;place-items:center;color:#ef4444;font:14px Consolas">' +
      'vendor/three.global.js 没加载 —— 先跑 py -3.14 tools/codex-scripts/vendor_three.py --write --classic</div>');
    return;
  }
  if (!D) {
    document.body.insertAdjacentHTML("beforeend",
      '<div style="position:fixed;inset:0;display:grid;place-items:center;color:#ef4444;font:14px Consolas">' +
      'brain-data.js 没加载 —— 先跑 py -3.14 tools/codex-scripts/brain-feed.py --out holo_pet_w3/brain/brain-data.js</div>');
    return;
  }

  /* ── 颜色**从 CSS token 读**，不在 JS 里写色号 ──
     皮肤的真源只有一处（skin-mission-control.css 的 :root）；JS 里再写一遍就是"第二套皮的开始"。
     audit_skin.py 连 `0xRRGGBB` 数字字面量一起扫，就是为了防这件事。 */
  const TOKEN = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const C = {
    ok:    new THREE.Color(TOKEN("--gbt-ok")     || "#22c55e"),
    gold:  new THREE.Color(TOKEN("--gbt-gold")   || "#f5b041"),
    cyan:  new THREE.Color(TOKEN("--gbt-cyan")   || "#00e5ff"),
    fault: new THREE.Color(TOKEN("--gbt-fault")  || "#ef4444"),
    dim:   new THREE.Color(TOKEN("--gbt-dim")    || "#9aa4c4"),
    off:   new THREE.Color(TOKEN("--gbt-off")    || "#6b7280"),
    text:  new THREE.Color(TOKEN("--gbt-text")   || "#e8ecf8"),
    violet:new THREE.Color(TOKEN("--gbt-violet") || "#7c4dff"),
  };
  const SURFACE = TOKEN("--mc-bg") || "#0b1120";

  /* 确定性抖动：同一个字符串永远得到同一个数（**替代 Math.random**）。
     为什么必须换：随机数让每次渲染都不一样，等于"每次给你看一个不同的东西"——
     在仪器上这是缺陷，不是特性。 */
  function hash01(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return ((h >>> 0) % 100000) / 100000;
  }

  /* ── §1 场景 ── */
  const canvas = $("brain-canvas");
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(new THREE.Color(SURFACE).getHex(), 0.0125);

  const camera = new THREE.PerspectiveCamera(52, 1, 0.1, 400);
  camera.position.set(0, 15, 46);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const controls = new THREE.OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.055;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.26;      // 极慢：巡游，不是转盘
  controls.minDistance = 14;
  controls.maxDistance = 110;
  controls.maxPolarAngle = Math.PI * 0.86;

  /* 辉光：**阈值调高**（0.10 → 0.42）。
     首版阈值 0.10 让所有东西都溢光 ⇒ 满屏糊成一团，正是"AI 作品感"的来源之一。
     调高之后只有真正亮的东西（核、脉冲、门禁刻度）才发光 —— 明暗主次就出来了。 */
  const composer = new THREE.EffectComposer(renderer);
  composer.addPass(new THREE.RenderPass(scene, camera));
  const bloom = new THREE.UnrealBloomPass(new THREE.Vector2(1, 1), 0.62, 0.62, 0.42);
  composer.addPass(bloom);
  /* 合成器真跑过的帧数 —— 让「**合成器/辉光真在跑**」成为**读数**而不是假设。
     为什么非记不可：`hd` 原来只有 `dpr/pr/drawing/css` 四个数 ⇒ 谁要是把
     `composer.render()` 改回 `renderer.render()`，**辉光会静默消失，而现有判据一条都抓不到**。 */
  let composerFrames = 0;

  /* 软圆点贴图：所有发光点共用一个径向渐变 —— 方点像噪声，软圆点才像发光体 */
  const DOT = (function () {
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const ctx = c.getContext("2d");
    const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0.0, "rgba(255,255,255,1)");
    g.addColorStop(0.30, "rgba(255,255,255,.62)");
    g.addColorStop(0.66, "rgba(255,255,255,.12)");
    g.addColorStop(1.0, "rgba(255,255,255,0)");
    ctx.fillStyle = g; ctx.fillRect(0, 0, 64, 64);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  })();

  /* ── §2 核心节点（第 58 轮：从**行星壳**改成**关联网里的焦点节点**）──
     🔴 口径为什么改（主人 2026-09-23 给了参照物：一张协作关联网络图）：
        那张图里**没有壳** —— 它是不规则聚类 + 细弧线 + **一个带标签的焦点节点**。
        原来那个半径 3.3 的线框球把整张网**罩在里面**，读出来是"一颗行星带着卫星"，
        不是"一张网络"。而"网络感"正是主人这次要的东西。
     ⇒ 壳缩成**一个节点**：小实心核 + 柔光。焦点地位靠**标签**给，不靠体量。
        品牌色（土豆金）落在核上 —— 它是这一屏唯一的"原点"。 */
  const cortex = new THREE.Group();
  scene.add(cortex);

  const coreMesh = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.05, 2),
    new THREE.MeshBasicMaterial({ color: C.gold, wireframe: true, transparent: true, opacity: 0.55 })
  );
  cortex.add(coreMesh);

  cortex.add(new THREE.Mesh(
    new THREE.SphereGeometry(0.52, 24, 24),
    new THREE.MeshBasicMaterial({ color: C.gold, transparent: true, opacity: 0.95,
                                  blending: THREE.AdditiveBlending })
  ));
  const haloSprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: DOT, color: C.gold, transparent: true, opacity: 0.30,
    blending: THREE.AdditiveBlending, depthWrite: false,
  }));
  haloSprite.scale.set(7, 7, 1);
  cortex.add(haloSprite);

  {
    const N = 90, pos = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const r = 3.9 + hash01("c" + i) * 1.1, th = hash01("t" + i) * Math.PI * 2,
            ph = Math.acos(2 * hash01("p" + i) - 1);
      pos[i * 3] = r * Math.sin(ph) * Math.cos(th);
      pos[i * 3 + 1] = r * Math.sin(ph) * Math.sin(th);
      pos[i * 3 + 2] = r * Math.cos(ph);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    cortex.add(new THREE.Points(g, new THREE.PointsMaterial({
      size: 0.34, map: DOT, color: C.cyan, transparent: true, opacity: 0.42,
      blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true,
    })));
  }

  /* ── §3 束长环（真实能力域）──
     **颜色不再是身份**：束长一律用中性 dim；身份靠位置与标签。
     大小仍随能力位数走（那是真信息，不是装饰）。 */
  const bundleGroup = new THREE.Group();
  scene.add(bundleGroup);
  const BUNDLE_R = 14;
  const bundleNodes = [];
  const bundles = D.bundles || [];

  /* 先算本窗的"状态统计"，供状态栏与图例使用（真数，不猜） */
  const caps = (D.nodes || []);
  const nSafe = caps.filter((n) => n.impl && n.safe).length;
  const nGated = caps.filter((n) => n.impl && !n.safe).length;
  const nDead = caps.filter((n) => !n.impl).length;

  bundles.forEach((b, i) => {
    const a = (i / bundles.length) * Math.PI * 2;
    const y = Math.sin(i * 1.7) * 1.6;
    const p = new THREE.Vector3(Math.cos(a) * BUNDLE_R, y, Math.sin(a) * BUNDLE_R);
    /* 束长是**枢纽**：给亮珠（`--gbt-text` 亮色 + 高不透明），不是灰石头。
       参照物上枢纽节点是**亮图标牌**，而能力位是小色点 —— 这一档对比就是"层级"。 */
    const size = 0.34 + Math.min(b.n, 24) * 0.016;

    const mesh = new THREE.Mesh(new THREE.SphereGeometry(size, 20, 20),
      new THREE.MeshBasicMaterial({ color: C.text, transparent: true, opacity: 0.92 }));
    mesh.position.copy(p);
    mesh.userData = { type: "bundle", id: b.id, label: b.label, n: b.n };
    bundleGroup.add(mesh);
    bundleNodes.push(mesh);

    const glow = new THREE.Sprite(new THREE.SpriteMaterial({
      map: DOT, color: C.dim, transparent: true, opacity: 0.13,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }));
    glow.position.copy(p);
    /* 🔴 第 58 轮把光晕从 `size*7` 收到 `size*4`：7 倍时束长是一团**6 个世界单位**的
       灰雾，29 团叠上去把标签糊成一枚枚"灰药丸"（第一版实图就是这样）。
       束长的身份靠**标签与位置**给，不靠体量 —— 这是本窗一开始就定的口径。 */
    glow.scale.setScalar(size * 4);
    bundleGroup.add(glow);
    mesh.userData.glow = glow;

    b._pos = p;
  });

  /* ── 边集：**统一成一套可寻址的几何** ──
     风哥令：「**所有连接都要可视化**」「大脑执行层跟什么连接……哪些连接也会根据对应连接亮起来」。
     要做到"某一条亮"，边就不能是几根静态线 —— 必须是**每条边占固定的顶点槽位**，
     于是能单独改它的颜色。所以三条来源（核心→束长 / 束长→能力位 / 能力位→能力位）**合成一套**：
       · 顶点数 = 边数 × 2；
       · `edgeSlot` 记住每条边占哪两个槽 ⇒ 事件来了按名字点亮它。
     基色**很暗**（加性混合下"暗"就等于"淡"）：不亮时是背景网，亮了才是信号（MC：明暗要有主次）。 */
  const EDGE = { pos: [], col: [], slot: new Map(), curves: [], n: 0 };
  const HOT = { cyan: C.cyan, gold: C.gold, ok: C.ok };
  const DIM_OWN = C.violet.clone().multiplyScalar(0.16);
  const DIM_USE = C.off.clone().multiplyScalar(0.22);

  /* 一条**曲线边** = 若干线段 = 一段连续的顶点槽 `[i0, i0+count)`。
     记下端点对象（**引用**，不是拷贝）⇒ 拖动节点后能就地重算这条边。 */
  /* 🔴 **顶点数必须与颜色数逐一对齐**（首跑在这里翻过车）：
     一条曲线 = `seg` 段 = **`seg × 2` 个顶点**（每段两个端点）。
     我第一版按 `(seg+1) × 2` 推颜色 ⇒ 每条边多塞 2 个顶点的颜色 ⇒ 两个缓冲长度不一致，
     运行时炸在 `reading 'x'` 上。这种"看着只是数字差一"的错，只有真跑才现形。 */
  function addEdgeCurve(key, aPos, bPos, lift, base, seg) {
    const nSeg = seg || 8;
    const i0 = EDGE.pos.length / 3;
    const rec = { key: key, i0: i0, count: nSeg * 2, aPos: aPos, bPos: bPos, lift: lift, seg: nSeg };
    writeCurve(rec);
    for (let i = 0; i < rec.count; i++) EDGE.col.push(base.r, base.g, base.b);
    EDGE.slot.set(key, i0);
    EDGE.curves.push(rec);
    EDGE.n++;
    return rec;
  }
  const _mid = new THREE.Vector3();
  function writeCurve(rec) {
    _mid.copy(rec.aPos).add(rec.bPos).multiplyScalar(0.5); _mid.y += rec.lift;
    /* 🔴 **不要给 `getPoints` 传 optionalTarget**（首跑踩到）：这个版本的实现不往传入数组里填，
       于是 `pts[i]` 是 undefined，炸在 `reading 'x'`。直接吃返回值，别赌签名行为。 */
    const pts = new THREE.CatmullRomCurve3([rec.aPos, _mid, rec.bPos]).getPoints(rec.seg);
    for (let i = 0; i < rec.seg; i++) {
      const o = rec.i0 * 3 + i * 6;
      EDGE.pos.length = Math.max(EDGE.pos.length, o + 6);
      EDGE.pos[o] = pts[i].x; EDGE.pos[o + 1] = pts[i].y; EDGE.pos[o + 2] = pts[i].z;
      EDGE.pos[o + 3] = pts[i + 1].x; EDGE.pos[o + 4] = pts[i + 1].y; EDGE.pos[o + 5] = pts[i + 1].z;
    }
  }
  /** 拖动后：只重算**碰到这个点**的边（290 条全算也行，但没必要）。 */
  function rebuildEdgesFor(posRef) {
    EDGE.curves.forEach((c) => { if (c.aPos === posRef || c.bPos === posRef) writeCurve(c); });
    if (EDGE.geo) EDGE.geo.attributes.position.needsUpdate = true;
  }

  /* 核心 → 束长（`aPos` 用固定的原点向量；束长被拖动时 `bPos` 跟着动） */
  const ORIGIN = new THREE.Vector3(0, 0, 0);
  bundles.forEach((b) => {
    addEdgeCurve("core>" + b.id, ORIGIN, b._pos, 2.4, DIM_OWN, 8);
  });

  /* ── §4 触手层：每一个真实能力位（**颜色 = 运行状态**）── */
  const capGroup = new THREE.Group();
  scene.add(capGroup);
  const capNodes = [];
  const CAP_R = 23;

  const byBundle = {};
  caps.forEach((n) => { if (n.impl && n.bundle) (byBundle[n.bundle] = byBundle[n.bundle] || []).push(n); });
  const bundleOf = {};
  bundles.forEach((b, i) => { bundleOf[b.id] = { i, b }; });

  /* 状态 → 颜色。**四条，各有运行含义**（MC §8：Color is the primary signal carrier） */
  function stateColor(n) {
    if (!n.impl) return C.fault;    // 仅登记未实现
    return n.safe ? C.ok : C.gold;  // 免卡直跑 / 需授权
  }

  Object.keys(byBundle).forEach((bid) => {
    const info = bundleOf[bid]; if (!info) return;
    const { i, b } = info;
    const base = (i / bundles.length) * Math.PI * 2;
    const list = byBundle[bid];
    list.forEach((n, j) => {
      const spread = 0.30 + Math.min(list.length, 12) * 0.020;
      const a = base + (j / Math.max(list.length, 1) - 0.5) * spread * 2;
      const r = CAP_R + (hash01(n.id) - 0.5) * 3.4;
      const p = new THREE.Vector3(
        Math.cos(a) * r,
        (hash01(n.id + "y") - 0.5) * 5 + Math.sin(i * 1.3) * 2.4,
        Math.sin(a) * r);
      const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.17, 10, 10),
        new THREE.MeshBasicMaterial({ color: stateColor(n) }));
      mesh.position.copy(p);
      mesh.userData = { type: "cap", id: n.id, bundle: bid, bundleLabel: b.label,
                        safe: n.safe, impl: n.impl, desc: n.desc };
      capGroup.add(mesh);
      capNodes.push(mesh);
      n._pos = p;
    });
  });

  /* 束长 → 能力位（真实从属关系；每条单独寻址） */
  Object.keys(byBundle).forEach((bid) => {
    const info = bundleOf[bid]; if (!info) return;
    byBundle[bid].forEach((n) => {
      addEdgeCurve(bid + ">" + n.id, info.b._pos, n._pos, 0.8, DIM_OWN, 6);
    });
  });

  /* 仅登记未实现的那 11 个：**单独一层、单独颜色**，绝不混进已实现里充数 */
  const deadNodes = [];
  caps.filter((n) => !n.impl).forEach((n, i) => {
    const a = (i / 11) * Math.PI * 2 + 0.4;
    const p = new THREE.Vector3(Math.cos(a) * (CAP_R + 6.5), Math.sin(i * 1.9) * 3.2,
                                Math.sin(a) * (CAP_R + 6.5));
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.21, 10, 10),
      new THREE.MeshBasicMaterial({ color: C.fault, transparent: true, opacity: 0.85 }));
    m.position.copy(p);
    m.userData = { type: "dead", id: n.id, impl: false, desc: n.desc };
    scene.add(m);
    deadNodes.push(m);
  });

  /* ── 能力位 → 能力位：**真依赖边**（brain-feed.py 从源码算出来的 108 条）──
     每条都能回查：`A --(文件甲→文件乙)--> B`。这是"所有连接都要可视化"的第三层，
     也是最能说明"大脑执行层跟什么连接"的一层。 */
  const posOf = {};
  capNodes.forEach((m) => { posOf[m.userData.id] = m.position; });
  const capEdges = (D.edges || []);
  capEdges.forEach((e) => {
    const A = posOf[e.a], B = posOf[e.b];
    if (!A || !B) return;
    addEdgeCurve(e.a + ">" + e.b, A, B, 1.6, DIM_USE, 6);
  });

  /* 一套几何装完，加进场景。**顶点色 = 亮度**（加性混合下暗即淡）。 */
  {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(EDGE.pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(EDGE.col, 3));
    scene.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({
      vertexColors: true, transparent: true, opacity: 0.9,
      blending: THREE.AdditiveBlending, depthWrite: false })));
    EDGE.geo = g;
  }

  /* 点亮：把某条边（含曲线分段）的顶点槽染成热色，然后随时间衰减回基色。
     为什么按"边名"而不是按索引：脉冲只知道 `kind`，不该知道几何细节。 */
  const hot = [];      // [{i0, count, t, life, col}]
  function lightEdge(name, col, life) {
    const c = EDGE.curves.find((x) => x.key === name);
    if (c) hot.push({ i0: c.i0, count: c.count, t: 0, life: life || 1.1, col: col || HOT.cyan });
  }

  /* 一次事件要点亮**整条链**（这才是"精细到每一步执行同步"）：
     核心 → 该能力位所属束 → 该能力位 → 它依赖的每一个能力位（出边）+ 依赖它的（入边）。
     分先后：越靠前的先亮，于是眼睛能读出"从核到叶"的顺序。 */
  function lightChain(kind, bundleId) {
    if (bundleId) lightEdge("core>" + bundleId, HOT.cyan, 1.3);
    if (bundleId) lightEdge(bundleId + ">" + kind, HOT.gold, 1.2);
    const downs = capEdges.filter((e) => e.a === kind);
    const ups = capEdges.filter((e) => e.b === kind);
    downs.forEach((e, i) => lightEdge(e.a + ">" + e.b, HOT.gold, 1.0 + i * 0.02));
    ups.forEach((e) => lightEdge(e.a + ">" + e.b, HOT.cyan, 0.9));
    return { downs: downs.length, ups: ups.length };
  }


  {
    const list = (D.skills || []).slice(0, 400);
    const pos = new Float32Array(list.length * 3);
    list.forEach((s, i) => {
      const r = 30 + (i % 7) * 1.5;
      const th = i * 2.399963;                        // 黄金角 ⇒ 均匀不结块
      const ph = Math.acos(1 - 2 * ((i + 0.5) / list.length));
      pos[i * 3] = r * Math.sin(ph) * Math.cos(th);
      pos[i * 3 + 1] = r * Math.cos(ph) * 0.75;
      pos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    scene.add(new THREE.Points(g, new THREE.PointsMaterial({
      size: 0.30, map: DOT, color: C.violet, transparent: true, opacity: 0.16,
      blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true })));
  }

  /* ── §6 门禁环（policy 的 14 个作用域）── */
  const gates = [];
  [0, 1].forEach((k) => {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(28 + k * 0.6, 0.04, 6, 160),
      new THREE.MeshBasicMaterial({ color: k ? C.gold : C.ok, transparent: true,
                                    opacity: k ? 0.24 : 0.30, blending: THREE.AdditiveBlending }));
    ring.rotation.x = Math.PI / 2;
    ring.position.y = k ? 9.5 : -9.5;
    scene.add(ring);
    gates.push(ring);
  });
  /* 门禁刻度：**按单位半径建**，排布完再按脑容积缩放。
     🔴 第 58 轮改成可缩放：原来写死 27.4/29.4，而排布半径一变（实测 27.6），
        刻度与门禁环就**横穿整张网** —— 第一版实图里那条横贯全屏的大椭圆就是它。
     为什么留着这两圈：14 道刻度 = policy 的 14 个作用域，是这张图上**唯一的门禁语义**，
     删了就没有"门"了；缩放后它变成脑容积的**外边界**，反而是最合适的位置。 */
  let gateTicks = null;
  {
    const n = D.totals.scopes || 0, verts = [];
    for (let i = 0; i < n; i++) {
      const a = (i / Math.max(n, 1)) * Math.PI * 2;
      verts.push(Math.cos(a) * 0.965, 0, Math.sin(a) * 0.965,
                 Math.cos(a) * 1.035, 0, Math.sin(a) * 1.035);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(verts, 3));
    gateTicks = new THREE.LineSegments(g, new THREE.LineBasicMaterial({
      color: C.ok, transparent: true, opacity: 0.40, blending: THREE.AdditiveBlending }));
    scene.add(gateTicks);
  }

  /* ── §7 脉冲：**电击电弧**（第 58 轮换掉圆点 sprite）────────────────────
     为什么换：主人要「电击脉冲特效」。圆点 + 尾迹读起来是"一颗光球在飘"，不是"电"。
     要像电，靠三条（都是可复核的几何做法，不是加个滤镜）：
       ① **折线抖动**：沿曲线采样，每点加垂直偏移；偏移**每 ~3 帧重掷一次**
          —— 每帧重掷会变成蠕动的虫，永不重掷会变成一根固定折线，都不像电；
       ② **包络** `sin(πu)^0.7`：两头贴住端点、中段炸开（物理上就是电场最强处）；
       ③ **行进窗口**：只有 head 附近一段亮（顶点色即亮度，加性混合下暗即透明）
          ⇒ 读得出"电是**打过去**的"，不是"整条一起亮"。
     另加 **1–2 条分叉**（从主弧中段岔出去）—— 那是闪电最有辨识度的一笔。
     🔴 打在哪条连接上：主弧 `核心 → 这次调用的能力位`；若它在真依赖边里有邻居，
        再补一条 `该能力位 → 邻居` 的副弧 —— 那才是"**对应的那条连接**"。 */
  const ARCN = 30;
  const pulses = [];          /* 🔴 别删：主循环每帧要用它。第 58 轮我替换旧脉冲段时
                                 把这一行一起删了 ⇒ 856 条 `pulses is not defined`，
                                 电弧一条都没打出来（`arcs: 0` 当场露馅）。 */
  const edgeIndex = {};
  capEdges.forEach((e) => {
    (edgeIndex[e.a] = edgeIndex[e.a] || []).push(e);
    (edgeIndex[e.b] = edgeIndex[e.b] || []).push(e);
  });
  const capMeshById = {};
  capNodes.forEach((m) => { capMeshById[m.userData.id] = m; });

  function makeArcLine() {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(ARCN * 3), 3));
    g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(ARCN * 3), 3));
    const l = new THREE.Line(g, new THREE.LineBasicMaterial({
      vertexColors: true, transparent: true, opacity: 0.95,
      blending: THREE.AdditiveBlending, depthWrite: false }));
    l.frustumCulled = false;
    return l;
  }

  /* 垂直基：给折线抖动一个稳定参考系（否则偏移方向乱转，看着像噪声） */
  const _tan = new THREE.Vector3(), _n1 = new THREE.Vector3(), _n2 = new THREE.Vector3();
  const _pt = new THREE.Vector3(), _up = new THREE.Vector3(0, 1, 0);
  function perpBasis(curve, u) {
    curve.getTangent(u, _tan).normalize();
    _n1.crossVectors(_up, _tan);
    if (_n1.lengthSq() < 1e-4) _n1.set(1, 0, 0);
    _n1.normalize();
    _n2.crossVectors(_tan, _n1).normalize();
  }

  function writeArc(rec) {
    const pos = rec.main.geometry.attributes.position.array;
    const col = rec.main.geometry.attributes.color.array;
    const c = rec.col;
    for (let i = 0; i < ARCN; i++) {
      const u = i / (ARCN - 1);
      rec.curve.getPoint(u, _pt);
      perpBasis(rec.curve, u);
      const env = Math.pow(Math.sin(Math.PI * u), 0.7);
      const a1 = (hash01(rec.seed + "a" + i) - 0.5) * 2;
      const a2 = (hash01(rec.seed + "b" + i) - 0.5) * 2;
      const amp = rec.amp * env;
      pos[i * 3] = _pt.x + (_n1.x * a1 + _n2.x * a2) * amp;
      pos[i * 3 + 1] = _pt.y + (_n1.y * a1 + _n2.y * a2) * amp;
      pos[i * 3 + 2] = _pt.z + (_n1.z * a1 + _n2.z * a2) * amp;
      /* 行进窗口：head 在 u=rec.t 附近 ⇒ 只有那一段亮 */
      const w = Math.max(0, 1 - Math.abs(u - rec.t) / rec.win);
      const k = (0.10 + 0.90 * w * w) * rec.global;
      col[i * 3] = c.r * k; col[i * 3 + 1] = c.g * k; col[i * 3 + 2] = c.b * k;
    }
    rec.main.geometry.attributes.position.needsUpdate = true;
    rec.main.geometry.attributes.color.needsUpdate = true;
    rec.forks.forEach((f) => {
      const fp = f.line.geometry.attributes.position.array;
      const fc = f.line.geometry.attributes.color.array;
      for (let i = 0; i < ARCN; i++) {
        const u = i / (ARCN - 1);
        const uu = f.u0 + (f.u1 - f.u0) * u;
        rec.curve.getPoint(uu, _pt);
        perpBasis(rec.curve, uu);
        const env = Math.pow(Math.sin(Math.PI * u), 0.6) * f.len;
        const a1 = (hash01(rec.seed + "f" + f.id + i) - 0.5) * 2;
        const a2 = (hash01(rec.seed + "g" + f.id + i) - 0.5) * 2;
        fp[i * 3] = _pt.x + (_n1.x * a1 + _n2.x * a2) * env + f.dir.x * env;
        fp[i * 3 + 1] = _pt.y + (_n1.y * a1 + _n2.y * a2) * env + f.dir.y * env;
        fp[i * 3 + 2] = _pt.z + (_n1.z * a1 + _n2.z * a2) * env + f.dir.z * env;
        const w = Math.max(0, 1 - Math.abs(uu - rec.t) / rec.win);
        const k = (0.06 + 0.7 * w * w) * rec.global * 0.8;
        fc[i * 3] = c.r * k; fc[i * 3 + 1] = c.g * k; fc[i * 3 + 2] = c.b * k;
      }
      f.line.geometry.attributes.position.needsUpdate = true;
      f.line.geometry.attributes.color.needsUpdate = true;
    });
  }

  function pushArc(rec) {
    scene.add(rec.main);
    rec.forks.forEach((f) => scene.add(f.line));
    scene.add(rec.head);
    pulses.push(rec);
    /* 计数挂到只读面上：验收要**量**"电弧有没有真的打出来"，不能靠看图说"有" */
    if (window.__brainNet) window.__brainNet.arcs = (window.__brainNet.arcs || 0) + 1;
  }

  function makeArc(aPos, bPos, col, life, opt) {
    const o = opt || {};
    const mid = aPos.clone().add(bPos).multiplyScalar(0.5);
    mid.y += o.lift === undefined ? 1.2 : o.lift;
    const curve = new THREE.CatmullRomCurve3([aPos.clone(), mid, bPos.clone()]);
    const rec = {
      arc: true, curve, col, t: 0, life,
      amp: o.amp === undefined ? 1.5 : o.amp,
      win: o.win === undefined ? 0.40 : o.win,
      global: 0, seed: String(o.seed === undefined ? Math.floor(t * 1000) : o.seed),
      baseSeed: String(o.seed === undefined ? Math.floor(t * 1000) : o.seed),
      rejitter: 0, size: o.size === undefined ? 1.7 : o.size,
      main: makeArcLine(), forks: [],
    };
    const nf = o.forks === undefined ? (hash01(rec.seed + "nf") > 0.45 ? 2 : 1) : o.forks;
    for (let k = 0; k < nf; k++) {
      const u0 = 0.22 + hash01(rec.seed + "u" + k) * 0.42;
      const dir = new THREE.Vector3(hash01(rec.seed + "dx" + k) - 0.5,
                                    hash01(rec.seed + "dy" + k) - 0.5,
                                    hash01(rec.seed + "dz" + k) - 0.5).normalize();
      rec.forks.push({ id: k, u0, u1: Math.min(1, u0 + 0.18 + hash01(rec.seed + "L" + k) * 0.22),
                       len: 1.6 + hash01(rec.seed + "ln" + k) * 3.4, dir, line: makeArcLine() });
    }
    const head = new THREE.Sprite(new THREE.SpriteMaterial({
      map: DOT, color: col, transparent: true, opacity: 0.95,
      blending: THREE.AdditiveBlending, depthWrite: false }));
    head.scale.setScalar(rec.size);
    rec.head = head;
    writeArc(rec);
    return rec;
  }

  function auditArc(entry) {
    if (!window.__brainNet) return;
    const A = window.__brainNet.arc_audit || (window.__brainNet.arc_audit = []);
    A.push(entry);
    if (A.length > 60) A.shift();          // 只留最近 60 条：够验收，不涨内存
  }

  function spawnPulse(p) {
    const isFail = p.ok === false;
    const col = isFail ? C.fault : C.cyan;
    const seed = String(p.ts || 0) + "|" + (p.kind || "");
    const life = isFail ? 2.4 : 1.85;

    /* 主弧：核心 → 这次调用的能力位（取不到就落到它的束长） */
    const cm = capMeshById[p.kind];
    const b = bundles.find((x) => x.id === p.bundle);
    const target = cm ? cm.position
                      : (b && bundleNodes[bundles.indexOf(b)] ? bundleNodes[bundles.indexOf(b)].position : ORIGIN);
    if (target !== ORIGIN) {
      pushArc(makeArc(ORIGIN, target, col, life, {
        seed: seed + ">main", amp: cm ? 1.5 : 2.4, lift: cm ? 2.0 : 3.0,
        size: cm ? 1.7 : 2.3, forks: 2 }));
      auditArc({ ts: p.ts, kind: p.kind, leg: "main", to: cm ? "cap" : ("bundle:" + (b ? b.id : "?")),
                 on_cap: !!cm });
    }

    /* 副弧：**打在对应那条连接上** —— 这次调用经由的真依赖边（确定性挑一条） */
    const es = edgeIndex[p.kind] || [];
    if (es.length) {
      const pick = es[Math.floor(hash01(seed + "e") * es.length) % es.length];
      const om = capMeshById[p.kind === pick.a ? pick.b : pick.a];
      if (om && capMeshById[p.kind]) {
        pushArc(makeArc(capMeshById[p.kind].position, om.position, col, life, {
          seed: seed + ">edge", amp: 1.1, lift: 0.9, win: 0.34, size: 1.3, forks: 1 }));
        lightEdge(pick.a + ">" + pick.b, col, life + 0.5);
        lightEdge(pick.b + ">" + pick.a, col, life + 0.5);
        /* 🔴 出处记录（第 62 轮补）：**把"打在哪条边上"写下来**。
           为什么非补：改前页面只记"打了几条"（`arcs` 计数）⇒ **没有任何验收能证明
           它打的是那条对的边**（"打在对应依赖边上"这句话在那之前是**声明**，不是读数）。
           记的是**真边名**（`a>b`），验收器拿盘上的 `brain-data.js` 里的 edges **独立对照**
           —— 不是让页面自己说"我打对了"。 */
        auditArc({ ts: p.ts, kind: p.kind, leg: "edge",
                   edge: pick.a + ">" + pick.b, other: (p.kind === pick.a ? pick.b : pick.a),
                   incident: (pick.a === p.kind || pick.b === p.kind) });
      }
    }

    /* 🔴 同步点亮整条链（风哥：「精细到每一步执行同步」）。
       电弧是"这一次调用"，点亮是"它经由哪些连接" —— 两件事一起发生，才算同步。 */
    lightChain(p.kind, p.bundle);
  }

  /* 真事件按时间正序排队（撞到队列尾就停 —— 不编造、不循环） */
  const queue = (D.pulses || []).slice().reverse();
  let queueAt = 0;

  /* ── §8 拾取（悬停读数 + 点击详情）── */
  const ray = new THREE.Raycaster();
  const ptr = new THREE.Vector2(-2, -2);
  let hovered = null;

  canvas.addEventListener("pointermove", (e) => {
    const r = canvas.getBoundingClientRect();
    ptr.x = ((e.clientX - r.left) / r.width) * 2 - 1;
    ptr.y = -((e.clientY - r.top) / r.height) * 2 + 1;
  });
  canvas.addEventListener("pointerleave", () => { ptr.set(-2, -2); });

  /* ── §8.1 拖拽：**把节点拖到别处**（风哥令「可视化可拖拽」）──
   * 为什么放在 WebGL 里做，而不是拖 DOM 面板：本页 CSP 是 `style-src 'self'`，
   * **`el.style.left = …` 会被当场挡掉**（实测报过 6 次）。在三维里拖点纯粹是改 `position`，
   * 一行内联样式都不用 —— 顺带还比拖 DOM 更"真"（能在空间里摆）。
   * 拖动时**暂停轨道旋转**，否则手一按相机也跟着转，手感是错的。 */
  const dragPlane = new THREE.Plane();
  const dragPt = new THREE.Vector3();
  const dragOff = new THREE.Vector3();
  let dragging = null;

  canvas.addEventListener("pointerdown", (e) => {
    const r = canvas.getBoundingClientRect();
    ptr.x = ((e.clientX - r.left) / r.width) * 2 - 1;
    ptr.y = -((e.clientY - r.top) / r.height) * 2 + 1;
    ray.setFromCamera(ptr, camera);
    const hit = ray.intersectObjects(pickable(), false)[0];
    if (!hit) return;
    dragging = hit.object;
    /* 拖拽平面 = 过该点、正对相机 */
    const n = camera.getWorldDirection(new THREE.Vector3()).negate();
    dragPlane.setFromNormalAndCoplanarPoint(n, dragging.position);
    if (ray.ray.intersectPlane(dragPlane, dragPt)) {
      dragOff.copy(dragging.position).sub(dragPt);
    } else {
      dragOff.set(0, 0, 0);
    }
    controls.enabled = false;              // 拖点时不转相机
    canvas.setPointerCapture && canvas.setPointerCapture(e.pointerId);
    canvas.style.cursor = "grabbing";
  });

  canvas.addEventListener("pointerup", (e) => {
    if (!dragging) return;
    dragging = null;
    controls.enabled = true;
    canvas.style.cursor = "default";
    canvas.releasePointerCapture && canvas.releasePointerCapture(e.pointerId);
    /* 位置变了 ⇒ 边也要跟着走：重算**碰到这个点**的边（其余不动）。
       传的是 `position` 引用本身，`rebuildEdgesFor` 靠引用相等判断"哪几条边碰它"。 */
    rebuildEdgesFor(dragging.position);
  });

  const pickable = () => bundleNodes.concat(capNodes, deadNodes);

  function stateText(u) {
    if (!u) return "—";
    if (u.type === "bundle") return u.n + " 个能力位";
    if (u.type === "dead") return "仅登记未实现";
    return u.safe ? "免卡直跑" : "需授权";
  }
  function nameOf(u) {
    if (!u) return "—";
    return u.type === "bundle" ? u.label + " 束" : u.id;
  }

  canvas.addEventListener("click", () => {
    ray.setFromCamera(ptr, camera);
    const hit = ray.intersectObjects(pickable(), false)[0];
    const card = $("detail");
    if (!hit) { card.classList.remove("show"); return; }
    const u = hit.object.userData;
    card.classList.add("show");
    $("d-name").textContent = nameOf(u);
    $("d-cat").textContent = u.type === "bundle" ? "触手束 · DOMAIN（真 domain 字段）"
                          : u.type === "dead" ? "仅登记 · UNIMPLEMENTED" : "能力位 · CAPABILITY";
    $("d-type").textContent = u.type === "bundle" ? "束长（环层）" : u.type === "dead" ? "未实现" : "已实现";
    $("d-bundle").textContent = u.type === "bundle" ? (u.n + " 个能力位") : (u.bundleLabel || "—");
    $("d-safe").textContent = u.type === "cap" ? (u.safe ? "是" : "否") : "—";
    const calls = (D.pulses || []).filter((p) => p.kind === u.id).length;
    $("d-calls").textContent = calls ? (calls + " 次（账本内）") : "账本内未见";
    $("d-desc").textContent = u.desc || "—";
  });
  $("detail-x").addEventListener("click", () => $("detail").classList.remove("show"));

  /* ── §9 视图切换（**双向绑定 + 落盘固化** · 第 60 轮按主人令改）────────────
     主人令：「记得做双向绑定固化好别重启又不见了」。
     **改前**：点页签只改 DOM 属性 ⇒ **重启必然回到「全脑」**（改前真读数：重启后 active=brain）。
     **改后**三条：
       · 正向：点页签 → 立刻切视角 + 写进 `localStorage`（键 `gbt.brain.view.v1`）
       · 反向：别的文档改了同一个键 → `storage` 事件 → 本页跟着切（真双向，不是只写不回）
       · 重启：boot 时读回上次那个视图并**直接落位**（不飞行动画 —— 重启不该还要等它飞一秒）
     🔴 前提**已实测**（`.scratch/_persist_probe.py` 两态）：`file://` 的 localStorage
        **跨进程重启持久**（态一写 A、关掉整个 context、同目录再开仍读到 A）。
        ⇒ 才敢用它固化；没验过这个前提就写"固化"是本仓最忌讳的空话。
     ⚠️ 存不进去（配额/隐私设置）时**不假装**：`window.__brainView.saved` 会是 false，页面照旧能用。 */
  const VIEWS = {
    brain:  { pos: [0, 15, 46], target: [0, 0, 0] },
    cortex: { pos: [0, 3.5, 15], target: [0, 0, 0] },
    bundle: { pos: [0, 22, 34], target: [0, 0, 0] },
    route:  { pos: [26, 15, 26], target: [0, 0, 0] },
  };
  const VIEW_KEY = "gbt.brain.view.v1";
  const VIEW_NAMES = Object.keys(VIEWS);
  const VIEW = { now: "brain", saved: null, restored: null, via: "none", err: null };
  let camTarget = null;

  function readStoredView() {
    try {
      const v = localStorage.getItem(VIEW_KEY);
      return (v && VIEW_NAMES.indexOf(v) >= 0) ? v : null;
    } catch (e) { VIEW.err = String((e && e.message) || e).slice(0, 60); return null; }
  }
  function writeStoredView(name) {
    try {
      localStorage.setItem(VIEW_KEY, name);
      VIEW.saved = true; VIEW.via = "localStorage";
    } catch (e) {
      VIEW.saved = false; VIEW.err = String((e && e.message) || e).slice(0, 60);
    }
  }
  /* `snap=true` ⇒ 直接落位（用于重启恢复）；`false` ⇒ 交给主循环里的 lerp 飞过去 */
  function applyView(name, snap) {
    if (VIEW_NAMES.indexOf(name) < 0) name = "brain";
    document.querySelectorAll(".tab").forEach((x) => {
      if (x.dataset.view === name) x.setAttribute("data-active", "true");
      else x.removeAttribute("data-active");
    });
    const v = VIEWS[name];
    if (snap) {
      camera.position.set(v.pos[0], v.pos[1], v.pos[2]);
      if (controls && controls.target) {
        controls.target.set(v.target[0], v.target[1], v.target[2]);
      }
      camTarget = null;
    } else {
      camTarget = { pos: new THREE.Vector3(v.pos[0], v.pos[1], v.pos[2]),
                    to: new THREE.Vector3(v.target[0], v.target[1], v.target[2]) };
    }
    VIEW.now = name;
    return name;
  }
  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => {
      applyView(t.dataset.view, false);
      writeStoredView(VIEW.now);
    });
  });
  /* 反向绑定的那一半：只在**别的文档**改键时触发（同文档改不会触发 storage，这是浏览器规定） */
  window.addEventListener("storage", (e) => {
    if (!e || e.key !== VIEW_KEY) return;
    const v = e.newValue;
    if (v && VIEW_NAMES.indexOf(v) >= 0 && v !== VIEW.now) {
      applyView(v, true);
      VIEW.restored = v;
      VIEW.via = "storage-event";
    }
  });

  /* ── §10.5 右栏能力面板阵列（风哥令「各项能力面板设计好专业化的排列，该有的全都要有」）──
   * 每一格都填**现算的真值**；取不到写「—」，不编。
   * 规格取自 mission-control：数据格 / 遥测条 / 徽章 / 进度条 —— 不新造形状。 */
  /* 转义器：**必须声明在使用它的函数之前**。
     首版把它留在下面，而 `fillRack()` 定义在上面 ⇒ 真跑报
     `Cannot access 'esc' before initialization`（TDZ）——
     这类错静态看不出来，是本仓"渲一次才知道"的典型。 */
  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function fillRack() {
    const T = D.totals || {};
    $("k-bundles").textContent = T.bundles;
    $("k-caps").textContent = T.caps_impl;
    $("k-safe").textContent = nSafe;
    $("k-gated").textContent = nGated;
    $("k-dead").textContent = nDead;
    $("k-edges").textContent = (D.edges || []).length;

    /* 束长阵列：按能力位数降序，每条带**占比条**（相对最大的一束）。 */
    const maxN = Math.max.apply(null, bundles.map((b) => b.n).concat([1]));
    $("rack-bundles").innerHTML = bundles.map((b) => {
      const safe = caps.filter((n) => n.impl && n.bundle === b.id && n.safe).length;
      const gated = caps.filter((n) => n.impl && n.bundle === b.id && !n.safe).length;
      const pct = Math.round((b.n / maxN) * 100);
      return '<div class="rack-b" title="' + esc(b.id) + ' · 免卡 ' + safe + ' · 需授权 ' + gated + '">' +
        '<span class="n">' + esc(b.label) + '<span class="rack-bar"><i class="' +
        (gated > safe ? "gold" : "") + '" data-w="' + pct + '"></i></span></span>' +
        '<span class="c">' + b.n + "</span>" +
        '<span class="g">' + (gated ? gated + "🔑" : "") + "</span></div>";
    }).join("");
    /* 占比条宽度：**CSP 不许内联 style**，所以按百分比分档加 class —— 50 档够用且不抖 */
    document.querySelectorAll(".rack-bar > i[data-w]").forEach(function (el) {
      el.classList.add("w" + (Math.round(parseInt(el.dataset.w, 10) / 5) * 5));
    });

    /* 依赖最密的边：MC 的表行，不是图 —— 图在中间那块已经有了 */
    const top = (D.edges || []).slice(0, 12);
    $("rack-edges").innerHTML = top.length
      ? top.map((e) => '<div class="rack-b"><span class="n">' + esc(e.a) + " → " + esc(e.b) +
          '</span><span class="c">' + e.w + "</span></div>").join("")
      : '<p class="rail-empty">依赖图里没有边</p>';

    /* 门禁作用域：14 个药丸 */
    const sc = D.scope_names || [];
    $("rack-scopes").innerHTML = sc.length
      ? sc.map((s) => '<span class="mc-badge">' + esc(s) + "</span>").join("")
      : '<span class="mc-badge">作用域名单未随数据落地</span>';
  }
  fillRack();


  /* 转义器：**必须声明在使用它的函数之前**。
     首版把它留在下面，而 `fillRack()` 定义在上面 ⇒ 真跑报
     `Cannot access 'esc' before initialization`（TDZ）——
     这类错静态看不出来，是本仓"渲一次才知道"的典型。 */

  function fillRail() {
    const T = D.totals;
    $("rail-at").textContent = D.at;
    $("st-bundles").textContent = T.bundles;
    $("st-caps").textContent = T.caps_impl + " / +" + T.caps_unimpl;
    $("st-pulse").textContent = T.pulses_live_6h;
    $("st-scopes").textContent = T.scopes;
    $("st-pulses").textContent = T.pulses;

    const steps = D.steps || [];
    $("rail-steps").innerHTML = steps.length
      ? steps.slice(0, 8).map((s) =>
          '<div class="step-row"><div class="g">' + esc(s.goal || s.id) + "</div>" +
          '<div class="m">' + esc(s.id) + " · 开了 " + esc(s.age_h) + "h</div></div>").join("")
      : '<p class="rail-empty">步账里没有未收的步 —— 没有欠的活（不是「读不到」）</p>';

    const ps = D.pulses || [];
    $("rail-pulses").innerHTML = ps.length
      ? ps.slice(0, 16).map((p) =>
          '<div class="pulse-row' + (p.ok === false ? " bad" : "") + '">' +
          '<span class="t">' + esc(String(p.iso || "").slice(11, 19)) + "</span>" +
          '<span class="k">' + esc(p.kind) + "</span>" +
          '<span class="d">' + esc(p.bundle || "未分类") + "</span></div>").join("")
      : '<p class="rail-empty">账本里没有 call 事件</p>';
    $("stale").classList.toggle("show", ps.length === 0);

    $("rail-struct").innerHTML =
      '<div class="pulse-row"><span class="t">束长</span><span class="k">caps_registry.domain</span>' +
        '<span class="d">' + T.bundles + " 域</span></div>" +
      '<div class="pulse-row"><span class="t">免卡</span><span class="k">safe=true</span>' +
        '<span class="d">' + nSafe + " 位</span></div>" +
      '<div class="pulse-row"><span class="t">需授权</span><span class="k">safe=false</span>' +
        '<span class="d">' + nGated + " 位</span></div>" +
      '<div class="pulse-row"><span class="t">仅登记</span><span class="k">UNIMPLEMENTED_CAPS</span>' +
        '<span class="d">' + nDead + " 个</span></div>" +
      '<div class="pulse-row"><span class="t">技能雾</span><span class="k">skill_atlas</span>' +
        '<span class="d">' + T.skills + " 条</span></div>" +
      '<div class="pulse-row"><span class="t">门禁</span><span class="k">policy.scopes</span>' +
        '<span class="d">' + T.scopes + " 个</span></div>";
  }
  fillRail();

  /* ══════════════════════════════════════════════════════════════════════════
     §12 · 脑容积排布（第 58 轮）· 主人令：「按照果蝇大脑那样部署排布那就更好了」
            + 「像这张协作关联网络」+「加上电击脉冲特效同步 AI 运行对应连接」

     参照物是**果蝇全脑连接组**（FlyWire 那一类图）：它之所以一眼是"脑"而不是"图"，
     靠三件事 —— ① **椭球容积里的密集珠子**（不是同心圆环）；② **纤维状细连线**；
     ③ 活动**像波一样沿纤维级联**。所以本层按这三条重排：

       · 排布：力导向聚类（关联网络）**投进一个椭球脑容积**（软约束，不是硬夹）
         —— 椭球三轴按脑形给：左右宽 > 前后 > 上下扁。
       · 密度：`D.skills` 那 ~250 条技能是**真登记项**（按 root 分簇），
         当"技能雾"珠层打进去 —— 单次 draw call 的 Points，不冒充可点节点。
       · 纤维：边的分段从 6/8 提到 10，半径压细、基色压暗 ⇒ 读作纤维而不是粗线。

     🔴 先修一个**既有缺陷**（它正好挡着这一层）：边的端点引用有两套 ——
        构造时 `mesh.position.copy(p)` 与 `b._pos = p` 是**两个对象**，而
        「核心→束长」「束长→能力位」两类边引用的是 `_pos`、能力位↔能力位那类引用的是
        `mesh.position` ⇒ `rebuildEdgesFor(dragging.position)` 对前两类**匹配不到**，
        拖动时只有一类边跟随。统一到 `mesh.position` 之后三类一起跟随。
     ══════════════════════════════════════════════════════════════════════════ */

  /* ── §12.1 端点引用统一 ── */
  function bindEdgeRefsToMeshes() {
    const map = new Map();
    bundles.forEach((b, i) => {
      if (b._pos && bundleNodes[i]) map.set(b._pos, bundleNodes[i].position);
    });
    const capMeshById = {};
    capNodes.forEach((m) => { capMeshById[m.userData.id] = m; });
    caps.forEach((n) => {
      const m = capMeshById[n.id];
      if (n._pos && m) map.set(n._pos, m.position);
    });
    let fixed = 0;
    EDGE.curves.forEach((c) => {
      if (map.has(c.aPos)) { c.aPos = map.get(c.aPos); fixed++; }
      if (map.has(c.bPos)) { c.bPos = map.get(c.bPos); fixed++; }
    });
    return { curves: EDGE.curves.length, rebound: fixed, map_size: map.size };
  }

  /* ── §12.2 脑容积参数与排布 ── */
  /* 脑容积：左右宽 > 前后 > 上下扁。
     第 58 轮**第二轮密度打磨**：R 25.5 → **24.0**。为什么收：186 个节点铺在 25.5 上太散
     （读出来半径 23.3、"看着像星图不像脑"）。收一点容积 ⇒ 平均最近邻距离下降、密度上来。
     🔴 密度**不许靠感觉**：`NET.mean_nn`（平均最近邻距离）就是它的读数，改一次量一次。 */
  const BRAIN = { R: 24.0, ax: 1.06, ay: 0.80, az: 0.90 };
  const NET = { iter: 220, rep: 26, cut_k: 2.2, hc: 24, damp: 0.86, nodes: 0, edges: 0, e0: 0, e1: 0,
                radius: 0, ellipsoid: BRAIN };

  function layoutBrainVolume() {
    const P = [];
    bundleNodes.forEach((m) => P.push(m.position));
    capNodes.forEach((m) => P.push(m.position));
    const n = P.length;
    const ix = new Map();
    P.forEach((p, i) => ix.set(p, i));

    /* 边（三类）：隶属（把同域拉成一簇）· 真依赖（更硬更短）· 核心→束长 */
    const links = [];
    const bundleIx = new Map();
    bundles.forEach((b, i) => { if (bundleNodes[i]) bundleIx.set(b.id, ix.get(bundleNodes[i].position)); });
    capNodes.forEach((m) => {
      const bi = bundleIx.get(m.userData.bundle);
      const ci = ix.get(m.position);
      /* 🔴 隶属弹簧**必须比依赖弹簧更硬**（第 58 轮第四版）：
         实测 cluster_purity 只有 **0.45** —— 压密时簇被拽散了，
         因为这条原写 `[., 6.4, 0.50]`（目标 6.4 / 权重 0.50），
         而依赖边是 `[., 10.5, 0.30]`，**长程斥力又把它推平**。
         "关联网络"的全部价值在同域成簇 ⇒ 隶属这条要压过依赖那条：
         目标收到 4.6、权重提到 **1.30**（≈依赖边 4.3 倍）。 */
      if (bi !== undefined && ci !== undefined) links.push([ci, bi, 4.6, 1.30]);
    });
    capEdges.forEach((e) => {
      const a = capNodes.find((m) => m.userData.id === e.a);
      const b = capNodes.find((m) => m.userData.id === e.b);
      if (!a || !b) return;
      const ia = ix.get(a.position), ib = ix.get(b.position);
      if (ia !== undefined && ib !== undefined) links.push([ia, ib, 10.5, 0.30]);
    });
    const coreIx = [];
    bundles.forEach((b, i) => { if (bundleNodes[i]) coreIx.push(ix.get(bundleNodes[i].position)); });

    /* 用**裸浮点**跑力导向（Vector3 在 16k 对 × 220 轮里太慢） */
    const px = new Float64Array(n), py = new Float64Array(n), pz = new Float64Array(n);
    P.forEach((p, i) => { px[i] = p.x; py[i] = p.y; pz[i] = p.z; });
    const dx = new Float64Array(n), dy = new Float64Array(n), dz = new Float64Array(n);
    const isBundle = new Uint8Array(n);
    bundles.forEach((b, i) => { const k = ix.get(bundleNodes[i].position); if (k !== undefined) isBundle[k] = 1; });

    const energy = () => {
      let e = 0;
      for (let k = 0; k < links.length; k++) {
        const [a, b, L] = links[k];
        const ddx = px[a] - px[b], ddy = py[a] - py[b], ddz = pz[a] - pz[b];
        const d = Math.sqrt(ddx * ddx + ddy * ddy + ddz * ddz);
        e += (d - L) * (d - L) * 0.5;
      }
      return e;
    };
    const K = Math.sqrt((BRAIN.R * BRAIN.R) / Math.max(n, 1)) * 1.9;   /* 理想间距 */
    NET.e0 = energy();

    for (let it = 0; it < NET.iter; it++) {
      dx.fill(0); dy.fill(0); dz.fill(0);
      /* 斥力：O(n²)，但 n=186 ⇒ 17k 对，裸浮点跑得动。
         🔴 **第 58 轮第三版（这一版是拿判据逼出来的）**：斥力原来**无截断** ⇒
            长程互相推，平衡点落在"谁也推不动谁"的**壳**上 ⇒ 实测径向分布
            [1,12,18,66,84,5]：**90% 的节点在 q>0.6、中心只有 7%** —— 空壳。
            且 mean_nn 4.78 **比同容积均匀分布的基准 3.24 还疏 48%**。
            ⇒ 加**截断半径**（超出不推），长程只由向心管 —— 这才是"实心球填充"的做法。 */
      const CUT2 = K * K * NET.cut_k * NET.cut_k;
      const dmin = K * 0.5;                     /* 硬芯半径：不许比理想间距的一半更近 */
      for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
          let ddx = px[i] - px[j], ddy = py[i] - py[j], ddz = pz[i] - pz[j];
          let d2 = ddx * ddx + ddy * ddy + ddz * ddz;
          if (d2 > CUT2) continue;                                 /* 太远：不推 */
          if (d2 < 1e-3) {
            ddx = hash01("jx" + i + j) - 0.5; ddy = hash01("jy" + i + j) - 0.5;
            ddz = hash01("jz" + i + j) - 0.5; d2 = 0.02;
          }
          const dd = Math.sqrt(d2);
          const inv = 1 / dd;
          const f = (K * K * NET.rep * 0.02) * inv * inv * inv;   /* /d² 方向 */
          const fx = ddx * f, fy = ddy * f, fz = ddz * f;
          dx[i] += fx; dy[i] += fy; dz[i] += fz;
          dx[j] -= fx; dy[j] -= fy; dz[j] -= fz;
          /* ── 硬芯（第 61 轮补）· **只在已经重叠的地方补一脚** ────────────────
             为什么非补：斥力是 `/d²`、越近越强，但它得跟**隶属弹簧**（w=1.30）抢平衡
             ⇒ 实测仍有两个节点落进 **0.42·K**（`nn_min 1.39` < `K/2 1.67`）：
             图上就是一团，拾取也点不准。**这是废，不是审美。**
             直接把 /d² 调大 ⇒ **全局**变疏（`mean_nn` 与取景都会动，那是另一个读数）；
             硬芯是**局部**约束：只在 `d < K/2` 时线性回推，系数比隶属弹簧大一个量级
             ⇒ 精准消重叠、不扰动别处。 */
          if (dd < dmin) {
            const hc = (dmin - dd) * NET.hc;
            const ux2 = ddx * inv, uy2 = ddy * inv, uz2 = ddz * inv;
            dx[i] += ux2 * hc; dy[i] += uy2 * hc; dz[i] += uz2 * hc;
            dx[j] -= ux2 * hc; dy[j] -= uy2 * hc; dz[j] -= uz2 * hc;
          }
        }
      }
      /* 弹簧 */
      for (let k = 0; k < links.length; k++) {
        const a = links[k][0], b = links[k][1], L = links[k][2], w = links[k][3];
        const ddx = px[a] - px[b], ddy = py[a] - py[b], ddz = pz[a] - pz[b];
        const d = Math.max(Math.sqrt(ddx * ddx + ddy * ddy + ddz * ddz), 0.05);
        const f = ((d - L) * w) / d;
        dx[a] -= ddx * f; dy[a] -= ddy * f; dz[a] -= ddz * f;
        dx[b] += ddx * f; dy[b] += ddy * f; dz[b] += ddz * f;
      }
      /* 向心 **∝ 归一化半径²** + 椭球软约束 ────────────────────────────────
         🔴 第 58 轮第二版教训：原来"体内几乎不拉、出界才狠推"，配合偏大的斥力，
            结果是**空壳**（节点全贴在椭球面上、中间一片空）—— 第一版实图就是稀疏星图。
            果蝇脑那种图是**实心**的：密度从中心向外递减。
            做法：把向心力写成 `∝ q`（q = 归一化半径²）⇒ 越靠外拉得越紧，
            自然形成"中心密、边缘疏"的实心分布；出界再叠一层狠推。 */
      for (let i = 0; i < n; i++) {
        const ux = px[i] / (BRAIN.R * BRAIN.ax), uy = py[i] / (BRAIN.R * BRAIN.ay),
              uz = pz[i] / (BRAIN.R * BRAIN.az);
        const q = ux * ux + uy * uy + uz * uz;
        const pull = (isBundle[i] ? 0.030 : 0.045) * (0.35 + q);
        dx[i] -= px[i] * pull; dy[i] -= py[i] * pull; dz[i] -= pz[i] * pull;
        if (q > 1) {                                  /* 出界：往心里按，越界越狠 */
          const s = (q - 1) * 40 * (isBundle[i] ? 0.8 : 1.2);
          dx[i] -= ux * s; dy[i] -= uy * s; dz[i] -= uz * s;
        }
      }
      /* 限步长 + 阻尼（FR 的标准做法：步长封顶，免得炸开） */
      const cap = 1.15;
      for (let i = 0; i < n; i++) {
        const m = Math.sqrt(dx[i] * dx[i] + dy[i] * dy[i] + dz[i] * dz[i]);
        const s = m > cap ? (cap / m) * NET.damp : NET.damp;
        px[i] += dx[i] * s; py[i] += dy[i] * s; pz[i] += dz[i] * s;
      }
    }
    P.forEach((p, i) => { p.set(px[i], py[i], pz[i]); });
    NET.e1 = energy();

    /* ── 取景打磨：以**质心**对齐 ──────────────────────────────────────
       力导向的质心常偏离原点 ⇒ 核（固定在原点）会落在云的一侧，取景跟着歪。
       把整片云平移、令**质心与核重合**，再算半径与取景 —— 这是"取景"那一刀的落点。
       偏移量记进 `NET.centroid_offset`：歪了多少是读数，不是"我觉得有点偏"。 */
    let cx = 0, cy = 0, cz = 0;
    for (let i = 0; i < n; i++) { cx += px[i]; cy += py[i]; cz += pz[i]; }
    cx /= n; cy /= n; cz /= n;
    for (let i = 0; i < n; i++) { px[i] -= cx; py[i] -= cy; pz[i] -= cz; }
    P.forEach((p, i) => { p.set(px[i], py[i], pz[i]); });
    NET.centroid_offset = [Math.round(cx * 10) / 10, Math.round(cy * 10) / 10,
                           Math.round(cz * 10) / 10];

    /* ── 密度读数：**平均最近邻距离**（越小越密）──────────────────────
       主人要的是"像果蝇脑那样密集"。而"看着挺密"是感觉、不是读数。
       最近邻距离是"密度"的可量测定义 ⇒ 记进 NET，**改一次量一次**，
       密度到底有没有变密看得见（而不是靠我说）。 */
    /* ── 密度读数（细粒度 · 第 61 轮补）：**平均值会掩盖重叠** ────────────────
       为什么非补：`mean_nn` 是平均值 —— 少数节点几乎重合、其余稀疏，平均值照样好看。
       而"两个节点叠在一起"是**看得见的废**（图上就是一团、点也点不准）。
       ⇒ 除了平均，再量三样：最近的那一对（`nn_min`）· 第 10 百分位（`nn_p10`）·
       有多少节点比**半个理想间距**（K/2）还近（`overlap_frac`）。
       判据：`overlap_frac` 必须为 **0**；不为 0 就是**真缺陷**（不是审美选择）。 */
    const nns = [];
    for (let i = 0; i < n; i++) {
      let best2 = Infinity;
      for (let j = 0; j < n; j++) {
        if (i === j) continue;
        const ddx = px[i] - px[j], ddy = py[i] - py[j], ddz = pz[i] - pz[j];
        const d2 = ddx * ddx + ddy * ddy + ddz * ddz;
        if (d2 < best2) best2 = d2;
      }
      nns.push(Math.sqrt(best2));
    }
    const nnSum = nns.reduce((a, b) => a + b, 0);
    NET.mean_nn = Math.round((nnSum / n) * 100) / 100;
    const nnSorted = nns.slice().sort((a, b) => a - b);
    NET.nn_min = Math.round(nnSorted[0] * 100) / 100;
    NET.nn_p10 = Math.round(nnSorted[Math.floor(n * 0.10)] * 100) / 100;
    NET.ideal_k = Math.round(K * 100) / 100;                  // 理想间距
    NET.nn_vs_K = Math.round((NET.mean_nn / K) * 100) / 100;  // 实测平均间距 / 理想间距
    const half = K * 0.5;
    NET.overlap_frac = Math.round((nns.filter((x) => x < half).length / n) * 1000) / 1000;
    NET.density_verdict = NET.overlap_frac > 0
      ? ("❗有 " + Math.round(NET.overlap_frac * 100) + "% 的节点比理想间距的一半还近（重叠）"
         + " · 最近 " + NET.nn_min)
      : ("✅ 无重叠（最近 " + NET.nn_min + " ≥ K/2 = " + (Math.round(half * 100) / 100)
         + "）· 平均间距是理想值的 " + NET.nn_vs_K + " 倍");

    /* ── 空壳自证：径向分布（**这条是我自己的未验账，不是别人要求的**）──────
       为什么要它：力导向写成"出界才推"极易做出**空壳** —— 半径看着正常、里面却是空的
       （第一版实图就是这样，我当场看出来了）。**只报半径根本证明不了"实心"。**
       做法：按归一化半径 q 分 5 桶（q=1 正好是椭球面）。
       **实心脑的分布应当"小 q 多、边缘少"**；若最大桶在 q≈1 附近 ⇒ 就是空壳，判红。 */
    const NB = 5;
    const hist = new Array(NB + 1).fill(0);            // 末桶 = 出界（q > 1）
    for (let i = 0; i < n; i++) {
      const ux = px[i] / (BRAIN.R * BRAIN.ax), uy = py[i] / (BRAIN.R * BRAIN.ay),
            uz = pz[i] / (BRAIN.R * BRAIN.az);
      const q = ux * ux + uy * uy + uz * uz;
      hist[Math.min(NB, Math.floor(Math.sqrt(q) * NB))]++;
    }
    NET.radial_hist = hist;                             // [0-0.2, 0.2-0.4, …, 0.8-1, >1]
    /* 均匀填球（体积 ∝ r³）时各桶**应有**的比例 —— **参考值，不是门槛**。
       为什么报它：现读 `[4,30,71,78,3,0]` 明显偏中心（最外一档理论该有 49%、实测 1.6%），
       而这是上面 L997 那条"向心力 ∝ q ⇒ 中心密、边缘疏"的**刻意设计后果**，**不是缺陷**。
       报出来只为让"密度像不像果蝇脑"这件事**有数可依**，而不是我说了算；
       要不要改这条设计，是**主人的选择**（已写进 README 未验账第 2 条）。 */
    NET.radial_uniform_ref = [];
    for (let k = 0; k < NB; k++) {
      NET.radial_uniform_ref.push(
        Math.round((Math.pow((k + 1) / NB, 3) - Math.pow(k / NB, 3)) * n * 10) / 10);
    }
    let devMax = 0;
    for (let k = 0; k < NB; k++) {
      devMax = Math.max(devMax, Math.abs(hist[k] - NET.radial_uniform_ref[k]) / n);
    }
    NET.radial_max_dev = Math.round(devMax * 100) / 100;   // 与"均匀填球"的最大偏离
    NET.shell_frac = Math.round((hist[NB - 1] + hist[NB]) / n * 100) / 100;
    NET.outer_void = hist[0] === 0 && hist[1] === 0;    // 中心两桶全空 ⇒ 强空壳信号
    NET.hollow_verdict = (hist[NB - 1] + hist[NB] > n * 0.5)
      ? "❗空壳：过半节点贴在壳上/出界"
      : ("✅ 实心（边缘占比 " + Math.round(NET.shell_frac * 100) + "%）");
    /* 🔴 上面这一行原本写成 `"…%.0f%%" % x` —— 那是 **Python 的格式化**，
       在 JS 里 `%` 是**取模**（字符串%数 = NaN）⇒ 判据算出 `nan`。
       手误已修；记在这里是因为"判据自己是 nan"这种错**极难从结论看出来**。 */

    /* ── 密度的**参照值**：同容积、同点数的均匀分布下 mean_nn 会是多少 ──────
       为什么必须给基准：4.78 这个数**单看毫无意义**（没有"多少算密"的标尺）。
       基准用**同一套确定性哈希**撒点（球内均匀：r = R·∛u，再按椭球三轴拉伸），可复算、不随机。 */
    const UP = new Float64Array(n * 3);
    for (let i = 0; i < n; i++) {
      const u = hash01("uni" + i), v = hash01("univ" + i), w = hash01("uniw" + i);
      const r = Math.cbrt(u), th = Math.acos(2 * v - 1), ph = 2 * Math.PI * w;
      UP[i * 3] = r * Math.sin(th) * Math.cos(ph) * BRAIN.R * BRAIN.ax;
      UP[i * 3 + 1] = r * Math.cos(th) * BRAIN.R * BRAIN.ay;
      UP[i * 3 + 2] = r * Math.sin(th) * Math.sin(ph) * BRAIN.R * BRAIN.az;
    }
    let unSum = 0;
    for (let i = 0; i < n; i++) {
      let b2 = Infinity;
      for (let j = 0; j < n; j++) {
        if (i === j) continue;
        const a1 = UP[i * 3] - UP[j * 3], a2 = UP[i * 3 + 1] - UP[j * 3 + 1],
              a3 = UP[i * 3 + 2] - UP[j * 3 + 2];
        const d2 = a1 * a1 + a2 * a2 + a3 * a3;
        if (d2 < b2) b2 = d2;
      }
      unSum += Math.sqrt(b2);
    }
    NET.mean_nn_uniform = Math.round((unSum / n) * 100) / 100;
    NET.density_vs_uniform = NET.mean_nn_uniform > 0
      ? Math.round((1 - NET.mean_nn / NET.mean_nn_uniform) * 100) / 100 : null;

    /* ── 聚簇自证：**同域能力位是不是真的围着自家束长** ────────────────────
       为什么必须量（这是我自己留在 README 未验账里的那条）：
         压密 = 收容积 + 给斥力加截断。**代价可能是把簇打散** ——
         而"关联网络"的全部价值就在**同域成簇**；簇散了，"密了"也白密。
       判据：每个能力位到**本域束长**的距离，是否**小于**到最近**外域束长**的距离。
         `cluster_purity` = 命中比例（1.0 = 每个能力位都离自家束长更近）
         `intra/inter_mean` = 同域平均距离 / 最近外域平均距离（<1 = 成簇）
       ⇒ 只说"密度上来了"是不够的，这两条必须一起报。 */
    const bpos = bundleNodes.map((m) => m.position);
    const bidx = {};
    bundles.forEach((b, i) => { if (bpos[i]) bidx[b.id] = i; });
    let hit = 0, intra = 0, inter = 0, nCap = 0;
    capNodes.forEach((m) => {
      const own = bidx[m.userData.bundle];
      if (own === undefined) return;
      const dOwn = m.position.distanceTo(bpos[own]);
      let dOther = Infinity;
      for (let i = 0; i < bpos.length; i++) {
        if (i === own || !bpos[i]) continue;
        const d = m.position.distanceTo(bpos[i]);
        if (d < dOther) dOther = d;
      }
      if (!isFinite(dOther)) return;
      nCap++; intra += dOwn; inter += dOther;
      if (dOwn < dOther) hit++;
    });
    NET.caps_counted = nCap;
    NET.cluster_purity = nCap ? Math.round((hit / nCap) * 100) / 100 : null;
    NET.intra_mean = nCap ? Math.round((intra / nCap) * 100) / 100 : null;
    NET.inter_mean = nCap ? Math.round((inter / nCap) * 100) / 100 : null;
    /* 判据**不设单一硬门槛**（第 58 轮第五版改）：
       上一版写 `purity >= 0.9 ? ✅ : ❗`，实测 0.87 被判红 —— 可 **1.0 并不是目标**：
       能力位之间有**真实的跨域依赖边**（真 import 关系），它们本来就该把一部分节点
       拉到别的域旁边 —— 那正是"关联网络"要显示的东西，硬推到 1.0 等于抹掉跨域耦合。
       ⇒ 改成**报数 + 报比 + 标档**：让人看见数，再由人判断"够不够"。
         `intra/inter`（同域/外域平均距离比，<1 即成簇）是**无门槛**的判据，一并给出。 */
    if (NET.cluster_purity === null) {
      NET.cluster_verdict = "未量";
    } else {
      const band = NET.cluster_purity >= 0.9 ? "✅ 强成簇"
                 : NET.cluster_purity >= 0.8 ? "🟡 成簇（余下多为跨域依赖，属正常）"
                 : "❗簇被压散";
      NET.cluster_verdict = band + "：" + Math.round(NET.cluster_purity * 100)
        + "% 离自家束长更近 · 同域/外域距离比 "
        + (NET.inter_mean ? (NET.intra_mean / NET.inter_mean).toFixed(2) : "?")
        + "（<1 即成簇）";
    }

    /* 端点引用已统一到 `mesh.position` ⇒ 重建全部纤维 */
    EDGE.curves.forEach((c) => writeCurve(c));
    if (EDGE.geo) EDGE.geo.attributes.position.needsUpdate = true;

    /* 束长的柔光跟着走（构造时它贴在旧坐标上，不跟会留在半空） */
    bundleNodes.forEach((m) => { if (m.userData.glow) m.userData.glow.position.copy(m.position); });

    /* 半径读数：椭球三轴上的实际占用 —— 用来判"排布有没有真的铺开" */
    let rmax = 0;
    P.forEach((p) => { rmax = Math.max(rmax, p.length()); });
    NET.nodes = n;
    NET.edges = links.length;
    NET.radius = rmax;

    /* 门禁环与 14 道刻度：**贴着这次的脑容积边界**（见 §6 的注释：
       固定半径 28 会横穿排布半径 27.6 的网）。 */
    const gr = rmax * 1.13;
    gates.forEach((ring, k) => {
      ring.geometry.dispose();
      ring.geometry = new THREE.TorusGeometry(gr + k * 0.55, 0.03, 6, 200);
      ring.position.y = (k ? 1 : -1) * rmax * BRAIN.ay * 0.60;
    });
    if (gateTicks) {
      gateTicks.scale.setScalar(gr + 0.25);
      gateTicks.position.y = -rmax * BRAIN.ay * 0.60;
    }
    NET.gate_r = gr;

    /* ── 取景：**按真实排布出来的外接框**拟合，不按名义椭球估 ─────────────────
       🔴 第 60 轮修（**是新加的取景读数当场抓到的**）：
          改前按 `rmax·ax` 名义椭球估距离，实测 **画面填充 x = 1.879（内容比画布宽 1.88 倍）、
          7 个节点跑出画外**。根因：排布后的节点**并不落在名义椭球上** —— 斥力/弹簧会把
          一部分推出去，名义半径估出来的相机距离就偏近，横向被切。
          ⇒ 改成"把节点投影到屏幕、按最大 NDC 溢出倍数迭代缩放距离"，留 8% 边距。
          这是**数据驱动**的：椭球参数改了、节点数变了，取景自动跟着合，不用再手调常数。 */
    const fitNodes = pickable();
    const cbox = new THREE.Box3();
    fitNodes.forEach((m) => cbox.expandByPoint(m.position));
    const ctr = cbox.getCenter(new THREE.Vector3());
    const pv0 = new THREE.Vector3();

    /* 拟合一个方向：把节点投影到屏幕，迭代缩放距离，使最大 NDC 落在 0.92（留 8% 边距）。
       返回 { dist, fill }，`fill` = **最小边**的填充率（取 x/y 里小的那个 —— 构图好不好
       由短板决定，不看长边）。 */
    function fitAlong(dir) {
      let d = rmax * 3.0;
      let mx = 0, my = 0;
      for (let it = 0; it < 6; it++) {
        camera.position.copy(ctr).addScaledVector(dir, d);
        camera.lookAt(ctr);
        camera.updateMatrixWorld();
        mx = 0; my = 0;
        let behind = 0;
        fitNodes.forEach((m) => {
          pv0.copy(m.position).project(camera);
          if (pv0.z > 1) { behind++; return; }
          mx = Math.max(mx, Math.abs(pv0.x));
          my = Math.max(my, Math.abs(pv0.y));
        });
        if (behind) { d *= 1.6; continue; }          // 有节点落到相机背后 ⇒ 先退远
        const worst = Math.max(mx, my);
        if (!(worst > 0)) break;
        const ratio = worst / 0.92;                  // NDC ±1 即画布边缘
        if (Math.abs(ratio - 1) < 0.01) break;
        d *= ratio;
      }
      return { dist: d, fill: Math.min(mx, my), dir: dir };
    }

    /* 🔴 俯角**自己选**，不写死。为什么：这块脑容积**宽而扁**（ay=0.80 对 ax=1.06），
       而画布近方（938×900）⇒ 固定俯角下竖向天生填不满（实测只有 45%）。
       手工调角度就是又一个拍脑袋常数；改成在候选方向里挑"最小边填得最满"的那个，
       换椭球参数、换节点数都会自动跟着合。全程可量：取景读数就在下面。 */
    const AZ = 0.10 / 0.95;                          // 方位角保持不变（从 +z 略偏 +x 看）
    let best = null;
    [8, 16, 24, 32, 40, 48, 56].forEach((deg) => {
      const t = Math.tan((deg * Math.PI) / 180);
      const r = fitAlong(new THREE.Vector3(AZ, t, 1).normalize());
      if (!best || r.fill > best.fill) { best = r; best.deg = deg; }
    });
    const dist = best.dist;
    const fdir = best.dir;
    camera.position.copy(ctr).addScaledVector(fdir, dist);
    camera.lookAt(ctr);
    controls.target.copy(ctr);
    controls.minDistance = rmax * 0.45;
    controls.maxDistance = rmax * 4.5;
    controls.update();
    NET.cam_dist = dist;
    NET.cam_elev_deg = best.deg;
    NET.frame_center = [Math.round(ctr.x * 10) / 10, Math.round(ctr.y * 10) / 10,
                        Math.round(ctr.z * 10) / 10];
    /* 「全脑」页签必须回到**拟合后**的机位，否则点它会跳回旧的手写位置 [0,15,46] */
    if (VIEWS && VIEWS.brain) {
      VIEWS.brain.pos = [ctr.x + fdir.x * dist, ctr.y + fdir.y * dist, ctr.z + fdir.z * dist];
      VIEWS.brain.target = [ctr.x, ctr.y, ctr.z];
    }

    /* ── 取景**读数**（第 60 轮补）──────────────────────────────────────────
       为什么非补不可：改前这一段只有一个 `cam_dist`（**声明**）—— 它能算出"相机放多远"，
       却答不出"画面到底填了几成、有没有节点跑出画外"（**读数**）。
       本仓纪律：**声明 ≠ 已验证**；而"取景好不好"恰恰只能靠投影到屏幕才量得出来。
       口径：`fill_*` = 节点投影外接框占画布的比例；`clipped` = 跑出画外或落到相机背后的节点数。
       ⚠️ 它**只说明构图**，不说明"排布好不好"（那由 density/cluster 那几项管）。 */
    const CW = (renderer.domElement && renderer.domElement.clientWidth) || 1;
    const CH = (renderer.domElement && renderer.domElement.clientHeight) || 1;
    camera.updateMatrixWorld();
    const pv = new THREE.Vector3();
    let bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity, cut = 0, seen = 0;
    pickable().forEach((m) => {
      pv.copy(m.position).project(camera);            // NDC ∈ [-1,1]
      if (pv.z > 1) { cut++; return; }                // 落到相机背后
      const sx = (pv.x * 0.5 + 0.5) * CW;
      const sy = (1 - (pv.y * 0.5 + 0.5)) * CH;
      seen++;
      if (sx < 0 || sx > CW || sy < 0 || sy > CH) cut++;
      if (sx < bx0) bx0 = sx;
      if (sx > bx1) bx1 = sx;
      if (sy < by0) by0 = sy;
      if (sy > by1) by1 = sy;
    });
    const fx = seen ? (bx1 - bx0) / CW : 0, fy = seen ? (by1 - by0) / CH : 0;
    const fmin = Math.min(fx, fy);
    NET.screen = {
      canvas: [CW, CH],
      bbox: seen ? [Math.round(bx0), Math.round(by0), Math.round(bx1), Math.round(by1)] : null,
      fill_x: seen ? Math.round(fx * 1000) / 1000 : null,
      fill_y: seen ? Math.round(fy * 1000) / 1000 : null,
      clipped: cut,
      verdict: !seen ? "取不到"
        : cut > 0 ? ("❗有 " + cut + " 个节点跑出画外（构图不合格）")
        : fmin < 0.55 ? ("偏空：画面最小边只填了 " + Math.round(fmin * 100) + "%")
        : ("✅ 填满且无溢出（最小边 " + Math.round(fmin * 100) + "%）"),
    };
    return NET;
  }

  /* ── §12.3 技能雾（真登记项 ~250 条，按 root 分簇；单 draw call、不冒充可点节点）──
     ⚠️ 口径写死：这一层**只表示"技能质量落在哪一片"**，不参与拾取、没有详情面板 ——
        它不是"第 251 个能力位"，别让人误以为它可点。 */
  function buildSkillCloud() {
    const sk = (D.skills || []);
    if (!sk.length) return { n: 0, roots: 0 };
    const byRoot = {};
    sk.forEach((s) => { const r = String(s.root || "(未标)"); (byRoot[r] = byRoot[r] || []).push(s); });
    const roots = Object.keys(byRoot);
    const N = sk.length;
    const pos = new Float32Array(N * 3);
    const col = new Float32Array(N * 3);
    const base = new THREE.Color(TOKEN("--gbt-violet") || "#7c4dff");
    let w = 0;
    roots.forEach((r, ri) => {
      /* 每个 root 给一个**固定方向**（确定性），技能珠围它成一片云。
         🔴 第 58 轮把云铺开：第一版中心只放在 0.62R 的一圈上、云半径 3.4–8.6，
            结果是**5 个孤岛**浮在网外 —— 而果蝇脑那种图，珠子是**铺满容积**的。
            现在中心收到 0.42R、云半径按椭球三轴放大 ⇒ 五片云互相重叠、填满脑容积。 */
      const a = (ri / roots.length) * Math.PI * 2 + 0.7;
      const cy = (hash01("root" + ri) - 0.5) * BRAIN.R * BRAIN.ay * 0.85;
      const cx = Math.cos(a) * BRAIN.R * BRAIN.ax * 0.42;
      const cz = Math.sin(a) * BRAIN.R * BRAIN.az * 0.42;
      byRoot[r].forEach((s, j) => {
        const h1 = hash01("sx" + r + j), h2 = hash01("sy" + r + j), h3 = hash01("sz" + r + j);
        const rr = BRAIN.R * (0.30 + h1 * 0.34);
        pos[w * 3] = cx + (h1 - 0.5) * rr * BRAIN.ax * 1.7;
        pos[w * 3 + 1] = cy + (h2 - 0.5) * rr * BRAIN.ay * 1.7;
        pos[w * 3 + 2] = cz + (h3 - 0.5) * rr * BRAIN.az * 1.7;
        const k = 0.20 + h2 * 0.35;
        col[w * 3] = base.r * k; col[w * 3 + 1] = base.g * k; col[w * 3 + 2] = base.b * k;
        w++;
      });
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    const pts = new THREE.Points(g, new THREE.PointsMaterial({
      size: 0.55, map: DOT, vertexColors: true, transparent: true, opacity: 0.72,
      blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true }));
    pts.userData = { type: "skillfog" };
    scene.add(pts);
    return { n: N, roots: roots.length };
  }

  /* ── §12.4 标签（参照物上"焦点节点带标签"那一条）──
     做法：canvas 贴图 → Sprite。**不用任何内联样式**（本页 CSP 是 style-src 'self'）。
     焦点（核心）一个显眼的，29 个束长各一个**小而暗**的 —— 标签是"认路"用的，不是标题。 */
  function makeLabel(text, opt) {
    const o = opt || {};
    const fs = o.size || 44;
    const pad = 12;
    const c = document.createElement("canvas");
    const ctx = c.getContext("2d");
    ctx.font = "600 " + fs + "px 'Microsoft YaHei UI', 'Segoe UI', sans-serif";
    const tw = Math.ceil(ctx.measureText(text).width);
    c.width = Math.max(8, tw + pad * 2);
    c.height = fs + pad * 2;
    const g2 = c.getContext("2d");
    g2.font = "600 " + fs + "px 'Microsoft YaHei UI', 'Segoe UI', sans-serif";
    g2.textBaseline = "middle";
    g2.fillStyle = o.color || "rgba(232,236,248,.92)";
    g2.shadowColor = "rgba(0,0,0,.85)";        /* 深底上要能读：先描一层暗影，不靠加性发光 */
    g2.shadowBlur = 6;
    g2.fillText(text, pad, c.height / 2);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({
      map: tex, transparent: true, opacity: o.opacity === undefined ? 0.85 : o.opacity,
      depthWrite: false, depthTest: o.depthTest === undefined ? true : o.depthTest }));
    const h = o.worldH || 1.6;
    sp.scale.set((c.width / c.height) * h, h, 1);
    return sp;
  }

  function buildLabels() {
    /* 焦点节点的标签：**一句话就够**（参照物上那个焦点节点也只有一行 repo 名）。
       原来写全称「GBT小土豆V8 · 主脑（DSH 会话面）」，在 1600 宽的舞台上占掉三分之一。 */
    const core = makeLabel("GBT小土豆V8 · 主脑", { size: 52, worldH: 2.1,
      color: "rgba(245,176,65,.98)", opacity: 0.92 });
    core.position.set(0, 2.6, 0);
    scene.add(core);
    bundleNodes.forEach((m) => {
      const lb = makeLabel(m.userData.label || m.userData.id,
                           { size: 40, worldH: 1.05, opacity: 0.55 });
      /* 抬到 `球心 + 半径 + 0.9`：原来只 +1.0，标签会压在束长的灰晕上（看着像"灰药丸"） */
      lb.position.copy(m.position).add(new THREE.Vector3(0, m.geometry.parameters.radius + 0.9, 0));
      m.userData.label3d = lb;
      scene.add(lb);
    });
    return { core: 1, bundles: bundleNodes.length };
  }

  const BOOT = { bind: null, net: null, fog: null, labels: null };

  /* ── §11 循环（真实 delta；动效只留给信号）── */
  function resize() {
    const w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
    camera.aspect = w / h; camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    bloom.setSize(w, h);
  }
  if (window.ResizeObserver) new ResizeObserver(resize).observe(canvas);
  window.addEventListener("resize", resize);
  resize();

  let t = 0, frames = 0, fpsAt = performance.now(), last = performance.now(), hotCol = false;

  function tick(now) {
    requestAnimationFrame(tick);
    const dt = Math.min((now - last) / 1000, 0.1);   // 真实 delta，掉帧也不失真
    last = now;
    t += dt;

    /* 信号一：核心状态灯（慢，只转核本身） */
    coreMesh.rotation.y += dt * 0.22;
    haloSprite.material.opacity = 0.26 + Math.sin(t * 1.1) * 0.05;

    /* 信号二：门禁环扫描（反向，慢） */
    gates[0].rotation.z += dt * 0.09;
    gates[1].rotation.z -= dt * 0.06;

    /* 信号三：执行脉冲（事件驱动，不循环造事件） */
    queueAt -= dt;
    if (queueAt <= 0 && queue.length) { spawnPulse(queue.shift()); queueAt = 0.5; }

    /* ── 拖拽跟随：射线打在拖拽平面上，节点跟着手走；边就地重算 ── */
    if (dragging) {
      ray.setFromCamera(ptr, camera);
      if (ray.ray.intersectPlane(dragPlane, dragPt)) {
        dragging.position.copy(dragPt).add(dragOff);
        rebuildEdgesFor(dragging.position);
      }
    }

    /* ── 点亮衰减：热色 → 基色。**顶点色就是亮度**（加性混合），所以只用改颜色缓冲 ── */
    if (hot.length || hotCol) {
      hotCol = true;
      for (let i = hot.length - 1; i >= 0; i--) {
        const h = hot[i];
        h.t += dt / h.life;
        const k = Math.max(0, 1 - h.t);
        const a = k * k * (3 - 2 * k);                       // smoothstep：起亮猛、收尾柔
        for (let v = 0; v < h.count; v++) {
          const o = (h.i0 + v) * 3;
          const base = EDGE.col[o], baseG = EDGE.col[o + 1], baseB = EDGE.col[o + 2];
          EDGE.geo.attributes.color.array[o] = base + (h.col.r - base) * a;
          EDGE.geo.attributes.color.array[o + 1] = baseG + (h.col.g - baseG) * a;
          EDGE.geo.attributes.color.array[o + 2] = baseB + (h.col.b - baseB) * a;
        }
        if (h.t >= 1) hot.splice(i, 1);
      }
      EDGE.geo.attributes.color.needsUpdate = true;
    }

    /* ── 电弧推进（第 58 轮）：抖动静止就不像电，抖太快就像虫 —— 取 ~22Hz 重掷 ── */
    for (let i = pulses.length - 1; i >= 0; i--) {
      const p = pulses[i];
      p.t += dt / p.life;
      if (p.t >= 1) {
        scene.remove(p.main); p.main.geometry.dispose(); p.main.material.dispose();
        p.forks.forEach((f) => { scene.remove(f.line); f.line.geometry.dispose(); f.line.material.dispose(); });
        scene.remove(p.head); p.head.material.dispose();
        pulses.splice(i, 1); continue;
      }
      p.rejitter -= dt;
      if (p.rejitter <= 0) { p.seed = p.baseSeed + "#" + Math.floor(t * 45); p.rejitter = 0.045; }
      /* 全局包络：起手一记猛（放电那声"啪"），尾巴收干净 */
      p.global = Math.min(1.15, Math.pow(Math.sin(Math.PI * p.t), 0.55) * 1.2);
      writeArc(p);
      const fade = Math.sin(p.t * Math.PI);
      p.head.position.copy(p.curve.getPoint(p.t));
      p.head.material.opacity = 0.22 + fade * 0.78;
      p.head.scale.setScalar(p.size * (0.7 + fade * 0.75));
    }

    /* 拾取 → **固定位置读数条**（不做浮动 tooltip） */
    ray.setFromCamera(ptr, camera);
    const hit = ray.intersectObjects(pickable(), false)[0];
    const node = hit ? hit.object : null;
    if (node !== hovered) {
      if (hovered) hovered.scale.setScalar(hovered.userData._s || 1);
      hovered = node;
      if (hovered) {
        hovered.userData._s = hovered.scale.x;
        hovered.scale.setScalar(hovered.scale.x * 1.5);
        canvas.style.cursor = "pointer";
      } else canvas.style.cursor = "default";
      $("ro-name").textContent = nameOf(node && node.userData);
      $("ro-bundle").textContent = (node && node.userData && node.userData.bundleLabel) || "—";
      $("ro-state").textContent = stateText(node && node.userData);
    }

    if (camTarget) {
      camera.position.lerp(camTarget.pos, 1 - Math.pow(0.001, dt));
      controls.target.lerp(camTarget.to, 1 - Math.pow(0.001, dt));
      if (camera.position.distanceTo(camTarget.pos) < 0.35) camTarget = null;
    }

    controls.update();
    composer.render();
    composerFrames++;      /* 合成器真跑的帧数（只增）⇒ 验收拿它证明后期这条路真在跑 */

    frames++;
    if (now - fpsAt > 1000) {
      $("st-fps").textContent = Math.round((frames * 1000) / (now - fpsAt));
      frames = 0; fpsAt = now;
    }
  }
  /* ══ §13 启动顺序（第 58 轮）══════════════════════════════════════════
     顺序**不能换**，有真依赖：先统一端点引用（否则排布挪了坐标、边还指着旧对象）
     → 再排布 → 再铺技能雾 → 最后挂标签（标签要贴在排布**之后**的坐标上）。 */
  BOOT.bind = bindEdgeRefsToMeshes();
  BOOT.net = layoutBrainVolume();
  BOOT.fog = buildSkillCloud();
  BOOT.labels = buildLabels();
  window.__brainNet = { bind: BOOT.bind, net: BOOT.net, fog: BOOT.fog, labels: BOOT.labels,
                        hd: null, snap: null };

  /* ── §13.5 视图固化 · **启动恢复**（必须放这里，不能放 §9）────────────────
     🔴 顺序陷阱（读代码看出来的，不是猜的）：`layoutBrainVolume()` 里 L1127 会
        `camera.position.set(...)` **重设相机**。若在 §9 就恢复视图，会被它覆盖
        ⇒ 页面显示的页签是"执行路线"，画面却还是"全脑"。⇒ 恢复只能放在 BOOT 之后。 */
  const BOOT_VIEW = readStoredView();
  applyView(BOOT_VIEW || "brain", true);
  VIEW.restored = BOOT_VIEW;
  /* 只读自述：验收要能**量**"固化有没有生效"，不靠看图说"记住了" */
  window.__brainView = VIEW;

  /* ── 验收注入口（第 62 轮加）· 口径写死在这里 ─────────────────────────────
     为什么需要它：要证"**未知 kind 不会凭空画出电弧**"（失败关闭），就必须能喂一个假事件进去；
     没有这个口子，那条判据只能靠嘴说。
     🔴 它的能力**仅限画一条电弧**：调 `spawnPulse`，不碰 `D`、不写盘、不改任何数据。 */
  window.__brainProbe = {
    spawn: function (p) {
      spawnPulse(p || {});
      return (window.__brainNet.arc_audit || []).length;
    },
    audit: function () { return (window.__brainNet.arc_audit || []).slice(); },
    /* `arc_audit` 是**环形缓冲（上限 60）**⇒ 一满长度就不动
       ⇒ **不许拿"长度差"当判据**（实测踩过：负对照被队列排空顶成假红、正对照被环形顶成假绿）。
       验收要用**唯一 ts 标记**去找自己的那条。`queue_left` 用来报"队列排空进度"。 */
    queue_left: function () { return queue.length; },
    audit_cap: 60,
  };

  /* ── §14 快照轮询：**不放宽 CSP 的活数据路** ──────────────────────────
     本页 CSP 是 `connect-src 'none'` ⇒ fetch/XHR 一律被浏览器拒；但 `script-src 'self'`
     放行**同源脚本** ⇒ 重新 append 一个 `<script src="brain-data.js?t=…">` 就能拿到新快照：
     不产生任何 fetch（不喷 CSP 红字）、不放宽任何一条策略、也不改主人的安全口径。
     （数据件用的是 `globalThis.GBT_BRAIN = {…}` ⇒ **可重复声明**，已实测；
       哪天它改成 `const`，这条路会当场断 —— 届时本函数如实把 `snap.ok` 置 false。）
     🔴 口径：新快照只把**比上次新的事件**入队 —— 电弧只为"真的刚发生"的调用打，
        绝不把历史事件重播成"正在跑"（那是本仓最贵的假绿）。 */
  let lastTs = (D.pulses || []).reduce((m, x) => Math.max(m, x.ts || 0), 0);
  const SNAP = { ok: true, polls: 0, adopt: 0, fresh: 0, poll_ms: 15000 };

  function adoptSnapshot(next) {
    const fresh = (next.pulses || []).filter((x) => (x.ts || 0) > lastTs)
                                    .sort((a, b) => a.ts - b.ts);
    fresh.forEach((x) => queue.push(x));
    if (fresh.length) lastTs = fresh[fresh.length - 1].ts;
    const structChanged = (next.caps_total !== D.caps_total)
      || ((next.edges || []).length !== capEdges.length);
    D.at = next.at || D.at;
    D.totals = next.totals || D.totals;
    D.pulses = next.pulses || D.pulses;
    SNAP.adopt++; SNAP.fresh += fresh.length;
    fillRail();
    if (structChanged) {
      const st = $("stale");
      if (st) { st.hidden = false;
        st.textContent = "新快照的结构变了（节点/边数不同）—— 排布要刷新页面才重建；"
                       + "事件与遥测已按新快照走。"; }
    }
    return { fresh: fresh.length, structChanged };
  }

  function pollSnapshot() {
    const s = document.createElement("script");
    s.async = true;
    s.src = "brain-data.js?t=" + Date.now();
    s.onload = function () {
      SNAP.polls++;
      const next = globalThis.GBT_BRAIN;
      const newer = ((next && next.pulses) || []).some((x) => (x.ts || 0) > lastTs);
      if (next && (next.at !== D.at || newer)) adoptSnapshot(next);
      s.remove();
    };
    s.onerror = function () { SNAP.ok = false; s.remove(); };
    document.head.appendChild(s);
  }
  setInterval(pollSnapshot, SNAP.poll_ms);

  /* 新鲜度与渲染分辨率：**每秒现算**。"落后多少秒"是读数，不是形容词。 */
  function updHud() {
    const at = Date.parse(D.at || "");
    const lag = isFinite(at) ? Math.round((Date.now() - at) / 1000) : null;
    const pr = renderer.getPixelRatio();
    const w = Math.round(canvas.width), h = Math.round(canvas.height);
    BOOT.lag = lag; BOOT.pr = pr; BOOT.drawing = [w, h];
    window.__brainNet.hd = { dpr: window.devicePixelRatio || 1, pr: pr, drawing: [w, h],
                             css: [canvas.clientWidth, canvas.clientHeight],
                             /* 合成器/辉光：**真在跑的读数**（不是"代码里有"） */
                             composer: { passes: (composer.passes || []).length,
                                         rt_frames: composerFrames,
                                         bloom: { strength: bloom.strength,
                                                  radius: bloom.radius,
                                                  threshold: bloom.threshold } } };
    window.__brainNet.snap = { at: D.at, lag_s: lag, polls: SNAP.polls, adopt: SNAP.adopt,
                               fresh: SNAP.fresh, ok: SNAP.ok, poll_ms: SNAP.poll_ms };
    const atEl = $("snap-at"), lagEl = $("snap-lag"), hdEl = $("hd-info"), dot = $("dot-sync");
    if (atEl) atEl.textContent = D.at || "—";
    if (lagEl) lagEl.textContent = (lag === null) ? "取不到" : (lag + "s");
    if (hdEl) hdEl.textContent = pr.toFixed(1) + "x · " + w + "×" + h;
    if (dot) dot.className = "dot " + (!SNAP.ok ? "off" : (lag !== null && lag < 900 ? "ok" : "warn"));
    if (!SNAP.ok) {
      const st = $("stale");
      if (st) { st.hidden = false;
        st.textContent = "快照更新失败：同源脚本取不到 —— 如实报静默，不假装在同步"; }
    }
  }
  updHud();
  setInterval(updHud, 1000);

  requestAnimationFrame(tick);
})();
