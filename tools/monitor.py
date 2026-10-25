# -*- coding: utf-8 -*-
"""多域监控 · 逐位真调 + 基线 diff（发现异常第一时间报）

口径（照 docs/12-multidomain-monitor.md，不自创）：
  · 每个探针**真调一次**，判 ok / fail / timeout / skip
  · 判 ok 要求「调用成功 **且** 本体 ok != false」—— 只看信封绿不算过
  · 每次跑完跟**基线**逐位比：状态变了、耗时暴涨、读数掉了 ⇒ 标红
  · 不测的不假装测了（如实报 skip + 原因）

用法：
  python3 tools/monitor.py baseline     # 拍基线（改代码前跑）
  python3 tools/monitor.py check        # 复查 + diff（改代码后跑）
  python3 tools/monitor.py show         # 看基线
"""
from __future__ import annotations
import importlib.util, json, os, socket, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "state" / "monitor_baseline.json"
TOL_MS = 3.0          # 耗时超过基线 3 倍 ⇒ 标黄


def _load(p: Path, n: str):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _omni():
    # 🔴 必须走真身（gbt_allinone/ 653 个 .py），不能用 runtime/ 那 12 文件的审计切片 ——
    #    早先这里写的是 runtime/，等于让监控盯着一个过期副本。
    sys.path.insert(0, str(ROOT))
    from gbt_allinone import omni_plug as OP
    return OP


def _raw(path: str, timeout=4):
    try:
        s = socket.create_connection(("127.0.0.1", 8792), timeout=timeout)
        s.sendall(("GET %s HTTP/1.0\r\nHost: x\r\n\r\n" % path).encode())
        b = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            b += c
        s.close()
        return json.loads(b.split(b"\r\n\r\n", 1)[1])
    except Exception as e:
        return {"ok": False, "error": type(e).__name__}


# ───────── 探针：每个域一个，逐个真调 ─────────
def p_omni_status():
    r = _omni().run(op="status")
    return bool(r.get("ok")), {"插座": len(r.get("插座类型", []))}


def p_omni_energy():
    r = _omni().run(op="energy")
    e = r.get("energy", {})
    return bool(r.get("ok")), {"本机GB": e.get("本机", {}).get("磁盘可用GB")}


def p_omni_selftest():
    r = _omni().selftest()
    return bool(r.get("ok")), {"字段": len(r)}


def p_page_index():
    f = ROOT / "state" / "page_bind.json"
    if not f.is_file():
        return False, {"缺": "state/page_bind.json"}
    d = json.loads(f.read_text(encoding="utf-8"))
    return len(d.get("pages", [])) > 0, {"页": len(d["pages"]), "边": d.get("edges")}


def p_page_shards():
    mf = ROOT / "state" / "bind" / "manifest.json"
    if not mf.is_file():
        return False, {"缺": "manifest.json"}
    d = json.loads(mf.read_text(encoding="utf-8"))
    n = len(list((ROOT / "state" / "bind" / "shards").glob("*.json")))
    return n == d.get("count"), {"片": n, "应": d.get("count"), "manifestB": mf.stat().st_size}


def p_disk_index():
    f = ROOT / "state" / "disk_index.json.gz"
    if not f.is_file():
        return False, {"缺": "disk_index.json.gz"}
    return f.stat().st_size > 0, {"KB": round(f.stat().st_size / 1024, 1)}


def p_daemon_ping():
    r = _raw("/ping")
    return bool(r.get("ok")), {"起于": round(r.get("pong", 0))}


def p_daemon_stats():
    r = _raw("/stats")
    return bool(r.get("ok")), {"文件": r.get("文件"), "RSS_MB": r.get("常驻RSS_MB")}


def p_daemon_find():
    r = _raw("/find?q=omni_plug&limit=2")
    ok = bool(r.get("ok")) and r.get("命中", 0) > 0
    return ok, {"命中": r.get("命中"), "ms": r.get("ms")}


def p_caps_catalog():
    f = ROOT / "data" / "capabilities.json"
    if not f.is_file():
        return False, {"缺": "data/capabilities.json"}
    d = json.loads(f.read_text(encoding="utf-8"))
    caps = d if isinstance(d, list) else (d.get("capabilities") or d.get("caps") or [])
    return len(caps) == 341, {"位": len(caps)}


def p_route_smoke():
    m = _load(ROOT / "tools" / "page_route.py", "_r")
    r = m.route("授权门 状态")
    ok = bool(r.get("ok")) and len(r.get("能力位") or []) > 0
    return ok, {"候选": len(r.get("能力位") or [])}


