# gbt-capability: drama_forge
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""drama_forge — 短剧产线（原生位 · 2026-11-01）：剧本 → 分镜 → 旁白/字幕 → 竖屏成片。

## 它解决什么
"手搓短剧"最耗人的不是灵感，是**分镜→配音→字幕→对时→装配**的手工搬运。
本件把这些段收成一条可重复的产线：
  1) 剧本（带 `0s – 4s` 时间码）→ 用 `drama.parse_timed` 切分镜（复用既有链头，不另造一套）；
  2) 每镜旁白 → Windows SAPI 本地 TTS（离线；失败如实记，不假配音）；
  3) 画面：给了 `assets_dir` 就用你的自有图；没给就渲染**分镜卡（animatic）**——明确标 `storyboard_cards`，不是假装成片；
  4) 字幕：与旁白同源生成 SRT，烧进画面 + 软字幕轨；
  5) 装配：ffmpeg 竖屏 1080×1920 / 30fps / H.264 + AAC；
  6) 验收：ffprobe 逐条判（MP4/竖屏/时长/音轨/字幕轨），不达标如实红。

## 诚实边界
- **不生成** AI 画面/视频；没有素材时产出的是**分镜卡 animatic**，不是"AI 短剧成片"。
- 不下载、不复制、不发布；只用本地文件与本地 SAPI。
- 时长按旁白自然长度重排；与剧本声明时长不同会写进 `reading.timeline_note`。
- 供片：`assets_dir` 里放 `01.jpg/02.png...` 按镜序匹配；没有就自动用分镜卡。

## 契约
op：status / storyboard / make / verify / where
payload（make）：script（必填，时间码分镜稿）· assets_dir · name · voice（SAPI 默认）· min_dur/max_dur（默认 5/180，短剧正片请设 60/180）
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
try:
    from .. import drama as _drama
except Exception:  # noqa: BLE001
    try:
        import sys
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import drama as _drama
    except Exception:  # noqa: BLE001
        _drama = None

STATUS = {
    "cap": "drama_forge", "tier": "native",
    "ops": ["status", "storyboard", "series", "gen", "make", "verify", "where"],
    "input": ["script(带 0s–4s 时间码)", "assets_dir(可选自有图)", "gen + GBT_T2I_CMD(可选文生图命令)", "name/voice"],
    "outputs": ["storyboard.json", "cards/*.png", "audio/*.wav", "episode.srt", "episode.mp4", "report.json/md"],
    "not_implemented": ["AI 生成画面/视频", "AI 换脸/换声", "自动发布"],
    "guardrails": ["只用自有/授权素材", "不复制原片", "不自动发布", "TTS 本地优先（SAPI；Edge 需显式 -CloudTts）"],
}


def _bin(name: str) -> str:
    import os
    env = os.environ.get("GBT_" + name.upper())
    if env:
        return env
    for d in (ROOT / "vendor" / "ffmpeg" / "bin", ROOT.parent / "vendor" / "ffmpeg" / "bin"):
        p = d / (name + (".exe" if os.name == "nt" else ""))
        if p.is_file():
            return str(p)
    return shutil.which(name) or ""


def _run(cmd, timeout=900, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, cwd=str(cwd) if cwd else None)
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def _probe(path) -> dict:
    ffprobe = _bin("ffprobe")
    if not ffprobe:
        return {"ok": False, "status": "needs_dependency", "detail": "ffprobe 缺失"}
    code, out, err = _run([ffprobe, "-v", "error", "-print_format", "json",
                           "-show_format", "-show_streams", str(path)], timeout=60)
    if code != 0:
        return {"ok": False, "status": "failed", "detail": (err or out)[-200:]}
    d = json.loads(out or "{}")
    fmt = d.get("format") or {}
    streams = d.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    s = next((x for x in streams if x.get("codec_type") == "subtitle"), {})
    return {"ok": True, "duration_s": round(float(fmt.get("duration") or 0), 2),
            "format": fmt.get("format_name"), "width": v.get("width"), "height": v.get("height"),
            "fps": v.get("avg_frame_rate"), "vcodec": v.get("codec_name"),
            "acodec": a.get("codec_name"), "has_audio": bool(a), "has_subtitle": bool(s)}


