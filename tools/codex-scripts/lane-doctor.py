#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模型车道医生（唯一入口）· GBT小土豆V8

为什么要有它：2026-10-22 页面卡死排查里，真因分散在四处（RunPod 端点参数、Worker 契约、
宿主 maxTokens、凭据真源），每一处都只能靠临时脚本 + 印象去猜。这里把它们收成一套
**有判据、有阈值、有退出码**的常设体检。

用法：
  py -3.14 tools/codex-scripts/lane-doctor.py check            # 全量体检（默认）
  py -3.14 tools/codex-scripts/lane-doctor.py check --json     # 机读
  py -3.14 tools/codex-scripts/lane-doctor.py warm             # 需要时把端点设回常驻
  py -3.14 tools/codex-scripts/lane-doctor.py latency          # 只量秒级闸

退出码：0 = 全绿（含仅 WARN）· 1 = 有 FAIL · 2 = 连读数都取不到
纪律：凭据只校验“在不在、长度对不对”，永不打印；每条 FAIL 必须带上游原话。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

# 中文 Windows 控制台是 cp936/GBK：不强制 UTF-8 就抛 UnicodeEncodeError，
# 结果 stdout 为空 ⇒ 调用方（本仓 encoding-guard-check.py 与 boot-selfcheck）把它读成空读数。
# 本仓已有 307 件这么写；本件从第一天就按这条来（不给自己留一条"新件又犯"）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

EP_ID = os.environ.get("GBT_POTATO_EP") or "qnnqf9w8xcefj8"
EP_MODEL = "/runpod-volume/gbt-v8-v83"
WORKER = "https://gbt-potato-cloud-10.paysssk.workers.dev"
CRED = os.path.join(os.path.expanduser("~"), ".dsh", ".credentials.yaml")
SETTINGS = os.path.join(os.path.expanduser("~"), ".dsh", "settings.yaml")

# 秒级闸（主人令：秒级响应）。冷启动单发不计入；取第 2、3 发的最大值。
TTFB_LIMIT_MS = 2000
TOTAL_LIMIT_MS = 6000
MIN_WORKERS = 1
MIN_IDLE_TIMEOUT = 600
MIN_CTX = 32768

ROWS = []
TOLERATE_NET = False  # --gate：把「连不上」降为 WARN（离线不等于车道坏），契约坏仍是 FAIL
# 2026-10-23 23:50 定位到的真凶：`sse_once()` 里把超时**写死 240 秒**，
#    而 G6/G7/G8 一次要打两发 ⇒ 单单这一组就 480s；加上前面 G1~G5 的请求，整条闸 >600s 挂起。
#    先前我只改了 `http()` 的**默认值**（60→15）—— 调用方显式传了 240，默认值根本没用上，
#    所以那次改动对这条闸**无效**（实测 >600s 证明了它）。
#    现在改为**模块级上限**，gate 模式更紧：判据口径不变（打不通 = 无读数 = 红/WARN），只是不许挂那么久。
SSE_TIMEOUT = 240


def tmo(seconds):
    """gate 模式下把单次请求上限压到 15s：判据该「快速红」，不该把开机自检拖成 5 分钟。
    口径不变：取不到 = 无读数 = WARN/FAIL（不会被超时放过）。"""
    return 15 if TOLERATE_NET else seconds


def set_sse_timeout(seconds):
    global SSE_TIMEOUT
    SSE_TIMEOUT = int(seconds)


def net_status(r):
    """传输层失败（status==0，请求根本没出去）在 --gate 下不算红：离线 ≠ 车道坏。"""
    if TOLERATE_NET and r.get("status") == 0:
        return "WARN"
    return "FAIL"


def row(gid, name, status, detail, fix=""):
    ROWS.append({"id": gid, "name": name, "status": status, "detail": detail, "fix": fix})


def env_get(name):
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, name)[0]
    except Exception:  # noqa: BLE001
        return ""


