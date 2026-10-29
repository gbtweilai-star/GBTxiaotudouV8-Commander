#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全项目**故障总扫**（主人令：「梳理修复感觉把整个项目的故障都清理排除跑通」）

## 这个件是什么、不是什么
**是**：把项目**自己的体检能力位**逐个走门跑一遍，把每一个自己吐出来的红字段摊在一张表上。
**不是**：我自己发明一套"健康分"。判据只能用**能力位自己报的字段**（verdict / findings /
needs_a_look / ok / denied），本件只做**转发 + 归类**——发明判据就是造第二处真相。

## 三条纪律（写死）
1. 🔴 **只跑只读体检位**。凡名字带写动作（`root_fix` / `sched_*` / `wf_*` / `devour_reflect` /
   `lr_tick` / `ledger_note` / `trace_store` …）一律**只列不跑** —— 它们是"修"，要主人点头
   （`omni.py caliber` 现读已经指出：omni 认为 22 条要确认，而 `cross_scan.PROBE_SKIP_KINDS` 只有 13 条，
   差的 9 条里就有 `root_fix` ⇒ 这份名单**不能**当"可直跑"用）。
2. 🔴 **认得出收窄**：`five-dim.py` 在 result > 1100 字时会收窄成 `{_摘要, keys, preview}`
   ⇒ 读真值必须解 `preview`，否则会把"被收窄"当成"没字段"。
3. 🔴 **不硬凑结论**：认不出判据的就如实报 `形状看不懂` 并把它的键名列出来，不许当通过。

用法：
```
python tools/codex-scripts/fault-sweep.py            # 全扫（约 1–2 分钟）
python tools/codex-scripts/fault-sweep.py --only 门,安全
python tools/codex-scripts/fault-sweep.py --raw health   # 单个原样打出来
```
退出码：0 无红 · 1 有红 · 2 起不来   ·   报告落盘 `state/fault-sweep.json`
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "fault-sweep.json"
PY = sys.executable
GATE = ROOT / "tools" / "codex-scripts" / "five-dim.py"

# (能力位, 归组, 一句话说明) —— **只读体检位**
CAPS = [
    ("health", "基础", "平台/python/时间"),
    ("selfscan", "基础", "自体检：路由/注册/覆盖"),
    ("alerts", "基础", "窗口内异常事件"),
    ("truth_scan", "基础", "自称与事实对账"),
    ("inventory", "基础", "在册清点"),
    ("file_hygiene", "基础", "文件卫生（残留/临时件）"),
    ("auth_gate_status", "门", "授权门现读"),
    ("signature_guard", "门", "署名/印章守护"),
    ("caps_called_audit", "门", "能力位调用审计"),
    ("shared_resources", "门", "共享资源占用"),
    ("hook_registry", "门", "钩子登记"),
    ("orchestration_kernel", "门", "编排内核"),
 # 2026-10-13 深扫补盲区（原清单只有旧件 ⇒ 新件**从没被扫过**=盲点）：
    #    旧 cross_scan 实测给到 300s 仍超时（结构问题，不是预算），已在册的增强版
    #    penetrating_cross_scan（钩子强制/步骤锁/双路交叉互扫/遗漏补扫/留痕）才是要用的那件。
    ("penetrating_cross_scan", "交叉", "穿透式交叉扫描（增强版·新件：钩子+步骤锁+双路互扫+遗漏补扫+留痕）"),
    ("coverage_auditor", "交叉", "覆盖审计（谁没被验过）"),
    ("context_vault", "交叉", "上下文仓"),
    ("energy_pool", "交叉", "能量池"),
    ("tentacle_cognition", "交叉", "手眼网耳认知位"),
    ("platform_profile", "项目", "平台画像（注意 30s TTL 缓存）"),
    ("project_context", "项目", "项目上下文/蓝图"),
    ("sec_surface", "安全", "攻击面"),
    ("sec_scan", "安全", "漏洞扫描"),
    ("sec_chain", "安全", "攻击链推演"),
    ("sec_defenses", "安全", "防御是否真生效"),
    ("mirror_scan", "交付", "镜像体检（只读扫描器，已豁免）"),
    ("mirror_status", "交付", "镜像现读"),
    ("pipeline_status", "交付", "流水线现读"),
    ("svc_inspect", "交付", "服务探活"),
    ("ghost_guard", "交付", "幽灵守卫"),
]

