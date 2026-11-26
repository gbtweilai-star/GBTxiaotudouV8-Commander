---
name: gbt-framework
displayName: GBT 框架门（门可见性 + 自改门规程）
version: 1.0.0
description: GBT小土豆V8 `framework` 职业域的用法规程（注册表里只此一位：`gate_visibility`）。它回答两件事 —— ① **门看得见什么、看不见什么**（三态：已纳入 / 显式不纳入 / 未决定，未决定那一栏就是「门盲区清单」）；② 姊妹工具 `framework_gate` 的**自改门**状态（基线 / 护照 / 印章 / verify 红绿）。规程里每一步都带**当天真跑的读数**，并写死一条纪律：**派并发任务前先看它要碰的门是不是一次性的**（本机授权是一次性消耗，2026-09-22 已被烧掉两张）。当用户问「门看得见什么 / 有没有盲区 / 框架自改门现在什么状态 / verify 为什么红 / 改框架要不要护照」，或要判断某个动作会不会被门挡住时使用。
triggers:
  - "门盲区"
  - "门看得见什么"
  - "框架自改门"
  - "framework_gate"
  - "gate_visibility"
  - "verify 红"
  - "护照"
  - "基线"
  - "改动留账"
---

# GBT 框架门（门可见性 + 自改门）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 分工：`gbt-omni` 管「人话落到哪条能力位」；**本件只讲"门"这一件事** ——
> 门看得见什么、看不见什么，以及改框架时那本账（基线 / 护照 / 印章 / 红绿）。

