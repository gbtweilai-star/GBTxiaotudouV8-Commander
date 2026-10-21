# -*- coding: utf-8 -*-
"""对一个 OpenAI 兼容端点说话，并把它的回答**按目录校一遍**。

这一层的价值不在"能发请求"（urllib 三行就够），而在两条纪律：

1. **模型给的名字必须能在目录里查到** —— 查不到就是幻觉，当场判 `ok=false`，
   绝不放它进下一步（本仓叫这条「判据不认口头结论」）；
2. **回执要带真读数** —— 耗时、token 数、模型名、端点，都写进回执；
   失败时把上游原话带回来，不许只说"失败了"。

用法：

    from gbt_commander import Catalog, CommanderClient

    cat = Catalog.load()
    cli = CommanderClient(base_url="http://127.0.0.1:8000/v1", model="gbt-v8")
    rec = cli.route("我要把一份 Markdown 变成 PPT，该调哪个能力位？", cat)
    rec["ok"], rec["capability"], rec["reason"]
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .catalog import Catalog

__all__ = ["CommanderClient", "PROMPT_TEMPLATE"]

# 提示词刻意写死形状：一句话问题 → 一个能力位名 + 参数 + 一句理由。
# 之所以不让模型自由发挥，是因为下游要拿这个名字去查目录、去过门。
PROMPT_TEMPLATE = """你是 GBT小土豆V8（总指挥）。任务：把下面这句话落到**一位**能力位上。

可用能力位（格式：域名/能力位名）：
{catalog}

要求：
1. 只能从上面列出的能力位里选，**不许编造新名字**；
2. 只回一个 JSON 对象，不要任何解释性文字，形状固定为：
   {{"capability": "<能力位名>", "args": {{...}}, "reason": "<不超过 40 字的理由>"}}
3. 这件事需要人授权的（会改状态/出网/花钱），照常给出名字，reason 里写明"需授权"。

用户的话：{question}
"""


class CommanderClient:
    """最小 OpenAI 兼容客户端（只用标准库）。"""

    def __init__(self, base_url: str = "http://127.0.0.1:8000/v1",
                 model: str = "gbt-v8", api_key: str = "EMPTY",
                 timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = float(timeout)

    # ---------- 底层 ----------
    def _post(self, path: str, body: dict) -> tuple[int, bytes, float]:
        url = self.base_url + path
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key,
            "User-Agent": "gbt-commander/1.0",
        })
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.read(), time.perf_counter() - t0
        except urllib.error.HTTPError as exc:
            return exc.code, (exc.read() or b""), time.perf_counter() - t0
        except Exception as exc:                                  # noqa: BLE001
            return -1, ("%s: %s" % (type(exc).__name__, exc)).encode("utf-8"), time.perf_counter() - t0

    def chat(self, messages: list[dict], max_tokens: int = 512,
             temperature: float = 0.0) -> dict:
        """一问一答，回执带 http / 耗时 / usage / 原文；失败也把上游原话带回。"""
        body = {"model": self.model, "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature}
        status, raw, elapsed = self._post("/chat/completions", body)
        text = raw.decode("utf-8", "replace")
        out = {"ok": False, "http": status, "elapsed_s": round(elapsed, 2),
               "endpoint": self.base_url + "/chat/completions", "model": self.model}
        if status != 200:
            out["error"] = "上游 http=%s：%s" % (status, text[:300])
            return out
        try:
            payload = json.loads(text)
        except Exception:                                          # noqa: BLE001
            out["error"] = "200 但载荷不是 JSON：%s" % text[:200]
            return out
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        out.update({
            "ok": True,
            "text": (message.get("content") or "").strip(),
            "usage": payload.get("usage") or {},
            "finish_reason": choice.get("finish_reason"),
        })
        return out

    # ---------- 有判据的那一层 ----------
    def route(self, question: str, catalog: Catalog, max_tokens: int = 512) -> dict:
        """把一句话落到能力位，并用目录校验模型给的名字。

        回执字段：
            ok           决策是否可用（名字查得到 且 JSON 形状对）
            capability   能力位名（ok=false 时是模型原话，便于定位）
            args/reason  模型给的参数与理由
            verified     名字是否在目录里
            call         模型那一发的原始回执（http/耗时/usage）
            risk         这一位是不是要过门（writes/需票）—— 给调用方决定要不要请人授权
        """
        listing = "\n".join("%s/%s" % (c.domain, c.name) for c in catalog)
        prompt = PROMPT_TEMPLATE.format(catalog=listing, question=question)
        call = self.chat([{"role": "user", "content": prompt}],
                         max_tokens=max_tokens, temperature=0.0)
        out = {"ok": False, "question": question, "call": call}
        if not call.get("ok"):
            out["error"] = call.get("error")
            return out

        text = call.get("text") or ""
        decision = _parse_json_object(text)
        if decision is None:
            out["error"] = "模型没按形状回 JSON：%s" % text[:200]
            out["raw"] = text
            return out

        name = str(decision.get("capability") or "").strip()
        cap = catalog.get(name)
        out.update({
            "capability": name,
            "args": decision.get("args") or {},
            "reason": str(decision.get("reason") or "").strip(),
            "verified": cap is not None,
        })
        if cap is None:
            out["error"] = "模型给的能力位在目录里查不到（幻觉）：%s" % (name or "<空>")
            return out
        out.update({
            "ok": True,
            "domain": cap.domain,
            "readonly": cap.readonly,
            "scopes_static": list(cap.scopes_static),
            "risk": "read" if (cap.readonly and not cap.needs_ticket) else "needs_gate",
            "one_liner": cap.one_liner,
        })
        return out


def _parse_json_object(text: str) -> dict | None:
    """从模型回话里抠出第一个 JSON 对象（允许它前后带 ``` 或客套话）。"""
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
                    chunk = text[start:i + 1]
                    try:
                        obj = json.loads(chunk)
                    except Exception:                              # noqa: BLE001
                        break
                    return obj if isinstance(obj, dict) else None
        start = text.find("{", start + 1)
    return None
