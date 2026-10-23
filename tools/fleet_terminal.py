# gbt-capability: tentacle_fleet
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""远程薄终端 · 把"触手"伸到任何一台主机上（主人令 2026-09-27：云上终端 + 万能插）。

主人原话：「抓取哪些可以 24 小时待机的免费服务器，就部署各个品牌的终端和万能插进去，
即可全部关联本体可调用全部能力，这样把体积缩小到可忽略不计，运行速度加倍，
而且完全没有了本地压力。」

**本文件是"终端那一半"**：它**零框架体积**（不 import 本仓任何模块、不带任何凭据文件），
只做一件事 —— 拿令牌把一条能力调用**送进本体的唯一门**（`run_task`），把结果拿回来。
本体那一半（网关）**要主人授权才能部署**，本工具**不部署任何东西**。

## 红线（写死在代码里，不是口头约定）
  1. **只许 http/https**；**拒环形/私有/保留/本机名**（`localhost` · `127.0.0.0/8` · `::1` ·
     `10/8` · `172.16/12` · `192.168/16` · `169.254/16` · `0.0.0.0` · `*.local` · `.internal`）
     —— 服务端请求必须校验主机，这条与框架的既有约束一致；
  2. **令牌只从环境变量读**（默认 `GBT_TERMINAL_TOKEN`），**不落盘、不打印、不进日志**；
     没有令牌 → **拒绝发请求**（不许匿名调）；
  3. **能力白名单**：默认只允许**只读安全集**；要放开必须显式 `--allow`（或主人侧的
     `--allow-all`，会打印醒目警告并写台账）。远程调用面越大，越要有闸。
  4. **不批量注册任何账号**（主人 9·23 令）：终端只装到**主人自己合法持有的主机**上。

## 命令
  python tools/fleet_terminal.py guard <url>                       # 单看一个 URL 过不过闸
  python tools/fleet_terminal.py call --gateway <url> --cap <kind> --payload-json '{"op":"status"}'
  python tools/fleet_terminal.py call ... --dry-run                # 只看请求长什么样，不发
  python tools/fleet_terminal.py selftest                          # 闸门用例（不出网）
  python tools/fleet_terminal.py selftest --loopback               # 再用本机桩跑一次真往返（仅自测）

## 本体那一半的契约（网关必须实现，序号即纪律）
  `POST <gateway>/terminal/exec`
    Header: `Authorization: Bearer <GBT_TERMINAL_TOKEN>`
    Body:   `{"terminal_id": "...", "cap": "<能力位>", "payload": {...}}`
  网关侧**必须**：① 校验令牌 ② 校验该能力在终端的授权范围内 ③ 走 `run_task` ④ 结果原样回；
  **不许**把能力调用直连模块（绕过授权门 = 违规，本仓 2026-09-19 有过实测教训）。
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
LEDGER = ROOT / "state" / "fleet_terminals.jsonl"
TOKEN_ENV = "GBT_TERMINAL_TOKEN"
TIMEOUT = 60
# 默认可调用的**只读安全集**（要更多必须显式 --allow / --allow-all）
READONLY_ALLOW = (
    "vision", "mirror_status", "mirror_scan", "file_hygiene", "inventory",
    "caps_called_audit", "coverage_auditor", "pentrating_cross_scan",
    "penetrating_cross_scan", "hook_enforcer", "omission_detector",
    "tentacle_bind", "selfscan", "platform_profile", "media_run",
)
BAD_HOSTS = ("localhost", "localhost.localdomain")
BAD_SUFFIX = (".local", ".internal", ".localhost", ".lan", ".home")


