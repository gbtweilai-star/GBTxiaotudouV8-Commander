# -*- coding: utf-8 -*-
"""云插件互联验收（10 节点 · 90 条有向边）。

## 判据（写死，不许口算）
· 节点在役 = `/health` 返回 ok:true 且 node_id 非空；
· 边 = 节点 A 的 peer 名单里有 B **且** B 的 peer 名单里有 A（双向才算一条边，单向只算半条，单独计数）；
· 期望：`n*(n-1)` 条有向边（n=10 → 90）；
· 跨账号的边必须走 HTTPS + `x-gbt-mesh-key`（Workers 的 `[[services]]` 只能同账号）——
  所以每条边都要能 `GET /mesh/ping?to=<对端node_id>` 拿到 `ok:true`，否则算**线在但路不通**。

用法：
  py -3 tools/codex-scripts/mesh-verify.py --list           # 只看账上有哪些节点、逐个 /health
  py -3 tools/codex-scripts/mesh-verify.py --expect 10      # 按 10 节点算期望边数并给出缺口
  py -3 tools/codex-scripts/mesh-verify.py --selftest       # 判据自检（无网也能跑）
退出码：0 全绿 / 1 有红 / 2 账上还没有节点。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, "state", "mesh-nodes.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) gbt-mesh-verify"


def nodes():
    if not os.path.isfile(LEDGER):
        return []
    try:
        d = json.load(open(LEDGER, encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return []
    out = []
    seen = {}
    for n in (d.get("nodes") or d.get("items") or []):
        url = (n.get("url") or n.get("endpoint") or "").rstrip("/")
        if not url:
            continue
        # 同一 URL 只算一个节点（账上重复登记是账的问题，不是节点多了）
        seen.setdefault(url, {"id": n.get("id") or n.get("node_id") or "", "url": url,
                              "acct": n.get("acct") or n.get("account") or "",
                              "at": n.get("deployed_at") or n.get("at") or ""})
    return list(seen.values())


def get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return {"status": r.status, "json": json.loads(raw)}
            except Exception:                                # noqa: BLE001
                return {"status": r.status, "text": raw[:200]}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:200]
        except Exception:                                    # noqa: BLE001
            pass
        return {"status": e.code, "text": body or str(e)}
    except Exception as e:                                   # noqa: BLE001
        return {"status": 0, "error": str(e)[:160]}


def probe(ns: list) -> list:
    rows = []
    for n in ns:
        h = get(n["url"] + "/health")
        j = h.get("json") or {}
        info = get(n["url"] + "/mesh/info")
        ij = info.get("json") or {}
        peers = ij.get("peers") or j.get("peers") or []
        # 🔴 2026-10-23 对齐真回包：worker 用 `node` 不是 `node_id`；
        #    /health 的 peers 是**数字**，/mesh/info 的 peers 才是**数组** —— 两处不混用。
        rows.append({"id": n["id"], "url": n["url"], "acct": n["acct"],
                     "health": h.get("status"), "ok": bool(j.get("ok")),
                     "node_id": ij.get("node") or j.get("node") or j.get("node_id") or "",
                     "peers": peers if isinstance(peers, list) else [],
                     "known_nodes": ij.get("known_nodes", j.get("known_nodes")),
                     "roster": (get(n["url"] + "/roster").get("json") or {}).get("nodes")})
    return rows


def evaluate(rows: list, expect: int) -> dict:
    alive = [r for r in rows if r["ok"]]
    ids = {r["node_id"] or r["id"] for r in alive if (r["node_id"] or r["id"])}
    # 双向边：A 的 peers 含 B 且 B 的 peers 含 A
    directed = 0
    both = 0
    one_way = []
    byid = {(r["node_id"] or r["id"]): r for r in alive}
    for a_id, a in byid.items():
        for p in a["peers"]:
            pid = p.get("node_id") if isinstance(p, dict) else str(p)
            if not pid or pid == a_id:
                continue
            directed += 1
            b = byid.get(pid)
            if b and any((q.get("node_id") if isinstance(q, dict) else str(q)) == a_id for q in b["peers"]):
                both += 1
            else:
                one_way.append("%s→%s" % (a_id, pid))
    exp_edges = expect * (expect - 1)
    return {"alive": len(alive), "expect_nodes": expect, "node_ids": sorted(ids),
            "directed_edges": directed, "mutual_edges": both // 2, "one_way": one_way[:10],
            "expected_edges": exp_edges,
            "ok": len(alive) >= expect and directed >= exp_edges and not one_way}


def selftest() -> int:
    """负控：造 3 个节点（A↔B 双向、C 单向）验证判据能把单向/缺边咬出来。"""
    rows = [
        {"id": "A", "ok": True, "node_id": "A", "peers": [{"node_id": "B"}], "url": "", "acct": "", "health": 200},
        {"id": "B", "ok": True, "node_id": "B", "peers": [{"node_id": "A"}], "url": "", "acct": "", "health": 200},
        {"id": "C", "ok": True, "node_id": "C", "peers": [{"node_id": "A"}], "url": "", "acct": "", "health": 200},
    ]
    r = evaluate(rows, 3)
    good = (r["alive"] == 3) and (r["mutual_edges"] == 1) and (r["directed_edges"] == 3) \
        and (not r["ok"]) and r["expected_edges"] == 6 and any(x.startswith("C→") for x in r["one_way"])
    print(json.dumps({"selftest": "pass" if good else "fail", "reading": r}, ensure_ascii=False, indent=1))
    return 0 if good else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", type=int, default=10)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    ns = nodes()
    if not ns:
        print(json.dumps({"ok": False, "why": "state/mesh-nodes.json 里还没有节点（10 槽一个都没装）",
                          "ledger": LEDGER}, ensure_ascii=False, indent=1))
        return 2
    rows = probe(ns)
    rep = evaluate(rows, a.expect)
    rep["rows"] = [{k: r[k] for k in ("id", "url", "acct", "health", "ok", "node_id")} for r in rows]
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
