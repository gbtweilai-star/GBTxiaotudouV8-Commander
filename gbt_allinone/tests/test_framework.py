import os
import sys
import json
import contextlib
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

# 测试隔离：独立临时 store，回归测试绝不污染生产审计日志与产物目录
os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_test_store_"))

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))  # 项目根（gbt_allinone 的父目录）
sys.path.insert(0, _ROOT)

import gbt_allinone as gbt
from gbt_allinone import store
from gbt_allinone.caps_registry import UNIMPLEMENTED_CAPS


def _body(result):
    """V8 钢印结构兼容：取 gbt_result 主体，旧结构直接返回。"""
    if isinstance(result, dict) and "gbt_result" in result:
        return result["gbt_result"]
    return result


def _op(result):
    """再钻一层到**能力自身的返回**：`gbt_result = {status, kind, result}`。

    少钻这一层会让断言落在不存在的键上 —— `dict.get` 照样返回 None，
    测试**空过**（本人第一版就是这样，被 `first["ok"]` 的 KeyError 顺带揭出来）。
    """
    body = _body(result)
    if isinstance(body, dict) and "result" in body:
        return body["result"]
    return body


class WorkLogIdempotencyTests(unittest.TestCase):
    """日志侧幂等（O73 的另一半）：**写入前查指纹**，不靠事后删。

    实测由来：落账脚本跑第二遍 → work_log 多一条 + 生命事件多一条
    （`life/events.jsonl` 第 165/166 行），而 `work_log_mirrored` 还报 duplicate=false
    —— 镜像那层按含 `at` 的 digest 判，时间戳变了就永远不重合。
    """

    def setUp(self):
        from gbt_allinone import _paths
        self.log = Path(_paths.STORE_DIR) / "work_log.jsonl"
        self.before = self.log.read_text(encoding="utf-8").count("\n") if self.log.exists() else 0

    def _lines(self):
        return self.log.read_text(encoding="utf-8").strip().split("\n") if self.log.exists() else []

    def test_same_content_twice_writes_once(self):
        # 🔴 样本必须**按运行唯一**：去重窗口是 300s，固定串会被上一次运行（或同文件里
        # 前面的用例）留下的同内容条目命中 ⇒ 第一枪就 `duplicate` ⇒
        # 红字报"幂等坏了"，真相是"测试重用了固定样本串"。**那是错报。**
        # 注意：测试内两枪仍用**同一个 payload**，所以"同内容"这条语义分毫未变。
        _u = __import__("uuid").uuid4().hex[:8]
        payload = {"op": "work_log", "action": "lesson",
                   "title": "幂等回归样本", "detail": "同内容只该落一条-%s" % _u}
        first = _op(gbt.run_task("root_fix", payload))
        second = _op(gbt.run_task("root_fix", payload))

        self.assertIn("ok", first, "返回结构变了：断言必须先能看见键，否则是空过")
        self.assertIn("duplicate", second, "第二枪必须明确回答 duplicate，不许沉默")
        self.assertTrue(first["ok"])
        self.assertFalse(first.get("duplicate"))
        self.assertTrue(second.get("duplicate"))
        self.assertTrue(second["skipped"])
        self.assertEqual(second["window_s"], 300.0)
        self.assertEqual(second["row"]["title"], "幂等回归样本")
        added = len(self._lines()) - self.before
        self.assertEqual(added, 1, "同内容两次调用只该多一行")

    def test_different_content_still_logs_twice(self):
        """负对照：幂等门不许把正常日志吃掉。"""
        _u = __import__("uuid").uuid4().hex[:8]     # 按运行唯一，理由同上
        first = _op(gbt.run_task("root_fix", {
            "op": "work_log", "action": "lesson", "title": "幂等负对照甲", "detail": "甲-%s" % _u}))
        second = _op(gbt.run_task("root_fix", {
            "op": "work_log", "action": "lesson", "title": "幂等负对照乙", "detail": "乙-%s" % _u}))

        self.assertTrue(first["ok"] and second["ok"])
        self.assertFalse(first.get("duplicate") or second.get("duplicate"))
        self.assertEqual(len(self._lines()) - self.before, 2)

    def test_window_expiry_allows_the_same_line_again(self):
        """窗口过后同一句必须能再记 —— 否则幂等门变成"记忆黑洞"。"""
        from gbt_allinone import root_fix
        _u = __import__("uuid").uuid4().hex[:8]     # 按运行唯一，理由同上
        payload = {"op": "work_log", "action": "lesson",
                   "title": "窗口过期样本", "detail": "过了窗口就该能重记-%s" % _u}
        first = _op(gbt.run_task("root_fix", payload))
        with mock.patch.object(root_fix, "_WORKLOG_DEDUPE_WINDOW_S", 0.0):
            again = _op(gbt.run_task("root_fix", payload))

        self.assertTrue(first["ok"])
        self.assertIn("duplicate", again)
        self.assertFalse(again.get("duplicate"))
        self.assertEqual(len(self._lines()) - self.before, 2)

    def test_fingerprint_ignores_timestamp_only(self):
        """指纹只看 action/title/detail —— 只有 at 不同仍算同一条。"""
        from gbt_allinone import root_fix
        row_a = {"at": "2026-09-19T01:02:56", "action": "done", "title": "t", "detail": "d"}
        row_b = {"at": "2026-09-19T01:03:06", "action": "done", "title": "t", "detail": "d"}
        row_c = {"at": "2026-09-19T01:03:06", "action": "done", "title": "t", "detail": "换个说法"}

        self.assertEqual(root_fix._worklog_fingerprint(row_a),
                         root_fix._worklog_fingerprint(row_b))
        self.assertNotEqual(root_fix._worklog_fingerprint(row_a),
                            root_fix._worklog_fingerprint(row_c))


