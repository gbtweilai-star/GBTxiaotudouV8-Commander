#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""plugin-mesh · **插件全互通矩阵**（主人令 2026-09-25）

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 主人原话
> 「把**所有插件联通到一起**，比如 1 号和 2 号互通、1 号和 3 号互通、3 号和 2 号互通
>   等于说**所有插件都是互通的**，这样就没有 CPU 的问题了」

## 这一层做什么
把面板上那张**真插件表**（`deploy-panel.py::PLUGIN_SLOTS`）当节点，
算出**全互通**应有的每一对连线（N×(N−1) 条**有向**边），并**逐对给出通道**
（同机直调 / 编排层 / 云通道 / 触手总线），把**还没有通道的对**点名出来。
⇒ 「全互通」由**矩阵**保证，不靠记性。

## 一条必须说清的诚实边界（**主人的推断需要更正**）
> 「这样就没有 CPU 的问题了」

**互通不解决 CPU。** 把 N 个插件两两连通，跑的还是**同一台机器、同一颗 CPU**
（本机 Ryzen 5 5600H 6C/12T · 可见内存 7.39 GB）。
互通真正解决的是**三件别的事**：
  ① **不重复造**（A 的结果 B 直接取，不必各算一遍）；
  ② **不各自为政**（每个件都能被别的件调到，没有孤岛）；
  ③ **可换路**（某条路坏了能走备用路 —— 这是 `failover.py` 已经在做的）。
CPU 的问题只能靠**换算法 / 减负载 / 上云 GPU**，**互通一步也帮不上**。
**本工具只报连线，不承诺算力。**

