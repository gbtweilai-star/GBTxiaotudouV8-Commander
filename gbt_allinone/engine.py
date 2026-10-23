"""GBT小土豆V8 · 万能插执行引擎（大脑的手）

立场（Owner 定调，2026-09-11）：框架内不再依赖"子代理"。
- 脑子只有一份：SOUL 理念 + 统一接口 run_task 做一切决策；
- 手有很多只：本引擎的 worker 线程池并行执行节点；
- 纯标准库、零模型调用——并行编排成本 ≈ 0（比 LLM 子代理省一个数量级）。

工作流模型（DAG）：
  nodes: [{id, kind, params, depends_on: [node_id...]}]
  执行：按依赖分层，同层并行；上游输出经 {{node.field.path}} 模板注入下游参数；
  fail_fast 默认 True——任何节点失败即停，如实上报，不伪造成功。

节点级武器（万能插延伸）：
  timeout        节点超时秒数，超时如实报错，不拖垮整个工作流
  when           条件执行表达式，不满足则跳过（不算失败）；支持 node.status/node.ok 便捷路径
                 （AST 白名单求值，禁函数调用，安全）
  fallback       降级回退：主能力最终失败时改走备选能力 {kind, params}，成功则带 gbt_fallback 标记
  retry_backoff  重试退避秒数（配合 max_node_retries 使用）
  routes         条件分流（switch 语义）：[{when, kind, params}, ...]，取第一条命中分支
  cache          传输缓存：同 (kind, 参数指纹) 命中即复用，cache_ttl 秒（默认 300）

核心传输工具（万能插的传输能力）：
  扇入聚合       {{*}} 收集全部上游结果；{{*.gbt_result.result.words}} 收集多路上游字段成列表
  数据算子       transfer 能力：map/filter/merge/unique/sort/limit/pluck/collect/flatten/
                 split/join/rename/wrap/stats —— 让节点间数据流动"有形状"
  层级传输       节点 kind=wf_run 可把工作流当节点嵌套（深度保护 MAX_WF_DEPTH=5）
  数字索引       模板支持列表下标：{{node.result.items.0.name}}

存储：
  store/workflows.json      工作流定义（按名幂等覆盖）
  store/wf_runs/<id>.json   每次运行完整记录（节点状态/结果/耗时）
"""
import ast as _ast
import json
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_STORE = __import__("gbt_allinone._paths", fromlist=["STORE_DIR"]).STORE_DIR
_WF_FILE = _STORE / "workflows.json"
_RUNS_DIR = _STORE / "wf_runs"

_TPL = re.compile(r"^\{\{([^}]+)\}\}$")


class EngineError(Exception):
    pass


