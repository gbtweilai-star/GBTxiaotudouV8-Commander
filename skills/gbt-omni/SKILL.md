---
name: gbt-omni
displayName: GBT 万能插 · 人类视角操控一切
version: 1.0.0
description: GBT小土豆V8 的「人类视角操控一切」协议。它把全机职业技能（**能力位/技能/域/审美素材的条数一律现算，见 `omni caliber` —— 不写死，写死一次过期一次**）收进一张现扫图鉴，并把「人一句自然语言 → 落到哪个能力位或哪个技能 → 该跑哪条命令 → 要过哪道门」这条链定死。默认拒绝安全纪律：只自动跑能证明是只读无参的，其余一律只给命令并说明要过的授权门，绝不绕门。当用户说「让框架去做某件事」「操控一切」「人类视角」「万能插」「帮我跑一下」「怎么让它干这个」，或想知道某个职业域有哪些能力可以调时使用。
triggers:
  - "万能插"
  - "操控一切"
  - "人类视角"
  - "让框架去做"
  - "帮我跑一下"
  - "能力位"
  - "职业域"
  - "有哪些能力"
  - "怎么调"
  - "omnipulg"
  - "omni"
  - "自主执行"
  # ── 反模式触发词（2026-09-23 补，源自外部设计对照）──
  # 为什么要把"**症状**"也做成触发词：用户不会说"我要用万能插"，
  # 他会说"**怎么点下去没反应**""**报得出名字但跑不了**""**门说拒了报表却说未知**"。
  # 这些症状正是本协议存在的理由 —— 触发表里没有它们，人就得先学会我们的行话才找得到路。
  - "假绿"
  - "报得出名字"
  - "点下去没反应"
  - "门说拒了"
  - "怎么调不动"
  - "落在哪个能力位"
  - "不许绕门"
---

# GBT 万能插 · 人类视角操控一切

> **Status**: 在用（本会话实测可达）· **Last Updated**: 2026-09-23
> 规模数字（能力位/技能/域）**一律现算**：`py -3.14 tools/codex-scripts/omni.py caliber` —— 本文不抄。
>
> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> Owner 定调：「把框架里面的所有职业技能深度学习到精通，蒸馏提炼成**使用万能插就可以人类视角操控一切**」。

**一句话**：人只说"我要什么"，**落点、命令、要过的门**由这条协议定 —— 而不是让人去记**上百个能力位的名字**（到底几位：`omni caliber`）。

---

## 0. 先分清五类通道（"怎么调它"）

全机的职业技能**不是一个东西**，五种通道，混了就调不动：

| 通道 | 是什么 | 怎么调 | 数量（**现算，不手抄**） |
|---|---|---|---|
| **`omnipulg`（万能插）** | 框架自己的能力位，**唯一门 `run_task`** | `py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['{...}']` | **条数一律现算**（`omni caliber` 的 A/B/C 行 + `omni build` 的图鉴）—— 本表**不写数字**，写一次过期一次 |
| **`local-tool`（本地工具面）** | 本机**真实存在**的扫描器/操作台（**不走 run_task**） | 直接跑真命令（`omni tools` 列出来） | **条数与名单都现算**：`omni list --channel local-tool` |
| **`agent-skill`** | 装了就能用的职业技能（arkcli / lark / 审美 / 我们自己的…） | 由我按**技能名**加载执行（`skill <名>`） | 图鉴去重后若干条 —— **但只有本会话真读的两个根里的才加载得动** |
| **外部 CLI** | `arkcli` / `lark-cli` 这类有自己门与账单的 | 按各自协议调（Ark 要带全前缀 + 过登录闸/账号验证闸） | 见各自技能 |
| **`design-asset`（料，不是能力）** | 品牌设计系统 / 设计骨架 / craft 规则书 | **被引用**，不是被"调用" | 93 条技能 + **234 个目录**（设计系统 150 / 骨架 84） |

