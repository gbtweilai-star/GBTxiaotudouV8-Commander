# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 免费数据库编队 —— 生成器 / 判据 / 开通清单。

主人令（2026-10-07，逐字）：
    「在以设计云插件的方式部署上最大内存和最稳定的免费数据库插件，
      也一样排布好对应使用的指向，备注好都是存的什么东西。」

## 这件干什么

1. 读**单一真源** `deploy/cloud-10/db-fleet.json`（7 个免费库：选型、额度、稳定性依据、指向、存什么）；
2. `render`：把真源烘成页面数据件（经典脚本，页面走 file:// 读不了 json，同窗 E/F/G 的做法）；
3. `check`：判据（含负对照）；
4. `needs`：逐个库打印**开通清单**（缺什么、谁有权给、环境变量名）。

## 口径纪律（钉死，别放宽）

- 🔴 **这些库一个都还没开通**。`check` 里有一条专门钉死：任何 `status` 出现「已部署 / 已连通 / 已验证」
  一律判红 —— 设计不是部署，拿设计当部署是本仓最恨的假绿。
- 额度与稳定性**必须带出处**（`quota_source` / `stability.来源` 指向 `sources[]` 里的 id）；
  官网没列的字段留 `null`，不许补数。
- 页面的「未开通」不是灰头土脸的占位 —— 它是**真读数**：真源的 status 就是它。

用法：
    py -3.14 tools/codex-scripts/db-fleet.py render
    py -3.14 tools/codex-scripts/db-fleet.py check
    py -3.14 tools/codex-scripts/db-fleet.py needs

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "deploy" / "cloud-10" / "db-fleet.json"
PAGE_DIR = ROOT / "holo_pet_w3" / "db-fleet"
DATA_JS = PAGE_DIR / "db-fleet-data.js"
PAGE = PAGE_DIR / "index.html"
TZ = timezone(timedelta(hours=8))

# 措辞纪律：这些词只许出现在"禁止"的语境里；status 里出现即判红
FORBIDDEN_STATUS = ("已部署", "已连通", "已验证", "deployed", "connected", "verified")


def now_iso() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


def load() -> dict:
    return json.loads(SRC.read_text(encoding="utf-8"))


# ────────────────────────────── render ──────────────────────────────
def cmd_render(_args) -> int:
    d = load()
    data = {
        "generated_at": now_iso(),
        "regen": "py -3.14 tools/codex-scripts/db-fleet.py render",
        "check": "py -3.14 tools/codex-scripts/db-fleet.py check",
        "source": "deploy/cloud-10/db-fleet.json（单一真源）",
        "honesty": d.get("honesty") or [],
        "pointers": d.get("pointers") or {},
        "conventions": d.get("conventions") or {},
        "sources": d.get("sources") or [],
        "fleet": d.get("fleet") or [],
        "totals": {
            "库": len(d.get("fleet") or []),
            "主": len([x for x in (d.get("fleet") or []) if x.get("rank") == "主"]),
            "备": len([x for x in (d.get("fleet") or []) if x.get("rank") != "主"]),
            "指向": len(((d.get("pointers") or {}).get("map")) or []),
            "未开通": len([x for x in (d.get("fleet") or []) if x.get("status") == "未开通"]),
        },
    }
    PAGE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_JS.write_text(
        "/* GBT小土豆V8 · 数据库编队数据件 —— **生成产物**，由 db-fleet.py render 覆盖，不许手改。\n"
        " * 重生成：%s\n"
        " * 口径：一切来自 deploy/cloud-10/db-fleet.json；额度与稳定性逐条带出处。 */\n"
        "window.GBT_DB_FLEET = %s;\n" % (data["regen"], json.dumps(data, ensure_ascii=False, indent=1)),
        encoding="utf-8")
    t = data["totals"]
    print("已生成：%s" % DATA_JS)
    print("  %d 个库（主 %d · 备 %d）· %d 条指向 · 未开通 %d"
          % (t["库"], t["主"], t["备"], t["指向"], t["未开通"]))
    return 0


# ────────────────────────────── needs ──────────────────────────────
def cmd_needs(_args) -> int:
    d = load()
    print("=" * 82)
    print("开通清单 · 每个免费库要真接上，缺什么、谁有权给")
    print("=" * 82)
    for x in d.get("fleet") or []:
        n = x.get("needs") or {}
        print("\n▸ %s（%s · %s · %s）" % (x.get("id"), x.get("provider"), x.get("engine"), x.get("role")))
        print("    环境变量：%s" % x.get("apiKeyEnv"))
        print("    缺什么：%s" % n.get("缺什么"))
        print("    谁有权给：%s" % n.get("谁有权给"))
        print("    开通后：%s" % n.get("开通后要做什么"))
    print("\n" + "-" * 82)
    print("🔴 凭据一律进环境变量，**不写进仓内任何文件**（与 ~/.dsh 的凭据 seam 同一口径）。")
    print("🔴 在凭据到位之前，本编队的每一条 status 都只能是「未开通」——不许先写成「已部署」。")
    return 0


# ────────────────────────────── check ──────────────────────────────
def _page_selfcontained(text: str) -> list:
    """页面自包含判据：注释里的出处 URL 不算引用。"""
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    hits = [t for t in ("http://", "https://", "fetch(", "XMLHttpRequest", "eval(",
                        "new Function", "<iframe", 'type="module"')
            if t in body]
    return hits


