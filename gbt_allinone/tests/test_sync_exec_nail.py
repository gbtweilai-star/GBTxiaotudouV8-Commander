# -*- coding: utf-8 -*-
"""五维合一同步执行 · **钉子测试**（Owner 2026-09-22：「必须给我钉死，不管怎么重启都是这个执行方式」）

═══ 为什么这个文件本身就是"钉死" ═══
  重启会丢的是**记忆**；不会丢的是**磁盘上的代码**。
  所以"钉死"= 把这条执行方式变成**代码事实**，再用测试守住它：
      谁删了它 ⇒ 这个测试红 ⇒ 删的人立刻知道自己在违约
      进程重启 ⇒  pytest 一跑，机制还在不在，当场见分晓

═══ 守哪六颗钉 ═══
  1. 五维（route/execute/verify/health/unify）**每个都挂 @_spanned**
     —— 少了谁，"忙/卡"那一维就永远点不亮（= 不可观测）
  2. `brain_exec.span` 存在，且**异常路径也一定落 exit**
     （否则崩一次就永久"卡"着，成了假信号）
  3. `sync_exec.run` 存在，且**四觉齐全**（ear/eye/hand/mouth）
  4. **嘴不许只报喜**：`mouth()` 必须能吐出 missed / bad_dims
  5. **眼不许默认没问题**：不给观察目标时 `eye()` 必须 ok=False
  6. **耳不许空转**：空目标必须中止并记 sync_abort
"""
import ast
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_sync_test_"))

_PKG = Path(__file__).resolve().parent.parent          # gbt_allinone/
_BE = _PKG / "brain_exec.py"
_SE = _PKG / "tools" / "sync_exec.py"

_DIMS = ("route", "execute", "verify", "health", "unify")


def _decorated_funcs(src: str) -> set:
    """AST 取"挂了 @_spanned 的函数名" —— 不看文本，免得被注释里的示例骗到。"""
    out = set()
    for n in ast.parse(src).body:
        if isinstance(n, ast.FunctionDef):
            for d in n.decorator_list:
                name = getattr(d, "id", None) or getattr(d, "attr", None)
                if name == "_spanned":
                    out.add(n.name)
    return out


class NailTests(unittest.TestCase):
    """六颗钉，缺一颗就红。"""

    def test_nail1_all_five_dims_are_spanned(self):
        got = _decorated_funcs(_BE.read_text(encoding="utf-8-sig"))
        missing = [d for d in _DIMS if d not in got]
        self.assertFalse(missing, f"这些维没挂 @_spanned，忙/卡将不可观测: {missing}")

    def test_nail2_span_records_exit_even_on_exception(self):
        src = _SE.parent.parent.joinpath("brain_exec.py").read_text(encoding="utf-8-sig")
        self.assertIn("def span(", src, "span 没了，进出事件断链")
        # 必须同时有 except 分支（异常也落）与 else 分支（正常落）
        tree = ast.parse(src)
        span_fn = next(n for n in ast.walk(tree)
                       if isinstance(n, ast.FunctionDef) and n.name == "span")
        has_except = any(isinstance(x, ast.ExceptHandler) for x in ast.walk(span_fn))
        self.assertTrue(has_except, "span 没有 except 分支 ⇒ 崩一次就永久'卡'着（假信号）")

    def test_nail3_four_senses_exist(self):
        from gbt_allinone.tools import sync_exec as se
        for fn in ("ear", "eye", "mouth", "run"):
            self.assertTrue(callable(getattr(se, fn, None)), f"缺 {fn}()")

    def test_nail4_mouth_must_report_what_it_missed(self):
        from gbt_allinone.tools import sync_exec as se
        m = se.mouth("目标", {"route": {"state": "ok"}},
                     {"eye": {"ok": False, "note": "这次没看"}})
        self.assertIn("missed", m["said"], "嘴没有 missed 字段 ⇒ 会只报喜")
        self.assertTrue(m["said"]["missed"], "明明有没做到的，missed 却是空的 ⇒ 假嘴")
        self.assertEqual(m["verdict"], "partial", "有没做到的却报 ok ⇒ 假嘴")

    def test_nail5_eye_must_not_default_to_ok(self):
        from gbt_allinone.tools import sync_exec as se
        r = se.eye(None)
        self.assertFalse(r["ok"], "没给观察目标却报 ok ⇒ 默认'应该没问题'，这正是要防的")
        self.assertIn("没看", r["note"])

    def test_nail6_ear_must_abort_on_empty_goal(self):
        from gbt_allinone.tools import sync_exec as se
        r = se.ear("")
        self.assertFalse(r["ok"], "空目标竟然听清了 ⇒ 会瞎干")
        out = se.run("")
        self.assertFalse(out.get("ok", True), "空目标竟然跑完了全程")

    def test_nail7_brainless_ratio_is_measurable(self):
        """尺子本身也得在 —— 不然'改进没有'只能靠嘴说。"""
        from gbt_allinone.tools import sync_exec as se
        r = se.audit_sync(limit=200)
        self.assertTrue(r["ok"])
        for k in ("cap_calls_total", "inside_envelope", "outside_envelope",
                  "brainless_ratio", "verdict"):
            self.assertIn(k, r, f"审计缺字段 {k} ⇒ 这把尺子量不全")


