# -*- coding: utf-8 -*-
"""V3（HUD）交付前自检。"""
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
CANVAS = BASE / "V3 GBT小土豆V8-无限画布.html"
PROTO = BASE / "V3 GBT小土豆V8-可交互原型.html"
TMP = BASE / ".scratch"
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


def script_of(t):
    return t[t.rindex("<script>") + 8:t.rindex("</script>")]


print("=" * 76)
print("V3 HUD 交付前自检")
print("=" * 76)

print("\n[1] 文件 / 版本 / 归档")
for p in (CANVAS, PROTO):
    (ok if p.exists() else bad)("%s · %d B" % (p.name, len(p.read_bytes()) if p.exists() else 0))
ok("两文件版本号一致（V3）") if re.search(r"V3 ", CANVAS.name) and re.search(r"V3 ", PROTO.name) else bad("版本不一致")
for v in ("V1", "V2"):
    n = len(list((BASE / "archive").glob(v + " GBT*")))
    (ok if n == 2 else bad)("archive/ %s 快照 %d/2" % (v, n))

print("\n[2] JS 语法（node --check）")
for p in (CANVAS, PROTO):
    js = script_of(p.read_text(encoding="utf-8"))
    f = TMP / ("_v3_%s.js" % ("canvas" if p is CANVAS else "proto"))
    f.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    (ok if r.returncode == 0 else bad)("%s 语法（%d 字符）%s" % (p.name, len(js), (r.stderr or '').strip()[:160]))

print("\n[3] 真实数据层")
ptext = PROTO.read_text(encoding="utf-8")
m = re.search(r"const HUD = /\* real scan snapshot \*/(\{.*?\});\n", ptext, re.S)
if not m:
    bad("未注入真实读数")
    H = None
else:
    H = json.loads(m.group(1))
    M = H["meta"]
    ok("在册 %d（可执行 %d + 禁用 %d）· 域 %d" % (M["total"], M["executable"], M["disabled"], M["domains"]))
    ok("真实读数：路由 %s/%s · 接线 %s/%s · 模块 %s · 体检 %s"
       % (M["routed"], M["registered"], M["wired"], M["audit_total"], M["modules_checked"], M["verdict"]))
    tot = sum(r["total"] for r in H["radar"])
    (ok if tot == M["executable"] and len(H["radar"]) == 6 else bad)(
        "雷达六维覆盖 %d 项（应 == 可执行 %d）" % (tot, M["executable"]))
    doms = set()
    for r in H["radar"]:
        doms |= set(r["domains"])
    (ok if len(doms) == M["domains"] else bad)("六维划分域 %d 个（应 == %d，不重不漏）" % (len(doms), M["domains"]))
    ok("通道 %d 条：%s" % (len(H["channels"]),
                       " / ".join("%s %s/%s" % (c["name"], c["num"], c["den"]) for c in H["channels"])))
    ok("真实故障 %d 条 · 缺口 %d 项" % (len(H["faults"]), M["gap_count"]))
    rt = H["runtime"]
    ok("本机实时读数：内存 %d%% · CPU %d%% · 存储 %d 文件" % (rt["mem_load"], rt["cpu_pct"], rt["store_json"]))

print("\n[4] 无限画布三层")
ctext = CANVAS.read_text(encoding="utf-8")
for k in ("01 项目背景", "02 设计系统", "03 设计稿"):
    (ok if k in ctext else bad)("标注「%s」" % k)
for q in ("是什么", "给谁用", "解决什么问题"):
    (ok if q in ctext else bad)("Row 1 回答「%s」" % q)
pages = re.findall(r"\['[^']+',\s*p\d\(\)\]", ctext)
(ok if len(pages) >= 6 else bad)("Row 3 页面 %d 个 + 引导线" % len(pages))

print("\n[5] HUD 令牌一致性")
for tok in ("#04070f", "#08111f", "#0c1a2e", "#2ad4f0", "#6ef2ff", "#dff2fb", "#3ddc97", "#f5b544", "#ff7a7a"):
    if tok not in ptext:
        bad("原型缺 token %s" % tok)
ok("原型九个 HUD token 齐备")
for tok in ("#2ad4f0", "#04070f"):
    (ok if tok in ctext else bad)("画布含 HUD token %s" % tok)
