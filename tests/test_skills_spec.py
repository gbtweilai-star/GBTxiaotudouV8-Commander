# -*- coding: utf-8 -*-
"""Agent Skills 规范判据：合规校验 / 打包 / 安装 / 渐进读取（闭环）。

跑法：python tests/test_skills_spec.py
"""
from __future__ import annotations

import os
import pathlib
import shutil
import sys
import zipfile

ROOT = pathlib.Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(ROOT))

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)[:300]))
    if not cond:
        FAILED.append(name)


def main() -> int:
    import gbt_allinone as gbt
    from gbt_allinone.tentacle import skills_hub as SH

    def api(op, **kw):
        return gbt.run_task("skills_hub", {"op": op, **kw}, probe=True)["gbt_result"]["result"]

    print("[1] validate：全部 skill 符合 Agent Skills 规范")
    v = api("validate")
    check("verdict clean", v.get("verdict") == "clean", v.get("errors"))
    check(">=22 个", (v.get("count") or 0) >= 22, v.get("count"))

    print("[2] validate 能抓不合规（name 大写 / 空描述 / 目录不同名）")
    fake = {"name": "Bad Name", "path": "state/tmp/bad-skill/SKILL.md",
            "body": "", "description": ""}
    v2 = SH.validate(items=[fake])
    check("verdict broken", v2.get("verdict") == "broken", v2)
    errs = " ".join(v2.get("errors")[0]["errors"]) if v2.get("errors") else ""
    check("报 name 规则", "name" in errs, errs)
    check("报 description", "description" in errs, errs)

    print("[3] pack：打成 <name>/SKILL.md 结构的 zip")
    p = api("pack", name="brainstorming")
    check("pack ok", p.get("ok") is True, p.get("error"))
    z = pathlib.Path(p["packs"][0]["zip"])
    check("zip 存在", z.is_file(), str(z))
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
    check("zip 根是 <name>/SKILL.md", "brainstorming/SKILL.md" in names, names[:5])

    print("[4] install：默认演练不写盘；真装出 SKILL.md（过 filesystem_write 门）")
    target = ROOT / "state" / "tmp" / "skills-spec-test"
    if target.exists():
        shutil.rmtree(target)
    d = api("install", name="brainstorming", dir=str(target))
    check("dry_run ok", d.get("ok") is True, d)
    check("演练没写盘", not (target / "brainstorming").exists(), "dry_run 竟然写了盘")
    from gbt_allinone.security import policy
    with policy.owner_session():
        r = api("install", name="brainstorming", dir=str(target), dry_run=False)
    check("真装 ok", r.get("ok") is True, r)
    check("SKILL.md 到位", (target / "brainstorming" / "SKILL.md").is_file(), list(target.rglob("*"))[:5])

    print("[5] read：渐进读取 SKILL.md；越界路径被拒")
    rd = api("read", name="brainstorming", file="SKILL.md")
    check("读到正文", (rd.get("text") or "").strip() != "", rd.get("text"))
    bad = api("read", name="brainstorming", file="../../../README.md")
    check("越界被拒", bad.get("ok") is False, bad)

    shutil.rmtree(target, ignore_errors=True)
    if z.exists():
        z.unlink()

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 规范校验/打包/安装/渐进读取 全闭环")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
