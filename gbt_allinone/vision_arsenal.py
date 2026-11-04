# -*- coding: utf-8 -*-
"""vision_arsenal -- 视觉作战区（唯一区块 · 大脑执行层的视觉选型入口）

来源：2026-11-04 主人令「把开源仓库排名前十的视觉能力吞噬一遍，补齐缺失的视觉，
      全部整理到一个区块，让大脑执行层自动决策使用哪个视觉能力」。

开源基线（GitHub Computer Vision 星标榜 · 2026-09-27 快照，已用 devour_github 吞过）
  1  huggingface/transformers      166,700   图文理解 / VLM
  2  opencv/opencv                  90,973   图像处理基础库
  3  CompVis/stable-diffusion       73,479   文生图
  4  ultralytics/ultralytics        62,028   检测 / 分割 / 姿态
  5  ultralytics/yolov5             58,089   检测（前代）
  6  facebookresearch/segment-anything 54,943 通用分割 SAM
  7  roboflow/supervision           51,054   检测结果标注 / 跟踪
  8  huggingface/pytorch-image-models 37,171 视觉骨干 timm
  9  facebookresearch/detectron2    34,735   检测/分割框架
 10  huggingface/diffusers          34,611   扩散管线

── 铁律（与 vision_grounding 同源，不许破）────────────────────────────
1. **先结构后像素**：能用 uia_tree / cdp_dom 就别用像素。
2. **主选必须真能跑**：needs_dependency 的位只进 alternatives，并在 `missing` 里
   写明缺什么 —— **绝不把"装了但其实跑不了"当主选**。
3. **图不进上下文**：所有像素类能力只回坐标/文本/数值，绝不回图片本体。
4. **降级必须自曝**：`degraded=True` + `degraded_reason`，不冒充完整能力。

对外三门：`status()` 全量体检 · `matrix()` 决策矩阵 · `decide(intent)` 选型
外加两个本机真能跑的新位：`template_match()` 图标定位 · `region_scan()` 可点区块扫描
"""
from __future__ import annotations

import importlib.util
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ────────────────────────── 依赖探测 ──────────────────────────
_PKG_CACHE: dict = {}


def _has(pkg: str) -> bool:
    if pkg not in _PKG_CACHE:
        try:
            _PKG_CACHE[pkg] = bool(importlib.util.find_spec(pkg))
        except Exception:
            _PKG_CACHE[pkg] = False
    return _PKG_CACHE[pkg]


