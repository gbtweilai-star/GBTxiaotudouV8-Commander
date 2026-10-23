  /* ══════════════════════════════════════════════════════════════════
     V18 · 能力广场（源码驱动）
     三份真相合并，每一条都能追到源码：
       ① caps_registry  登记面（名字/域/说明/handler/safe）
       ② api.py 反查    实现面（实现模块路径 + 行数 + 模块自述 + op 表 + 公开函数）
       ③ 140 能力真调   实测面（跑通 / 待授权 / 待参数）
     ══════════════════════════════════════════════════════════════════ */
  var CS = V18.capsrc;
  var csFilter = 'all';

  function csState(s) {
    return { ok: ['g', '跑通'], gated: ['a', '待授权'], needs_params: ['d', '待参数'] }[s]
      || ['d', s];
  }
  function csNum(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

  function csRow(c) {
    var st = csState(c.state);
    var ops = [];
    Object.keys(c.ops || {}).forEach(function (k) {
      (c.ops[k] || []).slice(0, 12).forEach(function (v) { if (ops.indexOf(v) < 0) ops.push(v); });
    });
    return '<div style="padding:8px 0;border-bottom:1px solid var(--line)">' +
      '<div style="display:flex;align-items:baseline;gap:9px;flex-wrap:wrap">' +
      '<span class="led ' + st[0] + '"></span>' +
      '<span class="mono" style="font-size:11.5px;color:var(--ink);font-weight:var(--w-sem)">' + esc(c.name) + '</span>' +
      '<span class="mono dim" style="font-size:9.5px">' + esc(c.domain) + '</span>' +
      '<span class="cap ' + (st[0] === 'g' ? 'g' : '') + '" style="height:18px;font-size:9px">' + st[1] + '</span>' +
      (c.ms ? '<span class="mono dim" style="font-size:9px">' + c.ms + 'ms</span>' : '') +
      '<span class="mono" style="margin-left:auto;font-size:9.5px;color:var(--neon-2)">' +
      (c.module ? esc(String(c.module).replace('gbt_allinone/', '')) + ' · ' + csNum(c.module_lines) + ' 行'
                : 'api.py 内联 / 包级入口') + '</span></div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin:4px 0 0;line-height:1.7">' + esc(c.desc || '') + '</p>' +
      (c.module_doc ? '<p style="font-size:9.5px;color:var(--ink-3);margin:3px 0 0;line-height:1.7">' +
        '<span style="color:var(--ink-2)">源码自述：</span>' + esc(c.module_doc) + '</p>' : '') +
      (ops.length ? '<div class="capwrap" style="margin-top:5px">' + ops.map(function (o) {
        return '<span class="cap" style="height:18px;font-size:9px"><i></i>' + esc(o) + '</span>';
      }).join('') + '</div>' : '') +
      (c.note ? '<p style="font-size:9px;color:var(--ink-3);margin:4px 0 0">实测：' + esc(c.note) + '</p>' : '') +
      '</div>';
  }

  function panelCapSrc() {
    var bs = CS.by_state;
    var list = CS.caps.filter(function (c) { return csFilter === 'all' || c.state === csFilter; });
    head('能力广场 · 源码驱动', { tag: 'caps_registry + api.py', meta: CS.total + ' 能力 · ' + CS.n_modules + ' 模块' });
    var chips = [['all', '全部 ' + CS.total], ['ok', '跑通 ' + (bs.ok || 0)],
                 ['gated', '待授权 ' + (bs.gated || 0)], ['needs_params', '待参数 ' + (bs.needs_params || 0)]];
    $('chatBody').innerHTML =
      '<div class="card"><div class="card-h"><b>三份真相合并</b> / THREE SOURCES' +
      '<span class="r">' + esc(CS.source) + '</span></div><div class="card-b">' +
      '<div class="grid3" style="gap:10px">' +
      '<div><div class="mono" style="font-size:20px;color:var(--neon-2)">' + CS.total + '</div>' +
      '<div class="mono dim" style="font-size:9.5px">已登记能力</div></div>' +
      '<div><div class="mono" style="font-size:20px;color:var(--neon-2)">' + CS.n_modules + '</div>' +
      '<div class="mono dim" style="font-size:9.5px">实现模块（去重）</div></div>' +
      '<div><div class="mono" style="font-size:20px;color:var(--neon-2)">' +
      csNum(CS.caps.reduce(function (a, c) { return a + (c.module_lines || 0); }, 0)) + '</div>' +
      '<div class="mono dim" style="font-size:9.5px">模块行数合计</div></div></div>' +
      '<div class="grid3" style="gap:10px;margin-top:11px">' +
      '<div><div class="mono" style="font-size:18px;color:var(--green)">' + (bs.ok || 0) + '</div>' +
      '<div class="mono dim" style="font-size:9.5px">实测跑通</div></div>' +
      '<div><div class="mono" style="font-size:18px;color:var(--amber)">' + (bs.gated || 0) + '</div>' +
      '<div class="mono dim" style="font-size:9.5px">卡授权门（授权只能主人发）</div></div>' +
      '<div><div class="mono" style="font-size:18px;color:var(--ink-3)">' + (bs.needs_params || 0) + '</div>' +
      '<div class="mono dim" style="font-size:9.5px">需给参数（有实现）</div></div></div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:11px;line-height:1.8">' +
      '每条都追得到源码：登记项来自 <span class="mono">caps_registry.BENIGN_CAPS</span>；' +
      '实现模块由 <span class="mono">api.py</span> 的路由分支反查得到；op 表与模块自述直接读源码；' +
      '状态是 140 个能力逐个真调的实测结果。<br>' +
      '<span style="color:var(--amber)">本页取代原先手写的「能力广场」—— 之前那版的能力清单是我转述的，这一版是源码驱动的。</span>' +
      '</p></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>筛选</b> / FILTER' +
      '<span class="r">' + list.length + ' / ' + CS.total + '</span></div><div class="card-b">' +
      '<div class="capwrap">' + chips.map(function (c) {
        return '<button class="pill" data-csf="' + c[0] + '" style="cursor:pointer;' +
          (csFilter === c[0] ? 'border-color:var(--neon);color:var(--neon-2)' : '') + '">' + esc(c[1]) + '</button>';
      }).join('') + '</div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px">按域分布：' +
      Object.keys(CS.by_domain).sort(function (a, b) { return CS.by_domain[b] - CS.by_domain[a]; })
        .map(function (d) { return esc(d) + ' ' + CS.by_domain[d]; }).join(' · ') + '</p>' +
      '</div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>逐个能力</b> / CAPABILITIES' +
      '<span class="r">按域 · 名字排序</span></div><div class="card-b">' +
      list.slice().sort(function (a, b) {
        return (a.domain + a.name).localeCompare(b.domain + b.name);
      }).map(csRow).join('') + '</div></div>';

    Array.prototype.forEach.call(document.querySelectorAll('[data-csf]'), function (b) {
      b.addEventListener('click', function () { csFilter = b.dataset.csf; panelCapSrc(); });
    });
  }

  /* 上帝视角加一张源码覆盖卡 */
  function capSourceCard() {
    var top = Object.keys(CS.modules).slice(0, 8);
    return '<div class="card" style="margin-bottom:11px"><div class="card-h"><b>能力 → 源码</b> / CAP → SOURCE' +
      '<span class="r">' + CS.total + ' 能力 · ' + CS.n_modules + ' 模块</span></div><div class="card-b">' +
      top.map(function (m) {
        var v = CS.modules[m];
        return '<div class="statline"><span class="led g"></span>' +
          '<span class="mono" style="font-size:10.5px">' + esc(String(m).replace('gbt_allinone/', '')) + '</span>' +
          '<span class="n mono" style="font-size:9.5px">' + v.caps.length + ' 能力 · ' + csNum(v.lines) + ' 行</span></div>';
      }).join('') +
      '<p style="font-size:9.5px;color:var(--ink-3);margin-top:8px">' +
      '每个能力的实现模块由 api.py 路由反查得到，op 表与自述直读源码。</p></div></div>';
  }
