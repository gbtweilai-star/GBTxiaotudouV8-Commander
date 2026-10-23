#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**密钥一致性对账**（只读 · 只印掩码）—— 同一个密钥如有两份，它们还一样吗？

为什么要有这一件（一手账）：
  主人令「密钥全部部署跟双向插件一样、可以自动读取」⇒ 在 User 作用域的注册表之外，
  又把密钥收了一份进 DPAPI 保险箱。**两份就是两个真相源** ——
  轮换时只改一处，另一处就静默过期。这不是假想：本器首跑就现读出一条**已经分叉**的：
      · `agnes`：保险箱 `sk-HX****` vs 注册表 `sk-Oy****`
  分叉的后果不是报错，是"**有时能通、有时 401**"，最难查的那类故障。
  ⇒ 与其靠人记得两边都改，不如**让它对得起来**：一条命令，逐 profile 比。

判什么（四态）：
  · `一致`          —— 两处都有且逐字相同（不可见处只比长度与哈希，不印值）
  · `分叉`          —— 两处都有但不同 ⇒ **红**（就是要人判哪份是新的）
  · `只在保险箱`    —— 注册表没有、库里有（正常：主人直接用 set 收进来的）
  · `只在注册表`    —— 库没有、注册表有（= 还没收进库；**不是错**，是待迁）

红线：**只印掩码与长度**，明文只在内存里比；不写盘、不改注册表、不改保险箱。
用法：python tools/codex-scripts/key-consistency-check.py [--json]
退出码：0 = 没有分叉；1 = 有分叉（要人判）；2 = 环境不支持（非 Windows / 读不到注册表）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import deepseek_key as dk  # noqa: E402


def _registry_values() -> dict:
    import winreg

    out = {}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
        i = 0
        while True:
            try:
                n, v, _t = winreg.EnumValue(k, i)
                out[n] = v
                i += 1
            except OSError:
                break
    return out


def _fingerprint(v: str) -> str:
    """不可见处只比**长度 + 前 12 位指纹**：能判等，又不泄漏值。"""
    v = (v or "").strip()
    if not v:
        return ""
    return "%d/%s" % (len(v), hashlib.sha256(v.encode("utf-8")).hexdigest()[:12])


def classify(vault_key: str, reg_val: str) -> str:
    """纯函数：给定"库里的"与"注册表里的"，判四态。

    抽出来是为了**能被带牙的用例直接测**（不必真去改注册表就能造出"分叉"）。
    判据只有一条要点：**两处都有且不同 = 分叉（红）**；只有一处不算错 ——
    保险箱独有是正常的（主人直接用 `set` 收进来的），注册表独有只是"待迁"。
    """
    v = (vault_key or "").strip()
    r = (reg_val or "").strip()
    if v and r:
        return "一致" if v == r else "分叉"
    if v:
        return "只在保险箱"
    if r:
        return "只在注册表"
    return "两处都没有"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="密钥一致性对账（只读 · 只印掩码）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    try:
        reg = _registry_values()
    except Exception as exc:  # noqa: BLE001
        print("读不到注册表（%s: %s）⇒ 无法对账" % (type(exc).__name__, str(exc)[:80]))
        return 2

    rows = []
    for name in sorted(dk._PROFILES):
        spec = dk._PROFILES[name]
        env_name = spec["env"]
        # 只看保险箱（忽略环境变量）—— 这条判的是"两份存量对不对得上"
        try:
            vault_key, _src = dk.load_from_vault(name)
        except Exception as exc:  # noqa: BLE001
            # 🔴 2026-09-26 自纠：单个 profile 的库读不动（DPAPI 损坏等）原来会让整器
            #    traceback 退出 1 —— 而 1 的语义是"有分叉要人判"，错误信号被污染。
            #    现在该行如实记"读不动"，其余 profile 照常对账；"读不动"与"分叉"同算不绿。
            _reg = (reg.get(env_name) or "").strip()
            rows.append({"profile": name, "env": env_name, "verdict": "读不动", "same": None,
                         "vault": "", "vault_fp": None,
                         "registry": dk.mask(_reg) if _reg else "",
                         "registry_fp": _fingerprint(_reg),
                         "note": "%s: %s" % (type(exc).__name__, str(exc)[:80])})
            continue
        reg_val = (reg.get(env_name) or "").strip()
        verdict = classify(vault_key, reg_val)
        same = (vault_key == reg_val) if (vault_key and reg_val) else None
        rows.append({
            "profile": name, "env": env_name, "verdict": verdict, "same": same,
            "vault": dk.mask(vault_key) if vault_key else "",
            "vault_fp": _fingerprint(vault_key),
            "registry": dk.mask(reg_val) if reg_val else "",
            "registry_fp": _fingerprint(reg_val),
        })

    # 🔴 2026-09-26：**读不动 ≠ 干净** —— 库解不开的 profile 也算"不绿"，否则保险箱
    #    坏了反而对出全绿的假读数（与 precommit-secret-scan 的反空洞同一条纪律）。
    split = [r for r in rows if r["verdict"] in ("分叉", "读不动")]
    diverged = [r for r in rows if r["verdict"] == "分叉"]
    unreadable = [r for r in rows if r["verdict"] == "读不动"]
    if a.json:
        print(json.dumps({"ok": not split, "rows": rows,
                          "note": "只印掩码与指纹（长度+sha256 前 12 位）；明文只在内存里比"},
                         ensure_ascii=False, indent=2))
    else:
        print("═══ 密钥一致性对账（保险箱 ↔ User 作用域注册表）═══")
        for r in rows:
            tag = {"一致": "✅ 一致", "分叉": "🔴 分叉", "读不动": "🟣 读不动（库解不开）",
                   "只在保险箱": "🟦 只在保险箱",
                   "只在注册表": "🟨 只在注册表（待迁）", "两处都没有": "⚪ 两处都没有"}[r["verdict"]]
            fp = ""
            if r["verdict"] == "分叉":
                fp = "  [库 %s vs 注册表 %s]" % (r["vault_fp"], r["registry_fp"])
            print("  %-14s %-18s 库=%s 注册表=%s%s"
                  % (tag, r["env"], r["vault"] or "-", r["registry"] or "-", fp))
        print("")
        print("合计 %d 个 profile：一致 %d · **分叉 %d** · 读不动 %d · 只在保险箱 %d · 只在注册表 %d · 都没有 %d"
              % (len(rows),
                 sum(1 for r in rows if r["verdict"] == "一致"),
                 len(diverged), len(unreadable),
                 sum(1 for r in rows if r["verdict"] == "只在保险箱"),
                 sum(1 for r in rows if r["verdict"] == "只在注册表"),
                 sum(1 for r in rows if r["verdict"] == "两处都没有")))
        if diverged:
            print("🔴 分叉的：%s ⇒ **要人判哪份是新的**（两份都能用最麻烦：时通时 401）"
                  % "、".join(r["profile"] for r in diverged))
        if unreadable:
            print("🟣 读不动的：%s ⇒ 保险箱解不开（DPAPI 损坏/换了 Windows 用户？）—— **不当干净**，要人看"
                  % "、".join(r["profile"] for r in unreadable))
        print("边界：本器只对账**存量**，不判密钥是否有效（那要真打一次接口）；只读，不改任何一处。")
    return 1 if split else 0


if __name__ == "__main__":
    raise SystemExit(main())
