# 语音剧场 · 设计规格（A · 全屏对话剧场）

> 设计稿：`index.html`（单文件自包含，无构建、无外网）
> 验收器：`py -3.14 tools/codex-scripts/voice-theater-check.py --shot <截图>`
> 就绪清单：`py -3.14 tools/codex-scripts/voice-link-readiness.py`
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 0. 它要解决什么

主人原话：「数字人也一并语音交互，我感觉之前的不行，你重新设计一下」。

旧的数字人页是**探针台**：全部篇幅在证明「麦克风采不到、worklet 被 CSP 拒、桥在哪」——
读数诚实，但不是**交互**。这一稿把重心换过来：

> **人在跟她说话**是主角；诊断信息降级为**右侧常驻体检列**，随时可看，但不抢戏。

---

## 1. 三轴选型（对齐本仓审美规程）

| 轴 | 选择 | 为什么是这个 |
|---|---|---|
| **形态** | 全屏对话剧场（A） | 三个候选里唯一让「她」占满视线；常驻语音条（B）会把她压成小窗，极简环（C）信息量不够撑起"对话" |
| **品牌语言** | 沿用 `holo_pet_w3/window.css` 的三色 | 土豆金 `#F5B041` 主强调 · 赛博青 `#00E5FF` 状态冷色 · 深空紫 `#7C4DFF` 只用作发丝线与极淡径向底。**不另造一套皮** |
| **普适手艺** | 单一光源 · 少即是多 · 层级靠明度与字距 | 全画面只有一个光源（她身后那池光）；分隔线一律 1px 低透明；状态靠**一盏灯**而不是满屏动画 |

**AI 味禁令自查**：无紫粉渐变团、无玻璃拟态堆叠、无三个居中卡片、无 emoji 图标、无"科技感粒子"。

---

## 2. 版式

```
┌────┬──────────────────────────────┬──────────────┐
│ 88 │                              │  体检列 300  │
│ 状 │        舞台（一池光）          │  现读，不装饰 │
│ 态 │        她的立绘（羽化）         │              │
│ 轨 │                              │              │
├────┴──────────────────────────────┴──────────────┤
│   波形（真包络 72 根）        字幕          光球·输入 │
└──────────────────────────────────────────────────┘
```

- 栅格：`88px | 1fr | 300px` 三列，底栏跨 2–3 列；≤1080px 时体检列收起（保证她还在画面里）。
- 立绘：**按高度定尺寸**（`height:100%; width:auto`）。
  ⚠️ 曾用 `object-fit:cover` 被宽画布按宽度铺满、纵向把头顶裁掉——这是实测踩过的坑，别再改回去。
- 光池：椭圆径向遮罩把摄影棚灰底收成一池光；矩形硬边是最露馅的地方。

---

## 3. 状态机（唯一改口 `setState()`）

| 状态 | 灯 | 触发 | 出口 |
|---|---|---|---|
| `idle` 待机 | 灰 | 启动 / 说完 / 被打断 | 按住 / 输入 / 点球 |
| `listen` 在听 | 青（呼吸） | 按住光球（pointerdown） | 松手 → `think`；拿不到麦 → 回 `idle` 并明说 |
| `think` 在想 | 金（常亮） | 松手 / 回车提交 | 700ms 后 → `speak` |
| `speak` 在说 | 金（强） | 音频开始播放 | 播完 → `idle`；Esc/点球/直接输入 → 立即停 |

**三条铁律**：① 任何状态都能被打断；② 灯只反映真实状态；③ 没能力时明说，不让界面装出"能用"。

---

## 4. 数据来源（诚实边界）

| 元素 | 来源 | 现状 |
|---|---|---|
| 波形 / 光晕 | WebAudio `AnalyserNode` 实时包络 | **真音频**，不是随机动画 |
| 音频源 | 默认她的欢迎语音 `welcome-gbt-v8-zh.wav`；`?audio=<地址>` 换成框架真跑出的 TTS 产物 | 两种写法都兼容（相对路径失败会自动再试仓根绝对路径）|
| 字幕 | 逐字显现 + 光标 | 设计稿阶段是固定文案，接真回复时替换 `caption()` 调用 |
| 语音输入 | `getUserMedia` 真申请 | 本机 `0 个录音端点` ⇒ 如实显示"无输入端点"并退到键盘 |
| 出声 | **页面不合成**（要 `audio_output` 票） | 由框架产出 wav 后经 `?audio=` 交给页面 |

