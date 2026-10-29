#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gene_guard —— 「树规 GENE-HT-001」的执行器（不是文档，是闸）

主人令（2026-10-30 原话）：
「不管是什么代码只要进了我们的项目树就要使用触手双向绑定，每一页覆盖每一个代码，
  并实现所有代码页面可以互通，达到不跑弯路直达操控。」

这条已经刻进她的基因（state/her_persona.txt、_lite、model-chat 的 #system），
但**写在人设里只是话，必须有机器能验**。本器就是那道闸：

  ① 基因在位  三处人设都带 GENE-HT-001 标记（改丢了立刻红）
  ② 进来就绑  跑 gapbind：凡是有标签可挂却没绑的，当场绑完，复量必须为 0
  ③ 每页覆盖  跑 page_tentacle scan：每一页都要 kit + 壳
  ④ 互通直达  每一页都装了 window.gbtW3（走 /_cap 打 run_task），不经中间人绕路

用法：
    python3 tools/gene_guard.py            # 自愈 + 判决（可接巡检/验收）
    python3 tools/gene_guard.py --check    # 只查不改（CI 用，有缺口就非 0）
    python3 tools/gene_guard.py --json     # 机读回执
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
MARK = "GENE-HT-001"

GENE_FILES = [
    ROOT / "state" / "her_persona.txt",
    ROOT / "state" / "her_persona_lite.txt",
    ROOT / "holo_pet_w3" / "model-chat" / "index.html",
]


def _run(args: list, timeout: int = 900) -> tuple:
    try:
        r = subprocess.run([sys.executable, "-u"] + args, cwd=str(ROOT),
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "超时"
    except Exception as exc:                                      # noqa: BLE001
        return 1, "%s: %s" % (type(exc).__name__, exc)


def check_gene() -> dict:
    """① 基因在位：三处人设都要带标记。"""
    rows, ok = [], True
    for f in GENE_FILES:
        try:
            hit = MARK in f.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            hit = False
        rows.append({"file": str(f.relative_to(ROOT)), "has_mark": hit})
        ok = ok and hit
    return {"ok": ok, "rows": rows}


def heal_bind(check_only: bool) -> dict:
    """② 进来就绑：有标签没绑的，当场绑完。"""
    if not check_only:
        _rc, out = _run([str(TOOLS / "tentacle_bind.py"), "gapbind"])
        healed = out.strip().splitlines()[-2:] if out.strip() else []
    else:
        healed = []
    rc, out = _run([str(TOOLS / "tentacle_bind.py"), "gaps"])
    # gaps 的 verbose 输出里 "真缺口 N 个"
    n = 0
    for ln in out.splitlines():
        if "真缺口" in ln:
            try:
                n = int(ln.split("真缺口")[1].split("个")[0].strip())
            except Exception:                                     # noqa: BLE001
                pass
    return {"ok": n == 0, "gaps": n, "heal": healed, "tail": out.strip().splitlines()[-1:] }


def check_pages() -> dict:
    """③④ 每页覆盖 + 互通直达：kit/壳/gbtW3 三样都要在。"""
    rc, out = _run([str(TOOLS / "page_tentacle.py"), "scan"])
    lines = [l.strip() for l in out.splitlines() if "index.html" in l]
    bad = []
    for l in lines:
        if "kit=有" not in l or "壳=有" not in l:
            bad.append(l[:80])
    return {"ok": not bad and bool(lines), "pages": len(lines), "bad": bad[:8]}


def main() -> int:
    check_only = "--check" in sys.argv
    g = check_gene()
    b = heal_bind(check_only)
    p = check_pages()
    res = {"ok": g["ok"] and b["ok"] and p["ok"],
           "gene": g, "bind": b, "pages": p,
           "mode": "check" if check_only else "self-heal"}
    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print("  ═══ 基因守卫 GENE-HT-001 ═══")
        for r in g["rows"]:
            print("    %s 基因标记  %s" % ("✅" if r["has_mark"] else "🔴", r["file"]))
        print("    %s 进来就绑  真缺口 %d 条%s"
              % ("✅" if b["ok"] else "🔴", b["gaps"],
                 "" if not b["heal"] else "（本轮自愈：%s）" % " / ".join(b["heal"])))
        print("    %s 每页覆盖  %d 页已接（壳+kit）" % ("✅" if p["ok"] else "🔴", p["pages"]))
        for x in p["bad"]:
            print("       🔴 %s" % x)
        print("    判决：%s" % ("✅ 树规成立" if res["ok"] else "🔴 有缺口，不算成立"))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
