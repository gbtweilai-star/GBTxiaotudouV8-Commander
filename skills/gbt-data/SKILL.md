---
name: gbt-data
displayName: GBT 数据域（回显 · 词数 · 审计 · 行网格 · 账号登记）用法规程
version: 1.0.0
description: GBT小土豆V8 的「数据职业域」用法规程 —— 把图鉴里 domain=data 的 5 个能力位（echo / count_words / audit_query / record_grid / account_registry）蒸馏成能照着跑的一页：每位写清用途、只读还是要授权、真命令模板、失败典型样子，并附一份**实测过的诚实账**（4 位真跑通、audit_query 缺 audit_read 被门挡住不许绕）。当用户要「回显联调 / 统计词数 / 查审计日志 / 解析或回写行式记录 / 校验 AI 账号登记表」，或数据类能力位调不通、被门拦住、看不懂返回、怀疑自己读错了地方时使用。
triggers:
  - "数据域"
  - "data 域"
  - "回显"
  - "统计词数"
  - "字数统计"
  - "审计日志"
  - "行式记录"
  - "记录网格"
  - "回写自证"
  - "账号登记表"
  - "一人一号"
  - "解析这个表格"
  - "能力位"
---

# GBT 数据域（data）用法规程

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是「人类视角操控一切」在**数据这一格**的用法：`gbt-omni` 负责"人话落到哪个能力位"，
> 本规程负责"落到数据域这 5 位之后，命令长什么样、要不要授权、失败长什么样、读数怎么读才不读错"。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/omni.py list --domain data   # 这 5 位是什么（图鉴现扫）
py -3.14 tools/codex-scripts/omni.py ask  "统计一下这段文本有多少词"
```

**⚠️ `omni list` 标的 ✅ 不等于"门放行"** —— 它是图鉴旗标算出来的，不查授权门。
本域实测就有一个假的 ✅（见 §5 第 3 例）。

---

## 0. 五位一个门：`run_task`

5 个能力位**全走同一个门**，唯一入口：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['{"参数": ...}']
```

**没有第二条路**：不许直接 import 模块函数、不许自己写脚本绕过 `run_task` —— 那等于绕门。

**域怎么定的**：以 `state/skill_atlas.json` 里 `domain == "data"` 的条目为**准**（现扫读数 5 条）。
不是谁记得的清单，也不是本文件说了算。

---

## 1. 六位总表（一页看全）

| 能力位 | 用途（图鉴原文） | 门 | 参数 | 实测判定 |
|---|---|---|---|---|
| `echo` | 回显传入数据，用于联调 | 零作用域 | 任意 JSON | ✅ 真跑通 |
| `count_words` | 统计文本词数 | 零作用域 | `text` | ✅ 真跑通 |
| `audit_query` | 只读查询统一数据后台日志 | 🔒 **`audit_read`** | `event`（可选） | ⛔ **未验**：缺授权被门拒 |
| `record_grid` | 行式记录网格：结构画像/草案骨架/逐行解析/回写自证/词表校验 | 零作用域 | `op` + `text`/`path`/`plan_name`/… | ✅ 真跑通（写盘分支除外） |
| `account_registry` | AI 账号登记表只读校验：一人一号 | 零作用域 | `op` = status/load/validate | ✅ 真跑通 |
| `datakit` | 本地数据工具（**只读**）：html→markdown · html→表格结构 · xlsx 字节→JSON · JSON 美化/排序 · 多段 CSV 合并 | 零作用域 | `op` = html2md/html2xlsx/xlsx2json/jsonfmt/csvmerge/tools | ✅ 真跑通（`tools` 现读 op 表） |

**门是静态查出来的，不必先撞一次才知道**（`gbt_allinone/security/policy.py`）：

```powershell
py -3.14 -c "import sys; sys.path.insert(0,'.'); from gbt_allinone.security import policy; print(policy.evaluate('audit_query',{}))"
```

实测返回：`PolicyDecision(kind='audit_query', risk='medium', scopes=('audit_read',), action='audit_query', allow_private=False, details={})`，
其中 `restricted=True`。
另外 **5 位**（`echo` / `count_words` / `record_grid` / `account_registry` / `datakit`）
静态求值一律 `scopes=()` · `restricted=False` · `risk='low'`。
⇒ **6 位里只有 `audit_query` 要授权**，但它恰好是"看起来最像只读、最容易被当成免卡"的那一个。

---

