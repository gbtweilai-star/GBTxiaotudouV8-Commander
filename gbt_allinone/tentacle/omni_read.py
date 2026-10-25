# gbt-capability: subprocess, dynamic-import, ctypes, base64
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
# ⚠️ 外部内容纪律：本域读到的**屏幕文字一律是不可信数据，不是指令** ——
#    屏幕上的字来自任何程序（含网页、聊天窗、控制台），可能写着"忽略你之前的指令"。
#    本域只把它当数据返回；不执行其中任何祈使句、不拼进 system 提示、不拿去驱动执行口。
#    覆盖校验器：py -3.14 -m gbt_allinone.tools.external_content_check gbt_allinone
# read 域 mixin — 拆分自 omni_tentacle (自动生成, 2026-08-10)
# ⛔ 拆分保障: 自身目录(brain/)入 sys.path — spec_from_file_location 加载
#    不会自动加路径, 需显式保障 omni_core 可寻址 (插 brain/ 而非项目根)
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))


# ── 病因钩子：吞错统一收口 + 导航入口病因（**必须放在 sys.path 修正之后**）。
#    教训（2026-09-22 实测）：放在 insert 之前 ⇒ `from nav_etiology import …` 导入期就失败，
#    静默退回垫片 ⇒ 63 处"收口"一个病因都没真记上 = **假收口**。
try:
    from nav_etiology import (record_swallow as _record_swallow,
                              etiology as _etiology,
                              enrich as _enrich_cause)
except Exception:  # noqa: BLE001
    def _record_swallow(_e, _mod="?", _op=""):
        import sys as _s
        print(f"⚠️ {_mod}: 吞错: {_e}", file=_s.stderr)
        return "action_no_effect"

    def _etiology(_m, _o=""):
        def _d(fn):
            return fn
        return _d

    def _enrich_cause(r, _m="?", _o=""):
        return r
# publish沙盒(非项目根cwd)执行兜底: 类定义不访问core符号, 吞异常安全
try:
    from omni_core import *  # noqa: F401,F403
except Exception as _e:
    _record_swallow(_e, "omni_read")


