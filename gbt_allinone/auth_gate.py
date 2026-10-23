"""GBT小土豆V8 · 人工授权门（Auth Gate）——被禁能力的硬性人工放行机制。

定位（Owner 定调 2026-09-11）：默认拒绝的能力不给 AI 绕过入口——
要放行只能由人亲手授权，AI 的任何调用路径（run_task / 工作流 / autopilot / 长程任务）
都无权创建授权。

授权的唯二来源：
  1. CLI 交互确认（auth grant 命令，终端人工输入 YES）
  2. 主人手写授权文件（store/auth_grants.jsonl 追加一行，格式严格校验）

授权纪律（**2026-09-25 Owner 令后分级**，改前是全体一次性消耗）：
  - **日常技术动作 = 时段授权**：TTL 内可多次用，用一次在账本里记一次（`used` /
    `last_used_at`）。为什么改：改前实测 `voice -> denied · 账本 0 行` —— 一次性消耗
    放在 audio_output / privacy_read 这类日常动作上，等于"每说一句话回终端敲一次 YES"，
    语音对讲在物理上不可用；而它挡的又不是危险动作，是主人自己的日常动作。
  - **危险动作 = 仍一次性消耗**：`owner_control`（总控钥匙）/ `deploy_publish` /
    `remote_device` / `data_export`，用掉即从账本删行。见 `ONE_SHOT_SCOPES`。
  - 过期自毁：过期授权在下次检查时自动清理
  - 全程留痕：发放/校验/消耗全部落审计（时段授权记 `mode=window` 与 `reuse_count`）
  - AI 无权发放：本模块没有任何可供 run_task 调用的"创建授权"入口
    —— **分级改的是"用几次"，没碰"谁能发"这条红线**

当前纳入授权门的作用域：
  osint_private   OSINT 扫描内网/保留地址（原 allow_private 直通开关废止）
"""
import json
import time
from pathlib import Path

from . import _paths

_BASE = Path(__file__).resolve().parent
_GRANTS = _paths.STORE_DIR / "auth_grants.jsonl"

SCOPES = {
    "osint_private": "OSINT 扫描自有内网/保留地址（一次性授权）",
    # 其余 13 项由 security/policy.py 的 SCOPE_DESCRIPTIONS 声明。历史上两次只改 policy、
    # 漏改本表 → 未注册作用域在 check_and_consume* 直接返回"未知授权作用域"，任何授权都
    # 满足不了 → 该能力对非主人调用者永久不可授权。
    #   2026-09-15 补 4 项（browser/desktop/external_llm/process_execute）
    #   2026-09-18 R113 补齐余下 9 项，并把空转的契约测试改成有牙版
    # 契约测试 test_policy_scopes_are_registered（真值取自 policy.SCOPE_DESCRIPTIONS）
    # + 变异负对照 test_policy_scope_registry_has_teeth 保证此处与 policy 不再漂移。
    # 2026-09-19 R-H98 修根源：本作用域此前是**纸面能力**——全仓只有这一行描述字符串，
    # check_and_consume_many 从不读它 ⇒ 主人发了也放行不了任何动作（与"门自己也要被验过"同型）。
    # 现按声明把它做成真的：本次动作缺任意作用域时，可用**一条** owner_control 顶掉**这一次**
    # （一次性消耗，审计记 substituted_for）。它不新增任何发放入口：仍然只能主人亲手发放。
    "owner_control": "主人总控授权：一条可替代该次动作所需的全部未授权作用域（一次性消耗）",
    "process_execute": "启动进程、执行命令或连接 MCP/终端服务器",
    "filesystem_write": "写入、移动、删除或自动整理文件",
    "remote_device": "启动/停止远程设备中继或外部接管通道",
    "deploy_publish": "部署、晋升、回滚或写入生产交付区",
    "deploy_force": "放行被门卡住的动作（未全绿晋升 / 未声明落点 / 公网中继）；专用一次性钥匙，每放一次要主人发一次",
    "network_private": "访问本机、内网、保留地址或非标准端口",
    "browser_control": "操控系统浏览器或自动化浏览器执行点击/输入",
    "desktop_control": "调用桌面触手的输入、鼠标、键盘与窗口控制能力",
    "device_control": "连接、写入或控制蓝牙及其他外部设备",
    "external_llm": "把当前任务数据发送到外部大模型服务",
    "data_export": "把数据发送到外部服务或持久化到框架外",
    "privacy_read": "读取屏幕、摄像头、麦克风或隐私载体",
    "audio_output": "让本机发声（TTS 合成/播放）或写入音频产物",
    #   2026-09-19 补 1 项（audio_output）—— 由契约测试 test_policy_scopes_are_registered 抓出：
    #   policy 声明了它却没注册，导致 voice.tts 对非主人调用者永久不可授权。
    "audit_read": "读取审计、授权或运行历史",
}
DEFAULT_TTL_S = 600   # 授权默认 10 分钟有效