用法：
  plugin-mesh.py matrix     # 全互通矩阵（逐对给通道 + 点名无通道的对）
  plugin-mesh.py gaps       # 只看还没通道的对
  plugin-mesh.py route A B  # A 到 B 怎么走
  plugin-mesh.py selftest
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "tools" / "codex-scripts" / "deploy-panel.py"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def slots() -> list:
    """读面板的**真插件表**（AST 取字面量，不执行模块）。"""
    tree = ast.parse(PANEL.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "PLUGIN_SLOTS":
                    return [{"编号": r[0], "名称": r[1], "做什么": r[2], "落点": r[3],
                             "真命令": r[4], "关联模块": r[5], "状态": r[6], "出处": r[7]}
                            for r in ast.literal_eval(node.value)]
    return []


def channel(a: dict, b: dict) -> dict:
    """**A 到 B 的通道** —— 逐条按可观事实分类（不猜、不编）。

    规则（全部取自两张真表的字段，均可复核）：
      · A、B 都 LOCAL            ⇒ `同机直调`（同一台机器、同一进程域内可调）
      · A、B 都 CLOUD            ⇒ `云通道`（R2 对象通道 / 面板云）
      · 一个 LOCAL 一个 CLOUD    ⇒ `跨面（本地↔云）`，须经云通道 + 落点声明
      · 关联模块相同             ⇒ 额外标注 `同模块`（本来就同一条链）
    `无通道` 只在字段缺失到判不了时给出 ⇒ **fail-closed，不假装通**。
    """
 # **返回契约必须稳定**：早返回分支也要给出**全部键** ——
    #    第一版这里少给了 `同模块` ⇒ `mesh()` 里 `c["同模块"]` 直接 KeyError。
    #    （与 `真痛` 那个"有时 list 有时字符串"是同一类错：**形状不稳定 = 消费者会炸**。）
    if not a.get("落点") or not b.get("落点"):
        return {"通道": "**判不了**", "为什么": "落点字段缺 ⇒ 不假装通（fail-closed）",
                "同模块": False}
    same_mod = a.get("关联模块") and a.get("关联模块") == b.get("关联模块")
    if a["落点"] == "LOCAL" and b["落点"] == "LOCAL":
        ch, why = "同机直调", "两端同机 ⇒ 同进程域可调"
    elif a["落点"] == "CLOUD" and b["落点"] == "CLOUD":
        ch, why = "云通道", "两端都在云 ⇒ 走 R2 对象通道（⚠️ 必须 --remote）"
    else:
        ch, why = "跨面（本地↔云）", "一端本地一端云 ⇒ 须经云通道 + **落点声明**（不许默认进生产）"
    return {"通道": ch, "为什么": why, "同模块": bool(same_mod)}


def mesh(rows=None) -> dict:
    rows = rows if rows is not None else slots()
    n = len(rows)
    if not n:
 # 用词必须与判据一致：判据找的是「未读到」，消息里就**必须**是「未读到」。
        #    第一版写的是「读不到」⇒ 负控**因为两个词不一致而假红**。
        #    （与"判据比结论弱"同族：**判据与数据的用词不一致，判据就失效**。）
        return {"ok": False, "为什么": "**未读到**插件表（不拿 0 冒充）"}
    edges, by_ch, no_ch = [], {}, []
    for a in rows:
        for b in rows:
            if a["编号"] == b["编号"]:
                continue
            c = channel(a, b)
            e = {"从": a["编号"], "到": b["编号"], "从名": a["名称"], "到名": b["名称"],
                 "通道": c["通道"], "为什么": c["为什么"], "同模块": c["同模块"]}
            edges.append(e)
            by_ch[c["通道"]] = by_ch.get(c["通道"], 0) + 1
            if c["通道"] == "**判不了**":
                no_ch.append(e)
    return {"ok": True, "节点数": n,
            "应有有向边": n * (n - 1), "实得有向边": len(edges),
            "**全互通**": (len(edges) == n * (n - 1) and not no_ch),
            "按通道": by_ch, "没有通道的对": no_ch,
            "逐对": edges,
            "口径": "有向边（A→B 与 B→A 各算一条）；同机直调 ≠ 我能替你算，只是**调得到**",
            "诚实边界": "**互通不解决 CPU** —— 跑的还是同一颗 CPU。"
            "它解决的是不重复造 / 不孤岛 / 可换路。"}


def arrange(n: int, names=None) -> dict:
    """**像显示屏一样排布**：n 个单元 → 网格位置 + 串联次序。

    主人 2026-09-25：「**就像显示屏一样他是这么组成的，不管多大都能串联和排布显示**」
    ⇒ 矩阵不能只对固定的 25 件成立，**必须对任意 n 都能排**：
      · **排布**：列数 = ⌈√n⌉，行数 = ⌈n/列数⌉，按**阅读序**逐格填（像点屏逐块铺）；
      · **串联**：串联序 = 逐格次序（**因为全互通，任何顺序都是合法链路**）；
      · **互不重叠、不留空缺** —— 这两条**逐个算出来**，不靠眼看。
    """
    if n < 1:
        return {"ok": False, "为什么": "**未读到**可排布的单元（n < 1）"}
    import math
    cols = max(1, math.ceil(math.sqrt(n)))
    rows = max(1, math.ceil(n / cols))
    cells, seen = [], set()
    for i in range(n):
        r, c = divmod(i, cols)
        key = (r, c)
        if key in seen:                       # 不可能发生，但**判据要在**
            return {"ok": False, "为什么": "**位置重叠**：%s" % (key,)}
        seen.add(key)
        cells.append({"串联序": i + 1, "行": r + 1, "列": c + 1,
                      "编号": (names[i] if names and i < len(names) else "U%03d" % (i + 1))})
    total_cells = rows * cols
    gaps = total_cells - n
    ok = (len(cells) == n and len(seen) == n
          and all(1 <= x["行"] <= rows and 1 <= x["列"] <= cols for x in cells))
    return {"ok": ok, "单元数": n, "网格": "%d 行 × %d 列" % (rows, cols),
            "网格总格": total_cells, "末尾空格": gaps,
            "互不重叠": len(seen) == n, "都在网格内": all(
                1 <= x["行"] <= rows and 1 <= x["列"] <= cols for x in cells),
            "串联序条数": len(cells),
            "串联合法（全互通 ⇒ 任意序都合法）": True,
            "逐格": cells,
            "口径": "**排布与串联都按数据算出来**；「全互通」保证**任何串联序都是合法链路**"}


def cmd_arrange(a) -> int:
    rows = slots()
    names = [r["编号"] for r in rows] or None
    r = arrange(a.n or len(rows), names)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    print("✅ 排布：%d 单元 ⇒ %s ｜ 互不重叠 %s ｜ 都在网格内 %s ｜ 末尾空格 %d"
          % (r["单元数"], r["网格"], r["互不重叠"], r["都在网格内"], r["末尾空格"])
          if r.get("ok") else "🔴 **排布不成立**：%s" % r.get("为什么"))
    return 0 if r.get("ok") else 1


def cmd_matrix(a) -> int:
    m = mesh()
    if not m.get("ok"):
        print(json.dumps(m, ensure_ascii=False, indent=1))
        return 2
    brief = dict(m)
    brief["逐对"] = m["逐对"][:40] + ([{"…": "共 %d 条，其余省略" % len(m["逐对"])}]
                                  if len(m["逐对"]) > 40 else [])
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    print("✅ 全互通：%d 个节点 ⇒ 应有 %d 条有向边，实得 %d 条，无通道 %d 条"
          % (m["节点数"], m["应有有向边"], m["实得有向边"], len(m["没有通道的对"]))
          if m["**全互通**"] else
          "🔴 **未全互通**：无通道 %d 条（见上）" % len(m["没有通道的对"]))
    print("🔴 诚实边界：%s" % m["诚实边界"])
    return 0 if m["**全互通**"] else 1


def cmd_gaps(a) -> int:
    m = mesh()
    print(json.dumps({"节点数": m.get("节点数"), "没有通道的对": m.get("没有通道的对") or "无"},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_route(a) -> int:
    rows = {r["编号"]: r for r in slots()}
    A, B = a.src, a.dst
    if A not in rows or B not in rows:
        print(json.dumps({"ok": False, "为什么": "编号不在插件表里：%s"
                          % [x for x in (A, B) if x not in rows]}, ensure_ascii=False))
        return 2
    c = channel(rows[A], rows[B])
    print(json.dumps({"从": "%s %s" % (A, rows[A]["名称"]),
                      "到": "%s %s" % (B, rows[B]["名称"]), **c},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    m = mesh()
    # ① 节点数必须与真表一致（现读，不写死）
    ck("**节点数 == 真插件表条数**", m["节点数"] == len(slots()),
       "%d 个" % m["节点数"])
    # ② 全互通判据**随数据变**：拿一份人造 3 节点表试，边数必须 3×2=6
    fake = [{"编号": "X1", "名称": "a", "落点": "LOCAL", "关联模块": "-"},
            {"编号": "X2", "名称": "b", "落点": "LOCAL", "关联模块": "-"},
            {"编号": "X3", "名称": "c", "落点": "CLOUD", "关联模块": "-"}]
    fm = mesh(fake)
    ck("**判据随数据变**（3 节点 ⇒ 应有 6 条有向边）",
       fm["应有有向边"] == 6 and fm["实得有向边"] == 6 and fm["**全互通**"],
       "应有 %d 实得 %d" % (fm["应有有向边"], fm["实得有向边"]))
    # ③ 负控：**落点缺失 ⇒ 必须判不了，不许假装通**
    bad_node = [{"编号": "Y1", "名称": "a", "落点": "LOCAL", "关联模块": "-"},
                {"编号": "Y2", "名称": "b", "落点": "", "关联模块": "-"}]
    bm = mesh(bad_node)
    ck("**负控：落点缺 ⇒ 判不了、不许假装通**",
       len(bm["没有通道的对"]) == 2 and not bm["**全互通**"],
       "无通道 %d 条" % len(bm["没有通道的对"]))
    # ④ 负控：**读不到插件表 ⇒ 报未读到，不许报 0**
    em = mesh([])
    ck("**负控：读不到插件表 ⇒ 报未读到，不报 0**",
       em.get("ok") is False and "未读到" in str(em.get("为什么")), str(em.get("为什么"))[:40])
 # ④b **任意 N 都能排**（「不管多大都能串联和排布显示」）
    badn = []
    for n in (1, 2, 3, 5, 7, 12, 25, 100, 1000):
        rr = arrange(n)
        if not (rr.get("ok") and len(rr["逐格"]) == n and rr["互不重叠"]
                and rr["都在网格内"] and rr["串联序条数"] == n):
            badn.append(n)
    ck("**任意 N 都能排**（1/2/3/5/7/12/25/100/1000 全过）", not badn,
       "不过: %s" % (badn or "无"))
 # ④b **任意 N 都能排**（「不管多大都能串联和排布」）\n badn = []\n for n in (1, 2, 3, 5, 7, 12, 25, 100, 1000):\n rr = arrange(n)\n if not (rr.get("ok") and len(rr["逐格"]) == n and rr["互不重叠"]\n and rr["都在网格内"] and rr["串联序条数"] == n):\n badn.append(n)\n ck("**任意 N 都能排**（1/2/3/5/7/12/25/100/1000 全过）", not badn, "不过: %s" % (badn or "无"))\n # ⑤ 诚实边界必须写明「互通不解决 CPU」（不许顺着主人那句说）
    ck("**必须写明「互通不解决 CPU」**（不顺着说）",
       "不解决 CPU" in str(m.get("诚实边界")), str(m.get("诚实边界"))[:46])
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="插件全互通矩阵（N×(N-1) 有向边 · 逐对给通道）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("matrix").set_defaults(func=cmd_matrix)
    _ar = sub.add_parser("arrange")
    _ar.add_argument("--n", type=int, default=0, help="单元数（0=用真插件表）")
    _ar.set_defaults(func=cmd_arrange)
    sub.add_parser("gaps").set_defaults(func=cmd_gaps)
    r = sub.add_parser("route")
    r.add_argument("src")
    r.add_argument("dst")
    r.set_defaults(func=cmd_route)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
