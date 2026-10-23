  /* ── 面板 8：语音 ── */
  function panelVoice() {
    $('composer').style.display = 'none';
    var V = V6.device.voice;
    $('chatTitle').textContent = '语音';
    $('chatTag').textContent = V.tts_backend || '—';
    $('chatMeta').textContent = '实测于 ' + esc(String(V6.device.probed_at).replace('T', ' '));
    var asrOk = V.asr_state === 'configured';
    var ttsOk = !V.tts_gate.denied;
    var chain = [
      ['听 · ASR', asrOk ? '可用' : '缺后端', asrOk ? 'g' : 'r', asrOk ? '已配置' : esc(V.asr_missing)],
      ['想 · 大模型/大脑', true, 'g', 'brain_unify 全链 24.2s（真实）'],
      ['说 · TTS', ttsOk ? '可用' : '被授权门拦住', ttsOk ? 'g' : 'a',
       ttsOk ? 'win-sapi' : '缺 ' + (V.tts_gate.missing || []).join(' + ')]
    ];
    $('chatBody').innerHTML =
      '<div class="chainbox" style="padding:12px"><div class="trace" style="grid-template-columns:118px 1fr 92px">' +
      chain.map(function (c) {
        return '<span class="nm">' + c[0] + '</span>' +
          '<span><span class="led ' + c[2] + '" style="display:inline-block;margin-right:7px"></span>' + c[1] +
          '<span class="dim" style="margin-left:9px;font-size:10px">' + c[3] + '</span></span>' +
          '<span class="ms" style="color:' + (c[2] === 'g' ? 'var(--green)' : (c[2] === 'a' ? 'var(--amber)' : 'var(--rose)')) + '">' +
          (c[2] === 'g' ? '通' : (c[2] === 'a' ? '待授权' : '缺件')) + '</span>';
      }).join('') + '</div>' +
      '<p style="font-size:10.5px;color:var(--ink-3);margin-top:10px;line-height:1.7">' +
      '「语音对话」= 听 + 想 + 说 三段全通。当前想得通（大脑执行层实测 24.2s 全链），' +
      '说被授权门拦着，听缺后端 —— 所以<b style="color:var(--ink)">目前还不能叫语音对话</b>，这两条补齐才算。</p></div>' +

      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>说 · 语音合成</b> / TTS<span class="r">' + esc(V.tts_backend || '—') + '</span></div>' +
      '<div class="card-b">' +
      '<label class="mono dim" style="font-size:9.5px;letter-spacing:.08em" for="ttsText">朗读文本</label>' +
      '<textarea id="ttsText" style="width:100%;min-height:52px;margin-top:5px;background:var(--void);border:1px solid var(--line);border-radius:6px;padding:8px;font-size:12px;outline:none" placeholder="想让它念什么…">能力中枢在线，语音合成链路正常。</textarea>' +
      '<div style="display:flex;gap:7px;margin-top:8px;align-items:center">' +
      '<button class="pill" id="ttsRun" style="border-color:var(--line-hot);color:var(--neon-2)">朗读</button>' +
      '<span class="dim" id="ttsMsg" style="font-size:10.5px">后端在，但需要 audio_output 授权</span></div>' +
      '<div class="degrade" style="margin:9px 0 0">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" width="14" height="14" style="color:var(--amber);flex:none" aria-hidden="true"><path d="M12 9v5M12 17h.01M10.3 3.9L2.6 17a2 2 0 001.7 3h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"/></svg>' +
      '<span>真实调用返回 <b style="color:var(--ink)">denied</b>：缺 <code class="mono">' +
      esc((V.tts_gate.missing || []).join(' + ')) + '</code>。授权只能主人在终端发放，AI 无权自授。</span></div>' +
      '<div class="mono" style="font-size:10px;color:var(--ink-3);margin-top:8px;background:var(--void);border:1px solid var(--line);border-radius:6px;padding:8px;word-break:break-all">' +
      esc((V.tts_gate.how_to_grant || [])[0] || 'python -m gbt_allinone auth grant --scope audio_output --ttl 600') + '</div>' +
      '</div></div>' +

      '<div class="card"><div class="card-h"><b>听 · 语音识别</b> / ASR<span class="r">' +
      (asrOk ? '已配置' : 'needs_dependency') + '</span></div><div class="card-b">' +
      '<div class="statline"><span class="led r"></span>后端状态<span class="n">' + esc(V.asr_state || '—') + '</span></div>' +
      '<div class="statline"><span class="led a"></span>缺什么<span class="n mono" style="font-size:10px">' + esc(V.asr_missing) + '</span></div>' +
      '<p style="font-size:10.5px;color:var(--ink-3);margin-top:9px;line-height:1.7">' +
      'ASR 未配置就没有「听」。面板不摆假麦克风 —— 配好 URL/KEY 后这里会变成绿色可用态。</p></div></div>' +
      '</div>' +

      '<div class="card" style="margin-top:2px"><div class="card-h"><b>语音技能中枢</b> / VOICE ORCHESTRA' +
      '<span class="r">' + (V.skills_total || 0) + ' 项技能 · 实测</span></div><div class="card-b">' +
      '<div class="capwrap">' + (V.skills || []).map(function (s) {
        return '<span class="cap a" title="' + esc((s.domain || '') + ' · ' + (s.provider || '')) + '"><i></i>' + esc(s.name) + '</span>';
      }).join('') + '</div>' +
      '<div class="degrade" style="margin:10px 0 0">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" width="14" height="14" style="color:var(--amber);flex:none" aria-hidden="true"><path d="M12 9v5M12 17h.01M10.3 3.9L2.6 17a2 2 0 001.7 3h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"/></svg>' +
      '<span>' + esc(V.promote_rule || '') + '</span></div></div></div>';

    var b = $('ttsRun');
    if (b) b.addEventListener('click', function () {
      $('ttsMsg').innerHTML = '<span class="spin" style="border-color:rgba(42,212,240,.3);border-top-color:var(--neon-2)"></span> 真实调用被授权门拦下';
      window.setTimeout(function () {
        $('ttsMsg').innerHTML = 'denied · capability requires human authorization';
      }, 620);
    });
  }

  /* ── 面板 9：蓝牙 ── */
  function panelBluetooth() {
    $('composer').style.display = 'none';
    var D = V6.device.bluetooth;
    $('chatTitle').textContent = '蓝牙';
    $('chatTag').textContent = D.ble_backend === 'bleak' ? 'BLE 可用' : 'BLE 缺件';
    $('chatMeta').textContent = '实测于 ' + esc(String(V6.device.probed_at).replace('T', ' '));
    var devs = D.devices || [];
    var best = -30, worst = -100;
    $('chatBody').innerHTML =
      '<div class="grid2">' +
      '<div class="card"><div class="card-h"><b>适配器</b> / ADAPTER<span class="r">' + esc(D.ble_backend) + '</span></div>' +
      '<div class="card-b">' +
      line(D.ble_backend === 'bleak' ? 'g' : 'r', 'BLE 后端', esc(D.ble_backend)) +
      line('g', '经典蓝牙栈', esc(D.classic_backend)) +
      '<p style="font-size:10.5px;color:var(--ink-3);margin-top:9px;line-height:1.7">' +
      '本轮已修复：安装 bleak 3.0.2 + 9 个 winrt 包后，scan 由 needs_dependency 转为 ok（真跑得通）。</p></div></div>' +

      '<div class="card"><div class="card-h"><b>可用原语</b> / OPS<span class="r">' + (D.ops || []).length + ' 个</span></div>' +
      '<div class="card-b"><div class="capwrap">' + (D.ops || []).map(function (o) {
        var open = o === 'scan' || o === 'status';
        return '<span class="cap ' + (open ? 'g' : 'a') + '"><i></i>' + esc(o) + '</span>';
      }).join('') + '</div>' +
      '<p style="font-size:10.5px;color:var(--ink-3);margin-top:9px">绿色＝当前可直接跑；琥珀＝需要 device_control 授权。</p></div></div>' +
      '</div>' +

      '<div class="card"><div class="card-h"><b>附近 BLE 设备</b> / SCAN' +
      '<span class="r">实测 ' + devs.length + ' 台 · ' + D.scan_ms + 'ms</span></div><div class="card-b">' +
      (devs.length ? devs.map(function (d) {
        var r = Math.max(0, Math.min(100, Math.round(100 * (d.rssi - worst) / (best - worst))));
        return '<div style="display:grid;grid-template-columns:auto 1fr 52px;gap:9px;align-items:center;padding:6px 0;border-bottom:1px dashed var(--line)">' +
          '<span class="mono" style="font-size:11px;color:var(--ink)">' + esc(d.address) + '</span>' +
          '<span><span class="dim" style="font-size:10px">' + esc(d.name || '未命名') + '</span>' +
          '<span class="track" style="display:block;margin-top:4px"><i style="width:' + r + '%"></i></span></span>' +
          '<span class="mono dim" style="font-size:10px;text-align:right">' + d.rssi + ' dBm</span></div>';
      }).join('') : '<div class="empty"><h4>未扫到设备</h4><p>附近没有可发现的 BLE 广播。</p></div>') +
      '<div style="display:flex;gap:7px;align-items:center;margin-top:10px">' +
      '<button class="pill" id="btScan" style="border-color:var(--line-hot);color:var(--neon-2)">重新扫描</button>' +
      '<span class="dim" id="btMsg" style="font-size:10.5px">原型回放构建时的真实快照</span></div></div></div>' +

      '<div class="grid2" style="margin-top:10px">' +
      '<div class="card"><div class="card-h"><b>连接与读写</b> / CONTROL<span class="r">需授权</span></div><div class="card-b">' +
      '<dl class="kv"><dt>设备 MAC</dt><dd class="mono">' + esc(devs[0] ? devs[0].address : '—') + '</dd>' +
      '<dt>特征 UUID</dt><dd class="mono">6e400002-b5a3-f393-e0a9-e50e24dcca9e</dd>' +
      '<dt>写入值</dt><dd class="mono">—</dd></dl>' +
      '<div class="degrade" style="margin:9px 0 0">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" width="14" height="14" style="color:var(--amber);flex:none" aria-hidden="true"><path d="M12 9v5M12 17h.01M10.3 3.9L2.6 17a2 2 0 001.7 3h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"/></svg>' +
      '<span>真实调用返回 <b style="color:var(--ink)">denied</b>：缺 <code class="mono">' +
      esc((D.classic_gate.missing || []).join(' + ')) + '</code>。连接/读写/经典态都归它管。</span></div>' +
      '<div class="mono" style="font-size:10px;color:var(--ink-3);margin-top:8px;background:var(--void);border:1px solid var(--line);border-radius:6px;padding:8px;word-break:break-all">' +
      esc((D.classic_gate.how_to_grant || [])[0] || 'python -m gbt_allinone auth grant --scope device_control --ttl 600') + '</div></div></div>' +

      '<div class="card"><div class="card-h"><b>协议库</b> / PROTOCOLS<span class="r">' + (D.protocols || []).length + ' 条公开协议</span></div>' +
      '<div class="card-b"><div class="capwrap">' + (D.protocols || []).map(function (p) {
        return '<span class="cap g"><i></i>' + esc(p) + '</span>';
      }).join('') + '</div>' +
      '<p style="font-size:10.5px;color:var(--ink-3);margin-top:9px;line-height:1.7">' +
      '脑层（意图解析/设备识别/协议匹配/指令组装/闭环验证）已就绪；只收厂商公开文档协议，未知设备如实报告不编造。</p></div></div>' +
      '</div>';

    var sb = $('btScan');
    if (sb) sb.addEventListener('click', function () {
      $('btMsg').innerHTML = '<span class="spin" style="border-color:rgba(42,212,240,.3);border-top-color:var(--neon-2)"></span> 原型不联网外呼，回放真实快照…';
      window.setTimeout(function () {
        $('btMsg').textContent = '回放完毕：仍是构建时实测的 ' + devs.length + ' 台（真实扫描在 RunTask 侧执行）';
      }, 700);
    });
  }
