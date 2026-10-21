# 变更记录

格式：`日期 · 版本 · 一句话`。只记**对外可见**的变化。

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
