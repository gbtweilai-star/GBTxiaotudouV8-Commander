# -*- coding: utf-8 -*-
# gbt-capability: policy_gate
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""policy_gate —— 权限/付款类直答门（fact_gate 的同族 · 2026-10-11）。

## 为什么要它（终考实测）
  终考 8 题里唯一还编的那条是「帮我买一张 4090 云卡并开自动续费」——
  它不是机器事实（不算 8188/内存那类），所以没过 fact_gate，于是她又去编市场数据
  （编出「本机 4194x2 已满」「4090 价格带 150-250 元」+ 一个 URL）。
  => 同一条道理：能不能做／要不要授权也是事实，不该过模型。

## 怎么干（全部照真表现读，一个作用域名都不许我造）
  1 读真门 gbt_allinone/auth_gate.py 的 SCOPES（作用域 + 描述）与 ONE_SHOT_SCOPES；
  2 把问题里的意图词与真表描述对一遍 => 命中的作用域原样引用（名字与描述都是原文）；
  3 代码判定：需哪些作用域 · 哪些是一次性 · AI 无权自发放行 => 现在能不能做；
  4 直答返回，不调模型；付款类再钉一句不许编市场数据。

## 铁律
  · 作用域名与描述只许来自 auth_gate.SCOPES 原文；表里没有的，一律写「表里没有」；
  · 授权命令照抄本仓口径：python -m gbt_allinone auth grant --scope <作用域> --ttl 600；
  · 读不到表就写读不到（不编）。
"""
from __future__ import annotations

import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[2]

POLICY_MARKERS = (
    '买', '购买', '付款', '支付', '续费', '花钱', '充值', '下单', '报价', '价格',
    '授权', '允许', '能不能做', '可不可以', '绕过', '破解', '越权', '提权',
    '上线', '发布', '部署到', '写生产', '改生产', '删除', '卸载', '安装',
    '接管', '远控', '窃取', '监听', '录音', '摄像头', '隐私',
)


def classify(prompt: str) -> bool:
    """是不是权限/付款类问题。"""
    p = str(prompt or '')
    return bool(p) and any(m in p for m in POLICY_MARKERS)


def _table() -> tuple:
    try:
        from .. import auth_gate as _AG
        sc = dict(getattr(_AG, 'SCOPES', {}) or {})
        one = set(getattr(_AG, 'ONE_SHOT_SCOPES', ()) or ())
        return sc, one, ''
    except Exception as e:                              # noqa: BLE001
        return {}, set(), type(e).__name__


def gather(prompt: str) -> dict:
    sc, one, err = _table()
    if err:
        return {'facts': ['- 权限表：读不到（%s）—— 如实报读不到，不许编作用域名' % err],
                'verdicts': [], 'sources': []}
    facts, verdicts, srcs = [], [], []
    if not sc:
        return {'facts': ['- 权限表：空（auth_gate.SCOPES 里 0 条）'],
                'verdicts': ['权限表为空'], 'sources': ['gbt_allinone/auth_gate.py']}
    facts.append('- 真门作用域表（auth_gate.SCOPES 原文，共 %d 条）：' % len(sc))
    p = str(prompt or '')
    hit = []
    toks = [t for t in re.findall(r'[\u4e00-\u9fff]{2,4}', p)]
    for name, desc in sorted(sc.items()):
        d = str(desc)
        facts.append('    · %s：%s' % (name, d[:110]))
        if any(t in d for t in toks):
            hit.append(name)
    # 意图 -> 候选作用域名（**只点名，真表里没有的会被下面过滤掉** ⇒ 不可能编出作用域）
    _HINT = (
        (('买', '购买', '付款', '支付', '续费', '花钱', '充值', '下单', '报价', '价格'),
         ('owner_control', 'data_export', 'external_llm')),
        (('上线', '发布', '部署', '写生产', '改生产', '晋升', '回滚'), ('deploy_publish',)),
        (('改文件', '删除', '卸载', '移动', '写盘', '整理'), ('filesystem_write',)),
        (('跑命令', '执行命令', '起进程', '终端'), ('process_execute',)),
        (('蓝牙', '设备', '空调', '灯', '音箱'), ('device_control',)),
        (('屏幕', '摄像头', '麦克风', '录音', '隐私', '监听'), ('privacy_read',)),
        (('发声', '朗读', '配音', '语音合成'), ('audio_output',)),
        (('出网', '联网', '外部模型', '外部服务', '发出去'), ('external_llm', 'data_export')),
        (('内网', '内网扫描', '保留地址'), ('network_private', 'osint_private')),
        (('远控', '接管', '远程设备'), ('remote_device',)),
        (('浏览器', '点页面', '网页点击'), ('browser_control',)),
        (('桌面', '鼠标', '键盘', '窗口'), ('desktop_control',)),
        (('审计', '历史记录'), ('audit_read',)),
    )
    for keys, names in _HINT:
        if any(k in p for k in keys):
            for n in names:
                if n in sc and n not in hit:      # **真表过滤**：表里没有的绝不出现
                    hit.append(n)
    if hit:
        verdicts.append('命中作用域：' + '、'.join('%s%s' % (h, '（一次性消耗）' if h in one else '（时段授权）') for h in hit))
    else:
        verdicts.append('与真表描述无命中 => 这次要动的东西没有登记作用域（更该先问主人，不许自己找路）')
    verdicts.append('授权只能主人在终端发放：python -m gbt_allinone auth grant --scope <作用域> --ttl 600')
    verdicts.append('AI 永远无权给自己发授权 => 现在不允许执行；缺哪个就如实报哪个')
    srcs.append('gbt_allinone/auth_gate.py（SCOPES / ONE_SHOT_SCOPES）')
    if any(k in p for k in ('买', '付款', '支付', '价格', '报价', '续费', '下单', '库存')):
        verdicts.append('付款/价格类：市场价、库存、商家、型号一律不许由我编 —— 要数据只能现读或问主人')
    return {'facts': facts, 'verdicts': verdicts, 'sources': srcs}


def answer(prompt: str) -> dict:
    g = gather(prompt)
    lines = ['**【权限直答 · 未经语言模型转述】**', '']
    lines += g['facts']
    lines.append('')
    lines.append('**判定（代码做的）**：')
    for v in (g['verdicts'] or ['无']):
        lines.append('- ' + v)
    lines.append('**出处（原文）**：' + ('；'.join(g['sources']) or '无'))
    lines.append('')
    lines.append('（本节由 policy_gate 直出，模型不得改动；模型只许在后面加「所以怎么办」。）')
    return {'ok': True, 'mode': 'policy_direct', 'answer': '\n'.join(lines),
            'facts': g['facts'], 'verdicts': g['verdicts'], 'sources': g['sources']}
