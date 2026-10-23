# -*- coding: utf-8 -*-
"""构建 V17：补 5 个面板（原生浏览器 / 云电脑独立窗口 / 万能插工具集 / 编排内核 / 严格覆盖审计）。
Refinement，视觉层沿用 V16；只加内容与一处导航分组。"""
import re
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
V16P = BASE / "V16 GBT小土豆V8-可交互原型.html"
V17P = BASE / "V17 GBT小土豆V8-可交互原型.html"
V16ARC = BASE / "archive" / V16P.name

for n in (V16P.name, "V16 GBT小土豆V8-无限画布.html"):
    p = BASE / n
    if p.exists():
        shutil.copy2(p, BASE / "archive" / n)
        print("归档:", n)

SRC = V16P if V16P.exists() else V16ARC
assert SRC.exists(), "找不到 V16 源"
src = SRC.read_text(encoding="utf-8")
src = src.replace("可交互原型 V16", "可交互原型 V17")
src = re.sub(r"\bV16\b", "V17", src)
assert "const V17 = " in src

# ── 1. 换数据层（花括号配对）──
new_json = (S / "v17_manifest.json").read_text(encoding="utf-8").strip()
head = src.index("const V17 = ")
brace = src.index("{", head)
i, depth, in_str, esc_next = brace, 0, False, False
while i < len(src):
    c = src[i]
    if in_str:
        if esc_next:
            esc_next = False
        elif c == "\\":
            esc_next = True
        elif c == '"':
            in_str = False
    else:
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
    i += 1
assert depth == 0, "数据层花括号未配对"
src = src[:brace] + "/* V17 · + 原生浏览器 + 云电脑 + 工具集 + 编排内核 + 严格覆盖审计 */" + new_json + src[i + 1:]
print("数据层: %.1f KB" % (len(new_json) / 1024))

# ── 2. 注入 5 个面板（必须在 renderGod 之前）──
panels = (S / "panels_v17.js").read_text(encoding="utf-8")
anchor = "  function renderGod() {"
assert anchor in src, "renderGod 锚点未命中"
src = src.replace(anchor, panels.rstrip("\n") + "\n\n" + anchor, 1)

# ── 3. NAV 加一组 ──
old_nav = "    ['密钥保险箱', 'corevault', '4 文件']\n  ];"
new_nav = ("    ['密钥保险箱', 'corevault', '4 文件'],\n"
           "    ['原生浏览器', 'v17browser', '1508 行'], ['云电脑窗口', 'v17cloudpc', '5 原语'],\n"
           "    ['万能插工具集', 'v17tools', '50 文件'], ['编排内核', 'v17kernel', '三源蒸馏'],\n"
           "    ['严格覆盖审计', 'v17strict', '9.6 万行']\n  ];")
assert old_nav in src, "NAV 锚点未命中"
src = src.replace(old_nav, new_nav, 1)

old_grp = "    covaudit: '框架核心 · 机器穷举补漏' };"
new_grp = ("    covaudit: '框架核心 · 机器穷举补漏',\n"
           "    v17browser: 'V17 · 补漏（浏览器 / 云电脑 / 工具 / 内核）' };")
assert old_grp in src, "GRP 锚点未命中"
src = src.replace(old_grp, new_grp, 1)

# ── 4. 分发 ──
old_disp = "    if (st.nav === 'corevault') return panelCoreVault();\n  }"
new_disp = ("    if (st.nav === 'corevault') return panelCoreVault();\n"
            "    if (st.nav === 'v17browser') return panelV17Browser();\n"
            "    if (st.nav === 'v17cloudpc') return panelV17CloudPC();\n"
            "    if (st.nav === 'v17tools') return panelV17Tools();\n"
            "    if (st.nav === 'v17kernel') return panelV17Kernel();\n"
            "    if (st.nav === 'v17strict') return panelV17Strict();\n  }")
assert old_disp in src, "分发锚点未命中"
src = src.replace(old_disp, new_disp, 1)

# ── 5. 页脚 ──
old_foot = '<b>GBT小土豆V8 · V17</b>50 面板 / 53 画布页 · 排版与节奏已打磨<br>'
new_foot = '<b>GBT小土豆V8 · V17</b>55 面板 / 58 画布页 · 原生浏览器与云电脑已补<br>'
assert old_foot in src, "页脚锚点未命中"
src = src.replace(old_foot, new_foot, 1)

V17P.write_text(src, encoding="utf-8")

