# 92 · 吞噬 superpowers-zh：缺的不是能力，是"做法"

> 主人 2026-11-01：「看看有没有你缺失的东西，先吞噬强化一下自己」
> 来源：[paysssk-creator/superpowers-zh](https://github.com/paysssk-creator/superpowers-zh)（MIT，上游 [obra/superpowers](https://github.com/obra/superpowers)）

## 一、吞了什么

对方 20 个 skill，**全部吸收**到 `skills/superpowers/`，并挂成新能力位 `skills_hub`（第 376 位）：

`brainstorming` `writing-plans` `executing-plans` `test-driven-development` `systematic-debugging`
`verification-before-completion` `requesting-code-review` `receiving-code-review`
`dispatching-parallel-agents` `subagent-driven-development` `using-git-worktrees`
`finishing-a-development-branch` `mcp-builder` `workflow-runner` `writing-skills` `using-superpowers`
`chinese-code-review` `chinese-commit-conventions` `chinese-documentation` `chinese-git-workflow`

许可与归属保留：`skills/superpowers/LICENSE`（MIT，版权 jnMetaCode）+ 每个 SKILL.md 的 frontmatter 里加
`source:` / `upstream:` 两行。

## 二、缺口比对（名字 0 命中，功能有重叠）

按名字比：20 个 skill 在我们 375 位能力位里**一个都对不上**。
按**功能**比，其实不是"没有能力"，是"没有把做法写成可复用套路"：

| superpowers skill | 我们已有的对应能力位 | 差在哪 |
|---|---|---|
| `writing-plans` / `executing-plans` | `blueprint` / `orchestration` | 我们有"架构→蓝图→派遣"，缺"写计划前先澄清需求"的硬门 |
| `test-driven-development` | `tests/` 判据 + `truth_scan` | 有判据，缺"先写测试再实现"的强制顺序 |
| `systematic-debugging` | `root_fix` / `nav_etiology` | 能定位病因，缺"先复现再修、禁止猜"的流程 |
| `verification-before-completion` | `signature_guard` / `truth_scan` | 有校验器，缺"没跑过不许说完成"的收口 |
| `dispatching-parallel-agents` | `wf_*`（DAG 引擎） | 有并行执行器，缺"何时该拆并行"的判断 |
| `requesting/receiving-code-review` | `code_audit` / `sec_scan` | 有审计，缺"审查怎么提、怎么收"的礼节与模板 |
| `using-git-worktrees` | `git_read` / `repo_publish` | 有 git 只读，缺 worktree 工作法 |
| `mcp-builder` | `mcp_bridge` | 能连 MCP，缺"自己造 MCP server"的脚手架 |
| `chinese-*`（4 个） | `docs/` 纪律 + 署名守卫 | 有纪律，缺"中文提交/评审/文档"的具体口径 |

**结论：能力位是"手"，skill 是"做法" —— 这次补的是做法。**

## 三、怎么用（已可用）

```python
import gbt_allinone as gbt

gbt.run_task("skills_hub", {"op": "list"})                        # 22 个（20 吸收 + 2 原生）
gbt.run_task("skills_hub", {"op": "match", "query": "改代码 先写测试"})  # → TDD 排第一（3.2 分）
gbt.run_task("skills_hub", {"op": "get", "name": "brainstorming"})     # 取全文（4.2KB）
gbt.run_task("skills_hub", {"op": "verify"})                      # 体检：无重名
```

判据：`tests/test_skills_hub.py`（4 组 8 条全绿）。

## 四、故意不吞的（诚实边界）

| 对方有 | 为什么不要 |
|---|---|
| npm 包 + 18 款工具的插件清单（`.claude-plugin` / `.cursor-plugin` / `.opencode` …） | 那是**给别的工具做扩展包**的形态；我们的入口是 `run_task`，不需要再包一层 |
| 赞助商 / 官网 / 课程导流 | 与框架无关，不进仓 |
| 62 个 tests（他们自己的测试套） | 我们只吸收方法论；他们的测试是测他们打包器的 |
| 一键安装脚本 | 我们的安装是 `install.ps1` + `启动-GBT.cmd` |

## 五、固化

- 能力位：`skills_hub`（注册表 + api 分派 + 判据 + 文档 + 账本）
- 资产：`skills/superpowers/`（20 个 SKILL.md + LICENSE + README 说明）
- 判据：`tests/test_skills_hub.py`
- 账本：`orchestration.record('add','skills_hub', ...)`

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
