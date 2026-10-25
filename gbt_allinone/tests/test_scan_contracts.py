# -*- coding: utf-8 -*-
"""R-H170 契约用例：幂等命中要有 ok 键 / 扫描器不许把"提到"当"用了"。

由来（全是今天一手实测出来的红）：
  ① wf_define 命中幂等时只返回 {"status":"already_satisfied", ...} —— 没有 ok 键，
     用例 r["result"]["ok"] 直接 KeyError（用例与实现打架，不是环境问题）。
     修法按"契约补全"：ok=True = 目标达成（无论新做还是复用）。
  ② cross_scan G 维用正则扫原文 ⇒ 把 tests 里的字符串字面量当成了真 import 报"断链"
     （扫到"提到"，不是"用了"）。
  ③ 同一个 G 维还要区分硬导入与受保护导入：integration/platform_client.py 里的
     `try: from ..bridge import deposit_bridge` 是家规第 10 条允许的"优雅降级占位"
     （bridge 这类业务模块本就该在框架里缺席），不算断链。
  ④ file_hygiene 用"看名字"判 `_*.py` ⇒ 把 cli.py 真导入的活模块
     recon/last30days/_pids.py 判成临时残留。判据改成"看有没有人真引用它"。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import gbt_allinone as gbt  # noqa: E402
from gbt_allinone import cross_scan, hygiene  # noqa: E402


def _payload(env):
    """取能力自身的返回体（gbt_result = {status, kind, result}）。"""
    body = (env or {}).get("gbt_result") or env or {}
    return body.get("result") or body


class IdempotentContractTests(unittest.TestCase):
    def test_wf_define_idempotent_hit_still_says_ok(self):
        """同一个定义定义两次：第二次是幂等命中，但仍要给出可判定的 ok。"""
        nodes = [{"id": "h", "kind": "health", "params": {}}]
        first = _payload(gbt.run_task("wf_define", {"name": "t-rh170-idem", "nodes": nodes}))
        self.assertIs(first.get("ok"), True, "首次定义必须 ok=True")
        second = _payload(gbt.run_task("wf_define", {"name": "t-rh170-idem", "nodes": nodes}))
        self.assertIn("ok", second,
                      "幂等命中不许只给 status —— 没有 ok 键，调用方只能靠猜（KeyError 的由来）")
        self.assertIs(second["ok"], True, "幂等命中同样是『这次调用达成了目标』")
        self.assertEqual(second.get("status"), "already_satisfied")
        self.assertIs(second.get("reused"), True)


_SCAN_SAMPLE = "\n".join([
    "import os",
    "def f():",
    "    from .module_that_does_not_exist import a",
    "    try:",
    "        from ..bridge import deposit_bridge",
    "    except Exception:",
    "        pass",
    "NOTE = 'from .trace_store import SELFTEST_HINTS'",
    'DOC = """from .also_missing import x"""',
    "# from .commented_missing import y",
])


class ScannerHonestyTests(unittest.TestCase):
    def test_g_dim_sees_hard_imports_only(self):
        rels = cross_scan._rel_imports(_SCAN_SAMPLE)
        self.assertIn((1, "module_that_does_not_exist"), rels,
                      "硬导入必须被看见（断链检测的本职）")

    def test_g_dim_ignores_literals_docstrings_and_guarded_imports(self):
        seen = {rel for _lvl, rel in cross_scan._rel_imports(_SCAN_SAMPLE)}
        for phantom in ("trace_store", "also_missing", "commented_missing", "bridge"):
            self.assertNotIn(phantom, seen,
                             f"{phantom} 只出现在文本里或受 try 保护（提到 ≠ 用了），不许当断链")

    def test_hygiene_live_module_is_not_a_leftover(self):
        """活模块（被真 import 的 `_*.py`）不许判成临时残留。"""
        stems = hygiene._live_module_stems()
        self.assertIn("_pids", stems, "`_pids` 被 cli.py 真导入 ⇒ 必须被识别成活模块")
        result = hygiene.scan()
        leftovers = [f for f in result["findings"] if f.get("rule") == "temp_leftover"]
        self.assertEqual(leftovers, [], f"活模块不许报残留：{leftovers}")
        self.assertEqual(result["verdict"], "clean", "家根卫生应判 clean")
        self.assertIn("live_underscore_modules", result, "活模块要如实列出，不许静默跳过")


class XGateFailureCauseTests(unittest.TestCase):
    """X 维隔离门禁：**四种失败分因必须各自归对因**（第 40 轮补的判据）。

    🔴 为什么补：`_x_run_isolated` 的 docstring 写着 `child_src` "只给判别性负对照用
    （注入噪声 / 坏 JSON / 超时 / 退码）"，而**全仓没有任何测试用它** ——
    这条链的四个失败分支**一个判据都没有**。没判据的分支就是错报的藏身处，
    本轮实测就抓到一条：

        「子进程退出 0 但一个字节都没写」被报成 `child_out_not_json`
        （「out 内容不可解析」+ JSONDecodeError: Expecting value…）

    而真相是**它根本没写**。根因：`out_file` 是 `mkstemp` 造的 ⇒ **必然 exists**，
    于是 `elif not out_file.exists(): GATE_CHILD_NO_OUT` 是**死代码**，永远轮不到。
    读的人会去查"子进程的 JSON 序列化哪儿写坏了"，方向全错。

    ⇒ 本用例把四种分因**逐个逼出来并钉死**；正对照用真子进程，确认不误报。
    """
    _RC = "import sys; sys.exit(3)"
    _TIMEOUT = "import time; time.sleep(30)"
    _NO_OUT = "import sys; sys.exit(0)"
    _BAD_JSON = ("import sys; open(sys.argv[3], 'w', encoding='utf-8').write('{not json')")

    def _gate(self, src, timeout_s=30):
        return cross_scan._x_run_isolated(child_src=src, timeout_s=timeout_s)

    def test_child_rc_maps_to_child_rc(self):
        r = self._gate(self._RC)
        self.assertEqual(r["gate_error"], cross_scan.GATE_CHILD_RC)
        self.assertEqual(r["child_rc"], 3, "退码要如实带回，便于追因")
        self.assertEqual(r["verdicts"], {}, "门没跑完 ⇒ 不许有扫描器判定")

    def test_timeout_maps_to_child_timeout(self):
        r = self._gate(self._TIMEOUT, timeout_s=1)
        self.assertEqual(r["gate_error"], cross_scan.GATE_CHILD_TIMEOUT)
        self.assertIn("timeout", str(r["gate_detail"]))

    def test_exit_zero_without_writing_out_is_missing_not_bad_json(self):
        """**退出 0 却没写 out** ⇒ 必须是 `child_out_missing`（"没写"），不是坏 JSON。

        这条就是本轮抓到的归因错：空文件 ≠ 坏 JSON。
        """
        r = self._gate(self._NO_OUT)
        self.assertEqual(r["gate_error"], cross_scan.GATE_CHILD_NO_OUT,
                         "退出 0 没写 out 应报『out 缺失』；报成 not_json 会把追因带偏")
        self.assertNotEqual(r["gate_error"], cross_scan.GATE_CHILD_BAD_JSON)
        self.assertEqual(r["child_rc"], 0)

    def test_non_json_out_maps_to_bad_json(self):
        """**写了但不是 JSON** ⇒ 才是 `child_out_not_json`（"写了但坏"）。"""
        r = self._gate(self._BAD_JSON)
        self.assertEqual(r["gate_error"], cross_scan.GATE_CHILD_BAD_JSON)
        self.assertIn("JSONDecodeError", str(r["gate_detail"]))

    def test_real_child_is_the_positive_control(self):
        """正对照：真子进程 ⇒ 门跑通（gate_error 为空）且有扫描器判定。

        少了这把对照，上面四条"分因正确"可能只是"什么都报错"而已。
        """
        r = cross_scan._x_run_isolated(timeout_s=240)
        self.assertIsNone(r["gate_error"], r["gate_detail"])
        self.assertTrue(r["verdicts"], "真子进程应当带回各扫描器的判定")
        self.assertEqual(r["child_rc"], 0)

    def test_four_causes_are_distinct(self):
        """四种分因必须**互不相同** —— 否则"分因"就是摆设。"""
        got = {self._gate(self._RC)["gate_error"],
               self._gate(self._TIMEOUT, timeout_s=1)["gate_error"],
               self._gate(self._NO_OUT)["gate_error"],
               self._gate(self._BAD_JSON)["gate_error"]}
        self.assertEqual(len(got), 4, "分因码有重复 ⇒ 读的人分不清是哪种失败：%s" % sorted(got))


if __name__ == "__main__":
    unittest.main()
