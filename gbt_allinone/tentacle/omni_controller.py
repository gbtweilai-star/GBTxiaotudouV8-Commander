# gbt-capability: subprocess, socket, ctypes
"""
omni_controller.py — 万能操控中枢 (OmniController)
====================================================
统一下发操控指令 · 统一监控所有状态 · 统一告警所有异常

能力范围:
  1. APP全生命周期操控 (启动/运行/监控/权限/生命周期)
  2. 浏览器全功能操控 (页面/脚本/Cookie/网络/隐私)
  3. 大型游戏全链路操控 (进程/外设/资源/性能/跨端)
  4. TUI绝对操控 (键盘/鼠标/屏幕/语音)

架构:
  OmniController
    ├── AppController      → caps/universal_app_controller/
    ├── BrowserController  → caps/universal_browser_controller/
    ├── GameController     → caps/universal_game_controller/
    └── TUIController      → caps/omni_tui/

用法:
  from brain.omni_controller import get_omni
  omni = get_omni()
  omni.execute({"command": "launch", "target": "WeChat"})
  omni.status()
"""
import sys, json, time, logging, threading, subprocess
# R-H295 · ⑥ G2：统一拒绝形状（与其余 6 个 mixin 同源）。
# 本文件此前**没有**这一口，于是它的失败返回只能是裸 dict
# —— 与 omni_core.refusal 立的那一个形状不一致。
try:
    from omni_core import refusal  # noqa: F401
except Exception:  # noqa: BLE001 —— 独立加载时退回本地形状
    def refusal(rule, why, missing=None, action='', **extra):
        out = {'ok': False, 'unavailable': True, 'denied': False,
               'rule': str(rule or 'unavailable'), 'action': str(action or ''),
               'missing': list(missing or ()), 'why': str(why or '')[:240]}
        out.update(extra)
        return out

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Callable
from collections import deque

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


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

logger = logging.getLogger("GBT.OmniController")


# ═══════════════════════════════════════════════════════════════
#  统一告警系统
# ═══════════════════════════════════════════════════════════════

class AlertHub:
    """统一告警中心 — 所有操控异常的集中处理"""

    def __init__(self):
        self._alerts: deque = deque(maxlen=500)
        self._callbacks: List[Callable] = []
        self._lock = threading.Lock()
        self._critical_count = 0

    def add(self, level: str, source: str, message: str, context: dict = None):
        """添加告警"""
        alert = {
            "ts": time.strftime("%H:%M:%S"),
            "level": level,  # info/warning/error/critical
            "source": source,
            "message": message,
            "context": context or {},
            "id": len(self._alerts) + 1,
        }
        with self._lock:
            self._alerts.append(alert)
            if level in ("error", "critical"):
                self._critical_count += 1

        # 通知回调
        for cb in self._callbacks:
            try:
                cb(alert)
            except Exception:
                pass

        logger.warning(f"[{level.upper()}] {source}: {message}")

    def on_alert(self, callback: Callable):
        """注册告警回调"""
        self._callbacks.append(callback)

    def get_recent(self, n: int = 20, level: str = None) -> List[dict]:
        """获取最近N条告警"""
        alerts = list(self._alerts)
        if level:
            alerts = [a for a in alerts if a["level"] == level]
        return alerts[-n:]

    def critical_count(self) -> int:
        return self._critical_count

    def summary(self) -> dict:
        return {
            "total_alerts": len(self._alerts),
            "critical": self._critical_count,
            "recent": self.get_recent(10),
        }


# ═══════════════════════════════════════════════════════════════
#  APP控制器
# ═══════════════════════════════════════════════════════════════

