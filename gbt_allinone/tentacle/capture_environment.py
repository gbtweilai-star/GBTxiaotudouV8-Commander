"""Read-only Windows display/capture environment diagnostics.

This module does not install drivers, change proxy settings, or modify the
desktop. It only reports the process desktop session, display adapters, and
available Python capture backends so the existing vision stack can choose the
right target instead of assuming output 0 on device 0.
"""
from __future__ import annotations

import ctypes
import importlib.util
import os
import time
from ctypes import wintypes
from typing import Any


_SM_REMOTESESSION = 0x1000
_MONITORINFOF_PRIMARY = 0x00000001
_DISPLAY_DEVICE_ACTIVE = 0x00000001
_DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004
_DISPLAY_DEVICE_MIRRORING_DRIVER = 0x00000008
_UOI_NAME = 2


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class _MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


class _DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def assert_not_silent(payload: dict, where: str = "") -> dict:
    """带牙守卫（R-H203 · 修 G3）：**失败必须有出口** ——
    失败（`ok is False`）时必须同时给出 `reason`（为什么）与 `next`（下一步怎么办），
    缺一 ⇒ 判 `silent_failure`（死角定义：**不会还不说**）。
    """
    out = dict(payload or {})
    if out.get("ok") is False:
        missing = [k for k in ("reason", "next") if not str(out.get(k) or "").strip()]
        if missing:
            return {"ok": False, "denied": True, "rule": "silent_failure",
                    "where": str(where or ""), "missing": missing,
                    "why": "静默失败 = 没有失败出口 = 真死角：必须回结构化否决 + reason + next"}
    return {"ok": True, "readonly": True}


def _int_env(name: str, default: int | None = None) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _window_station_names() -> tuple[str, str]:
    if os.name != "nt":
        return "", ""
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.GetProcessWindowStation.restype = wintypes.HANDLE
        user32.GetThreadDesktop.restype = wintypes.HANDLE
        user32.GetUserObjectInformationW.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        user32.GetUserObjectInformationW.restype = wintypes.BOOL

        def _name(handle) -> str:
            if not handle:
                return ""
            needed = wintypes.DWORD(0)
            # The null-buffer call is a size probe: it legitimately returns
            # FALSE with ERROR_INSUFFICIENT_BUFFER and fills `needed`. Only a
            # zero size means the handle is unusable, otherwise every Windows
            # session would be misreported as non-interactive.
            user32.GetUserObjectInformationW(
                handle, _UOI_NAME, None, 0, ctypes.byref(needed))
            if int(needed.value) <= 0:
                return ""
            buffer = ctypes.create_unicode_buffer(int(needed.value))
            if not user32.GetUserObjectInformationW(
                    handle, _UOI_NAME, buffer, needed, ctypes.byref(needed)):
                return ""
            return str(buffer.value or "")

        station = _name(user32.GetProcessWindowStation())
        desktop = _name(user32.GetThreadDesktop(kernel32.GetCurrentThreadId()))
        return station, desktop
    except Exception:
        return "", ""


def _enumerate_monitors() -> list[dict[str, Any]]:
    if os.name != "nt":
        return []
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        monitor_enum_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(_RECT),
            wintypes.LPARAM,
        )
        user32.GetMonitorInfoW.argtypes = [
            wintypes.HMONITOR,
            ctypes.POINTER(_MONITORINFOEXW),
        ]
        user32.GetMonitorInfoW.restype = wintypes.BOOL
        user32.EnumDisplayMonitors.argtypes = [
            wintypes.HDC,
            ctypes.POINTER(_RECT),
            monitor_enum_proc,
            wintypes.LPARAM,
        ]
        user32.EnumDisplayMonitors.restype = wintypes.BOOL
        rows: list[dict[str, Any]] = []

        def _callback(handle, _hdc, _rect, _data):
            info = _MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(info)
            if not user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                return True
            rows.append({
                "index": len(rows),
                "device": str(info.szDevice or ""),
                "primary": bool(info.dwFlags & _MONITORINFOF_PRIMARY),
                "rect": {
                    "left": int(info.rcMonitor.left),
                    "top": int(info.rcMonitor.top),
                    "right": int(info.rcMonitor.right),
                    "bottom": int(info.rcMonitor.bottom),
                },
                "width": int(info.rcMonitor.right - info.rcMonitor.left),
                "height": int(info.rcMonitor.bottom - info.rcMonitor.top),
            })
            return True

        if not user32.EnumDisplayMonitors(
                None, None, monitor_enum_proc(_callback), 0):
            return []
        return rows
    except Exception:
        return []


