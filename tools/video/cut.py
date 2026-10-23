# -*- coding: utf-8 -*-
"""Video Cut（剪）· **本地可执行**版：不依赖任何 Runtime / 宿主。

出处与依据：
- 方法口径来自 `chengfeng-cut` / `chengfeng-videocut-workbench`（已装技能，读它们的 SKILL.md 取craft）；
- 执行只用本机 **ffmpeg 8.1.2**（`silencedetect` / `silenceremove` 均在本机实测存在）；
- 有 whisper（本机 `whisper.exe` ✓）时可再加一层**口误/重复句**识别。

    python tools/video/cut.py silence <in.mp4> <out.mp4> [--thresh -35dB] [--min 0.30]
    python tools/video/cut.py e（打印 EDL）         # 只分析不落刀
    python tools/video/cut.py probe <in.mp4>        # 客观读数

判据（真门）：
  ① 输出存在且可解码；② 输出时长 < 输入时长（真的剪掉了）；③ 剪切段数 ≥1；④ 分辨率/帧率不变。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

# 🔴 2026-09-26 补：Windows 管道/重定向下 stdout 回落 GBK，emoji 一打印就崩；与 self_model.py 同一款补丁
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


WS = pathlib.Path(__file__).resolve().parents[2]


def dur_of(p: pathlib.Path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


def probe_streams(p: pathlib.Path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate", "-of", "json", str(p)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    s = (json.loads(r.stdout or "{}").get("streams") or [{}])[0]
    return s.get("width"), s.get("height"), s.get("r_frame_rate")


def detect_silence(p: pathlib.Path, thresh="-35dB", min_len=0.30):
    """返回 [(start, end), ...] 静音段（ffmpeg silencedetect 真读数）"""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af",
                        f"silencedetect=noise={thresh}:d={min_len}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = (r.stderr or "")
    starts = [float(m.group(1)) for m in re.finditer(r"silence_start:\s*([0-9.]+)", log)]
    ends = [float(m.group(1)) for m in re.finditer(r"silence_end:\s*([0-9.]+)", log)]
    spans = list(zip(starts, ends + ([dur_of(p)] if len(ends) < len(starts) else [])))
    return spans, log


def cut_silence(src: pathlib.Path, out: pathlib.Path, thresh="-35dB", min_len=0.30, keep_pad=0.08):
    """删静音：保留每段有声区（两端留 keep_pad），再无损拼接。"""
    spans, _ = detect_silence(src, thresh, min_len)
    total = dur_of(src)
    if not spans:
        print("S2 门: ❌ 未检出静音段（阈值/时长不合？）")
        return 1
    keep, cursor = [], 0.0
    for s, e in spans:
        a, b = s + keep_pad, e - keep_pad            # a=有声段终点（静音前），b=静音后的起点
        if a - cursor > 0.12:                        # 保留 [cursor, a] = 这段有声
            keep.append((cursor, a))
        cursor = max(cursor, b)                      # 跳过静音
    if total - cursor > 0.12:
        keep.append((cursor, total))
    if not keep:
        print("S2 门: ❌ 全被剪空（阈值过松）")
        return 1
    # 用 filter_complex 精确切+拼（避免多次重编码累积损失：一次编码完成）
    parts, labels = [], []
    for i, (a, b) in enumerate(keep):
        parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}];"
                     f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    fc = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(keep)}:v=1:a=1[vo][ao]"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
           "-filter_complex", fc, "-map", "[vo]", "-map", "[ao]",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"S2 门: ❌ ffmpeg 失败：{(r.stderr or '')[:120]}")
        return 1
    # ── 真门（判据必须能抓住"没剪掉"）──
    d_in, d_out = dur_of(src), dur_of(out)
    w1, h1, fps1 = probe_streams(src)
    w2, h2, fps2 = probe_streams(out)
    sil_total = sum(e - s for s, e in spans)
    saved = d_in - d_out
    ok = (out.exists() and d_out > 0
          and saved >= 0.5 * sil_total          # ★ 省下的必须≈检出的静音总长（宽松系数 0.5，留给 padding）
          and len(spans) >= 1
          and (w1, h1, fps1) == (w2, h2, fps2))
    print(f"  检出静音 {len(spans)} 段（共 {sil_total:.2f}s）· 保留有声 {len(keep)} 段")
    print(f"  时长 {d_in:.2f}s → {d_out:.2f}s（省 {saved:.2f}s · 应≈{sil_total:.2f}s）· {w2}x{h2} {fps2}")
    print(f"S2 门: {'✅' if ok else '❌'} {'剪掉的量与检出静音相符且规格未变' if ok else '省下的时长与检出静音不符（没真剪掉？）'}")
    return 0 if ok else 1


def detect_still(p: pathlib.Path, fps=4, thresh=2.0, min_len=0.6):
    """返回 [(start, end), ...] **静止段**（视频域的真读数，不靠音轨）。

    🔴 2026-10-10 补：本件原来只有 silence（删静音），它走 [0:a]atrim ⇒ **要求有音轨**。
    而"本地录制"（tools/video/tentacle-record.py）出的是**无音轨**屏幕录像 ⇒ S2 **根本剪不了它**。
    ⇒ 补一条**视频域**的判法：按帧间差找"画面不动"的段，用于删掉屏幕录像里的发呆段。
    量法与录制件的质量读数同源（下采样灰度平均绝对差），**不是另发明一套尺子**。
    """
    import tempfile
    td = pathlib.Path(tempfile.mkdtemp(prefix="gbt_still_"))
    pat = td / "f%05d.png"
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(p),
                        "-vf", f"fps={fps},scale=64:36", str(pat)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return [], r.stderr or "抽帧失败"
    try:
        from PIL import Image
    except Exception:                                                  # noqa: BLE001
        return [], "PIL 不在，静止段判不了"
    files = sorted(td.glob("*.png"))
    diffs, prev = [], None
    for f in files:
        cur = list(Image.open(f).convert("L").getdata())
        diffs.append(0.0 if prev is None else sum(abs(a - b) for a, b in zip(cur, prev)) / len(cur))
        prev = cur
    spans, start = [], None
    for i, d in enumerate(diffs):
        still = d < thresh
        if still and start is None:
            start = i
        elif not still and start is not None:
            if (i - start) / fps >= min_len:
                spans.append((start / fps, i / fps))
            start = None
    if start is not None and (len(diffs) - start) / fps >= min_len:
        spans.append((start / fps, len(diffs) / fps))
    n = len(files)
    for f in files:
        f.unlink()
    try:
        td.rmdir()
    except OSError:
        pass
    return spans, {"抽帧数": n, "平均帧间差": round(sum(diffs[1:]) / max(1, len(diffs) - 1), 2)}


def cut_still(src: pathlib.Path, out: pathlib.Path, thresh=2.0, min_len=0.6):
    """删**静止段**（保动的那部分）—— 视频域，不需要音轨。判据照本件自己的风格。"""
    spans, info = detect_still(src, thresh=thresh, min_len=min_len)
    if isinstance(info, str):
        print(f"S2 门: ❌ {info}")
        return 1
    total = dur_of(src)
    if not spans:
        print(f"S2 门: ❌ 未检出静止段（平均帧间差 {info.get('平均帧间差')} ⇒ 整条都在动，没得剪）")
        return 1
    keep, cursor = [], 0.0
    for s, e in spans:
        if s - cursor > 0.12:
            keep.append((cursor, s))
        cursor = max(cursor, e)
    if total - cursor > 0.12:
        keep.append((cursor, total))
    if not keep:
        print(f"S2 门: ❌ **全被剪空**（{len(spans)} 段静止覆盖了全片 ⇒ 这条录像没有可保留的画面）")
        return 1
    parts, labels = [], []
    for i, (a, b) in enumerate(keep):
        parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
        labels.append(f"[v{i}]")
    fc = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(keep)}:v=1:a=0[vo]"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
           "-filter_complex", fc, "-map", "[vo]",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"S2 门: ❌ ffmpeg 失败：{(r.stderr or '')[:120]}")
        return 1
    d_in, d_out = dur_of(src), dur_of(out)
    w1, h1, fps1 = probe_streams(src)
    w2, h2, fps2 = probe_streams(out)
    st_total = sum(e - s for s, e in spans)
    saved = d_in - d_out
    ok = (out.exists() and d_out > 0 and d_out < d_in
          and saved >= 0.6 * st_total
          and len(spans) >= 1
          and (w1, h1, fps1) == (w2, h2, fps2))
    print(f"  检出静止 {len(spans)} 段（共 {st_total:.2f}s · 平均帧间差 {info.get('平均帧间差')}）· 保留 {len(keep)} 段")
    print(f"  时长 {d_in:.2f}s → {d_out:.2f}s（省 {saved:.2f}s · 应≈{st_total:.2f}s）· {w2}x{h2} {fps2}")
    print(f"S2 门: {'✅' if ok else '❌'} "
          f"{'剪掉的量与检出静止相符且规格未变' if ok else '省下的时长与检出静止不符（没真剪掉？）'}")
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        raise SystemExit(2)
    if a[0] == "probe":
        p = pathlib.Path(a[1]); w, h, fps = probe_streams(p)
        print(f"✅ {dur_of(p):.3f}s · {w}x{h} · {fps}")
        raise SystemExit(0)
    if a[0] in ("still", "still-edl"):
        src = pathlib.Path(a[1])
        def _o(flag, default):
            if flag not in a:
                return default
            i = a.index(flag)
            return a[i + 1] if i + 1 < len(a) else default
        th = float(_o("--thresh", 2.0))
        ml = float(_o("--min", 0.6))
        if a[0] == "still-edl":
            sp, info = detect_still(src, thresh=th, min_len=ml)
            print(f"EDL：拟删静止 {len(sp)} 段 · 共 {sum(e - s for s, e in sp):.2f}s · {info}")
            for s, e in sp[:20]:
                print(f"  {s:7.2f} → {e:7.2f}  （{e - s:.2f}s）")
            raise SystemExit(0)
        raise SystemExit(cut_still(src, pathlib.Path(a[2]), th, ml))
    if a[0] in ("silence", "edl"):
        src = pathlib.Path(a[1])
        def _opt(flag, default):
            # 🔴 2026-09-26 自纠：flag 恰为末参时 a[i+1] 会 IndexError
            if flag not in a:
                return default
            i = a.index(flag)
            return a[i + 1] if i + 1 < len(a) else default
        thresh = _opt("--thresh", "-35dB")
        min_len = float(_opt("--min", 0.30))
        if a[0] == "edl":
            spans, _ = detect_silence(src, thresh, min_len)
            print(f"EDL：拟删静音 {len(spans)} 段 · 共 {sum(e - s for s, e in spans):.2f}s")
            for s, e in spans[:20]:
                print(f"  {s:7.2f} → {e:7.2f}  （{e - s:.2f}s）")
            raise SystemExit(0)
        out = pathlib.Path(a[2])
        raise SystemExit(cut_silence(src, out, thresh, min_len))
    print(__doc__)
    raise SystemExit(2)