class DefaultSyncTests(unittest.TestCase):
    """第八颗钉（2026-09-23 Owner 令）：**大脑执行层 / 万能插 / 五维合一 默认同步**。

    为什么必须钉死在这儿 —— 当轮实测三条主道的默认同步状态**只有两条是好的**：
      · 五维合一 `five-dim.py cap`：有（自己开信封 + 自动开步/收步）；
      · 万能插 `omni.py run`：有（起 `five-dim.py cap` 子进程，不传 `--no-envelope`）；
      · **大脑执行层：没有自己的** —— `engine.py` 是 `from .api import _run_task_core as run_task`
        直连内层，面板 `panel_server.capability()` / `python -m gbt_allinone` / 任何直调
        在账本上一律 `synced: false`。

    落实点收在**唯一那道门**（`api._run_task_core` 一进来 `auto_envelope()`），所以这里钉三件事：
      A 直调也默认同步（`auto`）
      B 已经在信封里就**原样不动**（`outer`，不覆盖外层归属）
      C **留着一个能关的开关** —— `GBT_ENVELOPE_OFF=1` 必须真的记 `synced: false`。
        没有 C 这把尺子就不可证伪（测不出"假"的尺子不是尺子）。
    """

    def _rows(self, run):
        """隔离审计落点（**只改 `store._LOG`**，不碰 `GBT_STORE_DIR`）。

        🔴 第一版我改的是 `GBT_STORE_DIR` 环境变量 —— 当场被 `_paths.verify_store_binding()`
        拒了（"store 绑定与环境变量不一致，拒绝写入"）。那个门是对的：**进程内换 store 身份
        本身就是该被拦住的事**。隔离审计只需把落点指到 tmp 文件，不必换身份。
        """
        import contextlib
        import tempfile
        from gbt_allinone import api, store

        tmp = Path(tempfile.mkdtemp(prefix="gbt_defsync_")) / "audit.jsonl"

        @contextlib.contextmanager
        def _iso():
            old = store._LOG
            store._LOG = tmp
            try:
                yield
            finally:
                store._LOG = old

        with _iso():
            run(api)
        return [json.loads(l) for l in tmp.read_text(encoding="utf-8").splitlines() if l.strip()]

    def _call_row(self, rows):
        return next(r for r in rows
                    if r.get("event") == "call" and (r.get("meta") or {}).get("kind") == "echo")

    def test_A_direct_call_defaults_to_synced(self):
        rows = self._rows(lambda api: api.run_task("echo", {"text": "gbt"}))
        m = self._call_row(rows)["meta"]
        self.assertTrue(m.get("synced"), "直调没默认同步 ⇒ 门口那道默认没生效")
        self.assertEqual(m.get("synced_via"), "ctx")
        self.assertEqual(m.get("synced_entry"), "auto",
                         "门口替你开的要记 auto —— 混成一格会把'默认打开了'读成'纪律执行得好'")

    def test_B_outer_envelope_is_not_overwritten(self):
        from gbt_allinone.tools.sync_exec import envelope

        def _run(api):
            with envelope():
                api.run_task("echo", {"text": "gbt"})

        m = self._call_row(self._rows(_run))["meta"]
        self.assertTrue(m.get("synced"))
        self.assertEqual(m.get("synced_entry"), "outer", "外层主动信封被门口的默认盖掉了")

    def test_C_negative_control_can_still_be_off(self):
        """负对照：显式要求不进信封，就必须真有 `synced: false` 的记录可看。"""
        prev = os.environ.get("GBT_ENVELOPE_OFF")
        os.environ["GBT_ENVELOPE_OFF"] = "1"
        try:
            rows = self._rows(lambda api: api.run_task("echo", {"text": "gbt"}))
        finally:
            if prev is None:
                os.environ.pop("GBT_ENVELOPE_OFF", None)
            else:
                os.environ["GBT_ENVELOPE_OFF"] = prev
        m = self._call_row(rows)["meta"]
        self.assertFalse(m.get("synced"), "负对照被默认同步吃掉了 ⇒ 这把尺子不可证伪")


