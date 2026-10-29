# -*- coding: utf-8 -*-
"""判据：**4 个云插件的双向绑定**（`state/cloud-plugins-edges.json`）到底成不成立。

四条带牙 + 三条负对照（负对照不通过 ⇒ 判据自己是坏的，出口非零）：
  ① 条数：有向 = N×(N-1) · 无向 = C(N,2)（N 现读台账的 nodes，**不写死 4**）
  ② 对称：每条 a→b 必须有 b→a（这是"双向"的定义）
  ③ 无自环
  ④ 每位度数 = N-1（每位与其余每位各一条出边）
负对照：抽掉一条反向边 ⇒ 必须红；造一个自环 ⇒ 必须红；少一个节点 ⇒ 必须红。

用法：
    py -3.14 -X utf8 tools/codex-scripts/cloud-plugins-bind-check.py
    py -3.14 -X utf8 tools/codex-scripts/cloud-plugins-bind-check.py --json
"""
import argparse
import io
import json
import os
import sys

# ── 编码守门（encoding-guard 要求）：不带 -X utf8 调用时不许静默输出空 ──
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "state", "cloud-plugins-edges.json")


def load():
    return json.load(io.open(SRC, encoding="utf-8"))


def check(doc):
    """返回 (findings, stats)。findings 空 = 合格。"""
    nodes = list(doc.get("nodes") or [])
    edges = [(e.get("from"), e.get("to")) for e in (doc.get("edges") or [])]
    n = len(nodes)
    f = []
    if n < 2:
        f.append("节点少于 2 个（%d）⇒ 谈不上双向绑" % n)
        return f, {"n": n}
    want_d, want_u = n * (n - 1), n * (n - 1) // 2
    if len(edges) != want_d:
        f.append("有向边 %d 条 ≠ 期望 %d（%d×%d）" % (len(edges), want_d, n, n - 1))
    if len(set(edges)) != len(edges):
        f.append("有重复边：%s" % [e for e in set(edges) if edges.count(e) > 1][:4])
    loops = [e for e in edges if e[0] == e[1]]
    if loops:
        f.append("有自环：%s" % loops[:4])
    for a, b in edges:
        if a not in nodes or b not in nodes:
            f.append("边 %s→%s 里有不在 nodes 里的名字" % (a, b))
    # 对称 + 度数
    es = set(edges)
    for a in nodes:
        for b in nodes:
            if a == b:
                continue
            if (a, b) in es and (b, a) not in es:
                f.append("缺反向边：%s→%s 有，%s→%s 没有" % (a, b, b, a))
    undirected = {tuple(sorted(e)) for e in edges if e[0] != e[1]}
    if len(undirected) != want_u:
        f.append("无向边 %d 组 ≠ 期望 %d" % (len(undirected), want_u))
    deg = {a: sum(1 for e in edges if e[0] == a) for a in nodes}
    for a, k in deg.items():
        if k != n - 1:
            f.append("节点 %s 出度 %d ≠ %d" % (a, k, n - 1))
    # 每条边都得有 why（出处纪律）
    for e in (doc.get("edges") or []):
        if not str(e.get("why") or "").strip():
            f.append("边 %s→%s 没有 why（不许只写关系不写理由）" % (e.get("from"), e.get("to")))
    return f, {"n": n, "directed": len(edges), "undirected": len(undirected),
               "deg": deg, "want_directed": want_d, "want_undirected": want_u}


def negative_controls(doc):
    """三条负对照：判据必须在坏对象上真报红（否则是坏尺子）。"""
    out = []
    # ① 抽掉一条反向边
    d = json.loads(json.dumps(doc))
    d["edges"] = [e for e in d["edges"]][:-1]
    f, _ = check(d)
    out.append(("抽掉一条边", bool(f)))
    # ② 造一个自环
    d = json.loads(json.dumps(doc))
    d["edges"].append({"from": d["nodes"][0], "to": d["nodes"][0], "why": "x"})
    f, _ = check(d)
    out.append(("造一个自环", bool(f)))
    # ③ 少一个节点（边没跟着少 ⇒ 度数/对称都会崩）
    d = json.loads(json.dumps(doc))
    d["nodes"] = d["nodes"][:-1]
    f, _ = check(d)
    out.append(("少一个节点", bool(f)))
    # ④ 抽掉一条 why
    d = json.loads(json.dumps(doc))
    d["edges"][0]["why"] = ""
    f, _ = check(d)
    out.append(("抽掉一条 why", bool(f)))
    return out


def main(argv):
    ap = argparse.ArgumentParser(description="4 云插件双向绑定判据")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not os.path.isfile(SRC):
        print("没有台账 %s" % os.path.relpath(SRC, ROOT))
        return 2
    doc = load()
    findings, stats = check(doc)
    ncs = negative_controls(doc)
    bad_nc = [k for k, hit in ncs if not hit]
    out = {"ok": (not findings) and (not bad_nc), "nodes": doc.get("nodes"),
           "stats": stats, "findings": findings,
           "负对照": {k: ("红(应红)" if hit else "没红(尺子坏)") for k, hit in ncs}}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("== 4 云插件双向绑定判据 ==")
        print("  节点 %s" % doc.get("nodes"))
        print("  有向 %d（期望 %d）· 无向 %d 组（期望 %d）"
              % (stats.get("directed", 0), stats.get("want_directed", 0),
                 stats.get("undirected", 0), stats.get("want_undirected", 0)))
        print("  每位出度：%s" % stats.get("deg"))
        for k, hit in ncs:
            print("  负对照[%s] %s" % (k, "红（应红）✓" if hit else "**没红 ⇒ 尺子坏**"))
        if findings:
            print("  🔴 findings：")
            for x in findings:
                print("     - %s" % x)
        print("  => %s" % ("合格" if out["ok"] else "不合格"))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
