# -*- coding: utf-8 -*-
"""主执行器 v2 · 路由 → 双闸 → 隔离执行 → 结构化回执

v2 相对 v1 的三处改动（都是这轮验出来的）：
  ① **过门换成仓库真源**：`policy.evaluate(kind,payload)` 判作用域票，
     不再自己维护名单（v1 的名单是抄的，抄就会抄错）。
  ② **加载体闸**：`guard.host_vet()` 判磁盘/内存/电量/温度 ——
     仓库存量里没有这一层，但"跑她的这台手机"必须保护。
  ③ **执行改隔离进程 + 硬超时**：v1 直接调 run_task，实测 `redteam_recon`
     会把调用方一起拖死（900 秒无返回）。现在子进程跑，超时就杀，回执如实写 timeout。

双闸的语义：**两扇门都开才执行**；任一扇关就 denied，并把两扇门的读数一起带回来。

用法：
  python3 tools/executor.py "任务描述"            # 干跑（只路由 + 双闸判定）
  python3 tools/executor.py "任务描述" --run      # 真执行（隔离进程，--timeout 60）
  python3 tools/executor.py "任务描述" --run --json
"""
from __future__ import annotations
import argparse, importlib.util, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _mod(path: Path, name: str):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _guard():
    return _mod(ROOT / "tools" / "guard.py", "_gbt_guard")


def _route(text: str) -> dict:
    return _mod(ROOT / "tools" / "page_route.py", "_gbt_route").route(text)


def _action_kind(cap: dict) -> str:
    """把能力位映射成载体动作类型（决定查哪几条载体阈值）。"""
    if cap is None:
        return "read"
    if bool(cap.get("readonly", cap.get("read_only", False))):
        return "read"
    dom = str(cap.get("domain") or "")
    if dom in ("video", "pipeline", "engine", "llm"):
        return "long"
    return "write"


def _run_isolated(kind: str, payload: dict, timeout: float) -> dict:
    """子进程跑 run_task：超时就杀，绝不让一个卡死的位拖死执行器。"""
    code = (
        "import sys,json;sys.path.insert(0,%r);"
        "from gbt_allinone import run_task;"
        "print(json.dumps(run_task(%r,%r,safe=True),ensure_ascii=False,default=str))"
        % (str(ROOT), kind, payload)
    )
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "ok": False,
                "why": "超过 %.0fs 未返回（已杀），该位可能在做长任务" % timeout,
                "elapsed_ms": round((time.time() - t0) * 1000)}
    out = (p.stdout or "").strip().splitlines()
    if not out:
        return {"status": "exception", "ok": False,
                "why": (p.stderr or "")[-200:] or "无输出",
                "elapsed_ms": round((time.time() - t0) * 1000)}
    try:
        env = json.loads(out[-1])
    except Exception:
        return {"status": "unparsable", "ok": False, "raw": out[-1][:200],
                "elapsed_ms": round((time.time() - t0) * 1000)}
    # 信封层级：{gbt_stamp, gbt_result:{status,kind,result:{...}}} ⇒ 必须钻到最内层，
    # 否则 denied 会被外层的 status=ok 盖住（实测栽过：写了一层就停）。
    x = env
    for _ in range(6):
        if not isinstance(x, dict):
            break
        if isinstance(x.get("gbt_result"), dict):
            x = x["gbt_result"]; continue
        if isinstance(x.get("result"), dict) and len(x) <= 6:
            x = x["result"]; continue
        break
    return {"status": x.get("status") or ("ok" if x.get("ok") else "fail"),
            "ok": bool(x.get("ok")),
            "denied": bool(x.get("denied")),
            "missing_scopes": x.get("missing_scopes") or x.get("missing"),
            "how_to_grant": x.get("how_to_grant"),
            "result_digest": json.dumps(x, ensure_ascii=False, default=str)[:180],
            "elapsed_ms": round((time.time() - t0) * 1000)}


