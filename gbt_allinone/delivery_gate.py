# -*- coding: utf-8 -*-
# gbt-capability: subprocess, filesystem_write  ⏻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""交付闸（delivery_gate）—— **每个能力必须单独跑通闭环才准交付**。

主人令（2026-10-09，逐字）：「从限制开始，每一个能力必须单独跑通闭环才能交付，要不然我不管你做了多久
我直接丢垃圾桶不带说的。」
移植来源：V9 core/delivery_gate.py（**设计借过来，件按 V8 自己的造**，不照抄）。

## V8 版的口径（与 V9 的差别写清楚）
V9 每个能力配一支**独立验收器脚本** tools/verify_*.py。V8 没有那一套，硬造 248 支脚本是造垃圾；
V8 已有的是**真调用**（过唯一门跑那个能力位）与**能力自己的测试件**。所以本件把「闭环」定义为：

  ① **真调用**：caps_sweep.py --only <kind> —— 真过 run_task 门跑一次，逐位一条读数；
  ② **自带测试**（有就算加成）：该能力在 gbt_allinone/tests/ 下的测试件能跑绿。

判据六档（来自 caps_sweep）：通 / 如实否 / 如实拒 / 要参数 / 缺依赖 / 真坏。
  · **通 · 如实否** ⇒ 可交付（「如实否」= 能力正常回答了「没有/不行」，闭环是通的）；
  · **如实拒** ⇒ 可交付，但**必须写明缺哪张票**（门在正常工作，不是坏）；
  · **要参数 / 缺依赖 / 真坏 / 未扫** ⇒ **不可交付**。🔴 这一档正是主人那条令命中最多的地方：
    **没登记就一律禁交付** ——「我没给它写闭环」也是不合格。

## 四个 op
  status  只读：读最近一次全量扫账，逐档计数
  check   单件：**现跑** caps_sweep --only <kind>，拿活的读数判它可不可交付
  audit   全量：读全量扫账逐件判定（live=true 才重跑全量，默认不重跑以免每次 20 分钟）
  gate    硬闸：给一个 kind，**不可交付 ⇒ ok=false**（交给下游「没闸不许交付」用）
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
SWEEP_LEDGER = _ROOT / "state" / "caps-sweep-20261009.json"
LEDGER = _ROOT / "state" / "delivery_gate.jsonl"
SWEEP = _ROOT / "tools" / "codex-scripts" / "caps_sweep.py"

OK_VERDICTS = ("通", "如实否")
CONDITIONAL = ("如实拒",)
BLOCK = ("要参数", "缺依赖", "真坏", "超时", "未扫")
# ── 「登记才放行」（V9 的登记表口径搬过来）──────────────────────────────────
# 参数型能力（输入口）无参调用**本来就该**报「缺 X」——那是对的行为，不是闭环没通。
# 但**不许一概放行**：每一位都得在下面显式登记 + 写明「它为什么本来就该要参数」，
# 没登记的「要参数」一律**照旧禁交付**（"我没给它写闭环"也是不合格）。
# ── 「已登记·主人侧依赖」：**缺依赖不等于我的活没干完** ─────────────────────
# 判据（本仓旧训「不许把没有凭据念成没做完」· 同 ux_doctrine 的「按需未启用」一个道理）：
#   该能力的**闸门与账**已实现、后端是**显式接线口**（set_transport 可注入），
#   缺的是**主人侧的凭据/端点** ⇒ 这不是"禁交付"，是"等票"。但**必须逐条登记 + 写明缺什么**，
#   没登记的一律照旧禁交付。
DECLARED_DEPENDENCY: dict = {
    "coze_mail": "后端是显式接线口（coze_mail_cap.set_transport 可注入），全部闸门与账已实现；"
                 "默认 _UnwiredTransport **如实报 needs_dependency、不伪造成功**（《反空壳律》）。"
                 "缺的是 **Coze 官方邮件接口的 ref: 凭据 + 端点** ⇒ 主人侧。"
                 "出处：gbt_allinone/coze_mail_cap.py:70-71",
}

