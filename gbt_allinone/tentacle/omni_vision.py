# gbt-capability: subprocess, dynamic-import, ctypes, base64
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
# vision 域 mixin — 拆分自 omni_tentacle (自动生成, 2026-08-10)
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


class OmniVisionMixin:
    """vision 域能力 — 8 方法"""

    # ── R-H295 · ⑥ G1/G2：视觉面的**结构化"做不了"** ──────────────────────
    # 《触手覆盖矩阵.md》§三 实测：「眼（视觉）5/5 模块 · 能报"做不了" **0/5**」——
    # 唯一一个**零上报信号**的组。病根有两层，这里一并修：
    #   ① 有拒绝但**无结构**：原来是 `{"ok": False, "error": "无法获取活动窗口"}`，
    #      调用方拿不到"这是缺依赖、还是缺权限、还是没硬件"的分类；
    #   ② 更糟的是**五处根本没检查** —— `see_active_window` / `see_window` /
    #      `screenshot_diff` / `wait_for_change` / `live` 都在 `screen_capture_safe()` 之后
    #      直接取 `cap["image_base64"]` / `cap["size"]`。截屏失败（无显示 / DXGI 取不到帧）
    #      时它们抛 `KeyError` —— **既不报"我做不了"，也不说为什么**，正是
    #      "只抛异常不回结构化否决"。眼睛坏了却一声不响，比报错更坏。
    # 下面这个 `_cap_refusal` 是**唯一**的失败出口：任何取帧失败都经它，
    # 形状固定为 `ok/unavailable/rule/missing/why/cap`，与门禁的 denied 形状同族。
    _CAP_MISSING = ("display", "frame_source")

    def _cap_refusal(self, cap, action: str) -> dict:
        """取帧失败 ⇒ 结构化"做不了"。**不抛异常、不返回半截数据。**"""
        cap = cap if isinstance(cap, dict) else {}
        why = str(cap.get("error") or cap.get("why") or "取帧失败（原因未报）")[:200]
        return {
            "ok": False,
            "unavailable": True,
            "denied": False,
            "rule": "screen_capture_unavailable",
            "action": action,
            "missing": list(self._CAP_MISSING),
            "why": why,
        "error": str(why)[:240],  # 向后兼容：老调用方读 error
            "cap": cap,
            "note": ("视觉面做不了时**必须结构化上报**（G1/G2）："
                     "缺什么写在 missing 里，不要只抛 KeyError。"),
        }

    def _require_cap(self, cap, action: str):
        """取帧 + 检查；成功返回 (cap, None)，失败返回 (None, 结构化拒绝)。

        R-H295：`cap` 可能是一个**已经抛出来的异常**而不是 dict —— `_screen_capture`
        在非交互桌面上会 `raise CaptureUnavailable`，那条路径**绕过所有 `cap.get("ok")`
        检查**，直接炸穿调用链（我第一版就是这样漏的）。所以这里先把异常形态也接住；
        调用方要彻底不抛，请用 `omni_core.screen_capture_safe(...)`。
        """
        if isinstance(cap, BaseException):
            return None, self._cap_refusal(
                {"error": "%s: %s" % (type(cap).__name__, str(cap)[:160])}, action)
        if not isinstance(cap, dict) or not cap.get("ok"):
            return None, self._cap_refusal(cap, action)
        if "image_base64" not in cap and "size" not in cap:
            return None, self._cap_refusal(
                {"error": "取帧返回里既无 image_base64 也无 size（形状异常）"}, action)
        return cap, None

    def see(self, region=None, incremental=True):
        """取一帧。

        🔴 `incremental`（2026-09-23 补，为触手视觉回传窗而开）：
        `_screen_capture` 的增量模式是**为"秒级传输优化"设计的** —— 画面变化 <15% 时
        **只编码变化的那块矩形**并把 `delta` 标成 True。对"看一眼发生了什么"是对的；
        但对**"把画面当一路视频回传"是错的**：实测同一秒里取到的"帧"会是
        `1136×64` / `428×720` / `1636×68` 这种碎片，**根本不成画面**。
        ⇒ 默认仍是 `True`（**不动既有调用方的行为**），要看整帧的调用方显式传
        `incremental=False`。经唯一门调就是：
        `cap tentacle '{"action":"see","kwargs":{"incremental":false}}'`
        """
        cap = screen_capture_safe(region, incremental=incremental)
        # ⛔ 2026-08-04 触手→大脑: 截屏摘要穿透传输
        if cap.get("ok"):
            try:
                from .brain.tentacle_transmission import transmit as _tx
                _tx({"size": cap.get("size", [0, 0]), "ok": True,
                     "channel": "screen", "format": cap.get("format", "PNG")},
                    source="omni_tentacle.see", channel="visual", priority="normal")
            except Exception: pass  # 容错: 非关键路径
        else:
            return self._cap_refusal(cap, "see")
        return cap

    def see_active_window(self):
        win = _get_active_window()
        if not win:
            return {"ok": False, "unavailable": True, "denied": False,
                    "rule": "no_active_window", "action": "see_active_window",
                    "missing": ["active_window"],
                    "why": "拿不到活动窗口（无前台窗口 / 窗口 API 取不到）"}
        r = win["rect"]
        cap, refusal = self._require_cap(
            screen_capture_safe({"x": r["left"], "y": r["top"],
                             "w": r["right"]-r["left"], "h": r["bottom"]-r["top"]}),
            "see_active_window")
        if refusal:
            return refusal
        cap["window"] = win
        return cap

    def see_window(self, target):
        win = _find_window(target)
        if not win:
            return {"ok": False, "unavailable": True, "denied": False,
                    "rule": "window_not_found", "action": "see_window",
                    "missing": ["window"], "target": str(target)[:80],
                    "why": f"未找到窗口: {target}"}
        r = win["rect"]
        cap, refusal = self._require_cap(
            screen_capture_safe({"x": r["left"], "y": r["top"],
                             "w": r["right"]-r["left"], "h": r["bottom"]-r["top"]}),
            "see_window")
        if refusal:
            return refusal
        cap["window"] = win
        return cap

    def list_windows(self):
        try:
            wins = _enum_windows()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "unavailable": True, "denied": False,
                    "rule": "window_enum_failed", "action": "list_windows",
                    "missing": ["window_api"], "why": "%s: %s" % (type(e).__name__, str(e)[:120])}
        return {"ok": True, "windows": wins}

    def screenshot(self, filepath: str = None, region: dict = None):
        """截图 — 默认内存回传不落盘; 显式 filepath 走镜像出品写盘(b64文本)
        ⛔ 2026-08-13 打磨: v5.5 写保护拦截裸写(与 export_data 同类), 且临时画面
        数据落盘违反数据铁律(边操作边过滤)。默认通道 memory, 显式保存走 publish。"""
        cap, refusal = self._require_cap(screen_capture_safe(region, fmt="png"), "screenshot")
        if refusal:
            return refusal
        if filepath is None:
            return {"ok": True, "size": cap["size"], "kb": cap["image_kb"],
                    "image_base64": cap["image_base64"], "channel": "memory"}
        try:
            from .brain import gatekeeper as _gk_shot
            _res = _gk_shot.publish(str(filepath), cap["image_base64"], "omni_tentacle_screenshot")
        except Exception as e:
            return {"ok": False, "error": f"截图写盘被管线拒绝: {str(e)[:100]}"}
        if not _res.get("ok"):
            return {"ok": False, "error": f"截图写盘被管线拒绝: {_res.get('error','?')[:100]}"}
        return {"ok": True, "filepath": str(filepath), "size": cap["size"], "kb": cap["image_kb"],
                "format": "base64_text", "channel": "mirror_pipeline"}

    def screenshot_diff(self, other_filepath: str = None):
        """截图对比 — 当前画面 vs 之前保存的截图"""
        import hashlib
        cap, refusal = self._require_cap(screen_capture_safe(), "screenshot_diff")
        if refusal:
            return refusal
        current_hash = hashlib.sha256(
            __import__('base64').b64decode(cap["image_base64"])
        ).hexdigest()[:16]

        if other_filepath:
            try:
                other_data = __import__('base64').b64encode(
                    Path(other_filepath).read_bytes()
                ).decode()
                other_hash = hashlib.sha256(
                    Path(other_filepath).read_bytes()
                ).hexdigest()[:16]
                changed = current_hash != other_hash
                return {"ok": True, "changed": changed, "current_hash": current_hash,
                       "other_hash": other_hash, "other_file": other_filepath}
            except Exception as e:
                return {"ok": False, "error": str(e)[:100]}

        # 与上次对比
        if hasattr(self, '_last_screenshot_hash'):
            changed = current_hash != self._last_screenshot_hash
            result = {"ok": True, "changed": changed, "current_hash": current_hash,
                     "previous_hash": self._last_screenshot_hash}
        else:
            result = {"ok": True, "changed": None, "current_hash": current_hash,
                     "note": "首次截图，无对比基准"}
        
        self._last_screenshot_hash = current_hash
        return result

    def wait_for_change(self, timeout: float = 30, interval: float = 0.5):
        """等待画面变化"""
        import hashlib
        base, refusal = self._require_cap(screen_capture_safe(), "wait_for_change")
        if refusal:
            return refusal
        base_hash = hashlib.sha256(
            __import__('base64').b64decode(base["image_base64"])
        ).hexdigest()

        end = time.time() + timeout
        while time.time() < end:
            cur, refusal = self._require_cap(screen_capture_safe(), "wait_for_change")
            if refusal:
                return refusal          # 中途眼睛瞎了 ⇒ 如实报，不许硬等到超时
            cur_hash = hashlib.sha256(
                __import__('base64').b64decode(cur["image_base64"])
            ).hexdigest()
            if cur_hash != base_hash:
                return {"ok": True, "changed": True,
                       "elapsed": round(timeout - (end - time.time()), 1)}
            time.sleep(interval)
        return {"ok": True, "changed": False, "timeout": timeout}

    def live(self, duration_s=10, interval_ms=500):
        frames = []
        end = time.time() + duration_s
        while time.time() < end:
            t0 = time.time()
            cap, refusal = self._require_cap(screen_capture_safe(), "live")
            if refusal:
                # 一帧都取不到 ⇒ 直接报；已经取到的帧如实带上，不丢证据也不假装成功
                refusal["frames_captured"] = len(frames)
                return refusal
            frames.append({"ts": datetime.now().isoformat(), "size": cap["size"], "kb": cap["image_kb"]})
            elapsed = (time.time() - t0) * 1000
            sleep_s = max(0, interval_ms - elapsed) / 1000
            if sleep_s > 0: time.sleep(sleep_s)
        return {"ok": True, "duration_s": duration_s, "frames": len(frames), "fps": round(len(frames) / max(duration_s, 0.1), 1)}

    # ═══ 视觉传输总线（V8：视觉也是传输——缓存/定位/流/回放）═══

    def vision_snapshot(self, region=None, ttl=60):
        """带缓存的视觉快照：同画面指纹命中缓存则零成本复用（视觉的 cache:true）。"""
        import importlib as _il
        try:
            vision_bus = _il.import_module('gbt_allinone.tentacle.vision_bus')
        except Exception:
            vision_bus = _il.import_module('vision_bus')
        return vision_bus.snapshot(self, region, ttl)

    def vision_diff(self, grid=4):
        """变化区域定位：与上次快照对比，给出变化矩形（网格哈希），非只说"变了"。"""
        import importlib as _il
        try:
            vision_bus = _il.import_module('gbt_allinone.tentacle.vision_bus')
        except Exception:
            vision_bus = _il.import_module('vision_bus')
        return vision_bus.diff_with_previous(self, grid)

    def vision_stream_record(self, duration_s=10, interval_ms=500, stream_name=None):
        """视觉流记录：帧时间线（指纹+变化）落 store，可回放。"""
        import importlib as _il
        try:
            vision_bus = _il.import_module('gbt_allinone.tentacle.vision_bus')
        except Exception:
            vision_bus = _il.import_module('vision_bus')
        return vision_bus.stream_record(self, duration_s, interval_ms, stream_name)

    def vision_stream_replay(self, name=None, limit=50):
        """视觉流回放：帧时间线 + 变化段提取。"""
        import importlib as _il
        try:
            vision_bus = _il.import_module('gbt_allinone.tentacle.vision_bus')
        except Exception:
            vision_bus = _il.import_module('vision_bus')
        return vision_bus.stream_replay(name, limit)
