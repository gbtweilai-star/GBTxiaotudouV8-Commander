# gbt-capability: dynamic-import
"""能力风险策略：保留全部能力，给高风险动作增加主人会话与一次性授权边界。

策略原则：
- 默认读取、健康检查、公开网络抓取继续直接可用；
- 命令执行、文件写入、远程接管、发布晋升、私有网络、浏览器操控、设备写入、
  外部 LLM 数据交换等动作，在主人本机会话中直接执行，在未受信路径中必须消耗人工授权；
- 授权只由 CLI 交互或主人手写授权文件发放，run_task 本身不能创建授权。
"""
from __future__ import annotations

import contextlib
import contextvars
import os
import urllib.parse
from dataclasses import dataclass, field
from typing import Iterator

from . import net_guard

_TRUSTED_OWNER = contextvars.ContextVar("gbt_trusted_owner", default=False)

SCOPE_DESCRIPTIONS = {
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
    "audit_read": "读取审计、授权或运行历史",
    "audio_output": "让本机发声（TTS 合成/播放）或写入音频产物",
}

_READ_ONLY_TENTACLE = {
    "", "status", "eye", "see", "vision_snapshot", "screen_size", "screenshot_diff",
    "read_text", "list_windows", "process_list", "see_active_window", "window_list",
    "window_info", "active_window", "monitor", "detect", "ocr", "manifest",
}

_READ_ONLY_DC_TOOLS = {
    "get_config", "get_prompts", "read_file", "read_multiple_files", "list_directory",
    "get_file_info", "list_processes", "list_sessions", "get_usage_stats",
    "get_recent_tool_calls", "get_more_search_results", "list_searches",
}

_READ_ONLY_NATIVE_BROWSER_ACTIONS = {
    "status", "list_tabs", "get_title", "get_url", "get_text", "dom_query",
    "get_cookies", "intercept_events", "intercept_status",
}

_DC_WRITE_TOOLS = {
    "set_config_value", "write_file", "write_pdf", "create_directory", "move_file",
    "edit_block",
}

_DC_PROCESS_TOOLS = {
    "start_process", "read_process_output", "interact_with_process", "force_terminate",
    "kill_process", "start_search", "stop_search",
}


@dataclass(frozen=True)
class PolicyDecision:
    kind: str
    risk: str = "low"
    scopes: tuple[str, ...] = ()
    action: str = ""
    allow_private: bool = False
    details: dict = field(default_factory=dict)

    @property
    def restricted(self) -> bool:
        return bool(self.scopes)


def owner_session() -> contextlib.AbstractContextManager:
    """标记主人的本地可信会话；仅 CLI、GUI 和已鉴权本地服务应进入。"""
    return _owner_session()


@contextlib.contextmanager
def _owner_session() -> Iterator[None]:
    token = _TRUSTED_OWNER.set(True)
    try:
        yield
    finally:
        _TRUSTED_OWNER.reset(token)


def is_trusted() -> bool:
    if _TRUSTED_OWNER.get():
        return True
    return (os.environ.get("GBT_OWNER_SESSION") or "").strip() in ("1", "true", "yes", "on")


# ── 自主长线任务 · 自行判断授权（主人 2026-10-17 令）────────────────────────────
# 主人原话（逐字）：「门在自主长线任务的时候除了转账，黑客能力，其他皆可GBT小土豆V8判断点授权」
AUTONOMOUS_ENV = "GBT_AUTONOMOUS"
MONEY_KINDS = frozenset({"transfer"})          # 转账类：**仍要主人**（钱不能让她自己拍）
_DEFENSIVE_SECURITY = frozenset({              # security 域里这些是"防御/登记"面，不算黑客能力
    "event_ledger", "review_gate", "policy_delta", "hook_enforcer",
    "omission_detector", "onboarding_gate", "sec_defenses",
})


def autonomous_enabled() -> bool:
    return (os.environ.get(AUTONOMOUS_ENV) or "").strip() in ("1", "true", "yes", "on")


def _hacker_kinds() -> set:
    """黑客能力位 = security 域全部进攻面（动态现读名册，去掉防御/登记面）；读不到就保守返回空集。"""
    try:
        from ..caps_registry import BENIGN_CAPS
    except Exception:                                            # noqa: BLE001
        return set()
    return {k for k, v in (BENIGN_CAPS or {}).items()
            if (v or {}).get("domain") == "security"} - _DEFENSIVE_SECURITY


def autonomous_exclusion(kind: str) -> str:
    """返回**不可自行授权**的原因（空串 = 可自授）。"""
    k = str(kind or "")
    if k in MONEY_KINDS:
        return "转账类动作（钱）：必须主人授权"
    if k in _hacker_kinds():
        return "黑客能力：必须主人授权"
    return ""


def autonomous_self_judgment(kind: str, scopes) -> tuple:
    """(可否自授, 原因)。仅 `GBT_AUTONOMOUS=1` 时可能返回 True。"""
    if not autonomous_enabled():
        return False, ""
    why = autonomous_exclusion(kind)
    if why:
        return False, why
    if not list(scopes or ()):
        return False, ""
    return True, ("GBT小土豆V8 自行判断授权（主人 2026-10-17 令：自主长线任务里除转账/黑客能力外）")


def _audit_autonomous(kind: str, scopes, action: str, reason: str) -> None:
    """落审计：自授权**必须留痕**（谁授的、什么动作、哪些作用域）。审计写不进也不阻断，但要如实记。"""
    try:
        from ..store import audit
        audit("autonomous_authorized", {"kind": kind, "scopes": list(scopes or ()),
                                        "action": action, "by": "GBT小土豆V8", "reason": reason})
    except Exception:                                            # noqa: BLE001
        pass


def _url_params(payload: dict) -> list[str]:
    return [str(payload.get(k) or "") for k in ("url", "target", "base_url", "repo") if payload.get(k)]


def _needs_private_network(payload: dict) -> bool:
    for raw in _url_params(payload):
        if not raw:
            continue
        parsed = raw if "://" in raw else "https://" + raw
        try:
            net_guard.validate_url(str(parsed), allow_private=False)
        except net_guard.NetworkGuardError as exc:
            text = str(exc)
            if "非公网地址" in text or "端口" in text:
                return True
    return False


