# -*- coding: utf-8 -*-
"""V7 交付前自检：十一块真面板（+ 万能插 / 亿万触手）。"""
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
CANVAS = BASE / "V7 GBT小土豆V8-无限画布.html"
PROTO = BASE / "V7 GBT小土豆V8-可交互原型.html"
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
print("V7 交付前自检 · 十一块真面板")
print("=" * 78)

print("\n[1] 文件 / 版本 / 归档")
for p in (CANVAS, PROTO):
    (ok if p.exists() else bad)("%s · %d B" % (p.name, len(p.read_bytes()) if p.exists() else 0))
(ok if re.search(r"V7 ", CANVAS.name) and re.search(r"V7 ", PROTO.name) else bad)("版本一致（V7）")
arch = sorted(x.name for x in (BASE / "archive").glob("V* GBT*"))
(ok if len(arch) == 12 else bad)("archive/ 历史 %d 份（V1-V6 各 2）" % len(arch))
(ok if not list(BASE.glob("V[1-6] *.html")) else bad)("根目录只留活跃版本")

print("\n[2] JS 语法")
for p in (CANVAS, PROTO):
    t = p.read_text(encoding="utf-8")
    js = t[t.rindex("<script>") + 8:t.rindex("</script>")]
    f = BASE / ".scratch" / ("_v7chk_%s.js" % ("canvas" if p is CANVAS else "proto"))
    f.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    (ok if r.returncode == 0 else bad)("%s 语法（%d 字符）%s" % (p.name, len(js), (r.stderr or '').strip()[:140]))

ptext = PROTO.read_text(encoding="utf-8")
ctext = CANVAS.read_text(encoding="utf-8")

print("\n[3] 万能插真读数")
m = re.search(r"const V7 = /\* real scan \+ brain \+ device \+ plug \+ tentacle snapshot \*/(\{.*?\});\n", ptext, re.S)
D = None
if not m:
    bad("未注入真实读数")
else:
    H = json.loads(m.group(1))
    PL = H["plug"]
    ok("工作流定义 %s 个 · 运行记录 %s 条 · 算子 %d 个 · 定时任务 %s 个"
       % (PL["workflow_count"], len(PL["runs"]), len(PL["operators"]), PL["schedules"]))
    big = [w for w in PL["workflows"] if w["node_count"] >= 19]
    (ok if big else bad)("含大型工作流（%s · %d 节点）" % (big[0]["name"], big[0]["node_count"]) if big else "无 19 节点工作流")
    (ok if len({w["name"] for w in PL["workflows"]}) == 9 else bad)("九条工作流名唯一")
    ug = (PL["real_runs"]["unique"] or {}).get("data")
    (ok if ug == [3, 1, 2] else bad)("transfer unique 真输出 %s（应 [3,1,2]）" % ug)
    (ok if "engine.py:541" in ptext else warn)("标注了正规数据出口来源")
    (ok if "list_workflows" in ptext or "include_workflows" in ptext else warn)("出口口径写清")
    for k in ("self-polish", "gbt_polish_v1", "honesty-test"):
        (ok if k in ptext else bad)("工作流「%s」上屏" % k)
    for op in ("unique", "stats", "flatten", "pluck"):
        (ok if op in ptext else bad)("算子 %s 上屏" % op)

print("\n[4] 亿万触手真读数")
if D:
    T = H["tentacle"]
    (ok if "85项" in (T["headline"] or "") or "三通道" in (T["headline"] or "") else bad)("总纲标题：%s" % (T["headline"] or "")[:40])
    (ok if len(T["channels"]) == 3 else bad)("三通道 %d 个" % len(T["channels"]))
    for c in ("视觉", "听觉", "操作"):
        (ok if c in ptext else bad)("通道「%s」上屏" % c)
    (ok if T["sections_total"] == 66 else bad)("能力分段合计 %d 项（应 66）" % T["sections_total"])
    (ok if len(T["sections"]) == 14 else bad)("分段数 %d（应 14）" % len(T["sections"]))
    C = T["coverage"]
    (ok if C["pct"] == 100.0 else bad)("意图覆盖 %s%%" % C["pct"])
    (ok if C["uncovered"] == 0 and C["ghosts"] == 0 else bad)("未覆盖 %s · 幽灵 %s" % (C["uncovered"], C["ghosts"]))
    (ok if C["domains"] == 10 and len(C["by_domain"]) == 10 else bad)("十域 %s 个" % C["domains"])
    deps = T["diagnose"]["deps"]
    (ok if len(deps) == 4 and all(d["ok"] for d in deps) else bad)(
        "依赖四项全 ok：%s" % " / ".join(d["name"] for d in deps))
    (ok if T["diagnose"]["manifest_methods"] == 66 else bad)("总纲方法 %s" % T["diagnose"]["manifest_methods"])
    mx = T["audit"]["matrix"]
    (ok if len(mx) == 8 else bad)("八短板矩阵 %d 行（应 8）" % len(mx))
    eye = [r for r in mx if r["key"] == "NO_SELF_VIEW"]
    (ok if eye and eye[0]["reportable_modules"] == 0 else warn)("「看不见自己」0/5 如实展示（真实短板）")
    (ok if "desktop_control" in ptext else bad)("触手门缺件名 desktop_control（真实）")

