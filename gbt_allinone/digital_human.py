# -*- coding: utf-8 -*-
"""digital_human — 数字人「以图生视频」能力位（本地 SadTalker，零账号）

## 这是什么（主人 2026-10-19 定）
主人原话："数字人你就不会以图生视频的形式实现动作自然口型对齐吗这么简单的事情你搞一天"。
对。之前那套在浏览器里实时画 2.5D 嘴的路子，本质是**我自己造嘴**，只能在"贴纸"和"面瘫"之间选。
这一位换成让**模型**从她这张脸生成动作与口型：一张图 + 一段配音 ⇒ 说话视频。

## 顺带固化的第二件事：算力插座
主人原话："反向调用的只是算力和 CPU/GPU 而不是模型"、"只要密钥有 1 块钱能通云端就行"。
所以本能力位不只跑本地：`socket` 动作会把本模块的 render 包成一个 **OpenAI 兼容端点**
（`/v1/chat/completions`），主脑可用 `omni_plug.ai_control`（远端 https）或
`_local_ai_call`（回环）反向调用它 —— **对面跑的是我们的权重，借的只是 CPU/GPU**。
换远端时只改 base_url；本模块一行不用动。

## ops
  status       只读：引擎/权重/venv/最近任务/插座状态
  capabilities 只读：能干什么、边界在哪（含"取景决定画质上限"这条实测教训）
  probe        只读：这台机器现在能不能立刻出片（缺什么如实报）
  render       写：起一个出片任务（异步，回 task_id）；写面只落 outputs/dh-talk/ 与 state/digital_human/
  task         只读：按 task_id 查状态/产物/失败原因
  jobs         只读：最近任务账（jsonl）
  socket       start/stop/status：起/停/查 OpenAI 兼容插座（只监听回环）

## 纪律
  · 写面自收窄：只允许 outputs/dh-talk/ 与 state/digital_human/（policy 无本 kind ⇒ 门内零作用域，故自钉）；
  · 失败必须带原因（returncode / log_tail / why），不许只说"没拿到"；
  · 不假装：引擎缺件就如实报缺 + 给补齐的那一步。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / '.venv-sadtalker'
REPO = ROOT / 'third_party' / 'SadTalker'
CKPT = REPO / 'checkpoints'
OUTDIR = ROOT / 'outputs' / 'dh-talk'
STATEDIR = ROOT / 'state' / 'digital_human'
JOBS = STATEDIR / 'jobs.jsonl'
WRITE_ROOTS = (OUTDIR.resolve(), STATEDIR.resolve())
SOCKET_DEFAULT_PORT = 8377

_TASKS: dict = {}
_LOCK = threading.Lock()
_SOCK = {'proc': None, 'port': SOCKET_DEFAULT_PORT, 'started': ''}

NEED_CKPT = ('mapping_00109-model.pth.tar', 'mapping_00229-model.pth.tar',
             'SadTalker_V0.0.2_256.safetensors')
NEED_BFM = ('01_MorphableModel.mat', 'BFM09_model_info.mat', 'Exp_Pca.bin', 'facemodel_info.mat')
NEED_FA = ('2DFAN4-cd938726ad.zip', 's3fd-619a316812.pth')


def _py() -> Path:
    p = VENV / 'Scripts' / 'python.exe'
    return p if p.is_file() else VENV / 'bin' / 'python'


def _torch_hub() -> Path:
    base = os.environ.get('TORCH_HOME')
    return (Path(base) / 'hub' / 'checkpoints') if base else (
        Path(os.environ.get('USERPROFILE') or Path.home()) / '.cache' / 'torch' / 'hub' / 'checkpoints')


def _allowed(p: Path) -> bool:
    try:
        r = p.resolve()
    except Exception:                                                 # noqa: BLE001
        return False
    return any(str(r).startswith(str(w)) for w in WRITE_ROOTS)


def _log(rec: dict) -> None:
    STATEDIR.mkdir(parents=True, exist_ok=True)
    with JOBS.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def _engine() -> dict:
    miss_c = [n for n in NEED_CKPT if not (CKPT / n).is_file() or (CKPT / n).stat().st_size < 1024]
    miss_b = [n for n in NEED_BFM if not (CKPT / 'BFM_Fitting' / n).is_file()]
    miss_f = [n for n in NEED_FA if not (_torch_hub() / n).is_file()]
    return {
        'venv': str(_py()), 'venv_ok': _py().is_file(),
        'repo': str(REPO), 'repo_ok': (REPO / 'inference.py').is_file(),
        'checkpoints_missing': miss_c, 'bfm_missing': miss_b, 'face_alignment_missing': miss_f,
        'checkpoints_dir': str(CKPT),
        'ready': not (miss_c or miss_b or miss_f) and _py().is_file() and (REPO / 'inference.py').is_file(),
    }


def _run_job(tid: str, spec: dict) -> None:
    out = Path(spec['out'])
    cmd = [str(_py()), str(ROOT / 'tools' / 'digihuman' / 'talk-photo.py'),
           '--image', spec['image'], '--audio', spec['audio'], '--out', str(out),
           '--size', str(spec.get('size') or 256), '--preprocess', spec.get('preprocess') or 'full']
    if spec.get('no_still'):
        cmd.append('--no-still')
    if spec.get('enhancer'):
        cmd += ['--enhancer', str(spec['enhancer'])]
    with _LOCK:
        _TASKS[tid].update(status='running', started=time.strftime('%Y-%m-%dT%H:%M:%S'), cmd=cmd)
    t0 = time.time()
    try:
        # 常驻档用 pythonw 跑（无控制台）：子进程不屏蔽的话 Windows 会给它**新开一个黑窗**。
        _flags = 0x08000000 if os.name == 'nt' else 0        # CREATE_NO_WINDOW
        p = subprocess.run(cmd, capture_output=True, creationflags=_flags,
                           timeout=int(spec.get('timeout') or 14400))
        log = ((p.stdout or b'') + (p.stderr or b'')).decode('utf-8', 'replace')
        ok = p.returncode == 0 and out.is_file() and out.stat().st_size > 10240
        upd = {'status': 'done' if ok else 'failed', 'returncode': p.returncode,
               'secs': round(time.time() - t0, 1),
               'mp4': str(out) if out.is_file() else None,
               'bytes': out.stat().st_size if out.is_file() else -1,
               'log_tail': log.strip().splitlines()[-15:]}
        if not ok:
            upd['why'] = 'returncode=%s · mp4_exist=%s · bytes=%s' % (
                p.returncode, out.is_file(), upd['bytes'])
    except Exception as e:                                            # noqa: BLE001
        upd = {'status': 'failed', 'why': '%s: %s' % (type(e).__name__, str(e)[:300]),
               'secs': round(time.time() - t0, 1)}
    with _LOCK:
        _TASKS[tid].update(upd)
    _log({'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'task_id': tid, **{k: v for k, v in upd.items() if k != 'log_tail'},
          'image': spec['image'], 'audio': spec['audio'], 'out': str(out)})


def op_status(**_kw) -> dict:
    e = _engine()
    recent = []
    if JOBS.is_file():
        lines = JOBS.read_text(encoding='utf-8').splitlines()[-5:]
        for ln in lines:
            try:
                recent.append(json.loads(ln))
            except Exception:                                         # noqa: BLE001
                pass
    with _LOCK:
        live = len([t for t in _TASKS.values() if t.get('status') in ('queued', 'running')])
    return {'ok': True, 'cap': 'digital_human', 'op': 'status', 'engine': e,
            'live_tasks': live, 'recent_jobs': recent, 'socket': op_socket(action='status'),
            'outdir': str(OUTDIR), 'ledger': str(JOBS),
            'note': '本机 CPU 出片按 ~13.6 s/帧 计（14.8s 配音≈80 分钟）；远端 GPU 通常 1~2 分钟。'}


def op_capabilities(**_kw) -> dict:
    return {'ok': True, 'cap': 'digital_human', 'op': 'capabilities',
            'ops': ['status', 'capabilities', 'probe', 'render', 'task', 'jobs', 'socket'],
            'what': '一张照片 + 一段配音 ⇒ 带头部动作与口型同步的说话视频（SadTalker，本地权重）',
            'limits': [
                '取景决定画质上限：脸在画面里越小，口型越看不清 —— 传头肩景（如 outputs/ref/face-tight.png）',
                '本机纯 CPU：~13.6 s/帧；要快就把本能力放远端跑，见 socket',
                '不换背景、不改身份：模型只动脸/头，原图背景会被预处理轻微重建（--preprocess crop 更干净但会裁方）',
                '嘴型来自音频驱动（audio2exp/audio2pose），不是逐帧对齐外部字幕',
            ],
            'socket': 'op=socket action=start → 起一个 OpenAI 兼容端点；主脑用 omni_plug.ai_control/_local_ai_call 反向调用',
            'write_roots': [str(w) for w in WRITE_ROOTS]}


def op_probe(**_kw) -> dict:
    e = _engine()
    miss = []
    if not e['venv_ok']:
        miss.append('venv(.venv-sadtalker)')
    if not e['repo_ok']:
        miss.append('third_party/SadTalker')
    miss += ['checkpoint:' + m for m in e['checkpoints_missing']]
    miss += ['bfm:' + m for m in e['bfm_missing']]
    miss += ['face_alignment:' + m for m in e['face_alignment_missing']]
    return {'ok': e['ready'], 'cap': 'digital_human', 'op': 'probe', 'engine': e,
            'missing': miss, 'can_render_now': e['ready'],
            'why': None if e['ready'] else '缺件：' + '、'.join(miss)}


def op_render(image: str = '', audio: str = '', out: str = '', size: int = 256,
              preprocess: str = 'full', no_still: bool = False, timeout: int = 14400,
              enhancer: str = '', **_kw) -> dict:
    e = _engine()
    if not e['ready']:
        return {'ok': False, 'cap': 'digital_human', 'op': 'render',
                'why': '引擎不可用，先补件', 'missing': op_probe()['missing']}
    if not image:
        image = str(ROOT / 'outputs' / 'ref' / 'face-tight.png')
    if not audio:
        audio = str(ROOT / 'outputs' / 'voice-studio' / 'short-video' / 'dialogue.wav')
    for p, tag in ((image, 'image'), (audio, 'audio')):
        if not Path(p).is_file():
            return {'ok': False, 'cap': 'digital_human', 'op': 'render',
                    'why': '%s 不存在：%s' % (tag, p)}
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = out or str(OUTDIR / ('dh-%s.mp4' % time.strftime('%Y%m%d-%H%M%S')))
    if not _allowed(Path(out)):
        return {'ok': False, 'cap': 'digital_human', 'op': 'render',
                'why': '写面自收窄：只允许落 %s' % ' 或 '.join(str(w) for w in WRITE_ROOTS),
                'asked': out}
    tid = uuid.uuid4().hex[:12]
    spec = {'image': str(Path(image).resolve()), 'audio': str(Path(audio).resolve()),
            'out': str(Path(out).resolve()), 'size': int(size), 'preprocess': preprocess,
            'no_still': bool(no_still), 'enhancer': str(enhancer or ''),
            'timeout': int(timeout)}
    with _LOCK:
        _TASKS[tid] = {'status': 'queued', 'spec': spec, 'created': time.strftime('%Y-%m-%dT%H:%M:%S')}
    threading.Thread(target=_run_job, args=(tid, spec), daemon=True).start()
    return {'ok': True, 'cap': 'digital_human', 'op': 'render', 'task_id': tid,
            'status': 'queued', 'out': spec['out'],
            'poll': 'run_task digital_human {"op":"task","task_id":"%s"}' % tid,
            'eta_note': '本机 CPU 约 13.6 s/帧；14.8s 配音 ≈ 80 分钟'}


def op_task(task_id: str = '', **_kw) -> dict:
    with _LOCK:
        t = _TASKS.get(task_id)
    if not t:
        # 回落到账本（进程重启后仍可查）
        if JOBS.is_file():
            for ln in reversed(JOBS.read_text(encoding='utf-8').splitlines()):
                try:
                    j = json.loads(ln)
                except Exception:                                     # noqa: BLE001
                    continue
                if j.get('task_id') == task_id:
                    return {'ok': True, 'cap': 'digital_human', 'op': 'task', 'source': 'ledger', **j}
        return {'ok': False, 'cap': 'digital_human', 'op': 'task', 'why': '没有这个 task_id',
                'task_id': task_id}
    return {'ok': True, 'cap': 'digital_human', 'op': 'task', 'task_id': task_id,
            **{k: v for k, v in t.items() if k != 'spec'}, 'spec': t.get('spec')}


def op_jobs(limit: int = 10, **_kw) -> dict:
    items = []
    if JOBS.is_file():
        for ln in JOBS.read_text(encoding='utf-8').splitlines()[-int(limit):]:
            try:
                items.append(json.loads(ln))
            except Exception:                                         # noqa: BLE001
                pass
    return {'ok': True, 'cap': 'digital_human', 'op': 'jobs', 'n': len(items), 'items': items}


def op_socket(action: str = 'status', port: int = SOCKET_DEFAULT_PORT, **_kw) -> dict:
    """OpenAI 兼容插座：把 render 包成端点，主脑反向调用（换远端只改 base_url）。"""
    p = _SOCK['proc']
    alive = bool(p and p.poll() is None)
    if action == 'start':
        if alive:
            return {'ok': True, 'cap': 'digital_human', 'op': 'socket', 'action': 'start',
                    'already': True, 'url': 'http://127.0.0.1:%d/v1' % _SOCK['port'],
                    'pid': p.pid}
        script = ROOT / 'tools' / 'digihuman' / 'talk-socket.py'
        if not script.is_file():
            return {'ok': False, 'op': 'socket', 'why': '插座脚本不在：%s' % script}
        py = Path(sys.executable) if sys.version_info >= (3, 10) else Path(sys.executable)
        proc = subprocess.Popen([str(py), str(script), '--port', str(int(port))],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _SOCK.update(proc=proc, port=int(port), started=time.strftime('%Y-%m-%dT%H:%M:%S'))
        time.sleep(1.5)
        return {'ok': proc.poll() is None, 'cap': 'digital_human', 'op': 'socket',
                'action': 'start', 'pid': proc.pid, 'url': 'http://127.0.0.1:%d/v1' % int(port),
                'drive': 'omni_plug._local_ai_call(base, {"messages":[{"role":"user","content":"{\\"op\\":\\"render\\"}"}]})'}
    if action == 'stop':
        if not alive:
            return {'ok': True, 'cap': 'digital_human', 'op': 'socket', 'action': 'stop', 'already': True}
        p.terminate()
        try:
            p.wait(timeout=10)
        except Exception:                                             # noqa: BLE001
            p.kill()
        _SOCK.update(proc=None)
        return {'ok': True, 'cap': 'digital_human', 'op': 'socket', 'action': 'stop'}
    return {'ok': True, 'cap': 'digital_human', 'op': 'socket', 'action': 'status',
            'running': alive, 'pid': (p.pid if alive else None),
            'url': 'http://127.0.0.1:%d/v1' % _SOCK['port'] if alive else None,
            'started': _SOCK.get('started') or None,
            'note': '只监听回环；要暴露给远端请用隧道，不要在插座里开 0.0.0.0'}


def _cloud_token() -> str:
    """云插座令牌：DPAPI 存（secrets 只写不可读，所以本地必须自己留一把）。"""
    p = ROOT / 'gbt_allinone' / 'store' / 'secrets' / 'talk_socket.dpapi'
    if not p.is_file():
        return ''
    try:
        import ctypes
        import ctypes.wintypes as wt

        class B(ctypes.Structure):
            _fields_ = [('cbData', wt.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

        data = p.read_bytes()
        bi = B(len(data), ctypes.cast(ctypes.c_char_p(data), ctypes.POINTER(ctypes.c_char)))
        bo = B()
        if not ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(bi), None, None, None, None, 0, ctypes.byref(bo)):
            return ''
        return ctypes.string_at(bo.pbData, bo.cbData).decode('utf-8', 'replace').strip()
    except Exception:                                                 # noqa: BLE001
        return ''


# ── 两条云插件一屏共享图（主人令 2026-10-19：「借算力的容器云插件和主脑的云插件
#    也使用触手双向绑定联通共享」）──────────────────────────────────────────────
# 云源清单**只从 cloud_plugin.SOURCES 现读**（不在这里抄第二份 —— 抄一份就有一份会过期）。
# 每一条 lane 都要回答三件事：① 它在这台机器上能不能连（/health 无鉴权）② 数据面缺什么钥
# ③ 缺的那把钥，主人要跑哪一行。**不许用一句 401 把三种不同的病混成一句。**
_LANE_GRANT = {
    'cloud_brain': {
        'why': '数据面令牌只写不可读：远端 tokens_configured 已是 2，本机三把钥（potato/gateway/custom）实测全 401。',
        'owner_cmd': ('cd deploy/cloud-10; npx wrangler secret put GBT_ENDPOINT_TOKENS '
                      '--config wrangler.toml'),
        'after': ('敲完把同一把钥交给主脑，我加密入箱：'
                  'python -m gbt_allinone.deepseek_key set --profile custom'
                  '（从 stdin 读，不留明文）'),
    },
}


def _lane_token(src_key: str) -> str:
    """这一条 lane 在本机握没握钥。**只有 socket 那一把是我自己落的 DPAPI。**"""
    if src_key == 'cloud_compute':
        return _cloud_token()
    return ''


def _http_probe(url: str, body=None, token: str = '', timeout: int = 25) -> dict:
    """一次出网，**原话必带**（P17/P19：4xx 要读包体，别把拒绝念成断网）。"""
    import json as _j
    import urllib.error as _ue
    import urllib.request as _u
    hdr = {'user-agent': 'gbt-dh-lanes/1.0 (+local probe)'}
    data = None
    if body is not None:
        data = _j.dumps(body, ensure_ascii=False).encode()
        hdr['content-type'] = 'application/json'
    if token:
        hdr['authorization'] = 'Bearer ' + token
    req = _u.Request(url, data=data, method=('POST' if data else 'GET'), headers=hdr)
    try:
        with _u.urlopen(req, timeout=timeout) as s:
            txt = s.read(1200).decode('utf-8', 'replace')
            return {'http': s.status, 'ok': True, 'body': txt}
    except _ue.HTTPError as e:
        return {'http': e.code, 'ok': False,
                'body': e.read(1200).decode('utf-8', 'replace')}
    except Exception as e:                                            # noqa: BLE001
        return {'http': None, 'ok': False, 'body': '',
                'why': '%s: %s' % (type(e).__name__, str(e)[:200])}


def op_cloud_lanes(tentacle: str = 'digital_human', **_kw) -> dict:
    """两条云插件的一屏共享图：**现读绑定 + 现探活 + 如实报鉴权缺什么**。"""
    import json as _j

    try:
        from .tools.cloud_plugin import SOURCES, run as _cp_run
    except Exception as e:                                            # noqa: BLE001
        return {'ok': False, 'cap': 'digital_human', 'op': 'cloud', 'action': 'lanes',
                'why': 'cloud_plugin 读不到: %s' % e}
    try:
        both = _cp_run('resolve', tentacle=tentacle)
    except Exception as e:                                            # noqa: BLE001
        both = {'ok': False, 'why': 'resolve 失败: %s' % e}
    fwd = set(both.get('正向_触手到云源') or [])

    lanes = []
    for s in SOURCES:
        key = s.get('key') or ''
        url = s.get('url') or ''
        if not url:
            continue                       # 没 url 的云源不是 lane（登记在册但没接线）
        base = url[:-3] if url.endswith('/v1') else url.rstrip('/')
        tok = _lane_token(key)
        row = {'source': key, 'cn': s.get('cn'), 'url': url.replace('/v1', ''),
               'cap': s.get('cap'), 'bound_to': tentacle if key in fwd else None,
               'token_held': bool(tok),
               'health': _http_probe(base + '/health')}
        # 数据面只在**确实握有钥**时才试 —— 没钥就不是「坏了」，是「缺钥」（P27）
        if tok:
            if key == 'cloud_compute':
                row['dataplane'] = _http_probe(
                    url + '/chat/completions',
                    {'messages': [{'role': 'user', 'content': _j.dumps({'op': 'probe'})}]},
                    tok)
            else:
                row['dataplane'] = _http_probe(
                    url + '/chat/completions',
                    {'model': 'gbt-potato-v8',
                     'messages': [{'role': 'user', 'content': 'ping'}]}, tok)
            dp = row['dataplane']
            row['verdict'] = '通' if dp.get('ok') else '数据面被拒（%s）' % dp.get('http')
        else:
            g = _LANE_GRANT.get(key) or {}
            row['verdict'] = '缺钥（%s）' % (g.get('why') or '本机没握这把数据面钥')
            if g:
                row['how_to_grant'] = {'owner_cmd': g.get('owner_cmd'), 'after': g.get('after')}
        lanes.append(row)

    live = [r['source'] for r in lanes if r.get('verdict') == '通']
    dead = [r['source'] for r in lanes if r.get('verdict') != '通']
    return {'ok': True, 'cap': 'digital_human', 'op': 'cloud', 'action': 'lanes',
            'tentacle': tentacle, '双向绑定': both,
            'lanes': lanes, 'live': live, 'needs_key': dead,
            'note': ('共享的是**算力与网**，不是模型：cloud_compute 只排队，算力在 claim 端；'
                     'cloud_brain 是主脑那半边，缺钥就如实缺钥，不假装通。')}


def op_cloud(action: str = 'probe', url: str = '', task_id: str = '', image: str = '',
             audio: str = '', mp4: str = '', bytes_: int = -1, why: str = '',
             tentacle: str = 'digital_human', **_kw) -> dict:
    """云插座（Cloudflare Worker，队列式）：**主脑 → omni_plug.ai_control → 云插件**。

    这是"借算力不借模型"那一半：云插件只排队；算力端（本机/GPU 机/容器）来 claim 真干活。
    probe/render/status 走 `omni_plug._ai_call`（框架真件）；claim/complete 是算力端口令。
    """
    import json as _j
    import urllib.request as _u

    # lanes 要排在令牌闸**之前**：它天生就是"逐条报缺钥"的读数件，
    # 让它先被 socket 那把钥挡住 = 把两种病混成一句（P14 那一型的坑）。
    if action == 'lanes':
        return op_cloud_lanes(tentacle=tentacle)

    base = (url or os.environ.get('GBT_TALK_CLOUD') or
            'https://gbt-talk-socket.paysssk.workers.dev').rstrip('/')
    tok = _cloud_token()
    if not tok:
        return {'ok': False, 'cap': 'digital_human', 'op': 'cloud', 'why':
                '本地没有云插座令牌（gbt_allinone/store/secrets/talk_socket.dpapi）——如实报缺，不假装能调'}
    if action in ('probe', 'render', 'status'):
        try:
            from .omni_plug import _ai_call
        except Exception as e:                                        # noqa: BLE001
            return {'ok': False, 'op': 'cloud', 'why': 'omni_plug 不可用: %s' % e}
        d = {'op': action}
        # _ai_call 只从「环境变量 / 金库」取钥：DPAPI 那把先临时放进本进程环境（不出内存、不落盘）
        os.environ['GBT_TALK_CLOUD_TOKEN'] = tok
        if action == 'render':
            d.update(image=image or str(ROOT / 'outputs' / 'ref' / 'face-tight.png'),
                     audio=audio or str(ROOT / 'outputs' / 'voice-studio' / 'short-video' / 'dialogue.wav'))
        if action == 'status':
            d['task_id'] = task_id
        r = _ai_call(base + '/v1', {'messages': [{'role': 'user', 'content': _j.dumps(d, ensure_ascii=False)}],
                                    'key_env': 'GBT_TALK_CLOUD_TOKEN'}, timeout=45)
        try:
            inner = _j.loads(r.get('text') or '{}')
        except Exception:                                             # noqa: BLE001
            inner = {'raw': (r.get('text') or '')[:300]}
        return {'ok': bool(r.get('ok')), 'cap': 'digital_human', 'op': 'cloud', 'action': action,
                'url': base, 'http': r.get('http'), 'reply': inner,
                'why': None if r.get('ok') else (r.get('reason') or '上游拒绝，见 http/reply')}
    if action == 'claim':
        req = _u.Request('%s/v1/jobs/claim?token=%s' % (base, tok),
                         headers={'user-agent': 'gbt-dh-claimer/1.0'})
        try:
            with _u.urlopen(req, timeout=45) as s:
                return {'ok': True, 'cap': 'digital_human', 'op': 'cloud', 'action': 'claim',
                        **(_j.loads(s.read().decode('utf-8', 'replace')))}
        except Exception as e:                                        # noqa: BLE001
            return {'ok': False, 'op': 'cloud', 'action': 'claim',
                    'why': '%s: %s' % (type(e).__name__, str(e)[:200])}
    if action == 'complete':
        body = _j.dumps({'task_id': task_id, 'status': 'done' if mp4 else 'failed',
                         'mp4': mp4, 'bytes': bytes_, 'why': why or None}).encode()
        req = _u.Request('%s/v1/jobs/complete?token=%s' % (base, tok), data=body, method='POST',
                         headers={'content-type': 'application/json', 'user-agent': 'gbt-dh-claimer/1.0'})
        try:
            with _u.urlopen(req, timeout=45) as s:
                return {'ok': True, 'cap': 'digital_human', 'op': 'cloud', 'action': 'complete',
                        **(_j.loads(s.read().decode('utf-8', 'replace')))}
        except Exception as e:                                        # noqa: BLE001
            return {'ok': False, 'op': 'cloud', 'action': 'complete',
                    'why': '%s: %s' % (type(e).__name__, str(e)[:200])}
    return {'ok': False, 'op': 'cloud', 'why': 'unknown action: %s' % action,
            'actions': ['probe', 'render', 'status', 'claim', 'complete', 'lanes']}


_OPS = {'status': op_status, 'capabilities': op_capabilities, 'probe': op_probe,
        'render': op_render, 'task': op_task, 'jobs': op_jobs, 'socket': op_socket,
        'cloud': op_cloud}


def run_op(op: str = 'status', **kw) -> dict:
    fn = _OPS.get(str(op or 'status'))
    if not fn:
        return {'ok': False, 'cap': 'digital_human', 'why': 'unknown op: %s' % op,
                'ops': list(_OPS)}
    try:
        return fn(**kw)
    except TypeError as e:
        return {'ok': False, 'cap': 'digital_human', 'op': op, 'why': 'args: %s' % e}
    except Exception as e:                                            # noqa: BLE001
        return {'ok': False, 'cap': 'digital_human', 'op': op,
                'why': '%s: %s' % (type(e).__name__, str(e)[:300])}
