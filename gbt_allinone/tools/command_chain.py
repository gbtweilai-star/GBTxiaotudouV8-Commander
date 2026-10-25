# gbt-capability: command_chain
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""指挥链（command_chain）· 总指挥参谋部 · 🥔GBT小土豆V8

主人令 2026-10-01：「全部统一品牌统一智能体以 GBT小土豆V8 为主延申，GBT小土豆V8 是以操控
智能体的总指挥来设计的。全局所有的智能体都必须：GBT小土豆V8 接收指令理解意图 → 大脑执行层
和上帝之眼给意见建议 → GBT小土豆V8 根据自己的决策生成最专业的提示词 → 让触手智能体去执行
专业工作。梳理工作不能重复和错误指挥。这里要设计好。」

════════════════════════════════════════════════════════════════════════
指挥链五段（**全部踩在已有件的肩上，不重造**）：

  ① 接令·理解意图   → `brain_exec.route`（大脑执行层·路由维：意图→能力语义路由+备选）
  ② 双顾问意见       → 大脑执行层读数（①本身）＋ `gods_eye`（顾问席机器可读 + 眼睛读数）
                       —— 分工口径 = 主人 2026-09-28 原话：Jev 决策 / Claude 意见建议 /
                          Codex 专注编程 / DSH 专注执行层
  ③ 总指挥决策       → **确定性合并**成工作单元清单（每单元：work_key/capability/执行席/顺序）；
                       **决策必须引用双顾问出处，缺一即红** —— 不许绕过顾问直接拍板
  ④ 专业提示词       → `prompt_bridge.compile_prompt`（四段：角色/目标/约束/输出格式，
                       带"原意保真"自检）
  ⑤ 触手智能体执行   → 分派台账（`commit` 只落账；**真正执行仍走各能力的门** run_task/confirm）

════════════════════════════════════════════════════════════════════════
两条铁律（做成判据，不是口号）：

  防重复：work_key 在同一计划内唯一 · 同 plan_hash 只许 commit 一次（重放拒绝）·
          开放分派中同 work_key 拒（不许两个执行体干同一件活）
  防错指挥：幽灵能力红（不在注册表）· 幽灵执行席红（不在名册）·
            决策缺双顾问出处红 · 侧效应能力必须带许可标签（owner 档 ⇒ "需主人授权"）
  不编（2026-10-01 评审加 · 决策采信闸）：造单只看**锚点** —— 指令点名在册 ∨ 主路
            语义路由判定 ∨ 触手本地方法路由自信命中；降级启发式的 2-gram 巧合与
            alternatives 清单**不是依据**（有锚点时只作备选单元）。没有锚点 ⇒
            **零工作单元 + 如实说明**；指令点名**不在册**的名字 ⇒ 如实报缺 +
            路由来源一概不采信（不许照不存在的名字猜）

本模块**只读 + 只追加自己的台账**：不执行任何能力位（执行走 api.run_task 的门）、
不出网、不碰密钥。`commit` 只把分派写进自己的台账（state/command_chain.jsonl）。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_LEDGER = _ROOT / "state" / "command_chain.jsonl"
_CAP_TAGS = _ROOT / "state" / "cap_tags.json"      # cap_tags.tags() 的生成物（许可标签读它的 tags 行）
_AGENTS_DIR = Path.home() / ".zcode" / "agents"

CAP_KIND = "command_chain"
DOMAIN = "mind"
CAP_TYPE = "internal"          # 内调型：给别的模块/面板用

# 总指挥品牌（唯一发令体）
COMMANDER = {"名": "GBT小土豆V8", "品牌": "🥔 GBT小土豆V8",
             "职权": ["接收指令", "理解意图", "听取顾问", "决策", "生成专业提示词", "向触手发令"],
             "决策权": "唯一（顾问只有建议权，无决策权）"}

