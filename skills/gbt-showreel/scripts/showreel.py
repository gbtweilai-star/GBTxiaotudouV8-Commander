#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""showreel.design 操作器 —— 把「用这个站」变成可复跑的命令，而不是每次现写爬虫。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

契约全文见 ../references/site-contract.md（2026-10-13 实探）。摘要：

  GET /api/videos.json           248 条 · slug title author authorAvatar category description
                                 tags year industries[] styles[] soundMusic[] thumbnailUrl publishDate
  GET /api/launch.json            21 条 · slug title brand studio description tags thumbnailUrl
  GET /api/logo-animations.json  139 条 · file brand agency
  GET /api/resources.json         13 条 · name type description href logo tags

  ⚠️ 成片 mp4 **不可推导**：只有 /videos/<slug>（或 /launch/<slug>）页面里的
     <script type="application/ld+json"> 才带 contentUrl 与 author.url（工作室官网）。
  ⚠️ 列表页的 data-video-url 是**几秒循环预览**（Thumbnails/*.mp4），不是成片。
  ✅ 静帧海报可推导：thumbnailUrl 尾巴 `thumbnail_videos_<tail>.mp4`
     ⇒ https://video.showreel.design/Posters/poster_videos_<tail>.jpg
     全量实测（2026-10-13 · 248 条逐条）：规则 248/248 适用 · HEAD 200 = 245 · GET 200 = 242。
     另外 6 条**按对象确定性**取不到（不是抖动），分两类：3 条 HEAD 就 404（对象不存在）、
     3 条 HEAD 200 但 GET 404（元数据在、对象取不到）。
     ⇒ 脚本按 best-effort 处理：GET 回 404 就自动回退到预览 mp4，不假装成功。

用法：
    python showreel.py catalog [--refresh]
    python showreel.py taxonomy
    python showreel.py query --style cinematic-dramatic --industry tech-saas --limit 8
    python showreel.py query --q "logo animation" --sort date --json
    python showreel.py resolve frog-showreel-2026            # → contentUrl + 官网
    python showreel.py get frog-showreel-2026 --kind poster  # 静帧（默认，小）
    python showreel.py get frog-showreel-2026 --kind reel --dry-run
    python showreel.py verify                                # 重跑契约断言

口径：本脚本只做「取参考」。成片是第三方工作室的作品 ⇒ 可看不可发（见 SKILL.md 边界）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):          # 本机默认 GBK：不reconfigure 会 UnicodeDecodeError
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SITE = "https://showreel.design"
CDN = "https://video.showreel.design"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

FEEDS = {
    "videos": f"{SITE}/api/videos.json",
    "launch": f"{SITE}/api/launch.json",
    "logos": f"{SITE}/api/logo-animations.json",
    "resources": f"{SITE}/api/resources.json",
}

_LAST_CALL = [0.0]
DELAY = [0.2]


# ── 网络 ──────────────────────────────────────────────────────────────────────

def _throttle() -> None:
    gap = time.time() - _LAST_CALL[0]
    if gap < DELAY[0]:
        time.sleep(DELAY[0] - gap)
    _LAST_CALL[0] = time.time()


def http(url: str, method: str = "GET", timeout: int = 45):
    """返回 (status, headers, body_bytes)。HTTP 错误也返回状态码而不是抛异常。"""
    url = quote_url(url)
    _throttle()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), (b"" if method == "HEAD" else resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), b""
    except Exception as exc:                                     # noqa: BLE001
        return 0, {"error": f"{type(exc).__name__}: {exc}"}, b""


def get_json(url: str):
    status, headers, body = http(url)
    if status != 200:
        raise SystemExit(f"🔴 GET {url} → {status} {headers.get('error', '')}")
    return json.loads(body.decode("utf-8"))


def quote_url(url: str) -> str:
    """把 URL 路径里的空格/非 ASCII 编码掉，但**保留已有的 %XX 与分隔符**。

    为什么必须有（2026-10-13 实测）：详情页 JSON-LD 的 contentUrl 里是**裸空格**
    （`.../videos/Frog showreel 2026.mp4`）—— 不编码的话 HEAD 拿不到 Content-Length，
    dry-run 里大小一路显示 `?`，看起来像"站点没给"。
    """
    return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")


# ── 缓存 ─────────────────────────────────────────────────────────────────────

def cache_dir(override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser()
    env = os.environ.get("GBT_SHOWREEL_CACHE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "showreel"


def load_catalog(refresh: bool, cache: str | None, feeds=("videos", "launch", "logos", "resources")):
    root = cache_dir(cache)
    root.mkdir(parents=True, exist_ok=True)
    out = {}
    for name in feeds:
        path = root / f"api-{name}.json"
        if refresh or not path.exists():
            data = get_json(FEEDS[name])
            path.write_text(json.dumps(
                {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "source": FEEDS[name], "items": data},
                ensure_ascii=False), encoding="utf-8")
        blob = json.loads(path.read_text(encoding="utf-8"))
        out[name] = blob
    return out


def _age(iso: str) -> str:
    try:
        t = datetime.fromisoformat(iso)
    except Exception:                                            # noqa: BLE001
        return "?"
    secs = int((datetime.now(timezone.utc) - t).total_seconds())
    return f"{secs // 60} 分钟前" if secs < 3600 else f"{secs // 3600} 小时前"


# ── 小工具 ────────────────────────────────────────────────────────────────────

def sha16(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16].upper()


def human(n) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return "?"


def _sluggify(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "item"


def poster_url(thumbnail_url: str) -> str | None:
    """缩略 mp4 → 静帧 jpg。规则：thumbnail_<group>_<tail>.mp4 ⇒ Posters/poster_<group>_<tail>.jpg"""
    if not thumbnail_url:
        return None
    tail = urllib.parse.unquote(thumbnail_url.rsplit("/", 1)[-1])
    m = re.match(r"^thumbnail_(.+?)_(.+)\.mp4$", tail)
    if not m:
        return None
    group, rest = m.group(1), m.group(2)
    return f"{CDN}/Posters/poster_{group}_{urllib.parse.quote(rest)}.jpg"


def _taxonomy_values(items, field):
    seen = {}
    for item in items:
        val = item.get(field)
        for v in (val if isinstance(val, list) else [val]):
            if v in (None, ""):
                continue
            seen.setdefault(str(v), 0)
            seen[str(v)] += 1
    return dict(sorted(seen.items(), key=lambda kv: (-kv[1], kv[0].lower())))


# ── 命令 ─────────────────────────────────────────────────────────────────────

def cmd_catalog(args) -> int:
    blob = load_catalog(args.refresh, args.cache)
    rows = []
    for name, data in blob.items():
        rows.append((name, len(data["items"]), _age(data["fetched_at"]), data["source"]))
    if args.json:
        print(json.dumps({n: {"count": c, "fetched_at": blob[n]["fetched_at"], "source": s}
                          for n, c, _a, s in rows}, ensure_ascii=False, indent=2))
        return 0
    print(f"缓存：{cache_dir(args.cache)}")
    print(f"{'feed':<10}{'条数':>6}   拉取时间")
    for name, count, age, _src in rows:
        print(f"{name:<10}{count:>6}   {age}")
    if not args.refresh:
        print("（读的是本地缓存；要对齐站点现状加 --refresh）")
    return 0


def cmd_taxonomy(args) -> int:
    blob = load_catalog(False, args.cache)
    videos = blob["videos"]["items"]
    tax = {
        "category": _taxonomy_values(videos, "category"),
        "styles": _taxonomy_values(videos, "styles"),
        "industries": _taxonomy_values(videos, "industries"),
        "soundMusic": _taxonomy_values(videos, "soundMusic"),
        "year": _taxonomy_values(videos, "year"),
        "tags": _taxonomy_values(videos, "tags"),
    }
    if args.json:
        print(json.dumps(tax, ensure_ascii=False, indent=2))
        return 0
    for field, values in tax.items():
        print(f"\n{field}（{len(values)}）")
        for val, count in values.items():
            print(f"   {val:<28} {count}")
    return 0


def _match_list(item_value, wanted: str) -> bool:
    vals = item_value if isinstance(item_value, list) else [item_value]
    want = wanted.strip().lower()
    return any(want == str(v).strip().lower() for v in vals if v)


def cmd_query(args) -> int:
    blob = load_catalog(False, args.cache)
    feed = args.feed
    items = list(blob[feed]["items"])

    if args.category:
        items = [i for i in items if _match_list(i.get("category"), args.category)]
    if args.style:
        items = [i for i in items if _match_list(i.get("styles"), args.style)]
    if args.industry:
        items = [i for i in items if _match_list(i.get("industries"), args.industry)]
    if args.sound:
        items = [i for i in items if _match_list(i.get("soundMusic"), args.sound)]
    if args.year:
        items = [i for i in items if str(i.get("year")) == str(args.year)]
    if args.tag:
        items = [i for i in items if _match_list(i.get("tags"), args.tag)]
    if args.q:
        needle = args.q.lower()
        def haystack(item):
            parts = []
            for key in ("title", "author", "brand", "studio", "agency", "category",
                        "description", "file", "name"):
                parts.append(str(item.get(key) or ""))
            for key in ("tags", "styles", "industries", "soundMusic"):
                val = item.get(key)
                parts.append(" ".join(str(v) for v in val) if isinstance(val, list) else str(val or ""))
            return " ".join(parts).lower()
        items = [i for i in items if needle in haystack(i)]

    if args.sort == "title":
        items.sort(key=lambda i: str(i.get("title") or i.get("name") or "").lower())
    elif args.sort == "author":
        items.sort(key=lambda i: str(i.get("author") or i.get("brand") or "").lower())
    else:
        items.sort(key=lambda i: str(i.get("publishDate") or ""), reverse=True)

    total = len(items)
    if args.limit:
        items = items[:args.limit]

    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0
    print(f"命中 {total} 条（显示 {len(items)}）· feed={feed} · 缓存 {_age(blob[feed]['fetched_at'])}")
    for idx, item in enumerate(items, 1):
        name = item.get("title") or item.get("name") or item.get("file")
        who = item.get("author") or item.get("studio") or item.get("brand") or item.get("agency") or ""
        marks = []
        if item.get("styles"):
            marks.append("/".join(item["styles"]))
        if item.get("industries"):
            marks.append("/".join(item["industries"]))
        if item.get("soundMusic"):
            marks.append("/".join(item["soundMusic"]))
        date = str(item.get("publishDate") or "")[:10]
        print(f"\n[{idx}] {name}")
        print(f"    作者/品牌：{who}    {date}    {item.get('category') or item.get('type') or ''}")
        if item.get("slug"):
            print(f"    页面：{SITE}/videos/{item['slug']}" if feed == "videos" else f"    页面：{SITE}/launch/{item['slug']}")
        if marks:
            print(f"    标签：{' · '.join(marks)}")
    return 0


def cmd_resolve(args) -> int:
    blob = load_catalog(False, args.cache)
    feed = args.feed
    entry = next((i for i in blob[feed]["items"] if i.get("slug") == args.slug), None)
    page = f"{SITE}/videos/{args.slug}" if feed == "videos" else f"{SITE}/launch/{args.slug}"
    status, headers, body = http(page)
    if status != 200:
        raise SystemExit(f"🔴 {page} → {status} {headers.get('error', '')}")
    html = body.decode("utf-8", "replace")
    m = re.search(r'<script type="application/ld\+json">([\s\S]*?)</script>', html)
    ld = json.loads(m.group(1)) if m else {}
    author = ld.get("author") or {}
    # launch 的 JSON-LD **没有 author**（只有 publisher=Showreel.design 自己），
    # 真实作者在 API 条目的 brand / studio 里 —— 不回退的话这里会打出刺眼的 `None`。
    who = (author.get("name") or (entry or {}).get("author")
           or (entry or {}).get("studio") or (entry or {}).get("brand"))
    out = {
        "slug": args.slug,
        "page": page,
        "title": ld.get("name") or (entry or {}).get("title"),
        "author": who,
        "author_url": author.get("url"),
        "content_url": ld.get("contentUrl"),
        "upload_date": ld.get("uploadDate"),
        "description": (ld.get("description") or (entry or {}).get("description") or "").strip(),
        "category": (entry or {}).get("category"),
        "styles": (entry or {}).get("styles"),
        "industries": (entry or {}).get("industries"),
        "soundMusic": (entry or {}).get("soundMusic"),
        "tags": (entry or {}).get("tags"),
        "year": (entry or {}).get("year"),
        "poster_url": poster_url((entry or {}).get("thumbnailUrl", "")),
        "preview_url": (entry or {}).get("thumbnailUrl"),
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    if not ld:
        print("🔴 详情页里没找到 ld+json —— 站点结构可能变了，跑 `verify`")
    print(f"片名   : {out['title']}")
    print(f"作者   : {out['author']}   官网：{out['author_url'] or '（本条 JSON-LD 没有官网字段）'}")
    print(f"成片   : {out['content_url']}")
    print(f"静帧   : {out['poster_url']}")
    print(f"预览   : {out['preview_url']}")
    desc = out["description"]
    if desc:
        print(f"简介   : {desc[:300]}{'…' if len(desc) > 300 else ''}")
    return 0


def _download(url: str, dest: Path, dry_run: bool, max_mb: float | None, assume_yes: bool) -> int:
    status, headers, _ = http(url, method="HEAD")
    size = headers.get("Content-Length")
    if dry_run:
        print(f"  would GET {url}\n            → {dest}  大小 {human(size)}")
        return 0
    if status != 200:
        print(f"  🔴 HEAD {url} → {status} {headers.get('error', '')}")
        return 1
    if size and max_mb and float(size) > max_mb * 1024 * 1024 and not assume_yes:
        print(f"  ⛔ 体积 {human(size)} 超过 --max-mb {max_mb}（要下就加 --yes）")
        return 2
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    status, headers, body = http(url, timeout=600)
    if status != 200:
        print(f"  🔴 GET {url} → {status}"
              "（HEAD 说 200、GET 不成 —— 本站海报确有这种档，且是**按对象确定性**的，不是抖动）")
        return 3
    part.write_bytes(body)
    if size and len(body) != int(size):
        print(f"  🔴 字节数不符：拿到 {len(body)} / 声明 {size}")
        return 1
    part.replace(dest)
    if dest.stat().st_size == 0:
        print("  🔴 落盘 0 字节")
        return 1
    print(f"  ✅ {dest}   {human(dest.stat().st_size)}   sha256:{sha16(dest)}")
    return 0


def cmd_get(args) -> int:
    blob = load_catalog(False, args.cache)
    feed = args.feed
    entry = next((i for i in blob[feed]["items"] if i.get("slug") == args.slug), None)
    if entry is None:
        raise SystemExit(f"🔴 {feed} 目录里没有 slug={args.slug}（先跑 `catalog --refresh`）")
    thumb = entry.get("thumbnailUrl") or ""
    outdir = Path(args.out).expanduser()
    author = _sluggify(str(entry.get("author") or entry.get("studio")
                            or entry.get("brand") or "unknown"))
    stamp = datetime.now().strftime("%Y%m%d")

    if args.kind == "poster":
        url = poster_url(thumb)
        if not url:
            print("🔴 这条推不出静帧 URL；改用 --kind preview")
            return 1
        dest = outdir / f"{stamp}_{args.slug}__{author}.jpg"
        rc = _download(url, dest, args.dry_run, args.max_mb, True)
        if rc == 3 and not args.dry_run:
            print("  ↪ 静帧取不到（本站 Posters 批量半坏）⇒ 回退取预览 mp4：")
            dest = outdir / f"{stamp}_{args.slug}__{author}_preview.mp4"
            return _download(thumb, dest, args.dry_run, args.max_mb, True)
        return rc

    if args.kind == "preview":
        dest = outdir / f"{stamp}_{args.slug}__{author}_preview.mp4"
        return _download(thumb, dest, args.dry_run, args.max_mb, True)

    page = f"{SITE}/videos/{args.slug}" if feed == "videos" else f"{SITE}/launch/{args.slug}"
    status, headers, body = http(page)
    if status != 200:
        print(f"🔴 详情页 {page} → {status}")
        return 1
    m = re.search(r'<script type="application/ld\+json">([\s\S]*?)</script>',
                  body.decode("utf-8", "replace"))
    reel = json.loads(m.group(1)).get("contentUrl") if m else None
    if not reel:
        print("🔴 详情页里没拿到 contentUrl")
        return 1
    ext = Path(urllib.parse.urlparse(reel).path).suffix or ".mp4"
    dest = outdir / f"{stamp}_{args.slug}__{author}_reel{ext}"
    print(f"成片（第三方作品，只作参考）：{reel}")
    return _download(reel, dest, args.dry_run, args.max_mb, args.yes)


def cmd_logo(args) -> int:
    """logo 演绎：目录条目没有 slug，只有 `file`（= `<Brand>--<Agency>.mp4`）。

    资源直链 = `https://video.showreel.design/Logo Animation/<file>`（整个路径要 percent-encode）。
    """
    what = args.match.strip().lower()
    items = load_catalog(False, args.cache)["logos"]["items"]
    hits = [i for i in items
            if what in str(i.get("brand", "")).lower()
            or what in str(i.get("agency", "")).lower()
            or what in str(i.get("file", "")).lower()]
    if not hits:
        raise SystemExit(f"🔴 logo 目录里没有匹配 {args.match!r} 的条目（共 {len(items)} 条）")
    if len(hits) > 1:
        exact = [i for i in hits if what == str(i.get("brand", "")).lower()]
        if len(exact) != 1:
            print(f"命中 {len(hits)} 条，给具体点（用品牌名）：")
            for i in hits[:12]:
                print(f"   {i['brand']:<20} — {i['agency']}")
            return 1
        hits = exact
    item = hits[0]
    url = f"{CDN}/Logo Animation/{item['file']}"
    author = _sluggify(str(item.get("brand") or "brand"))
    dest = Path(args.out).expanduser() / f"{datetime.now():%Y%m%d}_logo_{author}.mp4"
    print(f"logo 演绎（第三方作品，只作参考）：{item['brand']} — {item['agency']}")
    return _download(url, dest, args.dry_run, args.max_mb, args.yes)


def cmd_verify(args) -> int:
    """重跑契约断言：站点结构变了要当场响，而不是等下次调用才发现拿不到东西。"""
    checks = []
    notes = []

    for name, feed in FEEDS.items():
        status, _h, body = http(feed)
        ok = status == 200
        count = 0
        if ok:
            try:
                count = len(json.loads(body.decode("utf-8")))
            except Exception:                                    # noqa: BLE001
                ok = False
        checks.append((f"① /api/{name}.json 可达且是数组", ok, f"{status} · {count} 条"))

    blob = load_catalog(True, args.cache, feeds=("videos",))
    videos = blob["videos"]["items"]
    expected = {"slug", "title", "author", "category", "styles", "industries",
                "soundMusic", "tags", "year", "thumbnailUrl", "publishDate"}
    missing = sorted(expected - set(videos[0].keys())) if videos else ["<空>"]
    checks.append(("② videos 条目字段齐全", not missing, f"缺 {missing}" if missing else "11 个字段都在"))

    sample = videos[0]["slug"] if videos else None
    if sample:
        status, _h, body = http(f"{SITE}/videos/{sample}")
        ld = re.search(r'<script type="application/ld\+json">([\s\S]*?)</script>',
                       body.decode("utf-8", "replace"))
        obj = json.loads(ld.group(1)) if ld else {}
        has = bool(obj.get("contentUrl"))
        checks.append(("③ 详情页 JSON-LD 带 contentUrl", has, str(obj.get("contentUrl"))[:90]))
        checks.append(("④ 详情页 JSON-LD 带 author.url", bool((obj.get("author") or {}).get("url")),
                       str((obj.get("author") or {}).get("url"))))

    # ⑤ 静帧海报：**只报不判**。理由（2026-10-13 全量实测）：规则 248/248 适用，
    #    但拿 HEAD 当"能取到"就是假绿 —— 实测有 3 条 HEAD 200 而 GET 404，
    #    另有 3 条 HEAD 也 404；**按对象确定性**，不是抖动（同一对象连测 3 次结果一致）。
    #    ⇒ 这里做真 GET，把真实命中率摆出来，**不参与通过/不通过**；--posters-all 才扫全量。
    n = len(videos) if args.posters_all else 8
    step = max(1, len(videos) // max(1, n))
    sample_items = videos[::step][:n] if videos else []
    head_ok = get_ok = 0
    for item in sample_items:
        url = poster_url(item.get("thumbnailUrl", ""))
        if not url:
            continue
        status, _h, _b = http(url, method="HEAD")
        head_ok += 1 if status == 200 else 0
        status, _h, _b = http(url, method="GET", timeout=30)
        get_ok += 1 if status == 200 else 0
    notes.append(f"⑤ 静帧海报（Posters/*.jpg）：规则对 {len(videos)} 条**全部适用**；本器真 GET "
                 f"{len(sample_items)} 条 ⇒ HEAD {head_ok}/{len(sample_items)} · "
                 f"GET {get_ok}/{len(sample_items)}"
                 + ("" if args.posters_all else "（全量基线 2026-10-13：HEAD 245/248 · GET 242/248）")
                 + " · 取不到是**按对象确定性**的 ⇒ `get --kind poster` 失败会自动回退 preview")

    reel = None
    if sample:
        _s, _h, body = http(f"{SITE}/videos/{sample}")
        ld = re.search(r'<script type="application/ld\+json">([\s\S]*?)</script>',
                       body.decode("utf-8", "replace"))
        reel = json.loads(ld.group(1)).get("contentUrl") if ld else None
    if reel:
        status, headers, _ = http(reel, method="HEAD")
        checks.append(("⑥ 成片 mp4 支持 Range（可断点/只取前段）",
                       status == 200 and headers.get("Accept-Ranges") == "bytes",
                       f"{status} · {human(headers.get('Content-Length'))} · ranges={headers.get('Accept-Ranges')}"))

    bad = [c for c in checks if not c[1]]
    if args.json:
        print(json.dumps({"checks": [{"check": c, "ok": o, "detail": d} for c, o, d in checks],
                          "notes": notes,
                          "passed": len(checks) - len(bad), "total": len(checks)},
                         ensure_ascii=False, indent=2))
    else:
        print("showreel.design 契约自检")
        for name, ok, detail in checks:
            print(f"  {'✅' if ok else '🔴'} {name}   {detail}")
        for note in notes:
            print(f"  ⚠️ {note}")
        print(f"\n结论：{len(checks) - len(bad)}/{len(checks)} 通过")
        if bad:
            print("🔴 有断言不成立 ⇒ 先改 references/site-contract.md 再动这条技能，别硬用。")
    return 1 if bad else 0


# ── main ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="showreel.design 操作器")
    ap.add_argument("--cache", help="缓存目录（默认 ~/.cache/showreel 或 $GBT_SHOWREEL_CACHE）")
    ap.add_argument("--delay", type=float, default=0.2, help="两次请求之间的最小间隔秒（默认 0.2）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("catalog", help="拉/看四个 API 的本地缓存")
    p.add_argument("--refresh", action="store_true", help="强制重新拉取")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_catalog)

    p = sub.add_parser("taxonomy", help="现算全部可筛选值")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_taxonomy)

    p = sub.add_parser("query", help="本地过滤目录（不进网）")
    p.add_argument("--feed", choices=list(FEEDS), default="videos")
    p.add_argument("--category")
    p.add_argument("--style")
    p.add_argument("--industry")
    p.add_argument("--sound")
    p.add_argument("--year")
    p.add_argument("--tag")
    p.add_argument("--q", help="关键词（标题/作者/简介/标签，忽略大小写）")
    p.add_argument("--sort", choices=["date", "title", "author"], default="date")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("resolve", help="单条 → 成片 mp4 + 工作室官网（读详情页 JSON-LD）")
    p.add_argument("slug")
    p.add_argument("--feed", choices=["videos", "launch"], default="videos")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("get", help="落盘：静帧 / 预览 / 成片")
    p.add_argument("slug")
    p.add_argument("--feed", choices=["videos", "launch"], default="videos")
    p.add_argument("--kind", choices=["poster", "preview", "reel"], default="poster")
    p.add_argument("--out", default="./showreel-refs")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-mb", type=float, default=5.0, help="超过就拦（成片默认要 --yes）")
    p.add_argument("--yes", action="store_true", help="确认下大文件")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("logo", help="落盘 logo 演绎（按品牌/代理机构匹配）")
    p.add_argument("match", help="品牌名 / 代理机构 / 文件名片段（忽略大小写）")
    p.add_argument("--out", default="./showreel-refs")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-mb", type=float, default=5.0)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_logo)

    p = sub.add_parser("verify", help="重跑站点契约断言")
    p.add_argument("--json", action="store_true")
    p.add_argument("--posters-all", action="store_true",
                   help="海报那一条改成扫全量（默认只抽 8 条，全量约 3 分钟）")
    p.set_defaults(func=cmd_verify)

    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    DELAY[0] = max(0.0, args.delay)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
