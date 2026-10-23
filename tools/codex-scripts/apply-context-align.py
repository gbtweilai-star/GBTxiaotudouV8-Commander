# -*- coding: utf-8 -*-
"""把上下文对齐值写进 Codex 声明面（Owner 落点那一跳的机械执行件）。

为什么是这个形态（根因留痕 2026-10-14）：
  旧版 apply-context-align.ps1 用 PowerShell 的 Get-Content -Raw | ConvertFrom-Json ——
  在 Windows PowerShell 5.1 下**按 ANSI 读 UTF-8**，中文直接乱码（用户终端实测：
  "display_name": "GBT灏忓湡璞哣8 v24..."）⇒ JSON 解析失败。**不是文件坏，是读法坏。**
  => 本件用 Python（UTF-8 显式）只做**两个键的定点替换**，不做 JSON 往返（避免重排 114KB 大文件、
     也不碰里面那两段巨型 instructions 模板）。写入一律 utf-8 **无 BOM**、原子替换、写完回读校验。

用法：
  py -3.14 tools/codex-scripts/apply-context-align.py --target "<models.json>" --context-window 13361 --auto-compact 11089
  py -3.14 tools/codex-scripts/apply-context-align.py --target "<models.json>" --dry-run --context-window 13361 --auto-compact 11089

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys
import time

SLUG = "gbt-potato-v8"


def patch(text: str, slug: str, cw: int, ac: int) -> tuple:
    i = text.find('"slug": "%s"' % slug)
    if i < 0:
        raise SystemExit("找不到 slug=%s 的条目" % slug)
    j = text.find('"slug":', i + 10)
    seg = text[i:j] if j > 0 else text[i:]
    before = re.search(r'"context_window"\s*:\s*(\d+)', seg)
    before_ac = re.search(r'"auto_compact_token_limit"\s*:\s*(null|\d+)', seg)
    seg2 = re.sub(r'("context_window"\s*:\s*)(\d+)', lambda m: m.group(1) + str(cw), seg, count=1)
    seg2 = re.sub(r'("auto_compact_token_limit"\s*:\s*)(null|\d+)', lambda m: m.group(1) + str(ac), seg2, count=1)
    out = text[:i] + seg2 + (text[j:] if j > 0 else "")
    return out, {"context_window": before.group(1) if before else None,
                 "auto_compact_token_limit": before_ac.group(1) if before_ac else None}


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                       # noqa: BLE001
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--context-window", type=int, required=True)
    ap.add_argument("--auto-compact", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    p = pathlib.Path(a.target)
    text = p.read_text(encoding="utf-8")                        # 显式 UTF-8，不和 ANSI 打架
    new, old = patch(text, SLUG, a.context_window, a.auto_compact)
    try:
        doc = json.loads(new)
    except Exception as exc:                                    # noqa: BLE001
        print("🔴 改后 JSON 解析失败，拒绝落盘：" + str(exc)[:120])
        return 1
    got = next((m for m in doc.get("models", []) if m.get("slug") == SLUG), {})
    print("目标 %s · slug=%s" % (p, SLUG))
    print("  改前：context_window=%s · auto_compact_token_limit=%s" % (old["context_window"], old["auto_compact_token_limit"]))
    print("  改后：context_window=%s · auto_compact_token_limit=%s" % (got.get("context_window"), got.get("auto_compact_token_limit")))
    if a.dry_run:
        print("  （--dry-run：未落盘）")
        return 0
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = p.with_name(p.name + ".bak-apply-" + stamp)
    shutil.copy2(p, bak)
    tmp = p.with_name(p.name + ".tmp-" + stamp)
    tmp.write_text(new, encoding="utf-8", newline="\n")        # 无 BOM
    tmp.replace(p)                                             # 原子替换
    back = json.loads(p.read_text(encoding="utf-8"))
    ok = next((m for m in back.get("models", []) if m.get("slug") == SLUG), {})
    good = ok.get("context_window") == a.context_window and ok.get("auto_compact_token_limit") == a.auto_compact
    print("  已落盘 · 备份 %s" % bak.name)
    print("  回读校验：" + ("✅ 一致" if good else "🔴 不一致（请从备份还原）"))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