def _adapter_for_monitor(device: str) -> dict[str, Any]:
    if os.name != "nt" or not device:
        return {}
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.EnumDisplayDevicesW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(_DISPLAY_DEVICEW),
            wintypes.DWORD,
        ]
        user32.EnumDisplayDevicesW.restype = wintypes.BOOL
        info = _DISPLAY_DEVICEW()
        info.cb = ctypes.sizeof(info)
        if not user32.EnumDisplayDevicesW(
                device, 0, ctypes.byref(info), 0):
            return {}
        return {
            "device": device,
            "name": str(info.DeviceString or ""),
            "device_id": str(info.DeviceID or ""),
            "device_key": str(info.DeviceKey or ""),
            "state_flags": int(info.StateFlags),
            "active": bool(info.StateFlags & _DISPLAY_DEVICE_ACTIVE),
            "primary": bool(info.StateFlags & _DISPLAY_DEVICE_PRIMARY_DEVICE),
        }
    except Exception:
        return {}


def _enumerate_adapters() -> list[dict[str, Any]]:
    if os.name != "nt":
        return []
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.EnumDisplayDevicesW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(_DISPLAY_DEVICEW),
            wintypes.DWORD,
        ]
        user32.EnumDisplayDevicesW.restype = wintypes.BOOL
        rows: list[dict[str, Any]] = []
        index = 0
        while True:
            info = _DISPLAY_DEVICEW()
            info.cb = ctypes.sizeof(info)
            if not user32.EnumDisplayDevicesW(
                    None, index, ctypes.byref(info), 0):
                break
            flags = int(info.StateFlags)
            rows.append({
                "index": index,
                "device": str(info.DeviceName or ""),
                "name": str(info.DeviceString or ""),
                "device_id": str(info.DeviceID or ""),
                "device_key": str(info.DeviceKey or ""),
                "state_flags": flags,
                "active": bool(flags & _DISPLAY_DEVICE_ACTIVE),
                "primary": bool(flags & _DISPLAY_DEVICE_PRIMARY_DEVICE),
                "mirroring": bool(flags & _DISPLAY_DEVICE_MIRRORING_DRIVER),
            })
            index += 1
        return rows
    except Exception:
        return []


def _is_idd(name: str) -> bool:
    value = str(name or "").lower()
    return any(token in value for token in (
        "iddsampledriver",
        "indirect display",
        "virtual display",
        "virtual monitor",
        "spacedesk",
    ))