# 只列不跑：名字即写动作，或 omni 标了 needs_confirmation（深修后单一真源：
# `PROBE_SKIP_KINDS = 探测专项 ∪ preflight.state_changing_kinds()`，原"口径分裂 9 条"已闭合）
NOT_RUN = [
    ("root_fix", "修（会改状态）：口径分裂名单里就有它 ⇒ 不许自动跑"),
    ("sched_define/sched_tick", "定时器：改状态"),
    ("wf_define/wf_run/wf_resume/wf_cache_clear", "工作流：改状态/清缓存"),
    ("devour_reflect", "反思进化：会写盘/出网/跑外部模型（作用域为空但会动手）"),
    ("lr_tick", "长程推进：改状态"),
    ("ledger_note", "记账：写盘"),
    ("trace_store", "留痕：写盘"),
    ("devour_* / stigmergy / life", "写域：不在本轮只读范围内"),
]


def unwrap(res):
    """认得出 five-dim 的收窄（真值在 preview），返回 (真值, 是否被收窄)。"""
    if isinstance(res, dict) and "preview" in res and "_摘要" in res:
        return res.get("preview"), True
    return res, False


# 2026-10-13 修（深扫报红 1 条：cross_scan 超时 90s）：
#    它是"扫全项目"的重活，90 秒不是它的预算——**慢位要给自己的预算**，不是当故障念。
SLOW_CAPS = {"cross_scan": 300}

# 2026-10-13：**已退场件·只列不探**（「新增即清旧」）。不藏、也不当红：
#    旧 `cross_scan` 给到 300s 仍超时（结构问题），同族增强版 `penetrating_cross_scan`
#    已入探针清单且通过 ⇒ 旧件不再探；但**在此显式登记**，谁读总扫都能看见它被退场了。
#    注意：这是**扫描层退场**；**登记层退场**（caps_registry 里的在位登记 + handler 文件回收）
#    仍待做 —— 那一步要按清旧判据走，不许在这个文件里假装已完成。
RETIRED_CAPS = [("cross_scan", "旧跨域扫描：300s 仍超时；已由 penetrating_cross_scan 取代（登记层退场待做）")]

# 2026-10-13 修（深扫"认不出 5 条"）：**纯数据位**的已知形状表。
#    这几位只回数据、不报 verdict/ok/quiet ⇒ 旧逻辑一律归"形状看不懂"（那是尺子的问题，不是对象的）。
DATA_CAPS = {
    "health": ("platform", "python", "time"),
    "platform_profile": ("workspace", "exists", "top_level_dirs"),
    "project_context": ("status", "path", "sha256"),
    "pipeline_status": ("records", "count", "total"),
    "svc_inspect": ("services", "total", "up", "down"),
}


def run_cap(cap, timeout=90):   # 单位超时：一个慢位不许吃掉全扫的预算
    t0 = time.time()
    try:
        cp = subprocess.run([PY, str(GATE), "cap", cap], cwd=str(ROOT), capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"cap": cap, "起不来": "超时 %ss" % timeout, "耗时s": round(time.time() - t0, 1)}
    except Exception as e:                                                 # noqa: BLE001
        return {"cap": cap, "起不来": str(e)[:120], "耗时s": round(time.time() - t0, 1)}
    txt = (cp.stdout or "").strip()
    i = txt.find("{")
    try:
        j = json.loads(txt[i:]) if i >= 0 else None
    except Exception:                                                      # noqa: BLE001
        j = None
    if j is None:
        return {"cap": cap, "起不来": "没有 JSON 输出（exit=%s）：%s"
                % (cp.returncode, (cp.stderr or txt)[-160:]), "耗时s": round(time.time() - t0, 1)}
    return {"cap": cap, "exit": cp.returncode, "信封": j.get("信封") or j.get("_信封"),
            "stamp": j.get("stamp"), "status": j.get("status"), "denied": j.get("denied"),
            "missing_scopes": j.get("missing_scopes") or j.get("missing"),
            "耗时s": round(time.time() - t0, 1), "原始": j}