**页面永不宣称**：它没有说话能力、没有识别能力。它只宣称"能把真产物放出来"。

---

## 5. 可访问性与降级

- 键盘：`Esc` 随时打断；输入框 `Enter` 提交；光球可 Tab 聚焦。
- 无麦 / 无网 / 无音频：三种情况都有**可见的**提示，且不阻塞键盘路径。
- 窄屏：体检列收起，控制台单列排布。

---

## 6. 验收（可复跑）

```powershell
# ① 静态三条随时可跑
py -3.14 tools/codex-scripts/voice-theater-check.py
# ② 加真渲染（本沙箱必须外部拍图）
py -3.14 -m http.server 8899 --bind 127.0.0.1 *> $env:TEMP/vt-server.log   # 另开窗口
msedge --headless=new --disable-gpu --no-sandbox --window-size=1600,1000 `
       --virtual-time-budget=6000 --screenshot=.scratch/voice-theater-check.png `
       http://127.0.0.1:8899/holo_pet_w3/voice-theater/index.html
py -3.14 tools/codex-scripts/voice-theater-check.py --shot .scratch/voice-theater-check.png
```

五条判据：C1 结构齐 · C2 素材真（含 RIFF/WAVE 头）· C3 无外网面 · C4 真渲染 · C5 非空画面。

**它不验**：音质、ASR/TTS 是否接通、异步行为（解码/开麦/说话）——
实测**无头浏览器不跑页面异步任务**（截图里"录音端点"停在"正在枚举…"），故这三件事本器一律不宣称验过。

### 6.1 状态机行为验证（不靠浏览器）

```powershell
node tools/codex-scripts/voice-theater-states.mjs
```

把页面里的内联脚本**原样**取出来，在 Node `vm` + 假 DOM 里跑，用真实事件驱动状态机：

| 判据 | 验什么 |
|---|---|
| S1 | 初始态 = idle |
| S2 / S2b | 按住光球 → listen；光球 `data-live=1` |
| S3a / S3b | 松手 → think；780ms 后 → speak |
| S4 | `Esc` 立即打断 → idle |
| S5a / S5b | 默认源=样本；`?audio=` → 产物（文案随来源变） |
| S6a–S6d | 解码成功→「已就绪」；取不到→「解码失败」**且给原因**（负控） |

现读：**12/12 全过**（2026-10-18）。
⚠️ 这条量具自己栽过一次：第一版沙箱漏给 `URLSearchParams` ⇒ `?audio=` 读不到、三条红全是**量具自己的 bug**。
写判据的人要记得：红先怀疑尺子。

---

## 7. 还差什么（2026-10-18 二次实测 · 比第一版更准）

第一版这里写的是「两张票没发」。**实测证明不够** —— 票只是第一层。当天逐条跑出来的分层：

| 层 | 项 | 现读 | 谁来解 |
|---|---|---|---|
| 门 | `audio_output` | ✅ 已发并**真跑过**（`auth_consumed: grant-1792332978164`） | 已完成 |
| 门 | `privacy_read` | ✅ 已发并**真跑过**（`auth_consumed: grant-1792332981866`） | 已完成 |
| 门 | `filesystem_write` | ❌ 0 张 —— **要把 TTS 落成 wav 给页面播就必须有它**（`op=tts` 带 `out=` 实测被拒） | `python -m gbt_allinone auth grant --scope filesystem_write --ttl 600` |
| 引擎 | edge-tts 可达 | ⚠️ HTTPS voices 列表 **200**，但 **wss 合成 403**（`edge-tts 7.2.8`） | 让 wss 通（代理，或升级 edge-tts —— 属装包，需主人点头） |
| 引擎 | zh-TW 发音人 | ❌ 本机 SAPI 9 个发音人里 **zh-TW 0 个**（只有 zh-CN / en-US） | 装 Windows「中文(繁體，台灣)」语音包；装好后走本地 SAPI，不依赖外网 |
| 硬件 | 录音端点 | ❌ **不是「没有麦」**：MME/DirectSound/WASAPI 的 `default_input` 全是 `-1`（所以 `listen` 开默认设备必失败）；而 **WDM-KS 看见 4 个采集引脚**（Realtek 麦克风 #9 / 立体声混音 #10 / 蓝牙免提 #6 / Input() #11）——逐个真录：**#9 与 #10 都「流开得起来但 0 帧」** ⇒ 引脚未被 Windows 路由 | 设置 → 系统 → 声音 → 管理声音设备 → 启用『麦克风』或『立体声混音』；或插 USB 麦/耳麦 |
| 落点 | 挂进壳 | 未注册 | 改 `windows.json` + `main.cjs` 窗表（条目见 `window-entry.json`） |

