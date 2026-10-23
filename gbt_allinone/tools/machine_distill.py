# gbt-capability: machine_distill
"""蒸馏件：**求解器驱动的可视化**取法（每帧真解 · 确定性时钟 · 坏也是算的 · 真量纲真材质）。

## 这不是外挂 —— 这是「吞天」蒸出来的**我们自己的**能力
吞入件是 AirsupHQ/machine-skill（MIT · 91★ · JavaScript · three.js 0.170 · 无构建步 ·
「Describe any machine in one line. Claude builds the real thing, running on real physics.」）。
本位**不是接入端**：不联网、不起 node、不装 `npx skills`；只把它的**取法**提炼成我们自己的判据。
所以它敢零作用域（本文件没有 subprocess / urllib / 写盘）。

## 边界（和隔壁 `diagram_distill` 分清楚，别当同一件）
- `diagram_distill`（蒸自 Anatomy）管 **概念怎么变成一个会动的机构**（概念物化 · 单一数源 ·
  几何不变量审计 · 逐关节自检）。
- 本位（蒸自 Machine）管 **机构上的每一个数怎么真解出来**（求解器 · 确定性 · 可算的破坏 · 真量纲）。
  两者互补：一个管「画什么」，一个管「画出来的数凭什么可信」。
  出图的位我们**已有**（`code_art` / `scene_anchor` / `projection_card`）⇒ **不建平行位**。

## 蒸馏四条（每条指回原话，见 op=provenance）
1. **每帧真解，不查表**：原话「Every number on screen is computed」「a small solver per machine
   (Brayton cycle, rocket chamber and nozzle, …) drives every motion and every number」→
   画面上的数必须是**当帧解出来的**，并且能给人看方程（`How it is computed shows the equations`）。
2. **确定性时钟**：原话「`?film=1` gives a deterministic clock」→ 录制可复现：同输入 → 同片。
3. **坏也是算出来的**：原话「cut the regen cooling and the copper throat melts」「throw a fan blade and
   the solver computes the load the case has to hold」→ 失效/破坏是**求解结果**，不是写死的动画。
4. **真量纲 + 真材质**：原话「Real proportions in metres, 15 to 40 named parts」「Physically based steel,
   titanium, Inconel … with measured reflectances」→ 可信度来自**尺度与材质**，不来自贴图。

op=method / source / provenance / where
"""
from __future__ import annotations

import hashlib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CAPSULE = _ROOT / "gbt_allinone" / "store" / "devoured" / "devoured_airsuphq_machine-skill"
_SRC = "https://github.com/AirsupHQ/machine-skill"

_METHOD = (
    {
        "序": "①",
        "取法": "每帧真解，不查表",
        "原话": "Every number on screen is computed … a small solver per machine (Brayton cycle, rocket chamber and nozzle, …) drives every motion and every number",
        "我们的落点": "画面上的数必须**当帧解出来**，且能给人看方程；查表就标明是表",
        "我们已有": "diagram_distill ②（单一数源）的上游：这里把**数源本身**钉成求解器",
    },
    {
        "序": "②",
        "取法": "确定性时钟（录制可复现）",
        "原话": "?film=1 gives a deterministic clock",
        "我们的落点": "录出来的片子必须能**复跑**：同输入同片；非确定的部分要标出来",
        "我们已有": "仓里四元组印章/回归口径（跨口径打 not_comparable）",
    },
    {
        "序": "③",
        "取法": "坏也是算出来的（破坏=求解结果）",
        "原话": "cut the regen cooling and the copper throat melts … throw a fan blade and the solver computes the load the case has to hold",
        "我们的落点": "失效/破坏必须是**求解**，不许写死一段动画冒充",
        "我们已有": "sec_chain（从漏洞清单推演影响链，逐条带依据）",
    },
    {
        "序": "④",
        "取法": "真量纲 + 真材质（可信度来自尺度与材质）",
        "原话": "Real proportions in metres, 15 to 40 named parts … Physically based steel, titanium, Inconel … with measured reflectances",
        "我们的落点": "先量纲后画面：米/秒/牛先落地，材质用**实测** reflectance，不靠贴图糊",
        "我们已有": "diagram_distill ③（几何不变量要有审计）同一条精神",
    },
)


