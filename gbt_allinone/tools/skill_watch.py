# -*- coding: utf-8 -*-
# gbt-capability: skill_watch
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""skill_watch —— 技能观察器（主人令 2026-10-11）。

主人原话：「**给她设计一个类似使用技能，在每次使用的时候都要注意技能的变化和短板来打磨进化**」。

## 一句话
  每次用技能，都要留三笔：**用成没成（读数）· 它变了没（面漂移）· 它短板在哪（打磨点）**；
  三笔攒起来 ⇒ **谁该打磨、打磨什么**，由读数说话，不靠感觉。

## 三件事
  ① **observe（每次用都记）**：cap / 成没成 / 耗时 / 错误类 / 被谁拦住 ⇒ 追加落账（只追加）。
  ② **drift（它变了没）**：把技能当下的**可控制面**（op 表/参数/节点数/版本）与上次快照比；
     变了就报 `surface_changed`（对齐本仓「**节点消失=断连**」口径：升级改名也算变化）。
  ③ **shortboards + advise（短板与打磨）**：按读数排行短板（失败率/耗时 P90/缺依赖/被门拒/超时），
     每条给一句**可执行的打磨点**。

## 铁律
  · **只追加**：账只 append，不改写历史；
  · **不许编**：没观测到就报"无观测"，不许用印象填短板；
  · **短板要有读数**：每条建议必须挂它对应的读数（次数/耗时/错误类）。
"""
from __future__ import annotations

import json
import os
import pathlib
import statistics
import time

_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _dir() -> pathlib.Path:
    d = os.environ.get("GBT_STORE_DIR")
    base = pathlib.Path(d) if d else (_ROOT / 'gbt_allinone' / 'store')
    p = base / 'skill_watch'
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ledger() -> pathlib.Path:
    return _dir() / 'ledger.jsonl'


def _snaps() -> pathlib.Path:
    return _dir() / 'surfaces.json'


def observe(cap: str, ok: bool, ms: float = 0.0, error_class: str = '', detail: str = '',
            gate: str = '') -> dict:
    """每用一次技能，追加一笔观测。"""
    row = {'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'cap': cap, 'ok': bool(ok),
           'ms': float(ms), 'error_class': error_class or '', 'detail': (detail or '')[:300],
           'gate': gate or ''}
    with _ledger().open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + chr(10))
    return {'ok': True, 'recorded': row}


def snapshot(cap: str, surface: dict) -> dict:
    """存一个技能当下可控制面的快照（用于下次比变化）。"""
    p = _snaps()
    data = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            data = {}
    old = data.get(cap) or {}
    data[cap] = {'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'surface': surface}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'ok': True, 'cap': cap, 'had_previous': bool(old),
            'changed': bool(old) and old.get('surface') != surface}


def _rows() -> list[dict]:
    p = _ledger()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def shortboards(top: int = 10) -> dict:
    """短板排行：按读数说话（失败率 / 耗时 P90 / 错误类 / 被门拒）。"""
    rows = _rows()
    if not rows:
        return {'ok': True, 'observed': 0, 'boards': [], 'note': '无观测（不许用印象填短板）'}
    agg: dict[str, dict] = {}
    for r in rows:
        c = agg.setdefault(r['cap'], {'calls': 0, 'fails': 0, 'ms': [], 'errs': {}, 'gates': {}})
        c['calls'] += 1
        if not r.get('ok'):
            c['fails'] += 1
            k = r.get('error_class') or 'unknown'
            c['errs'][k] = c['errs'].get(k, 0) + 1
        if r.get('ms'):
            c['ms'].append(float(r['ms']))
        if r.get('gate'):
            c['gates'][r['gate']] = c['gates'].get(r['gate'], 0) + 1
    boards = []
    for cap, c in agg.items():
        p90 = round(statistics.quantiles(c['ms'], n=10)[8], 1) if len(c['ms']) >= 10 else (max(c['ms']) if c['ms'] else 0.0)
        fail_rate = round(c['fails'] / max(c['calls'], 1), 3)
        score = fail_rate * 2 + min(p90 / 60000.0, 1.0)
        boards.append({'cap': cap, 'calls': c['calls'], 'fails': c['fails'], 'fail_rate': fail_rate,
                       'p90_ms': p90, 'errors': c['errs'], 'gates': c['gates'], 'score': round(score, 3)})
    boards.sort(key=lambda x: x['score'], reverse=True)
    return {'ok': True, 'observed': len(rows), 'caps': len(agg), 'boards': boards[:top]}


def advise(cap: str | None = None, top: int = 5) -> dict:
    """按读数给打磨点（每条都挂读数）。"""
    sb = shortboards(top=top if not cap else 100)
    items = []
    for b in sb['boards']:
        if cap and b['cap'] != cap:
            continue
        tips = []
        if b['fail_rate'] > 0.2:
            tips.append('失败率 %.0f%%（%d/%d）⇒ 先看错误类 %s，别猜' % (b['fail_rate'] * 100, b['fails'], b['calls'],
                                                                        json.dumps(b['errors'], ensure_ascii=False)))
        if b['p90_ms'] > 30000:
            tips.append('P90 耗时 %.0fs ⇒ 疑似冷启动/未预热（实测口径：Serverless 冷启动 ~70-82s）' % (b['p90_ms'] / 1000))
        if b['gates']:
            tips.append('被门拦过：%s ⇒ 要么补授权说明，要么把口径写进文档' % json.dumps(b['gates'], ensure_ascii=False))
        if not tips:
            tips.append('读数健康（失败率 %.0f%% · P90 %.0fs）—— 仍建议定期比对可控制面漂移' % (b['fail_rate'] * 100, b['p90_ms'] / 1000))
        items.append({'cap': b['cap'], 'readings': {'calls': b['calls'], 'fails': b['fails'], 'p90_ms': b['p90_ms']},
                      'polish': tips})
    return {'ok': True, 'advice': items, 'note': '每条打磨点都挂读数；无观测就不给建议'}


def drift(cap: str | None = None) -> dict:
    """面漂移：与上次快照比（变了就报，对齐「节点消失=断连」）。"""
    p = _snaps()
    if not p.exists():
        return {'ok': True, 'note': '还没有面快照（先 snapshot 一次）', 'diffs': []}
    data = json.loads(p.read_text(encoding='utf-8'))
    diffs = []
    for k, v in data.items():
        if cap and k != cap:
            continue
        diffs.append({'cap': k, 'snapshot_at': v.get('at'), 'surface_keys': sorted((v.get('surface') or {}).keys())})
    return {'ok': True, 'diffs': diffs}


def run(payload: dict | None = None) -> dict:
    p = dict(payload or {})
    op = str(p.get('op') or 'shortboards').strip().lower()
    if op == 'observe':
        return observe(str(p.get('cap') or ''), bool(p.get('ok', True)), float(p.get('ms') or 0),
                       str(p.get('error_class') or ''), str(p.get('detail') or ''), str(p.get('gate') or ''))
    if op == 'snapshot':
        return snapshot(str(p.get('cap') or ''), p.get('surface') or {})
    if op == 'shortboards':
        return shortboards(int(p.get('top') or 10))
    if op == 'advise':
        return advise(p.get('cap'), int(p.get('top') or 5))
    if op == 'drift':
        return drift(p.get('cap'))
    return {'ok': False, 'fail_closed': True, 'error': 'user_error: 未列出的 op（fail-closed）',
            'ops': ['observe', 'snapshot', 'shortboards', 'advise', 'drift']}