def execute(text: str, do_run: bool = False, timeout: float = 60.0) -> dict:
    t0 = time.time()
    G = _guard()

    r = _route(text)
    cap_name = (r.get("能力位") or [{}])[0].get("cap", "")
    caps = _mod(ROOT / "tools" / "guard.py", "_g").__dict__  # 占位，下面直接用 catalog
    # 取能力位本体
    cat = json.loads((ROOT / "data" / "capabilities.json").read_text(encoding="utf-8"))
    cl = cat if isinstance(cat, list) else (cat.get("capabilities") or cat.get("caps") or [])
    cap = next((c for c in cl if c.get("name") == cap_name), None)

    nat = (r.get("原生") or [])
    B = _mod(ROOT / "tools" / "body.py", "_gbt_body")

    # 🔴 一级路由：**器官先认领**（主人口径「设备即肉身」）。
    #   先问"这是哪个器官的事"，再问"用哪根实现" —— 不再靠工具名反查。
    org = B.route_organ(text)
    organ = None
    use_native = False
    if org and (not cap_name or org[0]["score"] >= 1):
        o0 = org[0]
        if o0.get("organ_ready"):
            organ = {"organ": o0["organ"], "cn": o0.get("cn"), "cmd": o0.get("cmd")}
            use_native = True
    # 器官没认领 ⇒ 退回原生直连（更细的命令，如 maps search）
    if not organ and nat and (not cap_name or nat[0].get("score", 0) >= 1):
        oi = B.organ_for(nat[0]["tool"], nat[0].get("cmd") or None)
        if oi.get("organ") and oi.get("in_body"):
            organ = {"organ": oi["organ"], "cn": oi.get("cn"), "cmd": nat[0].get("cmd") or ""}
        use_native = True
    g1 = G.gate(cap_name, {}) if (cap_name and not use_native) else (
        {"risk": "native", "scopes": [], "need_ticket": False,
         "why": "原生插座自带门：读通写拦（device_control）"} if use_native
        else {"risk": None, "scopes": [], "need_ticket": False, "why": "路由无命中"})
    if use_native:
        _W = ("create","update","delete","set","schedule","cancel","play","pause","resume",
              "seek","stop","export","import","add","favorite","trigger","connect",
              "disconnect","write","notify","complete","remind","scan")
        _n0c = (nat[0].get("cmd") if nat else "") or organ.get("cmd") or ""
        _ak = "write" if any(str(_n0c).startswith(w) for w in _W) else "read"
    else:
        _ak = _action_kind(cap)
    g2 = G.host_vet(_ak)

    allow = (not g1.get("scopes")) and g2.get("allow", False)
    out = {
        "问": text,
        "路由": {"能力位": cap_name or "（无命中）",
                 "候选数": len(r.get("能力位") or []),
                 "代码页": (r.get("代码页") or [])[:3],
                 "器官": (organ or {}).get("organ"),
                 "原生": nat,
                 "按需激活": r.get("按需激活")},
        "闸①作用域": g1,
        "闸②载体": g2,
        "允许": allow,
        "执行": None,
        "ms": None,
    }

    if not allow:
        why = []
        if g1.get("scopes"):
            why.append("缺作用域票: %s" % ",".join(g1["scopes"]))
        if not g2.get("allow"):
            why.append(g2.get("why") or "载体资源不足")
        out["执行"] = {"status": "denied", "ok": False, "why": " · ".join(why)}
        out["ms"] = round((time.time() - t0) * 1000, 1)
        G.audit("executor.denied", task=text[:80], cap=cap_name,
                scopes=g1.get("scopes"), host=g2.get("why"))
        return out

    if not do_run:
        out["执行"] = {"status": "dry-run", "ok": True,
                       "would": (
                           ("omni_plug op=body do=use organ=%s" % organ["organ"])
                           if (use_native and organ)
                           else (nat[0]["how"] if nat else "run_task(%r, {})" % cap_name))}
        out["ms"] = round((time.time() - t0) * 1000, 1)
        return out

    if use_native and organ:
        n0 = nat[0] if nat else {}
        _cmd = (n0.get("cmd") or organ.get("cmd") or "")
        res = _run_isolated("omni_plug", {"op": "body", "do": "use",
                                          "organ": organ["organ"],
                                          "cmd": _cmd, "args": []}, timeout)
    elif use_native:
        n0 = nat[0]
        res = _run_isolated("omni_plug", {"op": "native", "tool": n0["tool"],
                                          "cmd": n0["cmd"], "args": []}, timeout)
    else:
        res = _run_isolated(cap_name, {}, timeout)
    out["执行"] = res
    out["ms"] = round((time.time() - t0) * 1000, 1)
    G.audit("executor.run", task=text[:80], cap=cap_name,
            status=res.get("status"), elapsed_ms=res.get("elapsed_ms"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", nargs="+")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--timeout", type=float, default=60.0)
    a = ap.parse_args()
    out = execute(" ".join(a.task), a.run, a.timeout)

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0 if out.get("执行", {}).get("ok") else 1

    print("问: %s" % out["问"])
    rd = out["路由"]
    print("\n① 路由（索引直达）")
    print("   能力位: %s（候选 %d）" % (rd["能力位"], rd["候选数"]))
    if rd.get("器官"):
        print("     器官: %s（走身体，不直连桥）" % rd["器官"])
    for n in (rd.get("原生") or []):
        print("     原生: %s %s（score %d）" % (n.get("tool"), n.get("cmd") or "-", n.get("score")))
    for p in rd["代码页"]:
        print("     页: [%d跳] %s" % (p.get("hops", 0), p.get("page")))
    pa = rd["按需激活"] or {}
    print("   按需激活: 读 %s 字节 · 加载 %s/%s 片"
          % (pa.get("读了字节"), pa.get("加载分片"), pa.get("总页数")))

    g1, g2 = out["闸①作用域"], out["闸②载体"]
    print("\n② 双闸")
    print("   闸①作用域: risk=%s scopes=%s" % (g1.get("risk"), g1.get("scopes") or "[]"))
    for h in (g1.get("how_to_grant") or []):
        print("      → %s" % h)
    print("   闸②载体  : %s" % ("✅ " + str(g2.get("读数")) if g2.get("allow")
                                else "⛔ " + str(g2.get("why"))))

    ex = out["执行"] or {}
    print("\n③ 执行: %s" % ex.get("status"))
    for k in ("why", "would", "result_digest", "elapsed_ms"):
        if ex.get(k):
            print("   %s: %s" % (k, str(ex[k])[:150]))
    print("\n总耗时: %s ms" % out["ms"])
    return 0 if ex.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
