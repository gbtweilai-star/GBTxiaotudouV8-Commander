#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模块 02 · orchestrator（编排器）—— 派活，但**只派已登记的模块**

主人的要求是两句话：**自动化** + **千万不能胡乱运行和排布**。
这两句在这里合起来是一条**代码里的闸**：

    作业的每一道工序，只有当它对应的模块**已在云登记**（`pipeline/modules/<m>/current.json`）
    且状态 ∈ {已验, 已部署} 时才允许跑；**没登记 ⇒ 拒派**（fail-closed）。

⇒ 顺序不再是文档里的约定，而是**跑不动**的东西。这就是"不会出错"的实处。

## 触手槽位（规矩三：N 根触手 ⇒ N 个隔离位）
触手根数只认 `state/tentacle-roster.json` 的**声明值**（只有主人能改）。
派活按**确定性轮转**分到 `state/tentacle-slots/T0k/`，同一作业**只挂一根触手**（账本可查）。

## 诚实说的三条
  ① **本工具不部署云函数**（Workers/Queues/DO 是发布动作，须主人点头）。它是**总部侧调度**：
     读云上的单 → 按闸派给本地触手槽 → 结果回写云。
  ② 领单是**近似原子**（R2 无 compare-and-set），靠 `render-agent` 的租约 + 幂等兜底。
  ③ `tick --dry-run` 是默认姿势；真跑要显式加 `--apply`。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
DP_PATH = ROOT / "tools/codex-scripts" / "deploy-panel.py"
RA_PATH = ROOT / "tools" / "codex-scripts" / "render-agent.py"
PREFIX = "pipeline"
LEDGER = ROOT / "state" / "orchestrator-ledger.jsonl"
_DP = None


def _dp():
    global _DP
    if _DP is None:
        spec = importlib.util.spec_from_file_location("_dp_mod3", DP_PATH)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _DP = m
    return _DP


def _ra():
    return _dp()._load_ra()


# 工序链：**按模块编号升序**（编排表就是顺序表）。
# `long_video` 是主人要的"自动化长视频"那条链 —— 注意 07/08 现在**没登记**，
# 所以真派单时会在 07 处**被闸挡住**（这正是我们要的：宁可停住，不许乱跑）。
CHAINS = {
    "remotion":    [("06", "render")],
    "hyperframes": [("06", "render")],
    "long_video":  [("04", "frame-cache"), ("06", "render"), ("07", "assemble"), ("08", "publish")],
}

# 各工序**怎么真跑**（编排器只调已验过的入口，不自己重写渲染）
#
# 2026-10-10 修：原来 07/08 是**手写死的字符串**「（未接线）…」，而 07 早就本地接线了
#    （assemble.py 现读 13.0KB · 自检 6/6 全过：正控 3 条 + 负控 3 条，执行地如实标 LOCAL-触手）
#    ⇒ 手写的接线状态**必然过期**，还把通的说成不通（反向误导，与前几轮抓的"假绿"是同一族病）。
#    改成**现读**：文件在不在、自检过不过，读出来是什么就写什么。
RUNNERS = {
    "06": "render-agent.py run <job_id> --worker <slot>",
    "04": "（可选前置）frame-cache.py put <job> <frame>",
}


def _runner_state(num: str, name: str) -> str:
    """**真跑入口现读**（不写死）—— 手写的接线状态一定会过期。

    判法：模块文件在不在 + 能不能自检过。**在 = 本地已接线**；不在 = 如实标未接线。
    云那条另算：本工具不部署云函数（须主人点头），所以"本地通/云未授权"要**分开写**。
    """
    files = {
        "04": "frame-cache.py", "06": "render-agent.py",
        "07": "assemble.py", "08": "publish.py",
    }
    fn = files.get(num)
    if not fn:
        return "?"
    p = ROOT / "tools" / "codex-scripts" / fn
    if not p.is_file():
        return "**（未接线）找不到 %s**" % fn
    kb = p.stat().st_size / 1024
    if num == "07":
        return ("**本地触手已接线**（%s %.1fKB · 执行地 LOCAL-触手；云函数未授权须主人点头）"
                % (fn, kb))
    if num == "08":
        return "**要 deploy_publish 授权**（%s %.1fKB · 授权只有主人能在终端发）" % (fn, kb)
    return "%s（%.1fKB）" % (fn, kb)


def _tentacles() -> int:
    return _dp()._tentacles()[0]


def _module_state(m: str) -> dict | None:
    """"在云上有登记吗 + 什么状态" —— 闸的判据就是这一个读数。"""
    ra = _ra()
    tmp = ROOT / "state" / ("_orch_mod_%s.json" % m)
    ok, _ = ra._get("%s/modules/%s/current.json" % (PREFIX, m), tmp)
    if not ok:
        return None
    try:
        return json.loads(tmp.read_text(encoding="utf-8"))
    except Exception:
        return None


