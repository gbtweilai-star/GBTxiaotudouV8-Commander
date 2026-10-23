# -*- coding: utf-8 -*-
"""R-H295 追问：api.py 里 14 条路由的默认 op 不是 status。

要回答的是：**空参调用时，它们究竟在"读数"还是在"干活"？**
分别归类：
  A 只读读数   ok=True 且 readonly=True       → 正确
  B 只读列举   ok=True 但无 readonly 标记      → 基本正确
  C 如实拒绝   报缺参数/门不存在 且 ok 非 True  → 可接受（诚实）
  D 真去干活   ok=True 且产生动作/副作用        → 缺陷（该补 status）
  E 抛异常                                     → 缺陷
"""
import json
import sys
import traceback
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))

from gbt_allinone import api  # noqa: E402

TARGETS = [
    "meta_cognition", "coverage_auditor", "tentacle_cognition", "caps_called_audit",
    "scene_anchor", "hook_registry", "emotion_projection",
    "vision", "prompt_bridge", "voice", "voice_orchestra",
    "browser", "bluetooth", "bt_control",
]


def unwrap(res):
    """run_task 返回的是信封：{ok,status,kind,gbt_result:{result:{...}},gbt_stamp}。

    第一版探针直接读信封顶层，于是把 7 个 **内层 readonly=True** 的只读能力
    误判成「空参去干活」。判定必须下沉到内层 result。
    """
    if not isinstance(res, dict):
        return {}, None
    inner = res.get("gbt_result")
    if isinstance(inner, dict):
        r = inner.get("result")
        if isinstance(r, dict):
            return r, inner
    r = res.get("result")
    return (r if isinstance(r, dict) else {}), res


def classify(kind, res):
    if not isinstance(res, dict):
        return "E", "非 dict 返回：%r" % (type(res).__name__,)
    inner, env = unwrap(res)
    outer_ok = res.get("ok") is True
    if not outer_ok:
        return "C", "外层未通过（门/参数）：%s" % (res.get("error") or res.get("message") or "")[:60]
    if inner.get("readonly") is True:
        return "A", "只读读数"
    if inner.get("ok") is False:
        code = inner.get("reason_code") or inner.get("error") or inner.get("reason") or ""
        return "C", "如实拒绝（%s）" % str(code)[:40]
    if inner.get("ok") is True:
        # 只读列举：要么显式 readonly，要么返回的是清单类字段
        listish = any(k in inner for k in ("ops", "list", "items", "classes", "hooks",
                                           "catalogue", "matrix", "red_lines", "models"))
        if listish:
            return "B", "只读列举（无 readonly 标记）"
        return "D", "ok=True 且无 readonly 标记、非列举"
    return "B", "口径待看（inner 无 ok 字段）"


def main():
    rows = []
    for kind in TARGETS:
        try:
            res = api.run_task(kind, {}, safe=True, probe=True)
            cls, note = classify(kind, res)
            body = res if isinstance(res, dict) else {"_raw": repr(res)[:200]}
        except Exception as exc:  # noqa: BLE001
            cls, note = "E", "抛异常 %s: %s" % (type(exc).__name__, exc)
            body = {"_trace": traceback.format_exc()[-300:]}
        rows.append((kind, cls, note, body))

    print("=" * 92)
    print("空参真调 · 14 条「默认 op 不是 status」的路由（判定已下沉到内层 result）")
    print("=" * 92)
    bad = []
    for kind, cls, note, body in rows:
        flag = {"A": "✓", "B": "·", "C": "~", "D": "✗", "E": "✗"}[cls]
        inner, _env = unwrap(body)
        keys = ",".join(sorted(inner)[:9])
        print("%s [%s] %-22s %-26s inner_keys=%s" % (flag, cls, kind, note, keys))
        if cls in ("D", "E"):
            bad.append((kind, cls, note))
            print("      inner: %s" % json.dumps(inner, ensure_ascii=False, default=str)[:320])

    print("-" * 92)
    print("真缺陷（空参去干活 / 抛异常）：%d 条" % len(bad))
    for kind, cls, note in bad:
        print("   ✗ %-22s %s" % (kind, note))
    print("A 只读=%d  B 列举=%d  C 诚实拒绝=%d  D 干活=%d  E 异常=%d" % (
        sum(1 for r in rows if r[1] == "A"), sum(1 for r in rows if r[1] == "B"),
        sum(1 for r in rows if r[1] == "C"), sum(1 for r in rows if r[1] == "D"),
        sum(1 for r in rows if r[1] == "E")))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
