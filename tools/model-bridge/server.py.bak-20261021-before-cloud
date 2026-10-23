# -*- coding: utf-8 -*-
"""原生 APP ⇄ 原生大模型 的本地桥（127.0.0.1:8791，只监听回环）。

为什么要它：Electron 壳里的页面是 `file://`，**不能把密钥写进页面**（那等于把钥发给任何能看网页的人）。
所以页面只连本机桥，桥拿 DPAPI 保险箱里的钥去打上游，回执里**只出现槽名**，永不回显明文。

对外只三件：
  GET  /health                  —— 桥活着吗、每个上游配好没（不回钥）
  GET  /v1/models               —— 给界面用的模型清单
  POST /v1/chat/completions     —— 转发（支持 stream=true 的 SSE 直通）

纪律：
  · 只监听 127.0.0.1；不接外部连接；
  · 钥只从 `deepseek_key.load_key(profile)` 取（DPAPI），缺钥就如实报缺，不假装；
  · 上游 4xx/5xx 的原话必须带回来（P19），不许只说"失败了"；
  · 不落聊天内容（隐私）：只在 stderr 打一行 `slot/model/http/耗时`。

用法：
  py -3.14 -X utf8 tools/model-bridge/server.py            # 前台跑，Ctrl-C 停
  py -3.14 -X utf8 tools/model-bridge/server.py --port 8791 --self-test   # 自检一次就退
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# name → (base_url, model, vault profile, timeout_s)
# `ours` = **我们自己的原生指挥官模型**（GBT小土豆V8 · vLLM on RunPod 无服务器）
#   端点自报 id = `/runpod-volume/gbt-v8-v83`；钥在 DPAPI 保险箱 `potato` 槽。
#   无服务器会冷启动 ⇒ 超时给到 300s（别用 60s 判它"挂了"）。
UPSTREAMS = {
    "ours":     ("https://api.runpod.ai/v2/qnnqf9w8xcefj8/openai/v1",
                 "/runpod-volume/gbt-v8-v83", "potato", 300),
    "ours-alt": ("https://api.runpod.ai/v2/7b5inowyar12yh/openai/v1",
                 "/runpod-volume/gbt-v8-v83", "potato", 300),
    "local":    ("http://127.0.0.1:8000/v1", "gbt-v8", None, 120),
    "agnes":    ("https://apihub.agnes-ai.com/v1", "agnes-2.5-flash", "agnes", 180),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat", "deepseek", 180),
    "openai":   ("https://api.openai.com/v1", "gpt-4o-mini", "openai", 180),
}
DEFAULT = "ours"
UA = "gbt-v8/model-bridge"


def key_for(profile: str | None) -> tuple[str, str]:
    """返回 (key, slot_name)。本地 vLLM 不需要钥 ⇒ ('EMPTY','none:local')。"""
    if not profile:
        return "EMPTY", "none:local"
    from gbt_allinone import deepseek_key as DK
    try:
        key, _src = DK.load_key(profile)
        if key:
            return key, "vault:" + profile
    except Exception as exc:                                  # noqa: BLE001
        return "", "err:%s" % type(exc).__name__
    return "", "missing:" + profile


def _post_json(url: str, payload: dict, key: str, timeout_s: int) -> tuple[int, bytes]:
    """发一发 JSON，返回 (http, 原始字节)；4xx/5xx 也把上游原话带回来（P19）。"""
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": UA,
                 "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.read() or b"")
    except Exception as exc:                                  # noqa: BLE001
        return -1, ("%s: %s" % (type(exc).__name__, str(exc)[:200])).encode("utf-8")


def _extract_json(text: str) -> dict | None:
    """从模型回话里抠出第一个 JSON 对象（允许前后带尾巴/```）。"""
    if not text:
        return None
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        got = json.loads(text[start:i + 1])
                    except Exception:                         # noqa: BLE001
                        break
                    if isinstance(got, dict):
                        return got
                    break
        start = text.find("{", start + 1)
    return None


def _release_root() -> "pathlib.Path | None":
    """找 gbt_commander 检索库所在的根：线上仓与发布仓布局不同，两处都认。"""
    for cand in (ROOT / "outputs" / "open-source-release", ROOT):
        if (cand / "gbt_commander").is_dir() and (cand / "data" / "capabilities.json").is_file():
            return cand
    return None


def _shortlist(question: str, cat: dict, k: int = 18) -> tuple[list[str], str]:
    """把 341 位收窄成候选，再让模型挑。

    为什么需要：实测（2026-10-21）让 7B 级模型直接面对 341 位时，它回的是
    `py -3.14 tools/codex-scripts/release.py` 这种**命令行**，不是能力位名 ——
    收窄到十几个候选后它才在"名字"这个层面作答。
    收窄用的是**已发布那套检索**（`gbt_commander.Catalog.search`：词表 + IDF），不另写一套。
    """
    rel = _release_root()
    try:
        if rel is None:
            raise RuntimeError("找不到 gbt_commander")
        if str(rel) not in sys.path:
            sys.path.insert(0, str(rel))
        from gbt_commander import Catalog                    # noqa: PLC0415
        c = Catalog.load(rel / "data" / "capabilities.json")
        hits = [cap.name for cap, _score in c.search(question, k)]
        hits = [h for h in hits if h in cat]
        if hits:
            return hits, "gbt_commander.search"
        raise RuntimeError("search 空")
    except Exception as exc:                                  # noqa: BLE001
        return sorted(cat)[:k], "fallback-first-%d(%s)" % (k, type(exc).__name__)


class Handler(BaseHTTPRequestHandler):
    server_version = "gbt-model-bridge/1.0"
    protocol_version = "HTTP/1.1"

    # ---------- 小工具 ----------
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):                        # 只留一行最小读数
        sys.stderr.write("[bridge] %s\n" % (fmt % args))

    # ---------- 派活：两个 POST 端点 ----------
    @staticmethod
    def _catalog() -> dict:
        for p in (ROOT / "outputs" / "open-source-release" / "data" / "capabilities.json",
                  ROOT / "data" / "capabilities.json"):
            if p.is_file():
                try:
                    raw = json.loads(p.read_text(encoding="utf-8"))
                    caps = raw.get("capabilities") if isinstance(raw, dict) else raw
                    return {c["name"]: c for c in caps if isinstance(c, dict) and c.get("name")}
                except Exception:                             # noqa: BLE001
                    continue
        return {}

    def _route(self, body: dict) -> None:
        """问模型“该落哪个能力位”，再用**目录**校验（查不到就是幻觉，当场拒）。"""
        question = str(body.get("question") or "").strip()
        if not question:
            return self._json(400, {"ok": False, "error": {"message": "缺 question"}})
        cat = self._catalog()
        if not cat:
            return self._json(200, {"ok": False,
                                    "error": {"message": "读不到能力目录（capabilities.json）"}})
        # 先把 341 位**收窄成候选**，再让模型在这几个里挑 —— 7B 级模型直接面对 341 位会开始编命令
        # （实测它 2026-10-21 回的是 `py -3.14 tools/codex-scripts/release.py` 这种命令行）。
        # 收窄用的是我们**已发布的那套检索**（gbt_commander.Catalog），不另写一套：单一真源。
        short, how_short = _shortlist(question, cat, k=int(body.get("k") or 18))
        if not short:
            return self._json(200, {"ok": False,
                                    "error": {"message": "候选为空（检索没命中任何能力位）"}})
        prompt = ("你是 GBT小土豆V8 总指挥。下面是从 341 位里筛出的候选能力位：\n%s\n"
                  "用户的话：%s\n"
                  "只回答最该执行的那一个能力位名字本身（不要解释、不要命令、不要代码块、不要标点）。"
                  % ("\n".join("- " + s for s in short), question))
        name = str(body.get("upstream") or DEFAULT)
        cfg = UPSTREAMS.get(name) or UPSTREAMS[DEFAULT]
        base, model, profile, timeout_s = cfg
        key, slot = key_for(profile)
        if not key:
            return self._json(200, {"ok": False, "key_slot": slot,
                                    "error": {"message": "没有可用钥匙（槽 %s）" % slot}})
        payload = {"model": model, "max_tokens": 60, "temperature": 0,
                   "messages": [{"role": "user", "content": prompt}]}
        t0 = time.perf_counter()
        st, raw = _post_json(base.rstrip("/") + "/chat/completions", payload, key, timeout_s)
        dt = round(time.perf_counter() - t0, 2)
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        if st != 200:
            return self._json(200, {"ok": False, "http": st, "upstream": name, "key_slot": slot,
                                    "error": {"message": text[:400]}})
        try:
            d = json.loads(text)
        except Exception:                                     # noqa: BLE001
            return self._json(200, {"ok": False, "error": {"message": "回包不是 JSON"}})
        msg = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        answer = msg.strip().strip("`'\"。.,，:：\n\t ")
        cap, how = "", "模型原话不匹配目录"
        if answer in cat:                                     # ① 原话就是位名
            cap, how = answer, "模型原话精确命中"
        else:                                                 # ② 话里带了位名 ⇒ 取最长的那个
            for cand in sorted(cat, key=len, reverse=True):
                if cand in answer:
                    cap, how = cand, "模型原话里含位名"
                    break
        hit = cat.get(cap)
        out = {"ok": bool(hit), "capability": cap or answer, "args": {}, "match": how,
               "reason": answer[:80], "verified": bool(hit),
               "upstream": name, "model": d.get("model"), "elapsed_s": dt,
               "usage": d.get("usage") or {}, "key_slot": slot,
               "catalog_size": len(cat), "shortlist": short, "shortlist_by": how_short}
        if not hit:
            out["error"] = {"message": "模型给的名字在 341 位目录里查不到（幻觉或措辞不符）：%r"
                                       % (answer[:60] or "<空>")}
            return self._json(200, out)
        out.update({"domain": hit.get("domain"), "readonly": hit.get("readonly"),
                    "scopes_static": hit.get("scopes_static"),
                    "requires_params": hit.get("requires_params"),
                    "params_hint": hit.get("params_hint")})
        return self._json(200, out)

    def _dispatch(self, body: dict) -> None:
        """真调一次：**只走唯一门 run_task**。门缺票就如实回缺，不绕。"""
        kind = str(body.get("capability") or body.get("kind") or "").strip()
        if not kind:
            return self._json(400, {"ok": False, "error": {"message": "缺 capability"}})
        cat = self._catalog()
        if cat and kind not in cat:
            return self._json(400, {"ok": False,
                                    "error": {"message": "目录里没有这位能力位：%s" % kind}})
        payload = body.get("args") or {}
        if not isinstance(payload, dict):
            return self._json(400, {"ok": False, "error": {"message": "args 必须是对象"}})
        t0 = time.perf_counter()
        try:
            from gbt_allinone import run_task
            env = run_task(kind, payload) or {}
        except Exception as exc:                              # noqa: BLE001
            return self._json(200, {"ok": False, "capability": kind,
                                    "error": {"message": "%s: %s" % (type(exc).__name__,
                                                                     str(exc)[:300])}})
        dt = round(time.perf_counter() - t0, 2)
        sys.stderr.write("[bridge] dispatch kind=%s %.2fs\n" % (kind, dt))
        env = env if isinstance(env, dict) else {}
        # 门的拒绝信封把缺票放在 `missing`，正常的放 `missing_scopes` —— 两处都读，别念成空。
        missing = env.get("missing_scopes") or env.get("missing") or None
        return self._json(200, {"ok": bool(env.get("status") == "ok" or env.get("ok")),
                                "capability": kind, "elapsed_s": dt,
                                "gate": env.get("gate"),
                                "status": env.get("status"),
                                "denied": bool(env.get("denied")),
                                "message": env.get("message") or env.get("reason"),
                                "missing_scopes": missing,
                                "how_to_grant": env.get("how_to_grant"),
                                "envelope": env})

    # ---------- 路由 ----------
    def do_OPTIONS(self):                                     # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):                                         # noqa: N802
        if self.path.startswith("/health"):
            ups = []
            for name, (base, model, prof, _to) in UPSTREAMS.items():
                key, slot = key_for(prof)
                ups.append({"name": name, "base_url": base, "model": model,
                            "key_slot": slot, "key_ready": bool(key)})
            return self._json(200, {"ok": True, "service": "gbt-model-bridge",
                                    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    "default": DEFAULT, "upstreams": ups,
                                    "note": "钥只在桥里；页面永远拿不到明文"})
        if self.path.startswith("/v1/models"):
            return self._json(200, {"object": "list", "data": [
                {"id": m, "owned_by": n, "base_url": b} for n, (b, m, _p, _t) in UPSTREAMS.items()]})
        return self._json(404, {"error": {"message": "no route %s" % self.path}})

    def do_POST(self):                                        # noqa: N802
        KNOWN = ("/v1/chat/completions", "/v1/route", "/v1/dispatch")
        if not any(self.path.startswith(k) for k in KNOWN):
            return self._json(404, {"error": {"message": "no route %s" % self.path}})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as exc:                              # noqa: BLE001
            return self._json(400, {"error": {"message": "请求体不是 JSON：%s" % exc}})

        # ── 派活①：先问模型该落哪个能力位，再用目录校验（幻觉当场拒）────────────
        if self.path.startswith("/v1/route"):
            return self._route(body)
        # ── 派活②：真调一次（**走唯一门 run_task**，门拒就如实回拒）────────────
        if self.path.startswith("/v1/dispatch"):
            return self._dispatch(body)

        name = str(body.pop("upstream", "") or DEFAULT)
        if name not in UPSTREAMS:
            return self._json(400, {"error": {"message": "不认的上游：%s（可选 %s）"
                                              % (name, ",".join(UPSTREAMS))}})
        base, model_default, profile, timeout_s = UPSTREAMS[name]
        body.setdefault("model", model_default)
        stream = bool(body.get("stream"))

        key, slot = key_for(profile)
        if not key:
            return self._json(200, {"error": {"message": "没有可用钥匙（槽 %s）" % slot,
                                              "slot": slot},
                                    "ok": False})

        url = base.rstrip("/") + "/chat/completions"
        t0 = time.perf_counter()
        req = urllib.request.Request(
            url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "User-Agent": UA,
                     "Authorization": "Bearer " + key})
        try:
            resp = urllib.request.urlopen(req, timeout=timeout_s)
        except urllib.error.HTTPError as exc:
            raw = (exc.read() or b"")[:800].decode("utf-8", "replace")
            sys.stderr.write("[bridge] upstream=%s model=%s http=%s slot=%s\n"
                             % (name, body.get("model"), exc.code, slot))
            return self._json(200, {"ok": False, "http": exc.code, "upstream": name,
                                    "key_slot": slot, "upstream_error": raw,
                                    "error": {"message": raw}})
        except Exception as exc:                              # noqa: BLE001
            sys.stderr.write("[bridge] upstream=%s net_error=%s\n" % (name, type(exc).__name__))
            return self._json(200, {"ok": False, "upstream": name, "key_slot": slot,
                                    "error": {"message": "%s: %s" % (type(exc).__name__, exc)}})

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self._cors()
            self.end_headers()
            try:
                while True:
                    chunk = resp.readline()
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except Exception:                                 # noqa: BLE001
                pass
            sys.stderr.write("[bridge] stream upstream=%s model=%s slot=%s %.2fs\n"
                             % (name, body.get("model"), slot, time.perf_counter() - t0))
            return

        raw = resp.read()
        sys.stderr.write("[bridge] upstream=%s model=%s http=200 slot=%s %.2fs\n"
                         % (name, body.get("model"), slot, time.perf_counter() - t0))
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)