def evaluate(kind: str, payload: dict | None = None) -> PolicyDecision:
    p = dict(payload or {})
    op = str(p.get("op") or p.get("action") or p.get("method") or "").lower()
    scopes: list[str] = []
    risk = "low"
    action = op or kind
    allow_private = False
    details: dict = {}

    # 🔴 2026-10-19 主人令（逐字）：「除了设计好的三个人工授权其他限制都给我去掉」。
    #    收口点就在这一个 add() 上：只有"三道护栏"对应的作用域还会被记成"需要人工授权"；
    #    其余机制层作用域不再要票（filesystem_write / process_execute / audio_output /
    #    browser_control / device_control / network_private …）。
    #    三道护栏一个不少：G1 黑客(privacy_read/desktop_control/osint_private/remote_device)
    #    · G2 付款(external_llm/data_export) · G3 生产面板(deploy_publish/deploy_force)。
    #    怎么回滚：py -3.14 -X utf8 tools/codex-scripts/relax-gates-20261019.py --rollback
    # 机制层自我保护：**要票**，但不归三道护栏（主人 2026-10-19 核实：
    # 上一版白名单过滤器把 filesystem_write 吃掉了 ⇒ 全仓 10+ 处 add 空转）。
    MECHANISM_GATES = {"filesystem_write"}
    HUMAN_GATES = {
        # ── 主人 2026-10-19 正表（真源：guardrail-check.py 文件头 2026-10-10 主人令）──
        # G1 黑客全能力
        "process_execute", "remote_device", "network_private", "browser_control",
        "desktop_control", "device_control", "privacy_read",
        # 2026-10-21 补（主人当场批准）：本表原写 `network_private`，而 `osint_scan` 分支
        # add 的是 `osint_private` —— 两个名字都在作用域表里，但 add() 只认白名单里的名字，
        # 于是内网扫描那道护栏**被静默放行**（实测：target=127.0.0.1 直接 ok）。
        # 上面第 190 行的设计注释本来就写着 G1 应含 `osint_private` ⇒ 这次是**把门补上**，
        # 不是放宽；四条判据（auth_gate_flow / osint_guard / sec_defenses·net_guard /
        # longrun_escalate）此前一直红，根因就是这一个词。
        "osint_private",
        # G2 付款
        "external_llm", "data_export", "audio_output",
        # G3 生成代码禁入生产面板
        "deploy_publish", "deploy_force",
        # 通道件（它是授权本身，不是第四道）
        "owner_control",
        # ⚠️ 上一版漏了 process_execute/browser_control/device_control/network_private/audio_output，
        #    等于把 G1 与 G2 人工授权一起撤掉；2026-10-19 按正表补齐（备份见 state/authz-relax-20261019/）。
    }

    def add(*items: str) -> None:
        nonlocal risk
        for item in items:
            if item and (item in HUMAN_GATES or item in MECHANISM_GATES) and item not in scopes:
                scopes.append(item)
        if any(x in scopes for x in (
            "remote_device", "process_execute", "filesystem_write", "deploy_publish",
            "network_private", "browser_control", "desktop_control", "device_control",
            "external_llm", "data_export",
        )):
            risk = "high"
        elif scopes:
            risk = "medium"


    # ── 主人 2026-10-19「最终答复」：三处同型兜底 + 未知 kind 写动词兜底 ──
    # 1) record_grid：补**真票**（通用写）。只读侧黑名单放行，其余一律要票。
    if kind == "record_grid":
        if op not in ("", "parse", "read", "preview", "status"):
            add("filesystem_write")
    # 2) stigmergy：**不碰 DEPOSIT**。它是有闸的追加口（目标固定/只追加/调用方传不了路径），
    #    是这一族口径的源头（ledger_note 原话「对齐盘上 stigmergy 的先例」）。
    #    真正不一致的是：ledger_note 有兜底，而它和 event_ledger 没有 ⇒ 这里补的只是兜底。
    if kind == "stigmergy":
        if op.upper() not in ("", "READ", "FORAGE", "STATUS", "DEPOSIT", "DECAY"):   # op 在上游已转小写 => 这里必须大小写无关
            add("filesystem_write")
    # 3) event_ledger：同样只补兜底
    if kind == "event_ledger":
        if op not in ("", "read", "list", "status", "verify", "append"):
            add("filesystem_write")
    # 4) 未知 kind：只扣高风险动词（不一刀切 fail-closed —— 那会把既有 kind 打红）
    _WRITE_VERBS = {"write", "apply", "commit", "push", "delete", "move",
                    "emit", "append", "deposit", "update", "patch"}
    try:
        # 🔴 2026-10-19 修（本条兜底从上线起就没生效过，两处错叠在一起）：
        #    ① 相对路径写错：policy.py 在 `gbt_allinone/security/` 里，写成 `.caps_registry`
        #       会去 `gbt_allinone.security.caps_registry` 找 ⇒ **ImportError 被 except 吞掉**；
        #    ② 表名也错：注册表里装能力位的是 `BENIGN_CAPS`，`CAPS` 是空字典。
        #    两处一叠 ⇒ `_KNOWN_KINDS` 恒为空 ⇒ **每个 kind 都被当"未知"**，任何名字叫
        #    move/apply/emit 的 op 都被扣 filesystem_write。实证：`tentacle_arm {"op":"move"}`
        #    只是"逐关节调一个只读位"，却被要求写盘票（读数：scopes=('filesystem_write',)）。
        #    ③（第三处，一并修）`CAPS` 这个名字在注册表里**根本不存在**，硬 import 会连累
        #       整个 except 分支 ⇒ 即使修好相对路径仍是空集。改成**逐个取**、谁在就收谁。
        from .. import caps_registry as _R
        _KNOWN_KINDS = set(getattr(_R, "CAPS", None) or {}) | set(getattr(_R, "BENIGN_CAPS", None) or {})
    except Exception:
        _KNOWN_KINDS = set()
    if (kind not in _KNOWN_KINDS and kind not in ("record_grid", "stigmergy", "event_ledger", "ledger_note") and str(op).lower() in _WRITE_VERBS):
        add("filesystem_write")

    if kind == "coze_mail":
        # R104 · 刀一（通信域）：对外发信 / 在自有账号下立地址 = data_export（收紧）；
        # status/inbox/search/read/mark/draft 是只读侧，不收口 —— 与仓库既有
        # 「写操作收紧、读不收紧」口径一致。
        if op in ("send", "reply", "register"):
            add("data_export")
    if kind == "create":
        # R104 · 刀二（创作出口）：写进 outputs/ = filesystem_write（收紧）；
        # status/configure/intent/output 不收口 —— 文本出口本刀**未接线**、不出网，
        # 故不挂 data_export（真接线那一刀再单独收紧）。
        if op == "write":
            add("filesystem_write")
    if kind == "mcp_connect":
        add("process_execute")
    elif kind == "mcp_call":
        add("process_execute")
    elif kind == "desktop_commander":
        op = op or "status"
        if op == "connect":
            add("process_execute")
        elif op in ("remote_start", "remote_stop"):
            add("remote_device")
        elif op == "call":
            tool = str(p.get("tool") or "")
            details["tool"] = tool
            if tool in _DC_WRITE_TOOLS:
                add("filesystem_write")
            elif tool in _DC_PROCESS_TOOLS:
                add("process_execute")
            elif tool not in _READ_ONLY_DC_TOOLS:
                # 同上（主人令 2026-10-09）：桌面触手凡落点动作，**看**与**动**必须同时具备。
                add("desktop_control", "privacy_read")
    elif kind == "tentacle":
        if op not in _READ_ONLY_TENTACLE:
            # 🔴 2026-10-09 主人令「为什么她的视觉每次都要**跟手分开**去使用传统的**瞎子操作**？
            #    把视觉这么使用给她**钉死在上面**，别再使用传统瞎子操作」：
            #    原来这里**只加 desktop_control**（手），不加 privacy_read（眼）⇒
            #    **看不到也能动手** = 瞎子操作。这是本仓唯一还留着的这类缝。
            #    钉死：凡落点动作（要动键鼠/窗口）**必须同时**具备"看"的票 ——
            #    **没有眼睛就没有手**（与 omni_plug 的 app 插座口径一致）。
            add("desktop_control", "privacy_read")
    elif kind == "browser":
        op = op or "open"
        if op in ("native", "deep", "controller", "cdp"):
            action = str(p.get("action") or p.get("cmd") or "status").lower()
            if action not in _READ_ONLY_NATIVE_BROWSER_ACTIONS:
                add("browser_control")
            if action == "screenshot":
                add("filesystem_write")
            if action == "get_cookies" and bool(p.get("include_values")):
                add("privacy_read")
            if _needs_private_network(p):
                add("network_private")
                allow_private = True
        elif op == "fetch":
            if _needs_private_network(p):
                add("network_private")
                allow_private = True
        elif op in ("open", "search"):
            # R-H178 · 人类视角执行律：**打开浏览器 / 搜索 = 人的基本可逆动作 ⇒ 免卡**。
            # 旧口径把 open/search 落进最后的 else，与"读页面（native/fetch）免卡"自相矛盾；
            # 判据只有一条：**人打开电脑工作时，会卡自己这一步吗？** 不会 ⇒ 降级。
            # 保留的唯一闸：**内网判定**（访问本机/内网/保留地址仍要 network_private）。
            if _needs_private_network(p):
                add("network_private")
                allow_private = True
        elif op == "automate":
            add("browser_control")
            if _needs_private_network(p):
                add("network_private")
                allow_private = True
        else:
            add("browser_control")
            if _needs_private_network(p):
                add("network_private")
                allow_private = True
    elif kind == "osint_scan":
        if _needs_private_network(p):
            add("osint_private")
            allow_private = True
    elif kind == "file_hygiene":
        if bool(p.get("fix")):
            add("filesystem_write")
    elif kind == "inventory":
        if bool(p.get("fix")):
            add("filesystem_write")
    elif kind == "signature_guard":
        if bool(p.get("restore")):
            add("filesystem_write")
    elif kind in ("llm_watch", "task_graph", "replan_loop", "duty_board",
                  "wiki_graph", "doc_intake"):
        # 🔴 大脑执行层·监督环（主人令 2026-10-13）：**整位零作用域** —— 它只动**我们自己的账**
        #    （主脑注意力队列 / 任务图 / 回流账，落 `store/brain_supervisor/`），与 `wf_*` / `lr_*` 同口径：
        #    任务图与长程账是本仓自己的账本，不是外面的世界。它**描述**的动作各自带自己的门
        #    （真执行时由那条链自己过门）。
        #    这里**显式写出来**，不是靠下方 fail-open —— 新增位必须有人交代它是什么（room_space 那块教训）。
        pass
    elif kind in ("pipeline_submit", "pipeline_rollback", "mirror_ascend", "mirror_rewind",
                  "one_key_deploy", "mirror_release"):
        # 🔴 2026-10-13（主人令逐字：「**技术层面不能给她有限制只保留人工授权护栏即可**」·
        #    「**直接改成终端YES才能使用就好了有时候我需要用到的啊**」）：
        #    带 `owner_override` 是走**专用钥匙**那条路 —— 门外要的是 `deploy_force`（另发一张一次性），
        #    而不是 `deploy_publish`。⇒ 主人可以只发"正常发布"的钥匙、**不发"强制放行"的钥匙**；
        #    旗标本身不带任何授权（没钥匙 ⇒ 门外就拒），所以**模型无法自我解锁**。
        if p.get("owner_override") and kind in ("mirror_ascend", "mirror_release", "one_key_deploy"):
            add("deploy_force")
        else:
            add("deploy_publish")
        if kind in ("one_key_deploy", "mirror_release"):
            add("process_execute", "filesystem_write")
    elif kind == "mirror_plan":
        if p.get("plan"):
            add("filesystem_write")
    elif kind == "mirror_simulate":
        add("filesystem_write")
    elif kind == "mirror_parity":
        add("filesystem_write")
    elif kind == "mirror_rehearse":
        add("process_execute", "filesystem_write")
    elif kind == "mirror_shape":
        if p.get("path"):
            add("filesystem_write")
    elif kind == "remote_confinement":
        # 🔴 这一位**会起探针**（whoami / tasklist / docker version / wsl node -v）⇒ 读类也挂 process_execute，
        #    别把"只是看看"念成"零作用域"（本仓有"零作用域≠只读"的现成教训）。
        #    ttl / grant 是纯读文件（不起进程）⇒ 零作用域。
        _rop = str(p.get("op") or "verdict").lower()
        if _rop in ("ttl", "grant"):
            pass
        else:
            add("process_execute")
    elif kind == "self_intake":
        # 未命中即取源：读 op 零作用域；intake 写胶囊/护照/账本 ⇒ filesystem_write。
        #   出网读按仓里既有先例（notion_bridge / coze_mail 也是零），不自造第三个口径。
        if str(p.get("op") or "known").lower() == "intake":
            add("filesystem_write")
    elif kind == "topic_web":
        # 主题共现网：读 op 零作用域；build 写图落盘 ⇒ filesystem_write。
        if str(p.get("op") or "stats").lower() == "build":
            add("filesystem_write")
    elif kind == "comfy_forge":
        # 创作融合台：全 op 只读 ⇒ **固定零作用域**。写死在这里是为了以后加写 op 时必须先改这行。
        pass
    elif kind == "scan_cap":
        # 统一扫描：species/scan 只读盘（不起进程、不出网）⇒ 零作用域；
        #   report 会写 store/scan_cap/ ⇒ 挂 filesystem_write。
        if str(p.get("op") or "scan").lower() == "report":
            add("filesystem_write")
    elif kind == "figure_gate":
        # 出图交付门：checklist / verdict / rounds 只读（零作用域）；
        #   declare_numbers / record_round 会写 store/figure_gate/ ⇒ 挂 filesystem_write。
        if str(p.get("op") or "verdict").lower() in ("declare_numbers", "record_round",
                                                      "record_evidence", "require_evidence"):
            add("filesystem_write")
    elif kind == "theme_cap":
        # 主题能力位（2026-10-15 新接）：list/show/check/discover/render **只读文件**⇒ 零作用域；
        #   只有 apply 会重写四个 CSS 的主题块（且先留 .bak）⇒ 挂 filesystem_write。
        #   未知 op：不加任何作用域（它只会回错，不动状态）—— 与本仓其他纯判据位同格。
        if str(p.get("op") or "check").lower() == "apply":
            add("filesystem_write")
    elif kind == "omarchy_bridge":
        # Omarchy 桥（2026-10-15 新接）：每个 op 都会起探针（which / wsl -l -q / hyprctl）
        #   ⇒ 读类也挂 process_execute（同 remote_confinement 的教训：别把"只是看看"念成零作用域）。
        #   events（读 .socket2.sock 事件流，一次性、读完即断）/ window（activewindow）
        #   / clients（clients）也是读类，同样挂 process_execute —— 它们都要起进程连 socket。
        #   改状态的那些 op（set_theme / theme_install / plugin_add / plugin_rm /
        #   plugin_enable / plugin_disable / dispatch / eval）追加 filesystem_write ——
        #   它们会改主题、装卸插件（**插件是无沙箱任意代码**）、排窗、当场执行 Lua。
        #   未知 op：仍按"会起探针"收 process_execute（fail-closed，宁紧不松）。
        _oop = str(p.get("op") or "assess").lower()
        add("process_execute")
        # observe：默认要落 store/omarchy_watch/（可被 GBT_STORE_DIR 隔离）⇒ 加 filesystem_write；
        #   observe(write=False) 是纯读，不加。
        if _oop == "observe" and p.get("write", True):
            add("filesystem_write")
        if _oop in ("set_theme", "theme_install", "plugin_add", "plugin_rm",
                    "plugin_enable", "plugin_disable", "dispatch", "eval"):
            add("filesystem_write")
    elif kind == "god_view":
        # 只读：读注册表 + state/ 账本，不起进程/不写盘/不出网 ⇒ 零作用域
        pass
    elif kind == "ux_doctrine":
        # 纯函数判据（不起进程、不写盘、不出网）⇒ 零作用域；未知 op 也零（它只会返回 error，不改状态）
        pass
    elif kind == "vision_loop":
        # 与内层真调用**同口径**（不许比它松）：眼=privacy_read · 耳=privacy_read ·
        # 嘴=audio_output · 手=desktop_control+privacy_read · status/think/verify=纯算零作用域。
        _vop = str(p.get("op") or "status").lower()
        if _vop == "look":
            add("privacy_read")
        elif _vop == "hear":
            add("privacy_read")
        elif _vop == "speak":
            add("audio_output")
        elif _vop == "act":
            add("desktop_control", "privacy_read")
        elif _vop == "loop":
            add("desktop_control", "privacy_read")
            if not bool(p.get("dry", True)):
                add("audio_output")
        elif _vop not in ("status", "think", "verify"):
            add("desktop_control", "privacy_read")     # 未知 op fail-closed
    elif kind == "delivery_gate":
        # status/gate 是纯读账（零作用域）；check/audit 会**起子进程**现跑扫，挂 process_execute。
        _dop = str(p.get("op") or "status").lower()
        if _dop in ("check", "audit"):
            add("process_execute")
        elif _dop not in ("status", "gate"):
            add("process_execute")            # 未知 op fail-closed
    elif kind == "tentacle_equip":
        # 🔴 职业 → 装备/账号：读类零作用域；equip 是写类（落账），默认要动装备 ⇒ 再挂 process_execute。
        #    具体装备自己的作用域（screen→privacy_read · ui_tree→desktop_control）由 tool_bay 内部
        #    **再过一道 auth_gate.check_and_consume** —— 两层门都在 V8 这边，谁也不绕。
        _eop = str(p.get("op") or "status").lower()
        if _eop == "equip":
            add("filesystem_write")
            if str(p.get("tools", True)).lower() not in ("false", "0"):
                add("process_execute")
        elif _eop == "assign":
            add("filesystem_write")            # 立职业 = 写 state/tentacle_professions.json
        elif _eop not in ("status", "professions", "plan", "report", "assigned", "roster"):
            add("filesystem_write")
    elif kind == "tool_bay":
        _top = str(p.get("op") or "state").lower()
        if _top == "install":
            add("filesystem_write")            # 落账 + 真接装备时内层自会再过一道门
        elif _top != "state":
            add("filesystem_write")            # 未知 op fail-closed
    elif kind == "omni_plug":
        # 🔴 2026-10-09（主人：把 V9 那种「插座」能力在自己这边补齐）：
        #   读类三 op 零作用域；plug 只做存在性探测（不动手）也不挂；
        #   **run 是真执行** ⇒ 按**插座类型**挂门；判不出来一律 fail-closed 按最重处理。
        #   这正是 V9 那套最缺的一环：V9 的 run_plugged 里 process 直接 subprocess、file 直接写盘，
        #   门只在 api 那条（net_guard）。门留在 V8 这边，能力才敢放出去。
        _pop = str(p.get("op") or p.get("action") or "status").lower()
        _sock = str(p.get("socket") or "").lower()
        if _pop == "run":
            if _sock == "process":
                add("process_execute")
            elif _sock == "file":
                if str(p.get("do") or "").lower() in ("write", "append"):
                    add("filesystem_write")
            elif _sock == "api":
                add("external_llm", "data_export")
            elif _sock == "web":
                add("desktop_control", "privacy_read")
            elif _sock == "app":
                # 插任意 APP 并操控 = 她的眼+手（看屏幕=隐私载体；点键鼠=桌面控制）
                add("desktop_control", "privacy_read")
                if str(p.get("do") or "").lower() == "launch":
                    add("process_execute")
            else:
                add("process_execute", "filesystem_write")   # 插座类型判不出 ⇒ 按最重收口
        elif _pop == "plug" and _sock == "app":
            add("privacy_read")           # 列窗口/读标题本身就是隐私载体
        elif _pop not in ("status", "sockets", "snapshot", "energy", "selftest", "plug"):
            add("filesystem_write")                          # 未知 op fail-closed
    elif kind == "media_stamp":
        # 🔴 2026-10-09（主人问「元数据接入了吗」后补齐）：
        #   status/tags/verify 是**读类**（只读容器标签）⇒ 零作用域；
        #   stamp 真写盘（重写容器）⇒ filesystem_write；未列出的 op **fail-closed**。
        #   （旁边的 media_run / media_publish 靠 write_guard 自钉写面、门内零作用域；
        #    新接的这一位不走那条老路，直接在门上声明。）
        _sop = str(p.get("op") or p.get("action") or "status").lower()
        if _sop == "stamp":
            add("filesystem_write")
        elif _sop not in ("status", "tags", "verify"):
            add("filesystem_write")                 # 未知 op 一律按写类
    elif kind == "obsidian_vault":
        # 🔴 2026-10-09 根因修复（第二处 fail-open 写盘口，护照 fc-20261009T051306-0ztd）：
        #   obsidian_vault 的 provision/sync_page **真写盘**（实测 provision 报 vaults=273，
        #   root=<仓>/vaults），但本函数没有它的分支 ⇒ 零作用域 fail-open。
        #   后果两层：① 写盘免授权；② api 的「preflight 故障 ⇒ 有副作用的调用 fail-closed」
        #   判据是按**作用域**分流的 —— 零作用域 ⇒ 感知层坏了也照跑。
        #   实测红：test_preflight_fail_closed::test_a（喂坏 preflight 后 provision 仍 ok=True）。
        #   口径：读类 op 零作用域；写类 op filesystem_write；未知 op fail-closed。
        _vop = (p.get("op") or p.get("action") or "status").lower()
        if _vop not in ("status", "read", "list", "pages", "tags"):
            add("filesystem_write")
    elif kind == "room_space":
        # 🔴 2026-10-09 根因修复（门盲区 = 生产面红线的唯一漏洞，护照 fc-20261009T051306-0ztd）：
        #   注册表里**房间只有一个能力位** `room_space`（op 在 payload 里分派，api.py:540），
        #   而本函数下方的分支写的是 `room_create` / `room_shape` / `room_release` … ——
        #   这些 kind **从来没有任何能力位携带**，全是死分支。
        #   本函数对未列出的 kind 又是 **fail-open**（scopes=() ⇒ restricted=False）⇒ 实测：
        #     `policy.evaluate("room_space", {"op":"release"})` → scopes=[] restricted=False
        #     `cap room_space op=create` → 真写盘、**未消耗任何授权**（无 auth_consumed）
        #   即「写镜像/房间」这条生产面红线在**唯一可调用入口**上是失守的。
        #   口径按 AGENTS.md 生产面红线：写房间一律 filesystem_write；发布加 deploy_publish；
        #   演练加 process_execute；只读取数免卡；**未知 op fail-closed**（同 key_gateway 口径）。
        _rop = (p.get("op") or "status")
        if _rop in ("get_plan", "frame", "status"):
            pass                                        # 只读取数，免卡
        elif _rop == "release":
            add("deploy_publish", "filesystem_write")
        elif _rop == "rehearse":
            add("process_execute", "filesystem_write")
        else:
            add("filesystem_write")                     # create/enter/define_plan/gate/namespace/
                                                        # shape/snapshot/observe/plan/simulate/parity
                                                        # 以及**未知 op**（fail-closed）
    elif kind in ("room_create", "room_enter", "room_shape", "room_snapshot",
                  "room_observe", "room_gate", "room_namespace"):
        add("filesystem_write")
    elif kind == "room_release":
        # 同上：放行那条路走专用钥匙 `deploy_force`（单独一次性）
        add("deploy_force" if p.get("owner_override") else "deploy_publish", "filesystem_write")
    elif kind in ("room_plan", "room_simulate", "room_parity"):
        if kind != "room_plan" or p.get("plan"):
            add("filesystem_write")
    elif kind == "room_rehearse":
        add("process_execute", "filesystem_write")
    elif kind == "collab_open":
        add("remote_device", "filesystem_write")
    elif kind == "collab_close":
        add("filesystem_write")
    elif kind == "collab_server_start":
        add("process_execute", "network_private", "remote_device")
        allow_private = True
    elif kind == "collab_server_stop":
        add("process_execute", "remote_device")
    elif kind == "peer_register":
        add("remote_device", "filesystem_write")
    elif kind == "peer_request":
        add("remote_device", "network_private", "data_export")
        allow_private = True
    elif kind == "deploy_queue":
        if op == "tick" or op == "submit":
            add("deploy_publish")
    elif kind == "devour_github":
        add("data_export", "filesystem_write")
    elif kind == "devour_pulse":
        add("data_export", "filesystem_write", "external_llm")
    elif kind in ("llm_chat", "sec_llm", "autopilot", "think_loop"):
        add("external_llm")
    # ── 2026-09-28 补：新增三能力位的作用域声明（主人令：新增能力全部要与触手双向绑定）──
    # 为什么**必须**在这里补，光注册名字不够：
    #   本函数对**未列出的 kind 是 fail-open** —— `scopes=()` ⇒ `decision.restricted` 为假
    #   ⇒ `authorize()` 直接放行。三个新位里 `key_gateway` 能铸钥/吊销/重置运行态、
    #   `multimodal_port`/`genoffice_bridge` 能真出网，若只登记名字不声明作用域，
    #   就是**带着写盘与出网能力裸奔**，仓内"读类直连、写类过门"的收口在此处失守。
    #   （同族坑先例见 R-H98/R-H99c：声明与执行漂移，未授权路径可直开线程/发回合。）
    elif kind == "key_gateway":
        # 读类（只读账本与配置，不落盘、不外发、不铸钥）⇒ 零作用域：
        #   status/whoami/energy/plan/keys/compat/mask/classify/verify/selftest
        # 写类（改密钥账本与运行态）⇒ filesystem_write。
        # materialize 是**唯一返回明文密钥**的路（R-H201），且仓内全部调用方
        #   （cloud_llm.py / genoffice_bridge.py）取钥都是为了随后出网调模型
        #   ⇒ 按 external_llm 收口。
        # 未列出的 op 一律 fail-closed 按写类处理（将来加写动作不会被静默放行）。
        op = op or "status"
        if op == "materialize":
            add("external_llm")
        elif op in ("mint", "revoke", "note", "note_result", "report", "reset"):
            add("filesystem_write")
        elif op not in ("status", "whoami", "energy", "plan", "mask",
                        "classify", "verify", "keys", "compat", "selftest"):
            add("filesystem_write")
    elif kind == "multimodal_port":
        # 读类 ⇒ 零作用域：status/catalog/redlines/selftest；`port` 只回**密钥引用**
        #   （key_id / 掩码 / 指纹，永不含明文）且返回体自标 `readonly: True`。
        # `probe` **真出网**探端点（本机实测会打真实 HTTP）⇒ external_llm。
        # 未列出的 op 按"可能出网" fail-closed。
        op = op or "status"
        if op == "probe":
            add("external_llm")
        elif op not in ("status", "port", "catalog", "redlines", "selftest"):
            add("external_llm")
    elif kind == "genoffice_bridge":
        # status/probe ⇒ 零作用域（只读接线状态 + 回环 GET /health 探本桥存活）。
        # selftest 三样都占：`KG.mint()` 铸测试钥（filesystem_write）+ 起临时监听
        #   （network_private）+ 真出网打上游模型（external_llm）。
        # serve 不在能力位上（serve_forever 常驻会挂住调用方）；真带过来则按起监听收口。
        op = op or "status"
        if op == "selftest":
            add("filesystem_write", "network_private", "external_llm")
        elif op == "serve":
            add("network_private")
        elif op not in ("status", "probe"):
            add("external_llm")
    elif kind == "life":
        op = op or "status"
        write_ops = {"record", "event", "remember", "daily", "export",
                     "export_obsidian", "vault", "ingest", "import_sources",
                     "sync_sources"}
        if op in write_ops:
            add("filesystem_write")
        elif op == "reflect" and bool(p.get("save")):
            add("filesystem_write")
        elif op in ("chapter", "commitment", "habit"):
            action = str(p.get("action") or "list").lower()
            if action not in ("", "list", "status"):
                add("filesystem_write")
    elif kind == "bluetooth":
        if op not in ("status", "scan", "list"):
            add("device_control")
    elif kind == "bt_control":
        if op not in ("status", "scan", "list"):
            add("device_control")
    elif kind == "vision":
        if op not in ("status", "analyze_file"):
            add("privacy_read")
    elif kind == "voice":
        if p.get("out"):
            add("filesystem_write")
        if (op or "tts") in ("tts", "speak", None):
            # 风哥 2026-09-18 拍板：把「本机发声」这条隐式规则**显式化**（进注册表）。
            add("audio_output")
        if op in ("listen", "asr", "record"):
            # 🔴 2026-10-09 主人令「还有耳，嘴」补的缝：原来 **listen（耳）一条门都没有** ——
            #    麦克风可以不开票就开。而"听"与"看屏幕"同类：**采的是房间，也是隐私载体**
            #    ⇒ 挂 privacy_read（与 vision 的读屏同一档，不许比它松）。
            add("privacy_read")
    elif kind == "audit_query":
        add("audit_read")
    elif kind == "notion":
        op = op or "status"
        # R-H178 · 人类视角执行律：**查 ≠ 送** —— status/recent/search/page 是只读查询 ⇒ 免卡。
        # 其余动作（含将来新增的写入/未知动作）一律 fail-closed 挂 data_export。
        if op not in ("status", "recent", "search", "page"):
            add("data_export")
    elif kind == "codex_chat":
        # 真 Codex 通道：会驱动本机代理进程与外部模型服务。
        add("process_execute", "external_llm")
    elif kind in ("codex_thread_new", "codex_turn_send", "codex_interrupt"):
        # R-H99c（由一处恒真断言占位挖出来的真洞）：这三条在注册表里一直写着
        # "官方 Codex 写操作（需 process_execute 授权）"，**策略层却从没给它们挂过作用域** ——
        # 实测改前：`policy.evaluate(...)` 三个都返回 scopes=[] · restricted=False
        # ⇒ 未授权路径可以直接开线程 / 发回合 / 打断，声明与执行漂移（同 R-H98 那个病根）。
        # turn_send 还会把文本送到外部模型，故与 codex_chat 同口径加 external_llm。
        add("process_execute")
        if kind == "codex_turn_send":
            add("external_llm")
    elif kind == "codex_models":
        add("external_llm")

    elif kind == "prompt_bridge":
        # 第一刀纯本地模板（stdlib-only，不接外部模型）：三个动作零作用域。
        # 未列出的动作一律 fail-closed —— 将来接外部模型时必须显式加 external_llm。
        op = op or "compile"
        if op not in ("compile", "passthrough", "status"):
            add("external_llm", "data_export")
    elif kind == "voice_orchestra":
        # 语音技能中枢（2026-09-18 接进能力库）：三个只读动作 list/pipeline/status 读的是
        # **仓内常量表**（voice_orchestra.VOICE_SKILL_REGISTRY），不碰数据面、不外发、不落盘，
        # 所以显式声明「零作用域」。未列出的动作一律按「可能外发/落盘」处理 —— fail-closed，
        # 免得将来加 tts/clone 动作时被静默放行（同族坑：作用域未注册）。
        op = op or "list"
        if op not in ("list", "pipeline", "status"):
            add("data_export", "external_llm")
    elif kind == "ledger_note":
        # R-H600 立 · **R-H620 改**（主人 2026-09-21 明确要求「切过去」）。
        #
        # 原口径：只有 status/rules/preview 零作用域，**唯一写原语 APPEND 挂 filesystem_write**。
        # 后果（实测）：`run_task('ledger_note', {'op':'append', ...})` 在**非可信会话**里一律
        # `denied`，于是这条「登记」的路永远走不进万能插 —— 而**同一个效果**在仓里早就
        # 用脚本直接写盘（.scratch/_rhNNN_append.py）达成 ⇒ 挂闸并没有真的挡住那次写入，
        # 只是把「走万能插」这条路堵死了（**闸挂了，路没通**）。
        #
        # 现口径：**对齐盘上 `stigmergy` 的先例**（那一族也是「只追加」的能力，policy 里
        # 没有条目 ⇒ 零作用域）。理由：本能力位的写面**窄到只剩一条**——
        #   · 目标**固定**（只能写那一份台账；**调用方传不了路径**）
        #   · **只追加**（目标末尾必须是换行，否则拒写；不修不补）
        #   · **单物理行** + **禁半角双引号** + **行首形状** + **幂等** + **缺前驱拒写**
        # ⇒ 它不是通用文件写入，是**一条有七道闸的追加口**。
        #
        # 🔴 fail-closed 保留：**未列出的动作**（含将来新增的写动作）**仍然挂**
        #    `filesystem_write` —— 免得将来加了别的写动作被静默放行
        #    （同族坑：作用域未注册）。
        #
        # 注：本规则**不动任何别的能力**；可信主人会话（CLI/GUI/已鉴权本地服务）
        # 照旧走 is_trusted() 直接放行。
        op = op or "status"
        if op not in ("status", "rules", "preview", "append"):
            add("filesystem_write")

    if kind == "code_patch":
        # 2026-09-23 新接：**改代码**从此过门。
        # 口径与 `ledger_note` 同族但方向相反：那边是"只有 APPEND 写"，这边是
        # **"只有 apply / rollback 写"**（dry_run 是默认，零作用域）。
        # 🔴 fail-closed：**不写白名单、写黑名单** —— 只把三个只读别名放行，
        # 其余任何 op（含将来新增的写动作）**一律挂 filesystem_write**。
        if op not in ("", "dry_run", "dry", "preview", "diff"):
            add("filesystem_write")

    if kind == "git_read":
        # 2026-09-23：版本库**只读面**（status/diff/log/show/branch_list/stash_list）。
        # **显式空挂**：写在这里是为了让"它零作用域"是一条**看得见的决定**，
        # 而不是"文件里没提它所以碰巧没挂"。将来谁往里加写 op，必须同时改这一行。
        pass

    if kind == "git_write":
        # 2026-09-23：版本库**写面**（stage/commit）。
        # **永远挂**，不按 op 判 —— 拆成独立能力位就是为了让这条判据平凡正确，
        # 没有"这个 op 算不算写"的判断题，也就没有判错的机会。
        add("filesystem_write")

    if kind == "pipeline_submit" and (p.get("review") or int(p.get("refine_rounds", 0) or 0) > 0):
        add("external_llm")

    # ── 授权红队内核（Owner 2026-09-25 令：黑客能力多维度全覆盖，使用需人工授权）──
    # 口径与全仓一致：**纯离线分析不挂作用域；碰隐私载体 / 设备 / 写盘 / 出网的一律挂**。
    # （Owner 同日的授权分级令让这些"日常技术动作"变成 TTL 内可多次用的时段授权 ——
    #   否则开一次输入记录就要回终端敲一次 YES，能力等于不可用。见 auth_gate.ONE_SHOT_SCOPES。）
    elif kind == "redteam_recon":
        if op == "creds":                       # 只有翻凭据落点那条碰隐私载体
            add("privacy_read")
    elif kind == "pentest":
        if op == "verify":                      # plan 只出计划不碰目标
            add("network_private")
        elif op in ("authorize", "revoke"):     # 授权清单是写盘
            add("filesystem_write")
    elif kind == "keylogger":
        if op in ("start", "stop", "purge"):
            add("privacy_read", "process_execute", "filesystem_write")
        else:                                   # status / dump 只读采集结果
            add("privacy_read")
    elif kind == "screen_sniff":
        if op in ("capture", "purge"):
            add("privacy_read", "filesystem_write")
        else:
            add("privacy_read")
    elif kind == "device_takeover":
        if op == "take":
            add("device_control")
    elif kind == "remote_domain":
        if op in ("add", "revoke"):
            # 公网 endpoint 那条放行走专用钥匙（内网/记录类照旧 remote_device）
            if op == "add" and p.get("owner_override"):
                add("deploy_force", "filesystem_write")
            else:
                add("remote_device", "filesystem_write")
    elif kind == "credential_steal":
        add("privacy_read")
    elif kind == "data_hijack":
        if op in ("baseline", "verify"):
            add("filesystem_write")
        else:
            add("privacy_read")
    # 外部 CLI 智能体（2026-09-25 补齐接线）：status/version 只探 PATH，不挂；
    # 真调 exec 是把任务数据送出去 + 起进程，两条都挂。
    elif kind in ("claude_code", "codebuddy", "ul_tars_desktop"):
        if op in ("exec", "run", "chat", "ask"):
            add("process_execute", "external_llm")
    # social_eng / paywallbuster / asset_vault_freeze / onboarding_gate：
    # 纯离线判定 + 只读体检，与 sec_surface / sec_scan 同类 —— **不挂作用域**。

    # ── 2026-10-04 补：万能触手·Web 六态（omni_web）—— 此前**零作用域 fail-open** ──
    #   24h 审查实证（不是理论风险）：
    #     · `edit_file` 真写盘（omni_web_cap.py:285 起，目标路径由调用方给）
    #     · `read_source` 可被绝对路径穿透 ⇒ 读**任意本机文件**（同函数，原实现无仓根校验）
    #     · `read_structure/gitingest` 真 `git clone` 落盘 + 出网（:72 起）
    #   本函数对未列出的 kind 是 fail-open（同上方 key_gateway 段注释）⇒ 只在
    #   caps_registry 登记名字（:1347）而不在此声明 = 写盘/私读/出网全免授权。
    #   口径与全仓一致（同族先例 devour_github = data_export + filesystem_write）：
    #     · 本地路径 ⇒ 读的是本机 ⇒ privacy_read
    #     · 远程仓库 ⇒ clone 落盘 + 外网取物 ⇒ filesystem_write + data_export
    #   🔴 fail-closed：未列出的 op 按"写 + 私读 + 外发"三挂处理（将来加动作不被静默放行）。
    elif kind == "omni_web":
        op = op or "read_structure"
        if _needs_private_network(p):
            add("network_private")
            allow_private = True
        _raw = str(p.get("repo") or p.get("url") or "")
        _is_local = bool(_raw) and (os.path.isabs(_raw) or (len(_raw) > 1 and _raw[1] == ":"))
        _read_ops = ("read_structure", "read_source", "read", "tree", "结构", "看结构",
                     "源码", "读源码")
        if op in _read_ops:
            if _is_local:
                add("privacy_read")
            else:
                add("filesystem_write", "data_export")
        elif op in ("read_explanation", "讲解", "读讲解", "explain", "wiki"):
            pass  # 只打 GitHub API / raw README，不落盘、不克隆 ⇒ 公开只读
        elif op in ("edit_file", "改文件", "edit", "write"):
            add("filesystem_write")
        elif op in ("gitingest", "交给AI", "ai_digest"):
            add("filesystem_write", "data_export")
        elif op in ("stackblitz", "跑项目", "run"):
            pass  # 只生成 URL / 指令，不真跑、不落盘
        else:
            add("filesystem_write", "privacy_read", "data_export")

    # ── 2026-10-04 补：脑会·编队群（brain_council）—— **显式零作用域**（同 git_read 的写法：
    #    让"它零作用域"是一条看得见的决定，不是文件里没提所以碰巧没挂）。
    #    依据主人令「触手职业拉群、群里只出本域意见、决策与执行权全局只属 GBT小土豆V8」：
    #    脑会是**纯推演**（不出网、不落盘、不起进程，brain_council.py 只 import 标准库 +
    #    动态导入脑模块）⇒ 读类直连；它产出的只是提案 —— **执行永远另行走既有授权门**。
    #    🔴 fail-closed 保留：将来给脑会加任何写/出网动作，必须回这里显式挂作用域。
    if kind == "brain_council":
        pass

    # ── 2026-10-08 补：独立终审位（C-15「验收方 ≠ 产出方」· 2026-10-08 新在册的能力位 review_gate）──
    # 为什么**必须**在这里补：本函数对**未列出的 kind 是 fail-open**（scopes=() ⇒ authorize 直接放行，
    # 同上方 key_gateway 段的注释）⇒ 只登记名字不声明作用域，等于带着写面裸奔。
    # 判据按它**实际做什么**定（读接线件 tools/codex-scripts/terminal-review.py 定档，不是拍脑袋）：
    #   · review / escalate / status / where 是**纯读盘判定**（现算 sha256/字节/空否/BOM/关键词 +
    #     读任务真读数，只打印不落盘；件头明文「本件默认零写盘」）⇒ 零作用域（读类直连）；
    #   · reflow 只在 **submit=true**（落任务账，走既有 lr_submit 位）或 **tick=true**（推进任务，
    #     走既有 lr_tick 位）时才产生写 ⇒ 那时挂 filesystem_write（更深的执行由被推进任务各自的
    #     能力位**自己**过门，双层门，这里不越权代判）；
    #   · retro 只在 **handoff=true**（写跨体接续包，走既有 handoff 位）时才写盘 ⇒ 那时挂 filesystem_write。
    # 🔴 fail-closed：**未列出的 op**（含将来新增的写动作）一律挂 filesystem_write ——
    #    免得将来加了别的写动作被静默放行（同族坑：作用域未注册）。
    if kind == "review_gate":
        op = op or "status"
        if op == "reflow" and (bool(p.get("submit")) or bool(p.get("tick"))):
            add("filesystem_write")
        elif op == "retro" and bool(p.get("handoff")):
            add("filesystem_write")
        elif op not in ("review", "escalate", "retro", "reflow", "status", "where"):
            add("filesystem_write")

    # ── 2026-10-13 补：视觉打印（新在册的能力位 vision_print · 主人令「给我补齐」）──
    # 为什么**必须**在这里补：本函数对**未列出的 kind 是 fail-open**（scopes=() ⇒ authorize 直接放行）。
    # 判据按它**实际做什么**定（读件定档，不是拍脑袋）：
    #   · status / where = 纯契约读数（只 import 模块 + 读落点路径）⇒ 零作用域；
    #   · see / print / diff / loop 里的取帧段 —— 读屏幕是**隐私载体**，与 vision / voice listen
    #     同一档（口径：不许比 vision 松）；
    #   · print / loop —— 写真代码 + 真截图产物（outputs/vision-print/）⇒ filesystem_write；
    #     且**真起浏览器进程**渲页（Chromium/Edge headless）⇒ process_execute；
    #   · ask_model —— 把**图**发给外部视觉模型 ⇒ external_llm（数据出境，同 vision cloud 那条）。
    # 🔴 fail-closed：**未列出的 op** 一律按"要取屏 + 要渲"挂满（privacy_read +
    #    filesystem_write + process_execute）—— 免得将来加了别的动作被静默放行
    #    （同族坑：作用域未注册）。
    if kind == "vision_print":
        # 🔴 空 op 也归 status 档 —— 判据**跟着实现走**：`tools/vision_print.py::run()`
        #    的默认就是 `op or "status"`（api.py 那条分派分支同款），裸调只会读契约、
        #    不会偷偷去截屏/起浏览器。若将来把默认 op 改成会动的东西，**这里必须同步改**，
        #    否则就是一个 fail-open 洞。
        if op in ("", "status", "where"):
            pass
        elif op in ("see", "diff"):
            add("privacy_read")
        elif op == "ask_model":
            add("privacy_read", "external_llm")
        elif op in ("print", "loop"):
            add("process_execute", "filesystem_write")
            if op == "loop":
                add("privacy_read")               # loop 一定先取帧
                if p.get("use_model"):
                    add("external_llm")           # 看图回码那条可选腿
        elif op == "polish":
            # 2026-10-13 加：调优那一步**真跑两条腿**（天真放大写图 · 外观库 ffmpeg 上味道）
            # ⇒ 起进程 + 写产物。两条腿都是**嵌套走唯一门**（run_task）去调既有位，不绕门。
            add("process_execute", "filesystem_write")
        else:
            add("privacy_read", "filesystem_write", "process_execute")

    # ── 2026-10-13 补：本机 CAD 链的口（新在册的能力位 cadgen）──
    # 判据按它**实际做什么**定（读件定档，不是拍脑袋）：
    #   · status / where（含空 op）**连 `--version` 都不跑** ⇒ 纯探、零作用域
    #     （判据跟着实现走：`tools/cadgen_cap.py::run()` 的默认就是 `status`）；
    #   · version / doctor / help ⇒ 会**起进程**跑真件 ⇒ process_execute；
    #   · snapshot ⇒ 起进程 **且写产物**（PNG/SVG/MP4，写在哪由调用方给）⇒ 另加 filesystem_write。
    # 🔴 fail-closed：**未列出的 op** 一律按「要起进程 + 要写盘」挂满（同族坑：作用域未注册）。
    if kind == "cadgen":
        if op in ("", "status", "where"):
            pass
        elif op in ("version", "doctor", "help"):
            add("process_execute")
        elif op == "snapshot":
            add("process_execute", "filesystem_write")
        else:
            add("process_execute", "filesystem_write")

    # ── 2026-10-13 补：UI 组件库的口（新在册能力位 ui_kit）──
    # 判据按它**实际做什么**定：
    #   · status / where / find = 只读索引（读 jsonl 打分）⇒ **零作用域**；
    #   · build = 扫 `_upstream/galaxy` 并**写自己的 store**（`store/ui_kit/index.jsonl`）⇒ filesystem_write；
    #   · take = 把件**拷到 `outputs/ui-kit/`** ⇒ filesystem_write。
    # 🔴 fail-closed：未列出的 op 一律按"要写盘"挂（同族坑：作用域未注册）。
    if kind == "ui_kit":
        if op in ("", "status", "where", "find"):
            pass
        else:
            add("filesystem_write")

    # ── 2026-10-13 补：设计与审美图鉴的口（新在册能力位 design_atlas）──
    # 判据按它**实际做什么**定：status/where/find = 只读索引 ⇒ **零作用域**；
    # build = 扫上游手册并**写自己的 store** ⇒ filesystem_write。**未列出的 op fail-closed**。
    if kind == "design_atlas":
        if op in ("", "status", "where", "find"):
            pass
        else:
            add("filesystem_write")

    # ── 2026-10-13 补：作品链（新在册能力位 art_chain）──
    # 判据按它**实际做什么**定：status/where = 只读契约 ⇒ **零作用域**；
    # run = 跑四步链：真渲（**起子进程**跑 render_page.py）+ 取件/调优**写产物** + 嵌套调 ui_kit/vision_print
    # ⇒ process_execute + filesystem_write。**未列出的 op fail-closed**。
    if kind == "art_chain":
        if op in ("", "status", "where"):
            pass
        else:
            add("process_execute", "filesystem_write")

    # ── 2026-10-13 补：动效引擎的口（新在册能力位 motion_kit）──
    # 判据按它**实际做什么**定：status/where/find/api = 只读索引（读 jsonl 打分）⇒ **零作用域**；
    # build = 扫 `_upstream/anime/dist/modules` 并**写自己的 store** ⇒ filesystem_write；
    # prove = **起 Node 子进程**原生真跑引擎算纯函数 ⇒ process_execute。
    # 🔴 fail-closed：未列出的 op 一律按"要起进程 + 要写盘"挂满（同族坑：作用域未注册）。
    if kind == "motion_kit":
        if op in ("", "status", "where", "find", "api"):
            pass
        elif op == "build":
            add("filesystem_write")
        elif op == "prove":
            add("process_execute")
        else:
            add("process_execute", "filesystem_write")

    # ── 2026-10-13 补：动效组件图鉴的口（新在册能力位 bits_kit）──
    # 判据按它**实际做什么**定：status/where/find/api = 只读索引（读 jsonl 打分）⇒ **零作用域**；
    # build = 扫 `_upstream/react-bits/src/content` 并**写自己的 store** ⇒ filesystem_write。
    # 本位**不起任何进程**（零执行），所以 fail-closed 只挂写盘，不硬加 process_execute。
    if kind == "bits_kit":
        if op in ("", "status", "where", "find", "api"):
            pass
        else:
            add("filesystem_write")

    # ── 2026-10-13 补：作品策划位（新在册能力位 art_brief）──
    # 判据按它**实际做什么**定：status/where/plan = 只读编排（四路 `find` 全是零作用域的读）⇒ **零作用域**；
    # run = 把整条链交给 art_chain：真渲（**起子进程**）+ 写产物 ⇒ process_execute + filesystem_write。
    # 🔴 fail-closed：未列出的 op 一律按"要起进程 + 要写盘"挂满（同族坑：作用域未注册）。
    if kind == "art_brief":
        if op in ("", "status", "where", "plan"):
            pass
        else:
            add("process_execute", "filesystem_write")

    # ── 2026-10-13 补：外部件接入图鉴（新在册能力位 intake_kit）──
    # 判据按它**实际做什么**定：status/where/find/api = 只读索引（读 jsonl 打分）⇒ **零作用域**；
    # build = 扫 `_upstream/` 下六件的知识面并**写自己的 store** ⇒ filesystem_write。
    # 本位**不起任何进程、不出网、不执行外部件** ⇒ fail-closed 只挂写盘。
    if kind == "intake_kit":
        if op in ("", "status", "where", "find", "api"):
            pass
        else:
            add("filesystem_write")

    # ── 2026-10-13 补：内存墙蒸馏件（新在册能力位 offload_distill）──
    # 判据按它**实际做什么**定：五个 op **全是只读**（读本文件常量 + 只读系统 API；
    # **无 subprocess、无 urllib、无写盘**）⇒ **整位零作用域**。
    # 未知名由**处理器自己** fail-closed（回 `{ok:false, fail_closed:true}` 并列出可用 op）——
    # 同族先例 `recon_distill`（注册表里明写"零作用域"）。这里显式写出来，是为了让"零作用域"**可见**，
    # 不是靠"没写分支所以放行"。
    if kind == "offload_distill":
        pass

    # ── 2026-10-13 补：云卡触手（新在册能力位 pod_link）──
    # 判据按它**实际做什么**定（同族口径：公网读=零；把数据发出去=data_export；跑东西=process_execute）：
    #   · status/ls/down/where = 公网**读**（拉卡清单、列目录、取回文件）⇒ **零作用域**；
    #   · up   = **把本机数据送出去**（上传到卡）+ 读本机文件 ⇒ data_export + filesystem_write；
    #   · run  = **在远端跑代码** ⇒ process_execute。
    # 🔴 fail-closed：未列出的 op 一律挂满三项。
    if kind == "pod_link":
        if op in ("", "status", "ls", "down", "where"):
            pass
        elif op == "up":
            add("data_export", "filesystem_write")
        elif op == "run":
            # 🔴 2026-10-13 自纠（口径一致性，不是给自己开方便）：`run` = **在远端跑代码**，
            #    同族先例（mcp_call / cadgen / codex_chat / browser 的 automate）都**只挂
            #    process_execute** —— 没有谁因为"它也能顺带发数据"就再叠一道出境闸。
            #    **`up` 不动**：那才是字面意义上的「把数据发送到外部服务」⇒ 仍挂 data_export。
            add("process_execute")
        else:
            add("process_execute", "data_export", "filesystem_write")

    # ── 2026-10-13 补：云卡 ComfyUI 触手（新在册能力位 comfy_cloud）──
    # 判据按它**实际做什么**定（同族口径：跑东西=process_execute；落本机产物=filesystem_write）：
    #   · status/nodes/models/queue/history = 每一步运输都要**在远端跑代码**（经 pod_link run）
    #     ⇒ 读类也挂 process_execute —— 这不是多余，是如实：本机到 8188 没有路，读也得在卡里读。
    #   · submit/video/free = 在远端跑 + （video 还会 down 产物到本机 outputs/cloud）⇒ 再叠 filesystem_write。
    #   · fetch = 卡→本机落盘 ⇒ 只挂 filesystem_write（down 本身零作用域）。
    # 🔴 fail-closed：未列出的 op 一律挂满三项。
    if kind == "comfy_cloud":
        # 2026-10-21 补（主人令「没有宿主无空闲 GPU 就自动调用云端免费 GPU」→「继续」）：
        #   `freegpu` = 付费卡没空卡时转 **HF 免费 GPU 节点**出片。
        #   按它实际做什么定：出网打 HF（network_private）+ 产物逐字节落本机（filesystem_write）；
        #   **不叠 data_export**（不把本机数据外传，只发一句提示词与收到产物）。
        if op == "freegpu":
            add("network_private", "filesystem_write")
        elif op in ("", "status", "nodes", "models", "queue", "history"):
            add("process_execute")
        elif op == "fetch":
            add("filesystem_write")
        elif op in ("submit", "video", "free"):
            add("process_execute", "filesystem_write")
        else:
            add("process_execute", "data_export", "filesystem_write")

    return PolicyDecision(kind=kind, risk=risk, scopes=tuple(scopes),
                          action=action, allow_private=allow_private, details=details)


