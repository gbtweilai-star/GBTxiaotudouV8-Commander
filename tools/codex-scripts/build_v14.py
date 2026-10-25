# -*- coding: utf-8 -*-
"""构建 V14：补「框架核心层」10 面板。"""
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
V13P = BASE / "V13 GBT小土豆V8-可交互原型.html"
V14P = BASE / "V14 GBT小土豆V8-可交互原型.html"
V13ARC = BASE / "archive" / V13P.name

for p in [BASE / "V13 GBT小土豆V8-无限画布.html", V13P]:
    if p.exists():
        shutil.copy2(p, BASE / "archive" / p.name)
        print("归档:", p.name)

SRC = V13P if V13P.exists() else V13ARC
assert SRC.exists(), "找不到 V13 源"
print("源:", SRC.name, "(%s)" % ("根目录" if SRC == V13P else "archive"))
src = SRC.read_text(encoding="utf-8")
src = src.replace("可交互原型 V13", "可交互原型 V14")
src = re.sub(r"\bV13\b", "V14", src)
assert "const V14 = " in src, "数据层常量未改名"

# ── 1. 换数据层（花括号配对） ──
new_json = (S / "v14_manifest.json").read_text(encoding="utf-8").strip()
head = src.index("const V14 = ")
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
src = src[:brace] + "/* V14 · + 框架核心层 + 机器穷举覆盖审计 */" + new_json + src[i + 1:]
print("数据层: %.1f KB" % (len(new_json) / 1024))

# ── 2. 注入框架核心层 10 面板 ──
panels = (S / "panels_v14.js").read_text(encoding="utf-8")
anchor = "  function renderGod() {"
assert anchor in src, "renderGod 锚点未命中"
src = src.replace(anchor, panels.rstrip("\n") + "\n\n" + anchor, 1)

# ── 3. NAV 加一组 ──
old_nav = "    ['量化与钱包', 'wsquant', '11390 行'], ['账本与审美脑', 'wsledger', '557 行']\n  ];"
new_nav = ("    ['量化与钱包', 'wsquant', '11390 行'], ['账本与审美脑', 'wsledger', '557 行'],\n"
           "    ['源码覆盖审计', 'covaudit', '机器穷举'],\n"
           "    ['统一接口层', 'coreapi', 'api.py'], ['授权与安全策略', 'coresec', '6 模块'],\n"
           "    ['框架底座', 'corebase', '10 文件'], ['omni 触手家族', 'coreomni', '20 文件'],\n"
           "    ['部署层', 'coredeploy', '12 文件'], ['对外桥接', 'corebridge', '7 文件'],\n"
           "    ['技能库', 'coreskill', '17 文件'], ['镜像与乾坤底座', 'coremirror', '4 文件'],\n"
           "    ['密钥保险箱', 'corevault', '4 文件']\n  ];")
assert old_nav in src, "NAV 锚点未命中"
src = src.replace(old_nav, new_nav, 1)

old_grp = "  var GRP = { shell: '宿主外壳 · DSH 席面', wsover: '工作区源码 · 全量清点' };"
new_grp = ("  var GRP = { shell: '宿主外壳 · DSH 席面', wsover: '工作区源码 · 全量清点',\n"
           "    covaudit: '框架核心 · 机器穷举补漏' };")
assert old_grp in src, "GRP 锚点未命中"
src = src.replace(old_grp, new_grp, 1)

# ── 4. 分发 ──
old_disp = "    if (st.nav === 'wsledger') return panelWsLedger();\n  }"
new_disp = ("    if (st.nav === 'wsledger') return panelWsLedger();\n"
            "    if (st.nav === 'covaudit') return panelCovAudit();\n"
            "    if (st.nav === 'coreapi') return panelCoreApi();\n"
            "    if (st.nav === 'coresec') return panelCoreSec();\n"
            "    if (st.nav === 'corebase') return panelCoreBase();\n"
            "    if (st.nav === 'coreomni') return panelCoreOmni();\n"
            "    if (st.nav === 'coredeploy') return panelCoreDeploy();\n"
            "    if (st.nav === 'corebridge') return panelCoreBridge();\n"
            "    if (st.nav === 'coreskill') return panelCoreSkill();\n"
            "    if (st.nav === 'coremirror') return panelCoreMirror();\n"
            "    if (st.nav === 'corevault') return panelCoreVault();\n  }")
