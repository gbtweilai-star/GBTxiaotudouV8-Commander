#!/usr/bin/env python
# gbt-capability: none
"""bp-app-scan.py —— 对已抽取的 projectaal App 源码做「未完成形态」机检。

数据来源：`output/blueprint-audit/app-sources.json`
（由 `bp-js.py` 把预览 srcdoc 里 18 个 `<script type="text/plain">` 源文件整体抽出）

为什么要有这个
--------------
主人令：**「全方位无死角的看到所有故障问题以及疑是故障的全部都不能放过」**、
**「哪些地方还没完善」**。
靠人逐个文件读会漏、会随心情。把「没完善」拆成**可机检的形态**，逐文件扫，
命中就报，并给出判据 —— 人只看结论、复核证据。

判据（每条都写明"为什么它算未完成"）
------------------------------------
U1  TODO/FIXME/XXX/HACK           —— 作者自己标注的未完成
U2  占位文案                      —— placeholder / lorem / 「示例」「待填」「coming soon」
U3  空实现                        —— `return null` / 空函数体 `{}` / 只 console.log
U4  死链                          —— `href="#"`（点了只改 URL，不跳转）
U5  声明了却没挂载                —— 文件存在、但没有任何 import 引用它（死代码）
U6  硬编码样例数据                —— 组件里写死的 const 数组（真实产品应来自接口）
U7  注释掉的内容缺口              —— 形如 `{/* Other ... */}` 的「这里还该有别的东西」
U8  占位型可视元素                —— 空的 `<div/>` 撑位、`<img src="">`

用法
----
    python tools/codex-scripts/bp-app-scan.py            # 打印
    python tools/codex-scripts/bp-app-scan.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "output" / "blueprint-audit" / "app-sources.json"

RULES = [
    ("U1", "TODO/FIXME/XXX/HACK", re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")),
    # ⚠️ 自纠（2026-09-25 首轮实测）：本规则原来写成 `placeholder|...`，
    #    于是把**正常的 HTML 输入框属性** `placeholder="you@example.com"` 也报成"占位文案"
    #    （首轮 3 处命中全是这类噪声）。**`placeholder=` 是 HTML 属性，不是未完成内容。**
    #    ⇒ 只保留"内容型占位"的措辞，并显式排除 `placeholder=` 属性形态。
    ("U2", "占位文案（内容型）",
     re.compile(r"lorem|待填|敬请期待|coming soon|placeholder text|TBD|占位符", re.I)),
    # ⚠️ 自纠（同上）：原来含 `return\s+null\s*;`，把 `if (!isAuthenticated) return null;`
    #    这种**正当守卫**报成"空实现"。⇒ 去掉裸 `return null`，只留真正空的函数体。
    ("U3", "空实现", re.compile(r"=>\s*\{\s*\}|onClick=\{\(\)\s*=>\s*\{\s*\}\}|function\s+\w+\s*\([^)]*\)\s*\{\s*\}")),
    ("U4", "死链 href=\"#\"", re.compile(r'href\s*=\s*"#"')),
    ("U6", "硬编码样例数据", re.compile(r"^const\s+\w+\s*=\s*\[", re.M)),
    ("U7", "注释掉的内容缺口", re.compile(r"\{\s*/\*\s*(Other|TODO|Add|更多|其余)", re.I)),
    ("U8", "占位型可视元素", re.compile(r"<img\s+src\s*=\s*\{\s*[\"']{2}\s*\}|<div\s*/>")),
]

# U9 / U10：需要跨行判断，不走单行正则（在 scan_file 里单独做）
#
# U9 · 组件无导出（第 5 轮新增，实测）：文件里定义了组件函数，但**没有任何 export**
#      ⇒ 别人 `import X from …` 拿到的是 `undefined`，渲染即抛错。
#      **这不是"没接上"，是"接不上"** —— 两种处置完全不同（补导出 vs 挂载）。
#
# U10 · 用到未 import 的外部符号（第 5 轮新增，实测）：
#      注意 **`React` 不算** —— 本预览用 UMD 把 React 挂在全局（unpkg react.development.js），
#      所以"零 import 却用 React.useState"是**合法的**，不许当缺陷报。
#      只查下面这张**明确不在全局**的第三方清单。
_NOT_GLOBAL_PKGS = ("DOMPurify", "axios", "clsx", "lucide", "recharts", "d3")

# 组件是否被别的文件 import（U5 用）
IMPORT_RE = re.compile(r"""from\s+['"]([^'"]+)['"]""")


def scan_file(name: str, code: str, imported_by: set) -> list:
    hits = []
    lines = code.splitlines()
    for rid, label, pat in RULES:
        for i, ln in enumerate(lines, 1):
            if pat.search(ln):
                hits.append({"rule": rid, "why": label, "line": i,
                             "text": ln.strip()[:130]})
    # U5：没被任何文件 import 的组件
    if name.endswith(".tsx") and not name.endswith("App.tsx"):
        base = name.split("/")[-1].replace(".tsx", "")
        if base not in imported_by:
            hits.append({"rule": "U5", "why": "无人 import（死代码）", "line": 0, "text": name})

    # U9：定义了组件却没有任何 export ⇒ 别人 import 到的是 undefined（**接不上，不是没接**）
    if name.endswith(".tsx") and not name.endswith("App.tsx"):
        has_export = bool(re.search(r"export\s+default\b", code)
                          or re.search(r"export\s+(?:const|function|class)\b", code)
                          or re.search(r"export\s*\{", code))
        if not has_export:
            hits.append({"rule": "U9", "why": "无任何 export（import 到 undefined）",
                         "line": len(lines), "text": "文件末尾缺 `export default <组件>;`"})

    # U10：用到未 import、且**确定不在全局**的第三方符号
    imports_all = " ".join(IMPORT_RE.findall(code)) + " " + " ".join(
        re.findall(r"import\s+([^;]+?)\s+from", code))
    for pk in _NOT_GLOBAL_PKGS:
        if re.search(r"\b" + re.escape(pk) + r"\b", code) and pk not in imports_all:
            ln = next((i for i, line in enumerate(lines, 1) if re.search(r"\b" + re.escape(pk) + r"\b", line)), 0)
            hits.append({"rule": "U10", "why": "用到未 import 的外部符号（会抛 ReferenceError）",
                         "line": ln, "text": pk})
    return hits


def _reachable(files: list) -> set:
    """从 `/src/App.tsx` 出发做传递可达（按 import 路径末段匹配文件名）。

    为什么必须分这一层：**"死链"发生在可达组件里**（用户点得到 ⇒ 真故障）与
    **发生在本来就没人 import 的死码里**（用户碰不到 ⇒ 只是清理项）
    是两种完全不同的严重度。不分开就是拿数量充战况。
    """
    by_base = {}
    for f in files:
        p = next((a.split("=", 1)[1] for a in f.get("attrs") or []
                  if a.startswith("data-src-path=")), "")
        if p:
            by_base[p.split("/")[-1].replace(".tsx", "").replace(".ts", "")] = p
    seen, queue = set(), ["App"]
    while queue:
        cur = queue.pop()
        for f in files:
            p = next((a.split("=", 1)[1] for a in f.get("attrs") or []
                      if a.startswith("data-src-path=")), "")
            if p.split("/")[-1].replace(".tsx", "").replace(".ts", "") != cur:
                continue
            if p in seen:
                continue
            seen.add(p)
            for m in IMPORT_RE.findall(f.get("content") or ""):
                b = m.split("/")[-1].replace(".tsx", "").replace(".ts", "")
                if b in by_base and by_base[b] not in seen:
                    queue.append(b)
    return seen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    if not SRC.exists():
        print("找不到 %s —— 先用 bp-js.py 抽一次源码。" % SRC, file=sys.stderr)
        return 2
    data = json.loads(SRC.read_text(encoding="utf-8"))
    files = data.get("files") or []

    # 收集所有被 import 的模块名（去掉路径前缀，只看 ./xxx 的末段）
    imported = set()
    for f in files:
        for m in IMPORT_RE.findall(f.get("content") or ""):
            imported.add(m.split("/")[-1].replace(".tsx", "").replace(".ts", ""))

    print("扫描 %d 个源文件（数据源 %s）" % (len(files), SRC.name))
    reach = _reachable(files)
    print("从 /src/App.tsx 传递可达的文件：%d 个 —— %s" % (len(reach), sorted(reach)))
    print()
    all_rows = []
    total = 0
    live_total = 0
    for f in files:
        name = next((a.split("=", 1)[1] for a in f.get("attrs") or []
                     if a.startswith("data-src-path=")), "?")
        is_live = name in reach
        hits = scan_file(name, f.get("content") or "", imported)
        if hits:
            total += len(hits)
            if is_live:
                live_total += len(hits)
        print("%-42s %5d 字  %s  未完成命中 %d" %
              (name, f.get("len") or 0, "[可达]" if is_live else "[死码]", len(hits)))
        for h in hits:
            print("      [%s] L%-4s %-22s %s" % (h["rule"], h["line"], h["why"], h["text"]))
        all_rows.append({"file": name, "len": f.get("len"), "reachable": is_live, "hits": hits})

    print()
    print("=== 合计 %d 处；其中发生在【可达组件】里的 %d 处（用户点得到 = 真故障面）==="
          % (total, live_total))
    by_rule = {}
    for r in all_rows:
        for h in r["hits"]:
            by_rule[h["rule"]] = by_rule.get(h["rule"], 0) + 1
    for rid, label, _ in RULES:
        print("   %s %-22s %d" % (rid, label, by_rule.get(rid, 0)))
    print("   U5 %-22s %d" % ("无人 import（死代码）", by_rule.get("U5", 0)))
    print("   U9 %-22s %d" % ("无任何 export（接不上）", by_rule.get("U9", 0)))
    print("   U10 %-21s %d" % ("未 import 的外部符号", by_rule.get("U10", 0)))
    _sum = sum(by_rule.get(r, 0) for r in
               [x[0] for x in RULES] + ["U5", "U9", "U10"])
    print("   ---- 分类合计 %d（应与上面的总数一致；对不上就是漏计）" % _sum)

    if args.json:
        Path(args.json).write_text(json.dumps(all_rows, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        print()
        print("已写", args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