def method(**_kw) -> dict:
    """求解器驱动可视化的取法四条：我们的落点 + 原话 + 已有承接位。"""
    return {"ok": True, "op": "method", "kind": "machine_distill",
            "条目": [dict(r) for r in _METHOD],
            "边界": "本位管**数凭什么可信**；隔壁 `diagram_distill` 管**概念怎么变成机构**",
            "口径": "**取法**不是**建位**：四条都落在已有承接位/纪律上（不复制它的代码）"}


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
    return {"ok": True, "op": "source", "kind": "machine_distill",
            "repo": "AirsupHQ/machine-skill", "url": _SRC, "license": "MIT", "stars": 91,
            "胶囊": str(_CAPSULE.relative_to(_ROOT)).replace("\\", "/"), "文件": files,
            "口径": "只**读**胶囊（不写盘）；哈希现读现算，不是抄来的"}


def provenance(**_kw) -> dict:
    """蒸馏出处：每条落成哪个 op、来自哪句原话；**没蒸的如实标**。"""
    return {"ok": True, "op": "provenance", "kind": "machine_distill",
            "吞入件": {"repo": "AirsupHQ/machine-skill", "site": _SRC, "license": "MIT",
                       "stars": 91, "language": "JavaScript",
                       "胶囊": "gbt_allinone/store/devoured/devoured_airsuphq_machine-skill/"},
            "蒸馏映射": [
                {"原话/出处": "Describe any machine in one line. Claude builds the real thing, running on real physics（README 头）",
                 "落成": "本位立项：只取「数凭什么可信」那套取法，不取它的壳"},
                {"原话/出处": "Every number on screen is computed（README：hero 图说）",
                 "落成": "op=method ①（每帧真解）"},
                {"原话/出处": "a small solver per machine (Brayton cycle, rocket chamber and nozzle, slider crank and BMEP, torsional oscillator, Cp(lambda, beta), pump curves, Kienzle, Darcy) drives every motion and every number（README：Real physics）",
                 "落成": "op=method ①（求解器清单：每台机器自带小求解器）"},
                {"原话/出处": "?film=1 gives a deterministic clock（README：A film）",
                 "落成": "op=method ②（确定性时钟）"},
                {"原话/出处": "cut the regen cooling and the copper throat melts / throw a fan blade and the solver computes the load（README：Gallery）",
                 "落成": "op=method ③（坏也是算的）"},
                {"原话/出处": "Real proportions in metres … Physically based steel, titanium, Inconel … with measured reflectances（README：What you get）",
                 "落成": "op=method ④（真量纲 + 真材质）"},
                {"原话/出处": "examples/ 的 turbofan.html / rocket-engine.html / scripts/record.mjs / 28 s film beats（README）",
                 "落成": "**未蒸馏（故意）**：那是它的**作品与引擎**，不是取法"},
                {"原话/出处": "npx skills add AirsupHQ/machine-skill -g -a claude-code（README：Install）",
                 "落成": "**未蒸馏（故意）**：装它 = 改别的 agent 配置，不取"},
            ],
            "边界": "接入端 ≡ 我们**已有**的出图位（`code_art` / `scene_anchor` / `projection_card`）；"
                    "本位 ≡ 蒸馏件（求解器驱动的可信度判据）· 与 `diagram_distill` 互补不重复："
                    "一个管**画什么**，一个管**数凭什么可信**",
            "口径": "蒸馏 = 把外面**契合我们**的那部分取法变成我们自己的判据；"
                    "**没蒸出来的如实体现在「未蒸馏」那两行**"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "machine_distill", "tentacle": "machine_distill",
            "entry": "run_task('machine_distill', {'op': …})",
            "ops": ["method", "source", "provenance", "where"],
            "files": {"handler": "gbt_allinone/tools/machine_distill.py",
                      "胶囊": "gbt_allinone/store/devoured/devoured_airsuphq_machine-skill/"},
            "scopes": "零作用域（只读 + 纯算：无 subprocess / 无 urllib / 无写盘）",
            "contract": [
                {"op": "method", "params": "无", "returns": "求解器驱动四取法 + 我们的落点 + 已有承接位"},
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
                "ops": sorted(_OPS), "how": "run_task('machine_distill', {'op': …})"}
    extra = set(params) - _ALLOWED[op]
    if extra:
        return {"ok": False, "op": op, "fail_closed": True,
                "error": "不认的参数：" + str(sorted(extra)), "allowed": sorted(_ALLOWED[op])}
    return fn(**params)
