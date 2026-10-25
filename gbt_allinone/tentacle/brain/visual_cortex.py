# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 · 视觉皮层（visual_cortex）

原版能力不丢失: L1 组件架构 / L2 渲染管线 / L3 行为叙事 / 屏幕结构理解 /
画面指纹缓存 / 本地视觉兜底 / 文本契约。

V8 增强:
  - 直接消费触手视觉总线与帧库, 不另开视觉旁路
  - 云视觉可用时做语义理解; 无云后端时仍产出真实本地契约, 不伪造描述
  - 画面缓存落 V8 store, 进程重启后不重复计算
  - 持续看电影时由 vision_watch 后台调用, 结果回传 visual 通道
"""
from __future__ import annotations

import hashlib
import importlib
import json
import re
import time
from pathlib import Path
from typing import Optional


def _import_first(candidates):
    for modpath in candidates:
        try:
            return importlib.import_module(modpath)
        except Exception:  # noqa: BLE001
            continue
    return None


def _store_dir() -> Path:
    mod = _import_first(("gbt_allinone._paths", "_paths"))
    if mod is not None and getattr(mod, "STORE_DIR", None):
        return Path(mod.STORE_DIR) / "visual_cortex"
    return Path(__file__).resolve().parents[3] / "store" / "visual_cortex"


def _safe_json_read(path: Path, default):
    mod = _import_first(("gbt_allinone.safe_io", "safe_io"))
    if mod is not None:
        try:
            return mod.load_json(path, default)
        except Exception:  # noqa: BLE001
            pass
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


# ── 落盘降级可见性（2026-09-22 · 第 31/39/40/41/42 条）──────────────────────────
# 🔴 第 41 条：本函数与 `visual_memory._safe_write` 原是**逐字同构的两级无声兜底**
# ⇒ 抽成共享件 `tools/visible_write.py` 并改为**委托**它，不再各维护一份拷贝。
# 共享件自带两把对照（它自己的负对照当场抓出过"bytes 塞给 write_text"的 bug）。
def _vw():
    return _import_first(("gbt_allinone.tools.visible_write", "visible_write"))


def write_health() -> dict:
    """只读：本模块落盘降级读数（委托 `visible_write.health("visual_cortex")`）。"""
    mod = _vw()
    if mod is None:
        return {"ok": False, "unavailable": True,
                "why": "visible_write 不可用 —— 落盘降级读数取不到（**不假装为 0**）"}
    return mod.health("visual_cortex")


def _safe_json_write(path: Path, data) -> bool:
    """写 JSON。**返回是否真的落盘**。共享件不在时返回 False（不假装成功）。"""
    mod = _vw()
    return False if mod is None else mod.write_json(path, data, label="visual_cortex")


def _transmission():
    return _import_first((
        "gbt_allinone.tentacle.brain.tentacle_transmission",
        "tentacle_transmission",
    ))


def _vision_cap():
    return _import_first(("gbt_allinone.vision_cap", "vision_cap"))


def _latest_visual_summary() -> dict:
    """取当前可用的视觉摘要（皮层唯一的取帧口）。

    🔴 2026-09-25 修：**这条取帧口从第一天起就是死的** —— 眼睛→皮层从来没通过。

    病根（**实测出来的，不是推断**）：原来这里只有一句
    `tx.snapshot(channel="visual", limit=8, min_priority="low")`。而 V8 的
    `brain.tentacle_transmission` 是个**兼容垫片**（它自己的 docstring 就写着
    "V8 审计总线**降级实现**"）：

      · `transmit()` 只把 `(source, channel, priority, **size**)` 写进审计，
        **数据本体直接丢掉**；
      · 它**根本没有 `snapshot`** —— 那个方法属于已经不存在的 `omni_*` 老硬件层
        （该模块公开面实测只有 `transmit` 与 `pulse`）。

    ⇒ 每次调用都抛 `AttributeError`，又被下面的 `except: return {}` **静默吞掉**
    ⇒ 皮层永远读到空 ⇒ `understand_screen` 永远回
    「无画面帧(总线无visual数据或视觉流未启动)」——
    **而眼睛其实一直在采帧**（实测：`captured=193 / buffer_frames=120` 时它仍这么报）。
    这正是本仓最恨的那类病：**不是没数据，是读取口调了个不存在的方法，异常被吞**。

    修法（两条，按顺序）：
      ① 老路径**存在才用**（`getattr` 探一下，不写死）——将来 omni 层若回来，它照旧生效；
      ② 否则回落到**眼睛自己的焦点帧** `vision_watch.frame()`。它的 docstring 就是
         「取当前最重要帧（**大脑视觉焦点**: 注意力 + 边看边清理）」
         —— 本来就是为大脑取帧而设计的口，不是绕过设计去翻内部缓冲。
    """
    tx = _transmission()
    if tx is not None:
        # ⚠️ 不许写死 `tx.snapshot(...)`：V8 垫片没有它（老 omni 层才有）
        snap = getattr(tx, "snapshot", None)
        if callable(snap):
            try:
                snapshots = snap(channel="visual", limit=8, min_priority="low") or []
            except Exception:  # noqa: BLE001
                snapshots = []
            for entry in snapshots:
                summary = (entry or {}).get("summary") or {}
                if summary.get("frame_b64") or summary.get("frame_id") or summary.get("text"):
                    return summary

    # ── ② V8 回退：眼睛的实时焦点帧 ──────────────────────────────────────
    vw = _import_first(("gbt_allinone.tentacle.vision_watch",
                        "tentacle.vision_watch", "vision_watch"))
    if vw is None:
        return {}
    try:
        got = vw.frame() or {}
    except Exception:  # noqa: BLE001
        return {}
    if not got.get("ok"):
        return {}
    f = got.get("frame") or {}
    b64 = f.get("image_base64") or ""
    if not b64:
        return {}
    out = {"frame_b64": b64, "text": f.get("screen_text") or "",
           "ts": f.get("ts"), "engine": f.get("engine"),
           "source": "vision_watch.frame"}
    if f.get("frame_id"):
        out["frame_id"] = f["frame_id"]
    return out


def _frame_from_bus(summary: dict | None = None) -> tuple[str, dict]:
    summary = summary or _latest_visual_summary()
    frame_b64 = summary.get("frame_b64") or ""
    frame_id = summary.get("frame_id") or ""
    if frame_b64:
        return frame_b64, summary
    if not frame_id:
        return "", summary
    vb = _import_first(("gbt_allinone.tentacle.vision_bus", "vision_bus"))
    if vb is None:
        return "", summary
    try:
        got = vb.get_frame(frame_id)
    except Exception:  # noqa: BLE001
        return "", summary
    if got.get("ok") and got.get("frame_b64"):
        merged = dict(summary)
        merged["frame_b64"] = got["frame_b64"]
        merged.setdefault("frame_id", got.get("frame_id"))
        return got["frame_b64"], merged
    return "", summary


def _fingerprint(frame_b64: str) -> str:
    vb = _import_first(("gbt_allinone.tentacle.vision_bus", "vision_bus"))
    try:
        bits = vb._ahash(frame_b64) if vb is not None else frame_b64
    except Exception:  # noqa: BLE001
        bits = frame_b64
    return hashlib.sha256(str(bits).encode("utf-8")).hexdigest()[:16]


class VisualCortex:
    """视觉皮层: HTML 三层结构分析 + 屏幕画面理解。"""

    def __init__(self):
        self._last_analysis: dict = {}
        self._page_cache: dict = {}
        self._screen_cache: dict = {}
        self._screen_cache_max = 16
        self._screen_cache_file = _store_dir() / "screen_cache.json"
        self._load_screen_cache()

    # ═══════════════ L1: 组件架构层 ═══════════════

    def analyze_components(self, html: str) -> dict:
        result = {
            "layer": 1,
            "name": "组件架构层",
            "components": [],
            "props_map": {},
            "hierarchy": {},
        }
        for match in re.finditer(r'<div[^>]*data-gbt3d="(\w+)"[^>]*>', html, re.IGNORECASE):
            tag = match.group(0)
            comp_type = match.group(1)
            result["components"].append({
                "type": f"gbt3d:{comp_type}",
                "props": self._extract_props(tag),
                "declarative": True,
                "engine": "gbt-3d.js" if comp_type in ("particles", "globe", "model") else "native",
            })

        anim_classes = {
            "gbt-reveal": "ScrollReveal",
            "gbt-reveal-left": "SlideLeft",
            "gbt-reveal-right": "SlideRight",
            "gbt-reveal-scale": "ScaleIn",
            "gbt-float": "Float",
            "gbt-pulse-glow": "PulseGlow",
            "gbt-spin-slow": "SpinSlow",
            "gbt-gradient-text": "GradientText",
            "gbt-card": "GlassCard",
        }
        for class_name, component_name in anim_classes.items():
            matches = re.findall(rf'class="[^"]*\b{class_name}\b[^"]*"', html, re.IGNORECASE)
            if matches:
                result["components"].append({
                    "type": f"animation:{component_name}",
                    "count": len(matches),
                    "declarative": True,
                    "engine": "gbt-animations.css",
                })

        parallax = re.findall(
            r'<[^>]*data-parallax[^>]*data-parallax-depth="(\d+)"[^>]*>',
            html,
            re.IGNORECASE,
        )
        if parallax:
            result["components"].append({
                "type": "interaction:Parallax",
                "count": len(parallax),
                "props": {"depth": [int(value) for value in parallax]},
                "declarative": True,
                "engine": "gbt-3d.js",
            })

        beams = re.findall(r'data-beam="from:\s*([^,]+),\s*to:\s*([^"]+)"', html, re.IGNORECASE)
        if beams:
            result["components"].append({
                "type": "interaction:Beam",
                "count": len(beams),
                "connections": [{"from": f.strip(), "to": t.strip()} for f, t in beams],
                "declarative": True,
                "engine": "gbt-3d.js (SVG overlay)",
            })

        result["total_components"] = len(result["components"])
        return result

    def _extract_props(self, tag: str) -> dict:
        props = {}
        for match in re.finditer(r'data-(\w[\w-]*)\s*=\s*"([^"]*)"', tag, re.IGNORECASE):
            key, value = match.group(1), match.group(2)
            if value.isdigit():
                props[key] = int(value)
            elif re.match(r"^-?\d+\.?\d*$", value):
                props[key] = float(value)
            elif value in ("true", "false"):
                props[key] = value == "true"
            else:
                props[key] = value
        return props

    # ═══════════════ L2: 渲染管线层 ═══════════════

    def analyze_pipeline(self, html: str) -> dict:
        result = {
            "layer": 2,
            "name": "渲染管线层",
            "pipeline": {},
            "bottlenecks": [],
            "mobile_risk": "low",
        }
        tag_count = len(re.findall(r"<\w+", html))
        result["pipeline"]["dom"] = {
            "tag_count": tag_count,
            "estimated_depth": self._estimate_depth(html),
            "weight": "heavy" if tag_count > 500 else "normal",
        }
        result["pipeline"]["css"] = {
            "external_sheets": len(re.findall(
                r"<link[^>]*stylesheet[^>]*>", html, re.IGNORECASE)),
            "inline_blocks": len(re.findall(r"<style[^>]*>", html, re.IGNORECASE)),
            "weight": "normal",
        }
        script_count = len(re.findall(r"<script[^>]*>", html, re.IGNORECASE))
        has_three = "three" in html.lower()
        result["pipeline"]["js"] = {
            "script_tags": script_count,
            "gbt3d_loaded": "gbt-3d.js" in html,
            "threejs_loaded": has_three,
            "react_r3f": "react-three-fiber" in html.lower() or "R3F" in html,
            "weight": "heavy" if has_three and script_count > 3 else "normal",
        }
        particles = sum(int(value) for value in re.findall(r'data-count="(\d+)"', html))
        globes = len(re.findall(r'data-gbt3d="globe"', html))
        models = len(re.findall(r'data-gbt3d="model"', html))
        gpu_load = particles + globes * 500 + models * 1000
        result["pipeline"]["gpu"] = {
            "estimated_particles": particles,
            "globe_instances": globes,
            "model_instances": models,
            "total_gpu_load": gpu_load,
            "weight": "critical" if gpu_load > 3000 else ("heavy" if gpu_load > 1500 else "normal"),
        }
        if gpu_load > 3000:
            result["bottlenecks"].append({
                "stage": "GPU",
                "issue": f"粒子+几何体总量{gpu_load}超过3000",
                "fix": "移动端降低粒子/几何体数量或启用自动降级",
                "severity": "high",
            })
        if tag_count > 500:
            result["bottlenecks"].append({
                "stage": "DOM",
                "issue": f"标签数{tag_count}偏高",
                "fix": "考虑懒加载或虚拟滚动",
                "severity": "medium",
            })
        if gpu_load > 3000 and not ("IS_MOBILE" in html or "mobile" in html.lower()):
            result["mobile_risk"] = "high"
            result["bottlenecks"].append({
                "stage": "Mobile",
                "issue": "GPU负载高但无移动端降级逻辑",
                "fix": "引入移动端粒子/视差/像素比降级",
                "severity": "critical",
            })
        return result

    def _estimate_depth(self, html: str) -> int:
        max_depth = 0
        current = 0
        for line in html.split("\n"):
            stripped = line.lstrip()
            if stripped.startswith("</"):
                current -= 1
            elif stripped.startswith("<") and not stripped.startswith("<!"):
                current += 1
                max_depth = max(max_depth, current)
        return max_depth

    # ═══════════════ L3: 行为叙事层 ═══════════════

    def analyze_narrative(self, html: str) -> dict:
        result = {
            "layer": 3,
            "name": "行为叙事层",
            "funnel": {},
            "score": 0,
            "suggestions": [],
        }
        has_particles = bool(re.search(r'data-gbt3d="particles"', html))
        has_globe = bool(re.search(r'data-gbt3d="globe"', html))
        has_hero = bool(re.search(r"<h1[^>]*>", html))
        result["funnel"]["attract"] = {
            "particles": has_particles,
            "globe_3d": has_globe,
            "hero_title": has_hero,
            "score": (2 if has_particles else 0) + (3 if has_globe else 0) + (1 if has_hero else 0),
            "max": 6,
        }
        reveal_count = len(re.findall(r'class="[^"]*gbt-reveal[^"]*"', html))
        has_stagger = "stagger" in html.lower() or "gbt-reveal:nth-child" in html
        result["funnel"]["explain"] = {
            "reveal_elements": reveal_count,
            "has_stagger": has_stagger,
            "score": min(reveal_count, 5) + (2 if has_stagger else 0),
            "max": 7,
        }
        has_parallax = bool(re.search(r"data-parallax", html))
        has_beam = bool(re.search(r"data-beam", html))
        has_cta = bool(re.search(
            r"(?i)(cta|call.to.action|get.started|sign.up|buy.now|立即|马上)", html))
        result["funnel"]["convert"] = {
            "parallax": has_parallax,
            "beams": has_beam,
            "cta_present": has_cta,
            "score": (2 if has_parallax else 0) + (3 if has_beam else 0) + (2 if has_cta else 0),
            "max": 7,
        }
        total = sum(part["score"] for part in result["funnel"].values())
        max_total = sum(part["max"] for part in result["funnel"].values())
        result["score"] = round(total / max_total * 100, 1)
        if not has_particles and not has_globe:
            result["suggestions"].append({
                "stage": "attract",
                "action": '首屏缺少3D焦点。添加 data-gbt3d="particles" 或 data-gbt3d="globe"',
            })
        if reveal_count < 3:
            result["suggestions"].append({
                "stage": "explain",
                "action": '滚动叙事元素不足。为关键内容添加 class="gbt-reveal"',
            })
        if not has_beam and has_globe and has_cta:
            result["suggestions"].append({
                "stage": "convert",
                "action": '地球和CTA之间缺少视觉引导。添加 data-beam="from:#globe, to:#cta"',
            })
        return result

    def analyze_page(self, html: str, url: str = "") -> dict:
        t0 = time.time()
        l1 = self.analyze_components(html)
        l2 = self.analyze_pipeline(html)
        l3 = self.analyze_narrative(html)
        report = {
            "url": url,
            "timestamp": time.time(),
            "analysis_time_ms": round((time.time() - t0) * 1000),
            "html_size_kb": round(len(html) / 1024, 1),
            "layers": {
                "L1_architecture": l1,
                "L2_pipeline": l2,
                "L3_narrative": l3,
            },
            "summary": {
                "components": l1["total_components"],
                "gpu_load": l2["pipeline"]["gpu"]["total_gpu_load"],
                "mobile_risk": l2["mobile_risk"],
                "narrative_score": l3["score"],
                "bottlenecks": len(l2["bottlenecks"]),
                "suggestions": len(l3["suggestions"]),
            },
            "verdict": self._verdict(l1, l2, l3),
        }
        self._last_analysis = report
        if url:
            self._page_cache[url] = report
        return report

    def _verdict(self, l1: dict, l2: dict, l3: dict) -> str:
        issues = []
        if l1["total_components"] == 0:
            issues.append("无声明式组件")
        if l2["mobile_risk"] == "high":
            issues.append("移动端高风险")
        if l2["bottlenecks"]:
            issues.append(f'{len(l2["bottlenecks"])}个性能瓶颈')
        if l3["score"] < 40:
            issues.append(f'叙事评分低({l3["score"]}%)')
        if not issues:
            return "生产级: 组件声明完备, 性能达标, 叙事结构完整"
        return f"需优化: {'; '.join(issues)}"

    # ═══════════════ 屏幕结构理解 ═══════════════

    def analyze_screen(self, frame_b64: str | None = None) -> dict:
        frame_b64, summary = _frame_from_bus() if not frame_b64 else (frame_b64, _latest_visual_summary())
        if not frame_b64:
            return {"ok": False, "error": "无画面帧(视觉总线为空, 请先启动 vision_watch 或 vision_snapshot)"}
        text = str(summary.get("text") or "")
        blocks = summary.get("text_blocks") or []
        local = {}
        vc = _vision_cap()
        if vc is not None:
            try:
                local = vc.analyze(image=frame_b64, grid=4)
            except Exception:  # noqa: BLE001
                local = {}
        if not text and blocks:
            text = " ".join(str(block.get("text", "")) for block in blocks if isinstance(block, dict))

        component_hints = []
        if re.search(r"(?i)3d|particle|globe|模型", text):
            component_hints.append("3D组件")
        if re.search(r"(?i)button|btn|按钮|点击|提交|登录|注册", text):
            component_hints.append("交互控件")
        if re.search(r"(?i)chart|graph|图表|数据|统计", text):
            component_hints.append("数据可视化")

        zones = {
            "top": {"blocks": 0, "density": 0},
            "middle": {"blocks": 0, "density": 0},
            "bottom": {"blocks": 0, "density": 0},
        }
        for block in blocks:
            if not isinstance(block, dict):
                continue
            y = block.get("y", 0)
            zone = "top" if y < 200 else ("middle" if y < 700 else "bottom")
            zones[zone]["blocks"] += 1
        total = len(blocks) or 1
        for zone in zones.values():
            zone["density"] = round(zone["blocks"] / total * 100)

        task_hints = []
        if re.search(r"(?i)code|coding|编程|代码|python|js|html|css", text):
            task_hints.append("编程")
        if re.search(r"(?i)chat|对话|聊天|deepseek|gpt|claude", text):
            task_hints.append("AI对话")
        if re.search(r"(?i)browser|chrome|edge|标签|tab", text):
            task_hints.append("浏览网页")
        if re.search(r"(?i)trade|交易|股票|stock|买入|卖出", text):
            task_hints.append("交易")

        grid_brightness = local.get("grid_brightness") or []
        if grid_brightness:
            rows = [round(sum(grid_brightness[i:i + 4]) / 4, 1)
                    for i in range(0, min(16, len(grid_brightness)), 4)]
            zones["top"]["brightness"] = rows[0] if rows else None
            zones["middle"]["brightness"] = rows[1] if len(rows) > 1 else None
            zones["bottom"]["brightness"] = rows[2] if len(rows) > 2 else None
        return {
            "ok": True,
            "engine": "local-contract" if not text else "bus-contract",
            "total_blocks": len(blocks),
            "screen_zones": zones,
            "component_hints": component_hints,
            "task_inference": task_hints or ["未知"],
            "text_sample": text[:300],
            "local": local,
            "frame_id": summary.get("frame_id"),
            "fingerprint": summary.get("fingerprint"),
        }

    # ═══════════════ 画面语义理解 + 缓存 ═══════════════

    def _load_screen_cache(self) -> None:
        data = _safe_json_read(self._screen_cache_file, {})
        if isinstance(data, dict):
            self._screen_cache = dict(list(data.items())[-self._screen_cache_max:])

    def _save_screen_cache(self) -> None:
        now = time.time()
        if getattr(self, "_sc_saved_at", 0) + 30 < now:
            _safe_json_write(self._screen_cache_file, self._screen_cache)
            self._sc_saved_at = now

    def _cache_hit(self, fingerprint: str) -> dict | None:
        hit = self._screen_cache.get(fingerprint)
        if hit:
            out = dict(hit)
            out["cached"] = True
            return out
        return None

    def understand_screen(self, frame_b64: str = None, use_cache: bool = True) -> dict:
        frame_b64, summary = _frame_from_bus() if not frame_b64 else (frame_b64, _latest_visual_summary())
        if not frame_b64:
            return {"ok": False, "error": "无画面帧(总线无visual数据或视觉流未启动)"}
        fingerprint = _fingerprint(frame_b64)
        if use_cache:
            hit = self._cache_hit(fingerprint)
            if hit:
                return hit

        result = None
        vc = _vision_cap()
        if vc is not None:
            try:
                if vc.resolve_vision_backend():
                    raw = __import__("base64").b64decode(frame_b64)
                    cloud = vc.cloud_recognize(
                        image=raw,
                        prompt=(
                            "详细描述当前屏幕: 窗口、界面元素、可见文字、正在进行的任务、"
                            "人物/物体与场景变化。用中文回答。"
                        ),
                    )
                    if cloud.get("ok") and cloud.get("description"):
                        result = {
                            "ok": True,
                            "engine": cloud.get("model") or "cloud-vision",
                            "description": str(cloud["description"])[:2000],
                            "description_cn": str(cloud["description"])[:2000],
                            "frame_id": summary.get("frame_id"),
                            "fingerprint": fingerprint,
                            "note": "画面契约: 视觉后端把屏幕画面转成文本描述",
                        }
            except Exception as exc:  # noqa: BLE001
                result = {"ok": False, "error": f"cloud-vision: {type(exc).__name__}: {exc}"[:200]}

        if result is None or not result.get("ok"):
            local = self.analyze_screen(frame_b64)
            if not local.get("ok"):
                return local
            bits = []
            if local.get("text_sample"):
                bits.append(f"屏幕文字: {local['text_sample']}")
            stats = local.get("local") or {}
            if stats.get("size"):
                bits.append(f"画面尺寸: {stats['size'][0]}x{stats['size'][1]}")
            if stats.get("brightness") is not None:
                bits.append(f"亮度: {stats['brightness']}")
            if stats.get("edge_density") is not None:
                bits.append(f"细节密度: {stats['edge_density']}")
            if local.get("component_hints"):
                bits.append("界面线索: " + "、".join(local["component_hints"]))
            if local.get("task_inference"):
                bits.append("任务推断: " + "、".join(local["task_inference"]))
            description = "；".join(bits) if bits else "画面帧已到达本地视觉皮层，暂无文字或结构线索"
            result = {
                "ok": True,
                "engine": "local-contract",
                "description": description,
                "description_cn": description,
                "text_blocks": summary.get("text_blocks") or [],
                "frame_id": summary.get("frame_id") or local.get("frame_id"),
                "fingerprint": fingerprint,
                "local": stats,
                "note": "本地视觉契约: 无云视觉后端时仍提供真实文字、像素与结构信息",
            }

        result["ts"] = time.time()
        if use_cache:
            self._screen_cache[fingerprint] = dict(result)
            if len(self._screen_cache) > self._screen_cache_max:
                oldest = min(
                    self._screen_cache,
                    key=lambda key: self._screen_cache[key].get("ts", 0),
                )
                self._screen_cache.pop(oldest, None)
            self._save_screen_cache()
        return result

    def status(self) -> dict:
        return {
            "ok": True,
            "engine": "visual-cortex-v8",
            "layers": ["L1_architecture", "L2_pipeline", "L3_narrative"],
            "screen_cache": len(self._screen_cache),
            "screen_cache_limit": self._screen_cache_max,
            "cache_file": str(self._screen_cache_file),
        }


_cortex: Optional[VisualCortex] = None


def get_cortex() -> VisualCortex:
    global _cortex
    if _cortex is None:
        _cortex = VisualCortex()
    return _cortex


# ── R-H295 · ⑥ G1/G2：视觉皮层的**结构化"做不了"** ────────────────────────
# 《触手覆盖矩阵.md》§三 实测眼组「能报做不了 0/5」，本文件是其中之一。
# 病根：`_frame_from_bus()` 取不到帧时**静默返回空串**（连原因都不带），
# 于是下游要么在空帧上算出没有意义的结果，要么抛一个没有分类的异常 ——
# 调用方分不清"没帧源 / 没显示 / 帧已过期 / 形状异常"。
# 下面这个出口把「拿不到帧」变成有分类的拒绝：缺什么写在 missing 里。
_CORTEX_MISSING = ("display", "frame_source")


def _no_frame(action: str, summary: dict | None = None) -> dict:
    """拿不到帧 ⇒ 结构化"做不了"（不返回空结果、不假装分析过）。"""
    s = summary if isinstance(summary, dict) else {}
    return {
        "ok": False,
        "unavailable": True,
        "denied": False,
        "rule": "visual_cortex_no_frame",
        "action": action,
        "missing": list(_CORTEX_MISSING),
        "why": ("取不到可用帧：既无 frame_b64，也无法由 frame_id 从 vision_bus 取回"
                + ("（有 frame_id=%s 但取回失败/已过期）" % str(s.get("frame_id"))[:40]
                   if s.get("frame_id") else "（也无 frame_id）")),
        "note": "视觉皮层做不了时结构化上报：缺什么写在 missing 里，不返回空结果。",
    }


def analyze_html(html: str, url: str = "") -> dict:
    if not str(html or "").strip():
        return {"ok": False, "unavailable": True, "denied": False,
                "rule": "visual_cortex_empty_input", "action": "analyze_html",
                "missing": ["html"], "why": "html 为空：没有可分析的页面内容"}
    return get_cortex().analyze_page(html, url)


def analyze_current_screen(frame_b64: str = None) -> dict:
    frame = frame_b64
    summary = None
    if not frame:
        frame, summary = _frame_from_bus()
    if not frame:
        return _no_frame("analyze_current_screen", summary)
    return get_cortex().analyze_screen(frame)


def understand_screen(frame_b64: str = None, use_cache: bool = True) -> dict:
    frame = frame_b64
    summary = None
    if not frame:
        frame, summary = _frame_from_bus()
    if not frame:
        return _no_frame("understand_screen", summary)
    return get_cortex().understand_screen(frame, use_cache=use_cache)


def status() -> dict:
    return get_cortex().status()


__all__ = [
    "VisualCortex",
    "get_cortex",
    "analyze_html",
    "analyze_current_screen",
    "understand_screen",
    "status",
]