# ── **只剩三道护栏**（Owner 2026-10-19 第二次重申，逐字：「我说了除了黑客全能力和转账要票
#    其他都去掉」；2026-09-23 原令：「除了设计好的三个人工授权其他限制都给我去掉」）
#
# 本集合就**是**"哪几件事还要主人发票"的白名单。不在里面的作用域，一律在
# `check_and_consume_many` 里**直接放行**（记 auto_passed，进审计），不再要票。
#   G1 黑客全能力（7）：browser_control 操控浏览器 · desktop_control 桌面输入 · device_control
#                      外设 · network_private 本机/内网/保留地址 · privacy_read 屏幕/摄像头/麦克风
#                      · process_execute 起进程/执行命令 · remote_device 远程接管通道
#   G2 转账/付款（3）：audio_output（常走外部语音服务）· data_export（出框架就可能计费）
#                      · external_llm（发外部大模型，按量计费）
#   G3 生产面板（2）：deploy_publish（部署/晋升/回滚）· deploy_force（强制放行专用钥匙）
# ⚠️ 这**不是**"AI 可以给自己发票"：SCOPES 与发放路径一个都没动，终端 YES 仍是唯一入口。
# ⚠️ 与本仓判据 `guardrail-check.py`（"护栏只有三道"）**同一口径** —— 那份打印的就是这 12 条；
#    两边必须一致，改一边就得改另一边（否则就是"门和判据各算各的"）。
ENFORCED_SCOPES = frozenset({
    # ① 黑客全能力
    "browser_control", "desktop_control", "device_control", "network_private",
    "privacy_read", "process_execute", "remote_device",
    # 2026-10-21 补（主人当场批准的那个词的**第二处**）：`osint_scan` 对私有网段声明的作用域是
    # `osint_private`（policy.py 的 `elif kind == "osint_scan": add("osint_private")`）。
    # 本集合里只有 `network_private` ⇒ 前者落进"非三道护栏"分支被**自动放行**，
    # 于是内网扫描不打票就能跑（实测 127.0.0.1 → ok）。两处名字必须同时认，门才算真的在。
    "osint_private",
    # ② 转账 / 付款
    "audio_output", "data_export", "external_llm",
    # ③ 生产面板
    "deploy_publish", "deploy_force",
})

# ── 作用域分级（Owner 2026-09-25 令：「改成时段授权：TTL 内可多次用，危险类保持一次性」）
#
# 分级只决定**一张授权能用几次**，不决定**谁能发**。发放入口一个都没变：
#   ① 终端交互确认（cli_grant_interactive，getpass 敲 YES）
#   ② 主人手写 store/auth_grants.jsonl
# 本文件里**没有**任何 run_task 可达的"创建授权"分支 —— 这是红线，改语义不许碰。
ONE_SHOT_SCOPES = {
    # 总控钥匙：一条顶掉该次动作**全部**缺失作用域。若变成时段，等于一把万能钥匙
    # 连开 10 分钟，比它顶掉的那几项各自时段化加起来还宽 —— 必须一次性。
    "owner_control",
    "deploy_publish",   # 写生产 / 晋升 / 回滚（不可逆）
    "deploy_force",     # 放行被门卡住的动作（未全绿晋升 / 未声明落点 / 公网中继）：每放一次要主人发一次
    "remote_device",    # 远控中继 / 外部接管通道
    "data_export",      # 数据出框架 / 出网（发出去就收不回）
}


def grant_mode(scope: str) -> str:
    """该作用域的授权模式：`one_shot`（用掉即失效）或 `window`（TTL 内可多次）。"""
    return "one_shot" if scope in ONE_SHOT_SCOPES else "window"


_NOTE_DENY = ("日常技术动作=时段授权（TTL 内可多次）· "
              "owner_control/deploy_publish/remote_device/data_export=一次性消耗；"
              "AI 调用路径无权自行发放")
_NOTE_STATUS = ("日常技术动作=时段授权（TTL 内可多次，用一次记一次）· "
                "危险作用域=一次性消耗（用掉即从账本删行）；AI 无权发放")

_OPERATOR_HUMAN = "human-terminal"
_OPERATOR_OWNER = "owner-manual"


