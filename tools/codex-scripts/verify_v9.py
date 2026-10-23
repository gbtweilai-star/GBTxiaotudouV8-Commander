# -*- coding: utf-8 -*-
"""V9 交付前自检：二十块真面板（+ 插件市场蒸馏件）。"""
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
CANVAS = BASE / "V9 GBT小土豆V8-无限画布.html"
PROTO = BASE / "V9 GBT小土豆V8-可交互原型.html"
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


print("=" * 78)
print("V9 交付前自检 · 二十块真面板")
print("=" * 78)

print("\n[1] 文件 / 版本 / 归档")
for p in (CANVAS, PROTO):
    (ok if p.exists() else bad)("%s · %d B" % (p.name, len(p.read_bytes()) if p.exists() else 0))
(ok if re.search(r"V9 ", CANVAS.name) and re.search(r"V9 ", PROTO.name) else bad)("版本一致（V9）")
arch = sorted(x.name for x in (BASE / "archive").glob("V* GBT*"))
(ok if len(arch) == 16 else bad)("archive/ 历史 %d 份（V1-V8 各 2）" % len(arch))
(ok if not list(BASE.glob("V[1-8] *.html")) else bad)("根目录只留活跃版本")

print("\n[2] JS 语法")
for p in (CANVAS, PROTO):
    t = p.read_text(encoding="utf-8")
    js = t[t.rindex("<script>") + 8:t.rindex("</script>")]
    f = BASE / ".scratch" / ("_v9chk_%s.js" % ("canvas" if p is CANVAS else "proto"))
    f.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    (ok if r.returncode == 0 else bad)("%s 语法（%d 字符）%s" % (p.name, len(js), (r.stderr or '').strip()[:140]))

ptext = PROTO.read_text(encoding="utf-8")
ctext = CANVAS.read_text(encoding="utf-8")

print("\n[3] 插件市场蒸馏件 · 真读数")
m = re.search(r"const V9 = /\* full snapshot \+ plugin market \*/(\{.*?\});\n", ptext, re.S)
if not m:
    bad("未注入插件市场数据")
else:
    MK = json.loads(m.group(1))["market"]
    L = MK["local"]
    (ok if L["packages"] > 0 else bad)("本机包 %d 个" % L["packages"])
    (ok if L["with_manifest"] > 0 else bad)("带 dsh 清单 %d 个" % L["with_manifest"])
    (ok if L["official"] > 0 else bad)("官方 scope %d 个" % L["official"])
    ok("清单类型：%s" % L["manifest_types"])
    (ok if len(L["manifest_types"]) >= 3 else warn)("清单类型数 %d" % len(L["manifest_types"]))
    (ok if len(MK["profiles"]) >= 1 else bad)("profile %d 个" % len(MK["profiles"]))
    C = MK["candidates"]
    (ok if len(C) == 4 else bad)("候选包 %d 个（应 4）" % len(C))
    scores = [c["score"] for c in C]
    (ok if scores == sorted(scores, reverse=True) else bad)("候选按分数降序 %s" % scores)
    top = C[0]
    (ok if top["name"] == "dshmarket" and top["score"] >= 85 else bad)(
        "最高分 %s = %d（应 dshmarket ≥85）" % (top["name"], top["score"]))
    worst = C[-1]
    (ok if worst["score"] < 60 else bad)("最低分 %s = %d（应 <60）" % (worst["name"], worst["score"]))
    for c in C:
        (ok if len(c["dims"]) == 5 else bad)("%s 维度 %d 个（应 5）" % (c["name"], len(c["dims"])))
    ok("五维口径：%s" % " / ".join(MK["dims"]))
    (ok if "dshmarket" in ptext and "dsh-market" in ptext else bad)("真名 / 仿冒名对照上屏")
    (ok if "404" in ptext else bad)("写明 dsh-market 包名 404（真实）")
    (ok if "deploy_publish" in ptext else bad)("安装门前置授权上屏")
    (ok if "store.audit" in ptext or "审计留痕" in ptext else bad)("审计留痕上屏")
    (ok if "不执行安装" in ptext else bad)("明确本原型不执行安装")
    (ok if "不过不进环境" in ptext or "报告不过" in ptext else bad)("装前报告规矩上屏")

print("\n[4] 二十块真面板")
NAMES = ["对话", "能力广场", "大脑执行层", "领域分类", "审计台账", "语音", "蓝牙", "万能插", "亿万触手",
         "镜像与晋升", "大模型通道", "心智与记忆", "情报与观察", "安全攻防", "长程与工具", "创作与吞噬",
         "其余域", "插件市场", "系统体检", "设置"]
for n in NAMES:
    (ok if ("'" + n + "'") in ptext else bad)("导航含「%s」" % n)
n_panel = len(re.findall(r"function panel[A-Z]\w+\(", ptext))
(ok if n_panel == 20 else bad)("面板函数 %d 个（应 20）" % n_panel)
(ok if "function panelMarket" in ptext else bad)("实现 panelMarket()")
(ok if "return panelMarket();" in ptext else bad)("分发到 market")

print("\n[5] 画布")
for k in ("01 项目背景", "02 设计系统", "03 设计稿"):
    (ok if k in ctext else bad)("标注「%s」" % k)
for q in ("是什么", "给谁用", "解决什么问题"):
    (ok if q in ctext else bad)("Row 1 回答「%s」" % q)
pages = re.findall(r"\['[^']+',\s*p\d+\(\)\]", ctext)
(ok if len(pages) >= 20 else bad)("Row 3 页面 %d 个" % len(pages))
(ok if "插件市场 · 蒸馏件" in ctext else bad)("画布含「插件市场 · 蒸馏件」")

print("\n[6] 硬性要求 / 反 slop")
for bp in ("max-width:1439px", "max-width:1279px", "max-width:1023px", "max-width:767px"):
    (ok if bp in ptext else bad)("断点 %s" % bp)
(ok if len(re.findall(r"addEventListener\('click'", ptext)) >= 2 else bad)("可点击绑定")
(ok if "data-theme" in ptext else bad)("亮 / 暗主题")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")
for p in (CANVAS, PROTO):
    hits = EMOJI.findall(p.read_text(encoding="utf-8"))
    (ok if not hits else warn)("%s emoji %s" % (p.name, set(hits) if hits else "无"))
(ok if "lorem ipsum" not in (ptext + ctext).lower() else bad)("无 lorem ipsum")
(ok if len(PROTO.read_bytes()) / 1024 < 800 else warn)("原型 %.0f KB" % (len(PROTO.read_bytes()) / 1024))

print("\n[7] 结果")
print("  PASS %d · WARN %d · FAIL %d" % (len(oks), len(warns), len(fails)))
for f in fails:
    print("   - " + f)
sys.exit(1 if fails else 0)
