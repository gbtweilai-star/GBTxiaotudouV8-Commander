# -*- coding: utf-8 -*-
"""agnes_keys —— Agnes apihub 钥匙库 + 限流自动切换器

从桌面上的「图片生成视频生成密钥库.txt」提取全部 sk- 钥匙，按序轮转；
当某把钥匙收到 429（PROMOTION_MODEL_LIMIT_REACHED / 上游限流）时，把它放进
冷却并自动切下一把；全部钥匙都冷却/失败时才返回失败。只报索引与尾号，
绝不回显钥匙明文。

环境变量：
    AGNES_KEY_FILE   密钥库 txt 路径（默认 ~/Desktop/图片生成视频生成密钥库.txt）
    AGNES_KEY_COOLDOWN_S   429 后冷却秒数（默认 60）
"""
from __future__ import annotations

import os
import pathlib
import re
import time

DEFAULT_KEY_FILE = pathlib.Path.home() / "Desktop" / "图片生成视频生成密钥库.txt"
SK_RE = re.compile(r"\b(sk-[A-Za-z0-9]{20,})\b")


def load_keys(path=None) -> list:
    """从 txt 里按原文顺序提取全部 sk- 钥匙并去重。"""
    p = pathlib.Path(os.environ.get("AGNES_KEY_FILE") or path or DEFAULT_KEY_FILE)
    if not p.is_file():
        return []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return []
    seen = []
    for m in SK_RE.finditer(text):
        k = m.group(1)
        if k not in seen:
            seen.append(k)
    return seen


def _tail(key: str) -> str:
    return key[-6:] if key else ""


class KeyRing:
    """按序轮转的钥匙环，带 429 冷却。"""

    def __init__(self, keys=None, cooldown_s: float = 60.0):
        self.keys = list(keys or load_keys())
        self.cooldown_s = float(cooldown_s or os.environ.get("AGNES_KEY_COOLDOWN_S") or 60.0)
        self.index = 0
        self.state = {
            i: {"rate_limited_until": None, "fail_count": 0, "last_used": None}
            for i in range(len(self.keys))
        }

    def __len__(self):
        return len(self.keys)

    def next_key(self):
        """返回 (key, idx) 下一把未冷却的钥匙并推进索引；全部冷却则 (None, None)。"""
        if not self.keys:
            return None, None
        n = len(self.keys)
        start = self.index
        while True:
            idx = self.index
            self.index = (idx + 1) % n
            st = self.state[idx]
            rlu = st["rate_limited_until"]
            if rlu is None or time.time() >= rlu:
                st["last_used"] = time.time()
                return self.keys[idx], idx
            if self.index == start:
                break
        return None, None

    def mark_rate_limited(self, idx: int, retry_after_s: float | None = None):
        """收到 429：冷却该把，下次 next_key() 自动跳过。"""
        st = self.state[idx]
        st["fail_count"] += 1
        st["rate_limited_until"] = time.time() + (retry_after_s or self.cooldown_s)
        st["last_used"] = time.time()

    def mark_success(self, idx: int):
        st = self.state[idx]
        st["fail_count"] = 0
        st["rate_limited_until"] = None
        st["last_used"] = time.time()

    def active_count(self) -> int:
        now = time.time()
        return sum(1 for i in range(len(self.keys))
                   if self.state[i]["rate_limited_until"] is None
                   or time.time() >= self.state[i]["rate_limited_until"])

    def summary(self) -> list:
        now = time.time()
        out = []
        for i, k in enumerate(self.keys):
            st = self.state[i]
            rlu = st["rate_limited_until"]
            out.append({
                "idx": i,
                "key_tail": _tail(k),
                "cooling_down": bool(rlu and now < rlu),
                "rate_limited_until": rlu,
                "fail_count": st["fail_count"],
                "last_used": st["last_used"],
            })
        return out


def build_ring() -> KeyRing:
    return KeyRing()