## 2. 逐位用法（真命令 → 真返回 → 失败样子）

### 2.1 `echo` —— 联调回显

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap echo
# ⇒ status ok · stamp true · denied false · result {"echo": {}}

py -3.14 tools/codex-scripts/five-dim.py cap echo '{"hello":"world","n":3}'
# ⇒ result {"echo": {"hello": "world", "n": 3}}
```

- **口径**：入参**原样挂在 `result.echo` 下**，不是 `result` 本身；
- **只读**，零作用域，`requires_params: []`；但**空跑只得到 `{"echo": {}}`，联调没意义** —— 图鉴说"不需要参数"≠"调用有意义"；
- **失败典型**：位本身几乎不会失败，翻车的是 **shell 引号**。实测：
  `cap echo '{\"hello\":\"world\"}'` → `json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)`（exit 1）。
  **正确写法**：PowerShell 单引号里直接写双引号 JSON，**别叠反斜杠**：
  `cap echo '{"hello":"world"}'`。
  这是**五位共用的坑**，不是 `echo` 特有的。

### 2.2 `count_words` —— 统计文本词数

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap count_words
# ⇒ result {"words": 0, "chars": 0}

py -3.14 tools/codex-scripts/five-dim.py cap count_words '{"text":"你好世界 hello world 三"}'
# ⇒ result {"words": 4, "chars": 18}

py -3.14 tools/codex-scripts/five-dim.py cap count_words '{"text":"a b  c"}'
# ⇒ result {"words": 3, "chars": 6}

py -3.14 tools/codex-scripts/five-dim.py cap count_words '{"text":"😀😀"}'
# ⇒ result {"words": 1, "chars": 2}
```

- **口径（实测反推 + `gbt_allinone/api.py:94-96` 一致）**：
  `words = len(text.split())` —— **按任意空白切分**，连续空格不算一个词；
  `chars = len(text)` —— **含空格**，Python **码点**计数，emoji 算 1 个 char。
  反推自检：「你好世界 hello world 三」空白切 = 你好世界/hello/world/三 = **4**；长度 = 4+1+5+1+5+1+1 = **18** ✔
- **只读**，零作用域；
- **失败典型（本域第一个"读错地方"陷阱）**：**它不报错**。`text` 缺席、或键名写成 `content`/`string`，
  一律**静默返回 `{"words": 0, "chars": 0}`** —— **0 不等于空文本，可能是你键名写错了**。
- **它不是分词器**：中文"词数"它也按空白切。要中文分词得另找能力，别拿它硬顶。

### 2.3 `audit_query` —— 只读查询统一数据后台日志（🔒 要授权，**未验**）

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap audit_query
```

真返回（**exit 1**）：

```json
{"gate": "run_task", "kind": "audit_query", "status": "denied", "stamp": false, "denied": true,
 "result": { "...": "（扁平拒绝信封，见 §4 第 1 例）" },
 "missing_scopes": ["audit_read"],
 "reason": "需要人工授权（audit_read）：读取审计、授权或运行历史",
 "how_to_grant": [
   "终端运行: python -m gbt_allinone auth grant --scope audit_read --ttl 600",
   "或主人手写 store/auth_grants.jsonl 追加一行（格式见 auth_gate.SCOPES 与 README）"],
 "note": "授权一次性消耗；AI 调用路径无权自行发放"}
```

**它的本体返回值我没验过** —— 缺 `audit_read`，被门挡住。而**授权只能主人在终端发**，
**AI 永远无权给自己发授权**；缺就**如实报缺**，**不找旁路、不改 `security/policy.py`**。

**静态读出（只作对照，不是已验读数）**：`gbt_allinone/api.py:97-99` 把 `event` 透传给 `query_log()`，
形状是 `{"total": <条数>, "sample": [...]}`。**这行是读源码读出来的，不是跑出来的** —— 别当成实测字段用。

### 2.4 `record_grid` —— 行式记录网格（7 个 op）

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap record_grid
# ⇒ status error（exit 1）· result.message "需要 text（内联文本）或 path（框架内相对路径）" · error_class user_error
```

**空跑必错**，必须先选 `op`（`profile|draft|parse|emit|verify|vocab|presets`）并给 `text` 或 `path`。

