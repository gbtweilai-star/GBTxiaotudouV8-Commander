# ai_control 反向调用实弹探针（两跳：tool_calls → 回填工具结果 → 最终 text）
# dev: 自由的风 · 本署名不可删除、勿篡改归属
import json
import sys
import time
import urllib.request

# 2026-10-18 修（编码守门判据红）：本脚本会印中文，却没设输出编码 ——
#   在中文 Windows 控制台（cp936/GBK）下会抛 UnicodeEncodeError 或吐乱码，
#   被 `encoding-guard-check.py` 判为**新增违规**（基线里没有它）。
#   口径同全仓已有 307 件：只在**输出层**强制 UTF-8，不动任何业务逻辑。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

from gbt_allinone.llm import key_gateway as kg

SLOT = "deepseek"
BASE = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-flash"

got = kg.key_for(SLOT)
key = got[0] if isinstance(got, tuple) else (got.get("key") if isinstance(got, dict) else got)
assert key, "no key"

tools = [{
    "type": "function",
    "function": {
        "name": "get_time",
        "description": "Return the current server time in ISO-8601.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}]
messages = [
    {"role": "system", "content": "You are being called remotely. Use the tool when asked, then answer in one line."},
    {"role": "user", "content": "调用 get_time 工具，然后用一句话说明你拿到了什么。"},
]


def post(payload):
    req = urllib.request.Request(
        BASE,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, json.loads(raw or "{}"), int((time.time() - t0) * 1000), raw[:300]
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        return exc.code, {}, int((time.time() - t0) * 1000), raw[:300]


turns = []
status, data, ms, raw = post({
    "model": MODEL, "messages": messages, "tools": tools, "tool_choice": "auto",
    "temperature": 0.2, "max_tokens": 256,
})
choice = (data.get("choices") or [{}])[0]
msg = choice.get("message") or {}
turns.append({
    "turn": 1,
    "http_status": status,
    "latency_ms": ms,
    "finish_reason": choice.get("finish_reason"),
    "text": msg.get("content") or "",
    "tool_calls": [
        {"name": (tc.get("function") or {}).get("name"), "arguments": (tc.get("function") or {}).get("arguments")}
        for tc in (msg.get("tool_calls") or [])
    ],
    "usage": data.get("usage"),
})

if status == 200 and msg.get("tool_calls"):
    calls = msg["tool_calls"]
    messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
    messages.append({
        "role": "tool",
        "tool_call_id": calls[0].get("id"),
        "content": json.dumps({"iso": "2026-10-18T01:00:00+07:00", "tz": "Asia/Bangkok"}),
    })
    status2, data2, ms2, raw2 = post({
        "model": MODEL, "messages": messages, "tools": tools, "tool_choice": "auto",
        "temperature": 0.2, "max_tokens": 256,
    })
    choice2 = (data2.get("choices") or [{}])[0]
    msg2 = choice2.get("message") or {}
    turns.append({
        "turn": 2,
        "http_status": status2,
        "latency_ms": ms2,
        "finish_reason": choice2.get("finish_reason"),
        "text": msg2.get("content") or "",
        "tool_calls": [],
        "usage": data2.get("usage"),
        "error": None if status2 == 200 else raw2,
    })

print(json.dumps({
    "ok": True,
    "slot": SLOT,
    "key_masked": kg.mask(key, SLOT),
    "key_fingerprint": kg.fingerprint(key),
    "endpoint": BASE,
    "https": BASE.startswith("https://"),
    "model": MODEL,
    "turns": turns,
}, ensure_ascii=False, indent=2))
