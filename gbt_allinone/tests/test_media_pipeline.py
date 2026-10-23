import unittest
from unittest import mock

from gbt_allinone.tools import media_pipeline as mp


class MediaPipelineTests(unittest.TestCase):
    def test_plans_cover_short_video_film_and_music(self):
        for kind in ("short_video", "film", "music"):
            result = mp.plan(kind, "demo", "brief")
            self.assertTrue(result["ok"])
            self.assertTrue(result["stages"])

    def test_compose_stays_in_room_and_self_reviews(self):
        with mock.patch("gbt_allinone.room_space.create", return_value={"ok": True}), \
             mock.patch("gbt_allinone.room_space.shape", return_value={"ok": True}) as shape:
            result = mp.compose(
                "music", "demo", "brief", "media-test",
                {"lyrics": "x", "arrangement": "x", "audio": "x",
                 "master": "x", "export": "x"},
                copyright_attested=True, safety_reviewed=True, owner_reviewed=True,
            )
        self.assertTrue(result["ok"])
        self.assertTrue(result["self_review"]["ok"])
        self.assertEqual(shape.call_count, 2)

    def test_publish_is_owner_gated(self):
        result = mp.publish("media-test")
        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])

    def test_knowledge_covers_craft_quality_and_profit_metrics(self):
        for kind in ("short_video", "film", "music"):
            result = mp.knowledge(kind)
            self.assertTrue(result["ok"])
            self.assertTrue(result["knowledge"]["roles"])
            self.assertTrue(result["knowledge"]["craft"])
            self.assertTrue(result["knowledge"]["quality"])
            self.assertTrue(result["knowledge"]["metrics"])
            self.assertFalse(result["external_generators_connected"])

    def test_collaboration_assigns_isolated_rooms_and_evidence(self):
        result = mp.collaborate("film", "制作一部可归因收益的长视频", cycle_id="film-1")
        self.assertTrue(result["ok"])
        rooms = [packet["room_id"] for packet in result["packets"]]
        self.assertEqual(len(rooms), len(set(rooms)))
        self.assertIn("independent_review", [packet["stage"] for packet in result["packets"]])
        self.assertEqual(result["packets"][-1]["stage"], "owner_release")
        self.assertTrue(all(packet["required_outputs"] for packet in result["packets"]))

    @mock.patch("gbt_allinone.tools.long_run_supervisor.create")
    def test_launch_cycle_hands_packets_to_resumable_supervisor(self, create):
        create.return_value = {"ok": True, "task": {"task_id": "media-1"}}
        result = mp.launch_cycle("short_video", "测试闭环", "media-1")
        self.assertTrue(result["ok"])
        self.assertEqual(result["execution"], "waiting_for_worker_claim")
        steps = create.call_args.args[2]
        self.assertGreaterEqual(len(steps), 7)


if __name__ == "__main__":
    unittest.main()