# ────────────────────────── 能力位表 ──────────────────────────
# status 由 _resolve_status() 现算，不写死。
POSITIONS = [
    # ===== A 读：本机真能跑 =====
    {
        "id": "ocr", "cn": "读字", "group": "读", "kind": "ocr",
        "src": "Windows.Media.Ocr（系统内置）", "repo": None, "stars": None,
        "need": [], "weights": None,
        "use": "图里有文字要抄 / 看报错文案 / 读界面标签 / 截图转文字",
        "kw": ["文字", "文本", "ocr", "读字", "读图", "图里", "图上", "截图转文字",
               "报错", "文案", "写的什么", "写了什么", "抄下来", "识别文字",
               # 2026-11-04 决策接入：实测「读屏幕上的字」原来落到 vision_grounding 降级，
               # 因为 kw 里只有「读字」，而口语常把「屏幕」插在中间。
               "读屏幕", "屏幕上的字", "屏幕的字", "屏幕文字", "读出来", "认字"],
        "cost": "低（只回文本，几百 token）",
        "fallback": [],
    },
    {
        "id": "template_match", "cn": "图标定位", "group": "读", "kind": "vision_arsenal",
        # 2026-11-04：多位共用一个 kind 时，光给 kind 等于没说清怎么调
        # （decide 说 region_scan，调用方拿到 vision_arsenal 还得再猜 op）。
        "op": "template_match",
        "src": "opencv.matchTemplate", "repo": "opencv/opencv", "stars": 90973,
        "need": ["cv2", "numpy"], "weights": None,
        "use": "拿一张小图（图标/按钮）在整屏里找坐标，用于点击；不改动画面",
        "kw": ["图标", "按钮在哪", "找到这个", "模板", "定位", "坐标", "在哪里", "点哪", "匹配"],
        "cost": "低（只回坐标列表）",
        "fallback": ["region_scan", "uia_tree"],
    },
    {
        "id": "region_scan", "cn": "可点区块", "group": "读", "kind": "vision_arsenal",
        "op": "region_scan",
        "src": "opencv 轮廓/边缘", "repo": "opencv/opencv", "stars": 90973,
        "need": ["cv2", "numpy"], "weights": None,
        "use": "无 a11y 时扫出画面里像按钮/输入框/卡片的矩形块，给可点坐标与排序",
        "kw": ["可点", "区块", "布局", "界面结构", "有哪些按钮", "格子", "区域", "元素在哪",
                 # 2026-11-04：「有什么按钮」= 不知道有哪些要扫，与「找这个特定图标」是两回事
                 "有什么按钮", "按钮有哪些", "有哪些输入", "有哪些控件", "哪里能点",
                 # 2026-11-04 端到端实测补：说「界面上有哪些能点的地方」原来**没进视觉车道**
                 # （落到通用主路 impact_check）—— 缺的是「能点的地方」这个口语说法本身。
                 "能点的地方", "能点的", "可以点的", "能点啥", "哪里可以点"],
        "cost": "低（只回矩形列表）",
        "fallback": ["uia_tree"],
    },
    {
        "id": "pixel_stats", "cn": "像素统计", "group": "读", "kind": "vision",
        # 真实落地是 vision_cap 的 analyze（本地 PIL：尺寸/亮度/对比度/边缘密度/主色/网格），
        # 实测 brightness 29.4 / contrast 53.7 / edge_density 4.0 —— 不是图像识别。
        "op": "analyze",
        "src": "PIL / opencv", "repo": "opencv/opencv", "stars": 90973,
        "need": ["PIL"], "weights": None,
        "use": "亮度/对比度/边缘密度/主色/网格亮度 —— 判断「是不是同一个画面」「变化了没有」",
        "kw": ["亮度", "对比度", "颜色", "主色", "变了没", "变化", "一样吗", "差异", "统计"],
        "cost": "极低（纯数值）",
        "fallback": [],
    },
    {
        "id": "uia_tree", "cn": "控件树", "group": "读", "kind": "uia_tree",
        "src": "Windows UIA", "repo": None, "stars": None,
        # 2026-11-04 修：这里原来是 `need: []`，于是 arsenal 永远把它标成 available ——
        # 实测调 domain_index 直接 ModuleNotFoundError: uiautomation。
        # 「静态推断看不到的缺件」正是虚报的来源，所以把它列进 need。
        "need": ["uiautomation"], "weights": None,
        "use": "原生窗口的结构化控件（可寻址、无视遮挡）—— 最优先的结构通道",
        "kw": ["控件", "窗口", "元素", "输入框", "菜单", "原生", "软件界面",
               # 2026-11-04：与 template_match 的「在哪里」冲突 —— 复合词命中 2 项才能压过它
               "菜单在哪", "菜单在哪里", "控件在哪"],
        "cost": "低（实测 1012ms / 6 窗口 / 14.5k 字）",
        "fallback": ["region_scan"],
    },
    {
        "id": "cdp_dom", "cn": "页面 DOM", "group": "读", "kind": "browser",
        "src": "Chrome DevTools Protocol", "repo": None, "stars": None,
        "need": [], "weights": None,
        "use": "网页内的元素/文本/点击 —— 页面级可寻址，遮挡无关",
        "kw": ["网页", "页面", "dom", "浏览器", "html", "链接", "表单"],
        "cost": "低",
        "fallback": ["region_scan"],
    },
    # ===== B 懂：需模型 =====
    {
        "id": "vlm_understand", "cn": "图文理解", "group": "懂", "kind": "vision",
        "src": "huggingface/transformers", "repo": "huggingface/transformers", "stars": 166700,
        "need": ["torch", "transformers"], "weights": "需下载 VLM 权重（1~16GB）",
        "use": "回答「这张图是什么意思」「这个界面在干什么」 —— 语义级理解",
        "kw": ["看懂", "什么意思", "在干什么", "内容是什么", "理解", "描述这张", "语义", "为什么报错"],
        "cost": "高（图片进上下文，吃 token）",
        "fallback": ["ocr", "pixel_stats"],
    },
    {
        "id": "caption", "cn": "图像描述", "group": "懂", "kind": "vision",
        "src": "transformers (BLIP)", "repo": "huggingface/transformers", "stars": 166700,
        "need": ["torch", "transformers"], "weights": "需下载 BLIP 权重（~1GB）",
        "use": "给一张图生一句话描述（无需提问）",
        "kw": ["描述图片", "说明这张图", "图里有什么", "caption"],
        "cost": "中",
        "fallback": ["ocr"],
    },
    {
        "id": "feature_embed", "cn": "语义相似度", "group": "懂", "kind": "vision_embed",
        "src": "CLIP ViT-B/32 视觉编码器（ONNX · 352MB · 不装 torch）",
        "repo": "huggingface/transformers", "stars": 166700,
        "need": ["onnxruntime", "numpy", "PIL"], "model": "state/models/clip_vision.onnx",
        "use": "两张图是不是「同一回事」的语义判定 —— 补 aHash 的盲区：主题切换/反色时 aHash 归零，它仍认得出（实测 0.94 vs 0.00）",
        "kw": ["相似", "像不像", "同一个", "是不是同一张", "比对", "指纹", "特征",
                 "换了没", "还是刚才那个",
                 # 2026-11-04：「有多像」「差多少」是同一件事的口语说法
                 "多像", "差多少", "一样不一样", "相似度"],
        "cost": "中（CPU 约 0.35~0.4 秒/张）",
        "fallback": ["pixel_stats"],
    },
    # ===== C 找：需模型 =====
    {
        "id": "detect", "cn": "目标检测", "group": "找", "kind": "vision_detect",
        "src": "ultralytics YOLO11n（ONNX 路线 · 不装 torch）",
        "repo": "ultralytics/ultralytics", "stars": 62028,
        "need": ["onnxruntime", "numpy", "cv2"], "model": "state/models/yolo11n.onnx",
        "use": "框出并分类画面里的真实物体（人/车/动物/电脑）；对纯 UI 截图基本只认「一整块屏幕」，界面请用 region_scan",
        "kw": ["检测", "找出来", "有哪些物体", "框出来", "几个人", "识别出", "目标", "照片里", "画面里有什么"],
        "cost": "中（CPU 约 0.5~0.9 秒）",
        "fallback": ["region_scan"],
    },
    {
        "id": "segment", "cn": "通用分割", "group": "找", "kind": "vision_segment",
        "src": "facebookresearch/segment-anything", "repo": "facebookresearch/segment-anything", "stars": 54943,
        # 2026-11-04 落地：不用 torch —— slimsam-77（SAM 蒸馏版）有现成 ONNX，两段共 38MB，
        # onnxruntime 早就在。实测：encoder 3.2s（每图一次，缓存）/ decoder 0.08~0.37s。
        # 框提示 iou .913 覆盖 31.3%（整人）；点提示 iou .688 覆盖 1.1%（常只抠局部）。
        "need": [], "model": "state/models/slimsam_encoder.onnx",
        "use": "点一下/框一下把目标抠出来（去背景、精确边界）；产物落本地文件只回路径",
        "kw": ["抠图", "分割", "去背景", "边界", "mask", "轮廓精确", "抠出来"],
        "cost": "中（首点 3.3s 含 encoder，同图再点 0.1~0.4s）",
        "fallback": ["region_scan"],
    },
    {
        "id": "pose", "cn": "姿态", "group": "找", "kind": "vision_pose",
        "src": "ultralytics/ultralytics", "repo": "ultralytics/ultralytics", "stars": 62028,
        # 2026-11-04 落地：不走 torch —— YOLO11n-pose 的 onnx 只有 11.3MB，
        # onnxruntime 早就在，和 vision_detect 同一条路。所以 need 清空、改看模型文件。
        "need": [], "model": "state/models/yolo11n-pose.onnx",
        "use": "人体 17 关键点 + 粗几何判定（举手 / 站坐 / 是否正对）；不做动作语义识别",
        "kw": ["姿态", "关键点", "手势", "骨架", "举手", "站姿", "坐姿",
                 # 2026-11-04：口语说「姿势」比「姿态」多，缺了这一个问法就落到降级
                 "姿势", "动作", "什么姿势", "怎么站的", "在做什么动作",
                 # 2026-11-04：实测「他举着手吗」原来降级到 vision_grounding，因为只有「举手」没有「举着」
                 "举着", "手举", "举起", "举手吗", "坐着", "站着", "坐着还是站着"],
        "cost": "中（306~378ms/张，纯 CPU）",
        "fallback": [],
    },
    {
        "id": "track", "cn": "目标跟踪", "group": "找", "kind": "vision_track",
        "src": "roboflow/supervision", "repo": "roboflow/supervision", "stars": 51054,
        # 2026-11-04 落地：不装 supervision —— 跟踪的核心只是「上一帧的框↔这一帧的框怎么配对」，
        # 是取最大值问题。贪心 IoU 实现约 100 行纯 Python，零依赖。实测帧2/帧3 id 稳定。
        "need": [], "weights": None,
        "use": "跨帧跟踪同一目标（视频/连续截图里的「还是它」）：给 boxes 就关联，给 frames 就自动检测+关联",
        "kw": ["跟踪", "追踪", "跟随", "连续", "视频里", "还是它"],
        "cost": "低（纯计算，毫秒级）",
        "fallback": ["pixel_stats"],
    },
    # ===== D 造：需模型（本机可降级到 comfy_native）=====
    {
        "id": "t2i", "cn": "文生图", "group": "造", "kind": "comfy_native",
        "src": "CompVis/stable-diffusion · huggingface/diffusers",
        "repo": "CompVis/stable-diffusion", "stars": 73479,
        "need": ["torch", "diffusers"], "weights": "需下载 SD 权重（2~7GB）",
        "use": "文字生成图片",
        "kw": ["生成图", "画一张", "文生图", "出图", "作图"],
        "cost": "高",
        "fallback": ["comfy_native"],
    },
    {
        "id": "img_edit", "cn": "图生图 / 修复", "group": "造", "kind": "comfy_native",
        "src": "huggingface/diffusers", "repo": "huggingface/diffusers", "stars": 34611,
        "need": ["torch", "diffusers"], "weights": "需下载权重（2~7GB）",
        "use": "改图 / 局部重绘 / 放大洗图",
        "kw": ["改图", "重绘", "修复", "放大", "高清", "锐化", "洗图", "4k"],
        "cost": "高",
        "fallback": ["comfy_native"],
    },
    # ===== E 既有触手位：保留，作为契约与闭环 =====
    {
        "id": "vision_grounding", "cn": "分层契约", "group": "读", "kind": "vision_grounding",
        "src": "触手自有", "repo": None, "stars": None,
        "need": [], "weights": None,
        "use": "查「看」的分层规矩，动手前先读它",
        "kw": ["怎么看看", "分层", "规矩", "契约", "视觉方案"],
        "cost": "极低",
        "fallback": [],
    },
    {
        "id": "vision_loop", "cn": "四觉闭环", "group": "读", "kind": "vision_loop",
        "src": "触手自有", "repo": None, "stars": None,
        "need": [], "weights": None,
        "use": "眼耳嘴手同步的连续观察闭环",
        "kw": ["闭环", "连续看", "边看边做", "四觉"],
        "cost": "中",
        "fallback": ["vision_grounding"],
    },
    {
        "id": "vlx_flow", "cn": "流式观察", "group": "读", "kind": "vlx_flow",
        "src": "om-ai-lab/VLX-Flow", "repo": None, "stars": None,
        "need": [], "weights": None,
        "use": "流式观察 + 两层记忆（长操作过程的记忆）",
        "kw": ["流式", "持续观察", "记住过程", "两层记忆"],
        "cost": "中",
        "fallback": ["vision_loop"],
    },
    {
        "id": "vision_print", "cn": "视觉打印", "group": "读", "kind": "vision_print",
        "src": "触手自有", "repo": None, "stars": None,
        "need": ["cv2"], "weights": None,
        "use": "看到的东西原样以代码打印并渲染（see→print→render→diff→judge）",
        "kw": ["打印界面", "还原页面", "复刻", "渲染出来", "代码还原"],
        "cost": "中",
        "fallback": ["region_scan"],
    },
]