def _sapi_tts(text: str, wav: Path) -> dict:
    import hashlib
    # SAPI 对非 ASCII 路径会 InvalidOperationException ⇒ 先写到 ASCII 临时目录再拷回
    tmpdir = ROOT / "outputs" / "drama-forge" / "_tts"
    try:
        tmpdir.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    h = hashlib.md5((text or "").encode("utf-8")).hexdigest()[:16]
    tmpwav = tmpdir / ("t-%s.wav" % h)
    txt = tmpdir / ("t-%s.txt" % h)
    try:
        txt.write_text(text, encoding="utf-8-sig")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    ps = ("Add-Type -AssemblyName System.Speech;"
          "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
          "$vs=$s.GetInstalledVoices()|ForEach-Object{$_.VoiceInfo};"
          "$pick=$vs|Where-Object{$_.Culture.Name -eq 'zh-TW' -and $_.Gender -eq 'Female'}|Select-Object -First 1;"
          "if(-not $pick){$pick=$vs|Where-Object{$_.Culture.Name -like 'zh-*'}|Select-Object -First 1};"
          "if($pick){$s.SelectVoice($pick.Name)};"
          "$s.SetOutputToWaveFile('%s');$s.Speak([IO.File]::ReadAllText('%s'));"
          "$name=$s.Voice.Name;$s.Dispose();Write-Output $name"
          % (str(tmpwav), str(txt)))
    try:
        code, out, err = _run(["powershell", "-NoProfile", "-Command", ps], timeout=120)
        if code == 0 and tmpwav.is_file() and tmpwav.stat().st_size > 1000:
            import shutil as _sh
            _sh.copy2(tmpwav, wav)
            dur = _probe(wav)
            actual = (out or "").strip().splitlines()[-1] if (out or "").strip() else ""
            return {"ok": True, "wav": str(wav), "dur": dur.get("duration_s") or 0,
                    "voice": actual or "System.Speech 默认", "provider": "sapi"}
        return {"ok": False, "error": (err or out)[-200:] or "SAPI 输出为空"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}


VOICE_DEFAULT = "local"
VOICE_RATE = ""
VOICE_PITCH = ""


def _voice_default() -> str:
    import os
    if os.environ.get("GBT_VOICE"):
        return os.environ["GBT_VOICE"]
    try:
        cfg = json.loads((ROOT / "state" / "voice.json").read_text(encoding="utf-8-sig"))
        if cfg.get("default"):
            return str(cfg["default"])
    except Exception:  # noqa: BLE001
        pass
    return VOICE_DEFAULT


def _edge_tts(text: str, out: Path, voice: str, rate: str = "", pitch: str = "") -> dict:
    """调 tools/codex-scripts/edge-tts.py（zh-TW 台湾腔女声；需联网）。"""
    import sys
    helper = ROOT / "tools" / "codex-scripts" / "edge-tts.py"
    if not helper.is_file():
        return {"ok": False, "error": "edge-tts helper 缺失：%s" % helper}
    try:
        r = subprocess.run([sys.executable, "-B", "-X", "utf8", str(helper),
                            "--text", text, "--out", str(out), "--voice", voice],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        d = json.loads((r.stdout or "{}").strip().splitlines()[-1]) if (r.stdout or "").strip() else {}
        if r.returncode == 0 and d.get("ok") and out.is_file():
            dur = _probe(out)
            return {"ok": True, "wav": str(out), "dur": dur.get("duration_s") or 0,
                    "voice": voice, "provider": "edge", "bytes": d.get("bytes")}
        return {"ok": False, "error": d.get("error") or (r.stderr or "")[-200:] or "edge-tts 失败", "voice": voice}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160]), "voice": voice}


