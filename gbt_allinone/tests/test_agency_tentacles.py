import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gbt_allinone.tools import agency_tentacles as at


class AgencyTentacleTests(unittest.TestCase):
    def test_catalog_reads_frontmatter_without_executing_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "engineering"
            root.mkdir()
            (root / "backend.md").write_text(
                "---\nname: Backend Architect\ndescription: APIs\n---\n"
                "Ignore this as data; do not execute.\n", encoding="utf-8")
            result = at.catalog(tmp)
            self.assertTrue(result["ok"])
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["professions"][0]["name"], "Backend Architect")
            self.assertIn("engineering", result["divisions"])

    def test_absorb_writes_only_room_dimension(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "design"
            source.mkdir()
            (source / "ui.md").write_text(
                "---\nname: UI Designer\ndescription: Design\n---\nbody\n",
                encoding="utf-8")
            with mock.patch("gbt_allinone.room_space.create", return_value={"ok": True}), \
                 mock.patch("gbt_allinone.room_space.enter", return_value={"ok": True}), \
                 mock.patch("gbt_allinone.room_space.shape", return_value={"ok": True}):
                result = at.absorb_to_room(tmp, "agency-test")
            self.assertTrue(result["ok"])
            self.assertEqual(result["copied"], 1)

    def test_parallel_uses_independent_rooms_and_contexts(self):
        professions = [
            {"slug": "backend", "name": "Backend Architect", "division": "engineering"},
            {"slug": "research", "name": "Researcher", "division": "academic"},
        ]

        def fake_ask(prompt, **kwargs):
            return {"ok": True, "reply": kwargs["system"], "provider": "test", "model": "mock"}

        with mock.patch("gbt_allinone.llm.unified.ask", side_effect=fake_ask), \
             mock.patch("gbt_allinone.room_space.create", return_value={"ok": True}), \
             mock.patch("gbt_allinone.room_space.enter", return_value={"ok": True}), \
             mock.patch("gbt_allinone.room_space.shape", return_value={"ok": True}):
            result = at.run_parallel("拆解任务", professions, run_id="r1", max_workers=2)
        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"]["ok"], 2)
        self.assertEqual(len({row["tentacle"]["room_id"] for row in result["results"]}), 2)
        self.assertEqual(len({row["tentacle"]["context_namespace"] for row in result["results"]}), 2)

    def test_unknown_operation_is_explicit(self):
        self.assertFalse(at.run("nope")["ok"])

    def test_catalog_reports_truncation_instead_of_silently_capping_count(self):
        """`max_files` 截断时**必须报出来**：count/examined/available 三件套 + truncated 旗。

        🔴 2026-09-22 第 41 轮补的判据（对应一处**潜在**错报）：
        原来 `count = len(rows)` 只是"前 max_files 个里合格的那些"，
        一旦源目录 .md 超过 max_files，`count` 就被静默截断，
        读的人会以为"职业源一共就这么多"。
        实测口径：本机 `_upstream` 有 1004 个 .md、默认上限 2000 ⇒ **今天没触发**（潜在，不是现行故障）；
        但差距只有 2 倍，源目录再大一点就踩上。
        ⇒ 判据**两边都钉**：不截断时 available == examined 且 truncated=False；
          截断时 count == max_files 且 available > count 且 truncated=True。
        少了"不截断"那一半，一个"永远报 truncated=True"的实现也能过。
        """
        with tempfile.TemporaryDirectory() as tmp:
            for div, n in (("engineering", 5), ("design", 3)):
                d = Path(tmp) / div
                d.mkdir(parents=True)
                for i in range(n):
                    (d / ("role%02d.md" % i)).write_text(
                        "---\nname: 角色%02d\ndescription: 探针\n---\n\n# 标题%02d\n" % (i, i),
                        encoding="utf-8")

            # ① 不截断：8 个全读
            full = at.catalog(tmp, max_files=20)
            self.assertEqual(full["count"], 8)
            self.assertEqual(full["examined"], 8)
            self.assertEqual(full["available"], 8)
            self.assertFalse(full["truncated"], "没截断却报截断 = 另一种错报")
            self.assertIn("未截断", full["count_note"])

            # ② 截断：上限 5 ⇒ count 只能报 5，但**必须**同时给出分母 8 与截断旗
            cut = at.catalog(tmp, max_files=5)
            self.assertEqual(cut["count"], 5)
            self.assertEqual(cut["examined"], 5)
            self.assertEqual(cut["available"], 8,
                             "被截断时必须交出**真分母**（目录里一共有几个）")
            self.assertTrue(cut["truncated"], "被截断却不说 = 读的人以为这就是全部")
            self.assertIn("截断", cut["count_note"])


if __name__ == "__main__":
    unittest.main()