# ── 授权门自己的审计降级：**不许无声**（2026-09-22 错报治理 · 第 31 条）──────────
# 本函数原来是 `except: pass` —— 于是「这次授权/拒绝没记上」**无人知道**：
# 授权账本看起来完整、实际缺行。**这是安全门上最重的一种错报。**
# 现在的口径：**仍然不抛**（门不能因为记账失败就崩），但**出声 + 可查**。
# ⚠️ 已知边界（留给主人定夺，不擅自改安全行为）：本仓对**有后果的动作**的既有规矩是
#    「主账本写不进去，就不许把后果动作放过去」（见 file_operation / coze_mail_cap 的同款注释）。
#    这里**没有**改成 fail-closed，因为那会让「store 不可写」直接等于「门永久拒绝一切」，
#    属于**行为变更**，须主人点头。
_AUDIT_DEGRADED = {"count": 0, "reasons": {}, "last_at": None}


def audit_degraded() -> dict:
    """只读：授权门记账降级的计数与原因。

    `count > 0` ⇒ **授权账本可能缺行** —— 这是必须被看见的读数，不是内部细节。
    """
    return {"ok": True, "readonly": True, "count": _AUDIT_DEGRADED["count"],
            "reasons": dict(_AUDIT_DEGRADED["reasons"]),
            "last_at": _AUDIT_DEGRADED["last_at"],
            "note": "count>0 ⇒ 有授权/拒绝事件未落账（授权账本可能缺行）"}


def _audit(event, meta):
    try:
        from .store import audit
        audit(event, meta)
    except Exception as _e:                     # noqa: BLE001
        import time as _t
        _AUDIT_DEGRADED["count"] += 1
        _AUDIT_DEGRADED["last_at"] = round(_t.time(), 3)
        _k = type(_e).__name__
        _AUDIT_DEGRADED["reasons"][_k] = _AUDIT_DEGRADED["reasons"].get(_k, 0) + 1
        if _AUDIT_DEGRADED["reasons"][_k] == 1:      # 同类只首次出声，避免刷屏淹掉真故障
            try:
                import sys as _s
                print("⚠️ auth_gate: 审计降级（%s: %s）⇒ 授权账本可能缺行（累计 %d 次）"
                      % (_k, str(_e)[:120], _AUDIT_DEGRADED["count"]), file=_s.stderr)
            except Exception:                        # noqa: BLE001
                pass


def _load_grants() -> list:
    """读全部授权行（容错：坏行跳过）。"""
    if not _GRANTS.exists():
        return []
    out = []
    for line in _GRANTS.read_text(encoding="utf-8").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            g = json.loads(line)
            if isinstance(g, dict) and g.get("id") and g.get("scope") in SCOPES:
                out.append(g)
        except Exception:
            continue
    return out


def _save_grants(grants: list):
    _GRANTS.parent.mkdir(parents=True, exist_ok=True)
    _GRANTS.write_text(
        "\n".join(json.dumps(g, ensure_ascii=False) for g in grants) + ("\n" if grants else ""),
        encoding="utf-8")


def _expire_stale(grants: list) -> list:
    now = time.time()
    alive = [g for g in grants if float(g.get("expires_at", 0)) > now]
    n_dead = len(grants) - len(alive)
    if n_dead:
        _save_grants(alive)
        _audit("auth_expired", {"cleaned": n_dead})
    return alive


def status() -> dict:
    """授权门状态：各作用域的可用授权数 + 授权模式（只读，不消耗）。"""
    grants = _expire_stale(_load_grants())
    by: dict[str, int] = {}
    used: dict[str, int] = {}
    for g in grants:
        scope = g["scope"]
        by[scope] = by.get(scope, 0) + 1
        used[scope] = used.get(scope, 0) + int(g.get("used", 0) or 0)
    return {
        "ok": True,
        "scopes": {k: {"desc": v, "grants_available": by.get(k, 0),
                       "mode": grant_mode(k),
                       # 时段授权会留在账本里，所以"已用几次"是必须看得见的读数
                       # （否则"还剩 1 张"读起来像"一次都没用过"）。
                       "used_total": used.get(k, 0)}
                   for k, v in SCOPES.items()},
        "one_shot_scopes": sorted(ONE_SHOT_SCOPES),
        "ai_can_grant": False,
        "grant_sources": ["CLI 交互确认（auth grant）", "主人手写 store/auth_grants.jsonl"],
        "note": _NOTE_STATUS,
    }


