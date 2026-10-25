# gbt-capability: energy_pool
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""能源池（energy_pool）· R-H223 只读骨架。

**能源观**：模型不是"大脑"，是**燃料** —— 模型是 92 号，发动机是原生栈。

三层：
  ① 能源抽象层 —— 所有模型统一为 `EnergySource`，**大脑只认接口，不认模型名**；
  ② 原生能力衍生器 —— 按能源生成调用代码与流水线，**不依赖外部 SDK**；
  ③ 能源池 —— **免费优先，但不拒绝付费**；**没有能源时如实报缺**。

五条红线（做成机械闸）：
  ① 模型是燃料，不是身份　② 能源可换，原生栈不动　③ 衍生代码必须走原生路由
  ④ 能源池按需分配　　　　⑤ 没有能源时如实报缺

本骨架只读：**不调模型、不出网、不落盘、不发密钥**。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

CAP_KIND = "energy_pool"
DOMAIN = "system"
CAP_TYPE = "internal"          # 内调型：给别的模块用（不是"门"）

SECRETS_DIR = "store/secrets"

# ── R-H224 · 能源抽象层（官方设计口径）──
# 「荤素之别」：付费 / 免费只是荤素，**不改变它"是燃料"这件事**
GRADES = ("免费", "付费", "高级", "未知")
KINDS = ("荤", "素")            # 荤＝付费 · 素＝免费（比喻 · 不参与判据）
STATUSES = ("可用", "限流", "缺key")


@dataclass(frozen=True)
class EnergySource:
    """**所有模型统一成一个接口**：大脑只认它，不认具体模型名。"""

    source_id: str                       # 如 agnes-2.5-flash
    grade: str = "未知"                   # 免费 / 付费 / 高级
    kind: str = "未知"                    # 荤 / 素（付费 / 免费）
    endpoint: str = ""                   # base_url
    key_ref: str = ""                    # **DPAPI 引用，不存明文**
    capability: tuple = ("text",)        # text / image / video / code
    status: str = "缺key"                 # 可用 / 限流 / 缺key

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["capability"] = list(self.capability)
        return d

# 五条红线（写死）
RED_LINES = (
    "模型是燃料，不是身份（owner_ai_id 只能是 AI 身份，永远不是模型名）",
    "能源可换，原生栈不动（换能源不改变原生栈指纹）",
    "衍生代码必须走原生路由（不许把 SDK 直连写进衍生代码）",
    "能源池按需分配（按 owner_ai_id 借，用完归还，不许囤）",
    "没有能源时如实报缺（不硬撑、不假装有）",
)

# 附带三条（同一族）
SIDE_RULES = (
    "输出**永远不以模型自居** —— 它是燃料，不是说话的人",
    "自动生成的代码**也不能绕过路由**",
    "**不许硬编、不许偷密钥** —— key 只从 DPAPI / 密钥池取",
)

# ── R-H226 · 「原生栈」到底指什么（主人钉死）──
# 红线③原话：**换模型时，触手 / 记忆 / 门禁 / 审计一条不动**
NATIVE_STACK = (
    {"key": "tentacle", "cn": "触手", "why": "执行末端"},
    {"key": "memory", "cn": "记忆", "why": "trace_store / 生命档案 / 知识库"},
    {"key": "gate", "cn": "门禁", "why": "auth_gate / 权限/二次确认"},
    {"key": "audit", "cn": "审计", "why": "独立复核 / 假绿检测 / 护照"},
)

# 能源观五条红线（官方口径 · R-H226 对账过 5/5 已有闸）
ENERGY_REDLINES = (
    {"n": 1, "cn": "模型是燃料，不是身份", "gate": "model_is_not_identity"},
    {"n": 2, "cn": "能源可换，原生栈不动", "gate": "stack_drift"},
    {"n": 3, "cn": "换模型时，触手 / 记忆 / 门禁 / 审计一条不动",
     "gate": "check_stack_four → native_stack_changed"},
    {"n": 4, "cn": "衍生代码必须走原生路由", "gate": "derived_bypasses_route"},
    {"n": 5, "cn": "能源池按需分配", "gate": "lease_energy（按 owner_ai_id）"},
)

