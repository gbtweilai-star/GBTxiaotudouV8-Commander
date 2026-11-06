/* skin-hud-live.js · 会动的 HUD 层（2026-11-06）
 * 做五件事：工程图底层 / 扫描线 / 四边刻度 / 粒子尘 / 读数柱；粒子用 rAF，30fps 封顶。
 * 只读浏览器的时钟与帧率，不请求后端 —— 皮肤不拖慢 APP。
 */
(function () {
  if (window.__hudLive) return;
  window.__hudLive = true;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ── ① 工程图底层（z-index 2：在面板之下，只在留白里露出来）──
  var ground = document.createElement('div');
  ground.className = 'hud-ground';
  ground.setAttribute('aria-hidden', 'true');
  ground.innerHTML =
    '<svg class="hud-sketch" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"></svg>' +
    '<div class="hud-callout tl"><b>COGNITION FIELD</b><span>L1 · CAPS</span></div>' +
    '<div class="hud-callout tr"><b>LINK BUS</b><span>LOCAL · CTX</span></div>' +
    '<div class="hud-callout bl"><b>MEMORY CHAIN</b><span>STATE · LEDGER</span></div>' +
    '<div class="hud-callout br"><b>SENSOR ARRAY</b><span>DOMAIN · TENTACLE</span></div>';
  document.body.appendChild(ground);

  var sketch = ground.querySelector('svg');
  var callout = {
    tl: ground.querySelector('.hud-callout.tl'),
    tr: ground.querySelector('.hud-callout.tr'),
    bl: ground.querySelector('.hud-callout.bl'),
    br: ground.querySelector('.hud-callout.br')
  };

  // 图纸细部按 .console 的真实盒模型排：改窗口就重排一次（防抖 180ms）
  function layoutGround() {
    var host = document.querySelector('.console') || document.body;
    var r = host.getBoundingClientRect();
    var W = window.innerWidth, H = window.innerHeight;
    sketch.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

    var parts = [];
    // 罗盘中心：压在输入区后面，刻度扇在正文下方的留白里
    var cx = r.left + r.width / 2;
    var cy = r.bottom - 120;
    var R = Math.min(r.width * 0.36, 380);

    // ① 放射刻度扇：2° 一齿，10° 一长齿（只有上半圈，下方留给输入框）
    var tick = [];
    for (var deg = 196; deg <= 344; deg += 2) {
      var rad = deg * Math.PI / 180;
      var long = deg % 10 === 0;
      var r1 = R, r2 = R + (long ? 13 : 6);
      var ca = Math.cos(rad), sa = Math.sin(rad);
      tick.push('M' + (cx + ca * r1).toFixed(1) + ' ' + (cy + sa * r1).toFixed(1) +
        ' L' + (cx + ca * r2).toFixed(1) + ' ' + (cy + sa * r2).toFixed(1));
    }
    parts.push('<path class="d-tick" d="' + tick.join('') + '"/>');

    // ② 两圈弧：内圈断线（像分度盘），外圈细实线，只画上半
    function arc(radius, cls, from, to) {
      var a0 = from * Math.PI / 180, a1 = to * Math.PI / 180;
      var x0 = cx + Math.cos(a0) * radius, y0 = cy + Math.sin(a0) * radius;
      var x1 = cx + Math.cos(a1) * radius, y1 = cy + Math.sin(a1) * radius;
      return '<path class="d-ring ' + cls + '" d="M' + x0.toFixed(1) + ' ' + y0.toFixed(1) +
        ' A' + radius.toFixed(1) + ' ' + radius.toFixed(1) + ' 0 0 1 ' + x1.toFixed(1) + ' ' + y1.toFixed(1) + '"/>';
    }
    parts.push(arc(R - 34, 'dash', 190, 350));
    parts.push(arc(R + 30, '', 200, 340));

    // ③ 定位十字：240px 图纸格交点，中心 R*0.62 内让位给正文
    var step = 240, arm = 4, guard = R * 0.62;
    for (var gx = Math.ceil(r.left / step) * step; gx <= r.right; gx += step) {
      for (var gy = Math.ceil(r.top / step) * step; gy <= r.bottom; gy += step) {
        var dx = gx - cx, dy = gy - (r.top + r.height * 0.34);
        if (Math.sqrt(dx * dx + dy * dy) < guard) continue;
        parts.push('<path class="d-cross" d="M' + (gx - arm) + ' ' + gy + ' h' + (arm * 2) +
          ' M' + gx + ' ' + (gy - arm) + ' v' + (arm * 2) + '"/>');
      }
    }

    // ④ 四角引出线：L 形 + 3px 方块节点（图纸语言，不是装饰花边）
    function lead(x, y, dx, dy) {
      parts.push('<path class="d-lead" d="M' + x.toFixed(1) + ' ' + y.toFixed(1) +
        ' h' + dx + ' v' + dy + '"/>' +
        '<rect class="d-node" x="' + (x + dx - 1.5).toFixed(1) + '" y="' +
        (y + dy - 1.5).toFixed(1) + '" width="3" height="3"/>');
    }
    lead(r.left + 28, r.top + 128, 110, 26);
    lead(r.right - 28, r.top + 128, -110, 26);
    lead(r.left + 28, r.bottom - 176, 110, -26);
    lead(r.right - 28, r.bottom - 176, -110, -26);

    sketch.innerHTML = parts.join('');

    // 标注列贴着中栏四角，不压正文（正文列宽 952px 居中，四角都在列外）
    callout.tl.style.left = (r.left + 26) + 'px';
    callout.tl.style.top = (r.top + 100) + 'px';
    callout.tr.style.left = (r.right - 26) + 'px';
    callout.tr.style.top = (r.top + 100) + 'px';
    callout.bl.style.left = (r.left + 26) + 'px';
    callout.bl.style.top = (r.bottom - 208) + 'px';
    callout.br.style.left = (r.right - 26) + 'px';
    callout.br.style.top = (r.bottom - 208) + 'px';
  }
  layoutGround();

  var relayout = 0;
  window.addEventListener('resize', function () {
    clearTimeout(relayout);
    relayout = setTimeout(layoutGround, 180);
  });

  // ── ② 动态层 ──
  var wrap = document.createElement('div');
  wrap.className = 'hud-live';
  wrap.setAttribute('aria-hidden', 'true');
  wrap.innerHTML =
    '<div class="hud-ruler top"></div>' +
    '<div class="hud-ruler bottom"></div>' +
    '<div class="hud-ruler left"></div>' +
    '<div class="hud-ruler right"></div>' +
    '<div class="hud-scan"></div>' +
    '<div class="hud-orbit"><div class="ring"></div><div class="ring b"></div></div>' +
    '<canvas class="hud-dust"></canvas>' +
    '<div class="hud-rail l">' +
      '<span>LINK <b class="live">●</b></span>' +
      '<span>SYS <b data-hud="clock">--:--:--</b></span>' +
      '<span>FPS <b data-hud="fps">--</b></span>' +
      '<span class="bar"><i></i></span>' +
      '<span>WEIGHTS</span>' +
      '<span>LOCAL</span>' +
    '</div>' +
    '<div class="hud-rail r">' +
      '<span>SESSION <b data-hud="uptime">0s</b></span>' +
      '<span>SCAN <b data-hud="scan">IDLE</b></span>' +
      '<span class="bar"><i></i></span>' +
      '<span>GBT · V8</span>' +
    '</div>';
  document.body.appendChild(wrap);

  var clock = wrap.querySelector('[data-hud="clock"]');
  var fpsEl = wrap.querySelector('[data-hud="fps"]');
  var upEl = wrap.querySelector('[data-hud="uptime"]');
  var scanEl = wrap.querySelector('[data-hud="scan"]');
  var t0 = Date.now();

  function tickClock() {
    var d = new Date();
    if (clock) clock.textContent = [d.getHours(), d.getMinutes(), d.getSeconds()]
      .map(function (n) { return (n < 10 ? '0' : '') + n; }).join(':');
    if (upEl) upEl.textContent = Math.round((Date.now() - t0) / 1000) + 's';
  }
  tickClock();
  setInterval(tickClock, 1000);

  // ── 粒子尘 ──
  var cv = wrap.querySelector('canvas');
  var ctx = cv && cv.getContext ? cv.getContext('2d') : null;
  if (!ctx || reduce) { if (cv) cv.style.display = 'none'; return; }

  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  var W = 0, H = 0, parts = [];
  function resize() {
    W = window.innerWidth; H = window.innerHeight;
    cv.width = Math.floor(W * dpr); cv.height = Math.floor(H * dpr);
    cv.style.width = W + 'px'; cv.style.height = H + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var n = Math.max(36, Math.min(90, Math.round(W * H / 42000)));
    parts = [];
    for (var i = 0; i < n; i++) {
      parts.push({ x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.12, vy: -0.05 - Math.random() * 0.16,
        r: 0.6 + Math.random() * 1.4, a: 0.10 + Math.random() * 0.35, p: Math.random() * 6.283 });
    }
  }
  resize();
  window.addEventListener('resize', resize);

  var last = 0, frames = 0, fpsT = performance.now();
  function loop(now) {
    requestAnimationFrame(loop);
    if (now - last < 33) return;            // 30fps 封顶
    last = now;
    frames++;
    if (now - fpsT >= 1000) {
      if (fpsEl) fpsEl.textContent = String(frames);
      frames = 0; fpsT = now;
    }
    ctx.clearRect(0, 0, W, H);
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      p.x += p.vx; p.y += p.vy; p.p += 0.02;
      if (p.y < -8) { p.y = H + 8; p.x = Math.random() * W; }
      if (p.x < -8) p.x = W + 8; else if (p.x > W + 8) p.x = -8;
      var a = p.a * (0.6 + 0.4 * Math.sin(p.p));
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, 6.283);
      ctx.fillStyle = 'rgba(88,200,224,' + a.toFixed(3) + ')';
      ctx.fill();
    }
  }
  requestAnimationFrame(loop);

  // 扫描状态：跟着真实请求走（有 fetch 就点亮）
  if (window.fetch && !window.__hudFetch) {
    window.__hudFetch = true;
    var orig = window.fetch;
    window.fetch = function () {
      if (scanEl) scanEl.textContent = 'RUN';
      return orig.apply(this, arguments).finally(function () {
        if (scanEl) scanEl.textContent = 'IDLE';
      });
    };
  }
})();
