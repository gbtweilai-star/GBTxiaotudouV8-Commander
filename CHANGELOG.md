# 变更记录

## 2026-11-01 · 第十五批：手部两枚原生位 + 双仓同步 + 巡检位

- **手部原生位**：`hand_retarget`（21 点 → 关节角，几何法/非 IK）· `hand_bridge`（loopback 真跑 + Modbus TCP 真帧；真机需 register_map）；能力位 **368**。
- **双仓同步工具**：`tools/two-way-sync.ps1` + `tools/codex-scripts/two-way-sync.py`（sha1 对账/静默守卫/备份/刷新链）；交付树与 live 现为 **ALIGNED（368/368）**。
- **巡检位 `sync_guard`**：status/verify/patrol/where；DRIFT 出 alerts；`notify=true` 写审计 + 推送（webhook/飞书/n8n/桌面 toast）；工作流 `双仓同步巡检` + 每 6 小时计划任务 + 登录自启。
- **补齐**：`test_catalog` 条数改现算（不再写死 341）；`docs/README` 索引补 51–54、74–75；`capabilities-full.json` 仍为 2026-10-25 的 349 旧快照（已在索引注明）。
- 交付读数：**2707 文件 / 135.5 MB**；`cap_self` 368=368=368；audit 14/0（462 项）；bindings 18/0。

## 2026-11-01 · 第十四批：主干换成自己的脑子（权重融合 + 四合一 + 自知 + 自动插口）

- **主干判决改走自有权重**：新增能力位 `commander`（`gbt_allinone/tentacle/commander.py`）——
  盘上的 `gbt-v8-v82-q5_0.gguf`（5.24 GB，sha256 与 WEIGHTS.md 逐字相同）经 llama-server
  在 `127.0.0.1:8792` 本地推理，`semantic_route.choose()` 的第一顺位换成它，云端车道退居第二档。
  实测：「塞进剪贴板」→ `clipboard_copy`、「扫描漏洞」→ `sec_scan`、「有哪些窗口」→ `see`；
  冷启 2.6 s、生成约 2.8 tok/s（纯 CPU 12 线程）；`tentacle op=plan` 返回 `lane=commander_local_weights`。
- **四合一原生位 `pulse_core`**：脉冲（一次拿全身状态）· 量化压缩（Q5_0 相对 fp16 **2.71×**）·
  按需激活（`--sleep-idle-seconds 600`，闲置卸权重、来请求再醒）· 精准直达（召回先兜住全部能力位+触手方法）。
  `op=verify` 真跑四条判据，任一不成立即红。
- **能力自知 `cap_self`**：`has` / `list` / `ask` / `brief` / `verify`。`verify` 做**三源对账**
  （注册表 ↔ `data/capabilities.json` ↔ `api.py` 分派）；实测 **354 = 354 = 354**，漂移即红。
- **万能插自动打开 `omni_open`**：不再写死六类插座，而是**扫出来的**——本轮 35 根
  （port24 / ai5 / file3 / process3）；每次能力调用前自动过一遍（廉价探针 + 60s 缓存，重扫在后台不挡调用）；
  增量对比（新增/拔掉/通断翻转）会进 `alerts`。
- **代码图谱补齐**：`gbt_allinone/tools/code_graph.py` 此前**模块不存在**（注册表有、分派有、一调 ImportError），
  现按 desc 实现：665 文件 / 10,137 符号 / 98,280 条边 / 0 未解析。
- **修一个静默坑**：10 个 `.py` 带 UTF-8 BOM —— Python 导入无感，但任何 `ast.parse` 的工具都会静默少扫一批文件；
  已全仓剥除，并让 `code_graph` 用 `utf-8-sig` 读。
- **署名覆盖补漏**：`signature_guard` 的扫描面此前**不含仓库 `docs/**/*.md`**（77 页只有 8 页带署名却一直报绿）；
  新增 `scope=all` 口径并用工具自己的 restore 补回 69 页，现 **100/100 clean**。
- **诊断栈清零**：`selfscan` clean（补建 `store/wf_runs`）· `ghost_guard` clean · `sec_defenses` 5/5 ·
  `truth_scan` FAKE=0 · `cross_scan` hard=0（仅剩 4 条 W 维 latent：根与包内同名目录，属形态非缺陷）·
  `inventory`/`file_hygiene` clean（新增 checkout 形态判定，29 项假异物归零，home 形态读数不变）。
- **落地脚本**：`tools/commander-install.ps1`（六步幂等：权重→sha256→指针→起引擎→自检→可选守护/自启）·
  `tools/commander-supervisor.ps1`（health 守护，实测 kill 后 **7 秒自愈**）。登录自启因沙箱无权限**未注册**，如实记在 docs/47。
- **判决层**：478 项逐项真跑（`tools/codex-scripts/commander-coverage.py`，可断点续跑），抽样 60 项 **56/60 = 93.3%**；
  7 个 miss 全部是**模型辨别力**问题（目标全在候选里，最差排第 9），不是接线问题。
- **短意图路由修复（docs/52–53）**：人写短意图（"审计"/"体检"/"镜像"）命中只有 1/6，而**召回 100%** ——
  进一步定位到"模型在 12 个候选里选错兄弟位"。改法不是调模型而是**收窄候选**：
  命中 `data/intent-lexicon.json`（人写词表）时，把候选压到人点名的那几位（`route(..., use_lexicon=True)` 默认开，可关）。
  实测同一批短意图 **1/6 → 5/5**；词表从 24 条扩到 **36 条**，并消解了 6 组重复 `say` 词（重复会让收窄并集变脏，实测 `体检` 因此选错）。
  新增 `tests/test_lexicon_scope.py`（9 条，离线）钉住三条性质：**命中才收窄 · 收窄不替模型拍板 · 词表自身干净**。
- **两把尺子分开报（docs/50–52）**：478 项合成基准（desc 回环）量"可达性上限"；24 条人写词量"短意图真实可用性"，
  两个数**并列写、不混成一个**。实测结论：召回两把尺子都接近满，错在判决；且**置信度区分"有没有把握"、不区分"对不对"**
  （孪生位误选的置信度 0.993/0.999）。
