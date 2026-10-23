# gbt-capability: code_art
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""代码画画艺术内核（code_art_kernel）· R-H188 只读骨架。

五源蒸馏：awesome-creative-coding + algorithmic-art + p5.js + tldraw + HashLips
⇒ 一条创作链：**找工具 → 定种子 → 设画布 → 加图层 → 导出**（元数据回流：可复现、可追溯）。

五原语（缺一即开环）：INDEX（索引）· SEED（种子）· CANVAS（画布）· LAYER（图层）· EXPORT（导出）。

四条红线（做成机械闸）：
  ① 无种子不许导出（不可复现的作品等于不存在）；
  ② 图层只追加、不覆盖（要改先回退）；
  ③ 索引只读（不许把索引当成第二份数据源）；
  ④ 批量导出必带元数据（谁生成的、什么参数、什么种子）。

本骨架**内存态**：不画图、不落盘、不出网。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

PRIMITIVES = ("INDEX", "SEED", "CANVAS", "LAYER", "EXPORT")
PRIMITIVE_CN = {"INDEX": "索引", "SEED": "种子", "CANVAS": "画布",
                "LAYER": "图层", "EXPORT": "导出"}
LAYERS_BY_PRIMITIVE = {"INDEX": "表达层", "CANVAS": "表达层",
                       "SEED": "生成层", "LAYER": "生成层", "EXPORT": "交付层"}

RED_LINES = (
    "无种子不许导出——不可复现的作品等于不存在",
    "图层只追加、不覆盖——要改先回退",
    "索引只读——不许把索引当成第二份数据源",
    "批量导出必带元数据——谁生成的、什么参数、什么种子",
)

CANVAS_MODES = ("2d", "webgl", "svg")
STATUSES = ("draft", "rendered", "exported", "rejected")


@dataclass
class CodeArtWork:
    """一次创作的完整记录（五原语各占一格）。"""

    work_id: str
    title: str = ""
    tools_used: List[str] = field(default_factory=list)          # INDEX
    seed: Optional[int] = None                                   # SEED
    canvas_width: int = 1080
    canvas_height: int = 1080
    canvas_mode: str = "2d"                                      # CANVAS
    layers: List[Dict[str, Any]] = field(default_factory=list)   # LAYER
    exports: List[Dict[str, Any]] = field(default_factory=list)  # EXPORT
    status: str = "draft"
    evidence_ref: Optional[str] = None


class CodeArtKernel:
    """内核（只读骨架）：**内存态**，只出结构，不画图、不落盘。"""

    def __init__(self) -> None:
        self.works: Dict[str, CodeArtWork] = {}

    def new_work(self, work_id: str, title: str = "") -> CodeArtWork:
        if not str(work_id or "").strip():
            raise ValueError("work_id 不能为空")
        w = CodeArtWork(work_id=str(work_id).strip(), title=str(title or "").strip())
        self.works[w.work_id] = w
        return w

    def index(self, keyword: str = "") -> dict:
        """INDEX：查工具/库/参考 —— **只读**（骨架期返回结构，不假装有数据）。"""
        return {"ok": True, "readonly": True, "keyword": str(keyword or ""),
                "tools": [], "count": 0,
                "note": "骨架期索引为空：结构在、资源未接入 —— 空就是空"}

    def set_canvas(self, work: CodeArtWork, width: int, height: int, mode: str = "2d") -> dict:
        if str(mode) not in CANVAS_MODES:
            raise ValueError("未知画布模式 %r（可用：%s）" % (mode, "/".join(CANVAS_MODES)))
        work.canvas_width, work.canvas_height, work.canvas_mode = int(width), int(height), str(mode)
        return {"ok": True, "readonly": True,
                "canvas": [work.canvas_width, work.canvas_height, work.canvas_mode]}

    def set_seed(self, work: CodeArtWork, seed: int) -> dict:
        work.seed = int(seed)
        return {"ok": True, "readonly": True, "seed": work.seed,
                "note": "同输入同输出：种子是复现的命根子"}

    def add_layer(self, work: CodeArtWork, layer: Dict[str, Any]) -> dict:
        """LAYER：**只追加、不覆盖**（红线 ②）。"""
        if not isinstance(layer, dict) or not layer:
            raise ValueError("layer 必须是非空对象")
        work.layers.append(dict(layer))
        return {"ok": True, "readonly": True, "depth": len(work.layers), "appended": True}

    def rollback_layer(self, work: CodeArtWork, steps: int = 1) -> dict:
        """LAYER 的可逆面：要改先回退（**不许就地改**）。"""
        n = min(int(steps or 1), len(work.layers))
        dropped = [work.layers.pop() for _ in range(n)]
        return {"ok": True, "readonly": True, "dropped": len(dropped), "depth": len(work.layers)}

    def export(self, work: CodeArtWork, fmt: str = "png", meta: bool = True,
               batch: bool = False) -> dict:
        """EXPORT：无种子不许导出（红线 ①）；批量必带元数据（红线 ④）。"""
        if work.seed is None:
            return {"ok": False, "denied": True, "reason": "seed_missing",
                    "note": "无种子的导出不可复现——拒绝"}
        if batch and not meta:
            return {"ok": False, "denied": True, "reason": "batch_needs_metadata",
                    "note": "批量导出必带元数据：谁生成的、什么参数、什么种子"}
        record = {
            "format": str(fmt or "png"),
            "with_metadata": bool(meta),
            "batch": bool(batch),
            "seed": work.seed,
            "canvas": [work.canvas_width, work.canvas_height, work.canvas_mode],
            "layers_count": len(work.layers),
        }
        work.exports.append(record)
        work.status = "exported"
        return {"ok": True, "readonly": True, **record}

    def status(self) -> dict:
        return {"ok": True, "readonly": True, "works": len(self.works),
                "primitives": [{"key": k, "cn": PRIMITIVE_CN[k], "layer": LAYERS_BY_PRIMITIVE[k]}
                               for k in PRIMITIVES],
                "red_lines": list(RED_LINES),
                "works_detail": [asdict(w) for w in self.works.values()]}


_DEFAULT = CodeArtKernel()


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / index / redlines。不画图、不落盘、不出网。"""
    op = str(op or "status")
    if op == "status":
        return _DEFAULT.status()
    if op == "index":
        return _DEFAULT.index(params.get("keyword", ""))
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES),
                "primitives": list(PRIMITIVES), "canvas_modes": list(CANVAS_MODES)}
    raise ValueError("未知 op %r（可用：status/index/redlines）" % (op,))


HONEST_BOUNDARY = (
    "内核能保证『可复现、可回退、可追元数据』；"
    "但它保证不了『画得好不好看』——好看只有人看了才知道。"
    "这条和情感投射同族：机器保证结构，人保证共鸣。"
)