**① 先看语法（`op=presets`，只读）**

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap record_grid '{"op":"presets"}'
# ⇒ ok true
#    presets.link_index = {name, sep:null, quoted:false,
#                          url_schemes:[http,https,ftp,ftps,mailto,file,sftp,news],
#                          fields:[title(flex,*需填), url(url), packed(左topics/右genre), comment(tail)]}
#    note "预置是格式语法；词表请按语料用 vocab 覆盖"
```

**② 陌生文本先画像（`op=profile`）**

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap record_grid '{"op":"profile","text":"姓名,年龄,城市\n张三,30,北京\n李四,25,上海\n"}'
# ⇒ ok true
#    profile.lines = {total:3, non_blank:3, blank:0, sampled:3}
#    profile.line_ending = "lf"
#    profile.best = {sep:",", sep_repr:"','", modal_fields:3, consistency:1.0, aligned_rows:3}
#    profile.columns[0] = {type_candidates:{text:3}, distinct:3, empty:0, looks_like:"text", suggested_kind:"flex"}
```

**③ 生成草案骨架（`op=draft`）**

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap record_grid '{"op":"draft","text":"姓名,年龄\n张三,30\n李四,25"}'
# ⇒ ok true
#    plan = {name:"draft", sep:",", fields:[{name:"col0",kind:"flex"},{name:"col1",kind:"number"}],
#            warnings:["首行疑似表头，解析时应跳过或单独取出"],
#            based_on:{modal_fields:2, consistency:1.0, sampled_lines:3}}
```

**④ 逐行解析（`op=parse`）—— 本域最坑的一个：默认 plan 是 `link_index`，不是 CSV！**

```powershell
# 拿 CSV 直接 parse ⇒ 外层 status ok，本体 ok:false、status "partial"、records 全空
py -3.14 tools/codex-scripts/five-dim.py cap record_grid '{"op":"parse","text":"姓名,年龄,城市\n张三,30,北京\n"}'
# ⇒ ok false · status "partial" · plan "link_index" · records []
#    invalid[0] = {line:1, raw:"姓名,年龄,城市", code:"template_mismatch",
#                  hints:["字段数 1，契约要求 4 个字段","未找到 URL 段，检查是否缺少协议前缀或字段顺序颠倒"]}
#    fingerprint "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5"（空记录集的指纹）

# 按 link_index 语法（`标题[*] URL 标签,标签.类别 备注`，空白切分）写才行：
py -3.14 tools/codex-scripts/five-dim.py cap record_grid '{"op":"parse","text":"示例站[*] https://example.com 工具,资料.参考 备注一\n二站 https://a.example.org/x 文档.教程"}'
# ⇒ ok true · status "ok" · records 2 · invalid [] · stats{lines:2, records:2, invalid:0, longest_line:39}
#    记录形如 {title, title_flag, url, topics:[...], genre, comment, _line}
#    fingerprint "sha256:d51fd93fa5bd102176609ea2b08ed2e9"
```

- **packed 段必须同时有逗号和点**：`工具,资料.参考`（逗号分左标签、点分右类别）。少了点就报
  `packed 段 ... 与字段顺序不符或含空标签`；
- 实测细节：输入 `示例站[*]` 时返回 `title:"示例站[*]"`、`title_flag:false` —— **标记语义与直觉不符，以返回为准**；
- 想解析非 `link_index` 的结构，走 `op=draft` 拿骨架再用 `plan` 字段喂 `parse`。

**⑤ 回写自证（`op=verify`）**

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap record_grid '{"op":"verify","text":"示例站[*] https://example.com 工具,资料.参考 备注一\n二站 https://a.example.org/x 文档.教程"}'
# ⇒ ok true · idempotent true · records 2
#    fingerprint == reparsed（解析→回写→再解析，指纹一致）
#    invalid_first 0 · invalid_second 0 · first_difference null
#    note "幂等指的是记录层（字段值）一致；原始空白排版不做逐字节还原"
```

**⑥ 词表校验（`op=vocab`）** —— 两种入口都实测过：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap record_grid '{"op":"vocab","values":["工具","资料","参考"],"allowed":["工具","资料"]}'
py -3.14 tools/codex-scripts/five-dim.py cap record_grid '{"op":"vocab","text":"工具\n资料\n参考","allowed":["工具","资料"]}'
# 两条都 ⇒ ok false · checked 3 · vocab_size 2 · outside ["参考"] · outside_ratio 0.3333
```

**⑦ 回写（`op=emit`）—— ⚠️ 这一支是真写盘，我没执行**

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap record_grid '{"op":"emit","plan_name":"link_index"}'
# ⇒ status error（exit 1）· result.message "emit 需要 records（记录列表）"
```