**唯一现读入口（别信二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap gate_visibility        # 门可见性（能力位 · 只读 · 免授权）
py -3.14 -m gbt_allinone.tools.framework_gate status                 # 自改门状态（只读）
py -3.14 -m gbt_allinone.tools.framework_gate verify                 # 自改门核对（只读，会给出红/绿）
```

---

## 1. 这一格是什么（图鉴口径 + 实测）

| 项 | 值 |
|---|---|
| kind / domain | `gate_visibility` / `framework`（本域**只有这一位**） |
| `safe` / 参数 | `true` / 无必填参数 |
| 授权门 | **无**（`policy.evaluate('gate_visibility', {})` 实测 `risk='low'` · `scopes=()` · `restricted=False`）⇒ **随时可跑** |
| 三态 | `已纳入` · `显式不纳入` · `未决定` |
| 判据单一 | `read_from`: **「framework_gate 的常量（本模块不复刻范围表）」** —— 范围表只有一处真源，本模块**不另抄一份** |
| 盲区文档 | `doc`: `gbt_allinone/docs/门盲区清单.md` |
| 核心一句 | `core`: **「门必须知道自己看不见什么」（坑册 §60）** |

**四条机械闸**（图鉴原话，也是本模块的牙）：
① 三态不许漏；② **不纳必须带出处**；③ 已纳入必须**命中门规则**；④ **空样本不许当绿**。

---

## 2. 实测读数（2026-09-22 真跑，原文摘录）

```
status ok · stamp true · denied false
states   = ["已纳入","显式不纳入","未决定"]
gate_scope.dirs       = ["gbt_allinone","holo_pet","holo_pet_w3","potato_pet"]
gate_scope.suffix     = [".py",".js",".cjs",".html",".css",".bat",".ps1"]
gate_scope.root_files = ["AGENTS.md","HEARTBEAT.md","CHARTER.md","SOUL.md","CODING_DISCIPLINE.md"]
gate_scope.root_suffix= [".md",".bat",".py"]
gate_scope.root_exclude=["USER.md","MEMORY.md"]
gate_scope.extra_files =[".cluster/dd_squad/toolchain_manifest.json"]
gate_scope.skip_dirs   = [".backups",".git",".pylibs",".scratch",".venv","__pycache__","archive", …]
```

**怎么念这张表**：
- 「可见」= 上面那些目录 / 后缀 / 根级文件；**根级 `.md` 里 `USER.md` 与 `MEMORY.md` 被显式排除**
  —— 那是保护长期文件，**不是漏了**（属于三态里的「显式不纳入」，且必须带出处）；
- **不在表里 = 「未决定」，不是「没问题」** —— 未决定那一栏才是要盯的盲区；
- 想核"某个文件到底算哪一态"，**别自己推**：用 `gate_visibility.classify(path)` 的同一套判据
  （测试 `gbt_allinone/tests/test_gate_visibility.py` 就是它的牙）。

---

## 3. 姊妹工具 `framework_gate`（自改门）

四个子命令，**只有前两个是只读**：

| 命令 | 性质 | 实测（2026-09-22） |
|---|---|---|
| `…framework_gate status` | **只读** | `ok true` · 基线 `baseline_at 2026-09-21T11:06:17` · `baseline_files 400` · 护照列表（每条带 `changed_files` / `has_stamp` / `complete`） |
| `…framework_gate verify` | **只读** | **`ok false` · `verdict "red"`** · `changed_files 136` · `passports_closed 513` · `stamp_waived_passports` 一大串 —— 详见第 4 节 |
| `…framework_gate snapshot --label "…"` | **写**（立基线） | 有未关护照时**拒绝**（`rc=2` `reason_code=passport_open`）；确要吞须 `--force` + 理由并写进基线 |
| `…framework_gate open/close` | **写**（开/关护照） | 关护照要**五件套**（原因 / 证据"命令=>读数" / 独立复核 / 回滚 / 印章），缺件 `rc=2`；**且复核的 checker 标签与 evidence 标签同名即红** |

🔴 **AI 不许自己开护照、不许自己盖章**：那是"改框架要留账"的机制，
`--no-review-reason` 那种豁免口子也**不许**由 AI 拿来给自己开后门。缺件就如实报缺件。

---

## 4. 🔴 现读读数：`verify` 是**红**的 —— 怎么念、别念错

2026-09-22 实测原文：`ok: false` · `verdict: "red"` · `changed_files: 136` · `passports_closed: 513`。

**它说的是什么**：相对基线（2026-09-21T11:06:17 立的 400 个文件），**有 136 个被监视文件发生了变动**，
而门的账（护照 / 印章）**没对齐到能判绿** —— `stamp_waived_passports` 那一长串就是"带豁免关掉的护照"。
按模块自己的口径，红来自两类：`no_passport`（有变动没护照）与 `stale_passport`（护照过期/对不上）。

**别念错的三处**：
1. **红 ≠ "有人偷偷改了框架"**。它只说明"账实没对齐"，不含动机、也不含好坏；
2. **红 ≠ 全是今天造成的**。基线是 09-21 立的，136 是**相对基线**的累计；其中**本会话确有贡献**
   （今天改过 `caps_registry.py` / `brain_exec.py` / `quant_tech.py` / `tentacle/bridge.py` /
   `gbt_allinone/store` 下的账），但**其余部分不是本会话的**，别把 136 全揽到自己身上、也别全推给别人；
3. **绿也不是"没人改过"**，绿只说明"变动都有对应护照与印章"。
⇒ **要断言"谁改了什么"，只看 `changed_files` 列表与护照内容，不看红绿本身。**

---

## 5. 怎么用（三条实操）

1. **派活 / 动手之前先看门**：要碰的能力位后面是哪道门、这道门**是不是一次性的**
   （`desktop_control` / `device_control` / `privacy_read` 这类**一次性消耗**：花掉就没了）。
   一次性授权**只配给它本意那一件事，并且当轮就用掉** —— 2026-09-22 本机两张
   `desktop_control` 就是这么被无关调用烧掉的（审计里 `auth_consumed` 才算真花，`auth_denied` 不算）。
   查可用数：`py -3.14 -m gbt_allinone auth status`。
2. **看盲区用"未决定"，别用"有没有报错"**：门不报错，**沉默**才是问题。
   `gbt_allinone/docs/门盲区清单.md` 是"未决定"那一栏的落地版；**空样本不许当绿**
   （没有样本 = 没验证过 = 不许打勾）。
3. **改框架要留账**：先 `status` 看清基线，动完 `verify` 看红绿；
   护照这类写动作**由主人拍板**，AI 只负责把"改了什么、证据是什么"备齐。

---

## 6. 🔴 报告层红线（读数先问"这是事实，还是我读错了地方"）

1. **`verify` 的 `ok:false` 是结论字段，不是错误** —— 别当成"工具坏了"；
2. **同名的东西要看是不是同物**：`changed_files 136`（相对基线的文件数）与护照里的
   `changed_files 6/10`（那本护照内的文件数）**是两个口径**，混着念必错；
3. **能力位信封**：只读位成功时 `status ok` / `ok true`；被门拒时是**扁平信封**
   （顶层 `missing_scopes`，**没有 `gbt_result`**）—— 要按拒绝念，不要读成"未知"；
4. **数字要带口径**：`baseline_files 400` 是**基线当时**的文件数，不是现在的仓库文件数。

---

## 7. 验收（做完怎么证明真做了）

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap gate_visibility     # 期望 status ok · states 三态齐 · gate_scope 非空
py -3.14 -m gbt_allinone.tools.framework_gate status             # 期望 ok true + 基线时间 + 护照列表
py -3.14 -m gbt_allinone.tools.framework_gate verify             # 期望拿到红/绿与数字（红不一定是错，要按第 4 节念）
py -3.14 tools/codex-scripts/verify-distill.py --domain framework --skill gbt-framework   # 本件的机器验收
```

---

## 8. 固化与出处

- 能力位真源：`state/skill_atlas.json`；图鉴 desc：`gbt_allinone/caps_registry.py`
- 门可见性实现：`gbt_allinone/tools/gate_visibility.py`（`read_from` 指向门常量）
- 自改门实现：`gbt_allinone/tools/framework_gate.py`（`status`/`verify`/`snapshot`/`open`/`close`）
- 盲区文档：`gbt_allinone/docs/门盲区清单.md`
- 门的作用域与一次性语义：`gbt_allinone/security/policy.py` · `auth_gate.SCOPES`
- 审计原文（判断"花没花授权"的唯一依据）：`gbt_allinone/store/audit.jsonl`（只看 `auth_consumed`）
- 本件的机器验收：`tools/codex-scripts/verify-distill.py`