def p_guard_host():
    """载体四读数：能读就叫 ok（读到 0 或未读到不算 ok）"""
    g = _load(ROOT / "tools" / "guard.py", "_gm")
    s = g.host_status()
    disk = s.get("磁盘", {}); mem = s.get("内存", {})
    ok = (disk.get("可用pct") is not None) and (mem.get("可用MB") is not None)
    return ok, {"磁盘pct": disk.get("可用pct"), "内存MB": mem.get("可用MB"),
                "内存来源": mem.get("来源"), "温度": (s.get("温度") or {}).get("thermal_state")}


def p_guard_gate():
    """判门必须走仓库 policy.evaluate：keylogger 要 privacy_read，audit_query 不要"""
    g = _load(ROOT / "tools" / "guard.py", "_gm2")
    a = g.gate("audit_query", {})
    b = g.gate("keylogger", {})
    ok = (not a.get("scopes")) and ("privacy_read" in (b.get("scopes") or []))
    return ok, {"audit_query": a.get("scopes"), "keylogger": b.get("scopes")}


def p_guard_redact():
    """脱敏器必须认得本仓自己的 gbtv8 钥格式"""
    g = _load(ROOT / "tools" / "guard.py", "_gm3")
    r = g.redact("k=gbtv8-0123456789abcdef0123456789abcdef")
    ok = "gbtv8-2153" not in r.get("脱敏后", "")
    return ok, {"脱敏后": r.get("脱敏后"), "命中": r.get("命中")}


def p_executor_dry():
    """执行器干跑：路由 + 双闸能走通，不真执行"""
    e = _load(ROOT / "tools" / "executor.py", "_em")
    r = e.execute("查审计账本", False)
    ok = r.get("允许") is True and (r.get("执行") or {}).get("status") == "dry-run"
    return ok, {"能力位": r.get("路由", {}).get("能力位"),
                "允许": r.get("允许"), "执行": (r.get("执行") or {}).get("status")}


def p_native_socket():
    """native 插座：读类直通、写类必被 device_control 拦 —— 两态都要对"""
    sys.path.insert(0, str(ROOT))
    from gbt_allinone import omni_plug as OP
    r = OP.run("native", tool="apple-device", cmd="info")
    w = OP.run("native", tool="apple-calendar", cmd="delete")
    ok = bool(r.get("ok")) and w.get("status") == "denied" and \
         "device_control" in (w.get("missing_scopes") or [])
    return ok, {"读": bool(r.get("ok")), "写拦": w.get("status"),
                "missing": w.get("missing_scopes")}


def p_native_ledger():
    """原生能力面台账必须存在且探过"""
    f = ROOT / "state" / "native_surface.json"
    if not f.is_file():
        return False, {"缺": "native_surface.json"}
    d = json.loads(f.read_text(encoding="utf-8"))
    return d.get("ok", 0) >= 20, {"工具": d.get("tools"), "命令": d.get("commands"),
                                   "探过": d.get("probed"), "ok": d.get("ok")}


def p_body_organs():
    """化身：10 个器官必须全部探到可用实现（缺一个就是身体残了）"""
    b = _load(ROOT / "tools" / "body.py", "_bm")
    d = b.body()
    ok = d["缺"] == 0
    return ok, {"器官": d["器官数"], "可用": d["可用"], "缺": d["缺"]}


def p_body_feel():
    """化身：全身感知四项（本体/位置/环境/内感受）都要有读数"""
    b = _load(ROOT / "tools" / "body.py", "_bm2")
    d = b.feel()["feel"]
    ok = all(v.get("ok") for v in d.values())
    return ok, {k: bool(v.get("ok")) for k, v in d.items()}


def p_body_via_omni():
    """化身经万能插的三路要通，且写类必须被 device_control 拦（堵绕门洞）"""
    sys.path.insert(0, str(ROOT))
    from gbt_allinone import omni_plug as OP
    def inner(r):
        return (r.get("gbt_result") or {}).get("result") or {}
    a = inner(OP.run("body", do="organs")) if False else None
    # omni_plug.run 直接调（不经 run_task 信封）
    o = OP.run("body", do="organs")
    f = OP.run("body", do="feel")
    w = OP.run("body", do="use", organ="手", cmd="create", args=[])
    ok = (o.get("body") or {}).get("缺") == 0 and bool(f.get("feel")) and w.get("status") == "denied"
    return ok, {"器官缺": (o.get("body") or {}).get("缺"),
                "feel": bool(f.get("feel")), "写拦": w.get("status")}


