# -*- coding: utf-8 -*-
"""Cloudflare 多账号「登入授权」检查器（OAuth 路线，不碰 API 密钥）。

主人令 2026-10-23：「你直接做成账户登入授权不就好了，不做密钥密钥容易泄露」
—— 实测依据（本机，2026-10-23）：把 `USERPROFILE` 指向独立目录再跑 `wrangler whoami`，
它会如实报 `Not logged in` ⇒ **一个目录 = 一个账号的 OAuth 会话**，互不串。
所以 10 个账号 = 10 个目录 + 10 次浏览器授权，全程**不存在明文密钥**。

本器只做两件事（都只读）：
  1. 列出 `CF_OAUTH_ROOT` 下每个账号目录的登录状态（已登 / 未登 / 目录缺）
  2. 已登的报账号名与掩码（**不打印**任何 token）

用法：
  py -3 tools/codex-scripts/cf-oauth-check.py
  py -3 tools/codex-scripts/cf-oauth-check.py --root D:\\cf-oauth --want 10
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ACCOUNT_LINE = re.compile(r"│\s*(.+?)\s*│\s*([0-9a-f]{32})\s*│")


def check_profile(path: str) -> dict:
    """在一个独立 HOME 里跑 whoami；只读，不改任何东西。"""
    env = dict(os.environ)
    env["USERPROFILE"] = path
    env["HOME"] = path
    env.pop("CLOUDFLARE_API_TOKEN", None)      # 有令牌就会盖掉 OAuth 读数，这里必须去掉
    try:
        out = subprocess.run(["wrangler", "whoami"], capture_output=True, text=True,
                             timeout=90, env=env, shell=True).stdout
    except Exception as exc:                                    # noqa: BLE001
        return {"logged_in": False, "why": str(exc)[:120]}
    if "Not logged in" in out:
        return {"logged_in": False, "why": "未登录（目录里没有会话）"}
    rows = ACCOUNT_LINE.findall(out)
    email = re.search(r"associated with the email\s+(\S+@\S+)", out)
    return {
        "logged_in": bool(rows),
        "email": email.group(1) if email else None,
        "accounts": [{"name": n.strip(), "id_mask": i[:8] + "****"} for n, i in rows],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get("CF_OAUTH_ROOT", os.path.expanduser("~/.cf-oauth")))
    ap.add_argument("--want", type=int, default=10)
    a = ap.parse_args()

    root = a.root
    if not os.path.isdir(root):
        print(json.dumps({
            "ok": False,
            "root": root,
            "why": "根目录不存在。先跑 deploy/cloud-10/lanes/cf-oauth-login.cmd 建立并逐个授权",
            "how": "该 cmd 会为每个账号建一个独立 HOME，再执行 wrangler login（浏览器里选对应账号）",
        }, ensure_ascii=False, indent=1))
        return 2

    rows = []
    for i in range(1, a.want + 1):
        d = os.path.join(root, "acct-%02d" % i)
        if not os.path.isdir(d):
            rows.append({"slot": i, "dir": d, "exists": False})
            continue
        info = check_profile(d)
        rows.append({"slot": i, "dir": d, "exists": True, **info})

    logged = [r for r in rows if r.get("logged_in")]
    emails = [r.get("email") for r in logged if r.get("email")]
    dup = sorted({e for e in emails if emails.count(e) > 1})
    print(json.dumps({
        "root": root,
        "slots": a.want,
        "logged_in": len(logged),
        "distinct_emails": len(set(emails)),
        "duplicate_emails": dup,
        "rows": rows,
        "verdict": ("齐了：%d 个账号各自独立会话" % len(logged)) if len(logged) == a.want
                   else ("还缺 %d 个（未登录或目录缺）" % (a.want - len(logged))),
    }, ensure_ascii=False, indent=1))
    return 0 if len(logged) == a.want else 1


if __name__ == "__main__":
    raise SystemExit(main())
