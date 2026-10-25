# -*- coding: utf-8 -*-
# gbt-capability: audio-extract
"""从视频里把声音取出来（native 能力位 `audio_extract`）。

## 出处（Owner 2026-09-23 指定要"学会并固化为原生能力"）

1. `https://online-audio-converter.com/blog/how-to-extract-sound-from-video`
   —— 那篇是**在线工具的走查**（打开文件 → 选格式 → 转换 → 下载），**没有技术方法**。
   它能给的两条真东西是：① **默认就给 mp3 / 标准质量**（拿不准时的稳妥选择）；
   ② 它自己也是**在服务器上跑 ffmpeg 一类的东西**再把文件给你 —— 也就是说这件事**本机就能干**，
   不必经过别人的服务器（**本能力位因此零出网**）。
2. `https://online-audio-converter.com/blog/audio-formats`（Owner 的链接片段正指向它）
   —— **格式知识**：容器 vs 编解码器不是一回事（容器是盒子，codec 是装法）；
   有损（MP3/WMA/OGG/AAC）与无损（FLAC/APE/ALAC）两族；WAV 基本是未压缩 PCM（约 10 MB/分钟）；
   AAC 同体积下质量更好，扩展名可以是 `.aac/.mp4/.m4a/.m4b/.m4p/.m4r`；FLAC 与原音一致但播放器支持窄。
   ⇒ 这些**不是抄进注释就算学会**，而是落成 `FORMATS` 表，可查、可测（见 `formats` op 与单测）。

## 红线（照 `edit_core` 的先例，同一套纪律）

1. 🔴 **`policy.evaluate()` 对未登记 kind 返回零作用域**（本仓既有现象），而 `policy.py`
   是**主人的门，我一个字都不许改** ⇒ **本能力位自己把写面钉死**：
   只读 op 随便调；写 op 只准落在 `projects/` · `outputs/` · `.scratch/` 之下，
   别处的绝对路径**当场拒绝并说明为什么**（不是静默改写）。这条自收窄**有判据**。
2. **零出网**：只用本机 ffmpeg。谁的服务器都不经过。
3. **不吞坏因**：ffmpeg/ffprobe 失败要把 stderr 尾部如实带出来（本仓的老规矩）。
4. **产出即验证**：extract 落盘后**用 ffprobe 回读产物**（codec / 采样率 / 声道 / 时长 / 字节），
   复核读数与产物一起返回 —— 不拿"命令返回 0"当"文件好了"。
5. **不许编**：没有 ffmpeg 就如实报 `needs_dependency`；源文件没有音轨就如实说没有。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_IMPL_VERSION = "1.0"

READ_OPS = ("status", "formats", "probe", "tracks")
WRITE_OPS = ("extract",)
WRITE_ROOTS = ("projects", "outputs", ".scratch")

# ── 格式知识表（第 2 篇文章的要点，逐条落成数据；`formats` op 就是把它读出来）──
# 键 = 容器/扩展名；codec = ffmpeg 侧的编码器名；kind = 有损 / 无损 / 未压缩
FORMATS = {
    "mp3": {"codec": "libmp3lame", "kind": "有损", "ext": ".mp3", "default_bitrate": "192k",
            "why": "世界上最通用的格式，几乎什么设备都认 ⇒ **拿不准就用它**（默认）",
            "note": "体积/质量已不是最优，但兼容性最好"},
    "aac": {"codec": "aac", "kind": "有损", "ext": ".m4a", "default_bitrate": "192k",
            "why": "同体积下质量通常优于 MP3；通道数与采样率上限也更高",
            "note": "扩展名可以是一族：.aac/.mp4/.m4a/.m4b/.m4p/.m4r（容器与 codec 不是一回事）"},
    "m4a": {"codec": "aac", "kind": "有损", "ext": ".m4a", "default_bitrate": "192k",
            "why": "AAC 装进 MP4 容器 —— 苹果生态常用", "note": "同 aac"},
    "wav": {"codec": "pcm_s16le", "kind": "未压缩", "ext": ".wav", "default_bitrate": None,
            "why": "要**无损且立刻能用**（继续剪、送进别的工具）时选它",
            "note": "约 10 MB/分钟；不压缩，改它不会再掉质量"},
    "flac": {"codec": "flac", "kind": "无损", "ext": ".flac", "default_bitrate": None,
             "why": "要**存档**、且不想占 WAV 那么大时选它",
             "note": "解码后与原音逐位一致；但部分播放器/设备不认"},
    "ogg": {"codec": "libvorbis", "kind": "有损", "ext": ".ogg", "default_bitrate": "160k",
            "why": "开放格式，质量与 MP3 同档", "note": "设备支持面比 MP3 窄"},
    # 🔴 opus 的默认码率**故意低一档**（实测教训）：Opus 是为低码率设计的编解码器，
    #    给它 192k 会白占体积 —— 本机实测同一条 6.35 s 音轨：aac@192k = 73 KB，
    #    而 opus@192k = 175 KB（比 aac 大一倍多，**完全违背选它的理由**）。
    "opus": {"codec": "libopus", "kind": "有损", "ext": ".opus", "default_bitrate": "96k",
             "why": "语音/低码率场景更省（同听感下体积最小）",
             "note": "比 MP3 新，老设备可能不认；**别给它高码率**，那是浪费"},
    "wma": {"codec": "wmav2", "kind": "有损", "ext": ".wma", "default_bitrate": "192k",
            "why": "只在必须喂给老 Windows 场景时用", "note": "Microsoft 所有，支持 DRM"},
}

BITRATES = ("96k", "128k", "160k", "192k", "256k", "320k")
DEFAULT_FORMAT = "mp3"          # 照那篇文章的建议：mp3 + 标准质量
DEFAULT_BITRATE = "192k"

# 容器（ffmpeg 的 `-f`）—— **不是** codec 名，别混。
# 🔴 `opus` 是**编解码器**不是容器：`.opus` 文件实际装在 Ogg 里 ⇒ 必须写 `-f ogg`。
#    第一版我按格式名去猜 `-f opus`，那是**跑不通的**（ffmpeg 没有叫 opus 的 muxer）。
#    ⇒ 显式表：一眼能看出"格式名 → 容器名"这层映射，也免得下次又猜。
MUXERS = {"mp3": "mp3", "aac": "ipod", "m4a": "ipod", "wav": "wav",
          "flac": "flac", "ogg": "ogg", "opus": "ogg", "wma": "asf"}


def _have(tool: str) -> bool:
    return shutil.which(tool) is not None


def _run(cmd: list, timeout: int = 600) -> tuple:
    """跑外部命令。**编码一律 utf-8 + errors=replace**（Windows 默认 cp936 会把中文输出弄乱）。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return p.returncode, p.stdout or "", p.stderr or ""
    except FileNotFoundError as e:
        return 127, "", "找不到可执行文件：%s" % e
    except subprocess.TimeoutExpired:
        return 124, "", "超时（%ss）：%s" % (timeout, " ".join(cmd[:3]))