**仓里的硬规矩**（不是我加的，别绕过）：拿不到台湾腔就**不出声，不用大陆腔顶替。
⇒ 「先随便出个声」不是选项，除非主人明确改这条口径。

### 7.1 已修：识别前 16 kHz 归一化（2026-10-18，主人点头后做）
| 项 | 前 | 后 |
|---|---|---|
| 喂 24 kHz 素材给离线识别器 | `confidence 0.252` | **0.311**（+24%），文本更贴原话 |
| 实现 | 录音件直接送识别（设备原生 44.1k / 素材原样） | `voice_cap._normalize_wav_16k()`：先转 16 kHz/单声道/16-bit 再送；回执带 `normalized{changed,in_rate,in_ch,why}` |
| 判据 | 无 | `gbt_allinone/tests/test_voice_normalize16k.py`（3 条：转换 / 本已 16k 不折腾 / 读不了头如实报） |

铁律：**ffmpeg 不在或转码失败时如实报"未归一"，绝不假装转过**。

### 7.2 已修：`listen` 支持 `device`（2026-10-18 · 根因修法）

| 项 | 前 | 后 |
|---|---|---|
| 采集 | 只会开"默认设备"；本机 `default_input` 全是 `-1` ⇒ **永远 `no_input`** | `cap voice '{"op":"listen","seconds":4,"device":9}'` 直连 WDM-KS 引脚 |
| 参数 | `{seconds,culture,min_confidence,timeout,wav}` | 增 `device`（整数索引；`auto`/缺省=老行为） |
| 坏参数 | — | 非整数 → `status:"bad_device"` + 原因（不许猜一个数用） |
| 判据 | 无 | `test_voice_gate_scopes.py` 里 4 条：设备号真进命令行 / 不给就不加 / 坏参数如实拒 / 签名与白名单都在 |

⚠️ **诚实边界（2026-10-18 已实弹验证，不再是"待验"）**：
- ✅ **设备号真送得到录音件**：`device=9` 时回执 `device_attempts[0] = {index:9, device:"麦克风 (Realtek HD Audio Mic input)", api:"Windows WDM-KS"}`；`device=10` 同样命中立体声混音。
- ❌ **但它采不到数据**：两个引脚都是 `流开起来了但 0 帧（引脚没被路由/激活）`。
  ⇒ 「指定设备」这一步通了，卡点下移到 **Windows 侧没把采集引脚路由起来**（启用设备或插 USB 麦），
  不是代码问题。有票能验、没票不猜 —— 这次是**拿票真验过**的结论。

### 7.3 已修：两处读数假话

- `gate_blind_spot` 原来恒为「未读到」：`policy.evaluate()` 返回 **dataclass**，代码只认 dict。
  现改 `_gate_scopes(op)` 现读。**实弹验证**：`op=listen` 的回执现读 `必备作用域 ['privacy_read']`。
- `attempts` 原来被覆盖成空数组：`_record_wav` 用解释器级 attempts 覆盖了录音件的设备级 attempts。
  现另存 `device_attempts` 并在 `listen` 的 wasapi 腿里带出。**实弹验证**：`device_attempts` 里能看到 `index/device/api/why` 四字段。

### 7.4 新增：耳朵第三条腿 `device=loopback`（系统播放回环 · 2026-10-18）

**为什么要它**：本机 `waveInGetNumDevs()=0`、三条 API 的 `default_input` 全是 `-1`、WDM-KS 引脚看得见却 0 帧 ——
麦克风那一路卡在 **Windows 没把采集引脚路由起来**，代码层面已经到底了。
但**扬声器状态是 OK 的** ⇒ 用 WASAPI 回环能录「电脑自己在放什么」，把「听 → 识别」这条链**先闭环证明通**，
不必等麦克风被启用。

| 项 | 内容 |
|---|---|
| 调用 | `cap voice '{"op":"listen","seconds":5,"device":"loopback"}'`（别名 `desktop` / `system` / `扬声器回环`） |
| 实现 | `voice_cap._record_loopback()` → `tools/codex-scripts/wasapi-loopback.py`（成熟件 **PyAudioWPatch**，自己写的只有取数与收尾） |
| 回执 | `leg:"loopback"`（**不许冒名 `wasapi-record`**）· `device:"扬声器 (Realtek(R) Audio) [Loopback]"` · `status:"no_frames"` 时带人话原因 |
| 判据 | `test_voice_gate_scopes.py::TestLoopbackLeg`（路由到回环件而非录音件 · 三个别名 · 回执 leg 自报 `loopback`） |

