# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""预热：把「判据需要的运行时产物」先跑出来，再跑测试。

## 为什么需要它

2026-11-04 实测：2597 个测试里有 170 条红。逐条追下去，除了「缺系统程序」「外部组件不在本仓」
这两类（已分别由 Dockerfile 和 tests/_external.py 处理），还有一大类是：

    needs_build / 索引不在 ⇒ 先 op=build / 还没扫过 / 清单缺失

这些**不是代码 bug，也不是环境缺程序** —— 是「这台机器上还没跑过那些初始化」。
拿一份干净代码直接跑判据，它当然答不上来：产物还没生成。

**预热 = 在跑判据之前，把本仓自带的、幂等的、不需要外部程序的初始化先跑一遍。**

## 边界（很重要，别越界）

只跑同时满足四条的东西：
  ① 本仓自带（不需要 Blender / ComfyUI / 私有云脚本）
  ② **幂等**（重复跑不改变语义，只刷新产物）
  ③ 不写仓外（写了也由 `obsidian_vault._write` 自动留账，但这里不应触发）
  ④ 失败**不阻断**（某条预热失败要如实报，不能让整个流程挂掉 —— 它可能只是本机缺某样东西）

## 它不是什么

它**不**试图让测试全绿。它只做一件事：**把「本机没跑过初始化」这个可消除的变量消掉**，
让剩下的红只剩真问题。消不掉的（需要 Blender 等）会明确列在 `skipped` 里。

## 用法

    python tools/codex-scripts/warmup.py            # 人读
    python tools/codex-scripts/warmup.py --json     # 机读（CI 用）
    python tools/codex-scripts/warmup.py --only code_audit
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (能力位, 参数, 它能解掉什么) —— 第三条不是注释，是**选择依据**：
# 说不清"跑它能解哪个判据"的初始化，不该放进来自动跑。
JOBS = [
    ("code_audit", {"op": "scan"},
     "代码审计的扫描产物 —— 解掉「code_audit op=report 还没扫过」这类"),
    ("code_audit", {"op": "report"},
     "审计报告 —— 依赖上一条的扫描结果"),
    ("omni_plug", {"op": "page_index"},
     "页索引 —— 解掉「索引不在 ⇒ 先 op=build」这类（omni_plug **没有** build op，"
     "是 page_index；照抄报错文案里的 op 名会跑空）"),
    ("cap_self", {"op": "verify"},
     "能力位三数一致（注册/快照/分派）—— 顺手校验，也刷新快照读数"),
    ("growth_hooks", {"op": "shortboard"},
     "短板读数 —— 解掉 growth_hooks 相关断言缺输入"),
    ("cap_tags", {"op": "tags"},
     "能力标签表（owner/open 分布）—— 契约真源，判据与文档都读它（op 名叫 tags，不叫 rebuild）"),
]


def _unwrap(env: dict) -> dict:
    """**三层信封**：`run_task` → `gbt_result` → `result` → 本体。

    血账：本仓最容易出错的读回执层级。只钻一层会拿到 `{"status","kind","result"}`，
    看着像成功、其实没读到 `ok`。
    """
    body = env.get("gbt_result") or env
    if isinstance(body.get("result"), dict):
        return body["result"]
    return body


def run_one(kind: str, params: dict) -> dict:
    t0 = time.time()
    try:
        sys.path.insert(0, str(ROOT))
        import gbt_allinone as gbt                     # noqa: PLC0415
        env = gbt.run_task(kind, dict(params))
        body = _unwrap(env)
        ok = bool(env.get("ok")) and body.get("ok", True) is not False
        return {"kind": kind, "op": params.get("op"), "ok": ok,
                "status": env.get("status"), "error": str(body.get("error") or "")[:200],
                "seconds": round(time.time() - t0, 2)}
    except Exception as e:                             # noqa: BLE001
        return {"kind": kind, "op": params.get("op"), "ok": False,
                "status": "exception", "error": f"{type(e).__name__}: {str(e)[:200]}",
                "trace": traceback.format_exc(limit=2)[-400:],
                "seconds": round(time.time() - t0, 2)}


def main(argv: list) -> int:
    only = ""
    if "--only" in argv:
        i = argv.index("--only")
        if i + 1 < len(argv):
            only = argv[i + 1]

    results = []
    for kind, params, why in JOBS:
        if only and kind != only:
            continue
        r = run_one(kind, params)
        r["why"] = why
        results.append(r)

    ok = [r for r in results if r["ok"]]
    bad = [r for r in results if not r["ok"]]

    if "--json" in argv:
        print(json.dumps({"total": len(results), "ok": len(ok), "failed": len(bad),
                          "rows": results}, ensure_ascii=False))
        # 预热失败**不算致命**：它可能只是本机缺某样东西，而这一条不应拦住整个流程。
        # 但必须让调用方看得见 —— 所以退出码非零，由调用方决定要不要忽略。
        return 1 if bad else 0

    print("=" * 78)
    print(f"预热（warmup）· 共 {len(results)} 项")
    print("=" * 78)
    for r in results:
        mark = "✅" if r["ok"] else "🔴"
        print(f"  {mark} {r['kind']:<14} op={str(r['op']):<8} {r['seconds']:>5.2f}s"
              f"  {'' if r['ok'] else r['error'][:70]}")
        if not r["ok"] and r.get("trace"):
            for line in r["trace"].strip().splitlines()[-2:]:
                print(f"       {line.strip()[:100]}")
    print()
    print(f"成功 {len(ok)} · 失败 {len(bad)}")
    if bad:
        print()
        print("失败的项**不代表预热没用** —— 它可能只是本机缺某样东西；")
        print("但请如实报出来，不要用「假装成功」把它盖过去（那会让后面的判据基于假前提）。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
