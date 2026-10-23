# gbt-capability: filesystem
"""六环里的第 1 环：采集。

一个源一次采集 = 三件事，**分开写、不许合并**：

    结局   state/runs/<id>.json     成功和失败**都写**。失败只有结局，没有水位。
    水位   state/last_seen.json     **只写成功**。失败一个字节都不许碰它（判据 D）。
    入库   state/signals.jsonl      采到的信号一律过判据 F 的闸（缺 url 拒收）。

四条自制：

1. 没实现这个源 -> **什么都不写**。留「已登记 · 未采集」是如实的；
   写一条 outcome=failed 会把「没有代码」冒充成「采集失败」，那是谎报。
2. 单条拉不到只跳过这一条，不毁整轮。
3. 缺 url 的记录本采集器自己就不产它 —— 与其让入库闸拒收，不如根本不产出。
4. 请求 URL 一律走 urlencode（无害且正确），但**别把它当成 arXiv 406 的解**：
   实测（.scratch/_r35 + _r36）**缓存命中 -> 200，缓存里没有 -> 406**，与编码、参数、
   Accept、UA 全部无关（热形状带一个荒谬的 Accept 照样 200）。本模块仍然不发
   sortBy / sortOrder、倒序放在客户端，但那是**风格选择，不是解法**：换一个从没被
   缓存过的形状（例如 max_results=2）立刻 406。真因未定，见 memory/2026-09-18.md。

用法：

    python holo_pet/research/collector.py                  # 只跑已实现的源
    python holo_pet/research/collector.py --only arxiv      # 只跑一个
    python holo_pet/research/collector.py --limit 5 --timeout 30
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
HOLO = HERE.parent
STATE = ROOT / "state"
RUNS = STATE / "runs"
LAST_SEEN = STATE / "last_seen.json"
SIGNALS = STATE / "signals.jsonl"
SOURCES = ROOT / "sources.json"

for _p in (str(HOLO), str(ROOT / "gbt_allinone")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import signal_ingest  # noqa: E402

try:
    import safe_io
except ImportError:  # pragma: no cover
    safe_io = None

UA = "gbt-xiaotudou-research/1.0"
DEFAULT_TIMEOUT = 20.0


def _now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _get(url, *, timeout, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


# ---- 三个源 ----

def collect_arxiv(row, *, timeout, limit):
    # sortBy / sortOrder 一律不发：实测这是 406 的唯一判别量（值无关）。
    params = {"search_query": "all:electron", "start": 0, "max_results": limit}
    url = str(row.get("endpoint") or "").rstrip("?") + "?" + urllib.parse.urlencode(params)
    _, body = _get(url, timeout=timeout)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(body)
    out = []
    for entry in root.findall("a:entry", ns):
        link = (entry.findtext("a:id", "", ns) or "").strip()
        if not link:
            continue
        out.append({
            "id": "arxiv-" + link.rsplit("/", 1)[-1],
            "url": link,
            "title": " ".join((entry.findtext("a:title", "", ns) or "").split()),
            "source": "arxiv",
            "published_at": (entry.findtext("a:published", "", ns) or "").strip(),
        })
    # 服务端排序被 406 挡死，倒序改在这里做。
    out.sort(key=lambda r: r["published_at"], reverse=True)
    return out


def collect_hackernews(row, *, timeout, limit):
    endpoint = str(row.get("endpoint") or "")
    base = endpoint.rsplit("/", 1)[0]
    _, body = _get(endpoint, timeout=timeout)
    ids = json.loads(body)
    if not isinstance(ids, list):
        raise ValueError("topstories 不是数组")
    # 每个 item 一次请求，所以 N 就是请求数 —— 首轮写死 10，不拿额度赌。
    out = []
    for sid in ids[:max(1, min(limit, 10))]:
        try:
            _, item_body = _get("%s/item/%s.json" % (base, sid), timeout=timeout)
            item = json.loads(item_body)
        except (urllib.error.URLError, OSError, ValueError):
            continue
        if not isinstance(item, dict) or item.get("type") != "story":
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue  # 缺 url 的（Ask HN 那类）本采集器不产它
        out.append({
            "id": "hn-%s" % sid,
            "url": url,
            "title": str(item.get("title") or ""),
            "source": "hackernews",
            "points": item.get("score"),
            "comments": item.get("descendants"),
            "discussion": "https://news.ycombinator.com/item?id=%s" % sid,
        })
    return out


def collect_github(row, *, timeout, limit):
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    params = {"q": "stars:>500 pushed:>%s" % since, "sort": "stars", "order": "desc",
              "per_page": max(1, min(limit, 30))}
    url = str(row.get("endpoint") or "") + "?" + urllib.parse.urlencode(params)
    _, body = _get(url, timeout=timeout,
                   headers={"Accept": "application/vnd.github+json"})
    doc = json.loads(body)
    out = []
    for item in (doc.get("items") or []):
        html = str(item.get("html_url") or "").strip()
        if not html:
            continue
        out.append({
            "id": "gh-%s" % item.get("id"),
            "url": html,
            "title": str(item.get("full_name") or ""),
            "source": "github",
            "stars": item.get("stargazers_count"),
            "pushed_at": str(item.get("pushed_at") or ""),
        })
    return out


COLLECTORS = {"arxiv": collect_arxiv, "hackernews": collect_hackernews,
              "github": collect_github}


# ---- 一轮 ----

def run_source(row, *, timeout=DEFAULT_TIMEOUT, limit=None):
    """跑一个源 -> (结局文档, 信号列表)。**只返回，不落盘**（落盘是调用方的事）。"""
    sid = str(row.get("id") or "")
    limit = int(limit if limit is not None else (row.get("limit_per_run") or 20))
    doc = {"id": sid, "started_at": _now_iso(), "finished_at": "", "outcome": "",
           "http": None, "reason": "", "items": None, "attempts": 1}
    records = []
    fn = COLLECTORS[sid]
    try:
        records = fn(row, timeout=timeout, limit=limit)
        doc["outcome"] = "ok"
        doc["http"] = 200
        doc["items"] = len(records)
    except urllib.error.HTTPError as exc:
        doc["outcome"] = "failed"
        doc["http"] = exc.code
        doc["reason"] = "HTTP %d：%s" % (exc.code, str(getattr(exc, "reason", ""))[:100])
    except urllib.error.URLError as exc:
        doc["outcome"] = "failed"
        doc["reason"] = "连接失败：%s" % str(getattr(exc, "reason", ""))[:140]
    except (OSError, ValueError) as exc:
        doc["outcome"] = "failed"
        doc["reason"] = "%s：%s" % (type(exc).__name__, str(exc)[:140])
    doc["finished_at"] = _now_iso()
    return doc, records


def _write_json(path, payload):
    if safe_io is not None:
        safe_io.atomic_write_json(path, payload)
    else:  # pragma: no cover
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_sources(path=SOURCES):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("sources.json 顶层不是对象")
    rows = doc.get("research")
    if not isinstance(rows, list):
        raise ValueError("sources.json 的 research 不是数组")
    return [r for r in rows if isinstance(r, dict) and str(r.get("id") or "").strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description="调研信源采集器（六环第 1 环）")
    ap.add_argument("--only", default="", help="只跑指定的源 id，逗号分隔")
    ap.add_argument("--limit", type=int, default=0, help="覆盖 limit_per_run")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    ap.add_argument("--sources", default=str(SOURCES))
    args = ap.parse_args(argv)

    RUNS.mkdir(parents=True, exist_ok=True)
    wanted = {s.strip().lower() for s in args.only.split(",") if s.strip()}

    rows = load_sources(args.sources)
    watermark = {}
    if LAST_SEEN.is_file():
        try:
            blob = json.loads(LAST_SEEN.read_text(encoding="utf-8"))
            watermark = blob if isinstance(blob, dict) else {}
        except ValueError:
            watermark = {}

    print("[collector] 登记 %d 个源；本次实现的只有 %d 个：%s"
          % (len(rows), len(COLLECTORS), ", ".join(sorted(COLLECTORS))))
    skipped, ran = [], 0
    for row in rows:
        sid = str(row["id"]).strip().lower()
        if wanted and sid not in wanted:
            continue
        if not row.get("enabled"):
            skipped.append((sid, "未启用（enabled=false）"))
            continue
        if sid not in COLLECTORS:
            # 没实现就不写：留「已登记 · 未采集」，不冒充「采集失败」。
            skipped.append((sid, "本采集器未实现，不写盘（保持未采集）"))
            continue
        doc, records = run_source(row, timeout=args.timeout, limit=args.limit or None)
        _write_json(RUNS / ("%s.json" % sid), doc)
        ran += 1
        line = "[collector] %-12s outcome=%s http=%s items=%s %s" % (
            sid, doc["outcome"], doc["http"], doc["items"], doc["reason"])
        print(line)
        if doc["outcome"] == "ok":
            # 水位只记最后一次成功 —— 失败不动它。
            watermark[sid] = {"at": doc["finished_at"], "items": doc["items"]}
            res = signal_ingest.ingest(records, path=SIGNALS, stream=sys.stdout)
            print("[collector] %-12s 入库 offered=%d written=%d rejected=%d codes=%s"
                  % (sid, res["offered"], res["written"], res["rejected"], res["codes"]))

    if ran:
        _write_json(LAST_SEEN, watermark)
        print("[collector] 水位已更新：%s" % ", ".join(sorted(watermark)))
    for sid, why in skipped:
        print("[collector] 跳过 %-12s %s" % (sid, why))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