# 执行席映射（域 → crew 智能体；**只映射盘上真实存在的**，缺了自动回落触手轮转）
_DOMAIN_AGENT = {
    "creation": "gbt-ig-visual", "design": "gbt-design-system", "media": "gbt-tiktok",
    "video": "gbt-tiktok", "engine": "gbt-dev-senior", "code": "gbt-codex",
    "security": "gbt-recon", "recon": "gbt-recon", "llm": "gbt-deepseek",
    "data": "gbt-db-tune", "mind": "gbt-framework", "system": "gbt-framework",
    "pipeline": "gbt-eng-practice", "tentacle": "gbt-framework",
    "social": "gbt-tiktok", "finance": "gbt-recon",
    # 2026-10-01 评审实测补缺项（**映射缺一项 ⇒ 整域回落裸触手轮转**）：
    #   `_agent_for('image_video', 3)` 出 T01（触手）—— 而 a1art_skill 这类是**创作侧
    #   出图**的活，应落 creation 档的 crew 智能体。只补「盘上真有、职责对得上」的三项：
    "image_video": "gbt-ig-visual",     # 创作侧出图（a1art_skill 等）
    "automation": "gbt-browser",        # browser / n8n_wf（gbt-browser.md = 浏览器全控）
    "framework": "gbt-framework",       # 本体能力位（gate_visibility 等）
}
_TENTACLES = ("T01", "T02", "T03")   # 触手名册（state/tentacle-roster.json：只有主人能改根数）


def _now() -> float:
    return time.time()


def _rel(p: Path) -> str:
    """台账展示用相对化；台账被指到仓外（测试隔离）时如实给全路径，不炸。"""
    try:
        return str(p.relative_to(_ROOT))
    except ValueError:
        return str(p)


def _import(dotted: str):
    """绝对导入助手：**两种加载方式通吃**（包内正常加载 / spec 直载文件）。
    血账 2026-10-01：相对导入 `from .. import x` 在 spec 直载下炸
    "attempted relative import with no known parent package" ⇒ 双顾问整段未读到。"""
    import sys
    import importlib
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    return importlib.import_module(dotted)


def _work_key(capability: str, instruction: str, order: int) -> str:
    """工作键：同一能力 + 同一指令 ⇒ 同一件活。防重复的锚点。（SHA-256，不用弱算法）"""
    raw = json.dumps([capability, " ".join(str(instruction).split()), order],
                     ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _agent_for(domain: str, order: int) -> dict:
    """执行席：域专属 crew 智能体优先（**盘上真有才用**），否则触手轮转
    （轮转时**如实写明是哪个域没有 crew 映射** —— 免得"落了裸触手"看不出来）。"""
    cand = _DOMAIN_AGENT.get(str(domain or ""), "")
    if cand and (_AGENTS_DIR / (cand + ".md")).is_file():
        return {"执行席": cand, "形态": "crew 智能体", "出处": f"~/.zcode/agents/{cand}.md"}
    t = _TENTACLES[order % len(_TENTACLES)]
    return {"执行席": t, "形态": "触手智能体",
            "出处": f"state/tentacle-roster.json（轮转：域 {str(domain or '—') or '—'} 无 crew 映射）"}


def _scope_note(capability: str) -> str:
    """许可标签（来自 cap_tags 的 owner/open 档）—— 防错指挥的第三只眼。
    读不到就如实"未读到"，不编。

    血账 2026-10-01（评审实测）：原实现读 `cap_tags.tags()` 的 `rows`/`items` —— 但
    `tags()` 是**生成器**，它落的 `state/cap_tags.json` 里按能力位存的是 **`tags` 行**
    （`{"<能力位>": {"permission": "owner"/"open", …}}`），`rows`/`items` 两个键根本不存在
    ⇒ 标签**恒落「未读到（不编）」**：owner 档的 redteam_recon 报不出「需主人授权」，
    open 档的 libtv_workflow/brain_unify 也报不出「走门即可」。
    改为：① 读生成物 `state/cap_tags.json` 的 `tags` 行（只读，不重新生成）；
    ② 生成物没有这行（新能力位）⇒ 现算兜底 `cap_tags.check(kind=…)`（只读判定）；
    ③ 两条都读不到才「未读到（不编）」。
    """
    row = None
    try:
        doc = json.loads(_CAP_TAGS.read_text(encoding="utf-8"))
        for key in ("tags", "rows", "items"):     # 兼容旧形状，但正身是 `tags`
            rows = doc.get(key)
            if isinstance(rows, dict) and capability in rows:
                row = rows[capability]
                break
    except Exception:                                        # noqa: BLE001
        row = None
    if row is None:                                          # 生成物没这行 ⇒ 现算（只读）
        try:
            row = _import("gbt_allinone.tools.cap_tags").check(kind=capability)
        except Exception:                                    # noqa: BLE001
            row = None
    if isinstance(row, dict):
        permit = str(row.get("permission") or row.get("permit") or row.get("档") or "")
        if permit:
            return ("open（走门即可）" if "open" in permit
                    else f"{permit}（需主人授权）")
    if isinstance(row, str):
        return row
    return "未读到（不编）"


# ═════════════════════ 段①②：意图 + 双顾问 ═════════════════════
def _stage_intent(instruction: str) -> dict:
    try:
        brain_exec = _import("gbt_allinone.brain_exec")
        r = brain_exec.route(instruction)
        r["_出处"] = "gbt_allinone/brain_exec.route（大脑执行层·路由维）"
        return r
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "未读到": f"brain_route 不可用：{type(e).__name__}: {e}"[:160],
                "_出处": "gbt_allinone/brain_exec.route"}


