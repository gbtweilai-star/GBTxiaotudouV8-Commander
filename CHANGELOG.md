# 变更记录

## 2026-11-06 · 第三十八批：每一步都能看见 —— 扫描 / 工具 / 回执 / 回答 四段 · 屏幕采集自愈

- **主人令**（逐字）：「精细一点必须她扫描过哪里，在执行哪里，调用什么工具每一步细节都要能看得到」。
  上一批只做到「一条过程行 + 正文」；这一批把那一行拆成**四段实测**，并把回执前的空省略号
  换成带真实计时的进行中骨架。
- **① 进行中骨架 `beginTurn()`**：发出即出现「接收指令 · 正在处理 / 执行中 · 等待本机回执」，
  毫秒是 `Date.now()` 实时走秒；回执到达后**原地**换成完整步骤（不闪两条）。
  连发时上一轮被 `__abort` 收成「已中途中止」，其真实回答到达时仍会补进同一条消息（不丢）。
- **② 四段步骤行 `buildSteps()`**：
  · `扫描指令` — 原话 / 意图·动作 / 对象 / **命中词** / 缺参数 / 置信度（= 她扫了哪里、凭什么命中）；
  · `调用工具` — 工具名 · op / socket / target / do / params / 代价（= 她调了什么、在哪个面上动手）；
  · `执行回执` — 结果 / 状态 / 判定 / 原因 / 缺件 / 采集引擎 / 帧尺寸 / 载荷（= 她执行到哪、成了没有）；
  · `组织回答` — 通道 / tokens / 记忆环 seq / 总耗时。
  每段毫秒都取自回执实测字段（`ms_route` / `cap.ms` / `elapsed_ms`），没有一处估算。
- **③ 回执形状按「非元数据键」认**（本轮踩到的真差异）：屏幕/看图挂在 `capability["看"]`（dict，
  键是中文动作词，不是 `action=see`），读文件直接把正文挂在 `capability.read`（字符串）。
  两种都如实摊开；缺一个字段就少一行，不补假值。
- **④ 异常状态不许压成「失败」**：连发第二次时回执是 `status=already_running`，
  标题如实写「执行回执 · already_running」，正文仍是「同一动作已在执行，本次没有重复动手」。
  失败分支（`ok:false` / 网络错误）也改走 `printBot` + 步骤行 —— 报错同样要能看见她做过什么。
- **⑤ `/api/chat` 分开报阶段耗时**（`tools/console-server.py`）：`ms_route`（路由器总耗时，
  `perf_counter` 实测）、`ms_run`（工具耗时）。前端「扫描指令」= `ms_route - ms_run`，
  「调用工具」= `ms_run`；两个数都是实测，否则宁可不显示。
- **⑥ 屏幕采集自愈（真 bug，非配置）**：长驻服务从 03:42 起每次「看屏幕」都报
  `screen_grab_unavailable`（实测 2/2 失败），而同一时刻新进程同一路径 200ms 抓帧成功 ——
  根因是**复用的 mss 实例 DC 失效后永久 BitBlt failed**，代码里没有重建入口。
  现改为第一次失败即 `_mss_drop()`（关旧实例、清缓存）再试一次，成功在回执标 `mss_recovered`。
  细粒度验证：注入一个 `grab()` 必抛 `BitBlt failed` 的假实例 → 重建后抓到 1920×1200 · 64.1 ms ·
  `mss_recovered=True`；修后真机「看屏幕」`ok=true` · 362ms · run 289ms。
- **⑦ 展开是逐条的**：`.step-head.is-open`（此前 `wrap.is-open` 会让**一个箭头转全组**）；
  进行中计时 `.step-ms.live` 带呼吸点。
- **判据**：`test_console_chat_print` 5 → **7 条**（新增 `test_f_every_step_visible` /
  `test_g_step_numbers_come_from_real_stages`）—— 7/7 OK。
  真机（重启服务后 v=5）：四段标题齐、毫秒 64 / 48 / — / 112、`hidden` 默认折叠、
  点开后看到「命中词 看屏幕/看看屏幕/看看屏/看屏」「socket=app do=see」「帧 1920×1200 · 整帧」
  「载荷 241KB · jpeg」；文件通道四段齐（含 `内容=` 正文首段）。
- **读数**：`guard-three` 5/5 全过 · 全量 `py_compile` 0 bad · `test_brain_health_vision` 12/12 OK。
- **仍未做**：`dxcam` 仍是缺件（JSON 里有 `dxcam:false`，如实报，不假装硬采）；
  `holo_pet_w3/package.json` 推产品要主人点赞；`plugins/gbt-master/lib/host.js` 不在本机。

## 2026-11-06 · 第三十七批：对话面板「过程行 + 逐字回答」· 审美闸 67→97 · 台账重建

- **主人令**（逐字）：「AI 打印做跟 Codex 对话面板同款」「还有对话面板的 AI 对话显示，设置这样的同款」。
  落成两个可观测特征：先一条可折叠的过程行，再逐字吐正文。
- **① 逐字打印器**（`holo_pet_w3/console/app.js::printBot`）：`PRINT_CPS=90`、末尾光标、
  贴底跟滚（只在距底 48px 内）、`prefers-reduced-motion` 保内容、新消息先把上一条收尾。
  真机实测（127.0.0.1:8766，重启后 pid 29552）：长度 3→13→23→33→44→54→64、光标在、然后落定；
  第二次 4→16→26→36→46、然后落定。
- **② AI 步骤行**（`buildSteps` / `renderSteps`）：把 `/api/chat` 回执折成
  「已使用 … · 25.4s」一行，详情（via / cap / op / params / context / tokens / seq）默认折叠、点开才看。
  结点顺序硬序为 `msg-steps > msg-text > meta`（过程在前、正文在后，与 Codex 同形状）。
  真机实测：标题「已使用 本机指挥官」· 25.4s · 2 行详情 · 默认 `hidden`。
- **③ 审美闸 67 → 97**（`taste_guard op=audit`）：emoji 换内联 SVG、补 `<h1>`、
  仪表盘由 2×2 同款卡改为「主图 + 两辅读 + 全宽流水」（`dash-panel--hero/--ring/--kv/--flow`），
  当色块用的 `<i>` 全部归还 `<span class="scan-note">` / `.res-bar-fill` / `.legend-dot`。
  仅剩 1 条 WARN（`<img>` 0 个）—— 控制台不是落地页，如实不凑图。
- **④ 闸自己的两处假红**（同属 P33「量具自身的系统错」）：
  · `<i[^>]*>` 无词界 ⇒ `<input …>` 全被当强调词（改 `<i\b|<em\b`）；
  · `motion_count` 只扫 HTML ⇒ 动效全在 CSS 里恒报 0 处（改为同目录 CSS 一并喂，
  并把「读了哪几份 / 哪几份读失败」写进回执 `css_scanned` / `css_missed`）。
- **⑤ `capability_router._why()`**：只读回执第一层 ⇒「看屏幕」失败时把上游 `why/rule/missing`
  全吞掉，只报「原因未报」。现改为先第一层、再下钻一层含 `ok:false` 的 dict，并追加「（缺：…）」。
- **⑥ `state/排查台账.json` 整件重建**（现读：它与 `state/logbook.jsonl` 同时不在盘、
  本仓非 git 仓库、产品目录无副本 ⇒ 原 34 条根因与 700+ 笔轨迹原文不可恢复）：
  按契约重建 12 个顶层键 + 26 条根因模式（每条带 src）+ `_口径`（写明 +07:00 与重建范围），
  `ledger-refresh --check` PASS 6 · FAIL 0 · 腐烂 0；记录本用 `logbook.py append` 接回（自链哈希）。
  契约测试由 11 errors + 1 fail → 3 errors（剩下 3 条全是 `plugins/gbt-master/lib/host.js`
  不在本机；已按五项格式登进 `state/unimplemented.json`）。
- **⑦ 写手自己的同型假红**：`logbook.jsonl` 不在盘时，R2 会报「`in_progress` 没写日期」——
  读不到当结论。现分开报：`state/logbook.jsonl` 不在盘或为空 ⇒ 判不了前进笔数。
- **判据**：`test_console_chat_print` 4 → 5 条（新增 `test_e_ai_steps_block_like_codex`：
  拦 `buildSteps`/`renderSteps` 存在、步骤行必须排在正文之前、详情默认折叠、五类样式齐全）—— 5/5 OK。
- **读数**：`guard-three` 5/5 全过（3.9 s，`dxcam:false` 如实报）· `claim-audit run` 4/4 PROVEN ·
  全量 `py_compile` OK。
- **仍未做**：`holo_pet_w3/package.json` 推产品要主人点赞（danger 档）；
  屏幕采集在本机是「缺件」：dxcam / pyautogui 不在 pyembed ⇒「看屏幕」如实报
  `screen_grab_unavailable`，不是静默失败。

## 2026-11-06 · 第三十六批：短板读数不再是「印象」—— 幻影 src / None 名字 / 死分支

- **起因**：`growth_hooks op=shortboard` 排出的第一条（覆盖，权重 88）写着
  `src: state/coverage_matrix.json` —— **这个文件全仓不存在**，真源是
  `gbt_allinone/positions.py::audit()`（`framework_state._face_coverage` 读的就是它）。
  指错源比没源更坏：它让人去修一个不存在的东西。
- **① 幻影 src**：覆盖条目的 `src` 改为读 `faces["覆盖矩阵"]["src"]`（缺省也指向真模块），
  不再硬写 `state/coverage_matrix.json`；`how` 同时写清**真实修法**（`libtv_workflow.make_short`
  接生成端 / 或把 `min_level` 如实降级）并标明与「未实现」第 3 条**同根因**，
  免得同一件事被当两笔各补一遍。
- **② 名字全是 None**：`[i.get('kind') for i in um]` 读错键 —— `unimplemented.json` 的条目
  用 `where` 记名（`kind` 根本不存在）⇒ 读数印出 `[None, None, None, None]`。
  新增 `_names()`（`where` → `name` → `kind` → `?`），现在印的是
  `['tentacles/', 'tools/binding_hook.py', 'gbt_allinone/tools/libtv_workflow.py',
  'gbt_allinone/auth_gate.py::ENFORCED_SCOPES']`。
- **③ 死分支**：老化判定读 `cov.get("年龄h")` —— `_face_coverage` **从不产出这个键** ⇒
  「读数 N 小时没更新」这条**永远不会触发**。改为 `_age_hours(cov["at"])` 真算；
  读不动回 `-1`（**不许当 0 = 刚更新过**）。
- **④ 缺读数 ≠ 全绿**：`positions.audit()` 失败时 `_face_coverage` 回 `present: False`，
  而 `cov.get("全绿", True)` 缺省是 True ⇒ 整条覆盖短板**凭空消失**。
  现在先判 `present is False`，如实记一条「读不动」。
- **判据**（`gbt_allinone/tests/test_native_growth_stack.py::TestGrowthHooks`，3 → **5** 条）：
  · `test_d_shortboard_src_points_to_real_file` —— 每条短板的 src 必须解析到**盘上真实文件**；
  · `test_e_unimplemented_names_are_readable` —— 读数里不许出现 `None`，并钉住
    `_names` / `_age_hours` 的边界（`{}` → `?`；`"not-a-time"` → `-1.0`）。
  **负控实测**：把 `shortboard` 换回旧形状（幻影 src + `[None, None]`），两条判据
  **2 failures**；换回新形状 **5/5 OK** —— 判据确实咬得住，不是装饰。
- **读数**：`guard-three` **5 项全过**（856 ms）· `claim-audit run --slow` **5/5 PROVEN / broken 0**
  （含 `criterion-ratchet`，28.4 s）· 该测试模块 **23 条 / 4 failures + 1 error**，
  与改前 **21 条 / 4 + 1 同名同数**（零新增红；那 5 条是 `auth_gate` 仓外写入的
  已知冲突，见 `state/unimplemented.json` 第 4 条）。
- **仍未做**：触手库 1/442、owner 类 135 位仍需主人拍板；
  `排查台账.json` 在本仓不存在（故障面因此恒空 —— 同一类「缺读数当全绿」，留作下一条）。

## 2026-11-06 · 第三十五批：原生挖洞链（hunt / swarm）+ 主脑挖洞知识 + D3 判据重写

- **主人令（逐字）**：「把 AI 挖漏洞以及触手大军协作排查挖洞的所有专业能力，必须以原生能力优先来执行，
  以及主脑注入专业的挖洞知识，我们设计有危险能力和资金转账要票以外不能有任何限制阉割以及拒绝机制」。
- **① D3 判据 v5（399 → 6）**：前三代 D3 都咬着「有 `len()` / `.get(空)`」这条弱指纹，
  实测 399 条里 57 条只是因为 `json.loads` 挂了名、绝大多数是纯汇报函数。
  这一代钉到真形状：**循环里逐个读文件 · `except` 只 `continue`/`pass` · 回执里没有任何未读位
  ⇒ 少读一个文件仍然报「N 条 / 全干净」** —— 这正是会让挖洞扫描漏报的那一类。
  同轮把 8 个扫描器的未读位补齐：`security_brain.map_attack_surface`（含 `coverage_complete`，
  有未读就**不许**报低危）、`quick_scan.scan_plane1_prod`、`observer_anchor.auditors/depth_caps`、
  `false_report_audit.audit`（`AuditRows.unread`）、`llm_guard.scan`、`omni_guard._scan`、
  `surface_bind.keys`、`comfy_native._op_runs`。
  台架自检 **26/26**，新增负控「带 unread 的扫描器不许报」；基线 918 → **525**（`check` 无变坏）。
- **② `offense_ops` 四个原生 op**：
  `op=hunt`（一条命令跑全链：面测绘 → OWASP/CWE 模式库 → 多阶段 SAST → LLM 面探针 → 污点候选，
  合并去重 + 覆盖账）· `op=swarm`（多条扫描链并行，各出独立回执）·
  `op=coverage`（只回答覆盖到哪、哪里没覆盖）· `op=knowledge`（方法论/CWE 表/原生路由的机器可读版）。
  全部调本仓既有能力位：**不引云、不装外挂扫描器、不出网**；报告落 `state/offense/`。
  口径：**候选 ≠ 已证**（`candidates` 与 `findings` 分栏，`No exploit, no report`）；
  **触手失败/覆盖率不足必须进 `unread`**，`coverage_complete` 才允许为 true。
- **③ `pentest_flow` 补源**：原 `_SOURCE_RX` 只认 Web 四类入参（`req.query` / `request.args` /
  `$_GET` / `req.body`），对桌面代理的真实入口（`sys.argv` / `input()` / 环境变量 / 工具 payload）
  **恒等于 0 个 source** ⇒ 污点近似整条链是哑的（实测 candidates=0）。
  本次并入桌面侧入口 + `BaseHTTPRequestHandler` 的 `do_GET/do_POST` 路由；Web 侧判据一条没删。
  实测同一条 flow 触手从 **0 → 70 条候选**。`tests/test_pentest_flow.py` 全绿（24 项自检）。
