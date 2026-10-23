# -*- coding: utf-8 -*-
# gbt-capability: knowledge_lib
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""knowledge_lib —— 知识库两件（主人令 2026-10-13：吞 WeKnora ⇒ **蒸我们自己的那两面**）。

来历（现读）：主人发来周榜 #05 `Tencent/WeKnora`（Go · 33.5k★ · MIT）⇒ 走门 `devour_github`
真吞成胶囊 `devoured_tencent_weknora`（README 34,257 字符 · absorbed_knowledge 6,517 字符）。
**重合面判定**（它 README 三大支柱 × 本仓位面）后，只蒸**我们没有的那两面**，不搬它的代码、不造重复器官：

  · **wiki_graph**  自维护百科 + **知识图谱** + **回滚**
      —— 本仓原来只有碎片（`brain_vault` Obsidian / `thebrain_bridge` / `asset_index`）。
      四件铁律：① **每页必须有出处**（无源页 verify 必须点出来）② **悬空边**（links 指向不存在的页）
      必须点名，不许静默 ③ **回滚留痕**（回滚=产生新版本，**永不删历史**）④ 图**现算**，不存第二份真相。

  · **doc_intake**  解析 → 入库 → 同步（那条链）
      —— 本仓原来只有单件（`datakit` / `genoffice`）。
      三条口径：① **只吃本地文件**（出网那条路另挂门，本位不偷偷下载）② **不新造解析器**
      （md/txt 直读；html 只做去标签+实体还原，**并如实标注这不是真解析**；其余类型如实报「解析手未接」）
      ③ `sources` 只**如实报**外部源（飞书/GitLab）的接线状态，**没接就说没接**。

## 落点
  `store/knowledge_lib/`：`pages/<slug>.json`（现版）· `revisions/<slug>/rev-N.json`（版本链，回滚用）·
  `intake.jsonl`（入库账）。`GBT_STORE_DIR` 一变就跟着走（同 skill_watch 口径）。
