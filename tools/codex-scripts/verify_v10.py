# -*- coding: utf-8 -*-
"""V10 交付前自检：项目树进上帝视角（按 DSH 官方规格核对）。"""
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
CANVAS = BASE / "V10 GBT小土豆V8-无限画布.html"
PROTO = BASE / "V10 GBT小土豆V8-可交互原型.html"
fails, warns, oks = [], [], []


def ok(m):
    oks.append(m)
    print("  PASS  " + m)


def bad(m):
    fails.append(m)
    print("  FAIL  " + m)


def warn(m):
    warns.append(m)
    print("  WARN  " + m)


print("=" * 78)
print("V10 交付前自检 · 项目树进上帝视角")
print("=" * 78)

print("\n[1] 文件 / 版本 / 归档")
for p in (CANVAS, PROTO):
    (ok if p.exists() else bad)("%s · %d B" % (p.name, len(p.read_bytes()) if p.exists() else 0))
(ok if re.search(r"V10 ", CANVAS.name) and re.search(r"V10 ", PROTO.name) else bad)("版本一致（V10）")
arch = sorted(x.name for x in (BASE / "archive").glob("V* GBT*"))
(ok if len(arch) == 18 else bad)("archive/ 历史 %d 份（V1-V9 各 2）" % len(arch))
(ok if not list(BASE.glob("V[1-9] *.html")) else bad)("根目录只留活跃版本")

print("\n[2] JS 语法")
for p in (CANVAS, PROTO):
    t = p.read_text(encoding="utf-8")
    js = t[t.rindex("<script>") + 8:t.rindex("</script>")]
    f = BASE / ".scratch" / ("_v10chk_%s.js" % ("canvas" if p is CANVAS else "proto"))
    f.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    (ok if r.returncode == 0 else bad)("%s 语法（%d 字符）%s" % (p.name, len(js), (r.stderr or '').strip()[:140]))

ptext = PROTO.read_text(encoding="utf-8")
ctext = CANVAS.read_text(encoding="utf-8")

print("\n[3] 核对：项目树确实进了上帝视角")
m = re.search(r"const V10 = /\* full snapshot \+ plugin market \+ project tree \*/(\{.*?\});\n", ptext, re.S)
if not m:
    bad("未注入项目树数据")
    TR = None
else:
    TR = json.loads(m.group(1))["tree"]
    T, SP = TR["tree"], TR["spec"]
    (ok if "function treeCard" in ptext else bad)("实现 treeCard()")
    god_i = ptext.index("function renderGod")
    god_seg = ptext[god_i:ptext.index("function drawNet", god_i)]
    (ok if "treeCard()" in god_seg else bad)("treeCard() 被 renderGod 调用（在上帝视角内，非独立面板）")
    (ok if "'项目树'" in god_seg or "项目树" in god_seg else bad)("上帝视角内含「项目树」标题")
    nav_seg = ptext[ptext.index("var NAV = ["):ptext.index("var st = {")]
    (ok if "'tree'" not in nav_seg else warn)("未新增导航项（按指令留在上帝视角内）")

print("\n[4] 树数据真读数")
if TR:
    (ok if T["count"] == 70 and len(T["entries"]) == 40 else bad)(
        "根层 %d/%d 项（应 40/70）" % (len(T["entries"]), T["count"]))
    (ok if T["truncated"] else bad)("根层标 truncated=%s（应 True）" % T["truncated"])
    (ok if len(TR["preexpanded"]) >= 3 else bad)("预展开目录 %d 个" % len(TR["preexpanded"]))
    kinds = set()

    def walk(es):
        for e in es:
            kinds.add(e["kind"])
            if e.get("entries"):
                walk(e["entries"])
    walk(T["entries"])
    (ok if kinds <= {"directory", "file", "other"} else bad)("条目类型仅三态：%s" % sorted(kinds))
    names = [e["name"] for e in T["entries"]]
    (ok if any(n.startswith(".") for n in names) else bad)("dotfiles 与普通条目同列（如 .git/.scratch）")
    dirs_first = [e["kind"] for e in T["entries"]]
    (ok if dirs_first == sorted(dirs_first, key=lambda k: 0 if k == "directory" else 1) else bad)("目录优先排序")
    files = [e for e in T["entries"] if e["kind"] == "file"]
    (ok if files and files[0].get("bytes") is not None else warn)("文件条目带字节数")
    expanded = [e for e in T["entries"] if e.get("entries")]
    (ok if expanded else bad)("存在已展开层（%d 个）" % len(expanded))