- 新增测试 8 份：`test_commander_trunk` / `test_pulse_core` / `test_cap_self` / `test_omni_open` /
  `test_omni_open_diff` / `test_alerts_sockets` / `test_inventory_checkout` / `test_code_graph`，全绿。
- **换机器重装的三个工具收编进仓**（此前只躺在工作区临时区，换台机器就得重写）：
  `tools/dl-weights.js`（分片下载，带重试/断点跳过）· `tools/merge-weights.py`（按序合并 + 魔数/大小校验）·
  `tools/probe-all.py` + `tools/probe-one.py`（逐能力过唯一门探针，`PROBE_LIMIT=N` 限量）。
  收编时做了三处仓化：路径按 `tools/` 的上一级算仓库根、能力清单改读仓内 `data/capabilities.json`、
  解释器走 `GBT_PYTHON` 或 `pyembed/python.exe`；无参调用给用法而不是抛栈（实测 `PROBE_LIMIT=3` → `{"ok": 3}`）。
- **文档索引对齐**：`docs/README.md` 的 348 → 354（现读）、`能力总表.md` 死链换成 `03-capabilities.md` + `capabilities/`，
  另 9 份本快照不存在的文档改为纯文本 + 「本快照无此文件」标注；根 README 的 `docs/并发容量登记.md` 同样标注。
  两个索引现在**死链 0**；`docs/01-model-card.md` 的只读/需授权数改为现算（313 / 41）。

## 2026-10-25 · 第十三批：能力面统一 348 + 采纳朋友圈三条建议

- **口径统一到注册表现读 348 位 / 30 域**（原 README 写 341 = 2026-10-21 权重发布快照）。
  多出的 7 位是 `body_*`（`device` 域身体桥：see/say/open/click/type/map/volume，10-24 之后补）。
  README 与 `docs/03-capabilities.md` 都写清「两套数不是一个数」；**测量读数仍保留 341 快照并标注**
  （341 位全量真跑 340 通过 / 0 失败；236/341 多域监控；74 位未测），不把快照读数改写成 348。
- **分域表新增两列**：`必填载荷`（从 `PARAM_REQUIRED` 现读，25 位登记；未登记写「无必填」，不猜）与
  `常见错误`（静态三层：`denied: missing_scopes` / `user_error` / `needs_dependency` 与 `needs_input`）。
  30 份域页 + 逐位详解全部重生成。
- **采纳「提交前重观测」**：`tools/control_loop.py` 新增 `commit_guard()` —— 提交前重拍一张，比同一
  `target_index` 的 label 与中心点位移（默认 12px），超限退回 `WAIT` 并落 `drift_px`；
  `act_real(execute=True)` 给了 `fresh_obs` 就先在动作门外挡。判据 `test_control_loop_commit_guard.py` 9 条
  （含「闸没过时门一次都不许被调」负控）全绿。
- **采纳「发布键留给人」**：社交发布默认草稿模式（工具在 `outputs/poster/tools/`，不进本仓）。
- 说明：本次只改对外表述与文档生成器；**能力面本身没有新增/删除**（341 → 348 是补齐 7 个身体桥位的登记），
  评测与逐位真跑读数未重跑，故一律标快照。


格式：`日期 · 版本 · 一句话`。只记**对外可见**的变化。

## 2026-10-25 · 第十二批：手机版补齐实拍（iPhone 上真跑我们自己的 `q5_0`）

- **新增三张真机截图**（`assets/mobile-lm-pocket-chat.png`、`mobile-ios-worker-queue.png`、`mobile-ios-run-recap.png`），
  README 中英两版在「手机版」一节各加了一小节 `手机实拍（不是 PWA）`：iPhone 用 **LM Pocket** 直接加载
  **`gbt-v8-v82-q5_0`（GGUF · 4.88 GB）**、本机芯片推理；工作器把 3 条问题排队、结果自动落 `/tmp/a19_done.jsonl`；
  以及「今晚这一整轮的账」那张表（Q4_0 的 9% 量化噪声被 28 层放大 0.22→605 · Q5_0/Q8_0 稳定 6.19 ·
  339/339 张量 · A19 直连 8–11.7 tok/s · iOS 后台约束）。
- **口径写死**：截图里的数字是**页面自报**，本仓不替它重算；这三张证明的是「手机上跑的是我们那份 q5_0、
  且 Q4_0 是坏样本」，不是「所有量化都坏」。与 `docs/APP-自有权重.md` §十一 的五份实测同向。
- 不改动其它任何页面与读数。

## 2026-10-21 · 第十一批：出片真落片（免费 GPU · 27.0s · 49,893 B · sha_match=true）

主人问「为什么不跑一次出片」—— 跑了，而且这一轮落到了本地：

- 门现状：`comfy_cloud op=freegpu` 默认拒（`missing_scopes: ["network_private"]`）；主人发
  `grant-1792576825272`（时段票）后真跑。
- 真读数：`route=free-hf` · `Sneezemande/wan22-comfyui-demo` · `zero-a10g(免费 GPU)` · **27.0s** ·
  **2s / 480×480** · `outputs/cloud/hf-free-gpu/freegpu-20261021T170305.mp4` · **49,893 B** ·
  sha256 `d07b61397c1c9cf5bd539630b437f52a9d7f128e078d3633195a44fa376c1fcd` · **`sha256_match=true`** ·
  付费卡现读 **RUNNING 0 / 共 15**（先量付费卡，再转免费档，全程留档）。
- 编码复核（ffprobe 现读）：**h264 · 480×480 · 49 帧 · 2.04s**；抽帧亲眼看
  `outputs/cloud/cable-all/frames/freegpu-new-frame20.png`。
- 表第④行主账改成这条真片；Agnes 那条腿（反向调用通、回传 200+Not Found）作为并排记录保留，
  不删不盖 —— 「调用」和「取回」两件事分开记。
- 修掉一处自己刚犯的读数错：`cable_freegpu()` 第一版只读信封第一层，`result.ok` 明明是 `true`
  却被读成"未出片" ⇒ 改成往里挖到「带 `ok`+`op` 的那一层」，再跑才拿到真片。

## 2026-10-21 · 第十批：**只要密钥跟云端联通了，就能反向调用** —— 出片那根电缆真契约问出来了

