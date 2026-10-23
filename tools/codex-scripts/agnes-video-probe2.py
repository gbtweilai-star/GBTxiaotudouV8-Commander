# -*- coding: utf-8 -*-
"""agnes-video-probe2.py — 摸清 /v1/videos 的 mode 与图片字段名（只读探路）。

判据：找到一组参数能让它**返回任务 id**（而不是 4xx 参数错误）即视为契约成立。
所有失败都把服务器原话贴出来（P26）。
"""
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):          # 不带 -X utf8 调用时不许静默输出空
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SECRETS = ROOT / 'gbt_allinone' / 'store' / 'secrets'
from gbt_allinone.deepseek_key import _unprotect_dpapi as unprotect  # noqa: E402

BASE = 'https://apihub.agnes-ai.com/v1'
KEY = unprotect((SECRETS / 'agnes_api.dpapi').read_bytes(), profile='agnes').decode().strip()
FACE = ROOT / 'outputs' / 'ref' / 'face-ref.png'
B64 = base64.b64encode(FACE.read_bytes()).decode('ascii')


def post(body, timeout=90):
    req = urllib.request.Request(BASE + '/videos', data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
                                 method='POST',
                                 headers={'Authorization': 'Bearer ' + KEY,
                                          'Content-Type': 'application/json',
                                          'User-Agent': 'gbt-probe/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', 'replace')[:700]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:700]
    except Exception as e:                                            # noqa: BLE001
        return 0, '%s: %s' % (type(e).__name__, str(e)[:200])


CASES = [
    ('t2v', {'model': 'agnes-video-2.5', 'prompt': 'a girl standing in rain', 'mode': 't2v'}),
    ('i2v+image', {'model': 'agnes-video-2.5', 'prompt': 'she talks', 'mode': 'i2v', 'image': B64[:200]}),
    ('i2v+image_url', {'model': 'agnes-video-2.5', 'prompt': 'she talks', 'mode': 'i2v',
                       'image': 'https://example.com/a.png'}),
    ('img2video', {'model': 'agnes-video-2.5', 'prompt': 'she talks', 'mode': 'img2video'}),
]
for tag, body in CASES:
    st, txt = post(body)
    head = txt[:320].replace('\n', ' ')
    print('%-14s http=%-4s %s' % (tag, st, head))
    if st in (200, 201):
        print('   ^^^ 契约成立，响应里有任务 id')