> 🔴 **为什么现在多了 `local-tool` 这一通道**（2026-09-23 实测，这是"无死角"漏的那一格）：
> 原先只有「能力位 + agent 技能」两通道，而**本机的扫描能力其实在命令行工具里**。于是：
> `omni ask "扫一下这台电脑有没有病毒木马后门"` → `selfscan`/`cross_scan`/`gbt-security`
> （前两个与病毒无关；`gbt-security` 本会话加载不了；`sec_scan` 无参挂死 180 s）；
> `omni ask "全维度无死角扫描"` → `osint_scan`/`bluetooth`/`bt_control`（全打偏）。
> **真正的扫描器 `quick_scan.py` 不在任何通道里** ⇒ "扫"这类意图必然落空。
> 补上这一通道后的实测：「扫病毒木马」→ `quick_scan`(**4.2**) 第一；
> 「全维度无死角扫描」→ `quick_scan`(**8.4**) 第一。

**判据**：想让**框架本体**干活 → 万能插；想让**本机的扫描器/操作台**干活 → 本地工具面；
想让**装了的手艺**干活 → agent 技能；要**花钱/出网/部署** → 外部 CLI，先过它的门。

---

## 1. 人类视角入口：`omni`

```bash
python tools/codex-scripts/omni.py build              # 现扫全机，落 state/skill_atlas.json
python tools/codex-scripts/omni.py ask  "人类一句话"     # 三通道并列给候选 + **落点可达性**
python tools/codex-scripts/omni.py run  "人类一句话" [--yes]   # 经万能插真跑
python tools/codex-scripts/omni.py list [--domain 域] [--channel 通道]
python tools/codex-scripts/omni.py tools               # 本地工具面清单（含真命令与门）
python tools/codex-scripts/omni.py caliber             # 口径对账：「可直跑」到底几条
```

**通道取值**：`omnipulg`（能力位）· `local-tool`（本地工具面）· `agent-skill` · `design-asset`。

### 1.1 🔴 三条"不许省"的纪律（2026-09-23 补，都是拿实测坑换的）

| # | 纪律 | 为什么 |
|---|---|---|
| **R-A** | **落点必须报可达性** | 路由通了 ≠ 能用。实测 `gbt-system`(12.0) / `gbt-security`(4.8) 都被当首选推给人，而**本会话 `skill <名>` 报 unknown** —— 技能目录是**会话启动时快照**的，本会话只读得到 `<仓>/.dsh/skills` ∪ `~/.agents/skills`。现在 `ask` 对每条技能标 `✅ 本会话可加载` / `🔴 本会话加载不了` |
| **R-B** | **数字必须带口径，禁止手抄** | 同一件事曾有三个数：§0 写 122 · §7.1 写 88 · `omni_max` 真跑得 102。`omni caliber` 现算 A→G 七种口径并指定权威 |
| **R-C** | **"扫描"类意图必须落到真扫描器** | 本机扫描能力在命令行工具里，不在能力位里。`ask` 先给**本地工具面**（谁最贴意图谁在前，与通道无关） |
| **R-D** | **域过滤器不许误杀只读扫描器** | 实测 `ghost_guard` / `mirror_scan` / `mirror_status` / `pipeline_status` / `svc_inspect` 都是 `safe=True` + 静态零作用域的**只读扫描器**，却因 `domain=pipeline` 被永久排除在自动探测之外 —— **静默砍覆盖**。现规则：`safe ∧ enabled ∧ 无作用域 ∧ 无参数 ∧ 名字是只读动作` ⇒ **豁免域过滤**；但 `needs_confirmation`、写动作名、`preflight` 会改状态 **照旧一票否决**。想恢复旧行为用 `--strict` |
| **R-E** | **三条主道默认同步，且"谁开的信封"要分开记** | 2026-09-23 Owner 令：大脑执行层 / 万能插 / 五维合一**全部默认同步**。实测先查了三层：五维合一（`five-dim.py cap`）**有**自己的信封；万能插（`omni.py run` 起 `five-dim.py cap` 子进程）**有（间接）**；**大脑执行层没有自己的** —— `engine.py` 是 `from .api import _run_task_core as run_task` 直连内层，面板 `panel_server.capability()` / `python -m gbt_allinone` / 任何直调在账本上一律 `synced: false`。⇒ 落实点收在**唯一那道门** `api._run_task_core`（一进来 `auto_envelope()`：没在信封里就自己开，已在里头原样不动），这样三条主道 + 面板 + CLI + 复合能力**一处生效**，不靠谁记得先 open。⚠️ **语义位移必须一起记**：`synced` 现在只说「**走了唯一那道门**」；**"谁开的信封"在 `synced_entry`**（`auto` 门口默认 / `outer` 外层主动）。只读 `synced` 会把"我把默认打开了"读成"纪律执行得好"。可证伪性仍在：`cap --no-envelope` 会真的记 `synced: false` |

