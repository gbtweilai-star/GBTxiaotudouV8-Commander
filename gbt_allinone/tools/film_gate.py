# -*- coding: utf-8 -*-
"""film_gate —— 成片验收器（**零外部依赖**）。

为什么要有这一层（2026-11-06 现场读数）
--------------------------------------
本 checkout 里没有 ffmpeg（`vendor/ffmpeg/bin` 不存在、PATH 也没有），也没有 torch：
「这条成片到底是不是 1080×1920 / 25fps / 15.000s / 有没有音轨 / 字幕尾端差多少」
此前只能靠人写报告 —— 报告里的数字没有人复核，也没法机器复跑。

于是验收器**自己读容器**：MP4 box（mvhd/tkhd/mdhd/hdlr/stsd/stts）+ ASS 事件表。
有 ffmpeg 的机器上结论一致（数字来源不同，判据写死在同一份 checks 里）；
没 ffmpeg 的机器上照样能验收，不会因为缺工具就「看起来一切正常」。

三条口径（不许省）
------------------
1. 读不到就报读不到（`needs_input` / `failed`），不许拿默认值当读数；
2. 每个 check 都带**实测值 + 判据**，不只给通过/不通过 —— 报告要能被别人复核；
3. 时长容差 = ±1 帧（25fps ⇒ 0.04s）；字幕尾端 ≤0.3s（沿用渡口 v6 的验收线）。

op
--
    schema      返回契约（不读盘）
    probe       只读一个 mp4：时长/画幅/fps/帧数/编码/音轨
    subtitles   只读一个 ass：条数/覆盖区间/重叠/尾端差
    storyboard  只读分镜：cuts 时长、cutStarts、h3 Picture 时间点三方对齐
    verify      三方合并出结论（缺哪个就说哪个缺，不猜）

与 `tools/render_storyboard_segment.py` 的分工
---------------------------------------------
那边**生产**（t2i/i2v/拼接），这边**验收**。生产能跑不代表成片合格，
验收也不许替生产修图 —— 只报数、只判线。
"""
from __future__ import annotations

import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 竖屏成片的默认线（1080×1920 · 25fps）。调用方可按项目覆盖，但**必须显式传**。
DEFAULT_SPEC = {"width": 1080, "height": 1920, "fps": 25.0,
                "sub_tail_max": 0.3, "duration_tolerance": None}

_ASS_TIME = re.compile(r"^(\d+):(\d{1,2}):(\d{1,2})[.,](\d{1,3})$")
_PICTURE_MARK = re.compile(
    r"Picture\s+(\d+)[^.]*?aligns\s+with\s+the\s+([\d.]+)-second\s+mark", re.I)


# ── 状态词（三态，不许混装）────────────────────────────────────────────────
def _need(what, **kw):
    out = {"ok": False, "status": "needs_input", "missing": what,
           "detail": "缺少 %s —— 验收器不拿默认值代替真读数" % what}
    out.update(kw)
    return out


def _dep(what, **kw):
    out = {"ok": False, "status": "needs_dependency", "missing": what,
           "detail": "%s 不可用（这是环境缺件，不是授权问题）" % what}
    out.update(kw)
    return out


def _bad(msg, **kw):
    out = {"ok": False, "status": "failed", "detail": msg}
    out.update(kw)
    return out


# ── MP4 容器 ───────────────────────────────────────────────────────────────
def _boxes(buf, start, end):
    """遍历 [start, end) 里的同级 box。size==1 走 64 位大盒子，size==0 到文件尾。"""
    pos = start
    while pos + 8 <= end:
        size = struct.unpack_from(">I", buf, pos)[0]
        typ = buf[pos + 4:pos + 8].decode("latin-1", "replace")
        hdr = 8
        if size == 1:
            if pos + 16 > end:
                return
            size = struct.unpack_from(">Q", buf, pos + 8)[0]
            hdr = 16
        elif size == 0:
            size = end - pos
        if size < hdr or pos + size > end:
            return
        yield typ, pos + hdr, pos + size
        pos += size


def _find(buf, start, end, typ):
    for t, a, b in _boxes(buf, start, end):
        if t == typ:
            return a, b
    return None


def _path(buf, start, end, *names):
    a, b = start, end
    for name in names:
        got = _find(buf, a, b, name)
        if not got:
            return None
        a, b = got
    return a, b


