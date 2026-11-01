# gbt-capability: viral_forge
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""viral_forge — 爆款拆解 + 克隆配方（原生位 · 2026-11-01，吸收 hypit 架构思想）。

## 它是什么 / 不是什么
输入**你自己有权使用的字幕/逐句稿**（SRT / VTT / 逐句列表），输出：
  1) 爆款拆解 `reading`：时长、语速、黄金 3 秒钩子、钩子类型、每 5 秒节奏、段落角色、CTA；
  2) 克隆配方 `recipe`：**词锚**（不是秒锚）的场景表 + 变体槽位，可直接喂本仓 `edit_pipeline`
     或人工二创（换人/换产品/换语言/换 B-roll，结构不动）；
  3) 变体钩子 `variants`：按 brief 生成 N 条**模板钩子**（纯模板，不调模型）。

**是**：结构分析器 + 可编辑配方生成器；零依赖、可复现。
**不是**：不下载/不缓存原视频；不复制原画面/原音频；不自动发布；不冒充 AI 生成。
真正的"克隆"= **结构复刻**，素材与内容必须是你自己的或已获授权（红线写进 guardrails）。

## 吸收来源
`hypit-ai/hypit`（27,145★ · TypeScript · "Clone any viral video with AI agents"）的
**SVML/词锚工作流 + 组件化 + 一变多**架构思想（只吸收设计，未复制其代码；许可为
Hypit Open Source License，见 `整理报告/吞噬记录-hypit.md`）。

## 契约
op（默认 status）：
  · `status`   只读：能力/输入/边界
  · `teardown` 字幕 → 拆解读数 + 配方（最少输入：`text` 或 `cues`）
  · `blueprint` 同上，但主要交付 recipe + variants（brief 越全，钩子越具体）
  · `where`    只读：入口与调用例
payload：
  · `text`: SRT/VTT 全文；或 `cues`: [{start,end,text}]（秒）
  · `duration`: 秒（不给则取最后一句结束时间）
  · `brief`: {product,audience,pain,promise,topic}（变体钩子用）
  · `variants`: 变体条数（默认 3，上限 20）
  · `video`: 可选本地路径——仅用 ffprobe 读时长（读不到就如实说，不猜）
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

STATUS = {
    "cap": "viral_forge", "tier": "native",
    "ops": ["status", "teardown", "blueprint", "analyze", "frames", "pipeline", "inbox", "batch", "where"],
    "inputs": ["text(SRT/VTT)", "cues[{start,end,text}]", "video(path, 需 ffmpeg/ffprobe)", "optional brief"],
    "outputs": ["reading", "recipe(viral_clone_v1)", "variants"],
    "not_implemented": ["视频画面/音频下载", "AI 生成素材", "自动发布", "原片内容复刻"],
    "guardrails": ["只用自有或已授权素材", "不复制原视频画面/音频", "不自动发布",
                   "模型调用需主人授权", "结构复刻 ≠ 内容抄袭"],
}

_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?[.,](\d{1,3})")
_CTA = ("关注", "点赞", "评论", "购买", "下单", "链接", "私信", "订阅", "左下角", "购物车", "收藏")
_HOOK_COMMAND = ("千万别", "一定要", "别再", "记住", "听我", "看完")
_HOOK_CURIOSITY = ("为什么", "秘密", "没人告诉", "想不到", "居然", "竟然", "真相")
_HOOK_CONTRAST = ("但是", "却", "反而", "结果", "其实", "不是", "不是所有", "but")
_ANGLES = ["反常识", "数字冲击", "身份代入", "对比挑衅", "结果先行"]
_TEMPLATES = [
    "POV：{audience} 以为 {expectation}，结果 {twist}",
    "先别划走——{pain} 的人，这条 30 秒讲清楚 {promise}",
    "我花了 {time} 测完 {product}，只说三个字：{twist}",
    "如果你也在 {pain}，千万别再 {wrong}，先看这个",
]


def _to_sec(m: re.Match) -> float:
    h = int(m.group(1))
    mi = int(m.group(2))
    s = int(m.group(3) or 0)
    ms = int(m.group(4).ljust(3, "0")[:3])
    return h * 3600 + mi * 60 + s + ms / 1000.0


