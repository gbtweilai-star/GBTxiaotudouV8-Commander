  /* ══════════════════════════════════════════════════════════════════
     工作区源码层 · V12 新增 10 面板
     数字全部来自本机递归清点 + AST 解析（不是探针调用）：
     23835 文件 / 1202 MB / 文本 4218849 行 / 代码 8125 文件 / 1941784 行；
     剥掉 vendored 与脚手架后，自有代码 233905 行（含测试 24748）。
     其中 80023 行此前从未进入任何面板。
     ══════════════════════════════════════════════════════════════════ */
  var WS = V12.workspace;
  var UN = WS.unseen;

  function wsHuman(n) {
    if (n == null) return '—';
    if (n >= 1048576) return (n / 1048576).toFixed(0) + ' MB';
    if (n >= 1024) return (n / 1024).toFixed(0) + ' KB';
    return n + ' B';
  }
  function wsNum(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
  function wsAreaCell(s) {
    return '<div class="statline"><span class="led ' + (s.verdict && s.verdict.indexOf('活') === 0 ? 'g' : 'a') + '"></span>' +
      esc(s.zh) + '<span class="n mono" style="font-size:9.5px">' + s.py + ' 文件 · ' + wsNum(s.lines) + ' 行 · 入口 ' +
      s.with_main + ' · 外部引用 ' + s.referenced_outside + '</span></div>';
  }

  /* ── 面板 31：工作区源码总览 ── */
  function panelWsOverview() {
    head('工作区源码总览', { tag: 'workspace', meta: '递归清点 ' + wsNum(WS.inventory.file_count) + ' 文件' });
    var iv = WS.inventory, bk = WS.buckets, own = 0;
    Object.keys(bk).forEach(function (k) {
      if (k === '自有源码' || k === '测试') own += bk[k].lines;
    });
    var order = ['自有源码', '测试', 'vendored/第三方或生成物', '构建脚手架(.scratch)', '运行期数据/产出'];
    var maxB = Math.max.apply(null, order.map(function (k) { return bk[k] ? bk[k].lines : 0; }));
    var ext = Object.keys(iv.by_ext).slice(0, 10);
    var maxE = ext.length ? iv.by_ext[ext[0]] : 1;
    $('chatBody').innerHTML = dshCoverCard() +
      '<div class="grid2" style="margin-top:11px">' +
      '<div class="card"><div class="card-h"><b>清点口径</b> / INVENTORY<span class="r">' +
      esc(String(WS.scanned_at).slice(0, 10)) + '</span></div><div class="card-b">' +
      '<div class="grid2" style="gap:9px;margin-bottom:10px">' +
      '<div><div class="mono" style="font-size:19px;color:var(--neon-2)">' + wsNum(iv.file_count) + '</div>' +
      '<div class="mono dim" style="font-size:9px">文件</div></div>' +
      '<div><div class="mono" style="font-size:19px;color:var(--neon-2)">' + wsHuman(iv.total_bytes) + '</div>' +
      '<div class="mono dim" style="font-size:9px">体积</div></div></div>' +
      kvRows([['代码文件', wsNum(iv.code_files) + ' 个', 'g'],
              ['代码行', wsNum(iv.code_lines) + ' 行', 'g'],
              ['文本总行', wsNum(iv.total_lines) + ' 行', 'd'],
              ['跳过 .git', wsNum(iv.skipped['.git'] || 0), 'd'],
              ['跳过 __pycache__', wsNum(iv.skipped['__pycache__'] || 0), 'd'],
              ['跳过 node_modules', wsNum(iv.skipped['node_modules'] || 0), 'd']]) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px;line-height:1.8">' +
      '口径：' + esc(WS.source) + '<br>含二进制与数据文件 —— 所以「文件数」远大于「代码文件数」。</p></div></div>' +
      '<div class="card"><div class="card-h"><b>剥掉第三方之后</b> / OWN SOURCE<span class="r">自有 ' +
      wsNum(own) + ' 行</span></div><div class="card-b">' +
      order.map(function (k) {
        var v = bk[k]; if (!v) return '';
        var p = Math.round(100 * v.lines / maxB);
        var tone = (k === '自有源码') ? '' : (k === '测试' ? '' : 'warn');
        return '<div style="padding:4px 0"><div style="display:flex;align-items:baseline;gap:8px;font-size:10.5px">' +
          '<span style="color:var(--ink-2)">' + esc(k) + '</span>' +
          '<span class="mono" style="margin-left:auto;font-size:10px;color:' +
          (k === '自有源码' ? 'var(--neon-2)' : 'var(--ink-3)') + '">' + wsNum(v.lines) + ' 行 · ' + v.n + ' 文件</span></div>' +
          '<span class="track" style="display:block;margin-top:4px"><i class="' + tone + '" style="width:' + Math.max(p, 2) + '%"></i></span></div>';
      }).join('') +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.8">' +
      '194 万行代码里，<b>128 万行是 vendored 第三方</b>（numpy / fastapi / pygments / uiautomation / comtypes），' +
      '41 万行是我自己造的构建脚手架。真正属于这个项目的自有代码只有 <b>' + wsNum(own) + ' 行</b>。' +
      '<span style="color:var(--amber)">之前我一直没做这个剥离，所以「有多少代码」这件事我从来没有准确数字。</span></p></div></div>' +
      '</div>' +
      '<div class="grid2" style="margin-top:11px">' +
      '<div class="card"><div class="card-h"><b>按文件类型</b> / BY EXTENSION</div><div class="card-b">' +
      ext.map(function (e) {
        var p = Math.round(100 * iv.by_ext[e] / maxE);
        return '<div style="padding:3px 0"><div style="display:flex;align-items:baseline;gap:8px;font-size:10.5px">' +
          '<span class="mono" style="color:var(--ink-2);min-width:74px">' + esc(e) + '</span>' +
          '<span class="mono" style="margin-left:auto;font-size:10px;color:var(--ink-3)">' + wsNum(iv.by_ext[e]) + '</span></div>' +
          '<span class="track" style="display:block;margin-top:3px"><i style="width:' + Math.max(p, 2) + '%"></i></span></div>';
      }).join('') + '</div></div>' +
      '<div class="card"><div class="card-h"><b>自有代码按顶层目录</b> / OWN BY TOP</div><div class="card-b">' +
      Object.keys(WS.own_by_top).slice(0, 12).map(function (k) {
        var v = WS.own_by_top[k];
        return '<div class="statline"><span class="led g"></span>' +
          '<span class="mono" style="font-size:10.5px">' + esc(k) + '</span>' +
          '<span class="n mono" style="font-size:9.5px">' + v.n + ' 文件 · ' + wsNum(v.lines) + ' 行</span></div>';
      }).join('') + '</div></div>' +
      '</div>';
  }

  /* ── 面板 32：工作区缺口对账 ── */
  function panelWsGap() {
    head('工作区缺口对账', { tag: 'gap', meta: '80023 行从未进面板' });
    var keys = Object.keys(UN);
    var tot = 0;
    keys.forEach(function (k) { tot += UN[k].lines || 0; });
    var ownTotal = 0;
    Object.keys(WS.buckets).forEach(function (k) {
      if (k === '自有源码' || k === '测试') ownTotal += WS.buckets[k].lines;
    });
    var p = Math.round(100 * tot / ownTotal);
    $('chatBody').innerHTML = '<div class="card"><div class="card-h"><b>这次扫出来的缺口</b> / THE GAP' +
      '<span class="r">占自有代码 ' + p + '%</span></div><div class="card-b">' +
      '<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:8px">' +
      '<span class="mono" style="font-size:30px;color:var(--rose);line-height:1">' + wsNum(tot) + '</span>' +
      '<span class="mono dim" style="font-size:12px">行自有代码，此前<b>从未进入任何一个面板</b></span></div>' +
      '<span class="track" style="display:block"><i class="rose" style="width:' + Math.max(p, 3) + '%"></i></span>' +
      '<p style="font-size:10.5px;color:var(--ink-2);margin-top:11px;line-height:1.9">' +
      '问题的性质要说清楚：前 11 版我扫的是<b>运行期读数</b> —— 调 <span class="mono">run_task</span> 拿返回。' +
      '这能告诉我「能力注册了几个、跑通没有」，<b>但告诉不了我源码里还有什么没被注册成能力的东西</b>。<br>' +
      '这次改成<b>真读源码</b>（递归清点 + AST 解析），缺口立刻就现形了。</p></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>九个板块逐条</b> / AREA BY AREA' +
      '<span class="r">活性已判定</span></div><div class="card-b">' +
      keys.sort(function (a, b) { return (UN[b].lines || 0) - (UN[a].lines || 0); }).map(function (k) {
        return wsAreaCell(UN[k]);
      }).join('') +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.8">' +
      '「外部引用」= 该板块之外的自有代码里，出现该板块模块名的文件数。' +
      '九个板块<b>全部有外部引用或有可执行入口</b> —— 没有一个是纯孤儿。' +
      '也就是说：这不是死代码，是<b>活的功能，只是没进界面</b>。</p></div></div>' +
      '<div class="grid2" style="margin-top:11px">' +
      '<div class="card"><div class="card-h"><b>死代码扫描</b> / DEAD CODE<span class="r">全自有 .py</span></div><div class="card-b">' +
      kvRows([['raise NotImplementedError', '2 处 / 2 文件（providers.py 各一，是抽象基类约定）', 'g'],
              ['TODO / FIXME / XXX', '6 处 / 4 文件（3 处在 .openclaw/tmp 的历史脚本）', 'g'],
              ['占位 pass 函数体', '2 处（都在测试里）', 'g'],
              ['裸 NotImplemented', '1 处（.openclaw/tmp/audit_gbt.py）', 'g']]) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">结论：源码里没有成规模的未完成占位 —— 缺口不在「没写完」，在「没接进界面」。</p></div></div>' +
      '<div class="card"><div class="card-h"><b>硬编码密钥复核</b> / SECRETS<span class="r">31 处命中</span></div><div class="card-b">' +
      kvRows([['命中总数', '31 处 / 9 文件', 'd'],
              ['测试假体', '31 处（形如 sk-abcdefghijklmnop）', 'g'],
              ['需人工复核', '0 处', 'g']]) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px;line-height:1.8">' +
      '逐条看过上下文：全部在 tests/ 里当夹具用，且多条断言是「不许出现在审计输出里」。' +
      '按掩码核对，<b>未见真实密钥落库</b>。</p></div></div>' +
      '</div>';
  }

  /* ── 通用：单板块详情页 ── */
  function wsAreaPage(navTitle, key, extraCard) {
    var s = UN[key];
    head(navTitle, { tag: key, meta: (s.py || 0) + ' 文件 · ' + wsNum(s.lines || 0) + ' 行' });
    var cls = (s.classes || []).map(function (c) {
      return '<div style="padding:7px 0;border-bottom:1px solid var(--line)">' +
        '<div style="display:flex;align-items:baseline;gap:8px">' +
        '<span class="mono" style="font-size:11px;color:var(--ink)">' + esc(c[0]) + '</span>' +
        (c[1] ? '<span class="mono dim" style="font-size:9.5px;margin-left:auto">' + c[1] + ' 方法</span>' : '') +
        '</div><p style="font-size:10px;color:var(--ink-3);margin:4px 0 0;line-height:1.7">' + esc(c[2]) + '</p></div>';
    }).join('');
    $('chatBody').innerHTML = wsCoverStrip() +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>' + esc(s.zh) + '</b> / ' + esc(key.toUpperCase()) +
      '<span class="r">' + esc(s.verdict || '') + '</span></div><div class="card-b">' +
      '<p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' + esc(s.what) + '</p>' +
      '<div class="grid3" style="gap:9px;margin-top:11px">' +
      '<div><div class="mono" style="font-size:18px;color:var(--neon-2)">' + (s.py || 0) + '</div>' +
      '<div class="mono dim" style="font-size:9px">Python 文件</div></div>' +
      '<div><div class="mono" style="font-size:18px;color:var(--neon-2)">' + wsNum(s.lines || 0) + '</div>' +
      '<div class="mono dim" style="font-size:9px">代码行</div></div>' +
      '<div><div class="mono" style="font-size:18px;color:var(--neon-2)">' + (s.referenced_outside || 0) + '</div>' +
      '<div class="mono dim" style="font-size:9px">外部引用</div></div></div>' +
      '<div class="degrade" style="margin-top:11px"><span>' + esc(s.note) + '</span></div>' +
      '</div></div>' +
      '<div class="grid2" style="margin-top:11px">' +
      '<div class="card"><div class="card-h"><b>主要类型 / 模块</b> / API SURFACE<span class="r">AST 抽取</span></div>' +
      '<div class="card-b">' + (cls || '<div class="statline" style="color:var(--ink-3)">该板块无类定义，能力都在顶层函数里。</div>') + '</div></div>' +
      '<div class="card"><div class="card-h"><b>关键构成</b> / COMPONENTS<span class="r">入口 ' + (s.with_main || 0) + ' · 测试 ' + (s.tests || 0) + '</span></div>' +
      '<div class="card-b">' + (s.extra || []).map(function (t) {
        return '<div class="statline"><span class="led g"></span>' +
          '<span style="font-size:10.5px;color:var(--ink-2);white-space:normal">' + esc(t) + '</span></div>';
      }).join('') +
      (extraCard || '') + '</div></div></div>';
  }

  function wsCoverStrip() {
    var ownTotal = 0;
    Object.keys(WS.buckets).forEach(function (k) {
      if (k === '自有源码' || k === '测试') ownTotal += WS.buckets[k].lines;
    });
    return '<div class="card"><div class="card-h"><b>源码覆盖</b> / SOURCE COVERAGE' +
      '<span class="r">自有 ' + wsNum(ownTotal) + ' 行</span></div><div class="card-b">' +
      '<p style="font-size:10px;color:var(--ink-3);line-height:1.8">' +
      '本页是 <b>V12 新增</b>的工作区源码层 —— 前 11 版从未覆盖这一块。' +
      '数字来自递归清点 + AST 解析，不是探针调用。</p></div></div>';
  }

  function panelWsHolo() { wsAreaPage('全息面板桥', 'holo_pet'); }
  function panelWsPotato() { wsAreaPage('桌面数字人', 'potato_pet'); }
  function panelWsDesign() { wsAreaPage('设计大脑', 'caps/design_brain'); }

  function panelWsFive() {
    wsAreaPage('五维合一 · 脑眼耳嘴手', '.cluster/five-dim-ultimate',
      '<div class="degrade" style="margin-top:10px"><span>' +
      '两套五维必须分清：<b>gbt_allinone 的 brain</b> 是 route / execute / tentacle / vision / audit（大脑执行层面板画的是这套）；' +
      '<b>这套</b>是脑-眼-耳-嘴-手（Brain-Eye-Ear-Mouth-Hand）。' +
      '工作区里两套并存，我在 V11 之前只呈现了前一套，且从未说明还有第二套。</span></div>');
  }

  function panelWsRecon30() {
    wsAreaPage('情报流水线 last30days', 'gbt_allinone/recon/last30days',
      '<div class="statline" style="margin-top:9px"><span class="led d"></span>' +
      '<span style="font-size:10px;color:var(--ink-3);white-space:normal">' +
      'v3.0.0 的五源引擎：GitHub Search API / YouTube（yt-dlp 转写）/ Reddit / Polymarket / TikTok。' +
      '规划器是 LLM 优先，但对「危险查询」有确定性兜底 —— 即大模型挂了也不会乱跑。</span></div>');
  }

  function panelWsAesth() {
    wsAreaPage('审美技能与骨架', '审美相关skill',
      '<div class="statline" style="margin-top:9px"><span class="led d"></span>' +
      '<span style="font-size:10px;color:var(--ink-3);white-space:normal">' +
      '本项目 1507 个 .md 里有 469 个在这个目录 —— 占三成。它与我的唯一交集就是设计流程要读的那几份规则文件，' +
      '代码层我一行没读过。</span></div>');
  }

  function panelWsQuant() {
    wsAreaPage('量化与钱包', 'agent-gvmz-gbtv8',
      '<div class="statline" style="margin-top:9px"><span class="led a"></span>' +
      '<span style="font-size:10px;color:var(--ink-3);white-space:normal">' +
      '注意：同族文件还散落在顶层 .openclaw/tmp/（412 个 .py）。' +
      '这个板块涉及真实资金链路，任何冒烟测试都应在隔离房间跑，不许直连生产。</span></div>');
  }

  function panelWsLedger() {
    var a = UN['holo_pet_w3'], b = UN['brain'];
    head('四路账本与审美大脑', { tag: 'w3 · brain', meta: '2 板块 / ' + ((a.lines || 0) + (b.lines || 0)) + ' 行' });
    $('chatBody').innerHTML = wsCoverStrip() +
      '<div class="grid2" style="margin-top:11px">' +
      '<div class="card"><div class="card-h"><b>四路账本常驻化</b> / LEDGER W3<span class="r">' + a.py + ' 文件</span></div>' +
      '<div class="card-b"><p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' + esc(a.what) + '</p>' +
      '<div class="capwrap" style="margin-top:9px">' + a.extra.map(function (t) {
        return '<span class="cap g"><i></i>' + esc(t.split(' · ')[0]) + '</span>';
      }).join('') + '</div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px">' + esc(a.note) + '</p></div></div>' +
      '<div class="card"><div class="card-h"><b>审美大脑与技能打磨</b> / BRAIN<span class="r">' + b.py + ' 文件</span></div>' +
      '<div class="card-b"><p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' + esc(b.what) + '</p>' +
      '<div class="capwrap" style="margin-top:9px">' + b.extra.map(function (t) {
        return '<span class="cap g"><i></i>' + esc(t.split(' · ')[0]) + '</span>';
      }).join('') + '</div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px">' + esc(b.note) + '</p></div></div>' +
      '</div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>为什么这两个要放一起</b> / WHY TOGETHER</div>' +
      '<div class="card-b"><p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' +
      '一个是给我自己看的账本常驻化，一个是给自己用的审美评估与技能打磨 —— ' +
      '两块都很小（合计 ' + ((a.lines || 0) + (b.lines || 0)) + ' 行），但都属于「框架的自我维护层」。' +
      '它们此前一个都没进面板。</p></div></div>';
  }

  /* ── 上帝视角 · 源码覆盖卡 ── */
  function wsCoverCard() {
    var bk = WS.buckets, ownTotal = 0;
    Object.keys(bk).forEach(function (k) {
      if (k === '自有源码' || k === '测试') ownTotal += bk[k].lines;
    });
    var gap = 0;
    Object.keys(UN).forEach(function (k) { gap += UN[k].lines || 0; });
    var order = ['自有源码', '测试', 'vendored/第三方或生成物', '构建脚手架(.scratch)', '运行期数据/产出'];
    var maxB = Math.max.apply(null, order.map(function (k) { return bk[k] ? bk[k].lines : 0; }));
    return '<div class="card" style="margin-bottom:11px"><div class="card-h"><b>工作区源码</b> / WORKSPACE SOURCE' +
      '<span class="r">V12 新增 · 从未进过面板的 ' + wsNum(gap) + ' 行已补</span></div><div class="card-b">' +
      '<div class="grid3" style="gap:9px;margin-bottom:11px">' +
      '<div><div class="mono" style="font-size:18px;color:var(--neon-2)">' + wsNum(WS.inventory.file_count) + '</div>' +
      '<div class="mono dim" style="font-size:9px">文件 · ' + wsHuman(WS.inventory.total_bytes) + '</div></div>' +
      '<div><div class="mono" style="font-size:18px;color:var(--neon-2)">' + wsNum(ownTotal) + '</div>' +
      '<div class="mono dim" style="font-size:9px">自有代码行</div></div>' +
      '<div><div class="mono" style="font-size:18px;color:var(--rose)">' + wsNum(gap) + '</div>' +
      '<div class="mono dim" style="font-size:9px">曾漏掉的行</div></div></div>' +
      order.map(function (k) {
        var v = bk[k]; if (!v) return '';
        var p = Math.round(100 * v.lines / maxB);
        return '<div style="padding:3px 0"><div style="display:flex;align-items:baseline;gap:8px;font-size:10px">' +
          '<span class="mono" style="color:var(--ink-3);min-width:172px">' + esc(k) + '</span>' +
          '<span class="mono" style="margin-left:auto;font-size:9.5px;color:' +
          (k === '自有源码' ? 'var(--neon-2)' : 'var(--ink-3)') + '">' + wsNum(v.lines) + '</span></div>' +
          '<span class="track" style="display:block;margin-top:3px"><i class="' +
          (k === '自有源码' ? '' : 'warn') + '" style="width:' + Math.max(p, 2) + '%"></i></span></div>';
      }).join('') +
      '<p style="font-size:9.5px;color:var(--ink-3);margin-top:9px">' +
      '口径：递归清点 + AST 解析（不是探针）。194 万行代码里 128 万行是 vendored 第三方。</p></div></div>';
  }
