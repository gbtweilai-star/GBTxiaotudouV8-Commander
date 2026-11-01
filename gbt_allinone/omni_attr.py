"""GBT小土豆V8 · 万能插全开失败归因

把全开同步执行（omni_all）的逐位结果按原因分类，并按域/职业聚合，输出修复清单。

分类（基于 error 文本，不猜）：
  ticket         需授权位没票（不是失败，是边界）
  timeout        子进程超时（12s kill）
  missing_dep    ModuleNotFoundError / ImportError / cannot import
  missing_file   FileNotFoundError / No such file / 找不到
  permission     PermissionError / Access denied / 拒绝访问
  network        Connection / timed out / 网络
  real_bug       其余（值得人工看的真失败）

输出：state/omni-attribution.json + outputs/omni-attribution-<run_id>.md

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "state" / "omni-results.jsonl"
OUT_JSON = ROOT / "state" / "omni-attribution.json"
OUT_DIR = ROOT / "outputs"

CATS = {
    "policy_block": ["需要人工授权", "policy", "scope 未授权"],
    "env_missing": ["找不到 git", "WinError 2", "系统找不到指定的文件"],
    "needs_input": ["需要 text", "需要 name", "需要 intent", "需要 goal", "需要 kind",
                    "需要 description", "缺少", "必填", "missing required",
                    "text 不能为空", "参数不足", "缺少参数", "运行记录不存在",
                    "工作流不存在"],
    "ticket": ["需授权", "ticket", "票"],
    "timeout": ["超时", "timeout", "TimeoutExpired"],
    "missing_dep": ["ModuleNotFoundError", "ImportError", "cannot import", "No module named"],
    "missing_file": ["FileNotFoundError", "No such file", "找不到", "not found"],
    "permission": ["PermissionError", "Access denied", "拒绝访问", "permission"],
    "network": ["Connection", "timed out", "URLError", "网络", "ECONN"],
}
CAT_LABEL = {
    "policy_block": "授权策略拦截（危险能力需人工授权，边界非 bug）",
    "env_missing": "环境缺件（缺 git/外部程序，装好即可）",
    "needs_input": "缺入参（全开 smoke 没覆盖，需补 payload）",
    "ticket": "需授权位（没票，边界非 bug）",
    "timeout": "超时（>12s，需查是否卡死/慢）",
    "missing_dep": "缺依赖（装包/接线）",
    "missing_file": "缺文件（路径/资产）",
    "permission": "权限（沙箱/ACL）",
    "network": "网络（不可达/超时）",
    "real_bug": "真 bug 候选（人工看）",
}


def classify(err: str) -> str:
    e = str(err or "")
    for cat, keys in CATS.items():
        if any(k.lower() in e.lower() for k in keys):
            return cat
    return "real_bug"


def load_results(run_id: str = "", results_path: Path | None = None) -> tuple[str, list]:
    rows = []
    src = Path(results_path) if results_path else RESULTS
    if src.is_file():
        for ln in src.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ln.strip():
                continue
            try:
                d = json.loads(ln)
            except Exception:  # noqa: BLE001
                continue
            rows.append(d)
    if not rows:
        return "", []
    runs = {}
    for r in rows:
        runs.setdefault(r.get("run_id"), []).append(r)
    rid = run_id or sorted(runs)[-1]
    return rid, runs.get(rid, [])


def _meta() -> tuple[dict, dict]:
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    prof = {}
    try:
        pj = json.loads((ROOT / "data" / "professions.json").read_text(encoding="utf-8"))
        for p in pj.get("professions") or []:
            for c in p.get("caps") or []:
                prof.setdefault(c, []).append(p.get("title"))
    except Exception:  # noqa: BLE001
        pass
    return BENIGN_CAPS, prof


def attribute(run_id: str = "", results_path: Path | None = None) -> dict:
    rid, rows = load_results(run_id, results_path)
    caps, prof = _meta()
    fails = [r for r in rows if not r.get("ok")]
    cats = Counter()
    by_domain = defaultdict(Counter)
    by_prof = defaultdict(Counter)
    items = []
    for r in fails:
        cap = str(r.get("cap") or "")
        err = str(r.get("error") or "")
        cat = classify(err)
        cats[cat] += 1
        dom = (caps.get(cap) or {}).get("domain") or "?"
        by_domain[dom][cat] += 1
        for p in prof.get(cap) or ["（未归职业）"]:
            by_prof[p][cat] += 1
        items.append({"cap": cap, "domain": dom, "category": cat, "ms": r.get("ms"),
                      "error": err[:240],
                      "professions": prof.get(cap) or []})
    out = {
        "ok": True, "run_id": rid, "caps_total": len(caps),
        "executed": sum(1 for r in rows if r.get("ok") is not None),
        "failed": len(fails), "categories": dict(cats),
        "category_labels": {k: CAT_LABEL[k] for k in cats},
        "by_domain": {d: dict(c) for d, c in by_domain.items()},
        "by_profession": {p: dict(c) for p, c in by_prof.items()},
        "items": sorted(items, key=lambda x: (x["category"], x["domain"], x["cap"])),
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = OUT_DIR / ("omni-attribution-%s.md" % (rid or "unknown"))
    lines = ["# 万能插全开失败归因 %s" % rid, "",
             "- 执行位: %d / 385" % out["executed"],
             "- 失败位: %d" % out["failed"], ""]
    lines.append("## 按原因")
    for k, v in cats.most_common():
        lines.append("- **%s** %d — %s" % (k, v, CAT_LABEL.get(k, "")))
    lines.append("")
    lines.append("## 按域")
    for d, c in sorted(by_domain.items(), key=lambda x: -sum(x[1].values())):
        lines.append("- %s: %s" % (d, dict(c)))
    lines.append("")
    lines.append("## 按职业")
    for p, c in sorted(by_prof.items(), key=lambda x: -sum(x[1].values())):
        lines.append("- %s: %s" % (p, dict(c)))
    lines.append("")
    lines.append("## 失败清单")
    for it in out["items"]:
        lines.append("- [%s] %s（%s）%s — %s" % (it["category"], it["cap"], it["domain"],
                                               (" · " + "/".join(it["professions"])) if it["professions"] else "",
                                               it["error"].replace("\n", " ")[:120]))
    lines.append("")
    lines.append("> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属")
    md.write_text("\n".join(lines), encoding="utf-8")
    out["report"] = str(md)
    return out


if __name__ == "__main__":
    rid = sys.argv[1] if len(sys.argv) > 1 else ""
    r = attribute(rid)
    print(json.dumps({k: r[k] for k in ("run_id", "executed", "failed", "categories",
                                       "report")}, ensure_ascii=False, indent=2))
