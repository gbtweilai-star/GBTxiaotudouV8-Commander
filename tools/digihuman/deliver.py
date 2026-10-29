# -*- coding: utf-8 -*-
"""deliver.py — 把 SadTalker 的原始输出装配成**可交付件**，并当场量三条口径。

## 为什么收敛成一件
SadTalker 自己写出的是 `cv2.VideoWriter(mp4v)` 的 mp4（画质/兼容性都一般），
交付前还要：① 只编一次的高质量 x264（避免"编两次掉两次"）② 中文硬字幕 ③ 三条口径读数。
这三步以前散在会话里手敲 —— 手敲就会漏、就会两次编码。本件把三步焊死成一条命令。

## 三个动作
1. **重编**：libx264 · crf 16 · preset slow · yuv420p · aac 192k（**只编这一次**）
2. **烧字幕**：srt 先搬到 ASCII 暂存（本仓路径带中文，ffmpeg 的 subtitles 过滤器不认），
   字体 `Microsoft YaHei`，描边 1，底部居中
3. **量口径**：调 `qc-video.py --track`（逐帧关键点算 MAR）出一条回执

## 用法
  py -3.14 tools/digihuman/deliver.py --raw outputs/dh-talk/v3-gfpgan-motion.mp4 \
      --srt outputs/voice-studio/short-video/dialogue.srt \
      --out outputs/dh-talk/dh-talk-v3.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path(tempfile.gettempdir()) / 'gbt-deliver'


def _ffprobe(p: Path) -> dict:
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                        'stream=codec_type,width,height,nb_frames,r_frame_rate:format=duration,bit_rate',
                        '-of', 'json', str(p)], capture_output=True, text=True)
    return json.loads(r.stdout or '{}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', required=True, help='SadTalker 原始输出 mp4')
    ap.add_argument('--srt', default='', help='要烧的中文字幕（空=不烧）')
    ap.add_argument('--out', required=True, help='交付件落点')
    ap.add_argument('--crf', type=int, default=16)
    ap.add_argument('--qc', default='', help='三条口径回执 json 落点')
    ap.add_argument('--qc-python', default='',
                    help='跑量具用哪个解释器（默认 .venv-sadtalker，那里才有 cv2/numpy）')
    ap.add_argument('--no-qc', action='store_true')
    a = ap.parse_args()

    raw, out = Path(a.raw), Path(a.out)
    if not raw.is_file():
        print(json.dumps({'ok': False, 'why': '原始件不在：%s' % raw}, ensure_ascii=False))
        return 2
    STAGE.mkdir(parents=True, exist_ok=True)
    info = _ffprobe(raw)
    v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), {})
    w, h = int(v.get('width') or 0), int(v.get('height') or 0)
    if not w or not h:
        print(json.dumps({'ok': False, 'why': '读不到分辨率'}, ensure_ascii=False))
        return 3

    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['ffmpeg', '-y', '-v', 'error', '-i', str(raw)]
    vf = []
    if h % 2 or w % 2:                       # libx264 要偶数边
        vf.append('scale=%d:%d' % (w - w % 2, h - h % 2))
    if a.srt:
        srt = Path(a.srt)
        if not srt.is_file():
            print(json.dumps({'ok': False, 'why': '字幕不在：%s' % srt}, ensure_ascii=False))
            return 4
        srt_ascii = STAGE / 'sub.srt'
        shutil.copyfile(srt, srt_ascii)
        style = ('FontName=Microsoft YaHei,FontSize=22,PrimaryColour=&H00FFFFFF,'
                 'OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=18')
        # 反斜杠一律正斜杠；'=' ':' 在 filter 里要转义
        p = str(srt_ascii).replace('\\', '/')
        vf.append("subtitles='%s':force_style='%s'" % (p.replace(':', r'\:'), style))
    if vf:
        cmd += ['-vf', ','.join(vf)]
    cmd += ['-c:v', 'libx264', '-crf', str(a.crf), '-preset', 'slow', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.is_file():
        print(json.dumps({'ok': False, 'why': 'ffmpeg 失败', 'returncode': r.returncode,
                          'stderr': (r.stderr or '')[-600:], 'cmd': ' '.join(cmd)},
                         ensure_ascii=False))
        return 5

    rep = {'ok': True, 'raw': str(raw), 'out': str(out),
           'raw_bytes': raw.stat().st_size, 'out_bytes': out.stat().st_size,
           'crf': a.crf, 'srt': a.srt or None, 'probe': _ffprobe(out)}
    print(json.dumps(rep, ensure_ascii=False, indent=1))

    if not a.no_qc:
        qc_out = Path(a.qc) if a.qc else Path('state/digital_human/qc-deliver.json')
        # 🔴 量具必须用**装了 cv2/numpy 的那个解释器**（本仓是 .venv-sadtalker），
        #    不能用调用本件的 sys.executable —— 3.14 那边没有 cv2，
        #    第一版就是这里静默失败：capture_output 一夹，回执里只剩「没有 qc 块」，看不出为什么。
        py = a.qc_python or str(ROOT / '.venv-sadtalker' / 'Scripts' / 'python.exe')
        if not Path(py).is_file():
            py = sys.executable
        aud = STAGE / 'audio.wav'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(out), '-vn',
                        '-ac', '1', '-ar', '16000', str(aud)], capture_output=True)
        q = subprocess.run([py, str(ROOT / 'tools' / 'digihuman' / 'qc-video.py'),
                            '--video', str(out), '--audio', str(aud),
                            '--source', str(ROOT / 'outputs' / 'ref' / 'face-tight.png'),
                            '--track', '--out', str(qc_out)], capture_output=True, text=True)
        if not qc_out.is_file():
            print(json.dumps({'qc': 'failed', 'python': py, 'returncode': q.returncode,
                              'stderr': (q.stderr or '')[-500:],
                              'stdout': (q.stdout or '')[-300:]}, ensure_ascii=False))
        if qc_out.is_file():
            q = json.loads(qc_out.read_text(encoding='utf-8'))
            print(json.dumps({'qc': q}, ensure_ascii=False, indent=1))
            # 交付即记账（主人令：「每次那里问题 那里踩坑 方向是那里 都要记入到编排账本」）
            # 判据写死在这里：三条达标线不绿也照记，且判决里明说没达标 —— 不许只记绿的
            try:
                _orch(ROOT / 'tools' / 'codex-scripts' / 'orch-note.py', py,
                      'dh.deliver.%s' % out.stem, _verdict(q, out))
            except Exception as e:                                 # noqa: BLE001
                print(json.dumps({'orch_note': 'failed', 'why': str(e)[:200]},
                                 ensure_ascii=False))
    return 0


def _verdict(q: dict, out: Path) -> str:
    """把三条口径压成一句能进账本的话（带达标线判定，不粉饰）。"""
    sx = (q.get('画质清晰') or {}).get('ratio')
    mv = (q.get('动作自然') or {}).get('head_move_mean')
    mo = q.get('语音嘴对齐') or {}
    r, lag, neg = mo.get('r_peak'), mo.get('lag_frames'), mo.get('neg_control_r')
    ok = (sx is not None and sx >= 0.90 and mv is not None and mv >= 0.15
          and r is not None and r >= 0.60 and lag is not None and abs(lag) <= 2
          and neg is not None and neg <= 0.15)
    return ('交付 %s：画质 ratio=%s（线 0.90）· 动作 head_move=%s（线 0.15）· '
            '嘴 r=%s lag=%s帧 负控=%s（线 r≥0.60 |lag|≤2 负控≤0.15）⇒ %s'
            % (out.name, sx, mv, r, lag, neg, '三条全绿' if ok else '未达标，不交付'))


def _orch(script: Path, py: str, job_id: str, verdict: str) -> None:
    r = subprocess.run([py, str(script), 'add', '--job-id', job_id,
                        '--verdict', verdict], capture_output=True, text=True)
    print(json.dumps({'orch_note': 'ok' if r.returncode == 0 else 'failed',
                      'explain': (r.stdout or r.stderr or '')[:300]}, ensure_ascii=False))


if __name__ == '__main__':
    sys.exit(main())
