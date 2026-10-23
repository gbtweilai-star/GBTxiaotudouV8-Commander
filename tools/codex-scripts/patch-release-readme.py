# -*- coding: utf-8 -*-
"""把三份新文档 / 两张新图 / 三段读数接进开源仓 README 与 CHANGELOG。

为什么用脚本而不是手点：README 是 CRLF，edit 工具按 LF 匹配会“找不到”（本会话已踩），
脚本里先归一化换行再替换，并且**每处替换都断言真的命中**（没命中就报错退出，不静默跳过）。
用法：py -3.12 tools/codex-scripts/patch-release-readme.py
"""
import pathlib
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
REL = ROOT / "outputs" / "open-source-release"


def load(p: pathlib.Path) -> str:
    t = p.read_text(encoding="utf-8")
    return t.replace("\r\n", "\n")


def save(p: pathlib.Path, t: str) -> None:
    p.write_text(t, encoding="utf-8", newline="\n")


def sub(text: str, old: str, new: str, tag: str) -> str:
    if old not in text:
        print("!! 没命中：", tag)
        sys.exit(2)
    print("   命中：", tag)
    return text.replace(old, new, 1)


readme = load(REL / "README.md")

readme = sub(readme, "## 实测证据（四张图，全部真跑，不是示意图）",
             "## 实测证据（六张图，全部真跑，不是示意图）", "证据节标题")
readme = sub(
    readme,
    "| ![链路](assets/fig-chain.png) | **整链通** | 本地框架→云插件→端点→流式，五段真跑全绿 |\n\n"
    "细节页：[能力自证](docs/07-capability-proof.md) · [并发爆发力](docs/08-concurrency.md) · "
    "[镜像多维度空间](docs/09-mirror-space.md) · [真实回执](docs/06-showcase.md)",
    "| ![链路](assets/fig-chain.png) | **整链通** | 本地框架→云插件→端点→流式，五段真跑全绿 |\n"
    "| ![GBT天真](assets/fig-tianzhen.png) | **不装 ComfyUI 也能跑它的契约** | 原生算子 **27**"
    "（18 个与 ComfyUI 同名同契约）· 契约面 1495 · 校验正例过、反例被抓 |\n"
    "| ![多域监控](assets/fig-monitor.png) | **改一处不坏别处** | 29 域 236 位逐位真调："
    "**221 通过 / 15 要票 / 回归 0 / 修好 0** |\n\n"
    "细节页：[能力自证](docs/07-capability-proof.md) · [并发爆发力](docs/08-concurrency.md) · "
    "[镜像多维度空间](docs/09-mirror-space.md) · [GBT天真](docs/10-gbt-tianzhen.md) · "
    "[五维合一](docs/11-five-dim.md) · [多域监控](docs/12-multidomain-monitor.md) · "
    "[真实回执](docs/06-showcase.md)",
    "证据表两行 + 细节页链接",
)

# 在「镜像多维度空间」一节之后插入 GBT天真 / 五维合一 / 多域监控 三节
anchor = "## 60 秒上手"
block = """## GBT天真：不装 ComfyUI，也跑得动 ComfyUI 的节点契约

**GBT天真**是本项目给「触手自己的 ComfyUI 能力」取的名字（能力位 `comfy_native`）。
一句话：**契约用 ComfyUI 的（节点名 / socket 名），算子用我们自己的（纯 CPU）。**
所以一张 `workflow.json` 可以直接写 ComfyUI 的节点名，而机器上**不需要装 ComfyUI、不需要起 8188、不需要 GPU**。

| 项 | 现读（2026-10-21） |
|---|---:|
| 原生算子 | **27** |
| 其中与 ComfyUI **同名同契约** | **18** |
| 对齐的契约面节点（秋叶版快照） | **1495** |
| 原生覆盖率 | **1.2%**（小，但不修饰：1477 个未接按原因分类列出） |
| 离线校验 | 正例（ComfyUI 写法）通过 · 反例（未知节点/缺必填/成环）逐条被抓 |
| 写面真跑 | 3 节点全过闸，产物含 sha256；坏图 fail-closed（一件产物都不落） |

> 为了让"ComfyUI 的图能直接跑"，当场修掉三处契约失真（`image` vs `path`、`out` 是否必填、连边按 socket 名取产物）——
> 过程与读数全在 **[docs/10-gbt-tianzhen.md](docs/10-gbt-tianzhen.md)**。

---

## 五维合一：一句话进去，route → execute → verify → health 一条链出来

```mermaid
flowchart LR
    G["人话 goal"] --> R["① route<br/>语义路由选落点"]
    R --> E["② execute<br/>万能插执行（过同一道门）"]
    E --> V["③ verify<br/>触手肉眼：抓帧 + 指纹"]
    V --> H["④ health<br/>五维自检评分"]
    H --> O["回执：chain.* + elapsed_s"]
```

- **顺序串链，不是星形**：route 的 `best.kind` 喂给 execute；
- **执行一律走 `run_task`**：要票的位当场 `denied` + `missing_scopes`；
- **降级自曝**：语义路由不可用时 `path=heuristic` · `degraded=true` · 写明原因，绝不假装没降级；
- 五条真跑回执（含两条**被门挡住**的完整拒绝回执）：**[docs/11-five-dim.md](docs/11-five-dim.md)**。

---

## 多域监控：改一处，整面复查

> 最难听的质疑是「修一处坏一处，你怎么知道你只修了那一处？」——这页就是答案。

```
29 个域 · 236 位只读位逐位真调 · 用时 306.2s
通过 221 · 未通过 15（**全部是门拒绝，没有一条是失败/超时**）· 未跑 105（写口/需参数）
回归 0 · 修好 0   ← 立完基线后我改了三处代码，整面重跑一条没变
```

- 15 条"未通过"按缺的票点名：`deploy_publish` 4 · `process_execute` 4 · `external_llm` 2 · `device_control` 2 · `data_export` 1 · `privacy_read` 1 · `audio_output` 1；
- `--strict` 有回归就非零退出；读不到基线**报"没有基线可比"并非零退出**，不假装全绿；
- 方法与逐域读数：**[docs/12-multidomain-monitor.md](docs/12-multidomain-monitor.md)**。

---

"""
readme = sub(readme, anchor, block + anchor, "插入三节（GBT天真/五维合一/多域监控）")

