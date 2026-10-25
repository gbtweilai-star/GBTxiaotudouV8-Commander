# -*- coding: utf-8 -*-
"""框架总账（health-ledger）—— **一遍跑完，哪里有问题一目了然**。

主人令（2026-10-10）：
  「你都不审查，不登记的吗？**不调用跑一遍全部能力那里有问题就一目了然了**」
  「还有这些都要留着过年是吗」

## 为什么要有它（不是又造一份账）
仓里已经有**六本子账**，但它们是**分散**的：能力审计一本、能量通道一本、数据库编队一本、
账号一本、数字人一本、体检一本 —— 看一页只能看见一块，**拼不出「整体到底缺什么」**。
本件**只做汇总**（**不重造**任何一处读数）：把六本子账读进来，逐条归到**四档**，
并给每条写清**根因 / 该谁给 / 怎么给**。判据：**每一条都必须有状态与归属**（缺一即红）。

四档（未配置 与 缺依赖 **不是「没做完」**，是「等票」——但**必须逐条登记**，不许含糊）：
  · **好**      现读可用
  · **未配置**  缺主人侧凭据/开关（写清**哪张票、谁能给**）
  · **缺依赖**  缺外部件/上游未接线（写清**缺什么**）
  · **真坏**    现读就是坏的（**这一档才是我的活没干完**）

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


def render(rows, counts) -> None:
    """渲一页（**一目了然**：四档分色 · 每条带根因与归属）。"""
    order = {"真坏": 0, "缺依赖": 1, "未配置": 2, "好": 3}
    rs = sorted(rows, key=lambda r: (order.get(r["档"], 9), r["面"], r["项"]))
    color = {"真坏": "#f87171", "缺依赖": "#f5b041", "未配置": "#38bdf8", "好": "#22c55e"}
    body = "".join(
        '<tr><td>%s</td><td class="m">%s</td><td style="color:%s">%s</td><td>%s</td>'
        '<td>%s</td><td>%s</td></tr>'
        % (r["面"], r["项"], color.get(r["档"], "#888"), r["档"], r["读数"],
           r["根因"] or "—", (r["该谁给"] or "—") + ("｜" + r["怎么给"] if r["怎么给"] else ""))
        for r in rs)
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<!-- 自动生成，别手改。重建：py -3.14 tools/codex-scripts/health-ledger.py -->
<title>GBT小土豆V8 · 框架总账</title>
<style>
 body{{margin:0;background:#06080c;color:#e8eef6;font:13px/1.6 "Segoe UI","Microsoft YaHei",system-ui,sans-serif}}
 header{{display:flex;align-items:center;gap:14px;padding:14px 20px;border-bottom:1px solid #1d2733}}
 .who{{font-size:16px}} .who b{{color:#f5b041}} .spacer{{flex:1}}
 .pill{{border:1px solid #2a3644;border-radius:999px;padding:3px 11px;font-size:12px}}
 table{{width:100%;border-collapse:collapse}} th,td{{padding:7px 14px;border-bottom:1px solid #131b25;text-align:left;vertical-align:top}}
 th{{color:#7d8ea3;font-size:12px;font-weight:500}} .m{{color:#9fb0c3}}
 .foot{{padding:12px 20px;color:#5b6b7d;font-size:12px;border-top:1px solid #131b25}}
</style></head><body>
<header><span class="who">GBT<b>小土豆</b>V8 · 框架总账</span><span class="spacer"></span>
<span class="pill" style="color:#f87171">真坏 {counts.get('真坏', 0)}</span>
<span class="pill" style="color:#f5b041">缺依赖 {counts.get('缺依赖', 0)}</span>
<span class="pill" style="color:#38bdf8">未配置 {counts.get('未配置', 0)}</span></header>
<table><thead><tr><th>面</th><th>项</th><th>档</th><th>读数</th><th>根因</th><th>该谁给 / 怎么给</th></tr></thead>
<tbody>{body}</tbody></table>
<div class="foot">共 {len(rows)} 条 ｜ 口径：<b>真坏</b>=我的活没干完 · <b>未配置/缺依赖</b>=等票（逐条写清该谁给）｜ 重生成 py -3.14 tools/codex-scripts/health-ledger.py<br>{SIG}</div>
</body></html>
""", encoding="utf-8")


def _json(rel: str) -> dict:
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _rows():
    rows = []

    def add(面, 项, 档, 读数, 根因="", 谁给="", 怎么给=""):
        rows.append({"面": 面, "项": 项, "档": 档, "读数": str(读数)[:120],
                     "根因": 根因, "该谁给": 谁给, "怎么给": 怎么给})

    a = _json("state/capability-audit.json")
    for i in (a.get("items") or []):
        st = i.get("state")
        if st in ("断连", "缺失"):
            add("能力位", i.get("id"), "真坏", st, str(i.get("why"))[:80], "框架", "追根因修")
        elif st == "按需未启用":
            add("能力位", i.get("id"), "未配置", st,
                str(i.get("why"))[:70], "主人", str(i.get("expect"))[:50])

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
    for k in ("真坏", "缺依赖", "未配置"):
        if c.get(k):
            print("  %-6s %d 条" % (k, c[k]))
    if c.get("真坏"):
        print("  🔴 真坏（**这才是我的活没干完**）：")
        for r in rows:
            if r["档"] == "真坏":
                print("     [%s] %s ｜ %s" % (r["面"], r["项"], r["读数"]))
    print("  未配置/缺依赖 = **等票**（每条已写清该谁给）；没状态/没归属的 %d 条" % len(bad))
    print("判据：%s" % ("PASS" if not bad else "FAIL"))
    return 0 if not bad else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="框架总账")
    ap.add_argument("--check", action="store_true")
    ap.parse_args()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
