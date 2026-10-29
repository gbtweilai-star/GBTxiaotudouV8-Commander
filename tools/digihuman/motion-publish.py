# -*- coding: utf-8 -*-
"""motion-publish.py — 把成片发布到**云动作库**（部署在云插件上的 R2 公网桶），并生成 APP 能直接播的一页。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要这一件（主人令）
「所有的动作你都要保存在部署容器的那个云插件上面 使用云来投射到 APP 上面」

所以「动作」不是躺在本地 outputs/ 里，而是：
  ① 视频进公网桶 `gbt-motion`（APP 一句 fetch 就能拉，逐字节 sha 可校）；
  ② 同时生成 `manifest.json`（动作目录：谁、多长、多清、哪条已达标）；
  ③ 再生成一页 `index.html` **也放在桶里** —— 零部署就能在浏览器里看/选/播，
     这就是「云投射到 APP」的最小闭环。

## 三条纪律
- 上传后**必须用公网 URL 下载回来比 sha256**（上传回执不算证据）；
- manifest 只写真量过的字段，没量过的写 null，**不许编**；
- 桶名走 `GBT_R2_BUCKET`（默认 `gbt-motion`），绝不往放权重的桶里写。

用法：
  py -3.14 tools/digihuman/motion-publish.py add outputs/dh-talk/x.mp4 --framing full-body --voice 台湾腔
  py -3.14 tools/digihuman/motion-publish.py sync      # 只重建 manifest + index.html 并上传
  py -3.14 tools/digihuman/motion-publish.py list      # 只读：现读桶里的 manifest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUCKET = os.environ.get("GBT_R2_BUCKET", "gbt-motion")
PUBLIC = "https://pub-3b817fc945aa4e1c8d7cce0ea93fa725.r2.dev"
LEDGER = ROOT / "state" / "motion-library.jsonl"
MANIFEST = ROOT / "state" / "motion-manifest.json"
INDEX = ROOT / "state" / "motion-index.html"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                 # noqa: BLE001
        pass


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _probe(p: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,width,height,nb_frames:format=duration",
                        "-of", "json", str(p)], capture_output=True, text=True)
    try:
        j = json.loads(r.stdout or "{}")
    except Exception:                                                 # noqa: BLE001
        return {}
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    d = {"secs": round(float(j.get("format", {}).get("duration") or 0), 3),
         "size": [int(v.get("width") or 0), int(v.get("height") or 0)],
         "frames": int(v.get("nb_frames") or 0)}
    return d


def put(local: Path, key: str, ctype: str) -> dict:
    """上传 + **公网回读比 sha**（只认这个）。"""
    env = dict(os.environ, GBT_R2_BUCKET=BUCKET)
    up = subprocess.run(["wrangler", "r2", "object", "put", "%s/%s" % (BUCKET, key),
                         "--file", str(local), "--remote", "--content-type", ctype],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        env=env, shell=True)
    if "Upload complete" not in ((up.stdout or "") + (up.stderr or "")):
        return {"ok": False, "why": "upload", "tail": ((up.stdout or "") + (up.stderr or ""))[-300:]}
    url = "%s/%s" % (PUBLIC, key)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"user-agent": "gbt-pub/1.0"}),
                                    timeout=120) as s:
            data = s.read()
            ctype_got = s.headers.get("content-type")
    except Exception as e:                                            # noqa: BLE001
        return {"ok": False, "why": "public_read", "err": "%s: %s" % (type(e).__name__, str(e)[:160])}
    want = _sha(local)
    got = hashlib.sha256(data).hexdigest()
    return {"ok": want == got, "url": url, "bytes": len(data), "sha256": got,
            "sha_match": want == got, "content_type": ctype_got}


def _load_rows() -> list:
    if not LEDGER.is_file():
        return []
    rows = []
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:                                             # noqa: BLE001
            pass
    return rows


def _write_manifest(rows: list) -> dict:
    """按 id 合并：clip 行立条目，**fix 行在当前值上打补丁**（只追加，不回头改历史）。"""
    merged: dict = {}
    for r in rows:
        if r.get("event") == "clip":
            merged[r.get("id")] = {k: r.get(k) for k in
                                   ("id", "title", "url", "sha256", "bytes", "secs", "size",
                                    "frames", "framing", "voice", "qc", "added_at")}
        elif r.get("event") == "fix" and r.get("id") in merged:
            for k in ("title", "framing", "voice", "qc"):
                if r.get(k) not in (None, ""):
                    merged[r["id"]][k] = r[k]
            merged[r["id"]]["fixed_at"] = r.get("at")
            if r.get("why"):
                merged[r["id"]]["fix_why"] = r["why"]
    clips = [merged[k] for k in merged]
    if False:
        clips.append({k: r.get(k) for k in
                      ("id", "title", "url", "sha256", "bytes", "secs", "size", "frames",
                       "framing", "voice", "qc", "added_at")})
    m = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "library": "gbt-motion", "public": PUBLIC, "count": len(clips), "clips": clips}
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return m


def _write_index(m: dict) -> Path:
    clips = json.dumps(m.get("clips") or [], ensure_ascii=False)
    html = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<title>GBT 动作库 · 云投射</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:dark}
body{margin:0;background:#0d0f12;color:#e9edf2;font:15px/1.6 -apple-system,"Microsoft YaHei",sans-serif}
header{padding:18px 22px;border-bottom:1px solid #1d222b;display:flex;gap:14px;align-items:baseline;flex-wrap:wrap}
h1{font-size:17px;margin:0;font-weight:600;letter-spacing:.3px}
small{color:#8b96a5}
main{display:grid;grid-template-columns:300px 1fr;gap:18px;padding:18px 22px}
@media(max-width:820px){main{grid-template-columns:1fr}}
.list{display:flex;flex-direction:column;gap:8px}
.item{padding:10px 12px;border:1px solid #222a35;border-radius:10px;cursor:pointer;background:#12161c}
.item:hover{border-color:#3a4757}
.item.on{border-color:#e0b34a;background:#171c23}
.item b{display:block;font-weight:600;font-size:14px}
.item span{color:#8b96a5;font-size:12px}
.pane{background:#12161c;border:1px solid #222a35;border-radius:12px;padding:14px}
video{width:100%;max-height:72vh;border-radius:8px;background:#000}
.qc{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
.chip{border:1px solid #2a3341;border-radius:999px;padding:4px 10px;font-size:12px;color:#b9c4d2}
.ok{border-color:#2f6f4f;color:#7fd6a5}
.bad{border-color:#7a3a3a;color:#f0a0a0}
code{background:#0b0e12;padding:2px 6px;border-radius:6px;font-size:12px;color:#9fb3c8}
footer{padding:10px 22px 26px;color:#6e7987;font-size:12px}
</style></head><body>
<header><h1>GBT 动作库 · 云投射到 APP</h1>
<small id="meta">读 manifest…</small></header>
<main>
 <div class="list" id="list"></div>
 <div class="pane">
  <video id="v" controls playsinline></video>
  <div class="qc" id="qc"></div>
  <p id="url" style="margin:10px 0 0"></p>
 </div>
</main>
<footer>公网桶 <code>gbt-motion</code> · manifest 与片子同源 · 每条都带 sha256 可逐字节校 ·
开发者：自由的风 · 守护者：公主土豆</footer>
<script>
const CLIPS = __CLIPS__;
const list = document.getElementById('list'), v = document.getElementById('v'),
      qc = document.getElementById('qc'), meta = document.getElementById('meta'),
      urlp = document.getElementById('url');
meta.textContent = CLIPS.length + ' 条动作 · 数据来自 manifest.json（同桶同源）';
function chip(t, cls){ const d=document.createElement('span'); d.className='chip '+(cls||''); d.textContent=t; return d; }
function play(c, el){
  [...document.querySelectorAll('.item')].forEach(x=>x.classList.remove('on'));
  el.classList.add('on');
  v.src = c.url; v.load(); v.play().catch(()=>{});
  qc.innerHTML='';
  const q = c.qc || {};
  if (q['画质清晰']) qc.appendChild(chip('画质 ratio ' + q['画质清晰'].ratio, q['画质清晰'].ratio>=0.9?'ok':'bad'));
  if (q['动作自然']) qc.appendChild(chip('头动 ' + q['动作自然'].head_move_mean, q['动作自然'].head_move_mean>=0.15?'ok':'bad'));
  if (q['语音嘴对齐']) qc.appendChild(chip('嘴 r ' + q['语音嘴对齐'].r_peak + ' / lag ' + q['语音嘴对齐'].lag_frames + '帧',
      (q['语音嘴对齐'].r_peak>=0.55 && Math.abs(q['语音嘴对齐'].lag_frames)<=2)?'ok':'bad'));
  qc.appendChild(chip((c.framing||'?') + ' · ' + (c.voice||'?')));
  qc.appendChild(chip((c.size||[]).join('×') + ' · ' + (c.secs||'?') + 's'));
  qc.appendChild(chip('sha ' + String(c.sha256||'').slice(0,12)));
  urlp.innerHTML = '直链：<code>' + c.url + '</code>';
}
CLIPS.forEach((c,i)=>{
  const d=document.createElement('div'); d.className='item';
  d.innerHTML = '<b>'+c.title+'</b><span>'+(c.size||[]).join('×')+' · '+(c.secs||'?')+'s · '+(c.voice||'')+'</span>';
  d.onclick = ()=>play(c,d);
  list.appendChild(d);
  if(i===0) setTimeout(()=>play(c,d),10);
});
</script></body></html>"""
    INDEX.write_text(html.replace("__CLIPS__", clips), encoding="utf-8")
    return INDEX