# ── R-H225 · 视频自研**八层图**（主人给 · **与生产流水线并存，不合并**）──
# 注意：这套讲的是「**哪一层我们自己扛**」（自研边界），
# 而 derive_video_pipeline 那套讲的是「**片子怎么做出来**」（生产步骤）——
# **两个维度，各说各的**。
SELF_DEV_LAYERS = (
    {"n": 1, "layer": "脚本/分镜", "ours": True, "module": ""},
    {"n": 2, "layer": "原生能力（已有）", "ours": True, "module": "caps_registry"},
    {"n": 3, "layer": "画面生成", "ours": True, "module": ""},
    {"n": 4, "layer": "原生调度（调度多个模型）", "ours": True,
     "module": "orchestration_kernel"},
    {"n": 5, "layer": "流畅度", "ours": True, "module": "render_evolution"},
    {"n": 6, "layer": "原生帧插值 + 编码", "ours": True, "module": "render_evolution"},
    {"n": 7, "layer": "成片", "ours": True, "module": ""},
    {"n": 8, "layer": "原生剪辑 + 品牌片尾", "ours": True, "module": "brand_outro"},
)

# 照报：这套八层图与我们的六步流水线**两处差异**
SELF_DEV_DIFFS = (
    "① 八层图里**没有**「质检与重跑」（我们流水线有）——不擅自补，待主人确认；",
    "② 八层图**从「脚本/分镜」起头**（我们流水线第 1 步是「素材输入」）⇒ "
    "素材属于**输入**，不算自研层；",
    "③ 八层图有**四层带「原生」**（原生能力 / 原生调度 / 原生帧插值 / 原生剪辑）⇒ "
    "它讲的是**自研边界**，不是生产步骤 —— **两个维度并存，不合并**。",
)

# 衍生代码里**不许出现**的形状（= 绕过原生路由）
_BYPASS_PATTERNS = (
    r"^\s*import\s+openai\b", r"^\s*from\s+openai\b",
    r"^\s*import\s+anthropic\b", r"^\s*from\s+anthropic\b",
    r"import\s+requests\b.*https?://", r"requests\.post\(",
    r"urllib\.request", r"http\.client",
)


def _profiles() -> Dict[str, dict]:
    """盘上现有的能源表（复用 deepseek_key._PROFILES —— **引用，不另造**）。"""
    try:
        from .. import deepseek_key as dk
        return dict(getattr(dk, "_PROFILES", {}) or {})
    except Exception:  # noqa: BLE001
        return {}


def _secrets_dir() -> Path:
    root = Path(__file__).resolve().parents[1]
    return root / SECRETS_DIR


def list_energies() -> List[dict]:
    """现有能源清单（**动态读盘**，不手写）。"""
    prof = _profiles()
    sdir = _secrets_dir()
    out = []
    for name, cfg in prof.items():
        f = str(cfg.get("file") or "")
        out.append({
            "name": name,
            "key_ref": "%s/%s" % (SECRETS_DIR, f) if f else "",
            "env": cfg.get("env") or "",
            "on_disk": bool(f) and (sdir / f).is_file(),
            # ⚠️ 盘上没有免费/付费字段 ⇒ **如实标 unknown**，不编
            "tier": "unknown",
        })
    # ── 本地原生端点（土豆大模型 · 双向互绑 2026-09-26 主人令）──
    # ⚠️ 2026-10-04 修 F20：本仓能源的**统一模型**是「可用 ⟺ key_ref 在盘」，本地端点也照走 ——
    # 不给第三态「接线态」（实测它会穿透 `derive_client_code` 的 `缺key` 拦门 ⇒ 为一条没凭据的
    # 能源生成调用代码）。凭据文件（如放行令牌）落进 store/secrets 之前，一律如实报「缺key」。
    _ql = "qwen_local.dpapi"
    out.append({
        "name": "qwen-local",
        "key_ref": "%s/%s" % (SECRETS_DIR, _ql),
        "env": "GBT_LLM_API_KEY",
        "on_disk": (sdir / _ql).is_file(),
        "tier": "unknown",
        "endpoint": "http://127.0.0.1:8111/v1",
        "status": "可用" if (sdir / _ql).is_file() else "缺key",
    })
    return sorted(out, key=lambda x: x["name"])


