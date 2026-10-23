# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 剪辑硬规则检查器（edit_rules）

蒸馏自 `browser-use/video-use`（MIT · Owner 2026-09-22 定点蒸馏）的那 9 条硬规则。
它自己写明这些是「**deviation produces silent failures**」的地方 ——
**错了不会报错，只会出个"看着还行但其实是坏的"片**。
那正是我们最该防的**假执行**，所以把它做成机检。

═══ 诚实设计：分两类，不假装全能 ═══
  · **可机检**（只看命令/filtergraph 就能判）：ED-1 / ED-2 / ED-3 / ED-4
  · **需人工**（判据不在命令里）：ED-5 / ED-6 / ED-7 / ED-8 / ED-9
    —— 这几条的判据要**转录数据**（词边界、时间戳漂移）或**运行历史**（有没有重转），
       **一条 ffmpeg 命令里根本看不出来**。硬凑成正则只会产出假警报。
    ⇒ 所以它们照样列出来（**不隐身**），但标 `manual` 并写明**为什么机检不了**。

每条带**稳定规则号**（沿用 skill_vetting 那套），便于讨论、抑制、对账。
"""
from __future__ import annotations

import argparse
import json
import re

_IMPL_VERSION = "1.0"

# 字幕/overlay/拼接 相关的滤镜名（用于判顺序与形态）
_SUB_FILTERS = ("subtitles", "ass", "srt", "drawtext")
_OVERLAY_FILTERS = ("overlay",)


def _positions(cmd: str, names: tuple) -> list:
    """返回这些滤镜名在命令里出现的字符位置（按出现顺序）。"""
    out = []
    for n in names:
        for m in re.finditer(r"\b" + re.escape(n) + r"\b", cmd, re.I):
            out.append((m.start(), n))
    return sorted(out)


def check(cmd: str) -> dict:
    """查一条 ffmpeg 命令。返回 {ok, findings[], manual[], rules[]}。

    `ok=False` 只代表**发现了可机检的违规**；`manual` 里的是**要人看的**，
    不代表通过 —— **不把"没查"说成"没问题"**（这是本轮最重要的一条纪律）。
    """
    c = str(cmd or "")
    findings, manual, passed = [], [], []

    # ── ED-1 字幕必须在所有 overlay 之后 ──
    subs = _positions(c, _SUB_FILTERS)
    ovls = _positions(c, _OVERLAY_FILTERS)
    if subs and ovls:
        first_sub = subs[0][0]
        later_ovl = [p for p, _ in ovls if p > first_sub]
        if later_ovl:
            findings.append({"rule": "GBT-ED-1", "what": "字幕没有放在 overlay 之后",
                             "why": "overlay 会盖住字幕（静默失败：字幕被吃掉）",
                             "evidence": f"第一个字幕滤镜在位置 {first_sub}，"
                                         f"其后的 overlay 在 {later_ovl[:3]}"})
        else:
            passed.append("GBT-ED-1")
    else:
        manual.append({"rule": "GBT-ED-1", "why": "命令里没有字幕或没有 overlay，无需判顺序"})

    # ── ED-2 分段抽取 + 无损 -c copy 拼接，不要单趟 filtergraph ──
    has_copy = bool(re.search(r"-c\s+copy|-codec\s+copy", c, re.I))
    # 单趟 filtergraph 的征兆：一条命令里既 trim/select 又 concat 又重编码
    seg_like = len(re.findall(r"\b(trim|atrim|select)\s*=", c, re.I))
    has_concat = bool(re.search(r"\bconcat\b", c, re.I))
    if seg_like >= 2 and has_concat and not has_copy:
        findings.append({"rule": "GBT-ED-2", "what": "像是单趟 filtergraph 拼接（未用 -c copy）",
                         "why": "单趟会重新编码 ⇒ 画质掉（静默失败：看着还行，其实糊了）",
                         "evidence": f"trim/select × {seg_like} + concat，但没有 -c copy"})
    elif has_copy and has_concat:
        passed.append("GBT-ED-2")
    else:
        manual.append({"rule": "GBT-ED-2",
                       "why": "没有 concat 或多段拼接征兆，不适用（单段不需要拆分拼接）"})

    # ── ED-3 每个接缝 30ms 音频淡入淡出 ──
    if has_concat:
        fades = len(re.findall(r"\bafade\b", c, re.I))
        if fades == 0:
            findings.append({"rule": "GBT-ED-3", "what": "有拼接但没有 afade",
                             "why": "接缝会爆音（静默失败：音频咔一下）",
                             "evidence": "concat 存在，afade 出现 0 次"})
        else:
            passed.append("GBT-ED-3")
    else:
        manual.append({"rule": "GBT-ED-3", "why": "没有拼接，接缝淡变不适用"})

    # ── ED-4 overlay 用 setpts=PTS-STARTPTS+T/TB 对齐窗口起点 ──
    # 🔴 2026-09-22 一个字母的锅：原来搜的是 "starpts"，而 STARTPTS 的拼写是
    #    s-t-a-r-**t**-p-t-s ⇒ 少一个 t ⇒ 永远匹配不上 ⇒ 对合规命令报假阳性。
    #    教训：**拼写类判据必须打印 repr 核对**，光看"应该匹配"会一直错下去。
    if ovls:
        # 只看 overlay 之前的 setpts（就近作用域）
        first_ovl = ovls[0][0]
        head = c[:first_ovl]
        if "setpts" in head.lower() and "startpts" in head.lower():
            passed.append("GBT-ED-4")
        else:
            findings.append({"rule": "GBT-ED-4", "what": "overlay 前没有 setpts=PTS-STARTPTS",
                             "why": "overlay 会从错误时刻开始（静默失败：动画提前/延后出现）",
                             "evidence": "overlay 之前的片段里没有 setpts=…STARTPTS"})
    else:
        manual.append({"rule": "GBT-ED-4", "why": "没有 overlay，不适用"})

    # ── 需人工的四条：判据不在命令里 ──
    manual += [
        {"rule": "GBT-ED-5", "why": "主 SRT 是否用**输出时间轴**偏移 —— 要看 SRT 内容与"
                                    "segment 偏移，命令里看不出"},
        {"rule": "GBT-ED-6", "why": "切点是否**吸附到词边界** —— 要有词级转录才知道词边界在哪"},
        {"rule": "GBT-ED-7", "why": "切边 padding 是否 30–200ms —— 要看切点与词边界的距离，"
                                    "要有时间戳（原文：Scribe 漂移 50–100ms，padding 吸收它）"},
        {"rule": "GBT-ED-8", "why": "是否**词级逐字** ASR（而非 SRT/短语模式）—— "
                                    "取决于调用转录时的参数，不在这条命令里"},
        {"rule": "GBT-ED-9", "why": "逐字稿是否**按源缓存** —— 要看运行历史，命令里看不出"},
    ]

    return {"ok": not findings, "version": _IMPL_VERSION,
            "findings": findings, "passed": passed, "manual": manual,
            "counts": {"findings": len(findings), "passed": len(passed),
                       "manual": len(manual)},
            "note": ("`manual` 里的是**要人看的**，**不代表通过** —— "
                     "不把「没查」说成「没问题」。")}


def report(cmd: str) -> str:
    r = check(cmd)
    L = ["# 剪辑硬规则检查", "", f"- 命令：`{cmd[:200]}`",
         f"- 结论：{'✔ 可机检部分全过' if r['ok'] else '✘ 有可机检违规'}", "",
         "## 可机检的违规", ""]
    L += [f"- `{f['rule']}` **{f['what']}**\n  - 为什么是坑：{f['why']}\n  - 证据：{f['evidence']}"
          for f in r["findings"]] or ["- （无）"]
    L += ["", "## 可机检且已通过", ""]
    L += [f"- `{p}`" for p in r["passed"]] or ["- （无）"]
    L += ["", "## 需人工（**判据不在命令里，不代表通过**）", ""]
    L += [f"- `{m['rule']}`：{m['why']}" for m in r["manual"]]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GBT 剪辑硬规则检查器")
    ap.add_argument("cmd", nargs="?", help="ffmpeg 命令（不传则从 stdin 读）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    cmd = a.cmd
    if not cmd:
        import sys
        cmd = sys.stdin.read()
    r = check(cmd)
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else report(cmd))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
