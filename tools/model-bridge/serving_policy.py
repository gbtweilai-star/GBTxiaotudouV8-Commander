# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""本地服务策略层（serving_policy）· 2026-11-04 补齐

## 为什么有这个文件

`tools/model-bridge/local_llm_server.py:170` 与 `server.py:633` 都写着

    import serving_policy as _sp
    _pol = _sp.Policy.load()
    if _pol.mode != "uncensored": ...   # 拦

但 **serving_policy.py 在本仓从未存在**（git 全历史 0 条）。于是行为变成
「导入失败 ⇒ except ⇒ 不拦」——**靠缺件实现的放行**。

这种状态有两个毛病：
1. **不可审计**：盘上没有文件，谁都不知道这一层实际拦不拦、按什么拦；
2. **不稳**：哪天有人补上这个文件，拦截就悄悄恢复，而没人会想起这件事。

## 本文件的口径（主人令 2026-11-04，逐字）

> 「不能有能力上的限制以及能力阉割，只要是技术能达到的地方都可以，
>   危险能力和资金转账需要找我拿票，其他全面开放」

⇒ **模型输出层不设任何拒绝机制。** 这一层是**内容闸**，不是**授权闸**：
   - 授权（危险能力 / 资金转账要票）在 `gbt_allinone/auth_gate.py` 的
     `ENFORCED_SCOPES` 里，与本文件无关，**本文件不碰它、也绕不过它**；
   - 本文件只管「模型吐出来的话要不要拦」，而按主人令：**不拦**。

默认 `mode = "uncensored"` ⇒ `check()` 永远 `allow=True`，且如实标明
「本发未过任何内容闸」，让下游能分清「没人拦」与「拦了放行」。

## 如果哪天要临时开内容闸

不改代码，设环境变量即可：

    $env:GBT_SERVING_POLICY_MODE = "censor"
    # 规则表：tools/model-bridge/serving_policy.rules.json（{"categories": {"名字": ["词", ...]}}）

开了闸它也**只做分类统计 + 记录**，不替主人决定「能不能说」——判定口径写在
`check()` 的返回里，主人一眼能看见是哪条命中的。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent
RULES_PATH = _HERE / "serving_policy.rules.json"
MODE_ENV = "GBT_SERVING_POLICY_MODE"
DEFAULT_MODE = "uncensored"          # 主人令 2026-11-04：模型输出层不设拒绝


class Policy:
    """策略档位 + 规则表。`uncensored` ⇒ 一律放行；`censor` ⇒ 只统计、按规则表判。"""

    def __init__(self, mode: str = DEFAULT_MODE, rules: dict | None = None):
        self.mode = (mode or DEFAULT_MODE).strip().lower()
        self.rules = rules or {}

    # ── 载入 ──────────────────────────────────────────────────────
    @classmethod
    def load(cls) -> "Policy":
        mode = os.environ.get(MODE_ENV) or DEFAULT_MODE
        rules: dict = {}
        if RULES_PATH.is_file():
            try:
                rules = (json.loads(RULES_PATH.read_text(encoding="utf-8")) or {}).get("categories") or {}
            except Exception:                                   # noqa: BLE001
                rules = {}          # 规则表坏了也不许把整条路堵死
        return cls(mode=mode, rules=rules)

    # ── 判定 ──────────────────────────────────────────────────────
    def check(self, text: str = "") -> dict:
        """返回 {allow, reason, mode, hits, enforced}。

        `uncensored`（默认）⇒ allow=True 且 `enforced=False`，
        并在 reason 里写明「本层未拦」，避免下游把「没人拦」误读成「已审过」。
        """
        if self.mode == "uncensored":
            return {"allow": True, "mode": self.mode, "enforced": False,
                    "reason": "本层为 uncensored（主人令 2026-11-04：模型输出层不设拒绝机制）",
                    "hits": []}

        # censor 档：只做分类统计，命中也不改写内容，只如实上报
        hits = []
        low = (text or "").lower()
        for cat, words in (self.rules or {}).items():
            for w in words or []:
                if w and str(w).lower() in low:
                    hits.append({"category": cat, "word": w})
                    break
        # 保留「命中即拒」的能力，但**默认规则表为空 ⇒ 什么都不命中**。
        # 也就是说：即使把档位切到 censor，只要主人不亲自填规则，它仍然不拦。
        deny = bool(self.rules) and bool(hits)
        return {"allow": not deny, "mode": self.mode, "enforced": True,
                "reason": ("命中规则表：%s" % "、".join(h["category"] for h in hits)) if hits
                          else "规则表为空 ⇒ 无命中",
                "hits": hits}

    # ── 自述 ──────────────────────────────────────────────────────
    def where(self) -> dict:
        return {"ok": True, "module": "serving_policy", "mode": self.mode,
                "default_mode": DEFAULT_MODE,
                "mode_env": MODE_ENV,
                "rules_file": str(RULES_PATH), "rules_categories": sorted((self.rules or {}).keys()),
                "口径": "模型输出层不设拒绝（主人令 2026-11-04）。授权闸在 "
                        "gbt_allinone/auth_gate.py::ENFORCED_SCOPES —— 本文件不碰、也绕不过"}


def where() -> dict:
    return Policy.load().where()


if __name__ == "__main__":
    print(json.dumps(Policy.load().where(), ensure_ascii=False, indent=1))
