  /* ══════════════════════════════════════════════════════════════════
     宿主外壳层 · V11 新增 10 面板
     全部席位 id 来自本机 @deepseek-ai/* 包 lib/client.js 的真实注册，
     无一条编造。判据：该 slot 是否在本原型里真正渲染出来。
     ══════════════════════════════════════════════════════════════════ */
  var DSH = V11.dsh;

  function dshShort(n) {
    return String(n).replace(/^dsh-client-ui-/, '').replace(/^dsh-client-/, '').replace(/^dsh-/, '');
  }
  function dshDone(slot) {
    for (var i = 0; i < DSH.implemented.length; i++) {
      if (DSH.implemented[i].slot === slot) return DSH.implemented[i].how;
    }
    return null;
  }
  function dshOwners(slot) {
    var o = DSH.slot_owner[slot] || [];
    if (!o.length) return '无注册方';
    return o.slice(0, 3).map(dshShort).join(' + ') + (o.length > 3 ? ' 等 ' + o.length + ' 个' : '');
  }
  function dshSlotRows(keys, hideOwner) {
    if (!keys || !keys.length) {
      return '<div class="statline" style="color:var(--ink-3)">该家族在本次扫描里没有席位 —— 不是漏画，是官方没注册。</div>';
    }
    return keys.map(function (s) {
      var how = dshDone(s);
      return '<div class="statline"><span class="led ' + (how ? 'g' : (hideOwner ? 'd' : 'r')) + '"></span>' +
        '<span class="mono" style="font-size:10.5px;color:' + (how ? 'var(--ink)' : 'var(--ink-2)') + '">' + esc(s) + '</span>' +
        '<span class="n mono" style="font-size:9.5px;max-width:56%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:' +
        (how ? 'var(--neon-2)' : 'var(--ink-3)') + '">' +
        esc(how ? how : (hideOwner ? '未实现' : dshOwners(s))) + '</span></div>';
    }).join('');
  }
  function dshFamCard(key, hideOwner) {
    var f = null, i;
    for (i = 0; i < DSH.families.length; i++) if (DSH.families[i].key === key) f = DSH.families[i];
    if (!f) return '';
    var done = f.slots.filter(function (s) { return !!dshDone(s); }).length;
    return '<div class="card"><div class="card-h"><b>' + esc(f.zh) + '</b><span class="r">' +
      f.slots.length + ' 席位 · 已实现 ' + done + '</span></div><div class="card-b">' +
      dshSlotRows(f.slots, hideOwner) + '</div></div>';
  }
  function dshPluginRows(names, note) {
    var byName = {};
    DSH.plugins.forEach(function (p) { byName[p.name] = p; });
    var found = names.filter(function (n) { return byName[n]; });
    if (!found.length) {
      return '<div class="statline" style="color:var(--ink-3)">本次扫描未在客户端清单里找到这些包。</div>';
    }
    return found.map(function (n) {
      var p = byName[n];
      return '<div style="padding:7px 0;border-bottom:1px solid var(--line)">' +
        '<div style="display:flex;align-items:baseline;gap:8px">' +
        '<span class="mono" style="font-size:11px;color:var(--ink)">' + esc(n) + '</span>' +
        '<span class="mono dim" style="font-size:9.5px;margin-left:auto">' + p.n_slots + ' 席位</span></div>' +
        '<p style="font-size:10px;color:var(--ink-3);margin:4px 0 5px;line-height:1.7">' + esc(p.desc || '（该包 README 无前置描述）') + '</p>' +
        '<div class="capwrap">' + p.slots.slice(0, 8).map(function (s) {
          return '<span class="cap ' + (dshDone(s) ? 'g' : '') + '"><i></i>' + esc(s) + '</span>';
        }).join('') + (p.slots.length > 8 ? '<span class="cap"><i></i>+ ' + (p.slots.length - 8) + '</span>' : '') + '</div></div>';
    }).join('') + (note ? '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">' + esc(note) + '</p>' : '');
  }
  function dshGateNote(title, zh, need) {
    return '<div class="degrade" style="margin-top:9px"><span><b>' + esc(title) + '</b> · ' + esc(zh) +
      '　解锁需要：<span class="mono">' + esc(need) + '</span>　授权只能主人在终端发放，本原型不代发。</span></div>';
  }
  function dshCoverCard() {
    var p = Math.round(100 * DSH.n_implemented / DSH.n_total);
    return '<div class="card"><div class="card-h"><b>宿主插槽覆盖</b> / SLOT COVERAGE' +
      '<span class="r">' + esc(DSH.scanned_at.slice(0, 10)) + ' 实测</span></div><div class="card-b">' +
      '<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:8px">' +
      '<span class="mono" style="font-size:30px;color:var(--neon-2);line-height:1">' + DSH.n_implemented + '</span>' +
      '<span class="mono dim" style="font-size:12px">/ ' + DSH.n_total + ' 席位已实现</span>' +
      '<span class="mono" style="margin-left:auto;font-size:11px;color:var(--amber)">缺口 ' + DSH.n_missing + '</span></div>' +
      '<span class="track" style="display:block"><i class="warn" style="width:' + p + '%"></i></span>' +
      '<div class="grid2" style="gap:9px;margin-top:11px">' +
      '<div><div class="mono" style="font-size:17px;color:var(--ink)">' + DSH.n_slots_real + '</div>' +
      '<div class="mono dim" style="font-size:9px">宿主界面席位</div></div>' +
      '<div><div class="mono" style="font-size:17px;color:var(--ink)">' + DSH.n_slots_app + '</div>' +
      '<div class="mono dim" style="font-size:9px">外部应用席位</div></div></div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.8">' +
      '来源：' + esc(DSH.source) + '<br>' +
      '官方包 ' + DSH.official_total + ' 个，其中带客户端清单 ' + DSH.client_total +
      ' 个，真正注册了席位的 ' + DSH.client_with_slots + ' 个。</p></div></div>';
  }

  /* ── 面板 21：外壳与侧栏 ── */
  function panelShell() {
    head('外壳与侧栏', { tag: 'shell · sidebar', meta: '11 席位 · 已实现 1' });
    var n = DSH.n_total;
    $('chatBody').innerHTML =
      dshCoverCard() +
      '<div class="grid2" style="margin-top:11px">' +
      dshFamCard('sidebar.brand') + dshFamCard('sidebar.workspaces') +
      '</div>' +
      '<div class="grid2" style="margin-top:11px">' +
      dshFamCard('sidebar.panellist') + dshFamCard('sidebar.footer') +
      '</div>' +
      '<div class="grid2" style="margin-top:11px">' +
      dshFamCard('sidebar.settings') + dshFamCard('shell.overlay') +
      '</div>' +
      '<div class="grid2" style="margin-top:11px">' +
      dshFamCard('session.new') + dshFamCard('session.hierarchy') +
      '</div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>工作区席位</b> / WORKSPACE' +
      '<span class="r">' + DSH.families.filter(function (f) { return f.key === 'workspace.add'; }).length + ' 家族</span></div>' +
      '<div class="card-b">' + dshSlotRows(['workspace.add']) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px;line-height:1.8">' +
      '官方侧栏是插槽外壳：品牌行、面板清单、工作区、设置席位、底部署位各自独立注册，' +
      '任一插件都能往这些位置塞东西。本原型只实现了「工作区」这一格（项目树），' +
      '其余 10 格目前是空的 —— 空就是空，不画假内容填。</p></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>这 11 格分别归谁</b> / REGISTRANTS</div>' +
      '<div class="card-b">' + dshPluginRows(
        ['dsh-client-ui-sidebar', 'dsh-client-ui-brand-official', 'dsh-client-ui-workspace',
         'dsh-client-ui-settings-general', 'dsh-client-ui-layout'], '') + '</div></div>';
  }

  /* ── 面板 22：会话头部 ── */
  function panelSesshead() {
    head('会话头部', { tag: 'session.header', meta: '6 席位 · 已实现 0' });
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      dshFamCard('conversation.session') +
      '<div class="card"><div class="card-h"><b>头部席位分工</b> / HEADER SLOTS<span class="r">官方声明</span></div>' +
      '<div class="card-b">' +
      [['conversation.session.header', '整个头部容器，其他席位挂在它里面'],
       ['…header.actions', '动作区：本包实测被 3 个插件抢注（jobs / schedule / agent-preset）'],
       ['…header.corner', '角标区：右侧栏插件用'],
       ['…header.lineage', '谱系区：子代理续接路由用，画的是谁派生了谁'],
       ['…header.utilities', '工具区：会话日志导出 ZIP 用']].map(function (r) {
        return '<div style="padding:7px 0;border-bottom:1px solid var(--line)">' +
          '<div class="mono" style="font-size:10.5px;color:var(--ink)">' + esc(r[0]) + '</div>' +
          '<p style="font-size:10px;color:var(--ink-3);margin:4px 0 0;line-height:1.7">' + esc(r[1]) + '</p></div>';
      }).join('') +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px">两个插件抢同一个席位是官方允许的：席位是列表，不是单槽。</p>' +
      '</div></div>' +
      '</div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>抢注 ·header.actions 的三家</b> / CONTENTION</div>' +
      '<div class="card-b">' + dshPluginRows(
        ['dsh-client-ui-jobs', 'dsh-client-ui-schedule', 'dsh-client-ui-agent-preset'], '') + '</div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>剩余四席</b> / CORNER · LINEAGE · UTILITIES</div>' +
      '<div class="card-b">' + dshSlotRows(
        ['conversation.session.header.corner', 'conversation.session.header.lineage',
         'conversation.session.header.utilities']) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px">' +
      'corner 归右侧栏、lineage 归子代理、utilities 归会话日志导出 —— 三家互不干扰，这是插槽设计的意义。</p></div></div>';
  }

  /* ── 面板 23：输入区席位 ── */
  function panelComposer2() {
    head('输入区席位', { tag: 'conversation.input', meta: '13 席位 · 已实现 0' });
    var fam = ['conversation.input.dock', 'conversation.input.plan', 'conversation.input.model',
               'conversation.input.attachments', 'conversation.input.overlay',
               'conversation.input.left', 'conversation.input.right'];
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>7 个输入席位</b> / INPUT SLOTS<span class="r">全未实现</span></div>' +
      '<div class="card-b">' + dshSlotRows(fam) + '</div></div>' +
      '<div class="card"><div class="card-h"><b>输入栏与空态</b> / COMPOSER · HERO<span class="r">6 席位</span></div>' +
      '<div class="card-b">' + dshSlotRows(
        ['conversation.composer', 'conversation.composer.bar', 'conversation.composer.dock',
         'conversation.hero.brand.mark', 'conversation.hero.workspace', 'conversation.message.images']) + '</div></div>' +
      '</div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>每个输入席位放什么</b> / MAPPING<span class="r">读自插件声明</span></div>' +
      '<div class="card-b">' +
      [['conversation.input.dock', '目标条带 GoalBar：显示当前目标，支持编辑 / 暂停 / 恢复 / 清除（CAS 提交）', 'dsh-client-ui-goal'],
       ['conversation.input.plan', 'plan 模式徽章：显示已开启，并可一键关闭', 'dsh-client-ui-plan'],
       ['conversation.input.model', '模型选择器：当前模型 / 提供方切换', 'dsh-client-ui-model-selection'],
       ['conversation.input.attachments', '草稿附件栏：待发送的文件与图片', 'dsh-client-ui-attachment'],
       ['conversation.input.overlay', '浮层：/ 命令目录、skill 引用、@ 引用、点赞点踩弹窗', 'dsh-client-ui-commands / skill / reference'],
       ['conversation.input.left', '左席位（输入框内左侧）', 'dsh-cordis-client-runner'],
       ['conversation.input.right', '右席位（输入框内右侧）', 'dsh-cordis-client-runner'],
       ['conversation.composer.dock', '输入栏底部停靠带', 'dsh-client-ui-chat'],
       ['conversation.composer.bar', '输入栏本体横条', 'dsh-client-ui-conversation'],
       ['conversation.hero.workspace', '空态引导里的工作区入口', 'dsh-client-ui-workspace'],
       ['conversation.message.images', '历史消息里的图片画廊（含原图灯箱）', 'dsh-client-ui-attachment']].map(function (r) {
        return '<div style="padding:7px 0;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:flex-start">' +
          '<span class="led ' + (dshDone(r[0]) ? 'g' : 'r') + '" style="margin-top:5px"></span>' +
          '<div style="flex:1"><div class="mono" style="font-size:10.5px;color:var(--ink)">' + esc(r[0]) + '</div>' +
          '<p style="font-size:10px;color:var(--ink-3);margin:3px 0 0;line-height:1.7">' + esc(r[1]) + '</p></div>' +
          '<span class="mono dim" style="font-size:9px;max-width:30%;text-align:right">' + esc(r[2]) + '</span></div>';
      }).join('') + '</div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>输入区注册方</b> / WHO PUTS WHAT HERE</div>' +
      '<div class="card-b">' + dshPluginRows(
        ['dsh-client-ui-goal', 'dsh-client-ui-plan', 'dsh-client-ui-model-selection',
         'dsh-client-ui-attachment', 'dsh-client-ui-commands', 'dsh-client-ui-input-trigger'], '') + '</div></div>';
  }

  /* ── 面板 24：对话视图环 ── */
  function panelViewring() {
    head('对话视图环', { tag: 'conversation.view', meta: '6 席位 · 已实现 3' });
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>视图环席位</b> / VIEW RING<span class="r">可换视图</span></div>' +
      '<div class="card-b">' + dshSlotRows(
        ['conversation.view', 'main.conversation', 'conversation.chat.node',
         'conversation.chat.assistant-actions', 'conversation.chat.commandview',
         'conversation.trajectory.images']) + '</div></div>' +
      '<div class="card"><div class="card-h"><b>往视图环里注册的</b> / REGISTERED VIEWS<span class="r">3 家</span></div>' +
      '<div class="card-b">' +
      [['dsh-client-ui-chat', '聊天流视图（默认）', 'conversation.chat.node'],
       ['dsh-client-ui-trajectory', '轨迹视图：按轮次的事件记录表 + 交互式时间概览', 'conversation.view'],
       ['dsh-client-ui-workflow-run', '工作流运行节点：把顶层运行重建成带折叠的独立聊天节点', 'conversation.chat.node'],
       ['dsh-client-ui-deliverables', '产出物：轮次末尾的产出文件行 + 正文行内可点链接', 'tool.call.toolview'],
       ['dsh-client-ui-tool', '工具调用卡（视图环里最大的一家）', 'conversation.chat.node']].map(function (r) {
        return '<div style="padding:7px 0;border-bottom:1px solid var(--line)">' +
          '<div style="display:flex;gap:8px;align-items:baseline">' +
          '<span class="mono" style="font-size:10.5px;color:var(--ink)">' + esc(r[0]) + '</span>' +
          '<span class="mono dim" style="font-size:9px;margin-left:auto">' + esc(r[2]) + '</span></div>' +
          '<p style="font-size:10px;color:var(--ink-3);margin:4px 0 0;line-height:1.7">' + esc(r[1]) + '</p></div>';
      }).join('') + '</div></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>视图环是什么</b> / WHY A RING</div>' +
      '<div class="card-b"><p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' +
      '官方把「对话区长什么样」做成了一个可注册的环：插件把视图注册进 <span class="mono">conversation.view</span>，' +
      '用户在视图之间切换，数据源不变。<br>' +
      '这解释了为什么同一个会话能既显示成聊天流、又显示成事件轨迹表 —— 不是两个页面，是同一个环的两个席位。<br>' +
      '<span style="color:var(--amber)">本原型目前只实现了聊天流一个席位（' + esc(dshDone('conversation.view') || '') +
      '），轨迹视图与工作流节点未实现。</span></p></div></div>';
  }

  /* ── 面板 25：工具卡片与调用树 ── */
  function panelToolcard() {
    head('工具卡片与调用树', { tag: 'tool.call · tool.title', meta: '14 席位 · 已实现 0' });
    var titles = DSH.slot_owner ? Object.keys(DSH.slot_owner).filter(function (s) {
      return s.indexOf('tool.title.') === 0;
    }).sort() : [];
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>调用卡席位</b> / CALL SLOTS<span class="r">3 席</span></div>' +
      '<div class="card-b">' + dshSlotRows(['tool.call.toolview', 'tool.call.images', 'tool.view.cordis']) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px;line-height:1.8">' +
      'toolview 被 4 家抢注（tool / deliverables / skill / cordis），按工具名分发到不同卡片。</p></div></div>' +
      '<div class="card"><div class="card-h"><b>内置工具标题位</b> / TOOL TITLES<span class="r">' +
      titles.length + ' 个</span></div><div class="card-b"><div class="capwrap">' +
      titles.map(function (t) {
        return '<span class="cap"><i></i>' + esc(t.replace('tool.title.', '')) + '</span>';
      }).join('') + '</div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.8">' +
      '官方给每个内置工具留了独立标题位：' + esc(titles.map(function (t) { return t.replace('tool.title.', ''); }).join(' / ')) +
      '。<br>generic 是兜底位，未单独注册的工具走它。</p></div></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>调用树怎么组合</b> / CALL TREE<span class="r">dsh-client-ui-tool</span></div>' +
      '<div class="card-b">' +
      [['整次调用树', '把一轮对话里所有工具调用组合成一棵树，子调用挂在父调用下'],
       ['keyed 按工具视图', '按工具名 key 分发到各自的卡片渲染器，互不干扰'],
       ['原子工具卡片', 'read / write / edit / glob / grep / bash / pwsh / code / inspect / search 各一张'],
       ['图片席位', '工具产出图片时的画廊位（tool.call.images）'],
       ['Cordis 动态插件面', '动态包的专属视图（tool.view.cordis），与静态工具卡分开']].map(function (r) {
        return '<div class="statline"><span class="led d"></span>' + esc(r[0]) +
          '<span class="n" style="font-size:10px;color:var(--ink-3);max-width:58%;text-align:right;white-space:normal">' +
          esc(r[1]) + '</span></div>';
      }).join('') + '</div></div>' +
      dshGateNote('未实现', '本原型的工具调用只是文本流，没有树、没有按工具分卡、没有图片画廊。', '设计实现（不需要授权）');
  }

  /* ── 面板 26：权限批准与提问 ── */
  function panelGateask() {
    head('权限批准与提问', { tag: 'approval · questions', meta: '4 包 · 已实现 0' });
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>批准界面</b> / APPROVAL<span class="r">conversation.approval.detail</span></div>' +
      '<div class="card-b">' +
      '<p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' +
      '宿主发权限请求时，浏览器侧的批准界面接管。措辞是官方 README 原文：<br>' +
      '<span style="color:var(--ink)">「通过作用域交互路径响应 Host 权限请求的浏览器批准界面」</span></p>' +
      '<div class="capwrap" style="margin-top:9px">' +
      '<span class="cap"><i></i>conversation.approval.detail</span><span class="cap"><i></i>conversation.composer</span></div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.8">' +
      '关键在「作用域」：批准的不是「一次操作」，是「一个作用域 + 一个 TTL」。' +
      '本项目的授权门（auth_gate）就是这个模型 —— AI 永远不能自己给自己发。</p></div></div>' +
      '<div class="card"><div class="card-h"><b>提问界面</b> / ASK USER<span class="r">dsh-client-ui-user-questions</span></div>' +
      '<div class="card-b">' +
      '<p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' +
      '官方描述：「接管编辑器的提问 UI 与 plan-review 审批卡片」。<br>' +
      '也就是 ask_user_question 不是弹窗，是<b>接管整个输入框</b>；plan 复审走同一套卡片。</p>' +
      '<div class="capwrap" style="margin-top:9px">' +
      ['单选', '多选', '自由文本', '跳过 / 超时按默认继续', 'plan 复审卡'].map(function (t) {
        return '<span class="cap ' + (t.indexOf('plan') === 0 ? '' : 'g') + '"><i></i>' + esc(t) + '</span>';
      }).join('') + '</div></div></div></div>' +
      '<div class="grid2" style="margin-top:11px">' +
      '<div class="card"><div class="card-h"><b>权限预设</b> / PRESETS<span class="r">settings.permission</span></div>' +
      '<div class="card-b">' + dshSlotRows(['settings.permission']) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px;line-height:1.8">' +
      '预设是「一组作用域的打包」，在设置里切换，不用每次单独批。</p></div></div>' +
      '<div class="card"><div class="card-h"><b>反馈</b> / FEEDBACK<span class="r">dsh-client-ui-message-feedback</span></div>' +
      '<div class="card-b">' + dshSlotRows(['conversation.chat.assistant-actions', 'conversation.input.overlay']) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px;line-height:1.8">' +
      '已定稿消息动作行里的点赞/点踩，与 /feedback 共用同一个弹窗。</p></div></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>四个包的真实描述</b> / SOURCE TEXT</div>' +
      '<div class="card-b">' + dshPluginRows(
        ['dsh-client-ui-approval', 'dsh-client-ui-user-questions',
         'dsh-client-ui-permission-presets', 'dsh-client-ui-message-feedback'], '') + '</div></div>';
  }

  /* ── 面板 27：子代理与技能 ── */
  function panelSubskill() {
    head('子代理与技能', { tag: 'subagent · skill', meta: '5 包 · 已实现 0' });
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>子代理界面</b> / SUBAGENT<span class="r">dsh-client-ui-subagent</span></div>' +
      '<div class="card-b">' +
      '<p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">官方描述：「subagent 对话目录、续接路由 UI 与 \'@\' 引用 source」。三件事：</p>' +
      '<div class="capwrap" style="margin-top:8px">' +
      '<span class="cap"><i></i>对话目录（谁派生了谁 · session.hierarchy）</span>' +
      '<span class="cap"><i></i>续接路由（会话头部 lineage 席位）</span>' +
      '<span class="cap"><i></i>@ 引用（把子代理当上下文引进来）</span></div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.8">' +
      '本会话里子代理是真实存在的能力（subagent / subagent_fork），但界面上只有一行文字，' +
      '没有目录、没有谱系、没有 @ 引用 —— 三样全缺。</p></div></div>' +
      '<div class="card"><div class="card-h"><b>技能界面</b> / SKILL<span class="r">dsh-client-ui-skill</span></div>' +
      '<div class="card-b">' +
      '<p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">官方描述：「skill 引用与专属 skill 工具行：/ 触发的 skill source 与 skill 调用卡片」。</p>' +
      '<div class="capwrap" style="margin-top:8px">' +
      '<span class="cap"><i></i>/ 触发候选</span><span class="cap"><i></i>skill 调用卡片</span>' +
      '<span class="cap"><i></i>tool.call.toolview</span></div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.8">' +
      '本环境技能目录有 40+ 项（飞书全套、链上数据、浏览器等），界面上一个都点不到。</p></div></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>命令与引用</b> / COMMANDS · REFERENCE<span class="r">两个 source</span></div>' +
      '<div class="card-b">' +
      [['dsh-client-ui-commands', '客户端命令 API：/ 命令 source、三类派发、会话级命令目录，以及 popupSelect 与 action', 'conversation.input.overlay'],
       ['dsh-client-ui-reference', 'Web @file 与 @session 引用 source：候选项、排序，以及原子行内引用', 'conversation.input.overlay'],
       ['dsh-client-ui-input-trigger', '输入触发器：识别 / 与 @ 并唤起对应浮层', 'conversation.input.overlay'],
       ['dsh-client-ui-directory-picker-browse', 'Miller 分栏「选择工作区目录」对话框', '（模态，不占 slot）'],
       ['dsh-client-ui-directory-picker-native', '驱动宿主操作系统选择器的浏览器半部', '（模态，不占 slot）'],
       ['dsh-client-ui-open-in-app', '"Open In..." 分体按钮：在记住的应用中打开工作区目录', 'conversation.session.header.corner']].map(function (r) {
        return '<div style="padding:7px 0;border-bottom:1px solid var(--line)">' +
          '<div style="display:flex;gap:8px;align-items:baseline">' +
          '<span class="mono" style="font-size:10.5px;color:var(--ink)">' + esc(r[0]) + '</span>' +
          '<span class="mono dim" style="font-size:9px;margin-left:auto">' + esc(r[2]) + '</span></div>' +
          '<p style="font-size:10px;color:var(--ink-3);margin:4px 0 0;line-height:1.7">' + esc(r[1]) + '</p></div>';
      }).join('') + '</div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>五个包的真实描述</b> / SOURCE TEXT</div>' +
      '<div class="card-b">' + dshPluginRows(
        ['dsh-client-ui-subagent', 'dsh-client-ui-skill', 'dsh-client-ui-commands',
         'dsh-client-ui-reference', 'dsh-client-ui-input-trigger'], '') + '</div></div>';
  }

  /* ── 面板 28：右侧栏与文档预览 ── */
  function panelRightpane() {
    head('右侧栏与文档预览', { tag: 'sidebar.right', meta: '6 席位 · 已实现 0' });
    var right = DSH.plugins.filter(function (p) {
      return p.name === 'dsh-client-ui-sidebar-files' || p.name === 'dsh-client-ui-sidebar-documentpreview' ||
             p.name === 'dsh-client-ui-sidebar-right';
    });
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>右侧栏席位</b> / RIGHT PANE<span class="r">五层页签</span></div>' +
      '<div class="card-b">' + dshSlotRows(
        ['sidebar.right.pane.tab', 'sidebar.right.pane.tab.title', 'sidebar.right.tab.document',
         'sidebar.right.tab.guide', 'sidebar.right.tab.menu.item', 'rightbar.session']) +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:8px;line-height:1.8">' +
      '页签是分层的：pane.tab 是页签本体，pane.tab.title 是标题位，tab.document / tab.guide 是两类内容位，' +
      'menu.item 是页签右键菜单。工具区（sidebar-files）和文档预览（documentpreview）都往 pane.tab 注册。</p></div></div>' +
      '<div class="card"><div class="card-h"><b>文档预览的渲染器</b> / RENDERERS<span class="r">5 + 兜底</span></div>' +
      '<div class="card-b"><div class="capwrap">' +
      [['Markdown', 1], ['代码', 1], ['图片', 1], ['PDF', 1], ['HTML', 1], ['纯文本兜底', 1]].map(function (r) {
        return '<span class="cap ' + (r[0] === '纯文本兜底' ? '' : 'g') + '"><i></i>' + r[0] + '</span>';
      }).join('') + '</div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:9px;line-height:1.8">' +
      '共享文件加载 + 控件，按扩展名选渲染器，不认识的一律退纯文本。<br>' +
      '本原型里点文件名没有任何反应 —— 没有预览面。</p></div></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>三个右侧栏包的真实描述</b> / SOURCE TEXT</div>' +
      '<div class="card-b">' + dshPluginRows(
        ['dsh-client-ui-sidebar-right', 'dsh-client-ui-sidebar-files',
         'dsh-client-ui-sidebar-documentpreview'], '') + '</div></div>' +
      dshGateNote('未实现', '点击文件名应打开右侧预览页签（Markdown / 代码 / 图片 / PDF / HTML 五选一），现在点了没反应。',
                  '设计实现（读取走 filesystem_read，只读）');
  }

  /* ── 面板 29：设置中心 ── */
  function panelSettingsX() {
    head('设置中心', { tag: 'settings.*', meta: '24 席位 · 已实现 0' });
    var sfam = DSH.families.filter(function (f) { return f.key.indexOf('settings.') === 0; })
      .sort(function (a, b) { return b.slots.length - a.slots.length; });
    $('chatBody').innerHTML =
      '<div class="card"><div class="card-h"><b>设置是插槽底座</b> / SETTINGS FOUNDATION' +
      '<span class="r">' + sfam.length + ' 家族 · ' +
      sfam.reduce(function (a, f) { return a + f.slots.length; }, 0) + ' 席位</span></div>' +
      '<div class="card-b"><p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' +
      '官方 dsh-client-ui-settings 自己的定义：「设置命名空间 scope 服务、schema 服务，以及规范设置 slot 类型约定」。<br>' +
      '也就是设置面板<b>本身不含任何设置项</b>，它只提供位置和校验；每一项都由别的插件注册进来。' +
      '所以本原型里那个「设置」面板（主题 / 分布 / 快捷键）其实一个官方席位都没对上。</p></div></div>' +
      '<div class="grid2" style="margin-top:11px">' +
      sfam.slice(0, 12).map(function (f) { return dshFamCard(f.key, true); }).join('') +
      '</div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>谁往设置里放了什么</b> / REGISTRANTS<span class="r">6 包</span></div>' +
      '<div class="card-b">' + dshPluginRows(
        ['dsh-client-ui-settings', 'dsh-client-ui-settings-general', 'dsh-client-ui-settings-models',
         'dsh-client-ui-settings-plugins', 'dsh-client-ui-settings-plugin-inventory',
         'dsh-client-ui-theme', 'dsh-client-ui-locale', 'dsh-client-ui-permission-presets'], '') + '</div></div>';
  }

  /* ── 面板 30：外部应用直通 ── */
  function panelOpenapp() {
    head('外部应用直通', { tag: 'app.*', meta: DSH.n_slots_app + ' 个应用席位 · 已实现 0' });
    $('chatBody').innerHTML =
      '<div class="card"><div class="card-h"><b>Open In… 分体按钮</b> / OPEN IN APP<span class="r">dsh-client-ui-open-in-app</span></div>' +
      '<div class="card-b"><p style="font-size:10.5px;color:var(--ink-2);line-height:1.9">' +
      '官方描述：「在记住的应用中打开会话 workspace 目录，并列出主机探测到已安装的全部应用」。<br>' +
      '每个应用一个席位 id，宿主探测到装了才点亮。<b>下面这些 id 全部读自官方编译产物的注册表</b>，不是猜的。</p></div></div>' +
      '<div class="card" style="margin-top:11px"><div class="card-h"><b>' + DSH.n_slots_app + ' 个应用席位</b> / APP SEATS' +
      '<span class="r">宿主探测后点亮</span></div><div class="card-b"><div class="grid3" style="gap:7px">' +
      DSH.apps.map(function (a) {
        return '<div style="padding:6px 8px;border:1px solid var(--line);border-radius:4px;background:var(--bg-2)">' +
          '<div style="display:flex;align-items:center;gap:6px">' +
          '<span class="led d"></span><span style="font-size:11px;color:var(--ink)">' + esc(a.zh) + '</span></div>' +
          '<div class="mono dim" style="font-size:9px;margin-top:3px">' + esc(a.slot) + '</div></div>';
      }).join('') + '</div>' +
      '<p style="font-size:10px;color:var(--ink-3);margin-top:10px;line-height:1.8">' +
      '编辑器 ' + DSH.apps.filter(function (a) { return /cursor|vscode|windsurf|zed|sublime|intellij|goland|pycharm|webstorm|phpstorm|rider|rustrover|androidstudio|xcode/i.test(a.id); }).length + ' 个 · ' +
      '文件管理器 ' + DSH.apps.filter(function (a) { return /explorer|finder|filemanager/i.test(a.id); }).length + ' 个 · ' +
      '终端 ' + DSH.apps.filter(function (a) { return /terminal|iterm|warp|kitty|ghostty/i.test(a.id); }).length + ' 个 · ' +
      'Git 客户端 ' + DSH.apps.filter(function (a) { return /github|gitkraken|fork|tower|smartgit|sourcetree|sublimemerge/i.test(a.id); }).length + ' 个。<br>' +
      '点「在 X 中打开」= 起一个外部进程，属于 device_control 作用域，本原型不代发授权。</p></div></div>';
  }

  /* ── 上帝视角 · 宿主席位矩阵卡 ── */
  function slotMatrixCard() {
    var fams = DSH.families.slice(0, 18);
    var maxN = fams.length ? fams[0].slots.length : 1;
    return '<div class="card" style="margin-bottom:11px"><div class="card-h"><b>宿主席位矩阵</b> / DSH SLOT MATRIX' +
      '<span class="r">' + DSH.n_implemented + ' / ' + DSH.n_total + ' 已实现</span></div><div class="card-b">' +
      '<p style="font-size:10px;color:var(--ink-3);margin-bottom:9px;line-height:1.8">' +
      '官方客户端插件共注册 <b>' + DSH.n_slots_real + '</b> 个宿主界面席位，加 <b>' + DSH.n_slots_app +
      '</b> 个外部应用席位。本原型命中 <b>' + DSH.n_implemented + '</b> 个 —— 缺口是公开的，不藏。</p>' +
      fams.map(function (f) {
        var done = f.slots.filter(function (s) { return !!dshDone(s); }).length;
        var p = Math.round(100 * f.slots.length / maxN);
        var dp = f.slots.length ? Math.round(100 * done / f.slots.length) : 0;
        return '<div style="padding:3px 0"><div style="display:flex;align-items:baseline;gap:8px;font-size:10.5px">' +
          '<span class="mono" style="color:var(--ink-2);min-width:186px">' + esc(f.key) + '</span>' +
          '<span style="color:var(--ink-3);font-size:10px">' + esc(f.zh) + '</span>' +
          '<span class="mono" style="margin-left:auto;font-size:10px;color:' + (done ? 'var(--neon-2)' : 'var(--ink-3)') + '">' +
          done + '/' + f.slots.length + '</span></div>' +
          '<span class="track" style="display:block;margin-top:4px"><i class="' + (dp >= 50 ? '' : 'warn') +
          '" style="width:' + Math.max(p, 3) + '%;opacity:' + (dp ? 1 : 0.35) + '"></i></span></div>';
      }).join('') +
      '<p style="font-size:9.5px;color:var(--ink-3);margin-top:9px">条长 = 该家族席位数量；条亮 = 有已实现席位。' +
      '完整 39 家族见「外壳与侧栏」面板。</p></div></div>';
  }
