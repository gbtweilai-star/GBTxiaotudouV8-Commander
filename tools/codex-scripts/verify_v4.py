# -*- coding: utf-8 -*-
"""V4 交付前自检：对话面板 + 上帝视角 + 双主题对比度。"""
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
CANVAS = BASE / "V4 GBT小土豆V8-无限画布.html"
PROTO = BASE / "V4 GBT小土豆V8-可交互原型.html"
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


print("=" * 78)
print("V4 交付前自检 · 对话面板 + 上帝视角")
print("=" * 78)

print("\n[1] 文件 / 版本 / 归档")
for p in (CANVAS, PROTO):
    (ok if p.exists() else bad)("%s · %d B" % (p.name, len(p.read_bytes()) if p.exists() else 0))
(ok if re.search(r"V4 ", CANVAS.name) and re.search(r"V4 ", PROTO.name) else bad)("两文件版本号一致（V4）")
for v in ("V1", "V2", "V3"):
    n = len(list((BASE / "archive").glob(v + " GBT*")))
    (ok if n == 2 else bad)("archive/ %s 快照 %d/2" % (v, n))
(ok if not list(BASE.glob("V1 *.html")) + list(BASE.glob("V2 *.html")) + list(BASE.glob("V3 *.html"))
 else bad)("根目录只留活跃版本")

print("\n[2] JS 语法（node --check）")
for p in (CANVAS, PROTO):
    js = script_of(p.read_text(encoding="utf-8"))
    f = TMP / ("_v4_%s.js" % ("canvas" if p is CANVAS else "proto"))
    f.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    (ok if r.returncode == 0 else bad)("%s 语法（%d 字符）%s" % (p.name, len(js), (r.stderr or '').strip()[:150]))

print("\n[3] 真实数据层")
ptext = PROTO.read_text(encoding="utf-8")
m = re.search(r"const V4 = /\* real scan snapshot \*/(\{.*?\});\n", ptext, re.S)
H = None
if not m:
    bad("未注入真实读数")
else:
    H = json.loads(m.group(1))
    M, RT = H["meta"], H["runtime"]
    ok("在册 %d（可执行 %d + 禁用 %d）· 域 %d · 需授权 %d · 缺口 %d"
       % (M["total"], M["executable"], M["disabled"], M["domains"], M["gated"], M["gap_count"]))
    ok("composer 真实字段：项目 GBT小土豆V8 · 分支 %s（改动 %d）· 权限 %s · 模型 %s/%s"
       % (RT["git_branch"], RT["git_changed"], RT["permission"], RT["model_provider"], RT["model"]))
    ok("会话列真实来源：审计活动 %d 条（最近 %s）· 扫描 %d 行"
       % (len(H.get("activity") or []), (H["activity"][0]["last"] if H.get("activity") else "—"),
          H.get("audit_lines_scanned", 0)))
    (ok if "audit.jsonl" in ptext else warn)("界面标注了活动列的真实来源")
    tot = sum(r["total"] for r in H["radar"])
    (ok if tot == M["executable"] and len(H["radar"]) == 6 else bad)("六维覆盖 %d 项（应 %d）" % (tot, M["executable"]))

print("\n[4] 无限画布三层")
ctext = CANVAS.read_text(encoding="utf-8")
for k in ("01 项目背景", "02 设计系统", "03 设计稿"):
    (ok if k in ctext else bad)("标注「%s」" % k)
for q in ("是什么", "给谁用", "解决什么问题"):
    (ok if q in ctext else bad)("Row 1 回答「%s」" % q)
pages = re.findall(r"\['[^']+',\s*p\d\(\)\]", ctext)
(ok if len(pages) >= 6 else bad)("Row 3 页面 %d 个 + 引导线" % len(pages))

print("\n[5] 对话面板（Codex 式格式）")
for part, label in [('id="nav"', '左导航'), ('id="sessions"', '会话/活动列'), ('id="chatBody"', '对话主区'),
                    ('id="input"', 'composer 输入'), ('id="compChips"', 'composer 上下文 chips'),
                    ('id="permPill"', '权限指示'), ('id="modelPill"', '模型指示'), ('id="sendBtn"', '发送按钮'),
                    ('id="newChat"', '新对话按钮')]:
    (ok if part in ptext else bad)("存在 %s" % label)
(ok if "你想让我们在 GBT小土豆V8 中构建什么" in ptext else bad)("居中空态引导语")

