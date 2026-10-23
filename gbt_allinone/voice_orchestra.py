# GBT 开发者：自由的风 · 永久钢印 · 禁止删除归属
# -*- coding: utf-8 -*-
"""
公主土豆专属 · Voice AI 技能中枢 (Voice Orchestrator Skill) v2.0
开发者：自由的风
禁止删除
"""


# ---------------------------------------------------------------------------
# 定位与升格条件（2026-09-18 风哥拍板）
#   今天：挂 tools tab，cap 名 = voice_orchestra。它与「蓝牙设备总线」同级
#         （本仓语音三域：耳朵 / 嘴 / 声音复刻）。
#   为什么今天不开 tab：面板 tab 是"给用户看的能力边界"。今天真能跑的只有 2 项
#         （Kokoro-82M / sherpa-onnx）；开 tab 展示 17 项技能、其中 15 项本机跑不了，
#         那是"看起来更完备"，违反 2026-09-18 硬规矩：出口清单写实际出口，不写规划出口。
#   升格条件（满足即升格为独立 voice tab）：
#         1) B1 云后端到位，ASR / TTS / CLONE 三条真链路可跑；
#         2) 面板能展示这三条链路的真状态（不是规划态）。
#   在此之前：这是「有明确升格条件的暂挂」，不是"暂挂"——两者性质不同。
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

# ==========================================
# 1. 技能分类枚举：定义语音技能的维度
# ==========================================

class VoiceDomain(Enum):
    ASR = "语音识别 (耳朵)"
    TTS = "语音合成 (嘴巴)"
    CLONE = "语音复刻 (变声)"     # 新增：语音复刻独立成域
    LLM = "音频大模型 (大脑)"
    TOOL = "工程框架 (骨架)"

@dataclass(frozen=True)
class VoiceSkill:
    """语音技能原子：封装单个开源项目的能力"""
    name: str
    domain: VoiceDomain
    provider: str
    highlights: List[str]
    deployment: str
    license_type: str
    recommended_scene: str

# ==========================================
# 2. 技能库集成：新增语音复刻专属技能
# ==========================================

VOICE_SKILL_REGISTRY: List[VoiceSkill] = [
    # --- 耳朵 (ASR) ---
    VoiceSkill("Whisper", VoiceDomain.ASR, "OpenAI", ["多语言", "泛化强", "生态极好"], "本地/云端", "MIT", "通用转录、翻译"),
    VoiceSkill("Qwen3-ASR", VoiceDomain.ASR, "阿里千问", ["0.6B/1.7B双尺寸", "性能均衡"], "本地/云端", "Apache-2.0", "中文优先、流式识别"),
    VoiceSkill("VibeVoice-ASR", VoiceDomain.ASR, "微软", ["60分钟长音频", "50+语言", "WER 7.77%"], "本地/云端", "MIT", "会议记录、超长播客"),

    # --- 嘴巴 (TTS) ---
    VoiceSkill("VoxCPM 2", VoiceDomain.TTS, "面壁智能", ["2B参数", "30语言", "48kHz", "音色设计"], "本地", "Apache-2.0", "高保真配音、有声书"),
    VoiceSkill("CosyVoice2", VoiceDomain.TTS, "阿里FunAudioLLM", ["零样本克隆", "流式合成", "首包延迟150ms"], "本地/云端", "Apache-2.0", "实时对话、语音助手"),
    VoiceSkill("Kokoro-82M", VoiceDomain.TTS, "Hexgrad", ["仅82M参数", "极速推理", "效果好"], "本地/CPU", "Apache-2.0", "端侧部署、轻量应用"),

    # --- 变声 (Voice Clone) —— 本轮重点扩充 ---
    VoiceSkill("GPT-SoVITS", VoiceDomain.CLONE, "社区", ["5秒克隆", "中文优化", "少样本微调"], "本地", "MIT", "个人音色克隆、短视频配音、无障碍语音修复"),
    VoiceSkill("OpenVoice V2", VoiceDomain.CLONE, "MyShell", ["30秒克隆", "浏览器本地运行", "MIT可商用"], "浏览器/本地", "MIT", "Web端互动、隐私敏感场景"),
    VoiceSkill("Fish Speech", VoiceDomain.CLONE, "Fish Audio", ["10-30秒克隆", "13语言", "延迟<150ms"], "本地", "Apache-2.0", "实时语音对话、跨语言配音"),
    VoiceSkill("Qwen3-TTS", VoiceDomain.CLONE, "阿里千问", ["3秒声纹克隆", "97ms超低延迟", "自然语言设计声音"], "本地/云端", "Apache-2.0", "实时数字人、多语言客服"),
    VoiceSkill("VibeVoice", VoiceDomain.CLONE, "微软", ["1分钟克隆", "60分钟长音频", "42k Star"], "本地/云端", "MIT", "有声书制作、长视频配音"),
    VoiceSkill("Seed-VC", VoiceDomain.CLONE, "社区", ["零样本语音转换", "歌声转换", "实时支持"], "本地", "GPL-3.0", "歌声转换、实时变声直播"),
    VoiceSkill("VoiceStudio", VoiceDomain.CLONE, "Palash Deb", ["完全本地 · 646 语言", "克隆/设计/配音/转写", "已接本机 127.0.0.1:3900"], "本地（已接）", "AGPL-3.0", "一站式语音创作、视频配音工作流"),

    # --- 大脑 (Audio LLM) ---
    VoiceSkill("Qwen-Omni", VoiceDomain.LLM, "阿里", ["端到端多模态", "文本/音频/图像输入", "音频输出"], "本地/云端", "Apache-2.0", "全模态AI Agent"),
    VoiceSkill("Step-Audio 2", VoiceDomain.LLM, "阶跃星辰", ["8B全开源", "副语言推理"], "本地", "Apache-2.0", "情感交互、语音对话"),

    # --- 骨架 (Tool) ---
    VoiceSkill("sherpa-onnx", VoiceDomain.TOOL, "k2-fsa", ["本地运行", "ASR/TTS/说话人识别", "跨平台"], "本地", "Apache-2.0", "端侧集成、嵌入式"),
    VoiceSkill("NVIDIA NeMo", VoiceDomain.TOOL, "NVIDIA", ["可扩展", "企业级", "训练+推理"], "云端/本地", "Apache-2.0", "工业级语音流水线"),
]

