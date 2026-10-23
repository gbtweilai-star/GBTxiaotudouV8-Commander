# -*- coding: utf-8 -*-
"""现在到底哪些型号能用？（读 FreeLLMAPI 自己的库 · 只读 · 值打码）

**为什么要读它的库而不是靠探针猜**（2026-09-22 教训）：
  探针只反映"这一秒"；代理是免费上游，会 503/502/空流/冷却。
  真正可信的证据是 app 自己的 `freeapi.db`：`requests`（每条请求的成败与错误原文）、
  `rate_limit_cooldowns`（哪把 key 对哪个模型在冷却）、`api_keys`（key 健康度）。
  ⇒ **先读库定候选，再用一条活体探针确认**，别反过来。

    python tools/model-route/usable-models.py           # 近 60 分钟战绩 + 冷却 + key 健康
    python tools/model-route/usable-models.py --since 180   # 改时间窗（分钟）
"""
from __future__ import annotations

import os
import pathlib
import sqlite3
import sys
import time

# 🔴 2026-09-26 补：Windows 管道/重定向下 stdout 回落 GBK，emoji 一打印就崩；与 self_model.py 同一款补丁
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


DB = pathlib.Path(os.environ.get("APPDATA", "")) / "FreeLLMAPI" / "freeapi.db"


def main():
    since = 60
    a = sys.argv[1:]
    if "--since" in a:
        since = int(a[a.index("--since") + 1])
    if not DB.exists():
        print(f"❌ 找不到 {DB}（FreeLLMAPI 没装 / 路径变了）")
        sys.exit(1)
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    now = int(time.time() * 1000)

    print(f"数据源 {DB}（只读）· 时间窗 近 {since} 分钟\n")

    print("① key 健康度")
    for r in con.execute("SELECT platform, status, COUNT(*) n FROM api_keys GROUP BY platform, status"):
        print(f"   {r['platform']:<10} {r['status']:<10} ×{r['n']}")

    print(f"\n② 近 {since} 分钟战绩（ok 多 bad 少 = 现在能用）")
    q = f"""SELECT model_id,
                   SUM(status='success') ok, SUM(status<>'success') bad,
                   MAX(CASE WHEN status='success' THEN created_at END) last_ok
            FROM requests WHERE created_at >= datetime('now','-{since} minutes')
            GROUP BY model_id ORDER BY ok DESC, bad ASC"""
    rows = list(con.execute(q))
    usable = [r for r in rows if r["ok"] and r["ok"] >= r["bad"]]
    for r in rows[:20]:
        flag = "✅" if r in usable else "❌"
        print(f"   {flag} {str(r['model_id'])[:34]:<34} ok={r['ok']:<3} bad={r['bad']:<3} 最近成功={str(r['last_ok'])[:19]}")
    if not rows:
        print("   （窗口内无请求）")

    print("\n③ 仍在冷却（等这些没意义）")
    for r in con.execute("SELECT model_id, key_id, expires_at_ms FROM rate_limit_cooldowns ORDER BY expires_at_ms DESC LIMIT 8"):
        left = max(0, (r["expires_at_ms"] - now) / 1000) if r["expires_at_ms"] else 0
        if left <= 0:
            continue
        print(f"   {str(r['model_id'])[:34]:<34} key#{r['key_id']:<3} 还剩 {left/3600:.1f} 小时")

    print("\n④ 最近错误原文（判断是上游故障还是配额）")
    for r in con.execute("""SELECT created_at, model_id, error FROM requests
                            WHERE status<>'success' AND error IS NOT NULL
                            ORDER BY created_at DESC LIMIT 6"""):
        print(f"   {str(r['created_at'])[:19]} {str(r['model_id'])[:20]:<20} {str(r['error'])[:96]}")
    con.close()

    print(f"\n⇒ 现在可优先用：{', '.join(str(r['model_id']) for r in usable[:4]) or '（窗口内没有稳定成功的型号）'}")
    sys.exit(0 if usable else 1)


if __name__ == "__main__":
    main()
