"""index（可视化面板总索引）⇄ 名册（host.js PANELS）**双向一致**审计器

════════════════════════════════════════════════════════════════════════
它判什么
════════════════════════════════════════════════════════════════════════
`index.html` 是「一屏看全所有可视化面板」的总入口。它的新鲜度就是：
**它索引的面板，与此刻真实名册是否一致**（两个方向都要测）。

  真源 = `plugins/gbt-master/lib/host.js` 的 `PANELS`（宿主插件的唯一名册）。
  正向：名册每条 → 索引里有没有**同路径**的卡片。缺 ⇒ 那块面板**从索引进不去**。
  反向：索引每张卡 → 名册里有没有。多 ⇒ 要么名册漏收，要么索引多了（**要定性**）。

════════════════════════════════════════════════════════════════════════
口径（写死在这里，因为它踩过三次坑）
════════════════════════════════════════════════════════════════════════
① **不用 basename 匹配，用完整相对路径**。
   名册里 `index.html` 一个名字被 **5 条**共用（index/w3/h1/pet/deploy）—— 按 basename 匹配
   时，只要页里链了任意一个 index.html，其余四条**全部假通过**。
   这个坑真的发生过：第 113 轮报「正向 0 缺」，而实际缺了 `pet` 一条。

② **两个方向跑在同一个地址集合上**：都只看 `a.card`。
   曾经正向看「页内任何 href」、反向看「class 在 href 前的 card」——
   两个口径不同 ⇒ 量出来的差**不是读数**，是两个口径的差。
   只看卡片还因为：`a.card` 就是"面板清单"的展示位；非卡片链接是导航 / 卡内子入口
   （如 W3 的窗 E），强行 1:1 对名册只会逼出"要么删有用链接、要么给名册塞假条目"。
   ⇒ 与页子自身的活体对账（`querySelectorAll('a.card')` 读 `GET /gbt-master`）**同一口径**。

③ **属性顺序无关**：逐 `<a ...>` 解析再取 href/class，不用 `class="card"[^>]*href=`
   这种依赖书写顺序的正则。

不判的：文件在不在盘上（索引的意义是**指得着**，不是文件存在）、
自指那条（名册把「总索引」本身也登记为一块面板，而本页不该给自己一张卡 ——
**豁免是声明的，可推翻**）。
本器**只报不一致，不判谁对、不改任何文件**。

用法：`python tools/codex-scripts/index-roster-parity.py`（0 = 一致 · 1 = 有不一致）
"""
import io
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
PAGE = "index.html"

# ── 名册（唯一真源）────────────────────────────────────────────────────
h = io.open(ROOT / "plugins/gbt-master/lib/host.js", encoding="utf-8").read()
i = h.find("const PANELS = [")
blk = h[i:h.find("\n]", i)]
entries = []
for part in re.split(r"\{\s*id:\s*'", blk)[1:]:
    def g(pat):
        return re.search(pat, part, re.S).group(1) if re.search(pat, part, re.S) else ""
    entries.append((g(r"^([^']+)'"), g(r"name:\s*'([^']*)'"), g(r"file:\s*'([^']*)'")))

index_html = (ROOT / PAGE).read_text(encoding="utf-8", errors="replace")


def attr(attrs, name):
    m = re.search(name + r"""\s*=\s*["']([^"']*)["']""", attrs, re.S)
    return m.group(1) if m else ""


def norm(u):
    """规范化 href：去 ./ 前缀、去 #锚点与 ?查询、统一斜杠。"""
    u = u.strip().split("#")[0].split("?")[0]
    u = u.replace("\\", "/")
    while u.startswith("./"):
        u = u[2:]
    return u


# ── 地址集合 A：逐锚点解析（属性顺序无关）────────────────────────────────
anchors = []
for m in re.finditer(r"<a\b([^>]*)>", index_html, re.S):
    a = m.group(1)
    href = attr(a, "href")
    if not href:
        continue
    cls = attr(a, "class").split()
    anchors.append({"href": href, "path": norm(href), "card": "card" in cls,
                    "line": index_html.count("\n", 0, m.start()) + 1})

external = [a for a in anchors if re.match(r"^(https?:|mailto:|javascript:|data:|#)", a["href"])]
local = [a for a in anchors if a not in external]
local_html = [a for a in local if re.search(r"\.html?$", a["path"])]
local_other = [a for a in local if a not in local_html]
cards = [a for a in local_html if a["card"]]
noncard = [a for a in local_html if not a["card"]]

roster_files = [f for _p, _n, f in entries]
roster_set = set(roster_files)

