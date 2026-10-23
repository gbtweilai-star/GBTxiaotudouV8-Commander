#!/usr/bin/env python
# gbt-capability: none
"""bp-apply-patches.py —— 把 `补丁集.md` 里的 F1~F7 真正施加到一份**工作副本**上，供编译验证。

为什么要写成可执行脚本，而不是手工照抄补丁
--------------------------------------------
因为**这次排雷一路抓到的就是"静默什么都不做"**：
参数被静默丢弃、`e.click()` 报成功、散文串被当成真调用…
⇒ 补丁也一样：`str.replace()` 没命中就**悄无声息**，读的人以为改了。
**所以本脚本每一条替换都必须断言命中**（命中 0 次 ⇒ 当场报错退出）。

产出
----
* `.scratch/bp-verify/src.orig/`     —— 原始 19 个文件（从 app-sources.json 还原）
* `.scratch/bp-verify/src.patched/`  —— 施加补丁后的同一批文件
* 屏幕：每个文件命中了哪几条补丁

用法
----
    python tools/codex-scripts/bp-apply-patches.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "output" / "blueprint-audit" / "app-sources.json"
OUT = ROOT / ".scratch" / "bp-verify"


# ── F6：5 个文件补 export default（补丁集 §F6）─────────────────────────────
F6 = {
    "/src/components/RichTextEditor.tsx": "RichTextEditor",
    "/src/components/DataGrid.tsx": "DataGrid",
    "/src/components/CodeEditorWidget.tsx": "CodeEditorWidget",
    "/src/components/ChartDashboard.tsx": "ChartDashboard",
    "/src/components/KanbanBoard.tsx": "KanbanBoard",
}


def sub_once(text: str, old: str, new: str, label: str, hits: list) -> str:
    """**必须命中**的替换：命中 0 次或多次都报错 —— 不许静默。"""
    n = text.count(old)
    if n != 1:
        raise SystemExit("❌ 补丁 %s 没命中（出现 %d 次，应为 1 次）\n   要找的原文：\n%s"
                         % (label, n, old[:300]))
    hits.append(label)
    return text.replace(old, new, 1)


def apply(name: str, code: str) -> tuple:
    hits = []

    # ── F6 ──────────────────────────────────────────────────────────────
    if name in F6:
        comp = F6[name]
        if "export default" in code:
            raise SystemExit("❌ F6：%s 已经有 export，补丁前提不成立（读数变了，先复核）" % name)
        code = code.rstrip() + "\n\nexport default %s;\n" % comp
        hits.append("F6 补 export default %s" % comp)

    # ── F7：RichTextEditor 的 contentEditable + dangerouslySetInnerHTML ──
    if name == "/src/components/RichTextEditor.tsx":
        # ⚠️ 实测踩到（正是本脚本"断言命中"要抓的东西）：
        #    真实 L26 是 `'      <div '` —— **带一个尾随空格**。
        #    我第一版补丁写的是 `'      <div\n'`（无空格）⇒ 命中 0 次 ⇒ 断言当场报错。
        #    一个尾随空格就能让"字面补丁"静默失效；若没有断言，读的人会以为已经改了。
        old = ("      <div \n"
               "        contentEditable\n"
               "        className=\"min-h-[200px] p-4 outline-none prose prose-sm\"\n"
               "        style={{ fontWeight: isBold ? 'bold' : 'normal', fontStyle: isItalic ? 'italic' : 'normal' }}\n"
               "        dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(content) }}\n"
               "      />")
        new = ("      <div\n"
               "        contentEditable\n"
               "        suppressContentEditableWarning\n"
               "        className=\"min-h-[200px] p-4 outline-none prose prose-sm\"\n"
               "        style={{ fontWeight: isBold ? 'bold' : 'normal', fontStyle: isItalic ? 'italic' : 'normal' }}\n"
               "        onInput={(e) => setContent((e.target as HTMLDivElement).innerHTML)}\n"
               "      >\n"
               "        {content}\n"
               "      </div>")
        code = sub_once(code, old, new, "F7 去危险路径 + 受控 contentEditable", hits)

    # ── F2：Dashboard 挂 ChartDashboard ─────────────────────────────────
    if name == "/src/pages/Dashboard.tsx":
        code = sub_once(
            code,
            "import DashboardStats from '../components/DashboardStats';",
            "import DashboardStats from '../components/DashboardStats';\n"
            "import ChartDashboard from '../components/ChartDashboard';",
            "F2 加 import ChartDashboard", hits)
        code = sub_once(
            code,
            "          <DashboardStats />\n          {/* Other dashboard components */}",
            "          <DashboardStats />\n          <ChartDashboard />",
            "F2 挂载 ChartDashboard", hits)

    # ── F4 + F1：Sidebar ────────────────────────────────────────────────
    if name == "/src/components/Sidebar.tsx":
        code = sub_once(
            code,
            '<h1 className="text-xl font-bold">Dashboard</h1>',
            '<h1 className="text-xl font-bold">GBT小土豆V8</h1>',
            "F4 侧栏标题去重（Dashboard → 品牌名）", hits)
        for label in ("Overview", "Analytics", "Settings"):
            old = ('<a href="#" className="flex items-center p-2 rounded-lg text-foreground hover:bg-brand/5">\n'
                   "              %s\n"
                   "            </a>" % label)
            new = ('<span className="flex items-center p-2 rounded-lg text-foreground/60 cursor-default">\n'
                   "              %s\n"
                   "            </span>" % label)
            code = sub_once(code, old, new, "F1 死链改非链接（%s）" % label, hits)

    # ── F3：标注示例数据 ────────────────────────────────────────────────
    if name == "/src/components/DashboardStats.tsx":
        code = sub_once(
            code,
            "const stats = [",
            "// ⚠️ 示例数据（未接接口）—— 数值为占位，不代表真实指标\nconst stats = [",
            "F3 标注示例数据", hits)

    return code, hits


def main() -> int:
    if not SRC.exists():
        print("找不到", SRC, file=sys.stderr)
        return 2
    data = json.loads(SRC.read_text(encoding="utf-8"))
    files = data.get("files") or []

    (OUT / "src.orig").mkdir(parents=True, exist_ok=True)
    (OUT / "src.patched").mkdir(parents=True, exist_ok=True)

    total_hits = 0
    touched = 0
    for f in files:
        name = next((a.split("=", 1)[1] for a in f.get("attrs") or []
                     if a.startswith("data-src-path=")), None)
        if not name:
            continue
        rel = name.lstrip("/")
        code = f.get("content") or ""
        (OUT / "src.orig" / rel.replace("/", "__")).write_text(code, encoding="utf-8")
        patched, hits = apply(name, code)
        (OUT / "src.patched" / rel.replace("/", "__")).write_text(patched, encoding="utf-8")
        if hits:
            touched += 1
            total_hits += len(hits)
            print("  %-42s 命中 %d 条" % (name, len(hits)))
            for h in hits:
                print("        · %s" % h)

    print()
    print("施加完毕：%d 个文件被改，共 %d 条补丁；原件与补丁件都已写到 %s"
          % (touched, total_hits, OUT.relative_to(ROOT)))
    print("（每一条替换都断言过命中：命中数 != 1 会当场退出 —— 不许静默什么都不做）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
