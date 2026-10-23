# gbt-capability: diagram_distill
"""蒸馏件：**把抽象概念物化成可动示意图**的取法（概念先行 · 单一数源 · 几何不变量 · 逐关节自检）。

## 这不是外挂 —— 这是「吞天」蒸出来的**我们自己的**能力
吞入件是 wheresryan22/anatomy（MIT · 7551★ · JavaScript · 零依赖，只用 Node 内置模块 ·
「A Claude skill that explains an idea by building it as a real, working object」）。
本位**不是接入端**：不联网、不起 node、不装 `npx skills`；只把它的**取法**提炼成
我们自己的概念图判据。所以它敢零作用域（本文件没有 subprocess / urllib / 写盘）。

## 为什么是「取法」不是「建平行位」（立项理由）
出图的位我们**已有**：`code_art`（代码艺术内核 INDEX/SEED/CANVAS/LAYER/EXPORT）·
`scene_anchor` · `projection_card`，加 design-asset 那一路。照抄建个平行的「anatomy 位」=
撞仓规「**新增即清旧**」的「同功能两份」⇒ 本位只蒸**取法**：它那套「概念→机构→可动→自证」的规矩。

## 蒸馏四条（每条指回原话，见 op=provenance）
1. **概念物化**：原话「invent a physical thing whose working *is* the concept」→ 抽象概念先变成一个
   「它怎么转**就是**这个概念」的物理机构（cache key → 弹子锁；GPU 上下文 → 龙门绘图仪）。
2. **单一数源**：原话「Every number the figure shows comes from the same small model that moves its
   parts」→ 图上显示的每个数，必须来自**同一个**驱动模型的读数，不许各写各的。
3. **几何不变量（有审计）**：原话「An audit proves that no pipe passes through anything, at rest,
   apart and in every frame between」→ 不穿模是**查过的**：静止态、拆解态、以及两者之间的**每一帧**。
4. **逐关节自检**：原话「checks its own work by zooming in on every joint」→ 交付前自己放大挨个关节看。

op=method / source / provenance / where
"""
from __future__ import annotations

import hashlib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CAPSULE = _ROOT / "gbt_allinone" / "store" / "devoured" / "devoured_wheresryan22_anatomy"
_SRC = "https://github.com/wheresryan22/anatomy"

# 四条取法：我们的落点 + 原话（出处可复核，不靠回忆）
_METHOD = (
    {
        "序": "①",
        "取法": "概念物化：先把抽象概念发明成一个**物理机构**",
        "原话": "invent a physical thing whose working *is* the concept",
        "我们的落点": "画图前先答一句：**它怎么转就是这个概念？**（答不出就别画）",
        "我们已有": "code_art（CANVAS/LAYER）· scene_anchor（先锚场景再画）",
    },
    {
        "序": "②",
        "取法": "单一数源：图上每个数来自**同一个**驱动模型",
        "原话": "Every number the figure shows comes from the same small model that moves its parts",
        "我们的落点": "读数与动画**同源**；禁止「画面一套、标注另一套」",
        "我们已有": "门/台账的单真源口径（同族：devour_fusion 的 fused 从盘上算）",
    },
    {
        "序": "③",
        "取法": "几何不变量要有**审计**（不穿模）",
        "原话": "An audit proves that no pipe passes through anything, at rest, apart and in every frame between",
        "我们的落点": "任何\"看起来对\"的几何都要有可复跑判据；关键态与**过渡帧**都查",
        "我们已有": "穿透式交叉扫描的思路（覆盖率 <100% 要如实报）",
    },
    {
        "序": "④",
        "取法": "逐关节自检（交付前放大挨个看）",
        "原话": "checks its own work by zooming in on every joint",
        "我们的落点": "交付前**自己**放大逐处看一遍，不靠\"应该没问题\"",
        "我们已有": "gbt-tentacle 铁律 5/6（每步亲眼验证 · 不确定就对比前后）",
    },
)


def method(**_kw) -> dict:
    """概念物化图的取法四条：我们的落点 + 原话 + 已有承接位。"""
    return {"ok": True, "op": "method", "kind": "diagram_distill",
            "条目": [dict(r) for r in _METHOD],
            "口径": "**取法**不是**建位**：四条都落在已有的承接位/纪律上，"
                    "本位只把 Anatomy 的 craft 规矩写成可复读的判据（不复制它的代码）"}


