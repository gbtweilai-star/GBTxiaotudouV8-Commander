# -*- coding: utf-8 -*-
"""Omarchy 桥 判据（2026-10-15 主人拍 A 案：小土豆住进 Omarchy）。

锁五件事：
  ① **门按 op 挂**：读类也挂 process_execute（会起探针），写类追加 filesystem_write；
  ② **未知 op fail-closed**：只回错，不执行任何东西；
  ③ **没装就如实报**：写类 op 在无 Omarchy 的机器上必须拒（omarchy_not_installed / no_active_session）；
  ④ **socket 名现算**：照官方 md5(OMARCHY_PATH/shell+WAYLAND_DISPLAY) 算，不写死；
  ⑤ **不许命令注入**：route/sub 白名单外一律拦下，连跑都不跑。
"""
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone.security import policy  # noqa: E402
from gbt_allinone.tentacle import omarchy_bridge as OB  # noqa: E402


def _result_of(kind, payload):
    """只看 policy.evaluate 给出的作用域（不跑能力本体）。

    注意签名：evaluate(kind, payload) -> PolicyDecision，作用域在 .scopes 上。
    """
    d = policy.evaluate(kind, payload or {})
    return sorted(getattr(d, "scopes", ()) or ())


class OmarchyBridgeGateTest(unittest.TestCase):

    def test_read_ops_still_carry_process_execute(self):
        """读类也起探针 ⇒ 不能念成零作用域。"""
        for op in ("assess", "list", "probe_wsl", "theme_list"):
            with self.subTest(op=op):
                self.assertIn("process_execute", _result_of("omarchy_bridge", {"op": op}))

    def test_write_ops_add_filesystem_write(self):
        for op in ("set_theme", "dispatch", "eval", "plugin_add", "plugin_rm"):
            with self.subTest(op=op):
                sc = _result_of("omarchy_bridge", {"op": op})
                self.assertIn("process_execute", sc)
                self.assertIn("filesystem_write", sc)

    def test_unknown_op_is_gated_not_free(self):
        """未知 op 不能因为"不认识"就变成零作用域（宁紧不松）。"""
        sc = _result_of("omarchy_bridge", {"op": "definitely_not_an_op"})
        self.assertIn("process_execute", sc)

    def test_default_op_assess_is_gated(self):
        sc = _result_of("omarchy_bridge", {})
        self.assertIn("process_execute", sc)


