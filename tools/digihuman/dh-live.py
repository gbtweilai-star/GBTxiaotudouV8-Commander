# -*- coding: utf-8 -*-
"""dh-live.py — **实时数字人唯一入口**：一张图 + 一句台词 → 云上一页会说话的她（浏览器 WebGL 跑，不烧卡）。

## 为什么是这一件（Owner 2026-10-21：「我让你固化一遍流程」）
之前这条链散在四处、要手敲五条命令：`dh2d-build.py`（分层素材）→ edge-tts（台湾腔）→
拼 live 页 → `dh2d-live-check.py`（判据）→ `wrangler r2 put`（上云）。**这次焊成一次调用**：

    build    ① 素材：assets/dh2d 缺则现做（dh2d-build.py，幂等）
             ② 配音：edge-tts 台湾腔（zh-TW-HsiaoChenNeural）→ voice.mp3
             ③ 组页：outputs/dh-live/<id>/（自包含：index.html + dh2d.js + atlas.js + assets/dh2d/*）
             ④ 判据：5 条（静音闭嘴 / 大声张开 / 中声<大声 / 静音后闭合 / 非说话态不动嘴）
             ⑤ 记账：outputs/dh-live/<id>/receipt.json + state/dh-live.jsonl
    verify   真跑一次判据并**截图**（静音 / 大音量 / 中音量三张），绿了才继续
    publish  上云（R2 桶 gbt-motion，公网回下载比 sha256 才算成功）—— **要 data_export 票**

## 口径（写死，不许悄悄放宽）
- 判据不到 5/5 绿 ⇒ `publish` 拒绝（不带着坏件上云）。
- 上云**必须**公网 URL 回下载比 sha256（上传回执不算证据）。
- 出网动作只发生在 `publish`（要票）与 edge-tts（配音）；`build`/`verify` 全本地。

## 用法
    py -3.14 tools/digihuman/dh-live.py build --id live-tw-01 \\
        --text "你好呀，我是小土豆，今天想陪你聊聊天。"
    py -3.14 tools/digihuman/dh-live.py verify --id live-tw-01
    py -3.14 tools/digihuman/dh-live.py publish --id live-tw-01
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV_PY = ROOT / ".venv-sadtalker" / "Scripts" / "python.exe"   # 装 edge-tts 的那个解释器
PY312 = Path(r"C:\Python312\python.exe")                        # 装 playwright+greenlet 的那个
THEATER = ROOT / "holo_pet_w3" / "voice-theater"
OUT = ROOT / "outputs" / "dh-live"
JUDGE = ROOT / "tools" / "codex-scripts" / "dh2d-live-check.py"
BUCKET = os.environ.get("GBT_R2_BUCKET", "gbt-motion")
PUBLIC = "https://pub-3b817fc945aa4e1c8d7cce0ea93fa725.r2.dev"
VOICES = {"tw": "zh-TW-HsiaoChenNeural", "tw_yun": "zh-TW-YunJheNeural",
          "cn": "zh-CN-XiaoxiaoNeural"}
SYNC = ["index.html", "dh2d.js", "atlas.js",
        "assets/dh2d/albedo.png", "assets/dh2d/cavity.png", "assets/dh2d/meta.json"]


def sh(cmd, cwd=None, timeout=3600) -> dict:
    t0 = time.time()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return {"cmd": cmd if isinstance(cmd, str) else " ".join(map(str, cmd)),
            "rc": r.returncode, "secs": round(time.time() - t0, 1),
            "out": (r.stdout or "")[-1200:], "err": (r.stderr or "")[-1200:]}


def say(tag: str, **kv) -> None:
    print(json.dumps(dict(tag=tag, **kv), ensure_ascii=False), flush=True)


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ── ① 素材层 ─────────────────────────────────────────────────────────────
def ensure_layers(image: Path) -> dict:
    d = THEATER / "assets" / "dh2d"
    need = ["albedo.png", "cavity.png", "meta.json"]
    have = [n for n in need if (d / n).is_file()]
    if len(have) == len(need):
        return {"ok": True, "reused": True, "files": {n: (d / n).stat().st_size for n in need}}
    r = sh([sys.executable, str(ROOT / "tools" / "digihuman" / "dh2d-build.py")],
           cwd=str(ROOT), timeout=600)
    ok = all((d / n).is_file() for n in need)
    return {"ok": ok and r["rc"] == 0, "reused": False, "rc": r["rc"],
            "tail": (r["out"] + r["err"])[-600:],
            "files": {n: ((d / n).stat().st_size if (d / n).is_file() else 0) for n in need}}


# ── ② 配音（台湾腔）──────────────────────────────────────────────────────
def tts(text: str, voice: str, rate: str, dst_mp3: Path, dst_wav: Path) -> dict:
    dst_mp3.parent.mkdir(parents=True, exist_ok=True)
    r = sh([str(VENV_PY), "-m", "edge_tts", "--voice", voice, "--rate", rate,
            "--text", text, "--write-media", str(dst_mp3)], timeout=300)
    if r["rc"] != 0 or not dst_mp3.is_file():
        return {"ok": False, "why": "tts_failed", "rc": r["rc"],
                "err": (r["err"] or r["out"])[-400:]}
    w = sh(["ffmpeg", "-y", "-v", "error", "-i", str(dst_mp3),
            "-ar", "16000", "-ac", "1", str(dst_wav)], timeout=180)
    return {"ok": w["rc"] == 0 and dst_wav.is_file(), "mp3": dst_mp3.stat().st_size,
            "wav": (dst_wav.stat().st_size if dst_wav.is_file() else 0)}


# ── ③ 组页 ───────────────────────────────────────────────────────────────
PAGE = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title>
<style>
 html,body{margin:0;height:100%%;background:#0e0f12;overflow:hidden}
 #wrap{position:fixed;inset:0;display:grid;place-items:center}
 /* 空闲态必须**肉眼看得见**在动：重心左右移 + 轻微转体（11s）、呼吸起伏（4.2s）
    —— 引擎里 sway/breath 那些 uniform 实测只上传不落像素（见台账 §82），先用这层兜住 */
 #bob{width:100%%;height:100%%;will-change:transform}
 #bre{width:100%%;height:100%%;transform-origin:50%% 100%%;animation:gbt-breath 4.2s ease-in-out infinite}
 @keyframes gbt-sway{0%%,100%%{transform:translateX(-6px) rotate(-0.35deg)}50%%{transform:translateX(6px) rotate(0.35deg)}}
 @keyframes gbt-breath{0%%,100%%{transform:scale(1,1)}50%%{transform:scale(1.006,1.012)}}
 canvas#dh2d{width:100%%;height:100%%;display:block}
 #bar{position:fixed;left:0;right:0;bottom:0;display:flex;gap:10px;align-items:center;
      padding:10px 14px;font:14px/1.4 system-ui,sans-serif;color:#e8e8ea;
      background:linear-gradient(transparent,rgba(0,0,0,.65))}
 button{font:inherit;padding:8px 16px;border-radius:999px;border:0;
        background:#f2c14e;color:#20180a;font-weight:600;cursor:pointer}
 #st{opacity:.75;font-size:12px;white-space:pre-wrap}
</style></head><body>
<div id="wrap"><div id="bob"><div id="bre"><canvas id="dh2d" data-crop-h="0.66" aria-label="數字人"></canvas></div></div></div>
<div id="bar"><button id="go">▶ 讓她說話</button>
  <span id="st">載入中…</span></div>
<audio id="au" src="voice.mp3" preload="auto"></audio>
<script src="atlas.js"></script>
<script src="dh2d.js"></script>
<script>
(function () {
  var S = window.GBT_DH2D, au = document.getElementById('au'),
      st = document.getElementById('st'), go = document.getElementById('go');
  var ctx, ana, buf, raf, playing = false;
  function boot() {
    if (!S || !S.ready || !S.ready()) { st.textContent = '引擎載入中…'; return setTimeout(boot, 80); }
    var i = S.info();
    st.textContent = 'ok=' + i.ok + ' status=' + i.status + (i.why ? ' why=' + i.why : '');
    S.setState('idle');
  }
  boot();
  function drive() {
    if (!playing) return;
    ana.getByteTimeDomainData(buf);
    var s = 0;
    for (var k = 0; k < buf.length; k++) { var v = (buf[k] - 128) / 128; s += v * v; }
    var rms = Math.sqrt(s / buf.length);
    var lvl = Math.min(1, rms * 6.0);            // 与试机台同一条口径
    S.level(lvl); window.__lv = lvl;
    raf = requestAnimationFrame(drive);
  }
  go.addEventListener('click', function () {
    if (playing) { au.pause(); return; }
    if (!ctx) {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      var src = ctx.createMediaElementSource(au);
      ana = ctx.createAnalyser(); ana.fftSize = 1024; buf = new Uint8Array(ana.fftSize);
      src.connect(ana); ana.connect(ctx.destination);
    }
    ctx.resume();
    au.currentTime = 0; au.play();
  });
  // 常驻微动：空闲慢摆（11s/来回），说话时按瞬时音量放大摆幅并加快 —— 让"在说话"看得出来
  var bob = document.getElementById('bob'), t0 = performance.now(), lvS = 0;
  (function anim() {
    var t = (performance.now() - t0) / 1000;
    lvS += (window.__lv - lvS) * 0.15;
    var amp = 5.5 + 9.0 * lvS;                       // 空闲 ±5.5px → 说话 ±14.5px
    var hz = 0.09 + 0.10 * lvS;                      // 周期由 11s 缩到 5.3s
    var x = Math.sin(t * hz * 6.2832) * amp;
    var r = Math.sin(t * hz * 6.2832) * (0.30 + 0.45 * lvS);
    bob.style.transform = 'translateX(' + x.toFixed(2) + 'px) rotate(' + r.toFixed(3) + 'deg)';
    requestAnimationFrame(anim);
  })();
  au.addEventListener('play', function () { playing = true; S.setState('talk'); go.textContent = '❚❚ 暫停'; drive(); });
  au.addEventListener('ended', function () { playing = false; S.level(0); S.setState('idle'); go.textContent = '▶ 讓她說話'; });
  au.addEventListener('pause', function () { playing = false; S.level(0); S.setState('idle'); go.textContent = '▶ 讓她說話'; });
})();
</script></body></html>
"""