def _stage_advisors() -> dict:
    """双顾问：① 大脑执行层（读数即意见）② 上帝之眼（顾问席 + 眼睛）。只读，缺了如实报。"""
    out: dict = {}
    ge = _import("gbt_allinone.tools.gods_eye")
    try:
        adv = ge.advisors() or {}
        out["上帝之眼·顾问席"] = {k: {"角色": v.get("role"), "可": v.get("may"),
                                   "不可": v.get("may_not"), "在位": v.get("available")}
                                for k, v in (adv.get("advisors") or {}).items()}
        see = ge.see() or {}
        out["上帝之眼·眼睛"] = {"页面": f"{see.get('pages_ok')}/{see.get('pages_total')}",
                              "服务在听": see.get("services_up"),
                              "口径": see.get("_口径")}
        out["_出处_上帝之眼"] = "gbt_allinone/tools/gods_eye.py advisors()+see()"
    except Exception as e:                                   # noqa: BLE001
        out["上帝之眼·未读到"] = f"{type(e).__name__}: {e}"[:160]
    out["_出处_大脑执行层"] = "gbt_allinone/brain_exec（route 即执行层意见）"
    return out


# ═════════════════════ 段③：总指挥决策 ═════════════════════
def _named_caps(instruction: str) -> list:
    """**指令点名**：指令里字面提到的注册能力位（词边界匹配）。

    为什么要有这条：语义路由走 LLM（会预算降级/读不出），但**主人/面板经常直接点名**
    （「用 energy_pool 检查…」）。点名 = **读指令**，不是猜意图 —— 确定性、零依赖。
    """
    import re
    from gbt_allinone import caps_registry as cr
    hits = []
    for k in sorted(cr.BENIGN_CAPS):
        if re.search(r'(?<![A-Za-z0-9_])' + re.escape(k) + r'(?![A-Za-z0-9_])',
                     str(instruction or "")):
            hits.append(k)
    return hits


def _named_absent(instruction: str) -> list:
    """**点名不在册**：指令点名的、像能力位标识符、但注册表里没有的名字（负向点名）。

    为什么要有这条（2026-10-01 评审实测：`用 __no_such_cap__ 启动厨房机器人`）：
    正向点名（`_named_caps`）只认在册名 ⇒ 不在册的点名被**静默丢掉** —— 五段里没有一处
    写明"该名不在册"，语义模型就照着这个不存在的名字瞎猜（猜成 launch 触手方法），
    凑出指不回任何注册能力位的单元。**不许编**：锚点指不回注册能力位时必须如实报缺。

    形状从严（只认"像能力位标识符"的：双下划线 / 下划线蛇形），且必须在**点名框**里
    （「用/跑/调…」引出或反引号包住）—— 免得把普通英文词（python/ffmpeg）、文件名当成点名。
    """
    import re
    from gbt_allinone import caps_registry as cr
    text = str(instruction or "")
    out: list = []
    for pat in (r'(?<![A-Za-z0-9_.])(__[A-Za-z0-9][A-Za-z0-9_]*__)(?![A-Za-z0-9_.])',
                r'(?<![A-Za-z0-9_.])([A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]*[A-Za-z0-9])(?![A-Za-z0-9_.])'):
        for m in re.finditer(pat, text):
            tok = m.group(1)
            if tok in cr.BENIGN_CAPS or tok in out:
                continue
            head = text[max(0, m.start() - 3):m.start()]
            # 双下划线名本身就是"能力位标识符"的样子（真文件必带扩展名，已被上面的
            # 前瞻排除）⇒ 不再要求点名框；蛇形名必须在点名框里（用/跑/调…或引号）。
            if (tok.startswith("__") or head.endswith("`") or head.endswith("「")
                    or any(v in head for v in ("用", "跑", "调", "走", "拿", "按", "照", "带", "靠", "试", "启", "执", "过"))):
                out.append(tok)
    return out


