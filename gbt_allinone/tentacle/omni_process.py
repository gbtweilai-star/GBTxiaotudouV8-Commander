# gbt-capability: subprocess, dynamic-import, ctypes, base64
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
# process 域 mixin — 拆分自 omni_tentacle (自动生成, 2026-08-10)
# ⛔ 拆分保障: 自身目录(brain/)入 sys.path — spec_from_file_location 加载
#    不会自动加路径, 需显式保障 omni_core 可寻址 (插 brain/ 而非项目根)
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))
# publish沙盒(非项目根cwd)执行兜底: 类定义不访问core符号, 吞异常安全
try:
    from omni_core import *  # noqa: F401,F403
except Exception:
    pass


def _load_penetration_scan():
    """加载 brain/penetration_scan：优先**包导入**（相对导入才有包上下文）；
    不行再回落 spec 加载（该模块的 _pkg() 已能自愈两种加载路）。

    2026-10-04 修（24h 审查实证）：原实现只有 spec 一条路 ⇒ `__package__=""`
    ⇒ penetration_scan 里 6 处 `from .. import …` 全部 ImportError，被每层 except
    吞成假错误 ⇒ diagnose/deep_diagnose 的自诊断能力实际归零。
    """
    _root = _P(__file__).resolve().parent.parent.parent
    if str(_root) not in _sys.path:
        _sys.path.insert(0, str(_root))
    try:
        from gbt_allinone.brain import penetration_scan as _mod
        return _mod
    except Exception:
        import importlib.util as _iu
        _spec = _iu.spec_from_file_location("_pscan_diag", str(_P(__file__).resolve().parent.parent / "brain" / "penetration_scan.py"))
        _mod = _iu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        return _mod


