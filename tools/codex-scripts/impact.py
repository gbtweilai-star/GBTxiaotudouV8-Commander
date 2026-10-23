# -*- coding: utf-8 -*-
"""impact.py —— 影响面检查的**零引号**入口（主人专用，避免 PowerShell 吃掉 JSON 引号）。

为什么要有这一件（2026-10-19 主人当场撞到）：
  `five-dim.py cap impact_check '{"op":"impact","target":"..."}'` 这行在 PowerShell 里
  内层双引号会被吃掉（`{op:impact,target:...}`）⇒ 报「payload 不是合法 JSON」。
  虽然 `--stdin` 管道写法是对的，但**主人不该为了查一个文件被引号折腾**。
  所以这里给一条不带 JSON、不带引号的写法：

      py -3.14 tools/codex-scripts/impact.py gbt_allinone/api.py
      py -3.14 tools/codex-scripts/impact.py code:gbt_allinone/api.py
      py -3.14 tools/codex-scripts/impact.py --top 8          # 最危险的 8 件
      py -3.14 tools/codex-scripts/impact.py --status         # 图有多大/通不通

仍然**走唯一门** `gbt_allinone.run_task`（授权/审计/钢印都在门上）；
本件只是把"人话参数"翻译成 payload，不绕门、不直接调模块函数。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

USAGE = """影响面检查（零引号入口）
  py -3.14 tools/codex-scripts/impact.py <目标>            # 影响面 + 1 跳必验清单
  py -3.14 tools/codex-scripts/impact.py <目标> --depth 1  # 只看 1 跳
  py -3.14 tools/codex-scripts/impact.py --top 8           # 最危险的 8 件
  py -3.14 tools/codex-scripts/impact.py --status          # 图的规模/连通性

目标可以写：仓内路径（gbt_allinone/api.py · holo_pet_w3/omni-arm/index.html）
           或带前缀的节点名（code:… / page:… / cap:tentacle_arm）
"""


def _run(kind: str, payload: dict) -> dict:
    from gbt_allinone import api as _api
    env = _api.run_task(kind, payload)
    body = env
    for _ in range(6):                      # 剥信封（与 impact-monitor-tick 同口径）
        if not isinstance(body, dict):
            break
        wrapper = any(k in body for k in ("gate", "gbt_stamp", "ok_source", "kind", "stamp"))
        if wrapper and isinstance(body.get("result"), dict):
            body = body["result"]
            continue
        break
    return body if isinstance(body, dict) else {"ok": False, "error": "bad_envelope"}


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if args else 2

    if "--status" in args:
        out = _run("impact_check", {"op": "status"})
        if out.get("ok"):
            print("图：%d 节点 / %d 有向边 / 连通分量 %d（最大分量 %s%%）"
                  % (out["nodes"], out["edges_directed"], out["components"],
                     out["largest_share"]))
            print("构建于 %s · 文件 %s" % (out["built_at"], out["graph"]))
        else:
            print("读不到图：%s · %s" % (out.get("error"), out.get("why")))
            return 1
        return 0

    if "--top" in args:
        i = args.index("--top")
        n = 8
        if i + 1 < len(args):
            try:
                n = int(args[i + 1])
            except ValueError:
                print("--top 后面要跟数字")
                return 2
        out = _run("impact_check", {"op": "risky", "n": n})
        if not out.get("ok"):
            print("失败：%s · %s" % (out.get("error"), out.get("why")))
            return 1
        print("=== 真实依赖最多（强边）的 %d 件 ===" % n)
        for r in out.get("top", []):
            print("  强边 %4d（全边 %5d）  %-56s 其中文件 %d / 能力位 %d"
                  % (r.get("strong", 0), r["total"], r["node"], r["files"], r["caps"]))
        print("\n⚠️ %s" % out.get("caveat", ""))
        return 0

    target = None
    for a in args:
        if not a.startswith("--"):
            target = a
            break
    if not target:
        print(USAGE)
        return 2
    depth = 2
    if "--depth" in args:
        i = args.index("--depth")
        if i + 1 < len(args):
            try:
                depth = int(args[i + 1])
            except ValueError:
                print("--depth 后面要跟数字")
                return 2

    out = _run("impact_check", {"op": "impact", "target": target, "depth": depth})
    if not out.get("ok"):
        print("🔴 %s：%s" % (out.get("error"), out.get("why")))
        if out.get("hint"):
            print("   %s" % out["hint"])
        return 1
    print("目标 %s ｜ %d 跳 ｜ 影响 %d 个节点" % ("、".join(out["targets"]), out["depth"],
                                                out["impact_nodes"]))
    print("构成：" + " · ".join("%s %d" % (k, v) for k, v in out["composition"].items()))
    print("\n=== 1 跳邻居（改完必须逐一验证，共 %d）===" % out["must_verify_count"])
    for x in out["must_verify_1hop"][:40]:
        print("  " + x)
    if out["must_verify_count"] > 40:
        print("  … 还有 %d 个（要全量：'{\"op\":\"impact\",\"target\":\"%s\"}' | "
              "py -3.14 tools/codex-scripts/five-dim.py cap impact_check --stdin --full）"
              % (out["must_verify_count"] - 40, target))
    if out.get("missing_targets"):
        print("\n⚠️ 不在图里的目标（前缀可能拼错）：%s" % "、".join(out["missing_targets"]))
    print("\n%s" % out.get("verdict", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