- **口径按主人令写死成一句无条件的话**：**只要密钥跟云端联通了，就能反向调用**。
  不需要云卡、不需要本地 GPU、不要求模型跑在自家 pod 上。写进了 `docs/13-omni-plug.md` 的
  §三 与 §电缆模型、`README.md` 亮点第 4 条、以及 `assets/fig-cable-all.png` 的表头与页脚。
- **Agnes 视频真契约（现场逐字段问上游问出来的）**：
  `POST /v1/video/generations {model, prompt, mode:"text"}` → `task_id` → `GET /v1/videos/{task_id}` 轮询 →
  `completed`（本次 **43 秒 / 5s / 720P / 100%**）。`mode` 已知取值 `text`、`keyframe`（后者要 `first_frame`）；
  `duration` **不是允许字段**，`seconds`/`size` 由服务端定。
- **纠正一条旧读数**：上一轮写的 `invalid_json · Failed to read request body` 不是"端点不通"，
  是上游把"体里缺 `mode`"折成了哑话 —— 按字段一个个问（空体→缺 model→缺 prompt→缺 mode→duration 不许→mode 非法）
  才问出真契约。旧的"我不猜"这句已经作废：**不是不能猜，是得问。**
- **反向调用是通的，坏的是"取回"**：网关自己发的 `result_url`（`/v1/videos/{task_id}/content`）连试 12 次 / 84.8 秒，
  每次 **HTTP 200 + `{"detail":"Not Found"}`**。表第④行如实写 **「通（回传坏）」**——不许拿"取回不了"反过来说"调用没通"。
  出片这件事本身有真 mp4（HF 免费 GPU 那条电缆 `route=free-hf`：73,884 B · sha256 `7a2f0ca6…`）。
- **修掉两处假账**：`probe-cable-all.py` 的 `cable_video()` 旧 body 缺 `mode` 且多传 `seconds`（已按真契约改写，
  提交/轮询/取片全链 + 12 次重试留档 + 记 `finish_seconds`）；`render-cable-all.py` 第④行原来**写死"未通"**、
  第①行 `our_model` **没有写手**（上一轮是手抄进 JSON 的）⇒ 现在补了 `cable_our_model()` 真跑产出，
  四行全部由 `data/cable-all-live.json` 现读驱动。
- 现读四根：① 我们的模型 `http=200 · 1.2s · 397 tokens` · ② 批量出图 **3/3 · 29.7s** ·
  ③ 本机 CPU **0.0535s · 321.1 GFLOP/s** · ④ 出片 **云端 43s 出活** / 回传坏。
- 图重渲染 `assets/fig-cable-all.png`（按 P7 亲眼看：修掉 ① 列错位、`\n` 破版、④ 状态挤字三处）。

## 2026-10-21 · 第九批：340/341 —— `comfy_cloud` 接上 HF 免费 GPU 腿

- 主人令「没有空闲 GPU 就自动调云端免费 GPU」⇒ 新增 `comfy_cloud op=freegpu`：
  **先量付费卡（现读 15 张全 EXITED / 0 运行）→ 自动转 HF 免费节点出片 → 产物逐字节落盘 + sha256 对账 → 回执写明 `route`**。
- 过门真跑：`route=free-hf · Sneezemande/wan22-comfyui-demo · zero-a10g(免费 GPU) · 29.3s · 73,884 字节 · sha256 7a2f0ca6…`；
  产物 `outputs/cloud/hf-free-gpu/freegpu-20261021T161333.mp4`，证据 `data/comfy-freegpu-live.json`。
- 作用域只登记一条：`network_private` + `filesystem_write`（**不叠 `data_export`**）；既有闸一条未动。
- **终账：340 通过 / 0 要票 / 1 缺输入 / 0 缺依赖 / 0 失败 = 341**（只剩 `codex_interrupt`：上游 app-server 串行化）


## 2026-10-21 · 第八批：339/341（最后一位「要票」真跑通过）

- **`pentest` 转绿**：主人发 `network_private` 后当轮真跑 ——
  `op=authorize` 登记 `127.0.0.1:8080`（受管动作）→ `op=verify` 拿到 **`tcp_reachable ok:true · 2.7ms`**、`findings:[]`、票已消耗。
  口径没变：**非破坏性**（TCP 可达 + TLS 握手 + GET 响应头，不爆破/不写/不改）+ **未登记目标一律拒**（本轮实测到
  `目标未登记授权:127.0.0.1:8080` 的拒绝原话，先登记才放行）。
- **阴性/阳性都留了证据**：先验 `127.0.0.1`（80 端口没人听）得 `ConnectionRefusedError [WinError 10061]` —— 那是目标没起；
  再起本机监听验 `127.0.0.1:8080` 才拿到阳性。探针 `probe-offense-live.py` 自带监听、用完即杀。
- **终账：339 通过 / 0 要票 / 1 缺输入 / 1 缺依赖 / 0 失败 = 341**
  （只剩：`codex_interrupt` 卡上游串行化 · `comfy_cloud` 云卡未起）


## 2026-10-21 · 第七批：补上「万能插」这一页（万物皆可插 · 万物皆可控 · 反向调用云端算力）

之前的能力总表只讲「341 位各是什么」，**没讲"她凭什么能插一切、控一切、还能反向烧云端 CPU/GPU"** —— 这一页补它：

- **`docs/13-omni-plug.md`**：六类插座（`process` / `file` / `api` / `web` / `app` / `ai`）逐类写清
  「能插什么 / 插上能干什么 / 要过哪道门」；三条铁律（不攻击 · 凭据只从 env 取且绝不回显 · 每插每跑都落账）。
- **万物皆可控**的口径写死：341 位 + 触手 + 外部 CLI 助手 + MCP/浏览器/桌面，**全部过同一道门**，
  「可控」= 有一道门 + 每次过门都有账，不是"能力声明"。
- **反向调用云端算力（CPU/GPU）** 单独一节：
  · `pod_link`（云卡触手）13 个 op：读类 `status/ls/where/logs/ports/account/gpus`、传类 `up/down`、
    跑类 `run`（**在卡上真跑命令**）、花钱类 `create/start/stop`（必须 `confirm="主人已授权"`，缺 confirm fail-closed）；
    走 JupyterLab HTTP 传文件 + **内核通道**（`POST /api/kernels` + `wss .../channels` 发 `execute_request`）跑命令。
  · `comfy_cloud`：把卡上的 ComfyUI 包成她的器官（该在卡里跑的 Python 现拼 → `run` 递进去 → 产物落卡 → `down` 取回 + **两头 sha256 对账**）。
  · `cloud_pc` 五原语 · `cloud_llm`（按 `external_llm` 收口）· `cloud_plugin`（10 个云源注册表，加一行即扩容）。