def _route_read(route: dict) -> dict:
    """路由读数分类（**采信闸**：猜出来的不许当依据）。

    可采信（能当锚点）：① 主路语义路由判定（`best.via=semantic`）—— 路由权威；
                       ② 触手本地方法路由**自信**命中（`tentacle_route.confident=true`）——
                          确定性、零依赖，且它自己标了"这个结果有多虚"。
    只记账不采信：降级启发式的 best（字符 2-gram 巧合 —— 实测含糊指令「把一切变得更好」
                  靠 desc 里"把一"二字就能凑出 media_run/one_shot）· 路由备选清单
                  （恒为启发式打分）· 不自信的本地命中。
    """
    route = route if isinstance(route, dict) else {}
    best = route.get("best") if isinstance(route.get("best"), dict) else {}
    sem = route.get("semantic") if isinstance(route.get("semantic"), dict) else {}
    tent = route.get("tentacle_route") if isinstance(route.get("tentacle_route"), dict) else {}
    tent_method = str(tent.get("method") or "")
    trusted, untrusted, alts = [], [], []
    if str(best.get("via") or "") == "semantic" and best.get("kind"):
        trusted.append({"kind": str(best.get("kind")), "domain": str(best.get("domain") or ""),
                        "title": str(best.get("desc") or ""), "why": "主路语义路由判定（via=semantic）"})
    elif best.get("kind"):
        untrusted.append({"kind": str(best.get("kind")),
                          "why": "降级启发式命中（2-gram 巧合信号，不作为依据）"})
    if tent_method and tent.get("confident") is True:
        trusted.append({"kind": "tentacle", "domain": "tentacle",
                        "title": f"触手方法 {tent_method}（本地路由自信命中）",
                        "why": "触手本地方法路由（confident=true）"})
    elif tent_method:
        untrusted.append({"kind": "tentacle",
                          "why": f"触手本地方法路由命中但不自信（method={tent_method}，"
                                 f"confident={tent.get('confident')!r} ⇒ 不采信）"})
    for a in (route.get("alternatives") or [])[:2]:
        if isinstance(a, dict) and a.get("kind"):
            alts.append({"kind": str(a.get("kind")), "domain": str(a.get("domain") or ""),
                         "title": str(a.get("desc") or a.get("kind") or "")})
    return {"可采信": trusted, "不采信": untrusted, "备选": alts,
            "读数": {"path": route.get("path"), "degraded": route.get("degraded"),
                    "degraded_reason": route.get("degraded_reason") or route.get("未读到"),
                    "主路": {"method": sem.get("method"), "confidence": sem.get("confidence"),
                            "reason": sem.get("reason")},
                    "触手本地路由": {"method": tent.get("method"), "confident": tent.get("confident"),
                                 "candidates": tent.get("candidates")}}}


def _zero_note(named: list, absent: list, read: dict) -> str:
    """零单元的**如实说明**（不编：说不清凭什么派，就不派，并写清为什么）。"""
    r = read.get("读数") or {}
    tr = r.get("触手本地路由") or {}
    local = ("命中但不自信（method=%s，confident=%r ⇒ 不采信）" % (tr.get("method"), tr.get("confident"))
             if tr.get("method") else "0 候选")
    if absent:
        return ("指令点名的 %s 不在注册表（指不回任何能力位）⇒ 零工作单元；"
                "路由来源一概不采信（不许照不存在的名字猜）。要派活请点名在册能力位。"
                % "、".join(absent))
    return ("零工作单元（不编）：指令没点名在册能力位；主路读数 path=%s degraded=%s（%s）；"
            "触手本地路由 %s；降级启发式的 2-gram 命中与备选清单都不是依据 "
            "⇒ 没有可采信锚点就不派单。" % (r.get("path"), r.get("degraded"),
                                        str(r.get("degraded_reason") or "原因未读到")[:80], local))


