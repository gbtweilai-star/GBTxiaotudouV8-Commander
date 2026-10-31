# -*- coding: utf-8 -*-
"""Agnes 客户端（2026-10-31 · 修 429）

诊断结论（实测，非推测）：
    密钥          ✅ 完全正确（连续 5 次 HTTP 200，/v1/models 也 200）
    429 真因      ❌ 免费档额度：约 **5 次/窗口（~30 秒）**
    429 原文      "You've reached the API rate limit for free users. Upgrade to a Token Plan..."
    恢复时间      实测 30 秒后恢复 200

另一个必须处理的坑（实测）：
    每次调用 prompt_tokens ≈ 285（其中 256 命缓存），且模型先把话写进
    reasoning_content。max_tokens=8 时 reasoning 直接吃满 ⇒ text_tokens=0、content=""。
    ⇒ max_tokens 必须 ≥512，且解析要能回落 reasoning_content。

用法：
    from tools import agnes_client
    r = agnes_client.chat("你好")          # 自动限速 + 退避 + 双字段解析
    r["text"], r["from_reasoning"], r["wait"]
"""
from __future__ import annotations

import json
import pathlib
import time
import urllib.error
import urllib.request

BASE = "https://apihub.agnes-ai.com/v1"
MODEL = "agnes-2.5-flash"
STATE = pathlib.Path(__file__).resolve().parents[1] / "state" / "agnes_rate.json"

# 实测：免费档约 5 次/30s。留余量 ⇒ 每 8 秒最多 1 次（≈7.5 次/分钟上限的保守值）
MIN_INTERVAL = 8.0
MAX_TOKENS = 768                       # 512 被 reasoning 吃掉的情况都见过


def _key() -> str:
    import os
    k = os.environ.get("AGNES_API_KEY", "").strip()
    if k:
        return k
    p = pathlib.Path(__file__).resolve().parents[1] / "store" / "secrets" / "agnes.key"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "缺 AGNES_API_KEY。设置环境变量，或写入 store/secrets/agnes.key。"
        "（不要写进代码）")


def _load_rate() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"last": 0.0, "strikes": 0, "until": 0.0}


def _save_rate(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d), encoding="utf-8")


def _wait_turn() -> float:
    """按实测额度排队：保证距上次调用 ≥ MIN_INTERVAL，且尊重退避截止时间。"""
    d = _load_rate()
    now = time.time()
    gap = max(d.get("until", 0.0) - now, d["last"] + MIN_INTERVAL - now, 0.0)
    if gap > 0:
        time.sleep(gap)
    return gap


def chat(text: str, max_tokens: int = MAX_TOKENS, tmo: float = 120.0,
         retries: int = 3) -> dict:
    """发一句话，返回 {ok,text,from_reasoning,wait,tokens,error}。429 自动退避重试。"""
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": text}],
        "max_tokens": max(max_tokens, 512),
    }).encode("utf-8")
    waited_total = 0.0
    for attempt in range(retries):
        waited_total += _wait_turn()
        req = urllib.request.Request(
            BASE + "/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + _key()},
            method="POST")
        d = _load_rate()
        try:
            with urllib.request.urlopen(req, timeout=tmo) as r:
                raw = json.loads(r.read().decode("utf-8", "ignore"))
            d.update({"last": time.time(), "strikes": 0, "until": 0.0})
            _save_rate(d)
            ch = (raw.get("choices") or [{}])[0]
            msg = ch.get("message") or {}
            content = (msg.get("content") or "").strip()
            reason = (msg.get("reasoning_content") or "").strip()
            return {
                "ok": True,
                "text": content or reason,
                "from_reasoning": (not content) and bool(reason),
                "finish": ch.get("finish_reason"),
                "tokens": (raw.get("usage") or {}).get("total_tokens"),
                "wait": round(waited_total, 1),
                "error": None,
            }
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "ignore")[:300]
            if e.code == 429:
                # 实测 30 秒恢复；指数退避
                back = 30.0 * (2 ** attempt)
                d.update({"strikes": d.get("strikes", 0) + 1,
                          "until": time.time() + back, "last": time.time()})
                _save_rate(d)
                waited_total += back
                if attempt == retries - 1:
                    return {"ok": False, "text": "", "from_reasoning": False,
                            "finish": None, "tokens": None,
                            "wait": round(waited_total, 1),
                            "error": "429 免费额度用尽（实测约 5 次/30 秒）：" + raw}
                continue
            return {"ok": False, "text": "", "from_reasoning": False, "finish": None,
                    "tokens": None, "wait": round(waited_total, 1),
                    "error": "HTTP %d: %s" % (e.code, raw)}
        except Exception as e:                                    # noqa: BLE001
            return {"ok": False, "text": "", "from_reasoning": False, "finish": None,
                    "tokens": None, "wait": round(waited_total, 1), "error": str(e)}
    return {"ok": False, "text": "", "from_reasoning": False, "finish": None,
            "tokens": None, "wait": round(waited_total, 1), "error": "重试耗尽"}


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "说一句话：我在"
    r = chat(q)
    print(json.dumps(r, ensure_ascii=False, indent=1))