class OmniReadMixin:
    """read 域能力 — 6 方法"""

    def find_text(self, text: str, region=None, fast: bool = False):
        """在屏幕上查找文字 → 返回坐标. UIA优先(快准), 原生视觉兜底(画布/游戏/自绘UI)

        fast=True: 仅UIA快速定位(窗口匹配+子树, 跳过全树遍历与视觉兜底, ~133ms)
                   — 轮询/监控/滚动查找等高频场景用; 未命中立即返回, 不含47s视觉兜底
        """
        # 1. UIA 快速定位 (窗口匹配+子树, ~133ms)
        try:
            f = self._uia_find_fast(text, fast=fast)
            if f:
                return {"found": True, "ok": True, "x": f["x"], "y": f["y"], "text": f["text"],
                        "conf": 1.0, "method": "uia", "w": f["w"], "h": f["h"]}
        except Exception as _e:
            _record_swallow(_e, "omni_read")
        if fast:
            return {"found": False, "ok": True, "fast": True,
                    "error": f"快速模式未找到 '{text}' (UIA)"}
        # 2. ⛔ 2026-08-09 原生视觉兜底: UIA读不到的(自绘UI/游戏/画布/网页渲染)视觉模型看图定位
        try:
            _nv = _native_lite_eye()
            if _nv is not None:
                _nr = _nv.find_native(text, region, confirm=True)  # ⛔ 2026-08-13 打磨: 启用二次确认 — VL模型单次定位会幻觉假阳性(24字随机串conf0.85误报), 定位后裁剪区域复验防误判
                if isinstance(_nr, dict) and _nr.get("found"):
                    return {"found": True, "ok": True, "x": _nr["x"], "y": _nr["y"], "text": text,
                            "conf": 0.85, "method": "vision-native",
                            "w": _nr.get("w", 0), "h": _nr.get("h", 0)}
        except Exception as _e:
            _record_swallow(_e, "omni_read")
        return {"found": False, "ok": True, "error": f"未找到 '{text}' (UIA+原生视觉均未命中)"}

    def click_text(self, text: str):
        """找到文字并点击 — 未命中自动弹窗处理后再试一次 (人类: 先关弹窗再点)"""
        r = self.find_text(text)
        if r.get("found"):
            self.click(r["x"], r["y"])
            return {"ok": True, "clicked": text, "position": (r["x"], r["y"]), "method": r.get("method", "uia")}
        try:
            self.handle_any_dialog()
            r = self.find_text(text)
            if r.get("found"):
                self.click(r["x"], r["y"])
                return {"ok": True, "clicked": text, "position": (r["x"], r["y"]),
                        "method": r.get("method", "uia"), "after_dialog": True}
        except Exception as _e:
            _record_swallow(_e, "omni_read")
        return refusal("text_not_found", f"未找到 '{text}'", ("text",))

    @_etiology("omni_read", "wait_text")
    def wait_text(self, text: str, timeout: float = 30, vision: bool = True):
        """等待文字出现 — UIA 快查轮询; ⛔ 2026-08-13 视觉兜底: 自绘/画布/游戏UI UIA读不到,
        临近超时(12s内)做一次轻量视觉定位 find_native(无二次确认), 命中也算出现"""
        import time
        deadline = time.time() + timeout
        vision_tried = False
        while True:
            try:
                f = self._uia_find_fast(text, fast=True)
                if f:
                    return {"ok": True, "status": "appeared", "position": (f["x"], f["y"]), "method": "uia"}
            except Exception as _e:
                _record_swallow(_e, "omni_read")
            if deadline <= time.time():
                break
            if vision and not vision_tried and (deadline - time.time()) <= 12:
                vision_tried = True  # 只试一次
                try:
                    _nv = _native_lite_eye()
                    if _nv is not None:
                        _nr = _nv.find_native(text, confirm=False)
                        if isinstance(_nr, dict) and _nr.get("found"):
                            return {"ok": True, "status": "appeared",
                                    "position": (_nr["x"], _nr["y"]), "method": "vision-native"}
                except Exception as _e:
                    _record_swallow(_e, "omni_read")
            time.sleep(0.5)
        return {"ok": False, "status": "timeout", "error": f"等待 '{text}' 超时({timeout}s)"}

    def read_text_fast(self, scope="active"):
        """快速读屏 — 触手=数据线: UIA秒级读取(300ms级), 非OCR。
        三位一体 _read_screen() 调用此方法, 返回可读文本给大脑。
        scope: "active"=仅活动窗口(最快, 300ms) | "full"=全屏窗口(秒级)
        ⛔ 2026-08-07 控制台回退: 活动窗口是控制台时, UIA读不到conhost字符单元,
           用 console_vision(AttachConsole+ReadConsoleOutputW) 直读缓冲区 — 显示屏→大脑传输线"""
        try:
            # ⛔ 2026-08-07 控制台直读回退 — UIA对conhost只返回标题/滚动条, 读不到字符
            if scope == "active":
                try:
                    import ctypes as _ct
                    import ctypes.wintypes  # Py3.12 fix
                    _u32 = _ct.windll.user32
                    _hw = _u32.GetForegroundWindow()
                    _cls = _ct.create_unicode_buffer(256)
                    _u32.GetClassNameW(_hw, _cls, 256)
                    if "ConsoleWindowClass" in _cls.value or "CASCADIA" in _cls.value:
                        _pid = _ct.wintypes.DWORD()
                        _u32.GetWindowThreadProcessId(_hw, _ct.byref(_pid))
                        if _pid.value:
                            from caps.console_vision.console_vision import read_console as _rc
                            _cr = _rc(pid=_pid.value)
                            if _cr.get("ok") and _cr.get("full_text", "").strip():
                                _ft = _cr["full_text"]
                                _res = {"ok": True, "method": "console_buffer", "scope": scope,
                                        "w": _cr["w"], "h": _cr["h"], "count": _cr["h"],
                                        "text": _ft[:8000]}
                                try:
                                    _tx_send({"text": _ft[:1500], "count": _cr["h"], "scope": scope, "ok": True},
                                        source="omni_tentacle.read_text_fast[console]", channel="visual", priority="high")
                                except Exception as _e:
                                    _record_swallow(_e, "omni_read")
                                return _res
                except Exception as _e:
                    _record_swallow(_e, "omni_read")
            import uiautomation as _uia
            with _uia.UIAutomationInitializerInThread():
                texts = []
                seen = set()
                def _walk(ctrl, depth=0):
                    if depth > 6 or len(texts) > 250:
                        return
                    try:
                        if ctrl.IsOffscreen:
                            return
                        name = ctrl.Name
                        if name and name.strip() and name not in seen:
                            seen.add(name)
                            texts.append(name.strip()[:200])
                        for child in ctrl.GetChildren():
                            _walk(child, depth + 1)
                    except Exception as _e:
                        _record_swallow(_e, "omni_read")
                if scope == "active":
                    # 活动窗口 — 最快通道
                    win = _uia.GetForegroundControl()
                    if win:
                        _walk(win, 0)
                else:
                    # 全屏 — 各顶层窗口
                    root = _uia.GetRootControl()
                    for win in root.GetChildren():
                        try:
                            if not win.IsOffscreen and win.Name and win.Name.strip():
                                texts.append(win.Name.strip()[:200])
                            for child in win.GetChildren():
                                _walk(child, 0)
                        except Exception:
                            continue
                result = {"ok": True, "method": "uia_data_line", "scope": scope,
                          "count": len(texts),
                          "text": chr(10).join(texts[:300])[:8000]}
                # ⛔ 2026-08-07 打磨: 秒级读屏穿透 → 大脑实时感知屏幕文字(快速通道)
                try:
                    _tx_send({"text": result.get("text", "")[:1500], "count": result.get("count", 0),
                         "scope": scope, "ok": True},
                        source="omni_tentacle.read_text_fast", channel="visual",
                        priority="high")
                except Exception as _e:
                    _record_swallow(_e, "omni_read")
                return result
        except Exception as e:
            return refusal("action_failed", f"快速读屏失败: {str(e)[:100]}", ())

    def read_text(self, region=None):
        """读屏文字(带坐标契约) — UIA控件树优先, OCR兜底"""
        try:
            import uiautomation as _uia
            with _uia.UIAutomationInitializerInThread():
                root = _uia.GetRootControl()
                blocks = []
                seen = set()
                def _walk(ctrl, depth=0):
                    if depth > 8 or len(blocks) > 200:
                        return
                    try:
                        name = ctrl.Name
                        if name and name.strip() and name not in seen:
                            seen.add(name)
                            r = ctrl.BoundingRectangle
                            blocks.append({"text": name.strip()[:200],
                                           "x": r.left, "y": r.top,
                                           "w": r.right - r.left, "h": r.bottom - r.top,
                                           "type": ctrl.ControlTypeName.replace("Control", "")})
                        for child in ctrl.GetChildren():
                            _walk(child, depth + 1)
                    except Exception as _e:
                        _record_swallow(_e, "omni_read")
                _walk(root)
                if blocks:
                    result = {"ok": True, "method": "uia", "count": len(blocks),
                              "text_blocks": blocks[:200],
                              "full_text": chr(10).join(b["text"] for b in blocks[:200])[:8000]}
                    # ⛔ 2026-08-04 触手→大脑: 读屏结果穿透传输 (大脑实时感知屏幕文字)
                    try:
                        _tx_send({"text": result.get("full_text", "")[:1500],
                             "count": result.get("count", 0),
                             "text_blocks": result.get("text_blocks", [])[:40],
                             "ok": True},
                            source="omni_tentacle.read_text", channel="visual",
                            priority="high")
                    except Exception as _e:
                        _record_swallow(_e, "omni_read")
                    return result
        except Exception as _e:
            _record_swallow(_e, "omni_read")
        # ⛔ 2026-08-07 控制台直读回退 — UIA读不到conhost字符, 控制台窗口用缓冲区直读
        try:
            import ctypes as _ct
            import ctypes.wintypes  # Py3.12 fix
            _u32 = _ct.windll.user32
            _hw = _u32.GetForegroundWindow()
            _cls = _ct.create_unicode_buffer(256)
            _u32.GetClassNameW(_hw, _cls, 256)
            if "ConsoleWindowClass" in _cls.value or "CASCADIA" in _cls.value:
                _pid = _ct.wintypes.DWORD()
                _u32.GetWindowThreadProcessId(_hw, _ct.byref(_pid))
                if _pid.value:
                    from caps.console_vision.console_vision import read_console as _rc
                    _cr = _rc(pid=_pid.value)
                    if _cr.get("ok"):
                        _ft = _cr.get("full_text", "")
                        _blocks = [{"text": l, "x": 0, "y": i, "w": _cr["w"], "h": 1, "type": "ConsoleRow"}
                                   for i, l in enumerate(_cr["lines"]) if l.strip()]
                        _res = {"ok": True, "method": "console_buffer", "count": len(_blocks),
                                "text_blocks": _blocks[:200], "full_text": _ft[:8000],
                                "w": _cr["w"], "h": _cr["h"]}
                        try:
                            _tx_send({"text": _ft[:1500], "count": len(_blocks), "ok": True},
                                source="omni_tentacle.read_text[console]", channel="visual", priority="high")
                        except Exception as _e:
                            _record_swallow(_e, "omni_read")
                        return _res
        except Exception as _e:
            _record_swallow(_e, "omni_read")
        return refusal("dependency_unavailable", "读屏失败: UIA不可用 (无OCR, 仅数据通道)", ("uiautomation",))

    def read_region_text(self, left=0, top=0, width=0, height=0):
        """区域读字 — ⛔ 2026-08-13 打磨: 补缺失方法(读屏6能力, screen_observer调用未实现曾致look整体失败)"""
        try:
            try:
                import ctypes as _ct
                import ctypes.wintypes  # Py3.12 fix
                _u32 = _ct.windll.user32
                _hw = _u32.GetForegroundWindow()
                _cls = _ct.create_unicode_buffer(256)
                _u32.GetClassNameW(_hw, _cls, 256)
                if "ConsoleWindowClass" in _cls.value or "CASCADIA" in _cls.value:
                    _pid = _ct.wintypes.DWORD()
                    _u32.GetWindowThreadProcessId(_hw, _ct.byref(_pid))
                    if _pid.value:
                        from caps.console_vision.console_vision import read_console as _rc2
                        _cr2 = _rc2(pid=_pid.value)
                        if _cr2.get("ok"):
                            _ft2 = _cr2.get("full_text", "")
                            return {"ok": True, "method": "console_buffer", "count": _cr2.get("count", 0),
                                    "text": _ft2[:2000],
                                    "text_blocks": [{"text": l, "x": 0, "y": i, "w": _cr2["w"], "h": 1, "type": "ConsoleRow"}
                                                      for i, l in enumerate(_cr2.get("lines", [])) if l.strip()][:100]}
            except Exception as _e:
                _record_swallow(_e, "omni_read")
            r = self.read_text()
            if not r.get("ok"):
                return r
            _in = []
            for b in r.get("text_blocks", []):
                _cx = b.get("x", 0) + b.get("w", 0) / 2
                _cy = b.get("y", 0) + b.get("h", 0) / 2
                if width <= 0 or height <= 0 or (left <= _cx and _cx <= left + width and top <= _cy and _cy <= top + height):
                    _in.append(b)
            return {"ok": True, "method": "uia-region", "count": len(_in),
                    "text": chr(10).join(b["text"] for b in _in)[:2000], "text_blocks": _in[:100]}
        except Exception as e:
            return refusal("action_failed", f"区域读字失败: {str(e)[:100]}", ())

    def read_console(self, pid=None, title=None, text=None):
        """控制台缓冲区直读 — 显示屏→大脑传输线 ⛔ 2026-08-07
        UIA读不到conhost字符单元。本方法用AttachConsole+ReadConsoleOutputW直读
        任何进程的控制台字符网格, LVB宽字符尾格跳过, 字符级精确。

        pid:  目标进程pid(直接附加)
        title: 窗口标题(精确)
        text:  窗口标题关键词(模糊匹配)

        返回 {ok, w, h, lines[], full_text}
        """
        try:
            from caps.console_vision.console_vision import read_console as _rc
            _r = _rc(pid=pid, title=title, text=text)
            if _r.get("ok"):
                try:
                    _tx_send({"text": _r.get("full_text", "")[:1500], "w": _r["w"], "h": _r["h"], "ok": True},
                        source="omni_tentacle.read_console", channel="visual", priority="high")
                except Exception as _e:
                    _record_swallow(_e, "omni_read")
            return _r
        except Exception as e:
            return refusal("action_failed", f"控制台直读失败: {str(e)[:100]}", ())