def authorize(kind: str, payload: dict | None = None) -> dict:
    """评估并授权。可信主人会话直接放行；其他路径按作用域消耗人工授权。

    🔴 2026-10-17 主人令（逐字）：「门在自主长线任务的时候除了转账，黑客能力，其他皆可GBT小土豆V8判断点授权」
    新增口径（**默认关**，仅自主长线任务开启时生效）：
      · 开启开关：环境变量 `GBT_AUTONOMOUS=1`（由无人值守链 `unattended-chain.py` 设）；
      · **排除项**（仍需主人在终端发授权）：`transfer`（转账类）与 security 域**进攻/黑客面**能力位；
      · 其余受限动作 ⇒ GBT小土豆V8 **自行判断授权**，并落审计 `autonomous_authorized`（谁、什么、哪些作用域）。
    """
    decision = evaluate(kind, payload)
    if not decision.restricted or is_trusted():
        return {
            "ok": True,
            "trusted": is_trusted(),
            "decision": decision,
            "scopes": list(decision.scopes),
            "authorizations": [],
        }
    auto_ok, auto_reason = autonomous_self_judgment(kind, decision.scopes)
    if auto_ok:
        _audit_autonomous(kind, decision.scopes, decision.action, auto_reason)
        return {
            "ok": True,
            "trusted": False,
            "decision": decision,
            "scopes": list(decision.scopes),
            "authorizations": [],
            "auto_authorized": True,
            "by": "GBT小土豆V8",
            "reason": auto_reason,
            "note": "自主长线任务：除转账/黑客能力外由她自行判断授权（主人 2026-10-17 令）",
        }
    from .. import auth_gate
    result = auth_gate.check_and_consume_many(
        decision.scopes, detail=f"{kind}:{decision.action}")
    if not result.get("ok"):
        return {
            "ok": False,
            "trusted": False,
            "decision": decision,
            "scope": result.get("missing", [None])[0],
            "missing": result.get("missing", []),
            "denied": True,
            "error": result.get("error"),
            "how_to_grant": result.get("how_to_grant"),
            "note": result.get("note"),
            **({"autonomous_excluded": auto_reason} if auto_reason else {}),
        }
    return {
        "ok": True,
        "trusted": False,
        "decision": decision,
        "scopes": list(decision.scopes),
        "authorizations": result.get("consumed") or result.get("authorizations") or [],
        # R-H98：总控替代要**看得见**——缺件时用的那一条 owner_control 在此如实透出，
        # 免得"用总控顶掉的"和"逐条授权的"在调用方眼里长得一模一样。
        "substituted_for": list(result.get("substituted_for") or []),
    }


def describe() -> dict:
    return {
        "trusted_owner_session": is_trusted(),
        "scope_descriptions": dict(SCOPE_DESCRIPTIONS),
        "policy": "主人会话直通；未受信调用对受限动作消耗一次性人工授权；不删除任何能力",
    }


def safe_url_parts(url: str) -> dict:
    parsed = urllib.parse.urlsplit(url)
    return {"scheme": parsed.scheme, "host": parsed.hostname, "port": parsed.port}
