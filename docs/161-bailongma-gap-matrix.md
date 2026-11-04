# 161 · 上游参考项目 → GBT 全能力对照 / 吞噬台账

> 对照对象：[xiaoyuanda666-ship-it/上游参考项目](https://github.com/xiaoyuanda666-ship-it/上游参考项目)（MIT，`main@e311c0d`，2026-11-02 抓取）。
> 读的是它的 `README.md`、`上游参考项目项目功能说明.md`（37KB，20 节）和实际源码目录，不是发布会文案。
> 口径：**只蒸设计与判据，不搬代码、不引它的 Node/Python 依赖**；能落成我们能力位/内核的才叫「吞了」，
> 只写进文档叫「登记」，不叫吞。状态：✅ 已有自研 / 🟡 有但不同 / ❌ 缺 / ⛔ 不吞（领域专属或不合我们红线）。

## 一、总表（20 组能力）

| # | 上游参考项目能力 | 它的实现（出处） | 我们的现状 | 差距 | 处置 |
|---|---|---|---|---|---|
| 1 | 持续运行主循环 / Tick 心跳 / 看门狗 / 任务续跑 | `src/index.js` 主循环 + 看门狗 + 启动自检 | 🟡 `gbt_allinone/proactive.py`、`energy_scheduler.py`、`task_manager.py`；无 Tick 主循环/看门狗统一体 | 缺少「常驻调度 + 失败续跑 + 自愈」一体 | **吞（P1）** 做 `loop_kernel`（Tick/看门狗/任务续跑），纯调度 + 门 |
| 2 | 记忆：SQLite 持久化 / FTS5 / 语义 / 用户画像 / 线索 / 焦点栈 / 审计 | `src/db.js` + `src/memory/*` | 🟡 `memory_bank.py`、`memory_manager.py`、`memory_sync.py`、`ring_context.py`、`context_vault.py`；非 SQLite FTS 同一套 | 无焦点栈、无线索模型、无画像表、无记忆审计视图 | **部分吞（P1）** 先 `focus_stack` + 记忆审计；SQLite/FTS 是否换存储要主人定 |
| 3 | 动态上下文注入 / 按需工具注入 / find_tool / 预取缓存 | `src/context/*` + `src/injectors/*` | 🟡 `ring_context.py` + `context_vault.py` + 能力检索（`skills_hub`） | 无预取缓存、无 UI 信号注入、无 find_tool 自发现闭环 | **吞（P1）** `context_inject` 判据 + 预取/信号两源 |
| 4 | 多模型 Provider / 激活 / 协议（Responses 与 Chat Completions）/ 迁移 / 模型列表 | `src/config.js` + `src/llm.js` | 🟡 本机指挥官（llama.cpp :8792）+ `llm/cloud_llm.py`；无 Provider 设置中心/双协议切换 | 无 UI 配置、无协议迁移、无动态模型列表 | **吞（P2）** 设置中心 + 双协议；不引它 Provider 清单 |
| 5 | 工具系统总成（通信/文件/Shell/Web/记忆/UI/提醒/媒体/安装/委托/工具市场/动态 API 槽） | `src/capabilities/*` | ✅ 390 能力位 + 统一门 `run_task`；文件/Shell/Web/媒体/安装/委托均有；**提醒/UI 卡片/工具市场/动态 API 槽无对应** | 4 块缺 | **吞（P1）** 提醒能力位（已登记待做）、ACUI 卡片、技能市场 UI、动态 API 槽；注册需主人点头 |
| 6 | Brain UI：聊天 / 思考流 / 行动流 / 记忆图 / 焦点线程 / 多面板 / 设置 | `src/ui/brain-ui/` | 🟡 console：对话/功能表/技能/3D 星图/世界/浏览器/大脑执行层/万能插/触手/思维导图/扫描…；**无思考流、记忆图、焦点线程、语音设置、ACUI 面板** | 5 个 UI 域缺 | **吞（P0/P1）** 先语音设置 + 思考流；记忆图/焦点线程随 #2 |
| 7 | 语音：ASR/TTS/设备/语音面板/自动发送/打断/唤醒 KWS/流式（载体=数字人） | `electron/voice-orb-preload.cjs`、`kws-process.cjs`、`src/voice/*`、`speech.js` | 🟡 既有 `voice` 能力位（Windows 离线听写 + edge-tts）+ **本轮新增语音球/五态/唤醒文本门/能量门/打断/朗读纪律** | 无 sherpa KWS、无 Whisper 流式、无 Provider 设置页 | **本轮已吞核心（docs/160）**；KWS/流式登记 P2（要模型/依赖，需主人点头） |
| 8 | 媒体：媒体舞台 / 音乐库 / AI 视频面板 / 媒体历史 | `src/media/*` + UI | 🟡 视频/出图/音乐有零散能力；无舞台/库/历史 UI | 统一媒体面板缺 | **吞（P2）** `media_stage` 只读聚合 + 播放器；不搬它的 Provider |
| 9 | 社交连接器：Discord / 微信桥 / 外部消息进同一主循环 | `src/social/*` | ❌ 仓内无微信/Discord 桥（`truthsocial.py` 是信息源，不是聊天桥） | 渠道接入缺 | **登记（P2）**；接不接微信桥要主人点头（涉及账号/风控） |
| 10 | 信息面板：天气 / 热点 / 世界杯 / 人物卡 / 文档面板 | `src/information/*` + `src/hotspots.js` | ❌ 无独立件（此前明确「没有的领域不摆空壳」） | 5 个领域面板缺 | **不吞领域专属**；只吞「面板协议」到 #13 ACUI，内容源按主人需要再接 |
| 11 | 本机资源感知：系统/桌面/软件/本地 Agent/SSH/Git/地理天气 | `desktop-scanner.js`、`device-information-scanner.js` | 🟡 `selfscan.py`、`preflight.py`、`scan` 仪表盘 | 缺地理/天气与软件清单的统一快照 | **吞（P2）** `host_profile` 只读快照 |
| 12 | 配额 / 限流 / Turn Trace / 行动日志 | `src/quota.js` + `db` | 🟡 有成本账本 / 审计 jsonl / `cap_self`；无回合轨迹视图 | 缺 trace 查询面 | **吞（P2）** 只读 trace 页 |
| 13 | Scene Protocol / Agent 驱动 UI / ACUI 卡片（天气/自检/图片/视频/确认） | `SCENE-PROTOCOL.md` + `ACUI (Remix)/*` | ✅ **P0 已落**：自有 `ui_card` 能力位（schema/白名单/纯文本/TTL/最多 20 张；动作只回 `ui_card_action` 事件 `executed=false`）+ `/api/ui/cards` + console 卡片栈 + 审计 jsonl | 主循环事件消费器/SSE 推送/富媒体卡仍待接 | **已吞（P0）** 见 `docs/163` |
| 14 | 浏览器：BrowserSkill 接管真实 Chrome Agent Window + app 内 `browser-embed-host`（`WebContentsView`） | `docs/browserskill-backend.md`、`electron/browser-embed-host.cjs` | ✅ **P0 已落**：自有 `browser_embed`（`WebContentsView` 宿主：标签/地址栏/前进后退/下载/分区/权限 deny/边界 clamp）+ 契约 `browser_embed.py` + 真机 example.com/标签验证；外部 Chrome `native_browser` 保留为另一条腿 | 已不再用页面内 `<webview>` 冒充；OAuth 弹窗/历史 UI/真下载读数待补 | **已吞（P0）** 见 `docs/162`；剩余项见边界 |
| 15 | 局域网访问：配对链接 / 临时证书 / 移动端共享会话 | `README` + `scripts/start-lan*` + `src/api.js` | 🟡 有 `mobile/`（Capacitor）+ 回环服务；无配对/证书/共享会话 | 局域网安全接入缺 | **登记（P2）**；证书/配对要主人点头 |
| 16 | 自动更新 / 安装包签名 / 启动进度 / 托盘 / 单实例 | `electron/main.cjs` + electron-builder | 🟡 桌面壳有单实例/托盘基础；无更新与签名流程 | 发布面缺 | **登记（P2）** 属打包面，不冒充已做 |
| 17 | 安全访问控制：本机默认 / 敏感接口 / API Token / 确认流程 | `src/api.js` 安全段 | ✅ 我们更严：统一门 + policy + 审计 + 红线 | 无 Token/配对体系 | **部分吞**：只取「敏感接口分级」思路，不引它的 token 体系 |
| 18 | 工具市场 / 自定义工具安装 / 动态 API 能力槽 | `src/capabilities/tools/*` + slots | 🟡 `skills_hub` 有技能安装/校验；无「动态 API 槽 + secret store」 | 动态能力注册缺 | **吞（P1）** 动态 API 槽（schema → 门 → secret 只存引用） |
| 19 | Agent 驱动 UI / 焦点横幅 / 多窗口 | `electron/*` | 🟡 单窗 console + 浏览器/世界等视图；无焦点横幅/多窗 | 多窗/焦点缺 | **吞（P2）** 先单窗卡片（#13），多窗后置 |
| 20 | 语音/媒体/TTS 的 Provider 设置与凭证 | `src/config.js` + 设置页 | 🟡 有 `settings.js`；语音只有默认台湾腔，无 Provider 设置 | 配置面板缺 | **吞（P1）** 语音设置页（TTS 音色/语速/设备 + 凭据只存引用） |

> 说明：本表按「能力面」归并，不按文件数堆；上游参考项目的领域数据源（热搜/世界杯/人物卡/天气）**不摆空壳**，
> 只吞承载它们的 UI 协议（#13）和可选数据源接口。
| 21 | body_control（身体控制 / 触手 / 全息投影） | 主人定名 + 状态纪律：深度学习+无模型≠能动 | ✅ 状态口已落：`body_control` 能力位 + `/api/body` + 右栏状态；默认 **not_supported**，全绑定也最多 partial 且 `executed=false` | 没有真实传感器/执行器/安全闭环 | **如实报缺**（不是吞成能动；docs/166） |
| 22 | 主人追加：视频能力全融合 + 每页触手脉冲/双向链 | 主人 2026-11-03 | ✅ 视频舱 33 件六段编目（`video_hub`）+ 页面触手网格（21 页/420 链/共享缓存） | 编目不执行；页间总线是前端逻辑链，非 420 真实进程 | **已落**（docs/180/181） |
| 23 | 主人追加：参考图 → 可拆解 3D 交互页（Salticus JS-8） | 主人 2026-11-03 | ✅ Skill `ref-to-3d` + 能力位 `ref3d` + `/teardown/`：我们的数字人 DH-V7（1 mesh/66 bones/本地 GLB） | 参考图只给外观；旧 Salticus/dh-live 已清；不是物理仿真 | **已装**（docs/182） |
| 24 | 主人追加：email_cap 审计 0 能力 | 主人 2026-11-03 | ✅ email_cap 别名 → 真实 coze_mail（闸门/配额/账本在；transport 未接线如实报） | 审计只认字面名会误报；真出网仍缺端点/凭据 | **已修**（docs/183） |
| 25 | 主人追加：触手必须和所有页面双向绑定 | 主人 2026-11-03 | ✅ 生成器 + state/page-bindings.json：20 页 ↔ 410 能力位全绑；page_scan 20/20/0 | 运行时红/黄仍要 page_scan 实测 | **已补**（docs/184） |
| 26 | 主人追加：用原生扫描深查 | 主人 2026-11-03 | ✅ selfscan/file_hygiene/signature/inventory/truth/page_scan status 复扫 clean；BOM 25 文件清、wf_runs 补 | capability_net 70/410、66 组重复文档、page_scan scan 超时仍留案 | **已查**（docs/185） |
| 27 | 主人追加：不要拿“诚实边界”当工作成果 | 主人 2026-11-03 | ✅ git_write 补 push/force_push/rebase/reset，临时仓+本地裸远端真跑；confirm/network/destructive 标记；Windows git 路径兜底 | push 仍按出网门放行；不是裸 force | **已做**（docs/186） |
| 28 | 主人截图：PAGE MESH 压住右栏 | 主人 2026-11-03 | ✅ HUD 进入布局槽；APP payload selfscan/signature/inventory clean | legacy 仍留 66 组重复文档 | **已修**（docs/187） |
| 29 | 主人追加：清 66 组重复文档、verified 5/410、has_test 2/410 | 主人 2026-11-03 | ✅ 66 组旧文档归档 docs/legacy；台账 verified 267/410、has_test 300/410（真探针/测试引用） | latent 影子目录 assets/deploy 是真实资产，未为扫描好看搬走 | **已清/已核**（docs/188） |

## 二、本轮真正吞进来的（不是登记）

| 项 | 落点 | 验收 |
|---|---|---|
| 数字人页 PTT + 状态灯 + 对话面板 | `holo_pet_w3/dh-live/{index.html,dh-live.js}` | 真机打开 / 按住空格或点 MIC / 气泡显示听到与回复 |
| 唤醒词文本门（先喊名字，剥问句） | `gbt_allinone/tools/voice_intercom.py` | 27 项内核自检 |
| 能量门 / 打断（只在 speaking 且能量过线） | 同上 | 自检 + 单测 |
| 朗读纪律（Markdown 剥离 / 纯表情不念 / 1000 字上限） | 同上 | 自检 |
| 一轮对讲 API（listen→chat→say，走 `voice` 能力位门） | `tools/console-server.py` | `status/say/audio/listen` 真跑 |
| 数字人语音对讲测试 | `tests/test_voice_intercom.py` | 29 项 ALL OK |
| 文档 | `docs/legacy/160-voice-intercom.md` | — |
| **我们自己的原生浏览器 browser_embed**（WebContentsView 宿主） | `gbt_allinone/tools/browser_embed.py` + `holo_pet_w3/shell/browser-embed-host.cjs` + `resources/app/{main.js,preload.js,browser-embed-host.cjs}` + console 标签条 | `tests/test_browser_embed.py` 21 项 + 真机 example.com/标签/URL 拒绝 |
| 文档（原生浏览器） | `docs/legacy/162-native-browser-embed.md` | — |
| **ACUI 卡片协议 ui_card**（纯数据/白名单/TTL/动作只回事件） | `gbt_allinone/tools/ui_card.py` + 能力位 `ui_card` + `/api/ui/cards` + `holo_pet_w3/console/ui-cards.js` | `tests/test_ui_card.py` + 真机创建/动作/关闭/坏卡拒 |
| 文档（ACUI） | `docs/legacy/163-ui-card-acui.md` | — |
| **语音设置页**（音色/语速/音高/ASR 后端/自动朗读） | `gbt_allinone/tools/voice_settings.py` + 能力位 `voice_settings` + `/api/voice/settings` + 数字人 ⚙ 弹窗 | `tests/test_voice_settings.py` + 真机保存/回读/坏值拒 |
| 文档（语音设置） | `docs/legacy/164-voice-settings.md` | — |
| **焦点栈 + 记忆审计 focus_stack** | `gbt_allinone/tools/focus_stack.py` + 能力位 + `/api/focus` + 右栏焦点面板 | `tests/test_focus_stack.py` 22 项 + 真机 push/pop/审计 |
| 文档（焦点栈） | `docs/legacy/165-focus-stack-memory-audit.md` | — |
| **body_control 状态口（如实报缺）** | `gbt_allinone/tools/body_control.py` + 能力位 + `/api/body` + 右栏状态块 | `tests/test_body_control.py` 22 项 + 真机 not_supported/动作拒 |
| 文档（body_control） | `docs/legacy/166-body-control.md` | — |
| **上下文注入 context_inject** | `gbt_allinone/tools/context_inject.py` + 能力位 + `/api/context` + 右栏预览 | `tests/test_context_inject.py` 22 项 + 真机预算/去重/过期 |
| 文档（上下文注入） | `docs/legacy/167-context-inject.md` | — |
| **思考流/行动流 thought_stream** | `gbt_allinone/tools/thought_stream.py` + 能力位 + `/api/stream` + console「思考流」视图 | `tests/test_thought_stream.py` 20 项 + 真机 100 条真实编排账 |
| 文档（思考流） | `docs/legacy/168-thought-stream.md` | — |
| **动态 API 槽 api_slot** | `gbt_allinone/tools/api_slot.py` + 能力位 + `/api/slots` + 右栏面板 | `tests/test_api_slot.py` 25 项 + 真机注册/call not_supported/坏槽拒 |
| 文档（API 槽） | `docs/legacy/169-api-slot.md` | — |
| **提醒能力位 reminder** | `gbt_allinone/tools/reminder.py` + 能力位 + `/api/reminders` + 右栏提醒面板 | `tests/test_reminder.py` 27 项 + 真机创建/取消/due |
| 文档（提醒） | `docs/170-reminder.md` | — |
| **本机资源快照 resource_snapshot** | `gbt_allinone/tools/resource_snapshot.py` + 能力位 + `/api/resources` + 右栏资源面板 | `tests/test_resource_snapshot.py` 18 项 + 真机 CPU/内存/磁盘/uptime |
| 文档（本机资源） | `docs/legacy/171-resource-snapshot.md` | — |
| **媒体舞台/音乐库/历史 media_library** | `gbt_allinone/tools/media_library.py` + 能力位 + `/api/media`（索引/文件 Range）+ console「媒体舞台」 | `tests/test_media_library.py` 22 项 + 真机 28 件/预览播放 |
| 文档（媒体舞台） | `docs/legacy/172-media-stage.md` | — |
| **轮次追踪 Turn Trace** | `gbt_allinone/tools/turn_trace.py` + 能力位 + `/api/turns` + console「轮次追踪」 | `tests/test_turn_trace.py` 21 项 + 真机 6 轮/42 步/证据 42 |
| 文档（轮次追踪） | `docs/173-turn-trace.md` | — |
| **配对/证书安全原语 pairing** | `gbt_allinone/tools/pairing.py` + 能力位 + `/api/pairing` + 右栏配对面板 | `tests/test_pairing.py` 24 项 + 真机码/claim/撤销/指纹 |
| 文档（配对） | `docs/174-pairing-cert.md` | — |
| **局域网监听/自签证书 lan_pairing** | `gbt_allinone/tools/lan_pairing.py` + 能力位 + `/api/lan` 启停 + TLS health/pair/status | `tests/test_lan_pairing.py` 28 项 + 真机 192.168.1.144:8767/TLS/401/stop |
| 文档（局域网监听） | `docs/175-lan-pairing.md` | — |
| **更新清单/签名校验 update_verify** | `gbt_allinone/tools/update_verify.py` + 能力位 + `/api/update` + 右栏校验 | `tests/test_update_verify.py` 22 项 + 真机 Ed25519/篡改拒/不安装 |
| 文档（更新校验） | `docs/176-update-verify.md` | — |
| **本地更新测试链 update_chain** | `gbt_allinone/tools/update_chain.py` + 能力位 + `/api/update-chain` + 面板 | `tests/test_update_chain.py` 20 项 + 真机 stage/confirm/rollback 8.0.1-test↔8.0.0-local |
| 文档（本地更新链） | `docs/178-update-chain-local.md` | — |
| **流式语音 voice_stream** | `gbt_allinone/tools/voice_stream.py` + 能力位 + `/api/voice/stream` + 右栏流式面板 | `tests/test_voice_stream.py` 20 项 + 真机 start/chunk/end 静音链 |
| 文档（流式语音） | `docs/177-voice-stream.md` | — |

## 三、下一批吞噬顺序（P0 → P2，逐项带契约/门/测试/APP 接线）

### P0（进度：browser_embed ✅ · ui_card ✅ —— P0 两件完成）

1. ✅ **`browser_embed` 我们自己的原生浏览器 — 已完成（docs/162，21 项验收）**
   - 参考只取架构：WebContentsView 子视图 + 主进程管理（分区/下载/权限/窗口尺寸）+ 页面侧卡片外壳；
   - 我们的落法：`gbt_allinone/tools/browser_embed.py` 只做**状态协议/白名单/事件账**（纯函数、可测）；
     Electron 主进程 `resources/app/main.js` 增加 `WebContentsView` 宿主与 IPC（地址栏/前进后退/刷新/标签/下载/关闭）；
     console「浏览器」页从 `<webview>` 升为宿主控制条（同一 UI 可降级到 webview）；
   - 门：页面文字仍按外部内容纪律；下载/上传走 `filesystem_write`；不引 BrowserSkill/腾讯依赖；
   - 验收：本地 example.com、下载一枚小文件、开两个标签、关闭一个不影响另一个、文字阅读标记「不可信」。
2. **`ui_card` ACUI 卡片协议**
   - schema：`{kind, title, body, actions[], ttl, source}`；白名单 kind（weather/selfcheck/wake/image/video/confirm）；
   - 渲染：console 右下卡片栈；动作只回发事件给主循环，不直接执行；全部落审计；
   - 验收：坏 schema 拒、未知 kind 拒、动作需确认、TTL 过期、审计有据。

### P1（体验/记忆/设置 · 六件已全落）

3. ✅ 语音设置页（TTS 音色/语速/音高/音量 + ASR 后端 + 自动朗读；见 docs/164）；
4. ✅ `focus_stack` + 记忆审计只读视图（见 docs/165）；
5. ✅ `context_inject`（预取缓存 + UI 信号两源，按轮次预算；见 docs/167）；
6. ✅ 思考流 / 行动流（真实读编排账归一化五类；见 docs/168；轮询非 SSE）；
7. ✅ 动态 API 槽（schema → 门 → secret 引用；见 docs/169；只登记定义，call=not_supported）；
8. ✅ 提醒能力位（`reminder`：创建/列出/取消，写面过 filesystem_write；见 docs/170）。

### P2（发布/生态/硬件）

9. ✅ 媒体舞台/音乐库/历史（只聚合既有产物；见 docs/172）；10. ✅ 本机资源快照（见 docs/171）；11. ✅ Turn Trace 页（见 docs/173）；
12. ✅ 局域网配对/证书（主人批准 LAN-only）：安全原语 + 私有 LAN TLS 监听/自签证书（docs/174/175）；无 CA/轮换、无远程命令；13. 🟡 自动更新/签名：离线验签（docs/176）+ **本地 hash-only 安装链**（docs/178，无密钥）；生产下载/安装器/发布身份仍未接；
14. ✅ 真 KWS/Whisper 流式：PCM16 流式采集 + 局部/最终 Whisper + **sherpa-onnx 声学 KWS（小土豆，本机/无密钥）已实测**（docs/177/179）。

## 四、不吞清单（说清，不装）

| 项 | 为什么不吞 |
|---|---|
| 热搜/世界杯/天气/人物卡等**领域数据** | 我们之前定过「没有的领域不摆空壳」；只吞承载协议（ACUI），数据源主人点名再接 |
| 它的 Provider 清单 / 搜索后端 / 嵌入模型 | 不是设计，是第三方服务绑定；我们要自己的 Provider 设置 |
| sherpa-onnx KWS / Whisper 打包 | 依赖体积与模型许可要主人拍板；当前用 Windows 离线识别 + 文本唤醒门 |
| 腾讯 BrowserSkill CLI / 微信桥 | 第三方运行时/账号风险；只取「接管真实 Chrome」的架构，不引 CLI |
| 其 SQLite/FTS 具体 schema | 存储可以换；先吞「焦点栈/画像/审计」判据，不搬表结构 |

## 五、怎么验这张表

- 本表每一项「吞」都必须有：**能力位/模块 + 门 + 测试 + APP 接线**四件，缺一件就退回「登记」；
- 当前本轮：语音对讲 = 四件齐（见 §二）；其余为登记/排期，**不冒充已做**；
- 每轮完成后更新本表状态与 `docs/legacy/README.md` 行。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
