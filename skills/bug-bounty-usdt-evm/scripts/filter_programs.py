#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# gbt-capability: bug-bounty-usdt-evm · filter_programs
"""赏金程序筛选器 —— **读本地 JSON，不联网，零依赖**。

它**只筛盘上已有的数据**。数据从哪来是另一件事（见 SKILL.md §3）：
  · 主线：主人给本地 JSON（或自己克隆下来的清单）；
  · 联网：走 `browser` 能力位（要 `browser_control` 票）—— 本脚本**不替你联网**，
    因为它不该在"没人看着"的时候出去拿数据。

输入形状（两种都收）：
  {"programs": [ {...}, ... ]}   或   [ {...}, ... ]

一条程序长这样（字段取不到的就没有，不造）：
  {
    "name": "…", "url": "https://immunefi.com/bug-bounty/<slug>/",
    "max_bounty_usd": 50000,
    "assets": [
      {"type": "smart_contract", "chain": "arbitrum", "token": "USDT", "address": "0x…"},
      {"type": "website", "url": "https://…"}
    ]
  }

命令：
  py -3.14 -X utf8 …/filter_programs.py --in state/bounties_raw.json --chain arbitrum --type smart_contract
  py -3.14 -X utf8 …/filter_programs.py --template      # 打印空模板（拿去填）
  py -3.14 -X utf8 …/filter_programs.py --selftest      # 负对照：合成数据，能筛能漏

退出码：0 跑成（哪怕 0 命中，也是"跑成了"）；1 输入坏了；2 selftest 失败。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_TEMPLATE = {
    "_note": "把真实数据填进来；字段取不到就删掉该字段，别填猜的",
    "source": "<从哪来的：本地克隆 / browser_control 读到 / 主人手给>",
    "fetched_at": "<YYYY-MM-DDTHH:MM:SS+07:00>",
    "programs": [
        {
            "name": "<程序名>",
            "url": "https://immunefi.com/bug-bounty/<slug>/",
            "max_bounty_usd": 0,
            "assets": [
                {"type": "smart_contract", "chain": "<arbitrum|ethereum|base|…>",
                 "token": "<USDT|USDC|…>", "address": "0x<40 hex>"}
            ],
        }
    ],
}


def _norm(v) -> str:
    return str(v or "").strip().lower()


def load(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("programs", [])
    if not isinstance(data, list):
        raise ValueError("输入不是 list，也不是含 programs 的 dict")
    return data


def _match_asset(asset: dict, chain: str, atype: str, token: str) -> bool:
    if chain and _norm(asset.get("chain")) != chain:
        return False
    if atype and _norm(asset.get("type")) != atype:
        return False
    if token and _norm(asset.get("token")) != token:
        return False
    return bool(chain or atype or token)


def filter_programs(programs: list, chain="", atype="", token="", kw="", min_bounty=0) -> list:
    chain, atype, token, kw = _norm(chain), _norm(atype), _norm(token), _norm(kw)
    out = []
    for p in programs:
        if not isinstance(p, dict):
            continue
        if kw and kw not in _norm(p.get("name")):
            continue
        try:
            if int(p.get("max_bounty_usd") or 0) < int(min_bounty):
                continue
        except (TypeError, ValueError):
            continue
        hit_assets = [a for a in (p.get("assets") or []) if isinstance(a, dict)
                      and _match_asset(a, chain, atype, token)]
        if (chain or atype or token) and not hit_assets:
            continue
        out.append({
            "name": p.get("name"),
            "url": p.get("url"),
            "max_bounty_usd": p.get("max_bounty_usd"),
            "matched_assets": hit_assets or p.get("assets") or [],
        })
    return out


def selftest() -> int:
    fails = []
    sample = [
        {"name": "Alpha", "url": "u1", "max_bounty_usd": 100000,
         "assets": [{"type": "smart_contract", "chain": "Arbitrum", "token": "USDT", "address": "0x" + "1" * 40}]},
        {"name": "Beta", "url": "u2", "max_bounty_usd": 5000,
         "assets": [{"type": "smart_contract", "chain": "ethereum", "token": "USDC"},
                    {"type": "website", "url": "https://beta"}]},
        {"name": "Gamma", "url": "u3", "max_bounty_usd": 20000,
         "assets": [{"type": "blockchain_dlt", "chain": "arbitrum"}]},
    ]
    r = filter_programs(sample, chain="arbitrum", atype="smart_contract", token="usdt")
    if [x["name"] for x in r] != ["Alpha"]:
        fails.append(f"链+类型+代币三筛应只剩 Alpha，实得 {[x['name'] for x in r]}")

    r = filter_programs(sample, chain="arbitrum")
    if sorted(x["name"] for x in r) != ["Alpha", "Gamma"]:
        fails.append(f"只按链应得 Alpha+Gamma，实得 {[x['name'] for x in r]}")

    r = filter_programs(sample, atype="website")
    if [x["name"] for x in r] != ["Beta"]:
        fails.append("按类型 website 应只剩 Beta")

    r = filter_programs(sample, min_bounty=10000)
    if sorted(x["name"] for x in r) != ["Alpha", "Gamma"]:
        fails.append("按最低赏金 10000 应得 Alpha+Gamma")

    r = filter_programs(sample, kw="beta")
    if [x["name"] for x in r] != ["Beta"]:
        fails.append("按名字关键词 beta 应只剩 Beta")

    if filter_programs(sample, chain="solana"):
        fails.append("按不存在的链应 0 命中（负对照）")

    if fails:
        print(json.dumps({"selftest": "FAIL", "fails": fails}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"selftest": "PASS", "cases": 6}, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="赏金程序筛选（本地 JSON · 零依赖）")
    ap.add_argument("--in", dest="src", help="输入 JSON 路径")
    ap.add_argument("--chain", default="", help="链（等值匹配，忽略大小写）")
    ap.add_argument("--type", dest="atype", default="", help="资产类型，如 smart_contract / website")
    ap.add_argument("--token", default="", help="代币，如 USDT")
    ap.add_argument("--kw", default="", help="程序名关键词")
    ap.add_argument("--min-bounty", type=int, default=0, help="最低最高赏金（USD）")
    ap.add_argument("--out", help="把筛选结果写成 JSON")
    ap.add_argument("--template", action="store_true", help="打印空模板")
    ap.add_argument("--selftest", action="store_true", help="跑负对照")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.template:
        print(json.dumps(_TEMPLATE, ensure_ascii=False, indent=2))
        return 0
    if not args.src:
        ap.print_help()
        return 1

    try:
        programs = load(Path(args.src))
    except Exception as e:  # 输入坏了要如实报，别吞
        print(json.dumps({"status": "error", "error_class": "bad_input", "message": str(e)},
                         ensure_ascii=False), file=sys.stderr)
        return 1

    hits = filter_programs(programs, args.chain, args.atype, args.token, args.kw, args.min_bounty)
    payload = {
        "status": "ok",
        "src": args.src,
        "filters": {"chain": args.chain, "type": args.atype, "token": args.token,
                    "kw": args.kw, "min_bounty": args.min_bounty},
        "scanned": len(programs),
        "matched": len(hits),
        "programs": hits,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["wrote"] = args.out
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