- **④ 主脑挖洞知识**：新增 `skills/gbt-pentest/SKILL.md`（六段工序 / CWE 速查 /
  证据口径 / 原生路由表 / 覆盖诚实 / 触手派发 / 交活自检 / 纪律）。
  `skills_hub op=verify` → **30 个，verdict=clean**；匹配实测「帮我挖漏洞，全仓扫一遍有没有洞」
  → `gbt-pentest` **7.2**（次名 2.4）。
- **⑤ 意图层**：`offense_ops` 的 desc 补「常用说法」（挖漏洞 / 找漏洞 / 漏洞排查 / 渗透测试 /
  触手大军排查 / 安全体检 / 代码审计找洞 / 攻击面测绘），重建算子索引后实测：
  「挖漏洞」「找漏洞」「触手大军排查」「渗透测试」「扫一遍有没有洞」**全部 top-1 = offense_ops**，
  margin 0.75–1.30，`escalate=false`。
- **⑥ 实测读数（首轮 · 未收敛扫描面）**：全链 `op=swarm` → **已证 86 条**（critical 1 · high 59 · info 26）+ **候选 70 条**；
  `coverage_complete=false`。其中 sast 40 条来自 `pyembed` 第三方包、critical 1 条来自自检夹具字符串，
  均见 ⑧⑨ 的根因修正；收敛后的最终读数见 ⑨。
- **⑦ 覆盖账修正（同日复验抓出）**：`flow` 触手只喂 `limit=200` 个文件，但 `_coverage()` 只读
  `coverage.scanned`，于是报告写 `files_scanned=0`、`coverage_complete=true` —— 抽样被伪装成全覆盖。
  现在 `_collect_files()` 返回候选/已喂/未喂/超限大件四项计数，`_coverage()` 把抽样与超限都写进
  `unread`，`files_scanned` 改取「已喂数」，判据新增「抽样也算不闭合 / 抽样也记账」两条。
  同轮修正 `knowledge.native_route`：LLM 面**实测**指向 `llm_redteam op=selfcheck`，
  `op=matrix` 单列为目录；原先把目录当实测，主脑照路由走会拿到空结果。
- **⑧ SAST 扫描面收敛（同日产品复验抓出）**：产品 `code_audit op=scan` 默认把 `pyembed` 当源码，
  4000 个名额先喂给第三方运行时 ⇒ 产品自有 1651 个文件被截断没扫（rate 0.7078）。
  现把 `pyembed` 加入 `EXCLUDED_DIRS`（理由可见；显式 `target=pyembed` 仍可全扫），
  产品 sast 覆盖 **4000/5651（70.78%）→ 2443/2444（99.96%，仅 1 个超限大件）**，
  第三方包噪声 40 条消失。判据新增「默认排除 pyembed / 显式 target 仍可扫」。
- **⑨ 自检夹具误报根治（同日复验抓出）**：`sec_scan` 把 `write_text("... os.system(...) ...")` 里的
  自检示例报成 critical 命令注入。根因：只豁免「表达式语句字符串」，没认「文本落盘/打印实参」。
  现在用 AST 收集 `write_text/write_bytes/write/dump/dumps/print/...` 实参里的字符串行（数据，不执行），
  `os.system("...")` / `subprocess.run(..., input="...")` 仍照扫。新增
  `tests/test_security_brain_text_sink.py`（夹具不误报 / 真实调用仍咬住）。
  收敛后开发仓最终读数：**已证 71 条（high 20 · medium 33 · info 18）+ 候选 70 条**，`critical=0`；
  `coverage_complete=false`（sast 2456/2458，flow 抽样 200/2263 + 5 个超限大件，逐条如实报）。
- **⑩ OWASP 截断账（同日复验抓出）**：`sec_scan` 默认只回 20 条，`owasp` 触手没把
  `truncated/total` 记进覆盖账，报告把「只看了 20 条」读成「全仓只有 20 条」。
  现在 `owasp` 传 `limit=500`，`_run_lane` 带出 `total/shown/truncated`，`_coverage` 把截断写进
  `unread`；开发仓 owasp **20 → 53 条**（medium +33），全链 **46 → 79 条**。
  产品侧同一把尺子实测：**已证 73 条（high 20 · medium 35 · info 18）+ 候选 70 条**，`critical=0`；
  `coverage_complete=false`（sast 2444/2445，flow 200/1954 + 9 个超限大件）。
- **⑪ LLM02 密钥误报（同日复验抓出）**：`sk-` 正则从 `paysssk-...` 用户名中间截中，
  产生 8 条 `sk-cre****` 噪声；加词边界 + 顺序占位串豁免（本次跳过 3 个占位串），
  LLM 面 info **26 → 18**；`sk-abcdefghijkl` 这类测试值不再上报。
- **纪律落地**：`hunt` / `swarm` 对扫自己的代码**不设任何白名单、敏感词、默认拒绝**；
  要票的仍然只有危险作用域（7 项）与资金转账（3 项）。扫外部目标时，授权范围本身就是那张票：
  没有范围不动手，给了范围就按范围打满。
- **判据**：`tests/test_offense_ops_hunt.py`（知识包 / 候选与已证分离 / 覆盖诚实 / 真跑落盘 /
  拒得清楚）与 `tests/test_security_brain_text_sink.py`（夹具不误报 / 真实调用仍咬住）全绿；
  `claim-audit run --slow` **5/5 PROVEN**；`guard-three` 5 项全过；
  `criterion_bench check` → 525，无变坏、无新增。

## 2026-11-06 · 第三十四批：判据反推（claim → evidence）+ 三个专业包 + D6 假阳根治

- **主人令（逐字）**：「可以按顺序」——① 判据反推通用链 ② 补专业能力 ③ 啃 D6 115 条。
- **① `claim-audit.py`（新）**：把「结论 → 可复跑证据」做成一条链。结论登记在 `state/claims.json`，
  每条绑一个**具名检查器**（不是任意命令；`cmd` 型必须显式 `allow_exec`）。`run` 当场重跑，
  `PROVEN` 才写 `last_ok_at`，跑不过是 `BROKEN`、退出码 1。
  内置：`caps_contract` / `doc_signature` / `omni_gap` / `tiers_test` / `criterion_ratchet`
  + 通用 `file_sha` / `same_bytes` / `json_eq` / `count_eq`。
  已种 5 条真结论，`run --slow` **5/5 PROVEN**（含 427、署名 0 缺、三向一致、分级闸 8 条、棘轮 918）。
  负控：错哈希 → `BROKEN` rc=1；指向不存在的检查器 → `BROKEN`（"判据在 X，X 不在"）。
- **② 三个专业包**：`skills/pro-contract-review` / `pro-bookkeeping` / `pro-customer-service`。
  每个都带「要素/工序/判据/模板/红线」，判据全部可判真假（例：八项要素缺项标 `缺失`、
  借贷差 1 分也不许过、P0 升级先于解释、禁语命中必须为 0）。`skills_hub` 自动发现，共 **29** 个，
  `op=verify` clean；三条匹配查询全部命中自己（margin 明显）。已推产品（3 文件 / 哈希一致 / `gate.mode=auto`）。
- **③ D6 假阳根治**：115 条里原先标「高危」的 **8 条全部是假阳** —— 根因是**按名字判**：
  同文件别处有 `out = Path(__file__).read_text()`，于是任何 `"x" in out` 都被当成自指。
  改成**按位置**：只看这一行之前**最近一次**绑定，且形参直接排除；另修 `_in_deciding_position`
  把「三元表达式在选值」误判成「定胜负」。结果：**高危 8 → 0**，总数仍 115（提示档，多是合法的运行数据判据）。
  加了永久负控「名字碰撞」；台架自检 **26/26**；棘轮 918 未变、`check` rc=0。
- **反作用**：棘轮在过程中两次咬住我自己（新写的 `"OK" in out` / `"没有变坏" in out` 触发 D2；`if True:` 触发 D1），
  都已按判据改掉 —— 这正是它该干的事。

## 2026-11-06 · 第三十三批：分级闸 —— 只有危险件/资金件要 LIKE，其余 GBT 自行决策

- **主人令（逐字）**：「只有危险能力使用和资金转账需要终端 YES，其他的 GBT 自己决策不需要人工」。
  上一批解决「一次 LIKE 推一批」，但仍要人；本批把「**该不该问人**」也落成可判定、可审计的规则。
- **分级**（`atomic-sync.py` 内置，`policy` 子命令随时可查）：
  `danger` 危险件 —— 可执行载体（.exe/.dll/.ps1/.bat/.cjs…）、授权门与审计本体
  （`api.py` / `auth_gate.py` / `security/` / `caps_registry.py` / 本工具自身 / `like.json` / 审计账）、
  系统目录与开机自启位置；`finance` 资金件 —— 转账/付款/钱包/账单类路径；
  `normal` 其余（文档 / 技能 / 面板素材 / 普通 .py .json .md / 权重）⇒ **自行决策，不打扰**。
- **三条牙**：① 判不准 ⇒ 升 danger（fail closed，只会多要票不会少要票）；
  ② 一批里只要有一件危险/资金 ⇒ **整批**要 LIKE，不拆开偷偷放行；
  ③ 自改门也在 danger 白名单里 —— 新工具自己的第一次推送仍要主人一次 LIKE。
- **留痕**：normal 每次落 `auto_approve` 到 `state/atomic-sync/ledger.jsonl`，带清单 sha256，
  「谁放的、放的是哪一批」都查得到。
- **反向审计补洞（同日）**：把 `policy` 清单逐条反推，发现 7 类**执行面**被判成了 normal ——
  `pyembed/`（解释器 + site-packages，`.pth` 也能注入）、`node_modules/`（npm 生命周期脚本）、
  `package.json`（postinstall）、`gbt_allinone/store/`（审计与授权库）、
  `tentacle/autonomy.py`（自主契约本体，改它就能自授权）、`tools/action_gate.py`、`.git/hooks/`；
  另补 `.pth/.sh/.pyz` 扩展名。全部升 `danger`，测试矩阵从 14 条加到 21 条。
- **旧行为**：`GBT_SYNC_STRICT=1` 一键恢复「逐件点赞」。
- **实测**：分级矩阵 14/14 对（文档 normal / .exe .ps1 .cjs danger / transfer 与「转账流程.md」finance）；
  无点赞状态推 63 个 shuohao `.md` ⇒ `gate.mode=auto`、写 63 失败 0、逐文件 sha256 63/63 一致；
  产品 `signature_guard` **missing=63 → 0**（verdict=clean, pages=213）；
  反推 `atomic-sync.py` 自身（danger）⇒ `need_like`，门没有被自己绕开。判据 `tests/test_atomic_sync_tiers.py` 8 条。

## 2026-11-06 · 第三十二批：`atomic-sync.py` 加 `manifest` / `put-batch` —— 一次 LIKE 授权一批，但锁死是哪一批

- **为什么**：产品侧 `signature · missing` 实测 **63 个 `.md`**（7 个 shuohao 技能包），开发仓 220 页 0 缺；
  用单文件 `put` 要敲 63 次 LIKE。主人选 A：把批量做进工具，而不是让门形同虚设。
- **新增两条子命令**：`manifest`（一行一个仓内相对路径 → 逐文件记 sha256，只写清单、不碰产品目录）·
  `put-batch`（按清单批量原子更新）。
- **批量门与单文件门同级、一条都不放松**：
  ① `like --manifest M` 把 `sha256(M)` 写进 like.json，`put-batch` **只认同一份清单**（清单改过就重新点赞）；
  ② 清单里每个源的 sha256 必须与点赞时一致，源被改过 ⇒ **整批拒写，一个都不写**（不是写一半）；
  ③ 单文件点赞不能挪用给批量，批量点赞也不能挪用给单文件；
  ④ 其余照旧：一次性 · TTL 600s · 真实 TTY · `--apply` 才落盘 · 逐文件备份 + tmp+fsync+os.replace + 读回校验 · 全落账。
- **自测 4 条**：源被改 → `denied` 且目标目录 **0 文件**；非产品目录 2 文件批量 → `applied`，内容/哈希/ledger 全对；
  无点赞 → `need_like` 且未写；agent 用管道调 `like` → `denied`（自批仍不可能）。
- **顺带修一处**：批量门原先用 `--root` 去找 `like.json`（会去产品目录找），已改回 `DEFAULT_ROOT`，与单文件 `put` 一致。
- **本次清单**：`state/atomic-sync/manifest-shuohao-63.json`（63 个 / 422,011 B / sha `e9c92d59…`）。

## 2026-11-06 · 第三十一批：控制台两块面板并轨；`/console` 少个尾斜杠整页白板的坑（真因＝相对路径解析）

- **主人令**：「别又搞错了出现好几个版本」+「监控使用触手来精准监控就好了」。
- **并轨**：开发仓 `om-*`（触手全域 + 最近变化）与产品侧 `im-*`（改动影响：1 跳 / 2 跳波及）**不是谁替换谁，是两块都要**。
  `impact-board.js` 并入开发仓，id 全部改名（`impact-mon` / `im-sub` / `im-toggle` / `im-collapse` / `im-refresh`），
  `index.html` 加按钮 + 面板 + 脚本，`skin-cube.css` 追加 37 条 `.im-*` 规则（两侧规则集实测 276 = 276，无缺项）。
- **浏览器实测**（8777 开发仓控制台，真开真点）：
  · 多域监控：`采样 01:21:52 · 变化 0 · 历史 21 次`；万能插 7 类插座（process/file/api/web/app/ai/dh）已插 3、钥匙槽 1；
    触手绑定 611 资产 / 758 对 / 覆盖 155/427；触手全域 13 域 127/127；关联线路 750 文件 / 1833 边。
  · 改动影响：图建于 2026-11-06 00:28:44；`8,111` 异位 / `126,358` 条关联 / 100% 连成一整片 / 1 处孤立；
    最不能随便动的前三：`api.py` 951、`policy.py` 287、`caps_registry.py` 224。
- **顺带逮到一处真 bug（不是面板的锅）**：`http://127.0.0.1:8777/console`（**少尾斜杠**）会直接回 `index.html`
  但 URL 不变 ⇒ 页面里的 `./app.js` / `./skin-cube.css` 被解析成 `/app.js` / `/skin-cube.css` ⇒ **整页 404**，
  看上去就是「没样式、按钮全不响应」。实测：`/skin-cube.css` 404、`/console/skin-cube.css` 200；首屏截图为默认灰按钮、无皮肤。
  已在 `console-server.py` 的目录分支补 **302 补尾斜杠**（保留 query）：`/console` → `/console/`、`/console?x=1` → `/console/?x=1`，
  `/blueprint3d` 这类独立页同样受益。
