# -*- coding: utf-8 -*-
# gbt-capability: gbt_universal_plug  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""GBT万能插 · 动态接口融合层（没有固定插座 · 有连接点即自动生成接口并插入调用）。

## 主人原话（2026-11-26）
「把能力全部整合融入触手实现真正的万能插能力，改名GBT万能插，
 没有固定插座，只要有接口和连接点他都能自动识别生成接口插入使用调用和操控」

## 这一层补的是什么（不另起炉灶）
现成链路**已有**且复用，本层只补"持久化 + 自动生成接口 + 触手可见"三环：

  ┌───────────── 已有（复用，不改）─────────────┐
  │ tools/omni_adapter.classify()  现场判类        │  ← 识别（纯分析）
  │ tools/omni_adapter.execute()   现场生成适配器  │  ← 生成接口 + 执行
  │ run_task("omni_plug", op=universal)  唯一门    │  ← 执行入口（门照旧）
  │ policy.py omni_plug 分支：现场判类挂作用域     │  ← 安全门（fail-closed）
  │ tentacle/bridge.call_capability() 触手回主门   │  ← 触手调用
  └──────────────────────────────────────────────┘

  ┌───────────── 本层新增（补齐缺口）─────────────┐
  │ ① port 登记：给任意连接点 → classify → 生成     │
  │    接口描述符（ops 签名）→ **落盘持久化**        │  ← "插上去"要持久，不能只在进程里
  │ ② 动态能力位：每个已插 port 暴露 schema/        │
  │    status/invoke，触手能发现并 call_capability   │  ← "融入触手"
  │ ③ 自动识别：autoconnect 扫连接点，能插的都插上   │  ← "自动识别生成接口插入"
  └──────────────────────────────────────────────┘

## 三条纪律（与 omni_plug 逐字同源，绝不放松）
  ① **门照旧**：本层不执行任何真动作，invoke 一律转 run_task("omni_plug")，
     由 policy 现场判类挂作用域；本层绕门 = 开后门，绝不允许。
  ② **落盘不落密**：port 描述符只存 target/类/op 签名；凭据只写环境变量**引用名**，
     绝不回显原文。
  ③ **如实报缺**：认不出的连接点标 unknown、执行器没接的标 not_wired，
     不伪造"插上就能用"。

## op
  schema        接口契约（只读、零作用域）
  plug          登记一个连接点：target→classify→生成接口描述符→落盘
  unplug        拔掉一个连接点
  ports/list    列出所有已插连接点及其接口签名
  describe      看某个连接点的接口描述符
  invoke        **经 run_task("omni_plug")** 调用已插连接点的某个 op（门照旧）
  autoconnect   现场扫可插面，把能识别的都登记上（只登记，不执行）
  verify        判据自检
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_STATE = _ROOT / "state" / "universal_plug"
_PORTS = _STATE / "ports.json"
MAX_PORTS = 64
NAME_RX = __import__("re").compile(r"^[a-z][a-z0-9_]{1,47}$")

# 每个 kind 能暴露的动词（= 自动生成的"接口"）；execute 支持的才列，不列没实现的。
_KIND_OPS = {
    "http": ("get",),
    "tcp": ("probe",),
    "path": ("read", "stat", "view"),
    "dir": ("list", "stat"),
    "bin": ("exec", "stat"),
    "cmd": ("run",),
    "scheme": ("open",),
    "unix": ("connect",),
    "image": ("view",),
    # 🔴 2026-11-26：浏览器接管（CDP）—— 人类级操作要的是**真动作**，不是只读读数。
    #   click/type/scroll 这类会改页面状态 ⇒ 门在 browser_control（下游 policy 判，本层不绕）。
    "browser": ("open", "click", "type", "scroll", "key", "drag", "wait", "script"),
    "mcp": ("call",),   # 🔴 2026-11-26：融入 mcp_bridge 专门通道（转 mcp_call，门照旧）
    "ws": (),           # 认得出，执行器未接 —— 不假装能调
    "remote": (),       # 执行器未接
    "unknown": (),
}
# 执行器未接的种类：如实标，不冒充可用。mcp 已接（转 mcp_bridge），从缺口里移除。
_NOT_WIRED = frozenset({"ws", "remote", "unknown"})