def cmd_check(_args) -> int:
    out = []

    def add(cid, ok, detail):
        out.append((cid, ok, detail))

    try:
        d = load()
        parsed = True
    except Exception as exc:                                          # noqa: BLE001
        d, parsed = {}, False
        add("D1", False, "真源解析失败：%s" % exc)

    fleet = (d.get("fleet") or []) if parsed else []
    srcs = {s.get("id") for s in (d.get("sources") or [])} if parsed else set()

    if parsed:
        missing = [x.get("id") for x in fleet
                   if not all(str(x.get(k) or "").strip()
                              for k in ("id", "provider", "engine", "role", "stores"))]
        add("D1", bool(fleet) and not missing,
            "真源可解析 · %d 个库，id/provider/engine/role/stores 有空缺的：%s" % (len(fleet), missing or "无"))

        # 指向表：每个 write_to / read_from 必须对得上编队里的 id
        ids = {x.get("id") for x in fleet}
        bad_ptr = []
        for p in ((d.get("pointers") or {}).get("map") or []):
            w = p.get("write_to")
            if w not in ids:
                bad_ptr.append("%s -> %s（写主不在编队里）" % (p.get("data"), w))
            for r in (p.get("read_from") or []):
                if r not in ids:
                    bad_ptr.append("%s -> %s（读源不在编队里）" % (p.get("data"), r))
        add("D2", bool((d.get("pointers") or {}).get("map")) and not bad_ptr,
            "指向表逐条对得上编队 id（对不上的：%s）" % (bad_ptr or "无"))

        no_src = []
        for x in fleet:
            qs = x.get("quota_source")
            st = (x.get("stability") or {}).get("来源")
            for tag in (qs, st):
                if tag not in srcs:
                    no_src.append("%s 引用了不存在的出处 %s" % (x.get("id"), tag))
        add("D3", not no_src, "额度与稳定性都带出处、且出处都在 sources[] 里（问题：%s）" % (no_src or "无"))

 # 状态纪律：设计不是部署
        dirty = ["%s=%s" % (x.get("id"), x.get("status")) for x in fleet
                 if any(w in str(x.get("status")) for w in FORBIDDEN_STATUS)]
        add("D4", not dirty, "status 里没有「已部署/已连通/已验证」这类假绿（命中：%s）" % (dirty or "无"))

        # 负对照一：把某条 status 改成「已部署」，D4 **必须**报红
        fake = json.loads(json.dumps(d))
        if fake.get("fleet"):
            fake["fleet"][0]["status"] = "已部署"
            dirty2 = [x for x in fake["fleet"]
                      if any(w in str(x.get("status")) for w in FORBIDDEN_STATUS)]
            add("N1", bool(dirty2), "负对照：status 写「已部署」必须被判红 —— %s"
                % ("报了红 ✅" if dirty2 else "**竟然放绿 ❌**"))
        else:
            add("N1", False, "负对照跑不了：编队是空的")

        # 负对照二：把指向改成一个不存在的库，D2 **必须**报红
        fake2 = json.loads(json.dumps(d))
        m = ((fake2.get("pointers") or {}).get("map")) or []
        if m:
            m[0]["write_to"] = "db-does-not-exist"
            ids2 = {x.get("id") for x in fake2.get("fleet") or []}
            bad2 = [p for p in m if p.get("write_to") not in ids2]
            add("N2", bool(bad2), "负对照：指向不存在的库必须被判红 —— %s"
                % ("报了红 ✅" if bad2 else "**竟然放绿 ❌**"))
        else:
            add("N2", False, "负对照跑不了：没有指向表")
    else:
        for cid in ("D1", "D2", "D3", "D4", "N1", "N2"):
            if cid not in [o[0] for o in out]:
                add(cid, False, "真源不可解析 ⇒ 判不了（不猜）")

    # 页面与数据件
    if PAGE.exists():
        add("D5", not _page_selfcontained(PAGE.read_text(encoding="utf-8", errors="replace")),
            "页面自包含（外链/取数口命中：%s）"
            % (_page_selfcontained(PAGE.read_text(encoding="utf-8", errors="replace")) or "无"))
    else:
        add("D5", False, "页面 holo_pet_w3/db-fleet/index.html 不存在")

    fresh = False
    why = "数据件不存在（先跑 render）"
    if DATA_JS.exists() and parsed:
        try:
            data = json.loads(DATA_JS.read_text(encoding="utf-8").split("=", 1)[1].rstrip().rstrip(";"))
            same_n = len(data.get("fleet") or []) == len(fleet)
            fresh = same_n and bool(fleet)
            why = ("数据件 %d 条 vs 真源 %d 条 · 生成于 %s"
                   % (len(data.get("fleet") or []), len(fleet), data.get("generated_at")))
        except Exception as exc:                                      # noqa: BLE001
            why = "数据件读不动：%s" % exc
    add("D6", fresh, "数据件与真源条数一致 —— " + why)

    print("=" * 82)
    print("数据库编队 · 判据")
    print("=" * 82)
    for cid, ok, detail in out:
        print("  %s %-3s %s" % ("✅" if ok else "❌", cid, detail))
    passed = sum(1 for _c, o, _d in out if o)
    print("-" * 82)
    print("  PASS %d · FAIL %d（共 %d 条）" % (passed, len(out) - passed, len(out)))
    if passed != len(out):
        print("  ⚠️ 有判据没过 —— 别宣称这份编队可用")
    return 0 if passed == len(out) else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="GBT小土豆V8 · 免费数据库编队（生成 / 判据 / 开通清单）")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("render", help="生成页面数据件").set_defaults(func=cmd_render)
    sub.add_parser("check", help="判据（含负对照）").set_defaults(func=cmd_check)
    sub.add_parser("needs", help="打印开通清单（缺什么、谁有权给）").set_defaults(func=cmd_needs)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