_BY_ID = {p["id"]: p for p in POSITIONS}


def _model_path(rel: str) -> str:
    return os.path.join(_ROOT, *rel.split("/"))


def _resolve_status(pos: dict) -> tuple:
    """返回 (status, missing)。status ∈ available / needs_dependency

    模型类能力不靠「有没有写 weights」判断，而是**实地看模型文件在不在** ——
    文件在才叫可用，否则如实报缺哪个文件。这样「装了包但没模型」不会被当成可用。
    """
    missing = [pkg for pkg in pos.get("need") or [] if not _has(pkg)]
    if missing:
        return "needs_dependency", missing
    rel = pos.get("model")
    if rel:
        p = _model_path(rel)
        if not (os.path.exists(p) and os.path.getsize(p) > 1_000_000):
            return "needs_dependency", ["模型文件缺失（%s）" % rel]
        return "available", []
    if pos.get("weights"):
        return "needs_dependency", ["模型权重"]
    return "available", []


# ────────────────────────── 1. 体检 ──────────────────────────
# 2026-11-04 加：区分「产出型」与「契约型」。
# 起因是主人问「视觉全部落实到位了吧」，我逐位真调才发现：
# vision_grounding / vision_loop / vlx_flow / vision_print 这 4 位 status=available，
# 但它们返回的是**通道契约 / 四觉口径 / 流程定义 / 五段链**（op=status），
# 实际不产出任何视觉结果。把它们算进「可用 15」是把数字说漂亮了，不是事实。
# 所以：available 只表示「依赖齐备」，能不能产出视觉要另算。
_EXEC_KINDS = {
    "ocr",              # 读字
    "vision_arsenal",   # template_match / region_scan
    "vision",           # pixel_stats
    "vision_embed",     # 特征向量
    "vision_detect",    # 目标检测
    "vision_segment",   # 分割
    "vision_pose",      # 姿态
    "vision_track",     # 跟踪
    "uia_tree",         # UIA 控件树（2026-11-04 建位：真实实现是触手方法
                        #   omni_domain.domain_index；原来这里写 kind="domain_index"
                        #   —— 那不是能力位也不是模块名，decide 指着它调不动）
    "browser",          # CDP DOM
    # t2i / img_edit 的 kind 是 comfy_native：它们**是产出型**（能真出图），
    # 只是本机不跑、走云卡 —— 别因为标成「契约型」让人误以为是流程定义。
    "comfy_native",
}


