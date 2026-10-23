# gbt-capability: voice
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""voice 能力 — Windows SAPI 语音合成 + **本机离线听觉**（两个真实后端）。

tts   : Windows SAPI.SpVoice（零依赖，Windows 自带）→ 播放或转 WAV 落盘
asr   : 云端 OpenAI 兼容端点（需 GBT_ASR_BASE_URL / GBT_ASR_API_KEY）
listen: **本机离线识别**（Windows 桌面识别器 System.Speech）—— 零密钥、零安装。
        主人令 2026-09-23：「打开页面就自动监听，关掉页面她也跟着关，大脑后台照常跑」
        ⇒ 这条腿的价值就是**不需要任何密钥**：本机现读有 `MS-2052-80-DESK（zh-CN）`。

────────────────────────────────────────────────────────────────────────────
🟢 **门盲区已关闭（2026-10-18 更正这段旧注释）**

  旧文（2026-09-23 写的）说：`op="listen"` **不挂任何作用域**、门拦不住它，
  并请主人在 `policy.py` 里补一行 —— **那句现在已经不成立了**，留着会误导下一个人。

  现读事实（`gbt_allinone/security/policy.py` 的 `voice` 分支）：
      if p.get("out"):                                    add("filesystem_write")
      if (op or "tts") in ("tts", "speak", None):         add("audio_output")
      if op in ("listen", "asr", "record"):               add("privacy_read")   # 2026-10-09 主人令补的
  ⇒ 耳（listen/asr/record）与眼（读屏）同一档：**要 privacy_read 票**；嘴 = audio_output。
  ⇒ 实测证据（2026-10-18 真跑，不是读代码猜）：
       cap voice '{"op":"listen","seconds":3,"culture":"zh-CN"}'
       → status=denied · missing=["privacy_read"] · how_to_grant 给出主人终端命令

  返回里的 `gate_blind_spot` 字段**不是静态断言**：它现读 policy 解析出真实作用域
  （`_voice_scopes(op)`），读不到就写「未读到」，不写「无盲区」。
────────────────────────────────────────────────────────────────────────────
🔴 **第 59 轮实测：`listen` 原来那条输入路在本机是死的，已改成两条腿。**
   本机现读（2026-09-23，四套音频 API 全查过）：
     · `waveInGetNumDevs() = 0` ⇒ `SetInputToDefaultAudioDevice()` 那条路是**旧版 waveIn
       映射器**，它**永远**抛 "Cannot find the requested data item"。
       ⚠️ 这跟插不插麦克风无关 —— 权威 API（MMDevice）现读录音侧 5 个端点，
       **在场的 0 个**（1 禁用 / 1 拔出 / 3 不在场），三个角色的默认录音设备**全不存在**。
     · MME 0 · DirectSound 0 · WASAPI 0 个输入端点；WDM-KS 列 4 个引脚但全部打不开。
   ⇒ `listen` 现在按顺序试两条腿，**两条腿的原因都留在 `legs` 里，不吞**：
       ① `wasapi-record.py`（PortAudio：MME/DirectSound/WASAPI/WDM-KS 都能看见）
          → 落成 16k/16bit/单声道 WAV → `asr-listen.ps1 -WavFile`
          —— PortAudio 能看见的端点**严格多于** winmm ⇒ 这条腿优先。
       ② 设备直连 `asr-listen.ps1`（无 `-WavFile`）—— 腿①不通时的兜底。
   ⚠️ 腿①会在**系统临时目录**写一个 WAV（用完即删）⇒ 本能力的"会动手"面比原来多了一项，
      这条也照实写进 `gate_blind_spot`，不藏。
────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# 本机离线识别助手（Windows 桌面识别器）。放在仓的 tools/ 下，随版本管理。
_LOCAL_ASR_PS = Path(__file__).resolve().parents[1] / "tools" / "codex-scripts" / "asr-listen.ps1"
# 录音件（PortAudio/WASAPI）——绕开旧版 winmm 映射器的那条腿。见文件头第 59 轮那段。
_LOCAL_REC = Path(__file__).resolve().parents[1] / "tools" / "codex-scripts" / "wasapi-record.py"
# 回环件（WASAPI loopback：录**系统播放**，不依赖采集引脚）—— 2026-10-18 主人令「缺啥就抓取成熟能力补齐」
_LOCAL_LOOP = Path(__file__).resolve().parents[1] / "tools" / "codex-scripts" / "wasapi-loopback.py"
_RECOG_CACHE = {"at": 0.0, "list": None}

# 依赖兜底：唯一真相源走 dependency_paths.activate_local_dependencies()。
# 不再手打 sys.path：手打会漏掉 ABI overlay（.pylibs/<abi>），
# 且会把 legacy 树顶到 sys.path[0]，对撞「系统包优先于 legacy 兜底」的设计。
try:
    from .dependency_paths import activate_local_dependencies
except ImportError:            # 以脚本方式直跑本文件时
    from gbt_allinone.dependency_paths import activate_local_dependencies
activate_local_dependencies()