(ok if "#c89b6c" not in ptext else warn)("V2 的暖琥珀已完全换出") if "#c89b6c" not in ptext else warn("仍残留 V2 琥珀色")

print("\n[6] 原型硬性要求")
(ok if re.search(r"max-width|clamp\(|@media", ptext) else bad)("响应式兜底存在")
(ok if not re.search(r"width:\s*390px", ptext) else warn)("未写死 390px 外轮廓")
for bp in ("max-width:1279px", "max-width:1023px", "max-width:767px"):
    (ok if bp in ptext else bad)("断点 %s" % bp)
clicks = len(re.findall(r"addEventListener\('click'", ptext))
(ok if clicks >= 2 else bad)("可点击绑定 %d 处" % clicks)
(ok if "aria-pressed" in ptext and "aria-expanded" in ptext else bad)("状态切换（筛选 aria-pressed + 故障展开 aria-expanded）")
for s in ("loading", "empty", "error"):
    (ok if s in ptext else warn)("三态文案 %s" % s)
for a in ("focus-visible", "aria-label", "aria-current", "role=\"img\"", "aria-modal"):
    (ok if a in ptext else warn)("无障碍 %s" % a)
(ok if "prefers-reduced-motion" in ptext else warn)("尊重减少动效偏好")

print("\n[7] 对比度（WCAG 2.2 AA ≥4.5:1）")


def lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def lum(t):
    return 0.2126 * lin(t[0]) + 0.7152 * lin(t[1]) + 0.0722 * lin(t[2])


def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def over(a, fg, bg):
    return tuple(a * fg[i] + (1 - a) * bg[i] for i in range(3))


BG = (0x08, 0x11, 0x1F)
INK = (0xDF, 0xF2, 0xFB)
for name, fg, bg in [
    ("正文 #dff2fb", INK, BG),
    ("二级 0.74", over(.74, INK, BG), BG),
    ("三级 0.54", over(.54, INK, BG), BG),
    ("霓虹 #2ad4f0", (0x2A, 0xD4, 0xF0), BG),
    ("霓虹亮 #6ef2ff", (0x6E, 0xF2, 0xFF), BG),
    ("正常 #3ddc97", (0x3D, 0xDC, 0x97), BG),
    ("警告 #f5b544", (0xF5, 0xB5, 0x44), BG),
    ("异常 #ff7a7a", (0xFF, 0x7A, 0x7A), BG),
    ("主按钮字 #6ef2ff", (0x6E, 0xF2, 0xFF), over(.10, (0x2A, 0xD4, 0xF0), BG)),
]:
    r = ratio(fg, bg)
    (ok if r >= 4.5 else bad)("%s → %.2f:1" % (name, r))

print("\n[8] 反 AI-slop / 真实性")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")
for p in (CANVAS, PROTO):
    t = p.read_text(encoding="utf-8")
    hits = EMOJI.findall(t)
    (ok if not hits else bad)("%s emoji %s" % (p.name, set(hits) if hits else "无"))
for tok in ("#6366f1", "#8b5cf6", "#7c3aed", "#a855f7"):
    if tok in ptext or tok in ctext:
        bad("AI 默认靛紫 %s" % tok)
ok("无 AI 默认靛紫")
(ok if "lorem ipsum" not in (ptext + ctext).lower() else bad)("无 lorem ipsum")
if H:
    if "程序化占位" in ptext or "程序化全息" in ptext:
        ok("中央形象明确标注为程序化占位（不冒充人像）")
    else:
        bad("中央形象未标注占位属性")
    if re.search(r">\s*(身高|体重|年龄)\s*<", ptext) or "'身高'" in ptext:
        bad("出现编造的人体数据（身高/体重/年龄）")
    else:
        ok("无编造的人体数据")
    if all(("'" + s + "'") in ptext for s in ("loading", "empty", "error", "list")):
        ok("故障区四态齐备（加载 / 空 / 错误 / 正常）")
    else:
        bad("故障区状态不齐")

print("\n[9] 结果")
print("  PASS %d · WARN %d · FAIL %d" % (len(oks), len(warns), len(fails)))
for f in fails:
    print("   - " + f)
sys.exit(1 if fails else 0)
