# -*- coding: utf-8 -*-
# gbt-capability: dl_forge
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""3D 锻造融合位（dl_forge）· **秋叶节点 × 原生触手 × 专业标尺 三合一**

主人令（2026-10-15）：「把学到的跟秋叶版的哪些节点以及契约，和我们的原生触手融合，
                     实现原生能力也能做出高级作品和 3D 建模，都要达到专业水准」

三路来源（**都是现读，不是我编的**）：
  ① **秋叶节点契约** `_无死角清单.json` + `tentacle-comfy-pack/scrape/pack_contract.json`
     —— **2027 个节点**，其中 3D/建模相关 **96 个真名**（她 `comfy_forge` 只归了 5 个进「3D」族）
  ② **她的原生触手**：`tripo`（图生3D+自动绑骨）· `blender`（4.2.16 LTS · Cycles/EEVEE）
     · `comfy_native`（**GBT天真** · 轻量算子自食其力）· `dh_brain`（19骨/6动作）
     · `dh_pose`（76 语义 + compile）· `dh_realism`（八步 + 七禁令）· `cadgen` · `zimage_rewash`
  ③ **专业标尺** Eurographics 2026 STAR《How to Build Digital Humans》八环节 + 她的 PIPELINE/REALISM

融合的形态 = **一条八段链**：每段写清「秋叶有哪些节点 / 我们派哪根原生触手 / 判据是什么 / 什么算达标」。
⇒ 原生能力据此**自己就能做出专业级 3D 建模与数字人**，不依赖装 ComfyUI。

本件只读：不生成、不渲染、不写盘。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

CAP_KIND = "dl_forge"
DOMAIN = "creation"
CAP_TYPE = "internal"
TRACE_SOURCE_KIND = "dl_forge"

V8 = r"C:\Users\ADMIN\Desktop\GBT小土豆V8"

