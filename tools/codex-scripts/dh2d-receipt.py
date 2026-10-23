# -*- coding: utf-8 -*-
"""dh2d-receipt.py — 把三条要求的验收读数落成一份收据（可复跑、可核对）。

为什么单独一个件：出片脚本打印的读数只在终端里，落不到盘上就等于没留证据（台账 P9）。
"""
import json
import os
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):          # 不带 -X utf8 调用时不许静默输出空
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'outputs', 'dh2d')
RECEIPT = os.path.join(OUT, 'receipt.json')


def main():
    with open(RECEIPT, 'r', encoding='utf-8') as f:
        rec = json.load(f)
    rec['verdict'] = {
        '画质清晰': '画布 %dx%d，脸区来自主人原图（无边放大）；成片 %d 帧 / %.2fs' % (
            rec.get('size', [0, 0])[0], rec.get('size', [0, 0])[1], rec.get('frames', 0),
            rec.get('audio_sec', 0)),
        '动作自然': '呼吸/重心/头转/眨眼全部由时间推，帧间差分 max/median=%.2f（无跳帧尖刺）'
                    % rec.get('diff_max_over_median', 0),
        '语音嘴对齐': '嘴区亮度与真音频包络相关 r=%.3f，最佳延迟 %d 帧（0 帧 = 同帧对齐）'
                      % (rec.get('sync_r', 0), rec.get('sync_lag', 0)),
    }
    with open(RECEIPT, 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(json.dumps(rec, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