def check_and_consume(scope: str, detail: str = "") -> dict:
    """校验并放行一次授权。有匹配的未过期授权 → 放行；没有 → 拒绝（含人工指引）。

    这是授权门唯一的校验入口，供被门拦截的操作调用。
    """
    # 单作用域版与批量版**同一套语义**（含 owner_control 替代），不再各写一份实现。
    r = check_and_consume_many([scope], detail=detail)
    if not r.get("ok"):
        return r
    consumed = list(r.get("consumed") or [])
    rest = _expire_stale(_load_grants())
    return {"ok": True,
            "consumed": consumed[0] if consumed else None,
            "substituted_for": r.get("substituted_for") or [],
            "mode": grant_mode(scope),
            "remaining": sum(1 for x in rest if x["scope"] == scope)}


def check_and_consume_many(scopes, detail: str = "") -> dict:
    """批量校验并消耗授权（policy 层唯一入口）。

    语义：**全部满足才消耗，缺任意一个则一个都不消耗**——避免出现"消耗了 A 却因为缺 B
    被拒"的半消耗脏状态。成功返回被消耗的授权 id 列表与各作用域剩余数；失败返回缺失
    作用域列表与人工发放指引。
    """
    wanted: list[str] = []
    for scope in list(scopes or []):
        name = str(scope or "").strip()
        if name and name not in wanted:
            wanted.append(name)
    if not wanted:
        return {"ok": True, "consumed": [], "remaining": {}}

    # 🔴 2026-10-19（主人令，第二次重申，逐字）：「我说了除了黑客全能力和转账要票其他都去掉」
    #    ⇒ **只有三道护栏仍要票**，其余作用域在本层**直接放行**（不是删除作用域、不是改谁能发）。
    #    改在这里而不是逐个模块改：本函数是**授权门唯一的校验入口**，模块层的
    #    `check_and_consume("filesystem_write")` 也都汇到这里 ⇒ 一处收口，不会漏改一片。
    #    三道护栏对应关系（与判据 `护栏只有三道` 同一口径）：
    #      G1 黑客全能力 → privacy_read（看/听）· process_execute（起进程/执行/接管）
    #      G2 付款/计费  → external_llm（把数据发给外部大模型 = 花钱）
    #      G3 生产面板   → deploy_publish（部署/晋升/回滚）· deploy_force（强制放行钥匙）
    #    仍然**没有**任何 run_task 可达的"创建授权"分支：AI 依旧不能给自己发票。
    passed = [s for s in wanted if s not in ENFORCED_SCOPES]
    wanted = [s for s in wanted if s in ENFORCED_SCOPES]
    if not wanted:
        return {"ok": True, "consumed": [], "remaining": {}, "auto_passed": passed,
                "note": "非三道护栏作用域 ⇒ 按主人令直接放行（不发票）"}

    unknown = [s for s in wanted if s not in SCOPES]
    if unknown:
        return {
            "ok": False,
            "denied": True,
            "missing": unknown,
            "error": f"未知授权作用域: {unknown[0]}",
            "note": _NOTE_DENY,
        }

    available: dict[str, int] = {}
    for grant in _expire_stale(_load_grants()):
        scope = grant.get("scope")
        available[scope] = available.get(scope, 0) + 1

    missing = [s for s in wanted if available.get(s, 0) <= 0]
    if missing:
        # ── 总控替代（R-H98 修根源）──
        # 声明："一条 owner_control 可替代该次动作所需的全部未授权作用域（一次性）"。
        # 只有**缺件**时才动用它；有对应作用域授权时照旧逐条消耗，总控不被动。
        if available.get("owner_control", 0) > 0:
            current = _expire_stale(_load_grants())
            for index, grant in enumerate(current):
                if grant.get("scope") != "owner_control":
                    continue
                _save_grants(current[:index] + current[index + 1:])
                _audit("auth_consumed", {
                    "scope": "owner_control",
                    "grant_id": grant.get("id"),
                    "granted_at": grant.get("granted_at"),
                    "detail": str(detail)[:60],
                    "substituted_for": list(missing),
                })
                rest = _expire_stale(_load_grants())
                remaining: dict[str, int] = {}
                for g2 in rest:
                    remaining[g2["scope"]] = remaining.get(g2["scope"], 0) + 1
                return {"ok": True, "consumed": [grant.get("id")],
                        "substituted_for": list(missing), "remaining": remaining}
        _audit("auth_denied", {"scope": missing[0], "detail": str(detail)[:60],
                               "kind": (str(detail).split(":")[-1].strip() if ":" in str(detail) else ""),
                               "missing": missing})
        _mode = grant_mode(missing[0])
        return {
            "ok": False,
            "denied": True,
            "missing": missing,
            "error": f"需要人工授权（{missing[0]}）：{SCOPES[missing[0]]}",
            "mode": _mode,
            "how_to_grant": [
                f"终端运行: python -m gbt_allinone auth grant --scope {missing[0]} --ttl 600",
                "或主人手写 store/auth_grants.jsonl 追加一行（格式见 auth_gate.SCOPES 与 README）",
                ("该作用域是**时段授权**：一张在 TTL 内可反复用"
                 if _mode == "window" else
                 "该作用域是**一次性消耗**：用掉即从账本删行"),
            ],
            "note": _NOTE_DENY,
        }

    consumed: list[str] = []
    for scope in wanted:
        current = _expire_stale(_load_grants())
        for index, grant in enumerate(current):
            if grant.get("scope") != scope:
                continue
            if grant_mode(scope) == "one_shot":
                _save_grants(current[:index] + current[index + 1:])
                consumed.append(grant.get("id"))
                _audit("auth_consumed", {"scope": scope, "grant_id": grant.get("id"),
                                         "granted_at": grant.get("granted_at"),
                                         "detail": str(detail)[:60], "mode": "one_shot"})
            else:
                # 时段授权：**不从账本删行**，只把用量记进那一行。
                # 为什么记用量而不是静默复用：账本要能如实回答"这张授权被用了几回" ——
                # 一张 10 分钟授权反复放行了多少动作，是主人事后必须看得见的东西。
                reuse = int(grant.get("used", 0) or 0) + 1
                grant["used"] = reuse
                grant["last_used_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                current[index] = grant
                _save_grants(current)
                consumed.append(grant.get("id"))
                _audit("auth_consumed", {"scope": scope, "grant_id": grant.get("id"),
                                         "granted_at": grant.get("granted_at"),
                                         "detail": str(detail)[:60], "mode": "window",
                                         "reuse_count": reuse})
            break

    remaining: dict[str, int] = {}
    for grant in _expire_stale(_load_grants()):
        scope = grant.get("scope")
        remaining[scope] = remaining.get(scope, 0) + 1
    return {"ok": True, "consumed": consumed, "remaining": remaining}


# ── 仅 CLI（人工终端）可达的发放入口 ──

def cli_grant_interactive(scope: str, ttl: int = DEFAULT_TTL_S, purpose: str = "") -> dict:
    """CLI 交互式发放：必须有人在终端亲手输入确认（getpass 防脚本注入）。

    本函数只被 cli.py 的 auth grant 命令调用——run_task 路由里不存在任何通往此处的分支。
    """
    import getpass
    if scope not in SCOPES:
        return {"ok": False, "error": f"未知作用域: {scope}"}
    _m = grant_mode(scope)
    print(f"[授权请求] 作用域: {scope}")
    print(f"           内容: {SCOPES[scope]}")
    # 人在敲 YES 之前必须看清自己签的是哪种 —— 这正是交互确认存在的意义。
    print(f"           模式: " + ("一次性消耗（用掉即从账本删行）" if _m == "one_shot"
                                 else "时段授权（有效期内可反复用，用一次记一次）"))
    print(f"           有效期: {ttl}s | 发放后将落审计")
    try:
        answer = getpass.getpass("人工确认请输入 YES（直接回车取消）: ")
    except Exception:
        return {"ok": False, "error": "终端不可用——授权只能由人亲手发放"}
    if answer.strip() != "YES":
        _audit("auth_grant_aborted", {"scope": scope})
        return {"ok": False, "error": "未确认，授权取消"}
    return _append_grant(scope, _OPERATOR_HUMAN, ttl, purpose)


def _append_grant(scope: str, operator: str, ttl: int, purpose: str) -> dict:
    _m = grant_mode(scope)
    g = {
        "id": f"grant-{int(time.time()*1000)}",
        "scope": scope,
        "operator": operator,
        "purpose": str(purpose)[:120],
        "granted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "expires_at": round(time.time() + max(30, int(ttl)), 3),
        "mode": _m,
        # 时段授权的用量计数（一次性的一直是 0：它用完就整行没了）
        "used": 0,
    }
    grants = _load_grants()
    grants.append(g)
    _save_grants(grants)
    _audit("auth_granted", {"scope": scope, "operator": operator, "mode": _m,
                             "grant_id": g["id"], "ttl": ttl, "purpose": g["purpose"]})
    return {"ok": True, "grant_id": g["id"], "scope": scope, "mode": _m,
            "expires_at": g["expires_at"], "one_shot": _m == "one_shot"}
