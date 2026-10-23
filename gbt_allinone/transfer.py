"""GBT小土豆V8 · 数据传输算子（万能插的传输总线原语）。

定位：万能插不只是"能跑 DAG 的执行器"，而是框架的核心传输工具。
本模块是它的传输算子层——纯数据变换、零副作用、零外部依赖、零模型调用，
让任意两个节点之间的数据流动"有形状"（可 map/filter/merge/aggregate）。

在流水线里配合扇入模板使用：
    {{*.gbt_result.result.items}}   ← 收集所有上游节点的 items 字段成列表
    run_task("transfer", {"op": "map", "data": ..., "field": "name"})

算子（op）：
    collect  归一化为列表（dict→[dict]）
    map      对列表逐项取字段 → 值列表
    pluck    从 dict 取字段（可点路径）
    filter   按表达式筛选（item.<path> 比较；复用引擎安全求值器）
    merge    列表 of dict → 合并成一个 dict
    unique   去重（保持首次出现顺序）
    sort     排序（可按 key，支持 reverse）
    limit    取前 N
    flatten  扁平化一层
    split    字符串 → 列表（分隔符）
    join     列表 → 字符串（分隔符）
    rename   字典改键（mapping: {旧: 新}）
    wrap     单值 → 列表
    stats    数据形状摘要（类型/长度/键）
"""
import json
import time
from pathlib import Path


def _dig(cur, parts):
    """按点路径取值（dict 键 + list 数字索引）。"""
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        elif isinstance(cur, list) and p.isdigit() and int(p) < len(cur):
            cur = cur[int(p)]
        else:
            raise KeyError(f"路径不存在: {p}")
    return cur


def _field(obj, field):
    if not field:
        return obj
    return _dig(obj, str(field).split("."))


def transfer(payload=None) -> dict:
    """数据传输算子入口。payload: {op, data, field?, key?, expr?, count?, sep?, mapping?, reverse?}"""
    p = payload or {}
    op = str(p.get("op") or "collect").lower()
    data = p.get("data")
    field = p.get("field")

    try:
        if op == "collect":
            if isinstance(data, list):
                out = data
            elif data is None:
                out = []
            else:
                out = [data]

        elif op == "map":
            src = data if isinstance(data, list) else ([] if data is None else [data])
            out = [_field(x, field) for x in src]

        elif op == "pluck":
            out = _field(data, field)

        elif op == "filter":
            from .engine import _eval_when
            src = data if isinstance(data, list) else ([] if data is None else [data])
            expr = str(p.get("expr") or "true")
            out = [x for x in src if _eval_when(expr, {"item": x})]

        elif op == "merge":
            src = data if isinstance(data, list) else ([] if data is None else [data])
            out = {}
            for x in src:
                if isinstance(x, dict):
                    out.update(x)

        elif op == "unique":
            src = data if isinstance(data, list) else ([] if data is None else [data])
            seen, out = set(), []
            for x in src:
                k = json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)
                if k not in seen:
                    seen.add(k)
                    out.append(x)

        elif op == "sort":
            src = data if isinstance(data, list) else ([] if data is None else [data])
            def _k(x):
                v = _field(x, p.get("key")) if p.get("key") else x
                return (v is None, v)
            out = sorted(src, key=_k, reverse=bool(p.get("reverse", False)))

        elif op == "limit":
            src = data if isinstance(data, list) else ([] if data is None else [data])
            out = src[: int(p.get("count", 10))]

        elif op == "flatten":
            src = data if isinstance(data, list) else ([] if data is None else [data])
            out = []
            for x in src:
                out.extend(x if isinstance(x, list) else [x])

        elif op == "split":
            out = str(data).split(str(p.get("sep", ",")))

        elif op == "join":
            src = data if isinstance(data, list) else ([] if data is None else [data])
            out = str(p.get("sep", ",")).join(str(x) for x in src)

        elif op == "rename":
            mapping = p.get("mapping") or {}
            out = {mapping.get(k, k): v for k, v in (data or {}).items()} if isinstance(data, dict) else {}

        elif op == "wrap":
            out = [data]

        elif op == "stats":
            if isinstance(data, list):
                out = {"type": "list", "len": len(data),
                       "items_type": sorted({type(x).__name__ for x in data})}
            elif isinstance(data, dict):
                out = {"type": "dict", "keys": list(data.keys())[:20], "len": len(data)}
            else:
                out = {"type": type(data).__name__, "value": (str(data)[:80] if data is not None else None)}

        else:
            return {"ok": False, "error": f"未知算子: {op}",
                    "supported": ["collect", "map", "pluck", "filter", "merge", "unique",
                                  "sort", "limit", "flatten", "split", "join", "rename", "wrap", "stats"]}

        if isinstance(out, list):
            return {"ok": True, "op": op, "count": len(out), "data": out}
        return {"ok": True, "op": op, "data": out}

    except Exception as e:  # noqa: BLE001
        return {"ok": False, "op": op, "error": f"{type(e).__name__}: {str(e)[:120]}"}
