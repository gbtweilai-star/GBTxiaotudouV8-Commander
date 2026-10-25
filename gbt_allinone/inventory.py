"""GBT小土豆V8 · 全息盘点（inventory）——你的视图与框架的视图一次对齐。

问题根源（Owner 发现 2026-09-11）：家根有双重身份——既是框架的家，
又是 OpenClaw 桌面端工作区。人看到的（文件树）和 AI 扫描的（hygiene/
signature/selfscan 各一套标准）永远对不上，永远有"遗漏"。

本能力一次输出统一视图：每个文件/目录都有**唯一归属标签**：
  framework   框架本体（gbt_allinone/ + README + requirements——她的一切）
  environment OpenClaw 运行环境（桌面端管理的 workspace 文件——不是框架的）
  data        框架数据（store/ 下的产物与记录——她记得的）
  archive     归档（archived_logs——历史）
  foreign     异物（不属于以上任何一类——需要处置的真正"遗漏"）

并给出双视图差异摘要：用户视角的文件总数 vs 框架管辖数 vs 异物数。
fix=True 时：foreign 中可安全处置项（临时脚本）自动清理，其余只报告。
"""
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent
_HOME = _BASE.parent

# 双身份检测：家根是否同时是 OpenClaw 工作区（宿主）。
# 框架只管辖 gbt_allinone/ 与下列声明的家根项；家根其余顶层项是宿主物。
_HOME_IS_WORKSPACE = (_HOME / ".openclaw").is_dir() or (
    (_HOME / "SOUL.md").exists() and (_HOME / "AGENTS.md").exists())
_FRAMEWORK_ROOT = {"README.md", "requirements.txt", "gbt_allinone"}

# 环境文件的单一来源（归属裁判在此）：
# 规则化判定（结构性特征）+ 显式清单兜底——桌面端新增文件类型时规则自动覆盖。
_ENV_FILES = {
    # OpenClaw 桌面端工作区的固定配置
    "AGENTS.md", "SOUL.md", "MEMORY.md", "USER.md", "TOOLS.md", "HEARTBEAT.md",
    "IDENTITY.md", "SELF_INTRO.md",
    # 桌面端设计工作流文档（.md 且非框架三件的家根文档默认环境）
    "DESIGN.md", "INDEX.md", "INTERACTIONS.md", "OUTPUT_RULES.md",
    "PRD_INGESTION.md", "REDESIGN.md", "TASK_ROUTER.md", "UI-check.md",
    "CODE_INGESTION.md", "IMAGE_GENERATION.md", "visual-asset-director.md",
}
_ENV_DIRS = {
    ".openclaw", ".openclaw-attachments", ".opencode", "archive", "memory",
    "outputs", "design-assets-index", "infinite-canvas-output", "config",
    "审美相关skill", ".git", ".agents", ".backups", "_wheels",
}


def _is_environment(name: str) -> bool:
    """OpenClaw 工作区环境判定（规则化：不依赖枚举追新）。

    规则：隐藏项（. 开头）= 环境缓存/配置；
          家根 .md（非框架 README）= 桌面端工作文档（桌面端只往家根放 .md/.json 工作文档）；
          显式清单兜底已知目录。
    """
    # 垃圾残留优先归 transient（运行足迹），不算宿主环境
    if name.endswith((".tmp", ".deleted")) or (name.startswith("_") and name.endswith((".py", ".txt"))):
        return False
    if name in _ENV_FILES or name in _ENV_DIRS:
        return True
    if name.startswith("."):
        return True
    if name.endswith(".md") and name != "README.md":
        return True
    # 双身份兜底：家根同时是 OpenClaw 工作区时，框架未声明的顶层项一律归宿主环境
    # （工作区基础设施 / 邻居 agent 家 / 用户自有文件——都不是框架的病）
    if _HOME_IS_WORKSPACE and name not in _FRAMEWORK_ROOT:
        return True
    return False