def _tts(text: str, wav: Path, payload=None) -> dict:
    import os
    payload = payload or {}
    voice = str(payload.get("voice") or _voice_default())
    allow_cloud = bool(payload.get("allow_cloud_tts")) or os.environ.get("GBT_ALLOW_CLOUD_TTS") == "1"
    if voice.lower() in ("local", "sapi", "auto"):
        s = _sapi_tts(text, wav)
        s["provider"] = "sapi"
        s.setdefault("voice", "local")
        return s
    if voice.startswith("zh-TW-"):
        if not allow_cloud:
            return {"ok": False, "status": "needs_local_voice",
                    "error": "本地没有 zh-TW 声线，且本地优先不允许联网 Edge；装 zh-TW 语言包或显式 allow_cloud_tts=true",
                    "voice": voice}
        rate, pitch = _voice_tone()
        return _edge_tts(text, wav.with_suffix(".mp3"), voice,
                         rate=str(payload.get("rate") or rate), pitch=str(payload.get("pitch") or pitch))
    s = _sapi_tts(text, wav)
    s["provider"] = "sapi"
    s.setdefault("voice", voice)
    return s

def _wrap(text: str, width_chars: int = 18) -> list:
    text = " ".join(str(text or "").split())
    return [text[i:i + width_chars] for i in range(0, len(text), width_chars)][:8]


def _card(idx: int, shot: dict, out_png: Path, size=(1080, 1920)) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:  # noqa: BLE001
        return False
    W, H = size
    img = Image.new("RGB", (W, H), (8, 10, 18))
    px = img.load()
    for y in range(H):
        c = int(8 + 28 * (y / H))
        for x in range(W):
            px[x, y] = (c, c + 2, c + 10)
    d = ImageDraw.Draw(img)
    try:
        f1 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 64)
        f2 = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 44)
        f3 = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 30)
    except Exception:  # noqa: BLE001
        f1 = f2 = f3 = ImageFont.load_default()
    d.rectangle([0, 120, W, 132], fill=(0, 180, 255))
    d.text((80, 170), "第 %02d 镜" % idx, font=f1, fill=(240, 245, 255))
    meta = " · ".join(x for x in (shot.get("shot_size"), shot.get("camera"), shot.get("emotion")) if x)
    d.text((80, 260), meta or "分镜卡（animatic）", font=f3, fill=(120, 210, 255))
    y = 420
    for line in _wrap(shot.get("desc") or shot.get("title") or ""):
        d.text((80, y), line, font=f2, fill=(225, 232, 245))
        y += 66
    if shot.get("dialogue"):
        d.text((80, H - 420), "旁白", font=f3, fill=(255, 190, 90))
        y = H - 370
        for line in _wrap(shot["dialogue"]):
            d.text((80, y), line, font=f2, fill=(255, 225, 160))
            y += 56
    d.text((80, H - 110), "GBT天真 · drama_forge · 分镜卡（非成片素材）", font=f3, fill=(110, 120, 140))
    try:
        img.save(out_png, "PNG")
        return out_png.is_file() and out_png.stat().st_size > 1000
    except Exception:  # noqa: BLE001
        return False


