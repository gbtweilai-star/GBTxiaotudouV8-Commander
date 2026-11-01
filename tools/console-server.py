# -*- coding: utf-8 -*-
"""认知界面本地服务（console-server）：给 console 页提供真数据与真对话。

为什么需要它：file:// 直开时浏览器 CORS 会挡 fetch，控制台只能演示；
起这个小服务后，页面用 http://127.0.0.1:8766/ 打开 → 数据现读、对话走本机指挥官。

口径（主人 2026-11-01）：「我们的是无限制上下文稳定输出」
  · 无限上下文：每轮对话走 `energy_core.think(context="console-web")` ——
    模型只吃**有界窗口**（恒定长度），全量历史落 sqlite 可 recall（ring_context）；
  · 稳定输出：temperature=0、max_tokens 封顶、同一问题同一回答（可复现）；
  · 没电/没票/出错：如实报错，不编回答。

用法：python tools/console-server.py [--port 8766]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = pathlib.Path(__file__).resolve().parents[1]
WEB = REPO / "holo_pet_w3"
sys.path.insert(0, str(REPO))

DATA_LOCK = threading.Lock()
DATA_CACHE = {"at": 0.0, "data": None}
CONTEXT_NAME = "console-web"


def _build_data() -> dict:
    """真数据：与 tools/gen-console-data.py 同源（直接调它）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen_console_data", REPO / "tools" / "gen-console-data.py")
    mod = importlib.util.module_from_spec(spec)
    old = sys.argv
    sys.argv = ["gen"]
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod.build()
    finally:
        sys.argv = old


def _data() -> dict:
    with DATA_LOCK:
        if DATA_CACHE["data"] is None or time.time() - DATA_CACHE["at"] > 5:
            DATA_CACHE["data"] = _build_data()
            DATA_CACHE["at"] = time.time()
        return DATA_CACHE["data"]


def _chat(text: str, context: str = CONTEXT_NAME) -> dict:
    """无限上下文 + 稳定输出：temperature=0，context 走 ring_context。"""
    from gbt_allinone import energy_core as E
    t0 = time.time()
    r = E.think([{"role": "user", "content": str(text)}], temperature=0.0,
                max_tokens=512, timeout=300, context=context, label="console-web")
    out = {"ok": bool(r.get("ok")), "text": r.get("text"),
           "error": r.get("error"), "ms": r.get("ms"),
           "usage": r.get("usage"), "context": r.get("context"),
           "policy": {"temperature": 0.0, "max_tokens": 512,
                      "unlimited_context": True,
                      "note": "模型只看有界窗口；全量历史落 sqlite 可 recall"}}
    try:
        from gbt_allinone.llm import ring_context as RC
        rc = RC.RingContext(name=context)
        st = rc.stats()
        out["ring"] = {"name": context, "seq": st.get("seq"),
                       "db_turns": st.get("db_turns"),
                       "window_chars": st.get("window_chars") or rc.window_chars}
    except Exception as e:  # noqa: BLE001
        out["ring"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:100])}
    out["elapsed_ms"] = int((time.time() - t0) * 1000)
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "GBTConsole/1.0"

    def log_message(self, fmt, *args):  # noqa: A003
        pass  # 安静

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/events":
            return self._sse()
        if path == "/api/data":
            try:
                return self._json({"ok": True, "data": _data()})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160])}, 500)
        if path == "/api/state":
            d = _data()
            return self._json({"ok": True, "caps": d["caps"]["total"],
                               "skills": d["skills"]["count"],
                               "engine": d["engine"], "guards": d["guards"]})
        if path.startswith("/icons/"):
            # 头像/图标在仓库根 icons/（不在 holo_pet_w3 里）：单独放行
            f = (REPO / path.lstrip("/")).resolve()
            try:
                f.relative_to((REPO / "icons").resolve())
            except ValueError:
                return self._send(403, b"forbidden", "text/plain; charset=utf-8")
            if not f.is_file():
                return self._send(404, b"not found", "text/plain; charset=utf-8")
            ctype = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".webp": "image/webp", ".svg": "image/svg+xml"}.get(f.suffix.lower(),
                                                                      "application/octet-stream")
            return self._send(200, f.read_bytes(), ctype)
        if path == "/state/console-data.js":
            f = REPO / "state" / "console-data.js"
            if not f.is_file():
                return self._send(404, b"not found", "text/plain; charset=utf-8")
            return self._send(200, f.read_bytes(), "application/javascript; charset=utf-8")
        if path in ("/", "/index.html"):
            # 302 到 /console/index.html：保证页面里的相对路径（./app.js / ./app.css / ../../state/...）按 /console/ 解析
            self.send_response(302)
            self.send_header("Location", "/console/index.html")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        f = (WEB / path.lstrip("/")).resolve()
        try:
            f.relative_to(WEB.resolve())
        except ValueError:
            return self._send(403, b"forbidden", "text/plain; charset=utf-8")
        if not f.is_file():
            return self._send(404, b"not found", "text/plain; charset=utf-8")
        ctype = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "application/javascript; charset=utf-8",
                 ".webp": "image/webp", ".png": "image/png", ".svg": "image/svg+xml",
                 ".woff2": "font/woff2"}.get(f.suffix.lower(), "application/octet-stream")
        return self._send(200, f.read_bytes(), ctype)

    def _sse(self):
        """SSE：把 audit.jsonl 的新事件按行推给前端（3D 触手实时点亮用）。"""
        import json as _json
        audit = REPO / "gbt_allinone" / "store" / "audit.jsonl"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        pos = 0
        if audit.is_file():
            # 从当前 EOF 开始：只推"连上之后"的新事件，不重放历史（避免一上来点亮一堆旧能力位）
            pos = audit.stat().st_size
        last_beat = time.time()
        try:
            while True:
                try:
                    if audit.is_file():
                        size = audit.stat().st_size
                        if size < pos:
                            pos = 0
                        with open(audit, "rb") as fh:
                            fh.seek(pos)
                            chunk = fh.read()
                            pos = fh.tell()
                        for line in chunk.decode("utf-8", "replace").splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                d = _json.loads(line)
                            except Exception:  # noqa: BLE001
                                continue
                            ev = str(d.get("event") or "")
                            if not ev or ev in ("ok", "call", "denied", "error"):
                                continue
                            payload = _json.dumps({
                                "cap": ev, "iso": d.get("iso") or "",
                                "meta": d.get("meta") or {},
                            }, ensure_ascii=False)
                            self.wfile.write(("data: " + payload + "\n\n").encode("utf-8"))
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
                if time.time() - last_beat > 15:
                    try:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    last_beat = time.time()
                time.sleep(1.2)
        except Exception:  # noqa: BLE001
            return

    def do_POST(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except Exception:  # noqa: BLE001
            return self._json({"ok": False, "error": "bad json"}, 400)
        if path == "/api/chat":
            text = str(body.get("text") or "").strip()
            if not text:
                return self._json({"ok": False, "error": "user_error: 需要 text"}, 400)
            try:
                return self._json(_chat(text, str(body.get("context") or CONTEXT_NAME)))
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160])}, 500)
        return self._json({"ok": False, "error": "not found"}, 404)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print("认知界面: http://127.0.0.1:%d/  （/api/data · /api/chat）" % a.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
