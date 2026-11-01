# gbt-capability: experience_forge
"""已固化规则的回归闸：规则不能只写在 rules.json，必须能被测试抓住。"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def load():
    spec = importlib.util.spec_from_file_location("experience_forge_mod", ROOT / "gbt_allinone" / "tentacle" / "experience_forge.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    print("[1] 规则：首屏必须有可见 h1 / 真图 / 视图不得绝对覆盖")
    html = (ROOT / "holo_pet_w3" / "index.html").read_text(encoding="utf-8", errors="replace")
    css = (ROOT / "holo_pet_w3" / "taste-fix.css").read_text(encoding="utf-8", errors="replace")
    check("has h1", "<h1" in html.lower())
    check("real imgs >=4", html.lower().count("<img") >= 4, html.lower().count("<img"))
    check("gbt-view static", "position: static" in css and ".gbt-view" in css)
    check("no shadow fix", "box-shadow: none" in css)

    print("[2] 规则：同步 pull 必须 newer-wins")
    ps = (ROOT / "tools" / "two-way-sync.ps1").read_text(encoding="utf-8", errors="replace")
    check("mtime 比较在", "LastWriteTimeUtc" in ps)
    check("较新则跳过", "return $false" in ps)

    print("[3] 规则：无外部验证不许固化")
    E = load()
    with tempfile.TemporaryDirectory() as td:
        store = str(Path(td) / "exp")
        bad = E.run("record", store=store, problem="xx 没跑通", solution="xx")
        check("无证据拒收", bad.get("status") == "needs_verify" and bad.get("ok") is False, bad)
        good = E.run("record", store=store, problem="xx 修好了", solution="xx 修法",
                     verify={"cmd": "py tests/x.py", "exit_code": 0, "evidence": "ALL PASS"})
        check("有证据收下", good.get("status") == "recorded", good)
        check("库校验 ok", E.run("verify", store=store).get("ok") is True)

    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
