# gbt-capability: taste_guard
"""taste_guard 判据：反-slop 静态闸（纯读，不写盘）。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

MOD = Path(__file__).resolve().parents[1] / "gbt_allinone" / "tentacle" / "taste_guard.py"
FAILED = []

CLEAN = """<!doctype html><html><body>
<h1>海边的面包房</h1><p>每天五点开炉，只做一炉。</p>
<img src="1.jpg"><img src="2.jpg"><img src="3.jpg"><img src="4.jpg">
<section><h2>今天的面包</h2><p>黑麦、酸种、可颂。</p></section>
</body></html>"""

SLOP = """<!doctype html><html><body>
<div class="hero" style="background:linear-gradient(135deg,#6366f1,#a855f7);backdrop-filter:blur(8px);box-shadow:0 10px 30px rgba(0,0,0,.2)">
<span>✨ NEW</span><div class="card">A</div><div class="card">B</div><div class="card">C</div>
<p>Lorem ipsum dolor sit amet</p>
</div></body></html>"""


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def load():
    spec = importlib.util.spec_from_file_location("taste_guard_mod", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    T = load()
    print("[1] 规则表")
    check("规则 ≥15", len(T.RULES) >= 15, len(T.RULES))
    check("规则有 id/sev", all(r.get("id") and r.get("sev") in ("FAIL", "WARN") for r in T.RULES))

    print("[2] 干净页过闸")
    r = T.run("audit", html=CLEAN)
    check("PASS", r.get("verdict") == "PASS", r)
    check("有分数", isinstance(r.get("score"), int) and r["score"] >= 80, r.get("score"))

    print("[3] 烂大街页被抓")
    s = T.run("audit", html=SLOP)
    ids = {f["id"] for f in s.get("findings") or []}
    check("FAIL", s.get("verdict") == "FAIL", s)
    for must in ("no_gradient", "no_glass", "no_shadow_rest", "no_assistant_palette",
                 "no_emoji", "no_icon_cards", "no_lorem", "clear_title"):
        check("抓到 " + must, must in ids, sorted(ids))
    check("分数被扣", s.get("score", 100) < 50, s.get("score"))

    print("[4] brief / 边界")
    b = T.run("brief", sector="餐饮", tone="quiet")
    check("brief ok", b.get("ok") is True and b.get("constraints", {}).get("colors"), b)
    check("deep 探测在 status", "deep" in T.run("status"))
    d = T.run("deep_audit")
    check("deep 无 target 有边界", d.get("status") in ("needs_input", "needs_dependency") or d.get("ok") is not None, d.get("status"))
    check("inspector 可探测", "deep_audit" in T.STATUS["ops"])
    check("未知 op 拒绝", T.run("xxx").get("ok") is False)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