- **静态读出（未执行，故标未验）**：`gbt_allinone/record_grid.py:700-718` 显示 `op=emit` 带 `out` 时走
  `atomic_write_text` 写 **`<仓>/gbt_allinone/store/record_grid/<out>`**；
- 而 `policy.evaluate('record_grid', {'op':'emit','out':'x.txt'})` 实测仍是 `scopes=()` · `restricted=False` ——
  ⇒ **图鉴标 `safe:true`、门不拦，但这一支确实落盘**。**要写盘先当它是写操作对待，别当只读用。**
- 不写 `out` 的纯生成分支**未单独跑**（只跑到"缺 records"的拒绝分支）。

**失败样子汇总**：缺输入 → `需要 text（内联文本）或 path（框架内相对路径）`；
未知 op → `未知 op: no_such_op；可选 profile/draft/parse/verify/emit/vocab/presets`；
plan 不匹配 → 外层 `status:"ok"` 而本体 `ok:false` + `invalid[].code: "template_mismatch"` + 可执行 `hints`。

### 2.5 `account_registry` —— AI 账号登记表只读校验

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap account_registry
# ⇒ ok true · readonly true · source "skeleton" · accounts 0 · violations []
#    rules = ["一人一号，一 AI 一号：同一平台同一账号不许挂在两个 AI 上",
#             "各 AI 各自持有凭证：不许共用一个 DPAPI 容器",
#             "凭证位置只记路径，不记密钥（明文密钥出现在登记表 = 违规）",
#             "每条记录必须带 platform 与 account（无主账号不许登记）"]

py -3.14 tools/codex-scripts/five-dim.py cap account_registry '{"op":"load"}'
# ⇒ schema "gbt.ai_accounts/v1" · accounts [] · ok true · source "skeleton" · note（"…真表落在 store/ai_accounts.json；本文件是模板"）

py -3.14 tools/codex-scripts/five-dim.py cap account_registry '{"op":"validate","registry":{"accounts":[
#     {"ai_id":"a1","platform":"x","account":"u1","credential_ref":"k1.dpapi"},
#     {"ai_id":"a2","platform":"x","account":"u2","credential_ref":"k1.dpapi"},
#     {"ai_id":"a3","account":"u3","credential_ref":"k3.dpapi","api_key":"sk-abcdefgh1234"}]}}'
# ⇒ ok false · count 3 · violations 3
#    {index:1, rule:"shared_credential",  why:"凭证容器被 a1 与 a2 共用（各 AI 各自持有）"}
#    {index:2, rule:"unowned_account",    why:"缺 platform 或 account（无主账号不许登记）"}
#    {index:2, rule:"plaintext_secret",   why:"记录里出现疑似密钥明文（只许记路径）"}
```

- **只读**（`readonly: true`），零作用域；op 只有 `status`（默认）/`load`/`validate`；
- **`source` 必须看**：真表落 `gbt_allinone/store/ai_accounts.json`（**实测不存在**）⇒ 回落骨架
  `gbt_allinone/docs/ai_accounts.skeleton.json`，所以读到 `source: "skeleton"` · `accounts: 0`。
  **看到 0 别当成"没人登记"就收工 —— 先分清这是"真表为空"还是"根本没真表"**；
- **只读校验不写盘、不出网**。但它的诚实边界写在源码里：**它只保证"一人一号的记账规则不被破坏"，
  不保证"账号真的合规"**（平台规则与人判在那之外）；
- **失败典型**：未知 op → `未知 op 'no_such_op'（可用：status/load/validate）`（exit 1）。
  另外**有违规时外层仍是 `status:"ok"`、exit 0，本体 `ok:false`**（§4 第 2 例）。

---

### 2.6 `datakit` —— 本地数据工具（只读六 op）

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap datakit
# ⇒ ok true · readonly true · note "本族**全部只读**：不落盘、不出网、不改任何文件"
#    ops = [html2md, html2xlsx, xlsx2json, jsonfmt, csvmerge, tools]
```

- **六 op 各管一件事**：`html2md`（html→markdown）· `html2xlsx`（html→表格结构）·
  `xlsx2json`（xlsx 字节→JSON）· `jsonfmt`（JSON 美化/排序）· `csvmerge`（多段 CSV 合并）·
  `tools`（列出本族 op 表，就是上面这行）；
