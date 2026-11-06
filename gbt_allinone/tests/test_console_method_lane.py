"""`/api/chat` → `_chat` 的触手方法直达 · 回归（2026-11-05）。

为什么要单独钉：`tools/console-server.py` 不是包模块，任何单元测试都碰不到它，
于是「对话入口到底会不会直达」长期只能靠手工 POST 验。这里用 importlib 按路径
加载它，直接调 `_chat`。

钉两件事：
  ① 只读句（读剪贴板 / 有没有弹窗）走 `via=method-direct`，不经模型；
  ② 动手句（写剪贴板 / 操作控件 / 往控件里输入）**绝不**走 method-direct ——
     它们是 `brain_exec` 白名单血账里的那几条，旧版按邻域放行时会被直接执行。

为了让「没直达」的用例不真跑 20 秒模型，这里把模型和其余三条快车道全部关掉/打桩。
同时把 `operator_index.log_gate` 打桩 —— 否则测试会往生产台账里写探针记录。
"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gbt_allinone import operator_index as OI  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "console_server_under_test", str(_ROOT / "tools" / "console-server.py"))
CS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(CS)

_ENV_KEYS = ("GBT_CAPABILITY_ROUTER", "GBT_TACTILE_PULSE", "GBT_TACTILE_HINT",
             "GBT_OPERATOR_HINT", "GBT_METHOD_LANE")


class ChatMethodLaneTests(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.get(k) for k in _ENV_KEYS}
        for k in ("GBT_CAPABILITY_ROUTER", "GBT_TACTILE_PULSE",
                  "GBT_TACTILE_HINT", "GBT_OPERATOR_HINT"):
            os.environ[k] = "0"
        os.environ.pop("GBT_METHOD_LANE", None)

        # ① 台账不许被测试污染
        self._log_gate = OI.log_gate
        OI.log_gate = lambda *a, **k: None

        # ② 模型路径打成桩：走到这里就说明「没直达」，回一句话即可，不跑 20 秒
        from gbt_allinone import omni_plug as OP
        from gbt_allinone import energy_core as EC
        self._plug = OP.plug_and_run
        self._think = EC.think
        OP.plug_and_run = lambda *a, **k: {"ok": False, "text": ""}
        EC.think = lambda *a, **k: {"ok": False, "text": "<model-stub>", "via": "stub"}

    def tearDown(self):
        OI.log_gate = self._log_gate
        from gbt_allinone import omni_plug as OP
        from gbt_allinone import energy_core as EC
        OP.plug_and_run = self._plug
        EC.think = self._think
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_read_only_phrases_take_method_direct(self):
        for q, want in (("读一下剪贴板里的内容", "clipboard_read"),
                        ("有没有弹窗冒出来", "detect_dialog")):
            r = CS._chat(q, use_capabilities=True)
            self.assertEqual(r.get("via"), "method-direct", (q, r.get("via")))
            cap = r.get("capability") or {}
            self.assertEqual(cap.get("method"), want, q)
            self.assertEqual(cap.get("gate"), "read_only_whitelist", q)

    def test_action_phrases_never_take_method_direct(self):
        for q in ("写剪贴板", "操作控件", "往控件里输入"):
            r = CS._chat(q, use_capabilities=True)
            self.assertNotEqual(r.get("via"), "method-direct", q)

    def test_switch_off(self):
        os.environ["GBT_METHOD_LANE"] = "0"
        r = CS._chat("读一下剪贴板里的内容", use_capabilities=True)
        self.assertNotEqual(r.get("via"), "method-direct")


    def test_block_state_three_way(self):
        """缺票 / 缺件 / 真失败必须分开报 —— 缺件说成缺票是本仓明令禁止的混装。

        2026-11-05 实测血账：产品目录 pyembed 缺 pyperclip，`clipboard_read` 返回
        `rule=dependency_unavailable, missing=[pyperclip]`，旧回执写成
        「缺授权：pyperclip」—— 把缺件说成了缺票。
        """
        dep = CS._method_block_state(
            {"status": "ok"},
            {"ok": False, "unavailable": True, "denied": False,
             "rule": "dependency_unavailable", "missing": ["pyperclip"],
             "why": "pyperclip not installed"})
        self.assertEqual(dep["state"], "needs_dependency")
        self.assertIn("缺依赖", dep["line"])
        self.assertIn("pyperclip", dep["line"])
        self.assertNotIn("缺授权", dep["line"])

        den = CS._method_block_state(
            {"status": "denied"}, {"ok": False, "missing_scopes": ["os:control"]})
        self.assertEqual(den["state"], "denied")
        self.assertIn("缺授权", den["line"])
        self.assertIn("os:control", den["line"])

        bad = CS._method_block_state({"status": "ok"}, {"ok": False, "why": "boom"})
        self.assertEqual(bad["state"], "failed")


if __name__ == "__main__":
    unittest.main()
