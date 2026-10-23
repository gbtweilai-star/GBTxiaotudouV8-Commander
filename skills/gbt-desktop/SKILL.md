---
name: gbt-desktop
displayName: GBT · desktop 职业域用法规程（1 个能力位：ul_tars_desktop）
version: 1.0.0
description: GBT小土豆V8 的 `desktop` 职业域（桌面 GUI 智能体 UI-TARS Desktop · 三原语 PROBE·VERSION·EXEC）用法规程。这个域**只有 1 个能力位**：`ul_tars_desktop`。本文件把它写全：用途、三个 op 逐个标「要不要过门 / 会起进程吗」、逐 op 静态查+实测的作用域（**读 op 零作用域；exec/run/chat/ask 实挂 process_execute + external_llm**——与隔壁 cloud_pc「连花钱动作都零作用域」形成活对照）、真命令、真探结果（本机**未装**：找过 tars/ul-tars/ui-tars/UITARS 四个名）、`op=exe` 绝对路径旁路、失败典型样子（needs_dependency 不是坏了也不是被拒）、与 claude_code/codebuddy（同模块·但归 llm 域）和 gbt-tentacle（看屏幕那条路）的边界；并记下实测读数。当用户要起桌面 GUI 智能体、要问它装没装、要 op=exe 指路，或 ul_tars_desktop 报 needs_dependency 时使用。
triggers:
  - "UI-TARS"
  - "ui-tars"
  - "桌面智能体"
  - "GUI 智能体"
  - "ul_tars_desktop"
  - "desktop"
  - "needs_dependency"
---

# GBT · desktop 职业域用法规程（1 个能力位：`ul_tars_desktop`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`desktop` 是一位一域的最小域，它连着**外面的一整个 GUI 智能体**（UI-TARS Desktop）。
> 它踩的坑与 `cloud_pc` **对称而不同**：
> ① `cloud_pc` 是「**连花钱动作都在 policy 层零作用域**」；`ul_tars_desktop` 反过来 ——
> **读 op 零作用域，但 `exec/run/chat/ask` 实挂 `process_execute` + `external_llm`**（本规程实测）。
> ⇒ 两个域都叫"零作用域域"，**结论却相反**：拿一个去推另一个必错。
> ② 现状是「**真探过，本机没装**」：四个候选名全查了 PATH，一个都没有；
> 如实报 `needs_dependency` **不是"坏了"，也不是"被门拒"**。
> 本文件把「哪个 op、要不要授权、失败长什么样、读数该看哪个字段」逐个钉死。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```bash
python tools/codex-scripts/five-dim.py cap ul_tars_desktop ['<JSON载荷>'] [--full]
```

一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。

---

## 0. 一位一域（先确认名字）

现读 `gbt_allinone/caps_registry.py`（`domain == "desktop"`）**有两条**：

| 域 | 能力位（kind） | handler | safe | 注册表 desc 原文 |
|---|---|---|---|---|
| `desktop` | **`ul_tars_desktop`** | `ul_tars_desktop` | **false** | "Ul-TARS Desktop desktop agent" |
| `desktop` | **`control_loop`** | `control_loop` | **true** | 快慢双脑控制回路（枚举动作 · 执行前两查 · DONE 独立验证 · 预算闸 · 写 state/control_loop.jsonl 审计链）；**只决策不动手** |

🔴 **2026-10-11 勘误**：本节原来写「**只有一条**」—— 那是本文件写于 2026-10-03 时的读数，
而 `control_loop` 之后也挂进了 `domain="desktop"` ⇒ **那句话已经过期**（文档说了一个不再成立的事实）。
现在按现读改成两条。

**两条各有专件，别串门**：
- `ul_tars_desktop`（起外部 GUI 智能体进程）→ **本文件**
- `control_loop`（快慢双脑决策回路）→ **`skills/gbt-control-loop/SKILL.md`**（另一份规程，本文件不重写它）

