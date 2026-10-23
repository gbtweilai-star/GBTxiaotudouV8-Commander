# -*- coding: utf-8 -*-
# gbt-capability: fact_gate
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""fact_gate —— 机器事实直答门（主人令 2026-10-11「拿实质性证据说话，禁止胡说八道」）。

## 为什么要它（今天三次重训 + 十轮提示词的实证）
  · 重训权重 v12→v17→v19：**编事实照旧**（编出 voice_to_midi／comfyui 0.39.1）⇒ 权重治不了；
  · 加提示词规矩约 10 轮：**每加一条，失败模式换一种**（从「编」漂到「过度否定真证据」）⇒ 边际递减；
  · 框架把**现读／现查**喂进去：**结论层稳定正确**，只剩**细节层**会润色证据（编出处／否掉真证据）。
  ⇒ 结论：**「事实」这件事根本不该过语言模型** —— 模型天生会润色证据。

## 怎么干
  机器事实类问题（在位／装了／通不通／端口／内存／有没有能力位／版本／多少）：
    ① 现读（框架自己跑；读不到就写读不到）→ ② 代码判定（是/否/命中几个）→
    ③ 原文引用（读数原字贴出，不许转述）→ ④ 直答返回，**不调模型**。
  模型只在后面加「所以怎么办」（可选），且**不许碰事实段**。

## 铁律
  · **门的读数不许转述，只许原样贴**；
  · **读不到就写读不到**（不编）；
  · **判定由代码做**（命中有没有、端口通不通），不许由模型推断；
  · 模型段与事实段**物理分开**（事实段带前缀，便于人核对）。
"""
from __future__ import annotations

import json
import pathlib
import re
import socket

_ROOT = pathlib.Path(__file__).resolve().parents[2]

# 机器事实类问题的判据（问的是客观现状，不是「怎么想／怎么做」）
FACT_MARKERS = (
    '在位', '装了', '安装', '通不通', '通吗', '端口', '内存', '磁盘', '硬盘',
    '有没有能力位', '能力位有没有', '有多少能力位', '多少条', '版本',
    '能不能本地', '扫得到', '连得上', '跑得动', '支不支持', '有没有接口',
)


def classify(prompt: str) -> bool:
    """是不是机器事实类问题。"""
    p = str(prompt or '')
    if not p:
        return False
    if any(m in p for m in FACT_MARKERS):
        return True
    # 2026-10-11 修（实测漏网）：「有没有**蓝牙**能力位」—— '有没有能力位' 是连读子串，中间插了词就漏 ✗
    if re.search(r'有(没有|无)[^。，？?]{0,12}(能力位|接口|功能|工具|办法|方式)', p):
        return True
    if re.search(r'(能力位|接口)[^。，？?]{0,8}有(没有|无)', p):
        return True
    return bool(re.search(r'\d{2,5}\s*(端口|port)', p, re.I))


def _port(p: int, t: float = 0.35) -> bool:
    s = socket.socket()
    s.settimeout(t)
    try:
        return s.connect_ex(('127.0.0.1', p)) == 0
    except Exception:                                  # noqa: BLE001
        return False
    finally:
        s.close()


def gather(prompt: str) -> dict:
    """现读 + 代码判定 + 原文引用（全部在代码里做，不过模型）。"""
    facts: list = []
    verdicts: list = []
    srcs: list = []
    p = str(prompt or '')
    if ('能力位' in p) or ('有没有' in p) or ('支持' in p):
        try:
            from . import cloud_llm as _cl
            lk = _cl._cap_lookup(p)
            if lk:
                facts.append(lk.strip())
                srcs.append('注册表 BENIGN_CAPS（现查）')
                n = re.search(r'命中 \*\*(\d+) 个\*\*', lk)
                verdicts.append('能力位现查：命中 %s 个' % (n.group(1) if n else '0'))
        except Exception as e:                          # noqa: BLE001
            facts.append('- 能力位现查：失败（%s）' % type(e).__name__)
    for m in re.finditer(r'(\d{4,5})', p):
        pt = int(m.group(1))
        if 80 <= pt <= 65535:
            ok = _port(pt)
            facts.append('- 端口 %d：%s（本机回环实测）' % (pt, '通' if ok else '不通'))
            verdicts.append('端口 %d %s' % (pt, '通' if ok else '不通'))
            srcs.append('socket connect_ex 127.0.0.1:%d' % pt)
            break
    if 'comfy' in p.lower() or '8188' in p:
        try:
            from ..tools import tentacle_comfy_bridge as _cb
            st = _cb.status()
            facts.append('- ComfyUI：在位=%s · %s' % (st.get('in_position'), str(st.get('why'))[:80]))
            verdicts.append('ComfyUI 在位=%s' % st.get('in_position'))
            srcs.append('tentacle_comfy_bridge.status()')
        except Exception as e:                          # noqa: BLE001
            facts.append('- ComfyUI：探测失败（%s）' % type(e).__name__)
    if ('内存' in p) or ('磁盘' in p) or ('硬盘' in p):
        try:
            import psutil
            vm = psutil.virtual_memory()
            facts.append('- 内存：总 %.2f GB / 可用 %.2f GB' % (vm.total / 1e9, vm.available / 1e9))
            verdicts.append('内存总 %.2fGB 可用 %.2fGB' % (vm.total / 1e9, vm.available / 1e9))
            srcs.append('psutil.virtual_memory()')
        except Exception:                               # noqa: BLE001
            facts.append('- 内存：读不到（psutil 缺失）')
    if ('能力位' in p) and (('多少' in p) or ('总共' in p)):
        try:
            a = json.loads((_ROOT / 'state' / 'skill_atlas.json').read_text(encoding='utf-8'))
            facts.append('- 能力位总数：%d（图鉴 built_at %s）' % (len(a.get('caps') or []), a.get('built_at')))
            verdicts.append('能力位总数 %d' % len(a.get('caps') or []))
            srcs.append('state/skill_atlas.json')
        except Exception as e:                          # noqa: BLE001
            facts.append('- 能力位总数：读不到（%s）' % type(e).__name__)
    return {'facts': facts, 'verdicts': verdicts, 'sources': srcs}


def answer(prompt: str) -> dict:
    """直答：事实段（代码产）+ 出处（原文）。不调模型。"""
    g = gather(prompt)
    if not g['facts']:
        return {'ok': False, 'mode': 'fact_gate', 'reason': 'no_fact_matched'}
    lines = ['**【事实直答 · 未经语言模型转述】**', '']
    lines += g['facts']
    lines.append('')
    lines.append('**判定（代码做的）**：' + ('；'.join(g['verdicts']) or '无'))
    lines.append('**出处（原文）**：' + ('；'.join(g['sources']) or '无'))
    lines.append('')
    lines.append('（读不到就写读不到；本节由 fact_gate 直出，模型不得改动。）')
    return {'ok': True, 'mode': 'fact_direct', 'answer': '\n'.join(lines),
            'facts': g['facts'], 'verdicts': g['verdicts'], 'sources': g['sources']}