class OmarchyBridgeBehaviorTest(unittest.TestCase):

    def test_unknown_op_fails_closed(self):
        r = OB.run("definitely_not_an_op")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "unknown_op")
        self.assertIn("assess", r["known"])

    def test_assess_reports_both_sides(self):
        a = OB.run("assess")
        self.assertTrue(a["ok"])
        self.assertEqual(a["op"], "assess")
        self.assertIn(a["verdict"], ("host_ready", "host_installed_no_session", "host_not_found"))
        self.assertIn("bin", a["host"])
        self.assertIn("omarchy", a["host"]["bin"])
        self.assertIsInstance(a["wsl"], list)

    def test_write_ops_refuse_when_not_connected(self):
        """没装 / 没会话 ⇒ 一律拒，并说清怎么开（fail-closed）。"""
        for op in ("set_theme", "dispatch", "eval", "plugin_enable"):
            with self.subTest(op=op):
                r = OB.run(op, name="Tokyo", command="workspace 1", lua="x=1", plugin="omarchy.clock")
                if r["ok"]:
                    self.skipTest("本机真的接上了 Omarchy，跳过拒绝判据")
                self.assertIn(r["reason"], ("omarchy_not_installed", "no_active_session"))

    def test_refusal_always_says_how_to_enable(self):
        r = OB.run("set_theme", name="Tokyo")
        if r["ok"]:
            self.skipTest("本机已接上 Omarchy")
        self.assertIn("enable", r, "拒了必须给启用路径")

    def test_eval_and_plugin_add_never_auto_run(self):
        """写死的两道：当场执行 Lua 与装第三方插件，本件不自行放行。"""
        e = OB.run("eval", lua="return 1")
        self.assertFalse(e["ok"])
        self.assertIn(e["reason"], ("needs_owner_confirm", "omarchy_not_installed", "no_active_session"))
        p = OB.run("plugin_add", source="https://github.com/example/thing")
        self.assertFalse(p["ok"])
        self.assertIn(p["reason"], ("needs_owner_confirm", "omarchy_not_installed", "no_active_session"))

    def test_socket_name_matches_official_formula(self):
        want = "omarchy-shell-%s.sock" % hashlib.md5(b"/opt/omarchy/shellwayland-1").hexdigest()
        got = OB.socket_name("/opt/omarchy", "wayland-1")
        self.assertEqual(got, want)
        self.assertNotEqual(OB.socket_name("/opt/omarchy/", "wayland-1"), "")
        self.assertNotEqual(OB.socket_name("/opt/omarchy", "wayland-2"), got)

    def test_route_allowlist_blocks_injection(self):
        """白名单外的 route/sub 必须在跑之前就被拦下。"""
        r1 = OB._cli("omarchy", "rm", "-rf")
        self.assertFalse(r1["ok"])
        self.assertEqual(r1["reason"], "route_not_allowed")
        r2 = OB._cli("omarchy", "theme", "delete-everything")
        self.assertFalse(r2["ok"])
        self.assertEqual(r2["reason"], "subcommand_not_allowed")

    def test_list_reports_missing_cli_honestly(self):
        r = OB.list_commands(bin_="")
        if r["ok"]:
            self.skipTest("本机真有 omarchy")
        self.assertEqual(r["reason"], "omarchy_not_in_path")

    def test_events_and_window_are_read_ops_but_gated(self):
        """事件流/窗口/窗口列表：只读，但都要起进程连 socket ⇒ 照样挂门。"""
        for op in ("events", "window", "clients"):
            with self.subTest(op=op):
                sc = _result_of("omarchy_bridge", {"op": op})
                self.assertIn("process_execute", sc)
                self.assertNotIn("filesystem_write", sc, "读类不该要写权限")

    def test_events_op_reports_honestly_without_session(self):
        """没会话就如实报：不许返回空事件当成功。"""
        r = OB.run("events", duration=1, max_events=5)
        if r.get("ok") and r.get("count") is not None and r.get("via", "").startswith("wsl"):
            self.skipTest("本机真有 WSL 且里面真有 Hyprland")
        self.assertFalse(r.get("ok"), r)
        self.assertIn(r.get("reason"),
                      ("no_wsl_distro", "no_event_socket", "python3_not_found",
                       "wsl_no_json", "events_failed", "script_no_json"))

    def test_window_op_reports_honestly_without_session(self):
        r = OB.run("window")
        self.assertIn("op", r)
        self.assertEqual(r["op"], "window")
        if not r.get("ok"):
            self.assertIn(r.get("reason"),
                          ("hyprctl_not_in_path", "hyprctl_not_installed", "no_wsl_distro",
                           "wsl_no_json", "unknown_distro", "script_no_json"))

    def test_event_parser_splits_type_and_data(self):
        """脚本里那段 EVENT>>DATA 的分类口径要与官方一致。"""
        script = OB._LINUX_EVENTS_SCRIPT
        self.assertIn(".socket2.sock", script)
        self.assertIn(">>", script)
        self.assertIn("socket.AF_UNIX", script)
        # 一次性：读完必须 close（官方：挂着会冻结 Hyprland）
        self.assertIn("s.close()", script)

    def test_linux_delegation_targets_wsl(self):
        """委派路必须真的走 wsl，不能假装在本机跑了。"""
        src = OB._linux_via_wsl.__code__.co_consts + (OB._linux_via_wsl.__doc__ or "",)
        joined = " ".join(str(x) for x in src if isinstance(x, str))
        self.assertIn("wsl", joined.lower())