def _edge_tts(text: str, voice: str = "zh-TW-HsiaoChenNeural", out: str | None = None,
              edge_rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%",
              play: bool = True) -> dict:
    """Edge 神经语音（免费 · 高音质 · 14 种中文含台湾腔/辽宁腔）→ MP3 落盘 + 播放。
    主人 2026-10-04 定：台湾腔（zh-TW-HsiaoChenNeural）为默认。比 SAPI 好几个档次。

    2026-10-13 加 `edge_rate` / `pitch` / `volume` 三个透传口（主人反馈「像念稿、死板」）：
    edge-tts 7.x 的 Communicate 支持这三个韵律参数，原先没接 ⇒ 出来是一根平线。
    三者**只作用于 edge-tts 这条路**；默认值 "+0%/+0Hz/+0%" ⇒ 不传时与改动前逐字节相同。
    （注意与既有的整数 `rate` 不是一回事：那个是 SAPI 的档位。）
    """
    try:
        import edge_tts
        import asyncio

        async def _synth():
            tts = edge_tts.Communicate(text, voice, rate=edge_rate,
                                       pitch=pitch, volume=volume)
            path = out or os.path.join(
                os.environ.get("TEMP", os.environ.get("TMP", "")),
                "gbt_edge_tts.mp3")
            # 父目录不存在时 tts.save 会 [WinError 2] 并触发外层静默回退 SAPI —— 先建好
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            await tts.save(path)
            return path

        path = asyncio.run(_synth())
        # 播放（安全：os.startfile 不经 shell，不拼命令）
        # 🔴 2026-10-18 修（主人投诉「还有其他声音参入」时挖到的）：原来**不管调用方要什么**都 startfile 播放，
        #    于是连 `op=tts`（只要一个文件）也会突然出声 —— 写盘动作不该发声音。
        #    ⇒ 只有 `play=True`（"念一句"）才播放；`op=tts` 落盘走 play=False。
        if play:
            os.startfile(path)
        return {"ok": True, "backend": "edge-tts", "voice": voice,
                "file": path, "spoken": bool(play), "text": text[:80],
                "edge_rate": edge_rate, "pitch": pitch, "volume": volume}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"edge-tts 失败: {str(e)[:160]}"}


# ─────────────────────────────────────────────────────────────────────────────
# VoiceStudio 本地语音工作台（上游：debpalash/VoiceStudio · AGPL-3.0 · 已接
# `_upstream/VoiceStudio`，headless 后端跑 127.0.0.1:3900）。主人 2026-10-04「下一步」。
# 这条道的价值：**完全本地**的克隆/设计/646 语言（不经任何云端）。代价：CPU + 内存
# （本机 7.9G RAM：OmniVoice 2.4G 权重档会把机器挤到交换；轻量档 MOSS-TTS-Nano 100M 更合身）。
# 出站只许**字面回环**：四重校验见 `_vs_url()`（协议 / 主机白名单 / 解析后 IP 必须回环 /
# 禁重定向）——与 `tools/codex-scripts/cliproxy.py` 同款边界，无任何用户输入参与目标构造。
# 服务起停/克隆/转写/模型管理的操作口是本仓 `tools/codex-scripts/voicestudio.py`。
# ─────────────────────────────────────────────────────────────────────────────
import ipaddress as _ipaddress
import socket as _socket
import urllib.parse as _urlparse
import urllib.request as _urlrequest

_VS_HOST = "127.0.0.1"                  # 本组合唯一的出站目标（字面值，非常量拼接）
_VS_PORT = int(os.environ.get("OMNIVOICE_PORT", "3900") or 3900)
_VS_ALLOWED_HOSTS = ("127.0.0.1",)      # 主机白名单：只有一个字面回环地址
_VS_OUT = Path(__file__).resolve().parents[1] / "state" / "voicestudio" / "out"


