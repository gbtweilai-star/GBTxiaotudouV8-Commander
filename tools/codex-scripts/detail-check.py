# -*- coding: utf-8 -*-
# gbt-capability: detail-habit  ⏛ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""逐步细节化判据（detail-check）——把「做事细节化」从口号变成会红的必要条件。

主人令（2026-10-09）：「给她设计一个习惯，做事细节化的习惯，每一步都要细节化」。
本仓旧训：「口号不会自己红」⇒ 习惯必须配一道**机器判据**。

五问（每一步必答，缺一就红）：
  输入 · 动作 · 明细 · 判据 · 接点
其中「明细」硬要求：必须是**逐项**（≥ 1 条的列表）——
只给一个合计数 = 没有细节（本仓已有同族教训：「报一个总数不算读数」）。

用法：
  py -3.14 tools/codex-scripts/detail-check.py --selftest      # 正例绿 / 负例红（自证它真能咬）
  py -3.14 tools/codex-scripts/detail-check.py <报告.json>  # 查真报告
退出码：0 全过 · 1 有缺 · 2 用法错。
"""
from __future__ import annotations

import json
import sys

QUINTET = ("输入", "动作", "明细", "判据", "接点")


def check(report: dict) -> dict:
    """逐步查五问。返回 ok / fails（逐条可指名）。"""
    steps = (report or {}).get("steps") or (report or {}).get("report") or []   # 原生报告用 report，外封装用 steps
    if not steps:
        return {"ok": False, "steps": 0, "fails": ["报告里没有 steps（拿什么判细节？）"]}
    fails = []
    for i, s in enumerate(steps, 1):
        name = str(s.get("step") or s.get("name") or "第%d步" % i)
        # 五问可以**平铺**在步骤条目上，也可以收在 `详细` 里（原生报告用后者，更整洁）
        b = s.get("详细") if isinstance(s.get("详细"), dict) else s
        for k in QUINTET:
            if k not in b:
                fails.append("%s 缺「%s」" % (name, k))
        d = b.get("明细")
        if d is not None and (not isinstance(d, list) or len(d) < 1):
            fails.append("%s 的「明细」不是逐项（必须是 ≥1 条的列表，"
                         "现在是 %s）" % (name, type(d).__name__))
        j = b.get("判据")
        if isinstance(j, dict) and "过" not in j:
            fails.append("%s 的「判据」没给过/不过" % name)
        elif j is None:
            fails.append("%s 的「判据」是空的" % name)
    return {"ok": not fails, "steps": len(steps), "fails": fails}


_GOOD = {"steps": [
    {"step": "assets", "输入": {"脚本": "x.md"},
     "动作": "ffmpeg 逐镜渲染 + 链装", "明细": [{"no": 1, "dur": 5.0}, {"no": 2, "dur": 5.0}],
     "判据": {"过": True, "出处": "镜序与脚本一致"}, "接点": "x.mp4"},
]}
_BAD_MISSING = {"steps": [dict(_GOOD["steps"][0], **{})]}
_BAD_MISSING["steps"][0].pop("接点")
_BAD_TOTAL = {"steps": [dict(_GOOD["steps"][0], **{"明细": 4})]}          # 只报合计
_BAD_EMPTY = {"steps": [dict(_GOOD["steps"][0], **{"明细": []})]}
_BAD_NOJUDGE = {"steps": [dict(_GOOD["steps"][0], **{"判据": {"出处": "x"}})]}
_BAD_NOSTEPS = {"steps": []}


def selftest() -> int:
    cases = [("正例·五问齐且逐项", _GOOD, True),
             ("负例·缺接点", _BAD_MISSING, False),
             ("负例·明细只报合计", _BAD_TOTAL, False),
             ("负例·明细为空", _BAD_EMPTY, False),
             ("负例·判据没说过/不过", _BAD_NOJUDGE, False),
             ("负例·报告里没 steps", _BAD_NOSTEPS, False)]
    bad = 0
    for name, rep, want in cases:
        got = check(rep)
        flag = "✅" if got["ok"] == want else "❌"
        print("%s %-28s 期望 ok=%-5s 得到 ok=%-5s %s"
              % (flag, name, want, got["ok"], ("| " + "；".join(got["fails"])[:60]) if got["fails"] else ""))
        if got["ok"] != want:
            bad += 1
    print("自检：%d 例里 %d 例不符合预期" % (len(cases), bad))
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if "--selftest" in args:
        return selftest()
    if not args:
        print("用法：detail-check.py --selftest | <报告.json> | --stdin", file=sys.stderr)
        return 2
    try:
        raw = sys.stdin.read() if args[0] == "--stdin" else open(args[0], encoding="utf-8").read()
        rep = json.loads(raw)
    except Exception as e:                                            # noqa: BLE001
        print("读不了这份报告：%s" % str(e)[:120], file=sys.stderr)
        return 2
    res = check(rep)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
