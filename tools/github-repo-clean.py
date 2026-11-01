# -*- coding: utf-8 -*-
"""把远程 GitHub 仓整理干净（经 GitHub REST API，不需要装 git）。

背景：`gbtweilai-star/GBTxiaotudouV8-Commander` 根下混进了运行态与产物
（`state/` 里几千个 probe/bind/shards、`dist/`、`runtime/`、`logs/`、`vaults/`、`vendor/` 二进制、
甚至一个以 Windows 绝对路径命名的目录 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`），
仓库被撑到 ~200MB，看着头疼。

做法：
  · 用 Git Data API 读当前 main 的树；
  · 生成"删除清单"（JUNK 前缀 + 超过阈值的大文件 + 绝对路径目录）；
  · **只提交删除**（tree entries 用 sha=null），不动源码；
  · 同时把 `.gitignore` 换成能挡住这些路径的版本（不再二次变脏）。

用法：
    python tools/github-repo-clean.py --dry-run            # 只拉树、印清单（不需要 token）
    set GITHUB_TOKEN=ghp_xxx
    python tools/github-repo-clean.py --apply              # 创建 commit 并更新 main

参数：
    --repo   默认 gbtweilai-star/GBTxiaotudouV8-Commander
    --branch 默认 main
    --big-mb 超过这个大小的大文件也进删除清单（默认 2）
    --keep   额外保留的前缀（可多次）
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.request

API = "https://api.github.com"

# 这些前缀在公开仓里属于运行态/产物/二进制，不该进版本库
JUNK_PREFIXES = (
    "state/",
    "dist/",
    "runtime/",
    "logs/",
    "vaults/",
    "vendor/",
    "store/",
    "gbt_allinone/store/",
    "gbt_allinone/archived_logs/",
    "holo_pet_w3/_archive",
    "tools/_retired/",
    "worker.html",
)

GITIGNORE_BLOCK = """
# ── 2026-11-01 仓库整理：运行态/产物/二进制不进版本库 ──
state/
store/
gbt_allinone/store/
gbt_allinone/archived_logs/
dist/
runtime/
logs/
vaults/
vendor/
__pycache__/
*.pyc
*.pyo
*.gguf
*.zip
*.tar.gz
*.7z
*.png
*.jpg
*.jpeg
*.webp
*.wav
*.mp4
*.bin
*.db
*.log
*.jsonl
C:*/
"""


def _req(url: str, token: str | None = None, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", "dsh-repo-clean")
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        try:
            token.encode("ascii")
        except UnicodeEncodeError:
            raise SystemExit("token 里有中文/全角字符（多半是占位符没换）：%r\n"
                             "请换成真实的 ghp_ 开头 token，或用 --prompt 静默输入。" % token[:12])
        req.add_header("Authorization", "Bearer " + token)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
    return json.loads(raw) if raw.strip() else {}


def fetch_tree(repo: str, branch: str, token: str | None = None) -> tuple:
    ref = _req(f"{API}/repos/{repo}/git/ref/heads/{branch}", token)
    head = ref["object"]["sha"]
    commit = _req(f"{API}/repos/{repo}/git/commits/{head}", token)
    tree = _req(f"{API}/repos/{repo}/git/trees/{commit['tree']['sha']}?recursive=1", token)
    return head, commit["tree"]["sha"], tree


def plan(repo: str, branch: str, big_mb: float, keep: tuple, token: str | None = None) -> dict:
    head, tree_sha, tree = fetch_tree(repo, branch, token)
    items = tree.get("tree") or []
    dels, kept_big, by_top = [], [], {}
    big = int(big_mb * 1024 * 1024)
    for it in items:
        p = it["path"]
        by_top.setdefault(p.split("/")[0], [0, 0])
        by_top[p.split("/")[0]][0] += 1
        by_top[p.split("/")[0]][1] += it.get("size") or 0
        if any(p.startswith(k) for k in keep):
            continue
        if it.get("type") != "blob":
            continue
        junk = any(p.startswith(j) for j in JUNK_PREFIXES) or p.startswith("C:") or p.startswith("C:\\")
        if junk:
            dels.append({"path": p, "size": it.get("size") or 0, "why": "运行态/产物"})
        elif (it.get("size") or 0) > big:
            dels.append({"path": p, "size": it.get("size") or 0, "why": f"大文件 >{big_mb}MB"})
    tops = sorted(({"top": k, "files": v[0], "mb": round(v[1] / 1048576, 1)}
                   for k, v in by_top.items() if k not in ("", )), key=lambda x: -x["mb"])
    return {"repo": repo, "branch": branch, "head": head, "tree_sha": tree_sha,
            "total_files": len(items), "truncated": tree.get("truncated"),
            "delete_count": len(dels), "delete_mb": round(sum(d["size"] for d in dels) / 1048576, 1),
            "deletions": dels, "top_dirs": tops[:15], "keep": list(keep)}


def apply(repo: str, branch: str, p: dict, token: str) -> dict:
    """只提交删除 + 覆盖 .gitignore。"""
    # ① 删除项（blob 用 sha=null）
    entries = [{"path": d["path"], "mode": "100644", "type": "blob", "sha": None}
               for d in p["deletions"]]
    # ② .gitignore：在原文件后追加阻断块
    gi_path = ".gitignore"
    cur = ""
    try:
        c = _req(f"{API}/repos/{repo}/contents/{gi_path}?ref={branch}", token)
        cur = urllib.request.urlopen(
            urllib.request.Request(c["download_url"], headers={"User-Agent": "dsh"}), timeout=60
        ).read().decode("utf-8", "replace")
    except Exception:
        cur = ""
    new_gi = (cur.rstrip() + "\n" + GITIGNORE_BLOCK) if cur else GITIGNORE_BLOCK.lstrip()
    blob = _req(f"{API}/repos/{repo}/git/blobs", token, "POST",
                {"content": new_gi, "encoding": "utf-8"})
    entries.append({"path": gi_path, "mode": "100644", "type": "blob", "sha": blob["sha"]})

    tree = _req(f"{API}/repos/{repo}/git/trees", token, "POST",
                {"base_tree": p["tree_sha"], "tree": entries})
    commit = _req(f"{API}/repos/{repo}/git/commits", token, "POST",
                  {"message": "chore(repo): 清出运行态与产物（state/dist/runtime/logs/vaults/vendor/绝对路径目录），补 .gitignore",
                   "tree": tree["sha"], "parents": [p["head"]]})
    upd = _req(f"{API}/repos/{repo}/git/refs/heads/{branch}", token, "PATCH",
               {"sha": commit["sha"], "force": False})
    return {"commit": commit["sha"], "tree": tree["sha"], "ref": upd.get("object", {}).get("sha")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="gbtweilai-star/GBTxiaotudouV8-Commander")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--big-mb", type=float, default=2.0)
    ap.add_argument("--keep", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--token", default="", help="直接给 token（不推荐：会进命令历史）")
    ap.add_argument("--prompt", action="store_true", help="静默输入 token（推荐）")
    args = ap.parse_args()

    token = args.token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not token and args.prompt:
        import getpass
        token = getpass.getpass("粘贴 GitHub token（输入时不可见，回车确认）：").strip()
    if token and not token.isascii():
        raise SystemExit("token 含有非 ASCII 字符（常见原因：把示例里的占位符原样粘进来了）。\n"
                         "请用 --prompt 重新输入真实 token，或先 $env:GITHUB_TOKEN=\"ghp_xxx\" 再跑。")
    p = plan(args.repo, args.branch, args.big_mb, tuple(args.keep), token)

    print("== 仓库体检 ==")
    print(f"  {args.repo}@{args.branch} head={p['head'][:10]}")
    print(f"  文件总数 {p['total_files']}（truncated={p['truncated']}）")
    print(f"  建议删除 {p['delete_count']} 个文件 / {p['delete_mb']} MB")
    print("== 目录占用 Top ==")
    for t in p["top_dirs"]:
        print(f"  {t['top'][:42]:42s} {t['files']:6d} 文件 {t['mb']:8.1f} MB")
    print("== 删除样例（前 12）==")
    for d in p["deletions"][:12]:
        print(f"  - {d['path'][:88]}  ({d['size']//1024} KB, {d['why']})")

    out = pathlib.Path("state") / "github-clean-plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n清单已存：{out}")

    if args.apply:
        if not token:
            print("缺 GITHUB_TOKEN（需要 repo 写权限）", file=sys.stderr)
            return 2
        r = apply(args.repo, args.branch, p, token)
        print("已提交：", json.dumps(r, ensure_ascii=False))
        return 0
    if not args.dry_run:
        print("（预览模式；确认无误后加 --apply，并先设 GITHUB_TOKEN）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
