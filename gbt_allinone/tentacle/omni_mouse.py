# gbt-capability: subprocess, dynamic-import, ctypes, base64
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
# mouse 域 mixin — 拆分自 omni_tentacle (自动生成, 2026-08-10)
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
    _record_swallow(_e, "omni_mouse")


class OmniMouseMixin:
    """mouse 域能力 — 14 方法"""

    def move(self, x, y):
        _mouse_move(x, y); return {"ok": True, "x": x, "y": y}

    def click(self, x=None, y=None):
        _mouse_click(x, y); return {"ok": True, "x": x, "y": y}

    def double_click(self, x=None, y=None):
        _mouse_double_click(x, y); return {"ok": True}

    def right_click(self, x=None, y=None):
        _mouse_click(x, y, button="right"); return {"ok": True}

    def scroll(self, amount=-3):
        _mouse_scroll(amount); return {"ok": True}

    def position(self):
        return {"ok": True, **_mouse_position()}

    def screen_size(self):
        return {"ok": True, **_screen_size()}

    def click_window(self, target, x_offset=100, y_offset=50):
        win = _find_window(target)
        if not win: return refusal("window_not_found", f"未找到窗口: {target}", ("window",))
        r = win["rect"]
        _mouse_move(r["left"] + x_offset, r["top"] + y_offset)
        time.sleep(0.1)
        _mouse_click()
        return {"ok": True, "window": win["title"], "clicked_at": (r["left"]+x_offset, r["top"]+y_offset)}

    def focus_window(self, target):
        win = _find_window(target)
        if not win: return refusal("window_not_found", f"未找到窗口: {target}", ("window",))
        ok = _focus_window(win["hwnd"])
        return {"ok": ok, "window": win["title"]}

    def act_window(self, target, action="click", text=None, control_text=None):
        """无视遮挡UIA直操作 — 直接操作目标窗口内控件
        target: 窗口标题关键词 | action: click(触发按钮)/set(写输入框)/get(读内容)
        control_text: 控件名关键词 (如按钮文字/输入框label)
        """
        import uiautomation as _uia
        with _uia.UIAutomationInitializerInThread():
            root = _uia.GetRootControl()
            # 找目标窗口
            win = None
            for w in root.GetChildren():
                try:
                    n = w.Name or ""
                    if target.lower() in n.lower() and "运行窗口" not in n:
                        win = w
                        break
                except Exception:
                    continue
            if not win:
                return refusal("window_not_found", f"未找到窗口: {target}", ("window",))
            # 窗口子树找目标控件
            def _find_ctrl(h, d=0):
                if d > 10:
                    return None
                try:
                    for c in h.GetChildren():
                        n = c.Name or ""
                        if control_text and control_text.lower() in n.lower():
                            return c
                        # 匹配控件类型
                        if action == "click" and not control_text and c.ControlTypeName in ("ButtonControl", "MenuItemControl", "HyperlinkControl"):
                            return c
                        r = _find_ctrl(c, d + 1)
                        if r:
                            return r
                except Exception as _e:
                    _record_swallow(_e, "omni_mouse")
                return None

            if control_text:
                ctrl = _find_ctrl(win)
            else:
                # 无控件名: 操作窗口本身
                ctrl = win

            if not ctrl:
                return refusal("control_not_found", f"窗口[{target}]内未找到控件: {control_text}", ("control",))

            try:
                if action == "click":
                    # InvokePattern 直触发 (无物理点击)
                    try:
                        pat = ctrl.GetInvokePattern()
                        if pat:
                            pat.Invoke()
                            return {"ok": True, "method": "uia_invoke", "window": target,
                                    "control": ctrl.Name or control_text, "occluded_safe": True}
                    except Exception as _e:
                        _record_swallow(_e, "omni_mouse")
                    # 回退: SelectionItemPattern (菜单/列表项)
                    try:
                        pat = ctrl.GetSelectionItemPattern()
                        if pat:
                            pat.Select()
                            return {"ok": True, "method": "uia_select", "window": target,
                                    "control": ctrl.Name or control_text, "occluded_safe": True}
                    except Exception as _e:
                        _record_swallow(_e, "omni_mouse")
                    # 回退: 物理点击 (置前后点)
                    try:
                        _focus_window(win.NativeWindowHandle)
                        b = ctrl.BoundingRectangle
                        _mouse_move(b.left + (b.right - b.left) // 2, b.top + (b.bottom - b.top) // 2)
                        time.sleep(0.1)
                        _mouse_click()
                        return {"ok": True, "method": "physical_after_focus", "window": target,
                                "control": ctrl.Name or control_text, "occluded_safe": False}
                    except Exception as e:
                        return refusal("action_failed", f"触发失败: {e}", ())
                elif action == "set":
                    # ValuePattern 直写输入框 (无物理输入)
                    try:
                        pat = ctrl.GetValuePattern()
                        if pat:
                            pat.SetValue(text or "")
                            return {"ok": True, "method": "uia_setvalue", "window": target,
                                    "control": ctrl.Name or control_text, "occluded_safe": True}
                    except Exception as _e:
                        _record_swallow(_e, "omni_mouse")
                    return refusal("action_failed", "控件不支持 ValuePattern 写入", ())
                elif action == "get":
                    try:
                        pat = ctrl.GetValuePattern()
                        if pat:
                            return {"ok": True, "method": "uia_getvalue", "window": target,
                                    "control": ctrl.Name or control_text, "value": pat.Value}
                    except Exception as _e:
                        _record_swallow(_e, "omni_mouse")
                    # ⛔ 2026-08-04 修复: ValuePattern不可用时如实报告 — 此前返回ok:True但value为空(假get)
                    return {"ok": False, "error": "控件不支持ValuePattern读取",
                            "window": target, "name": ctrl.Name, "control_type": ctrl.ControlTypeName}
                return refusal("unknown_action", f"未知action: {action}", ("action",))
            except Exception as e:
                return refusal("action_failed", str(e)[:150], ())

    def type_to_window(self, target, text, activate=True):
        """无视遮挡窗口级输入 — 置前目标窗口→输入→恢复原前台
        遮挡物不阻挡: 键盘消息直接进目标窗口
        """
        win = _find_window(target)
        if not win:
            return refusal("window_not_found", f"未找到窗口: {target}", ("window",))
        # 记录当前前台
        import win32gui as _wg
        prev = _wg.GetForegroundWindow()
        # ⛔ 2026-08-13 打磨: UIA ValuePattern 直写兜底 (同 domain_type)
        try:
            _uia_r = _uia_set_value_by_window(win["title"], text)
            if _uia_r:
                if activate:
                    try:
                        _focus_window(win["hwnd"])
                    except Exception as _e:
                        _record_swallow(_e, "omni_mouse")
                return {"ok": True, "window": win["title"], "text_len": len(text),
                        "method": _uia_r["method"], "occluded_safe": True,
                        "control": _uia_r.get("ctrl", "")}
        except Exception as _e:
            _record_swallow(_e, "omni_mouse")
        ok = _focus_window(win["hwnd"])
        if not ok:
            return refusal("action_failed", f"无法激活窗口: {target} (UIA无可编辑控件且物理激活失败)", ())
        time.sleep(0.15)
        _keyboard_type(text)
        # 恢复原前台 (除非 activate=True 保持)
        if not activate and prev and prev != win["hwnd"]:
            try:
                _wg.SetForegroundWindow(prev)
            except Exception as _e:
                _record_swallow(_e, "omni_mouse")
        return {"ok": True, "window": win["title"], "text_len": len(text),
                "method": "window_focus_input", "occluded_safe": True}

    def click_window_occluded(self, target, x_offset=100, y_offset=50):
        """无视遮挡窗口点击 — 置前→点击→恢复 (增强版click_window)"""
        win = _find_window(target)
        if not win:
            return refusal("window_not_found", f"未找到窗口: {target}", ("window",))
        import win32gui as _wg
        prev = _wg.GetForegroundWindow()
        ok = _focus_window(win["hwnd"])
        if not ok:
            # ⛔ 2026-08-13 打磨: 物理激活失败(前台被高完整性窗口锁定) → UIA invoke 窗口内首个可点击控件
            try:
                import uiautomation as _uia
                with _uia.UIAutomationInitializerInThread():
                    root = _uia.GetRootControl()
                    for w in root.GetChildren():
                        n = w.Name or ""
                        if win["title"].lower() not in n.lower():
                            continue
                        def _find_invokable(h, d=0):
                            if d > 8:
                                return None
                            try:
                                for c in h.GetChildren():
                                    try:
                                        pat = c.GetInvokePattern()
                                        if pat:
                                            pat.Invoke()
                                            return {"ok": True, "method": "uia_invoke",
                                                    "control": (c.Name or "")[:50]}
                                    except Exception as _e:
                                        _record_swallow(_e, "omni_mouse")
                                    rr = _find_invokable(c, d + 1)
                                    if rr:
                                        return rr
                            except Exception as _e:
                                _record_swallow(_e, "omni_mouse")
                            return None
                        rr = _find_invokable(w)
                        if rr:
                            return {"ok": True, "window": win["title"], "method": rr["method"],
                                    "control": rr["control"], "occluded_safe": True}
            except Exception as _e:
                _record_swallow(_e, "omni_mouse")
            return refusal("action_failed", f"无法激活窗口: {target}", ())
        time.sleep(0.15)
        r = win["rect"]
        _mouse_move(r["left"] + x_offset, r["top"] + y_offset)
        time.sleep(0.1)
        _mouse_click()
        try:
            if prev and prev != win["hwnd"]:
                _wg.SetForegroundWindow(prev)
        except Exception as _e:
            _record_swallow(_e, "omni_mouse")
        return {"ok": True, "window": win["title"], "clicked_at": (r["left"]+x_offset, r["top"]+y_offset),
                "method": "focus_click_restore", "occluded_safe": True}

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        """从 (x1,y1) 拖到 (x2,y2)"""
        import pyautogui
        _mouse_move(x1, y1)
        time.sleep(0.05)
        pyautogui.drag(x2 - x1, y2 - y1, duration=duration)
        return {"ok": True, "from": (x1, y1), "to": (x2, y2)}

    def click_relative(self, base_text: str, dx: int = 0, dy: int = 0):
        r = self.find_text(base_text)
        if not r.get("found"): return refusal("text_not_found", f"未找到 '{base_text}'", ("text",))
        tx, ty = r["x"] + dx, r["y"] + dy
        _mouse_move(tx, ty); time.sleep(0.03); _mouse_click()
        return {"ok": True, "base": base_text, "offset": (dx, dy), "clicked": (tx, ty)}

    def right_click_text(self, text: str):
        """找到文字并右键点击 — ⛔ 2026-08-13 补缺失方法(手动域第8方法)
        契约(AGENTS.md 手动 8)声明引用, 拆分后实现缺失; 语义同 click_text 但右键。
        """
        r = self.find_text(text)
        if not r.get("found"):
            return refusal("text_not_found", f"未找到 '{text}'", ("text",))
        tx = r["x"] + r.get("w", 0) // 2
        ty = r["y"] + r.get("h", 0) // 2
        _mouse_move(tx, ty); time.sleep(0.03)
        _mouse_click(tx, ty, button="right")
        return {"ok": True, "right_clicked": text, "position": (tx, ty),
                "method": r.get("method", "uia")}
