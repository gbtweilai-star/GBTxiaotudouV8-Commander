#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""probe-safefalse · 把 `safe=False` 那 8 位从「静态核」推到「已验」

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 背景
账上 `safe=False·静态核` 有 8 位（§一百一十）—— 它们**只被静态读过源码，从没真调过**。
其中 `edit_pipeline` 已在 §一百一十六 推到「已验」（22/22 测试 + 真拼片 2.800s 对账 0.000）。
**本工具推剩下 7 位。**

## 🔴 纪律（与 `probe_needparam.py` 同一套）
1. **表外一律拒**（fail-closed）：只跑下面 `DECLARED` 里逐条**声明过**的 payload；
2. **每条只准走只读 op**（理由写在表里）：`status` / `formats` / `tracks` /
   `loudness_targets` / `platforms` / `check` / `list`，以及 `code_patch` 的 **`dry_run`（默认只算不写）**；
3. **明确不探**：`git_write`（会改版本库）· `media_run`（执行整链）—— **宁可账上留缺口**；
4. **不绕门**：一律经 `five-dim.py cap`（唯一门 → `run_task`）。

用法：
  probe-safefalse.py table   # 只看声明的表
  probe-safefalse.py run     # 真探（表内）
  probe-safefalse.py selftest
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIVE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
OWN_MP4 = "outputs/shorts-stitch/shorts.mp4"        # 我自己产的真片段（读它不需要新造件）

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DECLARED = {
    "media_publish": [
        ({"op": "status"}, "`status` 分支：只报现状", "只读"),
        ({"op": "platforms", "kind": "short_video"},
         "`platforms` 分支：读平台口径表（**不是发布**；`READ_OPS=(\"status\",\"platforms\")`）", "只读"),
    ],
    "media_license": [
        ({"op": "status"}, "`status` 分支：只报账本现状", "只读"),
        ({"op": "list"}, "`list` 分支：列出已登记素材", "只读"),
    ],
    "audio_extract": [
        ({"op": "formats"}, "`formats` 分支：读支持的音频格式表", "只读"),
        ({"op": "tracks", "path": OWN_MP4}, "`tracks` 分支：**读**该片的音轨（不抽件）", "只读"),
    ],
    "audio_mix": [
        ({"op": "loudness_targets"}, "`loudness_targets` 分支：读响度目标表", "只读"),
        ({"op": "status"}, "`status` 分支：只报现状", "只读"),
    ],
    "code_patch": [
        ({"op": "dry_run", "path": "tools/codex-scripts/plugin-mesh.py",
          "find": "全互通", "replace": "全互通(试)"},
         "**`dry_run` 是三原语默认**（原话：dry_run（**默认，只算不写**））", "只算不写"),
    ],
}
# 🔴 **明确不探**：写在这里是为了让"为什么没探"也上账，而不是悄悄跳过
REFUSED = {
    "git_write": "会改版本库（`git add`/`commit`）—— **不探，宁可账上留缺口**",
    "media_run": "一次调用把整条链走到尾（每步落真件）—— **不探**",
    "edit_pipeline": "**已在 §一百一十六 推出「已验」**（22/22 测试 + 真拼片），不需再探",
}


