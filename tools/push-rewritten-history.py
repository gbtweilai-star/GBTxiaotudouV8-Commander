# -*- coding: utf-8 -*-
"""把**已重写的历史**强制推到 GitHub（方案 A 的最后一步）。

前置：`.scratch/git-sync/repo-full` 已由 git-filter-repo 重写完成（HEAD 内容不变）。
用法：python tools/push-rewritten-history.py --prompt
"""
from __future__ import annotations

import argparse
import getpass
import os
import pathlib
import shutil
import subprocess
import sys

REPO = "gbtweilai-star/GBTxiaotudouV8-Commander"
WS = pathlib.Path(__file__).resolve().parents[1].parent  # GBTxiaotudouV8-Commander/
WORK = WS / ".scratch" / "git-sync" / "repo-full"
GIT = WS / ".scratch" / "git-sync" / "mingit" / "cmd" / "git.exe"


def run(args, env=None, check=False):
    print("  $ " + " ".join(a if "ghp_" not in str(a) else "ghp_***" for a in map(str, args)))
    p = subprocess.run([str(a) for a in args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    for line in (p.stdout or "").strip().splitlines()[-3:]:
        print("    " + line[:160])
    if p.returncode != 0:
        print("    STDERR: " + (p.stderr or "")[-500:])
        if check:
            raise SystemExit("失败")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", action="store_true")
    ap.add_argument("--token", default="")
    a = ap.parse_args()

    if not WORK.is_dir() or not GIT.is_file():
        raise SystemExit("重写好的仓库不在：%s（先跑 filter-repo 准备）" % WORK)

    token = a.token or os.environ.get("GITHUB_TOKEN") or ""
    if not token and a.prompt:
        token = getpass.getpass("粘贴 GitHub token（不可见，回车确认）：").strip()
    if not token:
        raise SystemExit("需要 token")
    if not token.isascii():
        raise SystemExit("token 含非 ASCII 字符（占位符没换？）")

    env = dict(os.environ,
               PATH=r"%s;%s;%s" % (GIT.parent, WS / ".scratch" / "git-sync" / "mingit" / "usr" / "bin", os.environ.get("PATH", "")),
               GIT_AUTHOR_NAME="gbt-sync", GIT_AUTHOR_EMAIL="gbt@local",
               GIT_COMMITTER_NAME="gbt-sync", GIT_COMMITTER_EMAIL="gbt@local")

    url = "https://x-access-token:%s@github.com/%s.git" % (token, REPO)
    run([GIT, "-C", WORK, "remote", "remove", "origin"], env=env)
    run([GIT, "-C", WORK, "remote", "add", "origin", url], env=env, check=True)
    print("强制推送重写后的历史（main）…")
    p = run([GIT, "-C", WORK, "push", "--force", "origin", "HEAD:main"], env=env)
    if p.returncode != 0:
        raise SystemExit("force push 失败（看上面 STDERR）")
    sha = run([GIT, "-C", WORK, "rev-parse", "HEAD"], env=env).stdout.strip()
    print("已强推 HEAD:", sha)
    run([GIT, "-C", WORK, "count-objects", "-vH"], env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
