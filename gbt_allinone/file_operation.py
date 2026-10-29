# -*- coding: utf-8 -*-
# gbt-capability: filesystem
"""创作出口 · create —— 创作意图/产物登记 ＋ **仅限 outputs/** 的文件写入。
边界（逐条可查）：
- **文本出口本刀未接线**：默认出口 = AI 朋友圈（`eigenflux`），但本刀**不注册**
  `eigenflux` cap、**不发任何网络请求** —— `output` 如实报 `pending`
  （《反空壳律》＋《空不等于不存在律》：没取证的不建，探不到就报，不许静默跳过）。
  **D4 否决判据**：默认值一旦能**凭自己把内容发出去** —— 本刀当场判红。
- **默认出口 != 默认发布**：`target_source=default` 只表示"用了默认出口取值"，
  **不代表"可以发"**。取值来源 = 设置页（`<STORE_DIR>/health/create/state.json`），
  不是模块里写死的常量。
- **写入根只有一个**：家根下的 `outputs/`（实际路径见 `write_root()`）。越界一律拒：
  `..` / 绝对路径 / 盘符 / 点号开头的段（含 `.backup`）全部拒。
- **覆盖必带 `confirm_token`**：`sha256(相对路径|新内容 sha256|时间窗)` —— 内容改一个字
  旧令牌立刻作废（防「确认 A、写成 B」）。**同内容重复提交 = 幂等（G7）**，
  不产生第二次覆盖、不产生新备份。
- **写前备份 + 双向 SHA**：覆盖前原字节进 `<root>/.backup/`；写后自证
  「备份 sha256 == 原 sha256」＋「盘上 sha256 == 新 sha256」，两项都 True 才算成功。
- **写不进去就不许落盘**：后果动作前先做通道可写预检；预检失败 -> 不动盘，
  主账本落 `health_channel_failed`（第二十五章《终端失败必须响》）。
- **创作原文不进生命档案**：账本只落 `content_sha256` ＋ `chars`。
- **独立通道**：`<STORE_DIR>/health/create/*.jsonl`，路径一律由 `_paths.STORE_DIR`
  在**调用时**拼（不 import 期绑常量、不硬编码 `store/`）。
- **`GBT_CREATE_ROOT` 在调用时读**（默认家根 `outputs/`）—— 与 O53 不同：这里每次都
  重新解析，结构上不存在「绑定后改 env 静默走旧路径」的窗口。
- **`confirm_token` 铸法与刀一 `coze_mail` 同一约定**（`sha256(parts|窗口桶)`，窗口 900 s、
  允许前一窗）。两处各自实现、**故意不跨域 import** —— 见复核报告「已知重复」一节。
**「3 个事件名承载 5 个动作」的映射（如实标，供复核）**：
    status    -> （只读：不落账、不建目录、零字节）
    configure -> create_intent（落 target ＋ target_source="user"）
    intent    -> create_intent
    output    -> create_output（result="pending"，**不发网络请求**）
    write     -> create_write（唯一**可逆后果**动作）
"""
from __future__ import annotations

import json
import os
import re
import time
from hashlib import sha256
from pathlib import Path

from . import _paths
from .safe_io import atomic_write_bytes

CHANNEL = "create"
EVENTS = ("create_intent", "create_output", "create_write")
TEXT_EXIT_TARGET_DEFAULT = "eigenflux"
TARGET_SOURCES = ("default", "user", "agent_suggested")
CONTENT_MAX = 200000
REL_MAX = 240
TOKEN_WINDOW_S = 900
STATUS_TTL_S = 30.0
BACKUP_DIRNAME = ".backup"
_DRIVE_RE = re.compile(r"^[A-Za-z]:")
DEFAULT_WRITE_ROOT = (Path(__file__).resolve().parent.parent / "outputs").resolve()


class CreateError(ValueError):
    """调用方问题（坏参数 / 越界 / 未过闸门）—— api 归 user_error。"""


class WriteRootError(CreateError):
    """越界写入 —— 一律拒（只允许写入根之内）。"""


class ChannelWriteError(CreateError):
    """通道写不进去 —— 后果动作必须中止（第二十五章）。"""


_STATUS_CACHE: dict = {}