class BrainVaultTests(unittest.TestCase):
    """脑库接入（R-H94）：记忆要**跟着一起上线**，且只增不删。

    测试一律把 `GBT_VAULT_DIR` 指到临时库 —— 绝不碰主人的真库（与 GBT_STORE_DIR 同理）。
    """

    @contextlib.contextmanager
    def _vault(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "地图").mkdir(parents=True, exist_ok=True)
            (root / "地图" / "记忆总纲.md").write_text(
                "# 记忆总纲\n\n开工先读这篇。\n\n枝：[[人物/人物总览|人物]]\n", encoding="utf-8")
            (root / "人物").mkdir(exist_ok=True)
            (root / "人物" / "人物总览.md").write_text("# 人物\n", encoding="utf-8")
            (root / "收集箱.md").write_text("# 所有记录\n\n这里会自动按时间追加。\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"GBT_VAULT_DIR": str(root)}):
                yield root

    def test_status_reads_the_vault_and_counts_links(self):
        with self._vault():
            res = _op(gbt.run_task("brain_vault", {"op": "status"}))

        self.assertTrue(res["ok"])
        self.assertEqual(res["notes"], 3)
        self.assertEqual(res["wikilinks"], 1)
        self.assertEqual(res["unresolved"], [], "链接写全路径 ⇒ 不该有断链")
        self.assertTrue(res["main_note_exists"] and res["inbox_exists"])

    def test_status_reports_dangling_links_not_hides_them(self):
        """断链必须如实计入 unresolved —— 空链接不许当噪音略过。"""
        with self._vault() as root:
            (root / "地图" / "记忆总纲.md").write_text("# 记忆总纲\n\n[[不存在的笔记]]\n", encoding="utf-8")
            res = _op(gbt.run_task("brain_vault", {"op": "status"}))

        self.assertEqual(res["unresolved"], ["不存在的笔记"])

    def test_recall_returns_main_note_and_recent_inbox_lines(self):
        with self._vault():
            res = _op(gbt.run_task("brain_vault", {"op": "recall", "limit": 5}))

        self.assertIn("记忆总纲", res["main_note"])
        self.assertGreaterEqual(res["inbox_lines"], 2)
        self.assertTrue(res["recent"])

    def test_remember_appends_and_never_overwrites(self):
        """写入口只有"追加"这一种：两次记 → 两行都在，文件只增不减。"""
        with self._vault() as root:
            first = _op(gbt.run_task("brain_vault", {"op": "remember", "text": "第一条真记录"}))
            second = _op(gbt.run_task("brain_vault", {"op": "remember", "text": "第二条真记录"}))
            body = (root / "收集箱.md").read_text(encoding="utf-8")

        self.assertTrue(first["wrote"] and second["wrote"])
        self.assertGreater(second["bytes"]["after"], first["bytes"]["after"])
        self.assertIn("第一条真记录", body)
        self.assertIn("第二条真记录", body)
        self.assertIn("# 所有记录", body, "原内容不许被覆盖")

    def test_no_delete_path_exists(self):
        """这个模块里没有任何删除路径：删类动作一律 user_error。"""
        with self._vault():
            for bad in ("delete", "remove", "clear", "truncate"):
                res = _op(gbt.run_task("brain_vault", {"op": bad}))
                self.assertIn("未知动作", res.get("message", ""), bad)

    def test_remember_rejects_empty_text(self):
        with self._vault():
            res = _op(gbt.run_task("brain_vault", {"op": "remember", "text": "   "}))

        self.assertFalse(res["ok"])
        self.assertIn("为空", res["error"])


class LLMKeyVaultProfileTests(unittest.TestCase):
    """多 profile 保险箱 + 两条密钥链口径（Owner 2026-09-19 配 Agnes）。"""

    def test_profiles_are_isolated_by_entropy_and_path(self):
        """熵值互不相同 ⇒ 甲库密文在乙库里解不开。这是**机制**，不是约定。

        🔴 2026-09-25 改（**这是"改了判据"，所以把理由写在现场**）：
        原文是 `assertEqual(set(dk._PROFILES), {"deepseek", "agnes"})` —— 那是
        2026-09-19 那一刻的**快照**，不是不变量。主人当天令「密钥全部部署跟双向插件一样、
        可以自动读取」，据此给 ADP 加了第三个 profile（各带自己的熵值与落盘），
        这条快照就红了。修法是**把快照换成不变量、并且收紧**：
          · 默认 profile 仍是 deepseek（这条是真正的钉子，一字未动）；
          · 三个必有的 profile 名字都在；
          · 熵值 / 落盘名 / **主环境变量名** 两两不许相同 ——
            最后一条是**新加的**：新 profile 悄悄复用别人的环境变量名，就会互相顶掉，
            这正是"加 profile"最容易犯又最不容易看出来的错。
        """
        from gbt_allinone import deepseek_key as dk

        self.assertEqual(dk._DEFAULT_PROFILE, "deepseek", "默认 profile 不许变，免得打断既有调用方")
        self.assertTrue({"deepseek", "agnes", "adp"} <= set(dk._PROFILES),
                        "在册 profile 少了：%s" % sorted(dk._PROFILES))
        entropies = [spec["entropy"] for spec in dk._PROFILES.values()]
        files = [spec["file"] for spec in dk._PROFILES.values()]
        envs = [spec["env"] for spec in dk._PROFILES.values()]
        self.assertEqual(len(set(entropies)), len(entropies), "有两个 profile 共用熵值")
        self.assertEqual(len(set(files)), len(files), "有两个 profile 落到同一个文件")
        self.assertEqual(len(set(envs)), len(envs), "有两个 profile 用同一个环境变量名")
        self.assertTrue(all(ent.startswith(b"GBTxiaotudouV8:") for ent in entropies),
                        "熵值前缀必须统一，否则不是同一套机制的库")
        self.assertEqual(dk._secret_file("agnes").name, "agnes_api.dpapi")
        self.assertEqual(dk._secret_file("adp").name, "adp_api.dpapi")

    def test_cross_profile_decrypt_fails(self):
        """负对照：agnes 库写出来的密文，换到 deepseek 库的路径上必须解不开。"""
        import tempfile
        from pathlib import Path
        from gbt_allinone import deepseek_key as dk

        with tempfile.TemporaryDirectory() as tmp:
            agnes_file = Path(tmp) / "agnes.dpapi"
            deep_file = Path(tmp) / "deep.dpapi"
            with mock.patch.dict(os.environ, {
                "GBT_AGNES_SECRET_FILE": str(agnes_file),
                "GBT_DEEPSEEK_SECRET_FILE": str(deep_file),
            }):
                os.environ.pop("AGNES_API_KEY", None)
                os.environ.pop("DEEPSEEK_API_KEY", None)
                report = dk.store_key("ak-testonly-notreal-0000000000", "agnes")
                self.assertTrue(report["ok"], report)
                self.assertEqual(report["profile"], "agnes")
                self.assertNotIn("ak-test", json.dumps(report, ensure_ascii=False))
                deep_file.write_bytes(agnes_file.read_bytes())   # 只换库，不换密文
                key, source = dk.load_key("deepseek")

        self.assertEqual(key, "")
        self.assertEqual(source, "unreadable")

    def test_unknown_profile_is_rejected_loudly(self):
        """写错库名必须报错，不许静默退回默认 —— 静默退回 = 密钥写进了错的库。"""
        from gbt_allinone import deepseek_key as dk

        with self.assertRaises(dk.DeepseekKeyError):
            dk._profile("no-such-vault")

    def test_both_chains_put_agnes_first_with_same_knobs(self):
        """两条链（APP 与框架）口径必须一致：agnes 在首位，地址与型号一字不差。"""
        from gbt_allinone.llm import cloud_llm
        sys.path.insert(0, str(Path(_ROOT) / "potato_pet"))
        import chat_client

        self.assertEqual(cloud_llm._KEY_CHAIN[0][0], "agnes")
        self.assertEqual(cloud_llm._KEY_CHAIN[0][2], "https://apihub.agnes-ai.com/v1")
        self.assertEqual(cloud_llm._KEY_CHAIN[0][3], "agnes-2.5-flash")
        self.assertEqual(chat_client._KEY_CHAIN[0],
                         ("AGNES_API_KEY", "https://apihub.agnes-ai.com/v1", "agnes-2.5-flash"))


class TestFramework(unittest.TestCase):
    def test_stamp_on_success(self):
        r = gbt.run_task("health")
        self.assertTrue(gbt.soul.is_stamped(r))
        self.assertEqual(r["gbt_stamp"]["mark"], "GBT")
        self.assertEqual(r["gbt_stamp"]["ownership"], "independent-personal")

    def test_no_stamp_when_disabled(self):
        r = gbt.run_task("health", stamp=False)
        self.assertNotIn("gbt_stamp", r)

    def test_soul_loaded(self):
        self.assertEqual(gbt.SOUL["name"], "GBT小土豆")
        self.assertEqual(len(gbt.SOUL["core_laws"]), 3)

    def test_benign_list_excludes_unimplemented(self):
        """2026-09-23 解禁后改口径：登记未实现的 11 条**不许混进良性清单**。

        解禁前它们状态是 "disabled"、被 filter_dangerous 剔掉；
        解禁后状态是 "unimplemented"，若不过滤就会变成"报得出名字、点下去 unknown capability"的假绿。
        """
        names = [c["name"] for c in gbt.list_capabilities(filter_dangerous=True)]
        self.assertIn("health", names)
        self.assertEqual(len(names), len(gbt.list_capabilities(filter_dangerous=False)) - len(UNIMPLEMENTED_CAPS))
        for d in UNIMPLEMENTED_CAPS:
            self.assertNotIn(d, names, "登记未实现的名字不应出现在良性清单: %s" % d)

    def test_all_list_marks_unimplemented(self):
        """全登记面（filter_dangerous=False）里，红队那 11 位的状态要**如实**。

        口径变更（Owner 2026-09-25 令「把黑客能力全部多维度全部覆盖补齐」）：
        这 11 位此前标 `unimplemented`（只有名字、没有实现），现在**全部接上了实现**。
        ⇒ 判据从"必须标 unimplemented"换成"标 enabled，且**全表不许再有任何
        unimplemented / disabled**"。名字守恒那一条由
        `tests/test_redteam.py::TestWiring::test_legacy_eleven_names_conserved` 守着。
        """
        items = gbt.list_capabilities(filter_dangerous=False)
        statuses = {i["name"]: i.get("status") for i in items}
        self.assertNotIn("disabled", set(statuses.values()), "解禁后不该再有任何 disabled 状态")
        self.assertNotIn("unimplemented", set(statuses.values()),
                         "红队 11 位已全部接上实现，不该再有 unimplemented 状态")
        for name in ("paywallbuster", "keylogger", "data_hijack", "remote_domain",
                     "screen_sniff", "device_takeover", "pentest", "asset_vault_freeze",
                     "credential_steal", "social_eng", "onboarding_gate"):
            self.assertEqual(statuses.get(name), "enabled", "%s 应已可执行" % name)

    def test_health_ok(self):
        r = _body(gbt.run_task("health"))
        self.assertEqual(r["status"], "ok")
        self.assertIn("python", r["result"])

    def test_count_words(self):
        r = _body(gbt.run_task("count_words", {"text": "a b c"}))
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["result"]["words"], 3)

    def test_redteam_names_are_no_longer_unknown(self):
        """2026-09-25 Owner 令后**换口径**：这 4 个名字已经接上实现。

        旧判据（本用例原名 `test_unimplemented_names_never_succeed`）钉的是**旧事实**：
        「不许跑成功 + 必须回 `unknown capability`」。那条事实已经被 Owner 的令改掉了 ——
        再留着它就是**用测试把过时结论钉死**。

        新判据只钉真正该守的那一件：**绝不许再回 `unknown capability`**
        （回了就等于说"名字有、实现没有"，那正是这次要消灭的状态）。
        实际行为（真跑 / 被授权门如实拒绝 / 缺参数报 user_error）三者都算接线在位，
        不在这里钉死 —— 那是 `tests/test_redteam.py` 的活。
        """
        from gbt_allinone.caps_registry import BENIGN_CAPS as _B
        for d in ["paywallbuster", "keylogger", "data_hijack", "remote_domain"]:
            self.assertIn(d, _B, "%s 应已登记为可执行能力" % d)
            r = _body(gbt.run_task(d))
            self.assertNotIn("unknown capability", json.dumps(r, ensure_ascii=False),
                             "%s 已接上实现，不该再报 unknown capability" % d)

    def test_unknown_cap_error(self):
        r = _body(gbt.run_task("no_such_capability_xyz"))
        self.assertEqual(r["status"], "error")

    def test_osint_guard_blocks_private(self):
        # 人工授权门：无授权时内网目标 denied（allow_private 不再是绕过入口）
        r = _body(gbt.run_task("osint_scan", {"target": "127.0.0.1", "allow_private": True}))
        res = r.get("result", r)
        self.assertTrue(res.get("denied"))
        self.assertIn("人工授权", str(res.get("error", "")))

    def test_auth_gate_flow(self):
        # 授权门全链路（**Owner 2026-09-25 令后分级**）：
        #   无授权拒 → 人工授权放行 → **时段授权在 TTL 内可再次放行，且用量如实累计**
        #   → 过期即拒。
        # 旧口径是「消耗 → 再拒」（全体一次性）。改它的理由写在 auth_gate.ONE_SHOT_SCOPES
        # 上方：一次性消耗压在 audio_output / privacy_read 这类**日常技术动作**上，
        # 实测等于"每说一句话回终端敲一次 YES"，语音对讲物理上不可用。
        # 注意：本用例改的是**日常类**作用域（osint_private）的语义；
        # 危险类的"仍一次性"由 test_one_shot_scopes_stay_one_shot 单独钉住。
        import os as _os
        import time as _t
        import json as _j
        from pathlib import Path as _P
        from gbt_allinone import auth_gate as _AG
        from gbt_allinone.security import policy as _Pol
        # 清场
        from gbt_allinone import _paths as _p
        gf = _P(_AG._GRANTS)   # O33：唯一来源——不自己拼 /"store"/（否则测试与授权门各看一份路径）
        self.assertEqual(gf.resolve(),
                         (_P(_p.STORE_DIR) / "auth_grants.jsonl").resolve(),
                         "授权门落点必须在 _paths.STORE_DIR 里：%s" % gf)
        _prev_env = _os.environ.pop("GBT_OWNER_SESSION", None)
        _prev_bytes = gf.read_bytes() if gf.exists() else b""
        try:
            # 主人会话下授权门直通，本用例的每一条断言都不成立 —— 与其静默假绿，
            # 不如先把会话按成非主人并**断言它确实是非主人**。
            self.assertFalse(_Pol.is_trusted(), "本用例必须在非主人会话下跑")
            if gf.exists():
                gf.unlink()
            # 1) 无授权拒绝
            r1 = _body(gbt.run_task("osint_scan", {"target": "192.168.1.1", "allow_private": True}))
            self.assertTrue(r1["result"].get("denied"))
            # 2) 主人手写授权（合法途径）
            g = {"id": "grant-test-flow", "scope": "osint_private", "operator": "owner-manual",
                 "purpose": "测试授权流", "granted_at": _t.strftime("%Y-%m-%dT%H:%M:%S"),
                 "expires_at": round(_t.time() + 120, 3), "mode": "window", "used": 0}
            gf.parent.mkdir(parents=True, exist_ok=True)
            gf.write_text(_j.dumps(g, ensure_ascii=False) + "\n", encoding="utf-8")
            # 3) 授权后放行
            r2 = _body(gbt.run_task("osint_scan", {"target": "192.168.1.1"}))
            self.assertEqual(r2["status"], "ok")
            self.assertEqual(r2["result"].get("auth_consumed"), "grant-test-flow")
            # 4) **正题**：时段授权在 TTL 内必须能再次放行
            r3 = _body(gbt.run_task("osint_scan", {"target": "192.168.1.1"}))
            self.assertEqual(r3["status"], "ok",
                             "时段授权在 TTL 内必须能反复放行；这里若 denied，就是又退回一次性语义")
            rows = [_j.loads(x) for x in gf.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(rows), 1, "时段授权不许从账本删行（删了就没法回答'用了几回'）")
            self.assertEqual(int(rows[0].get("used", 0)), 2,
                             "用量必须如实累计：两次放行 = used 2")
            # 5) 时段授权也不是永久的：过期即拒
            g["expires_at"] = round(_t.time() - 1, 3)
            gf.write_text(_j.dumps(g, ensure_ascii=False) + "\n", encoding="utf-8")
            r4 = _body(gbt.run_task("osint_scan", {"target": "192.168.1.1"}))
            self.assertTrue(r4["result"].get("denied"), "过期授权必须失效")
        finally:
            if _prev_bytes:
                gf.write_bytes(_prev_bytes)
            elif gf.exists():
                gf.unlink()
            if _prev_env is not None:
                _os.environ["GBT_OWNER_SESSION"] = _prev_env

    def test_one_shot_scopes_stay_one_shot(self):
        """危险作用域**不许**跟着时段化 —— 分级只放日常类，这条是那次改动的边界。

        钉两件事：① 名单本身（owner_control 是总控钥匙，绝不能变成时段）；
        ② 行为（用一次即从账本删行，第二次即拒）。

        🔴 2026-10-13 加一项（主人令「直接改成终端YES才能使用就好了」）：新增
        `deploy_force` = **放行被门卡住的动作**的专用钥匙（未全绿晋升 / 未声明落点 / 公网中继），
        它必须也是**一次性** —— 每放一次要主人**单独**发一次，不能变成"开一次管十分钟"。
        """
        import json as _j
        import time as _t
        from pathlib import Path as _P
        from gbt_allinone import auth_gate as _AG
        from gbt_allinone.security import policy as _Pol

        self.assertEqual(sorted(_AG.ONE_SHOT_SCOPES),
                         ["data_export", "deploy_force", "deploy_publish",
                          "owner_control", "remote_device"])
        for s in _AG.ONE_SHOT_SCOPES:
            self.assertEqual(_AG.grant_mode(s), "one_shot", s)
        # 日常类必须是 window —— 否则这次改动等于没做
        for s in ("audio_output", "privacy_read", "filesystem_write", "process_execute"):
            self.assertEqual(_AG.grant_mode(s), "window", s)

        if _Pol.is_trusted():
            self.skipTest("主人本机会话下授权门直通，本用例不适用")
        gf = _P(_AG._GRANTS)
        before = gf.read_bytes() if gf.exists() else b""
        try:
            row = {"id": "g-dx", "scope": "data_export", "operator": "owner-manual",
                   "purpose": "一次性边界用例", "mode": "one_shot", "used": 0,
                   "granted_at": _t.strftime("%Y-%m-%dT%H:%M:%S"),
                   "expires_at": round(_t.time() + 300, 3)}
            gf.parent.mkdir(parents=True, exist_ok=True)
            gf.write_text(_j.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
            d1 = _AG.check_and_consume_many(["data_export"], detail="test")
            self.assertTrue(d1.get("ok"), d1)
            self.assertEqual(_AG._load_grants(), [], "data_export 必须一次性消耗（用掉即删行）")
            d2 = _AG.check_and_consume_many(["data_export"], detail="test")
            self.assertFalse(d2.get("ok"))
            self.assertTrue(d2.get("denied"))
        finally:
            if before:
                gf.write_bytes(before)
            elif gf.exists():
                gf.unlink()

    def test_auth_gate_ai_cannot_grant(self):
        # AI 无发放入口：能力清单里不存在 grant 类能力
        caps = [c["name"] for c in gbt.list_capabilities()]
        self.assertNotIn("auth_grant", caps)
        self.assertNotIn("auth_gate_grant", caps)

    def test_owner_control_substitutes_missing_scopes(self):
        """R-H98 修根源：owner_control 的**声明语义**必须真的成立。

        病根（改前读数）：全仓只有两行描述字符串（policy.SCOPE_DESCRIPTIONS /
        auth_gate.SCOPES），`check_and_consume_many` 从不读它 ⇒ 主人发了"总控"也放行不了
        任何动作（纸面能力，与"门自己也要被验过"同型）。
        现在：本次动作缺件时，一条 owner_control 顶掉这一次，且**一次性消耗**、
        有对应授权时不许被动用。
        """
        import json as _j
        import time as _t
        from pathlib import Path as _P
        from gbt_allinone import auth_gate as _AG
        from gbt_allinone.security import policy as _Pol

        if _Pol.is_trusted():
            self.skipTest("主人本机会话下授权门直通，本用例不适用")

        gf = _P(_AG._GRANTS)
        before = gf.read_bytes() if gf.exists() else b""

        def _grant(scope, gid):
            return {"id": gid, "scope": scope, "operator": "owner-manual", "purpose": "R-H98 用例",
                    "granted_at": _t.strftime("%Y-%m-%dT%H:%M:%S"),
                    "expires_at": round(_t.time() + 300, 3)}

        def _write(rows):
            gf.parent.mkdir(parents=True, exist_ok=True)
            gf.write_text("\n".join(_j.dumps(r, ensure_ascii=False) for r in rows)
                          + ("\n" if rows else ""), encoding="utf-8")

        try:
            # 1) 只有总控 → 顶掉这一次缺的作用域
            # 🔴 2026-10-19 口径翻正（主人令：只留三道人工授权）：
            #    原期望 ["deploy_publish","filesystem_write","process_execute"]；
            #    现在 filesystem_write / process_execute 已不再要票 ⇒ one_key_deploy 只缺 deploy_publish。
            _write([_grant("owner_control", "g-oc-1")])
            d1 = _Pol.authorize("one_key_deploy", {"target": "x", "into_global_production": True})
            self.assertTrue(d1.get("ok"), d1)
            # 2026-10-21 判据翻正（留痕 · 仓规「改判据必须写明哪条口径翻了/为什么翻/原期望是什么」）：
            #   原期望：["deploy_publish","filesystem_write","process_execute"]
            #   新期望：["deploy_publish","process_execute"]
            #   为什么翻：主人 2026-10-19 令后，auth_gate 把 filesystem_write 归入「机制层自动放行」
            #     （不在 ENFORCED_SCOPES 里）⇒ 它**根本不会进 missing**，也就永远不会进 substituted_for。
            #   上一版只改了上面第 507-509 行的注释、没改这条断言，于是「注释两条 / 断言三条」长期红。
            self.assertEqual(sorted(d1.get("substituted_for") or []),
                             ["deploy_publish", "process_execute"])
            self.assertEqual(_AG._load_grants(), [], "总控必须一次性消耗")

            # 2) 一次性：第二次即拒（且如实报缺什么）
            d2 = _Pol.authorize("one_key_deploy", {"target": "x"})
            self.assertFalse(d2.get("ok"))
            self.assertTrue(d2.get("denied"))
            # 2026-10-21 同上翻正：filesystem_write 已归机制层自动放行，不会进 missing。
            self.assertEqual(sorted(d2.get("missing") or []),
                             ["deploy_publish", "process_execute"])

            # 3) 逐条授权齐备时，总控不许被顺手消耗掉
            #    （filesystem_write 仍可发授权、只是不再必需；这里保留它，验"发了也不被动用总控"）
            _write([_grant("owner_control", "g-oc-2")]
                   + [_grant(s, "g-" + s) for s in
                      ("deploy_publish", "process_execute", "filesystem_write")])
            d3 = _Pol.authorize("one_key_deploy", {"target": "x"})
            self.assertTrue(d3.get("ok"), d3)
            self.assertEqual(d3.get("substituted_for") or [], [], "有对应授权时不该动用总控")
            left = {g["scope"] for g in _AG._load_grants()}
            self.assertIn("owner_control", left, "有对应授权时总控应原封不动")
        finally:
            if before:
                gf.write_bytes(before)
            elif gf.exists():
                gf.unlink()

    def test_scope_description_tables_stay_in_sync(self):
        """两张作用域表必须逐字一致（同义不同文 = 下一轮静默漂移的种子）。

        policy.SCOPE_DESCRIPTIONS 与 auth_gate.SCOPES 各写一份描述，历史上漂过
        （audio_output 漏注册那次就是这么来的）。这里把"逐字一致"变成硬约束：
        允许的唯一例外是 auth_gate 侧的 osint_private（policy 不声明）。
        """
        from gbt_allinone import auth_gate as _AG
        from gbt_allinone.security import policy as _P

        gate_only = {"osint_private"}
        policy_only = sorted(set(_P.SCOPE_DESCRIPTIONS) - set(_AG.SCOPES))
        self.assertEqual(policy_only, [], f"policy 声明但 auth_gate 没注册：{policy_only}")
        extra_gate = sorted(set(_AG.SCOPES) - set(_P.SCOPE_DESCRIPTIONS) - gate_only)
        self.assertEqual(extra_gate, [], f"auth_gate 多出来且不在豁免清单：{extra_gate}")
        drift = sorted(s for s in _P.SCOPE_DESCRIPTIONS
                       if s in _AG.SCOPES
                       and _P.SCOPE_DESCRIPTIONS[s] != _AG.SCOPES[s])
        self.assertEqual(drift, [], f"两张表描述不一致（漂移种子）：{drift}")

    def test_param_required_contract_has_evidence(self):
        """R-H98 修根源：能力注册表必须**声明自己的入参契约**，且声明要有出处。

        病根：注册表只声明"能力叫什么"，不声明"它需要什么输入" ⇒ 面板那份能力总目录
        只能发 {kind, confirm}，带参数的能力点下去就是一次空调用。
        本用例：① 结构（在册/启用/有参数名）② 目录带出契约 ③ 抽一批"副作用之前就拒"的
        能力，实测空调用确实被拒 —— 声明不是抄的，是可复现的。
        """
        from gbt_allinone import api as _api
        from gbt_allinone import caps_registry as _C
        from gbt_allinone.security import policy as _Pol

        for kind, spec in _C.PARAM_REQUIRED.items():
            self.assertIn(kind, _C.BENIGN_CAPS, f"{kind} 不在良性能力表")
            self.assertTrue(_C.BENIGN_CAPS[kind].get("safe"), f"{kind} 未标 safe")
            self.assertTrue(list(spec.get("params") or []), f"{kind} 有契约却没有参数名")
            self.assertTrue(str(spec.get("hint") or "").strip(), f"{kind} 缺少 hint")

        rows = {r["name"]: r for r in _C.all_caps()}
        for kind, spec in _C.PARAM_REQUIRED.items():
            self.assertTrue(rows[kind]["requires_params"], kind)
            self.assertEqual(rows[kind]["params"], list(spec["params"]), kind)

        provable = ("osint_scan", "sec_llm", "autopilot", "think_loop", "brain_execute",
                    "brain_unify", "one_key_deploy", "devour_github",
                    "codex_chat", "codex_turn_send", "codex_interrupt",
                    "pipeline_versions", "pipeline_rollback",
                    "wf_define", "wf_run", "wf_resume")
        for kind in provable:
            self.assertIn(kind, _C.PARAM_REQUIRED, f"{kind} 属于有参能力却没登记")
            with _Pol.owner_session():
                raw = _api.run_task(kind, {}, safe=True, probe=True)
            body = raw.get("gbt_result", raw)
            inner = body.get("result", body)
            ok = inner.get("ok") if isinstance(inner, dict) else None
            self.assertFalse(ok, f"{kind} 空调用居然成功了：{str(inner)[:200]}")

    def test_param_required_contract_has_teeth(self):
        """变异负对照：塞一个假能力名进 PARAM_REQUIRED，结构断言必须变红。"""
        from gbt_allinone import caps_registry as _C

        sentinel = "zz_param_probe_cap"
        self.assertNotIn(sentinel, _C.BENIGN_CAPS)
        _C.PARAM_REQUIRED[sentinel] = {"params": ["x"], "hint": "变异探针"}
        try:
            with self.assertRaises(AssertionError):
                self.test_param_required_contract_has_evidence()
        finally:
            _C.PARAM_REQUIRED.pop(sentinel, None)

    def test_wf_status_exposes_workflow_definitions(self):
        """R-H99b：万能插的**数据出口**必须存在且不破坏旧形状。

        由来：想给它做可视化时发现 `wf_status` 只回运行记录，**没人能列出工作流定义**
        ⇒ 可视化只能去偷读 `store/workflows.json`（绕开能力层，口径立刻散掉）。
        本用例锁三件事：① 显式要定义时确实带得出来，且与账本逐名一致；
        ② 定义里有画图需要的字段（id/kind/depends_on）；
        ③ **默认形状一字不变**（不要 `include_workflows` 时不许冒出 `workflows` 键）。
        """
        # 在（测试隔离的）store 里现定义一个工作流：这样断言的是"定义→列定义"的往返，
        # 而不是"恰好读得到主人的生产账本"——后者在隔离 store 下根本不成立（实测踩过）。
        wf_name = "t-plug-graph"
        defined = _body(gbt.run_task("wf_define", {"name": wf_name, "nodes": [
            {"id": "a", "kind": "health", "params": {}},
            {"id": "b", "kind": "ghost_guard", "params": {}, "depends_on": ["a"]},
        ]}, probe=True))
        self.assertEqual(defined["status"], "ok", defined)

        # ① 显式要定义 ⇒ 带得出来
        data = _body(gbt.run_task("wf_status", {"limit": 1, "include_workflows": True},
                                 probe=True))["result"]
        names = [w["name"] for w in data["workflows"]]
        self.assertIn(wf_name, names)
        self.assertEqual(data["count"], len(data["workflows"]))
        # ② 画图需要的字段必须在（id / kind / depends_on）
        wf = [w for w in data["workflows"] if w["name"] == wf_name][0]
        self.assertEqual(wf["node_count"], 2)
        self.assertEqual([n["id"] for n in wf["nodes"]], ["a", "b"])
        self.assertEqual([n["kind"] for n in wf["nodes"]], ["health", "ghost_guard"])
        self.assertEqual([n["depends_on"] for n in wf["nodes"]], [[], ["a"]])
        # ③ 默认形状一字不变（旧调用方不该被悄悄改口径）
        plain = _body(gbt.run_task("wf_status", {"limit": 1}, probe=True))["result"]
        self.assertIn("runs", plain)
        self.assertNotIn("workflows", plain)

    def test_osint_scan_public(self):
        r = _body(gbt.run_task("osint_scan", {"target": "example.com"}))
        self.assertEqual(r["status"], "ok")
        self.assertGreater(len(r["result"]["results"]), 0)

    def test_quant_strategy_reads_real_engine(self):
        r = _body(gbt.run_task("quant_strategy"))
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["result"].get("models"), "应读到真实量化引擎模型")

    def test_quant_params_reads_real_values(self):
        r = _body(gbt.run_task("quant_params"))
        self.assertEqual(r["status"], "ok")
        ep = r["result"].get("engine_params", {})
        self.assertTrue(any(bool(v) for v in ep.values()), "应读到真实数值参数")

    def test_platform_profile_reads_workspace(self):
        r = _body(gbt.run_task("platform_profile"))
        self.assertEqual(r["status"], "ok")
        self.assertIn("exists", r["result"])

    def test_engine_dag_with_template(self):
        gbt.run_task("wf_define", {"name": "t-engine", "nodes": [
            {"id": "a", "kind": "echo", "params": {"text": "one two"}},
            {"id": "b", "kind": "count_words",
             "params": {"text": "{{a.gbt_result.result.echo.text}}"},
             "depends_on": ["a"]},
        ]})
        r = _body(gbt.run_task("wf_run", {"name": "t-engine"}))
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["result"]["results"]["b"]["gbt_result"]["result"]["words"], 2)

    def test_engine_fail_fast_records_error(self):
        gbt.run_task("wf_define", {"name": "t-ff", "nodes": [
            {"id": "a", "kind": "echo", "params": {"text": "x"}},
            {"id": "b", "kind": "count_words",
             "params": {"text": "{{a.gbt_result.result.nope}}"},
             "depends_on": ["a"]},
        ]})
        r = _body(gbt.run_task("wf_run", {"name": "t-ff"}))
        self.assertEqual(r["result"]["status"], "failed")
        self.assertEqual(r["result"]["results"]["b"]["status"], "error")

    def test_codex_caps_contract(self):
        """契约测试（B 档第一步）：5 个官方 Codex 能力已注册，且走统一契约信封。

        本步只验"注册层"：读只读、写受策略守护（策略映射在第二步接入时补齐），
        并确认 run_task 对 5 个能力都返回 {ok, kind, result, error}，不抛异常。
        """
        from gbt_allinone import api as _api
        from gbt_allinone.caps_registry import BENIGN_CAPS, UNIMPLEMENTED_CAPS

        caps = ("codex_status", "codex_tools", "codex_thread_new",
                "codex_turn_send", "codex_interrupt")

        # 1) 已注册且未落在"登记未实现"名单里
        for cap in caps:
            self.assertIn(cap, BENIGN_CAPS, f"{cap} 未注册")
            self.assertNotIn(cap, UNIMPLEMENTED_CAPS, f"{cap} 不应在登记未实现名单")
            self.assertEqual(BENIGN_CAPS[cap]["domain"], "llm")
            self.assertTrue(str(BENIGN_CAPS[cap].get("desc", "")).strip(), f"{cap} 缺 desc")

        # 2) 统一契约信封：五个能力都返回四字段，且不抛异常
        for cap in caps:
            try:
                r = _api.run_task(cap, {})
            except Exception as exc:  # noqa: BLE001
                self.fail(f"{cap} 调用抛异常（契约要求永不抛）: {exc}")
            self.assertTrue({"ok", "kind", "result", "error"}.issubset(set(r.keys())),
                            f"{cap} 信封字段缺失: {sorted(r.keys())}")
            self.assertEqual(r["kind"], cap)

    def test_codex_write_caps_denied_without_grant(self):
        """契约测试（R-H99c 兑现旧占位）：Codex 写操作在**未授权路径**上必须被拒。

        由来（如实记账）：本用例前身是 `self.assertTrue(True)` 的占位（恒真 = 假绿），
        docstring 自己写着"第二步接入 api.py 后替换为『写操作未授权必被拒』的行为断言"——
        结果它把下面这个真洞盖了整整几天：

            改前实测 `policy.evaluate("codex_thread_new"/"codex_turn_send"/"codex_interrupt")`
            → **scopes=[] · restricted=False**（注册表里却写着"需 process_execute 授权"）。

        现在把它兑现成真断言：三个写能力逐个打一枪，未授权路径必须 denied，
        且 missing 必须指向它们声明的作用域。
        """
        from gbt_allinone.security import policy as _Pol

        # 口径：本用例只对"非主人会话"成立（主人本机会话是设计上的直通）
        if _Pol.is_trusted():
            self.skipTest("主人本机会话直通，本用例不适用")

        for cap in ("codex_thread_new", "codex_turn_send", "codex_interrupt"):
            decision = _Pol.evaluate(cap, {})
            # 🔴 2026-10-19 口径翻正（主人令逐字：「除了设计好的三个人工授权其他限制都给我去掉」）
            #    原期望：这三个写能力必须挂 process_execute 且未授权必被拒。
            #    现口径：process_execute 已不是人工授权（机制层票撤了）⇒ 它们不再 restricted；
            #    真正还会咬人的只剩三道护栏 —— 所以下面改成**反过来验**：
            #    ① 机制层写能力不再要票（不是"漏挂"，是主人令后的设计）
            #    ② 三道护栏仍然要票（这一条才是防漂移的硬判据）
            # 🔴 2026-10-19 口径回到正表：process_execute 属 G1 黑客全能力 ⇒ 这三个写能力必须 restricted
            self.assertTrue(decision.restricted,
                            f"{cap} 声明了要授权，策略层却没挂作用域（漂移）")
            self.assertIn("process_execute", decision.scopes, cap)

        # 三道护栏必须还咬人（G1 看/听、G2 出网计费、G3 生产面板）
        self.assertIn("privacy_read", _Pol.evaluate("vision", {"op": "see"}).scopes, "G1 黑客全能力掉了")
        self.assertIn("external_llm", _Pol.evaluate("codex_turn_send", {}).scopes, "G2 付款掉了")
        self.assertIn("deploy_publish", _Pol.evaluate("mirror_release", {}).scopes, "G3 生产面板掉了")

    def test_transmit_pulse_contract(self):
        """契约测试：transmit.pulse() 返回 {status, queue_size, last_transmission}，
        且任何状态下都不许抛异常（补回长期静默失效的"传输脉冲"可观测性）。"""
        from gbt_allinone.tentacle.brain import transmit as _TX

        required = {"status", "queue_size", "last_transmission"}

        # 态 1：有传输 → online
        _TX.transmit("payload", source="contract", channel="test")
        p1 = _TX.pulse()
        self.assertTrue(required.issubset(set(p1.keys())), f"字段缺失: {sorted(p1.keys())}")
        self.assertIn(p1["status"], {"idle", "online", "degraded"})

        # 态 2：审计不可用 → degraded（不抛异常）
        saved = dict(_TX._STATE)
        try:
            _TX._STATE["last_error"] = "audit_unavailable"
            p2 = _TX.pulse()
            self.assertEqual(p2["status"], "degraded")
            self.assertTrue(required.issubset(set(p2.keys())))

            # 态 3：内部状态被投毒 → 仍不抛异常且字段齐全
            _TX._STATE["sent"] = object()
            p3 = _TX.pulse()
            self.assertTrue(required.issubset(set(p3.keys())))
        finally:
            _TX._STATE.update(saved)

    def test_redaction_fallback_never_leaks(self):
        """契约测试：脱敏失败时 _redacted 绝不返回未脱敏原文（覆盖 5 种失败场景）。

        场景：①redact_text 调用抛 ImportError ②函数内部抛异常 ③返回 None
             ④返回空列表 ⑤返回格式不对。
        断言：任何一种失败下，输出都不包含原始敏感内容（宪章第九章第二条⑦款）。
        """
        from gbt_allinone import codex_bridge as _CB
        from gbt_allinone.security import data_policy as _DP

        secret = "sk-live-abcdef1234567890"
        raw = f"api_key={secret} user=alice"
        original = _DP.redact_text

        def _raise_inside(_text):
            raise RuntimeError("boom inside redactor")

        def _raise_import(*_args, **_kwargs):
            raise ImportError("simulated import failure")

        scenarios = {
            "import_fail": _raise_import,
            "raises_inside": _raise_inside,
            "returns_none": lambda _t: None,
            "returns_empty_list": lambda _t: [],
            "returns_bad_shape": lambda _t: [{"not": "a string"}],
        }
        try:
            for name, fake in scenarios.items():
                _DP.redact_text = fake
                out = _CB._redacted(raw)
                self.assertNotIn(secret, str(out), f"{name}: 泄漏了原文")
                self.assertTrue(str(out).strip(), f"{name}: 返回为空")
        finally:
            _DP.redact_text = original

    def test_policy_scopes_are_registered(self):
        """契约测试：policy 声明的每个作用域都必须注册在 auth_gate.SCOPES。

        防止"policy 声明了 scope 但没注册 → 任何授权都满足不了 → 该能力对非主人
        调用者永久不可授权"这类结构缺口。

        R113 重写：旧版有两个致命缺陷，断言恒真、永远抓不到漂移 ——
          ① 正则 `"([a-z_]+:[a-z_]+)"` 要求串里带冒号，而作用域名不含冒号 → 匹配恒为空；
          ② 第二个正则是硬编码白名单，恰好等于当时刚修好的 5 个作用域。
        实测旧版 would_fail_set == []，即 R113 之前 deploy_publish / filesystem_write /
        data_export / remote_device 等 9 个作用域漂移了整整三天都没被它拦住。
        现改为真值集合直接从 policy.SCOPE_DESCRIPTIONS 推导；变异负对照见
        test_policy_scope_registry_has_teeth。
        """
        from gbt_allinone import auth_gate as _A
        from gbt_allinone.security import policy as _P

        declared = set(_P.SCOPE_DESCRIPTIONS)
        missing = sorted(scope for scope in declared if scope not in _A.SCOPES)
        self.assertEqual(missing, [],
                         f"policy 声明但未注册进 auth_gate.SCOPES 的作用域：{missing}")
        # O71（2026-09-19 风哥拍）：**反向断言** —— 单向契约只能抓"声明了没注册"，
        # 反方向（注册了没声明）此前没人管（实测 `osint_private` 正属此类）。
        # 豁免清单是**显式**的：只在 auth_gate 侧定义、policy 不声明的作用域，必须在此点名。
        allowed_gate_only = {"osint_private"}
        extra = sorted(s for s in _A.SCOPES
                       if s not in declared and s not in allowed_gate_only)
        self.assertEqual(extra, [],
                         f"auth_gate 注册但 policy 未声明、且不在豁免清单：{extra}")

    def test_policy_scope_registry_has_teeth(self):
        """变异负对照：给 policy 塞一个假作用域，上面那条断言必须变红。

        同时断言旧版逻辑在同一变异下仍然通过 —— 证明旧断言无牙、新断言有牙。
        """
        import inspect as _inspect
        import re as _re
        from gbt_allinone import auth_gate as _A
        from gbt_allinone.security import policy as _P

        sentinel = "zz_probe_scope"
        self.assertNotIn(sentinel, _A.SCOPES)
        _P.SCOPE_DESCRIPTIONS[sentinel] = "变异探针"
        try:
            with self.assertRaises(AssertionError):
                self.test_policy_scopes_are_registered()
            old_referenced = set(_re.findall(
                r'"(browser_control|desktop_control|external_llm|process_execute|osint_private)"',
                _inspect.getsource(_P)))
            old_missing = sorted(s for s in old_referenced if s not in _A.SCOPES)
            self.assertEqual(old_missing, [], "旧逻辑在变异下也应为空（证明其无牙）")
        finally:
            _P.SCOPE_DESCRIPTIONS.pop(sentinel, None)
    def test_pipeline_publish_and_block(self):
        from gbt_allinone.security import policy as _policy
        # 发布属受守护动作：测试以主人可信会话执行（与 CLI/GUI 同路径）。
        # 授权门自身的语义由 test_auth_gate_flow 单独覆盖，不在这里重复验证。
        with _policy.owner_session():
            ok = _body(gbt.run_task("pipeline_submit", {
                "name": "t-ok.txt", "content": "gbt v8",
                "meta": {"actor": "test", "purpose": "unit"}}))
            self.assertEqual(ok["result"]["status"], "published")
            bad = _body(gbt.run_task("pipeline_submit", {
                "name": "t-bad.txt", "content": "x",
                "meta": {"purpose": "no-actor"}}))
            self.assertEqual(bad["result"]["status"], "blocked")

    def test_ghost_guard_clean(self):
        r = _body(gbt.run_task("ghost_guard", {}))
        self.assertTrue(r["result"]["clean"], f"防复发检测应干净: {r['result']['findings']}")

    def test_schedule_define_tick_status(self):
        gbt.run_task("wf_define", {"name": "t-sched", "nodes": [
            {"id": "a", "kind": "health", "params": {}}]})
        r = _body(gbt.run_task("sched_define", {
            "name": "t-sched-run", "workflow": "t-sched", "every_seconds": 1}))
        self.assertEqual(r["status"], "ok")
        import time as _t
        _t.sleep(1.2)
        tick = _body(gbt.run_task("sched_tick", {}))
        self.assertGreaterEqual(tick["result"]["count"], 1)
        st = _body(gbt.run_task("sched_status", {"name": "t-sched-run"}))
        self.assertEqual(st["result"]["t-sched-run"]["last_status"], "ok")

    def test_schedule_rejects_missing_workflow(self):
        r = _body(gbt.run_task("sched_define", {
            "name": "t-bad-sched", "workflow": "no-such-wf", "every_seconds": 10}))
        self.assertEqual(r["status"], "error")

    def test_services_inspect(self):
        r = _body(gbt.run_task("svc_inspect", {}))
        self.assertGreater(r["result"]["total"], 0)
        # 至少验证数据结构完整
        first = next(iter(r["result"]["services"].values()))
        for k in ("host", "port", "up", "checked_at"):
            self.assertIn(k, first)

    def test_services_register_unregister(self):
        reg = _body(gbt.run_task("svc_inspect", {}))
        # 注册一个必然不通的探针端口再验证 down 路径
        from gbt_allinone import services as S
        S.register("t-dead", "127.0.0.1", 1, owner="test", note="probe")
        try:
            snap = S.inspect("t-dead")
            self.assertFalse(snap["services"]["t-dead"]["up"])
        finally:
            S.unregister("t-dead")

    def test_longrun_success_flow(self):
        r = _body(gbt.run_task("lr_submit", {
            "description": "测试成功流", "kind": "health", "acceptance": ["status_ok"]}))
        self.assertEqual(r["status"], "ok")
        tid = r["result"]["task_id"]
        t = _body(gbt.run_task("lr_tick", {"max_tasks": 5}))
        self.assertTrue(any(x["task_id"] == tid and x["status"] == "done" for x in t["result"]["ran"]))
        st = _body(gbt.run_task("lr_status", {"task_id": tid}))
        self.assertEqual(st["result"]["status"], "done")

    def test_longrun_fail_then_escalate(self):
        r = _body(gbt.run_task("lr_submit", {
            "description": "测试升级流", "kind": "osint_scan",
            "params": {"target": "127.0.0.1"}, "max_attempts": 1}))
        tid = r["result"]["task_id"]
        t = _body(gbt.run_task("lr_tick", {"max_tasks": 5}))
        self.assertTrue(any(x["task_id"] == tid and x["status"] == "failed" for x in t["result"]["ran"]))
        st = _body(gbt.run_task("lr_status", {"task_id": tid}))
        self.assertIn("escalation", st["result"])
        self.assertGreater(len(st["result"]["escalation"]["options"]), 0)

    def test_longrun_rejects_unregistered_kind(self):
        r = _body(gbt.run_task("lr_submit", {
            "description": "非法能力", "kind": "no_such_cap"}))
        self.assertEqual(r["status"], "error")

    def test_tactics_urgency(self):
        r = _body(gbt.run_task("tactics_advise", {"user_text": "这个急，马上要"}))
        self.assertEqual(r["result"]["posture"], "results_first")

    def test_tactics_failure_overrides(self):
        r = _body(gbt.run_task("tactics_advise", {
            "user_text": "随便", "situation": "failed"}))
        self.assertEqual(r["result"]["posture"], "steady_problemsolve")
        self.assertTrue(all("不改" in h or "如实" in h or "方案" in h
                            for h in r["result"]["honesty"]))

    def test_tactics_fatigue(self):
        r = _body(gbt.run_task("tactics_advise", {"user_text": "我累了，先这样，明天再说"}))
        self.assertEqual(r["result"]["posture"], "compress")

    def test_engine_resume_reuses_done_nodes(self):
        gbt.run_task("wf_define", {"name": "t-resume", "nodes": [
            {"id": "a", "kind": "echo", "params": {"text": "resume-test"}}]})
        r1 = _body(gbt.run_task("wf_run", {"name": "t-resume"}))
        rid = r1["result"]["run_id"]
        from gbt_allinone import engine
        r2 = engine.resume_run(rid)
        self.assertEqual(r2["status"], "ok")
        self.assertEqual(r2["reused_nodes"], 1)

    def test_bluetooth_capability(self):
        # 蓝牙能力：模块存在 + 状态报告真实（BLE 后端/操作清单）
        # 真机验证记录（2026-09-13）：scan 扫到 11 台设备；connect 枚举 9 服务/6 可写特征；
        # read 读出 iPhone/Apple Inc./电量 0x5F；write 对真实设备 Apple Continuity
        # 服务写入成功（write-without-response）——全链路真机验证通过
        r = _body(gbt.run_task("bluetooth", {"op": "status"}))
        self.assertTrue(r["result"]["ok"])
        self.assertIn("bleak", r["result"]["ble_backend"])
        for op in ("scan", "connect", "read", "write"):
            self.assertIn(op, r["result"]["ops"])


        # V8 补齐后：vision/voice/browser 已接真实后端（不再是 stub）
        # 语义升级：空参调用应给出明确的参数/依赖指引（诚实降级），而非崩溃
        #
        # 🔴 第 29 条：这一段验的是"空参降级指引"，而未授权时**根本调不到能力本体**
        # （vision/voice 走 `desktop_control` 等作用域的门）⇒ 前提不具备 ⇒ **具名 skip**，
        # 不许把它报成红 —— 那会让红字说"蓝牙失败"而真因是"没授权"（名字与内容不符的错报）。
        # 授权之后，下面这几条会照常逐条验。
        _pre = _body(gbt.run_task("vision", {}))
        _env = _pre if isinstance(_pre, dict) and _pre.get("denied") is True \
            else (_pre.get("result") if isinstance(_pre, dict) else None)
        if isinstance(_env, dict) and _env.get("denied") is True:
            _miss = _env.get("missing") or _env.get("scopes") or []
            self.assertTrue(bool(_miss), "拒绝信封必须写明缺哪个作用域（vision 段）")
            self.assertTrue(bool(_env.get("how_to_grant")), "拒绝信封必须给出 how_to_grant（vision 段）")
            raise unittest.SkipTest("未授权（%s）—— 空参降级这几条要授权后才能验" % ",".join(_miss))
        # vision 默认 op=analyze：无图时截屏分析（真实后端）
        r = _pre
        self.assertIn(r["result"].get("ok"), (True, False))
        # voice 默认 op=tts：缺 text 时应报参数错误（user_error 顶层无 result）
        r = _body(gbt.run_task("voice", {}))
        self.assertIn("text", str(r.get("message", r.get("result", ""))))
        # voice op=status：状态诚实报告
        r = _body(gbt.run_task("voice", {"op": "status"}))
        self.assertTrue(r["result"]["ok"])
        # browser 默认 op=open：缺 url 时应报参数错误
        r = _body(gbt.run_task("browser", {}))
        self.assertIn("url", str(r.get("message", r.get("result", ""))))
        # browser op=status：标准库能力可用 + automate 依赖如实
        r = _body(gbt.run_task("browser", {"op": "status"}))
        self.assertTrue(r["result"]["ok"])
        # browser op=fetch：真实抓取（需网络；失败也验证路由已通）
        r = _body(gbt.run_task("browser", {"op": "fetch", "url": "https://example.com"}))
        self.assertIn(r["result"].get("ok"), (True, False))

    def test_wf_resume_via_api(self):
        gbt.run_task("wf_define", {"name": "t-resume-api", "nodes": [
            {"id": "a", "kind": "echo", "params": {"text": "api-resume"}}]})
        r1 = _body(gbt.run_task("wf_run", {"name": "t-resume-api"}))
        rid = r1["result"]["run_id"]
        r2 = _body(gbt.run_task("wf_resume", {"run_id": rid}))
        self.assertEqual(r2["result"]["status"], "ok")
        self.assertGreaterEqual(r2["result"]["reused_nodes"], 1)

    def test_selfscan_clean(self):
        r = _body(gbt.run_task("selfscan", {}))
        self.assertIn(r["result"]["verdict"], ("clean", "P1"))
        self.assertTrue(r["result"]["sections"]["routing"]["ok"],
                        f"路由断连: {r['result']['sections']['routing']}")
        self.assertTrue(r["result"]["sections"]["modules"]["ok"])

    def test_selfscan_detects_broken_routing(self):
        from gbt_allinone import selfscan as S
        orig = S._routed_kinds
        def fake():
            kinds, prefixes, stubs = orig()
            kinds.discard("health")
            return kinds, prefixes, stubs
        S._routed_kinds = fake
        try:
            r = S.check_routing()
            self.assertIn("health", r["unrouted"])
            self.assertFalse(r["ok"])
        finally:
            S._routed_kinds = orig

    def test_alerts_structure(self):
        r = _body(gbt.run_task("alerts", {"last": 100}))
        self.assertIn("quiet", r["result"])
        self.assertIn("anomalies", r["result"])

    def test_quant_is_real(self):
        r = _body(gbt.run_task("quant", {}))
        self.assertEqual(r["status"], "ok")
        self.assertIn("profile", r["result"])
        self.assertIn("engine_params", r["result"])

    def test_audit_signal_grading(self):
        from gbt_allinone import selfscan as S
        a = S.check_audit(last=500)
        for sig in ("runtime", "guard", "trace"):
            self.assertIn(sig, a["by_signal"])
        self.assertEqual(a["by_signal"]["runtime"], a["runtime_faults"])

    def test_tentacle_eye_ready(self):
        from gbt_allinone.tentacle import bridge as TB
        self.assertTrue(TB.eye_ready(), f"触手未就绪: {TB.eye_error()}")

    def test_tentacle_see(self):
        # see() 增量模式可能返回变化区域局部图（尺寸不定）——只断言采集健康；
        # 全屏尺寸语义由 vision_snapshot（强制全屏帧）验证。
        r = _body(gbt.run_task("tentacle", {"action": "see"}))
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["result"].get("ok"))
        size = r["result"].get("size") or [0, 0]
        self.assertGreater(size[0], 0)
        self.assertGreater(size[1], 0)

    def test_tentacle_vision_snapshot_full_frame(self):
        r = _body(gbt.run_task("tentacle", {"action": "vision_snapshot"}))
        self.assertEqual(r["status"], "ok")
        res = r["result"]
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("size"), [1920, 1080])   # 强制全屏帧：尺寸稳定
        self.assertTrue(res.get("fingerprint"))

    def test_tentacle_manifest(self):
        r = _body(gbt.run_task("tentacle_manifest", {}))
        self.assertEqual(r["status"], "ok")
        self.assertIn("铁律", r["result"]["manifest"])
        self.assertTrue(r["result"]["eye_ready"])

    def test_tentacle_status_coverage(self):
        r = _body(gbt.run_task("tentacle_status", {}))
        self.assertTrue(r["result"]["diagnose"]["ok"])
        self.assertGreater(r["result"]["coverage"]["total_domains"], 5)

    def test_tentacle_requires_action(self):
        r = _body(gbt.run_task("tentacle", {}))
        self.assertEqual(r["status"], "error")

    def test_tentacle_unknown_method(self):
        from gbt_allinone.security import policy as _policy
        # 本条验的是"统一接口层正确路由到触手 + 触手层如实报无此能力"，
        # 必须先过授权门（tentacle 依赖 desktop_control），否则会被拦成 denied。
        with _policy.owner_session():
            r = _body(gbt.run_task("tentacle", {"action": "no_such_tentacle_method_xyz"}))
            self.assertEqual(r["status"], "ok")  # 统一接口层 ok（正确路由到触手）
            self.assertFalse(r["result"].get("ok"))  # 触手层如实报无此能力

    def test_tentacle_process_list(self):
        r = _body(gbt.run_task("tentacle", {"action": "process_list"}))
        self.assertTrue(r["result"].get("ok"))
        self.assertGreater(len(r["result"].get("processes", r["result"].get("list", []))), 3)

    def test_autopilot_dry_run(self):
        from gbt_allinone.security import policy as _policy
        # autopilot 依赖 external_llm 授权：测试以主人可信会话执行（与 CLI/GUI 同路径）。
        #
        # 终态由内层 selfscan 的 verdict 决定（autopilot.py：
        #   dry_run → "dry_run" | clean → "done" | 其他 → "stopped"）。
        # 本套件是隔离设计：顶部把 GBT_STORE_DIR 指到全新空 store，空 store 下
        # selfscan 会如实报 P0（缺目录），因此 autopilot 如实报 "stopped"——这是
        # 文档化行为（"未达 clean 如实报 stopped，绝不无限循环"），不是缺陷。
        # 所以这里只断言文档化终态集合与轮次推进；dry_run 的精确语义
        # （内层 verdict == "dry_run"）在"已准备 store"的场景下另行覆盖。
        with _policy.owner_session():
            r = _body(gbt.run_task("autopilot", {
                "goal": "健康检查并发布结论", "max_rounds": 1, "dry_run": True}))
            self.assertIn(r["result"]["status"], ("dry_run", "done", "stopped"))
            self.assertGreaterEqual(r["result"]["rounds_used"], 1)

    def test_autopilot_requires_goal(self):
        from gbt_allinone.security import policy as _policy
        # 本条验的是"缺 goal → user_error"的参数校验，必须先过授权门
        # （autopilot 依赖 external_llm），否则会被门禁拦成 denied，测不到校验逻辑。
        with _policy.owner_session():
            r = _body(gbt.run_task("autopilot", {}))
            self.assertEqual(r["status"], "error")

    def test_autopilot_validates_llm_plan(self):
        """本地校验器必须拒掉**未注册**能力 —— 判据不该绑在某一位的历史状态上。

        ⚠️ 本用例原来拿 `keylogger` 当"未注册样本"。2026-09-25 Owner 令后它**已注册**，
        样本失效 ⇒ 用例变成假红。**修法是换一个真未注册的名字，不是把用例删掉**：
        它的意图（"未注册能力应被拒绝"）一个字没变。
        """
        from gbt_allinone import autopilot as AP
        bad_nodes = [{"id": "a", "kind": "no_such_capability_xyz", "params": {}}]
        try:
            AP._validate_nodes(bad_nodes)
            self.fail("未注册能力应被拒绝")
        except AP.AutopilotError:
            pass
        # 正控：已注册的名字不许被误拒（`keylogger` 从"负样本"改任"正控"）
        AP._validate_nodes([{"id": "a", "kind": "keylogger", "params": {}}])

    def test_truth_scan_readonly(self):
        r = _body(gbt.run_task("truth_scan", {}))
        self.assertEqual(r["result"]["verdict"], "clean")
        self.assertEqual(r["result"]["FAKE"], 0)

    def test_tentacle_chain(self):
        r = _body(gbt.run_task("tentacle", {"action": "chain", "args": [[
            {"action": "screen_size"}, {"action": "see"}]]}))
        # 复合动作不在只读白名单 ⇒ 挂 desktop_control；未授权时**具名 skip**，
        # 不许把"门按设计拦我"报成"链坏了"（第 29 条）。
        self.assertTrue(_ok_or_skip(self, r, "tentacle.chain"))
        self.assertEqual(r["result"].get("completed"), 2)

    def test_tentacle_screenshot_diff(self):
        gbt.run_task("tentacle", {"action": "screenshot_diff"})
        r = _body(gbt.run_task("tentacle", {"action": "screenshot_diff"}))
        self.assertTrue(r["result"].get("ok"))
        self.assertIn("current_hash", r["result"])

    def test_tentacle_monitor_snapshot(self):
        r = _body(gbt.run_task("tentacle", {"action": "monitor",
            "args": [[{"on": "text_appear", "text": "XYZ_NEVER", "action": "see"}]],
            "kwargs": {"duration": 0.6, "interval": 0.3}}))
        self.assertTrue(r["result"].get("ok"))
        self.assertEqual(r["result"].get("triggered"), 0)

    def test_tentacle_active_window(self):
        r = _body(gbt.run_task("tentacle", {"action": "see_active_window"}))
        self.assertTrue(r["result"].get("ok"))
        self.assertIn("title", r["result"].get("window", {}))

    def test_perf_baseline(self):
        """性能基线守卫：热路径能力超时即失败（防退化）。

        阈值 = 实测中位数 x 10 的富余量（CI 机器可能慢，但不允许数量级退化）。

        🔴 2026-09-23 改「三样本取中位数」：原版**只测一次**，实测在机器有别的重活时
        （同日并行跑 158 条能力探针）报 `ghost_guard 958ms > 500ms` —— 而同一时刻
        探针自己量到 ghost_guard 是 817ms、机器空下来后回到阈值内。
        **单样本判红 = 把"机器忙"读成"代码退化"**，正是"扫出一堆假故障"的老病根。
        取中位数不会掩盖真退化（真退化三样本会**一起**高），但毛刺不再定罪；
        失败时把三个样本原样打出来，读的人能自己看分布。
        """
        import time as _t
        cases = [
            ("health", 50), ("ghost_guard", 500), ("selfscan", 500),
        ]
        for kind, limit_ms in cases:
            gbt.run_task(kind)  # 预热：冷导入一次性成本不计入热路径基线
            samples, r = [], None
            for _ in range(3):
                t0 = _t.perf_counter()
                r = _body(gbt.run_task(kind))
                samples.append((_t.perf_counter() - t0) * 1000)
            samples.sort()
            ms = samples[len(samples) // 2]
            self.assertEqual(r["status"], "ok", f"{kind} 应成功")
            self.assertLess(ms, limit_ms,
                            f"{kind} 性能退化: 中位 {ms:.0f}ms > {limit_ms}ms"
                            f"（三样本 {[round(s) for s in samples]}ms）")

    def test_sec_surface_real(self):
        r = _body(gbt.run_task("sec_surface", {}))
        self.assertTrue(r["result"].get("ok"))
        self.assertGreater(r["result"].get("total_vectors", 0), 10)

    def test_sec_defenses_all_pass(self):
        r = _body(gbt.run_task("sec_defenses", {}))
        self.assertTrue(r["result"].get("ok"))
        self.assertEqual(r["result"].get("passed"), r["result"].get("total"))

    def test_sec_llm_configured(self):
        r = _body(gbt.run_task("sec_llm", {"prompt": "在线吗一个词", "max_tokens": 3000, "timeout": 240}))
        # 🔴 实测（第 13 轮）：这里**不是**"缺 key"，而是 `external_llm` 那道门**先拦**了 ——
        # 「把当前任务数据发送到外部大模型服务」必须人工授权，返回的是**拒绝信封**：
        # `denied=true · missing=["external_llm"] · how_to_grant=[…]`。
        # ⇒ 用**拒绝感知**的助手（不是标记型那个：标记型认的是"未配置密钥"，
        #    而这条路根本走不到 LLM 层那句话）。未授权 ⇒ 具名 skip，不许报成"运行失败"。
        self.assertTrue(_ok_or_skip(self, r, "sec_llm"))
        self.assertTrue(r["result"].get("reply") or r["result"].get("reasoning_only"))

    def test_mcp_full_chain(self):
        r = _body(gbt.run_task('mcp_connect', {
            'server': 'mcp-test',
            'command': ['npx', '-y', '@modelcontextprotocol/server-everything']}))
        self.assertTrue(_ok_or_skip(self, r, "mcp_connect"))
        tools = _body(gbt.run_task('mcp_tools', {'server': 'mcp-test'}))
        self.assertGreater(tools['result'].get('count', 0), 5)
        call = _body(gbt.run_task('mcp_call', {
            'server': 'mcp-test', 'tool': 'echo',
            'arguments': {'message': 'test'}}))
        self.assertTrue(call['result'].get('ok'))

    def test_mcp_requires_server(self):
        from gbt_allinone.security import policy as _policy
        # 本条验的是"MCP 未连接 → error"的前置校验，必须先过授权门
        # （mcp_call 依赖 process_execute），否则会被门禁拦成 denied，测不到前置逻辑。
        with _policy.owner_session():
            r = _body(gbt.run_task('mcp_call', {'tool': 'x'}))
            self.assertEqual(r['status'], 'error')

    def test_devour_cycle(self):
        r = _body(gbt.run_task("devour_scan", {}))
        self.assertTrue(r["result"].get("ok"))
        self.assertGreater(r["result"].get("total_caps", 0), 70)
        rf = _body(gbt.run_task("devour_reflect", {}))
        self.assertTrue(rf["result"].get("ok"))

    def test_devour_github_real(self):
        r = _body(gbt.run_task("devour_github", {
            "repo": "https://github.com/sindresorhus/slugify", "name": "slugify-test"}))
        self.assertTrue(_ok_or_skip(self, r, "devour_github"))
        self.assertGreater(r["result"].get("knowledge_chars", 0), 100)

    def test_wf_when_conditional(self):
        r = _body(gbt.run_task("wf_define", {"name": "t-when", "nodes": [
            {"id": "h", "kind": "health", "params": {}},
            {"id": "yes", "kind": "count_words", "params": {"text": "a b"}, "depends_on": ["h"], "when": "h.ok == true"},
            {"id": "no", "kind": "count_words", "params": {"text": "c d"}, "depends_on": ["h"], "when": "h.ok == false"},
        ]}))
        self.assertTrue(r["result"]["ok"])
        rn = _body(gbt.run_task("wf_run", {"name": "t-when", "fail_fast": False}))["result"]
        self.assertEqual(rn["nodes"]["yes"], "ok")
        self.assertEqual(rn["nodes"]["no"], "skipped")
        self.assertEqual(rn["status"], "ok")

    def test_wf_fallback(self):
        r = _body(gbt.run_task("wf_define", {"name": "t-fb", "nodes": [
            {"id": "bad", "kind": "pipeline_submit",
             "params": {"name": "fb.txt", "content": "y", "meta": {"actor": "a"}},
             "fallback": {"kind": "echo", "params": {"degraded": True}}},
        ]}))
        self.assertTrue(r["result"]["ok"])
        rn = _body(gbt.run_task("wf_run", {"name": "t-fb", "fail_fast": False}))["result"]
        self.assertEqual(rn["nodes"]["bad"], "ok")
        self.assertEqual(rn["results"]["bad"].get("gbt_fallback", {}).get("to"), "echo")

    def test_wf_timeout(self):
        # sec_scan 约 1.5s，用 0.01s 超时必定触发（确定性，不靠竞态）
        _body(gbt.run_task("wf_define", {"name": "t-to", "nodes": [
            {"id": "slow", "kind": "sec_scan", "params": {"severity": "low"}, "timeout": 0.01},
        ]}))
        rn = _body(gbt.run_task("wf_run", {"name": "t-to", "fail_fast": False}))["result"]
        self.assertEqual(rn["nodes"]["slow"], "error")

    def test_wf_retry_backoff(self):
        _body(gbt.run_task("wf_define", {"name": "t-bo", "nodes": [
            {"id": "f", "kind": "pipeline_submit",
             "params": {"name": "bo.txt", "content": "q", "meta": {"actor": "a"}},
             "retry_backoff": 0.1},
        ]}))
        import time as _t
        t0 = _t.time()
        rn = _body(gbt.run_task("wf_run", {"name": "t-bo", "fail_fast": False, "max_node_retries": 2}))["result"]
        self.assertGreaterEqual(_t.time() - t0, 0.2)   # 2 次退避 × 0.1s

    def test_wf_define_rejects_bad_fallback(self):
        r = _body(gbt.run_task("wf_define", {"name": "t-badfb", "nodes": [
            {"id": "x", "kind": "health", "params": {},
             "fallback": {"kind": "no_such_cap"}},
        ]}))
        self.assertEqual(r.get("status"), "error")

    def test_transfer_ops(self):
        r = _body(gbt.run_task("transfer", {"op": "map",
            "data": [{"n": "a"}, {"n": "b"}], "field": "n"}))
        self.assertEqual(r["result"]["data"], ["a", "b"])
        r2 = _body(gbt.run_task("transfer", {"op": "filter",
            "data": [{"v": 1}, {"v": 5}], "expr": "item.v > 3"}))
        self.assertEqual(r2["result"]["count"], 1)
        r3 = _body(gbt.run_task("transfer", {"op": "merge",
            "data": [{"a": 1}, {"b": 2}]}))
        self.assertEqual(r3["result"]["data"], {"a": 1, "b": 2})

    def test_wf_fanin_aggregation(self):
        _body(gbt.run_task("wf_define", {"name": "t-fanin", "nodes": [
            {"id": "a", "kind": "count_words", "params": {"text": "x y"}},
            {"id": "b", "kind": "count_words", "params": {"text": "z"}},
            {"id": "g", "kind": "transfer",
             "params": {"op": "map", "data": "{{*.gbt_result.result.words}}"},
             "depends_on": ["a", "b"]},
        ]}))
        rn = _body(gbt.run_task("wf_run", {"name": "t-fanin", "fail_fast": False}))["result"]
        self.assertEqual(rn["nodes"]["g"], "ok")
        self.assertEqual(rn["results"]["g"]["gbt_result"]["result"]["data"], [2, 1])

    def test_wf_cache(self):
        _body(gbt.run_task("wf_define", {"name": "t-cache", "nodes": [
            {"id": "c", "kind": "count_words", "params": {"text": "cache me"}, "cache": True, "cache_ttl": 60},
        ]}))
        _body(gbt.run_task("wf_run", {"name": "t-cache"}))
        r2 = _body(gbt.run_task("wf_run", {"name": "t-cache"}))["result"]
        self.assertIn("gbt_cached", r2["results"]["c"])

    def test_wf_routes(self):
        _body(gbt.run_task("wf_define", {"name": "t-routes", "nodes": [
            {"id": "h", "kind": "health", "params": {}},
            {"id": "r", "depends_on": ["h"], "routes": [
                {"when": "h.ok == true", "kind": "count_words", "params": {"text": "ok branch"}},
                {"when": "true", "kind": "echo", "params": {"fb": True}},
            ]},
        ]}))
        rn = _body(gbt.run_task("wf_run", {"name": "t-routes", "fail_fast": False}))["result"]
        self.assertEqual(rn["nodes"]["r"], "ok")
        self.assertEqual(rn["results"]["r"]["gbt_route"]["index"], 0)

    def test_wf_subworkflow(self):
        _body(gbt.run_task("wf_define", {"name": "t-sub-inner", "nodes": [
            {"id": "i", "kind": "health", "params": {}}]}))
        _body(gbt.run_task("wf_define", {"name": "t-sub-outer", "nodes": [
            {"id": "call", "kind": "wf_run", "params": {"name": "t-sub-inner", "fail_fast": False}}]}))
        rn = _body(gbt.run_task("wf_run", {"name": "t-sub-outer", "fail_fast": False}))["result"]
        self.assertEqual(rn["nodes"]["call"], "ok")

    def test_wf_routes_validation(self):
        r = _body(gbt.run_task("wf_define", {"name": "t-badroute", "nodes": [
            {"id": "x", "routes": [{"when": "true", "kind": "no_such_cap"}]}]}))
        self.assertEqual(r.get("status"), "error")

    def test_brain_route_cn(self):
        r = _body(gbt.run_task("brain_route", {"intent": "统计一段文字的词数"}))
        self.assertEqual(r["result"]["best"]["kind"], "count_words")

    def test_brain_execute(self):
        r = _body(gbt.run_task("brain_execute", {"kind": "count_words", "text": "a b c"}))
        self.assertTrue(r["result"]["ok"])
        self.assertEqual(r["result"]["result"]["words"], 3)

    def test_brain_health_five_dims(self):
        r = _body(gbt.run_task("brain_health", {}))
        self.assertEqual(r["result"]["total_dims"], 5)
        self.assertEqual(r["result"]["healthy_dims"], 5)

    def test_brain_unify_chain(self):
        r = _body(gbt.run_task("brain_unify", {"goal": "统计词数", "kind": "count_words", "text": "x y"}))
        self.assertTrue(r["result"]["ok"])
        for dim in ("route", "execute", "verify", "health"):
            self.assertIn(dim, r["result"]["chain"])

    # ── 单一路由权威（Owner 2026-09-19 拍 A 案：brain_exec.route 必须接主路）──

    def test_brain_route_declares_path_and_degradation(self):
        """路由必须自报来路：path 只许 semantic/heuristic；降级不许静默。"""
        d = _op(gbt.run_task("brain_route", {"intent": "统计一段文字的词数"}))
        self.assertIn(d["path"], ("semantic", "heuristic"))
        if d["path"] == "heuristic":
            self.assertTrue(d["degraded"], "走辅路却没标 degraded —— 降级被静默了")
            self.assertTrue(d.get("degraded_reason"), "降级没给原因 —— 违反如实报")

    def test_brain_route_uses_semantic_main_path(self):
        """主路可用时，brain_exec.route 必须照主路走，不自己另判。"""
        from gbt_allinone import brain_exec, semantic_route
        fake = {"ok": True, "path": "semantic", "method": "see", "confidence": 0.9,
                "reason": "看屏幕", "provider": "stub"}
        with mock.patch.object(semantic_route, "route",
                               side_effect=lambda intent, mode="auto": dict(fake)):
            rt = brain_exec.route("给我看看当前屏幕")
        self.assertEqual(rt["path"], "semantic")
        self.assertFalse(rt["degraded"])
        # 主路选中触手方法 ⇒ 落在 tentacle 能力并把方法名带住（不丢参数）
        self.assertEqual(rt["best"]["kind"], "tentacle")
        self.assertEqual(rt["best"]["method"], "see")

    def test_brain_route_capability_from_main_path(self):
        """主路直接点中本体能力名 ⇒ 不套 tentacle 壳。"""
        from gbt_allinone import brain_exec, semantic_route
        fake = {"ok": True, "path": "semantic", "method": "count_words",
                "confidence": 1.0, "reason": "词数", "provider": "stub"}
        with mock.patch.object(semantic_route, "route",
                               side_effect=lambda intent, mode="auto": dict(fake)):
            rt = brain_exec.route("统计词数")
        self.assertEqual(rt["best"]["kind"], "count_words")
        self.assertEqual(rt["path"], "semantic")

    def test_brain_route_semantic_null_degrades_loudly(self):
        """主路跑通但判"清单里没有" ⇒ 降级到能力启发式，且必须写明原因。"""
        from gbt_allinone import brain_exec, semantic_route
        fake = {"ok": True, "path": "semantic", "method": None,
                "reason": "清单里没有合适的", "provider": "stub"}
        with mock.patch.object(semantic_route, "route",
                               side_effect=lambda intent, mode="auto": dict(fake)):
            rt = brain_exec.route("统计一段文字的词数")
        self.assertTrue(rt["degraded"])
        self.assertEqual(rt["best"]["kind"], "count_words")
        self.assertIn("主路", rt["degraded_reason"])

    def test_mirror_release_calls_ascend_with_real_signature(self):
        """发布链路必须真能走通：`release()` 调 `ascend()` 的入参必须匹配真身签名。

        实测由来（R-H95 · 2026-09-19）：旧代码传了 `require_rehearsal` /
        `rehearsal_name` 两个关键字，而 `mirror_space.ascend(purpose)` 只收一个形参
        ⇒ `mirror_release` 每次必抛 TypeError，**生产发布这条路从未开过**
        （宪章第 18 条：一道从未开过的门，等于没有门）。

        2026-10-13：`ascend` 真身多了两个形参（`owner_override` / `override_reason`，放行口）。
        判据**不放空、改成对着真身签名判**：传过去的关键字必须**逐个都在真身份上**，
        位置参数仍须恰好一个 —— 旧病（传了真身不认的关键字）照样会被咬住。
        """
        from gbt_allinone import deployment_rehearsal as DR
        from gbt_allinone import mirror_space as MS
        seen = {}

        def fake_ascend(*args, **kwargs):
            seen["args"] = args
            seen["kwargs"] = kwargs
            return {"ok": True, "version": 1}

        with mock.patch.object(DR, "rehearse", return_value={"ok": True, "report_id": "r"}):
            with mock.patch.object(MS, "ascend", side_effect=fake_ascend):
                out = DR.release("default", "回归：发布链路契约")
        import inspect as _inspect
        _params = set(_inspect.signature(MS.ascend).parameters)
        _bad = [k for k in (seen.get("kwargs") or {}) if k not in _params]
        self.assertEqual(_bad, [],
                         "ascend 收到的关键字里有**真身不认**的形参：%s（真身形参 %s）"
                         % (_bad, sorted(_params)))
        self.assertEqual(len(seen.get("args") or ()), 1, "ascend 必须恰好收到一个位置参数（purpose）")
        self.assertTrue(out["ok"])

    def test_inventory_dual_view(self):
        r = _body(gbt.run_task("inventory", {}))
        self.assertTrue(r["result"]["ok"])
        dv = r["result"]["dual_view"]
        self.assertGreaterEqual(dv["框架管辖（framework）"], 3)      # README/requirements/gbt_allinone
        self.assertGreaterEqual(dv["环境托管（environment）"], 20)   # OpenClaw 工作区
        self.assertIn("异物（foreign）", dv)

    def test_signature_no_env_overreach(self):
        # 署名越权修复：环境页面（如 USER.md）不在签名扫描范围
        from gbt_allinone import signature as S
        from gbt_allinone.inventory import _classify
        env_leak = [p for p in S._scan_pages() if _classify(p) == "environment"]
        self.assertEqual(len(env_leak), 0)

    def test_screen_capture_identity_gate(self):
        """契约测试：非交互桌面上抓屏必须先被身份门拦下 —— 抛原因码、不试后端、不喷噪音。

        口径（2026-09-18 风哥拍「追踪根源修复」）：现象是 BitBlt 拒绝访问 + 每次调用一行
        「吞错」；根因是进程不在交互桌面（WinSta0\\Default），不是采集栈坏了。
        门的作用是把「身份不对」与「后端坏了」分开，并且一个原因码只播一次。
        """
        import io as _io_mod
        import contextlib as _ctx
        from gbt_allinone.tentacle import omni_core as _OC
        from gbt_allinone.tentacle import capture_environment as _CE

        _fake = {"interactive_desktop": False, "window_station": "WinSta0",
                 "desktop": "CodexSandboxDesktop-test", "reason": "non_interactive_desktop",
                 "checked_at": "test"}
        _old_cap = _CE.capacity
        _old_gate = dict(_OC._CAPTURE_GATE)
        _old_seen = set(_OC._CAPTURE_NOTICE_SEEN)
        try:
            _CE.capacity = lambda: dict(_fake)
            _OC._CAPTURE_GATE.update({"ts": 0.0, "data": None})
            _OC._CAPTURE_NOTICE_SEEN.clear()
            _err = _io_mod.StringIO()
            with _ctx.redirect_stderr(_err):
                with self.assertRaises(_OC.CaptureUnavailable) as _cm:
                    _OC._screen_capture()
            self.assertEqual(_cm.exception.reason_code, "non_interactive_desktop")
            self.assertIn("非交互桌面", str(_cm.exception))
            _out = _err.getvalue()
            self.assertIn("采集不可用[non_interactive_desktop]", _out)   # 不静默
            self.assertNotIn("吞错", _out)                               # 不再贴「吞错」标签
            self.assertNotIn("mss", _out)                                # 门拦下后不许再试后端
            _OC._CAPTURE_GATE.update({"ts": 0.0, "data": None})          # 复读机判据
            _err2 = _io_mod.StringIO()
            with _ctx.redirect_stderr(_err2):
                with self.assertRaises(_OC.CaptureUnavailable):
                    _OC._screen_capture()
            self.assertEqual(_err2.getvalue(), "")
        finally:
            _CE.capacity = _old_cap
            _OC._CAPTURE_GATE.clear()
            _OC._CAPTURE_GATE.update(_old_gate)
            _OC._CAPTURE_NOTICE_SEEN.clear()
            _OC._CAPTURE_NOTICE_SEEN.update(_old_seen)

    def test_cross_scan_clean(self):
        """除**已声明为 latent 的家根影子**外，不许有 findings。

        🔴 2026-09-22 修（错报治理）：原来断言 `findings == []`，而家根 `tools/`、`deploy/`
        与 `gbt_allinone/` 下同名子目录**是既有结构**（W 维如实报 `exposure=latent`）——
        这条断言因此**长期红**。而本仓自己的家规写着「**一条长期红的断言等于没有断言**」：
        长期红不只是噪音，它会训练人忽略红。
        真正的病（影子被**非限定引用** ⇒ 活的解析错位）由紧邻的
        `test_no_live_shadow_exposure` 单独守着 —— 那条才是判据。
        ⇒ 这里**放窄而不是放空**：只放行"W 维 + 已声明同名结构 + exposure=latent"三者同时成立的，
        其余（含任何 exposure≠latent 的影子）一条都不许有。
        """
        r = _body(gbt.run_task("cross_scan", {"deep": False}))
        self.assertTrue(r["result"]["ok"])
        ALLOWED_LATENT = ("家根影子子目录（与 gbt_allinone/ 同名）",)
        left = [f for f in r["result"]["findings"]
                if not (f.get("dim") == "W"
                        and any(k in f.get("issue", "") for k in ALLOWED_LATENT)
                        and "exposure=latent" in f.get("issue", ""))]
        self.assertEqual(left, [], "除已声明的 latent 影子外，findings 必须为空")

    def test_no_live_shadow_exposure(self):
        """影子**被非限定引用**才叫活的解析错位；只是名字撞了不算。

        为什么单独立这一条：`test_cross_scan_clean` 断言 findings 为空，
        但家根 `tools/`、`deploy/` 与 `gbt_allinone/` 下同名子目录是既有结构，
        于是那条测试**永远红**（2026-09-21 拿改代码之前的回执做过 A/B：
        `ok=False`、findings 逐字相同 ⇒ 不是后来改坏的）。长期挂红 = 噪声淹掉真问题。

        本条守的是真正要紧的不变量：**影子一旦被非限定导入变成 `live`，立刻炸出来**。
        `import tools` 在仓库根进了 sys.path 时会拿到根上那个，而不是
        `gbt_allinone.tools` —— 那才是会出事的时刻。
        """
        from gbt_allinone.tools.shadow_check import shadow_report
        rep = shadow_report()
        exp = rep.get("exposure")
        self.assertIn(exp, ("none", "latent", "live", "unknown"),
                      "exposure 取值越界: %r" % (exp,))
        self.assertNotEqual(
            exp, "live",
            "影子被非限定引用了（活错位）：%s —— %s" % (
                (rep.get("shadow_reachable") or {}).get("hits"),
                rep.get("exposure_note")),
        )

    def test_ghost_guard_nine_dims(self):
        # 旧病根四类复发的防退化：私有口径/杂交链/活跃区副本——造病必报，清病必净
        import shutil as _sh
        from pathlib import Path as _P
        base = _P(gbt.__file__).parent
        priv = base / "_private_caliber_test.py"
        priv.write_text('X = {' + '"a": {"domain": "x"}, ' * 6 + '}', encoding="utf-8")
        hyb = base / "store" / "devoured" / "a_x_b_test"
        hyb.mkdir(parents=True, exist_ok=True)
        cap_copy = base / "recon" / "capability.json"
        cap_copy.write_text('{}', encoding="utf-8")
        try:
            r = _body(gbt.run_task("ghost_guard", {}))
            kinds = {f["kind"] for f in r["result"]["findings"]}
            self.assertIn("private_registry", kinds)
            self.assertIn("hybrid_chain", kinds)
            self.assertIn("cap_copy", kinds)
        finally:
            priv.unlink(missing_ok=True)
            _sh.rmtree(hyb, ignore_errors=True)
            cap_copy.unlink(missing_ok=True)
        r2 = _body(gbt.run_task("ghost_guard", {}))
        self.assertTrue(r2["result"]["clean"])

    def test_root_fix_pit_and_prework(self):
        # 坑册防复发锁：登记幂等（同坑拒重）+ 查坑命中 + 开工查看有 verdict
        uid = f"测试坑-{int(time.time()*1000)}"
        r1 = _body(gbt.run_task("root_fix", {"op": "pit_record",
                                             "pit": uid, "root_cause": "测试", "lesson": "测试"}))
        r2 = _body(gbt.run_task("root_fix", {"op": "pit_record",
                                             "pit": uid, "root_cause": "测试", "lesson": "测试"}))
        self.assertTrue(r1["result"]["ok"])
        self.assertTrue(r2["result"].get("duplicate"), "同坑重复登记未被拒——幂等失效")
        hits = _body(gbt.run_task("root_fix", {"op": "pit_check", "keywords": uid}))
        self.assertGreaterEqual(hits["result"]["hits"], 1, "查坑未命中刚登记的坑")
        pw = _body(gbt.run_task("root_fix", {"op": "pre_work", "task": uid}))
        self.assertIn(pw["result"]["verdict"], ("GO——坑已避开、家底完好，可以动手",
                                                "BLOCK——先处理红灯再动手"))
        wl = _body(gbt.run_task("root_fix", {"op": "work_log", "action": "lesson",
                                             "title": "测试日志"}))
        self.assertTrue(wl["result"]["ok"])

    def test_selfscan_recovered_semantics(self):
        # 恢复语义锁：error 后同 kind 有 ok 证据 -> recovered（不是 runtime）
        r = _body(gbt.run_task("selfscan", {}))
        a = r["result"]["sections"]["audit"]
        sig = a["by_signal"]
        runtime_kinds = {k: v["runtime"] for k, v in a["errors_by_kind"].items() if v["runtime"]}
        # 任何 runtime kind 都必须在当前窗口内没有 ok 证据（否则恢复语义失效）
        from gbt_allinone.store import query_log
        ok_kinds = set()
        for x in query_log(limit=500):
            if x.get("event") == "ok":
                m = x.get("meta") or {}
                k = m.get("kind") or m.get("name")
                if isinstance(k, str):
                    ok_kinds.add(k)
        for kind in runtime_kinds:
            self.assertNotIn(kind, ok_kinds,
                             f"{kind} 有 ok 证据却仍判 runtime——恢复语义失效")
        self.assertIsInstance(sig["recovered"], int)

    def test_desktop_commander_brand(self):
        # 品牌注入：preload 存在 + remote 启动命令含 --require + preload 含 GBT 品牌
        from pathlib import Path
        from gbt_allinone.tentacle import desktop_commander as DC
        pre = Path(DC.__file__).resolve().parent / "dc_brand_preload.js"
        self.assertTrue(pre.exists(), "品牌注入 preload 缺失")
        joined = " ".join(DC._remote_cmd())
        self.assertIn("dc_brand_preload.js", joined, "remote 启动未注入品牌 preload")
        self.assertIn("--require", joined, "remote 启动缺 --require")
        self.assertIn("GBT", pre.read_text(encoding="utf-8"), "preload 未含 GBT 品牌")

    def test_desktop_commander_tentacle(self):
        # 桌面指挥官触手：能力已登记 + 默认 op 只读（探测安全）+ 工具归类覆盖主要工具
        from gbt_allinone.caps_registry import BENIGN_CAPS
        self.assertIn("desktop_commander", BENIGN_CAPS)
        r = _body(gbt.run_task("desktop_commander", {}))     # 默认 status：只读，不启动 remote
        res = r["result"]
        self.assertTrue(res.get("ok"))
        self.assertIn("connected", res)
        self.assertIn("remote_running", res)
        from gbt_allinone.tentacle import desktop_commander as DC
        names = []
        for g in DC.TOOL_GROUPS.values():
            names += g
        for must in ("read_file", "write_file", "start_process", "list_directory", "edit_block"):
            self.assertIn(must, names, f"工具归类缺 {must}")
        self.assertGreaterEqual(len(names), 24, "归类应覆盖绝大多数桌面指挥官工具")

    def test_observer_effect_quiet_probe(self):
        # 观察者效应锁：探活查询不落 svc_down（自放大循环防线）+ probe 标记最优先判定
        from gbt_allinone import services
        n0 = len([x for x in store.query_log(limit=800) if x.get("event") == "svc_down"])
        services.inspect(quiet=True)          # 纯探活：不应新增任何 svc_down
        n1 = len([x for x in store.query_log(limit=800) if x.get("event") == "svc_down"])
        self.assertEqual(n1, n0, "quiet 探活落了 svc_down——观察者自放大防线失效")
        services.inspect()                    # 主动体检：应落 svc_down（如实记录）
        n2 = len([x for x in store.query_log(limit=800) if x.get("event") == "svc_down"])
        self.assertGreater(n2, n1, "主动体检未落 svc_down——如实记录失效")
        # probe 标记最优先：带 probe 的 error 不算 runtime
        from gbt_allinone.store import audit
        audit("error", {"kind": "_probe_lock_test", "reason": "探针锁测试", "probe": True})
        r = _body(gbt.run_task("selfscan", {}))
        kinds = r["result"]["sections"]["audit"]["errors_by_kind"]
        self.assertEqual(kinds.get("_probe_lock_test", {}).get("runtime", 0), 0,
                         "probe 标记的 error 被判 runtime——probe 优先判定失效")

    def test_root_fix_debt_ceiling(self):
        # 补丁债上限锁：判例法<=2行 / 白名单<=3项（框架三件）/ 豁免<=2 —— 债不回升
        r = _body(gbt.run_task("root_fix", {"op": "patch_debt"}))
        d = r["result"]
        self.assertLessEqual(d["selfscan_判例行"], 2, f"判例法回升: {d['selfscan_判例行']}行")
        self.assertLessEqual(d["hygiene_白名单项"], 3, f"白名单回升: {d['hygiene_白名单项']}项")
        self.assertLessEqual(d["hygiene_豁免分支"], 3, f"豁免回升: {d['hygiene_豁免分支']}处")

    def test_user_error_source_classification(self):
        # 源头分类锁：用法错误必须是 user_error（不再混入 error 运行时故障）
        r = gbt.run_task("brain_route", {})
        self.assertEqual(r.get("error_class"), "user_error")
        from gbt_allinone.store import query_log
        rows = [x for x in query_log(limit=8, event="error")
                if (x.get("meta") or {}).get("kind") == "brain_route"]
        self.assertEqual(len(rows), 0, "brain_route 的用法错误仍记为 error——源头分类退化")

    def test_audit_backend_records(self):
        before = store.log_count()
        gbt.run_task("health")
        self.assertGreater(store.log_count(), before)


class TestRecordGrid(unittest.TestCase):
    """行式记录网格：注册/路由/成功/失败/自证五项（缺一不算完成）。"""

    SAMPLE = (
        "Alpha* http://a.example/x intro.list first comment\n"
        "Beta Works http://b.example/y learning,logic.edu second comment\n"
        "Gamma http://c.example/z nlp.org\n"
    )

    def test_registered_and_routed(self):
        from gbt_allinone.caps_registry import BENIGN_CAPS
        self.assertIn("record_grid", BENIGN_CAPS)
        names = [c["name"] for c in gbt.list_capabilities(filter_dangerous=True)]
        self.assertIn("record_grid", names)

    def test_parse_success_path(self):
        r = _body(gbt.run_task("record_grid", {"op": "parse", "text": self.SAMPLE}))
        result = r["result"]
        self.assertTrue(result["ok"], result.get("invalid"))
        self.assertEqual(result["stats"]["records"], 3)
        first = result["records"][0]
        self.assertEqual(first["title"], "Alpha")
        self.assertTrue(first["title_flag"])
        self.assertEqual(first["topics"], ["intro"])
        self.assertEqual(first["genre"], "list")
        self.assertEqual(first["comment"], "first comment")
        third = result["records"][2]
        self.assertFalse(third["title_flag"])
        self.assertEqual(third["comment"], "")

    def test_bad_line_reported_not_fatal(self):
        text = self.SAMPLE + "NoUrl here intro.list broken line\n"
        r = _body(gbt.run_task("record_grid", {"op": "parse", "text": text}))
        result = r["result"]
        self.assertFalse(result["ok"], "有坏行时 ok 必须为假（不粉饰）")
        self.assertEqual(result["stats"]["records"], 3, "坏行不得废掉整卷")
        self.assertEqual(len(result["invalid"]), 1)
        bad = result["invalid"][0]
        self.assertEqual(bad["line"], 4)
        self.assertTrue(bad["hints"], "坏行必须带可执行诊断提示")
        self.assertIn("code", bad)

    def test_roundtrip_is_idempotent(self):
        r = _body(gbt.run_task("record_grid", {"op": "verify", "text": self.SAMPLE}))
        result = r["result"]
        self.assertTrue(result["ok"], result.get("first_difference"))
        self.assertEqual(result["fingerprint"], result["reparsed"])

    def test_profile_and_draft(self):
        prof = _body(gbt.run_task("record_grid", {"op": "profile", "text": self.SAMPLE}))["result"]
        self.assertTrue(prof["ok"])
        self.assertIn("candidates", prof["profile"])
        self.assertIn("columns", prof["profile"])
        draft = _body(gbt.run_task("record_grid",
                                   {"op": "draft", "text": self.SAMPLE}))["result"]
        self.assertTrue(draft["ok"])
        self.assertTrue(draft["plan"]["fields"], "草案骨架不能为空")
        self.assertIn("warnings", draft["plan"])

    def test_unknown_op_is_honest_failure(self):
        r = _body(gbt.run_task("record_grid", {"op": "no_such_op", "text": self.SAMPLE},
                               safe=True))
        self.assertEqual(r["status"], "error")
        self.assertIn("未知 op", str(r.get("error")))

    def test_unknown_vocabulary_kept_not_dropped(self):
        text = "Alpha http://a.example/x intro,bogus.list c\n"
        r = _body(gbt.run_task("record_grid", {
            "op": "parse", "text": text,
            "plan": {"name": "t-vocab", "fields": [
                {"name": "title", "kind": "flex", "required": True, "marker": "*"},
                {"name": "url", "kind": "url", "required": True},
                {"name": "packed", "kind": "packed", "required": True,
                 "left": "topics", "right": "genre",
                 "left_vocab": ["intro", "nlp"], "right_vocab": ["list", "org"]},
                {"name": "comment", "kind": "tail"},
            ]}}))
        result = r["result"]
        self.assertTrue(result["ok"], "未知词不应升级成坏行")
        self.assertEqual(result["records"][0]["topics"], ["intro", "bogus"])
        self.assertTrue(any(f["code"] == "unknown_vocabulary" for f in result["findings"]))

    def test_decode_bytes_handles_bom_and_gbk(self):
        from gbt_allinone import record_grid as RG
        for payload in ("标题 http://a.example/x intro.org 备注".encode("utf-8-sig"),
                        "标题 http://a.example/x intro.org 备注".encode("gbk")):
            text, encoding, replaced = RG.decode_bytes(payload)
            self.assertIn("标题", text)
            self.assertEqual(replaced, 0, f"{encoding} 解码出现替换字符")
        self.assertEqual(RG.decode_bytes(b"abc")[1], "utf-8")

    def test_emit_writes_inside_store(self):
        r = _body(gbt.run_task("record_grid", {
            "op": "emit", "out": "t-grid.txt",
            "records": [{"title": "Alpha", "title_flag": True,
                         "url": "http://a.example/x", "topics": ["intro"],
                         "genre": "list", "comment": "c"}]}))
        result = r["result"]
        self.assertTrue(result["ok"])
        from gbt_allinone import _paths as _p  # O33：判据挂在语义上，不挂在目录名字上
        self.assertTrue(
            Path(result["written"]).resolve().is_relative_to(Path(_p.STORE_DIR)),
            "产物没落在隔离 store 里：%s" % result["written"])

        self.assertIn("Alpha*", result["text"])

    def test_emit_rejects_outside_store(self):
        r = _body(gbt.run_task("record_grid", {
            "op": "emit", "out": "../escape.txt", "records": [{"title": "x"}]}, safe=True))
        self.assertEqual(r["status"], "error")


def _ok_or_skip(case, body, what=""):
    """**分路径断言**（必读清单第 29 条）：被门拒 ⇒ 验拒绝信封齐全并**具名 skip**；
    否则才断言 `ok is True`。

    🔴 由来（第 8 轮实测）：`self.assertTrue(r["result"].get("ok"))` 在**未授权**环境下**必然红** ——
    拒绝信封按设计**不带 `ok`**（字段是 denied/reason/scopes/missing/how_to_grant/note），
    于是红字把"根本没被调用（未授权）"报成"某能力失败"。**那是错报**：
    它让人去修一个没坏的东西，还盖住了真正该看的 `how_to_grant`。
    """
    b = body if isinstance(body, dict) else {}
    mirrored = b.get("result")
    is_denial = b.get("denied") is True or (isinstance(mirrored, dict)
                                            and mirrored.get("denied") is True)
    if is_denial:
        env = b if b.get("denied") is True else mirrored
        miss = env.get("missing") or env.get("scopes") or []
        how = env.get("how_to_grant") or []
        # 拒绝也必须**可判**：缺哪个作用域、怎么放行，两样都得有（否则才是真问题）
        case.assertTrue(bool(miss), "拒绝信封必须写明缺哪个作用域%s" % (what and "（%s）" % what))
        case.assertTrue(bool(how), "拒绝信封必须给出 how_to_grant%s" % (what and "（%s）" % what))
        raise unittest.SkipTest("未授权（%s）：%s" % (",".join(miss),
                                                   (how or ["见 how_to_grant"])[0]))
    return b.get("ok") is True


def _skip_if_unconfigured(case, body, what=""):
    """**前提缺失**（未配 key / 缺依赖）⇒ 具名 skip；不许把"没配置"报成"运行失败"。

    判据：响应里出现**具名的未配置标记**（`未配置` / `尚未配置` / `needs_dependency`），
    且没有给出可用的 `ok is True`。

    🔴 边界（写死）：**不许**把"result 里没有 `ok` 键"当成"未配置" ——
    那只能说明信封不对，是另一回事（那才是真问题）。本助手只认**具名标记**。
    """
    blob = body if isinstance(body, str) else str(body)
    marks = [m for m in ("未配置", "尚未配置", "needs_dependency", "not configured") if m in blob]
    if marks and not (isinstance(body, dict) and body.get("ok") is True):
        raise unittest.SkipTest("前提缺失（%s）%s" % ("/".join(marks), what))
    return body


import pytest  # noqa: E402  （只为给下面那个类挂超时标记）


@pytest.mark.timeout(240)
class TestProductionStoreIsolation(unittest.TestCase):
    """测试期绝不许写生产 store（第一次实证：2026-09-17 `t-sched-run` 被写进生产 schedules.json）。

    ⏱️ 2026-09-22 加超时标记（**错报治理**）：本类用例要**起冷子进程 import 14 个模块**
    （见 `test_native_rc_import_writes_nothing_into_the_controlled_store`），
    内层 subprocess 预算写的是 **180s**，而 pytest 全局单测预算是 **30s** ⇒ **外层先杀**。
    后果：判决**取决于机器快慢/缓存冷热** —— 实测同一份代码 82.6s 能跑完（6 failed），
    也会 88–95s 被杀（TIMEOUT），而我上一轮差点把它当成"我改坏了"。
    **一个由负载决定、不由对错决定的红，就是错报。**
    给本类 240s（> 内层 180s）之后，超时与否才由被测代码决定。

    根因：`gbt_allinone` 包在 import 时就把 `_paths.STORE_DIR` 绑成常量；
    `python -m unittest discover` 先导入父包、再跑测试模块体 —— 测试再设环境变量已经来不及。
    兜底在 `gbt_allinone/tests/__init__.py`（导入即报错，宁可红不写生产）；本类是它的契约测试。
    """

    PROD_STORE = Path(_ROOT) / "gbt_allinone" / "store"

    def test_native_rc_import_writes_nothing_into_the_controlled_store(self):
        """R102 回归固化（风哥 2026-09-18 拍）：import native_rc 必须对受控 store 零写入。

        实测口径：新起子进程 + GBT_STORE_DIR 指向全新空目录 + import
        `gbt_allinone.tools.native_rc`，然后数那个目录 —— **0 文件 0 字节**才算过。
        绑定会发生（O53 已记，且实测拉进 14 个模块），但**不许写入**。
        """
        import os
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        iso = tempfile.mkdtemp(prefix="r102_native_rc_")
        env = dict(os.environ)
        env["GBT_STORE_DIR"] = iso
        code = ("import sys; sys.path.insert(0, sys.argv[1]); "
                "import gbt_allinone.tools.native_rc as m; "
                "assert hasattr(m, 'run_native'), 'run_native missing'")
        p = subprocess.run([sys.executable, "-c", code, str(root)], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[-400:])
        files = [q for q in Path(iso).rglob("*") if q.is_file()]
        total = sum(q.stat().st_size for q in files)
        self.assertEqual((len(files), total), (0, 0), "import 写进了受控 store")

    def test_test_package_guard_refuses_without_env(self):
        """反向用例（风哥 2026-09-18 拍）：没设 env 的进程里导入测试包，必须以守卫错误退出。

        守卫最怕被当「烦人」优化掉 —— 有这条红测试，它就动不了。
        """
        import os
        import subprocess
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env.pop("GBT_STORE_DIR", None)
        env["PYTHONUTF8"] = "1"
        p = subprocess.run([sys.executable, "-c", "import gbt_allinone.tests"],
                           cwd=str(root), env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        err = p.stderr.decode("utf-8", "replace")
        self.assertNotEqual(p.returncode, 0, "无 env 进程居然跑通了 —— 守卫失效")
        self.assertIn("RuntimeError", err)
        self.assertIn("STORE_DIR", err)

    def test_active_store_is_not_the_production_store(self):
        from gbt_allinone import store as _s
        self.assertNotEqual(
            Path(_s._STORE_DIR).resolve(), self.PROD_STORE.resolve(),
            "活跃 store == 生产 store：这一轮测试会把账与调度写进生产")

    def test_store_dir_binding_snapshot_blocks_env_drift(self):
        """O53 甲案（风哥 2026-09-18 拍）：绑定后改 env 必须 fail-fast，文件系统保持原样。

        臂 A（正对照）：先设 env 再 import，写必须落进隔离 store。
        臂 B（负对照）：import 后再改 env 成另一个目录触发写 —— 必须 RuntimeError，
        且【两个目录都保持原样】：新 env 目录仍为空，隔离 store 里那份一字未动。
        两臂必须不同 —— 否则本用例只是空壳。
        """
        import os
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        iso_a = tempfile.mkdtemp(prefix="r103_arm_a_")
        iso_b = tempfile.mkdtemp(prefix="r103_arm_b_")
        base_env = dict(os.environ)
        base_env["PYTHONUTF8"] = "1"
        arm_a = ("import sys; sys.path.insert(0, sys.argv[1]); "
                 "from gbt_allinone import store; "
                 "store.audit(sys.argv[2]); print(sys.argv[3])")
        p = subprocess.run([sys.executable, "-c", arm_a, str(root),
                            "r103_arm_a", "ARM_A_WROTE"],
                           cwd=str(root), env=dict(base_env, GBT_STORE_DIR=iso_a),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[-400:])
        self.assertIn("ARM_A_WROTE", p.stdout.decode("utf-8", "replace"))
        a_log = Path(iso_a) / "audit.jsonl"
        self.assertTrue(a_log.is_file(), "臂 A：写入没落进隔离 store")
        a_before = a_log.read_bytes()
        arm_b = ("import os, sys; sys.path.insert(0, sys.argv[1]); "
                 "from gbt_allinone import store; "
                 "os.environ[\"GBT_STORE_DIR\"] = sys.argv[3]; "
                 "store.audit(sys.argv[2]); print(sys.argv[4])")
        q = subprocess.run([sys.executable, "-c", arm_b, str(root), "r103_arm_b", iso_b,
                            "ARM_B_WROTE"],
                           cwd=str(root), env=dict(base_env, GBT_STORE_DIR=iso_a),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        b_err = q.stderr.decode("utf-8", "replace")
        self.assertNotEqual(q.returncode, 0, "绑定后改 env 居然写成功了 —— 快照失效")
        self.assertNotIn("ARM_B_WROTE", q.stdout.decode("utf-8", "replace"))
        self.assertIn("RuntimeError", b_err)
        self.assertIn("绑定路径", b_err)
        self.assertIn(Path(iso_a).name, b_err, "出错信息里没有「绑定时刻」的 env 值")
        self.assertIn(Path(iso_b).name, b_err, "出错信息里没有「当前」的 env 值")
        self.assertEqual(a_log.read_bytes(), a_before, "臂 B：隔离 store 被动了")
        b_left = [x for x in Path(iso_b).rglob("*") if x.is_file()]
        self.assertEqual(b_left, [], "臂 B：拒绝路径不该产生任何文件")

    def test_audit_contract_two_arms(self):
        """`store.audit()` 的**双臂契约**：落盘意外不抛（但要可见），门拒绝必抛。

        🔴 由来（第 34 轮）：`audit()` 上一版写成"**永不抛**"，把两种完全不同的失败
        混成一锅 —— 连 O53 甲案的门拒绝也被兜住，于是"绑定后改 env"这条安全契约
        **当场失效**（`test_store_dir_binding_snapshot_blocks_env_drift` 抓出来的）。
        而它之所以能悄悄溜进去，是因为**当时没有任何判据覆盖这两臂**（全仓 grep
        `audit_degraded` / `audit_failures` 在测试里 0 命中）。
        ⇒ 这里把契约钉成**方向相反的两臂**，谁再把它们混一锅，本用例立刻红。

        臂 ①落盘意外：把 `_LOG` 指到一个**目录**上（`open(..., "a")` 必 OSError）
                     ⇒ 必须**不抛**、返回记录、且 `audit_failures()` 计数 +1。
        臂 ②门拒绝：把 env 改成另一个路径（绑定时刻的 env 不同）
                     ⇒ 必须**抛 RuntimeError**，且计数**不增加**（拒绝≠降级，不许混算）。
        两臂方向相反 —— 否则本用例只是空壳。
        """
        import os
        from gbt_allinone import store as _s

        # ── 臂 ①：落盘意外 ⇒ 不抛，但必须可见 ──
        before = _s.audit_failures()
        real_log = _s._LOG
        trap_dir = _s._STORE_DIR / "_contract_arm_trap_dir"
        trap_dir.mkdir(parents=True, exist_ok=True)
        _s._LOG = trap_dir
        try:
            rec = _s.audit("r103_contract_arm_disk_fail",
                           {"probe": "臂①落盘意外"})
        finally:
            _s._LOG = real_log
        self.assertIsInstance(rec, dict, "臂①：落盘失败也必须返回一条记录（不许抛）")
        self.assertEqual(rec.get("event"), "r103_contract_arm_disk_fail")
        mid = _s.audit_failures()
        self.assertEqual(mid["count"], before["count"] + 1,
                         "臂①：落盘失败必须计数 —— 不计数就是沉默（账本可能缺行却没人知道）")
        self.assertGreaterEqual(mid["pending_in_memory"], 1,
                                "臂①：没落盘的记录必须留在内存缓冲里（不许凭空消失）")
        self.assertGreaterEqual(mid["reasons"].get("PermissionError", 0)
                                + mid["reasons"].get("IsADirectoryError", 0)
                                + mid["reasons"].get("OSError", 0), 1,
                                "臂①：失败原因必须记名，否则看板读不出为什么缺行")

        # ── 臂 ②：门拒绝 ⇒ 必抛，且不许算成"降级" ──
        real_env = os.environ.get("GBT_STORE_DIR")
        os.environ["GBT_STORE_DIR"] = str(_s._STORE_DIR) + "_drift_probe"
        try:
            with self.assertRaises(RuntimeError, msg="臂②：绑定漂移必须 fail-fast（不许被兜底）"):
                _s.audit("r103_contract_arm_gate_refusal")
        finally:
            if real_env is None:
                os.environ.pop("GBT_STORE_DIR", None)
            else:
                os.environ["GBT_STORE_DIR"] = real_env
        after = _s.audit_failures()
        self.assertEqual(after["count"], mid["count"],
                         "臂②：门拒绝**不是**落盘意外 —— 不许混算进降级计数")

        # 复原 env 后，正常写入必须照旧可用（证明臂②没有留下副作用）
        ok_rec = _s.audit("r103_contract_arm_recovered", {"probe": "复原后"})
        self.assertEqual(ok_rec.get("event"), "r103_contract_arm_recovered")
        self.assertNotIn("_audit_degraded", ok_rec.get("meta") or {},
                         "臂②：env 复原后不许再降级（否则整条审计口被污染）")
        try:
            trap_dir.rmdir()
        except OSError:
            pass

    def test_production_schedules_has_no_test_residue(self):
        """契约：生产 `schedules.json` 里不许残留任何测试命名空间的调度键。

        第一次实证（2026-09-15 写入 → 2026-09-17 清理）：两条 `t-preflight-sched-*`
        是当年的验收探针脚本在**未隔离 store** 的进程里写进生产的；此后它们每小时
        被 `sched_tick` 真跑一次（最近一次 09-17 17:41:53），在 `wf_runs/` 与
        `audit.jsonl` 里持续留痕。本断言把这条线钉死：残留再出现，回归当场红。
        """
        f = self.PROD_STORE / "schedules.json"
        if not f.exists():
            self.skipTest("生产没有 schedules.json")
        data = json.loads(f.read_text(encoding="utf-8")) or {}
        residue = [k for k in data
                   if k.startswith("t-preflight-sched-")
                   or k in ("t-sched-run", "t-bad-sched")]
        self.assertEqual(residue, [],
                         "生产 schedules.json 出现测试残留调度键：%s" % residue)

    def test_production_workflows_has_no_test_residue(self):
        """契约：生产 `workflows.json` 与 `wf_runs/` 里不许残留测试命名空间的产物。

        实证（2026-09-15 写入 → 2026-09-17 清 · O20）：`t-*` **20 条**工作流定义 +
        **492 个** run 文件，全部来自未隔离 store 的自测 / 探针验收。
        清账证据：`.scratch/_r53_o20_clean.json`。
        """
        wf = self.PROD_STORE / "workflows.json"
        if wf.exists():
            data = json.loads(wf.read_text(encoding="utf-8")) or {}
            residue = [k for k in data if k.startswith("t-")]
            self.assertEqual(residue, [],
                             "生产 workflows.json 出现测试残留定义：%s" % residue)
        runs = self.PROD_STORE / "wf_runs"
        if runs.exists():
            files = sorted(p.name for p in runs.iterdir()
                           if p.is_file() and p.name.startswith("t-"))
            self.assertEqual(files, [],
                             "生产 wf_runs/ 出现测试残留产物：%s" % files[:5])

    def test_production_schedules_has_no_test_entries(self):
        """契约：跑一段**真实调度动作**（就是当年写脏生产的那条路径）之后，
        生产 `schedules.json` 必须逐字节不变，而隔离 store 里必须有这条。

        正对照 = 隔离 store 里出现 `iso-sched`；负对照 = 生产文件零变化。
        两组缺一组就不算过（《扫描器自证律》）。
        """
        f = self.PROD_STORE / "schedules.json"
        if not f.exists():
            self.skipTest("生产没有 schedules.json")
        before = f.read_bytes()

        gbt.run_task("wf_define", {"name": "iso-wf", "nodes": [
            {"id": "a", "kind": "health", "params": {}}]})
        r = _body(gbt.run_task("sched_define", {
            "name": "iso-sched", "workflow": "iso-wf", "every_seconds": 60}))
        self.assertEqual(r["status"], "ok")
        _body(gbt.run_task("sched_tick", {}))

        after = f.read_bytes()
        self.assertEqual(before, after,
                         "测试把调度写进了生产 schedules.json")

        from gbt_allinone import _paths as _p
        iso = Path(_p.STORE_DIR) / "schedules.json"
        self.assertTrue(iso.exists(), "隔离 store 里连文件都没建 = 上面那条动作没生效")
        self.assertIn("iso-sched", json.loads(iso.read_text(encoding="utf-8")),
                      "动作真跑过：隔离 store 里必须看得到它")


    def test_production_pit_log_has_no_test_residue(self):
        """契约：生产 `pit_log.json` 里不许残留测试形态坑册条目。

        第一次实证（2026-09-11 起写入 → 2026-09-17 清 · O33）：`root_fix.py` 把 store 路径
        硬编码成 `_BASE / 'store'`，绕开 `_paths.STORE_DIR` —— 设 `GBT_STORE_DIR` 对它无效，
        跑一次回归就往生产写一条 `测试坑-<epoch_ms>`。清理证据：`.scratch/_r82_o33_clean_evidence.json`。

        判据用**严格三元组**（`pit` 以「测试坑-」开头 且 `root_cause == "测试"` 且 `lesson == "测试"`），
        **不许**用关键词匹配 —— 生产里有一条真实教训「测试把数据写进家根 store -> 家根被污染」，
        它带「测试」二字但必须留着（它是 O33 的证据链）。
        """
        f = self.PROD_STORE / "pit_log.json"
        if not f.exists():
            self.skipTest("生产没有 pit_log.json")
        pits = json.loads(f.read_text(encoding="utf-8")).get("pits", [])
        residue = [it.get("pit") for it in pits
                   if str(it.get("pit", "")).startswith("测试坑-")
                   and it.get("root_cause") == "测试" and it.get("lesson") == "测试"]
        self.assertEqual(residue, [],
                         "生产 pit_log.json 出现测试形态条目：%s" % residue[:3])

    def test_production_work_log_has_no_test_residue(self):
        """契约：生产 `work_log.jsonl` 里不许残留 `测试日志` / `atomic work log` 行。"""
        f = self.PROD_STORE / "work_log.jsonl"
        if not f.exists():
            self.skipTest("生产没有 work_log.jsonl")
        rows = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        residue = [r.get("title") for r in (json.loads(l) for l in rows)
                   if r.get("title") in ("测试日志", "atomic work log")]
        self.assertEqual(residue, [],
                         "生产 work_log.jsonl 出现测试日志行：%s" % residue[:3])

    def test_production_store_untouched_by_root_fix_and_auth_gate(self):
        """契约：跑一段真实动作（当年写脏生产的那两条路径）之后，生产三份文件逐字节不变。

        正对照 = 隔离 store 里出现新坑 / 新日志 / 授权文件；负对照 = 生产三份零变化。
        两组缺一组就不算过（《扫描器自证律》）。
        """
        from gbt_allinone import _paths as _p
        from gbt_allinone import auth_gate as _ag

        names = ("pit_log.json", "work_log.jsonl", "auth_grants.jsonl")

        def snap():
            out = {}
            for n in names:
                p = self.PROD_STORE / n
                out[n] = p.read_bytes() if p.exists() else None
            return out

        before = snap()
        uid = "测试坑-契约%d" % int(time.time() * 1000)
        _body(gbt.run_task("root_fix", {"op": "pit_record", "pit": uid,
                                        "root_cause": "测试", "lesson": "测试"}))
        _body(gbt.run_task("root_fix", {"op": "work_log", "action": "lesson",
                                        "title": "测试日志"}))
        # 授权门的写入路径（就是当年把生产 auth_grants.jsonl 创建出来的那一条）：
        # 这里只探**落点**，不真发授权。
        _ag._save_grants(_ag._load_grants())
        after = snap()
        for n in names:
            self.assertEqual(before[n], after[n],
                             "生产 %s 被测试改动了（隔离洞还在）" % n)

        iso = Path(_p.STORE_DIR)
        for n in names:
            self.assertTrue((iso / n).exists(),
                            "隔离 store 里没有 %s：上面那条动作没生效" % n)
        pits = json.loads((iso / "pit_log.json").read_text(encoding="utf-8"))["pits"]
        self.assertIn(uid, [it.get("pit") for it in pits],
                      "动作真跑过：隔离坑册里必须看得到它")


    # ── R86 · O35 扩展：store 硬编码家族的高危 5 条（写生产）契约 ──
    # 一律两档：正对照 = 隔离 store 里必须出现 / 负对照 = 生产逐字节不变。

    def test_mirror_space_dimension_writes_stay_isolated(self):
        """R86 · O35 扩展：mirror_space 曾硬编码 `_BASE / "store"`，GBT_STORE_DIR 对它无效。"""
        import hashlib
        from gbt_allinone import _paths as _p
        from gbt_allinone import mirror_space as MS

        def fp(root):
            if not root.exists():
                return {}
            return {f.relative_to(root).as_posix():
                    hashlib.sha256(f.read_bytes()).hexdigest()[:16]
                    for f in sorted(root.rglob("*")) if f.is_file()}

        prod_dim = self.PROD_STORE / "mirror_space" / "dimension"
        before = fp(prod_dim)
        r = MS.shape("r86-probe.txt", "契约探针（R86）\n", note="R86")
        self.assertTrue(r["ok"], "shape 没成功：%s" % r)
        self.assertEqual(fp(prod_dim), before, "生产 dimension 被测试写入（隔离洞还在）")
        iso = Path(_p.STORE_DIR) / "mirror_space" / "dimension" / "r86-probe.txt"
        self.assertTrue(iso.exists(), "隔离 dimension 没写进去 = 上面那条动作没生效")
        MS.unshape("r86-probe.txt")
        self.assertFalse(iso.exists(), "unshape 没删掉隔离探针")

    def test_qiankun_queue_writes_stay_isolated(self):
        """R86 · O35 扩展：qiankun 部署队列曾硬编码 `_BASE / "store" / deploy / queue.json`。"""
        from gbt_allinone import _paths as _p
        from gbt_allinone import qiankun as Q

        prod_q = self.PROD_STORE / "deploy" / "queue.json"
        before = prod_q.read_bytes() if prod_q.exists() else None
        Q._save_q({"next_id": 2, "items": [{"id": 1, "name": "r86-probe"}]})
        after = prod_q.read_bytes() if prod_q.exists() else None
        self.assertEqual(before, after, "生产 deploy/queue.json 被测试写入（隔离洞还在）")
        iso_q = Path(_p.STORE_DIR) / "deploy" / "queue.json"
        self.assertTrue(iso_q.exists(), "隔离队列文件没建 = 上面那条动作没生效")
        self.assertEqual(json.loads(iso_q.read_text(encoding="utf-8"))["items"][0]["name"],
                         "r86-probe", "动作真跑过：隔离队列里必须看得到它")

    def test_hygiene_data_move_lands_in_isolated_store(self):
        """R86 · O35 扩展：hygiene 归位落点曾硬编码 `_BASE / "store"`（铁律 5）。"""
        from unittest import mock
        from gbt_allinone import _paths as _p
        import gbt_allinone.hygiene as H

        tmp = Path(tempfile.mkdtemp(prefix="r86_hygiene_"))
        pkg = tmp / "pkg"
        home = tmp / "home"
        pkg.mkdir()
        home.mkdir()
        stray = pkg / "r86-stray.jsonl"
        stray.write_text('{"probe": 1}\n', encoding="utf-8")

        with mock.patch.object(H, "_BASE", pkg), mock.patch.object(H, "_HOME", home), \
                mock.patch.object(H, "PKG_DIRS", set()):
            H.scan(fix=True)

        self.assertFalse(stray.exists(), "原位置还在 = 没真归位")
        iso = Path(_p.STORE_DIR) / "r86-stray.jsonl"
        self.assertTrue(iso.exists(), "归位落点没进隔离 store = 上面那条动作没生效")
        self.assertFalse((self.PROD_STORE / "r86-stray.jsonl").exists(),
                         "归位落进了生产 store（隔离洞还在）")
        iso.unlink()

    def test_think_loop_reflection_writes_stay_isolated(self):
        """R86 · O35 扩展：think_loop 反思落盘曾硬编码 `.../store/polish_insights.json`。"""
        from gbt_allinone import _paths as _p
        from gbt_allinone import think_loop as TL

        prod_ins = self.PROD_STORE / "polish_insights.json"
        before = prod_ins.read_bytes() if prod_ins.exists() else None
        r = TL._step_reflect("R86 契约探针", [{"ok": True}])
        self.assertTrue(r.get("ok"), "反思落盘没成功：%s" % r)
        after = prod_ins.read_bytes() if prod_ins.exists() else None
        self.assertEqual(before, after, "生产 polish_insights.json 被测试写入（隔离洞还在）")
        iso = Path(_p.STORE_DIR) / "polish_insights.json"
        self.assertTrue(iso.exists(), "隔离里的 polish_insights.json 没建 = 上面那条动作没生效")

    def test_vision_bus_cache_and_stream_stay_isolated(self):
        """R86 · O35 扩展：vision_bus 曾硬编码 `_BASE.parent / "store"`（传输缓存 + 视觉流）。"""
        import base64 as _b64
        import io as _io
        from PIL import Image as _PILImage
        from gbt_allinone import _paths as _p
        from gbt_allinone.tentacle import vision_bus as VB

        iso_store = Path(_p.STORE_DIR).resolve()
        for name in ("_VISION_DIR", "_STREAM_FILE", "_CACHE_FILE"):
            got = Path(getattr(VB, name)).resolve()
            self.assertTrue(got.is_relative_to(iso_store),
                            "%s 没落在隔离 store 里：%s" % (name, got))
            self.assertFalse(got.is_relative_to(self.PROD_STORE.resolve()),
                             "%s 落在生产 store 里（隔离洞还在）：%s" % (name, got))

        buf = _io.BytesIO()
        _PILImage.new("RGB", (8, 8), (0, 0, 0)).save(buf, format="PNG")
        png = _b64.b64encode(buf.getvalue()).decode("ascii")

        class _FakeEye:
            def see(self, region=None):
                return {"ok": True, "image_base64": png, "size": [8, 8], "image_kb": 0.1}

            def _screen_capture(self, region=None, fmt=None, **kw):
                return self.see(region)

        prod_stream = self.PROD_STORE / "vision" / "r86-probe.json"
        before = prod_stream.read_bytes() if prod_stream.exists() else None
        r = VB.stream_record(_FakeEye(), duration_s=0.05, interval_ms=10,
                             stream_name="r86-probe")
        self.assertTrue(r["ok"], "视觉流记录没成功：%s" % r)
        after = prod_stream.read_bytes() if prod_stream.exists() else None
        self.assertEqual(before, after, "生产 vision/ 被测试写入（隔离洞还在）")
        iso_stream = Path(_p.STORE_DIR) / "vision" / "r86-probe.json"
        self.assertTrue(iso_stream.exists(), "隔离 vision/ 里没有流文件 = 上面那条动作没生效")
        iso_stream.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)




