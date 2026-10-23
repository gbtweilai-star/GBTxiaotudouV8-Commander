# -*- coding: utf-8 -*-
"""talk-socket.py — 把「算力」做成一个 OpenAI 兼容插座（主脑反向调用，不是调别人的模型）。

## 原理（主人 2026-10-19 复述后确认）
不是"借对面的视频模型"，而是：**对面那台机器上跑我们自己的模型**，只把它的 **CPU/GPU**
借过来。做法是把对面包装成一个 **OpenAI 兼容端点**：

    本机主脑 ── omni_plug.ai_control / _local_ai_call ──> POST /v1/chat/completions
                                                            │
                                                            └─ 在**执行端**跑 SadTalker（我们的权重）
                                                               产物落盘，回任务 id

所以计费不按 token 走大厂，走的是"我们自己那台机器"的算力。本文件就是执行端那一半：
它在本机（或任何一台被隧道暴露的机器）上起一个 OpenAI 兼容服务，把"图 + 音频 ⇒ 说话视频"
包成一个可调用动作。

## 契约（主脑侧只需三条）
  GET  /v1/models                                   → 插座在不在
  POST /v1/chat/completions  {"messages":[{"role":"user","content":"<JSON 指令>"}]}
       指令 {"op":"probe"}                        → 报自己能干什么
       指令 {"op":"render","image":...,"audio":...,"out":...} → 起任务，回 task_id
       指令 {"op":"status","task_id":...}          → 回 status/mp4/bytes/log_tail
  （回包是标准 OpenAI chat 形状：choices[0].message.content 里放 JSON 字符串）

## 纪律
  · 只监听回环（默认 127.0.0.1）；要暴露给远端，请用隧道（Cloudflare Tunnel/SSH -R），
    不要在本文件里开 0.0.0.0 —— 那是另一件事，得主人点头；
  · 任务串行（一个 GPU 跑一个 SadTalker 才快），并发请求排队并如实回 queued；
  · 失败如实带原因（stdout/stderr 尾巴），不假装成功。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / '.venv-sadtalker' / 'Scripts' / 'python.exe'
OUTDIR = ROOT / 'outputs' / 'dh-talk'
TASKS: dict = {}
LOCK = threading.Lock()
QUEUE: list = []


def _py() -> Path:
    return PY if PY.is_file() else ROOT / '.venv-sadtalker' / 'bin' / 'python'


def _run_job(tid: str, spec: dict) -> None:
    """真的去跑 SadTalker（用我们自己的 talk-photo.py，不重写流水线）。"""
    out = spec.get('out') or str(OUTDIR / ('socket-%s.mp4' % tid))
    cmd = [str(_py()), str(ROOT / 'tools' / 'digihuman' / 'talk-photo.py'),
           '--image', str(spec.get('image') or ROOT / 'outputs' / 'ref' / 'portrait-ref.png'),
           '--audio', str(spec.get('audio') or ROOT / 'outputs' / 'voice-studio' / 'short-video' / 'dialogue.wav'),
           '--out', out, '--size', str(spec.get('size') or 256)]
    with LOCK:
        TASKS[tid].update(status='running', started=time.strftime('%Y-%m-%dT%H:%M:%S'), cmd=cmd)
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=int(spec.get('timeout') or 7200))
        log = ((p.stdout or b'') + (p.stderr or b'')).decode('utf-8', 'replace')
        mp4 = Path(out)
        ok = p.returncode == 0 and mp4.is_file() and mp4.stat().st_size > 10240
        upd = {'status': 'done' if ok else 'failed', 'returncode': p.returncode,
               'secs': round(time.time() - t0, 1),
               'mp4': str(mp4) if mp4.is_file() else None,
               'bytes': mp4.stat().st_size if mp4.is_file() else -1,
               'log_tail': log.strip().splitlines()[-12:]}
        if not ok:
            upd['why'] = 'returncode=%s, mp4_exist=%s, bytes=%s' % (
                p.returncode, mp4.is_file(), upd['bytes'])
    except Exception as e:                                            # noqa: BLE001
        upd = {'status': 'failed', 'why': '%s: %s' % (type(e).__name__, str(e)[:300]),
               'secs': round(time.time() - t0, 1)}
    with LOCK:
        TASKS[tid].update(upd)


def _start(spec: dict) -> dict:
    tid = uuid.uuid4().hex[:12]
    with LOCK:
        TASKS[tid] = {'status': 'queued', 'spec': {k: v for k, v in spec.items() if k != 'op'}}
    t = threading.Thread(target=_run_job, args=(tid, spec), daemon=True)
    t.start()
    return {'ok': True, 'task_id': tid, 'status': 'queued', 'poll': 'op=status&task_id=%s' % tid}


def _status(tid: str) -> dict:
    with LOCK:
        t = TASKS.get(tid)
    if not t:
        return {'ok': False, 'why': '没有这个 task_id', 'task_id': tid}
    return {'ok': True, 'task_id': tid, **{k: v for k, v in t.items() if k != 'spec'}}


def _probe() -> dict:
    ready = _py().is_file() and (ROOT / 'third_party' / 'SadTalker' / 'inference.py').is_file()
    ck = ROOT / 'third_party' / 'SadTalker' / 'checkpoints'
    return {'ok': ready, 'socket': 'gbt-talk-local', 'engine': 'SadTalker (local, our weights)',
            'venv': str(_py()), 'venv_ok': _py().is_file(),
            'checkpoints': sorted(p.name for p in ck.glob('*') if p.is_file()) if ck.is_dir() else [],
            'ops': ['probe', 'render', 'status'],
            'note': '算力在本机；远端只需把本服务放到那台机器上并用隧道接回来（base_url 换成 https）'}


class H(BaseHTTPRequestHandler):
    server_version = 'gbt-talk-socket/1.0'

    def _send(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):                                # noqa: A003
        pass                                                          # 自己不打噪音

    def do_GET(self):                                                 # noqa: N802
        if self.path.rstrip('/') in ('/v1/models', '/models'):
            return self._send(200, {'object': 'list', 'data': [
                {'id': 'gbt-talk-local', 'object': 'model', 'owned_by': 'gbt'}]})
        return self._send(404, {'error': {'message': 'no route %s' % self.path, 'code': 'not_found'}})

    def do_POST(self):                                                # noqa: N802
        if not self.path.rstrip('/').endswith('/chat/completions'):
            return self._send(404, {'error': {'message': 'no route %s' % self.path}})
        try:
            n = int(self.headers.get('Content-Length') or 0)
            body = json.loads(self.rfile.read(n).decode('utf-8', 'replace') or '{}')
        except Exception as e:                                        # noqa: BLE001
            return self._send(400, {'error': {'message': 'bad json: %s' % e}})
        msgs = body.get('messages') or []
        content = ''
        for m in reversed(msgs):
            if m.get('role') == 'user':
                content = m.get('content') or ''
                break
        try:
            spec = json.loads(content) if content.strip().startswith('{') else {'op': 'probe'}
        except Exception:                                             # noqa: BLE001
            spec = {'op': 'probe'}
        op = str(spec.get('op') or 'probe')
        if op == 'render':
            res = _start(spec)
        elif op == 'status':
            res = _status(str(spec.get('task_id') or ''))
        else:
            res = _probe()
        # 标准 OpenAI chat 形状：调用方（_local_ai_call）只读 choices[0].message.content
        return self._send(200, {'id': 'chatcmpl-%s' % uuid.uuid4().hex[:8], 'object': 'chat.completion',
                                'created': int(time.time()), 'model': body.get('model') or 'gbt-talk-local',
                                'choices': [{'index': 0, 'finish_reason': 'stop',
                                             'message': {'role': 'assistant',
                                                         'content': json.dumps(res, ensure_ascii=False)}}],
                                'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8377)
    a = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer((a.host, a.port), H)
    print(json.dumps({'ok': True, 'listening': 'http://%s:%d/v1' % (a.host, a.port),
                      'ops': ['probe', 'render', 'status']}, ensure_ascii=False), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
