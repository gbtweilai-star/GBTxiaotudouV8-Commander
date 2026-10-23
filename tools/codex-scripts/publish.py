#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模块 08 · publish（发布门卫）—— 默认拒，且**不是发布器**

## 先把身份说清楚（免得被读成"已经能发布了"）
本模块是**发布门卫**，**不是发布器**。真发布必须走**唯一门**
`five-dim.py cap <能力位>` → `run_task`，且要**主人授权** `deploy_publish` + **显式声明落点**。
门卫只干两件事：**报授权现状** · **把不合规的发布请求挡在门外**。

## 三道闸（全部 fail-closed）
  ① **授权闸**：现读 `auth_gate_status` 的 `deploy_publish.grants_available`；**0 ⇒ 拒**。
     AI **无权发授权**（`ai_can_grant=False` 是现读事实，不是我谦虚）。
  ② **落点闸**：必须显式声明 `--room <房间名>` 或 `--into-global-production`
     （本仓红线：不声明落点 = 直接拒绝，任何代码都别想溜进生产）。
  ③ **唯一门**：过前两闸后，**只打印**该走的那条 `run_task` 命令，**本模块不执行**。

## 🔴 为什么 ③ 不执行
执行 = 写生产/晋升 = **发布动作**，那是主人的点头范围，不是我的。
本模块的价值在于：让"**没授权就发不出去**"从一句话变成**跑得出来的 rc**。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIVE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
PY = [sys.executable]
SCOPE = "deploy_publish"


def auth_read(inject: bool = False) -> dict:
    """真读授权现状。`GBT_FAKE_DP_GRANTS` **只给自检注入用**，且会在读数里标出来。"""
    fake = os.environ.get("GBT_FAKE_DP_GRANTS")
    if inject and fake is not None:
        try:
            n = int(fake)
        except Exception:
            return {"ok": False, "错误": "注入值 %r 不是整数 ⇒ 按读不到处理" % fake,
                    "deploy_publish_grants": None, "注入值": True}
        return {"ok": True, "deploy_publish_grants": n, "ai_can_grant": False,
                "注入值": True, "来源": "GBT_FAKE_DP_GRANTS（**自检注入，不是真读数**）"}
    r = subprocess.run(PY + [str(FIVE), "cap", "auth_gate_status", "--full"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT), timeout=180)
    if r.returncode != 0:
        return {"ok": False, "错误": "auth_gate_status 调用失败 rc=%d" % r.returncode,
                "deploy_publish_grants": None,
                "说明": "**读不到 ⇒ 按 0 处理（fail-closed）**"}
    txt = (r.stdout or "") + (r.stderr or "")
    i = txt.find("{")
    if i < 0:
        return {"ok": False, "错误": "返回里没有 JSON", "deploy_publish_grants": None}
    try:
        d = json.loads(txt[i:])
    except Exception as e:
        return {"ok": False, "错误": "JSON 解析失败：%s" % e, "deploy_publish_grants": None}
    res = d.get("result") or {}
    sc = (res.get("scopes") or {}).get(SCOPE) or {}
    return {"ok": True, "deploy_publish_grants": sc.get("grants_available"),
            "desc": sc.get("desc"), "ai_can_grant": res.get("ai_can_grant"),
            "grant_sources": res.get("grant_sources"),
            "有授权的其他作用域": [k for k, v in (res.get("scopes") or {}).items()
                          if isinstance(v, dict) and v.get("grants_available")],
            "来源": "five-dim.py cap auth_gate_status --full（现读）"}


def _gate_auth(inject: bool) -> tuple[bool, dict]:
    a = auth_read(inject=inject)
    n = a.get("deploy_publish_grants")
    if not a.get("ok") or not n:
        return False, a
    return True, a


