# -*- coding: utf-8 -*-
# gbt-capability: vision_grounding
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""vision_grounding —— 视觉/定位通道契约（主人令 2026-10-11）。

主人原话：「他的视觉必须能达到 VLX-Flow 他的水平和脑，手同步不能使用传统截图看来在操作」。

## 一句话
  脑-手同步的主通道必须是结构化的（控件树／DOM／API 读数）—— 无视遮挡、可寻址、无像素误差；
  截图只许当兜底，而且兜底时也不许人眼看，必须走模型级 grounding（把「点这个」映射到坐标）。

## 三级通道（顺序即纪律，不许跳级）
  L1 结构层（首选）：
     · 桌面：UIA 控件树 —— tentacle.domain_index / domain_read / domain_act / domain_type
     · 浏览器：CDP DOM —— browser(op=native) 的 list_tabs / get_text / click_element / execute_script
     · 服务：HTTP/API 读数 —— comfyui_surface / key_gateway / five-dim cap
  L2 接地层（结构层确实没有该控件时才用）：像素 + 模型 grounding（VLX-Flow 级）
     仅用于：自绘 UI ／ Canvas ／ 游戏 ／ 无 a11y 的窗口
  L3 回读层（每次动手后必做）：用 L1 再读一次结构化状态确认动了没、动对没（不是再截一张图看）

## 铁律
  · 先结构后像素：没有 L1 尝试记录的动作，不许用 L2（struct_first 判据咬这条）；
  · 像素不许当主通道：L2 若被当主通道 ⇒ 记违规；
  · 动完必回读：L3 缺一次 ⇒ 这条动作标 unverified；
  · 不编：L1 读不到就如实报「该控件不在 a11y 树里」，不许假装看到了。
"""
from __future__ import annotations

import json
import os
import pathlib
import time

_ROOT = pathlib.Path(__file__).resolve().parents[2]

CHANNELS = (
    {'level': 'L1', 'name': 'uia_tree',
     'where': 'tentacle.domain_index / domain_read / domain_act / domain_type',
     'why': 'UIA 控件树：可寻址、无视遮挡、无像素误差'},
    {'level': 'L1', 'name': 'cdp_dom',
     'where': 'browser(op=native): list_tabs / get_text / click_element / execute_script',
     'why': 'CDP DOM：页面级可寻址，不经操作系统，遮挡与前台无关'},
    {'level': 'L1', 'name': 'http_api', 'where': 'comfyui_surface / key_gateway / five-dim cap',
     'why': '服务读数：最精确、可复现'},
    {'level': 'L2', 'name': 'pixel_grounding', 'where': '截图 + 模型 grounding（VLX-Flow 级）',
     'why': '仅兜底：自绘 UI / Canvas / 游戏 / 无 a11y 窗口'},
    {'level': 'L3', 'name': 'readback', 'where': '用 L1 再读一次确认',
     'why': '脑-手同步的收口：动完必须回读'},
)


def _ledger_path() -> pathlib.Path:
    d = os.environ.get('GBT_STORE_DIR')
    base = pathlib.Path(d) if d else (_ROOT / 'gbt_allinone' / 'store')
    p = base / 'vision_grounding'
    p.mkdir(parents=True, exist_ok=True)
    return p / 'ledger.jsonl'


def channels() -> dict:
    return {'ok': True, 'channels': list(CHANNELS),
            'rule': 'L1 优先 -> L2 仅兜底（且必须模型 grounding）-> L3 动完必回读',
            'ban': '禁止把截图像素的人眼看当脑-手同步的主通道'}


def record(level: str, name: str, target: str = '', struct_tried: bool = False,
           readback: bool = False, ok: bool = True, detail: str = '') -> dict:
    viol = []
    if str(level).upper() == 'L2' and not struct_tried:
        viol.append('struct_first：用了 L2 却没有 L1 尝试记录')
    if not readback:
        viol.append('unverified：动完没有回读（L3 缺）')
    row = {'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'level': level, 'channel': name,
           'target': target[:120], 'struct_tried': bool(struct_tried),
           'readback': bool(readback), 'ok': bool(ok), 'violations': viol, 'detail': detail[:200]}
    with _ledger_path().open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + chr(10))
    return {'ok': True, 'recorded': row, 'violations': viol}


def audit(limit: int = 200) -> dict:
    p = _ledger_path()
    if not p.exists():
        return {'ok': True, 'observed': 0, 'by_level': {}, 'violations': 0, 'note': '无观测'}
    rows = []
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines()[-limit:]:
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    by_level: dict = {}
    for r in rows:
        by_level[r.get('level')] = by_level.get(r.get('level'), 0) + 1
    viol = sum(1 for r in rows if r.get('violations'))
    l2 = sum(1 for r in rows if str(r.get('level')).upper() == 'L2')
    return {'ok': True, 'observed': len(rows), 'by_level': by_level, 'violations': viol,
            'l2_share': round(l2 / max(len(rows), 1), 3),
            'verdict': ('主通道是结构层 OK' if by_level.get('L1', 0) >= l2 else 'WARN 像素占比过高，检查 L1 是否真试过')}


def run(payload: dict | None = None) -> dict:
    p = dict(payload or {})
    op = str(p.get('op') or 'channels').strip().lower()
    if op == 'channels':
        return channels()
    if op == 'record':
        return record(str(p.get('level') or 'L1'), str(p.get('name') or ''), str(p.get('target') or ''),
                      bool(p.get('struct_tried')), bool(p.get('readback')), bool(p.get('ok', True)),
                      str(p.get('detail') or ''))
    if op == 'audit':
        return audit(int(p.get('limit') or 200))
    return {'ok': False, 'fail_closed': True, 'error': 'user_error: 未列出的 op（fail-closed）',
            'ops': ['channels', 'record', 'audit']}