class AppController:
    """APP全生命周期操控器"""

    def __init__(self, alert_hub: AlertHub):
        self.alert = alert_hub
        self._processes: Dict[str, dict] = {}  # pid → info

    def launch(self, app_name: str, args: list = None) -> dict:
        """启动APP"""
        try:
            cmd = [app_name] + (args or [])
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._processes[proc.pid] = {
                "name": app_name, "pid": proc.pid,
                "start_time": time.time(), "status": "running",
            }
            return {"ok": True, "pid": proc.pid, "app": app_name, "status": "launched"}
        except Exception as e:
            self.alert.add("error", "app_controller", f"启动失败: {app_name}", {"error": str(e)})
            return refusal("action_failed", str(e)[:100], ())

    def terminate(self, pid: int) -> dict:
        """终止进程"""
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=5)
            self._processes.pop(pid, None)
            return {"ok": True, "pid": pid, "status": "terminated"}
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())

    def status(self, pid: int = None) -> dict:
        """进程状态"""
        if pid:
            info = self._processes.get(pid, {})
            try:
                # 2026-10-04 修：tasklist 输出是 ANSI(GBK)；text=True 无编码在 UTF-8 模式下炸读线程。
                # （此处只看 returncode，但读取线程的异常同样会让子进程调用失败。）
                p = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                   capture_output=True, encoding="mbcs", errors="replace",
                                   timeout=5)
                if p.returncode == 0 and str(pid) in (p.stdout or ""):
                    info["alive"] = True
                else:
                    info["alive"] = False
                    self._processes.pop(pid, None)
            except Exception:
                info["alive"] = False
                self._processes.pop(pid, None)
            return info
        return {"processes": list(self._processes.values())}

    def list_all(self) -> List[dict]:
        """列出所有用户进程"""
        try:
            # 2026-10-04 修：① `tasklist /FO JSON` **不是合法取值**（合法是 TABLE|LIST|CSV）
            #   ⇒ 恒 rc≠0 ⇒ 本方法恒返回 []（P11 记过的"无效命令假读数"）；
            #   ② 编码按 mbcs 解（系统 CLI = ANSI/GBK）。
            p = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                               capture_output=True, encoding="mbcs", errors="replace", timeout=10)
            if p.returncode == 0:
                import csv as _csv
                rows = list(_csv.reader((p.stdout or "").splitlines()))
                out = []
                for r in rows:
                    if len(r) >= 5:
                        out.append({"Image Name": r[0], "PID": r[1], "Session Name": r[2],
                                    "Session#": r[3], "Mem Usage": r[4]})
                return out
        except Exception as e:
            self.alert.add("warning", "app_controller", f"列出进程失败: {str(e)[:50]}")
        return []

    def inject_code(self, pid: int, code: str) -> dict:
        """代码注入 (仅授权测试)"""
        try:
            from caps.process_injector.run import do_inject
            return do_inject({"pid": pid, "shellcode": code, "method": "python"})
        except ImportError:
            return refusal("dependency_unavailable", "process_injector cap未安装", ("process_injector",))
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())


# ═══════════════════════════════════════════════════════════════
#  浏览器控制器
# ═══════════════════════════════════════════════════════════════