class _VSNoRedirect(_urlrequest.HTTPRedirectHandler):
    """拒绝重定向：本地服务不该把我们导去别处（防被引导型 SSRF）。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_VS_OPENER = _urlrequest.build_opener(_VSNoRedirect)


def _vs_url(path: str) -> str:
    """VoiceStudio 的唯一出站点。四重校验：路径形状 → 协议 → 主机白名单 → 解析后 IP 必须回环。"""
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("路径必须以单个 / 开头：%r" % path[:40])
    url = "http://%s:%d%s" % (_VS_HOST, _VS_PORT, path)
    parts = _urlparse.urlsplit(url)
    if parts.scheme != "http":
        raise ValueError("只许 http：%r" % url)
    if parts.hostname not in _VS_ALLOWED_HOSTS:
        raise ValueError("主机不在白名单 %r 内，拒绝：%r" % (_VS_ALLOWED_HOSTS, url))
    try:
        ip = _ipaddress.ip_address(_socket.gethostbyname(parts.hostname))
    except ValueError as e:
        raise ValueError("主机解析失败，拒绝：%r（%s）" % (url, e))
    if not ip.is_loopback:
        raise ValueError("解析后 IP 非回环，拒绝：%s" % ip)
    return url


def _vs_health(timeout: float = 1.0) -> tuple[bool, str | None]:
    """→ (是否在跑, 版本)。连不上⇒(False, None)，不算错——只是"没起"。"""
    try:
        with _VS_OPENER.open(_vs_url("/health"), timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
            return True, d.get("version")
    except Exception:  # noqa: BLE001
        return False, None


def voicestudio_tts(text: str, profile: str | None = None, language: str | None = None,
                    out: str | None = None, instruct: str | None = None,
                    speed: float = 1.0, steps: int = 16, timeout: float = 900.0,
                    play: bool = True, engine: str | None = None) -> dict:
    """VoiceStudio（本地克隆引擎 · 646 语言）出声 → WAV 落盘（+ 播放）。

    `engine` 可点名引擎：`omnivoice`（默认 · 质量档 · 本机 CPU 约 157s/句）、
    `moss-tts-nano`（轻量档 100M · 本机热启动快得多）。不点名 = 服务端默认。

    失败**如实报**（backend_down + reason + 起法），**绝不偷偷降级到别的嗓子**
    —— 显式点名这条道时，静默换成 edge-tts 会让主人以为听到的是克隆声。
    """
    if not text:
        raise ValueError("缺少 text：要合成的文本")
    import uuid as _uuid
    boundary = "----gbtVScap" + _uuid.uuid4().hex
    fields = {"text": text, "speed": str(speed), "num_step": str(steps)}
    if language:
        fields["language"] = language
    if profile:
        fields["profile_id"] = profile
    if instruct:
        fields["instruct"] = instruct
    if engine:
        fields["engine"] = engine
    chunks = []
    for k, v in fields.items():
        chunks.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                       % (boundary, k, v)).encode("utf-8"))
    chunks.append(("--%s--\r\n" % boundary).encode("utf-8"))
    req = _urlrequest.Request(_vs_url("/generate"), data=b"".join(chunks), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=%s" % boundary)
    try:
        with _VS_OPENER.open(req, timeout=timeout) as resp:
            raw = resp.read()
            aid = (resp.headers.get("X-Audio-Id") or "").strip()
            gen = resp.headers.get("X-Gen-Time")
            dur = resp.headers.get("X-Audio-Duration")
    except Exception as e:  # noqa: BLE001 —— 连不上/超时/5xx 都属于"这条道现在出不了声"
        return {"ok": False, "backend": "voicestudio", "status": "backend_down",
                "reason": "%s: %s" % (type(e).__name__, str(e)[:160]),
                "spoken": False,
                "hint": "起服务：py -3.14 tools/codex-scripts/voicestudio.py up"}
    target = Path(out) if out else (_VS_OUT / ("vs-%s.wav" % (aid or ("t%d" % int(time.time())))))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    res = {"ok": True, "backend": "voicestudio", "file": str(target), "bytes": len(raw),
           "audio_id": aid or None, "gen_time_s": gen, "audio_duration_s": dur,
           "profile_id": profile, "language": language, "text": text[:80], "spoken": False}
    if play:
        os.startfile(str(target))  # 安全：不经 shell
        res["spoken"] = True
    return res


def tts(text, voice=None, rate=0, out=None, backend=None, engine=None,
        edge_rate="+0%", pitch="+0Hz", volume="+0%", play=None):
    """语音合成。链：**显式点名 voicestudio（本地克隆引擎）** → edge-tts 神经语音
    （默认台湾腔 zh-TW-HsiaoChenNeural）→ SAPI 回退。

    `backend="voicestudio"` 或 `voice="vs:<profile_id>"` ⇒ **只走 VoiceStudio**；
    服务没起就如实报 backend_down（不偷偷换嗓子）。`engine` 透传给 VoiceStudio
    （`omnivoice`=质量档 / `moss-tts-nano`=轻量快速档）。不点名时行为与改动前一致。

    `play`（2026-10-19 加，可省）：显式决定"要不要出声"。
    不传时沿用老口径「有 out 就不出声」（写盘动作不该发声音，主人投诉过）。
    **传了就按传的来** —— 剧场要「一次合成、既落盘又出声」时传 `play=true`，
    免得为了出声再跑一遍合成（那样波形与听到的会来自两次不同的合成）。
    """
    if not text:
        raise ValueError("缺少 text：要合成的文本")
    _vs = backend == "voicestudio" or (isinstance(voice, str) and voice.startswith("vs:"))
    if _vs:
        prof = voice[3:].strip() or None if (isinstance(voice, str) and voice.startswith("vs:")) else None
        return voicestudio_tts(text, profile=prof, out=out, engine=engine)
    # edge-tts 优先（音质好几个档次）
    try:
        import edge_tts  # noqa: F401
        v = voice or "zh-TW-HsiaoChenNeural"   # 主人定：台湾腔
        r = _edge_tts(text, voice=v, out=out, edge_rate=edge_rate,
                      pitch=pitch, volume=volume,
                      # 🔴 只写文件时**不出声**：写盘动作不该发声音（主人投诉「还有其他声音参入」的直接来源之一）
                      #    2026-10-19：`play` 显式给了就以它为准（剧场要"一次合成、又落盘又出声"）。
                      play=(not bool(out)) if play is None else bool(play))
        if r.get("ok"):
            return r
        # 2026-10-17 主人令：主人听到的是鬼叫声（SAPI 回落 zh-CN）=> **fail-closed**
        # 拿不到台湾腔就不出声，不许用大陆腔/怪声顶替。显式点非 zh-TW 声才允许走 SAPI。
        if isinstance(v, str) and v.startswith("zh-TW"):
            # 🔴 2026-10-18 修（P19/P26）：原来这里把原因**写死**成「wss 403」，
            #    而 `_edge_tts` 真实失败原因被丢掉 ⇒ 读数永远是旧结论，无法定位当场发生了什么。
            #    现在原话透传：`raw` 是上游原样，`reason` 带上它。
            raw = str(r.get("error") or "edge-tts 没回原因（连 error 字段都没有）")
            return {"ok": False, "status": "no_taiwan_lane", "voice": v,
                    "reason": "拿不到台湾腔：" + raw,
                    "raw": raw,
                    "note": "本机无 zh-TW SAPI 发音人 ⇒ 按主人令 fail-closed，不用大陆腔顶替",
                    "policy": "主人令：拿不到台湾腔就不出声（不用大陆腔顶替）",
                    "how": "装 zh-TW 离线发音人（设置→语言→中文繁体台湾→语音）或放行 speech.platform.bing.com"}
        # edge-tts 失败 → 降 SAPI（仅当调用方显式点非 zh-TW 声）
    except ImportError:
        pass
    # SAPI 回退
    try:
        import comtypes.client
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "needs_dependency",
                "missing": "comtypes（.pylibs 已带；当前解释器未加载）",
                "detail": str(e)[:120]}
    try:
        sapi = comtypes.client.CreateObject("SAPI.SpVoice")
        if voice:
            for v in sapi.GetVoices():
                if voice.lower() in str(v.GetDescription()).lower():
                    sapi.Voice = v
                    break
        sapi.Rate = int(rate)
        if out:
            # 落盘 WAV（SAPI.SpFileStream）
            stream = comtypes.client.CreateObject("SAPI.SpFileStream")
            out_p = Path(out)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            stream.Open(str(out_p), 3)  # SSFMCreateForWrite = 3
            try:
                sapi.AudioOutputStream = stream
                sapi.Speak(text)
            finally:
                # 🔴 2026-09-26 修：Speak 抛异常时原来不 Close —— WAV 句柄占用、半成品文件锁死
                stream.Close()
            return {"ok": True, "backend": "win-sapi", "wav": str(out_p),
                    "text": text[:80], "size_kb": round(out_p.stat().st_size / 1024, 1)}
        # 直接播放
        sapi.Speak(text)
        return {"ok": True, "backend": "win-sapi", "spoken": True, "text": text[:80]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"SAPI 合成失败: {str(e)[:160]}"}


def asr(audio=None):
    """语音识别（ASR）。

    需配置 GBT_ASR_BASE_URL / GBT_ASR_API_KEY（OpenAI 兼容 /audio/transcriptions 端点）。
    未配置时如实返回 needs_dependency，不伪造转写结果。
    """
    base = os.environ.get("GBT_ASR_BASE_URL", "")
    key = os.environ.get("GBT_ASR_API_KEY", "")
    if not (base and key):
        return {"ok": False, "status": "needs_dependency",
                "missing": "GBT_ASR_BASE_URL / GBT_ASR_API_KEY",
                "note": "ASR 后端未配置；tts（SAPI）已可用"}
    if not audio:
        raise ValueError("缺少 audio：要转写的音频路径")
    try:
        import hashlib
        from .security import net_guard as _ng
        from .security import ai_audit as _audit
        from .security import policy as _policy
        p = Path(audio)
        if not p.exists():
            raise ValueError(f"音频文件不存在: {audio}")
        boundary = "----gbtvoice"
        blob = p.read_bytes()
        model = os.environ.get("GBT_ASR_MODEL", "whisper-1")
        body = _io_boundary(boundary, p)
        url = base.rstrip("/") + "/audio/transcriptions"
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}",
                   "Authorization": f"Bearer {key}"}
        # R120：语音原文与密钥都不进账本，只留长度/指纹。
        ctx = _audit.begin("openai-asr", url, model=model,
                           request_body={"model": model, "filename": p.name,
                                         "audio_bytes": len(blob),
                                         "audio_sha256": hashlib.sha256(blob).hexdigest()},
                           headers=headers)
        response = _ng.safe_request_json(
            url, method="POST", headers=headers, body=body, timeout=120,
            max_bytes=8_000_000, allow_private=_policy.is_trusted())
        status = int(response.get("status") or 0)
        data = response.get("json")
        if status >= 400 or not isinstance(data, dict):
            _audit.finish(ctx, status=status, ok=False, response_text=response.get("text"))
            return {"ok": False,
                    "error": "HTTP %s: %s" % (status, str(response.get("text") or "")[:200])}
        _audit.finish(ctx, status=status, ok=True, response=data,
                      response_text=data.get("text", ""))
        return {"ok": True, "backend": "cloud", "text": data.get("text", "")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:200]}


def _ps_exe():
    for n in ("pwsh", "powershell"):
        p = shutil.which(n)
        if p:
            return p
    return None


def recognizers(ttl=300.0):
    """本机装了哪些**离线**识别器（只枚举，**不开任何设备**，无副作用）。

    为什么要单列一个：`op=status` 必须能如实说清"离线这条路能不能走"，
    而"能不能走"的第一步是"有没有该语言的识别器"。设备那一步故意留在 listen 里 ——
    status 一旦去开麦克风，它就不再是只读读数了。
    """
    now = time.time()
    if _RECOG_CACHE["list"] is not None and (now - _RECOG_CACHE["at"]) < ttl:
        return _RECOG_CACHE["list"]
    exe = _ps_exe()
    if not exe:
        return []
    code = ("Add-Type -AssemblyName System.Speech;"
            "[System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()"
            "|ForEach-Object{$_.Culture.Name+'|'+$_.Id}")
    try:
        cp = subprocess.run([exe, "-NoProfile", "-Command", code],
                            capture_output=True, timeout=25,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        txt = (cp.stdout or b"").decode("utf-8", "replace")
        out = [x.strip() for x in txt.splitlines() if "|" in x]
    except Exception:  # noqa: BLE001
        out = []
    _RECOG_CACHE["list"] = out
    _RECOG_CACHE["at"] = now
    return out


def _wavein_count():
    """`waveInGetNumDevs()` —— 旧版 waveIn 映射器能看见几个**输入**设备。

    **这就是本机"设备直连"那条腿的死活判据**：映射器数 0 ⇒ `SetInputToDefaultAudioDevice()`
    永远抛 "Cannot find the requested data item"，与插不插麦克风无关。
    用它当 status 的一个字段，是为了**堵掉一个假绿**：光看"有没有中文识别器"会报
    `listen 离线可用`，而实际上**一个输入端点都没有** —— 识别器在、耳朵不在。
    """
    try:
        import ctypes
        return int(ctypes.WinDLL("winmm").waveInGetNumDevs())
    except Exception:  # noqa: BLE001
        return None


def _clip(s, n):
    """把长字符串截短（`None` 原样返回）。

    🔴 **这不是装饰，是必需**：`five-dim.py` 在结果 >1100 字时会把整个 `result`
    收窄成 `{"_摘要":…, "preview":…}`，而**收窄后顶层 `status` 就没了**；
    `intercom.py watch` 正是按顶层 `status` 判"安静 / 没有设备 / 没有识别器"的
    ⇒ 实测因此把「**没有可用录音设备**」念成「**安静（没听到，不是坏）**」（假绿）。
    根因是我给 `listen` 补的 `legs` 里带着**异常原文**（很长）。
    ⇒ 两条腿的原因只留够看的前 `n` 字，把结果压回收窄阈值以内。
    """
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= n else (s[:n] + "…")


def _last_json(raw):
    """从助手输出里取**最后一行** JSON（Python 侧唯一解析处，避免两处口径漂移）。"""
    for ln in reversed((raw or "").splitlines()):
        if ln.strip().startswith("{"):
            try:
                return json.loads(ln.strip())
            except Exception:  # noqa: BLE001
                return None
    return None


def _ps_run(args, to):
    """跑一次 asr-listen.ps1 并解析。**异常一律原样带出**，绝不吞成空结果。"""
    try:
        cp = subprocess.run(args, capture_output=True, timeout=to)
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "timeout", "exit": None,
                "error": "离线识别超时（%.0fs）：助手没在预期时间内返回" % to}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "error", "exit": None,
                "error": "起不来离线识别助手：%s" % str(e)[:160]}
    raw = (cp.stdout or b"").decode("utf-8", "replace").strip()
    out = _last_json(raw)
    if out is None:
        return {"ok": False, "status": "error", "exit": cp.returncode,
                "error": "助手没吐 JSON（exit=%s）" % cp.returncode,
                "stderr": (cp.stderr or b"").decode("utf-8", "replace")[:200]}
    out["exit"] = cp.returncode
    return out


def _record_loopback(seconds, to, out):
    """腿③：**系统播放回环**（WASAPI loopback，成熟件 PyAudioWPatch）。

    为什么要有它：本机 `waveInGetNumDevs()=0` 且三条 API 的默认输入全是 -1；
    WDM-KS 看得见引脚却 0 帧。而**扬声器**状态 OK ⇒ 回环能录"电脑在放什么"。
    边界：**录不到房间里的说话声**（那是麦克风），只证明耳朵链路通 + 做闭环演示。
    """
    rec = _LOCAL_LOOP
    if not rec.is_file():
        return {"ok": False, "status": "needs_dependency",
                "missing": "tools/codex-scripts/wasapi-loopback.py（回环件不在盘上）"}
    cands = []
    for c in (shutil.which("python"), shutil.which("python3"), sys.executable):
        if c and c not in cands:
            cands.append(c)
    if not cands:
        return {"ok": False, "status": "needs_dependency", "missing": "找不到可用的 python 解释器"}
    attempts = []
    for py in cands:
        cmd = [py, str(rec), "--seconds", str(float(seconds)), "--out", str(out), "--json"]
        try:
            cp = subprocess.run(cmd, capture_output=True, timeout=max(20.0, min(to, 120.0)),
                                cwd=str(rec.parents[2]))
        except Exception as e:  # noqa: BLE001
            attempts.append({"interpreter": py, "error": "起不来：%s" % str(e)[:120]})
            continue
        d = _last_json((cp.stdout or b"").decode("utf-8", "replace").strip())
        if d is None:
            attempts.append({"interpreter": py, "exit": cp.returncode,
                             "stderr": (cp.stderr or b"").decode("utf-8", "replace")[:160]})
            continue
        d["exit"] = cp.returncode
        d["interpreter"] = py
        d["attempts"] = attempts
        d["leg"] = "loopback"
        return d
    return {"ok": False, "status": "error", "attempts": attempts,
            "error": "回环件在 %d 个解释器下都没吐 JSON（逐条见 attempts）" % len(cands)}


def _record_wav(seconds, to, device=None):
    """腿①：用 PortAudio 录一段到临时 WAV（绕开旧版 winmm 映射器）。

    PortAudio 的四个主机 API（MME/DirectSound/WASAPI/WDM-KS）能看见的端点
    **严格多于** winmm ⇒ 优先试它。本机现读没有在场端点时会如实报 `no_input`。

    🔴 2026-10-18 加 `device`：本机 `waveInGetNumDevs()=0` 且
    MME/DirectSound/WASAPI 的 `default_input` **全是 -1**
    ⇒ 只会开"默认设备"的话永远 `no_input`。而 WDM-KS 明明看得见
    `麦克风 #9` / `立体声混音 #10`。给个设备号就能直连——这是**根因修法**，
    不是绕门（仍然是 `voice` 这个能力位、仍然要 privacy_read 票）。
    """
    rec = _LOCAL_REC
    if not rec.is_file():
        return {"ok": False, "status": "needs_dependency",
                "missing": "tools/codex-scripts/wasapi-record.py（录音件不在盘上）"}
    out = Path(tempfile.gettempdir()) / ("gbt_ear_%d.wav" % int(time.time() * 1000))

    # 🔴 2026-10-18「缺啥就抓取成熟能力补齐」：**系统播放回环**这一条腿。
    #    本机采集引脚全没被路由（两条腿都 0 帧），但扬声器状态 OK ⇒
    #    用 WASAPI loopback（成熟件 PyAudioWPatch，装在 3.12）录**电脑正在放的声音**。
    #    它录不到房间里的说话声（那是麦克风的事），但能证明"耳朵链路通"，
    #    也能做"她说什么 → 回环抓回 → 再识别"的闭环演示。
    if str(device or "").lower() in ("loopback", "desktop", "system", "扬声器回环"):
        return _record_loopback(seconds, to, out)
    # 解释器候选：先试本机 `python`（**已实测带 sounddevice**），再退回框架自己的解释器。
    # 为什么要点名逐个试：本仓声明口径是 **3.14**，而 sounddevice/pyaudio 现装在 **3.12**
    # ⇒ 用错解释器会**静默**变成"录音件起不来"，看起来像设备坏了。试过的每个都留在 attempts 里。
    cands = []
    for c in (shutil.which("python"), shutil.which("python3"), sys.executable):
        if c and c not in cands:
            cands.append(c)
    if not cands:
        return {"ok": False, "status": "needs_dependency", "missing": "找不到可用的 python 解释器"}
    attempts = []
    dev_arg = None
    if device not in (None, "", "auto", "default"):
        try:
            dev_arg = str(int(device))
        except Exception:  # noqa: BLE001
            return {"ok": False, "status": "bad_device",
                    "error": "device 必须是整数索引（现读拿到的是 %r）" % (device,)}
    for py in cands:
        cmd = [py, str(rec), "--seconds", str(float(seconds)), "--out", str(out), "--json"]
        if dev_arg is not None:
            cmd += ["--device", dev_arg]
        try:
            cp = subprocess.run(cmd, capture_output=True, timeout=max(20.0, min(to, 120.0)),
                                cwd=str(rec.parents[2]))
        except Exception as e:  # noqa: BLE001
            attempts.append({"interpreter": py, "error": "起不来：%s" % str(e)[:120]})
            continue
        d = _last_json((cp.stdout or b"").decode("utf-8", "replace").strip())
        if d is None:
            attempts.append({"interpreter": py, "exit": cp.returncode,
                             "stderr": (cp.stderr or b"").decode("utf-8", "replace")[:160]})
            continue
        d["exit"] = cp.returncode
        d["interpreter"] = py
        # 🔴 2026-10-18 修 **读数是假话**：原来这一行直接 `d["attempts"] = attempts`，
        #    把录音件**自己**的 attempts（设备级逐条原因）覆盖成解释器级的（通常是空数组）
        #    ⇒ 回执写着「逐条原因见 attempts」，而 attempts = []（实测踩到）。
        #    口径：两个都留，名字分开：attempts=解释器级（外层契约不变），
        #          device_attempts=录音件报的**设备级**原因。
        d["device_attempts"] = d.get("attempts") or []
        d["attempts"] = attempts
        return d
    return {"ok": False, "status": "error", "attempts": attempts,
            "error": "录音件在 %d 个解释器下都没吐 JSON（逐条见 attempts）" % len(cands)}


def _normalize_wav_16k(src):
    """把待识别 WAV 归一成 **16 kHz / 16-bit / 单声道** —— 识别器的活门槛。

    🔴 2026-10-18 实测（主人令「可以」后做的降质点）：同一条素材
       24 kHz 直喂 → confidence **0.252**，转 16 kHz 后 → **0.311**（+24%），
       文本也更贴原话（"唤醒我世纪里的小土豆…" → "系统唤醒我实际笔直小土豆…"）。
    ⇒ 不是玄学：`asr-listen.ps1` 走 `SetInputToWaveFile`，桌面识别器吃 16k。
    本函数只**归一**，不改内容；ffmpeg 不在就如实报「未归一」，不假装做了。
    """
    import wave

    src = Path(src)
    info = {"input": src.name, "changed": False, "path": str(src), "why": None}
    try:
        with wave.open(str(src), "rb") as w:
            ch, rate, width = w.getnchannels(), w.getframerate(), w.getsampwidth()
        info.update({"in_ch": ch, "in_rate": rate, "in_width": width})
    except Exception as e:  # noqa: BLE001
        info["why"] = "读不了 wav 头（%s）⇒ 原样送识别" % type(e).__name__
        return info

    if ch == 1 and rate == 16000 and width == 2:
        info["why"] = "本来就是 16k/16-bit/单声道，无需归一"
        return info

    ff = shutil.which("ffmpeg")
    if not ff:
        info["why"] = "ffmpeg 不在 PATH ⇒ 未归一（可能拖低识别率）"
        return info

    out_dir = Path(tempfile.mkdtemp(prefix="gbt-asr16k-"))
    dst = out_dir / "norm16k.wav"
    try:
        # 不用管道接子进程输出（本沙箱会挡）；直接丢弃，判据只看产物在不在。
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(src),
                        "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(dst)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    except Exception as e:  # noqa: BLE001
        shutil.rmtree(out_dir, ignore_errors=True)
        info["why"] = "ffmpeg 转码失败（%s）⇒ 原样送识别" % type(e).__name__
        return info

    if not dst.is_file() or dst.stat().st_size < 1024:
        shutil.rmtree(out_dir, ignore_errors=True)
        info["why"] = "ffmpeg 没产出有效 wav ⇒ 原样送识别"
        return info

    info.update({"changed": True, "path": str(dst), "tmpdir": str(out_dir),
                 "why": "%d Hz/%dch → 16000 Hz/1ch" % (rate, ch)})
    return info


def asr_local(seconds=6.0, culture="zh-CN", min_confidence=0.0, timeout=None, wav=None,
              device=None):
    """本机离线听觉（Windows 桌面识别器）——**零密钥、零安装**。

    为什么要有它：`asr` 原来只认云端端点，没配密钥就 `needs_dependency`
    ⇒「没密钥就听不见」。而主人要的「打开页面自动监听」恰恰是**不许要密钥**的那条路。

    两条输入腿（见文件头第 59 轮那段）：先试 `wav`/录音件 → WAV → 识别器（腿①），
    不通再退回设备直连（腿②）。**两条腿各自的原因都留在 `legs` 里，绝不吞掉。**
    `wav=` 给了就用它，不再录音（便于离线复验与喂现成素材）。

    返回契约（**"安静"与"坏了"必须分开报**，这是本仓最贵的教训之一）：
      ok=True,  heard=True   → text/confidence 是真识别结果
      ok=True,  heard=False  → 跑完了但这段没听到（reason 写清是安静还是置信度不够）
      ok=False               → 后端不可用（缺 .NET / 缺该语言识别器 / **没有在场录音端点**）

    🔴 绝不伪造：任何异常原样带出，绝不拿空字符串冒充"识别成功"。
    """
    ps = _LOCAL_ASR_PS
    if not ps.is_file():
        return {"ok": False, "status": "needs_dependency",
                "missing": "tools/codex-scripts/asr-listen.ps1（离线识别助手不在盘上）"}
    exe = _ps_exe()
    if not exe:
        return {"ok": False, "status": "needs_dependency", "missing": "pwsh / powershell 都不在 PATH"}
    to = float(timeout) if timeout is not None else float(seconds) + 25.0

    def args_for(w):
        a = [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps),
             "-Seconds", str(float(seconds)), "-Culture", str(culture),
             "-MinConfidence", str(float(min_confidence))]
        if w:
            a += ["-WavFile", str(w)]
        return a

    legs = []
    target = wav
    tmp = None
    if not target:                                    # 腿① 先录音（PortAudio 看得更多）
        rec = _record_wav(seconds, to, device)
        legs.append({"leg": rec.get("leg") or "wasapi-record", "ok": bool(rec.get("ok")),
                     "status": rec.get("status"),
                     "reason": _clip(rec.get("reason") or rec.get("error") or rec.get("missing"), 140),
                     "device": _clip(rec.get("device"), 60), "api": rec.get("api"),
                     "peak": rec.get("peak"), "rms": rec.get("rms"),
                     "interpreter": rec.get("interpreter"),
                     "attempts": [{"interpreter": a.get("interpreter"),
                                   "exit": a.get("exit"),
                                   "err": _clip(a.get("error") or a.get("stderr"), 90)}
                                  for a in (rec.get("attempts") or [])],
                     # 设备级逐条原因（录音件自己报的；别被解释器级覆盖，见 _record_wav）
                     "device_attempts": rec.get("device_attempts") or []})
        if rec.get("ok") and rec.get("wav"):
            target = rec["wav"]
            tmp = target

    out = None
    norm = None
    if target:
        # 🔴 先归一成 16k/单声道/16bit 再送识别（实测 +24% 置信度，见 _normalize_wav_16k）
        norm = _normalize_wav_16k(target)
        legs.append({"leg": "normalize-16k", "ok": True,
                     "status": "changed" if norm.get("changed") else "as-is",
                     "reason": _clip(norm.get("why"), 120)})
        out = _ps_run(args_for(norm.get("path") or target), to)
        legs.append({"leg": "asr-wav", "ok": bool(out.get("ok")), "status": out.get("status"),
                     "exit": out.get("exit"),
                     "reason": _clip(out.get("reason") or out.get("error"), 140)})
    if out is None or not out.get("ok"):              # 腿② 兜底：设备直连
        dev = _ps_run(args_for(None), to)
        legs.append({"leg": "asr-device", "ok": bool(dev.get("ok")), "status": dev.get("status"),
                     "exit": dev.get("exit"),
                     "reason": _clip(dev.get("reason") or dev.get("error"), 140)})
        if out is None or dev.get("ok"):
            out = dev
    if out is None:
        out = {"ok": False, "status": "no_input", "reason": "两条输入腿都没跑起来"}

    removed = None
    if tmp:
        try:
            Path(tmp).unlink()
            removed = True
        except Exception:  # noqa: BLE001
            removed = False
    out["backend"] = "win-speech"
    out["legs"] = legs
    out["source"] = out.get("source") or ("wav" if target else "device")
    if tmp:
        out["temp_wav_removed"] = removed
    # 归一化读数如实带出（改了没有、源是什么规格、为什么没改）
    if norm is not None:
        out["normalized"] = {k: norm.get(k) for k in ("changed", "why", "in_rate", "in_ch")}
        if norm.get("tmpdir"):
            shutil.rmtree(norm["tmpdir"], ignore_errors=True)
    # 2026-10-16 主人令：盲区必须看得见，且文案不许与实现漂移。
    # 改为**运行时现读 policy**（同步由构造保证，不靠人手改文案）。
    # 🔴 2026-10-18 修：`policy.evaluate()` 返回的是 **dataclass `PolicyDecision`**，
    #    而这里原来只 `isinstance(_dec, dict)` ⇒ 永远 False ⇒ 字段恒为「未读到」。
    #    实测证据：`op=listen` 明明被 privacy_read 拦住（denied 原文可查），
    #    同一返回里的 `gate_blind_spot` 却写「作用域 未读到」—— 自相矛盾。
    _sc = _gate_scopes("listen")
    if _sc is not None:
        out["gate_blind_spot"] = ("现读 policy：op=listen → 必备作用域 %s（与实现同步，非静态断言）"
                                  % (list(_sc) or "无（门不拦）"))
    else:
        out["gate_blind_spot"] = "现读 policy 失败 ⇒ 如实写未读到"
    return out


def _gate_scopes(op):
    """现读 policy：这个 op 要哪些作用域。**读不到返回 None**（不返回空表冒充"无门"）。"""
    try:
        from .security import policy as _pol
    except Exception:  # noqa: BLE001
        return None
    fn = getattr(_pol, "evaluate", None)
    if not callable(fn):
        return None
    try:
        dec = fn("voice", {"op": str(op)})
    except Exception:  # noqa: BLE001
        return None
    if isinstance(dec, dict):
        got = dec.get("required") or dec.get("scopes") or dec.get("missing_scopes") or []
    else:
        got = getattr(dec, "scopes", ()) or ()
    try:
        return [str(x) for x in got]
    except Exception:  # noqa: BLE001
        return None


def _io_boundary(boundary, path):
    import io
    fields = {"model": os.environ.get("GBT_ASR_MODEL", "whisper-1"),
              "file": (path.name, path.read_bytes(), "audio/wav")}
    buf = io.BytesIO()
    for k, v in fields.items():
        if isinstance(v, tuple):
            buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{v[0]}\"\r\nContent-Type: {v[2]}\r\n\r\n".encode())
            buf.write(v[1])
        else:
            buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    buf.write(f"--{boundary}--\r\n".encode())
    return buf.getvalue()


# 每个 op **认**哪些参数。用途只有一个：**把"传了但没被用"的参数如实报出来**。
# 为什么必须有一张表（2026-09-25 实测踩到）：
#   调度层（`api.py` 的 voice 分支）当年是手写白名单转发，白名单外的参数**静默丢**；
#   而这层的 `params.get(...)` 是**第二次静默丢** —— 两层都不报错。
#   实测：传 `path=<wav路径>` 期望落盘，读数却是 `{"ok":true,"spoken":true}`（直接发声、零文件）。
#   ⇒ 修法不是"多加几个名字"（第 59 轮就是这么补的，同类病照样复发），而是**认不出就报**。
_ACCEPTED_PARAMS = {
    "tts": {"text", "voice", "rate", "out", "backend", "engine",
            "edge_rate", "pitch", "volume"},
    "asr": {"audio"},
    "listen": {"seconds", "culture", "min_confidence", "timeout", "wav", "device"},
    "status": set(),
}


def _dispatch(op, params):
    if op in ("tts", "speak", None):
        return tts(params.get("text"), params.get("voice"),
                   int(params.get("rate", 0)), params.get("out"),
                   params.get("backend"), params.get("engine"),
                   params.get("edge_rate", "+0%"), params.get("pitch", "+0Hz"),
                   params.get("volume", "+0%"),
                   # 2026-10-19：显式 play（不给就沿用"有 out 不出声"的老口径）
                   params.get("play"))
    if op == "asr":
        return asr(params.get("audio"))
    if op == "listen":
        return asr_local(params.get("seconds", 6.0),
                         params.get("culture", "zh-CN"),
                         params.get("min_confidence", 0.0),
                         params.get("timeout"),
                         params.get("wav"),
                         # 🔴 2026-10-18：设备号必须能传进来。本机 default_input 全是 -1，
                         #    不给 device 就只能开"默认设备"⇒ 永远 no_input（实测）。
                         params.get("device"))
    if op == "status":
        base = os.environ.get("GBT_ASR_BASE_URL", "")
        key = os.environ.get("GBT_ASR_API_KEY", "")
        recs = recognizers()
        zh = [r for r in recs if r.startswith("zh")]
        w = _wavein_count()
        _vs_up, _vs_ver = _vs_health(timeout=0.8)
        return {"ok": True,
                "tts": "edge-tts（神经语音 · 默认台湾腔）+ win-sapi（回退）",
                # 🔴 2026-10-04：VoiceStudio 本地克隆引擎（127.0.0.1:3900）——
                #    只读探测（0.8s 超时）。点名 `backend="voicestudio"` 才走它。
                "voicestudio": (("up（v%s · 本地克隆 646 语言）" % _vs_ver) if _vs_up
                                else "down（未起 · py -3.14 tools/codex-scripts/voicestudio.py up）"),
                "asr": "configured" if (base and key) else "needs_dependency",
                "listen": ("win-speech（离线可用）" if zh else "needs_dependency"),
                "recognizers": recs,
                "recognizers_zh": zh,
                # 🔴 第 59 轮补：**光看识别器会报假绿**。识别器在位 ≠ 耳朵能听 ——
                #    本机实测有 zh 识别器，而输入端点**在场的 0 个** ⇒ listen 必报 no_input。
                "listen_recognizer": ("win-speech（识别器在位）" if zh else "needs_dependency"),
                "wavein_devices": w,
                "listen_input": ("wavein 可见 %d 个输入设备" % w) if w is not None else "取不到",
                "listen_note": ("wavein_devices = 0 ⇒ 设备直连那条腿**在本机是死的**"
                                "（与插不插麦克风无关）；只听 wasapi-record 那条腿。"
                                "两条腿都写在 listen 返回的 legs 里。"),
                "note": ("listen = 本机离线识别（零密钥，两条输入腿）；asr = 云端端点（需 GBT_ASR_*）；"
                         "listen 是否要挂 privacy_read 由主人的 policy.py 决定")}
    raise ValueError(f"未知 op: {op}（可用: tts/asr/listen/status）")


def run(op="tts", **params):
    """voice 统一入口：tts（SAPI，默认）/ asr（云端）/ **listen（本机离线）** / status。

    `listen` 是 2026-09-23 为「打开页面就自动监听」加的那条腿：
    它不需要任何密钥，也不需要主人发授权（门现读不给它挂作用域 —— 见文件头那条盲区说明）。

    🔴 本函数**只加字段、不改任何既有字段**：有认不出的参数时，返回值里多一个
    `ignored_params`（+ 一句 `ignored_note`）；参数都认得时，返回体与改动前**逐字节相同**。
    """
    op_n = "tts" if op in ("tts", "speak", None) else op
    accepted = _ACCEPTED_PARAMS.get(op_n)
    extra = sorted(k for k in params if k not in accepted) if accepted is not None else []
    res = _dispatch(op, params)
    if extra and isinstance(res, dict):
        res = dict(res)
        res["ignored_params"] = extra
        res["ignored_note"] = ("这些参数本 op 不认，**已原样丢弃、未参与执行**；"
                               "本 op 认的参数是 %s —— 别把 `ok:true` 读成『你要的效果达成了』"
                               % (sorted(accepted) or "无"))
    return res
