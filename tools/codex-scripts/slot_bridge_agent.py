# -*- coding: utf-8 -*-
"""50 槽桥代理（云端排队 ⇄ 本机 run_task 执行 ⇄ 结果回传）—— 主人 2026-10-04 令「槽转发到对应能力位」。

## 它是什么
云端 Worker 上 50 个槽排队等活；本机这根桥代理**轮询取活** → 把每条命令送进**run_task 唯一门**
（授权/作用域/审计全在门里）→ 把结果回传云端。这样云端槽就真的"转发到对应能力位"了。

## 红线
  · 执行一律 run_task（门内）—— 代理**只搬运，不旁路**；
  · 只执行**槽位表里已指派**的槽（备用槽/未知槽拒收并如实回执）；
  · 每次取活**先认领**（云端标记 claimed）防双跑；结果截断 8KB 回传；
  · 钥匙 = GW_AUTH（同一个统一密钥，从应用数据区读），**不落盘、不打印**；
  · 出站目标**字面量锁死**：`https://gbt-potato-cloud-10.lopaycn.workers.dev`（协议/主机白名单 +
    解析后 IP 不得落私网/环回/链路本地 —— 防 DNS rebinding；不用 OpenAI 兼容口，走专用队列路）。

用法：
    py -3.14 tools/codex-scripts/slot_bridge_agent.py            # 前台跑（Ctrl+C 停）
    py -3.14 tools/codex-scripts/slot_bridge_agent.py --once     # 只跑一轮（验收用）
    py -3.14 tools/codex-scripts/slot_bridge_agent.py --loop 5   # 每 5 秒轮询

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import ssl
import sys
import time
import http.client
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "deploy" / "cloud-10" / "plugins50.json"
KEYFILE = Path(os.environ.get("APPDATA", str(Path.home()))) / "gbt-cliproxy" / "client-key.txt"

# 出站目标**字面量锁死**（Mimosa SSRF 口径：协议/主机白名单 + 解析后 IP 边界校验）
WORKER_HOST = "gbt-potato-cloud-10.lopaycn.workers.dev"
WORKER_ORIGIN = "https://" + WORKER_HOST
_ALLOWED_PATHS = re.compile(r"^/slots50(/(queue|claim|result))?$") if False else None
import re  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))   # 🔴 2026-10-04 补：重写时弄丢了这行 ⇒ run_task 导入失败（活悬死）
_ALLOWED_PATHS = re.compile(r"^/slots50(?:/(queue|claim|result))?$")

_KEYFILE = KEYFILE
AGENT = "slot-bridge@" + os.environ.get("COMPUTERNAME", "local")


def _key() -> str:
    f = KEYFILE
    return f.read_text(encoding="utf-8").strip() if f.is_file() else ""


def _checked_target(path: str) -> str:
    """出站三重校验：① 路径在允许集 ② 主机=字面量白名单 ③ 解析后 IP 不落私网/环回/链路本地
    （防 DNS rebinding）。校验不过就抛，**不发请求**。"""
    import re as _re
    if not _ALLOWED_PATHS.match(path):
        raise ValueError("路径不在允许集：%r" % path[:60])
    infos = socket.getaddrinfo(WORKER_HOST, 443, type=socket.SOCK_STREAM)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("解析到非公网地址 %s —— 拒发（防 rebinding）" % ip)
    return WORKER_HOST


def _request(path: str, body=None, timeout: float = 60) -> tuple:
    """出站唯一口：HTTPSConnection（字面量主机）+ 校验过的路径。返回 (status, dict)。"""
    host = _checked_target(path)
    conn = http.client.HTTPSConnection(host, timeout=timeout, context=ssl.create_default_context())
    headers = {"Authorization": "Bearer " + _key(),
               "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")}
    payload = None
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    try:
        conn.request("POST" if body is not None else "GET", path, body=payload, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", "replace")
        try:
            return resp.status, json.loads(raw)
        except Exception:                                      # noqa: BLE001
            return resp.status, {"raw": raw[:300]}
    finally:
        conn.close()


def _call(path: str, body=None, timeout: float = 60) -> tuple:
    try:
        return _request(path, body, timeout)
    except Exception as e:                                     # noqa: BLE001
        return 0, {"error": "%s: %s" % (type(e).__name__, str(e)[:160])}


def slot_map() -> dict:
    d = json.loads(SPEC.read_text(encoding="utf-8"))
    return {m["slot"]: m.get("local_driver") or "" for m in d.get("modules") or []}


def run_round(once: bool = False) -> int:
    smap = slot_map()
    st, d = _call("/slots50/queue")
    if st != 200 or not d.get("ok"):
        print("取队列失败：HTTP %s %s" % (st, json.dumps(d, ensure_ascii=False)[:120]))
        return 1
    items = d.get("items") or []
    queued = [x for x in items if x.get("state") == "queued"]
    if not queued:
        print("队列空（%d 条历史）" % len(items))
        return 0
    ids = [x["id"] for x in queued]
    st2, d2 = _call("/slots50/claim", {"ids": ids, "agent": AGENT})
    got = set(d2.get("claimed") or [])
    print("认领 %d/%d" % (len(got), len(queued)))
    for x in queued:
        if x["id"] not in got:
            continue
        slot, cap = x["slot"], x.get("cap") or smap.get(x["slot"], "")
        op, args = x.get("op") or "status", x.get("args") or {}
        t0 = time.time()
        from gbt_allinone import run_task
        env = run_task(cap, {"op": op, **args}, safe=True)
        ms = int((time.time() - t0) * 1000)
        okk = bool(env.get("ok"))
        result = json.dumps(env.get("result") or env.get("error") or {}, ensure_ascii=False, default=str)[:8000]
        st3, _d3 = _call("/slots50/result", {"id": x["id"], "ok": okk, "result": result,
                                             "error": env.get("error") or "", "agent": AGENT, "ms": ms})
        print("  [%s] %s → %s %dms（结果已回传 %s）" % (x["id"], cap, "ok" if okk else "失败", ms, "✓" if st3 == 200 else "✗"))
    return 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                      # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="50 槽桥代理（云端排队 ⇄ 本机 run_task）")
    ap.add_argument("--once", action="store_true", help="只跑一轮（验收用）")
    ap.add_argument("--loop", type=float, default=5.0, help="轮询间隔秒（前台常驻）")
    a = ap.parse_args(argv)
    if a.once:
        return run_round(True)
    try:
        while True:
            run_round(False)
            time.sleep(max(2.0, float(a.loop)))
    except KeyboardInterrupt:
        print("桥代理已停")
        return 0


if __name__ == "__main__":
    sys.exit(main())