- **今天的三条现读回执**（不修饰）：`omni_plug status → ok:true`（六类插座齐）·
  `pod_link status → ok:true · key_configured:true · pod_count:15` · `pod_link gpus → denied`（看算力市场要票）·
  `comfy_cloud status → ok:false`（云卡当前不可达；本地 27 个原生算子照常离线可跑）。


## 2026-10-21 · 第六批：338 通过 + 341 位逐位详解（6 位过短介绍补齐）

### 能力介绍补到底（这一批是「介绍清楚仔细」的交付）
- **341 位逐位详解**：域页从「4 列摘要表」升级成「摘要表 + 逐位详解（341 节）」，每位写清：
  域 · 类型（只读 / 需授权）· 需不需要参数 · **要哪张票（作用域名字，`policy.evaluate` 静态算出来的）** ·
  它做什么（**全文，不截断**）· 怎么调（真命令模板）· 失败三态怎么读（`denied` / `needs_*` / `failed`）。
- **6 位过短介绍重写**（原来最短只有 6 个字）：`echo`（11→104 字）· `count_words`（6→84）·
  `audit_query`（→128）· `lr_status`（→56）· `cloud_llm`（→134，并写明它是**不是只读位**、按 `external_llm` 收口）·
  `voice`（→142，含本机 WASAPI 端点实测口径：渲染 1 / 录音 0）。

### 跑通面
- **`offense_ops` 转绿**：目标只用**本机回环**（`127.0.0.1`），真跑 `op=plan`（只出计划不动手），
  五阶段 + 三条判据都在回执里。
- **`pentest` 目标已登记**：走 `op=authorize` 把 `127.0.0.1` 写进授权表（受管动作）；
  `op=verify` 现在只差 `network_private` 一张票（主人终端发，模型无权自给）。
- **`codex_interrupt` 的真因量清了**：同进程三步探针 ⇒ `thread_new` ✓ · `turn_send` ✓（0.23s 拿到 turnId）·
  `interrupt` 被**服务端串行化**挡住（请求排 19.3s 才处理，回合已结束）。**上游单 stdio 不并发读**，
  不是我们没实现、也不是缺票。
- **终账：338 通过 / 1 要票 / 1 缺输入 / 1 缺依赖 / 0 失败 = 341**
  （来源：监控 216 · 写口 49 · 隐私与流程 45 · 需参数 16 · 带票 10 · 房间晋升 1 · 打断链 1 · 出图门 1 · 进攻面 2）

### 工具
`probe-codex-interrupt.py`（同进程三步，附三层根因）· `probe-offense-live.py`（本机回环，plan/verify 各跑一次）


## 2026-10-21 · 第五批：337 通过 / 失败 0（出图门真看了四轮，打断链查到真根因）

### 收口
- **`figure_gate` 转绿**：这个门要「数已声明 + 至少 4 轮看图 + 最新一轮问题清空」。逐张看了七张测试图和落地页截图，
  逮到 **3 处真问题**、修完复看清零，门自判 `deliverable=true · rounds=4 · open_issues=[]`：
  · `fig-caps` 副标题写死「三路真跑」而账里已有 6 路 ⇒ 改「五类真跑」+ 加一行由数据自己给的**来源计数**；
  · `fig-eval`/`fig-monitor` 的「⇒」渲染成**豆腐块**（字体缺字）⇒ 换字，渲染器里归零；
  · `fig-eval` 把 99.10% 与卡片上的 98.51% 混在同一句 ⇒ 写清「第1轮 332/335 · 第2轮 330/335」。
- **`codex_interrupt` 仍是 `needs_input`，但假账换成真因**：新增同进程三步探针
  `tools/codex-scripts/probe-codex-interrupt.py`，量出三层叠加 —— ① shared app-server 是**进程级**缓存，
  跨 `cap` 调用必然 `thread not found`；② `start_turn` **阻塞**到回合跑完才返回；③ 订阅期间 app-server
  **一条通知都不推**，拿不到打断要的 `turnId`（上游原话 `missing field turnId`）。下一步补「通知回流」那一腿。

### 终账
- **337 通过 / 要票 1 / 缺输入 2 / 缺依赖 1 / 高危未跑 0 / 失败 0 = 341**
  （来源计数：监控 216 · 写口 50 · 隐私与流程 46 · 需参数 16 · 带票 10 · 房间晋升 1 · 打断链 1 · 出图门 1）
- `docs/07` 新增 §十 记这两位；能力自证数字**问门现读**，不再手抄。


## 2026-10-21 · 第四批：能力自证 336 通过 / 失败 0，并修掉两条「会说假话」的判据

### 修复（两个真缺陷，都是把「没跑通」记错的引信）
- **入口契约三处各抄一份字面量**：`room_space.scan` / `room_space.simulate` / `qiankun` 各自写了一遍
  `("index.html","main.py","app.py","start.ps1")`；而 `simulate` 只看计划里声明的 `entrypoints`、**根本不看树**
  ⇒ 任何没手填该字段的计划，静态推演第 4 关**永远**报「未声明入口」，且不说该怎么办。
  修：入口名收敛成唯一定义 `room_space.ENTRY_NAMES`；未声明时**按名字在维度树里真找一遍**（找不到才红，并把可识别名报出来）；
  `qiankun` 面对没有入口的树**当场如实拒绝**，不再立一份永远过不了的计划。
- **`rehearse` 把「一次都没跑」写成「未通过」**：命令的执行条件是 `if execute and not blockers`，静态一红就整段跳过，
  回执却把没跑的用例照样列进「未通过验收命令」⇒ 同一次失败被记成两笔。修：拆成
  `验收命令未执行（前置未过：…）` 与 `未通过验收命令`，并新增 `commands_skipped` / `commands_skip_reason`。
