# -*- coding: utf-8 -*-
"""把发布件一次性推到 GitHub（Git Data API，不 clone 大仓库）。

用法（token 只从环境变量读，绝不打印）：
  $env:GH_TOKEN = (gh auth token --user gbtweilai-star).Trim()
  py -3.14 -X utf8 tools/codex-scripts/push-open-source.py \
      --repo gbtweilai-star/GBTxiaotudouV8moxing --dir outputs/open-source-release

纪律：
  · 只**新增/替换**本目录里的文件（base_tree 合并），不删仓库里已有的东西；
  · 推之前逐条打印将要写的路径；推完**立刻回读**一个文件做验收（不信"应该成功"）。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

API = "https://api.github.com"


def call(method: str, path: str, body: dict | None, token: str):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "gbt-open-source/1.0",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:500].decode("utf-8", "replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--message", default="docs: 发布 GBT小土豆V8 总指挥模型（341 位能力全量 + 评测 + 部署）")
    a = ap.parse_args()

    token = (os.environ.get("GH_TOKEN") or "").strip()
    if not token:
        print("缺 GH_TOKEN：先 set GH_TOKEN=<gbtweilai-star 的 token>")
        return 1

    root = pathlib.Path(a.dir)
    if not root.is_dir():
        print("目录不存在：", root)
        return 1

    # 只推"人写的件"：字节码/缓存/编辑器垃圾一律不推（2026-10-21 真栽过：把
    # `tests/__pycache__/*.pyc` 推上了公网仓库 —— 这类件在 PR 里是噪声，别人一看就觉得不专业）。
    SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git", ".idea", ".vscode"}
    SKIP_SUFFIX = (".pyc", ".pyo", ".pyd", ".log", ".tmp", ".bak", ".swp", ".DS_Store")
    def wanted(p: pathlib.Path) -> bool:
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            return False
        name = rel.name
        if name.endswith(SKIP_SUFFIX) or name == ".DS_Store":
            return False
        return True

    all_files = sorted(p for p in root.rglob("*") if p.is_file())
    files = [p for p in all_files if wanted(p)]
    skipped = [p for p in all_files if not wanted(p)]
    print("待写入 %d 个文件（跳过 %d 个缓存/垃圾件）：" % (len(files), len(skipped)))
    for p in files:
        print("  " + p.relative_to(root).as_posix())
    if skipped:
        print("  跳过：" + "、".join(p.relative_to(root).as_posix() for p in skipped[:8])
              + ("…" if len(skipped) > 8 else ""))
    if not files:
        return 1

    st, ref = call("GET", "/repos/%s/git/ref/heads/%s" % (a.repo, a.branch), None, token)
    if st != 200:
        print("取 ref 失败：", st, ref)
        return 1
    head_sha = ref["object"]["sha"]

    st, commit = call("GET", "/repos/%s/git/commits/%s" % (a.repo, head_sha), None, token)
    if st != 200:
        print("取 commit 失败：", st, commit)
        return 1
    base_tree = commit["tree"]["sha"]
    print("当前 HEAD %s（tree %s）" % (head_sha[:10], base_tree[:10]))

    entries = []
    for p in files:
        raw = p.read_bytes()
        st, blob = call("POST", "/repos/%s/git/blobs" % a.repo,
                        {"content": base64.b64encode(raw).decode(), "encoding": "base64"}, token)
        if st != 201:
            print("建 blob 失败：%s → %s %s" % (p.name, st, blob))
            return 1
        entries.append({"path": p.relative_to(root).as_posix(), "mode": "100644",
                        "type": "blob", "sha": blob["sha"]})
    print("blob 建好 %d 个" % len(entries))

    st, tree = call("POST", "/repos/%s/git/trees" % a.repo,
                    {"base_tree": base_tree, "tree": entries}, token)
    if st != 201:
        print("建 tree 失败：", st, tree)
        return 1

    st, newc = call("POST", "/repos/%s/git/commits" % a.repo,
                    {"message": a.message, "tree": tree["sha"], "parents": [head_sha]}, token)
    if st != 201:
        print("建 commit 失败：", st, newc)
        return 1
    print("新 commit：%s" % newc["sha"][:10])

    st, upd = call("PATCH", "/repos/%s/git/refs/heads/%s" % (a.repo, a.branch),
                   {"sha": newc["sha"], "force": False}, token)
    if st not in (200, 201):
        print("更新分支失败：", st, upd)
        return 1
    print("分支已更新 → %s" % upd["object"]["sha"][:10])

    # 验收：**内容寻址**逐文件核对（本地算 git blob sha，与远端 contents 的 sha 比对）。
    # 2026-10-21 修：此前这里"回读 README 前 3 行"，两种情况下都会失败却说不清原因 ——
    #   · 大文件 contents API 不回 content（encoding=none）⇒ 解出空串 ⇒ 打印出"空 3 行"；
    #   · 一旦那一步不是 200，脚本直接 return 1，**明明推送已经成功**（分支已移动）却报失败。
    # 现在：比 sha（内容寻址，没法糊弄）；失败把上游 status+原话打出来；且**只报真失败**。
    def _blob_sha(data: bytes) -> str:
        import hashlib
        return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()

    probes = [p for p in files if p.relative_to(root).as_posix() in
              ("README.md", "index.html", "data/capability-live-test.json")] or files[:3]
    bad = []
    print("回读核对（内容寻址）：")
    for p in probes:
        rel = p.relative_to(root).as_posix()
        st, got = call("GET", "/repos/%s/contents/%s?ref=%s" % (a.repo, rel, newc["sha"]),
                       None, token)
        if st != 200 or not isinstance(got, dict):
            bad.append((rel, "HTTP %s · %s" % (st, str(got)[:200])))
            continue
        want = _blob_sha(p.read_bytes())
        ok = got.get("sha") == want
        print("  %-34s %s  local=%s remote=%s"
              % (rel, "OK" if ok else "MISMATCH", want[:10], str(got.get("sha"))[:10]))
        if not ok:
            bad.append((rel, "sha 不一致 local=%s remote=%s" % (want, got.get("sha"))))
    if bad:
        print("⚠ 回读核对未通过（推送本身已落地，下面是逐文件原话）：")
        for rel, why in bad:
            print("  - %s：%s" % (rel, why))
        return 1

    print("PUSH_OK https://github.com/%s" % a.repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
