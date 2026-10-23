# -*- coding: utf-8 -*-
"""独立复验代理 thinking-mode 修复：跑出真正的帧序，看上游还拒不拒。"""
import json
import urllib.request
import urllib.error

URL = "http://127.0.0.1:4446/responses"
TOOLS = [{"type": "function", "function": {"name": "exec", "description": "Run a shell command.",
          "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}]


def call(payload):
    req = urllib.request.Request(URL, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=300)
        return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


USER = {"type": "message", "role": "user",
        "content": [{"type": "input_text", "text": "Use the exec tool to run: echo PROXY-TOOL-OK . Do not answer in text."}]}

print("== T1 首轮：带工具声明 ==")
st, body = call({"model": "deepseek-flash", "stream": False, "input": [USER], "tools": TOOLS})
print("   HTTP", st)
if isinstance(body, str):
    print("  ", body[:400])
    raise SystemExit(1)
out = body.get("output", [])
print("   output items:", [(o.get("type"), o.get("name") or o.get("status")) for o in out])
fc = next((o for o in out if o.get("type") == "function_call"), None)
rs = next((o for o in out if o.get("type") == "reasoning"), None)
print("   reasoning:", ("encrypted %d B" % len(rs.get("encrypted_content") or "")) if rs else "无")
print("   function_call:", (fc.get("name"), (fc.get("arguments") or "")[:90]) if fc else "无")
if not fc:
    raise SystemExit(2)

print()
print("== T2 回声复现（曾经 400 的帧序：reasoning + function_call + output）==")
inp = [USER]
if rs:
    inp.append(rs)
inp.append(fc)
inp.append({"type": "function_call_output", "call_id": fc.get("call_id"), "output": "PROXY-TOOL-OK"})
inp.append({"type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "Reply with the exact tool output only."}]})
st2, body2 = call({"model": "deepseek-flash", "stream": False, "input": inp, "tools": TOOLS})
print("   HTTP", st2)
print("  ", (json.dumps(body2, ensure_ascii=False) if not isinstance(body2, str) else body2)[:500])
print()
print("VERDICT:", "PASS —— 上游不拒、工具链路可用" if st2 == 200 else "FAIL —— 上游仍拒绝")
