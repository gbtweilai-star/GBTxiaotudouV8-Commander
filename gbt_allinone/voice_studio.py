# gbt-capability: voice_studio
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""VoiceStudio 原生桥（**只提炼接口，不下载任何模型**）—— 主人令 2026-10-17。

## 上游真身（现读，不是印象）
`debpalash/VoiceStudio`（AGPL-3.0 · 69.9k★ · 全本地 ElevenLabs 替代）：
语音克隆 / 声音设计 / 视频配音 / 听写 / 转写 / 有声书，**646 语言**；默认引擎 k2-fsa/OmniVoice。
它自带 **Local speech platform**（`docs/speech-platform.md` 现读）：
- `GET  :3900/.well-known/voicestudio-speech` —— 能力发现（协议 `voicestudio.speech.v1`，相对 URL）
- `POST :3900/v1/audio/transcriptions` —— **OpenAI 兼容**转写（文件/脚本/现成 SDK 直接用）
- `WS   :3900/v1/audio/transcriptions/stream` —— 流式 partial/final
- `POST :3900/mcp/`（新版裸 `/mcp`）· stdio `python -m backend.mcp_shim` —— MCP 给 agent
- 回环客户端**免钥匙**；远端用 `OMNIVOICE_API_KEY` bearer；浏览器走 `/api/auth/ws-ticket`。

## 为什么这样做（主人令「整理提炼原生能力，这样就省去本地下载模型了」）
它的模型权重有**各自的许可**、本地要几 GB 磁盘；我们的口径是**只提炼"怎么连、怎么调"**：
本机若已装 VoiceStudio（或其后端）就直接调它的 Local API；没装就**如实报未部署**（`ok=false`），
绝不假装能跑、也不偷偷下模型。这样我们**不用下载模型**也能获得同一套语音能力面。

## 出网硬钉（本仓红线）
1. 只认 `http(s)`；2. **默认只许回环**（127.0.0.1 / localhost / ::1）；
3. 要连远端（LAN/公网）必须**显式** `GBT_VOICESTUDIO_ALLOW_REMOTE=1`，否则拒（不静默放行）；
4. 拒重定向；5. 密钥/票据**只回掩码**，永不回显。

## op
**桥接面（要上游后端在线）**：`status`（探活 + 协议版本）· `capabilities`（保真返回发现文档）·
`transcribe`（转写本地音频，OpenAI 兼容）· `plan` · `mcp_info` · `where`。

**三工作流面（2026-10-19 补 · **纯本地、不需要任何引擎**）**：
主人的三大自动化工作流是 **AI 短剧 / AI 电影 / AI 音乐**（`docs/GBT小土豆V8-模型卡.md` 逐字）。
这三条链在「声音」这一格真正缺的不是又一路 TTS，而是四件**引擎无关**的事 —— 谁的声音、
哪句从第几秒到第几秒、这句有多少秒的预算、字幕时间轴从哪来：

- `cast` —— **角色↔音色台账**（`state/voice-cast.json`）：短剧有 N 个角色、电影有旁白、
  音乐有人声，三工作流共用同一本账，音色才不会一片一个样。读写都在本仓 state/ 下，自收窄。
- `align` —— **音频节奏测绘**：ffmpeg 解码 → 20ms 帧能量 → 门限切段 → 每句 (start,end,dur)。
  这是字幕/剪辑/口型的时间轴真源；**不编时间轴**（切不出就如实报 0 段）。
- `fit` —— **时长预算**：给台词行与目标秒数，算每行可用秒数与建议语速（中文按字、西文按词）。
- `subtitle` —— 段 + 行 → **SRT**（行数与段数对不上就拒，绝不硬配）。
- `brief` —— 三工作流各自的**语音配方**：这一步要什么、本机有什么、缺什么、走哪个 op。

**全部只读**（无模型下载、无外网非回环调用）；只有 `cast` 的 set/rm 与 `subtitle` 的落盘会写，
写面自收窄在 `state/`。

## 为什么上游的 Local API 只给了「听」不给「说」（2026-10-19 现读 docs/speech-platform.md）
上游的 speech platform 是 **ASR 数据面**：`/v1/audio/transcriptions`、WS 流式、MCP。
**没有 TTS 端点** —— 合成/克隆/设计都在 Electron 应用本体里（它自己管模型与引擎）。
所以本能力位对"说"这件事**只提炼接口、不假装能跑**：要出声走本仓 `voice`（SAPI）或
`hf_voice`（云），要克隆就得上游装应用（AGPL-3.0，且声纹=生物特征，必须主人授权）。
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

OPS = ("status", "capabilities", "transcribe", "plan", "mcp_info", "where",
       "cast", "align", "fit", "subtitle", "brief", "say", "timeline")
READ_OPS = ("status", "capabilities", "plan", "mcp_info", "where",
            "align", "fit", "subtitle", "brief", "cast")
