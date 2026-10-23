  /* ── 面板 10：万能插 ── */
  function panelPlug() {
    $('composer').style.display = 'none';
    var PL = V7.plug;
    $('chatTitle').textContent = '万能插';
    $('chatTag').textContent = PL.workflow_count + ' 个工作流';
    $('chatMeta').textContent = '实测于 ' + esc(String(PL.probed_at).replace('T', ' '));
    if (!st.wf) st.wf = (PL.workflows.filter(function (w) { return w.node_count === Math.max.apply(null, PL.workflows.map(function (x) { return x.node_count; })); })[0] || PL.workflows[0] || {}).name;
    var cur = PL.workflows.filter(function (w) { return w.name === st.wf; })[0] || PL.workflows[0] || { nodes: [] };
    var runs = PL.runs || [];

    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>工作流定义</b> / WORKFLOWS<span class="r">' +
      PL.workflow_count + ' 个 · 真读数</span></div><div class="card-b">' +
      PL.workflows.map(function (w) {
        var on = w.name === cur.name;
        return '<button class="routebar" data-wf="' + esc(w.name) + '" style="width:100%;text-align:left;border-bottom:1px dashed var(--line);background:' +
          (on ? 'var(--neon-dim)' : 'transparent') + ';border-radius:4px;padding:6px 8px">' +
          '<code style="flex:1">' + esc(w.name) + '</code>' +
          '<span class="alt">' + w.node_count + ' 节点</span></button>';
      }).join('') +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.7">出口说明：' +
      esc(PL.data_outlet) + '</p></div></div>' +

      '<div class="card"><div class="card-h"><b>传输算子</b> / OPERATORS<span class="r">' +
      PL.operators.length + ' 个纯变换</span></div><div class="card-b">' +
      '<div class="capwrap">' + PL.operators.map(function (o) {
        return '<span class="cap g"><i></i>' + esc(o) + '</span>';
      }).join('') + '</div>' +
      '<div class="out" style="margin-top:9px;max-height:120px">' +
      'unique [3,1,3,2,1] → ' + esc(JSON.stringify((PL.real_runs.unique || {}).data)) + '\n' +
      'stats  [1,2,3,4,5] → ' + esc(JSON.stringify((PL.real_runs.stats || {}).data)) + '</div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:7px">上面两行是真实执行结果（transfer 直调）</p></div></div>' +
      '</div>' +

      '<div class="card" style="margin-top:2px"><div class="card-h"><b>依赖图</b> / DAG' +
      '<span class="r">' + esc(cur.name) + ' · ' + (cur.nodes || []).length + ' 节点 · 分层并行</span></div>' +
      '<div class="card-b"><div id="dag" style="overflow-x:auto"></div></div></div>' +

      '<div class="card" style="margin-top:2px"><div class="card-h"><b>运行记录</b> / RUNS' +
      '<span class="r">最近 ' + runs.length + ' 条 · 真实</span></div><div class="card-b">' +
      '<div class="trace" style="grid-template-columns:1fr 74px 1fr 62px">' +
      runs.map(function (r) {
        var okr = r.status === 'ok';
        var nd = r.nodes || {};
        var nds = Object.keys(nd).map(function (k) { return k + ':' + nd[k]; }).join(' ');
        return '<span class="nm" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(r.run_id) + '</span>' +
          '<span class="mono" style="font-size:10px;color:' + (okr ? 'var(--green)' : 'var(--rose)') + '">' + esc(r.status) + '</span>' +
          '<span class="mono dim" style="font-size:9.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(nds) + '</span>' +
          '<span class="ms">' + esc(r.elapsed_s) + 's</span>';
      }).join('') + '</div>' +
      '<div class="statline" style="margin-top:9px;border-top:1px dashed var(--line);padding-top:8px">' +
      '<span class="led a"></span>定时任务<span class="n">' + (PL.schedules || 0) + ' 个（sched_status 实测）</span></div>' +
      '</div></div>';
    drawDag(cur);
  }

  function drawDag(wf) {
    var el = $('dag'); if (!el) return;
    var nodes = (wf.nodes || []);
    if (!nodes.length) { el.innerHTML = '<div class="empty"><h4>该工作流没有节点</h4></div>'; return; }
    var byId = {};
    nodes.forEach(function (n) { byId[n.id] = n; });
    var depth = {};
    function d(id) {
      if (depth[id] != null) return depth[id];
      var n = byId[id]; if (!n) return 0;
      var deps = n.depends_on || [];
      depth[id] = deps.length ? Math.max.apply(null, deps.map(d)) + 1 : 0;
      return depth[id];
    }
    nodes.forEach(function (n) { d(n.id); });
    var layers = {};
    nodes.forEach(function (n) { (layers[depth[n.id]] = layers[depth[n.id]] || []).push(n); });
    var CW = 118, CH = 30, GX = 10, GY = 22, PAD = 14;
    var maxW = Math.max.apply(null, Object.keys(layers).map(function (k) { return layers[k].length; }));
    var maxD = Math.max.apply(null, Object.keys(layers).map(Number));
    var W = PAD * 2 + maxW * CW + (maxW - 1) * GX;
    var H = PAD * 2 + (maxD + 1) * (CH + GY);
    var pos = {}, o = [];
    Object.keys(layers).forEach(function (k) {
      var L = layers[k], i;
      var rowW = L.length * CW + (L.length - 1) * GX;
      var x0 = (W - rowW) / 2, y = PAD + Number(k) * (CH + GY);
      L.forEach(function (n, i2) {
        pos[n.id] = { x: x0 + i2 * (CW + GX), y: y };
      });
    });
    nodes.forEach(function (n) {
      (n.depends_on || []).forEach(function (dp) {
        var a = pos[dp], b = pos[n.id]; if (!a || !b) return;
        var x1 = a.x + CW / 2, y1 = a.y + CH, x2 = b.x + CW / 2, y2 = b.y;
        var my = (y1 + y2) / 2;
        o.push('<path d="M' + x1 + ' ' + y1 + ' C' + x1 + ' ' + my + ',' + x2 + ' ' + my + ',' + x2 + ' ' + y2 +
          '" fill="none" stroke="var(--line-hot)" stroke-width="1.2" class="flow"/>');
      });
    });
    nodes.forEach(function (n) {
      var p = pos[n.id];
      o.push('<g><rect x="' + p.x + '" y="' + p.y + '" width="' + CW + '" height="' + CH + '" rx="5" fill="var(--panel-2)" stroke="var(--line-hot)"/>' +
        '<text x="' + (p.x + 8) + '" y="' + (p.y + 13) + '" fill="var(--ink)" font-family="var(--mono)" font-size="9.5">' + esc(n.id) + '</text>' +
        '<text x="' + (p.x + 8) + '" y="' + (p.y + 24) + '" fill="var(--ink-3)" font-family="var(--mono)" font-size="8.5">' + esc(n.kind) + '</text></g>');
    });
    el.innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:' + W + 'px;max-width:none;height:auto;display:block" role="img" ' +
      'aria-label="工作流 ' + esc(wf.name) + ' 的依赖图，共 ' + nodes.length + ' 个节点">' + o.join('') + '</svg>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:7px">层 = 依赖深度；同层节点并行执行（wf_run 分层并行）。节点下方等宽字为真实 kind。</p>';
  }

  /* ── 面板 11：亿万触手 ── */
  function panelTentacle() {
    $('composer').style.display = 'none';
    var T = V7.tentacle;
    $('chatTitle').textContent = '亿万触手';
    $('chatTag').textContent = T.sections_total + ' 项 · 三通道';
    $('chatMeta').textContent = '实测于 ' + esc(String(T.diagnose.checked_at || '').replace('T', ' '));
    var C = T.coverage, doms = C.by_domain || {};
    var ICON = {
      eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
      ear: '<path d="M8 20v-2a4 4 0 014-4 3 3 0 003-3V9a5 5 0 00-10 0"/><path d="M12 8a2 2 0 00-2 2"/>',
      hand: '<path d="M9 11V5a1.6 1.6 0 013.2 0v6M12.2 11V4.2a1.6 1.6 0 013.2 0V11M15.4 11.4V6.6a1.6 1.6 0 013.2 0V15a6 6 0 01-6 6h-1.6a6 6 0 01-6-6v-2.6a1.6 1.6 0 013.2 0"/>'
    };
    $('chatBody').innerHTML =
      '<div class="grid3">' + T.channels.map(function (c) {
        return '<div class="stagecard on"><div class="sh">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" width="14" height="14" style="color:var(--neon-2)" aria-hidden="true">' +
          (ICON[c.icon] || ICON.eye) + '</svg>' + esc(c.channel) +
          '<span class="k">CHANNEL</span></div>' +
          '<div class="sb" style="font-size:10.5px;line-height:1.7">' + esc(c.text) + '</div></div>';
      }).join('') + '</div>' +

      '<div class="grid2" style="margin-top:10px">' +
      '<div class="card"><div class="card-h"><b>自诊断</b> / DIAGNOSE' +
      '<span class="r">' + (T.diagnose.ok ? 'ok' : '异常') + '</span></div><div class="card-b">' +
      line(T.diagnose.eye_error ? 'r' : 'g', '眼睛', T.diagnose.eye_error ? esc(T.diagnose.eye_error) : '正常') +
      T.diagnose.deps.map(function (d) {
        return line(d.ok ? 'g' : 'r', d.name, esc(d.role));
      }).join('') +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">总纲方法 ' + T.diagnose.manifest_methods +
      ' · 邻域 ' + T.diagnose.neighborhoods + ' 个</p></div></div>' +

      '<div class="card"><div class="card-h"><b>意图覆盖</b> / COVERAGE<span class="r">真读数</span></div><div class="card-b">' +
      '<div class="mono" style="font-size:24px;color:var(--neon-2);letter-spacing:-0.02em">' + esc(C.pct) + '%</div>' +
      '<div class="statline"><span class="led g"></span>已覆盖动作<span class="n">' + C.covered + '/' + C.denominator + '</span></div>' +
      '<div class="statline"><span class="led g"></span>未覆盖<span class="n">' + C.uncovered + '</span></div>' +
      '<div class="statline"><span class="led g"></span>地图幽灵<span class="n">' + C.ghosts + '</span></div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px;line-height:1.7">分母来源：' + esc(C.denominator_source) + '</p>' +
      '</div></div></div>' +

      '<div class="card" style="margin-top:10px"><div class="card-h"><b>十域触手分布</b> / DOMAINS' +
      '<span class="r">' + C.domains + ' 个域 · 真身 ' + C.real_methods + ' 个方法</span></div><div class="card-b">' +
      '<div class="capwrap">' + Object.keys(doms).map(function (k) {
        return '<span class="cap g" title="关键能力 ' + esc(doms[k].key_capability) + '"><i></i>' +
          esc(k) + ' ' + doms[k].methods + '</span>';
      }).join('') + '</div></div></div>' +

      '<div class="card" style="margin-top:10px"><div class="card-h"><b>能力分段</b> / SECTIONS' +
      '<span class="r">' + T.sections.length + ' 段 · 合计 ' + T.sections_total + ' 项</span></div><div class="card-b">' +
      T.sections.map(function (s) {
        return '<div style="display:flex;align-items:center;gap:8px;padding:3px 0;font-size:11px;color:var(--ink-2)">' +
          '<span style="width:64px;font-family:var(--mono);font-size:10.5px;color:var(--ink)">' + esc(s.name) + '</span>' +
          '<span class="track" style="flex:1"><i style="width:' + Math.round(100 * s.count / 12) + '%"></i></span>' +
          '<span class="mono dim" style="font-size:10px;width:34px;text-align:right">' + s.count + '</span></div>';
      }).join('') + '</div></div>' +

      '<div class="card" style="margin-top:10px"><div class="card-h"><b>覆盖审计 · 八短板</b> / AUDIT' +
      '<span class="r">' + esc(T.audit.by_group || '') + '</span></div><div class="card-b">' +
      (T.audit.matrix || []).map(function (r) {
        var exp = r.expected_modules || 0, rep = r.reportable_modules || 0;
        var pct = exp ? Math.round(100 * rep / exp) : 0;
        var tone = pct >= 80 ? '' : (pct >= 40 ? 'warn' : 'rose');
        return '<div style="padding:5px 0;border-bottom:1px dashed var(--line)">' +
          '<div style="display:flex;align-items:baseline;gap:8px;font-size:11px;color:var(--ink-2)">' +
          '<span style="font-family:var(--mono);font-size:10.5px;color:var(--ink)">' + esc(r.group) + '</span>' +
          '<span style="font-size:10px;color:var(--ink-3)">' + esc(r.short_board) + '</span>' +
          '<span class="mono" style="margin-left:auto;font-size:10.5px;color:var(--neon-2)">' + rep + '/' + exp + '</span></div>' +
          '<span class="track" style="display:block;margin-top:5px"><i class="' + tone + '" style="width:' + pct + '%"></i></span></div>';
      }).join('') +
      '<div style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.8">' +
      '上报模块 ' + esc(T.audit.modules || '') + '<br>' +
      (T.audit.gaps || []).map(function (g) { return '· ' + esc(g); }).join('<br>') + '<br>' +
      '取证：' + esc(T.audit.as_of || '') + '</div></div></div>' +

      '<div class="degrade" style="margin-top:10px">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" width="14" height="14" style="color:var(--amber);flex:none" aria-hidden="true"><path d="M12 9v5M12 17h.01M10.3 3.9L2.6 17a2 2 0 001.7 3h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"/></svg>' +
      '<span>触手能力清单（<code class="mono">tentacle op=caps</code>）实测被拦：缺 <code class="mono">' +
      esc((T.caps_gate.missing || []).join(' + ')) + '</code>。诊断与审计是只读的，照常可看；真要动手才需要这道门。</span></div>';

    var wfBtns = $('chatBody').querySelectorAll('[data-wf]');
    Array.prototype.forEach.call(wfBtns, function (b) {
      b.addEventListener('click', function () { st.wf = b.dataset.wf; panelPlug(); });
    });
  }