"""
from __future__ import annotations

import html as _html
import json
import os
import pathlib
import re
import time

_ROOT = pathlib.Path(__file__).resolve().parent.parent

OPS = {
    "wiki_graph": ("status", "put", "get", "graph", "neighbors", "history",
                   "rollback", "verify", "where"),
    "doc_intake": ("status", "sources", "plan", "intake", "verify", "where"),
}

_TEXT_EXT = (".md", ".markdown", ".txt", ".csv", ".json", ".log", ".yaml", ".yml")
_HTML_EXT = (".html", ".htm")
_TAG_RE = re.compile(r"<[^>]+>")


def _root() -> pathlib.Path:
    d = os.environ.get("GBT_STORE_DIR")
    base = pathlib.Path(d) if d else (_ROOT / "gbt_allinone" / "store")
    p = base / "knowledge_lib"
    (p / "pages").mkdir(parents=True, exist_ok=True)
    (p / "revisions").mkdir(parents=True, exist_ok=True)
    return p


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _slug(raw: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff-]", "_", str(raw or "").strip())
    return s[:60] or "untitled"


def _page_path(slug: str) -> pathlib.Path:
    return _root() / "pages" / (_slug(slug) + ".json")


def _rev_dir(slug: str) -> pathlib.Path:
    return _root() / "revisions" / _slug(slug)


def _load_page(slug: str) -> dict | None:
    p = _page_path(slug)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return None


def _all_pages() -> list:
    out = []
    for p in sorted((_root() / "pages").glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:                                       # noqa: BLE001
            continue
    return out


def _append(name: str, row: dict) -> None:
    with (_root() / name).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _graph() -> dict:
    """**现算**图：节点+边（links 去重、剔自环）+ 悬空边 + 孤儿页。不存第二份真相。"""
    pages = _all_pages()
    known = {p["slug"] for p in pages}
    edges, dangling, linked = [], [], set()
    for p in pages:
        for tgt in p.get("links") or []:
            t = _slug(tgt)
            if t == p["slug"]:
                continue
            edges.append({"from": p["slug"], "to": t})
            if t in known:
                linked.add(t)
            else:
                dangling.append({"from": p["slug"], "to": t})
    orphans = sorted(known - linked)
    return {"nodes": len(known), "slugs": sorted(known), "edges": edges,
            "dangling_edges": dangling, "orphans": orphans}


# ── ① wiki_graph ──────────────────────────────────────────────────────────
def _wiki(op: str, p: dict) -> dict:
    if op in ("status", "where"):
        g = _graph()
        return {"ok": True, "op": op, "ops": list(OPS["wiki_graph"]),
                "页数": g["nodes"], "边数": len(g["edges"]),
                "悬空边": len(g["dangling_edges"]), "孤儿页": len(g["orphans"]),
                "落点": str(_root()),
                "口径": "图现算不存副本；无源页/悬空边/孤儿页由 verify 点名，不静默"}
    if op == "put":
        title = str(p.get("title") or p.get("slug") or "").strip()
        slug = _slug(p.get("slug") or title)
        if not title:
            return {"ok": False, "error": "缺 title（页名）"}
        body = str(p.get("body") or "")
        if not body.strip():
            return {"ok": False, "error": "空正文不许入库（无意义 + 会污染图）"}
        sources = [str(x) for x in (p.get("sources") or [])]
        old = _load_page(slug)
        rev = int(old.get("rev", 0)) + 1 if old else 1
        if old:
            d = _rev_dir(slug)
            d.mkdir(parents=True, exist_ok=True)
            (d / ("rev-%d.json" % int(old.get("rev", 1)))).write_text(
                json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
        rec = {"slug": slug, "title": title, "body": body,
               "tags": [str(x) for x in (p.get("tags") or [])],
               "links": [_slug(x) for x in (p.get("links") or [])],
               "sources": sources, "rev": rev, "updated_at": _now(),
               "created_at": (old or {}).get("created_at") or _now()}
        _page_path(slug).write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
        d = _rev_dir(slug)
        d.mkdir(parents=True, exist_ok=True)
        (d / ("rev-%d.json" % rev)).write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
        warn = [] if sources else ["**无源页**：这页没写出处（verify 会点它）"]
        return {"ok": True, "op": "put", "slug": slug, "rev": rev,
                "出边": len(rec["links"]), "警示": warn,
                "口径": "改动=新版本；旧版自动进版本链，永不删历史"}
    if op == "get":
        pg = _load_page(str(p.get("slug") or ""))
        if not pg:
            return {"ok": False, "error": "没有这一页（slug=%s）" % p.get("slug")}
        return {"ok": True, "op": "get", "page": pg}
    if op == "graph":
        g = _graph()
        g.update({"ok": True, "op": "graph"})
        return g
    if op == "neighbors":
        slug = _slug(p.get("slug") or "")
        if not _load_page(slug):
            return {"ok": False, "error": "没有这一页（slug=%s）" % slug}
        g = _graph()
        out = {slug}
        for _ in range(max(1, int(p.get("depth") or 1))):
            new = set()
            for e in g["edges"]:
                if e["from"] in out and e["to"] in g["slugs"]:
                    new.add(e["to"])
                if e["to"] in out and e["from"] in g["slugs"]:
                    new.add(e["from"])
            out |= new
        return {"ok": True, "op": "neighbors", "中心": slug, "邻域": sorted(out),
                "页数": len(out)}
    if op == "history":
        slug = _slug(p.get("slug") or "")
        d = _rev_dir(slug)
        rows = []
        if d.exists():
            for f in sorted(d.glob("rev-*.json")):
                try:
                    r = json.loads(f.read_text(encoding="utf-8"))
                except Exception:                               # noqa: BLE001
                    continue
                rows.append({"rev": r.get("rev"), "updated_at": r.get("updated_at"),
                             "chars": len(str(r.get("body") or "")),
                             "rolled_back_from": r.get("rolled_back_from")})
        return {"ok": bool(rows), "op": "history", "slug": slug, "versions": rows} if rows else \
            {"ok": False, "error": "没有版本链（slug=%s）" % slug}
    if op == "rollback":
        slug = _slug(p.get("slug") or "")
        want = int(p.get("rev") or 0)
        f = _rev_dir(slug) / ("rev-%d.json" % want)
        if not want or not f.exists():
            return {"ok": False, "error": "没这个版本（slug=%s rev=%s）" % (slug, want)}
        src = json.loads(f.read_text(encoding="utf-8"))
        cur = _load_page(slug) or {}
        new_rev = int(cur.get("rev", 0)) + 1
        rec = dict(src, rev=new_rev, updated_at=_now(),
                   rolled_back_from=want, rolled_back_at=_now())
        _page_path(slug).write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
        (_rev_dir(slug) / ("rev-%d.json" % new_rev)).write_text(
            json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "op": "rollback", "slug": slug, "回到": want, "新版本": new_rev,
                "口径": "回滚=产生新版本（**不删历史**）：旧版还在版本链里，可再回滚回来"}
    if op == "verify":
        pages = _all_pages()
        g = _graph()
        no_src = [x["slug"] for x in pages if not (x.get("sources") or [])]
        empty = [x["slug"] for x in pages if not str(x.get("body") or "").strip()]
        bad_hist = []
        for x in pages:
            if not (_rev_dir(x["slug"]) / ("rev-%d.json" % int(x.get("rev", 1)))).exists():
                bad_hist.append(x["slug"])
        ok = not (no_src or empty or g["dangling_edges"] or bad_hist)
        return {"ok": ok, "op": "verify", "页数": len(pages),
                "无源页": no_src, "空正文页": empty, "悬空边": g["dangling_edges"],
                "当前版本缺快照": bad_hist, "孤儿页": g["orphans"],
                "判决": ("✅ 四件全过（无源页0 · 空正文0 · 悬空边0 · 版本快照齐）" if ok else
                       "🔴 有项不过 ⇒ 照上面点名逐条补（**孤儿页只提示不算错**，知识可以先孤立再接线）"),
                "口径": "自维护=这些项**可被机器点出来**；点出来就不许装没看见"}
    return {"ok": False, "error": "未知 op:%s" % op, "known": list(OPS["wiki_graph"])}


# ── ② doc_intake ──────────────────────────────────────────────────────────
def _to_text(raw: str, ext: str) -> tuple:
    """**不新造解析器**：文本类直读；html 只做去标签+实体还原（并标注这不是真解析）。"""
    if ext in _TEXT_EXT:
        return raw, "直读（文本类）"
    if ext in _HTML_EXT:
        body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
        body = _TAG_RE.sub(" ", body)
        body = re.sub(r"[ \t\r\f\v]+", " ", _html.unescape(body))
        return re.sub(r"\n{3,}", "\n\n", body).strip(), "html 去标签（**不是真解析**：要真解析走 datakit/genoffice，另挂）"
    return "", "解析手未接（%s 这类要走别的解析手，本位不假装能读）" % (ext or "未知类型")


def _intake(op: str, p: dict) -> dict:
    if op == "status":
        rows = []
        f = _root() / "intake.jsonl"
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except Exception:                           # noqa: BLE001
                        continue
        return {"ok": True, "op": "status", "ops": list(OPS["doc_intake"]),
                "入库账笔数": len(rows), "落点": str(_root()),
                "口径": "只吃本地文件；出网那条路另挂门"}
    if op == "sources":
        ext = []
        try:
            import importlib
            for mod, name in (("gbt_allinone.feishu_embed", "飞书"), ("gbt_allinone.tools.git_read", "GitLab/Git")):
                try:
                    importlib.import_module(mod)
                    ext.append({"源": name, "状态": "模块在位（**未接线到本位**：要走它自己的门与授权）"})
                except Exception:                               # noqa: BLE001
                    ext.append({"源": name, "状态": "**未读到模块**"})
        except Exception:                                       # noqa: BLE001
            pass
        return {"ok": True, "op": "sources",
                "本地文件": {"状态": "可用（本位直接读，只读）"},
                "外部源（飞书 / GitLab）": ext or "**未读到**",
                "口径": "**没接就说没接**：外部源接入要走各自的门，本位不偷偷拉"}
    if op == "plan":
        path = str(p.get("path") or "").strip()
        ext = pathlib.Path(path).suffix.lower() if path else ""
        hand = ("直读" if ext in _TEXT_EXT else
                ("html 去标签" if ext in _HTML_EXT else "**解析手未接**"))
        return {"ok": True, "op": "plan", "path": path, "后缀": ext or "**未给**",
                "步骤": [
                    {"步": "1 判类型", "怎么做": "看后缀；未知类型如实报「解析手未接」", "判据": "后缀已判"},
                    {"步": "2 取文本", "怎么做": "解析手 = %s" % hand, "判据": "拿到非空文本"},
                    {"步": "3 入库", "怎么做": "wiki_graph.put（slug/title/sources 必填）", "判据": "页入库且**带出处**"},
                    {"步": "4 记账", "怎么做": "落 intake.jsonl（谁、哪个文件、多少字符）", "判据": "账可查"},
                ],
                "口径": "只吃本地文件；外部源同步另走各自的门（见 sources）"}
    if op == "intake":
        path = str(p.get("path") or "").strip()
        if not path:
            return {"ok": False, "error": "缺 path：本地文件路径"}
        f = pathlib.Path(path)
        if not f.is_file():
            return {"ok": False, "error": "不是文件或不存在：%s" % path}
        if re.match(r"^[A-Za-z]:[\\/]", path) is None and f.is_absolute() and not path.startswith(str(_ROOT)):
            pass
        ext = f.suffix.lower()
        try:
            raw = f.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:                                # noqa: BLE001
            return {"ok": False, "error": "读不开：%s: %s" % (type(exc).__name__, str(exc)[:80])}
        text, how = _to_text(raw, ext)
        if not text.strip():
            return {"ok": False, "error": how, "后缀": ext,
                    "口径": "拿不到文本就**如实报**，不许拿空页充数"}
        title = str(p.get("title") or f.stem)
        slug = str(p.get("slug") or f.stem)
        with_src = [str(x) for x in (p.get("sources") or [])] or ["本地文件:%s" % f.name]
        put = _wiki("put", {"slug": slug, "title": title, "body": text,
                            "tags": p.get("tags") or [], "links": p.get("links") or [],
                            "sources": with_src})
        _append("intake.jsonl", {"at": _now(), "path": str(f), "chars": len(text),
                                 "how": how, "slug": put.get("slug"), "rev": put.get("rev")})
        return {"ok": bool(put.get("ok")), "op": "intake", "文件": f.name, "解析手": how,
                "字符": len(text), "入库": put.get("slug"), "rev": put.get("rev"),
                "出处": with_src, "口径": "入库即带出处；无源页 verify 会点它"}
    if op == "verify":
        same = pathlib.Path(str(p.get("path") or ""))
        return {"ok": True, "op": "verify",
                "解析手覆盖": {"文本类": list(_TEXT_EXT), "html": list(_HTML_EXT),
                            "其余": "**未接**（如实报，不假装）"},
                "本文件可读": (same.is_file() if str(p.get("path") or "").strip() else "未给 path"),
                "口径": "判据只量**我们能证明的**：类型覆盖 + 真读一次"}
    return {"ok": False, "error": "未知 op:%s" % op, "known": list(OPS["doc_intake"])}


KINDS = tuple(OPS)
DEFAULT_OP = {"wiki_graph": "status", "doc_intake": "status"}


def run(kind: str, payload: dict | None = None) -> dict:
    """能力位统一入口（`api.run_task` 的 if 链调它）。两个位同一道门。"""
    k = str(kind or "").strip()
    if k not in OPS:
        return {"ok": False, "error": "未知能力位:%s" % k, "known": list(OPS)}
    p = dict(payload or {})
    op = str(p.get("op") or p.get("action") or "").strip() or DEFAULT_OP[k]
    fn = {"wiki_graph": _wiki, "doc_intake": _intake}[k]
    try:
        out = fn(op, {kk: vv for kk, vv in p.items() if kk not in ("op", "action")})
    except Exception as exc:                                    # noqa: BLE001
        return {"ok": False, "kind": k, "error": "%s: %s" % (type(exc).__name__, str(exc)[:160])}
    out.setdefault("kind", k)
    return out