def status(group: str = "") -> dict:
    rows = []
    for p in POSITIONS:
        if group and p["group"] != group:
            continue
        st, missing = _resolve_status(p)
        rows.append({
            "id": p["id"], "cn": p["cn"], "group": p["group"], "kind": p["kind"],
            "status": st, "missing": missing,
            "repo": p.get("repo"), "stars": p.get("stars"),
            "need_weights": bool(p.get("weights")),
            "use": p["use"], "cost": p["cost"],
            "produces_vision": p["kind"] in _EXEC_KINDS,
        })
    avail = [r for r in rows if r["status"] == "available"]
    producing = [r for r in avail if r["produces_vision"]]
    contract = [r for r in avail if not r["produces_vision"]]

    # 2026-11-04 加：把「能力在位」与「环境就绪」分开。
    # cdp_dom 的通道是标准库实现的（transport=standard-library-rfc6455），代码完全不缺；
    # 但 Chrome 没开 --remote-debugging-port=9222 时，调用会回 needs_browser_debug。
    # 若把这种情况也算成 needs_dependency，会把「没开浏览器」误报成「能力缺失」——
    # 反过来若不管，又会像 uia_tree 那样虚报可用。所以单列 runtime_ready。
    runtime = {}
    try:
        import socket as _sk
        _s = _sk.socket(); _s.settimeout(0.3)
        try:
            _s.connect(("127.0.0.1", 9222))
            runtime["cdp_dom"] = True
        except Exception:                                          # noqa: BLE001
            runtime["cdp_dom"] = False
        finally:
            _s.close()
    except Exception:                                              # noqa: BLE001
        runtime["cdp_dom"] = None

    for r in rows:
        if r["id"] in runtime:
            r["runtime_ready"] = runtime[r["id"]]

    return {
        "ok": True, "total": len(rows), "available": len(avail),
        "needs_dependency": len(rows) - len(avail),
        # ⚠️ 只有这个才是「真能出视觉结果」的位数；available 含契约位，别混报
        "produces_vision": len(producing),
        "contract_only": [r["id"] for r in contract],
        "contract_only_note": "这几位 status=available 只表示依赖齐备，"
                              "调用返回的是契约/口径/流程定义，**不产出视觉结果**",
        "runtime": runtime,
        "runtime_note": "cdp_dom 通道代码不缺，但需 Chrome 开 --remote-debugging-port=9222；"
                        "未开时调用回 needs_browser_debug，属环境未就绪而非能力缺失",
        "positions": rows,
        "pkg": {k: _has(k) for k in ("cv2", "numpy", "PIL", "onnxruntime",
                                     "torch", "transformers", "ultralytics",
                                     "timm", "diffusers", "supervision",
                                     "segment_anything", "pytesseract",
                                     "uiautomation")},
    }