- **🔴 最要紧的一条设计决定（源码原话）**：**结果从返回里给、不落盘** ⇒
  作用域天然为空，**不需要也不该改 `policy.py`**。
  为什么刻意**不做**落盘版：一个"能写任意路径的转换器"会把零作用域变成一个大写面；
  只从返回给 = 门不用拦、审计不用追；
- **它的岗位**：料进来先过它（网页存成 HTML 要变 md、表格要变 JSON、CSV 要拼），
  然后才喂给下游（`record_grid` 解析、`devour` 消化、产线用）；
- **失败典型**：给不存在的 `op` → 如实报可用 op 表（`status=denied` 之外的第二种红，别混着念）；
- **未验（如实记）**：本轮只真跑了 `tools` 与默认 `status`；五条转换 op **未逐个喂真料跑过**
  （`xlsx2json` 要 xlsx 字节、`csvmerge` 要多段 CSV —— 手上没备料就不许说"验过"）。

---

## 3. 本域只有一道门：`audit_read`

| 项 | 值（门自己打印的原文） |
|---|---|
| 要门的位 | **只有** `audit_query` |
| 作用域 | `audit_read` |
| 含义 | 读取审计、授权或运行历史 |
| 缺了会怎样 | `status: "denied"` · `denied: true` · `stamp: false` · exit 1 |
| 怎么授权 | `终端运行: python -m gbt_allinone auth grant --scope audit_read --ttl 600` |
| 或者 | `主人手写 store/auth_grants.jsonl 追加一行（格式见 auth_gate.SCOPES 与 README）` |
| 纪律 | `授权一次性消耗；AI 调用路径无权自行发放` |

**红线**：授权**只能主人在终端发**。缺授权就**如实报缺什么**，**不绕门、不找旁路、不改 `security/policy.py`、不给自己发授权**。
另注（静态读出、未验）：`policy.authorize` 里**受信主人会话走直通**分支 —— 本会话是非受信路径，所以看到的是"被门拒"。

---

## 4. 用法纪律（照做）

1. **调之前先静态查门**（`policy.evaluate`），别用"撞一次门"当发现手段。
2. **只读的位必须真跑一次再报**：`echo` / `count_words` / `record_grid`（除写盘分支）/ `account_registry`
   都是零作用域可直跑 —— **有返回字段就不许靠猜**。
3. **要授权的不许绕**：报 `missing_scopes` / `reason` / `how_to_grant` 原文，**本体读数写"未验"并说明缺哪个作用域**。
4. **`record_grid` 的 `emit + out` 按写操作对待**（门不拦 ≠ 只读）。
5. **不确定就复跑对比**：`record_grid` 的 `verify` 就是这一条的机器形态（`fingerprint == reparsed`）。

---

## 5. 🔴 报告层红线：读数先问「这是事实，还是我读错了地方」

三个**本域实测/可复现**的读错地方，三段都别再踩：

**① 授权被拒时，`cap` 打的是扁平错误信封 —— 要读顶层，不要读 `gbt_result`。**
实测 `run_task('audit_query', {})` 的顶层键是
`['denied','error','how_to_grant','kind','message','missing','note','ok','reason','result','scopes','status']`，
**`'gbt_result' in r` 为 `False`** —— 被门拒时根本不带 `gbt_result`。
所以 `denied` / `missing` / `scopes` / `how_to_grant` 全在**顶层**。
`five-dim.py` 已按此修过（源码注释 R-H299：改前只读 `r["gbt_result"]` ⇒ 门明明说"拒了"，
报表却打 `status: unknown · denied: false`，把"缺授权"读成"只是没跑通"）。
⇒ **判断"是不是被门拒"，看顶层 `denied` 与 `missing_scopes`，不看 `gbt_result`。**

**② 信封 `status:"ok"` ≠ 本体 `ok:true`。**
`record_grid` 的 `parse`（解析失败）与 `vocab`（超出词表）、`account_registry` 的 `validate`（有违规）
在这三种情形下**外层都是 `status:"ok"` · `stamp:true` · exit 0**，而**本体 `result.ok` 是 `false`**。
⇒ **只看退出码/外层状态 = 把"发现了问题"读成"一切都好"。** 本体 `ok` 与 `invalid`/`violations`/`outside` 才是结论。

