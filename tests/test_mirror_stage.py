# gbt-capability: mirror_stage
"""mirror_stage 判据：生产只读、镜像多候选、验过才原子替换。"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

MOD = Path(__file__).resolve().parents[1] / "gbt_allinone" / "tentacle" / "mirror_stage.py"
FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def load():
    spec = importlib.util.spec_from_file_location("mirror_stage_mod", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    M = load()
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        repo.mkdir()
        prod = repo / "page.html"
        prod.write_text("OLD", encoding="utf-8")
        kw = {"repo": str(repo), "stage_root": str(Path(td) / "stage"),
              "backup_root": str(Path(td) / "backup")}

        print("[1] create/write 不碰生产")
        r = M.run("create", id="c1", targets=["page.html"], **kw)
        check("staged", r.get("status") == "staged", r)
        check("生产未动", prod.read_text(encoding="utf-8") == "OLD")
        w = M.run("write", id="c1", path="page.html", content="NEW", **kw)
        check("written", w.get("status") == "written", w)
        check("生产仍未动", prod.read_text(encoding="utf-8") == "OLD")

        print("[2] 没验过不许 promote")
        p0 = M.run("promote", id="c1", confirm=True, **kw)
        check("not_verified", p0.get("status") == "not_verified", p0)
        check("生产仍 OLD", prod.read_text(encoding="utf-8") == "OLD")

        print("[3] 失败验证不许 promote")
        bad = M.run("verify", id="c1", cmd='%s -c "import sys;sys.exit(1)"' % _q(sys.executable), **kw)
        check("verify_failed", bad.get("status") == "verify_failed", bad)
        p1 = M.run("promote", id="c1", confirm=True, **kw)
        check("仍拒", p1.get("status") == "not_verified", p1)

        print("[4] 通过后原子整页替换 + 备份 + 回滚")
        ok = M.run("verify", id="c1", cmd='%s -c "import sys;sys.exit(0)"' % _q(sys.executable), **kw)
        check("verified", ok.get("status") == "verified", ok)
        p2 = M.run("promote", id="c1", confirm=True, **kw)
        check("promoted", p2.get("status") == "promoted", p2)
        check("生产变 NEW", prod.read_text(encoding="utf-8") == "NEW", prod.read_text(encoding="utf-8"))
        check("有备份", bool(p2.get("backup")) and Path(p2["backup"]).is_dir())
        rb = M.run("rollback", id="c1", **kw)
        check("rolled_back", rb.get("status") == "rolled_back", rb)
        check("生产回 OLD", prod.read_text(encoding="utf-8") == "OLD", prod.read_text(encoding="utf-8"))

        print("[5] 多候选互不覆盖")
        M.run("create", id="a", targets=["page.html"], **kw)
        M.run("create", id="b", targets=["page.html"], **kw)
        M.run("write", id="a", path="page.html", content="A", **kw)
        M.run("write", id="b", path="page.html", content="B", **kw)
        check("两候选都在", {x["id"] for x in M.run("list", **kw)["stages"]} >= {"a", "b"})
        check("生产还没变", prod.read_text(encoding="utf-8") == "OLD")

    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


def _q(s: str) -> str:
    return '"' + str(s).replace('"', '\\"') + '"'


if __name__ == "__main__":
    raise SystemExit(main())
