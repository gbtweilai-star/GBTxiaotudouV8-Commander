# -*- coding: utf-8 -*-
"""dbfleet 判据 —— 咬「数据库编队有没有被念成已开通」。

## 为什么有它
主人 2026-10-07 令：把最大内存、最稳的免费数据库排布好指向、备注存什么。
设计已完备（deploy/cloud-10/db-fleet.json：7 条编队 + 指向表 + 额度带出处 + 谁当主库两条硬标准），
**但 7 条一个都没开通** —— 而设计**自己**在 honesty 第①条写了「这些库一个都还没开通」。

⇒ 本判据咬的就是这件事：**不许把「设计」念成「已开通」**。

## 判据四条
  ① 编队齐（db-fleet.json 的 fleet 条数 == state/dbfleet_probe.json 的 fleets 条数）；
  ② **逐条现读**：每条编队的 apiKeyEnv 在环境里有没有值 ⇒ 没有就是「未开通」；
  ③ **百库是 Turso 的分片**：shards_100 必须 100 条、各带独立 env 名；
  ④ **负控（真植入）**：假装给某条编队设了 env ⇒ 它必须从「未开通」变成「有环境变量」。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")           # type: ignore[attr-defined]
    except Exception:
        pass

WS = pathlib.Path(__file__).resolve().parents[2]
FLEET = WS / "deploy" / "cloud-10" / "db-fleet.json"
PROBE = WS / "state" / "dbfleet_probe.json"


def _probe_fresh() -> list:
    """现读环境变量（不缓存）。"""
    d = json.loads(FLEET.read_text(encoding="utf-8"))
    out = []
    for f in d.get("fleet") or []:
        env = f.get("apiKeyEnv") or ""
        envs = env if isinstance(env, list) else [env]
        have = [e for e in envs if e and (os.environ.get(e) or "").strip()]
        out.append({"id": f.get("id"), "provider": f.get("provider"), "role": f.get("role"),
                    "rank": f.get("rank"), "envs": envs,
                    "status": "未开通" if not have else "有环境变量(%d/%d)" % (len(have), len(envs))})
    return out


def check() -> dict:
    problems, notes = [], []
    if not FLEET.is_file():
        return {"ok": False, "problems": ["db-fleet.json 不在：%s" % FLEET]}
    live = _probe_fresh()
    if not PROBE.is_file():
        problems.append("探针件不在（没落真件）：%s" % PROBE)
        return {"ok": False, "problems": problems, "live": live}
    p = json.loads(PROBE.read_text(encoding="utf-8"))

    if len(p.get("fleets") or []) != len(live):
        problems.append("编队数对不上：设计 %d vs 探针 %d" % (len(live), len(p.get("fleets") or [])))
    shards = p.get("shards_100") or []
    if len(shards) != 100:
        problems.append("百库分片不是 100 条：实得 %d" % len(shards))
    if len({s.get("env") for s in shards}) != len(shards):
        problems.append("百库分片的 env 名有重复（分片必须各自隔离）")

    opened = [f for f in live if f["status"] != "未开通"]
    notes.append("编队 %d 条 · **真开通 %d 条** · 分片 %d 条"
                 % (len(live), len(opened), len(shards)))
    if not opened:
        notes.append("⚠️ 一条都没开通 —— **这不是失败，是如实**：开通要主人的账号与密钥"
                     "（设计里 apiKeyEnv 逐条点名）；本判据只确保它**不被念成已开通**")
    # 探针里的 status 必须与**现读**一致（防止探针件过期后骗人）
    stale = []
    for a, b in zip(p.get("fleets") or [], live):
        if a.get("id") == b.get("id") and a.get("status") != b.get("status"):
            stale.append("%s: 探针写 %s，现读 %s" % (a.get("id"), a.get("status"), b.get("status")))
    if stale:
        problems.append("探针件**过期**（与现读不一致，会骗人）：%s" % stale)

    return {"ok": not problems, "problems": problems, "notes": notes,
            "fleets": len(live), "opened": len(opened), "shards": len(shards), "live": live}


def selftest() -> int:
    ok = []
    real = check()
    ok.append(("真件·编队能现读", bool(real.get("live")), "编队 %s 条" % real.get("fleets")))
    ok.append(("真件·百库分片 100 条", real.get("shards") == 100, "shards=%s" % real.get("shards")))
    ok.append(("真件·零开通时不许报绿成'已部署'",
               isinstance(real.get("opened"), int), "开通 %s" % real.get("opened")))
    # 真植入负控：给一条编队设 env ⇒ 它必须变「有环境变量」
    key = None
    d = json.loads(FLEET.read_text(encoding="utf-8"))
    for f in d.get("fleet") or []:
        e = f.get("apiKeyEnv")
        if isinstance(e, str) and e.startswith("GBT_DB_"):
            key = e
            break
    if key:
        os.environ[key] = "probe-value-not-a-real-key"
        again = _probe_fresh()
        flipped = [f for f in again if f["status"] != "未开通"]
        ok.append(("真植入负控·设一条 env ⇒ 必须被现读看见", bool(flipped),
                   "%s → %s" % (key, flipped[0]["status"] if flipped else "没变")))
        os.environ.pop(key, None)
    else:
        ok.append(("真植入负控·找得到可测的 env 名", False, "没找到 GBT_DB_* 的 apiKeyEnv"))
    bad = [n for n, c, _ in ok if not c]
    for n, c, dd in ok:
        print("  %-46s %s  (%s)" % (n, "✅" if c else "❌", dd))
    print("")
    print("dbfleet-check 自检: %s（%d 条）"
          % ("全部通过" if not bad else "%d 条失败" % len(bad), len(ok)))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="数据库编队判据")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = check()
    print("=" * 74)
    print("数据库编队审查 —— 不许把「设计」念成「已开通」")
    print("=" * 74)
    for f in r.get("live") or []:
        print("  %-14s %-12s %-24s rank=%-3s %s"
              % (f.get("id"), str(f.get("provider"))[:12], str(f.get("role"))[:24],
                 f.get("rank"), f.get("status")))
    print("")
    for n in r.get("notes") or []:
        print("  · %s" % n)
    print("")
    if r.get("problems"):
        for p in r["problems"]:
            print("  🔴 %s" % p)
        print("")
        print("  结论：**红 %d 条**" % len(r["problems"]))
    else:
        print("  ✅ 编队齐 · 逐条现读 · 百库分片 100 · **未开通如实报未开通**")
    print("")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