print("=" * 78)
print("index（可视化面板总索引）⇄ 名册（host.js PANELS）· **双向一致**")
print("=" * 78)
print("  真源：host.js PANELS = **%d 条**" % len(entries))
print("  索引：%s · %d 行 · %.1f KB" % (PAGE, index_html.count("\n"), len(index_html) / 1024))
print("  锚点：共 %d 个 → 外部 %d · 本地 %d（.html %d = 卡片 %d + 非卡片 %d · 非 .html %d）"
      % (len(anchors), len(external), len(local), len(local_html),
         len(cards), len(noncard), len(local_other)))
print("  ⚠️ 非 .html 的 %d 个本地锚点（图片 tile 等）与 %d 个非卡片 .html 锚点"
      "**不进判据**，只列出。" % (len(local_other), len(noncard)))
print()

print("  " + "-" * 74)
print("  正向：名册 %d 条 → 索引的**卡片**里有没有同路径的" % len(entries))
print("  " + "-" * 74)
print("  %-7s %-22s %-11s %s" % ("id", "name", "在索引里", "命中的卡片（可复核）"))
missing, selfref = [], []
for pid, name, f in entries:
    if f == PAGE:
        selfref.append((pid, name, f))
        print("  %-7s %-22s %-11s %s" % (pid, name[:20], "⚪ 自指·豁免", "（本页自身：不该给自己一张卡）"))
        continue
    hit = [a for a in cards if a["path"] == f]
    if hit:
        print("  %-7s %-22s %-11s L%d  %s" % (pid, name[:20], "✅ 有卡片", hit[0]["line"], f))
    else:
        missing.append((pid, name, f))
        print("  %-7s %-22s %-11s %s" % (pid, name[:20], "🔴 **无卡片**", f or "—"))

print()
print("  " + "-" * 74)
print("  反向：索引 %d 张卡片 → 名册里有没有" % len(cards))
print("  " + "-" * 74)
extra_card = []
for a in cards:
    if a["path"] in roster_set:
        print("  L%-4d ✅ 名册里有   %s" % (a["line"], a["path"]))
    else:
        extra_card.append(a)
        print("  L%-4d 🔴 **名册里没有** %s" % (a["line"], a["path"]))

print()
print("  " + "-" * 74)
print("  **不进判据**：非卡片的本地 .html 锚点 %d 个（导航 / 卡内子入口）" % len(noncard))
print("  " + "-" * 74)
for a in noncard:
    print("  L%-4d %-52s %s" % (a["line"], a["path"],
                                "（名册里也有）" if a["path"] in roster_set else "（名册外 · 子入口）"))
if not noncard:
    print("  （无）")

print()
print("  " + "-" * 74)
print("  旁证（**不参与判据**）：名册各条指向的文件在不在盘上")
print("  " + "-" * 74)
for pid, name, f in entries:
    p = ROOT / f
    print("  %-7s %-22s %s" % (pid, name[:20],
                               ("在 · %.1f KB" % (p.stat().st_size / 1024)) if p.is_file()
                               else "🔴 盘上不存在"))
gone = [(pid, f) for pid, _n, f in entries if not (ROOT / f).is_file()]

print()
print("=" * 78)
print("正向判读：名册 %d 条（自指 %d 条豁免）→ 索引卡片里找不到 **%d 条**"
      % (len(entries), len(selfref), len(missing)))
for pid, name, f in missing:
    print("  🔴 %-7s %-22s → %s" % (pid, name[:20], f))
print("反向判读：索引 %d 张卡片 → 名册里没有 **%d 张**" % (len(cards), len(extra_card)))
for a in extra_card:
    print("  🔴 L%-4d %s" % (a["line"], a["path"]))
print()
print("  🔴 名册里有、索引无卡片 ⇒ 那块面板**从索引进不去**（「各自面板全部连接上」的一种缺）。")
print("  🔴 索引有卡、名册里没有 ⇒ **要么名册漏收，要么索引多了 —— 是哪一种要定性**。")
print("  ⚠️ 本器**只报不一致，不判谁对、不改任何文件**。")
print("  ⚠️ 也不拿「文件在不在盘上」当一致 —— 索引的意义是**指得着**，不是文件存在。")
print("  ⚠️ 页子自带同一口径的**双向**活体对账（读 GET /gbt-master），两处互为对照；")
print("     差别：页子比的是**现役登记表**（进程加载的那份），本器比的是**源码名册** —— ")
print("     两者若不同（如新增行未重启），本器绿而页子会报「登记表有 N 块面板本页没有卡片」。")
sys.exit(1 if (missing or extra_card or gone) else 0)