def _load() -> dict:
    if _WF_FILE.exists():
        try:
            return json.loads(_WF_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: dict):
    _STORE.mkdir(parents=True, exist_ok=True)
    _WF_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def define_workflow(name: str, nodes) -> dict:
    """定义/覆盖一个工作流。校验：id 唯一、依赖存在、无环、kind 必须是注册过的能力。"""
    if not name or not isinstance(nodes, list) or not nodes:
        raise EngineError("需要 name 与非空 nodes 列表")
    from .caps_registry import BENIGN_CAPS

    ids = [n.get("id") for n in nodes]
    if any(not i for i in ids) or len(set(ids)) != len(ids):
        raise EngineError("节点 id 必须非空且唯一")
    id_set = set(ids)
    for n in nodes:
        _has_routes = isinstance(n.get("routes"), list) and n.get("routes")
        if n.get("kind") not in BENIGN_CAPS and not _has_routes:
            raise EngineError(f"节点 {n.get('id')} 的能力未注册: {n.get('kind')}")
        for d in n.get("depends_on", []):
            if d not in id_set:
                raise EngineError(f"节点 {n.get('id')} 依赖了不存在的节点: {d}")
        fb = n.get("fallback")
        if fb is not None:
            if not isinstance(fb, dict) or fb.get("kind") not in BENIGN_CAPS:
                raise EngineError(f"节点 {n.get('id')} 的 fallback 能力未注册: {fb}")
        if n.get("timeout") is not None:
            try:
                if float(n["timeout"]) <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                raise EngineError(f"节点 {n.get('id')} 的 timeout 必须是正数秒")
        routes = n.get("routes")
        if routes is not None:
            if not isinstance(routes, list) or not routes:
                raise EngineError(f"节点 {n.get('id')} 的 routes 必须是非空列表")
            for rt in routes:
                if not isinstance(rt, dict) or rt.get("kind") not in BENIGN_CAPS:
                    raise EngineError(f"节点 {n.get('id')} 的 routes 分支能力未注册: {rt}")
        if n.get("cache") is not None and not isinstance(n.get("cache"), bool):
            raise EngineError(f"节点 {n.get('id')} 的 cache 必须是布尔值")
    _topo_levels(nodes)  # 环检测（有环直接抛）
    data = _load()
    data[name] = {"name": name, "nodes": nodes, "defined_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _save(data)
    return {"ok": True, "name": name, "nodes": len(nodes)}


def _topo_levels(nodes):
    deps = {n["id"]: set(n.get("depends_on", [])) for n in nodes}
    done, levels = set(), []
    while deps:
        ready = [nid for nid, d in deps.items() if d <= done]
        if not ready:
            raise EngineError("依赖成环，无法执行")
        levels.append(ready)
        for nid in ready:
            done.add(nid)
            deps.pop(nid)
    return levels


def _dig(cur, parts):
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        elif isinstance(cur, list) and p.isdigit() and int(p) < len(cur):
            cur = cur[int(p)]
        else:
            raise EngineError(f"模板引用不存在: .{p}")
    return cur


def _resolve(path: str, results: dict, deps=None):
    """解析模板路径。扇入语义：路径首段为 * 时，对所有上游节点结果做映射后收集成列表。"""
    parts = path.split(".")
    if parts[0] == "*":
        out = []
        for d in (deps or []):
            if d in results:
                try:
                    out.append(_dig(results[d], parts[1:]) if len(parts) > 1 else results[d])
                except EngineError:
                    pass
        return out
    return _dig(results, parts)


def _substitute(params, results, deps=None):
    """{{node.path}} 模板注入；{{*}} / {{*.path}} 扇入聚合上游。整串保类型；混排转字符串。"""
    if isinstance(params, dict):
        return {k: _substitute(v, results, deps) for k, v in params.items()}
    if isinstance(params, list):
        return [_substitute(v, results, deps) for v in params]
    if isinstance(params, str):
        m = _TPL.match(params.strip())
        if m:
            return _resolve(m.group(1).strip(), results, deps)
        return re.sub(r"\{\{([^}]+)\}\}", lambda mm: str(_resolve(mm.group(1).strip(), results, deps)), params)
    return params


def _eval_when(expr, results):
    """条件执行表达式求值（AST 白名单，禁函数调用，安全）。

    支持：布尔 and/or/not、比较 == != > >= < <=、常量、节点路径 a.b.c。
    路径便捷解析：node.status / node.ok 会落到 node.gbt_result 上。
    表达式非法时保守返回 True（宁可执行，不可漏跑）。
    """
    try:
        tree = _ast.parse(expr, mode="eval")
    except Exception:
        return True
    return bool(_ev(tree.body, results))


def _ev(node, results):
    if isinstance(node, _ast.BoolOp):
        vals = [_ev(v, results) for v in node.values]
        return all(vals) if isinstance(node.op, _ast.And) else any(vals)
    if isinstance(node, _ast.UnaryOp) and isinstance(node.op, _ast.Not):
        return not _ev(node.operand, results)
    if isinstance(node, _ast.Compare):
        left = _ev(node.left, results)
        for op, comp in zip(node.ops, node.comparators):
            right = _ev(comp, results)
            ok = ((isinstance(op, _ast.Eq) and left == right) or
                  (isinstance(op, _ast.NotEq) and left != right) or
                  (isinstance(op, _ast.Gt) and left > right) or
                  (isinstance(op, _ast.GtE) and left >= right) or
                  (isinstance(op, _ast.Lt) and left < right) or
                  (isinstance(op, _ast.LtE) and left <= right))
            if not ok:
                return False
            left = right
        return True
    if isinstance(node, _ast.Constant):
        return node.value
    if isinstance(node, _ast.Name):
        if node.id in ("True", "True_", "true"):
            return True
        if node.id in ("False", "false"):
            return False
        if node.id in ("None", "null"):
            return None
        return results.get(node.id, {})
    if isinstance(node, _ast.Attribute):
        base = _ev(node.value, results)
        if isinstance(base, dict):
            if node.attr in base:
                return base[node.attr]
            gr = base.get("gbt_result")
            if isinstance(gr, dict):
                if node.attr == "ok":
                    return gr.get("status") == "ok"
                return gr.get(node.attr)
            return None
        return getattr(base, node.attr, None)
    if isinstance(node, _ast.Subscript):
        base = _ev(node.value, results)
        key = _ev(node.slice, results)
        try:
            return base[key]
        except Exception:
            return None
    raise ValueError("when 表达式含不支持的语法")


def _invoke(kind, params, timeout=None):
    """调用能力；timeout 秒超时则如实返回超时错误（不拖垮整个工作流）。"""
    # 内部引擎走 core：对外契约层只服务外部调用方，内部保持既有形状与异常语义。
    from .api import _run_task_core as run_task
    if not timeout:
        return run_task(kind, params)
    box = {}

    def _run():
        try:
            box["r"] = run_task(kind, params)
        except Exception as e:  # noqa: BLE001
            box["e"] = e

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    th.join(float(timeout))
    if th.is_alive():
        return {"status": "error", "kind": kind, "message": f"节点超时（>{timeout}s）"}
    if "e" in box:
        raise box["e"]
    return box["r"]


_CACHE_FILE = _STORE / "transfer_cache.json"
_cache_lock = threading.Lock()


def _cache_fingerprint(kind, params) -> str:
    import hashlib
    raw = kind + "|" + json.dumps(params, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _cache_all() -> dict:
    if _CACHE_FILE.exists():
        try:
            return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _cache_get(fp, ttl):
    with _cache_lock:
        d = _cache_all()
        hit = d.get(fp)
        if hit and (time.time() - hit.get("ts", 0)) <= ttl:
            return hit.get("result")
    return None


def _cache_put(fp, result):
    with _cache_lock:
        d = _cache_all()
        d[fp] = {"ts": time.time(), "result": result}
        if len(d) > 500:   # 上限防膨胀
            for k in sorted(d, key=lambda k: d[k].get("ts", 0))[:100]:
                d.pop(k, None)
        _STORE.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def cache_clear() -> dict:
    """清空传输缓存（返回清理条数）。"""
    with _cache_lock:
        n = len(_cache_all())
        if _CACHE_FILE.exists():
            _CACHE_FILE.unlink()
    return {"ok": True, "cleared": n}


_DEPTH = threading.local()
MAX_WF_DEPTH = 5


def run_workflow(name: str, params=None, fail_fast: bool = True,
                 max_node_retries: int = 0) -> dict:
    """执行工作流的对外入口：带子工作流嵌套深度保护（防递归失控）。"""
    depth = getattr(_DEPTH, "n", 0)
    if depth >= MAX_WF_DEPTH:
        raise EngineError(f"子工作流嵌套超过上限 {MAX_WF_DEPTH} 层（疑似递归调用）")
    _DEPTH.n = depth + 1
    try:
        return _run_workflow_inner(name, params, fail_fast, max_node_retries)
    finally:
        _DEPTH.n = depth


def _run_workflow_inner(name: str, params=None, fail_fast: bool = True,
                        max_node_retries: int = 0) -> dict:
    """执行工作流：分层并行（线程池），节点结果如实记录。

    max_node_retries > 0 时，节点失败自动重试至多该次数（幂等能力适用）。
    """
    wf = _load().get(name)
    if not wf:
        raise EngineError(f"工作流不存在: {name}（先 wf_define）")
    nodes = wf["nodes"]
    node_map = {n["id"]: n for n in nodes}
    levels = _topo_levels(nodes)

    results, node_status = {}, {}
    t0 = time.time()
    aborted = False
    for level in levels:
        if aborted and fail_fast:
            for nid in level:
                node_status[nid] = "skipped"
            continue
        if any(node_status.get(d) == "failed" for nid in level for d in node_map[nid].get("depends_on", [])):
            for nid in level:
                node_status[nid] = "skipped"
            aborted = True
            continue

        def _one(nid):
            node = node_map[nid]
            deps = node.get("depends_on", [])
            # ── 条件执行（when）：不满足则跳过（不算失败，依赖方照常跑）──
            when = node.get("when")
            if when:
                try:
                    if not _eval_when(str(when), results):
                        return nid, {"gbt_result": {"status": "skipped", "kind": node.get("kind"),
                                                    "message": f"when 条件不满足: {when}"}}
                except Exception:
                    pass  # 表达式异常保守执行
            # ── 条件分流（routes）：按顺序取第一条命中的分支（switch 语义）──
            route_info = None
            routes = node.get("routes")
            if isinstance(routes, list) and routes:
                chosen = None
                for idx, rt in enumerate(routes):
                    if not isinstance(rt, dict):
                        continue
                    if _eval_when(str(rt.get("when", "true")), results):
                        chosen = rt
                        route_info = {"index": idx, "when": rt.get("when")}
                        break
                if chosen is not None:
                    node = dict(node)
                    node["kind"] = chosen.get("kind") or node.get("kind")
                    node["params"] = chosen.get("params") or {}
                elif not node.get("kind"):
                    return nid, {"gbt_result": {"status": "skipped", "kind": None,
                                                "message": "routes 无命中且无默认分支"}}
            if not node.get("kind"):
                return nid, {"status": "error", "kind": None, "message": "节点缺少 kind"}

            last = None
            tries = max(1, int(max_node_retries) + 1)
            backoff = float(node.get("retry_backoff", 0) or 0)
            timeout = node.get("timeout")
            for i in range(tries):
                if i > 0 and backoff > 0:
                    time.sleep(backoff)
                try:
                    p = _substitute(node.get("params") or {}, results, deps)
                except EngineError as e:
                    last = {"status": "error", "kind": node.get("kind"), "message": str(e)}
                    break  # 模板错误重试无意义
                # ── 传输缓存（cache）：同 (kind, 参数指纹) 命中即复用，不重算 ──
                if node.get("cache"):
                    _fp = _cache_fingerprint(node["kind"], p)
                    _hit = _cache_get(_fp, float(node.get("cache_ttl", 300) or 300))
                    if _hit is not None:
                        _hit = dict(_hit)
                        _hit["gbt_cached"] = {"fingerprint": _fp}
                        return nid, _hit
                last = _invoke(node["kind"], p, timeout)
                body = last.get("gbt_result", last) if isinstance(last, dict) else {}
                if body.get("status") == "ok":
                    # 深层验收：能力自身声明 blocked/failed（如管线门禁拦截）不算节点成功，如实传导
                    inner = body.get("result") if isinstance(body.get("result"), dict) else {}
                    if inner.get("status") in ("blocked", "failed"):
                        last = dict(last)
                        last["gbt_result"] = dict(body)
                        last["gbt_result"]["status"] = "error"
                        last["gbt_result"]["message"] = f"能力深层状态: {inner.get('status')}"
                        continue  # 计入重试
                    if route_info:
                        last = dict(last)
                        last["gbt_route"] = route_info
                    if node.get("cache"):
                        _cache_put(_cache_fingerprint(node["kind"], p), last)
                    return nid, last
            # ── 降级回退（fallback）：主能力最终失败时走备选能力 ──
            fb = node.get("fallback")
            if isinstance(fb, dict) and fb.get("kind"):
                try:
                    fbp = _substitute(fb.get("params") or {}, results, deps)
                    fbr = _invoke(fb["kind"], fbp, fb.get("timeout") or timeout)
                    fb_body = fbr.get("gbt_result", fbr) if isinstance(fbr, dict) else {}
                    if fb_body.get("status") == "ok":
                        fbr = dict(fbr)
                        fbr["gbt_fallback"] = {"from": node.get("kind"), "to": fb.get("kind")}
                        return nid, fbr
                    last = fbr
                except Exception as fe:  # noqa: BLE001
                    last = {"status": "error", "kind": fb.get("kind"), "message": f"fallback 失败: {fe}"}
            return nid, last

        with ThreadPoolExecutor(max_workers=min(8, len(level))) as pool:
            for nid, r in pool.map(_one, level):
                body = r.get("gbt_result", r) if isinstance(r, dict) else {}
                node_status[nid] = body.get("status", "error")
                results[nid] = r
        if fail_fast and any(v in ("failed", "error") for v in node_status.values()):
            aborted = True

    elapsed = round(time.time() - t0, 3)
    statuses = list(node_status.values())
    if all(v in ("ok", "skipped") for v in statuses):
        overall = "ok" if any(v == "ok" for v in statuses) else "skipped"
    else:
        overall = "failed"
    record = {
        "run_id": f"{name}-{int(time.time()*1000)}",
        "workflow": name,
        "params": params or {},
        "status": overall,
        "nodes": node_status,
        "elapsed_s": elapsed,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (_RUNS_DIR / f"{record['run_id']}.json").write_text(
        json.dumps({"record": record, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    out = dict(record)
    out["results"] = results
    return out


def workflow_exists(name: str) -> bool:
    return name in _load()


def resume_run(run_id: str, max_node_retries: int = 0) -> dict:
    """断点续跑：读上次运行的落盘记录，只重跑未完成节点，已完成节点直接复用。

    进程崩溃/中断后调用此函数，从检查点接着跑，不重复已完成工作。
    """
    rec = get_run(run_id)
    record = rec.get("record") or rec
    wf_name = record.get("workflow")
    old_results = record.get("results") or rec.get("results") or {}
    wf = _load().get(wf_name)
    if not wf:
        raise EngineError(f"工作流已不存在: {wf_name}")
    nodes = wf["nodes"]
    node_map = {n["id"]: n for n in nodes}
    levels = _topo_levels(nodes)

    results, node_status = {}, {}
    reused = 0
    for level in levels:
        for nid in level:
            body = old_results.get(nid)
            b = body.get("gbt_result", body) if isinstance(body, dict) else {}
            if body is not None and b.get("status") == "ok":
                results[nid] = body
                node_status[nid] = "ok"
                reused += 1
            elif body is not None and b.get("status") == "skipped":
                node_status[nid] = "skipped"

    for level in levels:
        todo = [nid for nid in level if nid not in results and node_status.get(nid) != "skipped"]
        if not todo:
            continue
        # 依赖结果已从检查点恢复，模板注入可用
        def _one(nid):
            node = node_map[nid]
            p = _substitute(node.get("params") or {}, results)
            from .api import run_task
            return nid, run_task(node["kind"], p)
        with ThreadPoolExecutor(max_workers=min(8, len(todo))) as pool:
            for nid, r in pool.map(_one, todo):
                body = r.get("gbt_result", r) if isinstance(r, dict) else {}
                node_status[nid] = body.get("status", "error")
                results[nid] = r

    elapsed = 0.0
    statuses = list(node_status.values())
    overall = "ok" if statuses and all(v == "ok" for v in statuses) else (
        "skipped" if statuses and all(v == "skipped" for v in statuses) else "failed")
    out = {
        "run_id": f"{wf_name}-resume-{int(time.time()*1000)}",
        "resumed_from": run_id,
        "workflow": wf_name,
        "status": overall,
        "nodes": node_status,
        "reused_nodes": reused,
        "elapsed_s": elapsed,
        "results": results,
    }
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (_RUNS_DIR / f"{out['run_id']}.json").write_text(
        json.dumps({"record": {k: v for k, v in out.items() if k != "results"},
                    "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def get_run(run_id: str) -> dict:
    f = _RUNS_DIR / f"{run_id}.json"
    if not f.exists():
        raise EngineError(f"运行记录不存在: {run_id}")
    return json.loads(f.read_text(encoding="utf-8"))


def list_workflows() -> dict:
    """列出工作流**定义**（只读）。

    R-H99b 由来：想给万能插做可视化时发现**没有正规数据出口**——`wf_status` 只回运行记录，
    `engine` 侧只有 define/run/resume，没人能"列出有哪些工作流、各自什么形状"。
    没有这一步，任何可视化都只能去偷读 `store/workflows.json`（绕过能力层，口径就散了）。
    这里只读 `_load()`（本模块自己的账本），不执行、不写盘。
    """
    data = _load()
    out = []
    for name, wf in data.items():
        nodes = list(wf.get("nodes") or [])
        out.append({
            "name": name,
            "node_count": len(nodes),
            "nodes": [{
                "id": n.get("id"),
                "kind": n.get("kind"),
                "depends_on": list(n.get("depends_on") or []),
                "has_fallback": bool(n.get("fallback")),
                "routes": len(n.get("routes") or []) if isinstance(n.get("routes"), list) else 0,
                "cache": bool(n.get("cache")),
            } for n in nodes],
        })
    out.sort(key=lambda r: r["name"])
    return {"workflows": out, "count": len(out)}


def list_runs(name=None, limit=20, include_workflows: bool = False) -> dict:
    """最近运行记录；`include_workflows=True` 时**顺带**带回工作流定义（可视化的正规出口）。

    默认输出形状与改动前逐字段一致（`{"runs": [...]}`），新字段只在显式要的时候出现 ——
    不让"看一眼记录"的既有调用方被悄悄改口径。
    """
    if not _RUNS_DIR.exists():
        out = {"runs": []}
        if include_workflows:
            out.update(list_workflows())
        return out
    files = sorted(_RUNS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    runs = []
    for f in files:
        try:
            rec = json.loads(f.read_text(encoding="utf-8")).get("record", {})
        except Exception:
            continue
        if name and rec.get("workflow") != name:
            continue
        runs.append(rec)
        if len(runs) >= limit:
            break
    out = {"runs": runs}
    if include_workflows:
        out.update(list_workflows())
    return out
