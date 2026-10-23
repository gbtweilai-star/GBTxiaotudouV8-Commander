# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 云上模型编队 —— 只读探针 / 判据（含负对照）。

主人令 2026-10-08（逐字）：「**本地不要大模型，所有的大模型都转到云插件排布好懂吗**」。

## 这件干什么

1. 读**单一真源** `deploy/cloud-10/llm-lanes.json`（19 条车道：云插件层 6 + 网关转发 9 + 本机退场 4）；
2. `probe`（默认，**只读**）：把「哪条车道活着、哪条只是占位」**现算**出来 ——
   · 云端：GET `<base>/health` 与 `<base>/v1/models`（匿名只读；base 取 state/cloud-status.json 的 base，兜底 README 记的现役地址）；
   · 网关转发：`key_gateway.energy()`（**只读直连：不铸钥、不落盘、不改运行态**——同 capability-bindings.py 的口径）；
   · 本机回环：GET 我们本机自己的 4 个固定口（11434 / 31415 / 8317 / 8111）——本机退场普查要的就是它们活没活；
   · 逐条车道给出「声明状态 vs 现读」的对照与矛盾数。
3. `--json`：把上面那份现算结果吐成机读 JSON；
4. `--check`（离线 · 不发一字节请求）：判据 8 条 + **负对照 5 条**（把「未开通」画成「已通」、把托管模型
   冒充无审查、退场件缺回滚、出处掏空、回环写回云车道 —— 每一条都必须当场报红）。

## 🔴 口径纪律（钉死，别放宽）

- **只读**：本脚本不发写请求、不铸钥、不改任何文件（连探针台账都不落——要落账的写法在 cloud-status.py，本件刻意不落）。
- **不许假绿**：只有「真发过一次、回包读到了」才算「可通」；没有探活口的车道如实写「无探活口」，不许画成通。
- **不许拿托管模型冒充无审查**：C2 专门钉死（hosting 不许是托管、模型 id 不许是 `@cf/` 目录 id）。
- **本机只许退场**：C5 钉死「非退场车道的端点/开通文案里不许出现回环地址」。
- **额度价格查不到就写查不到**：C6 钉死出处纪律（cost 要么带「查不到」，要么 cost_source 指向真源里的 sources）。

## 发请求前的 host 校验（照 cloud-status.py 的口径，防 SSRF / DNS rebinding）

- 云端 base：只允许公网 http/https；回环/私网/链路本地/保留/组播一律拒发；
- 回环口：**只**允许脚本里写死的 4 个本机口（11434/31415/8317/8111），其余一律拒发、不许用户输入进来。

用法：
    py -3.14 tools/codex-scripts/llm-lanes.py            # 现算（只读）· 打印逐车道表
    py -3.14 tools/codex-scripts/llm-lanes.py --json     # 同上 · 机读 JSON
    py -3.14 tools/codex-scripts/llm-lanes.py --check    # 判据 + 负对照 · 退出码 0/1 ｜ 加 --json 出机读

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import copy
import ipaddress
import json
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
SSOT = ROOT / "deploy" / "cloud-10" / "llm-lanes.json"   # 单一真源（本编队）
STATE = ROOT / "state" / "cloud-status.json"             # **只读**（借用它的 base 与现役口径，不改它）
BASE_DEFAULT = "https://gbt-potato-cloud-10.lopaycn.workers.dev"
UA = "gbt-llm-lanes/1.0 (+" + BASE_DEFAULT + ")"
TIMEOUT_CLOUD = 3.0
TIMEOUT_LOCAL = 2.0
LOOP_PORTS = {11434: "Ollama", 31415: "FreeLLMAPI", 8317: "CLIProxyAPI", 8111: "小土豆本机端点"}
TZ = timezone(timedelta(hours=8))

REQUIRED_LANE_FIELDS = ("id", "name", "purpose", "hosting", "endpoint", "model", "used_by",
                        "cost", "cost_source", "status", "points_at", "binds_with", "needs")
LOCAL_IDS = ("lane-local-gbt-local", "lane-local-freellmapi", "lane-local-cliproxy", "lane-local-potato")
UNCENSORED_ID = "lane-c03-uncensored-text"

