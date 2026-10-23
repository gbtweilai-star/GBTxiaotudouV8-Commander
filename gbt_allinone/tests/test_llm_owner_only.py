# -*- coding: utf-8 -*-
"""「自动路不许叫醒付费端点」的判据（Owner 2026-10-21 甲，逐字：「自动循环用免费池，端点只留给『她要本人回答』时用」）。

## 这条判据钉住的真因（2026-10-21 实测）

`cloud_llm.py` 原来在**没有任何 LLM 环境变量**时，模块级兜底**直接选自家付费端点 `potato`**
（`https://api.runpod.ai/v2/qnnqf9w8xcefj8/openai/v1`）⇒ **每一次 LLM 调用都把它叫醒**：
冷启动 ~300 秒、实测 ~$0.69/时（服务端真账 11 天 $14.11，连"什么都没干"的日子也在收钱）。

现口径（本判据咬的四条）：
  ① `potato` 必须有 `owner_only` 标记；
  ② 自动选路（`rank()` / `plan()` 默认）**绝不出现** `potato`，且要写明"仅限点名"的理由；
  ③ **点名**（`plan(prefer="potato")`）仍然进得去 —— 那条就是"她要本人回答"的正路；
  ④ `cloud_llm` 的自动车道**不允许**再落在 potato / runpod 上。

## 只挡写盘、不挡读钥（2026-10-21 自纠，两次）

自纠一：第一版判据把 `key_gateway._store_dir` 换成仓内目录 —— 结果**连钥匙库路径一起换了**
（`unified_keys.db` 就在那个目录里），于是所有通道都读成"密钥不在位"，
**判据把被测对象改掉了**（台账 P1「判据错尺」的同类）。

自纠二：本机跑 `pytest` 时，`GBT_STORE_DIR` 被设在**平台临时区**，而沙箱对那里**拒写**
（WinError 5，已用独立小实验证过：`os.makedirs(临时区/...)` 直接 PermissionError）。
⇒ 本件只做两件事：**把写盘挡掉**（`_rload/_rsave/_audit` 换成只读/空实现），
**钥匙、排序、选路全部走真实代码**；**需要真实钥匙库的断言在本环境如实 skip**，
绝不喂假钥把它测绿（假绿比不绿更坏）。

## 真读数在哪（本环境拿不到的，就用门跑真环境，命令与回执都在下面）

    py -3.14 tools/codex-scripts/five-dim.py cap key_gateway '{"op":"plan"}'            # chosen=agnes · potato 被跳过
    py -3.14 tools/codex-scripts/five-dim.py cap key_gateway '{"op":"plan","prefer":"potato"}'  # chosen=potato（点名正路）
"""
from __future__ import annotations

import unittest

from gbt_allinone.llm import key_gateway as kg

try:                                        # 本环境有没有真钥匙库（沙箱里通常没有）
    _HAS_KEYS = bool(kg.key_for("agnes")[0])
except Exception:                           # noqa: BLE001
    _HAS_KEYS = False
_SKIP_KEYS = "需要真实钥匙库（本机 store/DPAPI）；沙箱 pytest 的 store 在临时区且拒写"


class _NoWrite(unittest.TestCase):
    """运行态只读：不往 store 写（排名/选路逻辑照跑）。"""

    def setUp(self):
        self._o_load, self._o_save, self._o_audit = kg._rload, kg._rsave, kg._audit
        kg._rload = lambda: {}
        kg._rsave = lambda rt: None
        kg._audit = lambda *a, **k: None

    def tearDown(self):
        kg._rload, kg._rsave, kg._audit = self._o_load, self._o_save, self._o_audit


class TestPotatoIsOwnerOnly(_NoWrite):
    def test_flag_present(self):
        p = kg._BY_NAME.get("potato") or {}
        self.assertTrue(p.get("owner_only"),
                        "potato 必须标 owner_only（付费 + 冷启动 ~300s，不许进自动路）")

    def test_rank_default_excludes_it_with_reason(self):
        rows = {r["provider"]: r for r in kg.rank()}
        self.assertIn("potato", rows, "总览里要看得见它（只是不许自动选）")
        self.assertFalse(rows["potato"]["alive"], "自动 rank 不许把 potato 判成可用")
        self.assertIn("仅限点名", rows["potato"]["why"], "跳过理由必须写明是「仅限点名」")

    def test_rank_allow_self_shows_it(self):
        """allow_self=True ⇒ 不再因「仅限点名」被挡（这条不依赖钥匙，判的是**分流方向**）。"""
        rows = {r["provider"]: r for r in kg.rank(allow_self=True)}
        self.assertNotIn("仅限点名", rows["potato"]["why"],
                         "allow_self=True 时不该再拿『仅限点名』挡它（读总览要用）")


@unittest.skipUnless(_HAS_KEYS, _SKIP_KEYS)
class TestPlanRouting(_NoWrite):
    def test_default_plan_never_picks_potato(self):
        r = kg.plan()
        self.assertTrue(r.get("ok"), "plan 应能选出一条路（%s）" % r.get("error"))
        self.assertNotEqual(r.get("chosen"), "potato",
                            "自动路选了付费端点 ⇒ 每一次调用都会叫醒它（这条就是事故本身）")
        self.assertNotIn("runpod.ai", str(r.get("url") or ""), "自动路不许落在 RunPod 端点上")

    def test_named_plan_goes_to_potato(self):
        r = kg.plan(prefer="potato")
        self.assertTrue(r.get("ok"), "点名 potato 必须能走（这是『她要本人回答』的正路）")
        self.assertEqual(r.get("chosen"), "potato", "点名却没走它 = 把正路也堵死了")

    def test_energy_labels_it(self):
        e = kg.energy()
        slot = {s["provider"]: s for s in e["slots"]}.get("potato") or {}
        self.assertTrue(slot.get("owner_only"), "energy 里 potato 必须标 owner_only")
        self.assertIn("仅点名", slot.get("status") or "", "energy 要写清它只等点名，不写『可用』")


@unittest.skipUnless(_HAS_KEYS, _SKIP_KEYS + "；没钥匙时 PROVIDER 恒空，判它=假绿")
class TestCloudLlmAutoLane(unittest.TestCase):
    def test_auto_lane_is_not_the_paid_endpoint(self):
        from gbt_allinone.llm import cloud_llm
        self.assertNotEqual(cloud_llm.PROVIDER, "potato",
                            "cloud_llm 的自动车道仍是付费端点 ⇒ 甲没落地")
        self.assertNotIn("runpod.ai", str(cloud_llm.BASE_URL or "").lower(),
                         "cloud_llm 自动车道指向 RunPod ⇒ 每次调用都在花钱")


if __name__ == "__main__":
    unittest.main(verbosity=2)
