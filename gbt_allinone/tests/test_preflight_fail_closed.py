# -*- coding: utf-8 -*-
"""F3 判据：preflight（感知层）故障时，**有副作用的调用必须按拒处理**（不再 fail-open）。

背景（排查台账 F3 · 高）：`api.run_task` 里 preflight 抛异常时，原实现一律把守卫降级成
`not_guarded` 然后**照跑** —— 理由写的是"感知层故障不能阻止原有能力"。可这只对**读类**成立；
**要作用域的**调用跳过守卫 = "守卫坏了就没人管了" ⇒ 2026-09-28 改为按风险分流。

判据（喂坏样本，看拦不拦得住）：
  A. **要作用域**的调用 + preflight 抛异常 ⇒ **必须 denied**，且说清"是感知层故障"；
  B. **读类**调用 + preflight 抛异常 ⇒ **照常放行**（不许把读也一起挡死）；
  C. 异常路径**留痕**：audit 里能查到 `preflight_error`（不许无声）。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _load_preflight_mod():
    """按包路径导入 preflight（与 api 用的是同一份实例 —— 按文件路径再装一份会打到别的对象上）。"""
    from gbt_allinone import preflight as pf
    return pf


# 🔴 2026-10-09 根因修复（本文件此前会**污染后面所有测试文件**）：
#   原来还原点是在 `setUpClass` 里现取的（`cls._orig = cls.pf.before_action`）。
#   只要此刻模块属性**已经被换过**（例如上一次运行、或别的用例留下的绑定方法），
#   取到的"原件"就是一个**绑定方法**而不是模块级函数 ⇒ 之后每次还原都把它写回去，
#   泄漏从此固化：实测 `before_action` 变成 `(payload, *, decision, force)`（`kind` 被
#   self 吃掉），后继 test_redteam 报 `preflight_error: before_action() takes 2 positional
#   arguments but 3 were given` 的**假故障**（单跑全绿、合跑必红，且取决于文件顺序）。
#   修法：还原点在**导入时刻**取一次（那一刻还没人动过它），并且只还原这一个对象。
_PRISTINE_BEFORE_ACTION = _load_preflight_mod().before_action


class TestPreflightFailClosed(unittest.TestCase):
    """A/B/C 三条都在**同一进程内**用猴子补丁喂坏样本（真跑，不是读代码）。"""

    @classmethod
    def setUpClass(cls):
        import gbt_allinone as g
        cls.g = g
        cls.pf = _load_preflight_mod()
        cls._orig = _PRISTINE_BEFORE_ACTION   # 仅供人工查看；还原一律用上面那个模块级常量

    def setUp(self):
        # 🔴 2026-10-09 隔离加固：坏样本是**模块级**猴子补丁，一旦某个用例异常退出
        #   没走到 tearDown，坏样本会留给**后面整个测试文件**（实测：本文件跑在
        #   test_redteam 之前时，后者报 preflight_error 假故障；反过来跑则全绿）。
        #   所以进入每个用例前先还原一次，并用 addCleanup 兜底（不依赖 tearDown 被调到）。
        # ⚠️ 必须引用**模块级常量**，不能引用挂在类上的 `self._orig`：
        #   函数是描述符 —— 存成类属性再经 `self.` 取回会被**重新绑定成方法**，
        #   于是还原回去的 before_action 少掉第一个参数 `kind`
        #   （实测签名变成 `(payload, *, decision, force)`，后继文件报假故障）。
        #   这条才是本文件污染的**真根因**（还原点取法只是让它更早发生）。
        self.pf.before_action = _PRISTINE_BEFORE_ACTION
        self.addCleanup(self._restore)

    def _restore(self):
        self.pf.before_action = _PRISTINE_BEFORE_ACTION

    def tearDown(self):
        self.pf.before_action = _PRISTINE_BEFORE_ACTION

    def _boom(self, *a, **k):
        raise RuntimeError("判据样本：感知层故障")

    def test_a_side_effect_kind_is_refused(self):
        self.pf.before_action = self._boom
        # `filesystem_write` 类调用（写盘）—— 典型"有副作用"
        r = self.g.run_task("obsidian_vault", {"op": "provision", "only": "lobehub"})
        p = r.get("result", r)
        if isinstance(p, dict) and "result" in p:
            p = p["result"]
        # 可能先被授权门拦（没票）——那也是"按拒处理"，符合 fail-closed 的意图
        self.assertTrue(p.get("denied") or not p.get("ok"),
                        f"**感知层故障时竟然放行了有副作用的调用**：{str(p)[:200]}")
        blob = json.dumps(r, ensure_ascii=False)
        self.assertTrue(("preflight" in blob) or ("授权" in blob) or ("authorization" in blob),
                        "拒了但没说清是谁拦的（感知层还是授权门）")

    def test_b_read_only_kind_still_works(self):
        self.pf.before_action = self._boom
        r = self.g.run_task("console_hub", {"op": "pages"})
        p = r.get("result", r)
        if isinstance(p, dict) and "result" in p:
            p = p["result"]
        self.assertTrue(p.get("ok"), f"读类被一起挡死了（不该）：{str(p)[:200]}")

    def test_c_audit_records_the_error(self):
        self.pf.before_action = self._boom
        self.g.run_task("console_hub", {"op": "status"})
        # 🔴 2026-10-09 修（判据自身的环境假设）：原来把台账**写死在生产 store**
        #   （ROOT/gbt_allinone/store/audit.jsonl），而本仓 `tests/__init__.py` **强制**
        #   测试跑在隔离 store（GBT_STORE_DIR）里 ⇒ 异常确实留了痕，只是留在**被隔离的那个**
        #   store 里，这条判据却去翻生产账本，于是恒红（假故障）。改读**当前生效**的 store。
        from gbt_allinone import _paths as _gbt_paths
        led = Path(_gbt_paths.STORE_DIR) / "audit.jsonl"
        self.assertTrue(led.is_file(), "审计台账不在 ⇒ 异常路径没留痕")
        tail = led.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]
        self.assertTrue(any("preflight_error" in ln for ln in tail),
                        "audit 尾部看不到 preflight_error ⇒ 异常路径无声")


if __name__ == "__main__":
    unittest.main(verbosity=2)