- **新增工具** `tools/codex-scripts/engine-layout.py <root>`：只读体检「exe / 聊天模板 / 权重」三样，
  给上一批 `_engine_bin()` / `_chat_template()` 的两布局口径一个现场读数（不写盘、不起进程、不加载权重）。
- **验证**：`guard-three.py` 5/5 全绿；产品侧 `cap_self op=verify` → `registry 427 = snapshot 427 = dispatched 427`、`failed=[]`。
- **待推产品（需 LIKE）**：`holo_pet_w3/console/impact-board.js`、`holo_pet_w3/console/index.html`、
  `holo_pet_w3/console/skin-cube.css`、`tools/console-server.py`、`tools/codex-scripts/engine-layout.py`。

## 2026-11-06 · 第三十批：`engine-up.py` 的两套实现从根上并回一套（引擎只扫 `vendor/` 的锅）

- **触发**：开发仓 ↔ 产品目录做逐文件对账（内容归一后 **125 处不一致**），其中**只有 3 处是产品侧更新**：
  `console/index.html`（另议）、`tools/gen-console-data.py`（注释与换行，已收回开发仓）、
  `tools/engine-up.py` —— 一 diff 就看出不是"谁新谁旧"，是**同一件事的两套实现**。
- **根因**：`gbt_allinone/tentacle/commander._engine_bin()` **只扫 `vendor/`**。实测两种布局：
  · 开发仓：`vendor/llama/llama-server.exe` ✅
  · 打包版：`tools/llama/llama-server.exe`，`vendor/` 下 0 命中 ❌
  ⇒ 于是 `engine-up.py` 被写成两套：开发仓那套委派 `commander.start()`（打包版会 rc=2 起不来），
  产品那套自拼命令行（躲开 commander）。两边各自都只在自家布局里对。
- **修在根上**：`_engine_bin()` 改成 **`tools/llama` → `vendor` 两处都扫**（环境变量仍最优先），
  失败时的 `reason/how` 一并改准。`engine-up.py` 保留**委派**版本（单一真源），另把「引擎自己扫 vendor」
  那句过期注释改准。实测：`C.ROOT` 指开发仓 → `vendor/llama/…`；指打包版 → `tools/llama/…`，两处都命中。
- **产品侧三源对账转绿**：`registry 427 = snapshot 427 = dispatched 427`，`failed=[]`
  （补推 `data/capabilities.json`：产品那份停在 2026-11-02 / 390 位）。
- **对账口径**：CRLF/LF 与 BOM 归一后再比，避免把换行差异当成"两个版本"（原先 137 → 真实 125）；
  125 里 124 处是开发仓更新，产品侧只剩 `console/index.html` 一处待定（`im-*` 改动影响面板 vs 开发仓 `om-*` 触手面板）。
- **顺带挖出同一类布局依赖的第二处：聊天模板**。`start()` 原先把模板写死 `ROOT/vendor/llama/gbt-user-assistant.jinja`，
  而打包版 `tools/llama/` **根本没带这个文件** ⇒ 引擎退回 GGUF 内置 Qwen 模板，普通对话里注入
  「You are Qwen, created by Alibaba Cloud.」，问「你是谁」会答成别的名字（正是主人要的「人性化」被它吃掉的地方）。
  已抽出 `_chat_template(engine_path)`：**先看引擎 exe 旁边 → tools/llama → vendor/llama**，找不到如实返回 None。
- **新增 5 条布局判据**（`gbt_allinone/tests/test_engine_layout.py`，只碰临时目录、不起进程）：
  两种布局都要找到 exe · 都没有时 reason 必须同时点出两处（负对照）· 模板优先取 exe 旁边 ·
  模板不存在时返回 None 不编路径（负对照）· `start()` 必须带 `--chat-template-file`。实测 5/5 过。
- **既有红如实**：`test_framework` 18 红里，`quant_*` / `tentacle_chain` 这类是**本机引擎 8111 没起**（环境），
  `brain_route_cn` 用改前索引复跑同样红（`ocr` vs `count_words`，与本次无关）。

## 2026-11-06 · 第二十九批：`caps_registry` 里逮到 4 个位被写了两次（431 键 → 427 名）；3 个真分叉全部合并

- **主人令**：「可以固化好别又搞错了出现好几个版本，你全量扫描一遍」。上一批扫的是
  「cap ↔ 分派分支」与「同名文件 sha256」，这一批把**注册表自己的字典字面量**也扫了 —— 结果是最隐蔽的一类：
- **`caps_registry.BENIGN_CAPS` 字面量里有 431 个键、只有 427 个唯一名**：`body_realtime` /
  `vision_grounding` / `vision_arsenal` / `ocr` 四个位在**文件末尾又被"补登"了一遍**，与前面的定义逐字相同。
  Python 对重复键**静默取后者**、不报错不警告，所以 `len(BENIGN_CAPS)` 一直是 427、
  `op=verify` 也一直绿 —— 但**改前面那处等于没改**。已删末尾 4 处（46 行），现 427 键 427 名零重复。
- **新增 3 条判据**（`tests/test_capability_registry.py`，该类现共 11 条）：① 字典字面量里一个能力名只许出现一次；
  ② 该判据的负对照（合成重复键必须报红）；③ 427 是契约（去重后必须仍是 427）。实测 11 条 10 过，
  余 1 条仍是既有环境缺件 `holo_pet_w3/window.js`。
- **3 个真分叉全部落定**（判定一律用证据，不看行数长短）：
  · `caps_registry.py`：17 条 desc 分叉，**16 条取开发仓**（把会过期的节点数/星标数改成「以 op 现查为准」；
    `cap_self` 的「32 域」、`console_hub` 的「427 能力」实测都对，产品侧写的 30 域 / 209 能力已过期）；
    `omni_open` 取产品侧（仅多「万能插·」前缀）。**`omni_plug` 两版都不对** → 合并出一条新的：
    产品侧写的 `op=all/all_status/attr` 在 `omni_plug.py` 里**一个字面都不存在**（2026-11-03 起只剩
    `surface_audit`/`full_sweep` 与 `discover`），开发仓那版又把「全开」触发词整个删了 →
    改成**真 op 口径 + 保留「万能插全开」说法**，路由实测 `score "万能插全开"` → `omni_plug` 1.5。
  · `holo_pet_w3/shell/main.cjs`：开发仓是**严格超集**（行号指针 `1390/1277/1291` vs 产品的 `941/836/842`；
    放行本机 console 页面网格 vs 简单 deny；服务失败带 `status`）⇒ 无需回灌，直接推产品。
  · `holo_pet_w3/console/app.js`：产品侧更新 14 分钟且更干净（复用 `ctxOf(d)`、保留「方案 1」注记）
    ⇒ 收回开发仓，两侧内容已一致（仅换行符不同）。
- **索引按 desc 重建**：`state/operator-index.json` → 427 个算子 / 已策展 375 / 待补 52；
  `state/codepage_index.json` → 4974 文件 / 124018 符号 / bad=0（`op=build` 8.2 s）。
- **三源对账全绿**：`cap_self op=verify` → registry 427 = snapshot 427 = dispatched 427，5 项检查全过。
- **既有红已 A/B 判白**（换回改前文件复跑，结果一字不差，文件已还原并核 sha256）：
  `test_caps_called_audit` 的 13 个内调型孤儿 · `test_redteam` 的 `claude_code` 缺 CLI 与监控可见性 ·
  `test_capability_registry` 缺 `holo_pet_w3/window.js`。
- 改前现场存证：`.archive/versions/2026-11-06/before-merge-2026-11-06/`（含 README 写清判定依据）。

## 2026-11-06 · 第二十八批：全量版本扫描 —— 427 个能力位实现唯一；清掉 1 处重复分派、2 处真分叉、23 个版本残片

- **主人令**：「固化好，别又搞错了出现好几个版本，全量扫描一遍看看有没有一个能力出现好几个版本的」。
- **扫描口径（三向）**：① `caps_registry` 的 427 个位 → `api.py` 分派分支；② 全树同名文件
  （29 组 / 90 个文件）逐个 sha256；③ 开发仓 vs 产品目录 `payload` 逐文件对账。
- **能力位实现：唯一**。427 个 cap 对应 427 条分派分支，没有「一个位两套实现」。
  扫出的 `health` / `create` / `inventory` 是通用函数名撞名（`brain_exec.health()` 之类），不是能力重复；
  `gbt_allinone/omni_web.py` 是**带钢印的真名门面**（`from .omni_web_cap import run`），不是副本。
- **真重复：12 位授权红队分派在 `api.py` 里粘了两遍**（原 553 行与 2665 行，627 字符整段相同）。
  前一条永远先命中、后一条是死代码 —— 「改错一条就以为有两个版本，而且改的是不生效的那条」。
  已删第二处；删后 12 位逐位实测仍能分派（`unknown capability` = 0）。
- **真分叉 2 个**（开发仓 vs 产品目录，不是"谁落后"而是"两边各改了一半"）：
  · `tools/look_grade_cap.py`：产品侧已改用 `_opcall.call`（全仓 58 个模块在用），但把
    `needs_dependency` 兜底弄丢了（`fg = _fg()` 提到 try 外）。已把 `_opcall` 合并进开发仓，
    **保留**兜底 —— 现在开发仓是两者的严格超集。
  · `tentacle/commander.py`：开发仓有 2026-11-04 的权重指针修正（`weights.base()`，
    原先写死 8792 与指针里的 8111 分裂）+ `INTENT_ALIASES` 中文别名回填；产品侧还缺。
    ⇒ 待推产品（需主人 LIKE）。
  其余 **47 个**是产品单侧落后（开发仓更新），不是分叉。
- **版本残片 23 个**（`gbt_allinone/` 11 个模块的 `.prev/.bak-*` + 4 份能力清单快照 + 根目录 2 个）
  整体移到 `.archive/versions/2026-11-06/`（**只移动、不删除**，附 INDEX.md 与放回命令）。
- **登记指针漂移 3 处已校正**：`holo_pet_w3/shell/main.cjs` 的 `caps_registry.py:1373/1260/1274`
  → 实测 `1390/1277/1291`（`prompt_bridge` / `coze_mail` / `create`）。
- **新增 3 条判据**（`gbt_allinone/tests/test_capability_registry.py`）：
  ① 一个 cap 只许一条分派分支（只认 `If` 语句，外层 `in` + 内层 `==` 的合法嵌套不误报）；
  ② 该判据的负对照（合成两条同 kind 必须报红）；③ 活代码目录不许出现 `.prev/.bak` 残片。
  实测 8 条用例 7 过（余 1 条是既有环境缺件 `holo_pet_w3/window.js`）。
- **基线已重新盖**：`outputs/repo-pack/files.jsonl` 整表重建（追加式清单必须先挪开）→
  `state/drift/baseline.json` 8924 件；`drift` 实测 **added 0 / modified 0 / deleted 0**。
  守护闸五项全绿；主测试套 **142 OK / skipped=6**。

## 2026-11-06 · 第二十七批：监控改用触手本体读数；顺手拔掉三处"每次都要交"的性能税

- **主人令**：「监控使用触手来精准监控就好了」。原来 `/api/omni?op=monitor` 的
  `tentacle` 域只报**资产绑定**（assets/pairs/caps_bound），跟"触手现在准不准"无关。
  现在增报触手本体的一手读数：13 邻域 · 动作 127/127 全覆盖 · `uncovered=0` ·
  `grab_ok`/`eye_ready` · 缺依赖名单 · 文件主权（2928 件 / owned 812 / 孤儿 0 /
  能力位归属 427/427）。控制台新增「触手全域」卡，与「触手绑定」并列。
- **不重扫**：`trunk_cover op=scan` 实测 **7.6s**（2928 文件 + AST），塞进 2.5s 轮询会互相踩。
  监控只读它上一次落盘的 `state/trunk-cover.json`，并带 `scanned_at` + `stale` 阈值位。
  实测 `/api/omni?op=monitor` 冷 0.27s / 稳态 **0.035s**。
- **不许把会自己走的数字放进 diff**：`scan_age_s` 每轮 +0.1s，会把台账刷成一堆
  "变化"（与 `omni_plug` 的 `status` 空行同类）。改为只报 `scanned_at`，年龄由前端现算。
- **三处性能根因（实测）**：
  ① `omni_lines.ensure_graph` 从盘上读回图时没设 `at`，age 从 1970 年算起 ⇒
    "刚读到的图"被判过期、当场再整表重建 → `sample()` **2.14s → 0.035s**；
  ② `build_graph` 每 120s 全量重解析 748 文件，改成按 `(mtime,size)` 增量 →
    整表 **2.56s → 1.09s**、增量 **0.60s**，且与旧图**逐节点逐边完全一致**（1423 节点 / 1829 边，差集 0）；
  ③ `_rel()` 对 1373 个文件逐个 `Path.resolve()` 走盘（0.34s）→ 纯字符串 `relpath`。
- **`trunk_cover` 漏配 `SKIP_DIRS`**：`pyembed/`、`store/` 没被跳过，456 个第三方文件被算成
  "孤儿"。补上后孤儿 **457 → 1**；把根目录 82 B 的 `hello.py` 样例归档到 `.archive/`（不删），
  再扫 **2928 文件 / 孤儿 0 / 能力位归属 427/427**，`op=verify` 三项全绿。
- **守护闸口径冲突（`guard-three.py check_omni`）**：`status` 已按设计不留痕，旧判据
  "跑一次 status 要让留痕长个儿" ⇒ 必红（实测 `128346 → 128346`）。改成双向：
  `status` 必须 **不**长（噪声门）、`energy` 必须长（写侧门），实测 `status_delta=0 / energy_delta=131`。
  五项全绿；相关测试 **142 OK / skipped=6**。

## 2026-11-05 · 第二十六批：清"登记幻影" —— 三条工具指向不存在的文件，28 个 npm script 里 21 条死链

- **起因**：第二十五批把"印出来的命令"修准了，但判据只覆盖 `.py` / `.md`。
  顺着"能不能真跑"往下查，发现三类**登记的幻影**：
- **① `LOCAL_TOOLS` 有三条指向不存在的东西**（11 条里 3 条）：
  · `deep_scan` / `omni_max` → `.scratch/scan-20260923/*.py`，**整个目录已不存在**，
    而 `.scratch` 按 AGENTS 定义就是"临时产物（可删）"；
  · `desktop-shell` → `holo_pet_w3/shell/preflight.cjs`，**文件不存在**
    （同目录 23 个文件逐个核过；`package.json` 的 `main` 指向的是 `shell/main.cjs`）。
  ⇒ 处置：摘掉前两条；`desktop-shell` 改指真入口 `shell/main.cjs`，删掉同样不存在的 `--rehearse` variant。
  现在 **9 条 path 全部真实存在、无一条落在临时目录**。
