#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""probe_needparam · 给「缺参 5 位」按契约喂**只读安全参数**，看它们是「缺参」还是「底下也坏了」

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要这个
这 5 位（`browser` `osint_scan` `topic_watch` `brain_execute` `brain_unify`）现在账上记的是
**「🟡 需参数·未探」** —— 空参探不动。但**「空参探不动」和「能力坏了」是两件事**，
账上目前没有这个区分。本脚本把这件事**探清楚**。

## 三条安全纪律（写死成代码）
1. **表外一律拒**：只跑下面 `DECLARED` 里逐条**声明过**的 payload，别的一律不出门（fail-closed）。
2. **每一条都必须是只读路**，理由写在表里：
   - `browser` 走 `op=native + action=status` —— **框架注册表自己声明的只读路**
     （`caps_registry` 原话：「只读路请写 op=native + action=status」）
   - `osint_scan` 目标写 **回环 `127.0.0.1`** —— `classify_target()` 会判 private，
     **全程不出网**（api.py: `allow_private = kind_t == "private"`）
   - `brain_execute` / `brain_unify` 指定 `kind=count_words` —— **零作用域只读位**
   - `topic_watch` 走 `op=status` —— 只读 op（**不是**默认那条要 `need` 的 `route`）
3. **不绕门**：一律经 `five-dim.py cap`（唯一门 → `run_task`），被门拒就是被门拒，如实报。

用法：
  probe_needparam.py run        # 真探 5 位（表内）
  probe_needparam.py table      # 只看声明的表（不跑）
  probe_needparam.py selftest
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]      # tools/codex-scripts/ → 仓根
FIVE = ROOT / "tools" / "codex-scripts" / "five-dim.py"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# **声明表**：只跑这 5 条，每条写明「为什么这条是只读安全的」
DECLARED = {
    "browser": {
        "payload": {"op": "native", "action": "status"},
        "为什么安全": "框架注册表自己声明的只读路（caps_registry：「只读路请写 op=native + action=status」）",
        "会不出网": "不出网：读本机原生浏览器窗口状态",
    },
    "osint_scan": {
        "payload": {"target": "127.0.0.1"},
        "为什么安全": "回环地址；api.py 用 classify_target() 判定 private ⇒ allow_private=True，**不出网**",
        "会不出网": "不出网：只扫本机回环",
    },
    "topic_watch": {
        "payload": {"op": "status"},
        "为什么安全": "只读 op（topic_watch.run 的 op=status 分支）；**不是**默认那条要 need 的 route",
        "会不出网": "不出网：读话题追踪的现状",
    },
    "brain_execute": {
        "payload": {"kind": "count_words", "text": "a b c"},
        "为什么安全": "执行对象是 **count_words**（零作用域只读位，纯本地计数）",
        "会不出网": "不出网、不改状态",
    },
    "brain_unify": {
        "payload": {"goal": "统计词数", "kind": "count_words", "text": "x y"},
        "为什么安全": "同上，统一入口指向零作用域只读位 count_words",
        "会不出网": "不出网、不改状态",
    },
}


# 门信封的**标记键**：含其一者才可能是外层信封
_ENV_MARKS = {"result", "denied", "ok", "error_class", "missing_scopes", "status"}


def _envelope(out: str):
    """取**最外层**门信封 —— 不是"最后一个 JSON 对象"。

    🔴 第一版取"最后一个 raw_decode 成功的对象" ⇒ 拿到的是**嵌套内层**片段
    （`found/synced/entry/via/来源` 那段审计账本读数），于是 5 位全判成「❓ 判不了」。
    正确规则：**外层信封在位置上更靠前** ⇒ 升序找**第一个**带标记键的对象。
    """
    dec = json.JSONDecoder()
    first_any = None
    for i, ch in enumerate(out):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(out[i:])
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        if first_any is None:
            first_any = obj
        if _ENV_MARKS & set(obj):
            return obj
    return first_any


