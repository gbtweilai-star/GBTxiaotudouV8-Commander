# -*- coding: utf-8 -*-
"""框架总账（health-ledger）—— **一遍跑完，哪里有问题一目了然**。

主人令（2026-10-10）：
  「你都不审查，不登记的吗？**不调用跑一遍全部能力那里有问题就一目了然了**」
  「还有这些都要留着过年是吗」

## 为什么要有它（不是又造一份账）
仓里已经有**六本子账**，但它们是**分散**的：能力审计一本、能量通道一本、数据库编队一本、
账号一本、数字人一本、体检一本 —— 看一页只能看见一块，**拼不出「整体到底缺什么」**。
本件**只做汇总**（**不重造**任何一处读数）：把六本子账读进来，逐条归到**五档**，
并给每条写清**根因 / 该谁给 / 怎么给**。判据：**每一条都必须有状态与归属**（缺一即红）。

五档（未配置 与 缺依赖 **不是「没做完」**，是「等票」——但**必须逐条登记**，不许含糊）：
  · **好**      现读可用
  · **未配置**  缺主人侧凭据/开关（写清**哪张票、谁能给**）
  · **缺依赖**  缺外部件/上游未接线（写清**缺什么**）
  · **不适用**  已归档 / 已退役 —— **明确不需要**，既不是「好」也不是「欠账」（2026-10-26 排查新增）
  · **真坏**    现读就是坏的（**这一档才是我的活没干完**）

🔴 为什么要有「不适用」这一档（2026-10-26 深度排查抓到，真缺陷）：
  子账里 `按需未启用` 这个读数**混着两种东西**：① 缺主人侧票；② 页面已归档/窗已 retired。
  旧代码一律记「未配置 · 该谁给=主人」⇒ 账上出现「根因：已作废不审计（明确不需要）」
  却「该谁给：主人」的自相矛盾行，还把 2 条**根本不需要处理**的算进黄色欠账。
  账本的作用是"告诉主人还欠什么"，**把不需要的东西记成欠账，就是让账本失真**。
  判据用源头结构化信号（`probe.probed === False` 且带 `retired`/`archived`），
  **不解析中文 why 文本** —— 解析措辞的判据会随文案漂。

用法：py -3.14 -X utf8 tools/codex-scripts/health-ledger.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "health-ledger.json"
PAGE = ROOT / "holo_pet_w3" / "health-ledger" / "index.html"
SIG = "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"

# 界面/注释里不许出现 emoji（2026-10-26 主人令）。范围：本件产出的**页面与台账**。
# 终端打印不在此列 —— 本仓判据记号（红圈/对勾）在命令行里是通用语言，守卫自己也这么打。
sys.path.insert(0, str(Path(__file__).resolve().parent))
# 审美令牌（内联版）：唯一实现在 `_taste_inline.py`，别在这里再抄一份。
from _taste_inline import site_root_block  # noqa: E402
# 页面文本卫生（emoji / markdown 记号 / None）：唯一实现在 `_page_text.py`。
# 2026-10-26 收编：原来本件自带一份 `_EMOJI` + `_c`，而 ai-board.py 与 capability-audit.py
# 各有一份同样漏的（一个没洗、一个只洗了 emoji）—— 三份判断，正是本仓付过代价的那种事。
from _page_text import clean as _c  # noqa: E402
# 页面落盘的唯一出口（清洗 markdown 记号后再写盘）。唯一判定在 page-text-scan.py。
from _page_emit import clean_html  # noqa: E402

# 五档 → 本仓的语义令牌（**这是一次真融合，不是换色**）：
#   真坏 = negative（红）｜缺依赖 = warning（金）｜未配置 = unknown（紫，本仓特有的"未探测"）｜
#   不适用 = muted（灰，"明确不需要"——**既不是通也不是欠账**，所以不给语义色）｜
#   好   = positive（青，本仓「接上=青」，**不跟库的绿**）。
# 原来的第四档是天空蓝 #38bdf8 —— 在本仓语义里它什么都不是（既不是"通"也不是"未探测"），
# 现在归到 unknown：**未配置 = 还没探/还没给票**，正是 unknown 的定义。
#
# 兜底值一律写**令牌真值**，不许写"改之前那个颜色"（2026-10-26 主人当场抓的）：
#   写成 `var(--taste-unknown,#7c4dff)` 的后果是 —— 令牌表在时是紫、令牌表不在时是天蓝，
#   **一个状态两种颜色**，而且天蓝是我们四色之外的第四色。这正撞本仓审美方向 avoid 里的
#   「给同一个状态配两种颜色（或引第四色）」。兜底的意义是"表没了也还是我们定的样子"，
#   不是"表没了就退回改之前"。
_COLOR = {"真坏": "var(--taste-negative,#EF4444)",
          "缺依赖": "var(--taste-warning,#F5B041)",
          "未配置": "var(--taste-unknown,#7C4DFF)",
          "不适用": "var(--taste-muted,#9aa4c4)",
          "好": "var(--taste-positive,#00E5FF)"}


def render(rows, counts) -> None:
    """渲一页（**一目了然**：五档分色 · 每条带根因与归属）。"""
    order = {"真坏": 0, "缺依赖": 1, "未配置": 2, "不适用": 3, "好": 4}
    rs = sorted(rows, key=lambda r: (order.get(r["档"], 9), r["面"], r["项"]))
    color = _COLOR
    body = "".join(
        '<tr><td>%s</td><td class="m">%s</td><td style="color:%s">%s</td><td>%s</td>'
        '<td>%s</td><td>%s</td></tr>'
        % (r["面"], r["项"], color.get(r["档"], "#888"), r["档"], r["读数"],
           r["根因"] or "—", (r["该谁给"] or "—") + ("｜" + r["怎么给"] if r["怎么给"] else ""))
        for r in rs)
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    _page = f"""<!doctype html>
<html data-page-id="health-ledger" lang="zh-CN"><head><meta charset="utf-8">
<!-- 自动生成，别手改。重建：py -3.14 tools/codex-scripts/health-ledger.py -->
<title>GBT小土豆V8 · 框架总账</title>
<style>
{site_root_block()}
 body{{margin:0;background:var(--taste-ground,#0B1120);color:var(--taste-text,#e8ecf8);font:13px/1.6 "Segoe UI","Microsoft YaHei",system-ui,sans-serif}}
 header{{display:flex;align-items:center;gap:14px;padding:14px 20px;border-bottom:1px solid var(--taste-border,#1E3A5F)}}
 .who{{font-size:16px}} .who b{{color:var(--taste-accent,#f5b041)}} .spacer{{flex:1}}
 .pill{{border:1px solid var(--taste-border,#1E3A5F);border-radius:999px;padding:3px 11px;font-size:12px}}
 table{{width:100%;border-collapse:collapse}} th,td{{padding:7px 14px;border-bottom:1px solid var(--taste-rule,#162035);text-align:left;vertical-align:top}}
 th{{color:var(--taste-muted,#9aa4c4);font-size:12px;font-weight:500}} .m{{color:var(--taste-muted,#9aa4c4)}}
 /* 「面」「档」两列不许折行（2026-10-26 排查抓到）：列一窄就把「缺依赖」竖排成三行
    「缺/依/赖」—— 这页的用途是"一目了然"，竖排三个字正好反过来。 */
 td:nth-child(1),td:nth-child(3),th:nth-child(1),th:nth-child(3){{white-space:nowrap}}
 .foot{{padding:12px 20px;color:var(--taste-faint,#6b7280);font-size:12px;border-top:1px solid var(--taste-rule,#162035)}}
</style></head><body>
<header><span class="who">GBT<b>小土豆</b>V8 · 框架总账</span><span class="spacer"></span>
<span class="pill" style="color:{_COLOR['真坏']}">真坏 {counts.get('真坏', 0)}</span>
<span class="pill" style="color:{_COLOR['缺依赖']}">缺依赖 {counts.get('缺依赖', 0)}</span>
<span class="pill" style="color:{_COLOR['未配置']}">未配置 {counts.get('未配置', 0)}</span>
<span class="pill" style="color:{_COLOR['不适用']}">不适用 {counts.get('不适用', 0)}</span></header>
<table><thead><tr><th>面</th><th>项</th><th>档</th><th>读数</th><th>根因</th><th>该谁给 / 怎么给</th></tr></thead>
<tbody>{body}</tbody></table>
<div class="foot">共 {len(rows)} 条 ｜ 口径：<b>真坏</b>=我的活没干完 · <b>未配置/缺依赖</b>=等票（逐条写清该谁给） · <b>不适用</b>=已归档/已退役，<b>明确不需要，不算欠账</b>（该谁给写「—」）｜ 重生成 py -3.14 tools/codex-scripts/health-ledger.py<br>{SIG}</div>
<script src="../shell/tentacle-kit.js" defer></script>
</body></html>
    """
    # 页面落盘走唯一出口（2026-10-27）：出口会清掉漏到界面上的 markdown 记号。
    # 为什么不在产物上洗：只清产物 = 下次重生成又漂回来（`test_pages_no_emoji` ③ 的注释原话）。
    PAGE.write_text(clean_html(_page), encoding="utf-8")


def _json(rel: str) -> dict:
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _rows():
    rows = []

    def add(面, 项, 档, 读数, 根因="", 谁给="", 怎么给=""):
        """**入账即清洗**（2026-10-26 主人令：界面/注释一律不留 emoji）。

        为什么在这里清而不是渲染时清：本页六个字段全是从别的台账**原样搬来**的
        （能力审计的读数里就带 ❌/✅ 记号）。在 add() 清一次，台账 JSON 与页面同时干净，
        两边口径不会分叉（渲染层再清一遍就成了"两处判断"，正是本仓最贵的教训）。

        2026-10-26 排查补一条：源头的 `evidence` 里带 markdown 粗体记号（`**按需未启用**`），
        旧写法原样搬 ⇒ 界面上直接印出两个星号。**源台账是 markdown、这页是 HTML**，
        搬运时得把记号去掉，不能指望读者把 `**` 当强调看。反引号同理（2026-10-26 二次排查
        实测本页还有 5 处 `` `…` ``），两条已一起收进 `_page_text.clean()`。
        """
        rows.append({"面": _c(面), "项": _c(项),
                     "档": 档, "读数": _c(读数, 120),
                     "根因": _c(根因), "该谁给": _c(谁给),
                     "怎么给": _c(怎么给)})

    a = _json("state/capability-audit.json")
    for i in (a.get("items") or []):
        st = i.get("state")
        pr = i.get("probe") or {}
        # 🔴 根因取不到时别印 "None"（2026-10-26 排查抓到）：5 条本地服务的 `why` 是 null，
        #    旧写法 `str(i.get("why"))[:70]` 把字面 "None" 记进账本，而真实原因
        #    （"HTTP 502 / 目标计算机积极拒绝 / 按需未启用"）一直躺在 `evidence` 里。
        why = str(i.get("why") or "").strip()
        if not why or why == "None":
            ev = str(i.get("evidence") or "").strip()
            segs = [s.strip() for s in ev.split("｜") if s.strip()]
            # 取「按需未启用」那一段 —— 真正的失败读数（HTTP 502 / 目标计算机积极拒绝）在末尾，
            # 直接 [:70] 截 evidence 会停在「登记出处：…」这种无关的半句上。
            pick = next((s for s in segs if "按需未启用" in s), None)
            why = pick or (segs[-1] if segs else ev)
        if st in ("断连", "缺失"):
            add("能力位", i.get("id"), "真坏", st, why[:80], "框架", "追根因修")
        elif st == "按需未启用":
            # 🔴 第五档「不适用」（2026-10-26 排查抓到）：`按需未启用` 这一个读数里
            #    混着两种完全不同的东西 ——
            #      ① 缺主人侧凭据/开关（等票）⇒ 未配置；
            #      ② 页面已归档 / 窗已 retired（**明确不需要**）⇒ 不适用。
            #    旧代码把它们一律记成「未配置 · 该谁给=主人」，于是账本上出现
            #    "根因：已作废不审计（明确不需要）" 却 "该谁给：主人" 的自相矛盾行，
            #    还把那 2 条算进黄色欠账里 ⇒ 主人会去追一件不需要追的事。
            #    判据用**源头结构化信号**（probe.probed === False 且带 retired/archived），
            #    不去解析中文 why 文本（解析措辞＝判据会随文案漂）。
            na = (pr.get("probed") is False
                  and (pr.get("retired") or pr.get("archived")))
            if na:
                add("能力位", i.get("id"), "不适用", "明确不需要", why[:80],
                    "—", "无需处理（已归档/已退役，不算能力断连）")
            else:
                add("能力位", i.get("id"), "未配置", st,
                    why[:70], "主人", str(i.get("expect"))[:50])

    sw = _json("state/caps-sweep-20261009.json")
    for k, r in (sw.get("逐位") or {}).items():
        v = (r or {}).get("verdict")
        if v == "真坏":
            add("能力扫描", k, "真坏", v, str((r or {}).get("reason"))[:80], "框架", "追根因修")
        elif v == "缺依赖":
            add("能力扫描", k, "缺依赖", v, str((r or {}).get("reason"))[:80], "上游/主人", "补依赖")

    try:
        t = (ROOT / "holo_pet_w3" / "energy" / "energy-data.js").read_text(encoding="utf-8", errors="replace")
        m = re.search(r"globalThis[.]GBT_ENERGY = (\{.*?\});", t, re.S)
        if m:
            e = json.loads(m.group(1))
            for r in (e.get("providers") or e.get("rows") or []):
                st = str(r.get("可用") or r.get("state") or "")
                if "未声明" in st or "missing" in st or "禁" in st:
                    add("能量通道", r.get("provider"), "未配置", st,
                        str(r.get("why") or "密钥/开关未就位")[:70], "主人",
                        "给该 provider 的 key 或改用别的通道")
    except (OSError, ValueError):
        pass

    d = _json("deploy/cloud-10/db-fleet.json")
    for r in (d.get("rows") or d.get("fleet") or []):
        st = str(r.get("status") or "")
        if "未开通" in st or r.get("opened") is False:
            add("数据库编队", r.get("id") or r.get("name"), "未配置", st,
                "云侧库还没开通（免费档有闲置暂停/额度限制）", "主人", "开通或改用本地库")

    try:
        import subprocess as _sp
        cp = _sp.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / "digihuman" / "pipeline.py"),
                      "status"], capture_output=True, cwd=str(ROOT), timeout=300)
        for line in (cp.stdout or b"").decode("utf-8", "replace").splitlines():
            if line.strip().startswith(chr(10060)):
                add("数字人", line.strip()[2:].strip().split(" ")[0], "缺依赖",
                    line.strip()[:80], "该阶段产物未生成", "框架/主人", "见 pipeline.py map")
    except Exception:                                        # noqa: BLE001
        pass

    ck = _json("state/checkup-last.json")
    for name, rc in ((ck.get("逐条 rc") or {})).items():
        if rc:
            add("体检闸", name, "真坏", "rc=%s" % rc, "体检里这道闸没过", "框架", "追根因修")
    return rows


def check() -> int:
    from collections import Counter
    rows = _rows()
    c = Counter(r["档"] for r in rows)
    bad = [r for r in rows if not r["档"] or not r["该谁给"]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
                               "总条": len(rows), "分档": dict(c), "逐条": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    render(rows, dict(c))
    print("   已渲一页：%s" % PAGE.relative_to(ROOT))
    print("框架总账：%d 条" % len(rows))
    for k in ("真坏", "缺依赖", "未配置", "不适用"):
        if c.get(k):
            print("  %-6s %d 条" % (k, c[k]))
    if c.get("真坏"):
        print("  🔴 真坏（**这才是我的活没干完**）：")
        for r in rows:
            if r["档"] == "真坏":
                print("     [%s] %s ｜ %s" % (r["面"], r["项"], r["读数"]))
    print("  未配置/缺依赖 = **等票**（每条已写清该谁给）；"
          "不适用 = **明确不需要，不算欠账**；没状态/没归属的 %d 条" % len(bad))
    print("判据：%s" % ("PASS" if not bad else "FAIL"))
    return 0 if not bad else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="框架总账")
    ap.add_argument("--check", action="store_true")
    ap.parse_args()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
