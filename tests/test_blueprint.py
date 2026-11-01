# -*- coding: utf-8 -*-
"""蓝图主链判据：架构 → 蓝图 → 过目 → 思维导图 → 派遣 → 落地。

主人 2026-11-01：「必须由 GBT小土豆V8 根据用户给的架构框架来生成蓝图，用户看了没问题
就分析推理然后派遣思维导图任务指引给触手去执行任务，直至项目落地」。

四条硬判据：
  ① 没过目不许派遣（fail-closed）
  ② 过目后自动进入自主模式（不再打扰主人）
  ③ 思维导图任务有依赖、有验收
  ④ 派遣后 landed 要求**全部**任务通过（不许"差不多"）

跑法：python tests/test_blueprint.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.tentacle import autonomy as AU
    from gbt_allinone.tentacle import blueprint as BP

    # 判据测试不许留垃圾：蓝图目录只留真实蓝图；模板目录只删本次新增
    _bp_dir = os.path.join(ROOT, "state", "blueprints")
    _tpl_dir = os.path.join(ROOT, "state", "blueprint-templates")
    _tpl_snapshot = set(os.listdir(_tpl_dir)) if os.path.isdir(_tpl_dir) else set()

    print("[1] 架构 → 蓝图")
    m = BP.make("GBT小土豆V8 触手主干：全自主推进到项目落地", "判据测试")
    check("蓝图生成", m.get("ok") and bool(m.get("id")), m)
    bid = m.get("id")
    check("任务数 >= 10", (m.get("tasks") or 0) >= 10, m.get("tasks"))
    check("蓝图文件落盘", os.path.exists(os.path.join(ROOT, "state", "blueprints", bid + ".json")))
    check("蓝图 md 落盘", os.path.exists(os.path.join(ROOT, "state", "blueprints", bid + ".md")))

    print("[2] 没过目不许派遣")
    d0 = BP.dispatch(bid)
    check("未过目被拒", d0.get("ok") is False and "未过目" in str(d0.get("error")), d0)

    print("[3] 过目 → 自主模式")
    a = BP.approve(bid)
    check("过目成功", a.get("ok") is True, a)
    st_au = AU.status()
    check("已进入自主模式", st_au.get("architecture_accepted") is True, st_au)

    print("[4] 思维导图（依赖 + 验收）")
    mm = BP.mindmap(bid)
    check("任务图生成", mm.get("ok") and (mm.get("tasks") or 0) >= 10, mm.get("tasks"))
    graph = json.loads(open(os.path.join(ROOT, "state", "blueprints", bid + ".mindmap.json"),
                            encoding="utf-8").read())
    check("任务带依赖（除首个）", sum(1 for t in graph["tasks"] if t.get("needs")) >= len(graph["tasks"]) - 1)
    check("任务带验收", all(t.get("acceptance") for t in graph["tasks"]))

    print("[5] 派遣 → 落地（全部通过才算）")
    d = BP.dispatch(bid)
    check("派遣完成", d.get("ok") is True, d.get("failed_tasks"))
    check("done 等于任务数", d.get("done") == d.get("dispatched"), (d.get("done"), d.get("dispatched")))
    check("landed=True", d.get("landed") is True, d.get("landed"))
    st = BP.status(bid)
    check("status progress=1.0", (st.get("progress") or 0) >= 0.999, st.get("progress"))
    check("status landed", st.get("landed") is True, st.get("landed"))

    print("[6] land：跑到落地，中途不停")
    m2 = BP.make("触手主干 + 无限制上下文 + 自主吞噬 + 脉冲提速", "land 判据")
    bid2 = m2["id"]
    BP.approve(bid2)
    L = BP.land(bid2, max_rounds=4)
    check("landed", L.get("landed") is True, L.get("note"))
    check("有轮次记录", bool(L.get("rounds")), L.get("rounds"))
    check("第一轮就全部通过", (L.get("rounds") or [{}])[0].get("failed") == 0,
          (L.get("rounds") or [{}])[0])

    print("[7] 已落地不再重跑")
    L2 = BP.land(bid2, max_rounds=2)
    check("识别已落地", L2.get("landed") is True and "已落地" in str(L2.get("note")), L2.get("note"))
    check("没有新轮次", not L2.get("rounds"), L2.get("rounds"))

    print("[8] 研究环：卡点 → 查资料 → 落知识")
    rr = BP.research("quantization q5_0 dequantize", max_sources=1)
    check("研究能跑（或明确失败不抛）", isinstance(rr.get("ok"), bool), rr.get("ok"))
    if rr.get("ok"):
        check("落了知识文件", os.path.exists(rr.get("knowledge") or ""), rr.get("knowledge"))
        check("有来源", len(rr.get("sources") or []) >= 1, rr.get("sources"))

    print("[9] 卡点触发研究（不是停下问主人）")
    from gbt_allinone.tentacle import blueprint as BPm
    bidB = "blocker-test-%d" % os.getpid()
    PB = BPm._paths(bidB)
    PB["json"].parent.mkdir(parents=True, exist_ok=True)
    PB["json"].write_text(json.dumps({
        "id": bidB, "architecture": "演示", "goal": "验证研究环",
        "tasks": [{"id": "实现.1", "phase": "实现", "title": "故意失败",
                   "cap": "nonexistent_cap_xyz", "payload": {}, "acceptance": "不该通过",
                   "needs": []}], "risks": [], "acceptance": "x"}, ensure_ascii=False),
        encoding="utf-8")
    PB["approved"].write_text(json.dumps({"approved": True}), encoding="utf-8")
    for suf in (".stuck.json", ".runs.jsonl", ".mindmap.json"):
        try:
            (pathlib.Path(PB["json"]).with_name(pathlib.Path(PB["json"]).stem + suf)).unlink(missing_ok=True)
        except Exception:
            pass
    LB = BPm.land(bidB, max_rounds=1)
    r1 = (LB.get("rounds") or [{}])[0]
    check("未落地（如实报）", LB.get("landed") is False, LB.get("note"))
    check("第一轮就触发了研究", bool(r1.get("research")), r1.get("research"))
    led = os.path.join(ROOT, "state", "research-ledger.jsonl")
    check("研究账本落盘", os.path.exists(led) and os.path.getsize(led) > 0)

    print("[10] 深推理 + 规则兜底")
    from gbt_allinone.tentacle import blueprint as BPd
    fb = BPd._fallback_deep_task("No module named psutil 导致自检失败")
    check("兜底按卡点类型给任务", fb.get("ok") and len(fb.get("tasks") or []) == 1, fb)
    check("兜底任务带可执行能力位",
          (fb.get("tasks") or [{}])[0].get("cap") in ("cap_self", "inventory", "autonomy",
                                                      "orchestration", "pulse_core", "comfy_native"),
          (fb.get("tasks") or [{}])[0].get("cap"))
    check("兜底标明来源（不冒充模型推理）", fb.get("source") == "fallback_rule", fb.get("source"))
    # 深推理真调一次（模型不通也必须回退，不许抛）
    dr = BPd.deep_reason("timeout 在 300 秒", ["retry with longer timeout"])
    check("deep_reason 不抛且带 source", isinstance(dr.get("ok"), bool) and dr.get("source"),
          dr.get("source"))

    print("[11] 诊断质量门（胡话不采信）")
    digest = ["No module named psutil: install it with pip",
              "1.5-bit to 8-bit integer quantization for faster inference"]
    bad = BPd._score_diagnosis("成年礼版 GBT-LLM 微软营 不含 AI", digest, "psutil 缺失")
    good = BPd._score_diagnosis("psutil 模块未安装，需要 install", digest, "psutil 缺失")
    empty = BPd._score_diagnosis("", digest)
    check("胡话判 unsupported", bad.get("supported") is False, bad)
    check("有依据判 supported", good.get("supported") is True, good)
    check("空诊断判 unsupported", empty.get("supported") is False, empty)
    check("兜底任务按卡点类型（dependency → cap_self verify）",
          (BPd._fallback_deep_task("No module named psutil").get("tasks") or [{}])[0].get("cap") == "cap_self")

    print("[12] 死循环保护（stuck 两轮剔除）")
    from gbt_allinone.tentacle import blueprint as BPs
    bidS = "stuck-test-%d" % os.getpid()
    PS = BPs._paths(bidS)
    PS["json"].parent.mkdir(parents=True, exist_ok=True)
    PS["json"].write_text(json.dumps({
        "id": bidS, "architecture": "x", "goal": "x",
        "tasks": [{"id": "实现.1", "phase": "实现", "title": "永远失败",
                   "cap": "nonexistent_cap_xyz", "payload": {}, "acceptance": "x", "needs": []}],
        "risks": [], "acceptance": "x"}, ensure_ascii=False), encoding="utf-8")
    PS["approved"].write_text(json.dumps({"approved": True}), encoding="utf-8")
    # 清掉上一轮遗留的 stuck/runs，保证判据可重复（否则第一次跑就被跳过）
    for suf in (".stuck.json", ".runs.jsonl", ".mindmap.json"):
        try:
            (pathlib.Path(PS["json"]).with_name(pathlib.Path(PS["json"]).stem + suf)).unlink(missing_ok=True)
        except Exception:
            pass
    LS = BPs.land(bidS, max_rounds=3)
    check("未落地（如实报）", LS.get("landed") is False, LS.get("note"))
    check("任务被标 stuck", "实现.1" in (LS.get("stuck") or []), LS.get("stuck"))
    rounds = LS.get("rounds") or []
    check("rounds 里记了 stuck 事件", any(r.get("stuck") for r in rounds), rounds)
    check("后续轮跳过（末轮 failed=0）", rounds and rounds[-1].get("failed") == 0,
          (rounds[-1] if rounds else {}))
    stS = BPs.status(bidS)
    check("status 带 stuck", "实现.1" in (stS.get("stuck") or []), stS.get("stuck"))

    print("[13] 模板库：落地即沉淀，相似架构复用")
    from gbt_allinone.tentacle import blueprint as BPt
    tdir = os.path.join(ROOT, "state", "blueprint-templates")
    before = set(os.listdir(tdir)) if os.path.isdir(tdir) else set()
    arch = "触手主干 + 无限制上下文 + 脉冲提速 + 自主吞噬"
    m1 = BPt.make(arch, "模板判据")
    b1 = m1["id"]
    BPt.approve(b1)
    L1 = BPt.land(b1, max_rounds=2)
    check("落地后自动沉淀模板", bool(L1.get("template") and L1["template"].get("ok")), L1.get("template"))
    m2 = BPt.make("触手主干 + 无限制上下文 + 脉冲提速", "复用判据")
    check("相似架构复用模板", bool(m2.get("from_template")), m2.get("from_template"))
    check("复用后任务数 > 0", (m2.get("tasks") or 0) > 0, m2.get("tasks"))
    tl = BPt.templates()
    check("模板列表可读", tl.get("count", 0) >= 1, tl.get("count"))
    # 清掉本测试新建的模板（不制造垃圾）
    after = set(os.listdir(tdir)) if os.path.isdir(tdir) else set()
    for f in after - before:
        try:
            os.remove(os.path.join(tdir, f))
        except Exception:
            pass

    print("[14] 一句话入口（go）")
    from gbt_allinone.tentacle import blueprint as BPg
    created = []
    try:
        pi = BPg.parse_intent("按这个架构推进到落地：触手主干 + 脉冲提速")
        check("解析出架构", bool(pi.get("ok") and pi.get("arch")), pi)
        check("未写已确认 ⇒ approved=False", pi.get("approved") is False, pi)
        r1 = BPg.go("按这个架构推进到落地：触手主干 + 脉冲提速")
        created.append(r1.get("id"))
        check("不确认时停在蓝图", r1.get("stage") == "blueprint" and r1.get("pending_approval") is True, r1.get("stage"))
        r2 = BPg.go("按这个架构推进到落地，已确认：触手主干 + 脉冲提速", auto_approve=True, max_rounds=2)
        created.append(r2.get("id"))
        check("已确认时走到落地", r2.get("stage") in ("landed", "land_attempted"), r2.get("stage"))
        check("land 有读数", bool((r2.get("land") or {}).get("rounds")), (r2.get("land") or {}).get("note"))
    finally:
        # 清掉本测试造的蓝图（不制造垃圾）
        for bid in [c for c in created if c]:
            for suf in (".json", ".md", ".approved.json", ".mindmap.json", ".mmd",
                        ".runs.jsonl", ".stuck.json"):
                try:
                    (BPg.BP_DIR / (bid + suf)).unlink(missing_ok=True)
                except Exception:
                    pass

    # 清理：蓝图目录只留真实蓝图；模板目录只删本次新增
    _KEEP_BP = "gbt小土豆v8触手主-5d1942"
    if os.path.isdir(_bp_dir):
        for _f in os.listdir(_bp_dir):
            if _f.startswith(_KEEP_BP):
                continue
            try:
                os.remove(os.path.join(_bp_dir, _f))
            except Exception:
                pass
    if os.path.isdir(_tpl_dir):
        for _f in os.listdir(_tpl_dir):
            if _f in _tpl_snapshot:
                continue
            try:
                os.remove(os.path.join(_tpl_dir, _f))
            except Exception:
                pass

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 蓝图→过目→思维导图→派遣→落地 五段全链有读数")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