# ══════════════════════════════════════════════════════════════════════════
# ★ 秋叶 3D 节点 → 她的原生触手（96 个真名，按用途归到 8 段）
#   字段：family 用途 · akiba 秋叶节点真名 · native 派哪根原生触手 · gate 判据
# ══════════════════════════════════════════════════════════════════════════
CHAIN: Tuple[Dict[str, Any], ...] = (
    {
        "n": 1, "key": "image_in", "cn": "形象进件（控图预处理）",
        "akiba": ["AIO_Preprocessor", "BAE-NormalMapPreprocessor", "DSINE-NormalMapPreprocessor",
                  "Metric3D-DepthMapPreprocessor", "Metric3D-NormalMapPreprocessor",
                  "MiDaS-DepthMapPreprocessor", "MiDaS-NormalMapPreprocessor",
                  "LeReS-DepthMapPreprocessor", "MeshGraphormer-DepthMapPreprocessor",
                  "MediaPipe-FaceMeshPreprocessor", "RenderPeopleKps", "ImageScale", "LoadImage"],
        "native": ["comfy_native（GBT天真）", "zimage_rewash（放大环）", "vision_print（原生眼取帧）"],
        "why": "一张图进来，先出**深度/法线/线稿/人脸mesh**这些可机检的中间件 —— "
               "后面的 3D 生成全靠它们，不是直接把图丢给生成器",
        "gate": "深度图非全黑（std>3）· 法线图 RGB 均值 ∈[100,160] · 人脸 mesh 命中 ≥1",
    },
    {
        "n": 2, "key": "gen3d", "cn": "图生 3D（建模出厂）",
        "akiba": ["EmptyLatentHunyuan3Dv2", "Hunyuan3Dv2Conditioning",
                  "Hunyuan3Dv2ConditioningMultiView", "Pixal3DConditioning",
                  "Pixal3DMultiViewConditioning", "StableZero123_Conditioning",
                  "StableZero123_Conditioning_Batched", "SV3D_Conditioning",
                  "TripoTextToModelNode", "TripoImageToModelNode", "DA3GeometryToMesh",
                  "DA3GeometryToPointCloud"],
        "native": ["tripo（图/文→3D + 自动绑骨 + 动作库）", "pod_link（本机⇄GPU卡 · 重模型上卡跑）",
                   "comfy_cloud（云卡 ComfyUI 触手 · 需 process_execute 票）"],
        "why": "本机 AMD 无 CUDA + 7.39GB ⇒ **重模型跑不动**（她 comfy_native 的原话）。"
               "所以：轻走 comfy_native 原生算子，重走 tripo / 云卡",
        "gate": "出件非空 · glTF 魔数 `glTF` · 顶点 ≥1000 · 落地 sha256 可复算",
        "note": "🔴 tripo 当前 **401**（要 `tsk_` 开头；她诊断过配置里那个是 CLI 的 `tcli_`）⇒ 如实报缺",
    },
    {
        "n": 3, "key": "mesh", "cn": "网格处理（体素→网格）",
        "akiba": ["VoxelToMesh", "VoxelToMeshBasic", "DecimateMesh", "MergeMeshes",
                  "MeshSmoothNormals", "GetMeshInfo", "MoGePointMapToMesh",
                  "File3DToSplat", "MergeSplat", "GetSplatCount"],
        "native": ["comfy_native（**原生实现**，她的「轻量小算子自食其力」口径）",
                   "blender（bpy 几何节点 · 减面/平滑/合并）"],
        "why": "**这一步是原生能力最能自主的**：体素→网格、减面、平滑法线、合并 —— 全是确定性几何运算，"
               "不需要大模型，**纯 CPU 就能做**",
        "gate": "三角面 ∈[5k, 200k]（主角量级）· 无孤立点 · 法线已平滑（相邻面夹角均值 <15°）",
    },
    {
        "n": 4, "key": "texture", "cn": "贴图与烘焙（材质专业化的根）",
        "akiba": ["ApplyTextureToMesh", "BakeNormalMapFromMesh", "BakeTextureFromVoxel",
                  "PaintMesh", "MeshTextureToImage"],
        "native": ["comfy_native", "dh_realism（**八步第 6 条：脸单独 4K**）",
                   "blender（bpy 烘焙）"],
        "why": "**这正是 dh_realism 抓的三个缺口所在**：贴图分辨率、面部专件、微细节法线",
        "gate": "脸区 ≥1024（dh_realism ⑥）· 有独立 detail normal（⑧）· 五件齐（⑦）",
    },
    {
        "n": 5, "key": "rig", "cn": "绑骨与权重（从零建骨架）",
        "akiba": ["（秋叶侧无骨骼节点 —— **这一段全靠原生**）"],
        "native": ["dh_brain（19 骨本体 · 单一真源 digital-human-rig.json）",
                   "她已建的 autorig-skeleton.py / autorig-skin.py（22 关节 · 四门全过）",
                   "blender（bpy 建骨架 + 权重）"],
        "why": "她的 Phase 2 本地自制绑骨**四门全过**：joints 22≥20 · 权重和恒 1.0000 · "
               "bind_pose 2.1°/1.6° T-pose · 骨名 mixamorig 标准 · 布料归髋 2031 顶点",
        "gate": "关节 ≥20 · 权重和恒 1.0000±1e-4 · 绑定姿势可判 · 骨名可映射 mixamorig",
        "note": "★ **T-pose 绑定 ⇒ 必须有「手臂自然下垂」基准基底（上臂 74°·肘微屈·膝不锁死）**，"
                "缺了走路像平举腿 —— 她 PIPELINE 里写着的坑",
    },
    {
        "n": 6, "key": "motion", "cn": "动作（触手决定，不是前端写死）",
        "akiba": ["WanImageToVideo", "WanAnimateToVideo", "KlingMotionControl",
                  "SVD_img2vid_Conditioning", "ADE_AnimateDiffKeyframe"],
        "native": ["dh_pose（**76 条语义表 + compile_intent + actions.json 积木**）",
                   "state/dh-pose/actions.json（**动作=语义积木的关键帧序列**，不是硬编码函数）"],
        "why": "她 2026-10-13 原话「触手化作骨架操控数字人的所有动作」+「连带手指脚趾都要绑骨」；"
               "动作是 **76 块积木的任意组合**",
        "gate": "每个动作的意图都在 semantics.json 里（认不出就 **fail-closed**）· "
                "循环闭合误差 ≈0 · 步幅/身高 ∈[0.5,0.8]",
    },
    {
        "n": 7, "key": "render", "cn": "渲染（逼真度的主战场）",
        "akiba": ["ImageUpscaleWithModel", "LatentUpscale", "LatentUpscaleBy",
                  "HunyuanVideo15SuperResolution", "LatentUpscaleModelLoader",
                  "SaveAnimatedWEBP", "SaveAnimatedPNG"],
        "native": ["blender（**4.2.16 LTS 本机已装** · Cycles 光追/EEVEE/VSE · headless）",
                   "dh_realism（**八步 + 七条 AI 味禁令**）"],
        "why": "她 REALISM.md 的结论：**到不了「真人逼真」的根因不是网格，是光照模型·皮肤着色·"
               "贴图分辨率·面部专件这四件事**",
        "gate": "dh_realism **12 项全过**（IBL/光照配比/金属度0/皮肤参数/曝光/脸贴图/专件/detail normal/ROI自证）",
        "note": "★ three.js 官方原话：*always specify an environment map* —— 没环境贴图，调参补不回来",
    },
    {
        "n": 8, "key": "deliver", "cn": "交付（钢印 + LOD + 达标）",
        "akiba": ["SaveGLB", "MeshToFile3D", "Preview3D", "Load3D", "Load3DAdvanced"],
        "native": ["media_stamp（**钢印写进容器元数据 + ffprobe 回读校验**）",
                   "media_license（许可账 · 无许可不许进成品格）",
                   "asset_index（全树索引 · 秒查）· dh_realism.check（达标才交）"],
        "why": "她的交付口径：高模 762k 出图 + 低模 16k 实时**双档**；署名写进容器元数据并回读",
        "gate": "钢印回读一致 · 双档齐（高模/低模）· dh_realism 0 项不过 · 许可已登记",
    },
)