def status() -> dict:
    """能源池读数（只读）。"""
    items = list_energies()
    return {
        "ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
        "type": CAP_TYPE,
        "count": len(items),
        "energies": items,
        "dpapi_on_disk": [x["name"] for x in items if x["on_disk"]],
        "dpapi_missing": [x["name"] for x in items if not x["on_disk"]],
        "tier_known": [x["name"] for x in items if x["tier"] != "unknown"],
        "note": "**免费/付费盘上判不出**（没有该字段）⇒ 标 unknown，不编；"
                "能源可换，原生栈不动",
        "side_rules": list(SIDE_RULES),
    }


def check_identity_not_model(owner_ai_id: str = "",
                             known_models: Optional[List[str]] = None) -> dict:
    """红线①：**模型是燃料，不是身份** —— `owner_ai_id` 不能是模型名。"""
    o = str(owner_ai_id or "").strip()
    if not o:
        return {"ok": False, "denied": True, "rule": "missing_owner_ai_id",
                "why": "一 AI 一号：能源要借给某个 **AI 身份**，不是借给模型"}
    names = {str(m).lower() for m in (known_models or [])}
    names |= {n.lower() for n in _profiles()}
    if o.lower() in names:
        return {"ok": False, "denied": True, "rule": "model_is_not_identity",
                "owner_ai_id": o,
                "why": "**模型是燃料，不是身份**：`owner_ai_id` 只能是 AI 身份，"
                       "永远不能填模型名（否则换模型 = 换身份）"}
    return {"ok": True, "readonly": True, "owner_ai_id": o}


def check_stack_unchanged(before: Any = None, after: Any = None) -> dict:
    """红线②：**能源可换，原生栈不动** —— 换能源前后，原生栈指纹必须一致。"""
    if before is None or after is None:
        return {"ok": False, "denied": True, "rule": "missing_stack_fingerprint",
                "why": "要给换能源**前后**的原生栈指纹，才能证明没被动过"}
    if before != after:
        return {"ok": False, "denied": True, "rule": "stack_drift",
                "before": str(before)[:120], "after": str(after)[:120],
                "why": "换能源把**原生栈**也换了 ⇒ 那就不是「换叶」，是「换根」了"}
    return {"ok": True, "readonly": True, "stack": str(before)[:120],
            "note": "能源换了，原生栈没动 ⇒ 才是『换叶不换根』"}


def check_stack_four(before: Optional[Dict] = None,
                     after: Optional[Dict] = None) -> dict:
    """R-H226 红线③：换模型时，**触手 / 记忆 / 门禁 / 审计 四件逐一不变**。

    为什么要有这条：`check_stack_unchanged` 只判**一个总指纹**——
    总指纹一样，也可能"**触手换了、审计没换**"互相抵消。
    这条把四件**逐项**验一遍（红线原话就是这么列的）。
    """
    b, a = dict(before or {}), dict(after or {})
    if not b or not a:
        return {"ok": False, "denied": True, "rule": "missing_stack_snapshot",
                "expected_keys": [x["key"] for x in NATIVE_STACK],
                "why": "要给出**四件各自的指纹**（换前/换后），才能逐项验"}
    changed = [x["cn"] for x in NATIVE_STACK
               if str(b.get(x["key"])) != str(a.get(x["key"]))]
    if changed:
        return {"ok": False, "denied": True, "rule": "native_stack_changed",
                "changed": changed,
                "why": "换模型时**这四件一条都不许动**：%s —— "
                       "动了就是「换根」，不是「换叶」" % " / ".join(changed)}
    return {"ok": True, "readonly": True,
            "checked": [x["cn"] for x in NATIVE_STACK],
            "note": "四件逐项未变 ⇒ 换的确实是「叶」（模型），根没动"}


def check_derived_code(source: str = "") -> dict:
    """红线③：**衍生代码必须走原生路由**（不许 SDK 直连 / 不许自己拼请求）。"""
    src = str(source or "")
    if not src.strip():
        return {"ok": False, "denied": True, "rule": "empty_derived_code",
                "why": "没有代码可查 —— 未测不按绿"}
    hits = [p for p in _BYPASS_PATTERNS if re.search(p, src, re.M)]
    if hits:
        return {"ok": False, "denied": True, "rule": "derived_bypasses_route",
                "patterns": hits,
                "why": "衍生代码里出现 SDK / 直连请求 ⇒ **绕过原生路由**；"
                       "衍生代码也必须走统一出口（run_task）"}
    return {"ok": True, "readonly": True, "lines": len(src.splitlines()),
            "note": "衍生代码走原生路由 ⇒ 换能源时它不用改"}


