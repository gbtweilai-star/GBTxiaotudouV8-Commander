# -*- coding: utf-8 -*-
"""talk-claimer.py — 算力端领取器：从云插座的队列里领活儿，真跑 SadTalker，回填结果。

## 它在链条里的位置
主脑 ──ai_control──> 云插件（排队） ──claim──> **本文件（算力端）** ──本地 SadTalker──> 回填

所以"算力在哪"只决定**这个文件跑在哪台机器上**，主脑与云插件都不用改。

## 四种跑法（2026-10-19 补 daemon：主人令「继续推进实现」）
  py -3.14 tools/digihuman/talk-claimer.py --once --dry-run    # 只领不跑（看得到任务，不烧 CPU）
  py -3.14 tools/digihuman/talk-claimer.py --once              # 领一条、真跑、回填
  py -3.14 tools/digihuman/talk-claimer.py --loop --sleep 20   # 前台常驻轮询
  py -3.14 tools/digihuman/talk-claimer.py --daemon            # **无窗口常驻**（计划任务用它）

## 为什么要有 daemon 这一档
`--loop` 死掉就没人知道了：队列里的活儿会一直躺着，而主脑以为"已经派出去了"——
这就是本仓 P15「状态机停在门口不重试」。所以常驻那一档必须：
  · 每一轮都写**心跳**（state/digital_human/claimer-heartbeat.json，带 ts），
    心跳停 = 算力端没了，一眼能看出来；
  · 每一件事都**落日志**（state/digital_human/claimer.log），无窗口运行时也有账；
  · 单轮异常**不许把整条命丢掉**（catch 住、记原因、继续下一轮）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gbt_allinone.digital_human import op_cloud, op_render, op_task  # noqa: E402

STATEDIR = ROOT / 'state' / 'digital_human'
LOG = STATEDIR / 'claimer.log'
HEARTBEAT = STATEDIR / 'claimer-heartbeat.json'


def _emit(obj: dict) -> None:
    """一条回执：**同时**给 stdout 与日志（无窗口进程只有日志这条路）。"""
    line = json.dumps(obj, ensure_ascii=False)
    print(line, flush=True)
    try:
        STATEDIR.mkdir(parents=True, exist_ok=True)
        with LOG.open('a', encoding='utf-8') as f:
            f.write('%s %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%S'), line))
    except Exception:                                                 # noqa: BLE001
        pass                                                          # 日志写不进去不能拖垮领取


def _beat(**kw) -> None:
    try:
        STATEDIR.mkdir(parents=True, exist_ok=True)
        rec = {'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'pid': __import__('os').getpid(), **kw}
        HEARTBEAT.write_text(json.dumps(rec, ensure_ascii=False), encoding='utf-8')
    except Exception:                                                 # noqa: BLE001
        pass


def claim() -> dict:
    r = op_cloud(action='claim')
    job = (r.get('job') or None)
    return {'claim_ok': r.get('ok'), 'job': job, 'why': r.get('why'), 'depth': r.get('queue_depth')}


def drain(dry_run: bool) -> int:
    c = claim()
    _emit({'claim_ok': c['claim_ok'], 'depth': c['depth'],
           'job': (c['job'] or {}).get('task_id'), 'why': c['why']})
    job = c['job']
    if not job:
        return 0
    spec = {'image': job.get('image') or str(ROOT / 'outputs' / 'ref' / 'face-tight.png'),
            'audio': job.get('audio') or str(ROOT / 'outputs' / 'voice-studio' / 'short-video' / 'dialogue.wav'),
            'size': job.get('size') or 256}
    if dry_run:
        _emit({'dry_run': True, 'would_render': spec})
        return 0
    r = op_render(**spec)
    tid = r.get('task_id')
    _emit({'local_task': tid, 'status': r.get('status'), 'why': r.get('why')})
    if not tid:
        op_cloud(action='complete', task_id=job['task_id'], mp4='', why='算力端起不来: %s' % r.get('why'))
        return 1
    _beat(state='rendering', local_task=tid, cloud_task=job.get('task_id'))
    # 轮询本地任务直到出片（本机 CPU 很慢，耐心等）
    while True:
        st = op_task(task_id=tid)
        if st.get('status') in ('done', 'failed'):
            break
        _beat(state='rendering', local_task=tid, cloud_task=job.get('task_id'),
              local_status=st.get('status'))
        time.sleep(20)
    done = op_cloud(action='complete', task_id=job['task_id'],
                    mp4=st.get('mp4') or '', bytes_=st.get('bytes') or -1,
                    why=st.get('why') or '')
    _emit({'complete': done.get('ok'), 'cloud_status': done.get('status'),
           'local_status': st.get('status'), 'mp4': st.get('mp4'), 'why': st.get('why')})
    return 0 if st.get('status') == 'done' else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--loop', action='store_true')
    ap.add_argument('--daemon', action='store_true', help='无窗口常驻（带心跳与日志）')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--sleep', type=int, default=20)
    a = ap.parse_args()
    if a.once or not (a.loop or a.daemon):
        sys.exit(drain(a.dry_run))
    _emit({'claimer': 'start', 'mode': ('daemon' if a.daemon else 'loop'),
           'sleep': max(5, a.sleep), 'log': str(LOG)})
    _beat(state='idle', mode=('daemon' if a.daemon else 'loop'))
    while True:
        try:
            rc = drain(a.dry_run)
            _beat(state='idle', mode=('daemon' if a.daemon else 'loop'), last_rc=rc)
        except Exception as e:                                        # noqa: BLE001
            # 单轮坏了不许丢命：记原因、留心跳、继续下一轮（P15）
            _emit({'round_error': '%s: %s' % (type(e).__name__, str(e)[:300])})
            _beat(state='error', why='%s: %s' % (type(e).__name__, str(e)[:200]))
        time.sleep(max(5, a.sleep))


if __name__ == '__main__':
    main()