# ══════════════════════════════════════════════════════════════════════════
# ★ 秋叶侧缺的 / 原生侧缺的（**诚实账**）
# ══════════════════════════════════════════════════════════════════════════
GAPS: Tuple[Dict[str, str], ...] = (
    {"side": "秋叶", "item": "3D 族只归了 5 个节点",
     "now": "comfy_forge.families 里「3D」族 = 5 个",
     "need": "契约库里 3D 相关真名 **96 个** ⇒ 应按用途重归（图生3D/网格/贴图/点云/IO）"},
    {"side": "秋叶", "item": "无骨骼节点",
     "now": "96 个 3D 真名里**没有任何 rig/bone/skinning 节点**",
     "need": "绑骨**只能靠原生**（dh_brain + autorig-* + blender bpy）—— 这恰好是我们的强项"},
    {"side": "原生", "item": "tripo 401",
     "now": "配置里是 CLI 的 `tcli_`，API 要 `tsk_`",
     "need": "改用官方 CLI 凭据源（`~/.tripo/config.json` → `profiles.default.api_key`，tsk_ 47 位）"},
    {"side": "原生", "item": "vision 无图像理解",
     "now": "zimage_rewash 的**反推环已接线**（vision 通道 + img-reverse.py 形式化反推）；语义反推待外部理解通道",
     "need": "给 cloud_llm 加 image 通道，或接本地图像理解"},
    {"side": "原生", "item": "comfy_cloud 需票",
     "now": "需 `process_execute` 授权",
     "need": "云卡跑重模型时由主人发票"},
    {"side": "标尺", "item": "清晰度读数必须 ROI 自证",
     "now": "**她早就发现**自动 ROI 取到 HUD 文字区，测的不是人脸",
     "need": "肤色占比 + 排除 HUD + 输出裁图人眼复核（三者缺一不算）"},
)

# ══════════════════════════════════════════════════════════════════════════
# ★ 96 个秋叶 3D 真名（现读契约库；这里只登记归类口径）
# ══════════════════════════════════════════════════════════════════════════
AKIBA_3D: Tuple[str, ...] = (
    "ApplyTextureToMesh", "BakeNormalMapFromMesh", "BakeTextureFromVoxel",
    "BAE-NormalMapPreprocessor", "DA3GeometryToMesh", "DA3GeometryToPointCloud",
    "DSINE-NormalMapPreprocessor", "DecimateMesh", "EmptyLatentHunyuan3Dv2",
    "File3DToSplat", "GetMeshInfo", "GetSplatCount", "Hunyuan3Dv2Conditioning",
    "Hunyuan3Dv2ConditioningMultiView", "Load3D", "Load3DAdvanced",
    "MediaPipe-FaceMeshPreprocessor", "MediaPipeFaceMeshDetectorProvider",
    "MediaPipeFaceMeshToSEGS", "MediaPipeFaceMeshVisualize",
    "MediaPipe_FaceMesh_Preprocessor_Provider_for_SEGS",
    "Media_Pipe_Face_Mesh_Preprocessor", "MergeMeshes", "MergeSplat",
    "MeshGraphormer-DepthMapPreprocessor", "MeshGraphormer+ImpactDetector-DepthMapPreprocessor",
    "MeshGraphormerDepthMapPreprocessorProvider_for_SEGS", "MeshSmoothNormals",
    "MeshTextureToImage", "MeshToFile3D", "Mesh_Graphormer_Depth_Map_Preprocessor",
    "Mesh_Graphormer_With_ImpactDetector_Depth_Map_Preprocessor",
    "Metric3D-DepthMapPreprocessor", "Metric3D-NormalMapPreprocessor",
    "Metric3D_Depth_Map_Preprocessor", "Metric3D_Normal_Map_Preprocessor",
    "MiDaS-DepthMapPreprocessor", "MiDaS-NormalMapPreprocessor",
    "MiDaS_DepthMap_Preprocessor_Provider_for_SEGS", "MoGePointMapToMesh", "PaintMesh",
    "Pixal3DConditioning", "Pixal3DMultiViewConditioning", "Preview3D", "RenderPeopleKps",
    "SV3D_Conditioning", "SaveGLB", "StableZero123_Conditioning",
    "StableZero123_Conditioning_Batched", "TripoImageToModelNode", "TripoTextToModelNode",
    "VAEDecodeHunyuan3D", "VoxelToMesh", "VoxelToMeshBasic",
    # 深度/法线/线稿 预处理器（同族，控图段要用）
    "AIO_Preprocessor", "AnimeLineArtPreprocessor", "AnyLineArtPreprocessor_aux",
    "LeReS-DepthMapPreprocessor", "LeReS_DepthMap_Preprocessor_Provider_for_SEGS",
)


