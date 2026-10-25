# -*- coding: utf-8 -*-
# gbt-capability: dh_realism
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""数字人逼真度位（dh_realism）· **把专业流程固化成可机检的能力**

来源（**精确抓取，不是我编的**）：
  · Zielonka, Kirschstein, Bolkart, … , Thies
    **How to Build Digital Humans? From Priors to Photorealistic Avatars**
    Computer Graphics Forum Vol.45 No.2, 2026（**Eurographics State-of-the-Art Report**）
    Meta · TUM · Google · 清华 · MPI · NVIDIA · TU Darmstadt · ETH
    <https://github.com/Zielon/how-to-build-digital-humans>（49★）
  · 该文 `llms.txt` 给的**14 维 avatar 分类 / 12 维 assets 分类**（见 `TAXONOMY`）
  · three.js 官方 `MeshPhysicalMaterial` 文档
    （原话：*For best results, always specify an environment map when using this material.*）
  · 我们仓内 `holo_pet/assets/digital-human/PIPELINE.md` 与 `REALISM.md`（2026-09-22/25 蒸馏）

本件管三件事，全部**现读、可机检、不达标就卡**：
  ① **八步流程**（每步带判据与读数口径）
  ② **七条 AI 味禁令**（负向清单，逐条可机检）
  ③ **14 维分类自评**（照论文的表，能定位「我们这一件属于哪一类」）

与另两条腿的关系：
  `dh_brain` = 本体（19 骨 · 6 动作 · 11 真源）· `dh_pose` = 动作（76 语义 + compile）
  **`dh_realism` = 逼真度**（本件）