CMD_PROBE = "py -3.14 tools/codex-scripts/llm-lanes.py"
CMD_JSON = "py -3.14 tools/codex-scripts/llm-lanes.py --json"
CMD_CHECK = "py -3.14 tools/codex-scripts/llm-lanes.py --check"


def now_iso() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


# ══════════════════════════════════════════════════════════════════════════
# 🔴 host 校验（发请求前唯一一道闸）
# ══════════════════════════════════════════════════════════════════════════
def host_guard(url: str, allow_local: bool = False):
    """返回 (ok, why)。allow_local=True 只给「写死的本机 4 口」用（本机退场普查的目的就是量它们）。"""
    try:
        p = urllib.parse.urlsplit(url)
    except Exception as e:                                              # noqa: BLE001
        return False, "URL 解析不了：%s" % str(e)[:80]
    if p.scheme not in ("http", "https"):
        return False, "协议不是 http/https：%r" % (p.scheme or "(空)")
    host = p.hostname
    if not host:
        return False, "缺主机名"
    h = host.lower().rstrip(".")
    if allow_local:
        if h != "127.0.0.1":
            return False, "回环探针只许写死的 127.0.0.1（实际 %s）" % h
        port = p.port or 80
        if port not in LOOP_PORTS:
            return False, "回环探针只许那 4 个写死的口（实际 %s）" % port
        return True, None
    if (h in ("localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback")
            or h.endswith(".localhost") or h.endswith(".local") or h.endswith(".internal")):
        return False, "本地名（localhost/.local/.internal）：%s" % host
    port = p.port or (443 if p.scheme == "https" else 80)
    ips = []
    try:
        ipaddress.ip_address(h)
        ips = [h]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            ips = sorted({i[4][0] for i in infos})
        except Exception as e:                                          # noqa: BLE001
            return False, "域名解析不了（无法证明是公网地址 ⇒ 拒发）：%s" % str(e)[:60]
        if not ips:
            return False, "域名没解析出任何地址"
    for a in ips:
        try:
            ip = ipaddress.ip_address(str(a).split("%")[0])
        except ValueError:
            return False, "解析出非法地址 %r" % a
        if ip.is_loopback or ip.is_link_local or ip.is_private or ip.is_reserved \
                or ip.is_multicast or ip.is_unspecified:
            return False, "回环/私有/链路本地/保留/组播（%s）不许发" % ip
    return True, None


# ══════════════════════════════════════════════════════════════════════════
# 真源读取（只读）
# ══════════════════════════════════════════════════════════════════════════
def load_ssot() -> dict:
    return json.loads(SSOT.read_text(encoding="utf-8"))


def base_of() -> str:
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        b = (d.get("base") or "").strip()
        if b:
            return b
    except Exception:                                                   # noqa: BLE001
        pass
    return BASE_DEFAULT