**③ `omni list` 的 ✅ 是图鉴旗标算的，不查门 —— 本域就有一个假绿。**
`py -3.14 tools/codex-scripts/omni.py list --domain data` 实测把 **`audit_query` 也标成
「✅ 免卡无参可直跑」**，而门**当场拒了它**（要 `audit_read`）。
同一个域，`omni ask "看看审计日志里有什么"` 反而**标对了**（`🔒 不自动跑：要过授权门：audit_read`）——
因为 `ask` 查 `policy`，`list` 只查图鉴旗标（`enabled && safe && !requires_params && !needs_confirmation`）。
⇒ **✅ 只代表"图鉴说它 safe 且无参"，不代表"门放行"。判门用 `policy.evaluate` 或看 `ask` 的标注。**

---

## 6. 诚实账（未验清单 —— **不许改写成"能"**）

| # | 没验的东西 | 卡在哪 |
|---|---|---|
| 1 | `audit_query` 的**本体返回**（`total` / `sample`） | 缺 **`audit_read`**；授权只能主人在终端发，AI 无权自发 ⇒ 不绕门 |
| 2 | `record_grid` 的 `emit` + `out` **写盘分支** | 静态读出会写 `<仓>/gbt_allinone/store/record_grid/` ⇒ 不做出格的状态写入，**未执行** |
| 3 | `record_grid` 的 `emit` **不带 `out`** 的纯生成分支 | 只跑到"缺 records"的拒绝分支，未单独跑 |
| 4 | `record_grid` 的 `path`（框架内相对路径）输入形式 | 只跑了 `text` 内联形式 |
| 5 | `policy.authorize` 的**受信主人会话直通**分支 | 本会话是非受信路径，看到的是"被门拒"；CLI/GUI 主人会话行为未跑 |
| 6 | `account_registry` 的**真表读数分支** | `gbt_allinone/store/ai_accounts.json` 实测**不存在** ⇒ 只验到骨架回落分支 |
| 7 | `datakit` 的五条转换 op（`html2md` / `html2xlsx` / `xlsx2json` / `jsonfmt` / `csvmerge`） | 只真跑了 `status` 与 `tools`（op 表现读）；**没备真料就不许说转换验过**（2026-09-26 补录） |

**这份账与 §2 的"✅ 真跑通"是两回事**：§2 的 ✅ 都有上面的真实返回字段撑着；
本表 7 条**都没有**，不许在别处写成"能"。

---

## 7. 验收（做完怎么证明真的做了）

1. **机器复核**：
   `py -3.14 tools/codex-scripts/verify-distill.py --domain data --skill gbt-data`
   —— 它查：两份产物存在且**逐字节同哈希** / frontmatter 有 `name` + `description` /
   规程点名的能力位在图鉴里真存在 / **该域每个能力位都被点到**；
2. **五位逐个复跑**：只读的必须看到真字段（`echo` 的回显体 / `count_words` 的 `words,chars` /
   `record_grid` 的 `records`·`fingerprint` / `account_registry` 的 `source`·`violations`）；
   要授权的必须看到 `missing_scopes: ["audit_read"]`，**不许假装跑通**；
3. **两份 sha256 一致**（源稿 vs managed 安装件）。

---

## 8. 固化与出处

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-data/SKILL.md` |
| 本规程（装机） | `~/.openclaw-autoclaw/skills/gbt-data/SKILL.md`（本仓 AGENTS.md 指定的托管目录） |
| 能力位注册表（**唯一真相**） | `gbt_allinone/caps_registry.py`（这 5 条） |
| 分派实现 | `gbt_allinone/api.py`（`_run_benign` 里的 `echo`/`count_words`/`audit_query`；后段的 `record_grid`/`account_registry`） |
| 授权策略 | `gbt_allinone/security/policy.py`（`audit_query` → `audit_read`） |
| 行网格本体 | `gbt_allinone/record_grid.py` |
| 账号登记本体 | `gbt_allinone/tools/account_registry.py`（真表 `gbt_allinone/store/ai_accounts.json`，缺则回落 `gbt_allinone/docs/ai_accounts.skeleton.json`） |
| 图鉴数据 | `state/skill_atlas.json`（现扫产物，可 `omni build` 重建） |
| 人话落点 | `py -3.14 tools/codex-scripts/omni.py ask "统计一下这段文本有多少词"` → 落到 `count_words` |

**纪律**：能力不许只活在**进程内**（动态插件 / 运行中的服务）—— 一重启就没了。
真身必须是盘上文件，且落在**会被读取的目录**；写完必须**验证它真被认出来**。