def _tail(s: str, n: int = 400) -> str:
    s = (s or "").strip().replace("\r", "")
    return s[-n:] if len(s) > n else s


def write_guard(path, root=None) -> dict:
    """写面自收窄：只准往 `projects/` · `outputs/` · `.scratch/` 之下写。

    `root` 可传（**给测试用**）：生产恒为仓库根，测试传临时目录，
    这样同一条判据在两种场景下都真被执行，而不是测试里绕过它。
    """
    root = Path(root or _ROOT).resolve()
    p = Path(path)
    ap = (root / p).resolve() if not p.is_absolute() else p.resolve()
    try:
        rel = ap.relative_to(root)
    except ValueError:
        return {"ok": False, "why": "落点 **%s** 在仓库之外 —— 本能力位只写仓内 %s"
                                    % (ap, "、".join(WRITE_ROOTS))}
    if rel.parts and rel.parts[0] not in WRITE_ROOTS:
        return {"ok": False, "why": "落点 **%s** 不在允许的写面内（只认 %s 之下）"
                                    % (rel.as_posix(), "、".join(WRITE_ROOTS))}
    return {"ok": True, "abs": str(ap), "rel": rel.as_posix()}


def probe(src) -> dict:
    """读源文件有什么：全部流 + 音轨清单。只读。"""
    if not _have("ffprobe"):
        return {"ok": False, "status": "needs_dependency", "missing": "ffprobe",
                "why": "本机没有 ffprobe ⇒ 读不了流信息（不假装能读）"}
    sp = Path(src)
    if not sp.is_file():
        return {"ok": False, "error": "源不是文件：%s" % src}
    rc, out, err = _run(["ffprobe", "-v", "error", "-print_format", "json",
                         "-show_format", "-show_streams", str(sp)], 120)
    if rc != 0:
        return {"ok": False, "error": "ffprobe 读不动这个文件", "rc": rc, "stderr_tail": _tail(err)}
    try:
        d = json.loads(out or "{}")
    except ValueError:
        return {"ok": False, "error": "ffprobe 输出不是 JSON", "stdout_tail": _tail(out)}
    streams = []
    for s in d.get("streams", []):
        streams.append({"index": s.get("index"), "type": s.get("codec_type"),
                        "codec": s.get("codec_name"), "channels": s.get("channels"),
                        "sample_rate": s.get("sample_rate"),
                        "bit_rate": s.get("bit_rate"),
                        "language": (s.get("tags") or {}).get("language"),
                        "duration": s.get("duration")})
    fmt = d.get("format") or {}
    audio = [s for s in streams if s["type"] == "audio"]
    return {"ok": True, "src": sp.name, "bytes": sp.stat().st_size,
            "duration_s": fmt.get("duration"), "format_name": fmt.get("format_name"),
            "streams": streams, "audio_count": len(audio), "audio": audio,
            "video_count": len([s for s in streams if s["type"] == "video"]),
            "has_audio": bool(audio)}


