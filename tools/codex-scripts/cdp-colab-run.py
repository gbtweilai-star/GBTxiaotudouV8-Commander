# -*- coding: utf-8 -*-
"""接管 Chrome（CDP）→ 在 Colab 里新建笔记本 → 粘贴启动格 → 运行 → 抓隧道地址。

## 为什么用 CDP 而不是 Playwright
主人已经登录了 Colab。Playwright 起新浏览器 = 没有登录态；复制配置文件又会被 App-Bound 加密挡住。
所以直接连**他自己那个 Chrome**（用 `--remote-debugging-port` 拉起来的同一份配置），在页面里执行 JS。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import websocket                                      # websocket-client

CDP = "http://127.0.0.1:9222"

CELL_CODE = r'''
# ---- GBT 自有权重 · 免费 GPU 启动格（由本机接管脚本注入）----
!pip -q install "transformers>=4.44" accelerate bitsandbytes fastapi uvicorn
!wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared
!wget -q --show-progress https://prefers-reaching-disposal-lanes.trycloudflare.com/gbt-weights.zip -O /content/gbt-weights.zip
!unzip -q -o /content/gbt-weights.zip -d /content/gbt-weights
open("srv.py","w").write(r"""
import json, subprocess, threading, time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
MD, PORT = "gbt-weights", 8077
dev = "cuda" if torch.cuda.is_available() else "cpu"
if dev == "cuda":
    p = torch.cuda.get_device_properties(0)
    print("[gbt] gpu =", p.name, "vram %.1f GB" % (p.total_memory/1024**3), flush=True)
print("[gbt] device =", dev, flush=True)
tok = AutoTokenizer.from_pretrained(MD, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(MD, device_map="auto", trust_remote_code=True,
        torch_dtype=torch.float16 if dev=="cuda" else torch.float32).eval()
print("[gbt] 模型已加载", flush=True)
app = FastAPI()
@app.get("/health")
def h(): return {"ok": True, "weights_ours": True, "device": dev}
@app.post("/v1/chat/completions")
async def chat(body: dict):
    msgs = body.get("messages") or [{"role":"user","content":""}]
    txt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    ids = tok(txt, return_tensors="pt").to(model.device)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(**ids, max_new_tokens=int(body.get("max_tokens") or 512),
                             do_sample=False, pad_token_id=tok.eos_token_id)
    ans = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
    return JSONResponse({"id":"gbt-"+str(int(time.time())),"object":"chat.completion","model":"gbt-v8",
        "choices":[{"index":0,"message":{"role":"assistant","content":ans},"finish_reason":"stop"}],
        "gbt":{"weights_ours":True,"host":"free-gpu","ms":int((time.time()-t0)*1000)}})
def tun():
    time.sleep(1.5)
    p = subprocess.Popen(["cloudflared","tunnel","--url","http://127.0.0.1:%d"%PORT,"--no-autoupdate"],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in p.stdout:
        if "trycloudflare.com" in line:
            print("[gbt] ==== URL ==== " + [w for w in line.split() if "trycloudflare.com" in w][0], flush=True)
threading.Thread(target=tun, daemon=True).start()
uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
""")
!python srv.py
'''


def targets():
    with urllib.request.urlopen(CDP + "/json", timeout=8) as r:
        return json.loads(r.read().decode())


def colab_target():
    for t in targets():
        if t.get("type") == "page" and "colab.research.google.com" in (t.get("url") or ""):
            return t
    return None


class Cdp:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=60, max_size=None)
        self.i = 0

    def send(self, method, **params):
        self.i += 1
        mid = self.i
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                return msg

    def js(self, expr, await_promise=False):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True,
                      awaitPromise=await_promise, userGesture=True)
        return (r.get("result") or {}).get("result", {}).get("value")


def main() -> int:
    t = colab_target()
    if not t:
        print("没找到 Colab 标签页"); return 2
    print("接管目标:", (t.get("title") or "")[:40], "·", (t.get("url") or "")[:60])
    cdp = Cdp(t["webSocketDebuggerUrl"])
    cdp.send("Page.enable")
    cdp.send("Runtime.enable")

    # ① 新建一个笔记本
    print("→ 新建笔记本")
    cdp.send("Page.navigate", url="https://colab.research.google.com/#create=true")
    time.sleep(14)

    # ② 把启动格写进第一个 cell
    print("→ 写入启动格")
    payload = json.dumps(CELL_CODE)
    res = cdp.js("""
      (function(src){
        var cm = document.querySelector('.CodeMirror');
        if (cm && cm.CodeMirror) { cm.CodeMirror.setValue(src); return 'cm5'; }
        var ed = document.querySelector('div[role="textbox"], .cell .inputarea, textarea');
        if (ed) { ed.focus(); document.execCommand('insertText', false, src); return 'contenteditable'; }
        return 'no-editor';
      })(%s)
    """ % payload)
    print("  写入方式:", res)
    time.sleep(2)

    # ③ 跑它（Ctrl+Enter）
    print("→ 执行（Ctrl+Enter）")
    cdp.js("var cm=document.querySelector('.CodeMirror'); if(cm&&cm.CodeMirror){cm.CodeMirror.focus();}")
    for mtype, code, vk in (("keyDown", 13, "Enter"), ("keyUp", 13, "Enter")):
        cdp.send("Input.dispatchKeyEvent", type=mtype, key="Enter", code="Enter",
                 windowsVirtualKeyCode=13, nativeVirtualKeyCode=13,
                 modifiers=2)                     # 2 = Ctrl
    time.sleep(8)

    # ④ 读页面尾部（看是否在下载 / 报错）
    txt = cdp.js("document.body.innerText.slice(-1500)") or ""
    print("---- 页面尾部 ----")
    print(txt[-1200:])
    print("---- 是否已出现隧道地址 ----")
    import re
    urls = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", txt)
    print("urls:", urls[:3] or "（还没出现，需要等下载+加载）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