分派链（三处接齐 · 实测可调）：
`api.py:330`（`kind == "ul_tars_desktop"` → `cli_agents.ul_tars_desktop(payload)`）
→ `cli_agents.py:152` → `run("ul_tars_desktop", payload)`（88-141 是全部逻辑）

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个 op | 只读还是要授权 | 起进程吗 |
|---|---|---|---|
| 问「本机装没装 UI-TARS」 | `status` / `list` / `probe` | 只读，**零作用域** | 否 |
| 看装的是哪个版本 | `version` / `ver` | 只读，**零作用域** | 跑一次 `--version` |
| **让它真干活（给 prompt）** | `exec` / `run` / `chat` / `ask` | 🔴 **挂 `process_execute` + `external_llm`** | ✅ 起外部进程 |

**不在这 1 个位里的事**：看屏幕/操作鼠标键盘 → `gbt-tentacle`；
`claude_code` / `codebuddy`（同一模块实现的兄弟位）→ **归 `llm` 域**，不在本规程范围。

---

## 2. 🔴 要过哪道门：**读免卡、写（起进程）挂两作用域**

**实测（本机 2026-09-26 · `policy.evaluate` 逐 op 真跑）**：

```python
policy.evaluate("ul_tars_desktop", {"op": "status"}).scopes   # → ()          零作用域
policy.evaluate("ul_tars_desktop", {"op": "version"}).scopes  # → ()          零作用域
policy.evaluate("ul_tars_desktop", {"op": "exec"}).scopes     # → ('process_execute', 'external_llm')
policy.evaluate("ul_tars_desktop", {"op": "run"}).scopes      # → ('process_execute', 'external_llm')
policy.evaluate("ul_tars_desktop", {"op": "chat"}).scopes     # → ('process_execute', 'external_llm')
policy.evaluate("ul_tars_desktop", {"op": "ask"}).scopes      # → ('process_execute', 'external_llm')
```

| op | 作用域（实测） | risk | restricted |
|---|---|---|---|
| `status` / `list` / `probe` | **零** | low | false |
| `version` / `ver` | **零** | low | false |
| **`exec` / `run` / `chat` / `ask`** | **`process_execute` + `external_llm`** | **high** | **true** |

🔴 **与 `cloud_pc` 的活对照（本域最大的读反风险）**：
`cloud_pc` 是「连 `provision`（花钱+不可逆）都零作用域」；本域是「**读零作用域，起进程挂两作用域**」。
⇒ **别拿"都是零作用域域"把两个域的结论互换**（policy.py:427 `kind in ("claude_code","codebuddy","ul_tars_desktop")` 那一支就是本域的门）。

**未受信会话要跑 `exec`**：须主人在终端发 `process_execute` 与 `external_llm` 两条授权
（`python -m gbt_allinone auth grant --scope process_execute --ttl 600` 等）。
**AI 永远无权给自己发授权** —— 缺授权就如实报缺，不找旁路、不改 `security/policy.py`。

---

## 3. 怎么调（真命令）

```bash
# ── 只读这一档（零作用域；本规程真跑过，见 §6）──
python tools/codex-scripts/five-dim.py cap ul_tars_desktop                      # 空载荷 = status
python tools/codex-scripts/five-dim.py cap ul_tars_desktop '{"op":"status"}'
python tools/codex-scripts/five-dim.py cap ul_tars_desktop '{"op":"version"}'

# ── 起进程那一档（挂两作用域；本规程未跑，见 §8）──
python tools/codex-scripts/five-dim.py cap ul_tars_desktop '{"op":"exec","prompt":"帮我打开记事本"}'
python tools/codex-scripts/five-dim.py cap ul_tars_desktop '{"op":"exec","prompt":"…","exe":"C:/path/to/UI-TARS.exe","timeout":300}'
```

🔴 **`op=exe` 是 PATH 旁路**（源码 106 行 `exe = p.get("exe") or probe["found"][0]["path"]`）：
本机没进 PATH 时，直接给绝对路径即可跳过探测 —— 但**先 `status` 确认 probe 结果**，别拿旁路当"装好了"。

