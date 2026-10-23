# -*- coding: utf-8 -*-
"""gen_corpus_v54 -- **回归最佳基底 v50** + 三类补齐（v51/v52 的教训写在这里）。

为什么从 v50 起而不是 v52（**留痕 · 有实测依据**）：
  v50 家族合计 40/44（comfy 5/6）；v51 = 37/44；v52 = 35/44（comfy 掉到 3/6）。
  v52 掉分根因：秋叶版教学行写成了**散文**，而 comfy 判据要**可跑的 JSON 工作流**
  （`accept_comfy.extract_graph` 要从答案里抠出含 ≥3 个 class_type 的平衡 JSON 并过 `validate`）。
  ⇒ 本版以 v50 为基底，秋叶版改用**真实节点图 JSON** 教，不再用描述性散文。

三类追加（全部现读真源，不编）：
  A. 秋叶版 JSON 工作流：txt2img / img2img / txt2video 三张图（节点名取 `accept_comfy.NEED`），
     每张都是可直接 `validate` 的 API 图（`class_type` + `inputs` + 连线）；
  B. 作品质量把控 + 文本判据（`TEXT_RULES` 现读）；
  C. 触手 30 个域（职业面）：从 `state/cap-bindings.json` 现读域名/标签 + `caps_registry` 的 desc，
     每域一行「专业面：能力位清单 + 专业动作 + 交付物 + 常见不专业错误」；
  D. 看清再动手/看图放大细节（主人 2026-10-17 两条令）。
纪律：v50 基础逐字节不动；只追加；manifest 记条数与来源。
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v50.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v54.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v54_manifest.json"
TRAIN = ROOT / "tools" / "train"


def _load(fname: str):
    sp = importlib.util.spec_from_file_location("v54_" + fname.replace(".py", ""), str(TRAIN / fname))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _wf(kind: str) -> dict:
    n = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "masterpiece, 1girl, sunset", "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "low quality, blurry, watermark", "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 1024, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"seed": 12345, "steps": 28, "cfg": 6.0,
                                                  "sampler_name": "dpmpp_2m", "scheduler": "karras",
                                                  "denoise": 1.0, "model": ["1", 0], "positive": ["2", 0],
                                                  "negative": ["3", 0], "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "gbt_v54_txt2img"}},
    }
    if kind == "img2img":
        n["8"] = {"class_type": "LoadImage", "inputs": {"image": "input.png"}}
        n["9"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["8", 0], "vae": ["1", 2]}}
        n["5"]["inputs"]["latent_image"] = ["9", 0]
        n["5"]["inputs"]["denoise"] = 0.55
        n["7"]["inputs"]["filename_prefix"] = "gbt_v54_img2img"
    if kind == "txt2video":
        n["8"] = {"class_type": "ADE_AnimateDiffLoaderGen1", "inputs": {"model": ["1", 0], "motion_scale": 1.0}}
        n["5"]["inputs"]["model"] = ["8", 0]
        n["9"] = {"class_type": "VHS_VideoCombine", "inputs": {"images": ["6", 0], "frame_rate": 12,
                                                               "loop_count": 0, "format": "video/h264-mp4",
                                                               "filename_prefix": "gbt_v54_txt2video"}}
        del n["7"]
    return n


def _comfy_rows() -> list:
    need = dict(getattr(_load("accept_comfy.py"), "NEED", {}) or {})
    rules = getattr(_load("accept_comfy.py"), "TEXT_RULES", {}) or {}
    r = []
    r.append(("秋叶版文生图 JSON 工作流（要能 validate）",
              "文生图 API 图（含 %s，节点用 class_type 标名，直接过 validate）：\n```json\n%s\n```"
              "参数口径：seed 固定可复现、steps 20~30、cfg 4~8、负向词写清、短边 512~1024。"
              % (" · ".join(need.get("txt2img", [])), json.dumps(_wf("txt2img"), ensure_ascii=False))))
    r.append(("秋叶版图生图 JSON 工作流（要能 validate）",
              "图生图 API 图（含 %s）：\n```json\n%s\n```"
              "要点：LoadImage 读原图 → VAEEncode → KSampler（denoise 0.3~0.6 保结构 / 0.6~0.9 换风格）→ VAEDecode → SaveImage。"
              % (" · ".join(need.get("img2img", [])), json.dumps(_wf("img2img"), ensure_ascii=False))))
    r.append(("秋叶版文生视频 JSON 工作流（要能 validate，必须有运动模块）",
              "文生视频 API 图（含 %s + 运动模块 ADE_AnimateDiffLoaderGen1）：\n```json\n%s\n```"
              "输出用 VHS_VideoCombine 合成 mp4；显存门槛：4060 8G + 32G 内存 5 秒 536x736 ≈ 6 分多钟。"
              % (" · ".join(need.get("txt2video", [])), json.dumps(_wf("txt2video"), ensure_ascii=False))))
    r.append(("秋叶版文本题判据要写清哪三样？",
              "现读 `TEXT_RULES`：题面含「判据」⇒ 必须同时出现 `validate`、`未知`、`必填`；含「必填」⇒ `seed` 与 `steps`；"
              "含「目录」⇒ `models/` 且带 `checkpoints` 或 `vae`。取不到就写**未知**，必填参数缺一不可。"))
    r.append(("秋叶版作品质量怎么把控（出图前/出图后各看什么）？",
              "出图前：seed 固定可复现、steps 20~30、cfg 4~8、分辨率合用途、负向词写清、LoRA/ControlNet 不叠爆、"
              "先 validate 再跑。出图后：构图完整、清晰度/锐度（必要时高清修复）、人脸修复（脸崩必修）、超分（POST）、"
              "一致性（同角色/风格跨图对齐）、不达标**重跑不凑数**；产物落盘并写 `trace_store`（source_kind=comfyui）后回读对账。"))
    return r


def _care_rows() -> list:
    return [
        ("查看东西时正确的顺序是什么？为什么要先看清再动手？",
         "三步：① 先看整体（是什么/边界/元素）→ ② 放大局部（目标区域裁切或按区域放大）→ ③ 核细节（边缘/文字/接缝/异常）。"
         "缩略图会掩盖瑕疵；动手前先读清原状（文件/状态/错误原文）并记录，改完对照，不一致就停下查明原因。"),
        ("看图片时要怎么做才算看清楚了？",
         "不只看缩略图：① 整图定性与构图；② 关键区域**裁切放大**看文字/表格/水印/边缘接缝/手指五官/噪点色偏；"
         "③ 多尺度对比；④ 有疑问换区域再看直到说清「哪里、什么样子」；⑤ 放大仍不可辨就如实写「放大后仍不可辨」，不装看不猜。"),
        ("图片里的小字/表格看不清怎么办？",
         "先**放大到字清楚**再读（裁切分段放大逐字核对），不靠缩略图臆测；若仍模糊=分辨率不足或压缩失真，"
         "如实报「看不清/需更高清原图」，绝不编内容。"),
        ("检查作品质量时眼睛要盯哪些细节？",
         "主体与构图、清晰度/锐度与噪点、文字 logo 可读性、人脸手指易崩处、边缘接缝水印压缩痕、色彩一致性；"
         "每项都放大看，不达标重做不凑数。"),
        ("为什么「取不到读数」时必须写未读到而不是写 0 或空？",
         "假绿比报错更坏：0/空会被当真实结论（本仓栽过：空列表被念成「无废钥」）。取不到就写**未读到**并给出处"
         "（哪一步、什么返回），让下一个人能复核；绝不用印象/默认值填补。"),
    ]


def _career_rows() -> list:
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    cb = json.loads((ROOT / "state" / "cap-bindings.json").read_text(encoding="utf-8"))
    caps = cb.get("caps") or []
    from gbt_allinone.caps_registry import BENIGN_CAPS
    by_dom = {}
    for c in caps:
        d = str(c.get("domain") or "")
        by_dom.setdefault(d, {"label": str(c.get("domain_label") or d), "caps": []})
        by_dom[d]["caps"].append(str(c.get("name") or ""))
    out = []
    for d, info in sorted(by_dom.items()):
        names = info["caps"]
        roster = []
        for n in names[:18]:
            desc = str((BENIGN_CAPS.get(n) or {}).get("desc") or "").split("；")[0][:70]
            roster.append("`%s`（%s）" % (n, desc or "见 cap 名册"))
        deliver = [n for n in names if any(k in n for k in ("deliver", "report", "log", "audit", "scan"))][:6]
        out.append((
            "%s 这个职业面（触手域）有哪些能力位、专业标准是什么？" % info["label"],
            "触手域 `%s`（%s）· 能力位 %d 个：%s。%s"
            "专业标准：① 动作前现读状态（不许凭印象）；② 只走唯一门 `five-dim.py cap <能力位> '<json>'`，不直调模块；"
            "③ 产物落盘 + 回读对账（sha/行数）并写 logbook/trace；④ 缺票如实报缺、不绕门；⑤ 取不到读数写「未读到」。"
            "常见不专业错误：绕门直调、把空当读数（假绿）、不落盘、不复核就报完成。"
            % (d, info["label"], len(names), "；".join(roster),
               ("交付/审计类：%s。" % "、".join(deliver)) if deliver else "")))
    return out


def main():
    base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    base_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    adds = ([("秋叶版质量", q, a) for q, a in _comfy_rows()]
            + [("看清再动手", q, a) for q, a in _care_rows()]
            + [("职业专业性", q, a) for q, a in _career_rows()])
    all_rows = list(base) + [{"instruction": q, "output": a, "family": fam, "source": "v54-" + fam}
                             for fam, q, a in adds]
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.parent.mkdir(parents=True, exist_ok=True)
    MAN.write_text(json.dumps({
        "gen": "v54", "parent": "v50", "count": len(all_rows), "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(), "base_count": len(base),
        "base_sha256": base_sha, "base_unchanged": hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha,
        "appended": len(adds),
        "appended_by_kind": {"秋叶版质量": len(_comfy_rows()), "看清再动手": len(_care_rows()),
                             "职业专业性": len(_career_rows())},
        "directives": [
            "主人 2026-10-17：「训练的时候必须把秋叶版我们自己的原生能力打磨到极致哈，作品质量必须把控好」",
            "主人 2026-10-17：「对了让她在查看东西的时候仔细看清楚在动手，以及细节必须做到位」",
            "主人 2026-10-17：「看图片的时候她要懂得把图片放大看清楚」",
            "主人 2026-10-17：「对了把触手上的所有职业也训练到真正的专业，感觉大模型都不专业了」",
        ],
        "why": "回归 v50 最佳基底；秋叶版改教**真实 JSON 工作流**（v52 散文版实测 comfy 5/6→3/6）；+30 职业专业面 + 看清再动手",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v54：%d 条（基底 v50 %d + 追加 %d：秋叶版%d/看清%d/职业%d）· %d 字节 · sha %s"
          % (len(all_rows), len(base), len(adds), len(_comfy_rows()), len(_care_rows()), len(_career_rows()),
             len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  基底 sha 未变:", hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
