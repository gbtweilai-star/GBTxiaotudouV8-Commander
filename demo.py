# -*- coding: utf-8 -*-
"""30 秒看懂的 demo：一句话 → 一位能力位 → 该跑的那条真命令。

不需要模型权重、不需要联网、不需要装任何第三方包：

    python demo.py
    python demo.py "我要把一份 Markdown 变成 PPT，该调哪个能力位？"
    python demo.py "扫一下镜像有没有脏东西"      # 只读位
    python demo.py "把这次发布推到生产"          # 会被门挡住的那种

想让它**真做决策**（而不是关键字兜底），加一个 OpenAI 兼容端点：

    python demo.py "把这份 Markdown 转成 PPT" --endpoint http://127.0.0.1:8000/v1 --model gbt-v8

两种模式在输出里都写清了是哪一种，不混着说。
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from gbt_commander import Catalog, CommanderClient          # noqa: E402

QUESTION = "我要把一份 Markdown 变成 PPT，该调哪个能力位？需要什么参数？"


def print_stats(cat: Catalog) -> None:
    s = cat.stats()
    print("① 这台机器的能力目录（机器可读，不是截图）")
    print("   %d 位能力 · %d 个域 · 只读 %d · 会改状态 %d · 挂作用域 %d"
          % (s["capabilities"], s["domains"], s["readonly"], s["writes"], s["needs_ticket"]))
    print("   %s" % (cat.meta.get("note") or ""))
    print("")


def show_hits(cat: Catalog, question: str, limit: int = 3) -> None:
    print("② 按你的那句话，落点候选（关键字打分，不是模型决策）：")
    for cap, score in cat.search(question, limit):
        kind = "只读" if cap.readonly else "会改状态"
        gate = "零作用域" if not cap.needs_ticket else "要票：" + ",".join(cap.scopes_static)
        print("   [%.1f] %-18s %-12s %-8s %s" % (score, cap.name, cap.domain, kind, gate))
        print("         %s" % cap.one_liner)
    print("")


def print_command(cat: Catalog, question: str) -> None:
    hits = cat.search(question, 1)
    if not hits:
        print("③ 没命中：换个说法，或 `python -m gbt_commander catalog` 翻一遍。")
        return
    cap = hits[0][0]
    payload = "{}"
    if cap.requires_params and cap.params_hint:
        payload = '<按 params_hint 填：%s>' % cap.params_hint.replace("'", " ")
    print("③ 在这台机器上，它就是这么被调用的（唯一门，绕过它没有留痕）：")
    print("   py -3.14 tools/codex-scripts/five-dim.py cap %s '%s'" % (cap.name, payload))
    print("   回执形状：{gate, kind, status, stamp, denied, result:{ok, ...}}")
    if cap.needs_ticket:
        print("   ⚠️ 这一位挂了作用域 %s ⇒ 门会先拒，等主人发票（AI 不能给自己发）。"
              % ",".join(cap.scopes_static))
    else:
        print("   ✓ 零作用域 ⇒ 不需要授权；但「零作用域 ≠ 只读」，会不会改状态看 readonly=%s。"
              % cap.readonly)
    print("")


def route_with_model(args: argparse.Namespace, cat: Catalog) -> int:
    client = CommanderClient(base_url=args.endpoint, model=args.model,
                             api_key=args.api_key, timeout=args.timeout)
    rec = client.route(args.question, cat)
    call = rec.get("call") or {}
    print("② 模型决策（route=model）")
    print("   端点 %s · 模型 %s · http=%s · %ss · usage=%s"
          % (args.endpoint, args.model, call.get("http"), call.get("elapsed_s"),
             call.get("usage") or {}))
    if not rec.get("ok"):
        print("   决策不可用：%s" % rec.get("error"))
        return 1
    print("   能力位 %s（%s）" % (rec["capability"], rec.get("domain")))
    print("   参数 %s" % (rec.get("args") or {}))
    print("   理由 %s" % rec.get("reason"))
    print("   校验 目录里查得到 ⇒ verified=true（模型编名字会被这里拦下）")
    print("")
    print_command(cat, rec["capability"])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="GBT小土豆V8 · 30 秒 demo")
    ap.add_argument("question", nargs="?", default=QUESTION)
    ap.add_argument("--endpoint", default=None, help="OpenAI 兼容 base_url（给了就真调模型）")
    ap.add_argument("--model", default="gbt-v8")
    ap.add_argument("--api-key", default="EMPTY")
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()

    cat = Catalog.load()
    print_stats(cat)
    if args.endpoint:
        rc = route_with_model(args, cat)
        print("④ 下一步：`python -m gbt_commander catalog --domain <域>` 看这个域还有什么。")
        return rc
    print("   （没给 --endpoint ⇒ 下面是关键字兜底，不是模型决策：route=keyword-fallback）")
    print("")
    show_hits(cat, args.question)
    print_command(cat, args.question)
    print("④ 想让它真做决策：")
    print('   python demo.py "%s" --endpoint http://127.0.0.1:8000/v1 --model gbt-v8'
          % args.question)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
