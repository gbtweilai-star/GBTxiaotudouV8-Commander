# -*- coding: utf-8 -*-
"""defense-report-server -- 本机最小「自卫上报/反控」端点（主人 2026-10-17 批准）。

手机版/电脑版页面里的自卫层命中攻击时，会 POST 证据到这里；本服务只做两件事：
  ① 走门跑 `sec_defenses`（蓝队验证，防御面可自授）；
  ② 若证据里带 `targets`（攻击者 AI 的 OpenAI 兼容端点）⇒ 走门跑 `omni_plug counter_strike`
     极限触手并行反控，并把 text/tool_calls/usage（脱敏）收进事件账本。

## 安全边界（写死）
- **只监听局域网地址**（默认取本机 LAN IP；可用 `--host` 覆盖到 127.0.0.1 做本机联调）；
- **只接受私有网段来源**（10/172.16-31/192.168/127/::1），公网来源 403；
- 请求体 ≤ 64KB、每分钟 ≤ 30 次（防被当成喇叭打）；
- 可选令牌：`GBT_DEFENSE_TOKEN` 设了就必须带 `X-GBT-Token`；
- 绝不回显任何钥匙/明文；反控结果**如实报**（缺票/缺钥匙/不可达都照实写）；
- 只要求攻击源**停止并回报来源**，不越权、不外带敏感数据。

## 用法
py -3.14 tools/codex-scripts/defense-report-server.py --port 8877
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import pathlib
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
GATE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
OUT = ROOT / "state" / "defense"
MAX_BODY = 64 * 1024
RATE_LIMIT = 30
TOKEN = (os.environ.get("GBT_DEFENSE_TOKEN") or "").strip()
_hits = {}
_lock = threading.Lock()


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:                                            # noqa: BLE001
        return "127.0.0.1"


def _cap(kind: str, payload: dict, timeout: int = 240) -> dict:
    """走唯一门调能力位（不直调模块；门怎么说就怎么报）。"""
    p = subprocess.run([sys.executable, "-X", "utf8", str(GATE), "cap", kind,
                        json.dumps(payload, ensure_ascii=False), "--full"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, cwd=str(ROOT))
    t = (p.stdout or "") + (p.stderr or "")
    i = t.find("{")
    try:
        return json.loads(t[i:])
    except Exception:                                            # noqa: BLE001
        return {"status": "error", "raw": t[:300]}


def _allowed(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(str(ip).split("%")[0])
        return a.is_private or a.is_loopback or a.is_link_local
    except Exception:                                            # noqa: BLE001
        return False


def _rate_ok(ip: str) -> bool:
    now = time.time()
    with _lock:
        arr = [t for t in _hits.get(ip, []) if now - t < 60]
        if len(arr) >= RATE_LIMIT:
            _hits[ip] = arr
            return False
        arr.append(now)
        _hits[ip] = arr
    return True


class H(BaseHTTPRequestHandler):
    server_version = "gbt-defense/1.0"
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, obj: dict) -> None:
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-GBT-Token")
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, fmt, *args):                           # 静默默认访问日志（证据走 incidents.jsonl）
        return

    def do_OPTIONS(self):                                        # noqa: N802
        self._send(200, {"ok": True, "op": "options"})

    def do_GET(self):                                            # noqa: N802
        if self.path.split("?")[0] in ("/defense/health", "/defense"):
            return self._send(200, {"ok": True, "service": "gbt-defense-report",
                                    "version": "1.0", "accepts": "POST /defense/report",
                                    "rate_limit_per_min": RATE_LIMIT, "max_body_bytes": MAX_BODY})
        return self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):                                           # noqa: N802
        ip = self.client_address[0]
        if self.path.split("?")[0] != "/defense/report":
            return self._send(404, {"ok": False, "error": "not_found"})
        if not _allowed(ip):
            return self._send(403, {"ok": False, "error": "non_private_source_denied", "source": ip})
        if not _rate_ok(ip):
            return self._send(429, {"ok": False, "error": "rate_limited", "per_min": RATE_LIMIT})
        if TOKEN and (self.headers.get("X-GBT-Token") or "") != TOKEN:
            return self._send(401, {"ok": False, "error": "token_required"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except Exception:                                        # noqa: BLE001
            n = 0
        if n <= 0 or n > MAX_BODY:
            return self._send(413, {"ok": False, "error": "bad_body_size", "max": MAX_BODY})
        try:
            ev = json.loads(self.rfile.read(n).decode("utf-8", "replace"))
        except Exception:                                        # noqa: BLE001
            return self._send(400, {"ok": False, "error": "bad_json"})
        t0 = time.time()
        OUT.mkdir(parents=True, exist_ok=True)
        inc = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "source_ip": ip,
               "rule": str(ev.get("rule") or "")[:40], "hit": str(ev.get("hit") or "")[:160],
               "where": str(ev.get("where") or "")[:60], "url": str(ev.get("url") or "")[:300],
               "targets": [str(x)[:300] for x in (ev.get("targets") or [])][:16]}
        with (OUT / "incidents.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(inc, ensure_ascii=False) + "\n")
        # ① 蓝队验证（防御面可自授；门怎么说就怎么报）
        d = _cap("sec_defenses", {"op": "status"}, timeout=180)
        dr = d.get("result") or {}
        defense = {"ok": bool(dr.get("ok")), "status": dr.get("defense_status") or "未读到",
                   "passed": dr.get("passed"), "total": dr.get("total"),
                   **({} if dr.get("ok") else {"gate_denied": d.get("denied"),
                                               "reason": str(d.get("result") or d.get("status") or "")[:160]})}
        # ② 有攻击源 ⇒ 极限触手并行反控
        tgts = [str(x) for x in (ev.get("targets") or []) if str(x).strip()][:8]
        counter = {"skipped": "未提供 targets（只留证，不反控）"}
        if tgts:
            c = _cap("omni_plug", {"op": "counter_strike", "targets": tgts,
                                   "max_tentacles": min(8, len(tgts)),
                                   "evidence": {"rule": inc["rule"], "hit": inc["hit"]}}, timeout=300)
            cr = c.get("result") or {}
            counter = {"ok": bool(cr.get("ok")), "并发": cr.get("并发"), "成功": cr.get("成功"),
                       "耗时_ms": cr.get("耗时_ms"),
                       "逐目标": [{k: r.get(k) for k in ("target", "ok", "http", "key_slot", "reason")}
                                  for r in (cr.get("results") or [])],
                       **({} if cr.get("ok") else
                          {"gate_denied": c.get("denied"),
                           "note": "反控未成功：如实报（缺钥匙/不可达/缺票都可能）"})}
        resp = {"ok": True, "op": "defense_report", "incident": inc,
                "defense": defense, "counter": counter,
                "elapsed_ms": int((time.time() - t0) * 1000),
                "_口径": "只对私有网段来源；只要求攻击源停止并回报；缺票/缺钥匙如实报"}
        with (OUT / "incidents.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": resp["incident"]["ts"], "kind": "response",
                                 "defense_ok": defense.get("ok"),
                                 "counter_ok": (counter or {}).get("ok"),
                                 "elapsed_ms": resp["elapsed_ms"]}, ensure_ascii=False) + "\n")
        return self._send(200, resp)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="本机最小自卫上报/反控端点（LAN-only）")
    ap.add_argument("--host", default="")
    ap.add_argument("--port", type=int, default=8877)
    a = ap.parse_args(argv)
    host = a.host or lan_ip()
    try:
        srv = ThreadingHTTPServer((host, a.port), H)             # 只绑局域网地址
    except Exception as e:                                       # noqa: BLE001
        print("RED 起不来：%s: %s" % (type(e).__name__, e))
        return 1
    print("自卫上报端点已起：http://%s:%d/defense/report" % (host, a.port))
    print("  只收私有网段来源 · 每分钟≤%d 次 · 体≤64KB · 令牌%s" % (RATE_LIMIT, "已启用" if TOKEN else "未设(可选)"))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("收工")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
