# -*- coding: utf-8 -*-
"""用**便携 git**做全量同步（比 1095 次 API 上传稳得多：一次 clone + 一次 push）。

步骤：
 1. 下载 MinGit 到 `.scratch/mingit`（只需一次，约 50MB）；
 2. 匿名 clone 仓库到 `.scratch/repo-sync`（--depth 1）；
 3. 用本地真身覆盖工作区（排除运行态/产物/二进制）；
 4. `git add -A` → commit → push（token 只用于 push 的远端地址，不落盘）。

用法：
    python tools/git-portable-sync.py --dry-run
    python tools/git-portable-sync.py --prompt --apply
"""
from __future__ import annotations

import argparse
import getpass
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import urllib.request
import zipfile

REPO = "gbtweilai-star/GBTxiaotudouV8-Commander"
ROOT = pathlib.Path(__file__).resolve().parents[1]
WS = ROOT.parent
SCRATCH = WS / ".scratch" / "git-sync"
MINGIT_DIR = SCRATCH / "mingit"
WORK = SCRATCH / "repo-sync"
MINGIT_URL = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/MinGit-2.47.1-64-bit.zip"

SKIP_TOP = {"state", "store", "dist", "runtime", "logs", "vaults", "vendor", ".git",
            "__pycache__", "node_modules", ".scratch", "outputs", "pyembed"}
SKIP_EXT = {".pyc", ".pyo", ".gguf", ".zip", ".7z", ".gz", ".tar", ".mp4", ".webm",
            ".wav", ".db", ".pkl", ".pt", ".bin", ".log"}
GITIGNORE_BLOCK = """
# ── 2026-11-01 仓库清理：运行态/产物/二进制不进版本库 ──
state/
store/
dist/
runtime/
logs/
vaults/
vendor/
__pycache__/
*.pyc
*.gguf
*.zip
*.mp4
*.bin
*.db
*.jsonl
C:*/
"""




def _force_rmtree(path: pathlib.Path) -> None:
    """Windows 下 .git 里的对象是只读的，shutil.rmtree 会留残骸。"""
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
    if path.exists():  # 最后手段：改名再删
        try:
            path.rename(path.with_name(path.name + ".old%02d" % int(__import__("time").time())))
        except Exception:
            pass


def git_exe() -> pathlib.Path:
    g = MINGIT_DIR / "cmd" / "git.exe"
    if g.is_file():
        return g
    SCRATCH.mkdir(parents=True, exist_ok=True)
    z = SCRATCH / "mingit.zip"
    if not z.is_file():
        print("下载 MinGit（约 50MB）…")
        with urllib.request.urlopen(MINGIT_URL, timeout=300) as r, open(z, "wb") as f:
            shutil.copyfileobj(r, f, 1024 * 512)
    print("解压 MinGit …")
    with zipfile.ZipFile(z) as zf:
        zf.extractall(MINGIT_DIR)
    if not g.is_file():
        raise SystemExit("MinGit 解压后没找到 cmd/git.exe")
    return g


def run(args, cwd=None, env=None, check=False):
    print("  $ " + " ".join(str(a) for a in args))
    p = subprocess.run([str(a) for a in args], cwd=str(cwd) if cwd else None,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env)
    if p.stdout.strip():
        print("    " + p.stdout.strip().splitlines()[-1][:160])
    if p.returncode != 0:
        print("    STDERR: " + (p.stderr or "")[-400:])
        if check:
            raise SystemExit("命令失败: " + " ".join(str(a) for a in args))
    return p


def local_files():
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.split("/")[0] in SKIP_TOP or p.suffix.lower() in SKIP_EXT or rel.endswith(".pyc"):
            continue
        out.append(rel)
    gi = ROOT / ".gitignore"
    if gi.is_file():
        t = gi.read_text(encoding="utf-8", errors="ignore")
        if "2026-11-01 仓库清理" not in t:
            gi.write_text(t.rstrip() + "\n" + GITIGNORE_BLOCK, encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--prompt", action="store_true")
    ap.add_argument("--token", default="")
    a = ap.parse_args()

    git = git_exe()
    files = local_files()
    print("本地待同步文件:", len(files))

    if a.dry_run or not a.apply:
        if not WORK.is_dir():
            SCRATCH.mkdir(parents=True, exist_ok=True)
            run([git, "clone", "--depth", "1", "https://github.com/%s.git" % REPO, WORK], check=True)
        print("已 clone 到:", WORK)
        print("（预览完成；加 --prompt --apply 真正推送）")
        return 0

    token = a.token or os.environ.get("GITHUB_TOKEN") or ""
    if not token and a.prompt:
        token = getpass.getpass("粘贴 GitHub token（不可见，回车确认）：").strip()
    if not token:
        raise SystemExit("要 --apply 必须有 token")
    if not token.isascii():
        raise SystemExit("token 含非 ASCII 字符（占位符没换？）")

    url = "https://x-access-token:%s@github.com/%s.git" % (token, REPO)
    if WORK.is_dir():
        _force_rmtree(WORK)
    run([git, "clone", "--depth", "1", url, WORK], check=True)

    # 清掉 clone 里的受控文件（保留 .git），再用本地真身覆盖
    for child in WORK.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink()
    copied = 0
    for rel in files:
        src = ROOT / rel
        dst = WORK / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dst)
            copied += 1
        except Exception as e:
            print("  跳过", rel, e)
    print("已复制:", copied)

    env = dict(os.environ, GIT_AUTHOR_NAME="gbt-sync", GIT_AUTHOR_EMAIL="gbt@local",
               GIT_COMMITTER_NAME="gbt-sync", GIT_COMMITTER_EMAIL="gbt@local")
    run([git, "-C", WORK, "add", "-A"], env=env, check=True)
    st = run([git, "-C", WORK, "status", "--porcelain"], env=env)
    changed = len([l for l in (st.stdout or "").splitlines() if l.strip()])
    print("变更文件数:", changed)
    if changed == 0:
        print("没有变化，无需提交")
        return 0
    run([git, "-C", WORK, "commit", "-m",
         "chore(repo): 全面清扫——以本地真身为唯一真相（全量对齐）"], env=env, check=True)
    p = run([git, "-C", WORK, "push", "origin", "HEAD:main"], env=env)
    if p.returncode != 0:
        raise SystemExit("push 失败（看上面 STDERR）")
    sha = run([git, "-C", WORK, "rev-parse", "HEAD"], env=env).stdout.strip()
    print("已推送 commit:", sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
