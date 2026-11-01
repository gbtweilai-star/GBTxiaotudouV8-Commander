# gbt-capability: experience_forge
"""experience_forge 判据：没有外部验证证据，不许固化。"""
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

MOD = Path(__file__).resolve().parents[1] / "gbt_allinone" / "tentacle" / "experience_forge.py"
FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def load():
    spec = importlib.util.spec_from_file_location("experience_forge_mod", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    E = load()
    with tempfile.TemporaryDirectory() as td:
        store = str(Path(td) / "exp")
        print("[1] 无验证 → 拒收")
        r = E.run("record", store=store, problem="页面无标题导致真浏览器 FAIL", solution="补 h1")
        check("needs_verify", r.get("status") == "needs_verify", r)
        check("fail_closed", r.get("ok") is False and r.get("fail_closed") is True)

        print("[2] 验证 exit≠0 → 拒收")
        r = E.run("record", store=store, problem="页面无标题导致真浏览器 FAIL", solution="补 h1",
                  verify={"cmd": "deep_audit", "exit_code": 1, "evidence": "report.json"})
        check("非零拒收", r.get("status") == "needs_verify", r)

        print("[3] 有证据 → 收、可查、可升规则")
        v = {"cmd": "run_task('taste_guard',{'op':'deep_audit'})", "exit_code": 0,
             "evidence": "outputs/taste-guard/inspect/report.json PASS"}
        r = E.run("record", store=store, problem="上帝视角首页无 h1、0 图、被绝对定位遮住",
                  attempts=["加 hero", "改 gbt-view 为 static"], solution="首屏 hero + 真图 + 静态视图",
                  verify=v, tags=["taste_guard", "html"], files=["holo_pet_w3/index.html"])
        check("recorded", r.get("status") == "recorded", r)
        eid = r.get("id")
        q = E.run("query", store=store, query="首页 h1 绝对定位")
        check("query 命中", q.get("ok") and q.get("count", 0) >= 1, q)
        pr = E.run("promote", store=store, id=eid, kind="rule", name="首屏必须有可见 h1")
        check("rule 升级", pr.get("status") == "rule_promoted", pr)
        vr = E.run("verify", store=store)
        check("库校验 ok", vr.get("ok") is True and vr.get("entries") == 1, vr)

        print("[4] 镜像能力：派生副本 + 过期检测")
        mir = E.run("mirror", store=store, out=str(Path(td) / "mirror" / "entries.jsonl"))
        check("mirror 生成", mir.get("status") == "mirrored" and mir.get("entries") == 1, mir)
        ms = E.run("mirror_status", store=store, out=str(Path(td) / "mirror" / "entries.jsonl"))
        check("mirror 同步", ms.get("in_sync") is True, ms)
        E.run("record", store=store, problem="镜像过期测试条目", solution="再记一条",
              verify={"cmd": "py tests/x.py", "exit_code": 0, "evidence": "OK"})
        stale = E.run("mirror_status", store=store, out=str(Path(td) / "mirror" / "entries.jsonl"))
        check("库变后 mirror 过期", stale.get("in_sync") is False and stale.get("status") == "stale", stale)

        print("[5] promote 不存在的 id")
        check("not_found", E.run("promote", store=store, id="nope").get("status") == "not_found")

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
