# gbt-capability: subprocess, dynamic-import, ctypes
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""
brain/omni_tentacle.py — 万能触手 · 无护栏 · 直连硬件
======================================================
触手插入显示屏 → 实时画面回传
触手带动鼠标 → 点击任何东西
触手读取一切 → 不受任何限制

零 brain 依赖。纯 pyautogui + win32。直接干。
"""
import sys, os, json, time, base64, io


# ── 病因钩子（吞错统一收口）：记录本身绝不许拖垮触手，缺模块就退回原来的 print
try:
    from nav_etiology import record_swallow as _record_swallow
except Exception:  # noqa: BLE001
    def _record_swallow(_e, _mod="?", _op=""):
        import sys as _s
        print(f"⚠️ {_mod}: 吞错: {_e}", file=_s.stderr)
        return "action_no_effect"
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent


# ═══════════════════════════════════════════
#  硬件直连 — 屏幕/鼠标/键盘
# ═══════════════════════════════════════════

_MSS_SCT = None  # 复用mss实例 (新建95ms → 复用30ms)
_DXCAM = None  # DXGI Desktop Duplication (硬件级采集, 1.6-9.9ms)
_DXCAM_FAIL_TS = 0.0  # ⛔ 2026-08-08: 创建失败冷却(60s后重试, 不永久缓存False)
_DXCAM_BASE = None  # 增量基准帧 (numpy)
_DXCAM_BASE_TIME = 0
_NV_LITE = None      # ⛔ 2026-08-09: native_vision轻量眼缓存 (画布/游戏/自绘UI原生视觉定位兜底)
_NV_LITE_TS = 0.0    # 加载失败重试节流(30s)


# ⛔ 采集身份门（2026-09-18 风哥拍「追踪根源修复」）
# 现象：进程若在非交互桌面（WinSta0 下挂 CodexSandboxDesktop-…），抓屏必然
#       BitBlt 拒绝访问；旧实现每次调用都往 stderr 喷「吞错」，且先白试三个后端。
# 处置：① 前置身份门（数据源单一：capture_environment.capacity()，2s 缓存）；
#       ② 门拦截 → 抛 CaptureUnavailable(reason_code)，不试后端、不喷噪音；
#       ③ 后端全灭 → 同样抛一次带原因码的异常（不吞、不复读）。
class CaptureUnavailable(RuntimeError):
    """采集不可用：带机器可读的原因码（身份门拦截 / 后端全灭）。"""

    def __init__(self, reason_code: str, detail: str = ""):
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)


_CAPTURE_GATE = {"ts": 0.0, "data": None}
_CAPTURE_GATE_TTL = 2.0
_CAPTURE_NOTICE_SEEN = set()


def _capture_identity(ttl: float = _CAPTURE_GATE_TTL) -> dict:
    """采集身份门（缓存 ttl 秒——抓帧是热路径，不许每帧体检）。"""
    now = time.time()
    if _CAPTURE_GATE["data"] is None or (now - _CAPTURE_GATE["ts"]) > ttl:
        try:
            try:
                from . import capture_environment as _ce
            except ImportError:                       # 以脚本方式直跑 omni_core 时
                from gbt_allinone.tentacle import capture_environment as _ce
            _CAPTURE_GATE["data"] = _ce.capacity()
        except Exception as _e:  # noqa: BLE001 —— 门自己坏掉不许拖垮采集
            _CAPTURE_GATE["data"] = {"interactive_desktop": None, "window_station": "",
                                     "desktop": "", "reason": "gate_unavailable",
                                     "detail": f"{type(_e).__name__}: {_e}"[:120]}
        _CAPTURE_GATE["ts"] = now
    return dict(_CAPTURE_GATE["data"])


def _capture_notice(reason_code: str, detail: str) -> None:
    """一个原因码只播一次：不静默（有话说），也不当复读机（每帧一行）。"""
    if reason_code in _CAPTURE_NOTICE_SEEN:
        return
    _CAPTURE_NOTICE_SEEN.add(reason_code)
    print(f"⚠️ omni_core: 采集不可用[{reason_code}] {detail}", file=sys.stderr)


# ── R-H295 · ⑥ G1/G2：本仓**唯一**的「做不了」返回形状 ─────────────────────
# 《触手覆盖矩阵.md》§三：手组 9 模块里只有 4 个能报"做不了"；G2 的定性原话是
# 「部分模块**只抛异常不回结构化否决**」。本文件正是那个典型：
# `_screen_capture` 取不到屏时 `raise CaptureUnavailable(reason_code, detail)` ——
# 原因码是有的，但**抛出去就没人接**：调用方（如 omni_vision.see）拿不到分类，
# 上层要么崩要么把一个没有形状的异常当字符串。
# 所以这里立一个**共享**出口，7 个 mixin 共用一份形状，不各抄一遍：
#   ok=False / unavailable=True / denied=False / rule / action / missing / why
def refusal(rule: str, why: str, missing=None, action: str = "", **extra) -> dict:
    """结构化"做不了"（与门禁的 denied 同族）。**不抛异常。**"""
    out = {
        "ok": False,
        "unavailable": True,
        "denied": False,
        "rule": str(rule or "unavailable"),
        "action": str(action or ""),
        "missing": list(missing or ()),
        "why": str(why or "做不了（原因未报）")[:240],
        "error": str(why)[:240],  # 向后兼容：老调用方读 error
        "note": "万能插做不了时**结构化上报**：缺什么写在 missing 里，不抛裸异常、不返回半截数据。",
    }
    out.update(extra)
    return out


def screen_capture_safe(region: dict = None, fmt: str = "jpeg", quality: int = 80,
                        incremental: bool = True, action: str = "screen_capture") -> dict:
    """`_screen_capture` 的**不抛版本**：失败返回结构化拒绝，成功返回原 cap。

    为什么必须有它：`CaptureUnavailable` 一旦抛出，就绕过了所有 `cap.get("ok")` 检查
    （那些检查只对"返回了失败 dict"有效）—— 眼睛瞎了却以异常形式炸穿调用链。
    """
    try:
        return _screen_capture(region, fmt=fmt, quality=quality, incremental=incremental)
    except CaptureUnavailable as exc:
        return refusal("screen_capture_unavailable", str(exc), ("display", "frame_source"),
                       action, reason_code=str(getattr(exc, "args", [""])[0] or "")[:80])
    except Exception as exc:  # noqa: BLE001
        return refusal("screen_capture_failed",
                       "%s: %s" % (type(exc).__name__, str(exc)[:160]),
                       ("display", "frame_source"), action)


def _attach_input_desktop() -> dict:
    """风哥 2026-09-18 拍板 (b)：**显式开关**才切到输入桌面，默认不越界。

    只有 `GBT_CAPTURE_ATTACH=1` 时才尝试；成功则继续采集，失败保持原行为（报原因码）。
    为什么默认关：`SetThreadDesktop(WinSta0\\Default)` = 从沙箱桌面跨到**用户真实桌面**，
    越过沙箱隔离。能力要拿到，边界仍握在主人手里。
    约束：只影响**当前线程**；必须在创建窗口/钩子之前调用。
    """
    if str(os.environ.get("GBT_CAPTURE_ATTACH", "")).strip() not in ("1", "true", "TRUE", "yes"):
        return {"attached": False, "reason": "attach_disabled"}
    try:
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.WinDLL("user32", use_last_error=True)
        u32.OpenInputDesktop.restype = wintypes.HANDLE
        u32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        u32.SetThreadDesktop.restype = wintypes.BOOL
        h = u32.OpenInputDesktop(0, False, 0x0001 | 0x0100)
        if not h:
            return {"attached": False, "reason": "open_input_desktop_failed"}
        ok = bool(u32.SetThreadDesktop(h))
        return {"attached": ok, "reason": "ok" if ok else "set_thread_desktop_failed"}
    except Exception as exc:  # noqa: BLE001
        return {"attached": False, "reason": f"{type(exc).__name__}: {exc}"[:120]}


def _get_sct():
    """获取复用的 mss 采集实例"""
    global _MSS_SCT
    if _MSS_SCT is None:
        try:
            import warnings as _w
            with _w.catch_warnings():
                _w.simplefilter("ignore", DeprecationWarning)
                import mss
                _MSS_SCT = mss.mss()
        except Exception:
            _MSS_SCT = False
    return _MSS_SCT if _MSS_SCT else None


def _mss_drop():
    """丢掉复用的 mss 实例（DC 失效后必须重建，否则每次 grab 都失败）"""
    global _MSS_SCT
    _old = _MSS_SCT
    _MSS_SCT = None
    try:
        if _old:
            _old.close()
    except Exception:
        pass
    return True


def _get_dxcam():
    """获取 DXGI Desktop Duplication 采集器 (硬件级: 直读显卡帧缓冲)"""
    global _DXCAM, _DXCAM_FAIL_TS
    if _DXCAM is None:
        if time.time() - _DXCAM_FAIL_TS < 60.0:
            return None  # ⛔ 冷却期内不重试(防循环创建)
        try:
            import warnings as _w
            # 防御: 清理 sys.path 中的 cv2 目录条目 (cv2 目录身在 path 会导致 dxcam 内部 import cv2 递归爆炸)
            import sys as _sys_cv
            _clean_cv = [p for p in _sys_cv.path if p.lower().replace(chr(92), "/").rstrip("/").endswith("/cv2")]
            if _clean_cv:
                for _p_cv in _clean_cv:
                    try:
                        _sys_cv.path.remove(_p_cv)
                    except ValueError:
                        pass
            with _w.catch_warnings():
                _w.simplefilter("ignore")
                import dxcam
            _DXCAM = dxcam.create(output_idx=0, output_color='RGB')
            _DXCAM.start(target_fps=144)
        except Exception:
            _DXCAM_FAIL_TS = time.time()  # ⛔ 失败记时间, 60s后自动重试自愈
    return _DXCAM if _DXCAM else None


def _dxcam_frame():
    """DXGI 采集最新帧 (numpy RGB, 1.6-9.9ms)"""
    cam = _get_dxcam()
    if not cam:
        return None
    try:
        return cam.get_latest_frame()
    except Exception:
        return None


def _native_lite_eye():
    """⛔ 2026-08-09 原生视觉眼 — importlib加载native_vision的LiteEyes (零brain依赖, 复用定位缓存)
    画布/游戏/自绘UI UIA读不到的, 视觉模型看图定位; 加载失败缓存False, 30s后重试"""
    global _NV_LITE, _NV_LITE_TS
    if _NV_LITE is False and time.time() - _NV_LITE_TS < 30:
        return None
    try:
        if _NV_LITE is None or _NV_LITE is False:
            import importlib.util as _iu_nv
            _spec_nv = _iu_nv.spec_from_file_location("_nv_eye", str(ROOT / "caps" / "native_vision" / "run.py"))
            _nv_mod = _iu_nv.module_from_spec(_spec_nv)
            _spec_nv.loader.exec_module(_nv_mod)
            _NV_LITE = _nv_mod.LiteEyes()
    except Exception:
        _NV_LITE = False
        _NV_LITE_TS = time.time()
    return _NV_LITE if _NV_LITE else None


def _capture_legs_status(no_frame: bool = True) -> list:
    """逐条报三路采集后端的现状：缺件，还是装上了却没出帧。

    🔴 2026-11-05 为什么把它从 `_screen_capture` 里抽出来：
    ① 报错原来只拼 `_last_err`，而它**只有** mss/pyautogui 抛异常时才写；
       dxcam 返回 None（没装）、mss 直接 None（没装）都不留痕 ⇒ 报出的是
       「三级后端全灭：pyautogui: ModuleNotFoundError」，读起来像只缺 pyautogui，
       实际三路全缺。诊断时被这句话带偏过一轮。
    ② 抽成纯函数之后判据可以在**不真的抓帧**的情况下验它 --
       留在 `_screen_capture` 里验的话，测试必须依赖「本机装没装 mss」，
       换个解释器就假失败（实测：pyembed 里 pyautogui 是装着的，
       只按 dxcam/mss 两条腿，它真能抓到帧，assertRaises 直接失败）。
    """
    legs = []
    for mod, label in (("dxcam", "DXGI 硬采"),
                       ("mss", "BitBlt"),
                       ("pyautogui", "终极兜底")):
        try:
            __import__(mod)
            legs.append("%s(%s) 已装%s"
                        % (label, mod, "但没出帧" if no_frame else ""))
        except Exception as imp_err:  # noqa: BLE001
            legs.append("%s(%s) 缺件:%s" % (label, mod, type(imp_err).__name__))
    return legs


def _screen_capture(region: dict = None, fmt: str = "jpeg", quality: int = 80, incremental: bool = True):
    """屏幕采集 — 秒级传输优化 v2
    基线(PNG): 234ms / 1622KB b64
    优化(mss+JPEG): 79ms / 389KB b64  (3x提速, 4x减负)
    fmt: jpeg(默认,快) | png(兼容,慢)
    """
    _ident = _capture_identity()
    if _ident.get("interactive_desktop") is False and _attach_input_desktop().get("attached"):
        # 显式开关生效：切到输入桌面成功 -> 重新探身份（下一帧不再拦）
        _CAPTURE_GATE.update({"ts": 0.0, "data": None})
        _ident = _capture_identity()
    if _ident.get("interactive_desktop") is False:
        _why = str(_ident.get("reason") or "non_interactive_desktop")
        _detail = ("非交互桌面（window_station=%s, desktop=%s）——GDI/DXGI 都拿不到屏幕；"
                   "采集进程必须落在交互桌面（WinSta0\\Default）"
                   % (_ident.get("window_station") or "?", _ident.get("desktop") or "?"))
        _capture_notice(_why, _detail)
        raise CaptureUnavailable(_why, _detail)
    import io as _io, base64 as _b64
    import numpy as _np
    from PIL import Image as _PILImage
    img = None
    captured_ms = 0.0
    delta = False
    _last_err = ""
    _mss_recovered = False
    t_start = __import__("time").time()

    # 方案1: DXGI 硬件级采集 (1.6-9.9ms, 直读显卡帧缓冲)
    frame = _dxcam_frame()
    if frame is not None:
        captured_ms = (__import__("time").time() - t_start) * 1000
        # 增量模式: 与基准帧对比, 只编码变化区域
        global _DXCAM_BASE, _DXCAM_BASE_TIME
        if incremental and _DXCAM_BASE is not None and (__import__("time").time() - _DXCAM_BASE_TIME) < 5:
            try:
                # 快速差异检测: 步长采样4x4 (面积1/16), uint8对比免int16
                step = 4
                base_s = _DXCAM_BASE[::step, ::step]
                frame_s = frame[::step, ::step]
                diff_s = _np.abs(base_s.astype(_np.int16) - frame_s.astype(_np.int16)).sum(axis=2)
                changed_s = diff_s > 40
                ratio = float(changed_s.mean())
                if ratio < 0.15:  # 变化<15% → 增量
                    ys_s, xs_s = _np.where(changed_s)
                    if len(xs_s):
                        # 采样坐标 → 原图坐标 (外扩1步长防边缘)
                        y0 = max(0, int(ys_s.min()) * step - 4)
                        y1 = min(frame.shape[0], (int(ys_s.max()) + 1) * step + 4)
                        x0 = max(0, int(xs_s.min()) * step - 4)
                        x1 = min(frame.shape[1], (int(xs_s.max()) + 1) * step + 4)
                        if (y1 - y0) * (x1 - x0) < frame.shape[0] * frame.shape[1] * 0.4 \
                                and (y1 - y0) >= 64 and (x1 - x0) >= 64:
                            img = _PILImage.fromarray(frame[y0:y1, x0:x1])
                            delta = True
                            region_out = {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
            except Exception as _e:
                _record_swallow(_e, "omni_core")
        if img is None:
            img = _PILImage.fromarray(frame)
        _DXCAM_BASE = frame
        _DXCAM_BASE_TIME = __import__("time").time()

    # 方案2: mss 兜底 (BitBlt)
    # 2026-11-06：复用的 mss 实例会随锁屏 / 换显示器 / DPI 变化而**DC 失效** ——
    # 之后每次 grab 都 "BitBlt failed"，而且永远好不了（实测：长驻服务从 03:42 起
    # 每次「看屏幕」都报 screen_grab_unavailable；同一时刻新进程同一路径 200ms
    # 抓帧成功）。所以第一次失败就丢掉缓存实例、重建再试一次，成功则标 mss_recovered。
    if img is None:
        for _attempt in (0, 1):
            try:
                sct = _get_sct()
                if sct is None:
                    break
                mon = sct.monitors[1]
                if region:
                    shot = sct.grab({"left": mon["left"] + region["x"], "top": mon["top"] + region["y"],
                                     "width": region["w"], "height": region["h"]})
                else:
                    shot = sct.grab(mon)
                img = _PILImage.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                captured_ms = (__import__("time").time() - t_start) * 1000
                if _attempt:
                    _mss_recovered = True
                    _last_err = ""
                break
            except Exception as _e:
                if _attempt == 0:
                    _last_err = "mss(重建前): %s: %s" % (type(_e).__name__, str(_e)[:120])
                    _mss_drop()
                    continue
                _last_err = ((_last_err + " | ") if _last_err else "") + \
                    "mss: %s: %s" % (type(_e).__name__, str(_e)[:140])
    # 方案3: pyautogui 终极兜底
    if img is None:
        try:
            import pyautogui
            if region:
                img = pyautogui.screenshot(region=(region["x"], region["y"], region["w"], region["h"]))
            else:
                img = pyautogui.screenshot()
            captured_ms = (__import__("time").time() - t_start) * 1000
        except Exception as _e:
            _last_err = ((_last_err + " | ") if _last_err else "") + \
                f"pyautogui: {type(_e).__name__}: {_e}"[:160]
    if img is None:
        # 🔴 2026-11-05：这里原来只拼 `_last_err`，而它**只有** mss 抓取抛异常和
        #    pyautogui 抛异常时才会写。最常见的情形是 dxcam 返回 None（没装）和
        #    mss 直接 None（没装）—— 这两条都不留痕，于是报出的是
        #    「三级后端全灭：pyautogui: ModuleNotFoundError」，
        #    读起来像"只缺 pyautogui"，实际三路全缺。诊断被带偏过一轮。
        # 现在逐腿探明（_capture_legs_status，抽出去是为了能单独验），
        # 再附上采集期报错 —— 两者不同：一个是"没装"，一个是"装了但抓的时候炸"。
        _detail = "三路采集后端都没有可用帧【%s】" % "；".join(_capture_legs_status())
        if _last_err:
            _detail += " | 采集期报错：%s" % _last_err
        _capture_notice("screen_grab_unavailable", _detail)
        raise CaptureUnavailable("screen_grab_unavailable", _detail)

    buf = _io.BytesIO()
    if fmt == "jpeg":
        img.save(buf, "JPEG", quality=quality)
        fmt_out = "jpeg"
    else:
        img.save(buf, "PNG")
        fmt_out = "png"
    data = buf.getvalue()
    if _mss_recovered:
        _last_err = ""
    result = {"ok": True, "size": list(img.size), "fmt": fmt_out,
              "image_base64": _b64.b64encode(data).decode(),
              "image_kb": len(data) // 1024,
              "capture_ms": round(captured_ms, 1),
              "engine": "dxcam" if _DXCAM is not None else ("mss" if _MSS_SCT is not None else "pyautogui"),
              "delta": delta}
    if _mss_recovered:
        result["mss_recovered"] = True
    if delta:
        result["delta_region"] = region_out
    return result

def _mouse_move(x, y):
    import pyautogui; pyautogui.moveTo(x, y)

def _mouse_click(x=None, y=None, button="left"):
    import pyautogui
    if x is not None: pyautogui.click(x, y, button=button)
    else: pyautogui.click(button=button)

def _mouse_double_click(x=None, y=None):
    import pyautogui
    if x is not None: pyautogui.doubleClick(x, y)
    else: pyautogui.doubleClick()

def _mouse_scroll(amount=-3):
    import pyautogui; pyautogui.scroll(amount)

def _keyboard_type(text):
    import pyautogui; pyautogui.write(text, interval=0.03)

def _keyboard_press(key):
    import pyautogui; pyautogui.press(key)

def _keyboard_hotkey(*keys):
    import pyautogui; pyautogui.hotkey(*keys)

def _mouse_position():
    import pyautogui; pos = pyautogui.position(); return {"x": pos.x, "y": pos.y}

def _screen_size():
    import pyautogui; size = pyautogui.size(); return {"width": size.width, "height": size.height}

# ═══════════════════════════════════════════════════════════════════
#  win32 窗口后端 — ctypes 实现（零 pywin32 依赖）
#  pyembed 是 embeddable 包且不带 pip/pywin32；旧实现 `import win32gui` 的
#  ImportError 被吞成 `return None/[]`，上层再误读成 window_not_found ——
#  这就是「触手遮挡点击」被挡住的真因。这里用 user32/kernel32 的 ctypes 直连：
#  枚举窗口 / 按标题子串 + 进程名 + class 找窗 / 激活 / PostMessage 后台点击。
#  后端真不可用（非 Windows / 直连失败）时**抛 WindowBackendUnavailable**，
#  绝不静默返回 None 冒充「找不到窗口」。
# ═══════════════════════════════════════════════════════════════════

class WindowBackendUnavailable(RuntimeError):
    """win32 窗口后端不可用（非缺窗口，是缺直连能力）。"""


_WIN32 = None
_WIN32_ERR = None

# Win32 消息常量（后台点击用）
_WM_MOUSEMOVE = 0x0200
_WM_LBUTTONDOWN = 0x0201
_WM_LBUTTONUP = 0x0202
_WM_RBUTTONDOWN = 0x0204
_WM_RBUTTONUP = 0x0205
_MK_LBUTTON = 0x0001
_MK_RBUTTON = 0x0002


def _win32():
    """惰性初始化 ctypes win32 后端；成功返回 dict，失败返回 None 并在 _WIN32_ERR 留因。"""
    global _WIN32, _WIN32_ERR
    if _WIN32 is not None or _WIN32_ERR is not None:
        return _WIN32
    try:
        import ctypes
        from ctypes import wintypes as _w
        # DPI 感知（关键）：pyembed 进程默认 DPI-unaware，本机 150% 缩放下
        # GetWindowRect/ScreenToClient 返回被压缩的逻辑坐标（物理 1920x1200 → 逻辑 1280x800），
        # 而 WinUI/Notepad 按物理像素解 WM_LBUTTONDOWN 的 lParam —— 不设感知会 1.5x 打偏。
        try:
            _dpi = ctypes.WinDLL("user32", use_last_error=True)
            _aw = getattr(_dpi, "SetProcessDpiAwarenessContext", None)
            if _aw is not None:
                _aw.argtypes = [ctypes.c_void_p]
                _aw.restype = ctypes.c_bool
                _aw(ctypes.c_void_p(-4))  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            else:
                _dpi.SetProcessDPIAware()
        except Exception:
            pass
        u32 = ctypes.WinDLL("user32", use_last_error=True)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        WNDENUMPROC = ctypes.WINFUNCTYPE(_w.BOOL, _w.HWND, _w.LPARAM)

        u32.EnumWindows.argtypes = [WNDENUMPROC, _w.LPARAM]
        u32.EnumWindows.restype = _w.BOOL
        u32.IsWindowVisible.argtypes = [_w.HWND]
        u32.IsWindowVisible.restype = _w.BOOL
        u32.GetWindowTextLengthW.argtypes = [_w.HWND]
        u32.GetWindowTextLengthW.restype = ctypes.c_int
        u32.GetWindowTextW.argtypes = [_w.HWND, _w.LPWSTR, ctypes.c_int]
        u32.GetWindowTextW.restype = ctypes.c_int
        u32.GetClassNameW.argtypes = [_w.HWND, _w.LPWSTR, ctypes.c_int]
        u32.GetClassNameW.restype = ctypes.c_int
        u32.GetWindowRect.argtypes = [_w.HWND, ctypes.POINTER(_w.RECT)]
        u32.GetWindowRect.restype = _w.BOOL
        u32.GetClientRect.argtypes = [_w.HWND, ctypes.POINTER(_w.RECT)]
        u32.GetClientRect.restype = _w.BOOL
        u32.WindowFromPoint.argtypes = [_w.POINT]
        u32.WindowFromPoint.restype = _w.HWND
        u32.GetForegroundWindow.argtypes = []
        u32.GetForegroundWindow.restype = _w.HWND
        u32.GetWindowThreadProcessId.argtypes = [_w.HWND, ctypes.POINTER(_w.DWORD)]
        u32.GetWindowThreadProcessId.restype = _w.DWORD
        u32.ShowWindow.argtypes = [_w.HWND, ctypes.c_int]
        u32.ShowWindow.restype = _w.BOOL
        u32.SetForegroundWindow.argtypes = [_w.HWND]
        u32.SetForegroundWindow.restype = _w.BOOL
        u32.BringWindowToTop.argtypes = [_w.HWND]
        u32.BringWindowToTop.restype = _w.BOOL
        u32.PostMessageW.argtypes = [_w.HWND, ctypes.c_uint, _w.WPARAM, _w.LPARAM]
        u32.PostMessageW.restype = _w.BOOL
        u32.SendMessageW.argtypes = [_w.HWND, ctypes.c_uint, _w.WPARAM, _w.LPARAM]
        u32.SendMessageW.restype = ctypes.c_ssize_t
        u32.ScreenToClient.argtypes = [_w.HWND, ctypes.POINTER(_w.POINT)]
        u32.ScreenToClient.restype = _w.BOOL
        u32.ClientToScreen.argtypes = [_w.HWND, ctypes.POINTER(_w.POINT)]
        u32.ClientToScreen.restype = _w.BOOL
        u32.ChildWindowFromPointEx.argtypes = [_w.HWND, _w.POINT, ctypes.c_uint]
        u32.ChildWindowFromPointEx.restype = _w.HWND
        u32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_uint, ctypes.c_void_p]
        u32.keybd_event.restype = None
        u32.GetSystemMetrics.argtypes = [ctypes.c_int]
        u32.GetSystemMetrics.restype = ctypes.c_int

        k32.GetCurrentThreadId.argtypes = []
        k32.GetCurrentThreadId.restype = _w.DWORD
        k32.OpenProcess.argtypes = [_w.DWORD, _w.BOOL, _w.DWORD]
        k32.OpenProcess.restype = _w.HANDLE
        k32.QueryFullProcessImageNameW.argtypes = [_w.HANDLE, _w.DWORD, _w.LPWSTR, ctypes.POINTER(_w.DWORD)]
        k32.QueryFullProcessImageNameW.restype = _w.BOOL
        k32.CloseHandle.argtypes = [_w.HANDLE]
        k32.CloseHandle.restype = _w.BOOL

        _WIN32 = {"u32": u32, "k32": k32, "ctypes": ctypes, "w": _w, "WNDENUMPROC": WNDENUMPROC}
    except Exception as _e:  # noqa: BLE001
        _WIN32_ERR = "%s: %s" % (type(_e).__name__, str(_e)[:160])
        _WIN32 = None
    return _WIN32


def _win32_backend_status() -> dict:
    """窗口后端可用性三态（不吞错）：ok / needs_dependency（带真实异常原文）。"""
    b = _win32()
    if b is not None:
        return {"ok": True, "backend": "ctypes"}
    return {"ok": False, "needs_dependency": True, "backend": "ctypes",
            "why": "win32 ctypes 后端不可用: %s" % (_WIN32_ERR or "未知原因")}


def _require_win32():
    """取后端；不可用就抛 WindowBackendUnavailable（带真实异常），绝不返回 None 冒充找不到。"""
    b = _win32()
    if b is None:
        raise WindowBackendUnavailable(
            "win32 ctypes 后端不可用: %s" % (_WIN32_ERR or "未知原因"))
    return b


def _ct_window_text(hwnd):
    b = _win32()
    if not b:
        return ""
    ln = b["u32"].GetWindowTextLengthW(hwnd)
    if ln <= 0:
        return ""
    buf = b["ctypes"].create_unicode_buffer(ln + 1)
    b["u32"].GetWindowTextW(hwnd, buf, ln + 1)
    return buf.value or ""


def _ct_window_class(hwnd):
    b = _win32()
    if not b:
        return ""
    buf = b["ctypes"].create_unicode_buffer(256)
    b["u32"].GetClassNameW(hwnd, buf, 256)
    return buf.value or ""


def _ct_window_rect(hwnd):
    b = _win32()
    if not b:
        return None
    r = b["w"].RECT()
    if not b["u32"].GetWindowRect(hwnd, b["ctypes"].byref(r)):
        return None
    return {"left": int(r.left), "top": int(r.top), "right": int(r.right), "bottom": int(r.bottom)}


def _ct_window_from_point(x, y):
    """屏幕坐标 → 窗口句柄（按屏幕 Z 序，取该点最上层窗口；含子窗口，失败返回 0）。

    与 _background_click 里的 ChildWindowFromPointEx 不同：这里就是要「谁在最上面」，
    对应旧 pywin32 的 win32gui.WindowFromPoint((x, y))。后端不可用返回 0（不抛）。
    """
    b = _win32()
    if not b:
        return 0
    try:
        hwnd = b["u32"].WindowFromPoint(b["w"].POINT(int(x), int(y)))
        return int(hwnd or 0)
    except Exception:
        return 0


def _ct_window_pid(hwnd):
    b = _win32()
    if not b:
        return None
    pid = b["w"].DWORD()
    b["u32"].GetWindowThreadProcessId(hwnd, b["ctypes"].byref(pid))
    return int(pid.value)


def _ct_window_thread(hwnd):
    b = _win32()
    if not b or not hwnd:
        return 0
    pid = b["w"].DWORD()
    return int(b["u32"].GetWindowThreadProcessId(int(hwnd), b["ctypes"].byref(pid)))


def _ct_process_name(pid):
    """由 PID 取进程名（如 notepad.exe）；失败返回空串，不抛。"""
    b = _win32()
    if not b or not pid:
        return ""
    c = b["ctypes"]
    w = b["w"]
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    try:
        h = b["k32"].OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return ""
        try:
            size = w.DWORD(1024)
            buf = c.create_unicode_buffer(1024)
            if b["k32"].QueryFullProcessImageNameW(h, 0, buf, c.byref(size)):
                return os.path.basename(buf.value)
        finally:
            b["k32"].CloseHandle(h)
    except Exception:
        pass
    return ""


def _window_snapshot(hwnd):
    """由 hwnd 构造统一窗口描述 dict（字段与旧 win32gui 版对齐，另补 class/process）。"""
    title = _ct_window_text(hwnd)
    rect = _ct_window_rect(hwnd) or {"left": 0, "top": 0, "right": 0, "bottom": 0}
    pid = _ct_window_pid(hwnd)
    cls = _ct_window_class(hwnd)
    snap = {
        "title": (title or "")[:100],
        "pid": pid,
        "hwnd": int(hwnd or 0),
        "class": cls,
        "rect": rect,
        "size": "%dx%d" % (rect["right"] - rect["left"], rect["bottom"] - rect["top"]),
        "pos": "(%d,%d)" % (rect["left"], rect["top"]),
    }
    pname = _ct_process_name(pid) if pid else ""
    if pname:
        snap["process"] = pname
    return snap


def _enum_windows(max_count=50):
    b = _require_win32()
    windows = []
    def _cb(hwnd, _lparam):
        if len(windows) >= max_count:
            return True
        try:
            if not b["u32"].IsWindowVisible(hwnd):
                return True
            title = _ct_window_text(hwnd)
            if not title or not title.strip():
                return True
            snap = _window_snapshot(hwnd)
            if snap["rect"]["right"] - snap["rect"]["left"] <= 0:
                return True
            windows.append(snap)
        except Exception:
            pass
        return True
    b["u32"].EnumWindows(b["WNDENUMPROC"](_cb), 0)
    return windows

# 中文应用名 → 窗口标题关键词映射 (中文匹配不到时用英文)
_WINDOW_TITLE_MAP = {
    "记事本": "notepad",
    "浏览器": "chrome",
    "资源管理器": "explorer",
    "文件管理器": "explorer",
    "计算器": "calculator",
    "画图": "mspaint",
    "终端": "terminal",
    "命令提示符": "cmd",
    "控制台": "console",
}


def window_title_matches(target, title):
    """窗口标题模糊匹配 — 双向子串 OR token级AND
    例: target="Chrome - doubao.com" 匹配真实Chrome标题 "豆包 - doubao.com - Google Chrome"
    (模型常按"浏览器 - 域名"旧格式猜测窗口名, 实际标题为"页面名 - 域名 - 浏览器名")
    """
    t = str(target or "").lower().strip()
    n = str(title or "").lower().strip()
    if not t or not n:
        return False
    if t in n or n in t:
        return True
    try:
        import re as _wm_re
    except Exception:
        return False
    _sep = r"[\s\-_.:：,，/\\()\[\]{}]+"
    t_toks = [x for x in _wm_re.split(_sep, t) if len(x) >= 2]
    if not t_toks:
        return False
    n_toks = {x for x in _wm_re.split(_sep, n) if len(x) >= 2}
    if not n_toks:
        return False
    _noise = {"google", "microsoft", "windows", "www", "浏览器"}
    t_toks = [x for x in t_toks if x not in _noise]
    if not t_toks:
        return False
    return all(any(tok in nt or nt in tok for nt in n_toks) for tok in t_toks)

def _find_window(target):
    """按名字找窗口：标题子串（双向/token）→ class → 进程名 匹配，任一命中即返回。

    后端不可用时抛 WindowBackendUnavailable（**不吞成 None**）；真找不到才返回 None。
    """
    b = _require_win32()
    t = str(target or "").strip()
    if not t:
        return None
    tl = t.lower()
    # 中文→英文映射: 同时尝试原始关键词和映射关键词
    candidates = [tl]
    for cn, en in _WINDOW_TITLE_MAP.items():
        if cn in t:
            candidates.append(en)
            candidates.append(f"{cn} - {en.capitalize()}")
    hit = {"snap": None}
    def _cb(hwnd, _lparam):
        if hit["snap"]:
            return True
        try:
            if not b["u32"].IsWindowVisible(hwnd):
                return True
            title = _ct_window_text(hwnd)
            tlow = title.lower()
            # ① 标题子串 / token 级 AND
            if window_title_matches(t, title) or any(c in tlow for c in candidates if c):
                hit["snap"] = _window_snapshot(hwnd)
                return True
            # ② class 匹配（如 "Notepad" / "Chrome_WidgetWin_1"）
            cls = _ct_window_class(hwnd)
            if cls:
                cl = cls.lower()
                if tl in cl or cl in tl:
                    hit["snap"] = _window_snapshot(hwnd)
                    return True
            # ③ 进程名匹配（target 可为 "notepad.exe" / "notepad"）
            pid = _ct_window_pid(hwnd)
            if pid:
                pname = _ct_process_name(pid).lower()
                if pname:
                    pbase = pname.rsplit(".", 1)[0]
                    if tl in (pname, pbase) or tl in pname or pname in tl:
                        hit["snap"] = _window_snapshot(hwnd)
                        return True
        except Exception as _e:
            _record_swallow(_e, "omni_core")
        return True
    b["u32"].EnumWindows(b["WNDENUMPROC"](_cb), 0)
    return hit["snap"]

def _get_active_window():
    b = _require_win32()
    hwnd = b["u32"].GetForegroundWindow()
    if not hwnd:
        return None
    return _window_snapshot(hwnd)

def _focus_window(hwnd):
    """激活窗口 — ctypes 版：ShowWindow(SW_RESTORE) + SetForegroundWindow + ALT 脉冲绕过前台锁。"""
    b = _require_win32()
    u32 = b["u32"]
    SW_RESTORE = 9
    hwnd = int(hwnd or 0)
    try:
        u32.ShowWindow(hwnd, SW_RESTORE)
        try:
            cur = b["k32"].GetCurrentThreadId()
            fg = u32.GetForegroundWindow()
            fg_tid = _ct_window_thread(fg) if fg else 0
            if fg_tid and fg_tid != cur:
                u32.keybd_event(0x12, 0, 0, 0)
                u32.keybd_event(0x12, 0, 2, 0)
            u32.SetForegroundWindow(hwnd)
        except Exception as _e:
            _record_swallow(_e, "omni_core")
        try:
            u32.BringWindowToTop(hwnd)
        except Exception as _e:
            _record_swallow(_e, "omni_core")
        if u32.GetForegroundWindow() != hwnd:
            try:
                u32.keybd_event(0x12, 0, 0, 0)
                u32.keybd_event(0x12, 0, 2, 0)
                u32.SetForegroundWindow(hwnd)
            except Exception as _e:
                _record_swallow(_e, "omni_core")
        return bool(u32.GetForegroundWindow() == hwnd)
    except Exception:
        return False


def _ct_integrity():
    """当前进程完整性级别（诊断 UIPI 用，报 Low/Medium/High，不回显敏感信息）。"""
    try:
        import ctypes
        from ctypes import wintypes as _wi
        a32 = ctypes.WinDLL("advapi32", use_last_error=True)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        a32.OpenProcessToken.argtypes = [_wi.HANDLE, _wi.DWORD, ctypes.POINTER(_wi.HANDLE)]
        a32.OpenProcessToken.restype = _wi.BOOL
        a32.GetTokenInformation.argtypes = [_wi.HANDLE, ctypes.c_int, ctypes.c_void_p, _wi.DWORD, ctypes.POINTER(_wi.DWORD)]
        a32.GetTokenInformation.restype = _wi.BOOL
        k32.GetCurrentProcess.argtypes = []
        k32.GetCurrentProcess.restype = _wi.HANDLE
        k32.CloseHandle.argtypes = [_wi.HANDLE]
        k32.CloseHandle.restype = _wi.BOOL
        t = _wi.HANDLE()
        if not a32.OpenProcessToken(k32.GetCurrentProcess(), 0x0008, ctypes.byref(t)):
            return "tokenerr"
        try:
            n = _wi.DWORD()
            a32.GetTokenInformation(t, 25, None, 0, ctypes.byref(n))  # TokenIntegrityLevel
            buf = ctypes.create_string_buffer(n.value or 64)
            a32.GetTokenInformation(t, 25, buf, n.value or 64, ctypes.byref(n))
            sid_ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
            sub = ctypes.cast(sid_ptr, ctypes.POINTER(ctypes.c_ubyte))[1]
            rid = ctypes.cast(sid_ptr, ctypes.POINTER(ctypes.c_uint32))[(8 + (sub - 1) * 4) // 4]
            names = {0x0000: "Untrusted", 0x1000: "Low", 0x2000: "Medium",
                     0x2100: "Medium+", 0x3000: "High", 0x4000: "System", 0x5000: "Protected"}
            return names.get(rid, "0x%04x" % rid)
        finally:
            k32.CloseHandle(t)
    except Exception:
        return "?"


def _background_click(hwnd, x, y, button="left", mode="post"):
    """后台点击 — PostMessage/SendMessage 发鼠标消息，不移动真实鼠标、不抢焦点。

    (x, y) 是**窗口左上角相对坐标**（含标题栏，与旧 click_window_occluded 的
    x_offset/y_offset 语义一致）。内部换算：
      屏幕点   = window rect 左上 + (x, y)
      客户区点 = ScreenToClient(target, 屏幕点)
      子控件   = ChildWindowFromPointEx(target, 客户区点)
                 —— 只在本窗口内命中测试、不看 Z 序，正是「被遮挡仍能点中」的关键
                    （这里**不能用** WindowFromPoint，它按屏幕 Z 序会返回遮挡物）。
    然后把 WM_LBUTTONDOWN/UP（左键）或 WM_RBUTTONDOWN/UP（右键）发到子控件或本窗。

    mode: "post" 用 PostMessage（异步入队，默认，最不侵入）；"send" 用 SendMessage（同步）。
    """
    b = _require_win32()
    u32 = b["u32"]
    hwnd = int(hwnd or 0)
    rect = _ct_window_rect(hwnd) or {"left": 0, "top": 0}
    sx = rect["left"] + int(x)
    sy = rect["top"] + int(y)
    # 屏幕点 → 本窗口客户区坐标（纯坐标换算，与遮挡无关）
    pt = b["w"].POINT(sx, sy)
    u32.ScreenToClient(hwnd, b["ctypes"].byref(pt))
    cx, cy = int(pt.x), int(pt.y)
    # 命中本窗口内的子控件（跳过不可见/禁用，不随 Z 序跑偏）
    CWP_SKIPINVISIBLE = 0x0001
    CWP_SKIPDISABLED = 0x0002
    target_hwnd = hwnd
    try:
        child = u32.ChildWindowFromPointEx(hwnd, b["w"].POINT(cx, cy),
                                           CWP_SKIPINVISIBLE | CWP_SKIPDISABLED)
        if child and int(child) not in (0, hwnd):
            target_hwnd = int(child)
            pt2 = b["w"].POINT(sx, sy)
            if u32.ScreenToClient(target_hwnd, b["ctypes"].byref(pt2)):
                cx, cy = int(pt2.x), int(pt2.y)
    except Exception as _e:
        _record_swallow(_e, "omni_core")
    if button == "right":
        down, up, wdown, wup = _WM_RBUTTONDOWN, _WM_RBUTTONUP, _MK_RBUTTON, 0
    else:
        down, up, wdown, wup = _WM_LBUTTONDOWN, _WM_LBUTTONUP, _MK_LBUTTON, 0
    lp = ((cy & 0xFFFF) << 16) | (cx & 0xFFFF)
    sender = u32.SendMessageW if mode == "send" else u32.PostMessageW
    ctypes_mod = b["ctypes"]
    def _send(msg, wp):
        ctypes_mod.set_last_error(0)
        ok = bool(sender(target_hwnd, msg, wp, lp))
        return ok, ctypes_mod.get_last_error()
    r_move, e_move = _send(_WM_MOUSEMOVE, 0)
    r_down, e_down = _send(down, wdown)
    r_up, e_up = _send(up, wup)
    return {"ok": bool(r_down and r_up), "hwnd": target_hwnd, "top_hwnd": hwnd,
            "screen": (sx, sy), "client": (cx, cy), "mode": mode,
            "integrity": _ct_integrity(),
            "messages": {"mousemove": r_move, "down": r_down, "up": r_up},
            "last_errors": {"mousemove": e_move, "down": e_down, "up": e_up}}


def _uia_element_at_window_point(hwnd, sx, sy):
    """在指定窗口内做命中测试 — 不随屏幕 Z 序跑偏（窗口被遮挡也点得中）。

    模块级 ControlFromPoint 走 ElementFromPoint（屏幕 Z 序），被遮挡时返回的是
    遮挡物；这里改用 ControlFromHandle（按句柄，与遮挡无关）拿到窗口元素，再递归找
    BoundingRectangle 包含 (sx, sy) 的**最深**后代（面积最小者）。
    返回 Control 或 None（UIA 不可用 / 查不到时，不抛、不吞成别的错）。
    """
    try:
        import uiautomation as _uia
    except Exception:
        return None
    try:
        with _uia.UIAutomationInitializerInThread():
            win_ctl = _uia.ControlFromHandle(int(hwnd))
            if win_ctl is None:
                return None
            best = [None, None]  # [control, area]

            def _hit(c, d=0):
                if d > 18 or c is None:
                    return
                try:
                    r = c.BoundingRectangle
                except Exception:
                    r = None
                if r is not None:
                    try:
                        if r.left <= sx <= r.right and r.top <= sy <= r.bottom:
                            area = (r.right - r.left) * (r.bottom - r.top)
                            if best[1] is None or area < best[1]:
                                best[0] = c
                                best[1] = area
                    except Exception:
                        pass
                try:
                    children = c.GetChildren()
                except Exception:
                    children = []
                for ch in children:
                    _hit(ch, d + 1)

            _hit(win_ctl)
            return best[0]
    except Exception as _e:
        _record_swallow(_e, "omni_core")
        return None


def _occluded_state_signature(hwnd, sx, sy):
    """点击"是否真生效"的可观测状态签名 — **不依赖 PostMessage 返回值**。

    记两样：① 窗口标题（tab 切换 / 对话框变化会改标题）；② 点击点处控件的选择状态
    （若支持 SelectionItemPattern，记 IsSelected + 名字）。UIA 查不到时退化为仅标题
    签名（best-effort，不报错）。用于点击前后对比判断 PostMessage 是否真把点击送到。
    """
    sig = {"title": _ct_window_text(hwnd)}
    ctl = _uia_element_at_window_point(hwnd, sx, sy)
    if ctl is not None:
        try:
            sig["control"] = (ctl.Name or "")[:80]
            sig["control_type"] = ctl.ControlTypeName or ""
        except Exception:
            pass
        node = ctl
        for _ in range(5):
            if node is None:
                break
            try:
                pat = node.GetSelectionItemPattern()
                if pat is not None:
                    try:
                        sig["selection_item"] = {
                            "name": (node.Name or "")[:80],
                            "is_selected": bool(pat.IsSelected),
                        }
                    except Exception:
                        pass
                    break
            except Exception:
                pass
            try:
                node = node.GetParentControl()
            except Exception:
                break
    return sig


def _occluded_state_changed(before, after):
    """比较两份状态签名：标题变了 或 选择状态变了 → True。"""
    if (before.get("title") or "") != (after.get("title") or ""):
        return True
    b = before.get("selection_item")
    a = after.get("selection_item")
    if b is not None and a is not None:
        if b.get("is_selected") != a.get("is_selected"):
            return True
    return False


def _uia_occluded_click(hwnd, sx, sy):
    """UIA 兜底点击 — 命中窗口内点击点处的控件，按序试三模式，逐条记尝试。

    顺序：SelectionItemPattern.Select() → InvokePattern.Invoke()
          → LegacyIAccessiblePattern.DoDefaultAction()
    每个模式在点击点元素及其祖先链（≤6 层）上找支持者；找到就调用一次，成功即返。
    返回 {"mode", "attempts", "side_effects"}；**不在此处下"是否生效"结论**，
    由调用方用 _occluded_state_signature 复核（UIA 返回值同样不作数）。
    """
    attempts = []
    side_effects = ["brings_window_to_front"]  # UIA 触发会把窗口带到前台（实测）
    out = {"mode": "none", "attempts": attempts, "side_effects": side_effects}
    ctl = _uia_element_at_window_point(hwnd, sx, sy)
    if ctl is None:
        attempts.append({"pattern": "control_not_found",
                         "point": [int(sx), int(sy)]})
        return out
    patterns = (
        ("selection_item", "GetSelectionItemPattern", "Select", "post+uia_select"),
        ("invoke", "GetInvokePattern", "Invoke", "post+uia_invoke"),
        ("legacy", "GetLegacyIAccessiblePattern", "DoDefaultAction", "post+uia_legacy"),
    )
    for pname, getter, invoker, mode in patterns:
        probe = ctl
        supported = False
        for _depth in range(6):
            if probe is None:
                break
            cname = ""
            try:
                cname = (probe.Name or "")[:60]
            except Exception:
                pass
            try:
                pat = getattr(probe, getter)()
            except Exception as _e:
                attempts.append({"pattern": pname, "control": cname,
                                 "error": "%s: %s" % (type(_e).__name__, str(_e)[:100])})
                break
            if pat is not None:
                supported = True
                try:
                    ok = bool(getattr(pat, invoker)())
                    attempts.append({"pattern": pname, "control": cname,
                                     "called": True, "succeeded": ok})
                except Exception as _e:
                    attempts.append({"pattern": pname, "control": cname,
                                     "called": False,
                                     "error": "%s: %s" % (type(_e).__name__, str(_e)[:100])})
                    break
                if ok:
                    out["mode"] = mode
                    return out
                break
            try:
                probe = probe.GetParentControl()
            except Exception:
                break
        if not supported:
            attempts.append({"pattern": pname, "available": False})
    return out


def _uia_set_value_by_window(window_title, text):
    """UIA ValuePattern 直写 — 目标窗口内首个可编辑控件(Edit/Document) SetValue
    ⛔ 2026-08-13 打磨: 不依赖焦点/前台, 穿透完整性边界(UIA 跨同用户窗口无障碍)。
    前台被高完整性窗口锁定时物理输入无法落地(Medium→High UIPI), 此路径兜底。
    → {"ctrl", "method": "uia_setvalue"} | None
    """
    try:
        import uiautomation as _uia
        with _uia.UIAutomationInitializerInThread():
            root = _uia.GetRootControl()
            for w in root.GetChildren():
                try:
                    n = w.Name or ""
                    if window_title.lower() in n.lower() and "运行窗口" not in n:
                        _budget = [120]
                        def _walk(h, d=0):
                            if d > 6 or _budget[0] <= 0:
                                return None
                            try:
                                for c in h.GetChildren():
                                    if _budget[0] <= 0:
                                        return None
                                    _budget[0] -= 1
                                    ct = c.ControlTypeName.replace("Control", "")
                                    if ct in ("Edit", "Document"):
                                        try:
                                            vp = c.GetValuePattern()
                                            if vp is not None:
                                                vp.SetValue(text)
                                                return {"ctrl": (c.Name or "")[:50],
                                                        "method": "uia_setvalue"}
                                        except Exception as _e:
                                            _record_swallow(_e, "omni_core")
                                    rr = _walk(c, d + 1)
                                    if rr:
                                        return rr
                            except Exception as _e:
                                _record_swallow(_e, "omni_core")
                            return None
                        rr = _walk(w)
                        if rr:
                            return rr
                except Exception:
                    continue
    except Exception as _e:
        _record_swallow(_e, "omni_core")
    return None


def _uia_set_value_by_label(label, text):
    """UIA 标签定位直写 — 找到含 label 的控件所在窗口, 向窗口内首个可编辑控件(Edit/Document) SetValue
    ⛔ 2026-08-13 打磨: type_to_field UIA 兜底, 不依赖焦点/前台。
    两遍遍历: ① 窗口子树存在含 label 控件 → ② SetValue 该窗口首个可编辑控件。
    → {"ctrl", "window", "method": "uia_setvalue"} | None
    """
    try:
        import uiautomation as _uia
        with _uia.UIAutomationInitializerInThread():
            root = _uia.GetRootControl()
            for w in root.GetChildren():
                try:
                    n = w.Name or ""
                    if not n.strip() or "运行窗口" in n:
                        continue
                    _budget = [180]
                    def _has_label(h, d=0):
                        if d > 6 or _budget[0] <= 0:
                            return False
                        try:
                            for c in h.GetChildren():
                                if _budget[0] <= 0:
                                    return False
                                _budget[0] -= 1
                                cn = c.Name or ""
                                if label.lower() in cn.lower():
                                    return True
                                if _has_label(c, d + 1):
                                    return True
                        except Exception as _e:
                            _record_swallow(_e, "omni_core")
                        return False
                    if not _has_label(w):
                        continue
                    def _set_first(h, d=0):
                        if d > 6 or _budget[0] <= 0:
                            return None
                        try:
                            for c in h.GetChildren():
                                if _budget[0] <= 0:
                                    return None
                                _budget[0] -= 1
                                ct = c.ControlTypeName.replace("Control", "")
                                if ct in ("Edit", "Document"):
                                    try:
                                        vp = c.GetValuePattern()
                                        if vp is not None:
                                            vp.SetValue(text)
                                            return {"ctrl": (c.Name or "")[:50],
                                                    "window": (w.Name or "")[:60],
                                                    "method": "uia_setvalue"}
                                    except Exception as _e:
                                        _record_swallow(_e, "omni_core")
                                rr = _set_first(c, d + 1)
                                if rr:
                                    return rr
                        except Exception as _e:
                            _record_swallow(_e, "omni_core")
                        return None
                    rr = _set_first(w)
                    if rr:
                        return rr
                except Exception:
                    continue
    except Exception as _e:
        _record_swallow(_e, "omni_core")
    return None


# ═══════════════════════════════════════════
#  ⛔ 自动生成: omni_core 共享基础设施 (拆分自 omni_tentacle, 2026-08-10)
#  所有 mixin 通过 `from omni_core import *` 获得模块级符号
# ═══════════════════════════════════════════
__all__ = ['sys', 'json', 'time', 'base64', 'io', 'Path', 'datetime', 'ROOT', '_MSS_SCT', '_DXCAM', '_DXCAM_FAIL_TS', '_DXCAM_BASE', '_DXCAM_BASE_TIME', '_NV_LITE', '_NV_LITE_TS', '_get_sct', '_mss_drop', '_get_dxcam', '_dxcam_frame', '_native_lite_eye', '_screen_capture', '_mouse_move', '_mouse_click', '_mouse_double_click', '_mouse_scroll', '_keyboard_type', '_keyboard_press', '_keyboard_hotkey', '_mouse_position', '_screen_size', '_enum_windows', 'window_title_matches', '_WINDOW_TITLE_MAP', '_find_window', '_get_active_window', '_focus_window', '_background_click', '_win32', '_win32_backend_status', '_require_win32', 'WindowBackendUnavailable', '_ct_window_text', '_ct_window_class', '_ct_window_rect', '_ct_window_from_point', '_ct_window_pid', '_ct_window_thread', '_ct_process_name', '_window_snapshot', 'refusal', 'screen_capture_safe', '_uia_set_value_by_window', '_uia_set_value_by_label', '_uia_element_at_window_point', '_occluded_state_signature', '_occluded_state_changed', '_uia_occluded_click']
