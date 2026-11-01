# 99 · 吞噬蒸馏：Agent Skills 规范（GSAP AI Skills 那一套）

> 主人 2026-11-01 看到 GSAP AI Skills（[greensock/gsap-skills](https://github.com/greensock/gsap-skills)）说
> 「看到这些 APP 面板真闹心，来强化一遍自己」，随后给了指令：**吞噬 · 蒸馏 · 提炼**。
> 我们**不搬别人的技能内容**，只把「技能怎么长、怎么验、怎么装」这套规矩吸收进来。

## 一、对方是什么（看清楚了再动）

| 项 | 事实 |
|---|---|
| GSAP AI Skills | GreenSock 官方 AI 技能包：教 agent 正确用 GSAP（timeline / ScrollTrigger / plugin / React / Vue…） |
| 目录 | `skills/`（每个技能一目录 + SKILL.md）、`examples/`、`.claude-plugin/`、`.cursor-plugin/`、`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` |
| 规范 | 背后是 [agentskills.io/specification](https://agentskills.io/specification)：SKILL.md + YAML frontmatter（name / description / license / compatibility / metadata / allowed-tools），可选 `scripts/` `references/` `assets/`，渐进披露 |
| 分发 | 40+ 客户端（Claude Code / Cursor / Codex / Copilot / Windsurf…）按同一目录约定发现技能 |

## 二、缺口比对（我们原来缺什么）

我们的 `skills_hub` 早就有：列 / 取 / 匹配 / 体检（当时 22 个技能，含 superpowers 汉化那批；2026-11-01 吸 gsap 后 **23** 个）。
缺的是**规范的另外半截**：

| 规范要求 | 我们原来 | 现在 |
|---|---|---|
| name 命名硬约束（≤64、a-z0-9-、不许首尾/连续连字符、必须=目录名） | 没校验 | `op=validate` 逐条查 |
| description 1..1024 且写"做什么+何时用" | 只存不查 | 长度/空值硬校验 |
| compatibility ≤500、metadata 为映射、allowed-tools 字符串 | 不认 | 校验 + 原样保留 |
| 目录结构 `scripts/ references/ assets/` | 不认 | `op=read` 渐进读取（防路径穿越） |
| 打包成 `<name>/SKILL.md` 结构 | 没有 | `op=pack` 出 zip |
| 装进别的 agent 的 skills 目录 | 没有 | `op=install`（claude/codex/agents 或任意 dir；默认 dry_run，真装过 `filesystem_write` 门） |

## 三、闭环判据（`tests/test_skills_spec.py`，15 条全绿）

```
[1] validate   22 个 skill 全合规（clean，0 errors）
[2] validate   故意造坏：name="Bad Name" + 空 description → broken，逐条报错
[3] pack       brainstorming → state/tmp/skill-packs/brainstorming.zip（4,692 B，内含 brainstorming/SKILL.md）
[4] install    dry_run=true 不写盘；owner 会话下 dry_run=false → 目录里出现 SKILL.md（过写盘门）
[5] read       读到 SKILL.md 正文；file="../../../README.md" → 越界被拒
```

## 四、怎么用

```python
import gbt_allinone as gbt
gbt.run_task("skills_hub", {"op": "validate"})                                  # 合规体检
gbt.run_task("skills_hub", {"op": "pack", "name": "brainstorming"})             # 打包
gbt.run_task("skills_hub", {"op": "install", "name": "brainstorming",
                            "target": "claude"})                                # 演练（默认 dry_run）
gbt.run_task("skills_hub", {"op": "install", "name": "brainstorming",
                            "target": "claude", "dry_run": False})              # 真装（需写盘门）
gbt.run_task("skills_hub", {"op": "read", "name": "brainstorming",
                            "file": "references/notes.md"})                      # 渐进读取
```

装好后对方客户端（Claude Code / Cursor / Codex …）按它们的 skills 目录约定就能发现 ——
**技能是同一份，入口不同**。

## 五、拒收（以及为什么）

| 对方的东西 | 拒收理由 |
|---|---|
| `skills-ref`（官方参考实现：parser/validator/models/prompt 一整套库） | **重复**：我们的 `skills_hub` 已有解析/匹配，再搬一套两套解析器打架；只借它的规范口径 |
| `.claude-plugin/` `.cursor-plugin/`（marketplace + plugin.json） | 平台分发壳，与 `run_task` 入口无关 |
| `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `copilot-instructions.md` | 客户端各自的提示词适配层，不属框架本体 |
| GSAP 技能正文（动画库用法） | 是别人的领域知识；真要用时按需单独吸成一个 skill，不混进框架能力 |
| `examples/`（Nuxt/React 示例） | 领域示例代码，不进仓 |

## 六、顺手带回的"纪律"

1. **技能 = 目录 + SKILL.md**，正文写给模型看，元数据写给客户端发现 —— 和我们"能力位=手，skill=做法"完全同构；
2. **渐进披露**：默认只读 frontmatter，正文按需读，`references/` 不加载只引用（省 context）；
3. **合规可验**：任何"规范"如果没有 `validate` 就是口号 —— 所以这条必须配判据。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