print("\n[6] 上帝视角（右上角）")
top_area = ptext[:ptext.index('class="main"')]
(ok if 'id="godBtn"' in top_area else bad)("入口位于顶栏（右上角区域）")
(ok if 'id="god"' in ptext and "上帝视角" in ptext else bad)("上帝视角面板存在")
for part, label in [('class="net"', '径向能力网络'), ('class="bars"', '能力分布柱状'),
                    ('class="rank"', '排名条'), ('class="feed"', '活动流'), ('class="warnbar"', '禁用提示条')]:
    (ok if part in ptext else bad)("上帝视角含 %s" % label)
(ok if "ALIAS" in ptext and "30" in ptext else warn)("30 域人话别名映射存在")
alias_block = ptext[ptext.index("var ALIAS = {"):ptext.index("};", ptext.index("var ALIAS = {"))]
alias_n = len(re.findall(r"(\w+):\s*'", alias_block))
(ok if alias_n >= 30 else bad)("别名条目 %d（应 ≥30）" % alias_n)

print("\n[7] 原型硬性要求")
(ok if re.search(r"max-width|clamp\(|@media", ptext) else bad)("响应式兜底")
(ok if not re.search(r"width:\s*390px", ptext) else warn)("未写死 390px")
for bp in ("max-width:1279px", "max-width:1023px", "max-width:767px"):
    (ok if bp in ptext else bad)("断点 %s" % bp)
clicks = len(re.findall(r"addEventListener\('click'", ptext))
(ok if clicks >= 2 else bad)("可点击绑定 %d 处" % clicks)
(ok if "aria-pressed" in ptext and "aria-current" in ptext else bad)("状态切换 + 当前项 aria")
(ok if "data-theme" in ptext and "themeBtn" in ptext else bad)("亮 / 暗主题切换")
(ok if ("skeleton" in ptext and 'role="status"' in ptext and "godLoaded" in ptext) else bad)("加载态（骨架 + role=status + 一次性加载标志）")
for s in ("empty", "error", "populated"):
    (ok if s in ptext else warn)("状态 %s" % s)
for a in ("focus-visible", "aria-label", "aria-modal", "aria-haspopup", "role=\"dialog\""):
    (ok if a in ptext else warn)("无障碍 %s" % a)
(ok if "prefers-reduced-motion" in ptext else warn)("尊重减少动效偏好")

print("\n[8] 双主题对比度（WCAG 2.2 AA ≥4.5:1）")


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


DARK_BG = (0x08, 0x11, 0x1F)
LIGHT_BG = (0xFF, 0xFF, 0xFF)
D_INK = (0xDF, 0xF2, 0xFB)
L_INK = (0x14, 0x1A, 0x20)
cases = [
    ("暗·正文", D_INK, DARK_BG), ("暗·二级 .74", over(.74, D_INK, DARK_BG), DARK_BG),
    ("暗·三级 .54", over(.54, D_INK, DARK_BG), DARK_BG),
    ("暗·霓虹", (0x2A, 0xD4, 0xF0), DARK_BG), ("暗·霓虹亮", (0x6E, 0xF2, 0xFF), DARK_BG),
    ("暗·正常", (0x3D, 0xDC, 0x97), DARK_BG), ("暗·警告", (0xF5, 0xB5, 0x44), DARK_BG),
    ("暗·异常", (0xFF, 0x7A, 0x7A), DARK_BG),
    ("亮·正文", L_INK, LIGHT_BG), ("亮·二级 .72", over(.72, L_INK, LIGHT_BG), LIGHT_BG),
    ("亮·三级 .62", over(.62, L_INK, LIGHT_BG), LIGHT_BG),
    ("亮·霓虹", (0x0A, 0x7D, 0x94), LIGHT_BG), ("亮·正常", (0x0F, 0x6B, 0x41), LIGHT_BG),
    ("亮·警告", (0x8A, 0x5A, 0x00), LIGHT_BG), ("亮·异常", (0xA3, 0x24, 0x1C), LIGHT_BG),
]
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
if re.search(r">\s*(身高|体重|年龄)\s*<", ptext):
    bad("出现编造的人体数据")
else:
    ok("无编造的人体数据")
if "不给你编一份回执" in ptext:
    ok("对话回执明确声明不编造（原型不发网络请求）")
else:
    warn("未声明回执不编造")

print("\n[10] 结果")
print("  PASS %d · WARN %d · FAIL %d" % (len(oks), len(warns), len(fails)))
for f in fails:
    print("   - " + f)
sys.exit(1 if fails else 0)
