# gbt-capability: subprocess, dynamic-import, ctypes, base64
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
# window 域 mixin — 拆分自 omni_tentacle (自动生成, 2026-08-10)
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
except Exception:
    pass


class OmniWindowMixin:
    """window 域能力 — 16 方法"""

    def detect_dialog(self):
        """检测弹窗/对话框 — 仅认可对话框窗口内的按钮(排除普通窗口标题栏/内容误报)

        ⛔ 2026-08-12 v2: 深度8→5 + 节点预算300 + 命中即返 — 3218节点5.2s→数百节点亚秒
        ⛔ 2026-08-13 v3: 修复误报 — 此前全桌面扫按钮, Trae/Telegram/微信/Chrome 的
           "关闭" 被误判为弹窗(dismiss_dialog 曾差点点掉 IDE 关闭按钮)。
           判定: 按钮必须位于 对话框类窗口(#32770/DialogControl) 或 小窗口(高≤400) 内,
           且不在窗口标题栏区(顶部60px), 窗口/按钮必须屏上可见。
        """
        dialog_buttons = ["确定", "取消", "是", "否", "重试", "忽略", "中止",
                         "OK", "Cancel", "Yes", "No", "Retry", "Ignore", "Abort",
                         "关闭", "Close", "应用", "Apply"]
        _priority = ["确定", "ok", "是", "yes", "取消", "cancel", "否", "no",
                     "重试", "retry", "忽略", "ignore", "中止", "abort",
                     "关闭", "close", "应用", "apply"]
        _need = set(b.lower() for b in dialog_buttons)
        _found = {}
        try:
            import ctypes as _ct
            _u32 = _ct.windll.user32
            _sw, _sh = _u32.GetSystemMetrics(0), _u32.GetSystemMetrics(1)
        except Exception:
            _sw = _sh = 4000
        def _on_screen(x, y):
            return 0 <= x <= _sw and 0 <= y <= _sh
        try:
            import uiautomation as _uia
            with _uia.UIAutomationInitializerInThread():
                root = _uia.GetRootControl()
                for w in root.GetChildren():
                    if not _need:
                        break
                    try:
                        wname = (w.Name or "").strip()
                        if not wname or "运行窗口" in wname:
                            continue
                        wb = w.BoundingRectangle
                        wh = wb.bottom - wb.top
                        # 窗口离屏(最小化/隐藏) → 跳过
                        if wb.right <= wb.left or wb.bottom <= wb.top:
                            continue
                        if not _on_screen((wb.left + wb.right) / 2, (wb.top + wb.bottom) / 2):
                            continue
                        # 仅认可: 对话框类窗口(#32770/Dialog) 或 小窗口(高≤400 弹窗/气泡)
                        cls = (w.ClassName or "")
                        ctype = (w.ControlTypeName or "").lower()
                        if cls != "#32770" and "dialog" not in ctype and wh > 400:
                            continue
                        _budget = [120]
                        def _probe(h, d=0):
                            if d > 5 or _budget[0] <= 0 or not _need:
                                return
                            try:
                                for c in h.GetChildren():
                                    if _budget[0] <= 0 or not _need:
                                        return
                                    _budget[0] -= 1
                                    n = (c.Name or "").strip()
                                    nl = n.lower()
                                    if nl in _need and nl not in _found:
                                        try:
                                            cb = c.BoundingRectangle
                                            if cb.right <= cb.left or cb.bottom <= cb.top:
                                                continue
                                            # 标题栏区按钮(窗口高>150 且 按钮中心距顶<60) → 跳过
                                            if wh > 150 and (cb.top + cb.bottom) / 2 - wb.top < 60:
                                                continue
                                            if not _on_screen((cb.left + cb.right) / 2, (cb.top + cb.bottom) / 2):
                                                continue
                                            _found[nl] = {"name": n, "ctrl": c}
                                            _need.discard(nl)
                                        except Exception: pass  # 容错: 非关键路径
                                    _probe(c, d + 1)
                            except Exception: pass  # 容错: 非关键路径
                        _probe(w)
                    except Exception:
                        continue
        except Exception:
            pass
        if _found:
            # 优先级选按钮: 确定/OK > 是/Yes > 取消/Cancel > 关闭/Close
            btn_nl = min(_found.keys(),
                         key=lambda k: _priority.index(k) if k in _priority else 99)
            _entry = _found[btn_nl]
            try:
                _b = _entry["ctrl"].BoundingRectangle
                return {"ok": True, "dialog_detected": True,
                        "button": _entry["name"], "position": (_b.left, _b.top)}
            except Exception:
                return {"ok": True, "dialog_detected": True, "button": _entry["name"]}
        return {"ok": True, "dialog_detected": False}

    def dismiss_dialog(self, button: str = "确定"):
        """关闭弹窗 — 先确认弹窗存在(防误点), 点击指定按钮; ESC兜底后真实验证是否消失

        ⛔ 2026-08-13 打磨: 无弹窗时幂等返回 ok(不再因误报ESC失败), 且避免无谓的慢速find_text
        """
        d = self.detect_dialog()
        if not d.get("dialog_detected"):
            return {"ok": True, "dismissed_with": None, "note": "无弹窗, 幂等返回"}
        target = button if button else d.get("button")
        r = self.click_text(target)
        if r.get("ok"):
            return {"ok": True, "dismissed_with": target}
        # 试试 ESC
        _keyboard_press("escape")
        # ⛔ 2026-08-04 真实执行: ESC后验证弹窗确已消失 — 此前无条件声称已关闭(假成功)
        try:
            gone = not self.detect_dialog().get("dialog_detected", False)
        except Exception:
            gone = False
        if gone:
            return {"ok": True, "dismissed_with": "ESC (验证已关闭)"}
        return {"ok": False, "dismissed_with": "ESC",
                "error": "ESC后弹窗仍在, 未能关闭"}

    def handle_any_dialog(self):
        """自动处理任何弹窗 — 检测→点击确定/关闭"""
        d = self.detect_dialog()
        if d.get("dialog_detected"):
            return self.dismiss_dialog(d["button"])
        return {"ok": True, "dialog_detected": False, "note": "无弹窗"}

    def scroll_to_bottom(self, max_scrolls: int = 30):
        """滚到底"""
        for i in range(max_scrolls):
            _mouse_scroll(-10)
            time.sleep(0.05)
        return {"ok": True, "scrolled": max_scrolls}

    def scroll_to_top(self, max_scrolls: int = 30):
        """滚到顶"""
        for i in range(max_scrolls):
            _mouse_scroll(10)
            time.sleep(0.05)
        return {"ok": True, "scrolled": max_scrolls}

    def scroll_find(self, text: str, max_scrolls: int = 30, direction: str = "down"):
        """边滚边找 — 滚动 + 每步查找, 找到即返回坐标 (滚动域第3方法)

        ⛔ 2026-08-13 修复: 拆分时丢失, 契约(AGENTS/manifest/自动化邻域)仍在引用。
        direction: down=向下滚找 | up=向上滚找
        """
        _step = -10 if direction == "down" else 10
        for i in range(max_scrolls):
            try:
                # ⛔ 2026-08-13 打磨: 快查模式 — 全树+视觉兜底47s/次, 滚动步进会拖成23分钟
                r = self.find_text(text, fast=True)
                if r.get("found"):
                    return {"ok": True, "found": True, "text": text,
                            "x": r["x"], "y": r["y"], "scrolled": i,
                            "direction": direction, "method": r.get("method", "?")}
            except Exception: pass  # 容错: 单步查找失败继续滚
            _mouse_scroll(_step)
            time.sleep(0.1)
        return {"ok": False, "found": False,
                "error": f"滚动{max_scrolls}次未找到 '{text}'", "scrolled": max_scrolls}

    @_etiology("omni_window", "wait_window")
    def wait_window(self, target: str, timeout: float = 30):
        end = time.time() + timeout
        while time.time() < end:
            win = _find_window(target)
            if win: return {"ok": True, "window": win["title"][:100], "elapsed": round(timeout - (end - time.time()), 1)}
            time.sleep(0.5)
        return {"ok": False, "error": f"超时: {target}", "timeout": timeout}

    @_etiology("omni_window", "wait_window_gone")
    def wait_window_gone(self, target: str, timeout: float = 30):
        end = time.time() + timeout
        while time.time() < end:
            if not _find_window(target): return {"ok": True, "window_gone": target, "elapsed": round(timeout - (end - time.time()), 1)}
            time.sleep(0.5)
        return {"ok": False, "error": f"窗口仍在: {target}", "timeout": timeout}

    def wait_stable(self, interval: float = 0.5, stable_frames: int = 3):
        import hashlib, base64 as _b64
        hashes = []
        for _ in range(stable_frames + 2):
            cap = _screen_capture(); hashes.append(hashlib.sha256(_b64.b64decode(cap["image_base64"])).hexdigest()); time.sleep(interval)
        last = hashes[-stable_frames:]; stable = len(set(last)) == 1
        return {"ok": True, "stable": stable, "elapsed": round((stable_frames+2)*interval, 1)}

    def chain(self, actions: list):
        log = []
        for i, act in enumerate(actions):
            action_name = act.get("action", "")
            if not hasattr(self, action_name):
                log.append({"step": i, "ok": False, "error": f"未知: {action_name}"}); break
            kwargs = {k: v for k, v in act.items() if k != "action" and not k.startswith("_")}
            retries = act.get("_retries", 0) + 1
            for attempt in range(retries):
                try:
                    result = getattr(self, action_name)(**kwargs)
                    ok = result.get("ok", False) or result.get("found", False)
                    log.append({"step": i, "action": action_name, "ok": ok, "attempt": attempt+1})
                    if ok: break
                    if attempt < retries-1: time.sleep(0.5)
                except Exception as e:
                    log.append({"step": i, "action": action_name, "ok": False, "error": str(e)[:100]})
                    if attempt < retries-1: time.sleep(0.5)
            if not log[-1]["ok"]: break
        success = all(s.get("ok", False) for s in log if "ok" in s)
        return {"ok": success, "steps": len(actions), "completed": sum(1 for s in log if s.get("ok")), "log": log}

    def get_log(self, last_n: int = 20):
        log = getattr(self, '_action_log', []); return {"ok": True, "total": len(log), "recent": log[-last_n:]}

    def clear_log(self): self._action_log = []; return {"ok": True}

    def export_data(self, data: dict, filepath: str = None, format: str = "json"):
        if filepath is None: filepath = str(Path.home() / "Desktop" / f"grab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}")
        # ⛔ 2026-08-13 打磨: 全量走镜像出品 — v5.5 gatekeeper 全局写保护拦截一切非
        #    publish 写入(含项目外), 旧"项目外直写"分支已死且裸抛 PermissionError。
        _fp_export = Path(filepath)
        from .brain import gatekeeper as _gk_exp
        _content_exp = json.dumps(data, ensure_ascii=False, indent=2)
        if format == "csv":
            import csv, io
            _buf = io.StringIO()
            writer = csv.writer(_buf)
            for row in data.get("table", data.get("rows", [])):
                writer.writerow(row)
            _content_exp = _buf.getvalue()
        elif format == "txt":
            _content_exp = str(data)
        _res_exp = _gk_exp.publish(str(_fp_export), _content_exp, "omni_tentacle_export")
        if not _res_exp.get("ok"):
            return refusal("rejected_by_pipeline", f"导出被管线拒绝: {_res_exp.get('error','?')[:150]}", ())
        return {"ok": True, "filepath": filepath, "format": format, "channel": "mirror_pipeline"}

    def monitor(self, triggers: list, duration: float = 0, interval: float = 0.3):
        """实时监控 — 持续盯屏，触发条件满足即刻执行动作
        
        triggers: [{"on": "text_appear", "text": "确定", "action": "click_text", "text": "确定"},
                   {"on": "dialog", "action": "dismiss_dialog", "button": "确定"},
                   {"on": "window_open", "target": "微信", "action": "focus_window", "target": "微信"},
                   {"on": "text_disappear", "text": "加载中...", "action": "type", "text": "done"}]
        
        duration: 0=无限监控, >0=秒数
        interval: 检测间隔(秒)
        """
        triggered = []
        start = time.time()
        
        while True:
            if duration > 0 and time.time() - start > duration:
                break
            
            for i, t in enumerate(triggers):
                if i in [x["index"] for x in triggered]:
                    continue  # 已触发过，跳过
                
                event = t.get("on", "")
                matched = False
                
                if event == "text_appear":
                    # ⛔ 2026-08-13 打磨: 快查模式 — find_text全树+视觉兜底最长47s/次, 直接击穿duration控制
                    r = self.find_text(t.get("text", ""), fast=True)
                    matched = r.get("found", False)
                elif event == "text_disappear":
                    r = self.find_text(t.get("text", ""), fast=True)
                    matched = not r.get("found", True)
                elif event == "dialog":
                    r = self.detect_dialog()
                    matched = r.get("dialog_detected", False)
                elif event == "window_open":
                    win = _find_window(t.get("target", ""))
                    matched = win is not None
                elif event == "window_gone":
                    win = _find_window(t.get("target", ""))
                    matched = win is None
                elif event == "change":
                    r = self.screenshot_diff()
                    matched = r.get("changed", False)
                elif event == "stable":
                    r = self.wait_stable(0.3, 2)
                    matched = r.get("stable", False)
                
                if matched:
                    # 执行动作
                    action_name = t.get("action", "")
                    if hasattr(self, action_name):
                        _fn = getattr(self, action_name)
                        kwargs = {k: v for k, v in t.items() 
                                 if k not in ("on", "action", "index")}
                        # ⛔ 2026-08-13 打磨: 参数按动作签名过滤 — 此前把检测专用键
                        #    (如 window_open 的 target) 原样传给动作, 动作不认该键
                        #    (如 clipboard_write) → TypeError → 检测成功但动作失败
                        try:
                            import inspect as _insp
                            _params = _insp.signature(_fn).parameters
                            if not any(p.kind == _insp.Parameter.VAR_KEYWORD for p in _params.values()):
                                kwargs = {k: v for k, v in kwargs.items() if k in _params}
                        except Exception: pass  # 签名解析失败 → 原样传参
                        try:
                            result = _fn(**kwargs)
                            triggered.append({
                                "index": i, "event": event, "action": action_name,
                                "ok": result.get("ok", False), "ts": datetime.now().isoformat()
                            })
                        except TypeError:
                            # 签名仍不匹配(如动作无参数) → 降级无参调用
                            try:
                                result = _fn()
                                triggered.append({
                                    "index": i, "event": event, "action": action_name,
                                    "ok": result.get("ok", False), "ts": datetime.now().isoformat()
                                })
                            except Exception as e:
                                triggered.append({
                                    "index": i, "event": event, "action": action_name,
                                    "ok": False, "error": str(e)[:100]
                                })
                        except Exception as e:
                            triggered.append({
                                "index": i, "event": event, "action": action_name,
                                "ok": False, "error": str(e)[:100]
                            })
            
            time.sleep(interval)
        
        return {"ok": True, "monitored_s": round(time.time() - start, 1),
               "triggers_total": len(triggers), "triggered": len(triggered),
               "events": triggered}

    def on_dialog(self, action: str = "dismiss_dialog", **kwargs):
        """便捷: 弹窗出现时处理"""
        return self.on_text("确定", action, **kwargs)

    def on_text(self, text: str, action: str = "click_text", **kwargs):
        """便捷: 文字出现时执行动作 (监控域 on_text)

        ⛔ 2026-08-13 修复: 拆分时丢失, on_dialog 依赖此方法(此前直接 AttributeError)。
        text 作为动作的第一位置参数(click_text/focus_window/dismiss_dialog 均兼容),
        动作不需要 text 参数时(kwargs 提供)自动降级为仅 kwargs 调用。
        """
        _timeout = kwargs.pop("timeout", 30)
        try:
            r = self.wait_text(text, _timeout)
        except Exception as e:
            return refusal("action_failed", f"wait_text异常: {str(e)[:100]}", ())
        if not (r.get("ok") and r.get("status") == "appeared"):
            return {"ok": False, "status": "timeout", "error": r.get("error", "文字未出现")}
        if not hasattr(self, action):
            return refusal("action_failed", f"action不存在: {action}", ())
        try:
            res = getattr(self, action)(text, **kwargs)
            return {"ok": True, "text": text, "action": action,
                    "result": res.get("ok", False) if isinstance(res, dict) else bool(res)}
        except TypeError:
            try:
                res = getattr(self, action)(**kwargs)
                return {"ok": True, "text": text, "action": action,
                        "result": res.get("ok", False) if isinstance(res, dict) else bool(res)}
            except Exception as e:
                return refusal("action_failed", f"{action}(kwargs)异常: {str(e)[:100]}", ())
        except Exception as e:
            return refusal("action_failed", f"{action}异常: {str(e)[:100]}", ())

    @_etiology("omni_window", "watch_and_click")
    def watch_and_click(self, text: str, timeout: float = 30):
        """监控+点击 — 等到文字出现立刻点击"""
        r = self.wait_text(text, timeout)
        if r.get("ok") and r.get("status") == "appeared":
            # ⛔ 2026-08-13 修复: wait_text返回键是position而非at — 此前文字一出现即KeyError
            _pos = r.get("position")
            if not _pos:
                return {"ok": False, "error": "wait_text 未返回坐标", "wait": r}
            _mouse_move(_pos[0], _pos[1])
            time.sleep(0.03)
            _mouse_click()
            return {"ok": True, "clicked": text, "at": _pos}
        return refusal("action_failed", f"未等到 '{text}'", ())

    def watch_sequence(self, sequence: list, timeout_per_step: float = 10):
        """监控序列 — 等待一系列文字依次出现"""
        results = []
        for text in sequence:
            r = self.wait_text(text, timeout_per_step)
            if not r.get("ok") or r.get("status") != "appeared":
                return {"ok": False, "error": f"序列中断于 '{text}'", "completed": results}
            results.append({"text": text, "at": r.get("position"), "elapsed": r.get("elapsed")})
        return {"ok": True, "sequence_completed": True, "steps": results}

    def watch_any(self, texts: list, timeout: float = 30):
        """监控任意 — 等待多个文字任一出现即返回 (监控域第5方法)

        ⛔ 2026-08-13 修复: 拆分时丢失, 契约(AGENTS监控6项)仍在引用。
        texts: 候选文字列表, 任一出现即命中。
        """
        import time as _t
        end = _t.time() + timeout
        while _t.time() < end:
            for tx in texts:
                try:
                    f = self._uia_find_fast(tx, fast=True)
                    if f:
                        return {"ok": True, "found": tx, "position": (f["x"], f["y"])}
                except Exception: pass  # 容错: 单文字快查失败继续
            _t.sleep(0.5)
        return refusal("timeout", f"超时({timeout}s), 以下均未出现: {texts}", ())