def guard_url(url: str) -> tuple[bool, str]:
    """URL 闸：只许 http/https、只许**公网**主机。返回 (过, 原因)。"""
    try:
        p = urllib.parse.urlparse(url)
    except ValueError as e:
        return False, f"URL 解析失败：{e}"
    if p.scheme not in ("http", "https"):
        return False, f"协议必须是 http/https（收到 {p.scheme or '空'}）"
    if p.username or p.password:
        return False, "URL 里不许带账号密码（凭据只走令牌头）"
    host = (p.hostname or "").strip().lower().rstrip(".")
    if not host:
        return False, "URL 没有主机名"
    if host in BAD_HOSTS or host.endswith(BAD_SUFFIX):
        return False, f"拒本机名：{host}"
    # 字面 IP：逐段判私有/环回/保留
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved \
                or ip.is_multicast or ip.is_unspecified:
            return False, f"拒私有/环回/保留地址：{host}"
        return True, f"公网 IP 放行：{host}"
    except ValueError:
        pass
    # 域名：解析一遍，任一解析结果落在私有/环回/保留段即拒（防 DNS 指向内网）
    try:
        infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        return False, f"域名解析不了：{host}（{e.strerror or e}）"
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False, f"解析出非法地址：{addr}"
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
            return False, f"域名解析到私有/环回地址（{host} → {addr}）⇒ 拒（防内网穿透）"
    return True, f"域名公网可达：{host}"


def _token(env_name: str) -> str:
    tok = (os.environ.get(env_name) or "").strip()
    return tok


def build_request(gateway: str, cap: str, payload: dict, terminal_id: str) -> dict:
    """构造请求（**先把头去掉令牌再返回**，方便 dry-run 打印而不泄露）。"""
    body = json.dumps({"terminal_id": terminal_id, "cap": cap, "payload": payload},
                      ensure_ascii=False).encode("utf-8")
    url = gateway.rstrip("/") + "/terminal/exec"
    return {"url": url, "method": "POST",
            "headers": {"Content-Type": "application/json",
                        "Authorization": "Bearer <令牌（不回显）>",
                        "X-Terminal-Id": terminal_id},
            "body": body}


def call(gateway: str, cap: str, payload: dict, allow: tuple[str, ...],
         allow_all: bool, dry_run: bool, terminal_id: str) -> dict:
    ok, why = guard_url(gateway)
    if not ok:
        _ledger({"event": "terminal_refused", "why": why, "gateway": gateway, "cap": cap})
        return {"ok": False, "why": f"URL 闸拒绝：{why}"}
    allowed = set(READONLY_ALLOW) | set(allow)
    if not (allow_all or cap in allowed):
        return {"ok": False, "why": f"能力 {cap} 不在本终端白名单内（只读集：{sorted(set(READONLY_ALLOW))[:6]}…）"
                                    f"；要放开请显式 --allow {cap}（--allow-all 仅主人）"}
    req = build_request(gateway, cap, payload, terminal_id)
    if allow_all:
        print("⚠️ --allow-all：本终端可调用任意能力 —— 只在主人明确点头后使用，已写台账。")
    if dry_run:
        return {"ok": True, "dry_run": True, "url": req["url"], "method": req["method"],
                "headers": req["headers"], "body": req["body"].decode("utf-8")}
    tok = _token(TOKEN_ENV)
    if not tok:
        return {"ok": False, "why": f"环境变量 {TOKEN_ENV} 里没有令牌 ⇒ 拒绝发送（不许匿名调）"}
    r = urllib.request.Request(req["url"], data=req["body"], method="POST")
    for k, v in req["headers"].items():
        r.add_header(k, tok if k == "Authorization" else v)
    r.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(r, timeout=TIMEOUT) as resp:   # noqa: S310（URL 已过闸）
            data = resp.read().decode("utf-8", errors="replace")
            out = {"ok": True, "http": resp.status, "result": data[:4000]}
    except urllib.error.HTTPError as e:
        out = {"ok": False, "http": e.code, "why": (e.read().decode("utf-8", errors="replace") or "")[:400]}
    except (urllib.error.URLError, OSError) as e:
        out = {"ok": False, "why": f"连不上：{type(e).__name__}: {e}"}
    _ledger({"event": "terminal_call", "gateway": gateway, "cap": cap,
             "ok": out.get("ok"), "http": out.get("http"), "terminal_id": terminal_id,
             "allow_all": allow_all})
    return out