def _cp(src: Path, dst: Path) -> None:
    """源与目标同一路径时跳过（TTS 已经把文件写在最终位置，再 copy 会 WinError 32）。"""
    if Path(src).resolve() == Path(dst).resolve():
        return
    shutil.copy2(src, dst)


def assemble(bid: str, title: str, voice_mp3: Path, voice_wav: Path, text: str) -> dict:
    dst = OUT / bid
    (dst / "assets" / "dh2d").mkdir(parents=True, exist_ok=True)
    for n in ["dh2d.js"]:
        _cp(THEATER / n, dst / n)
    _cp(THEATER / "assets" / "dh2d" / "atlas.js", dst / "atlas.js")
    for n in ["albedo.png", "cavity.png", "meta.json"]:
        _cp(THEATER / "assets" / "dh2d" / n, dst / "assets" / "dh2d" / n)
    _cp(voice_mp3, dst / "voice.mp3")
    _cp(voice_wav, dst / "voice.wav")
    (dst / "script.txt").write_text(text + "\n", encoding="utf-8")
    (dst / "index.html").write_text(PAGE % {"title": title}, encoding="utf-8")
    files = {}
    for p in sorted(dst.rglob("*")):
        if p.is_file():
            files[str(p.relative_to(dst)).replace("\\", "/")] = p.stat().st_size
    return {"dir": str(dst), "files": files}