**豁免用名字白名单**（可审计，不装神）：`scan|guard|hygiene|inventory|parity|audit|probe|status|check|verify|inspect|selfscan|truth`。
实测结果：`one_key_deploy` / `mirror_release` / `mirror_ascend` / `mirror_rehearse` / `pipeline_submit` **仍然全 🔒**（默认拒绝没被放宽）。
实测仍被域拦下的 4 条 —— `mirror_plan` · `svc_inspect`（旧）· `feishu_embed` · `cloud_pc`（**不豁免**，宁可保守）。

**它补的是哪一环（先说清，免得重复造）**：

- **万能插本身早就有**（`five-dim.py cap` → `run_task`）✅；
- **语义路由也早就有**（`gbt_allinone/semantic_route.py`，Owner 2026-09-19 定架构：主路=统一大模型，
  没配就**如实降级**到启发式）—— 但它路由到的是**触手方法**（`see`/`click_text`/`find_text`），
  **不是那 158 个能力位，也不是全机技能**；
- ⇒ **`omni` 补的就是「人话 → 能力位/技能」这一环**。

**落点怎么算出来的（要能打开看，不许装神）**：中文**字符 n-gram**（直接复用 `semantic_route.grams`，
不自造第二份）× 三种命中（能力位名 ×3 / 说明 ×1.5 / **域中文提示词** ×1）加权；
禁用的位乘 0.2 排后面但**不隐藏**；拿不准就**给多个候选，由人定**，不猜一个出来。

**为什么非要有"域中文提示词"**：能力位名与说明基本是英文术语（`codex_status`、"官方 Codex 只读状态"），
而人说"看一眼有多少能力位"。不借域提示词，人话根本落不下来。

---

## 1.2 🔴 **默认执行通道**（2026-09-23 Owner 第二次指出后固化）

Owner 原话：「**万能插不是也是默认使用的吗，这么你都不使用来执行任务啊**」。
我第一次只做到"用 `omni ask` 问落点，然后**还是直接跑 `py -3.14 tools/…`**" ——
那等于把它当**查询工具**，没当**执行通道**。**这条写死，别再犯：**

| 想干的事 | **默认**走这条 | 不要直接跑 |
|---|---|---|
| 框架**能力位**（161 条那一类） | `py -3.14 tools/codex-scripts/omni.py run "<人话>"`（内部 → `five-dim.py cap` → 唯一门 `run_task`） | `gbt_allinone` 模块函数 |
| 本机**扫描器/操作台**（`quick_scan` 等） | `omni run "<人话>"`（落到 local-tool 通道，真命令由它给） | 手打一长串参数 |
| 装了的手艺 | `skill <名>` | 猜一个同名脚本 |
| 只想**知道落点** | `omni ask "<人话>"` | — |

### 为什么"走万能插"不是形式主义（一条实测对比）

同一次「读一下本机健康度」，**直接跑**只拿到结果；**走 `omni run`** 多拿到三样：

```
落点：selfscan（system，分 4.0）              ← ① 路由理由（谁选的、为什么）
── 走的哪条路 ──
    sync_exec.run（五维默认路径）｜ 信封=True ｜ 五维判决=partial ｜ 耗时 751ms
                                              ← ② 信封状态（这次调用进不进账本）
    嘴说漏了什么：['eye: 这次没有指定任何观察目标 ⇒ 没看就说没看']
                                              ← ③ **这次没验哪一维**
```

