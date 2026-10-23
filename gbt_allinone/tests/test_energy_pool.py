# -*- coding: utf-8 -*-
"""能源池 · 带牙用例（R-H223）。

① 五条红线都在，且各自有机械闸；
② 红线①：**模型是燃料，不是身份**（owner_ai_id 填模型名 ⇒ 拒）；
③ 红线②：能源可换、**原生栈不动**（指纹漂移 ⇒ 拒）；
④ 红线③：**衍生代码必须走原生路由**（SDK 直连 / 自己拼请求 ⇒ 拒）；
⑤ 红线④⑤：按需分配 + **没有能源如实报缺**（不硬撑）；
⑥ 取证如实：能源数从盘上动态读；**免费/付费盘上判不出 ⇒ 标 unknown**（不编）；
⑦ 只读骨架里不许有网络 / 写盘 / 发密钥路径；登记在册且**落地即接线**。
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import energy_pool as ep  # noqa: E402
from gbt_allinone.tools import orchestration_kernel as ok  # noqa: E402
from gbt_allinone import caps_registry as CR  # noqa: E402


def key_on_disk(key_ref) -> "Path":
    """把 `key_ref`（如 `store/secrets/agnes_api.dpapi`）还原成**绝对路径**。

    🔴 2026-09-22 第 35 轮加（**为了不再犯我自己刚犯的那个错**）：
    我第一版写成 `ep._secrets_dir().parent / key_ref`，自以为 `.parent` 是包根，
    实际 `_secrets_dir()` 已经是 `gbt_allinone/store/secrets` ⇒ `.parent` 是
    `gbt_allinone/store`，拼出来的是 **`store/store/secrets/…`**（多一层），
    于是"文件明明在盘上"被判成不在 ⇒ **我自己造了一条假红**（本会话第 5 次装置错）。
    救命的是我把**实际路径打进了失败信息**，一眼看出多了一层。

    ⇒ 正确做法：`key_ref` 的前缀就是模块自己的 `SECRETS_DIR` 常量，**按它剥掉再接绝对根**，
    两边同源，不会各算各的。
    """
    rel = str(key_ref or "")
    prefix = ep.SECRETS_DIR.rstrip("/") + "/"
    if rel.startswith(prefix):
        rel = rel[len(prefix):]
    return ep._secrets_dir() / rel


class RedLineTests(unittest.TestCase):
    def test_five_redlines_each_have_a_gate(self):
        r = ep.run("redlines")
        self.assertEqual(len(r["red_lines"]), 5)
        for s in ("燃料", "身份", "原生栈", "原生路由", "按需", "如实报缺"):
            self.assertTrue(any(s in x for x in r["red_lines"]),
                            "五条红线里少了：%s" % s)
        self.assertEqual(len(r["side_rules"]), 3, "附带三条也要在")

    def test_model_is_not_identity(self):
        self.assertEqual(ep.check_identity_not_model("")["rule"],
                         "missing_owner_ai_id")
        bad = ep.check_identity_not_model("deepseek")
        self.assertEqual(bad["rule"], "model_is_not_identity",
                         "模型是燃料，不是身份 —— owner_ai_id 不能填模型名")
        self.assertEqual(ep.check_identity_not_model("agnes")["rule"],
                         "model_is_not_identity")
        self.assertTrue(ep.check_identity_not_model("ai-video-1")["ok"])

    def test_stack_must_not_drift(self):
        self.assertEqual(ep.check_stack_unchanged()["rule"],
                         "missing_stack_fingerprint")
        self.assertEqual(ep.check_stack_unchanged("abc", "xyz")["rule"],
                         "stack_drift", "换能源不许把原生栈也换了")
        self.assertTrue(ep.check_stack_unchanged("abc", "abc")["ok"])

    def test_derived_code_must_use_native_route(self):
        self.assertEqual(ep.check_derived_code("")["rule"],
                         "empty_derived_code", "未测不按绿")
        bad = ep.check_derived_code("import openai\nclient = openai.Client()")
        self.assertEqual(bad["rule"], "derived_bypasses_route")
        bad2 = ep.check_derived_code("requests.post('https://api.x/v1/gen')")
        self.assertEqual(bad2["rule"], "derived_bypasses_route")
        good = ep.check_derived_code(
            "from gbt_allinone import api\napi.run_task('llm_chat', {})\n")
        self.assertTrue(good["ok"], "走原生路由的衍生代码要放行")

    def test_no_energy_is_reported_honestly(self):
        self.assertEqual(ep.lease_energy("")["rule"], "missing_owner_ai_id")
        out = ep.lease_energy("ai-not-configured-xyz")
        self.assertFalse(out["ok"])
        self.assertTrue(out.get("honest"), "**没有能源 ⇒ 如实报缺**，不硬撑")
        self.assertEqual(out["rule"], "no_key_for_owner")


class ForensicsAndSkeletonTests(unittest.TestCase):
    def test_energies_are_read_from_disk_not_hardcoded(self):
        st = ep.run("status")
        self.assertEqual(st["count"], len(st["energies"]))
        names = [x["name"] for x in st["energies"]]
        self.assertIn("deepseek", names)
        self.assertIn("agnes", names)
        for x in st["energies"]:
            self.assertEqual(x["tier"], "unknown",
                             "免费/付费盘上判不出 ⇒ 一律 unknown，不许编")
        self.assertEqual(st["tier_known"], [])

    def test_dpapi_missing_is_reported(self):
        """`dpapi_on_disk` / `dpapi_missing` 必须**与盘上事实一致**（不许写死某一项）。

        🔴 2026-09-22 第 35 轮重写（错报治理）。原来这里写死：
        `assertIn("agnes", st["dpapi_missing"], "agnes_api.dpapi 不在盘上 ⇒ 必须如实报缺")`。
        实测（本轮）：`gbt_allinone/store/secrets/agnes_api.dpapi` **在盘上（314 字节）**
        ⇒ 代码报 `可用` 是**对的**，是这条判据的**前提过期了**（主人后来补了钥匙）。
        它的真意是"缺了就如实报缺"，不是"agnes 必须缺"。

        ⇒ 改成**当下实测的不变量**：报"在盘"的必须真在盘、报"缺"的必须真不在盘，
        两栏还必须互斥且覆盖全部能源。这样它既守得住原意，
        又不会因为主人补/撤一把钥匙而翻红 —— **判据不许把某一刻的盘上事实写死。**
        """
        st = ep.run("status")
        items = {x["name"]: x for x in st["energies"]}
        on = set(st["dpapi_on_disk"])
        missing = set(st["dpapi_missing"])

        self.assertEqual(on & missing, set(), "同一项不能既算在盘又算缺：%s" % (on & missing))
        self.assertEqual(on | missing, set(items),
                         "两栏必须覆盖全部能源（有项没被算进任何一栏 = 读数漏项）")
        self.assertTrue(on, "一个 .dpapi 都不在盘 ⇒ 这一栏没得判，是空话")
        for name in on:
            f = key_on_disk(items[name]["key_ref"])
            self.assertTrue(f.is_file(), "报了『在盘』却查不到文件：%s" % f)
        for name in missing:
            f = key_on_disk(items[name]["key_ref"])
            self.assertFalse(f.is_file(), "报了『缺 key』却其实在盘：%s" % f)

    def test_module_has_no_network_or_write_paths(self):
        src = Path(ep.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket",
                    "import subprocess", ".write_text(", ".write_bytes(",
                    "unlink("):
            self.assertNotIn(bad, src, "只读骨架里不该出现：%s" % bad)


class WiringTests(unittest.TestCase):
    def test_registered_and_wired(self):
        cap = CR.BENIGN_CAPS.get("energy_pool")
        self.assertIsNotNone(cap)
        self.assertEqual(cap["handler"], "energy_pool")
        self.assertIn("energy_pool", ok._READONLY_MODULES)
        self.assertIs(ok._READONLY_MODULES["energy_pool"], ep)


class AbstractionAndDeriverTests(unittest.TestCase):
    """R-H224 · 能源抽象层 + 原生能力衍生器（**自己生成的代码要过自己的红线**）。"""

    def test_energy_source_has_the_seven_fields(self):
        from dataclasses import fields
        got = {f.name for f in fields(ep.EnergySource)}
        self.assertEqual(got, {"source_id", "grade", "kind", "endpoint",
                               "key_ref", "capability", "status"})
        src = ep.EnergySource(source_id="x")
        self.assertEqual(src.grade, "未知", "盘上无该字段 ⇒ 默认未知，不编")
        self.assertEqual(src.kind, "未知", "荤素只是比喻，不参与判据")
        self.assertIn(src.status, ep.STATUSES)

    def test_sources_built_from_disk(self):
        """每个能源的 status 必须**与它自己那把 .dpapi 在不在盘上一致**。

        🔴 2026-09-22 第 35 轮重写（错报治理）：原来写死
        `by["agnes"]["status"] == "缺key"`（附言"agnes_api.dpapi 不在盘上"）与
        `by["deepseek"]["status"] == "可用"`。实测 agnes 的 .dpapi **在盘上** ⇒ 前提过期。
        真正要守的不变量是**一致性**：`status == "可用"` ⟺ `key_ref` 指向的文件真在盘上。
        """
        r = ep.run("sources")
        self.assertGreater(r["count"], 0, "一个能源都没有 ⇒ 这一栏是空话")
        by = {s["source_id"]: s for s in r["sources"]}
        for sid, s in by.items():
            f = key_on_disk(s["key_ref"])
            on_disk = bool(s["key_ref"]) and f.is_file()
            expect = "可用" if on_disk else "缺key"
            self.assertEqual(s["status"], expect,
                             "%s 的 status 与盘上事实不符（key_ref=%s ⇒ %s 在盘=%s）"
                             % (sid, s["key_ref"], f, on_disk))
        self.assertTrue(all(s["grade"] == "未知" for s in r["sources"]))
        # 判据卡在真问题上：key_ref 必须是 **DPAPI 引用**，且**不含密钥形状**
        # （上一版我拿 "secret" 做子串判据 ⇒ 被路径 `store/secrets/` 误伤，属判据扩大化）
        for s in r["sources"]:
            self.assertTrue(s["key_ref"].endswith(".dpapi"),
                            "key_ref 必须是 DPAPI 引用：%s" % s["key_ref"])
            self.assertIsNone(
                re.search(r"\b(?:sk|ak|lt)[-_][A-Za-z0-9_\-]{16,}\b", s["key_ref"]),
                "key_ref 里不许出现密钥形状")

    def test_status_mapping_under_a_controlled_disk(self):
        """盘 → status 的映射必须在**受控盘态**下验证（当前盘态 7 把钥匙全在 ⇒ 测不出谎报）。

        🔴 2026-09-22 第 35 轮加，**因为变异测试逼出来的**：把
        `status="可用" if has_key else "缺key"` 变异成 `status="可用"`（永远谎报可用）后，
        上面那条"与盘上一致"的判据 **照样全绿** —— 因为 7 个 `.dpapi` 现在都在盘上，
        "一直说可用"与事实**恰好一致**。
        ⇒ 没有"缺 key 的能源"时，那条不变量是**空的**。
        这里把扫描根换成只放一把钥匙的**受控临时目录**，谎报立刻现形。
        （实测：变异成永远"可用" ⇒ 本用例红；恢复 ⇒ 绿。）
        """
        import tempfile
        prof = ep._profiles()
        self.assertGreaterEqual(len(prof), 2,
                                "至少要有两个能源才判得出『缺』（现在只有 %d 个）" % len(prof))
        first = sorted(prof)[0]
        with tempfile.TemporaryDirectory() as td:
            sdir = Path(td)
            (sdir / str(prof[first]["file"])).write_bytes(b"probe")   # 只放这一把
            real = ep._secrets_dir
            ep._secrets_dir = lambda: sdir
            try:
                srcs = {s.source_id: s for s in ep.build_sources()}
            finally:
                ep._secrets_dir = real
        self.assertEqual(srcs[first].status, "可用", "受控盘上放了钥匙的必须报可用")
        for k in sorted(srcs):
            if k == first:
                continue
            self.assertEqual(srcs[k].status, "缺key",
                             "%s 的钥匙不在受控盘上 ⇒ 必须报『缺key』"
                             "（一律报可用 = 谎报，这条就是抓它的）" % k)

    def test_derived_code_passes_our_own_redline(self):
        """🔴 自洽带牙：**衍生器生成的代码，必须能过红线③自己的闸**。"""
        r = ep.run("derive_code", source_id="deepseek")
        self.assertTrue(r["self_check"]["ok"],
                        "自己生成的代码没过自己的闸：%s" % r["self_check"])
        self.assertIn("run_task", r["code"], "必须走原生路由")
        self.assertNotIn("import requests", r["code"])
        self.assertNotIn("openai", r["code"])

    def test_missing_energy_derives_nothing(self):
        """缺 key 的能源 ⇒ **不生成调用代码、如实报缺**（用**受控输入**测，不赌盘上缺谁）。

        🔴 2026-09-22 第 35 轮重写（错报治理）：原来写死 `source_id="agnes"` 并假定它缺 key。
        实测 agnes 的 .dpapi **在盘上** ⇒ 衍生器**正确地**为它生成了调用代码，
        而判据却喊"该报缺" —— 一个"缺 key"判据拿一个不缺 key 的能源去测，
        测的就不是它声称的那件事。
        ⇒ 主判据改成**受控合成输入**（一条 `status="缺key"` 的能源）：
        这条分支**永远可测**，不随盘上钥匙增减而失效；端到端那条真缺才跑。
        """
        # ① 不变量（受控输入 ⇒ 永远可测）：status 为缺 key ⇒ 必须拒绝生成、且给可执行的失败
        synth = ep.EnergySource(source_id="合成-缺key", key_ref="store/secrets/nope.dpapi",
                                status="缺key")
        code = ep.NativeDeriver().derive_client_code(synth)
        self.assertIn("不生成调用代码", code, "缺 key 的能源 ⇒ 不生成代码，如实报缺")
        self.assertIn("raise RuntimeError", code)
        # ② 不存在的能源：必须报 unknown_source（不猜、不编）
        self.assertEqual(ep.run("derive_code", source_id="不存在")["rule"],
                         "unknown_source", "不存在的能源必须报 unknown_source")
        # ③ 端到端（盘上真缺才跑；都有 key 就具名 skip —— 不把"没测"说成"通过"）
        missing = list(ep.run("status")["dpapi_missing"])
        if not missing:
            self.skipTest("盘上所有能源都有 key ⇒ **端到端**这条今天无从验证"
                          "（受控输入那条上面已验过；撤掉一把 .dpapi 即可连端到端一起真验）")
        r = ep.run("derive_code", source_id=missing[0])
        self.assertIn("不生成调用代码", r["code"],
                      "缺 key 的能源（%s）⇒ 不生成调用代码" % missing[0])

    def test_video_pipeline_by_capability(self):
        t2v = ep.run("derive_pipeline", capability="文生视频")
        self.assertTrue(t2v["ok"])
        self.assertIn("提示词", t2v["steps"][0])
        i2v = ep.run("derive_pipeline", capability="image")
        self.assertIn("上传参考图(OSS)", i2v["steps"][0])
        ext = ep.run("derive_pipeline", capability="video")
        self.assertIn("上传已有视频(OSS)", ext["steps"][0])
        self.assertEqual(ep.run("derive_pipeline", capability="魔法")["rule"],
                         "unknown_capability", "不硬凑蓝图")


class PoolAndSelfDevTests(unittest.TestCase):
    """R-H225 · 能源池（**不挑食但有优先级**）+ 视频自研八层图。"""

    def test_pool_registers_and_picks_free_first(self):
        pool = ep.EnergyPool()
        pool.register(ep.EnergySource(source_id="paid-1", grade="付费",
                                      capability=("text",), status="可用",
                                      key_ref="store/secrets/a.dpapi"))
        pool.register(ep.EnergySource(source_id="free-1", grade="免费",
                                      capability=("text",), status="可用",
                                      key_ref="store/secrets/b.dpapi"))
        got = pool.pick("text", prefer="免费")
        self.assertEqual(got.source_id, "free-1",
                         "**免费优先**（荤素之别，不是好坏之别）")
        got2 = pool.pick("text", prefer="付费")
        self.assertEqual(got2.source_id, "paid-1", "偏好可换 ⇒ 说明只是偏好")

    def test_pool_does_not_pick_unavailable_or_unmatched(self):
        pool = ep.EnergyPool()
        pool.register(ep.EnergySource(source_id="nokey", capability=("text",),
                                      status="缺key"))
        self.assertIsNone(pool.pick("text"),
                          "**没有可用能源 ⇒ 如实返回 None**（不硬撑）")
        pool.register(ep.EnergySource(source_id="vid", capability=("video",),
                                      status="可用", key_ref="store/secrets/c.dpapi"))
        self.assertIsNone(pool.pick("text"), "能力不匹配不挑")
        self.assertEqual(pool.pick("video").source_id, "vid", "不挑食：能跑就行")

    def test_pool_refuses_plaintext_key_ref(self):
        pool = ep.EnergyPool()
        bad = pool.register(ep.EnergySource(source_id="x", key_ref="sk-plain-key-123456"))
        self.assertEqual(bad["rule"], "key_must_be_dpapi")

    def test_pool_loads_from_disk(self):
        """挑能源：**挑中的必须是当下真可用的**，且注册表要覆盖盘上全部能源。

        🔴 2026-09-22 第 35 轮重写（错报治理）：原来写死
        `picked["source_id"] == "deepseek"`（附言"agnes 缺key ⇒ 只有 deepseek 可用"）。
        实测 agnes 的 .dpapi **在盘上**，两个都可用，池子按优先级挑了 agnes ⇒ 判据翻红。
        「挑中谁」取决于盘上有几把钥匙 —— 那是**会变的**，不该进判据；
        该进判据的是**不变量**：挑中的必须可用、必须属于注册表、没可用时必须如实返回 None。
        """
        r = ep.run("pool", capability="text")
        srcs = {s["source_id"]: s for s in ep.run("sources")["sources"]}
        self.assertEqual(sorted(r["registered"]), sorted(srcs),
                         "注册表必须覆盖盘上全部能源（漏一个 = 读数不全）")
        picked = r["picked"]
        self.assertIsNotNone(picked, "有可用能源却挑不出来 ⇒ 挑能源这条链断了")
        self.assertIn(picked["source_id"], srcs)
        self.assertEqual(srcs[picked["source_id"]]["status"], "可用",
                         "挑中了一个**不可用**的能源：%s" % picked["source_id"])

    def test_self_dev_eight_layers_vs_six_step_pipeline(self):
        s = ep.run("self_dev_layers")
        self.assertEqual(s["count"], 8)
        names = [x["layer"] for x in s["layers"]]
        self.assertEqual(names[0], "脚本/分镜")
        self.assertEqual(names[-1], "原生剪辑 + 品牌片尾")
        native = [n for n in names if "原生" in n]
        self.assertEqual(len(native), 4,
                         "四层带『原生』⇒ 这份讲的是**自研边界**")
        self.assertEqual(len(s["vs_pipeline"]), 3, "三处差异都要照报")
        self.assertIn("并存", s["note"], "两个维度并不同，不许合并")
        self.assertEqual(
            [x["module"] for x in s["layers"] if x["module"]],
            ["caps_registry", "orchestration_kernel", "render_evolution",
             "render_evolution", "brand_outro"])


class NativeStackFourTests(unittest.TestCase):
    """R-H226 · 「原生栈」= 触手/记忆/门禁/审计 —— 换模型时**逐项**验，不看总指纹。"""

    def test_five_redlines_all_have_gates(self):
        r = ep.run("native_stack")
        self.assertEqual(len(r["redlines"]), 5)
        for x in r["redlines"]:
            self.assertTrue(str(x["gate"]).strip(), "%s 没写闸" % x["cn"])

    def test_native_stack_is_the_four_named_things(self):
        ns = ep.run("native_stack")["native_stack"]
        self.assertEqual([x["cn"] for x in ns], ["触手", "记忆", "门禁", "审计"])

    def test_four_items_checked_individually_not_by_total_fingerprint(self):
        """🔴 关键：总指纹一样，也可能"触手换了、审计没换"互相抵消。"""
        before = {"tentacle": "A", "memory": "B", "gate": "C", "audit": "D"}
        after_same = dict(before)
        self.assertTrue(ep.check_stack_four(before, after_same)["ok"])
        # 只有"触手"变了 ⇒ 逐项查验必须抓到（总指纹可能因别的抵消而看不出）
        after_one = dict(before, tentacle="X")
        out = ep.check_stack_four(before, after_one)
        self.assertEqual(out["rule"], "native_stack_changed")
        self.assertEqual(out["changed"], ["触手"])
        self.assertEqual(ep.check_stack_four({}, {})["rule"],
                         "missing_stack_snapshot")

    def test_all_four_are_guarded(self):
        before = {"tentacle": "A", "memory": "B", "gate": "C", "audit": "D"}
        for k, cn in (("tentacle", "触手"), ("memory", "记忆"),
                      ("gate", "门禁"), ("audit", "审计")):
            out = ep.check_stack_four(before, dict(before, **{k: "changed"}))
            self.assertEqual(out["rule"], "native_stack_changed",
                             "%s 变了必须抓到" % cn)
            self.assertIn(cn, out["changed"])


if __name__ == "__main__":
    unittest.main()
