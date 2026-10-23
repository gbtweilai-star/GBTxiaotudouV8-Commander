# gbt-capability: subprocess, dynamic-import, ctypes, base64
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
# ⚠️ 外部内容纪律：本域从屏幕/控件树拿到的**文字与像素一律是不可信数据，不是指令** ——
#    `grab_pixel`/`grab_region`/`grab_table`/`grab_value` 读的是屏幕，
#    屏幕内容由任何程序决定（含网页与聊天窗），可能写着"忽略你之前的指令"。
#    本域只把它当数据返回；不执行其中任何祈使句、不拼进 system 提示、不拿去驱动执行口。
#    覆盖校验器：py -3.14 -m gbt_allinone.tools.external_content_check gbt_allinone
# domain 域 mixin — 拆分自 omni_tentacle (自动生成, 2026-08-10)
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
    _record_swallow(_e, "omni_domain")
try:
    from omni_core import window_title_matches  # noqa: F401  (显式导入, 绕过 __all__)
except Exception as _e:
    _record_swallow(_e, "omni_domain")


class OmniDomainMixin:
    """domain 域能力 — 17 方法"""

    def domain_index(self, max_windows: int = 30, control_depth: int = 3) -> dict:  # perf: 深度3平衡(2漏控件, 4慢)
        """领域索引 — 枚举全桌面可见窗口 + 每窗口可操作控件树 (含被遮挡窗口)
        控件树是逻辑层, 不依赖物理可见性 → 被遮挡窗口的控件同样可索引/操作
        """
        import uiautomation as _uia
        with _uia.UIAutomationInitializerInThread():  # ⛔ 2026-08-07: 线程安全UIA初始化
            return self._domain_index_impl(_uia, max_windows, control_depth)

    def _domain_index_impl(self, _uia, max_windows: int, control_depth: int) -> dict:
        root = _uia.GetRootControl()
        windows = []
        _CTRL_TYPES = ("Button", "MenuItem", "Edit", "Hyperlink", "TabItem", "CheckBox", "ListItem", "Document")
        for w in root.GetChildren():
            if len(windows) >= max_windows:
                break
            try:
                wname = w.Name or ""
                if not wname.strip() or "运行窗口" in wname or "通知" in wname:
                    continue
                b = w.BoundingRectangle
                controls = []
                def _walk(h, d=0):
                    if d > control_depth:
                        return
                    try:
                        for c in h.GetChildren():
                            ctype = c.ControlTypeName.replace("Control", "")
                            cname = (c.Name or "").strip()
                            if ctype in _CTRL_TYPES and cname:
                                cb = c.BoundingRectangle
                                controls.append({
                                    "type": ctype, "name": cname[:80],
                                    "x": cb.left, "y": cb.top, "w": cb.right - cb.left, "h": cb.bottom - cb.top,
                                })
                            _walk(c, d + 1)
                    except Exception as _e:
                        _record_swallow(_e, "omni_domain")
                _walk(w)
                windows.append({
                    "title": wname[:100],
                    "type": w.ControlTypeName.replace("Control", ""),
                    "rect": {"left": b.left, "top": b.top, "right": b.right, "bottom": b.bottom},
                    "controls": controls[:60],
                    "control_count": len(controls),
                })
            except Exception:
                continue
        return {"ok": True, "method": "domain_index", "windows": windows,
                "window_count": len(windows),
                "total_controls": sum(w["control_count"] for w in windows)}

    def _domain_find_control(self, window_title: str, control_text: str, control_type: str = None):
        import uiautomation as _uia
        with _uia.UIAutomationInitializerInThread():  # ⛔ 2026-08-07: 线程安全UIA初始化
            return self._domain_find_control_impl(_uia, window_title, control_text, control_type)

    def _domain_find_control_impl(self, _uia, window_title: str, control_text: str, control_type: str = None):
        root = _uia.GetRootControl()
        for w in root.GetChildren():
            try:
                n = w.Name or ""
                if window_title_matches(window_title, n) and "运行窗口" not in n:
                    def _find(h, d=0):
                        if d > 8:
                            return None
                        try:
                            for c in h.GetChildren():
                                cn = (c.Name or "").strip()
                                ctype = c.ControlTypeName.replace("Control", "")
                                if control_text and control_text.lower() in cn.lower():
                                    if control_type is None or ctype == control_type:
                                        return c
                                r = _find(c, d + 1)
                                if r:
                                    return r
                        except Exception as _e:
                            _record_swallow(_e, "omni_domain")
                        return None
                    ctrl = _find(w)
                    if ctrl:
                        return ctrl
            except Exception:
                continue
        return None

    def domain_act(self, window: str, control: str = None, action: str = "click", text: str = None, control_type: str = None) -> dict:
        """领域覆盖穿透操作 — 任意窗口任意控件, 无视遮挡
        window: 窗口标题关键词 | control: 控件名关键词 | action: click/set/get/select
        """
        ctrl = self._domain_find_control(window, control or "", control_type)
        if not ctrl:
            return refusal("control_not_found", f"领域内未找到: 窗口[{window}] 控件[{control}]", ("window", "control"))
        try:
            if action in ("click", "select", "check"):
                try:
                    pat = ctrl.GetInvokePattern()
                    if pat:
                        pat.Invoke()
                        return {"ok": True, "method": "uia_invoke", "window": window,
                                "control": (ctrl.Name or control)[:80], "occluded_safe": True}
                except Exception as _e:
                    _record_swallow(_e, "omni_domain")
                try:
                    pat = ctrl.GetSelectionItemPattern()
                    if pat:
                        pat.Select()
                        return {"ok": True, "method": "uia_select", "window": window,
                                "control": (ctrl.Name or control)[:80], "occluded_safe": True}
                except Exception as _e:
                    _record_swallow(_e, "omni_domain")
                try:
                    pat = ctrl.GetTogglePattern()
                    if pat:
                        pat.Toggle()
                        return {"ok": True, "method": "uia_toggle", "window": window,
                                "control": (ctrl.Name or control)[:80], "occluded_safe": True}
                except Exception as _e:
                    _record_swallow(_e, "omni_domain")
                try:
                    _focus_window(ctrl.NativeWindowHandle)
                    b = ctrl.BoundingRectangle
                    _mouse_move(b.left + (b.right - b.left) // 2, b.top + (b.bottom - b.top) // 2)
                    time.sleep(0.1)
                    _mouse_click()
                    return {"ok": True, "method": "physical_fallback", "window": window,
                            "control": (ctrl.Name or control)[:80], "occluded_safe": False}
                except Exception as e:
                    return refusal("action_failed", f"触发失败: {e}", ())
            elif action == "set":
                try:
                    pat = ctrl.GetValuePattern()
                    if pat:
                        pat.SetValue(text or "")
                        return {"ok": True, "method": "uia_setvalue", "window": window,
                                "control": (ctrl.Name or control)[:80], "occluded_safe": True}
                except Exception as _e:
                    _record_swallow(_e, "omni_domain")
                try:
                    _focus_window(ctrl.NativeWindowHandle)
                    time.sleep(0.2)
                    _keyboard_type(text or "")
                    return {"ok": True, "method": "focus_type", "window": window,
                            "control": (ctrl.Name or control)[:80], "occluded_safe": False}
                except Exception as e:
                    return refusal("write_failed", f"写入失败: {e}", ())
            elif action == "get":
                try:
                    pat = ctrl.GetValuePattern()
                    if pat:
                        return {"ok": True, "method": "uia_getvalue", "window": window,
                                "control": (ctrl.Name or control)[:80], "value": pat.Value}
                except Exception as _e:
                    _record_swallow(_e, "omni_domain")
                # ⛔ 2026-08-04 修复: ValuePattern不可用时如实报告 — 此前返回ok:True但value为空(假get)
                return {"ok": False, "error": "控件不支持ValuePattern读取",
                        "window": window, "name": ctrl.Name, "control_type": ctrl.ControlTypeName}
            return refusal("unknown_action", f"未知action: {action}", ("action",))
        except Exception as e:
            return refusal("action_failed", str(e)[:150], ())

    def domain_type(self, window: str, text: str, activate: bool = False) -> dict:
        """领域覆盖穿透输入 — 目标窗口键入文字 (无视遮挡, 输入后恢复前台)"""
        win = _find_window(window)
        if not win:
            return refusal("window_not_found", f"未找到窗口: {window}", ("window",))
        import win32gui as _wg
        prev = _wg.GetForegroundWindow()
        # ⛔ 2026-08-13 打磨: UIA ValuePattern 直写兜底 — 前台被高完整性窗口锁定时
        #    物理输入无法落地, UIA 直写可编辑控件不依赖焦点
        try:
            _uia_r = _uia_set_value_by_window(win["title"], text)
            if _uia_r:
                if activate:
                    try:
                        _focus_window(win["hwnd"])
                    except Exception as _e:
                        _record_swallow(_e, "omni_domain")
                return {"ok": True, "window": win["title"], "text_len": len(text),
                        "method": _uia_r["method"], "occluded_safe": True,
                        "control": _uia_r.get("ctrl", "")}
        except Exception as _e:
            _record_swallow(_e, "omni_domain")
        ok = _focus_window(win["hwnd"])
        if not ok:
            return refusal("action_failed", f"无法激活窗口: {window} (UIA无可编辑控件且物理激活失败)", ())
        time.sleep(0.15)
        _keyboard_type(text)
        if not activate and prev and prev != win["hwnd"]:
            try:
                _wg.SetForegroundWindow(prev)
            except Exception as _e:
                _record_swallow(_e, "omni_domain")
        return {"ok": True, "window": win["title"], "text_len": len(text),
                "method": "domain_type", "occluded_safe": True}

    def domain_read(self, window: str) -> dict:
        """领域覆盖穿透读 — 目标窗口全部可见文本 (无视遮挡)"""
        import uiautomation as _uia
        with _uia.UIAutomationInitializerInThread():  # ⛔ 2026-08-07: 线程安全UIA初始化
            return self._domain_read_impl(_uia, window)

    def _domain_read_impl(self, _uia, window: str) -> dict:
        root = _uia.GetRootControl()
        for w in root.GetChildren():
            try:
                n = w.Name or ""
                if window_title_matches(window, n) and "运行窗口" not in n:
                    texts = []
                    def _walk(h, d=0):
                        if d > 8:
                            return
                        try:
                            for c in h.GetChildren():
                                cn = (c.Name or "").strip()
                                ctype = c.ControlTypeName.replace("Control", "")
                                if cn and ctype in ("Text", "Button", "MenuItem", "Edit", "TabItem", "Document", "ListItem", "Hyperlink"):
                                    texts.append({"text": cn[:200], "type": ctype})
                                _walk(c, d + 1)
                        except Exception as _e:
                            _record_swallow(_e, "omni_domain")
                    _walk(w)
                    seen = []
                    seen_set = set()
                    for t in texts:
                        if t["text"] not in seen_set:
                            seen_set.add(t["text"])
                            seen.append(t)
                    return {"ok": True, "window": n[:100], "count": len(seen),
                            "texts": seen[:100],
                            "full_text": chr(10).join(t["text"] for t in seen)[:8000]}
            except Exception:
                continue
        return refusal("window_not_found", f"未找到窗口: {window}", ("window",))

    # 2026-09-22 删（职业习惯审计 G5-6「不注释掉的死代码」）：
    # 这里原本是「把 def 行注释掉、方法体留着」——
    #     # def _grab_screen_pil(self, region: dict = None):
    #         """PIL ImageGrab 截屏 …"""
    #         from PIL import ImageGrab …
    # 后果不是"少一个函数"，是**留下 5 行永不可达语句**挂在上面那个 return 之后：
    # 既污染前一个函数的语义，又躲开所有静态检查（它不是 _*.py 残留、不是 .tmp，
    # hygiene 的四条铁律一条都碰不到）。
    # 现状核实：全仓 grep `_grab_screen_pil` 只有那一处定义、无任何调用方 ⇒ 废弃。
    # 若将来要恢复截屏：**写回完整的 def**，不要留半截。

    def _uia_find_fast(self, text: str, fast=False):
        # ⛔ 2026-08-13 打磨: fast=True 跳过全树遍历(未命中25s), wait_text轮询用
        """UIA快速定位 — 顶层窗口精确匹配优先(快), 全树回退(准)
        基线: 全树遍历 585ms → 窗口匹配+子树 133ms (4.4x)
        """
        import uiautomation as _uia
        try:
            import ctypes as _ct
            _u32 = _ct.windll.user32
            _sw, _sh = _u32.GetSystemMetrics(0), _u32.GetSystemMetrics(1)
        except Exception:
            _sw = _sh = 4000
        with _uia.UIAutomationInitializerInThread():
            root = _uia.GetRootControl()
            # ⛔ 2026-08-13 打磨: 全局节点预算+离屏窗口跳过 — 未加预算时忙桌面
            #    深度8子树遍历单次未命中4.6s, 直接击穿 monitor/watch_any/on_text 的时长控制
            _budget = [400]
            # 方案A: 顶层窗口名匹配 (最快)
            try:
                for w in root.GetChildren():
                    try:
                        wname = w.Name or ""
                        if not wname.strip() or "运行窗口" in wname:
                            continue
                        wb = w.BoundingRectangle
                        if wb.right <= wb.left or wb.bottom <= wb.top:
                            continue  # 最小化/隐藏 → 跳过
                        if not (0 <= (wb.left + wb.right) / 2 <= _sw and 0 <= (wb.top + wb.bottom) / 2 <= _sh):
                            continue  # 离屏窗口 → 跳过
                        # 控件名包含目标 → 直接命中窗口
                        if text.lower() in wname.lower():
                            return {"text": wname, "x": wb.left, "y": wb.top,
                                    "w": wb.right - wb.left, "h": wb.bottom - wb.top,
                                    "type": w.ControlTypeName.replace("Control", "")}
                        # 窗口子树搜索 (限深8 + 全局节点预算)
                        def _sub(h, d=0):
                            if d > 8 or _budget[0] <= 0:
                                return None
                            try:
                                for c in h.GetChildren():
                                    if _budget[0] <= 0:
                                        return None
                                    _budget[0] -= 1
                                    n = c.Name or ""
                                    if n and text.lower() in n.lower():
                                        return c
                                    r = _sub(c, d + 1)
                                    if r:
                                        return r
                            except Exception as _e:
                                _record_swallow(_e, "omni_domain")
                            return None
                        hit = _sub(w)
                        if hit:
                            b = hit.BoundingRectangle
                            return {"text": hit.Name, "x": b.left, "y": b.top,
                                    "w": b.right - b.left, "h": b.bottom - b.top,
                                    "type": hit.ControlTypeName.replace("Control", "")}
                    except Exception:
                        continue
            except Exception as _e:
                _record_swallow(_e, "omni_domain")
            if fast:
                return None  # ⛔ 2026-08-13 打磨: 快速模式不做全树遍历(未命中25s拖爆wait_text超时)
            # 方案B: 全树遍历 (兜底, 慢)
            found = {"_uia": None}

            def _walk(ctrl, depth=0):
                if depth > 12 or found["_uia"]:
                    return
                try:
                    name = ctrl.Name
                    if name and text.lower() in str(name).lower():
                        r = ctrl.BoundingRectangle
                        found["_uia"] = {"text": name, "x": r.left, "y": r.top,
                                         "w": r.right - r.left, "h": r.bottom - r.top,
                                         "type": ctrl.ControlTypeName.replace("Control", "")}
                        return
                    for child in ctrl.GetChildren():
                        _walk(child, depth + 1)
                except Exception as _e:
                    _record_swallow(_e, "omni_domain")
            _walk(root)
            if found["_uia"]:
                f = found["_uia"]
                return {"text": f["text"], "x": f["x"], "y": f["y"],
                        "w": f["w"], "h": f["h"], "type": f["type"]}
            return None

    def trace_source(self, x: int, y: int):
        try:
            import win32gui, win32process
            hwnd = win32gui.WindowFromPoint((x, y))
            if not hwnd: return refusal("action_failed", "无法定位窗口", ())
            title = win32gui.GetWindowText(hwnd); _, pid = win32process.GetWindowThreadProcessId(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            try: import psutil; proc_name = psutil.Process(pid).name()
            except Exception: proc_name = f"pid={pid}"  # 容错: psutil 进程信息不可用降级
            cap = _screen_capture({"x": max(0,x-50), "y": max(0,y-15), "w": 100, "h": 30})
            return {"ok": True, "x": x, "y": y, "window": {"title": title[:100], "pid": pid, "process": proc_name, "rect": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]}}, "surrounding_kb": cap.get("image_kb", 0)}
        except ImportError: return refusal("action_failed", "win32 API 不可用", ())

    def trace_text(self, text: str):
        r = self.find_text(text)
        if not r.get("found"): return refusal("text_not_found", f"未找到 '{text}'", ("text",))
        trace = self.trace_source(r["x"], r["y"]); trace["text"] = text; trace["position"] = (r["x"], r["y"])
        return trace

    def trace_window_chain(self, target: str):
        win = _find_window(target)
        if not win: return refusal("window_not_found", f"未找到窗口: {target}", ("window",))
        try:
            import psutil; proc = psutil.Process(win["pid"])
            parents = []; p = proc
            for _ in range(5):
                try: parent = p.parent()
                except Exception: break  # 容错: 父进程查询失败终止链
                if parent: parents.append({"pid": parent.pid, "name": parent.name()}); p = parent
                else: break
            children = [{"pid": c.pid, "name": c.name()} for c in proc.children(recursive=False)]
            return {"ok": True, "window": win["title"], "process": {"pid": win["pid"], "name": proc.name()}, "parent_chain": parents, "children": children}
        except ImportError: return refusal("dependency_unavailable", "psutil 不可用", ("psutil",))

    def grab_pixel(self, x: int, y: int):
        import pyautogui
        try: c = pyautogui.pixel(x, y); return {"ok": True, "x": x, "y": y, "rgb": list(c)}
        except Exception as e: return refusal("action_failed", str(e)[:100], ())

    def grab_region(self, x: int, y: int, w: int, h: int):
        return _screen_capture({"x": x, "y": y, "w": w, "h": h})

    def extract_ui_elements(self, scope="active"):
        """提取UI元素契约 — 可点击控件清单(按钮/输入框/链接) + 坐标, 供大脑决策后点击。
        scope: "active"=活动窗口(快) | "full"=全屏(慢)"""
        try:
            import uiautomation as _uia
            with _uia.UIAutomationInitializerInThread():
                elements = []
                seen = set()
                INTEREST = ("ButtonControl", "EditControl", "HyperlinkControl",
                            "CheckBoxControl", "ComboBoxControl", "ListItemControl",
                            "TabItemControl", "MenuItemControl")
                def _walk(ctrl, depth=0):
                    if depth > 8 or len(elements) > 200:
                        return
                    try:
                        if ctrl.IsOffscreen:
                            return
                        ctype = ctrl.ControlTypeName
                        name = ctrl.Name
                        if ctype in INTEREST and name and name.strip():
                            key = f"{ctype}:{name}"
                            if key not in seen:
                                seen.add(key)
                                r = ctrl.BoundingRectangle
                                elements.append({"type": ctype.replace("Control", ""),
                                                 "text": name.strip()[:100],
                                                 "x": r.left, "y": r.top,
                                                 "w": r.right - r.left, "h": r.bottom - r.top})
                        for child in ctrl.GetChildren():
                            _walk(child, depth + 1)
                    except Exception as _e:
                        _record_swallow(_e, "omni_domain")
                if scope == "active":
                    win = _uia.GetForegroundControl()
                    if win:
                        _walk(win, 0)
                else:
                    root = _uia.GetRootControl()
                    for win in root.GetChildren():
                        try:
                            for child in win.GetChildren():
                                _walk(child, 0)
                        except Exception:
                            continue
                result = {"ok": True, "method": "uia", "scope": scope,
                           "elements": elements[:200],
                           "count": len(elements),
                           "contract": chr(10).join(f"[{e['type']}] {e['text']} @({e['x']},{e['y']})" for e in elements[:100])}
                # ⛔ 2026-08-07 打磨: UI元素坐标契约穿透 → 大脑拿到可点击控件清单
                try:
                    from .brain.tentacle_transmission import transmit as _tx
                    _tx({"elements": result.get("elements", [])[:40],
                         "count": result.get("count", 0), "scope": scope, "ok": True},
                        source="omni_tentacle.extract_ui_elements", channel="visual",
                        priority="high")
                except Exception as _e:
                    _record_swallow(_e, "omni_domain")
                return result
        except Exception as e:
            return refusal("action_failed", f"UI元素提取失败: {str(e)[:100]}", ())

    def grab_table(self, x=0, y=0, w=800, h=600):
        """提取屏幕区域表格数据 — read_text坐标文本按行聚合"""
        r = self.read_text({"x": x, "y": y, "w": w, "h": h})
        if not r.get("ok"):
            return r
        blocks = r.get("text_blocks", [])
        rows = {}
        for b in blocks:
            yk = round(b.get("y", 0) / 10) * 10
            rows.setdefault(yk, []).append(b)
        table = []
        for yk in sorted(rows.keys()):
            row_blocks = sorted(rows[yk], key=lambda b: b.get("x", 0))
            table.append([b["text"] for b in row_blocks])
        return {"ok": True, "method": "uia", "rows": len(table), "table": table[:50]}

    def grab_value(self, label):
        """找标签旁边的值 — 如 grab_value('余额') 返回余额旁的数值"""
        r = self.read_text()
        if not r.get("ok"):
            return r
        blocks = r.get("text_blocks", [])
        for b in blocks:
            if label.lower() in b["text"].lower():
                by = b.get("y", 0)
                candidates = []
                for b2 in blocks:
                    if abs(b2.get("y", 0) - by) < 15 and b2.get("x", 0) >= b.get("x", 0) and b2 is not b:
                        candidates.append(b2["text"])
                if candidates:
                    return {"ok": True, "label": label, "value": candidates[0],
                            "all_candidates": candidates[:5]}
                return {"ok": True, "label": label, "value": b["text"]}
        return refusal("label_not_found", f"未找到标签: {label}", ("label",))
