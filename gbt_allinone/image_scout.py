# gbt-capability: image_scout
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""image_scout -- **美图精准抓取**（主人令 2026-10-17「去精准抓取美图能力给她注入」）。

## 定位
**只做"找对图 + 把关质量与许可"**，不做下载/写盘（写盘走既有写面能力位）。
产出 = 候选清单（直链 + 尺寸 + 比例 + 许可 + 署名行 + 来源），供后续 `zimage_rewash`（修饰/放大）
或 `file_operation`（落盘）接棒。

## 源（真实可用/带许可）
- **Openverse**（`api.openverse.org`，CC 授权聚合，**免钥匙**）——默认源，许可字段可机读；
- **Unsplash**（`api.unsplash.com`，需 `GBT_UNSPLASH_KEY`）；
- **Pexels**（`api.pexels.com`，需 `GBT_PEXELS_KEY`）。
缺钥匙的源一律如实报"未配钥匙"，**不假装可用**。

## 精准门槛（不是"搜出来就行"）
`min_width / min_height / aspect / license / extension / source` 全可设；
`curate` 按 分辨率×比例契合×许可优先 排序，返回前 k 条并逐条给**署名行**。

## 出网硬钉
只许 https；主机白名单（三个源）；拒重定向；密钥只回掩码；**本能力绝不下载图片字节**。

op = status / sources / search / curate / where
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

OPS = ("status", "sources", "search", "curate", "where")
READ_OPS = OPS
WRITE_OPS = ()

UA = "gbt-v8/image_scout (+native; read-only)"
HOSTS = {"api.openverse.org", "api.unsplash.com", "api.pexels.com"}
DEFAULT_MIN_W = 1024   # 2026-10-17 实测：Openverse 索引尺寸多为 ≤1024 宽，1600 会把结果全滤空
DEFAULT_MIN_H = 768


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):   # noqa: D401
        return None


def _mask(v: str) -> str:
    v = str(v or "")
    return (v[:4] + "****") if v else ""


def _key(env: str) -> str:
    return (os.environ.get(env) or "").strip()


def _get(url: str, headers: dict | None = None, timeout: int = 20) -> tuple:
    p = urllib.parse.urlparse(url)
    if p.scheme != "https":
        return -1, None, {"ok": False, "denied": True, "reason": "只认 https"}
    if (p.hostname or "").lower() not in HOSTS:
        return -1, None, {"ok": False, "denied": True,
                          "reason": "主机不在白名单（%s）" % (p.hostname or "?")}
    h = {"User-Agent": UA, "Accept": "application/json", **(headers or {})}
    opener = urllib.request.build_opener(_NoRedirect())
    rq = urllib.request.Request(url, headers=h)
    try:
        with opener.open(rq, timeout=timeout) as s:
            return s.status, s.read(), None
    except urllib.error.HTTPError as e:
        try:
            b = e.read()
        except Exception:                                            # noqa: BLE001
            b = b""
        return e.code, b, None
    except Exception as e:                                           # noqa: BLE001
        return -1, None, {"ok": False, "未读到": "%s: %s" % (type(e).__name__, str(e)[:160])}


def sources(**_kw) -> dict:
    return {"ok": True, "op": "sources",
            "sources": [
                {"id": "openverse", "host": "api.openverse.org", "key": "免钥匙",
                 "license": "CC 系（字段可机读）", "note": "默认源；聚合 Flickr/Wikimedia 等"},
                {"id": "unsplash", "host": "api.unsplash.com", "key": ("已配（%s）" % _mask(_key("GBT_UNSPLASH_KEY")))
                 if _key("GBT_UNSPLASH_KEY") else "未配（GBT_UNSPLASH_KEY）",
                 "license": "Unsplash License（需署名）"},
                {"id": "pexels", "host": "api.pexels.com", "key": ("已配（%s）" % _mask(_key("GBT_PEXELS_KEY")))
                 if _key("GBT_PEXELS_KEY") else "未配（GBT_PEXELS_KEY）",
                 "license": "Pexels License（需署名）"}],
            "_口径": "缺钥匙的源如实报未配，不假装可用"}


def status(**_kw) -> dict:
    st, b, err = _get("https://api.openverse.org/v1/images/?q=test&page_size=1", timeout=12)
    if err:
        return {"ok": False, "op": "status", **err,
                "note": "Openverse 不可达 ⇒ 如实报未读到（不编候选）"}
    ok = bool(st and 200 <= st < 300)
    return {"ok": ok, "op": "status", "http": st,
            "openverse": "可达" if ok else "异常",
            "sources": {s["id"]: s["key"] for s in sources()["sources"]},
            "keys": {"unsplash": _mask(_key("GBT_UNSPLASH_KEY")) or "未配",
                     "pexels": _mask(_key("GBT_PEXELS_KEY")) or "未配"}}