WRITE_OPS = ("cast", "say")          # cast 的 set/rm 会写 state/voice-cast.json；list/get 不写

DEFAULT_URL = "http://127.0.0.1:3900"
LOOPBACK = {"127.0.0.1", "localhost", "::1", "127.0.0.1:3900"}
UA = "gbt-v8/voice_studio (+native bridge)"


def _base() -> str:
    return (os.environ.get("GBT_VOICESTUDIO_URL") or DEFAULT_URL).strip().rstrip("/")


def _key() -> str:
    return (os.environ.get("GBT_VOICESTUDIO_KEY") or os.environ.get("OMNIVOICE_API_KEY") or "").strip()


def _allow_remote() -> bool:
    return (os.environ.get("GBT_VOICESTUDIO_ALLOW_REMOTE") or "").strip() in ("1", "true", "yes", "on")


def _mask(v: str) -> str:
    v = str(v or "")
    return (v[:4] + "****") if v else ""


def _guard(url: str) -> tuple:
    """回环默认 + 远端要显式开关；没开就拒（不静默放行）。"""
    from urllib.parse import urlparse
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return False, "只认 http(s)"
    host = (p.hostname or "").lower()
    if host in ("127.0.0.1", "localhost", "::1"):
        return True, ""
    if not _allow_remote():
        return False, ("目标不是回环（%s）⇒ 拒：要连远端请显式设 GBT_VOICESTUDIO_ALLOW_REMOTE=1" % host)
    return True, ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):   # noqa: D401
        return None                                                     # 跟随重定向=把"发到哪"交给对方


def _req(url: str, method: str = "GET", data: bytes | None = None,
         ctype: str = "application/json", timeout: int = 8) -> tuple:
    ok, why = _guard(url)
    if not ok:
        return -1, None, {"ok": False, "denied": True, "reason": why}
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if ctype:
        headers["Content-Type"] = ctype
    k = _key()
    if k:
        headers["Authorization"] = "Bearer " + k
    opener = urllib.request.build_opener(_NoRedirect())
    rq = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with opener.open(rq, timeout=timeout) as s:
            return s.status, s.read(), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except Exception:                                            # noqa: BLE001
            body = b""
        return e.code, body, None
    except Exception as e:                                           # noqa: BLE001
        return -1, None, {"ok": False, "未读到": "%s: %s" % (type(e).__name__, str(e)[:160])}


def status(**_kw) -> dict:
    base = _base()
    st, b, err = _req(base + "/.well-known/voicestudio-speech", timeout=5)
    if err:
        return {"ok": False, "op": "status", "base": base, **err,
                "note": "VoiceStudio 后端未部署/未启动 ⇒ 如实报未读到（不会自动下载模型）",
                "怎么接": "在本机装 VoiceStudio（或只跑它的 Python 后端）后重试；或设 GBT_VOICESTUDIO_URL 指向已部署后端"}
    try:
        j = json.loads((b or b"{}").decode("utf-8", "replace"))
    except Exception:                                                # noqa: BLE001
        return {"ok": False, "op": "status", "base": base, "http": st,
                "未读到": "发现文档不是 JSON", "raw": (b or b"")[:200].decode("utf-8", "replace")}
    return {"ok": bool(st and 200 <= st < 300), "op": "status", "base": base, "http": st,
            "protocol": j.get("protocol") or j.get("version") or "未读到",
            "features": (j.get("features") or {}) if isinstance(j.get("features"), dict) else {},
            "auth": "回环免钥匙" if not _key() else ("已带 bearer（掩码 %s）" % _mask(_key())),
            "note": "后端在线即可用；本能力只提炼接口，不下载模型"}


def capabilities(**_kw) -> dict:
    base = _base()
    st, b, err = _req(base + "/.well-known/voicestudio-speech", timeout=8)
    if err:
        return {"ok": False, "op": "capabilities", "base": base, **err}
    txt = (b or b"").decode("utf-8", "replace")
    try:
        doc = json.loads(txt)
    except Exception:                                                # noqa: BLE001
        return {"ok": False, "op": "capabilities", "http": st, "未读到": "非 JSON", "raw": txt[:200]}
    return {"ok": bool(st and 200 <= st < 300), "op": "capabilities", "http": st, "doc": doc}


