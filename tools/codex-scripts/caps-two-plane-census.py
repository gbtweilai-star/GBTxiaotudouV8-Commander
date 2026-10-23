#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**能力面双平面普查**（只读）—— 回答一个问题：

    「面板上说『172 个能力』，那**能动生产的那一片**在哪儿？」

为什么要有这一件（一手账）：
  第 41 轮查 F5 时挖出 F12：`caps_registry.all_caps()`（172 条能力位）里**没有收录**
  一整批**真在生产上跑、真过门、真能成功**的操作（`room_*` / `collab_*` / `peer_register` /
  `notion` / `tripo` / `mirror_space` / `qiankun` / `deployment_rehearsal` …）。
  证据是审计账：`room_release` 31 次 call / **7 次 ok** / 14 次 preflight_checked / 17 次因缺作用域 denied。
  ⇒ 面板 / `omni` / 普查报的「172 个能力」，**对『写生产/镜像』那一整片是瞎的**。

  改 `caps_registry.py` 是**主人专属**（红线：不经授权不许改）⇒ 本器**什么都不改**，
  只把**两个平面各自的成员与来源**摊开印出来，让主人能看着数拍板 D13。

口径（三条，不许念过头）：
  1. **平面一 = 注册表**：`caps_registry.BENIGN_CAPS`（唯一真源，只读）。
  2. **平面二 = 注册表之外的生产原语**：只收**有权威出处**的名字 ——
     `preflight` 的改状态名单 / AGENTS.md 点名的生产动作 / 审计账里**有 ok 记录**的 kind。
     **每条都带出处**；出处拿不到的**不写进来**（宁可少列，不许凑数）。
  3. **两个平面都不是『全部真相』**：平面二是"注册表没收录但在跑的"，不是"注册表漏了"——
     是不是漏，是**口径问题**，由主人定；本器只负责把事实摆平。

用法：python tools/codex-scripts/caps-two-plane-census.py [--json]
只读：不联网、不写盘、不改注册表。退出码：0（本器不判红绿，只出读数）。
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _plane1() -> dict:
    from gbt_allinone import caps_registry as CR

    caps = CR.all_caps()
    dom = collections.Counter(c.get("domain", "?") for c in caps)
    return {"names": {c["name"] for c in caps}, "count": len(caps),
            "by_domain": dict(sorted(dom.items(), key=lambda x: -x[1]))}


def _plane2(plane1_names: set) -> list:
    """注册表之外、**有出处**的生产原语。每条 = {name, 出处}。"""
    out: dict = {}

    def add(name: str, src: str) -> None:
        if not name or name in plane1_names:
            return
        out.setdefault(name, []).append(src)

    # ① preflight 的「会改状态」名单（唯一真源，不另抄）
    try:
        from gbt_allinone import preflight
        for n in sorted(preflight.state_changing_kinds()):
            add(n, "preflight.state_changing_kinds()")
    except Exception as exc:  # noqa: BLE001
        add("", "")  # 不写占位；只记在 note 里
        out.setdefault("__note_preflight__", ["读不到 preflight：%s" % type(exc).__name__])

    # ② AGENTS.md 点名的生产动作（仓库自己的治理文件）
    agents = ROOT / "AGENTS.md"
    if agents.is_file():
        text = agents.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"`([a-z][a-z0-9_]{3,})`", text):
            name = m.group(1)
            if name.startswith(("room_", "mirror_", "one_key_", "pipeline_", "qiankun")):
                add(name, "AGENTS.md 点名的生产动作")

    # ③ 审计账里**有 ok 记录**的 kind（真跑成过，不是"调用过"）
    try:
        from gbt_allinone import _paths
        p = Path(_paths.STORE_DIR) / "audit.jsonl"
        if p.is_file():
            ok_kinds = collections.Counter()
            for line in p.open(encoding="utf-8", errors="replace"):
                line = line.strip()
                if not line:
                    continue
                try:
                    j = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                if j.get("event") != "ok":
                    continue
                k = (j.get("meta") or {}).get("kind")
                if k:
                    ok_kinds[k] += 1
            for k, n in ok_kinds.items():
                if k not in plane1_names:
                    add(k, "审计账 event=ok ×%d" % n)
    except Exception as exc:  # noqa: BLE001
        out.setdefault("__note_audit__", ["读不到审计账：%s" % type(exc).__name__])

    rows = []
    for name, sources in sorted(out.items()):
        if name.startswith("__note"):
            continue
        # 出处分三档 —— **不许把三档念成一句**（"出现在审计里" ≠ "有实现" ≠ "跑成了"）
        in_truth = name in _TRUTH_PROBE_NAMES
        in_code = name in _CODE_LITERAL_NAMES
        kind = ("代码里有字面量" if in_code else
                ("被 truth_scan 当探针调过（run_task）" if in_truth else
                 "只在审计账里出现过"))
        rows.append({"name": name, "sources": sorted(set(sources)), "provenance": kind})
    return rows


