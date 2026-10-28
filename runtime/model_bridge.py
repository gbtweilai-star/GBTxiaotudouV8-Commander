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
import collections
import json
import os
import pathlib
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 🔴 2026-10-25：原来写 parents[2]，那指到 /var/minis/shared（比仓库根多一层），
#   `gbt_allinone` 于是变成 "unknown location" ⇒ 四个云上游全报 err:ImportError，
#   密钥一个都取不到。本文件在 <repo>/runtime/ 下，仓库根是 parents[1]。
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 监听队列自适应（同一目录下的 runtime/adaptive_http.py）
from adaptive_http import (AdaptiveThreadingHTTPServer,  # noqa: E402
                           MAX_BACKLOG)

# name → (base_url, model, vault profile, timeout_s)
# `ours` = **我们自己的原生指挥官模型**（GBT小土豆V8 · vLLM on RunPod 无服务器）
#   端点自报 id = `/runpod-volume/gbt-v8-v83`；钥在 DPAPI 保险箱 `potato` 槽。
#   无服务器会冷启动 ⇒ 超时给到 300s（别用 60s 判它"挂了"）。
UPSTREAMS = {
    # 🔴 2026-10-25：手机上的 A19（LM Pocket，OpenAI 兼容口）。
    #    model 留空 ⇒ 桥每次问 /v1/models 拿当前加载的模型名，换权重零改动。
    # 页面（holo_pet_w3/model-chat）认的名字是 selfhost —— 名字对齐，页面不用改逻辑。
    # 指向手机自己的 A19（LM Pocket，OpenAI 兼容口）。
    "selfhost": ("http://127.0.0.1:1234/v1", "", "raw:gbt", 30),
    "ours":     ("https://api.runpod.ai/v2/qnnqf9w8xcefj8/openai/v1",
                 "/runpod-volume/gbt-v8-v83", "potato", 300),
    "ours-alt": ("https://api.runpod.ai/v2/7b5inowyar12yh/openai/v1",
                 "/runpod-volume/gbt-v8-v83", "potato", 300),
    "local":    ("http://127.0.0.1:8000/v1", "gbt-v8", None, 120),
    # 🔴 2026-10-25：本机免费模型池（FreeLLMAPI，127.0.0.1:3001，259 个模型零注册零付费）。
    #    作用：A19 那个 App 的服务是手动开关，一关整条链路就哑。接上这个，
    #    A19 不在时她照样能说话，A19 一回来又能自动切回去（见 FALLBACK）。
    #    钥不写死在这里，走 file: 槽读 0600 文件。
    #    模型用 auto：池子有 352 个模型，定死单个会在它被限流时直接 429 无路可走。
    #    会吐思维链/回包乱码的那几个已在池里打 tombstone 停用，不靠桥来兜。
    # 🔴 定模型而不是 auto：auto 在 352 个里随机飘，实测会落到吐思维链的
    #    Qwen3.5/3.6 和回包乱码的 dots-3。改成两档**已知可用**的模型轮换：
    #    mistral 1 秒、llama 2 秒，都被限流才落到 deepseek。
    #    （模型名大小写必须照抄池子里的写法，否则 404。）
    "freepool":   ("http://127.0.0.1:3001/v1", "mistral-small-3.2-24b",
                   "file:/var/minis/shared/gbtv8/vaults/freellmapi/unified_api_key", 180),
    "freepool-b": ("http://127.0.0.1:3001/v1", "llama-3.3-70b",
                   "file:/var/minis/shared/gbtv8/vaults/freellmapi/unified_api_key", 180),
    "agnes":    ("https://apihub.agnes-ai.com/v1", "agnes-2.5-flash", "agnes", 180),
    # 🔴 2026-10-26：DeepSeek 侧已换代为 V4.1-Flash（发布日 1017）。
    #    口径：API 只认 deepseek-flash / deepseek-v4-pro（传 -1017 后缀直接 400）；
    #    deepseek-chat 仍可用但已被静默映射到 flash —— 显式写 flash，别靠别名。
    #    上下文 1,048,576 / 单次输出上限 393,216 / 吃图 / effort=low|high|max。
    #    钥走 0600 文件槽：本机没有 DPAPI 保险箱，profile 名取不到钥（实测 key_ready=false）。
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat",
                 "file:/var/minis/shared/gbtv8/vaults/deepseek/api_key", 180),
    "deepseek-pro": ("https://api.deepseek.com/v1", "deepseek-v4-pro",
                 "file:/var/minis/shared/gbtv8/vaults/deepseek/api_key", 300),
    "openai":   ("https://api.openai.com/v1", "gpt-4o-mini", "openai", 180),
}
DEFAULT = "selfhost"     # A19 优先：手机自己的算力

