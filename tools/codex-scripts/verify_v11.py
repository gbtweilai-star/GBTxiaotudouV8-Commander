# -*- coding: utf-8 -*-
"""V11 交付校验：契约 + 静态口径 + 数据自洽。只读，不改文件。"""
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
PROTO = BASE / "V11 GBT小土豆V8-可交互原型.html"
CANVAS = BASE / "V11 GBT小土豆V8-无限画布.html"
SIG = "开发者：自由的风"

R = []


def chk(name, ok, detail=""):
    R.append((bool(ok), name, detail))


p = PROTO.read_text(encoding="utf-8")
c = CANVAS.read_text(encoding="utf-8")
man = json.loads((S / "v11_manifest.json").read_text(encoding="utf-8"))
scan = json.loads((S / "dsh_register_scan.json").read_text(encoding="utf-8"))

# ── 1. 交付契约 ──
chk("两文件都在且非空", PROTO.stat().st_size > 100_000 and CANVAS.stat().st_size > 80_000,
    "原型 %.1f KB · 画布 %.1f KB" % (PROTO.stat().st_size / 1024, CANVAS.stat().st_size / 1024))
actives = sorted(x.name for x in BASE.glob("V*.html"))
chk("根目录只有 V11 两件成品", all(x.startswith("V11 ") for x in actives), " · ".join(actives))
arc = sorted(x.name for x in (BASE / "archive").glob("*.html"))
chk("归档 V1~V10 各两件（20 件）", len(arc) == 20, "%d 件" % len(arc))
chk("归档无重名", len(set(arc)) == len(arc), "")
chk("原型带署名", SIG in p and "不可删除" in p, "")
chk("画布带署名", SIG in c and "不可删除" in c, "")

# ── 2. 版本一致性 ──
chk("原型标题为 V11", "可交互原型 V11" in p, "")
chk("画布标题为 V11", "无限画布 V11" in c, "")
chk("无 V10 残留标识", not re.search(r"\bV10\b", p), "")

# ── 3. Craft 红线 ──
AI_INDIGO = ["#6366f1", "#818cf8", "#a5b4fc", "#4f46e5", "#8b5cf6", "#7c3aed"]
hit = [h for h in AI_INDIGO if h in p.lower() or h in c.lower()]
chk("无 AI 靛蓝", not hit, "命中 " + ", ".join(hit) if hit else "")
lorem = re.findall(r"lorem ipsum|Lorem Ipsum|此处填写|TODO|待补充|xxx", p)
chk("无占位文案", not lorem, "命中 %d" % len(lorem))
emoji = re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", p)
chk("无 emoji 作 UI 元素", not emoji, "命中 " + "".join(sorted(set(emoji))[:8]) if emoji else "")

# ── 4. 对比度（WCAG 2.2 AA ≥ 4.5:1） ──


def lum(hexc):
    hexc = hexc.lstrip("#")
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def f(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


BG_DARK, BG_LIGHT = "#04070f", "#f6f7f8"
pairs = [
    ("原型 主文本", "#dff2fb", BG_DARK), ("原型 副文本", "#b8cfda", BG_DARK),
    ("原型 三级文本", "#8fa9b8", BG_DARK), ("原型 强调青", "#2ad4f0", BG_DARK),
    ("画布 主文本", "#dff2fb", BG_DARK), ("画布 副文本", "#a9c4d2", BG_DARK),
    ("画布 亮色主文本", "#141a20", BG_LIGHT),
]
worst = None
for n, fg, bg in pairs:
    rr = ratio(fg, bg)
    ok = rr >= 4.5
    if worst is None or rr < worst[0]:
        worst = (rr, n)
    chk("对比度 " + n, ok, "%.2f:1" % rr)

# ── 5. 数据自洽 ──
d = man["dsh"]
chk("席位口径自洽", d["n_implemented"] + d["n_missing"] == d["n_slots_real"],
    "已实现 %d + 缺口 %d = 界面席位 %d" % (d["n_implemented"], d["n_missing"], d["n_slots_real"]))
chk("应用席位全部未实现（已计入总数）",
    all(a["slot"] not in {x["slot"] for x in d["implemented"]} for a in d["apps"]),
    "%d 个应用席位" % d["n_slots_app"])
chk("席位总数 = 界面 + 应用", d["n_slots_real"] + d["n_slots_app"] == d["n_total"],
    "%d + %d = %d" % (d["n_slots_real"], d["n_slots_app"], d["n_total"]))
real_reg = set()
for pk, info in scan.items():
    real_reg.update(info.get("registered_slots", {}))
all_man = set(d["slots_real"]) | set(d["slots_app"])
chk("席位 id 全部来自真实注册（无编造）", all_man <= real_reg,
    "编造 %d 个" % len(all_man - real_reg))
chk("缺口席位都有注册方", all(d["slot_owner"].get(s) for s in d["missing"]), "")
chk("已实现席位不重复", len({x["slot"] for x in d["implemented"]}) == d["n_implemented"], "")
chk("家族席位并集 = 全部界面席位",
    set().union(*[set(f["slots"]) for f in d["families"]]) == set(d["slots_real"]), "")
chk("插件包数 ≥ 有席位的包数", d["client_with_slots"] <= d["client_total"],
    "%d ≤ %d" % (d["client_with_slots"], d["client_total"]))

# ── 6. 结构 ──
_i = p.index("var NAV = [")
_j = p.index("];", _i)
nav_entries = re.findall(r"\['[^']+', '[a-z0-9]+'", p[_i:_j])
dispatch = re.findall(r"if \(st\.nav === '[a-z0-9]+'\) return panel", p)
chk("原型 30 个导航项", len(nav_entries) == 30 and len(dispatch) == 30,
    "NAV %d 条 · 分发 %d 条" % (len(nav_entries), len(dispatch)))
chk("导航无重键", len({x.split("'")[3] for x in nav_entries}) == 30, "")
chk("画布 33 页", len(re.findall(r"\['[^']+', p\d+\(\)\],", c)) == 33,
    "%d 页" % len(re.findall(r"\['[^']+', p\d+\(\)\],", c)))
chk("画布 p1~p33 齐", all(("function p%d(" % i) in c for i in range(1, 34)), "")
chk("原型无 undefined 字面量", "undefined" not in re.sub(r"//[^\n]*", "", p.split("const V11 = ")[1]), "（数据层已解析，见运行期校验）")

# ── 输出 ──
ok = sum(1 for r in R if r[0])
print("=" * 78)
print("V11 交付校验 · %d 项" % len(R))
print("=" * 78)
for good, name, detail in R:
    print("  %s %-34s %s" % ("✓" if good else "✗", name, detail))
print("-" * 78)
print("通过 %d · 失败 %d" % (ok, len(R) - ok))
print("最低对比度：%.2f:1（%s）" % worst)
print("席位：界面 %d + 应用 %d = %d · 已实现 %d · 缺口 %d"
      % (d["n_slots_real"], d["n_slots_app"], d["n_total"], d["n_implemented"], d["n_missing"]))
sys.exit(0 if ok == len(R) else 1)
