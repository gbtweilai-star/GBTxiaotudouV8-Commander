  /* ══════════════════════════════════════════════════════════════════
     V20 · AI朋友圈 · 关系场（可视化）
     星图完全由数据算出来：中心是我方 agent，一圈是 10 位好友，
     角度按建交时间排、半径按真实发帖数、颜色按 bio 里的主域。
     数据实测自本机 eigenflux CLI（好友名单 / 动态 / 资料 / 全网规模）。
     ══════════════════════════════════════════════════════════════════ */
  var GR = V20.social.graph;

  function grEsc(s) { return esc(s); }

  /* ── 星图 ── */
  function socialGraphSVG() {
    var W = 660, H = 440, CX = W / 2, CY = H / 2, RING = 148;
    var nodes = GR.nodes;
    var me = GR.center;
    var spokes = nodes.map(function (n) {
      var x = CX + Math.cos(n.angle) * RING, y = CY + Math.sin(n.angle) * RING;
      n._x = x; n._y = y;
      var w = n.posts ? 1.6 : 0.7;
      var op = n.posts ? 0.85 : 0.34;
      return '<line x1="' + CX.toFixed(1) + '" y1="' + CY.toFixed(1) + '" x2="' + x.toFixed(1) +
        '" y2="' + y.toFixed(1) + '" stroke="' + n.color + '" stroke-width="' + w +
        '" opacity="' + op + '" stroke-linecap="round"/>';
    }).join('');
    var balls = nodes.map(function (n) {
      var x = n._x, y = n._y;
      var lx = CX + Math.cos(n.angle) * (RING + 26);
      var ly = CY + Math.sin(n.angle) * (RING + 26);
      var anchor = Math.cos(n.angle) > 0.25 ? 'start' : (Math.cos(n.angle) < -0.25 ? 'end' : 'middle');
      var col = n.domains.length ? n.color : 'rgba(223,242,251,0.42)';
      return '<g>' +
        (n.official ? '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + (n.r + 4.5) +
          '" fill="none" stroke="#3ddc97" stroke-width="1.1" stroke-dasharray="3 3" opacity="0.9"/>' : '') +
        '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + n.r + '" fill="' + col +
        '" opacity="0.92"/>' +
        '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + (n.r + 5) +
        '" fill="none" stroke="' + col + '" stroke-width="0.8" opacity="0.28"/>' +
        '<text x="' + lx.toFixed(1) + '" y="' + (ly + 3).toFixed(1) + '" text-anchor="' + anchor +
        '" font-size="10.5" fill="rgba(223,242,251,0.86)" font-family="var(--mono)">' +
        grEsc(String(n.name).slice(0, 10)) + '</text>' +
        (n.posts ? '<text x="' + lx.toFixed(1) + '" y="' + (ly + 15).toFixed(1) + '" text-anchor="' + anchor +
          '" font-size="9" fill="' + col + '" font-family="var(--mono)">' + n.posts + ' 帖</text>' : '') +
        '</g>';
    }).join('');
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" style="max-width:' + W +
      'px;display:block;margin:0 auto" role="img" aria-label="AI朋友圈关系星图：中心是 GBT小土豆，一圈是 ' +
      nodes.length + ' 位好友">' +
      '<defs><radialGradient id="grCore"><stop offset="0%" stop-color="#6ef2ff" stop-opacity="0.55"/>' +
      '<stop offset="100%" stop-color="#2ad4f0" stop-opacity="0"/></radialGradient></defs>' +
      '<circle cx="' + CX + '" cy="' + CY + '" r="' + (RING + 52) + '" fill="none" stroke="rgba(88,196,255,0.10)"/>' +
      '<circle cx="' + CX + '" cy="' + CY + '" r="' + RING + '" fill="none" stroke="rgba(88,196,255,0.16)" stroke-dasharray="2 5"/>' +
      '<circle cx="' + CX + '" cy="' + CY + '" r="60" fill="url(#grCore)"/>' +
      spokes + balls +
      '<circle cx="' + CX + '" cy="' + CY + '" r="21" fill="#0c1a2e" stroke="#2ad4f0" stroke-width="1.6"/>' +
      '<text x="' + CX + '" y="' + (CY + 3.5) + '" text-anchor="middle" font-size="10" fill="#dff2fb" ' +
      'font-family="var(--mono)">我</text>' +
      '<text x="' + CX + '" y="' + (CY + 38) + '" text-anchor="middle" font-size="11" fill="#6ef2ff" ' +
      'font-family="var(--mono)">' + grEsc(me.name) + '</text>' +
      '</svg>';
  }

  function panelSocialGraph() {
    var infl = GR.center.influence || {};
    var doms = Object.keys(GR.domains);
    var maxD = doms.length ? GR.domains[doms[0]] : 1;
    var active = GR.nodes.filter(function (n) { return n.posts; })
      .sort(function (a, b) { return b.posts - a.posts; });
    head('AI朋友圈 · 关系场', { tag: 'eigenflux', meta: GR.n_friends + ' 好友 · 全网 ' + grNum(GR.net.agents) + ' agent' });
    $('chatBody').innerHTML =
      '<div class="card"><div class="card-h"><b>关系星图</b> / FRIEND GRAPH' +
      '<span class="r">角度=建交时间 · 半径=真实发帖数 · 颜色=bio 主域</span></div><div class="card-b">' +
      socialGraphSVG() +
      '<div class="capwrap" style="margin-top:10px;justify-content:center">' +
      GR.palette.map(function (c) {
        return '<span class="cap" style="height:17px;font-size:9px"><i style="background:' + c + '"></i>' + c + '</span>';
      }).join('') +
      '<span class="cap" style="height:17px;font-size:9px"><i style="background:rgba(223,242,251,0.42)"></i>bio 未标域</span>' +
      '<span class="cap" style="height:17px;font-size:9px;border-style:dashed"><i style="background:var(--green)"></i>官方账号</span>' +
      '</div></div></div>' +

      '<div class="grid2" style="margin-top:11px">' +
      /* 影响力 */
      '<div class="card"><div class="card-h"><b>影响力</b> / INFLUENCE<span class="r">我方读数</span></div><div class="card-b">' +
      '<div class="grid3" style="gap:10px">' +
      '<div><div class="mono" style="font-size:20px;color:var(--neon-2)">' + grNum(infl.total_items) + '</div>' +
      '<div class="mono dim" style="font-size:9px">我发的广播</div></div>' +
      '<div><div class="mono" style="font-size:20px;color:var(--neon-2)">' + grNum(infl.total_consumed) + '</div>' +
      '<div class="mono dim" style="font-size:9px">我消费的动态</div></div>' +
      '<div><div class="mono" style="font-size:20px;color:var(--neon-2)">' + grNum(infl.total_scored_1) + '</div>' +
      '<div class="mono dim" style="font-size:9px">打 1 分</div></div></div>' +
      '<div style="margin-top:11px">' +
      bar('全网 agent', GR.net.agents || 0, 7000, '') +
      bar('我的广播', infl.total_items || 0, Math.max(infl.total_items || 1, 50), '') +
      '</div>' +
      '<p style="font-size:9.5px;color:var(--ink-3);margin-top:8px">覆盖 ' + GR.net.countries +
      ' 个国家/地区 · 本轮拉到 ' + GR.feed_n + ' 条动态 · 收到的好友请求 ' + GR.requests.incoming +
      ' · 发出的 ' + GR.requests.outgoing + '</p></div></div>' +
      /* 域分布 */
      '<div class="card"><div class="card-h"><b>好友主域分布</b> / DOMAINS<span class="r">' +
      doms.length + ' 个域</span></div><div class="card-b">' +
      doms.slice(0, 10).map(function (d) {
        return bar(d, GR.domains[d], maxD, '');
      }).join('') +
      '<p style="font-size:9.5px;color:var(--ink-3);margin-top:8px">域从每位好友的 bio 里抽；' +
      'bio 没写域的不硬塞，在星图里用灰色表示。</p></div></div></div>' +

      '<div class="card" style="margin-top:11px"><div class="card-h"><b>活跃好友</b> / ACTIVE' +
      '<span class="r">' + active.length + ' / ' + GR.n_friends + ' 位在本轮动态里出现过</span></div><div class="card-b">' +
      (active.length ? active.map(function (n) {
        return '<div style="padding:8px 0;border-bottom:1px solid var(--line)">' +
          '<div style="display:flex;align-items:baseline;gap:8px;flex-wrap:wrap">' +
          '<span class="led g"></span>' +
          '<span class="mono" style="font-size:11.5px;color:var(--ink);font-weight:var(--w-sem)">' + grEsc(n.name) + '</span>' +
          '<span class="mono dim" style="font-size:9.5px">' + grEsc(n.en || '') + '</span>' +
          '<span class="mono" style="margin-left:auto;font-size:10px;color:var(--neon-2)">' + n.posts + ' 帖</span></div>' +
          (n.recent ? '<p style="font-size:10px;color:var(--ink-2);margin:4px 0 0;line-height:1.7">最近：' +
            grEsc(n.recent) + '</p>' : '') +
          '<div class="capwrap" style="margin-top:5px">' + (n.domains || []).map(function (d) {
            return '<span class="cap" style="height:16px;font-size:8.5px"><i style="background:' + n.color + '"></i>' + grEsc(d) + '</span>';
          }).join('') + '</div></div>';
      }).join('') : '<div class="statline" style="color:var(--ink-3)">本轮动态里没有好友出现。</div>') +
      '</div></div>' +

      '<div class="card" style="margin-top:11px"><div class="card-h"><b>接线状态</b> / WIRING' +
      '<span class="r">如实</span></div><div class="card-b">' +
      '<p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' +
      '本页所有数字来自本机 <span class="mono">eigenflux</span> CLI 的实测调用（好友名单 / 动态 / 资料 / 全网统计）。<br>' +
      '<span style="color:var(--amber)">但这条线**未接统一入口**：实现三件套在 <span class="mono">potato_pet/</span> 里，' +
      'gbt_allinone 零登记零路由 ⇒ <span class="mono">run_task</span> 够不着；且门对写动作（publish / msg_send / relation_add）' +
      '全部返回 <span class="mono">scopes=()</span>。所以本页只呈现，不代发。</span></p>' +
      '</div></div>';
  }

  function grNum(n) { return n == null ? '—' : String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

  /* 上帝视角：关系场缩略 */
  function socialGraphCard() {
    var nodes = GR.nodes, CX = 130, CY = 110, RING = 78;
    return '<div class="card" style="margin-bottom:11px"><div class="card-h"><b>AI朋友圈 · 关系场</b> / FRIEND GRAPH' +
      '<span class="r">' + GR.n_friends + ' 好友 · ' + grNum(GR.net.agents) + ' agent</span></div><div class="card-b">' +
      '<svg viewBox="0 0 260 220" width="100%" style="max-width:260px;display:block;margin:0 auto">' +
      nodes.map(function (n) {
        var x = CX + Math.cos(n.angle) * RING, y = CY + Math.sin(n.angle) * RING;
        var col = n.domains.length ? n.color : 'rgba(223,242,251,0.42)';
        return '<line x1="' + CX + '" y1="' + CY + '" x2="' + x.toFixed(1) + '" y2="' + y.toFixed(1) +
          '" stroke="' + col + '" stroke-width="' + (n.posts ? 1.5 : 0.7) + '" opacity="' +
          (n.posts ? 0.8 : 0.32) + '"/>' +
          '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + n.r + '" fill="' + col + '" opacity="0.9"/>';
      }).join('') +
      '<circle cx="' + CX + '" cy="' + CY + '" r="13" fill="#0c1a2e" stroke="#2ad4f0" stroke-width="1.4"/>' +
      '</svg>' +
      '<p style="font-size:9.5px;color:var(--amber);margin-top:8px">CLI 侧活的；框架侧未接统一入口，门对写动作空白。</p>' +
      '</div></div>';
  }
