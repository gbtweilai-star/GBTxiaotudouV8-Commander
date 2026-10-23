# -*- coding: utf-8 -*-
"""qc-video.py — 数字人片的**验收量具**（画质清晰 / 动作自然 / 语音嘴对齐 三条各给一个数）。

## 为什么要有这一件
主人只有一个要求：**"画质清晰 动作自然 语音嘴对齐"**。
这三条不能靠"我觉得还行"——得每次交付前量一遍，并把数写进回执。本件就是那把尺子。

## 三个数怎么来的（口径写死，别自己改着玩）
1. **画质清晰** = `sharp_face_video / sharp_face_src`
   Laplacian 方差（越锐越大），取**人脸框内**（不含背景，免得被干净灰底抬高分）。
   < 1 表示视频把人脸磨糊了 —— 这就是"生成后变糊"的定量说法。
2. **动作自然** = 两个读数并列，不许只报一个：
   · `head_move`：人脸框外（头/身/背景）逐帧平均绝对差 —— 太小=死板，太大=抽动；
   · `flicker_ratio`：逐帧差分的**尖峰率**（超过中位数 4 倍的帧占比）—— 发光/闪帧会把它顶上去。
3. **语音嘴对齐** = 音频包络 vs 嘴开合度的**互相关**（在 ±12 帧内找峰）
   · `mouth_open` = 嘴框内**暗像素占比**（张嘴露口腔 ⇒ 暗像素变多，这是单调的"开合度"）
   · `r`（峰值相关）、`lag_frames`（视频相对音频的滞后，正=视频慢）
   · `r_at_zero`：不找峰、直接零滞后的相关 —— 报它是为了防"靠挪 12 帧凑出来的高 r"。

## 已知边界（如实写）
· 嘴框固定取**中间帧**的关键点，不逐帧跟踪：still 档头几乎不动 ⇒ 够用；
  头大幅摆动时会低估（读数偏保守）。要更严就逐帧关键点，慢 20 倍。
· 暗像素阈值 60/255 是经验值；换人换光要重标，本件把阈值写进回执，方便对账。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path(tempfile.gettempdir()) / 'gbt-qc'


def _stage(p: Path) -> Path:
    """OpenCV 在 Windows 上读不了非 ASCII 路径（本仓路径带中文）⇒ 先搬到 ASCII 暂存。

    ⚠️ 输入**已经在暂存区**时原样返回：否则自己拷自己会抛 SameFileError
    （2026-10-20 实测栽过：整条 MAR 算完 30 分钟，最后一步炸在这里 —— 便宜校验必须排在贵计算之前）。
    """
    STAGE.mkdir(parents=True, exist_ok=True)
    dst = STAGE / (p.stem.replace(' ', '_') + p.suffix)
    try:
        if dst.resolve() == p.resolve():
            return dst
    except Exception:                                                 # noqa: BLE001
        pass
    shutil.copyfile(p, dst)
    return dst


def _read_frames(path: Path) -> tuple[np.ndarray, float]:
    import cv2
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    if not frames:
        raise SystemExit('读不到帧：%s' % path)
    return np.stack(frames), float(fps)


def _audio_env(path: Path, n: int, fps: float) -> np.ndarray:
    """按视频帧率切成 n 段，每段 RMS，再归一化到 0..1。"""
    import wave
    with wave.open(str(path), 'rb') as w:
        sr, ch = w.getframerate(), w.getnchannels()
        raw = w.readframes(w.getnframes())
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    seg = int(round(sr / fps))
    env = np.array([np.sqrt(np.mean(a[i:i + seg] ** 2) + 1e-12)
                    for i in range(0, min(len(a), seg * n), seg)])
    if env.size < n:
        env = np.pad(env, (0, n - env.size))
    env = env[:n]
    m, M = float(env.min()), float(env.max())
    return (env - m) / (M - m + 1e-9)


def _landmarks(frame_bgr: np.ndarray) -> dict:
    """68 点关键点（face_alignment，venv 里已装）⇒ 脸框 / 嘴框。"""
    import cv2
    import face_alignment
    fa = face_alignment.FaceAlignment(face_alignment.LandmarksType.TWO_D,
                                      device='cpu', flip_input=False)
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pts = fa.get_landmarks(rgb)
    if not pts:
        raise SystemExit('这一帧没检出人脸，量具不下结论')
    p = np.array(pts[0], dtype=np.float32)
    mouth = p[48:68]
    h, w = frame_bgr.shape[:2]

    def box(q, pad):
        x0, x1 = int(max(0, q[:, 0].min() - pad)), int(min(w, q[:, 0].max() + pad))
        y0, y1 = int(max(0, q[:, 1].min() - pad)), int(min(h, q[:, 1].max() + pad))
        return [x0, y0, x1, y1]

    return {'face': box(p, 8), 'mouth': box(mouth, 3),
            'mouth_pts': len(mouth), 'frame_hw': [h, w]}


def _mar_series(frames: np.ndarray, max_width: int = 0) -> np.ndarray:
    """逐帧嘴开合度 MAR（**真正的量法**）：内唇上下距 / 嘴宽，值越大张得越开。

    · 上内唇 62/63/64，下内唇 66/67/68（68 点标准），嘴宽取 48↔54；
    · 检不到脸的帧记 NaN，最后线性插值补上（不拿 0 冒充"闭嘴"）；
    · `max_width>0` 时先把帧缩到该宽度再检测 —— **MAR 是比值，缩放不变**，
      而检测成本随像素走：1472→736 实测快 3 倍以上。
    """
    import cv2
    import face_alignment
    fa = face_alignment.FaceAlignment(face_alignment.LandmarksType.TWO_D,
                                      device='cpu', flip_input=False)
    out = np.full(len(frames), np.nan, dtype=np.float64)
    for i, f in enumerate(frames):
        if max_width and f.shape[1] > max_width:
            sc = float(max_width) / f.shape[1]
            f = cv2.resize(f, (max_width, int(round(f.shape[0] * sc))),
                           interpolation=cv2.INTER_AREA)
        pts = fa.get_landmarks(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        if not pts:
            continue
        p = np.array(pts[0], dtype=np.float32)
        up = p[62:65, 1].mean()
        lo = p[66:69, 1].mean()
        w = abs(float(p[54, 0] - p[48, 0])) or 1.0
        out[i] = abs(lo - up) / w
    bad = np.isnan(out)
    if bad.all():
        raise SystemExit('逐帧都检不到人脸，量具不下结论')
    if bad.any():
        idx = np.arange(len(out))
        out[bad] = np.interp(idx[bad], idx[~bad], out[~bad])
    return out


def _lvar(gray: np.ndarray) -> float:
    import cv2
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--audio', required=True)
    ap.add_argument('--source', required=True, help='原图（判定"变糊了多少"的基准）')
    ap.add_argument('--out', default='', help='报告 json 落点')
    ap.add_argument('--dark', type=int, default=60, help='暗像素阈值 0-255（只在快量法下用）')
    ap.add_argument('--track', action='store_true',
                    help='逐帧关键点算 MAR（准、慢）——**交付前验收必须开**')
    ap.add_argument('--max-width', type=int, default=0, dest='max_width',
                    help='算 MAR 前把帧缩到该宽度（MAR 是比值、缩放不变）；1472 的片用 736 快 3 倍')
    ap.add_argument('--ref-width', type=int, default=736, dest='ref_width',
                    help='画质/动作统一缩到该宽度再量（不同分辨率不可直接比，默认 736）')
    ap.add_argument('--mar-cache', default='', dest='mar_cache',
                    help='逐帧 MAR 序列缓存落点：量过一次就别再量一次（10 分钟/条片）')
    a = ap.parse_args()

    import cv2
    vpath, apath, spath = Path(a.video), Path(a.audio), Path(a.source)
    for p in (vpath, apath, spath):
        if not p.is_file():
            print(json.dumps({'ok': False, 'why': '缺件：%s' % p}, ensure_ascii=False))
            return 2

    frames, fps = _read_frames(_stage(vpath))
    n = len(frames)
    # 🔴 便宜的先做：音频包络**必须在逐帧关键点之前**算完。
    #    2026-10-20 实测栽过：MAR 跑了 30 分钟，最后一步音频自己拷自己抛 SameFileError，
    #    整条白跑。顺序 = 先所有便宜校验，再贵的计算（P26 的正解）。
    env = _audio_env(_stage(apath), n, fps)

    # 🔴 分辨率归一：Laplacian 方差随尺度变（二阶导 ∝ 1/尺度²），
    #    拿 1472 的片去比 736 的原图 = 拿两种尺子量长度。
    #    2026-10-20 实测栽过：v3（1472）算出来 0.4529，首版（736）算出来 0.5438，
    #    看着"变糊了"，其实只是没归一。⇒ 两边都缩到同一宽度再量。
    if a.ref_width:
        native = [int(frames.shape[2]), int(frames.shape[1])]
        frames = np.stack([cv2.resize(f, (a.ref_width, int(round(f.shape[0] * a.ref_width / f.shape[1]))),
                                      interpolation=cv2.INTER_AREA)
                           if f.shape[1] != a.ref_width else f for f in frames])
    else:
        native = [int(frames.shape[2]), int(frames.shape[1])]
    mid = frames[n // 2]
    lm = _landmarks(mid)
    x0, y0, x1, y1 = lm['face']
    mx0, my0, mx1, my1 = lm['mouth']

    # ── 1 画质：视频中位帧 vs 原图，同口径（脸框内 Laplacian 方差）
    gray_mid = cv2.cvtColor(mid, cv2.COLOR_BGR2GRAY)
    src = cv2.imdecode(np.fromfile(str(spath), dtype=np.uint8), cv2.IMREAD_COLOR)
    if src is None:
        raise SystemExit('原图读不到')
    if src.shape[:2] != mid.shape[:2]:
        src = cv2.resize(src, (mid.shape[1], mid.shape[0]), interpolation=cv2.INTER_AREA)
    lm_src = _landmarks(src)
    sx0, sy0, sx1, sy1 = lm_src['face']
    sharp_v = _lvar(gray_mid[y0:y1, x0:x1])
    sharp_s = _lvar(cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)[sy0:sy1, sx0:sx1])

    # ── 2 动作：脸框外的逐帧差（头/身/背景）+ 尖峰率
    g = np.stack([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]).astype(np.int16)
    body = np.ones(g.shape[1:], dtype=bool)
    body[y0:y1, x0:x1] = False
    d_body = np.abs(np.diff(g, axis=0))[:, body].mean(axis=1)
    med = float(np.median(d_body)) or 1e-6
    flicker = float((d_body > 4 * med).mean())

    # ── 3 嘴对齐：开合度 vs 音频包络（--track 用 MAR 真量法，否则用暗像素占比快量）
    if a.track:
        cache = Path(a.mar_cache) if a.mar_cache else None
        if cache and cache.is_file():
            open_ratio = np.array(json.loads(cache.read_text(encoding='utf-8'))['mar'], dtype=np.float64)
            if len(open_ratio) != n:
                open_ratio = _mar_series(frames, a.max_width)
        else:
            open_ratio = _mar_series(frames, a.max_width)
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps({'n': n, 'fps': fps, 'mar': list(map(float, open_ratio))},
                                            ensure_ascii=False), encoding='utf-8')
        method = 'MAR（逐帧关键点：内唇上下距/嘴宽）'
    else:
        inner = g[:, my0:my1, mx0:mx1]
        open_ratio = (inner < a.dark).mean(axis=(1, 2)).astype(np.float64)
        method = '暗像素占比（嘴框内 < %d/255）' % a.dark
    o = (open_ratio - open_ratio.min()) / (open_ratio.max() - open_ratio.min() + 1e-9)

    def xcorr(envx: np.ndarray, lag: int) -> float:
        if lag >= 0:
            x, y = o[:n - lag], envx[lag:]
        else:
            x, y = o[-lag:], envx[:n + lag]
        if x.size < 10:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])

    best = max(range(-12, 13), key=lambda L: abs(xcorr(env, L)))
    # 负控：把包络随机打乱 —— 真对齐的片子这时相关必须塌下来；塌不下来就说明尺子是假的
    rng = np.random.default_rng(0)
    ctrl = float(np.mean([abs(xcorr(env[rng.permutation(n)], 0)) for _ in range(5)]))
    rep = {
        'ok': True,
        'video': str(vpath), 'audio': str(apath), 'source': str(spath),
        'frames': n, 'fps': round(fps, 3), 'size': native, '量尺宽度': a.ref_width,
        '脸框': [int(x0), int(y0), int(x1), int(y1)],
        '嘴框': [int(mx0), int(my0), int(mx1), int(my1)],
        '暗阈值': a.dark,
        '画质清晰': {'sharp_face_video': round(sharp_v, 2),
                     'sharp_face_src': round(sharp_s, 2),
                     'ratio': round(sharp_v / (sharp_s or 1e-6), 4)},
        '动作自然': {'head_move_mean': round(float(d_body.mean()), 3),
                     'head_move_p95': round(float(np.percentile(d_body, 95)), 3),
                     'flicker_ratio': round(flicker, 4)},
        '语音嘴对齐': {'method': method,
                       'r_peak': round(xcorr(env, best), 4), 'lag_frames': int(best),
                       'lag_ms': round(best * 1000.0 / fps, 1),
                       'r_at_zero': round(xcorr(env, 0), 4),
                       'neg_control_r': round(ctrl, 4),
                       'mouth_open_range': round(float(open_ratio.max() - open_ratio.min()), 5)},
    }
    line = json.dumps(rep, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(line, encoding='utf-8')
    print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