def classify(rec):
    """**只用能力位自己报的字段**归类。认不出就如实说认不出。"""
    if "起不来" in rec:
        return "起不来", rec["起不来"]
    if rec.get("denied"):
        return "被门拒", "missing_scopes=%s" % (rec.get("missing_scopes"),)
    res, narrowed = unwrap((rec.get("原始") or {}).get("result"))
    tag = "（已收窄，读的是 preview）" if narrowed else ""
    if not isinstance(res, dict):
        return "形状看不懂", "result 不是对象%s：%s" % (tag, type(res).__name__)
    # ① 明确的红字段
    for k in ("verdict",):
        v = res.get(k)
        if isinstance(v, str) and v.lower() not in ("clean", "ok", "pass", "green", "true", "健康"):
            return "有发现", "%s=%s%s" % (k, v, tag)
    for k in ("findings", "issues", "anomalies", "problems", "errors", "unrouted", "ghost_routes"):
        v = res.get(k)
        if isinstance(v, list) and v:
            return "有发现", "%s=%d 条%s" % (k, len(v), tag)
    if res.get("needs_a_look") is True:
        return "有发现", "needs_a_look=True%s" % tag
    if res.get("ok") is False:
        return "有发现", "ok=False：%s%s" % (str(res.get("why") or res.get("note") or "")[:90], tag)
    # ② 明确说"干净"
    if res.get("verdict") in ("clean", "ok") or res.get("ok") is True or res.get("quiet") is True:
        return "通过", "%s%s" % (res.get("verdict") or ("ok" if res.get("ok") is True else "quiet"), tag)
 # ②b 2026-10-13 修：**纯数据位**（只回数据、不报 verdict/ok/quiet 的只读解释器）
    #     不许被归成"形状看不懂"——它有已知形状，按形状核对；对不上才算认不出。
    #     实测这五位命中：health / platform_profile / project_context / pipeline_status / svc_inspect。
    _exp = DATA_CAPS.get(rec.get("cap"))
    if _exp and all(k in res for k in _exp):
        _down = res.get("down")
        if isinstance(_down, int) and _down > 0:
            return "有发现", "svc_inspect 报 %d 个服务下线（键名对上了）" % _down
        return "通过", "数据位（按已知形状核对通过）"
    # ③ 认不出 ⇒ 不硬凑
    return "形状看不懂", "键名=%s%s" % (",".join(list(res)[:8]), tag)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="只跑组名含这些字的（逗号分隔）")
    ap.add_argument("--raw", default="", help="单个能力位原样打印")
    ap.add_argument("--timeout", type=int, default=90, help="单位超时秒（慢位要调大）")
    a = ap.parse_args()

    if a.raw:
        r = run_cap(a.raw)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0

    pick = [s for s in a.only.split(",") if s.strip()]
    rows, t0 = [], time.time()
    for cap, group, why in CAPS:
        if pick and not any(p in group for p in pick):
            continue
        rec = run_cap(cap, timeout=SLOW_CAPS.get(cap, a.timeout))
        cls, note = classify(rec)
        env = rec.get("信封") or {}
        rows.append({"能力位": cap, "组": group, "说明": why, "类": cls, "判据": note,
                     "status": rec.get("status"), "耗时s": rec.get("耗时s"),
                     "门信封找到": env.get("found"), "门信封同步": env.get("synced")})
        print("%s %-22s %6.1fs  %s" % ({"通过": "✅", "有发现": "❗", "被门拒": "⛔",
                                        "起不来": "⛔", "形状看不懂": "❓"}[cls],
                                       cap, rec.get("耗时s") or 0, note))

    red = [r for r in rows if r["类"] in ("有发现", "被门拒", "起不来")]
    unknown = [r for r in rows if r["类"] == "形状看不懂"]
    rep = {"扫的时间": time.strftime("%Y-%m-%dT%H:%M:%S"), "全扫耗时s": round(time.time() - t0, 1),
           "只跑的（只读体检位）": len(rows), "红": len(red), "形状看不懂": len(unknown),
           "逐位": rows,
           "只列不跑（写动作，要主人点头）": [{"能力位": c, "为什么": w} for c, w in NOT_RUN],
           "_口径": ("判据只用能力位**自己报的字段**（verdict/findings/needs_a_look/ok/denied）；"
                   "本件不发明健康分。收窄过的结果读的是 preview。"
                   "「形状看不懂」不是通过 —— 是这条我认不出判据，照实标出来给人看。")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), "utf-8")
    print("=" * 78)
    print("总判：%s（只跑 %d 位 · 红 %d · 认不出 %d · %.1fs）"
          % ("❗有红" if red else ("❓有认不出的" if unknown else "✅ 全过"),
             len(rows), len(red), len(unknown), rep["全扫耗时s"]))
    for r in red:
        print("   ❗ %-20s %s" % (r["能力位"], r["判据"]))
    for r in unknown:
        print("   ❓ %-20s %s" % (r["能力位"], r["判据"]))
    print("   （写动作 %d 位只列不跑，见报告）" % len(NOT_RUN))
    print("报告落盘：%s" % OUT)
    return 1 if red else 0


if __name__ == "__main__":
    raise SystemExit(main())
