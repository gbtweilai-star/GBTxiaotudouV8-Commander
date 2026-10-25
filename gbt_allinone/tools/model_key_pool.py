# gbt-capability: model_key_pool
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""模型密钥池（model_key_pool）· R-H197 只读骨架。

**密钥不是配置，是权限。触手不是身份，是手。**
**一 AI 一号，触手借用，用完归还。超限上报，不自动换号。**

关键区分：**一 AI 一号 ≠ 一触手一号** —— 后者是**批量注册，违规**。
触手是弹性执行体，从**所属 AI 的池**借密钥，用完归还，**不注册新账号**。

不另造 DPAPI 封装（引用 ≠ 复制）：**引用** `deepseek_key._PROFILES`
（盘上已有 `agnes` profile）作为唯一真相源。

六条红线（做成机械闸）：① 一 AI 一号 ② 密钥只存 DPAPI ③ 不共享
④ 不批量注册/不绕验证 ⑤ 超限只上报不换号 ⑥ 新增密钥过 auth_gate。

本骨架只读：**不发密钥、不落盘、不出网**（`register_key` 必须显式 authorized）。
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .. import deepseek_key                      # 引用唯一真相源（不复制 profile 表）

SECRETS_DIR = "store/secrets"
AGNES = {"provider_type": "custom", "base_url": "https://apihub.agnes-ai.com/v1",
         "model": "agnes-2.5-flash"}

_ABUSE_HINTS = ("批量注册", "mass register", "bulk signup", "小号矩阵", "刷号")
_BYPASS_HINTS = ("绕过验证", "绕验证", "bypass", "solve_captcha", "伪装成真实用户")
_SECRET_RX = re.compile(r"\b(?:sk|ak)[-_][A-Za-z0-9_\-]{16,}\b")

RED_LINES = (
    "一 AI 一号，不是一触手一号——触手是临时执行体，不注册独立账号",
    "密钥只存 DPAPI——不许明文落盘、不许贴在对话里",
    "不共享密钥——每个 AI 独立密钥，跨 AI 不共用",
    "必须一人一个（**工程理由，不只是合规**）：共用一把密钥 ⇒ 平台按单账号限流 ⇒ "
    "几个 AI 互相挤占 ⇒ 效率被拖死；所以**并发按 AI 身份计，到顶即拒，不许抢别人的钥匙**",
    "不批量注册、不绕验证——违反合规底座，一票否决",
    "超限只上报，不自动换号——换号是资源分配，必须过大脑",
    "新增密钥过 auth_gate——它不是配置，是权限",
)

REGISTER_SCOPES = ("filesystem_write",)     # 落 DPAPI 文件属"写盘"面


@dataclass(frozen=True)
class ProviderProfile:
    """模型提供商配置（Agnes 已固化）。"""

    provider_type: str = AGNES["provider_type"]
    base_url: str = AGNES["base_url"]
    model: str = AGNES["model"]
    api_key_ref: str = ""            # 指向 DPAPI 容器，**不存明文**
    owner_ai_id: str = ""            # 一 AI 一号


@dataclass
class ApiKeyLease:
    lease_id: str
    key_id: str
    owner_ai_id: str
    tentacle_id: str
    status: str = "leased"           # leased / released / exhausted
    tokens_used: int = 0
    created_at: str = ""