def _srt_ts(t: float) -> str:
    ms = int(round(max(0.0, float(t)) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def _srt(rows) -> str:
    out = []
    for i, (a, b, text) in enumerate(rows, 1):
        out += [str(i), "%s --> %s" % (_srt_ts(a), _srt_ts(b)), text, ""]
    return "\n".join(out)


def _assets(assets_dir):
    if not assets_dir:
        return []
    d = Path(assets_dir)
    if not d.is_dir():
        return []
    exts = (".png", ".jpg", ".jpeg", ".webp")
    return sorted([p for p in d.iterdir() if p.is_file() and p.suffix.lower() in exts])


def _slug(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", (s or "drama"))[:40]


def _storyboard(payload):
    script = payload.get("script") or payload.get("text") or ""
    if _drama is None:
        return {"ok": False, "status": "needs_dependency", "detail": "drama 链头不可用"}
    res = _drama.parse_timed(script)
    if not res.get("ok"):
        return {"ok": False, **res}
    return {"ok": True, "source": "drama.parse_timed", "total_dur": res["total_dur"],
            "shots": res["shots"], "verdict": res.get("verdict")}


def _gen_assets(shots, payload, out_dir: Path) -> dict:
    """用外部文生图命令生成每镜图（GBT_T2I_CMD；{prompt}/{out}/{idx} 占位）。

    本机无 CUDA/无 Qwen 权重，也不装重壳；所以这里只做**适配器**：
    配了命令就真跑命令、产出图；没配就 needs_model（不假装出图）。
    """
    import os
    cmd = os.environ.get("GBT_T2I_CMD") or payload.get("t2i_cmd")
    if not cmd:
        return {"ok": False, "status": "needs_model",
                "detail": "未配置 GBT_T2I_CMD（本机 AMD 无 CUDA、无 Qwen 权重）；不假装出图",
                "how_to_fix": "设 GBT_T2I_CMD='你的生成器 {prompt} -> {out}'（{idx} 可用）"}
    gen_dir = out_dir / "assets-gen"
    try:
        gen_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "not_writable", "detail": "%s: %s" % (type(e).__name__, str(e)[:120])}
    prefix = str(payload.get("prompt_prefix") or "竖屏短剧分镜，电影感，真实光影，")
    style = str(payload.get("style") or "cinematic, 9:16")
    made = []
    for sh in shots:
        idx = sh.get("idx")
        prompt = "%s%s，%s" % (prefix, sh.get("desc") or sh.get("title") or "", style)
        out = gen_dir / ("shot-%02d.png" % idx)
        try:
            c = cmd.replace("{prompt}", prompt).replace("{out}", str(out)).replace("{idx}", str(idx))
            rc, so, se = _run(c, timeout=int(payload.get("gen_timeout") or 240), cwd=out_dir)
            if rc == 0 and out.is_file() and out.stat().st_size > 1000:
                made.append(str(out))
            else:
                made.append(None)
        except Exception:  # noqa: BLE001
            made.append(None)
    ok = sum(1 for x in made if x)
    return {"ok": ok > 0, "status": "generated" if ok else "failed",
            "made": made, "count": ok, "dir": str(gen_dir),
            "honesty": "外部生成器产出；本件不内置模型"}


_BEATS = [
    ("钩子", "大特写", "推近", "紧张", "把观众按在座位上：一句话抛出不公平/不可能"),
    ("铺垫", "中景", "跟拍", "压抑", "交代关系与代价：谁要什么、谁挡着"),
    ("冲突", "近景", "手持", "愤怒", "正面撞上：第一次反击失败或代价出现"),
    ("反转", "特写", "环绕", "震惊", "信息翻面：真正的对手/真相露出"),
    ("悬念", "空镜", "拉远", "好奇", "留钩子：下一集才给答案"),
]


def _series(payload):
    """多集策划：premise → N 集 × 5 拍分镜稿 + series bible（不生成画面）。"""
    premise = " ".join(str(payload.get("premise") or payload.get("story") or "").split())
    if len(premise) < 8:
        return {"ok": False, "status": "needs_input", "error": "需要 premise（一句话故事，≥8 字）"}
    n = max(1, min(int(payload.get("episodes") or 3), 12))
    ep_sec = max(15.0, float(payload.get("episode_sec") or 90))
    genre = str(payload.get("genre") or "都市悬疑")
    chars = payload.get("characters") or ["她", "他"]
    if isinstance(chars, str):
        chars = [chars]
    chars = [str(c) for c in chars][:6] or ["她", "他"]
    name = payload.get("name") or "series-%s" % time.strftime("%m%d-%H%M")
    out = (ROOT / "outputs" / "drama-forge" / _slug(name)).resolve()
    try:
        out.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "not_writable", "detail": "%s: %s" % (type(e).__name__, str(e)[:120])}
    episodes = []
    for e in range(1, n + 1):
        d = ep_sec
        spans = [(0.0, 3.0), (3.0, round(d * 0.35, 2)), (round(d * 0.35, 2), round(d * 0.65, 2)),
                 (round(d * 0.65, 2), round(d * 0.88, 2)), (round(d * 0.88, 2), round(d, 2))]
        lines = []
        voices = {
            "钩子": "他们说，这场婚礼不该有新娘。",
            "铺垫": "她站在红毯尽头，发现所有人都在看她的脸。",
            "冲突": "她冲上去，却被一只手死死按住。",
            "反转": "直到她看见，镜子里的人不是她。",
            "悬念": "而真正的她，正站在门外。",
        }
        for i, ((role, size, cam, emo, intent), (a, b)) in enumerate(zip(_BEATS, spans), 1):
            who = chars[(i + e) % len(chars)]
            desc = "%s；%s；%s" % (premise, intent, "本集角色：" + "、".join(chars))
            lines.append("%ss – %ss（%s）%s %s %s %s %s；旁白：%s" % (
                a, b, role, size, cam, emo, who, desc, voices.get(role, premise)))
        script = "\n".join(lines) + "\n"
        sf = out / ("E%02d.txt" % e)
        sf.write_text(script, encoding="utf-8")
        episodes.append({"episode": e, "script": str(sf),
                         "logline": "%s：%s（第 %d 集）" % (genre, premise, e),
                         "beats": [x[0] for x in _BEATS]})
    bible = {"name": name, "premise": premise, "genre": genre, "characters": chars,
             "episodes": n, "episode_sec": ep_sec, "episodes_detail": episodes,
             "honesty": "只做策划/分镜稿；不生成画面、不下载、不发布"}
    (out / "series.json").write_text(json.dumps(bible, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "op": "series", "dir": str(out), "series_json": str(out / "series.json"),
            "episodes": episodes, "bible": bible,
            "next": "对每集跑 tools\\drama-build.ps1 -ScriptFile <E01.txt> -Name <名>-E01 [-AssetsDir ...] [-Gen]"}


def _make(payload):
    sb = _storyboard(payload)
    if not sb.get("ok"):
        return sb
    shots = sb["shots"]
    name = payload.get("name") or "drama-%s" % time.strftime("%m%d-%H%M")
    out_dir = (ROOT / "outputs" / "drama-forge" / _slug(name)).resolve()
    try:
        (out_dir / "cards").mkdir(parents=True, exist_ok=True)
        (out_dir / "audio").mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "not_writable", "detail": "%s: %s" % (type(e).__name__, str(e)[:120])}
    assets = _assets(payload.get("assets_dir"))
    gen = None
    if not assets and payload.get("gen"):
        gen = _gen_assets(shots, payload, out_dir)
        if gen.get("ok"):
            assets = [Path(x) for x in gen.get("made") or [] if x]
    visual_mode = "generated_assets" if assets and gen and gen.get("ok") else ("assets" if assets else "storyboard_cards")
    audio_src = Path(payload["audio_dir"]).expanduser().resolve() if payload.get("audio_dir") else None
    timeline, rows, tts_fail = [], [], []
    cur = 0.0
    for i, sh in enumerate(shots, 1):
        text = (sh.get("dialogue") or sh.get("desc") or "").strip()
        wav = out_dir / "audio" / ("shot-%02d.wav" % i)
        pre = None
        if audio_src:
            for cand in (audio_src / ("shot-%02d.wav" % i), audio_src / ("shot-%02d.mp3" % i),
                         audio_src / ("%02d.wav" % i), audio_src / ("%02d.mp3" % i),
                         audio_src / ("%d.wav" % i), audio_src / ("%d.mp3" % i)):
                if cand.is_file():
                    pre = cand
                    break
        if pre:
            tts = {"ok": True, "wav": str(pre), "dur": (_probe(pre).get("duration_s") or 0),
                   "voice": "provided", "provider": "audio_dir"}
        elif payload.get("tts", "edge") != "off" and text:
            tts = _tts(text, wav, payload)
        else:
            tts = {"ok": False, "error": "未提供音频且 TTS 关闭"}
        if not tts.get("ok"):
            tts_fail.append({"shot": i, "error": tts.get("error")})
        dur = max(float(sh.get("dur") or 3), (tts.get("dur") or 0) + 0.35)
        dur = max(1.0, round(dur, 2))
        # 画面
        img = out_dir / "cards" / ("shot-%02d.png" % i)
        ok_card = False
        if assets:
            try:
                from PIL import Image, ImageOps
                src = assets[(i - 1) % len(assets)]
                im = ImageOps.fit(Image.open(src).convert("RGB"), (1080, 1920))
                im.save(img, "PNG")
                ok_card = True
            except Exception:  # noqa: BLE001
                ok_card = False
        if not ok_card:
            ok_card = _card(i, sh, img)
        timeline.append({"shot": i, "start": round(cur, 3), "end": round(cur + dur, 3),
                         "dur": dur, "text": text, "image": str(img),
                         "audio": tts.get("wav") if tts.get("ok") else None,
                         "voice": tts.get("voice"), "provider": tts.get("provider"),
                         "card_ok": ok_card})
        rows.append((cur, cur + dur, text or sh.get("desc") or ""))
        cur += dur
    total = round(cur, 3)
    srt = out_dir / "episode.srt"
    srt.write_text(_srt(rows), encoding="utf-8")
    # 音轨：拼所有 wav；缺的补静音
    ffmpeg = _bin("ffmpeg")
    if not ffmpeg:
        return {"ok": False, "status": "needs_dependency", "detail": "ffmpeg 缺失（装 vendor/ffmpeg 或设 GBT_FFMPEG）", "out_dir": str(out_dir)}
    audio = out_dir / "narration.wav"
    if any(x["audio"] for x in timeline):
        try:
            inputs, filt = [], []
            for j, x in enumerate(timeline):
                if x["audio"]:
                    # 旁白只有几秒，镜头却有十几秒：补静音到镜长，不让 -shortest 把片尾剪掉
                    pad = out_dir / "audio" / ("pad-%02d.wav" % (j + 1))
                    _run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", x["audio"],
                          "-af", "apad", "-t", str(x["dur"]), "-ar", "44100", "-ac", "1", str(pad)], timeout=120)
                    inputs += ["-i", str(pad) if pad.is_file() else x["audio"]]
                else:
                    inputs += ["-f", "lavfi", "-t", str(x["dur"]), "-i", "anullsrc=r=44100:cl=mono"]
                filt.append("[%d:a]" % j)
            cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"] + inputs + [
                "-filter_complex", "".join(filt) + "concat=n=%d:v=0:a=1[a]" % len(timeline),
                "-map", "[a]", "-ar", "44100", "-ac", "1", str(audio)]
            code, out, err = _run(cmd, timeout=300)
            if code != 0:
                audio = None
        except Exception:  # noqa: BLE001
            audio = None
    else:
        audio = None
    # 静音兜底
    if not audio or not audio.is_file():
        audio = out_dir / "silence.wav"
        _run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
              "-i", "anullsrc=r=44100:cl=mono", "-t", str(total), "-c:a", "pcm_s16le", str(audio)], timeout=120)
    # 画面：默认给每镜加 Ken Burns 运镜（静图也能动）；motion=false 退回静态
    motion = bool(payload.get("motion", True)) and bool(timeline)
    concat = out_dir / "concat.txt"
    if motion:
        clips = out_dir / "clips"
        clips.mkdir(parents=True, exist_ok=True)
        names = []
        for idx, x in enumerate(timeline, 1):
            clip = clips / ("shot-%02d.mp4" % idx)
            z = "min(zoom+0.0008,1.12)" if idx % 2 else "max(1.0,1.12-on*0.0008)"
            vf = ("scale=1296:2304:force_original_aspect_ratio=increase,crop=1080:1920,"
                  "zoompan=z='%s':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,"
                  "format=yuv420p" % z)
            c, so, se = _run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                              "-loop", "1", "-i", str(x["image"]), "-t", str(x["dur"]),
                              "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
                              "-crf", "23", "-an", str(clip)], timeout=300)
            if c == 0 and clip.is_file():
                names.append(clip)
        if names:
            concat.write_text("\n".join("file 'clips/%s'" % p.name for p in names) + "\n", encoding="utf-8")
            vid_in = ["-f", "concat", "-safe", "0", "-i", "concat.txt"]
            final_vf = "format=yuv420p,subtitles=episode.srt:force_style='FontName=Microsoft YaHei,Fontsize=18'"
        else:
            motion = False
    if not motion:
        lines = []
        for x in timeline:
            p = "cards/" + Path(x["image"]).name
            lines += ["file '%s'" % p, "duration %.3f" % x["dur"]]
        lines += ["file 'cards/%s'" % Path(timeline[-1]["image"]).name]
        concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
        vid_in = ["-f", "concat", "-safe", "0", "-i", "concat.txt"]
        final_vf = ("scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
                    "format=yuv420p,fps=30,subtitles=episode.srt:force_style='FontName=Microsoft YaHei,Fontsize=18'")
    mp4 = out_dir / "episode.mp4"
    code, out, err = _run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error"] + vid_in + [
                           "-i", "narration.wav" if audio.name == "narration.wav" else "silence.wav",
                           "-i", "episode.srt", "-map", "0:v", "-map", "1:a", "-map", "2:s",
                           "-vf", final_vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                           "-c:a", "aac", "-b:a", "128k", "-c:s", "mov_text",
                           "-metadata:s:s:0", "language=zh", "-shortest", str(mp4)], timeout=900, cwd=out_dir)
    v = _probe(mp4) if mp4.is_file() else {"ok": False, "status": "missing"}
    min_dur = float(payload.get("min_dur") or 5)
    max_dur = float(payload.get("max_dur") or 180)
    checks = {"mp4": mp4.is_file(), "vertical": v.get("width") == 1080 and v.get("height") == 1920,
              "duration": bool(v.get("duration_s")) and min_dur <= v["duration_s"] <= max_dur,
              "audio": bool(v.get("has_audio")), "subtitle": bool(v.get("has_subtitle"))}
    report = {"ok": all(checks.values()), "name": name, "out_dir": str(out_dir),
              "visual_mode": visual_mode, "motion": motion, "timeline": timeline, "srt": str(srt),
              "mp4": str(mp4), "probe": v, "checks": checks, "tts_failures": tts_fail,
              "storyboard": sb, "gen": gen, "guardrails": STATUS["guardrails"],
              "honesty": ("assets=自有图" if assets else "无素材：分镜卡 animatic，不是 AI 成片") +
                         "；不下载/不复制/不发布"}
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# %s · 短剧装配报告" % name, "",
          "- 模式：**%s** · 时长 %.1fs · 1080×1920 · 音轨 %s · 字幕 %s" % (
              visual_mode, v.get("duration_s") or 0, checks["audio"], checks["subtitle"]),
          "- 成片：%s" % mp4, "- 字幕：%s" % srt, ""]
    for x in timeline:
        md.append("- 第%02d镜 %.1f–%.1fs：%s" % (x["shot"], x["start"], x["end"], x["text"] or "（无旁白）"))
    if tts_fail:
        md.append("")
        md.append("> ⚠️ 配音失败 %d 镜（已静音占位）：%s" % (len(tts_fail), tts_fail[:3]))
    (out_dir / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    report["report_md"] = str(out_dir / "report.md")
    return report


def run(op="status", **kw):
    op = str(op or "status").strip().lower()
    if op == "status":
        return {"ok": True, "op": "status", **STATUS}
    if op == "where":
        return {"ok": True, "op": "where", "cap": "drama_forge", **STATUS,
                "module": "gbt_allinone/tentacle/drama_forge.py",
                "entry": "py -3.14 tools/codex-scripts/five-dim.py cap drama_forge '{\"op\":\"storyboard\",...}'",
                "example": "run_task('drama_forge', {'op':'make','name':'醒来E1','script':'0s – 4s（标题）…','min_dur':5})"}
    if op == "storyboard":
        return _storyboard(kw)
    if op == "series":
        return _series(kw)
    if op == "gen":
        sb = _storyboard(kw)
        if not sb.get("ok"):
            return sb
        if not (os.environ.get("GBT_T2I_CMD") or kw.get("t2i_cmd")):
            return {"ok": False, "status": "needs_model",
                    "detail": "未配置 GBT_T2I_CMD（本机 AMD 无 CUDA、无 Qwen 权重）；不假装出图"}
        out = (ROOT / "outputs" / "drama-forge" / ("gen-" + time.strftime("%m%d-%H%M%S"))).resolve()
        try:
            out.mkdir(parents=True, exist_ok=True)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "status": "not_writable", "detail": str(e)[:120]}
        return _gen_assets(sb["shots"], kw, out)
    if op == "make":
        return _make(kw)
    if op == "verify":
        p = kw.get("video") or kw.get("mp4") or kw.get("path")
        v = _probe(p)
        return {"ok": v.get("ok", False), "op": "verify", "probe": v,
                "checks": {"vertical": v.get("width") == 1080 and v.get("height") == 1920,
                           "audio": bool(v.get("has_audio")), "subtitle": bool(v.get("has_subtitle"))}}
    return {"ok": False, "op": op, "status": "unknown_op", "error": "未知 op：%s" % op,
            "available": STATUS["ops"], "fail_closed": True}