def write_root() -> Path:
    """写入根 —— **调用时**解析 `GBT_CREATE_ROOT`，默认 `DEFAULT_WRITE_ROOT`。

    **只解析、不设闸门**：`status` 等只读口要用它如实报路径。
    任何**可能落盘**的路径一律走 `_write_root_checked()`（R107 隔离钩子 · 乙案）。
    """
    env = os.getenv("GBT_CREATE_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_WRITE_ROOT


def _write_root_checked() -> Path:
    """写入口的写根闸门（R107 · 乙案）—— 覆盖**所有**可能落盘的路径。

    谓词（两条同时成立才拒）：
      ① 进程的 store 在**绑定时刻**已被显式隔离（`_paths.STORE_DIR_ENV_AT_BIND` 非空）；
      ② 写根 == `DEFAULT_WRITE_ROOT`（家根 `outputs/`）。
    生产进程 ① 恒假（`GBT_STORE_DIR` 未设）-> 本闸门**零影响**。用绑定快照而不是现场读
    env，与 O53 同源：绑定后改 env 不会让闸门自己漂走。

    覆盖范围（不许有旁路）：`_resolve_target()`（目标文件）· `backup_root()`（备份目录）·
    `_op_write`（写入口前置）三处入口全部走这里；`write_root()` 只留给只读口。
    判据 `test_arm_f_no_write_path_bypasses_the_gate` 用 AST 钉死这条覆盖范围。

    🔴 配方 #4 —— **本处不加"授权即过"短路，而且是刻意的**（2026-09-25 记）：
    配方原文对这条写的是「`filesystem_write` + **仍要求显式落点**」。
    而本函数的拒条件本来就是「隔离进程 **且** 写根仍是默认值」——
    一旦"仍要求显式落点"成立，写根就已经不是默认值，**条件根本不成立、它自然放行**。
    ⇒ 在这里加短路是个 **no-op**（改与不改行为完全一致）。
    **不写没用的代码，只把这件事记下来** —— 免得下一个人以为"这里漏改了"。
    """
    root = write_root()
    if root == DEFAULT_WRITE_ROOT and _paths.STORE_DIR_ENV_AT_BIND is not None:
        raise WriteRootError(
            "拒绝把产物写进生产 outputs/：进程已隔离 store（绑定时刻 GBT_STORE_DIR=%r），"
            "写根却仍指 %s。隔离进程必须显式设 GBT_CREATE_ROOT 到隔离目录。"
            % (_paths.STORE_DIR_ENV_AT_BIND, root))
    return root


def channel_dir() -> Path:
    """通道目录 —— **调用时**由 `_paths.STORE_DIR` 拼（不 import 期绑定）。"""
    return Path(_paths.STORE_DIR) / "health" / CHANNEL


# ══════════════════════════════════════════════════════════════════════════
# 「授权即过」短路（Owner 2026-09-25 令：「限制全改人工授权」· 配方 #1/#2/#3）
# ══════════════════════════════════════════════════════════════════════════
# 为什么要有它：`refusal-census.py scan` 现读「门面 15 处硬拒里 13 处**授权也绕不过**」——
# 因为它们**根本不消费作用域**，`owner_control` 只能顶掉"缺作用域"，顶不掉
# "路径不许绝对"这种校验。主人要的「限制全改人工授权」在这几处上原本不成立。
#
# 形状（每一处都一样，`docs/无限制创作流水线.md §十三`）：
#     if _authorized(scope, purpose):  → 走"授权即过"的短路
#     否则                             → **逐字节走原来的校验分支**
# ⇒ **没授权时行为与改前完全一致**，这就是回滚面；撤掉那两行即还原。
#
# 🔴 失败方向写死 **fail-closed**：门不可用（导入炸 / 抛异常）一律**返回 False**，
#    也就是**回到原来的校验分支**，绝不因为"门坏了"而放行。这条不许改。
def _authorized(scope: str, purpose: str) -> bool:
    """拿到该作用域的一次授权 ⇒ True；否则 False（含门不可用）。"""
    try:
        from . import auth_gate as _ag
        return bool(_ag.check_and_consume_many([scope], detail=purpose).get("ok"))
    except Exception:  # noqa: BLE001 —— fail-closed：门坏了不许放行
        return False


def events_path() -> Path:
    return channel_dir() / "events.jsonl"


def state_path() -> Path:
    return channel_dir() / "state.json"


def backup_root() -> Path:
    return _write_root_checked() / BACKUP_DIRNAME


def read_state() -> dict:
    """读状态（默认出口 / 总开关）。缺文件 / 坏 JSON = 默认值，不猜、**不建目录**。"""
    data = {"text_exit_target": TEXT_EXIT_TARGET_DEFAULT,
            "text_exit_source": "default", "enabled": True}
    try:
        raw = json.loads(state_path().read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return data
    if isinstance(raw, dict):
        target = str(raw.get("text_exit_target") or "").strip()
        if target:
            data["text_exit_target"] = target
            data["text_exit_source"] = str(raw.get("text_exit_source") or "user")
        data["enabled"] = bool(raw.get("enabled", True))
    return data


def write_state(state: dict) -> Path:
    """写状态（设置页 / configure 共用同一口）—— 写入口前过 O53 绑定比对。"""
    _paths.verify_store_binding()
    blob = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return atomic_write_bytes(state_path(), blob)


def _open_events():
    """通道追加句柄 —— 预检与写入走**同一个**开法，两者不许分叉。"""
    _paths.verify_store_binding()
    d = channel_dir()
    d.mkdir(parents=True, exist_ok=True)
    return open(events_path(), "a", encoding="utf-8", newline="\n")


def _log_event(event: str, meta: dict) -> None:
    """落一条通道账（写入 + fsync 后才返回）—— 失败抛 ChannelWriteError。
    **本函数不做「要不要落盘」的判断**；后果动作一律先 `_preflight_channel()` 探可写。
    """
    if event not in EVENTS:
        raise CreateError("未知事件名：%s（只允许 %s）" % (event, "/".join(EVENTS)))
    rec = {"ts": round(time.time(), 3),
           "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "event": event,
           "meta": meta}
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    try:
        with _open_events() as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        raise ChannelWriteError("通道写失败：%s: %s" % (type(exc).__name__, exc)) from exc


def _preflight_channel() -> None:
    """后果动作前的通道可写预检。只开、不写 —— 不产生任何行。
    与 `_log_event` 用**同一个** `_open_events()`，所以「预检说能写」与「真能写」不会分叉。
    """
    try:
        with _open_events():
            pass
    except OSError as exc:
        raise ChannelWriteError("通道不可写：%s: %s" % (type(exc).__name__, exc)) from exc


def _channel_fail(action: str, reason: str, detail: str) -> None:
    """故障走**主账本**（正常事件不混、故障仍然混）。"""
    try:
        from .store import audit
        audit("health_channel_failed", {"channel": CHANNEL, "action": action,
                                        "reason": reason, "detail": str(detail)[:200]})
    except Exception:  # noqa: BLE001 - 主账本也写不进去时，不许把后果动作放过去
        pass


def _emit(event: str, meta: dict) -> bool:
    """非后果动作的落账口：写不进去 -> 主账本 1 条，**不中止**（如实报，不伪成功）。
    后果动作（write）不走这里 —— 它走预检 + 中止。
    """
    try:
        _log_event(event, meta)
    except ChannelWriteError as exc:
        _channel_fail(str(meta.get("op") or "?"), "channel_write_failed", str(exc))
        return False
    return True


def _read_rows() -> list:
    p = events_path()
    if not p.is_file():
        return []
    rows = []
    for raw in p.read_bytes().split(b"\n"):
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw.decode("utf-8")))
        except ValueError:
            continue
    return rows


