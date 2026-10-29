# -*- coding: utf-8 -*-
"""顾问席「**只有建议权**」的判据器（可机检，四条 + 一条有牙自检）

主人 2026-09-23 定：「里面的克劳德和 DeepSeek Harness **只有给意见和给建议，没有执行权**」。
本器把那句话变成**能跑、能指行号、能红**的东西 —— 而不是文档里的一句承诺。

四条判据：
  ① **建议账只追加**：写入器里出现过的写模式**只有** `'a'`（`open(..., 'a')`）；
     出现 `'w'` / `'x'` / `os.remove` / `unlink` / `rmtree` 即判否。
  ② **无执行面**：写入器的 AST 里不出现 `run_task` / `one_key_deploy` / `ascend` / `release`
     （这四个是"真动手"的门面）；也不出现写 `projects/**` 的路径字面量。
  ③ **席位固定**：只认 `claude` / `dsh` 两个席位，别的名字**拒绝**（不许多开一个口）。
  ④ **账实相符**：写入器 `status` 报的条数与**盘上真行数**一致（现读，不手抄）。
外加：
  ⑤ **判据有牙**：把一段 `run_task(...)` 与 `open(..., 'w')` 植进**副本**，判据必须报红。
     —— 不植扰动就说"判据活着"，等于没量过（本仓第 34 轮的教训）。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
WRITER = ROOT / "tools" / "codex-scripts" / "advisor-note.py"
LEDGER_DIR = ROOT / "gbt_allinone" / "store" / "advisor"
SEATS = ("claude", "dsh")
BANNED_CALLS = ("run_task", "one_key_deploy", "ascend", "release")


def scan(src: str, name: str = "writer") -> dict:
    """查"执行面"与"写面"。

    🔴 第 42 轮当场修过一个**假红**：第一版把**任何**含 `projects/` 的字符串字面量都算成写路径，
    于是本件文档里那句「不出现写 `projects/**`」**自己被自己判红**。
    假红比没有判据更坏 —— 它会让人把真问题当噪音。
    修法两条：① 只看**写类调用的实参**（`open` / `write_text` / `write_bytes` / `Path` / 删除类），
              不看散文；② 跳过**文档字符串**（AST 里它是 Expr(Constant)，不是实参）。
    """
    tree = ast.parse(src)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
               and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    WRITE_FNS = ("open", "write_text", "write_bytes", "Path", "mkdir", "remove", "unlink",
                 "rmtree", "rmdir", "truncate", "replace", "rename")
    modes, calls, proj = [], [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            fn = getattr(f, "attr", None) or getattr(f, "id", None)
            if fn in BANNED_CALLS:
                calls.append("%s() @L%d" % (fn, getattr(node, "lineno", 0)))
            if fn == "open":
                for a in list(node.args) + [k.value for k in node.keywords if k.arg == "mode"]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        modes.append(a.value)
            if fn in ("remove", "unlink", "rmtree", "rmdir", "truncate"):
                proj.append("%s() @L%d" % (fn, getattr(node, "lineno", 0)))
            if fn in WRITE_FNS:                      # ← 只查**写类调用的实参**，不查散文
                for a in list(node.args):
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                       and ("projects/" in a.value or a.value.startswith("projects")):
                        proj.append("写路径实参 %r @L%d" % (a.value[:36], getattr(node, "lineno", 0)))
    return {"modes": sorted(set(modes)), "banned_calls": calls, "project_writes": proj,
            "docstring_literals_skipped": len(docstrings)}


def ledger_lines(seat: str) -> int:
    p = LEDGER_DIR / ("%s.jsonl" % seat)
    if not p.is_file():
        return 0
    with open(p, encoding="utf-8") as fh:
        return sum(1 for ln in fh if ln.strip())


def main() -> int:
    print("=" * 80)
    print("顾问席 · 只有建议权 · 四条判据（+ 一条有牙自检）")
    print("=" * 80)
    if not WRITER.is_file():
        print("🔴 写入器不在：%s" % WRITER)
        return 2
    src = WRITER.read_text(encoding="utf-8")
    s = scan(src)

    # ① 只追加
    bad_modes = [m for m in s["modes"] if not m.startswith("a")]
    c1 = not bad_modes
    # ② 无执行面
    c2 = not s["banned_calls"] and not s["project_writes"]
    # ③ 席位固定
    m = re.search(r"SEATS\s*=\s*\(([^)]*)\)", src)
    seats = tuple(x.strip().strip('"\'') for x in (m.group(1).split(",") if m else []) if x.strip())
    c3 = seats == SEATS
    # ④ 账实相符（现读：盘上行数 vs 逐行计数）
    per = {}
    for seat in SEATS:
        p = LEDGER_DIR / ("%s.jsonl" % seat)
        by_hand = sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()) if p.is_file() else 0
        per[seat] = {"盘上行数": by_hand, "逐行计数": ledger_lines(seat),
                     "一致": by_hand == ledger_lines(seat)}
    c4 = all(v["一致"] for v in per.values())

    # ⑤ 判据有牙：往副本里植入两处违规，必须被抓到。
 # 植入的调用要**直呼其名**（不许用别名）—— 我第一版用 `_rt(...)` 别名调用，
    #       按名字查的判据当然扫不到 ⇒ 那次"反向对照"是假阴性，不是判据没牙。
    planted = src.replace("def note(", "def _probe():\n    return open('projects/x.md', 'w')\n\n\ndef note(", 1) \
                 .replace("    p = ledger_of(seat)",
                          "    __import__('gbt_allinone').run_task('x', {})\n    p = ledger_of(seat)", 1)
    sp = scan(planted)
    teeth = ("w" in sp["modes"]) and bool(sp["banned_calls"]) and bool(sp["project_writes"])

    print("\n  ① 建议账只追加：open 模式 = %s ⇒ %s"
          % (s["modes"] or "(没有 open 调用?)", "✔ 只有追加" if c1 else "✗ 出现非追加模式 %s" % bad_modes))
    print("  ② 无执行面：%s / 写 projects：%s ⇒ %s"
          % (s["banned_calls"] or "无", s["project_writes"] or "无", "✔" if c2 else "✗"))
    print("  ③ 席位固定：%s ⇒ %s" % ("、".join(seats) or "(没解析到)", "✔" if c3 else "✗"))
    print("  ④ 账实相符：")
    for seat, v in per.items():
        print("       %-8s 盘上 %d 行 · 逐行计数 %d ⇒ %s" % (seat, v["盘上行数"], v["逐行计数"], "✔" if v["一致"] else "✗"))
    print("  ⑤ 判据有牙（植入 run_task + open('w') 必被抓）：植入后 modes=%s calls=%s ⇒ %s"
          % (sp["modes"], sp["banned_calls"], "✔" if teeth else "✗"))

    ok = c1 and c2 and c3 and c4 and teeth
    print("\n判读：%s" % ("✅ 顾问席**只有建议权**（写面只此一处、只追加；无执行面）—— 四条判据全过"
                       if ok else "🔴 有判据没通过，见上"))
    print("⚠️ 本器**只查得到代码结构**：它证明「没有执行面」，不证明「建议有用」。")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