def cmd_add(a) -> int:
    src = Path(a.file)
    if not src.is_file():
        print(json.dumps({"ok": False, "why": "没有这个文件：%s" % src}, ensure_ascii=False))
        return 2
    cid = a.id or src.stem
    key = "motions/clips/%s.mp4" % cid
    r = put(src, key, "video/mp4")
    print(json.dumps({"upload": r}, ensure_ascii=False, indent=1))
    if not r.get("ok"):
        return 1
    qc = None
    qp = Path(a.qc) if a.qc else None
    if qp and qp.is_file():
        try:
            qc = json.loads(qp.read_text(encoding="utf-8"))
        except Exception:                                             # noqa: BLE001
            qc = None
    pr = _probe(src)
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "clip", "id": cid,
           "title": a.title or cid, "url": r["url"], "sha256": r["sha256"], "bytes": r["bytes"],
           "secs": pr.get("secs"), "size": pr.get("size"), "frames": pr.get("frames"),
           "framing": a.framing, "voice": a.voice, "qc": qc, "added_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    m = _write_manifest(_load_rows())
    idx = _write_index(m)
    print(json.dumps({"manifest_count": m["count"], "index": str(idx)}, ensure_ascii=False))
    return cmd_sync(a)


def cmd_sync(a) -> int:
    m = _write_manifest(_load_rows())
    idx = _write_index(m)
    out = {"manifest": put(MANIFEST, "manifest.json", "application/json; charset=utf-8")}
    out["index"] = put(idx, "index.html", "text/html; charset=utf-8")
    out["player"] = "%s/index.html" % PUBLIC
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out["manifest"].get("ok") and out["index"].get("ok") else 1