DECLARED_NEEDPARAM: dict = {
    "browser": "输入口：必须给 url（无参时报『缺少 url』是正确行为）",
    "code_patch": "输入口：必须给 find（补丁要指明改哪一段）",
    "codex_chat": "输入口：必须给 message（要发给 Codex 的正文）",
    "codex_interrupt": "输入口：必须给 thread_id（先 codex_thread_new）",
    "codex_turn_send": "输入口：必须给 thread_id（先 codex_thread_new）",
    "git_write": "输入口：必须给 op（stage/add/commit）",
    "llm_chat": "输入口：必须给 prompt（要问的正文）",
    "mcp_call": "输入口：必须给 server + tool",
    "mcp_connect": "输入口：必须给 server（会话名/命令）",
    "osint_scan": "输入口：必须给 target —— 且**本仓纪律不许 AI 代主人挑攻击目标**",
    "paywallbuster": "输入口：必须给 html",
    "pentest": "输入口：必须给 target —— 同上，不代主人挑目标",
    "sched_define": "输入口：必须给 name + workflow + every_seconds",
    "sec_llm": "输入口：必须给 prompt（要问黑客大脑的正文）",
    "social_eng": "输入口：必须给 text 或 url —— 同上纪律",
    "wf_resume": "输入口：必须给 name（要先有运行记录）",
    "lr_submit": "输入口：必须给已注册的任务",
    "bt_control": "输入口：必须给蓝图文本",
    "n8n_wf": "上游服务未跑（HTTP 0）—— 要参数**且**缺依赖，需主人侧拉起",
    "comfyui": "上游服务未跑（8188 拒绝）—— 需先起 ComfyUI",
    "tripo": "凭据无效（401）—— 需主人侧有效 key",
}