def lease_energy(owner_ai_id: str = "", tentacle_id: str = "energy") -> dict:
    """红线④⑤：**按需分配** + **没有能源如实报缺**（走密钥池，不自己发钥匙）。"""
    if not str(owner_ai_id or "").strip():
        return {"ok": False, "denied": True, "rule": "missing_owner_ai_id",
                "why": "按需分配：要说清**给哪个 AI 身份**用"}
    try:
        from . import model_key_pool as mkp
        got = mkp.ModelKeyPool().lease(tentacle_id, owner_ai_id)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "denied": True, "rule": "key_pool_unavailable",
                "why": "密钥池不可用：%s" % str(e)[:80]}
    if not got.get("ok"):
        # 红线⑤：**没有能源就如实报缺，不硬撑**
        return {"ok": False, "denied": True,
                "rule": got.get("rule") or "no_key_for_owner",
                "honest": True,
                "why": "**没有能源 ⇒ 如实报缺**（不硬撑、不假装有）；"
                       "要加能源就过 auth_gate 落池"}
    return {"ok": True, "readonly": True, "lease_id": got.get("lease_id"),
            "owner_ai_id": owner_ai_id,
            "key_masked": "****（池内持有，不出池）",
            "note": "借来的钥匙用完要 release —— **不许囤**"}


def build_sources() -> List[EnergySource]:
    """把盘上的能源表**装配**成 `EnergySource`（动态读盘，不手写）。

    ⚠️ 诚实口径：`grade` / `kind` **盘上没有这个字段** ⇒ 一律 `未知`，
    **不编**；「荤素」只是比喻，**不参与任何判据**。
    """
    prof = _profiles()
    sdir = _secrets_dir()
    out: List[EnergySource] = []
    for name, cfg in prof.items():
        f = str(cfg.get("file") or "")
        has_key = bool(f) and (sdir / f).is_file()
        out.append(EnergySource(
            source_id=name,
            grade="未知", kind="未知",
            endpoint=str(cfg.get("base_url") or cfg.get("endpoint") or ""),
            key_ref=("%s/%s" % (SECRETS_DIR, f)) if f else "",
            capability=("text",),          # 盘上没有能力位字段 ⇒ 只标已知的文本
            status="可用" if has_key else "缺key",
        ))
    # ── 本地原生端点（土豆大模型 · 双向互绑 2026-09-26 主人令）────────────────
    # 无密钥本地端点：endpoint 指向本机 dsh-llm-qwen-local（preflight 已验收「可以接真
    # 端点」，真 vLLM 换 baseURL 一行即成）。
    # ⚠️ 2026-10-04 修 F20：本地端点也必须走**同一条不变量**（可用 ⟺ key_ref 在盘）——
    # 原来报第三态「接线态」，实测它会穿透 NativeDeriver 的 `缺key` 拦门（为没凭据的
    # 能源生成调用代码），且三条判据 + 复验器 probe_f20 都钉这条不变量。
    # 要让它「可用」：落一把 `store/secrets/qwen_local.dpapi`（放行令牌/占位凭据）即可。
    _ql = "qwen_local.dpapi"
    _ql_on_disk = (sdir / _ql).is_file()
    out.append(EnergySource(
        source_id="qwen-local",
        grade="未知", kind="未知",          # 盘上没有档位字段 ⇒ 如实「未知」，不编
        endpoint="http://127.0.0.1:8111/v1",
        key_ref="%s/%s" % (SECRETS_DIR, _ql),
        capability=("text",),               # multimodal 待真端点起来再实测升级，不预支
        status="可用" if _ql_on_disk else "缺key",   # 凭据不在盘 ⇒ 如实报缺，不谎报可用
    ))
    return sorted(out, key=lambda s: s.source_id)