def _token_for_bucket(bucket: int, parts) -> str:
    body = "|".join(str(x) for x in parts) + "|" + str(bucket)
    return sha256(body.encode("utf-8")).hexdigest()


def build_confirm_token(*parts) -> str:
    """公开口：调用方（面板 / 设置页）按同一公式铸令牌，能力侧只校验。"""
    return _token_for_bucket(int(time.time() // TOKEN_WINDOW_S), parts)


def _token_ok(token, parts) -> bool:
    if not token:
        return False
    now = int(time.time() // TOKEN_WINDOW_S)
    return str(token) in (_token_for_bucket(now, parts),
                          _token_for_bucket(now - 1, parts))


def _reject_lexical_escape(value) -> str:
    """**字面**拒绝（在一切授权短路之前）：绝对路径/盘符 · 任何 `..` 段 · 保留目录 `.backup`。

    🔴 2026-10-25 · 为什么把它单独抽出来、并且提到短路之前：
      `_check_rel()` 与 `_resolve_target_name()` 里都有「拿到 `filesystem_write`
      授权 ⇒ 校验短路」的配方分支；而 F23 已实测该授权**恒为真**
      （`auth_gate.ENFORCED_SCOPES` 里没有 `filesystem_write`）⇒ **整条路径校验被跳过**，
      于是 `/abs.md` 被剥成相对、`a/./../b.md` 被归一化、`.backup/x.md` 落进备份区，
      盘上真的多出三个文件。⇒ 把**与授权无关的路径规则**提到短路之前：
      授权再大也不该让「绝对路径/上跳/写进保留目录」变成合法。
      **这不是放宽**：以前能过的这几种怪路径，现在一律 `WriteRootError`（`CreateError` 的子类）。
    """
    if not isinstance(value, str):
        raise CreateError("path 必须是字符串：%r" % (value,))
    raw = value.strip()
    if not raw:
        raise CreateError("缺少 path：写入必须给写入根下的相对路径")
    norm = raw.replace("\\", "/")
    if norm.startswith("/") or _DRIVE_RE.match(norm):
        raise WriteRootError("越界：`%s` 是绝对路径/带盘符 —— 写入根之外一律拒" % raw)
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise WriteRootError("越界：`%s` 含 `..` 段 —— 不许用归一化掩盖上跳" % raw)
    if parts and parts[0] == BACKUP_DIRNAME:
        raise WriteRootError("越界：`%s` 落在保留目录 `%s`（写前备份区）里"
                             % (raw, BACKUP_DIRNAME))
    return raw


def _check_rel(value) -> str:
    """相对路径闸门：越界一律拒（不靠"拼完再看一眼"）。

    🔴 配方 #1（`docs/无限制创作流水线.md §十三`）：拿到 `filesystem_write` 授权 ⇒
    **越界校验短路**（授权即过）；拿不到 ⇒ **逐字节走原分支**（回滚面）。
    唯一保留的是"必须有有效段落"：空路径无从落盘 —— 那不是限制，那是无意义。
    """
    raw = str(value or "").strip()
    if not raw:
        raise CreateError("缺少 path：写入必须给写入根下的相对路径")
    norm = raw.replace("\\", "/")
    if _authorized("filesystem_write", "file_operation._check_rel"):
        parts = [p for p in norm.split("/") if p not in ("", ".")]
        if not parts:
            raise CreateError("path 没有有效段落：%r" % raw)
        return "/".join(parts)
    if len(norm) > REL_MAX:
        raise CreateError("path 过长：%d > %d" % (len(norm), REL_MAX))
    if norm.startswith("/"):
        raise CreateError("path 不许是绝对路径：%r" % raw)
    if _DRIVE_RE.match(norm):
        raise CreateError("path 不许带盘符：%r" % raw)
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    if not parts:
        raise CreateError("path 没有有效段落：%r" % raw)
    if any(p == ".." for p in parts):
        raise CreateError("path 不许含 '..'：%r" % raw)
    if any(p.startswith(".") for p in parts):
        raise CreateError("path 不许含点号开头的段（隐藏文件 / .backup）：%r" % raw)
    return "/".join(parts)


def _resolve_target(rel: str) -> Path:
    root = _write_root_checked()
    # 🔴 2026-10-25 · **字面拒绝，不靠归一化**（原口径 → 新口径 → 为什么翻）：
    #   原口径：把 `rel` 拼到写根上再 `resolve()`，只要结果仍在写根内就放行。
    #   新口径：**在归一化之前**先按字面拒三样 —— ① 绝对路径/带盘符 ② 任何 `..` 段
    #           ③ 第一段是保留目录（`.backup`，即写前备份区）。
    #   为什么翻：`test_escape_paths_are_rejected_and_disk_untouched` 的契约是
    #   「越界一律拒，且**盘上零新增**」，而实测三种样例都**被写成了文件**
    #   （`_tree(root)` 里出现 `['.backup/x.md', 'abs.md', 'b.md']`）：
    #   `/abs.md` 被剥成相对、`a/./../b.md` 被归一化成 `b.md`、`.backup/x.md` 直接落在备份区。
    #   **这不是放宽**：以前能过的这几种怪路径，现在一律 `CreateError`（WriteRootError 是它的子类）。
    if not isinstance(rel, str) or not rel.strip():
        raise CreateError("path 必须是非空字符串：%r" % (rel,))
    raw = rel.replace("\\", "/")
    if raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
        raise WriteRootError("越界：`%s` 是绝对路径/带盘符 —— 写入根之外一律拒" % rel)
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise WriteRootError("越界：`%s` 含 `..` 段 —— 不许用归一化掩盖上跳" % rel)
    if parts and parts[0] == BACKUP_DIRNAME:
        raise WriteRootError("越界：`%s` 落在保留目录 `%s`（写前备份区）里"
                             % (rel, BACKUP_DIRNAME))
    target = (root / rel).resolve()
    if not target.is_relative_to(root):
        raise WriteRootError("越界：%s 不在写入根 %s 之内" % (rel, root))
    return target


def _backup(target: Path, old_bytes: bytes, rel: str, old_sha: str) -> dict:
    """写前备份 + 立刻自证「备份字节 == 原字节」。不等，不拖到事后。"""
    d = backup_root()
    d.mkdir(parents=True, exist_ok=True)
    flat = rel.replace("/", "__")
    stamp = time.strftime("%Y%m%dT%H%M%S")
    dest = d / ("%s-%s" % (stamp, flat))
    n = 1
    while dest.exists():
        dest = d / ("%s.%d-%s" % (stamp, n, flat))
        n += 1
    atomic_write_bytes(dest, old_bytes)
    back = dest.read_bytes()
    return {"rel": dest.relative_to(_write_root_checked()).as_posix(),
            "sha256": sha256(back).hexdigest(),
            "equal_to_original": (back == old_bytes),
            "matched_original_sha": (sha256(back).hexdigest() == old_sha)}


def _require_enabled(state: dict) -> None:
    if not state.get("enabled", True):
        raise CreateError("create.enabled = false：总开关关掉即全部动作拒绝")


def _check_content(value, name="content") -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CreateError("%s 必须是字符串（本刀只写文本）：%s" % (name, type(value).__name__))
    if len(value) > CONTENT_MAX:
        raise CreateError("%s 超上限：%d > %d 字符（拒绝而不是截断）"
                          % (name, len(value), CONTENT_MAX))
    return value


def _resolve_target_name(payload: dict, state: dict):
    """出口取值的三态（D4）：不指定 -> default；显式 user / agent_suggested -> 必须给 target。
    `target_source=default` **不许自带 target** —— 默认值只能来自设置页，不许被参数顶掉。

    🔴 配方 #2：拿到 `filesystem_write` 授权 ⇒ 三态校验短路（授权即过）；
    显式 target 优先，没给就用设置页默认值。拿不到 ⇒ **逐字节走原分支**（回滚面）。
    """
    source = str(payload.get("target_source") or "").strip().lower()
    target = str(payload.get("target") or "").strip()
    if _authorized("filesystem_write", "file_operation._resolve_target_name"):
        if target:
            return target, (source or "user")
        return (str(state.get("text_exit_target") or TEXT_EXIT_TARGET_DEFAULT),
                (source or "default"))
    if source and source not in TARGET_SOURCES:
        raise CreateError("target_source 只允许 %s：%r" % ("/".join(TARGET_SOURCES), source))
    if source == "default":
        if target and target != state.get("text_exit_target"):
            raise CreateError(
                "target_source=default 不许自带 target —— 默认出口取值只来自设置页（%r）"
                % state.get("text_exit_target"))
        return str(state.get("text_exit_target") or TEXT_EXIT_TARGET_DEFAULT), "default"
    if source in ("user", "agent_suggested"):
        if not target:
            raise CreateError("target_source=%s 必须显式给 target" % source)
        return target, source
    if not target:
        return str(state.get("text_exit_target") or TEXT_EXIT_TARGET_DEFAULT), "default"
    return target, "user"


def _op_status(payload: dict) -> dict:
    """**只读**：不落账、不建目录、零字节。"""
    now = time.time()
    cached = _STATUS_CACHE.get("at")
    if cached is not None and (now - float(cached)) < STATUS_TTL_S:
        return dict(_STATUS_CACHE["payload"], cached=True)
    state = read_state()
    root = write_root()
    base = {"ok": True, "channel": CHANNEL,
            "text_exit": {"target": str(state.get("text_exit_target") or TEXT_EXIT_TARGET_DEFAULT),
                          "target_source": str(state.get("text_exit_source") or "default"),
                          "status": "pending",
                          "wired": False,
                          "reason": "text_exit_not_wired",
                          # 🔴 **2026-09-23 补 `detail` / `policy`**：原来这里只报 `not_wired`，
                          #    读起来像"还没做"—— 结果**扫描器和我本人**都把它当成了待办
                          #    （`unimplemented_scan.py` 的 D 面据此报「动态不成立」，
                          #     我据此汇报"真实待办 = 1 条"）。
                          #    真相是：这是**这一刀的刻意范围边界**（模块头第 5 行就写着），
                          #    而且**默认出口 != 默认发布**。
                          #    ⇒ **报了"没接"就必须说清"为什么没接"**：解释性字段不是装饰，
                          #      它是**判据的输入** —— 有它，读者才分得清"缺陷"与"边界"。
                          "detail": "文本出口（AI 朋友圈 / eigenflux）本刀未接线 —— "
                                    "不注册 eigenflux cap、不发任何网络请求，如实报 pending，不伪造成功",
                          "policy": "本刀刻意排除发布端；默认出口 != 默认发布",
                          "policy_source": "SKILL-VETTING-REPORT-三块插件.md §自动发布 = A. 先不开"},
            "write_root": str(root), "write_root_exists": root.is_dir(),
            "content_max": CONTENT_MAX, "enabled": bool(state.get("enabled", True)),
            "ttl_s": STATUS_TTL_S}
    _STATUS_CACHE.update({"at": now, "payload": dict(base)})
    return dict(base, cached=False)


def _op_configure(payload: dict) -> dict:
    """设置页写默认出口 —— 默认出口不写死在模块里，也不写死在前端。"""
    state = read_state()
    _require_enabled(state)
    target = str(payload.get("target") or "").strip()
    if not target:
        raise CreateError("configure 必须给 target（默认出口由设置页写，不在前端写死）")
    new_state = dict(state)
    new_state["text_exit_target"] = target
    new_state["text_exit_source"] = "user"
    write_state(new_state)
    _emit("create_intent", {"op": "configure", "target": target, "target_source": "user"})
    return {"ok": True, "channel": CHANNEL, "text_exit_target": target,
            "text_exit_source": "user"}


def _op_intent(payload: dict) -> dict:
    """登记创作意图：`target` ＋ `target_source` 必落（D4）。**不发布、不出网**。"""
    state = read_state()
    _require_enabled(state)
    target, source = _resolve_target_name(payload, state)
    text = _check_content(payload.get("content"))
    digest = sha256(text.encode("utf-8")).hexdigest()
    _emit("create_intent", {"op": "intent", "target": target, "target_source": source,
                            "content_sha256": digest, "chars": len(text),
                            "published": False})
    return {"ok": True, "channel": CHANNEL, "action": "intent", "target": target,
            "target_source": source, "chars": len(text), "content_sha256": digest,
            "published": False, "network_attempted": False}


def _op_output(payload: dict) -> dict:
    """文本出口 —— 本刀**未接线**：如实报 pending，**一次网络请求都不发**。"""
    state = read_state()
    _require_enabled(state)
    target, source = _resolve_target_name(payload, state)
    text = _check_content(payload.get("content"))
    digest = sha256(text.encode("utf-8")).hexdigest()
    _emit("create_output", {"op": "output", "target": target, "target_source": source,
                            "content_sha256": digest, "chars": len(text),
                            "result": "pending", "published": False,
                            "network_attempted": False})
    return {"ok": False, "channel": CHANNEL, "action": "output", "status": "pending",
            "target": target, "target_source": source, "chars": len(text),
            "content_sha256": digest, "published": False, "network_attempted": False,
            "reason": "text_exit_not_wired",
            "detail": "文本出口（AI 朋友圈 / eigenflux）本刀未接线 —— 如实报 pending，不伪造成功"}


def _op_write(payload: dict) -> dict:
    """唯一**可逆后果**动作：仅写入根之内；覆盖必带 confirm_token ＋ 写前备份 ＋ 双向 SHA。"""
    _write_root_checked()  # R107 · 乙案：写入口闸门，先于一切副作用
    state = read_state()
    _require_enabled(state)
    rel = _check_rel(_reject_lexical_escape(payload.get("path")))
    new_text = _check_content(payload.get("content"))
    new_bytes = new_text.encode("utf-8")
    new_sha = sha256(new_bytes).hexdigest()
    target = _resolve_target(rel)
    if target.is_dir():
        raise CreateError("目标是目录：%s" % rel)
    overwrite = bool(payload.get("overwrite"))
    existed = target.is_file()
    old_bytes = b""
    old_sha = None
    if existed:
        old_bytes = target.read_bytes()
        old_sha = sha256(old_bytes).hexdigest()
        if old_bytes == new_bytes:
            # G7 幂等：同内容重复提交 -> 不落盘、不备份、不产生第二次覆盖
            _emit("create_write", {"op": "write", "path": rel, "bytes": len(new_bytes),
                                   "sha256": new_sha, "wrote": False, "overwrote": False,
                                   "idempotent": True, "backup": None})
            return {"ok": True, "channel": CHANNEL, "action": "write", "path": rel,
                    "abs": str(target), "bytes": len(new_bytes), "sha256": new_sha,
                    "wrote": False, "overwrote": False, "idempotent": True, "backup": None}
        if not overwrite:
            raise CreateError("目标已存在：%s（要覆盖就显式 overwrite=True ＋ confirm_token）" % rel)
        if not _token_ok(payload.get("confirm_token"), (rel, new_sha)):
            raise CreateError("confirm_token 不匹配（相对路径|新内容 sha256 改一个字即失效）")
    elif overwrite:
        # 🔴 配方 #3（"_op_write 覆盖当新建"）：拿到 `filesystem_write` 授权 ⇒ 该暗门**授权即过**；
        # 拿不到 ⇒ 逐字节走原分支（回滚面）。
        if not _authorized("filesystem_write",
                           "file_operation._op_write.overwrite_as_create"):
            raise CreateError("overwrite=True 但目标不存在：%s（不许把「覆盖」当「新建」的暗门）" % rel)
    try:
        _preflight_channel()
    except ChannelWriteError as exc:
        _channel_fail("write", "channel_write_failed", str(exc))
        return {"ok": False, "channel": CHANNEL, "action": "write", "status": "blocked",
                "path": rel, "wrote": False, "overwrote": False,
                "reason": "channel_write_failed",
                "detail": "通道写不进去 -> 不动盘，一个字节都不写"}
    backup = None
    if existed:
        info = _backup(target, old_bytes, rel, old_sha)
        if not (info["equal_to_original"] and info["matched_original_sha"]):
            raise CreateError("写前备份自证失败：备份字节 != 原字节")
        backup = info["rel"]
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(target, new_bytes)
    on_disk = target.read_bytes()
    verify_new = (sha256(on_disk).hexdigest() == new_sha)
    verify_backup = True if backup is None else (
        sha256((_write_root_checked() / backup).read_bytes()).hexdigest() == old_sha)
    _emit("create_write", {"op": "write", "path": rel, "bytes": len(on_disk),
                           "sha256": new_sha, "wrote": True, "overwrote": bool(existed),
                           "idempotent": False, "backup": backup,
                           "verify_new_sha": verify_new,
                           "verify_backup_sha": verify_backup})
    if not (verify_new and verify_backup):
        raise CreateError("写后双向 SHA 自证失败：new=%s backup=%s" % (verify_new, verify_backup))
    return {"ok": True, "channel": CHANNEL, "action": "write", "path": rel,
            "abs": str(target), "bytes": len(on_disk), "sha256": new_sha,
            "wrote": True, "overwrote": bool(existed), "idempotent": False,
            "backup": backup, "verify_new_sha": verify_new,
            "verify_backup_sha": verify_backup}


_OPS = {
    "status": _op_status,
    "configure": _op_configure,
    "intent": _op_intent,
    "output": _op_output,
    "write": _op_write,
}


def run(op, payload=None) -> dict:
    """动作分派（5 条，见模块头映射表）。坏 op / 坏参数 -> CreateError（user_error）。"""
    key = str(op or "").strip().lower()
    fn = _OPS.get(key)
    if fn is None:
        raise CreateError("未知 op：%r（可用：%s）" % (op, " / ".join(sorted(_OPS))))
    return fn(dict(payload or {}))