def cred_refs():
    try:
        t = open(CRED, encoding="utf-8").read()
    except OSError:
        return {}
    refs = {}
    # 只取 refs: 小节下的键名与值（值只在内存里用，不打印）
    in_refs = False
    for line in t.splitlines():
        if re.match(r"^refs:\s*$", line):
            in_refs = True
            continue
        if in_refs:
            if line and not line.startswith((" ", "\t")):
                break
            m = re.match(r"^\s{2}([A-Z0-9_]+):\s*(\S+)\s*$", line)
            if m:
                refs[m.group(1)] = m.group(2).strip("\"'")
    return refs


def http(url, method="GET", body=None, token=None, timeout=15, accept=None):
 # 2026-10-23：默认超时 60s → **15s**。
    # 真因：F25（端点 running=0）时每个请求都要挂到 60s，整条闸 300s 才返回，
    # 开机自检被一条死车道拖了 5 分钟。判据该是"快速红"，不是"慢速等"。
    # 读数口径不变：取不到 = 未验 = 红（不因超时短就放过）。
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    r.add_header("User-Agent", "GBTxiaotudouV8-lanedoctor/1.0")
    if accept:
        r.add_header("Accept", accept)
    if token:
        r.add_header("Authorization", "Bearer " + token)
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return {"ok": True, "status": resp.status, "body": resp.read().decode("utf-8", "replace"),
                    "ms": int((time.time() - t0) * 1000), "headers": dict(resp.headers)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "body": e.read().decode("utf-8", "replace")[:600],
                "ms": int((time.time() - t0) * 1000), "headers": dict(e.headers)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": 0, "body": "%s: %s" % (type(e).__name__, e),
                "ms": int((time.time() - t0) * 1000), "headers": {}}


# ── G1 端点参数（冷热启动的根）──────────────────────────────────────────────
def g1_endpoint_params(key):
    r = http("https://rest.runpod.io/v1/endpoints/%s" % EP_ID, token=key)
    if not r["ok"]:
        row("G1", "端点参数（workersMin/idleTimeout）", net_status(r),
            "取不到端点配置：HTTP %s %s" % (r["status"], r["body"][:200]),
            "py -3.14 tools/codex-scripts/lane-doctor.py warm")
        return None
    j = json.loads(r["body"])
    wmin = j.get("workersMin")
    wmax = j.get("workersMax")
    idle = j.get("idleTimeout")
    flash = j.get("flashboot")
    bad = []
    if not isinstance(wmin, int) or wmin < MIN_WORKERS:
        bad.append("workersMin=%s（要 ≥%d，否则每轮冷启动）" % (wmin, MIN_WORKERS))
    if not isinstance(idle, int) or idle < MIN_IDLE_TIMEOUT:
        bad.append("idleTimeout=%s（要 ≥%d 秒）" % (idle, MIN_IDLE_TIMEOUT))
    if not isinstance(wmax, int) or wmax < 1:
        bad.append("workersMax=%s" % wmax)
    if flash is not True:
        bad.append("flashboot=%s（要 true）" % flash)
    detail = "workersMin=%s · workersMax=%s · idleTimeout=%s · flashboot=%s · gpu=%s" % (
        wmin, wmax, idle, flash, ",".join(j.get("gpuTypeIds") or []))
    if bad:
        row("G1", "端点参数（workersMin/idleTimeout）", "FAIL", "；".join(bad) + " ｜ " + detail,
            "py -3.14 tools/codex-scripts/lane-doctor.py warm")
    else:
        row("G1", "端点参数（workersMin/idleTimeout）", "PASS", detail)
    return j