def _learn_receipt(capability: str, instruction: str) -> dict:
    """**先学后做**（主人令 2026-10-01）：指挥链接令即学 —— 为工作单元自动抓核心资料、
    全文读完、复验新鲜，带回收据。抓不到料 ⇒ 如实记（材料数 0 不算失败）；
    导航不可用/材料缺盘 ⇒ 如实记（judges 的「学习账齐」会红，不许跳过）。"""
    try:
        import sys as _sys
        _cp = str(_ROOT / "tools" / "codex-scripts")
        if _cp not in _sys.path:
            _sys.path.insert(0, _cp)
        import omni_nav as _on
        mats = _on.materials_for(instruction, {"kind": capability}, _ROOT,
                                 docs_dir=_ROOT / "docs")
        g = _on.gate("command_chain:%s" % capability, mats, [capability])
        if not g.get("ok"):
            return {"状态": "fail-closed", "error": str(g.get("error"))[:160]}
        return {"状态": "已学", "材料数": g.get("learned_n", 0),
                "复用账": bool(g.get("reused")), "闸": g.get("gate"),
                "材料": [Path(m["path"]).name for m in (g.get("materials") or [])[:6]],
                "账": "state/omni_nav.jsonl"}
    except Exception as e:                                   # noqa: BLE001
        return {"状态": "不可用", "error": "%s: %s" % (type(e).__name__, str(e)[:100])}


def _decide(instruction: str, route: dict, advisors: dict) -> dict:
    """**确定性合并**（决策规则 · 2026-10-01 评审修两个缺口）：

    ① 指令点名的注册能力位（读指令，不是猜）——造单；
    ② **点名不在册** ⇒ 如实报缺 + 路由来源一概不采信（不许照不存在的名字猜）；
    ③ 路由来源过**采信闸**（`_route_read`）：主路语义判定 / 触手本地自信命中才算锚点；
       有锚点（点名在册 ∨ 可采信路由）时，路由最优 + 备选列入工作单元；
       **没有锚点 ⇒ 零工作单元 + 如实说明** —— 降级启发式的 2-gram 巧合与备选清单
       不是依据（实测含糊指令靠 desc 里"把一"二字就能凑出 media_run/one_shot，
       答不出「为什么是它」⇒ 不编）。
    每个工作单元**接令即学**（先学后做闸，带学习账）；决策依据**必须引用双顾问出处**
    （缺一 ⇒ judges.防错指挥 红）。
    """
    named = _named_caps(instruction)
    absent = _named_absent(instruction)
    read = _route_read(route)
    if absent:                                               # 点名不在册 ⇒ 路由猜测全不采信
        read = {**read, "可采信": [], "备选": [],
                "不采信": read["可采信"] + read["不采信"],
                "不采信原因": f"指令点名不在册（{'、'.join(absent)}）⇒ 路由来源一概不采信（不许编）"}
    from gbt_allinone import caps_registry as _cr
    units, order, seen = [], 0, set()

    def _add(k: str, title: str, dom: str, src: str) -> None:
        nonlocal order
        if not k or k in seen:
            return                                          # 防重复：同能力不重开单元
        seen.add(k)
        order += 1
        seat = _agent_for(str(dom or ""), order)
        units.append({"work_key": _work_key(k, instruction, order),
                      "order": order, "capability": k, "domain": str(dom or ""),
                      "title": str(title or "")[:80], "来源": src, **seat,
                      "学习账": _learn_receipt(k, instruction)})

    for k in named:                                          # ③-a 指令点名（确定性）
        spec = _cr.BENIGN_CAPS.get(k) or {}
        _add(k, "指令点名（字面点名）：" + str(spec.get("desc") or "")[:60],
             str(spec.get("domain") or ""), "指令点名（在册）")
    if not absent and (named or read["可采信"]):             # ③-b/③-c 有锚点才吃路由读数
        for s in read["可采信"]:
            _add(s["kind"], s["title"], s["domain"], s["why"])
        for a in read["备选"]:
            _add(a["kind"], a["title"], a["domain"], "路由备选（启发式；本单有锚点才列入）")
    decision = {"工作单元": units, "指令点名": named, "点名不在册": absent,
                "路由采信": read,
                "依据": {"大脑执行层": (route or {}).get("_出处")
                                or "gbt_allinone/brain_exec（route 即执行层意见；本次未读到）",
                        "上帝之眼": advisors.get("_出处_上帝之眼")
                                 or "gbt_allinone/tools/gods_eye（本次未读到）",
                        "口径": "决策 = 确定性合并（采信闸：指令点名 > 主路语义判定/触手本地自信命中；"
                                "降级启发式与备选清单不单独造单；无锚点或点名不在册 ⇒ 零单元 + 如实说明）；"
                                "主人的 Jev 决策引擎在 gods_eye.decide，需要时可作咨询档"}}
    if not units:
        decision["零单元说明"] = _zero_note(named, absent, read)
    return decision


