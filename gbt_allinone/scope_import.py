"""GBT小土豆V8 · 平台 scope 导入（离线，不联网）

主人 2026-11-02：「下一步」——把 HackerOne / Bugcrowd 的项目 scope 结构化导入成授权项目。

合规口径：
  · **必须人工确认**：`confirm=True` 才允许落库；默认 dry-run 只给预览；
  · 导入的 authorization_ref 会自动写明来源（平台+项目），但仍标注「需人工核对授权」；
  · 不联网：只读本地 JSON 文件；不访问任何平台 API；
  · 空 scope / 解析失败一律拒绝，不造项目。

支持格式（结构归一化）：
  · HackerOne 导出：{"program": {...}, "scopes": [{asset_identifier, asset_type, ...}]}
  · Bugcrowd 导出：{"program": {...}, "targets": {"in_scope": [...], "out_of_scope": [...]}}
  · 也接受已归一化：{"name": "...", "scope": [...], "out_of_scope": [...]}

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gbt_allinone import bounty as B  # noqa: E402

SAMPLES = ROOT / "data" / "scope-samples"
ALLOWED_DIRS = (SAMPLES, ROOT / "state" / "scope-import")


def _norm_asset(kind: str, value: str) -> str | None:
    v = str(value or "").strip()
    if not v:
        return None
    kind = (kind or "").upper()
    if kind in ("WILDCARD", "DOMAIN", "URL"):
        v = v.replace("https://", "").replace("http://", "").rstrip("/")
        v = v.split("/")[0].split("?")[0]
        v = v.strip().lstrip("*").lstrip(".")
        if not v or " " in v:
            return None
        return v
    if kind in ("IP_ADDRESS", "IP"):
        return v
    if kind in ("CIDR", "IP_RANGE", "NETWORK"):
        return v if "/" in v else v + "/32"
    # 未知类型按域名/IP 处理
    v = v.replace("https://", "").replace("http://", "").rstrip("/").split("/")[0]
    v = v.strip().lstrip("*").lstrip(".")
    return v or None


def normalize(doc: dict) -> dict:
    """平台 JSON → {name, platform, url, handle, scope[], out_of_scope[], rules}。"""
    if not isinstance(doc, dict):
        return {"ok": False, "reason": "不是 JSON 对象"}
    platform = str(doc.get("platform") or "").strip()

    # 已归一化格式
    if doc.get("scope") is not None and isinstance(doc.get("scope"), list):
        return {"ok": True, "name": str(doc.get("name") or "").strip(),
                "platform": platform or "generic",
                "url": str(doc.get("url") or ""),
                "handle": str(doc.get("handle") or ""),
                "scope": [x for x in (_norm_asset("", a) for a in doc["scope"]) if x],
                "out_of_scope": [x for x in (_norm_asset("", a)
                                             for a in (doc.get("out_of_scope") or [])) if x],
                "rules": str(doc.get("rules") or "")}

    prog = doc.get("program") or {}
    if not isinstance(prog, dict):
        prog = {}
    name = str(prog.get("name") or prog.get("handle") or doc.get("name") or "").strip()
    handle = str(prog.get("handle") or "").strip()
    url = str(prog.get("url") or prog.get("website") or "").strip()
    scope, out = [], []

    # HackerOne：scopes[]
    scopes = doc.get("scopes") or doc.get("structured_scopes") or []
    if isinstance(scopes, list) and scopes:
        for s in scopes:
            if not isinstance(s, dict):
                continue
            a = _norm_asset(str(s.get("asset_type") or ""), str(s.get("asset_identifier") or s.get("identifier") or ""))
            if not a:
                continue
            if s.get("eligible_for_bounty") is False:
                # 保守：不参与赏金的资产按 out 处理（宁可少测，不越界）
                out.append(a)
            else:
                scope.append(a)
        platform = platform or "hackerone"

    # Bugcrowd：targets.in_scope / out_of_scope
    targets = doc.get("targets") or {}
    if isinstance(targets, dict):
        for s in (targets.get("in_scope") or []):
            if isinstance(s, dict):
                a = _norm_asset(str(s.get("category") or ""), str(s.get("uri") or s.get("target") or ""))
                if a:
                    scope.append(a)
        for s in (targets.get("out_of_scope") or []):
            if isinstance(s, dict):
                a = _norm_asset(str(s.get("category") or ""), str(s.get("uri") or s.get("target") or ""))
                if a:
                    out.append(a)
            elif isinstance(s, str):
                a = _norm_asset("", s)
                if a:
                    out.append(a)
        platform = platform or "bugcrowd"

    # 兜底：scopes 是字符串列表
    if not scope and isinstance(doc.get("in_scope"), list):
        scope = [x for x in (_norm_asset("", s) for s in doc["in_scope"]) if x]
        out = [x for x in (_norm_asset("", s) for s in (doc.get("out_of_scope") or [])) if x]

    # 顶层 out_of_scope 也要并进来（HackerOne 导出常见）
    for x in (doc.get("out_of_scope") or []):
        a = _norm_asset("", x) if isinstance(x, str) else None
        if a:
            out.append(a)

    # 去重保序
    def uniq(xs):
        seen, o = set(), []
        for x in xs:
            if x not in seen:
                seen.add(x)
                o.append(x)
        return o

    return {"ok": True, "name": name, "platform": platform or "generic", "url": url,
            "handle": handle, "scope": uniq(scope), "out_of_scope": uniq(out),
            "rules": str(prog.get("rules") or doc.get("rules") or "")}


def load_sample(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    try:
        p.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return {"ok": False, "reason": "路径必须在仓库内"}
    if not p.is_file():
        return {"ok": False, "reason": "文件不存在：%s" % p}
    try:
        return {"ok": True, "path": str(p), "doc": json.loads(p.read_text(encoding="utf-8"))}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": "JSON 解析失败：%s" % str(e)[:120]}


def import_doc(doc: dict, confirm: bool = False) -> dict:
    n = normalize(doc)
    if not n.get("ok"):
        return {"ok": False, "reason": n.get("reason")}
    if not n.get("scope"):
        return {"ok": False, "reason": "解析后 scope 为空——拒绝导入（不造空项目）"}
    auth = "imported from %s program %s — 需人工核对授权" % (
        n.get("platform"), n.get("handle") or n.get("name"))
    preview = {"ok": True, "dry_run": not confirm, "name": n["name"], "platform": n["platform"],
               "url": n["url"], "handle": n["handle"], "scope": n["scope"],
               "out_of_scope": n["out_of_scope"], "authorization_ref": auth,
               "requires_confirm": "confirm=True 才落库（防止把示例/未审 scope 当授权）"}
    if not confirm:
        return preview
    r = B.add_program(n["name"], n["scope"], n["out_of_scope"], platform=n["platform"],
                      url=n["url"], authorization_ref=auth,
                      reward_range="", rules=n.get("rules") or "")
    preview.update({"dry_run": False, "created": r.get("ok"), "program": r.get("program"),
                    "reason": r.get("reason")})
    return preview


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "data/scope-samples/hackerone-sample.json"
    loaded = load_sample(arg)
    if not loaded.get("ok"):
        print(json.dumps(loaded, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    print(json.dumps(import_doc(loaded["doc"], confirm="--confirm" in sys.argv),
                     ensure_ascii=False, indent=2))