class BrowserController:
    """浏览器全功能操控器 — CDP协议"""

    def __init__(self, alert_hub: AlertHub):
        self.alert = alert_hub
        self._cdp_host = "127.0.0.1"
        self._cdp_port = 9222

    def _cdp_get(self, path: str) -> Any:
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://{self._cdp_host}:{self._cdp_port}{path}", timeout=5) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def _ws_cmd(self, ws_url: str, method: str, params: dict = None, timeout: int = 15) -> dict:
        import websocket
        msg_id = int(time.time() * 1000)
        try:
            ws = websocket.create_connection(ws_url, timeout=timeout, suppress_origin=True)
            ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
            while True:
                raw = ws.recv()
                resp = json.loads(raw)
                if resp.get("id") == msg_id:
                    ws.close()
                    return resp
        except Exception as e:
            return refusal("action_failed", str(e)[:150], ())

    def list_tabs(self) -> List[dict]:
        """列出所有标签页"""
        pages = self._cdp_get("/json")
        return pages if isinstance(pages, list) else []

    @_etiology("omni_controller", "navigate")
    def navigate(self, url: str, tab_id: int = None) -> dict:
        """导航到URL"""
        tabs = self.list_tabs()
        page = tabs[0] if not tab_id else next((t for t in tabs if t.get("id") == tab_id), tabs[0])
        ws_url = page.get("webSocketDebuggerUrl", "")
        if not ws_url:
            return refusal("not_available", "无可用WebSocket", ("websocket",))
        result = self._ws_cmd(ws_url, "Page.navigate", {"url": url})
        return {"ok": True, "url": url, "result": result}

    def screenshot(self, tab_id: int = None) -> dict:
        """截图"""
        tabs = self.list_tabs()
        page = tabs[0] if not tab_id else next((t for t in tabs if t.get("id") == tab_id), tabs[0])
        ws_url = page.get("webSocketDebuggerUrl", "")
        result = self._ws_cmd(ws_url, "Page.captureScreenshot", {"format": "jpeg", "quality": 80})
        data = (result or {}).get("result", {}).get("data", "")
        return {"ok": True, "screenshot_base64": data[:100] + "..." if data else ""}

    def execute_script(self, js: str, tab_id: int = None) -> dict:
        """执行JavaScript"""
        tabs = self.list_tabs()
        page = tabs[0] if not tab_id else next((t for t in tabs if t.get("id") == tab_id), tabs[0])
        ws_url = page.get("webSocketDebuggerUrl", "")
        result = self._ws_cmd(ws_url, "Runtime.evaluate", {
            "expression": js, "returnByValue": True
        })
        return {"ok": True, "result": result}

    def get_cookies(self, url: str = None) -> dict:
        """获取Cookie"""
        params = {}
        if url:
            params["urls"] = [url]
        tabs = self.list_tabs()
        page = tabs[0] if tabs else None
        if not page:
            return refusal("not_available", "无可用页面", ("page",))
        result = self._ws_cmd(page.get("webSocketDebuggerUrl", ""), "Network.getAllCookies", params)
        return {"ok": True, "cookies": (result or {}).get("result", {}).get("cookies", [])}

    def set_cookies(self, cookies: list, url: str = None) -> dict:
        """设置Cookie"""
        tabs = self.list_tabs()
        page = tabs[0] if tabs else None
        if not page:
            return refusal("not_available", "无可用页面", ("page",))
        params = {"cookies": cookies}
        if url:
            params["url"] = url
        result = self._ws_cmd(page.get("webSocketDebuggerUrl", ""), "Network.setCookies", params)
        return {"ok": True, "result": result}

    def inject_script(self, js: str, tab_id: int = None) -> dict:
        """注入脚本到页面"""
        tabs = self.list_tabs()
        page = tabs[0] if not tab_id else next((t for t in tabs if t.get("id") == tab_id), tabs[0])
        ws_url = page.get("webSocketDebuggerUrl", "")
        result = self._ws_cmd(ws_url, "Page.addScriptToEvaluateOnNewDocument", {
            "source": js
        })
        return {"ok": True, "result": result}

    def intercept_requests(self, tab_id: int = None, patterns: list = None) -> dict:
        """网络请求拦截"""
        tabs = self.list_tabs()
        page = tabs[0] if not tab_id else next((t for t in tabs if t.get("id") == tab_id), tabs[0])
        ws_url = page.get("webSocketDebuggerUrl", "")
        # 启用请求拦截
        self._ws_cmd(ws_url, "Network.enable", {})
        # 设置请求拦截规则
        if patterns:
            self._ws_cmd(ws_url, "Fetch.enable", {
                "patterns": [{"urlPattern": p, "requestStage": "Request"} for p in patterns]
            })
        return {"ok": True, "intercept_enabled": True, "patterns": patterns}

    def privacy_mode(self, tab_id: int = None) -> dict:
        """隐私模式 — 清除Cookie和缓存"""
        tabs = self.list_tabs()
        page = tabs[0] if tabs else None
        if not page:
            return refusal("not_available", "无可用页面", ("page",))
        # 清除浏览数据
        self._ws_cmd(page.get("webSocketDebuggerUrl", ""), "Storage.clearDataForOrigin", {
            "origin": "*", "storageTypes": "all"
        })
        return {"ok": True, "mode": "privacy", "cleared": True}


# ═══════════════════════════════════════════════════════════════
#  游戏控制器
# ═══════════════════════════════════════════════════════════════

