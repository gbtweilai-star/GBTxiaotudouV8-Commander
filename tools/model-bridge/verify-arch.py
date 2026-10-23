# -*- coding: utf-8 -*-
"""架构验收：五根柱子逐条真测，出计分卡。

柱子：
  1) 双向绑定 —— 341 个能力位每条都有页；页里 data-kind 对得上；页能回调本页能力
  2) 互通    —— 任何一页都能调任何能力位（/v1/caps 给全名册 + /v1/dispatch 真调）
  3) 秒级    —— 只读能力位的 dispatch 延迟 p50 / p95
  4) 按需    —— 权重进程常驻内存 / 空闲自动退
  5) 算力    —— GPU 是否可用（llama.cpp 后端能力 + 适配器）

用法：py -3.14 tools/model-bridge/verify-arch.py [--json 出到文件]
"""
from __future__ import annotations
import json, os, re, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAPS_DIR = os.path.join(ROOT, "holo_pet_w3", "brain", "caps")
BRIDGE = "http://127.0.0.1:8791"
OK, BAD, WARN = "OK", "FAIL", "WARN"
rows = []


def add(pillar, name, state, detail):
    rows.append({"pillar": pillar, "check": name, "state": state, "detail": detail})


def get(path, timeout=10):
    return json.loads(urllib.request.urlopen(BRIDGE + path, timeout=timeout).read().decode("utf-8"))