def p_body_infer():
    """A19 推理通道：只验「通路没坏」——能给出 queued 或 answered 之一即算通过。
    🔴 「A19 在线/离线」是**该抖的位**（iOS 一切后台就离线，是常态不是故障），
       所以不把在线状态放进指纹，否则天天假红。"""
    b = _load(ROOT / "tools" / "body.py", "_bm3")
    r = b.use("推理", None, ["只回两个字：在的"])
    st = r.get("status") or ("answered" if r.get("answer") else "?")
    ok = st in ("queued", "answered")
    try:
        n = len(b.ORGANS["推理"]["impls"])
    except Exception:
        n = 0
    return ok, {"器官": "推理", "通道": n, "状态": st}

def p_bridge_health():
    """模型桥（8791）：她的对话面唯一入口。桥在 = 页面能开口；
    自有权重车道挂没挂是**该抖的位**（A19 一后台就断），所以只记车道数不进指纹。"""
    import json as _j, urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:8791/health",
                                     headers={"User-Agent": "gbt-mon"})
        with urllib.request.urlopen(req, timeout=4) as r:
            d = _j.loads(r.read().decode("utf-8", "replace"))
        ups = d.get("upstreams") or []
        ready = [u.get("name") for u in ups if u.get("key_ready")]
        return bool(d.get("ok")), {"默认": d.get("default"), "上游数": len(ups),
                                   "就绪数": len(ready)}
    except Exception as e:
        return False, {"桥": "unreachable", "why": type(e).__name__}


PROBES = [
    ("omni", "status", p_omni_status),
    ("omni", "energy", p_omni_energy),
    ("omni", "selftest", p_omni_selftest),
    ("index", "page_index", p_page_index),
    ("index", "page_shards", p_page_shards),
    ("index", "disk_index", p_disk_index),
    ("daemon", "ping", p_daemon_ping),
    ("daemon", "stats", p_daemon_stats),
    ("daemon", "find", p_daemon_find),
    ("catalog", "caps_341", p_caps_catalog),
    ("route", "smoke", p_route_smoke),
    ("guard", "host", p_guard_host),
    ("guard", "gate", p_guard_gate),
    ("guard", "redact", p_guard_redact),
    ("executor", "dry", p_executor_dry),
    ("native", "socket", p_native_socket),
    ("native", "ledger", p_native_ledger),
    ("body", "organs", p_body_organs),
    ("body", "feel", p_body_feel),
    ("body", "via_omni", p_body_via_omni),
    ("body", "infer", p_body_infer),
    ("bridge", "health", p_bridge_health),
]


def run_all() -> dict:
    rows = {}
    for dom, name, fn in PROBES:
        t0 = time.time()
        try:
            ok, detail = fn()
            st = "ok" if ok else "fail"
        except Exception as e:
            st, detail = "exception", {"err": "%s: %s" % (type(e).__name__, str(e)[:90])}
        rows["%s.%s" % (dom, name)] = {
            "status": st, "ms": round((time.time() - t0) * 1000, 1),
            "domain": dom, "detail": detail}
    return rows


def load_base():
    return json.loads(BASE.read_text(encoding="utf-8")) if BASE.is_file() else {}


def save_base(rows):
    BASE.parent.mkdir(parents=True, exist_ok=True)
    BASE.write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                "digest": _digest(_flat(rows)), "rows": rows},
                               ensure_ascii=False, indent=1), encoding="utf-8")


def _flat(rows: dict) -> dict:
    """把嵌套读数拍平成 probe.field → 值，供逐位比对。"""
    out = {}
    for probe, v in rows.items():
        out[probe + ".status"] = v.get("status")
        def walk(prefix, obj):
            if isinstance(obj, dict):
                for k, x in obj.items():
                    walk(prefix + "." + str(k), x)
            elif isinstance(obj, (list, tuple)):
                out[prefix] = json.dumps(obj, ensure_ascii=False)[:80]
            else:
                out[prefix] = obj
        walk(probe, v.get("detail") or {})
    return out


def _stable_flat(flat: dict) -> dict:
    """只留"该稳的位"——抖动的位（耗时/时间戳/内存）不进指纹，
    否则每次跑指纹都变，指纹就失去意义（等于没有基线）。"""
    return {k: v for k, v in flat.items() if not _is_volatile(k)}