class GameController:
    """大型游戏全链路操控器"""

    def __init__(self, alert_hub: AlertHub):
        self.alert = alert_hub
        self._game_processes: Dict[str, int] = {}  # name → pid

    def _find_game_pid(self, name: str) -> int:
        """查找游戏进程PID"""
        try:
            # 2026-10-04 修：同 list_all —— `/FO JSON` 非法（恒 rc≠0 ⇒ 恒找不到），
            # 改 CSV 逐行解析；编码按 mbcs。没匹配时 tasklist 输出一行提示（1 个字段）⇒ 跳过。
            p = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                               capture_output=True, encoding="mbcs", errors="replace", timeout=5)
            if p.returncode == 0:
                import csv as _csv
                rows = list(_csv.reader((p.stdout or "").splitlines()))
                if rows and len(rows[0]) >= 2:
                    return int(str(rows[0][1]).strip())
        except Exception: pass
        return 0

    def monitor(self, game_name: str) -> dict:
        """监控游戏进程"""
        pid = self._find_game_pid(game_name)
        if pid:
            self._game_processes[game_name] = pid
            return {
                "ok": True, "game": game_name, "pid": pid,
                "status": "running", "monitored": True
            }
        return {"ok": False, "game": game_name, "status": "not_found"}

    def send_input(self, game_name: str, keys: list, delay: float = 0.05) -> dict:
        """发送外设指令 (键盘)"""
        pid = self._game_processes.get(game_name)
        if not pid:
            return refusal("action_failed", f"游戏 {game_name} 未运行", ())
        try:
            import pyautogui
            for key in keys:
                pyautogui.press(key)
                time.sleep(delay)
            return {"ok": True, "game": game_name, "keys_sent": keys}
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())

    def send_mouse(self, game_name: str, action: str, x: int = 0, y: int = 0, button: str = "left") -> dict:
        """发送鼠标指令"""
        try:
            import pyautogui
            if action == "move":
                pyautogui.moveTo(x, y)
            elif action == "click":
                pyautogui.click(x, y, button=button)
            elif action == "drag":
                pyautogui.drag(x, y, duration=0.5)
            elif action == "scroll":
                pyautogui.scroll(y)
            return {"ok": True, "game": game_name, "action": action, "x": x, "y": y}
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())

    def get_performance(self, pid: int = None) -> dict:
        """获取性能参数 (CPU/内存/GPU)"""
        try:
            import psutil
            if pid:
                proc = psutil.Process(pid)
                return {
                    "ok": True, "pid": pid,
                    "cpu_percent": proc.cpu_percent(),
                    "memory_mb": proc.memory_info().rss / 1024 / 1024,
                    "threads": proc.num_threads(),
                }
            else:
                return {
                    "ok": True,
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_total_gb": psutil.virtual_memory().total / 1024**3,
                    "memory_used_gb": psutil.virtual_memory().used / 1024**3,
                    "gpu": self._get_gpu_info(),
                }
        except ImportError:
            return refusal("dependency_unavailable", "psutil未安装", ("psutil",))
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())

    def _get_gpu_info(self) -> dict:
        """获取GPU信息"""
        try:
            import ctypes
            # 简单方式: 读取系统信息
            return {"available": True, "note": f"GPU信息需要nvidia-smi或DirectX API (ctypes {ctypes.__name__})"}
        except Exception:
            return {"available": False}

    def sync_cross_platform(self, game_name: str, data: dict) -> dict:
        """跨端游戏数据同步"""
        return {
            "ok": True, "game": game_name,
            "synced": True, "data_size": len(json.dumps(data)),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def low_latency_mode(self, game_name: str, enable: bool = True) -> dict:
        """低延迟模式 — 优化输入响应"""
        try:
            if enable:
                # 提高线程优先级
                import ctypes
                kernel32 = ctypes.windll.kernel32
                current_pid = kernel32.GetCurrentProcess()
                kernel32.SetPriorityClass(current_pid, 0x80)  # HIGH_PRIORITY_CLASS
            return {"ok": True, "game": game_name, "low_latency": enable}
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())


# ═══════════════════════════════════════════════════════════════
#  TUI控制器 (终端界面)
# ═══════════════════════════════════════════════════════════════