# ── ④ 判据 ───────────────────────────────────────────────────────────────
def judge(page: Path, shots: Path | None = None) -> dict:
    if not PY312.is_file():
        return {"ok": False, "why": "no_py312", "detail": "C:\\Python312\\python.exe 不存在"}
    env = dict(os.environ)
    env["DH2D_PAGE"] = str(page)
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
        env["DH2D_SHOTS"] = str(shots)
    r = subprocess.run([str(PY312), str(JUDGE)], capture_output=True, text=True,
                       timeout=900, env=env, encoding="utf-8", errors="replace")
    raw = (r.stdout or "").strip()
    try:
        j = json.loads(raw[raw.index("{"):])
    except Exception:                                              # noqa: BLE001
        return {"ok": False, "why": "judge_unreadable", "rc": r.returncode,
                "out": raw[-600:], "err": (r.stderr or "")[-600:]}
    v = j.get("verdict") or {}
    j["ok"] = bool(v) and all(v.values())
    j["judge_rc"] = r.returncode
    return j


# ── ⑤ 上云 ───────────────────────────────────────────────────────────────
CTYPE = {".html": "text/html; charset=utf-8", ".js": "application/javascript",
         ".png": "image/png", ".json": "application/json", ".mp3": "audio/mpeg",
         ".wav": "audio/wav", ".txt": "text/plain; charset=utf-8"}


