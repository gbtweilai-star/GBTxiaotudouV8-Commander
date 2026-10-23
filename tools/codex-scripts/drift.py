# -*- coding: utf-8 -*-
"""drift.py —— 全项目变化监控的**零引号**入口（主人专用）。

    py -3.14 tools/codex-scripts/drift.py            # 基线在哪、多旧、多少件
    py -3.14 tools/codex-scripts/drift.py check      # 变了什么（全仓 stat 一遍，约 90 秒）
    py -3.14 tools/codex-scripts/drift.py check gbt_allinone/   # 只看某个目录
    py -3.14 tools/codex-scripts/drift.py freeze     # 冻结新基线（要 filesystem_write 票）

仍走唯一门 `gbt_allinone.run_task`；本件只把"人话参数"翻译成 payload。
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

USAGE = """全项目变化监控（零引号入口）
  py -3.14 tools/codex-scripts/drift.py            基线状态（快）
  py -3.14 tools/codex-scripts/drift.py check      变了什么（全仓 stat，约 90 秒）
  py -3.14 tools/codex-scripts/drift.py check <前缀>  只看某个目录/前缀
  py -3.14 tools/codex-scripts/drift.py freeze     把现状冻结成新基线（要 filesystem_write 票）
"""


def _run(payload: dict) -> dict:
    from gbt_allinone import api as _api
    env = _api.run_task("project_drift", payload)
    body = env
    for _ in range(6):
        if not isinstance(body, dict):
            break
        wrapper = any(k in body for k in ("gate", "gbt_stamp", "ok_source", "kind", "stamp"))
        if wrapper and isinstance(body.get("result"), dict):
            body = body["result"]
            continue
        break
    return body if isinstance(body, dict) else {"ok": False, "error": "bad_envelope"}


def _show_status(out: dict) -> int:
    if not out.get("ok"):
        print("失败：%s · %s" % (out.get("error"), out.get("why")))
        return 1
    if not out.get("baseline"):
        print("还没有基线 —— 这**不等于**『项目没变』，只是还看不见。")
        print("建基线：py -3.14 tools/codex-scripts/drift.py freeze")
        return 0
    age = out.get("age_s")
    print("基线 %s · 覆盖 %d 件 · %s" % (out["at"], out["files"],
                                        ("%.1f 小时前" % (age / 3600)) if age is not None else "年龄未知"))
    print("来源 %s · 文件 %s" % (out.get("source"), out.get("baseline")))
    if out.get("stale"):
        print("⚠️ 基线已过期（>24h）—— 结论必须带这个年龄，不许当「刚刚的事实」")
    return 0


def _show_drift(out: dict) -> int:
    if not out.get("ok"):
        print("失败：%s · %s" % (out.get("error"), out.get("why")))
        if out.get("how"):
            print("   %s" % out["how"])
        return 1
    print("基线 %s（%s）｜ 现在 %d 件 ｜ 扫描 %.1f s"
          % (out.get("baseline_at"),
             ("%.1f 小时前" % (out["baseline_age_s"] / 3600)) if out.get("baseline_age_s") else "年龄未知",
             out.get("scanned_now", 0), out.get("walk_s", 0)))
    print(out.get("verdict"))
    print("真哈希核过 %d 件 · 预算外未验 %d 件 · 旧差异（早于基线）%d 件"
          % (out.get("hash_checked", 0), out.get("hash_skipped", 0),
             out.get("predates_baseline_count", 0)))
    for label, key in (("新增", "added"), ("改动", "modified"), ("删除", "deleted"),
                       ("仅碰时间", "touched_only"), ("旧差异", "predates_baseline")):
        rows = out.get(key) or []
        if not rows:
            continue
        print("\n── %s（%d）──" % (label, out.get("%s_count" % key, len(rows))))
        for r in rows[:15]:
            extra = ""
            if "bytes_before" in r and "bytes_after" in r:
                extra = "  %d→%d B" % (r["bytes_before"], r["bytes_after"])
            print("   %s%s" % (r["path"], extra))
            if r.get("note"):
                print("      · %s" % r["note"])
    flags = out.get("flags") or []
    if flags:
        print("\n🔴 异常 %d 条：" % len(flags))
        for f in flags[:15]:
            print("   [%s] %s —— %s" % (f.get("级别"), f.get("为什么"), f.get("path")))
    else:
        print("\n✅ 未命中五条异常判据")
    if out.get("baseline_stale"):
        print("⚠️ 基线过期 —— 上面这些差异的时间边界不可信，先 freeze")
    return 0


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return _show_status(_run({"op": "status"}))
    if args[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if args[0] in ("check", "drift"):
        payload = {"op": "drift", "top": 15}
        if len(args) > 1 and not args[1].startswith("-"):
            payload["scope"] = args[1]
        return _show_drift(_run(payload))
    if args[0] in ("freeze", "baseline"):
        out = _run({"op": "baseline"})
        if out.get("ok"):
            print("已冻结新基线：%s · %d 件 · 来源 %s"
                  % (out.get("path"), out.get("files", 0), out.get("source")))
            return 0
        print("没能冻结：%s" % (out.get("why") or out.get("error")))
        if out.get("how_to_grant"):
            print("   %s" % out["how_to_grant"])
        return 1
    print(USAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