---

## 4. 有哪些 op（源码逐个点名 · `cli_agents.py:88-141`）

| op | 去处 | 性质 |
|---|---|---|
| `status` / `list` / `probe` | `_probe(kind)`（shutil.which 真查四名） | 只读 |
| `version` / `ver` | `_version(exe)`（`--version`→`-v`→`version` 三个旗标轮流试） | 只读（跑一次） |
| `exec` / `run` / `chat` / `ask` | `subprocess.run([exe, prompt])`，stdout/stderr 原样带回，**不吞错** | 🔴 起进程 |
| 缺 `prompt` | `{"ok": false, "error": "缺少 prompt"}` + hint | 拒（非门拒） |
| 未知 op | `known: ["status", "version", "exec"]` | 拒（非门拒） |

---

## 5. 落点 / 外部面（真探结果）

| 维度 | 实测（2026-09-26） |
|---|---|
| **PATH 探测** | `found: []` · `available: false` · 找过：`tars`、`ul-tars`、`ui-tars`、`UITARS` |
| **安装提示（原文）** | "UI-TARS Desktop 是**图形应用**，不是 CLI —— 装完把它的可执行目录加进 PATH，或用 op=exe 直接给绝对路径" |
| **兄弟位** | `claude_code`（未装）· `codebuddy`（**已装**：`%LOCALAPPDATA%\codebuddy\bin\codebuddy.exe`）——两者归 llm 域 |
| **落点** | 读 op 不写盘不出网；`exec` 起外部进程（stdout 截 8000 / stderr 截 2000） |
| **超时** | `exec` 默认 300s，可传 `timeout`；超时回 `status: "timeout"` |

---

## 6. 实测读数（本机 2026-09-26 真跑，原文抄录）

### 6.1 `cap ul_tars_desktop '{"op":"status"}'`

```json
{"gate":"run_task","kind":"ul_tars_desktop","status":"ok","stamp":true,"denied":false,
 "result":{"ok":true,"op":"status","kind":"ul_tars_desktop","dimension":"llm",
  "label":"UI-TARS Desktop（桌面 GUI 智能体）",
  "found":[],"available":false,
  "searched":["tars","ul-tars","ui-tars","UITARS"],
  "install_hint":"UI-TARS Desktop 是**图形应用**，不是 CLI —— 装完把它的可执行目录加进 PATH，或用 op=exe 直接给绝对路径",
  "口径":"真查 PATH（shutil.which），不是读配置猜的"},
 "_信封":{"found":true,"synced":true,"entry":"outer","via":"ctx","来源":"审计账本末尾现读"}}
```

exit **0**。注意：`status:"ok"` 是**外层**（run_task 门系正常），`result.available:false` 是**内层**（真探结论）——
**判"这一发调用成功了吗"看外层；判"本机能不能用它"看内层 `available`。**（与 gbt-infra §10.4 同型）

---

## 7. 失败典型样子（照着认）

| 症状 | 真因 | 正确读法 |
|---|---|---|
| `ok:false` + `status:"needs_dependency"` + `missing:"…可执行文件（找过：…）"` | **本机没装**（真探过） | **不是"坏了"、不是"被门拒"** —— 装完再调，或 op=exe 给绝对路径 |
| `ok:false` + `error:"缺少 prompt"` | exec 没给 prompt | 补 `prompt`；只想看装没装用 `status` |
| `ok:false` + `status:"timeout"` | 外部智能体 300s 未返回 | 调 `timeout` 或查那个进程在干什么 |
| `denied:true` + `missing:["process_execute",…]` | 未受信会话跑 exec | **这才是"被门拒"** —— 主人在终端发授权（§2） |
| 把 `status:"ok"` 读成"桌面智能体可用" | 外层 ≠ 内层 | 看 `result.available`（§6.1） |

---

## 8. 🔴 未验清单（**为什么不做**）