def source(**_kw) -> dict:
    """吞入件来源：胶囊在不在、多大、逐个 sha256（真读数，不信转述）。"""
    if not _CAPSULE.is_dir():
        return {"ok": False, "op": "source", "error": "胶囊不在盘上：" + str(_CAPSULE)}
    files = []
    for f in sorted(_CAPSULE.rglob("*")):
        if f.is_file():
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            files.append({"name": f.name, "bytes": f.stat().st_size, "sha256": h.hexdigest()[:16]})
    return {"ok": True, "op": "source", "kind": "diagram_distill",
            "repo": "wheresryan22/anatomy", "url": _SRC, "license": "MIT", "stars": 7551,
            "胶囊": str(_CAPSULE.relative_to(_ROOT)).replace("\\", "/"), "文件": files,
            "口径": "只**读**胶囊（不写盘）；哈希现读现算，不是抄来的"}


def provenance(**_kw) -> dict:
    """蒸馏出处：每条落成哪个 op、来自哪句原话；**没蒸的如实标**。"""
    return {"ok": True, "op": "provenance", "kind": "diagram_distill",
            "吞入件": {"repo": "wheresryan22/anatomy", "site": _SRC, "license": "MIT",
                       "stars": 7551, "language": "JavaScript",
                       "胶囊": "gbt_allinone/store/devoured/devoured_wheresryan22_anatomy/"},
            "蒸馏映射": [
                {"原话/出处": "A Claude skill that explains an idea by building it as a real, working object（README 头）",
                 "落成": "本位的立项：只取「怎么把想法做成一个**真会动**的东西」的 craft，不取它的壳"},
                {"原话/出处": "invent a physical thing whose working *is* the concept（README：What it makes 前）",
                 "落成": "op=method ①（概念物化）"},
                {"原话/出处": "Every number the figure shows comes from the same small model that moves its parts",
                 "落成": "op=method ②（单一数源）"},
                {"原话/出处": "An audit proves that no pipe passes through anything, at rest, apart and in every frame between",
                 "落成": "op=method ③（几何不变量要有审计）"},
                {"原话/出处": "checks its own work by zooming in on every joint",
                 "落成": "op=method ④（逐关节自检）"},
                {"原话/出处": "33 figures / examples 画廊 / WebGL shader / 3D mode (beta) / scripts/capture.mjs（README）",
                 "落成": "**未蒸馏（故意）**：那是它的**作品与引擎**，不是取法；我们按需走自己的出图路"},
                {"原话/出处": "npx skills add wheresryan22/anatomy -g -a claude-code（README：Install）",
                 "落成": "**未蒸馏（故意）**：装它 = 改别的 agent 配置，我们不取（接入端那条线不做）"},
            ],
            "边界": "接入端 ≡ 我们**已有**的出图位（`code_art` / `scene_anchor` / `projection_card` + design-asset）；"
                    "本位 ≡ 蒸馏件（概念物化的 craft 判据）",
            "口径": "蒸馏 = 把外面**契合我们**的那部分取法变成我们自己的判据；"
                    "**没蒸出来的如实体现在「未蒸馏」那两行**"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "diagram_distill", "tentacle": "diagram_distill",
            "entry": "run_task('diagram_distill', {'op': …})",
            "ops": ["method", "source", "provenance", "where"],
            "files": {"handler": "gbt_allinone/tools/diagram_distill.py",
                      "胶囊": "gbt_allinone/store/devoured/devoured_wheresryan22_anatomy/"},
            "scopes": "零作用域（只读 + 纯算：无 subprocess / 无 urllib / 无写盘）",
            "contract": [
                {"op": "method", "params": "无", "returns": "概念物化四取法 + 我们的落点 + 已有承接位"},
                {"op": "source", "params": "无", "returns": "吞入件胶囊现读（尺寸 + 逐文件 sha256）"},
                {"op": "provenance", "params": "无", "returns": "每条蒸馏自哪句原话；未蒸的如实标"},
            ]}


_OPS = {"method": method, "source": source, "provenance": provenance, "where": where}
_ALLOWED = {"method": set(), "source": set(), "provenance": set(), "where": set()}


def run_op(op: str = "where", **params) -> dict:
    op = (op or "where").strip().lower()
    fn = _OPS.get(op)
    if fn is None:
        return {"ok": False, "op": op, "fail_closed": True, "error": "未知 op：" + op,
                "ops": sorted(_OPS), "how": "run_task('diagram_distill', {'op': …})"}
    extra = set(params) - _ALLOWED[op]
    if extra:
        return {"ok": False, "op": op, "fail_closed": True,
                "error": "不认的参数：" + str(sorted(extra)), "allowed": sorted(_ALLOWED[op])}
    return fn(**params)