# ═════════════════════ 段④：专业提示词 ═════════════════════
def _prompts(instruction: str, units: list) -> list:
    try:
        pb = _import("gbt_allinone.prompt_bridge")
    except Exception as e:                                   # noqa: BLE001
        return [{"错误": f"prompt_bridge 不可用：{e}"[:120]}]
    out = []
    n = len(units) or 1
    for u in units:
        raw = (f"作为 {u.get('执行席')}（GBT小土豆V8 指挥链第 {u.get('order')}/{n} 号工作单元），"
               f"执行：{instruction}。本单元能力位：{u.get('capability')}"
               f"（{u.get('title')}）。产出必须可验收、带读数出处。")
        r = pb.compile_prompt(raw)
        out.append({"work_key": u["work_key"], "ok": r.get("ok"),
                    "prompt": r.get("prompt") or "", "四段自检": r.get("missing") == []})
    return out


# ═════════════════════ 判据（防重复 / 防错指挥）═════════════════════
def _judges(plan: dict, ledger: list) -> dict:
    units = (plan.get("决策") or {}).get("工作单元") or []
    keys = [u.get("work_key") for u in units]
    caps = [u.get("capability") for u in units]
    agents = [u.get("执行席") for u in units]
    依据 = ((plan.get("决策") or {}).get("依据") or {})

    cr = _import("gbt_allinone.caps_registry")
    ghosts_cap = sorted({c for c in caps if c not in cr.BENIGN_CAPS})

    roster_names = set(_TENTACLES)
    try:
        for p in _AGENTS_DIR.glob("*.md"):
            roster_names.add(p.stem)
    except OSError:
        pass
    ghosts_agent = sorted({a for a in agents if a not in roster_names})

    dup_keys = sorted({k for k in keys if keys.count(k) > 1})
    open_keys = {str(r.get("work_key")) for r in ledger
                 if r.get("type") == "commit" and r.get("status") == "已分派"}
    overlap_open = sorted({k for k in keys if k in open_keys})

    citations_ok = bool(依据.get("大脑执行层")) and bool(依据.get("上帝之眼"))
    # 先学后做（主人令 2026-10-01）：每个工作单元必须带**已学**的学习账（不许跳过）。
    learn_missing = sorted({u.get("capability") for u in units
                            if (u.get("学习账") or {}).get("状态") != "已学"})

    return {
        "防重复": {"work_key 唯一": not dup_keys, "重复键": dup_keys,
                 "plan_hash 幂等": True,   # commit 时再对账（重放拒绝在那里执行）
                 "开放分派互斥": not overlap_open, "与开放分派撞键": overlap_open},
        "防错指挥": {"幽灵能力": ghosts_cap, "幽灵执行席": ghosts_agent,
                   "双顾问出处齐": citations_ok,
                   "学习账齐（先学后做）": not learn_missing,
                   "学习账缺/坏": learn_missing,
                   "许可标签": {u["work_key"]: _scope_note(u["capability"]) for u in units}},
        "通过": (not dup_keys and not overlap_open and not ghosts_cap
                 and not ghosts_agent and citations_ok and not learn_missing),
    }