def cmd_check(a) -> int:
    auth = auth_read(inject=a.inject)
    n = auth.get("deploy_publish_grants")
    print(json.dumps({
        "授权现状": auth,
        "判决": "**门是关的**：没有 deploy_publish 授权 ⇒ 任何发布请求都拒" if not n else
        "门是开的：有 %s 次授权（一次性消耗，用完即关）" % n,
        "AI 能不能自己发授权": "**不能**（ai_can_grant=%s）" % auth.get("ai_can_grant"),
        "主人怎么开": "python -m gbt_allinone auth grant --scope deploy_publish --ttl 600"
        "（或主人手写 store/auth_grants.jsonl）",
        "本模块是什么": "**发布门卫，不是发布器**；真发布走唯一门 run_task",
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_send(a) -> int:
    # 闸① 授权
    ok1, auth = _gate_auth(inject=a.inject)
    if not ok1:
        print(json.dumps({
            "ok": False, "拒单": "**授权闸拦住**：没有 deploy_publish 授权（fail-closed）",
            "现读": auth,
            "主人怎么开": "python -m gbt_allinone auth grant --scope deploy_publish --ttl 600",
            "我不会做什么": "不绕门、不自己发授权、不改 security/policy.py",
        }, ensure_ascii=False, indent=1))
        return 3
    # 闸② 落点
    if not a.room and not a.into_global_production:
        print(json.dumps({
            "ok": False, "拒单": "**落点闸拦住**：必须显式声明落点（本仓红线）",
            "两条路": {"只写房间（生产分毫不动）": '--room "<房间名>"',
                    "写全局生产（必须人工授权）": "--into-global-production"},
        }, ensure_ascii=False, indent=1))
        return 4
    # 闸③ 唯一门：只打印，不执行
    payload = {"op": "one_key_deploy", "job_id": a.job_id}
    if a.room:
        payload["room"] = a.room
    else:
        payload["into_global_production"] = True
    cmd = "py -3.14 tools/codex-scripts/five-dim.py cap one_key_deploy '%s'" % json.dumps(
        payload, ensure_ascii=False)
    print(json.dumps({
        "ok": True, "闸①授权": "✅ 过", "闸②落点": "✅ 过", "闸③唯一门": "**只给命令，本模块不执行**",
        "该跑的命令": cmd,
        "为什么不在模块里执行": "执行 = 写生产/晋升 = **发布动作**，是主人的点头范围",
        "边界": "本模块是发布门卫，不是发布器",
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_selftest(a) -> int:
    """真身自检：**1 正控 + 4 负控**，全部走同一条代码路径（靠注入改"授权读数"这一格）。"""
    lines, bad = [], 0

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    keep = os.environ.get("GBT_FAKE_DP_GRANTS")

    # ① 真读（不注入）：报的是真授权现状，且结构健全
    real = auth_read(inject=False)
    ck("正控·真读授权现状（不注入）",
       bool(real.get("ok")) and "deploy_publish_grants" in real,
       "deploy_publish grants=%s · ai_can_grant=%s · 来源=%s"
       % (real.get("deploy_publish_grants"), real.get("ai_can_grant"), real.get("来源")))

    # ② 负控：没有授权 ⇒ `send` 必须拒（rc=3）
    os.environ["GBT_FAKE_DP_GRANTS"] = "0"

    class S:
        job_id, room, into_global_production, inject = "demo-005", "", False, True
    rc0 = cmd_send(S())
    ck("负控①·无授权 ⇒ 发布被拒", rc0 == 3, "rc=%d（期望 3）" % rc0)

    # ③ 负控：有授权但**没声明落点** ⇒ 必须拒（rc=4）
    os.environ["GBT_FAKE_DP_GRANTS"] = "1"
    rc1 = cmd_send(S())
    ck("负控②·有授权但没声明落点 ⇒ 拒", rc1 == 4, "rc=%d（期望 4）" % rc1)

    # ④ 负控：注入值不是数字 ⇒ 按读不到处理 ⇒ 拒
    os.environ["GBT_FAKE_DP_GRANTS"] = "不是数字"
    rc2 = cmd_send(S())
    ck("负控③·授权读数不可用 ⇒ 拒（fail-closed）", rc2 == 3, "rc=%d（期望 3）" % rc2)

    # ⑤ 正控：有授权 + 声明落点 ⇒ 过两闸，**只给命令不执行**（rc=0）
    os.environ["GBT_FAKE_DP_GRANTS"] = "1"

    class S2:
        job_id, room, into_global_production, inject = "demo-005", "排练房间", False, True
    rc3 = cmd_send(S2())
    ck("正控②·有授权+声明落点 ⇒ 过两闸（只给唯一门命令）", rc3 == 0, "rc=%d（期望 0）" % rc3)

    if keep is None:
        os.environ.pop("GBT_FAKE_DP_GRANTS", None)
    else:
        os.environ["GBT_FAKE_DP_GRANTS"] = keep
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines,
                      "口径": "注入只改『授权读数』这一格，闸的代码路径完全一样；"
                      "注入值在读数里会明确标出是注入"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="模块 08 · publish（发布门卫，不是发布器）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--inject", action="store_true", help="自检用：允许读注入值")
    c.set_defaults(func=cmd_check)
    s = sub.add_parser("send")
    s.add_argument("job_id")
    s.add_argument("--room", default="")
    s.add_argument("--into-global-production", action="store_true")
    s.add_argument("--inject", action="store_true", help="自检用：允许读注入值")
    s.set_defaults(func=cmd_send)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