| 动作 | 状态 | 为什么不做 |
|---|---|---|
| `{"op":"exec", …}` 真跑 | **未验** | 本机没装（真探过）+ 会起外部进程；要跑须主人授权两作用域 |
| `{"op":"version"}` 真跑 | **未验** | 没装，`_version` 无从跑；装了即验 |
| `op=exe` 绝对路径分支 | **未验** | 没有真可执行文件可指；分支源码在 106 行 |
| `codebuddy` 真调 | **不在本域** | 归 llm 域规程；本规程只把它作为"兄弟位对照"记录 |

> **"未验"不是"不能用"**：上表每条都存在、都有源码落点；缺的是当次运行证据。

---

## 9. 与相邻域的边界（一句话切干净）

| 相邻 | 谁是谁 | 边界 |
|---|---|---|
| `gbt-tentacle` | 手眼网耳（看屏幕/鼠标键盘） | 那是**我们自己的**输入层；本域是**起外面一整只 GUI 智能体**。两者都可操作屏幕，**门不同**（本域挂 process_execute+external_llm） |
| `gbt-llm`（claude_code / codebuddy） | 同模块兄弟位 | **同一份 `cli_agents.py`，不同域**：它俩 domain=llm；**改本域时不许顺手动它们** |
| `gbt-infra`（cloud_pc） | 另一位一域 | 都易读反：cloud_pc「连花钱也零作用域」，本域「起进程挂两作用域」——**结论相反** |

---

## 10. 🔴 报告层红线

1. **外层 `status:"ok"` ≠ 内层可用**：判调用看外层，判可用性看 `result.available`（§6.1）。
2. **`needs_dependency` ≠ 坏了 ≠ 被拒**：它是"真探过、没探到"的如实报告（§7）。
3. **"零作用域"必须带 op 说**：本域读 op 零、写 op 非零——**单说"本域零作用域"就是错话**。
4. **同模块 ≠ 同域**：claude_code/codebuddy 与 ul_tars_desktop 共用实现，**域不同门不同**。
5. **未验就是未验**：不拿"源码看着能"当"验过"。

---

## 11. 不许做什么（红线）

1. **不许给自己发授权**：不跑 `auth grant`、不手写 `store/auth_grants.jsonl`、不改 `security/policy.py` / `auth_gate`。
2. **不许绕门**：不直接调 `cli_agents.run(...)` 替掉 `run_task` 唯一门。
3. **不许**把 `op=exe` 当"装好了"的证据。
4. **不许**替主人编 UI-TARS 的安装路径/版本（本机没有就是没有，`found: []` 是读数）。
5. **不许**动 `cli_agents.py` 里另两个兄弟位的域归属（那是 gbt-llm 的地界）。

---

## 12. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-desktop/SKILL.md` |
| 本规程（装机·托管目录） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-desktop\SKILL.md` |
| ⛔ **不许装到** | `~/.agents/skills/`（本仓 AGENTS.md 明令禁止） |
| 注册表条目 | `gbt_allinone/caps_registry.py`（`domain == "desktop"` 唯一条） |
| 分派 | `gbt_allinone/api.py:330` → `gbt_allinone/cli_agents.py:152`（`run()` 88-141；`_probe` 66-81；`_version` 84-97） |
| 授权判据（**单一真相**） | `gbt_allinone/security/policy.py:427`（`kind in ("claude_code","codebuddy","ul_tars_desktop")` 那一支） |
| 现读入口 | `tools/codex-scripts/five-dim.py cap ul_tars_desktop` |

**验收（做完怎么证明真的做了）**：

```bash
python tools/codex-scripts/verify-distill.py --domain desktop --skill gbt-desktop
```

1. 必须 **PASS**（覆盖 1/1）；
2. 两份产物**逐字节相同**（sha256 一致）；
3. 再静态查 `policy.evaluate("ul_tars_desktop", {"op":"exec"}).scopes` —— 必须**仍是** `('process_execute','external_llm')`
   （哪天变了，回来改本文件 §2）；
4. 声明"某 op 能用"之前先问：**这是实测读数，还是我读错了地方？** 拿不准就写"未验"。
