# gbt-capability: render_evolution
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""视频渲染进化内核（render_evolution）· R-H191 只读骨架。

五原语（从热门项目蒸馏）：确定性（HyperFrames）· 帧编程（Remotion）· 路径追踪（MoonRay）
· 实时PBR（Filament）· 神经渲染（DiffusionRenderer）。

逼真和流畅不是二选一，是一条帕累托前沿：机器负责把前沿画出来，人负责在上面点一个点
—— 机器不许替人点那个点。

六条红线（做成机械闸）：① 无基线不许进化 ② 无种子不许复现 ③ 未测不按绿
④ 机器不替人判逼真/流畅 ⑤ 不许单目标牺牲 ⑥ 每轮可回滚。

本模块只算不渲：不调用任何渲染引擎、不落盘、不出网（盘上本来也没有可调用的渲染管线）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PRIMITIVES = ("确定性", "帧编程", "路径追踪", "实时PBR", "神经渲染")
PRIMITIVE_SOURCE = {"确定性": "HyperFrames", "帧编程": "Remotion",
                    "路径追踪": "MoonRay", "实时PBR": "Filament",
                    "神经渲染": "DiffusionRenderer"}

ON_DISK = {"HyperFrames": "skill+template", "Remotion": "skill+probe(partial)",
           "MoonRay": "none", "Filament": "none", "DiffusionRenderer": "none"}

STATUSES = ("draft", "experiment", "winner", "rejected")

# 帕累托容差：任一维下降超过这个量 ⇒ 判"单目标牺牲"
DIM_TOLERANCE = 0.05

RED_LINES = (
    "无基线不许进化——没有当前最优基因，不许乱改",
    "无种子不许复现——同输入必须同输出",
    "未测不按绿——指标没跑，不许标『已优化』",
    "机器不替人判逼真/流畅——机器只给客观分，主观分必须人给",
    "不许单目标牺牲——不能为了流畅把逼真拉到不可接受（反之亦然）",
    "每轮可回滚——进化失败必须能回退到上一代基因",
)


@dataclass
class RenderGenome:
    """渲染基因：一次渲染管线的完整参数（只读骨架：只描述，不执行）。"""

    genome_id: str
    parent_id: str = ""
    generation: int = 0
    primitives: List[str] = field(default_factory=list)
    seed: Optional[int] = None
    ray_depth: int = 4
    samples: int = 64
    denoise: bool = True
    upscaler: str = "none"
    neural_render_strength: float = 0.0
    target_fps: int = 60
    resolution: str = "1080p"
    bitrate: str = "8M"
    frame_interpolation: bool = False
    realism_score: Optional[float] = None
    smoothness_score: Optional[float] = None
    human_realism: Optional[float] = None
    human_smoothness: Optional[float] = None
    status: str = "draft"


@dataclass
class RenderExperiment:
    genome_id: str
    baseline_id: str
    realism_metrics: Dict[str, float] = field(default_factory=dict)
    smoothness_metrics: Dict[str, float] = field(default_factory=dict)
    human_verdict: Optional[str] = None
    evidence_ref: Optional[str] = None