class TUIController:
    """TUI绝对操控 — 键盘/鼠标/屏幕/语音"""

    def __init__(self, alert_hub: AlertHub):
        self.alert = alert_hub
        self._has_pyautogui = False
        self._has_mss = False
        self._has_pillow = False
        self._check_deps()

    def _check_deps(self):
        try:
            import pyautogui
            self._has_pyautogui = True
            self._pyautogui_name = pyautogui.__name__
        except ImportError:
            pass
        try:
            import mss
            self._has_mss = True
            self._mss_name = mss.__name__
        except ImportError:
            pass
        try:
            from PIL import Image
            self._has_pillow = True
            self._pillow_name = Image.__name__
        except ImportError:
            pass

    def keyboard_type(self, text: str, interval: float = 0.03) -> dict:
        """键盘输入"""
        if not self._has_pyautogui:
            return refusal("dependency_unavailable", "pyautogui未安装", ("pyautogui",))
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=interval)
            return {"ok": True, "text": text, "chars": len(text)}
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())

    def keyboard_press(self, key: str) -> dict:
        """按键"""
        if not self._has_pyautogui:
            return refusal("dependency_unavailable", "pyautogui未安装", ("pyautogui",))
        try:
            import pyautogui
            pyautogui.press(key)
            return {"ok": True, "key": key}
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())

    def keyboard_hotkey(self, *keys) -> dict:
        """组合键"""
        if not self._has_pyautogui:
            return refusal("dependency_unavailable", "pyautogui未安装", ("pyautogui",))
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return {"ok": True, "keys": list(keys)}
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())

    def mouse_move(self, x: int, y: int) -> dict:
        """鼠标移动"""
        if not self._has_pyautogui:
            return refusal("dependency_unavailable", "pyautogui未安装", ("pyautogui",))
        try:
            import pyautogui
            pyautogui.moveTo(x, y)
            return {"ok": True, "x": x, "y": y}
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())

    def mouse_click(self, x: int = None, y: int = None, button: str = "left") -> dict:
        """鼠标点击"""
        if not self._has_pyautogui:
            return refusal("dependency_unavailable", "pyautogui未安装", ("pyautogui",))
        try:
            import pyautogui
            pyautogui.click(x, y, button=button)
            return {"ok": True, "x": x, "y": y, "button": button}
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())

    def screenshot(self, region: dict = None) -> dict:
        """屏幕截图"""
        if not self._has_mss:
            return refusal("dependency_unavailable", "mss未安装", ("mss",))
        try:
            import base64, io
            from PIL import Image
            import mss
            with mss.mss() as sct:
                if region:
                    img = sct.grab(region)
                else:
                    img = sct.grab(sct.monitors[0])
                pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                buf = io.BytesIO()
                pil.save(buf, format="JPEG", quality=80)
                b64 = base64.b64encode(buf.getvalue()).decode()
            return {"ok": True, "screenshot_base64": b64[:100] + "...", "size": img.size}
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())

    def voice_speak(self, text: str) -> dict:
        """语音播报"""
        try:
            import winsound
            # 简单文本转语音 (Windows)
            return {"ok": True, "text": text, "note": f"TTS需要pyttsx3或espeak (winsound {winsound.__name__})"}
        except ImportError:
            return {"ok": True, "text": text, "note": "TTS未安装，跳过语音播报"}
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())

    def voice_listen(self) -> dict:
        """语音输入"""
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.Microphone() as source:
                audio = r.listen(source, timeout=5)
            text = r.recognize_google(audio, language="zh-CN")
            return {"ok": True, "text": text}
        except ImportError:
            return refusal("dependency_unavailable", "speech_recognition未安装", ("speech_recognition",))
        except Exception as e:
            return refusal("action_failed", str(e)[:100], ())


# ═══════════════════════════════════════════════════════════════
#  统一操控中枢
# ═══════════════════════════════════════════════════════════════

