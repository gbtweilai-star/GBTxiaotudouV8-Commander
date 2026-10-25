# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 · 视觉记忆（visual_memory）

原版“大脑影院”的记忆沉淀能力回归:
  看到的帧 → 缩略图 + OCR文本 + 画面描述 + 语义关键词 → 时间线/语义索引
  可回忆: “刚才屏幕上有什么 / 今天看到了什么 / 最近场景如何演变 / 搜索画面”

V8 调整:
  - 数据落 V8 store, 遵守 GBT_STORE_DIR 隔离
  - 内容寻址去重, 同一画面不重复写盘
  - 线程锁保护推流与理解线程并发写入
  - 原有 10000 条时间线 / 500 张帧的边界保持不变
"""
from __future__ import annotations

import base64
import hashlib
import importlib
import json
import re
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

MAX_TIMELINE = 10000
MAX_FRAMES = 500
MAX_INDEX_ENTRIES = 1000
MAX_SEMANTIC_KEYS = 500


def _import_first(candidates):
    for modpath in candidates:
        try:
            return importlib.import_module(modpath)
        except Exception:  # noqa: BLE001
            continue
    return None


def _base_dir() -> Path:
    mod = _import_first(("gbt_allinone._paths", "_paths"))
    if mod is not None and getattr(mod, "STORE_DIR", None):
        return Path(mod.STORE_DIR) / "visual_memory"
    return Path(__file__).resolve().parents[3] / "store" / "visual_memory"


MEMORY_DIR = _base_dir()
FRAMES_DIR = MEMORY_DIR / "frames"
OCR_DIR = MEMORY_DIR / "ocr"
ANALYSIS_DIR = MEMORY_DIR / "analysis"
TIMELINE_FILE = MEMORY_DIR / "timeline.json"
SEMANTIC_FILE = MEMORY_DIR / "semantic.json"
STATS_FILE = MEMORY_DIR / "stats.json"

_LOCK = threading.RLock()


def _safe_read(path: Path, default):
    safe_io = _import_first(("gbt_allinone.safe_io", "safe_io"))
    if safe_io is not None:
        try:
            return safe_io.load_json(path, default)
        except Exception:  # noqa: BLE001
            pass
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


# ── 落盘降级可见性（2026-09-22 · 第 31/39/40/41/42 条）──────────────────────────
# 🔴 第 41 条：同一段「两级兜底、两级都无声」被抄了两遍（本文件 + `visual_cortex`）
# ⇒ 抽成共享件 `tools/visible_write.py`（原子写 → 兜底写 → **每级留痕 + 返回真假 + 只读口**，
#    且它自带两把对照 —— 它自己的负对照当场抓出过"bytes 塞给 write_text"的 bug）。
# 本文件改为**委托**它，不再自己维护一份拷贝（免得出现第三份）。
def _vw():
    return _import_first(("gbt_allinone.tools.visible_write", "visible_write"))


def write_health() -> dict:
    """只读：本模块落盘降级读数（委托 `visible_write.health("visual_memory")`）。"""
    mod = _vw()
    if mod is None:
        return {"ok": False, "unavailable": True,
                "why": "visible_write 不可用 —— 落盘降级读数取不到（**不假装为 0**）"}
    return mod.health("visual_memory")


def _safe_write(path: Path, data) -> bool:
    """写 JSON。**返回是否真的落盘**。共享件不在时返回 False（不假装成功）。"""
    mod = _vw()
    return False if mod is None else mod.write_json(path, data, label="visual_memory")


def _safe_write_bytes(path: Path, data: bytes) -> bool:
    """写字节。**返回是否真的落盘**。"""
    mod = _vw()
    return False if mod is None else mod.write_bytes(path, data, label="visual_memory")


def _safe_text(path: Path, text: str) -> bool:
    """写文本。**返回是否真的落盘**。"""
    mod = _vw()
    return False if mod is None else mod.write_text(path, text, label="visual_memory")


def _decode_frame(frame_b64: str) -> tuple[bytes, str, str]:
    raw = base64.b64decode(frame_b64)
    digest = hashlib.sha256(raw).hexdigest()[:16]
    return raw, digest, f"{digest}.jpg"


class VisualMemory:
    """视觉记忆: 像人脑一样存储和回忆看到的画面。"""

    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        FRAMES_DIR.mkdir(parents=True, exist_ok=True)
        OCR_DIR.mkdir(parents=True, exist_ok=True)
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        self.timeline = _safe_read(TIMELINE_FILE, [])
        self.semantic = _safe_read(SEMANTIC_FILE, {})
        self.stats = _safe_read(STATS_FILE, {
            "total_frames": 0,
            "total_ocr_chars": 0,
            "unique_frames": 0,
            "started_at": None,
            "last_frame_at": None,
        })
        if not self.stats.get("started_at"):
            self.stats["started_at"] = datetime.now().isoformat()

    def _prune_frames(self) -> None:
        try:
            files = sorted(FRAMES_DIR.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
            for old in files[:-MAX_FRAMES] if len(files) > MAX_FRAMES else []:
                try:
                    old.unlink()
                except OSError:
                    pass
        except OSError:
            pass

    def _prune_ocr(self, max_files: int = MAX_FRAMES) -> None:
        try:
            files = sorted(OCR_DIR.glob("*.txt"), key=lambda p: p.stat().st_mtime)
            for old in files[:-max_files] if len(files) > max_files else []:
                try:
                    old.unlink()
                except OSError:
                    pass
        except OSError:
            pass

    def _save_indexes(self) -> None:
        _safe_write(TIMELINE_FILE, self.timeline[-MAX_INDEX_ENTRIES:])
        semantic_items = sorted(
            self.semantic.items(),
            key=lambda item: item[1][-1] if item[1] else "",
            reverse=True,
        )[:MAX_SEMANTIC_KEYS]
        _safe_write(SEMANTIC_FILE, dict(semantic_items))
        _safe_write(STATS_FILE, self.stats)

    def _index_keywords(self, memory_id: str, keywords: list[str]) -> None:
        for keyword in keywords:
            bucket = self.semantic.setdefault(keyword, [])
            if memory_id not in bucket:
                bucket.append(memory_id)
            if len(bucket) > 100:
                del bucket[:-100]

    def remember(self, capture_result: dict) -> dict:
        """记住一帧: 图像/OCR/理解描述/分析结果全部沉淀。"""
        if not isinstance(capture_result, dict):
            return {"ok": False, "error": "capture_result 必须是 dict"}
        with _LOCK:
            now = datetime.now()
            memory_id = f"mem_{now.strftime('%Y%m%d_%H%M%S_%f')}"
            entry = {
                "id": memory_id,
                "timestamp": now.isoformat(),
                "channel": capture_result.get("channel", "?"),
                "size": capture_result.get("size", [0, 0]),
            }
            description = str(capture_result.get("description") or "")[:1000]
            if description:
                entry["description"] = description

            frame_b64 = capture_result.get("image_base64") or capture_result.get("frame_b64") or ""
            if frame_b64:
                try:
                    raw, digest, filename = _decode_frame(frame_b64)
                    frame_path = FRAMES_DIR / filename
                    if not frame_path.exists():
                        _safe_write_bytes(frame_path, raw)
                        self._prune_frames()
                    entry["frame_id"] = digest
                    entry["frame_file"] = str(frame_path)
                except Exception:  # noqa: BLE001
                    pass
            if capture_result.get("frame_id"):
                entry["frame_id"] = capture_result["frame_id"]

            ocr = capture_result.get("ocr") or {}
            ocr_text = str(ocr.get("text") or capture_result.get("text") or "")
            if ocr_text:
                try:
                    ocr_path = OCR_DIR / f"{memory_id}.txt"
                    _safe_text(ocr_path, ocr_text)
                    self._prune_ocr()
                    entry["ocr_file"] = str(ocr_path)
                    entry["ocr_length"] = len(ocr_text)
                    entry["ocr_blocks"] = ocr.get("block_count", len(capture_result.get("text_blocks") or []))
                    entry["ocr_preview"] = ocr_text[:500]
                    self.stats["total_ocr_chars"] = int(self.stats.get("total_ocr_chars", 0)) + len(ocr_text)
                except OSError:
                    pass

            keywords = self._extract_keywords(ocr_text) if ocr_text else []
            if description:
                keywords.extend(self._extract_keywords(description, min_count=1))
            keywords = list(dict.fromkeys(keywords))[:30]
            entry["keywords"] = keywords
            self._index_keywords(memory_id, keywords)

            analysis = capture_result.get("analysis") or {}
            if analysis.get("ok"):
                try:
                    analysis_path = ANALYSIS_DIR / f"{memory_id}.json"
                    _safe_write(analysis_path, analysis)
                    entry["analysis_file"] = str(analysis_path)
                    entry["brightness"] = analysis.get("brightness")
                    entry["edge_density"] = analysis.get("edge_density")
                except OSError:
                    pass

            self.timeline.append(entry)
            if len(self.timeline) > MAX_TIMELINE:
                del self.timeline[:-MAX_TIMELINE]
            self.stats["total_frames"] = int(self.stats.get("total_frames", 0)) + 1
            self.stats["last_frame_at"] = now.isoformat()
            self.stats["unique_frames"] = len({item.get("frame_id") for item in self.timeline if item.get("frame_id")})
            self._save_indexes()
            return {"ok": True, "memory": entry, "stats": dict(self.stats)}

    def _extract_keywords(self, text: str, min_count: int = 2) -> list[str]:
        keywords = []
        keywords.extend(url[:80] for url in re.findall(r"https?://[^\s]+", text))
        chinese = re.findall(r"[\u4e00-\u9fff]{2,4}", text)
        word_counts = Counter(chinese)
        effective_min = 1 if len(text) < 80 else min_count
        keywords.extend(
            word for word, count in word_counts.most_common(20)
            if count >= effective_min
        )
        english = re.findall(r"[A-Z][a-z]{2,}", text)
        keywords.extend(list(dict.fromkeys(english))[:10])
        return list(dict.fromkeys(keywords))[:30]

    def recall(self, query: str = None, limit: int = 10, minutes: int = None) -> list:
        results = []
        now = datetime.now()
        needle = (query or "").lower()
        for entry in reversed(self.timeline):
            try:
                ts = datetime.fromisoformat(entry["timestamp"])
            except (KeyError, ValueError):
                ts = now
            if minutes and (now - ts).total_seconds() > minutes * 60:
                continue
            if needle:
                haystacks = [
                    str(entry.get("ocr_preview") or "").lower(),
                    str(entry.get("description") or "").lower(),
                ]
                haystacks.extend(str(keyword).lower() for keyword in entry.get("keywords") or [])
                if not any(needle in value for value in haystacks):
                    continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results

    def what_i_see_now(self) -> dict:
        if not self.timeline:
            return {"ok": False, "message": "还没有视觉记忆"}
        latest = self.timeline[-1]
        return {
            "ok": True,
            "timestamp": latest.get("timestamp"),
            "channel": latest.get("channel"),
            "size": latest.get("size"),
            "ocr_preview": latest.get("ocr_preview", ""),
            "description": latest.get("description", ""),
            "keywords": latest.get("keywords", []),
            "brightness": latest.get("brightness"),
            "frame_id": latest.get("frame_id"),
            "frame_file": latest.get("frame_file"),
        }

    def today_summary(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        entries = [entry for entry in self.timeline if entry.get("timestamp", "").startswith(today)]
        keywords = []
        urls = set()
        scenes = []
        for entry in entries:
            keywords.extend(entry.get("keywords") or [])
            for url in re.findall(r"https?://[^\s]+", entry.get("ocr_preview", "")):
                urls.add(url[:80])
            if entry.get("description"):
                scenes.append(entry["description"])
        return {
            "ok": True,
            "date": today,
            "total_frames": len(entries),
            "top_keywords": Counter(keywords).most_common(20),
            "urls_seen": list(urls)[:10],
            "native_scenes": scenes[-3:],
            "first_frame": entries[0].get("timestamp") if entries else None,
            "last_frame": entries[-1].get("timestamp") if entries else None,
        }

    def recent_scenes(self, limit: int = 10) -> dict:
        scenes = []
        for entry in self.timeline[-limit:]:
            description = str(entry.get("description") or "")[:200]
            ocr = str(entry.get("ocr_preview") or "")[:160]
            if not description and not ocr:
                continue
            scenes.append({
                "ts": entry.get("timestamp", ""),
                "channel": entry.get("channel", "?"),
                "description": description,
                "ocr": ocr,
                "frame_id": entry.get("frame_id"),
                "frame_file": entry.get("frame_file"),
            })
        return {"ok": True, "count": len(scenes), "scenes": scenes}

    def compress(self, retention: int = 100) -> dict:
        if not self.timeline:
            return {"ok": True, "current": 0, "removed": 0}
        scored = []
        now = datetime.now()
        for index, entry in enumerate(self.timeline):
            try:
                age_hours = (now - datetime.fromisoformat(entry["timestamp"])).total_seconds() / 3600
            except (KeyError, ValueError):
                age_hours = 0
            score = max(0, 1 - age_hours / 24) * 0.3
            score += min(int(entry.get("ocr_length", 0)) / 500, 1.0) * 0.25
            score += min(len(entry.get("keywords") or []) / 10, 1.0) * 0.2
            if entry.get("description"):
                score += 0.15
            if entry.get("brightness") is not None:
                score += 0.1
            scored.append((index, entry, score))
        keep = {index for index, _, _ in sorted(scored, key=lambda item: -item[2])[:retention]}
        removed = len(self.timeline) - len(keep)
        self.timeline = [entry for index, entry, _ in scored if index in keep]
        self.timeline.sort(key=lambda entry: entry.get("timestamp", ""))
        self._save_indexes()
        return {"ok": True, "current": len(self.timeline), "removed": removed}

    def status(self) -> dict:
        return {
            "ok": True,
            "timeline_entries": len(self.timeline),
            "stats": dict(self.stats),
            "memory_dir": str(MEMORY_DIR),
            "frame_limit": MAX_FRAMES,
            "timeline_limit": MAX_TIMELINE,
        }


_memory: Optional[VisualMemory] = None
_memory_lock = threading.Lock()


def get_memory() -> VisualMemory:
    global _memory
    if _memory is None:
        with _memory_lock:
            if _memory is None:
                _memory = VisualMemory()
    return _memory


def remember(capture: dict) -> dict:
    try:
        return get_memory().remember(capture)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:160]}


def recall(query: str = None, limit: int = 10, minutes: int = None) -> list:
    return get_memory().recall(query, limit, minutes)


def what_i_see() -> dict:
    return get_memory().what_i_see_now()


def recent_scenes(limit: int = 10) -> dict:
    return get_memory().recent_scenes(limit)


def today() -> dict:
    return get_memory().today_summary()


def compress(retention: int = 100) -> dict:
    return get_memory().compress(retention)


def status() -> dict:
    return get_memory().status()


__all__ = [
    "VisualMemory",
    "get_memory",
    "remember",
    "recall",
    "what_i_see",
    "recent_scenes",
    "today",
    "compress",
    "status",
]