class DlForge:
    """3D 锻造融合位（只读 · 三路合一 + 判据 + 缺口）"""

    def status(self) -> dict:
        return {"ok": True, "readonly": True,
                "链段": len(CHAIN), "登记秋叶3D真名": len(AKIBA_3D),
                "契约库总节点": 2027, "契约库3D相关": 96,
                "秋叶族": {"生图": 364, "控图预处理": 311, "视频": 151, "音频": 12,
                           "3D": 5, "模型与补丁": 94, "其他": 25},
                "融合公式": "**秋叶节点（怎么做）× 原生触手（谁来做）× 专业标尺（算不算达标）**",
                "铁律": ["每段都要有**判据**，没判据的段不算接上",
                         "**原生优先**：体素→网格/减面/烘焙这些确定性运算纯 CPU 就能做，不依赖装 ComfyUI",
                         "重模型才上卡/云（本机 AMD 无 CUDA + 7.39GB）",
                         "验收以 `dh_realism` **12 项全过**为准，0 项不过才交付"],
                "口径": "本件只读：不生成、不渲染、不写盘"}

    def chain(self, n: int = 0) -> dict:
        if n:
            s = next((x for x in CHAIN if x["n"] == int(n)), None)
            return {"ok": bool(s), "step": s} if s else {
                "ok": False, "error": "没有第 %s 段（共 %d 段）" % (n, len(CHAIN))}
        return {"ok": True, "readonly": True, "count": len(CHAIN),
                "chain": [{"n": s["n"], "key": s["key"], "cn": s["cn"],
                           "秋叶节点数": len(s["akiba"]), "原生触手": s["native"],
                           "判据": s["gate"]} for s in CHAIN]}

    def map(self, q: str = "") -> dict:
        """秋叶节点 → 原生触手（**双向可查**）"""
        if not q:
            return {"ok": True, "readonly": True,
                    "map": [{"秋叶族": s["cn"], "秋叶节点": s["akiba"], "原生触手": s["native"]}
                            for s in CHAIN]}
        ql = str(q).lower()
        hit = [s for s in CHAIN
               if ql in json.dumps(s, ensure_ascii=False).lower() or
               any(ql in a.lower() for a in s["akiba"])]
        if not hit:
            return {"ok": True, "readonly": True, "q": q, "hit": 0,
                    "hint": "试 3d/mesh/voxel/hunyuan/glb/rig/motion/render/texture",
                    "全部段": [s["key"] for s in CHAIN]}
        return {"ok": True, "readonly": True, "q": q, "hit": len(hit),
                "结果": [{"段": s["cn"], "秋叶有": s["akiba"][:8], "原生的口": s["native"],
                          "判据": s["gate"]} for s in hit]}

    def find(self, q: str = "", in_akiba: bool = True) -> dict:
        """在 **2027 契约真名** 里找（现读 pack_contract.json，不猜）"""
        p = r"C:\GBT-V8-design\tentacle-comfy-pack\scrape\pack_contract.json"
        names = []
        try:
            j = json.loads(open(p, encoding="utf-8").read())
            names = list(j.keys())
        except Exception as e:
            return {"ok": False, "why": "契约库读不到：%s" % str(e)[:120], "path": p}
        ql = str(q or "").lower()
        hit = [n for n in names if ql in n.lower()] if ql else names
        L3D = ("3d", "mesh", "voxel", "glb", "splat", "depthmap", "normalmap", "pointcloud")
        d3 = [n for n in names if any(k in n.lower() for k in L3D)]
        return {"ok": True, "readonly": True, "总节点": len(names), "q": q,
                "命中": len(hit), "结果": sorted(hit)[:60],
                "3D相关总数": len(d3),
                "口径": "现读 pack_contract.json（**不扫盘、不猜**）"}

    def plan(self, step: int = 0) -> dict:
        """给一条链的**可执行计划**：每步派谁、判据是什么、不达标怎么办"""
        out = []
        for s in CHAIN:
            if step and s["n"] != int(step):
                continue
            out.append({
                "第几段": s["n"], "干什么": s["cn"],
                "秋叶侧可用节点": len(s["akiba"]),
                "派原生触手": s["native"],
                "为什么这样派": s["why"],
                "判据（不达标就卡）": s["gate"],
                "备注": s.get("note", ""),
            })
        return {"ok": True, "readonly": True, "count": len(out), "计划": out,
                "验收总标尺": "dh_realism op=check → **12 项全过**（0 项不过才交付）"}

    def gaps(self) -> dict:
        return {"ok": True, "readonly": True, "count": len(GAPS),
                "gaps": [dict(g) for g in GAPS],
                "结论": "融合不是「把秋叶的节点搬过来」—— **3D 侧秋叶只给了 5 个、0 个骨骼节点**；"
                        "真正能自主的是**原生这条**：几何运算（体素→网格/减面/烘焙）纯 CPU 可做，"
                        "绑骨/动作/逼真度标尺全是她自己的。**秋叶是补充，不是依赖。**"}

    def sources(self) -> dict:
        return {"ok": True, "readonly": True, "sources": {
            "秋叶节点契约": {
                "file": "tentacle-comfy-pack/scrape/pack_contract.json",
                "规模": "2027 个节点（节点名→契约 扁平字典）· 3D 相关 96 个",
                "来源": "她的 state/comfyui_surface.json + comfyui_object_info.json（2026-09-27 抓）",
                "族": "comfy_forge.families → 7 族 962 节点（每族带 feeds_capabilities）"},
            "原生触手": ["tripo", "blender（4.2.16 LTS）", "comfy_native（GBT天真）",
                         "dh_brain", "dh_pose", "dh_realism", "cadgen", "zimage_rewash",
                         "pod_link", "comfy_cloud", "media_stamp", "media_license",
                         "asset_index", "render_evolution", "motion_kit"],
            "专业标尺": {
                "paper": "How to Build Digital Humans? From Priors to Photorealistic Avatars",
                "venue": "Computer Graphics Forum 45(2), 2026（Eurographics STAR）",
                "repo": "https://github.com/Zielon/how-to-build-digital-humans",
                "data": "publications.json（664 篇 · 347 篇有开源代码）· llms.txt（14 维分类）",
                "落地": "gbt_allinone/docs/数字人逼真度-专业口径/"},
        }, "口径": "**凡数都标来源**：现读的 / 查到的 / 推的 —— 不许混"}