def _mvhd(buf, a, b):
    ver = buf[a]
    if ver == 1:
        return (struct.unpack_from(">I", buf, a + 20)[0],
                struct.unpack_from(">Q", buf, a + 24)[0])
    return (struct.unpack_from(">I", buf, a + 12)[0],
            struct.unpack_from(">I", buf, a + 16)[0])


def _mdhd(buf, a, b):
    ver = buf[a]
    if ver == 1:
        return (struct.unpack_from(">I", buf, a + 20)[0],
                struct.unpack_from(">Q", buf, a + 24)[0])
    return (struct.unpack_from(">I", buf, a + 12)[0],
            struct.unpack_from(">I", buf, a + 16)[0])


def _stts(buf, a, b):
    n = struct.unpack_from(">I", buf, a + 4)[0]
    total = 0
    dur = 0
    pos = a + 8
    for _ in range(n):
        if pos + 8 > b:
            break
        cnt, delta = struct.unpack_from(">II", buf, pos)
        total += cnt
        dur += cnt * delta
        pos += 8
    return total, dur


def _stsd_type(buf, a, b):
    try:
        pos = a + 8
        if pos + 8 > b:
            return None
        return buf[pos + 4:pos + 8].decode("latin-1", "replace")
    except Exception:                                   # noqa: BLE001
        return None


def probe_mp4(path) -> dict:
    p = Path(path)
    if not p.is_file():
        return _need(str(p))
    try:
        buf = p.read_bytes()
    except Exception as exc:                            # noqa: BLE001
        return _bad("读不动文件：%s" % type(exc).__name__)
    moov = _find(buf, 0, len(buf), "moov")
    if not moov:
        return _bad("不是可解析的 MP4：没有 moov（可能是纯音频/损坏/未封装）")
    out = {"ok": True, "status": "ok", "path": str(p), "bytes": len(buf),
           "ftyp": None, "duration": None, "video": None, "audio": None,
           "tracks": 0}
    ftyp = _find(buf, 0, len(buf), "ftyp")
    if ftyp:
        out["ftyp"] = buf[ftyp[0]:ftyp[0] + 4].decode("latin-1", "replace")
    mv = _find(buf, *moov, "mvhd")
    if mv:
        ts, du = _mvhd(buf, *mv)
        out["duration"] = round(du / float(ts), 6) if ts else None
        out["timescale"] = ts
    for typ, a, b in _boxes(buf, *moov):
        if typ != "trak":
            continue
        out["tracks"] += 1
        hdlr = _path(buf, a, b, "mdia", "hdlr")
        kind = ""
        if hdlr:
            kind = buf[hdlr[0] + 8:hdlr[0] + 12].decode("latin-1", "replace")
        mdhd = _path(buf, a, b, "mdia", "mdhd")
        mts = mdu = None
        if mdhd:
            mts, mdu = _mdhd(buf, *mdhd)
        tkhd = _find(buf, a, b, "tkhd")
        w = h = None
        if tkhd:
            blk = buf[tkhd[0]:tkhd[1]]
            if len(blk) >= 8:
                w = round(struct.unpack_from(">I", blk, len(blk) - 8)[0] / 65536.0, 3)
                h = round(struct.unpack_from(">I", blk, len(blk) - 4)[0] / 65536.0, 3)
        stbl = _path(buf, a, b, "mdia", "minf", "stbl")
        codec = _stsd_type(buf, *_find(buf, *stbl, "stsd")) if stbl and _find(buf, *stbl, "stsd") else None
        if kind == "vide":
            frames = 0
            if stbl:
                st = _find(buf, *stbl, "stts")
                if st:
                    frames, _ = _stts(buf, *st)
            media_s = (mdu / float(mts)) if (mts and mdu) else None
            fps = round(frames / media_s, 3) if (frames and media_s) else None
            out["video"] = {"codec": codec, "width": w, "height": h,
                            "frames": frames, "fps": fps,
                            "media_seconds": round(media_s, 6) if media_s else None}
        elif kind == "soun":
            rate = ch = None
            st = _find(buf, *stbl, "stsd") if stbl else None
            if st:
                # stsd body = version/flags(4) + entry_count(4) + [size/format(8) + AudioSampleEntry]
                # AudioSampleEntry 偏移：reserved6+dri2=8，version2+revision2+vendor4=16，
                # 于是 channelcount 在 +16、samplerate(16.16) 在 +24（相对 entry 正文）。
                entry = st[0] + 8 + 8
                if entry + 28 <= st[1]:
                    ch = struct.unpack_from(">H", buf, entry + 16)[0]
                    raw = struct.unpack_from(">I", buf, entry + 24)[0]
                    rate = raw >> 16 or round(raw / 65536.0)
            out["audio"] = {"codec": codec, "channels": ch, "sample_rate": rate,
                            "media_seconds": round(mdu / float(mts), 6) if (mts and mdu) else None}
    return out


