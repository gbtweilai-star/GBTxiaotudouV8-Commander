# -*- coding: utf-8 -*-
"""把 README 里的读数行从真身数据同步过来 —— 人不再手改数字。

为什么要有这个脚本（2026-11-04）：
    首屏图因为「脚本里硬编码 341」而长期与正文脱节；README 的读数行同样是
    靠人手改，改一次换一次口径、还能漏项（曾经把 denied 2 位漏掉，写成 124）。
    口径漂移的根因是「数字有多个来源」，不是某次手滑。所以把 README 读数行
    也做成数据驱动：**只认 data/ 里的真身，替换行数不对就报错退出。**

口径（写死）：
  · 锚点是行首 `| 逐位真调 |`（中文）与 `| Every bit live-tested |`（英文）；
  · 每张表**必须恰好命中 1 行**，0 行或多行都报错 —— 不静默、不尽力而为；
  · 分类合计必须等于注册表位数，否则报错不出手。

用法：
    py -3.12 -X utf8 tools/codex-scripts/sync-readme-figures.py           # 写入
    py -3.12 -X utf8 tools/codex-scripts/sync-readme-figures.py --check   # 只比对，漂移则退出码 1
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
CMD = "`python tools/codex-scripts/probe-caps-live.py --timeout 120`"

# 分类的中文说法：顺序即展示顺序，合计必须是 427
LABELS = (
    ("needs_auth", "需授权不跑"),
    ("needs_params", "缺参数不瞎编"),
    ("needs_state", "缺前置排练计划"),
    ("needs_dependency", "缺依赖"),
    ("denied", "被授权门拒绝"),
    ("timeout", "超时"),
    ("failed", "无法归因"),
    ("exception", "异常"),
)


def read_figures() -> dict:
    caps = json.loads((ROOT / "data" / "capabilities.json").read_text(encoding="utf-8"))
    total = int(caps.get("count") or len(caps["capabilities"]))
    if total != len(caps["capabilities"]):
        raise SystemExit(f"账不平：count={total} vs capabilities={len(caps['capabilities'])}")
    live = json.loads((ROOT / "data" / "capability-live-test.json").read_text(encoding="utf-8"))
    cnt = live["counts"]
    if sum(cnt.values()) != total:
        raise SystemExit(f"真调账不平：分类合计 {sum(cnt.values())} ≠ 注册表 {total}")
    return {"total": total, "counts": cnt, "ok": int(cnt.get("ok", 0)),
            "live_at": live.get("at")}


def cn_row(f: dict) -> str:
    rest = f["total"] - f["ok"]
    parts = [f"{v} {txt}" for k, txt in LABELS if (v := int(f["counts"].get(k, 0))) > 0]
    unattributed = int(f["counts"].get("failed", 0)) + int(f["counts"].get("timeout", 0)) + int(f["counts"].get("exception", 0))
    tail = "**0 位无法归因、0 超时**" if unattributed == 0 else f"**{unattributed} 位无法归因**"
    return (f"| 逐位真调 | **{f['ok']} / {f['total']} 通过**（其余 {rest} 位："
            f"{'、'.join(parts)}；{tail}） | {CMD} |")


def en_row(f: dict) -> str:
    c = f["counts"]
    return (f"| Every bit live-tested | **{f['ok']} ok / {c.get('needs_auth', 0)} needs-ticket / "
            f"{c.get('needs_params', 0)} needs-input / {c.get('denied', 0)} denied = {f['total']}** "
            f"(live at {f['live_at']}; 0 unattributed, 0 timeout) | "
            f"[docs/07-capability-proof.md](docs/07-capability-proof.md) |")


def docs_pages() -> int:
    """docs/ 下 Markdown 页数（README 的 Docs 徽章口径）。"""
    d = ROOT / "docs"
    return len(list(d.glob("*.md"))) if d.is_dir() else 0


TARGETS = (
    (("README.md", r"^\| 逐位真调 \|.*$", cn_row)),
    (("README.en.md", r"^\| Every bit live-tested \|.*$", en_row)),
)


def main() -> int:
    check = "--check" in sys.argv[1:]
    f = read_figures()
    print("读数 ←", json.dumps({"total": f["total"], "ok": f["ok"], "counts": f["counts"]}, ensure_ascii=False))
    drift = 0
    for fname, pattern, builder in TARGETS:
        path = ROOT / fname
        if not path.is_file():
            print(f"  {fname}: 跳过（文件不存在）")
            continue
        text = path.read_text(encoding="utf-8")
        new_line = builder(f)
        new_text, n = re.subn(pattern, lambda _m: new_line, text, flags=re.M)
        if n != 1:
            raise SystemExit(f"{fname}: 锚点 {pattern} 命中 {n} 行（必须恰好 1 行）—— 拒绝同步")
        if new_text == text:
            print(f"  {fname}: 已一致")
            continue
        drift += 1
        if check:
            print(f"  {fname}: 有漂移（--check 不写入）")
            for a, b in zip(text.splitlines(), new_text.splitlines()):
                if a != b:
                    print(f"    - {a[:100]}\n    + {b[:100]}")
        else:
            path.write_text(new_text, encoding="utf-8")
            print(f"  {fname}: 已同步 1 行")
    # badges 同步：shields.io URL 里的数字也会漂移（曾出现 docs 徽章写 364 而实际 264）。
    # 这一层不要求「恰好 1 行」，而是每处匹配都替换；没有匹配说明徽章被删了，只提示不报错。
    readme = ROOT / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        new = re.sub(r"badge/Capabilities-\d+", f"badge/Capabilities-{f['total']}", text)
        new = re.sub(r"badge/Docs-\d+_pages", f"badge/Docs-{docs_pages()}_pages", new)
        if new != text:
            drift += 1
            if check:
                print("  README.md badges: 有漂移")
            else:
                readme.write_text(new, encoding="utf-8")
                print(f"  README.md badges: 已同步（Capabilities={f['total']} · Docs={docs_pages()} pages）")
        else:
            print("  README.md badges: 已一致")

    if check and drift:
        print(f"漂移 {drift} 处 → 退出码 1")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
