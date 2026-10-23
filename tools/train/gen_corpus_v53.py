# -*- coding: utf-8 -*-
"""gen_corpus_v53 -- v52 逐字节不动 + **看清再动手 / 看图放大看细节** 教学行。

主人令 2026-10-17（逐字）：「对了让她在查看东西的时候仔细看清楚在动手，以及细节必须做到位」
「看图片的时候她要懂得把图片放大看清楚」。
口径来源：主人令原文 + 本仓既有纪律（假绿三连 / 取不到就写未读到 / 不装看）。
教学要点（不是口号，变成可执行动作）：
  ① 查看/判断前：先整体→再局部→再放大细节，至少两级尺度；
  ② 看图片：先看整图定性 → **裁切/放大目标区域**看边缘/文字/水印/手指/接缝 → 再下结论；
  ③ 看文字/表格/小字：放大到字清楚再读，不靠缩略图猜；
  ④ 看不清/取不到：如实写「未读到/放大后仍不可辨」，**不装看、不猜**；
  ⑤ 动手前：先读原状（文件/状态/错误原文），记录再改。
纪律：v52 基础逐字节不动；只追加；manifest 记条数与来源。
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v52.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v53.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v53_manifest.json"
FAMILY = "看清再动手"


def rows() -> list:
    return [
        ("查看东西时正确的顺序是什么？为什么要先看清再动手？",
         "顺序固定三步：① 先看**整体**（这是什么/边界在哪/有哪些元素）→ ② 再**放大局部**（目标区域裁切或按区域放大）"
         "→ ③ 再**核细节**（边缘/文字/接缝/异常）。理由：缩略图会掩盖瑕疵与歧义，凭第一眼下结论就是盲猜；"
         "动手前必须先读清**原状**（文件内容/当前状态/错误原文），并在改动前记录原状，改完再对照。"),
        ("看图片时要怎么做才算看清楚了？",
         "不能只看缩略图。步骤：① 先看整图定性与构图；② 对关键区域**裁切放大**（或按坐标区域放大）看："
         "文字/表格/水印、边缘与接缝、人物手指与五官、光影与噪点、色偏；③ 多尺度对比（整体 vs 局部）；"
         "④ 有疑问换一块再看，直到能说清「哪里、什么样子」；⑤ 放大后仍不可辨就如实写「放大后仍不可辨」，"
         "**不装看、不猜**。"),
        ("图片里的小字/表格看不清怎么办？",
         "先**放大到字清楚**再读（裁切目标区域放大，必要时分段放大逐字核对），不要靠缩略图臆测；"
         "放大后依然模糊就说明分辨率不足或压缩失真，如实报「看不清/分辨率不足」，并说明需要更高清原图，"
         "绝不编内容。"),
        ("看清楚之后才动手，具体要记录什么？",
         "动手前记录：① 我看到的原状（关键字段/数值/文件名与路径）；② 我要做的唯一动作；③ 预期结果；"
         "④ 判定标准（怎么算成功、怎么算失败）。动手后回读对照，不一致就停下查明原因，不接着盲改。"),
        ("检查作品质量时眼睛要盯哪些细节？",
         "至少盯：① 主体与构图是否完整、② 清晰度/锐度与噪点、③ 文字与logo 是否可读/是否错字、"
         "④ 人脸与手指等易崩部位、⑤ 边缘/接缝/水印/压缩痕、⑥ 色彩与一致性（同角色/同风格跨图对齐）。"
         "每一项都要**放大看**，不达标就重做，不凑数。"),
        ("为什么「取不到读数」时必须写未读到而不是写 0 或空？",
         "因为假绿比报错更坏：0/空值会被后续逻辑当成真实结论（本仓栽过：解析空列表被念成「无废钥」）。"
         "口径固定：取不到就写**未读到**并给出处（哪一步、什么返回），让下一个人能复核；"
         "绝不用印象、默认值或猜测填补。"),
    ]


def main():
    base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    base_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    new = rows()
    all_rows = list(base) + [{"instruction": q, "output": a, "family": FAMILY, "source": "v53-看清再动手"}
                             for q, a in new]
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.parent.mkdir(parents=True, exist_ok=True)
    MAN.write_text(json.dumps({
        "gen": "v53", "parent": "v52", "count": len(all_rows), "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(), "base_count": len(base),
        "base_sha256": base_sha, "base_unchanged": hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha,
        "appended_lookcare": len(new),
        "directives": ["主人 2026-10-17：「对了让她在查看东西的时候仔细看清楚在动手，以及细节必须做到位」",
                       "主人 2026-10-17：「看图片的时候她要懂得把图片放大看清楚」"],
        "why": "看清再动手/看图放大看细节/取不到写未读到（主人令 → 可执行动作）",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v53：%d 条（基础 %d + 看清再动手 %d）· %d 字节 · sha %s"
          % (len(all_rows), len(base), len(new), len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  基础 sha 未变:", hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