def transcribe(path: str = "", language: str = "", model: str = "whisper-1", **_kw) -> dict:
    """转写**本机音频文件**（OpenAI 兼容端点）。只发到本机后端（默认回环），不发外网。"""
    p = Path(str(path or ""))
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[1] / p
    if not p.is_file():
        return {"ok": False, "op": "transcribe", "status": "file_not_found", "path": str(p),
                "note": "请给本机存在的音频文件路径（wav/mp3/webm…）"}
    base = _base()
    boundary = "----gbtvs%d" % os.getpid()
    fn = p.name
    head = (("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
             "Content-Type: application/octet-stream\r\n\r\n") % (boundary, fn)).encode()
    mid = ("\r\n--%s\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n%s\r\n" %
           (boundary, model)).encode()
    lang = ("--%s\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n%s\r\n" %
            (boundary, language)).encode() if language else b""
    tail = ("--%s--\r\n" % boundary).encode()
    body = head + p.read_bytes() + mid + lang + tail
    st, b, err = _req(base + "/v1/audio/transcriptions", method="POST", data=body,
                      ctype="multipart/form-data; boundary=" + boundary, timeout=300)
    if err:
        return {"ok": False, "op": "transcribe", "base": base, **err}
    txt = (b or b"").decode("utf-8", "replace")
    try:
        j = json.loads(txt)
        out = j.get("text") or j.get("transcript") or j
    except Exception:                                                # noqa: BLE001
        out = txt[:4000]
    return {"ok": bool(st and 200 <= st < 300), "op": "transcribe", "http": st,
            "file": fn, "language": language or "auto", "text": out,
            **({} if st and 200 <= st < 300 else {"raw": txt[:400]})}


def mcp_info(**_kw) -> dict:
    base = _base()
    return {"ok": True, "op": "mcp_info", "base": base,
            "mcp_http": base + "/mcp/",
            "mcp_http_note": "新版后端是裸 /mcp；老版是 /mcp/",
            "mcp_stdio": "python -m backend.mcp_shim（stdio 客户端，如 Claude Code/Codex）",
            "auth": "回环免钥匙；远端带 bearer（GBT_VOICESTUDIO_KEY / OMNIVOICE_API_KEY）",
            "_口径": "端点与用法来自上游 docs/speech-platform.md 现读（2026-10-17）"}


def plan(**_kw) -> dict:
    return {"ok": True, "op": "plan", "capability": "voice_studio",
            "上层能力面": ["语音克隆", "声音设计", "视频配音", "听写", "转写", "有声书", "646 语言"],
            "怎么接（三步）": [
                "① 本机装 VoiceStudio（Electron 或只跑 Python 后端）——模型由它自己管，我们不下载",
                "② 用 GBT_VOICESTUDIO_URL 指向后端（默认 http://127.0.0.1:3900）",
                "③ cap voice_studio '{\"op\":\"status\"}' 探活；在线即可 transcribe / 走 MCP"],
            "省在哪": "模型权重与许可都留在上游那边；我们只提炼接口（发现文档/OpenAI 兼容转写/MCP），"
                      "所以**不需要本地下载模型**，也不用维护引擎版本",
            "缺什么（如实）": ["没装后端 ⇒ status 会报未读到/未部署（不是'没有能力'）",
                            "远端连接需显式 GBT_VOICESTUDIO_ALLOW_REMOTE=1（默认只许回环）"],
            "边界": "本能力**只读**：不写盘、不下载模型、不外发非回环数据；克隆需授权且仅用有权限的声音",
            "_来源": "debpalash/VoiceStudio（AGPL-3.0）· docs/speech-platform.md · README（2026-10-17 现读）"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "voice_studio",
            "entry": "five-dim.py cap voice_studio '{\"op\":\"status\"}'",
            "ops": list(OPS),
            "what": "VoiceStudio 原生桥 + 三工作流语音面（cast/align/fit/subtitle/brief 纯本地）",
            "base": _base(),
            "remote_allowed": _allow_remote()}


# ═══════════════════════════════════════════════════════════════════════════
# 三工作流面（AI 短剧 / AI 电影 / AI 音乐）—— 下面这些**不需要任何语音引擎**
# ═══════════════════════════════════════════════════════════════════════════

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
CAST_FILE = STATE / "voice-cast.json"
FFMPEG = os.environ.get("GBT_FFMPEG") or "ffmpeg"


def _ffmpeg() -> str:
    """ffmpeg 路径：先用 PATH，再试 winget 的 Gyan 全量包（本机实测在那一层）。"""
    import shutil
    p = shutil.which(FFMPEG) or shutil.which("ffmpeg")
    if p:
        return p
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                        "Microsoft", "WinGet", "Packages")
    if os.path.isdir(base):
        for d in sorted(os.listdir(base), reverse=True):
            if d.startswith("Gyan.FFmpeg"):
                cand = os.path.join(base, d)
                for sub in os.listdir(cand):
                    exe = os.path.join(cand, sub, "bin", "ffmpeg.exe")
                    if os.path.exists(exe):
                        return exe
    return ""


def _abs(p: str) -> Path:
    q = Path(str(p or ""))
    return q if q.is_absolute() else (ROOT / q)