# ── G2 引擎健康 ────────────────────────────────────────────────────────────
def g2_health(key):
    r = http("https://api.runpod.ai/v2/%s/health" % EP_ID, token=key)
    if not r["ok"]:
        row("G2", "引擎健康（worker ready）", net_status(r),
            "HTTP %s %s" % (r["status"], r["body"][:200]),
            "" if r["status"] == 0 else "py -3.14 tools/codex-scripts/lane-doctor.py warm")
        return
    j = json.loads(r["body"])
    w = j.get("workers") or {}
    ready = int(w.get("ready") or 0)
    running = int(w.get("running") or 0)
    init = int(w.get("initializing") or 0)
    detail = "ready=%s running=%s idle=%s initializing=%s inQueue=%s" % (
        ready, running, w.get("idle"), init, (j.get("jobs") or {}).get("inQueue"))
 # 2026-10-22 判据翻正（留痕，不是静默改）：原口径只认 `ready>=1`。
    #    实测反证：本体检自己去打端点的那一瞬，那台 worker 正在跑这次调用
    #    ⇒ 读数变成 `ready=0 running=1`，旧口径当场判红 —— 而机器其实是好的。
    #    这是本仓 P1「判据错尺」的活样本（量具自己被自己的请求占住）。
    #    现口径：**running≥1 也算活着**（有 worker 在算），只有 ready=running=initializing=0 才是真没有。
    if ready >= 1 or running >= 1:
        row("G2", "引擎健康（worker ready）", "PASS",
            detail + ("（此刻 worker 正在跑请求：running≥1 即活着）" if ready == 0 else ""))
    elif init >= 1 or int((j.get("jobs") or {}).get("inQueue") or 0) >= 1:
        row("G2", "引擎健康（worker ready）", "WARN", "正在拉起（首个请求会慢）：" + detail,
            "py -3.14 tools/codex-scripts/lane-doctor.py warm")
    else:
        row("G2", "引擎健康（worker ready）", "FAIL", "没有任何活着的 worker：" + detail,
            "py -3.14 tools/codex-scripts/lane-doctor.py warm")


# ── G3 引擎模型契约 ────────────────────────────────────────────────────────
def g3_engine_models(key):
    r = http("https://api.runpod.ai/v2/%s/openai/v1/models" % EP_ID, token=key, timeout=tmo(120))
    if not r["ok"]:
        row("G3", "引擎模型（id / 窗口）", net_status(r), "HTTP %s %s" % (r["status"], r["body"][:200]))
        return None
    try:
        j = json.loads(r["body"])
    except Exception:  # noqa: BLE001
        row("G3", "引擎模型（id / 窗口）", "FAIL", "回包不是 JSON：%s" % r["body"][:200])
        return None
    ids = []
    ctx = None
    for m in j.get("data") or []:
        ids.append(m.get("id"))
        if m.get("id") == EP_MODEL:
            ctx = m.get("max_model_len") or m.get("context_length")
    if EP_MODEL in ids and isinstance(ctx, int) and ctx >= MIN_CTX:
        row("G3", "引擎模型（id / 窗口）", "PASS", "%s · max_model_len=%s" % (EP_MODEL, ctx))
    else:
        row("G3", "引擎模型（id / 窗口）", "FAIL",
            "模型清单=%s · 窗口=%s（要 %s ≥ %d）" % (ids[:4], ctx, EP_MODEL, MIN_CTX))
    return j


# ── G4 Worker 元数据（身份注入 / 自权重接线）────────────────────────────────
def g4_worker_meta(gw):
    r = http(WORKER + "/v1/models", token=gw, timeout=tmo(60))
    if not r["ok"]:
        row("G4", "Worker 元数据（自有权重接线）", net_status(r),
            "HTTP %s %s" % (r["status"], r["body"][:200]), "检查 GW_AUTH 是否与远端 secret 一致")
        return
    j = json.loads(r["body"])
    g = j.get("gbt") or {}
    m = (j.get("data") or [{}])[0]
    ctx = m.get("context_length")
    wired = g.get("llm_endpoint_wired") or {}
    ok = (m.get("id") == "gbt-potato-v8" and isinstance(ctx, int) and ctx >= MIN_CTX
          and g.get("weights_ours_configured") is True
          and wired.get("non_stream") is True and wired.get("stream") is True)
    detail = "id=%s · ctx=%s · weights_ours_configured=%s · 非流式=%s · 流式=%s" % (
        m.get("id"), ctx, g.get("weights_ours_configured"), wired.get("non_stream"), wired.get("stream"))
    row("G4", "Worker 元数据（自有权重接线）", "PASS" if ok else "FAIL", detail)