def _classify(p: Path) -> str:
    name = p.name
    try:
        rel = p.relative_to(_HOME).as_posix()
    except ValueError:
        # 🔴 2026-09-26 修（真故障，被 `test_signature_no_env_overreach` 抓出来）：
        # 分类器必须是**全函数** —— 家外路径（典型：`GBT_STORE_DIR` 被指到临时测试库，
        # 扫描器把临时 store 的页面带进来）以前会当场抛 `ValueError`，
        # 把"分类"变成"崩溃"。现在：家外凡在 store 里的归 `data`，其余归 `foreign`。
        parts = {s.lower() for s in p.parts}
        return "data" if "store" in parts else "foreign"
    # 框架本体
    if rel.startswith("gbt_allinone/"):
        # 框架内再分数据
        if "/store/" in rel:
            return "data"
        if rel.startswith("gbt_allinone/archived_logs/"):
            return "archive"
        return "framework"
    if name in ("README.md", "requirements.txt", "gbt_allinone"):
        return "framework"
    # 环境文件（OpenClaw workspace——规则化判定，单一来源在此）
    if _is_environment(name):
        return "environment"
    # 临时脚本（_*.py / *.tmp）= 运行足迹（观察者效应：扫描自己正跑的脚本）
    # 与 hygiene 铁律2 对齐——不算框架异物
    if (name.startswith("_") and name.endswith((".py", ".txt"))) or name.endswith((".tmp", ".deleted")):
        return "transient"
    # 其他皆异物
    return "foreign"


def scan(fix: bool = False) -> dict:
    """全息盘点：家的每一项都有归属。返回四分类清单 + 双视图对账。

    R-H295 · ⑥ G1/G2：家的根不存在/读不了时返回**结构化拒绝** ——
    原来 `_HOME.iterdir()` 会直接抛异常，调用方分不清"家不在"与"程序坏了"。
    """
    t0 = time.time()
    if not _HOME.is_dir():
        return {
            "ok": False,
            "unavailable": True,
            "denied": False,
            "rule": "inventory_home_missing",
            "action": "inventory.scan",
            "missing": ["home"],
            "why": "家的根不存在或不是目录：%s（盘不了点，不是没东西）" % _HOME,
            "items": {}, "scanned": False,
            "note": "盘点不了 ⇒ 没验成，不报『零游离物』。",
        }
    items = {"framework": [], "environment": [], "data": [], "archive": [], "transient": [], "foreign": []}
    try:
        entries = sorted(_HOME.iterdir())
    except OSError as exc:
        return {
            "ok": False,
            "unavailable": True,
            "denied": False,
            "rule": "inventory_home_unreadable",
            "action": "inventory.scan",
            "missing": ["read_permission"],
            "why": "读家的根失败：%s: %s" % (type(exc).__name__, str(exc)[:160]),
            "items": {}, "scanned": False,
        }
    for p in entries:
        if p.name in (".git",):
            continue
        cat = _classify(p)
        info = {"name": p.name, "type": "dir" if p.is_dir() else "file"}
        if p.is_file():
            info["size_kb"] = max(1, p.stat().st_size // 1024)
        items[cat].append(info)

    # 框架内部统计（framework 细分给用户看）
    pkg = _HOME / "gbt_allinone"
    fw_detail = {}
    if pkg.exists():
        for sub in sorted(pkg.iterdir()):
            if sub.is_dir() and sub.name not in ("__pycache__", ".pylibs", "store", "archived_logs"):
                fw_detail[sub.name] = len(list(sub.glob("*.py")))
        fw_detail["(包根 .py)"] = len(list(pkg.glob("*.py")))

    # 数据统计
    store = pkg / "store" if pkg.exists() else None
    data_detail = {}
    if store and store.exists():
        for sub in ("devoured", "pipeline", "mirror_space", "wf_runs", "vision"):
            d = store / sub
            if d.exists():
                data_detail[sub] = len(list(d.rglob("*")))

    # 异物处置
    fixed = []
    if fix:
        for it in list(items["foreign"]):
            p = _HOME / it["name"]
            if it["type"] == "file" and (p.name.startswith("_") and p.suffix == ".py" or p.suffix == ".tmp"):
                p.unlink()
                fixed.append(it["name"])
                items["foreign"].remove(it)

    total = sum(len(v) for v in items.values())
    result = {
        "ok": True,
        "verdict": "clean" if not items["foreign"] else ("fixed" if fixed else "foreign_found"),
        "dual_view": {
            "你看到的（家根总项）": total,
            "框架管辖（framework）": len(items["framework"]),
            "环境托管（environment）": len(items["environment"]),
            "异物（foreign）": len(items["foreign"]),
        },
        "items": {k: [i["name"] for i in v] for k, v in items.items()},
        "framework_detail": fw_detail,
        "data_detail": data_detail,
        "fixed": fixed,
        "law": "framework=她的本体 environment=桌面端的家 data=她记得的 foreign=要处置的",
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
    }
    try:
        from .store import audit
        audit("inventory", {"verdict": result["verdict"], "foreign": len(items["foreign"])})
    except Exception:
        pass
    return result