def _decode_pcm16k(path: Path) -> tuple:
    """ffmpeg → 16k 单声道 float32。零出网、只读本地文件。"""
    exe = _ffmpeg()
    if not exe:
        return None, "", "本机找不到 ffmpeg（PATH 与 winget 包都没有）"
    cmd = [exe, "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000",
           "-f", "wav", "-acodec", "pcm_s16le", "-"]
    try:
        cp = subprocess.run(cmd, capture_output=True, timeout=300)
    except Exception as e:                                            # noqa: BLE001
        return None, exe, "%s: %s" % (type(e).__name__, str(e)[:160])
    if cp.returncode != 0 or not cp.stdout:
        return None, exe, "ffmpeg 解码失败：%s" % (cp.stderr or b"")[:200].decode("utf-8", "replace")
    import soundfile as sf
    x, sr = sf.read(io.BytesIO(cp.stdout), dtype="float32", always_2d=False)
    return (x, sr), exe, ""


def align(path: str = "", min_gap: float = 0.22, min_len: float = 0.18,
          rel_db: float = 12.0, floor_db: float = -45.0, **_kw) -> dict:
    """**音频节奏测绘**：能量门切句 → 每句 (start, end, dur)。

    口径（写死，不随手改）：20ms 帧、10ms 跳；噪声底 = 帧能量的 20 分位；
    说话门限 = max(噪声底 × 10^(rel_db/20), 10^(floor_db/20))；间隔 < min_gap 合并；
    长度 < min_len 丢弃。切不出就如实报 0 段（**不编时间轴**）。
    """
    p = _abs(path)
    if not p.is_file():
        return {"ok": False, "op": "align", "status": "file_not_found", "path": str(p)}
    got, exe, why = _decode_pcm16k(p)
    if got is None:
        return {"ok": False, "op": "align", "status": "decode_failed", "path": str(p), "why": why}
    x, sr = got
    import numpy as np
    win, hop = int(0.020 * sr), int(0.010 * sr)
    if len(x) < win:
        return {"ok": False, "op": "align", "status": "too_short", "samples": int(len(x))}
    n = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    frames = x[idx]
    rms = np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1))
    db = 20.0 * np.log10(np.maximum(rms, 1e-9))
    noise = float(np.percentile(db, 20))
    thr = max(noise + rel_db, float(floor_db))
    hot = db > thr
    segs = []
    i = 0
    while i < n:
        if hot[i]:
            j = i
            while j + 1 < n and hot[j + 1]:
                j += 1
            segs.append([i * hop / sr, (j + 1) * hop / sr + win / sr])
            i = j + 1
        else:
            i += 1
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < min_gap:
            merged[-1][1] = s[1]
        else:
            merged.append(list(s))
    merged = [s for s in merged if (s[1] - s[0]) >= min_len]
    out = [{"i": k, "start": round(a, 3), "end": round(b, 3), "dur": round(b - a, 3)}
           for k, (a, b) in enumerate(merged)]
    total = round(len(x) / float(sr), 3)
    speech = round(sum(o["dur"] for o in out), 3)
    return {"ok": True, "op": "align", "file": p.name, "sr": sr, "total_sec": total,
            "segments": out, "n_segments": len(out), "speech_sec": speech,
            "speech_ratio": round(speech / total, 3) if total else 0.0,
            "gate": {"noise_db": round(noise, 1), "thr_db": round(thr, 1),
                     "rel_db": rel_db, "floor_db": floor_db,
                     "min_gap": min_gap, "min_len": min_len},
            "ffmpeg": exe}


def _cjk_weight(s: str) -> float:
    """中文按字、西文按词：一个 CJK 字 ≈ 2 个西文词的口播时长量级。"""
    cjk = sum(1 for ch in s if "\u3400" <= ch <= "\u9fff")
    latin = sum(1 for w in "".join(c if c.isalnum() or ord(c) < 128 else " "
                                   for c in s).split() if w)
    return cjk * 1.0 + latin * 0.5


def fit(lines=None, target_sec: float = 0.0, text: str = "", **_kw) -> dict:
    """**时长预算**：给台词行与目标秒数，算每行可用秒数与建议语速。"""
    if lines is None:
        lines = []
    if isinstance(lines, str):
        lines = [s for s in lines.splitlines() if s.strip()]
    if not lines and text:
        lines = [s for s in str(text).splitlines() if s.strip()]
    if not lines:
        return {"ok": False, "op": "fit", "status": "no_lines",
                "note": "给 lines（数组）或 text（按行切）"}
    try:
        tgt = float(target_sec or 0)
    except (TypeError, ValueError):
        tgt = 0.0
    if tgt <= 0:
        return {"ok": False, "op": "fit", "status": "no_target",
                "note": "给 target_sec（这一镜/这一段要有多少秒）"}
    w = [_cjk_weight(str(s)) for s in lines]
    tot = sum(w) or 1.0
    rows, acc = [], 0.0
    for k, s in enumerate(lines):
        sec = round(tgt * w[k] / tot, 2)
        acc += sec
        rows.append({"i": k, "text": str(s)[:80], "weight": round(w[k], 1),
                     "sec": sec, "start": round(acc - sec, 2), "end": round(acc, 2)})
    chars = sum(len(str(s)) for s in lines)
    return {"ok": True, "op": "fit", "target_sec": round(tgt, 2), "lines": rows,
            "n_lines": len(rows), "total_chars": chars,
            "建议语速": round(chars / tgt, 2) if tgt else 0,
            "_口径": "按 CJK 字=1、西文词=0.5 的比例分秒；这是**预算**，不是实测时长",
            "_下一步": "真要精确，用 align 量实际配音，再回填这里"}


