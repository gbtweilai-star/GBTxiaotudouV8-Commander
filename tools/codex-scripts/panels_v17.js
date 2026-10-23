  /* ══════════════════════════════════════════════════════════════════
     V17 · 补两个「有源码、有规格、却没有任何面板」的东西
     —— 原生浏览器与云电脑独立窗口，
     外加严格覆盖判据揪出的三块（万能插工具集 / 编排内核 / 假覆盖清单）。
     ══════════════════════════════════════════════════════════════════ */
  var N17 = V17.v17;   /* 数据常量本身就叫 V17（全局改名后的结果），本段挂在它的 v17 键下 */
  var BRW = N17.browser, CPC = N17.cloudpc, TLS = N17.tools, KRN = N17.kernel, SA = N17.strict_audit;

  function n17(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

  function apiRows(items, limit) {
    if (!items || !items.length) return '<div class="statline" style="color:var(--ink-3)">无公开函数。</div>';
    var sh = items.slice(0, limit || 12);
    var h = sh.map(function (m) {
      return '<div style="padding:4px 0;border-bottom:1px solid var(--line)">' +
        '<div class="mono" style="font-size:10.5px;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
        esc(m.name) + '</div>' +
        (m.doc ? '<p style="font-size:9.5px;color:var(--ink-3);margin:3px 0 0;line-height:1.7">' + esc(m.doc) + '</p>' : '') +
        '</div>';
    }).join('');
    if (items.length > sh.length) {
      h += '<p style="font-size:10px;color:var(--ink-3);margin-top:7px">… 另 ' + (items.length - sh.length) + ' 个</p>';
    }
    return h;
  }

  function clsRows(cls) {
    return (cls || []).map(function (c) {
      return '<div style="padding:6px 0;border-bottom:1px solid var(--line)">' +
        '<div style="display:flex;align-items:baseline;gap:8px">' +
        '<span class="mono" style="font-size:11px;color:var(--ink)">' + esc(c.name) + '</span>' +
        '<span class="mono dim" style="font-size:9.5px;margin-left:auto">' + c.n + ' 公开方法</span></div>' +
        (c.doc ? '<p style="font-size:10px;color:var(--ink-3);margin:3px 0 0;line-height:1.7">' + esc(c.doc) + '</p>' : '') +
        (c.pub && c.pub.length ? '<div class="capwrap" style="margin-top:5px">' + c.pub.map(function (x) {
          return '<span class="cap"><i></i>' + esc(x) + '</span>';
        }).join('') + '</div>' : '') + '</div>';
    }).join('');
  }

  /* ── 面板 51：原生浏览器 ── */
  function panelV17Browser() {
    head('原生浏览器', { tag: 'native_browser', meta: n17(BRW.ctrl_lines) + ' 行 + ' + BRW.cap_lines + ' 行' });
    $('chatBody').innerHTML =
      '<div class="card"><div class="card-h"><b>原生浏览器控制器</b> / CHROME DEVTOOLS PROTOCOL' +
      '<span class="r">' + esc(BRW.ctrl) + '</span></div><div class="card-b">' +
      '<p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' + esc(BRW.what) + '</p>' +
      '<div class="grid3" style="gap:8px;margin-top:11px">' +
      '<div><div class="mono" style="font-size:20px;color:var(--neon-2)">' + n17(BRW.ctrl_lines) + '</div>' +
      '<div class="mono dim" style="font-size:9.5px">行 · 控制器</div></div>' +
      '<div><div class="mono" style="font-size:20px;color:var(--neon-2)">' + BRW.ops.length + '</div>' +
      '<div class="mono dim" style="font-size:9.5px">个操作</div></div>' +
      '<div><div class="mono" style="font-size:20px;color:var(--neon-2)">' + BRW.classes.length + '</div>' +
      '<div class="mono dim" style="font-size:9.5px">个类</div></div></div>' +
      '<div class="degrade" style="margin-top:11px"><span>' + esc(BRW.why) + '</span></div>' +
      '</div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>' + BRW.ops.length +
      ' 个操作</b> / OPERATIONS<span class="r">读自模块 docstring</span></div><div class="card-b"><div class="capwrap">' +
      BRW.ops.map(function (o) { return '<span class="cap g"><i></i>' + esc(o) + '</span>'; }).join('') +
      '</div></div></div>' +
      '<div class="grid2" style="margin-top:11px">' +
      '<div class="card"><div class="card-h"><b>内部实现</b> / INTERNALS<span class="r">' +
      BRW.classes.length + ' 类 · ' + BRW.api.length + '+ 函数</span></div><div class="card-b">' +
      clsRows(BRW.classes) + '</div></div>' +
      '<div class="card"><div class="card-h"><b>窗口置顶落位</b> / PIN WINDOW<span class="r">pin_window</span></div>' +
      '<div class="card-b">' + Object.keys(BRW.window).map(function (k) {
        return '<div class="statline"><span class="led g"></span>' +
          '<span style="font-size:10.5px;color:var(--ink-2);white-space:normal">' + esc(BRW.window[k]) + '</span></div>';
      }).join('') + '</div></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>能力入口的三级后端</b> / BROWSER CAP' +
      '<span class="r">' + esc(BRW.cap) + ' · ' + BRW.cap_lines + ' 行</span></div><div class="card-b">' +
      '<div class="grid3" style="gap:8px">' + BRW.cap_tiers.map(function (t, i) {
        return '<div class="stagecard"><div class="sh">' + (i + 1) + ' 级<span class="k">' + esc(t[0]) + '</span></div>' +
          '<div class="sb" style="font-size:10px">' + esc(t[1]) + '</div></div>';
      }).join('') + '</div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:10px">如实降级：装了什么就说什么，没装就说 needs_dependency 并给安装指引。</p>' +
      '</div></div>';
  }

  /* ── 面板 52：云电脑独立窗口 ── */
  function panelV17CloudPC() {
    var W = CPC.window, C = CPC.current;
    var dim = function (b) { return b ? '<span class="led a"></span>' : '<span class="led d"></span>'; };
    head('云电脑独立窗口', { tag: CPC.kind, meta: CPC.lines + ' 行 · ' + CPC.domain + ' · ' + CPC.cap_type });
    $('chatBody').innerHTML =
      '<div class="card"><div class="card-h"><b>形态</b> / FORM<span class="r">R-H284 主人定</span></div><div class="card-b">' +
      '<p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' + esc(CPC.what) + '</p>' +
      '<div class="degrade" style="margin-top:10px"><span>' + esc(W.not_iframe) + '　·　' + esc(W.for_whom) +
      '　·　事实源：' + esc(W.source_of_truth) + '</span></div>' +
      '<div class="grid2" style="margin-top:11px;gap:12px">' +
      '<div><div class="mono dim" style="font-size:10px;margin-bottom:6px">卡片只呈现</div>' +
      (W.card_shows || []).map(function (x) {
        return '<div class="statline"><span class="led g"></span><span style="font-size:10.5px;color:var(--ink-2);white-space:normal">' +
          esc(x) + '</span></div>';
      }).join('') + '</div>' +
      '<div><div class="mono dim" style="font-size:10px;margin-bottom:6px">按钮一律过门</div>' +
      '<div class="routebar"><code style="flex:1;font-size:10px">' + esc(W.buttons_go_through) + '</code></div>' +
      '<div class="statline" style="margin-top:6px"><span class="led g"></span>' +
      '<span style="font-size:10.5px;color:var(--ink-2)">和别的卡同级 —— 独立窗口，不是嵌进别人的卡里</span></div>' +
      '</div></div></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>五原语</b> / PRIMITIVES' +
      '<span class="r">逐个标：可逆 · 花钱 · 过门</span></div><div class="card-b">' +
      CPC.primitives.map(function (p) {
        var tone = (!p.reversible || p.needs_gate) ? 'a' : 'g';
        return '<div style="padding:8px 0;border-bottom:1px solid var(--line)">' +
          '<div style="display:flex;align-items:baseline;gap:8px;flex-wrap:wrap">' +
          '<span class="mono" style="font-size:12px;color:var(--ink);font-weight:var(--w-sem)">' + esc(p.key) + '</span>' +
          '<span style="font-size:10.5px;color:var(--ink-2)">' + esc(p.cn) + '</span>' +
          '<span class="capwrap" style="margin-left:auto">' +
          '<span class="cap' + (p.reversible ? ' g' : '') + '"><i></i>' + (p.reversible ? '可逆' : '不可逆') + '</span>' +
          '<span class="cap' + (p.costs_money ? '' : ' g') + '"><i></i>' + (p.costs_money ? '花钱' : '不花钱') + '</span>' +
          '<span class="cap' + (p.needs_gate ? '' : ' g') + '"><i></i>' + (p.needs_gate ? '必须过门' : '不必卡门') + '</span>' +
          '</span></div>' +
          '<p style="font-size:10px;color:var(--ink-3);margin:5px 0 0;line-height:1.75">' + esc(p.note) + '</p></div>';
      }).join('') + '</div></div>' +
      '<div class="grid2" style="margin-top:11px">' +
      '<div class="card"><div class="card-h"><b>五条红线</b> / RED LINES<span class="r">' + CPC.red_lines.length +
      ' 条</span></div><div class="card-b">' + CPC.red_lines.map(function (r, i) {
        return '<div class="statline" style="align-items:flex-start"><span class="led r" style="margin-top:5px"></span>' +
          '<span style="font-size:10.5px;color:var(--ink-2);white-space:normal;line-height:1.75">' +
          '<span class="mono" style="color:var(--ink-3)">红' + (i + 1) + '</span> ' + esc(r) + '</span></div>';
      }).join('') + '</div></div>' +
      '<div class="card"><div class="card-h"><b>当前状态</b> / CURRENT<span class="r">骨架只读</span></div><div class="card-b">' +
      '<div class="statline"><span class="led ' + (C.credentials_present ? 'g' : 'r') + '"></span>' +
      '<span class="mono" style="font-size:10.5px">云厂商凭据</span>' +
      '<span class="n mono" style="font-size:10px;color:' + (C.credentials_present ? 'var(--green)' : 'var(--rose)') + '">' +
      (C.credentials_present ? '有' : '无') + '</span></div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin:8px 0 0;line-height:1.8">' + esc(C.credential_note) + '<br>' +
      esc(C.provider_note) + '<br><span style="color:var(--amber)">' + esc(C.local_pc_state) + '</span></p>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;padding-top:9px;border-top:1px solid var(--line);line-height:1.8">' +
      esc(CPC.boundary) + '</p></div></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>带牙用例</b> / TEETH<span class="r">只读骨架也有牙</span></div>' +
      '<div class="card-b">' + apiRows(CPC.api, 8) + '</div></div>';
  }

  /* ── 面板 53：万能插工具集 ── */
  function panelV17Tools() {
    head('万能插工具集', { tag: 'tools', meta: TLS.n + ' 文件 · ' + n17(TLS.lines) + ' 行' });
    var maxL = TLS.files.length ? TLS.files[0].lines : 1;
    $('chatBody').innerHTML =
      '<div class="card"><div class="card-h"><b>gbt_allinone/tools</b> / TOOLBOX' +
      '<span class="r">' + TLS.n + ' 文件 · ' + n17(TLS.lines) + ' 行</span></div><div class="card-b">' +
      '<div class="degrade"><span>' + esc(TLS.why) + '</span></div>' +
      '<div style="margin-top:11px">' + TLS.files.slice(0, 22).map(function (t) {
        var w = Math.round(100 * t.lines / maxL);
        return '<div style="padding:4px 0"><div style="display:flex;align-items:baseline;gap:8px;font-size:10.5px">' +
          '<span class="mono" style="color:var(--ink-2);min-width:196px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
          esc(t.f.split('/').pop()) + '</span>' +
          '<span style="color:var(--ink-3);font-size:9.5px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
          esc((t.doc || '').slice(0, 40)) + '</span>' +
          '<span class="mono" style="font-size:10px;color:var(--neon-2)">' + n17(t.lines) + '</span></div>' +
          '<span class="track" style="display:block;margin-top:3px"><i style="width:' + Math.max(w, 2) + '%"></i></span></div>';
      }).join('') + '</div>' +
      (TLS.files.length > 22 ? '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">… 另 ' +
        (TLS.files.length - 22) + ' 个文件 / ' +
        n17(TLS.files.slice(22).reduce(function (a, x) { return a + x.lines; }, 0)) + ' 行</p>' : '') +
      '</div></div>';
  }

  /* ── 面板 54：编排内核 ── */
  function panelV17Kernel() {
    head('编排内核', { tag: 'orchestration_kernel', meta: KRN.lines + ' 行 · ' + KRN.source });
    $('chatBody').innerHTML =
      '<div class="card"><div class="card-h"><b>三源蒸馏</b> / THREE SOURCES<span class="r">' + esc(KRN.source) + '</span></div>' +
      '<div class="card-b"><div class="grid3" style="gap:8px">' + KRN.three.map(function (t) {
        return '<div class="stagecard"><div class="sh">' + esc(t[0]) + '</div>' +
          '<div class="sb" style="font-size:10px">' + esc(t[1]) + '</div></div>';
      }).join('') + '</div>' +
      '<div class="degrade" style="margin-top:11px"><span>' + esc(KRN.why) + '</span></div></div></div>' +
      '<div class="grid2" style="margin-top:11px">' +
      '<div class="card"><div class="card-h"><b>三层职责</b> / LAYERS<span class="r">' + KRN.layers.length + ' 层</span></div>' +
      '<div class="card-b">' + KRN.layers.map(function (l, i) {
        return '<div class="statline" style="align-items:flex-start"><span class="led g" style="margin-top:5px"></span>' +
          '<span style="font-size:10.5px;color:var(--ink-2);white-space:normal;line-height:1.75">' +
          '<span class="mono" style="color:var(--ink-3)">第' + (i + 1) + '层</span> ' + esc(l) + '</span></div>';
      }).join('') + '</div></div>' +
      '<div class="card"><div class="card-h"><b>真调用点</b> / THE REAL CALL SITE<span class="r">治「挂号不接线」</span></div>' +
      '<div class="card-b"><p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' + esc(KRN.teeth) + '</p></div></div>' +
      '</div>' +
      '<div class="grid2" style="margin-top:11px">' +
      '<div class="card"><div class="card-h"><b>内部类型</b> / CLASSES<span class="r">' + KRN.classes.length + ' 个</span></div>' +
      '<div class="card-b">' + clsRows(KRN.classes) + '</div></div>' +
      '<div class="card"><div class="card-h"><b>能力入口</b> / API</div><div class="card-b">' +
      apiRows(KRN.api, 8) + '</div></div></div>';
  }

  /* ── 面板 55：严格覆盖审计 ── */
  function panelV17Strict() {
    var dirs = Object.keys(SA.by_dir).map(function (k) {
      return { k: k, n: SA.by_dir[k].n, lines: SA.by_dir[k].lines };
    }).sort(function (a, b) { return b.lines - a.lines; });
    var maxD = dirs.length ? dirs[0].lines : 1;
    head('严格覆盖审计', { tag: 'strict-audit', meta: '假覆盖 ' + n17(SA.false_covered_lines) + ' 行' });
    $('chatBody').innerHTML =
      '<div class="card"><div class="card-h"><b>宽松判据漏掉了什么</b> / FALSE COVERAGE' +
      '<span class="r">再收一层判据</span></div><div class="card-b">' +
      '<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:8px">' +
      '<span class="mono" style="font-size:28px;color:var(--rose);line-height:1">' + n17(SA.false_covered_n) + '</span>' +
      '<span class="mono dim" style="font-size:12px">个文件 / ' + n17(SA.false_covered_lines) +
      ' 行 —— 宽松口径下被算作「已覆盖」，其实只是名字在清单里出现过</span></div>' +
      '<p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' +
      '<b>方法</b>：' + esc(SA.method) + '<br>' +
      '<b>怎么暴露的</b>：' + esc(SA.why) + '</p>' +
      '<div class="degrade" style="margin-top:10px"><span><b>上界不是精确值</b>：' + esc(SA.caveat) + '</span></div>' +
      '</div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>假覆盖按目录</b> / BY DIR' +
      '<span class="r">' + dirs.length + ' 个目录</span></div><div class="card-b">' +
      dirs.slice(0, 14).map(function (d) {
        var w = Math.round(100 * d.lines / maxD);
        return '<div style="padding:3px 0"><div style="display:flex;align-items:baseline;gap:8px;font-size:10.5px">' +
          '<span class="mono" style="color:var(--ink-2);min-width:230px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
          esc(d.k) + '</span>' +
          '<span style="color:var(--ink-3);font-size:9.5px">' + d.n + ' 文件</span>' +
          '<span class="mono" style="margin-left:auto;font-size:10px;color:var(--rose)">' + n17(d.lines) + '</span></div>' +
          '<span class="track" style="display:block;margin-top:3px"><i class="rose" style="width:' + Math.max(w, 2) + '%"></i></span></div>';
      }).join('') + '</div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>最大的假覆盖文件</b> / TOP FILES' +
      '<span class="r">主人点名的那一类</span></div><div class="card-b">' +
      SA.top.slice(0, 16).map(function (t) {
        return '<div class="statline"><span class="led a"></span>' +
          '<span class="mono" style="font-size:10.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
          esc(t.rel) + '</span>' +
          '<span class="n mono" style="font-size:10px">' + n17(t.lines) + ' 行</span></div>';
      }).join('') + '</div></div>';
  }

