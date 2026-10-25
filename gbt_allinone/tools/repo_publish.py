# -*- coding: utf-8 -*-
# gbt-capability: repo_publish
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""repo_publish —— **远端发布面**（补 git_write 的另一半）。

## 为什么有这个件（主人在 2026-10-11 当场指出）
  万能插名册现读：tools 域 7 条里，版本库只有 `git_read`（只读）与 `git_write`（**只有 stage/commit**）。
  ⇒ **push 到远端 / 建仓 / 发 Release 这一整片，框架里根本没有能力位** ✗
  ⇒ 于是前面全靠**手搓 git push / wrangler / python 一行流** —— 不过门、没审计、没信封。
  **正确做法：把洞补成能力位**（本文件），而不是继续手搓。

## 口径（照本仓铁律）
  · **不可逆外部动作 ⇒ 过 `deploy_publish` 一次性门**（AI 无权自发放行）；
  · **出网硬钉**：只许 https + 主机白名单（github.com / api.github.com / huggingface.co）；
  · **凭据只报"已配/未配"或掩码**，**永不进读数、永不进日志**（本件第一版就吃过这个亏）；
  · **只追加落账**：每次 publish 落 store/repo_publish/ledger.jsonl（目标/分支/提交/时间/结果）；
  · **不假装**：没凭据/没权限 ⇒ 如实报，不许念成成功。

## ops
  status  只读：目标仓 / 凭据是否就位（掩码）/ 工作区状态
  plan    只读：**将要推什么**（分支、提交数、文件数、体积）——先看再动
  push    写（过 deploy_publish 门）：git push 到白名单远端
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import time
import urllib.parse

_ROOT = pathlib.Path(__file__).resolve().parents[2]

_ALLOWED_HOSTS = {"github.com", "api.github.com", "huggingface.co"}
_MAX_REPORT = 60


def _store() -> pathlib.Path:
    d = os.environ.get("GBT_STORE_DIR")
    base = pathlib.Path(d) if d else (_ROOT / "gbt_allinone" / "store")
    p = base / "repo_publish"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ledger(row: dict) -> None:
    with (_store() / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + chr(10))


def _git(*args: str, cwd: str | None = None, timeout: int = 120) -> dict:
    try:
        r = subprocess.run(["git", *args], cwd=cwd or str(_ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return {"rc": r.returncode, "out": (r.stdout or "").strip(), "err": (r.stderr or "").strip()}
    except Exception as e:                                  # noqa: BLE001
        return {"rc": -1, "out": "", "err": "%s: %s" % (type(e).__name__, str(e)[:120])}


def _remote() -> dict:
    r = _git("remote", "-v")
    urls = []
    for ln in (r.get("out") or "").splitlines():
        parts = ln.split()
        if len(parts) >= 2 and parts[1] not in urls:
            urls.append(parts[1])
    host = ""
    for u in urls:
        h = urllib.parse.urlparse(u).hostname or ""
        if h:
            host = h
            break
    return {"urls": urls, "host": host, "allowed": host in _ALLOWED_HOSTS if host else False}


def _cred_state() -> dict:
    """只报'有没有'，**不取值**（掩码也不回显全文）。"""
    env_hits = [k for k in ("GITHUB_TOKEN", "GH_TOKEN", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")
                if os.environ.get(k)]
    return {"env_已配": env_hits,
            "说明": "值一律不回显；git 侧凭据由 git credential helper 管，本件不读、不打印"}


def status(extra: dict | None = None) -> dict:
    rem = _remote()
    br = _git("rev-parse", "--abbrev-ref", "HEAD")
    st = _git("status", "--porcelain")
    return {"ok": True, "op": "status", "repo": str(_ROOT),
            "remote": rem, "branch": br.get("out"),
            "dirty_files": len([l for l in (st.get("out") or "").splitlines() if l.strip()]),
            "credentials": _cred_state(),
            "rule": "push 是**不可逆外部动作** ⇒ 过 deploy_publish 一次性门；凭据永不回显"}


def plan(extra: dict | None = None) -> dict:
    rem = _remote()
    if not rem["allowed"]:
        return {"ok": False, "op": "plan", "error": "远端不在白名单（%s）：%s" % (rem.get("host") or "-", rem["urls"]),
                "allowed_hosts": sorted(_ALLOWED_HOSTS)}
    ahead = _git("rev-list", "--count", "@{u}..HEAD")
    files = _git("diff", "--name-only", "@{u}..HEAD")
    return {"ok": True, "op": "plan", "remote": rem["urls"], "host": rem["host"],
            "将推的提交数": ahead.get("out") or "(无上游/未知)",
            "将推的文件": (files.get("out") or "").splitlines()[:_MAX_REPORT],
            "文件数": len([l for l in (files.get("out") or "").splitlines() if l.strip()]),
            "怎么推": "push（需 deploy_publish 授权：python -m gbt_allinone auth grant --scope deploy_publish --ttl 600）"}


def push(extra: dict | None = None) -> dict:
    e = dict(extra or {})
    rem = _remote()
    if not rem["allowed"]:
        return {"ok": False, "op": "push", "error": "远端不在白名单：%s" % (rem["urls"] or "-")}
    branch = str(e.get("branch") or _git("rev-parse", "--abbrev-ref", "HEAD").get("out") or "").strip()
    url = str(e.get("url") or (rem["urls"][0] if rem["urls"] else ""))
    h = urllib.parse.urlparse(url).hostname or ""
    if h not in _ALLOWED_HOSTS:
        return {"ok": False, "op": "push", "error": "目标主机 %r 不在白名单" % h}
    if not branch or branch == "HEAD":
        return {"ok": False, "op": "push", "error": "拿不到分支名（detached?) —— 点名 branch 再推"}
    t0 = time.time()
    r = _git("push", url, "%s:%s" % (branch, branch), timeout=900)
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "op": "push", "url": url, "branch": branch,
           "rc": r["rc"], "ok": r["rc"] == 0, "ms": int((time.time() - t0) * 1000),
           "err": (r["err"] or "")[:300], "out": (r["out"] or "")[:300]}
    _ledger(row)
    return {"ok": r["rc"] == 0, "op": "push", "url": url, "branch": branch,
            "stdout": (r["out"] or "")[:600], "stderr": (r["err"] or "")[:400],
            "ledger": str(_store() / "ledger.jsonl"), "ms": row["ms"]}


def run(payload: dict | None = None) -> dict:
    p = dict(payload or {})
    op = str(p.get("op") or "status").strip().lower()
    if op == "status":
        return status(p)
    if op == "plan":
        return plan(p)
    if op == "push":
        return push(p)
    return {"ok": False, "fail_closed": True, "error": "user_error: 未列出的 op（fail-closed）",
            "ops": ["status", "plan", "push"]}