class ModelKeyPool:
    """密钥池（只读骨架 · 内存态）：按 AI 身份分池，触手只借不拥有。"""

    def __init__(self) -> None:
        self.keys: Dict[str, ProviderProfile] = {}     # owner_ai_id -> profile
        self.leases: Dict[str, ApiKeyLease] = {}
        self.usage: Dict[str, int] = {}
        self.limits: Dict[str, int] = {}
        self.concurrency: Dict[str, int] = {}           # owner_ai_id -> 允许的并发租约数

    # ── 红线⑥：新增密钥要过 auth_gate ────────────────────────
    def register_key(self, profile: ProviderProfile, authorized: bool = False,
                     purpose: str = "") -> dict:
        problems = self._scan_text(purpose)
        if problems:
            return {"ok": False, "denied": True, "problems": problems}
        if not authorized:
            return {"ok": False, "denied": True, "rule": "auth_gate_required",
                    "scopes": list(REGISTER_SCOPES),
                    "why": "新增密钥不是配置，是权限：须先过 auth_gate（主人发授权）再落池"}
        if not str(profile.owner_ai_id or "").strip():
            return {"ok": False, "denied": True, "rule": "missing_owner_ai_id",
                    "why": "一 AI 一号：密钥必须挂到某个 AI 身份上，不许挂到触手上"}
        ref = str(profile.api_key_ref or "").strip().replace("\\", "/")
        if not ref.endswith(".dpapi") or SECRETS_DIR not in ref:
            return {"ok": False, "denied": True, "rule": "key_must_be_dpapi",
                    "why": "密钥只存 DPAPI：引用须形如 %s/<name>.dpapi" % SECRETS_DIR}
        exist = self.keys.get(profile.owner_ai_id)
        if exist is not None and exist.api_key_ref != ref:
            return {"ok": False, "denied": True, "rule": "shared_key",
                    "why": "同一 AI 身份的密钥不许被换绑到另一个容器（防两处真相）"}
        self.keys[profile.owner_ai_id] = profile
        return {"ok": True, "readonly": True, "owner_ai_id": profile.owner_ai_id,
                "api_key_ref": ref, "profile_in_registry": self._profile_known(ref)}

    # ── 红线①：触手只借所属 AI 的密钥 ───────────────────────
    def lease(self, tentacle_id: str, owner_ai_id: str) -> dict:
        if not str(owner_ai_id or "").strip():
            return {"ok": False, "denied": True, "rule": "missing_owner_ai_id",
                    "why": "触手必须带 owner_ai_id 才能借（一 AI 一号，不是一触手一号）"}
        profile = self.keys.get(owner_ai_id)
        if profile is None:
            return {"ok": False, "denied": True, "rule": "no_key_for_owner",
                    "why": "该 AI 身份尚未配置密钥 —— 拒执行并上报，不瞎猜"}
        # R-H198 · 「必须一人一个」的机械形态：**并发按 AI 身份计，到顶即拒**
        cap = self.concurrency.get(owner_ai_id) or 0
        active = sum(1 for r in self.leases.values()
                     if r.owner_ai_id == owner_ai_id and r.status == "leased")
        if cap and active >= cap:
            return {"ok": False, "denied": True, "rule": "owner_concurrency_full",
                    "owner_ai_id": owner_ai_id, "active": active, "cap": cap,
                    "why": "该 AI 的并发已到顶（%d/%d）——**不许去抢别人的钥匙**；"
                           "要么等它 release，要么由大脑给它加配（加配=资源分配，要过 auth_gate）"
                           % (active, cap)}
        lid = "lease-%s-%s" % (tentacle_id, owner_ai_id)
        self.leases[lid] = ApiKeyLease(lease_id=lid, key_id=owner_ai_id,
                                       owner_ai_id=owner_ai_id, tentacle_id=tentacle_id,
                                       created_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        self.limits.setdefault(owner_ai_id, 0)
        return {"ok": True, "readonly": True, "lease_id": lid, "owner_ai_id": owner_ai_id,
                "key_ref": profile.api_key_ref, "note": "触手**借用**，用完 release"}

    def borrow(self, owner_ai_id: str, target_ai_id: str, tentacle_id: str = "") -> dict:
        """跨 AI 借用密钥 ⇒ **一律拒**（共用 = 限流 = 互相拖累）。"""
        if str(owner_ai_id).strip() != str(target_ai_id).strip():
            return {"ok": False, "denied": True, "rule": "cross_ai_borrow",
                    "why": "不许跨 AI 借密钥：共用一把密钥会被平台按单账号限流，"
                           "几个 AI 互相挤占 ⇒ 效率被拖死（必须一人一个）"}
        return self.lease(tentacle_id or "t-?", owner_ai_id)

    def set_concurrency(self, owner_ai_id: str, n: int) -> dict:
        """并发上限（**按 AI 身份计**）。加配属资源分配 ⇒ 调用方须已过 auth_gate。"""
        self.concurrency[str(owner_ai_id)] = int(n or 0)
        return {"ok": True, "readonly": True, "owner_ai_id": owner_ai_id,
                "concurrency": self.concurrency[str(owner_ai_id)]}

    def release(self, lease_id: str) -> dict:
        row = self.leases.get(lease_id)
        if row is None:
            return {"ok": False, "denied": True, "rule": "lease_not_found"}
        row.status = "released"
        return {"ok": True, "readonly": True, "lease_id": lease_id, "status": "released"}

    # ── 红线⑤：超限只上报，不自动换号 ───────────────────────
    def report_usage(self, lease_id: str, tokens: int) -> dict:
        row = self.leases.get(lease_id)
        if row is None:
            return {"ok": False, "denied": True, "rule": "lease_not_found"}
        row.tokens_used += int(tokens or 0)
        self.usage[row.owner_ai_id] = self.usage.get(row.owner_ai_id, 0) + int(tokens or 0)
        limit = self.limits.get(row.owner_ai_id) or 0
        over = bool(limit and self.usage[row.owner_ai_id] > limit)
        if over:
            row.status = "exhausted"
        return {"ok": True, "readonly": True, "tokens_used": row.tokens_used,
                "owner_total": self.usage[row.owner_ai_id],
                "limit_exceeded": over,
                "action": "report_only" if over else "none",
                "note": "超限只上报，不自动换号 —— 换号必须走大脑"}

    def set_limit(self, owner_ai_id: str, tokens: int) -> dict:
        self.limits[str(owner_ai_id)] = int(tokens or 0)
        return {"ok": True, "readonly": True, "owner_ai_id": owner_ai_id,
                "limit": self.limits[str(owner_ai_id)]}

    def stats(self) -> dict:
        active_by_owner = {}
        for r in self.leases.values():
            if r.status == "leased":
                active_by_owner[r.owner_ai_id] = active_by_owner.get(r.owner_ai_id, 0) + 1
        return {"ok": True, "readonly": True, "keys_total": len(self.keys),
                "leases_active": sum(1 for r in self.leases.values() if r.status == "leased"),
                "active_by_owner": active_by_owner,
                "concurrency": dict(self.concurrency),
                "by_owner": {k: v.model for k, v in self.keys.items()},
                "usage": dict(self.usage), "limits": dict(self.limits),
                "known_profiles": self._profile_names(),
                "note": "按 AI 身份分池；一触手一号 = 批量注册 = 违规"}

    # ── 内部 ────────────────────────────────────────────────
    def _profile_names(self) -> List[str]:
        return sorted((getattr(deepseek_key, "_PROFILES", {}) or {}).keys())

    def _profile_known(self, ref: str) -> bool:
        name = ref.rsplit("/", 1)[-1]
        return any((v or {}).get("file") == name
                   for v in (getattr(deepseek_key, "_PROFILES", {}) or {}).values())

    @staticmethod
    def _scan_text(text: str) -> List[dict]:
        t = str(text or "")
        low = t.lower()
        out = []
        if any(h in low for h in _ABUSE_HINTS):
            out.append({"rule": "no_bulk_register", "why": "不批量注册（一 AI 一号）"})
        if any(h in low for h in _BYPASS_HINTS):
            out.append({"rule": "no_bypass", "why": "不绕验证（合规底座红线）"})
        if _SECRET_RX.search(t):
            out.append({"rule": "no_plaintext_secret", "why": "密钥不许明文出现"})
        return out


_DEFAULT = ModelKeyPool()


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / redlines / agnes。不落盘、不出网、不发密钥。"""
    op = str(op or "status")
    if op == "status":
        return _DEFAULT.stats()
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES),
                "register_scopes": list(REGISTER_SCOPES),
                "note": "一 AI 一号 ≠ 一触手一号"}
    if op == "agnes":
        return {"ok": True, "readonly": True, **AGNES,
                "api_key_ref": "%s/agnes_api.dpapi" % SECRETS_DIR,
                "profile_known": _DEFAULT._profile_known("agnes_api.dpapi"),
                "note": "Profile 固化；DPAPI 读写引用 deepseek_key._PROFILES（不另造）"}
    raise ValueError("未知 op %r（可用：status/redlines/agnes）" % (op,))


HONEST_BOUNDARY = (
    "密钥池保证『按 AI 身份分配、触手只借不拥有、密钥加密存储』；"
    "它保证不了『免费额度无限』——免费密钥的获取与使用必须遵守平台条款；"
    "『每个 AI 配一个免费密钥算不算违规』由**平台条款**定义，不由我们定义。"
)
