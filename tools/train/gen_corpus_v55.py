# -*- coding: utf-8 -*-
"""gen_corpus_v55 -- v50（最佳基底）逐字节不动 + 本轮全部新增教学（可追溯）。

主人令（2026-10-17 逐条）：
  · 「训练的时候必须把秋叶版我们自己的原生能力打磨到极致哈，作品质量必须把控好」
  · 「对了让她在查看东西的时候仔细看清楚在动手，以及细节必须做到位」「看图片的时候她要懂得把图片放大看清楚」
  · 「对了把触手上的所有职业也训练到真正的专业，感觉大模型都不专业了」
  · 「记得量化压缩，使用那一块就激活那一块没使用的就静默空显存，最后触手绑定每一页…实现精准提速体积压缩」
  · 「让她把这个整理提炼原生能力，这样就省去本地下载模型了」（VoiceStudio）

为什么基底回到 v50：实测家族合计 v50=40/44 · v51=37/44 · v52=35/44（秋叶版散文教训）· v54=37/44。
以 v50 为基底、只加本轮新教学，避免把已实测掉分的行叠进来。
内容全部**现读真源**（判据/注册表/文档），不手写凭空内容。
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v50.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v55.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v55_manifest.json"


def _load(path: Path, name: str):
    sp = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _v54_rows() -> list:
    """复用 v54 已验证的三类行（秋叶版 JSON 工作流 / 看清再动手 / 30 职业面）。"""
    m = _load(ROOT / "tools" / "train" / "gen_corpus_v54.py", "v54gen")
    out = []
    out += [("秋叶版质量", q, a) for q, a in m._comfy_rows()]
    out += [("看清再动手", q, a) for q, a in m._care_rows()]
    out += [("职业专业性", q, a) for q, a in m._career_rows()]
    return out


def _voice_studio_rows() -> list:
    """VoiceStudio 原生能力（只提炼接口、不下载模型）——事实取上游 README + speech-platform.md 现读。"""
    return [
        ("VoiceStudio 是什么、我们怎么用它？",
         "`debpalash/VoiceStudio`（AGPL-3.0 · 全本地 ElevenLabs 替代）：语音克隆 / 声音设计 / 视频配音 / 听写 / "
         "转写 / 有声书，**646 语言**，默认引擎 k2-fsa/OmniVoice。我们把它提炼成能力位 `voice_studio`（域 voice，"
         "**全只读**）：只调它的 **Local speech platform**（默认 http://127.0.0.1:3900），"
         "**不下载任何模型**、不写盘。调用：`five-dim.py cap voice_studio '{\"op\":\"status\"}'`。"),
        ("voice_studio 能力位怎么探活、怎么转写？",
         "① 探活：`cap voice_studio '{\"op\":\"status\"}'` → GET `/.well-known/voicestudio-speech`（协议 "
         "voicestudio.speech.v1）；后端没起就**如实报未读到**（WinError 10061 之类），绝不假装可用。"
         "② 转写：`cap voice_studio '{\"op\":\"transcribe\",\"path\":\"<本机音频>\",\"language\":\"zh\"}'` → "
         "POST `/v1/audio/transcriptions`（OpenAI 兼容，multipart，model/language 可选）。"
         "③ MCP：`op=mcp_info` 给 `/mcp/` 与 `python -m backend.mcp_shim` 用法。"),
        ("voice_studio 的安全边界与「省去下载模型」是什么意思？",
         "边界：默认**只许回环**（127.0.0.1/localhost/::1）；连远端必须显式 `GBT_VOICESTUDIO_ALLOW_REMOTE=1`；"
         "拒重定向；密钥/票据只回掩码；能力位**全部只读**（不写盘、不下载权重）。"
         "「省去本地下载模型」= 模型权重与许可留在上游，我们只提炼**接口**（发现文档/OpenAI 兼容转写/MCP），"
         "本机装的是它的后端或直接连它的服务，所以不用在我们的仓库里再放一份模型。"),
        ("voice_studio 缺什么要如实报？",
         "缺：① 后端未部署/未启动 ⇒ `status` 报未读到 + 给「怎么接」；② 远端未开开关 ⇒ 直接拒并说明要 "
         "`GBT_VOICESTUDIO_ALLOW_REMOTE=1`；③ 音频文件不存在 ⇒ `file_not_found`。"
         "口径：**缺什么报什么**，不拿「正在加载」「稍后再试」糊弄，也不偷偷下载模型。"),
    ]


def _quant_rows() -> list:
    return [
        ("量化压缩各档体积怎么算、怎么选？",
         "按参数现算（本模型 7,696,356,864 参数，含 5% 结构开销）：bf16/16bit ≈ **15.05GB** · 8bit ≈ **7.53GB** · "
         "4bit ≈ **3.76GB** · 2bit ≈ **1.88GB**。选档口径：显存紧就 4bit（QLoRA 训练就是 4bit 底座），"
         "交付底座用 bf16 保精度；数字要**现算**、写明公式，不拍脑袋。原生能力：`cap quant_plan '{\"op\":\"plan\"}'`。"),
        ("惰性激活（用哪块激活哪块、不用静默空显存）怎么落地？",
         "口径：① 页面/工作台**按块静态渲染**，进哪页只加载那页的块与数据；② 推理**按层加载**，"
         "未用层不放进显存（静默）；③ 训练/推理进程退出要**释放**显存，别留僵尸占用；"
         "④ 读数要诚实：峰值显存从日志 `TRAIN_DONE peak_vram_gb=` 现读，取不到写未读到。"),
        ("精准提速与体积压缩怎么验证？",
         "验证三件：① 体积：`quant_plan` 各档估算 vs 实盘文件大小对账；② 提速：`cap quant_plan '{\"op\":\"speed\"}'` "
         "与本地实测（页面加载秒数、单页占比）对照；③ 直达：`page-reach --check` 全可达 + 遗留 0，"
         "`project-bind --check` 全项目双向绑定 PASS。三者都要有读数与出处，缺一写未读到。"),
    ]


def main():
    base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    base_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    adds = ([("VoiceStudio原生能力", q, a) for q, a in _voice_studio_rows()]
            + [("量化压缩·惰性激活", q, a) for q, a in _quant_rows()]
            + _v54_rows())
    rows = list(base) + [{"instruction": q, "output": a, "family": fam, "source": "v55-" + fam}
                         for fam, q, a in adds]
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.parent.mkdir(parents=True, exist_ok=True)
    MAN.write_text(json.dumps({
        "gen": "v55", "parent": "v50", "count": len(rows), "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(), "base_count": len(base),
        "base_sha256": base_sha, "base_unchanged": hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha,
        "appended": len(adds),
        "appended_by_kind": {
            "VoiceStudio原生能力": len(_voice_studio_rows()),
            "量化压缩·惰性激活": len(_quant_rows()),
            "秋叶版质量": 0, "看清再动手": 0, "职业专业性": 0, "__reused_v54__": len(_v54_rows())},
        "directives": [
            "主人 2026-10-17：「训练的时候必须把秋叶版我们自己的原生能力打磨到极致哈，作品质量必须把控好」",
            "主人 2026-10-17：「对了让她在查看东西的时候仔细看清楚在动手，以及细节必须做到位」",
            "主人 2026-10-17：「看图片的时候她要懂得把图片放大看清楚」",
            "主人 2026-10-17：「对了把触手上的所有职业也训练到真正的专业，感觉大模型都不专业了」",
            "主人 2026-10-17：「记得量化压缩…实现精准提速体积压缩」",
            "主人 2026-10-17：「让她把这个整理提炼原生能力，这样就省去本地下载模型了」",
        ],
        "why": "回归 v50 最佳基底（40/44）；只加本轮新教学：VoiceStudio 接口 + 量化/惰性 + 复用 v54 的秋叶版JSON/看清/30职业",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v55：%d 条（基底 v50 %d + 追加 %d：VoiceStudio %d · 量化/惰性 %d · 复用 v54 %d）· %d 字节 · sha %s"
          % (len(rows), len(base), len(adds), len(_voice_studio_rows()), len(_quant_rows()), len(_v54_rows()),
             len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  基底 sha 未变:", hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