def publish(bid: str) -> dict:
    dst = OUT / bid
    if not (dst / "index.html").is_file():
        return {"ok": False, "why": "no_build", "dir": str(dst)}
    if shutil.which("wrangler") is None:
        return {"ok": False, "why": "no_wrangler"}
    import urllib.request
    rows, bad = [], []
    for rel in SYNC + ["voice.mp3"]:
        p = dst / rel
        if not p.is_file():
            bad.append({"missing": rel})
            continue
        key = "live/%s/%s" % (bid, rel)
        env = dict(os.environ, GBT_R2_BUCKET=BUCKET)
        up = subprocess.run(["wrangler", "r2", "object", "put", "%s/%s" % (BUCKET, key),
                             "--file", str(p), "--remote",
                             "--content-type", CTYPE.get(p.suffix, "application/octet-stream")],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=env, shell=True, timeout=900)
        blob = (up.stdout or "") + (up.stderr or "")
        if "Upload complete" not in blob:          # 与 motion-publish 同一条判据
            bad.append({"file": rel, "why": "upload", "tail": blob[-300:]})
            continue
        url = "%s/%s" % (PUBLIC, key)
        got = -1
        data = b""
        err = ""
        for _ in range(4):                          # r2.dev 会偶发 403，必须重试再归因
            try:
                with urllib.request.urlopen(urllib.request.Request(
                        url, headers={"user-agent": "gbt-pub/1.0"}), timeout=120) as s:
                    data = s.read()
                got = len(data)
                break
            except Exception as e:                  # noqa: BLE001
                err = "%s: %s" % (type(e).__name__, str(e)[:140])
        want = sha(p)
        ok_sha = got == p.stat().st_size and hashlib.sha256(data).hexdigest() == want
        rows.append({"file": rel, "key": key, "bytes": p.stat().st_size,
                     "public_bytes": got, "url": url, "sha_match": ok_sha, "err": err})
    ok = not bad and bool(rows) and all(r["sha_match"] for r in rows)
    return {"ok": ok, "bucket": BUCKET, "page": "%s/live/%s/index.html" % (PUBLIC, bid),
            "files": rows, "bad": bad}

