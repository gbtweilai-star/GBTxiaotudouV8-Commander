#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""omni_discover —— 万能插的「自动识别所有接口并生成插入」（2026-10-30）

主人令：万能插必须自己认出**所有**接口，并生成可插入的插座；否则名不副实。

做法（全实测，不靠配置）：
  ① 候选来源三路并集
     · 端口表（本仓已知服务 + A19 + 免费池）
     · 桥 /health 报出来的上游（每条上游本身就是插件）
     · 页面工人管线（state/local_results.jsonl 有记录 ⇒ 这条工人可派活）
  ② 每个候选真探一次：TCP → HTTP 路径探测（/health、/v1/models、/api/state）
  ③ 分类成插座：openai / bridge / panel / static / worker / a19
  ④ 生成 state/omni_sockets.json —— 带 kind / target / alive / protocol / 证据
  ⑤ 结论按"能用/半通/不通"三态写，不做覆盖率的美化

用法：
    python3 tools/omni_discover.py            # 人读
    python3 tools/omni_discover.py --json     # 机读
    python3 tools/omni_discover.py --bind     # 顺便把活着的写进 omni_plug 的插座表
"""
from __future__ import annotations

import argparse
import json
import pathlib
import socket
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "state" / "omni_sockets.json"

# ① 端口表：名字 → (端口, 探活路径, 期望协议)
PORTS = [
    ("a19",          1234, "/v1/models", "openai"),
    ("bridge",       8791, "/health",    "bridge"),
    ("panel",        8765, "/api/state", "panel"),
    ("index",        8792, "/health",    "static"),
    ("page",         8080, "/index.html", "static"),
    ("wgpu-page",    8081, "/holo_pet_w3/wgpu/local-llm.html", "static"),
    ("freepool",     3001, "/api/ping",  "openai"),
    ("async_gate",   8790, "/health",    "static"),
]


def _tcp(port: int, host="127.0.0.1", t=1.0) -> float | None:
    s = socket.socket()
    s.settimeout(t)
    t0 = time.time()
    try:
        s.connect((host, port))
        return round((time.time() - t0) * 1000, 1)
    except Exception:                                            # noqa: BLE001
        return None
    finally:
        s.close()


def _http(url: str, timeout=6, limit=400):
    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        body = r.read(limit)
        return r.status, body
    except Exception as exc:                                     # noqa: BLE001
        return None, str(exc)[:60].encode()


def discover() -> dict:
    rows = []
    # ② 端口表
    for name, port, path, proto in PORTS:
        ms = _tcp(port)
        row = {"kind": proto, "name": name, "target": "http://127.0.0.1:%d" % port,
               "port": port, "tcp_ms": ms, "alive": False, "protocol": None,
               "evidence": ""}
        if ms is not None:
            url = "http://127.0.0.1:%d%s" % (port, path)
            code, body = _http(url)
            row["http"] = code
            if code and 200 <= code < 400:
                row["alive"] = True
                txt = body[:160].decode("utf-8", "replace")
                row["evidence"] = txt
                if proto == "openai" and '"data"' in txt or '"object"' in txt:
                    row["protocol"] = "openai-compatible"
            elif code:
                row["evidence"] = "HTTP %s" % code
            else:
                row["evidence"] = body.decode("utf-8", "replace")[:60]
        rows.append(row)

    # ③ 桥报出来的上游（每条上游就是一个可插的源）
    up = []
    code, body = _http("http://127.0.0.1:8791/health", limit=200000)
    if code and 200 <= code < 400:
        try:
            d = json.loads(body.decode("utf-8", "replace") + "}" * 0)
            for u in d.get("upstreams") or []:
                # ⚠️ 不冒充：key_ready 只说明"凭据齐"，**不等于可达**。
                # 所以这类条目单独标 credential_only，alive 仍按真探结果给（这里没探，就 False）。
                up.append({"kind": "bridge-upstream", "name": u.get("name"),
                           "target": u.get("base_url"), "alive": False,
                           "credential_only": bool(u.get("key_ready")),
                           "protocol": "openai-compatible" if "v1" in str(u.get("base_url")) else None,
                           "evidence": "凭据就绪=%s（未探通达，按不可达计）model=%s"
                                       % (u.get("key_ready"), u.get("model"))})
        except Exception:                                        # noqa: BLE001
            pass
    rows.extend(up)

    # ④ 页面工人管线
    res_f = ROOT / "state" / "local_results.jsonl"
    jobs_f = ROOT / "state" / "local_jobs.jsonl"
    if jobs_f.is_file():
        jobs = [l for l in jobs_f.read_text(encoding="utf-8").splitlines() if l.strip()]
        done = set()
        if res_f.is_file():
            for ln in res_f.read_text(encoding="utf-8").splitlines():
                try:
                    done.add(json.loads(ln).get("id"))
                except Exception:                                # noqa: BLE001
                    pass
        rows.append({"kind": "worker", "name": "local-worker",
                     "target": "bridge:/_local/enqueue",
                     "alive": len(done) > 0, "protocol": "gguf-in-browser",
                     "evidence": "已交回 %d / 派过 %d 单" % (len(done), len(jobs))})

    alive = [r for r in rows if r.get("alive")]
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "total": len(rows),
            "alive": len(alive), "rows": rows,
            "by_kind": {k: sum(1 for r in alive if r.get("kind") == k)
                        for k in {r.get("kind") for r in alive}}}


def bind(data: dict) -> dict:
    """把活着的插座写进一份可被 omni_plug 直接吃的表。"""
    plugs = []
    for r in data.get("rows") or []:
        if not r.get("alive"):
            continue
        plugs.append({"name": r.get("name"), "kind": r.get("kind"),
                      "target": r.get("target"), "protocol": r.get("protocol"),
                      "evidence": r.get("evidence")})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"at": data.get("at"), "plugs": plugs}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    return {"plugs": len(plugs), "file": str(OUT)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--bind", action="store_true")
    a = ap.parse_args(argv)

    d = discover()
    if a.bind:
        b = bind(d)
        d["bind"] = b

    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 0 if d["alive"] else 2

    print("  万能插 · 自动识别 %d 个候选接口，活着 %d 个" % (d["total"], d["alive"]))
    if d.get("by_kind"):
        print("  按类：", d["by_kind"])
    for r in d["rows"]:
        mark = "✅" if r.get("alive") else "🔴"
        print("   %s %-14s %-26s %-18s %s" % (
            mark, r.get("name"), str(r.get("target"))[:26],
            str(r.get("protocol"))[:18], str(r.get("evidence"))[:44]))
    if a.bind:
        print("  已生成插座表：%s（%d 条）" % (d["bind"]["file"], d["bind"]["plugs"]))
    return 0 if d["alive"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
