# -*- coding: utf-8 -*-
"""V8 交付前自检：十九块真面板（30 域全覆盖）。"""
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

# 本目录自 .scratch/ 迁到 tools/codex-scripts/ 后深度 +1：原来的 .parent.parent
# 落在 …\tools\（tools 下 0 个 html，实测 FileNotFoundError）。向上找根标记。
BASE = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
# V8 早已从根目录移入 archive/，历史版本的自检要能重跑就得允许指到归档目录。
import os as _os  # noqa: E402
if _os.environ.get("GBT_DELIVERABLE_DIR"):
    BASE = BASE / _os.environ["GBT_DELIVERABLE_DIR"]
CANVAS = BASE / "V8 GBT小土豆V8-无限画布.html"
PROTO = BASE / "V8 GBT小土豆V8-可交互原型.html"
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
print("V8 交付前自检 · 十九块真面板")
print("=" * 78)

print("\n[1] 文件 / 版本 / 归档")
for p in (CANVAS, PROTO):
    (ok if p.exists() else bad)("%s · %d B" % (p.name, len(p.read_bytes()) if p.exists() else 0))
(ok if re.search(r"V8 ", CANVAS.name) and re.search(r"V8 ", PROTO.name) else bad)("版本一致（V8）")
arch = sorted(x.name for x in (BASE / "archive").glob("V* GBT*"))
(ok if len(arch) == 14 else bad)("archive/ 历史 %d 份（V1-V7 各 2）" % len(arch))
(ok if not list(BASE.glob("V[1-7] *.html")) else bad)("根目录只留活跃版本")

print("\n[2] JS 语法")
for p in (CANVAS, PROTO):
    t = p.read_text(encoding="utf-8")
    js = t[t.rindex("<script>") + 8:t.rindex("</script>")]
    f = BASE / ".scratch" / ("_v8chk_%s.js" % ("canvas" if p is CANVAS else "proto"))
    f.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    (ok if r.returncode == 0 else bad)("%s 语法（%d 字符）%s" % (p.name, len(js), (r.stderr or '').strip()[:140]))

ptext = PROTO.read_text(encoding="utf-8")
ctext = CANVAS.read_text(encoding="utf-8")

print("\n[3] 缺口数据真读数")
m = re.search(r"const V8 = /\* full snapshot incl\. gap domains \*/(\{.*?\});\n", ptext, re.S)
G = None
if not m:
    bad("未注入缺口数据")
else:
    G = json.loads(m.group(1))["gaps"]
    mp = G["mirror_pipeline"]
    ok("镜像 %s 文件 ↔ 现实 %s 文件（v%s）· scan %s/%s · 服务 %d 个"
       % ((mp["mirror_status"]["dimension"] or {}).get("files"),
          (mp["mirror_status"]["reality"] or {}).get("files"),
          (mp["mirror_status"]["reality"] or {}).get("version"),
          mp["mirror_scan"]["passed"], mp["mirror_scan"]["total"], len(mp["services"])))
    (ok if len(mp["mirror_scan"]["checks"]) == 5 else bad)("镜像体检 %d 项（应 5）" % len(mp["mirror_scan"]["checks"]))
    (ok if mp["ghost_guard"]["clean"] else warn)("幽灵守卫 clean")
    lc = G["llm_channel"]
    ok("密钥链 %d 级 · 提示词 %d 段 · Codex connected=%s"
       % (len(lc["llm_status"]["key_chain"]), len(lc["prompt_bridge"]["segments"]),
          lc["codex_status"]["connected"]))
    (ok if "external_llm" in (lc["codex_models_gate"]["missing"] or []) else bad)("codex_models 缺件名 external_llm（真实）")
    mm = G["mind_memory"]
    ok("心智 %s/%s/%s · 脑库 notes %s wikilinks %s · 红线 %d 条"
       % (mm["mind"]["state"], mm["mind"]["mood"], mm["mind"]["expression"],
          mm["brain_vault"]["notes"], mm["brain_vault"]["wikilinks"], len(mm["meta_cognition"]["red_lines"])))
    sc = G["security"]
    (ok if sc["sec_scan"]["total"] == 743 and sc["sec_scan"]["critical"] == 33 else bad)(
        "安全扫描 total=%s critical=%s" % (sc["sec_scan"]["total"], sc["sec_scan"]["critical"]))
    (ok if (sc["sec_surface"]["attack_surface"] or {}).get("entry_points") == 785 else bad)(
        "攻击面入口 %s" % (sc["sec_surface"]["attack_surface"] or {}).get("entry_points"))
    lt = G["longrun_tools"]
    (ok if lt["lr_progress"]["total"] == 58 and lt["lr_progress"]["done"] == 33 else bad)(
        "长程任务 %s（done %s / failed %s）" % (lt["lr_progress"]["total"], lt["lr_progress"]["done"],
                                          lt["lr_progress"]["failed"]))
    (ok if len(lt["capability_net"]["seven_columns"]) == 7 else bad)(
        "穿透网七栏 %d 个" % len(lt["capability_net"]["seven_columns"]))
    # 只查清单条数会漏掉「清单 7 条、画布只画 5 行」：旧画布把 7 栏手写死成 5 项，
    # 标题仍写「七栏」，本行照样 PASS。必须比「清单 ←→ 画布渲染」两侧。
    _sc = lt["capability_net"]["seven_columns"]
    _miss = [k for k in _sc if k not in ctext]
    (ok if not _miss else bad)(
        "画布卡片渲染全部 %d 栏（缺 %s）" % (len(_sc), _miss or "无"))
    cd = G["creation_devour"]
    ok("场景 %d 大类 · 能力质量均分 %s · 吞噬缺口 %s"
       % (len(cd["scene_anchor"]["classes"]), cd["devour_reflect"]["cap_quality_summary"]["avg_score"],
          [x["domain"] for x in cd["devour_scan"]["gaps"]]))
    ot = G["others"]
    (ok if ot["life"]["events"] == 168 else bad)("生命档案 events %s" % ot["life"]["events"])
    (ok if len(ot["gate_visibility"]["states"]) == 3 else bad)("门三态 %d 个" % len(ot["gate_visibility"]["states"]))
    (ok if ot["quant"]["exists"] else warn)("量化工作区存在=%s" % ot["quant"]["exists"])

