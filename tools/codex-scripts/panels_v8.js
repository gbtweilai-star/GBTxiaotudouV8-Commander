  /* ── 缺口补板 · 共用小件 ── */
  function kvRows(pairs) {
    return pairs.map(function (r) {
      return '<div class="statline"><span class="led ' + (r[2] || 'g') + '"></span>' + esc(r[0]) +
        '<span class="n mono" style="font-size:10.5px;max-width:60%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
        esc(r[1] == null ? '—' : String(r[1])) + '</span></div>';
    }).join('');
  }
  function bar(label, n, den, tone) {
    var p = den ? Math.round(100 * n / den) : 0;
    return '<div style="padding:4px 0"><div style="display:flex;align-items:baseline;gap:8px;font-size:11px;color:var(--ink-2)">' +
      '<span>' + esc(label) + '</span><span class="mono" style="margin-left:auto;color:var(--neon-2);font-size:10.5px">' +
      n + (den ? '/' + den : '') + '</span></div>' +
      '<span class="track" style="display:block;margin-top:5px"><i class="' + (tone || '') + '" style="width:' + p + '%"></i></span></div>';
  }
  function head(title, right) {
    $('composer').style.display = 'none';
    $('chatTitle').textContent = title;
    $('chatTag').textContent = right.tag || '';
    $('chatMeta').textContent = right.meta || '';
  }

  /* ── 面板 12：镜像与晋升（pipeline 18） ── */
  function panelMirror() {
    var G = V8.gaps.mirror_pipeline;
    head('镜像与晋升', { tag: 'pipeline', meta: '实测于 ' + String(V8.gaps.probed_at).replace('T', ' ') });
    var st = G.mirror_status, scan = G.mirror_scan, svc = G.svc_inspect.services || {};
    var upN = Object.keys(svc).filter(function (k) { return svc[k].up; }).length;
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>镜像 ↔ 现实</b> / DIMENSION' +
      '<span class="r">现实版本 ' + esc((st.reality || {}).version) + '</span></div><div class="card-b">' +
      '<div class="grid2" style="gap:9px">' +
      '<div><div class="mono" style="font-size:22px;color:var(--neon-2)">' + esc((st.dimension || {}).files) + '</div>' +
      '<div class="mono dim" style="font-size:9px;margin-top:3px">镜像维度 · 文件</div></div>' +
      '<div><div class="mono" style="font-size:22px;color:var(--neon-2)">' + esc((st.reality || {}).files) + '</div>' +
      '<div class="mono dim" style="font-size:9px;margin-top:3px">现实 · 文件</div></div></div>' +
      kvRows([['差异项', (st.dimension_vs_reality || []).length + ' 项', (st.dimension_vs_reality || []).length ? 'a' : 'g'],
              ['生产晋升', '现实零修改，一次性全量', 'g']]) + '</div></div>' +
      '<div class="card"><div class="card-h"><b>镜像体检</b> / MIRROR SCAN<span class="r">' +
      esc(scan.passed) + '/' + esc(scan.total) + ' 通过</span></div><div class="card-b">' +
      Object.keys(scan.checks || {}).map(function (k) {
        var c = scan.checks[k];
        return '<div class="statline"><span class="led ' + (c.ok ? 'g' : 'r') + '"></span>' + esc(k) +
          '<span class="n mono dim" style="font-size:9.5px">' + esc(c.detail) + '</span></div>';
      }).join('') + '</div></div>' +
      '</div>' +
      '<div class="grid2" style="margin-top:10px">' +
      '<div class="card"><div class="card-h"><b>服务巡检</b> / SERVICES<span class="r">' + upN + '/' +
      Object.keys(svc).length + ' 在跑</span></div><div class="card-b">' +
      Object.keys(svc).slice(0, 10).map(function (k) {
        var s = svc[k];
        return '<div class="statline"><span class="led ' + (s.up ? 'g' : (s.optional ? 'd' : 'r')) + '"></span>' +
          esc(k) + '<span class="n mono dim" style="font-size:9.5px">' + esc(s.host) + ':' + esc(s.port) +
          (s.up ? ' up' : ' down') + '</span></div>';
      }).join('') + '</div></div>' +
      '<div class="card"><div class="card-h"><b>发布记录</b> / PIPELINE<span class="r">' +
      (G.pipeline_status.records || []).length + ' 条</span></div><div class="card-b">' +
      (G.pipeline_status.records || []).slice(0, 6).map(function (r) {
        return '<div class="routebar"><code style="flex:1">' + esc(r.name) + '</code>' +
          '<span class="tm">' + esc(String(r.rec_id).slice(-10)) + '</span></div>';
      }).join('') +
      kvRows([['部署队列', (G.deploy_queue.total || 0) + ' 项', 'd'],
              ['幽灵守卫', G.ghost_guard.clean ? 'clean' : '有发现', G.ghost_guard.clean ? 'g' : 'r']]) +
      '</div></div></div>';
  }

  /* ── 面板 13：大模型通道（llm） ── */
  function panelLLM() {
    var G = V8.gaps.llm_channel;
    head('大模型通道', { tag: 'llm', meta: 'Codex 未连接 · 密钥链 7 级' });
    var cx = G.codex_status, ls = G.llm_status, pool = G.model_key_pool, pb = G.prompt_bridge;
    $('chatBody').innerHTML =
      '<div class="grid3">' +
      '<div class="card"><div class="card-h"><b>官方 Codex</b> / CODEX<span class="r">' +
      (cx.connected ? '已连接' : '未连接') + '</span></div><div class="card-b">' +
      kvRows([['连接', cx.connected ? '已连接' : '未连接', cx.connected ? 'g' : 'a'],
              ['可执行体', cx.codex_path ? String(cx.codex_path).split('\\').pop() : '—', 'g'],
              ['并发上限', '1（单实例复用）', 'g'], ['空闲回收', '600s', 'g']]) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">codex_models 实测被拦：缺 external_llm 授权</p></div></div>' +
      '<div class="card"><div class="card-h"><b>密钥链</b> / KEY CHAIN<span class="r">' +
      (ls.key_chain || []).length + ' 级</span></div><div class="card-b">' +
      (ls.key_chain || []).map(function (k, i) {
        return '<div class="statline"><span class="led g"></span>' + esc(k) +
          '<span class="n mono dim" style="font-size:9.5px">第 ' + (i + 1) + ' 顺位</span></div>';
      }).join('') +
      '<div class="statline" style="border-top:1px dashed var(--line);margin-top:6px;padding-top:6px">' +
      '<span class="led g"></span>通道状态<span class="n mono">' + esc(ls.status) + '</span></div></div></div>' +
      '<div class="card"><div class="card-h"><b>提示词桥</b> / PROMPT<span class="r">纯本地</span></div><div class="card-b">' +
      (pb.segments || []).map(function (s) {
        return '<span class="cap g" style="margin:0 5px 5px 0"><i></i>' + esc(s) + '</span>';
      }).join('') +
      kvRows([['外呼模型', pb.external_model ? '是' : '否（纯本地）', pb.external_model ? 'a' : 'g'],
              ['依赖', pb.deps, 'g']]) + '</div></div>' +
      '</div>' +
      '<div class="card" style="margin-top:10px"><div class="card-h"><b>模型密钥池</b> / KEY POOL' +
      '<span class="r">只读 · 触手只借不拥有</span></div><div class="card-b">' +
      '<div class="grid3">' +
      '<div><div class="mono" style="font-size:22px;color:var(--neon-2)">' + esc(pool.keys_total) + '</div>' +
      '<div class="mono dim" style="font-size:9px">在池密钥</div></div>' +
      '<div><div class="mono" style="font-size:22px;color:var(--neon-2)">' + esc(pool.leases_active) + '</div>' +
      '<div class="mono dim" style="font-size:9px">活跃租借</div></div>' +
      '<div><div class="mono" style="font-size:22px;color:var(--neon-2)">' +
      Object.keys(pool.active_by_owner || {}).length + '</div><div class="mono dim" style="font-size:9px">借出方</div></div></div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px">DPAPI 只存路径，密钥不落界面。</p></div></div>';
  }

  /* ── 面板 14：心智与记忆（mind + brain） ── */
  function panelMind() {
    var G = V8.gaps.mind_memory;
    head('心智与记忆', { tag: 'mind · brain', meta: 'state ' + (G.mind.state || '—') });
    var m = G.mind, bv = G.brain_vault, dm = G.director_mood, mc = G.meta_cognition, asw = G.auto_switch;
    $('chatBody').innerHTML =
      '<div class="grid3">' +
      '<div class="card"><div class="card-h"><b>心智状态</b> / MIND<span class="r">' + esc(m.state) + '</span></div>' +
      '<div class="card-b">' + kvRows([['状态', m.state], ['情绪', m.mood], ['表情', m.expression],
        ['在场感', m.presence], ['经验条数', m.lesson_count]]) + '</div></div>' +
      '<div class="card"><div class="card-h"><b>脑库</b> / BRAIN VAULT<span class="r">Obsidian</span></div>' +
      '<div class="card-b"><div class="grid2" style="gap:9px">' +
      '<div><div class="mono" style="font-size:20px;color:var(--neon-2)">' + esc(bv.notes) + '</div>' +
      '<div class="mono dim" style="font-size:9px">笔记</div></div>' +
      '<div><div class="mono" style="font-size:20px;color:var(--neon-2)">' + esc(bv.wikilinks) + '</div>' +
      '<div class="mono dim" style="font-size:9px">双链</div></div></div>' +
      kvRows([['未解析链接', (bv.unresolved || []).length + ' 条', (bv.unresolved || []).length ? 'a' : 'g'],
              ['写入方式', '只追加 · 无删除路径', 'g']]) + '</div></div>' +
      '<div class="card"><div class="card-h"><b>导演情绪</b> / MOOD<span class="r">只改怎么看</span></div>' +
      '<div class="card-b">' + kvRows([['当前情绪', dm.emotion], ['强度', dm.intensity],
        ['驱动', dm.drive || '（无）'], ['半衰期', dm.half_life]]) + '</div></div>' +
      '</div>' +
      '<div class="grid2" style="margin-top:10px">' +
      '<div class="card"><div class="card-h"><b>元认知红线</b> / META COGNITION<span class="r">只读</span></div>' +
      '<div class="card-b">' + (mc.red_lines || []).map(function (r) {
        return '<div style="font-size:10.5px;color:var(--ink-2);padding:5px 0;border-bottom:1px dashed var(--line);line-height:1.7">' +
          '<span class="mono" style="color:var(--neon-2)">·</span> ' + esc(r) + '</div>';
      }).join('') + '</div></div>' +
      '<div class="card"><div class="card-h"><b>自动切换</b> / AUTO SWITCH<span class="r">阈值 ' +
      esc(asw.threshold) + '</span></div><div class="card-b">' +
      kvRows([['置信度阈值', asw.threshold], ['策略', 'L1 解析 + L2 交叉验证 + L3 置信度'],
              ['低置信处理', '先问主人，不硬猜']]) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">absorb_loop / dream_replay 为骨架级只读能力，未接线执行。</p>' +
      '</div></div></div>';
  }

  /* ── 面板 15：情报与观察（recon 7） ── */
  function panelRecon() {
    var G = V8.gaps.recon;
    head('情报与观察', { tag: 'recon', meta: '只读台账' });
    var tw = G.trend_watch, vw = G.verification_watch;
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>趋势观察链</b> / TREND WATCH<span class="r">' +
      (tw.chain || []).length + ' 环</span></div><div class="card-b">' +
      (tw.chain || []).map(function (c, i) {
        return '<div class="statline"><span class="led ' + (i === 0 ? 'g' : 'd') + '"></span>' + esc(c) +
          '<span class="n mono dim" style="font-size:9.5px">第 ' + (i + 1) + ' 环</span></div>';
      }).join('') +
      ((tw.gaps || []).length ? '<div class="degrade" style="margin-top:9px"><span>缺口：' +
        esc((tw.gaps || []).map(function (g) { return typeof g === 'string' ? g : JSON.stringify(g); }).join(' / ').slice(0, 160)) +
        '</span></div>' : '') + '</div></div>' +
      '<div class="card"><div class="card-h"><b>人机验证台账</b> / VERIFICATION<span class="r">三部门</span></div>' +
      '<div class="card-b">' + (vw.groups || []).map(function (g) {
        return '<div class="statline"><span class="led ' + (g.violations ? 'r' : 'g') + '"></span>' + esc(g.group) +
          '<span class="n mono" style="font-size:10.5px">' + g.count + ' 条 · 违规 ' + g.violations + '</span></div>';
      }).join('') + '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">不主动绕做成机械闸；台账为空即无违规。</p></div></div>' +
      '</div>' +
      '<div class="card" style="margin-top:10px"><div class="card-h"><b>情报组覆盖</b> / INTEL GROUPS' +
      '<span class="r">六维覆盖 · 只读骨架</span></div><div class="card-b"><div class="capwrap">' +
      ['film_intel 影视', 'music_intel 音乐', 'video_intel 短视频', 'osint_scan 开源情报',
       'topic_watch 话题追踪', 'trend_watch 爆火观察', 'verification_watch 验证台账'].map(function (t) {
        return '<span class="cap g"><i></i>' + esc(t) + '</span>';
      }).join('') + '</div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px">' +
      'topic_watch 实测需参数：' + esc(G.topic_watch_err || '') + '<br>' +
      '情报是输入不是指令；禁区清单优先于流量趋势。</p></div></div>';
  }

  /* ── 面板 16：安全攻防（security 5） ── */
  function panelSecurity() {
    var G = V8.gaps.security;
    head('安全攻防', { tag: 'security', meta: '真扫 ' + (G.sec_scan.total || 0) + ' 项' });
    var s = G.sec_scan, sf = (G.sec_surface.attack_surface || {});
    var dist = s.distribution || {};
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>漏洞扫描</b> / SEC SCAN<span class="r">' +
      esc(G.m.sec_scan.ms) + 'ms · 真扫自有代码</span></div><div class="card-b">' +
      '<div class="grid2" style="gap:9px;margin-bottom:10px">' +
      '<div><div class="mono" style="font-size:22px;color:var(--neon-2)">' + esc(s.total) + '</div>' +
      '<div class="mono dim" style="font-size:9px">总命中</div></div>' +
      '<div><div class="mono" style="font-size:22px;color:var(--rose)">' + esc(s.critical) + '</div>' +
      '<div class="mono dim" style="font-size:9px">critical</div></div></div>' +
      bar('high', s.high || 0, s.total, 'rose') + bar('medium', s.medium || 0, s.total, 'warn') +
      bar('low', s.low || 0, s.total, '') +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">OWASP Top 10 + CWE 模式库，扫的是自己。</p></div></div>' +
      '<div class="card"><div class="card-h"><b>攻击面测绘</b> / SURFACE<span class="r">' +
      esc(G.m.sec_surface.ms) + 'ms</span></div><div class="card-b">' +
      [['入口点', sf.entry_points, 900], ['文件操作', sf.file_operations, 1000],
       ['网络', sf.network, 600], ['用户输入', sf.user_inputs, 400],
       ['认证边界', sf.auth_boundaries, 200]].map(function (r) {
        return bar(r[0], r[1] || 0, r[2], (r[1] || 0) > r[2] * 0.7 ? 'warn' : '');
      }).join('') + '</div></div>' +
      '</div>' +
      '<div class="grid3" style="margin-top:10px">' +
      ['sec_scan 漏洞扫描', 'sec_surface 攻击面', 'sec_chain 利用链', 'sec_defenses 蓝队验证',
       'sec_llm 黑客大脑（独立密钥）'].map(function (t) {
        return '<div class="stagecard"><div class="sh">' + esc(t.split(' ')[0]) +
          '<span class="k">' + esc(t.split(' ')[1]) + '</span></div>' +
          '<div class="sb" style="font-size:10px">' +
          (t.indexOf('sec_llm') === 0 ? '独立大模型 + 独立密钥，专用通道不与其他能力混用' : '仅跑自有资产；未授权目标不碰') +
          '</div></div>';
      }).join('') + '</div>';
  }

  /* ── 面板 17：长程与工具（longrun + tools） ── */
  function panelLongrun() {
    var G = V8.gaps.longrun_tools;
    head('长程与工具', { tag: 'longrun · tools', meta: '任务图 58 项' });
    var lr = G.lr_status.progress || {}, sc = G.capability_net.seven_columns || {};
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>长程任务图</b> / LONGRUN<span class="r">' +
      esc(lr.total) + ' 项</span></div><div class="card-b">' +
      bar('已完成 done', lr.done || 0, lr.total, '') +
      bar('失败 failed', lr.failed || 0, lr.total, 'rose') +
      bar('停滞 stalled', lr.stalled || 0, lr.total, 'warn') +
      bar('待办 pending', lr.pending || 0, lr.total, '') +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">非 LLM 验收 + 重试 + 停滞升级，跨进程可续。</p></div></div>' +
      '<div class="card"><div class="card-h"><b>穿透网七栏</b> / CAPABILITY NET<span class="r">只读读数</span></div>' +
      '<div class="card-b">' + Object.keys(sc).map(function (k) {
        var v = String(sc[k]);
        var num = parseInt(v, 10), den = parseInt(v.split('/')[1] || '0', 10);
        return bar(k, isNaN(num) ? 0 : num, isNaN(den) ? 0 : den, k === 'has_test' ? 'warn' : '');
      }).join('') + '</div></div>' +
      '</div>' +
      '<div class="grid2" style="margin-top:10px">' +
      '<div class="card"><div class="card-h"><b>任务明细</b> / TASKS<span class="r">最近 6 条</span></div><div class="card-b">' +
      (G.lr_status.tasks || []).slice(0, 6).map(function (t) {
        var okr = t.status === 'done' || t.status === 'ok';
        return '<div class="routebar"><code style="flex:1;font-size:10.5px">' + esc(t.task_id || '') + '</code>' +
          '<span class="dim" style="font-size:9.5px;max-width:44%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
          esc((t.descr || t.desc || t.description || '').slice(0, 26)) + '</span>' +
          '<span class="tm" style="color:' + (okr ? 'var(--green)' : 'var(--rose)') + '">' + esc(t.status) + '</span></div>';
      }).join('') + '</div></div>' +
      '<div class="card"><div class="card-h"><b>工具箱</b> / TOOLS<span class="r">索引 / 投射</span></div><div class="card-b">' +
      kvRows([['awesome_tools_index', '四原语 INDEX/LOOKUP/MAP/VERIFY · 索引只读'],
              ['projection_card', V8.gaps.longrun_tools.projection_card.readonly_note || '只呈现不执行'],
              ['穿透就绪', sc['penetrate_ready'] || '—']]) + '</div></div></div>';
  }

  /* ── 面板 18：创作与吞噬（creation + devour） ── */
  function panelCreate() {
    var G = V8.gaps.creation_devour;
    head('创作与吞噬', { tag: 'creation · devour', meta: '场景 8 类 · 质量均分 78' });
    var sa = G.scene_anchor, ca = G.code_art, dr = G.devour_reflect, ds = G.devour_scan;
    var q = dr.cap_quality_summary || {};
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>场景锚定</b> / SCENE ANCHOR<span class="r">' +
      (sa.classes || []).length + ' 大类</span></div><div class="card-b">' +
      (sa.classes || []).map(function (c) {
        return '<div style="padding:6px 0;border-bottom:1px dashed var(--line)">' +
          '<div style="display:flex;gap:8px;align-items:baseline"><span class="mono" style="font-size:11px;color:var(--neon-2)">' +
          esc(c.key) + '</span><span class="dim" style="font-size:9.5px">' +
          (c.scenes || []).length + ' 场景 · ' + (c.emotions || []).length + ' 情绪</span></div>' +
          '<div style="font-size:10px;color:var(--ink-3);margin-top:3px">' +
          esc((c.scenes || []).slice(0, 5).join(' · ')) + '</div></div>';
      }).join('') + '</div></div>' +
      '<div class="card"><div class="card-h"><b>吞噬与进化</b> / DEVOUR<span class="r">质量均分 ' +
      esc(q.avg_score) + '</span></div><div class="card-b">' +
      '<div class="grid3" style="gap:9px;margin-bottom:9px">' +
      '<div><div class="mono" style="font-size:19px;color:var(--neon-2)">' + esc(q.total) + '</div>' +
      '<div class="mono dim" style="font-size:9px">已评能力</div></div>' +
      '<div><div class="mono" style="font-size:19px;color:var(--green)">' + esc(q.strong) + '</div>' +
      '<div class="mono dim" style="font-size:9px">强项</div></div>' +
      '<div><div class="mono" style="font-size:19px;color:var(--amber)">' + esc(q.weak) + '</div>' +
      '<div class="mono dim" style="font-size:9px">弱项</div></div></div>' +
      bar('能力质量均分', q.avg_score || 0, 100, (q.avg_score || 0) >= 70 ? '' : 'warn') +
      '<div style="margin-top:9px">' + (ds.gaps || []).map(function (x) {
        return '<div class="statline"><span class="led a"></span>' + esc(x.domain) +
          '<span class="n mono dim" style="font-size:9.5px">' + esc(x.hint) + '</span></div>';
      }).join('') + '</div></div></div>' +
      '</div>' +
      '<div class="grid2" style="margin-top:10px">' +
      '<div class="card"><div class="card-h"><b>代码艺术</b> / CODE ART<span class="r">五原语</span></div>' +
      '<div class="card-b"><div class="capwrap">' + (ca.primitives || []).map(function (p) {
        return '<span class="cap g"><i></i>' + esc(p.cn || p.key) + ' · ' + esc(p.layer || '') + '</span>';
      }).join('') + '</div>' + kvRows([['作品数', ca.works, ca.works ? 'g' : 'd'],
        ['红线', '无种子不许导出', 'g']]) + '</div></div>' +
      '<div class="card"><div class="card-h"><b>创作线</b> / CREATION LINE<span class="r">8 项</span></div>' +
      '<div class="card-b"><div class="capwrap">' +
      ['create 创作出口', 'drama 剧本转分镜', 'brand_outro 品牌片尾', 'emotion_projection 情感投射',
       'render_evolution 渲染进化', 'music_publishing 音乐发布'].map(function (t) {
        return '<span class="cap g"><i></i>' + esc(t) + '</span>';
      }).join('') + '</div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px">brand_outro 实测需参数：' +
      esc(G.brand_outro_err || '') + '</p></div></div></div>';
  }

  /* ── 面板 19：其余域（life / gate / project / finance / 媒体域） ── */
  function panelOthers() {
    var G = V8.gaps.others;
    head('其余域', { tag: 'life · gate · project · media', meta: '一次盘完剩余 14 项' });
    var lf = G.life, gv = G.gate_visibility, pc = G.project_context, qt = G.quant.profile || {};
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>生命档案</b> / LIFE<span class="r">' + esc(lf.state) + '</span></div>' +
      '<div class="card-b"><div class="grid3" style="gap:9px;margin-bottom:9px">' +
      '<div><div class="mono" style="font-size:20px;color:var(--neon-2)">' + esc(lf.events) + '</div>' +
      '<div class="mono dim" style="font-size:9px">事件</div></div>' +
      '<div><div class="mono" style="font-size:11px;color:var(--ink)">' + esc(String(lf.first_at || '').slice(0, 10)) + '</div>' +
      '<div class="mono dim" style="font-size:9px">首次</div></div>' +
      '<div><div class="mono" style="font-size:11px;color:var(--ink)">' + esc(String(lf.last_at || '').slice(0, 10)) + '</div>' +
      '<div class="mono dim" style="font-size:9px">最近</div></div></div>' +
      kvRows([['写入', '只写框架 store · 不出网', 'g']]) + '</div></div>' +
      '<div class="card"><div class="card-h"><b>框架之门</b> / GATE VISIBILITY<span class="r">三态</span></div>' +
      '<div class="card-b">' + (gv.states || []).map(function (s, i) {
        return '<div class="statline"><span class="led ' + (i === 0 ? 'g' : (i === 1 ? 'd' : 'a')) + '"></span>' +
          esc(s) + '</div>';
      }).join('') + '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">回答「门看得见什么、看不见什么」；可见范围只从 framework_gate 读，不复刻第二份。</p></div></div>' +
      '</div>' +
      '<div class="grid2" style="margin-top:10px">' +
      '<div class="card"><div class="card-h"><b>项目上下文</b> / PROJECT<span class="r">只读检索</span></div>' +
      '<div class="card-b">' + kvRows([['蓝图', pc.path], ['指纹', String(pc.sha256 || '').slice(0, 16) + '…'],
        ['写入', '不写盘、不执行命令', 'g']]) + '</div></div>' +
      '<div class="card"><div class="card-h"><b>量化项目</b> / QUANT<span class="r">' +
      (qt.exists ? '工作区存在' : '未测绘') + '</span></div><div class="card-b">' +
      kvRows([['工作区', String(qt.workspace || '').split('\\').pop()],
              ['顶层目录', (qt.top_level_dirs || []).length + ' 个']]) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">quant / quant_backtest / quant_params / quant_strategy 属外部业务模块，未挂载即如实报缺口。</p></div></div>' +
      '</div>' +
      '<div class="card" style="margin-top:10px"><div class="card-h"><b>媒体与外部域</b> / MEDIA &amp; EXTERNAL' +
      '<span class="r">10 项能力 · 只读骨架或门</span></div><div class="card-b"><div class="capwrap">' +
      ['video 视频制作 3', 'image_video 图像生成', 'digital_human 3D 数字人', 'infra 云电脑',
       'integration 飞书镶嵌', 'social 社交发布', 'comms 通信邮件', 'collab 协作网络',
       'automation 浏览器', 'vision 视觉识别', 'finance 量化 4'].map(function (t) {
        return '<span class="cap a"><i></i>' + esc(t) + '</span>';
      }).join('') + '</div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.7">' +
      '这 10 项多数是需要密钥/外部服务的门（如 a1art_skill / libtv / h3_video_gen / cloud_pc / feishu_embed），' +
      '按框架规矩：<b style="color:var(--ink)">出口清单写实际出口，不写规划出口</b> —— 所以这里如实标为「门」，不画假的运行台。</p>' +
      '</div></div>';
  }