def _door(kind: str, payload: dict) -> dict:
    r = subprocess.run([sys.executable, str(FIVE), "cap", kind,
                        json.dumps(payload, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600, cwd=str(ROOT))
    out = (r.stdout or "") + (r.stderr or "")
    dec = json.JSONDecoder()
    env = None
    for i, ch in enumerate(out):
        if ch != "{":
            continue
        try:
            o, _ = dec.raw_decode(out[i:])
        except Exception:
            continue
        if isinstance(o, dict) and ({"result", "denied", "status"} & set(o)):
            env = o
            break
    if env is None:
        return {"ok": None, "为什么": "取不到门信封", "原文尾": out[-200:]}
    if env.get("denied") is True:
        return {"ok": False, "被门拒": env.get("missing_scopes"),
                "为什么": str(env.get("message"))[:120]}
    res = env.get("result") if isinstance(env.get("result"), dict) else env
    return res


def classify(res: dict) -> str:
    if not isinstance(res, dict):
        return "❓ 判不了"
    if res.get("被门拒"):
        return "🔒 被门拒·缺授权"
    # 🔴 门的「**结果收窄**」信封（大结果只报形状）⇒ **真值在 `preview.ok` 里**。
    #    第一版没看它 ⇒ 3 个**其实成功**的只读 op 被判「判不了」。
    if "_摘要" in res:
        pv = res.get("preview") if isinstance(res.get("preview"), dict) else {}
        if pv.get("ok") is True:
            return "✅ 通（真调成功 · 结果被门收窄）"
        if pv.get("ok") is False:
            return "⛔ 痛（收窄后的 ok=false）"
        return "❓ 判不了（收窄了但 preview 里没有 ok）"
    if res.get("ok") is True:
        return "✅ 通（真调成功）"
    st = str(res.get("status") or "")
    if st.startswith("needs_"):
        return "🟠 环境未就绪"
    # 🔴 **模块自己的安全自检驳回**（例：`code_patch` 的 find 有歧义 ⇒ 「拒绝替你挑一个」）
    #    ⇒ 这是**安全行为**、且证明 **op 真可达**，**不是痛**。
    rc = str(res.get("reason_code") or "")
    msg = str(res.get("message") or res.get("error") or "")
    if rc in ("ambiguous", "too_short") or "拒绝" in msg:
        return "🟡 模块自检驳回（**安全行为** · op 真可达）"
    if res.get("ok") is False:
        return "⛔ 痛（报错但不是缺参/自检）"
    return "❓ 判不了"


def probe_all() -> dict:
    rows, tally = {}, {}
    for kind, items in DECLARED.items():
        rows[kind] = []
        for payload, why, kind_of in items:
            t0 = time.time()
            res = _door(kind, payload)
            v = classify(res)
            tally[v] = tally.get(v, 0) + 1
            rows[kind].append({
                "payload": payload, "为什么只读安全": why, "性质": kind_of,
                "判决": v, "秒": round(time.time() - t0, 1),
                "返回的键": sorted(res)[:12] if isinstance(res, dict) else None,
                # 🔴 **原始返回必须可见**：分类器认不出时不许静默 —— 把原文尾巴带上
                "原始返回": (json.dumps(res, ensure_ascii=False)[:260]
                         if isinstance(res, dict) else str(res)[:200]),
                "证据": ({"被门拒": res.get("被门拒"), "message": res.get("message"),
                        "status": res.get("status")} if isinstance(res, dict) else None),
            })
    return {"逐位": rows, "合计": tally,
            "明确不探（**为什么也上账**）": REFUSED,
            "读法": "「✅ 通」= 只读 op 真调成功 ⇒ 该位从「静态核」升为「已验」；"
            "「🔒 被门拒」= 如实报缺授权（**不改判成「坏」**）"}


# 🔴 **拒绝面探针**：`git_write` 会改版本库 ⇒ **绝不真写**。
#    但"**写面不点名路径必须拒**"本身就是它最关键的安全判据（源码原话：
#    「写面**必须点名路径** —— 本仓脏行可能上万」）⇒ **不给路径就永远不可能写**。
#    ⇒ 验的是**拒绝面**，不是写路径 —— **两个状态分开写**。
REFUSAL = {
    "git_write": [
        ({"op": "stage"}, "**不点名路径必须拒**（源码：写面必须点名路径）"),
        ({"op": "commit"}, "**commit 也必须点名路径**（pathspec-limited）"),
        ({"op": "__bogus__"}, "**不认识的 op 不许静默成功**"),
    ],
}


def classify_refusal(res) -> str:
    """拒绝面判决：**拒**才算过。"""
    if not isinstance(res, dict):
        return "❓ 判不了"
    if res.get("被门拒"):
        return "🔒 被门拒·缺授权（**门先挡** = 也是拒绝面成立）"
    if res.get("ok") is True:
        return "🔴 **竟然放行了**（写面没点名路径却没拒 —— 这是缺陷）"
    rc = str(res.get("reason_code") or res.get("error_class") or "")
    msg = str(res.get("message") or res.get("error") or "")
    if rc in ("paths_required", "bad_limit", "user_error", "unknown_op") or msg:
        return "✅ 拒绝了（拒绝面成立）"
    return "❓ 判不了"


def probe_refusal() -> dict:
    rows = {}
    for kind, items in REFUSAL.items():
        rows[kind] = []
        for payload, why in items:
            res = _door(kind, payload)
            rows[kind].append({"payload": payload, "判据": why,
                               "判决": classify_refusal(res),
                               "原始返回": (json.dumps(res, ensure_ascii=False)[:200]
                                        if isinstance(res, dict) else str(res)[:160])})
    return {"拒绝面逐条": rows,
            "口径": "**只验拒绝面**（不给路径 ⇒ 永不可能写）· 写路径**仍未验** —— 两个状态分开写"}


def cmd_table(a) -> int:
    print(json.dumps({"声明表": {k: [p for p, _, _ in v] for k, v in DECLARED.items()},
                      "明确不探": REFUSED,
                      "纪律": "表外拒 · 每条只准只读 op · 不绕门"}, ensure_ascii=False, indent=1))
    return 0


def cmd_run(a) -> int:
    r = probe_all()
    r.update(probe_refusal())
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    flat = [(k, p, kind_of) for k, v in DECLARED.items() for p, _, kind_of in v]
    # ① **只准只读 op**：通用白名单 **或** `code_patch` 专属的 `dry_run`
    #    🔴 第一版只查通用白名单 ⇒ `dry_run` 被误判越界。**判据要写成精确表达式**：
    #    「只读 op ∪ (code_patch ∧ dry_run)」——`dry_run` 不许给别的位置用。
    READONLY_OPS = {"status", "formats", "tracks", "loudness_targets", "platforms",
                    "check", "list", "qc", "schema", "probe"}
    bad_ops = [(k, p) for k, p, _ in flat
               if not (str(p.get("op")) in READONLY_OPS
                       or (k == "code_patch" and p.get("op") == "dry_run"))]
    ck("**每条声明的 op 都是只读 op**（通用白名单 ∪ code_patch 的 dry_run）",
       not bad_ops, "越界: %s" % (bad_ops or "无"))
    # ② `code_patch` 只准 dry_run（它的 apply 会真写盘）
    ck("**`code_patch` 只声明 dry_run**（apply 会真写盘）",
       all(p.get("op") == "dry_run" for p in
           [x[1] for x in flat if x[0] == "code_patch"]),
       "已声明: %s" % [x[1].get("op") for x in flat if x[0] == "code_patch"])
    # ③ **会改版本库 / 执行整链的必须明确写在"不探"里**（不许悄悄跳过）
    ck("**`git_write` / `media_run` 明确列为不探**",
       "git_write" in REFUSED and "media_run" in REFUSED and all(REFUSED.values()),
       "不探 %d 条（每条都有理由）" % len(REFUSED))
    # ④ 负控：**表外一律拒** —— 拿一个没声明的能力位问，必须不出门
    ck("**负控：表外的能力位不出门**", "edit_pipeline" not in DECLARED,
       "`edit_pipeline` 不在表里（已验过，不需再探）")
    # ⑤ 判据**随数据变**：分类器对三种信封给出三种判决
    ck("分类器·ok:true ⇒ 通", classify({"ok": True}).startswith("✅"), "已验")
    ck("分类器·被门拒 ⇒ 缺授权", classify({"被门拒": ["x"]}).startswith("🔒"), "已验")
    ck("分类器·needs_* ⇒ 环境未就绪", classify({"ok": False, "status": "needs_x"}).startswith("🟠"),
       "已验")
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="把 safe=False 那 8 位从静态核推到已验（只读 op）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("table").set_defaults(func=cmd_table)
    sub.add_parser("run").set_defaults(func=cmd_run)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
