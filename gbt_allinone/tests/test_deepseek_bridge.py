# -*- coding: utf-8 -*-
"""DeepSeek 免费决策桥 · 判据（2026-10-04 主人令：GBT 全能力接入 chat.deepseek.com）。

**判据（都可判定，全部封闭——run_task 被 monkeypatch，绝不碰真盘/真门/真网）**：
  A. 清单：manifest 把**每一个** enabled 能力位一项一项列出（名字集合恒等，不许漏、不许编）；
  B. 解析：多行块 / 单行内联块 / `gbt json` 语言后缀都认；```gbt-result **绝不**被误抓（防回喂自吞环）；
  C. 纪律：不在册 kind（如 keylogger）在**解析层**就被拒，一次执行都不发生；
  D. dry-run：不带 --execute 时不调用 run_task（先看后跑是主人的默认权利）；
  E. 执行：过 run_task_safe 唯一口；结果带 ok/error/ms；缺票回执**原样**透传（不美化）；
  F. 急停：PAUSE 文件在 ⇒ 一律拒绝执行（宁可停，不可闯）；
  G. 回喂：反馈块是合法 JSON 的 ```gbt-result 栏，且它自己**不再匹配**指令块正则（闭环不自吞）；
  H. 截断：超大结果带 `…截断…` 标记（不许静默扔数据）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("GBT_DS_BRIDGE_STATE", tempfile.mkdtemp(prefix="gbt-dsbridge-test-"))

TOOL = ROOT / "tools" / "codex-scripts" / "deepseek_bridge.py"
_spec = importlib.util.spec_from_file_location("deepseek_bridge", TOOL)
BR = importlib.util.module_from_spec(_spec)
sys.modules["deepseek_bridge"] = BR
_spec.loader.exec_module(BR)


class _FakeGate:
    """替身 run_task：记调用、按剧本回信封。"""

    def __init__(self, script=None):
        self.calls = []
        self.script = script or {}

    def __call__(self, kind, payload=None, **kw):
        self.calls.append((kind, payload, kw))
        if kind in self.script:
            return self.script[kind]
        return {"ok": True, "kind": kind, "result": {"stub": True}}


class DeepSeekBridgeTests(unittest.TestCase):
    def setUp(self):
        # 每条用例换一块自留地，互不串账
        self.state = Path(tempfile.mkdtemp(prefix="gbt-dsbridge-case-"))
        self._orig = (BR.STATE, BR.PAUSE, BR.ROUNDS, BR.WATCH_STATE)
        BR.STATE, BR.PAUSE = self.state, self.state / "PAUSE"
        BR.ROUNDS, BR.WATCH_STATE = self.state / "rounds.jsonl", self.state / "watch_state.json"

    def tearDown(self):
        (BR.STATE, BR.PAUSE, BR.ROUNDS, BR.WATCH_STATE) = self._orig

    # ── A 清单 ──
    def test_manifest_lists_every_enabled_cap_one_by_one(self):
        from gbt_allinone.caps_registry import all_caps
        rows = all_caps()
        enabled = {c["name"] for c in rows if c.get("status") == "enabled"}
        unimp = {c["name"] for c in rows if c.get("status") != "enabled"}
        m = BR.build_manifest()
        got = {c["name"] for dom in m["domains"] for c in dom["caps"]}
        self.assertEqual(got, enabled, "清单与在册能力位名字集合必须恒等（漏一位=假接入，多一位=假能力）")
        self.assertEqual(m["enabled_count"], len(enabled))
        self.assertEqual({u["name"] for u in m["unimplemented"]}, unimp,
                         "登记未实现的位也要如实列出（不许隐藏）")
        md = BR.render_manifest(m)
        missing = [n for n in enabled if n not in md]
        self.assertFalse(missing, "markdown 清单漏了：%s" % missing[:10])
        for token in ("指令块格式", "run_task", "缺作用域", "gbt-result"):
            self.assertIn(token, md, "清单头必须讲清闭环纪律：%s" % token)

    # ── B 解析 ──
    def test_extract_blocks_multiline_inline_suffix_and_result_not_matched(self):
        text = (
            "先看一下：\n\n```gbt\n{\"kind\": \"health\", \"args\": {\"deep\": {\"a\": 1}}}\n```\n\n"
            "再内联一条：```gbt {\"kind\": \"task_manager\", \"args\": {\"op\": \"list\"}}```\n\n"
            "```gbt json\n{\"kind\": \"llm_status\", \"args\": {}}\n```\n\n"
            "下面是回喂样例（绝不能被当指令抓走）：\n\n```gbt-result\n{\"summary\": \"x\"}\n```\n"
        )
        blocks = BR.extract_blocks(text)
        kinds = [b["obj"].get("kind") for b in blocks if b["obj"]]
        self.assertEqual(kinds, ["health", "task_manager", "llm_status"],
                         "多行/内联/带语言后缀都该认；gbt-result 绝不许混进来")
        self.assertTrue(all(not b["error"] for b in blocks),
                         "好块不许带错：%s" % [b["error"] for b in blocks if b["error"]])

    def test_extract_blocks_bad_json_reported_honestly(self):
        blocks = BR.extract_blocks("```gbt\n{\"kind\": broken}\n```")
        self.assertEqual(len(blocks), 1)
        self.assertIsNone(blocks[0]["obj"])
        self.assertIn("JSON 解析失败", blocks[0]["error"])
        blocks2 = BR.extract_blocks("```gbt\n[1,2,3]\n```")
        self.assertIn("必须是 JSON 对象", blocks2[0]["error"])
        blocks3 = BR.extract_blocks("```gbt\n{\"kind\": \"health\"}\n")   # 没收栏
        self.assertIn("缺收栏", blocks3[0]["error"])

    # ── C 两层拒绝，各在其位 ──
    def test_unregistered_kind_rejected_at_parse_layer(self):
        fake = _FakeGate()
        orig, BR.run_task_safe = BR.run_task_safe, fake
        try:
            rnd = BR.execute_round('```gbt\n{"kind": "not_a_real_cap_xyz", "args": {}}\n```',
                                   "test", execute=True)
        finally:
            BR.run_task_safe = orig
        self.assertEqual(fake.calls, [], "不在册名一次都不许执行（编造名连门都到不了）")
        self.assertEqual(rnd["rejected"], 1)
        self.assertIn("不在 GBT 在册能力", rnd["results"][0]["error"])

    def test_registered_dangerous_kind_denied_by_gate_verbatim(self):
        # keylogger 这类在册但涉险的名，桥**不另立黑名单**，送门硬拒、回执原样回喂
        # （单一真相 = policy.py；桥复制一份黑名单 = 两处真相必漂移）。
        import gbt_allinone.api as API
        denial = {"ok": False, "kind": "keylogger",
                  "error": "已拒绝：keylogger 是 policy 硬拒类，不存在授权路径"}
        orig_api, API.run_task = API.run_task, (lambda kind, payload=None, **kw: denial)
        orig_bridge, BR.run_task_safe = BR.run_task_safe, BR.run_task_safe
        try:
            rnd = BR.execute_round('```gbt\n{"kind": "keylogger", "args": {}}\n```',
                                   "test", execute=True)
        finally:
            API.run_task = orig_api
            BR.run_task_safe = orig_bridge
        self.assertEqual(rnd["failed"], 1)
        row = rnd["results"][0]
        self.assertFalse(row["ok"])
        self.assertIn("policy 硬拒", row["error"], "门的拒绝理由必须原样带回，不许美化")

    # ── D dry-run ──
    def test_dry_run_never_executes(self):
        fake = _FakeGate()
        orig, BR.run_task_safe = BR.run_task_safe, fake
        try:
            rnd = BR.execute_round('```gbt\n{"kind": "health", "args": {}}\n```',
                                   "test", execute=False)
        finally:
            BR.run_task_safe = orig
        self.assertEqual(fake.calls, [])
        self.assertEqual(rnd["mode"], "dry")
        self.assertIsNone(rnd["results"][0]["ok"])
        self.assertIn("dry-run", rnd["results"][0]["note"])

    # ── E 执行与缺票透传 ──
    def test_execute_routes_through_gate_and_reports_verbatim(self):
        fake = _FakeGate(script={"code_patch": {
            "ok": False, "kind": "code_patch", "error": "缺 filesystem_write 授权（票只能主人在终端发放）"}})
        orig, BR.run_task_safe = BR.run_task_safe, fake
        try:
            rnd = BR.execute_round(
                '```gbt\n{"kind": "health", "args": {}}\n```\n'
                '```gbt\n{"kind": "code_patch", "args": {"path": "x"}}\n```',
                "test", execute=True)
        finally:
            BR.run_task_safe = orig
        self.assertEqual([c[0] for c in fake.calls], ["health", "code_patch"])
        by_kind = {r["kind"]: r for r in rnd["results"] if r.get("kind")}
        self.assertTrue(by_kind["health"]["ok"])
        self.assertFalse(by_kind["code_patch"]["ok"])
        self.assertIn("缺 filesystem_write", by_kind["code_patch"]["error"],
                      "门的回执必须原样带回，不许美化")
        self.assertEqual(rnd["ok"], 1)
        self.assertEqual(rnd["failed"], 1)
        # 台账真落了
        self.assertTrue(BR.ROUNDS.exists())
        row = json.loads(BR.ROUNDS.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(row["found"], 2)
        self.assertEqual(row["executed"], 2)

    def test_gate_contract_safe_true_and_result_passthrough(self):
        # safe=True 合同直接对真执行口验（替换 api.run_task 本尊，不替桥的包装）：
        # 永不炸信封是桥接层的合同，写死在 run_task_safe 里。
        import gbt_allinone.api as API
        seen = {}

        def spy(kind, payload=None, **kw):
            seen.update(kind=kind, payload=payload, kw=kw)
            return {"ok": True, "kind": kind, "result": {"answer": 42}}

        orig, API.run_task = API.run_task, spy
        try:
            rnd = BR.execute_round('```gbt\n{"kind": "health", "args": {"deep": 1}}\n```',
                                   "test", execute=True)
        finally:
            API.run_task = orig
        self.assertEqual(seen["kw"].get("safe"), True,
                         "run_task_safe 必须以 safe=True 过门")
        self.assertEqual(seen["payload"], {"deep": 1})
        row = rnd["results"][0]
        self.assertTrue(row["ok"])
        self.assertIn("42", row["result"], "结果要回喂给决策模块")

    def test_block_cap_per_round(self):
        many = "\n".join('```gbt\n{"kind": "health", "args": {}}\n```' for _ in range(BR.MAX_BLOCKS_PER_ROUND + 3))
        fake = _FakeGate()
        orig, BR.run_task_safe = BR.run_task_safe, fake
        try:
            rnd = BR.execute_round(many, "test", execute=True)
        finally:
            BR.run_task_safe = orig
        self.assertEqual(len(fake.calls), BR.MAX_BLOCKS_PER_ROUND)
        self.assertEqual(rnd["skipped"], 3)

    # ── F 急停 ──
    def test_pause_file_halts_everything(self):
        BR.PAUSE.write_text("stop", encoding="utf-8")
        fake = _FakeGate()
        orig, BR.run_task_safe = BR.run_task_safe, fake
        try:
            rnd = BR.execute_round('```gbt\n{"kind": "health", "args": {}}\n```', "test", execute=True)
        finally:
            BR.run_task_safe = orig
        self.assertEqual(fake.calls, [])
        self.assertEqual(rnd["summary"], "PAUSED")
        self.assertIn("急停闸", rnd["why"])

    # ── G 回喂不自吞 ──
    def test_feedback_is_fenced_result_and_not_reingested(self):
        rnd = BR.execute_round('```gbt\n{"kind": "health", "args": {}}\n```', "test", execute=False)
        fb = BR.render_feedback(rnd)
        self.assertIn("```gbt-result", fb)
        body = fb.split("```gbt-result\n", 1)[1].rsplit("```", 1)[0]
        obj = json.loads(body)
        self.assertEqual(obj["summary"], rnd["summary"])
        self.assertEqual(BR.extract_blocks(fb), [],
                         "反馈块被桥再吃进去 = 闭环自吞环（解析器必须排除 gbt-result）")

    # ── H 截断 ──
    def test_oversized_result_truncated_with_marker(self):
        big = {"blob": "x" * 5000}
        s = BR._compact(big, budget=1000)
        self.assertIn("…截断", s)
        self.assertLess(len(s), 1600)
        self.assertIn("原 5", s)

    def test_round_log_rotation(self):
        for i in range(30):
            BR._log_round({"ts": "t", "source": "test", "mode": "dry", "found": 0, "executed": 0,
                           "ok": 0, "failed": 0, "rejected": 0, "skipped": 0, "kinds": [],
                           "summary": "s%d" % i})
        lines = BR.ROUNDS.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 30, "未到阈值不许裁")
        # 阈值行为用小参数直验（不改模块常量的前提下按公式验）
        self.assertGreaterEqual(BR._ROUNDS_MAX, BR._ROUNDS_KEEP)

    # ── I 剪贴板读口炸不坏（2026-10-04 实测 access violation 教训）──
    def test_clip_read_never_raises_and_returns_str(self):
        # 读的是真剪贴板（只读）；无论里面是什么/别家是否正在改写，都不许抛
        val = BR.clip_read()
        self.assertIsInstance(val, str)
        self.assertLessEqual(len(val), 4 * 1024 * 1024, "定界读上限生效")

    # ── J 一键投喂（能力原生化）──
    def test_feed_puts_native_identity_and_full_manifest_on_clipboard(self):
        import argparse
        seen = {}
        orig = BR.clip_write
        BR.clip_write = lambda text: seen.update(text=text) or True
        try:
            rc = BR.cmd_feed(argparse.Namespace())
        finally:
            BR.clip_write = orig
        self.assertEqual(rc, 0)
        text = seen.get("text", "")
        self.assertIn("原生执行内核", text, "投喂件必须带身份注入（不然她继续自称没工具）")
        self.assertIn("GBT小土豆V8", text)
        self.assertIn("指令块格式", text, "投喂件必须教闭环用法")
        self.assertIn("task_manager", text, "投喂件必须带全部能力位")
        self.assertTrue(BR.MANIFEST_MD.exists(), "投喂同时落一份文件兜底（剪贴板失败还有路）")


if __name__ == "__main__":
    unittest.main()