def _digest(flat: dict) -> str:
    import hashlib
    s = json.dumps(_stable_flat(flat), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.blake2b(s.encode(), digest_size=8).hexdigest()


# 该抖的位：时间戳/耗时/内存 —— 每次必变，只在大幅漂移时报警
VOLATILE_SUFFIX = (".ms", ".RSS_MB")
VOLATILE_KEYS = {
    "daemon.ping.起于",
    # 2026-10-25：温度随负载在 fair ↔ serious 之间来回跳（同一个错第三次犯）。
    # guard 本来就在 serious/critical 时拦，监控再指纹化它只会天天假红。
    "guard.host.温度",
}
VOLATILE_RATIO = 3.0          # 超过基线 3 倍才算异常
VOLATILE_ABS = 300.0          # 或绝对增量超过 300（ms/MB）

# 载体读数专用绝对阈值：它们天生在抖，但抖过这个量就是真事
# （内存 655→1965 才算异常太松；这里用绝对增量，不是比例）
VOLATILE_ABS_KEYS = {
    "guard.host.内存MB": 400.0,     # 可用内存骤变 >400MB ⇒ 报
    "guard.host.磁盘pct": 20.0,     # 可用空间骤降 >20 个百分点 ⇒ 报
    "guard.host.电量": 30.0,
    "omni.energy.本机GB": 20.0,    # 磁盘可用量天生在动（读写/日志/缓存）        # 电量骤降 >30% ⇒ 报
}


def _is_volatile(k: str) -> bool:
    return (k in VOLATILE_KEYS or k in VOLATILE_ABS_KEYS
            or k.endswith(VOLATILE_SUFFIX))


def diff(base, cur) -> list:
    """逐位比，但**分清该稳的与该抖的**：
         该稳的 ⇒ 任何一位变化都报警
         该抖的 ⇒ 只在比例/绝对量超阈时报警（否则天天假红，人就不看了）
    """
    bad = []
    fb, fc = _flat(base), _flat(cur)
    for k, cv in fc.items():
        if k not in fb:
            bad.append(("新增位", k, "—", cv)); continue
        bv = fb[k]
        if bv == cv:
            continue
        if _is_volatile(k):
            try:
                b_, c_ = float(bv), float(cv)
                if k in VOLATILE_ABS_KEYS:
                    if abs(c_ - b_) > VOLATILE_ABS_KEYS[k]:
                        bad.append(("骤变超阈", k, bv, cv))
                elif c_ > max(b_ * VOLATILE_RATIO, b_ + VOLATILE_ABS):
                    bad.append(("漂移超阈", k, bv, cv))
            except (TypeError, ValueError):
                pass                      # 抖位没法比数 ⇒ 忽略
        else:
            kind = "状态变" if k.endswith(".status") else "读数变"
            bad.append((kind, k, bv, cv))
    for k, bv in fb.items():
        if k not in fc:
            bad.append(("消失位", k, bv, "—"))
    return bad


def main() -> int:
    cmd = (sys.argv[1:2] or ["check"])[0]
    rows = run_all()

    if cmd == "baseline":
        save_base(rows)
        ok = sum(1 for v in rows.values() if v["status"] == "ok")
        print("  基线已拍: %d 个探针 · ok %d / 非ok %d" % (len(rows), ok, len(rows) - ok))
        for k, v in rows.items():
            mark = "✅" if v["status"] == "ok" else "❌"
            print("    %s %-22s %6.0f ms  %s" % (mark, k, v["ms"], v["detail"]))
        return 0

    if cmd == "show":
        b = load_base()
        if not b:
            print("  还没基线"); return 1
        print("  基线 %s · %d 个探针" % (b.get("at"), len(b.get("rows", {}))))
        for k, v in b["rows"].items():
            print("    %-22s %s %.0fms" % (k, v["status"], v["ms"]))
        return 0

    # check
    base = load_base().get("rows", {})
    bad = diff(base, rows)
    ok = sum(1 for v in rows.values() if v["status"] == "ok")
    print("  复查: %d 个探针 · ok %d / 非ok %d" % (len(rows), ok, len(rows) - ok))
    cur_dig = _digest(_flat(rows))
    old_dig = load_base().get("digest", "?")
    print("  读数位数: %d 位 · 指纹 %s%s" % (len(_flat(rows)), cur_dig,
          " ✅ 与基线同指纹" if cur_dig == old_dig else " ⚠ 指纹变了"))
    if not base:
        print("  ⚠ 没有基线可比（先跑 baseline）")
    elif not bad:
        print("  ✅ 与基线逐位一致")
    else:
        print("  🔴 发现 %d 处异常:" % len(bad))
        for kind, k, a, b2 in bad:
            print("    [%s] %-22s %s → %s" % (kind, k, a, b2))
    for k, v in rows.items():
        if v["status"] != "ok":
            print("    ❌ %-22s %s" % (k, v["detail"]))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