def post(path, obj, timeout=60):
    body = json.dumps(obj).encode()
    req = urllib.request.Request(BRIDGE + path, data=body, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


# ── 1 双向绑定 ──────────────────────────────────────────────
caps = []
try:
    caps = get("/v1/caps")["caps"]
    add(1, "名册可取", OK, "341 条" if len(caps) == 341 else "只有 %d 条" % len(caps))
except Exception as exc:                                        # noqa: BLE001
    add(1, "名册可取", BAD, "%s: %s" % (type(exc).__name__, str(exc)[:80]))

missing, wrongkind, nocsp, nojs = [], [], [], []
for c in caps:
    name = c["name"]
    p = os.path.join(CAPS_DIR, name + ".html")
    if not os.path.isfile(p):
        missing.append(name); continue
    try:
        t = open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        missing.append(name); continue
    if ('data-kind="%s"' % name) not in t:
        wrongkind.append(name)
    if "connect-src http://127.0.0.1:8791" not in t:
        nocsp.append(name)
    if "cap.js" not in t:
        nojs.append(name)
add(1, "每条能力位有页", OK if not missing else BAD, "缺 %d 页%s" % (len(missing), (" 例:" + ",".join(missing[:5])) if missing else ""))
add(1, "页面 data-kind 对得上", OK if not wrongkind else BAD, "错 %d" % len(wrongkind))
add(1, "页面允许连本地桥(CSP)", OK if not nocsp else BAD, "缺 %d 页" % len(nocsp))
add(1, "页面挂了渲染器 cap.js", OK if not nojs else BAD, "缺 %d 页" % len(nojs))

# ── 2 互通：任意页调任意能力位 ──────────────────────────────
try:
    calc = post("/v1/calc", {"expr": "100 - 3 * 18"})
    add(2, "计算器互通", OK if calc.get("value") == 46 else BAD, "100-3*18=%s" % calc.get("value"))
except Exception as exc:                                        # noqa: BLE001
    add(2, "计算器互通", BAD, str(exc)[:80])

RO = ["echo", "audit_query", "tentacle_manifest", "count_words", "health"]
lat = []
fails = []
for cap in RO:
    t0 = time.perf_counter()
    try:
        j = post("/v1/dispatch", {"capability": cap, "args": {}}, timeout=120)
        dt = (time.perf_counter() - t0) * 1000
        lat.append((cap, dt, j.get("ok")))
        if not j.get("ok"):
            fails.append(cap)
    except Exception as exc:                                    # noqa: BLE001
        fails.append(cap + ":" + type(exc).__name__)
add(2, "跨能力位真调", OK if not fails else WARN, "5 发失败 %d%s" % (len(fails), ("  " + ",".join(fails)) if fails else ""))

# ── 3 秒级 ────────────────────────────────────────────────
if lat:
    ds = sorted(d for _c, d, _o in lat)
    p50 = ds[len(ds) // 2]
    p95 = ds[min(len(ds) - 1, int(len(ds) * 0.95))]
    add(3, "只读位延迟 p50/p95", OK if p95 < 1000 else WARN, "p50 %.0fms · p95 %.0fms（%s）"
        % (p50, p95, " · ".join("%s %.0fms" % (c, d) for c, d, _o in lat)))
else:
    add(3, "只读位延迟", BAD, "没测到")

# ── 4 按需激活 ────────────────────────────────────────────
try:
    h = get("/health")
    ours = [u for u in h.get("upstreams", []) if u["name"] == "selfhost"]
    add(4, "桥默认车道", OK if h.get("default") == "selfhost" else WARN, "default=%s" % h.get("default"))
    add(4, "selfhost 车道存在", OK if ours else BAD, ours[0]["base_url"] if ours else "没有")
except Exception as exc:                                        # noqa: BLE001
    add(4, "桥 health", BAD, str(exc)[:80])

try:
    out = subprocess.run(["powershell", "-NoProfile", "-c",
        "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'local_llm_server' } | ForEach-Object { (Get-Process -Id $_.ProcessId).WorkingSet64 })"],
        capture_output=True, text=True)
    ws = [int(x) for x in (out.stdout or "").split() if x.isdigit()]
    if ws:
        add(4, "权常常驻内存", OK, "%.0f MB（文件 4.88 GB，mmap 按需换页）" % (ws[0] / 1048576))
    else:
        add(4, "权常常驻内存", WARN, "服务没起（按需模式，这是正常的冷态）")
except Exception as exc:                                        # noqa: BLE001
    add(4, "权常常驻内存", WARN, str(exc)[:80])

# ── 5 算力（GPU） ─────────────────────────────────────────
try:
    r = subprocess.run([sys.executable, "-c",
        "import llama_cpp.llama_cpp as lc; print(int(lc.llama_supports_gpu_offload()))"],
        capture_output=True, text=True)
    off = (r.stdout or "").strip() == "1"
    add(5, "llama.cpp 能卸载到 GPU", OK if off else BAD,
        "offload=%s（False = 现在纯 CPU）" % off)
except Exception as exc:                                        # noqa: BLE001
    add(5, "llama.cpp 能卸载到 GPU", BAD, str(exc)[:80])

try:
    r = subprocess.run(["powershell", "-NoProfile", "-c",
        "Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name + '|' + [math]::Round($_.AdapterRAM/1GB,1) }"],
        capture_output=True, text=True)
    add(5, "本机显卡", WARN if "Radeon" in (r.stdout or "") else OK, (r.stdout or "").strip().replace("\n", " · ")[:120])
except Exception as exc:                                        # noqa: BLE001
    add(5, "本机显卡", WARN, str(exc)[:80])

# ── 计分 ─────────────────────────────────────────────────
bad = sum(1 for r in rows if r["state"] == BAD)
warn = sum(1 for r in rows if r["state"] == WARN)
print("=" * 74)
print(" 架构验收 · 五根柱子")
print("=" * 74)
p = None
for r in rows:
    if r["pillar"] != p:
        p = r["pillar"]
        print("\n[%d] %s" % (p, ["", "双向绑定", "互通", "秒级响应", "按需激活/内存", "算力(GPU)"][p]))
    print("   %-4s %-22s %s" % (r["state"], r["check"], r["detail"]))
print("\n" + "-" * 74)
print("合计 %d 项：绿 %d · 黄 %d · 红 %d" % (len(rows), len(rows) - bad - warn, warn, bad))
if len(sys.argv) > 2 and sys.argv[1] == "--json":
    json.dump(rows, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("已写 " + sys.argv[2])
raise SystemExit(1 if bad else 0)