def _http_get(url: str, timeout: float, allow_local: bool = False) -> dict:
    ok, why = host_guard(url, allow_local=allow_local)
    if not ok:
        return {"url": url, "blocked": True, "why": why, "http": None, "ok": None, "raw": ""}
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={"user-agent": UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            return {"url": url, "http": r.status, "ms": int((time.perf_counter() - t0) * 1000),
                    "ok": r.status == 200, "raw": raw[:4000], "blocked": False, "why": None}
    except urllib.error.HTTPError as e:                                 # 4xx/5xx 是读数不是异常
        raw = e.read().decode("utf-8", "replace")
        return {"url": url, "http": e.code, "ms": int((time.perf_counter() - t0) * 1000),
                "ok": False, "raw": raw[:600], "blocked": False, "why": "HTTP %d" % e.code}
    except Exception as e:                                              # noqa: BLE001
        return {"url": url, "http": None, "ms": int((time.perf_counter() - t0) * 1000),
                "ok": False, "raw": "", "blocked": False,
                "why": "%s: %s" % (type(e).__name__, str(e)[:120])}


# ══════════════════════════════════════════════════════════════════════════
# 现算（probe）—— 四路只读证据
# ══════════════════════════════════════════════════════════════════════════
def probe_cloud(base: str) -> dict:
    """云端只读面：/health（逐模块表）与 /v1/models（模型面自报）。"""
    base = base.rstrip("/")
    health = _http_get(base + "/health", TIMEOUT_CLOUD)
    rows = {}
    if health.get("ok"):
        try:
            body = json.loads(health["raw"])
            for r in body.get("rows") or []:
                rows[r.get("id")] = r
        except Exception:                                               # noqa: BLE001
            pass
    models = _http_get(base + "/v1/models", TIMEOUT_CLOUD)
    v1 = {}
    if models.get("ok"):
        try:
            v1 = json.loads(models["raw"]).get("gbt") or {}
        except Exception:                                               # noqa: BLE001
            v1 = {}
    return {"base": base, "health": health, "rows": rows, "v1_models": models, "v1_gbt": v1}


def probe_key_gateway() -> dict:
    """能量链只读读数（key_gateway.energy；不铸钥、不落盘、不改运行态）。"""
    out = {"ok": False, "slots": {}, "error": None}
    try:
        if str(ROOT) not in sys.path:            # 直接跑本文件时包根不在 sys.path —— 先补上
            sys.path.insert(0, str(ROOT))
        from gbt_allinone.llm import key_gateway as kg
        e = kg.energy()
        for s in e.get("slots") or []:
            out["slots"][s["provider"]] = {"status": s.get("status"), "alive": bool(s.get("alive")),
                                           "tier": s.get("tier"), "url": s.get("url"), "model": s.get("model")}
        out["ok"] = True
    except Exception as e:                                              # noqa: BLE001
        out["error"] = "%s: %s" % (type(e).__name__, str(e)[:120])
    return out


def probe_loopback() -> dict:
    """我们本机自己的 4 个固定口（写死；别的口一律不发）。"""
    out = {}
    for port, who in LOOP_PORTS.items():
        r = _http_get("http://127.0.0.1:%d/v1/models" % port, TIMEOUT_LOCAL, allow_local=True)
        if r.get("blocked"):
            state = "被 host 校验拦下（不发）"
        elif r.get("http") == 200:
            state = "在跑（HTTP 200）"
        elif r.get("http") in (401, 403):
            state = "在跑（HTTP %d · 要鉴权）" % r["http"]
        elif r.get("http"):
            state = "在跑（HTTP %s）" % r["http"]
        else:
            state = "未监听（%s）" % (r.get("why") or "拒连")
        out[str(port)] = {"who": who, "state": state, "http": r.get("http"), "ms": r.get("ms")}
    return out


GW_MAP = {
    "lane-gw-agnes": "agnes", "lane-gw-deepseek": "deepseek", "lane-gw-kimi": "kimi",
    "lane-gw-nvidia-glm": "nvidia-glm", "lane-gw-nvidia-flash": "nvidia-flash",
    "lane-gw-openai-teamorouter": "openai", "lane-gw-anthropic": "anthropic",
    "lane-gw-gemini": "gemini", "lane-gw-custom": "custom",
}
LOCAL_MAP = {
    "lane-local-gbt-local": "11434", "lane-local-freellmapi": "31415",
    "lane-local-cliproxy": "8317", "lane-local-potato": "8111",
}


def live_for_lane(lane: dict, cloud: dict, gw: dict, loop: dict) -> dict:
    """给一条车道算「现读」。判据：只有真读到的才算数；没有探活口的如实写「无探活口」。"""
    lid = lane.get("id")
    rows, v1 = cloud.get("rows") or {}, cloud.get("v1_gbt") or {}

    if lid == "lane-c01-workers-ai":
        h1 = rows.get("gbt-c01-llm-gateway") or {}
        wired = bool(h1.get("wired"))
        wrote = bool((v1.get("llm_endpoint_wired") or {}).get("non_stream"))
        return {"state": "可通" if (cloud.get("health", {}).get("ok") and wired) else "未读到",
                "ok": bool(cloud.get("health", {}).get("ok") and wired),
                "detail": "/health c01 wired=%s；/v1/models upstream=%s（LLM_ENDPOINT=%s）"
                          % (h1.get("wired"), v1.get("upstream"), "已配" if wrote else "未配")}
    if lid == "lane-c01-selfhosted":
        non_stream = bool((v1.get("llm_endpoint_wired") or {}).get("non_stream"))
        stream = bool((v1.get("llm_endpoint_wired") or {}).get("stream"))
        return {"state": "可通" if (non_stream or stream) else "未接线",
                "ok": bool(non_stream or stream),
                "detail": "llm_endpoint_wired={non_stream:%s, stream:%s}（云端自报）" % (non_stream, stream)}
    if lid == "lane-c03-uncensored-text":
        h3 = rows.get("gbt-c03-uncensored-lane") or {}
        wired = bool(h3.get("wired"))
        return {"state": "可通" if wired else "未读到", "ok": wired,
                "detail": "/health c03 wired=%s reading=%s（云端自报）" % (h3.get("wired"), h3.get("reading"))}
    if lid == "lane-c03-uncensored-image":
        return {"state": "无探活口", "ok": None,
                "detail": "图像面没有独立探活行（/health 只探 status）；真源口径=占位（未接线）。"}
    if lid in ("lane-c07-embeddings", "lane-vision"):
        return {"state": "无探活口", "ok": None,
                "detail": "云侧无绑定可探（真源口径=未开通）；现役 c07 用词袋 embed() 占位。"}
    if lid in GW_MAP:
        if not gw.get("ok"):
            return {"state": "未取证", "ok": None,
                    "detail": "key_gateway 读不到：%s" % gw.get("error")}
        s = (gw.get("slots") or {}).get(GW_MAP[lid]) or {}
        st, alive = s.get("status"), bool(s.get("alive"))
        state = "可通" if st == "可用" else ("未开通" if st else "未取证")
        return {"state": state, "ok": alive, "detail": "能量链现读：%s（tier=%s · %s）"
                % (st, s.get("tier"), s.get("url") or "无 URL")}
    if lid in LOCAL_MAP:
        p = (loop or {}).get(LOCAL_MAP[lid]) or {}
        port_state = p.get("state") or "未探测"
        gw_slot = {"lane-local-gbt-local": "gbt-local", "lane-local-freellmapi": "freellmapi",
                   "lane-local-cliproxy": "cliproxy", "lane-local-potato": "potato"}[lid]
        s = (gw.get("slots") or {}).get(gw_slot) or {}
        st = s.get("status") or ("未取证" if not gw.get("ok") else "未读到")
        return {"state": "在跑" if "在跑" in port_state else ("未监听" if "未监听" in port_state else "未探测"),
                "ok": ("在跑" in port_state),
                "detail": "回环口 %s → %s；链上现读=%s" % (LOCAL_MAP[lid], port_state, st)}
    return {"state": "无探活口", "ok": None, "detail": "真源里有、探针不认识的车道（如实写无探活口）。"}


def verdict_for(declared: str, live: dict) -> str:
    """声明 vs 现读：退场件允许「还在跑」（未执行）；别的对不上就是矛盾。"""
    d, st = str(declared or ""), live.get("state")
    if d.startswith("退场"):
        return "一致（退场未执行，现读为准）"
    if d.startswith("已通"):
        if live.get("ok") is True and st in ("可通", "在跑"):
            return "一致"
        if live.get("ok") is None:
            return "矛盾（声明已通但现读无证据）"
        return "矛盾（声明已通但现读：%s）" % st
    if d.startswith("未开通") or d.startswith("占位"):
        if live.get("ok") is True:
            return "矛盾（真源落后：车道已可通，真源还写 %s）" % d
        return "一致"
    return "未定义的声明状态：%s" % d


def run_probe(base: str) -> dict:
    ssot = load_ssot()
    lanes = ssot.get("lanes") or []
    cloud = probe_cloud(base)
    gw = probe_key_gateway()
    loop = probe_loopback()
    out_lanes = []
    mismatch = 0
    for lane in lanes:
        live = live_for_lane(lane, cloud, gw, loop)
        v = verdict_for(lane.get("status"), live)
        if v.startswith("矛盾"):
            mismatch += 1
        out_lanes.append({"id": lane.get("id"), "name": lane.get("name"),
                          "declared": lane.get("status"), "live": live, "verdict": v})
    declared_ok = sum(1 for x in lanes if str(x.get("status", "")).startswith("已通"))
    local_ids = set(LOCAL_IDS)
    return {
        "at": now_iso(), "ssot": "deploy/cloud-10/llm-lanes.json", "base": base,
        "evidence": {"cloud": cloud, "key_gateway": gw, "loopback": loop},
        "lanes": out_lanes,
        "summary": {"lanes": len(lanes), "declared_ok": declared_ok,
                    "live_ok": sum(1 for x in out_lanes
                                   if x["live"].get("ok") is True and x["id"] not in local_ids),
                    "loop_running": sum(1 for x in out_lanes
                                        if x["id"] in local_ids and x["live"].get("ok") is True),
                    "retire_planned": sum(1 for x in lanes if str(x.get("status", "")).startswith("退场")),
                    "mismatch": mismatch},
    }


def print_probe(model: dict) -> int:
    ev = model["evidence"]
    ch, cm = ev["cloud"]["health"], ev["cloud"]["v1_models"]
    print("=" * 96)
    print("云上模型编队 · 只读探针（%s）" % model["at"])
    print("=" * 96)
    print("  真源：%s · 探测基址：%s" % (model["ssot"], model["base"]))
    print("  云端 /health     → HTTP %s %s" % (ch.get("http"), ("（%d 个模块行）" % len(ev["cloud"]["rows"])) if ch.get("ok") else ("· %s" % (ch.get("why") or ""))))
    print("  云端 /v1/models  → HTTP %s %s" % (cm.get("http"), ("upstream=%s · weights_ours=%s" % (ev["cloud"]["v1_gbt"].get("upstream"), ev["cloud"]["v1_gbt"].get("weights_ours"))) if cm.get("ok") else ("· %s" % (cm.get("why") or ""))))
    if ev["key_gateway"].get("ok"):
        slots = ev["key_gateway"]["slots"]
        print("  能量链           → %d 条 · 可用 %d 条（key_gateway.energy 只读）"
              % (len(slots), sum(1 for s in slots.values() if s.get("alive"))))
    else:
        print("  能量链           → 🔴 读不到：%s" % ev["key_gateway"].get("error"))
    print("  本机 4 回环口    → " + " ｜ ".join("%s:%s" % (p, ev["loopback"][p]["state"]) for p in ("11434", "31415", "8317", "8111")))
    print("-" * 96)
    print("  %-28s %-18s %-12s %s" % ("车道", "声明", "现读", "判定"))
    for x in model["lanes"]:
        flag = "🔴" if x["verdict"].startswith("矛盾") else "✓"
        print("  %-28s %-18s %-12s %s %s" % (x["id"], str(x["declared"])[:18], str(x["live"].get("state")), flag, x["verdict"]))
    s = model["summary"]
    print("-" * 96)
    print("  车道 %d · 声明已通 %d · 现读可通（云侧）%d · 本机回环在跑 %d（退场计划 %d）· **矛盾 %d**"
          % (s["lanes"], s["declared_ok"], s["live_ok"], s["loop_running"], s["retire_planned"], s["mismatch"]))
    print("  复验：%s  ｜  %s" % (CMD_JSON, CMD_CHECK))
    return 1 if s["mismatch"] else 0


# ══════════════════════════════════════════════════════════════════════════
# 判据（离线 · 不发一字节请求）—— 纯函数，判据与负对照共用
# ══════════════════════════════════════════════════════════════════════════
def run_checks(ssot: dict) -> list:
    rows = []

    def add(cid, ok, detail):
        rows.append({"id": cid, "ok": bool(ok), "detail": detail})

    lanes = ssot.get("lanes") or []
    by_id = {l.get("id"): l for l in lanes}
    src_ids = {s.get("id") for s in (ssot.get("sources") or [])}

    # C1 真源可读 · 车道齐 · 必填字段齐
    missing = []
    for l in lanes:
        for f in REQUIRED_LANE_FIELDS:
            if not l.get(f):
                missing.append("%s.%s" % (l.get("id"), f))
    add("C1 真源可读 · 车道 ≥10 · 必填字段齐（%d 条）" % len(lanes),
        bool(lanes) and len(lanes) >= 10 and not missing,
        "缺字段：%s" % (missing[:5] or "无"))

    # C2 无限制车道不许拿托管模型冒充（hosting 不许托管 · 模型 id 不许 @cf/ 目录）
    u = by_id.get(UNCENSORED_ID) or {}
    bad2 = []
    if not u:
        bad2.append("无限制文本车道不在册")
    else:
        if "Workers AI" in str(u.get("hosting")):
            bad2.append("hosting 出现「Workers AI」（托管冒充）")
        if str(u.get("model", "")).startswith("@cf/"):
            bad2.append("模型 id 是托管目录 id（%s）" % u.get("model"))
        if "冒充" not in str(u.get("boundary", "")):
            bad2.append("boundary 没写死「不许拿托管模型冒充」")
    add("C2 无限制车道在册且不是托管冒充（hosting/模型 id/boundary 三查）", not bad2,
        "违规：%s" % (bad2 or "无"))

    # C3 本机 4 回环退场在册：status 含退场 + retire 四字段齐
    bad3 = []
    for lid in LOCAL_IDS:
        l = by_id.get(lid)
        if not l:
            bad3.append("%s 不在册" % lid)
            continue
        if "退场" not in str(l.get("status")):
            bad3.append("%s status 不含「退场」" % lid)
        r = l.get("retire") or {}
        for k in ("回环端点", "链上位次", "接管云槽位", "怎么回滚"):
            if not r.get(k):
                bad3.append("%s.retire 缺「%s」" % (lid, k))
    add("C3 本机回环退场 4 条在册（status=退场 · retire 四字段：端点/链位/接管/回滚）", not bad3,
        "违规：%s" % (bad3[:4] or "无"))

    # C4 不许假绿：已通 ⇒ 必须有 ok=true 的证据；未开通/占位 ⇒ 证据里不许出现 ok=true
    #    （退场件允许 ok=true —— 那记的是「现读还在跑」的真读数，不是把它画成绿；退场件的绿由 status 管住）
    bad4 = []
    for l in lanes:
        lid, st = l.get("id"), str(l.get("status", ""))
        evd = l.get("evidence") or []
        ok_true = [e for e in evd if isinstance(e, dict) and e.get("ok") is True]
        if st.startswith("已通"):
            if not evd:
                bad4.append("%s 声明已通但没有证据" % lid)
            else:
                for e in ok_true:
                    if not (e.get("url") or e.get("kind")) or not e.get("at"):
                        bad4.append("%s 证据缺 url/kind 或 at" % lid)
                if not ok_true:
                    bad4.append("%s 声明已通但证据里没有 ok=true 的一条" % lid)
        elif st.startswith("退场"):
            for e in evd:
                if isinstance(e, dict) and not e.get("at"):
                    bad4.append("%s 退场件证据缺 at" % lid)
        else:
            if ok_true:
                bad4.append("%s 状态=%s 但证据里有 ok=true（提前画绿）" % (lid, st))
    add("C4 不许假绿（已通⇒ok=true 证据 + url/kind/at；未开通/占位⇒不许出现 ok=true；退场件允许「还在跑」读数）", not bad4,
        "违规：%s" % (bad4[:4] or "无"))

    # C5 本机只许退场：非退场车道的 endpoint 与 needs 文案不许出现回环地址
    bad5 = []
    for l in lanes:
        if "退场" in str(l.get("status", "")):
            continue
        blob = str(l.get("endpoint", "")) + " " + json.dumps(l.get("needs") or {}, ensure_ascii=False)
        if "127.0.0.1" in blob or "localhost" in blob:
            bad5.append(l.get("id"))
    add("C5 非退场车道不许把回环写进端点/开通文案（退场后不许回吊本机）", not bad5,
        "违规：%s" % (bad5 or "无"))

    # C6 出处纪律：cost 非空；不带「查不到」的 cost 必须有合法 cost_source（「—」只许本机退场件用——
    #    本机电费没有外部出处，但云侧/网关侧车道不许拿「—」蒙混）；sources 元数据齐
    bad6 = []
    for s in (ssot.get("sources") or []):
        for k in ("id", "on", "name", "url", "fetched", "quote"):
            if not s.get(k):
                bad6.append("sources[%s] 缺 %s" % (s.get("id"), k))
    for l in lanes:
        lid = str(l.get("id") or "")
        cost, cs = str(l.get("cost") or ""), str(l.get("cost_source") or "")
        if not cost:
            bad6.append("%s.cost 为空" % lid)
            continue
        if "查不到" in cost:
            continue
        toks = [t.strip() for t in cs.split("/") if t.strip()]
        if cs.strip() == "—" and lid.startswith("lane-local-"):
            continue                                    # 本机退场件：本机电费，明确写「无平台账」
        if not toks or not any(t in src_ids for t in toks):
            bad6.append("%s 的 cost_source=%r 没指向真源里的 sources" % (lid, cs))
    add("C6 出处纪律（cost 非空；非「查不到」必须带合法 cost_source；sources 六字段齐）", not bad6,
        "违规：%s" % (bad6[:4] or "无"))

    # C7 图像面覆盖：IMAGE_ENDPOINT 在册，且该车道不许提前画绿
    img = [l for l in lanes
           if "IMAGE_ENDPOINT" in (str(l.get("endpoint", "")) + " " + json.dumps(l.get("needs") or {}, ensure_ascii=False))]
    ok7 = bool(img) and all(not str(l.get("status", "")).startswith("已通") for l in img)
    add("C7 图像面 IMAGE_ENDPOINT 在册（且未开通时不许画成已通）", ok7,
        "命中车道：%s" % [l.get("id") for l in img] or "无")

    # C8 改动点纪律：全部未执行 · ≥8 条 · 字段齐 · 覆盖三个落点
    cp = ssot.get("change_points") or {}
    pts = cp.get("points") or []
    bad8 = []
    if cp.get("executed") is not False:
        bad8.append("change_points.executed 不是 false")
    if len(pts) < 8:
        bad8.append("改动点少于 8 条（现读 %d）" % len(pts))
    for p in pts:
        for k in ("id", "file", "line", "what", "rollback"):
            if not p.get(k):
                bad8.append("%s 缺 %s" % (p.get("id"), k))
        if p.get("executed") is not False:
            bad8.append("%s 没标「未执行」" % p.get("id"))
    files = " ".join(str(p.get("file")) for p in pts)
    for need in ("cloud_llm.py", "key_gateway.py", "~/.dsh"):
        if need not in files:
            bad8.append("改动点没覆盖 %s" % need)
    add("C8 改动点纪律（≥8 条 · 每条 file/line/what/rollback · 全部未执行 · 覆盖两链路表+~/.dsh）", not bad8,
        "违规：%s" % (bad8[:4] or "无"))

    return rows


def run_negatives(ssot: dict) -> list:
    """负对照：改坏内存副本，对应判据必须报红。"""
    negs = []

    def target_fail(mut, cid):
        rows = run_checks(mut)
        r = [x for x in rows if x["id"].startswith(cid)]
        return bool(r and not r[0]["ok"]), (r[0]["detail"] if r else "（没跑 %s）" % cid)

    # N1 假绿：未开通画成「已通」⇒ C4 必须报红
    m1 = copy.deepcopy(ssot)
    for l in m1["lanes"]:
        if l["id"] == "lane-vision":
            l["status"] = "已通"
    ok, det = target_fail(m1, "C4")
    negs.append(("假绿：未开通（lane-vision）画成「已通」", "C4", ok, det))

    # N2 托管冒充：无限制车道改成托管模型 ⇒ C2 必须报红
    m2 = copy.deepcopy(ssot)
    for l in m2["lanes"]:
        if l["id"] == UNCENSORED_ID:
            l["hosting"] = "Workers AI 托管模型"
            l["model"] = "@cf/openai/gpt-oss-120b"
    ok, det = target_fail(m2, "C2")
    negs.append(("托管冒充：无限制车道换成 Workers AI 托管模型", "C2", ok, det))

    # N3 退场件缺回滚：删掉 potato 的 retire ⇒ C3 必须报红
    m3 = copy.deepcopy(ssot)
    for l in m3["lanes"]:
        if l["id"] == "lane-local-potato":
            l.pop("retire", None)
    ok, det = target_fail(m3, "C3")
    negs.append(("退场件缺回滚：lane-local-potato 删掉 retire", "C3", ok, det))

    # N4 出处掏空：agnes 的 cost 清空 ⇒ C6 必须报红
    m4 = copy.deepcopy(ssot)
    for l in m4["lanes"]:
        if l["id"] == "lane-gw-agnes":
            l["cost"] = ""
    ok, det = target_fail(m4, "C6")
    negs.append(("出处掏空：lane-gw-agnes 的 cost 清空", "C6", ok, det))

    # N5 回环写回云车道 ⇒ C5 必须报红
    m5 = copy.deepcopy(ssot)
    for l in m5["lanes"]:
        if l["id"] == "lane-c01-selfhosted":
            l["endpoint"] = "http://127.0.0.1:9999/v1"
    ok, det = target_fail(m5, "C5")
    negs.append(("回环写回云车道：lane-c01-selfhosted 端点改成 127.0.0.1", "C5", ok, det))

    return negs


def cmd_check(as_json: bool = False) -> int:
    try:
        ssot = load_ssot()
    except Exception as e:                                              # noqa: BLE001
        print("🔴 真源读不到（%s）：%s" % (SSOT, e))
        return 2
    rows = run_checks(ssot)
    negs = run_negatives(ssot)
    fails = [r for r in rows if not r["ok"]]
    neg_fail = [x for x in negs if not x[2]]
    if as_json:
        print(json.dumps({"rows": rows,
                          "negatives": [{"name": n, "target": t, "ok": o, "detail": d} for n, t, o, d in negs],
                          "pass": len(rows) - len(fails), "fail": len(fails),
                          "neg_pass": len(negs) - len(neg_fail)}, ensure_ascii=False, indent=1))
    else:
        print("=" * 96)
        print("云上模型编队 · 判据（含负对照 · 离线 · 不发一字节请求）")
        print("=" * 96)
        for r in rows:
            print("%s %-60s %s" % ("PASS" if r["ok"] else "FAIL", r["id"], r["detail"][:120]))
        print("-" * 96)
        for nm, tg, ok, det in negs:
            print("%s 负对照[%s] %-44s %s" % ("PASS" if ok else "FAIL", tg, nm[:44], det[:110]))
        print("-" * 96)
        print("判据 PASS %d · FAIL %d ｜ 负对照 PASS %d · FAIL %d"
              % (len(rows) - len(fails), len(fails), len(negs) - len(neg_fail), len(neg_fail)))
    return 1 if (fails or neg_fail) else 0


# ══════════════════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description="云上模型编队 · 只读探针 / 判据")
    ap.add_argument("--check", action="store_true", help="跑判据 + 负对照（离线）")
    ap.add_argument("--json", action="store_true", help="机读输出")
    ap.add_argument("--base", default="", help="覆盖云端基址（默认取 state/cloud-status.json 的 base）")
    args = ap.parse_args(argv)
    if args.check:
        return cmd_check(as_json=args.json)
    base = args.base or base_of()
    ok, why = host_guard(base)
    if not ok:
        print("🔴 云端基址 host 校验不过（不发请求）：%s → %s" % (base, why))
        return 2
    model = run_probe(base)
    if args.json:
        print(json.dumps(model, ensure_ascii=False, indent=1))
        return 1 if model["summary"]["mismatch"] else 0
    return print_probe(model)


if __name__ == "__main__":
    raise SystemExit(main())