# ────────────────────────── 2. 决策矩阵 ──────────────────────────
def matrix() -> dict:
    """一眼看全：每组有哪些位、哪些能用、缺什么。"""
    out: dict = {}
    for p in POSITIONS:
        st, missing = _resolve_status(p)
        out.setdefault(p["group"], []).append({
            "id": p["id"], "cn": p["cn"], "status": st,
            "missing": missing, "kind": p["kind"],
            "src": p["src"], "stars": p.get("stars"),
        })
    return {"ok": True, "groups": ["读", "懂", "找", "造"], "matrix": out}


# ────────────────────────── 3. 选型 ──────────────────────────
def _score(intent: str) -> list:
    """按「命中关键词的总长度」打分 —— 长词更具体，短词更泛。

    为什么不用命中个数：只数个数会让「页面」(cdp_dom) 和「像不像」(feature_embed)
    打平，再靠字母序决出 cdp_dom —— 实测「刚才那个页面和现在像不像」就是这么错判的。
    改成按词长加权后，「像不像」(3) 压过「页面」(2)，判对。
    """
    q = (intent or "").lower()
    rows = []
    for p in POSITIONS:
        hits = [k for k in p["kw"] if k.lower() in q]
        if hits:
            rows.append((sum(len(k) for k in hits), len(hits), p["id"]))
    rows.sort(key=lambda r: (-r[0], -r[1], r[2]))
    return rows


