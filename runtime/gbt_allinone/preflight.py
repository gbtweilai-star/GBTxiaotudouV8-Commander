"""GBT小土豆V8 · 执行前感知层。

任何有副作用或系统状态变化的动作，进入真实执行前都必须先回答三件事：
1. 同一动作是否已经在别的线程/进程执行；
2. 目标状态是否已经满足，不需要再做一次；
3. 本次动作观察到了什么证据。

本模块只增加“先看再动”和跨进程在途去重，不删除、禁用或降级任何能力。
主人显式传入 ``force: true`` 时跳过“已满足”复用，但仍保留并发锁，避免同一
动作在多个线程/进程中同时写入。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
from pathlib import Path

from ._paths import STORE_DIR
from .safe_io import FileLock, atomic_write_json, load_json

_GUARD_DIR = Path(STORE_DIR) / "action_guard"
_IGNORED_FIELDS = {
    "_probe",
    "_coding_discipline",
    "_force",
    "force",
}

_SIDE_EFFECT_SCOPES = {
    "process_execute",
    "filesystem_write",
    "remote_device",
    "deploy_publish",
    "browser_control",
    "desktop_control",
    "device_control",
    "external_llm",
    "data_export",
}

# 安全策略没有覆盖、但会改变框架自身状态的动作；新增动作默认在这里显式声明，
# 不能靠“没写 scope”就当只读。
_STATE_CHANGING_KINDS = {
    "wf_define",
    "wf_run",
    "wf_resume",
    "wf_cache_clear",
    "lr_submit",
    "lr_tick",
    "sched_define",
    "sched_tick",
    "root_fix",
    "devour_reflect",
    "devour_pulse",
}


def state_changing_kinds() -> frozenset:
    """「会改框架自身状态」的公开访问器（单一真源）。

    🔴 为什么要有它（2026-09-24 深修）：`cross_scan.PROBE_SKIP_KINDS` 当年是从探测
    视角手抄的一份 13 条名单，与这张表**各算各的** —— 9 个会改状态的位（`root_fix`
    `wf_run` `wf_cache_clear` `sched_tick` 等）不在探测名单里，`cross_scan` H 维
    的"逐个轻调用"当轮就真调过它们（`wf_cache_clear` 真清了传输缓存并回报
    `cleared:1`）。修法不是让两个消费方各并各的，而是：**改状态的唯一定义在这里**，
    探测名单从这里**派生**（`PROBE_SKIP_KINDS` 只保留纯探测语义的 4 条专项），
    谁要"要不要拦"的完整答案，用 `is_side_effect()` 或本函数 + 专项的并集。
    """
    return frozenset(_STATE_CHANGING_KINDS)

_READ_ONLY_TENTACLE = {
    "", "status", "eye", "see", "vision_snapshot", "screen_size", "screenshot_diff",
    "read_text", "list_windows", "process_list", "see_active_window", "window_list",
    "window_info", "active_window", "monitor", "detect", "ocr", "manifest",
    "app_running",
}

_BROWSER_PROCESS_NAMES = {
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe",
    "vivaldi.exe", "chromium.exe",
}

_BROWSER_ENGINE_HOSTS = {
    "bing": "bing.com",
    "baidu": "baidu.com",
    "google": "google.com",
    "duckduckgo": "duckduckgo.com",
}

_BROWSER_READ_ONLY_ACTIONS = {
    "status", "list_tabs", "get_title", "get_url", "get_text", "dom_query",
    "get_cookies", "intercept_events", "intercept_status",
}


def _clean_value(value):
    if isinstance(value, dict):
        return {
            str(k): _clean_value(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
            if str(k) not in _IGNORED_FIELDS and not str(k).startswith("_preflight_")
        }
    if isinstance(value, (list, tuple)):
        return [_clean_value(v) for v in value]
    if isinstance(value, set):
        return sorted((_clean_value(v) for v in value), key=lambda v: json.dumps(
            v, ensure_ascii=False, sort_keys=True, default=str))
    if isinstance(value, Path):
        return str(value)
    return value


def action_payload(payload: dict | None) -> dict:
    """去掉内部控制字段后的稳定动作载荷。"""
    return _clean_value(dict(payload or {}))


def fingerprint(kind: str, payload: dict | None) -> str:
    """动作身份指纹：同能力 + 同业务参数 = 同一动作。"""
    canonical = json.dumps(
        {"kind": str(kind or ""), "payload": action_payload(payload)},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    )
    # 🔴 2026-10-19：指纹要**永远算得出来**。payload 里混进孤立代理对（\udxxx）时，
    #    `encode("utf-8")` 会抛 UnicodeEncodeError ⇒ 整条感知层判故障 ⇒ 有副作用的调用被
    #    fail-closed 拒掉（实测：一次触手 move 就这么被挡回去）。`surrogatepass` 让坏字符
    #    也能进哈希：指纹只用来"认同一个动作"，不参与任何语义判断。
    return hashlib.sha256(canonical.encode("utf-8", "surrogatepass")).hexdigest()


def _decision_scopes(decision) -> set[str]:
    if not decision:
        return set()
    scopes = getattr(decision, "scopes", None)
    if scopes is None and isinstance(decision, dict):
        scopes = decision.get("scopes") or ()
    return {str(scope) for scope in (scopes or ())}


def is_side_effect(kind: str, payload: dict | None, decision=None) -> bool:
    """判断动作是否可能改变框架/系统状态。新动作默认不假定安全。"""
    kind = str(kind or "")
    payload = payload or {}
    if _decision_scopes(decision) & _SIDE_EFFECT_SCOPES:
        return True
    if kind in _STATE_CHANGING_KINDS:
        return True
    if kind == "file_hygiene":
        return bool(payload.get("fix"))
    if kind == "inventory":
        return bool(payload.get("fix"))
    if kind == "signature_guard":
        return bool(payload.get("restore"))
    if kind.startswith("room_"):
        if kind == "room_plan":
            return isinstance(payload.get("plan"), dict)
        return kind in {
            "room_create",
            "room_enter",
            "room_shape",
            "room_snapshot",
            "room_observe",
            "room_simulate",
            "room_parity",
            "room_rehearse",
            "room_gate",
            "room_release",
            "room_namespace",
        }
    if kind in {
        "collab_open",
        "collab_close",
        "collab_server_start",
        "collab_server_stop",
        "peer_register",
        "peer_request",
    }:
        return True
    if kind == "deploy_queue":
        return str(payload.get("op") or "status").lower() in ("submit", "tick")
    if kind == "omni_web":
        # 2026-10-04 补：与 security/policy.py 同一把尺（此前这里末尾 return False ⇒ 不认它）。
        #   读讲解/跑项目 = 只打 GitHub API、只生成 URL ⇒ 无副作用；
        #   其余（含 read_source 本地路径读文件、edit_file 写盘、gitingest 克隆落盘、
        #   以及未列出的 op）一律算副作用 —— fail-closed。
        op = str(payload.get("op") or "read_structure").lower()
        if op in ("read_explanation", "讲解", "读讲解", "explain", "wiki",
                  "stackblitz", "跑项目", "run"):
            return False
        return True
    if kind == "tentacle":
        action = str(payload.get("action") or "").lower()
        return action not in _READ_ONLY_TENTACLE
    if kind == "browser":
        op = str(payload.get("op") or "open").lower()
        if op in ("native", "deep", "controller", "cdp"):
            action = str(payload.get("action") or payload.get("cmd") or "status").lower()
            return action not in _BROWSER_READ_ONLY_ACTIONS
        return op not in ("status", "fetch")
    if kind in ("anatomy_figures", "machine_film"):
        # 2026-10-19 接入的两个外部件（主人令「这两个能力不完美补齐缺失了吗」）：
        # 读面（status/examples/docs/where）是纯读；写面会**落盘 + 起 extern 运行时**
        # （anatomy：node 构建页面/印张；machine：本机无头 Chrome 逐帧录制 + ffmpeg），
        # 按"写到盘上就是副作用"的老口径显式声明——不靠"没写 scope"当只读（同 omni_web 那一刀）。
        return str(payload.get("op") or "status").lower() in ("build", "verify", "shot", "film")
    if kind in ("rig_audit", "rig_fix", "anim_audit", "anim_fix", "dh_asset_gate"):
        # 2026-10-19 建模绑骨五位一套：**逐位按它自己会不会落盘**判，不按名字一刀切。
        #   · anim_audit / dh_asset_gate：纯读，永远不算副作用；
        #   · rig_audit：run 会写派生 .js（页面用 <script> 吃），check/status 不写；
        #   · rig_fix：run 写 outputs/rig-fix/（glb + 转台图 + report）；
        #   · anim_fix：dry=true 只自检不落盘，dry=false 才写 dst。
        op = str(payload.get("op") or "status").lower()
        if kind in ("anim_audit", "dh_asset_gate"):
            return False
        if kind == "rig_audit":
            return op == "run"
        if kind == "rig_fix":
            return op == "run"
        if kind == "anim_fix":
            return op == "run" and not bool(payload.get("dry"))
        return False
    if kind == "omni_arm":
        # 2026-10-19：build 会跑 Blender 建件并落 GLB/规格/报告 ⇒ 只有 build 算副作用。
        return str(payload.get("op") or "status").lower() == "build"
    if kind == "tentacle_arm":
        # 2026-10-19 触手操控臂：plan/limits/status/where 纯读；**move 会真动触手** ⇒ 算副作用，
        # 但它自己不收票（票由被动的那个能力位自己的门收）——所以这里只声明"会动"，不重复要票。
        return str(payload.get("op") or "status").lower() == "move"
    return False


def _normalize_url(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if not re.match(r"^[a-z][a-z0-9+.-]*://", value, re.I):
        value = "https://" + value
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return value
    host = (parsed.hostname or "").lower()
    if not host:
        return value
    try:
        port = parsed.port
    except ValueError:
        return value
    path = re.sub(r"/+", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query.sort()
    normalized = urllib.parse.urlunsplit((
        parsed.scheme.lower() or "https",
        host + (f":{port}" if port else ""),
        path,
        urllib.parse.urlencode(query),
        "",
    ))
    return normalized


def _url_host(raw: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(raw if "://" in raw else "https://" + raw)
        return (parsed.hostname or "").lower()
    except ValueError:
        return ""


def _title_matches_target(title: str, target_url: str, query: str = "") -> bool:
    title = str(title or "").strip()
    target = str(target_url or "").strip()
    if not title or not target:
        return False
    low = title.lower()
    normalized = _normalize_url(target)
    if normalized and normalized.lower().rstrip("/") in low:
        return True
    host = _url_host(target)
    if not host:
        return False
    if query:
        return host in low and str(query).lower() in low
    try:
        parsed = urllib.parse.urlsplit(target if "://" in target else "https://" + target)
    except ValueError:
        return False
    # 标题通常只有域名，主页/无路径目标可据此确认；深链接不能只凭域名误判。
    return host in low and (not parsed.path or parsed.path == "/") and not parsed.query


def _windows_browser_windows() -> list[dict]:
    """枚举可见浏览器窗口；仅返回窗口与浏览器进程身份。"""
    if os.name != "nt":
        return []
    try:
        from .dependency_paths import activate_local_dependencies
        activate_local_dependencies()
        import psutil
    except Exception:
        return []

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    windows: list[dict] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            proc_name = (psutil.Process(pid.value).name() or "").lower()
        except Exception:
            return True
        if proc_name in _BROWSER_PROCESS_NAMES:
            windows.append({
                "hwnd": int(hwnd),
                "pid": int(pid.value),
                "process": proc_name,
                "title": title[:300],
            })
        return True

    try:
        user32.EnumWindows(_callback, 0)
    except Exception:
        return []
    return windows


def _uia_address_for_window(hwnd: int) -> str:
    """尽力从浏览器地址栏读取当前 URL；失败时返回空串，绝不猜。"""
    if os.name != "nt":
        return ""
    try:
        from .dependency_paths import activate_local_dependencies
        activate_local_dependencies()
        import uiautomation as auto
    except Exception:
        return ""

    try:
        with auto.UIAutomationInitializerInThread():
            window = auto.ControlFromHandle(hwnd)
            if window is None:
                return ""
            budget = [600]

            def _walk(node, depth=0):
                if depth > 10 or budget[0] <= 0:
                    return ""
                budget[0] -= 1
                try:
                    children = node.GetChildren()
                except Exception:
                    children = []
                for child in children:
                    if budget[0] <= 0:
                        return ""
                    try:
                        control_type = (child.ControlTypeName or "").lower()
                        automation_id = (child.AutomationId or "").lower()
                        name = (child.Name or "").lower()
                        looks_like_address = (
                            ("edit" in control_type and (
                                "address" in automation_id or "url" in automation_id
                                or "地址" in name or "search" in automation_id
                            ))
                            or automation_id in {
                                "address and search bar", "urlbar-input",
                                "urlbar", "omnibox",
                            }
                        )
                        if looks_like_address:
                            try:
                                value = child.GetValuePattern().Value
                            except Exception:
                                value = ""
                            value = str(value or "").strip()
                            if value and re.match(r"^[a-z][a-z0-9+.-]*://", value, re.I):
                                return value
                            if value and ("." in value or "localhost" in value.lower()):
                                return _normalize_url(value)
                        found = _walk(child, depth + 1)
                        if found:
                            return found
                    except Exception:
                        continue
                return ""

            return _walk(window)
    except Exception:
        return ""


def observe_browser(payload: dict | None) -> dict:
    """检查系统浏览器中是否已打开同一 URL/同一搜索页。"""
    payload = payload or {}
    op = str(payload.get("op") or "open").lower()
    if op not in ("open", "goto", "search"):
        return {"checked": False, "matched": False, "reason": "op_not_observable"}

    if op == "search":
        engine = str(payload.get("engine") or "bing").lower()
        query = str(payload.get("query") or "").strip()
        host = _BROWSER_ENGINE_HOSTS.get(engine, "")
        target_url = f"https://{host}/" if host else ""
    else:
        query = ""
        target_url = str(payload.get("url") or "").strip()
        host = _url_host(target_url)

    windows = _windows_browser_windows()
    if not windows:
        return {
            "checked": True,
            "matched": False,
            "browser_running": False,
            "reason": "no_browser_window",
        }

    normalized_target = _normalize_url(target_url)
    for window in windows:
        current_url = _uia_address_for_window(window["hwnd"])
        matched = bool(current_url and normalized_target
                      and _normalize_url(current_url) == normalized_target)
        method = "uia_url"
        if not matched and query and current_url:
            current_host = _url_host(current_url)
            title = window.get("title") or ""
            matched = bool(host and host in current_host
                           and (query.lower() in current_url.lower()
                                or query.lower() in title.lower()))
            method = "uia_search"
        if not matched:
            matched = _title_matches_target(
                window.get("title") or "", target_url, query=query)
            method = "window_title"
        if matched:
            return {
                "checked": True,
                "matched": True,
                "browser_running": True,
                "method": method,
                "process": window.get("process"),
                "pid": window.get("pid"),
                "host": host or None,
                "note": "目标已在现有浏览器窗口中打开，复用现场，不重复启动。",
            }

    return {
        "checked": True,
        "matched": False,
        "browser_running": True,
        "reason": "browser_running_page_not_matched",
        "host": host or None,
        "note": "浏览器已在运行，但没有确认到同一目标页；继续原动作。",
    }


def _process_or_window_matches(app: str) -> dict:
    target = str(app or "").strip()
    if not target:
        return {"checked": True, "matched": False, "reason": "empty_app"}
    try:
        from .dependency_paths import activate_local_dependencies
        activate_local_dependencies()
        import psutil
    except Exception:
        return {"checked": False, "matched": False, "reason": "psutil_unavailable"}

    needle = Path(target).name.lower()
    if needle.endswith(".exe"):
        needle = needle[:-4]
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = str((proc.info or {}).get("name") or "").lower()
            if needle and needle in name:
                return {
                    "checked": True,
                    "matched": True,
                    "method": "process",
                    "pid": proc.pid,
                    "process": name,
                }
        except Exception:
            continue
    return {"checked": True, "matched": False, "reason": "process_not_running"}


def _observe_mcp_connect(payload: dict) -> dict:
    server = str(payload.get("server") or "").strip()
    if not server:
        return {"checked": True, "matched": False, "reason": "missing_server"}
    try:
        from .tentacle import mcp_bridge
        alive = bool(
            mcp_bridge.status().get("servers", {}).get(server, {}).get("alive")
        )
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False, "reason": "mcp_status_error",
                "error": str(exc)[:120]}
    return {
        "checked": True,
        "matched": alive,
        "method": "mcp_session_registry",
        "server": server,
        "reason": "server_session_alive" if alive else "server_session_not_alive",
        "note": ("该 MCP 服务会话已存活，复用现有连接。"
                 if alive else "未发现同服务的存活会话，继续原连接动作。"),
    }


def _observe_desktop_commander(payload: dict) -> dict:
    op = str(payload.get("op") or "status").lower()
    if op not in ("connect", "remote_start", "remote_stop"):
        return {"checked": False, "matched": False, "reason": "op_not_observable"}
    try:
        from .tentacle import desktop_commander as dc
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False, "reason": "dc_import_error",
                "error": str(exc)[:120]}
    try:
        if op == "connect":
            alive = bool(dc.status().get("connected"))
            matched = alive
            reason = "dc_session_alive" if alive else "dc_session_not_alive"
            note = ("桌面指挥官 MCP 会话已连接，复用现有连接。"
                    if matched else "桌面指挥官尚未连接，继续原连接动作。")
        else:
            running = bool(dc.remote_status().get("running"))
            matched = running if op == "remote_start" else not running
            reason = (
                "remote_already_running" if op == "remote_start" and matched else
                "remote_not_running" if op == "remote_start" else
                "remote_already_stopped" if matched else
                "remote_still_running"
            )
            note = (
                "远程设备已经在运行，复用现有实例。"
                if op == "remote_start" and matched else
                "远程设备未在运行，继续原启动动作。"
                if op == "remote_start" else
                "远程设备已经停止，无需重复停止。"
                if matched else
                "远程设备仍在运行，继续原停止动作。"
            )
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False, "reason": "dc_status_error",
                "error": str(exc)[:120]}
    return {
        "checked": True,
        "matched": matched,
        "method": "desktop_commander_state",
        "op": op,
        "reason": reason,
        "note": note,
    }


def _observe_workflow_define(payload: dict) -> dict:
    name = str(payload.get("name") or "")
    nodes = payload.get("nodes")
    if not name or not isinstance(nodes, list) or not nodes:
        return {"checked": True, "matched": False, "reason": "missing_workflow_body"}
    try:
        from . import engine
        current = engine._load().get(name)
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False, "reason": "workflow_state_error",
                "error": str(exc)[:120]}
    matched = bool(current and current.get("nodes") == nodes)
    return {
        "checked": True,
        "matched": matched,
        "method": "workflow_definition_state",
        "name": name,
        "reason": "definition_already_equal" if matched else "definition_absent_or_changed",
        "note": ("同名工作流定义已经与本次一致，复用现有定义。"
                 if matched else "工作流定义不存在或内容不同，继续原定义动作。"),
    }


def _observe_schedule_define(payload: dict) -> dict:
    name = str(payload.get("name") or "")
    workflow = str(payload.get("workflow") or "")
    if not name or not workflow:
        return {"checked": True, "matched": False, "reason": "missing_schedule_body"}
    try:
        from . import schedule
        current = schedule.status(name).get(name) or {}
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False, "reason": "schedule_state_error",
                "error": str(exc)[:120]}
    try:
        every = int(payload.get("every_seconds"))
    except (TypeError, ValueError):
        return {"checked": True, "matched": False, "reason": "invalid_interval"}
    enabled = bool(payload.get("enabled", True))
    matched = bool(
        current
        and str(current.get("workflow")) == workflow
        and int(current.get("every_seconds", 0)) == every
        and bool(current.get("enabled", True)) == enabled
    )
    return {
        "checked": True,
        "matched": matched,
        "method": "schedule_definition_state",
        "name": name,
        "reason": "schedule_already_equal" if matched else "schedule_absent_or_changed",
        "note": ("同名调度定义已经与本次一致，复用现有调度。"
                 if matched else "调度定义不存在或内容不同，继续原定义动作。"),
    }


def _observe_cache_clear(payload: dict) -> dict:
    del payload
    try:
        from . import engine
        cache = engine._cache_all()
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False, "reason": "cache_state_error",
                "error": str(exc)[:120]}
    matched = not bool(cache)
    return {
        "checked": True,
        "matched": matched,
        "method": "transfer_cache_state",
        "reason": "cache_already_empty" if matched else "cache_not_empty",
        "note": ("传输缓存已经为空，无需重复清理。"
                 if matched else "传输缓存非空，继续原清理动作。"),
    }


def _observe_pipeline_rollback(payload: dict) -> dict:
    name = str(payload.get("name") or "")
    if not name:
        return {"checked": True, "matched": False, "reason": "missing_name"}
    try:
        from . import pipeline
        pipeline._ensure()
        normalized = pipeline._normalized_name(name)
        prod = pipeline._prod_path(normalized)
        vdir = pipeline._VERSIONS / normalized
        if not prod.exists() or not vdir.exists():
            return {"checked": True, "matched": False,
                    "reason": "production_or_history_missing"}
        hist = sorted(vdir.glob("v*"), key=lambda item: item.stat().st_mtime)
        if not hist:
            return {"checked": True, "matched": False, "reason": "history_missing"}
        to_version = payload.get("to_version")
        target = None
        if to_version is None:
            target = hist[-1]
        else:
            wanted = int(to_version)
            for item in hist:
                try:
                    if int(item.stem[1:].split(".")[0]) == wanted:
                        target = item
                        break
                except ValueError:
                    continue
        if target is None:
            return {"checked": True, "matched": False, "reason": "target_missing"}
        current_digest = pipeline._sha256(prod.read_bytes())
        target_digest = pipeline._sha256(target.read_bytes())
    except (TypeError, ValueError) as exc:
        return {"checked": True, "matched": False, "reason": "invalid_version",
                "error": str(exc)[:120]}
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False, "reason": "pipeline_state_error",
                "error": str(exc)[:120]}
    matched = current_digest == target_digest
    return {
        "checked": True,
        "matched": matched,
        "method": "pipeline_current_vs_target_digest",
        "name": normalized,
        "target": target.name,
        "reason": "target_already_current" if matched else "current_differs_from_target",
        "note": ("目标版本内容已经在生产中，无需重复回滚。"
                 if matched else "当前生产内容与目标版本不同，继续原回滚动作。"),
    }


def _observe_mirror_plan(payload: dict) -> dict:
    plan = payload.get("plan")
    name = str(payload.get("name") or "default")
    if not isinstance(plan, dict):
        return {"checked": True, "matched": False, "reason": "read_only_lookup"}
    try:
        from . import deployment_rehearsal as DR
        current = DR.get_plan(name)
        normalized = DR._normalize_plan(plan)
        incoming_sha = DR._json_sha(normalized)
    except Exception as exc:  # noqa: BLE001
        return {
            "checked": False,
            "matched": False,
            "reason": "mirror_plan_state_error",
            "error": str(exc)[:120],
        }
    matched = incoming_sha == current.get("plan_sha")
    return {
        "checked": True,
        "matched": matched,
        "method": "deployment_rehearsal_plan_sha",
        "name": name,
        "plan_sha": incoming_sha,
        "reason": "plan_already_equal" if matched else "plan_absent_or_changed",
        "note": ("同名排练计划已经与本次内容一致，复用现有定义。"
                 if matched else "排练计划不存在或内容不同，继续原定义动作。"),
    }


def _observe_mirror_shape(payload: dict) -> dict:
    path = str(payload.get("path") or "")
    if not path or payload.get("delete"):
        return {"checked": True, "matched": False, "reason": "read_only_or_delete"}
    try:
        from . import mirror_space as MS
        from .safe_io import safe_relative_path
        target = safe_relative_path(MS._DIM, path)
        if not target.is_file():
            return {"checked": True, "matched": False,
                    "reason": "mirror_file_absent"}
        incoming = hashlib.sha256(
            str(payload.get("content", "")).encode("utf-8")
        ).hexdigest()[:16]
        current = MS._sha_file(target)
    except ValueError:
        return {"checked": True, "matched": False,
                "reason": "mirror_path_escape"}
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False,
                "reason": "mirror_shape_state_error", "error": str(exc)[:120]}
    matched = incoming == current
    return {
        "checked": True,
        "matched": matched,
        "method": "mirror_dimension_file_digest",
        "path": path,
        "sha": current,
        "reason": "mirror_content_already_equal" if matched else "mirror_content_changed",
        "note": ("镜像维度内同一路径内容已经一致，无需重复写入。"
                 if matched else "镜像文件不存在或内容不同，继续原写入动作。"),
    }


def _observe_room_create(payload: dict) -> dict:
    room_id = str(payload.get("room_id") or payload.get("id") or "default")
    try:
        from . import room_space as RS
        root = RS._room_root(room_id)
        meta = RS.load_json(RS._meta_path(root), None)
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False,
                "reason": "room_state_error", "error": str(exc)[:120]}
    matched = isinstance(meta, dict)
    return {
        "checked": True,
        "matched": matched,
        "method": "room_metadata_exists",
        "room_id": room_id,
        "reason": "room_already_exists" if matched else "room_absent",
        "note": ("同名房间已经存在，复用现场，不重复初始化。"
                 if matched else "房间尚不存在，继续创建。"),
    }


def _observe_room_shape(payload: dict) -> dict:
    room_id = str(payload.get("room_id") or payload.get("id") or "default")
    path = str(payload.get("path") or "")
    if not path:
        return {"checked": True, "matched": False, "reason": "read_only_lookup"}
    try:
        from . import room_space as RS
        root, _meta = RS._room_meta(room_id)
        dim = RS._dirs(root)["dimension"]
        target = RS.safe_relative_path(dim, path)
        if not target.is_file():
            return {"checked": True, "matched": False,
                    "reason": "room_file_absent"}
        incoming = hashlib.sha256(
            str(payload.get("content", "")).encode("utf-8")
        ).hexdigest()[:16]
        current = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
    except ValueError:
        return {"checked": True, "matched": False,
                "reason": "room_path_escape"}
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False,
                "reason": "room_shape_state_error", "error": str(exc)[:120]}
    matched = incoming == current
    return {
        "checked": True,
        "matched": matched,
        "method": "room_dimension_file_digest",
        "room_id": room_id,
        "path": path,
        "sha": current,
        "reason": "room_content_already_equal" if matched else "room_content_changed",
        "note": ("房间同一路径内容已经一致，无需重复写入。"
                 if matched else "房间文件不存在或内容不同，继续原写入动作。"),
    }


def _observe_mirror_rewind(payload: dict) -> dict:
    try:
        from . import mirror_space as MS
        version = int(payload.get("version", 1))
    except (TypeError, ValueError) as exc:
        return {"checked": True, "matched": False, "reason": "invalid_version",
                "error": str(exc)[:120]}
    try:
        target = MS._TIMELINES / f"v{version}"
        if not target.is_dir():
            return {"checked": True, "matched": False,
                    "reason": "timeline_missing"}
        target_tree = MS._tree_fingerprint(target)
        reality_tree = MS._tree_fingerprint(MS._REALITY)
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False,
                "reason": "mirror_rewind_state_error", "error": str(exc)[:120]}
    matched = target_tree == reality_tree
    return {
        "checked": True,
        "matched": matched,
        "method": "mirror_timeline_vs_reality",
        "version": version,
        "reason": "timeline_already_current" if matched else "reality_differs",
        "note": ("目标时间线已经是当前生产现实，无需重复整树替换。"
                 if matched else "当前生产现实与目标时间线不同，继续原回滚动作。"),
    }


def _observe_file_hygiene(payload: dict) -> dict:
    if not payload.get("fix"):
        return {"checked": True, "matched": False, "reason": "read_only_scan"}
    try:
        from . import hygiene
        result = hygiene.scan(fix=False)
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False,
                "reason": "file_hygiene_state_error", "error": str(exc)[:120]}
    matched = bool(
        result.get("verdict") == "clean"
        and not result.get("findings")
        and int(result.get("cache_cleared", 0) or 0) == 0
    )
    return {
        "checked": True,
        "matched": matched,
        "method": "file_hygiene_clean_scan",
        "reason": "hygiene_already_clean" if matched else "hygiene_findings_present",
        "note": ("家规扫描全净且缓存为空，无需重复执行归位。"
                 if matched else "仍有卫生项或缓存需要处理，继续原修复动作。"),
    }


def _observe_inventory_fix(payload: dict) -> dict:
    if not payload.get("fix"):
        return {"checked": True, "matched": False, "reason": "read_only_scan"}
    try:
        from . import inventory
        result = inventory.scan(fix=False)
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False,
                "reason": "inventory_state_error", "error": str(exc)[:120]}
    foreign = ((result.get("items") or {}).get("foreign") or [])
    matched = result.get("verdict") == "clean" and not foreign
    return {
        "checked": True,
        "matched": matched,
        "method": "inventory_foreign_scan",
        "reason": "inventory_already_clean" if matched else "inventory_foreign_present",
        "note": ("全息盘点没有异物，无需重复执行清理。"
                 if matched else "盘点仍发现异物，继续原修复动作。"),
    }


def _observe_signature_restore(payload: dict) -> dict:
    if not payload.get("restore"):
        return {"checked": True, "matched": False, "reason": "read_only_audit"}
    try:
        from . import signature
        result = signature.audit(restore=False)
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "matched": False,
                "reason": "signature_state_error", "error": str(exc)[:120]}
    missing = result.get("missing") or []
    matched = result.get("verdict") == "clean" and not missing
    return {
        "checked": True,
        "matched": matched,
        "method": "signature_missing_scan",
        "reason": "signature_already_complete" if matched else "signature_missing",
        "note": ("所有页面署名完整，无需重复恢复。"
                 if matched else "仍有页面缺少署名，继续原恢复动作。"),
    }


def observe(kind: str, payload: dict | None) -> dict:
    """按能力调用现实探针；未注册探针时如实返回 no_probe。"""
    kind = str(kind or "")
    payload = payload or {}
    if kind == "browser":
        return observe_browser(payload)
    if kind == "mcp_connect":
        return _observe_mcp_connect(payload)
    if kind == "desktop_commander":
        return _observe_desktop_commander(payload)
    if kind == "wf_define":
        return _observe_workflow_define(payload)
    if kind == "sched_define":
        return _observe_schedule_define(payload)
    if kind == "wf_cache_clear":
        return _observe_cache_clear(payload)
    if kind == "pipeline_rollback":
        return _observe_pipeline_rollback(payload)
    if kind == "mirror_plan":
        return _observe_mirror_plan(payload)
    if kind == "mirror_shape":
        return _observe_mirror_shape(payload)
    if kind == "room_create":
        return _observe_room_create(payload)
    if kind == "room_shape":
        return _observe_room_shape(payload)
    if kind == "mirror_rewind":
        return _observe_mirror_rewind(payload)
    if kind == "file_hygiene":
        return _observe_file_hygiene(payload)
    if kind == "inventory":
        return _observe_inventory_fix(payload)
    if kind == "signature_guard":
        return _observe_signature_restore(payload)
    if kind == "tentacle" and str(payload.get("action") or "").lower() == "launch":
        args = payload.get("args")
        app = payload.get("app") or payload.get("target")
        if isinstance(args, (list, tuple)) and args:
            app = args[0]
        result = _process_or_window_matches(str(app or ""))
        result["note"] = (
            "目标应用已经在运行，复用现场，不重复启动。"
            if result.get("matched") else
            "未确认目标应用正在运行，继续原启动动作。"
        )
        return result
    return {"checked": False, "matched": False, "reason": "no_reality_probe"}


class ActionLease:
    """跨线程/跨进程动作租约；OS 锁随进程退出自动释放。"""

    def __init__(self, kind: str, action_fingerprint: str):
        self.kind = kind
        self.fingerprint = action_fingerprint
        self.path = _GUARD_DIR / f"{action_fingerprint}.lock"
        self.state_path = _GUARD_DIR / f"{action_fingerprint}.json"
        self.lock = FileLock(self.path, timeout=0)

    def acquire(self) -> bool:
        try:
            self.lock.acquire()
        except TimeoutError:
            return False
        try:
            atomic_write_json(self.state_path, {
                "status": "running",
                "kind": self.kind,
                "fingerprint": self.fingerprint,
                "pid": os.getpid(),
                "started_at": time.time(),
                "started_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
        except Exception:
            self.lock.release()
            raise
        return True

    def finish(self, status: str, detail=None) -> None:
        try:
            previous = load_json(self.state_path, {}) or {}
            previous.update({
                "status": status,
                "finished_at": time.time(),
                "finished_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "detail": detail if isinstance(detail, dict) else {},
            })
            atomic_write_json(self.state_path, previous)
        finally:
            self.lock.release()


def before_action(kind: str, payload: dict | None, *, decision=None,
                  force: bool = False) -> dict:
    """统一执行前门禁。

    返回 status=not_guarded|reuse|already_running|acquired。``acquired`` 时
    调用方必须在动作结束后调用 ``lease.finish``。
    """
    payload = payload or {}
    if not is_side_effect(kind, payload, decision):
        return {"status": "not_guarded", "side_effect": False}

    action_fingerprint = fingerprint(kind, payload)
    observation = observe(kind, payload)
    if observation.get("matched") and not force:
        return {
            "status": "reuse",
            "side_effect": True,
            "fingerprint": action_fingerprint,
            "observation": observation,
        }

    lease = ActionLease(kind, action_fingerprint)
    if not lease.acquire():
        state = load_json(lease.state_path, {}) or {}
        return {
            "status": "already_running",
            "side_effect": True,
            "fingerprint": action_fingerprint,
            "observation": observation,
            "running": state,
        }
    return {
        "status": "acquired",
        "side_effect": True,
        "fingerprint": action_fingerprint,
        "observation": observation,
        "lease": lease,
    }


def status() -> dict:
    """只读报告感知层配置与当前锁目录规模。"""
    locks = list(_GUARD_DIR.glob("*.lock")) if _GUARD_DIR.exists() else []
    states = list(_GUARD_DIR.glob("*.json")) if _GUARD_DIR.exists() else []
    return {
        "ok": True,
        "side_effect_scopes": sorted(_SIDE_EFFECT_SCOPES),
        "state_changing_kinds": sorted(_STATE_CHANGING_KINDS),
        "probes": [
            "browser",
            "desktop_commander.connect",
            "desktop_commander.remote_start",
            "desktop_commander.remote_stop",
            "file_hygiene",
            "inventory",
            "mcp_connect",
            "mirror_plan",
            "mirror_rewind",
            "mirror_shape",
            "pipeline_rollback",
            "room_create",
            "room_shape",
            "sched_define",
            "signature_guard",
            "tentacle.launch",
            "wf_cache_clear",
            "wf_define",
        ],
        "lock_files": len(locks),
        "state_files": len(states),
        "note": "执行前先检查在途状态与已满足状态；force=true 仅跳过已满足复用，不绕过并发锁。",
    }