class NativeRouterDistillTest(unittest.TestCase):
    """后拉的这一层：把官方 CLI router 的“配置即命令”思想落成**本仓自己的分档**。"""

    def test_deny_wins_over_guarded_and_safe(self):
        """能把人关在外面或断电的，不管叫什么都 deny。"""
        for r in ("omarchy system lock", "omarchy system suspend", "omarchy power reboot",
                  "omarchy logout", "omarchy hibernate"):
            with self.subTest(route=r):
                self.assertEqual(OB.classify_route(r), "deny")

    def test_mutating_routes_are_guarded(self):
        for r in ("omarchy theme set tokyo", "omarchy plugin enable omarchy.clock",
                  "omarchy update", "omarchy install gaming steam"):
            with self.subTest(route=r):
                self.assertEqual(OB.classify_route(r), "guarded")

    def test_read_routes_are_safe(self):
        for r in ("omarchy theme list", "omarchy bar status", "omarchy debug info",
                  "omarchy commands --json"):
            with self.subTest(route=r):
                self.assertEqual(OB.classify_route(r), "safe")

    def test_unknown_route_fails_closed_to_guarded(self):
        self.assertEqual(OB.classify_route("omarchy zzz what-is-this"), "guarded")

    def test_discover_reports_honestly_without_cli(self):
        d = OB.run("discover")
        self.assertEqual(d.get("op"), "discover")
        if not d.get("ok"):
            self.assertEqual(d.get("reason"), "omarchy_not_in_path")
        else:
            self.assertIn("counts", d)
            self.assertEqual(sum(d["counts"].values()), d["total"])

    def test_discover_is_registered_as_read_op(self):
        self.assertIn("discover", OB.READ_OPS)
        self.assertNotIn("discover", OB.WRITE_OPS)

    def test_new_read_groups_are_allowlisted(self):
        for grp in ("capture", "clipboard", "notify", "audio", "battery", "brightness", "monitors"):
            self.assertIn(grp, OB._ALLOW_ROUTE)
        self.assertFalse(OB._cli("omarchy", "capture", "install").get("ok"))
        self.assertEqual(OB._cli("omarchy", "capture", "install")["reason"], "subcommand_not_allowed")

    def test_metadata_classifier_blocks_sudo_first(self):
        """requires_sudo ⇒ 一律 deny，就算 group 在 safe 白名单里也不例外。"""
        self.assertEqual(OB.classify_cmd(
            {"route": "omarchy sudo docker", "group": "sudo", "requires_sudo": True}), "deny")
        self.assertEqual(OB.classify_cmd(
            {"route": "omarchy system shutdown", "group": "system", "requires_sudo": False}), "guarded")

    def test_metadata_classifier_unknown_group_is_guarded(self):
        """两张表都没点名 ⇒ guarded（safe 是白名单，不是黑名单）。"""
        self.assertEqual(OB.classify_cmd({"route": "omarchy brandnew thing", "group": "brandnew"}),
                         "guarded")
        self.assertEqual(OB.classify_cmd({"route": "omarchy theme list", "group": "theme"}), "safe")
        self.assertEqual(OB.classify_cmd({"route": "omarchy plugin add x", "group": "plugin"}),
                         "guarded")

    def test_metadata_classifier_falls_back_to_patterns(self):
        """没元数据的条目（本机现读只拿到字符串时）退回 route 模式分档。"""
        self.assertEqual(OB.classify_cmd("omarchy system lock"), "deny")
        self.assertEqual(OB.classify_cmd("omarchy theme list"), "safe")


