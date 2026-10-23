# 「CLI-Anything」深度蒸馏 → 原生能力 `cli_ify`

> 主人令 2026-10-16：「把这个深度分析蒸馏提炼出契合我们大模型的能力」
> 开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属

## 一、上游现读（**本轮真抓了原文**）

`raw.githubusercontent.com/HKUDS/CLI-Anything/main/README.md` → **HTTP 200 · 80,551 字**。

| 块 | 原文说法 | 我们的口径 |
|---|---|---|
| **The Agent-Software Gap** | “AI agents are great at reasoning but terrible at using real professional software”；现有三个坑：脆弱的 UI 自动化 · 能力残缺的 API · **dumbed-down reimplementations that miss 90% of functionality** | **包壳，不重写**（宜写死进判据） |
| **7 相流水线** | Analyze → Design → Implement → Plan Tests → Write Tests → Docs → Publish（代码分析到发 PyPI 全自动） | 对应我们的**命令化六步**（Plan/Write Tests 合并为第 6 步；Publish 落到第 4 步“登记”） |
| **CLI-Hub** | 社区 CLI 注册表：浏览 / 安装 / 更新 / 卸载 / 启动（`cli-hub install <name>`） | 本仓对应 **`state/cli-surfaces.json`**（现读 **12 条**） |

**本位只蒸馏工程思想，不搬代码与注册表内容。**

## 二、落成原生能力：`cli_ify`（第 310 位）

| op | 零票 | 干什么 |
|---|---|---|
| `gate` | ✅ | 三档选型：已有 CLI → 直用；只有 API → 包 CLI；只有 GUI → 走触手；**三个信号都没给 ⇒ fail-closed** |
| `plan` | ✅ | 六步计划（每步带 **对照上游 7 相** 与该留的 **evidence**） |
| `registry` | ✅ | 读 `state/cli-surfaces.json` + 按 status 分档；**文件不在就报「未读到」，不当空表绿** |
| `check` | ✅ | **C1~C4 自实现**（不 shell-out）：表可读 · name/entry/verbs 齐 · evidence 非空 · status 合法 |
| `gap` | ✅ | 说清三个坑与“为何不重写” |

```powershell
'{"op":"gate","name":"gimp","has_gui":true}' | py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap cli_ify --stdin
'{"op":"check"}'                      | py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap cli_ify --stdin
```

**本轮实测**：`gate → gui-only` · 缺信号 → `need_signals` · `plan` 上游 7 相对照完整 · `registry` 现读 **12 条** · `check` **违规 0** · 未知 op → `unknown_op`。

## 三、加固：为什么不能“自己写一个简版”

> 上游原话的工程结论：**焦位版重写会丢掉 90% 功能**；三个坑里最坑的就是这个。
> 所以本位把 `rule` 写死在返回里：**包壳，不重写**。

## 四、诚实边界

- 本位**只读**（零作用域）；登记表的写入不在本位（走现有写渠道）。
- 现有管理技能 `gbt-cli-ify` 已有一份蒸馏（选型闸+六步+登记表+C1~C4）；
  本位把它**可执行化**，并补上上游的 Gap / 7 相 / CLI-Hub 三块。
  ⚠️ 管理技能文件本位**未改**（仓规：不直接改管理技能）—— 要同步去那份，请主人一句话。

> 开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属
