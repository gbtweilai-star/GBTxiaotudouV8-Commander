# -*- coding: utf-8 -*-
"""body-sway.py — 给**已经生成好的**说话人视频加一层「站着不倒」的身体微动。

## 为什么要有这一件（主人 2026-10-20：「我要的是全身」）
SadTalker 只驱动**头与脸**：身体是原图被头部姿态带着做的整体形变。
所以全身片子里头在说、身子像雕塑。本机没有 GPU、也没有 EchoMimic / AniPortrait
这类"全身骨骼"模型（现读：third_party 里没有，nvidia-smi 不存在），
所以能在这台机器上做到的"身体也在动"只有一种诚实做法 ——
**把整帧按物理学上站得住的方式轻轻推一下**：呼吸（纵向微胀缩）+ 重心左右
（绕脚底的极慢横摆）+ 极小的整体旋转。

## 它不是骨骼动画（这条要写死在交付话术里）
它动的幅度是 **0.x%** 量级：看得见"活着"，永远不会挥手、不会走路。
真要胳膊腿各自动，必须换带姿态驱动的视频模型（云上花钱 / 换 GPU 机）。

## 三个旋钮（默认值 = 站在那儿说话的人，不是跳舞的人）
  --breathe  纵向胀缩幅度（占幅高比）默认 0.004
  --shift    重心横摆幅度（占幅宽比）  默认 0.003
  --rot      整体旋转（度）            默认 0.15
  --breath-hz 呼吸频率 默认 0.22（≈13 次/分）  --shift-hz 重心频率 默认 0.09

## 用法
  py -3.14 tools/digihuman/body-sway.py --in fullbody-v4.mp4 --out fullbody-v4-sway.mp4
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys

import numpy as np


def _probe(p: str) -> dict:
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                        'stream=codec_type,width,height,r_frame_rate:format=duration',
                        '-of', 'json', p], capture_output=True, text=True)
    return json.loads(r.stdout or '{}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='src', required=True)
    ap.add_argument('--out', dest='dst', required=True)
    ap.add_argument('--breathe', type=float, default=0.004)
    ap.add_argument('--shift', type=float, default=0.003)
    ap.add_argument('--rot', type=float, default=0.15)
    ap.add_argument('--breath-hz', type=float, default=0.22, dest='breathe_hz')
    ap.add_argument('--shift-hz', type=float, default=0.09, dest='shift_hz')
    ap.add_argument('--crf', type=int, default=16)
    ap.add_argument('--report', default='')
    a = ap.parse_args()

    import cv2

    info = _probe(a.src)
    v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), {})
    W, H = int(v.get('width') or 0), int(v.get('height') or 0)
    fps_s = str(v.get('r_frame_rate') or '25/1')
    num, _, den = fps_s.partition('/')
    fps = float(num) / float(den or 1)
    if not W or not H:
        print(json.dumps({'ok': False, 'why': '读不到分辨率'}, ensure_ascii=False))
        return 2

    cap = cv2.VideoCapture(a.src)
    if not cap.isOpened():
        print(json.dumps({'ok': False, 'why': '打不开视频'}, ensure_ascii=False))
        return 3

    # 单次编码：rawvideo 管道进 ffmpeg，音轨直接抄源片的
    enc = subprocess.Popen(
        ['ffmpeg', '-y', '-v', 'error',
         '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', str(fps), '-i', '-',
         '-i', a.src, '-map', '0:v', '-map', '1:a?',
         '-c:v', 'libx264', '-crf', str(a.crf), '-preset', 'slow', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', a.dst],
        stdin=subprocess.PIPE)

    cx, cy = W / 2.0, float(H)                      # 支点放在脚底中线：头动得最多、脚几乎不动
    i = 0
    prev = None
    diffs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        t = i / fps
        br = math.sin(2 * math.pi * a.breathe_hz * t)
        sh = math.sin(2 * math.pi * a.shift_hz * t + 0.8)
        rot = math.radians(a.rot) * sh
        sy = 1.0 + a.breathe * br
        shear = (a.shift * W / H) * sh * 0.5    # 顶部横移，底部不动
        c, s = math.cos(rot), math.sin(rot)
        # 绕 (cx,cy) 旋转 + 纵向胀缩 + 顶部横移（shear）
        M = np.array([[c * 1.0, -s + shear, 0.0],
                      [s, c * sy, 0.0]], dtype=np.float64)
        T1 = np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]], dtype=np.float64)
        T2 = np.array([[1, 0, cx], [0, 1, cy], [0, 0, 1]], dtype=np.float64)
        M3 = np.vstack([M, [0, 0, 1]]) @ T1
        M3 = T2 @ M3
        warp = M3[:2]
        out = cv2.warpAffine(f, warp, (W, H), flags=cv2.INTER_LANCZOS4,
                             borderMode=cv2.BORDER_REPLICATE)
        if prev is not None:
            diffs.append(float(np.abs(out.astype(np.int16) - prev.astype(np.int16)).mean()))
        prev = out
        enc.stdin.write(out.tobytes())
        i += 1

    cap.release()
    enc.stdin.close()
    enc.wait()

    rep = {'ok': enc.returncode == 0, 'src': a.src, 'out': a.dst, 'frames': i,
           'size': [W, H], 'fps': fps,
           'breathe': a.breathe, 'shift': a.shift, 'rot_deg': a.rot,
           'breathe_hz': a.breathe_hz, 'shift_hz': a.shift_hz,
           'frame_diff_mean': round(float(np.mean(diffs)), 4) if diffs else None,
           'note': ('**不是骨骼动画**：只加呼吸/重心/极小旋转（0.x% 量级）。'
                    '要胳膊腿各自动，必须换带姿态驱动的视频模型。')}
    if a.report:
        from pathlib import Path
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(rep, ensure_ascii=False))
    return 0 if rep['ok'] else 4


if __name__ == '__main__':
    sys.exit(main())