print("\n[4] 十九块真面板 · 缺口全补")
NAMES = ["对话", "能力广场", "大脑执行层", "领域分类", "审计台账", "语音", "蓝牙", "万能插", "亿万触手",
         "镜像与晋升", "大模型通道", "心智与记忆", "情报与观察", "安全攻防", "长程与工具", "创作与吞噬", "其余域",
         "系统体检", "设置"]
for n in NAMES:
    (ok if ("'" + n + "'") in ptext else bad)("导航含「%s」" % n)
FNS = ["panelChat", "panelSquare", "panelBrain", "panelDomains", "panelAudit", "panelVoice",
       "panelBluetooth", "panelPlug", "panelTentacle", "panelMirror", "panelLLM", "panelMind",
       "panelRecon", "panelSecurity", "panelLongrun", "panelCreate", "panelOthers",
       "panelHealth", "panelSettings"]
for fn in FNS:
    (ok if ("function " + fn) in ptext else bad)("实现 %s()" % fn)
n_panel = len(re.findall(r"function panel[A-Z]\w+\(", ptext))
(ok if n_panel == 19 else bad)("面板函数共 %d 个（应 19）" % n_panel)
for gone in ("'智能体'", "'知识库'", "'工作流'", "'数据分析'", "'系统设置'", "尚未接入", "规划中"):
    (ok if gone not in ptext else bad)("无空壳留位：%s" % gone)

print("\n[5] 30 域覆盖核对")
if G:
    H = json.loads(m.group(1))
    doms = [d["name"] for d in H["domains"]]
    (ok if len(doms) == 30 else bad)("注册域 %d 个" % len(doms))
    panel_src = ptext
    covered = 0
    detail = []
    ALIAS = {"system": "系统体检", "llm": "大模型通道", "pipeline": "镜像与晋升", "engine": "万能插",
             "creation": "创作与吞噬", "recon": "情报与观察", "tentacle": "亿万触手", "mind": "心智与记忆",
             "data": "审计台账", "security": "安全攻防", "devour": "创作与吞噬", "finance": "其余域",
             "longrun": "长程与工具", "tools": "长程与工具", "video": "其余域", "brain": "心智与记忆",
             "device": "蓝牙", "project": "其余域", "voice": "语音", "automation": "其余域",
             "collab": "其余域", "comms": "其余域", "digital_human": "其余域", "framework": "其余域",
             "image_video": "其余域", "infra": "其余域", "integration": "其余域", "life": "其余域",
             "social": "其余域", "vision": "其余域"}
    for d in doms:
        if ALIAS.get(d) and panel_src.count("'" + ALIAS[d] + "'"):
            covered += 1
        else:
            detail.append(d)
    (ok if covered == 30 else bad)("30 域全部有归属面板（%d/30）%s" % (covered, detail or ""))

print("\n[6] 画布")
for k in ("01 项目背景", "02 设计系统", "03 设计稿"):
    (ok if k in ctext else bad)("标注「%s」" % k)
for q in ("是什么", "给谁用", "解决什么问题"):
    (ok if q in ctext else bad)("Row 1 回答「%s」" % q)
pages = re.findall(r"\['[^']+',\s*p\d+\(\)\]", ctext)
(ok if len(pages) >= 19 else bad)("Row 3 页面 %d 个" % len(pages))
for t in ("镜像与晋升 · 对账与巡检", "安全攻防 · 743 项扫描", "其余域 · 一次盘完"):
    (ok if t in ctext else bad)("画布含「%s」" % t)

print("\n[7] 硬性要求 / 反 slop")
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
size_kb = len(PROTO.read_bytes()) / 1024
(ok if size_kb < 800 else warn)("原型体积 %.0f KB（<800 合理）" % size_kb)

print("\n[8] 结果")
print("  PASS %d · WARN %d · FAIL %d" % (len(oks), len(warns), len(fails)))
for f in fails:
    print("   - " + f)
sys.exit(1 if fails else 0)
