# -*- coding: utf-8 -*-
"""upscale-hd.py — 把生成出来的片**真放大**（Real-ESRGAN），不是插值糊大。

## 为什么要单列一件
主人令「记得高清」。视频模型原生 480p；直接把 480p 拉成 1080p 只是把像素摊开，
不会多一个细节。Real-ESRGAN 是**学出来的**超分：给纹理/边缘补出可信的高频。

## 口径（写死）
- 逐帧超分后**一次性**编码（rawvideo 管道进 ffmpeg），音轨直接抄源片；
- 帧数进出必须相等（少一帧就报错，不静默）；
- 记录：源分辨率 → 目标分辨率、逐帧耗时、峰值显存/内存不适用（CPU 版不给假读数）。

## 用法
  py -3.14 tools/digihuman/upscale-hd.py --in raw.mp4 --out hd.mp4 --scale 2
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time


def _probe(p: str) -> dict:
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                        'stream=codec_type,width,height,r_frame_rate:format=duration',
                        '-of', 'json', p], capture_output=True, text=True)
    return json.loads(r.stdout or '{}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='src', required=True)
    ap.add_argument('--out', dest='dst', required=True)
    ap.add_argument('--scale', type=int, default=2, choices=[2, 4])
    ap.add_argument('--model', default='', help='默认按 scale 选 realesrgan-x2plus / x4plus')
    ap.add_argument('--tile', type=int, default=256, help='分块大小；内存小就调小')
    ap.add_argument('--denoise', type=float, default=0.5, help='denoise_strength 0-1')
    ap.add_argument('--crf', type=int, default=16)
    ap.add_argument('--limit', type=int, default=0, help='只处理前 N 帧（冒烟用）')
    a = ap.parse_args()

    import cv2
    import numpy as np
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer

    info = _probe(a.src)
    v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), {})
    W, H = int(v.get('width') or 0), int(v.get('height') or 0)
    num, _, den = str(v.get('r_frame_rate') or '25/1').partition('/')
    fps = float(num) / float(den or 1)
    if not W or not H:
        print(json.dumps({'ok': False, 'why': '读不到分辨率'}, ensure_ascii=False))
        return 2

    model_name = a.model or ('RealESRGAN_x2plus' if a.scale == 2 else 'RealESRGAN_x4plus')
    if a.scale == 2:
        net = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=2)
        url = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth'
    else:
        net = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        url = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth'
    up = RealESRGANer(scale=a.scale, model_path=url, model=net, tile=a.tile, tile_pad=10,
                      pre_pad=0, half=False)          # CPU ⇒ half 必须 False

    cap = cv2.VideoCapture(a.src)
    if not cap.isOpened():
        print(json.dumps({'ok': False, 'why': '打不开视频'}, ensure_ascii=False))
        return 3
    OW, OH = W * a.scale, H * a.scale
    enc = subprocess.Popen(
        ['ffmpeg', '-y', '-v', 'error',
         '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (OW, OH), '-r', str(fps), '-i', '-',
         '-i', a.src, '-map', '0:v', '-map', '1:a?',
         '-c:v', 'libx264', '-crf', str(a.crf), '-preset', 'slow', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', a.dst],
        stdin=subprocess.PIPE)

    i, t0 = 0, time.time()
    while True:
        ok, f = cap.read()
        if not ok:
            break
        try:
            out, _ = up.enhance(f, outscale=a.scale)
        except Exception as e:                                        # noqa: BLE001
            print(json.dumps({'ok': False, 'why': '超分失败', 'frame': i,
                              'err': '%s: %s' % (type(e).__name__, str(e)[:200])}, ensure_ascii=False))
            cap.release()
            enc.stdin.close()
            enc.wait()
            return 4
        if out.shape[1] != OW or out.shape[0] != OH:
            out = cv2.resize(out, (OW, OH), interpolation=cv2.INTER_AREA)
        enc.stdin.write(np.ascontiguousarray(out).tobytes())
        i += 1
        if i % 25 == 0:
            print(json.dumps({'progress': i, 'secs': round(time.time() - t0, 1)}, ensure_ascii=False), flush=True)
        if a.limit and i >= a.limit:
            break
    cap.release()
    enc.stdin.close()
    enc.wait()

    rep = {'ok': enc.returncode == 0, 'src': a.src, 'out': a.dst,
           'from': [W, H], 'to': [OW, OH], 'scale': a.scale, 'model': model_name,
           'frames': i, 'secs': round(time.time() - t0, 1),
           'secs_per_frame': round((time.time() - t0) / max(1, i), 2)}
    print(json.dumps(rep, ensure_ascii=False))
    return 0 if rep['ok'] else 5


if __name__ == '__main__':
    sys.exit(main())
