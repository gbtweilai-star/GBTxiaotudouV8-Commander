# -*- coding: utf-8 -*-
# gbt-instrument: 本件是**量具**（全仓枚举页面比对重复），不消费它报出来的任何一页。
"""近乎重复页猎手 —— 找「同一份东西留了两三个版本」的地方（那才是"容易搞混"的真来源）。

立场（Owner 2026-09-23，说过三次）：「旧页面都要清理掉别留在项目里面**容易搞混**」。
⇒ 「旧」本身不是判据（`deploy/` 看着最旧，其实是 12/12 面板里的第 12 个 + 外网写入落点）。
   真正让人搞混的是 —— **同一份东西在不同路径下各留一份，且互不相同**。

判据（三条，都可机检）：
  A **同标题**：两页 `<title>` 完全一样；
  B **同尺寸带**：字节数相差 <2%；
  C **高相似**：去掉空白后前 4000 字符的重合率 > 0.9（便宜且够用的指纹）。
满足 A+B 或 A+C 记一对。

读法：本器**只报不改**。要动哪一对，得先过 `clean_residue.py` 的三重护栏（进程/声明/引用）。

用法:
  py -3.14 tools/codex-scripts/dup-pages.py
  py -3.14 tools/codex-scripts/dup-pages.py --min-kb 50     # 只看大页（小页是噪音）
"""
import argparse
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
SKIP = ("node_modules", ".git", ".pylibs", "vendor", "_upstream", ".venv", "archive")
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)


def walk(min_bytes):
    for p in ROOT.rglob("*.html"):
        s = str(p)
        if any(("/%s/" % k) in s or s.endswith("/%s" % k) for k in SKIP):
            continue
        try:
            n = p.stat().st_size
        except OSError:
            continue
        if n < min_bytes:
            continue
        yield p, n


def fingerprint(p):
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = TITLE.search(t)
    title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    body = re.sub(r"\s+", "", t)
    head = body[:4000]
    return {"title": title, "head": head,
            "sha_head": hashlib.sha1(head.encode("utf-8", "replace")).hexdigest()[:12],
            "sha_all": hashlib.sha1(body.encode("utf-8", "replace")).hexdigest()[:12],
            "chars": len(body)}


def overlap(a, b):
    """前 4000 字符的重合率（按 40 字一格的块比对）—— 便宜且够用的相似度。"""
    n, _ = 40, 0
    if not a or not b:
        return 0.0
    step = max(1, len(a) // n)
    hit = 0
    for i in range(0, len(a), step):
        if a[i:i + step] and a[i:i + step] in b:
            hit += 1
    return hit / max(1, len(range(0, len(a), step)))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-kb", type=int, default=20)
    a = ap.parse_args(argv)

    files = list(walk(a.min_kb * 1024))
    print("=" * 104)
    print("近乎重复页猎手 · 只看 ≥%d KB 的页 · 共 %d 个" % (a.min_kb, len(files)))
    print("=" * 104)

    fp = {}
    for p, n in files:
        f = fingerprint(p)
        if f:
            fp[p] = (n, f)

    by_title = defaultdict(list)
    for p, (n, f) in fp.items():
        if f["title"]:
            by_title[f["title"]].append(p)

    pairs = []
    for title, ps in by_title.items():
        if len(ps) < 2:
            continue
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                p1, p2 = ps[i], ps[j]
                n1, f1 = fp[p1]
                n2, f2 = fp[p2]
                same_size = abs(n1 - n2) / max(n1, n2) < 0.02
                ov = overlap(f1["head"], f2["head"])
                exact = f1["sha_all"] == f2["sha_all"]
                if exact or same_size or ov > 0.9:
                    pairs.append((title, p1, n1, p2, n2, exact, same_size, ov))

    if not pairs:
        print("  ✅ 没找到「同标题 + 近乎同尺寸/同内容」的页对。")
        return 0

    def rel(p):
        return str(p.relative_to(ROOT))
    pairs.sort(key=lambda x: -(x[2] + x[4]))
    print("  找到 %d 对：" % len(pairs))
    for title, p1, n1, p2, n2, exact, same_size, ov in pairs:
        kind = "**完全相同**" if exact else ("几乎同尺寸" if same_size else "内容高重合 %.0f%%" % (ov * 100))
        print()
        print("  ▸ 「%s」  %s" % (title[:44], kind))
        print("      A  %-58s %8.0f KB" % (rel(p1), n1 / 1024))
        print("      B  %-58s %8.0f KB" % (rel(p2), n2 / 1024))
    print()
    print("  ⚠️ 本器**只报不改**。要动哪一对，先过 clean_residue 的三重护栏（进程/声明/引用）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
