# -*- coding: utf-8 -*-
"""一键发布：推装修 + 设为私人 + 设置仓库元信息（描述/话题/主页）。

为什么合成一个：这三件事都要 token，分开做要反复输入 token。

用法：
    python tools/publish-and-private.py --prompt
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import pathlib
import shutil
import stat
import subprocess
import urllib.request

REPO = "gbtweilai-star/GBTxiaotudouV8-Commander"
API = "https://api.github.com"
ROOT = pathlib.Path(__file__).resolve().parents[1]
WS = ROOT.parent
SCRATCH = WS / ".scratch" / "publish"
MINGIT_DIR = SCRATCH / "mingit"
WORK = SCRATCH / "repo-sync"

SKIP_TOP = {"state", "store", "dist", "runtime", "logs", "vaults", "vendor", ".git",
            "__pycache__", "node_modules", ".scratch", "outputs", "pyembed", "交付成片"}
SKIP_EXT = {".pyc", ".pyo", ".gguf", ".zip", ".7z", ".gz", ".tar", ".mp4", ".webm",
            ".wav", ".db", ".pkl", ".pt", ".bin", ".log"}

DESCRIPTION = ("GBT小土豆V8 · 独立数字人框架：统一入口 run_task，375 位能力位 / 30 域，"
               "全行为落审计，写盘·花钱·出网一律先过主人授权门。"
               " A standalone digital-human framework: one entry (run_task), 375 audited capability bits behind a single gate.")
TOPICS = ["ai-agent", "ai-agents", "llm", "capability-routing", "audit-log", "tool-use",
          "tool-calling", "chinese-nlp", "openai-compatible", "digital-human", "automation",
          "desktop-automation", "workflow-engine", "qwen2", "robotics", "python"]
HOMEPAGE = "https://gbtweilai-star.github.io/GBTxiaotudouV8-Commander/"


def _req(url, token, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("User-Agent", "dsh-publish")
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("Authorization", "Bearer " + token)
    if data:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=90) as x:
        b = x.read()
    return json.loads(b) if b.strip() else {}


def git_exe() -> pathlib.Path:
    g = MINGIT_DIR / "cmd" / "git.exe"
    if g.is_file():
        return g
    SCRATCH.mkdir(parents=True, exist_ok=True)
    z = SCRATCH / "mingit.zip"
    if not z.is_file():
        print("下载 MinGit（约 50MB）…")
        r = urllib.request.Request("https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/MinGit-2.47.1-64-bit.zip",
                                   headers={"User-Agent": "dsh"})
        with urllib.request.urlopen(r, timeout=900) as resp, open(z, "wb") as f:
            shutil.copyfileobj(resp, f, 1024 * 512)
    import zipfile
    zipfile.ZipFile(z).extractall(MINGIT_DIR)
    return g


def _force_rmtree(path: pathlib.Path):
    def onerr(func, pth, exc):
        try:
            os.chmod(pth, stat.S_IWRITE)
            func(pth)
        except Exception:
            pass
    for _ in range(3):
        if not path.exists():
            return
        shutil.rmtree(path, onerror=onerr)


def run(args, env=None, check=False):
    print("  $ " + " ".join("ghp_***" if "ghp_" in str(a) else str(a) for a in args))
    p = subprocess.run([str(a) for a in args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    for line in (p.stdout or "").strip().splitlines()[-2:]:
        print("    " + line[:150])
    if p.returncode != 0:
        print("    STDERR: " + (p.stderr or "")[-400:])
        if check:
            raise SystemExit("命令失败")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", action="store_true")
    ap.add_argument("--token", default="")
    ap.add_argument("--skip-push", action="store_true")
    ap.add_argument("--skip-private", action="store_true")
    ap.add_argument("--skip-meta", action="store_true")
    a = ap.parse_args()

    token = a.token or os.environ.get("GITHUB_TOKEN") or ""
    if not token and a.prompt:
        token = getpass.getpass("粘贴 GitHub token（需 repo+admin 权限，不可见）：").strip()
    if not token:
        raise SystemExit("需要 token")
    if not token.isascii():
        raise SystemExit("token 含非 ASCII 字符（占位符没换？）")

    me = _req(API + "/user", token)
    print("token 身份:", me.get("login"))
    if me.get("login") != "gbtweilai-star":
        print("⚠️ 该 token 不是仓库 owner，可能无权改可见性")

    # ① 推送本地真身（含装修）
    if not a.skip_push:
        git = git_exe()
        if WORK.is_dir():
            _force_rmtree(WORK)
        url = "https://x-access-token:%s@github.com/%s.git" % (token, REPO)
        run([git, "clone", "--depth", "1", url, WORK], check=True)
        for child in WORK.iterdir():
            if child.name == ".git":
                continue
            if child.is_dir():
                _force_rmtree(child)
            else:
                child.unlink()
        n = 0
        for p in ROOT.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if rel.split("/")[0] in SKIP_TOP or p.suffix.lower() in SKIP_EXT or rel.endswith(".pyc"):
                continue
            dst = WORK / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            n += 1
        print("拷贝本地文件:", n)
        env = dict(os.environ, GIT_AUTHOR_NAME="gbt-sync", GIT_AUTHOR_EMAIL="gbt@local",
                   GIT_COMMITTER_NAME="gbt-sync", GIT_COMMITTER_EMAIL="gbt@local",
                   PATH=str(git.parent) + os.pathsep + os.environ.get("PATH", ""))
        run([git, "-C", WORK, "add", "-A"], env=env, check=True)
        st = run([git, "-C", WORK, "status", "--porcelain"], env=env)
        changed = len([l for l in (st.stdout or "").splitlines() if l.strip()])
        print("变更文件:", changed)
        if changed:
            run([git, "-C", WORK, "commit", "-m",
                 "docs(repo): 装修——README 专业版 + CI + Issue/PR 模板 + 能力介绍(docs/90)"],
                env=env, check=True)
            run([git, "-C", WORK, "push", "origin", "HEAD:main"], env=env, check=True)
            print("已推送")

    # ② 设为私人
    if not a.skip_private:
        r = _req(API + "/repos/" + REPO, token, "PATCH", {"private": True})
        print("visibility -> private:", r.get("private"))

    # ③ 元信息（排行榜/搜索都用它）
    if not a.skip_meta:
        r = _req(API + "/repos/" + REPO, token, "PATCH",
                 {"description": DESCRIPTION, "homepage": HOMEPAGE, "topics": TOPICS})
        print("description/homepage/topics 已更新 | topics:", r.get("topics"))

    _force_rmtree(SCRATCH)
    print("过程目录已清理")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
