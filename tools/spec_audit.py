#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec_audit —— 348 位里有多少是「说明书」而不是「执行器」。

为什么要这把尺子：
  实测 tentacle_learn 的每个 op 只返回 {"steps":[...], "judges":[...], "rule":"..."}，
  **一步活都不干**。它写着 ok:true，但它不执行 —— 是「诚实桩」，
  如实告诉你"该怎么做"，而不是假装做了。

  这类位**接进活路径是没意义的**：接上去也只是把说明书写进人设。
  所以要先分清楚：谁真干活，谁只是说明书。

判据（静态，不跑位）：
  读实现源码，看函数体里有没有**真 I/O**：open / sqlite / subprocess / urllib /
  socket / os. 文件操作 / 落盘 / 调 run_task。一个都没有 ⇒ 说明书。

口径：
  · 「说明书」≠ 坏。框架自己的规矩就是"没有实现就如实说"，写说明书是诚实的。
  · 这里只是量出来，**不替人决定删留**。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

IO_MARKS = (
    "open(", "sqlite3", "subprocess", "urllib", "requests.", "socket",
    "os.path.", "os.getenv", "os.environ", "shutil", "json.dump",
    "write_text", "read_text", "run_task", "Popen", "urlopen",
    "Path(", "mkdir", "glob", "listdir", "walk(",
)
SPEC_KEYS = ("steps", "judges", "rule", "how", "docs", "note", "redlines",
             "outputs", "loop", "guard", "surfaces", "route")


def find_impl(kind: str):
    """按名字找实现文件（几个常见落点）。"""
    cands = [
        ROOT / "gbt_allinone" / "tools" / (kind + ".py"),
        ROOT / "gbt_allinone" / (kind + ".py"),
        ROOT / "runtime" / "gbt_allinone" / (kind + ".py"),
        ROOT / "tools" / (kind + ".py"),
    ]
    for c in cands:
        if c.is_file():
            return c
    hits = list((ROOT / "gbt_allinone").rglob(kind + ".py")) + \
           list((ROOT / "tools").rglob(kind + ".py"))
    hits = [h for h in hits if "_archive" not in str(h)]
    return hits[0] if hits else None


_API_SRC = None


def _api_has(kind: str) -> bool:
    """api.py 里有没有这位的分发分支 —— 很多位是**内联实现**，没有独立文件。"""
    global _API_SRC
    if _API_SRC is None:
        f = ROOT / "gbt_allinone" / "api.py"
        _API_SRC = f.read_text(encoding="utf-8", errors="replace") if f.is_file() else ""
    return ('"%s"' % kind) in _API_SRC


def classify(kind: str) -> dict:
    f = find_impl(kind)
    if not f:
        if _api_has(kind):
            # 内联在 api.py：算真实现（不是说明书），只是没有独立文件
            return {"kind": kind, "verdict": "inline_api", "file": "gbt_allinone/api.py"}
        return {"kind": kind, "verdict": "no_impl_file", "file": None}
    src = f.read_text(encoding="utf-8", errors="replace")
    body = src
    io_n = sum(body.count(m) for m in IO_MARKS)
    spec_n = sum(len(re.findall(r'"%s"\s*:' % k, body)) for k in SPEC_KEYS)
    returns = len(re.findall(r"\breturn\s+\{", body))
    lines = body.count("\n") + 1
    verdict = "spec_only" if (io_n == 0 and spec_n >= 3) else "real"
    return {"kind": kind, "verdict": verdict, "file": str(f.relative_to(ROOT)),
            "lines": lines, "io_marks": io_n, "spec_keys": spec_n, "returns": returns}


def main() -> int:
    from gbt_allinone.caps_registry import all_caps
    caps = [str(c.get("name")) for c in all_caps() if isinstance(c, dict)]
    out, spec, nofile, inline = [], [], [], []
    for k in caps:
        r = classify(k)
        out.append(r)
        if r["verdict"] == "spec_only":
            spec.append(k)
        elif r["verdict"] == "inline_api":
            inline.append(k)
        elif r["verdict"] == "no_impl_file":
            nofile.append(k)
    print("  ═══ 说明书型能力审计（%d 位）═══\n" % len(caps))
    real = len(caps) - len(spec) - len(nofile) - len(inline)
    print("  真执行（独立文件，有 I/O）                    %4d  %4.0f%%"
          % (real, real / max(1, len(caps)) * 100))
    print("  内联在 api.py（有分发分支）                   %4d  %4.0f%%"
          % (len(inline), len(inline) / max(1, len(caps)) * 100))
    print("  说明书（只有 steps/judges，无 I/O）           %4d  %4.0f%%"
          % (len(spec), len(spec) / max(1, len(caps)) * 100))
    print("  真找不到实现                                %4d" % len(nofile))
    if nofile:
        print("    " + "  ".join("%-18s" % x for x in nofile[:12]))
    print()
    if spec:
        print("  ── 说明书型（前 40）──")
        for i in range(0, min(40, len(spec)), 4):
            print("    " + "  ".join("%-20s" % x for x in spec[i:i + 4]))
    (ROOT / "state" / "spec_audit.json").write_text(
        json.dumps({"total": len(caps), "spec_only": spec, "no_impl": nofile,
                    "rows": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n  报告: state/spec_audit.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