def receipt(bid: str, rec: dict) -> None:
    d = OUT / bid
    d.mkdir(parents=True, exist_ok=True)
    (d / "receipt.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    line = json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "id": bid,
                       "ok": rec.get("ok"), "page": rec.get("page"),
                       "judge": (rec.get("judge") or {}).get("verdict")}, ensure_ascii=False)
    with open(ROOT / "state" / "dh-live.jsonl", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["build", "verify", "publish", "status"])
    ap.add_argument("--id", default="live-tw-01")
    ap.add_argument("--title", default="小土豆 · 即時數位人")
    ap.add_argument("--text", default="")
    ap.add_argument("--text-file", default="")
    ap.add_argument("--voice", default="tw")
    ap.add_argument("--rate", default="+15%")
    ap.add_argument("--image", default=str(ROOT / "outputs" / "ref" / "character-ref.png"))
    a = ap.parse_args()

    if a.what == "status":
        d = OUT / a.id
        if not (d / "receipt.json").is_file():
            say("status", ok=False, why="no_receipt", dir=str(d))
            return 1
        say("status", ok=True, **json.loads((d / "receipt.json").read_text(encoding="utf-8")))
        return 0

    if a.what == "build":
        text = a.text or (Path(a.text_file).read_text(encoding="utf-8") if a.text_file else "")
        if not text.strip():
            say("fatal", why="need_text", hint="--text 或 --text-file")
            return 2
        dst = OUT / a.id
        lay = ensure_layers(Path(a.image))
        say("layers", **lay)
        if not lay["ok"]:
            receipt(a.id, {"ok": False, "step": "layers", "layers": lay})
            return 3
        voice_id = VOICES.get(a.voice, a.voice)
        v = tts(text, voice_id, a.rate, dst / "voice.mp3", dst / "voice.wav")
        say("tts", voice=voice_id, **v)
        if not v["ok"]:
            receipt(a.id, {"ok": False, "step": "tts", "tts": v})
            return 4
        page = assemble(a.id, a.title, dst / "voice.mp3", dst / "voice.wav", text)
        say("page", **page)
        j = judge(dst / "index.html", dst / "shots")
        say("judge", verdict=j.get("verdict"), jaw_track=j.get("jaw_track"),
            ok=j.get("ok"), why=j.get("why"))
        rec = {"ok": bool(j.get("ok")), "id": a.id, "page": str(dst / "index.html"),
               "voice": voice_id, "text": text[:200], "layers": lay, "tts": v,
               "judge": j, "files": page["files"]}
        receipt(a.id, rec)
        if not j.get("ok"):
            say("gate_failed", why="judge_not_green", verdict=j.get("verdict"))
            return 5
        say("build_ok", dir=str(dst), next="verify 或 publish")
        return 0

    if a.what == "verify":
        dst = OUT / a.id
        j = judge(dst / "index.html", dst / "shots")
        say("judge", verdict=j.get("verdict"), jaw_track=j.get("jaw_track"), ok=j.get("ok"))
        rec = {"ok": bool(j.get("ok")), "id": a.id, "judge": j,
               "shots": sorted(p.name for p in (dst / "shots").glob("*.png"))}
        receipt(a.id, rec)
        return 0 if j.get("ok") else 5

    if a.what == "publish":
        old = {}
        rp = OUT / a.id / "receipt.json"
        if rp.is_file():
            old = json.loads(rp.read_text(encoding="utf-8"))
        if old.get("judge", {}).get("verdict") and not old.get("ok"):
            say("gate_failed", why="last_judge_not_green")
            return 5
        p = publish(a.id)
        say("publish", ok=p["ok"], page=p.get("page"),
            files=[{"f": x["file"], "bytes": x["bytes"], "pub": x["public_bytes"],
                    "sha_match": x["sha_match"]} for x in p.get("files", [])],
            bad=p.get("bad"))
        rec = dict(old, ok=p["ok"], published=p["ok"], page=p.get("page"),
                   publish=p.get("files"), bad=p.get("bad"))
        receipt(a.id, rec)
        return 0 if p["ok"] else 6

    return 0


if __name__ == "__main__":
    sys.exit(main())
