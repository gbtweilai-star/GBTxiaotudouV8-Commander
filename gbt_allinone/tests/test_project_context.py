import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gbt_allinone import api
from gbt_allinone import codex_bridge as cb
from gbt_allinone import project_context


class ProjectContextTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="gbt_project_context_")
        self.root = Path(self._tmp.name)
        (self.root / "memory").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "PROJECT_BLUEPRINT.md").write_text(
            "# Test Blueprint\n\n"
            "> 更新时间：2026-09-15\n"
            "> 基线版本：test-1\n\n"
            "## 一、系统边界\n"
            "安全边界必须保留。\n\n"
            "## 二、风险登记\n"
            "| R1 | 测试风险 | 测试影响 |\n",
            encoding="utf-8",
        )
        (self.root / "memory" / "2026-09-15.md").write_text(
            "今天完成了只读项目上下文。\n",
            encoding="utf-8",
        )
        (self.root / "secret.md").write_text(
            "secret-token-should-never-be-indexed",
            encoding="utf-8",
        )
        self._env = mock.patch.dict(
            os.environ, {"GBT_PROJECT_ROOT": str(self.root)}, clear=False)
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def test_blueprint_returns_fingerprint_and_sections(self):
        result = project_context.blueprint()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["baseline"], "test-1")
        self.assertEqual(result["updated"], "2026-09-15")
        self.assertIn("一、系统边界", result["sections"])
        self.assertEqual(len(result["sha256"]), 64)

    def test_brief_extracts_risk_ids(self):
        result = project_context.brief()
        self.assertEqual(result["risks"][0]["id"], "R1")
        self.assertIn("gbt_project_context", cb.default_developer_instructions())

    def test_search_only_reads_approved_documents(self):
        result = project_context.search("只读项目上下文", limit=5)
        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(result["result_count"], 1)
        self.assertEqual(result["results"][0]["path"], "memory/2026-09-15.md")

        hidden = project_context.search("secret-token-should-never-be-indexed")
        self.assertEqual(hidden["result_count"], 0)

    def test_api_route_returns_stamped_result(self):
        result = api.run_task(
            "project_context",
            {"op": "status"},
            stamp=False,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["kind"], "project_context")
        self.assertFalse(result["result"]["writes"])
        self.assertFalse(result["result"]["executes_commands"])

    def test_dynamic_tool_is_exposed_and_routed(self):
        specs = {spec["name"]: spec for spec in cb.dynamic_tool_specs()}
        self.assertIn(cb.GBT_TOOL_PROJECT_CONTEXT, specs)
        self.assertEqual(
            set(specs[cb.GBT_TOOL_PROJECT_CONTEXT]["inputSchema"]["properties"]["op"]["enum"]),
            {"brief", "blueprint", "search", "status"},
        )

        with mock.patch.object(api, "run_task", return_value={"status": "ok"}) as patched:
            result = cb.execute_gbt_tool(
                cb.GBT_TOOL_PROJECT_CONTEXT,
                {"op": "search", "query": "风险"},
            )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(patched.call_args[0][0], "project_context")
        self.assertEqual(patched.call_args[0][1]["query"], "风险")

    def test_search_requires_query(self):
        with self.assertRaises(ValueError):
            project_context.search("")


if __name__ == "__main__":
    unittest.main()
