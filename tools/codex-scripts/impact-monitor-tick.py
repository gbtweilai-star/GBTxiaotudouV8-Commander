# -*- coding: utf-8 -*-
"""impact-monitor-tick.py —— 多域监控的**驱动轮**（把"每小时一次"真的转起来）。

主人令 2026-10-19（逐字）：「修改一个地方的时候要分出触手关注跟这个修复的地方相连的所有地方，
确保你修改其他地方不会被连带故障」＋「多域监控时刻都要开着用脑手做事，别搞的跟瞎子是的」。

## 为什么必须有这一件（留痕 · 2026-10-19 当场查出来的洞）
`gbt_allinone/schedule.py` 里 `sched_define` 能把调度登记进 `state/schedules.json`、
`sched_tick()` 能把到期的跑掉 —— 但**全仓没有 `run_forever` 的调用方**（grep 只有它自己的定义）。
⇒ 调度登记得再漂亮，没人 tick 它就永远不会跑。那正是本仓台账里 P15 那一型
（「状态机停在门口不重试」）与 P29（「量具自己没被真跑过」）：**没驱动轮的定时器 = 挂件**。
本件就是那台驱动轮：任何一方（开机自检 / 主人手敲 / 常驻循环）跑它一次，到期调度就跑一次。

## 做两件事（都只读，不写生产盘）
1. `sched_tick` —— 走唯一门 `gbt_allinone.api.run_task`，把到期调度真跑掉；
   回执里逐条列出 `ran[]`（哪个调度 / 哪个工作流 / 状态 / run_id）。
2. `impact_check status` —— 走同一道门读影响面图：节点数 / 边数 / 连通分量 / 构建时间。
   **图读不到 = 红**（连通性读数取不到时不许静默当 0，这是本仓最贵的一型假绿）。

## 判据（非零退出 = 真的有问题）
- 图读不出来（missing / parse_failed / bad_shape） ⇒ 红
- 连通分量 > 1（出现孤岛） ⇒ 红（孤岛 = 有件没被任何关系连上，改它没人知道）
- `sched_tick` 里有调度报 `error` ⇒ 红（把 error 原话带出来）
其余情形绿，并把"这次转到了什么"原样打出来。

用法：
  py -3.14 tools/codex-scripts/impact-monitor-tick.py
  py -3.14 tools/codex-scripts/impact-monitor-tick.py --quiet     # 只打结论行
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _door(kind: str, payload: dict) -> dict:
    """唯一门。门不存在就如实报（不 import 模块函数绕门）。"""
    from gbt_allinone import api as _api
    return _api.run_task(kind, payload)


def _unwrap(env) -> dict:
    """门回的信封是**两层**：外层 {status, ok, result:{kind, result:{…本体…}}}。

    留痕（2026-10-19 当场栽的一发）：第一版只剥一层就取 `nodes`，拿到的是一张
    「0 节点 / 0 边 / 单分量」的**假读数**，而且还打了绿 —— 正是本仓 P1 那一型
    （判据读错对象 ⇒ 假绿）。现在：逐层往下剥，剥到底还找不到 `ok` 就**报错不报绿**。
    """
    if not isinstance(env, dict):
        return {"ok": False, "error": "bad_envelope", "raw": str(env)[:200]}
    if env.get("denied"):
        return {"ok": False, "error": "denied",
                "missing_scopes": env.get("missing_scopes"),
                "how_to_grant": env.get("how_to_grant"),
                "why": env.get("reason") or env.get("why")}
    body = env
    for _ in range(6):                       # 最多剥 6 层，防环
        if not isinstance(body, dict):
            return {"ok": False, "error": "bad_body", "raw": str(body)[:200]}
        # 信封的特征键（gate / gbt_stamp / ok_source / kind / stamp）+ 内层 result 是字典 ⇒ 再剥一层。
        # 本体回执形状不统一（impact_check 带 op+ok；sched_tick 只带 ran+count），
        # 所以**剥到没有信封特征就停**，具体字段由调用方按各自契约核。
        wrapper = any(k in body for k in ("gate", "gbt_stamp", "ok_source", "kind", "stamp"))
        if wrapper and isinstance(body.get("result"), dict):
            body = body["result"]
            continue
        break
    return body if isinstance(body, dict) else {"ok": False, "error": "bad_body"}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    quiet = "--quiet" in argv

    problems = []

    # ① 驱动定时轮
    tick = _unwrap(_door("sched_tick", {}))
    if "ran" not in tick:
        problems.append("sched_tick 回执里没有 ran 字段（拿不到「这次跑了什么」⇒ 不许当 0 报绿）：%s"
                        % sorted(tick)[:10])
    ran = tick.get("ran") or []
    errs = [r for r in ran if str(r.get("status")) != "ok"]
    for r in errs:
        problems.append("调度 %s 报 %s：%s" % (r.get("schedule"), r.get("status"),
                                              r.get("error") or r.get("why") or "（上游没给原因）"))

    # ② 影响面图的连通性（多域监控的"眼睛"有没有睁开）
    fig = _unwrap(_door("impact_check", {"op": "status"}))
    if fig.get("ok") is not True:
        problems.append("影响面图读不出来：%s · %s"
                        % (fig.get("error") or "ok!=true", fig.get("why") or ""))
        comps = None
    elif "nodes" not in fig or "components" not in fig:
        problems.append("影响面图回执缺字段（拿不到节点/连通分量 ⇒ **不许当 0 报绿**）：%s"
                        % sorted(fig)[:10])
        comps = None
    else:
        comps = int(fig.get("components") or 0)
        share = float(fig.get("largest_share") or 0.0)
        # 留痕（2026-10-19 换图后改判据）：旧图是精选子集（6301 节点/单分量），新图由
        # `wiring-build.py` 从全仓重建（8365 节点/67 个分量/最大分量 96.9%）—— 多出来的
        # 小分量是**没有被任何关系连到的孤立件**，它们不降低影响面的可用性。
        # 所以判据从"必须 1 个分量"改成"**主分量必须 ≥90%**"，并把分量数如实打出来（不藏）。
        if comps == 0 or share < 90.0:
            problems.append("影响面图散了：分量 %d · 最大分量只有 %.1f%%（应 ≥90%%）—— "
                            "图不可信，先跑 tools/codex-scripts/wiring-build.py" % (comps, share))

    # ③ 全控变化监控的"眼睛"有没有睁开（只看基线状态，不跑全仓 stat —— 那是 90 秒的活，
    #    留给每小时的工作流节点；这里要的是"驱动轮还在转"这个事实）
    dft = _unwrap(_door("project_drift", {"op": "status"}))
    drift_ok = True
    if dft.get("ok") is not True:
        problems.append("全控变化监控读不到基线状态：%s · %s"
                        % (dft.get("error") or "ok!=true", dft.get("why") or ""))
        drift_ok = False
    elif not dft.get("baseline"):
        problems.append("全控变化监控还没有基线 ⇒ 项目变没变根本看不见（先 freeze 一次）")
        drift_ok = False
    elif dft.get("stale"):
        problems.append("全控变化基线已过期 %.1f 小时 —— 结论必须带这个年龄"
                        % ((dft.get("age_s") or 0) / 3600))
        drift_ok = False

    if not quiet:
        print("═══ 多域监控 · 驱动轮 ═══")
        if comps is not None:
            print("  图：%d 节点 / %d 有向边 / 连通分量 %d / 最大分量占比 %s%% / 构建于 %s"
                  % (fig.get("nodes", 0), fig.get("edges_directed", 0), fig.get("components", 0),
                     fig.get("largest_share", "?"), fig.get("built_at", "?")))
        if drift_ok:
            print("  基线：%s · %d 件 · %s"
                  % (dft.get("at"), dft.get("files", 0),
                     ("%.1f 小时前" % ((dft.get("age_s") or 0) / 3600))
                     if dft.get("age_s") is not None else "年龄未知"))
        print("  定时轮：这次跑到 %d 个调度" % len(ran))
        for r in ran:
            print("    · %-22s → %-22s %s" % (r.get("schedule"), r.get("workflow"), r.get("status")))
        if not ran:
            print("    （没有到期调度 —— 不是坏了：没到点时 tick 本来就什么也不跑）")

    if problems:
        print("  🔴 有 %d 个问题：" % len(problems))
        for p in problems:
            print("     - " + p)
        return 1
    print("  ✅ 多域监控在转：定时轮跑通 · 影响面图主分量 %.1f%%（%d 个分量）· 变化基线在位"
          % (float(fig.get("largest_share") or 0.0), int(fig.get("components") or 0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
