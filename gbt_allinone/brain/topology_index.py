# gbt-capability: topology-index
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 能力拓扑索引 — 2.5s 全量索引, 4ms 关键词查找。

构建 CAP_REGISTRY 的能力导航图，支持按领域/关键词/依赖关系查询。
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

_INDEX_PATH = Path(__file__).resolve().parent.parent / "store" / "_topology_index.json"
_BUILD_TIME_KEY = "_built_at"


def build() -> dict:
    """全量构建拓扑索引（~2.5s）。写入 store/_topology_index.json。"""
    t0 = time.time()
    from ..caps_registry import BENIGN_CAPS

    by_domain: dict[str, list[str]] = {}
    by_handler: dict[str, str] = {}
    by_keyword: dict[str, list[str]] = {}
    cap_info: dict[str, dict] = {}

    for cap_id, info in BENIGN_CAPS.items():
        domain = info.get("domain", "unknown")
        handler = info.get("handler", cap_id)
        desc = info.get("desc", "")
        by_domain.setdefault(domain, []).append(cap_id)
        by_handler[handler] = cap_id
        cap_info[cap_id] = {"domain": domain, "handler": handler, "desc": desc}
        # Index keywords (split on common delimiters)
        keywords = [k.strip().lower() for k in desc.replace("·", " ").replace("/", " ").replace(" ", " ").split() if len(k.strip()) >= 2]
        # Also index domain and cap_id itself
        keywords.extend([domain.lower(), cap_id.lower()])
        for kw in set(keywords):
            by_keyword.setdefault(kw, []).append(cap_id)

    elapsed = round((time.time() - t0) * 1000, 1)
    index = {
        "by_domain": by_domain,
        "by_handler": by_handler,
        "by_keyword": by_keyword,
        "cap_info": cap_info,
        "total_caps": len(BENIGN_CAPS),
        "total_domains": len(by_domain),
        "_built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "_build_ms": elapsed,
    }
    try:
        _INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        _INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return index


def get() -> dict:
    """从缓存或重新构建返回索引。"""
    try:
        if _INDEX_PATH.exists():
            data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
            if data.get("total_caps", 0) > 0:
                return data
    except Exception:
        pass
    return build()


def find(keyword: str, limit: int = 20) -> list[dict]:
    """按关键词搜索能力，返回排序后的匹配列表。"""
    idx = get()
    kw = keyword.lower().strip()
    if not kw:
        return []
    cap_ids = idx.get("by_keyword", {}).get(kw, [])
    # Also partial match
    if not cap_ids:
        cap_ids = []
        for k, ids in idx.get("by_keyword", {}).items():
            if kw in k or k in kw:
                cap_ids.extend(ids)
        cap_ids = list(set(cap_ids))
    results = []
    seen = set()
    for cid in cap_ids[:limit]:
        if cid in seen:
            continue
        seen.add(cid)
        info = idx.get("cap_info", {}).get(cid, {})
        results.append({
            "id": cid,
            "domain": info.get("domain", "unknown"),
            "handler": info.get("handler", cid),
            "desc": info.get("desc", ""),
        })
    return results


def nav() -> dict:
    """返回完整导航图（46KB）。"""
    idx = get()
    domains = idx.get("by_domain", {})
    nav_graph = {}
    for domain, caps in domains.items():
        nav_graph[domain] = {
            "count": len(caps),
            "caps": caps[:10],  # 首10个作为代表
            "full_list": caps,
        }
    return {
        "ok": True,
        "total_caps": idx.get("total_caps", 0),
        "total_domains": idx.get("total_domains", 0),
        "build_ms": idx.get("_build_ms", 0),
        "domains": nav_graph,
    }