class StepLedgerTests(unittest.TestCase):
    """第九组钉（2026-09-23）：**步账**是「欠的活」的唯一清单，它自己不许丢账。

    机检到的事实（改前）：**开步 64 · 收步 49**，而"未收步清单"是 `{}`
      ⇒ 那 15 步**既没收、也没留在盘上 = 丢了**。
    两条成因，两条都钉：
      ① 落点硬编码 `_BASE/'store'`、**不跟 `GBT_STORE_DIR`** ⇒ 隔离 store 里跑的一发
         会把开步写进**生产步账**，而它的收步落在别处/进程被杀 ⇒ 永久孤儿步；
      ② `_steps_load()` → 改 → `_steps_save()` 是**整文件读-改-写、没有锁** ⇒
         两个进程交错互相覆盖；`write_text` 写一半被杀还会留**半个 JSON**
         ⇒ 下次解析失败 ⇒ 静默 `{}` ⇒ **所有未收的步一起消失**。
    """

    def _se(self):
        from gbt_allinone.tools import sync_exec as se
        return se

    def test_steps_file_follows_store_binding(self):
        """落点必须来自 store 绑定（单一来源），不是硬编码仓内 store。"""
        from gbt_allinone import _paths
        se = self._se()
        self.assertEqual(se._STEPS_FILE.parent.resolve(), _paths.STORE_DIR.resolve(),
                         "步账落点没跟 store 绑定走 ⇒ 隔离跑一发就污染生产步账")
        self.assertEqual(se._LOCK_FILE.parent.resolve(), _paths.STORE_DIR.resolve(),
                         "锁文件必须和步账同目录（跨进程才锁得住同一个东西）")

    def test_lock_is_exclusive(self):
        """独占：拿着锁的期间，第二个获取者必须拿到 False（不许两个都以为自己在锁里）。"""
        se = self._se()
        with se._steps_lock(timeout=1.0) as first:
            self.assertTrue(first, "第一个竟然没拿到锁")
            with se._steps_lock(timeout=0.2) as second:
                self.assertFalse(second, "锁不独占 ⇒ 并发下必然互相覆盖")

    def test_atomic_write_leaves_no_half_file_or_residue(self):
        """原子写：盘上只能有**可解析的完整 JSON**，不许留 .tmp / .lock 残渣。"""
        se = self._se()
        r = se.step_open("钉子测试·原子写")
        self.assertTrue(r.get("ok"), r)
        raw = se._STEPS_FILE.read_text(encoding="utf-8")
        json.loads(raw)                                  # 半个 JSON 会在这儿就炸
        residue = [p.name for p in se._STEPS_FILE.parent.iterdir()
                   if p.name.startswith("sync_steps.") and p.name != se._STEPS_FILE.name]
        self.assertEqual([], residue, "留下了残渣: %s" % residue)
        se.step_close(r["step_id"], evidence=["nail=atomic"])

    def test_open_close_roundtrip_returns_to_zero(self):
        """开一步 → 收一步，盘上必须回到 0，且收步给出判决（不许静默成功）。"""
        se = self._se()
        before = len(json.loads(se._STEPS_FILE.read_text(encoding="utf-8"))) \
            if se._STEPS_FILE.is_file() else 0
        r = se.step_open("钉子测试·来回一趟")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(before + 1, r.get("open_steps"), "开步后未收步数没涨")
        c = se.step_close(r["step_id"], evidence=["nail=roundtrip"])
        self.assertIn(c.get("verdict"), ("ok", "partial"),
                      "收步没给判决（ok/partial）⇒ 只报喜或装死")
        after = len(json.loads(se._STEPS_FILE.read_text(encoding="utf-8")))
        self.assertEqual(before, after, "收步后未收步数没回到原值 ⇒ 步账泄漏")