- 两条都有判据（含负控）：`gbt_allinone/tests/test_room_entry_contract.py`，6 例全绿。

### 证明
- **一次性部署链首次全绿**：`one_key_deploy` 房间落点 `release-20261021`，77 件产物
  → `stage ok · plan ok(auto) · scan 3/3 · rehearse ok（acceptance=py-syntax-sweep 真执行）· release ok · 5.9s`，
  消耗一次性票 1 张（`deploy_publish`）。证据不手抄，由 `gen-capability-proof.py` 从房间报告现读。
- **终账：336 通过 / 要票 1 / 缺输入 3 / 缺依赖 1 / 高危未跑 0 / 失败 0 = 341**
  （来源计数：监控 216 · 写口 50 · 隐私与流程 48 · 需参数 16 · 带票 10 · 房间晋升 1）。
- 新增 `index.html` 发布落地页（静态、零外部依赖、零埋点），同时补齐「文档型产物必须有入口」这条硬约束。

### 文档
- `docs/07-capability-proof.md` 重写 §二 读数、§七 复核命令、§八 已知未跑（逐条机器回执）、新增 §九 记这两处修复。
- 全仓口径扫平：README / `docs/04` / `docs/12` 里残留的 335 / 329 / 221 三套旧数字统一到 336。

## 2026-10-21 · 第三批：能力自证从「221 通过 / 79 未跑」到「297 通过 / 失败 0」

### 修复（这一批都是真 bug，不是文案）
- **内网护栏名不符实**：`policy.py` 的 `add()` 只认 `HUMAN_GATES`，而 `osint_scan` 声明 `osint_private`、表里写
  `network_private`；`auth_gate.ENFORCED_SCOPES` 同病 ⇒ 内网扫描不打票就能跑（实测 `127.0.0.1 → ok`）。
  两处补 `osint_private` 后实测 `denied · missing=['osint_private']`。**一条修复让 4 条红了很久的测试同时转绿。**

### 证明（三路真跑，341 位一位一行）
- 只读位空参真调（90s 超时口径）· 需参数位**带人写样本参数**真跑 · 写口位**隔离 store**真跑
- 主人发票后又真跑 21 位（11 位转绿）：`autopilot` `think_loop` `sec_llm` `codex_chat` `devour_github`
  `tentacle` `codex_models` `codex_thread_new` `devour_pulse` `bluetooth` `vision`
- **终账：297 通过 / 要票 12 / 缺输入 23 / 缺依赖 1 / 高危未跑 8 / 失败 0**
- 12 位要票的是生产写入与隐私载体（mirror_* · pipeline_submit · keylogger 等）——**被门挡住是设计**

### 工具（都在 `tools/codex-scripts/`）
`probe-caps-params.py` · `probe-caps-params-fix4.py` · `probe-caps-write.py` · `probe-with-tickets.py` ·
`gen-capability-proof.py`（分桶合计 ≠ 341 直接退出）

## 2026-10-21 · 第二批公开（GBT天真 / 五维合一 / 多域监控）

### 新增文档（每页都有可复跑的数据源脚本，不是手抄）
- `docs/10-gbt-tianzhen.md` —— **GBT天真**（`comfy_native`）：27 个原生算子，其中 **18 个与 ComfyUI 同名同契约**；
  对齐契约面 1495 个节点（覆盖率 1.2%，1477 个未接按原因分类）；离线 `validate` 正反例；写面真跑 + fail-closed 反证。
- `docs/11-five-dim.md` —— **五维合一**（`brain_unify`）：route → execute → verify → health 顺序串链；
  五条真跑回执，含两条**被门挡住**的完整拒绝回执（`missing_scopes` 点名）。
- `docs/12-multidomain-monitor.md` —— **多域监控**：29 域 236 位只读位逐位真调，221 通过 / 15 要票（按票种点名）/ 未跑 105；
  基线 + `--diff`：立完基线后改了三处代码，整面重跑**回归 0 / 修好 0**。
- 新增数据：`data/gbt-tianzhen-live.json` · `data/five-dim-live.json` · `data/multidomain-monitor-live.json`
  （分别由 `gen-native-live.py`、`multi-domain-monitor.py --out` 生成）。
- 新增图：`assets/fig-tianzhen.png` · `assets/fig-monitor.png`。

### 修复（这批文档逼出来的真问题）
- **契约保真三处**（`comfy_native`）：`LoadImage` 只认内部别名 `path`（ComfyUI 叫 `image`）、把落点 `out` 当必填、
  连边按字面名取产物（`image->image` 取不到 `out`）⇒ 修到**标准 ComfyUI 图能过校验并真跑通**，反例仍被抓。
- **拒绝回执被省掉**（`brain_exec`）：五维合一的执行层只留 `status=denied`，缺的作用域与原话全丢 ⇒ 现在两层都透传。
- **监控读数被省掉**（`multi-domain-monitor`）：`missing_scopes` 嵌在 `result` 层而只读了顶层，15 条拒绝全变 `(未报)` ⇒ 两层都读并从原话兜底提取。
- **图鉴文案落后于盘**：`comfy_native` 写「18 个算子 / 962 把节点」，盘上现读 **27 / 1495** ⇒ 文案改为现读值并注明口径。

## 2026-10-21 · v83 发布版

### 模型
- 现役权重 `v83`（bf16 合并，15.25 GB，Qwen2-7B 底座 + LoRA r=64）。
- 线上评测：335 题 · mean cov **0.9908** · PASS45 **99.10%** · 零覆盖 2。
- 已知未过：`health`（样本不足）、`voice_studio`（判据与数据不同源）。

### 文档
- 首次公开发布：能力位全量 341 位 / 30 域，逐位说明由注册表现读生成（`data/capabilities.json`）。
- 补：模型卡、架构（单门 + 授权 + 审计）、评测口径、部署路径。

### 修复（发布前）
- **端点 502 真因**：客户端传友好别名而 vLLM 只认 served id → 统一按现役 served id 传参。
- **原生车道选不上**：选路只看环境变量、看不见保险箱里的钥 → 显式点名时回退保险箱取钥。
- **缩容太急**：端点 `idleTimeout=5s` 导致请求排队挂死（实测 90s 队列不动） → 对齐到 300s，实测 150s 内 worker 稳定在岗。
- **挂热是死路**：心跳硬编码打一个不存在的本机桥 → 改为「先本机桥，不通直打端点」并把走哪条路记进日志。