def parse_srt(text: str) -> list:
    cues = []
    for block in re.split(r"\r?\n\r?\n+", (text or "").strip()):
        lines = [x for x in block.splitlines() if x.strip()]
        tline = next((x for x in lines if "-->" in x), None)
        if not tline:
            continue
        times = _TIME.findall(tline)
        if len(times) < 2:
            continue
        a = _to_sec(re.search(_TIME, tline))
        tail = tline.split("-->", 1)[1]
        b = _to_sec(re.search(_TIME, tail))
        body = " ".join(x for x in lines[lines.index(tline) + 1:]).strip()
        if body:
            cues.append({"start": round(a, 3), "end": round(b, 3), "text": body})
    return sorted(cues, key=lambda x: (x["start"], x["end"]))


def _norm_cues(cues) -> list:
    out = []
    for c in cues or []:
        try:
            a, b = float(c["start"]), float(c["end"])
            t = str(c.get("text") or "").strip()
        except (KeyError, TypeError, ValueError):
            continue
        if b > a and t:
            out.append({"start": round(a, 3), "end": round(b, 3), "text": t})
    return sorted(out, key=lambda x: x["start"])


def _words(s: str) -> int:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", s or ""))
    latin = len(re.findall(r"[A-Za-z0-9]+", s or ""))
    return cjk + latin


def _hook_type(text: str) -> str:
    t = (text or "").lower()
    if any(w in text for w in ("?", "？", "吗", "呢")):
        return "question"
    if re.search(r"\d", text):
        return "number"
    if any(w in t for w in _HOOK_CONTRAST) or any(w in text for w in _HOOK_CONTRAST):
        return "contrast"
    if any(w in text for w in _HOOK_COMMAND):
        return "command"
    if any(w in text for w in _HOOK_CURIOSITY):
        return "curiosity"
    return "statement"


