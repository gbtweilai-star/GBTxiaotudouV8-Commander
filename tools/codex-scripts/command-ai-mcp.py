# -*- coding: utf-8 -*-
"""command-ai-mcp · 把她包成 MCP server（stdio JSON-RPC，纯标准库）。

纪律：**每个工具都代理到 gbt_allinone.api.run_task（唯一门）** —— 权限门/审计/钢印照旧，
     MCP 面**不是旁路**；本件不加算力、不装外部包。

v2 改造（2026-11-05，为省 token）：
  旧版只有 gbt_cap(kind, payload)，**不告诉调用方 kind 有哪些合法值**，
  于是 agent 只能逐个盲猜（tool_list / capabilities / wf_run / fs_write / cap_self ...），
  每次猜错都是一整轮往返 —— 这是 v11 烧掉 90k token 的主因。
  现在给三条发现路径：
    · gbt_caps  —— 枚举能力位（可按 domain / 关键字 / 是否缺参过滤，默认只回名字）
    · gbt_call  —— gbt_cap 的别名，但 kind 写错时**自动回候选**，不再空手而归
    · gbt_health —— 零授权读数
  另：kind 大小写/分隔符做归一化（fs.write / FS_WRITE / fs-write 都能命中）。

注册（Claude Code）： claude mcp add command-ai --transport stdio -- py -3.14 <本文件绝对路径>
开发者：自由的风 · 守护者：公主土豆 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
PROTO = "2024-11-05"

# 单次返回上限（字符）。全量 427 位约 166 KB，不设限会一次冲垮上下文。
MAX_TEXT = 20000
# 候选数量上限，避免"没找到"时又倒出 200 个名字
MAX_SUGGEST = 12


def _norm(name) -> str:
    """能力位名归一化：fs.write / FS-WRITE / fs write → fs_write。"""
    return re.sub(r"[\s.\-/]+", "_", str(name or "").strip()).lower()


def _cap_index():
    """返回 ({name_norm: cap}, [cap...])。索引失败不致命，返回空表。"""
    try:
        from gbt_allinone import api as A
        caps = A.list_capabilities() or []
    except Exception:
        return {}, []
    return {_norm(c.get("name")): c for c in caps}, caps


def _brief(cap) -> dict:
    """精简条目：只回定位所需字段，desc 截断。"""
    desc = (cap.get("desc") or "").strip()
    return {
        "name": cap.get("name"),
        "domain": cap.get("domain"),
        "desc": desc[:80] + ("…" if len(desc) > 80 else ""),
    }


def _suggest(name, caps):
    """kind 写错时给候选：先精确包含，再按 token 重叠打分。"""
    want = _norm(name)
    if not want:
        return []
    tokens = [t for t in want.split("_") if len(t) >= 3]
    scored = []
    for c in caps:
        cn = _norm(c.get("name"))
        if want in cn or cn in want:
            scored.append((100 + len(set(tokens) & set(cn.split("_"))), c))
            continue
        hit = len([t for t in tokens if t in cn])
        if hit:
            scored.append((hit, c))
    scored.sort(key=lambda x: -x[0])
    return [_brief(c) for _, c in scored[:MAX_SUGGEST]]


def _run(kind, payload):
    from gbt_allinone import api as A
    return A.run_task(str(kind), payload or {})


TOOLS = [
    {
        "name": "gbt_caps",
        "description": (
            "【第一步：先查再调】枚举 427 个能力位。默认只回名字（省 token），"
            "可按 domain 或 keyword 过滤。调 gbt_cap 之前不确定名字时，先跑这个，"
            "别再凭印象猜 kind。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "按域过滤，如 system / vision / data / engine / llm / device / tentacle / security / creation",
                },
                "keyword": {
                    "type": "string",
                    "description": "按名字或描述里的关键字搜，如 文件 / 截图 / 记忆 / fs",
                },
                "detail": {
                    "type": "boolean",
                    "description": "true = 带 domain+desc（每个约 100 字符）；默认 false 只回名字",
                },
                "limit": {"type": "number", "description": "最多返回条数，默认 60"},
            },
        },
    },
    {
        "name": "gbt_cap",
        "description": (
            "经唯一门调用一个能力位（权限门/审计/钢印照旧）。缺授权会如实返回缺少的作用域。"
            "kind 写错时不会空手而归 —— 会自动返回相近的候选名字。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "description": "能力位名，如 health / wf_run / impact_check / vision_loop"},
                "payload": {"type": "object", "description": "给该能力位的入参，如 {\"op\":\"list\"}"},
            },
            "required": ["kind"],
        },
    },
    {
        "name": "gbt_health",
        "description": "能力位健康读数（平台/解释器/时间），零授权。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _handle_caps(args):
    index, caps = _cap_index()
    if not caps:
        return {"ok": False, "status": "needs_dependency",
                "error": "list_capabilities 不可用，检查是否在仓根运行"}
    domain = (args.get("domain") or "").strip().lower()
    keyword = (args.get("keyword") or "").strip().lower()
    detail = bool(args.get("detail"))
    try:
        limit = max(1, min(int(args.get("limit") or 60), 300))
    except Exception:
        limit = 60

    rows = caps
    if domain:
        rows = [c for c in rows if (c.get("domain") or "").lower() == domain]
    if keyword:
        rows = [c for c in rows
                if keyword in (c.get("name") or "").lower()
                or keyword in (c.get("desc") or "").lower()]
    total = len(rows)
    rows = rows[:limit]
    out = {
        "ok": True,
        "status": "ok",
        "total": total,
        "returned": len(rows),
        "truncated": total > len(rows),
        "caps": [_brief(c) if detail else c.get("name") for c in rows],
    }
    if total == 0:
        out["hint"] = "没命中。去掉 domain/keyword 再试，或用 gbt_caps 不带参数看全量名字。"
    return out


def _handle_call(args):
    kind = args.get("kind")
    payload = args.get("payload")
    index, caps = _cap_index()
    norm = _norm(kind)
    if index and norm not in index:
        return {"ok": False, "status": "needs_input",
                "error": "没有这个能力位：%s" % kind,
                "did_you_mean": _suggest(kind, caps),
                "hint": "从 did_you_mean 里挑一个，或 gbt_caps(keyword=...) 搜。"}
    try:
        return _run(kind, payload)
    except Exception as e:
        return {"ok": False, "status": "failed", "error": str(e)[:400]}


def _send(obj) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + chr(10))
    sys.stdout.flush()


def _handle(msg):
    mid = msg.get("id")
    method = msg.get("method")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": PROTO, "capabilities": {"tools": {}},
            "serverInfo": {"name": "command-ai", "version": "2.0.0"}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        p = msg.get("params") or {}
        name = p.get("name")
        args = p.get("arguments") or {}
        try:
            if name == "gbt_health":
                out = _run("health", {})
            elif name == "gbt_cap":
                out = _handle_call(args)
            elif name == "gbt_caps":
                out = _handle_caps(args)
            else:
                out = {"status": "error", "message": "unknown tool: " + str(name)}
            text = json.dumps(out, ensure_ascii=False, default=str)[:MAX_TEXT]
            return {"jsonrpc": "2.0", "id": mid,
                    "result": {"content": [{"type": "text", "text": text}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid,
                    "result": {"isError": True,
                               "content": [{"type": "text", "text": str(e)[:400]}]}}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    return {"jsonrpc": "2.0", "id": mid,
            "error": {"code": -32601, "message": "method not found: " + str(method)}}


def main() -> int:
    for s in (sys.stdin, sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    for line in sys.stdin:
        # 剥 BOM：Windows 下管道/PowerShell 首行常带 \ufeff，会让 json.loads 直接失败
        line = line.lstrip("\ufeff").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        out = _handle(msg)
        if out is not None:
            _send(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
