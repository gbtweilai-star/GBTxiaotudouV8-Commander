# -*- coding: utf-8 -*-
"""把 GitHub 仓与**本地真身**做一次全面对齐（不是补丁，是全量清扫）。

口径：
  · 以本地工作仓为唯一真相（排除运行态：state/ store/ dist/ logs/ vaults/ vendor/ .scratch 等）；
  · 远程有、本地没有 → 删（旧件）；
  · 本地有、远程没有 → 传（新件）；
  · 同路径内容不同 → 用本地版本覆盖（旧版本）；
  · 一次 commit 完成，历史保留。

用法：
    python tools/github-full-sync.py --dry-run              # 只算差异（匿名可跑）
    python tools/github-full-sync.py --prompt --apply       # 静默输入 token 后执行
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import getpass
import hashlib
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
REPO = "gbtweilai-star/GBTxiaotudouV8-Commander"
BRANCH = "main"
ROOT = pathlib.Path(__file__).resolve().parents[1]

# 运行态/产物：永不上传
SKIP_TOP = {"state", "store", "dist", "runtime", "logs", "vaults", "vendor", ".git",
            "__pycache__", "node_modules", ".scratch", "outputs"}
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


def _req(url, token=None, method="GET", body=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("User-Agent", "dsh-sync")
    r.add_header("Accept", "application/vnd.github+json")
    if token:
        try:
            token.encode("ascii")
        except UnicodeEncodeError:
            raise SystemExit("token 含非 ASCII 字符（占位符没换？）请用 --prompt 重新输入")
        r.add_header("Authorization", "Bearer " + token)
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=120) as x:
            b = x.read()
    except urllib.error.HTTPError as e:
        raise SystemExit("HTTP %s %s: %s" % (e.code, url.split('/')[-1], e.read()[:200]))
    return b.decode("utf-8", "replace") if raw else (json.loads(b) if b.strip() else {})


def blob_sha(path: pathlib.Path) -> str:
    data = path.read_bytes()
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def local_files():
    out = {}
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.split("/")[0] in SKIP_TOP:
            continue
        if p.suffix.lower() in SKIP_EXT:
            continue
        if rel.endswith(".pyc"):
            continue
        try:
            out[rel] = p
        except Exception:
            pass
    # .gitignore：确保带阻断块
    gi = ROOT / ".gitignore"
    if gi.is_file():
        txt = gi.read_text(encoding="utf-8", errors="ignore")
        if "2026-11-01 仓库清理" not in txt:
            gi.write_text(txt.rstrip() + "\n" + GITIGNORE_BLOCK, encoding="utf-8")
            out[".gitignore"] = gi
    return out


def plan(token=None):
    ref = _req("%s/repos/%s/git/ref/heads/%s" % (API, REPO, BRANCH), token)
    head = ref["object"]["sha"]
    commit = _req("%s/repos/%s/git/commits/%s" % (API, REPO, head), token)
    tree = _req("%s/repos/%s/git/trees/%s?recursive=1" % (API, REPO, commit["tree"]["sha"]), token)
    remote = {it["path"]: it["sha"] for it in tree["tree"] if it["type"] == "blob"}
    local = local_files()
    loc_sha = {}
    for rel, p in local.items():
        try:
            loc_sha[rel] = blob_sha(p)
        except Exception:
            pass
    upload = [r for r in loc_sha if r not in remote or remote[r] != loc_sha[r]]
    delete = [r for r in remote if r not in loc_sha]
    return {"head": head, "tree": commit["tree"]["sha"], "remote_n": len(remote),
            "local_n": len(loc_sha), "upload": upload, "delete": delete,
            "local": local, "loc_sha": loc_sha}


def create_blob(path: pathlib.Path, token: str) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode()
    out = _req("%s/repos/%s/git/blobs" % (API, REPO), token, "POST",
               {"content": b64, "encoding": "base64"})
    return out["sha"]


def apply(p, token):
    entries = []
    jobs = [p["local"][rel] for rel in p["upload"]]
    print("上传 blob：%d 个（并发 8）…" % len(jobs))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(create_blob, pth, token): rel
                for pth, rel in zip(jobs, p["upload"])}
        done = 0
        for fut in concurrent.futures.as_completed(futs):
            rel = futs[fut]
            sha = fut.result()
            entries.append({"path": rel, "mode": "100644", "type": "blob", "sha": sha})
            done += 1
            if done % 200 == 0:
                print("  …%d" % done)
    for rel in p["delete"]:
        entries.append({"path": rel, "mode": "100644", "type": "blob", "sha": None})
    print("建树：%d 条变更 …" % len(entries))
    tree = _req("%s/repos/%s/git/trees" % (API, REPO), token, "POST",
                {"base_tree": p["tree"], "tree": entries})
    commit = _req("%s/repos/%s/git/commits" % (API, REPO), token, "POST",
                  {"message": ("chore(repo): 全面清扫——以本地真身为唯一真相（上传 %d / 删旧 %d）"
                               % (len(p["upload"]), len(p["delete"]))),
                   "tree": tree["sha"], "parents": [p["head"]]})
    upd = _req("%s/repos/%s/git/refs/heads/%s" % (API, REPO, BRANCH), token, "PATCH",
               {"sha": commit["sha"], "force": False})
    return {"commit": commit["sha"], "tree": tree["sha"], "ref": upd.get("object", {}).get("sha"),
            "uploaded": len(p["upload"]), "deleted": len(p["delete"])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--token", default="")
    ap.add_argument("--prompt", action="store_true")
    a = ap.parse_args()

    token = a.token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not token and a.prompt:
        token = getpass.getpass("粘贴 GitHub token（不可见，回车确认）：").strip()
    if token and not token.isascii():
        raise SystemExit("token 含非 ASCII 字符（占位符没换？）")

    p = plan(token)
    print("远程文件 %d · 本地文件 %d" % (p["remote_n"], p["local_n"]))
    print("需上传/更新：%d" % len(p["upload"]))
    print("需删除（远程旧件）：%d" % len(p["delete"]))
    for rel in p["delete"][:20]:
        print("  - " + rel)
    plan_file = ROOT / "state" / "github-full-sync-plan.json"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(json.dumps({"upload": p["upload"], "delete": p["delete"],
                                     "remote_n": p["remote_n"], "local_n": p["local_n"]},
                                    ensure_ascii=False, indent=1), encoding="utf-8")
    print("清单：%s" % plan_file)
    if a.apply:
        if not token:
            raise SystemExit("要 --apply 必须有 token（--prompt 或 GITHUB_TOKEN）")
        r = apply(p, token)
        print("已提交：" + json.dumps(r, ensure_ascii=False))
        return 0
    print("（预览模式：确认后加 --prompt --apply）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
