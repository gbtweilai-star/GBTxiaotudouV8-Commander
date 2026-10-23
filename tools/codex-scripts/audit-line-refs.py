#!/usr/bin/env python
# gbt-capability: none
"""audit-line-refs.py —— 全仓扫「`文件:行号`」形态的引用，把**飘了的锚**挑出来（**只读，不改任何代码**）。

为什么要有它
------------
2026-09-25 排雷期间，"**按绝对行号登记的锚，编辑一次漂一次，漂了没人管**"这类病
已经撞到 **4 次**：
  · `false_report_audit.KNOWN_LEGIT` 的两条 FR-2 行号锚（695/833 → 实为 825/1119）
  · `holo_pet_w3/shell/main.cjs` 的 `TOOLS_CAPS` 里三条 `registered:` 指针
    （593/498/504 → 实为 580/487/493，红了至少 3 天）
而且两次都是**判据早就红了、处置方法也写在注释里，就是没人做**。
⇒ 先把这一类病的**全貌**摸出来，再决定怎么根治，而不是一次次撞。

判据（每条都写明"为什么它算坏"）
--------------------------------
* **BROKEN_MISSING**   —— 被引用的文件根本不存在（引用指向空气）
* **OUT_OF_RANGE**     —— 行号超出该文件总行数
* **SUSPICIOUS_CLOSER**—— 那一行是空行，或只是个闭合符（`} / ); / ] / }; / )`）
                        ⇒ 指针几乎一定漂了：真锚不会指向"收尾行"
* **OK**               —— 其余（**注意：这只说明"落在实义行上"，不等于语义正确**）

⚠️ 口径边界（不许念过头）
本工具**不做语义核对**：它不知道"这一行该不该是那个东西"。
语义级的核对目前只有两处有专用判据（`test_capability_registry` 的出口清单、
`false_report_audit` 的 KNOWN_LEGIT）。本工具只负责把"结构上就不对"的挑出来。

用法
----
    python tools/codex-scripts/audit-line-refs.py
    python tools/codex-scripts/audit-line-refs.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 🔴 2026-09-25 实测：第一版用 `Path('.').rglob('*')`，**过滤写在拿到路径之后**
#    ⇒ 仍然会遍历 .git / node_modules / store（那里有 2.4 GB 资产）⇒ **300s 超时**。
#    ⇒ 必须**在 walk 时就剪枝**（`dirnames[:] = [...]`），而不是事后筛。
#
# 🔴 第二处：**`output/` 必须排除 —— 否则是自反馈回路。**
#    实测：本脚本把上一轮自己生成的 `output/blueprint-audit/line-refs.json` 当成
#    "引用来源"又扫了一遍（那份 JSON 里全是 `文件:行号` 字符串），
#    于是读数里冒出「api.py:333 ← output/blueprint-audit/line-refs.json」这种条目。
#    **拿自己的产出去喂自己，不是证据，是回声。**
PRUNE = {".git", ".scratch", ".pylibs", "node_modules", "_upstream", "vendor",
         ".cluster", "store", "dist", "build", ".venv", "venv", "assets",
         ".playwright-cli", "__pycache__", ".next", "coverage", "output"}

EXTS = {".py", ".js", ".cjs", ".mjs", ".ts", ".tsx", ".json", ".yml", ".yaml",
        ".toml", ".md", ".txt", ".ps1", ".bat", ".sh"}

REF = re.compile(r"([A-Za-z0-9_][\w./\\-]*\.(?:py|js|cjs|mjs|ts|tsx|json|yml|yaml|toml|md))[:\uff1a](\d{1,5})")
CLOSERS = {"}", ");", "]", "};", ")", "*/", "};", "{{", "}}", ")]", ");", ">)", ">"}


def walk_texts():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in PRUNE and not d.startswith(".")]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() not in EXTS:
                continue
            yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--limit", type=int, default=60, help="问题清单最多打印多少条")
    args = ap.parse_args()

    # 行数缓存（被引用文件的），避免重复读
    lines_cache = {}

    # 🔴 2026-09-25 **第二处自纠（解析器太窄，造出 1520 条假阳性）**：
    #    第一版只按「仓根」和「引用文件所在目录」两处解析路径。
    #    实测：文档里大量引用是**裸文件名**（`panel_server.py` / `codex_bridge.py`），
    #    实际在 `holo_pet/` / `gbt_allinone/` 下 ⇒ 一律被判成 BROKEN_MISSING。
    #    首次跑：BROKEN_MISSING 1520 条，而其中**绝大多数是解析器自己的错**。
    #    ⇒ 加一层「**唯一 basename**」兜底；同名多于一个时不猜，单列 AMBIGUOUS。
    by_base = {}
    for p in walk_texts():
        by_base.setdefault(p.name, []).append(p)

    def get_lines(p: Path):
        if p not in lines_cache:
            try:
                lines_cache[p] = p.read_bytes().decode("utf-8-sig", "replace").splitlines()
            except Exception:  # noqa: BLE001
                lines_cache[p] = None
        return lines_cache[p]

    scanned = 0
    refs = 0
    problems = []
    for p in walk_texts():
        try:
            txt = p.read_bytes().decode("utf-8-sig", "replace")
        except Exception:  # noqa: BLE001
            continue
        if not REF.search(txt):
            continue
        scanned += 1
        rel_src = str(p.relative_to(ROOT)).replace("\\", "/")
        for m in REF.finditer(txt):
            target, lineno = m.group(1), int(m.group(2))
            refs += 1
            # 路径解析四步：仓根 → 引用文件所在目录 → 唯一 basename → 报歧义/缺失
            best = target.replace("\\", "/").split("/")[-1]
            cands = [ROOT / target, (p.parent / target)]
            hit = next((c for c in cands if c.is_file()), None)
            if hit is None:
                same = by_base.get(best) or []
                if len(same) == 1:
                    hit = same[0]
                elif len(same) > 1:
                    problems.append({"kind": "AMBIGUOUS_BASENAME", "in": rel_src,
                                     "ref": "%s:%d" % (target, lineno),
                                     "note": "同名文件 %d 个，不猜：%s"
                                             % (len(same), [str(x.relative_to(ROOT)) for x in same[:4]])})
                    continue
            if hit is None:
                problems.append({"kind": "BROKEN_MISSING", "in": rel_src,
                                 "ref": "%s:%d" % (target, lineno)})
                continue
            ls = get_lines(hit)
            if ls is None:
                continue
            if lineno < 1 or lineno > len(ls):
                problems.append({"kind": "OUT_OF_RANGE", "in": rel_src,
                                 "ref": "%s:%d" % (target, lineno),
                                 "note": "该文件仅 %d 行（%s）" % (len(ls), str(hit.relative_to(ROOT)))})
                continue
            line = ls[lineno - 1].strip()
            if (not line) or line in CLOSERS:
                problems.append({"kind": "SUSPICIOUS_CLOSER", "in": rel_src,
                                 "ref": "%s:%d" % (target, lineno),
                                 "note": "落在 %s 的 %r（真锚不该指向收尾行）"
                                         % (str(hit.relative_to(ROOT))[:60], line[:40])})

    from collections import Counter
    c = Counter(x["kind"] for x in problems)
    print("扫过含引用的文件 %d 个，引用 %d 条" % (scanned, refs))
    print("结构上就有问题的：%d 条" % len(problems))
    for k in ("BROKEN_MISSING", "OUT_OF_RANGE", "SUSPICIOUS_CLOSER"):
        print("   %-20s %d" % (k, c.get(k, 0)))
    print()
    print("⚠️ 口径：本工具**不做语义核对** —— 挑出来的是「结构上就不对」的；")
    print("   落在实义行上**不等于**语义正确（那要有专用判据）。")
    print()
    if problems:
        print("明细（最多 %d 条）：" % args.limit)
        for x in problems[:args.limit]:
            print("   [%s] %s\n        引用自 %s   %s"
                  % (x["kind"], x["ref"], x["in"], x.get("note", "")))
        if len(problems) > args.limit:
            print("   … 另有 %d 条，见 --json" % (len(problems) - args.limit))
    if args.json:
        Path(args.json).write_text(json.dumps({"refs": refs, "scanned": scanned,
                                               "problems": problems},
                                              ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        print()
        print("已写", args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