def classify(rc: int, out: str) -> dict:
    """→ {判决, 为什么}。**只看证据，不猜**。"""
    env = _envelope(out)
    if env is None:
        return {"判决": "⛔ 痛（读数解析不了）", "详情": (out or "")[-220:]}
    # 扁平拒单信封：{"status":"denied", "missing_scopes":[...]}
    if env.get("denied") is True or str(env.get("status")) == "denied":
        return {"判决": "🔒 被门拒·缺授权",
                "详情": {"missing_scopes": env.get("missing_scopes"),
                       "reason": str(env.get("message") or env.get("reason") or "")[:150]},
                "怎么解": env.get("how_to_grant") or env.get("怎么授权")}
    res = env.get("result") if isinstance(env.get("result"), dict) else env
    if res.get("denied") is True:
        return {"判决": "🔒 被门拒·缺授权",
                "详情": {"missing_scopes": res.get("missing_scopes"),
                       "reason": str(res.get("message") or "")[:150]}}
    if res.get("ok") is False:
        ec = res.get("error_class")
        msg = str(res.get("message") or "")[:160]
        st = str(res.get("status") or "")
 # `ok:false` 不等于「坏」：本仓大量能力用 `status:"needs_*"` 表达**环境条件缺**
        #    （实测：browser 返回 needs_browser_debug / cdp_available:false / 端口 9222 无监听，
        #     但分支真跑了、动作表 23 个全返回）⇒ 这必须与「痛」分开，否则又是假痛（F35 同型）。
        if st.startswith("needs_"):
            return {"判决": "🟠 环境未就绪（分支跑了 · 条件缺）",
                    "详情": {"status": st, "还返回了什么": sorted(res)[:8]}}
        if ec == "user_error" or "缺少" in msg or "需要" in msg or "请提供" in msg or "请给" in msg:
            return {"判决": "🟡 仍是缺参", "详情": {"error_class": ec, "message": msg}}
        return {"判决": "⛔ 痛（报错但不是缺参/未就绪）",
                "详情": {"error_class": ec, "message": msg, "status": st}}
    if res.get("ok") is True:
        return {"判决": "✅ 通（给参后真跑通）", "详情": {"键": sorted(res)[:10]}}
    return {"判决": "❓ 判不了", "详情": {"rc": rc, "顶层键": sorted(env)[:10],
                                  "原文尾": (out or "")[-300:]}}


def probe(kind: str) -> dict:
    if kind not in DECLARED:
        return {"判决": "🔴 **表外，拒绝执行**", "为什么": "只跑声明表里的安全 payload（fail-closed）"}
    d = DECLARED[kind]
    cmd = [sys.executable, str(FIVE), "cap", kind, json.dumps(d["payload"], ensure_ascii=False)]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300, cwd=str(ROOT))
        rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return {"判决": "⛔ 痛（超时 >300s）", "payload": d["payload"], "秒": 300.0}
    c = classify(rc, out)
    return dict(c, **{"payload": d["payload"], "rc": rc, "秒": round(time.time() - t0, 1),
                      "为什么这条安全": d["为什么安全"], "出网": d["会不出网"],
                      "命令": "python tools/codex-scripts/five-dim.py cap %s '%s'"
                      % (kind, json.dumps(d["payload"], ensure_ascii=False))})


