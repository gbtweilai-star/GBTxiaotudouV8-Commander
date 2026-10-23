/* GBT小土豆V8 · 语音剧场 · **2.5D 分层数字人**（经典脚本，无外部依赖，零 CDN）
 *
 * ## 它是什么
 * 把主人指定的那张形象图（CHARACTER-SPEC 里写死的唯一基准）做成**可动的分层件**：
 *   · 画质：最终画面就是那张图本身，只受显示尺寸限制 —— 不再有"200px 贴图撑一张脸"
 *   · 动作：呼吸 / 重心位移 / 头转颌点 / 发丝滞后 / 眨眼，全部是顶点级形变，不是骨骼插值
 *   · 嘴：嘴唇被"下颌形变"拉开，缝里露出画出来的口腔层（内壁+上齿+舌）—— 嘴是真的会开
 *
 * ## 为什么不用现役 3D 资产 dh-v2-rigged.glb
 * 它 65 根 Mixamo 骨里**没有颌骨**，网格**没有形态键**，嘴是焊死的（`tools/codex-scripts/anim-audit.py`
 * 读二进制量过）。三个要求里"语音嘴对齐"在它上面做不到 —— 不做假嘴动，换一条真能做到的路。
 *
 * ## 接线（对外只暴露这几件）
 *   window.GBT_DH2D.ready()                  → bool
 *   window.GBT_DH2D.info()                   → {ok,status,why,frames,...}
 *   window.GBT_DH2D.setState("idle"|"listen"|"think"|"speak")
 *   window.GBT_DH2D.level(0..1)              // 真音量（AnalyserNode 给的），不说话传 0
 *   window.GBT_DH2D.viseme({open,wide,round}) // 可选：更细的嘴型（0..1 各一个）
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
(function () {
  'use strict';

  var S = { ok: false, status: 'boot', why: '', frames: 0, state: 'idle',
            level: 0, jaw: 0, blink: 0, gl: '', canvas: null };

  function info() { return S; }
  function say(text, tone) {
    S.why = tone === 'ok' ? '' : text;
    try {
      var b = document.getElementById('dh3dStatus');
      if (b) { b.textContent = text; b.setAttribute('data-tone', tone || 'warn'); }
    } catch (e) { /* 试机台上没有这个角标，不算错 */ }
  }
  window.GBT_DH2D = {
    ready: function () { return S.ok; }, info: info,
    setState: function () {}, level: function () {}, viseme: function () {}, set: function () {}
  };

  /* ══ 形变公共 GLSL（顶点这一段两个程序共用，保证口腔层与身体走同一套变换） ══ */
  var DEFORM = [
    'precision highp float;',
    'attribute vec2 aUv;',
    'uniform vec2 uImg;',
    'uniform vec2 uViewC;',
    'uniform vec2 uViewS;',
    'uniform float uTime, uJaw, uBlink, uBreath, uSway, uTilt, uNod, uLook;',
    'uniform vec2 uMouth, uEyeL, uEyeR, uNeck, uHeadC;',
    'uniform float uLipY, uChinY, uHeadR;',
    'varying vec2 vUv;',
    'varying vec2 vUv0;',
    'varying float vJawW;',
    'float ell(vec2 p, vec2 c, vec2 r, float soft){',
    '  float d = length((p - c) / r);',
    '  return 1.0 - smoothstep(1.0 - soft, 1.0, d);',
    '}',
    'vec2 deform(vec2 uv){',
    '  vec2 p = uv * uImg;',
    '  vec2 d = vec2(0.0);',
    /* 重心位移：脚底不动，越往上摆得越多 */
    '  d.x += uSway * (1.0 - uv.y);',
    /* 呼吸：胸腔上下 + 左右微鼓 */
    '  float chest = 1.0 - smoothstep(0.30, 0.62, uv.y);',
    '  d.y -= uBreath * 7.0 * chest;',
    '  d.x += (p.x - uImg.x * 0.5) * 0.0045 * uBreath * chest;',
    /* 头（含发）整体刚性部分 */
    '  float mHead = ell(p, uHeadC, vec2(uHeadR * 0.98, uHeadR * 1.24), 0.55);',
    '  vec2 hp = p - uNeck;',
    '  float ca = cos(uTilt), sa = sin(uTilt);',
    '  vec2 rot = vec2(hp.x * ca - hp.y * sa, hp.x * sa + hp.y * ca);',
    '  d += (rot - hp) * mHead;',
    /* 点/摇头：沿颈轴压缩与左右偏移 */
    '  d.y -= hp.y * uNod * mHead;',
    '  d.x += uLook * 9.0 * mHead;',
    /* 下颌：绕耳侧枢轴张开，唇线以下的皮肤整体下沉 */
    '  float jx = 1.0 - smoothstep(30.0, 56.0, abs(p.x - uMouth.x));',
    /* 唇线上下 2~7px 内就到位（上一版写成 lipY-16 起坡 ⇒ 唇线处只吃到 0.2 的权重，
       嘴只开了 2px，看着像"嘴上贴了一条黑胶带"） */
    '  float jy = smoothstep(uLipY - 2.0, uLipY + 7.0, p.y);',
    '  float jw = clamp(jy * jx * mHead, 0.0, 1.0);',
    '  float f = clamp((p.y - (uLipY - 30.0)) / (uChinY - (uLipY - 30.0)), 0.0, 1.35);',
    '  d.y += uJaw * 20.0 * f * jw;',
    /* 发丝滞后：越靠外越慢半拍 */
    '  float hair = ell(p, uHeadC, vec2(uHeadR * 1.045, uHeadR * 1.30), 0.6) * (1.0 - mHead);',
    '  d.x += (sin(uTime * 1.15 + p.y * 0.013) * 3.4 - uSway * 0.45) * hair;',
    /* 眨眼：眼区纵向压扁 */
    '  float eL = ell(p, uEyeL, vec2(15.0, 9.5), 0.85);',
    '  float eR = ell(p, uEyeR, vec2(15.0, 9.5), 0.85);',
    '  float em = clamp(eL + eR, 0.0, 1.0) * uBlink;',
    '  float eyeCy = (uEyeL.y + uEyeR.y) * 0.5;',
    '  d.y -= (p.y - eyeCy) * 0.86 * em;',
    '  vJawW = jw;',
    '  return uv + d / uImg;',
    '}'
  ].join('\n');

  var VS_MAIN = DEFORM + '\n' + [
    'void main(){',
    '  vec2 uv2 = deform(aUv);',
    '  vUv = uv2; vUv0 = aUv;',
    '  vec2 p = uv2 * uImg;',
    '  gl_Position = vec4((p - uViewC) * uViewS * vec2(1.0, -1.0), 0.0, 1.0);',
    '}'
  ].join('\n');

  var FS_MAIN = [
    'precision highp float;',
    'uniform sampler2D uTex;',
    'uniform sampler2D uCav;',
    'uniform float uJaw, uLipY, uHalfW;',
    'uniform vec2 uMouth, uImg;',
    'varying vec2 vUv;',
    'varying vec2 vUv0;',
    'void main(){',
    '  vec4 c = texture2D(uTex, vUv);',
    '  vec3 col = c.rgb;',
    '  if (uJaw > 0.02) {',
    /* 口腔**在同一支着色器里合成**，不挖洞。
       上一版用 discard 挖洞、口腔另画一层，洞边直接透到页面底色 ⇒ 放大看就是"嘴上一块黑药丸"。 */
    '    vec2 q = vUv0 * uImg;',
    '    float hw = uHalfW * (0.78 + 0.22 * uJaw);',
    /* 唇缝是一条**上弯的弧**（她在笑），不是水平线：中间低、嘴角高。
       上一版按水平线开洞，洞口必然一半压在上唇、一半漏到嘴角外 —— 放大看就是"一条黑胶带斜贴着"。 */
    '    float ux = clamp((q.x - uMouth.x) / hw, -1.0, 1.0);',
    '    float seam = uLipY - 8.0 * ux * ux;',
    '    float dy = q.y - seam;',
    /* 上沿只啃 1.2px（保住上唇），下沿随张口长（下唇跟着下颌走，别把它吃掉） */
    '    float hhUp = 1.0;',
    '    float hh = dy < 0.0 ? 1.0 : (1.4 + 6.5 * uJaw);',
    '    float dd = length(vec2(ux, dy / hh));',
    '    float open = (1.0 - smoothstep(0.45, 1.0, dd)) * uJaw;',
    '    if (open > 0.004) {',
    /* 2026-10-19：**不再贴口腔、不出牙** —— 只压暗她自己的唇像素。
       依据：她的嘴在源图里只有 32×15 px，投到 720 宽画面约 31 px。这个尺寸上人眼看到的是
       "唇缝变深 + 下唇下移"，不是整排牙；而任何"贴一块口腔/牙"的做法放大看必然是贴纸
       （v1 硬边矩形 = 钢琴键、v2 圆角牙弧 = 卡通黑洞，两版实测都不合格，见 DH2D.md §11）。
       这也是 Live2D 在没有张口原画时的标准处理：只对真像素做形变+明度调制。 */
    '      float kk = clamp(open * 2.6, 0.0, 1.35);',
    /* 只加深**她自己已经暗的那条唇缝**：不画几何抛物线、不贴图。
       上一版用 seam = uLipY - 8*u^2 画几何线，两端必然爬到她唇角以上 ⇒ 放大看是一道"猫须"。
       改成按像素亮度取权重后，形状天然跟着她的唇形走：皮肤与唇面（亮）权重≈0，不会画到脸上。
       2026-10-19 二次调：幅度 1.7→2.6、权重区间 0.30~0.52→0.34~0.62、压暗到 0.40/0.20/0.24。
       原因是成片实测摆幅只有 3.2 级（旧版 40 级是假黑洞撑的）⇒ 1× 会读成"嘴没动"。 */
    '      float lum = dot(col, vec3(0.299, 0.587, 0.114));',
    '      float wt = 1.0 - smoothstep(0.34, 0.62, lum);',
    '      vec3 deep = col * vec3(0.40, 0.20, 0.24);',
    '      col = mix(col, deep, min(kk * wt, 1.0));',
    '    }',
    '  }',
    '  float al = c.a;',
    '  gl_FragColor = vec4(col * al, al);',
    '}'  ].join('\n');

  var VS_CAV = DEFORM + '\n' + [
    'attribute vec2 aUV2;',
    'varying vec2 vCav;',
    'void main(){',
    '  vec2 uv2 = deform(aUv);',
    '  vUv = uv2; vUv0 = aUv;',
    '  vCav = aUV2;',
    '  vec2 p = uv2 * uImg;',
    '  gl_Position = vec4((p - uViewC) * uViewS * vec2(1.0, -1.0), 0.0, 1.0);',
    '}'
  ].join('\n');

  var FS_CAV = [
    'precision highp float;',
    'uniform sampler2D uTex;',
    'varying vec2 vCav;',
    'void main(){',
    '  vec4 c = texture2D(uTex, vCav);',
    '  gl_FragColor = vec4(c.rgb * c.a, c.a);',
    '}'
  ].join('\n');

  function compile(gl, type, src) {
    var s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      throw new Error((type === gl.VERTEX_SHADER ? 'VS: ' : 'FS: ') + gl.getShaderInfoLog(s));
    }
    return s;
  }

  function program(gl, vs, fs) {
    var p = gl.createProgram();
    gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, vs));
    gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error('LINK: ' + gl.getProgramInfoLog(p));
    return p;
  }

  function tex(gl, img) {
    var t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    return t;
  }

  /* ══ 启动 ══════════════════════════════════════════════════════════ */
  function boot(canvas, atlas, opts) {
    opts = opts || {};
    var gl = canvas.getContext('webgl', { premultipliedAlpha: false, alpha: true, antialias: true })
          || canvas.getContext('experimental-webgl', { premultipliedAlpha: false, alpha: true });
    if (!gl) { S.status = 'no-webgl'; S.why = '这个壳不支持 WebGL'; return; }
    S.gl = (gl.getParameter(gl.VERSION) || '') + ' / ' + (gl.getParameter(gl.RENDERER) || '');

    var m = atlas.meta, A = m.anchors;
    var img = m.size;
    var U = {
      img: img, mouth: A.mouth, eyeL: A.eye_l, eyeR: A.eye_r, neck: [A.head_c[0], A.neck_y],
      headC: A.head_c, lipY: A.lip_line_y, chinY: A.chin_y, headR: 88,
      halfW: A.mouth_half_w
    };

    var pMain = program(gl, VS_MAIN, FS_MAIN);
    var pCav = program(gl, VS_CAV, FS_CAV);

    /* 网格：40×64 的规则格，够密到形变看不出折线，又不至于拖性能 */
    var NX = 112, NY = 288, verts = [], idx = [];
    for (var j = 0; j <= NY; j++) {
      for (var i = 0; i <= NX; i++) verts.push(i / NX, j / NY);
    }
    for (var j2 = 0; j2 < NY; j2++) {
      for (var i2 = 0; i2 < NX; i2++) {
        var a = j2 * (NX + 1) + i2, b = a + 1, c = a + NX + 1, d = c + 1;
        idx.push(a, c, b, b, c, d);
      }
    }
    var meshBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, meshBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(verts), gl.STATIC_DRAW);
    var idxBuf = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, idxBuf);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(idx), gl.STATIC_DRAW);

    /* 口腔层：一条贴着唇线的窄带，下颌形变会把它自然拉开 */
    var cavPos = null, cavUV = null;
    (function () {
      /* 口腔带的上下沿要盖住开口：上沿只到唇线上方 4px（被上唇压着），
         下沿放到唇线下方 18px —— 张口时下唇把这块布一起拉下去，牙与舌才有地方露出来。 */
      var w = U.halfW * 1.02, y0 = U.lipY - 4, y1 = U.lipY + 8;
      var v = [U.mouth[0] - w, y0, U.mouth[0] + w, y0, U.mouth[0] - w, y1, U.mouth[0] + w, y1];
      cavPos = new Float32Array([v[0] / img[0], v[1] / img[1], v[2] / img[0], v[3] / img[1],
                                 v[4] / img[0], v[5] / img[1], v[6] / img[0], v[7] / img[1]]);
      cavUV = new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]);
    })();
    var cavPosBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, cavPosBuf);
    gl.bufferData(gl.ARRAY_BUFFER, cavPos, gl.STATIC_DRAW);
    var cavUvBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, cavUvBuf);
    gl.bufferData(gl.ARRAY_BUFFER, cavUV, gl.STATIC_DRAW);

    function loadImg(src) {
      return new Promise(function (res, rej) {
        var im = new Image();
        im.onload = function () { res(im); };
        im.onerror = function () { rej(new Error('贴图解不开')); };
        im.src = src;
      });
    }

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

    var st = {
      state: 'idle', level: 0, jaw: 0, wide: 0, round: 0, blink: 0, blinkT: 0, nextBlink: 1.6,
      breath: 0, sway: 0, tilt: 0, nod: 0, look: 0
    };
    var t0 = performance.now();
    var proj = { cx: img[0] * 0.5, cy: null, sx: 0, sy: 0 };

    function fit() {
      var w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      gl.viewport(0, 0, canvas.width, canvas.height);
      /* 取景：把"人"这段高度（cropY 内）铺满画布高；两侧该切就切，脸才够大 */
      var cropH = (opts.cropH || 0.74) * img[1];
      var bandTop = (opts.bandTop || 0.0) * img[1];
      var aspect = canvas.width / Math.max(1, canvas.height);
      proj.sy = 2 / cropH;
      proj.sx = 2 / (cropH * aspect);
      proj.cx = (opts.cx || 0.5) * img[0];
      proj.cy = bandTop + cropH / 2;
    }
    window.addEventListener('resize', fit);

    function uni(p) {
      return {
        uImg: gl.getUniformLocation(p, 'uImg'),
        uViewC: gl.getUniformLocation(p, 'uViewC'),
        uViewS: gl.getUniformLocation(p, 'uViewS'),
        uTime: gl.getUniformLocation(p, 'uTime'),
        uJaw: gl.getUniformLocation(p, 'uJaw'),
        uBlink: gl.getUniformLocation(p, 'uBlink'),
        uBreath: gl.getUniformLocation(p, 'uBreath'),
        uSway: gl.getUniformLocation(p, 'uSway'),
        uTilt: gl.getUniformLocation(p, 'uTilt'),
        uNod: gl.getUniformLocation(p, 'uNod'),
        uLook: gl.getUniformLocation(p, 'uLook'),
        uMouth: gl.getUniformLocation(p, 'uMouth'),
        uEyeL: gl.getUniformLocation(p, 'uEyeL'),
        uEyeR: gl.getUniformLocation(p, 'uEyeR'),
        uNeck: gl.getUniformLocation(p, 'uNeck'),
        uHeadC: gl.getUniformLocation(p, 'uHeadC'),
        uLipY: gl.getUniformLocation(p, 'uLipY'),
        uChinY: gl.getUniformLocation(p, 'uChinY'),
        uHeadR: gl.getUniformLocation(p, 'uHeadR'),
        uHalfW: gl.getUniformLocation(p, 'uHalfW'),
        uTex: gl.getUniformLocation(p, 'uTex'),
        uCav: gl.getUniformLocation(p, 'uCav')
      };
    }
    var uM = uni(pMain), uC = uni(pCav);
    var texA = null, texC = null;

    function setCommon(u, t) {
      gl.uniform2fv(u.uImg, img);
      gl.uniform2f(u.uViewC, proj.cx, proj.cy);
      gl.uniform2f(u.uViewS, proj.sx, proj.sy);
      gl.uniform1f(u.uTime, t);
      gl.uniform1f(u.uJaw, st.jaw);
      gl.uniform1f(u.uBlink, st.blink);
      gl.uniform1f(u.uBreath, st.breath);
      gl.uniform1f(u.uSway, st.sway);
      gl.uniform1f(u.uTilt, st.tilt);
      gl.uniform1f(u.uNod, st.nod);
      gl.uniform1f(u.uLook, st.look);
      gl.uniform2fv(u.uMouth, U.mouth);
      gl.uniform2fv(u.uEyeL, U.eyeL);
      gl.uniform2fv(u.uEyeR, U.eyeR);
      gl.uniform2fv(u.uNeck, U.neck);
      gl.uniform2fv(u.uHeadC, U.headC);
      gl.uniform1f(u.uLipY, U.lipY);
      gl.uniform1f(u.uChinY, U.chinY);
      gl.uniform1f(u.uHeadR, U.headR);
      gl.uniform1f(u.uHalfW, U.halfW * (1 + 0.20 * st.wide));
    }

    function draw(t) {
      fit();
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);

      /* 1) 口腔层已合进主着色器（见 FS_MAIN），这里不再单独画 —— 留着会盖到嘴唇上 */
      if (false) { gl.useProgram(pCav);
      setCommon(uC, t);
      gl.bindTexture(gl.TEXTURE_2D, texC);
      gl.uniform1i(uC.uTex, 0);
      var ac = gl.getAttribLocation(pCav, 'aUv'), ac2 = gl.getAttribLocation(pCav, 'aUV2');
      gl.bindBuffer(gl.ARRAY_BUFFER, cavPosBuf);
      gl.enableVertexAttribArray(ac);
      gl.vertexAttribPointer(ac, 2, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, cavUvBuf);
      gl.enableVertexAttribArray(ac2);
      gl.vertexAttribPointer(ac2, 2, gl.FLOAT, false, 0, 0);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4); }

      /* 2) 人物 */
      gl.useProgram(pMain);
      setCommon(uM, t);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, texA);
      gl.uniform1i(uM.uTex, 0);
      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, texC);
      gl.uniform1i(uM.uCav, 1);
      gl.activeTexture(gl.TEXTURE0);
      var am = gl.getAttribLocation(pMain, 'aUv');
      gl.bindBuffer(gl.ARRAY_BUFFER, meshBuf);
      gl.enableVertexAttribArray(am);
      gl.vertexAttribPointer(am, 2, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, idxBuf);
      gl.drawElements(gl.TRIANGLES, idx.length, gl.UNSIGNED_SHORT, 0);
      S.jawNow = +st.jaw.toFixed(3);
      S.blinkNow = +st.blink.toFixed(3);
    }

    /* 注意：cavPos / cavUV 在第 210 行就声明过了 —— 这里**不许**再写一次 `var cavPos = null`，
       那会在 IIFE 之后把它们清成 null（var 提升只提升声明，不提升赋值），缓冲就成了空数组。 */

    Promise.all([loadImg(atlas.albedo), loadImg(atlas.cavity)]).then(function (ims) {
      texA = tex(gl, ims[0]);
      texC = tex(gl, ims[1]);
      fit();
      S.ok = true;
      S.status = 'ready';
      S.canvas = canvas;
      say('数字人就绪 · 图集 ' + img[0] + '×' + img[1] + ' · 嘴型吃真音量（' + S.gl.split('/')[0].trim() + '）', 'ok');
      if (opts.onReady) opts.onReady(S);
      (function loop() {
        var now = performance.now();
        var t = (now - t0) / 1000;
        step(t, 1 / 60);
        draw(t);
        S.frames += 1;
        S.jawNow = +st.jaw.toFixed(3);
        S.blinkNow = +st.blink.toFixed(3);
        requestAnimationFrame(loop);
      })();
    }).catch(function (e) {
      S.status = 'tex-fail';
      S.why = '图集加载失败：' + String(e && e.message || e);
      say('数字人图集加载失败：' + S.why, 'fault');
      if (opts.onReady) opts.onReady(S);
    });

    /* ══ 动作：全部由时间与状态推，不读随机数（可复现才量得准） ══ */
    function step(t, dt) {
      if (st.frozen) return;          /* 截图/量具用：冻结动作，直接看某一组参数 */
      var sp = st.state;
      var lv = (sp === 'speak') ? st.level : 0;
      var breathTarget = 0.5 + 0.5 * Math.sin(t * 1.9);   // 0..1，约 3.3s 一次呼吸
      st.breath = breathTarget;
      st.sway = Math.sin(t * 0.42) * 11.0 + Math.sin(t * 0.19) * 5.0 + (sp === 'listen' ? 2.4 * Math.sin(t * 0.9) : 0);
      st.tilt = Math.sin(t * 0.31) * 0.030 + Math.sin(t * 0.13) * 0.012 + (sp === 'think' ? 0.05 : 0);
      st.nod = Math.sin(t * 0.67) * 0.016 - (sp === 'listen' ? 0.020 : 0);
      st.look = Math.sin(t * 0.23) * 0.5 + (sp === 'think' ? 0.35 : 0);

      /* 嘴：音量包络 + 说话时的音节起伏（不是固定正弦，随包络走） */
      var want = 0;
      if (sp === 'speak') {
        var syl = 0.55 + 0.45 * Math.sin(t * 11.3) * Math.sin(t * 3.7);
        want = lv * (0.62 + 0.38 * syl);
      }
      want = Math.max(0, Math.min(1, want));
      st.jaw += (want - st.jaw) * (want > st.jaw ? 0.55 : 0.30);
      st.wide = st.jaw * 0.5;
      st.round = st.jaw * 0.3;

      /* 眨眼：按节律表，不用随机（同一分钟两次开页面看到的应该一样） */
      st.nextBlink -= dt;
      if (st.nextBlink <= 0) { st.blinkT = 0.001; st.nextBlink = 2.6 + 1.7 * (0.5 + 0.5 * Math.sin(t * 0.7)); }
      if (st.blinkT > 0) {
        st.blinkT += dt;
        var k = st.blinkT / 0.16;
        st.blink = k < 0.5 ? k * 2 : Math.max(0, 2 - k * 2);
        if (k >= 1) { st.blinkT = 0; st.blink = 0; }
      } else st.blink = 0;
    }

    /* ══ 对外接口 ══ */
    window.GBT_DH2D.setState = function (n) { st.state = String(n || 'idle'); S.state = st.state; };
    window.GBT_DH2D.level = function (v) {
      var x = Number(v);
      st.level = isFinite(x) ? Math.max(0, Math.min(1, x)) : 0;
    };
    window.GBT_DH2D.viseme = function (o) {
      o = o || {};
      if (o.open != null) st.jaw = Math.max(0, Math.min(1, +o.open));
      if (o.wide != null) st.wide = Math.max(0, Math.min(1, +o.wide));
      if (o.round != null) st.round = Math.max(0, Math.min(1, +o.round));
    };
    /* 量具/截图用：冻结动作并直接给一组参数（不改变业务接口） */
    window.GBT_DH2D.set = function (o) {      o = o || {};
      if (o.jaw != null) st.jaw = +o.jaw;
      if (o.blink != null) st.blink = +o.blink;
      if (o.breath != null) st.breath = +o.breath;
      if (o.sway != null) st.sway = +o.sway;
      if (o.tilt != null) st.tilt = +o.tilt;
      if (o.nod != null) st.nod = +o.nod;
      if (o.look != null) st.look = +o.look;
      if (o.freeze) st.frozen = true;
    };
    var _step = step;
    step = function (t, dt) { if (st.frozen) return; _step(t, dt); };
    window.GBT_DH2D._draw = function (t) { draw(t == null ? 1 : t); return true; };
    /* 量具口：把动作推进 n 帧。
       为什么需要：无头 Chromium 把 rAF 节流到几乎不走，不推进就等于"动作链没跑过"。
       这个口走的是**真的 step()**（level → 包络 → 嘴），不是绕过它直接塞 jaw ——
       否则验出来的只是着色器，验不到"音量能不能驱动嘴"。 */
    window.GBT_DH2D._tick = function (n, dt) {
      n = n || 1;
      dt = dt || (1 / 60);
      var t = performance.now() / 1000;
      for (var i = 0; i < n; i++) step(t + i * dt, dt);
      draw(t + n * dt);
      return { jaw: +st.jaw.toFixed(4), blink: +st.blink.toFixed(4),
               level: st.level, state: st.state };
    };
    /* 量具用：把"冻结"也当动作入口，截图脚本只需要打一个口（_step 里已经拦了） */
    window.GBT_DH2D._frozen = function (v) { st.frozen = !!v; return !!st.frozen; };
    /* 取景口：cropH = 画面里能看到多少「图像高度」，越小 = 镜头越近。
       出片时用它做推镜（半身 → 特写）；量具也用它按不同取景复算。 */
    window.GBT_DH2D.setCrop = function (h, bandTop) {
      var v = Number(h);
      if (isFinite(v) && v > 0.05) opts.cropH = v;
      if (bandTop != null && isFinite(Number(bandTop))) opts.bandTop = Number(bandTop);
      fit();
      return { cropH: opts.cropH, bandTop: opts.bandTop || 0 };
    };

    /* 量具/出片口：**当场画一帧、当场把像素读出来**，不依赖页面合成。
       （实测教训：无头 Chromium 把 rAF 节流到几乎不走，`page.screenshot` 拿到的是
       上一次"已呈现"的旧帧 —— jaw 从 0 改到 0.95，截图一模一样，差点被读成"嘴不动"。）
       返回 data:image/png;base64,...；背景是竖直渐变（舞台底色），可直接进 ffmpeg。 */
    window.GBT_DH2D._png = function (t, bgTop, bgBot) {
      draw(t == null ? 1 : t);
      var w = canvas.width, h = canvas.height;
      var px = new Uint8Array(w * h * 4);
      gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
      var out = new Uint8ClampedArray(w * h * 4);
      var top = bgTop || [5, 7, 12], bot = bgBot || [11, 18, 32];
      for (var y = 0; y < h; y++) {
        var sy = h - 1 - y;                    /* WebGL 原点在左下，翻过来 */
        var k = y / Math.max(1, h - 1);
        var br = top[0] + (bot[0] - top[0]) * k;
        var bg2 = top[1] + (bot[1] - top[1]) * k;
        var bb = top[2] + (bot[2] - top[2]) * k;
        for (var x = 0; x < w; x++) {
          var si = (sy * w + x) * 4, di = (y * w + x) * 4;
          var a = px[si + 3] / 255;            /* 着色器输出的是预乘色 ⇒ 直接 + 背景*(1-a) */
          out[di] = px[si] + br * (1 - a);
          out[di + 1] = px[si + 1] + bg2 * (1 - a);
          out[di + 2] = px[si + 2] + bb * (1 - a);
          out[di + 3] = 255;
        }
      }
      var cv2 = document.createElement('canvas');
      cv2.width = w; cv2.height = h;
      var c2 = cv2.getContext('2d');
      var im = c2.createImageData(w, h);
      im.data.set(out);
      c2.putImageData(im, 0, 0);
      return cv2.toDataURL('image/png');
    };
  }

  /* ══ 自启：页面上有 #dh2d 就自己跑（也允许外部先放好 atlas 再 late boot） ══ */
  window.GBT_DH2D.boot = boot;
  window.addEventListener('load', function () {
    var cv = document.getElementById('dh2d');
    if (!cv) return;
    if (!window.GBT_DH2D_ATLAS) {
      S.status = 'no-atlas';
      S.why = 'assets/dh2d/atlas.js 没载进来（图集缺失）';
      return;
    }
    boot(cv, window.GBT_DH2D_ATLAS, {
      cropH: parseFloat(cv.getAttribute('data-crop-h') || '0.74'),
      bandTop: parseFloat(cv.getAttribute('data-band-top') || '0'),
      cx: parseFloat(cv.getAttribute('data-cx') || '0.5')
    });
  });
})();