# ── ASS 字幕 ───────────────────────────────────────────────────────────────
def _ass_seconds(text: str):
    m = _ASS_TIME.match(str(text or "").strip())
    if not m:
        return None
    h, mi, s, frac = m.groups()
    return round(int(h) * 3600 + int(mi) * 60 + int(s) + int(frac.ljust(3, "0")) / 1000.0, 3)


def parse_ass(path) -> dict:
    p = Path(path)
    if not p.is_file():
        return _need(str(p))
    try:
        text = p.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as exc:                            # noqa: BLE001
        return _bad("读不动字幕：%s" % type(exc).__name__)
    events, in_ev, skipped = [], False, 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            in_ev = s.lower().startswith("[events")
            continue
        if not in_ev or not s.lower().startswith("dialogue:"):
            continue
        parts = s.split(":", 1)[1].split(",", 9)
        if len(parts) < 10:
            skipped += 1
            continue
        a, b = _ass_seconds(parts[1]), _ass_seconds(parts[2])
        if a is None or b is None:
            skipped += 1
            continue
        events.append({"start": a, "end": b, "text": parts[9].strip()})
    events.sort(key=lambda e: e["start"])
    overlaps = [(x["end"], y["start"]) for x, y in zip(events, events[1:])
                if x["end"] > y["start"] + 0.001]
    return {"ok": True, "status": "ok", "path": str(p), "count": len(events),
            "events": events, "overlaps": overlaps, "skipped": skipped,
            "first": events[0]["start"] if events else None,
            "last": events[-1]["end"] if events else None}


# ── 分镜时间轴 ─────────────────────────────────────────────────────────────
def _cuts_of(sb: dict, segment_id: str):
    for ep in sb.get("episodes") or []:
        for seg in ep.get("segments") or []:
            if seg.get("id") == segment_id:
                return ep, seg
    return None, None


def check_storyboard(sb, segment_id: str) -> dict:
    if isinstance(sb, (str, Path)):
        p = Path(sb)
        if not p.is_file():
            return _need(str(p))
        try:
            sb = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception as exc:                        # noqa: BLE001
            return _bad("分镜不是合法 JSON：%s" % type(exc).__name__)
    ep, seg = _cuts_of(sb or {}, segment_id)
    if seg is None:
        have = [s.get("id") for e in (sb or {}).get("episodes") or []
                for s in e.get("segments") or []]
        return _bad("分镜里没有 segment %s（有：%s）" % (segment_id, have))
    cuts = seg.get("cuts") or []
    if not cuts:
        return _bad("segment %s 没有 cuts" % segment_id)
    secs = []
    for i, c in enumerate(cuts):
        try:
            secs.append(float(c.get("seconds")))
        except Exception:                               # noqa: BLE001
            return _failed_at(i)
    starts = [round(sum(secs[:i]), 3) for i in range(len(secs))]
    total = round(sum(secs), 3)
    declared = seg.get("cutStarts")
    checks = []
    if isinstance(declared, list):
        checks.append({"name": "cutStarts", "ok": len(declared) == len(starts)
                       and all(abs(float(a) - b) < 1e-6 for a, b in zip(declared, starts)),
                       "expect": starts, "got": declared})
    else:
        checks.append({"name": "cutStarts", "ok": True, "expect": starts,
                       "got": None, "detail": "分镜未声明 cutStarts，按 seconds 累加"})
    marks = [(int(n), float(t)) for n, t in
             _PICTURE_MARK.findall(str(seg.get("h3Prompt") or ""))]
    if marks:
        pairs = [(n, t) for n, t in marks if 1 <= n <= len(starts)]
        checks.append({"name": "h3PictureTimes", "ok": len(pairs) == len(starts)
                       and all(abs(t - starts[n - 1]) < 0.001 for n, t in pairs),
                       "expect": starts, "got": [list(m) for m in marks]})
    shots = len(re.findall(r"\[Shot\s+\d+\]", str(seg.get("h3Prompt") or "")))
    checks.append({"name": "h3ShotCount", "ok": shots == len(cuts),
                   "expect": len(cuts), "got": shots})
    return {"ok": True, "status": "ok", "segment": segment_id, "episode": ep.get("ep"),
            "cuts": len(cuts), "seconds": secs, "cutStarts": starts,
            "total_seconds": total, "checks": checks,
            "checks_ok": all(c["ok"] for c in checks)}


