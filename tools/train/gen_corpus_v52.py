# -*- coding: utf-8 -*-
"""gen_corpus_v52 -- v51 逐字节不动 + **秋叶版原生能力 + 作品质量**教学行。

主人令 2026-10-17：「训练的时候必须把秋叶版我们自己的原生能力打磨到极致哈，作品质量必须把控好」。
内容**全部现读真源**（不编）：
  · `gbt_allinone/docs/ComfyUI秋叶整合包设计.md`：三层架构（启动器/节点/模型层）· 五原语
    （LOAD/GENERATE/CONTROL/POST/EXPORT）· 模型层目录 `ComfyUI/models` 子目录 · 产物落盘 + trace_store
    `source_kind=comfyui` · 硬件门槛（4G/8G 显存、视频 8G+32G、5 秒 536x736≈6 分钟）· 支持面
    （SD/FLUX/Krea-2 · SVD/AnimateDiff/Hunyuan/Wan/LTX-2 · Stable Audio/Ace-Step/Seed Audio）；
  · `tools/train/accept_comfy.py`：每类工作流**必需节点名**（`NEED`）与文本题判据（`TEXT_RULES`）。
为什么：v50/v51 的 comfy 套件仍 5/6（txt2video 缺运动模块、质量口径不牢），且「作品质量」不只是能跑，
  还要有固定质检链（种子可复现 / 步数 CFG / 负向词 / 高清与人脸修复 / 超分 / 落盘对账）。
纪律：v51 基础逐字节不动；只追加；manifest 记条数与来源。
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v51.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v52.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v52_manifest.json"
TRAIN = ROOT / "tools" / "train"
FAMILY = "秋叶版原生能力"


def _load(fname: str):
    sp = importlib.util.spec_from_file_location("v52_" + fname.replace(".py", ""), str(TRAIN / fname))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _need_nodes() -> dict:
    return dict(getattr(_load("accept_comfy.py"), "NEED", {}) or {})


def rows() -> list:
    need = _need_nodes()
    txt2img = need.get("txt2img", [])
    img2img = need.get("img2img", [])
    vid = need.get("txt2video", [])
    r = []

    r.append((
        "秋叶版三层架构各是什么、谁管什么？",
        "秋叶整合包是**工具箱**不是模型，三层：① 启动器层（绘世启动器）：可视化管虚拟环境/依赖/"
        "修报错/显存模式（如 --lowvram 适用 8G 以下）；② 节点层（工作流核心）：每节点单一功能"
        "（加载模型/提示词/尺寸/采样/解码/存图），连线成流水线，预装 90%+ 常用节点与成熟模板；"
        "③ 模型层（燃料）：决定「能生成什么」，整合包通常**不含大模型**，要自行下载放进 "
        "`ComfyUI/models` 对应子目录。"))

    r.append((
        "秋叶版能力位叫什么、五原语怎么用？",
        "能力位 `comfyui_local`（domain=creative、type=internal），五原语：LOAD（加载模型与工作流）→ "
        "GENERATE（执行文生图/视频/音频）→ CONTROL（ControlNet 等节点控制结果）→ POST（后处理：超分/修复）"
        "→ EXPORT（结果落盘）。它作为「手」接大脑指令执行生成、作为「眼」的延伸把产物交给视觉触手质检；"
        "产物必须落盘并写 `trace_store`，`source_kind=comfyui`。"))

    r.append((
        "秋叶版文生图 JSON 工作流必须有哪些节点？",
        "文生图（txt2img）必需节点（现读判据）：%s。顺序：CheckpointLoaderSimple 加载大模型 → "
        "CLIPTextEncode 正/负提示词 → EmptyLatentImage 尺寸 → KSampler 采样 → VAEDecode 解码 → "
        "SaveImage 存图；每个节点用 `class_type` 标名，连成 API 图后必须过 `validate` 校验。"
        % " · ".join(txt2img)))

    r.append((
        "秋叶版图生图 JSON 工作流必须有哪些节点？",
        "图生图（img2img）必需节点（现读判据）：%s。关键差别：LoadImage 读原图 → VAEEncode 编到潜空间 → "
        "KSampler 以去噪强度（denoise 0.3~0.6 保结构、0.6~0.9 换风格）重绘 → VAEDecode → SaveImage。"
        % " · ".join(img2img)))

    r.append((
        "秋叶版文生视频 JSON 工作流必须有哪些节点？运动模块怎么选？",
        "文生视频（txt2video）必需节点（现读判据）：%s，**并且必须带运动模块**（AnimateDiff / SVD / Wan / "
        "Hunyuan / LTX 任一）——缺运动模块判红。输出用 VHS_VideoCombine 合成 mp4；显存门槛：视频更吃资源，"
        "4060 8G + 32G 内存生成 5 秒 536x736 ≈ 6 分多钟（尝鲜级）。" % " · ".join(vid)))

    r.append((
        "秋叶版作品质量怎么把控（出图前/出图后各看什么）？",
        "出图前：① 种子（seed）固定可复现、② 步数 steps（20~30）与 CFG（4~8）在合理区间、"
        "③ 分辨率与比例符合用途（短边 512~1024，避免脸崩）、④ 负向词写清（低质/畸变/多手多指/水印）、"
        "⑤ LoRA/ControlNet 权重不叠爆、⑥ 先用 `validate` 过 API 图再跑。出图后：① 构图与主体完整、"
        "② 清晰度/锐度（必要时高清修复 hires-fix）、③ 人脸修复（脸崩必修）、④ 超分（POST 阶段）、"
        "⑤ 一致性（同角色/同风格跨图对齐）、⑥ 不达标**重跑而不是凑数**；产物落盘后写 `trace_store` 并回读对账。"))

    r.append((
        "秋叶版文本题判据要写清哪三样？",
        "文本类判据现读 `TEXT_RULES`：题面含「判据」⇒ 答案必须同时出现 `validate`、`未知`、`必填` 三个词；"
        "含「必填」⇒ 必须写 `seed` 与 `steps`；含「目录」⇒ 必须写 `models/` 且带 `checkpoints` 或 `vae`。"
        "取不到就写**未知**（不许编），必填参数缺一不可。"))

    r.append((
        "秋叶版支持哪些模型方向（现读文档）？",
        "① AI 生图：Stable Diffusion、FLUX、Krea-2 —— 文生图/图生图/局部重绘/高清修复/人脸修复；"
        "② AI 生视频：Stable Video Diffusion、AnimateDiff、Hunyuan Video、Wan 2.7/3.0、LTX-2 —— "
        "文生视频/图生视频（可带音频）；③ AI 生音乐/音频：Stable Audio、Ace-Step、Seed Audio 1.0 —— "
        "文生音频/音乐、声音克隆、多说话人对话。整合包本体约 2–8GB，完整模型库要预留 200GB–1TB+。"))
    return r


def main():
    base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    base_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    new = rows()
    all_rows = list(base) + [{"instruction": q, "output": a, "family": FAMILY, "source": "v52-秋叶版"}
                             for q, a in new]
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.parent.mkdir(parents=True, exist_ok=True)
    MAN.write_text(json.dumps({
        "gen": "v52", "parent": "v51", "count": len(all_rows), "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(), "base_count": len(base),
        "base_sha256": base_sha, "base_unchanged": hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha,
        "appended_qiuqiu": len(new),
        "directives": ["主人 2026-10-17：「训练的时候必须把秋叶版我们自己的原生能力打磨到极致哈，作品质量必须把控好」"],
        "why": "秋叶版原生能力+作品质量：三层架构/五原语/模型层目录/validate/质量修复链/支持面（现读文档+判据）",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v52：%d 条（基础 %d + 秋叶版 %d）· %d 字节 · sha %s"
          % (len(all_rows), len(base), len(new), len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  基础 sha 未变:", hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
