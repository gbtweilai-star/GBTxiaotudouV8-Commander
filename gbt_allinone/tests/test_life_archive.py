"""生命档案回归：原生轨迹、隐私最小化与 Obsidian 兼容镜像。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from gbt_allinone import (  # noqa: E402
    _paths,
    api,
    life_archive,
    mind_engine,
    root_fix,
)


class TestLifeArchive(unittest.TestCase):
    def setUp(self):
        self._old_store = _paths.STORE_DIR
        self._old_owner = os.environ.get("GBT_OWNER_SESSION")
        os.environ["GBT_OWNER_SESSION"] = "1"
        self._tmp = tempfile.TemporaryDirectory(prefix="gbt_life_test_")
        _paths.STORE_DIR = Path(self._tmp.name)
        for path in (
            life_archive._event_path(),
            life_archive._state_path(),
            mind_engine._state_path(),
        ):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def tearDown(self):
        _paths.STORE_DIR = self._old_store
        if self._old_owner is None:
            os.environ.pop("GBT_OWNER_SESSION", None)
        else:
            os.environ["GBT_OWNER_SESSION"] = self._old_owner
        self._tmp.cleanup()

    def test_record_timeline_dedupe_and_privacy(self):
        secret = "sk-abcdefghijklmnopqrstuvwxyz"
        raw_prompt = "完整提示词" * 120
        first = life_archive.record_event({
            "type": "decision",
            "title": "确定生命档案边界",
            "summary": f"只保存短摘要；{secret}；{raw_prompt}",
            "dedupe_key": "life-boundary-v1",
            "tags": ["privacy", "architecture"],
            "projects": ["GBT小土豆V8"],
            "importance": 0.9,
        })
        second = life_archive.record_event({
            "type": "decision",
            "title": "确定生命档案边界",
            "dedupe_key": "life-boundary-v1",
            "tags": ["privacy"],
        })
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        timeline = life_archive.timeline(limit=10)
        self.assertEqual(timeline["total"], 1)
        raw = life_archive._event_path().read_text(encoding="utf-8")
        self.assertNotIn(secret, raw)
        self.assertNotIn(raw_prompt, raw)
        self.assertIn("redacted", raw)

    def test_timeline_range_accepts_mixed_naive_and_aware_timestamps(self):
        life_archive._event_path().parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "id": "evt_naive",
                "at": "2026-09-13T12:00:00",
                "type": "event",
                "title": "旧格式事件",
                "summary": "历史导入没有时区",
            },
            {
                "id": "evt_aware",
                "at": "2026-09-14T12:00:00+07:00",
                "type": "event",
                "title": "新格式事件",
                "summary": "新事件带时区",
            },
        ]
        life_archive._event_path().write_text(
            "".join(
                json.dumps(row, ensure_ascii=False) + "\n"
                for row in rows
            ),
            encoding="utf-8",
        )

        result = life_archive.timeline(
            start="2026-09-13T00:00:00+07:00",
            end="2026-09-13T23:59:59+07:00",
            limit=10,
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["events"][0]["id"], "evt_naive")
        self.assertIsInstance(
            life_archive._parse_dt("2026-09-13T12:00:00").utcoffset(),
            type(life_archive._now().utcoffset()),
        )

    def test_chapter_commitment_habit_relationship_and_graph(self):
        opened = life_archive.chapter(
            "open", title="生命档案", summary="建立小土豆自己的时光")
        self.assertTrue(opened["created"])
        promise = life_archive.commitment(
            "add", title="不丢原有能力", importance=0.95)
        completed = life_archive.commitment(
            "complete", id=promise["commitment"]["id"])
        self.assertEqual(completed["commitment"]["status"], "done")
        habit = life_archive.habit("define", name="每日复盘", cadence="daily")
        checkin = life_archive.habit("checkin", name=habit["habit"]["name"])
        self.assertEqual(checkin["habit"]["streak"], 1)
        life_archive.record_event({
            "type": "relationship",
            "title": "和主人一起收束 Obsidian 方案",
            "summary": "选择原生生命档案加兼容导出",
            "people": ["自由的风"],
            "projects": ["GBT小土豆V8"],
            "capabilities": ["life"],
            "links": ["Obsidian"],
            "importance": 0.88,
        })
        graph = life_archive.graph()
        labels = {node["label"] for node in graph["nodes"]}
        self.assertIn("自由的风", labels)
        self.assertIn("GBT小土豆V8", labels)
        self.assertIn("Obsidian", labels)
        self.assertTrue(graph["edge_count"] >= 4)

    def test_daily_summary_and_export_are_idempotent_with_user_edit_guard(self):
        life_archive.record_event({
            "type": "milestone",
            "title": "生命档案原生部署",
            "summary": "时间线、复盘与 Obsidian 兼容镜像接通",
            "importance": 0.96,
            "tags": ["milestone", "life"],
            "projects": ["GBT小土豆V8"],
        })
        today = life_archive._now().strftime("%Y-%m-%d")
        daily = life_archive.build_daily(today)
        self.assertEqual(daily["count"], 1)
        vault = Path(self._tmp.name) / "vault"
        first = life_archive.export_obsidian(vault)
        self.assertTrue(first["created"])
        self.assertTrue((vault / "README.md").exists())
        self.assertTrue((vault / f"Daily/{today}.md").exists())
        self.assertTrue(any((vault / "Events").rglob("*.md")))

        second = life_archive.export_obsidian(vault)
        self.assertFalse(second["updated"])
        self.assertFalse(second["created"])
        self.assertTrue(second["unchanged"])

        daily_path = vault / f"Daily/{today}.md"
        daily_path.write_text(
            daily_path.read_text(encoding="utf-8") + "\n用户手写内容\n",
            encoding="utf-8",
        )
        third = life_archive.export_obsidian(vault)
        self.assertIn(f"Daily/{today}.md", third["conflicts"])
        self.assertIn("用户手写内容", daily_path.read_text(encoding="utf-8"))

    def test_ingest_existing_sources(self):
        store = Path(self._tmp.name)
        (store / "work_log.jsonl").write_text(
            json.dumps({
                "at": life_archive._iso(),
                "action": "done",
                "title": "接通生命档案",
                "detail": "完成最小闭环",
            }, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (store / "polish_insights.json").write_text(
            json.dumps({
                "insights": [{
                    "no": 1,
                    "title": "生命周期需要原生主库",
                    "detail": "外部笔记只做兼容镜像",
                }],
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        result = life_archive.ingest_sources()
        self.assertTrue(result["ok"])
        self.assertEqual(result["recorded"], 2)
        self.assertEqual(result["duplicates"], 0)

    def test_mind_events_are_archived_without_full_prompt(self):
        prompt = "秘密提示词" * 100
        mind_engine.observe(
            "mistake",
            task="生命档案接线失误",
            text=prompt,
            lesson="接线后必须验证短摘要和去重",
            guard="不保存完整文本",
            severity="high",
        )
        rows = life_archive.timeline(limit=20)
        self.assertTrue(rows["events"])
        raw = life_archive._event_path().read_text(encoding="utf-8")
        self.assertNotIn(prompt, raw)
        self.assertTrue(any(row["type"] == "mistake" for row in rows["events"]))
        self.assertTrue(any(row["type"] == "lesson" for row in rows["events"]))

    def test_root_fix_work_log_mirrors_into_life_timeline(self):
        old_path = root_fix._WORKLOG_PATH
        root_fix._WORKLOG_PATH = Path(self._tmp.name) / "work_log.jsonl"
        try:
            result = root_fix.work_log(
                "lesson", "工作日志接生命线", "完成后自动形成生命事件")
        finally:
            root_fix._WORKLOG_PATH = old_path
        self.assertTrue(result["ok"])
        rows = life_archive.timeline(limit=10)
        self.assertTrue(any(
            row["source"].get("kind") == "root_fix.work_log"
            for row in rows["events"]
        ))

    def test_api_route_and_codex_dynamic_tool(self):
        result = api.run_task("life", {
            "op": "record",
            "event": {
                "type": "milestone",
                "title": "统一入口接通",
                "summary": "life 能力已注册",
                "importance": 0.8,
            },
        })
        body = result.get("gbt_result", result)
        self.assertEqual(body["status"], "ok")
        self.assertFalse(body["result"]["duplicate"])

        from gbt_allinone import codex_bridge as cb
        specs = {spec["name"]: spec for spec in cb.dynamic_tool_specs()}
        self.assertIn(cb.GBT_TOOL_LIFE, specs)
        with mock.patch.object(
            api, "run_task", return_value={"status": "ok"}
        ) as patched:
            cb.execute_gbt_tool(cb.GBT_TOOL_LIFE, {
                "op": "record",
                "event": {"type": "milestone", "title": "x"},
            })
        self.assertEqual(patched.call_args[0][0], "life")
        self.assertEqual(patched.call_args[0][1]["op"], "record")


if __name__ == "__main__":
    unittest.main(verbosity=2)
