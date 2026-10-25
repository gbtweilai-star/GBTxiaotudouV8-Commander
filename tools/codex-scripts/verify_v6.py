# -*- coding: utf-8 -*-
"""V6 交付前自检：九块真面板（含新增语音 / 蓝牙）。"""
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
CANVAS = BASE / "V6 GBT小土豆V8-无限画布.html"
PROTO = BASE / "V6 GBT小土豆V8-可交互原型.html"
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
print("V6 交付前自检 · 九块真面板（+ 语音 / 蓝牙）")
print("=" * 78)

print("\n[1] 文件 / 版本 / 归档")
for p in (CANVAS, PROTO):
    (ok if p.exists() else bad)("%s · %d B" % (p.name, len(p.read_bytes()) if p.exists() else 0))
(ok if re.search(r"V6 ", CANVAS.name) and re.search(r"V6 ", PROTO.name) else bad)("版本一致（V6）")
arch = sorted(x.name for x in (BASE / "archive").glob("V* GBT*"))
(ok if len(arch) == 10 else bad)("archive/ 历史版本 %d 份（V1-V5 各 2）" % len(arch))
(ok if not list(BASE.glob("V[1-5] *.html")) else bad)("根目录只留活跃版本")

print("\n[2] JS 语法")
for p in (CANVAS, PROTO):
    js = p.read_text(encoding="utf-8")
    js = js[js.rindex("<script>") + 8:js.rindex("</script>")]
    f = BASE / ".scratch" / ("_v6chk_%s.js" % ("canvas" if p is CANVAS else "proto"))
    f.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    (ok if r.returncode == 0 else bad)("%s 语法（%d 字符）%s" % (p.name, len(js), (r.stderr or '').strip()[:140]))

ptext = PROTO.read_text(encoding="utf-8")
ctext = CANVAS.read_text(encoding="utf-8")

print("\n[3] 语音真读数")
m = re.search(r"const V6 = /\* real scan \+ brain \+ device snapshot \*/(\{.*?\});\n", ptext, re.S)
D = None
if not m:
    bad("未注入真实读数")
else:
    H = json.loads(m.group(1))
    D = H["device"]
    V = D["voice"]
    ok("TTS 后端：%s" % V["tts_backend"])
    ok("ASR 状态：%s（缺 %s）" % (V["asr_state"], V["asr_missing"]))
    ok("TTS 授权门实测：denied=%s · 缺 %s" % (V["tts_gate"]["denied"], V["tts_gate"]["missing"]))
    (ok if "audio_output" in (V["tts_gate"]["missing"] or []) else bad)("缺件名为 audio_output（真实）")
    (ok if "auth grant --scope audio_output" in ptext else bad)("授权命令原样上屏")
    ok("voice_orchestra 技能 %s 项（Whisper / %s …）" % (V["skills_total"], (V["skills"][1]["name"] if len(V["skills"]) > 1 else "—")))
    (ok if "只跑得动 2 项" in ptext else bad)("升格规则如实标注（不摆规划出口）")

print("\n[4] 蓝牙真读数")
if D:
    B = D["bluetooth"]
    (ok if B["ble_backend"] == "bleak" else bad)("BLE 后端已修复为 bleak（原 needs_dependency）")
    ok("经典栈：%s" % B["classic_backend"])
    ok("实测扫到 %d 台设备 · %sms" % (len(B["devices"]), B["scan_ms"]))
    addrs = [d["address"] for d in B["devices"]]
    (ok if len(addrs) == 5 else warn)("设备地址数 %d" % len(addrs))
    (ok if all(("'" + a + "'") in ptext or a in ptext for a in addrs) else bad)("五台真实地址全部上屏")
    (ok if "device_control" in (B["classic_gate"]["missing"] or []) else bad)("连接/读写缺件名为 device_control（真实）")
    (ok if "auth grant --scope device_control" in ptext else bad)("蓝牙授权命令上屏")
    ok("协议库 %d 条：%s" % (len(B["protocols"]), " / ".join(B["protocols"][:4])))
    (ok if "已修复" in ptext and "bleak" in ptext else bad)("界面标注本轮已修复")
    (ok if "回放" in ptext else bad)("扫描按钮如实标注为回放快照（不假装联网）")

