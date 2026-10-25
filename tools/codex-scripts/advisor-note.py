# -*- coding: utf-8 -*-
"""顾问席 · **只追加**的建议账写入器（Claude / DSH 两个席位）

════════════════════════════════════════════════════════════════════════
设计口径（主人 2026-09-23 定：「克劳德和 DeepSeek Harness 只有给意见和给建议，没有执行权」）
════════════════════════════════════════════════════════════════════════
一句话：**给足"看得见"的，掐死"动得了"的。**

  能读：项目树 · 对话事件流 · 各窗只读读数（都由宿主代取，见 host.js 的 w3 数据件）
  能写：**只此一处** —— `gbt_allinone/store/advisor/<席位>.jsonl`，**只追加**
  不能做：任何能力位调用 / `run_task` / 部署 / 改项目文件 —— 本件里**没有**那些调用面

为什么本件必须长这样：
  · "没有执行权"如果只写在文档里，那它就只是一句话。⇒ 做成**能跑的判据**：
    本文件的 AST 里不出现 `run_task`、不出现写 `projects/**`（`advisor-audit.py` 会查）。
  · 建议账**只追加**：只以 `'a'` 模式打开目标文件；不提供删除/改写入口。
    谁想撤一条，就再追加一条「撤回：…」——**历史不改写**，这与本仓审计账本同一口径。
"""
from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stdout, "reconfigure") else None

ROOT = Path(__file__).resolve().parents[2]
LEDGER_DIR = ROOT / "gbt_allinone" / "store" / "advisor"
SEATS = ("claude", "dsh")
SIGN = "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"


def ledger_of(seat: str) -> Path:
    if seat not in SEATS:
        raise ValueError("不认的席位 %r（认这些：%s）" % (seat, "、".join(SEATS)))
    return LEDGER_DIR / ("%s.jsonl" % seat)


def note(seat: str, text: str, *, about: str = "", kind: str = "建议") -> dict:
    """追加一条建议。**只追加**：目标文件以 `'a'` 打开，本函数没有其它写路径。"""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "空建议不写（空着的一条比没有更坏：它让人以为有人看过了）"}
    p = ledger_of(seat)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seat": seat,
        "kind": kind,                       # 建议 / 观察 / 撤回
        "about": about,                     # 针对什么（作品名 / 文件 / 主题）
        "text": text,
        "executes": False,                  # 本账**只承载建议**，不承载执行
        "sign": SIGN,
    }
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    with open(p, "a", encoding="utf-8") as fh:      # ← 唯一的写口，且是追加
        fh.write(line)
    return {"ok": True, "seat": seat, "ledger": str(p.relative_to(ROOT)),
            "lines": count(seat), "record": rec}


def count(seat: str) -> int:
    p = ledger_of(seat)
    if not p.is_file():
        return 0
    with open(p, encoding="utf-8") as fh:
        return sum(1 for ln in fh if ln.strip())


def tail(seat: str, n: int = 3) -> list[dict]:
    p = ledger_of(seat)
    if not p.is_file():
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:                            # noqa: BLE001
                out.append({"坏行": ln[:80]})
    return out[-n:]


def audit_self() -> dict:
    """**自证没有执行面**：读本文件自己的 AST，查两类禁止引用。

    为什么要写在文件里、而不是只放在另一个审计器里：
      ① 提议席的实现和它的判据放在一处，改实现的人**绕不过**判据；
      ② `advisor-audit.py` 也查同两条 —— **两边都查**，任一边被绕过另一边还拦得住。
    """
    src = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    banned_calls, banned_targets = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = getattr(f, "attr", None) or getattr(f, "id", None)
            if name in ("run_task", "one_key_deploy", "ascend", "release"):
                banned_calls.append("%s() 在第 %d 行" % (name, getattr(node, "lineno", 0)))
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            # 只查"看起来像在写 projects/ 下的路径"的字面量（本件的账在 store/ 下，不在此列）
            if v.startswith("projects/") or "/projects/" in v:
                banned_targets.append("字面量 %r 在第 %d 行" % (v[:40], getattr(node, "lineno", 0)))
    return {"ok": not banned_calls and not banned_targets,
            "banned_calls": banned_calls, "banned_targets": banned_targets}


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "note":
        if len(argv) < 3:
            print(json.dumps({"ok": False, "note": "用法: note <claude|dsh> \"建议正文\" [--about 主题]"},
                             ensure_ascii=False))
            return 2
        about = ""
        if "--about" in argv:
            i = argv.index("--about")
            about = argv[i + 1] if i + 1 < len(argv) else ""
        r = note(argv[1], argv[2], about=about)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    if cmd == "status":
        print(json.dumps({"ok": True,
                          "seats": {s: {"lines": count(s), "tail": tail(s, 2)} for s in SEATS},
                          "self_audit": audit_self(),
                          "note": "建议账只追加；本件没有执行面（判据见 advisor-audit.py）"},
                         ensure_ascii=False, indent=1))
        return 0
    print(json.dumps({"ok": False, "note": "未知子命令 %r（认：note / status）" % cmd}, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
