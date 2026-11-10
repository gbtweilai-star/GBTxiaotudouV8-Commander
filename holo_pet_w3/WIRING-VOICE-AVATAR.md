# 语音对讲 / 3D常驻 / 命令台 · 接线说明书（2026-11-06）

这一轮只补「建了但没接上」的线，不新造后端、不动能力位、不动 payload/。

## 1. 新增 3 件 + 改 2 处

| 文件 | 作用 |
|---|---|
| `avatar-roam.js`（新） | 3D 数字人跨页常驻层：任何页引了她就"她在场"。THREE 走本仓 vendor 三件（three.global.js + GLTFLoader.global.js），GLB 走 `assets/dh/dh-v7-detail.glb`。3D 起不来时兜底为平面拟球并如实记录原因（badge.title）。可拖动（位置记 localStorage）、双击休/醒。 |
| `console/tutorial-voice.js`（新） | 全程语音教程：首次进页她开口带你走（走 avatar 的 TTS），之后每页可说「小土豆 教程」重放。 |
| `console/commander-mode.js`（新） | 命令台（Ctrl+K）：她说出意图 → `window.gbtW3.cap → /_cap → run_task` 真能力位。已接：self_check / impact_check / body_see / caps_list / time_now / status_report / voice(tts)。危险/资金句式（转账、付款、关机、删库…）一律拒答并在台面上写明「必须终端 YES」。 |
| `console/voice-stream-panel.js`（改） | 最终/局部转写出来时派 `gbt-voice-final` 事件，教程与命令台据此接话。采集/上传/会话逻辑一行没动。 |
| `index.html` / `console/index.html`（改） | 各补 3 行 `<script>` 引用。 |

## 2. 设计红线（照仓内既定口径）

- 朗读只走能力位 `voice`（edge-tts → SAPI），不走浏览器 SpeechSynthesis 顶替；
  无桥（tentacle-bridge 不在）时不出声并在头像 badge 上如实写「无桥：不出声」。
- 事实纪律照仓规：灰状态一律带原因、取不到就不说拿到。
- 授权纪律照仓规：命令台没有同意键——危险/资金必须人工在终端 YES。
  被拒的话不是隐藏，是写在命令台 output 区。

## 3. 音色口径（本仓既定，不重设）

edge-tts → `zh-TW-HsiaoChenNeural` @ +15%；失败退 `SAPI Microsoft Hanhan`；
再失败就不出声并报原因，不许用大陆腔顶替。（voice_cap.py 已按此实现，本层只调 op = tts。）

## 4. 三字稿（供她朗读）——不是新加的逻辑，是既有的 spioc 条目的落点

- 「小土豆，自检」→ self_check 能力位
- 「小土豆，影响面」→ impact_check 能力位
- 「小土豆，看屏」→ body_see 能力位
- 「小土豆，能力目录」→ caps_list 能力位
- 「小土豆，几点了」→ time_now 能力位
- 「小土豆，念一句XX」→ voice(op=tts) 能力位
- 「小土豆，教程」→ tutorial-voice 重放

## 5. 遗留不拿（本轮正交，防复述成"已做完"）

1. Electron 本机不在 PATH → 桌面壳当前无法启动，按主人要求走网页版。
2. see_camera 仍无真 mmal/cam 桥——命令台没接它，因为这层"接了也只会假装拿到帧"。
3. package.json 里 20/28 个 UNIMPLEMENTED 占位脚本未动（本轮不扩库，只接线）。

## 6. 已核验证

- 4 个 JS 全部过 `node --check`（语法层面零报错）。
- 两份 index.html 的 6 条新 `<script>` 引用全部落到位（grep 核对过）。