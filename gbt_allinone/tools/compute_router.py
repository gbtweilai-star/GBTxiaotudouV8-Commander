#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""算力分层路由 —— 让"换一层去干"成为默认动作。

Owner 2026-09-22：「你自己设计好，让自己可以实现高难度任务不影响就行了」

═══ 为什么要有这个模块 ═══
  实测病根：**CPU 30% · 内存 91% · 换页 21,210 页/秒**。
  ⇒ 瓶颈是"记不住"，不是"算得慢"。**加 CPU 加速器没用。**

  所以本模块只做一件事：**接任务 → 先量宿主 → 说出该走哪层 + 现在能不能跑。**
  它不执行任务，它**给路由结论**（含"不能跑"这个结论）。

═══ 五层（按"吃不吃本地内存"分）═══
  T0 本地·必须   DSH 对话（我的意识）—— 已在账上，动不了也不该动
  T1 本地·轻     read/grep/glob/edit/write —— harness 内部，≈0 代价
  T2 DSH 内并行  子代理 / workflow —— API 调用，**零本地进程**（今晚已证）
  T3 云端服务    Tripo（3D）· Cloudflare（托管/边缘）—— 本地只出网络
  T4 本地·重     Playwright 渲染 / Electron 打包 —— **数百 MB 起，只在这层受限**

═══ 四条自律 ═══
  ① 换层不许绕过门（云上跑的一样过 auth_gate）—— 对齐 energy_pool「能源可换，栈不动」
  ② 换不动就说换不动（**不许假装"已经用云算力跑完了"**）
  ③ 每次路由留痕（任务 · 宿主读数 · 选了哪层 · 为什么）
  ④ T4 不因"任务重要"就放行 —— 内存不够就换层或推迟，**不许硬上**
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# ── 任务类型 → 首选层（判据写死，可复核）──────────────────────
# 键是任务类型；值是 (首选层, 备选层, 说明)
TASK_ROUTES = {
    "read_file":      ("T1", None, "读文件/搜索/列目录 —— harness 内部，零代价"),
    "write_file":     ("T1", None, "写文件/编辑 —— harness 内部，零代价"),
    "analyze":        ("T2", None, "分析/审计/设计 —— 派子代理，零本地进程"),
    "audit_code":     ("T2", "T1", "代码审计 —— 子代理分批读，比本地脚本省内存"),
    "test_caps":      ("T2", None, "全能力测试 —— 分批派子代理，不需要本地 GUI"),
    "gen_3d":         ("T3", None, "3D 生成 —— Tripo 云端，本地只下载"),
    "publish_web":    ("T3", None, "公网发布 —— Cloudflare Pages"),
    "edge_inference": ("T3", "T4", "模型推理 —— 优先边缘（Workers AI），本地兜底"),
    "render_page":    ("T4", "T3", "页面渲染验证 —— 真要浏览器内核；边缘无此能力则必 T4"),
    "package_app":    ("T4", None, "打包桌面 APP —— 真需要本地进程与磁盘 IO"),
    "run_local_proc": ("T4", None, "任何本地起进程的活"),
}


def host_vitals() -> dict:
    """量宿主。**量不到就如实标 unknown，不猜一个数。**"""
    v = {"cpu_pct": None, "mem_pct": None, "mem_free_gb": None,
         "mem_total_gb": None, "swapping": None, "measured_at": time.strftime("%H:%M:%S")}
    try:
        import psutil
        v["cpu_pct"] = psutil.cpu_percent(interval=0.4)
        m = psutil.virtual_memory()
        v["mem_pct"] = round(m.percent, 1)
        v["mem_free_gb"] = round(m.available / 1024 ** 3, 2)
        v["mem_total_gb"] = round(m.total / 1024 ** 3, 1)
        try:
            s = psutil.swap_memory()
            v["swapping"] = "swap 已用 %d MB (%.0f%%)" % (s.used / 1024 ** 2, s.percent)
        except Exception:                                        # noqa: BLE001
            pass
    except Exception as e:                                       # noqa: BLE001
        v["error"] = ("psutil 不可用：%s —— 宿主读数 unknown，"
                      "**不当作「内存充足」**" % type(e).__name__)
    return v


