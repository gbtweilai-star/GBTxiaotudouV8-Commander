# -*- coding: utf-8 -*-
"""权重主干（2026-10-31 · 主人令：权重融合进触手主干）

一句话口径：**任何触手要"脑子"，都来这里取，不许各自去接外面的模型。**

为什么要有它（现状的毛病）：
  以前 omni 的 ai 插座去调 deepseek、页面各自接自己的端点、桥只服务 /v1 ——
  同一件事十条线，谁在答、答的谁家的权重，说不清。这不是"融合"。

现在的形状：
   触手（omni_ai / 页面 chat / 主动引擎说话 / 桥）
        │
        ▼
   weights.chat()          ← 唯一入口
        │
        ├─ ① A19（我们的 7.6B，LM Pocket 提供运行时）── 在线就走它
        ├─ ② 后台大脑队列（A19 此刻被挂起时，入队由它拉起来算）
        └─ ③ 我们自己的整机 GPU 权重（页面工人）—— 备用
   全程标注 lane / weights_ours，**绝不静默换成外部模型**。

用法：
    python3 -c "import sys; sys.path.insert(0,'tools'); import weights; \\
                print(weights.chat('用一句话说你是谁'))"
"""
from __future__ import annotations

import json
import pathlib
import socket
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
KEY = "gbt"
MODEL = "gbt-v8-v82-q5_0"
JOBS = ROOT / "state" / "local_jobs.jsonl"
RESULTS = ROOT / "state" / "local_results.jsonl"
WORKER_HB = ROOT / "state" / "local_worker.json"
BRAIN_HB = ROOT / "state" / "a19_brain.json"


def _fresh(p: pathlib.Path, max_age: float) -> bool:
    try:
        return p.is_file() and (time.time() - p.stat().st_mtime) <= max_age
    except Exception:                                            # noqa: BLE001
        return False


def a19_ok(tmo: float = 4.0) -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:1234/v1/models",
                                     headers={"Authorization": "Bearer " + KEY})
        with urllib.request.urlopen(req, timeout=tmo) as r:
            return r.status == 200
    except Exception:                                            # noqa: BLE001
        return False


def _a19_chat(text: str, max_tokens: int, tmo: float = 180.0) -> dict:
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": text}],
                       "max_tokens": max(8, min(512, max_tokens))}).encode()
    for attempt, wait in enumerate((0, 12, 25)):
        if wait:
            time.sleep(wait)
        req = urllib.request.Request("http://127.0.0.1:1234/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + KEY})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=tmo) as r:
                d = json.loads(r.read())
                ch = (d.get("choices") or [{}])[0]
                return {"ok": True, "lane": "a19", "weights_ours": True,
                        "text": str((ch.get("message") or {}).get("content") or ""),
                        "sec": round(time.time() - t0, 2),
                        "tokens": (d.get("usage") or {}).get("completion_tokens")}
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                continue
            return {"ok": False, "lane": "a19", "err": "http=%s" % e.code}
        except Exception as e:                                   # noqa: BLE001
            return {"ok": False, "lane": "a19", "err": type(e).__name__}
    return {"ok": False, "lane": "a19", "err": "429x3"}


def _via_queue(text: str, max_tokens: int, wait_s: float = 90.0) -> dict:
    """A19 此刻被挂起 ⇒ 入队，让后台大脑把它拉起来算。"""
    jid = "W%d" % int(time.time() * 1000)
    rec = {"id": jid, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "text": text[:2000], "max_tokens": max(8, min(512, max_tokens))}
    JOBS.parent.mkdir(parents=True, exist_ok=True)
    with JOBS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    t0 = time.time()
    while time.time() - t0 < wait_s:
        if RESULTS.is_file():
            for line in RESULTS.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except Exception:                                # noqa: BLE001
                    continue
                if r.get("id") == jid:
                    return {"ok": bool(r.get("text")), "lane": "a19-brain",
                            "weights_ours": True, "text": str(r.get("text") or ""),
                            "sec": round(time.time() - t0, 2),
                            "tokens": r.get("tokens")}
        time.sleep(0.5)
    return {"ok": False, "lane": "a19-brain", "err": "队列 %.0fs 未回" % wait_s}


def chat(text: str, max_tokens: int = 128, wait_s: float = 90.0) -> dict:
    """唯一入口：**我们自己的无限制权重**（整机 GPU · 浏览器内 GGUF）。
    2026-10-31 主人令：LM Pocket 已弃用，这里不再碰它。"""
    if _fresh(WORKER_HB, 45):
        r = _via_queue(text, max_tokens, wait_s)
        if r.get("ok"):
            return r
        return {"ok": False, "lane": "ownweights", "weights_ours": True,
                "error": "工人页在岗但没交回（%s）—— 不换外部模型" % (r.get("err") or "")}
    return {"ok": False, "lane": None, "weights_ours": False,
            "error": "我们的工人页不在岗（需要开着 worker.html）—— 不换外部模型"}


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "用一句话说你是谁"
    print(json.dumps(chat(q), ensure_ascii=False, indent=1))