def _search_openverse(q: str, n: int, min_w: int, min_h: int, aspect: str,
                      license_: str, extension: str) -> tuple:
    # 2026-10-17 修（实测）：带 aspect/license/extension 筛选参数时 Openverse 响应明显变慢甚至超时
    #   ⇒ 现口径：**只带最小参数（q + page_size）**，筛选全部在本地做；超时 30s 且重试一次。
    # 2026-10-17 修（实测）：Openverse 默认**不返回 width/height** ⇒ 质量门槛全被过滤成 0 条。
    #   现口径：显式带 `fields=` 把这些字段要回来（实证：带 fields 后返回 1024x384 等真尺寸）。
    params = {"q": q, "page_size": str(max(1, min(20, n * 2))),
              "fields": "id,title,url,thumbnail,width,height,license,license_url,creator,creator_url,foreign_landing_url"}
    url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(params)
    st, b, err = _get(url, timeout=30)
    if err:
        st, b, err = _get(url, timeout=30)                     # 一次重试（瞬断如实保留，不假装成功）
    if err:
        return [], err
    try:
        j = json.loads((b or b"{}").decode("utf-8", "replace"))
    except Exception:                                                # noqa: BLE001
        return [], {"ok": False, "未读到": "Openverse 返回非 JSON", "raw": (b or b"")[:160].decode("utf-8", "replace")}
    out = []
    for r in (j.get("results") or []):
        w, h = int(r.get("width") or 0), int(r.get("height") or 0)
        if w < min_w or h < min_h:
            continue
        lic = str(r.get("license") or "").lower()
        if license_ and license_.lower() not in lic:
            continue
        if extension and extension.lower() not in str(r.get("url") or "").lower():
            continue
        if aspect and aspect != "any":
            ratio = (w / h) if h else 0
            if aspect == "wide" and not ratio > 1.15:
                continue
            if aspect == "tall" and not ratio < 0.87:
                continue
            if aspect == "square" and not (0.87 <= ratio <= 1.15):
                continue
        out.append({
            "source": "openverse", "title": str(r.get("title") or "")[:80],
            "url": r.get("url"), "thumb": r.get("thumbnail"), "width": w, "height": h,
            "ratio": round((w / h), 3) if h else 0,
            "license": lic, "license_url": r.get("license_url"),
            "creator": str(r.get("creator") or ""), "creator_url": r.get("creator_url"),
            "attribution": "「%s」by %s · %s · %s" % (str(r.get("title") or "?")[:40],
                                                     str(r.get("creator") or "?"),
                                                     lic.upper() or "?",
                                                     r.get("foreign_landing_url") or r.get("url") or ""),
        })
    return out, None


def _search_unsplash(q: str, n: int) -> tuple:
    k = _key("GBT_UNSPLASH_KEY")
    if not k:
        return [], {"ok": False, "未配钥匙": "GBT_UNSPLASH_KEY"}
    url = "https://api.unsplash.com/search/photos?" + urllib.parse.urlencode(
        {"query": q, "per_page": str(max(1, min(30, n)))})
    st, b, err = _get(url, headers={"Authorization": "Client-ID " + k})
    if err:
        return [], err
    j = json.loads((b or b"{}").decode("utf-8", "replace"))
    out = []
    for r in (j.get("results") or []):
        w, h = int(r.get("width") or 0), int(r.get("height") or 0)
        out.append({"source": "unsplash", "title": str(r.get("description") or r.get("alt_description") or "")[:80],
                    "url": (r.get("urls") or {}).get("full"), "thumb": (r.get("urls") or {}).get("small"),
                    "width": w, "height": h, "ratio": round(w / h, 3) if h else 0,
                    "license": "unsplash-license", "creator": str(((r.get("user") or {}).get("name")) or ""),
                    "attribution": "「%s」by %s · Unsplash License · %s" % (str(r.get("id") or "?"),
                                                                          str(((r.get("user") or {}).get("name")) or "?"),
                                                                          str(r.get("links") or {}).get("html") or "")})
    return out, None


def _search_pexels(q: str, n: int) -> tuple:
    k = _key("GBT_PEXELS_KEY")
    if not k:
        return [], {"ok": False, "未配钥匙": "GBT_PEXELS_KEY"}
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": q, "per_page": str(max(1, min(30, n)))})
    st, b, err = _get(url, headers={"Authorization": k})
    if err:
        return [], err
    j = json.loads((b or b"{}").decode("utf-8", "replace"))
    out = []
    for r in (j.get("photos") or []):
        w, h = int(r.get("width") or 0), int(r.get("height") or 0)
        out.append({"source": "pexels", "title": str(r.get("alt") or "")[:80],
                    "url": (r.get("src") or {}).get("original"), "thumb": (r.get("src") or {}).get("medium"),
                    "width": w, "height": h, "ratio": round(w / h, 3) if h else 0,
                    "license": "pexels-license", "creator": str(r.get("photographer") or ""),
                    "attribution": "「%s」by %s · Pexels License · %s" % (str(r.get("alt") or "?")[:30],
                                                                        str(r.get("photographer") or "?"), r.get("url") or "")})
    return out, None