print("\n[5] 九块真面板")
NAMES = ["对话", "能力广场", "大脑执行层", "领域分类", "审计台账", "语音", "蓝牙", "系统体检", "设置"]
for n in NAMES:
    (ok if ("'" + n + "'") in ptext else bad)("导航含「%s」" % n)
for fn in ("panelChat", "panelSquare", "panelBrain", "panelDomains", "panelAudit",
           "panelVoice", "panelBluetooth", "panelHealth", "panelSettings"):
    (ok if ("function " + fn) in ptext else bad)("实现 %s()" % fn)
for fn in ("voice", "bluetooth"):
    (ok if ("return panel" + fn.capitalize() + "();") in ptext else bad)("分发到 %s" % fn)
for gone in ("'智能体'", "'知识库'", "'工作流'", "'数据分析'", "'系统设置'", "尚未接入", "规划中"):
    (ok if gone not in ptext else bad)("无空壳留位：%s" % gone)

print("\n[6] 大脑执行层（V5 能力保留）")
if D:
    BD = H["brain"]
    ok("健康维 %s 分 %s/%s · 路由 %d 条 · 合一 %s s" % (
        BD["health"]["score"], BD["health"]["healthy"], BD["health"]["total"],
        len(BD["routes"]), BD["unify"]["elapsed_s"]))
    for part in ('class="flow"', 'class="pulse"', 'class="stagecard', 'class="routebar', 'class="trace"'):
        (ok if part in ptext else bad)("大脑可视化部件 %s" % part)

print("\n[7] 无限画布三层")
for k in ("01 项目背景", "02 设计系统", "03 设计稿"):
    (ok if k in ctext else bad)("标注「%s」" % k)
for q in ("是什么", "给谁用", "解决什么问题"):
    (ok if q in ctext else bad)("Row 1 回答「%s」" % q)
pages = re.findall(r"\['[^']+',\s*p\d+\(\)\]", ctext)
(ok if len(pages) >= 9 else bad)("Row 3 页面 %d 个" % len(pages))
for t in ("语音 · 听想说三段", "蓝牙 · 扫描与控制"):
    (ok if t in ctext else bad)("画布含「%s」" % t)

print("\n[8] 原型硬性要求 / 反 slop")
for bp in ("max-width:1439px", "max-width:1279px", "max-width:1023px", "max-width:767px"):
    (ok if bp in ptext else bad)("断点 %s" % bp)
(ok if len(re.findall(r"addEventListener\('click'", ptext)) >= 2 else bad)("可点击绑定")
(ok if "data-theme" in ptext and "aria-pressed" in ptext and "aria-current" in ptext else bad)("主题/筛选/当前项")
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

print("\n[9] 对比度（暗 / 亮双主题 ≥4.5:1）")


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
for name, fg, bg in [("暗·正文", DI, DB), ("暗·二级", over(.74, DI, DB), DB), ("暗·三级", over(.54, DI, DB), DB),
                     ("暗·霓虹", (0x2A, 0xD4, 0xF0), DB), ("暗·霓虹亮", (0x6E, 0xF2, 0xFF), DB),
                     ("暗·正常", (0x3D, 0xDC, 0x97), DB), ("暗·警告", (0xF5, 0xB5, 0x44), DB), ("暗·异常", (0xFF, 0x7A, 0x7A), DB),
                     ("亮·正文", LI, LB), ("亮·二级", over(.72, LI, LB), LB), ("亮·三级", over(.62, LI, LB), LB),
                     ("亮·霓虹", (0x0A, 0x7D, 0x94), LB), ("亮·正常", (0x0F, 0x6B, 0x41), LB),
                     ("亮·警告", (0x8A, 0x5A, 0x00), LB), ("亮·异常", (0xA3, 0x24, 0x1C), LB)]:
    r = ratio(fg, bg)
    (ok if r >= 4.5 else bad)("%s → %.2f:1" % (name, r))

print("\n[10] 结果")
print("  PASS %d · WARN %d · FAIL %d" % (len(oks), len(warns), len(fails)))
for f in fails:
    print("   - " + f)
sys.exit(1 if fails else 0)
