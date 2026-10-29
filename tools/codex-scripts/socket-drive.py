# -*- coding: utf-8 -*-
"""socket-drive.py — 用框架自己的插座函数驱动算力插座，证明"主脑 → 插座 → 算力"这条链。

调用的是 `gbt_allinone.omni_plug._local_ai_call`（框架真件，不是我另写的一套 HTTP）。
"""
import json
import sys

# ── 编码守门（encoding-guard 要求）：不带 -X utf8 调用时不许静默输出空 ──
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gbt_allinone.omni_plug import _local_ai_call  # noqa: E402

BASE = 'http://127.0.0.1:8377'


def call(directive: dict, timeout=60) -> dict:
    body = {'model': 'gbt-talk-local',
            'messages': [{'role': 'user', 'content': json.dumps(directive, ensure_ascii=False)}]}
    r = _local_ai_call(BASE, body, timeout=timeout)
    txt = r.get('text') or ''
    try:
        return {'ok': r.get('ok'), 'http': r.get('http'), **json.loads(txt)}
    except Exception:                                                 # noqa: BLE001
        return {'ok': r.get('ok'), 'http': r.get('http'), 'raw': txt[:400], 'why': r.get('reason')}


print('--- 1) 插座在不在 ---')
print(json.dumps(call({'op': 'probe'}), ensure_ascii=False, indent=1))

if len(sys.argv) > 1 and sys.argv[1] == '--render':
    print('--- 2) 让它跑一个任务（借算力） ---')
    job = call({'op': 'render',
                'image': sys.argv[2] if len(sys.argv) > 2 else str(ROOT / 'outputs' / 'ref' / 'face-tight.png'),
                'audio': sys.argv[3] if len(sys.argv) > 3 else str(ROOT / 'outputs' / 'dh-talk' / 'test4s.wav'),
                'out': sys.argv[4] if len(sys.argv) > 4 else str(ROOT / 'outputs' / 'dh-talk' / 'socket-out.mp4'),
                'size': 256})
    print(json.dumps(job, ensure_ascii=False, indent=1))
    tid = job.get('task_id')
    for i in range(240):                       # 最多等 2 小时
        time.sleep(30)
        st = call({'op': 'status', 'task_id': tid})
        print('[%02d] %s' % (i + 1, json.dumps({k: st.get(k) for k in ('status', 'secs', 'bytes', 'mp4', 'why')},
                                               ensure_ascii=False)))
        if st.get('status') in ('done', 'failed'):
            break