# ═════════════════════ 主操作 ═════════════════════
def plan(instruction: str = "", **_kw) -> dict:
    """**全链只读推演**：①意图 → ②双顾问 → ③决策 → ④提示词 → ⑤分派预案。
    不执行任何能力位；执行走各能力的门。"""
    instruction = str(instruction or "").strip()
    if not instruction:
        return {"ok": False, "fail_closed": True,
                "error": "指令为空 —— 总指挥不猜意图（fail-closed）"}
    t0 = _now()
    route = _stage_intent(instruction)
    advisors = _stage_advisors()
    decision = _decide(instruction, route, advisors)
    units = decision.get("工作单元") or []
    prompts = _prompts(instruction, units)
    plan_hash = hashlib.sha256(json.dumps(
        [[u.get("work_key"), u.get("capability"), u.get("执行席")] for u in units],
        ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    ledger = _read_ledger()
    judges = _judges({"决策": decision}, ledger)
    out = {"ok": True, "op": "plan", "总指挥": COMMANDER["名"],
            "instruction": instruction, "plan_hash": plan_hash,
            "stages": {"①意图": route, "②双顾问": advisors,
                       "③决策": decision, "④专业提示词": prompts,
                       "⑤分派预案": [{"work_key": u["work_key"], "capability": u["capability"],
                                    "执行席": u.get("执行席"), "顺序": u.get("order"),
                                    "来源": u.get("来源"),
                                    "许可": _scope_note(u["capability"]),
                                    "学习账": (u.get("学习账") or {}).get("材料数", "—"),
                                    "学习账状态": (u.get("学习账") or {}).get("状态")}
                                   for u in units]},
            "judges": judges,
            "只读": True,
            "执行纪律": "commit 只落分派台账；真正执行仍走各能力的门（run_task/confirm）",
            "耗时秒": round(_now() - t0, 1),
            "_口径": "每段带出处；judges.通过=False 时 commit 会拒绝；"
                     "零工作单元时 ③决策.零单元说明 写明为什么（不编、不硬凑）"}
    if not units and decision.get("零单元说明"):
        out["零单元说明"] = decision["零单元说明"]             # 顶层也露一次，免得埋在段里没人看
    return out


def commit(plan: dict | None = None, **_kw) -> dict:
    """把 `plan()` 的产出**落成分派台账**（只追加；执行仍走各能力的门）。
    三道闸：① plan_hash 必须与工作单元重算一致（防篡改）；② 同 plan_hash 拒重放；
    ③ 开放分派同 work_key 拒（防重复）。"""
    if not isinstance(plan, dict) or not (plan or {}).get("stages"):
        return {"ok": False, "fail_closed": True,
                "error": "缺 plan（先跑 op=plan 拿全链推演，再原样传入 commit）"}
    units = ((plan.get("stages") or {}).get("③决策") or {}).get("工作单元") or []
    if not units:
        return {"ok": False, "fail_closed": True, "error": "plan 里没有工作单元"}
    plan_hash = hashlib.sha256(json.dumps(
        [[u.get("work_key"), u.get("capability"), u.get("执行席")] for u in units],
        ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    if str(plan.get("plan_hash") or "") != plan_hash:
        return {"ok": False, "fail_closed": True,
                "error": f"plan_hash 不一致（{plan.get('plan_hash')} ≠ 重算 {plan_hash}）—— 防篡改闸"}
    ledger = _read_ledger()
    if any(r.get("type") == "commit" and r.get("plan_hash") == plan_hash for r in ledger):
        return {"ok": False, "fail_closed": True, "error": "同一 plan_hash 已 commit 过（重放拒绝）"}
    open_keys = {str(r.get("work_key")) for r in ledger
                 if r.get("type") == "commit" and r.get("status") == "已分派"}
    dup = sorted({u["work_key"] for u in units if u["work_key"] in open_keys})
    if dup:
        return {"ok": False, "fail_closed": True,
                "error": f"与开放分派撞键（防重复）：{dup}"}
    j = _judges({"决策": (plan.get("stages") or {}).get("③决策") or {}}, ledger)
    if not j.get("通过"):
        return {"ok": False, "fail_closed": True, "error": "judges 未过（防错指挥）", "judges": j}
    _append({"type": "commit", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "plan_hash": plan_hash, "instruction": str(plan.get("instruction") or "")[:200],
             "status": "已分派",
             "work_units": [{"work_key": u["work_key"], "capability": u["capability"],
                             "执行席": u.get("执行席"), "顺序": u.get("order"),
                             "许可": _scope_note(u["capability"])} for u in units]})
    return {"ok": True, "op": "commit", "plan_hash": plan_hash,
            "分派": len(units), "台账": _rel(_LEDGER),
            "纪律": "分派 ≠ 执行：每个能力位的真正执行仍走 run_task 的门与确认"}


def close(work_key: str = "", note: str = "", **_kw) -> dict:
    """把一个工作单元标记完成（防重复判据据此释放该工作键）。"""
    wk = str(work_key or "").strip()
    if not wk:
        return {"ok": False, "fail_closed": True, "error": "缺 work_key"}
    ledger = _read_ledger()
    hit = [r for r in ledger if r.get("type") == "commit" and r.get("status") == "已分派"
           and any(u.get("work_key") == wk for u in (r.get("work_units") or []))]
    if not hit:
        return {"ok": False, "error": f"开放分派里没有 {wk}"}
    _append({"type": "close", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "work_key": wk, "note": str(note or "")[:160]})
    return {"ok": True, "op": "close", "work_key": wk}


def assignments(**_kw) -> dict:
    """分派台账现读（追加式；最新的在前）。"""
    rows = list(reversed(_read_ledger()))
    return {"ok": True, "op": "assignments", "count": len(rows), "rows": rows[:50],
            "台账": _rel(_LEDGER)}


def roster(**_kw) -> dict:
    """**统一智能体名册**（统一品牌：全员挂 GBT小土豆V8 指挥体系）。"""
    advisors = {}
    ge = _import("gbt_allinone.tools.gods_eye")
    try:
        adv = ge.advisors() or {}
        advisors = {k: {"品牌": "GBT小土豆V8 · 顾问席", "角色": v.get("role"),
                        "在位": bool(v.get("available")),
                        "决策权": "无（顾问只有建议权）"}
                    for k, v in (adv.get("advisors") or {}).items()}
    except Exception as e:                                   # noqa: BLE001
        advisors = {"未读到": str(e)[:120]}
    crew = []
    try:
        for p in sorted(_AGENTS_DIR.glob("*.md")):
            crew.append(p.stem)
    except OSError:
        pass
    return {"ok": True, "op": "roster", "品牌": COMMANDER["品牌"],
            "总指挥": COMMANDER,
            "顾问席": {"大脑执行层": {"品牌": "GBT小土豆V8 · 顾问席",
                                 "意见": "brain_exec.route 读数（执行层意见）",
                                 "决策权": "无（顾问只有建议权）"},
                      **advisors},
            "执行席": {"触手智能体": list(_TENTACLES),
                     "crew 智能体": crew,
                     "口径": "触手 = state/tentacle-roster.json（只有主人能改根数）；"
                             "crew = ~/.zcode/agents/*.md 现读"},
            "_口径": "全员以 GBT小土豆V8 为唯一总指挥延申：顾问只有建议权、决策权在总指挥、"
                     "执行席只接总指挥生成的专业提示词"}


def status(**_kw) -> dict:
    ledger = _read_ledger()
    # 开放工作键 = 已分派 − 已收口（台账只追加，净额现算）
    committed = {str(u.get("work_key")) for r in ledger
                 if r.get("type") == "commit" and r.get("status") == "已分派"
                 for u in (r.get("work_units") or [])}
    closed = {str(r.get("work_key")) for r in ledger if r.get("type") == "close"}
    open_units = sorted(committed - closed)
    return {"ok": True, "op": "status", "总指挥": COMMANDER["名"],
            "台账条数": len(ledger), "开放工作键": open_units,
            "判据": {"防重复": "work_key 唯一 · plan_hash 幂等 · 开放分派互斥",
                    "防错指挥": "幽灵能力/幽灵执行席/缺双顾问出处 全红"},
            "_口径": "链路五段全踩已有件：brain_route / gods_eye / prompt_bridge / 触手名册"}


# ── 台账（追加式）───────────────────────────────────────────────
def _append(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


def _read_ledger() -> list:
    if not _LEDGER.is_file():
        return []
    rows = []
    for line in _LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def run(op: str = "status", **params) -> dict:
    op = (op or "status").strip().lower()
    fn = {"plan": plan, "commit": commit, "close": close,
          "assignments": assignments, "roster": roster, "status": status}.get(op)
    if fn is None:
        return {"ok": False, "fail_closed": True,
                "error": f"未知 op:{op}（plan/commit/close/assignments/roster/status）"}
    return fn(**params)


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": CAP_KIND, "tentacle": "command_chain",
            "entry": "run_task('command_chain', {'op':'plan','instruction':'…'})",
            "ops": ["plan", "commit", "close", "assignments", "roster", "status", "where"],
            "chain": "①意图(brain_route) → ②双顾问(大脑执行层+上帝之眼) → ③总指挥决策 → "
                     "④专业提示词(prompt_bridge 四段) → ⑤触手智能体分派台账",
            "指挥体系": {"总指挥": "GBT小土豆V8（唯一决策与发令）",
                       "顾问席": "大脑执行层 + 上帝之眼（克劳德/Jev/Codex/DSH 按主人 9-28 口径）",
                       "执行席": "触手 T01-T03 轮转 + crew 智能体（~/.zcode/agents 现读）"},
            "files": {"台账": "state/command_chain.jsonl"}}