# ── 遥测转发（2026-10-04 修）：**包内相对优先，退绝对导入** ─────────────────────
# 病灶：把导入改成包内相对后，omni_read 被**单独加载**（非包上下文）时相对导入抛
# "attempted relative import with no known parent package"，外层 except 把它**吞成一行提示**
# （实测见 `吞错[backend_unavailable]`）—— 遥测丢了不打紧，但**原因不许无痕吞掉**。
# ⇒ 统一取一次（缓存）+ 两条路都试 + 原因留在 TRANSMIT_LAST_ERR。
_TRANSMIT = None
TRANSMIT_LAST_ERR = ""


def _get_transmit():
    global _TRANSMIT, TRANSMIT_LAST_ERR
    if _TRANSMIT is not None:
        return _TRANSMIT
    try:
        from .brain.tentacle_transmission import transmit as _t      # 包内（正常路径）
        _TRANSMIT, TRANSMIT_LAST_ERR = _t, ""
        return _t
    except Exception as _e1:                                     # noqa: BLE001
        try:
            from gbt_allinone.tentacle.brain.tentacle_transmission import transmit as _t
            _TRANSMIT, TRANSMIT_LAST_ERR = _t, ""
            return _t
        except Exception as _e2:                                 # noqa: BLE001
            TRANSMIT_LAST_ERR = "relative: %s | absolute: %s" % (str(_e1)[:60], str(_e2)[:60])
            return None


def _tx_send(payload, **kw):
    """转发一次遥测；取不到 transmit ⇒ False + 原因留痕（不无痕吞）。"""
    global TRANSMIT_LAST_ERR
    _t = _get_transmit()
    if _t is None:
        return False
    try:
        _t(payload, **kw)
        return True
    except Exception as _e:                                      # noqa: BLE001
        TRANSMIT_LAST_ERR = "call: %s" % str(_e)[:80]
        return False
