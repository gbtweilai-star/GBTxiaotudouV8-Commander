  /* ── 面板 20：插件市场（蒸馏件） ── */
  function panelMarket() {
    var MK = V9.market;
    head('插件市场', { tag: '蒸馏件 · 不裸装', meta: '扫描于 ' + String(MK.scanned_at).replace('T', ' ') });
    var L = MK.local, C = MK.candidates || [];
    var kinds = L.manifest_types || {};
    var maxK = Math.max.apply(null, Object.keys(kinds).map(function (k) { return kinds[k]; }).concat([1]));
    var best = C[0] || {}, worst = C[C.length - 1] || {};

    $('chatBody').innerHTML =
      '<div class="grid3">' +
      '<div class="card"><div class="card-h"><b>本机插件全景</b> / LOCAL<span class="r">只读扫描</span></div>' +
      '<div class="card-b"><div class="grid2" style="gap:9px">' +
      '<div><div class="mono" style="font-size:21px;color:var(--neon-2)">' + L.packages + '</div>' +
      '<div class="mono dim" style="font-size:9px">包总数</div></div>' +
      '<div><div class="mono" style="font-size:21px;color:var(--neon-2)">' + L.with_manifest + '</div>' +
      '<div class="mono dim" style="font-size:9px">带 dsh 清单</div></div></div>' +
      kvRows([['官方 scope', L.official + ' 个', 'g'], ['profile', (MK.profiles || []).map(function (p) { return p.profile; }).join(', '), 'g']]) +
      '</div></div>' +
      '<div class="card"><div class="card-h"><b>清单类型</b> / MANIFEST KINDS<span class="r">' +
      Object.keys(kinds).length + ' 类</span></div><div class="card-b">' +
      Object.keys(kinds).map(function (k) {
        return bar(k, kinds[k], maxK, '');
      }).join('') + '</div></div>' +
      '<div class="card"><div class="card-h"><b>安装门</b> / GATE<span class="r">绝不裸装</span></div>' +
      '<div class="card-b">' + kvRows([['安装命令', 'dsh plugin --profile web add <pkg>', 'a'],
        ['前置授权', 'deploy_publish（主人终端发放）', 'a'],
        ['审计留痕', 'store.audit 追加一条', 'g'],
        ['本原型', '不执行安装', 'g']]) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px;line-height:1.7">' +
      'DSH 的插件就是 Cordis Loader 条目；官方清单接口只读，安装靠 profile 里 pnpm。' +
      '所以「一键安装」在本项目里必须过门、必须留痕。</p></div></div>' +
      '</div>' +

      '<div class="card" style="margin-top:10px"><div class="card-h"><b>候选包五维审查</b> / VETTING REPORT' +
      '<span class="r">事实来源：' + esc(MK.facts_from) + '</span></div><div class="card-b">' +
      C.map(function (c) {
        var tone = c.score >= 80 ? 'g' : (c.score >= 60 ? 'a' : 'r');
        return '<div style="border:1px solid var(--line);border-radius:8px;padding:10px;margin-bottom:9px">' +
          '<div style="display:flex;align-items:baseline;gap:9px;flex-wrap:wrap">' +
          '<span class="mono" style="font-size:13px;color:var(--ink)">' + esc(c.name) + '</span>' +
          '<span class="mono dim" style="font-size:10px">v' + esc(c.version) + ' · ' + esc(c.published) +
          ' · ' + esc(c.maintainer) + '</span>' +
          '<span class="mono" style="margin-left:auto;font-size:17px;color:var(--' +
          (tone === 'g' ? 'green' : tone === 'a' ? 'amber' : 'rose') + ')">' + c.score + '</span>' +
          '<span class="badge ' + (tone === 'g' ? 'live' : tone === 'a' ? 'gated' : 'gap') + '">' + esc(c.verdict) + '</span></div>' +
          '<div style="font-size:10.5px;color:var(--ink-3);margin:6px 0 8px">' + esc(c.desc) + '</div>' +
          '<div class="grid3" style="gap:7px">' +
          c.dims.map(function (d) {
            var t = d.score >= 80 ? '' : (d.score >= 60 ? 'warn' : 'rose');
            return '<div style="padding:3px 0"><div style="display:flex;gap:6px;font-size:10px;color:var(--ink-2)">' +
              '<span>' + esc(d.dim) + '</span><span class="mono" style="margin-left:auto;color:var(--neon-2)">' + d.score + '</span></div>' +
              '<span class="track" style="display:block;margin-top:4px"><i class="' + t + '" style="width:' + d.score + '%"></i></span>' +
              '<div style="font-size:9px;color:var(--ink-3);margin-top:3px;line-height:1.5">' + esc(d.why) + '</div></div>';
          }).join('') + '</div>' +
          '<div style="font-size:9.5px;color:var(--ink-3);margin-top:7px">依赖 ' + (c.deps || []).length +
          ' 个 · 生命周期脚本 ' + ((c.lifecycle || []).join('/') || '无') + ' · 许可 ' + esc(c.license || '未声明') +
          ' · 仓库 ' + esc(c.repo || '无') + '</div></div>';
      }).join('') + '</div></div>' +

      '<div class="degrade" style="margin-top:10px">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" width="14" height="14" style="color:var(--amber);flex:none" aria-hidden="true"><path d="M12 9v5M12 17h.01M10.3 3.9L2.6 17a2 2 0 001.7 3h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"/></svg>' +
      '<span><b style="color:var(--ink)">同名仿冒实测存在</b> —— 真名是 <code class="mono">dshmarket</code>（npm 上 <code class="mono">dsh-market</code> 这个包名 404）。' +
      '评分最低的 <code class="mono">' + esc(worst.name || '') + '</code> 只拿到 ' + (worst.score || 0) +
      ' 分：' + esc(((worst.dims || [])[4] || {}).why || '') + '。最高分是 <code class="mono">' +
      esc(best.name || '') + '</code> ' + (best.score || 0) + ' 分。' +
      '本项目规矩：<b style="color:var(--ink)">装之前先出报告，报告不过不进环境</b>。</span></div>' +

      '<div class="card" style="margin-top:10px"><div class="card-h"><b>蒸馏口径</b> / DISTILLATION<span class="r">GBT 版市场</span></div>' +
      '<div class="card-b"><div class="grid2" style="gap:9px">' +
      '<div>' + kvRows([['① 只读索引', '本机扫描 + 实采元数据', 'g'],
        ['② 五维评分', MK.dims.join(' / '), 'g']]) + '</div>' +
      '<div>' + kvRows([['③ 装前报告', '自动生成，不过不装', 'g'],
        ['④ 安装过门', 'run_task + 授权 + 审计', 'g']]) + '</div></div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.7">' + esc(MK.law) +
      ' —— 那个社区市场缺的正是后两条：它给的是「一键装」，本项目给的是「一键装，但先过门、留痕、可复核」。</p>' +
      '</div></div>';
  }
