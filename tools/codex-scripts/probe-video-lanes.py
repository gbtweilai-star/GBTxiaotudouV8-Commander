# -*- coding: utf-8 -*-
"""probe-video-lanes.py — 只读探测：现有各条出网钥的端点里，有没有能"图生视频"的模型。

判据（P1：先写死再跑）：
  · 命中 = /v1/models 返回的 id 里出现 video / lipsync / talking / kling / sora / veo / seedance / wan / pika / heygen / liveportrait 之一；
  · 没命中就如实报"没有"，不许拿聊天模型冒充视频模型；
  · **绝不打印明文钥**，只报槽名 + 状态码 + 模型数 + 命中名单。
"""
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

LANES = {
    'agnes': 'https://apihub.agnes-ai.com/v1',
    'openai': 'https://api.teamorouter.com/v1',
    'deepseek': 'https://api.deepseek.com/v1',
    'kimi': 'https://api.moonshot.cn/v1',
    'potato': 'https://gbt-potato-cloud-10.lopaycn.workers.dev/v1',
    'custom': '',
    'freellmapi': '',
}
VIDEO_HINTS = ('video', 'lipsync', 'lip-sync', 'talking', 'kling', 'sora', 'veo', 'seedance',
               'wan2', 'wanx', 'pika', 'heygen', 'liveportrait', 'sadtalker', 'wav2lip',
               'animate', 'avatar', 'i2v', 't2v')

try:
    from gbt_allinone.deepseek_key import _unprotect_dpapi as unprotect
except Exception as e:                                                # noqa: BLE001
    print('IMPORT_FAIL %s: %s' % (type(e).__name__, e))
    raise SystemExit(2)


def get_key(profile):
    p = SECRETS / ('%s_api.dpapi' % profile)
    if not p.is_file():
        return ''
    try:
        return unprotect(p.read_bytes(), profile=profile).decode('utf-8', 'replace').strip()
    except Exception:                                                 # noqa: BLE001
        return ''


def models(base, key):
    req = urllib.request.Request(base.rstrip('/') + '/models',
                                 headers={'Authorization': 'Bearer ' + key,
                                          'User-Agent': 'gbt-lane-probe/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            j = json.loads(r.read().decode('utf-8', 'replace'))
        ids = [m.get('id') for m in (j.get('data') or j.get('models') or []) if isinstance(m, dict)]
        return 200, ids, ''
    except urllib.error.HTTPError as e:
        return e.code, [], e.read().decode('utf-8', 'replace')[:160]
    except Exception as e:                                            # noqa: BLE001
        return 0, [], '%s: %s' % (type(e).__name__, str(e)[:120])


out = []
for name, base in LANES.items():
    key = get_key(name)
    rec = {'lane': name, 'key_present': bool(key), 'base': base}
    if key and base:
        st, ids, err = models(base, key)
        hits = [i for i in ids if any(h in str(i).lower() for h in VIDEO_HINTS)]
        rec.update(http=st, models=len(ids), video_hits=hits[:8], err=err)
    out.append(rec)
    print(json.dumps(rec, ensure_ascii=False))

print('--- summary ---')
print('lanes with key:', [r['lane'] for r in out if r['key_present']])
print('lanes with video-capable model:', [r['lane'] for r in out if r.get('video_hits')])
