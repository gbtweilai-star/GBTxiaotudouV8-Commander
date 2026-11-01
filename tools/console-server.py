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
        if path == "/api/route":
            return self._api_route(raw)
        if path == "/api/dispatch":
            return self._api_dispatch(raw)
        if path == "/api/bounty":
            return self._api_bounty(raw)
        if path == "/api/security/policy":
            return self._api_security_policy(raw)
        if path == "/api/omni":
            return self._api_omni(raw)
        if path == "/api/scan":
            from urllib.parse import parse_qs as _pq
            from urllib.parse import urlparse as _urlparse
            q = _pq(_urlparse(self.path).query)
            target = (q.get("target") or ["bindings"])[0]
            return self._api_scan(target)
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

    # 允许现场重扫的目标（白名单；tree: 只允许仓库内已声明目录，防穿越）
    SCAN_DIRS = {"gbt_allinone", "holo_pet_w3", "tools", "docs", "tests", "skills", "arms",
                 "runtime", "assets", "data"}

    def _scan_target_ok(self, target):
        target = str(target or "").strip()
        if target in ("bindings", "registry"):
            return target
        if target.startswith("tree:"):
            rel = target[5:].strip().strip("/\\")
            if not rel or ".." in rel.split("/"):
                return None
            head = rel.split("/")[0]
            if head not in self.SCAN_DIRS:
                return None
            return "tree:" + rel
        return None

    def _api_scan(self, target):
        """现场真跑 penetrating_cross_scan，返回该目标的结果（含 unit_details）。"""
        import json as _json
        import subprocess as _sub
        ok_target = self._scan_target_ok(target)
        if not ok_target:
            return self._send(400, _json.dumps(
                {"ok": False, "error": "target 不在白名单（bindings|registry|tree:<dir>）"},
                ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        t0 = time.time()
        try:
            r = _sub.run([sys.executable, "-X", "utf8",
                          str(REPO / "tools" / "penetrating_cross_scan.py"),
                          "scan", ok_target],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         cwd=str(REPO), timeout=600)
            d = _json.loads(r.stdout)
        except Exception as e:  # noqa: BLE001
            return self._send(500, _json.dumps(
                {"ok": False, "target": ok_target, "error": str(e)[:200]}, ensure_ascii=False
            ).encode("utf-8"), "application/json; charset=utf-8")
        out = {
            "ok": bool(d.get("ok")), "target": ok_target, "units": d.get("units"),
            "hooked": d.get("hooked"), "coverage": d.get("coverage"),
            "agree": d.get("agree"), "arbitrated": d.get("arbitrated"),
            "missing": d.get("missing") or [], "mode": d.get("mode"),
            "coverage": d.get("coverage"), "full_coverage": d.get("full_coverage"),
            "dead_spots": d.get("dead_spots") or [],
            "dead_spot_count": d.get("dead_spot_count", len(d.get("missing") or [])),
            "unit_details": (d.get("unit_details") or [])[:4000],
            "ms": int((time.time() - t0) * 1000),
        }
        return self._send(200, _json.dumps(out, ensure_ascii=False).encode("utf-8"),
                          "application/json; charset=utf-8")

    def _api_route(self, raw=b"{}"):
        """职业路由：任务 → 职业 → 候选能力位（只读，不派单）。

        do_POST 已经把 body 读进 raw（读两次会拿到空），所以这里收参数不再读流。
        """
        import json as _json
        try:
            body = (raw or b"{}").decode("utf-8", "replace")
            d = _json.loads(body or "{}")
        except Exception:  # noqa: BLE001
            d = {}
        task = str(d.get("task") or "").strip()
        if not task:
            return self._send(400, b'{"ok":false,"error":"task empty"}',
                              "application/json; charset=utf-8")
        try:
            sys.path.insert(0, str(REPO))
            from gbt_allinone.profession_router import plan as _plan
            out = _plan(task[:500])
        except Exception as e:  # noqa: BLE001
            return self._send(500, _json.dumps({"ok": False, "error": str(e)[:200]},
                                               ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        return self._send(200, _json.dumps(out, ensure_ascii=False).encode("utf-8"),
                          "application/json; charset=utf-8")

    def _api_dispatch(self, raw=b"{}"):
        """职业派单：默认 dry_run；confirm=true 才真跑 safe 能力位。"""
        import json as _json
        try:
            d = _json.loads((raw or b"{}").decode("utf-8", "replace") or "{}")
        except Exception:  # noqa: BLE001
            d = {}
        task = str(d.get("task") or "").strip()
        if not task:
            return self._send(400, b'{"ok":false,"error":"task empty"}',
                              "application/json; charset=utf-8")
        try:
            sys.path.insert(0, str(REPO))
            from gbt_allinone.profession_dispatch import dispatch as _dispatch
            out = _dispatch(task[:500], dry_run=not bool(d.get("confirm")),
                            confirm=bool(d.get("confirm")),
                            max_caps=int(d.get("max_caps") or 3))
        except Exception as e:  # noqa: BLE001
            return self._send(500, _json.dumps({"ok": False, "error": str(e)[:200]},
                                               ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        return self._send(200, _json.dumps(out, ensure_ascii=False).encode("utf-8"),
                          "application/json; charset=utf-8")

    def _api_bounty(self, raw=b"{}"):
        """赏金工作台：summary / check / add_finding / report / payout。"""
        import json as _json
        try:
            d = _json.loads((raw or b"{}").decode("utf-8", "replace") or "{}")
        except Exception:  # noqa: BLE001
            d = {}
        try:
            sys.path.insert(0, str(REPO))
            from gbt_allinone import bounty as B
            op = str(d.get("op") or "summary")
            if op == "summary":
                out = B.summary()
                out["programs_list"] = B.list_programs().get("programs") or []
                out["findings_list"] = B.list_findings().get("findings") or []
            elif op == "check":
                out = B.check(str(d.get("program") or ""), str(d.get("target") or ""),
                              str(d.get("action") or "read-only-recon"))
            elif op == "add_finding":
                out = B.add_finding(str(d.get("program") or ""), str(d.get("title") or ""),
                                    str(d.get("severity") or "medium"), str(d.get("target") or ""),
                                    cwe=str(d.get("cwe") or ""), cvss=str(d.get("cvss") or ""),
                                    steps=str(d.get("steps") or ""),
                                    impact=str(d.get("impact") or ""),
                                    remediation=str(d.get("remediation") or ""),
                                    evidence=[str(x) for x in (d.get("evidence") or [])],
                                    fix_diff=str(d.get("fix_diff") or ""),
                                    attachments=[str(x) for x in (d.get("attachments") or [])])
            elif op == "report":
                out = B.report(str(d.get("finding") or ""))
            elif op == "platform_sync":
                from gbt_allinone import platform_sync as PS
                out = PS.sync(str(d.get("provider") or "mock"),
                              dry_run=not bool(d.get("confirm")),
                              program=str(d.get("program") or ""))
            elif op == "bundle":
                out = B.bundle(str(d.get("finding") or ""))
            elif op == "submit":
                out = B.submit(str(d.get("finding") or ""),
                               platform=str(d.get("platform") or ""),
                               url=str(d.get("url") or ""),
                               note=str(d.get("note") or ""))
            elif op == "set_status":
                out = B.set_status(str(d.get("finding") or ""),
                                   str(d.get("to") or ""), str(d.get("note") or ""))
            elif op == "cvss":
                from gbt_allinone import bounty_core as BC
                out = BC.cvss3(str(d.get("vector") or ""))
            elif op == "scope_import":
                from gbt_allinone import scope_import as SI
                loaded = SI.load_sample(str(d.get("file") or ""))
                if not loaded.get("ok"):
                    out = loaded
                else:
                    out = SI.import_doc(loaded["doc"], confirm=bool(d.get("confirm")))
            elif op == "payout":
                out = B.payout(str(d.get("program") or ""), str(d.get("finding") or ""),
                               float(d.get("amount") or 0), str(d.get("currency") or "USD"),
                               str(d.get("status") or "pending"), str(d.get("note") or ""))
            elif op == "add_program":
                out = B.add_program(str(d.get("name") or ""), [str(x) for x in (d.get("scope") or [])],
                                    [str(x) for x in (d.get("out_of_scope") or [])],
                                    platform=str(d.get("platform") or ""),
                                    url=str(d.get("url") or ""),
                                    authorization_ref=str(d.get("authorization_ref") or ""),
                                    reward_range=str(d.get("reward_range") or ""),
                                    rules=str(d.get("rules") or ""))
            else:
                out = {"ok": False, "error": "unknown op"}
        except Exception as e:  # noqa: BLE001
            return self._send(500, _json.dumps({"ok": False, "error": str(e)[:200]},
                                               ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        return self._send(200, _json.dumps(out, ensure_ascii=False).encode("utf-8"),
                          "application/json; charset=utf-8")

    def _api_omni(self, raw=b"{}"):
        """万能插全开同步执行：confirm 才起后台全开；否则只读状态。"""
        import json as _json
        try:
            d = _json.loads((raw or b"{}").decode("utf-8", "replace") or "{}")
        except Exception:  # noqa: BLE001
            d = {}
        sys.path.insert(0, str(REPO))
        from gbt_allinone import omni_all
        op = str(d.get("op") or "")
        if op == "attribution":
            from gbt_allinone import omni_attr
            out = omni_attr.attribute(str(d.get("run_id") or ""))
            return self._send(200, _json.dumps(out, ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        if op == "status" or not d.get("confirm"):
            out = omni_all.status()
            out["notice"] = ("状态查询；真全开执行需要 confirm=true"
                             if not d.get("confirm") else "已确认")
            return self._send(200, _json.dumps(out, ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        # 真执行：后台起一个进程（同步逐个执行，不阻塞 HTTP）
        run_id = time.strftime("%Y%m%d-%H%M%S")
        cmd = [sys.executable, "-X", "utf8", str(REPO / "tools" / "omni-run.py"),
               "--run-id", run_id, "--timeout", str(float(d.get("timeout") or 12))]
        if d.get("ticket"):
            cmd += ["--ticket", str(d.get("ticket"))]
        try:
            import subprocess as _sub
            proc = _sub.Popen(cmd, cwd=str(REPO), stdout=_sub.DEVNULL,
                              stderr=_sub.DEVNULL,
                              creationflags=getattr(_sub, "CREATE_NO_WINDOW", 0))
        except Exception as e:  # noqa: BLE001
            return self._send(500, _json.dumps({"ok": False, "error": str(e)[:200]},
                                               ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        out = {"ok": True, "started": True, "run_id": run_id, "pid": proc.pid,
               "mode": "sync-all", "note": "全开 385 位同步执行已启动；用 op=status 查进度"}
        return self._send(200, _json.dumps(out, ensure_ascii=False).encode("utf-8"),
                          "application/json; charset=utf-8")

    def _api_security_policy(self, raw=b"{}"):
        """安全策略：status / check / attack-on / attack-off（终端确认只能在 CLI 批准）。"""
        import json as _json
        try:
            d = _json.loads((raw or b"{}").decode("utf-8", "replace") or "{}")
        except Exception:  # noqa: BLE001
            d = {}
        sys.path.insert(0, str(REPO))
        from gbt_allinone import security_policy as SP
        op = str(d.get("op") or "status")
        if op == "status":
            out = SP.status()
        elif op == "check":
            out = SP.check(str(d.get("cap") or ""))
        elif op == "attack-on":
            out = SP.enter_attack_mode(str(d.get("reason") or "detected attack"),
                                       str(d.get("evidence") or ""),
                                       int(d.get("ttl") or 600))
        elif op == "attack-off":
            out = SP.exit_attack_mode(str(d.get("reason") or ""))
        elif op == "request":
            out = SP.request_confirm(str(d.get("cap") or ""), str(d.get("reason") or ""))
        else:
            out = {"ok": False, "error": "unknown op"}
        return self._send(200, _json.dumps(out, ensure_ascii=False).encode("utf-8"),
                          "application/json; charset=utf-8")

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
        if path == "/api/route":
            return self._api_route(raw)
        if path == "/api/dispatch":
            return self._api_dispatch(raw)
        if path == "/api/bounty":
            return self._api_bounty(raw)
        if path == "/api/security/policy":
            return self._api_security_policy(raw)
        if path == "/api/omni":
            return self._api_omni(raw)
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