print("\n[5] 规格一致性（逐条对照官方 README）")
if TR:
    (ok if "workspaceFiles.list" in ptext else bad)("标注真实接口 workspaceFiles.list(sessionId, path)")
    (ok if "WorkspaceDirectoryListing" in ptext or "DirectoryListing" in ptext else bad)("标注返回结构 DirectoryListing")
    (ok if "目录优先" in ptext else bad)("规格：目录优先 → 自然序不分大小写")
    (ok if "dotfiles" in ptext else bad)("规格：dotfiles 与其他条目一样显示")
    (ok if "other" in ptext and "aria-disabled" in ptext else bad)("规格：other 灰显不可点（aria-disabled）")
    (ok if "maxEntries" in ptext else bad)("规格：maxEntries 上限")
    (ok if "truncated" in ptext else bad)("规格：truncated 标记")
    (ok if "此目录为空" in ptext else bad)("规格：空层如实说明")
    (ok if "workspace-file/" in ptext else bad)("规格：失败按错误码展示")
    (ok if "只有一个根" in ptext else bad)("规格：已知限制（只有一个根）")
    (ok if "无搜索" in ptext else bad)("规格：已知限制（只有列目录）")
    (ok if "重新读取" in ptext else bad)("规格：标题行右端重新读取控件")
    (ok if SP["limits"]["maxEntries_spec"] == 2000 else bad)("规格默认 maxEntries=2000 记录在案")
    (ok if SP["readonly"] else bad)("规格：本服务不提供修改操作")

print("\n[6] 交互")
(ok if "data-tree" in ptext and "data-kind" in ptext else bad)("树行带 data-tree / data-kind")
(ok if "aria-expanded" in ptext and "treeBody" in ptext else bad)("目录展开态 + treeBody 容器")
(ok if "treeReload" in ptext else bad)("重新读取按钮已接线")
(ok if "treeHuman" in ptext else bad)("文件大小人性化显示")

print("\n[7] 面板与画布")
n_panel = len(re.findall(r"function panel[A-Z]\w+\(", ptext))
(ok if n_panel == 20 else bad)("面板函数 %d 个（应仍为 20，未新增导航项）" % n_panel)
for k in ("01 项目背景", "02 设计系统", "03 设计稿"):
    (ok if k in ctext else bad)("画布标注「%s」" % k)
pages = re.findall(r"\['[^']+',\s*p\d+\(\)\]", ctext)
(ok if len(pages) >= 21 else bad)("Row 3 页面 %d 个" % len(pages))
(ok if "上帝视角 · 项目树" in ctext else bad)("画布含「上帝视角 · 项目树」")
(ok if "workspaceFiles / 项目树 / entries 出现 0 次" in ctext or "出现 0 次" in ctext else warn)("画布记录了核对结论")

print("\n[8] 反 slop")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")
for p in (CANVAS, PROTO):
    hits = EMOJI.findall(p.read_text(encoding="utf-8"))
    (ok if not hits else warn)("%s emoji %s" % (p.name, set(hits) if hits else "无"))
(ok if "lorem ipsum" not in (ptext + ctext).lower() else bad)("无 lorem ipsum")
(ok if len(PROTO.read_bytes()) / 1024 < 800 else warn)("原型 %.0f KB" % (len(PROTO.read_bytes()) / 1024))

print("\n[9] 结果")
print("  PASS %d · WARN %d · FAIL %d" % (len(oks), len(warns), len(fails)))
for f in fails:
    print("   - " + f)
sys.exit(1 if fails else 0)