def _get_json(url: str, tries: int = 4) -> dict:
    """r2.dev 公网端点会偶发 403（限速/边缘），**必须重试**再归因（2026-10-20 实测两次）。"""
    last = ""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"user-agent": "Mozilla/5.0 gbt-pub/1.0"})
            with urllib.request.urlopen(req, timeout=60) as s:
                return {"ok": True, "data": json.loads(s.read().decode("utf-8"))}
        except Exception as e:                                        # noqa: BLE001
            last = "%s: %s" % (type(e).__name__, str(e)[:120])
            time.sleep(1.5 * (i + 1))
    return {"ok": False, "why": last, "tries": tries}


def cmd_fix(a) -> int:
    """给已入库的条目**追加一条更正**（只追加不删；播放页与 manifest 会按最新一条显示）。"""
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "fix", "id": a.id,
           "title": a.title, "framing": a.framing, "voice": a.voice, "why": a.why}
    if a.qc:
        qp = Path(a.qc)
        if qp.is_file():
            row["qc"] = json.loads(qp.read_text(encoding="utf-8"))
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"ok": True, "fixed": a.id, "row": row}, ensure_ascii=False))
    return cmd_sync(a)


def cmd_list(_a) -> int:
    r = _get_json(PUBLIC + "/manifest.json")
    if not r.get("ok"):
        fallback = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else {}
        print(json.dumps({"ok": False, "why": r.get("why"), "tries": r.get("tries"),
                          "local_fallback_count": fallback.get("count")}, ensure_ascii=False))
        return 1
    m = r["data"]
    print(json.dumps({"ok": True, "count": m.get("count"),
                      "clips": [{"id": c.get("id"), "title": c.get("title"),
                                 "secs": c.get("secs"), "size": c.get("size")}
                                for c in (m.get("clips") or [])]}, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("add")
    a.add_argument("file")
    a.add_argument("--id", default="")
    a.add_argument("--title", default="")
    a.add_argument("--framing", default="", help="full-body / head-shoulder …")
    a.add_argument("--voice", default="", help="台湾腔 / 普通话 …")
    a.add_argument("--qc", default="", help="三条口径回执 json")
    f = sub.add_parser("fix")
    f.add_argument("--id", required=True)
    f.add_argument("--title", default="")
    f.add_argument("--framing", default="")
    f.add_argument("--voice", default="")
    f.add_argument("--why", default="")
    f.add_argument("--qc", default="")
    sub.add_parser("sync")
    sub.add_parser("list")
    ns = ap.parse_args()
    fn = {"add": cmd_add, "fix": cmd_fix, "sync": cmd_sync, "list": cmd_list}.get(ns.cmd or "list", cmd_list)
    return fn(ns)


if __name__ == "__main__":
    sys.exit(main())