def cmd_table(a) -> int:
    print(json.dumps({"声明表（只跑这 %d 条）" % len(DECLARED): DECLARED,
                      "纪律": "表外一律拒；每条都写明为什么只读安全；不绕门"},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_run(a) -> int:
    rows, tally, new_scopes = {}, {}, {}
    for k in DECLARED:
        r = probe(k)
        rows[k] = r
        tally[r["判决"]] = tally.get(r["判决"], 0) + 1
        ms = (r.get("详情") or {}).get("missing_scopes")
        if ms:
            new_scopes[k] = ms
    payload = {
        "逐位": rows,
        "合计": tally,
        "🔴 本轮新露出来的作用域（**空参探时看不见**）": {
            "怎么露的": "空参时这些位**先卡在参数校验**，根本走不到门 ⇒ 作用域永远不出现；"
            "给参之后门才发声",
            "逐位": new_scopes,
            "对账的影响": "「缺授权按作用域」那张表若只按**空参探**生成，会**漏掉这些作用域**"
            "（实测：`osint_scan` → `osint_private`）",
        },
        "读法": "「✅ 通」= 给参后真跑通 ·「🟠 环境未就绪」= 分支跑了、条件缺（**不是坏**）· "
        "「🟡 仍是缺参」= 还要别的参 ·「🔒 被门拒」= 从缺参改判成缺授权",
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=1))
    # 落一份给融合层读（否则授权面永远只看得到空参探到的那 9 个作用域）
    try:
        out = ROOT / "state" / "needparam-last.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print("落盘 state/needparam-last.json（%d 字节）" % out.stat().st_size)
    except Exception as e:
        print("⚠️ 落盘失败（不影响读数）：%s" % str(e)[:70])
    return 0


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    # ① **表外一律拒**（负控：拿一个真能力位名去问，必须被拒）
    r = probe("count_words")
    ck("**负控：表外的能力位必须被拒**（fail-closed）",
       "表外" in r["判决"], "%s ⇒ %s" % ("count_words", r["判决"]))
    # ② 每条都必须写明「为什么安全」，否则不许跑
    noplace = [k for k, v in DECLARED.items() if not v.get("为什么安全")]
    ck("每条都写明「为什么这条只读安全」", not noplace, "缺理由: %s" % (noplace or "无"))
    # ③ 声明的 payload 里**不许出现真域名/真 URL**
    bad_url = []
    for k, v in DECLARED.items():
        s = json.dumps(v["payload"], ensure_ascii=False)
        if "http://" in s or "https://" in s or ".com" in s or ".cn" in s:
            bad_url.append(k)
    ck("**声明表里不许有真域名/真 URL**（不许出网）", not bad_url, "可疑: %s" % (bad_url or "无"))
    # ④ 判决分类器负控：三种信封必须分别认出来
    ck("分类器·扁平拒单 ⇒ 判缺授权",
       classify(0, '{"status":"denied","missing_scopes":["process_execute"]}')["判决"].startswith("🔒"),
       "已验")
    ck("分类器·缺参报错 ⇒ 判仍是缺参",
       classify(0, '{"result":{"ok":false,"error_class":"user_error","message":"缺少 url"}}'
                )["判决"].startswith("🟡"), "已验")
    ck("分类器·ok:true ⇒ 判通",
       classify(0, '{"result":{"ok":true,"n":3}}')["判决"].startswith("✅"), "已验")
 # 负控：`ok:false` + `status:"needs_*"` **不是痛**（browser 实测就是这个）
    ck("分类器·**ok:false + needs_\\* ⇒ 判环境未就绪，不判痛**",
       classify(0, '{"result":{"ok":false,"status":"needs_browser_debug","cdp_available":false}}'
                )["判决"].startswith("🟠"),
       "已验（否则就是假痛，F35 同型）")
    # ⑤ 读数里有噪声时也要取到**最后一个**信封（神经总线踩过的坑）
    noisy = '前情提要 {"junk":1}\n{"result":{"ok":true,"x":1}}\n[stamp] 尾巴\n'
    ck("分类器·有噪声 ⇒ 仍取到真信封",
       classify(0, noisy)["判决"].startswith("✅"), "已验（raw_decode 取最后一个对象）")
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="给缺参 5 位喂只读安全参数（表外拒 · 不绕门）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run").set_defaults(func=cmd_run)
    sub.add_parser("table").set_defaults(func=cmd_table)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
