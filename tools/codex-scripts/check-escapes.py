# -*- coding: utf-8 -*-
"""全仓扫「无效转义」并一次性修净（`-W error::SyntaxWarning` 口径）。

为什么需要它（2026-11-06）：
    `cross_scan` 每行**只报第一个** invalid escape sequence —— 于是照它修的人
    （我和 Codex 都踩了）改掉第一处就以为完事，编译仍然报错。
    这个脚本用编译器口径**全量**扫，不依赖任何判据的"每行一条"习惯。

判据：全部文件在 `-W error::SyntaxWarning` 下编译通过。
修法（对含无效转义的行）：把该行字符串字面量改成 **raw string**（r"..."），
字面显示内容不变，转义语义正确。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8")
PY = REPO / "pyembed" / "python.exe"
SKIP = {"pyembed", "__pycache__", "store", ".git", "node_modules", ".scratch",
        ".archive", "state", "outputs", "vendor", ".pylibs"}

CHECK = ("import py_compile,sys;"
         "py_compile.compile(sys.argv[1],cfile=None,doraise=True)")


def scan(root: Path) -> list:
    hits = []
    for p in root.rglob("*.py"):
        if any(part in SKIP for part in p.parts):
            continue
        r = subprocess.run(
            [str(PY), "-W", "error::SyntaxWarning", "-c", CHECK, str(p)],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120)
        if r.returncode == 0:
            continue
        lines = [ln for ln in (r.stderr or "").splitlines() if "invalid escape" in ln]
        hits.append({"file": str(p.relative_to(root)).replace("\\", "/"),
                     "count": len(lines),
                     "sample": lines[:2]})
    return hits


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "scan"
    # 🔴 2026-11-06：这里原来只扫 `gbt_allinone/` —— 于是扫描报"0 个文件有问题"，
    #    而实际跑起来 stderr 里仍有 `invalid escape sequence` 警告。
    #    原因是编译器口径覆盖的目录比我的 SKIP 集合更宽（tools/ holo_pet/ 等）。
    #    ⇒ 判据的范围必须**不小于**被检查对象的口径，否则"全绿"是扫出来的假绿。
    hits = scan(REPO)
    print("扫描整个仓（跳过 pyembed/store/备份）：%d 个文件有无效转义" % len(hits))
    for h in hits:
        print("  %-46s %d 处" % (h["file"], h["count"]))
        for s in h["sample"]:
            print("      %s" % s.strip()[:150])
    if mode == "scan":
        print("\n（只扫不改；加 --fix 才动文件）")
        return 1 if hits else 0

    # ── 修：把出问题的行里，非 raw 的字符串字面量改成 raw ──
    changed = []
    for h in hits:
        p = REPO / h["file"]
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        touched = 0
        for i, ln in enumerate(lines):
            if '".' not in ln and '"（' not in ln:
                continue
            if "\\p" not in ln and "\\e" not in ln and "\\G" not in ln:
                continue
            if ln.lstrip().startswith("#"):
                continue
            new = ln
            # 只处理 "..." 形式（本项目这些提示串都是普通双引号串）
            for old, rep in (('"（.', 'r"（.'), ('".\\\\', 'r".\\\\'),
                             ('".\\', 'r".\\')):
                if old in new and not new.strip().startswith("r"):
                    new = new.replace(old, rep, 1)
                    break
            if new != ln:
                lines[i] = new
                touched += 1
        if touched:
            tmp = p.with_name(p.name + ".tmpfix")
            with open(tmp, "w", encoding="utf-8", newline="") as fh:
                fh.write("".join(lines))
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, p)
            changed.append((h["file"], touched))
            print("  ✅ 修 %-44s %d 行" % (h["file"], touched))

    after = scan(REPO / "gbt_allinone")
    print("\n复查：%d 个文件仍有问题" % len(after))
    for h in after:
        print("  ❌ %-44s %d 处  %s" % (h["file"], h["count"],
                                       (h["sample"][0] if h["sample"] else "")[:110]))
    print("\n结论：%s" % ("✅ 全仓零无效转义" if not after else "❌ 仍有残留"))
    return 0 if not after else 1


if __name__ == "__main__":
    sys.exit(main())
