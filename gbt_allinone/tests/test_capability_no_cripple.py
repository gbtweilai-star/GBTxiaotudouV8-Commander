# -*- coding: utf-8 -*-
"""能力「不限制、不阉割」判据（2026-11-04 主人令）。

## 主人令（逐字）

> 「我的要求就是不限制能力不阉割能力，危险能力和资金转账必须找我那票才行，
>    其他的你按照专业规范推进必须给我仔细看清楚在动手别给我偷懒」

## 翻成五条机检

  A **不许禁用**：`DISABLED_CAPS` 必须为空。禁掉一个能力 = 阉割。
  B **不许留空壳**：`UNIMPLEMENTED_CAPS` 必须为空。只有名字没实现 = 变相阉割。
  C **不许悬空**：每一位的 `handler` 必须真能被解析到（名字漂了就调不动）。
  D **票只发给危险能力与资金转账**：`HUMAN_GATES` 必须是这两类的子集。
     多一个日常能力进去，就等于"开个浏览器也要找主人"—— 那正是令里不许的。
  E **`safe=False` 不许影响可用性**：它只是「自主性边界」（她不自己偷偷跑），
     **不是**「主人也不能用」。所以日常能力位的 restricted 必须是 False。

## 这几条为什么值得单独写

`DISABLED_CAPS` 历史上不是空的。11 个黑客能力（`paywallbuster` / `data_hijack` /
`keylogger` / `device_takeover` / `credential_steal` / `social_eng` …）曾经
**只有名字、没有实现**，靠 `UNIMPLEMENTED_CAPS` 记账顶着。2026-09-25 Owner 令后
全部接上了 `security/redteam.py`（需要人工授权即可用），名字一个没丢。

也就是说：**「阉割」在这个仓真实发生过一次，是被主人令掰回来的。**
所以它必须有一条判据守着，否则会再发生一次。

## 判据红了怎么修

不要为了让它绿而去掉断言，也不要"顺手"把某个能力标成 disabled。
红了说明有人动了三张表之一 —— 要么补实现（B），要么补解析（C），
要么把不该要票的从 HUMAN_GATES 里拿出来（D）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gbt_allinone import caps_registry as CR  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402


# 主人令授权的两类 —— 只有这些 scope 可以要票。
# 多一个进来，就是「限制能力」；少一个，就是「危险动作漏了票」。
DANGEROUS_SCOPES = {
    "privacy_read",        # 读隐私
    "process_execute",     # 执行任意代码
    "network_private",     # 打内网
    "osint_private",       # 情报侦察
    "remote_device",       # 控制远端设备
    "deploy_publish",      # 发布上线
    "deploy_force",        # 强制发布
}
MONEY_SCOPES = {
    "transfer",            # 真金白银
    "external_llm",        # 把内容发给外部模型（出去的收不回）
    "data_export",         # 数据外发
}
ALLOWED_GATES = DANGEROUS_SCOPES | MONEY_SCOPES


# ── A · 不许禁用 ────────────────────────────────────────────────────────────
class TestNoDisable(unittest.TestCase):
    """A · 禁掉一个能力就是阉割。"""

    def test_disabled_caps_is_empty(self):
        disabled = dict(CR.DISABLED_CAPS or {})
        self.assertEqual(disabled, {},
                         "有 %d 个能力被禁用了 —— 主人令「不限制能力不阉割能力」：\n%s"
                         % (len(disabled),
                            "\n".join("  - %s" % k for k in list(disabled)[:20])))


# ── B · 不许留空壳 ──────────────────────────────────────────────────────────
class TestNoEmptyShell(unittest.TestCase):
    """B · 只有名字、没有实现 = 变相阉割。"""

    def test_unimplemented_caps_is_empty(self):
        un = dict(CR.UNIMPLEMENTED_CAPS or {})
        self.assertEqual(un, {},
                         "有 %d 个能力只有名字、没有实现（2026-09-25 令要求全部接实现）：\n%s"
                         % (len(un),
                            "\n".join("  - %s" % k for k in list(un)[:20])))

    def test_benign_caps_not_empty(self):
        """正控：如果 BENIGN_CAPS 整体消失，上面两条会**假绿**。"""
        self.assertGreater(len(CR.BENIGN_CAPS or {}), 400,
                           "BENIGN_CAPS 只剩 %d 项 —— 判据在空集上恒真，等于没有"
                           % len(CR.BENIGN_CAPS or {}))


# ── C · 不许悬空 ────────────────────────────────────────────────────────────
class TestNoDanglingHandler(unittest.TestCase):
    """C · 每一位的 handler 必须真能被解析到。"""

    def test_every_cap_has_handler(self):
        missing = [k for k, v in (CR.BENIGN_CAPS or {}).items()
                   if not str((v or {}).get("handler") or "").strip()]
        self.assertEqual(missing, [],
                         "这些位没有 handler，调了必然 500：%r" % missing[:20])

    def test_handler_names_resolve(self):
        """handler 名必须能解析到（同名模块 or api 分派里有分支）。

        这里用**静态可判**的方式：handler 名要么是 `gbt_allinone.<name>` 模块，
        要么在 api.py 的分派里被提到。解析不到 = 名字漂了 = 这个位成了孤儿。
        """
        import importlib.util

        caps = CR.BENIGN_CAPS or {}
        api_src = (ROOT / "gbt_allinone" / "api.py").read_text(encoding="utf-8")

        dangling = []
        for name, meta in caps.items():
            h = str((meta or {}).get("handler") or "").strip()
            if not h:
                continue
            # ① 有同名模块
            if importlib.util.find_spec("gbt_allinone.%s" % h) is not None:
                continue
            # ② 有同名子包模块（tools / tentacle / security）
            if any(importlib.util.find_spec("gbt_allinone.%s.%s" % (pkg, h)) is not None
                   for pkg in ("tools", "tentacle", "security", "llm")):
                continue
            # ③ 在 api.py 的分派里出现过
            if ('"%s"' % h) in api_src or ("'%s'" % h) in api_src:
                continue
            dangling.append((name, h))

        self.assertEqual(dangling, [],
                         "这些位的 handler 解析不到（孤儿）：%r" % dangling[:15])


# ── D · 票只发给危险能力与资金转账 ─────────────────────────────────────────
class TestTicketOnlyForDanger(unittest.TestCase):
    """D · `HUMAN_GATES` 必须是「危险能力 + 资金转账」的子集。

    多一个日常能力进来 ⇒ 开个浏览器也要找主人 ⇒ 正是主人令不许的「影响工作效率」。
    """

    def test_human_gates_subset_of_allowed(self):
        gates = set(policy.HUMAN_GATES or ())
        extra = gates - ALLOWED_GATES
        self.assertEqual(extra, set(),
                         "HUMAN_GATES 里有不该要票的 scope：%r\n"
                         "（主人令：只有危险能力和资金转账要票，其他按专业规范推进）"
                         % sorted(extra))

    def test_no_dangerous_scope_forgotten(self):
        """反向：危险/转账类 scope 一个都不许漏票。"""
        gates = set(policy.HUMAN_GATES or ())
        missing = ALLOWED_GATES - gates
        self.assertEqual(missing, set(),
                         "这些危险/转账 scope 漏了票：%r" % sorted(missing))

    def test_mechanism_gates_is_empty(self):
        """机制层自保：2026-11-03 令已全部免票 ⇒ 必须是空集。"""
        self.assertEqual(set(getattr(policy, "MECHANISM_GATES", ()) or ()), set(),
                         "MECHANISM_GATES 不为空 —— 机制件又要票了")


# ── E · safe=False 只是自主性边界，不是可用性开关 ──────────────────────────
class TestSafeIsAutonomyNotAvailability(unittest.TestCase):
    """E · `safe=False` 不许把能力挡在主人之外。

    `safe` 的语义（2026-11-04 逐点核对）：
      · cross_scan 深度扫描时跳过探测（只影响"她自己去探"，不影响"主人去用"）
      · profession_router 把候选分成 safe / needs-ticket 两堆（**都留着**）
      · growth_hooks 自主进化时只自动做 safe 的，其余待主人点
      · cloud_llm 只影响 status 显示 ok / warn
    **api.run_task 不读 safe** —— 所以它不参与分派。

    这条钉的是：那些日常能力位（不含危险/转账 scope 的）**restricted 必须 False**。
    """

    def test_daily_caps_are_not_gated(self):
        日常 = []
        gated = []
        for name, meta in sorted((CR.BENIGN_CAPS or {}).items()):
            try:
                d = policy.evaluate(name, {})
            except Exception:                                     # noqa: BLE001
                continue
            scopes = set(d.scopes or ())
            if scopes & ALLOWED_GATES:
                continue                    # 含危险/转账 scope ⇒ 该要票，跳过
            if bool(d.restricted):
                gated.append(name)
            else:
                日常.append(name)

        self.assertEqual(gated, [],
                         "这些位不含任何危险/转账 scope，却要票 —— 这是限制能力：\n%s"
                         % "\n".join("  - %s" % n for n in gated[:20]))
        # 正控：绝大多数位必须是免票的，否则上面那条在空集上恒真
        self.assertGreater(len(日常), 300,
                           "只数出 %d 个免票位 —— 判据可能没真跑" % len(日常))

    def test_safe_flag_does_not_change_gate(self):
        """同一个位，`safe` 是 True 还是 False，**不许**影响要不要票。"""
        gates = set(policy.HUMAN_GATES or ())
        bad = []
        for name, meta in (CR.BENIGN_CAPS or {}).items():
            safe = bool((meta or {}).get("safe"))
            try:
                d1 = policy.evaluate(name, {})
            except Exception:                                     # noqa: BLE001
                continue
            # 结论只取决于 scope 是否命中 HUMAN_GATES
            expect = bool(set(d1.scopes or ()) & gates)
            if bool(d1.restricted) != expect:
                bad.append((name, safe, bool(d1.restricted), expect))
        self.assertEqual(bad, [],
                         "restricted 与 HUMAN_GATES 不一致（说明有别的因素在决定票）：%r"
                         % bad[:10])


if __name__ == "__main__":
    unittest.main(verbosity=2)
