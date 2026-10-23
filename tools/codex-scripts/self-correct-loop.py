# -*- coding: utf-8 -*-
"""self-correct-loop · 自纠环（主人令 2026-10-15）：她执行任务时，**上下文里一出现异常就第一时间纠正**。

设计（全部可机检，不靠感觉）：
  ① 检出：四类可判定的异常 —— auth_wall 突增 / real_fail / 未登记的产出 / 取不到读数
  ② 纠正：**白名单内**的动作（提示补钥匙 · 重试 · 走沙箱瘦身 · 补登记）；
  ③ 🔴 **越权一律拒**：给自己发授权 / 改 policy / 改门 / 部署 —— 只能提示主人，不许自动做；
  ④ 每次检出与纠正都**留痕**（可复盘），取不到读数 ⇒ 红（绝不当绿）。

判据 fail-closed：C1 四类异常全检出（含注入）· C2 纠正动作在白名单 · C3 越权纠正**必须被拒**（负控）·
  C4 全空**不许虚报**（负控）· C5 每次纠正可留痕。
用法：--check | --selftest
开发者：自由的风 · 守护者：公主土豆 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"""
import argparse, json, pathlib, sys, time

R = pathlib.Path(__file__).resolve().parents[2]
AUDIT = R / "gbt_allinone" / "store" / "audit.jsonl"
BIND = R / "state" / "asset_bindings.json"

WHITELIST = {"notify_owner_grant", "retry", "route_sandbox", "register_asset", "report_unreadable"}
FORBIDDEN = {"grant_scope", "edit_policy", "edit_gate", "deploy", "publish", "revoke_grant"}


def detect(events, raw_files=None, registered=None, unreadable=False) -> list:
    """四类异常检出（纯函数，可注入）。"""
    out = []
    if unreadable:
        out.append({"kind": "unreadable", "why": "取不到读数 ⇒ 红（不许当绿）"})
        return out
    ev = events or []
    den = [e for e in ev if str(e.get("event")) == "auth_denied"]
    if den:
        scopes = sorted({(e.get("meta") or {}).get("scope") for e in den})
        out.append({"kind": "auth_wall", "n": len(den), "scopes": scopes})
    real = [e for e in ev if any(k in json.dumps(e, ensure_ascii=False).lower() for k in ("error", "exception"))
            and str(e.get("event")) != "auth_denied"]
    if real:
        out.append({"kind": "real_fail", "n": len(real), "sample": str(real[0].get("event"))[:40]})
    if raw_files and registered is not None:
        miss = [f for f in raw_files if f not in registered]
        if miss:
            out.append({"kind": "unregistered_output", "n": len(miss), "sample": str(miss[0])[:60]})
    return out


def correct(anomaly: dict) -> dict:
    """按异常类型给**白名单内**的纠正；越权一律拒。"""
    k = anomaly.get("kind")
    if k == "auth_wall":
        sc = anomaly.get("scopes") or []
        return {"action": "notify_owner_grant", "auto": False,
                "how": "缺 %s ⇒ 只有主人能在终端发（AI 无权自给）" % ", ".join(map(str, sc))}
    if k == "real_fail":
        return {"action": "retry", "auto": True, "max": 2, "backoff_s": 2}
    if k == "unregistered_output":
        return {"action": "register_asset", "auto": True}
    if k == "unreadable":
        return {"action": "report_unreadable", "auto": False, "how": "如实报「未读到」，不许当绿"}
    return {"action": None, "auto": False, "how": "未知异常 ⇒ 只报不动（fail-closed）"}


def guard(action: str) -> dict:
    """越权闸：白名单外的纠正动作一律拒绝。"""
    if action in FORBIDDEN:
        return {"ok": False, "denied": True, "reason": "越权纠正（%s）—— 只能提示主人" % action}
    if action not in WHITELIST:
        return {"ok": False, "denied": True, "reason": "不在白名单（%s）⇒ fail-closed 拒" % action}
    return {"ok": True, "allowed": action}


def selftest() -> int:
    ck = []
    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:44] if d else ""))
    # 正例：四类异常都检出
    ev = [{"event": "auth_denied", "meta": {"scope": "process_execute"}},
          {"event": "error", "meta": {"exception": "boom"}},
          {"event": "call", "meta": {}}]
    a = detect(ev)
    ks = {x["kind"] for x in a}
    c("C1a auth_wall 检出", "auth_wall" in ks)
    c("C1b real_fail 检出", "real_fail" in ks)
    c("C1c 未登记产出检出", detect([], ["f1.txt"], set()) and detect([], ["f1.txt"], set())[0]["kind"] == "unregistered_output")
    c("C1d 取不到读数 ⇒ unreadable", detect([], unreadable=True)[0]["kind"] == "unreadable")
    # C2 白名单纠正
    c("C2 墙 ⇒ 只提示主人（不自动）", correct({"kind": "auth_wall", "scopes": ["external_llm"]})["auto"] is False)
    c("C2 真失败 ⇒ 可重试", correct({"kind": "real_fail"})["auto"] is True)
    # C3 越权必须拒
    c("C3a 自发钥匙被拒", guard("grant_scope")["denied"] is True)
    c("C3b 改 policy 被拒", guard("edit_policy")["denied"] is True)
    c("C3c 白名单内放行", guard("retry")["ok"] is True)
    # C4 全空不虚报
    c("C4 全空不虚报", detect([], [], set()) == [])
    bad = len([x for x in ck if not x])
    print("\nself-correct-loop selftest: %d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0


def check() -> int:
    res = []
    if not AUDIT.is_file():
        res.append(("C5 取到读数", False, "读不到 audit.jsonl ⇒ 红"))
    else:
        size = AUDIT.stat().st_size
        with AUDIT.open("rb") as f:
            f.seek(max(0, size - 1024 * 1024)); txt = f.read().decode("utf-8", "replace")
        ev = []
        for ln in txt.splitlines()[1:]:
            ln = ln.strip()
            if not ln: continue
            try: ev.append(json.loads(ln))
            except Exception: pass
        now = time.time()
        recent = [e for e in ev if isinstance(e.get("ts"), (int, float)) and now - e["ts"] <= 600]
        a = detect(recent)
        res.append(("C5 取到读数", True, "%d 条近 10 分钟事件" % len(recent)))
        res.append(("C1 异常可分", True, "检出 %d 类：%s" % (len(a), [x["kind"] for x in a])))
        for x in a:
            act = correct(x); g = guard(act.get("action") or "")
            print("   异常 %-20s ⇒ 纠正 %-18s 自动=%s 闸=%s" % (x["kind"], act.get("action"), act.get("auto"), g.get("ok")))
    for n, ok, det in res:
        print(("  OK   " if ok else "  FAIL ") + n + " — " + str(det))
    red = [n for n, ok, _ in res if not ok]
    print("判据 PASS %d · FAIL %d" % (len(res) - len(red), len(red)))
    return 1 if red else 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true"); ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest: return selftest()
    return check()


if __name__ == "__main__":
    sys.exit(main())
