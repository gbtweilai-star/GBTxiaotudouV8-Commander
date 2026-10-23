# -*- coding: utf-8 -*-
"""万能插（omni_plug）判据（主人令 2026-10-09：把自己这边缺的插座能力补齐）。

锁三件事：
  ① **插座是真探测**：文件存在/进程就绪/URL 合法，非法类型如实 failed；
  ② **驱动是真执行**：真起进程、真读回（不是装饰数字）；
  ③ **门按插座类型挂**：process→process_execute · file写→filesystem_write · api→external_llm+data_export ·
     web→desktop_control+privacy_read · **判不出 fail-closed** —— 这正是 V9 那套最缺的一环。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import omni_plug as OP  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402


class OmniPlugTest(unittest.TestCase):

    def test_status_says_wansongcha(self):
        r = OP.run("status")
        self.assertTrue(r["ok"])
        self.assertEqual(r["名字"], "万能插")
        self.assertEqual(list(r["插座类型"]), ["process", "file", "api", "web", "app"])

    def test_plug_is_a_real_probe(self):
        good = OP.run("plug", socket="file", target="projects")
        self.assertTrue(good["ok"], good)
        bad_kind = OP.run("plug", socket="not_a_kind", target="x")
        self.assertFalse(bad_kind["ok"], "非法插座类型必须如实失败")
        # 父目录在 ⇒ 算插得上（新件可建）；父目录都不在 ⇒ 才 failed
        creatable = OP.run("plug", socket="file", target="projects/__不存在的件__.txt")
        self.assertTrue(creatable["ok"], "父目录在就该插得上（否则写新件被自己挡死）")
        missing = OP.run("plug", socket="file", target="__没有这个目录__/x.txt")
        self.assertFalse(missing["ok"], "父目录都不在就必须 failed")

    def test_drive_is_real_execution(self):
        st = OP.run("selftest")
        self.assertTrue(st["ok"], st)
        self.assertEqual(st["真驱动"]["stdout"], "42",
                         "面板上那个数字必须来自真动作（真起进程、真读回）")
        self.assertGreaterEqual(st["插座数"], 4)
        self.assertTrue(any("not_a_kind" in x for x in st["失败"]), "故意非法那个必须在失败里")

    def test_file_write_is_narrowed(self):
        inside = OP.plug_and_run(".scratch/_omni_plug_probe.txt", kind="file",
                                 action="write", args={"text": "probe"})
        self.assertTrue(inside.get("ok"), inside)
        (ROOT / ".scratch" / "_omni_plug_probe.txt").unlink(missing_ok=True)
        outside = OP.plug_and_run(str(Path.home() / "_omni_plug_outside.txt"), kind="file",
                                  action="write", args={"text": "x"})
        self.assertFalse(outside.get("ok"), "写面必须自收窄在 projects/outputs/.scratch")
        self.assertIn("写面", str(outside.get("reason")))

    def test_gate_scopes_by_socket_kind(self):
        cases = [
            ({"op": "status"}, set(), False),
            ({"op": "selftest"}, set(), False),
            ({"op": "plug", "socket": "file", "target": "x"}, set(), False),
            ({"op": "run", "socket": "process", "target": "py:print(1)"}, {"process_execute"}, True),
            ({"op": "run", "socket": "file", "target": "projects/a", "do": "write"}, {"filesystem_write"}, True),
            ({"op": "run", "socket": "file", "target": "projects/a", "do": "read"}, set(), False),
            ({"op": "run", "socket": "api", "target": "https://e.com"}, {"external_llm", "data_export"}, True),
            ({"op": "run", "socket": "web", "target": "https://e.com"}, {"desktop_control", "privacy_read"}, True),
            ({"op": "run", "socket": "??"}, {"process_execute", "filesystem_write"}, True),
            ({"op": "weird_op"}, {"filesystem_write"}, True),
        ]
        for payload, want, restricted in cases:
            d = policy.evaluate("omni_plug", dict(payload))
            self.assertEqual(set(d.scopes), want, "作用域不对：%s -> %s" % (payload, list(d.scopes)))
            self.assertEqual(bool(d.restricted), restricted, "restricted 不对：%s" % payload)

    def test_web_socket_does_not_pretend(self):
        r = OP.plug_and_run("https://example.com", kind="web", action="run")
        self.assertFalse(r.get("ok"), "web 插座不许假装能驱动：要她自己的眼+手")
        self.assertIn("tentacle", str(r.get("how") or r.get("reason")))

    def test_app_socket_plugs_a_real_app_and_drives_her_eyes(self):
        """🔴 主人点破的那一层：万能插要能**插任意 APP 并操控**（不是指个路）。"""
        r = OP.run("plug", socket="app", target="__绝对不存在的窗口__")
        self.assertFalse(r["ok"], "插不上的 APP 必须如实 failed")
        self.assertIn("窗口没命中", str(r["插座"]["detail"]))
        wins = OP._windows()[0]
        if not wins:
            self.skipTest("本机当前没有可枚举窗口（无头环境）")
        title = str(wins[0].get("title") or wins[0].get("name") or "").strip()
        if len(title) < 2:
            self.skipTest("窗口标题太短，无法作为匹配串")
        hit = OP.run("plug", socket="app", target=title[:6])
        self.assertTrue(hit["ok"], hit)
        self.assertEqual(hit["插座"]["state"], "plugged")
        seen = OP.plug_and_run(title[:6], kind="app", action="see")
        self.assertTrue(seen.get("ok"), seen)
        self.assertIn("看", seen)

    def test_app_action_space_is_a_whitelist(self):
        # 先用一个真能插上的目标（本机 python.exe 属于 app 插座可认的可执行件），再试非法动作
        import sys as _s
        bad = OP.plug_and_run(_s.executable, kind="app", action="act",
                              args={"action": "format_c_drive"})
        self.assertFalse(bad.get("ok"), "动作不在白名单里必须拒")
        self.assertIn("不认的动作", str(bad.get("reason")))
        self.assertIn("click", bad.get("known") or [], "必须给出已知动作集")

    def test_app_socket_is_gated(self):
        self.assertEqual(set(policy.evaluate("omni_plug", {"op": "plug", "socket": "app",
                                                            "target": "x"}).scopes),
                         {"privacy_read"})
        self.assertEqual(set(policy.evaluate("omni_plug", {"op": "run", "socket": "app",
                                                            "target": "x", "do": "see"}).scopes),
                         {"desktop_control", "privacy_read"})
        self.assertEqual(set(policy.evaluate("omni_plug", {"op": "run", "socket": "app",
                                                            "target": "x", "do": "launch"}).scopes),
                         {"desktop_control", "privacy_read", "process_execute"})


if __name__ == "__main__":
    unittest.main()
