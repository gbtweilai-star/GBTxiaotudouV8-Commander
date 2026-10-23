# -*- coding: utf-8 -*-
"""talk-photo.py — 以图生视频：一张照片 + 一段配音 ⇒ 说话视频（本地 SadTalker，零账号）。

## 为什么是这个做法（P7 之后的结论）
主人 2026-10-19 逐字："数字人你就不会以图生视频的形式实现动作自然口型对齐吗这么简单的事情你搞一天"。
对。之前在用"浏览器里实时画 2.5D"的路子，那条路本质是**我自己造嘴**，
无论怎么调都只是贴纸 vs 面瘫的二选一。以图生视频是让**模型**从她这张脸生成动作与口型，
不存在"我造嘴"这件事。

## 依赖（本机已装，独立 3.10 环境，不动主仓解释器）
  .venv-sadtalker/            uv venv --python 3.10
  third_party/SadTalker/      上游仓库（--depth 1）
  checkpoints/                mapping_00109/00229 + SadTalker_V0.0.2_256.safetensors + BFM_Fitting
  ~/.cache/torch/hub/checkpoints/  2DFAN4 + s3fd（face_alignment 自己的权重）

## 用法
  py -3.14 tools/digihuman/talk-photo.py --check
  py -3.14 tools/digihuman/talk-photo.py --image outputs/ref/character-ref.png \
        --audio outputs/voice-studio/short-video/dialogue.wav --out outputs/dh-talk/line.wav.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV = ROOT / '.venv-sadtalker'
REPO = ROOT / 'third_party' / 'SadTalker'
CKPT = REPO / 'checkpoints'
OUTDIR = ROOT / 'outputs' / 'dh-talk'

NEED_CKPT = ['mapping_00109-model.pth.tar', 'mapping_00229-model.pth.tar',
             'SadTalker_V0.0.2_256.safetensors']
NEED_BFM = ['01_MorphableModel.mat', 'BFM09_model_info.mat', 'Exp_Pca.bin', 'facemodel_info.mat']
NEED_FA = ['2DFAN4-cd938726ad.zip', 's3fd-619a316812.pth']


def py() -> Path:
    p = VENV / 'Scripts' / 'python.exe'
    return p if p.is_file() else VENV / 'bin' / 'python'


def torch_hub() -> Path:
    base = os.environ.get('TORCH_HOME')
    if base:
        return Path(base) / 'hub' / 'checkpoints'
    return Path(os.environ.get('USERPROFILE') or Path.home()) / '.cache' / 'torch' / 'hub' / 'checkpoints'


def check() -> dict:
    """只查前置，不跑推理。缺什么就如实报缺 + 给出补齐的那一步。"""
    rec = {'ok': False, 'steps': {}}
    rec['steps']['venv'] = {'ok': py().is_file(), 'path': str(py())}
    rec['steps']['repo'] = {'ok': (REPO / 'inference.py').is_file()}
    miss = [n for n in NEED_CKPT if not (CKPT / n).is_file() or (CKPT / n).stat().st_size < 1024]
    rec['steps']['checkpoints'] = {'ok': not miss, 'missing': miss,
                                   'files': sorted(p.name for p in CKPT.glob('*') if p.is_file())}
    miss_bfm = [n for n in NEED_BFM if not (CKPT / 'BFM_Fitting' / n).is_file()]
    rec['steps']['bfm'] = {'ok': not miss_bfm, 'missing': miss_bfm}
    miss_fa = [n for n in NEED_FA if not (torch_hub() / n).is_file()]
    rec['steps']['face_alignment'] = {'ok': not miss_fa, 'missing': miss_fa, 'dir': str(torch_hub())}
    if py().is_file():
        try:
            r = subprocess.run([str(py()), '-c', 'import torch,numpy;print(torch.__version__, numpy.__version__)'],
                               capture_output=True, timeout=180)
            rec['steps']['imports'] = {'ok': r.returncode == 0,
                                       'out': (r.stdout or b'').decode('utf-8', 'replace').strip(),
                                       'err': (r.stderr or b'').decode('utf-8', 'replace').strip()[-400:]}
        except Exception as e:                                        # noqa: BLE001
            rec['steps']['imports'] = {'ok': False, 'err': '%s: %s' % (type(e).__name__, e)}
    rec['ok'] = all(v.get('ok') for v in rec['steps'].values())
    return rec


def ascii_root() -> Path:
    """OpenCV(Windows) 的 imread/imwrite **读不了非 ASCII 路径** —— 本仓路径带中文，
    上一发就是这么死的：`cv2.error: !_src.empty()` + `can't open/read file`。
    所以输入与工作目录一律先落到纯 ASCII 的临时根，跑完再把成片搬回来。"""
    p = Path(os.environ.get('GBT_TALK_TMP') or (Path(os.environ.get('TEMP', 'C:/')) / 'gbt-talk'))
    p.mkdir(parents=True, exist_ok=True)
    return p


def stage(src: Path) -> Path:
    """把输入复制到 ASCII 根下（同名不覆盖别的东西）。"""
    root = ascii_root()
    dst = root / src.name
    dst.write_bytes(src.read_bytes())
    return dst


def run(image: str, audio: str, out: str, still=True, preprocess='full', size=256,
        expression=1.0, enhancer='', timeout=7200) -> dict:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    img_ascii = stage(Path(image).resolve())
    aud_ascii = stage(Path(audio).resolve())
    work = ascii_root() / ('work_' + time.strftime('%H%M%S'))
    cmd = [str(py()), 'inference.py',
           '--driven_audio', str(aud_ascii),
           '--source_image', str(img_ascii),
           '--result_dir', str(work),
           '--checkpoint_dir', str(CKPT),
           '--size', str(size), '--batch_size', '1',
           '--expression_scale', str(expression),
           '--preprocess', preprocess, '--cpu']
    if still:
        cmd.append('--still')
    if enhancer:
        # GFPGAN 把人脸从 256 的生成态"修回照片级"—— 这是画质那一半的主要杠杆
        cmd += ['--enhancer', enhancer]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, timeout=timeout)
    log = ((r.stdout or b'') + (r.stderr or b'')).decode('utf-8', 'replace')
    (OUTDIR / 'last-run.log').write_text(log, encoding='utf-8')
    found = sorted(work.rglob('*.mp4'), key=lambda p: p.stat().st_mtime, reverse=True)
    rec = {'ok': r.returncode == 0 and bool(found), 'returncode': r.returncode,
           'secs': round(time.time() - t0, 1), 'cmd': ' '.join(cmd),
           'log_tail': log.strip().splitlines()[-25:], 'mp4': None, 'bytes': -1}
    if found:
        dst = Path(out)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.is_file():
            dst.unlink()
        found[0].replace(dst)
        rec['mp4'] = str(dst)
        rec['bytes'] = dst.stat().st_size
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--image', default=str(ROOT / 'outputs' / 'ref' / 'character-ref.png'))
    ap.add_argument('--audio', default=str(ROOT / 'outputs' / 'voice-studio' / 'short-video' / 'dialogue.wav'))
    ap.add_argument('--out', default=str(OUTDIR / 'talk.mp4'))
    ap.add_argument('--size', type=int, default=256)
    ap.add_argument('--preprocess', default='full')
    ap.add_argument('--expression', type=float, default=1.0)
    ap.add_argument('--enhancer', default='', help='gfpgan / RestoreFormer（空=不修脸）')
    ap.add_argument('--no-still', action='store_true')
    a = ap.parse_args()

    c = check()
    if a.check or not c['ok']:
        print('<<<GBT-TALK-CHECK>>>')
        print(json.dumps(c, ensure_ascii=False, indent=1))
        if a.check:
            sys.exit(0 if c['ok'] else 3)
        sys.exit(3)
    rec = run(a.image, a.audio, a.out, still=not a.no_still, preprocess=a.preprocess,
              size=a.size, expression=a.expression, enhancer=a.enhancer)
    (OUTDIR / 'last-run.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
    print('<<<GBT-TALK-RUN>>>')
    # 控制台是 GBK：日志里有非法字节时会 UnicodeEncodeError（上一发就崩在这里，不是推理崩）
    sys.stdout.write(json.dumps(rec, ensure_ascii=True, indent=1) + '\n')
    sys.exit(0 if rec['ok'] else 4)


if __name__ == '__main__':
    main()
