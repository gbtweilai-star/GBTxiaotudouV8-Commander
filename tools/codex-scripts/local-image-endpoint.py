"""本机图像端点（OpenAI 兼容）—— 把 ComfyUI 包成拼接网认得的 `/v1/images/generations`。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么是它
主人 2026-09-25 的标准：「**所有的东西都要跑起来了才算合格**」。
拼接网的 03 号有一个 `image` op，打的就是 OpenAI 兼容的 `/v1/images/generations`。
本机 ComfyUI（已装 · 真 SD1.5 权重 · LCM-LoRA · CPU）能真出图 ⇒ 这个进程把它包成那个形状，
于是**网里能真的调出图**，而不是打到假端点。

## 口径
- 出不来就 **503 + `{"ok":false,"reason":"未读到"}`**，并说清卡在哪（ComfyUI 没起 / 超时 / 节点报错）。
- **不许**回占位图、不许回空 data 冒充成功。
- 回的是 `{data:[{b64_json}]}`（与 OpenAI 一致）；同时把耗时、步数、尺寸写进读数。
- ⚠️ 这是 **CPU 出图**：512² / 6 步 LCM ≈ 3~4 分钟/张。**慢是真慢，但不假。**

用法：
  python tools/codex-scripts/local-image-endpoint.py serve [--port 8114] [--steps 6] [--size 512]
  python tools/codex-scripts/local-image-endpoint.py selftest
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
UA = "gbt-local-image-endpoint/1.0 (+local)"
CFG = {"port": 8114, "steps": 6, "size": 512, "timeout": 900.0,
       "comfy": "http://127.0.0.1:8188", "ckpt": "v1-5-pruned-emaonly-fp16.safetensors",
       "lora": "lcm-lora-sdv1-5.safetensors"}

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util                                          # noqa: E402

_spec = importlib.util.spec_from_file_location("lci", str(Path(__file__).resolve().parent / "local-comfy-image.py"))
lci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lci)                                   # 复用它的节点图与 PNG 判定，不复制一份


def _http(url: str, method: str = "GET", payload=None, timeout: float = 60.0) -> dict:
    data = None
    headers = {"user-agent": UA}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "status": r.status, "bytes": r.read()}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "bytes": e.read()}
    except Exception as e:                                     # noqa: BLE001
        return {"ok": False, "err": "%s: %s" % (type(e).__name__, e)}


def comfy_alive() -> dict:
    st = _http(CFG["comfy"] + "/system_stats", timeout=8)
    if not st["ok"]:
        return {"up": False, "why": st.get("err") or ("HTTP %s" % st.get("status"))}
    try:
        dev = (json.loads(st["bytes"].decode("utf-8", "replace")).get("devices") or [{}])[0]
    except Exception:                                          # noqa: BLE001
        dev = {}
    return {"up": True, "device": dev.get("name"), "type": dev.get("type")}


def generate(prompt: str, negative: str, size: int, steps: int) -> dict:
    """出一张图，回 PNG 字节。**失败一律带原因**，不编。"""
    alive = comfy_alive()
    if not alive["up"]:
        return {"ok": False, "reason": "未读到", "detail": "ComfyUI 没起：%s" % alive["why"],
                "how": "cd C:\\Users\\ADMIN\\ComfyUI; .\\.venv\\Scripts\\python.exe main.py --cpu --port 8188"}
    wf = lci.build_workflow(prompt, negative, size, steps, int(time.time()) % 100000, "gbt_api")
    t0 = time.time()
    r = _http(CFG["comfy"] + "/prompt", method="POST", payload={"prompt": wf, "client_id": "gbt-api"}, timeout=30)
    if not r["ok"]:
        return {"ok": False, "reason": "未读到", "detail": "ComfyUI 拒了这次提交：HTTP %s %s" % (r.get("status"), r["bytes"][:200])}
    pid = json.loads(r["bytes"].decode("utf-8", "replace")).get("prompt_id")
    deadline = time.time() + CFG["timeout"]
    img = None
    while time.time() < deadline:
        time.sleep(3)
        h = _http(CFG["comfy"] + "/history/" + str(pid), timeout=20)
        if not h["ok"]:
            continue
        entry = (json.loads(h["bytes"].decode("utf-8", "replace")) or {}).get(pid)
        if not entry:
            continue
        outs = (entry.get("outputs") or {}).get("9", {}).get("images") or []
        if outs:
            img = outs[0]
            break
    if not img:
        return {"ok": False, "reason": "未读到", "detail": "超时 %.0fs 没拿到图" % CFG["timeout"]}
    q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": img.get("type", "output")})
    v = _http(CFG["comfy"] + "/view?" + q, timeout=120)
    if not v["ok"]:
        return {"ok": False, "reason": "未读到", "detail": "取图失败 HTTP %s" % v.get("status")}
    data = v["bytes"]
    w, h = lci.png_size(data)
    return {"ok": True, "png": data, "ms": int((time.time() - t0) * 1000), "size": [w, h],
            "steps": steps, "device": alive.get("device"), "filename": img["filename"]}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):                                          # noqa: N802
        if self.path.rstrip("/") in ("/health", "/v1/models", "/models", "/"):
            a = comfy_alive()
            self._send(200, {
                "ok": True, "object": "list",
                "data": [{"id": "gbt-potato-v8-image", "owned_by": "GBT小土豆V8"}],
                "comfy": a, "steps": CFG["steps"], "size": CFG["size"],
                "compute_boundary": "CPU 出图：512²/6 步 ≈ 3~4 分钟/张。慢是真慢，但不假。",
            })
        else:
            self._send(404, {"error": {"message": "not found: %s" % self.path}})

    def do_POST(self):                                         # noqa: N802
        if self.path.rstrip("/") not in ("/v1/images/generations", "/images/generations"):
            self._send(404, {"error": {"message": "not found: %s" % self.path}})
            return
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads((self.rfile.read(n) if n else b"{}").decode("utf-8", "replace"))
        except Exception:                                      # noqa: BLE001
            self._send(400, {"error": {"message": "body 不是 JSON"}})
            return
        prompt = str(body.get("prompt") or "")
        if not prompt:
            self._send(400, {"error": {"message": "prompt 为空"}})
            return
        size = int(body.get("size") or CFG["size"]) if str(body.get("size") or "").isdigit() else CFG["size"]
        steps = int(body.get("steps") or CFG["steps"])
        out = generate(prompt, str(body.get("negative_prompt") or "blurry, low quality, watermark, text"), size, steps)
        if not out["ok"]:
            self._send(503, {"ok": False, "reason": out.get("reason", "未读到"), "detail": out.get("detail"),
                             "how": out.get("how"), "compute_boundary": "CPU 出图，慢。"})
            return
        self._send(200, {
            "created": int(time.time()),
            "model": "gbt-potato-v8-image",
            "data": [{"b64_json": base64.b64encode(out["png"]).decode("ascii"),
                      "revised_prompt": prompt[:120]}],
            "gbt": {"bytes": len(out["png"]), "size": out["size"], "ms": out["ms"],
                    "steps": out["steps"], "device": out["device"], "filename": out["filename"],
                    "compute_boundary": "CPU 出图；真图，不是占位。"},
        })


def selftest() -> int:
    ok = 0
    total = 0
    fails = []

    def ck(name, cond, detail=""):
        nonlocal ok, total
        total += 1
        if cond:
            ok += 1
        else:
            fails.append("%s :: %s" % (name, detail))

    # 复用的是同一个节点图（不复制一份实现）
    ck("正控·复用 local-comfy-image 的节点图", callable(lci.build_workflow) and callable(lci.png_size), "import")
    wf = lci.build_workflow("x", "y", 512, 6, 1, "p")
    ck("正控·节点图仍是 8 节点且 KSampler 在", len(wf) == 8 and wf["3"]["class_type"] == "KSampler", str(len(wf)))
    # 未就绪时的诚实出口：拿一个肯定没服务的端口探
    old = CFG["comfy"]
    CFG["comfy"] = "http://127.0.0.1:9"
    g = generate("p", "n", 512, 6)
    ck("负控·ComfyUI 没起 ⇒ ok=False 且 reason=未读到（不许编图）", g["ok"] is False and g["reason"] == "未读到", str(g)[:80])
    CFG["comfy"] = old
    ck("正控·配置里有步数/尺寸/超时（可调）", CFG["steps"] >= 1 and CFG["size"] >= 256 and CFG["timeout"] > 0, str(CFG))
    print("local-image-endpoint selftest：%d/%d" % (ok, total))
    for f in fails:
        print("  ✗ " + f)
    return 0 if ok == total else 1


def serve(port: int, steps: int, size: int) -> int:
    CFG.update({"port": port, "steps": steps, "size": size})
    a = comfy_alive()
    srv = ThreadingHTTPServer((HOST, port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("本机图像端点 :%d（ComfyUI %s · steps=%d · size=%d）" % (port, "在线" if a["up"] else "未就绪(" + str(a.get("why")) + ")", steps, size), flush=True)
    srv.serve_forever()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="本机图像端点（OpenAI 兼容，驱动 ComfyUI）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8114)
    s.add_argument("--steps", type=int, default=6)
    s.add_argument("--size", type=int, default=512)
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "serve":
        return serve(a.port, a.steps, a.size)
    if a.cmd == "selftest":
        return selftest()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
