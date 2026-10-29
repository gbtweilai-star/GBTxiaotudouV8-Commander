# -*- coding: utf-8 -*-
"""shortvideo-demo.py — 一条命令跑完「AI 短剧」的一个镜头，产物落**抽屉树**并登记许可。

这一步把之前手工串的那条链固化成**可复跑的一条命令**：
    台词 → 配音(cast/say) → 精确时间轴(timeline) → 2.5D 数字人出画 → 烧字幕 → 登记许可

为什么单独一个件（而不是继续手工敲）：
  · 手工那条链的产物散在 outputs/ 里，**没有进 `projects/<方向>/<格>/`**，门的汇总看不见它；
  · 家规第 2 条：进成品格的素材必须有许可记录 —— 自产的也要**如实写自有**；
  · 运行时要报真读数（配音时长、对齐 r、帧数），不能只说"跑完了"。

用法：
  py -3.14 tools/codex-scripts/shortvideo-demo.py --work yuting --who 女主 \
      --lines "雨停之前，我一定要走到那栋楼。|你连伞都没带，走到一半就会后悔。" \
      --crop-to 0.40
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys

# ── 编码守门（encoding-guard 要求）：不带 -X utf8 调用时不许静默输出空 ──
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

FFMPEG = shutil.which('ffmpeg') or ''
if not FFMPEG:
    _b = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WinGet', 'Packages')
    for _d in sorted(os.listdir(_b), reverse=True) if os.path.isdir(_b) else []:
        if _d.startswith('Gyan.FFmpeg'):
            _p = Path(_b) / _d
            for _s in _p.iterdir() if _p.is_dir() else []:
                _e = _s / 'bin' / 'ffmpeg.exe'
                if _e.exists():
                    FFMPEG = str(_e)
                    break


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _house_name(kind, work, ext):
    """合 media_flow 的命名规则：`YYYYMMDD-<方向>-<作品>-rehearsal.ext`（方向用连字符）。"""
    import time as _t
    return '%s-%s-%s-rehearsal.%s' % (_t.strftime('%Y%m%d'), kind.replace('_', '-'), work, ext)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='demo', help='作品名（进文件名）')
    ap.add_argument('--who', default='', help='角色名（走 cast 台账取音色）')
    ap.add_argument('--voice', default='', help='显式音色（盖过 cast）')
    ap.add_argument('--lines', required=True, help='台词，用 | 分隔')
    ap.add_argument('--crop-to', type=float, default=0.40)
    ap.add_argument('--crop-from', type=float, default=0.74)
    ap.add_argument('--crop-sec', type=float, default=2.2)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--w', type=int, default=720)
    ap.add_argument('--h', type=int, default=1500)
    ap.add_argument('--wrap', type=int, default=13)
    ap.add_argument('--scratch', default=str(ROOT / '.scratch' / 'shortvideo-demo'))
    a = ap.parse_args()

    lines = [s.strip() for s in a.lines.split('|') if s.strip()]
    if not lines:
        raise SystemExit('--lines 空')
    scratch = Path(a.scratch)
    if scratch.is_dir():
        shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True, exist_ok=True)

    vs = _load('vs', 'gbt_allinone/voice_studio.py')
    dv = _load('dv', 'tools/codex-scripts/dh2d-video.py')

    rec = {'ok': False, 'work': a.work, 'who': a.who or None, 'lines': lines, 'steps': {}}

    # ① 配音
    say = vs.say(lines=lines, who=a.who, voice=a.voice,
                 concat=str(scratch / 'dialogue.wav'))
    rec['steps']['say'] = {k: say.get(k) for k in ('ok', 'engine', 'voice', 'voice_src', 'n', 'concat', 'status', 'why')}
    if not say.get('ok'):
        print('<<<GBT-SHORTVIDEO>>>')
        print(json.dumps(rec, ensure_ascii=False, indent=1))
        raise SystemExit(2)
    wav = Path(say['concat'])
    made = [m['path'] for m in say['made']]
    rec['steps']['say']['durations'] = [m['dur'] for m in say['made']]

    # ② 精确时间轴（生成的对白用 timeline，不用 align 猜边界）
    tl = vs.timeline(paths=made, lines=lines, wrap=a.wrap,
                     out=str(scratch / 'dialogue.srt'))
    rec['steps']['timeline'] = {k: tl.get(k) for k in ('ok', 'n', 'total_sec', 'out', 'bytes', 'status')}
    if not tl.get('ok'):
        print('<<<GBT-SHORTVIDEO>>>')
        print(json.dumps(rec, ensure_ascii=False, indent=1))
        raise SystemExit(2)

    # ③ 出画（2.5D 数字人，嘴吃这句真配音的包络）
    frames = scratch / 'frames'
    paths = dv.shoot_frames(dv.envelope(str(wav), a.fps, str(scratch / '_t.wav'))[0],
                            str(frames), a.fps, a.w, a.h, a.crop_from, a.crop_to, a.crop_sec)
    silent = scratch / 'silent.mp4'
    subprocess.run([FFMPEG, '-y', '-v', 'error', '-framerate', str(a.fps),
                    '-i', str(frames / 'f%04d.png'), '-i', str(wav),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18',
                    '-c:a', 'aac', '-b:a', '160k', '-shortest', str(silent)], check=True)
    rec['steps']['render'] = {'ok': silent.exists(), 'frames': len(paths),
                              'bytes': silent.stat().st_size if silent.exists() else -1,
                              'crop': [a.crop_from, a.crop_to, a.crop_sec]}

    # ④ 烧字幕 + 钢印
    drawer = ROOT / 'projects' / 'short-video' / '03-raw'
    drawer.mkdir(parents=True, exist_ok=True)
    mp4 = drawer / _house_name('short-video', a.work, 'mp4')
    srt = drawer / _house_name('short-video', a.work, 'srt')
    wav_out = drawer / _house_name('short-video', a.work, 'wav')
    # 烧字幕 + 钢印。
 # Windows 下 `subtitles=C:/...` 会被 ffmpeg 把盘符冒号当成选项分隔符（报
    #    "Unable to parse original_size"）⇒ **切到 srt 所在目录用相对文件名**，别去转义冒号。
    subprocess.run([FFMPEG, '-y', '-v', 'error', '-i', str(silent),
                    '-vf', "subtitles=dialogue.srt:force_style='FontName=Microsoft YaHei,FontSize=17,"
                           "Outline=2,Shadow=0,MarginV=34'",
                    '-c:a', 'copy',
                    '-metadata', 'title=GBT-V8 short-video %s' % a.work,
                    '-metadata', 'artist=GBT小土豆V8',
                    '-metadata', 'comment=开发者：自由的风 · GBT小土豆V8',
                    str(mp4)], check=True, cwd=str(scratch))
    shutil.copy2(scratch / 'dialogue.srt', srt)
    shutil.copy2(wav, wav_out)
    rec['steps']['burn'] = {'ok': mp4.exists(), 'mp4': str(mp4), 'mp4_bytes': mp4.stat().st_size,
                            'srt': str(srt), 'srt_bytes': srt.stat().st_size,
                            'wav': str(wav_out), 'wav_bytes': wav_out.stat().st_size}

    # ⑤ 登记许可（自产 ⇒ 如实写自有，不替别人编来源）
    lic = []
    for f, kind in ((mp4, 'video'), (wav_out, 'audio'), (srt, 'text')):
        r = vs.__dict__ and None
        try:
            from gbt_allinone.tools.media_license import run as lic_run
            r = lic_run(op='register', path=str(f.relative_to(ROOT)),
                        source='GBT小土豆V8 本机自产（2.5D 数字人 + edge-tts）',
                        license='自有（作者本人）' if kind != 'audio' else '自有合成（TTS 引擎：edge-tts）',
                        note='shortvideo-demo 一条命令产出')
        except Exception as e:                                        # noqa: BLE001
            r = {'ok': False, 'why': '%s: %s' % (type(e).__name__, str(e)[:120])}
        lic.append({'file': str(f.name), 'result': {k: r.get(k) for k in ('ok', 'status', 'why')} if isinstance(r, dict) else r})
    rec['steps']['license'] = lic

    # ⑥ 回读成片（真读数）
    try:
        st = dv.subprocess.run([str(Path(FFMPEG).with_name('ffprobe.exe')), '-v', 'error',
                                '-show_entries', 'format=duration,size:stream=codec_name,width,height',
                                '-of', 'json', str(mp4)], capture_output=True, timeout=60)
        rec['probe'] = json.loads(st.stdout.decode('utf-8', 'replace') or '{}')
    except Exception as e:                                            # noqa: BLE001
        rec['probe'] = {'未读到': '%s: %s' % (type(e).__name__, str(e)[:120])}

    rec['ok'] = all([rec['steps']['say'].get('ok'), rec['steps']['timeline'].get('ok'),
                     rec['steps']['render'].get('ok'), rec['steps']['burn'].get('ok')])
    print('<<<GBT-SHORTVIDEO>>>')
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    if not rec['ok']:
        sys.exit(2)


if __name__ == '__main__':
    main()