# 仓库结构补三份文档 + 三份读数
readme = sub(
    readme,
    "│   ├── 07-capability-proof.md ← 341 位逐位真调（221 位通过 / 15 位只读要票 / 79 位写口）\n"
    "│   ├── 08-concurrency.md      ← 触手并发爆发力（4096 路零失败，瓶颈在审计写盘）\n"
    "│   └── 09-mirror-space.md     ← 镜像多维度空间（先排练，再一次性晋升）",
    "│   ├── 07-capability-proof.md ← 341 位逐位真调（221 位通过 / 15 位只读要票 / 79 位写口）\n"
    "│   ├── 08-concurrency.md      ← 触手并发爆发力（4096 路零失败，瓶颈在审计写盘）\n"
    "│   ├── 09-mirror-space.md     ← 镜像多维度空间（先排练，再一次性晋升）\n"
    "│   ├── 10-gbt-tianzhen.md     ← GBT天真（27 原生算子 / 18 个与 ComfyUI 同名同契约）\n"
    "│   ├── 11-five-dim.md         ← 五维合一（route→execute→verify→health 五条真跑回执）\n"
    "│   └── 12-multidomain-monitor.md ← 多域监控（29 域 236 位 / 基线 + diff / 回归 0）",
    "仓库结构 docs",
)
readme = sub(
    readme,
    "│   ├── concurrency-bench.json ← 并发台架原始读数\n"
    "│   └── mirror-space-live.json ← 镜像只读五步读数",
    "│   ├── concurrency-bench.json ← 并发台架原始读数\n"
    "│   ├── mirror-space-live.json ← 镜像只读五步读数\n"
    "│   ├── gbt-tianzhen-live.json ← GBT天真 live 读数（算子/契约/校验/写面真跑/流水）\n"
    "│   ├── five-dim-live.json     ← 五维合一 live 回执（含被门挡住的完整拒绝）\n"
    "│   └── multidomain-monitor-live.json ← 多域监控 live 读数（逐域 + diff）",
    "仓库结构 data",
)
readme = sub(readme, "├── assets/                    ← 架构图 · 域分布 · 四张实测证据图（png）",
             "├── assets/                    ← 架构图 · 域分布 · 六张实测证据图（png）", "仓库结构 assets")

# 诚实声明补两条
readme = sub(
    readme,
    "**已公开且可复核**：能力位全量清单（341 位）、评测方法、评测读数（含未过项）、部署路径、运行时的门与账设计。",
    "**已公开且可复核**：能力位全量清单（341 位）、评测方法、评测读数（含未过项）、部署路径、运行时的门与账设计、\n"
    "GBT天真的算子/契约现读读数、五维合一的五条真跑回执、多域监控的逐域读数与基线 diff。\n\n"
    "**还有两条要说清**：\n\n"
    "1. **GBT天真只覆盖契约面的 1.2%**（18/1495）：重生成与模型面 359 个、控图检测面 290 个要权重/GPU，本机没有；\n"
    "   传统算法面还有 809 个「可原生但没接」。**别把「能用 ComfyUI 的节点名写图」读成「ComfyUI 的节点全能跑」。**\n"
    "2. **多域监控只测 236/341 位**（只读且无需参数的那批）：105 位写口/需参数位不跑、也不假装跑过。",
    "诚实声明补两条",
)

save(REL / "README.md", readme)
print("README 已更新 →", REL / "README.md")