- **② 能力缺口如实记，不粉饰**：`deep_scan` 原来做「全树穿透 L1–L8」，
  而 `quick_scan` 只到 **L1–L5**（七面 + 安全面）——**L6–L8 那一层（重复/哈希/编码/BOM/断链）随脚本一起没了**。
  所以 `omni ask "深扫一遍"` 现在会如实回「🔴 没有一路命中」。
  这**是对的**：与其推一条指向 `.scratch` 的死命令，不如承认这层能力缺着，等人补回正式件。
  （`omni_max` 那条是真有替代：`cap_probe_all` 干同样的活。）
- **③ `holo_pet_w3/package.json`：28 个 script 里 21 条是死的**：
  · **17 个**引用的 `.py` 不存在（`taste-*` / `text-fatigue-*` / `ctx-chain-*` / `cg-*` / `release-runtime-sync` …）
  · **4 个**引用的 `shell/*.cjs` 不存在（`preflight` / `rehearse` / `startup` / `interact`）
  · **19 个**用 `py -3.14`（本机 `py -0` 只有 3.15）
  `npm run verify` / `pack` / `release:*` 全在里面 —— 也就是说**发布链整条跑不了**。
  处置：解释器一律改 `../pyembed/python.exe`；死链**不删名字**（CI/文档可能引用），
  改成会**明确报错**的哨兵：
      node -e "console.error('UNIMPLEMENTED: taste 需要的文件不存在 -> ../tools/codex-scripts/taste-guard.py'); process.exit(1)"
  跑 `npm run taste` 会得到一条说人话的错误，而不是含糊的 `Cannot find module`。
- **判据补两条**（`tests/test_no_dead_command.py` 4 → **6 条**）：
  · `test_local_tools_paths_are_real` —— 每条 `path` 必须真实存在，且**不许落在临时目录**；
  · `test_npm_scripts_reference_real_files` —— 引用的文件必须存在，**或**该 script 已标 `UNIMPLEMENTED`；
    且不许出现 `py -3.x` / `C:\Python3xx`。
  改前这两条会报 **3 条幻影 + 19 死解释器 + 21 死引用**。
- **读数**：判据 **60/60** · 三条默认闸全过 1147 ms · 语法 1908 个 `.py` / 0 失败 ·
  `skills_sync check` exit=0 · `audit-skill-roots` exit=0 ·
  `LOCAL_TOOLS` 9 条全部实物在位 · npm script 死解释器 **0**、哨兵 **20**。
- **仍未关的红**：审计 ③ —— `gbt-ai-101` / `gbt-selfgrowth` 未登记进
  `DISTILLED_DOMAINS`/`DISTILLED_CLUSTERS`，**归类决策待主人**。

## 2026-11-05 · 第二十五批：死指令还藏在**数据**里 —— 「✅ 可达」配着一条跑不了的命令

- **第三形态的假绿**：第二十批把 `print(...)` 行里的 `py -3.14` 全修了（73 处 / 21 文件），
  也立了判据。但判据只扫 `print(...)` 行与 7 份人读入口 —— **死指令还藏在数据结构里**：
  `LOCAL_TOOLS` 的 11 条里 **10 条** `invoke` 写着 `py -3.14 …`，能力位的 `invoke` 写的是裸 `python`。
  而 `invoke` 会被 `omni ask` **原样印给人照抄**：

      → py -3.14 tools/codex-scripts/quick_scan.py   ✅ 可达

  **标着可达、命令却是死的。** 这比"找不到工具"更坏：它让人以为问题出在自己身上。
- **修法**：`LOCAL_TOOLS` 与能力位 `invoke` 一律改 `./pyembed/python.exe`（11 + 1 处）。
  这些字符串**只用于打印，从不被执行**（5 处 print 全在展示路径上），所以改动零副作用；
  改完实测 `omni ask "扫一下…"` 印的已是 `./pyembed/python.exe tools/codex-scripts/quick_scan.py ✅ 可达`。
- **判据补上数据层**（`tests/test_no_dead_command.py` 3 → 4 条），两条不变量：
  · **A**：任何印出来的命令都不许含 `py -3.x` / `C:\Python3xx`（当前 LOCAL_TOOLS 0 条、427 位 0 条）；
  · **B**：本地工具的命令首 token 本机解析不到时，**这一条必须已标 🔴 并写明原因** ——
    钉的是"命令能跑"与"标没标红"**不许自相矛盾**。
    这条不变量是**被真红逼出来的**：第一版我写成"所有命令都必须能跑"，当场红了 `desktop-shell`
    （`electron` 本机没装）—— 可它**已经诚实地标着 🔴「实物不存在」**。
    真正要挡的是「✅ + 死命令」那种组合，不是"承认自己缺依赖"。
- **顺带写明一条边界**：`_py_parses` 的 docstring 加了 —— **语法通过 ≠ 跑得起来**。
  `.cjs` 里 `require('electron')` 而 `node_modules` 缺失时，`node --check` 照样过，真跑却起不来
  （本机 `holo_pet_w3/node_modules` 现在就是缺的）。别拿前者冒充后者。
- **一次没落成的改动（记下来当纪律样本）**：第一版补丁在构造替换串时用了 `%` 格式化 + `\p` 转义，
  抛 `TypeError` / `SyntaxWarning`。因为全程 `ast.parse` 在前、`os.replace` 在后，
  **盘上一个字节都没变**，跑出来的还是旧输出 —— 当场就能发现，而不是留个坏文件过夜。
- **读数**：判据 **58/58** · 三条默认闸全过 1148 ms · 语法 1908 个 `.py` / 0 失败 ·
  `skills_sync check` exit=0 · `audit-skill-roots` exit=0。
- **仍未关的红**：审计 ③ —— `gbt-ai-101` / `gbt-selfgrowth` 未登记进
  `DISTILLED_DOMAINS`/`DISTILLED_CLUSTERS`，**归类决策待主人**。

## 2026-11-05 · 第二十四批：三处"可达性"其实是三件事 + 三份根清单钉成一份

- **巡检起点**：`omni ask` 同时给三通道"能不能用"，但三处说的是**三件不同的事**：

  | 函数 | 真正回答的问题 | 最容易被误读成 |
  |---|---|---|
  | `skill_reachable` | 本会话**能不能按名字加载**（`<根>/<名>/SKILL.md` 在不在） | "这个技能好不好" |
  | `cap_auto_runnable`（原 `cap_reachable`） | 能力位**能不能免卡无参自动跑** | **"能力位可不可达 / 坏没坏"** |
  | `local_tools()` | 工具**实物在不在 + 语法能否解析** | "工具能不能完成任务" |

- **最刺眼的一条**：`see_camera`（打开摄像头）在 `cap_auto_runnable` 里是 **False**，
  理由「注册表未标 safe」—— 它**完全可用**，只是不能免卡自动跑。
  实测 427 位里 False 的 **163 个，没有一个是"实现缺失"**，全是门类原因：
  未标 safe(70) · 需参数(34) · 有侧效应(10) · 名字带写动作(9) · 要过授权门 · 有后果的域。
  ⇒ 把这种 False 读成"能力位坏了"，结论会**完全反过来**。
- **处置一：正名。** `cap_reachable` → `cap_auto_runnable`。
  而且它**一次都没被调用过**（死函数），名字却足以误导后面接手的人。
  保留 `cap_reachable` 作历史别名（`return cap_auto_runnable(c)`），docstring 明写"别再用"。
- **处置二：修过期注释。** `skill_reachable` 的 docstring 写"只看本会话实测真读的**两个**根"，
  实际 `SESSION_SKILL_ROOTS` 已是 **3 个**（加了项目内 `.agents/skills` 那批）。文档过期也是过期。
- **处置三：三份根清单钉成一份。** 同一件事实（"本会话读哪几个技能根"）在**三处各写一遍**：
  `omni.SESSION_SKILL_ROOTS`(3) · `audit-skill-roots.py` 的 `LOADED`(3) · 计数判据里的 2 个 hub。
  谁加删一个根，另外两处不会自动跟 —— 又回到"同一件事两个出口两个结论"。
  新增判据把它们锁在一起：**只改一处就红**。
- **负面实测（证明锁会红）**：只给 `omni.SESSION_SKILL_ROOTS` 塞一个假根 → 判据立刻报
  「只在 omni：`<仓>\skills`」。当前两侧集合**逐条一致**。
- **另加一条**：**「装在哪」的两个枢纽必须都在会话根清单里** ——
  否则会出现"`skills_sync` 装进 `<hub>/<名>/`（加载器看得见）、`omni` 说读不到"的经典分裂。
- **判据**：新增 `tests/test_reachability_agreement.py`（**7 条**）：
  ① 两份根清单一致 ② `skill_reachable` 不许假绿也不许假红（逐条对盘） ③ **False 不许表示"缺失"**
  ④ False 理由必须归入已知门类 ⑤ 别名不许与新名分叉 ⑥ 枢纽必须被会话根覆盖 ⑦ 根清单每项都有说明。
- **读数**：判据 **57/57** · 三条默认闸全过 1538 ms · 语法 1908 个 `.py` / 0 失败 ·
  `skills_sync check` exit=0 · `audit-skill-roots` exit=0。
- **仍未关的红**：审计 ③ —— `gbt-ai-101` / `gbt-selfgrowth` 未登记进
  `DISTILLED_DOMAINS`/`DISTILLED_CLUSTERS`，**归类决策待主人**。

## 2026-11-05 · 第二十三批：把「万能插」这个品牌词从 8 个位的自述里摘出来

- **起因**：第二十二批留下的已知限制 —— 用户说「万能插」，路由落到 `wf_cache_clear`（"查运行记录"）
  而不是本体 `omni_plug`。因为 **8 个位**同时在 desc 里自称「万能插」：
  `wf_define` / `wf_run` / `wf_status` / `wf_resume` 前缀是「万能插执行引擎：」、
  `wf_cache_clear` 是「万能插：清空传输缓存」、`omni_open` 是「万能插·全自动打开：」。
- **改法（6 处，逐条判断，不一刀切）**：
  · 4 个 `wf_*` 前缀 → **「工作流引擎：」**（它们本来就是工作流引擎，借品牌当前缀）
  · `wf_cache_clear` → 「工作流引擎：清空传输缓存」
  · `omni_open` → 「全自动打开：」（它的名字就是 omni_open）
- **⛔ 一个字没动的三处（硬约束）**：
  · `train_ground` 里**引述主人令原话**：「必须使用万能插来无死角训练大模型…」（×2）
  · `self_intake`：「**主执行器是万能插**」—— 这是事实陈述，不是品牌前缀
  · `brain_execute`：「（万能插线程池）」—— 技术事实
  改了就是**篡改史料/事实**。已写成判据（`test_quotation_is_preserved`）防止后人"清理"时洗掉。
- **关键教训（值得记在案上）**：**启发式无效时先查数据，别急着调权重。**
  「标题精确匹配」第一次加的时候**零收益**（top-1/top-3 一点没变），当时我撤掉了；
  真实原因是那时 8 个位的标题都叫「万能插」，精确命中打成平手。
  把数据改准之后（只剩 `omni_plug` 标题是「万能插」）再加回同一条启发式 —— **立刻生效**。
- **读数**：
  · 「万能插」→ **`omni_plug` 10.82** ✅（改前是 `wf_cache_clear`）
  · 「全自动打开」→ `omni_open` 13.21 ✅
  · 金标准 top-1 **154 → 155/203**（76%）· top-3 **184/203**（90.6% → 91%）
  · 噪声句 hits 仍为 **0**
- **快照同步**：`export-capabilities.py` 重导 427 条 → `data/capabilities.json` + `docs/capabilities-full.json`；
  `omni.py build` 重建图鉴。
- **文档同步 23 处**（`docs/能力总表.md` / `docs/capabilities/{engine,system,tentacle}.md` /
  `gbt_allinone/README.md` / `docs/90-what-she-can-do.md` / `CAPABILITIES-索引.md`），
  替换后全仓 `.md` 残留 **0**。
- **刻意不动的一处**：`data/intent-lexicon.json` 里的「万能插·全自动打开」——
  那是**人写的人工词表**（文件注释明写「say 是人写的」），而且这句作为**人的口语说法**依然成立，
  派生物才该重导，人工词表不该被脚本改。
- **判据**：`tests/test_cap_scoring.py` 5 → **7 条**（新增：品牌词必须落到本体 · 引述不许被改）。
- **读数**：判据 **50/50** · 三条默认闸全过 1196 ms · 语法 1907 个 `.py` / 0 失败 ·
  `skills_sync check` exit=0 · `audit-skill-roots` exit=0。
- **仍未关的红**：审计 ③ —— `gbt-ai-101` / `gbt-selfgrowth` 未登记进
  `DISTILLED_DOMAINS`/`DISTILLED_CLUSTERS`，**归类决策待主人**。

## 2026-11-05 · 第二十二批：能力位打分重写（**安全面**）+ 一个 16 倍性能坑

- **为什么这是安全面**：`omni run` 据 `rank()` 的 caps 排序**自动选位执行**。改排序 = 改行为，
  所以本批先立**金标准**再动手，且判据里单列一条「门不许被顺手放松」。
- **金标准不是我编的**：能力位 `desc` 里写着「常用说法：A / B / C」（`AGENTS.md` §4.1 就用它抽触发词）。
  抽出来 **237 句**，剔除「同一句被多个位声明」的歧义句（`卡片` 被 `ui_kit` 和 `design_atlas` 同时声明、
  `动画` 被三个位声明 —— 留着等于要求模型猜作者偏好）⇒ **203 句干净集**。
- **改前读数**：top-1 **69%** · top-3 **85%**；噪声「今天天气不错适合出去走走」拿 **1.50**、
  「嗯嗯好的可以我想一下再说」拿 **4.50**，与真查询的 3–6 分**完全重叠** ⇒ cap 通道当时没有可用阈值。
- **改法（与技能侧同一套道理，三项都不再"裸乘"）**：
  · **整名命中** 6 分（用户直接点名 `body_eye`）；
  · **整句出现在描述里** 5 分（短语级证据：bigram 汤里"卡片"能撞十几个位，整句只出现在一个位）；
  · **描述 bigram** 权重 10 但**按 √长度归一**（长 desc 不再白占便宜）；
  · **域提示** 权重压到 2 并归一（"vision"/"llm" 又短又泛，原来是白送分）。
- **改后读数**：top-1 **76%** · top-3 **90.6%** · 噪声最高 **1.71** · 正确位分数中位 **6.32**
  （94% 在 5.0 以上，只有 3/194 低于 2.0）⇒ **分隔带出现了**，`min_hit_cap=2.0` 有据可依。
  `cmd_ask` 因此撤掉那条「这一节的分数不能当命中判据」的警告，改成"过了门槛的候选"+
  低于门槛的另列标明噪声。
- **安全面复核**：`auto_run_verdict()` **一个字没动**（它才是"能不能自动执行"的判据）。
  新判据钉死：凡需要参数或带侧效应的位，无论分多高都不许被判可自动执行；
  另实测 `omni run "今天天气不错适合出去走走"` 现在返回 **🔴 没有落点，不猜（exit=1）** ——
  改前它会拿噪声分随便选一个位。