def _srt_ts(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def subtitle(path: str = "", lines=None, text: str = "", out: str = "", **_kw) -> dict:
    """段 + 行 → SRT。**行数与段数对不上就拒**（绝不把台词硬塞到别人的时间轴上）。"""
    if lines is None and text:
        lines = [s for s in str(text).splitlines() if s.strip()]
    lines = [str(s) for s in (lines or [])]
    a = align(path=path)
    if not a.get("ok"):
        return {"ok": False, "op": "subtitle", "status": "align_failed", "align": a}
    segs = a["segments"]
    if lines and len(lines) != len(segs):
        return {"ok": False, "op": "subtitle", "status": "count_mismatch",
                "lines": len(lines), "segments": len(segs),
                "note": "行数≠段数 ⇒ 拒（硬配出来的字幕比没有更坏）。"
                        "先调 align 看切段，或调整 min_gap/min_len 再试",
                "segments_preview": segs[:12]}
    body = []
    for k, s in enumerate(segs):
        txt = lines[k] if lines else ""
        body.append("%d\n%s --> %s\n%s\n" % (k + 1, _srt_ts(s["start"]), _srt_ts(s["end"]), txt))
    srt = "\n".join(body)
    rec = {"ok": True, "op": "subtitle", "n": len(segs), "srt": srt}
    if out:
        q = _abs(out)
        try:
            rel = q.resolve().relative_to(ROOT.resolve())
        except ValueError:
            return {"ok": False, "op": "subtitle", "status": "out_of_repo",
                    "why": "落点必须在本仓内（%s）" % out}
        if rel.parts and rel.parts[0] not in ("projects", "outputs", ".scratch"):
            return {"ok": False, "op": "subtitle", "status": "out_not_allowed",
                    "why": "写面自收窄到 projects/ · outputs/ · .scratch/（得到 %s）" % rel.as_posix(),
                    "srt": srt}
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text(srt, encoding="utf-8")
        rec["out"] = str(q)
        rec["bytes"] = q.stat().st_size
    return rec


def cast(action: str = "list", who: str = "", voice: str = "", note: str = "", **_kw) -> dict:
    """**角色↔音色台账**（三工作流共用）。落 `state/voice-cast.json`。

    为什么这是"契合三工作流"的核心：短剧一集十几个角色、电影有旁白与主角、音乐有人声，
    音色一致性只能靠一本账；散在各链的配置里 ⇒ 一片一个样（本仓 F12 那类"两套名字空间"）。
    """
    act = str(action or "list").strip().lower()
    data = {}
    if CAST_FILE.is_file():
        try:
            data = json.loads(CAST_FILE.read_text(encoding="utf-8"))
        except Exception:                                            # noqa: BLE001
            data = {}
    voices = data.get("voices") or {}
    if act in ("list", "get"):
        if act == "get":
            if not who:
                return {"ok": False, "op": "cast", "status": "no_who", "note": "给 who（角色名）"}
            if who not in voices:
                return {"ok": False, "op": "cast", "status": "not_found", "who": who,
                        "known": sorted(voices)}
            return {"ok": True, "op": "cast", "action": "get", "who": who, "entry": voices[who]}
        return {"ok": True, "op": "cast", "action": "list", "n": len(voices),
                "voices": voices, "file": str(CAST_FILE)}
    if act == "set":
        if not who or not voice:
            return {"ok": False, "op": "cast", "status": "missing",
                    "note": "set 需要 who（角色名）与 voice（引擎/音色/参考音频指纹 任一标识）"}
        voices[who] = {"voice": voice, "note": note,
                       "at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds")}
        data["voices"] = voices
        data["schema"] = "gbt-voice-cast/v1"
        STATE.mkdir(parents=True, exist_ok=True)
        CAST_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "op": "cast", "action": "set", "who": who, "voice": voice,
                "n": len(voices), "file": str(CAST_FILE)}
    if act == "rm":
        if not who:
            return {"ok": False, "op": "cast", "status": "no_who"}
        if who not in voices:
            return {"ok": False, "op": "cast", "status": "not_found", "who": who}
        gone = voices.pop(who)
        data["voices"] = voices
        CAST_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "op": "cast", "action": "rm", "who": who, "removed": gone,
                "n": len(voices)}
    return {"ok": False, "op": "cast", "status": "unknown_action", "action": act,
            "available": ["list", "get", "set", "rm"]}


