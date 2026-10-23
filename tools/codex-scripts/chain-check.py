# -*- coding: utf-8 -*-
"""整链路体检：本地框架 → （云插件 | 直连端点）→ 现役权重（v83）。

四段各真跑一次，**每段都要能指到读数**：
  ① 选路：显式点名 `potato`（原生车道）⇒ PROVIDER/BASE_URL/MODEL 正确、钥匙来自保险箱
  ② 本地 ask()：走框架真实内部口 `unified.ask` ⇒ 回执 provider/model 与回答
  ③ 云插件：`/v1/models` 的 weights_ours_configured + 一次真问答（过令牌门）
  ④ 直连端点：一次真推理，回包 `model` 字段必须等于现役 served id

判据口径（2026-10-21 定，改它要留痕）：
  · ①②③④ 全真跑过且各有读数 ⇒ PASS；任何一段没读到 ⇒ FAIL（不许默认绿）
  · `drift=true`（落到 potato 而 unified 的"期望 provider"是 agnes）**只作提示**，
    不判红 —— 它说明"原生车道在跑、不是托管那条"，恰恰是这本件要证的事。
用法：
  py -3.14 -X utf8 tools/codex-scripts/chain-check.py               # 原生车道直连端点
  py -3.14 -X utf8 tools/codex-scripts/chain-check.py --via-plugin  # 原生车道走云插件
  py -3.14 -X utf8 tools/codex-scripts/chain-check.py --no-plain    # 跳过 ③④（只验本地段）
"""
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = "https://gbt-potato-cloud-10.paysssk.workers.dev/v1"
SERVED = json.loads((ROOT / "state/weights/ACTIVE.json").read_text(encoding="utf-8"))["active_artifact"]
UA = "gbt/1.0"