- **试过又撤掉的**：「标题精确匹配」（desc 第一个冒号前那段）。实测 top-1/top-3 **一点没变**，
  且 `wf_cache_clear` 的标题字面上就叫「万能插」—— **8 个位都这么自称**，是**数据层歧义**，
  不是打分能解决的。**没有实测收益的启发式不留**。
  已知限制如实记下：「万能插」这 3 个字被 `omni_plug` + 7 个 `wf_*` + `omni_open` 同时自称，
  所以它 top-1 落到 `wf_cache_clear`；要修得改那 8 条 desc 的措辞（编辑决策，不在打分这一层）。
- **顺带挖出一个 16 倍的性能坑**：批量路由 203 句跑了 **28.8 秒**。逐层查：
  ① `load_atlas()` **每次 rank 都重读+解析 400KB JSON**（无缓存）；
  ② `score_cap` 每次都重算 `grams(长 desc)` —— 203×427 = **8.6 万次**；
  ③ `local_tools()` 每次都把每个本地工具脚本重新 `ast` 解析 —— 4000 次。
  三处都按 `(路径, mtime_ns, 大小)` 或图鉴代次缓存。**28.8s → 1.79s**。
  缓存不改变结果：复测 top-1 76%、噪声 0 hit 与缓存前一致。
- **判据**：新增 `tests/test_cap_scoring.py`（5 条）—— 金标准非空且覆盖 ≥15 位 ·
  top-1/top-3 棘轮（只许升不许降）· **噪声必须 0 命中** · 真查询必须命中 ·
  **门不许被放松**。中途我还把一处缩进写坏过（`_data` 落在 `return` 底下 → UnboundLocalError），
  是判据当场逮出来的。
- **读数**：判据 **48/48** · 三条默认闸全过 1239 ms · 语法 1907 个 `.py` / 0 失败 ·
  `skills_sync check` exit=0 · `audit-skill-roots` exit=0。
- **仍未关的红**：审计 ③ —— `gbt-ai-101` / `gbt-selfgrowth` 未登记进
  `DISTILLED_DOMAINS`/`DISTILLED_CLUSTERS`，**归类决策待主人**。

## 2026-11-05 · 第二十一批：**布局装错了** —— 逐字节一致 ≠ 加载得了

- **这条线终于到底了**：从"文件不存在" → "契约不认" → "看不见" → "调不到" →
  最后发现真根因是**同步器装错了布局**。
- **铁证（三处独立代码路径都说同一个规范）**：
  · `omni.skill_reachable()` 查 `<root>/<技能名>/SKILL.md`
  · `tentacle/skills_hub.install()` 写 `<target>/<name>/SKILL.md`
  · `skills_hub.pack()` 打的 zip 根是 `<name>/SKILL.md`
  而 `skills_sync` 把 `superpowers` **整包**拷成 `<hub>/superpowers/<子技能>/`，于是运行时按
  `<hub>/<技能名>/` 找 —— **27 个子技能（superpowers 20 + shuohao 7）一个都加载不了**。
  实测：枢纽顶层只有 5 个包名；按 `<root>/<名字>/SKILL.md` 查，只有 `gsap` 命中（包名刚好=技能名）。
  **可 `check` 当时报"四条全过、逐字节一致"** —— 文件都在，布局错了。这是「盘上对」被念成「生效了」的最贵一版。
- **`skills_sync` 重写为技能级（不再是包级）**：
  · 目录**有**根 `SKILL.md` ⇒ 它自己是一个技能；
  · 目录**没有** ⇒ 每个带 `SKILL.md` 的直接子目录各算一个技能，**平铺**安装到 `<hub>/<技能名>/`。
  · 为什么不用 rglob 一把梭：`taste-skill` 有根 SKILL.md，内部子件是"按需加载的章节"不是独立技能。
- **又抓到一处自欺**：`_hub_skills()` 原来按 **frontmatter 名**做键，于是枢纽里叫 `taste-skill/` 的目录
  被当成技能 `design-taste-frontend` 并判"一致" —— 而加载器按 `design-taste-frontend/` 根本找不到。
  改成**按目录名认**（加载器就是这么找的），立刻如实报出 `1 未安装 / 1 孤儿`。
- **旧布局清理（先证后删）**：`taste-skill/`(1 件) 与 `superpowers/`(20 件) 逐字节比对与新平铺目录
  **全部相同**，才移入 `state/skills-hub-backup/<时间戳>-layout-cleanup/`（不硬删）。
- **新判据**：`tests/test_skill_count_agreement.py` 加 `test_every_skill_is_loadable_by_layout` ——
  每个技能必须能按 `<枢纽>/<技能名>/SKILL.md` 解析到。**它就是钉死"逐字节一致 ≠ 装对了"的那颗钉子。**
  同时把 `test_skills_install_sync.py` 的独立枚举从"顶层包数(8)"改成"技能级(33)"，两边才能对账。
- **顺带抓出自己的假命中**：给技能打分加 `min_hit=1.0`（实测噪声底 ≤0.26、真命中 ≥3.0，中间是空的）。
  一切分，`小说人物小传怎么写`(0.16)、`git 分支怎么规划`(0.26) 立刻露馅 ——
  **它们此前是靠噪声分"通过"我自己的判据的**。没降阈值，补了能真命中的触发词（`人物小传` / `分支规划`）。
  `cmd_ask` 同步改：弱匹配单列并标明"几乎肯定是噪声，别当命中"。
- **能力位通道的诚实标注**：实测无关句也能拿 1.50、「嗯嗯好的可以我想一下再说」能拿 4.50，
  与真查询的 3–6 分**完全重叠** ⇒ cap 侧目前**没有可用的分数阈值**。
  不拿一个好看的数字糊过去：`cmd_ask` 在 cap 区直接印出这条警告。
  （重写 cap 打分属于安全面改动 —— `omni run` 据此自动执行，留待单独一批。）
- **补会话技能根**：`SESSION_SKILL_ROOTS` 漏了项目内 `.agents/skills`，而审计的
  `LOADED = {user-agents, dsh-project, proj-agents}` 明写本会话读它 ⇒ 同一件事两个出口两个结论。已按审计为准。
- **读数**：`skills_sync check` **33/33 一致 · 孤儿 0 · exit=0** ·
  运行时 `<root>/<名>/SKILL.md` **33/33 可解析** · `brainstorming` 显示 **✅ 本会话可加载** ·
  判据 **43/43** · 三条默认闸全过 1231 ms · `audit-skill-roots` exit=0。
- **仍未关的红**：审计 ③ —— `gbt-ai-101` / `gbt-selfgrowth` 未登记进
  `DISTILLED_DOMAINS`/`DISTILLED_CLUSTERS`，属**归类决策**，待主人定。

## 2026-11-05 · 第二十批：技能路由的三个打分失真（不是词不够，是尺子歪）

- **起点**：第十九批补了 16 条短 desc 技能的触发词，8 句人话 8/8。
  本批先量剩下 17 条的**基线**（自然白话、刻意避开各自 desc 原词）：**14/32 = 44%**。
- **第一轮：补 15 条触发词** → **67%**。有进步，然后**卡住**了。
  失败模式很整齐：**同族兄弟互抢**（`小说改成剧本`→`novel-outline`、`参考图转3D`→`character-refs`），
  正解多半在 top-2。说明瓶颈不在词表。
- **拆开分数才看见三处尺子歪了**（都在 `omni.py` 的 `rank()` 技能侧）：
  1. **没按语料长度归一**：`score = len(hit) * 1.2`，desc 越长越占便宜 ——
     `character-refs`(450 字) / `gbt-ai-101`(1162 字) 靠"泛词多"压过精准的短描述技能。
     改：**人工策展字段高权重**（整名 4 / 触发词 3），**自由文本 desc 低权重且按 √长度归一**。
  2. **触发词按 bigram 堆**：`novel-outline` 的触发词 `"小说转短剧"` 含泛词 `小说`，
     于是「给小说配插画」让它与 `novel-art` 的精确词 `插画` **同分**（3.0 vs 3.0），
     最后靠描述 0.07 分反超。
     改：一条触发词里 **≥60% 的 bigram 被意图覆盖才算命中**，按覆盖率加权。
  3. **名字按 bigram 命中**：`gbt-ai-101` 的 bigram 含 `AI`，于是「前端不要AI味 要设计感」
     让它命中 1 次拿 **4.0 分**，压过 `design-taste-frontend` 两条精确触发词；
     `ref-to-3d` 同因抢到「小说分镜拆解」。
     改：**整名出现在意图里才算命中**（归一化后子串匹配），不再数 bigram。
- **读数**：44% → 67%（只加词）→ **23/23**（改尺子后）。A 组 8 条**不许倒退**，改完仍 8/8。
- **一条“失败”其实是歧义，我没改判据迁就自己**：`人物设定图怎么出` → `novel-characters`。
  因为 **「人物设定」正是它的触发词原文**，拿第一站得住；是我的期望写窄了。
  改用能区分的句子验 `character-refs`：`角色参考图怎么出` 3.24 ✅、`出张人设图` 3.0 ✅。
  判据里对三处**公认歧义**（gsap/gsap-official、staging/storyboard、worktree/git-workflow）
  显式写可接受集，其余一律单元素 —— 这是承认语料重叠，不是放宽标准。
- **覆盖层**：16 → **31 条**（33 减去 2 条自述「不要自动触发」的 `chinese-*`，继续排除）。
  合并逻辑改**覆盖层优先 + 上限 16** —— 否则 `gbt-ai-101` 自带的 12 条会把新词挤掉（实测坑）。
- **判据**：`tests/test_skill_triggers_overlay.py` 用例 8 → **23** 条（A 组 8 不许倒退 + B 组 15）。
- **读数**：语法 1906 个 `.py` / 0 失败 · 判据 **42/42** · 三条默认闸全过 1200 ms ·
  `audit-skill-roots` exit=0 · `skills_sync check` exit=0。
- **仍未关的红**：审计 ③ —— `gbt-ai-101` / `gbt-selfgrowth` 未登记进
  `DISTILLED_DOMAINS`/`DISTILLED_CLUSTERS`，属**归类决策**，待主人定。

## 2026-11-05 · 第十九批：技能触发词覆盖层（看得见 ≠ 调得到）

- **上一批留下的红**：第十八批把技能口径统一后，图鉴从 8 → 33 条，`superpowers` 那 20 条终于进了语料。
  **但立刻发现它们仍然调不到**：
  `ask "帮我把这个方案的发散思路打开一下"` → 0.4 `desktop-shell`；
  `ask "这个 bug 老修不好 要走系统化调试"` → 1.4 `clean_residue`。全是打偏。
- **先更正我自己的一个误判**：我上一轮说那 20 条 desc 是"英文短句" —— **错了**，
  它们全是中文（22–56 个汉字）。我是按长度猜的，没看内容。真正的病是**词不撞**：
  `brainstorming` 写「在任何创造性工作之前……探索用户意图、需求和设计」，人说的是「发散思路」；
  `systematic-debugging` 写「遇到任何 bug、测试失败或异常行为」，人说的是「老修不好」。
  语义同义、bigram 零交集 ⇒ 打分 0。唯一英文的是 `design-taste-frontend`（1155 字 / 0 汉字）。
- **为什么不直接改 SKILL.md**：那 20 条是 **vendored（第三方）**。改了 ① 与上游更新冲突（下次拉包白改）
  ② 立刻制造「源 ≠ 装」分叉 —— `skills_sync check` 会红，而且这个红是**我们自己造成的**。
- **改法：仓内覆盖层** `tools/codex-scripts/skill-triggers.json`（16 条技能 / 121 个中文说法），
  `omni.collect_skills()` 在 build 时并进 `row["triggers"]`，打分语料
  （`name + displayName + desc + desc_tail + triggers`，`omni.py:971`）自动吃到。**源件一个字节不动。**
- **两条陷阱（读原文才发现的）**：`chinese-code-review` / `chinese-documentation` 的 SKILL.md 明写
  「仅在用户显式 /命令 时调用，**不要根据上下文自动触发**」⇒ 给它们加触发词等于我们违反技能自己的规则。
  已列入 `_opt_out` 并由判据钉死。
- **读数**：8 句人话 **首选命中 8/8**（改前 0/8）。
  `发散思路 → brainstorming 4.8` · `老修不好 → systematic-debugging 10.8` ·
  `设计感 → design-taste-frontend 8.4` · `收尾开PR → finishing-a-development-branch 6.0`。
- **防回归**：新增 `tests/test_skill_triggers_overlay.py`（5 条）——
  ①覆盖层必须自带「为什么」②每个键必须是真技能（打错字不许静静失效）
  ③不许给 opt-out 的两条加词 ④**命中实证**（8 句必须首选命中）⑤触发词不许跨技能撞车。
  **负对照实测**：临时清空 triggers → 重建 → 8 句全部打偏、判据红在正确原因；恢复后 8/8。
- **读数**：语法 1905 个 `.py` / 0 失败 · 判据 **42/42** · 三条默认闸全过 1107 ms ·
  `audit-skill-roots` exit=0 · `skills_sync check` exit=0。
- **仍未关的红**：审计 ③ —— `gbt-ai-101` / `gbt-selfgrowth` 有源稿但未登记进
  `DISTILLED_DOMAINS`/`DISTILLED_CLUSTERS`，属**归类决策**，待主人定。

## 2026-11-05 · 第十八批：技能"装了 ≠ 看得见" —— 三个读者三个口径，统一到一个

- **症状**：`skills_sync check` 报"四条全过、8 个包逐字节一致"，`audit-skill-roots` 也绿 ——
  但 `omni ask "给小说写个分章大纲"` 命中不了 `novel-outline`，`brainstorming` /
  `systematic-debugging` 这些压根不在图鉴里。典型 F18：「盘上对」被念成「生效了」。
- **根因（同一份盘，三个读者三个数）**：

  | 读者 | 口径 | 数出 |
  |---|---|---|
  | `gbt_allinone/tentacle/skills_hub.py:56` | `rglob("SKILL.md")` | 26（漏 `gbt_allinone/skills` 的 7） |
  | `tools/codex-scripts/omni.py:613` | `iterdir()` 一层 | 8（其中 **2 条 desc=0 空壳**） |
  | `tools/codex-scripts/audit-skill-roots.py:75` | `iterdir()` 一层 | 6 / 4 / 2（与 omni 打架） |

  `skills/superpowers/` 是**插件集合**：20 个子目录各带 `SKILL.md`
  （brainstorming / systematic-debugging / test-driven-development / writing-plans …），
  自身**没有根 SKILL.md**；`shuohao/` 同理 7 条。一层枚举把它们收成"一个包、desc 为空"，
  **27 个子技能在图鉴里彻底隐形，路由打分永远 0**。
