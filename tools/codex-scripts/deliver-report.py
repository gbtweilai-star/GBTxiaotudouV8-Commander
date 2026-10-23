# -*- coding: utf-8 -*-
"""deliver-report -- 把总验收结果落成交付报告（主人令 2026-10-16）"""
import argparse, json
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
SIG = '开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属'


def newest_manifest():
    best = (0, {})
    for p in (ROOT / 'state' / 'train').glob('corpus_v*_manifest.json'):
        try:
            j = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        v = int(str(j.get('gen', 'v0')).lstrip('v') or 0)
        if v > best[0]:
            best = (v, j)
    return best[1]


def main():
    ap = argparse.ArgumentParser(description='验收交付报告')
    ap.add_argument('--out', default='docs/验收交付.md')
    args = ap.parse_args()
    rp = ROOT / 'state' / 'accept' / 'latest.json'
    if not rp.is_file():
        print('未读到 state/accept/latest.json => 先跑 accept-all.py')
        return 2
    rep = json.loads(rp.read_text(encoding='utf-8'))
    man = newest_manifest()
    rows = rep.get('rows') or []
    red = [r for r in rows if r.get('state') != 'OK']
    L = ['# GBT小土豆V8 · 验收交付报告', '', '> ' + SIG, '']
    L.append('- 生成时间：' + str(rep.get('at')))
    L.append('- 判定：**' + str(rep.get('verdict')) + '**（' + str(len(rows)) + ' 项 · 红 ' + str(len(red)) + '）')
    L.append('- 语料：**v' + str(man.get('gen')) + ' · ' + str(man.get('count')) + ' 条 · sha256 ' + str(man.get('sha256'))[:16] + '**')
    L += ['', '## 一、逐项结果', '', '| 组 | 项 | 现读 | 判据 | 判定 |', '|---|---|---|---|---|']
    for r in rows:
        L.append('| ' + str(r.get('group')) + ' | ' + str(r.get('item')) + ' | ' + str(r.get('reading')) + ' | ' + str(r.get('judge')) + ' | ' + str(r.get('state')) + ' |')
    if red:
        L += ['', '## 二、未过项（不许掩盖）', '']
        for r in red:
            L.append('- **' + str(r.get('group')) + ' / ' + str(r.get('item')) + '**：现读 ' + str(r.get('reading')) + '（判据 ' + str(r.get('judge')) + '）')
    L += ['', '## 三、复跑命令', '',
          '- 总验收：py -3.14 tools/codex-scripts/accept-all.py --model-answers <54题> --comfy-answers <秋叶版> --stress',
          '- 步进跟踪：py -3.14 tools/codex-scripts/brain-step-track.py --tail 20',
          '- 压力测试：py -3.14 tools/codex-scripts/tentacle-stress.py --n 6 --levels 1,4,8', '']
    out = ROOT / args.out
    out.write_text(chr(10).join(L), encoding='utf-8')
    print('交付报告已落 ' + str(out) + '（' + str(len(rows)) + ' 项 · 红 ' + str(len(red)) + ' · 判定 ' + str(rep.get('verdict')) + '）')
    return 0 if not red else 1


if __name__ == '__main__':
    raise SystemExit(main())
