# -*- coding: utf-8 -*-
"""V5 交付前自检：七块真面板 + 大脑执行层五维实测 + 零留位。"""
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
CANVAS = BASE / "V5 GBT小土豆V8-无限画布.html"
PROTO = BASE / "V5 GBT小土豆V8-可交互原型.html"
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


print("=" * 78)
print("V5 交付前自检 · 七块真面板 + 大脑执行层")
print("=" * 78)

print("\n[1] 文件 / 版本 / 归档")
for p in (CANVAS, PROTO):
    (ok if p.exists() else bad)("%s · %d B" % (p.name, len(p.read_bytes()) if p.exists() else 0))
(ok if re.search(r"V5 ", CANVAS.name) and re.search(r"V5 ", PROTO.name) else bad)("版本一致（V5）")
arch = sorted(x.name for x in (BASE / "archive").glob("V* GBT*"))
(ok if len(arch) == 8 else bad)("archive/ 历史版本 %d 份（V1-V4 各 2）" % len(arch))
(ok if not list(BASE.glob("V[1-4] *.html")) else bad)("根目录只留活跃版本")

print("\n[2] JS 语法")
for p in (CANVAS, PROTO):
    js = script_of(p.read_text(encoding="utf-8"))
    f = BASE / ".scratch" / ("_v5_%s.js" % ("canvas" if p is CANVAS else "proto"))
    f.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    (ok if r.returncode == 0 else bad)("%s 语法（%d 字符）%s" % (p.name, len(js), (r.stderr or '').strip()[:140]))

ptext = PROTO.read_text(encoding="utf-8")
ctext = CANVAS.read_text(encoding="utf-8")

print("\n[3] 大脑执行层 · 五维真读数")
m = re.search(r"const V5 = /\* real scan \+ brain probe snapshot \*/(\{.*?\});\n", ptext, re.S)
if not m:
    bad("未注入真实读数")
    B = None
else:
    H = json.loads(m.group(1))
    M, RT, B = H["meta"], H["runtime"], H["brain"]
    ok("数据层：在册 %d · 可执行 %d · 域 %d · 缺口 %d" % (M["total"], M["executable"], M["domains"], M["gap_count"]))
    b = B
    ok("健康维：%s 分 · %s/%s · %sms" % (b["health"]["score"], b["health"]["healthy"], b["health"]["total"], b["health"]["ms"]))
    ok("健康维五维明细齐备：%s" % " / ".join(d["key"] for d in b["health"]["dims"]))
    (ok if len(b["health"]["dims"]) == 5 else bad)("健康维明细数 %d（应 5）" % len(b["health"]["dims"]))
    ok("路由维：%d 条真实意图实测（%s）" % (len(b["routes"]), " · ".join(r["best"] or "?" for r in b["routes"])))
    ok("执行维：真调 %s · %sms · %s" % (b["execute"]["kind"], b["execute"]["ms"], b["execute"]["python"]))
    ok("验证维：真抓屏 · 指纹 %s · %s · %sms" % (b["verify"]["fingerprint"], b["verify"]["size"], b["verify"]["ms"]))
    ok("合一：命中 %s · %ss" % (b["unify"]["kind"], b["unify"]["elapsed_s"]))
    ok("审计总量真实读数：%s 条" % b["audit_total"])
    (ok if any(r["degraded"] for r in b["routes"]) else warn)("路由降级实测存在（界面需如实标注）")
    (ok if b["routes"] and b["routes"][0]["degraded_reason"] and b["routes"][0]["degraded_reason"] in ptext
     else bad)("降级原因原样上屏（不藏）")

print("\n[4] 七块真面板 · 零留位")
for n in ("对话", "能力广场", "大脑执行层", "领域分类", "审计台账", "系统体检", "设置"):
    (ok if ("'" + n + "'") in ptext else bad)("导航含「%s」" % n)
for gone in ("'智能体'", "'知识库'", "'工作流'", "'数据分析'", "'系统设置'", "尚未接入", "规划中"):
    (ok if gone not in ptext else bad)("空壳留位已清除：「%s」" % gone)
for fn in ("panelChat", "panelSquare", "panelBrain", "panelDomains", "panelAudit", "panelHealth", "panelSettings"):
    (ok if ("function " + fn) in ptext else bad)("实现 %s()" % fn)

print("\n[5] 大脑执行层可视化部件")
for part, label in [("class=\"flow\"", "流动链路动画"), ("class=\"pulse\"", "链路脉冲点"),
                    ("class=\"chainbox\"", "链路容器"), ("class=\"stagecard", "维度卡"),
                    ("class=\"routebar", "路由明细行"), ("class=\"degrade\"", "降级提示条"),
                    ("class=\"trace\"", "全链留痕"), ("UNIFY TRACE", "合一留痕标题")]:
    (ok if part in ptext else bad)("含 %s" % label)