def gate(v: dict) -> dict:
    """宿主闸：**放不放行 T4**。这是本模块最要紧的一条判据。"""
    mem = v.get("mem_pct")
    if mem is None:
        return {"allow_t4": False, "level": "unknown",
                "why": "宿主读数取不到 ⇒ **不放行 T4**（宁可不做，不许硬上）"}
    if mem > 90:
        return {"allow_t4": False, "level": "stop",
                "why": "内存 %.1f%% > 90%% ⇒ 停手，只许 T0–T3" % mem}
    if mem > 85:
        return {"allow_t4": True, "level": "single",
                "why": "内存 %.1f%% 处 85–90%% ⇒ 允许**单次** T4，且必须当场报读数、当场收工" % mem}
    return {"allow_t4": True, "level": "normal",
            "why": "内存 %.1f%% < 85%% ⇒ 允许 T4，但**一次只开一个重活**" % mem}


def route(task: str) -> dict:
    """给一个任务类型，返回路由结论。**这是本模块的入口。**"""
    v = host_vitals()
    g = gate(v)
    t = TASK_ROUTES.get(task)
    if not t:
        return {"ok": False, "task": task, "vitals": v, "gate": g,
                "error": "未知任务类型：%s" % task,
                "known": sorted(TASK_ROUTES),
                "hint": "**不猜一个层给你** —— 先把这个任务类型登记进 TASK_ROUTES"}
    first, alt, why = t
    chosen, fallback_used, blocked = first, False, None

    if first == "T4" and not g["allow_t4"]:
        if alt:
            chosen, fallback_used = alt, True
        else:
            blocked = ("T4 被宿主闸拦住，且此任务无备选层 ⇒ **现在做不了**。"
                       "如实报缺，不许硬上。%s" % g["why"])
    return {
        "ok": blocked is None,
        "task": task,
        "tier": chosen,
        "preferred": first,
        "fallback_used": fallback_used,
        "blocked": blocked,
        "why": why,
        "vitals": v,
        "gate": g,
        "law": ("换层不许绕过门：云上跑的能力一样过 auth_gate；"
                "换不动就说换不动，**不许假装已经跑完**。"),
    }


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="算力分层路由（只读，不执行任务）")
    ap.add_argument("task", nargs="?", help="任务类型；不给则列出全部")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not a.task:
        v = host_vitals()
        g = gate(v)
        print("=" * 74)
        print("算力分层路由 · 宿主体检")
        print("=" * 74)
        for k, val in v.items():
            print("  %-14s %s" % (k, val))
        print("\n  宿主闸: T4 %s —— %s" % ("放行" if g["allow_t4"] else "**拦住**", g["why"]))
        print("\n  任务 → 层：")
        for k, (f, alt, why) in sorted(TASK_ROUTES.items()):
            print("    %-16s %s%s   %s" % (k, f, ("（备选 %s）" % alt) if alt else "", why[:44]))
        print("\n  " + "换层不许绕过门；换不动就说换不动。")
        return 0
    r = route(a.task)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1
    print(f"  任务     : {r['task']}")
    print(f"  该走哪层 : **{r['tier']}**" + ("  （首选 %s 被拦，已换层）" % r["preferred"]
                                            if r["fallback_used"] else ""))
    print(f"  为什么   : {r.get('why')}")
    if r.get("blocked"):
        print(f"  ⛔ 做不了 : {r['blocked']}")
    print(f"  宿主     : 内存 {r['vitals'].get('mem_pct')}% · "
          f"空闲 {r['vitals'].get('mem_free_gb')} GB · CPU {r['vitals'].get('cpu_pct')}%")
    print(f"  宿主闸   : {r['gate']['why']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