assert old_disp in src, "分发锚点未命中"
src = src.replace(old_disp, new_disp, 1)

# ── 5. 上帝视角：把源码覆盖卡升级成「含未覆盖面」的版本 ──
old_card = "      wsCoverCard() +"
new_card = "      wsCoverCard() +\n      covGapCard() +"
assert old_card in src, "上帝视角锚点未命中"
src = src.replace(old_card, new_card, 1)

GAP_CARD = r"""
  /* ── 上帝视角 · 未覆盖缺口卡（机器穷举口径） ── */
  function covGapCard() {
    var C = V14.coverage;
    var dirs = Object.keys(C.by_dir).map(function (k) {
      return { k: k, un: C.by_dir[k].lines - C.by_dir[k].covered_lines, cov: C.by_dir[k].covered_lines };
    }).filter(function (d) { return d.un > 0; }).sort(function (a, b) { return b.un - a.un; }).slice(0, 10);
    var maxUn = dirs.length ? dirs[0].un : 1;
    var p = Math.round(100 * C.uncovered_lines / C.total_lines);
    return '<div class="card" style="margin-bottom:11px"><div class="card-h"><b>源码未覆盖面</b> / UNCOVERED' +
      '<span class="r">机器穷举 · 连模块名都没进过交付件</span></div><div class="card-b">' +
      '<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:8px">' +
      '<span class="mono" style="font-size:24px;color:var(--rose);line-height:1">' + covNum(C.uncovered_lines) + '</span>' +
      '<span class="mono dim" style="font-size:11px">/ ' + covNum(C.total_lines) + ' 行（' + p + '%）</span></div>' +
      '<span class="track" style="display:block"><i class="rose" style="width:' + Math.max(p, 3) + '%"></i></span>' +
      dirs.map(function (d) {
        var w = Math.round(100 * d.un / maxUn);
        return '<div style="padding:3px 0"><div style="display:flex;align-items:baseline;gap:8px;font-size:10px">' +
          '<span class="mono" style="color:var(--ink-3);min-width:210px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
          esc(d.k) + '</span>' +
          '<span class="mono" style="margin-left:auto;font-size:9.5px;color:' +
          (d.cov === 0 ? 'var(--rose)' : 'var(--amber)') + '">' + covNum(d.un) + '</span></div>' +
          '<span class="track" style="display:block;margin-top:3px"><i class="' +
          (d.cov === 0 ? 'rose' : 'warn') + '" style="width:' + Math.max(w, 2) + '%"></i></span></div>';
      }).join('') +
      '<p style="font-size:9.5px;color:var(--ink-3);margin-top:9px">' +
      '判据是「模块名是否出现在交付件里」—— 这是弱判据，真实缺口在此之下。' +
      'V14 已补 102 文件 / 31,000 行（统一接口层 / 授权与安全策略 / 框架底座 / omni 家族 / 部署层 / 桥接 / 技能库 / 镜像底座 / 密钥箱）。</p>' +
      '</div></div>';
  }
"""
anchor2 = "  function renderGod() {"
src = src.replace(anchor2, GAP_CARD.strip() + "\n\n" + anchor2, 1)

# ── 6. 页脚 ──
old_foot = '<div class="nav-foot"><b>GBT小土豆V8 · V14</b>40 面板 / 43 画布页 · 品牌 Logo 已接入<br>'
new_foot = '<div class="nav-foot"><b>GBT小土豆V8 · V14</b>50 面板 / 53 画布页 · 框架核心层已补<br>'
assert old_foot in src, "页脚锚点未命中"
src = src.replace(old_foot, new_foot, 1)

V14P.write_text(src, encoding="utf-8")
print("写出:", V14P.name, "%.1f KB" % (V14P.stat().st_size / 1024))
if V13P.exists():
    V13P.unlink()
    print("移除旧版:", V13P.name)
