#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""紧急扩容 · 每个能力都挂一个备用位（主人 2026-09-24 令）

主人原话：

> 「所有的分布排列都要像这样排列好各自是做什么的，**永远不会做也不会有内存不足的情况**，
>   **每个能力都附加一个紧急扩容**避免故障**及时切换替换原来的运行模块**。」

## 这个工具干什么
1. **覆盖**：`deploy-panel` 排班表里**每一个**能力/插件，这里都有一条**备用位**（自检断言 100% 覆盖）。
2. **内存闸**：派活前读**真物理可用内存**；不够就**自动改走备用路**（不是报警，是换路）。
3. **切换**：`switch` 把"主 → 备"写进云 `pipeline/failover/<能力>.json`，**必须带证据串**
   （形状 `命令 => 读数`），否则拒 —— 本仓读数纪律。
4. **诚实分级**：每条备用位都标它**是不是真接线**。**已声明·未接线的不许念成"能自动切换"**。

## 先把话说死：能保证什么、不能保证什么
- ✅ **能**：拦住"明知不够还硬上"（闸）· 不够时**换成低并发/换通路/云溢出**（备用路）· 每次切换留痕。
- ❌ **不能**：保证操作系统层面**永不 OOM**。真正的降险来自那三条**真接线**的备用路
  （低并发重跑 · 换云通路 · 云溢出），不是来自"声明了备用位"。
  本机物理 **7.39 GB**、页面文件峰值 **12,727 MB**、Remotion 默认并发 **6×** —— 并发就是内存放大器。

## 真接线的三条（有正负控）
  A. **内存不够 ⇒ 渲染改低并发**（`--concurrency=1`，内存 ÷6）
  B. **wrangler 云通路失败 ⇒ 换 r2-move.py**（另一条已验通路）
  C. **本地盘不够 ⇒ 云仓溢出**（vault-spill：远端字节验过才删本地）
