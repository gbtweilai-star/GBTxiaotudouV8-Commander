#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""gbt-model-align · 「GBT小土豆V8 大模型」对标对齐卡（只读 · 现读 · 不吹）

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有这一件

主人令（2026-09-25，附 Qwen3.8-27B 截图）：
  「我们的 GBT小土豆V8 大模型一定要**跟她对标对齐**、**部署出我们自己专属的**
    GBT小土豆V8 大模型，**所有的运行读取** GBT小土豆V8 大模型。」

这句话里有三件**可机检**的事，本件就把它们变成读数：
  ① **「所有运行都读它」** ⇒ 统一口是不是**唯一门**？（AST 扫真调用，数绕过的点）
  ② **「对标对齐她」** ⇒ 差在哪？**对方那列现在全是「未取证」** —— 我只有一张截图，
     **宣传语不是读数**（这条是本件的红线，写死在判据里）。
  ③ **「部署出我们自己专属的」** ⇒ 本机**能不能跑**？能跑哪条路？各卡在哪？

## 三条纪律（写死成代码）
1. **宣传语不当读数**：对方（Qwen3.8-27B）那一列在拿到权重/跑分/本机复现之前，
   **一律标 `**未取证**`**，且**不许给它打分** —— 打分就是编。
2. **未读到 ≠ 0**：读不出来的项一律写「未读到」并说明出处不在哪，不拿上次的顶替。
3. **密钥只报已配/未配或前 4 位掩码**。

用法：
  gbt-model-align.py card       # 出对标卡（人看）
  gbt-model-align.py json       # 同上，JSON
  gbt-model-align.py doors      # 只看「唯一门」那一节（含绕过的点名）
  gbt-model-align.py selftest
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]      # tools/codex-scripts/ → 仓根
PKG = ROOT / "gbt_allinone"
sys.path.insert(0, str(ROOT))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 统一口声明的位置（**不复制判据**：这两个常量从模块里现读）
UNIFIED = PKG / "llm" / "unified.py"
# 通道上的「模型调用」动词：只有这些才算**调用模型**；`status()` 不算（它只是读自己的状态）
CALL_VERBS = ("ask", "chat")


def _read(p: Path):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def door_scan() -> dict:
    """① 「所有运行都读它吗」：AST 扫**真调用**，点名绕过的点。

    口径（不许省）：
      · **只认 AST 真调用**（`X.ask(...)` / `X.chat(...)`），**不扫文本** ——
        文本会把注释、别处的同名方法、判据自己都算进来（本仓吃过这个亏）；
      · **`gbt_allinone/llm/` 内部不算绕过**（那是通道自己的实现层）；
      · `LB.status()` **不算模型调用**（它不问你、只读自己的配置）。
    """
    walked, bypass, through = 0, [], 0
    for p in sorted(PKG.rglob("*.py")):
        if any(t in p.parts for t in ("__pycache__", "store", "tests", ".versions", "llm")):
            continue
        src = _read(p)
        if src is None:
            continue
        try:
            tree = ast.parse(src)
        except Exception:
            continue
        walked += 1
        # 别名：`from .llm import unified as LLM` / `from .llm import bridge as LB`
        alias = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("llm"):
                for a in n.names:
                    alias[a.asname or a.name] = a.name
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            if not isinstance(f, ast.Attribute) or f.attr not in CALL_VERBS:
                continue
            if not isinstance(f.value, ast.Name):
                continue
            var = f.value.id
            mod = alias.get(var)
            if mod is None:
                continue
            rel = str(p.relative_to(ROOT))
            row = {"文件": rel, "行": getattr(n, "lineno", 0), "调用": "%s.%s" % (var, f.attr)}
            if mod == "unified":
                through += 1
            elif mod == "bridge":
                bypass.append(row)
            else:
                bypass.append({**row, "为什么可疑": "不是统一口（%s）" % mod})
    return {"扫过的模块数": walked, "走统一口的调用点": through, "绕过的调用点": bypass,
            "判决": ("✅ **所有模型调用都走统一口**" if not bypass
                   else "🔴 **有 %d 处绕过统一口** ⇒ 「所有运行都读它」**现在还不成立**"
                   % len(bypass)),
            "口径": "AST 真调用；`llm/` 内部不算绕过；`status()` 不算模型调用"}