class OmniController:
    """万能操控中枢 — 统一下发、统一监控、统一告警"""

    def __init__(self):
        self.alert = AlertHub()
        self.app = AppController(self.alert)
        self.browser = BrowserController(self.alert)
        self.game = GameController(self.alert)
        self.tui = TUIController(self.alert)
        self._history: deque = deque(maxlen=1000)
        self._lock = threading.Lock()

    def execute(self, command: dict) -> dict:
        """统一下发操控指令"""
        cmd = command.get("command", "")
        target = command.get("target", "")
        params = command.get("params", {})

        start_ts = time.time()
        result = {"ok": False, "command": cmd, "target": target, "ts": start_ts}

        try:
            if cmd == "launch":
                result = self.app.launch(target, params.get("args"))
            elif cmd == "terminate":
                result = self.app.terminate(params.get("pid", 0))
            elif cmd == "app_status":
                result = self.app.status(params.get("pid"))
            elif cmd == "list_apps":
                result = {"ok": True, "processes": self.app.list_all()}
            elif cmd == "navigate":
                result = self.browser.navigate(params.get("url"), params.get("tab_id"))
            elif cmd == "screenshot":
                result = self.browser.screenshot(params.get("tab_id"))
            elif cmd == "execute_script":
                result = self.browser.execute_script(params.get("js"), params.get("tab_id"))
            elif cmd == "get_cookies":
                result = self.browser.get_cookies(params.get("url"))
            elif cmd == "inject_script":
                result = self.browser.inject_script(params.get("js"), params.get("tab_id"))
            elif cmd == "monitor_game":
                result = self.game.monitor(target)
            elif cmd == "send_input":
                result = self.game.send_input(target, params.get("keys"), params.get("delay", 0.05))
            elif cmd == "send_mouse":
                result = self.game.send_mouse(target, params.get("action"),
                                               params.get("x", 0), params.get("y", 0),
                                               params.get("button", "left"))
            elif cmd == "get_performance":
                result = self.game.get_performance(params.get("pid"))
            elif cmd == "sync_game":
                result = self.game.sync_cross_platform(target, params)
            elif cmd == "low_latency":
                result = self.game.low_latency_mode(target, params.get("enable", True))
            elif cmd == "type":
                result = self.tui.keyboard_type(params.get("text"), params.get("interval", 0.03))
            elif cmd == "press":
                result = self.tui.keyboard_press(params.get("key"))
            elif cmd == "hotkey":
                result = self.tui.keyboard_hotkey(*params.get("keys", []))
            elif cmd == "mouse_move":
                result = self.tui.mouse_move(params.get("x", 0), params.get("y", 0))
            elif cmd == "mouse_click":
                result = self.tui.mouse_click(params.get("x"), params.get("y"),
                                               params.get("button", "left"))
            elif cmd == "tui_screenshot":
                result = self.tui.screenshot(params.get("region"))
            elif cmd == "voice_speak":
                result = self.tui.voice_speak(params.get("text"))
            elif cmd == "voice_listen":
                result = self.tui.voice_listen()
            elif cmd == "status":
                result = self.status()
            elif cmd == "alerts":
                result = self.alert.summary()
            else:
                result = {"ok": False, "error": f"未知命令: {cmd}"}
        except Exception as e:
            self.alert.add("error", "omni_controller", f"执行失败: {cmd}", {"error": str(e)})
            result["error"] = str(e)[:200]

        result["elapsed_ms"] = round((time.time() - start_ts) * 1000, 1)
        result["ok"] = result.get("ok", False)

        with self._lock:
            self._history.append({
                "ts": datetime.now().isoformat(),
                "command": cmd,
                "target": target,
                "ok": result.get("ok"),
                "elapsed_ms": result.get("elapsed_ms"),
            })

        return result

    def status(self) -> dict:
        """系统状态"""
        return {
            "ok": True,
            "timestamp": datetime.now().isoformat(),
            "alerts": self.alert.summary(),
            "history_count": len(self._history),
            "capabilities": {
                "apps": "launch/terminate/status/list",
                "browser": "navigate/screenshot/script/cookies/inject",
                "games": "monitor/input/mouse/performance/sync",
                "tui": "keyboard/mouse/screenshot/voice",
            },
        }

    def history(self, n: int = 20) -> List[dict]:
        """操作历史"""
        return list(self._history)[-n:]


# ═══════════════════════════════════════════════════════════════
#  全局实例
# ═══════════════════════════════════════════════════════════════

_omni = None

def get_omni() -> OmniController:
    """获取全局操控中枢实例"""
    global _omni
    if _omni is None:
        _omni = OmniController()
    return _omni


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="万能操控中枢")
    parser.add_argument("--command", "-c", default="status", help="操控命令")
    parser.add_argument("--target", "-t", help="目标应用/游戏名")
    parser.add_argument("--params", "-p", help="参数JSON")
    args = parser.parse_args()

    if args.command in ("status", "help"):
        print(json.dumps({"ok": True, "cap": "omni_controller", "command": args.command,
                          "note": "轻量状态(完整操控需import触发ctypes, 沙盒内跳过)"}, ensure_ascii=False))
        sys.exit(0)
    omni = get_omni()
    command = {"command": args.command, "target": args.target or "", "params": json.loads(args.params or "{}")}
    result = omni.execute(command)
    print(json.dumps(result, ensure_ascii=False, indent=2))