# ==========================================
# 3. 技能调度引擎：多维度场景 Pipeline 构建
# ==========================================

class VoiceSkillEngine:
    def __init__(self):
        self.registry = VOICE_SKILL_REGISTRY

    def query(self, domain: Optional[VoiceDomain] = None, keyword: str = "") -> List[VoiceSkill]:
        """按领域或关键词检索技能"""
        results = self.registry
        if domain:
            results = [s for s in results if s.domain == domain]
        if keyword:
            results = [s for s in results if keyword.lower() in s.name.lower() or any(keyword.lower() in h.lower() for h in s.highlights)]
        return results

    def build_pipeline(self, scene: str, want_all: bool = False):
        """
        多维度场景 Pipeline 构建器。
        每个场景都精确编排 ASR / LLM / CLONE / TTS / TOOL 的原子技能。

        `want_all=True` 时返回**全部**链条（含兜底「默认」）—— 给"这个场景到底认不认"
        这类判断用；不传时行为与改动前逐字节相同。
        """
        pipelines = {

            # ====== 场景 1：实时语音助手 ======
            "实时对话": {
                "ASR (耳朵)": "Qwen3-ASR (0.6B) — 低延迟流式识别",
                "LLM (大脑)": "Step-Audio 2 — 情感与副语言理解",
                "TTS (嘴巴)": "CosyVoice2 — 流式零样本合成，首包延迟150ms",
                "调度骨架": "sherpa-onnx — 端侧低延迟编排",
                "推荐理由": "全链路追求低延迟与情感交互，适合数字人直播、智能客服。",
                "复刻接入点": "在 TTS 层挂载 VoiceSkill.CLONE，用 3 秒样本动态切换音色。",
            },

            # ====== 场景 2：有声书 / 播客制作 ======
            "有声书": {
                "Voice Clone (变声)": "GPT-SoVITS — 5秒克隆目标音色",
                "TTS (嘴巴)": "VoxCPM 2 — 48kHz 高保真合成，30语言9方言",
                "调度骨架": "本地脚本 / ComfyUI 批处理",
                "推荐理由": "追求极致音质与特定音色，适合长音频内容生产。",
                "复刻接入点": "先离线克隆主播音色，再批量合成全本有声书。",
            },

            # ====== 场景 3：视频配音 / 短视频创作 ======
            "视频配音": {
                "Voice Clone (变声)": "VibeVoice — 1分钟克隆，支持60分钟长音频",
                "TTS (嘴巴)": "Fish Speech — 10-30秒克隆，延迟<150ms",
                "调度骨架": "VoiceStudio — 一站式本地工作台，集成16个TTS引擎",
                "推荐理由": "覆盖长/短视频配音，支持多语言，适合MCN机构和独立创作者。",
                "复刻接入点": "VoiceStudio 内直接调用克隆引擎，配音+克隆+导出一体化。",
            },

            # ====== 场景 4：跨语言 / 跨方言内容出海 ======
            "跨语言配音": {
                "Voice Clone (变声)": "Qwen3-TTS — 3秒声纹克隆，10语言跨语种迁移",
                "TTS (嘴巴)": "CosyVoice2 / Fun-CosyVoice3 — 9语种18方言，中英混说",
                "调度骨架": "阿里百聆 SDK / 本地部署",
                "推荐理由": "保持原音色不变，无缝切换语种和方言，适合内容出海和跨境电商。",
                "复刻接入点": "Qwen3-TTS 克隆原声后，用 CosyVoice2 做跨语种合成。",
            },

            # ====== 场景 5：歌声转换 / 音乐创作 ======
            "歌声转换": {
                "Voice Clone (变声)": "Seed-VC — 零样本语音转换 + 歌声转换，实时支持",
                "TTS (嘴巴)": "Seed-VC 内置合成 / Fish Speech 辅助",
                "调度骨架": "本地 GPU 推理 / Gradio WebUI",
                "推荐理由": "专门处理歌声转换，保留旋律的同时替换音色，适合翻唱和虚拟歌手。",
                "复刻接入点": "Seed-VC 直接输入源歌声 + 目标音色参考音频，输出转换后歌声。",
            },

            # ====== 场景 6：无障碍辅助 / 语音修复 ======
            "无障碍语音修复": {
                "Voice Clone (变声)": "GPT-SoVITS — 5秒历史录音恢复原始声线",
                "TTS (嘴巴)": "VoxCPM 2 — 高保真合成，保留情感韵律",
                "调度骨架": "本地部署，保护隐私",
                "推荐理由": "为声带受损或失语患者重建自然语音，适合医疗辅助场景。",
                "复刻接入点": "用患者历史录音做少样本微调，合成日常交流语音。",
            },

            # ====== 默认兜底 ======
            "默认": {
                "提示": "请指定场景（实时对话 / 有声书 / 视频配音 / 跨语言配音 / 歌声转换 / 无障碍语音修复）",
                "可用技能域": "ASR / TTS / CLONE / LLM / TOOL",
                "快速开始": "先调用 query(domain=VoiceDomain.CLONE) 查看所有复刻技能",
            },
        }

        if want_all:
            return pipelines
        return pipelines.get(scene, pipelines["默认"])

    def pipeline_scenes(self) -> List[str]:
        """**有专属链条**的场景名（不含兜底的「默认」）。"""
        return sorted(k for k in self.build_pipeline("", want_all=True) if k != "默认")

    def resolve_pipeline(self, scene: str):
        """返回 `(链条, 是否命中专属场景)`。

        🔴 为什么必须有它（2026-09-25 实测抓到的**假绿灯**）：
        老实现只有 `pipelines.get(scene, pipelines["默认"])` —— 未知场景**静默兜底**成
        「默认」链条，而 `run(op="pipeline")` 又把**请求的场景名原样回显**在 `scene` 字段里
        ⇒ 调用方读到 `{"ok": true, "scene": "我瞎编的场景"}` 会**以为自己拿到了该场景的链条**。
        实测：`cap voice_orchestra '{"op":"pipeline","scene":"不存在的场景"}'` 返回 `ok:true`，
        而 `steps` 是「默认」那条 —— 读数在骗人，且骗得很自然。
        """
        ps = self.build_pipeline("", want_all=True)
        if scene in ps:
            return ps[scene], True
        return ps["默认"], False