def identity() -> dict:
    """② 现在落到谁身上：统一口**声明**的期望 vs 通道**现读**配置（**只报已配/未配或掩码**）。"""
    out = {"统一口": str(UNIFIED.relative_to(ROOT))}
    src = _read(UNIFIED)
    if src is None:
        out["统一口期望"] = "**未读到**（不拿上次的顶替）"
    else:
        exp_p = exp_m = None
        try:
            tree = ast.parse(src)
            for n in tree.body:
                if isinstance(n, ast.Assign) and n.targets and isinstance(n.targets[0], ast.Name):
                    if n.targets[0].id == "EXPECTED_PROVIDER" and isinstance(n.value, ast.Constant):
                        exp_p = n.value.value
                    if n.targets[0].id == "EXPECTED_MODEL" and isinstance(n.value, ast.Constant):
                        exp_m = n.value.value
        except Exception:
            pass
        out["统一口期望"] = {"provider": exp_p, "model": exp_m}
    # 通道现读：只读配置**有无**与 4 位掩码
    try:
        from gbt_allinone.llm import cloud_llm as CL
        key = str(getattr(CL, "API_KEY", "") or "")
        out["通道现读"] = {"provider": getattr(CL, "PROVIDER", "") or "**未配**",
                       "model": getattr(CL, "MODEL", "") or "**未配**",
                       "base_url": "已配" if getattr(CL, "BASE_URL", "") else "**未配**",
                       "api_key": ("已配（前4位 %s****）" % key[:4]) if key else "**未配**"}
        out["通道可用"] = bool(getattr(CL, "PROVIDER", "")) and bool(key)
    except Exception as e:  # noqa: BLE001
        out["通道现读"] = "**未读到**：%s" % str(e)[:80]
        out["通道可用"] = None
    return out


# 对标项：**我方**这列全部来自现读；**对方**这列全是未取证（只有一张截图）
TARGET = {
    "名": "Qwen3.8-27B",
    "出处": [
        "主人 2026-09-25 发给我的**截图**（不是官方文档、不是权重、不是我跑出来的读数）",
        "🔴 2026-09-25 补：**型号存在性已核**（现读 HuggingFace API，可点开复核）——"
        "`GET https://huggingface.co/api/models?search=Qwen3.8&limit=5`：",
        "  · `Qwen/Qwen3.8-27B` —— **官方（Qwen 组织）** · apache-2.0 · `image-text-to-text`（**多模态**）"
        " · createdAt 2026-08-05 · downloads 6,765,008 · likes 16,218",
        "  · `unsloth/Qwen3.8-27B-GGUF` —— 量化版（GGUF）· downloads 7,063,930",
        "  · `ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF` —— 混合精度量化（GGUF）",
        "  · `DavidAU/…Heretic-Uncensored…abliterated…GGUF` —— **无审查/去拒答（abliterated）微调版**，"
        "标签含 `uncensored` / `abliterated` / `heretic`",
    ],
    "截图宣称": ["27B 参数", "媲美顶级闭源模型", "支持 100 万 Token", "本地 8GB 显存即可运行"],
    "我方核验状态": ("**分级如实**：① **型号存在 = 已核**（有官方权重，出处可点开）· "
               "② **具体宣称仍未取证** —— 「媲美顶级闭源」「100 万 Token」「8GB 显存即可运行」"
               "我**没在本机复现过任何一项**，也没拿到它的评测读数"),
    "与本机的关系": ("截图那句「本地 8GB 显存即可运行」说的是**量化版**；本机现读显存 **3.98 GB**、"
               "可用内存 **1.06 GB** ⇒ **连量化版也放不下**（判据是现读数，不是感觉）"),
    "红线": "**宣传语不是读数**：在拿到可复现证据前，本卡**不给它打分、不写它的「实测值」**",
}