# ── 6b. 真渲染揪出的塌页 bug：panelRecon 的运算符优先级 ──
#   `a + b ? c : d` 会被解析成 `(a+b) ? c : d` —— 整页 payload 全成了三元条件，
#   只要条件为真就**只渲染那个 degrade div，其余全丢**。渲染图里「情报与观察」整页
#   塌成一行「缺口：」。stub 校验器阈值 60 字符，一个 degrade 框就超过 60 ⇒ 连过 5 版。
PANEL_FIX = [
    # ① panelRecon 的运算符优先级：`a + b ? c : d` 解析成 `(a+b) ? c : d`，
    #    整页 payload 都成了三元条件 ⇒ 只渲染一个 degrade div，其余全丢。
    #    渲染图里「情报与观察」整页塌成一行「缺口：」。
    ("      }).join('') +\n"
     "      (tw.gaps || []).length ? '<div class=\"degrade\" style=\"margin-top:9px\"><span>缺口：' +\n"
     "        esc((tw.gaps || []).map(function (g) { return typeof g === 'string' ? g : JSON.stringify(g); }).join(' / ').slice(0, 160)) +\n"
     "        '</span></div>' : '' + '</div></div>' +",
     "      }).join('') +\n"
     "      ((tw.gaps || []).length ? '<div class=\"degrade\" style=\"margin-top:9px\"><span>缺口：' +\n"
     "        esc((tw.gaps || []).map(function (g) { return typeof g === 'string' ? g : JSON.stringify(g); }).join(' / ').slice(0, 160)) +\n"
     "        '</span></div>' : '') + '</div></div>' +"),
    # ② bar() 加钳位：分母一旦小于真实值，填充就会渲成 >100% 溢出卡片。
    #    实测 auth_boundaries 真实 769 / 旧分母 200 ⇒ 384%，右边跑到 3202px。
    ("  function bar(label, n, den, tone) {\n"
     "    var p = den ? Math.round(100 * n / den) : 0;",
     "  function bar(label, n, den, tone) {\n"
     "    var p = den ? Math.round(100 * n / den) : 0;\n"
     "    /* 钳位：分母若小于真实值，填充会渲成 >100% 并溢出卡片边界。\n"
     "       这不是显示层的容错，而是提醒：**永远不要给 bar 编分母**。 */\n"
     "    p = Math.max(0, Math.min(100, p));"),
    # ③ 攻击面那五项原本用的是我编的刻度（900/1000/600/400/200），
    #    而真实值是 785/967/497/264/769 —— 编刻度就是编数据。改用这五项的真实最大值做分母。
    ("      [['入口点', sf.entry_points, 900], ['文件操作', sf.file_operations, 1000],\n"
     "       ['网络', sf.network, 600], ['用户输入', sf.user_inputs, 400],\n"
     "       ['认证边界', sf.auth_boundaries, 200]].map(function (r) {\n"
     "        return bar(r[0], r[1] || 0, r[2], (r[1] || 0) > r[2] * 0.7 ? 'warn' : '');\n"
     "      }).join('') + '</div></div>' +",
     "      (function () {\n"
     "        var rows = [['入口点', sf.entry_points], ['文件操作', sf.file_operations],\n"
     "                    ['网络', sf.network], ['用户输入', sf.user_inputs],\n"
     "                    ['认证边界', sf.auth_boundaries]];\n"
     "        var mx = Math.max.apply(null, rows.map(function (r) { return r[1] || 0; })) || 1;\n"
     "        return rows.map(function (r) {\n"
     "          return bar(r[0], r[1] || 0, mx, (r[1] || 0) > mx * 0.7 ? 'warn' : '');\n"
     "        }).join('');\n"
     "      })() + '</div></div>' +"),
]
for _o, _n in PANEL_FIX:
    assert _o in src, "面板修复锚点未命中: " + _o[:60]
    src = src.replace(_o, _n, 1)
print("面板修复: %d 处（recon 优先级 · bar 钳位 · 攻击面分母）" % len(PANEL_FIX))

V17P.write_text(src, encoding="utf-8")

# ── 6. 收刻度：新加的面板里若抄进了离群 gap，一并收到 2px 刻度 ──


def snap_gaps(path):
    t = path.read_text(encoding="utf-8")
    import collections
    total = collections.Counter()
    for bad, good in (("5px", "4px"), ("7px", "8px"), ("9px", "8px"),
                      ("11px", "12px"), ("13px", "12px"), ("14px", "16px"), ("15px", "16px")):
        pat = re.compile(r"(gap:\s*)" + re.escape(bad))
        n = len(pat.findall(t))
        if n:
            t = pat.sub(lambda m: m.group(1) + good, t)
            total[bad + "→" + good] = n
    path.write_text(t, encoding="utf-8")
    return total


print("收刻度:", dict(snap_gaps(V17P)) or "无离群值")
print("写出:", V17P.name, "%.1f KB" % (V17P.stat().st_size / 1024))
if V16P.exists():
    V16P.unlink()
    print("移除旧版:", V16P.name)
