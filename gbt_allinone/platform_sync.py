"""GBT小土豆V8 · 平台状态只读同步（read-only）

主人 2026-11-02：「下一步」——提交后平台会改状态（triaged/duplicate/paid），本地要能只读回填。

安全口径：
  · **只读**：只发 GET，绝不写平台；
  · 真平台需要 token（env），没 token 直接拒绝，不猜；
  · 状态回填走本地状态机（bounty.set_status），非法流转会被拒——不硬塞；
  · 每次同步写 `state/bounty/platform-sync.jsonl` 审计；
  · 目前支持 provider = mock（本地靶场用）/ hackerone / bugcrowd（需自己填 base_url+token_env）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gbt_allinone import bounty as B  # noqa: E402
from gbt_allinone import bounty_core as core  # noqa: E402

STORE = ROOT / "state" / "bounty"
SYNC_LOG = STORE / "platform-sync.jsonl"
PLATFORMS = STORE / "platforms.json"

DEFAULT_PLATFORMS = {
    "mock": {"base_url": "http://127.0.0.1:18990", "token_env": "GBT_MOCK_PLATFORM_TOKEN",
             "token_default": "MOCK-TOKEN", "read_only": True},
    "hackerone": {"base_url": "https://api.hackerone.com/v1", "token_env": "HACKERONE_TOKEN",
                  "read_only": True},
    "bugcrowd": {"base_url": "https://api.bugcrowd.com", "token_env": "BUGCROWD_TOKEN",
                 "read_only": True},
}

# 平台状态 → 本地状态机
STATUS_MAP = {
    "new": "submitted", "submitted": "submitted", "open": "submitted",
    "triaged": "triaged", "accepted": "triaged", "valid": "triaged",
    "duplicate": "duplicate", "duplicated": "duplicate",
    "resolved": "paid", "fixed": "paid", "paid": "paid", "bounty_paid": "paid",
    "closed": "closed", "informative": "closed", "not-applicable": "closed",
}


def _load_platforms() -> dict:
    try:
        return json.loads(PLATFORMS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return DEFAULT_PLATFORMS


def _token(conf: dict) -> str:
    env = conf.get("token_env")
    if env and os.environ.get(env):
        return os.environ[env]
    return str(conf.get("token_default") or "")


def _get(conf: dict, path: str, timeout: float = 8.0) -> dict:
    url = conf.get("base_url", "").rstrip("/") + path
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + _token(conf),
        "Accept": "application/json",
        "User-Agent": "gbt-platform-sync/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "status": r.status,
                    "body": json.loads(r.read().decode("utf-8", "replace"))}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)[:160]}


def _walk(current: str, target: str) -> list | None:
    """状态机最短路径（BFS）；不可达返回 None。"""
    if current == target:
        return []
    seen, q = {current: None}, [current]
    while q:
        cur = q.pop(0)
        for nxt in core.TRANSITIONS.get(cur, set()):
            if nxt in seen:
                continue
            seen[nxt] = cur
            if nxt == target:
                path, node = [], target
                while node is not None:
                    path.append(node)
                    node = seen[node]
                path = list(reversed(path))
                return path[1:]  # 去掉起点（当前状态），只回填需要走的步
            q.append(nxt)
    return None


def sync(provider: str = "mock", dry_run: bool = True, program: str = "") -> dict:
    conf_all = _load_platforms()
    conf = conf_all.get(provider)
    if not conf:
        return {"ok": False, "reason": "未知 provider：%s（可选 %s）"
                % (provider, sorted(conf_all))}
    token = _token(conf)
    if not token:
        return {"ok": False, "reason": "缺 token（env %s）——真平台只读同步也必须显式授权"
                % conf.get("token_env")}
    findings = B.list_findings()["findings"]
    if program:
        findings = [f for f in findings if f.get("program") == program]
    # 只同步已提交过的（draft 不查平台）
    todo = [f for f in findings if f.get("status") in ("submitted", "triaged", "duplicate")]
    checked, updated, skipped, errors, transitions = 0, [], [], [], []
    for f in todo:
        fid = f.get("id")
        r = _get(conf, "/api/v1/reports/" + urllib.parse.quote(str(fid)))
        checked += 1
        if not r.get("ok"):
            reason = str(r.get("reason") or "")
            if "404" in reason:
                skipped.append({"finding": fid, "reason": "平台没有该报告（404）"})
            else:
                errors.append({"finding": fid, "error": reason})
            continue
        body = r.get("body") or {}
        pstatus = str(body.get("status") or body.get("state") or "").lower()
        target = STATUS_MAP.get(pstatus)
        if not target:
            skipped.append({"finding": fid, "platform_status": pstatus, "reason": "未知状态"})
            continue
        cur = f.get("status")
        if cur == target:
            skipped.append({"finding": fid, "platform_status": pstatus, "reason": "已是最新"})
            continue
        path = _walk(cur, target)
        if path is None:
            skipped.append({"finding": fid, "platform_status": pstatus,
                            "reason": "本地状态机不可达 %s→%s" % (cur, target)})
            continue
        if dry_run:
            transitions.append({"finding": fid, "from": cur, "to": target, "path": path,
                               "platform_status": pstatus, "dry_run": True})
            continue
        for step in path:
            rr = B.set_status(fid, step, note="platform-sync %s→%s" % (provider, step))
            if not rr.get("ok"):
                errors.append({"finding": fid, "step": step, "error": rr.get("reason")})
                break
        else:
            transitions.append({"finding": fid, "from": cur, "to": target, "path": path,
                                "platform_status": pstatus})
            updated.append(fid)
    out = {"ok": not errors, "provider": provider, "program": program, "dry_run": bool(dry_run),
           "checked": checked, "updated": len(updated), "updated_ids": updated,
           "skipped": skipped[:20], "errors": errors[:20],
           "transitions": transitions[:30],
           "notice": "只读同步；平台侧没有写入；状态回填走本地状态机"}
    if not dry_run:
        STORE.mkdir(parents=True, exist_ok=True)
        with SYNC_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **out},
                                ensure_ascii=False) + "\n")
    return out


if __name__ == "__main__":
    prov = sys.argv[1] if len(sys.argv) > 1 else "mock"
    dry = "--apply" not in sys.argv
    print(json.dumps(sync(prov, dry_run=dry), ensure_ascii=False, indent=2))