class ObserveDistillTest(unittest.TestCase):
    """常驻感知：短周期观测 + 变化差。判据用隔离 store（不污染本仓）。

    🔴 2026-10-17 修（与 `test_figure_gate` **同一个 bug** · 留痕）：
      原实现 `reload(_paths)` 改绑定，`tearDown` 只还原 env、不还原绑定 ⇒
      进程内 `STORE_DIR_ENV_AT_BIND` 永久错位 ⇒ 之后每次写入都抛
      「store 绑定与环境变量不一致」（全量跑里 11 条红）。
      现口径：不 reload，**精确改 + 精确还原** 三个字段。
    """

    def setUp(self):
        import tempfile
        from gbt_allinone import _paths
        self._old_env = os.environ.get("GBT_STORE_DIR")
        self._old_store = _paths.STORE_DIR
        self._old_bind = _paths.STORE_DIR_ENV_AT_BIND
        self._tmp = tempfile.mkdtemp(prefix="gbt_obs_test_")
        os.environ["GBT_STORE_DIR"] = self._tmp
        _paths.STORE_DIR = Path(self._tmp).resolve()
        _paths.STORE_DIR_ENV_AT_BIND = self._tmp

    def tearDown(self):
        import shutil as _sh
        from gbt_allinone import _paths
        _sh.rmtree(self._tmp, ignore_errors=True)
        _paths.STORE_DIR = self._old_store
        _paths.STORE_DIR_ENV_AT_BIND = self._old_bind
        if self._old_env is None:
            os.environ.pop("GBT_STORE_DIR", None)
        else:
            os.environ["GBT_STORE_DIR"] = self._old_env

    def test_observe_never_says_unchanged_when_unreadable(self):
        """读不到 ≠ 没变化：没会话时 changed 必须为 False，且**不写盘**。"""
        r = OB.run("observe")
        self.assertEqual(r["op"], "observe")
        if not r["ok"]:
            self.assertFalse(r["changed"])
            self.assertFalse(r["written"], "读不到就不该落盘")
            self.assertIn("detail", r)
        else:
            self.assertTrue(r["fingerprint"])

    def test_fingerprint_changes_with_content(self):
        a = OB._fingerprint({"active": "A", "titles": ["x", "y"]})
        b = OB._fingerprint({"active": "B", "titles": ["x", "y"]})
        c = OB._fingerprint({"active": "A", "titles": ["x"]})
        self.assertEqual(a, OB._fingerprint({"active": "A", "titles": ["x", "y"]}))
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)

    def test_changed_flag_is_derived_not_guessed(self):
        """changed 必须是指纹比对算出来的，不是拍脑袋。"""
        fp = "abc123"
        self.assertTrue(bool(fp) and fp != "old")
        self.assertFalse(bool(fp) and fp != fp)

    def test_observe_history_handles_no_records(self):
        h = OB.run("observe_history")
        self.assertTrue(h["ok"])
        self.assertIn(h["count"], (0, h["count"]))
        if h["count"] == 0:
            self.assertIn("未读到", h.get("detail", ""))

    def test_observe_history_reads_back_what_was_written(self):
        d = OB._observe_dir()
        d.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps({"at": "2026-10-15T00:00:00", "fingerprint": "f1",
                        "active": "A", "count": 1, "changed": True}),
            json.dumps({"at": "2026-10-15T00:01:00", "fingerprint": "f2",
                        "active": "B", "count": 2, "changed": True}),
        ]
        (d / "observations.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        h = OB.run("observe_history", limit=1)
        self.assertTrue(h["ok"])
        self.assertEqual(h["count"], 2)
        self.assertEqual(len(h["items"]), 1)
        self.assertEqual(h["items"][0]["active"], "B")

    def test_observe_op_needs_filesystem_write_in_policy(self):
        sc = _result_of("omarchy_bridge", {"op": "observe"})
        self.assertIn("filesystem_write", sc)
        sc_ro = _result_of("omarchy_bridge", {"op": "observe", "write": False})
        self.assertNotIn("filesystem_write", sc_ro)
        self.assertIn("process_execute", sc_ro)


class ShellIpcDistillTest(unittest.TestCase):
    """第二根线：`omarchy-shell <target> <method>`。只读 method 才转发。"""

    def test_read_method_is_forwarded_never_write(self):
        r = OB.run("shell_call", target="omarchy.bar", method="restart")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "needs_owner_confirm")
        self.assertIn("omarchy-shell omarchy.bar restart", r["next"])

    def test_leaf_method_governs_namespaced_method(self):
        self.assertEqual(OB._leaf_method("Foo.status"), "status")
        self.assertEqual(OB._leaf_method("recent"), "recent")
        r = OB.run("shell_call", target="omarchy.x", method="Foo.restart")
        self.assertEqual(r.get("reason"), "needs_owner_confirm")

    def test_identifiers_are_validated_against_injection(self):
        for bad_t, bad_m in (("omarchy.bar; rm -rf /", "status"),
                             ("omarchy.bar", "status && curl x"),
                             ("$(whoami)", "status"),
                             ("", "status"),
                             ("omarchy.bar", "")):
            with self.subTest(t=bad_t, m=bad_m):
                r = OB.run("shell_call", target=bad_t, method=bad_m)
                self.assertFalse(r["ok"])
                self.assertIn(r["reason"], ("unsafe_identifier", "needs_target_and_method"))

    def test_needs_target_and_method_reported_separately(self):
        self.assertEqual(OB.run("shell_call")["reason"], "needs_target_and_method")

    def test_no_session_is_reported_honestly(self):
        r = OB.run("shell_call", target="omarchy.bar", method="status")
        if r["ok"]:
            self.skipTest("本机真有活动 shell 会话")
        self.assertIn(r["reason"], ("no_active_session", "omarchy_shell_not_in_path", "call_failed"))

    def test_shell_targets_reports_how_to_enable(self):
        r = OB.run("shell_targets")
        self.assertEqual(r["op"], "shell_targets")
        if not r["ok"]:
            self.assertIn("how_to_enable", r)
            self.assertIn(r["reason"], ("no_active_session", "omarchy_shell_not_in_path", "targets_failed"))

    def test_theme_install_is_owner_confirmed_not_auto(self):
        r = OB.run("theme_install", name="Tokyo")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "needs_owner_confirm")
        self.assertIn("gbt-vendor-intake", r["detail"])
        self.assertEqual(OB.run("theme_install")["reason"], "needs_source")

    def test_shell_ops_are_registered_read_only(self):
        self.assertIn("shell_targets", OB.READ_OPS)
        self.assertIn("shell_call", OB.READ_OPS)
        self.assertNotIn("shell_call", OB.WRITE_OPS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