- **先钉不变量再动手**（33 个 SKILL.md 实测）：父目录也带 SKILL.md 的 = **0**、
  缺 frontmatter `name` 的 = **0**、重名 = **0** ⇒「每个 SKILL.md = 一个技能」成立，
  递归不会重复计数，也不需要例外规则。（这条不变量已写进判据，谁破坏谁先红。）
- **改法（两处，各 1 个函数）**：
  - `omni.SKILL_ROOTS` 补 `gbt_allinone/skills`（`skills_sync` 的第二个源，从来没被 omni 扫过）；
    `collect_skills()` 对 `agent-skill` 根改 `rglob`，`design-asset` 仍走一层（那是"料"，递归会炸）。
  - `audit-skill-roots.py` 同步改 `rglob`，索引键改取 **frontmatter `name`**（原来按目录名，
    于是 `skills/taste-skill` 的 `name: design-taste-frontend` 与 omni 对不上）；
    补 `pkg-source` 根 + `SOURCE_KEYS`，否则 shuohao 的 7 条会被误报 **⑤ 孤本**
    （工具建议「拷到 skills/ 抢救」，而源稿根本没丢）。
- **读数**：图鉴 技能 **8 → 33**（去重前 42 · 多根 9）· **desc 为空 2 → 0** ·
  `skills_hub.validate` count 26 · 审计 `ws-source 26 / pkg-source 7 / proj-agents 24 / user-agents 9`，
  ①②④⑤⑥ 全 0，**exit=0**。
- **路由实证**：`omni ask "给小说写个分章大纲"` → `[2.4] novel-outline agent-skill`（改前 100% 命中不了）。
- **防回归**：新增 `tests/test_skill_count_agreement.py`（5 条）—— 独立枚举 vs omni 读者对账
  （漏/幽灵双向）、图鉴无 desc 空壳、图鉴条数 == 盘上、嵌套不变量。
  **负对照实测**：把口径退回一层 → 数出 8、判据报「漏 27 条」，红在正确原因上。
- **读数**：语法 1905 个 `.py` / 0 失败 · 判据 **37/37** · 三条默认闸全过 1181 ms。
- **仍红的（如实留着）**：
  ① 审计 ③ —— `gbt-ai-101` / `gbt-selfgrowth` 有源稿但没登记进 `DISTILLED_DOMAINS`/`DISTILLED_CLUSTERS`，
     属**归类决策**，不替主人编。
  ② 「可见 ≠ 可命中」—— `brainstorming`(58 字) / `systematic-debugging`(33 字) 的 desc 是英文短句，
     中文意图打不中。这是**描述质量**问题，不是计数问题，下一批单独治。

## 2026-11-05 · 第十七批：`skills_sync` 按**消费方契约**重建 + 死指令判据

- **`tools/skills_sync.py` 重建（按契约，不是按我的想象）**：上一版写的 `status()` 两个消费方**都不认** ——
  `gbt_allinone/tests/test_skills_install_sync.py` 要 `survey()`，`tools/tentacle_bind.py:627-633`
  （运行时 autobind）要 `survey()` + `do_sync()`，且读 `r["own"]` / `r["status"]` /
  `st["summary"]["ok"]` / `out["synced"][i]["skill"]` / `out["backup_root"]`。
  现逐字对齐：`survey()` 返回 `rows / summary / home_hub / hubs / sources`；
  `do_sync()` 覆盖前**自动备份**到 `state/skills-hub-backup/<时间戳>/<hub>/<skill>/`，
  复制完**回读指纹比对**，不符即判失败（不谎报成功）。
- **口径照 `LAYOUT.md:71/:86`，不另立一套**：源 = `skills/` + `gbt_allinone/skills/`（一个顶层目录 = 一个包）；
  装 = `~/.agents/skills/`（自有）+ 仓内 `.agents/skills/`（第三方）。第三方按**显式名单**声明
  （`gsap` / `gsap-official` / `ref-to-3d` / `superpowers` / `taste-skill`），不靠猜。
- **首次真装**：两个枢纽根此前**都不存在**（技能从没装过）⇒ 8 个包 / 183 文件 / ≈5.3 MB 一次装上；
  `check` 四条判据全过（一致 8 / 分叉 0 / 未安装 0 / 孤儿 0）。
- **负向验证（证明它会红、不是只会说 OK）**：人为给枢纽里的 `gsap/SKILL.md` 追加 1 字节 ⇒
  `⚠️ gsap 分叉（内容异 1）` exit=1 ⇒ `sync` 备份并修复 ⇒ 读回 `一致 8/8` 且**字节完全复原**。
- **判据自身失真修掉**：`test_tool_present_and_ran` 原来硬断言 `len(rows) > 50`，而实测源根下
  **8 个包 / 33 个 SKILL.md**（`superpowers` 20 子、`shuohao` 7 子），**任何口径都到不了 50** ⇒
  这条永远红且永远修不好。换成**独立枚举对账**：不经被测工具自己数一遍包，要求
  `rows == 独立包数 + 孤儿数`。源空了 / 工具漏报 / 口径漂了，三种都在这里红 —— 比魔数强。
- **补回根目录 `LAYOUT.md` 镜像**：`MIRROR_PAIRS` 声明它必须有，实测**不存在**（9268 字节，指纹一致补回）。
- **死指令判据（新）**：`audit-skill-roots.py` 结论里印的修法是 `py -3.14 tools/codex-scripts/omni.py build`，
  而本机 `py -0` 只有 `-V:3.15[-64]`，跑 `py -3.14` 得到 `[ERROR] No runtime installed that matches 3.14`
  —— 用户照着跑**就是废命令**，还把"修不好"归因成"你没照做"。
  全仓扫「可执行指令层」：`print(...)` 行 **73 处 / 21 文件**全改 `./pyembed/python.exe`
  （`capability-supervisor.py` 的 `_norm_cmd` 仍能归一化，spawn 路径不受影响），
  README / CHARTER 各 1 处同批修；改前预判影响面 **1 跳 49 节点 / 强边 38**。
  新增 `tests/test_no_dead_command.py`（3 条，含负对照：喂假行必须认出来），
  口径刻意窄（只查 print 层 + 7 份人读入口），`CHANGELOG`/`PROJECT_BLUEPRINT` 作**历史档案豁免** ——
  那里写的是"当初坏过"，改了就是篡改凭证。
- **图鉴重建**：`state/skill_atlas.json` 此前 `built_at=None · 收录 0 条`（从没建过，盘上技能对它全隐形）。
  用 `pyembed` 重扫：400.7 KB · 427 能力位 · 技能 8 条（去重前 10，跨目录 2）⇒ 审计 ⑥ 转绿。
- **读数**：语法 1903 个 `.py` / 0 失败 · 判据 **32/32**（含新增 3 条）· 三条默认闸全过 1322 ms
  （万能插留痕 310 行 / 多域 6306 节点 / 探测超时 63.6 ms / 运行时 pyembed 3.12.10 ✅）。
- **仍红的（如实留着，不粉饰）**：审计 ③ —— `gbt-ai-101` / `gbt-selfgrowth` 在 `skills/` 有源稿，
  但没登记进 `DISTILLED_DOMAINS` / `DISTILLED_CLUSTERS`。这是**归类决策**（该归哪个域/簇），不替主人编。

## 2026-11-05 · 第十六批：接线图补两层真依赖（import / impl）+ 描述去数字

- **权重口径 v2 → v4**（`tools/codex-scripts/wiring-build.py`）：
  - **v3 `import` 层**（KB=1.0）：`edges.jsonl` 只有 `path` / `cap` / `cap_mention` 三类，**全是"文本提及"**，
    从来不解析 Python import。结果 `api.py` 里明明写着 `from . import codex_bridge as _CB`，
    图里 `api.py ↔ codex_bridge.py` 却是 **0 条边**。AST 解析 2272 个 `.py`，补 **2200 条**真依赖；
    别名 `as _CB` 不影响结果（连的是模块，不是符号）。
  - **v4 `impl` 层**（KB=1.2）：cap↔code 此前只靠"文件里出现能力名"建立，可实现件往往**不含**能力名
    （`codex_bridge.py` 里没有 `codex_tools` 四个字，派发写在 `api.py`），于是 7 个 codex 位到本体永远 2 跳。
    现从 `api.py` 的 `if kind == "x"` 分支静态挖实现模块，**405/427 位可解析**，417 条 cap→code 映射。
    口径：一条 import 只归属**它所在 if 链**的能力名，不继承兄弟分支 —— 否则
    `if kind in (A,B): import X` 会把后面的 `Y` 也算给 A/B，权重虚高比漏连更糟（它会让人以为改 Y 必查 A）。
  - 触手树 `MY_WEIGHT_RULE` 同步 **2 → 4**。不同步它**不报错**，只会悄悄「退回自建」，那张图白算。
- **读数**：节点 6305→6306（+1 是仓库新增 `state/commander/coverage.json`，与本次无关）·
  无向边 48908→51197 · 强边 18768→21256 · 分量 1 · 100% · `api.py` 强边 400+ → 930。
- **`cap:codex_tools` 打通 1 跳**：权重 11.71 → 12.55（增量 0.832 = `1.2×log1p(1)`，无重复计数）；
  同批 `codex_chat` / `codex_models` / `codex_interrupt` / `codex_turn_send` 同步打通。
- **desc 去数字**：`impact_check` 的 desc 原写「现读 **6301 节点 / 951536 有向边 / 337 个能力位 /
  depth=2 = 4859 节点 / tentacle_arm 2 跳 = 342 节点**」—— 图重建三次它错了三次。现改指 `op=status`
  现查；`gbt_allinone/tools/impact_check.py` 的 docstring 也写死过同一组数（且原文还写着"每次调用现场数，
  不抄注释"），一并摘除并留血账。
- **快照重导**：`data/capabilities.json` 被 `cap_self` / `commander` / `pulse_core` / `orchestration` /
  `catalog` / `model_bridge` / `static_check` **七个模块**读取 —— 改注册表不重导出，读端拿到的还是旧 desc。
  已用 `export-capabilities.py` 重导（427 条），`docs/capabilities-full.json` 同步；
  `docs/capabilities/system.md` **无生成器**（手工产物），两处旧描述已脚本原子改写 + 读回校验。
- **防回归**：新增 `gbt_allinone/tests/test_wiring_v4_guard.py`（7 条），钉死
  ①口径版本三方一致（构建器 / 图 / 读端）②desc 不许写死规模读数且必须指向 `op=status`
  ③生产快照与注册表逐字一致 ④`cap:codex_tools` 1 跳直达且进强边。
- **顺带查明（文档漂移）**：AGENTS.md §4.1 的三道门在本树**已失效** —— `extract_intents.py`、
  `intent_extracted.json`、`router.load_caps()` 全都不存在（`synapse.py` 只在 `.scratch/synapse/`），
  `capability_router.py` **不读 desc**。改 desc 对路由零影响，无需重建索引。
  另：AGENTS.md 写的 `run-tests.py` 也不存在，实为 `run-tests.ps1`。
- **遗留**：`comfy_forge` / `comfy_native`（「现读 1495 把」）、`bits_kit`（「216 组件」）同样写死
  外部环境读数，未清（性质与图规模不同：随用户环境变，不随本地构建变）。
- **impl 层扩到动态派发**（同日追加）：原先 impl 只认 `if kind ==` 分支体里的 import，
  而 22 个位的分支体里**没有 import** —— 它们是 `_im("." + kind, __package__)` /
  `spec_from_file_location(name, Path/"x.py")` / `_external_capability("quant_tech", kind)`，
  所以全部停在 2 跳。现按**参数形态**认这三种模式（不按函数名认，别名太多），补回 **10 个**：
  vision ×5 · tentacle_bind · penetrating_cross_scan · asset_index · control_loop · i2v_agnes。
  余下 12 个里，4 个（echo / count_words / health / audit_query）实现就在 `api.py` 本身，
  **2 跳是正确的，不该硬连**；另 8 个目标文件不在图（omission_detector / hook_enforcer /
  review_gate）或走外部业务模块（quant 系列 → `quant_tech`，`needs_dependency` 是正确语义）。
  impl 边 88 → 105，无向边 51197 → 51214。
- **路径匹配只认主件**：`tools/control_loop.py` 会同时匹配
  `state/atomic-sync/backup/…/tools/control_loop.py`，连到备份副本等于「改主件时监控不提示」——
  看着接上了，其实接错了。已按「主件优先、备份/镜像/归档靠后 + 同层取短路径」排序并只取首个命中。
- **三个位 desc 去数字**：`comfy_forge`（现读 1495 把 · 原写 962）· `comfy_native`
  （契约面 1495 把 / 809 / 359 / 290 / 19）· `bits_kit`（★49005 · 216 组件 · 五类分布）——
  一律改指 `op=evidence` / `op=contract` / `op=build` 现查。**「常用说法」段一个字节没动**
  （那是路由触发词来源，动了会掉命中）。快照已重导。
- **补上 `docs/capabilities/system.md` 的生成器**：`tools/codex-scripts/sync-capabilities-doc.py`
  （`--check` 报告 / `--apply` 写回；原子替换 + 锚点数量守恒校验）。它只同步
  「`- **它做什么**：` 与下一个 `- **`」之间的正文 —— 元数据行与 `- **怎么调**` 之后一律不碰。
  首次运行就揪出 **3 个此前无人知道的漂移**（`cap_self` / `console_hub` / `mirror_stage`），
  同步后 54 段全一致。这份文档此前是全仓唯一「改了注册表也不会提醒你」的面。
- **多域监控全档跑通 + `risky` 榜去噪**（同日三次）：
  - 全档读数：`status` **6306 节点 / 102428 有向边 / 21291 强边 / 分量 1 / 100%**；
    `risky(n=50)` · `where` · `impact(depth=3)`（打 `api.py` 得 5039 影响面）。
  - **万能插全开**（**没有 `op=all`**；正名是 `surface_audit` + `discover` **两件**，
    `full_sweep` / `surface` / `万能面` / `全量` 都是 `surface_audit` 的**别名**，
    实现同一套，返回 `"op": "surface_audit"` 是**归一化到规范名**、不是静默兜底
    —— 兜底指落到 default 分支且没有 alias 表，这里是显式 alias 表，性质不同。
    AGENTS.md 把别名和正名并称"三件"，属精度问题，已记在此）：
    `surface_audit` 17 面 / 可驱动 16 / 缺口 1（`%%%` 是测试残留）；
    源码分支与声明表 **两栏都空** ⇒ 执行器真值表未漂移。`discover`：进程 93 · 监听端口 22。
  - **`risky` 榜去噪**：口径收紧到"按强边排"后，榜首正确变成 `api.py`（强边 930），
    但 Top15 里紧跟着 **8 个是历史副本**（`state/mirror/stage/…/security/policy.py`、
    `state/atomic-sync/backup/…/api.py`、`.archive/panels-…/brain/*.js`）——
    改主件时监控同时报一堆副本，**噪音盖过信号**，「最危险」变成「最吵」。
    现加 `_is_copy()` 判定，`top` 只放本体、副本单列 `copies`：
    **本体 2857 / 副本 470**，Top10 全是真代码（api.py 930 · security/policy.py 286 ·
    caps_registry.py 215 · …）。
