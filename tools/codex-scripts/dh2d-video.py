# -*- coding: utf-8 -*-
"""dh2d-video.py — 用**真音频**驱动 2.5D 数字人出片，并给出三条要求的可量读数。

流程：mp3 → wav → 30fps 包络 → 逐帧驱动嘴型（真浏览器 WebGL 出帧）→ ffmpeg 合成 MP4（带声）。

三条要求各自的读数（不靠"看着像"）：
  · 画质清晰：成片里脸区的 Laplacian 方差（越大越锐）+ 尺寸
  · 动作自然：相邻帧差分的中位数/最大值比（尖刺 = 跳帧或瞬变）
  · 语音嘴对齐：嘴区亮度（张嘴→变暗）与音频包络的相关系数 + 最佳延迟帧

用法：
  py -3.14 tools/codex-scripts/dh2d-video.py --audio holo_pet_w3/voice-theater/assets/voice-greet-zh-tw.mp3
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys

# ── 编码守门（encoding-guard 要求）：不带 -X utf8 调用时不许静默输出空 ──
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
import wave

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAB = os.path.join(ROOT, 'holo_pet_w3', 'voice-theater', 'dh2d-lab.html')
FFMPEG = shutil.which('ffmpeg') or r'C:\Users\ADMIN\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe'


def find_chrome():
    base = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright')
    if os.path.isdir(base):
        for d in sorted(os.listdir(base), reverse=True):
            p = os.path.join(base, d, 'chrome-win64', 'chrome.exe')
            if os.path.exists(p):
                return p
    return None


def envelope(mp3, fps, wav_path):
    """真包络：ffmpeg 解成 16k 单声道 wav，按帧算 RMS，再做"说话门"归一。"""
    subprocess.run([FFMPEG, '-y', '-v', 'error', '-i', mp3, '-ac', '1', '-ar', '16000',
                    '-acodec', 'pcm_s16le', wav_path], check=True)
    with wave.open(wav_path, 'rb') as w:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    hop = int(round(sr / float(fps)))
    frames = []
    for i in range(0, len(x) - hop, hop):
        seg = x[i:i + hop]
        frames.append(float(np.sqrt(np.mean(seg * seg))))
    e = np.array(frames, dtype=np.float32)
    # 说话门：去掉底噪后按 95 分位归一，再压一下峰值（人嘴开合的动态范围本来就没音频那么大）
    floor = float(np.percentile(e, 12))
    e = np.clip(e - floor, 0, None)
    top = float(np.percentile(e, 95)) or 1.0
    e = np.clip(e / top, 0, 1)
    # 短窗平滑：嘴是机械结构，跟不上 3ms 的毛刺
    k = np.array([0.15, 0.7, 0.15], dtype=np.float32)
    e = np.convolve(e, k, mode='same')
    return np.clip(e, 0, 1), (len(x) / float(sr))


def shoot_frames(env, outdir, fps, w, h, crop_from=0.74, crop_to=0.40, crop_sec=2.2):
    """逐帧出画。两个坑都踩过：
    ① 不能用 page.screenshot —— 无头 Chromium 节流 rAF，截到的是上一次"已呈现"的旧帧；
    ② 不能把参数用 evaluate 的第二实参传进去让 IIFE 接 —— 实测会被**静默丢掉**
       （jaw 0 → 0.95 画面纹丝不动，差点被读成"嘴是死的"，正是台账 P1 那一型）。
    一律拼字符串 + `_png()` 直读像素。

    推镜：cropH 从 crop_from 缓动到 crop_to（前 crop_sec 秒），之后定住。
    短剧对白本来就该是中近景；屏上那个开口只有 8px 高时，牙必然糊成虚线 —— 推近才看得清。
    """
    os.makedirs(outdir, exist_ok=True)
    paths = []
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, executable_path=find_chrome(), args=[
            '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
            '--allow-file-access-from-files', '--disable-web-security'])
        pg = br.new_page(viewport={'width': w + 40, 'height': h + 40}, device_scale_factor=1)
        pg.goto('file:///' + LAB.replace('\\', '/').replace(' ', '%20'), wait_until='load')
        pg.wait_for_function('window.__DH2D_READY === true', timeout=20000)
        pg.evaluate('var c=document.getElementById("dh2d");'
                    'c.style.width="%dpx"; c.style.height="%dpx";'
                    'window.GBT_DH2D.setState("speak"); window.GBT_DH2D._frozen(true);' % (w, h))
        n = len(env)
        for i in range(n):
            t = i / float(fps)
            k = 0.0 if crop_sec <= 0 else min(1.0, t / float(crop_sec))
            k = 1.0 - (1.0 - k) ** 3                      # ease-out
            crop = crop_from + (crop_to - crop_from) * k
            jaw = float(env[i]) * 0.92
            breath = 0.5 + 0.5 * float(np.sin(t * 1.9))
            sway = float(np.sin(t * 0.5)) * 4.2
            tilt = float(np.sin(t * 0.33)) * 0.012
            nod = float(np.sin(t * 0.71)) * 0.005
            pg.evaluate('window.GBT_DH2D.setCrop(%f);' % crop
                        + 'window.GBT_DH2D.set({jaw:%f,blink:0,breath:%f,sway:%f,tilt:%f,nod:%f})'
                        % (jaw, breath, sway, tilt, nod))
            url = pg.evaluate('window.GBT_DH2D._png(%f)' % t)
            p = os.path.join(outdir, 'f%04d.png' % i)
            with open(p, 'wb') as f:
                f.write(base64.b64decode(url.split(',', 1)[1]))
            paths.append(p)
        br.close()
    return paths


def measure(paths, mouth_box, face_box):
    """读数：嘴区亮度（张嘴变暗）、脸区锐度、帧间差分平滑度。"""
    lum_mouth, lum_face, lap = [], [], []
    prev = None
    diffs = []
    for p in paths:
        im = Image.open(p).convert('L')
        a = np.asarray(im, dtype=np.float32)
        lum_mouth.append(float(a[mouth_box[1]:mouth_box[3], mouth_box[0]:mouth_box[2]].mean()))
        f = a[face_box[1]:face_box[3], face_box[0]:face_box[2]]
        lum_face.append(float(f.mean()))
        g = f[1:-1, 1:-1] * 4 - f[:-2, 1:-1] - f[2:, 1:-1] - f[1:-1, :-2] - f[1:-1, 2:]
        lap.append(float(g.var()))
        if prev is not None:
            diffs.append(float(np.abs(a - prev).mean()))
        prev = a
    return np.array(lum_mouth), np.array(lum_face), np.array(lap), np.array(diffs)


def corr_lag(a, b, maxlag=12):
    """a=嘴区亮度（张嘴变暗 ⇒ 取负），b=音频包络。返回各延迟的相关系数。"""
    best = (-2, 0)
    out = {}
    for lag in range(-maxlag, maxlag + 1):
        if lag >= 0:
            x, y = -a[:len(a) - lag or None], b[lag:]
        else:
            x, y = -a[-lag:], b[:len(b) + lag]
        n = min(len(x), len(y))
        x, y = x[:n], y[:n]
        if n < 8 or x.std() < 1e-6 or y.std() < 1e-6:
            continue
        c = float(np.corrcoef(x, y)[0, 1])
        out[str(lag)] = round(c, 4)
        if c > best[0]:
            best = (c, lag)
    return best, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audio', default=os.path.join(ROOT, 'holo_pet_w3', 'voice-theater',
                                                    'assets', 'voice-greet-zh-tw.mp3'))
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--out', default=os.path.join(ROOT, 'outputs', 'dh2d'))
    ap.add_argument('--limit', type=int, default=0, help='只做前 N 帧（试跑用）')
    ap.add_argument('--keep-frames', action='store_true', help='保留逐帧 PNG（默认出片后删）')
    ap.add_argument('--audit-only', action='store_true', help='不重渲，只对已有帧复算读数并写收据')
    ap.add_argument('--w', type=int, default=720)
    ap.add_argument('--h', type=int, default=1500)
    ap.add_argument('--crop-from', type=float, default=0.74, help='起手取景（越大越远）')
    ap.add_argument('--crop-to', type=float, default=0.40, help='推镜后取景（越小越近）')
    ap.add_argument('--crop-sec', type=float, default=2.2, help='推镜时长（秒）')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    wav = os.path.join(a.out, '_tmp.wav')
    env, dur = envelope(a.audio, a.fps, wav)
    if a.limit:
        env = env[:a.limit]
        dur = len(env) / float(a.fps)

    # 读数盒子按**推镜结束后的取景**算（推镜途中取景在变，固定盒子会量错对象 —— P1 那一型）
    W, H = a.w, a.h
    CROP = a.crop_to * 1190.0
    scale = H / CROP
    viewW = CROP * (W / float(H))
    x0 = 368.0 - viewW / 2.0
    mx, my = (362.0 - x0) * scale, 170.0 * scale
    mouth_box = (int(mx - 0.085 * W), int(my - 0.030 * H), int(mx + 0.085 * W), int(my + 0.045 * H))
    face_box = (max(0, int(mx - 0.24 * W)), max(0, int(my - 0.17 * H)), int(mx + 0.24 * W), int(my + 0.13 * H))

    frames_dir = os.path.join(a.out, 'frames')
    if a.audit_only:
        paths = sorted(os.path.join(frames_dir, f) for f in os.listdir(frames_dir)
                       if f.startswith('f') and f.endswith('.png'))
        if not paths:
            raise SystemExit('--audit-only 需要已经渲好的帧，%s 里没有' % frames_dir)
    else:
        if os.path.isdir(frames_dir):
            shutil.rmtree(frames_dir)
        paths = shoot_frames(env, frames_dir, a.fps, W, H,
                             a.crop_from, a.crop_to, a.crop_sec)
    # 推镜段取景在动，只对**定住之后**的帧做读数（否则盒子对不上画面）
    skip = int(round(a.crop_sec * a.fps)) if a.crop_sec > 0 else 0
    lm, lf, lap, diffs = measure(paths[skip:], mouth_box, face_box)
    (best_c, best_lag), all_c = corr_lag(lm, np.resize(env, len(paths))[skip:])

    mp4 = os.path.join(a.out, 'dh2d-speak.mp4')
    if not a.audit_only:
        cmd = [FFMPEG, '-y', '-v', 'error', '-framerate', str(a.fps),
               '-i', os.path.join(frames_dir, 'f%04d.png'), '-i', a.audio,
               '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium',
               '-c:a', 'aac', '-b:a', '160k', '-shortest', mp4]
        subprocess.run(cmd, check=True)

    rec = {
        'ok': True,
        'size': [W, H],
        'audio': a.audio,
        'audio_sec': round(dur, 2),
        'fps': a.fps,
        'frames': len(paths),
        'mp4': mp4,
        'mp4_bytes': os.path.getsize(mp4) if os.path.exists(mp4) else -1,
        '画质_脸区Laplacian方差': {'mean': round(float(lap.mean()), 1),
                                   'p10': round(float(np.percentile(lap, 10)), 1)},
        '动作_帧间差分': {'median': round(float(np.median(diffs)), 3),
                          'max': round(float(diffs.max()), 3),
                          'max_over_median': round(float(diffs.max() / max(1e-6, np.median(diffs))), 2)},
        '嘴对齐': {'best_r': round(best_c, 4), 'best_lag_frames': best_lag,
                   'mouth_lum_range': [round(float(lm.min()), 1), round(float(lm.max()), 1)],
                   'env_mean': round(float(env.mean()), 4)},
        'corr_by_lag': all_c,
    }
    try:
        os.remove(wav)
    except OSError:
        pass
    with open(os.path.join(a.out, 'receipt.json'), 'w', encoding='utf-8') as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    print('<<<GBT-DH2D-VIDEO>>>')
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    if rec['嘴对齐']['best_r'] < 0.25:
        sys.exit(2)


if __name__ == '__main__':
    main()