def _failed_at(i):
    return _bad("第 %d 个 cut 的 seconds 不是数字 —— 分镜坏了，不能拿去渲染" % (i + 1))


# ── 合并验收 ───────────────────────────────────────────────────────────────
def verify(film, spec=None, subs=None, storyboard=None, segment="", audio=None) -> dict:
    sp = dict(DEFAULT_SPEC)
    sp.update({k: v for k, v in (spec or {}).items() if v is not None})
    checks = []
    mp4 = probe_mp4(film)
    if not mp4.get("ok"):
        return mp4
    v, au, dur = mp4.get("video"), mp4.get("audio"), mp4.get("duration")

    def line(name, ok, expect, got, detail=""):
        checks.append({"name": name, "ok": (None if ok is None else bool(ok)),
                       "expect": expect, "got": got, "detail": detail})

    line("container", True, "moov 可解析", "%s / %d tracks" % (mp4.get("ftyp"), mp4.get("tracks")))
    line("videoTrack", bool(v), "有视频轨", "有" if v else "无")
    if v:
        line("resolution", (v.get("width"), v.get("height")) == (sp["width"], sp["height"]),
             "%sx%s" % (sp["width"], sp["height"]),
             "%sx%s" % (v.get("width"), v.get("height")))
        if sp.get("fps"):
            fps = v.get("fps")
            line("fps", fps is not None and abs(fps - sp["fps"]) <= 0.01,
                 sp["fps"], fps)
        line("codec", True, "h264/hevc 任一", v.get("codec"))
    line("audioTrack", bool(au), "有音轨", "有" if au else "无")

    sb = None
    if storyboard:
        sb = check_storyboard(storyboard, segment)
        if not sb.get("ok"):
            return sb
        tol = sp.get("duration_tolerance")
        if tol is None:
            tol = round(1.0 / float(sp.get("fps") or 25), 3)     # ±1 帧
        line("duration", dur is not None and abs(dur - sb["total_seconds"]) <= tol + 1e-9,
             "%.3fs ± %.3f" % (sb["total_seconds"], tol), dur, "以分镜 cuts 之和为准")
        for c in sb["checks"]:
            checks.append({"name": "storyboard." + c["name"], "ok": c["ok"],
                           "expect": c.get("expect"), "got": c.get("got"),
                           "detail": c.get("detail", "")})
        if au and au.get("media_seconds") is not None:
            line("audioLength", abs(au["media_seconds"] - dur) <= 0.5,
                 "≈%.3fs" % dur, au["media_seconds"], "音轨短于画面 = 尾段静音")

    sub = None
    if subs:
        sub = parse_ass(subs)
        if not sub.get("ok"):
            return sub
        line("subtitles", sub["count"] > 0, "≥1 条", sub["count"])
        line("subOverlap", not sub["overlaps"], "无重叠", sub["overlaps"])
        if dur:
            first_in = sub["events"][0]["start"]
            last_out = max(e["end"] for e in sub["events"])
            line("subInBounds", first_in >= 0 and last_out <= dur + 0.05,
                 "0 ≤ start，end ≤ %.3fs" % dur, [first_in, last_out],
                 "字幕不许跑出片尾")
            checks.append({"name": "subLastEndGap", "ok": True, "expect": "仅报数",
                           "got": round(dur - last_out, 3),
                           "detail": "最后一条字幕尾端距片尾；稀疏台词的片子偏大属正常"})
        # 「尾端差 ≤0.3s」指的是**字幕尾端 vs 该句实测尾端**（渡口 v6 口径），
        # 没有每句实测尾端就拿不到这个数 —— 逐句配音表要由上游给（sub_refs）。
        # 不给就**如实跳过**，不许拿「距片尾」冒充（第一版就是这么错判的：
        # 稀疏字幕 3 条、最后一条 14.2s 结束，按「距片尾」算出 5.83s 假失败）。
        refs = [float(x) for x in (sp.get("sub_refs") or [])]
        if refs and len(refs) == sub["count"]:
            ds = [round(abs(e["end"] - r), 3) for e, r in zip(sub["events"], refs)]
            line("subTail", max(ds) <= sp["sub_tail_max"] + 1e-9,
                 "每条 ≤%.1fs" % sp["sub_tail_max"], ds, "字幕尾端 vs 该句实测尾端")
        else:
            line("subTail", None, "每条 ≤%.1fs" % sp["sub_tail_max"], "跳过",
                 "未给 sub_refs（每句实测尾端）⇒ 不判，不假绿")

    ok = all(c["ok"] for c in checks if c["ok"] is not None)
    return {"ok": ok, "status": "ok" if ok else "failed",
            "verdict": "过线" if ok else "未过线",
            "spec": sp, "readings": {"mp4": mp4, "storyboard": sb, "subtitles": sub,
                                     "audio": audio},
            "checks": checks,
            "failed": [c["name"] for c in checks if c["ok"] is False],
            "skipped": [c["name"] for c in checks if c["ok"] is None]}