## 2026-10-18 及以前（内部迭代）
- 多轮容量/配方实验（LoRA r=16→64、词表补齐、bf16 合并、量化对比）。
- 能力位从 172 扩到 341；评测从 118 题扩到 335 题。
- 详见仓库历史（本页只保留对外可读的摘要）。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

## 2026-11-01 · 闭环固化（脉冲·能源核心·无限制上下文）

- **能力位 354 → 362**：新增 `body_sense`（本体感觉/痛觉/神经邻域）、`trunk_cover`（每个代码文件归哪根触手）、
  `trunk_reason`（接在 `brain_exec` 五维链上的"想"）、`context_guard`（原来是脚本，现在正式成位）、
  `devour_auto`（锁缺口才吃、必须有转化物）、`energy_core`（一块电池/4 个取电口/电表）、
  `research_intel` / `hunyuan_video`（部署反查查出来的"有实现没能力位"，本轮补登记）。
  `knowledge_lib` / `brain_supervisor` **不登记**：它们是已登记位的模块外壳，重复登记会双计数。
- **脉冲直达**（提速来源）：`pulse_core.direct()` 四级命中（精确名/别名/词表唯一/唯一子串），
  24 条人写基准：命中 15/24（其中正确 13），**平均 4ms**；权重判决基线 16/24、平均 66s。
- **能源核心**：`/props` 实测 `total_slots=4`；4 个触手同时取电全部 32.6s 内完成、等待 2–4ms。
  撤掉"一把全局锁"的旧实现（那把 4 个取电口锁成了 1 个）。单路变慢是共享功率的代价，如实记录。
- **无限制上下文接进对话路径**：`energy_core.think(context=…)` → 环形有界窗口（120 条压到 72 条/3996 字符）、
  溢出落 sqlite（48 条）、`recall` 秒查。此前 `ring_context` 只有实现、**从未接进对话**（docs/31 自己写着）。
- **门政策收窄**（主人 2026-11-01 令）：41 → 31 个能力位要票；看/听/说/动手/只读抓取移出人工门，
  仍要票：`process_execute` / `remote_device` / `privacy_read`（看别人）/ `deploy_*` / `external_llm` / `data_export`。
- **部署反查** `tools/codex-scripts/audit-deployed.py`：三张清单（标了没登记 / 文档提了没登记 / 登记没实现），
  首跑 89 条假警报 → 收紧后 11 候选 → **真缺 2 个**（已部署）。README 与 docs/README 已同步。
- **固化**：`docs/55-tonight-ledger.md` 记全部读数与复跑命令；`cap_self brief` 记忆条 844 字符，
  含 energy_core/trunk_cover/body_sense 等新器官，**每次判决默认注入**。
- 闭环终值：9/9 测试全绿 · `cap_self` 362=362=362 · `selfscan` clean · `signature` clean 106 页 ·
  `trunk_cover` orphan 0 · `pulse_core verify` ok。