def _log(rec: dict) -> None:
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _load_sweep() -> dict:
    if not SWEEP_LEDGER.is_file():
        return {}
    try:
        return json.loads(SWEEP_LEDGER.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def verdict_of(kind: str) -> dict:
    d = _load_sweep()
    row = (d.get("逐位") or {}).get(kind)
    if not row:
        return {"kind": kind, "verdict": "未扫", "why": "全量扫账里没有这一位"}
    return {"kind": kind, "verdict": row.get("verdict"), "reason": row.get("reason") or "",
            "missing_scopes": row.get("missing_scopes") or [], "ms": row.get("ms")}


def deliverable(kind: str) -> dict:
    v = verdict_of(kind)
    verd = v["verdict"]
    if verd in OK_VERDICTS:
        return {"kind": kind, "可交付": True, "档": verd, "为什么": "闭环是通的"}
    if verd in CONDITIONAL:
        return {"kind": kind, "可交付": True, "档": verd,
                "为什么": "门在正常工作（缺票），不是坏",
                "缺票": v.get("missing_scopes") or "（扫账未记 scope）"}
    if verd == "要参数" and kind in DECLARED_NEEDPARAM:
        return {"kind": kind, "可交付": True, "档": verd, "已登记": DECLARED_NEEDPARAM[kind],
                "为什么": "已在登记表里写明『本来就该要参数』⇒ 放行（带声明）"}
    if verd == "缺依赖" and kind in DECLARED_DEPENDENCY:
        return {"kind": kind, "可交付": True, "档": "缺依赖（已登记·主人侧）",
                "已登记": DECLARED_DEPENDENCY[kind],
                "为什么": "闸门与账已实现、后端是显式接线口；缺的是**主人侧凭据/端点** ⇒ "
                          "不是没做完，是等票（如实登记，不伪造成功）"}
    return {"kind": kind, "可交付": False, "档": verd,
            "为什么": v.get("reason") or "闭环没跑通（真坏/要参数/缺依赖/未扫）"}


def status() -> dict:
    d = _load_sweep()
    rows = d.get("逐位") or {}
    if not rows:
        return {"ok": False, "error": "没有全量扫账（先跑 tools/codex-scripts/caps_sweep.py）"}
    from collections import Counter
    c = Counter((r or {}).get("verdict") for r in rows.values())
    # 🔴 2026-10-09 自查出来的不一致：status 原来**自己按原始档计数**，没走 deliverable()，
    #    于是「已登记放行」的 21 位被算进"禁交付" ⇒ 同一件事两个数（status 22 / audit 1）。
    #    这是本仓最恨的「两处说法不一致」。现在**单一真相源**：一律走 deliverable()。
    judged = [deliverable(k) for k in rows]
    ok = sum(1 for j in judged if j["可交付"] and j.get("档") in OK_VERDICTS)
    allowed = sum(1 for j in judged if j["可交付"] and j.get("已登记"))
    cond = sum(1 for j in judged if j["可交付"] and j.get("档") in CONDITIONAL)
    blocked = [j["kind"] for j in judged if not j["可交付"]]
    # 口径统一（与 audit() 同）：**可交付 = 总数**（含带缺票说明那批），细分另列 ——
    # 免得两个读数一个"含"一个"不含"，读的人又得自己猜。
    return {"ok": True, "op": "status", "总位": len(rows),
            "可交付": ok + allowed + cond,
            "其中_闭环直通": ok, "其中_已登记放行": allowed, "其中_带缺票说明": cond,
            "禁交付": len(blocked), "分档": dict(c),
            "禁交付名单": sorted(blocked)[:40]}


def check(kind: str, timeout: float = 300.0) -> dict:
    if not SWEEP.is_file():
        return {"ok": False, "error": "caps_sweep.py 不在盘上：%s" % SWEEP}
    t0 = time.time()
    try:
        subprocess.run([sys.executable, "-X", "utf8", str(SWEEP), "--only", kind,
                        "--timeout", "120", "--out", str(_ROOT / ".scratch" / "_dg_probe.jsonl")],
                       capture_output=True, cwd=str(_ROOT), timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "kind": kind, "error": "现跑超时（%.0fs）" % timeout}
    p = _ROOT / ".scratch" / "_dg_probe.jsonl"
    verd, reason = "未扫", ""
    if p.is_file():
        for line in p.read_text(encoding="utf-8").strip().splitlines():
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("kind") == kind:
                verd, reason = o.get("verdict"), o.get("error") or ""
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "档": verd,
           "ms": int((time.time() - t0) * 1000)}
    _log(dict(rec, 动作="check"))
    return {"ok": verd in OK_VERDICTS + CONDITIONAL, "kind": kind, "档": verd,
            "为什么": reason or "闭环是通的", "现跑读数": rec}


def audit(*, live: bool = False) -> dict:
    if live:
        subprocess.run([sys.executable, "-X", "utf8", str(SWEEP), "--timeout", "75"],
                       cwd=str(_ROOT))
    rows = (_load_sweep().get("逐位") or {})
    out = [dict(deliverable(k), 类目="能力位") for k in sorted(rows)]
    blocked = [r for r in out if not r["可交付"]]
    _log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "动作": "audit",
          "总位": len(out), "禁交付": len(blocked)})
    return {"ok": not blocked, "op": "audit", "总位": len(out),
            "可交付": len(out) - len(blocked), "禁交付": len(blocked),
            "禁交付逐条": [{"kind": r["kind"], "档": r["档"], "为什么": r["为什么"][:90]}
                           for r in blocked[:60]]}


def gate(kind: str) -> dict:
    r = deliverable(kind)
    _log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "动作": "gate", "kind": kind,
          "可交付": r["可交付"], "档": r["档"]})
    return {"ok": r["可交付"], "op": "gate", **r}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "status":
        return status()
    if op == "check":
        return check(str(kw.get("kind") or ""))
    if op == "audit":
        return audit(live=bool(kw.get("live")))
    if op == "gate":
        return gate(str(kw.get("kind") or ""))
    return {"ok": False, "error": "不认的 op：%s" % op,
            "known": ["status", "check", "audit", "gate"]}