def _enrich_monitors(
    monitors: list[dict[str, Any]],
    adapters: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    adapters = adapters or []
    enriched = []
    for row in monitors:
        copy = dict(row)
        device = str(row.get("device") or "")
        adapter = next(
            (item for item in adapters
             if str(item.get("device") or "") == device),
            {},
        )
        monitor_info = _adapter_for_monitor(device)
        copy["adapter"] = adapter
        copy["name"] = adapter.get("name") or monitor_info.get("name") or ""
        copy["monitor_name"] = monitor_info.get("name") or ""
        copy["monitor_device_id"] = monitor_info.get("device_id") or ""
        copy["is_idd"] = _is_idd(copy["name"])
        enriched.append(copy)
    return enriched


def resolve_capture_target(
    monitors: list[dict[str, Any]] | None = None,
    adapters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve the configured capture target without creating a capture device."""
    adapters = adapters if adapters is not None else _enumerate_adapters()
    monitors = monitors if monitors is not None else _enrich_monitors(
        _enumerate_monitors(), adapters)

    output_idx = _int_env("GBT_CAPTURE_OUTPUT_IDX")
    device_idx = _int_env("GBT_CAPTURE_DEVICE_IDX")
    selector = os.environ.get("GBT_CAPTURE_MONITOR", "").strip()
    prefer_idd = _bool_env("GBT_CAPTURE_PREFER_IDD")
    backend = os.environ.get("GBT_CAPTURE_BACKEND", "auto").strip().lower()
    if backend not in {"auto", "dxgi", "winrt", "mss", "pyautogui"}:
        backend = "auto"

    def _monitor_is_idd(row: dict[str, Any]) -> bool:
        if row.get("is_idd"):
            return True
        if _is_idd(str(row.get("name") or "")):
            return True
        adapter = row.get("adapter") or {}
        return _is_idd(str(adapter.get("name") or ""))

    selected = None
    reason = "default_first_output"
    if selector:
        for row in monitors:
            values = {
                str(row.get("index")),
                str(row.get("device") or ""),
                str(row.get("name") or ""),
            }
            if selector in values:
                selected = row
                reason = "explicit_monitor_selector"
                break
    if selected is None and prefer_idd:
        selected = next((row for row in monitors if _monitor_is_idd(row)), None)
        if selected is not None:
            reason = "prefer_idd"
    if selected is None and output_idx is not None:
        selected = next(
            (row for row in monitors if int(row.get("index", -1)) == output_idx),
            None,
        )
        reason = "explicit_output_index" if selected is not None else reason
    if selected is None:
        selected = next(
            (row for row in monitors if row.get("primary")),
            monitors[0] if monitors else None,
        )

    if selected is not None and output_idx is None:
        output_idx = int(selected.get("index", 0))
    if selected is not None and device_idx is None and selected.get("adapter"):
        device_name = str(selected["adapter"].get("device") or "")
        for row in adapters:
            if str(row.get("device") or "") == device_name:
                device_idx = int(row.get("index", 0))
                break
    if device_idx is None:
        device_idx = 0
    if output_idx is None:
        output_idx = 0

    return {
        "backend": backend,
        "prefer_idd": prefer_idd,
        "device_idx": device_idx,
        "output_idx": output_idx,
        "monitor": selected.get("device") if selected else "",
        "monitor_name": selected.get("name") if selected else "",
        "monitor_is_idd": _monitor_is_idd(selected) if selected else False,
        "reason": reason,
    }


def status() -> dict[str, Any]:
    """Return a non-secret, read-only snapshot of the capture boundary."""
    if os.name != "nt":
        return {
            "ok": True,
            "platform": os.name,
            "capture_ready": False,
            "reason": "windows_capture_requires_windows",
            "backends": {
                "dxcam": _module_available("dxcam"),
                "mss": _module_available("mss"),
                "pyautogui": _module_available("pyautogui"),
                "winrt": False,
            },
        }

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        session_id = wintypes.DWORD(0)
        session_ok = bool(kernel32.ProcessIdToSessionId(
            kernel32.GetCurrentProcessId(), ctypes.byref(session_id)))
        remote = bool(user32.GetSystemMetrics(_SM_REMOTESESSION))
    except Exception:
        session_ok = False
        session_id = wintypes.DWORD(0)
        remote = False

    station, desktop = _window_station_names()
    adapters = _enumerate_adapters()
    monitors = _enrich_monitors(_enumerate_monitors(), adapters)
    selected = resolve_capture_target(monitors, adapters)
    interactive = (
        station.lower() == "winsta0"
        and desktop.lower() == "default"
    )
    roots: list[str] = []
    if session_ok and int(session_id.value) == 0:
        roots.append("session_0_isolated")
    if not interactive:
        roots.append("non_interactive_desktop")
    if remote:
        roots.append("remote_desktop")
    if len([a for a in adapters if a.get("active") and not a.get("mirroring")]) > 1:
        roots.append("multi_gpu_or_multi_adapter")
    idd_monitors = [row for row in monitors if row.get("is_idd")]
    idd_adapters = [
        row for row in adapters
        if _is_idd(str(row.get("name") or ""))
    ]
    if idd_monitors:
        roots.append("idd_present")
    elif idd_adapters:
        roots.append("idd_available_inactive")

    actions = []
    if "session_0_isolated" in roots:
        actions.append(
            "Run capture in an interactive desktop session or use a local "
            "capture agent; Session 0 cannot provide desktop duplication."
        )
    if "remote_desktop" in roots:
        actions.append(
            "Try the WinRT backend or a virtual display; DXGI can be rejected "
            "while a remote session is active."
        )
    if "multi_gpu_or_multi_adapter" in roots:
        actions.append(
            "Set GBT_CAPTURE_DEVICE_IDX/GBT_CAPTURE_OUTPUT_IDX or select the "
            "integrated GPU for the capture process."
        )
    if idd_monitors:
        actions.append(
            "An active IDD display is available; set GBT_CAPTURE_MONITOR or "
            "GBT_CAPTURE_PREFER_IDD=1 to target it."
        )
    elif idd_adapters:
        actions.append(
            "An IDD adapter is installed but has no active monitor; enable a "
            "virtual monitor in the interactive Windows session before capture."
        )
    else:
        actions.append(
            "If a virtual display is required, install an IDD in the "
            "interactive Windows session; this module deliberately does not "
            "install drivers."
        )

    return {
        "ok": True,
        "platform": "windows",
        "process_session": int(session_id.value) if session_ok else None,
        "window_station": station,
        "desktop": desktop,
        "interactive_desktop": interactive,
        "remote_session": remote,
        "monitors": monitors,
        "adapters": adapters,
        "selected": selected,
        "idd_present": bool(idd_monitors),
        "idd_available": bool(idd_monitors or idd_adapters),
        "idd_adapters": [
            {
                "index": row.get("index"),
                "device": row.get("device"),
                "name": row.get("name"),
                "active": row.get("active"),
            }
            for row in idd_adapters
        ],
        "capture_ready": bool(interactive and monitors),
        # R-H203 · G3 修：统一失败出口（结构化否决 + reason + next，不许静默失败）
        "ok": bool(interactive and monitors),
        "reason": (None if (interactive and monitors)
                   else (roots[0] if roots else "capture_not_ready")),
        "next": (None if (interactive and monitors)
                 else (actions[0] if actions
                       else "用 vision_cap.analyze(image=路径) 走文件通道，或请主人到交互桌面再跑")),
        "likely_failure_roots": roots,
        "recommended_actions": actions,
        "backends": {
            "dxcam": _module_available("dxcam"),
            "dxcam_winrt": (
                _module_available("dxcam")
                and _module_available("winrt")
            ),
            "mss": _module_available("mss"),
            "pyautogui": _module_available("pyautogui"),
        },
    }


def capacity() -> dict[str, Any]:
    """轻量采集容量（**只查身份**，不枚举适配器/显示器）——抓帧路径的前置门数据源。

    为什么单独一支：`status()` 要枚举显卡与 EDID（几十毫秒级），只适合做体检；
    抓帧是热路径，每次调用都体检会把 1.6ms 的采集拖成几十毫秒。
    判据与 `status()` **同源**（`_window_station_names()` + 同一条 interactive 口径），
    只是不算显示器、不算后端，避免两处真相。

    返回 `reason`：非交互桌面时为 `non_interactive_desktop`，否则 `None`。
    """
    if os.name != "nt":
        return {"interactive_desktop": False, "window_station": "", "desktop": "",
                "reason": "capture_requires_windows", "checked_at": _stamp()}
    station, desktop = _window_station_names()
    interactive = (station.lower() == "winsta0" and desktop.lower() == "default")
    session_id = None
    remote = None
    try:
        _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _sid = wintypes.DWORD(0)
        if _k32.ProcessIdToSessionId(_k32.GetCurrentProcessId(), ctypes.byref(_sid)):
            session_id = int(_sid.value)
        remote = bool(ctypes.WinDLL("user32", use_last_error=True).GetSystemMetrics(_SM_REMOTESESSION))
    except Exception:
        pass
    out = {"interactive_desktop": interactive,
            "window_station": station, "desktop": desktop,
            "process_session": session_id, "remote_session": remote,
            "reason": None if interactive else "non_interactive_desktop",
            "checked_at": _stamp()}
    # R-H203 · G3 修：轻量门也要有统一失败出口（ok + reason + next）
    out["ok"] = bool(interactive)
    out["next"] = (None if interactive
                   else "非交互桌面拿不到画面：改用 vision_cap.analyze(image=路径) 文件通道，"
                        "或请主人在交互桌面会话里重跑")
    # 守卫给的是**判定**：通过就回原 payload，不通过才回否决（别把判定当返回值）
    guard = assert_not_silent(out, where="capacity")
    return out if guard.get("ok") else guard


def _stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


__all__ = ["resolve_capture_target", "status", "capacity"]
