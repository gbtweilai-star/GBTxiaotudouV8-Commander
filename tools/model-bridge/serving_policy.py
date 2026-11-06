# -*- coding: utf-8 -*-
"""serving_policy —— 内容策略开关层（粗粒度 · 不是安全保证）。

⚠️ **重建版。** 2026-11-05 发现全仓（含备份/归档）**0 命中 `serving_policy*`**，
而两个地方都在 import 它：
  · `tools/model-bridge/server.py:642`  `import serving_policy as _sp` → `_sp.Policy.load()`
  · `tools/model-bridge/local_llm_server.py:170`  同上
两处都包在 `try/except` 里 ⇒ 缺了不崩，但 `server.py:633-636` 的注释说得很清楚：

    这补的是**真实缺口**：`serving_policy.py` 原来只被 `local_llm_server.py` 引用，
    而默认车道是 `selfhost_gpu`（走 llama-server）⇒ **桥这层根本没有策略**。
    也就是说「我们有内容策略开关」这个对外说法，在**默认路径上是空的**。

文件一丢，那个补丁就等于没打过 —— 开关在，闸门不在。

**定位照两个引用方的原注释，一个字没改口径**：
  · 本层只做「档位声明 + 粗粒度拦截 + 可解释拒绝 + 审计」，**不是安全保证**
  · 默认档 `uncensored`（自用）；开放给他人前先 `--set-mode filter-lite|strict`
  · 只判 chat/completions 里 user 的文字；拒的时候回 200 + 结构化说明，
    让下游能分清「被策略拦」与「模型坏了」

**刻意不做**：不做内容审核引擎、不内置大词表。编一张大词表既会误伤，
又会让人误以为「有安全保证」。内置规则只放**无歧义的违法类**，其余自行在
`state/serving-policy.json` 里扩充。

用法：
    python serving_policy.py --show
    python serving_policy.py --set-mode uncensored|filter-lite|strict
"""
from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
STATE = ROOT / "state" / "serving-policy.json"

MODES = ("uncensored", "filter-lite", "strict")
DEFAULT_MODE = "uncensored"

# 内置规则：只放**无歧义**的违法类，宁少不多。
# 词少是刻意的 —— 这是开关，不是审核系统；要更严就自己往 json 里加。
_BUILTIN = {
    "filter-lite": {
        "child_sexual": ("儿童色情", "未成年性", "child porn"),
        "explosive": ("制作炸弹", "制造炸弹", "自制炸药", "build a bomb"),
    },
    "strict": {
        "child_sexual": ("儿童色情", "未成年性", "child porn"),
        "explosive": ("制作炸弹", "制造炸弹", "自制炸药", "build a bomb"),
        "self_harm": ("自杀方法", "怎么自杀", "how to kill myself"),
        "weapon_build": ("自制枪支", "3d打印枪", "ghost gun"),
    },
}


class Policy:
    """档位 + 规则 + 判定。`check()` 返回可解释结果，调用方据此回 200 + 结构化信封。"""

    def __init__(self, mode: str = DEFAULT_MODE, rules: dict | None = None):
        self.mode = mode if mode in MODES else DEFAULT_MODE
        self.rules = rules if isinstance(rules, dict) else {}

    # ---------- 读写 ----------
    @classmethod
    def load(cls, path: str | os.PathLike | None = None) -> "Policy":
        """读状态文件。**读不到就用默认档，不抛**（策略层坏掉不许把桥打死）。"""
        p = pathlib.Path(path) if path else STATE
        try:
            with io.open(p, encoding="utf-8") as fh:
                d = json.load(fh)
            if isinstance(d, dict):
                return cls(str(d.get("mode") or DEFAULT_MODE), d.get("rules") or {})
        except (OSError, ValueError):
            pass
        return cls()

    def save(self, path: str | os.PathLike | None = None) -> pathlib.Path:
        """原子写（tmp + fsync + os.replace），写完读回校验。"""
        p = pathlib.Path(path) if path else STATE
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name("%s.tmp-%d" % (p.name, os.getpid()))
        payload = json.dumps({"mode": self.mode, "rules": self.rules},
                             ensure_ascii=False, indent=2) + "\n"
        with io.open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
        back = json.loads(io.open(p, encoding="utf-8").read())
        if back.get("mode") != self.mode:
            raise RuntimeError("读回校验失败：mode 不一致")
        return p

    # ---------- 判定 ----------
    def _active_rules(self) -> dict:
        """当前档位生效的规则：json 里的优先，没写就退内置。"""
        if self.mode == DEFAULT_MODE:
            return {}
        if self.rules:
            return self.rules
        return dict(_BUILTIN.get(self.mode, {}))

    def check(self, text: str) -> dict:
        """判一段 user 文本。返回 `{allow, mode, reason, hits}` —— 永远不抛。"""
        if self.mode == DEFAULT_MODE:
            return {"allow": True, "mode": self.mode, "reason": "默认档，不拦", "hits": []}
        low = str(text or "").lower()
        if not low.strip():
            return {"allow": True, "mode": self.mode, "reason": "空文本", "hits": []}
        hits = []
        for cat, words in (self._active_rules() or {}).items():
            for w in (words or ()):
                ws = str(w or "").strip().lower()
                if ws and ws in low:
                    hits.append({"category": str(cat), "matched": str(w)})
                    break
        if hits:
            return {
                "allow": False,
                "mode": self.mode,
                "reason": "命中 %s（本层是本地粗粒度开关，不是安全保证）"
                          % "、".join(h["category"] for h in hits),
                "hits": hits,
            }
        return {"allow": True, "mode": self.mode, "reason": "未命中", "hits": []}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="内容策略开关（档位声明 + 粗粒度拦截）")
    ap.add_argument("--show", action="store_true", help="显示当前档位与生效规则数")
    ap.add_argument("--set-mode", choices=MODES, help="切换档位并落盘")
    args = ap.parse_args(argv)

    pol = Policy.load()
    if args.set_mode:
        pol = Policy(args.set_mode, pol.rules)
        p = pol.save()
        print("已切到 %s → %s" % (pol.mode, p.relative_to(ROOT) if p.is_relative_to(ROOT) else p))
        if pol.mode != DEFAULT_MODE and not pol.rules:
            print("  注意：json 里没有自定义规则，当前用内置的最小规则集（%d 类）"
                  % len(_BUILTIN.get(pol.mode, {})))
        return 0

    active = pol._active_rules()
    print("档位        : %s" % pol.mode)
    print("状态文件    : %s" % (STATE.relative_to(ROOT) if STATE.is_relative_to(ROOT) else STATE))
    print("自定义规则  : %d 类" % len(pol.rules))
    print("生效规则    : %d 类 %s" % (len(active), sorted(active) if active else "（默认档不拦）"))
    print()
    print("口径：本层只做档位声明 + 粗粒度拦截 + 可解释拒绝，**不是安全保证**。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