for cap in ("brain_route", "brain_execute", "brain_verify", "brain_health", "brain_unify"):
    (ok if cap in ptext else bad)("标注真实能力名 %s" % cap)
n_dimcards = len(re.findall(r"stagecard", ptext))
(ok if n_dimcards >= 5 else bad)("维度卡出现 %d 处（应 ≥5）" % n_dimcards)

print("\n[6] 无限画布三层")
for k in ("01 项目背景", "02 设计系统", "03 设计稿"):
    (ok if k in ctext else bad)("标注「%s」" % k)
for q in ("是什么", "给谁用", "解决什么问题"):
    (ok if q in ctext else bad)("Row 1 回答「%s」" % q)
pages = re.findall(r"\['[^']+',\s*p\d\(\)\]", ctext)
(ok if len(pages) >= 6 else bad)("Row 3 页面 %d 个" % len(pages))
for t in ("大脑执行层 · 五维链路", "大脑执行层 · 维度卡", "大脑执行层 · 全链留痕"):
    (ok if t in ctext else bad)("画布含「%s」" % t)

print("\n[7] 原型硬性要求")
for bp in ("max-width:1439px", "max-width:1279px", "max-width:1023px", "max-width:767px"):
    (ok if bp in ptext else bad)("断点 %s" % bp)
clicks = len(re.findall(r"addEventListener\('click'", ptext))
(ok if clicks >= 2 else bad)("可点击绑定 %d 处" % clicks)
(ok if "aria-pressed" in ptext and "aria-current" in ptext else bad)("状态切换 + 当前项")
(ok if "data-theme" in ptext and "themeBtn" in ptext else bad)("亮 / 暗主题切换")
(ok if "skeleton" in ptext and 'role="status"' in ptext else bad)("加载态")
(ok if 'class="empty"' in ptext else warn)("空态")
for a in ("focus-visible", "aria-label", "aria-modal", "aria-haspopup", "role=\"dialog\"", "role=\"img\""):
    (ok if a in ptext else warn)("无障碍 %s" % a)

print("\n[8] 双主题对比度（WCAG 2.2 AA）")


def lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def lum(t):
    return 0.2126 * lin(t[0]) + 0.7152 * lin(t[1]) + 0.0722 * lin(t[2])


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def over(a, fg, bg):
    return tuple(a * fg[i] + (1 - a) * bg[i] for i in range(3))


DB, LB = (0x08, 0x11, 0x1F), (0xFF, 0xFF, 0xFF)
DI, LI = (0xDF, 0xF2, 0xFB), (0x14, 0x1A, 0x20)
cases = [("暗·正文", DI, DB), ("暗·二级", over(.74, DI, DB), DB), ("暗·三级", over(.54, DI, DB), DB),
         ("暗·霓虹", (0x2A, 0xD4, 0xF0), DB), ("暗·霓虹亮", (0x6E, 0xF2, 0xFF), DB),
         ("暗·正常", (0x3D, 0xDC, 0x97), DB), ("暗·警告", (0xF5, 0xB5, 0x44), DB), ("暗·异常", (0xFF, 0x7A, 0x7A), DB),
         ("亮·正文", LI, LB), ("亮·二级", over(.72, LI, LB), LB), ("亮·三级", over(.62, LI, LB), LB),
         ("亮·霓虹", (0x0A, 0x7D, 0x94), LB), ("亮·正常", (0x0F, 0x6B, 0x41), LB),
         ("亮·警告", (0x8A, 0x5A, 0x00), LB), ("亮·异常", (0xA3, 0x24, 0x1C), LB)]
for name, fg, bg in cases:
    r = ratio(fg, bg)
    (ok if r >= 4.5 else bad)("%s → %.2f:1" % (name, r))

print("\n[9] 反 AI-slop / 真实性")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")
for p in (CANVAS, PROTO):
    hits = EMOJI.findall(p.read_text(encoding="utf-8"))
    (ok if not hits else bad)("%s emoji %s" % (p.name, set(hits) if hits else "无"))
for tok in ("#6366f1", "#8b5cf6", "#7c3aed", "#a855f7"):
    if tok in ptext or tok in ctext:
        bad("AI 默认靛紫 %s" % tok)
ok("无 AI 默认靛紫")
(ok if "lorem ipsum" not in (ptext + ctext).lower() else bad)("无 lorem ipsum")
(ok if re.search(r">\s*(身高|体重|年龄)\s*<", ptext) is None else bad)("无编造人数据")
(ok if "不给你编一份回执" in ptext else warn)("对话回执声明不编造")
if B:
    (ok if "实测" in ptext and str(B["probed_at"])[:10] in ptext else warn)("标注了实测时间")

print("\n[10] 结果")
print("  PASS %d · WARN %d · FAIL %d" % (len(oks), len(warns), len(fails)))
for f in fails:
    print("   - " + f)
sys.exit(1 if fails else 0)