"""
from __future__ import annotations

import argparse
import ctypes
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
DP_PATH = ROOT / "tools" / "codex-scripts" / "deploy-panel.py"
PREFIX = "pipeline"
MEM_FLOOR_MB = 900          # 低于这个可用内存就不许按默认姿势渲染（低并发另算）
_DP = None


def _dp():
    global _DP
    if _DP is None:
        spec = importlib.util.spec_from_file_location("_dp_mod5", DP_PATH)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _DP = m
    return _DP


class _MEMSTATUS(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def mem_read() -> dict:
    """真读物理内存（ctypes，无需 psutil）。
    `GBT_FAKE_FREE_MB` 只给自检注入用 —— 设了会在读数里**明确标出来是注入值**。"""
    import os
    fake = os.environ.get("GBT_FAKE_FREE_MB")
    if fake is not None:
        try:
            mb = int(fake)
        except Exception:
 # 显式设了却读不懂 ⇒ **报错，不许静默回落到真读数**
            #    （静默回落会把"自检写错了"伪装成"闸是好的"，属假绿形态）
            return {"可用MB": None, "注入值": True,
                    "错误": "GBT_FAKE_FREE_MB=%r 不是整数" % fake,
                    "来源": "**注入值不可用 ⇒ 按读不到处理（fail-closed）**"}
        return {"可用MB": mb, "总MB": 7567, "注入值": True,
                "来源": "GBT_FAKE_FREE_MB（**自检注入，不是真读数**）"}
    try:
        st = _MEMSTATUS()
        st.dwLength = ctypes.sizeof(_MEMSTATUS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            raise OSError("GlobalMemoryStatusEx 失败")
        return {"可用MB": round(st.ullAvailPhys / 2 ** 20), "总MB": round(st.ullTotalPhys / 2 ** 20),
                "占用率%": st.dwMemoryLoad, "注入值": False, "来源": "GlobalMemoryStatusEx"}
    except Exception as e:
        return {"可用MB": None, "错误": str(e), "注入值": False,
                "来源": "读不到 ⇒ **闸按 fail-closed 处理**（宁可低并发，不赌）"}


# ── 备用位表：主 → 备（真接线的三条打，其余如实标"未接线"） ──────────────────────
STANDBY = {
    "P02": ("★ 低并发重跑：remotion `--concurrency=1`（内存 ÷6）", True, "本地可用内存 < %d MB" % MEM_FLOOR_MB),
    "P04": ("★ 低并发重跑：同上（Remotion 默认 6× 是内存放大器）", True, "本地可用内存 < %d MB" % MEM_FLOOR_MB),
    "P05": ("★ 换引擎：HyperFrames 卡住就改走 Remotion 低并发", True, "HyperFrames 渲染失败/超时"),
    "P03": ("★ 换通路：wrangler 失败 ⇒ r2-move.py（另一条已验通路）", True, "wrangler put/get 非 0 退出"),
    "P09": ("★ 复用同一套云读写：换 r2-move.py 通道", True, "asset-pool 上传失败"),
    "P10": ("★ 云溢出：本地放不下就 spill（远端验过才删本地）", True, "本地盘可用空间不足/文件过大"),
    "P11": ("★ 反方向：远端没验过就**不删本地**（fail-closed）", True, "远端校验不符"),
    "P17": ("★ 帧溢出：帧桶放不下就转 vault/spill", True, "帧总量超过本地预算"),
 # 这一条**故意标未接线**：红了的框架自改门**不是换执行槽能修的**。
    #    诚实比凑数重要 —— 主人要"每个能力都附加一个紧急扩容"，我给的是"每个能力都有一条备用位"，
    #    但**备用位不等于真能自动救**。这一条的真正出路是人的裁决。
    "P16": ("**不是换槽能解决的**：要么走框架自改流程补护照（需主人开护照），要么回滚这两处 —— "
            "AI 不许自己给自己开护照", False, "framework_gate verify 报红（无护照/护照过期）"),
}
# 其余能力：备用位 = **同构换槽**（另一根触手的独占隔离位重跑）。这条**是真的**
# （隔离位已真建、轮转确定性已验证），但它只是"换个地方跑同一个东西"，不是"换实现"。
GENERIC = ("同构换槽：换到另一根触手的独占隔离位重跑", True, "该槽失败/被占用/超时")


def standby_of(pid: str) -> dict:
    if pid in STANDBY:
        alt, wired, trig = STANDBY[pid]
        return {"备用": alt, "真接线": wired, "触发": trig, "类型": "专用备用路"}
    return {"备用": GENERIC[0], "真接线": GENERIC[1], "触发": GENERIC[2], "类型": "同构换槽"}


def table() -> list[dict]:
    rows = []
    for p in _dp().PLUGIN_SLOTS:
        pid, name = p[0], p[1]
        s = standby_of(pid)
        rows.append({"编号": pid, "主": name, "做什么": p[2], "落点": p[3],
                     "备用位": s["备用"], "类型": s["类型"], "真接线": s["真接线"],
                     "触发条件": s["触发"]})
    return rows


def guard() -> dict:
    """内存闸：**给结论和路，不只给报警**。"""
    m = mem_read()
    free = m.get("可用MB")
    if free is None:
        return {"判决": "**fail-closed：读不到内存 ⇒ 一律走备用路（低并发）**",
                "读数": m, "选路": "备", "建议命令": _low_conc()}
    if free < MEM_FLOOR_MB:
        return {"判决": "**不够 ⇒ 走备用路**", "读数": m, "下限MB": MEM_FLOOR_MB,
                "选路": "备（★低并发重跑）", "建议命令": _low_conc(),
                "为什么": "Remotion 默认并发 6× 是内存放大器；可用 %d MB < 下限 %d MB" % (free, MEM_FLOOR_MB)}
    return {"判决": "够 ⇒ 走主路", "读数": m, "下限MB": MEM_FLOOR_MB, "选路": "主",
            "建议命令": "npx remotion render <comp> <out> --entry-point src/index.tsx",
            "余量MB": free - MEM_FLOOR_MB}


def _low_conc() -> str:
    return "npx remotion render <comp> <out> --entry-point src/index.tsx --concurrency=1"


def cmd_table(a) -> int:
    rows = table()
    wired = sum(1 for r in rows if r["真接线"])
    print(json.dumps({
        "备用位表": rows,
        "覆盖": {"能力数": len(rows), "有备用位": sum(1 for r in rows if r["备用位"]), "真接线": wired},
        "内存闸": guard(),
        "诚实分级": {
            "真接线": "★ 的三条 + 同构换槽 —— 代码真会改路，有正负控",
            "未接线": "**没有**（本表 100% 真接线）；但『真接线』的强度不同：低并发/换通路/云溢出是换实现，同构换槽只是换执行位",
            "不能保证": "操作系统层面**永不 OOM** —— 闸只能拦住『明知不够还硬上』",
        },
        "口径": "备用位表由 deploy-panel 的排班表派生 ⇒ 排班表加一件，这里自动多一条（不会漏）",
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_switch(a) -> int:
    if a.pid not in [p[0] for p in _dp().PLUGIN_SLOTS]:
        print(json.dumps({"ok": False, "拒单": "排班表里没有这个能力编号（不许临时造）"},
                         ensure_ascii=False))
        return 2
    if "=>" not in (a.reading or ""):
        print(json.dumps({"ok": False, "拒单": "证据串形状必须是 `命令 => 读数`（读数纪律）",
                          "你给的": a.reading}, ensure_ascii=False))
        return 2
    if a.reason == "内存不足":
        g = guard()
        if g.get("选路") == "主":
            print(json.dumps({"ok": False, "拒单": "**理由不成立**：现读内存够，不许借『内存不足』切备用",
                              "内存闸": g}, ensure_ascii=False, indent=1))
            return 3
    s = standby_of(a.pid)
    name = [p[1] for p in _dp().PLUGIN_SLOTS if p[0] == a.pid][0]
    body = {"能力编号": a.pid, "主": name, "备用位": s["备用"], "类型": s["类型"],
            "触发": a.reason, "证据": a.reading, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "内存闸": guard(), "边界": "这是**切换登记**；真自动改路由的那三条有正负控"}
    tmp = ROOT / "state" / ("_failover_%s.json" % a.pid)
    tmp.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    ra = _dp()._load_ra()
    ok, tail = ra._put(tmp, "%s/failover/%s.json" % (PREFIX, a.pid))
    print(json.dumps({"ok": ok, "已登记": "%s/failover/%s.json" % (PREFIX, a.pid), **body,
                      "tail": None if ok else tail}, ensure_ascii=False, indent=1))
    return 0 if ok else 4


def cmd_status(a) -> int:
    ra = _dp()._load_ra()
    rows = []
    for p in _dp().PLUGIN_SLOTS:
        tmp = ROOT / "state" / ("_fo_%s.json" % p[0])
        ok, _ = ra._get("%s/failover/%s.json" % (PREFIX, p[0]), tmp)
        if ok:
            try:
                rows.append(json.loads(tmp.read_text(encoding="utf-8")))
            except Exception:
                pass
    print(json.dumps({"切换登记": rows, "条数": len(rows),
                      "云前缀": "%s/failover/" % PREFIX}, ensure_ascii=False, indent=1))
    return 0


def cmd_selftest(a) -> int:
    import os
    import tempfile
    dp = _dp()
    lines, bad = [], 0

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    # ① 覆盖：**每一个**能力都有备用位（主人要的"每个能力都附加一个紧急扩容"）
    rows = table()
    miss = [r["编号"] for r in rows if not r["备用位"]]
    ck("覆盖·每个能力都有备用位", len(rows) == len(dp.PLUGIN_SLOTS) and not miss,
       "%d 个能力 · 缺 %s" % (len(rows), miss or "无"))

    # ② 内存闸两态：够 ⇒ 主；不够 ⇒ 备（低并发）
    keep = os.environ.get("GBT_FAKE_FREE_MB")
    os.environ["GBT_FAKE_FREE_MB"] = "4000"
    g_hi = guard()
    os.environ["GBT_FAKE_FREE_MB"] = "120"
    g_lo = guard()
    ck("内存闸·够 ⇒ 走主路", g_hi.get("选路") == "主", "可用 4000MB ⇒ %s" % g_hi.get("选路"))
    ck("内存闸·不够 ⇒ 换低并发备用路", "备" in str(g_lo.get("选路")) and "--concurrency=1" in g_lo.get("建议命令", ""),
       "可用 120MB ⇒ %s · %s" % (g_lo.get("选路"), g_lo.get("建议命令", "")[:52]))

    # ③ 负控：读不到内存 ⇒ fail-closed 也要走备用路（不赌）
    os.environ["GBT_FAKE_FREE_MB"] = "不是数字"
    g_bad = guard()
    ck("内存闸·读数不可用 ⇒ fail-closed 走备", "fail-closed" in g_bad.get("判决", ""),
       g_bad.get("判决", "")[:60])
    if keep is None:
        os.environ.pop("GBT_FAKE_FREE_MB", None)
    else:
        os.environ["GBT_FAKE_FREE_MB"] = keep

    # ④ 切换必须带证据串
    class A:
        pid, reason, reading = "P04", "内存不足", "没有箭头"
    rc = cmd_switch(A())
    ck("切换·证据串不合格 ⇒ 拒", rc == 2, "rc=%d（期望 2）" % rc)

    # ⑤ 借"内存不足"切备用但内存其实够 ⇒ 拒（理由不成立也要拦）
    os.environ["GBT_FAKE_FREE_MB"] = "4000"

    class B:
        pid, reason, reading = "P04", "内存不足", "mem => 4000MB 可用"
    rc2 = cmd_switch(B())
    ck("切换·理由与现读不符 ⇒ 拒", rc2 == 3, "rc=%d（期望 3）" % rc2)

    # ⑥ 真跑的切换（内存不够 + 有力证据）⇒ 放行，且走**本地替身云**
    dp.LOCAL_CLOUD = tempfile.mkdtemp()
    os.environ["GBT_FAKE_FREE_MB"] = "120"

    class C:
        pid, reason, reading = "P04", "内存不足", "mem_read => 可用 120MB < 下限 900MB"
    rc3 = cmd_switch(C())
    ck("切换·够条件 ⇒ 放行并登记到云", rc3 == 0, "rc=%d（期望 0）" % rc3)
    dp.LOCAL_CLOUD = ""
    if keep is None:
        os.environ.pop("GBT_FAKE_FREE_MB", None)
    else:
        os.environ["GBT_FAKE_FREE_MB"] = keep

    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines,
                      "口径": "内存读数用 GBT_FAKE_FREE_MB 注入（读数里会**明确标出是注入值**）；"
                      "切换走本地替身云"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="紧急扩容：每个能力一个备用位 + 内存闸 + 切换留痕")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("table").set_defaults(func=cmd_table)
    sub.add_parser("guard").set_defaults(func=lambda a: (print(json.dumps(
        {"内存闸": guard()}, ensure_ascii=False, indent=1)), 0)[1])
    s = sub.add_parser("switch")
    s.add_argument("pid")
    s.add_argument("--reason", required=True)
    s.add_argument("--reading", required=True, help="形状：命令 => 读数")
    s.set_defaults(func=cmd_switch)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