class EnergyPool:
    """**能源池**：不挑食，但有优先级。

    - **不挑食**＝任何**可用**能源都能跑；
    - **荤素之别**＝免费 / 付费只是**偏好**，**不是能力差别**。
    """

    def __init__(self) -> None:
        self.sources: Dict[str, EnergySource] = {}

    def register(self, source: EnergySource) -> dict:
        """登记一个能源（来源仍归 DPAPI / 密钥池；本池只记引用）。"""
        if str(source.key_ref or "") and not str(source.key_ref).endswith(".dpapi"):
            return {"ok": False, "denied": True, "rule": "key_must_be_dpapi",
                    "source_id": source.source_id,
                    "why": "能源池只收 DPAPI 引用，不收明文密钥"}
        self.sources[source.source_id] = source
        return {"ok": True, "readonly": True, "source_id": source.source_id,
                "status": source.status}

    def pick(self, capability: str = "text", prefer: str = "免费"):
        """按需挑能源 —— **不挑食，但有优先级**；**没有可用能源就如实返回 None**。"""
        cap = str(capability or "text").strip()
        want = str(prefer or "免费").strip()
        candidates = [s for s in self.sources.values()
                      if cap in s.capability and s.status == "可用"]
        if not candidates:
            return None
        # 免费优先（**荤素之别，不是好坏之别**）
        return sorted(candidates, key=lambda s: s.grade != want)[0]

    def load_from_disk(self) -> dict:
        """把盘上的能源装配进来（动态读盘）。"""
        n = 0
        for s in build_sources():
            self.register(s)
            n += 1
        return {"ok": True, "readonly": True, "loaded": n}