def _cannot(rule: str, why: str, missing, **extra) -> dict:
    """R-H295 · ⑥ G1/G2：语音中枢**做不了**时的结构化上报。

    《触手覆盖矩阵.md》§三：耳组 2 个模块只有 1 个能报"做不了"，本文件是缺的那个。
    原来只有 {"ok": False, "error": "未知 domain: ..."} —— 人看得懂，机器分不出
    "是 domain 不认、还是 scene 没给"。现在把缺哪一样写进 missing。
    """
    out = {
        "ok": False,
        "unavailable": True,
        "denied": False,
        "rule": str(rule),
        "action": "voice_orchestra",
        "missing": list(missing or ()),
        "why": str(why)[:240],
        "error": str(why)[:240],  # 向后兼容：老调用方读 error
        "note": "语音中枢做不了 ⇒ 结构化上报：缺什么写在 missing 里。",
    }
    out.update(extra)
    return out


def run(op: str = "status", **params) -> dict:
    """中枢统一入口（只读三档）：list / pipeline / status。

    list     : 按域或关键词检索技能原子
    pipeline : 给定场景返回端到端技能链
    status   : 报告本机可跑性（以能 import 的后端为准，不猜）
    三档都不安装依赖、不写盘、不改配置。

    R-H295：默认值从 "list" 改成 "status"，与 139/140 个能力的口径对齐 ——
    空参调用应当先报「我自己现在能不能跑」，而不是先回一张技能表。
    list 与 status 都是只读，三档一律显式带 readonly 标记。
    """
    engine = VoiceSkillEngine()
    if op in ("list", "query", None):
        dom = None
        want = params.get("domain")
        if want:
            dom = VoiceDomain.__members__.get(str(want).strip().upper())
            if dom is None:
                return _cannot("voice_unknown_domain", "未知 domain: %s（可用 ASR/TTS/CLONE/LLM/TOOL）" % want, ["domain"])
        rows = engine.query(domain=dom, keyword=str(params.get("keyword") or ""))
        return {"ok": True, "readonly": True, "op": "list", "count": len(rows),
                "skills": [{"name": s.name, "domain": s.domain.name, "provider": s.provider,
                            "deployment": s.deployment, "license": s.license_type,
                            "scene": s.recommended_scene, "highlights": s.highlights}
                           for s in rows]}
    if op == "pipeline":
        scene = str(params.get("scene") or "")
        if not scene:
            return _cannot("voice_scene_required",
                                   "需要 scene（实时对话/有声书/视频配音/跨语言配音/歌声转换/无障碍语音修复）",
                                   ["scene"])
        steps, matched = engine.resolve_pipeline(scene)
        if not matched:
            # 🔴 未知场景**不许静默兜底成 ok:true**（2026-09-25 修的那条假绿灯）。
            #    改用本文件既有的 `_cannot()` 结构化上报口径：ok=False + 缺什么写 missing，
            #    并把**建议链条**与**可选场景名**一并给出 —— 信息一点没少，只是不再冒充"命中"。
            return _cannot("voice_scene_unknown",
                           "场景「%s」没有专属链条；可选场景：%s"
                           % (scene, "、".join(engine.pipeline_scenes())),
                           ["scene"], scene=scene, scene_matched=False,
                           known_scenes=engine.pipeline_scenes(),
                           fallback_scene="默认", suggested_steps=steps)
        return {"ok": True, "op": "pipeline", "scene": scene, "scene_matched": True,
                "steps": steps}
    if op == "status":
        import importlib.util as _iu
        import os as _os

        def _has(m):
            try:
                return _iu.find_spec(m) is not None
            except Exception:
                return False

        def _svc(host: str, port: int, timeout: float = 0.6) -> str:
            """本机服务的活体探测（只读：只建 TCP 连接，不发请求、不写盘）。"""
            import socket as _s
            try:
                with _s.create_connection((host, port), timeout=timeout):
                    return "up"
            except Exception:  # noqa: BLE001 —— 连不上就是"没起"，不是错误
                return "down"

        return {"ok": True, "readonly": True, "op": "status", "registry_size": len(VOICE_SKILL_REGISTRY),
                "local_backends": {"onnxruntime": _has("onnxruntime"), "torch": _has("torch"),
                                   "dxcam": _has("dxcam"), "sapi": _os.name == "nt"},
                # 2026-10-04 接入：VoiceStudio 本地语音工作台（headless 后端）。
                # 看"服务在不在"与看"包能不能 import"是两把尺 —— 分开报。
                "local_services": {"voicestudio(127.0.0.1:3900)": _svc("127.0.0.1", 3900)},
                "note": ("本机可跑性以能 import 的后端为准；torch 缺失则 2B 级以上本地模型不可跑，"
                         "见 gbt_allinone/docs/语音中枢v2.0-实测与部署.md。"
                         "local_services 是活体探测（只读 TCP 连接）；VoiceStudio 起停/说话/克隆走 "
                         "tools/codex-scripts/voicestudio.py")}
    raise ValueError("未知 op: %s（可用: list / pipeline / status）" % op)


# ==========================================
# 4. 技能调用示例
# ==========================================

if __name__ == "__main__":
    print("=" * 60)
    print("公主土豆的 Voice AI 技能中枢 v2.0 · 启动")
    print("=" * 60)

    engine = VoiceSkillEngine()

    # 1. 列出所有的语音复刻技能
    print("\n[1] 检索『语音复刻』全技能：")
    for s in engine.query(domain=VoiceDomain.CLONE):
        print(f"  - {s.name} ({s.provider}) | 亮点: {', '.join(s.highlights)}")

    # 2. 按关键词检索
    print("\n[2] 检索含『实时』关键词的复刻技能：")
    for s in engine.query(keyword="实时"):
        print(f"  - {s.name} ({s.domain.value}) | 场景: {s.recommended_scene}")

    # 3. 多维度场景 Pipeline 展示
    scenes = ["实时对话", "有声书", "视频配音", "跨语言配音", "歌声转换", "无障碍语音修复"]
    for scene in scenes:
        print(f"\n[3] 场景：『{scene}』端到端技能链：")
        pipeline = engine.build_pipeline(scene)
        for step, tech in pipeline.items():
            print(f"  - {step}: {tech}")
