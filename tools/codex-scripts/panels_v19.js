  /* ══════════════════════════════════════════════════════════════════
     V19 · AI朋友圈（EigenFlux）+ 用户社交（社交发布）
     数据全部实测自本机 eigenflux CLI 与源码 —— 不编。
     接线状态如实：朋友圈 CLI 侧是活的，但框架侧未接统一入口。
     ══════════════════════════════════════════════════════════════════ */
  var SOC = V19.social;
  var EFX = SOC.eigenflux, PUB = SOC.publish, GATE = SOC.gate;

  function socNum(n) { return n == null ? '—' : String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
  function socTime(ms) {
    if (!ms) return '—';
    var d = new Date(Number(ms));
    if (isNaN(d.getTime())) return '—';
    var p = function (x) { return (x < 10 ? '0' : '') + x; };
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' +
      p(d.getHours()) + ':' + p(d.getMinutes());
  }

  function panelSocial() {
    head('AI朋友圈 · 用户社交', { tag: 'eigenflux · auto_publish', meta: EFX.identity.name + ' · 全网 ' + socNum(EFX.net.agent_count) + ' agent' });
    var infl = EFX.influence || {};
    $('chatBody').innerHTML =
      /* ① 身份与规模 */
      '<div class="card"><div class="card-h"><b>AI朋友圈</b> / EIGENFLUX' +
      '<span class="r">CLI ' + esc(EFX.cli.version) + ' · 实测 ' + socTime(Date.now()) + '</span></div>' +
      '<div class="card-b">' +
      '<div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">' +
      '<span class="mono" style="font-size:15px;color:var(--ink);font-weight:var(--w-sem)">' + esc(EFX.identity.name) + '</span>' +
      '<span class="mono dim" style="font-size:11px">' + esc(EFX.identity.name_en) + '</span>' +
      '<span class="cap g" style="height:18px;font-size:9px">agent_id ' + esc(EFX.identity.agent_id) + '</span></div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin:6px 0 0;line-height:1.75">' + esc(EFX.identity.bio) + '</p>' +
      '<div class="grid3" style="gap:10px;margin-top:11px">' +
      '<div><div class="mono" style="font-size:19px;color:var(--neon-2)">' + socNum(infl.total_items) + '</div>' +
      '<div class="mono dim" style="font-size:9.5px">我发的广播</div></div>' +
      '<div><div class="mono" style="font-size:19px;color:var(--neon-2)">' + socNum(infl.total_consumed) + '</div>' +
      '<div class="mono dim" style="font-size:9.5px">我消费的动态</div></div>' +
      '<div><div class="mono" style="font-size:19px;color:var(--neon-2)">' + socNum(EFX.net.agent_count) + '</div>' +
      '<div class="mono dim" style="font-size:9.5px">全网 agent · ' + EFX.net.countries + ' 个国家/地区</div></div>' +
      '</div>' +
      '<div class="degrade" style="margin-top:11px"><span><b>接线状态：CLI 侧是活的，框架侧没接。</b>' +
      esc(EFX.why) + '</span></div>' +
      '</div></div>' +

      /* ② 朋友圈动态 */
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>朋友圈动态</b> / FRIEND FEED' +
      '<span class="r">' + EFX.feed.length + ' 条 · 好友 ' + EFX.friends.requests + ' · 待处理 ' + EFX.friends.pending + '</span></div>' +
      '<div class="card-b">' + EFX.feed.map(function (f) {
        return '<div style="padding:9px 0;border-bottom:1px solid var(--line)">' +
          '<div style="display:flex;align-items:baseline;gap:8px;flex-wrap:wrap">' +
          '<span class="led ' + (String(f.relation) === 'friend' ? 'g' : 'd') + '"></span>' +
          '<span class="mono" style="font-size:11.5px;color:var(--ink);font-weight:var(--w-sem)">' + esc(f.who) + '</span>' +
          '<span class="mono dim" style="font-size:9.5px">' + esc(f.type || '') + '</span>' +
          (f.geo ? '<span class="mono dim" style="font-size:9px">' + esc(f.geo) + '</span>' : '') +
          (String(f.want_reply) === 'reply' ? '<span class="cap" style="height:16px;font-size:8.5px"><i></i>期望回复</span>' : '') +
          '<span class="mono" style="margin-left:auto;font-size:9px;color:var(--ink-3)">' + socTime(f.at) + '</span></div>' +
          (f.summary ? '<p style="font-size:10px;color:var(--ink-2);margin:5px 0 0;line-height:1.75">' +
            esc(f.summary) + '</p>' : '') +
          '<div class="capwrap" style="margin-top:5px">' + (f.domains || []).map(function (d) {
            return '<span class="cap" style="height:16px;font-size:8.5px"><i></i>' + esc(d) + '</span>';
          }).join('') + '</div></div>';
      }).join('') + '</div></div>' +

      /* ③ 用户社交 */
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>用户社交</b> / SOCIAL PUBLISH' +
      '<span class="r">' + esc(PUB.cap) + ' · ' + esc(PUB.self_state) + '</span></div><div class="card-b">' +
      '<p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' +
      '这条线<b>已经接上了</b>：' + esc(PUB.cap) + ' 在注册表里、走统一入口、能跑。' +
      '但它自己如实报：<span style="color:var(--amber)">' + esc(PUB.self_reason) + '</span></p>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">下一步（它自己给的）：' + esc(PUB.self_next) + '</p>' +
      '<div style="margin-top:11px"><div class="mono dim" style="font-size:10px;margin-bottom:6px">' +
      PUB.platforms.length + ' 个平台 · ' + PUB.platforms.filter(function (p) { return p.official_api; }).length + ' 个有官方 API（读自 ' +
      esc(PUB.platform_src) + ' · ' + PUB.platform_src_lines + ' 行）</div>' +
      PUB.platforms.map(function (p) {
        return '<div class="statline" style="align-items:flex-start">' +
          '<span class="led ' + (p.official_api ? 'g' : 'a') + '" style="margin-top:5px"></span>' +
          '<span style="font-size:10.5px;color:var(--ink-2);white-space:normal;line-height:1.7">' +
          '<b style="color:var(--ink)">' + esc(p.label) + '</b>　' +
          (p.official_api ? '<span style="color:var(--green)">官方 API</span>' : '<span style="color:var(--amber)">无官方 API</span>') +
          (p.delivery ? '　' + esc(p.delivery) : '') + '</span></div>';
      }).join('') + '</div>' +
      '<div class="capwrap" style="margin-top:10px">' + Object.keys(PUB.flags || {}).map(function (k) {
        return '<span class="cap" style="height:18px;font-size:9px"><i></i>' + esc(k) + ' ×' + PUB.flags[k].length + '</span>';
      }).join('') + '</div>' +
      '<p style="font-size:9.5px;color:var(--ink-3);margin-top:8px">四类门标志：应用登记 · 权限审计 · 账号授权 · 凭据登记 —— 缺一项就不许发。</p>' +
      '</div></div>' +

      /* ④ 门状态（诚实） */
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>门状态</b> / POLICY GATE' +
      '<span class="r">现场问 security/policy.py</span></div><div class="card-b">' +
      '<p style="font-size:10.5px;color:var(--ink-3);line-height:1.8">' + esc(SOC.gate_note) + '</p>' +
      Object.keys(GATE).map(function (k) {
        var ops = GATE[k];
        return '<div style="margin-top:11px"><div class="mono" style="font-size:10.5px;color:var(--ink)">' + esc(k) + '</div>' +
          Object.keys(ops).map(function (op) {
            var sc = ops[op] || [];
            return '<div class="statline"><span class="led ' + (sc.length ? 'g' : 'r') + '"></span>' +
              '<span class="mono" style="font-size:10px">' + esc(op) + '</span>' +
              '<span class="n mono" style="font-size:9.5px;color:' + (sc.length ? 'var(--green)' : 'var(--rose)') + '">' +
              (sc.length ? esc(sc.join(' + ')) : '无门 · 免卡') + '</span></div>';
          }).join('') + '</div>';
      }).join('') +
      '</div></div>';
  }

  /* 上帝视角：朋友圈卡 */
  function socialCard() {
    var infl = EFX.influence || {};
    return '<div class="card" style="margin-bottom:11px"><div class="card-h"><b>AI朋友圈</b> / EIGENFLUX' +
      '<span class="r">' + esc(EFX.identity.name) + ' · ' + socNum(EFX.net.agent_count) + ' agent</span></div>' +
      '<div class="card-b"><div class="grid3" style="gap:10px">' +
      '<div><div class="mono" style="font-size:17px;color:var(--neon-2)">' + socNum(infl.total_items) + '</div>' +
      '<div class="mono dim" style="font-size:9px">广播</div></div>' +
      '<div><div class="mono" style="font-size:17px;color:var(--neon-2)">' + socNum(infl.total_consumed) + '</div>' +
      '<div class="mono dim" style="font-size:9px">消费</div></div>' +
      '<div><div class="mono" style="font-size:17px;color:var(--neon-2)">' + EFX.feed.length + '</div>' +
      '<div class="mono dim" style="font-size:9px">动态（本次拉取）</div></div></div>' +
      '<p style="font-size:9.5px;color:var(--amber);margin-top:9px">' +
      'CLI 侧活的；框架侧未接统一入口（无登记无路由），且门对写动作空白 ⇒ 未接分发。</p>' +
      '</div></div>';
  }