def serve(port: int) -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("模型桥已起：http://127.0.0.1:%d  （只在回环；Ctrl-C 停）" % port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停。")
    return 0


def self_test(port: int) -> int:
    """起一个线程跑桥，打一发真请求，打印读数后退出（证明桥真能用，不是写完就算）。"""
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    time.sleep(0.3)
    import urllib.request as U
    health = json.loads(U.urlopen("http://127.0.0.1:%d/health" % port, timeout=10).read())
    print("health ok=%s · 上游 %d 个 · 钥就绪：%s"
          % (health.get("ok"), len(health.get("upstreams") or []),
             {u["name"]: u["key_ready"] for u in health.get("upstreams") or []}))
    body = json.dumps({"upstream": DEFAULT, "model": UPSTREAMS[DEFAULT][1],
                       "messages": [{"role": "user", "content": "回一句：桥已接通。"}],
                       "max_tokens": 200}).encode()
    req = U.Request("http://127.0.0.1:%d/v1/chat/completions" % port, data=body,
                    headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        raw = U.urlopen(req, timeout=120).read()
    except Exception as exc:                                  # noqa: BLE001
        print("请求失败：", type(exc).__name__, exc)
        srv.shutdown()
        return 1
    dt = time.perf_counter() - t0
    d = json.loads(raw)
    if d.get("ok") is False or d.get("error"):
        print("上游/桥报错：", json.dumps(d, ensure_ascii=False)[:400])
        srv.shutdown()
        return 1
    msg = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    print("真回执：%.2fs · model=%s · usage=%s" % (dt, d.get("model"), d.get("usage")))
    print("正文前 120 字：%s" % msg.strip().replace("\n", " ")[:120])
    srv.shutdown()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    return self_test(a.port) if a.self_test else serve(a.port)


if __name__ == "__main__":
    raise SystemExit(main())