def _bucket(cues, window=5.0) -> list:
    if not cues:
        return []
    end = max(c["end"] for c in cues)
    n = max(1, int((end + window - 1e-9) // window))
    out = []
    for i in range(n):
        a, b = i * window, (i + 1) * window
        words = sum(_words(c["text"]) for c in cues if c["start"] < b and c["end"] > a)
        out.append({"at": round(a, 1), "words": words, "wpm": round(words / window * 60, 1)})
    return out


def _overlap(c, a, b) -> float:
    return max(0.0, min(c["end"], b) - max(c["start"], a))


def _segments(cues, duration, allow_empty=False) -> list:
    d = max(float(duration or 0), max((c["end"] for c in cues), default=0.0))
    if d <= 0:
        return []
    spans = [("hook", 0.0, min(3.0, d)), ("setup", min(3.0, d), d * 0.35),
             ("twist", d * 0.35, d * 0.65), ("payoff", d * 0.65, d * 0.88), ("cta", d * 0.88, d)]
    out = []
    for role, a, b in spans:
        if b <= a:
            continue
        caps = [c["text"] for c in cues if _overlap(c, a, b) > 0]
        if not caps and role != "cta" and not allow_empty:
            continue
        out.append({"role": role, "start": round(a, 2), "end": round(b, 2),
                    "caption": " ".join(caps)[:160],
                    "word_count": sum(_words(x) for x in caps)})
    return out


def _cta(cues, duration) -> str:
    d = max(float(duration or 0), max((c["end"] for c in cues), default=0.0))
    hits = [c["text"] for c in cues if any(w in c["text"] for w in _CTA) and c["start"] >= d * 0.55]
    return " / ".join(hits)[:160]


def _variants(brief: dict, n: int) -> list:
    b = brief or {}
    product = str(b.get("product") or b.get("topic") or "这个产品")[:30]
    audience = str(b.get("audience") or "你")[:30]
    pain = str(b.get("pain") or "预算有限")[:40]
    promise = str(b.get("promise") or "把关键说清楚")[:40]
    expectation = str(b.get("expectation") or "它很普通")[:40]
    twist = str(b.get("twist") or "结果完全反过来")[:40]
    wrong = str(b.get("wrong") or "乱买")[:20]
    vals = {"product": product, "audience": audience, "pain": pain, "promise": promise,
            "expectation": expectation, "twist": twist, "wrong": wrong, "time": "3 天"}
    return [{"angle": _ANGLES[i % len(_ANGLES)],
             "hook": _TEMPLATES[i % len(_TEMPLATES)].format(**vals)}
            for i in range(max(1, min(int(n or 3), 20)))]


def _recipe(reading, brief, n) -> dict:
    scenes = []
    for seg in reading.get("segments") or []:
        scenes.append({
            "role": seg["role"], "start": seg["start"], "end": seg["end"],
            "caption": seg.get("caption", ""),
            "broll": "待选（自有/已授权素材）" if seg["role"] in ("setup", "twist", "payoff") else "无",
            "slots": ["host", "product"] if seg["role"] in ("hook", "payoff", "cta") else ["broll"],
        })
    return {
        "format": "viral_clone_v1", "anchor": "word", "source": "user_supplied_subtitles",
        "duration_s": reading.get("duration_s"),
        "segments": scenes,
        "shots": reading.get("shots"),
        "variant_slots": ["host", "product", "language", "hook_angle", "broll", "cta"],
        "variants": _variants(brief, n),
        "visual": reading.get("visual"),
        "guardrails": STATUS["guardrails"],
        "edit_chain_hint": "可交 edit_pipeline：scenes → 轨道/片段；caption → 字幕；broll → 素材槽",
    }


def _find_bin(name: str) -> str:
    import os
    env = os.environ.get("GBT_" + name.upper())
    if env:
        return env
    for d in (ROOT / "vendor" / "ffmpeg" / "bin", ROOT.parent / "vendor" / "ffmpeg" / "bin",
              ROOT / "tools" / "ffmpeg", ROOT.parent / "vendor" / "ffmpeg"):
        p = d / (name + (".exe" if __import__("os").name == "nt" else ""))
        if p.is_file():
            return str(p)
    return shutil.which(name) or ""


def _run(cmd, timeout=120):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def _parse_showinfo(text: str) -> list:
    """从 ffmpeg showinfo 输出解析场景切换时间（秒）。"""
    import re as _re
    hits = _re.findall(r"pts_time:([0-9]+(?:\.[0-9]+)?)", text or "")
    return [round(float(x), 3) for x in hits]


def _parse_volumedetect(text: str) -> dict:
    import re as _re
    out = {}
    for key in ("mean_volume", "max_volume"):
        m = _re.search(key + r":\s*(-?[0-9.]+)\s*dB", text or "")
        if m:
            out[key + "_db"] = float(m.group(1))
    return out


def _shot_stats(cuts: list, duration: float) -> dict:
    pts = [0.0] + sorted(float(x) for x in cuts or []) + ([round(float(duration), 3)] if duration else [])
    shot = [round(b - a, 3) for a, b in zip(pts, pts[1:]) if b > a]
    return {"cuts": len(cuts or []), "shots": len(shot),
            "first_shot_s": shot[0] if shot else None,
            "avg_shot_s": round(sum(shot) / len(shot), 2) if shot else None,
            "cuts_per_min": round(len(cuts or []) / duration * 60, 2) if duration else None}


def _parse_visual(text: str) -> dict:
    """解析 ffmpeg signalstats metadata=print 的 YAVG/SATAVG 序列。"""
    import re as _re
    y = [float(x) for x in _re.findall(r"lavfi\.signalstats\.YAVG=([0-9.]+)", text or "")]
    s = [float(x) for x in _re.findall(r"lavfi\.signalstats\.SATAVG=([0-9.]+)", text or "")]
    out = {}
    if y:
        out["yavg"] = {"n": len(y), "mean": round(sum(y) / len(y), 2),
                       "min": round(min(y), 2), "max": round(max(y), 2),
                       "first3s_mean": round(sum(y[:3]) / len(y[:3]), 2)}
    if s:
        out["satavg"] = {"n": len(s), "mean": round(sum(s) / len(s), 2),
                         "min": round(min(s), 2), "max": round(max(s), 2)}
    return out


def _visual_stats(path, timeout=180) -> dict:
    ffmpeg = _find_bin("ffmpeg")
    if not ffmpeg:
        return {}
    try:
        code, out, err = _run([ffmpeg, "-hide_banner", "-nostats", "-i", str(path),
                               "-vf", "signalstats,metadata=print:file=-",
                               "-an", "-f", "null", "-"], timeout=timeout)
        return _parse_visual((out or "") + (err or ""))
    except Exception:  # noqa: BLE001
        return {}


def _parse_keyframes(text: str) -> list:
    """解析 ffprobe csv（pkt_pts_time,pict_type）里的 I 帧时间。"""
    out = []
    for line in (text or "").splitlines():
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if not parts or "I" not in parts:
            continue
        for p in parts:
            try:
                out.append(round(float(p), 3))
                break
            except ValueError:
                continue
    return sorted(set(out))


def _keyframes(path, limit=30) -> list:
    ffprobe = _find_bin("ffprobe")
    if not ffprobe:
        return []
    try:
        code, out, err = _run([ffprobe, "-v", "error", "-select_streams", "v:0",
                               "-show_entries", "frame=best_effort_timestamp_time,pict_type",
                               "-of", "csv=p=0", str(path)], timeout=120)
        return _parse_keyframes(out)[:limit]
    except Exception:  # noqa: BLE001
        return []


def c_ok(x) -> bool:
    return isinstance(x, (int, float)) and x == x and x >= 0


def _align_cues(cues, cuts) -> list:
    """按场景切点切字幕：跨切的 cue 按字符比例拆开，起始/结束对齐到切点。"""
    pts = sorted({round(float(x), 3) for x in cuts or [] if c_ok(float(x))})
    out = []
    for c in cues or []:
        a0, b0 = float(c["start"]), float(c["end"])
        if b0 <= a0:
            continue
        bounds = [a0] + [x for x in pts if a0 < x < b0] + [b0]
        text = str(c.get("text") or "")
        n = max(1, len(text))
        pos = 0
        for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
            if b <= a:
                continue
            if i == len(bounds) - 2:
                seg = text[pos:]
            else:
                take = max(1, round(n * (b - a) / (b0 - a0)))
                seg = text[pos:pos + take]
            pos += len(seg)
            seg = seg.strip()
            if seg:
                out.append({"start": round(a, 3), "end": round(b, 3), "text": seg})
    return out


def _shot_captions(cues, cuts, duration) -> list:
    if not duration:
        return []
    pts = [0.0] + sorted({round(float(x), 3) for x in cuts or []}) + [round(float(duration), 3)]
    out = []
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        caps = [c["text"] for c in cues if min(c["end"], b) > max(c["start"], a)]
        out.append({"shot": i + 1, "start": round(a, 2), "end": round(b, 2),
                    "caption": " ".join(caps)[:160], "words": sum(_words(x) for x in caps)})
    return out


def _safe_stem(path) -> str:
    import re as _re
    s = _re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", str(path).replace("\\", "/").split("/")[-1])
    return (s or "video")[:60]


def _extract_frames(path, times, limit=8) -> dict:
    """导关键帧缩略图 + 首帧封面（写 outputs/viral-forge/；不进源码交付）。"""
    ffmpeg = _find_bin("ffmpeg")
    if not ffmpeg:
        return {"ok": False, "status": "needs_dependency",
                "detail": "ffmpeg 不在 PATH（可设 GBT_FFMPEG）"}
    ts = [0.0] + sorted({round(float(x), 3) for x in times or [] if c_ok(float(x)) and float(x) > 0})[:limit]
    out_dir = ROOT / "outputs" / "viral-forge" / _safe_stem(path)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "not_writable",
                "detail": "%s: %s" % (type(e).__name__, str(e)[:120])}
    files = []
    for i, t in enumerate(ts):
        name = "cover.jpg" if i == 0 else "frame-%02d-%s.jpg" % (i, str(t).replace(".", "_"))
        out = out_dir / name
        try:
            code, so, se = _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                                 "-ss", str(t), "-i", str(path), "-frames:v", "1",
                                 "-vf", "scale=480:-2", str(out)], timeout=60)
            if code == 0 and out.is_file() and out.stat().st_size > 0:
                files.append({"t": t, "path": str(out), "bytes": out.stat().st_size})
        except Exception:  # noqa: BLE001
            continue
    return {"ok": bool(files), "dir": str(out_dir), "files": files}


_VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")


def _inbox_dir(payload=None) -> Path:
    payload = payload or {}
    if payload.get("inbox"):
        return Path(payload["inbox"]).expanduser().resolve()
    try:
        cfg = json.loads((ROOT / "state" / "viral_forge.json").read_text(encoding="utf-8"))
        if cfg.get("inbox"):
            return Path(cfg["inbox"]).expanduser().resolve()
    except Exception:  # noqa: BLE001
        pass
    return (ROOT / "outputs" / "viral-forge" / "inbox").resolve()


def _scan_inbox(d: Path) -> list:
    out = []
    try:
        for p in d.iterdir():
            if p.is_file() and p.suffix.lower() in _VIDEO_EXT:
                out.append(p)
    except OSError:
        return []
    return sorted(out, key=lambda p: p.stat().st_mtime, reverse=True)


def _done_key(p: Path) -> str:
    try:
        st = p.stat()
        return "%s|%d|%d" % (p.name, st.st_size, int(st.st_mtime))
    except OSError:
        return p.name


def _load_done() -> set:
    try:
        return set(json.loads((ROOT / "state" / "viral_forge_done.json").read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        return set()


def _save_done(done: set) -> str:
    try:
        p = ROOT / "state" / "viral_forge_done.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(sorted(done)[-500:], ensure_ascii=False, indent=1), encoding="utf-8")
        return str(p)
    except Exception as e:  # noqa: BLE001
        return "not_writable: %s" % type(e).__name__


def _report_md(out: dict, name: str) -> str:
    rd = out.get("reading") or {}
    vis = rd.get("visual") or {}
    lines = ["# 爆款拆解报告 · %s" % name, "",
             "> 由 `viral_forge` 生成；只做结构/画面拆解，不复制原视频。", "",
             "## 读数", "",
             "- 时长：%ss · 语速：%s 字/分 · 钩子类型：%s" % (rd.get("duration_s"), rd.get("wpm") or "—", rd.get("hook_type")),
             "- 钩子：%s" % (rd.get("hook") or "（无字幕）"),
             "- CTA：%s" % (rd.get("cta") or "—")]
    if vis:
        st = vis.get("shot_stats") or {}
        col = vis.get("color") or {}
        lines += ["- 镜头：%s 个 · 首镜 %ss · 平均 %ss · 每分钟切点 %s" % (
            st.get("shots"), st.get("first_shot_s"), st.get("avg_shot_s"), st.get("cuts_per_min")),
            "- 关键帧：%s" % (vis.get("keyframes_s") or [])[:12],
            "- 亮度：%s · 饱和度：%s" % ((col.get("yavg") or {}).get("mean"), (col.get("satavg") or {}).get("mean"))]
    lines += ["", "## 段落", ""]
    for s in rd.get("segments") or []:
        lines.append("- **%s** %.1f–%.1fs：%s" % (s.get("role"), s.get("start"), s.get("end"), s.get("caption") or "（无字幕）"))
    rec = out.get("recipe") or {}
    if rec.get("variants"):
        lines += ["", "## 变体钩子", ""]
        for v in rec["variants"]:
            lines.append("- [%s] %s" % (v.get("angle"), v.get("hook")))
    lines += ["", "> 红线：只用自有/授权素材；不复制原片画面音频；不自动发布。", ""]
    return "\n".join(lines)


def _inbox(payload, batch=False) -> dict:
    inbox = _inbox_dir(payload)
    try:
        inbox.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "not_writable", "detail": "%s: %s" % (type(e).__name__, str(e)[:120]),
                "inbox": str(inbox)}
    videos = _scan_inbox(inbox)
    if not videos:
        return {"ok": True, "status": "empty", "inbox": str(inbox),
                "note": "把视频（mp4/mov/mkv/webm/avi）丢进这个目录，下一次心跳会自动拆解"}
    done = _load_done()
    todo = [v for v in videos if _done_key(v) not in done]
    if not todo:
        return {"ok": True, "status": "all_done", "inbox": str(inbox), "count": len(videos),
                "note": "目录里的视频都拆过了；要重拆就删 state/viral_forge_done.json 里对应项或加 --force"}
    picked = [todo[0]] if not batch else todo[: int(payload.get("limit") or 10)]
    results = []
    reports_dir = ROOT / "outputs" / "viral-forge" / "reports"
    for v in picked:
        srt = next((p for p in (v.with_suffix(".srt"), v.with_suffix(".vtt")) if p.is_file()), None)
        p = dict(payload)
        p.pop("inbox", None)
        p.update({"video": str(v), "thumbs": True, "align": True})
        if srt:
            p["text"] = srt.read_text(encoding="utf-8", errors="replace")
        out = _do(p, want_recipe=True)
        rec = {"file": str(v), "ok": out.get("ok"), "report": None, "thumbs": (out.get("thumbs") or {}).get("files", [])}
        if out.get("ok"):
            stem = v.stem
            try:
                reports_dir.mkdir(parents=True, exist_ok=True)
                md = reports_dir / (stem + ".md")
                js = reports_dir / (stem + ".json")
                md.write_text(_report_md(out, stem), encoding="utf-8")
                js.write_text(json.dumps({"reading": out.get("reading"), "recipe": out.get("recipe"),
                                          "thumbs": out.get("thumbs"), "video_probe": out.get("video_probe")},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
                rec["report"] = {"md": str(md), "json": str(js)}
                done.add(_done_key(v))
            except Exception as e:  # noqa: BLE001
                rec["report_error"] = "%s: %s" % (type(e).__name__, str(e)[:120])
        results.append(rec)
    rec_path = _save_done(done) if results else None
    return {"ok": all(x.get("ok") for x in results), "status": "processed", "inbox": str(inbox),
            "count": len(results), "results": results, "done_ledger": rec_path,
            "honesty": "只拆结构与画面；不复制原视频；报告落 outputs/viral-forge/reports/"}


def analyze_video(path, threshold: float = 0.35, timeout: int = 180) -> dict:
    """只读视频帧分析：ffprobe 元数据 + ffmpeg 场景切分 + 音量。缺依赖如实报。"""
    if not path:
        return {"ok": False, "status": "needs_input", "detail": "未提供 video 路径"}
    ffprobe, ffmpeg = _find_bin("ffprobe"), _find_bin("ffmpeg")
    if not ffprobe:
        return {"ok": False, "status": "needs_dependency",
                "detail": "ffprobe 不在 PATH（可设 GBT_FFPROBE）；只用字幕，不猜画面",
                "how_to_fix": "装 ffmpeg 后重试，或设 GBT_FFPROBE/GBT_FFMPEG"}
    try:
        code, out, err = _run([ffprobe, "-v", "error", "-print_format", "json",
                               "-show_format", "-show_streams", str(path)], timeout=30)
        if code != 0:
            return {"ok": False, "status": "failed", "detail": (err or out)[-200:]}
        meta = json.loads(out or "{}")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "failed", "detail": "%s: %s" % (type(e).__name__, str(e)[:120])}
    fmt = meta.get("format") or {}
    streams = meta.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    duration = float(fmt.get("duration") or v.get("duration") or 0) or 0
    fps = None
    try:
        num, den = str(v.get("avg_frame_rate") or "0/1").split("/")
        fps = round(float(num) / float(den), 3) if float(den) else None
    except Exception:  # noqa: BLE001
        pass
    probe = {"duration_s": round(duration, 3), "width": v.get("width"), "height": v.get("height"),
             "fps": fps, "video_codec": v.get("codec_name"), "audio_codec": a.get("codec_name"),
             "bitrate": fmt.get("bit_rate"), "size": fmt.get("size")}
    cuts, loud = [], {}
    if ffmpeg:
        try:
            code, out, err = _run([ffmpeg, "-hide_banner", "-nostats", "-i", str(path),
                                   "-vf", "select='gt(scene,%s)',showinfo" % threshold,
                                   "-an", "-f", "null", "-"], timeout=timeout)
            cuts = _parse_showinfo((err or "") + (out or ""))
        except Exception:  # noqa: BLE001
            cuts = []
        try:
            code, out, err = _run([ffmpeg, "-hide_banner", "-nostats", "-i", str(path),
                                   "-af", "volumedetect", "-vn", "-f", "null", "-"], timeout=timeout)
            loud = _parse_volumedetect((err or "") + (out or ""))
        except Exception:  # noqa: BLE001
            loud = {}
    return {"ok": True, "source": "ffprobe/ffmpeg", "path": str(path), "probe": probe,
            "visual": {"scene_threshold": threshold, "cuts": cuts,
                       "shot_stats": _shot_stats(cuts, duration),
                       "keyframes_s": _keyframes(path),
                       "color": _visual_stats(path, timeout=timeout),
                       "loudness": loud},
            "honesty": "只读分析，不写文件、不复制内容"}


def _reading(cues, duration, brief, allow_empty=False):
    d = float(duration or 0) or max((c["end"] for c in cues), default=0.0)
    words = sum(_words(c["text"]) for c in cues)
    hook_caps = [c["text"] for c in cues if c["start"] < 3.0]
    hook = " ".join(hook_caps)[:160]
    return {
        "duration_s": round(d, 2), "cue_count": len(cues), "words": words,
        "wpm": round(words / d * 60, 1) if d and words else None,
        "hook": hook, "hook_type": _hook_type(hook),
        "pacing_every_5s": _bucket(cues),
        "segments": _segments(cues, d, allow_empty=allow_empty),
        "cta": _cta(cues, d),
        "brief": brief or {},
    }


def _do(payload, want_recipe=True):
    text = payload.get("text") or payload.get("srt") or payload.get("vtt")
    cues = _norm_cues(payload.get("cues")) if payload.get("cues") else []
    if not cues and text:
        cues = parse_srt(text)
    va = analyze_video(payload.get("video")) if payload.get("video") else {
        "ok": True, "note": "未提供视频（只做字幕分析）"}
    video_dur = ((va.get("probe") or {}).get("duration_s") if va.get("ok") else None)
    if not cues and not video_dur:
        return {"ok": False, "status": "needs_input",
                "error": "需要字幕/逐句稿（text 或 cues），或提供可读视频（video + ffprobe）",
                "how_to_fix": "先有词级/句级字幕；视频分析需要 ffmpeg/ffprobe"}
    duration = payload.get("duration") or video_dur
    brief = payload.get("brief") if isinstance(payload.get("brief"), dict) else {}
    n = payload.get("variants", 3)
    cuts = ((va.get("visual") or {}).get("cuts") or []) if va.get("ok") else []
    aligned = False
    if cues and cuts and payload.get("align", True) is not False:
        cues = _align_cues(cues, cuts)
        aligned = True
    reading = _reading(cues, duration, brief, allow_empty=bool(video_dur and not cues))
    if va.get("ok") and va.get("visual"):
        reading["visual"] = va.get("visual")
        reading["video_probe"] = va.get("probe")
        reading["shots"] = _shot_captions(cues, cuts, duration)
        if aligned:
            reading["alignment"] = {"aligned": True, "cuts": len(cuts)}
        reading["mode"] = "video_only" if not cues else "video+subtitles"
    out = {"ok": True, "cap": "viral_forge", "reading": reading, "video_probe": va,
           "honesty": "只做结构/画面分析；不下载/不复制原视频；变体钩子是模板，不是模型生成"}
    if want_recipe:
        out["recipe"] = _recipe(reading, brief, n)
    if payload.get("thumbs") is True and payload.get("video"):
        out["thumbs"] = _extract_frames(payload.get("video"), cuts, limit=int(payload.get("thumbs_limit") or 6))
    return out


def run(op="status", **kw):
    op = str(op or "status").strip().lower()
    if op == "status":
        return {"ok": True, "op": "status", **STATUS}
    if op == "where":
        return {"ok": True, "op": "where", "cap": "viral_forge", **STATUS,
                "entry": "py -3.14 tools/codex-scripts/five-dim.py cap viral_forge '{\"op\":\"teardown\"}'",
                "module": "gbt_allinone/tentacle/viral_forge.py",
                "absorbed_from": "hypit-ai/hypit（设计吸收；未复制代码）",
                "example": "run_task('viral_forge', {'op':'teardown','text': srt, 'brief': {'product':'耳机'}, 'variants':3})",
                "video_example": "run_task('viral_forge', {'op':'teardown','video':'D:/clip.mp4','text': srt})  # 需 ffmpeg/ffprobe"}
    if op in ("inbox", "batch"):
        return _inbox(kw, batch=(op == "batch"))
    if op in ("analyze", "video"):
        return analyze_video(kw.get("video") or kw.get("path"), float(kw.get("threshold") or 0.35))
    if op in ("frames", "thumbs"):
        return _extract_frames(kw.get("video") or kw.get("path"), kw.get("times") or [],
                               limit=int(kw.get("limit") or kw.get("thumbs_limit") or 8))
    if op == "pipeline":
        p = dict(kw)
        p.setdefault("thumbs", True)
        analysis = analyze_video(p.get("video"), float(p.get("threshold") or 0.35)) if p.get("video") else {
            "ok": True, "note": "未提供视频（字幕链）"}
        forge = _do(p, want_recipe=True)
        return {"ok": forge.get("ok"), "op": "pipeline", "analysis": analysis, "forge": forge,
                "chain": ["analyze", "teardown", "recipe"],
                "honesty": "一条调用串起三段落；视频分析重复跑一次是为了让每段都能单独用"}
    if op in ("teardown", "blueprint", "clone"):
        out = _do(kw, want_recipe=True)
        out["op"] = op
        return out
    return {"ok": False, "op": op, "status": "unknown_op",
            "error": "未知 op：%s" % op, "available": STATUS["ops"], "fail_closed": True}
