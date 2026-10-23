# gbt-capability: dynamic-import, network
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
# compile_ok
"""
caps/design_brain/run.py — 设计大脑
=====================================
AI驱动3D真实图片生成:
  architect     — 建筑设计, 3D真实感外观
  interior      — 室内装修, 3D效果图
  renovate      — 翻新改造, 前后对比
  deploy_layout — 空间规划, 设备布局
  aesthetic     — 美观渲染增强
  prompt_builder — 构建专业3D渲染prompt
  style_guide   — 建筑/装修风格百科

输出: 专业3D渲染prompt + 可发送至AI图像生成API
"""
import sys, json, os, urllib.request, urllib.error
from pathlib import Path

# API配置
API_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("KIMI_API_KEY") or ""
IMAGE_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("STABILITY_KEY") or ""
BASE_URL = os.environ.get("GBT_LLM_BASE_URL", "https://api.deepseek.com")
MODEL = os.environ.get("GBT_LLM_MODEL", "deepseek-flash")  # 官方唯一 id：deepseek-flash = DeepSeek-V4.1-Flash

# ═══════════════════════════════════════════════════════════
#  建筑与室内风格百科全书
# ═══════════════════════════════════════════════════════════

STYLES = {
    "建筑外观": {
        "现代简约":   "clean lines, floor-to-ceiling glass, white concrete, flat roof, minimal ornamentation",
        "新中式":     "traditional Chinese courtyard, grey brick, wood lattice, sloping tile roof, moon gate",
        "北欧":       "wood cladding, gable roof, large windows, natural materials, muted earth tones",
        "工业风":     "exposed brick, steel beams, concrete floors, black metal windows, loft style",
        "地中海":     "white stucco walls, terracotta roof tiles, arched windows, wrought iron details",
        "日式":       "wooden structure, sliding doors, engawa veranda, zen garden, dark wood, simple geometry",
        "极简主义":   "pure geometric forms, monochrome palette, hidden details, seamless surfaces",
        "未来主义":   "parametric facade, fluid curves, LED integration, smart glass, biomimetic forms",
        "巴洛克":     "ornate stone carvings, gold accents, grand columns, dramatic dome, symmetrical",
        "热带度假":   "thatched roof, open pavilion, infinity pool, bamboo, lush landscaping"
    },
    "室内装修": {
        "现代轻奢":   "marble accent wall, brass fixtures, velvet furniture, recessed lighting, neutral palette",
        "奶油风":     "warm beige tones, curved furniture, plush textiles, soft ambient light, rounded arches",
        "侘寂":       "raw plaster walls, handmade ceramics, linen textiles, weathered wood, imperfect beauty",
        "北欧":       "light oak floors, white walls, cozy textiles, pendant lights, plants, functional",
        "工业 loft":  "exposed brick, polished concrete, metal pendant lights, leather sofa, open plan",
        "法式复古":   "herringbone parquet, crown molding, marble fireplace, crystal chandelier, silk drapes",
        "日式禅意":   "tatami mats, shoji screens, low wooden table, bonsai, natural light, minimal",
        "美式乡村":   "hardwood floors, shiplap walls, farmhouse sink, barn doors, cozy fireplace",
        "Art Deco":   "geometric patterns, gold + black, velvet, mirrored surfaces, bold symmetry",
        "孟菲斯":     "bold colors, geometric shapes, terrazzo, squiggly lines, playful, 80s aesthetic"
    }
}

RENDER_QUALITY = (
    "photorealistic, 8K resolution, Unreal Engine 5 render, "
    "ray tracing global illumination, cinematic lighting, "
    "architectural photography, wide angle lens 24mm, "
    "shallow depth of field, professional color grading, "
    "ultra detailed textures, ambient occlusion, subsurface scattering"
)

# ═══════════════════════════════════════════════════════════
#  LLM调用
# ═══════════════════════════════════════════════════════════

