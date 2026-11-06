# -*- coding: utf-8 -*-
"""把 docs/capabilities/system.md 的详情段 desc 与注册表对齐。

为什么需要这一步：这份文档 2026-11-05 之前**没有生成器**（纯手工产物），
注册表改了它不跟着变。血账：`impact_check` 的 desc 写死「现读 6301 节点 /
951536 有向边」，图重建三次错了三次，而这份文档里原样留着同一组旧数字 ——
同期 `docs/capabilities-full.json` 早有生成器，唯独它没有，
于是成了全仓唯一「改了注册表也不会提醒你」的面。

文档结构（54 段，每段一套）：

    ### `name`

    - **域**：...
    - **类型**：...
    - **要哪张票（静态）**：...
    - **必填载荷**：...
    - **常见错误**：...
    - **它做什么**：<=== 这里才是注册表 desc 原文
    - **怎么调**：...

口径（故意保守）：
  * 只同步 `- **它做什么**：` 与下一个 `- **` 之间的那段；
  * 其余元数据行、`- **怎么调**` 之后的内容**一个字节不碰**（手工维护）；
  * 顶部汇总表的截断行**不动**（截断长度是手工排版，机器猜不准）。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

from gbt_allinone.caps_registry import BENIGN_CAPS   # noqa: E402

DOC = os.path.join(ROOT, "docs", "capabilities", "system.md")
HEAD = re.compile(r"^### `([a-z0-9_]+)`[ \t]*$", re.M)
WHAT = "- **它做什么**："
HOOK = "- **怎么调**"


def _segments(src):
    """yield (name, start, end) —— 每个详情段的正文范围。"""
    marks = list(HEAD.finditer(src))
    for i, m in enumerate(marks):
        yield m.group(1), m.end(), (marks[i + 1].start() if i + 1 < len(marks) else len(src))


def _desc_span(seg: str):
    """段内 desc 正文的 (起, 止) 相对下标；找不到锚点返回 None。"""
    if WHAT not in seg:
        return None
    s = seg.index(WHAT) + len(WHAT)
    m = re.search(r"\n[ \t]*- \*\*", seg[s:])
    e = s + m.start() if m else len(seg)
    return s, e


FILL_BEGIN = "<!-- fill:auto"


def _do_fill(src: str, apply: bool) -> int:
    """为文档里**没有精修详情段**的位生成「全量速览」一节（紧凑表格，一行一位）。

    为什么不做成完整详情段：373 位 × 约 1.5 KB ≈ 560 KB，文档会肿成一个没人读的
    大字典；而这 373 位本来也没有手工精修过的「要哪张票 / 必填载荷 / 常见错误」，
    自动编只会编出一堆「无必填」套话。**一行一位**够用来查"这个位是干嘛的"，
    要完整参数就去看 `op=contract` 或 `docs/capabilities-full.json`（机器可读版）。

    幂等：已有 `<!-- fill:auto` 标记的节会被整段替换，反复跑不会叠加。
    """
    have = {m.group(1) for m in HEAD.finditer(src)}
    missing = sorted(set(BENIGN_CAPS) - have)
    if not missing:
        print("文档已覆盖全部 %d 位，无需 --fill" % len(BENIGN_CAPS))
        return 0

    block = [FILL_BEGIN + " 由 sync-capabilities-doc.py --fill 生成，勿手改 -->",
             "",
             "## 全量速览（其余 %d 位）" % len(missing),
             "",
             "> 数据源 `gbt_allinone/caps_registry.py` 现读。这些位**没有精修详情段**，"
             "只有一行摘要；完整参数与权限见 `api.run_task(\"<name>\", {\"op\":\"contract\"})` "
             "或 `docs/capabilities-full.json`。刷新：`sync-capabilities-doc.py --fill --apply`。",
             "",
             "| 能力位 | 域 | 门 | 它做什么 |",
             "|---|---|---|---|"]
    for name in missing:
        m = BENIGN_CAPS.get(name) or {}
        dom = str(m.get("domain") or "—")
        gate = "只读" if m.get("safe") else "**需授权**"
        desc = re.sub(r"\s+", " ", str(m.get("desc") or "—")).replace("|", "\\|")
        block.append("| `%s` | %s | %s | %s |" % (name, dom, gate, desc))
    block.append("")
    new_block = "\n".join(block)

    # 先摘掉旧的 fill 节（幂等）
    out = src
    i = out.find(FILL_BEGIN)
    if i >= 0:
        m = re.search(r"\n---\n\n返回 ", out[i:])
        j = i + (m.start() + 1) if m else len(out)
        out = out[:i] + out[j:]

    m = re.search(r"\n---\n\n返回 ", out)
    if not m:
        print("找不到文末的 `---` / `返回` 结构，拒绝写入（结构变了就说，不猜）")
        return 1
    pos = m.start() + 1
    out = out[:pos] + new_block + "\n" + out[pos:]

    print("已有精修段 %d 位 · 缺 %d 位 → 生成「全量速览」%d 行"
          % (len(have), len(missing), len(missing)))
    if not apply:
        print("\n干跑结束。要写回：加 --apply")
        return 0

    # 锚点守恒：精修段数量一个都不能变
    if out.count("### `") != src.count("### `"):
        print("!! 拒绝写入：详情段数量变了 %d → %d" % (src.count("### `"), out.count("### `")))
        return 1

    tmp = DOC + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(out)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, DOC)
    back = open(DOC, encoding="utf-8").read()
    print("\n已写 %s（%d → %d 字节）" % (os.path.relpath(DOC, ROOT), len(src), len(back)))
    print("  详情段仍为 %d 个（未被改动）" % back.count("### `"))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="同步 docs/capabilities/system.md 的详情段 desc")
    ap.add_argument("--apply", action="store_true", help="写回（默认只报告）")
    ap.add_argument("--fill", action="store_true",
                    help="为没有精修详情段的位生成「全量速览」节（需配 --apply 才写）")
    args = ap.parse_args(argv)

    if not os.path.exists(DOC):
        print("找不到 %s" % DOC)
        return 2
    src = open(DOC, encoding="utf-8").read()

    if args.fill:
        return _do_fill(src, args.apply)

    segs = list(_segments(src))
    drifted, no_anchor, unknown, same = [], [], [], 0
    pieces = []
    for name, s, e in segs:
        seg = src[s:e]
        span = _desc_span(seg)
        meta = BENIGN_CAPS.get(name)
        if not isinstance(meta, dict):
            unknown.append(name)
            continue
        want = str(meta.get("desc") or "").strip()
        if not want:
            continue
        if span is None:
            no_anchor.append(name)
            continue
        cur = seg[span[0]:span[1]].strip()
        if cur == want:
            same += 1
            continue
        drifted.append(name)
        if args.apply:
            new_seg = seg[:span[0]] + " " + want + seg[span[1]:]
            pieces.append((s, e, new_seg))

    print("详情段 %d · 一致 %d · 漂移 %d · 无锚点 %d · 注册表无此位 %d"
          % (len(segs), same, len(drifted), len(no_anchor), len(unknown)))
    if drifted:
        print("\n漂移（desc 与注册表不一致）共 %d：" % len(drifted))
        for n in drifted[:25]:
            print("   -", n)
    if no_anchor:
        print("\n缺 `- **它做什么**：` 锚点（需人工看）:", no_anchor[:10])
    if unknown:
        print("\n注册表里没有的位（文档过时）:", unknown[:10])

    if not args.apply:
        print("\n干跑结束。要写回：加 --apply")
        return 0
    if not pieces:
        print("\n无需改动。")
        return 0

    out = src
    for s, e, text in sorted(pieces, key=lambda x: -x[0]):
        out = out[:s] + text + out[e:]

    if out.count(HOOK) != src.count(HOOK):
        print("!! 拒绝写入：'- **怎么调**' 数量 %d → %d" % (src.count(HOOK), out.count(HOOK)))
        return 1
    if out.count(WHAT) != src.count(WHAT):
        print("!! 拒绝写入：'- **它做什么**：' 数量 %d → %d" % (src.count(WHAT), out.count(WHAT)))
        return 1

    tmp = DOC + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(out)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, DOC)

    back = open(DOC, encoding="utf-8").read()
    print("\n已写 %s（%d → %d 字节）" % (os.path.relpath(DOC, ROOT), len(src), len(back)))
    print("  锚点校验: '- **它做什么**：' ×%d · '- **怎么调**' ×%d"
          % (back.count(WHAT), back.count(HOOK)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