def _sha16(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def _dur(p: Path) -> float:
    """ffprobe 量时长（**回读产物**，不信合成器自报）。"""
    exe = _ffmpeg()
    if not exe:
        return -1.0
    probe = os.path.join(os.path.dirname(exe), "ffprobe.exe")
    probe = probe if os.path.exists(probe) else "ffprobe"
    try:
        cp = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=nw=1:nk=1", str(p)],
                            capture_output=True, timeout=60)
        return round(float((cp.stdout or b"0").decode().strip() or 0), 3)
    except Exception:                                                # noqa: BLE001
        return -1.0


def _out_ok(rel_parts) -> tuple:
    if not rel_parts:
        return False, "空路径"
    if rel_parts[0] not in ("projects", "outputs", ".scratch"):
        return False, "写面自收窄到 projects/ · outputs/ · .scratch/（得到 %s）" % "/".join(rel_parts)
    return True, ""


def say(text: str = "", lines=None, who: str = "", engine: str = "edge",
        voice: str = "", rate: str = "+0%", pitch: str = "+0Hz",
        out: str = "", concat: str = "", **_kw) -> dict:
    """**台词 → 音频**（三工作流的"出声"那一格）。engine=edge 用本机已装的 edge-tts。

    🔴 老实说：edge-tts 是**云端合成**（本仓欢迎语 voice-greet-zh-tw.mp3 本来就是它），
    文字会发到微软。要"文字不出本机"就必须换本地引擎（Kokoro/Piper，见 op=plan）。
    engine=sapi 走本机 Windows SAPI（真本地，音色少）；engine=upstream 转发到 VoiceStudio 后端（目前上游 Local API 无 TTS 端点 ⇒ 会如实报不可用）。
    """
    eng = str(engine or "edge").strip().lower()
    if lines is None and text:
        lines = [s for s in str(text).splitlines() if s.strip()]
    lines = [str(s) for s in (lines or []) if str(s).strip()]
    if not lines:
        return {"ok": False, "op": "say", "status": "no_text", "note": "给 text 或 lines（数组）"}

    # 音色：显式 voice > 台账里这个角色 > 默认（与欢迎语同一副嗓子）
    v = str(voice or "").strip()
    src = "explicit" if v else ""
    if not v and who:
        c = cast(action="get", who=who)
        if c.get("ok"):
            vv = str((c.get("entry") or {}).get("voice") or "")
            v = vv.split(":", 1)[1] if vv.startswith("edge:") else vv
            src = "cast" if v else ""
    if not v:
        v = "zh-TW-HsiaoChenNeural"
        src = src or "default"
    if eng == "edge" and "Neural" not in v:
        # 归因先排除"根本没有"：名字不像 edge 音色 id 就别去撞网，直接带原因拒（P26）
        return {"ok": False, "op": "say", "status": "bad_voice", "engine": eng, "voice": v,
                "voice_src": src,
                "why": "edge-tts 的音色名必须是 xx-XX-XXXXNeural 形态；台账里这条不是（%s）" % v,
                "known": ["zh-TW-HsiaoChenNeural", "zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"]}

    base_out = _abs(out) if out else (ROOT / "outputs" / "voice-studio")
    try:
        rel = base_out.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return {"ok": False, "op": "say", "status": "out_of_repo", "out": str(base_out)}
    okp, why = _out_ok(rel.parts)
    if not okp:
        return {"ok": False, "op": "say", "status": "out_not_allowed", "why": why}
    base_out.mkdir(parents=True, exist_ok=True)

    made, recs = [], []
    if eng == "upstream":
        return {"ok": False, "op": "say", "status": "engine_unavailable", "engine": eng,
                "why": "上游 Local API 只有转写端点，没有 TTS（见 docs/speech-platform.md 现读）",
                "怎么用": "装 VoiceStudio 应用本体（它自带合成）或用 engine=edge / sapi"}
    if eng not in ("edge", "sapi"):
        return {"ok": False, "op": "say", "status": "unknown_engine", "engine": eng,
                "available": ["edge", "sapi", "upstream"]}

    for i, ln in enumerate(lines):
        stem = "line%02d" % i
        if eng == "edge":
            try:
                import asyncio
                import edge_tts
            except ImportError:
                return {"ok": False, "op": "say", "status": "engine_unavailable", "engine": "edge",
                        "why": "本机没有 edge_tts 包（pip install edge-tts）"}
            p = base_out / (stem + ".mp3")
            try:
                async def _go(txt=ln, path=str(p)):
                    c = edge_tts.Communicate(txt, v, rate=rate, pitch=pitch)
                    await c.save(path)
                asyncio.run(_go())
            except Exception as e:                                   # noqa: BLE001
                return {"ok": False, "op": "say", "status": "synth_failed", "engine": eng,
                        "line": i, "why": "%s: %s" % (type(e).__name__, str(e)[:160]),
                        "note": "edge-tts 是云端合成，没网就会失败（要完全本地见 op=plan）"}
        else:  # sapi
            try:
                import win32com.client  # noqa: F401
            except ImportError:
                pass
            p = base_out / (stem + ".wav")
            ps = ("Add-Type -AssemblyName System.Speech;"
                  "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                  "$s.SetOutputToWaveFile('%s');$s.Speak('%s');$s.Dispose()"
                  % (str(p).replace("'", "''"), ln.replace("'", "''").replace('"', '')))
            cp = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                capture_output=True, timeout=180)
            if cp.returncode != 0 or not p.exists():
                return {"ok": False, "op": "say", "status": "synth_failed", "engine": "sapi",
                        "line": i, "why": (cp.stderr or b"")[:160].decode("utf-8", "replace")}
        if not p.exists() or p.stat().st_size < 512:
            return {"ok": False, "op": "say", "status": "empty_output", "line": i, "path": str(p)}
        made.append(p)
        recs.append({"i": i, "text": ln[:80], "path": str(p), "bytes": p.stat().st_size,
                     "dur": _dur(p), "sha16": _sha16(p)})

    joined = ""
    if concat:
        q = _abs(concat)
        try:
            relq = q.resolve().relative_to(ROOT.resolve())
            okq, whyq = _out_ok(relq.parts)
        except ValueError:
            okq, whyq = False, "落点必须在本仓内"
        if not okq:
            return {"ok": False, "op": "say", "status": "concat_not_allowed", "why": whyq,
                    "made": recs}
        q.parent.mkdir(parents=True, exist_ok=True)   # ffmpeg 不会自己建目录（踩过：concat_failed）
        lst = base_out / "_concat.txt"
        lst.write_text("".join("file '%s'\n" % str(x).replace("\\", "/") for x in made),
                       encoding="utf-8")
        cmdc = [_ffmpeg(), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                "-ac", "1", "-ar", "16000", str(q)]
        cp2 = subprocess.run(cmdc, capture_output=True, timeout=300)
        if cp2.returncode != 0 or not q.exists():
            return {"ok": False, "op": "say", "status": "concat_failed",
                    "why": (cp2.stderr or b"")[:200].decode("utf-8", "replace"), "made": recs}
        joined = str(q)

    # 可指回：引擎 + 参数 + 输入指纹，一行一笔记进 state/
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        with open(STATE / "voice-say.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": __import__("datetime").datetime.now().astimezone()
                                 .isoformat(timespec="seconds"),
                                 "engine": eng, "voice": v, "voice_src": src,
                                 "rate": rate, "pitch": pitch,
                                 "lines": [{"sha16": r["sha16"], "dur": r["dur"],
                                            "chars": len(r["text"])} for r in recs],
                                 "concat": joined}, ensure_ascii=False) + "\n")
    except Exception:                                                # noqa: BLE001
        pass

    return {"ok": True, "op": "say", "engine": eng, "voice": v, "voice_src": src,
            "rate": rate, "pitch": pitch, "n": len(recs), "made": recs,
            "concat": joined, "out_dir": str(base_out),
            "_口径": "时长是 ffprobe 回读产物的真读数，不是合成器自报",
            "_注意": "edge 是云端合成（文字会发到微软）；要文字不出本机见 op=plan"}


