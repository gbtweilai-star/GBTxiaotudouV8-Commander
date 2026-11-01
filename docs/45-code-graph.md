# 45 · 补上 `code_graph`：一个"注册了、分派了、模块却不存在"的能力位

> 起于 2026-10-31 的逐项核对：`run_task("code_graph", …)` 当场报
> `cannot import name 'code_graph' from 'gbt_allinone.tools'`。
> 2026-11-01 按它自己注册表里的 desc 逐条实现，并顺手挖出一个更隐蔽的坑（BOM）。

---

## 一、病根

| 层 | 状态 |
|---|---|
| 注册表 | ✅ `"code_graph"` 有条目，desc 写得很细（AST → SQLite → FTS5 → 结构化查询） |
| api 分派 | ✅ `if kind == "code_graph": … _cg.run_op(...)` |
| 实现文件 | ❌ **`gbt_allinone/tools/code_graph.py` 不存在** |

⇒ 三处只齐了两处。这种"半截能力位"最坑：`cap_self has code_graph` 会说"有"，
真调就 ImportError —— 正是主人反复说的"说的和做的不是一回事"。

## 二、补上的实现（按 desc 一条条对）

`gbt_allinone/tools/code_graph.py`，纯标准库（sqlite3 + ast），零新依赖：

| 表 | 字段 |
|---|---|
| `files` | path / lang / mtime / size / sha / exact / at |
| `symbols` | name / kind / file / line / signature / doc / exact |
| `edges` | src / src_file / src_line / dst / kind(call/import) / file / line |
| `symbols_fts` | FTS5（名 + 签名 + 文档），中文可检索 |

op：`index` / `find` / `callers` / `callees` / `summary` / `stats`。

三条纪律照 desc 落地：**不索引第三方与生成代码**（node_modules/.pylibs/vendor/mirror_space）、
**解析失败如实记 `未解析`**（不静默跳过）、**只写 `state/code_graph.sqlite`**。

## 三、实测（本机，2026-11-01）

```
index gbt_allinone（全包）：53.3s → 665 文件 / 10,137 符号 / 98,280 条边 / 未解析 0
find "route"              → 5 条命中，带 file:line 与签名
callers "run_task"        → app.py:160 / 178 / 183 …（调用方可指回）
stats                     → exact=1（ast 精确） vs exact=0（JS 正则粗解析，如实标）
```

## 四、顺手挖出的坑：**BOM 会让 ast 直接 SyntaxError**

首轮 index 报 4 个文件"解析失败"，全是同一句：
`SyntaxError: invalid non-printable character U+FEFF (…, line 1)`。

查下去：这些 .py 的开头带了 **UTF-8 BOM**（`\xEF\xBB\xBF`）。Python **导入**时会自动跳过 BOM，
所以运行时毫无症状；但任何**把源码读成文本再 ast.parse** 的工具（本仓的 cross_scan、
hygiene 的 live_stems、我新写的 code_graph）都会当场失败 —— **静默地少覆盖一批文件**。

两处一起修：

1. **清源**：全仓扫出 10 个带 BOM 的 .py，全部剥掉（BOM 对 Python 无语义）；
2. **加固**：code_graph 统一用 `utf-8-sig` 读，**再遇到 BOM 也不会挂**。

修后 index：**未解析 0**，`commander.route` 这类之前被跳过的符号也进库了。

> 这 10 个 BOM 是我自己前几轮用 PowerShell `Set-Content -Encoding utf8` 打补丁时带进去的
> （PS 5.1 的 utf8 会写 BOM）。记在这里：**改完 .py 要用无 BOM 写法**，否则会污染整仓的静态分析。

## 五、判据

`tests/test_code_graph.py`（9 条）：

- 建索引 ok、符号 > 0、**0 个解析失败**；
- `find` 命中带 `file:line`；`callers` / `callees` / `summary` 结构正确；
- **BOM 容忍**：现场造一个带 BOM 的 .py，必须解析成功且函数进库；
- 走唯一门 `run_task("code_graph", {"op":"stats"})` 可用（不再 ImportError）。

## 六、这一轮之后

| 检查 | 结果 |
|---|---|
| 八份契约测试 | **全绿**（code_graph / inventory_checkout / alerts_sockets / omni_open_diff / omni_open / cap_self / pulse_core / commander_trunk） |
| `selfscan` | clean |
| `cap_self verify` | 354 = 354 = 354（注册表=快照=分派） |
| `code_graph` | 从"断链"变成"可用，且 0 未解析" |

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