class UniversalPlugError(ValueError):
    pass


def _load() -> dict:
    try:
        d = json.loads(_PORTS.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:                                              # noqa: BLE001
        return {}


def _save(ports: dict) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    tmp = _PORTS.with_suffix(".tmp")
    tmp.write_text(json.dumps(ports, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _PORTS)


def _adapter():
    """现场加载 tools/omni_adapter.py（与 omni_plug.py 同一姿势，不 import 两次真身）。"""
    import importlib.util as _iu
    ap = _iu.spec_from_file_location("_gbt_universal_adapter", _ROOT / "tools" / "omni_adapter.py")
    m = _iu.module_from_spec(ap)                                   # type: ignore[union-attr]
    ap.loader.exec_module(m)                                       # type: ignore[union-attr]
    return m


def _descriptor(name: str, target: str, info: dict) -> dict:
    """由 classify 结果**自动生成接口描述符**（这就是"生成接口"）。"""
    kind = str(info.get("kind") or "unknown")
    ops = list(_KIND_OPS.get(kind, ()))
    return {
        "name": name,
        "target": target,
        "kind": kind,
        "why": str(info.get("why") or "")[:200],
        "ops": ops,                       # 自动生成的可用动词
        "executor": "not_wired" if kind in _NOT_WIRED or not ops else "omni_plug",
        "plugged_at": time.time(),
        "signature": hashlib.sha256((kind + "|" + target).encode("utf-8")).hexdigest()[:12],
    }


def plug(target: str, name: str = "", **opts) -> dict:
    """登记一个连接点：任意 target → 自动识别 → 生成接口 → 落盘。不执行任何动作。"""
    tgt = str(target or "").strip()
    if not tgt:
        raise UniversalPlugError("需要 target（一个连接点：路径 / URL / 命令 / 端点）")
    info = _adapter().classify(tgt)
    ports = _load()
    nm = str(name or "").strip() or ("port_%s" % hashlib.sha256(
        tgt.encode("utf-8")).hexdigest()[:8])
    if not NAME_RX.match(nm):
        raise UniversalPlugError("name 只许小写字母开头 + 小写字母数字_（2..48）")
    if nm in ports and not opts.get("replace"):
        raise UniversalPlugError("连接点 %s 已插（replace=true 可覆盖）" % nm)
    if nm not in ports and len(ports) >= MAX_PORTS:
        raise UniversalPlugError("连接点已满（上限 %d）" % MAX_PORTS)
    d = _descriptor(nm, tgt, info)
    d["options"] = {k: v for k, v in opts.items() if k != "replace"}  # 不存敏感值由调用方自律；见文档
    ports[nm] = d
    _save(ports)
    return {"ok": True, "op": "plug", "port": d,
            "note": "已登记并生成接口（未执行）；真调用走 invoke，门由 omni_plug 现场判"}


def unplug(name: str) -> dict:
    ports = _load()
    nm = str(name or "")
    if nm not in ports:
        return {"ok": False, "error": "no_such_port", "name": nm}
    d = ports.pop(nm)
    _save(ports)
    return {"ok": True, "op": "unplug", "removed": nm, "port": d}


def describe(name: str) -> dict:
    ports = _load()
    d = ports.get(str(name or ""))
    if not d:
        return {"ok": False, "error": "no_such_port", "name": str(name or "")}
    return {"ok": True, "op": "describe", "port": d}


def ports() -> dict:
    ports_d = _load()
    return {"ok": True, "op": "ports", "count": len(ports_d), "max": MAX_PORTS,
            "ports": list(ports_d.values())}


def invoke(name: str, op: str = "", args: dict | None = None) -> dict:
    """调用已插连接点的某个接口 —— **只转交唯一门 omni_plug，本层不执行**。"""
    ports_d = _load()
    nm = str(name or "")
    d = ports_d.get(nm)
    if not d:
        return {"ok": False, "error": "no_such_port", "name": nm}
    verb = str(op or "").strip()
    # 🔴 执行器未接优先判：连执行器都没有，谈不上"动词是否生成"，直接如实报 not_wired
    if d.get("executor") == "not_wired":
        return {"ok": False, "status": "not_wired", "name": nm, "op": verb,
                "evidence": "已识别为 %s，但执行器未接 —— 不冒充成功" % d.get("kind")}
    if not verb:
        verb = d["ops"][0] if d.get("ops") else ""
    if verb and verb not in d.get("ops", ()):
        return {"ok": False, "error": "op_not_generated",
                "name": nm, "op": verb, "available_ops": d.get("ops", []),
                "note": "这个接口生成时没有该动词（不支持），不冒充可调"}
    from .api import run_task
    # 🔴 2026-11-26：MCP 连接点转 mcp_bridge 专门通道（不是通用 execute），门照旧走 process_execute
    if d.get("kind") == "mcp":
        opts = d.get("options") or {}
        server = str(opts.get("server") or "")
        tool = str(opts.get("tool") or verb)
        if not server:
            return {"ok": False, "error": "mcp_missing_server", "name": nm,
                    "evidence": "MCP 连接点需要 options.server（哪个 MCP 服务器），不冒充可调用"}
        r = run_task("mcp_call", {"server": server, "tool": tool,
                                  "arguments": dict(args or {})})
        body = r.get("gbt_result", r) if isinstance(r, dict) else r
        out = dict(body) if isinstance(body, dict) else {"result": body}
        out.setdefault("ok", (body or {}).get("status") == "ok" if isinstance(body, dict) else False)
        out["port"] = nm
        out["gate"] = "mcp_call（process_execute 门，本层不绕门）"
        return out
    # 🔴 唯一出口：转 run_task("omni_plug", op=universal)，门在 policy 现场判类挂作用域
    r = run_task("omni_plug", {"op": "universal", "target": d["target"],
                                "do": verb, "args": dict(args or {})})
    body = r.get("gbt_result", r) if isinstance(r, dict) else r
    out = dict(body) if isinstance(body, dict) else {"result": body}
    out.setdefault("ok", (body or {}).get("status") == "ok" if isinstance(body, dict) else False)
    out["port"] = nm
    out["gate"] = "omni_plug/universal（policy 现场判类，本层不绕门）"
    return out


def autoconnect(targets: list | None = None, deep: bool = False) -> dict:
    """扫连接点，把认得出的都登记上（只登记+生成接口，不执行任何动作）。"""
    if targets is None:
        # 复用 omni_plug.discover 的本机可插面；它返回结构复杂，这里只取 target 形状
        try:
            from . import omni_plug as _OP
            disc = _OP.discover(deep=deep)
            targets = []
            for key, val in (disc or {}).items():
                if isinstance(val, list):
                    for x in val:
                        if isinstance(x, str):
                            targets.append(x)
                        elif isinstance(x, dict) and x.get("target"):
                            targets.append(str(x["target"]))
                elif isinstance(val, str) and key in ("target", "url", "path"):
                    targets.append(val)
        except Exception:                                           # noqa: BLE001
            targets = []
    targets = [str(t) for t in (targets or []) if str(t or "").strip()]
    added, skipped = [], []

    # 🔴 2026-11-26：融入 MCP 生态 —— 把已配置 MCP 服务器的每个 tool 当作动态连接点登记，
    #   这样"整个 MCP 工具生态"自动成为万能插的接口（invoke 转 mcp_call，门照旧）。
    mcp_tools = []
    try:
        from .api import run_task as _rt
        ms = _rt("mcp_servers", {})
        msb = ms.get("gbt_result", ms) if isinstance(ms, dict) else ms
        servers = (msb.get("result") or {}).get("servers") if isinstance(msb, dict) else None
        if isinstance(servers, dict):
            for srv in servers:
                if not srv:
                    continue
                tl = _rt("mcp_tools", {"server": srv})
                tlb = tl.get("gbt_result", tl) if isinstance(tl, dict) else tl
                tools = (tlb.get("result") or {})
                lst = tools.get("tools") if isinstance(tools, dict) else tools
                if isinstance(lst, list):
                    for t in lst:
                        tn = str(t.get("name") if isinstance(t, dict) else t or "")
                        if tn:
                            mcp_tools.append((srv, tn))
    except Exception:                                               # noqa: BLE001
        pass

    for t in targets:
        info = _adapter().classify(t)
        nm = "port_%s" % hashlib.sha256(t.encode("utf-8")).hexdigest()[:8]
        if info.get("kind") in _NOT_WIRED:
            skipped.append({"target": t, "kind": info.get("kind"), "why": "执行器未接，登记但不标可用"})
        try:
            r = plug(t, name=nm, replace=True)
            added.append(r["port"])
        except Exception as e:                                      # noqa: BLE001
            skipped.append({"target": t, "why": "%s: %s" % (type(e).__name__, str(e)[:80])})

    for srv, tool in mcp_tools:
        nm = "mcp_%s" % hashlib.sha256(("%s|%s" % (srv, tool)).encode("utf-8")).hexdigest()[:8]
        try:
            d = _descriptor(nm, "mcp://%s/%s" % (srv, tool), {"kind": "mcp", "why": "MCP 工具 %s.%s" % (srv, tool)})
            d["options"] = {"server": srv, "tool": tool}
            ports_d = _load()
            ports_d[nm] = d
            _save(ports_d)
            added.append(d)
        except Exception as e:                                      # noqa: BLE001
            skipped.append({"target": "%s.%s" % (srv, tool), "why": "%s" % type(e).__name__})

    return {"ok": True, "op": "autoconnect", "scanned": len(targets) + len(mcp_tools),
            "added": len(added), "skipped": skipped, "ports": added,
            "mcp_tools": len(mcp_tools),
            "note": "只登记+生成接口，没有执行；实际调用走 invoke（门照旧）"}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    m = _adapter()
    ck("识别-路径", m.classify("README.md")["kind"] == "path")
    ck("识别-URL", m.classify("https://example.com")["kind"] == "http")
    ck("识别-命令", m.classify("python")["kind"] == "bin")
    ck("接口生成-有 ops", bool(_descriptor("t", "https://x", {"kind": "http"})["ops"]))
    ck("未接执行器如实标", _descriptor("t", "ws://x", {"kind": "ws"})["executor"] == "not_wired")
    ck("schema 有 ops", "ops" in run("schema"))
    ck("ports 只读", run("ports")["ok"] is True)
    try:
        plug("")
        ck("空 target 拒", False)
    except UniversalPlugError:
        ck("空 target 拒", True)
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def run(op: str = "schema", **params):
    op = str(op or "schema").lower()
    if op in ("schema", "契约"):
        return {"ok": True, "name": "gbt_universal_plug", "brand": "GBT万能插",
                "ops": ["schema", "plug", "unplug", "ports", "list", "describe",
                        "invoke", "autoconnect", "verify"],
                "kind_ops": {k: list(v) for k, v in _KIND_OPS.items()},
                "not_wired": sorted(_NOT_WIRED), "max_ports": MAX_PORTS,
                "gate": "所有 invoke 转 run_task('omni_plug')，门由 policy 现场判类"}
    if op in ("plug", "插", "register"):
        return plug(str(params.get("target") or ""), str(params.get("name") or ""),
                    **{k: v for k, v in params.items() if k in ("replace",)})
    if op in ("unplug", "拔"):
        return unplug(str(params.get("name") or ""))
    if op in ("ports", "list", "列表"):
        return ports()
    if op in ("describe", "描述"):
        return describe(str(params.get("name") or ""))
    if op in ("invoke", "call", "调用"):
        # 动词从 verb/do/op 任一取（op 与外层 op 同名会被 api 展开覆盖，优先用 verb/do）
        verb = str(params.get("verb") or params.get("do") or params.get("op") or "")
        return invoke(str(params.get("name") or ""), verb, params.get("args") or {})
    if op in ("autoconnect", "auto", "自动插", "scan"):
        return autoconnect(params.get("targets"), deep=bool(params.get("deep", False)))
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/plug/unplug/ports/describe/invoke/autoconnect/verify）" % op)