# ── G5 鉴权 fail-closed（坏钥必须 401）────────────────────────────────────
def g5_auth(gw):
    body = {"model": "gbt-potato-v8", "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8, "stream": False}
    bad = http(WORKER + "/v1/chat/completions", method="POST", body=body,
               token="gbt-invalid-doctor-probe", timeout=tmo(60))
    good = http(WORKER + "/v1/chat/completions", method="POST", body=body, token=gw, timeout=tmo(180))
    if bad["status"] == 401 and good["ok"]:
        ident = ""
        try:
            ident = json.dumps((json.loads(good["body"]).get("gbt") or {}), ensure_ascii=False)
        except Exception:  # noqa: BLE001
            pass
        ident = ident[:140]
        row("G5", "鉴权 fail-closed（坏钥 401 / 好钥 200）", "PASS",
            "坏钥=%s · 好钥=%s %sms · %s" % (bad["status"], good["status"], good["ms"], ident))
    else:
        row("G5", "鉴权 fail-closed（坏钥 401 / 好钥 200）", "FAIL",
            "坏钥=%s（要 401）· 好钥=%s %s" % (bad["status"], good["status"], good["body"][:160]))


# ── G6/G7/G8 SSE 契约 + 秒级闸 + 工具回合 ─────────────────────────────────
TOOLS = [{"type": "function", "function": {"name": "read", "description": "读文件",
                                          "parameters": {"type": "object",
                                                         "properties": {"path": {"type": "string"}},
                                                         "required": ["path"]}}}]


def sse_once(gw, tools=False, max_tokens=32):
    body = {"model": "gbt-potato-v8",
            "messages": [{"role": "user", "content": "只回两个字：到了"}],
            "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True}}
    if tools:
        body["tools"] = TOOLS
        body["tool_choice"] = "auto"
    r = http(WORKER + "/v1/chat/completions", method="POST", body=body, token=gw,
             timeout=SSE_TIMEOUT, accept="text/event-stream")
    if not r["ok"]:
        return {"ok": False, "err": "HTTP %s %s" % (r["status"], r["body"][:200])}
    lines = [ln.strip() for ln in r["body"].splitlines() if ln.strip()]
    text = ""
    finish = None
    ttfb = None
    done = False
    for ln in lines:
        if ln == "data: [DONE]" or ln == "data:[DONE]":
            done = True
            continue
        if not ln.startswith("data:"):
            continue
        try:
            j = json.loads(ln[5:].strip())
        except Exception:  # noqa: BLE001
            continue
        for ch in j.get("choices") or []:
            piece = (ch.get("delta") or {}).get("content")
            if piece:
                if ttfb is None:
                    ttfb = r["ms"]
                text += piece
            if ch.get("finish_reason"):
                finish = ch.get("finish_reason")
    return {"ok": True, "text": text, "finish": finish, "done": done, "ttfb": ttfb,
            "ms": r["ms"], "lines": len(lines)}


def g6_g7_g8(gw):
    samples = []
    first = sse_once(gw, max_tokens=32)
    if not first.get("ok"):
        st = "WARN" if TOLERATE_NET else "FAIL"
        row("G6", "SSE 契约（finish_reason + [DONE]）", st, first.get("err", ""))
        row("G7", "秒级闸（首字/整轮）", st, "SSE 打不通，无读数")
        row("G8", "工具回合（带 tools 仍能收尾）", st, "SSE 打不通，无读数")
        return
    samples.append(first)
    time.sleep(0.4)
    samples.append(sse_once(gw, max_tokens=32))

    ok_contract = all(s.get("finish") in ("stop", "tool_calls") and s.get("done") for s in samples)
    detail = "；".join("finish=%s done=%s 首字=%sms 整轮=%sms" % (
        s.get("finish"), s.get("done"), s.get("ttfb"), s.get("ms")) for s in samples)
    row("G6", "SSE 契约（finish_reason + [DONE]）",
        "PASS" if ok_contract else "FAIL", detail,
        "" if ok_contract else "Worker 流式分支没按 OpenAI 契约收尾")

    warm = samples[1:] or samples
    ttfb_max = max([s.get("ttfb") or 99999 for s in warm])
    total_max = max([s.get("ms") or 99999 for s in warm])
    ok_speed = ttfb_max <= TTFB_LIMIT_MS and total_max <= TOTAL_LIMIT_MS
    row("G7", "秒级闸（首字 ≤%dms · 整轮 ≤%dms）" % (TTFB_LIMIT_MS, TOTAL_LIMIT_MS),
        "PASS" if ok_speed else "FAIL",
        "热态样本 首字=%dms 整轮=%dms（第 1 发计入判定外的冷样本 首字=%sms）" % (
            ttfb_max, total_max, samples[0].get("ttfb")),
        "" if ok_speed else "先确认 G1/G2；冷启动时这一条只应 WARN")

    t = sse_once(gw, tools=True, max_tokens=96)
    if not t.get("ok"):
        row("G8", "工具回合（带 tools 仍能收尾）", "FAIL", t.get("err", ""))
    elif t.get("finish") in ("stop", "tool_calls") and t.get("done"):
        row("G8", "工具回合（带 tools 仍能收尾）", "PASS",
            "finish=%s · 整轮=%sms · 正文=%r" % (t.get("finish"), t.get("ms"), (t.get("text") or "")[:40]))
    else:
        row("G8", "工具回合（带 tools 仍能收尾）", "FAIL",
            "finish=%s done=%s（要 stop/tool_calls 且带 [DONE]）" % (t.get("finish"), t.get("done")))


# ── G9 凭据真源（两套名字空间不许互抄）────────────────────────────────────
def g9_credentials(refs):
    gw = refs.get("GW_AUTH") or ""
    rp = refs.get("GBT_POTATO_API_KEY") or ""
    env_gw = env_get("GW_AUTH")
    env_other = env_get("GBT_GATEWAY_TOKEN")
    detail = "refs.GW_AUTH=%s(%d位) · refs.GBT_POTATO_API_KEY=%s(%d位)" % (
        (gw[:4] + "****") if gw else "缺", len(gw),
        (rp[:4] + "****") if rp else "缺", len(rp))
    problems = []
    if len(gw) < 20:
        problems.append("refs 里没有可用的 GW_AUTH（云端 Worker 的钥匙）")
    if len(rp) < 20:
        problems.append("refs 里没有可用的 GBT_POTATO_API_KEY（RunPod 引擎/控制面钥匙）")
 # 2026-10-22 现读订正（留痕）：先前把 HKCU 的 `GBT_GATEWAY_TOKEN` 判成「过期的同一把钥匙」，
    #    去查消费者才知道那是**另一个网关**的令牌 —— `gbt_allinone/tools/capability_gateway.py`
    #    读它做 `X-GBT-Token` 鉴权（第 32/84 行），`deepseek_key.py` 第 107 行也登记它。
    #    ⇒ 两者**不是**同一把：Worker 要 refs.GW_AUTH，本机能力网关卡要 HKCU GBT_GATEWAY_TOKEN。
    #    现在只在「环境里另有一把 GW_AUTH 且与 refs 不同」时才告警（那会让宿主取错钥）。
    if env_gw and gw and env_gw != gw:
        problems.append("环境变量里另有一把 GW_AUTH（%s…）与 refs 不一致 —— 宿主按哪个取钥不明确"
                        % env_gw[:6])
    note = ""
    if env_other and gw:
        note = " · 另：HKCU GBT_GATEWAY_TOKEN(%s…) 是本机能力网关的令牌（X-GBT-Token），与 Worker 的 GW_AUTH 是两把钥，别互抄" % env_other[:10]
    if problems:
        row("G9", "凭据真源", "FAIL", "；".join(problems) + " ｜ " + detail + note)
    else:
        row("G9", "凭据真源（Worker 钥 / 引擎钥 / 本机网关钥各归其位）", "PASS", detail + note)


# ── G10 宿主默认车道 / 上下文政策 ──────────────────────────────────────────
def g10_host_default():
    try:
        t = open(SETTINGS, encoding="utf-8").read()
    except OSError:
        row("G10", "宿主默认车道", "WARN", "读不到 %s" % SETTINGS)
        return
    m = re.search(r"agent-default-model:\s*\n\s*provider:\s*(\S+)\s*\n\s*model:\s*(\S+)", t)
    if not m:
        row("G10", "宿主默认车道", "WARN", "settings.yaml 里没有 agent-default-model")
        return
    prov, model = m.group(1), m.group(2)
    if prov in ("gbt-potato", "gbt-v8"):
        row("G10", "宿主默认车道", "PASS", "%s / %s（自有权重）" % (prov, model))
    else:
        row("G10", "宿主默认车道", "WARN", "%s / %s（不是自有权重车道）" % (prov, model))


def do_check(as_json=False):
    refs = cred_refs()
    gw = refs.get("GW_AUTH") or ""
    rp = refs.get("GBT_POTATO_API_KEY") or ""
    if not rp:
        rp = env_get("GBT_POTATO_API_KEY")
    if not gw:
        print("拿不到 GW_AUTH（凭据 refs），无从体检")
        return 2

    def safe(fn, *a):
        try:
            fn(*a)
        except Exception as e:  # noqa: BLE001
            row(fn.__name__.upper(), fn.__name__, "FAIL", "探针自己抛错：%s: %s" % (type(e).__name__, e))

    safe(g1_endpoint_params, rp)
    safe(g2_health, rp)
    safe(g3_engine_models, rp)
    safe(g4_worker_meta, gw)
    safe(g5_auth, gw)
    safe(g6_g7_g8, gw)
    safe(g9_credentials, refs)
    safe(g10_host_default)

    fails = [r for r in ROWS if r["status"] == "FAIL"]
    warns = [r for r in ROWS if r["status"] == "WARN"]
    if as_json:
        print(json.dumps({"stamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "rows": ROWS,
                          "fails": len(fails), "warns": len(warns)}, ensure_ascii=False, indent=2))
    else:
        print("GBT小土豆V8 · 模型车道体检 · %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
        print("-" * 96)
        for r in ROWS:
            print("%-4s %-4s %-34s %s" % (r["id"], r["status"], r["name"], r["detail"]))
            if r["fix"] and r["status"] != "PASS":
                print("      ↳ 修法：%s" % r["fix"])
        print("-" * 96)
        print("合计 %d 项：PASS %d · WARN %d · FAIL %d" % (
            len(ROWS), len(ROWS) - len(fails) - len(warns), len(warns), len(fails)))
    return 0 if not fails else 1


def do_warm():
    refs = cred_refs()
    rp = refs.get("GBT_POTATO_API_KEY") or env_get("GBT_POTATO_API_KEY")
    if not rp:
        print("拿不到 RunPod 控制面钥匙（GBT_POTATO_API_KEY）")
        return 2
    body = {"workersMin": MIN_WORKERS, "idleTimeout": MIN_IDLE_TIMEOUT}
    r = http("https://rest.runpod.io/v1/endpoints/%s" % EP_ID, method="PATCH", body=body, token=rp)
    print("PATCH %s → HTTP %s %sms" % (json.dumps(body), r["status"], r["ms"]))
    if not r["ok"]:
        print(r["body"][:400])
        return 1
    print("已设回常驻。回滚：PATCH workersMin=0")
    return 0


def do_latency():
    refs = cred_refs()
    gw = refs.get("GW_AUTH") or ""
    if not gw:
        print("拿不到 GW_AUTH")
        return 2
    for i in range(3):
        s = sse_once(gw, max_tokens=32)
        print("第%d发：" % (i + 1) + ("首字=%sms 整轮=%sms finish=%s done=%s 正文=%r" % (
            s.get("ttfb"), s.get("ms"), s.get("finish"), s.get("done"), (s.get("text") or "")[:30])
            if s.get("ok") else s.get("err")))
        time.sleep(0.3)
    return 0


def main():
    global TOLERATE_NET
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="check", choices=["check", "warm", "latency"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gate", action="store_true",
                    help="开机自检用：把「连不上」（传输层失败）降为 WARN，契约坏仍是 FAIL")
    a = ap.parse_args()
    TOLERATE_NET = bool(a.gate)
    set_sse_timeout(12 if a.gate else 60)      # gate：12s 快速红；手动排查：60s
    if a.cmd == "check":
        return do_check(a.json)
    if a.cmd == "warm":
        return do_warm()
    return do_latency()


if __name__ == "__main__":
    sys.exit(main())