**③ 是直接跑永远拿不到的**：手跑 `quick_scan` 时你不会知道"还有一维没看过"。
⇒ **绕开万能插的代价不是"少一道手续"，是"少一层对自己无知的可见性"。**

### 允许绕过的唯一情形

**万能插本身**坏了或在修它自己（比如本轮我在修它的可达性判据）——
那也是先 `omni ask` 确认它给不出落点，再直接动，并在汇报里写明"这次为什么没走"。

---

## 2. 🔴 默认拒绝（这一节是拿一次实测事故换来的，别改回去）

**事故（2026-09-22）**：`omni run "把这个项目一次性部署到生产"` 落到了 **`mirror_release`**
（镜像全量晋升生产），而第一版的"要不要确认"只查了一张**不完整的侧效应表** ——
`mirror_release` **不在那张表里** ⇒ 它**直接执行了**。

**兜底的是框架自己的授权门**（审计账本原文）：

```
event: "call"        kind: mirror_release
event: "auth_denied" scope: deploy_publish  missing: [deploy_publish, process_execute, filesystem_write]
event: "denied"      reason: "authorization required"
```

生产面没被写。**但"靠下游门兜底"不是设计** —— 上层必须自己先拒绝。

**修后的纪律（硬）**：`run` **默认拒绝**，只有**同时**满足下面全部才自动跑：

1. 注册表里 `status == "enabled"`（2026-09-23 解禁后口径改成这个：旧的 `DISABLED_CAPS` 已清空，
   而"只登记未实现"的 11 条状态是 `unimplemented` —— **同样不许自动跑**，跑了只会拿 `unknown capability`）；
2. 标了 `safe`；
3. **不需要参数**（空调用会被当场拒，等于白跑）；
4. 不在侧效应名单（`PROBE_SKIP_KINDS`）；
5. **域**不在有后果的域：`pipeline` / `dangerous` / `infra` / `integration`；
6. **名字**不带写动作字样：`deploy|release|publish|submit|rollback|rewind|ascend|purge|delete|drop|shape|rehearse|simulate|install|uninstall|write|patch|kill|stop|restart`；
7. **静态查出它不需要任何作用域**（见 §3）。

不满足的：**只打印命令 + 逐条说明为什么不能自动跑 + 要过哪道门**；人明确加 `--yes` 才往下走，
**而且门照样在**（缺授权如实报缺，不许绕）。

---

## 3. 要过哪道门：静态查，不靠跑它才知道

```python
from gbt_allinone.security import policy
d = policy.evaluate(kind, {})        # 只读求值，不执行
scopes = list(getattr(d, "scopes", ()) or ())
```

`omni` 用这条给每个候选标出「要过授权门：`deploy_publish,process_execute,filesystem_write`」——
**人还没跑就知道要什么授权**，不必先撞一次门。

**授权只能主人在终端发**（`python -m gbt_allinone auth grant --scope <scope> --ttl 600`）。
**AI 永远无权给自己发授权**；缺授权就如实报缺，**不找旁路、不改 `security/policy.py`**。

---

## 4. 三十个职业域（"能操控什么"的地图）

现扫读数（2026-09-22）：`system 21 · llm 18 · pipeline 18 · dangerous 11 · tentacle 10 · engine 9 · mind 9 ·
creation 8 · recon 7 · data 5 · security 5 · finance 4 · longrun 4 · devour 4 · video 4 · tools 3 ·
project 2 · voice 2 · device 2 · brain 2 · comms 1 · vision 1 · automation 1 · life 1 · image_video 1 ·
integration 1 · framework 1 · infra 1 · social 1 · collab 1`

**想不起来某个域有什么** → `omni list --domain system`（每条前面 `✅` = 只读无参可直跑，`🔒` = 要参数/要确认/已禁用）。

---

## 5. 图鉴（`state/skill_atlas.json`）

**现扫**产物，不是手抄清单。每个条目带：`名称 / 职业域 / 说明 / 触发词 / 通道 / 落在哪个根 /
有没有 references·scripts·assets / 许可`。