def _scan_names(names: list) -> tuple:
    """把几个真源翻一遍，给每个名字定出处（不改任何东西）。"""
    pkg = ROOT / "gbt_allinone"
    code_text = []
    for p in pkg.rglob("*.py"):
        if "__pycache__" in str(p) or ".pylibs" in str(p) or "/store/" in str(p).replace("\\", "/"):
            continue
        try:
            code_text.append(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    blob = "\n".join(code_text)
    truth_src = ""
    tp = pkg / "truth_scan.py"
    if tp.is_file():
        truth_src = tp.read_text(encoding="utf-8", errors="replace")
    code_lit, truth_called = set(), set()
    for n in names:
        if ('"%s"' % n) in blob or ("'%s'" % n) in blob:
            code_lit.add(n)
        if ('"%s"' % n) in truth_src or ("'%s'" % n) in truth_src:
            truth_called.add(n)
    return code_lit, truth_called


_CODE_LITERAL_NAMES: set = set()
_TRUTH_PROBE_NAMES: set = set()

# 钱面：这些名字**绝对不许探活**（探一下就可能真动钱/真开户）
MONEY_PREFIXES = ("ledger_", "receive_", "pool_", "wallet_")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="能力面双平面普查（只读）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    p1 = _plane1()
    p2 = _plane2(p1["names"])
    global _CODE_LITERAL_NAMES, _TRUTH_PROBE_NAMES
    _CODE_LITERAL_NAMES, _TRUTH_PROBE_NAMES = _scan_names([r["name"] for r in p2])
    # 重新标出处（上面 _plane2 已经建好行，这里补 provenance）
    for r in p2:
        if r["name"] in _CODE_LITERAL_NAMES:
            r["provenance"] = "代码里有字面量"
        elif r["name"] in _TRUTH_PROBE_NAMES:
            r["provenance"] = "被 truth_scan 当探针调过（run_task）"
        else:
            r["provenance"] = "只在审计账里出现过"
    money = [r["name"] for r in p2 if r["name"].startswith(MONEY_PREFIXES)]
    notes = []
    try:
        from gbt_allinone import preflight
        notes.append("改状态名单来自 preflight.state_changing_kinds()（唯一真源，本器不另抄）")
        del preflight
    except Exception:  # noqa: BLE001
        notes.append("⚠ preflight 读不到 ⇒ 平面二缺『改状态』那一支")

    rep = {"readonly": True,
           "plane1": {"label": "注册表能力位（caps_registry.BENIGN_CAPS）",
                      "count": p1["count"], "by_domain": p1["by_domain"]},
           "plane2": {"label": "注册表之外、在审计账里出现过被分派的 kind",
                      "count": len(p2), "rows": p2,
                      "provenance_legend": {
                          "代码里有字面量": "这个字符串在包内源码里出现过（不代表有实现）",
                          "被 truth_scan 当探针调过（run_task）": "仓库自己的真值扫描调过它",
                          "只在审计账里出现过": "只在账里见过；**不许念成『有实现』或『跑成了』**"}},
           "money_plane": {"count": len(money), "names": money,
                           "warning": ("这批是**钱面**（ledger_/receive_/pool_/wallet_）—— "
                                       "**本器不探活**：探一下就可能真开户/真动钱。"
                                       "要判它们通不通，必须主人在场、且明确授权。")},
           "boundary": ("本器**什么都不改**（改 caps_registry.py 是主人专属）。两个平面都不是『全部真相』："
                        "平面二是『注册表没收录、但在审计里被分派过』的名字，是不是漏由主人定（D13）。"
                        "**三种出处不许念成一句**：出现在代码里 ≠ 有实现 ≠ 跑成了。"
                        "钱面**一律不探活**。只读、不联网、不写盘。"),
           "notes": notes}

    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("═══ 能力面双平面普查（只读 · 不改任何东西）═══")
        print("")
        print("平面一 · %s" % rep["plane1"]["label"])
        print("  共 **%d** 条（面板/omni 报的就是这个数）" % p1["count"])
        top = list(p1["by_domain"].items())[:6]
        print("  域分布前 6：%s" % " · ".join("%s %d" % (k, v) for k, v in top))
        print("")
        print("平面二 · %s" % rep["plane2"]["label"])
        print("  共 **%d** 条（注册表里一条都没有）—— 但**三种出处不许念成一句**" % len(p2))
        by_prov = collections.Counter(r["provenance"] for r in p2)
        for k, v in by_prov.most_common():
            print("    · %s：%d 条" % (k, v))
        for r in p2[:14]:
            print("   · %-26s [%s]" % (r["name"], r["provenance"]))
        if len(p2) > 14:
            print("   · …共 %d 条（见 --json）" % len(p2))
        print("")
        print("🔴 钱面：**%d** 条（%s…）—— **本器一律不探活**" % (len(money), "、".join(money[:5])))
        print("   探一下就可能真开户/真动钱 ⇒ 要判通不通，必须主人在场且明确授权。")
        print("")
        print("边界：%s" % rep["boundary"])
        for n in notes:
            print("  · %s" % n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
