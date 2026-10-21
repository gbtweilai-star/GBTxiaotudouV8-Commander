# -*- coding: utf-8 -*-
"""命令行入口：`python -m gbt_commander <子命令>`。

四个子命令，都不需要模型权重、不需要联网（`route --endpoint` 才联网）：

    stats                     一眼看目录读数（341 位 / 30 域 / 只读几多 / 要票几多）
    catalog [--domain D]      列能力位
    search "把 Markdown 转 PPT"   按意图找能力位（关键字打分，不调模型）
    route "…" [--endpoint URL]    落到一位能力位；给了端点就用模型，没给就退回关键字
"""
from __future__ import annotations

import argparse
import sys

from .catalog import Catalog
from .client import CommanderClient


def _fmt_scopes(cap) -> str:
    if not cap.scopes_static:
        return "—（零作用域，但不等于只读）"
    return ",".join(cap.scopes_static)


def cmd_stats(args: argparse.Namespace, cat: Catalog) -> int:
    s = cat.stats()
    print("能力目录：%s" % (args.db or "data/capabilities.json"))
    print("  总位数      %d" % s["capabilities"])
    print("  域数        %d" % s["domains"])
    print("  只读位      %d" % s["readonly"])
    print("  会改状态    %d（调用前要过授权门）" % s["writes"])
    print("  挂作用域    %d（要主人发票）" % s["needs_ticket"])
    print("  必须带参数  %d" % s["requires_params"])
    print("")
    print("按域分布（成员数从多到少）：")
    for domain, n in cat.domains().items():
        print("  %-16s %3d" % (domain, n))
    return 0


def cmd_catalog(args: argparse.Namespace, cat: Catalog) -> int:
    caps = cat.by_domain(args.domain) if args.domain else list(cat)
    if args.domain and not caps:
        print("没有这个域：%s（可用域见 `stats`）" % args.domain)
        return 1
    caps.sort(key=lambda c: (c.domain, c.name))
    print("%-22s %-14s %-6s %s" % ("能力位", "域", "类型", "一句话"))
    print("-" * 108)
    for cap in caps[: args.limit]:
        kind = "只读" if cap.readonly else "会改状态"
        print("%-22s %-14s %-6s %s" % (cap.name, cap.domain, kind, cap.one_liner))
    if len(caps) > args.limit:
        print("… 还有 %d 位没显示（--limit 调大或加 --domain 收窄）" % (len(caps) - args.limit))
    return 0


def cmd_search(args: argparse.Namespace, cat: Catalog) -> int:
    hits = cat.search(args.query, args.limit)
    if not hits:
        print("没命中。换个说法，或直接 `catalog` 翻一遍。")
        return 1
    print("意图：%s" % args.query)
    print("")
    for cap, score in hits:
        print("[%.1f] %s · %s · %s" % (score, cap.name, cap.domain,
                                       "只读" if cap.readonly else "会改状态"))
        print("      %s" % cap.one_liner)
        print("      作用域：%s" % _fmt_scopes(cap))
        if cap.requires_params and cap.params_hint:
            print("      参数：%s" % cap.params_hint)
        print("")
    return 0


def cmd_route(args: argparse.Namespace, cat: Catalog) -> int:
    question = args.question
    if args.endpoint:
        client = CommanderClient(base_url=args.endpoint, model=args.model,
                                 api_key=args.api_key, timeout=args.timeout)
        rec = client.route(question, cat)
        call = rec.get("call") or {}
        print("模型：%s @ %s" % (args.model, args.endpoint))
        print("回执：http=%s · %ss · usage=%s" % (call.get("http"), call.get("elapsed_s"),
                                                  call.get("usage") or {}))
        print("")
        if not rec.get("ok"):
            print("决策不可用：%s" % rec.get("error"))
            if rec.get("capability"):
                print("模型原话的能力位名：%s（目录里查不到 ⇒ 判为幻觉，不放行）" % rec["capability"])
            return 1
        print("能力位：%s（%s）" % (rec["capability"], rec.get("domain")))
        print("参数：%s" % (rec.get("args") or {}))
        print("理由：%s" % rec.get("reason"))
        print("校验：目录里查得到 ⇒ verified=true")
        print("风险：%s（只读=%s · 作用域=%s）" % (rec.get("risk"), rec.get("readonly"),
                                                  rec.get("scopes_static") or "无"))
        return 0

    # 没给端点：关键字兜底，并且**明说**这不是模型决策
    hits = cat.search(question, 3)
    print("⚠️ 未给 --endpoint ⇒ 这是**关键字兜底**，不是模型决策（`route=keyword-fallback`）。")
    print("")
    if not hits:
        print("没命中。带端点跑一次真模型：")
        print('  python -m gbt_commander route "%s" --endpoint http://127.0.0.1:8000/v1' % question)
        return 1
    for cap, score in hits:
        print("[%.1f] %s · %s · %s" % (score, cap.name, cap.domain,
                                       "只读" if cap.readonly else "会改状态"))
        print("      作用域：%s" % _fmt_scopes(cap))
    print("")
    print("带端点让它真做决策：")
    print('  python -m gbt_commander route "%s" --endpoint http://127.0.0.1:8000/v1' % question)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gbt_commander",
        description="GBT小土豆V8 · 能力目录与决策校验（零依赖）",
    )
    p.add_argument("--db", default=None, help="能力目录 JSON 路径（默认 data/capabilities.json）")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("stats", help="目录读数")
    s.set_defaults(func=cmd_stats)

    c = sub.add_parser("catalog", help="列能力位")
    c.add_argument("--domain", default=None)
    c.add_argument("--limit", type=int, default=40)
    c.set_defaults(func=cmd_catalog)

    q = sub.add_parser("search", help="按意图找能力位")
    q.add_argument("query")
    q.add_argument("-n", "--limit", type=int, default=5)
    q.set_defaults(func=cmd_search)

    r = sub.add_parser("route", help="落到一位能力位（给端点就调模型）")
    r.add_argument("question")
    r.add_argument("--endpoint", default=None, help="OpenAI 兼容 base_url，如 http://127.0.0.1:8000/v1")
    r.add_argument("--model", default="gbt-v8")
    r.add_argument("--api-key", default="EMPTY")
    r.add_argument("--timeout", type=float, default=120.0)
    r.set_defaults(func=cmd_route)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cat = Catalog.load(args.db)
    except (FileNotFoundError, ValueError) as exc:
        print("读不到能力目录：%s" % exc, file=sys.stderr)
        return 2
    return int(args.func(args, cat))


if __name__ == "__main__":
    raise SystemExit(main())
