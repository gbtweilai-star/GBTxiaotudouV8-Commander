# -*- coding: utf-8 -*-
"""云插件独立页 + 可视化连接状态面板 · 生成器 / 真探针 / 判据（主人令 2026-10-07）。

主人原话：「把云插件独立页面和可视化连接状态面板都要设计上。」

本件是 `tools/codex-scripts/cloud-plugins.py`（云插件互绑拓扑页）的**姊妹件**，不是重做：
  · 拓扑页（`holo_pet_w3/plugins-mesh/index.html`）管「谁和谁互绑」；
  · 本件管两件事 ——
      A. **云插件独立页** `holo_pet_w3/cloud-plugins/index.html`：
         每个云插件一张卡片（带锚点 #c01…），一眼看全 id / 名称 / 角色 / 端点 / 能力 op / 与谁互绑。
      B. **可视化连接状态面板** `holo_pet_w3/cloud-status/index.html`：
         把「连接状态」画出来 —— 每个插件与每条连接都是 **通 / 不通 / 未探测** 三态，
         图例写明每种颜色的含义，逐条给出「探于何时 / 延迟多少 / 失败原因原文」。

单一真源与「现役」口径（**以现读为准，不猜**）：
  · `deploy/cloud-10/mesh.json` —— **现役真源**：10 个真模块（含 ops / op_gates / cloud / 边界），
    就是云端那台已部署 Worker（形态 A：10 模块同一 isolate）里的 10 个云插件。`probe` 探的就是它。
  · `deploy/cloud-10/plugins50.json` —— **蓝图**：50 槽（30 spec + 20 reserve），**未部署、无 ops、
    无端点**，只作「另册 · 50 槽蓝图」注记，**不探测**（对未部署的槽发请求只会造假红）。
    ⇒ 两份都在 `deploy/cloud-10/` 下；**现役=mesh.json**（有真 op、云端真在跑），页面上如实分开写。

三态（**不许假绿**）：
  · 通       = 真发过一次请求，HTTP 200 且本插件那一行 `ok=true`；
  · 不通     = 真发过，但失败（HTTP 非 200 / 超时 / 行内 ok=false / 回包缺行）—— 落**原始** status/错误串；
  · 未探测   = **没跑过 probe**（或该端点在探测前被 host 校验拦下）—— 一律「未探测」，**不许画成通**。

🔴 发请求前的 host 校验（防 SSRF / DNS rebinding，照 `slot_bridge_agent.py` 的口径）：
  只允许 `http`/`https`；**必须拒绝** `localhost`、回环（127.0.0.0/8、::1）、私有网段
  （10/8、172.16/12、192.168/16）、链路本地（169.254/16）与保留/组播地址。校验不过的端点
  **不许发请求**，直接记 `blocked` 并把原因写进结果。

用法：
    py -3.14 tools/codex-scripts/cloud-status.py probe            # 真探一次，落 state/cloud-status.json
    py -3.14 tools/codex-scripts/cloud-status.py render           # 生成两页 + 两个数据件（经典脚本）
    py -3.14 tools/codex-scripts/cloud-status.py --check          # 判据 ≥8 条（含负对照）· 退出码 0/1

    # 可换探测基址（默认读 deploy/cloud-10/README.md 记录的现役地址）：
    py -3.14 tools/codex-scripts/cloud-status.py probe --base https://gbt-potato-cloud-10.lopaycn.workers.dev

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
# 审美令牌（内联版）：唯一实现在 `_taste_inline.py`。本件产两页且都要求"零远端请求"，
# 所以只能生成期内联，不能挂 <link>（相对路径的 <link> 虽不算远端，但会让页面不再自包含）。
from _taste_inline import site_root_block  # noqa: E402
from _page_emit import clean_html  # noqa: E402
MESH = ROOT / "deploy" / "cloud-10" / "mesh.json"                 # 现役真源（10 真模块）
SPEC50 = ROOT / "deploy" / "cloud-10" / "plugins50.json"          # 蓝图（50 槽 · 不探测）
STATE = ROOT / "state" / "cloud-status.json"                      # 探测台账
PAGE_A = ROOT / "holo_pet_w3" / "cloud-plugins" / "index.html"
DATA_A = ROOT / "holo_pet_w3" / "cloud-plugins" / "cloud-plugins-data.js"
PAGE_B = ROOT / "holo_pet_w3" / "cloud-status" / "index.html"
DATA_B = ROOT / "holo_pet_w3" / "cloud-status" / "cloud-status-data.js"

# 现役地址出处：deploy/cloud-10/README.md:228（「地址 | https://gbt-potato-cloud-10.lopaycn.workers.dev」）
BASE_DEFAULT = "https://gbt-potato-cloud-10.lopaycn.workers.dev"
UA = "gbt-cloud-status/1.0 (+" + BASE_DEFAULT + ")"
TIMEOUT = 3.0          # 单请求超时 3 秒（主人令）
WORKERS = 8            # 并发 8（主人令）

CMD_PROBE = "py -3.14 tools/codex-scripts/cloud-status.py probe"
CMD_RENDER = "py -3.14 tools/codex-scripts/cloud-status.py render"
CMD_CHECK = "py -3.14 tools/codex-scripts/cloud-status.py --check"

S_OK, S_BAD, S_UNK = "通", "不通", "未探测"
C_OK, C_BAD, C_UNK = "#22C55E", "#EF4444", "#6b7280"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ══════════════════════════════════════════════════════════════════════════
# host 校验（发请求前唯一一道闸）—— 只允许公网 http/https，其余一律 blocked、不发
# ══════════════════════════════════════════════════════════════════════════
def host_guard(url: str):
    """返回 (ok: bool, why: str|None, ips: list)。

    ① 协议必须 http/https（file/ftp/gopher… 一律拒）；
    ② 本地名（localhost / *.localhost / *.local / *.internal）拒；
    ③ 字面量 IP 或域名**解析后**的每个地址都不得落回环/私网/链路本地/保留/组播/未指定（防 rebinding）。
    域名解析不出来 ⇒ fail-closed 拒发（无法证明是公网地址就不发）。
    """
    try:
        p = urllib.parse.urlsplit(url)
    except Exception as e:                                              # noqa: BLE001
        return False, "URL 解析不了：%s" % str(e)[:80], []
    if p.scheme not in ("http", "https"):
        return False, "协议不是 http/https：%r" % (p.scheme or "(空)"), []
    host = p.hostname
    if not host:
        return False, "缺主机名", []
    h = host.lower().rstrip(".")
    if (h in ("localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback")
            or h.endswith(".localhost") or h.endswith(".local") or h.endswith(".internal")):
        return False, "本地名（localhost/.local/.internal）：%s" % host, []
    port = p.port or (443 if p.scheme == "https" else 80)
    ips = []
    try:
        ipaddress.ip_address(h)                                         # 字面量 IP：不用 DNS
        ips = [h]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            ips = sorted({i[4][0] for i in infos})
        except Exception as e:                                          # noqa: BLE001
            return False, "域名解析不了（无法证明是公网地址 ⇒ 拒发）：%s" % str(e)[:60], []
        if not ips:
            return False, "域名没解析出任何地址", []
    for a in ips:
        try:
            ip = ipaddress.ip_address(str(a).split("%")[0])
        except ValueError:
            return False, "解析出非法地址 %r" % a, ips
        if ip.is_loopback:
            return False, "回环地址 %s" % ip, ips
        if ip.is_link_local:
            return False, "链路本地地址（169.254/16 等）%s" % ip, ips
        if ip.is_private:
            return False, "私有网段（10/8 · 172.16/12 · 192.168/16 等）%s" % ip, ips
        if ip.is_reserved:
            return False, "保留地址 %s" % ip, ips
        if ip.is_multicast:
            return False, "组播地址 %s" % ip, ips
        if ip.is_unspecified:
            return False, "未指定地址 %s" % ip, ips
    return True, None, ips


# ══════════════════════════════════════════════════════════════════════════
# 真源读取
# ══════════════════════════════════════════════════════════════════════════
def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                                   # noqa: BLE001
        return None


def _probe_op(ops: list, gates: dict) -> str:
    """挑一个**只读口径**的 op 作为该插件的代表路由：优先 status → 其次只读词（stats/query/
    recall/list/budget/scopes/report…）→ 再次任一 gate=none 的 op → 兜底首个 op。"""
    ops = ops or []
    order = ("status", "stats", "query", "recall", "list", "budget", "scopes", "report", "identity")
    for o in order:
        if o in ops:
            return o
    for o in ops:
        if (gates or {}).get(o) == "none":
            return o
    return ops[0] if ops else "status"


def build_plugins(mesh: dict, base: str) -> list:
    """从现役真源（mesh.json）现读 10 个真模块，派生出每位的端点与调用路由。"""
    out = []
    base = base.rstrip("/")
    for m in mesh.get("modules") or []:
        ops = m.get("ops") or []
        gates = m.get("op_gates") or {}
        op = _probe_op(ops, gates)
        out.append({
            "seq": m["seq"],
            "id": m["id"],
            "name": m.get("owner_label") or "",            # 名称 = 主人给的那条 npm 名（逐字照录）
            "duty": m.get("duty") or "",                   # 角色 = 这位于云端干什么
            "ops": ops,                                    # 能力 op
            "gates": gates,                                # 每个 op 的门
            "probe_op": op,
            "cloud": m.get("cloud") or [],
            "boundary": m.get("boundary") or "",
            "local_driver": m.get("local_driver") or "",
            "driver_why": m.get("driver_why") or "",
            "route": "%s/rpc/%s/%s" % (base, m["id"], op),  # 调用路由（POST，需网关鉴权）
            "probe": None,                                  # 由 probe 子命令填；没跑过就是 None ⇒「未探测」
        })
    return out


def blueprint_summary() -> dict:
    """蓝图（plugins50.json）只读注记：现役 10 个 vs 蓝图 50 槽 —— 如实分开，不冒充现役。"""
    d = load_json(SPEC50)
    if not d:
        return {"present": False}
    mods = d.get("modules") or []
    wired = [m for m in mods if (m.get("status") or "") != "reserve"]
    reserve = [m for m in mods if (m.get("status") or "") == "reserve"]
    return {
        "present": True,
        "path": "deploy/cloud-10/plugins50.json",
        "slots": len(mods),
        "wired": len(wired),
        "reserve": len(reserve),
        "groups": [g.get("name") for g in (d.get("groups") or [])],
        "ops": sum(1 for m in mods if m.get("ops")),
        "note": ("50 槽蓝图（%d 指派 + %d 备用）· 未部署 · 无 ops · 无端点 ⇒ **不探测**"
                 % (len(wired), len(reserve))),
    }


# ══════════════════════════════════════════════════════════════════════════
# 探针（真发一次请求）
# ══════════════════════════════════════════════════════════════════════════
def _http_get(url: str) -> dict:
    """一次 GET（如实自报 UA —— 平台侧会挡默认 Python-urllib UA，实测过）。"""
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={"user-agent": UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read().decode("utf-8", "replace")
            ms = int((time.perf_counter() - t0) * 1000)
            body, perr = None, None
            try:
                body = json.loads(raw)
            except Exception as e:                                      # noqa: BLE001
                perr = "回包不是 JSON：%s" % str(e)[:80]
            return {"http": r.status, "ms": ms, "body": body, "raw": raw[:300], "err": perr, "exc": None}
    except urllib.error.HTTPError as e:                                 # 4xx/5xx 是读数，不是异常
        raw = e.read().decode("utf-8", "replace")
        return {"http": e.code, "ms": int((time.perf_counter() - t0) * 1000),
                "body": None, "raw": raw[:300], "err": "HTTP %d" % e.code, "exc": None}
    except Exception as e:                                              # noqa: BLE001
        name = type(e).__name__
        kind = "timeout" if "timeout" in name.lower() else "error"
        return {"http": None, "ms": int((time.perf_counter() - t0) * 1000),
                "body": None, "raw": "", "err": "%s: %s" % (name, str(e)[:120]), "exc": kind}


def judge_probe(pid: str, res: dict) -> dict:
    """把一次 GET 的读数判成三态之一；**失败一律带原始 status/错误串**，不吞、不改写。"""
    at = now()
    base = {"url": None, "method": "GET", "at": at, "ms": res.get("ms"),
            "http": res.get("http"), "ok": None, "state": S_BAD, "kind": None,
            "reason": None, "raw": res.get("raw") or "", "exc": res.get("exc")}
    if res.get("exc") == "timeout":
        base.update(kind="timeout", reason="超时（>%.1fs）：%s" % (TIMEOUT, res.get("err")))
        return base
    if res.get("exc") == "error":
        base.update(kind="error", reason="连接失败：%s" % res.get("err"))
        return base
    http = res.get("http")
    if http != 200:
        raw = (res.get("raw") or "").strip().replace("\n", " ")
        tail = ("原文：" + raw[:140]) if raw else (res.get("err") or "")
        base.update(kind="http", reason="HTTP %s（非 200）%s" % (http, tail))
        return base
    body = res.get("body")
    if not isinstance(body, dict):
        base.update(kind="body", reason="回包不是 JSON 对象：%s" % (res.get("err") or ""))
        base["ok"] = False
        return base
    rows = body.get("rows")
    row = None
    if isinstance(rows, list):
        row = next((r for r in rows if isinstance(r, dict) and r.get("id") == pid), None)
    if row is None:
        base.update(kind="missing", ok=False,
                    reason="HTTP 200 但逐模块表里没有本插件的行（rows 里找不到 %s）" % pid)
        base["raw"] = res.get("raw") or ""
        return base
    base["row"] = row
    if row.get("ok") is True:
        base.update(ok=True, state=S_OK, kind="ok")
    else:
        base.update(ok=False, kind="row",
                    reason="行内 ok=%s reading=%s" % (row.get("ok"), row.get("reading")))
    return base


def cmd_probe(base: str) -> int:
    mesh = load_json(MESH)
    if not mesh:
        print("🔴 现役真源读不到：%s" % MESH)
        return 2
    plugins = build_plugins(mesh, base)

    ok, why, ips = host_guard(base)
    print("=" * 78)
    print("云插件连接状态 · 真探针（%s）" % now())
    print("=" * 78)
    print("  探测基址：%s" % base)
    print("  host 校验：%s  %s" % ("通过" if ok else "🔴 拦下",
                                   ("解析到 %s" % "、".join(ips)) if ok else why))
    print("  超时 %.1fs · 并发 %d · 方法 GET · UA %s" % (TIMEOUT, WORKERS, UA))
    print("-" * 78)

    # 总闸：先探根路由（现役 Worker 的路由索引）
    gateway = None
    if ok:
        gres = _http_get(base.rstrip("/") + "/")
        gateway = {"url": base.rstrip("/") + "/", "method": "GET", "at": now(),
                   "ms": gres.get("ms"), "http": gres.get("http"),
                   "ok": (gres.get("http") == 200), "reason": gres.get("err")}
    else:
        gateway = {"url": base.rstrip("/") + "/", "method": "GET", "at": now(),
                   "ms": None, "http": None, "ok": False,
                   "reason": "host 校验不过，未发请求：%s" % why, "blocked": True}

    probe_url = base.rstrip("/") + "/health"

    def route_read(p):
        """对**该插件自己的调用路由**再真发一次（GET，建议口径）—— 原始读数只留档，
        不拿它定三态（现役形态 A 的调用路由是 POST + 网关鉴权，匿名 GET 本来就不通）。"""
        url = base.rstrip("/") + "/rpc/" + p["id"] + "/" + p["probe_op"]
        res = _http_get(url)
        http = res.get("http")
        return {"url": url, "method": "GET", "at": now(), "ms": res.get("ms"), "http": http,
                "ok": (http == 200), "exc": res.get("exc"),
                "raw": (res.get("raw") or "")[:200],
                "reason": (res.get("err") if http != 200 else None)}

    if not ok:
        for p in plugins:
            p["probe"] = {"url": probe_url, "method": "GET", "at": now(), "ms": None, "http": None,
                          "ok": None, "state": S_BAD, "kind": "blocked", "row": None,
                          "raw": "", "reason": "host 校验不过，未发请求：%s" % why, "blocked": True,
                          "route": {"url": base.rstrip("/") + "/rpc/" + p["id"] + "/" + p["probe_op"],
                                    "method": "GET", "at": now(), "ms": None, "http": None, "ok": False,
                                    "raw": "", "reason": "host 校验不过，未发请求：%s" % why}}
    else:
        # 对**每个**云插件各发一次探活请求：现役形态 A 是 10 模块同一 isolate、同一 URL，
        # 其逐模块探活口是 GET /health；用 `?_probe=<id>` 给每位的请求一个可追溯标识
        # （Worker 返回全表，本方按 id 取本插件那一行）。
        def one(p):
            url = probe_url + "?_probe=" + p["id"]
            r = judge_probe(p["id"], _http_get(url))
            r["url"] = url
            r["route"] = None
            return r

        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            results = list(ex.map(one, plugins))
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            routes = list(ex.map(route_read, plugins))
        for p, r, rt in zip(plugins, results, routes):
            r["route"] = rt
            p["probe"] = r

    # 三态统计
    n_ok = sum(1 for p in plugins if p["probe"]["state"] == S_OK)
    n_bad = sum(1 for p in plugins if p["probe"]["state"] == S_BAD)
    n_unk = sum(1 for p in plugins if p["probe"]["state"] == S_UNK)
    n_to = sum(1 for p in plugins if p["probe"].get("kind") == "timeout")
    n_blk = sum(1 for p in plugins if p["probe"].get("blocked"))
    for p in plugins:
        pr = p["probe"]
        print("  %-28s %-4s %-6s %5sms  http=%s  %s"
              % (p["id"], p["probe_op"], pr["state"], pr["ms"] if pr["ms"] is not None else "-",
                 pr["http"], (pr["reason"] or "")[:70]))

    model = assemble(plugins, base, mesh, gateway)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(model, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-" * 78)
    print("  总数 %d · 通 %d · 不通 %d（其中 超时 %d / 被拦 %d）· 未探测 %d"
          % (len(plugins), n_ok, n_bad, n_to, n_blk, n_unk))
    print("  台账：%s" % STATE)
    print("  下一步：%s  →  %s" % (CMD_RENDER, CMD_CHECK))
    return 0


# ══════════════════════════════════════════════════════════════════════════
# 连接（边）三态 + 模型装配
# ══════════════════════════════════════════════════════════════════════════
def edge_state(sa: str, sb: str) -> str:
    """一条连接（a→b）的三态：任一端不通 ⇒ 不通；任一端未探测（且都不通）⇒ 未探测；两端都通 ⇒ 通。"""
    if sa == S_BAD or sb == S_BAD:
        return S_BAD
    if sa == S_UNK or sb == S_UNK:
        return S_UNK
    return S_OK


def assemble(plugins: list, base: str, mesh: dict, gateway: dict) -> dict:
    edges = []
    for a in plugins:
        for b in plugins:
            if a["seq"] == b["seq"]:
                continue
            sa = (a["probe"] or {}).get("state", S_UNK)
            sb = (b["probe"] or {}).get("state", S_UNK)
            st = edge_state(sa, sb)
            ats = [x for x in ((a["probe"] or {}).get("at"), (b["probe"] or {}).get("at")) if x]
            mss = [x for x in ((a["probe"] or {}).get("ms"), (b["probe"] or {}).get("ms"))
                   if isinstance(x, int)]
            reas = []
            if sa != S_OK and (a["probe"] or {}).get("reason"):
                reas.append("c%02d %s" % (a["seq"], (a["probe"] or {})["reason"]))
            if sb != S_OK and (b["probe"] or {}).get("reason"):
                reas.append("c%02d %s" % (b["seq"], (b["probe"] or {})["reason"]))
            edges.append({"a": a["seq"], "b": b["seq"], "a_id": a["id"], "b_id": b["id"],
                          "state": st, "at": (max(ats) if ats else None),
                          "ms": (max(mss) if mss else None),
                          "reason": ("；".join(reas) if reas else None)})
    n = len(plugins)
    counted = lambda s: sum(1 for p in plugins if (p["probe"] or {}).get("state", S_UNK) == s)  # noqa: E731
    return {
        "generated_at": now(),
        "base": base,
        "form": mesh.get("form"),
        "form_note": mesh.get("form_note"),
        "doctrine": mesh.get("_doctrine") or [],
        "spec_path": "deploy/cloud-10/mesh.json",
        "live_note": ("现役真源 mesh.json（10 真模块 · 云端已部署 Worker · 形态 single-isolate）；"
                      "plugins50.json 是 50 槽蓝图（未部署 · 无端点 ⇒ 不探测）。"),
        "plugins": plugins,
        "edges": edges,
        "gateway": gateway,
        "blueprint": blueprint_summary(),
        "counts": {
            "plugins": n,
            "directed": n * (n - 1),
            "undirected": n * (n - 1) // 2,
            "matrix_cells": n * n,
            "ok": counted(S_OK),
            "bad": counted(S_BAD),
            "unknown": counted(S_UNK),
            "timeout": sum(1 for p in plugins if (p["probe"] or {}).get("kind") == "timeout"),
            "blocked": sum(1 for p in plugins if (p["probe"] or {}).get("blocked")),
        },
        "commands": {"probe": CMD_PROBE, "render": CMD_RENDER, "check": CMD_CHECK},
        "probed": any((p["probe"] or {}).get("at") for p in plugins),
    }


# ══════════════════════════════════════════════════════════════════════════
# 三态合规（**不许假绿**）—— 纯函数，判据与负对照共用
# ══════════════════════════════════════════════════════════════════════════
def tristate_findings(model: dict) -> list:
    out = []
    for p in model.get("plugins") or []:
        pr = p.get("probe")
        st = p.get("state", (pr or {}).get("state", S_UNK))
        tag = "c%02d %s" % (p.get("seq", 0), p.get("id", "?"))
        if st not in (S_OK, S_BAD, S_UNK):
            out.append("%s 三态非法：%r" % (tag, st))
            continue
        if st == S_OK:
            if not pr or pr.get("ok") is not True or pr.get("http") != 200:
                out.append("%s 画成「通」但没有 200+ok=true 的真探测记录（假绿）" % tag)
            elif pr.get("blocked") or pr.get("kind") in ("timeout", "blocked", "error"):
                out.append("%s 画成「通」但探测是 %s（假绿）" % (tag, pr.get("kind")))
        elif st == S_UNK:
            if pr and pr.get("at"):
                out.append("%s 画成「未探测」但探测记录里有 at=%s" % (tag, pr.get("at")))
            if pr and pr.get("ok") is True:
                out.append("%s 画成「未探测」但记录里 ok=true" % tag)
        else:  # 不通
            if not pr:
                out.append("%s 画成「不通」但没有任何探测记录" % tag)
            elif not (pr.get("reason") or "").strip():
                out.append("%s 画成「不通」但**失败原因原文为空**（不许吞原始 status/错误串）" % tag)
    for e in model.get("edges") or []:
        st = e.get("state")
        if st not in (S_OK, S_BAD, S_UNK):
            out.append("连接 c%02d→c%02d 三态非法：%r" % (e.get("a", 0), e.get("b", 0), st))
        if st == S_OK:
            pmap = {p["seq"]: (p.get("probe") or {}).get("state", S_UNK)
                    for p in (model.get("plugins") or [])}
            if pmap.get(e.get("a")) != S_OK or pmap.get(e.get("b")) != S_OK:
                out.append("连接 c%02d→c%02d 画成「通」但端点不全通（假绿）"
                           % (e.get("a", 0), e.get("b", 0)))
    return out


# ══════════════════════════════════════════════════════════════════════════
# 渲染（自包含 · 生成期静态落图 · 数据只走经典脚本）
# ══════════════════════════════════════════════════════════════════════════
_CSS = "<style>\n" + site_root_block() + """
:root{--bg:var(--taste-ground,#0B1120);--pan:var(--taste-surface,#111827);
 --line:var(--taste-border,#1E3A5F);--ink:var(--taste-text,#e8ecf8);--dim:var(--taste-muted,#9aa4c4);
 --ok:var(--taste-positive,#00E5FF);--bad:var(--taste-negative,#EF4444);--off:#6b7280;
 --cy:#22d3ee;--brand-or:var(--taste-accent,#f5b041);--brand-cy:#22d3ee;
 --ok-bg:#0f2a20;--bad-bg:#2a1414;--off-bg:#16181d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.6 "Segoe UI",system-ui,sans-serif}
.gbt-topbar{display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid var(--line);
 /* 2026-10-26：原为 linear-gradient(90deg,#111827,#0d1117) —— 两档微渐变，取中点纯色。 */
 background:#111827;flex-wrap:wrap}
.mark{width:18px;height:18px;border:2px solid var(--brand-or);border-radius:4px}
.brand{font-weight:700;letter-spacing:.5px}.brand b{color:var(--brand-or)}
.note{color:var(--dim);font-size:11.5px}
.wrap{padding:14px;display:grid;gap:14px}
.card{background:var(--pan);border:1px solid var(--line);border-radius:10px;padding:12px}
h2{margin:0 0 8px;font-size:13px;color:var(--dim);font-weight:600;letter-spacing:.4px}
.hr{height:1px;background:var(--line);margin:10px 0}
.mono{font-family:ui-monospace,Consolas,monospace}
.stats{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:8px}
.stat{min-width:96px}.stat b{display:block;font-size:24px;color:var(--brand-cy);font-variant-numeric:tabular-nums}
.stat i{font-style:normal;color:var(--dim);font-size:12px}
.stat b.ok{color:var(--ok)}.stat b.bad{color:var(--bad)}.stat b.off{color:var(--off)}
svg{width:100%;height:auto;display:block}
.node text{fill:var(--ink);font-size:9px;text-anchor:middle;pointer-events:none}
.node .drv{fill:var(--dim);font-size:8px}
.hub circle{fill:#1a1206;stroke:var(--brand-or);stroke-width:2.5}
.hub text{fill:var(--brand-or);font-size:11px;font-weight:700;text-anchor:middle;pointer-events:none}
.arm{stroke:var(--brand-or);stroke-width:1.1;stroke-opacity:.4;fill:none}
table{border-collapse:collapse;width:100%;font-size:11px}
th,td{border:1px solid var(--line);padding:3px 5px;text-align:left;vertical-align:top}
th{color:var(--dim);font-weight:600;background:#111827}
td.cell{text-align:center;font-variant-numeric:tabular-nums}
td.cell.sok{background:var(--ok-bg);color:var(--ok);font-weight:700}
td.cell.sbad{background:var(--bad-bg);color:var(--bad);font-weight:700}
td.cell.sunk{background:var(--off-bg);color:var(--off)}
td.cell.self{background:#0a0e14;color:#1E3A5F}
.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:1px 7px;margin:2px 4px 2px 0;
 color:var(--dim);font-size:11px}
.pill.b{border-color:#1E3A5F;color:var(--brand-cy)}
.pill.ok{border-color:#1d5c45;color:var(--ok)}
.pill.bad{border-color:#6b2a2a;color:var(--bad)}
.pill.off{border-color:#1E3A5F;color:var(--off)}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin:6px 0 2px}
.lg{display:flex;align-items:center;gap:6px;color:var(--dim);font-size:11.5px}
.sw{width:14px;height:14px;border-radius:3px;border:1px solid var(--line);display:inline-block}
.sw.ok{background:var(--ok-bg);border-color:var(--ok)}
.sw.bad{background:var(--bad-bg);border-color:var(--bad)}
.sw.off{background:var(--off-bg);border-color:var(--off)}
.pcard{border:1px solid var(--line);border-radius:8px;padding:10px;margin:0 0 10px;background:#111827}
.pcard:target{border-color:var(--brand-or);box-shadow:0 0 0 1px var(--brand-or) inset}
.pc-h{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px}
.seq{background:#1a1206;color:var(--brand-or);border:1px solid #3a2c10;border-radius:4px;padding:0 6px;font-size:11px}
.pid{color:var(--ink);font-size:13px;font-weight:600}
.pc-r{color:var(--dim);font-size:11.5px;margin:2px 0 8px}
.kv{display:grid;grid-template-columns:96px 1fr;gap:3px 10px;font-size:11.5px}
.kv dt{color:var(--dim)}.kv dd{margin:0;word-break:break-all}
a{color:var(--brand-cy);text-decoration:none}a:hover{text-decoration:underline}
.nav{display:flex;gap:6px;flex-wrap:wrap}
.nav a{border:1px solid var(--line);border-radius:999px;padding:1px 8px;font-size:11px;color:var(--dim)}
.foot{border-top:1px solid var(--line);margin-top:12px;padding:10px 16px;color:var(--dim);font-size:11.5px}
code{font-family:ui-monospace,Consolas,monospace;color:var(--brand-cy)}
@media (prefers-reduced-motion: reduce){*{transition:none!important}}
</style>"""


def _head(title: str, gen: str, page_id: str) -> str:
 # 2026-10-11 补生成标记：本函数产出的页原来**没有标记** ⇒ 逐页新鲜度判据
    #    （tools/codex-scripts/page-bind-check.py）判不出它是生成物还是手写物，
    #    于是「主脑看到的它新不新」**没人能机检**。重建命令写死在这里。
 # 2026-10-26 加 `data-page-id`（主人令「触手覆盖每一页」）：本函数产**两页**，
    #    所以必须由调用方传自己的 id —— 不能写死，否则两页身份会撞在一起，
    #    跨页派活时 from 认不出是谁。`gen` 参数保留（历史签名），值由页脚另给。
    return ('<!doctype html>\n<html data-page-id="%s" lang="zh-CN"><head><meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<!-- 自动生成，别手改。重建：py -3.14 tools/codex-scripts/cloud-status.py render -->\n'
            '<title>%s</title>\n%s</head><body>\n' % (page_id, title, _CSS))


def _topbar(gen: str) -> str:
    return ('<div class="gbt-topbar"><span class="mark"></span>'
            '<span class="brand">GBT<b>小土豆</b>V8</span>'
            '<span class="note">生成 %s ｜ 重生成 <code>%s</code> ｜ 判据 <code>%s</code></span></div>'
            % (gen, CMD_RENDER, CMD_CHECK))


def _foot(gen: str) -> str:
    return ('<div class="foot">生成时刻 <b>%s</b> ｜ 重生成命令 <code>%s</code> ｜ 判据命令 <code>%s</code>'
            '（判据含负对照） ｜ 开发者：自由的风 · GBT小土豆V8</div>'
            % (gen, CMD_RENDER, CMD_CHECK))


def _state_pill(st: str) -> str:
    cls = {S_OK: "ok", S_BAD: "bad", S_UNK: "off"}.get(st, "off")
    return '<span class="pill %s">%s</span>' % (cls, st)


def _ops(ops: list, gates: dict) -> str:
    return "".join('<span class="pill%s">%s · %s</span>'
                   % ("" if (gates or {}).get(o) == "none" else " b", o, (gates or {}).get(o))
                   for o in (ops or []))


def _fmt_ms(v) -> str:
    return ("%s ms" % v) if isinstance(v, int) else "—"


def render_page_a(model: dict) -> str:
    gen = model["generated_at"]
    plugins = model["plugins"]
    base = model["base"]
    n = len(plugins)
    bp = model.get("blueprint") or {}
    cnt = model["counts"]

    nav = "".join('<a href="#c%02d">c%02d</a>' % (p["seq"], p["seq"]) for p in plugins)

    cards = []
    for p in plugins:
        others = [q for q in plugins if q["seq"] != p["seq"]]
        binds = " · ".join('<a href="#c%02d">c%02d %s</a>' % (q["seq"], q["seq"], q["id"]) for q in others)
        st = (p["probe"] or {}).get("state", S_UNK)
        pr = p["probe"] or {}
        rt = pr.get("route") or {}
        rt_http = str(rt.get("http")) if rt.get("http") is not None else "—（未探测）"
        rt_detail = re.sub(r"\s+", " ", (rt.get("raw") or rt.get("reason") or "—")).strip()[:160]
        cards.append(
            '<section class="pcard" id="c%02d">'
            '<div class="pc-h"><span class="seq">c%02d</span><span class="pid mono">%s</span>%s</div>'
            '<div class="pc-r">角色：%s</div>'
            '<dl class="kv">'
            '<dt>id</dt><dd class="mono">%s</dd>'
            '<dt>名称</dt><dd>%s <span class="note">（主人给的 npm 名 · 逐字照录）</span></dd>'
            '<dt>角色</dt><dd>%s</dd>'
            '<dt>端点</dt><dd class="mono">%s</dd>'
            '<dt>探活请求</dt><dd class="mono">%s</dd>'
            '<dt>能力 op</dt><dd>%s</dd>'
            '<dt>云资源</dt><dd>%s</dd>'
            '<dt>本机驱动</dt><dd><span class="mono">%s</span> <span class="note">%s</span></dd>'
            '<dt>与谁互绑</dt><dd>其余 %d 位双向互绑：%s</dd>'
            '<dt>边界</dt><dd class="note">%s</dd>'
            '</dl>'
            '<div class="hr"></div>'
            '<div class="note">当前连接状态（探于 %s · 延迟 %s）：%s%s</div>'
            '<div class="note">路由探测（该插件调用路由 · 匿名 GET 原始读数）：HTTP %s ｜ %s</div>'
            '</section>'
            % (p["seq"], p["seq"], p["id"], _state_pill(st), p["duty"], p["id"], p["name"], p["duty"],
               p["route"], (pr.get("url") or "%s/health（未探测）" % base),
               _ops(p["ops"], p["gates"]), "、".join(p["cloud"]),
               p["local_driver"], p["driver_why"], len(others), binds, p["boundary"],
               pr.get("at") or "未探测", _fmt_ms(pr.get("ms")), _state_pill(st),
               (' ｜ 失败原文：<span class="mono">%s</span>' % pr["reason"]) if pr.get("reason") else "",
               rt_http, '<span class="mono">%s</span>' % rt_detail))

    bpblock = ""
    if bp.get("present"):
        bpblock = ('<div class="note">另册 · 50 槽蓝图（<code>%s</code>）：%d 槽 = %d 指派 + %d 备用 · '
                   '%d 个带 op · 分组 %s。%s'
                   '<br>**现役 vs 蓝图**：本页卡片只列**现役真源** <code>%s</code> 的 %d 个真模块'
                   '（云端已部署 Worker 里真在跑的那 10 个）；50 槽蓝图**未部署 · 无端点**，不冒充现役、不探测。</div>'
                   % (bp.get("path"), bp.get("slots"), bp.get("wired"), bp.get("reserve"), bp.get("ops"),
                      "、".join(bp.get("groups") or []), bp.get("note"),
                      "deploy/cloud-10/mesh.json", n))
    else:
        bpblock = '<div class="note">蓝图件读不到（不影响现役 10 位）。</div>'

    body = (
        '<div class="wrap">'
        '<div class="card"><h2>// 01 — 云插件索引（每位都有锚点，点号直达）</h2>'
        '<div class="stats">'
        '<div class="stat"><b>%d</b><i>云插件（现役）</i></div>'
        '<div class="stat"><b>%d</b><i>有向连接点</i></div>'
        '<div class="stat"><b class="ok">%d</b><i>通</i></div>'
        '<div class="stat"><b class="bad">%d</b><i>不通</i></div>'
        '<div class="stat"><b class="off">%d</b><i>未探测</i></div>'
        '</div>'
        '<div class="nav">%s</div>'
        '<div class="hr"></div>%s'
        '<div class="note">形态：<code>%s</code> · 探测基址 <code>%s</code></div>'
        '</div>'
        '<div class="card"><h2>// 02 — 逐插件卡片（id / 名称 / 角色 / 端点 / 能力 op / 与谁互绑）</h2>%s</div>'
        '</div>%s'
        % (n, cnt["directed"], cnt["ok"], cnt["bad"], cnt["unknown"], nav, bpblock,
           model.get("form") or "single-isolate", base, "".join(cards), _foot(gen))
    )
    script = ('<script src="cloud-plugins-data.js"></script>\n'
              '<script>\n'
              '/* 经典脚本（非 module）：数据来自 cloud-plugins-data.js，本页零远端请求。*/\n'
              'var D = globalThis.GBT_CLOUD_PLUGINS || {plugins: []};\n'
              'document.querySelectorAll(".nav a").forEach(function(a){\n'
              '  a.addEventListener("click", function(){ a.blur(); });\n'
              '});\n'
              '</script>\n')
    return (_head("GBT小土豆V8 · 云插件独立页（每位一张卡片 · 带锚点）", gen, "cloud-plugins")
            + _topbar(gen) + body + script
            # 触手网格接管器（主人令 2026-10-26）：相对路径、非远端 ⇒ 仍满足"零远端请求"。
            + '<script src="../shell/tentacle-kit.js" defer></script>\n'
            + '</body></html>\n')


def render_page_b(model: dict) -> str:
    import math
    gen = model["generated_at"]
    plugins = model["plugins"]
    edges = model["edges"]
    base = model["base"]
    cnt = model["counts"]
    n = len(plugins)
    pmap = {p["seq"]: p for p in plugins}

    # ① 环形拓扑（生成期静态落图；节点/连线按三态着色）
    CX, CY, R, ARM = 450.0, 310.0, 235.0, 92.0
    pos = {}
    for i, p in enumerate(plugins):
        a = -math.pi / 2 + i * 2 * math.pi / n
        pos[p["seq"]] = (CX + R * math.cos(a), CY + R * math.sin(a))
    ring = []
    for i, a in enumerate(plugins):
        for b in plugins[i + 1:]:
            x1, y1 = pos[a["seq"]]
            x2, y2 = pos[b["seq"]]
            st = edge_state((a["probe"] or {}).get("state", S_UNK), (b["probe"] or {}).get("state", S_UNK))
            col = {S_OK: C_OK, S_BAD: C_BAD, S_UNK: C_UNK}[st]
            ring.append("<line class='clink' id='lnk-%d-%d' data-a='%d' data-b='%d' x1='%.1f' y1='%.1f' "
                        "x2='%.1f' y2='%.1f' stroke='%s' stroke-width='%.2f' stroke-opacity='%.2f'/>"
                        % (a["seq"], b["seq"], a["seq"], b["seq"], x1, y1, x2, y2, col,
                           1.6 if st == S_OK else (1.3 if st == S_BAD else 0.6),
                           0.55 if st == S_OK else (0.75 if st == S_BAD else 0.3)))
    ring.append("<g class='node hub'><circle cx='%.1f' cy='%.1f' r='30'/><text x='%.1f' y='%.1f'>GBT</text>"
                "<text x='%.1f' y='%.1f'>触手</text></g>" % (CX, CY, CX, CY - 2, CX, CY + 11))
    for p in plugins:
        x, y = pos[p["seq"]]
        a = math.atan2(y - CY, x - CX)
        st = (p["probe"] or {}).get("state", S_UNK)
        col = {S_OK: C_OK, S_BAD: C_BAD, S_UNK: C_UNK}[st]
        fill = {S_OK: "--ok-bg", S_BAD: "--bad-bg", S_UNK: "--off-bg"}[st]
        ring.append("<line class='arm' data-seq='%d' x1='%.1f' y1='%.1f' x2='%.1f' y2='%.1f'/>"
                    % (p["seq"], CX + ARM * math.cos(a), CY + ARM * math.sin(a),
                       x - math.cos(a) * 16, y - math.sin(a) * 16))
        ring.append("<g class='node' id='nd-%d' data-seq='%d'><circle cx='%.1f' cy='%.1f' r='15' "
                    "fill='var(%s)' stroke='%s' stroke-width='2'/><text x='%.1f' y='%.1f'>c%02d</text>"
                    "<text class='drv' x='%.1f' y='%.1f'>%s</text></g>"
                    % (p["seq"], p["seq"], x, y, fill, col, x, y + 1, p["seq"], x, y + 11, st))
    ring_svg = ("<svg viewBox='0 0 900 620' role='img' aria-label='云插件连接状态环形拓扑'>%s</svg>"
                % "".join(ring))

    # ② 连接矩阵（N×N，每格 = 一条有向连接；按三态着色）
    cell_state = {}
    for e in edges:
        cell_state[(e["a"], e["b"])] = e["state"]
    rows = ["<table><thead><tr><th>from\\to</th>"]
    rows += ["<th>c%02d</th>" % p["seq"] for p in plugins]
    rows.append("</tr></thead><tbody>")
    for a in plugins:
        rows.append("<tr><th>c%02d %s</th>" % (a["seq"], a["duty"][:10]))
        for b in plugins:
            if a["seq"] == b["seq"]:
                rows.append("<td class='cell self' data-a='%d' data-b='%d'>—</td>" % (a["seq"], b["seq"]))
            else:
                st = cell_state.get((a["seq"], b["seq"]), S_UNK)
                cls = {S_OK: "sok", S_BAD: "sbad", S_UNK: "sunk"}[st]
                rows.append("<td class='cell %s' data-a='%d' data-b='%d' title='%s'>%s</td>"
                            % (cls, a["seq"], b["seq"], st, st))
        rows.append("</tr>")
    rows.append("</tbody></table>")
    matrix = "".join(rows)

    # ③ 逐条连接明细（谁在什么时候探的 / 延迟 / 失败原因原文）
    erows = []
    for e in edges:
        st = e["state"]
        cls = {S_OK: "ok", S_BAD: "bad", S_UNK: "off"}[st]
        erows.append("<tr><td class='mono'>c%02d → c%02d</td><td>%s</td><td class='mono'>%s</td>"
                     "<td>%s</td><td><span class='pill %s'>%s</span></td><td class='note'>%s</td></tr>"
                     % (e["a"], e["b"], e["a_id"] + " → " + e["b_id"],
                        e["at"] or "—", _fmt_ms(e["ms"]), cls, st, e["reason"] or "—"))
    etable = ("<table><thead><tr><th>连接</th><th>端点对</th><th>探于</th><th>延迟</th><th>状态</th>"
              "<th>失败原因原文</th></tr></thead><tbody>%s</tbody></table>" % "".join(erows))

    # ④ 逐插件明细
    prows = []
    for p in plugins:
        pr = p["probe"] or {}
        st = pr.get("state", S_UNK)
        cls = {S_OK: "ok", S_BAD: "bad", S_UNK: "off"}[st]
        rt = pr.get("route") or {}
        rt_txt = (("HTTP %s ｜ %s" % (rt.get("http"), (rt.get("raw") or rt.get("reason") or "—")))
                  if rt.get("http") is not None else "—（未探测）")
        rt_txt = re.sub(r"\s+", " ", rt_txt).strip()[:170]
        prows.append("<tr><td class='mono'>c%02d</td><td class='mono'>%s</td><td>%s</td>"
                     "<td class='mono'>%s</td><td>%s</td><td>%s</td><td><span class='pill %s'>%s</span></td>"
                     "<td class='mono'>%s</td><td class='mono'>%s</td><td class='note'>%s</td>"
                     "<td class='note mono'>%s</td></tr>"
                     % (p["seq"], p["id"], p["duty"][:16], pr.get("url") or "—", pr.get("at") or "—",
                        _fmt_ms(pr.get("ms")), cls, st,
                        (("HTTP %s" % pr["http"]) if pr.get("http") is not None else "—"),
                        pr.get("kind") or "—", pr.get("reason") or "—", rt_txt))
    ptable = ("<table><thead><tr><th>号</th><th>id</th><th>角色</th><th>探活端点</th><th>探于</th><th>延迟</th>"
              "<th>状态</th><th>原始 status</th><th>类别</th><th>失败原因原文</th><th>路由探测(匿名GET)</th>"
              "</tr></thead><tbody>%s</tbody></table>" % "".join(prows))

    gw = model.get("gateway") or {}
    legend = ('<div class="legend">'
              '<span class="lg"><i class="sw ok"></i><b>通</b>：真发过一次请求，HTTP 200 且本插件那一行 ok=true</span>'
              '<span class="lg"><i class="sw bad"></i><b>不通</b>：真发过但失败（HTTP 非 200 / 超时 / 行内 ok=false / 回包缺行）</span>'
              '<span class="lg"><i class="sw off"></i><b>未探测</b>：没跑过 probe（或端点被 host 校验拦下）—— 不许画成通</span>'
              '</div>')

    nostate = ("" if model.get("probed") else
               '<div class="note"><b>本页尚无真探测</b>：state/cloud-status.json 里没有探测记录 ⇒ '
               '一律「未探测」（**不许假绿**）。请先跑 <code>%s</code>。</div>' % CMD_PROBE)

    body = (
        '<div class="wrap">'
        '<div class="card"><h2>// 01 — 探针台账（探测基址 · 三态基数）</h2>'
        '<div class="stats">'
        '<div class="stat"><b>%d</b><i>插件总数</i></div>'
        '<div class="stat"><b class="ok">%d</b><i>通</i></div>'
        '<div class="stat"><b class="bad">%d</b><i>不通</i></div>'
        '<div class="stat"><b>%d</b><i>其中超时</i></div>'
        '<div class="stat"><b>%d</b><i>其中被拦</i></div>'
        '<div class="stat"><b class="off">%d</b><i>未探测</i></div>'
        '</div>'
        '<div class="note">探测基址 <code>%s</code> ｜ 总闸 <code>%s</code> → HTTP %s（%s）｜ '
        '形态 <code>%s</code> ｜ UA <code>%s</code></div>'
        '<div class="hr"></div>%s%s'
        '</div>'
        '<div class="card"><h2>// 02 — 连接拓扑（节点与连线按三态着色）</h2>%s'
        '<div class="note">节点 = 云插件（中为触手）；连线 = 插件间双向互绑，颜色即该连接三态。</div></div>'
        '<div class="card"><h2>// 03 — 连接矩阵（%d×%d · 每格 = 一条有向连接 · 对角=自环不绑）</h2>%s'
        '<div class="note">点格看该连接三态；行 from → 列 to。</div></div>'
        '<div class="card"><h2>// 04 — 逐条连接明细（%d 条 · 探于何时 / 延迟 / 失败原因原文）</h2>%s</div>'
        '<div class="card"><h2>// 05 — 逐插件明细（端点 / 探于何时 / 延迟 / 原始 status / 失败原因原文）</h2>%s'
        '<div class="note">三态由「探活请求」定（现役形态 A：10 插件同一 isolate、同一 URL，'
        '逐模块探活口是 <code>GET /health</code>，按 <code>?_probe=&lt;id&gt;</code> 取本插件那一行）。'
        '末列「路由探测」是对该插件**调用路由** <code>/rpc/&lt;id&gt;/&lt;op&gt;</code> 另发的匿名 GET —— '
        '现役路由是 POST + 网关鉴权，匿名 GET 拿 404 是**真读数**，不当成插件不通。</div></div>'
        '</div>%s'
        % (cnt["plugins"], cnt["ok"], cnt["bad"], cnt["timeout"], cnt["blocked"], cnt["unknown"],
           base, gw.get("url") or "—",
           (gw.get("http") if gw.get("http") is not None else "—"),
           ("通" if gw.get("ok") else ("不通：" + (gw.get("reason") or "")[:48])),
           model.get("form") or "single-isolate", UA, legend, nostate,
           ring_svg, n, n, matrix, cnt["directed"], etable, ptable, _foot(gen))
    )
    script = ('<script src="cloud-status-data.js"></script>\n'
              '<script>\n'
              '/* 经典脚本（非 module）：数据来自 cloud-status-data.js，本页零远端请求。*/\n'
              'var S = globalThis.GBT_CLOUD_STATUS || {edges: []};\n'
              'document.querySelectorAll("td.cell").forEach(function(td){\n'
              '  td.addEventListener("click", function(){\n'
              '    var a = td.getAttribute("data-a"), b = td.getAttribute("data-b");\n'
              '    if (a === b) return;\n'
              '    var lnk = document.getElementById("lnk-" + Math.min(+a,+b) + "-" + Math.max(+a,+b));\n'
              '    document.querySelectorAll("td.cell.hot").forEach(function(x){ x.classList.remove("hot"); });\n'
              '    td.classList.add("hot");\n'
              '  });\n'
              '});\n'
              '</script>\n')
    return (_head("GBT小土豆V8 · 可视化连接状态面板（通 / 不通 / 未探测）", gen, "cloud-status")
            + _topbar(gen) + body + script
            # 触手网格接管器（主人令 2026-10-26）：相对路径、非远端 ⇒ 仍满足"零远端请求"。
            + '<script src="../shell/tentacle-kit.js" defer></script>\n'
            + '</body></html>\n')


def _data_js(global_name: str, payload: dict, rebuild_note: str) -> str:
    return ("/* 自动生成，别手改。重建：\n"
            "   %s\n"
            "   数据来自现役真源 deploy/cloud-10/mesh.json + 探测台账 state/cloud-status.json。*/\n"
            "globalThis.%s = %s;\n"
            % (rebuild_note, global_name,
               json.dumps(payload, ensure_ascii=False, separators=(",", ":"))))


def cmd_render(base_override: str = "") -> int:
    mesh = load_json(MESH)
    if not mesh:
        print("🔴 现役真源读不到：%s" % MESH)
        return 2
    state = load_json(STATE)
    base = base_override or (state or {}).get("base") or BASE_DEFAULT
    plugins = build_plugins(mesh, base)

    if state and state.get("plugins"):
        by_id = {p["id"]: p for p in state["plugins"]}
        for p in plugins:
            p["probe"] = by_id.get(p["id"], {}).get("probe")
    gw = (state or {}).get("gateway") or {
        "url": base.rstrip("/") + "/", "method": "GET", "at": None, "ms": None,
        "http": None, "ok": False, "reason": "未探测（未跑过 probe）"}
    model = assemble(plugins, base, mesh, gw)
    model["rendered_at"] = now()

    PAGE_A.parent.mkdir(parents=True, exist_ok=True)
    PAGE_B.parent.mkdir(parents=True, exist_ok=True)
    PAGE_A.write_text(clean_html(render_page_a(model)), encoding="utf-8")
    PAGE_B.write_text(clean_html(render_page_b(model)), encoding="utf-8")

    data_a = {"generated_at": model["generated_at"], "base": base, "form": model["form"],
              "spec_path": model["spec_path"], "counts": model["counts"],
              "commands": model["commands"], "blueprint": model["blueprint"],
              "plugins": [{"seq": p["seq"], "id": p["id"], "name": p["name"], "duty": p["duty"],
                           "ops": p["ops"], "gates": p["gates"], "route": p["route"],
                           "cloud": p["cloud"], "local_driver": p["local_driver"],
                           "state": (p["probe"] or {}).get("state", S_UNK)} for p in plugins]}
    data_b = {"generated_at": model["generated_at"], "base": base, "form": model["form"],
              "spec_path": model["spec_path"], "counts": model["counts"],
              "commands": model["commands"], "gateway": model["gateway"],
              "probed": model["probed"],
              "plugins": [{"seq": p["seq"], "id": p["id"], "duty": p["duty"], "probe": p["probe"]}
                          for p in plugins],
              "edges": model["edges"]}
    DATA_A.write_text(_data_js("GBT_CLOUD_PLUGINS", data_a, CMD_RENDER), encoding="utf-8")
    DATA_B.write_text(_data_js("GBT_CLOUD_STATUS", data_b, CMD_RENDER), encoding="utf-8")

    c = model["counts"]
    print("云插件独立页：%s" % PAGE_A)
    print("连接状态面板：%s" % PAGE_B)
    print("数据件 A：%s" % DATA_A)
    print("数据件 B：%s" % DATA_B)
    print("插件 %d · 有向连接 %d · 通 %d · 不通 %d · 未探测 %d · 探测=有" % (
        c["plugins"], c["directed"], c["ok"], c["bad"], c["unknown"])
        if model["probed"] else
        "插件 %d · 有向连接 %d · 通 %d · 不通 %d · 未探测 %d · 探测=无（一律未探测）" % (
            c["plugins"], c["directed"], c["ok"], c["bad"], c["unknown"]))
    return 0


# ══════════════════════════════════════════════════════════════════════════
# 判据（≥8 条 · **必须带负对照**：喂假数据/掏空必须报红）
# ══════════════════════════════════════════════════════════════════════════
_EXT_RE = re.compile(r'''(?:src|href)\s*=\s*["'](?:\s*)(?:https?:)?//''', re.I)


def _parse_data_js(text: str, name: str):
    m = re.search(r"globalThis\.%s\s*=\s*(\{.*\})\s*;\s*$" % re.escape(name), text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:                                                   # noqa: BLE001
        return None


def build_artifacts() -> dict:
    return {
        "mesh": load_json(MESH),
        "spec50": load_json(SPEC50),
        "state": load_json(STATE),
        "html_a": PAGE_A.read_text(encoding="utf-8") if PAGE_A.is_file() else "",
        "html_b": PAGE_B.read_text(encoding="utf-8") if PAGE_B.is_file() else "",
        "data_a": DATA_A.read_text(encoding="utf-8") if DATA_A.is_file() else "",
        "data_b": DATA_B.read_text(encoding="utf-8") if DATA_B.is_file() else "",
        "paths": {"page_a": str(PAGE_A), "page_b": str(PAGE_B),
                  "data_a": str(DATA_A), "data_b": str(DATA_B), "state": str(STATE)},
    }


def run_checks(art: dict) -> list:
    """判据本体：只读 art（内存内容），**不碰磁盘** —— 负对照喂改坏的内存副本即可。"""
    rows = []

    def add(cid, ok, detail):
        rows.append({"id": cid, "ok": bool(ok), "detail": detail})

    mesh = art.get("mesh") or {}
    mods = mesh.get("modules") or []
    n = len(mods)
    html_a, html_b = art.get("html_a") or "", art.get("html_b") or ""
    data_a, data_b = art.get("data_a") or "", art.get("data_b") or ""

    # C1 现役真源可读且是真模块
    add("C1 现役真源（mesh.json）可读且为真模块表",
        bool(mesh) and n >= 1 and all(m.get("id") and m.get("ops") for m in mods),
        "模块 %d 个 · 全部带 id+ops：%s" % (n, "是" if all(m.get("id") and m.get("ops") for m in mods) else "否"))

    # C2 现役 vs 蓝图分离（页面必须如实标 plugins50 是蓝图/未部署）
    bp_ok = ("plugins50.json" in html_a and "蓝图" in html_a
             and ("未部署" in html_a or "不探测" in html_a))
    add("C2 现役 vs 蓝图分离（页 A 如实标 50 槽为蓝图·未部署）", bp_ok,
        "页 A 命中 plugins50/蓝图/未部署：" + str(bp_ok))

    # C3 四件在盘
    add("C3 四件在盘（两页 + 两数据件）",
        all([art.get("html_a"), art.get("html_b"), art.get("data_a"), art.get("data_b")]),
        "A/B 页 + A/B 数据件：%s" % [bool(art.get(k)) for k in ("html_a", "html_b", "data_a", "data_b")])

    # C4 零远端引用（外链/CDN/iframe/@import）
    ext = _EXT_RE.findall(html_a) + _EXT_RE.findall(html_b)
    bad4 = []
    if ext:
        bad4.append("外链 %d 处" % len(ext))
    if "cdn" in (html_a + html_b).lower():
        bad4.append("出现 cdn 字样")
    if "<iframe" in (html_a + html_b).lower():
        bad4.append("出现 iframe")
    if re.search(r"@import\s+url\(\s*['\"]?https?:", html_a + html_b, re.I):
        bad4.append("CSS 远端 @import")
    add("C4 页面自包含·零远端引用（外链/CDN/iframe/@import）", not bad4,
        "违规：%s" % (bad4 or "无"))

    # C5 零 fetch/XHR/eval/new Function
    bad5 = []
    if re.search(r"\bfetch\s*\(", html_a + html_b):
        bad5.append("fetch(")
    if "XMLHttpRequest" in html_a + html_b:
        bad5.append("XMLHttpRequest")
    if re.search(r"\beval\s*\(", html_a + html_b):
        bad5.append("eval(")
    if re.search(r"new\s+Function\s*\(", html_a + html_b):
        bad5.append("new Function(")
    add("C5 零远端请求原语（fetch / XHR / eval / new Function）", not bad5,
        "违规：%s" % (bad5 or "无"))

    # C6 数据只走经典脚本
    bad6 = []
    if re.search(r'type\s*=\s*["\']module["\']', html_a + html_b, re.I):
        bad6.append('type="module"')
    if "cloud-plugins-data.js" not in html_a:
        bad6.append("页 A 未引 cloud-plugins-data.js")
    if "cloud-status-data.js" not in html_b:
        bad6.append("页 B 未引 cloud-status-data.js")
    if "import " in html_a + html_b and re.search(r"^\s*import\s", html_a + html_b, re.M):
        bad6.append("ES import")
    add("C6 数据只走经典脚本（无 type=module / 无 import）", not bad6,
        "违规：%s" % (bad6 or "无"))

    # C7 页 A 每插件一张卡片 + 锚点
    anchors = len(re.findall(r'id="c\d{2}"', html_a))
    cards = html_a.count('class="pcard"')
    add("C7 页 A 每位一体：卡片数=锚点数=插件数（%d）" % n,
        anchors == n and cards == n and n >= 1,
        "锚点 %d · 卡片 %d · 插件 %d" % (anchors, cards, n))

    # C8 页 B 三态图例齐全（三词 + 三色）
    leg = all(k in html_b for k in (S_OK, S_BAD, S_UNK)) and all(k in html_b for k in (C_OK, C_BAD, C_UNK))
    add("C8 页 B 三态图例（通/不通/未探测 × 三色，每种颜色含义写明）", leg,
        "三词（通/不通/未探测）+ 三色（%s/%s/%s）：%s" % (C_OK, C_BAD, C_UNK, leg))

    # C9 不许假绿（三态合规 — 判据与负对照同源）
    model = (art.get("state") or {})
    if model.get("plugins"):
        mdl = {"plugins": model["plugins"], "edges": model.get("edges") or []}
    else:
        mdl = {"plugins": [], "edges": []}
    finds = tristate_findings(mdl) if mdl["plugins"] else []
    if not mdl["plugins"]:
        # 没有探测台账不算违规（render 会写全「未探测」），但要检查页面确实标了未探测
        finds = [] if S_UNK in html_b else ["页 B 未标「未探测」"]
    add("C9 不许假绿（未探测不得画成通；通必须 200+ok 记录）", not finds,
        "违规：%s" % ("；".join(finds[:3]) or "无"))

    # C10 失败必带原始 status/错误串
    bad10 = []
    for p in (model.get("plugins") or []):
        st = (p.get("probe") or {}).get("state")
        if st == S_BAD and not ((p.get("probe") or {}).get("reason") or "").strip():
            bad10.append(p.get("id"))
    add("C10 「不通」必带失败原因原文（原始 status/错误串）", not bad10,
        "缺原文：%s" % (bad10 or "无"))

    # C11 页首页脚都有 生成时刻 + 重生成命令 + 判据命令
    def foot_ok(h):
        return (h.count(CMD_RENDER) >= 2 and h.count(CMD_CHECK) >= 2
                and ("生成时刻" in h or "生成 " in h))
    add("C11 两页页首/页脚都写 生成时刻 + 重生成命令 + 判据命令",
        foot_ok(html_a) and foot_ok(html_b),
        "页 A render×%d check×%d · 页 B render×%d check×%d"
        % (html_a.count(CMD_RENDER), html_a.count(CMD_CHECK),
           html_b.count(CMD_RENDER), html_b.count(CMD_CHECK)))

    # C12 数据件与台账一致
    da = _parse_data_js(data_a, "GBT_CLOUD_PLUGINS")
    db = _parse_data_js(data_b, "GBT_CLOUD_STATUS")
    same = (isinstance(da, dict) and isinstance(db, dict)
            and da.get("counts") == db.get("counts")
            and da.get("counts", {}).get("plugins") == n
            and len(db.get("edges") or []) == da.get("counts", {}).get("directed"))
    add("C12 两个数据件可解析且与真源/台账一致", same,
        "A 可解析=%s B 可解析=%s 插件=%s 有向连接=%s"
        % (isinstance(da, dict), isinstance(db, dict),
           (da or {}).get("counts", {}).get("plugins"),
           len((db or {}).get("edges") or [])))
    return rows


def cmd_check(as_json: bool = False) -> int:
    art = build_artifacts()
    rows = run_checks(art)
    negs = []
    art2 = build_artifacts()
    # 「现成模型」：有探测台账就用它；没有（还没跑 probe）就用现役真源现搭一份全「未探测」的，
    # 这样负对照在任何时候都跑得起来，不靠"必须先探过"。
    live_state = dict(art2.get("state") or {})
    if not live_state.get("plugins"):
        syn = build_plugins(art2.get("mesh") or {"modules": []}, BASE_DEFAULT)
        for p in syn:
            p["probe"] = None
        live_state = {"plugins": syn,
                      "edges": assemble(syn, BASE_DEFAULT, art2.get("mesh") or {}, {})["edges"]}

    # ── 负对照 1：掏空（未探测却画成「通」）⇒ C9 必须报红
    if live_state.get("plugins"):
        p0 = json.loads(json.dumps(live_state["plugins"][0]))
        p0["state"] = S_OK
        p0["probe"] = None
        mutant = {"plugins": [p0], "edges": live_state.get("edges") or []}
        f = tristate_findings(mutant)
        negs.append(("掏空：未探测却画成「通」", "C9", bool(f),
                     (f[0] if f else "（本该报红却没报）")))

    # ── 负对照 2：失败原因原文掏空 ⇒ C10 必须报红
    pl = json.loads(json.dumps(live_state.get("plugins") or []))
    if pl:
        pl[0]["probe"] = {"url": "x", "method": "GET", "at": now(), "ms": 1, "http": 500,
                          "ok": False, "state": S_BAD, "kind": "http", "reason": "", "raw": ""}
        art_bad = dict(art2)
        art_bad["state"] = {"plugins": pl, "edges": live_state.get("edges") or []}
        r10 = [r for r in run_checks(art_bad) if r["id"].startswith("C10")]
        negs.append(("喂假数据：不通但失败原因原文为空", "C10",
                     bool(r10 and not r10[0]["ok"]),
                     (r10[0]["detail"] if r10 else "（没跑 C10）")))

    # ── 负对照 3：外链注入 ⇒ C4 必须报红
    art3 = dict(art2)
    art3["html_a"] = art2["html_a"] + '<link rel="stylesheet" href="https://cdn.example.com/x.css">'
    r4 = [r for r in run_checks(art3) if r["id"].startswith("C4")]
    negs.append(("外链注入（https cdn）", "C4", bool(r4 and not r4[0]["ok"]),
                 (r4[0]["detail"] if r4 else "（没跑 C4）")))

    # ── 负对照 4：把数据脚本改成 type=module ⇒ C6 必须报红
    art4 = dict(art2)
    art4["html_b"] = re.sub(r'<script src="cloud-status-data\.js">',
                            '<script type="module" src="cloud-status-data.js">', art2["html_b"])
    r6 = [r for r in run_checks(art4) if r["id"].startswith("C6")]
    negs.append(("喂假数据：数据脚本改 type=module", "C6", bool(r6 and not r6[0]["ok"]),
                 (r6[0]["detail"] if r6 else "（没跑 C6）")))

    # ── 负对照 5：host 守卫（这些一律不许发请求）
    guard_cases = [
        ("http://127.0.0.1:9/x", "回环"),
        ("http://localhost/x", "本地名"),
        ("http://10.1.2.3/", "私有网段 10/8"),
        ("http://172.16.0.9/", "私有网段 172.16/12"),
        ("http://192.168.0.1/", "私有网段 192.168/16"),
        ("http://169.254.169.254/latest/meta-data/", "链路本地/元数据"),
        ("http://[::1]/", "回环 ::1"),
        ("ftp://example.com/x", "非 http/https"),
        ("file:///etc/passwd", "非 http/https"),
        ("http://x.local/x", "本地名 .local"),
    ]
    gbad = [u for u, _ in guard_cases if host_guard(u)[0]]
    pos_ok, pos_why, _ = host_guard(BASE_DEFAULT)
    negs.append(("host 守卫：10 个本机/私网/非法协议端点必须被拦（不发请求）",
                 "GUARD", not gbad and pos_ok,
                 "漏拦：%s ｜ 正控（现役基址）%s %s"
                 % (gbad or "无", "通过" if pos_ok else "🔴被拦", pos_why or "")))

    fails = [r for r in rows if not r["ok"]]
    neg_fail = [x for x in negs if not x[2]]
    if as_json:
        print(json.dumps({"rows": rows, "negatives": [{"name": n, "target": t, "ok": o, "detail": d}
                                                      for n, t, o, d in negs],
                          "pass": len(rows) - len(fails), "fail": len(fails),
                          "neg_pass": len(negs) - len(neg_fail)}, ensure_ascii=False, indent=1))
    else:
        print("=" * 78)
        print("云插件独立页 + 连接状态面板 · 判据（含负对照）")
        print("=" * 78)
        for r in rows:
            print("%s %-46s %s" % ("PASS" if r["ok"] else "FAIL", r["id"], r["detail"]))
        print("-" * 78)
        for nm, tg, ok, det in negs:
            print("%s 负对照[%s] %-40s %s" % ("PASS" if ok else "FAIL", tg, nm[:40], det[:90]))
        print("-" * 78)
        print("判据 PASS %d · FAIL %d ｜ 负对照 PASS %d · FAIL %d"
              % (len(rows) - len(fails), len(fails), len(negs) - len(neg_fail), len(neg_fail)))
    return 1 if (fails or neg_fail) else 0


# ══════════════════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                               # noqa: BLE001
            pass
    base = ""
    if "--base" in argv:
        i = argv.index("--base")
        base = argv[i + 1] if i + 1 < len(argv) else ""
        del argv[i:i + 2]
    if not base:
        import os
        base = os.environ.get("GBT_CLOUD_BASE") or ""
    if not argv or argv[0] == "probe":
        return cmd_probe(base or BASE_DEFAULT)
    if argv[0] == "render":
        return cmd_render(base)
    if argv[0] == "--check" or argv[0] == "check":
        return cmd_check(as_json="--json" in argv)
    print("用法：cloud-status.py [probe [--base URL] | render [--base URL] | --check [--json]]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