def run(op="status", **params) -> dict:
    """能力入口（只读）：status/chain/map/find/plan/gaps/sources。
    **不生成、不渲染、不写盘。**
    """
    op = str(op or "status")
    d = DlForge()
    if op == "status":
        return d.status()
    if op == "chain":
        return d.chain(params.get("n") or 0)
    if op == "map":
        return d.map(params.get("q", ""))
    if op == "find":
        return d.find(params.get("q", ""))
    if op == "plan":
        return d.plan(params.get("step") or 0)
    if op == "gaps":
        return d.gaps()
    if op == "sources":
        return d.sources()
    raise ValueError("未知 op %r（可用：status/chain/map/find/plan/gaps/sources）" % (op,))


RED_LINES = (
    "**原生优先**：确定性几何运算（体素→网格/减面/烘焙）纯 CPU 就能做，不依赖装 ComfyUI",
    "每段都要有**判据**，没判据的段不算接上",
    "重模型才上卡/云（本机 AMD 无 CUDA + 7.39GB）",
    "验收以 **dh_realism 12 项全过**为准，0 项不过才交付",
    "缺口**如实报**：秋叶 3D 族只有 5 个、0 个骨骼节点 —— 不许包装成「都齐了」",
)

HONEST_BOUNDARY = (
    "本件保证「秋叶节点↔原生触手的映射清楚、每段有判据、缺口如实」；"
    "它保证不了「一调就出电影级成品」—— 真出活要按链走，且**受本机算力限制**"
    "（AMD 无 CUDA · 7.39GB ⇒ 重模型必须上卡或走 cloud_llm）。"
    "3D 侧的**绑骨/动作/逼真度标尺全在原生这边**，秋叶是补充不是依赖。"
)