def matched(intent: str) -> bool:
    """意图是否真的落在视觉作战区的词汇表里。

    给大脑车道做门禁：宁可漏判（交回通用主路），也不要用外挂提示词误劫持
    —— 实测「帮我写个 python 脚本读 csv」会被裸「读」误命中。
    """
    return bool(_score(intent))


def decide(intent: str) -> dict:
    """大脑执行层问"这事该用哪个视觉能力"，这里给答案。

    主选永远给**本机真能跑**的位；想用但缺依赖的位进 alternatives 并在 missing 里
    写明缺什么 —— 不把跑不了的当主选。
    """
    intent = (intent or "").strip()
    if not intent:
        return {"ok": False, "reason": "需要 intent：说明你要看什么"}

    scored = _score(intent)
    if not scored:
        base = _BY_ID["vision_grounding"]
        return {"ok": True, "intent": intent[:120], "degraded": True,
                "degraded_reason": "没匹配到具体视觉位，回分层契约（先结构后像素）",
                "pick": {"id": base["id"], "cn": base["cn"], "kind": base["kind"],
                         "status": "available", "why": base["use"],
                         "cost": base["cost"], "chain": ["vision_grounding"]},
                "alternatives": [], "missing": []}

    avail, blocked = [], []
    for weight, nhits, pid in scored:
        p = _BY_ID[pid]
        st, missing = _resolve_status(p)
        item = {"id": pid, "cn": p["cn"], "kind": p["kind"],
                # op：多位共用同一个 kind 时，调用方照这个 op 调才落到**这一位**
                # （否则 decide 说 region_scan、调用方用 vision_arsenal 默认 op 会跑歪）
                "op": p.get("op"),
                "hits": nhits, "weight": weight,
                "status": st, "why": p["use"], "cost": p["cost"],
                "chain": [pid] + list(p["fallback"])}
        (avail if st == "available" else blocked).append((item, missing))

    missing_out = [{"id": it["id"], "cn": it["cn"], "need": m,
                    "repo": _BY_ID[it["id"]].get("repo"),
                    "stars": _BY_ID[it["id"]].get("stars")}
                   for it, m in blocked]

    if avail:
        pick = avail[0][0]
        return {"ok": True, "intent": intent[:120], "degraded": False,
                "pick": pick,
                "alternatives": [it for it, _ in avail[1:4]],
                "missing": missing_out}

    # 想用的都缺依赖 → 落到最近的可降级位，并如实自曝
    want = blocked[0][0]
    for cand in want["chain"][1:]:
        p = _BY_ID.get(cand)
        if p is None:
            # 降级目标是区外能力位（如 comfy_native）—— 不装作体检过，如实标 external
            return {"ok": True, "intent": intent[:120], "degraded": True,
                    "degraded_reason": "%s 缺依赖（%s），降级到区外能力位 %s —— 其可用性需现场确认"
                                        % (want["cn"], "、".join(blocked[0][1]), cand),
                    "pick": {"id": cand, "cn": cand, "kind": cand, "status": "external",
                             "why": "区外能力位（未纳入视觉作战区体检）",
                             "cost": "未知", "chain": [cand]},
                    "alternatives": [], "missing": missing_out, "wanted": want}
        st, _m = _resolve_status(p)
        if st == "available":
            return {"ok": True, "intent": intent[:120], "degraded": True,
                    "degraded_reason": "%s 缺依赖（%s），降级到 %s"
                                        % (want["cn"], "、".join(blocked[0][1]), p["cn"]),
                    "pick": {"id": p["id"], "cn": p["cn"], "kind": p["kind"],
                             "status": st, "why": p["use"], "cost": p["cost"],
                             "chain": list(p["fallback"]) and [p["id"]] + list(p["fallback"]) or [p["id"]]},
                    "alternatives": [], "missing": missing_out, "wanted": want}

    return {"ok": True, "intent": intent[:120], "degraded": True,
            "degraded_reason": "所有相关视觉位都缺依赖，本机暂不可达",
            "pick": None, "alternatives": [], "missing": missing_out, "wanted": want}


