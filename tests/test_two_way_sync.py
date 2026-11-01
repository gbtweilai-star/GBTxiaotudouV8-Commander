# gbt-capability: two-way-sync
"""two-way-sync 计划器判据（不碰真仓；用临时目录造 live/delivery 两棵树）。

跑法：python tests/test_two_way_sync.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "codex-scripts" / "two-way-sync.py"
FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def load_mod():
    spec = importlib.util.spec_from_file_location("two_way_sync", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    T = load_mod()
    print("[1] 排除与保留规则")
    check("归档目录被排除", T.rel_skip("holo_pet_w3/_archive-20261021/brain-caps/x.html"))
    check("退役目录被排除", T.rel_skip("tools/_retired/old.py"))
    check("去重删除件被排除", T.rel_skip("arms/omni_arm.py"))
    check("运行数据被排除", T.rel_skip("state/capability-audit.json"))
    check("普通源码不被排除", not T.rel_skip("gbt_allinone/tentacle/hand_bridge.py"))
    check("交付档案被识别", T.is_delivery_only("整理报告/双仓同步记录.md")
          and T.is_delivery_only("MANIFEST.json"))

    with tempfile.TemporaryDirectory() as td:
        live = Path(td) / "live"
        deliv = Path(td) / "deliv"
        for root in (live, deliv):
            (root / "gbt_allinone").mkdir(parents=True)
        files = {
            live / "same.py": "x=1\n",
            deliv / "same.py": "x=1\n",
            live / "live_only.py": "y=1\n",
            deliv / "deliv_only.py": "z=1\n",
            live / "changed.py": "old\n",
            deliv / "changed.py": "new\n",
            live / "holo_pet_w3/_archive-20261021/brain-caps/a.html": "arch\n",
            live / "state/run.json": "{}\n",
            deliv / "整理报告/r.md": "report\n",
            deliv / "MANIFEST.json": "{}\n",
        }
        for p, txt in files.items():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(txt, encoding="utf-8")

        print("[2] plan_pull")
        pull = T.plan_pull(live, deliv)
        check("拉取 live_only", "live_only.py" in pull, pull)
        check("拉取 changed", "changed.py" in pull, pull)
        check("不拉归档", not any("_archive" in x for x in pull))
        check("不拉运行数据", not any(x.startswith("state/") for x in pull))
        check("不拉交付档案", not any(x.startswith("整理报告/") for x in pull))

        print("[3] plan_push")
        push = T.plan_push(live, deliv)
        check("推送 deliv_only", "deliv_only.py" in push, push)
        check("推送 changed", "changed.py" in push, push)
        check("不推交付档案", not any(x.startswith("整理报告/") or x == "MANIFEST.json" for x in push))

        print("[4] status / verify")
        st = T.status(live, deliv)
        check("only_live 抓到 live_only", st["only_live"] == ["live_only.py"], st["only_live"])
        check("only_delivery 去掉交付档案", st["only_delivery"] == ["deliv_only.py"], st["only_delivery"])
        check("differ 抓到 changed", st["differ"] == ["changed.py"], st["differ"])
        check("catalog 计数可读（临时树为 -1）", st["live_caps"] == -1)
        check("状态判 DRIFT", st["verdict"] == "DRIFT", st["verdict"])

    print("[5] 注册表插入块（文本）")
    check("REG_BLOCK 含两枚能力", '"hand_retarget"' in T.REG_BLOCK and '"hand_bridge"' in T.REG_BLOCK)
    check("API_BLOCK 含两段分派", 'if kind == "hand_retarget"' in T.API_BLOCK
          and 'if kind == "hand_bridge"' in T.API_BLOCK)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
