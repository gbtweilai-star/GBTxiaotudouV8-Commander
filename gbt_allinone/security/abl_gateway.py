# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 黑客大脑 LLM 网关（abliteration.ai 接入层）。

Owner 提供（2026-09-11）：abliteration.ai（无限制模型服务）作为黑客大脑的推理引擎。
密钥纪律：只从 .env 读 ABLITERATION_API_KEY，不进源码不进日志（GBT_LLM_API_KEY 同模式）。

已实测（真实验证，非假接线）：
  - 端点：https://api.abliteration.ai/v1/chat/completions（OpenAI 兼容）
  - 鉴权：Authorization: Bearer <key>（x-api-key 亦可用）
  - 模型：abliterated-model（推理模型：思维在 message.reasoning，正文在 message.content）
  - 特性：max_tokens 需给足（≥1500），否则 reasoning 耗尽预算导致 content 为空
  - 回复提取：content 为空但 reasoning 有值时，如实返回 reasoning 并标注（不伪造正文）
"""
import json
import os
import time
import urllib.request
import urllib.error

_BASE = "https://api.abliteration.ai/v1"
_DEFAULT_MODEL = "abliterated-model-large-v2"  # 实测最快最省（54 tokens vs 157）


def _key():
    k = os.environ.get("ABLITERATION_API_KEY", "")
    if not k:
        # 尝试从 .env 读（与 ALCHEMY_RPC_URL 同一模式）
        try:
            from pathlib import Path
            env = Path(__file__).resolve().parent.parent / ".env"
            if env.exists():
                for line in env.read_text(encoding="utf-8").splitlines():
                    if line.startswith("ABLITERATION_API_KEY="):
                        k = line.split("=", 1)[1].strip()
                        break
        except Exception:  # noqa: BLE001
            # 合理兜底：读 .env 失败 → k 保持空串 → configured() 如实返回 False。
            # 静默是安全的：失败结果对调用方可见（未配置），不掩盖、不伪造。
            pass
    return k


def configured() -> bool:
    return bool(_key())


def models(timeout=15):
    """列出可用模型。"""
    k = _key()
    if not k:
        return {"ok": False, "error": "未配置 ABLITERATION_API_KEY"}
    req = urllib.request.Request(f"{_BASE}/models",
                                 headers={"x-api-key": k})  # /models 端点只认 x-api-key
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return {"ok": True, "models": [m.get("id") for m in data.get("data", [])]}


def chat(prompt, system="", model=None, max_tokens=2000, temperature=0.7, timeout=180):
    """推理对话。

    推理模型特性处理：
      - content 有值 → 正常返回
      - content 空但 reasoning 有值 → 返回 reasoning 并标注 reasoning_only=True（如实，不伪造正文）
      - 两者皆空且 finish_reason=length → 提示加大 max_tokens（而不是返回假空成功）
    """
    k = _key()
    if not k:
        return {"ok": False, "error": "未配置 ABLITERATION_API_KEY",
                "hint": "在 gbt_allinone/.env 写入 ABLITERATION_API_KEY=ak_..."}
    body = {
        "model": model or _DEFAULT_MODEL,
        "messages": ([{"role": "system", "content": system}] if system else [])
                   + [{"role": "user", "content": prompt[:8000]}],
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
    }
    # R120：出站统一走 net_guard（SSRF/端口/体积守门）+ 应用层 AI 审计。
    # 此前这段直连 urllib.request.urlopen，两道门都没过。
    from . import net_guard as _ng
    from . import ai_audit as _audit
    url = f"{_BASE}/chat/completions"
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {k}"}
    t0 = time.time()
    ctx = _audit.begin("abliteration", url, model=body["model"],
                       request_body=body, headers=headers)
    try:
        response = _ng.safe_request_json(
            url, method="POST", headers=headers,
            body=json.dumps(body).encode("utf-8"), timeout=timeout)
    except Exception as e:  # noqa: BLE001
        _audit.finish(ctx, ok=False, error=e)
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}
    if response["status"] >= 400:
        _audit.finish(ctx, status=response["status"], ok=False,
                      response_text=response.get("text"))
        return {"ok": False,
                "error": f"HTTP {response['status']}: "
                         f"{str(response.get('text') or '')[:200]}"}
    data = response.get("json")
    if not isinstance(data, dict):
        _audit.finish(ctx, status=response["status"], ok=False,
                      response_text=response.get("text"))
        return {"ok": False, "error": "abliteration 返回非 JSON 对象"}
    _audit.finish(ctx, status=response["status"], ok=True, response=data)

    msg = (data.get("choices") or [{}])[0].get("message", {}) or {}
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning") or ""
    finish = (data.get("choices") or [{}])[0].get("finish_reason", "")
    usage = data.get("usage", {})

    if not content and reasoning:
        return {"ok": True, "reply": "", "reasoning": reasoning,
                "reasoning_only": True,
                "note": "推理模型把预算耗在思维链上，正文为空——加大 max_tokens 可获得正文",
                "finish_reason": finish, "elapsed_ms": round((time.time() - t0) * 1000, 1)}
    if not content and finish == "length":
        return {"ok": False, "error": "max_tokens 不足以完成推理+正文",
                "hint": f"当前 {max_tokens}，推理模型建议 ≥1500",
                "completion_tokens": usage.get("completion_tokens")}
    return {"ok": True, "reply": content,
            "reasoning": reasoning[:500] if reasoning else None,
            "finish_reason": finish,
            "model": data.get("model", body["model"]),
            "usage": {"completion": usage.get("completion_tokens"),
                      "prompt": usage.get("prompt_tokens")},
            "elapsed_ms": round((time.time() - t0) * 1000, 1)}