**去重纪律**：同一技能常被装在多个 agent 目录（`.agents` / `.claude` / `.openclaw-autoclaw` / `.openclaw`），
**按名去重**并把「出现在哪几个根」记进 `roots` —— **不去重就是虚报**（25 个 arkcli 装在 9 处会变成 225 条，
读的人会以为框架里有两百多个技能）。当前（2026-09-22 22:16 现读）：**去重前 450 → 273 条**，其中 95 条装在多个目录。

**要新读数**：`omni build`（技能目录变了就跑一次）。

---

## 6. 固化位置（**重启后要在**）

| 什么 | 在哪 | 为什么 |
|---|---|---|
| 本技能（源） | `<仓>/skills/gbt-omni/SKILL.md` | 随仓版本管理，是真身 |
| 本技能（装机） | `~/.agents/skills/gbt-omni/` | **本会话实测会读的技能目录** |
| 本技能（装机·仓约定） | `~/.openclaw-autoclaw/skills/gbt-omni/` | 本仓 AGENTS.md 指定的托管目录（AutoClaw 侧） |
| 图鉴 + 路由 | `<仓>/tools/codex-scripts/omni.py` | 普通脚本，落盘即在 |
| 图鉴数据 | `<仓>/state/skill_atlas.json` | 现扫产物；`ask` **只在文件不存在时才重建**，输出里会打"本轮是读的还是重建的" |
| 万能插本体 | `<仓>/tools/codex-scripts/five-dim.py` | 走的仍是 `run_task` 唯一门 |
| **本地工具面（本目标轮新增）** | `omni.py` 里的 `LOCAL_TOOLS` | 扫描器/操作台登记表：真命令 + 门 + **可达性**（文件在不在、能不能解析） |
| **本会话真读的技能根（判可达性用）** | `omni.py` 里的 `SESSION_SKILL_ROOTS` | `<仓>/.dsh/skills` ∪ `~/.agents/skills` —— 实测只有这两个里的技能 `skill <名>` 才认 |

**纪律**：能力不许只活在**进程内**（动态插件 / 运行中的服务 / 浏览器注册）—— 那些一重启就没了。
真身必须是盘上文件，且落在**会被读取的目录**；写完必须**验证它真被认出来**。
⚠️ 补一条（2026-09-23 实测）：**"落在会被读取的目录"这件事，`skill <名>` 只在下次会话才认** ——
技能目录是**会话启动时快照**的。所以当场验证要用**文件哈希/路径比对**，不能靠调 `skill`。

---

## 7. 诚实边界（这段不许删）