- 三条闸全过（`guard-three.py`：万能插 / 多域监控 / 原子替换 / 探测超时 / 运行时），
  多域监控已读到新图 **6306 节点**。

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
- **文档索引对齐**：`docs/legacy/README.md` 的 348 → 354（现读）、`能力总表.md` 死链换成 `03-capabilities.md` + `capabilities/`，
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
- **GitHub 全量清扫（docs/88）**：以本地真身为唯一真相，用便携 git 一次推送（fc8742c + 3851410）：旧内容 470 → 0，缺件 1503 → 0，旧件 3 → 0，产物目录 交付成片/ 移出并加 .gitignore；README 换新版（Caps 375）。
- **方案A 历史重写（docs/89）**：便携 git+filter-repo 从 362 个提交历史里剔除 state/store/dist/runtime/logs/vaults/vendor/outputs/交付成片/C:\ 目录 → 351 提交、.git 193.1→177.2MB、HEAD 2752 文件不变；强推后远程 HEAD=d57a406。GitHub 体积是异步统计，旧对象待其 GC 释放。
- **仓库装修（README/CI/模板/能力介绍）**：README 换专业版（社交预览图/徽章/TOC/架构 SVG/demo GIF/图集/实测读数表）；新增 CI（ubuntu+windows × py3.10/3.12）、Issue 表单、PR 模板、行为准则；新增 docs/90 能力介绍（30 域 375 位，从注册表实时生成）。
- **可视化页面总览（docs/91）**：28 个静态面板逐一说明（一屏一问）+ 落地页/启动页/控制台 + docs/gallery 图集 + 三种打开方式；README 增「可视化页面」区块。
- **吞噬 superpowers-zh（docs/92，第 376 位 skills_hub）**：吸收 20 个方法论 skill（brainstorming/TDD/systematic-debugging 等，MIT 保留归属）到 skills/superpowers/；新增能力位 skills_hub（list/get/match/verify），中文 bigram 打分；判据 tests/test_skills_hub.py 8 条全绿。缺口结论：能力位是手，skill 是做法。
- **翻完 GBT-Framework v5 + 吞执行纪律（docs/93，第 377 位 chain_kernel）**：897 文件/32 文档/192 cap 全量归档到 data/absorbed-v5.json；把 V5 的 UNIFIED_PATH/pipeline/gates 落成七步不可跳步链（-1..5，每步证据+准入准出，默认只读面，失败 stopped_at）；判据 tests/test_chain_kernel.py 10 条全绿。
- **蒸馏不搬运（docs/94）**：① 熔断器只取状态机嵌进 energy_core（3 失败/60s→open 30s→half_open，think 秒回 circuit_open，不再白等 300s）；② root_cause 只取「假设+证据+案卷」并换成我们的 7 项检查（第 378 位，判据 9 条）；③ 拒收 skill_library/quad_brain/量子隐喻/攻击工具/input_sanitizer(暂缓) 等，理由成文。
- **第二轮蒸馏（docs/94 第五节）**：从 GBT-JXDWD 只取两道防线 —— ① `execution_guard`（第379位，四类「自己骗自己」：完成无证据/连续写无验证/折叠当完整/原地打转，照账本审，接进 chain_kernel 第3步）；② `proc_guard`（超时杀整棵进程树 taskkill /T /F、输出封顶、环境净化，已接身体桥）。判据 19 条全绿；payment/projects/旧备份一律拒收。
- **第三轮蒸馏（docs/95）**：从 GBT-JXDWD 的 `capability_protocol.py` 只取「清单发现 + 动态装载」，落成第 380 位 `cap_pack`（packs/*/capability.json；auto_exec 默认 false 只登记；执行须 auto_exec+process_execute 票；子进程走 proc_guard）；示例包 2 个 + 判据 10 条。`pipeline_gate.md` 与 `chain_kernel` 重复 ⇒ 拒收。
- **第四轮蒸馏（docs/96）**：① MCP 注册表（mcp_register/servers/unregister/health）—— 读标准 mcpServers 配置进 state/mcp-servers.json，体检真起子进程；闭环判据 12 条全绿（登记→列表→体检→连上→调工具→注销）。② 双脑确认 dual_gate（第385位）—— 推理脑（作用域/金额上限/收款人/force×dry_run）+ 编程脑（能力位/必填参数/落点存在），已接进 chain_kernel 派工前，任否决不派工；判据 12 条。orchestrator/decision_pipeline/旧备份拒收。
- **本机指挥官大模型接入（docs/97）**：llama-server@127.0.0.1:8792 起（5.24GB q5_0，ctx4096，4 slots，纯 CPU）；energy_core.think / commander.ask / commander.route 三条路径实测通过；顺手修掉 trunk_reason 抓到的 P0 假绿（4 个 MCP 能力位 handler 不在分派表 → 改成各自 kind），score 91.7→100；新增 tools/engine-on.cmd / engine-off.cmd。
- **能力位计数收口（docs/98）**：根因 = 文档里的数字是手写快照，能力位一直在加（341/348/368/375）。现在唯一真源 = 注册表现读（**385 位**，只读 300 / 需授权 85）；新增 `doc_counts` 齿轮 + `tools/sync-cap-counts.py --check/--apply` + `cap_self op=docs` + 判据 `tests/test_doc_counts.py`；文档 8 处现读数全部对齐，历史口径（341 快照/348 当时）原样保留。
- **吞噬 Agent Skills 规范（docs/99，skills_hub 强化）**：吸收 agentskills.io 规范的校验/打包/安装/渐进读取 —— `op=validate`（name 规则、描述 1..1024、目录同名、可选字段上限）、`op=pack`（<name>/SKILL.md zip）、`op=install`（claude/codex/agents 目录，默认 dry_run，真装过 filesystem_write 门）、`op=read`（只读 skill 内文件，防穿越）；判据 tests/test_skills_spec.py 15 条全绿。拒收 skills-ref 库 / marketplace 插件清单 / 客户端提示词 / GSAP 领域内容。
- **GSAP 蒸馏成技能（docs/100）**：把 greensock/gsap-skills 的 8 个官方技能蒸馏为我们的 1 个 `skills/gsap/`（核心 tween/timeline/ScrollTrigger/React/插件/性能/5 坑 + references 地图）；skills_hub validate → 23 个全合规（clean），match("给面板加滚动动画")→gsap 3.2 第一，pack 出 zip，read references 可读。
- **面板动效落地（docs/101）**：内置 gsap.min.js（72KB，离线）+ panel-anim.js（只动 transform/opacity、respect reduced-motion、失败标 failed、同步 started/count/done 标记）；panel/capabilities/welcome 三页接线；headless 截图对比 t≈250ms vs 3000ms：panel 5.75%、capabilities 15.81% 像素变化；判据 test_panel_anim.py 11 条。
- **认知界面（docs/102）**：① 28+ 旧面板全拆（29 目录归档 `.archive/panels-20261101/`，71.91MB；windows.json 20→2 窗、nav 2 项、w3/index 跳转、根 index 3 处链接改指）；② 按 成熟三栏骨架 1:1 做 `holo_pet_w3/console/`（左身份/守卫流、中对话、右心跳/行动日志/守卫能力、背景能力域图谱）；③ 土豆 Logo 重新生成（GBT/小土豆V8/385 caps，icon-512/192/apple-touch/favicon）；④ `tools/console-server.py`：/api/data 现读 + /api/chat 走 energy_core.think(context=console-web) 无限上下文、temperature=0 稳定输出；判据 tests/test_console.py 17 条全绿。
- **品牌标识改为她的开源头像（docs/102 §三）**：从 GitHub 用户 gbtweilai-star（GBT小土豆）头像取图，存 icons/avatar.png(512)/avatar-96；控制台左栏 brand-mark 改圆形头像、favicon 用头像；icon-512/192/apple-touch/favicon-32 全部改由头像生成（tools/gen-potato-logo.py）；作废我先前自造的「GBT/小土豆V8/385 caps」文字图标。
- **认知界面改成真 1:1（docs/102 §二）**：第一版只是"像"，主人指出不对劲；这版逐项照抄上游参考项目的 CSS 令牌与布局——--bg0/--panel/--console-bg/--warm/--cool/--line-strong/--shadow-* 同名同值，--side-panel-width clamp(260px,25vw,362px)、中栏 left/right = side+40px、.panel fixed top20/bottom20、#panel-l2 透明 rail + 模块自带卡面、心跳图 92px、行动日志 clamp 高度、Inter+JetBrains Mono；图谱默认关（同原设计），点按钮才开；差异：内容换成我们数据、无语音球/热点等空壳、署名放左栏底部。
- **控制台四视图 + 3D 触手星图（docs/103）**：中栏加页签 对话/功能表/技能栏/3D 星图/仪表盘；功能表 385 位可搜可筛（域/门/说明），技能栏 23 张卡，仪表盘域分布+门环形+守卫/引擎+流水；3D 用 Three.js 照主人参考图重做：30 域核 + 385 能力位 + **15,400 根视觉触手**（385×40，示意密度）+ 域弦 + 2000 点外圈 + 3000 星尘，标记 data-space3d=ok:385+30+15400；修 console-server `/` 未重定向导致相对路径 404 的真 bug。
- **3D Bloom + 真实调用点亮（docs/104）**：内置 three 后处理（EffectComposer/RenderPass/ShaderPass/MaskPass/UnrealBloomPass/Pass + 两个 shader），3D 星图加辉光（strength .75/radius .65/threshold .55）；`gen-console-data.py` 读 audit.jsonl 最近 800 条聚合 pulse，3D 把**真实调用过的能力位**触手用暖金呼吸层点亮；标记 data-space3d=ok:385+30+15400+4（能力位/域/视觉触手/点亮数）。\n- **实时触手 SSE（docs/105）**：console-server 新增 `/api/events`（SSE，1.2s 轮询 audit.jsonl，从 EOF 开始不重放）；3D 星图用 EventSource 接收 → 对应能力位触手暖金点亮 6s 淡出，`data-space3d` 的点亮数实时变；实测：连上后调用 inventory，audit 增长 492 字节，SSE 立刻收到 {cap:inventory, verdict:clean}。\n- **鼠标转动她 + 中心头像（docs/106）**：OrbitControls 改绑整个 `.space3d-wrap`（整块可拖，rotateSpeed .75/滚轮缩放/禁用平移，grab 光标），中心放她的头像球（深底圆盘去白底，慢速自转）；`?selftest=1` 程序化拖拽自检 data-space3d-drag=ok:14.491；顺带修真 bug：http 打开时 /icons/avatar.png 404（静态根不含 icons/），已给 console-server 加 /icons/ 白名单路由。\n- **大脑执行层可视化（docs/107）**：按主人视频新增第 6 个视图「大脑执行层」——中心脑核（她的头像）+ 7 条对称闭环管道（映射 chain_kernel 七步 -1→5）+ 臂上橙色证据节点 + 末端同心审计环 + Bloom；整块可拖/滚轮缩放；标记 data-brain3d=ok:7臂+审计环，截图 assets/panels/console-brain.webp。\n- **万能插可视化（docs/108）**：按主人第二段视频新增第 7 视图「万能插」——数字覆盖的三叶结管道（数字纹理沿 U 滚动代表数据流动）+ 8 个能力域插口（同心环座/发光内面）+ 自动插合触手（尖端沿路径脉冲）+ 中心调度核 + Bloom；整块可拖/滚轮缩放；标记 data-plug3d=ok:8插口+数字结，截图 assets/panels/console-plug.webp。\n- **原生 APP 自启认知界面服务（docs/109）**：Electron 壳 `shell/console-service.cjs`（main.cjs 建窗前 ensureConsoleServer，pyembed detached 起 + 12s 等接管 + 失败不牵连）、Python 桌面壳 `gbt_allinone/console_service.py`（app.main 先 ensure_server）、`启动-GBT.cmd` 新增 [2/4] 确保 :8766；另给登录自启包装器 `tools/autostart/GBT-console.cmd` + 一键 `设置开机自启.cmd`；实测：停服后 ensure_server 981ms 拉起 pid 3028 caps 385，二次调用 already:true（幂等）；tests/test_console_service.py ALL OK。\n- **触手协作 + 思维导图任务指引（docs/110）**：新增第 8/9 视图——「触手协作」中心共享任务+8 协作角色（感知/规划/执行/验证/审计/固化/报告/协同）+16 条协作链+流动消息点+共享账本同心环，标记 ok:8臂+16协作链；「思维导图」任务指引中心+6 分支×3 叶共 18 条真实流程动作（读架构/七步链/run_task/真跑读数字/ledger/docs/CHANGELOG/给数字），标记 ok:6支+18叶。\n- **触手协作脉冲特效（docs/111）**：真实事件到达时角色尖端炸出扩散冲击波环（Sprite 环 1.2→10.2 淡出）+ 消息点拖尾飞向中心 + 共享任务核闪光 + 角色触手亮 6s；事件→角色为真实映射（守卫类→审计，run/denied→执行/协同，report→报告，recon→感知）；标记 data-team3d=ok:8臂+16协作链+脉冲N；实测 selftest 脉冲2、pulse=1 脉冲16（上限回收）。\n- **穿透式交叉扫描（docs/112）**：新增第 10 视图「穿透扫描」——385 个真实能力位做节点（绿=只读 300 / 红=需授权疑点 85）、交叉边成网、扫描线自上而下；遇疑点：大脑反思（红环）+ 手穿透（纵深束）+ 扫描放慢 0.8s，一轮扫完嘴巴报结论，每轮开始眼睛看；五感面板明写「眼睛=视觉全谱·不止 OCR」并列出 11 个真实视觉能力位（vision_loop/vision/vision_grounding/vision_print/body_see/gods_eye/screen_sniff/video_intel/image_scout/zimage_rewash/chart_html）；标记 data-scan3d=ok:385节点+85疑点 + 每项计数器可巡检。\n- **穿透扫描接真实结果（docs/113）**：`penetrating_cross_scan._report()` 新增 per-unit `unit_details`（agree/arbitrated/unhooked 原样带出）；新增 `tools/export-scan-data.py` 跑 bindings(1913)/registry(1)/tree:gbt_allinone(943) 写 state/scan-data.json；gen-console-data 并入 scan；scan3d 节点=真实 unit（绿=agree/琥珀=arbitrated/红=unhooked）、HUD 可切目标；实测 bindings ok:1913单元+0疑点，registry 切过去 ok:1单元+1疑点（amber=1）。\n- **无死角扫描（docs/114）**：扫描器补 `full_coverage` / `dead_spots` / `dead_spot_count`，补扫轮次 2→3；HUD 加覆盖/死角实时字段 + 漏扫计数（每帧写 data-scan3d-missed）；三者归零且覆盖 100% 才显示「无死角」；新增「现场重扫」按钮（真调 GET /api/scan，白名单 bindings/registry/tree:<dir>），coverage<1 自动补扫最多 3 轮；实测三目标 coverage=1.0 full=True；页面 ?rescan=1 → rescan ok:1913单元:10ms:补扫1轮:覆盖1。
- **无死角自检抓出 70 个死角并修掉**：页面快扫复核发现扫描线只走到 ±9.4 而节点 y 到 ±10，上下边缘 70 个节点永远扫不到；边界改 ±10.6 后 data-scan3d-remaining/missed 均为 0、coverage=100、dead=0。\n- **触手职业表（docs/115）**：新增 `tools/gen-professions.py` 从 caps_registry 现读生成 `data/professions.json`（12 职业：编程/审查/测试/安全/运维/架构/数据/视觉/媒体/研究/文档/指挥），编程工程师为首席（47 能力位，工具=终端/编辑器/git/run_task 真跑/五处落位，KPI=改完即测·旧物清零·签名不丢）；认知界面新增第 11 视图「职业」（#prof，12 张真实卡 + CHIEF 徽标），标记 data-prof=ok:12职业+编程首席。
- **职业表扩到 18 种（补媒体职业）**：短视频编导(79 位)、音乐制作(10)、影视/电影(22)、数字人/直播(76)、设计/美术(59)、游戏/3D(70)——都由 caps_registry 现读映射；职业合计 971（跨域重复）。\n- **全方位职业覆盖（docs/115）**：职业 18→21（补集成/连接、命令行/入口、生活/陪伴）；gen-professions 加覆盖率审计（orphans/uncovered_domains）+ flex 补位机制；实测 385/385 能力位、30/30 域、孤儿 0；职业视图标题/副标题直显覆盖率。\n- **职业路由（docs/116）**：新增 gbt_allinone/profession_router.py（关键词+标题/域/能力位/KPI 打分，代码动词+20 优先编程工程师，safe/gated 候选分栏，无命中走协同兜底）；POST /api/route 接口；职业视图加路由条（#prof）；实测 5 例全中（短视频/音乐/编程/数字人/影视），接口 ok 候选 8 需授权 8。\n- **派单闭环（docs/117）**：新增 gbt_allinone/profession_dispatch.py（只跑 safe 候选、默认 dry_run、confirm 才执行、逐条结果 + orchestration-ledger 留痕、无 safe 候如实拒绝）；POST /api/dispatch；职业视图加「派单（安全候选）」按钮；实测 asset_vault_freeze 真跑 ✓。\n- **落地清零 3 个历史失败**：重建 holo_pet_w3 落地首页（h1 + 4 张真图 + 入口 + 签名，修 experience 两条）；rules.json 女声口径改 local 并重生成测试；test_voice_defaults 口径同步（2026-11-01 本地优先决定）；全量 30 个测试文件全绿。\n- **方向转向：赏金工作台（docs/118）**：新增 gbt_allinone/bounty.py（授权闸：无 authorization_ref 拒建项；范围闸：scope/out_of_scope + IP/CIDR；范围外发现拒录；报告带证据 sha256；赔付只记账）+ POST /api/bounty + #bounty 视图（项目/范围检查/发现/报告）；实测 own-lab 范围内允许、example.com 拒绝、报告 sha256 一致；tests/test_bounty.py ALL OK。\n- **自训靶场端到端（docs/119）**：新增 tools/lab/vuln_lab.py（本机 127.0.0.1 自建靶场，故意 6 类问题：XSS/IDOR/穿越/调试泄漏/未授权管理/缺头）、lab_scan.py（只读扫描）、run_lab.py（靶场→扫描→授权闸→录单→报告→账本）；实测发现 6/录单 6/报告 6，外部域被拒；tests/test_lab.py ALL OK。
- **诊断位口径写坏又修好（2026-11-05）**：改 `impact_check` 的「两种口径」时，新句子和旧文本残片被拼在一起 —— `逐字对齐"` 提前闭合字符串、`"强边"` 这个 key 直接丢了，整个能力位变成 `SyntaxError` 起不来。修复：坏块 7 行重写（补回 `强边`）+ 230 行注释补齐 v4 口径（原文还停在「只算 path + cap + 绑定账」，没提 import/impl）；顺手更正蓝图本节读数三项（51197 无向边 / 21256 强边 / 400+ → 102428 / 21291 / 67）。新增 `tests/test_diag_kou_jing.py` 6 条**静态**机检：`ast.parse` 能过 · 三键齐 · 4 位以上数字须对得上图或属历史白名单 {67} · 文本指向的 `op=status.strong_edges` 必须真存在 · `risky.caveat` 与 `impact.强边` 都必须含 import/impl/分派 · 不许有重复粘贴的残片。**这 6 条用 5 个 mutant 验过（内存改写源码、不落盘），5/5 全部抓到。** 教训：`grep` 结果经 JSON 转义（`"` 显示成 `\"`），引号结构错在屏幕上和正确的看不出区别 —— 这类文本必须过 `ast.parse`。
- **risky 榜分流派生物（2026-11-05）**：`state/console-data.js` 强边 777 排第 2，可它是 `tools/gen-console-data.py` 的产物（文件头「自动生成，勿手改」）——照榜去「修最危险的件」改的就是它，白改。新增 `_is_derived()`：判据用**文件头标记**而不是路径白名单（路径会变、标记不会），先过路径/扩展名两道闸 —— 全图 2900 个 `code:` 节点只有 2 个候选，读盘代价约等于零。派生物与「副本」**分开单列**成 `derived`，因为跟进动作不同：副本是快照要跟、派生物是产物要重跑生成器。分流后 `top` 第 2 从 **777 降到 286**（`policy.py`），榜单量级干净一个数量级。判据 `tests/test_impact_ranking.py` 6 条，并用 monkeypatch mutant（`_is_derived→False`）验证 C 条会红。**另：`must_verify_1hop` 经取证确认不该改** —— 消费方 `tools/codex-scripts/impact.py:121` 打印的就是「改完必须逐一验证」，副本是要验的实体；理由已写进代码注释，免得下一个人再纠结一遍。
- **孤儿位结案：只有 1 个真孤儿，已补上（2026-11-05）**：此前按 `handler` 名找同名文件，得出「8 个孤儿位」，**方法本身是错的**。取证结果：`hook_enforcer` / `omission_detector` 的实现是 `tools/penetrating_cross_scan.py`（`api.py:1421` 三个 kind 共用同一引擎），两者**早就在强边里**，从来不是孤儿；真正断线的只有 `review_gate` —— 它把路径**先存进变量**（`api.py:2705` `_rg_path = Path(...) / "tools" / "codex-scripts" / "terminal-review.py"`）再传给 loader，而 impl 层只从**调用参数**里抽路径，拿到 `ast.Name` 抽不出东西 ⇒ 0 条边。给 `wiring-build` 补第 ④ 种形态（`ast.Assign` 右值是 Path 拼接且以 `.py` 结尾），并把重复的路径连接逻辑抽成 `_link_path`（只认主件、不连备份副本）。重建后 **impl 105→106 · 强边 21291→21292**，精确 +1 无连带副作用；`review_gate` 强边 22→23 并含 `terminal-review.py`。判据 `test_wiring_v4_guard.py` 增至 8 条（新增 `test_review_gate_reaches_terminal_review`）。`quant` 系列 5 位仍走 `quant_tech` 外部业务模块，`needs_dependency` 是正确语义。
- **system.md 从 54/427 补到 427/427（2026-11-05）**：`sync-capabilities-doc.py` 新增 `--fill` —— 为没有精修详情段的 373 位生成**一行一位的「全量速览」**表格，插在文末 `---` 之前；54 个精修段原样保留、一个字节不动。**没有**给它们补完整详情段：373 × 约 1.5 KB ≈ 560 KB 会肿成没人读的大字典，而且这 373 位本来没有手工精修的「要哪张票 / 必填载荷」，自动编只会编出「无必填」套话。实测 82 KB → 260 KB，**幂等**（连跑两次 147920 → 147920 字符不变），**锚点守恒**（`### \`` 数量 54→54 不变，写入前校验，变了就拒写）。完整参数与权限仍走 `op=contract` 或 `docs/capabilities-full.json`（机器可读版）。顺带纠正：该脚本**没有 `--check` 参数**（不带参数即干跑），此前文档口径有误。
- **服务全没开：查出三层原因，修掉一层（2026-11-05）**：实测 8791/8766/8111/11434/1234/8080/8793/31720 **全部 closed**。逐层查：① `启动-GBT.cmd` 依赖 `py -3.14`、`C:\Python312\python.exe`、`electron.cmd` —— 本机**三个都没有**，脚本是写给另一个环境的（`py` 命令直接 not found）；② `tools/model-bridge/server.py:49` 硬 `import lane_guard`，而全仓（含所有备份/归档）**0 命中** —— 那是 2026-10-29 抽出来解决「回环代理 502 误判」的独立模块，文件丢了。`py_compile` **查不出**（语法没错，是运行期 ImportError），后果是 8791 起不来、启动链断在第一环；③ 同目录 `serving_policy.py` 也丢了（L642，在 `try:` 块内 ⇒ 可选，缺了降级不崩）。处置：按 `server.py` 的四个调用点（`open_url` / `classify_exc` / `kind_text` / `precheck_fit`）**重建 `lane_guard.py`**，实现它原注释交代的三件职责（回环强制直连 · 502 分档 · 发之前用 `/tokenize` 判上下文装不装得下）。然后用 pyembed 直起服务、绕开坏脚本：**8791 bridge `/health` 200 ✅ · 8766 认知界面 `/api/state` 200（页面 49036 字节）✅**。**8111 引擎没起**：`commander.status()` 的 gate 明写 `op=start/stop ⇒ process_execute`，需主人发票，agent 不自批。判据 `tests/test_model_bridge_imports.py` 3 条 —— 不写死「lane_guard 在不在」，而是**通用规则**：server.py 依赖的每个**必需**本地模块都必须能解析（`try:` 内算可选，避免把 `psutil` 这类判成缺失而误报）。
- **补回两件「发现了却留着」的（2026-11-05）**：落地核对 15/19，差的 4 项里有 2 项是我查到病灶却没修，已补：① **`serving_policy.py` 重建** —— `server.py:642` 与 `local_llm_server.py:170` 都 import 它，全仓 0 命中。两个引用方的注释写明它是「档位声明 + 粗粒度拦截 + 可解释拒绝 + 审计，**不是安全保证**」，默认档 `uncensored`。文件一丢，`server.py:633` 说的「补在唯一出口、覆盖 selfhost/selfhost_gpu/云车道全部」那个补丁就等于没打过 —— **开关在、闸门不在**。重建 `Policy.load()/.mode/.check(text)` + `--set-mode` CLI，内置规则**刻意只放无歧义的违法类**（编大词表既误伤又营造假安全感），状态原子写到 `state/serving-policy.json`。② **`启动-GBT.cmd` 修三处环境不符** —— `py -3.14` → `%~dp0pyembed\python.exe`、`C:\Python312\python.exe` → 同样 pyembed、electron 缺失时**明确跳过并给装法**（原来直接 `start` 一个不存在的文件，静默失败）；另加注记：`8792` 是 bridge 里的**车道名**，引擎真身在 `weights.py`（当前 8111）。落地核对 **15/19 → 17/19**。剩 2 项需主人：8111 引擎（`process_execute` 票）·Electron 桌面壳（`holo_pet_w3` 缺 `node_modules`，要 `npm install`）。判据 `tests/test_model_bridge_imports.py` 增至 4 条（新增策略门：默认放行 / filter-lite 拦明显违规 /拒绝必须给 hits / 不许误伤正常话）。
- **万能插 / 多域监控全量跑，抓出四个真 bug（2026-11-05）**：先把 op 清单用 AST 从源码数出来（`omni_plug` 实认 42 个、`impact_check` OPS 5 个），再全跑。四项都是实测铁证：① **`known` 自述漏 5 个 op**（`page_route`/`page_stats`/`disk_find`/`disk_stats`/`任意`）—— L1666 注释自己承认过同一问题，后又漏了一次，照自述调用的人摸不到入口；② **`impact_check` 的 `risky` 原来是兜底 `return`** ⇒ OPS 以后新增 op 忘写分支会**静默变成 risky**，返回值看着正常、口径全错；改成显式分支 + 未知 op 如实报 `op_in_OPS_but_no_branch`；③ **`omni_adapter.classify` 把盘上真实存在的 `AGENTS.md` 判成 `https://AGENTS.md`** ⇒ policy 挂 `external_llm`+`data_export`，回执写「把当前任务数据发送到外部大模型服务」——**读一个本地文件被当成外发**。根因：只在含 `/` 时查存在性，且 `exists()` 假时**不 return** 直接穿到「裸域名 ⇒ https」；修两条（盘上存在就算 path；带分隔符一律 path，不存在如实说不存在），并补 `"://" not in t` 防止把 `http://` 也吃掉（改完 12 个用例全对）；④ **`tools/page_lazy.py` 顶层 `import resource`** —— Unix-only，Windows 上整份 import 不了，连带 `op=page_stats` 直接 ModuleNotFoundError（api 层只包成 `status=error`，看着像「op 不支持」）。另建全盘索引：**1,227,540 文件 / 124,855 目录 / 107 秒 / 15.2 MB**，`disk_stats`/`disk_find` 转绿。判据新增 `tests/test_omni_truth.py` 6 条（自述==实际 / OPS 都有分支 / classify 12 用例 / page_lazy 可 import）。测试总数 30，全绿。
- **补回「判据本身不存在」（2026-11-05）**：`omni_plug.py:1668` 与 `caps_registry.py:1615` 都写着「判据在 `tools/codex-scripts/omni-monitor.py --gap`（AST 三向对账）」——实测那个文件**不存在**，`gbt_allinone/omni_monitor.py` 也没有 `--gap`/`main()`/argparse（它只是监控采样模块）。**「判据在 X」这句话本身没有判据**，而「自述漏 5 个 op」那类事正是在「以为有人看着、其实没人看着」的状态下发生的。补写 `tools/codex-scripts/omni-monitor.py`：`--gap` 做**三向对账** —— ① `_dispatch` 实际分支 **42** / ② `known` 自述 **42** / ③ `desc` 里 `op=…` 声明 **13**，任一方向有差集则 exit 1（支持 `op=a/b/c` 斜杠列举）。实测三向一致。判据 `test_omni_truth.py` 增至 7 条（新增「被判据点名的工具必须存在且跑得通」），总数 **31 全绿**。另：扫「427 个位的 desc 提到的 op 是否都实现了」时发现**方法不适用** —— 只有 4 个位的分支体能抽到 `op ==` 字面量，其余 op 分派在各自实现模块里，不能据此报「0 个 bug」（这是方法失效，不是结论）。