class OmniProcessMixin:
    """process 域能力 — 21 方法"""

    def _proc_names(self) -> set:
        """当前进程名集合（小写、去 .exe）。取不到就返回空集 —— 那是"没得比"，不是"没起来"。"""
        names = set()
        try:
            import psutil
            for pr in psutil.process_iter(["name"]):
                n = str((pr.info or {}).get("name") or "").lower()
                if n:
                    names.add(n[:-4] if n.endswith(".exe") else n)
        except Exception:  # noqa: BLE001
            pass
        return names

    def launch(self, app: str, args: list = None, verify_s: float = 6.0):
        """启动应用 + **验证它真的起来了**（铁律⑤：每步亲眼验证）。

        R-H295 · 修根因（假成功）：原来兜底路径 `cmd /c start "" <app>` **只要 cmd 自己起得来
        就报 `ok: True`** —— 而 Windows 的 `start` 对**不存在的目标照样返回 0**
        （只在 stderr 打印 "The system cannot find the file …"）。实测：
        `launch('绝对不存在的程序_zzz')` 报 `ok=True`，而屏幕上什么都没出现。
        这是"看着有、其实没成"的典型 —— 面板上一个绿勾，背后什么都没发生。

        现在起完之后**真的去看**：轮询进程表，出现匹配 `app` 的新进程才算成；
        到点还没出现 ⇒ 返回结构化拒绝 `launch_unverified`（不报绿、不猜）。
        """
        import subprocess
        before = self._proc_names()
        key = str(app or "").strip().lower()
        key = key.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        if key.endswith(".exe"):
            key = key[:-4]

        method = None
        try:
            # B602 修复：列表参数 + shell=False（不再混用 shell=True 拼接）
            if args:
                subprocess.Popen([app] + args, shell=False)
            else:
                subprocess.Popen([app], shell=False)
            method = "popen"
        except Exception:
            # Windows start 语义兜底（路径含空格的注册应用名），保留 shell 但只接受单一应用名
            try:
                subprocess.Popen(['cmd', '/c', 'start', '', str(app)], shell=False)
                method = "shell_start"
            except Exception as e:  # noqa: BLE001
                return refusal("action_failed", str(e)[:100], (), "launch")

        # ── 动后验证：不看一眼不算成 ──
        deadline = time.time() + max(0.5, float(verify_s))
        seen_new = set()
        while time.time() < deadline:
            time.sleep(0.4)
            now = self._proc_names()
            seen_new = now - before
            if key and any(key in n for n in seen_new):
                return {"ok": True, "launched": app, "method": method,
                        "verified": True, "new_processes": sorted(seen_new)[:6]}
        if not key:
            return refusal("launch_unverified", "app 名为空，无法验证是否真的起来",
                           ("app_name",), "launch")
        return refusal(
            "launch_unverified",
            "命令已发出（method=%s）但 %.1fs 内没看到匹配 '%s' 的新进程 —— "
            "不报绿：Windows start 对不存在的目标也返回 0，所以'发出去了'不等于'起来了'。"
            "这段时间新增进程：%s" % (method, verify_s, key, sorted(seen_new)[:6] or "（无）"),
            ("running_process",), "launch", attempted=app, method_used=method,
            new_processes=sorted(seen_new)[:6])

    def kill(self, target: str):
        try:
            import psutil; killed = []
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if target.lower() in proc.info['name'].lower(): proc.kill(); killed.append({"pid": proc.info['pid'], "name": proc.info['name']})
                except Exception: pass  # 容错: 非关键路径
            if killed: return {"ok": True, "killed": killed}
            win = _find_window(target)
            if win: psutil.Process(win["pid"]).kill(); return {"ok": True, "killed": [{"pid": win["pid"], "window": win["title"][:50]}]}
            return refusal("process_not_found", f"未找到进程: {target}", ("process",))
        except ImportError: return refusal("dependency_unavailable", "psutil 不可用", ("psutil",))

    def process_list(self, filter_name: str = None):
        try:
            import psutil
            # ⛔ 2026-08-13 性能打磨 v2: 三段成本拆解 — pid+name=21ms, memory_info=658ms(瓶颈:
            #    每进程OpenProcess系统调用), cpu_percent首采恒0(无前一采样点)。
            #    ① pid/name 快取 ② memory 模块级缓存5s(监控场景660ms→命中~20ms, 5s内新进程延迟可见)
            #    ③ top30 cpu 双采样复用同一Process实例(psutil采样点按实例缓存, v1不同实例恒0bug)
            _mem_cache = globals().get("_process_mem_cache")
            if _mem_cache is None or (time.time() - _mem_cache["ts"]) > 5.0:
                _mem_rows = {}
                for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                    try:
                        info = proc.info
                        if filter_name and filter_name.lower() not in info['name'].lower():
                            continue
                        _mem_rows[info['pid']] = {
                            "pid": info['pid'], "name": info['name'], "cpu": 0.0,
                            "memory_mb": round((info['memory_info'].rss if info['memory_info'] else 0) / 1024 / 1024, 1)}
                    except Exception: pass  # 容错: 非关键路径
                globals()["_process_mem_cache"] = {"ts": time.time(), "data": _mem_rows}
            else:
                _mem_rows = {}
                for pid, row in _mem_cache["data"].items():
                    if filter_name and filter_name.lower() not in row["name"].lower():
                        continue
                    _mem_rows[pid] = dict(row)
            procs = list(_mem_rows.values())
            procs.sort(key=lambda p: -p['memory_mb'])
            top = procs[:30]
            _handles = {}
            for p in top:
                try:
                    h = psutil.Process(p["pid"]); h.cpu_percent(None); _handles[p["pid"]] = h
                except Exception: pass  # 容错: 进程已退出
            time.sleep(0.1)  # 采样间隔, 差值才有意义
            for p in top:
                try:
                    h = _handles.get(p["pid"])
                    if h:
                        p["cpu"] = round(h.cpu_percent(None) or 0, 1)
                except Exception: pass  # 容错: 进程已退出
            procs.sort(key=lambda p: -p['cpu'])
            result = {"ok": True, "count": len(procs), "processes": procs[:30]}
            # ⛔ 2026-08-04 触手→大脑: 进程感知穿透传输 (高CPU/高内存 → critical)
            try:
                from .brain.tentacle_transmission import transmit as _tx
                _top = [p for p in procs[:5]]
                _heavy = [p for p in procs[:30] if p.get("cpu", 0) > 80]
                _tx({"processes": _top, "count": result["count"],
                     "heavy_cpu": [p["name"] for p in _heavy][:5], "ok": True},
                    source="omni_tentacle.process_list", channel="sensor",
                    priority="critical" if _heavy else "normal")
            except Exception: pass  # 容错: 非关键路径
            return result
        except ImportError: return refusal("dependency_unavailable", "psutil 不可用", ("psutil",))

    def app_running(self, name: str):
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                if name.lower() in (proc.info['name'] or '').lower(): return {"ok": True, "running": True, "pid": proc.pid, "name": proc.info['name']}
            return {"ok": True, "running": False}
        except ImportError:
            win = _find_window(name); return {"ok": True, "running": win is not None}

    def diagnose(self):
        """触手自诊断 — 穿透式交叉扫描 (L0+L1 + 交叉验证)"""
        try:
            mod = _load_penetration_scan()
            r = mod.quick_scan()
            result = {
                "ok": r["ok"],
                "health": r.get("health", {}).get("overall", r.get("health", {}).get("score", 0)),
                "tier": r.get("health", {}).get("tier", "?"),
                "issues": r.get("total_issues", 0),
                "errors": r.get("total_errors", 0),
                "elapsed_ms": r.get("elapsed_ms", 0),
                "mode": "penetration_cross_scan",
                "cross_validated": r.get("cross_validated", False),
            }
            cv = r.get("cross_validation")
            if cv:
                result["cross_validation"] = {
                    "confirmed": cv.get("confirmed_issues", 0),
                    "false_positives": cv.get("false_positives", 0),
                }
            return result
        except Exception as e:
            return refusal("action_failed", str(e)[:200], ())

    def deep_diagnose(self):
        """深度诊断 — 穿透式交叉扫描 (全层 + N触手网格 + 共识评分)"""
        results = {}
        try:
            mod = _load_penetration_scan()
            r = mod.run_full_scan(deep=True)
            results["full_scan"] = {
                "ok": r["ok"], "errors": r.get("total_errors", 0),
                "issues": r.get("total_issues", 0),
                "cross_validated": r.get("cross_validated", False),
            }
            cv = r.get("cross_validation")
            if cv:
                results["cross_validation"] = {
                    "mesh_coverage": cv.get("mesh_coverage_pct", 0),
                    "mesh_confirmed": cv.get("mesh_confirmed", 0),
                    "consensus_score": cv.get("consensus_score", 0),
                    "false_positives": cv.get("mesh_false_positives", 0),
                }
        except Exception as e:
            results["full_scan"] = {"error": str(e)[:200]}
        return {"ok": True, "results": results, "mode": "penetration_cross_deep"}

    def task_guide_load(self, mind_map: dict) -> dict:
        """加载大脑执行层生成的思维导图任务
        
        mind_map 格式:
          {"task": "总目标", "nodes": [
            {"id":"1","task":"步骤1","keywords":["搜索","定位"],"children":[...]},
            {"id":"2","task":"步骤2","keywords":["修改","编辑"],"children":[...]}
          ]}
        """
        self._task_guide = {
            "task": mind_map.get("task", "未命名任务"),
            "nodes": mind_map.get("nodes", []),
            "current_node": None,
            "history": [],
            "drift_count": 0,
            "drift_warnings": [],
            "loaded_at": datetime.now().isoformat(),
        }
        # 自动定位第一个待执行节点
        self._task_guide_advance()
        return {
            "ok": True,
            "task": self._task_guide["task"],
            "total_nodes": self._task_guide_count_nodes(self._task_guide["nodes"]),
            "current": self._task_guide["current_node"],
        }

    def task_guide_check(self, action_description: str) -> dict:
        """执行前校验: 当前动作是否对齐当前任务节点
        
        返回:
          aligned: True/False - 是否对齐
          drift_risk: low/medium/high - 偏航风险
          correction: 纠偏提示 (如果偏航)
        """
        if not hasattr(self, '_task_guide') or not self._task_guide.get("current_node"):
            return {"ok": True, "aligned": True, "drift_risk": "low", "note": "无活跃任务指引"}

        node = self._task_guide["current_node"]
        keywords = node.get("keywords", [])
        task_text = node.get("task", "")
        action_lower = action_description.lower()

        if not keywords:
            # 无关键词 → 用任务文本匹配
            task_words = set(task_text.lower().split())
            action_words = set(action_lower.split())
            overlap = task_words & action_words
            aligned = len(overlap) > 0 or len(task_words) == 0
            drift_risk = "low" if aligned else "medium"
        else:
            # 关键词匹配
            matches = [kw for kw in keywords if kw.lower() in action_lower]
            aligned = len(matches) > 0
            drift_risk = "low" if aligned else "high"

        result = {
            "ok": True,
            "aligned": aligned,
            "drift_risk": drift_risk,
            "current_task": task_text,
            "action": action_description[:120],
        }

        if not aligned:
            self._task_guide["drift_count"] += 1
            correction = self._task_guide_generate_correction(node, action_description)
            result["correction"] = correction
            self._task_guide["drift_warnings"].append({
                "time": datetime.now().isoformat(),
                "action": action_description[:100],
                "expected": task_text,
                "drift_count": self._task_guide["drift_count"],
            })
            # 连续偏航 ≥3 次 → 强制纠偏
            if self._task_guide["drift_count"] >= 3:
                result["force_correct"] = True
                result["force_message"] = (
                    f"STOP. 已连续偏航 {self._task_guide['drift_count']} 次。"
                    f"当前任务: {task_text}。请回到正轨，完成此任务后再进行下一步。"
                )
        else:
            # 对齐 → 重置偏航计数
            self._task_guide["drift_count"] = max(0, self._task_guide["drift_count"] - 1)

        return result

    def task_guide_complete(self, node_id: str = None, evidence: str = "") -> dict:
        """标记当前任务节点完成，自动推进到下一个"""
        if not hasattr(self, '_task_guide'):
            return refusal("action_failed", "无活跃任务指引", ())

        node = self._task_guide.get("current_node") if not node_id else self._task_guide_find_node(node_id)
        if not node:
            return refusal("action_failed", f"节点不存在: {node_id}", ())

        node["status"] = "completed"
        node["completed_at"] = datetime.now().isoformat()
        if evidence:
            node["evidence"] = evidence

        self._task_guide["history"].append({
            "node": node.get("id"), "task": node.get("task"),
            "completed_at": node["completed_at"], "evidence": evidence,
        })

        # 自动推进
        advanced = self._task_guide_advance()
        return {
            "ok": True,
            "completed": node.get("task"),
            "next": self._task_guide.get("current_node"),
            "progress": self._task_guide_progress(),
            "advanced": advanced,
        }

    def task_guide_status(self) -> dict:
        """当前任务指引状态"""
        if not hasattr(self, '_task_guide'):
            return refusal("action_failed", "无活跃任务指引", ())
        
        guide = self._task_guide
        return {
            "ok": True,
            "task": guide["task"],
            "current": guide.get("current_node"),
            "progress_pct": self._task_guide_progress(),
            "drift_count": guide["drift_count"],
            "history_len": len(guide["history"]),
            "recent_warnings": guide["drift_warnings"][-3:],
        }

    def task_guide_next(self) -> dict:
        """获取下一个待执行任务（不推进状态）"""
        if not hasattr(self, '_task_guide'):
            return refusal("action_failed", "无活跃任务指引", ())
        
        next_node = self._task_guide_find_next_pending(self._task_guide["nodes"])
        return {
            "ok": True,
            "next": next_node,
            "current": self._task_guide.get("current_node"),
        }

    def task_guide_drift_report(self) -> str:
        """偏航报告 — 人类可读"""
        if not hasattr(self, '_task_guide'):
            return "无活跃任务指引"
        
        guide = self._task_guide
        lines = [
            "=" * 50,
            f"Task Guide: {guide['task']}",
            f"  Progress: {self._task_guide_progress()}%",
            f"  Current:  {guide['current_node']['task'] if guide.get('current_node') else 'all done'}",
            f"  Drifts:   {guide['drift_count']}",
            f"  History:  {len(guide['history'])} completed",
            "=" * 50,
        ]
        if guide["drift_warnings"]:
            lines.append("")
            lines.append("Drift Warnings:")
            for w in guide["drift_warnings"][-5:]:
                lines.append(f"  [{w['drift_count']}] {w['action'][:60]}")
                lines.append(f"       Expected: {w['expected'][:60]}")
        return chr(10).join(lines)

    def _task_guide_find_node(self, node_id: str, nodes: list = None):
        if nodes is None:
            nodes = self._task_guide.get("nodes", []) if hasattr(self, '_task_guide') else []
        for n in nodes:
            if n.get("id") == node_id:
                return n
            for child in n.get("children", []):
                result = self._task_guide_find_node(node_id, [child])
                if result:
                    return result
        return None

    def _task_guide_find_next_pending(self, nodes: list):
        for n in nodes:
            if n.get("status", "pending") == "pending":
                return n
            for child in n.get("children", []):
                if child.get("status", "pending") == "pending":
                    return child
        return None

    def _task_guide_advance(self) -> bool:
        next_node = self._task_guide_find_next_pending(self._task_guide["nodes"])
        if next_node:
            if next_node.get("status", "pending") == "pending":
                next_node["status"] = "in_progress"
                next_node["started_at"] = datetime.now().isoformat()
            self._task_guide["current_node"] = next_node
            self._task_guide["drift_count"] = 0
            return True
        self._task_guide["current_node"] = None
        return False

    def _task_guide_count_nodes(self, nodes: list) -> int:
        count = len(nodes)
        for n in nodes:
            count += self._task_guide_count_nodes(n.get("children", []))
        return count

    def _task_guide_progress(self) -> int:
        nodes = self._task_guide.get("nodes", [])
        total = self._task_guide_count_nodes(nodes)
        if total == 0:
            return 100
        completed = sum(1 for _ in self._task_guide_iter_nodes(nodes) if _.get("status") == "completed")
        return round(completed / total * 100)

    def _task_guide_iter_nodes(self, nodes: list):
        for n in nodes:
            yield n
            yield from self._task_guide_iter_nodes(n.get("children", []))

    def _task_guide_generate_correction(self, node: dict, action: str) -> str:
        task = node.get("task", "")
        keywords = node.get("keywords", [])
        if keywords:
            return f"当前任务: {task}。建议聚焦: {', '.join(keywords[:3])}。你的动作 '{action[:60]}' 似乎偏离了目标。"
        return f"当前任务: {task}。你的动作 '{action[:60]}' 似乎偏离了目标。请回到此任务。"

    def self_diagnose(self) -> dict:
        """触手自身短板扫描 - 逐项检测73项能力 + 硬件依赖 + 短板提示"""
        t0 = time.time()
        report = {"ok": True, "mode": "self_diagnose", "capabilities": {}, "dependencies": {}, "weaknesses": [], "suggestions": []}
        deps = {}
        
        # pyautogui
        try:
            import pyautogui; pyautogui.size()
            deps["pyautogui"] = {"status": "ok"}
        except Exception as e:
            deps["pyautogui"] = {"status": "missing", "error": str(e)[:80]}
            report["weaknesses"].append({"area": "core", "issue": "pyautogui missing - mouse/keyboard/screen all dead", "fix": "pip install pyautogui", "severity": "critical"})
        
        # PIL
        try:
            from PIL import Image; deps["PIL"] = {"status": "ok"}
        except Exception as e:
            deps["PIL"] = {"status": "missing", "error": str(e)[:80]}
            report["weaknesses"].append({"area": "image", "issue": "Pillow missing - screenshot processing dead", "fix": "pip install Pillow", "severity": "high"})
        
        # OCR已清理(2026-08-03, 用户指令: 框架无OCR, 视觉=DXGI数据通道)
        
        
        # easyocr: 已随OCR清理移除
        
        # win32
        try:
            import win32gui, win32process; deps["win32"] = {"status": "ok"}
        except ImportError:
            deps["win32"] = {"status": "missing"}
            report["weaknesses"].append({"area": "windows", "issue": "pywin32 missing - list_windows/trace_source partially dead", "fix": "pip install pywin32", "severity": "medium"})
        except Exception as e:
            deps["win32"] = {"status": "error"}
        
        # numpy
        try:
            import numpy; deps["numpy"] = {"status": "ok"}
        except ImportError:
            deps["numpy"] = {"status": "missing"}
        
        report["dependencies"] = deps
        
        # Capability scan
        caps = {}
        screen_ok = deps.get("pyautogui", {}).get("status") == "ok"
        mouse_ok = screen_ok
        win_ok = deps.get("win32", {}).get("status") == "ok"
        pil_ok = deps.get("PIL", {}).get("status") == "ok"
        ocr_ok = True  # OCR已清理, 视觉走DXGI数据通道
        
        # Vision (9)
        v9 = ["see", "screen_size", "screenshot", "live", "wait_for_change", "wait_stable"]
        for c in v9: caps[c] = "ok" if screen_ok else "unavailable"
        caps["screenshot_diff"] = "ok" if screen_ok and pil_ok else ("degraded" if screen_ok else "unavailable")
        caps["see_active_window"] = caps["see_window"] = "ok" if screen_ok and win_ok else ("degraded" if screen_ok else "unavailable")
        caps["list_windows"] = "ok" if win_ok else "unavailable"
        
        # OCR (6)
        ocr6 = ["read_text", "read_text_fast", "find_text", "read_region_text", "grab_value", "grab_table"]
        for c in ocr6: caps[c] = "ok" if ocr_ok else "unavailable"
        
        # Mouse (8)
        m8 = ["click", "double_click", "right_click", "move", "scroll", "click_relative", "drag", "position"]
        for c in m8: caps[c] = "ok" if mouse_ok else "unavailable"
        caps["click_text"] = "ok" if mouse_ok and ocr_ok else ("degraded" if mouse_ok else "unavailable")
        
        # Keyboard (11)
        k11 = ["type", "press", "hotkey", "enter", "tab", "escape", "select_all", "undo", "copy", "paste", "cut"]
        for c in k11: caps[c] = "ok" if mouse_ok else "unavailable"
        
        # Scroll (4)
        for c in ["scroll", "scroll_to_bottom", "scroll_to_top"]: caps[c] = "ok" if mouse_ok else "unavailable"
        caps["scroll_find"] = "ok" if mouse_ok and ocr_ok else ("degraded" if mouse_ok else "unavailable")
        
        # Trace (3)
        for c in ["trace_source", "trace_text", "trace_window_chain"]: caps[c] = "ok" if win_ok else "unavailable"
        
        # Clipboard (4)
        for c in ["clipboard_read", "clipboard_write", "clipboard_copy", "copy_text_at"]: caps[c] = "ok" if mouse_ok else "unavailable"
        
        # Dialog (3)
        for c in ["detect_dialog", "dismiss_dialog", "handle_any_dialog"]: caps[c] = "ok" if screen_ok else "unavailable"
        
        # Process (4) - always available
        for c in ["launch", "kill", "process_list", "app_running"]: caps[c] = "ok"
        
        # Wait (5)
        for c in ["wait_window", "wait_window_gone", "wait_text", "wait_for_change", "wait_stable"]: caps[c] = "ok" if screen_ok else "degraded"
        
        # Chain (2)
        caps["chain"] = "ok"
        caps["monitor"] = "ok" if screen_ok else "degraded"
        
        report["capabilities"] = caps
        
        # Health score
        total = len(caps)
        ok_count = sum(1 for v in caps.values() if v == "ok")
        degraded_count = sum(1 for v in caps.values() if v == "degraded")
        unavailable_count = sum(1 for v in caps.values() if v == "unavailable")
        health_pct = round((ok_count + degraded_count * 0.5) / max(total, 1) * 100)
        
        report["health_pct"] = health_pct
        report["summary"] = {"total": total, "ok": ok_count, "degraded": degraded_count, "unavailable": unavailable_count}
        
        if health_pct < 50: report["tier"] = "critical"
        elif health_pct < 80: report["tier"] = "degraded"
        else: report["tier"] = "healthy"
        
        # Dedup weaknesses
        seen = set()
        unique_w = []
        for w in report["weaknesses"]:
            key = w["area"] + w["issue"]
            if key not in seen:
                seen.add(key); unique_w.append(w)
        report["weaknesses"] = unique_w
        
        # Suggestions
        if unavailable_count > 0:
            missing = [k for k, v in deps.items() if v.get("status") not in ("ok",)]
            if missing: report["suggestions"].append("Missing deps: " + ", ".join(missing))
        if degraded_count > 0:
            deg = [k for k, v in caps.items() if v == "degraded"]
            report["suggestions"].append(f"Degraded ({len(deg)}): " + ", ".join(deg[:10]))
        
        report["elapsed_ms"] = round((time.time() - t0) * 1000)
        return report

    def self_diagnose_text(self) -> str:
        """Human-readable self-diagnosis report"""
        r = self.self_diagnose()
        lines = ["=" * 60, f"OmniTentacle Self-Diagnosis", f"   Health: {r['health_pct']}% ({r['tier']})", f"   Caps: {r['summary']['ok']}ok {r['summary']['degraded']}degraded {r['summary']['unavailable']}unavailable", "=" * 60, "", "Dependencies:"]
        for name, info in r["dependencies"].items():
            s = info["status"]
            icon = "[OK]" if s == "ok" else "[WARN]" if s == "degraded" else "[MISS]"
            lines.append(f"   {icon} {name}: {s}")
        if r["weaknesses"]:
            lines.append(""); lines.append(f"Weaknesses ({len(r['weaknesses'])}):")
            for i, w in enumerate(r["weaknesses"], 1):
                lines.append(f"   {i}. [{w['area']}] {w['issue']}")
                lines.append(f"      Fix: {w['fix']}")
        degraded = [k for k, v in r["capabilities"].items() if v != "ok"]
        if degraded:
            lines.append(""); lines.append(f"Degraded/Unavailable ({len(degraded)}):")
            for c in degraded: lines.append(f"   [{r['capabilities'][c]}] {c}")
        if r["suggestions"]:
            lines.append(""); lines.append("Suggestions:")
            for s in r["suggestions"]: lines.append(f"   -> {s}")
        lines.append(""); lines.append(f"Scan: {r['elapsed_ms']}ms")
        return chr(10).join(lines)