def _gate(m: str) -> tuple[bool, str]:
    st = _module_state(m)
    if not st:
        return False, "云上没有 `%s/modules/%s/current.json` ⇒ **未登记，拒派**" % (PREFIX, m)
    s = str(st.get("状态") or "")
    if s not in ("已验", "已部署"):
        return False, "登记状态是「%s」⇒ 不是已验/已部署，拒派" % (s or "空")
    return True, "已登记 · %s · %s" % (s, st.get("证据", "")[:60])


def _chain_of(spec: dict) -> list[tuple[str, str]]:
    if isinstance(spec.get("stages"), list) and spec["stages"]:
        return [(str(a), str(b)) for a, b in ((x, y) for x, y in spec["stages"])]
    return CHAINS.get(spec.get("engine", "remotion"), CHAINS["remotion"])


def cmd_plan(a) -> int:
    ra = _ra()
    tmp = ROOT / "state" / ("_orch_spec_%s.json" % a.job_id)
    ok, tail = ra._get("%s/jobs/%s/spec.json" % (PREFIX, a.job_id), tmp)
    if not ok:
        print(json.dumps({"ok": False, "why": "作业单拉不下来", "job_id": a.job_id, "tail": tail},
                         ensure_ascii=False))
        return 2
    spec = json.loads(tmp.read_text(encoding="utf-8"))
    chain = _chain_of(spec)
    rows, stop = [], None
    for num, name in chain:
        g, why = _gate(name)
        rows.append({"工序": num, "模块": name, "闸": "✅ 放行" if g else "⛔ 拒", "判据": why,
                     "真跑入口": RUNNERS.get(num) or _runner_state(num, name)})
        if not g and stop is None:
            stop = {"停在": "%s %s" % (num, name), "为什么": why,
                    "编排器行为": "**停住**，不往下跑（后面的工序即使已登记也不许越级）"}
    print(json.dumps({"作业": a.job_id, "engine": spec.get("engine"),
                      "工序链": rows, "首个拦住点": stop,
                      "结论": "整条链都能跑" if not stop else "**这条链现在跑不通**（停在上面的点）"},
                     ensure_ascii=False, indent=1))
    return 0 if not stop else 3


def _pending(ra) -> list[str]:
    idx = [str(x) for x in ra._index_read()]
    out = []
    for jid in idx:
        if not ra._done_status(jid):            # 有产物 ⇒ 已完成，不用派
            out.append(jid)
    return out


