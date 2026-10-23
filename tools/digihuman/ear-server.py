# -*- coding: utf-8 -*-
"""ear-server.py —— 本机「耳朵桥」：把离线中文听令开放给 App（只监听回环）

## 为什么需要一个桥
`ear-listen.ps1` 是 PowerShell 侧的离线识别器（System.Speech · zh-CN · 零密钥零联网）。
但渲染进程（holo_pet 的 WebView / 浏览器）不能直接调 PowerShell —— 浏览器没有那种权限。
所以中间放一个**只监听 127.0.0.1** 的小 HTTP 桥：页面 fetch 过来，桥去跑识别器。

## 接口
  GET /health                       → {"ok":true,"listening":true}
  GET /listen?seconds=6             → 用默认麦克风听（会阻塞到有结果或超时）
  GET /listen?wav=<绝对路径>        → 用现成 wav 文件识别（**没有麦克风也能验链路**）
  GET /listen?...&min_conf=0.55     → 置信度门槛（低于门槛 returns accepted=false）

返回体就是 `ear-listen.ps1` 的原话回执（含 `text/action/conf/accepted/why/heard`），
**不二次加工** —— 上游说没听清就如实没听清。

## 安全口径（写死）
- 只绑定 `127.0.0.1`，不监听 0.0.0.0；
- 只做**只读**动作（听 → 回一个动作名），不执行任何命令、不写盘；
- CORS 只放行本机来源（`*` 仅用于回环开发，非公网服务）。

## 用法
  py -3.14 tools/digihuman/ear-server.py --port 8770
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
PS1 = ROOT / "tools" / "digihuman" / "ear-listen.ps1"
PWSH = "pwsh"


def listen(wav: str = "", seconds: int = 6, min_conf: float = 0.55, lang: str = "zh-CN") -> dict:
    args = [PWSH, "-NoProfile", "-File", str(PS1), "-Seconds", str(seconds),
            "-MinConf", str(min_conf), "-Lang", lang, "-Json"]
    if wav:
        if not Path(wav).is_file():
            return {"ok": False, "why": "wav 不在：%s" % wav}
        args += ["-Wave", wav]
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=max(20, seconds + 25))
    except subprocess.TimeoutExpired:
        return {"ok": False, "why": "识别器超时（%ss）" % (seconds + 25)}
    raw = (r.stdout or "") + (r.stderr or "")
    i, j = raw.find("{"), raw.rfind("}")
    if i < 0 or j <= i:
        return {"ok": False, "why": "识别器没有回 JSON",
                "tail": raw.strip().splitlines()[-5:]}
    try:
        data = json.loads(raw[i:j + 1])
    except ValueError:
        return {"ok": False, "why": "回执解析失败", "tail": raw.strip().splitlines()[-5:]}
    data["via"] = "ear-listen.ps1"
    data["wav"] = wav or None
    return data


class Handler(BaseHTTPRequestHandler):
    server_version = "GBT-Ear/1.0"

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")     # 仅回环开发用
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:                                  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:                                      # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/health":
            self._json(200, {"ok": True, "listening": True, "ps1": str(PS1),
                             "exists": PS1.is_file()})
            return
        if u.path == "/listen":
            wav = (q.get("wav") or [""])[0]
            secs = int((q.get("seconds") or ["6"])[0])
            mc = float((q.get("min_conf") or ["0.55"])[0])
            lang = (q.get("lang") or ["zh-CN"])[0]
            rep = listen(wav=wav, seconds=secs, min_conf=mc, lang=lang)
            self._json(200, rep)
            return
        self._json(404, {"ok": False, "why": "只有 /health 与 /listen"})

    def log_message(self, fmt: str, *args) -> None:                 # 安静点，别脏日志
        sys.stderr.write("[ear] %s\n" % (fmt % args))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                          # noqa: BLE001
            pass
    if not PS1.is_file():
        print(json.dumps({"ok": False, "why": "ear-listen.ps1 不在", "path": str(PS1)},
                         ensure_ascii=False))
        return 2
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(json.dumps({"ok": True, "listen_on": "http://%s:%d" % (a.host, a.port),
                      "health": "/health", "api": "/listen", "ps1": str(PS1)},
                     ensure_ascii=False), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