- **编排账本 + 面板**（第 363 位 `orchestration`）：六类动作 scan/add/edit/deploy/fix/run 只追加落 `state/orchestration-ledger.jsonl`；闸门对非 probe 调用自动记 run；`op=panel` 一屏给本会话计数 / 最近条目 / 各类扫描最后时间 / 能力位漂移 / 自上次看图以来新增。今晚的 20 条动作已补记。
- **别名锻造 + 直达第⑤级**（`tools/codex-scripts/gen-aliases.py`）：从 desc/名字自动生成口语别名，去歧义（丢 90 个一词多位）后只增不改写入词表（320 条，`auto: true`）；`pulse_core.direct()` 新增「别名唯一包含」级 ⇒ 能力位题面**可直达率 7.5% → 57.3%**（205/358，0 token）。起因：全量基准 485 项里今晚新加的 8 个器官全部 MISS（不可达 = 等于没长）。docs/57。
- **直达证据门 + 消歧**（`pulse_core._evidence_ok`）：别名多了会撞，长句里多别名命中先按（权重+长度+位置）打分，再要求**字面证据**（意图含该位真名 或 意图 ≤32 字），否则不直达。358 条能力位题面：直达 234（65.4%）、正确 204（57.0%）、错 30（其中多数是基准自身的兄弟位歧义）。阈值扫描 12/16/24/32/48/无门 全部记在 docs/57。
- **脉冲优先路由**（`commander.route(pulse=True)`）：路由入口先过 0 token 直达，命中即返回、不叫醒电池；未命中照旧走权重。人写 24 条：直达 17/24、正确 15、**2.3ms**（同批权重 16/24、66s）；真实入口实测 17ms（vs 40s 级）。`test_lexicon_scope` 改判据 + 新增三条（默认直达/0 token/毫秒级）。docs/58。
- **脉冲直达铺满（docs/58）**：按域逐批补「唯一短语」，直达率 7.5% → **89.7%（321/358）**、正确 288（80.4%），全程 0 token；词表 24 → **479** 条（人工 + 自动别名，自动条目可整批回滚）。原则：安全进攻类（data_hijack / llm_redteam / sec_chain）**故意不补**；真歧义不补；每批同一把尺子复测 + 契约测试（词表冲突判据本轮响了 6 次，全部消解后复绿）。
- **速度写进肌肉记忆 + 直达收尾**：脉冲直达 322/358 = **89.9%**（0 token、≈4ms），人写 24 条基准 **24/24 命中、22/24 正确**；`cap_self brief` 新增「十次请求约九次直达…」一句（读 `state/pulse-summary.json`，每次判决默认注入）。`direct()` ③ 增加整串命中例外（最高权重严格大于次高即可，不再要求 2×）；longrun 补 `长程任务看板` 至 4/4。
- **GBT天真 节点 42 → 50**（docs/59 第六节）：补遮罩/透明通道族 8 个 ComfyUI 核心同名节点（InvertMask/CropMask/FeatherMask/ThresholdMask/MaskPreview/SplitImageWithAlpha/JoinImageWithAlpha/GetImageSize），真跑遮罩链 5/5 ok。新增 `tools/collect-object-info.ps1`：在秋叶版机器上一条命令取 `/object_info` 真快照（只读、无 BOM、节点数异常会警告）。
- **GBT天真 家族统计 + 写进记忆条**：50 节点按族（Image 22 · Mask 13 · Text 4 · 其它 11），统计落 `state/comfy-families.json`；`cap_self brief`（1033 字符）新增构图行（节点数/传统缺口 0/无 CUDA 不接/采集入口）。纪律：真快照到手前**不再凭感觉造节点名**，先采集再补、每批同一把尺子量。
- **GBT天真 执行引擎加固（docs/60）**：`run_workflow` 补四条语义 —— `skip` 旁路 · `times` 重复（上限 50）· `on_error=stop|continue` · **失败回滚**（只删本次新产物，旧文件不碰）；未接线节点明确报 `unwired`（另有白名单 fail-closed 两道）。新增 `tests/test_comfy_engine.py`（5 组 11 条判据）全绿。
- **秋叶版取食器（docs/61）**：新增 `tools/comfy-harvest.py` —— 只取「我们没有 + 纯 CPU 可用」的节点契约，**权重一个不下**、模型面/云端一律跳过。同时修了两个真问题：① 分类顺序（ModelMergeFlux1 被误判云端 ⇒ 模型面优先）；② 补 Loop 结构性节点 5 个（StartLoop/EndLoop/LoopIteration/LoopResult/LoopProgress，writes=False，EndLoop 校验配对）。节点 50 → **55**，核心面同名覆盖 17（13.4%）、traditional 缺口 0。
- **GBT天真 校验期检查（docs/61 第六节）**：`validate` 把「契约里有、原生没接」**一次列全**（每条带处置说明），不再只报第一个；新增只读 `op=coverage`（契约/原生/缺失/覆盖率/按类）；契约快照缺失时退到**核心面参照**并标 `core_ref_fallback`（不冒充秋叶整包）。实测 coverage：127 契约 · 17 原生 · 110 缺失 · 13.4%；`test_comfy_engine` 增第 [6] 组 5 条判据。
- **GBT天真 覆盖读数进记忆条 + 校验留痕**：`cap_self brief`（1053 字符）构图行补「契约面覆盖 13.4%（17/127）」（读 `state/comfy-parity.json`，毫秒级）；`validate` 每次追加审计到 `state/comfy-validate.jsonl`；`test_comfy_engine` 补第 [7] 组「校验后审计行数 +1」。
- **取食器接成能力位**：`comfy_native op=harvest`（只读）—— 她自己就能看「缺哪些 / 哪些值得补 / 哪些不取」，返回分类计数 + useful_list + 规则；实测核心面 127/55/17/0/103/0/7。`test_comfy_engine` 补第 [8] 组 3 条判据。
- **补节点脚手架（docs/62）**：`tools/comfy-add-node.py` 三族模板（image/mask/passthrough）生成 `_n_*` 骨架 + 注册行，落到独立模块 `comfy_nodes_extra.py`（主模块末尾合并，绝不自动追加主模块）。首个用脚手架补的节点 `ImageFlipX` 真跑通（节点 55→56）；顺手修了模板缺 `import pathlib` 的坑（回滚机制正确删掉半成品，判据 [9] 钉住）。
- **补节点脚手架支持批量**（docs/62 第六节）：`--from-harvest` 读 `op=harvest` 的 useful_list，一次生成**待审骨架文件** + 待办清单（**不直接进 extras** —— TODO 骨架进去会变成「能跑但做错事」的假绿）。实测模拟清单 3 个名字流程通过；演示件已清理并用真实 harvest 覆盖，不留假清单。
- **参照重建（127→1000）+ 分类升级 + 批次 A（docs/63）**：新版 ComfyUI 用 `node_id="X"`（v3 API），旧解析只认 `NODE_CLASS_MAPPINGS` ⇒ 参照从 127 修到 **1000** 节点；分类改五级（Node 结尾/厂商前缀/3D/模型/传统），可补清单从 214（混着云端）收敛到 **130**；按清单补 **12 个纯 CPU 算子**（节点 56→68），真跑 7 节点混合链通过。覆盖率 13.4% → **5.1%**（分母变真，不是退步）；traditional 缺口 118。
- **GBT天真 批次 B（10 个纯 CPU 算子，68→78）**：裁剪/bbox/直方图/颜色空间/色彩迁移/图像对比/静音音频/数组字典转字符串等，全部 ComfyUI 同名同契约；6 节点链真跑通；`test_comfy_engine` 补第 [11] 组 3 条判据。
- **GBT天真 批次 C（14 个算子，78→92）**：音频三件（音量/拼接/裁剪，stdlib wave）、图像六件（合成/去重指纹/归一/重复/长边缩放/缩放补边）、文本五件（写图/大小写/截断/替换）；8 节点混合链真跑通；`test_comfy_engine` 补第 [12] 组 3 条判据。
- **GBT天真 批次 D（11 个算子，92→103）**：音频通道三件（Load/Save/Preview）+ 均衡器 + 拆合声道、图像三件（重分批/随机裁剪 seed 可复现/短边缩放/总像素缩放）、文本落盘；7 节点链真跑通；`test_comfy_engine` 补第 [13] 组 3 条判据。traditional 缺口 94 → 83。
- **原生 workflow 导入（docs/64）**：`op=import` + `validate/run` 自动识别 ComfyUI 原生格式（`nodes[].type` + `widgets_values` + `links`），转成我们的图再校验；`widget_mapping=best_effort` 如实标注；实测合成图 3 节点/2 边转换正确，KSampler 归 contract_only 并给出「要 GPU/权重」原因。判据补第 [15] 组 3 条。
- **批量导入目录（docs/65）**：`op=import_dir` 扫一个 workflow 目录，逐张转换+校验，四分类（runnable / needs_gpu / unknown_only / invalid），结果落 `state/comfy-import-manifest.json`；顺手修了相对路径按 CWD 解析的 bug（改为按仓库根）。判据补第 [16] 组 3 条。
- **可复跑快照（docs/66）**：每次 `run_workflow` 落 `state/comfy-runs/<hash>.json`（图+产物 sha256+闸结论+依赖版本）；新增只读 `op=runs`（列表）与 `op=replay`（重跑比对 sha256）；实测 replay 可复现 same=2/diff=0。判据补第 [17] 组 3 条。
- **自主契约（docs/67，第 364 位 autonomy）**：主人严令「架构给完后除终端危险能力与转账，禁止打扰用户/要求用户帮助」落成可判定契约 —— `declare` 生效、`check` 只放行 danger/transfer、其余 deny 并记账、`guard` 把「需要你确认/要不要我/请提供」改写为自主推进；接入 `trunk_reason`（LLM 的下一步先过 guard）与记忆条（铁律一行）；`tests/test_autonomy.py` 4 组 10 条判据全绿。
- **架构驱动蓝图 + 真实落地（docs/68 第七/八节）**：`blueprint.make` 增加「架构关键词 → 专项任务」（8 组关键词，全部只挑安全能力位）；用主人的完整架构跑通全链 —— 23 任务（12 模板 + 11 专项）→ 过目 → 思维导图 → 派遣 → **done=23/23 · landed=True · 49s**。\n- **跑到落地（docs/69）**：`blueprint.land` 一轮轮 dispatch 直到 landed —— 已完成不重跑、失败只重试失败项、全程不问主人（只有剩票任务时 blocked）；新增 `tools/blueprint-land.py`（无人值守入口，退出码 0=落地/1=未落地）。实测 21 任务 1 轮全通过；第二遍 land 识别"已落地"不重跑。判据补 [6][7]。\n
- **卡点研究环（docs/70）**：`blueprint.land` 遇失败（非票类）自动 —— 判卡点类型 → 只读查资料（白名单 raw.github/arxiv/docs，不传自己数据）→ 落 `state/knowledge/*.md` + research-ledger → 往思维导图**追加研究任务**（重排任务指引）→ 继续下一轮；全程**不问主人**。新增 `op=research` 可单独调用。判据补 [8][9]。
- **深推理 + 规则兜底（docs/70 第六节）**：`deep_reason()` 让本机权重读「卡点+摘录」判断如何改任务，输出写进思维导图（深推理.N）；实测 7.6B 两次都给 `tasks: []` ⇒ **不逼它编**，改规则兜底（按卡点类型落可执行任务），来源分开标 `energy_core` / `fallback_rule`。判据补 [10]。
- **诊断质量门（docs/70 第八节）**：`_score_diagnosis` 用「诊断词 ∩ (摘录+卡点)」重合率判依据，零重合/低于 0.08 标 `energy_core_unsupported` 并**不采信**、只走规则兜底；三处来源分开标（energy_core / energy_core_unsupported / fallback_rule, source_was）。实测胡话 score=0.0 被拦、有依据 0.25 放行。判据补 [11]。
- **死循环保护（docs/71）**：`blueprint.land` 对连续 2 轮失败的任务标 `stuck` 并写 `state/blueprints/<id>.stuck.json`，后续轮次跳过；`status` 暴露 stuck 列表；`landed` 仍要求全部通过（有 stuck 就如实报未落地）。实测 3 轮：fail→fail→跳过，stuck=['实现.1']。判据补 [12] 5 条。
- **蓝图模板库（docs/72）**：落地成功的蓝图自动沉淀 `state/blueprint-templates/<name>.json`（任务图+验收口径+关键词签名）；`make` 遇相似架构（关键词重合 ≥2）自动复用已验证任务图并补专项；新增 `op=templates` / `op=save_template`。实测 21 任务模板复用后 26 任务、不再从零拆。判据补 [13]（测试会清掉自己建的模板）。
- **一句话入口（docs/73）**：`blueprint op=go` 自然语言 → 蓝图 →（已确认则）过目 → 跑到落地；`parse_intent` 剥口语前缀并识别「已确认/直接跑」等；**没写已确认就只到蓝图**（不替你确认）。实测：未确认 stage=blueprint（26 任务，复用模板）；已确认 29 任务 1 轮落地并沉淀新模板。判据补 [14]（测试自清蓝图）。
- **固化收尾：测试全局自清（docs/73 第六节）**：`test_blueprint` 开头快照 `state/blueprints` 与 `state/blueprint-templates`，结束删除全部新增文件（实测跑一遍蓝图数 6→6 不增长）；顺手清掉历史残留（蓝图 78 个、重复模板 6 个）并补齐 `docs/capabilities` 30 页署名（套件前后 missing=0）。\n- **旧物守卫（docs/79）**：主人严令「项目里不允许旧代码/旧面板/重复物」—— 新增 `legacy_guard`（六类检查 + clean，重复文档只报不删）；实清 840 MB / 17,008 个旧文件（sync-backup 30 快照、6 个旧 worktree、旧面板归档、*.bak、tmp、重复文档 2 页）；因为 api/caps 会被外部同步整文件覆盖，做成 **包导入层自注册插件**（每次 import 自愈）。\n
- **旧覆盖新根治（2026-11-01）**：查出外部同步用 -Force 绕过了 newer-wins（所以新改动被旧副本打回）。改：-Force 只表示允许并发推送，**不再**能覆盖更新的一侧；要覆盖须显式 -ForceOverwrite。同时补 state/obsolete-files.json 淘汰清单（删掉的文件不会被 push 复活）、legacy_guard op=authority（唯一真相=live 当前文件+账本）、记忆条三条禁令（不留旧/唯一真相/不打扰）。
- **原始仓库整理（docs/82）**：GitHub 仓被运行态撑到 ~200MB（5108 文件，state/ 1876 个、dist/ 40.6MB、vendor/ 二进制，还有一个以 Windows 绝对路径命名的目录）。新增 	ools/github-repo-clean.py：只删运行态/产物（2323 文件 / 154MB）+ 重写 .gitignore，用 Git Data API 建一次 commit（本机无 git）。源文件与文档一律不动。
- **原始仓库整理完成（docs/83）**：用 Git Data API 一次 commit（19d2b06）把 GitHub 仓 HEAD 从 **5108 → 2708 文件**（删 2323 个 / 154.1MB：state/ 1876、dist/ 40.6MB、runtime/logs/vaults/vendor、C:\Users\ADMIN\Desktop\GBT小土豆V8 目录、>2MB 大二进制），并追加 .gitignore 阻断块；源码与 docs/ 未动。历史体积仍 ~200MB（需 filter-repo 才能缩）。