def _build_args(src: str, out: str, fmt: str, bitrate: str, track: int,
                start, end, volume, normalize) -> list:
    """纯函数：拼 ffmpeg 参数（**单独可测**，不用真跑 ffmpeg）。"""
    f = FORMATS.get(fmt) or FORMATS[DEFAULT_FORMAT]
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(src)]
    if end is not None:
        cmd += ["-to", str(end)]
    cmd += ["-vn", "-map", "0:a:%d" % int(track)]          # -vn：不要视频
    filters = []
    if volume is not None:
        filters.append("volume=%s" % volume)
    if normalize:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")     # 广播级响度目标
    if filters:
        cmd += ["-filter:a", ",".join(filters)]
    cmd += ["-c:a", f["codec"]]
    if f["kind"] != "未压缩" and f["codec"] not in ("flac",):
        cmd += ["-b:a", bitrate]
    cmd += ["-f", MUXERS.get(fmt, "mp3")]
    cmd += [str(out)]
    return cmd


def _verify(path: Path) -> dict:
    """产出即验证：回读产物，把真读数带回来。"""
    if not _have("ffprobe") or not path.is_file():
        return {"ok": False, "why": "产物不在或没有 ffprobe"}
    rc, out, err = _run(["ffprobe", "-v", "error", "-print_format", "json",
                         "-show_format", "-show_streams", str(path)], 120)
    if rc != 0:
        return {"ok": False, "why": "回读失败", "stderr_tail": _tail(err)}
    try:
        d = json.loads(out or "{}")
    except ValueError:
        return {"ok": False, "why": "回读输出不是 JSON"}
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {})
    fmt = d.get("format") or {}
    return {"ok": True, "codec": a.get("codec_name"), "channels": a.get("channels"),
            "sample_rate": a.get("sample_rate"), "duration_s": fmt.get("duration"),
            "bytes": path.stat().st_size}


