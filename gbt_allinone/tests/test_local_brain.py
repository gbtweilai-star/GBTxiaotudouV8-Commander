# -*- coding: utf-8 -*-
"""本地原生脑 · 带牙用例（R-H227）。

① 定位：本地模型 = **皮层**（可换）；主机 = **纪律层**（不可换）；
② 五层链路齐，且**模型只做第 2 与第 8 步**（中间全走原生栈）；
③ 五条红线各有机械闸：
   不许直接执行命令 / 不可逆必卡 / 缺参不许猜 / 每次留痕 / 身份不许改写；
④ 硬件门槛与选型是官方口径（12G+32G 起步 · Qwen2.5-7B-Instruct 起步）；
⑤ 只读骨架不许有加载模型/起服务/网络路径；登记在册且**落地即接线**。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import local_brain as lb  # noqa: E402
from gbt_allinone.tools import orchestration_kernel as ok  # noqa: E402
from gbt_allinone import caps_registry as CR  # noqa: E402


class PositioningTests(unittest.TestCase):
    def test_model_is_cortex_host_is_discipline(self):
        st = lb.run("status")
        self.assertIn("皮层", st["positioning"])
        self.assertIn("不可换", st["positioning"])
        self.assertEqual(st["model_steps"], [2, 8],
                         "**模型只做第 ② 和第 ⑧ 步**")
        self.assertEqual(st["layers"], 8)

    def test_middle_layers_are_all_native(self):
        layers = lb.run("layers")["layers"]
        native = [x["n"] for x in layers if not x["by_model"]]
        self.assertEqual(native, [1, 3, 4, 5, 6, 7],
                         "中间全走原生能力栈（注册表/门禁/触手/验证/审计）")

    def test_hardware_and_model_choice_are_official(self):
        hw = lb.run("hardware")
        self.assertEqual(hw["recommend"]["vram_gb"], 12)
        self.assertEqual(hw["recommend"]["ram_gb"], 32)
        self.assertEqual(hw["tiers"][0]["size"], "7B-8B")
        picked = [x["name"] for x in lb.run("models")["candidates"] if x["pick"]]
        self.assertEqual(picked, ["Qwen2.5-7B-Instruct"], "起步选型就这一个")


class RedLineTests(unittest.TestCase):
    def test_five_redlines(self):
        r = lb.run("redlines")
        self.assertEqual(len(r["red_lines"]), 5)
        for s in ("系统命令", "二次确认", "missing_params", "trace_store", "身份"):
            self.assertTrue(any(s in x for x in r["red_lines"]), "少了：%s" % s)

    def test_model_cannot_exec_directly(self):
        for raw in ("cmd /c del x", "powershell Get-Process",
                    "subprocess.run(['ls'])", "os.system('dir')",
                    "eval('1+1')"):
            out = lb.check_no_direct_exec({"raw": raw})
            self.assertEqual(out["rule"], "model_direct_exec",
                             "直接执行命令必须拒：%s" % raw)
        self.assertEqual(lb.check_no_direct_exec({"raw": "cat x"})["rule"],
                         "not_a_registered_tool",
                         "有命令没能力位 ⇒ 这是自己造命令")
        self.assertTrue(lb.check_no_direct_exec({"capability": "echo"})["ok"],
                        "只在注册表里选工具 ⇒ 放行")

    def test_irreversible_always_blocks(self):
        for w in ("删除文件", "发送消息", "部署到生产", "支付"):
            out = lb.must_confirm_irreversible({"action": w})
            self.assertEqual(out["rule"], "irreversible_needs_confirm",
                             "不可逆必须卡：%s" % w)
        self.assertTrue(lb.must_confirm_irreversible({"action": "读文件"})["ok"])
        self.assertTrue(lb.must_confirm_irreversible({"action": "删除文件"},
                                                     confirmed=True)["ok"],
                        "人确认后放行（但留痕）")

    def test_missing_params_must_not_be_guessed(self):
        self.assertEqual(lb.must_have_params({}, [])["rule"], "no_param_contract")
        out = lb.must_have_params({"a": "1"}, ["a", "b"])
        self.assertEqual(out["rule"], "missing_params")
        self.assertEqual(out["missing"], ["b"])
        self.assertTrue(lb.must_have_params({"a": "1", "b": "2"}, ["a", "b"])["ok"])

    def test_every_call_must_trace(self):
        self.assertEqual(lb.must_trace_call("")["rule"], "call_not_traced")
        self.assertTrue(lb.must_trace_call("trace-1")["ok"])

    def test_identity_must_not_be_rewritten(self):
        for t in ("我是 GPT-4", "I am Claude", "As an AI language model, ..."):
            self.assertEqual(lb.check_identity_text(t)["rule"],
                             "identity_rewritten", "身份漂移必须拒：%s" % t)
        okk = lb.check_identity_text("我是 GBT小土豆，能源是 deepseek")
        self.assertTrue(okk["ok"], "自称是身份、能源是燃料 ⇒ 正例放行")
        self.assertEqual(okk["self_name"], "我是 GBT小土豆")


class SkeletonAndWiringTests(unittest.TestCase):
    def test_module_has_no_load_or_network_paths(self):
        src = Path(lb.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket",
                    "import ollama", "subprocess.run(", ".write_text(",
                    "from_pretrained", "load_model("):
            self.assertNotIn(bad, src, "只读骨架里不该出现：%s" % bad)

    def test_registered_and_wired(self):
        cap = CR.BENIGN_CAPS.get("local_brain")
        self.assertIsNotNone(cap)
        self.assertEqual(cap["domain"], "mind")
        self.assertIn("local_brain", ok._READONLY_MODULES)
        self.assertIs(ok._READONLY_MODULES["local_brain"], lb)


class MultiModelSwitchTests(unittest.TestCase):
    """R-H228 · 多模型自动切换（**都装 · 按需加载 · 空闲卸载**）。"""

    def test_policy_updated_and_supersedes_single_model(self):
        p = lb.run("multi_model")
        self.assertIn("都装上", p["install"])
        self.assertIn("磁盘占用 ≠ 内存占用", p["disk_vs_memory"])
        self.assertIn("空闲必须卸载", p["idle"])
        self.assertIn("只驻留一个", p["residency"])
        self.assertIn("已由本条更新", p["supersedes"],
                      "此前『只保留一个』的口径必须显式标为已更新")

    def test_routing_by_task(self):
        self.assertEqual(lb.route_model("帮我写个 Python 脚本")["model"],
                         "Qwen2.5-Coder-7B")
        self.assertEqual(lb.route_model("这个复杂决策怎么权衡")["model"],
                         "DeepSeek-R1-Distill-Qwen-7B")
        self.assertEqual(lb.route_model("中文聊聊天")["model"],
                         "Qwen2.5-7B-Instruct")
        self.assertEqual(lb.route_model("")["rule"], "missing_task")
        self.assertEqual(lb.route_model("今天晚饭吃什么")["rule"],
                         "no_model_for_task",
                         "不匹配就**如实说不匹配**，不许随便挑一个顶上")

    def test_switch_is_unload_then_load(self):
        out = lb.plan_switch("Qwen2.5-7B-Instruct", "Qwen2.5-Coder-7B",
                             ["Qwen2.5-7B-Instruct"])
        self.assertTrue(out["ok"])
        self.assertEqual([s["action"] for s in out["steps"]], ["unload", "load"],
                         "**先卸后载** —— 不许新旧重叠")
        self.assertEqual(out["steps"][1]["keep_alive_s"],
                         lb.DEFAULT_KEEP_ALIVE_S)

    def test_switch_refuses_two_resident(self):
        out = lb.plan_switch("a", "c", ["a", "b"])
        self.assertEqual(out["rule"], "vram_overcommit",
                         "两 7B 同驻会爆显存 ⇒ 拒")

    def test_no_pointless_switch(self):
        out = lb.plan_switch("m", "m", ["m"])
        self.assertTrue(out["ok"])
        self.assertEqual(out["steps"], [], "已在驻留 ⇒ 不要白卸载再加载")

    def test_idle_policy_must_be_set(self):
        self.assertEqual(lb.check_idle_policy()["rule"], "idle_policy_missing")
        self.assertEqual(lb.check_idle_policy("abc")["rule"], "bad_keep_alive")
        self.assertEqual(lb.check_idle_policy(-1)["rule"], "bad_keep_alive")
        okc = lb.check_idle_policy(0)
        self.assertTrue(okc["ok"])
        self.assertIn("立刻", okc["note"])


if __name__ == "__main__":
    unittest.main()
