"""原生能力成长栈判据（主人令 2026-09-27）。

一条令里五件事，逐件立判据（**都可判定，且都写了红了怎么办**）：

  A. **Obsidian 永久记忆**：每根触手一本独立库 · 双向绑定两条腿都在盘上 · 共享页两侧同 sha；
  B. **GBT 专属标签 + 主人许可**：标签齐且不撞车 · 分类非空 · **AI 发不出许可**（非 TTY 直接拒）
     · 本模块**没有任何写许可文件的代码路径**（自己查自己的源码）；
  C. **先看→动脑→执行**：无证据拒 · 证据不在盘上拒 · 拿旧读数拒 · 没写预期拒 · 齐活才发闸号
     · `close` 不许空"看到"；
  D. **短板钩子 + 自主进化钩子**：短板每条带 `src` · 撞 `holdout` 封存集的步骤**必须被拦**；
  E. **吞天 × 原生融合**：三件不齐**不许写"已融合"**（假账当场拒）· 台账说的与盘上算的对得上；
  F. **硬性规则钩子**：已登记能力位六条腿全绿 · **没登记的不许硬造**（钩子不替人登记）· 台账有行；
  G. **一体**：五个新能力位都能过 `run_task` 调到（三处齐的实证）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / "gbt_allinone" / "tools"
NEW_CAPS = ["obsidian_vault", "cap_tags", "action_gate", "growth_hooks", "devour_fusion"]


def _load(name: str, path: Path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


class TestObsidianVault(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load("ov_t", T / "obsidian_vault.py")

    def test_a_every_tentacle_has_its_own_vault_and_two_way_links(self):
        v = self.m.verify()
        self.assertTrue(v.get("ok"), f"永久记忆层没立住：{v.get('problems')}")
        self.assertGreaterEqual(v["counts"]["vaults"], 200, "触手库太少 ⇒ 有触手没库")
        self.assertEqual(v["counts"]["tentacles"], v["counts"]["vaults"], "库数与触手数不等")

    def test_b_shared_page_lands_on_both_sides_with_same_sha(self):
        """共享页：触手库与本体库各一份，sha 必须相同（内容级互通）。

        **判据自己不许往真库里写**：全程在临时目录里做（血账：这条早先往本体库写了一张
        `自检页.md`，把主人的记忆库当成了试验田）。真闸单独验：根在**仓外**时必须过门。
        """
        with tempfile.TemporaryDirectory() as td:
            body = Path(td) / "body"
            root = Path(td) / "vaults"
            outside = Path(td) / "outside"
            (root / "lobehub").mkdir(parents=True)
            (outside / "lobehub").mkdir(parents=True)
            old_body, old_root, old_gate = self.m._body_vault, self.m._root_of, self.m._gate
            try:
                # ① 真闸：根在仓外（不是框架自己那片）⇒ 必须过门，没票就拒
                self.m._root_of = lambda: outside
                denied = self.m.sync_page(name="自检页", text="x", tentacles="lobehub")
                self.assertTrue(denied.get("denied"), f"写到仓外竟然没关门：{denied}")
                # ② 过了门（模拟主人开窗）才写，且只写在临时目录里
                self.m._body_vault = lambda: body
                self.m._root_of = lambda: root
                self.m._gate = lambda *a, **k: None
                r = self.m.sync_page(name="自检页", text="# 自检\n两侧应同 sha\n", tentacles="lobehub")
                self.assertTrue(r.get("ok"), f"两侧没写上：{r}")
                self.assertTrue(r.get("sha"), "没算出 sha")
                self.assertTrue(all(v["sha"] == r["sha"] for v in r["sides"].values()),
                                f"两侧 sha 不一致：{r['sides']}")
                for side in r["sides"].values():
                    self.assertIn(td, side["path"], "共享页写到临时目录之外去了")
            finally:
                self.m._body_vault, self.m._root_of, self.m._gate = old_body, old_root, old_gate


class TestCapTags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load("ct_t", T / "cap_tags.py")

    def test_a_tags_cover_every_cap_and_do_not_collide(self):
        r = self.m.tags()
        self.assertGreaterEqual(r["count"], 200, "标签数太少")
        self.assertEqual({}, r["duplicate_tags"], f"标签撞车：{r['duplicate_tags']}")
        self.assertTrue(self.m.verify().get("ok"), f"verify 红：{self.m.verify().get('problems')}")

    def test_b_two_classes_both_present(self):
        r = self.m.tags()
        self.assertGreater(r["by_permission"].get("open", 0), 0, "一个读类都没有 ⇒ 分类坏了")
        self.assertGreater(r["by_permission"].get("owner", 0), 0, "一个 owner 类都没有 ⇒ 默认不够严")

    def test_c_ai_cannot_issue_permits(self):
        r = self.m.permit(tag="GBT-SYSTEM-CAP-TAGS", ttl=60)
        self.assertFalse(r.get("ok"), f"**非交互会话竟然发出了许可**：{r}")
        self.assertTrue(r.get("denied") or r.get("error"), "拒了要说清为什么")

    def test_d_no_write_path_to_permit_file(self):
        src = Path(T / "cap_tags.py").read_text(encoding="utf-8")
        self.assertNotIn("_PERMITS.write", src, "出现写许可文件的路径 ⇒ AI 可自批")
        self.assertIn("isatty", src, "许可命令必须要求 TTY（非交互会话发不出）")

    def test_e_owner_class_cap_is_denied_without_permit(self):
        doc = json.loads((ROOT / "state" / "cap_tags.json").read_text(encoding="utf-8"))
        owner = [k for k, v in doc["tags"].items() if v["permission"] == "owner"]
        self.assertTrue(owner, "没有 owner 类 ⇒ 这条判据没验到东西")
        c = self.m.check(kind=owner[0])
        if c["allowed"] is True:
            self.assertGreater(c["permits_live"], 0, "没许可却说能调 ⇒ 许可门漏了")
        else:
            self.assertTrue("permit --tag" in (c.get("how_to_permit") or ""), "拒了要给准确授权命令")


class TestActionGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load("ag_t", T / "action_gate.py")

    def test_a_blind_op_is_refused(self):
        r = self.m.preflight(action="删掉某文件", hypothesis="我觉得可以删")
        self.assertFalse(r.get("ok"), "没证据竟然过了闸 ⇒ 无脑操作没拦住")
        self.assertIn("无脑操作", [x["rule"] for x in r["refuses"]])

    def test_b_guess_is_refused(self):
        r = self.m.preflight(action="改配置", evidence="README.md", hypothesis="改")
        self.assertFalse(r.get("ok"), "没写清预期竟然过了闸 ⇒ 盲猜没拦住")
        rules = [x["rule"] for x in r["refuses"]]
        self.assertTrue(any("盲猜" in x for x in rules) or "证据不在盘上" in rules, f"规则名不对：{rules}")

    def test_c_missing_evidence_path_is_refused(self):
        r = self.m.preflight(action="跑链", evidence="no/such/file.json", hypothesis="跑完应该出 8 个镜头")
        self.assertFalse(r.get("ok"), "盘上没有的证据也敢当依据")
        self.assertIn("证据不在盘上", [x["rule"] for x in r["refuses"]])

    def test_d_stale_evidence_is_refused_unless_declared(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "old.json"
            p.write_text("{}", encoding="utf-8")
            old = time.time() - 7200
            os.utime(p, (old, old))
            r1 = self.m.preflight(action="按旧读数动手", evidence=str(p), hypothesis="我预期它能跑通")
            self.assertFalse(r1.get("ok"), "旧读数竟然放行 ⇒ 把过去当现状")
            self.assertIn("拿旧读数当现状", [x["rule"] for x in r1["refuses"]])
            r2 = self.m.preflight(action="有意用旧读数", evidence=str(p), hypothesis="我明说用两小时前的读数",
                                  stale_ok=True)
            self.assertTrue(r2.get("ok"), f"显式声明 stale_ok 仍被拒 ⇒ 闸太死：{r2.get('refuses')}")

    def test_e_happy_path_gets_a_gate_id_and_close_requires_saw(self):
        """齐活才发闸号。

        ⚠️ 证据要用**现写的**临时文件：早先这条拿 `state/skill_atlas.json` 当证据，图鉴一超过
        600s 就红（闸判"拿旧读数当现状"是对的，是判据自己脆）—— **判据不该依赖别的东西多久没动**。
        """
        with tempfile.TemporaryDirectory() as td:
            ev = Path(td) / "现在读到的读数.json"
            ev.write_text('{"看到的": "现写"}', encoding="utf-8")
            r = self.m.preflight(action="读一遍台账", evidence=str(ev),
                                 hypothesis="我预期这份现写的读数能被当证据")
            self.assertTrue(r.get("ok"), f"齐活了还不给过：{r.get('refuses')}")
            self.assertTrue(r.get("gate_id"), "过了闸没发闸号")
            bad = self.m.close(gate_id=r["gate_id"], result="读完了")
            self.assertFalse(bad.get("ok"), "close 没写'看到什么'也放行 ⇒ 结果无人复核")
            good = self.m.close(gate_id=r["gate_id"], result="读完了", saw="看到文件里写着'现写'")
            self.assertTrue(good.get("ok"))

    def test_g_observed_and_unchanged_counts_as_fresh(self):
        """**内容龄 ≠ 认知龄**：刚看过、且之后没被改过的旧文件算新鲜；看过之后被改 ⇒ 又变陈旧。

        没有这条的话，"先看"这个动作本身就不被认账（早先只比文件 mtime，看过的旧文件照样被判 stale）。
        """
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "老文件.json"
            p.write_text("{}", encoding="utf-8")
            old = time.time() - 7200
            os.utime(p, (old, old))                       # 两小时前写的
            self.m.observe(paths=str(p))                  # 但我刚刚看过
            r = self.m.preflight(action="按刚看过的旧文件动手", evidence=str(p),
                                 hypothesis="我看过了，我预期它能用")
            self.assertTrue(r.get("ok"), f"刚看过还不给过：{r.get('refuses')}")
            # 看过之后它被改了（mtime 仍是很老，只有内容变了）⇒ 我的"看过"作废
            p.write_text('{"变了": 1}', encoding="utf-8")
            os.utime(p, (old, old))
            r2 = self.m.preflight(action="按刚看过的旧文件动手", evidence=str(p),
                                  hypothesis="我看过了，我预期它能用")
            self.assertFalse(r2.get("ok"), "看过之后内容变了还放行 ⇒ 等于没看")
            self.assertIn("拿旧读数当现状", [x["rule"] for x in r2["refuses"]])

    def test_f_observe_records_real_evidence(self):
        r = self.m.observe(paths="state/skill_atlas.json, no/such/file")
        self.assertTrue(r.get("ok"))
        kinds = {e["exists"] for e in r["evidence"]}
        self.assertEqual({True, False}, kinds, "observe 没有如实区分'在'与'不在'")
        self.assertEqual(1, r["missing"])


class TestGrowthHooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load("gh_t", T / "growth_hooks.py")

    def test_a_shortboard_items_all_carry_src(self):
        r = self.m.shortboard()
        self.assertTrue(r.get("count") is not None, "短板没算出来")
        for it in r["top"]:
            self.assertTrue(it.get("src"), f"短板没带 src（那是印象不是读数）：{it}")

    def test_b_holdout_conflict_is_blocked(self):
        """撞封存验收集的步骤必须被拦：自己出题自己打分 = 不合规。"""
        old = self.m._holdout_ids
        # 每条计划的**第一步**都含"读现状" ⇒ 用它当封存项，保证必然撞上（与挑哪个短板无关）
        self.m._holdout_ids = lambda: {"读现状"}
        try:
            r = self.m.evolve(dry_run=True, item="能力位")
            flagged = [s for s in r["steps"] if s.get("holdout_conflict")]
            self.assertTrue(flagged, f"撞 holdout 却没被拦：{[s['step'] for s in r['steps']]}")
            self.assertTrue(all(not s.get("safe") for s in flagged), "拦下之后还标 safe")
            self.assertNotIn(flagged[0], r["auto_ran"], "被拦的步骤还进了自动执行")
        finally:
            self.m._holdout_ids = old

    def test_c_evolve_dry_run_does_not_run(self):
        r = self.m.evolve(dry_run=True)
        self.assertTrue(r.get("ok"))
        self.assertEqual([], r.get("auto_ran") or [], "dry_run 竟然动手了")
        self.assertTrue(r.get("shortboard"), "没挑出短板")


class TestDevourFusion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load("df_t", T / "devour_fusion.py")

    def test_a_fused_status_requires_three_artifacts(self):
        r = self.m.intake(id="判据自检假账", source="x", native_cap="no_such_cap_at_all",
                          tentacle="no_such_tentacle", status="已融合")
        self.assertFalse(r.get("ok"), f"三件不齐竟然写成已融合：{r}")
        self.assertTrue(r.get("refused"), "拒的形状不对（要 refused=True）")
        self.assertGreaterEqual(len(r.get("missing") or []), 2, "缺件没列全")

    def test_b_ledger_matches_disk(self):
        r = self.m.list()
        for row in r["rows"]:
            if row.get("status") == "已融合":
                self.assertTrue(row["fused"], f"台账写已融合但盘上不齐：{row.get('id')}")
        self.assertTrue(self.m.verify().get("ok"), f"有假账：{self.m.verify().get('problems')}")

    def test_c_pending_intakes_are_honest(self):
        """图片里那三件必须**有名有姓在账上**，且状态只能是「真值」之一。

        🔴 2026-10-17 翻正（留痕 · 原断言 / 为什么翻 / 现口径）：
          原断言：`win-mcp` / `dataease` / `freecad-mcp` 只要在账上，状态**必须是 `待吞`**。
          为什么翻：现读盘上，这三件对应的原生位 **`desktop_distill` / `bi_distill` / `cad_distill`
            都已经三处齐**（注册表 + 模块 + api 分派 + 图鉴，均实测在位）——「吞天」的完成标志
            就是**蒸出原生位**，不是「把上游原工具装上」。它们已真蒸 ⇒ 台账 `已融合` 是**诚实的**；
            原断言写死 `待吞` 会把"真蒸了"判成假账（反而逼人写假话）。
          现口径（**更严**，不是放宽）：这三件必须出现在账上，且状态必须满足
            ① `待吞`（还没吞）——放行；
            ② `已融合` —— **必须同时算得出 `fused=True`**（三处齐 + 触手有效 + 库有笔记），
               算不出来就是假账，当场红；
            ③ 其它状态（含历史中间态 `已吸收`）—— 放行但必须是 `STATUSES` 里的合法值。
          即：**不许拿「装了没蒸」冒充融合**；也不许拿「真蒸了」当没蒸。
        """
        legal = {"待吞", "已吸收", "已融合"}
        r = self.m.list()
        by_id = {x.get("id"): x for x in r["rows"]}
        for want in ("win-mcp", "dataease", "freecad-mcp"):
            self.assertIn(want, by_id, "这三件必须**有名有姓**在账上（不许悄悄消失）")
            row = by_id[want]
            status = row.get("status")
            self.assertIn(status, legal, "%s 的状态不在合法集：%r" % (want, status))
            if status == "已融合":
                self.assertTrue(row.get("fused"),
                                "%s 写成已融合但盘上算不出三件齐（= 假账）" % want)


class TestBindingHook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load("bh_t", ROOT / "tools" / "binding_hook.py")

    def test_a_new_caps_have_all_six_legs(self):
        for kind in NEW_CAPS:
            L = self.m.legs(kind)
            miss = [k for k, v in L.items() if k.startswith(("①", "②", "③", "④", "⑥")) and not v]
            self.assertEqual([], miss, f"{kind} 有腿没接上：{miss}")

    def test_d_grouped_dispatch_counts_as_wired(self):
        """**成组元组分派也算分派**（血账：只认 `kind == "x"` 会把 25 条报成"没分派"）。

        api.py 里大量能力位是 `if kind in ("a", "b", "c")` 的写法；判据必须与
        `tools/framework_state.py` 同一把尺 —— 两种写法都算，否则就是**假报断连**。
        """
        L = self.m.legs("keylogger")          # 实测在 api.py 里是成组元组里的一个
        self.assertTrue(L["②分派"], f"成组元组分派没被认成分派：{L}")

    def test_b_hook_refuses_to_invent_an_unregistered_cap(self):
        r = self.m.after_add(kind="完全不存在的能力位")
        self.assertFalse(r.get("ok"), "没登记的东西竟然被钩子'办'了")
        self.assertTrue(r.get("fail_closed"), "应该 fail-closed")

    def test_c_verify_reports_real_state(self):
        r = self.m.verify()
        self.assertGreater(r.get("caps", 0), 200, "能力位数异常")
        self.assertTrue(r.get("ledger_rows"), "钩子台账是空的 ⇒ 一次都没走过")


class TestAllNewCapsDispatchThroughDoor(unittest.TestCase):
    """G. 三处齐的实证：五个新能力位都要能过 `run_task` 调到（不是只看文件在不在）。"""

    READ_ONLY = {"obsidian_vault": "status", "cap_tags": "tags", "action_gate": "status",
                 "growth_hooks": "verify", "devour_fusion": "list"}

    def test_all_five_are_callable(self):
        import sys
        sys.path.insert(0, str(ROOT))
        import gbt_allinone as g
        for kind, op in self.READ_ONLY.items():
            r = g.run_task(kind, {"op": op})
            payload = r.get("result", r)
            if isinstance(payload, dict) and "result" in payload:
                payload = payload["result"]
            self.assertTrue(payload.get("ok"), f"{kind} op={op} 过门调不通：{str(payload)[:200]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