def _wrap_cjk(t: str, n: int) -> str:
    r"""按 n 个字硬折行；窗口里若有标点就断在最后一个标点后（给 libass 用 \N）。"""
    if n <= 0 or len(t) <= n:
        return t
    out, i = [], 0
    P = "，。！？；：、,.!?;:）)」』"
    while i < len(t):
        win = t[i:i + n]
        cut = len(win)
        if i + n < len(t):
            for k in range(len(win) - 1, 2, -1):
                if win[k] in P:
                    cut = k + 1
                    break
        out.append(t[i:i + cut])
        i += cut
    return "\\N".join(out)

def timeline(paths=None, lines=None, out: str = "", wrap: int = 0, **_kw) -> dict:
    """**剧本时间轴**：按"每句一个音频件"的**实测时长**累加出每句起止，再出 SRT。

    和 `align` 的分工（这两件不是重复）：
      · `timeline` 用在**我们自己生成**的对白上 —— 每句的边界是精确的（累加实测时长）；
      · `align` 用在**别人给的**素材上 —— 只能靠能量切段猜，切几段就是几段。
    """
    ps = [str(x) for x in (paths or []) if str(x).strip()]
    if not ps:
        return {"ok": False, "op": "timeline", "status": "no_paths",
                "note": "给 paths（每句一个音频件，顺序即台词顺序）"}
    ls = [str(x) for x in (lines or [])]
    if ls and len(ls) != len(ps):
        return {"ok": False, "op": "timeline", "status": "count_mismatch",
                "paths": len(ps), "lines": len(ls),
                "note": "行数与音频件数必须一致（不一致就是配错了，不硬配）"}
    cues, t = [], 0.0
    for k, raw in enumerate(ps):
        q = _abs(raw)
        if not q.is_file():
            return {"ok": False, "op": "timeline", "status": "file_not_found", "path": str(q)}
        d = _dur(q)
        if d <= 0:
            return {"ok": False, "op": "timeline", "status": "no_duration", "path": str(q),
                    "note": "ffprobe 量不到时长（文件坏了或缺 ffmpeg）"}
        txt = ls[k] if ls else ""
        cues.append({"i": k, "start": round(t, 3), "end": round(t + d, 3), "dur": d,
                     "text": txt, "srt_text": _wrap_cjk(txt, int(wrap or 0)), "path": str(q)})
        t += d
    body = []
    for c in cues:
        body.append("%d\n%s --> %s\n%s\n" % (c["i"] + 1, _srt_ts(c["start"]),
                                             _srt_ts(c["end"]), c.get("srt_text") or c["text"]))
    srt = "\n".join(body)
    rec = {"ok": True, "op": "timeline", "n": len(cues), "total_sec": round(t, 3), "cues": cues,
           "srt": srt, "_口径": "每句边界 = 前若干句实测时长累加（精确，不是估的）"}
    if out:
        q = _abs(out)
        try:
            rel = q.resolve().relative_to(ROOT.resolve())
            okp, why = _out_ok(rel.parts)
        except ValueError:
            okp, why = False, "落点必须在本仓内"
        if not okp:
            return {"ok": False, "op": "timeline", "status": "out_not_allowed", "why": why, "srt": srt}
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text(srt, encoding="utf-8")
        rec["out"] = str(q)
        rec["bytes"] = q.stat().st_size
    return rec


