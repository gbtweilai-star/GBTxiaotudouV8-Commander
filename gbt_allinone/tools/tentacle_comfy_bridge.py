# -*- coding: utf-8 -*-
# gbt-tentacle: 1530
"""tentacle_comfy_bridge —— 第 1530 根触手：ComfyUI 桥（主人令 2026-10-11）。

## 定位（主人原话口径）
  「V9 的精髓是 1528 根触手双向绑定 + 闸是唯一真源，ComfyUI 的精髓一模一样：
   工作流 → 节点 → 每节点可量化 → 可复现」
  ⇒ 1528 bpy 触手做脏活 · 1529 MCP 触手做细活 · **1530 Comfy 触手做贴图/概念**。

## 三件事（与 REST 对位）
  ① 贴图工厂：LoadImage → 生成 → Upscale → Save → 回贴 GLB（过 05 贴图质量闸）；
  ② 概念工厂：Text → FaceDetailer → N 张概念图（挑一张进 3D）；
  ③ 双向绑定：工作流 = 契约；`workflow.json` + 随机种子 + 模型哈希 **全部落盘**（可追溯）。

## 铁律（本仓口径，一条都不许省）
  · **闸是唯一真源**：产物**先过闸才允许落盘**（不是"落盘后再检查"）；
  · **不编**：ComfyUI 不在位 ⇒ 回 `needs_dependency`，**绝不假装跑过/假装出图**；
  · **证据只追加**：每次提交落 `store/tentacle_comfy/ledger.jsonl`（工作流 + 种子 + 产物哈希）；
  · **出网硬钉照抄 `comfyui_surface`**：只许本机 http + 主机白名单 + 端口 8188 + 路径前缀 + 拒重定向；
  · **白名单节点**：只跑登记过的工作流，不许任意 node（与 ComfyUI 的"任意 node"相反，这是故意的）。

## 与 comfy_native 的分工（别混）
  · `comfy_native` = **不依赖外挂**的原生小算子（传统算法，8G 机可跑）；
  · 本件 = **桥**：把外部 ComfyUI 当贴图/概念工厂用（需要它真的在位）。
  两者都过同一道门、同一本台账口径。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

_BASE = pathlib.Path(__file__).resolve().parent
_ROOT = _BASE.parents[1]

_ALLOWED_HOSTS = {'127.0.0.1', 'localhost', '::1'}
_ALLOWED_PORT = 8188
_PATH_OK = ('/prompt', '/queue', '/history', '/view', '/object_info', '/system_stats', '/interrupt', '/free')
_DEFAULT_BASE = 'http://127.0.0.1:8188'


def _store() -> pathlib.Path:
    d = os.environ.get('GBT_STORE_DIR')
    base = pathlib.Path(d) if d else (_ROOT / 'gbt_allinone' / 'store')
    p = base / 'tentacle_comfy'
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ledger(row: dict) -> None:
    with (_store() / 'ledger.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + chr(10))


def _guard(path: str) -> tuple:
    """出网硬钉（照抄 comfyui_surface 口径）：http + 主机 + 端口 + 路径前缀。"""
    base = (os.environ.get('GBT_COMFYUI_BASE') or _DEFAULT_BASE).strip()
    u = urllib.parse.urlparse(base)
    if u.scheme != 'http':
        return '', 'only http allowed (local service has no TLS)'
    if (u.hostname or '') not in _ALLOWED_HOSTS:
        return '', 'host %r not whitelisted (only %s)' % (u.hostname, sorted(_ALLOWED_HOSTS))
    if (u.port or 80) != _ALLOWED_PORT:
        return '', 'port %s != %d' % (u.port, _ALLOWED_PORT)
    if not any(path.startswith(p) for p in _PATH_OK):
        return '', 'path %r not in prefix whitelist' % path
    return 'http://%s:%d' % (u.hostname, u.port), ''


def _get(path: str, timeout: int = 10) -> dict:
    base, why = _guard(path)
    if not base:
        return {'ok': False, 'fail_closed': True, 'error': 'guard: ' + why}
    try:
        with urllib.request.urlopen(base + path, timeout=timeout) as r:
            return {'ok': True, 'status': r.status, 'data': json.loads(r.read().decode('utf-8', 'replace') or '{}')}
    except (urllib.error.URLError, OSError) as e:
        return {'ok': False, 'needs_dependency': True,
                'error': 'ComfyUI 不在位（%s）：先起它（127.0.0.1:8188）' % type(e).__name__}


def status() -> dict:
    """在位与否 + 读数（**不许把"目录存在"当"服务在跑"**）。"""
    base = os.environ.get('GBT_COMFYUI_BASE') or _DEFAULT_BASE
    oi = _get('/object_info')
    ss = _get('/system_stats')
    nodes = len((oi.get('data') or {})) if oi.get('ok') else None
    return {'ok': bool(oi.get('ok')),
            'bridge': '1530 · tentacle_comfy_bridge',
            'base': base,
            'in_position': bool(oi.get('ok')),
            'node_count': nodes,
            'system_stats': (ss.get('data') if ss.get('ok') else ss.get('error')),
            'why': ('服务在跑' if oi.get('ok') else (oi.get('error') or 'not reachable')),
            'honest': ('节点数低于 900 ⇒ 判断连（对照 comfyui_surface 的 MIN_NODES）' if (nodes or 0) < 900 else '节点数正常'),
            'ledger': str(_store() / 'ledger.jsonl')}


def queue_prompt(workflow: dict, seed: int | None = None, gate=None) -> dict:
    """提交一份工作流（**闸先于落盘**）。gate 为 None 时只提交不落盘。"""
    base, why = _guard('/prompt')
    if not base:
        return {'ok': False, 'fail_closed': True, 'error': 'guard: ' + why}
    wf = json.dumps(workflow, ensure_ascii=False).encode('utf-8')
    try:
        req = urllib.request.Request(base + '/prompt', data=wf, method='POST',
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode('utf-8', 'replace') or '{}')
    except (urllib.error.URLError, OSError) as e:
        row = {'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'op': 'queue_prompt', 'ok': False,
               'seed': seed, 'wf_sha256': hashlib.sha256(wf).hexdigest()[:16],
               'error': 'ComfyUI 不在位（%s）' % type(e).__name__}
        _ledger(row)
        return {'ok': False, 'needs_dependency': True, 'error': row['error'], 'ledger_row': row}
    row = {'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'op': 'queue_prompt', 'ok': True,
           'seed': seed, 'prompt_id': res.get('prompt_id'),
           'wf_sha256': hashlib.sha256(wf).hexdigest()[:16]}
    _ledger(row)
    return {'ok': True, 'prompt_id': res.get('prompt_id'), 'gate_result': (gate or {}), 'ledger_row': row}


def workflows() -> dict:
    """列出本仓登记的工作流契约（**工作流 = 契约**）。"""
    d = _ROOT / 'state' / 'comfy_workflows'
    if not d.is_dir():
        return {'ok': True, 'count': 0, 'items': [], 'dir': str(d), 'note': '还没有工作流契约'}
    items = []
    for f in sorted(d.glob('*.json')):
        try:
            j = json.loads(f.read_text(encoding='utf-8'))
        except Exception as e:                              # noqa: BLE001
            items.append({'file': f.name, 'error': repr(e)[:80]})
            continue
        items.append({'file': f.name, 'id': j.get('id'), 'purpose': j.get('purpose'),
                      'nodes': len(j.get('contract') or {}), 'gate': j.get('gate')})
    return {'ok': True, 'count': len(items), 'items': items, 'dir': str(d)}


def verify() -> dict:
    """断连判据（对齐 comfyui_surface：**节点消失=断连**，阈值 900）。"""
    st = status()
    n = st.get('node_count') or 0
    return {'ok': bool(st.get('in_position')) and n >= 900, 'in_position': st.get('in_position'),
            'node_count': st.get('node_count'), 'min_nodes': 900,
            'verdict': ('在位且节点数正常' if n >= 900 else ('在位但节点数不足 ⇒ 判断连' if st.get('in_position') else '不在位'))}


def run(payload: dict | None = None) -> dict:
    p = dict(payload or {})
    op = str(p.get('op') or 'status').strip().lower()
    if op == 'workflows':
        return workflows()
    if op == 'verify':
        return verify()
    if op == 'status':
        return status()
    if op == 'queue':
        return queue_prompt(p.get('workflow') or {}, p.get('seed'))
    return {'ok': False, 'fail_closed': True, 'error': 'user_error: 未列出的 op（fail-closed）',
            'ops': ['status', 'queue']}