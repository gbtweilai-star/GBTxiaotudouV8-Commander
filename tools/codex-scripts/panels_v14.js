  /* ══════════════════════════════════════════════════════════════════
     框架核心层 · V14 新增 10 面板
     起因：主人问「你在重新排查一遍还是丢东西」。
     前 13 版的「未进面板」清单是我手挑的 12 个目录 —— 手挑必漏。
     本版改成机器穷举：260,342 行自有代码里，连模块名都没进过交付件的有 131,283 行（50.4%）。
     本页补的是其中最要紧的：统一接口层、授权与安全策略、框架底座、omni 触手家族、部署层、
     对外桥接、技能库、镜像与乾坤底座、密钥保险箱 —— 102 个文件 / 31,000 行。
     ══════════════════════════════════════════════════════════════════ */
  var CORE = V14.core;
  var COV = V14.coverage;

  function covNum(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

  function coreFileRows(items, limit) {
    if (!items || !items.length) {
      return '<div class="statline" style="color:var(--ink-3)">本组在本次审计里没有未覆盖文件。</div>';
    }
    var shown = items.slice(0, limit || 14);
    var h = shown.map(function (m) {
      return '<div style="padding:5px 0;border-bottom:1px solid var(--line);display:flex;gap:9px;align-items:flex-start">' +
        '<span class="mono" style="font-size:9.5px;color:var(--neon-2);flex:none;width:52px;text-align:right">' +
        covNum(m.lines) + '</span>' +
        '<div style="min-width:0;flex:1">' +
        '<div class="mono" style="font-size:10.5px;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
        esc(m.f) + '</div>' +
        (m.doc ? '<p style="font-size:9.5px;color:var(--ink-3);margin:3px 0 0;line-height:1.7">' + esc(m.doc) + '</p>' : '') +
        '</div></div>';
    }).join('');
    if (items.length > shown.length) {
      var rest = items.slice(shown.length);
      h += '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">… 另 ' + rest.length +
        ' 个文件 / ' + covNum(rest.reduce(function (a, x) { return a + x.lines; }, 0)) + ' 行</p>';
    }
    return h;
  }

  function corePage(gid, navTitle) {
    var c = CORE[gid];
    head(navTitle || c.zh, { tag: gid, meta: c.n + ' 文件 · ' + covNum(c.lines) + ' 行' });
    $('chatBody').innerHTML =
      '<div class="card"><div class="card-h"><b>' + esc(c.zh) + '</b> / FRAMEWORK CORE' +
      '<span class="r">V14 新补 · 此前从未进面板</span></div><div class="card-b">' +
      '<p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' + esc(c.what) + '</p>' +
      '<div class="degrade" style="margin-top:10px"><span>' + esc(c.why) + '</span></div>' +
      '<div class="grid3" style="gap:9px;margin-top:11px">' +
      '<div><div class="mono" style="font-size:18px;color:var(--neon-2)">' + c.n + '</div>' +
      '<div class="mono dim" style="font-size:9px">文件</div></div>' +
      '<div><div class="mono" style="font-size:18px;color:var(--neon-2)">' + covNum(c.lines) + '</div>' +
      '<div class="mono dim" style="font-size:9px">代码行</div></div>' +
      '<div><div class="mono" style="font-size:18px;color:var(--rose)">0</div>' +
      '<div class="mono dim" style="font-size:9px">此前出现在交付件的次数</div></div>' +
      '</div></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>逐个文件</b> / FILES' +
      '<span class="r">按行数降序 · 摘要读自源码 docstring</span></div>' +
      '<div class="card-b">' + coreFileRows(c.files, 16) + '</div></div>';
  }

  function panelCoreApi() { corePage('api', '统一接口层'); }
  function panelCoreSec() { corePage('security', '授权与安全策略'); }
  function panelCoreBase() { corePage('base', '框架底座'); }
  function panelCoreOmni() { corePage('omni', 'omni 触手家族'); }
  function panelCoreDeploy() { corePage('deploy', '部署层'); }
  function panelCoreBridge() { corePage('bridge', '对外桥接'); }
  function panelCoreSkill() { corePage('skill', '技能库'); }
  function panelCoreMirror() { corePage('mirror', '镜像与乾坤底座'); }
  function panelCoreVault() { corePage('vault', '密钥保险箱'); }

  /* ── 面板：覆盖审计（机器判定，不是手挑） ── */
  function panelCovAudit() {
    head('源码覆盖审计', { tag: 'coverage', meta: '机器穷举 · 非手挑' });
    var dirs = Object.keys(COV.by_dir).map(function (k) {
      var v = COV.by_dir[k];
      return { k: k, n: v.n, lines: v.lines, cov: v.covered_lines,
               un: v.lines - v.covered_lines, uncov_n: v.uncov_n || 0 };
    }).filter(function (d) { return d.un > 0; })
      .sort(function (a, b) { return b.un - a.un; });
    var maxUn = dirs.length ? dirs[0].un : 1;
    var p = Math.round(100 * COV.uncovered_lines / COV.total_lines);
    $('chatBody').innerHTML = '<div class="card"><div class="card-h"><b>为什么这一版才查出来</b> / WHY NOW' +
      '<span class="r">' + esc(String(V14.meta.scanned_at).slice(0, 10)) + '</span></div><div class="card-b">' +
      '<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:8px">' +
      '<span class="mono" style="font-size:30px;color:var(--rose);line-height:1">' + covNum(COV.uncovered_lines) + '</span>' +
      '<span class="mono dim" style="font-size:12px">行自有代码，连<b>模块名</b>都没进过交付件</span></div>' +
      '<span class="track" style="display:block"><i class="rose" style="width:' + Math.max(p, 3) + '%"></i></span>' +
      '<p style="font-size:10.5px;color:var(--ink-2);margin-top:11px;line-height:1.9">' +
      'V12 那份「未进面板的 9 个板块」是<b>我手挑的目录清单</b> —— 手挑就一定会漏。' +
      '这一版改成机器穷举：枚举工作区全部自有代码文件，按目录聚合，逐个查模块名是否出现过。<br>' +
      '<b>方法</b>：' + esc(COV.method) + '<br>' +
      '<span style="color:var(--amber)"><b>判据的诚实边界</b>：' + esc(COV.caveat) + '</span></p>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px">自检：' + esc(COV.selfcheck) + '</p>' +
      '</div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>按目录：未覆盖行数</b> / UNCOVERED BY DIR' +
      '<span class="r">共 ' + dirs.length + ' 个目录有缺口</span></div><div class="card-b">' +
      dirs.slice(0, 22).map(function (d) {
        var w = Math.round(100 * d.un / maxUn);
        return '<div style="padding:3px 0"><div style="display:flex;align-items:baseline;gap:8px;font-size:10.5px">' +
          '<span class="mono" style="color:var(--ink-2);min-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
          esc(d.k) + '</span>' +
          '<span style="color:var(--ink-3);font-size:9.5px">' + d.uncov_n + ' 文件</span>' +
          '<span class="mono" style="margin-left:auto;font-size:10px;color:' +
          (d.cov === 0 ? 'var(--rose)' : 'var(--amber)') + '">未覆盖 ' + covNum(d.un) + ' / ' + covNum(d.lines) + '</span></div>' +
          '<span class="track" style="display:block;margin-top:3px"><i class="' +
          (d.cov === 0 ? 'rose' : 'warn') + '" style="width:' + Math.max(w, 2) + '%"></i></span></div>';
      }).join('') + '</div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>零覆盖目录</b> / ZERO COVERAGE' +
      '<span class="r">' + COV.zero_coverage.length + ' 个整块没进过交付件</span></div><div class="card-b">' +
      COV.zero_coverage.map(function (k) {
        var v = COV.by_dir[k] || {};
        return '<div class="statline"><span class="led r"></span>' +
          '<span class="mono" style="font-size:10.5px">' + esc(k) + '</span>' +
          '<span class="n mono" style="font-size:9.5px">' + (v.n || 0) + ' 文件 · ' + covNum(v.lines || 0) + ' 行</span></div>';
      }).join('') + '</div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>V14 本版补了什么</b> / WHAT V14 PATCHES</div>' +
      '<div class="card-b">' +
      Object.keys(CORE).sort(function (a, b) { return CORE[b].lines - CORE[a].lines; }).map(function (g) {
        var c = CORE[g];
        return '<div class="statline"><span class="led g"></span>' + esc(c.zh) +
          '<span class="n mono" style="font-size:9.5px">' + c.n + ' 文件 · ' + covNum(c.lines) + ' 行</span></div>';
      }).join('') +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.8">' +
      '本版补的 ' + Object.keys(CORE).reduce(function (a, g) { return a + CORE[g].lines; }, 0).toLocaleString() +
      ' 行，占未覆盖总量的一部分 —— <b>不是全部</b>。剩下的最大两块：' +
      '<span class="mono">.openclaw/tmp</span>（431 文件 / 22,888 行，多数是另一个钱包项目的临时工作文件与一次性补丁脚本）与 ' +
      '<span class="mono">gbt_allinone/store</span>（237 文件，多为镜像/时间线快照的生成物）。' +
      '这两块的性质与「框架自有源码」不同，<b>我没有把它们硬凑成面板充数</b>。</p></div></div>';
  }
