# -*- coding: utf-8 -*-
"""talk-socket-cloud-check.py — 验收刚部署的云插件（插座 Worker）。

判据（先写死）：
  · /health 无鉴权 200 ⇒ 插件活
  · /v1/chat/completions 带 Bearer ⇒ probe 回 queue_depth/ops
  · 不带 Bearer ⇒ **401 且带原因**（不是静默放行）
  · render ⇒ 回 task_id；claim 取得到同一条；status 查得到
所有读数都打印，失败也带服务器原话（P26）。
"""
import ctypes
import ctypes.wintypes as w
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
URL = 'https://gbt-talk-socket.paysssk.workers.dev'
TOK_FILE = ROOT / 'gbt_allinone' / 'store' / 'secrets' / 'talk_socket.dpapi'


class B(ctypes.Structure):
    _fields_ = [('cbData', w.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]


def unprot(data: bytes) -> bytes:
    bi = B(len(data), ctypes.cast(ctypes.c_char_p(data), ctypes.POINTER(ctypes.c_char)))
    bo = B()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(bi), None, None, None, None, 0, ctypes.byref(bo)):
        raise ctypes.WinError()
    return ctypes.string_at(bo.pbData, bo.cbData)


def call(path, body=None, token='', method=None, timeout=30):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    hdr = {'content-type': 'application/json', 'user-agent': 'gbt-check/1.0'}
    if token:
        hdr['authorization'] = 'Bearer ' + token
    req = urllib.request.Request(URL + path, data=data, headers=hdr,
                                 method=method or ('POST' if data else 'GET'))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except Exception as e:                                            # noqa: BLE001
        return 0, '%s: %s' % (type(e).__name__, str(e)[:200])


def directive(obj, token):
    return call('/v1/chat/completions', {'model': 'gbt-talk-cloud',
                                         'messages': [{'role': 'user', 'content': json.dumps(obj)}]}, token)


def main():
    tok = unprot(TOK_FILE.read_bytes()).decode().strip()
    print('1) health      ', call('/health'))
    print('2) 无票 probe  ', call('/v1/chat/completions',
                                 {'messages': [{'role': 'user', 'content': '{"op":"probe"}'}]}))
    st, txt = directive({'op': 'probe'}, tok)
    print('3) 带票 probe  ', st, txt[:260])
    st, txt = directive({'op': 'render', 'image': 'outputs/ref/face-tight.png',
                         'audio': 'outputs/voice-studio/short-video/dialogue.wav'}, tok)
    print('4) render      ', st, txt[:260])
    try:
        tid = json.loads(json.loads(txt)['choices'][0]['message']['content'])['task_id']
    except Exception:                                                 # noqa: BLE001
        print('   ! 没拿到 task_id，后续跳过')
        return 1
    print('5) claim       ', call('/v1/jobs/claim?token=' + tok)[0],
          str(call('/v1/jobs/claim?token=' + tok)[1])[:200])
    st, txt = directive({'op': 'status', 'task_id': tid}, tok)
    print('6) status      ', st, txt[:220])
    return 0


if __name__ == '__main__':
    sys.exit(main())
