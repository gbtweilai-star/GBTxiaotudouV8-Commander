# -*- coding: utf-8 -*-
"""agnes-video-probe.py — 摸清 agnes 视频模型的真实接口契约（只读探路，不猜）。

做法：拿现成的 agnes 钥，对几个候选路径各发一次**最小请求**，把服务器的原始回包贴出来。
判据：只要有一个路径返回"参数缺失/需要有 image 字段"这类**契约性错误**，就说明接口存在、
只是参数不对 —— 那比 404 有价值得多（P26：格式类失败先打原始载荷）。
"""
import base64
import json
import sys

# ── 编码守门（encoding-guard 要求）：不带 -X utf8 调用时不许静默输出空 ──
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SECRETS = ROOT / 'gbt_allinone' / 'store' / 'secrets'
from gbt_allinone.deepseek_key import _unprotect_dpapi as unprotect  # noqa: E402

BASE = 'https://apihub.agnes-ai.com/v1'
KEY = unprotect((SECRETS / 'agnes_api.dpapi').read_bytes(), profile='agnes').decode().strip()


def call(method, path, body=None, timeout=60):
    url = BASE + path
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={'Authorization': 'Bearer ' + KEY,
                                          'Content-Type': 'application/json',
                                          'User-Agent': 'gbt-probe/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', 'replace')[:900]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:900]
    except Exception as e:                                            # noqa: BLE001
        return 0, '%s: %s' % (type(e).__name__, str(e)[:200])


print('--- models ---')
st, body = call('GET', '/models')
print(st, body[:600])

print('\n--- GET /videos (sora 风格列表) ---')
st, body = call('GET', '/videos')
print(st, body[:400])

print('\n--- POST /videos 最小请求 ---')
st, body = call('POST', '/videos', {'model': 'agnes-video-2.5', 'prompt': 'a girl talking'})
print(st, body[:600])

print('\n--- POST /video/generations ---')
st, body = call('POST', '/video/generations', {'model': 'agnes-video-2.5', 'prompt': 'a girl talking'})
print(st, body[:600])

print('\n--- POST /images/generations (看有没有出图，用于口型图) ---')
st, body = call('POST', '/images/generations', {'model': 'agnes-image-2.5', 'prompt': 'a red apple'})
print(st, body[:400])