# ────────────────────────── 4. 两个新位（本机真跑）──────────────────────────
def _imread(path: str):
    """中文路径安全的读图。cv2.imread 在非 ASCII 路径上会直接返回 None。"""
    import cv2
    import numpy as np
    if not os.path.exists(path):
        raise FileNotFoundError("图片不存在: %s" % path)
    buf = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("解不开这张图（格式不支持？）: %s" % path)
    return img


def template_match(image: str, template: str, threshold: float = 0.80, max_hits: int = 5) -> dict:
    """在 image 里找 template 的所有位置。回坐标，不回图。"""
    import cv2
    if not image or not template:
        return {"ok": False, "reason": "需要 image 与 template 两个本地路径"}
    img, tpl = _imread(image), _imread(template)
    ih, iw = img.shape[:2]
    th, tw = tpl.shape[:2]
    if th > ih or tw > iw:
        return {"ok": False, "reason": "模板(%dx%d)比底图(%dx%d)还大" % (tw, th, iw, ih)}

    # 方差守卫：纯色/低纹理模板会让 matchTemplate 在任意位置都给出 1.0，是假阳性温床
    gray_tpl = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
    tpl_std = float(gray_tpl.std())
    if tpl_std < 8.0:
        return {"ok": False, "template_std": round(tpl_std, 2),
                "reason": "模板太平（灰度标准差 %.1f，几乎纯色），匹配不可信 —— 换一块有字或有纹理的模板" % tpl_std}

    res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
    hits = []
    r = res.copy()
    for _ in range(max_hits):
        _min, maxv, _minloc, maxloc = cv2.minMaxLoc(r)
        if maxv < threshold:
            break
        x, y = int(maxloc[0]), int(maxloc[1])
        hits.append({"x": x, "y": y, "w": tw, "h": th,
                     "cx": x + tw // 2, "cy": y + th // 2,
                     "score": round(float(maxv), 4)})
        # 抑制邻域，避免同一个图标反复命中
        x0, y0 = max(0, x - tw // 2), max(0, y - th // 2)
        x1, y1 = min(r.shape[1], x + tw), min(r.shape[0], y + th)
        r[y0:y1, x0:x1] = -1.0
    return {"ok": True, "backend": "opencv.matchTemplate",
            "image_size": [iw, ih], "template_size": [tw, th],
            "template_std": round(tpl_std, 2),
            "threshold": threshold, "count": len(hits), "hits": hits}


def region_scan(image: str, min_area: int = 400, max_area: int = 400000,
                min_ratio: float = 0.15, max_ratio: float = 6.0,
                limit: int = 40) -> dict:
    """扫出画面里"像一块块"的矩形（按钮/输入框/卡片），按面积降序。不回图。"""
    import cv2
    if not image:
        return {"ok": False, "reason": "需要 image：本地截图路径"}
    img = _imread(image)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(gray, 40, 120)
    edges = cv2.dilate(edges, None, iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    rects = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < min_area or area > max_area or h == 0:
            continue
        ratio = w / float(h)
        if ratio < min_ratio or ratio > max_ratio:
            continue
        rects.append({"x": x, "y": y, "w": w, "h": h,
                      "cx": x + w // 2, "cy": y + h // 2,
                      "area": area, "ratio": round(ratio, 2)})
    rects.sort(key=lambda r: -r["area"])
    rects = rects[:limit]
    return {"ok": True, "backend": "opencv.findContours",
            "image_size": [img.shape[1], img.shape[0]],
            "count": len(rects), "rects": rects}


# ────────────────────────── 5. 统一入口 ──────────────────────────
def run(op: str = "decide", **kw) -> dict:
    op = str(op or "decide")
    if op in ("decide", "pick", "route"):
        return decide(kw.get("intent") or kw.get("query") or "")
    if op in ("status", "health"):
        return status(kw.get("group") or "")
    if op in ("matrix", "table", "all"):
        return matrix()
    if op == "template_match":
        return template_match(kw.get("image"), kw.get("template"),
                              float(kw.get("threshold") or 0.80),
                              int(kw.get("max_hits") or 5))
    if op == "region_scan":
        return region_scan(kw.get("image"))
    if op == "detect":
        from . import vision_detect as VD
        return VD.run("detect", **kw)
    if op in ("similarity", "embed", "nearest"):
        from . import vision_embed as VE
        return VE.run(op, **kw)
    return {"ok": False, "reason": "未知 op: %s（支持 decide/status/matrix/template_match/region_scan/detect/similarity/embed/nearest）" % op}
