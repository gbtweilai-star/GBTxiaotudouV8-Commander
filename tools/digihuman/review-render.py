# -*- coding: utf-8 -*-
r"""S12 渲染复核 · 把「这张图我看过了」写成**可核的凭据**（绑图片 sha256）。

## 为什么需要它
S12 的四层门里最后一层是 gate_review()：**没人看过的图不许自动判过**。
但那个门提示「看过之后跑 py -3.14 tools/digihuman/review-render.py」——
**而这个文件当时根本不存在**（我在门里引用了一个没建的工具）。
==这正是本仓最恨的那种坏法：判据指着一条不存在的出路，看的人以为有路可走。==
⇒ 本件把那句话兑现。

## 口径（写死）
  · 记录**必须绑当前 latest.png 的 sha256** —— 图一换，凭据立刻失效（gate_review 会判"复核已失效"）
  · **过与不过都要记**：不过要写清**为什么**（这就是"人眼那一层"的读数，不许只写个"不过"）
  · 复核人必填：**谁看的**要落下来，不许匿名

用法：
  py -3.14 -X utf8 tools/digihuman/review-render.py --by 自由的风            # 判过
  py -3.14 -X utf8 tools/digihuman/review-render.py --by 自由的风 --fail "姿态不是 T-pose：手臂朝上、看到的是后脑勺"
  py -3.14 -X utf8 tools/digihuman/review-render.py --show                   # 只读现存凭据
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[2]
IMG = ROOT / "holo_pet" / "assets" / "digital-human" / "render" / "latest.png"
REC = ROOT / "state" / "digihuman" / "render-review.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="S12 渲染复核（写绑哈希的复核凭据）")
    ap.add_argument("--by", help="复核人（必填，不许匿名）")
    ap.add_argument("--fail", help="判不过时写清为什么（给了它就记 失败）")
    ap.add_argument("--show", action="store_true", help="只读现存凭据")
    a = ap.parse_args()

    if a.show:
        if not REC.is_file():
            print("还没有复核凭据：%s 不在" % REC.relative_to(ROOT))
            return 0
        rec = json.loads(REC.read_text(encoding="utf-8"))
        now = hashlib.sha256(IMG.read_bytes()).hexdigest() if IMG.is_file() else ""
        fresh = (rec.get("图sha256") or "") == now
        print(json.dumps(rec, ensure_ascii=False, indent=1))
        print()
        print("新鲜：%s（记录 %s… / 现在 %s…）"
              % ("是" if fresh else "**否 —— 图换过了，这份凭据已失效**",
                 (rec.get("图sha256") or "")[:12], now[:12]))
        return 0

    if not IMG.is_file():
        print("缺渲染图（先跑 tools/digihuman/render-shot.py）")
        return 2
    if not a.by:
        print("必须写 --by <复核人> —— 复核是「谁看的」要落下来，不许匿名")
        return 2

    h = hashlib.sha256(IMG.read_bytes()).hexdigest()
    rec = {
        "图sha256": h,
        "复核人": a.by,
        "结论": "失败" if a.fail else "通过",
        "说明": (a.fail or "看图通过（取景/构图/可读性均达验收线）"),
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "_口径": "凭据**绑图片 sha256**：图一换即失效（gate_review 会判'复核已失效'）。过与不过都要落。",
    }
    REC.parent.mkdir(parents=True, exist_ok=True)
    REC.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已记复核凭据：%s" % REC.relative_to(ROOT))
    print("  图 sha256 %s… · 结论 **%s** · 复核人 %s" % (h[:12], rec["结论"], a.by))
    print("  说明：%s" % rec["说明"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