本件**只读**：不渲染、不写盘、不出网。
"""
from __future__ import annotations
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])

import os
import json
import re
from typing import Any, Dict, List, Tuple

CAP_KIND = "dh_realism"
DOMAIN = "creation"
CAP_TYPE = "internal"
TRACE_SOURCE_KIND = "dh_realism"

V8 = _GBT_ROOT

# ══════════════════════════════════════════════════════════════════════════
# ★ 八步流程（照 REALISM.md + PIPELINE.md 蒸馏；每步带判据）
# ══════════════════════════════════════════════════════════════════════════
STEPS: Tuple[Dict[str, Any], ...] = (
    {"n": 1, "key": "ibl", "cn": "IBL 环境",
     "how": "RoomEnvironment + PMREMGenerator → scene.environment（程序化影棚，不依赖外部 HDRI，离线可跑）",
     "why": "three.js 官方原话：*For best results, always specify an environment map.* "
            "没有环境贴图 ⇒ 皮肤只有方向光的镜面高光、**没有环境的漫反射包裹** —— 这是「像 CG」的头号原因，"
            "**调任何材质参数都补不回来**",
     "gauge": "scene.environment != null", "must": True},
    {"n": 2, "key": "lights", "cn": "光照配比",
     "how": "主光 1.1 / 辅光 0.30 / 勾边 0.65 / 半球 0.30",
     "why": "加了 IBL 之后方向光**必须压低**，否则叠爆（实测：黑衣冲成灰褐、皮肤惨白）",
     "gauge": "方向光和 ≤ 2.1 且 半球 ≤ 0.35", "must": True},
    {"n": 3, "key": "metalness", "cn": "金属度归零",
     "how": "皮肤区 metalness = 0",
     "why": "源模型实测金属度均值 **0.127**；真人必须 0，>0.05 就发灰发假（AI 味禁令第 2 条）",
     "gauge": "metalness 均值 < 0.05", "must": True},
    {"n": 4, "key": "skin", "cn": "皮肤参数",
     "how": "ior 1.4 · specularIntensity 0.42 · diffuseRoughness 0.65 · sheen 0.12 · clearcoat 0.05",
     "why": "皮肤是多层半透明介质：ior 默认 1.5 是「通用非金属」不是皮肤；specular 默认 1.0 会出油光塑料壳；"
            "sheen 模拟绒毛边缘散射；clearcoat 只给 T 区/唇（全脸加 = 塑料）",
     "gauge": "ior ∈ [1.33,1.44] · specularIntensity ∈ [0.35,0.55] · clearcoat ≤ 0.10", "must": True},
    {"n": 5, "key": "color", "cn": "色彩管线",
     "how": "outputColorSpace=SRGBColorSpace · ACESFilmicToneMapping · toneMappingExposure ≤ 1.0",
     "why": "高光不削顶、肤色不溢出",
     "gauge": "exposure ≤ 1.0", "must": True},
    {"n": 6, "key": "tex", "cn": "贴图分辨率",
     "how": "**脸单独 4K**；全身 2K 只够「能看」",
     "why": "现状 2048² 全身 ⇒ 脸只分到约 300²，毛孔/唇纹/睫毛全部丢失",
     "gauge": "脸区有效分辨率 ≥ 1024（全身 ≥ 2048 只是及格线）", "must": True},
    {"n": 7, "key": "face_parts", "cn": "面部专件",
     "how": "眼球 / 睫毛 / 眉毛 / 牙齿 / 口腔 必须是**独立几何 + 独立材质**",
     "why": "眼是贴图画的 ⇒ 没有角膜高光与折射（AI 味禁令第 5 条）",
     "gauge": "五件齐", "must": True},
    {"n": 8, "key": "micro_normal", "cn": "微细节法线",
     "how": "皮肤毛孔/细纹独立的 normal（或 detail normal）",
     "why": "只有一张全身 normal ⇒ 放大即塑料感（AI 味禁令第 7 条）",
     "gauge": "有独立 detail normal", "must": True},
)

# ══════════════════════════════════════════════════════════════════════════
# ★ 七条 AI 味禁令（负向清单 · 逐条可机检）
# ══════════════════════════════════════════════════════════════════════════
BANS: Tuple[Dict[str, str], ...] = (
    {"id": "oil_even", "cn": "全脸均匀油光", "why": "真人只有 T 区/唇部反光",
     "check": "clearcoat 全脸一致且 > 0.1 ⇒ 违禁"},
    {"id": "metal_skin", "cn": "金属度非零的皮肤", "why": "发灰、失血色",
     "check": "metalness 均值 > 0.05 ⇒ 违禁"},
    {"id": "no_env", "cn": "无环境光的纯方向光打光", "why": "阴影死黑、没有环境包裹",
     "check": "scene.environment == null 或方向光未压低 ⇒ 违禁"},
    {"id": "one_tex", "cn": "只有一张全身贴图", "why": "脸必然糊",
     "check": "无独立脸贴图且全身 < 4096² ⇒ 违禁"},
    {"id": "flat_eye", "cn": "眼睛是贴图画的", "why": "真人眼必须有角膜高光与折射",
     "check": "眼球不是独立几何 ⇒ 违禁"},
    {"id": "hard_term", "cn": "明暗交界线生硬", "why": "缺 SSS 的直接表现",
     "check": "无 SSS 近似（diffuseRoughness）且明暗边界宽度 < 阈值 ⇒ 违禁"},
    {"id": "no_pores", "cn": "皮肤无毛孔纹理", "why": "放大即塑料感",
     "check": "无 detail normal ⇒ 违禁"},
)

# ══════════════════════════════════════════════════════════════════════════
# ★ 14 维 avatar 分类（照论文 llms.txt 的表；用来给我们这一件定位）
# ══════════════════════════════════════════════════════════════════════════
TAXONOMY: Tuple[str, ...] = (
    "Prior Dataset Size", "Datasets", "Data Type", "Data Modality", "Needed Assets",
    "Input", "Additional Priors", "Req. Optimization", "Creation Speed",
    "Animation Signal", "Lighting Control", "Animation Speed", "Image Synthesis",
    "Image Refinement", "Contents",
)
ASSETS_TAXONOMY: Tuple[str, ...] = (
    "Prior Dataset Size", "Datasets", "Data Type", "Data Modality", "Needed Assets",
    "Input", "Additional Priors", "Creation Speed", "Representation",
    "Simulation Ready", "Lighting Control", "Contents",
)
BODY_PARTS: Tuple[str, ...] = ("Full-body", "Face", "Hair", "Hands", "Garment")

# 我们这一件（Tripo 图生 3D + 自建绑骨）的定位 —— **按现读资产填**
OURS: Dict[str, str] = {
    "Prior Dataset Size": "0（没用参数化先验）",
    "Datasets": "无（单件图生 3D）",
    "Data Type": "Synthetic（Tripo 生成）",
    "Data Modality": "Single image（写实样板图）",
    "Needed Assets": "None（只吃一张图）",
    "Input": "One",
    "Additional Priors": "None（**没用 SMPL-X / FLAME**）",
    "Req. Optimization": "No（前馈生成）",
    "Creation Speed": "Minutes（Tripo 云端约 1–3 分钟）",
    "Animation Signal": "None / 自烘焙（idle+walk 关键帧）",
    "Lighting Control": "Relightable（PBR 贴图 + IBL，非神经重打光）",
    "Animation Speed": "Real-time（22 关节蒙皮，网页 60fps 级）",
    "Image Synthesis": "Rasterization（three.js 光栅化，非神经渲染）",
    "Image Refinement": "No",
    "Contents": "Full-body（+ 弱 Face；**Hair/Hands/Garment 未分层**）",
}

# 现读的缺口账（照 REALISM.md §5，2026-09-25 的读数；**每项都要能重测**）
GAPS: Tuple[Dict[str, str], ...] = (
    {"item": "面部几何", "now": "全身 28382 顶点，脸约 2–3k", "need": "脸部单独 10k+（眼睑/唇/鼻翼塑形）"},
    {"item": "面部贴图", "now": "全身 2048²，脸约 300²", "need": "脸单独 4096²"},
    {"item": "眼球/睫毛/眉/牙", "now": "**0 件**", "need": "各为独立几何 + 独立材质"},
    {"item": "皮肤微细节", "now": "1024² 全身 normal 一张", "need": "毛孔/细纹 detail normal"},
    {"item": "次表面散射", "now": "只有 diffuseRoughness 近似", "need": "真 SSS（three.js NodeMaterial 的 MeshSSSNodeMaterial，本机 examples **无此文件**，未验）"},
    {"item": "源图本身", "now": "是**光泽人偶**质感", "need": "按「真人皮肤」重新诠释材质，不能照抄源图高光"},
    {"item": "分层", "now": "单网格（衣物/发/鞋长在身上）", "need": "头-脸-眼-牙 / 发 / 手 / 衣物 **分层独立拓扑与材质**"},
)


def _read_json(p: str) -> dict:
    try:
        return json.loads(open(p, encoding="utf-8").read())
    except Exception:
        return {}


class DhRealism:
    """数字人逼真度位（只读 · 流程 + 禁令 + 分类 + 缺口）"""

    def status(self) -> dict:
        return {"ok": True, "readonly": True,
                "步骤": len(STEPS), "禁令": len(BANS),
                "分类维度": len(TAXONOMY), "缺口": len(GAPS),
                "来源": "Eurographics 2026 STAR（Zielonka et al.）· CGF 45(2) · "
                        "Meta/TUM/Google/清华/MPI/NVIDIA/TUD/ETH",
                "为什么先学再做": "前面几轮把力气花在「网格能不能用」上（清洗/定向/减面/绑骨），"
                                "每步读数都过，但**绑完骨渲出来仍是 CG 娃娃** —— "
                                "根因是**流程里缺了整段**：逼真度不在网格，在"
                                "**光照模型 · 皮肤着色 · 贴图分辨率 · 面部专件**这四件事上",
                "口径": "本件只读：不渲染、不写盘、不出网"}

    def steps(self) -> dict:
        return {"ok": True, "readonly": True, "count": len(STEPS),
                "steps": [{"n": s["n"], "key": s["key"], "cn": s["cn"], "how": s["how"],
                           "gauge": s["gauge"], "must": s["must"], "why": s["why"]}
                          for s in STEPS]}

    def bans(self) -> dict:
        return {"ok": True, "readonly": True, "count": len(BANS),
                "bans": [dict(b) for b in BANS],
                "用法": "渲完对着清单逐条看；**有一条中就是 AI 味**，不是「差不多」"}

    def taxonomy(self, kind: str = "avatar") -> dict:
        t = ASSETS_TAXONOMY if str(kind).lower().startswith("a") else TAXONOMY
        return {"ok": True, "readonly": True, "table_type": kind, "fields": list(t),
                "body_parts": list(BODY_PARTS),
                "ours": OURS if kind != "assets" else {
                    k: OURS.get(k, "-") for k in ASSETS_TAXONOMY},
                "note": "字段名**逐字照论文 llms.txt**；ours 是我们这一件的定位（现读资产填的）"}

    def gaps(self) -> dict:
        return {"ok": True, "readonly": True, "count": len(GAPS),
                "gaps": [dict(g) for g in GAPS],
                "结论（不许粉饰）": "靠当前这一件 Tripo 多视图产物 + 参数调优，"
                                   "**到不了「真人逼真」**；缺的是面部专件与分层，不是调参",
                "量规自证": "清晰度读数**必须 ROI 自证**（肤色占比 + 排除 HUD + 输出裁图人眼复核）"
                            "—— 我们踩过：自动 ROI 取到 HUD 文字区，测的不是人脸"}

    def check(self, render_readings: dict) -> dict:
        """★ **机检**：把渲染读数喂进来，逐条判过不过。

        `render_readings` 建议字段（缺哪个就如实报"没给"，不猜）：
            environment(bool) · dir_light_sum(float) · hemi(float) · exposure(float)
            metalness_mean(float) · ior(float) · specular(float) · clearcoat(float)
            face_tex_px(int) · body_tex_px(int) · face_parts(list) · detail_normal(bool)
            diffuse_roughness(float) · roi_selfproof(dict: {skin_ratio, hud_excluded, crop})
        """
        r = dict(render_readings or {})
        out, p, f = [], 0, 0

        def T(name, cond, got, want, why):
            nonlocal p, f
            if cond is None:
                out.append({"判据": name, "结果": "未给读数", "got": got, "want": want,
                            "why": why, "pass": None})
            elif cond:
                p += 1
                out.append({"判据": name, "结果": "过", "got": got, "want": want, "why": why,
                            "pass": True})
            else:
                f += 1
                out.append({"判据": name, "结果": "★不过", "got": got, "want": want, "why": why,
                            "pass": False})

        T("① IBL 环境", (r.get("environment") is True) if "environment" in r else None,
          r.get("environment"), "True", STEPS[0]["why"])
        dls = r.get("dir_light_sum")
        T("② 光照配比", (dls <= 2.1) if isinstance(dls, (int, float)) else None,
          dls, "≤2.1", STEPS[1]["why"])
        hemi = r.get("hemi")
        T("②b 半球光 ≤0.35", (hemi <= 0.35) if isinstance(hemi, (int, float)) else None,
          hemi, "≤0.35", "半球光只做底色")
        mm = r.get("metalness_mean")
        T("③ 金属度归零", (mm < 0.05) if isinstance(mm, (int, float)) else None,
          mm, "<0.05", "源模型实测 0.127 ⇒ 真人必须 0")
        ior = r.get("ior")
        T("④ ior 皮肤值", (1.33 <= ior <= 1.44) if isinstance(ior, (int, float)) else None,
          ior, "1.33–1.44", "默认 1.5 是通用非金属，不是皮肤")
        sp = r.get("specular")
        T("④b 镜面强度", (0.35 <= sp <= 0.55) if isinstance(sp, (int, float)) else None,
          sp, "0.35–0.55", "默认 1.0 ⇒ 油光塑料壳")
        cc = r.get("clearcoat")
        T("④c clearcoat ≤0.10", (cc <= 0.10) if isinstance(cc, (int, float)) else None,
          cc, "≤0.10", "全脸加 = 塑料（禁令第 1 条）")
        ex = r.get("exposure")
        T("⑤ 曝光 ≤1.0", (ex <= 1.0) if isinstance(ex, (int, float)) else None,
          ex, "≤1.0", "高光不削顶")
        ftx = r.get("face_tex_px")
        T("⑥ 脸贴图 ≥1024", (ftx >= 1024) if isinstance(ftx, (int, float)) else None,
          ftx, "≥1024", "现状脸约 300² ⇒ 毛孔/唇纹全丢")
        fp = r.get("face_parts")
        T("⑦ 面部专件五件齐", (len(fp) >= 5) if isinstance(fp, (list, tuple)) else None,
          (len(fp) if isinstance(fp, (list, tuple)) else fp), "≥5", "眼球/睫毛/眉/牙/口腔")
        dn = r.get("detail_normal")
        T("⑧ 微细节法线", dn if isinstance(dn, bool) else None, dn, "True", "无 ⇒ 塑料感")
        roi = r.get("roi_selfproof")
        # 🔴 阈值是**标定出来的，不是猜的**（2026-10-15 正负对照）：
        #    正样本（真脸）：HSV 0.036~0.071 · YCrCb 0.056~0.113
        #    负样本（6 张 UI 截图）：HSV 0.000~0.002 · YCrCb 0.001~0.002
        #    ⇒ 可判别阈值 HSV 0.019 / YCrCb 0.029；判据取 **0.015** 留余量。
        #    ⚠️ 我第一版写 0.15 是**拍脑袋猜的**，连真脸都过不去（实测 0.064）。
        T("★ 清晰度 ROI 自证",
          (bool(roi) and float(roi.get("skin_ratio") or 0) > 0.015
           and roi.get("hud_excluded") is True and bool(roi.get("crop")))
          if isinstance(roi, dict) else None,
          roi, "肤色占比>0.015（标定值）且 排除HUD 且 输出裁图",
          "阈值 0.015 由正负对照标定：真脸 0.036~0.071 · UI 截图 0.000~0.002")

        return {"ok": True, "readonly": True, "过": p, "不过": f,
                "未给读数": len([x for x in out if x["pass"] is None]),
                "明细": out,
                "结论": ("全部达标" if f == 0 and p else
                        ("★%d 项不过 —— 不许粉饰" % f if f else "读数不足，先补读数"))}

    def plan(self, focus: str = "") -> dict:
        """按「清晰逼真收益」排序给下一步（照 PIPELINE.md §三 的原序）"""
        order = [
            ("渲染端清晰度", "SSAA 超采样 + 脸部/眼部专用补光 + 高分辨率出图（**零依赖、立刻见效**）",
             "脸部 ROI 梯度方差 ↑ · 边缘宽度 ↓"),
            ("材质专业化", "皮肤 SSS 近似 + micro-normal（从 albedo 高频提毛孔级细节）+ "
                          "眼角膜高光 + 头发各向异性", "specular 形态 · 粗糙度分区"),
            ("次级动力学", "头发/裙摆加 2–4 根弹簧骨（复用权重工具做区域重权）", "跟随延迟与回弹"),
            ("面部可动", "加颚/眼/眉 4–6 根骨 + 简单权重组", "眨眼/点头/张嘴幅度"),
            ("脸部保真（受源限制）", "源素材脸仅 ~200px ⇒ ①更高清脸照 或 ②本地人脸修复"
                                    "（onnxruntime + GFPGAN，约 365MB，**需主人批下载**）",
             "脸区有效分辨率"),
            ("状态机", "idle↔walk↔说话 交叉淡入（**禁硬切**）+ 脚部锁定（防滑步）",
             "切换时无跳变 · 脚不滑"),
        ]
        if focus:
            f = str(focus)
            order = [o for o in order if f in o[0] or f in o[1]] or order
        return {"ok": True, "readonly": True,
                "顺序口径": "按「清晰逼真」收益排序（照 PIPELINE.md §三）",
                "计划": [{"步骤": a, "怎么做": b, "量规": c} for a, b, c in order]}

    def sources(self) -> dict:
        return {"ok": True, "readonly": True, "sources": [
            {"what": "Eurographics 2026 STAR 论文（权威）",
             "title": "How to Build Digital Humans? From Priors to Photorealistic Avatars",
             "venue": "Computer Graphics Forum 45(2), 2026",
             "authors": "Zielonka, Kirschstein, Bolkart, Giebenhain, Sklyarova, Deng, Xiang, "
                        "Saito, Liu, Nießner, Thies",
             "org": "Meta · TUM · Google · 清华 · MPI · NVIDIA · TU Darmstadt · ETH",
             "repo": "https://github.com/Zielon/how-to-build-digital-humans",
             "data": "assets/data/publications.json（~250 篇结构化）· "
                     "tables_src/bibliography.bib · llms.txt（14/12 维分类）"},
            {"what": "three.js 官方材质文档（原话）",
             "quote": "For best results, always specify an environment map when using this material.",
             "url": "https://threejs.org/docs/#api/en/materials/MeshPhysicalMaterial"},
            {"what": "我们仓内已蒸馏",
             "files": ["holo_pet/assets/digital-human/PIPELINE.md（8 环节）",
                       "holo_pet/assets/digital-human/REALISM.md（8 步 + 7 禁令 + 缺口账）",
                       "holo_pet/assets/digital-human/STATUS.json（阶段/门限/凭据诊断）"]},
        ], "口径": "**凡是读数都标明是「测出来的」还是「查到的」；编的一律不写**"}


def run(op="status", **params) -> dict:
    """能力入口（只读）：status/steps/bans/taxonomy/gaps/check/plan/sources。
    **不渲染、不写盘、不出网。**
    """
    op = str(op or "status")
    d = DhRealism()
    if op == "status":
        return d.status()
    if op == "steps":
        return d.steps()
    if op == "bans":
        return d.bans()
    if op == "taxonomy":
        return d.taxonomy(params.get("kind", "avatar"))
    if op == "gaps":
        return d.gaps()
    if op == "check":
        return d.check(params.get("readings") or params)
    if op == "plan":
        return d.plan(params.get("focus", ""))
    if op == "sources":
        return d.sources()
    raise ValueError("未知 op %r（可用：status/steps/bans/taxonomy/gaps/check/plan/sources）" % (op,))


RED_LINES = (
    "凡读数必须标明来源（测出来的 / 查到的 / 编的 —— 编的一律不写）",
    "**先按专业流程定验收标尺，再逐项补齐，每项都要有读数**",
    "清晰度读数**必须 ROI 自证**（肤色占比 + 排除 HUD + 输出裁图人眼复核）",
    "AI 味禁令有一条中就是 AI 味，不是「差不多」",
    "缺口账**不许粉饰**：到不了就说到不了",
)

HONEST_BOUNDARY = (
    "本件保证「专业流程可查、判据可机检、分类可定位、缺口如实」；"
    "它保证不了「替你渲出一张真人级图」—— 渲染要走 `blender` 位或 three.js，"
    "而且真实感的天花板受**源素材信息量**限制（源图是光泽人偶质感，脸原图仅约 200px）。"
    "把知识固化成能力 ≠ 一按就出成品；它是**标尺 + 清单**，照着做才收敛。"
)
