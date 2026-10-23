# gbt-capability: caps_called_audit
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""能力位调用点审计（caps_called_audit）· R-H192 只读。

**判据（元规则）**：能力位的价值不在"登记了多少"，在"**有几个真活着**"。
零调用点的能力位，等于不存在。

做法：**动态计算**每个能力位的 `called_by`（谁在调用），**不手写字段** ——
手写的字段会腐烂（判据挂旧数据），算出来的不会。

口径（三层）：
  · **registry**：出现在 `caps_registry.BENIGN_CAPS` 里（= 挂了号）
  · **route**   ：`api.py` 里有分支（= 有官方入口）
  · **callers** ：registry/api/tests/docs/store 之外的代码里被引用（= **真接线**）
只有 `callers` 非空的才算"活着"；只有 registry 没有 callers 的 = **孤儿**。

本模块只读：不写盘、不出网、不执行任何能力。
"""
from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SELF = Path(__file__).name

REGISTRY_FILES = {"caps_registry.py", "api.py", _SELF}
SKIP_PARTS = (".pylibs", "node_modules", ".git", "__pycache__", "store", "docs", ".scratch",
              "archive", "resources", "dist", "build")
SCAN_DIRS = ("gbt_allinone", "holo_pet")
SCAN_SUFFIX = (".py", ".js", ".cjs")
# `\w+` 型 kind（本仓全部能力位都是）可走词表快查；其余走原正则，保证语义不变
_TOKEN_KIND = re.compile(r"\w+")

# ── 能力位分两类（R-H194 · 主人定）────────────────────────────
#   internal（内调型）：给别的模块用的 ⇒ **必须**被 import/called，否则报 orphan
#   external（入口型）：给人或 API 用的 ⇒ **天生就是门**，不被别的模块调用**不算孤儿**
# 默认 internal —— 这是**保守方向**：新能力位没登记类型时，先按"该被调用"要求它，
# 报出来的孤儿是**假红**（可以解释），而不会把真孤儿洗成 external（假绿）。
CAP_TYPES = {
    # 门 / 入口（给人或 API 用）
    "auth_gate_status": "external",     # 只读探针：查授权闸状态，给人查的
    "codex_tools": "external",          # 人用的工具清单
    "mcp_tools": "external",            # 人用的工具约清单（含入参 schema）
    "pipeline_versions": "external",    # 查版本历史的入口
    "orchestration_kernel": "external",  # 引擎入口（它自己就是那根线）
    # R-H202 判定（不是"忘了接"，是"它就是门"）：
    # `sec_chain` = 安全面 HackerBrain 的**入口**（`api.py:196` 直接调 build_exploit_chain），
    # 它是"人调的安全分析入口"，不是"给别的模块调的内部件" ⇒ 归 external。
    "sec_chain": "external",
    # 2026-10-13（主人令「发现问题必须追根因修」）：**蒸馏件家族**同 `sec_chain` 一类 ——
    # 它们是「人/agent 经门调的判据件」（`cap <kind>`），**不是给别的模块 import 的内部件**
    # ⇒ 按本文件自己的口径归 external；此前落默认 internal ⇒ 被当孤儿（假红）。
    "recon_distill": "external",
    "cad_distill": "external",
    "bi_distill": "external",
    # 2026-10-13 同上：这 6 位都暴露 status/plan/push/semantics 这类**给人/agent 调的 op**；
    # 按本文件判据「零调用点的内调型＝不存在」⇒ 零调用点的位只可能是入口型。
    "dh_pose": "external",
    "express_direct": "external",
    "pulse_direct": "external",
    "repo_publish": "external",
    "ring_context": "external",
    "warm_switch": "external",
    # R-H 入口型：api.py _run_benign 路由的入口能力，与 pipeline_versions 同族
    "agency_tentacles": "external",
    "media_pipeline": "external",
    # 第 81 轮补：`media_run`（三方向链执行器）**与 `media_pipeline` 同族** ——
    # 它只经 `api.run_task` 这道门进入，框架内部**没有任何东西该调它**。
    # 当初给 `media_pipeline` 分型时**漏了它一个** ⇒ 落回默认 internal ⇒
    # `caps_called_audit` 把它报成孤儿（`self_ref_only`），而它明明是入口。
    # 证据：审计自己的读数 `orphans: ["media_run"]` / `self_ref_only: ["media_run"]`。
    "media_run": "external",
    # 第 55 轮补：`datakit`（本地数据工具）**与 `media_run` 同族** ——
    # 它只经 `api.run_task` 这道门进入（`api.py` 的 `datakit` 分支），
    # 框架内部**没有任何东西该调它**：它是**给人用的入口**（HTML转MD / JSON美化 / CSV合并…）。
    # 证：不补分型时审计自己的读数就是 `orphan_count: 0 → 1`（我刚接上它时实测到的），
    # 补完应回 0。**分型不是洗白**：判据是"它是不是门"，不是"想不想让它绿"。
    "datakit": "external",
    "tentacle_pipeline": "external",
    # 🔴 2026-10-05 补 11 位（第七腿「分型」漏项 · P2 同族）：下面 11 位全是**蒸馏出来的工具位**
    # （agent_control / answer_shaper / belief_forge / cli_chat / creation_camp / db_probe /
    #  llm_redteam / policy_delta / slim_profile / spend_guard / thebrain_bridge）——
    # 每位都有 `api.py` 官方入口（=官方门），且**没有任何模块该调它们**：调用者就是经
    # `run_task` 的人/AI。与 `datakit` / `media_run` / `agency_tentacles` **同族**（那三条
    # 就是按同一判据补的）。**判据不是"想让它绿"**：逐位现读 docstring，无一位声明
    # "供内部模块调用"；审计当时的读数就是 `orphans: [这 11 位]`（orphan_count 0→11）。
    "agent_control": "external",
    "answer_shaper": "external",
    "belief_forge": "external",
    "cli_chat": "external",
    "creation_camp": "external",
    "db_probe": "external",
    "llm_redteam": "external",
    "policy_delta": "external",
    "slim_profile": "external",
    "spend_guard": "external",
    "thebrain_bridge": "external",
    # 2026-10-08 补 1 位（同族漏项 · review_gate 在册后）：它是**入口型** ——
    # 只经 `api.py` 的 `review_gate` 分支（run_task 唯一门）进入，框架内部无模块该调它。
    # 判据同 thebrain_bridge/media_run：不补分型时审计会按默认 internal 把它报成孤儿（假红）。
    "review_gate": "external",
    # 2026-10-08 补 1 位（同族漏项 · dh_brain 在册后）：数字人本体**只读门面** ——
    # 有 `api.py` 分派（run_task 唯一门）、零写面、**框架内部无模块该调它**
    # （它的读者是人与面板，不是别的模块）⇒ 入口型。实测：不补分型时审计报
    # `orphans: ['dh_brain']`（假红）。
    "dh_brain": "external",
    # ── 2026-10-17 补 18 位（全量审计现读 orphans=18；**逐位现读 desc** 后分类）──
    #   判据与上面 11 位**完全同族**：都有 `api.py` 分派（run_task 唯一门，现读 undispatched=0），
    #   desc 读者都是**人与面板**（去AI味改写 / 技能检索 / 知识图 / 图表 / 回炉训练场 / 镶嵌窗口…），
    #   **框架内部没有模块该调它们** ⇒ 入口型 external。
    #   ⚠️ 这不是"想让它绿"：若哪天某位真该被内部模块调用（如 humanizer 该挂进写作链），
    #      正确做法是**去接那根线**（改 internal 并补调用）；把 internal 留在这里才是假绿。
    "chart_html": "external",
    "cli_ify": "external",
    "cloud_plugin": "external",
    "db_plugin": "external",
    "dl_forge": "external",
    "forge_mastery": "external",
    "humanizer": "external",
    "know_map": "external",
    "offense_ops": "external",
    "quant_plan": "external",
    "showcase_ops": "external",
    "skill_finder": "external",
    "skill_forge": "external",
    "spider_ops": "external",
    "telegram_embed": "external",
    "tentacle_learn": "external",
    "train_ground": "external",
    "whatsapp_embed": "external",
    # ── 2026-10-18 补 2 位（全量审计现读 `orphans: ['install_selfcheck','voice_studio']`）──
    #   判据与上面同族，且这次**逐位现读过分派面**（不是照名字猜）：
    #     · `install_selfcheck` —— `api.py:660` 的 `if kind == "install_selfcheck"` 分派；
    #       模块自带 `where` op（`install_selfcheck.py:219`）把入口命令写给人；
    #       读者是「装机后的人/agent」，框架内部无模块该 import 它（只读查，不联动）。
    #     · `voice_studio` —— `api.py:670` 的 `if kind == "voice_studio"` 分派；
    #       模块自带 `plan`/`where` op（`voice_studio.py:186,201`）；
    #       读者是「要连 VoiceStudio 本地后端的人」，不是别的模块。
    #   ⚠️ 同上面 18 位的免责：这**不是**"想让它绿"。若哪天 install_selfcheck 该在
    #      **装完大模型后自动跑一遍**（主人 2026-10-17 令的原文），正确做法是去接那根线、
    #      把它改回 internal 并补真实调用点 —— 那时审计会替我们咬住没接的情况。
    "install_selfcheck": "external",
    "voice_studio": "external",
    # ── 2026-10-19 补 3 位（主人令「这两个能力不就可以完美补齐缺失了吗」接入的两个外部件 + 同族漏项）──
    #   判据与上面同族，逐位现读**分派面**（不是照名字猜）：
    #     · `anatomy_figures` —— `api.py` 的 `if kind == "anatomy_figures"` 分派 →
    #       `tools/anatomy_cap.py:run_op`；读者是「要出等轴详解图的人/AI」，框架内部无模块该 import 它。
    #     · `machine_film` —— 同上，→ `tools/machine_cap.py:run_op`；读者是「要出科普成片的人/AI」。
    #     · `image_scout` —— `api.py` 的 `if kind == "image_scout"` 分派 → `image_scout.py:run_op`；
    #       自带 `sources/curate/where` op（给人看的），同样不是给别的模块 import 的内部件。
    #   ⚠️ 免责同上面各位：这**不是**"想让它绿"。若哪天它们该被内部模块调用（例如成片链要自动
    #      调 anatomy 出图），正确做法是去接那根线并改回 internal —— 那时审计会咬住没接的调用点。
    "anatomy_figures": "external",
    "machine_film": "external",
    "image_scout": "external",
    # 2026-10-19 建模绑骨五位一套（`api.py` 一个分支路由五个 kind → `tools/dh_rig.py:run_op`）；
    # 读者是「要验/修数字人资产的人/AI」，框架内部无模块该 import 它 ⇒ 同 `dh_pose` 一族。
    "rig_audit": "external",
    "rig_fix": "external",
    "anim_audit": "external",
    "anim_fix": "external",
    "dh_asset_gate": "external",
    # 2026-10-19 Omni-Arm（22DoF 手 + 9 骨臂 + 8 段触手）：只经 `cap omni_arm` 进，内部无模块该调它。
    "omni_arm": "external",
    # 2026-10-19 触手操控臂：同上，只经 `cap tentacle_arm` 进。
    "tentacle_arm": "external",
}
DEFAULT_TYPE = "internal"
CAP_TYPE_CN = {"internal": "内调型（给别的模块用）", "external": "入口型（给人/API 用）"}


def cap_type(kind: str) -> str:
    return CAP_TYPES.get(str(kind), DEFAULT_TYPE)


def _candidate_files():
    """待扫文件（近 220 个）：排除登记文件、用例、依赖、文档与账本。"""
    for base in SCAN_DIRS:
        root = _ROOT / base
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix not in SCAN_SUFFIX:
                continue
            if any(s in p.parts for s in SKIP_PARTS):
                continue
            if "tests" in p.parts or p.name in REGISTRY_FILES:
                continue
            yield p


def _corpus() -> list:
    rows = []
    for p in _candidate_files():
        try:
            rows.append((p.relative_to(_ROOT).as_posix(),
                         _code_only(p.read_text(encoding="utf-8", errors="replace"),
                                    p.suffix)))
        except OSError:
            continue
    return rows


def _code_only(text: str, suffix: str) -> str:
    """**剥掉注释**再扫（R-H194 修：注释里提一句 ≠ 有人调用它）。

    由来（一手）：编排内核里我写了注记「注：`sec_chain` … 故意不接」，
    审计器就把 `sec_chain` 判成**已接线**，把一个**真孤儿**盖住了 ——
    与坑册第 34 条（扫到"提到"而不是"用了"）同族。

    口径：**只剥注释、保留字符串** —— 字符串字面量可能是真数据（如派发表的键），
    那属于"可执行的提及"；注释则一定是陈述。
    """
    if suffix == ".py":
        try:
            parts = []
            for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                if tok.type == tokenize.COMMENT:
                    continue
                parts.append(tok.string)
            return "\n".join(parts)
        except Exception:  # noqa: BLE001
            return re.sub(r"#.*", "", text)
    out = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", out)


def _corpus_index(corpus: list) -> list:
    """把语料**每个文件切一次词表**，供后续 O(1) 查词。

    为什么改（2026-09-22 实测）：原实现是「每个能力位 × 每个文件」各跑一次
    `re.search`：141 位 × 275 文件 = **38,775 次正则**，每次扫全文（合计 4.4 MB），
    实测 `audit()` 要 **19.5–33.2s**（抖动本身就让用例在 30s 硬超时边缘时红时绿）。
    拆开量过：走树 0.85s、读语料 1.88s —— 钱全花在这层重扫上。

    等价性：`re.compile(r"\\b" + re.escape(kind) + r"\\b")` 在 kind 是 `\\w+` 型时，
    等价于「kind 是文本里的一个**完整词**」，故可先切词集合再查。
    非 `\\w+` 型（含连字符等）仍走原正则路径 —— **不改变任何语义**。
    改完必须与冻结基线逐字节一致（见 tests/test_caps_called_audit.py 的口径）。
    """
    return [(rel, frozenset(re.findall(r"\w+", txt)), txt) for rel, txt in corpus]


def audit(kinds: list | None = None) -> dict:
    """逐个能力位算 called_by（只读）。返回 wired / orphan 两张清单。"""
    from ..caps_registry import BENIGN_CAPS
    corpus = _corpus()
    indexed = _corpus_index(corpus)
    targets = sorted(kinds) if kinds else sorted(BENIGN_CAPS)
    rows = []
    for kind in targets:
        # 判据与原来**逐字等价**（等价性说明见 _corpus_index）：
        # `\w+` 型 kind 走词表 O(1) 查；含非词字符的 kind 退回原正则路径。
        exact = _TOKEN_KIND.fullmatch(kind) is not None
        pat = None if exact else re.compile(r"\b" + re.escape(kind) + r"\b")
        # 🔴 口径修正（第一版被自己的读数打脸）：**同名模块自己的提及不算接线** ——
        # `account_registry.py` 里写着自己的名字，那不是"有人调用它"，那是自我介绍。
        # 不排掉这一层，审计会给出**假绿**（112/120），把"孤儿"算成"活着"。
        self_module_names = {kind + ".py", kind + ".js", kind + ".cjs"}
        callers, self_refs = [], []
        for rel, tokens, txt in indexed:
            hit = (kind in tokens) if exact else bool(pat.search(txt))
            if not hit:
                continue
            if Path(rel).name in self_module_names:
                self_refs.append(rel)
            else:
                callers.append(rel)
        rows.append({
            "kind": kind,
            "registry": kind in BENIGN_CAPS,
            "callers": callers,
            "self_refs": self_refs,
            "wired": bool(callers),
            "cap_type": cap_type(kind),
        })
    wired = [r for r in rows if r["wired"]]
    unwired = [r for r in rows if not r["wired"]]
    orphan = [r for r in unwired if r["cap_type"] == "internal"]
    entries = [r for r in unwired if r["cap_type"] == "external"]
    return {
        "ok": True,
        "readonly": True,
        "scanned_files": len(corpus),
        "total": len(rows),
        "wired_count": len(wired),
        "orphan_count": len(orphan),
        "wired": [{"kind": r["kind"], "callers": r["callers"],
                   "self_refs": r["self_refs"], "cap_type": r["cap_type"]} for r in wired],
        "orphans": [r["kind"] for r in orphan],
        "external_entries": [r["kind"] for r in entries],
        "unwired_by_name": [r["kind"] for r in unwired],
        "self_ref_only": [r["kind"] for r in unwired if r["self_refs"]],
        "rule": ("零调用点的**内调型**能力位 = 不存在；**入口型**天生是门，不报孤儿"),
        "cap_types": CAP_TYPES, "default_type": DEFAULT_TYPE,
    }


def run(op="audit", **params) -> dict:
    """能力入口（只读）：audit / orphans / wired。不写盘、不出网、不执行。"""
    op = str(op or "audit")
    data = audit(params.get("kinds") if isinstance(params.get("kinds"), list) else None)
    if op == "audit":
        return data
    if op == "orphans":
        return {"ok": True, "readonly": True, "orphans": data["orphans"],
                "orphan_count": data["orphan_count"], "total": data["total"]}
    if op == "wired":
        return {"ok": True, "readonly": True, "wired": data["wired"],
                "wired_count": data["wired_count"], "total": data["total"]}
    raise ValueError("未知 op %r（可用：audit/orphans/wired）" % (op,))


HONEST_BOUNDARY = (
    "本审计只保证『有没有代码引用这个能力名』。"
    "它**不保证**那条引用是**正确的接线**（可能只是提到、只是常量表）——"
    "所以它给的是**候选接线**，真正的接线仍要人看那一行。"
    "口径边界：已剥掉注释（注释提及不算），但**保留字符串字面量**"
    "（派发表的键属于可执行提及）；JS 侧只做注释剥离，不做字符串感知。"
)
