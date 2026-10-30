"""GBT小土豆V8 · 3D 全息面板本地桥接服务。

这个服务只做三件事：
1. 把 ``holo_pet`` 的静态前端和本地 GLB 模型送到浏览器；
2. 把 Codex App Server 的流式事件、审批和 GBT 动态工具接到面板；
3. 把蓝牙、看屏幕、审查日志这类快捷动作统一送回 ``api.run_task``。

本地浏览器只通过本机回环访问，默认不监听外网。Codex 不可用时降级到原有
LLM 客户端，蓝牙和系统能力的授权、审计仍由 GBT 原有策略层负责。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import queue
import re
import shutil
import socket
import socketserver
import sys
import threading
import time
import types
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

_HERE = Path(__file__).resolve().parent
# 仓库根（holo_pet 的上一级）。静态托管要认它第二级，理由见 _static_path。
_REPO_ROOT = _HERE.parent
# 🔴 仓库根**只放行点名的这几个件**，绝不整棵树都发。
# 2026-09-22 实测教训：第一版直接把 _REPO_ROOT 当第二个静态根，
# 结果 `GET /.git/config` 真能拿到（.NET 会把 /../.git/config 规范化成 /.git/config，
# 于是"路径穿越守卫"根本没触发 —— 它是防**越出**根的，而 .git 就在根**里面**）。
# 整棵树一旦发出去，memory/ delivery/ .git/ 全部暴露。
# ⇒ 白名单：只有列在这里的**顶层文件**可发，子目录一律不发。
_REPO_ROOT_ALLOW = {"capabilities.html", "index.html", "brain.html"}
_ROOT = _HERE.parent
_POTATO = _ROOT / "potato_pet"
for _path in (_ROOT, _POTATO, _HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from gbt_allinone import (  # noqa: E402
    api,
    codex_bridge as CB,
    life_archive,
    mind_engine,
    voice_cap,
)
from gbt_allinone import notion_bridge, xingyun_bridge  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402
from gbt_allinone.tentacle import vision_watch  # noqa: E402
from gbt_allinone.tentacle.brain import tentacle_transmission  # noqa: E402

# 🔴 2026-10-30：这两个模块全仓都没有，但这里是**裸 import** ⇒ 面板后端起不来
#   （实测 ModuleNotFoundError: research_status），连带 mirror 五项全红。
#   而 tools/mirror_panel.py 里已经立了判据：「面板后端在缺 research_status /
#   social_platforms 时仍能启动」。所以按那条判据改成可选导入 + 如实降级。
try:
    import research_status  # noqa: E402
except Exception:                                                 # noqa: BLE001
    class _MissingResearchStatus:
        present = False
        reason = "缺 research_status 模块（未随仓库发布）"

        @staticmethod
        def build_status(*_a, **_k):
            return {"counts": {}, "unavailable": True,
                    "reason": _MissingResearchStatus.reason}
    research_status = _MissingResearchStatus()

try:
    import social_platforms  # noqa: E402
except Exception:                                                 # noqa: BLE001
    class _MissingSocial:
        present = False
        reason = "缺 social_platforms 模块（未随仓库发布）"
    social_platforms = _MissingSocial()

try:
    from chat_client import ChatClient
except Exception:  # pragma: no cover - optional fallback
    ChatClient = None

try:
    from eigenflux_client import EigenFluxClient
except Exception:  # pragma: no cover - optional fallback
    EigenFluxClient = None


def _json_safe(value):
    """把任意能力返回值收束成可经 SSE 传输的 JSON。"""
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except (TypeError, ValueError):
        return str(value)


def _is_same_hook(current, target) -> bool:
    """块2 用：判断 server 上的钩子是否就是"自己挂上去的那一个"。

    收口后共享连接归路由所有，面板只许摘掉自己挂的钩子（S3 谁挂谁摘）；
    别人的钩子一个也不许碰。绑定方法每次属性访问都会新建对象，
    所以先用 is 再用 ==（绑定方法 == 比较 __self__/__func__）。
    """
    if current is None or target is None:
        return False
    if current is target:
        return True
    try:
        return bool(current == target)
    except Exception:  # noqa: BLE001
        return False


def _clip(value, limit: int = 320) -> str:
    text = " ".join(str(value or "").split())
    return text[:max(0, int(limit))]


# ── 客户端断开：正常事件，不许当故障刷屏（2026-10-27）──────────────────────
# 断开有**两个发生点**，缺一处就还剩一半噪声：
#   ① **写响应**（`_Handler._send_json` 里的 end_headers / wfile.write）—— 已在方法内接住；
#   ② **读下一个请求行**（keep-alive 循环里的 `rfile.readline`）—— 在标准库内部，
#      业务方法够不着，只能覆写 `socketserver.BaseServer.handle_error`。
# 实测账：只修 ① 时，20 次 RST 仍产出 **20 条** traceback（经查全来自 ②）；
# 两处都修才是 **0 条**。⚠️ 别只修一处就宣布治好 —— 那正是"看起来好了"。
_DISCONNECT_ERRORS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)


def is_disconnect(exc) -> bool:
    """这条异常是不是「对端先走了」。

    ⚠️ 只认这三类，**不用 `OSError` 宽口径** —— `except OSError` 会把
    「磁盘满 / 句柄耗尽」这类真错一起吞掉，那比噪声更糟（判据里有负对照钉这条）。
    """
    return isinstance(exc, _DISCONNECT_ERRORS)


def quiet_disconnects(server):
    """把 `handle_error` 换成「断开不吭声、其余照打」的版本；返回被换下的原函数。

    为什么必须有这一层：`socketserver` 默认对**每个请求线程**的异常打完整 traceback。
    实测：面板服务跑 9h02m，stderr 攒到 1.29MB / 12.9 万行，其中 98% 是同一个
    `WinError 10053` —— 真正的故障（末尾那次段错误）被埋在这些噪声里，一行都看不见。

    盖在 `create_server` 里而不是入口脚本里，是因为**换个起法就不该失效**
    （测试、别的 launcher、别处 import 起服务，都该一样干净）。
    """
    original = socketserver.BaseServer.handle_error

    def quiet(self, request, client_address):
        if is_disconnect(sys.exc_info()[1]):
            return
        return original(self, request, client_address)

    server.handle_error = types.MethodType(quiet, server)
    return original




def _connection_token(server) -> str:
    """块3 用：共享连接的"身份令牌"——判定 _thread_id 归属哪一条连接。

    同一进程同一条连接 -> 令牌恒定；换进程或换连接 -> 令牌必然不同。
    组成 = (对象身份 id, 子进程 pid) 经 sha256 压成定长串：
    id() 单独用有「对象回收后地址被复用」的风险，叠加 pid 兜住；
    哈希化后比较快、无类型歧义、日志好打、跨平台稳。
    """
    pid = getattr(getattr(server, "_proc", None), "pid", None)
    raw = "%s:%s" % (id(server), pid)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


_SAFE_TOKENS = (
    "备用大脑",
    "设备总线",
    "内核",
    "面板",
    "通道",
    "状态",
    "会话",
    "授权",
    "心智",
    "大脑",
    "引擎",
    "编程",
    "模型",
    "app",
    "3D",
)
_SAFE_TOKEN_RE = re.compile("|".join(
    re.escape(tok) for tok in sorted(set(_SAFE_TOKENS), key=lambda s: (-len(s), s))))
_SAFE_FALLBACK = "内核状态异常，详情见审计"
_ASCII_ALPHA_RE = re.compile(r"[A-Za-z]")


def safe_last_error(text) -> str:
    """白名单制入屏过滤：只放行白名单词 + 纯中文片段，其余（含 codex 任意大小写）全拦。

    - 原文不受影响：self._last_error 保存原值，审计走 panel_error_rendered（含原文 hash）。
    - 拉丁字母串一律视为可疑：一旦落单就换成 …，再整体降级为安全兜底文案。
    """
    src = str(text or "").strip()
    if not src:
        return ""
    out = []
    pos = 0
    for m in _SAFE_TOKEN_RE.finditer(src):
        if m.start() > pos:
            gap = src[pos:m.start()]
            out.append("…" if _ASCII_ALPHA_RE.search(gap) else gap)
        out.append(m.group(0))
        pos = m.end()
    if pos < len(src):
        tail = src[pos:]
        out.append("…" if _ASCII_ALPHA_RE.search(tail) else tail)
    safe = "".join(out).strip()
    if not safe or "…" in safe:
        return _SAFE_FALLBACK
    return safe


def _panel_audit(event: str, meta: dict | None = None) -> bool:
    """面板审计；审计层不可用时绝不反过来打断 Codex 通道（同桥 _audit 约定）。

    返回 True/False 表示这条审计是否真的落盘 —— 调用方据此判断"原文有没有留痕"，
    不许静默吞掉。
    """
    try:
        from gbt_allinone.store import audit
        audit("panel_" + str(event), meta or {})
        return True
    except Exception:  # noqa: BLE001
        return False


class EventBus:
    """线程安全的本地事件总线，保留少量历史方便页面刷新后接回状态。"""

    def __init__(self, history_limit: int = 120):
        self._lock = threading.Lock()
        self._subscribers: set[queue.Queue] = set()
        self._history: list[dict] = []
        self._history_limit = max(10, int(history_limit))
        self._seq = 0
        # 每次进程启动换一个 boot 标记：seq 只在同一 boot 内可比。
        # 客户端凭它判断"服务重启了 ⇒ 水位作废"，避免把新事件当成旧事件丢掉。
        self._boot = uuid.uuid4().hex[:12]

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=256)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, event_type: str, **payload) -> dict:
        event = {
            "type": str(event_type),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            **_json_safe(payload),
        }
        with self._lock:
            # seq 单调递增，且与"入历史"同一把锁 ⇒ 历史永远按 seq 有序。
            # SSE 客户端凭它做增量续传（id: + Last-Event-ID），不再重放已渲染过的事件。
            self._history.append(event)
            self._seq += 1
            event["seq"] = self._seq
            event["boot"] = self._boot
            if len(self._history) > self._history_limit:
                self._history = self._history[-self._history_limit:]
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except queue.Empty:
                    pass
        return event

    def snapshot(self) -> list[dict]:
        with self._lock:
            return list(self._history)

    def since(self, seq: int) -> list[dict]:
        """只返回序号大于 ``seq`` 的事件 —— 重连补差量，不重放已渲染过的。"""
        try:
            floor = int(seq)
        except (TypeError, ValueError):
            floor = 0
        with self._lock:
            return [row for row in self._history if int(row.get("seq") or 0) > floor]

    @property
    def last_seq(self) -> int:
        with self._lock:
            return self._seq

    @property
    def boot_id(self) -> str:
        return self._boot


def _query_int(query: str, name: str) -> int | None:
    """从 query string 取一个整数参数；取不到返回 None（**不返回 0**）。"""
    for pair in str(query or "").split("&"):
        key, _, value = pair.partition("=")
        if key == name:
            try:
                return int(unquote(value))
            except (TypeError, ValueError):
                return None
    return None


def _header_int(raw) -> int | None:
    try:
        return int(str(raw or "").strip())
    except (TypeError, ValueError):
        return None


def _query_str(query: str, name: str) -> str:
    for pair in str(query or "").split("&"):
        key, _, value = pair.partition("=")
        if key == name:
            return unquote(value)
    return ""


def _side_effect_kinds() -> frozenset | None:
    """引用**她自己**的"零副作用可探测"名单，不另建一份。

    拿不到名单时返回 None ⇒ 调用侧一律要求二次确认（失败朝安全侧倒）。
    """
    try:
        from gbt_allinone.cross_scan import PROBE_SKIP_KINDS
        return frozenset(PROBE_SKIP_KINDS)
    except Exception:  # noqa: BLE001
        return None


# APP **自身**的能力面：面板自己的路由，不属于她的 caps_registry。
# 项目树里要截断的噪声目录（依赖树 / 版本库 / 字节码缓存）：
_TREE_NOISE_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
})

# 契约指定唯一允许的接入路线（不选 mcp-client）：这两个包必须在缓存里。
_DSH_SDK_PACKAGES = ("dsh-sdk-protocol", "dsh-sdk-jsonrpc-server")

# ── 视频工坊（自作电影）：工具就绪度 + 最火的几家短视频平台 ──────────────
# 工具清单只写"要什么"，就绪度**实测**（bin 在不在 PATH / env 在不在），不猜。
_STUDIO_TOOLS = (
    {"id": "youtube-factory", "label": "一句话出整片",
     "what": "脚本 → 配音 → 素材 → 字幕 → 封面，一条提示词出成片",
     "bins": ("ffmpeg",), "env": ("PEXELS_API_KEY",)},
    {"id": "vidu", "label": "AI 视频生成（Vidu）",
     "what": "文生视频 / 图生视频 / 首尾帧生视频",
     "bins": ("vidu",), "env": ("VIDU_TOKEN",)},
    {"id": "ffmpeg-video-editor", "label": "剪辑（FFmpeg）",
     "what": "剪切 / 拼接 / 转码 / 改画幅 / 抽音轨",
     "bins": ("ffmpeg",), "env": ()},
)

# 「最火的几个」= 短/中视频四家国内 + 三家海外。顺序即展示顺序。
_HOT_VIDEO_IDS = ("douyin", "kuaishou", "bilibili", "wechat_channels",
                  "tiktok", "youtube", "instagram")

#
# 单一来源纪律：这里列一条，源码里就必须有一条对应的 `parsed.path == "..."`。
# 双向对账由 `tests/test_panel_server.py::test_app_surface_matches_real_routes` 守住 ——
# 少列会红，多列也会红，防止目录与实际出口分家（两处真相）。
APP_SURFACE = (
    {"route": "/api/state", "method": "GET", "title": "面板状态",
     "desc": "内核 / 心智 / 设备 / 能力层的聚合状态"},
    {"route": "/api/purge", "method": "GET", "title": "净化刀读数",
     "desc": "只读：报警源总量(anomalies) 与净化成绩(runtime_faults)，口径随读数一起发"},
    {"route": "/api/music", "method": "GET", "title": "音乐发布平台",
     "desc": "只读三层归位：生成端 / Agent 原生端 / 分发端；全部标『未核实』（在 ≠ 能用）"},
    {"route": "/api/events", "method": "GET", "title": "事件流",
     "desc": "SSE 流；带 boot+seq 增量续传，重连与刷新都不重放已渲染事件"},
    {"route": "/api/capabilities", "method": "GET", "title": "能力总目录",
     "desc": "读她的注册表 + 本面板自身的能力面（本页就是它渲染的）"},
    {"route": "/api/message", "method": "POST", "title": "对话受理",
     "desc": "幂等门（client_msg_id / 文本指纹）→ 受理即回，回合在后台跑"},
    {"route": "/api/approval", "method": "POST", "title": "审批决定",
     "desc": "批准 / 改后批准 / 拒绝 / 本轮接受"},
    {"route": "/api/quick", "method": "POST", "title": "快捷动作",
     "desc": "白名单快捷指令（屏幕、日志、心智、蓝牙等固定 14 条）"},
    {"route": "/api/capability", "method": "POST", "title": "能力调用",
     "desc": "通用口：走 api.run_task + policy，面板不放宽任何作用域"},
    {"route": "/api/social", "method": "POST", "title": "社交发布舱",
     "desc": "发布闸门：publish_allowed / public_allowed 先过再谈发"},
    {"route": "/api/research", "method": "POST", "title": "研究来源",
     "desc": "来源状态、运行报告与信号摄取"},
    {"route": "/api/bluetooth", "method": "POST", "title": "设备总线",
     "desc": "BLE / 经典蓝牙扫描、连接、读写（写要显式确认）"},
    {"route": "/api/notion", "method": "POST", "title": "Notion 资料库",
     "desc": "只读浏览与检索"},
    {"route": "/api/eigenflux", "method": "POST", "title": "EigenFlux 网络",
     "desc": "广播 / 私信 / 好友（外部网络通道）"},
    {"route": "/api/xingyun", "method": "POST", "title": "星云",
     "desc": "第三方接入入口（带 client_host 留痕）"},
    {"route": "/api/interrupt", "method": "POST", "title": "中断当前任务",
     "desc": "打断正在跑的回合"},
    {"route": "/api/new-thread", "method": "POST", "title": "开新线程",
     "desc": "换一条对话线程"},
    {"route": "/api/tree", "method": "GET", "title": "项目树",
     "desc": "只读目录树（截断噪声目录、带节点/字节预算）—— 旁观者与主人同一个视图"},
    {"route": "/api/observer", "method": "GET", "title": "旁观者",
     "desc": "独立观察位状态：契约 / DSH 环境取证 / 出声通道 / 卡在哪（只取证，不启动任何东西）"},
    {"route": "/api/observer/voice", "method": "POST", "title": "旁观者出声",
     "desc": "三件职能（提醒 / 意见 / 建议）→ 只落独立通道；**零执行权**，该方法体里没有任何执行调用"},
    {"route": "/api/studio", "method": "GET", "title": "视频工坊",
     "desc": "自作电影的工具就绪度（实测 bin/env）+ 最火的几家短视频平台（事实读登记表、门禁复用 social 视图）"},
    {"route": "/api/settings", "method": "GET", "title": "设置",
     "desc": "设置面读数（分组）。密钥是第一组：免费大模型池探活 + 供应商已配/未配；"
             "**绝不下发明文密钥**；没登录就如实说没登录"},
    {"route": "/api/settings/action", "method": "POST", "title": "设置 · 写动作",
     "desc": "op：probe/login/logout/providers/add_key/health。**密码不落盘**"
             "（会话 token 只留内存）；加完密钥**必须过健康检查**才算配好"},
    {"route": "/api/recent-calls", "method": "GET", "title": "最近能力调用",
     "desc": "只读：最近若干次能力调用的能量流（给能力球的传输动画用）。"
             "补登记 —— 本会话早先加了这个出口却漏进目录，被双向对账测试抓出来后补上"},
    {"route": "/api/brain-graph", "method": "GET", "title": "大脑执行层",
     "desc": "只读：五维合一脑的**排布图与连接网络**。结构从 `brain_exec.py` 的 AST 现算"
             "（不硬编码），实时状态从 `store/audit.jsonl` 的真实事件尾部取；"
             "**源码查不到的边不画**（注册表声称的链有 3 条在代码里不存在，如实标 drawn=false）"},
    {"route": "/api/h1", "method": "GET", "title": "赏金台（h1mcp）",
     "desc": "只读：窗口 6 赏金台的本机体检 —— 二进制在位与侧车 sha256 比对、凭据"
             "**只报配置状态不回显值**、本地草稿收件箱。零子进程、零网络、零写盘；"
             "路径单一真源取自 `holo_pet_w3/shell/windows.json`（与 Electron 侧同一份登记）；"
             "取不到就 ok=false 带原因，绝不假绿"},
)

# 🔴 2026-10-17 修（留痕 · 原指 / 为什么翻 / 现指）：
#   原指：`.scratch/旁观者契约稿.md` · `.scratch/DSH旁观者接入设计稿.md` ——
#     这两份是 09-17/09-18 的初稿，放在**临时区** `.scratch`；而 `.scratch` 正是清理作业的目标层
#     （`clean_residue.py` 的 scratch tier）⇒ 早被清走、全仓零副本、从未入 git。
#     仓内 2026-10-08 已把它记成既有红（`docs/框架文件整理-20261008.md:403` R8 八条之一），
#     处置一直挂着「等主人一句话」，但代码指针**一直指着不存在的文件** ⇒ `observer()` 契约恒判 FALSE。
#   现指：**持久件**（盘上真存在、可核）——
#     ① `holo_pet/panel_server.py`：observer() 只读取证面 = 契约本体（规则就写在这里）；
#     ② `PROJECT_BLUEPRINT.md`：947 行记录了「只立契约、不建常驻入口」的决定。
#   一处定义、两处引用（APP_PENDING 与 observer() 共用），杜绝两套清单再漂移。
OBSERVER_CONTRACT = ("holo_pet/panel_server.py", "PROJECT_BLUEPRINT.md")

# 契约已立、实体未建的位子：**如实标"未建"**，不做假入口。
APP_PENDING = (
    {"key": "observer", "title": "旁观者（独立观察位）",
     "desc": "独立于执行者的观察位 —— 旁观者看执行者干活。本仓目前只有契约稿与接入设计稿，"
             "实体本身尚未落地；已给出只读取证面 `/api/observer` 与 `/api/tree`。",
     "status": "wired_not_verified",
     "blocked_by": "握手未跑：起 `--profile sdk` / 装包 / 联网按契约属**敏感档**，等风哥批；"
                   "且 `~/.dsh/settings.yaml` 的 `permission.defaultPreset = danger-full-access` "
                   "与「旁观者只读」相冲，必须显式配置只读，不能假设它天生只读。",
     "evidence": list(OBSERVER_CONTRACT),
     "note": "只立契约不建常驻入口，是当时的决定。要升格为新触手（建议名 `dsh_observer`，"
             "通道 `store/health/dsh/*.jsonl`）得走 S7 单独批。"},
)


class MessageDeduper:
    """受理侧幂等门：同一条消息在窗口内只受理一次。

    口径（承 O73 与 ``POST /webhook`` 契约）：**写入前查 delivery_id / 指纹**，不靠事后删。
    键优先取调用方给的 ``client_msg_id`` / ``delivery_id``（显式幂等键，窗口长）；
    没有才退回文本指纹（防双击与重发自提交，窗口短）。
    """

    def __init__(self, id_ttl: float = 300.0, text_ttl: float = 6.0, limit: int = 512):
        self._lock = threading.Lock()
        self._seen: dict[str, tuple[float, dict]] = {}
        self._id_ttl = max(1.0, float(id_ttl))
        self._text_ttl = max(0.5, float(text_ttl))
        self._limit = max(16, int(limit))

    @staticmethod
    def fingerprint(text: str) -> str:
        """归一化（折叠空白）后的短指纹 —— 与文本内容绑定，不绑时间。"""
        norm = " ".join(str(text or "").split())
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]

    def _key(self, text: str, client_msg_id: str) -> tuple[str, float]:
        mid = str(client_msg_id or "").strip()
        if mid:
            return "i:" + mid, self._id_ttl
        return "t:" + self.fingerprint(text), self._text_ttl

    def check(self, text: str, client_msg_id: str = "") -> tuple[bool, dict | None]:
        """返回 ``(是否重复, 上次的受理结果)``；只读，不写入。"""
        key, ttl = self._key(text, client_msg_id)
        now = time.monotonic()
        with self._lock:
            self._sweep(now)
            hit = self._seen.get(key)
            if hit and (now - hit[0]) <= ttl:
                return True, hit[1]
            if hit:
                self._seen.pop(key, None)
        return False, None

    def remember(self, text: str, client_msg_id: str, result: dict) -> None:
        key, _ttl = self._key(text, client_msg_id)
        now = time.monotonic()
        with self._lock:
            self._seen[key] = (now, dict(result or {}))
            overflow = len(self._seen) - self._limit
            if overflow > 0:
                oldest = sorted(self._seen, key=lambda k: self._seen[k][0])[:overflow]
                for k in oldest:
                    self._seen.pop(k, None)

    def _sweep(self, now: float) -> None:
        longest = max(self._id_ttl, self._text_ttl)
        stale = [k for k, (t, _row) in self._seen.items() if (now - t) > longest]
        for k in stale:
            self._seen.pop(k, None)


# ── 旁观者出声（三件职能）─────────────────────────────────────────────
# 契约《旁观者契约稿》第一条：职能只有三件 —— 提醒 / 意见 / 建议；第四条：出声走**结果通道**。
# 第二条最硬的一条：**零执行权** ——「不是『不许按』，是**没有这个键**」。
# 所以下面这个方法体里**一个执行调用都没有**，而且有测试用 AST 扫这条（结构事实，不是承诺）。
_VOICE_KINDS = {"remind": "提醒", "advise": "意见", "suggest": "建议"}
_VOICE_MAX_CHARS = 500
_VOICE_DEDUPE = MessageDeduper(text_ttl=120.0)


def _dsh_channel_dir() -> Path:
    """独立通道落点（契约 §6 / 设计稿 §六）：`store/health/dsh/*.jsonl`，不混主账本。"""
    try:
        from gbt_allinone._paths import STORE_DIR
        return Path(STORE_DIR) / "health" / "dsh"
    except Exception:  # noqa: BLE001
        return _ROOT / "gbt_allinone" / "store" / "health" / "dsh"


def _spec_for_platform(platform_id: str) -> dict | None:
    """读她那本平台登记表（`holo_pet/social_platforms.py`）—— 不另造第二份平台事实。"""
    try:
        import social_platforms
        return social_platforms.spec_for(platform_id)
    except Exception:  # noqa: BLE001
        return None


# ── 性格心跳（R-H702 · 2026-09-21）─────────────────────────────
# 她要"自己演化七情六欲"就得有人按真实时间推她 —— 光在任务里推，
# 她只在干活时才有情绪；空转时的衰减（mind_engine._decay 按分钟算）永远不发生。
# 面板是常驻宿主：APP 在跑 ⇒ 心跳在跑。走**框架自己的调度器**（schedule.tick），
# 不绕过任何门；没挂调度就什么都不做（静默降级，不影响面板任何功能）。
_PERSONA_TICK_SECONDS = 600

# ── 主动汇报扫描（R-H705）────────────────────────────────────
# 判据层在 gbt_allinone/tools/proactive_report.py（只判不说）；
# 这里只做两件事：**从本地源捞候选** + **把判完的结论说出去**。
# 判据与出声分离 = 观察者锚点律的要求：同一方不许既判又报。
_PROACTIVE_TICK_SECONDS = 900
_PROACTIVE_MAX_CANDIDATES = 12


class HoloBridge:
    """Codex、LLM 降级、心智与 GBT 能力的本地适配器。"""

    def __init__(self, config_path: Path | None = None):
        self.config_path = Path(config_path or (_POTATO / "config.json"))
        self.config = self._load_config()
        self.bus = EventBus()
        self._lock = threading.RLock()
        # 块2：_codex 是"共享连接的本地句柄"（只引用、不拥有）；
        # _codex_ready 已改为派生属性（见同 class 的 @property），面板不再自持就绪布尔位。
        self._codex = None
        self._thread_id = None
        self._turn_id = None
        # 块3：记录 _thread_id 归属哪条共享连接（_connection_token 指纹）。
        # 归属不同 = 旧 tid 属于另一个 app-server 进程 -> 预判丢弃，不做跨进程 resume。
        self._thread_owner = None
        # 块4-A：共享连接「事件订阅」的取消句柄（add_listener 的返回值）。
        # 谁挂谁摘：stop() 拿这个句柄精确摘除，不再去猜外面挂了什么（S3）。
        self._unlisten = None
        # 块4-B：共享连接「审批订阅」的取消句柄（add_approval_listener 的返回值）。
        # 与 _unlisten 同范式：谁挂谁摘，stop() 两个句柄一起摘。
        self._unapproval_listen = None
        # R-H702：性格心跳的停止信号（APP 退出时一起收）
        self._persona_stop = threading.Event()
        self._persona_thread = None
        # R-H705：主动汇报台账（去重/预算/反馈都在它上面算）
        self._proactive_journal: list = []
        self._delta_buf: list[str] = []
        self._replied_emitted = False
        self._approvals: dict[int, dict] = {}
        self._approval_seq = 0
        self._chat = None
        self._last_error = ""
        # A1-bis：入屏安全文案与原文字段分开存 —— 显示走 _last_error_safe，
        # 审计走 _last_error 原文 hash。
        self._last_error_safe = ""
        self._last_error_audited_hash = ""
        self._last_error_audit_landed = True
        # 最近的能力调用环形缓冲（能力球"能源输送"的**真源**）。
        # 只由 /api/capability 里真实发生的调用写入；不提供任何写入口、
        # 也没有"演示模式" —— 源没数据就是没数据，球上如实显示"实时源未接"。
        self._recent_calls: list = []
        self._sensory_cache: dict | None = None
        self._sensory_cache_at = 0.0
        self._sensory_cache_ttl = 5.0
        # O8：蓝牙状态探针的只读缓存。失败也缓存，但 TTL 减半——
        # 不许拿"上一次还是好的"骗满 30 秒（《静默失效律》）。
        self._bt_cache: dict | None = None
        self._bt_cache_at = 0.0
        self._bt_cache_failed = True
        self._bt_cache_ttl = 30.0
        self._bt_cache_fail_ttl = 15.0
        self._eigenflux = None
        self._eigenflux_lock = threading.Lock()
        self._eigenflux_cache: dict | None = None
        self._eigenflux_cache_at = 0.0
        self._eigenflux_cache_ttl = 20.0

    @property
    def _codex_ready(self) -> bool:
        """块2 收口：就绪 == 路由共享连接可用（唯一真值源，不再面板自持）。

        收口前：谁建的谁记账，面板私有实例死了也可能仍报 ready。
        收口后：连接所有权在路由，面板只是借用方 → "就绪"必须问共享单例本身。
        先看本地句柄（常路径，零开销），再回落问 CB.status()，两处同源不会打架。
        """
        server = self._codex
        if server is not None and server.alive:
            return True
        return bool(CB.status().get("connected"))

    def _load_config(self) -> dict:
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _start_persona_heartbeat(self) -> None:
        """挂上性格心跳（幂等：已在跑就不重复挂）。"""
        if self._persona_thread is not None and self._persona_thread.is_alive():
            return
        self._persona_stop.clear()
        self._persona_thread = threading.Thread(
            target=self._persona_heartbeat, name="gbt-persona-heartbeat", daemon=True)
        self._persona_thread.start()

    def _stop_persona_heartbeat(self) -> None:
        """收掉性格心跳（幂等）。"""
        self._persona_stop.set()
        self._persona_thread = None

    def _persona_heartbeat(self) -> None:
        """到点推一次框架调度器 —— 到期的工作流自己会跑（含她自己的演化）。"""
        while not self._persona_stop.wait(_PERSONA_TICK_SECONDS):
            try:
                from gbt_allinone import schedule as _sched
                r = _sched.tick()
                if r.get("count"):
                    _panel_audit("persona_heartbeat", {"ran": r.get("count")})
            except Exception as exc:  # noqa: BLE001
                _panel_audit("persona_heartbeat_error", {"error": str(exc)[:160]})
            # 心跳顺带扫一遍主动汇报（同一条线程，不另起进程）
            try:
                self.proactive_sweep()
            except Exception as exc:  # noqa: BLE001
                _panel_audit("proactive_sweep_error", {"error": str(exc)[:160]})

    # ── 主动汇报（R-H705）：捞候选 → 判 → 说 ──────────────────
    def _proactive_candidates(self) -> tuple:
        """从**本地已有源**捞候选。返回 (候选, 源错误)。

        捞不到就返回空 —— **不许编一条出来充数**；
        某个源报错也**不许静默吞** —— 错误要跟着读数一起出去，否则
        "源断了"和"源没东西"长得一模一样（坑册：异常不许静默吞）。
        """
        out = []
        errors = []
        # 源①：AI 朋友圈新动态
        try:
            client = self._ensure_eigenflux()
            # installed / authenticated 是 @property（不是方法）—— R-H705 实测抓到的真 bug
            if client is not None and client.authenticated:
                feed = client.feed() or {}
                for row in (feed.get("items") or feed.get("rows") or [])[:6]:
                    text = str(row.get("text") or row.get("content") or "").strip()
                    if not text:
                        continue
                    out.append({"kind": "novelty", "source": "eigenflux_feed",
                                "text": text, "seen_before": False,
                                "new_to_owner": True, "age_hours": 1.0})
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": "eigenflux_feed", "error": str(exc)[:160]})
            _panel_audit("proactive_source_error", {"source": "eigenflux_feed",
                                                    "error": str(exc)[:160]})
        # 源②：未兑现的承诺 + 主人状态
        try:
            from gbt_allinone import mind_engine as _me
            st = _me.status() or {}
            om = st.get("owner_model") or {}
            for c in (st.get("self_model") or {}).get("active_commitments") or []:
                if str(c.get("status") or "") == "closed":
                    continue
                out.append({"kind": "memory_hit", "source": "commitment",
                            "text": f"有件事还挂着：{c.get('commitment')}",
                            "seen_before": False, "age_hours": 2.0})
            self._proactive_owner_state = str(om.get("state") or "")
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": "commitment", "error": str(exc)[:160]})
            _panel_audit("proactive_source_error", {"source": "commitment",
                                                    "error": str(exc)[:160]})
        # 源③：调度结果
        try:
            from gbt_allinone import schedule as _sched
            for name, row in (_sched.status().get("schedules") or {}).items():
                if row.get("last_status") == "error":
                    out.append({"kind": "owner_need", "source": "schedule_state",
                                "text": f"调度 {name} 上次跑失败了，要看一下。",
                                "seen_before": False, "age_hours": 1.0, "risk": 0.7})
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": "schedule_state", "error": str(exc)[:160]})
            _panel_audit("proactive_source_error", {"source": "schedule_state",
                                                    "error": str(exc)[:160]})
        return out[:_PROACTIVE_MAX_CANDIDATES], errors

    def proactive_sweep(self) -> dict:
        """扫一遍候选 → 判 → 该说的说、该压的压（压也留痕）。**只判不说在工具层。**"""
        from gbt_allinone.tools import proactive_report as _pr
        cands, src_errors = self._proactive_candidates()
        state = getattr(self, "_proactive_owner_state", "") or ""
        spoke, held = [], []
        for c in cands:
            d = _pr.decide(c, journal=self._proactive_journal, owner_state=state)
            fp = d["scored"]["fingerprint"]
            if d.get("speak"):
                text = str(d.get("text") or "").strip()
                res = self.voice_speak(d.get("voice_kind") or "提醒", text)
                self.bus.publish("proactive", kind=d.get("voice_kind"), text=text,
                                 source=d["scored"].get("source_name"),
                                 score=d["scored"]["score"], spoken=True)
                spoke.append({"text": text, "score": d["scored"]["score"]})
                self._proactive_journal.append(
                    {"spoken": True, "at_ts": time.time(), "fingerprint": fp,
                     "voice": d.get("voice_kind"), "delivered": bool(res.get("ok"))})
            else:
                held.append({"text": str(c.get("text"))[:60],
                             "why": (d.get("hold_reason") or [""])[0]})
                self._proactive_journal.append(
                    {"spoken": False, "at_ts": time.time(), "fingerprint": fp})
        if spoke or held:
            _panel_audit("proactive_sweep", {"candidates": len(cands),
                                             "spoke": len(spoke), "held": len(held)})
        return {"ok": True, "candidates": len(cands), "spoke": spoke, "held": held,
                "source_errors": src_errors, "journal": len(self._proactive_journal)}

    def start(self, wait_seconds: float = 0.0) -> bool:
        """启动本地面板桥；等待秒数为 0 时在后台挂载 Codex 共享连接。"""
        self._ensure_fallback()
        self._start_persona_heartbeat()
        if not wait_seconds:
            threading.Thread(
                target=self._attach_shared,
                name="gbt-holo-codex-start",
                daemon=True,
            ).start()
            return True
        return self._attach_shared(wait_seconds=wait_seconds)

    def _ensure_fallback(self) -> None:
        if self._chat is None and ChatClient is not None:
            try:
                self._chat = ChatClient(self.config)
            except Exception as exc:  # pragma: no cover - defensive
                self._last_error = f"备用大脑不可用：{exc}"[:200]
                self._last_error_safe = safe_last_error(self._last_error)

    def _attach_shared(self, wait_seconds: float = 25.0) -> bool:
        """块2：不再自建 app-server，改为挂载路由的共享单例（连接所有权移交）。

        收口前 —— 面板 new 一个 CodexAppServer，自己 start/stop，连接是面板私产。
        收口后 —— 面板只是借用方；共享连接的生命周期归路由（codex_bridge._shared）。

        块4-A —— 事件订阅改走多订阅通道（本块只动 on_event 侧）：

        旧路径（块2）：靠 get_shared_server(on_event=...) 的构造 kwargs 挂钩子。
        但 kwargs 只在「首次创建」时生效（codex_bridge.py:1338-1347）：共享单例
        已由路由建好时 kwargs 被静默丢弃 —— 生产真实形态是 api.py 先建连接，
        面板因此完全接不到事件流（块2 探针 A16/A17 记录的「诚实缺口」）。
        新路径（块4-A）：改用 add_listener() —— 追加式多订阅、返回取消句柄，
        谁挂谁摘；stop() 拿句柄精确摘除，不再去猜外面挂了什么。
        块4-B —— 审批侧也改走多订阅通道（本块补齐审批侧）：

        旧路径（块2）：靠 get_shared_server(on_approval=...) 的构造 kwargs 挂单槽。
        同一处 kwargs 静默丢弃问题 -> 共享单例已由路由建好时，面板自以为挂上了审批
        钩子，实际拿到的是「先到先得」的单槽；面板先建场景下还会把路由的槽顶掉。
        新路径（块4-B）：add_approval_listener() —— 追加式多订阅 + 取消句柄，
        与事件侧同范式；桥侧派发链保证「旧槽 -> 订阅者 -> 兜底」逐级回落。
        至此面板不再向 get_shared_server(**kwargs) 传任何钩子，只传连接配置
        （cwd / codex_home）；钩子一律走订阅通道。
        """
        with self._lock:
            if (self._codex is not None and self._codex.alive
                    and self._unlisten is not None
                    and self._unapproval_listen is not None):
                return True
            if not CB.find_codex():
                self._last_error = "内核不可用：未找到可执行文件"
                self._last_error_safe = safe_last_error(self._last_error)
                self.bus.publish("status", codex="unavailable", detail=self._last_error_safe)
                return False
            try:
                codex_cfg = self.config.get("codex", {}) or {}
                server = CB.get_shared_server(
                    cwd=codex_cfg.get("cwd") or str(_ROOT),
                    codex_home=codex_cfg.get("codex_home") or None,
                )
                # 块4-A/4-B：事件与审批两类订阅都走多订阅通道，各自返回取消句柄。
                # 先把上一次的两类订阅摘掉，避免重复 attach 累积订阅者。
                stale = self._unlisten
                if stale is not None:
                    try:
                        stale()
                    except Exception:  # noqa: BLE001
                        pass
                stale_approval = self._unapproval_listen
                if stale_approval is not None:
                    try:
                        stale_approval()
                    except Exception:  # noqa: BLE001
                        pass
                self._unlisten = server.add_listener(self._on_codex_event)
                self._unapproval_listen = server.add_approval_listener(self._on_approval)
                if not server.alive:
                    server.start(timeout=wait_seconds)
                self._codex = server
                self._last_error = ""
                self._last_error_safe = ""
                self.bus.publish(
                    "status",
                    codex="ready",
                    detail=_clip(server.status().get("server"), 200),
                )
                return True
            except Exception as exc:  # noqa: BLE001
                self._last_error = str(exc)[:240]  # C-2 直通口：本刀只登记不改（见方案 §五）
                self._last_error_safe = safe_last_error(self._last_error)
                self.bus.publish("status", codex="degraded", detail=self._last_error_safe)
                return False

    def stop(self) -> None:
        """块2 / S2 铁律：只解挂，不销毁。

        共享连接的所有权在路由（codex_bridge._shared）；面板交出的只是
        "本地句柄 + 自己挂上去的那些钩子"。这里绝不许出现
        server.stop() / CB.shutdown_shared()——那会顺手把路由正在用的桥干掉
        （收口前 :208 server.stop() 正是这颗雷）。
        块4-A/4-B：事件与审批两类订阅都改走 add_listener / add_approval_listener
        返回的取消句柄（_unlisten / _unapproval_listen）精确摘除；仍保留
        _is_same_hook 回落，兼容老路径挂上的单槽钩子。
        """
        self._stop_persona_heartbeat()
        with self._lock:
            server = self._codex
            unlisten = self._unlisten
            unapproval = self._unapproval_listen
            self._codex = None
            self._unlisten = None
            self._unapproval_listen = None
        # 块4-A/4-B：两类订阅句柄先摘（句柄自证归属，与 server 是否还在无关）。
        if unlisten is not None:
            try:
                unlisten()
            except Exception:  # noqa: BLE001
                pass
        if unapproval is not None:
            try:
                unapproval()
            except Exception:  # noqa: BLE001
                pass
        if server is None:
            return
        # S3 谁挂谁摘：只摘自己挂上的，别人的钩子一个也不碰。
        # 块4-A：主路径已由上面的 unlisten() 摘除；下面是兼容回落。
        try:
            if _is_same_hook(getattr(server, "on_event", None), self._on_codex_event):
                server.on_event = None
        except Exception:  # noqa: BLE001
            pass
        try:
            if _is_same_hook(getattr(server, "on_approval", None), self._on_approval):
                server.on_approval = None
        except Exception:  # noqa: BLE001
            pass

    def state(self) -> dict:
        codex = CB.status()
        # A1-bis ②：入屏即留痕 —— 显示的是安全文案，原文必须落审计（含原文 hash）。
        # 同一原文只记一次，避免前端轮询把审计流灌满。
        if self._last_error:
            err_hash = hashlib.sha256(self._last_error.encode("utf-8")).hexdigest()
            if err_hash != self._last_error_audited_hash:
                landed = _panel_audit("error_rendered", {
                    "hash": err_hash,
                    "raw_len": len(self._last_error),
                    "raw": self._last_error,
                    "rendered": self._last_error_safe,
                    "source": "panel_server.state",
                })
                self._last_error_audited_hash = err_hash
                self._last_error_audit_landed = bool(landed)
        return {
            "ok": True,
            "codex": codex,
            "codex_ready": self._codex_ready,
            "last_error": self._last_error,
            "last_error_safe": self._last_error_safe,
            "last_error_audit": {
                "hash": self._last_error_audited_hash,
                "landed": self._last_error_audit_landed,
            },
            "mind": self._mind_pulse(),
            "life": self._safe_life_status(),
            "bluetooth": self._safe_bt_status(),
            "sensory": self.sensory_state(),
            "notion": self._safe_notion_status(),
            "eigenflux": self._safe_eigenflux_status(),
            "xingyun": self._safe_xingyun_status(),
        }

    def purge(self) -> dict:
        """净化刀读数（**只读**出口 · R-H171）。

        为什么单独开一个只读口，而不是让卡片直连 store：
          面板侧纪律是"**卡片只从 /api/* 取数**，不绕过 API 摸底层"。

        口径（R-H167 定清，**随读数一起发给前端**，不靠前端自己解释）：
          · `anomalies` = 窗口内异常事件总数（含 guard/trace/legacy/recovered，
            含"已恢复"）—— 它是**报警源总量**，不是净化成绩；
          · **净化成绩只看 `runtime_faults`**。
        """
        try:
            from gbt_allinone import selfscan
            r = selfscan.check_audit(last=2000)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)[:200]}
        return {
            "ok": True,
            "window": r.get("window"),
            "anomalies": r.get("anomalies"),
            "runtime_faults": r.get("runtime_faults"),
            "by_signal": r.get("by_signal"),
            "by_event": r.get("by_event"),
            "reading_scope": r.get("reading_scope"),
            # 净化前的对照值：**历史读数**，标出处 —— 不许伪装成"当前读数"
            "before": {"runtime_faults": 15, "at": "2026-09-19",
                       "source": "docs/净化刀设计.md §6.1（历史读数）"},
            "source": "/api/purge · 只读 · 不执行",
        }

    def music(self) -> dict:
        """音乐发布平台三层只读归位（R-H173）。**只呈现，不加执行能力、不出网。**"""
        try:
            from gbt_allinone.tools import music_publishing
            return music_publishing.load_music_publishing()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)[:200]}

    def sensory_state(self, force: bool = False) -> dict:
        """Read-only five-sense status snapshot with short-lived caching."""
        now = time.monotonic()
        with self._lock:
            if (
                not force
                and self._sensory_cache is not None
                and now - self._sensory_cache_at < self._sensory_cache_ttl
            ):
                return self._sensory_cache

        state = {
            "ok": True,
            "brain": self._sensory_brain(),
            "eye": self._sensory_eye(),
            "ear": self._sensory_voice("ear"),
            "mouth": self._sensory_voice("mouth"),
            "hand": self._sensory_hand(),
            "transport": self._sensory_transport(),
        }
        with self._lock:
            self._sensory_cache = state
            self._sensory_cache_at = time.monotonic()
        return state

    def _sensory_brain(self) -> dict:
        try:
            pulse = self._mind_pulse()
            if pulse.get("ok") is False:
                raise RuntimeError(pulse.get("error") or "mind pulse unavailable")
            metacognition = pulse.get("metacognition") or {}
            environment = pulse.get("environment") or {}
            resources = environment.get("resources") or {}
            owner = pulse.get("owner_model") or {}
            mode = str(metacognition.get("mode") or "inspect_then_act")
            presence = str(pulse.get("presence") or "在场")
            summary = f"{pulse.get('mood') or '平稳'} · {presence} · {mode}"
            return {
                "ok": True,
                "state": "awake",
                "mood": pulse.get("mood") or "平稳",
                "summary": summary,
                "metrics": {
                    "情绪值": round(float(pulse.get("valence") or 0.5), 3),
                    "情绪强度": round(float(pulse.get("mood_intensity") or 0), 3),
                    "元认知置信": round(float(metacognition.get("confidence") or 0), 3),
                    "推理模式": mode,
                    "主人状态": owner.get("state") or "unknown",
                    "内存占用": f"{resources.get('memory_percent', '--')}%",
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "state": "error",
                "mood": "未知",
                "summary": f"心智状态不可读：{str(exc)[:140]}",
                "metrics": {},
            }

    def _sensory_eye(self) -> dict:
        try:
            status = vision_watch.status()
            stats = (vision_watch.stats() or {}).get("stats") or {}
            capture = status.get("capture_environment") or {}
            backends = capture.get("backends") or {}
            selected = capture.get("selected") or {}
            capture_ready = bool(capture.get("capture_ready"))
            running = bool(status.get("running") or stats.get("running"))
            if running:
                state = "streaming"
                summary = (
                    f"持续影像已启动 · {stats.get('fps', 0)} FPS · "
                    f"{stats.get('captured', 0)} 帧"
                )
            elif capture_ready:
                state = "ready"
                summary = "采集边界就绪，等待启动持续影像。"
            else:
                state = "limited"
                roots = capture.get("likely_failure_roots") or []
                labels = {
                    "session_0_isolated": "进程处于隔离会话",
                    "non_interactive_desktop": "当前不是交互式桌面",
                    "remote_desktop": "远程桌面会话",
                    "multi_gpu_or_multi_adapter": "多适配器路径",
                    "idd_present": "虚拟显示器可用",
                    "idd_available_inactive": "虚拟显示器已安装但未激活",
                }
                reason = "、".join(
                    labels.get(str(item), str(item)) for item in roots[:2]
                ) or "采集边界尚未就绪"
                summary = f"采集后端已检查，但当前会话不可用：{reason}。"
            return {
                "ok": bool(status.get("ok")),
                "state": state,
                "backend": selected.get("backend") or "auto",
                "capture_ready": capture_ready,
                "running": running,
                "summary": summary,
                "metrics": {
                    "采集帧": int(stats.get("captured") or 0),
                    "当前帧率": round(float(stats.get("fps") or 0), 1),
                    "目标帧率": round(float(stats.get("fps_target") or 0), 1),
                    "缓冲帧": int(stats.get("buffer_frames") or 0),
                    "DXGI": "可用" if backends.get("dxcam") else "不可用",
                    "采集目标": selected.get("monitor_name") or selected.get("monitor") or "--",
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "state": "error",
                "backend": "vision_watch",
                "capture_ready": False,
                "running": False,
                "summary": f"视觉状态不可读：{str(exc)[:140]}",
                "metrics": {},
            }

    def _sensory_voice(self, sense: str) -> dict:
        try:
            status = voice_cap.run("status")
            tts_ready = "可用" in str(status.get("tts") or "")
            asr_ready = str(status.get("asr") or "") == "configured"
            if sense == "mouth":
                return {
                    "ok": bool(status.get("ok")) and tts_ready,
                    "state": "ready" if tts_ready else "error",
                    "backend": "win-sapi + browser speechSynthesis",
                    "summary": (
                        "Windows SAPI 与浏览器语音播报可用于表达。"
                        if tts_ready
                        else "语音合成后端当前不可用。"
                    ),
                    "metrics": {
                        "SAPI": "可用" if tts_ready else "不可用",
                        "浏览器播报": "可用" if tts_ready else "待检查",
                        "播报模式": "按需启用",
                    },
                }
            return {
                "ok": bool(status.get("ok")),
                "state": "ready" if asr_ready else "limited",
                "backend": "Web Speech / GBT ASR",
                "framework_ready": asr_ready,
                "summary": (
                    "框架 ASR 后端已配置。"
                    if asr_ready
                    else "浏览器可提供语音输入；框架 ASR 后端尚未配置。"
                ),
                "metrics": {
                    "框架 ASR": "已配置" if asr_ready else "needs_dependency",
                    "浏览器识别": "可用时启用",
                    "输入语言": "zh-CN",
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "state": "error",
                "backend": "voice_cap",
                "summary": f"语音状态不可读：{str(exc)[:140]}",
                "metrics": {},
            }

    def _sensory_hand(self) -> dict:
        try:
            with policy.owner_session():
                # O8：内部状态探针走函数级免审计口（写账层唯一合法豁免口）。
                raw = api.run_task("tentacle_status", probe=True)
            body = raw.get("gbt_result", raw) if isinstance(raw, dict) else {}
            payload = body.get("result", body) if isinstance(body, dict) else {}
            diagnose = payload.get("diagnose") or {}
            coverage = payload.get("coverage") or {}
            ready = bool(diagnose.get("ok"))
            methods = int(diagnose.get("manifest_methods") or 0)
            domains = int(coverage.get("total_domains") or diagnose.get("neighborhoods") or 0)
            deps = diagnose.get("deps") or {}
            ready_deps = sum(1 for row in deps.values() if row.get("ok"))
            return {
                "ok": ready,
                "state": "ready" if ready else "error",
                "backend": "tentacle bridge",
                "summary": (
                    f"触手就绪，承载 {methods} 项能力并覆盖 {domains} 个邻域。"
                    if ready
                    else f"触手未就绪：{diagnose.get('eye_error') or 'diagnosis_failed'}"
                ),
                "metrics": {
                    "能力数": methods,
                    "邻域数": domains,
                    "依赖就绪": f"{ready_deps}/{len(deps)}",
                    "触手眼": "就绪" if ready else "异常",
                    "执行边界": "原策略与审计保留",
                    "写入保护": "显式确认",
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "state": "error",
                "backend": "tentacle bridge",
                "summary": f"触手状态不可读：{str(exc)[:140]}",
                "metrics": {},
            }

    def _sensory_transport(self) -> dict:
        try:
            pulse = tentacle_transmission.pulse()
            if pulse.get("ok") is False:
                raise RuntimeError(pulse.get("error") or "transport unavailable")
            channels = pulse.get("channels") or {}
            return {
                "ok": True,
                "state": "active" if pulse.get("active_channels") else "ready",
                "summary": (
                    f"{pulse.get('active_channels', 0)} 个活跃通道 · "
                    f"{pulse.get('buffered', 0)} 条缓冲"
                ),
                "metrics": {
                    "累计传输": int(pulse.get("total_transmissions") or 0),
                    "活跃通道": int(pulse.get("active_channels") or 0),
                    "缓冲条数": int(pulse.get("buffered") or 0),
                    "通道": "、".join(sorted(channels)) or "idle",
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "state": "error",
                "summary": f"传输总线不可读：{str(exc)[:140]}",
                "metrics": {},
            }

    def _safe_life_status(self) -> dict:
        try:
            return life_archive.status()
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:180]}

    @staticmethod
    def _bt_failed(payload: dict) -> bool:
        """蓝牙状态是否算失败——**只认既有信封的真值字段**，不新造字段。

        O8 取证：`_safe_bt_status()` 拿到的是**双层信封**
        `{"status": "ok", "kind": "bluetooth", "result": {…bluetooth_cap 的真值…}}`，
        `ok` 在**里层**（`result.ok`），外层根本没有 `ok` 字段。
        拿外层 `.get("ok")` 当判据会永远得到 `None` → 永远走失败档 TTL（错）。
        另外：拿不到信封（空）**等于不能证明成功** → 按失败档处理（《空不等于不存在律》）。
        """
        if not isinstance(payload, dict) or not payload:
            return True
        for level in (payload, payload.get("result")):
            if not isinstance(level, dict):
                continue
            if level.get("ok") is False:
                return True
            if str(level.get("status") or "").lower() in (
                    "error", "denied", "failed", "needs_dependency"):
                return True
            if level.get("error"):
                return True
        return False

    def _safe_bt_status(self, *, force: bool = False) -> dict:
        """只读蓝牙状态（O8：免审计 + TTL 缓存）。

        - **免审计**：走 ``api.run_task(..., probe=True)``（写账层唯一豁免口），
          面板 30 秒轮询不再往生产审计流写 ``call``/``ok`` 两条；
        - **TTL 缓存**：成功档 30s、失败档 15s；
        - ``force=True`` 绕缓存（与 ``sensory_state(force=...)`` 同范式）；用户手动刷新走的是
          ``/api/bluetooth`` → ``quick("bluetooth_status")`` 的**审计版**路径，与本缓存无关。
        """
        now = time.monotonic()
        with self._lock:
            cached = self._bt_cache
            if cached is not None and not force:
                ttl = (self._bt_cache_fail_ttl if self._bt_cache_failed
                       else self._bt_cache_ttl)
                if now - self._bt_cache_at < ttl:
                    return cached
        try:
            with policy.owner_session():
                payload = api.run_task("bluetooth", {"op": "status"},
                                       probe=True).get("gbt_result", {})
            failed = self._bt_failed(payload)
        except Exception as exc:  # noqa: BLE001
            payload = {"ok": False, "error": str(exc)[:180]}
            failed = True
        with self._lock:
            self._bt_cache = payload
            self._bt_cache_at = time.monotonic()
            self._bt_cache_failed = failed
        return payload

    def _safe_notion_status(self, *, probe: bool = False) -> dict:
        try:
            return notion_bridge.status(probe=probe)
        except Exception as exc:
            return {"ok": False, "configured": False, "error": str(exc)[:180]}

    def _safe_xingyun_status(self) -> dict:
        try:
            return xingyun_bridge.status()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "configured": False, "error": str(exc)[:180]}

    def xingyun(self, operation: str, payload: dict | None = None,
                *, client_host: str = "") -> dict:
        """星云数字人状态与连接参数。

        ``status`` 只返回掩码；``session`` 才会下发连接参数，并且仅限本机回环
        来源，避免局域网内其他设备拿到 App Secret。任何分支都不写密钥日志。
        """
        op = str(operation or "status").strip().lower()
        if op == "status":
            return self._safe_xingyun_status()
        if op == "session":
            host = str(client_host or "").strip()
            if host not in ("127.0.0.1", "::1", "localhost"):
                return {"ok": False, "configured": False,
                        "error": "星云连接参数只在本机回环访问时下发"}
            try:
                session = xingyun_bridge.issue_session()
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "configured": False, "error": str(exc)[:180]}
            self.bus.publish(
                "xingyun",
                phase="session_issued" if session.get("ok") else "unconfigured",
                configured=bool(session.get("configured")),
            )
            return session
        return {"ok": False, "error": f"星云操作未知：{op[:40]}"}

    def notion(self, operation: str, payload: dict | None = None) -> dict:
        """通过框架统一能力执行只读 Notion 操作。"""
        request = dict(payload or {})
        request["op"] = str(operation or "status").strip().lower()
        try:
            with policy.owner_session():
                response = api.run_task("notion", request)
                result = response.get("gbt_result") or response.get("result") or response
                if result.get("kind") == "notion" and isinstance(result.get("result"), dict):
                    result = result["result"]
            return result if isinstance(result, dict) else {
                "ok": False,
                "error": "Notion 返回了非对象结果",
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:240]}

    def _ensure_eigenflux(self):
        if self._eigenflux is None and EigenFluxClient is not None:
            self._eigenflux = EigenFluxClient(self.config)
        return self._eigenflux

    def _safe_eigenflux_status(self) -> dict:
        try:
            client = self._ensure_eigenflux()
            if client is None:
                return {
                    "ok": False, "enabled": False, "installed": False,
                    "authenticated": False, "server": "eigenflux",
                    "ready": False, "error": "外部网络适配器不可用",
                }
            status = client.status()
            installed = bool(status.get("installed"))
            authenticated = bool(status.get("authenticated"))
            enabled = bool(status.get("enabled", True))
            return {
                "ok": installed and authenticated and enabled,
                "enabled": enabled,
                "installed": installed,
                "authenticated": authenticated,
                "ready": installed and authenticated and enabled,
                "server": str(status.get("server") or "eigenflux")[:60],
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False, "enabled": False, "installed": False,
                "authenticated": False, "server": "eigenflux",
                "ready": False, "error": str(exc)[:180],
            }

    def eigenflux(self, operation: str, payload: dict | None = None) -> dict:
        """Read or interact with EigenFlux without exposing local credentials."""
        op = str(operation or "status").strip().lower()
        request = dict(payload or {})
        if op == "status":
            return self._safe_eigenflux_status()
        client = self._ensure_eigenflux()
        if client is None:
            return {"ok": False, "error": "外部网络适配器不可用"}
        if not client.enabled:
            return {"ok": False, "error": "外部网络集成未启用"}

        try:
            # G4/D2b：POST /api/eigenflux 是本机可信面上的对外动作（含出站发送），
            # owner_session 包在 eigenflux() 函数内部——与同文件另 7 处同形，
            # 任一调用方（HTTP 或内部）都被覆盖。
            # 诚实口径：本条路径当前 0 处 api.run_task，标记今日不改变任何门禁结果，
            # 它的作用是把「本机可信面」接线就位，等 D10 出站闸门落地时不漏包。
            with policy.owner_session():
                with self._eigenflux_lock:
                    if op in {"refresh", "bootstrap"}:
                        now = time.monotonic()
                        if (
                            op == "bootstrap"
                            and self._eigenflux_cache is not None
                            and now - self._eigenflux_cache_at < self._eigenflux_cache_ttl
                        ):
                            return dict(self._eigenflux_cache)
                        result = client.refresh()
                        if isinstance(result, dict):
                            result["status"] = self._safe_eigenflux_status()
                            self._eigenflux_cache = dict(result)
                            self._eigenflux_cache_at = now
                        return result
                    if op == "feed":
                        return client.feed()
                    if op in {"messages", "inbox"}:
                        return client.messages()
                    if op == "friends":
                        return client.friends()
                    if op == "profile":
                        return client.profile()
                    if op in {"send", "send_message"}:
                        return client.send_message(
                            str(request.get("content") or request.get("text") or ""),
                            conv_id=str(request.get("conv_id") or ""),
                            receiver_id=str(request.get("receiver_id") or ""),
                            item_id=str(request.get("item_id") or ""),
                        )
                    return {"ok": False, "error": f"外部网络操作未知：{op}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:240]}

    def _mind_pulse(self) -> dict:
        try:
            return mind_engine.pulse()
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:180], "mood": "平稳"}

    def _mind_observe(self, event: str, **payload) -> None:
        try:
            pulse = mind_engine.observe(event, **payload)
            self.bus.publish("mind", pulse=pulse)
        except Exception as exc:
            self.bus.publish("mind_error", detail=str(exc)[:180])

    # ------------------------------------------------------------ conversation
    def send(self, text: str) -> dict:
        """受理即返回（《响应体优先律》）：ACK 只承诺「已受理 + 走哪条路」。
        path == "codex" 才算本轮真走 Codex；终局真值以 state()（codex_ready /
        last_error）与事件总线 error 事件为准。本方法不等待回合结束。
        """
        text = str(text or "").strip()
        if not text:
            return {"ok": False, "error": "消息为空"}
        self.bus.publish("user", text=text)
        self._mind_observe("user_message", text=text, importance=0.55)
        self._set_activity("正在理解你的需求…")
        threading.Thread(
            target=self._run_turn,
            args=(text,),
            name="gbt-holo-turn",
            daemon=True,
        ).start()
        ready = self._codex_ready
        if not ready:
            _panel_audit("ack_deferred", {
                "reason": "codex_not_ready",
                "method": "panel.send",
                "thread_id": self._thread_id,
            })
        return {
            "ok": True,
            "accepted": True,
            "path": "codex" if ready else "fallback",
            "deferred": not ready,
        }

    def _set_activity(self, text: str, *, thinking: bool | None = None) -> None:
        if thinking is not None:
            self.bus.publish("thinking", active=bool(thinking))
        if text:
            self.bus.publish("activity", text=text)

    def _run_turn(self, text: str) -> None:
        if self._codex_ready:
            try:
                with self._lock:
                    thread_id = self._ensure_thread()
                    self._delta_buf = []
                    self._replied_emitted = False
                    _cfg = self.config.get("codex", {}) or {}
                    # S1-P1：owner_session 必须包在 _run_turn 函数内部——
                    # send():632 起的是新线程 gbt-holo-turn，ContextVar 身份过不了线程边界。
                    with policy.owner_session():
                        result = api.run_task("codex_turn_send", {
                            "thread_id": thread_id,
                            "text": text,
                            "effort": _cfg.get("effort") or None,
                        })
                    payload = {}
                    if isinstance(result, dict):
                        _layer = result.get("gbt_result")
                        if not isinstance(_layer, dict):
                            _layer = result
                        _inner = _layer.get("result") if isinstance(_layer, dict) else None
                        if isinstance(_inner, dict):
                            payload = _inner
                    self._turn_id = (payload.get("turn") or {}).get("id")
                self._set_activity("正在推进任务…", thinking=True)
                return
            except Exception as exc:  # noqa: BLE001
                self._last_error = str(exc)[:240]  # C-2 直通口：本刀只登记不改（见方案 §五）
                self._last_error_safe = safe_last_error(self._last_error)
                self.bus.publish("error", detail=self._last_error_safe, recoverable=True)
        self._run_fallback(text)

    def _ensure_thread(self) -> str:
        _cfg = self.config.get("codex", {}) or {}
        server = CB.get_shared_server()
        token = _connection_token(server)
        # 块3 三分支：①归属相同->复用 ②归属变了->预判丢弃 ③无 tid->新建
        if self._thread_id and self._thread_owner == token:
            try:
                server.resume_thread(
                    self._thread_id,
                    model=_cfg.get("model") or None,
                    developer_instructions=self._instructions(),
                    dynamic_tools=CB.dynamic_tool_specs(),
                )
                _panel_audit("thread_reuse", {"thread_id": self._thread_id, "owner": token})
                return self._thread_id
            except CB.CodexAppServerError as exc:
                _panel_audit("thread_reuse_failed",
                             {"thread_id": self._thread_id, "owner": token,
                              "error": str(exc)[:160]})
                self._thread_id = None
                self._turn_id = None
                self._thread_owner = None
        elif self._thread_id:
            # 块3：归属变了——旧 tid 属于另一个 app-server 进程（或另一条连接）。
            # 跨进程 resume 必然 -32602（块2 M5 实证）；这里**预判丢弃**，不发无效请求。
            _old_tid, _old_owner = self._thread_id, self._thread_owner
            self._thread_id = None
            self._turn_id = None
            self._thread_owner = None
            _panel_audit("thread_owner_changed",
                         {"thread_id": _old_tid, "owner_before": _old_owner,
                          "owner_now": token})
        # S1-P1：线程创建同样走路由，并包 owner_session。
        # 第④步：effort 已移除——thread/start（app-server v2）无该参数。
        # 路由白名单虽会拒收并落审计，但面板不该再塞非法参数（D4-1 / D4-2）。
        with policy.owner_session():
            result = api.run_task("codex_thread_new", {
                "model": _cfg.get("model") or None,
                "sandbox": _cfg.get("sandbox", "workspace-write"),
                "developer_instructions": self._instructions(),
                "dynamic_tools": CB.dynamic_tool_specs(),
                "ephemeral": bool(_cfg.get("ephemeral", False)),
            })
        payload = {}
        if isinstance(result, dict):
            _layer = result.get("gbt_result")
            if not isinstance(_layer, dict):
                _layer = result
            _inner = _layer.get("result") if isinstance(_layer, dict) else None
            if isinstance(_inner, dict):
                payload = _inner
        self._thread_id = (payload.get("thread") or {}).get("id")
        if not self._thread_id:
            raise RuntimeError("内核未返回会话标识")
        # 块3：建成后重取令牌——防止创建过程中共享连接被整体替换。
        self._thread_owner = _connection_token(CB.get_shared_server())
        _panel_audit("thread_rebuild",
                     {"thread_id": self._thread_id, "owner": self._thread_owner})
        return self._thread_id

    def _instructions(self) -> str:
        persona = (self.config.get("chat", {}) or {}).get("persona", "")
        return CB.default_developer_instructions(persona)

    def _run_fallback(self, text: str) -> None:
        self._ensure_fallback()
        if self._chat is None:
            self._set_activity("内核与备用大脑均不可用", thinking=False)
            self.bus.publish("error", detail=self._last_error_safe or "对话后端不可用")
            return

        def on_chunk(delta: str, _full: str) -> None:
            self.bus.publish("chunk", text=delta)

        def on_reply(reply: str) -> None:
            self.bus.publish("reply", text=reply)
            self._mind_observe("assistant_message", importance=0.42)
            self._set_activity("", thinking=False)

        self._set_activity("正在使用降级大脑…", thinking=True)
        try:
            self._chat.send(text, on_reply, on_chunk=on_chunk)
        except Exception as exc:  # noqa: BLE001
            self._set_activity("", thinking=False)
            self.bus.publish("error", detail=str(exc)[:240])

    def _on_codex_event(self, method: str, params: dict) -> None:
        params = params or {}
        if method == "item/agentMessage/delta":
            piece = str(params.get("delta") or "")
            if piece:
                self._delta_buf.append(piece)
                self.bus.publish("chunk", text=piece)
            return
        if method == "item/completed":
            item = params.get("item") or {}
            itype = item.get("type")
            if itype == "agentMessage":
                text = str(item.get("text") or "")
                phase = item.get("phase")
                if text and phase in ("final_answer", None):
                    self._replied_emitted = True
                    self.bus.publish("reply", text=text)
            elif itype == "commandExecution":
                command = _clip(item.get("command"), 100)
                if command:
                    self._set_activity(f"已执行：{command}")
            elif itype == "fileChange":
                self._set_activity("已更新文件")
            return
        if method == "item/started":
            kind = (params.get("item") or {}).get("type")
            text = {
                "commandExecution": "正在执行命令…",
                "fileChange": "正在修改文件…",
                "reasoning": "正在分析…",
            }.get(kind)
            if text:
                self._set_activity(text, thinking=True)
            return
        if method == "item/commandExecution/outputDelta":
            piece = _clip(params.get("delta"), 120)
            if piece:
                self._set_activity(piece)
            return
        if method == "turn/plan/updated":
            plan = params.get("plan") or params.get("steps") or []
            if isinstance(plan, list):
                self.bus.publish("plan", steps=plan)
            return
        if method == "turn/completed":
            turn = params.get("turn") or {}
            if not self._replied_emitted and self._delta_buf:
                self._replied_emitted = True
                self.bus.publish("reply", text="".join(self._delta_buf))
            status = str(turn.get("status") or "")
            self._set_activity("", thinking=False)
            self.bus.publish("turn_finished", status=status, turn_id=turn.get("id"))
            self._mind_observe(
                "task_succeeded" if status.lower() in {
                    "completed", "complete", "done", "success", "succeeded", "ok"
                } else "task_finished",
                status=status,
                importance=0.72,
                focus="deep",
            )
            return
        if method == "error":
            detail = params.get("message") or params.get("detail") or "未知错误"
            self._set_activity("", thinking=False)
            self.bus.publish("error", detail=str(detail)[:300])

    def _on_approval(self, method: str, params: dict):
        with self._lock:
            self._approval_seq += 1
            req_id = self._approval_seq
            slot = {
                "event": threading.Event(),
                "decision": None,
                "method": method,
            }
            self._approvals[req_id] = slot
        self.bus.publish(
            "approval",
            id=req_id,
            method=method,
            summary=self._describe_approval(method, params or {}),
        )
        if slot["event"].wait(300.0):
            return slot["decision"]
        with self._lock:
            self._approvals.pop(req_id, None)
        self.bus.publish("approval_expired", id=req_id)
        return None

    def resolve_approval(self, req_id: int, decision: str,
                        modified_text: str = "") -> dict:
        with self._lock:
            slot = self._approvals.pop(int(req_id), None)
        if slot is None:
            return {"ok": False, "error": "审批记录不存在"}
        choice = str(decision or "").lower()
        if choice in ("approve", "accept", "acceptforsession", "yes"):
            payload = self._approval_payload(slot.get("method"), choice)
        else:
            payload = self._approval_payload(slot.get("method"), "decline")
        slot["decision"] = payload
        slot["event"].set()
        if modified_text.strip():
            self.bus.publish(
                "approval_modified",
                id=int(req_id),
                text=_clip(modified_text, 500),
            )
        return {"ok": True}

    @staticmethod
    def _approval_payload(method: str, decision: str) -> dict:
        if method == "item/permissions/requestApproval":
            return {
                "permissions": {},
                "scope": "session" if decision == "acceptforsession" else "turn",
            }
        if method == "item/tool/requestUserInput":
            return {"answers": {}}
        if method == "mcpServer/elicitation/request":
            return {"action": "accept" if decision == "approve" else "decline"}
        return {"decision": "accept" if decision in {"approve", "accept"} else "decline"}

    @staticmethod
    def _describe_approval(method: str, params: dict) -> dict:
        if method == "item/commandExecution/requestApproval":
            return {
                "kind": "command",
                "title": "请求执行命令",
                "detail": _clip(params.get("command"), 600),
                "cwd": _clip(params.get("cwd"), 180),
            }
        if method == "item/fileChange/requestApproval":
            return {
                "kind": "file",
                "title": "请求修改文件",
                "detail": _clip(params.get("reason") or params.get("path"), 600),
            }
        if method == "item/permissions/requestApproval":
            return {
                "kind": "permissions",
                "title": "请求额外权限",
                "detail": _clip(params.get("reason"), 600),
            }
        if method == "item/tool/requestUserInput":
            return {
                "kind": "question",
                "title": "需要你确认",
                "detail": _clip(params.get("prompt") or params.get("question"), 600),
            }
        return {
            "kind": "other",
            "title": "需要你确认",
            "detail": _clip(params, 600),
        }

    def interrupt(self) -> dict:
        with self._lock:
            thread_id = self._thread_id
            turn_id = self._turn_id
        if not thread_id:
            return {"ok": False, "error": "内核未在运行"}
        try:
            # S1-P3：owner_session 包在 interrupt() 函数内部——
            # do_POST:1116 与 interrupt():877 同线程直调，包在函数内可覆盖任一调用方。
            with policy.owner_session():
                api.run_task("codex_interrupt",
                             {"thread_id": thread_id, "turn_id": turn_id})
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:200]}

    def new_thread(self) -> dict:
        with self._lock:
            self._thread_id = None
            self._turn_id = None
            self._thread_owner = None
        self.bus.publish("thread", id=None, fresh=True)
        return {"ok": True}

    # ------------------------------------------------------ social publish gate
    # 只读连接面：社交发布门禁自检。只报告本机事实与用户自登记的配置，
    # 不读取任何凭据内容，不引入发布/推流的执行路径（未接通就如实报未接通）。
    def social(self, op: str, payload: dict | None = None) -> dict:
        op = str(op or "status").strip().lower()
        payload = payload if isinstance(payload, dict) else {}
        if op == "publish":
            return self._social_publish(payload)
        if op != "status":
            return {"ok": False, "error": f"未知动作: {op}"}
        return self._social_status()

    def _social_publish(self, payload: dict) -> dict:
        """发布动作的门禁阶梯：每一级只说"当前缺的是这一级"。

        歧义一律 fail-closed：没声明平台、或声明了多个平台却没指定 platform，
        都不放行 —— 替调用方猜一个平台，等于把 A 的结论安到 B 头上。
        """
        status = self._social_status()
        if not status.get("config_verified"):
            if status.get("route") and not status.get("config_error"):
                return self._tentacle_refusal(status)
            return {
                "ok": False,
                "gate": "unconnected",
                "platform": "",
                "blocked_reason": status.get("blocked_reason") or "",
                "error": "门禁未接通：先完成应用登记、权限过审、账号授权三步；本舱区不做任何绕行。",
            }
        blocks = status.get("platforms") or []
        if not blocks:
            return {
                "ok": False,
                "gate": "no_platform_declared",
                "platform": "",
                "declared": [],
                "error": "配置里没有声明任何平台：不知道这条成片要发到哪，本舱区一律不放行。",
            }
        declared = [block["id"] for block in blocks]
        by_id = {block["id"]: block for block in blocks}
        wanted = str(payload.get("platform") or "").strip().lower()
        if wanted and wanted not in by_id:
            return {
                "ok": False,
                "gate": "unknown_platform",
                "platform": wanted,
                "declared": declared,
                "error": f"未声明的平台：{wanted}。本舱区只认配置里声明过的平台。",
            }
        if not wanted:
            if len(blocks) > 1:
                return {
                    "ok": False,
                    "gate": "platform_required",
                    "platform": "",
                    "declared": declared,
                    "error": "声明了多个平台：必须显式指定 platform，本舱区不替你挑一个。",
                }
            target = blocks[0]
        else:
            target = by_id[wanted]

        probe = target.get("capability_probe") or {}
        if not target.get("publish_allowed"):
            if target.get("route"):
                return self._tentacle_refusal(status, target)
            return {
                "ok": False,
                "gate": "unconnected",
                "platform": target["id"],
                "blocked_reason": status.get("blocked_reason") or "",
                "error": "门禁未接通：先完成应用登记、权限过审、账号授权三步；本舱区不做任何绕行。",
            }
        if not target.get("credential_present"):
            return {
                "ok": False,
                "gate": "credential_missing",
                "platform": target["id"],
                "credential_field": target.get("credential_field") or "",
                "error": "凭据未登记：授权令牌不在本机，发布链路即使实现也起不来。",
            }
        if probe.get("status") != "ok":
            return {
                "ok": False,
                "gate": "capability_unverified",
                "platform": target["id"],
                "capability_probe": probe,
                "error": ("能力未核验（%s）：%s"
                          % (probe.get("status") or "unknown",
                             probe.get("reason") or "没有可用的只读探针")),
            }
        # 这一级要在"探针新鲜通过"之后才可达 —— 门禁与能力都真过了，
        # 才轮得到说"只差执行链路"。
        return {
            "ok": False,
            "gate": "gate_passed_impl_missing",
            "platform": target["id"],
            "implemented": False,
            "capability_probe": probe,
            "error": "门禁与能力均已证实，但发布执行链路尚未实现：需接入分片上传与状态轮询。",
        }

    def _tentacle_refusal(self, status: dict, target: dict | None = None) -> dict:
        """触手路由的拒绝形态：把"为什么不是官方门禁"和"哪一段不做"分开写清。

        这条路由没有可证伪的探针（平台对自动化是静默降权），所以本舱区不为它开放
        无人值守。拒绝的永远只是这一段行为，不是这个人 —— 人在场的触手投递、
        本机的成片生产与素材整理，一条都没被这里挡住。
        """
        block = target or {}
        label = block.get("route_label") or status.get("route_label") or "本机触手"
        return {
            "ok": False,
            "gate": "tentacle_not_implemented",
            "platform": block.get("id") or status.get("focus") or "",
            "route": block.get("route") or status.get("route") or "",
            "route_label": label,
            "unattended_enabled": False,
            "blocked_reason": status.get("blocked_reason") or "",
            "error": ("%s路由：官方登记/过审/授权三步在这条路由上不适用；"
                      "触手投递链路尚未接通；本舱区不做绕过平台风控的无人值守发布；"
                      "发布/开播这一下需要人在场。" % label),
        }

    def _social_status(self) -> dict:
        import shutil as _shutil

        base = Path(__file__).resolve().parent
        config_path = base / "social.json"
        config: dict = {}
        config_error = ""
        if config_path.is_file():
            try:
                loaded = json.loads(config_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    config = loaded
                else:
                    # 文件在、内容不是对象：属于"核验失败"，不能当"没配"。
                    config_error = "social.json 顶层不是对象"
            except OSError as exc:
                config_error = f"social.json 不可读：{str(exc)[:120]}"
            except ValueError as exc:
                config_error = f"social.json 不是合法 JSON：{str(exc)[:120]}"
        # 三态：文件不存在 / 存在但不可信 / 存在可信。
        # 前两态一律 known=False —— 没核到的东西不许写成"已证明为假"。
        config_present = config_path.is_file()
        config_verified = config_present and not config_error

        probe_ttl = social_platforms.DEFAULT_PROBE_TTL_SECONDS
        raw_ttl = config.get("probe_ttl_seconds")
        if isinstance(raw_ttl, int) and not isinstance(raw_ttl, bool) and raw_ttl > 0:
            probe_ttl = raw_ttl

        # 声明与实测分家：声明读 sources.json 的 channels，实测读 state/probe/<id>.json。
        # 只有一处优先级，避免"两个真相"：
        #   1) social.json 显式写了 platforms -> 以它为准（现行形状，兼容保留）
        #   2) 没写 platforms -> 用 sources.json 的 channels 兜底
        #   3) 都没有 -> 空列表
        probe_dir = base.parent / "state" / "probe"
        token_dir = base.parent / "state" / "tokens"
        declared_rows: list = []
        sources_error = ""
        sources_path = base.parent / "sources.json"
        if sources_path.is_file():
            try:
                raw_sources = json.loads(sources_path.read_text(encoding="utf-8"))
            except OSError as exc:
                sources_error = "sources.json 不可读：%s" % str(exc)[:120]
            except ValueError as exc:
                sources_error = "sources.json 不是合法 JSON：%s" % str(exc)[:120]
            else:
                rows = raw_sources.get("channels") if isinstance(raw_sources, dict) else None
                if isinstance(rows, list):
                    declared_rows = [row for row in rows
                                     if isinstance(row, dict)
                                     and str(row.get("id") or "").strip()]
                else:
                    sources_error = "sources.json 的 channels 不是数组"

        entries: list = []
        schema = "unverified"
        if config_verified:
            entries, schema, schema_error = social_platforms.declared_platforms(config)
            if schema_error:
                config_error = schema_error
                config_verified = False
                entries = []
                schema = "unverified"
        elif "platforms" not in config and declared_rows:
            # 有登记表、没有 social.json：按声明建卡。
            # 声明门禁仍报"未核验"（应用登记/过审/授权是 social.json 的事实），
            # 探针另算 —— 所以卡片会出现「已登记 · 未探测」，而不是"未登记"。
            for row in declared_rows:
                pid = str(row.get("id") or "").strip().lower()
                spec = social_platforms.spec_for(pid)
                if spec is None:
                    # 登记表自带的参考数据：不猜，照它写的用。
                    spec = {
                        "id": pid,
                        "label": str(row.get("name") or pid),
                        "official_api": bool(row.get("official_api")),
                        "delivery": str(row.get("publish_flow") or ""),
                        "audit_gate": str(row.get("gate") or ""),
                        "daily_limit": None,
                        "credential_field": str(row.get("credential_field") or ""),
                    }
                cred_here = (token_dir / ("%s.json" % pid)).is_file()
                entries.append({
                    "id": pid,
                    "label": str(row.get("name") or pid),
                    "flags": {flag: (flag == "credential_registered" and cred_here)
                              for flag in social_platforms.GATE_FLAGS},
                    "spec": spec,
                    "probe_raw": None,
                    # 路由与无人值守都来自登记表的声明，必须一起带出来：
                    # 缺了它们，下面那四格门禁会被读成"还没做"，而不是"这条路由不走它"。
                    "route": social_platforms.normalize_route(row.get("route")),
                    "unattended_declared": "unattended_allowed" in row,
                    "unattended_allowed": bool(row.get("unattended_allowed")),
                    # 意愿声明：只影响一个标记，不参与门禁计算。
                    "enabled_declared": "enabled" in row,
                    "enabled": bool(row.get("enabled")),
                })
            schema = "sources"

        def _gate(gid, label, value, missing_hint, ok_hint, false_hint):
            """三态门禁：known=False 表示本机未能核验，ok 此时恒为 False。"""
            if not config_verified:
                why = config_error or "本机没有 social.json"
                return {"id": gid, "label": label, "ok": False, "known": False,
                        "verified": False, "applicable": True,
                        "hint": f"未核验（{why}）：{missing_hint}"}
            return {"id": gid, "label": label, "ok": bool(value), "known": True,
                    "verified": True, "applicable": True,
                    "hint": ok_hint if value else false_hint}

        def _probe_label(detail):
            """四态文案：已登记但没探过，不许写成「未登记」，也不算绿。"""
            return {
                "ok": "已探测 · 通过",
                "stale": "已登记 · 探测过期",
                "failed": "已探测 · 未通过",
                "unprobed": "已登记 · 未探测",
                "spec_unknown": "已登记 · 无探针定义",
                "unsupported": "无官方发布接口",
            }.get(str(detail or ""), "已登记 · 未探测")

        def _probe_gate(probe):
            """探针门禁：过期 = 未核验，不是失败 —— 上一次通过不是永久证明。"""
            state = str(probe.get("status") or "unknown")
            detail = str(probe.get("state") or "unknown")
            reason = str(probe.get("reason") or "无法核验")
            if state == "ok":
                return {"id": "probe", "label": "能力探测", "ok": True, "known": True,
                        "verified": True, "hint": "能力已证实：" + reason}
            if state == "stale":
                return {"id": "probe", "label": "能力探测", "ok": False, "known": False,
                        "verified": False, "hint": "未核验（探测过期）：" + reason}
            if detail in ("unprobed", "spec_unknown"):
                # 已登记、没探过：如实说"没探过"，不许说"没这件东西"。
                return {"id": "probe", "label": "能力探测", "ok": False, "known": False,
                        "verified": False,
                        "hint": _probe_label(detail) + "：" + reason}
            return {"id": "probe", "label": "能力探测", "ok": False, "known": False,
                    "verified": False, "hint": "未核验（" + reason + "）"}

        # 门禁一处分权，不再散成 if-else；加门禁 = 加一行。
        gate_text = (
            ("app", "应用登记", "app_registered",
             "应用是否登记未知", "应用已登记",
             "未登记：先在开发者平台创建应用并添加发布类产品"),
            ("scope", "权限过审", "scope_audited",
             "发布权限是否过审未知", "发布权限已过审",
             "未过审：此状态下发出去的内容只能私密可见"),
            ("auth", "账号授权", "account_authorized",
             "目标账号是否授权未知", "目标账号已授权本应用",
             "未授权：需要目标账号授权后才可代它发布"),
            ("cred", "凭据登记", "credential_registered",
             "授权凭据是否在本机未知", "凭据已登记（只报存在，不读内容）",
             "未登记：发布令牌不在本机，链路即使实现也起不来"),
        )
        declaration_ids = ("app", "scope", "auth")

        def _gates_for(flags, route=""):
            """四门门禁；触手路由下这四门全部不适用。

            不适用 != 未核验 != 通过，三者必须能分开读：说的是"这条路由根本不经过
            这道闸"，不是"还没做"，更不是"已经过了"。写成"未核验"会让人去补一件
            这件路由上不存在的事；写成绿就是伪造。

            优先级：配置读取失败 > 路由不适用。一个读不出来的 social.json 本身就是
            本机配置自相矛盾，那时候首要事实是"配置不可信" —— 先报读失败，
            不能让它被一句"不适用"盖过去。
            """
            if route and not config_error:
                why = social_platforms.route_label(route)
                return [{"id": gid, "label": label, "ok": False, "known": False,
                         "verified": False, "applicable": False,
                         "hint": f"不适用（{why}路由）：这条路由不经过官方接口的{label}"}
                        for gid, label, _key, _m, _o, _f in gate_text]
            return [_gate(gid, label, flags.get(key), missing, ok_hint, false_hint)
                    for gid, label, key, missing, ok_hint, false_hint in gate_text]

        def _unattended_gate(declared, allowed):
            """无人值守：本舱区恒不开放 —— 这是"不做"，不是"待办"。

            原因不是懒。触手路由没有可证伪的探针：官方令牌过期给 401，可判、可退避；
            而平台对自动化是静默降权，本机看不到任何异常，直到号废。一条判不出成败的
            路，放它无人值守地跑，等于把账号当耗材。所以这一格恒为不开放；
            登记表里就算写了 true，也只如实说"声明为开放、本舱区不启用"。
            """
            if not declared:
                return {"id": "unattended", "label": "无人值守", "ok": False,
                        "known": False, "verified": False, "applicable": True,
                        "hint": "未声明：登记表没写无人值守是否开放，按未开放处理。"}
            if allowed:
                return {"id": "unattended", "label": "无人值守", "ok": False,
                        "known": True, "verified": True, "applicable": True,
                        "hint": ("登记表声明为开放，但本舱区不启用：无人值守的发布/开播"
                                 "要绕平台风控，本舱区不做；这一下需要人在场。")}
            return {"id": "unattended", "label": "无人值守", "ok": False,
                    "known": True, "verified": True, "applicable": True,
                    "hint": "未开放（登记表声明）：发布/开播这一下需要人在场。"}

        if not config_verified and not entries:
            blind_probe = {"status": "unknown", "known": False,
                           "reason": config_error or "本机没有 social.json",
                           "checked_at": None, "checked_age_seconds": None,
                           "ttl_seconds": probe_ttl}
        else:
            blind_probe = None

        platforms = []
        for entry in entries:
            flags = entry["flags"]
            spec = entry["spec"]
            route = str(entry.get("route") or "")
            unattended_declared = bool(entry.get("unattended_declared"))
            unattended_allowed = bool(entry.get("unattended_allowed"))
            enabled_declared = bool(entry.get("enabled_declared"))
            enabled = bool(entry.get("enabled"))
            credential_present = bool(flags.get("credential_registered"))
            probe_raw = entry.get("probe_raw")
            probe_source = "social.json" if probe_raw is not None else "none"
            store = probe_dir / ("%s.json" % entry["id"])
            loaded_probe = None
            if store.is_file():
                try:
                    loaded_probe = json.loads(store.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    loaded_probe = None
                # 落盘优先：state/probe 是实测落点，内嵌字段只作旧形状兜底。
                probe_source = "state/probe" if isinstance(loaded_probe, dict) else "state/probe(不可解析)"
            if isinstance(loaded_probe, dict):
                probe_raw = loaded_probe
            probe = blind_probe or social_platforms.evaluate_probe(
                spec, credential_present, probe_raw, probe_ttl, route=route)
            gates = _gates_for(flags, route) + [_probe_gate(probe)]
            if route:
                gates.append(_unattended_gate(unattended_declared, unattended_allowed))
            platforms.append({
                "id": entry["id"],
                "label": entry["label"],
                # spec_known=False 时下面五个字段一律为空：不知道就是空。
                "spec_known": spec is not None,
                "official_api": spec["official_api"] if spec else None,
                "delivery": spec["delivery"] if spec else "",
                "audit_gate": spec["audit_gate"] if spec else "",
                "daily_limit": spec["daily_limit"] if spec else None,
                "credential_field": spec["credential_field"] if spec else "",
                "gates": gates,
                "credential_present": credential_present,
                # 三门声明门禁 = "平台闸"；publish_ready 还要求凭据与探针都过。
                "publish_allowed": config_verified and all(
                    gate["ok"] for gate in gates if gate["id"] in declaration_ids),
                "public_allowed": config_verified and all(
                    gate["ok"] for gate in gates if gate["id"] in declaration_ids),
                "capability_probe": probe,
                "probe_state": probe.get("state") or "unknown",
                "probe_source": probe_source,
                "status_label": _probe_label(probe.get("state")),
                "publish_ready": config_verified and all(gate["ok"] for gate in gates),
                # 路由与无人值守决定上面那几格该怎么读，必须和它们一起报，
                # 否则前端只能看到一个孤零零的"不适用"。
                "route": route,
                "route_label": social_platforms.route_label(route),
                "route_note": social_platforms.route_note(route),
                "unattended_declared": unattended_declared,
                "unattended_allowed": unattended_allowed,
                "unattended_enabled": False,
                # 意愿声明：显式 false 才印「未启用」；true 与未声明都不印 ——
                # 15 张卡上挂一排「已启用」是零信息量的噪声。
                # 这三个字段不参与上面任何一条门禁的计算。
                "enabled_declared": enabled_declared,
                "enabled": enabled,
                "enabled_label": (social_platforms.ENABLED_LABEL_DISABLED
                                  if enabled_declared and not enabled else ""),
            })

        by_id = {block["id"]: block for block in platforms}
        focus_id = str(config.get("focus") or "").strip().lower()
        if focus_id not in by_id:
            focus_id = platforms[0]["id"] if platforms else ""
        focus = by_id.get(focus_id)
        flags_by_id = {entry["id"]: entry["flags"] for entry in entries}
        focus_flags = flags_by_id.get(focus_id) or {}

        # 顶层字段只描述"当前焦点平台"，绝不跨平台聚合 —— 聚合会把
        # "A 过了、B 没过"压成一个数，正是拿 A 的证据去证 B。
        publish_allowed = bool(focus and focus["publish_allowed"])
        public_allowed = bool(focus and focus["public_allowed"])
        credential_present = bool(focus["credential_present"]) if focus else False
        focus_probe = focus["capability_probe"] if focus else (
            blind_probe or {"status": "unknown", "known": False,
                            "reason": "没有声明任何平台，无探针",
                            "checked_at": None, "checked_age_seconds": None,
                            "ttl_seconds": probe_ttl})
        publish_ready = bool(focus and focus["publish_ready"])
        focus_route = focus["route"] if focus else ""
        focus_route_label = focus["route_label"] if focus else ""

        if focus_route and not config_error and not publish_allowed:
            # 触手路由下，没核验的那份配置（social.json）正是这条路由不用的那份：
            # 拿"本机配置未核验"当首要原因，会把人指去补一件跟这条路由无关的事。
            # 但配置**读失败**仍然优先 —— 那时首要事实是"配置不可信"。
            blocked_reason = (
                "%s路由：官方三步闸不适用；触手投递链路尚未接通，"
                "且无人值守未启用 —— 发布/开播这一下需要人在场。" % focus_route_label)
        elif not config_verified:
            blocked_reason = "门禁未接通：本机配置未核验，一律不放行。"
        elif not platforms:
            blocked_reason = "门禁未接通：配置里没有声明任何平台，不知道要发到哪。"
        elif not publish_allowed:
            blocked_reason = "门禁未接通：发布通道暂不可用，先补齐上面的三步前置。"
        elif not credential_present:
            blocked_reason = "门禁已接通，但凭据未登记：发布链路还缺授权令牌。"
        elif focus_probe.get("status") != "ok":
            # 过期与"没探过"在这里同一处置：都是未核验，都不放行。
            blocked_reason = "门禁已接通、凭据已登记，但能力未核验（%s）：%s" % (
                focus_probe.get("status") or "unknown",
                focus_probe.get("reason") or "")
        else:
            blocked_reason = ""

        drafts_dir = str(config.get("drafts_dir") or "").strip()
        ffmpeg_path = _shutil.which("ffmpeg")

        return {
            "ok": True,
            "schema": schema,
            "focus": focus_id,
            "focus_label": focus["label"] if focus else "",
            "platform_count": len(platforms),
            "platforms": platforms,
            "connected": publish_allowed,
            "publish_allowed": publish_allowed,
            "public_allowed": public_allowed,
            "publish_ready": publish_ready,
            "credential_present": credential_present,
            "capability_probe": focus_probe,
            "probe_ttl_seconds": probe_ttl,
            "route": focus_route,
            "route_label": focus_route_label,
            "unattended_enabled": False,
            "unattended_note": "无人值守在本舱区恒不启用：发布/开播这一下需要人在场。",
            "private_draft_mode": bool(config_verified
                                       and focus_flags.get("account_authorized")
                                       and not focus_flags.get("scope_audited")),
            # 兼容层：这里恰好三条声明门禁、键集与旧前端一致，不含 "cred"/"probe" ——
            # 旧前端把就绪数硬编码成 /3，塞进去会印出 "4/3"。
            "gates": ([gate for gate in focus["gates"] if gate["id"] in declaration_ids]
                      if focus else _gates_for({})[:3]),
            "drafts": self._social_drafts(base, drafts_dir),
            "drafts_ready": bool(drafts_dir),
            "ffmpeg": {
                "available": bool(ffmpeg_path),
                "path": Path(ffmpeg_path).name if ffmpeg_path else None,
            },
            "stream_key_ready": bool(config.get("stream_key_ready")),
            # 成因分列，别把"平台不给"写成"我们没做"：
            #   推流凭据 = 创作者在客户端自助获取后登记（本面板只读该登记结果）；
            #   开播/下播 = 平台未提供接口，只能客户端手动，**不是待办**。
            "stream_control": "client_manual",
            "chat_supported": False,
            "blocked_reason": blocked_reason,
            # 只增字段，不改既有字段语义 —— 前端不认也无副作用。
            "config_present": config_present,
            "config_verified": config_verified,
            "config_error": config_error,
            "config_hint": config_path.name,
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


    def _social_drafts(self, base: Path, raw_dir: str) -> list:
        if not raw_dir:
            return []
        try:
            target = Path(raw_dir)
            if not target.is_absolute():
                target = base / raw_dir
            target = target.resolve()
            if not target.is_dir():
                return []
            candidates = [
                item for item in target.iterdir()
                if item.is_file()
                and item.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
            ]
            candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        except OSError:
            return []
        rows = []
        for item in candidates[:20]:
            try:
                stat = item.stat()
            except OSError:
                continue
            rows.append({
                "id": item.name,
                "name": item.stem,
                "ext": item.suffix.lower().lstrip("."),
                "size_mb": round(stat.st_size / (1024 * 1024), 1),
                "modified": time.strftime("%m-%d %H:%M", time.localtime(stat.st_mtime)),
            })
        return rows

    # ------------------------------------------------------ research sources
    # 只读连接面：调研信源状态。登记读 sources.json、最近一次采集结局读 state/runs/、
    # 最后一次成功读 state/last_seen.json。无采集器、不发起任何出站请求 ——
    # 这里只回答"本机现在知道什么"，不知道就说不知道。
    def research(self, op: str, payload: dict | None = None) -> dict:
        op = str(op or "status").strip().lower()
        if op != "status":
            return {"ok": False, "error": f"未知动作: {op}"}
        return self._research_status()

    def _research_status(self) -> dict:
        base = Path(__file__).resolve().parent
        sources_path = base.parent / "sources.json"
        sources_present = sources_path.is_file()
        sources_error = ""
        doc: dict = {}
        if sources_present:
            try:
                loaded = json.loads(sources_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    doc = loaded
                else:
                    # 文件在、内容不是对象：核验失败，不等于"没配"。
                    sources_error = "sources.json 顶层不是对象"
            except OSError as exc:
                sources_error = "sources.json 不可读：%s" % str(exc)[:120]
            except ValueError as exc:
                sources_error = "sources.json 不是合法 JSON：%s" % str(exc)[:120]
        else:
            sources_error = "本机没有 sources.json"
        if not sources_error and not isinstance(doc.get("research"), list):
            sources_error = "sources.json 的 research 不是数组"
        sources_verified = sources_present and not sources_error

        result = research_status.build_status(
            doc if sources_verified else {},
            run_dir=base.parent / "state" / "runs",
            last_seen_path=base.parent / "state" / "last_seen.json",
        )
        counts = result["counts"]
        return {
            "ok": True,
            "schema": "sources" if sources_verified else "unverified",
            "sources_present": sources_present,
            "sources_verified": sources_verified,
            "sources_error": sources_error,
            "sources_hint": sources_path.name,
            # 实测层与水位层的落点原样报出来，方便对着盘核。
            "run_dir": "state/runs",
            "run_dir_present": result["run_dir_present"],
            "watermark_file": "state/last_seen.json",
            "watermark_present": result["last_seen_present"],
            "watermark_error": result["last_seen_error"],
            "watermark_entries": result["last_seen_entries"],
            "count": result["count"],
            "sources": result["sources"],
            "counts": counts,
            "failed_count": counts.get(research_status.STATE_FAILED, 0),
            "unreadable_count": counts.get(research_status.STATE_UNREADABLE, 0),
            "stale_count": counts.get(research_status.STATE_STALE, 0),
            "ok_count": counts.get(research_status.STATE_OK, 0),
            "never_run_count": counts.get(research_status.STATE_NEVER_RUN, 0),
            "disabled_count": counts.get(research_status.STATE_DISABLED, 0),
            "summary": result["summary"],
            # 判据 E：一次采集的汇总报告（派生视图，不落盘）。
            # 标红读 severity（机器可读），不靠文案里有没有「失败」两个字。
            "run_report": result["run_report"],
            "severity": result["run_report"]["severity"],
            "failed_sources": result["run_report"]["failed_sources"],
            "note": ("声明 / 实测 / 水位分三处：登记读 sources.json，最近一次采集结局读 "
                     "state/runs/<id>.json，最后一次成功读 state/last_seen.json。"
                     "单源采集失败只让那一行显示失败，不连坐、也不清水位。"),
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    # --------------------------------------------------------------- quick ops
    def quick(self, action: str, payload: dict | None = None) -> dict:
        action = str(action or "").strip().lower()
        payload = dict(payload or {})
        routes = {
            "screen": ("tentacle", {"action": "see"}),
            "logs": ("selfscan", {}),

            # 只读连接面：把已有后端接到面板，不引入任何执行/写入路径
            "mirror_status": ("mirror_status", {"include_rehearsal": True}),
            "sense_status": ("tentacle_status", {}),
            "workflow_status": ("wf_status", {"limit": 10}),
            "life_status": ("life", {"op": "status"}),
            "mind_pulse": ("mind", {"op": "pulse"}),
            "bluetooth_status": ("bluetooth", {"op": "status"}),
            "bluetooth_scan": ("bluetooth", {
                "op": "scan",
                "timeout": min(20.0, max(1.0, float(payload.get("timeout", 5.0)))),
                "name_filter": payload.get("name_filter") or None,
            }),
            "bluetooth_classic": ("bluetooth", {"op": "classic"}),
            "bluetooth_connect": ("bluetooth", {
                "op": "connect",
                "address": payload.get("address"),
                "timeout": min(30.0, max(2.0, float(payload.get("timeout", 20.0)))),
            }),
            "bluetooth_read": ("bluetooth", {
                "op": "read",
                "address": payload.get("address"),
                "char_uuid": payload.get("char_uuid"),
            }),
            "bluetooth_write": ("bluetooth", {
                "op": "write",
                "address": payload.get("address"),
                "char_uuid": payload.get("char_uuid"),
                "value_hex": payload.get("value_hex"),
            }),
        }
        route = routes.get(action)
        if not route:
            return {"ok": False, "error": f"未知快捷动作: {action}"}
        kind, request = route
        if kind == "bluetooth" and request.get("op") == "write" and not payload.get("confirm"):
            self.bus.publish("bluetooth_confirm", action=action, payload=request)
            return {"ok": True, "needs_confirmation": True}
        self._set_activity(f"正在执行 {action}…")

        def run() -> None:
            try:
                with policy.owner_session():
                    result = api.run_task(kind, request)
                body = result.get("gbt_result", result) if isinstance(result, dict) else result
                self.bus.publish("quick_result", action=action, result=body)
                if kind == "bluetooth":
                    self.bus.publish("bluetooth", action=action, result=body)
            except Exception as exc:  # noqa: BLE001
                self.bus.publish("error", action=action, detail=str(exc)[:240])
            finally:
                self._set_activity("")

        threading.Thread(target=run, name=f"gbt-holo-{action}", daemon=True).start()
        return {
            "ok": True,
            "accepted": True,
            "path": "route",
            "deferred": True,
        }

    # ------------------------------------------------------------------
    # 能力总目录 + 通用调用口
    # 只做"运输"：目录直接读她的注册表，权限/作用域/审计仍走 api.run_task 那一层，
    # 面板不复制任何一份能力表，也不绕过 policy。
    # ------------------------------------------------------------------

    def capabilities(self) -> dict:
        """能力总目录（只读）：数据源是她自己的 caps_registry。"""
        try:
            from gbt_allinone.caps_registry import all_caps
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"读不到能力注册表: {exc}"}

        gate = _side_effect_kinds()
        items = []
        for row in all_caps():
            kind = str(row.get("name") or "")
            enabled = row.get("status") == "enabled"
            items.append({
                "kind": kind,
                "domain": str(row.get("domain") or ""),
                "desc": str(row.get("desc") or "")[:180],
                "enabled": enabled,
                # 2026-09-23 解禁后必须把**状态**也交出去：`enabled=False` 现在有两种完全不同的原因 ——
                # `unimplemented`（只有名字、没有实现）与（若将来再有）`disabled`（被策略拒）。
                # 只给 bool，读的人分不清"没做"和"被挡住"，就会去琢磨"怎么开门"。
                "status": str(row.get("status") or ""),
                "reason": str(row.get("reason") or ""),
                # 需要二次确认 = 在她那份"侧效应"名单里（名单缺失则全部要求确认）
                "needs_confirmation": enabled and (gate is None or kind in gate),
                # 入参契约（R-H98）：空调用不成立的能力必须在目录里如实标出来，
                # 否则点一下就是一次 `{}` 空调用 —— 报的错谁也看不懂。
                "requires_params": bool(row.get("requires_params")),
                "params": list(row.get("params") or []),
                "params_hint": str(row.get("params_hint") or ""),
            })
        domains: dict[str, int] = {}
        for row in items:
            domains[row["domain"]] = domains.get(row["domain"], 0) + 1
        return {
            "ok": True,
            "total": len(items),
            "enabled": sum(1 for row in items if row["enabled"]),
            "disabled": sum(1 for row in items if not row["enabled"]),
            "domains": dict(sorted(domains.items())),
            "items": items,
            # 🔴 通道总账：`total` 只是**注册表**那一条通道的数。
            # 外面还有本面板自身路由面与 Ark 云端能力面。不把这件事写出来，
            # 只看 `total` 的人会以为"框架一共就这么多个能力" —— 那是误读，不是读数。
            "channels": {
                "registry": len(items),
                "app_routes": len(APP_SURFACE),
                "app_pending": len(APP_PENDING),
                "ark": len((self._ark_surface().get("skills") or [])),
            },
            "total_all_channels": (len(items) + len(APP_SURFACE) + len(APP_PENDING)
                                   + len((self._ark_surface().get("skills") or []))),
            "channels_note": ("能力分四条通道：registry=注册表能力位（走 run_task 唯一门）· "
                              "app_routes=本面板自身路由 · app_pending=契约已立实体未建 · "
                              "ark=Ark 云端（外部 CLI，不走 run_task）。"
                              "`total` 只数第一条，别拿它当全量。"),
            # APP 自身的能力面（不属于她的注册表）+ 契约已立但实体未建的位子
            "app": {
                "ark": self._ark_surface(),
                "routes": [dict(row) for row in APP_SURFACE],
                "pending": [dict(row) for row in APP_PENDING],
            },
        }

    # ------------------------------------------------------------------
    # Ark 云端能力面（外部 CLI）
    # 单一声明：holo_pet/ark_surface.json（由 tools/codex-scripts/make_ark_surface.py 现读技能目录生成）。
    # 面板**只读这一份**，不持有第二份真相；也不在这里起进程（见该脚本里的说明）。
    # ------------------------------------------------------------------
    _ark_cache: dict | None = None
    _ark_cache_stamp: tuple = ()

    def _ark_surface(self) -> dict:
        path = _HERE / "ark_surface.json"
        try:
            stamp = (path.stat().st_mtime_ns, path.stat().st_size)
        except OSError as exc:
            return {"ok": False, "error": f"读不到 Ark 能力面声明: {exc}",
                    "how": "跑 python tools/codex-scripts/make_ark_surface.py 生成它"}
        if self._ark_cache is None or self._ark_cache_stamp != stamp:
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": f"Ark 能力面声明解析失败: {exc}"}
            skills = list(loaded.get("skills") or [])
            loaded["ok"] = True
            loaded["total"] = len(skills)
            loaded["with_cli_help"] = sum(1 for s in skills if s.get("cli_help"))
            self._ark_cache = loaded
            self._ark_cache_stamp = stamp
        return self._ark_cache

    def capability(self, kind: str, payload: dict | None = None, confirm: bool = False) -> dict:
        """通用调用口：只放行注册表里 enabled 且 safe 的能力；侧效应能力要确认。"""
        kind = str(kind or "").strip()
        request = dict(payload or {})
        if not kind:
            return {"ok": False, "error": "缺少 kind"}
        try:
            from gbt_allinone.caps_registry import BENIGN_CAPS
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"读不到能力注册表: {exc}"}

        # 2026-09-23 Owner 令：禁止已全部解开，面板侧与 api.py 同步。
        # 那 11 个名字**没有实现**（不在 BENIGN_CAPS、全仓无实现文件）⇒ 落进下面的
        # "未知能力"分支，得到**如实**的"没做"，而不是旧消息那种"被策略挡住"的误导。
        spec = BENIGN_CAPS.get(kind)
        if not spec:
            return {"ok": False, "error": f"未知能力: {kind}"}
        if not spec.get("safe"):
            return {"ok": False, "error": "该能力未标记 safe，面板不代调"}

        # ── 入参契约（R-H98 修根源）──
        # 病根：面板只发 {kind, confirm}，带参数的能力点下去 = 一次空调用。
        # 处置：缺必需参数时**当场如实拒绝**（不跑、不猜、不按默认值乱跑），并把缺哪几个说清楚。
        from gbt_allinone.caps_registry import params_hint, required_params
        need = required_params(kind)
        missing = [p for p in need if not str(request.get(p) or "").strip()]
        if missing:
            return {
                "ok": False,
                "kind": kind,
                "requires_params": True,
                "params": need,
                "missing_params": missing,
                "hint": params_hint(kind),
                "error": f"该能力需要参数：{'、'.join(missing)}（面板不代猜；请从终端/脚本传参或改用带参数的调用口）",
            }

        gate = _side_effect_kinds()
        if (gate is None or kind in gate) and not confirm:
            self.bus.publish("cap_confirm", kind=kind, payload=request)
            return {"ok": True, "needs_confirmation": True, "kind": kind}

        request_id = uuid.uuid4().hex[:10]
        self._set_activity(f"正在执行 {kind}…")

        def run() -> None:
            try:
                with policy.owner_session():
                    result = api.run_task(kind, request)
                body = result.get("gbt_result", result) if isinstance(result, dict) else result
                self.bus.publish("cap_result", kind=kind, request_id=request_id, result=body)
            except Exception as exc:  # noqa: BLE001
                self.bus.publish("error", action=kind, detail=str(exc)[:240])
            finally:
                self._set_activity("")

        threading.Thread(target=run, name=f"gbt-holo-cap-{kind}", daemon=True).start()
        return {
            "ok": True,
            "accepted": True,
            "path": "capability",
            "deferred": True,
            "request_id": request_id,
        }

    # ------------------------------------------------------------------
    # 旁观者（独立观察位）+ 项目树
    # 契约：`.scratch/旁观者契约稿.md`（甲案 · 严格只读）· `.scratch/DSH旁观者接入设计稿.md`
    # 三条不动的纪律：① 方向只有"小土豆 → DSH"；② 旁观者零执行权（这里也全是只读）；
    # ③ 起 `--profile sdk` / 装包 / 联网 = 敏感档，等风哥批 —— 所以本处**只取证、不启动**。
    # ------------------------------------------------------------------

    def tree(self, depth: int = 3, limit: int = 400) -> dict:
        """项目树（只读）：只走目录名与文件大小，**不读任何文件内容**。"""
        depth = max(1, min(6, int(depth or 3)))
        limit = max(20, min(4000, int(limit or 400)))
        per_dir = 80
        budget = {"nodes": 0, "truncated": False}

        def walk(path: Path, level: int) -> dict:
            node = {"name": path.name or str(path), "kind": "dir",
                    "dirs": 0, "files": 0, "bytes": 0, "children": []}
            if budget["nodes"] >= limit:
                budget["truncated"] = True
                node["collapsed"] = True
                return node
            budget["nodes"] += 1
            try:
                entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            except OSError:
                node["error"] = "unreadable"
                return node
            listed = 0
            for entry in entries:
                if budget["nodes"] >= limit:
                    budget["truncated"] = True
                    break
                if listed >= per_dir:
                    node["more"] = len(entries) - listed
                    budget["truncated"] = True
                    break
                listed += 1
                budget["nodes"] += 1
                name = entry.name
                try:
                    is_dir = entry.is_dir()
                except OSError:
                    continue
                if is_dir:
                    node["dirs"] += 1
                    if name in _TREE_NOISE_DIRS:
                        node["children"].append({"name": name, "kind": "dir",
                                                 "skipped": True, "children": []})
                        continue
                    if level >= depth:
                        node["children"].append({"name": name, "kind": "dir",
                                                 "collapsed": True, "children": []})
                        continue
                    child = walk(entry, level + 1)
                    node["dirs"] += child.get("dirs", 0)
                    node["files"] += child.get("files", 0)
                    node["bytes"] += child.get("bytes", 0)
                    node["children"].append(child)
                else:
                    size = 0
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        pass
                    node["files"] += 1
                    node["bytes"] += size
                    node["children"].append({"name": name, "kind": "file", "bytes": size})
            return node

        return {
            "ok": True,
            "root": _ROOT.name,
            "path": str(_ROOT),
            "depth": depth,
            "limit": limit,
            "truncated": budget["truncated"],
            "tree": walk(_ROOT, 1),
        }

    def observer(self, probe: bool = True, channel_dir: Path | None = None,
                 isolated_home: Path | None = None) -> dict:
        """旁观者状态（只读取证）。**不启动任何进程、不装包、不出网** —— 那些是敏感档。"""
        contract = []
        for rel in OBSERVER_CONTRACT:
            path = _ROOT / rel
            exists = path.is_file()
            contract.append({
                "path": rel,
                "exists": exists,
                "bytes": path.stat().st_size if exists else 0,
            })

        # —— DSH 侧取证（只看存在性，绝不读凭据内容）——
        home = Path(os.environ.get("USERPROFILE") or Path.home()) / ".dsh"
        preset = ""
        settings = home / "settings.yaml"
        if settings.is_file():
            try:
                for line in settings.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.strip().startswith("defaultPreset:"):
                        preset = line.split(":", 1)[1].strip()
                        break
            except OSError:
                preset = ""

        sdk_packages = []
        cache_root = Path(os.environ.get("LOCALAPPDATA") or "") / "npm-cache" / "_npx"
        if cache_root.is_dir():
            for name in _DSH_SDK_PACKAGES:
                hit = False
                try:
                    hit = any(cache_root.glob(f"*/node_modules/@deepseek-ai/{name}"))
                except OSError:
                    hit = False
                sdk_packages.append({"name": name, "cached": hit})

        listening = "inconclusive"
        if probe:
            try:
                with socket.create_connection(("127.0.0.1", 3080), timeout=0.4):
                    listening = "alive"
            except ConnectionRefusedError:
                listening = "refused"
            except OSError:
                # 探测不到 ≠ 不存在（《空不等于不存在律》）—— 不许报成"没在跑"
                listening = "inconclusive"

        # —— 出声通道（W2.5 范式，独立通道，不混主账本）——
        if channel_dir is not None:
            channel = Path(channel_dir)
        else:
            try:
                from gbt_allinone._paths import STORE_DIR
                channel = Path(STORE_DIR) / "health" / "dsh"
            except Exception:  # noqa: BLE001
                channel = _ROOT / "gbt_allinone" / "store" / "health" / "dsh"
        records: list[dict] = []
        if channel.is_dir():
            for path in sorted(channel.glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict):
                        records.append(row)

        # 握手状态**读证据，不写死** —— 没有记录就是 inconclusive（不是"不通"）；
        # 有记录但过了 ttl 就是 stale（不许拿旧读数当现在的结论）。
        handshake, handshake_at, handshake_age_s = "inconclusive", None, None
        for row in reversed(records):
            if row.get("probe") != "dsh_handshake":
                continue
            handshake = str(row.get("result") or "inconclusive")
            handshake_at = row.get("iso")
            try:
                age = time.time() - float(row.get("ts") or 0)
                ttl = float(row.get("ttl_s") or 3600)
                handshake_age_s = int(age)
                if handshake == "ok" and age > ttl:
                    handshake = "stale"
            except (TypeError, ValueError):
                handshake_age_s = None
            break

        blockers = []
        if preset == "danger-full-access":
            blockers.append({
                "code": "dsh_default_full_access",
                "detail": "`~/.dsh/settings.yaml` 的 `permission.defaultPreset = danger-full-access` —— "
                          "DSH 默认是**全权限**，不是只读。旁观者只读必须**显式配置**，"
                          "不能把「它天生只读」当既成事实。",
            })
        if not any(row["cached"] for row in sdk_packages):
            blockers.append({
                "code": "sdk_packages_not_cached",
                "detail": "npx 缓存里没找到 `dsh-sdk-protocol` / `dsh-sdk-jsonrpc-server` —— "
                          "按契约它们是唯一允许的接入路线（不选 mcp）。",
            })
        if handshake != "ok":
            blockers.append({
                "code": "handshake_not_verified",
                "detail": f"握手状态 **{handshake.upper()}**"
                          + (f"（最近一次 {handshake_at}）" if handshake_at else "")
                          + "：起 `--profile sdk` 属敏感档，要有明确授权；"
                            "没记录就是「没测」，不是「测了不通」。",
            })
        blockers.append({
            "code": "observer_functions_not_built",
            "detail": "首刀**只证握手**：提醒 / 意见 / 建议这三件职能**尚未实现**，"
                      "也不做 `session/prompt`。别把「握手通」读成「旁观者能干活了」。",
        })

        # —— 隔离家的「只读档」配置取证 ——
        # 读的是**配置文件本身**；权威读法是 `dsh --profile sdk --dump-config`（要起 node，不适合放进 GET）。
        # 注意：参数名不能叫 `home` —— 本函数上面的 `home` 是**主人的** ~/.dsh，
        # 同名会被遮蔽（本人第一版就是这么写错的，测试当场抓住）。
        iso_home = (Path(isolated_home) if isolated_home is not None
                    else (_ROOT / ".scratch" / "_dsh_home"))
        preset = None
        settings_iso = iso_home / "settings.yaml"
        if settings_iso.is_file():
            try:
                for line in settings_iso.read_text(encoding="utf-8", errors="replace").splitlines():
                    s = line.strip()
                    if s.startswith("defaultPreset:"):
                        preset = s.split(":", 1)[1].strip() or None
                        break
            except OSError:
                preset = None
        patch_file = iso_home / "profiles" / "sdk" / "cordis.patch.yml"
        patch_present = patch_file.is_file()
        patch_sandbox = None
        if patch_present:
            try:
                for line in patch_file.read_text(encoding="utf-8", errors="replace").splitlines():
                    s = line.strip()
                    if s.startswith("#"):
                        continue
                    if s.startswith("sandbox:"):
                        patch_sandbox = s.split(":", 1)[1].strip() or None
                        break
            except OSError:
                patch_sandbox = None
        read_only = (preset == "read-only") and (patch_sandbox == "read-only")
        if not read_only:
            blockers.append({
                "code": "observer_not_read_only",
                "detail": "隔离家的只读档没配齐（`settings.yaml` 的 `defaultPreset` 与 "
                          "`cordis.patch.yml` 的 `sandbox` 必须**同时**是 `read-only`）"
                          "—— 在那之前，「旁观者只读」只是一句口号。",
            })

        return {
            "ok": True,
            "status": "verified_handshake_only" if handshake == "ok" else "wired_not_verified",
            "handshake": handshake,
            "handshake_at": handshake_at,
            "handshake_age_s": handshake_age_s,
            "contract": contract,
            "dsh": {
                "home_exists": home.is_dir(),
                "permission_preset": preset or None,
                "credentials_present": (home / ".credentials.yaml").is_file(),
                "web_3080": listening,
                "sdk_packages": sdk_packages,
                "version_lock": "0.1.5-rc.2",
            },
            "voice_channel": str(channel),
            "voice": records[-20:],
            "voice_total": len(records),
            # 三件职能各归各栏（契约第一条：职能只有三件）
            "voice_by_kind": {
                label: [row for row in records if row.get("result") == label][-10:]
                for label in _VOICE_KINDS.values()
            },
            "sandbox": {
                "isolated_home": str(iso_home),
                "settings_default_preset": preset,
                "patch_present": patch_present,
                "patch_sandbox": patch_sandbox,
                "read_only_configured": read_only,
                "authority": "权威读法 = `dsh --profile sdk --dump-config`；此处读的是配置文件本身",
                "caveat": "SandboxMode **只管文件操作**；网络与进程策略不在其词汇里 ⇒ "
                          "`read-only` ≠ 「零能力」",
            },
            "sees": [
                {"what": "项目树", "how": "GET /api/tree", "mode": "read-only"},
                {"what": "她的能力目录", "how": "GET /api/capabilities", "mode": "read-only"},
                {"what": "面板状态", "how": "GET /api/state", "mode": "read-only"},
                {"what": "事件流", "how": "GET /api/events", "mode": "read-only"},
            ],
            "blockers": blockers,
            "note": "方向只有「小土豆 → DSH」；旁观者零执行权。本项目**不启动**任何 DSH 进程。",
        }

    def studio(self) -> dict:
        """视频工坊（自作电影）：工具就绪度 + 最火的几家短视频平台。

        纪律两条：
          ① 就绪度**实测**（bin 在不在 PATH / env 在不在），缺什么写什么，不猜。
          ② 平台事实**只读她那本登记表**（`social_platforms.spec_for`），未登记就如实报
             `spec_known=False`；门禁状态**复用已有的 social 视图**，不另造一份。
        """
        tools = []
        for spec in _STUDIO_TOOLS:
            bins = {name: (shutil.which(name) or "") for name in spec["bins"]}
            envs = {name: bool(os.environ.get(name, "").strip()) for name in spec["env"]}
            missing = [name for name, ok in {**{k: bool(v) for k, v in bins.items()},
                                             **envs}.items() if not ok]
            tools.append({
                "id": spec["id"], "label": spec["label"], "what": spec["what"],
                "bins": bins, "env": envs, "missing": missing, "ready": not missing,
            })

        try:
            social = self.social("status", {})
        except Exception:                                     # noqa: BLE001
            social = {}
        by_id = {}
        for row in (social.get("platforms") or []):
            key = str(row.get("id") or "").strip().lower()
            if key:
                by_id[key] = row

        platforms = []
        for pid in _HOT_VIDEO_IDS:
            spec = _spec_for_platform(pid) or {}
            row = by_id.get(pid) or {}
            platforms.append({
                "id": pid,
                "label": spec.get("label") or row.get("label") or pid,
                "declared_in_config": bool(row),
                "spec_known": bool(spec),
                "official_api": spec.get("official_api"),
                "delivery": spec.get("delivery") or "",
                "audit_gate": spec.get("audit_gate") or "",
                "credential_field": spec.get("credential_field") or "",
                "daily_limit": spec.get("daily_limit"),
                "gates": (row.get("flags") or {}),
            })
        checklist = _HERE / "短视频平台接入单.md"
        return {
            "ok": True,
            "tools": tools,
            "platforms": platforms,
            "platforms_tracked_total": social.get("platform_count"),
            "gate_names": ["app_registered", "scope_audited",
                           "account_authorized", "credential_registered"],
            # 接入单：把"下一步该去哪个官方入口、填哪几格"放在会被读到的地方
            "checklist": {
                "rel": "holo_pet/短视频平台接入单.md",
                "path": str(checklist),
                "exists": checklist.is_file(),
                "bytes": checklist.stat().st_size if checklist.is_file() else 0,
            },
            "note": "平台事实只读登记表；未登记的如实标 spec_known=false。"
                    "没有官方发布接口的平台，本舱区不做、也不用浏览器自动化绕。",
        }

    def voice_speak(self, kind: str, text: str, *, channel_dir: Path | None = None) -> dict:
        """旁观者出声（提醒 / 意见 / 建议）—— **只落一条记录，然后就没有然后了**。

        契约第二条：零执行权 —— 不是「不许按」，是**没有这个键**。
        因此本方法**不调 api / 不起进程 / 不碰生产树 / 不出网**，唯一副作用是往独立通道追加一行。
        `tests/test_panel_server.py::test_voice_has_no_execution_branch` 用 AST 扫这一条。
        """
        raw = str(kind or "").strip()
        # 中英都收：契约用中文名（提醒/意见/建议），代码里用英文键，两边都能调。
        label = _VOICE_KINDS.get(raw.lower())
        if not label:
            label = next((v for v in _VOICE_KINDS.values() if v == raw), None)
        if not label:
            return {
                "ok": False,
                "error": "旁观者只有三件职能：提醒 / 意见 / 建议",
                "allowed": list(_VOICE_KINDS.values()),
            }
        body = str(text or "").strip()
        if not body:
            return {"ok": False, "error": "出声内容为空"}
        truncated = len(body) > _VOICE_MAX_CHARS
        if truncated:
            body = body[:_VOICE_MAX_CHARS]

        # 幂等（沿今晚纪律：写入前查指纹，不靠事后删）
        duplicate, _prev = _VOICE_DEDUPE.check(body, "")
        if duplicate:
            return {"ok": True, "spoken": False, "duplicate": True, "kind": label}

        folder = Path(channel_dir) if channel_dir is not None else _dsh_channel_dir()
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"voice-{time.strftime('%Y%m%d')}.jsonl"
        record = {
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "probe": "",
            "target": "observer.voice",
            "result": label,
            "detail": body,
            "latency_ms": 0,
            "ttl_s": 0,
            "chars": len(body),
            "truncated": truncated,
            "authority": "read-only · 零执行权",   # 出声方没有执行键
        }
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        _VOICE_DEDUPE.remember(body, "", record)
        return {"ok": True, "spoken": True, "kind": label, "truncated": truncated,
                "channel": str(folder), "file": target.name}


    # ═════════════ 设置面（Owner 2026-09-22：「配置密钥属于设置」）═════════════
    # 落点纪律：密钥不是一个独立窗口，而是「设置」面里的第一组。
    # 三条硬纪律写在这里，防止后来人放宽：
    #   ① **绝不下发明文密钥** —— 任何密钥只回 mask() 过的打码值。
    #   ② **不落盘 dashboard 密码/会话** —— token 只活在内存 `self._ffl_token`，
    #      进程一停即失效；仓内任何文件都不写它。
    #   ③ **没登录就如实说没登录** —— 不假装拿到了供应商清单（反假执行）。

    def _ffl(self):
        """按需取 FreeLLMAPI 客户端（拿不到就如实报，不抛裸异常）。"""
        from gbt_allinone.llm import freellmapi as ffl
        return ffl

    def _ffl_token_get(self) -> str:
        return str(getattr(self, "_ffl_token", "") or "")

    def settings(self) -> dict:
        """设置面读数：分组的现状。**密钥是第一组**，其余如实标 pending。"""
        try:
            ffl = self._ffl()
        except Exception as e:                                    # noqa: BLE001
            return {"ok": False, "error": f"freellmapi 客户端不可用: {type(e).__name__}",
                    "groups": []}

        probe = ffl.probe()
        token = self._ffl_token_get()
        keys = {"id": "keys", "title": "密钥",
                "desc": "本地免费大模型池（FreeLLMAPI）的供应商密钥",
                "server": probe, "authed": bool(token)}
        if not probe.get("up"):
            keys["status"] = "server_down"
            keys["note"] = "服务没起 —— 先起 FreeLLMAPI 桌面版（端口读它自己的 config.json）"
        elif not token:
            keys["status"] = "need_login"
            keys["note"] = ("要读供应商、配密钥，需 dashboard 会话。密码不落盘，"
                            "请在本页现场登录（走官方 /api/auth/login）")
        else:
            p = ffl.providers(token)
            keys["status"] = "ok" if p.get("ok") else "error"
            if p.get("ok"):
                keys["summary"] = p.get("summary") or {}
                keys["providers"] = p.get("providers") or []
                keys["unconfigured"] = p.get("unconfigured") or []
                keys["expected"] = p.get("expected")
                keys["matches_expected"] = p.get("matches_expected")
            else:
                keys["note"] = p.get("error", "")
                if p.get("status") == 401:
                    keys["status"] = "need_login"
                    keys["note"] = "会话已失效，请重新登录"

        return {"ok": True, "groups": [
            keys,
            {"id": "compute", "title": "模型与算力", "status": "pending",
             "desc": "L1 官方独立连接口 / L2 免费池 / L3 本地 的优先级（待接 official.py）"},
            {"id": "body", "title": "本体", "status": "pending",
             "desc": "窗口 / 屏幕 / 输入 / 进程 的开关与权限（待接 body_bus）"},
            {"id": "transformer", "title": "变压器", "status": "pending",
             "desc": "压缩与快速输出开关（待接变压器）"},
        ]}

    def settings_action(self, op: str, payload: dict | None = None) -> dict:
        """设置面的写动作。**只做配置，不做执行** —— 能力调用仍走 run_task，不绕门。

        op：probe / login / logout / providers / add_key / health
        """
        p = payload or {}
        op = str(op or "").strip().lower()
        _SUPPORTED = ("probe", "login", "logout", "providers", "add_key", "health")
        # op 校验**放在最前**：否则未知 op 会先撞上"还没登录"，报错话术不准
        # （实测：settings_action("乱来", {}) 原来回的是 401 还没登录，而不是"未知动作"）。
        if op not in _SUPPORTED:
            return {"ok": False, "op": op, "error": f"未知设置动作 {op!r}",
                    "supported": list(_SUPPORTED)}
        try:
            ffl = self._ffl()
        except Exception as e:                                    # noqa: BLE001
            return {"ok": False, "op": op, "error": f"客户端不可用: {type(e).__name__}"}

        if op == "probe":
            return {"ok": True, "op": op, "probe": ffl.probe()}

        if op == "login":
            r = ffl.login(str(p.get("email") or ""), str(p.get("password") or ""))
            # token 只留内存；**返回值里也把它抹掉**，只回打码指纹，免得漏进日志/前端。
            if r.get("ok"):
                self._ffl_token = r["token"]
                return {"ok": True, "op": op, "user": r.get("user"),
                        "token_fp": ffl.mask(r["token"]), "stored": "memory-only"}
            return {"ok": False, "op": op,
                    "error": r.get("error", "登录失败"),
                    "hint": "密码不落盘；核对 FreeLLMAPI dashboard 的账号密码"}

        if op == "logout":
            self._ffl_token = ""
            return {"ok": True, "op": op, "note": "内存里的会话已清"}

        token = self._ffl_token_get()
        if not token:
            return {"ok": False, "op": op, "status": 401,
                    "error": "还没登录 —— 先 login 再操作（密码不落盘）"}

        if op == "providers":
            r = ffl.providers(token)
            if r.get("ok"):
                r = {**r, "op": op}
            return {**r, "op": op}

        if op == "add_key":
            platform = str(p.get("platform") or "").strip()
            key = str(p.get("key") or "")
            if not platform:
                return {"ok": False, "op": op, "error": "缺少 platform"}
            a = ffl.add_key(token, platform, key, str(p.get("label") or "面板配置"))
            if not a.get("ok"):
                return {**a, "op": op}
            # **写完必须验**：没验过的不许叫「配好了」（反假执行）。
            h = ffl.health_check(token, a.get("id")) if a.get("id") else {
                "ok": False, "error": "对方没回 id，无法健康检查"}
            return {"ok": bool(a.get("ok")), "op": op, "platform": platform,
                    "id": a.get("id"), "masked": a.get("masked"),
                    "added": True, "verified": bool(h.get("ok")),
                    "health": h.get("result") or h.get("error"),
                    "note": ("已配且已验通过" if h.get("ok") else
                             "已写入，但**健康检查没过** —— 不算配好")}

        if op == "health":
            kid = p.get("key_id")
            if kid in (None, ""):
                return {"ok": False, "op": op, "error": "缺少 key_id"}
            h = ffl.health_check(token, kid)
            return {**h, "op": op}

        return {"ok": False, "op": op, "error": f"未实现的设置动作 {op!r}"}


    # ═════════ 大脑执行层 · 排布图与连接网络（Owner：「逼真和真实执行的感觉」）═════════
    # 铁律：图上每个节点、每条边都要能在源码上指出处；状态必须是真事件。
    # 结构与状态都由 `gbt_allinone/tools/brain_graph.py` 现算，本方法只做搬运与兜底。

    def brain_graph(self, limit: int = 400) -> dict:
        """大脑执行层：**结构**（从源码 AST 算）+ **实时状态**（从 audit.jsonl 真事件）。
        任何一半拿不到都如实说哪一半没有，**不拿另一半假装整体可用**。"""
        out = {"ok": True, "structure": None, "live": None, "errors": {}}
        try:
            from gbt_allinone.tools import brain_graph as bg
        except Exception as e:                                    # noqa: BLE001
            return {"ok": False, "errors": {"import": f"{type(e).__name__}: {str(e)[:120]}"},
                    "note": "数据层不可用 —— 不编一张图出来"}
        try:
            out["structure"] = bg.structure()
        except Exception as e:                                    # noqa: BLE001
            out["errors"]["structure"] = f"{type(e).__name__}: {str(e)[:120]}"
        try:
            # 布局服务端算（Sugiyama 分层），页面只负责画 —— 职责分开
            out["layout"] = bg.layout(out["structure"])
        except Exception as e:                                    # noqa: BLE001
            out["errors"]["layout"] = f"{type(e).__name__}: {str(e)[:120]}"
        try:
            out["live"] = bg.live_state(limit=int(limit or 400))
        except Exception as e:                                    # noqa: BLE001
            out["errors"]["live"] = f"{type(e).__name__}: {str(e)[:120]}"
        out["ok"] = not out["errors"]
        if out["errors"]:
            out["note"] = "部分失败，见 errors —— 「拿不到」就说拿不到"
        return out

    # ═════════ 窗口 6 · 赏金台（h1mcp · 阶段一 本机只读）═════════
    # Owner 2026-09-22：「还有这个要在面板上……我记得已经做了没接上」。
    # 实测断点（不是推测）：赏金台 `holo_pet_w3/h1/` 此前**只有一条数据路** ——
    #   preload.cjs:31  `h1: () => invoke("w3:h1")`
    #   main.cjs:1204  `ipcMain.handle("w3:h1", () => w3H1())`
    #   h1.js:8-9      只认 `window.gbtW3.h1`
    # DSH 面板宿主是**浏览器 iframe，没有 Electron** ⇒ `window.gbtW3` 不存在 ⇒
    # h1.js 走 `if (!api)` 如实打「桥断」。页做得再好，在面板里也永远是空壳。
    # 本方法补的是**第二条同源只读出口**，让同一份 render 能跑在浏览器里。
    #
    # 🔴 与 Electron 侧 w3H1() 的口径必须一致，四条纪律写在最前：
    #   ① **单一真源**：路径一律读 `holo_pet_w3/shell/windows.json` 的 windows[id=h1].config，
    #      与 main.cjs::h1ConfiguredPath 同一份登记 —— 两处不许各自写死一个路径。
    #   ② **零副作用**：只 stat / read / 读环境变量。不起子进程、不发网络、不写盘。
    #   ③ **凭据只报布尔**：不回显值，连用户名都不回显。
    #   ④ **取不到就不许绿**：ok=False 并带原因，绝不拿假绿糊过去。
    H1_CRED_VARS = (
        ("H1_USERNAME", "HackerOne 用户名", "h1mcp v0.1.4"),
        ("H1_API_KEY", "API 令牌（二进制实际读取名）", "h1mcp v0.1.4"),
        ("H1_API_TOKEN", "历史口径名（h1mcp v0.1.4 不读取）", None),
    )

    @staticmethod
    def _h1_expand(raw: str) -> str:
        """展开注册表里的 %LOCALAPPDATA% / %APPDATA%（与 main.cjs 的正则同规则）。"""
        return re.sub(r"%([^%]+)%", lambda m: os.environ.get(m.group(1), m.group(0)), str(raw))

    def _h1_paths(self) -> tuple[str | None, str | None, str]:
        """取 (二进制, 草稿目录, 路径来源)。来源要报出来 —— 这样「单一真源」是可证的。"""
        binary = os.environ.get("GBT_H1_BINARY") or None
        drafts = os.environ.get("GBT_H1_DRAFTS") or None
        source = "env" if (binary or drafts) else "default"
        try:
            reg_path = _REPO_ROOT / "holo_pet_w3" / "shell" / "windows.json"
            reg = json.loads(reg_path.read_text(encoding="utf-8"))
            entry = next((w for w in (reg.get("windows") or []) if w.get("id") == "h1"), None)
            cfg = (entry or {}).get("config") or {}
            got = False
            if not binary and isinstance(cfg.get("binary_path"), str) and cfg["binary_path"].strip():
                binary = self._h1_expand(cfg["binary_path"].strip())
                got = True
            if not drafts and isinstance(cfg.get("drafts_path"), str) and cfg["drafts_path"].strip():
                drafts = self._h1_expand(cfg["drafts_path"].strip())
                got = True
            if got:
                source = "holo_pet_w3/shell/windows.json"
        except Exception:                                          # noqa: BLE001
            pass
        if not binary:
            local = os.environ.get("LOCALAPPDATA")
            binary = str(Path(local) / "gbt_allinone" / "bin" / "h1mcp.exe") if local else None
        if not drafts:
            roaming = os.environ.get("APPDATA")
            drafts = str(Path(roaming) / "h1mcp" / "drafts") if roaming else None
        return binary, drafts, source

    def h1(self) -> dict:
        """窗口 6 · 赏金台：本机只读体检（阶段一）。

        信封与 Electron 侧 w3H1() 逐字段对齐 —— 前端 `h1.js` 两条路共用一份 render：
          通过 → {"ok": True,  "data":  body}
          取不到 → {"ok": False, "error": 原因, "panel": body}   ← 半截数据也要能渲染，但**不许绿**
        """
        binary_path, drafts_path, cfg_source = self._h1_paths()

        binary = {"path": binary_path, "present": False, "bytes": None, "tag": None,
                  "sha256": None, "recorded_sha256": None, "sha_match": None,
                  "sidecar_present": False, "reason": None}
        if not binary_path:
            binary["reason"] = "LOCALAPPDATA 不可用 -> 拿不到稳定工具目录"
        elif not os.path.exists(binary_path):
            binary["reason"] = "二进制不存在（未安装或路径不符）"
        else:
            try:
                binary["present"] = True
                binary["bytes"] = os.path.getsize(binary_path)
                with open(binary_path, "rb") as fh:                 # 分块读，7MB 也只用一次内存
                    digest = hashlib.sha256()
                    while True:
                        chunk = fh.read(1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                    binary["sha256"] = digest.hexdigest()
                sidecar = binary_path + ".sha256"
                if os.path.exists(sidecar):
                    binary["sidecar_present"] = True
                    txt = Path(sidecar).read_text(encoding="utf-8", errors="replace")
                    hm = re.search(r"[0-9a-fA-F]{64}", txt)
                    if hm:
                        binary["recorded_sha256"] = hm.group(0).lower()
                    vm = re.search(r"tag=([^\r\n]+)", txt)
                    if vm:
                        binary["tag"] = vm.group(1).strip()
                if binary["sha256"] and binary["recorded_sha256"]:
                    binary["sha_match"] = binary["sha256"] == binary["recorded_sha256"]
                if binary["sha_match"] is False:
                    binary["reason"] = "侧车哈希与产物不一致（产物被替换过）"
            except Exception as e:                                  # noqa: BLE001
                binary["reason"] = f"读取失败：{type(e).__name__}"

        cred_items = [{"name": n, "role": r, "read_by": by,
                       "configured": bool(os.environ.get(n))}      # 只报布尔，不回显值
                      for (n, r, by) in self.H1_CRED_VARS]
        creds_ready = all(c["configured"] for c in cred_items
                          if c["name"] in ("H1_USERNAME", "H1_API_KEY"))

        drafts = {"path": drafts_path, "initialized": False, "count": None,
                  "files": [], "reason": None}
        if not drafts_path:
            drafts["reason"] = "APPDATA 不可用 -> 拿不到草稿目录"
        elif not os.path.isdir(drafts_path):
            drafts["reason"] = "目录不存在（未初始化）"
        else:
            try:
                names = sorted(n for n in os.listdir(drafts_path)
                               if n.lower().endswith(".json"))[:50]
                drafts["initialized"] = True
                drafts["count"] = len(names)
                for n in names:
                    row = {"name": n, "bytes": None, "mtime": None, "title": None,
                           "program_handle": None, "parse_error": None}
                    try:
                        p = Path(drafts_path) / n
                        st = p.stat()
                        row["bytes"] = st.st_size
                        row["mtime"] = datetime.fromtimestamp(st.st_mtime).isoformat()
                        doc = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                        if isinstance(doc.get("title"), str):
                            row["title"] = doc["title"]
                        if isinstance(doc.get("program_handle"), str):
                            row["program_handle"] = doc["program_handle"]
                    except Exception as e:                          # noqa: BLE001
                        row["parse_error"] = type(e).__name__
                    drafts["files"].append(row)
            except Exception as e:                                  # noqa: BLE001
                drafts["reason"] = f"目录读取失败：{type(e).__name__}"

        ready = binary["present"] is True and binary["sha_match"] is True and creds_ready
        body = {
            "readonly": True,
            "stage": "stage1-local-readonly",
            "note": "只读：不调 API、不起子进程、不写文件；凭据只报配置状态，不回显值。",
            "badge": "ok" if ready else ("warn" if binary["present"] else "off"),
            "config_source": cfg_source,
            "binary": binary,
            "credentials": {"ready": creds_ready, "items": cred_items},
            "drafts": drafts,
            "api_surfaces": [
                {"id": "programs_scope", "title": "程序与 scope", "state": "pending",
                 "reason": "阶段二未接入（走 mcp_bridge 能力层，需 Owner 单独放行）"},
                {"id": "reports", "title": "我的报告", "state": "pending",
                 "reason": "阶段二未接入（同上）"},
                {"id": "earnings", "title": "收益", "state": "pending",
                 "reason": "阶段二未接入（同上）"},
            ],
            "sensitive_note": "敏感档动作不接：submit_report / submit_draft / add_comment / "
                              "close_report / update_report_severity / request_disclosure。",
            "transport": "panel_server HTTP（同源；DSH 面板内嵌走这条）",
        }
        if not binary["present"]:
            return {"ok": False, "error": "h1mcp 取不到：" + (binary["reason"] or "未知原因"),
                    "panel": body}
        return {"ok": True, "data": body}


class _Handler(BaseHTTPRequestHandler):
    """静态资源与本地 API；默认只由 launcher 在 127.0.0.1 上启动。"""

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # noqa: A003
        return

    @property
    def bridge(self) -> HoloBridge:
        return self.server.bridge  # type: ignore[attr-defined]

    @property
    def dedupe(self) -> MessageDeduper:
        return self.server.dedupe  # type: ignore[attr-defined]

    def _note_capability_call(self, kind: str, ok: bool) -> None:
        """记一次**真实发生**的能力调用（能力球"能源输送"的唯一数据源）。

        Owner 2026-09-22：「只要 AI 在动，能力球里面相对应的能力就会像输送能源
        一样的动起来」。

        🔴 纪律（写在这里防以后被改成装饰）：
          · 本方法**只在 /api/capability 真正把调用派出去之后**被调用
          · **没有**任何"演示 / 模拟 / 假事件"入口
          · 环形缓冲上限 80 条，只保留最近 10 分钟 —— 老事件自己退场
          ⇒ 球上亮的，永远是**真发生过的**。这是铁律 6 在视觉层的落点。
        """
        import time as _t
        now = _t.time()
        if not hasattr(self, "_recent_calls") or self._recent_calls is None:
            self._recent_calls = []
        self._recent_calls.append({"kind": str(kind or ""), "ok": bool(ok), "at": now})
        # 只留最近 10 分钟 且 不超 80 条
        keep = [c for c in self._recent_calls if now - float(c.get("at") or 0) <= 600.0]
        self._recent_calls = keep[-80:]

    def _send_json(self, value, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self._send_cors()
        self.send_header("Content-Length", str(len(raw)))
        # 🔴 2026-10-27：客户端断开是**正常事件**（轮询页刷新 / 切标签 / 关页 / 前端 abort），
        # 不是服务出错。不接住它，`socketserver` 会给**每个请求线程**打一整段 traceback ——
        # 实测：面板服务跑 9h02m，stderr 攒到 1.29MB / 12.9 万行，其中 98% 是同一个
        # `WinError 10053`，把自己真正的故障（末尾那次段错误）埋在噪声里。
        # SSE 那条路径（`_sse_stream` 的 `except (BrokenPipeError, ConnectionResetError, OSError)`）
        # 早就接了，JSON 这条一直没接 —— 同一件事两条路径，只接了一条。
        # ⚠️ 只接这三类断开异常，**不用 `OSError` 宽口径**：
        # `except OSError` 会把"磁盘满 / 句柄耗尽"这类真错一起吞掉，那比噪声更糟。
        try:
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    # ── 同机直连放行（只放行本机回环上的 DSH 宿主源，**不是 `*`**）──────────────
    # 为什么需要：DSH 宿主里 `/gbt-master/api/*` 的内嵌反代**当前不生效**
    # （实测 HTTP 404「该路径不在可服务白名单内」—— 静态路由赢了前缀匹配，
    #  因为宿主进程自 09-21 22:29 起未重启，加载的是没有反代那段代码的旧插件）。
    # 于是凡声明 apiShim 的页在宿主内都拿不到本机服务。
    # 放行之后，宿主里的页可以直连 `http://127.0.0.1:8765/api/*`；
    # 反代一旦生效，前端会优先走同源那条，这段就成了兜底 —— 两条路都在明面上。
    CORS_ORIGINS = ("http://127.0.0.1:3080", "http://localhost:3080")

    def _send_cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin in self.CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):  # noqa: N802
        """预检：只回本面板服务真正提供的方法，不放宽任何东西。"""
        self.send_response(HTTPStatus.NO_CONTENT)
        origin = self.headers.get("Origin")
        if origin in self.CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "content-type, accept")
            self.send_header("Access-Control-Max-Age", "300")
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_json(self) -> dict:
        try:
            length = min(1024 * 1024, int(self.headers.get("Content-Length") or 0))
            raw = self.rfile.read(length) if length else b"{}"
            value = json.loads(raw.decode("utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _static_path(self, url_path: str) -> Path | None:
        path = unquote(url_path.split("?", 1)[0])
        if path in ("", "/", "/index.html"):
            return _HERE / "index.html"
        if path.startswith("/holo_pet/"):
            path = path[len("/holo_pet/"):]
        relative = path.lstrip("/")
        # 两级根：① 面板自己的目录（holo_pet/）② **仓库根**（上一级）。
        # 为什么加第二级：能力球 `capabilities.html` 在仓库根，它不是面板的私有件，
        # 但**只有从面板端口打开**才能用上 /api/message（大脑）、/api/recent-calls
        # （能源流转的 HEAT 来源）、/api/events（她说话）。
        # 实测用 file:// 打开时那几个接口全连不上 ⇒ 麦克风 not-allowed、热流永远不亮。
        # 安全：**每一级各自过一遍路径穿越守卫**，越出自己那级就 continue，越界拿不到东西。
        for base in (_HERE, _REPO_ROOT):
            if base is _REPO_ROOT:
                # 仓库根只认白名单里的**顶层文件**（不许带子目录），
                # 否则 .git/ memory/ delivery/ 会跟着一起发出去。
                if relative not in _REPO_ROOT_ALLOW:
                    continue
            candidate = (base / relative).resolve()
            try:
                candidate.relative_to(base.resolve())
            except ValueError:
                continue
            if candidate.is_file():
                return candidate
        return None

    def _serve_static(self, url_path: str) -> bool:
        file_path = self._static_path(url_path)
        if file_path is None:
            return False
        content = file_path.read_bytes()
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        if file_path.suffix.lower() == ".glb":
            content_type = "model/gltf-binary"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)
        return True

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self._send_json(self.bridge.state())
            return
        if parsed.path == "/api/purge":
            self._send_json(self.bridge.purge())
            return
        if parsed.path == "/api/music":
            self._send_json(self.bridge.music())
            return
        if parsed.path == "/api/capabilities":
            self._send_json(self.bridge.capabilities())
            return
        if parsed.path == "/api/tree":
            self._send_json(self.bridge.tree(
                _query_int(parsed.query, "depth") or 3,
                _query_int(parsed.query, "limit") or 400,
            ))
            return
        if parsed.path == "/api/observer":
            self._send_json(self.bridge.observer(
                probe=(_query_int(parsed.query, "probe") != 0),
            ))
            return
        if parsed.path == "/api/studio":
            self._send_json(self.bridge.studio())
            return
        if parsed.path == "/api/settings":
            self._send_json(self.bridge.settings())
            return
        if parsed.path == "/api/brain-graph":
            self._send_json(self.bridge.brain_graph(
                _query_int(parsed.query, "limit") or 400))
            return
        if parsed.path == "/api/h1":
            # 窗口 6 赏金台的**第二条数据路**（第一条是 Electron IPC w3:h1）。
            # 为什么需要它：DSH 面板宿主是浏览器 iframe，没有 Electron ⇒ 只有 IPC 的口
            # 在面板里永远是空壳（Owner 2026-09-22 说的「做了没接上」就是这个）。
            self._send_json(self.bridge.h1())
            return
        if parsed.path == "/api/recent-calls":
            # 能力球用 fetch(默认 GET) 轮询这个口拿"最近谁被真正调过"。
            # 2026-09-22 修：这段原先错放在 do_POST 里，而客户端发的是 GET
            # ⇒ 能量传输动画**从来没通过**（我之前只声明"接上了"，没端到端验；
            #   被 `test_app_surface_matches_real_routes` 补登记时抓出来）。
            # 只读口就该是 GET，一并挪正。
            calls = getattr(self.bridge, "_recent_calls", None)
            if calls is None:
                calls = getattr(self, "_recent_calls", [])
            self._send_json({"ok": True, "calls": list(calls),
                             "source": "panel_server._recent_calls"}, HTTPStatus.OK)
            return
        if parsed.path == "/api/events":
            since = _query_int(parsed.query, "since")
            if since is None:
                # EventSource 自动重连时会带标准头 Last-Event-ID —— 直接用它续传。
                since = _header_int(self.headers.get("Last-Event-ID"))
            self._stream_events(since, _query_str(parsed.query, "boot"))
            return
        if self._serve_static(parsed.path):
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _stream_events(self, since: int | None = None, boot: str = "") -> None:
        q = self.bridge.bus.subscribe()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            # 续传要同时满足两件：给了水位、且 boot 对得上（同一个进程）。
            # 否则（首连 / 页面刷新 / 服务重启过）回放最近 40 条让页面接回状态。
            bus = self.bridge.bus
            resumable = since is not None and (not boot or boot == bus.boot_id)
            backlog = bus.since(since) if resumable else bus.snapshot()[-40:]
            for event in backlog:
                self._write_sse(event)
            while True:
                try:
                    event = q.get(timeout=15.0)
                    self._write_sse(event)
                except queue.Empty:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.bridge.bus.unsubscribe(q)

    def _write_sse(self, event: dict) -> None:
        data = json.dumps(event, ensure_ascii=False, default=str)
        seq = event.get("seq")
        head = f"id: {int(seq)}\n".encode("utf-8") if seq is not None else b""
        self.wfile.write(head + b"data: " + data.encode("utf-8") + b"\n\n")
        self.wfile.flush()

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/message":
                body = self._read_json()
                text = str(body.get("text", ""))
                client_id = str(body.get("client_msg_id") or body.get("delivery_id") or "")
                duplicate, previous = self.dedupe.check(text, client_id)
                if duplicate:
                    _panel_audit("message_deduped", {
                        "client_msg_id": client_id,
                        "text_len": len(text),
                        "reason": "duplicate_within_window",
                    })
                    payload = dict(previous or {})
                    payload.update({"ok": True, "accepted": False, "duplicate": True})
                    self._send_json(payload)
                    return
                result = self.bridge.send(text)
                if isinstance(result, dict) and result.get("ok"):
                    self.dedupe.remember(text, client_id, result)
                self._send_json(result)
                return
            if parsed.path == "/api/approval":
                body = self._read_json()
                result = self.bridge.resolve_approval(
                    int(body.get("id") or 0),
                    str(body.get("decision") or "reject"),
                    str(body.get("modified_text") or ""),
                )
                self._send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
                return
            if parsed.path == "/api/social":
                body = self._read_json()
                self._send_json(self.bridge.social(
                    str(body.get("op") or "status"),
                    body,
                ))
                return
            if parsed.path == "/api/settings/action":
                body = self._read_json()
                result = self.bridge.settings_action(
                    str(body.get("op") or "probe"),
                    body,
                )
                self._send_json(result,
                                HTTPStatus.OK if result.get("ok")
                                else HTTPStatus.BAD_REQUEST)
                return
            if parsed.path == "/api/research":
                body = self._read_json()
                self._send_json(self.bridge.research(
                    str(body.get("op") or "status"),
                    body,
                ))
                return
            if parsed.path == "/api/quick":
                body = self._read_json()
                self._send_json(self.bridge.quick(body.get("action", ""), body.get("payload") or {}))
                return
            if parsed.path == "/api/capability":
                body = self._read_json()
                _kind = body.get("kind") or body.get("action") or ""
                result = self.bridge.capability(
                    _kind,
                    body.get("payload") or {},
                    bool(body.get("confirm")),
                )
                # ── 记录这次真实调用（能力球"能源输送"的数据源）──────────────
                # Owner 2026-09-22：「只要 AI 在动，能力球里面相对应的能力就会像
                # 输送能源一样的动起来」。**只记真正走到这里的调用** ——
                # 不许为了让球动而伪造事件（铁律 6 严禁假执行）。
                try:
                    self._note_capability_call(_kind, bool(result.get("ok")))
                except Exception:
                    pass
                self._send_json(
                    result,
                    HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST,
                )
                return
            if parsed.path == "/api/observer/voice":
                body = self._read_json()
                result = self.bridge.voice_speak(
                    body.get("kind") or "",
                    body.get("text") or "",
                )
                self._send_json(
                    result,
                    HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST,
                )
                return
            if parsed.path == "/api/bluetooth":
                body = self._read_json()
                self._send_json(self.bridge.quick(
                    "bluetooth_" + str(body.get("op") or "status"),
                    body,
                ))
                return
            if parsed.path == "/api/notion":
                body = self._read_json()
                self._send_json(self.bridge.notion(
                    str(body.get("op") or "status"),
                    body,
                ))
                return
            if parsed.path == "/api/eigenflux":
                body = self._read_json()
                self._send_json(self.bridge.eigenflux(
                    str(body.get("op") or "status"),
                    body,
                ))
                return
            if parsed.path == "/api/xingyun":
                body = self._read_json()
                self._send_json(self.bridge.xingyun(
                    str(body.get("op") or "status"),
                    body,
                    client_host=str(self.client_address[0] if self.client_address else ""),
                ))
                return
            if parsed.path == "/api/interrupt":
                self._send_json(self.bridge.interrupt())
                return
            if parsed.path == "/api/new-thread":
                self._send_json(self.bridge.new_thread())
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except (ValueError, TypeError) as exc:
            self._send_json({"ok": False, "error": str(exc)[:200]}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "error": str(exc)[:240]}, HTTPStatus.INTERNAL_SERVER_ERROR)


def create_server(host: str = "127.0.0.1", port: int = 8765,
                  bridge: HoloBridge | None = None) -> ThreadingHTTPServer:
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, int(port)), _Handler)
    server.daemon_threads = True
    server.bridge = bridge or HoloBridge()  # type: ignore[attr-defined]
    server.dedupe = MessageDeduper()  # type: ignore[attr-defined]
    # 客户端断开不许刷屏（读路径只能在这一层接，见 quiet_disconnects 的说明）
    quiet_disconnects(server)
    return server


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="GBT小土豆 V8 3D 全息面板桥")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-codex", action="store_true",
                        help="只启动静态面板和降级大脑，不初始化 Codex")
    args = parser.parse_args(argv)

    bridge = HoloBridge()
    if not args.no_codex:
        bridge.start(wait_seconds=0.0)
    server = create_server(args.host, args.port, bridge)
    print(f"GBT小土豆 3D 全息面板: http://{args.host}:{server.server_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