class RenderEvolutionKernel:
    """进化内核（只读骨架）：注册基线 → 提基因 → 记实验 → 择优/回滚。"""

    def __init__(self) -> None:
        self.genomes: Dict[str, RenderGenome] = {}
        self.experiments: List[RenderExperiment] = []
        self.history: List[dict] = []

    def register_baseline(self, genome: RenderGenome) -> dict:
        if genome.seed is None:
            return {"ok": False, "denied": True, "rule": "seed_missing",
                    "note": "基线也必须带种子：无种子不许复现（红线 ②）"}
        genome.generation = 0
        self.genomes[genome.genome_id] = genome
        self.history.append({"event": "baseline", "genome_id": genome.genome_id})
        return {"ok": True, "readonly": True, "genome_id": genome.genome_id,
                "seed": genome.seed}

    def propose(self, base_id: str, mutation: Dict[str, Any]) -> dict:
        base = self.genomes.get(base_id)
        if base is None:
            return {"ok": False, "denied": True, "rule": "no_baseline",
                    "note": "无基线不许进化——先把当前最优基因登记成基线"}
        extra = {k: v for k, v in (mutation or {}).items()
                 if k in RenderGenome.__dataclass_fields__ and k not in ("genome_id", "parent_id")}
        gid = "%s-mut-%d" % (base_id, len(self.genomes))
        child = RenderGenome(genome_id=gid, parent_id=base_id,
                             generation=base.generation + 1,
                             primitives=list(base.primitives),
                             seed=base.seed, status="experiment")
        for k, v in extra.items():
            setattr(child, k, v)
        self.genomes[gid] = child
        self.history.append({"event": "propose", "genome_id": gid, "parent": base_id})
        return {"ok": True, "readonly": True, "genome_id": gid, "parent": base_id,
                "generation": child.generation, "seed": child.seed}

    def record_experiment(self, exp: RenderExperiment) -> dict:
        g = self.genomes.get(exp.genome_id)
        if g is None:
            return {"ok": False, "denied": True, "rule": "genome_not_found"}
        if g.seed is None:
            return {"ok": False, "denied": True, "rule": "seed_missing",
                    "note": "无种子不许复现：实验不可复现就等于没做"}
        self.experiments.append(exp)
        flat_r = exp.realism_metrics or {}
        flat_s = exp.smoothness_metrics or {}
        if flat_r:
            g.realism_score = sum(flat_r.values()) / len(flat_r)
        if flat_s:
            g.smoothness_score = sum(flat_s.values()) / len(flat_s)
        self.history.append({"event": "experiment", "genome_id": exp.genome_id,
                             "baseline": exp.baseline_id})
        return {"ok": True, "readonly": True, "genome_id": exp.genome_id,
                "realism_score": g.realism_score, "smoothness_score": g.smoothness_score,
                "experiments": len(self.experiments)}

    def promote(self, genome_id: str) -> dict:
        g = self.genomes.get(genome_id)
        if g is None:
            return {"ok": False, "denied": True, "rule": "genome_not_found"}
        if g.realism_score is None or g.smoothness_score is None:
            return {"ok": False, "denied": True, "rule": "metrics_missing",
                    "note": "未测不按绿：客观指标没跑，不许标『已优化』"}
        if g.human_realism is None or g.human_smoothness is None:
            return {"ok": False, "denied": True, "rule": "human_verdict_missing",
                    "note": "机器不替人判逼真/流畅：主观分必须人给"}
        parent = self.genomes.get(g.parent_id)
        if parent is not None:
            sacrifice = []
            if parent.realism_score is not None and \
                    g.realism_score < parent.realism_score - DIM_TOLERANCE:
                sacrifice.append("逼真")
            if parent.smoothness_score is not None and \
                    g.smoothness_score < parent.smoothness_score - DIM_TOLERANCE:
                sacrifice.append("流畅")
            if sacrifice:
                return {"ok": False, "denied": True, "rule": "single_objective_sacrifice",
                        "note": "不许单目标牺牲：%s 比上一代掉了超过容差 %.2f"
                                % ("/".join(sacrifice), DIM_TOLERANCE)}
        g.status = "winner"
        self.history.append({"event": "promote", "genome_id": genome_id})
        return {"ok": True, "readonly": True, "genome_id": genome_id, "status": "winner",
                "realism_score": g.realism_score, "smoothness_score": g.smoothness_score}

    def rollback(self, genome_id: str) -> dict:
        g = self.genomes.get(genome_id)
        if g is None:
            return {"ok": False, "denied": True, "rule": "not_found"}
        g.status = "rejected"
        self.history.append({"event": "rollback", "genome_id": genome_id})
        return {"ok": True, "readonly": True, "rolled_back": genome_id,
                "status": "rejected", "parent_id": g.parent_id or None}

    def pareto_front(self) -> dict:
        pts = [g for g in self.genomes.values()
               if g.realism_score is not None and g.smoothness_score is not None]
        front = []
        for g in pts:
            dominated = any(o is not g and o.realism_score >= g.realism_score
                            and o.smoothness_score >= g.smoothness_score
                            and (o.realism_score > g.realism_score
                                 or o.smoothness_score > g.smoothness_score)
                            for o in pts)
            if not dominated:
                front.append(g)
        return {"ok": True, "readonly": True, "points": len(pts),
                "front": [{"genome_id": g.genome_id, "realism": g.realism_score,
                           "smoothness": g.smoothness_score,
                           "human": [g.human_realism, g.human_smoothness]} for g in front],
                "note": "机器只把前沿画出来；在上面点哪一个点由人决定"}

    def status(self) -> dict:
        winners = [g.genome_id for g in self.genomes.values() if g.status == "winner"]
        return {"ok": True, "readonly": True, "genomes": len(self.genomes),
                "experiments": len(self.experiments), "winners": winners,
                "primitives": [{"key": k, "source": PRIMITIVE_SOURCE[k],
                                "on_disk": ON_DISK[PRIMITIVE_SOURCE[k]]} for k in PRIMITIVES],
                "red_lines": list(RED_LINES), "dim_tolerance": DIM_TOLERANCE,
                "honest_boundary": HONEST_BOUNDARY}


HONEST_BOUNDARY = (
    "内核能保证『可复现、可比较、可回滚、可留痕』；"
    "它保证不了『人看了觉得逼真、觉得流畅』——那只能由人给分。"
)

_DEFAULT = RenderEvolutionKernel()


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / primitives / redlines。不渲、不落盘、不出网。"""
    op = str(op or "status")
    if op == "status":
        return _DEFAULT.status()
    if op == "primitives":
        return {"ok": True, "readonly": True,
                "primitives": [{"key": k, "source": PRIMITIVE_SOURCE[k],
                                "on_disk": ON_DISK[PRIMITIVE_SOURCE[k]]} for k in PRIMITIVES],
                "note": "盘上只有 HyperFrames / Remotion 有技能+模板影子；其余三者盘上没有 ⇒ 一律待接"}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES),
                "dim_tolerance": DIM_TOLERANCE}
    raise ValueError("未知 op %r（可用：status/primitives/redlines）" % (op,))
