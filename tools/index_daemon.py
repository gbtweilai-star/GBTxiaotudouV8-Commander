# -*- coding: utf-8 -*-
"""常驻索引层 · 索引载一次，之后每次查只走回环 socket（毫秒级）

为什么要有它：
  磁盘索引每次查询都要 grep 式载入 505 KB（gzip→JSON，约 216 ms）。
  那 216 ms 是「固定成本」，付一次就够 —— 常驻进程把它摊掉。

口径（照旧不吹）：
  · 只绑 127.0.0.1，不出网；只读，不写任何文件。
  · 读不到索引就如实报缺，不编。

用法：
  python3 tools/index_daemon.py serve [--port 8792] [--bg]
  python3 tools/index_daemon.py ping
  python3 tools/index_daemon.py find <词>
  python3 tools/index_daemon.py page <一句话>
  python3 tools/index_daemon.py stop
"""
from __future__ import annotations
import gzip, json, os, socket, sys, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISK = ROOT / "state" / "disk_index.json.gz"
BIND = ROOT / "state" / "bind"
MANIFEST = BIND / "manifest.json"
SHARDS = BIND / "shards"
PORT = int(os.environ.get("GBT_INDEX_PORT", "8792"))

_STATE = {"disk": None, "man": None, "inv": None, "loaded_at": 0.0}
_TOK = None


def _tok(s: str):
    """路径切词：按 / _ - . 和数字边界切，全部小写。"""
    import re
    return [t for t in re.split(r"[/_.\-\d]+", s.lower()) if t]


def load_all():
    t0 = time.time()
    if DISK.is_file():
        with gzip.open(DISK, "rb") as f:
            _STATE["disk"] = json.loads(f.read())
        # 倒排索引：token → 行号列表（44k 条路径建一次，之后查是 O(1)）
        inv = {}
        for i, (p, _s, _m) in enumerate(_STATE["disk"]["rows"]):
            for t in set(_tok(p)):
                inv.setdefault(t, []).append(i)
        _STATE["inv"] = inv
    if MANIFEST.is_file():
        _STATE["man"] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    _STATE["loaded_at"] = time.time()
    return (time.time() - t0) * 1000


def _rss_mb():
    try:
        with open("/proc/self/statm", encoding="utf-8") as f:
            return int(f.read().split()[1]) * 4096 / 1048576.0
    except Exception:
        return 0.0


def op_stats():
    d = _STATE["disk"]
    if not d:
        return {"ok": False, "error": "磁盘索引未载入"}
    tot = sum(r[1] for r in d["rows"])
    return {"ok": True, "文件": d["files"], "目录": d["dirs"],
            "总GB": round(tot / 1073741824, 2), "建于": d["built_at"],
            "常驻RSS_MB": round(_rss_mb(), 1), "已载入": bool(_STATE["man"])}


def op_find(q, limit=15):
    d = _STATE["disk"]
    if not d:
        return {"ok": False, "error": "磁盘索引未载入（先 build + serve）"}
    t0 = time.time()
    rows = d["rows"]
    ql = q.lower()
    toks = _tok(ql)
    inv = _STATE["inv"]
    hits = []
    if toks and inv and all(t in inv for t in toks):
        # 倒排命中：全部 token 都拿得到 ⇒ 取最短表做交集（毫秒级）
        lists = sorted((inv[t] for t in toks), key=len)
        cand = set(lists[0])
        for lst in lists[1:]:
            cand &= set(lst)
            if not cand:
                break
        # 倒排只是「粗筛」，必须再过一道子串核对 ——
        # 否则 omni_plug 会被切成 omni+plug 命中更多路径，与本地直查给不出同一个数。
        hits = [(rows[i][0], rows[i][1]) for i in cand if ql in rows[i][0].lower()]
    else:
        # 退化：路径子串匹配（token 切不出来时兜底）
        hits = [(p, s) for p, s, _m in rows if ql in p.lower()]
    hits.sort(key=lambda x: -x[1])
    return {"ok": True, "命中": len(hits), "ms": round((time.time() - t0) * 1000, 2),
            "方式": "倒排" if (toks and inv and all(t in inv for t in toks)) else "子串",
            "前几": [{"path": a, "KB": round(b / 1024, 1)} for a, b in hits[:limit]]}


def op_page(text, limit=6):
    man = _STATE["man"]
    if not man:
        return {"ok": False, "error": "页索引未载入"}
    import re
    tk = set(w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_\-]{2,}", text))
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        for i in range(len(seg) - 1):
            tk.add(seg[i:i + 2])
    t0 = time.time()
    seeds = [p for p in man["pages"] if any(t in p.lower() for t in tk)]
    for name, pids in man["name2"].items():
        if any(t in name for t in tk):
            seeds += pids
    seeds = list(dict.fromkeys(seeds))[:10]
    out, seen, frontier = [], set(), list(seeds)
    for depth in range(2):
        nxt = []
        for pid in frontier:
            if pid in seen or pid not in man["shard_of"]:
                continue
            f = SHARDS / man["shard_of"][pid]
            if not f.is_file():
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            seen.add(pid)
            out.append({"page": pid, "hops": depth,
                        "degree": len(d.get("neighbors", []))})
            nxt += d.get("neighbors", [])
        frontier = nxt
        if not frontier:
            break
    return {"ok": True, "分片": len(seen), "总页": man["count"],
            "ms": round((time.time() - t0) * 1000, 2), "页": out[:limit]}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"      # 开 keep-alive：连一次，多次查（iSH 上建连才是大头）

    def log_message(self, *a):
        pass

    def _send(self, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        g = lambda k, d="": (q.get(k, [d])[0])
        if u.path == "/ping":
            return self._send({"ok": True, "pong": time.time(),
                               "载入于": _STATE["loaded_at"]})
        if u.path == "/stats":
            return self._send(op_stats())
        if u.path == "/find":
            return self._send(op_find(g("q"), int(g("limit", "15"))))
        if u.path == "/page":
            return self._send(op_page(g("text"), int(g("limit", "6"))))
        return self._send({"ok": False, "error": "unknown", "routes": ["/ping", "/stats", "/find?q=", "/page?text="]})


def cmd_serve(port):
    ms = load_all()
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print("  常驻索引已起: http://127.0.0.1:%d" % port)
    print("  载入耗时: %.0f ms · 常驻 RSS: %.1f MB" % (ms, _rss_mb()))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def _get(path):
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=3)
        s.sendall(("GET %s HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n" % path).encode())
        buf = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            buf += c
        s.close()
        body = buf.split(b"\r\n\r\n", 1)[1]
        return json.loads(body)
    except Exception as e:
        return {"ok": False, "error": "%s（常驻层没起？）" % type(e).__name__}


def cmd_client(what, arg=""):
    t0 = time.time()
    r = _get({"ping": "/ping", "stats": "/stats", "find": "/find?q=" + urllib.parse.quote(arg),
              "page": "/page?text=" + urllib.parse.quote(arg)}[what])
    total = (time.time() - t0) * 1000
    r["往返ms"] = round(total, 2)
    print("  " + json.dumps(r, ensure_ascii=False)[:400])


if __name__ == "__main__":
    a = sys.argv[1:] or ["ping"]
    if a[0] == "serve":
        p = PORT
        if "--port" in a:
            p = int(a[a.index("--port") + 1])
        cmd_serve(p)
    elif a[0] in ("ping", "stats"):
        cmd_client(a[0])
    elif a[0] in ("find", "page"):
        cmd_client(a[0], " ".join(a[1:]))
    else:
        cmd_client("find", " ".join(a))
