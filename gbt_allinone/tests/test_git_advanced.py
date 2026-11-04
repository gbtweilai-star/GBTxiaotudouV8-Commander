# -*- coding: utf-8 -*-
"""git_write 高级写面：push / force_push / rebase / reset 真跑（临时仓 + 本地裸远端）。"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import git_repo as G  # noqa: E402

OK = 0
FAIL = []


def check(name, cond, got=None):
    global OK
    if cond:
        OK += 1
        print("  ok  ", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, "|", repr(got)[:200])


def main() -> int:
    git = G._git_exe()
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="gbt-git-adv-"))
    repo = tmp / "repo"
    remote = tmp / "remote.git"
    if repo.exists():
        shutil.rmtree(repo)
    old = G._ROOT
    try:
        G._ROOT = repo
        repo.mkdir()
        subprocess.run([git, "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run([git, "config", "user.email", "t@t.t"], cwd=repo, check=True)
        subprocess.run([git, "config", "user.name", "t"], cwd=repo, check=True)
        (repo / "a.txt").write_text("a", encoding="utf-8")
        subprocess.run([git, "add", "a.txt"], cwd=repo, check=True)
        subprocess.run([git, "commit", "-m", "one"], cwd=repo, check=True, capture_output=True)
        subprocess.run([git, "init", "--bare", str(remote)], check=True, capture_output=True)

        p = G.run_write({"op": "push", "confirm": True, "remote": str(remote), "branch": "main"})
        check("push 真推", p.get("ok") is True, p.get("text"))
        check("push 标 network", p.get("network") is True)
        check("push 拒绝无 confirm", _raises(G, {"op": "push", "branch": "main"}))

        (repo / "b.txt").write_text("b", encoding="utf-8")
        subprocess.run([git, "add", "b.txt"], cwd=repo, check=True)
        subprocess.run([git, "commit", "-m", "two"], cwd=repo, check=True, capture_output=True)
        r = G.run_write({"op": "reset", "confirm": True, "rev": "HEAD~1"})
        check("reset --hard 真跑", r.get("ok") is True, r.get("text"))
        check("reset 标 destructive", r.get("destructive") is True)
        b = G.run_write({"op": "rebase", "confirm": True, "onto": "HEAD"})
        check("rebase 真跑", b.get("ok") is True, b.get("text"))
        check("rebase 标 conflict=false", b.get("conflict") is False)
        check("reset 拒绝无 confirm", _raises(G, {"op": "reset", "rev": "HEAD~1"}))
        check("rebase 拒绝无 confirm", _raises(G, {"op": "rebase", "onto": "HEAD"}))
    finally:
        G._ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— git push/rebase/reset 真跑；confirm/network/destructive 标记齐")
    return 0


def _raises(G, payload):
    try:
        G.run_write(payload)
        return False
    except G.GitRepoError:
        return True


if __name__ == "__main__":
    raise SystemExit(main())