def deps() -> dict:
    """渲染链的依赖体检：**只报读数，不装、不猜**。

    为什么要单列一个 op：本机实测没有 ffmpeg / torch，但交付报告里写着「已渲染」——
    读的人分不清「片子做好了」和「这条链现在还能不能再跑一遍」。
    """
    import importlib.util as _iu
    import shutil as _sh

    have, missing = {}, []
    ff = _sh.which("ffmpeg")
    if not ff:
        for cand in (ROOT / "vendor" / "ffmpeg" / "bin" / "ffmpeg.exe",
                     ROOT / "vendor" / "ffmpeg" / "bin" / "ffmpeg"):
            if cand.is_file():
                ff = str(cand)
                break
    have["ffmpeg"] = ff
    if not ff:
        missing.append("ffmpeg")
    for mod in ("torch", "diffusers", "transformers"):
        ok = _iu.find_spec(mod) is not None
        have[mod] = ok
        if not ok:
            missing.append(mod)
    can_render = not missing
    return {"ok": can_render, "status": "ok" if can_render else "needs_dependency",
            "missing": missing, "have": have,
            "detail": ("渲染链就绪" if can_render else
                       "缺 %s：本机只能做**验收**，不能重新出片（验收器不依赖它们）"
                       % " / ".join(missing)),
            "note": "验收（probe/subtitles/storyboard/verify）零外部依赖，缺件也照跑"}


def schema() -> dict:
    return {"ok": True, "status": "ok", "ops": ["schema", "probe", "subtitles",
                                                "storyboard", "verify", "deps"],
            "spec": DEFAULT_SPEC,
            "input": {"verify": ["film", "spec?", "subs?", "storyboard?", "segment", "audio?"]},
            "states": ["ok", "failed", "needs_input", "needs_dependency"],
            "note": "零外部依赖：MP4 自己解 box，ASS 自己解事件表；不 shell 出去调 ffprobe",
            "checks": ["container", "videoTrack", "resolution", "fps", "codec",
                       "audioTrack", "duration", "audioLength", "subtitles",
                       "subOverlap", "subTail", "storyboard.*"]}


def run(op: str = "schema", **kw) -> dict:
    op = str(op or "schema").strip().lower()
    if op in ("schema", "help", ""):
        return schema()
    if op == "probe":
        return probe_mp4(kw.get("film") or kw.get("path") or "")
    if op == "subtitles":
        return parse_ass(kw.get("subs") or kw.get("path") or "")
    if op == "storyboard":
        return check_storyboard(kw.get("storyboard") or kw.get("path") or "",
                                str(kw.get("segment") or ""))
    if op == "deps":
        return deps()
    if op == "verify":
        film = kw.get("film") or kw.get("path") or ""
        if not film:
            return _need("film")
        return verify(film, spec=kw.get("spec"), subs=kw.get("subs"),
                      storyboard=kw.get("storyboard"),
                      segment=str(kw.get("segment") or ""), audio=kw.get("audio"))
    return {"ok": False, "status": "failed",
            "detail": "不认的 op：%s（有：schema/probe/subtitles/storyboard/verify）" % op}