print("\n[5] 十一块真面板")
NAMES = ["对话", "能力广场", "大脑执行层", "领域分类", "审计台账", "语音", "蓝牙",
         "万能插", "亿万触手", "系统体检", "设置"]
for n in NAMES:
    (ok if ("'" + n + "'") in ptext else bad)("导航含「%s」" % n)
for fn in ("panelChat", "panelSquare", "panelBrain", "panelDomains", "panelAudit", "panelVoice",
           "panelBluetooth", "panelPlug", "panelTentacle", "panelHealth", "panelSettings"):
    (ok if ("function " + fn) in ptext else bad)("实现 %s()" % fn)
for fn in ("plug", "tentacle"):
    (ok if ("return panel" + fn.capitalize() + "();") in ptext else bad)("分发到 %s" % fn)
for gone in ("'智能体'", "'知识库'", "'工作流'", "'数据分析'", "'系统设置'", "尚未接入", "规划中"):
    (ok if gone not in ptext else bad)("无空壳留位：%s" % gone)
(ok if "drawDag" in ptext else bad)("DAG 绘制函数存在")

print("\n[6] 前序能力保留")
if D:
    (ok if D["brain"]["health"]["score"] else bad)("大脑执行层健康维 %s 分" % D["brain"]["health"]["score"])
    (ok if D["device"]["bluetooth"]["ble_backend"] == "bleak" else bad)("蓝牙仍为 bleak")
    (ok if len(D["device"]["bluetooth"]["devices"]) == 5 else bad)("蓝牙五台设备仍在")

print("\n[7] 画布三层")
for k in ("01 项目背景", "02 设计系统", "03 设计稿"):
    (ok if k in ctext else bad)("标注「%s」" % k)
for q in ("是什么", "给谁用", "解决什么问题"):
    (ok if q in ctext else bad)("Row 1 回答「%s」" % q)
pages = re.findall(r"\['[^']+',\s*p\d+\(\)\]", ctext)
(ok if len(pages) >= 11 else bad)("Row 3 页面 %d 个" % len(pages))
for t in ("万能插 · 工作流与算子", "亿万触手 · 三通道与十域"):
    (ok if t in ctext else bad)("画布含「%s」" % t)

print("\n[8] 硬性要求 / 反 slop")
for bp in ("max-width:1439px", "max-width:1279px", "max-width:1023px", "max-width:767px"):
    (ok if bp in ptext else bad)("断点 %s" % bp)
(ok if len(re.findall(r"addEventListener\('click'", ptext)) >= 2 else bad)("可点击绑定")
(ok if "data-theme" in ptext and "aria-pressed" in ptext else bad)("主题 / 筛选状态")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")
for p in (CANVAS, PROTO):
    hits = EMOJI.findall(p.read_text(encoding="utf-8"))
    (ok if not hits else warn)("%s emoji %s" % (p.name, set(hits) if hits else "无"))
for tok in ("#6366f1", "#8b5cf6", "#7c3aed"):
    if tok in ptext or tok in ctext:
        bad("AI 默认靛紫 %s" % tok)
ok("无 AI 默认靛紫")
(ok if "lorem ipsum" not in (ptext + ctext).lower() else bad)("无 lorem ipsum")

print("\n[9] 结果")
print("  PASS %d · WARN %d · FAIL %d" % (len(oks), len(warns), len(fails)))
for f in fails:
    print("   - " + f)
sys.exit(1 if fails else 0)