def search(query: str = "", source: str = "openverse", n: int = 12, min_width: int = DEFAULT_MIN_W,
           min_height: int = DEFAULT_MIN_H, aspect: str = "any", license: str = "any",
           extension: str = "jpg", **_kw) -> dict:
    q = str(query or "").strip()
    if not q:
        return {"ok": False, "op": "search", "reason": "需要 query（搜什么）",
                "可用": "cap image_scout '{\"op\":\"search\",\"query\":\"golden hour portrait\"}'"}
    src = str(source or "openverse").lower()
    lic = "" if str(license or "any").lower() == "any" else str(license)
    errs = {}
    got = []
    if src in ("openverse", "default"):
        rows, e = _search_openverse(q, n, int(min_width), int(min_height), str(aspect), lic, str(extension))
        got += rows
        if e:
            errs["openverse"] = e
    if src in ("unsplash", "all"):
        rows, e = _search_unsplash(q, n)
        got += [r for r in rows if r["width"] >= int(min_width) and r["height"] >= int(min_height)]
        if e:
            errs["unsplash"] = e
    if src in ("pexels", "all"):
        rows, e = _search_pexels(q, n)
        got += [r for r in rows if r["width"] >= int(min_width) and r["height"] >= int(min_height)]
        if e:
            errs["pexels"] = e
    return {"ok": bool(got), "op": "search", "query": q, "source": src,
            "门槛": {"min_width": int(min_width), "min_height": int(min_height),
                   "aspect": aspect, "license": str(license), "extension": str(extension)},
            "count": len(got), "candidates": got[: max(1, min(40, int(n)))],
            "未读到": (errs or "无"),
            "_口径": "只给候选与许可+署名；**不下载图片字节**（落盘走写面能力位）",
            "_实测说明": "Openverse 索引尺寸常 ≤1024 宽（字段真值）；要更大原图请在候选原页取或改用 Unsplash/Pexels"}


def curate(items=None, k: int = 5, bias_ratio: float = 0.0, prefer_license: str = "cc0", **_kw) -> dict:
    """对 search 的候选做**质量排序**：分辨率×比例契合（bias_ratio 指定偏好的宽高比）×许可优先级。"""
    rows = items if isinstance(items, list) else []
    if not rows:
        return {"ok": False, "op": "curate", "reason": "需要 items（把 search 的 candidates 传回来）"}

    def score(r: dict) -> float:
        w, h = int(r.get("width") or 0), int(r.get("height") or 0)
        px = (w * h) / 1e6
        fit = 1.0
        try:
            if bias_ratio:
                fit = 1.0 / (1.0 + abs(float(r.get("ratio") or 0) - float(bias_ratio)))
        except Exception:                                            # noqa: BLE001
            fit = 1.0
        lic = str(r.get("license") or "").lower()
        lic_bonus = 0.25 if (prefer_license and prefer_license.lower() in lic) else 0.0
        return px * 0.5 + fit * 0.8 + lic_bonus

    ranked = sorted(rows, key=score, reverse=True)[: max(1, int(k))]
    return {"ok": bool(ranked), "op": "curate", "count": len(ranked),
            "picks": ranked,
            "_口径": "分数=像素量0.5+比例契合0.8+许可优先0.25；只排序不下载"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "image_scout",
            "entry": "py -3.14 tools/codex-scripts/five-dim.py cap image_scout '{\"op\":\"search\",\"query\":\"...\"}'",
            "ops": list(OPS),
            "what": "美图精准抓取：多源（Openverse/Unsplash/Pexels）+ 质量/许可门槛 + 署名行；只给候选 URL",
            "接棒": "修饰/放大 → `cap zimage_rewash '{\"op\":\"upscale\",\"src\":...}'`；落盘 → 写面能力位",
            "sources": [s["id"] for s in sources()["sources"]]}


def run_op(op: str = "status", **kw) -> dict:
    table = {"status": status, "sources": sources, "search": search, "curate": curate, "where": where}
    fn = table.get(str(op or "status").strip().lower())
    if fn is None:
        return {"ok": False, "op": op, "status": "unknown_op", "available": sorted(table),
                "_口径": "未知 op 一律拒，不猜"}
    return fn(**kw)