**诚实边界（一次实弹 + 一次未成，都写清）**：
- ✅ **接线证明**：走能力位真调回环件，回环端点被找到并打开，回执如实 `status:"no_frames"`，
  原因写的是「回环流一帧都没有：当前没有声音在播放（WASAPI 回环只在渲染端点有输出时喂数据）」——
  这是**等待放音**，不是坏件、也不是被拒。
- ❌ **未验**：真录到音频 → 再送离线识别这一段。要验它，得让扬声器**正在出声**
  （`cap voice '{"op":"speak",...}'` 或由主人在本机放点声音），并且在**票有效期内**。
  写这句时的读数：`privacy_read` 可用票 **0 张**（上一轮那张 `grant-1792335549266` 已在 600 s 窗口内消耗完）
  ⇒ 没有新票就不许再动采集口，**如实标「未验」，不拿单元测试冒充实弹**。
- 边界一遍：回环录**不到房间里的说话声**（那是麦克风的活），它证明的是「耳朵链路通 + 可做闭环演示」。


---

## 8. 2026-10-18 定稿：**对话式重排 + 真 3D + 台湾腔神经嗓 + 自卫层 v3**

主人当日三口调整（逐条对应实现）：

| 主人原话 | 落成什么 | 证据 |
|---|---|---|
| 「按照我们现在这个对话框设计然后加装我们的能力以及语音交互」 | 左列消息流（谁说的/几点/气泡/工具回执卡）+ 下边输入条 + 右侧她（3D）与链路体检；能力条 健康/任务/能力表/自检 走**壳桥真口** gbtW3.health/tasks/tools/selfcheck | chat-ui.js；C1–C5 全过 |
| 「严格按照源码并实现」→ 选 A「用已绑骨的 3D 模型」 | 撤掉静态 JPG，改吃工程资产 ssets/dh-v2-rigged.glb（6.4 MB · 65 骨 · idle 4.00s / walk 1.10s · 3 张内嵌贴图）+ 壳内 vendor 的 three/GLTFLoader（零 CDN）；ile:// 下 fetch 被拦 ⇒ 内联副本兜底（glb-inline.py 生成并 sha256 对账） | dh3d.js、dh3d-probe.cjs（舞台 ready ✅） |
| 「现在这个声音对了」/「还有其他声音参入」 | 嗓子只留 **edge-tts zh-TW-HsiaoChenNeural**：剧场默认音源换成 ssets/voice-greet-zh-tw.mp3（sha16 979762ecd928e58f）；壳桥新增 w3:say → 能力位 op=speak；把**自卫层**从 v2 升到 v3 —— 告警不再用 zh-CN SAPI 出声、页面正文命中只留证 | say-bridge-probe.cjs（spoken:true）、全仓 SAPI 出声点 359→1 |

### 8.1 三条"读数不准"的自查（都是自己先栽的）

1. **op=tts 与 op=speak 是同一个函数**：_dispatch 里两者并列落到 	ts()，差别只有 out。
   所以"一个通一个不通"不是两条腿，是**同一段代码两次结果不同**（上游瞬时失败）。
2. **
o_taiwan_lane 的原因原本是写死的**（「wss 403」）⇒ 看不到当场原话。已改：
eason 带 
aw 上游原文。
3. **_edge_tts 原来无论调用方要什么都会 os.startfile 播放** ⇒ 连"只写文件"也会突然出声
   （正是"还有其他声音"的来源之一）。已改：play=not bool(out)。

### 8.2 仍未验/仍未做（不许当成已做）

- op=tts 落盘那条路**没有在修完之后再实弹跑过**（票已过期），只跑了 25 条单元判据 ⇒ 标「未验」。
- 3D 模型的 idle 动作双臂原本是 V 字，已按轨道改成垂放，但**没有口型骨/形态键**：
  「在说」只用头颈与手势表示 —— 这是资产边界，不假装嘴动。
- 页面里 #gbt-direct-nav（全仓注入的直达链接条）已收成 24px、悬停展开；它由 page-reach.py 注入，
  要彻底改得动那个生成器（未做）。
