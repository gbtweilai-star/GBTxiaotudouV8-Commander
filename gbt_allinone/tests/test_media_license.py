# -*- coding: utf-8 -*-
"""`gbt_allinone/tools/media_license.py`（素材许可账）的判据。

立这组判据的由来（2026-09-23 第 49 轮）：`media_flow` 的家规第 2 条是「没有许可的素材不许进成品格」，
而它原来的判据是 `len(许可目录里的文件) > 0` —— **目录里随便有个文件就算过**。
本轮按新机制写了一份 **0 条的 manifest.json**，旧判据**立刻**就把 `short-video/04-cut` 的 P0
报成"许可 ✅"了，而那一格里 6 个件一条记录都没有。
⇒ 松判据不只是抓不到，**它会主动把红遮掉**。本组判据就是把"逐件"这件事钉住。

两层：**纯逻辑**（临时根，不碰生产账）+ **契约**（登记面/唯一门）。
不碰生产账这件事本身也是判据（§ Isolation）。
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gbt_allinone.tools import media_license as ML  # noqa: E402

NAME = "20260923-music-pipeline-selftest-rehearsal.wav"


def _make(tmp: str, body: bytes = b"RIFF" + b"\0" * 2048) -> Path:
    d = Path(tmp) / "projects" / "music" / "04-mix"
    d.mkdir(parents=True, exist_ok=True)
    f = d / NAME
    f.write_bytes(body)
    return f


class RegisterTests(unittest.TestCase):
    def test_refuses_a_file_that_is_not_on_disk(self):
        with tempfile.TemporaryDirectory() as t:
            r = ML.run("register", root=t, file="projects/music/04-mix/nope.wav",
                       source="x", license="y")
            self.assertFalse(r["ok"])
            self.assertIn("盘上没有这个文件", r["error"])

    def test_refuses_empty_source_or_license_and_the_reasons_differ(self):
        """判别性：三种"填不全"必须给**不同**的话 —— 否则读的人不知道该补哪一格。"""
        with tempfile.TemporaryDirectory() as t:
            f = _make(t)
            both = ML.run("register", root=t, file=str(f))
            no_src = ML.run("register", root=t, file=str(f), license="自有")
            no_lic = ML.run("register", root=t, file=str(f), source="自产")
            for r in (both, no_src, no_lic):
                self.assertFalse(r["ok"])
                self.assertTrue(r.get("refused"))
            self.assertIn("source", no_src["error"])
            self.assertIn("license", no_lic["error"])
            self.assertNotEqual(no_src["error"], no_lic["error"])
            self.assertIn("source", both["error"])
            self.assertIn("license", both["error"])

    def test_registers_with_a_computed_sha256_not_a_hand_typed_one(self):
        with tempfile.TemporaryDirectory() as t:
            f = _make(t)
            r = ML.run("register", root=t, file=str(f), source="本仓自产", license="自有")
            self.assertTrue(r["ok"], r)
            want = hashlib.sha256(f.read_bytes()).hexdigest()
            self.assertEqual(r["entry"]["sha256"], want)
            self.assertEqual(r["entry"]["file"], "projects/music/04-mix/" + NAME)

    def test_same_content_and_source_is_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            f = _make(t)
            a = ML.run("register", root=t, file=str(f), source="s", license="l")
            b = ML.run("register", root=t, file=str(f), source="s", license="l")
            self.assertTrue(a["changed"])
            self.assertFalse(b["changed"], "同内容同出处重复登记不该算改动")

    def test_changed_content_replaces_the_old_record(self):
        with tempfile.TemporaryDirectory() as t:
            f = _make(t)
            ML.run("register", root=t, file=str(f), source="s", license="l")
            f.write_bytes(b"RIFF" + b"\0" * 4096)
            r = ML.run("register", root=t, file=str(f), source="s", license="l")
            self.assertTrue(r["changed"])
            self.assertTrue(r["replaced"], "内容变了必须**替换**旧记录，不许新旧并存")


class CheckTests(unittest.TestCase):
    def test_clean_account_is_green(self):
        with tempfile.TemporaryDirectory() as t:
            f = _make(t)
            ML.run("register", root=t, file=str(f), source="s", license="l")
            c = ML.run("check", root=t)
            self.assertTrue(c["ok"])
            self.assertEqual(c["stale"], [])
            self.assertEqual(c["sha_mismatch"], [])

    def test_content_change_makes_the_account_red_and_names_the_file(self):
        """这是这个账的**牙**：素材被换掉，旧记录立刻对不上。"""
        with tempfile.TemporaryDirectory() as t:
            f = _make(t)
            ML.run("register", root=t, file=str(f), source="s", license="l")
            f.write_bytes(b"RIFF" + b"\0" * 999)
            c = ML.run("check", root=t)
            self.assertFalse(c["ok"])
            self.assertEqual(len(c["sha_mismatch"]), 1)
            self.assertIn(NAME, c["sha_mismatch"][0])

    def test_deleting_the_asset_makes_the_record_stale(self):
        with tempfile.TemporaryDirectory() as t:
            f = _make(t)
            ML.run("register", root=t, file=str(f), source="s", license="l")
            f.unlink()
            c = ML.run("check", root=t)
            self.assertFalse(c["ok"])
            self.assertEqual(len(c["stale"]), 1)

    def test_unregistered_assets_are_listed_but_do_not_make_it_red(self):
        """边界：本器**不越权判**"这些件能不能进成品格" —— 那是 `media_flow` 门的职责。"""
        with tempfile.TemporaryDirectory() as t:
            f = _make(t)
            c = ML.run("check", root=t)
            self.assertTrue(c["ok"], "没有陈旧/不匹配时不该红")
            self.assertEqual(len(c["unregistered"]), 1)
            self.assertIn(NAME, c["unregistered"][0])
            self.assertIn("不越权", c["note"])


class UnregisterTests(unittest.TestCase):
    def test_requires_a_reason(self):
        with tempfile.TemporaryDirectory() as t:
            f = _make(t)
            ML.run("register", root=t, file=str(f), source="s", license="l")
            r = ML.run("unregister", root=t, file="projects/music/04-mix/" + NAME)
            self.assertFalse(r["ok"])
            self.assertTrue(r.get("refused"))
            self.assertIn("why", r["error"])

    def test_removal_is_recorded_not_erased(self):
        with tempfile.TemporaryDirectory() as t:
            f = _make(t)
            ML.run("register", root=t, file=str(f), source="s", license="l")
            r = ML.run("unregister", root=t, file="projects/music/04-mix/" + NAME, why="自检完撤")
            self.assertTrue(r["ok"])
            man = json.loads((Path(t) / "projects" / "_shared" / "licenses"
                              / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(man["entries"], [])
            self.assertEqual(len(man.get("removed") or []), 1)
            self.assertIn("自检完撤", json.dumps(man["removed"], ensure_ascii=False))

    def test_removing_something_not_on_the_account_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            r = ML.run("unregister", root=t, file="projects/music/04-mix/" + NAME, why="x")
            self.assertFalse(r["ok"])
            self.assertIn("账上没有这条", r["error"])


class IsolationAndContractTests(unittest.TestCase):
    def test_production_account_is_never_touched_by_these_tests(self):
        """**量具不许有副作用**：上面的用例全走 `root=` 临时根，生产账里一条临时件都不许有。

        ⚠️ 判据不是"生产账必须是 0 条" —— 账上**允许有真件**（例如第 49 轮端到端那次
        往 `music/04-mix` 放的彩排自检件，那是**真登记**，不是测试污染）。
        要判的是**有没有泄漏**：每条记录都得是仓内 `projects/…` 且文件真的在。
        临时根写的记录会呈现为绝对路径 ⇒ 这条判据照样能抓住它。
        """
        lst = ML.run("list")
        self.assertTrue(lst["ok"])
        for e in lst["entries"]:
            f = str(e.get("file") or "")
            with self.subTest(entry=f):
                self.assertTrue(f.startswith("projects/"),
                                "生产账里出现了非仓内相对路径（多半是测试用了临时根却没隔离）：%s" % f)
                self.assertTrue((_ROOT / f).is_file(), "账上这条指向的文件不存在：%s" % f)

    def test_registry_entry_matches_handler_name_and_is_not_safe(self):
        from gbt_allinone import caps_registry as CR
        self.assertIn("media_license", CR.BENIGN_CAPS)
        self.assertEqual(CR.BENIGN_CAPS["media_license"]["handler"], "media_license")
        self.assertFalse(CR.BENIGN_CAPS["media_license"]["safe"],
                         "它会写账 ⇒ safe 必须为 False")

    def test_reachable_through_the_single_gate(self):
        from gbt_allinone import api
        r = api.run_task("media_license", {"op": "status"})
        self.assertTrue(r.get("ok"), r)
        inner = (r.get("result") or {}).get("result") or {}
        self.assertEqual(inner.get("impl"), "media_license",
                         "gate 没分派到本能力位 —— 检查 api.py 的 dispatch 支路")

    def test_unknown_op_lists_the_legal_ones(self):
        r = ML.run("nonsense")
        self.assertFalse(r["ok"])
        self.assertIn("不认的 op", r["error"])


if __name__ == "__main__":
    unittest.main()