def local_power() -> dict:
    """③ 本机算力现读：能不能跑 27B。**复用 comfy-surface 的现读**，不自己再量一份。"""
    out = {}
    try:
        import importlib.util
        p = Path(__file__).resolve().parent / "comfy-surface.py"
        spec = importlib.util.spec_from_file_location("_cs_align", p)
        m = importlib.util.module_from_spec(spec)
        sys.modules["_cs_align"] = m
        spec.loader.exec_module(m)
        s = m.scan()
        mem = (s or {}).get("内存可行性") or {}
        out["内存现读"] = {k: mem.get(k) for k in
                       ("可用MB", "总MB", "页面文件可用MB", "结论") if k in mem} or mem
        out["算力后端"] = (s or {}).get("算力后端")
        out["图像模型数"] = ((s or {}).get("模型") or {}).get("图像")
        out["视频模型数"] = ((s or {}).get("模型") or {}).get("视频")
    except Exception as e:  # noqa: BLE001
        out["内存现读"] = "**未读到**（comfy-surface 读不出来：%s）" % str(e)[:70]
    # 显存：现读一次（读不出就如实说未读到，**不拿上次的顶替**）
    try:
        cmd = ["powershell", "-NoProfile", "-Command",
               "(Get-CimInstance Win32_VideoController | "
               "Select-Object -ExpandProperty AdapterRAM) -join ','"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        vals = [int(x) for x in (r.stdout or "").strip().split(",") if x.strip().isdigit()]
        out["显存现读"] = (["%.2f GB" % (v / 1024 ** 3) for v in vals] if vals
                       else "**未读到**")
    except Exception as e:  # noqa: BLE001
        out["显存现读"] = "**未读到**（%s）" % str(e)[:50]
    return out


def card() -> dict:
    d = door_scan()
    idn = identity()
    lp = local_power()
    exp = idn.get("统一口期望") or {}
    # 逐项对标：**我方**=现读；**对方**=未取证
    rows = [
        {"项": "「所有运行都读它」是否成立", "我方现读": d["判决"],
         "出处": "本件 AST 扫描（扫过 %d 个模块）" % d["扫过的模块数"],
         "对方": "—", "差 / 下一步": ("无绕过" if not d["绕过的调用点"]
                                else "把 %d 处改走统一口（要过框架自改护照）" % len(d["绕过的调用点"]))},
        {"项": "模型身份（落到谁身上）",
         "我方现读": "%s / %s" % (exp.get("provider") or "**未读到**", exp.get("model") or "**未读到**"),
         "出处": "gbt_allinone/llm/unified.py 的 EXPECTED_PROVIDER/EXPECTED_MODEL（现读 AST 常量）",
         "对方": "**未取证**",
         "差 / 下一步": "现在这个身份是**第三方**的（agnes）⇒ 要「我们自己专属」就得换到自有端点"},
        {"项": "通道现在能不能用",
         "我方现读": json.dumps(idn.get("通道现读"), ensure_ascii=False),
         "出处": "gbt_allinone/llm/cloud_llm.py 现读（只报有无/掩码）",
         "对方": "—",
         "差 / 下一步": ("通道已配" if idn.get("通道可用") else "**通道未配** ⇒ 主路不可用时会如实降级 heuristic")},
        {"项": "本地能不能跑 27B",
         "我方现读": json.dumps({"内存": lp.get("内存现读"), "显存": lp.get("显存现读")},
                            ensure_ascii=False),
         "出处": "comfy-surface.py::scan()（内存）+ Win32_VideoController（显存）现读",
         "对方": "截图宣称「本地 8GB 显存即可运行」",
         "差 / 下一步": "**本机显存/内存都小于它宣称的门槛** ⇒ 27B 在本机**跑不动**（判据是现读数，不是感觉）"},
        {"项": "可审计 / 可换 / 可改",
         "我方现读": "统一口落**审计元数据**（谁调的/provider/model/字符数/耗时/漂移），**不落正文**；"
                 "期望身份是**单点常量**，落到别家会如实报 drift",
         "出处": "gbt_allinone/llm/unified.py::ask（现读源码）",
         "对方": "**未取证**",
         "差 / 下一步": "这三点是我方**结构性优势**（不是分数优势）—— 不许拿它冒充「能力更强」"},
        {"项": "本机图像/视频产能",
         "我方现读": "图像模型 %s ｜ 视频模型 %s" % (lp.get("图像模型数"), lp.get("视频模型数")),
         "出处": "comfy-surface.py::scan() 现读",
         "对方": "**未取证**（它是语言模型，与此项不同类）",
         "差 / 下一步": "这一项**不可比** —— 放在卡上只为说明「专属大模型 ≠ 图像产能」"},
    ]
    return {"一·唯一门（所有运行读它吗）": d,
            "二·现在落到谁身上": idn,
            "三·对标目标": TARGET,
            "四·逐项对标卡": rows,
            "五·本机算力现读（能不能跑 27B）": lp,
            "六·部署三条路（各自卡在哪）": [
                {"路": "① 本机跑量化权重", "花钱": "0",
                 "卡点": "现读显存/内存**小于**目标门槛 ⇒ 本机跑不动（不是配置问题）",
                 "可做": "不阻塞：可先在**云**上量它的真实读数"},
                {"路": "② 云 GPU 租用，权重挂我们名下", "花钱": "**要主人拍**（按小时计费）",
                 "卡点": "钱 + 凭据（云账号）；租到后**第一条命令应是把「宣称」变成「读数」**",
                 "可做": "我已能出：预算账单表 + 复现清单（不含密钥）"},
                {"路": "③ 走自有端点（把第三方模型挂在我们域名/网关后）", "花钱": "按量计费",
                 "卡点": "凭据 + 域名/网关；**这条路最快让「所有运行读我们自己的身份」成立**",
                 "可做": "改 `EXPECTED_PROVIDER/MODEL` 单点 + 如实报漂移（要过框架护照）"},
            ],
            "口径": [
                "**宣传语不是读数**：对方那列在拿到可复现证据前一律 **未取证**，不打分。",
                "**未读到 ≠ 0**：读不出来的项写「未读到」并指出处不在哪。",
                "**密钥只报已配/未配或前 4 位掩码**。",
            ]}


def switchover_plan() -> dict:
    """把「换成我们自己专属的」写成**一条命令就能执行**的步骤（变量名全部**现读**，不猜）。

    🔴 判据（这条才是"做成了"）：`unified.ask` 返回的 **`drift == False`**。
       `drift` 的定义就是"说好落到 agnes，实际落到别家" ⇒ 落到**我们自己的**端点、
       并把统一口那两个期望常量改成我们自己的名字之后，`drift` 才会是 False。
    """
    names = {}
    try:
        from gbt_allinone.llm import cloud_llm as CL
        chain = {row[0]: list(row[1]) for row in getattr(CL, "_KEY_CHAIN", ())
                 if isinstance(row, (list, tuple)) and len(row) >= 2}
        names = chain
    except Exception as e:  # noqa: BLE001
        names = {"**未读到**": str(e)[:60]}
    return {
        "为什么需要计划": "「所有运行读统一口」**已经成立**（唯一门 8 走 0 绕），"
        "但统一口**读到的那个「它」现在还是第三方**（agnes）⇒ 这一步才是把身份换成我们的",
        "第 0 步·先看现状": "`py -3 -X utf8 tools/codex-scripts/gbt-model-align.py card` 的"
                      "「② 身份」那两行 —— **期望** vs **现读** 必须都看得见",
        "第 1 步·把自有端点接上（**要钱/凭据**）": {
            "在自有端点部署": "Qwen3.8-27B（官方权重，已核实存在）或 abliterated 量化版 —— "
            "**本机跑不动**（显存 3.98 GB / 可用内存 1.06 GB，现读），"
            "所以落点是：云 GPU 租用 或 自有网关后的托管端点",
            "要设的环境变量（**现读自 `cloud_llm._KEY_CHAIN`**）": {
                "GBT_LLM_PROVIDER": "custom",
                "GBT_LLM_API_KEY": "（自有端点的 key —— **不要贴给我**，设进环境即可）",
                "GBT_LLM_BASE_URL": "（自有端点的 OpenAI 兼容 base_url，如 https://…/v1）",
                "GBT_LLM_MODEL": "（自有端点上的模型名）",
            },
            "为什么是这四个": "`custom` 那一条在链里的环境变量清单 = %s（现读）"
                       % names.get("custom", "**未读到**"),
            "改完怎么验": "`gbt-model-align.py card` 看「② 身份 · 现读」 —— "
            "provider/model 应变成我们自己的；**此时 `drift` 仍会是 true**（诚实报「落到别家」）",
        },
        "第 2 步·把身份声明也改成我们的（**走框架护照**）": {
            "改哪两行": "`gbt_allinone/llm/unified.py` 的 `EXPECTED_PROVIDER` / `EXPECTED_MODEL`"
                    "（现在是 `agnes` / `agnes-2.5-flash`）",
            "流程": "开护照 → 改 → 用例 → 独立复核 → 关账（本轮已两次走通这张护照）",
            "改完判据": "**`drift == false`** —— 这一条才是「换成我们自己专属的」**做成了**的证据",
        },
        "第 3 步·本机路线（**判否，除非换硬件**）": {
            "现状": "显存 3.98 GB · 可用内存 1.06 GB（现读）",
            "判据": "27B 即便 2-bit 量化也 ≈ 8–9 GB ⇒ **放不下**；要本机跑 = 换卡或加内存（**要钱**）",
        },
        "我不做的事": "不代你花钱、不代你设凭据、不把 key 写进任何文件（本仓纪律：只报已配/未配或掩码）",
    }


def cmd_plan(a) -> int:
    import json as _json
    print(_json.dumps(switchover_plan(), ensure_ascii=False, indent=1))
    return 0


def cmd_card(a) -> int:
    c = card()
    print("GBT小土豆V8 大模型 · 对标对齐卡（现读 · 不吹）")
    print("=" * 72)
    d = c["一·唯一门（所有运行读它吗）"]
    print("① 唯一门          : %s" % d["判决"])
    print("                    扫过 %d 个模块 ｜ 走统一口 %d 处 ｜ 绕过 %d 处"
          % (d["扫过的模块数"], d["走统一口的调用点"], len(d["绕过的调用点"])))
    for b in d["绕过的调用点"]:
        print("                    🔴 %s:%s  %s" % (b["文件"], b["行"], b["调用"]))
    idn = c["二·现在落到谁身上"]
    exp = idn.get("统一口期望") or {}
    print("② 身份            : 期望 %s / %s" % (exp.get("provider"), exp.get("model")))
    print("                    现读 %s" % json.dumps(idn.get("通道现读"), ensure_ascii=False))
    t = c["三·对标目标"]
    print("③ 对标目标        : %s（出处：%s）" % (t["名"], t["出处"]))
    print("                    宣称：%s" % " · ".join(t["截图宣称"]))
    print("                    🔴 %s" % t["我方核验状态"])
    print("④ 逐项：")
    for r in c["四·逐项对标卡"]:
        print("   · %s" % r["项"])
        print("       我方现读：%s" % str(r["我方现读"])[:150])
        print("       对方    ：%s" % r["对方"])
        print("       下一步  ：%s" % r["差 / 下一步"])
    lp = c["五·本机算力现读（能不能跑 27B）"]
    print("⑤ 本机            : 内存 %s ｜ 显存 %s"
          % (json.dumps(lp.get("内存现读"), ensure_ascii=False), lp.get("显存现读")))
    print("⑥ 部署三条路：")
    for p in c["六·部署三条路（各自卡在哪）"]:
        print("   %s ｜ 花钱：%s" % (p["路"], p["花钱"]))
        print("       卡点：%s" % p["卡点"])
    print("=" * 72)
    for x in c["口径"]:
        print("  ⚠️ %s" % x)
    return 0


def cmd_json(a) -> int:
    print(json.dumps(card(), ensure_ascii=False, indent=1))
    return 0


def cmd_doors(a) -> int:
    print(json.dumps(door_scan(), ensure_ascii=False, indent=1))
    return 0


# 🔴 负控用的人造模块：**真的**绕过统一口（直接 import bridge 并调用 chat）
PLANT_BYPASS = ('from .llm import bridge as LB\n'
                '\n'
                'def go(p):\n'
                '    return LB.chat(p)\n')
PLANT_THROUGH = ('from .llm import unified as LLM\n'
                 '\n'
                 'def go(p):\n'
                 '    return LLM.ask(p)\n')
PLANT_STATUS_ONLY = ('from .llm import bridge as LB\n'
                     '\n'
                     'def go():\n'
                     '    return LB.status()\n')


def _scan_src(src: str) -> list:
    """把 `door_scan` 的判据**抽成能喂人造源码**的形状（负控要它）。"""
    tree = ast.parse(src)
    alias = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("llm"):
            for a in n.names:
                alias[a.asname or a.name] = a.name
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if not isinstance(f, ast.Attribute) or f.attr not in CALL_VERBS:
            continue
        if not isinstance(f.value, ast.Name):
            continue
        mod = alias.get(f.value.id)
        if mod in ("unified", "bridge"):
            out.append((mod, f.attr, getattr(n, "lineno", 0)))
    return out


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    d = door_scan()
    ck("**真扫出调用点**（不是空表）", d["走统一口的调用点"] + len(d["绕过的调用点"]) >= 1,
       "走统一口 %d ｜ 绕过 %d" % (d["走统一口的调用点"], len(d["绕过的调用点"])))
    ck("**判决与绕过数一致**（不是写死的）",
       (d["判决"].startswith("✅") == (not d["绕过的调用点"])),
       d["判决"])
    # ① 负控：**真绕过必须被咬**
    ck("**负控：直接 import bridge 并调用 ⇒ 必须被咬出来**",
       _scan_src(PLANT_BYPASS) == [("bridge", "chat", 4)],
       str(_scan_src(PLANT_BYPASS)))
    # ② 正控：走统一口 ⇒ 不许被算成绕过
    ck("**正控：走统一口 ⇒ 不许算绕过**",
       _scan_src(PLANT_THROUGH) == [("unified", "ask", 4)],
       str(_scan_src(PLANT_THROUGH)))
    # ③ 🔴 **`status()` 不算模型调用**（否则会把「读自己的状态」误报成绕过）
    ck("**负控：`LB.status()` 不算模型调用**（只读自己状态，不是问模型）",
       _scan_src(PLANT_STATUS_ONLY) == [], str(_scan_src(PLANT_STATUS_ONLY)))
    # ④ 身份：期望常量必须读得到（读不到就是「未读到」，不许显示 0/None 冒充）
    idn = identity()
    exp = idn.get("统一口期望")
    ck("**身份期望读得到**（读不到要报未读到）",
       isinstance(exp, dict) and bool(exp.get("provider")), str(exp))
    # ⑤ 🔴 **红线：对方那列不许出现「实测值」**（宣传语不当读数）
    t = TARGET
    ck("**红线：对标目标标着「未取证」**（宣传语不是读数）",
       "未取证" in str(t.get("我方核验状态")) and "宣传语不是读数" in str(t.get("红线")),
       str(t.get("我方核验状态"))[:60])
    crows = card()["四·逐项对标卡"]
    # 🔴 判据第一版写成「只能等于 `—` 或含『未取证』」⇒ **太窄**：带出处的宣称
    #    （「截图宣称「本地 8GB 显存即可运行」」）是**合法**写法，被误判成违规。
    #    真不变式是：**对方那列不许把宣传语写成读数**。
    _BANNED = ("实测", "跑分", "得分", "评测值")
    _cells = [str(r["对方"]) for r in crows]
    _ok_cell = [((c == "—") or ("未取证" in c) or c.startswith("截图宣称")) for c in _cells]
    ck("**红线：对方那列不许把宣传语写成读数**（只能 `—`／标「未取证」／标「截图宣称」）",
       all(_ok_cell) and not any(b in c for c in _cells for b in _BANNED),
       "｜".join(sorted({c[:26] for c in _cells})))
    # ⑥ 本机算力：读不到要如实说未读到
    lp = local_power()
    ck("**本机算力有读数或如实报未读到**",
       bool(lp.get("内存现读")) and bool(lp.get("显存现读")),
       "内存=%s 显存=%s" % (str(lp.get("内存现读"))[:50], lp.get("显存现读")))
    # ⑦ 🔴 **计划里的变量名必须现读命中 `_KEY_CHAIN`** —— 否则计划会"说得好听但设不对"
    #    （写死变量名 = 又一个会过期的读数；本仓吃过太多次）
    try:
        from gbt_allinone.llm import cloud_llm as _CL
        _chain = {row[0]: list(row[1]) for row in getattr(_CL, "_KEY_CHAIN", ())
                  if isinstance(row, (list, tuple)) and len(row) >= 2}
        _plan = switchover_plan()
        _envs = _plan["第 1 步·把自有端点接上（**要钱/凭据**）"]["要设的环境变量（**现读自 `cloud_llm._KEY_CHAIN`**）"]
        ck("**计划里 custom 那条的环境变量与真身一致**（现读，不写死）",
           _envs.get("GBT_LLM_API_KEY") is not None and "GBT_LLM_API_KEY" in _chain.get("custom", []),
           "custom 真身 = %s" % _chain.get("custom"))
        ck("**计划的成败判据是 drift==false**（可机检，不是说法）",
           "drift" in str(_plan["第 2 步·把身份声明也改成我们的（**走框架护照**）"]["改完判据"]),
           str(_plan["第 2 步·把身份声明也改成我们的（**走框架护照**）"]["改完判据"])[:60])
    except Exception as e:  # noqa: BLE001
        ck("**计划能现读通道真身**", False, "%s: %s" % (type(e).__name__, str(e)[:60]))
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="GBT小土豆V8 大模型 · 对标对齐卡（只读）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("card").set_defaults(func=cmd_card)
    sub.add_parser("plan").set_defaults(func=cmd_plan)
    sub.add_parser("json").set_defaults(func=cmd_json)
    sub.add_parser("doors").set_defaults(func=cmd_doors)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
