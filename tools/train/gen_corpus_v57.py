# -*- coding: utf-8 -*-
"""gen_corpus_v57 -- v56 逐字节不动 + 四组实战胶囊（主人点名补的三块 + 新增抓图）。

主人令（2026-10-17）：
  · 「showcase_ops 8op 和 forge_mastery 7op 的实战胶囊」（评测指出的语料偏度）
  · 「视觉能力看图片必须懂得把图片放大看细微的图片变化以及懂得修饰」
  · 「去精准抓取美图能力给她注入」
内容全部**现读真源**：
  · `showcase_ops` / `forge_mastery` 的每个 op 的签名与返回键（源码现读，不编）
  · `zimage_rewash` 的 upscale/reverse/rewash/denoise_table（源码现读）
  · `image_scout` 的三源/门槛/许可/署名/只读边界（本仓新位，源码现读）
纪律：v56 基础逐字节不动；只追加；manifest 记条数与来源。
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v56.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v57.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v57_manifest.json"


def _showcase_rows() -> list:
    return [
        ("showcase_ops 是什么、为什么要有它？",
         "作品解剖与展示（主人令 2026-10-16「让每一次的作品都能完美的展示能力」）：把一件作品拆成**能讲给别人听**的结构，"
         "并给出能过判据的自检。它不生产作品，它让作品**可被理解、可被复核**。全部走唯一门 `cap showcase_ops '{\"op\":...}'`。"),
        ("showcase_ops 的 check 返回什么？",
         "`check`：返回 kind / rules / doc —— 该位的**判据清单与用法**，用来先看清规则再动手（不是直接产出）。"),
        ("showcase_ops 的 concept 怎么用？",
         "`concept(idea)`：把一个点子变成可执行概念——返回 reason（为什么值得做）/ how（怎么做）/ kind / idea / "
         "rule（判据）/ examples（参照例）/ judges（自检项）/ source。点子模糊时先跑它。"),
        ("showcase_ops 的 frame/motion/parts 各管什么？",
         "三件拆解：`frame`（画框/构图：parts + rule + judges）· `motion`（动效/运动：rule + judges）· "
         "`parts`（部件分层：layers + rule + judges）。一帧一帧、一层一层、一动一动地解剖，别一句「好看」带过。"),
        ("showcase_ops 的 readout 与 selfcheck 区别？",
         "`readout`：把作品读数讲出来（how + judges）——给谁看、看什么值；`selfcheck`：自检步骤（steps + judges）——"
         "照单逐条过，红一条就不算完。"),
        ("showcase_ops 的 route 怎么选路？",
         "`route(idea)`：按点子给出 map（走哪条解析路线）与 direct（直达结论）——先路由再拆解，别上来就写。"),
        ("showcase_ops 的 run 分派哪些 op？",
         "`run(op)` 分派：concept / parts / frame / motion / readout / selfcheck / check / route —— "
         "同一入口按 op 进不同分析步；未知 op 会被拒（不猜）。"),
        ("showcase_ops 的专业验收口径是什么？",
         "三问：① 结构讲清了吗（frame/parts/motion 各自说得出）② 展示给谁、看什么读数（readout）③ 自检过了吗"
         "（selfcheck 全绿）。缺一项 = 展示不合格，不许用「整体感觉」替代结构。"),
    ]


def _forge_rows() -> list:
    return [
        ("forge_mastery 是什么？",
         "节点即触手 · 专业生产与自我递归（主人令 2026-10-16）：把「专业生产」拆成可执行步骤 —— "
         "plan（计划）→ roles（谁干）→ judge（评审）→ improve（改进）→ recurse（自我递归），每步带判据。"),
        ("forge_mastery 的 plan 返回什么？",
         "`plan(goal, tier)`：reason / how / kind / goal / tier / steps（分步）/ graph_rule（图规则）/ native_run（怎么跑本机原生件）。"
         "接活先 plan：说清目标、层级、步骤与用什么原生件。"),
        ("forge_mastery 的 roles 是干什么的？",
         "`roles(node_type)`：返回 rule / each_tentacle（每个触手域的角色）/ how_to_use / source —— "
         "把工作分给**专业角色**（不是全塞给一个脑子），并说清怎么用。"),
        ("forge_mastery 的 judge 怎么评作品？",
         "`judge(artifact, tier)`：reason / axes（评分轴）/ rule / judges —— 按层级给多轴评分；"
         "只给「好/不好」没有 axes 与理由 = 不合格评审。"),
        ("forge_mastery 的 improve 怎么改？",
         "`improve(artifact, gaps)`：按缺口给 actions（可执行动作）与 anti_pattern（不许犯的反面模式）—— "
         "改要指名**改哪、怎么改、别学谁**。"),
        ("forge_mastery 的 recurse 怎么自我递归？",
         "`recurse(goal, max_rounds)`：给出 loop（轮次）/ ledger（账本）/ guard（护栏）/ cap_note —— "
         "递归必须有上限与账本，防止自嗨空转；每轮留痕再进下一轮。"),
        ("forge_mastery 的专业生产闭环是什么？",
         "固定闭环：**plan（计划）→ roles（分角色）→ judge（多轴评审）→ improve（按缺口改）→ recurse（有上限递归）**，"
         "每步带 rule/judges；跑完必须留账本。缺任何一环 = 不专业。"),
    ]


def _vision_rows() -> list:
    return [
        ("看图时怎么「放大看细微变化」？",
         "固定四步：① 先看整图定性（主体/构图/风格）→ ② **裁切目标区域**（坐标或图文框）→ ③ 对裁切块做"
         "**放大**（`cap zimage_rewash '{\"op\":\"upscale\",\"src\":\"<图>\",\"factor\":2}'`，lanczos+unsharp）→ "
         "④ 放大后再看边缘、文字、接缝、手指五官、噪点与色偏。结论必须写「在哪块、看到什么」，不许「整体感觉」。"),
        ("怎么比对两张图的细微差异？",
         "三路并用：① 同区域裁切**并排放大**对比；② 看关键锚点（文字/边角/关节/水印位置）是否位移；"
         "③ 有差值工具就出差分图，没有就用放大裁切逐块核。差异要报「位置 + 变化量 + 是否可接受」。"),
        ("修饰（洗图）能力有哪些真 op？",
         "`zimage_rewash`（洗图流水线，零依赖）：`upscale`（ffmpeg lanczos + unsharp 放大）· `reverse`（看图反推提示词）· "
         "`rewash`（按风格/去噪强度重绘）· `denoise_table`（降噪档位表）· `status`。修饰顺序："
         "先 reverse 拿到提示词 → rewash 重绘 → upscale 放大锐化；每步落到独立文件，别覆盖原图。"),
        ("修饰到什么程度算到位？",
         "看四点：① 结构不崩（脸/手/边缘不糊不歪）② 细节回来（锐化不过冲、噪点不放大）③ 色彩一致（不偏色）"
         "④ 尺寸与用途匹配（放大倍数够用即可）。改完**放大复看**关键区域，再给「改了什么 + 依据」。"),
        ("视觉能力位现读有哪些、各自干什么？",
         "`vision`（识别入口）· `vision_loop`（原生四觉闭环：看 → 判 → 动 → 复看）· `vision_print`（看到什么以代码打印）· "
         "`vlx_flow`（流式观察 + 两层记忆）· `vision_grounding`（L1 结构层定位）。要「看得准」就走 "
         "vision_loop/vision_print，要「记住变化」走 vlx_flow。"),
        ("看图放大后要留下什么证据？",
         "至少留：原图路径 + 裁切区域（坐标）+ 放大倍数与实现（lanczos/unsharp 参数）+ 复看结论（哪块、什么问题、"
         "建议怎么修饰）。没有这几样的「看图结论」= 不可复核。"),
    ]


def _scout_rows() -> list:
    return [
        ("美图精准抓取（image_scout）怎么用？",
         "`cap image_scout '{\"op\":\"search\",\"query\":\"golden hour portrait\",\"min_width\":2000,\"min_height\":1200,"
         "\"aspect\":\"wide\",\"license\":\"cc0\"}'`：多源找图（Openverse 免钥匙 / Unsplash / Pexels 需钥匙），"
         "按质量与许可门槛筛，返回**候选直链 + 尺寸/比例 + 许可 + 署名行**；**不下载字节**。"),
        ("image_scout 的 curate 怎么排序？",
         "`curate(items, k, bias_ratio, prefer_license)`：分数 = 像素量×0.5 + 比例契合×0.8 + 许可优先×0.25；"
         "bias_ratio 传你要的宽高比（例如海报 0.75、横屏 1.78），prefer_license 传 cc0 优先。"),
        ("抓图的许可与署名怎么守？",
         "三条硬规矩：① 只用明确许可（CC0/CC-BY/Unsplash/Pexels License）；② 逐图带**署名行**"
         "（题目 by 作者 · 许可 · 原页）；③ 商用前看清许可条款，拿不准就换图而不是赌。"),
        ("抓图 → 修饰 → 落盘的标准链路？",
         "① `image_scout search` 抓候选（带许可/署名）→ ② `image_scout curate` 挑最佳 → "
         "③ `zimage_rewash upscale/rewash` 修饰 → ④ 写面能力位落盘（filesystem_write 票）→ "
         "⑤ 回读文件核对尺寸与 sha，并把署名行一起写进交付说明。"),
    ]


def main():
    base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    base_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    adds = ([("作品展示·showcase_ops", q, a) for q, a in _showcase_rows()]
            + [("专业生产·forge_mastery", q, a) for q, a in _forge_rows()]
            + [("视觉放大·修饰", q, a) for q, a in _vision_rows()]
            + [("美图精准抓取", q, a) for q, a in _scout_rows()])
    rows = list(base) + [{"instruction": q, "output": a, "family": fam, "source": "v57-" + fam}
                         for fam, q, a in adds]
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.parent.mkdir(parents=True, exist_ok=True)
    MAN.write_text(json.dumps({
        "gen": "v57", "parent": "v56", "count": len(rows), "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(), "base_count": len(base),
        "base_sha256": base_sha, "base_unchanged": hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha,
        "appended_showcase": len(_showcase_rows()), "appended_forge": len(_forge_rows()),
        "appended_vision": len(_vision_rows()), "appended_scout": len(_scout_rows()),
        "directives": ["主人 2026-10-17：「showcase_ops 8op 和 forge_mastery 7op 的实战胶囊」",
                       "主人 2026-10-17：「视觉能力看图片必须懂得把图片放大看细微的图片变化以及懂得修饰」",
                       "主人 2026-10-17：「去精准抓取美图能力给她注入」"],
        "why": "补三块偏度：showcase 8op + forge 7op 实战胶囊（op 面现读源码）· 视觉放大/修饰链（zimage_rewash 现读）· image_scout 抓图链路",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v57：%d 条（基底 v56 %d + 追加 %d：showcase %d · forge %d · 视觉修饰 %d · 抓图 %d）· %d 字节 · sha %s"
          % (len(rows), len(base), len(adds), len(_showcase_rows()), len(_forge_rows()),
             len(_vision_rows()), len(_scout_rows()), len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  基底 sha 未变:", hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
