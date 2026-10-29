# -*- coding: utf-8 -*-
"""全能力「真调用」扫（caps_sweep）—— 每一项能力都过门调一次，逐项记读数。

主人令（2026-10-09）：「她的每一项能力你都要调用跑通闭环才算完成」。

口径：
  · **真调用**：每个能力位都走 gbt_allinone.run_task（唯一门），不是静态审计、不是看图鉴；
  · **逐项**：一位一条读数，**不报合计**（本仓旧训：报一个总数不算读数）；
  · **隔离**：每个能力位跑在**独立子进程**里，带超时 —— 一个挂死/崩溃不许拖垮整轮；
  · **诚实分类**（六类，一位只归一档）：
      通        status=ok 且本体没明说失败
      如实拒    denied=true（缺票）—— 门在正常工作，不是坏
      要参数    本体 user_error / 缺必填参数
      缺依赖    needs_dependency / unavailable
      超时      到点没回
      真坏      抛异常 / traceback / 退出码异常
用法：
  py -3.14 -X utf8 tools/codex-scripts/caps_sweep.py            # 全扫（默认每位 45s）
  py -3.14 -X utf8 tools/codex-scripts/caps_sweep.py --timeout 30 --skip sec_scan,media_run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".scratch" / "_caps_sweep.jsonl"

CHILD = r'''
import json, sys
sys.path.insert(0, r"%s")
from gbt_allinone import run_task
kind = sys.argv[1]
payload = json.loads(sys.argv[2])
env = run_task(kind, payload)
b = env.get("gbt_result", env)
res = b.get("result") if isinstance(b, dict) else None
out = {"kind": kind, "env_status": b.get("status"), "denied": bool(b.get("denied")),
       "missing_scopes": b.get("missing_scopes") or [],
       "stamp": b.get("stamp"), "auth_consumed": b.get("auth_consumed")}
# 有些能力位把内层信封塞在 result 下面（实测 brain_execute）—— 得挖深一层才看得见真错类
if isinstance(res, dict) and isinstance(res.get("result"), dict):
    inner = res["result"]
    merged = dict(res)
    for k in ("ok", "status", "message", "error_class"):
        merged.setdefault(k, inner.get(k))
    if inner.get("ok") is not None:
        merged["ok"] = inner.get("ok")
    res = merged
if isinstance(res, dict):
    out["ok"] = res.get("ok")
    out["result_status"] = res.get("status")
    out["unavailable"] = res.get("unavailable")
    out["error"] = str(res.get("error") or res.get("why") or res.get("message") or "")[:220]
    out["error_class"] = res.get("error_class")
    out["keys"] = sorted(res)[:12]
    # 把「为什么 ok=false」的理由也抓下来 —— 否则报表层分不清「如实否」与「真坏」
    for k in ("note", "reason_code", "verdict", "why", "message", "blockers", "error",
              "degraded_reason", "failed", "rules"):
        if res.get(k):
            out["reason"] = str(res.get(k))[:200]
            out["reason_field"] = k
            break
else:
    out["ok"] = None
    out["raw_type"] = type(res).__name__
    out["raw"] = str(res)[:160]
print("@@SWEEP@@" + json.dumps(out, ensure_ascii=False))
''' % str(ROOT)


def classify(o: dict, timed_out: bool = False) -> str:
    if timed_out:
        return "超时"
    if o.get("denied"):
        return "如实拒"
 # 先认本体自己报的错类（error_class），**不要拿 env_status==error 当崩**：
    #    实测 browser 无参就是 `status:error + message:'缺少 url' + error_class:'user_error'` —— 那叫「要参数」。
    ec = str(o.get("error_class") or "")
    rs = str(o.get("result_status") or "")
    es = str(o.get("env_status") or "")
    if "Traceback" in str(o.get("error", "")):
        return "真坏"
    if ec == "user_error" or rs == "user_error" or es == "user_error":
        return "要参数"
    if ec in ("needs_dependency", "unavailable") or o.get("unavailable") or rs == "needs_dependency":
        return "缺依赖"
    if o.get("ok") is False and not ec:
 # 实测：mcp_tools / prompt_bridge / train_recipe 无参都返回 ok=false，但**每条都带着理由**
        #    （note / reason_code / verdict+blockers）—— 那叫「如实否」，不是崩。
        #    只有**连理由都没有**的 ok=false 才配叫真坏（本仓旧训：不许只灰不解释）。
        if o.get("reason") or o.get("error"):
            return "如实否"
        return "真坏"
    if es == "ok" and o.get("ok") is not False:
        return "通"
    if es == "error" and o.get("error"):
        return "要参数"
    return "真坏"


def main() -> int:
    ap = argparse.ArgumentParser(description="全能力真调用扫")
    ap.add_argument("--timeout", type=float, default=45.0)
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="")
    ap.add_argument("--out", default=str(OUT))
    # 第二阶段用：按位喂最小真实 payload（JSON 文件 {kind: {...}}）——好让「要参数」的位也能跑通闭环。
 # 只用**真能表达业务**的最小值；编不出来的位如实留在「要参数」，**不许为凑绿编假输入**。
    ap.add_argument("--payloads", default="")
    a = ap.parse_args()

    sys.path.insert(0, str(ROOT))        # 本件在 tools/ 下，得先把仓根挂上才 import 得到
    from gbt_allinone import caps_registry as CR
    kinds = sorted(CR.BENIGN_CAPS)
    if a.only:
        want = {x.strip() for x in a.only.split(",") if x.strip()}
        kinds = [k for k in kinds if k in want]
    skip = {x.strip() for x in a.skip.split(",") if x.strip()}
    kinds = [k for k in kinds if k not in skip]

    pays = {}
    if a.payloads:
        pays = json.loads(Path(a.payloads).read_text(encoding="utf-8"))
    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    tally, rows = {}, []
    with outp.open("w", encoding="utf-8") as f:
        for i, kind in enumerate(kinds, 1):
            t0 = time.time()
            to = False
            try:
 # 2026-10-10 根因修复（全量扫报 5 个「真坏」**全是假的**）：
                #    子进程用 `sys.executable -c` 起、**不带 -X utf8** ⇒ 它在 GBK 控制台上打
                #    中文与「⇒」(U+21D2) 直接 UnicodeEncodeError 崩掉 ⇒ 被上层判成"真坏"。
                #    实测原文：UnicodeEncodeError: 'gbk' codec can't encode character '\u21d2'。
                #    这是本会话**第三次**撞同一个根因（checkup 一次、这里一次）——
                #    凡"派子进程"的地方都必须带 utf8 总开关。
                cp = subprocess.run([sys.executable, "-X", "utf8", "-c", CHILD, kind,
                                     json.dumps(pays.get(kind), ensure_ascii=False) if kind in pays else "{}"],
                                    capture_output=True, timeout=a.timeout)
                txt = (cp.stdout or b"").decode("utf-8", "replace")
                line = next((x for x in txt.splitlines() if x.startswith("@@SWEEP@@")), "")
                if line:
                    o = json.loads(line[len("@@SWEEP@@"):])
                else:
                    o = {"kind": kind, "env_status": "failed",
                         "error": ((cp.stderr or b"").decode("utf-8", "replace")[-220:])}
            except subprocess.TimeoutExpired:
                o, to = {"kind": kind, "env_status": "timeout", "error": "到点没回"}, True
            o["ms"] = int((time.time() - t0) * 1000)
            o["verdict"] = classify(o, to)
            tally[o["verdict"]] = tally.get(o["verdict"], 0) + 1
            rows.append(o)
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
            f.flush()
            first = (o.get("error") or o.get("raw") or "")[:70].replace("\n", " ")
            print("%3d/%-3d %-22s %-6s %6dms %s" % (i, len(kinds), kind, o["verdict"], o["ms"], first),
                  flush=True)

    print("\n========== 分类账（逐项已落 %s）==========" % outp)
    for k in ("通", "如实否", "如实拒", "要参数", "缺依赖", "超时", "真坏"):
        if tally.get(k):
            print("  %-6s %d" % (k, tally[k]))
    for k in ("超时", "真坏"):
        bad = [r["kind"] for r in rows if r["verdict"] == k]
        if bad:
            print("\n  %s 明细：%s" % (k, "、".join(bad)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