def run(op: str = "status", **kw) -> dict:
    """万能插入口：`run_task("audio_extract", {"op": ..., ...})` 落到这里。"""
    op = str(op or "status")

    if op == "status":
        return {"ok": True, "impl": "audio_extract", "version": _IMPL_VERSION,
                "kind": "audio_extract", "domain": "video",
                "read_ops": list(READ_OPS), "write_ops": list(WRITE_OPS),
                "write_roots": list(WRITE_ROOTS),
                "ffmpeg": _have("ffmpeg"), "ffprobe": _have("ffprobe"),
                "default_format": DEFAULT_FORMAT, "default_bitrate": DEFAULT_BITRATE,
                "formats": sorted(FORMATS),
                "learned_from": [
                    "online-audio-converter.com/blog/how-to-extract-sound-from-video"
                    "（走查页：默认 mp3/标准质量；且它也是服务端转 —— 本机 ffmpeg 即可，故零出网）",
                    "online-audio-converter.com/blog/audio-formats"
                    "（格式 vs 编解码器 / 有损与无损两族 / 各格式取舍 —— 已落成 FORMATS 表）",
                ],
                "note": "**自收窄**：policy 对未登记 kind 零作用域，故本能力位自己钉死写面"
                        "（只写 projects/ · outputs/ · .scratch/）。零出网，只用本机 ffmpeg。"}

    if op == "formats":
        return {"ok": True, "default": {"format": DEFAULT_FORMAT, "bitrate": DEFAULT_BITRATE,
                                        "why": "拿不准就用它（兼容性最好）"},
                "bitrates": list(BITRATES), "formats": FORMATS,
                "two_things_not_one": "**容器 ≠ 编解码器**：容器是盒子，codec 是装法。"
                                      "所以 `.mp4` 里的声音可能是 AAC，`.m4a` 其实就是 AAC 装进 MP4。"}

    if op in ("probe", "tracks"):
        src = kw.get("src") or kw.get("path") or kw.get("video")
        if not src:
            return {"ok": False, "error": "op=%s 需要 src（视频/音频文件路径）" % op}
        r = probe(src)
        if r.get("ok") and op == "tracks":
            return {"ok": True, "src": r["src"], "audio_count": r["audio_count"],
                    "tracks": r["audio"], "duration_s": r["duration_s"],
                    "note": "提取时用 track=N 选第几条（默认 0）"}
        return r

    if op == "extract":
        src = kw.get("src") or kw.get("path") or kw.get("video")
        out = kw.get("out") or kw.get("dst")
        fmt = str(kw.get("format") or DEFAULT_FORMAT).lower().lstrip(".")
        if fmt not in FORMATS:
            return {"ok": False, "error": "不认的格式 %r（认这些：%s）"
                                         % (fmt, "、".join(sorted(FORMATS)))}
        if not src:
            return {"ok": False, "error": "op=extract 需要 src"}
        if not _have("ffmpeg"):
            return {"ok": False, "status": "needs_dependency", "missing": "ffmpeg",
                    "why": "本机没有 ffmpeg ⇒ 提不了（不假装能提）"}
        info = probe(src)
        if not info.get("ok"):
            return info
        if not info.get("has_audio"):
            return {"ok": False, "error": "这条视频**没有音轨** —— 没声音可取",
                    "src": info.get("src"), "streams": info.get("streams")}
        track = int(kw.get("track") or 0)
        if track >= info["audio_count"]:
            return {"ok": False, "error": "track=%d 越界（这条只有 %d 条音轨）"
                                          % (track, info["audio_count"])}
        sp = Path(src)
        if not out:
            out = "outputs/audio/%s.%s" % (sp.stem, FORMATS[fmt]["ext"].lstrip("."))
        g = write_guard(out, kw.get("root"))
        if not g.get("ok"):
            return {"ok": False, "error": g["why"], "refused": True}
        dst = Path(g["abs"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        # 码率：调用方没说就用**该格式自己的**默认值（不是一律 192k —— 见 FORMATS["opus"] 那条实测）
        br = str(kw.get("bitrate") or FORMATS[fmt].get("default_bitrate") or DEFAULT_BITRATE)
        cmd = _build_args(str(sp), str(dst), fmt, br,
                          track, kw.get("start"), kw.get("end"),
                          kw.get("volume"), kw.get("normalize"))
        rc, _o, err = _run(cmd, int(kw.get("timeout") or 900))
        if rc != 0:
            return {"ok": False, "error": "ffmpeg 失败（rc=%d）" % rc,
                    "stderr_tail": _tail(err), "cmd_head": " ".join(cmd[:6])}
        v = _verify(dst)
        return {"ok": bool(v.get("ok")), "out": g["rel"], "format": fmt,
                "source_audio": {"codec": (info["audio"][track] or {}).get("codec"),
                                 "sample_rate": (info["audio"][track] or {}).get("sample_rate"),
                                 "channels": (info["audio"][track] or {}).get("channels")},
                "product": v, "verified": bool(v.get("ok")),
                "note": "**产出即验证**：上面 product 是 ffprobe 回读产物得到的真读数，"
                        "不是「命令返回 0」。"}

    return {"ok": False, "error": "不认的 op：%s（读 %s / 写 %s）"
                                 % (op, "/".join(READ_OPS), "/".join(WRITE_OPS))}