def _call_llm(system: str, user: str, temperature: float = 0.5) -> dict:
    if not API_KEY:
        return {"ok": False, "error": "未配置LLM API Key"}
    try:
        data = json.dumps({
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "max_tokens": 2000,
            "temperature": temperature
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/chat/completions", data=data,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        return {"ok": True, "content": resp["choices"][0]["message"]["content"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ═══════════════════════════════════════════════════════════
#  Prompt构建器 — 核心引擎
# ═══════════════════════════════════════════════════════════

def build_prompt(domain: str, style: str, description: str,
                 space_type: str = "", extra: str = "") -> dict:
    """构建专业3D渲染prompt"""
    
    style_map = STYLES.get(domain, STYLES["室内装修"])
    style_prompt = style_map.get(style, "")
    
    if not style_prompt and API_KEY:
        # LLM动态匹配风格
        llm = _call_llm(
            "你是建筑/室内设计专家。根据描述匹配最合适的风格关键词(英文)。只返回关键词。",
            f"领域: {domain}\n描述: {description}\n空间类型: {space_type}"
        )
        if llm.get("ok"):
            style_prompt = llm["content"].strip()
    
    if not style_prompt:
        style_prompt = "modern contemporary"

    # 组装完整prompt
    parts = [
        f"{space_type + ', ' if space_type else ''}{style} style {domain}",
        style_prompt,
        description,
        RENDER_QUALITY,
        extra
    ]
    
    full_prompt = ", ".join(p for p in parts if p).strip(", ")
    
    return {
        "ok": True,
        "prompt": full_prompt,
        "domain": domain,
        "style": style,
        "space_type": space_type,
        "render_engine": "Unreal Engine 5 / ray tracing",
        "resolution": "8K",
        "generation_note": "将此prompt发送至AI图像生成API (DALL-E 3 / Midjourney / Stable Diffusion XL)",
        "image_api_ready": {
            "dalle": {"prompt": full_prompt, "size": "1024x1024", "quality": "hd", "style": "vivid"},
            "midjourney": {"prompt": f"{full_prompt} --ar 16:9 --style raw --q 2 --v 6.1"},
            "sd_xl": {"prompt": full_prompt, "negative_prompt": "low quality, blurry, cartoon, 2D, flat"}
        }
    }

# ═══════════════════════════════════════════════════════════
#  动作处理函数
# ═══════════════════════════════════════════════════════════

def do_architect(params: dict) -> dict:
    """建筑设计 — 建筑外观3D效果图"""
    desc = params.get("description", params.get("prompt", ""))
    style = params.get("style", "现代简约")
    btype = params.get("building_type", params.get("type", ""))
    extra = params.get("extra", "")
    
    result = build_prompt("建筑外观", style, desc, btype, extra)
    result["action"] = "architect"
    result["view_angles"] = [
        "front elevation 正面视角 — 展示主立面",
        "aerial view 鸟瞰视角 — 展示整体布局与周边环境",
        "golden hour shot 黄金时刻 — 日落暖光渲染建筑质感",
        "night scene 夜景 — 灯光设计展示"
    ]
    return result


def do_interior(params: dict) -> dict:
    """室内装修设计 — 3D效果图"""
    desc = params.get("description", params.get("prompt", ""))
    style = params.get("style", "现代轻奢")
    room = params.get("room", params.get("space", "客厅"))
    area = params.get("area", "")
    extra = params.get("extra", "")
    
    extra_full = f"{extra}, {area + 'sqm' if area else ''}".strip(", ")
    result = build_prompt("室内装修", style, desc, room, extra_full)
    result["action"] = "interior"
    result["view_angles"] = [
        f"wide shot {room}全景 — 展示整体空间感",
        f"corner view {room}角落 — 展示材质细节",
        f"top-down {room}俯视 — 展示家具布局",
        "close-up 特写 — 展示材质和光影细节"
    ]
    result["material_palette"] = _suggest_materials(style)
    result["lighting_plan"] = _suggest_lighting(style, room)
    return result


def do_renovate(params: dict) -> dict:
    """翻新改造 — 前后对比"""
    desc = params.get("description", params.get("prompt", ""))
    style = params.get("style", "现代轻奢")
    room = params.get("room", params.get("space", "全屋"))
    before_desc = params.get("before", "老旧装修，墙皮脱落，管线外露")
    
    before = build_prompt("室内装修", "老旧", 
                          f"before renovation: {before_desc}, old and worn", room,
                          "dated interior, poor lighting, worn surfaces")
    after = build_prompt("室内装修", style, desc, room,
                         "completely transformed, brand new, stunning")
    
    return {
        "ok": True,
        "action": "renovate",
        "room": room,
        "target_style": style,
        "before": before,
        "after": after,
        "comparison_note": "生成两图拼接: 左侧Before + 右侧After",
        "renovation_plan": _renovation_plan(room, style)
    }


def do_deploy_layout(params: dict) -> dict:
    """部署布局 — 空间规划3D图"""
    desc = params.get("description", params.get("prompt", ""))
    space = params.get("space", params.get("room", "办公空间"))
    layout_type = params.get("layout_type", "open_plan")
    
    layout_styles = {
        "open_plan":     "open floor plan, collaborative zones, glass partitions, biophilic elements",
        "cellular":      "private offices, corridor layout, acoustic panels, focused work zones",
        "hybrid":        "hot desks, meeting pods, lounge areas, standing desks, agile workspace",
        "retail":        "customer flow, display islands, checkout counter, ambient lighting, signage",
        "restaurant":    "dining zones, open kitchen view, bar seating, mood lighting, acoustic treatment",
        "residential":   "living zones, traffic flow, storage solutions, natural light optimization"
    }
    
    layout_desc = layout_styles.get(layout_type, layout_styles["open_plan"])
    
    prompt = (
        f"3D floor plan visualization, {space}, {layout_desc}, "
        f"top-down isometric view, furniture layout, traffic flow arrows, "
        f"color-coded zones (work=blue, meeting=green, social=orange, quiet=yellow), "
        f"{desc}, "
        f"unreal engine 5 render, architectural visualization, 8K, isometric perspective"
    )
    
    return {
        "ok": True,
        "action": "deploy_layout",
        "prompt": prompt,
        "space": space,
        "layout_type": layout_type,
        "image_api_ready": {
            "dalle": {"prompt": prompt, "size": "1024x1024", "quality": "hd"},
            "midjourney": {"prompt": f"{prompt} --ar 1:1 --style raw --v 6.1"}
        },
        "zones": [
            {"name": "工作区", "color": "blue", "pct": 45},
            {"name": "会议区", "color": "green", "pct": 20},
            {"name": "社交区", "color": "orange", "pct": 15},
            {"name": "安静区", "color": "yellow", "pct": 20}
        ]
    }


def _match_aesthetic(text: str) -> str:
    """按输入语义自动匹配 aesthetic 风格（修复：旧实现恒用默认 warm_luxury）。"""
    t = (text or "").lower()
    rules = [
        ("cyberpunk", ("cyberpunk", "neon", "futuristic", "赛博", "霓虹", "未来")),
        ("zen", ("zen", "禅", "bamboo", "meditat", "peace", "日式", "和风")),
        ("natural", ("nature", "plant", "wood", "organic", "biophilic", "自然", "木", "绿植", "森林")),
        ("cool_minimal", ("minimal", "minimalist", "grey", "gray", "white", "极简", "简约", "冷", "无印")),
        ("dramatic", ("dramatic", "moody", "spotlight", "cinematic", "戏剧", "聚光", "高对比")),
        ("warm_luxury", ("luxury", "gold", "brass", "marble", "elegant", "豪华", "奢华", "金", "大理石", "暖")),
    ]
    for style, kws in rules:
        if any(k in t for k in kws):
            return style
    return "warm_luxury"


def do_aesthetic(params: dict) -> dict:
    """美观渲染增强 — 提升审美质量"""
    desc = params.get("prompt", params.get("description", ""))
    quality = params.get("quality", "ultra")
    
    quality_levels = {
        "ultra":  "photorealistic, 8K, unreal engine 5, ray tracing, cinematic, HDR, award-winning architectural photography",
        "high":   "photorealistic, 4K, vray render, professional lighting, detailed textures",
        "medium": "realistic, 2K, good lighting, clean composition",
        "artistic": "artistic architectural visualization, dramatic lighting, magazine cover quality, editorial style"
    }
    
    q = quality_levels.get(quality, quality_levels["ultra"])
    
    aesthetic_styles = params.get("aesthetic") or _match_aesthetic(desc)
    aesthetics = {
        "warm_luxury":   "warm golden hour light, marble and brass, soft shadows, elegant, quiet luxury",
        "cool_minimal":  "cool daylight, white and grey palette, sharp shadows, minimalist, serene",
        "dramatic":      "dramatic contrast, deep shadows, spotlighting, moody atmosphere, cinematic",
        "natural":        "soft diffused daylight, plants, wood textures, organic shapes, biophilic",
        "cyberpunk":     "neon lights, reflective surfaces, dark atmosphere, futuristic, high contrast",
        "zen":           "soft natural light, bamboo, stone, water feature, peaceful, meditative"
    }
    
    a = aesthetics.get(aesthetic_styles, aesthetics["warm_luxury"])
    
    enhanced = f"{desc}, {q}, {a}"
    
    return {
        "ok": True,
        "action": "aesthetic",
        "original": desc,
        "enhanced": enhanced,
        "quality_level": quality,
        "aesthetic": aesthetic_styles,
        "style_matched": True,
        "image_api_ready": {
            "dalle": {"prompt": enhanced, "size": "1024x1024", "quality": "hd", "style": "vivid"}
        }
    }


def do_prompt_builder(params: dict) -> dict:
    """Prompt构建器 — 将中文需求转为专业3D渲染prompt"""
    desc = params.get("prompt", params.get("description", ""))
    domain = params.get("domain", "室内装修")
    style = params.get("style", "")
    
    if not API_KEY:
        return {
            "ok": True,
            "action": "prompt_builder",
            "input": desc,
            "prompt": f"3D render, {domain}, {style}, {desc}, {RENDER_QUALITY}",
            "mode": "rule_based"
        }
    
    system = f"""你是顶尖建筑可视化专家。将用户的中文描述转换为专业3D渲染prompt(英文)。

规则:
1. 开头: 空间类型 + 风格 + 视角 (如 "wide shot of a modern living room")
2. 中间: 材质/家具/色彩/灯光 具体描述
3. 结尾: {RENDER_QUALITY}
4. 长度: 150-300词
5. 只返回最终prompt，不加前缀

参考风格关键词池: {json.dumps(list(STYLES.get(domain, {}).keys()), ensure_ascii=False)}"""
    
    llm = _call_llm(system, f"领域: {domain}\n风格倾向: {style}\n用户描述: {desc}")
    
    if llm.get("ok"):
        return {"ok": True, "action": "prompt_builder", "input": desc,
                "prompt": llm["content"].strip(), "mode": "llm_enhanced"}
    
    return {"ok": True, "action": "prompt_builder", "input": desc,
            "prompt": f"3D render, {domain}, {style}, {desc}, {RENDER_QUALITY}",
            "mode": "rule_based"}


def do_style_guide(params: dict) -> dict:
    """风格指南 — 返回所有支持的风格"""
    domain = params.get("domain", "")
    if domain and domain in STYLES:
        return {"ok": True, "action": "style_guide", 
                "domain": domain, "styles": list(STYLES[domain].keys())}
    return {"ok": True, "action": "style_guide", 
            "domains": {d: list(s.keys()) for d, s in STYLES.items()}}

# ═══════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════

def _suggest_materials(style: str) -> list:
    pool = {
        "现代轻奢": ["大理石", "黄铜", "天鹅绒", "胡桃木", "钢化玻璃"],
        "奶油风":   ["微水泥", "亚麻", "羊毛", "藤编", "哑光漆面"],
        "侘寂":     ["手工陶土", "原木", "亚麻", "石灰泥", "竹"],
        "北欧":     ["橡木", "羊毛毡", "陶瓷", "皮革", "棉麻"],
        "工业 loft": ["抛光混凝土", "红砖", "黑铁", "回收木", "金属网"],
        "法式复古": ["人字拼木地板", "大理石", "水晶", "丝绸", "石膏线"],
        "日式禅意": ["榻榻米", "杉木", "和纸", "竹", "硅藻土"],
    }
    return pool.get(style, ["实木", "天然石材", "金属", "玻璃", "布艺"])


def _suggest_lighting(style: str, room: str) -> dict:
    return {
        "主光源": f"暖色LED筒灯 3000K (适合{style})",
        "氛围灯": "隐藏式LED灯带 + 落地灯 + 壁灯",
        "自然光": f"{room}朝南大窗 + 电动百叶帘",
        "重点照明": "轨道射灯照装饰画/植物",
        "色温": "2700K-3000K (暖白)",
        "显色指数": "CRI ≥ 95"
    }


def _renovation_plan(room: str, style: str) -> dict:
    return {
        "phase1_拆除": ["旧墙纸/瓷砖", "老化管线", "非承重隔墙"],
        "phase2_水电": ["全屋水电重走", "智能家居布线", "地暖铺设"],
        "phase3_硬装": [f"{style}风格墙面处理", "地面铺设", "吊顶+灯光预埋"],
        "phase4_软装": ["定制柜体安装", "家具进场", "窗帘+灯具+装饰"],
        "estimated_time": "45-60天",
        "budget_range": "中高端 (1500-3000元/㎡)"
    }


# ═══════════════════════════════════════════════════════════
#  🤖 ControlNet真实渲染引擎 (深度学习注入)
#  技术: Depth Anything V2 + ControlNet + Stable Diffusion
#  来源: agentbus.sh + huggingface diffusers + 自主深度学习
# ═══════════════════════════════════════════════════════════

CONTROLNET_STYLES = [
    {
        "name": "minimalist_scandinavian",
        "label": "北欧极简",
        "prompt": "minimalist Scandinavian living room, white oak floors, light gray linen sofa, "
                  "white walls, single pendant lamp, wool throw blanket, diffused natural light, "
                  "interior design magazine photo, clean lines, 8k, photorealistic",
        "seed": 42,
    },
    {
        "name": "industrial_loft",
        "label": "工业Loft",
        "prompt": "industrial loft living room, exposed brick walls, steel beam ceiling, "
                  "dark leather chesterfield sofa, Edison bulb lighting, concrete floor, "
                  "reclaimed wood coffee table, moody warm lighting, architectural photography, 8k",
        "seed": 77,
    },
    {
        "name": "japanese_wabisabi",
        "label": "日式侘寂",
        "prompt": "Japanese minimalist living room, tatami flooring, low wooden platform furniture, "
                  "shoji screen panels, bonsai on shelf, neutral earth tones, indirect warm lighting, "
                  "wabi-sabi aesthetic, interior photography, 8k, photorealistic",
        "seed": 123,
    },
    {
        "name": "modern_luxury",
        "label": "现代轻奢",
        "prompt": "modern luxury living room, marble accent wall, brass fixtures, velvet emerald sofa, "
                  "geometric gold accents, crystal chandelier, lacquered dark wood, rich jewel tones, "
                  "luxury interior photography, 8k, photorealistic, ray tracing",
        "seed": 256,
    },
    {
        "name": "creamy_warm",
        "label": "奶油温馨",
        "prompt": "warm creamy toned living room, curved furniture, plush boucle sofa, "
                  "sheer linen curtains, soft ambient lighting, rounded arch doorway, "
                  "microcement walls, warm beige palette, cozy atmosphere, 8k, photorealistic",
        "seed": 501,
    },
]

CONTROLNET_NEGATIVE = (
    "blurry, cartoon, sketch, low quality, deformed, watermark, dark, oversaturated, "
    "plastic, cluttered, distorted, bad anatomy, ugly, pixelated, jpeg artifacts"
)

CONTROLNET_PARAMS = {
    "model": "lllyasviel/sd-controlnet-depth",
    "base": "stable-diffusion-v1-5/stable-diffusion-v1-5",
    "depth_estimator": "depth-anything/Depth-Anything-V2-Small-hf",
    "image_size": 512,
    "num_inference_steps": 25,
    "controlnet_conditioning_scale": 0.75,
    "guidance_scale": 7.5,
    "scheduler": "UniPCMultistepScheduler",
    "dtype": "float16",
}


def do_controlnet_render(params: dict) -> dict:
    """ControlNet真实渲染 — 深度估计+5风格批量生成"""
    image_path = params.get("image", params.get("photo", ""))
    room = params.get("room", "客厅")
    
    if not image_path:
        return {
            "ok": True, "action": "controlnet_render",
            "mode": "code_only",
            "note": "需要提供房间照片路径，返回完整渲染代码",
            "setup_code": _generate_setup_code(),
            "render_code": _generate_render_code(room),
            "styles": [{s["name"]: s["label"]} for s in CONTROLNET_STYLES],
            "params": CONTROLNET_PARAMS,
            "tuning_guide": {
                "conditioning_scale": "0.75最佳。>0.9边缘过硬, <0.5布局漂移",
                "guidance_scale": "7.5最佳。>10颜色过饱和, <5画面平淡",
                "depth_smoothing": "用MedianFilter(size=5)平滑深度图,保留边缘",
                "oom_fix": "enable_attention_slicing() + enable_vae_tiling()",
                "image_resize": "必须resize到512x512(LANCZOS),自动缩放会模糊深度信息",
            }
        }
    
    # 有图片→生成可执行渲染脚本
    return {
        "ok": True, "action": "controlnet_render",
        "image": image_path,
        "room": room,
        "execution_script": _generate_full_script(image_path, room),
        "styles_count": len(CONTROLNET_STYLES),
        "estimated_time": f"约{len(CONTROLNET_STYLES) * 6}秒(GPU)",
    }


def _generate_setup_code() -> str:
    """生成环境安装代码"""
    return """# 安装依赖
pip install diffusers transformers accelerate torch pillow numpy

# 验证GPU可用
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"

# 如CUDA不可用, 切换CPU模式:
# export CUDA_VISIBLE_DEVICES="" (Linux/Mac)
# 或修改代码中 torch_dtype=torch.float32, 移除.cuda()"""


def _generate_render_code(room: str) -> str:
    """生成5风格批量渲染代码"""
    styles_json = json.dumps(CONTROLNET_STYLES, ensure_ascii=False, indent=4)
    return f'''import torch
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel, UniPCMultistepScheduler
from PIL import Image, ImageFilter
from transformers import pipeline
import numpy as np

# ① 深度估计 (Depth Anything V2)
depth_estimator = pipeline(
    task="depth-estimation",
    model="{CONTROLNET_PARAMS['depth_estimator']}",
)
room_photo = Image.open("your_room.jpg").convert("RGB").resize((512, 512))
depth_result = depth_estimator(room_photo)
depth_map = depth_result["depth"]
# 平滑去噪 (保留边缘)
depth_smoothed = depth_map.filter(ImageFilter.MedianFilter(size=5))
depth_smoothed.save("depth_map.png")

# ② ControlNet + Stable Diffusion
controlnet = ControlNetModel.from_pretrained(
    "{CONTROLNET_PARAMS['model']}",
    torch_dtype=torch.float16,
)
pipe = StableDiffusionControlNetPipeline.from_pretrained(
    "{CONTROLNET_PARAMS['base']}",
    controlnet=controlnet,
    torch_dtype=torch.float16,
)
pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
pipe.enable_model_cpu_offload()
pipe.enable_attention_slicing()  # 节省VRAM

# ⛔ Flipbook四件套 (2026-08-13 深度吸收): 计算图融合 + CUDA Graph内存快照 + 激活缓存
#   torch.compile → 整体计算图融合优化内核, 消除Python逐操作调度开销
#   reduce-overhead → 录制静态GPU执行图重放, 消除调度间隙(支持视频级连续生成)
#   warmup一次 → 后续批量渲染复用快照, 不重新编译
try:
    import  t
    if _t.cuda.is_available():
        pipe.unet = _t.compile(pipe.unet, mode="reduce-overhead")
        pipe.controlnet = _t.compile(pipe.controlnet, mode="reduce-overhead")
        _warm = pipe(
            prompt=styles[0]["prompt"], negative_prompt=negative,
            image=depth_image, num_inference_steps=1, controlnet_conditioning_scale=0.75,
        )
        del _warm
        _t.cuda.empty_cache()
        print("[Flipbook四件套] torch.compile + CUDA Graph 已启用, 批量渲染提速")
    else:
        print("[Flipbook四件套] 无CUDA, 跳过编译(CPU模式)")
except  e:
    print(f"[Flipbook四件套] torch.compile 降级跳过: {{_e}}")  # 版本/驱动不支持时回退原管线

# ③ 5风格批量渲染
depth_image = depth_smoothed.convert("RGB").resize((512, 512), Image.LANCZOS)
styles = {styles_json}
negative = "{CONTROLNET_NEGATIVE}"

for style in styles:
    generator = torch.Generator(device="cpu").manual_seed(style["seed"])
    result = pipe(
        prompt=style["prompt"],
        negative_prompt=negative,
        image=depth_image,
        num_inference_steps={CONTROLNET_PARAMS['num_inference_steps']},
        controlnet_conditioning_scale={CONTROLNET_PARAMS['controlnet_conditioning_scale']},
        guidance_scale={CONTROLNET_PARAMS['guidance_scale']},
        generator=generator,
    ).images[0]
    result.save(f"render_{{style['name']}}_{{room}}.png")
    print(f"✅ {{style['label']}} 完成 → render_{{style['name']}}_{{room}}.png")

print("\\n🎨 5风格{room}渲染全部完成!")
print("查看: render_*_{room}.png")'''


def _generate_full_script(image_path: str, room: str) -> str:
    """生成可直接执行的完整渲染脚本"""
    return _generate_render_code(room).replace("your_room.jpg", image_path)


def do_controlnet_guide(params: dict) -> dict:
    """ControlNet渲染指南 — 参数调优+常见问题"""
    return {
        "ok": True, "action": "controlnet_guide",
        "title": "ControlNet室内设计渲染完全指南",
        "pipeline": [
            "① 拍摄房间照片(手机即可, 光线充足)",
            "② Depth Anything V2 提取深度图",
            "③ MedianFilter(size=5) 平滑深度图",
            "④ ControlNet + SD 批量渲染5种风格",
            "⑤ 对比选择最佳方案",
        ],
        "params_tuning": {
            "controlnet_conditioning_scale": {
                "optimal": 0.75,
                "range": "0.6-0.9",
                "too_high": ">0.9 家具边缘过硬,像描边",
                "too_low": "<0.5 布局漂移, 墙移位",
            },
            "guidance_scale": {
                "optimal": 7.5,
                "range": "7.0-8.0",
                "too_high": ">10 颜色过饱和,像HDR",
                "too_low": "<5 画面平淡,缺少细节",
            },
            "num_inference_steps": "25步(UniPC), 30步(默认scheduler)",
        },
        "common_errors": [
            {"error": "CUDA out of memory", 
             "fix": "enable_attention_slicing() + enable_vae_tiling() + enable_model_cpu_offload()"},
            {"error": "深度图模糊/边缘不清",
             "fix": "照片增加亮度+对比度 → MedianFilter去噪 → resize到512x512(LANCZOS)"},
            {"error": "颜色过饱和/褪色",
             "fix": "调整guidance_scale: 7.0-8.0是甜点区"},
            {"error": "房间布局不对",
             "fix": "提高controlnet_conditioning_scale到0.8-0.85, 检查深度图质量"},
            {"error": "生成速度慢",
             "fix": "UniPC scheduler + float16 + 25步 → 每张约4-6秒"},
        ],
        "vrang_requirements": "GPU≥8GB VRAM (RTX 3060+). CPU模式可用但每张约2-3分钟.",
        "reference": "agentbus.sh + huggingface/diffusers + Depth-Anything-V2",
    }

# ═══════════════════════════════════════════════════════════
#  Web 3D 展示 — 使用 gbt-3d.js 生成完整3D网页
# ═══════════════════════════════════════════════════════════

GBT3D_SPEC = """
你生成的HTML必须使用GBT 3D v2框架。可用标签:
- <div data-gbt3d="particles" data-count="2000" data-color="#00d4ff" data-rings="3">
- <div data-gbt3d="globe" data-markers="true">  3D地球(默认4城市标记)
- <div data-gbt3d="globe" data-markers="/api/active-ips">  动态数据地球
- <div data-beam="from:#a, to:#b" data-beam-color="#00d4ff">  光效连线
- <div class="gbt-reveal">  滚动入场动画
- <div data-parallax data-parallax-depth="2">  鼠标视差(移动端自动禁用)
颜色: 科技蓝#00d4ff 金#ffd700 紫#a855f7 绿#22c55e
背景: #0a0a0f  卡片: rgba(255,255,255,0.04) backdrop-filter:blur(16px)
必须引入: <script src="/assets/gbt-3d.js" defer></script>
"""

CARD_TEMPLATE = '<div class="gbt-reveal" style="position:relative;z-index:1;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:32px;backdrop-filter:blur(16px);max-width:800px;margin:40px auto;">{content}</div>'

def do_web3d_showcase(params: dict) -> dict:
    """生成带3D效果的完整HTML展示页"""
    theme = params.get("theme", "科技")
    title = params.get("title", "GBT Showcase")
    sections = params.get("sections", [])
    globe = params.get("globe", True)
    beams = params.get("beams", [])
    
    color_map = {"科技": "#00d4ff", "金融": "#ffd700", "创意": "#a855f7", "环保": "#22c55e", "暗黑": "#ff4444"}
    color = color_map.get(theme, "#00d4ff")
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | GBT</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a0f;color:#fff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow-x:hidden}}
h1{{font-size:clamp(2rem,5vw,4rem);background:linear-gradient(135deg,{color},#fff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;padding:60px 20px 20px}}
h2{{color:{color};font-size:clamp(1.2rem,3vw,1.8rem);margin:0 0 16px}}
h3{{color:{color};font-size:1.2rem;margin:0 0 8px}}
p{{color:rgba(255,255,255,0.7);line-height:1.7;font-size:1rem}}
</style></head>
<body>
<div data-gbt3d="particles" data-count="2000" data-color="{color}" data-rings="3"
     style="position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:0;pointer-events:none;opacity:0.5"></div>
'''
    if globe:
        html += f'''
<div data-gbt3d="globe" data-markers="true" data-color="{color}"
     style="position:absolute;top:20px;right:20px;width:280px;height:280px;z-index:2;opacity:0.85"></div>
'''
    html += '<h1 data-parallax data-parallax-depth="1">' + title + '</h1>'
    
    for i, section in enumerate(sections):
        html += CARD_TEMPLATE.format(content=f'''
<h2>{"0"+str(i+1) if i<9 else str(i+1)} · {section.get("title","")}</h2>
<p>{section.get("body","")}</p>
''')
    
    for beam in beams:
        html += f'<div data-beam="from:{beam.get("from","")}, to:{beam.get("to","")}" data-beam-color="{color}"></div>'
    
    html += '\n<script src="/assets/gbt-3d.js" defer></script>\n</body></html>'
    
    return {"ok": True, "action": "web3d_showcase", "html": html, "theme": theme, "title": title}


def do_web3d_prompt(params: dict) -> dict:
    """用LLM生成3D网页设计提示词"""
    description = params.get("description", "")
    theme = params.get("theme", "科技")
    
    if not API_KEY:
        return do_web3d_showcase({"theme": theme, "title": description[:30] or "GBT Page"})
    
    llm = _call_llm(
        f"你是GBT 3D网页设计师。{GBT3D_SPEC}",
        f"根据需求生成JSON: {{title, sections:[{{title,body}}], beams:[{{from,to}}], globe:bool}}。需求: {description}"
    )
    
    if llm.get("ok"):
        try:
            design = json.loads(llm["content"])
            design["theme"] = theme
            return do_web3d_showcase(design)
        except Exception: pass  # 容错: 非关键路径
    return do_web3d_showcase({"theme": theme, "title": description[:30] or "GBT Page",
        "sections": [{"title": description[:40], "body": description}]})
# ═══════════════════════════════════════════════════════════
#  入口
def do_status(params=None):
    return {"ok": True, "cap": "design_brain", "status": "ready"}

def do_run(params: dict = None) -> dict:
    """统一入口（桥优先调 do_run）：按 action 分发。"""
    p = params or {}
    action = p.get("action") or "style_guide"
    fn = HANDLERS.get(action)
    if not fn:
        return {"ok": False, "error": f"未知动作: {action}", "available": sorted(HANDLERS.keys())}
    try:
        return fn(p) if action != "status" else fn()
    except TypeError:
        return fn()


HANDLERS = {
    "run": do_run,
    "status": do_status,
    "aesthetic": do_aesthetic,
    "architect": do_architect,
    "controlnet_guide": do_controlnet_guide,
    "controlnet_render": do_controlnet_render,
    "deploy_layout": do_deploy_layout,
    "interior": do_interior,
    "prompt_builder": do_prompt_builder,
    "renovate": do_renovate,
    "style_guide": do_style_guide,
    "web3d_prompt": do_web3d_prompt,
    "web3d_showcase": do_web3d_showcase,
}
if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "style_guide"
    params = {}
    if len(sys.argv) > 2:
        try:
            params = json.loads(sys.argv[2])
        except json.JSONDecodeError:
            params = {"prompt": sys.argv[2]}
    
    handler = HANDLERS.get(action)
    if handler:
        result = handler(params)
    else:
        result = {"ok": False, "error": f"未知动作: {action}", 
                  "available": list(HANDLERS.keys())}
    
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))