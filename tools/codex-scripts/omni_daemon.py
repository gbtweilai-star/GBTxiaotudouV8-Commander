# -*- coding: utf-8 -*-
"""omni_daemon · 常驻直达（框架只 import 一次；每请求仍走 api.run_task = 统一门）。
门/审计/钢印/一次性授权消耗**全部现场由 run_task 做** —— 本件只搬请求，不是旁路。
开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"""
import json, os, pathlib, socket, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))   # 仓根进路，否则 import 不到 gbt_allinone
HOST, PORT = "127.0.0.1", int(os.environ.get("GBT_OMNI_PORT") or 8791)

def serve() -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    from gbt_allinone import api as _api
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT)); srv.listen(16)
    print(json.dumps({"ok": True, "ready": True, "port": PORT}), flush=True)
    while True:
        c, _ = srv.accept()
        try:
            f = c.makefile("rwb")
            line = f.readline()
            if not line:
                continue
            req = json.loads(line.decode("utf-8"))
            t0 = time.time()
            try:
                out = _api.run_task(str(req.get("kind") or ""), req.get("payload") or {})
            except Exception as e:
                out = {"status": "error", "error_class": "daemon_error", "message": str(e)[:200]}
            f.write((json.dumps({"ms": int((time.time() - t0) * 1000), "result": out},
                                ensure_ascii=False, default=str) + chr(10)).encode("utf-8"))
            f.flush()
        except Exception:
            pass
        finally:
            try: c.close()
            except Exception: pass

if __name__ == "__main__":
    sys.exit(serve())
