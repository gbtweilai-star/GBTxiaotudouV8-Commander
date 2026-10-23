# -*- coding: utf-8 -*-
"""`git_read` / `git_write` · 契约测试（2026-09-23 接 git 能力位时立的钉子）。

守五件事：
  ① **门的判据平凡正确**：`git_read` 永远零作用域；`git_write` 永远挂 `filesystem_write`
     （连它不认识的 op 也挂 —— fail-closed）
  ② **反选项注入真的会拒**：`rev` / `path` / `message` 以 `-` 开头一律拒
     （经典 `--upload-pack=…` 就是这么塞进去的）
  ③ **写面必须点名路径**：空 `paths` 拒（本仓脏行上万，`commit -a` 会卷进不相干的东西）
  ④ **只读面真能读**：status / log / branch_list 真跑出结果，且都标 `readonly: True`
  ⑤ **两条静态钉子**（改的人当场看见）：源码里**不许出现 `shell=True`**；
     带路径的 git 命令**必须带 `--`** 分隔符

纪律说明：写面**不在测试里真提交** —— 本仓是主人的活仓库，测试不许往里落提交。
写面只测"拒得对"（注入 / 空路径 / 缺 message）与"门拦得对"。
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_git_test_"))

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gbt_allinone.tools import git_repo as GR          # noqa: E402
from gbt_allinone.security import policy               # noqa: E402
from gbt_allinone import api                           # noqa: E402

_SRC = (Path(__file__).resolve().parents[1] / "tools" / "git_repo.py").read_text(encoding="utf-8")


class GateTests(unittest.TestCase):
    """① 门：判据平凡正确。"""

    def test_read_never_gets_any_scope(self):
        for op in ({}, {"op": "status"}, {"op": "diff"}, {"op": "log"},
                   {"op": "show"}, {"op": "brand_new_op"}):
            self.assertEqual([], list(policy.evaluate("git_read", op).scopes),
                             "git_read 竟然挂了作用域：%s" % op)

    def test_write_always_gets_filesystem_write(self):
        for op in ({}, {"op": "stage"}, {"op": "commit"}, {"op": "brand_new_op"}):
            self.assertIn("filesystem_write",
                          list(policy.evaluate("git_write", op).scopes),
                          "git_write 竟然没挂写作用域：%s" % op)

    def test_write_denied_at_the_gate_without_grant(self):
        """🔴 2026-10-19 口径翻正（Owner 令第二次重申，逐字：「我说了除了黑客全能力和转账
        要票其他都去掉」）：`filesystem_write` **不再是人工授权**。原来这条用例靠"必然被拒"
        来避免真的提交仓；门现在会放行 ⇒ 改成**在门那一层验**（不真跑 git_write，免得
        测试去动仓）：① 三道护栏之外的作用域必须直接放行；② 三道护栏必须仍然要票。
        """
        from gbt_allinone import auth_gate as _ag
        self.assertTrue(_ag.check_and_consume("filesystem_write").get("ok"),
                        "filesystem_write 仍被当票挡着（主人令：除三道护栏外都去掉）")
        for guard in ("privacy_read", "process_execute", "external_llm", "deploy_publish"):
            self.assertIn(guard, _ag.ENFORCED_SCOPES, "三道护栏里少了 %s" % guard)
            self.assertFalse(_ag.check_and_consume(guard).get("ok"),
                             "护栏 %s 居然不要票了（三道护栏掉了）" % guard)


class InjectionTests(unittest.TestCase):
    """② 反选项注入 —— 每一条都必须拒，并给机读 code。"""

    def _code(self, fn, *a, **kw) -> str:
        try:
            fn(*a, **kw)
        except GR.GitRepoError as e:
            return e.code
        return ""

    def test_rev_starting_with_dash_refused(self):
        self.assertEqual("option_injection",
                         self._code(GR.run_read, {"op": "show", "rev": "--upload-pack=calc"}))

    def test_path_starting_with_dash_refused(self):
        self.assertEqual("option_injection",
                         self._code(GR.run_read, {"op": "diff", "path": "-x"}))

    def test_message_starting_with_dash_refused(self):
        self.assertEqual("option_injection",
                         self._code(GR.run_write, {"op": "commit", "paths": ["README.md"],
                                                   "message": "-m injected"}))

    def test_path_outside_repo_refused(self):
        outside = Path(tempfile.gettempdir()) / "gbt_git_outside.txt"
        outside.write_text("x", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        self.assertEqual("outside_repo",
                         self._code(GR.run_read, {"op": "diff", "path": str(outside)}))

    def test_api_surfaces_reason_code(self):
        """集成：经唯一门之后，`reason_code` 必须在外层信封里（可机读，不靠读中文）。"""
        raw = api.run_task("git_read", {"op": "show", "rev": "--upload-pack=calc"})
        body = raw.get("gbt_result", raw)
        self.assertEqual("error", body.get("status"))
        self.assertEqual("user_error", body.get("error_class"))
        self.assertEqual("option_injection", body.get("reason_code"))


class WriteGuardTests(unittest.TestCase):
    """③ 写面必须点名路径。"""

    def test_empty_paths_refused(self):
        try:
            GR.run_write({"op": "commit", "paths": [], "message": "m"})
        except GR.GitRepoError as e:
            self.assertEqual("paths_required", e.code)
        else:
            self.fail("空 paths 竟然放过了")

    def test_message_required(self):
        try:
            GR.run_write({"op": "commit", "paths": ["README.md"]})
        except GR.GitRepoError as e:
            self.assertEqual("message_required", e.code)
        else:
            self.fail("缺 message 竟然放过了")

    def test_unknown_op_refused(self):
        try:
            GR.run_write({"op": "push"})
        except GR.GitRepoError as e:
            self.assertEqual("unknown_op", e.code)
        else:
            self.fail("没实现的 op 竟然放过了（不许假装有 push）")


class ReadTests(unittest.TestCase):
    """④ 只读面真能读（不 mock —— 直接在真仓上读，读不到就是坏了）。"""

    def test_status_reports_branch_and_dirty(self):
        r = GR.run_read({})
        self.assertTrue(r["readonly"])
        self.assertTrue(r["branch_line"].startswith("##"), r["branch_line"])
        self.assertIsInstance(r["dirty_n"], int)

    def test_log_returns_commits_and_respects_limit(self):
        r = GR.run_read({"op": "log", "limit": 3})
        self.assertLessEqual(len(r["commits"]), 3)
        self.assertTrue(r["commits"], "log 一条都没读出来")
        self.assertRegex(r["commits"][0], r"^[0-9a-f]{7,}\s")

    def test_branch_list_and_stash_list(self):
        self.assertIn("main", " ".join(GR.run_read({"op": "branch_list"})["items"]))
        self.assertIsInstance(GR.run_read({"op": "stash_list"})["items"], list)

    def test_bad_limit_is_a_user_error(self):
        with self.assertRaises(GR.GitRepoError) as cm:
            GR.run_read({"op": "log", "limit": "不是数字"})
        self.assertEqual("bad_limit", cm.exception.code)


class StaticPinTests(unittest.TestCase):
    """⑤ 两条静态钉子 —— 改的人当场看见，而不是等出事。"""

    def test_never_uses_a_shell(self):
        self.assertNotIn("shell=True", _SRC,
                         "git 调用不许过 shell —— 调用方给的字串会进命令行解析")
        self.assertIn("shell=False", _SRC)

    def test_path_bearing_commands_use_double_dash(self):
        """带路径的 git 命令必须带 `--` 分隔符（否则路径会被当版本/选项）。"""
        for pat in (r'"add",\s*"--"', r'"commit",\s*"-m"', r'"--",\s*\*paths'):
            self.assertRegex(_SRC, pat, "带路径的命令没带 `--`：%s" % pat)

    def test_no_destructive_ops_declared(self):
        """本轮**如实不做**危险 op：源码里不许悄悄长出 reset/rebase/push。"""
        for bad in ("reset", "rebase", "push", "--force", "clean"):
            self.assertNotRegex(_SRC, r'"%s"' % re.escape(bad),
                                "出现了未申报的危险 op：%s" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
