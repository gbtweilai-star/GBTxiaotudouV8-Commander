# gbt-capability: sync_guard
"""sync_guard 判据（临时两棵树；不碰真 live/交付）。"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "gbt_allinone" / "tentacle" / "sync_guard.py"
FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def load():
    spec = importlib.util.spec_from_file_location("sync_guard_mod", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_tree(root: Path, files: dict, caps: int = 367):
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "capabilities.json").write_text(
        json.dumps({"count": caps, "capabilities": []}), encoding="utf-8")
    for rel, txt in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8")


def main() -> int:
    SG = load()
    print("[1] status / where")
    st = SG.run("status")
    check("status 契约", st.get("ok") is True and "verdict" in st, st)
    wh = SG.run("where")
    check("where 有入口", wh.get("ok") is True and "entry" in wh)

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        live, deliv = base / "live", base / "deliv"
        make_tree(live, {"a.py": "x=1\n", "docs/x.md": "d\n"})
        make_tree(deliv, {"a.py": "x=1\n", "docs/x.md": "d\n"})
        r = SG.run("verify", live=str(live), delivery=str(deliv))
        check("对齐判 ALIGNED", r.get("ok") is True and r.get("verdict") == "ALIGNED", r)
        check("对齐无 alerts", r.get("alerts") == [], r.get("alerts"))
        check("reading 计数", r["reading"]["differ_n"] == 0 and r["reading"]["only_live_n"] == 0)

        (deliv / "a.py").write_text("x=2\n", encoding="utf-8")
        (live / "new.py").write_text("y=1\n", encoding="utf-8")
        r2 = SG.run("verify", live=str(live), delivery=str(deliv))
        check("漂移判 DRIFT", r2.get("verdict") == "DRIFT", r2)
        codes = [a.get("code") for a in r2.get("alerts") or []]
        check("出 sync_drift alert", "sync_drift" in codes, codes)
        check("修复命令可读", "two-way-sync" in (r2.get("alerts") or [{}])[0].get("fix", ""))

        r3 = SG.run("patrol", live=str(live), delivery=str(deliv))
        check("patrol 默认不写台账", r3.get("ok") is True and "skipped" in str(r3.get("record")), r3.get("record"))

        r4 = SG.run("verify", live=str(live), delivery=str(base / "nope"))
        check("缺交付树 needs_config", r4.get("ok") is False and r4.get("status") == "needs_config", r4)

    print("[2] 注册/分派接线")
    reg = (ROOT / "gbt_allinone" / "caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone" / "api.py").read_text(encoding="utf-8")
    check("注册表有 sync_guard", '"sync_guard"' in reg)
    check("api 有分派", 'if kind == "sync_guard"' in api)
    check("desc 写只读边界", "不自动 pull/push" in reg)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