# 哪些上游算「自有权重」（页面据此标 ✅ / ⚠）。免费池和云端通用模型都不算。
OURS_LANES = {"selfhost", "ours", "ours-alt", "local"}

# 降级链：指定的上游**网络不可达**时，按顺序自动往下试，不让整条链路哑掉。
# 只在「连不上/超时」时降级；上游明确回了 4xx/5xx 就如实上报，不掩盖。
# 显式在请求里写了 upstream 的，尊重调用方选择，不降级。
FALLBACK = {
    "selfhost":   ["deepseek", "freepool", "freepool-b"],
    "local":      ["deepseek", "freepool", "freepool-b"],
    "ours":       ["freepool", "freepool-b", "deepseek"],
    "ours-alt":   ["freepool", "freepool-b", "deepseek"],
    "freepool":   ["freepool-b", "deepseek"],
    "freepool-b": ["deepseek"],
    "agnes":      ["freepool", "freepool-b", "deepseek"],
    "deepseek":   ["freepool", "freepool-b"],
    "openai":     ["freepool", "freepool-b", "deepseek"],
}
UA = "gbt-v8/model-bridge"

# 她的对话落盘（2026-10-26）：容器一断、页面一关，说过的话还在。
TRANSCRIPT = str(ROOT / "state" / "her_transcript.jsonl")
# 落盘去重（2026-10-26）：页面离线时先存本地、回来补传，
# 补传可能"提交成功但回包丢了" ⇒ 重试会写重复行。按客户端给的 id 去重。
LOG_IDS = collections.deque(maxlen=500)
# 品味内核（吞噬 taste-skill 后蒸馏，见 docs/19-taste-absorbed.md）
TASTE_KERNEL = str(ROOT / "state" / "taste_kernel.txt")
PERSONA = str(ROOT / "state" / "her_persona.txt")
PERSONA_LITE = str(ROOT / "state" / "her_persona_lite.txt")

# 🔴 2026-10-26 主人口径：「使用 A19 不使用云端」。
#    selfhost（A19）探不到时**不再静默降级**到免费池/DeepSeek ——
#    宁可如实报错（调用方自己决定要不要换车道），也不许拿别人的模型冒充她的。
#    确需旧行为（可用性优先）时：export GBT_ALLOW_CLOUD_FALLBACK=1
if not os.environ.get("GBT_ALLOW_CLOUD_FALLBACK"):
    FALLBACK["selfhost"] = []
    FALLBACK["local"] = []