def http(method, url, body=None, key="", to=300):
    data = json.dumps(body).encode() if body is not None else None
    h = {"User-Agent": UA}
    if data:
        h["Content-Type"] = "application/json"
    if key:
        h["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=to) as r:
            return r.status, json.loads(r.read() or b"{}"), round(time.time() - t0, 1)
    except urllib.error.HTTPError as e:
        return e.code, {"raw": e.read()[:300].decode("utf-8", "replace")}, round(time.time() - t0, 1)
    except Exception as e:                                   # noqa: BLE001
        return "ERR", {"err": "%s: %s" % (type(e).__name__, str(e)[:140])}, round(time.time() - t0, 1)


def cred(name):
    p = pathlib.Path.home() / ".dsh" / ".credentials.yaml"
    if not p.is_file():
        return ""
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.strip().startswith(name + ":"):
            return ln.split(":", 1)[1].strip().strip("\"'")
    return ""


async_def = None
results = []
via_plugin = "--via-plugin" in sys.argv

# ① 选路 + ② 本地 ask（子进程里跑，确保 env 在 import 前生效）
env = dict(os.environ)
env["GBT_LLM_PROVIDER"] = "potato"
env["PYTHONIOENCODING"] = "utf-8"
if via_plugin:
    env["GBT_POTATO_BASE_URL"] = PLUGIN
coder = (
    "import sys,json,time;sys.path.insert(0,%r)\n"
    "from gbt_allinone.llm import cloud_llm as C\n"
    "from gbt_allinone.llm import unified as U\n"
    "print('ROUTE', json.dumps({'provider':C.PROVIDER,'url':C.BASE_URL,'model':C.MODEL,"
    "'key_len':len(C.API_KEY)}, ensure_ascii=False))\n"
    "t0=time.time()\n"
    "# 走框架真实内部口（unified.ask ⇒ bridge ⇒ cloud_llm），并**显式点名 potato**\n"
    "r=U.ask('请用一句话介绍你自己。', provider='potato', max_tokens=200)\n"
    "print('ASK', json.dumps({'elapsed':round(time.time()-t0,1),'ok':bool(r.get('ok')),"
    "'provider':r.get('provider'),'model':r.get('model'),'drift':r.get('drift'),"
    "'reply':str(r.get('reply') or r.get('error') or '')[:200]}, ensure_ascii=False))\n"
) % str(ROOT)
t0 = time.time()
proc = subprocess.run([sys.executable, "-X", "utf8", "-c", coder], capture_output=True,
                      text=True, encoding="utf-8", errors="replace", env=env, timeout=900)
print("== ① ② 本地框架（unified.ask · provider=potato · base=%s）=="
      % ("云插件" if via_plugin else "直连端点"))
route = {}
ask = {}
for ln in (proc.stdout or "").splitlines():
    print("  " + ln[:320])
    if ln.startswith("ROUTE "):
        try:
            route = json.loads(ln[6:])
        except Exception:                                             # noqa: BLE001
            route = {}
    if ln.startswith("ASK "):
        try:
            ask = json.loads(ln[4:])
        except Exception:                                             # noqa: BLE001
            ask = {}
if proc.returncode != 0:
    print("  stderr:", (proc.stderr or "")[-400:])
# 🔴 2026-10-21 修我自己这条判据的假绿：上一版拿 stdout 里出现 provider 就算通过，
#    而子进程其实抛了 AttributeError（cloud_llm 没有 ask，入口是 unified.ask）。
#    现在三条都要真：选路落到 potato · 回执 ok · 有非空回答。
ok12 = (route.get("provider") == "potato" and bool(ask.get("ok"))
        and bool((ask.get("reply") or "").strip()))
results.append(("①② 选路 + 真问一句", ok12,
                "provider=%s model=%s %ss reply=%r"
                % (ask.get("provider"), ask.get("model"), ask.get("elapsed"),
                   (ask.get("reply") or "")[:40])))

# ③ 云插件（令牌门 + 接线）
tok = cred("GBT_ENDPOINT_TOKEN") or cred("GW_AUTH")
st, d, el = http("GET", PLUGIN.rstrip("/") + "/models")
w = ((d or {}).get("gbt") or {}).get("llm_endpoint_wired") or {}
ours = bool(((d or {}).get("gbt") or {}).get("weights_ours_configured"))
st2, d2, el2 = http("POST", PLUGIN.rstrip("/") + "/chat/completions",
                    {"model": "gbt-potato-v8", "messages": [{"role": "user", "content": "只回两个字：收到"}],
                     "max_tokens": 16, "temperature": 0, "stream": False}, tok)
ans = ""
if isinstance(d2, dict):
    ans = (((d2.get("choices") or [{}])[0].get("message") or {}).get("content") or "")[:40]
print("== ③ 云插件 %s ==" % PLUGIN)
print("  /models HTTP %s %ss wired=%s weights_ours_configured=%s"
      % (st, el, {k: bool(v) for k, v in w.items()}, ours))
print("  /chat   HTTP %s %ss 答=%r raw=%s" % (st2, el2, ans, str(d2)[:160] if st2 != 200 else ""))
results.append(("③ 云插件问答", st2 == 200 and bool(ans), "%s %ss" % (st2, el2)))

# ④ 直连端点
url = os.environ.get("GBT_POTATO_BASE_URL", "").rstrip("/")
if not url or "runpod.ai" not in url:
    url = "https://api.runpod.ai/v2/qnnqf9w8xcefj8/openai/v1"
rkey = (ROOT / ".scratch/.runpod_key").read_text(encoding="utf-8").strip()
st3, d3, el3 = http("POST", url + "/chat/completions",
                    {"model": SERVED, "messages": [{"role": "user", "content": "只回两个字：收到"}],
                     "max_tokens": 16, "temperature": 0, "stream": False}, rkey)
echo = (d3.get("model") if isinstance(d3, dict) else None)
print("== ④ 直连端点 ==")
print("  HTTP %s %ss 回包 model=%r（现役 %r）" % (st3, el3, echo, SERVED))
results.append(("④ 直连端点", st3 == 200 and echo == SERVED, "%s %ss" % (st3, el3)))

# ⑤ 流式（云插件 stream=true）：真收增量才算通 —— 只看 content-type 会被"配了但没流"骗过
schunks, spieces = 0, []
try:
    body = {"model": "gbt-potato-v8", "messages": [{"role": "user", "content": "数到五，只输出数字。"}],
            "max_tokens": 40, "temperature": 0, "stream": True}
    req = urllib.request.Request(PLUGIN.rstrip("/") + "/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": UA,
                                          "Authorization": "Bearer " + tok}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        ctype = r.headers.get("content-type") or ""
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            schunks += 1
            try:
                one = json.loads(data)
            except Exception:                                     # noqa: BLE001
                continue
            piece = (((one.get("choices") or [{}])[0].get("delta") or {}).get("content") or "")
            if piece:
                spieces.append(piece)
            if schunks >= 8:
                break
    sest = "200"
except urllib.error.HTTPError as e:
    ctype, sest = str(e.code), str(e.code)
    print("  上游原话:", e.read()[:200].decode("utf-8", "replace"))
except Exception as e:                                            # noqa: BLE001
    ctype, sest = "%s: %s" % (type(e).__name__, str(e)[:80]), "ERR"
print("== ⑤ 流式（云插件 stream=true）==")
print("  HTTP %s · content-type=%s · 事件 %d 个 · 拼接=%r" % (sest, ctype, schunks, "".join(spieces)[:40]))
results.append(("⑤ 流式真收增量", sest == "200" and schunks > 0 and bool(spieces),
                "事件 %d · %r" % (schunks, "".join(spieces)[:20])))

print("== 汇总 ==")
allok = True
for name, ok, extra in results:
    allok = allok and ok
    print("  %s %s %s" % ("✓" if ok else "✗", name, extra))
print("CHAIN_CHECK " + ("PASS" if allok else "FAIL"))
raise SystemExit(0 if allok else 1)