BRIEF = {
    "short_video": {
        "workflow": "AI 短剧",
        "steps": "script→storyboard→assets→edit→export（media_pipeline.KINDS.short_video）",
        "语音落在哪": "assets（每角色配音）+ edit（字幕与对白时长）",
        "现在能给": ["cast 定每个角色的音色", "fit 按镜头时长分台词预算",
                     "align 量已生成配音的真时间轴", "subtitle 出 SRT（行数=段数才出）"],
        "缺什么": ["本机没有 TTS/克隆引擎（Local API 只有 ASR）⇒ 真出声要走 voice(SAPI) 或 hf_voice(云)",
                   "多角色一致性要等引擎到位才能验；现在只能记账"],
    },
    "film": {
        "workflow": "AI 电影",
        "steps": "concept→script→shots→sound→edit→export（media_pipeline.KINDS.film）",
        "语音落在哪": "sound（旁白/对白）+ edit（与分镜时长对齐）",
        "现在能给": ["cast 定旁白与主角音色", "fit 按分镜时长分旁白",
                     "align 量旁白时间轴与停顿（剪辑点靠它）", "subtitle 出成片字幕"],
        "缺什么": ["长旁白（有声书式）切块与断句策略未接引擎",
                   "多语言（646 语言）要上游应用本体，不是 Local API"],
    },
    "music": {
        "workflow": "AI 音乐",
        "steps": "lyrics→arrangement→audio→master→export（media_pipeline.KINDS.music）",
        "语音落在哪": "audio（人声/念白/和声）",
        "现在能给": ["align 量人声/伴奏的能量段，喂四条时间轴对齐（歌词↔音频）",
                     "cast 记人声音色（与 music_auto 的歌词时间轴对接）"],
        "缺什么": ["本机零算力跑不动歌声合成（hf_voice 已实测：真唱走云）",
                   "音色设计/克隆需上游应用，且声纹=生物特征，要主人授权"],
    },
}


def brief(workflow: str = "", **_kw) -> dict:
    """三工作流各自的语音配方（这一步要什么、本机有什么、缺什么、走哪个 op）。"""
    w = str(workflow or "").strip().lower()
    if not w:
        return {"ok": True, "op": "brief", "workflows": sorted(BRIEF),
                "note": "给 workflow=short_video|film|music 取单条配方"}
    if w not in BRIEF:
        return {"ok": False, "op": "brief", "status": "unknown_workflow", "workflow": w,
                "available": sorted(BRIEF)}
    return {"ok": True, "op": "brief", **BRIEF[w],
            "_上游": "debpalash/VoiceStudio（AGPL-3.0，只蒸馏思想不搬代码）"}


def run_op(op: str = "status", **kw) -> dict:
    """门面分派（`api._run_benign` 用）：op → 本模块函数；未知 op **fail-closed** 并给可用 op。"""
    table = {"status": status, "capabilities": capabilities, "transcribe": transcribe,
             "plan": plan, "mcp_info": mcp_info, "where": where,
             "cast": cast, "align": align, "fit": fit, "subtitle": subtitle, "brief": brief, "timeline": timeline,
             "say": say}
    fn = table.get(str(op or "status").strip().lower())
    if fn is None:
        return {"ok": False, "op": op, "status": "unknown_op", "available": sorted(table),
                "_口径": "未知 op 一律拒，不猜"}
    return fn(**kw)