def key_for(profile: str | None) -> tuple[str, str]:
    """返回 (key, slot_name)。本地 vLLM 不需要钥 ⇒ ('EMPTY','none:local')。"""
    if not profile:
        return "EMPTY", "none:local"
    # 🔴 2026-10-25：本机回环端点的字面钥（如 LM Pocket 的 gbt）。
    #    只用于 127.0.0.1，不进金库、不入日志。
    if profile.startswith("raw:"):
        return profile[4:], "raw:loopback"
    # 🔴 2026-10-25：从 0600 文件读钥（本机免费池等）。钥不出现在源码里。
    if profile.startswith("file:"):
        path = profile[5:]
        try:
            with open(path, "r", encoding="utf-8") as fh:
                key = fh.read().strip()
            if key:
                return key, "file:" + path.rsplit("/", 1)[-1]
            return "", "empty:" + path.rsplit("/", 1)[-1]
        except Exception as exc:                              # noqa: BLE001
            return "", "err:%s" % type(exc).__name__
    try:
        # 🔴 import 必须在 try 里面 —— 早先放在外面，
        #    `deepseek_key` 模块未随仓库发布时 torch 直接抛 ImportError，
        #    整个 /health 500，页面判不出桥在不在。
        from gbt_allinone import deepseek_key as DK
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
        self.send_header("Access-Control-Expose-Headers",
                         "X-GBT-Lane, X-GBT-Weights-Ours, X-GBT-Fallback-From")

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
                                    # 监听队列自适应读数：随时能看它现在开到多大
                                    "backlog": (self.server.backlog_stats()
                                                if hasattr(self.server, "backlog_stats") else {}),
                                    "note": "钥只在桥里；页面永远拿不到明文"})
        # ── 她的对话落盘：读回最近 n 条（页面打开时恢复「上次她说了什么」）──────
        if self.path.startswith("/_log/tail"):
            n = 20
            try:
                q = self.path.split("?", 1)[1] if "?" in self.path else ""
                for kv in q.split("&"):
                    if kv.startswith("n="):
                        n = max(1, min(200, int(kv[2:])))
            except Exception:                                     # noqa: BLE001
                n = 20
            rows = []
            try:
                with open(TRANSCRIPT, encoding="utf-8") as fh:
                    for line in fh.readlines()[-n:]:
                        line = line.strip()
                        if line:
                            rows.append(json.loads(line))
            except Exception:                                     # noqa: BLE001
                rows = []
            return self._json(200, {"ok": True, "count": len(rows), "rows": rows,
                                    "file": TRANSCRIPT})
        # ── 品味内核：页面「🎨 品味」按钮从这里取，避免把 1.2k token 写进 HTML ──
        # ── 她的人格：页面「人格」按钮从这里取（说话自然靠它，不是靠模型大小）
        if self.path.startswith("/_persona"):
            try:
                # ?lite=1 ⇒ 407 字精简版（默认），否则 1182 字全量版
                lite = "lite=1" in self.path or "lite" == self.path.split("?")[-1]
                with open(PERSONA_LITE if lite else PERSONA, encoding="utf-8") as fh:
                    text = fh.read()
                return self._json(200, {"ok": True, "chars": len(text),
                                        "lite": lite,
                                        "file": PERSONA_LITE if lite else PERSONA,
                                        "persona": text})
            except Exception as exc:                              # noqa: BLE001
                return self._json(500, {"ok": False,
                                        "error": "%s: %s" % (type(exc).__name__, exc)})
        if self.path.startswith("/_taste"):
            try:
                with open(TASTE_KERNEL, encoding="utf-8") as fh:
                    text = fh.read()
                return self._json(200, {"ok": True, "chars": len(text),
                                        "file": TASTE_KERNEL, "kernel": text})
            except Exception as exc:                              # noqa: BLE001
                return self._json(500, {"ok": False,
                                        "error": "%s: %s" % (type(exc).__name__, exc)})
        if self.path.startswith("/v1/models"):
            return self._json(200, {"object": "list", "data": [
                {"id": m, "owned_by": n, "base_url": b} for n, (b, m, _p, _t) in UPSTREAMS.items()]})
        return self._json(404, {"error": {"message": "no route %s" % self.path}})

    def do_POST(self):                                        # noqa: N802
        KNOWN = ("/v1/chat/completions", "/v1/route", "/v1/dispatch", "/_log/message",
                 "/voice/speak", "/voice/status")
        if not any(self.path.startswith(k) for k in KNOWN):
            return self._json(404, {"error": {"message": "no route %s" % self.path}})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as exc:                              # noqa: BLE001
            return self._json(400, {"error": {"message": "请求体不是 JSON：%s" % exc}})

        # ── 她的对话落盘：页面每说一句就追加一行 ────────────────────────────
        # ── 她的嗓子（单一门）───────────────────────────────────────────────
        # 🔴 2026-10-28：页面里本来直接调 window.speechSynthesis.speak()，
        #   而 iOS WebKit 的 getVoices() 首次常返回 0 ⇒ 落到错嗓音念中文 ⇒ 鬼叫。
        #   现在页面的唯一出口是这里：走 tentacle_bus 的嘴（edge-tts 曉臻·台湾腔），
        #   实在没有 edge-tts 才退 apple-speak zh-TW；两条都没有就如实说没有。
        if self.path.startswith("/voice/speak"):
            text = str(body.get("text") or "")[:500]
            if not text:
                return self._json(400, {"ok": False, "error": {"message": "缺 text"}})
            try:
                sys.path.insert(0, str(ROOT / "tools"))
                import tentacle_bus as _BUS
                out = _BUS.call("mouth", text)
            except Exception as exc:                          # noqa: BLE001
                return self._json(500, {"ok": False,
                                        "error": {"message": "%s: %s" %
                                                  (type(exc).__name__, str(exc)[:120])}})
            # 🔴 2026-10-28：页面（:8080）访问不到 /var/minis/attachments。
            #   所以把 TTS 产物**同时**放进仓库里被 :8080 服务的目录，
            #   并回一个 url —— 数字人页面直接 new Audio(url) 就能播 + 挂口型分析器。
            try:
                if out.get("ok") and out.get("file"):
                    import shutil as _sh
                    _dst = ROOT / "holo_pet_w3" / "digital-human" / "voice"
                    _dst.mkdir(parents=True, exist_ok=True)
                    _name = pathlib.Path(out["file"]).name
                    _sh.copyfile(out["file"], _dst / _name)
                    out["url"] = "/holo_pet_w3/digital-human/voice/" + _name
            except Exception as _e:                           # noqa: BLE001
                out["url_err"] = type(_e).__name__
            return self._json(200 if out.get("ok") else 500, out)

        if self.path.startswith("/voice/status"):
            try:
                sys.path.insert(0, str(ROOT / "tools"))
                import tentacle_bus as _BUS
                return self._json(200, _BUS.status())
            except Exception as exc:                          # noqa: BLE001
                return self._json(500, {"ok": False, "error": {"message": str(exc)[:120]}})

        if self.path.startswith("/_log/message"):
            try:
                rid = str(body.get("id") or "")
                if rid and rid in LOG_IDS:
                    return self._json(200, {"ok": True, "saved": False,
                                            "dup": True, "file": TRANSCRIPT})
                if rid:
                    LOG_IDS.append(rid)
                os.makedirs(os.path.dirname(TRANSCRIPT), exist_ok=True)
                rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                       "role": str(body.get("role") or "?"),
                       "text": str(body.get("text") or "")[:8000],
                       "upstream": body.get("upstream"),
                       "model": body.get("model"),
                       # 谁记的这一行：page（她的原生界面）/ minis（这个对话框）/ test
                       "source": str(body.get("source") or "page")}
                with open(TRANSCRIPT, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                return self._json(200, {"ok": True, "saved": True, "file": TRANSCRIPT})
            except Exception as exc:                              # noqa: BLE001
                return self._json(500, {"ok": False,
                                        "error": "%s: %s" % (type(exc).__name__, exc)})

        # ── 派活①：先问模型该落哪个能力位，再用目录校验（幻觉当场拒）────────────
        if self.path.startswith("/v1/route"):
            return self._route(body)
        # ── 派活②：真调一次（**走唯一门 run_task**，门拒就如实回拒）────────────
        if self.path.startswith("/v1/dispatch"):
            return self._dispatch(body)

        explicit = str(body.pop("upstream", "") or "").strip()
        name = explicit or DEFAULT
        if name not in UPSTREAMS:
            return self._json(400, {"error": {"message": "不认的上游：%s（可选 %s）"
                                              % (name, ",".join(UPSTREAMS))}})
        stream = bool(body.get("stream"))

        # 降级链：**默认就开**，即使调用方显式点名了上游也照样降级。
        #   原因：页面每次都把下拉值当 upstream 发上来（值恒为 selfhost），
        #   若"显式就不降级"，等于从 UI 上把整条保底链路关死 —— 实测她直接哑掉。
        #   可用性优先：连不上就往下试，响应里用 upstream/_fallback_from 如实说明谁答的。
        #   要严格不走保底，请求体里带 "fallback": false。
        allow_fb = body.pop("fallback", True) is not False
        chain = [name]
        if allow_fb:
            chain += [n for n in FALLBACK.get(name, []) if n != name]

        t0 = time.perf_counter()
        resp = None
        used, used_slot = name, ""
        tried = []
        for cand in chain:
            base, model_default, profile, timeout_s = UPSTREAMS[cand]
            # 首个沿用调用方给的 model；降级时换成本游默认模型（各家认的名字不同）
            if cand == name:
                body.setdefault("model", model_default)
            elif model_default:
                body["model"] = model_default
            key, slot = key_for(profile)
            if not key:
                tried.append({"upstream": cand, "skip": "无钥（槽 %s）" % slot})
                continue
            url = base.rstrip("/") + "/chat/completions"
            req = urllib.request.Request(
                url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
                headers={"Content-Type": "application/json", "User-Agent": UA,
                         "Authorization": "Bearer " + key})
            try:
                resp = urllib.request.urlopen(req, timeout=timeout_s)
                used, used_slot = cand, slot
                if cand != name:
                    sys.stderr.write("[bridge] fallback %s → %s\n" % (name, cand))
                break
            except urllib.error.HTTPError as exc:
                raw = (exc.read() or b"")[:800].decode("utf-8", "replace")
                sys.stderr.write("[bridge] upstream=%s model=%s http=%s slot=%s\n"
                                 % (cand, body.get("model"), exc.code, slot))
                # 5xx = 上游自己挂了 ⇒ 继续往下降级；4xx = 请求本身不对 ⇒ 如实上报，别掩盖
                # 5xx=上游挂了，429=上游限流 ⇒ 都继续往下降级；其余 4xx=请求本身不对，如实报
                if exc.code in (429, 529) or exc.code >= 500:
                    if cand != chain[-1]:
                        tried.append({"upstream": cand, "http": exc.code})
                        resp = None
                        continue
                return self._json(200, {"ok": False, "http": exc.code, "upstream": cand,
                                        "key_slot": slot, "upstream_error": raw,
                                        "tried": tried,
                                        "error": {"message": raw}})
            except Exception as exc:                          # noqa: BLE001
                sys.stderr.write("[bridge] upstream=%s net_error=%s\n"
                                 % (cand, type(exc).__name__))
                tried.append({"upstream": cand, "net_error": type(exc).__name__})
                resp = None
                continue

        if resp is None:
            return self._json(200, {"ok": False, "upstream": name, "key_slot": "",
                                    "tried": tried,
                                    "error": {"message": "所有上游都连不上：%s"
                                                         % ", ".join(str(t.get("upstream")) for t in tried)}})
        name, slot = used, used_slot

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            # 流式也报「实走哪条」——页面从响应头读，读不到就印「实走 ?」
            self.send_header("X-GBT-Lane", name)
            self.send_header("X-GBT-Weights-Ours",
                             "true" if name in OURS_LANES else "false")
            self.send_header("X-GBT-Fallback-From", chain[0])
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
        dt = time.perf_counter() - t0
        sys.stderr.write("[bridge] upstream=%s model=%s http=200 slot=%s %.2fs\n"
                         % (name, body.get("model"), slot, dt))
        # 🔴 2026-10-25：把「实走哪条」写进回包，页面才有得显示。
        #   原来纯透传，上游不返回这条信息 ⇒ 页面永远印「实走 ?」，
        #   分不清答话的到底是自有权重还是降级来的免费池。
        try:
            d = json.loads(raw.decode("utf-8", "replace"))
            d["gbt"] = {"lane": name,
                        "weights_ours": name in OURS_LANES,
                        "fallback_from": chain[0] if name != chain[0] else None,
                        "key_slot": slot,
                        "elapsed_s": round(dt, 2),
                        "bridge": "gbt-v8/model-bridge"}
            raw = json.dumps(d, ensure_ascii=False).encode("utf-8")
        except Exception:                                     # noqa: BLE001
            pass                                              # 不是 JSON 就原样透传
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-GBT-Lane", name)
        self.send_header("X-GBT-Weights-Ours", "true" if name in OURS_LANES else "false")
        self._cors()
        self.end_headers()
        self.wfile.write(raw)


def serve(port: int) -> int:
    # 🔴 2026-10-25：并发一高就 URLError / connection reset，根因是
    #   socketserver 的监听队列默认只有 5（request_queue_size=5）——
    #   连接在建连阶段就被内核丢掉，跟"触手多少根"毫无关系（触手本身不设闸）。
    #   这里换成**自适应**版：队列按压力自动跟随，不写死数字。见 runtime/adaptive_http.py
    srv = AdaptiveThreadingHTTPServer(("127.0.0.1", port), Handler)
    sys.stderr.write("[bridge] 监听队列自适应：初始 %d（上限 %d）\n"
                     % (srv._cur_backlog, MAX_BACKLOG))
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