def _ledger(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


def selftest(loopback: bool = False) -> int:
    """闸门用例（**不出网**）：必须拒的与必须放的各来几条。返回失败数。"""
    must_reject = [
        "ftp://example.com/x", "http://localhost:8080/x", "http://127.0.0.1/x",
        "http://10.1.2.3/x", "http://192.168.1.5/x", "http://172.16.5.5/x",
        "http://169.254.1.1/x", "http://0.0.0.0/x", "http://[::1]/x",
        "http://user:pw@example.com/x", "http://foo.internal/x", "http://x.local/x",
        "http:///nohost",
    ]
    must_accept = ["https://example.com/terminal", "http://1.1.1.1:8080/g"]
    bad = 0
    for u in must_reject:
        ok, why = guard_url(u)
        if ok:
            print(f"  🔴 本该拒却放行：{u}"); bad += 1
    for u in must_accept:
        ok, why = guard_url(u)
        if not ok:
            print(f"  🔴 本该放行却拒了：{u}（{why}）"); bad += 1
    print(f"  闸门用例：拒 {len(must_reject)} 条 · 放 {len(must_accept)} 条 ⇒ 失败 {bad}")
    # 令牌缺失必须拒绝
    saved = os.environ.pop(TOKEN_ENV, None)
    r = call("https://example.com", "mirror_status", {}, (), False, False, "selftest")
    if r.get("ok") or "令牌" not in str(r.get("why")):
        print(f"  🔴 没令牌竟然没被拒：{r}"); bad += 1
    else:
        print("  ✓ 没令牌 → 拒绝发送（不许匿名调）")
    if saved:
        os.environ[TOKEN_ENV] = saved
    # 白名单必须生效
    r = call("https://example.com", "one_key_deploy", {}, (), False, True, "selftest")
    if r.get("ok"):
        print("  🔴 白名单外的高危能力竟然放行"); bad += 1
    else:
        print("  ✓ 白名单外的高危能力（one_key_deploy）被拒")
    if loopback:
        print("  ⚠️ --loopback：仅自测用，拿本机桩跑一次真往返（这条**绕过**了 URL 闸，属特例）")
        import http.server
        import threading

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):                                   # noqa: N802
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n).decode("utf-8", errors="replace")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "echo": json.loads(body),
                                             "auth": bool(self.headers.get("Authorization"))},
                                            ensure_ascii=False).encode())
            def log_message(self, *a):                            # noqa: D102
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        os.environ[TOKEN_ENV] = "selftest-token-not-a-real-one"
        req = urllib.request.Request(f"http://127.0.0.1:{port}/terminal/exec",
                                     data=json.dumps({"terminal_id": "selftest",
                                                      "cap": "mirror_status", "payload": {}}).encode(),
                                     method="POST")
        req.add_header("Authorization", "Bearer selftest-token-not-a-real-one")
        with urllib.request.urlopen(req, timeout=10) as resp:
            got = json.loads(resp.read().decode())
        srv.shutdown()
        print(f"  ✓ 往返通：桩收到 {got['echo']['cap']} · 带令牌={got['auth']}")
        os.environ.pop(TOKEN_ENV, None)
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="远程薄终端（零体积 · 过唯一门 · 带闸）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("guard"); s.add_argument("url")
    s = sub.add_parser("call")
    s.add_argument("--gateway", required=True)
    s.add_argument("--cap", required=True)
    s.add_argument("--payload-json", default="{}")
    s.add_argument("--payload-file", default="")
    s.add_argument("--allow", action="append", default=[])
    s.add_argument("--allow-all", action="store_true")
    s.add_argument("--terminal-id", default=os.environ.get("COMPUTERNAME", "terminal"))
    s.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("selftest"); s.add_argument("--loopback", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "guard":
        ok, why = guard_url(a.url)
        print(f"{'✅ 放行' if ok else '🔴 拒绝'} {a.url}\n   {why}")
        return 0 if ok else 1
    if a.cmd == "selftest":
        return 0 if selftest(a.loopback) == 0 else 1
    payload = json.loads(Path(a.payload_file).read_text(encoding="utf-8")) if a.payload_file \
        else json.loads(a.payload_json or "{}")
    r = call(a.gateway, a.cap, payload, tuple(a.allow), a.allow_all, a.dry_run, a.terminal_id)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