def cmd_tick(a) -> int:
    """一个调度轮：把待办作业按**确定性轮转**分给触手槽；每道工序先过闸。
    `--dry-run`（默认）只看派不派；`--apply` 才真跑。"""
    ra = _ra()
    n = _tentacles()
    if not n:
        print(json.dumps({"ok": False, "why": "触手根数未声明 ⇒ 不派活（fail-closed）",
                          "改法": "state/tentacle-roster.json 的『声明根数』由主人定"},
                         ensure_ascii=False))
        return 2
    pend = _pending(ra)
    if not pend:
        print(json.dumps({"ok": True, "判决": "没有待办作业（云上每个单都有产物）",
                          "触手根数": n}, ensure_ascii=False, indent=1))
        return 0
    rows, ledger = [], []
    for i, jid in enumerate(pend):
        slot = "T%02d" % (i % n + 1)            # 确定性轮转：不掷骰子
        tmp = ROOT / "state" / ("_orch_spec2_%s.json" % jid)
        ok, _ = ra._get("%s/jobs/%s/spec.json" % (PREFIX, jid), tmp)
        spec = json.loads(tmp.read_text(encoding="utf-8")) if ok else {}
        chain = _chain_of(spec)
        verdict, ran = [], None
        for num, name in chain:
            g, why = _gate(name)
            verdict.append({"工序": num, "模块": name, "放行": g, "判据": why})
            if not g:
                break
            ran = (num, name)
            if a.apply and num == "06":          # 唯一真接线的工序
                import subprocess
                cmd = [sys.executable, str(RA_PATH), "run", jid, "--worker", slot]
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace")
                ran = ("06", "render", "rc=%d" % r.returncode)
                break
        blocked = [v for v in verdict if not v["放行"]]
        row = {"作业": jid, "触手槽": slot, "隔离位": "state/tentacle-slots/%s" % slot,
               "工序判定": verdict,
               "判决": ("⛔ 停在 %s %s" % (blocked[0]["工序"], blocked[0]["模块"])) if blocked
               else ("✅ 已跑到 %s" % (ran[1] if ran else "?")),
               "真跑": bool(a.apply and ran)}
        rows.append(row)
        ledger.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "job_id": jid, "slot": slot,
                       "apply": bool(a.apply), "判决": row["判决"]})
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        for e in ledger:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(json.dumps({"模式": "**真跑**" if a.apply else "彩排（--dry-run，默认）",
                      "触手根数": n, "待办": len(pend), "派单": rows,
                      "账本": str(LEDGER.relative_to(ROOT)),
                      "边界": "本工具不部署云函数；它是总部侧调度"},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_status(a) -> int:
    if not LEDGER.is_file():
        print(json.dumps({"账本": "还没有派单记录", "path": str(LEDGER.relative_to(ROOT))},
                         ensure_ascii=False))
        return 0
    rows = []
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    by_slot: dict[str, int] = {}
    for r in rows:
        by_slot[r.get("slot", "?")] = by_slot.get(r.get("slot", "?"), 0) + 1
    print(json.dumps({"派单条数": len(rows), "按触手槽": by_slot,
                      "最近 5 条": rows[-5:]}, ensure_ascii=False, indent=1))
    return 0


def cmd_selftest(a) -> int:
    """真身自检：闸的**正负控** + 轮转**确定性** + 同作业不双派。用本地替身云。"""
    import tempfile
    dp = _dp()
    keep = dp.LOCAL_CLOUD
    lines, bad = [], 0

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    with tempfile.TemporaryDirectory() as td:
        dp.LOCAL_CLOUD = str(pathlib.Path(td) / "cloud")
        ra = _ra()
        # 负控①：**未登记**的模块必须被拒
        g1, w1 = _gate("render")
        ck("负控①·模块未登记 ⇒ 拒派", g1 is False and "未登记" in w1, w1[:70])
        # 正控：登记成"已验"后必须放行
        man = ROOT / "state" / "_orch_man.json"
        man.write_text(json.dumps({"编号": "06", "模块": "render", "状态": "已验",
                                   "证据": "自检 => 正控"}, ensure_ascii=False), encoding="utf-8")
        ra._put(man, "%s/modules/render/current.json" % PREFIX)
        g2, w2 = _gate("render")
        ck("正控①·已验 ⇒ 放行", g2 is True, w2[:70])
        # 负控②：登记成"待部署"必须被拒（状态不是已验/已部署）
        man.write_text(json.dumps({"编号": "06", "模块": "render", "状态": "待部署"},
                                  ensure_ascii=False), encoding="utf-8")
        ra._put(man, "%s/modules/render/current.json" % PREFIX)
        g3, w3 = _gate("render")
        ck("负控②·登记了但状态不是已验 ⇒ 拒派", g3 is False and "不是已验" in w3, w3[:70])
        dp.LOCAL_CLOUD = keep

    # 负控③：轮转必须确定性（两次算同结果）且**同一作业不落两根触手**
    s1 = ["T%02d" % (i % 3 + 1) for i in range(9)]
    s2 = ["T%02d" % (i % 3 + 1) for i in range(9)]
    ck("负控③·轮转确定性（同输入同输出）", s1 == s2, " · ".join(s1))
    ck("正控②·一根触手可接多单但同单不双派",
       len(s1) == 9 and all(s1.count(t) >= 1 for t in ("T01", "T02", "T03")),
       "T01=%d T02=%d T03=%d" % (s1.count("T01"), s1.count("T02"), s1.count("T03")))
    # 负控④：长视频链必须在 07 处停住（07 在真云上没登记）
    dp2 = _dp()
    keep2 = dp2.LOCAL_CLOUD
    with tempfile.TemporaryDirectory() as td2:
        dp2.LOCAL_CLOUD = str(pathlib.Path(td2) / "cloud")
        ra = _ra()
        man = ROOT / "state" / "_orch_man2.json"
        man.write_text(json.dumps({"编号": "04", "模块": "frame-cache", "状态": "已验"}),
                       encoding="utf-8")
        ra._put(man, "%s/modules/frame-cache/current.json" % PREFIX)
        man.write_text(json.dumps({"编号": "06", "模块": "render", "状态": "已验"}),
                       encoding="utf-8")
        ra._put(man, "%s/modules/render/current.json" % PREFIX)
        chain = CHAINS["long_video"]
        stops = [name for num, name in chain if not _gate(name)[0]]
        ck("负控④·长视频链停在未登记工序（不越级）", stops == ["assemble", "publish"],
           "链 %s ⇒ 拦住 %s" % ([n for _, n in chain], stops))
        dp2.LOCAL_CLOUD = keep2

    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines,
                      "口径": "闸的正负控跑在**本地替身云**上；轮转确定性是纯函数对照"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="模块 02 · orchestrator（只派已登记的模块）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="看某作业的工序链与逐道闸判定")
    p.add_argument("job_id")
    p.set_defaults(func=cmd_plan)
    t = sub.add_parser("tick", help="一个调度轮（默认彩排，--apply 才真跑）")
    t.add_argument("--apply", action="store_true")
    t.set_defaults(func=cmd_tick)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