1. **"精通"是分层的：全量索引做完了，深度蒸馏按域推进中**：
   - **全量索引**（图鉴现读，`omni caliber` 可现算）：**能力位条数、enabled 数、免卡可直跑数、
     图鉴技能条数、域数、审美料目录数—— 一律现算**（见 §7 的现读命令；本文**不写死任何一个数**）—— 是现扫，不是手抄；
   - ⚠️ **本文曾同时出现过 122 与 88 两个"可直跑"数且都没写定义**，而 `omni_max.py` 真跑是 102 ——
     **同一件事三个数**。现已改为**只指口径、不写死数字**：
     ```powershell
     py -3.14 tools/codex-scripts/omni.py caliber     # A→H 八种口径现算 + 指定权威口径
     ```
     **权威口径 = H**（域过滤 + 只读扫描器豁免）。口径 G 是"上一轮真跑用过的旧筛法"，
     与 H **不等**，两个都要写清 —— 不许拿一个当另一个。
   - ✅ **两张"需确认"名单曾各算各的（2026-09-24 已深修为单一真源）**：omni 图鉴标
     `needs_confirmation` 曾有 22 条，而 `cross_scan.PROBE_SKIP_KINDS` 原是**手抄**的 13 条
     （差 9：`devour_reflect` `lr_tick` `root_fix` `sched_define` `sched_tick` **`wf_cache_clear`**
     `wf_define` `wf_resume` `wf_run`）⇒ 这 9 条"要确认"的曾被当"可直跑"真跑过
     （`wf_cache_clear` 真跑并回报 `cleared:1` 就是这个原因，**不是正则漏了 `clear`**）。
     深修后：**改状态的唯一定义在 `preflight`**（公开访问器 `state_changing_kinds()`），
     `PROBE_SKIP_KINDS = 探测专项 11 ∪ 改状态 11 = 22` 从它**派生**；图鉴的
     `needs_confirmation` 用同一份派生 ⇒ `caliber` 现做**同源校验**（不等 = 派生链断了，当真故障报）。
   - **已深蒸 30 / 30 域**（2026-09-22 收尾，**在队 0**；有我们自己的规程 + 可机检入口）：
     `tentacle` `llm` `creation` `image_video` `data` `finance` `vision` `device` `voice` `framework`
     `mind` `engine` `system` `longrun` `pipeline` `recon` `video` `security` `brain` `comms` `devour`
     `dangerous` `tools` `project` `automation` `life` `integration` `infra` `social` `collab`；
   - **已深蒸 15 / 20 簇**（簇的判据是**该簇每条技能都被规程点到**）：
     `arkcli`(25) `lark`(28) `fal`(12) `autoglm`(9) `figma`(7) `design`(4) `autoclaw`(5) `sandbox`(3)
     `pptx`(4) `youtube`(3) `video`(3) `frontend`(4) `gsap`(4) `web`(4)；
     其余在飞（venice · alchemy · cloudflare · ef · glmv）；
   - 🔴 **判据是三道彼此独立的门，一条命令跑完**（别照本文的数字当结论，它们会随交付变动）：
     ```powershell
     py -3.14 tools/codex-scripts/gbt-checkup.py        # 三关合一（推荐：退出码就是门）
     ```
     拆开看是这三条，**少跑一条就会得出"看着都挺好"的错觉**（本会话栽过三次）：
     ```powershell
     py -3.14 tools/codex-scripts/omni.py gaps                  # ① 队列：登记没登记（现算 + **现读盘**，实物缺失/两份不一致会告警）
     py -3.14 tools/codex-scripts/verify-distill.py --all       # ② 内容：覆盖 + 同哈希 + 点名位真存在 + 零编造
     py -3.14 tools/codex-scripts/audit-regulations.py          # ③ 结构：每件有没有 红线/未验账/门/出处 四个面
     ```
   - ⚠️ **本表曾经写错一处并已更正**：`creation` / `image_video` 原先指向 `gbt-aesthetic`，
     而那份规程**一个能力位都没点到**（机器验收一跑就露馅）⇒ 现指向 `gbt-creation`。
     **"已深蒸"这个结论必须过 `verify-distill.py`，人写的索引必然有缝。**
2. **队列在哪看**：`python tools/codex-scripts/omni.py gaps`
   —— 它把 **30 个域 + ≥3 条的技能簇逐个列出**并标 done/queued，
   **没做的也在表里**（状态从图鉴现算，不是手写待办，所以不会漏）；
   且**现在会现读盘**：登记的件若实物缺失或两份哈希不一致，会打 `⚠️ 已登记但实物缺失/不一致`，
   **不再只信映射表打绿勾**。
   推进规格：**蒸馏技能 + 可机检验收入口 + 固化三处**（照审美/手/Ark 那三个的规格）。
3. **语义主路未配置**：`semantic_route.available()` 报 `统一大模型通道未配置`，
   所以现在走的是**启发式**（中文 n-gram）。它**如实降级、不冒充**；配好主路后精度会显著提升。
4. **落点可能不只一个**：`ask` 故意给多个候选并列出理由，**由人定**；不要假装排序第一就永远对。
5. **有后果的动作永远要人**：本协议**不会**因为"听起来是个好主意"就自动写生产。这条不改。
6. **外部 CLI 有它自己的门与账单**：Ark 之类先过登录闸与账号验证闸（`identity.verified` false 时
   计费写入会被挡），本协议不替它放行。
7. **通道总账别只看 `total`**：`/api/capabilities` 的 `total` 只数**注册表**那一条通道；
   另有本面板路由面、契约未建面、Ark 云端面。它现在自己会报 `channels` 与 `total_all_channels`，
   **拿 `total` 当全量是误读**。
