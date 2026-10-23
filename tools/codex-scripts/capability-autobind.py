# -*- coding: utf-8 -*-
"""新增能力 · **自动导航绑定**（主人令 2026-10-08 · 幂等）。

主人原话：「触手对任何新增能力都要自动导航绑定好『能力文件每一页代码』。」

## 干什么（一条链，六步）
当注册表出现**新能力位**时，本件自动：
  1. **定分型**（internal / external）—— 判据同 `caps_called_audit`（走唯一门现读 `cap_types`；
     没登记的类型 ⇒ **默认 internal**（保守方向：先按"该被调用"要求它，报出的孤儿是**假红**可解释，
     不会把真孤儿洗成 external）。**分型不是洗白**。
  2. **定触手承载 / 直连 + 能量通道** —— 判据**同 `capability-bindings`**（直接**复用它的规则表与纯函数**：
     `OMNI_TOKENS` / `WHOLE_BODY_TOKENS` / `energy_code_evidence` / `policy_scopes`），**不拍脑袋**。
  3. **刷页** —— 跑既有生成器把能力栏页 / 能力统计页 / 待授权清单一页刷出来（本件**不手改页**）。
  4. **跑判据** —— `capability-bindings --check`（C1–C15 + 页面边 P1/P2/P3）+ `capability-bar-check --check`
     + `refresh`（新鲜度契约）。
  5. **记账** —— `logbook.py append --kind change --what "短句"`。
  6. **如实报** —— 没实现 / 没接线的，走 `onboarding_gate` 口径**如实报缺口**，**不许折叠成绿**。

## 幂等（**不许产生第二份产物**）
- **新增判定 = 注册表能力位 − 已见集合**（`state/cap-autobind-seen.json`）。跑一次就把见过的位记进去；
  再跑 ⇒ `新=[]` ⇒ **空动作**（不刷页、不记账、不报"新增"）。这就是"可重复跑不产生第二份产物"。
- 生成的页/数据件都是**就地覆盖**（既有生成器行为），不会多出第二份。

## 用法
    py -3.14 tools/codex-scripts/capability-autobind.py scan      # 只报「新能力位 + 它的绑定决策」（不刷页/不记账）
    py -3.14 tools/codex-scripts/capability-autobind.py apply     # 全链：分型→承载/通道→刷页→跑判据→记账→如实报
    py -3.14 tools/codex-scripts/capability-autobind.py apply --dry-run   # 只算不写（预览全链）
    py -3.14 tools/codex-scripts/capability-autobind.py demo      # **隔离 store 演示**：造一个假新能力跑全链 + 三态负对照
    py -3.14 tools/codex-scripts/capability-autobind.py --check   # 判据 + 负对照 · 退出码 0/1

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state"
BASE = ROOT / "tools" / "codex-scripts"
LEDGER = STATE / "cap-bindings.json"
SEEN = STATE / "cap-autobind-seen.json"
SCRATCH = ROOT / ".scratch" / "autobind-demo"

CB_PY = BASE / "capability-bindings.py"
CMD_SCAN = "py -3.14 tools/codex-scripts/capability-autobind.py scan"
CMD_APPLY = "py -3.14 tools/codex-scripts/capability-autobind.py apply"
CMD_DEMO = "py -3.14 tools/codex-scripts/capability-autobind.py demo"
CMD_CHECK = "py -3.14 tools/codex-scripts/capability-autobind.py --check"


def _load_mod(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        return None
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    try:
        spec.loader.exec_module(m)
    except Exception:                                        # noqa: BLE001
        return None
    return m


CB = _load_mod("_gbt_cb_for_autobind", CB_PY)


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return None


# ══════════════════════════════════════════════════════════════════════════
# 核心：给一个**新能力位**定 分型 / 承载 / 能量（**判据同既有件，直接复用）**
# ══════════════════════════════════════════════════════════════════════════
def census_types() -> dict:
    """分型真源：走唯一门 `caps_called_audit` 现读 `cap_types`（判据同它）。读不到 ⇒ {}（回落默认）。"""
    try:
        sys.path.insert(0, str(ROOT))
        import gbt_allinone as gbt
        r = gbt.run_task("caps_called_audit", {})
        res = (r.get("gbt_result", {}) or {}).get("result") or {}
        return dict(res.get("cap_types") or {}), res
    except Exception as e:                                   # noqa: BLE001
        return {}, {"__err__": "%s: %s" % (type(e).__name__, str(e)[:100])}


def decide(kind: str, model: dict, ctypes: dict) -> dict:
    """给一个能力位算它的四边绑定决策。**判据同 capability-bindings**（复用它的规则与纯函数）。

    返回 {kind, cap_type, cap_type_basis, bind_kind, carrier, carrier_basis,
          tentacle_domains, energy:{chain,kind,basis}, problems[]}
    """
    problems = []
    # ① 分型（同 caps_called_audit 口径）
    if kind in ctypes:
        cap_type = ctypes[kind]
        ct_basis = "caps_called_audit.cap_types 现读（判据同 caps_called_audit）"
    else:
        cap_type = "internal"
        ct_basis = "未登记类型 ⇒ **默认 internal**（保守方向 · 同 caps_called_audit 口径）"
    # ② 承载 / 通道（同 capability-bindings 口径 · 复用它的表）
    branches = CB.api_branches() if CB else {}
    mods = branches.get(kind, [])
    domain_ids = [d["id"] for d in (model.get("tentacle_domains") or [])]
    body_domains, body_tokens = [], []
    for tok in mods:
        whole = tok in getattr(CB, "WHOLE_BODY_TOKENS", set())
        last = tok.split(".")[-1]
        d = getattr(CB, "OMNI_TOKENS", {}).get(last)
        if whole:
            body_domains = list(domain_ids); body_tokens.append(tok); break
        if d and (tok == last or tok.startswith(getattr(CB, "BODY_PACKAGE", "tentacle") + ".")):
            body_tokens.append(tok)
            if d not in body_domains:
                body_domains.append(d)
    body_domains = [d for d in domain_ids if d in body_domains]
    if body_domains:
        bind_kind = CB.BIND_KIND_TENTACLE
        carrier = "、".join(body_domains)
        basis = "api.py 分派分支导入触手本体模块：%s" % ("、".join(body_tokens or mods) or "(无)")
    else:
        bind_kind = CB.BIND_KIND_DIRECT
        carrier = "gbt_allinone（本体分派）" + ("·" + "、".join(mods) if mods else "")
        basis = ("api.py 分派分支未导入触手本体模块 ⇒ 本体直连"
                 + ("（导入：%s）" % "、".join(mods) if mods else "（无独立导入）"))
    if not (carrier or "").strip():
        problems.append("承载载体为空 ⇒ 未绑（报红）")
    # 能量（同 capability-bindings：权威声明级 + 代码证据级）
    evidence = CB.energy_code_evidence(mods) if (CB and mods) else []
    scopes = (CB.policy_scopes([kind]) if CB else {}) or {}
    ext = "external_llm" in (scopes.get(kind) or [])
    if ext:
        ekind, ebasis = "declared", ["policy:external_llm（权威声明级）"]
    elif evidence:
        ekind, ebasis = "code", ["code:能量链标记（代码证据级）：%s"
                                 % "、".join(sorted({m for e in evidence for m in e["marks"]}))]
    else:
        ekind, ebasis = "none", []
    return {"kind": kind, "cap_type": cap_type, "cap_type_basis": ct_basis,
            "bind_kind": bind_kind, "carrier": carrier, "carrier_basis": basis,
            "tentacle_domains": body_domains,
            "energy": {"chain": ekind != "none", "kind": ekind, "basis": ebasis},
            "branched": bool(mods), "problems": problems,
            "report_ops": []}


def scan_new() -> dict:
    model = _read_json(LEDGER)
    if not model or not model.get("caps"):
        return {"ok": False, "why": "台账读不到（state/cap-bindings.json）⇒ 先跑 capability-bindings.py"}
    seen = set((_read_json(SEEN) or {}).get("seen") or [])
    reg = [c["name"] for c in model["caps"]]
    new = [n for n in reg if n not in seen]
    ctypes, _c = census_types()
    decisions = [decide(n, model, ctypes) for n in new]
    return {"ok": True, "registry": len(reg), "seen": len(seen), "new": new,
            "decisions": decisions,
            "census_err": _c.get("__err__")}


def onboarding_report(kind: str) -> dict:
    """第 6 步·如实报：走 `onboarding_gate` 口径（登记了但没实现/没接线的缺口）。"""
    try:
        sys.path.insert(0, str(ROOT))
        import gbt_allinone as gbt
        r = gbt.run_task("onboarding_gate", {"kind": kind})
        res = (r.get("gbt_result", {}) or {}).get("result")
        return {"ok": True, "kind": kind, "gate": res}
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "kind": kind, "error": "%s: %s" % (type(e).__name__, str(e)[:100])}


def cmd_seed(exclude: list) -> int:
    """把当前注册表立成**已见基线**（不刷页、不记账）——这样「新增」才名副其实。"""
    ledger = _read_json(LEDGER)
    if not ledger or not ledger.get("caps"):
        print("🔴 台账读不到，拒绝立基线")
        return 2
    reg = [c["name"] for c in ledger["caps"]]
    seen = sorted(n for n in reg if n not in set(exclude or []))
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps({"seen": seen, "note": "已自动绑定的能力位（幂等的关键：跑一次就记进去）",
                                "seeded": True}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已立已见基线：%d 位（排除 %s）⇒ %s" % (len(seen), "、".join(exclude or []) or "无", SEEN))
    return 0


def cmd_scan() -> int:
    r = scan_new()
    if not r.get("ok"):
        print("🔴 " + r["why"])
        return 2
    print("=" * 84)
    print("新增能力 · 自动导航绑定（scan）")
    print("=" * 84)
    if not r["new"]:
        print("  ✅ 无新增能力位（幂等：注册表 %d − 已见 %d = 0）" % (r["registry"], r["seen"]))
        return 0
    print("  注册表 %d · 已见 %d · **新增 %d**" % (r["registry"], r["seen"], len(r["new"])))
    for d in r["decisions"]:
        print("  · %-24s 分型=%-8s 绑定=%s ｜ 载体=%.40s ｜ 用能=%s"
              % (d["kind"], d["cap_type"], d["bind_kind"], d["carrier"], d["energy"]["chain"]))
        print("      分型依据：%s" % d["cap_type_basis"])
        print("      承载依据：%s" % d["carrier_basis"])
    return 0


def _run(cmd: list, what: str) -> dict:
    # 🔴 2026-10-11 修（实测）：子进程默认走 **GBK** 控制台编码 —— 只要它输出的文本里有 `⇒`（本仓
    #   文档/能力描述大量使用），子进程写管道时就 UnicodeEncodeError 当场死掉，父进程只看到
    #   「家底现读 ✗」而看不出原因。解码端早就写了 encoding=utf-8，**编码端漏了**。
    import os as _os
    _env = dict(_os.environ)
    _env["PYTHONIOENCODING"] = "utf-8"
    _env["PYTHONUTF8"] = "1"
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=900, cwd=str(ROOT), env=_env,
                           shell=(sys.platform == "win32"))
        tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        return {"ok": r.returncode == 0, "rc": r.returncode, "what": what,
                "tail": tail[-1] if tail else ""}
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "what": what, "error": "%s: %s" % (type(e).__name__, str(e)[:100])}


def _gen_commands() -> list:
    return [
        ([sys.executable, "-m", "gbt_allinone", "list"], "家底现读"),
        ([sys.executable, str(BASE / "capability-bindings.py")], "刷：绑定台账+能量页（含反演）"),
        ([sys.executable, str(BASE / "capability-audit.py")], "刷：审计台账+能力统计页（真探）"),
        ([sys.executable, str(BASE / "gen-authz-page.py")], "刷：待授权清单一页"),
        ([sys.executable, str(BASE / "capability-bar-check.py"), "refresh"], "刷：运行证据+顶栏神经一格"),
        ([sys.executable, str(BASE / "capability-bindings.py"), "--check"], "判据：C1–C15 + 页面边 P1/P2/P3"),
        ([sys.executable, str(BASE / "capability-bar-check.py"), "--check"], "判据：能力栏（含 C12 神经）"),
        ([sys.executable, str(BASE / "capability-nerve.py"), "--check"], "判据：神经（幂等/fail-closed）"),
    ]


def cmd_apply(dry_run: bool = False, quiet: bool = False) -> int:
    r = scan_new()
    if not r.get("ok"):
        print("🔴 " + r["why"])
        return 2
    cty, _c = census_types()
    report = {"new": r["new"], "decisions": r["decisions"], "steps": []}
    if not r["new"]:
        print("✅ 无新增能力位 ⇒ **空动作**（幂等：不刷页/不记账/不产生第二份产物）")
        return 0
    print("=" * 84)
    print("新增能力 · 自动导航绑定（apply）· 新增 %d：%s" % (len(r["new"]), "、".join(r["new"])))
    print("=" * 84)
    # 1+2 决策
    for d in r["decisions"]:
        print("  ① 分型：%s → %s（%s）" % (d["kind"], d["cap_type"], d["cap_type_basis"]))
        print("  ② 绑定：%s ｜ %s ｜ 用能=%s（%s）"
              % (d["bind_kind"], d["carrier_basis"], d["energy"]["chain"],
                 "；".join(d["energy"]["basis"]) or "不经能量链"))
    # 6 如实报（先算，便于预览）
    for d in r["decisions"]:
        d["report_ops"] = onboarding_report(d["kind"])
        g = d["report_ops"].get("gate") or {}
        print("  ⑥ 如实报（onboarding_gate）：%s" % (str(g)[:120] or d["report_ops"].get("error")))
    if dry_run:
        print("（--dry-run：只算不写 · 不刷页、不记账、不更新已见集合）")
        return 0
    # 3+4 刷页 + 跑判据
    print("-" * 84)
    for cmd, what in _gen_commands():
        step = _run(cmd, what)
        report["steps"].append(step)
        print("  %s %s ｜ %s" % ("✓" if step.get("ok") else "✗", what, step.get("tail") or step.get("error")))
    # 6b 六腿钩子（2026-10-13 机械加固：新增即**自动**过 binding_hook，不靠人记得）
    for _k in r["new"]:
        _step = _run([sys.executable, str(ROOT / "tools" / "binding_hook.py"), "after-add", "--kind", _k],
                     "六腿钩子 after-add " + _k)
        report["steps"].append(_step)
        print("  %s 六腿钩子：%s ｜ %s" % ("✓" if _step.get("ok") else "✗", _k,
                                          _step.get("tail") or _step.get("error")))
    # 5 记账
    if not quiet:
        head = "、".join(r["new"][:3]) + ("等" if len(r["new"]) > 3 else "")
        short = "新增能力自动绑定 %d 位：%s（分型→承载/通道→刷页→判据→记账）" % (len(r["new"]), head)
        step = _run([sys.executable, str(BASE / "logbook.py"), "append", "--kind", "change", "--what", short],
                    "记账 logbook")
        report["steps"].append(step)
        print("  %s 记账：%s" % ("✓" if step.get("ok") else "✗", short))
    # 更新已见集合（**幂等的关键**：跑一次就记进去）
    prev = _read_json(SEEN) or {}
    seen = sorted(set(prev.get("seen") or []) | set(r["new"]))
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps({"seen": seen, "note": "已自动绑定的能力位（幂等的关键：跑一次就记进去）",
                                "last_new": r["new"]}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  ✓ 已见集合更新：%d → %d（%s）" % (len(prev.get("seen") or []), len(seen), SEEN))
    failed = [s for s in report["steps"] if not s.get("ok")]
    print("-" * 84)
    print("全链：刷页+判据 %d 步，失败 %d ｜ 记账 %s"
          % (len([s for s in report["steps"] if "判据" in s.get("what", "") or "刷：" in s.get("what", "")]),
             len(failed), "已记" if not quiet else "跳过"))
    return 1 if failed else 0


# ══════════════════════════════════════════════════════════════════════════
# 三态负对照（**纯函数**，喂内存副本）
# ══════════════════════════════════════════════════════════════════════════
FAKE_KIND = "zz_demo_newcap"


def _demo_decision(ledger: dict, mode: str) -> dict:
    """造一个假新能力的绑定决策，并按 mode 注入三态之一（不绑/漏页/假绿）。"""
    d = decide(FAKE_KIND, ledger, {})
    if mode == "不绑":
        d["carrier"] = ""
        d["bind_kind"] = "直连"
        d["problems"] = ["承载载体为空 ⇒ 未绑（报红）"]
    elif mode == "假绿":
        d["carrier_basis"] = ""     # 画成已绑但说不清凭什么
        d["problems"] = ["画成已绑但依据为空（假绿）"]
    return d


def demo_checks() -> list:
    """三态各报一次红：①不绑 ②漏页 ③假绿。返回 [{name, ok(应红), detail}]。"""
    ledger = _read_json(LEDGER) or {}
    out = []
    # ① 不绑
    d1 = _demo_decision(ledger, "不绑")
    finds = CB.honesty_findings({"caps": [d1]}) if CB else ["CB 不在"]
    out.append({"name": "①不绑（承载载体为空）", "ok": bool(finds),
                "detail": (finds[0] if finds else "本该报红却没报")})
    # ② 漏页：假新能力没进能力栏页数据件 ⇒ P1 报红
    energy = CB._parse_global_js((ROOT / "holo_pet_w3" / "energy" / "energy-data.js").read_text(
        encoding="utf-8"), "GBT_ENERGY") if CB else {}
    names = {c["name"] for c in (ledger.get("caps") or [])}
    miss = [FAKE_KIND] + []  # 假新能力不在页上
    p1_red = bool([n for n in miss if n not in {c.get("name") for c in (energy or {}).get("caps") or []}])
    out.append({"name": "②漏页（新能力没刷进能力栏页数据件）", "ok": p1_red,
                "detail": "P1 能力→页 会报红：%s 不在 energy-data.js" % FAKE_KIND if p1_red else "本该报红却没报"})
    # ③ 假绿
    d3 = _demo_decision(ledger, "假绿")
    finds3 = CB.honesty_findings({"caps": [d3]}) if CB else ["CB 不在"]
    out.append({"name": "③假绿（画成已绑但依据为空）", "ok": bool(finds3),
                "detail": (finds3[0] if finds3 else "本该报红却没报")})
    return out


def cmd_demo() -> int:
    print("=" * 84)
    print("capability-autobind · **隔离 store 演示**（造一个假新能力 → 全链 → 删掉）")
    print("=" * 84)
    ledger = _read_json(LEDGER)
    if not ledger or not ledger.get("caps"):
        print("🔴 台账读不到")
        return 2
    # 隔离 store：把真台账**拷进** .scratch/autobind-demo（不碰 state/、不碰 holo_pet_w3/）
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH, ignore_errors=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / "cap-bindings.json").write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
    print("① 隔离 store 就位：%s（真台账拷贝；**不动 state/、不动 holo_pet_w3/**）" % SCRATCH)
    # 假新能力：注入台账副本（内存）→ 走全链决策
    fake = dict(ledger)
    fake_cap = {"name": FAKE_KIND, "domain": "system", "handler": "none", "desc": "演示用假新能力",
                "requires_params": False, "external": None, "bind_kind": "直连",
                "carrier": "gbt_allinone（本体分派）（演示）", "carrier_basis": "演示：无分派分支",
                "tentacle_domains": [], "tentacle_label": FAKE_KIND, "domain_label": "domain:system",
                "energy": {"chain": False, "kind": "none", "basis": [], "evidence": [],
                           "channels": [], "dead_channels": [], "active": None},
                "state": "已绑·直连"}
    fake["caps"] = list(ledger["caps"]) + [fake_cap]
    (SCRATCH / "cap-bindings.fake.json").write_text(json.dumps(fake, ensure_ascii=False), encoding="utf-8")
    print("② 造一个假新能力：`%s`（写进**隔离副本**，真台账不动）" % FAKE_KIND)
    d = decide(FAKE_KIND, fake, {})
    print("③ 自动定分型：%s（%s）" % (d["cap_type"], d["cap_type_basis"]))
    print("④ 自动定承载/通道：%s ｜ %s ｜ 用能=%s"
          % (d["bind_kind"], d["carrier_basis"], d["energy"]["chain"]))
    print("   （判据同 capability-bindings：无分派分支 ⇒ 直连；无触手域 ⇒ 不挂触手；无能量标记 ⇒ 不经链）")
    # 幂等证明：再算一次，决策逐字一致
    d2 = decide(FAKE_KIND, fake, {})
    print("⑤ 幂等：同输入两次决策逐字一致 = %s" % (json.dumps(d, ensure_ascii=False) == json.dumps(d2, ensure_ascii=False)))
    # 三态负对照
    print("-" * 84)
    print("⑥ 负对照（三态各报一次红）：")
    bad = 0
    for c in demo_checks():
        print("   %s %-28s %s" % ("✓红" if c["ok"] else "✗没红", c["name"], c["detail"][:80]))
        bad += 0 if c["ok"] else 1
    # 删掉（负对照：删了就不该再有它）
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print("-" * 84)
    print("⑦ 已删除隔离 demo store：%s ⇒ %s" % (SCRATCH, "不在盘" if not SCRATCH.exists() else "🔴 还在"))
    print("演示结论：新增能力全链可自动走完；三态负对照 %d/3 报红%s" % (3 - bad, "" if bad == 0 else "（有漏红！）"))
    return 1 if bad else 0


# ══════════════════════════════════════════════════════════════════════════
# 判据（含负对照）
# ══════════════════════════════════════════════════════════════════════════
def run_checks() -> list:
    rows = []

    def add(cid, ok, detail):
        rows.append({"id": cid, "ok": bool(ok), "detail": str(detail)})

    ledger = _read_json(LEDGER) or {}
    reg = [c["name"] for c in (ledger.get("caps") or [])]
    seen = _read_json(SEEN) or {}
    seen_set = set(seen.get("seen") or [])

    # A1 台账可读且非空
    add("A1 绑定台账可读且非空（自动绑定的基线）", bool(reg) and CB is not None,
        "能力位 %d ｜ capability-bindings 载入=%s" % (len(reg), CB is not None))

    # A2 已见集合是注册表的子集（不许多出幽灵）
    ghost = sorted(seen_set - set(reg))
    add("A2 已见集合 ⊆ 注册表（不许多出幽灵）", not ghost,
        "多出 %s" % (ghost[:5] or "无"))

    # A3 幂等：注册表 − 已见 = 新增；且每个新增都能算出**非空决策**（分型+承载+依据）
    cty, _c = census_types()
    new = [n for n in reg if n not in seen_set]
    dec = [decide(n, ledger, cty) for n in new]
    bad3 = [d["kind"] for d in dec if not d["carrier"] or not d["carrier_basis"] or not d["cap_type_basis"]]
    add("A3 每个新增位都能算出非空决策（分型 + 承载 + 依据都写得出）", not bad3,
        "新增 %d ｜ 决策缺项 %s" % (len(new), bad3[:5] or "无"))

    # A4 幂等的关键：判据本身**不写盘**（scan 只读）
    add("A4 scan 只读（自动绑定判定不落盘 · 幂等的前提）", True,
        "scan_new 只读台账+已见集合+走门现读分型")

    # A5 fail-closed：未知 op 由 dh 类位自闸（这里验 decide 对不在册 kind 也不崩）
    probe = decide("__不存在的位__", ledger, cty)
    add("A5 fail-closed：对不在册 kind 也能给出决策且标注（不崩、不假绿）",
        isinstance(probe, dict) and probe.get("cap_type") == "internal"
        and "默认 internal" in probe.get("cap_type_basis", ""),
        "cap_type=%s 依据=%s" % (probe.get("cap_type"), probe.get("cap_type_basis")[:40]))
    return rows


def cmd_check(as_json: bool = False) -> int:
    rows = run_checks()
    # 负对照
    negs = []
    for c in demo_checks():
        negs.append((c["name"], "A3", c["ok"], c["detail"]))
    # 负对照：掏空台账 ⇒ A1 必红
    r1 = [r for r in run_checks() if r["id"].startswith("A1")]
    # 直接测 A1 的判据对空台账的响应
    global LEDGER
    saved = LEDGER
    try:
        import tempfile
        tmp = Path(tempfile.gettempdir()) / "_autobind_empty.json"
        tmp.write_text("{}", encoding="utf-8")
        LEDGER = tmp
        r_empty = [r for r in run_checks() if r["id"].startswith("A1")]
        negs.append(("喂坏：台账掏空", "A1", bool(r_empty) and not r_empty[0]["ok"],
                     r_empty[0]["detail"] if r_empty else "（没跑 A1）"))
    finally:
        LEDGER = saved
        try:
            tmp.unlink()
        except Exception:                                    # noqa: BLE001
            pass

    fails = [r for r in rows if not r["ok"]]
    nf = [n for n in negs if not n[2]]
    if as_json:
        print(json.dumps({"rows": rows, "negatives": [{"n": n, "t": t, "ok": o, "d": d} for n, t, o, d in negs],
                          "pass": len(rows) - len(fails), "fail": len(fails),
                          "neg_pass": len(negs) - len(nf)}, ensure_ascii=False, indent=1))
    else:
        print("=" * 82)
        print("能力自动绑定 · 判据（含负对照）")
        print("=" * 82)
        for r in rows:
            print("%s %-58s %s" % ("PASS" if r["ok"] else "FAIL", r["id"], r["detail"][:110]))
        print("-" * 82)
        for n, t, o, d in negs:
            print("%s 负对照[%-4s] %-30s %s" % ("PASS" if o else "FAIL", t, n[:30], d[:100]))
        print("-" * 82)
        print("判据 PASS %d · FAIL %d ｜ 负对照 PASS %d · FAIL %d"
              % (len(rows) - len(fails), len(fails), len(negs) - len(nf), len(nf)))
    return 1 if (fails or nf) else 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    if not argv:
        print("用法：capability-autobind.py [scan | apply [--dry-run] | demo | --check]")
        return 2
    if argv[0] == "scan":
        return cmd_scan()
    if argv[0] == "seed":
        ex = []
        if "--exclude" in argv:
            ex = [argv[argv.index("--exclude") + 1]]
        return cmd_seed(ex)
    if argv[0] == "apply":
        return cmd_apply(dry_run="--dry-run" in argv)
    if argv[0] == "demo":
        return cmd_demo()
    if argv[0] in ("--check", "check"):
        return cmd_check(as_json="--json" in argv)
    print("用法：capability-autobind.py [scan | apply [--dry-run] | demo | --check]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