class NativeDeriver:
    """**原生能力衍生器**：不是"用模型"，是"**用模型当燃料，生成自己的代码**"。"""

    # 生成的客户端必须走的统一出口（**原生路由**）
    ROUTE = "gbt_allinone.api"

    def derive_client_code(self, source: EnergySource) -> str:
        """按能源生成调用代码：**只用标准库**，且**必须走原生路由**。"""
        if source.status == "缺key":
            return ("# ⛔ 该能源缺 key（%s）⇒ **不生成调用代码**，如实报缺\n"
                    "# 能源：%s\nraise RuntimeError('no energy: %s')\n"
                    % (source.key_ref or "无 key_ref", source.source_id,
                       source.source_id))
        return (
            "# 由 NativeDeriver 生成（能源=%s · 等级=%s · 荤素=%s）\n"
            "# 只依赖 Python 标准库；**统一走原生路由**，不直连任何 SDK\n"
            "from %s import run_task\n\n"
            "def call(prompt: str) -> dict:\n"
            "    return run_task('llm_chat', {'prompt': prompt,\n"
            "                                 'energy': %r})\n"
            % (source.source_id, source.grade, source.kind,
               self.ROUTE, source.source_id)
        )

    def derive_video_pipeline(self, capability: str = "text") -> Dict:
        """按模型能力**衍生视频流水线蓝图**（文生视频 / 图生视频 / 视频续写）。"""
        cap = str(capability or "text").strip().lower()
        base = ("素材输入", "脚本/分镜", "关键画面", "视频生成", "质检与重跑", "成片")
        if cap in ("text", "t2v", "文生视频"):
            steps = ("提示词",) + base
        elif cap in ("image", "i2v", "图生视频"):
            steps = ("上传参考图(OSS)",) + base
        elif cap in ("video", "extend", "视频续写"):
            steps = ("上传已有视频(OSS)", "续写段规划") + base
        else:
            return {"ok": False, "denied": True, "rule": "unknown_capability",
                    "capability": cap,
                    "known": ["text/t2v", "image/i2v", "video/extend"],
                    "why": "盘上只知道这几种；别的**不硬凑蓝图**"}
        return {"ok": True, "readonly": True, "capability": cap,
                "steps": list(steps),
                "route": self.ROUTE,
                "note": "**组合出顶级成片**靠的是把这几步串起来，"
                        "不靠单一模型；成片好不好看**只能由人判**"}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / energies / redlines /
    check_identity / check_stack / check_code / lease。不调、不出网、不落盘。"""
    op = str(op or "status")
    if op == "status":
        return status()
    if op == "energies":
        return {"ok": True, "readonly": True, "energies": list_energies()}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES),
                "side_rules": list(SIDE_RULES)}
    if op == "check_identity":
        return check_identity_not_model(params.get("owner_ai_id") or "",
                                        params.get("known_models"))
    if op == "check_stack":
        return check_stack_unchanged(params.get("before"), params.get("after"))
    if op == "check_stack_four":
        return check_stack_four(params.get("before"), params.get("after"))
    if op == "native_stack":
        return {"ok": True, "readonly": True,
                "native_stack": [dict(x) for x in NATIVE_STACK],
                "redlines": [dict(x) for x in ENERGY_REDLINES],
                "note": "**原生栈 = 触手 + 记忆 + 门禁 + 审计**（换模型时四件一条不动）；"
                        "五条红线 5/5 已有闸"}
    if op == "check_code":
        return check_derived_code(params.get("source") or "")
    if op == "lease":
        return lease_energy(params.get("owner_ai_id") or "",
                            params.get("tentacle_id") or "energy")
    # ── R-H224 · 能源抽象层 + 原生能力衍生器 ──
    if op == "sources":
        srcs = build_sources()
        return {"ok": True, "readonly": True,
                "sources": [s.to_dict() for s in srcs], "count": len(srcs),
                "grades": list(GRADES), "kinds": list(KINDS),
                "statuses": list(STATUSES),
                "note": "**大脑只认 EnergySource，不认模型名**；"
                        "grade/kind 盘上无字段 ⇒ 一律「未知」，不编"}
    if op == "derive_code":
        srcs = {s.source_id: s for s in build_sources()}
        sid = str(params.get("source_id") or "").strip()
        if sid not in srcs:
            return {"ok": False, "denied": True, "rule": "unknown_source",
                    "source_id": sid, "known": sorted(srcs),
                    "why": "没有这个能源 ⇒ 不派生代码（**没能源如实报缺**）"}
        code = NativeDeriver().derive_client_code(srcs[sid])
        # **自洽带牙**：自己生成的代码，必须能过自己的红线③
        guard = check_derived_code(code)
        return {"ok": bool(guard.get("ok")), "readonly": True,
                "source_id": sid, "code": code, "self_check": guard,
                "note": "衍生代码**自检通过**才算产出（自己的红线自己先过）"}
    if op == "derive_pipeline":
        return NativeDeriver().derive_video_pipeline(params.get("capability") or "text")
    # ── R-H225 · 能源池（不挑食但有优先级）+ 视频自研八层图 ──
    if op == "pool":
        pool = EnergyPool()
        pool.load_from_disk()
        cap = params.get("capability") or "text"
        prefer = params.get("prefer") or "免费"
        got = pool.pick(cap, prefer)
        return {"ok": True, "readonly": True,
                "registered": sorted(pool.sources),
                "capability": cap, "prefer": prefer,
                "picked": (got.to_dict() if got else None),
                "note": "**不挑食**＝任何可用能源都能跑；"
                        "**荤素之别**＝免费/付费只是偏好，**不是能力差别**；"
                        "没有可用能源 ⇒ **返回 None（如实报缺）**"}
    if op == "self_dev_layers":
        return {"ok": True, "readonly": True,
                "layers": [dict(x) for x in SELF_DEV_LAYERS],
                "count": len(SELF_DEV_LAYERS),
                "vs_pipeline": list(SELF_DEV_DIFFS),
                "note": "八层图讲**自研边界**，六步讲**生产步骤** ⇒ "
                        "**两个维度并存，不合并**"}
    raise ValueError("未知 op %r（可用：status/energies/redlines/check_identity/"
                     "check_stack/check_code/lease/sources/derive_code/"
                     "derive_pipeline/pool/self_dev_layers/check_stack_four/"
                     "native_stack）" % (op,))


HONEST_BOUNDARY = (
    "能源池只保证『按需借、来源归池、没能源如实报缺、换能源不动原生栈』。"
    "它**不保证**：能源额度够用、免费能源真的免费（**免费/付费盘上没有该字段 ⇒ "
    "一律标 unknown**）、以及『有能源就出好片子』—— "
    "成片好不好看**只能由人判**（与『好看由人判』同源）。"
)