class OmniRunPathTests(unittest.TestCase):
    """第十组钉（2026-09-23）：`omni run` 走五维默认路径，但**判据仍由 omni 出**。

    背景（机检）：`omni.py` 原先直接起 `five-dim.py cap` ⇒ 只到能力位那层，
    大脑（`brain_*`）与五维真链一次不参与（装钩子后 `brain_unify = 0`、`run() 全链 = 0`）。
    改成走 `sync_exec.run(intent, kind=…, use_unify=False)` 之后，
    **必须钉住"不许 use_unify=True"** —— 因为 `brain_unify` **自己会重新 route 并执行**，
    那就绕过了 omni 唯一的防乱跑装置（`auto_run_verdict` 默认拒绝）。
    这三条是**安全性质**，不是风格偏好。
    """

    _OMNI = Path(__file__).resolve().parents[2] / "tools" / "codex-scripts" / "omni.py"

    def _cmd_run_ast(self):
        """取 `cmd_run` 的 AST 节点 —— **不看文本**。

        🔴 第一版拿 `assertNotIn("use_unify=True", 源码)` 当判据，**当场被我自己的注释骗了**：
        注释里正好写着"为什么必须 use_unify=False（而 use_unify=True 会…）"。
        这正是本仓的老教训（`_decorated_funcs` 的 docstring 原文：「不看文本，免得被注释里的示例骗到」）。
        ⇒ 判"真调了什么"只能读 AST 里的 **Call 节点**。
        """
        tree = ast.parse(self._OMNI.read_text(encoding="utf-8-sig"))
        return next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "cmd_run")

    def _calls(self, node, name: str) -> list:
        """函数体里所有"函数名/属性名 == name"的 Call 节点。"""
        out = []
        for x in ast.walk(node):
            if isinstance(x, ast.Call):
                f = x.func
                n = getattr(f, "id", None) or getattr(f, "attr", None)
                if n == name:
                    out.append(x)
        return out

    def test_gate_still_runs_before_execution(self):
        """默认拒绝判定必须还在，且在真跑之前（**按行号比，按文本比会被注释骗**）。"""
        fn = self._cmd_run_ast()
        gates = self._calls(fn, "auto_run_verdict")
        runs = self._calls(fn, "run")
        self.assertTrue(gates, "omni run 的默认拒绝判定被拿掉了")
        self.assertTrue(runs, "没找到执行调用（sync_exec.run）")
        self.assertLess(min(g.lineno for g in gates), min(r.lineno for r in runs),
                        "判定跑到执行后面去了 ⇒ 等于没判")

    def test_five_dim_path_never_re_routes(self):
        """真调用必须是 `use_unify=False`（AST 读关键字实参，不读注释）。"""
        fn = self._cmd_run_ast()
        runs = [c for c in self._calls(fn, "run")
                if any(k.arg == "use_unify" for k in c.keywords)]
        self.assertTrue(runs, "没找到带 use_unify 的 sync_exec.run 调用 ⇒ 五维路径没接上")
        for c in runs:
            kw = {k.arg: k.value for k in c.keywords}
            v = kw.get("use_unify")
            self.assertIsInstance(v, ast.Constant, "use_unify 传的不是字面量")
            self.assertIs(v.value, False,
                          "use_unify 不是 False ⇒ brain_unify 会自己重新 route 并执行，"
                          "绕过 omni 的默认拒绝判定（安全件，不许放宽）")
            self.assertIn("kind", kw, "没把 omni 判定出的 kind 固定传下去 ⇒ 还是可能被重新 route")

    def test_no_unify_means_brain_unify_is_never_called(self):
        """动态钉：`use_unify=False` 时账本里**不许出现 `brain_unify`**。

        这是"没有重新 route"的**直接证据** —— 不是看代码，是看它到底调了谁。
        """
        import contextlib
        import tempfile
        from gbt_allinone import store
        from gbt_allinone.tools import sync_exec as se

        tmp = Path(tempfile.mkdtemp(prefix="gbt_omni_path_")) / "audit.jsonl"

        @contextlib.contextmanager
        def _iso():
            old = store._LOG
            store._LOG = tmp
            try:
                yield
            finally:
                store._LOG = old

        with _iso():
            r = se.run("钉子测试：只读健康检查", kind="health", use_unify=False)
        self.assertIn(r.get("verdict"), ("ok", "partial", "aborted"), r)
        rows = [json.loads(l) for l in tmp.read_text(encoding="utf-8").splitlines() if l.strip()]
        kinds = [((x.get("meta") or {}).get("kind")) for x in rows]
        self.assertNotIn("brain_unify", kinds,
                         "use_unify=False 竟然还调了 brain_unify ⇒ 会重新 route、绕过默认拒绝")
        self.assertIn("health", kinds, "连 health 都没调 ⇒ 这条测试没测到东西（假绿）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
