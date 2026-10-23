# -*- coding: utf-8 -*-
"""O8 契约测试：`run_task` 的探针免审计口。

三条硬约束（风哥 2026-09-17 批复原文）：
  ① `probe=True` 只允许白名单两处（`holo_pet/panel_server.py` 的 `_sensory_hand` / `_safe_bt_status`）；
  ② `run_task` 默认行为不变——判据是 **`{"event","meta"}` 的 JSON 序列化一致**，
     摘掉 `ts`/`iso` 两个天然时变字段（**摘掉不可能相同的字段，不是放松判据**）；
  ③ 正负对照必过《扫描器自证律》：判别不出差异就报 `SCANNER_BLIND`，不许报 PASS。

隔离口径：把 `store._LOG` 指到临时文件（`audit()` 是调用时才读 `_LOG`），
不新造隔离开关、不碰生产 `store/audit.jsonl`。
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
for _p in (ROOT, HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gbt_allinone import api, store  # noqa: E402
from gbt_allinone.tools import scan_scope  # noqa: E402


def _read_rows():
    """读隔离审计文件 → [{"event","meta"}]；文件不存在 = 0 行（免写的证据形态）。"""
    path = str(store._LOG)
    if not os.path.exists(path):
        return []
    rows = []
    with io.open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rows.append({"event": rec.get("event"), "meta": rec.get("meta")})
    return rows


def _canonical(rows):
    """逐字节判据的规范化形式：ts / iso 根本没进 rows，其余一个字节都不许差。"""
    return [json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows]


@contextlib.contextmanager
def isolated_store():
    """把审计落点临时改到 tmp 文件，退出即还原（不动生产审计流）。"""
    tmp = tempfile.mkdtemp(prefix="o8_probe_test_")
    log = Path(tmp) / "audit.jsonl"
    old = store._LOG
    store._LOG = log
    try:
        yield log
    finally:
        store._LOG = old


class ProbeAuditTests(unittest.TestCase):
    """V5：免审计的正负对照（同 kind、两种写法，结果必须不同）。"""

    def test_probe_true_writes_nothing_probe_false_writes_two(self):
        with isolated_store():
            api.run_task("bluetooth", {"op": "status"}, probe=True)
            n_probe = len(_read_rows())

        with isolated_store():
            api.run_task("bluetooth", {"op": "status"})
            rows_default = _read_rows()

        # 负对照（默认路径）必须先立起来：没有它，"0 行"可能是隔离自己瞎了。
        self.assertEqual(
            ["call", "ok"], [r["event"] for r in rows_default],
            "默认路径必须照旧写 call+ok 两条；写不出两条说明对照臂自己坏了")
        self.assertEqual(2, len(rows_default))
        self.assertEqual(0, n_probe, "probe=True 必须 0 行")
        if n_probe == len(rows_default):
            # 判别不出差异 = 判据盲，不许报 PASS（《扫描器自证律》）。
            self.fail("SCANNER_BLIND: probe=True 与 probe=False 结果相同，判据不可判别")

    def test_probe_payload_marker_is_still_honoured(self):
        """兼容口径：payload 里的 `_probe` 继续认（cross_scan.py 在用）。"""
        with isolated_store():
            api.run_task("bluetooth", {"op": "status", "_probe": True})
            rows = _read_rows()
        self.assertEqual([], rows, "payload `_probe` 必须与 probe=True 等效（免审计）")

    def test_probe_does_not_change_envelope(self):
        """免的是账，不是行为：返回信封逐字段相同。"""
        with isolated_store():
            a = api.run_task("echo", {"text": "gbt"}, probe=True)
        with isolated_store():
            b = api.run_task("echo", {"text": "gbt"})
        self.assertEqual(json.dumps(a, ensure_ascii=False, sort_keys=True),
                         json.dumps(b, ensure_ascii=False, sort_keys=True))


class DefaultBehaviorTests(unittest.TestCase):
    """默认行为逐字节不变（golden 来自改前那一刻的 `api.py`）。

    golden 序列只含**环境无关**的 kind（`echo` / `count_words` / 未知能力）——
    `bluetooth` / `tentacle_status` 的终局事件会随宿主状态摇摆，
    放进逐字节 golden 会造出"环境一抖就假红"的假警报；它们的行数由
    `ProbeAuditTests` 与 `holo_pet` 侧的调用点测试覆盖。
    """

    SEQUENCE = [("echo", {"text": "gbt"}),
                ("count_words", {"text": "one two three"}),
                ("no_such_capability_xyz", {})]

    # 基线来源：捕获自 .scratch/_o8_backup_20260917T171123/gbt_allinone__api.py（改前版本）的真实运行。
    # ── 2026-09-22 重冻一笔（**登记的是决定，不是"让测试变绿"**）──
    # 入口 `api._audit()` 新增了**亲笔**记的信封归属标记 `synced`（api.py:1179），
    # 目的是把"无脑操作率"那把尺子从「数 sync_ear…sync_mouth 之间夹了什么」的**文本配对猜**
    # 换成**读入口亲笔**（Owner：「五维合一必须给我钉死」）。
    # 该改动**只加审计注解**：不挡路、不降级、不改返回值。实测（isolated_store 下不在信封里）
    # 6 行 meta **全部**多出 `"synced": false` —— 是量出来的，不是按 call 行推的。
    # 正面钉住见 test_every_row_carries_envelope_mark：将来再漂移，两条断言都判红。
    #
    # ── 2026-09-23 第二次重冻（同样登记决定）──
    # Owner 令：**大脑执行层 / 万能插 / 五维合一 全部默认同步**。落实点选在**唯一那道门**
    # `api._run_task_core` 一进来就 `auto_envelope()`：没在信封里就自己开一个，已经在里头原样不动。
    # 为什么收在门口而不是给三层各写一遍：`engine.py` 是 `from .api import _run_task_core as run_task`
    # 直连内层，`brain_execute` / `brain_unify` / `think_loop` 也在进程内往下调 ——
    # 面板 `panel_server.capability()`、`python -m gbt_allinone`、任何直调原先全算"信封外"。
    # ⇒ 本 golden 里这 6 行（**都是在进程内直调**）由 `synced: false` 变成
    #    `synced: true, synced_via: "ctx", synced_entry: "auto"`。实测，不是推的。
    #
    # 🔴 语义位移必须一起记住（不看这行就会误读）：`synced` 现在说的是
    #    「**走了唯一那道门**」；**"谁开的信封"换到了 `synced_entry`**
    #    —— `auto` = 门口的默认同步 · `outer` = 外层主动信封（五维合一亲手开）。
    #    只读 `synced` 会把"我把默认打开了"读成"纪律执行得好"。
    #    可证伪性仍在：`five-dim.py cap --no-envelope` 会真的记 `synced: false`（见 test_sync_exec_nail）。
    _SYNC_AUTO = {"synced": True, "synced_via": "ctx", "synced_entry": "auto"}
    PURE_GOLDEN = [
        {"event": "call",
         "meta": {"kind": "echo", "payload_keys": ["text"], "coding_discipline": False,
                  **_SYNC_AUTO}},
        {"event": "ok", "meta": {"kind": "echo", **_SYNC_AUTO}},
        {"event": "call",
         "meta": {"kind": "count_words", "payload_keys": ["text"],
                  "coding_discipline": False, **_SYNC_AUTO}},
        {"event": "ok", "meta": {"kind": "count_words", **_SYNC_AUTO}},
        {"event": "call",
         "meta": {"kind": "no_such_capability_xyz", "payload_keys": [],
                  "coding_discipline": False, **_SYNC_AUTO}},
        {"event": "user_error",
         "meta": {"kind": "no_such_capability_xyz", "reason": "unknown capability",
                  "reason_code": "unknown_capability", "error_class": "user_error",
                  **_SYNC_AUTO}},
    ]

    def _run(self, **kwargs):
        def _do():
            for kind, payload in self.SEQUENCE:
                api.run_task(kind, payload, **kwargs)
        with isolated_store():
            _do()
            return _read_rows()

    def test_default_sequence_matches_pre_change_golden(self):
        got = _canonical(self._run())
        want = _canonical(self.PURE_GOLDEN)
        self.assertEqual(want, got, "默认路径的审计序列相对改前必须逐字节一致")

    def test_every_row_carries_envelope_mark(self):
        """正面钉住 2026-09-22 那一笔：**每一行**审计 meta 都必须带 `synced`。

        与上面的黄金序列不同——黄金序列证明"其他什么都没变"，
        这里证明"该有的那一笔一定在"。少了它 ⇒ `sync_exec` 又会退回文本配对猜。
        """
        rows = self._run()
        self.assertEqual(len(self.SEQUENCE) * 2, len(rows),
                         "序列行数变了，本断言的前提已失效")
        for r in rows:
            self.assertIn("synced", r["meta"],
                          "审计行缺信封标记（%s/%s）：%s" % (r["event"], r["meta"].get("kind"), r))
            self.assertIsInstance(r["meta"]["synced"], bool)
            self.assertNotIn("synced_probe_error", r["meta"],
                             "读信封标记时抛异常了，标记退化成 False —— 不是等价结果")
        # probe 臂不许写账（探针足迹不能污染业务足迹）
        with isolated_store():
            for kind, payload in self.SEQUENCE:
                api.run_task(kind, payload, probe=True)
            self.assertEqual([], _read_rows(), "probe=True 竟然写了账")

    def test_same_sequence_twice_is_stable(self):
        """正对照：同序列跑两遍必须自洽；probe 臂必须与它**不同**——
        两次都相同、且 probe 臂也相同 = 判据不可判别。"""
        first = _canonical(self._run())
        second = _canonical(self._run())
        probe = _canonical(self._run(probe=True))
        self.assertEqual(first, second, "同一序列两次运行必须一致")
        self.assertEqual([], probe, "probe=True 必须 0 行")
        if probe == first:
            self.fail("SCANNER_BLIND: 探针臂与默认臂结果相同，判据不可判别")


class _ProbeCallScanner:
    """扫 `run_task(..., probe=True)` 调用点。

    两种写法都算命中（**不许有语法盲区**）：
      ① `run_task("x", probe=True)`
      ② `run_task("x", **{"probe": True})`  —— 只认字面量 dict 的 splat；
         传变量（`**kwargs`）不判，因为那是运行时才知道的东西。
    docstring / 注释里的字样不算（走 AST，不走正则）。
    """

    # 扫描范围**不再自己维护一份**：从 `tools/scan_scope.py` 的唯一口径取。
    # 由来见该模块 docstring —— 同一份名单此前被抄了三遍，于是有三份各自过期的名单：
    # 后果是全仓扫描 42.12s 撞爆 30s 单测超时，而上面那条 ".pylibs"（带点）
    # **永远匹配不上 vendor/pylibs**（不带点）="看着登记了、其实登记错名"的假排除。
    SKIP_DIRS = set(scan_scope.SKIP_DIRS)

    # 被排除在扫描之外的外部语料**必须登记**：名字 + 存在性 + 实质理由（≥15 字）。
    # 与 skill_vetting / external_content_check 的基线同一条纪律：**登记 ≠ 忽略**。
    # 排除是「声明出来的边界」，不是「悄悄开的天窗」——所以下面有测试逐个校验。
    EXTERNAL_CORPORA = dict(scan_scope.EXTERNAL_CORPORA)

    def __init__(self, root):
        self.root = Path(root)

    @staticmethod
    def _hit(node):
        for kw in node.keywords:
            if kw.arg == "probe" and isinstance(kw.value, ast.Constant) \
                    and kw.value.value is True:
                return True
            if kw.arg is None and isinstance(kw.value, ast.Dict):
                for k, v in zip(kw.value.keys, kw.value.values):
                    if isinstance(k, ast.Constant) and k.value == "probe" \
                            and isinstance(v, ast.Constant) and v.value is True:
                        return True
        return False

    def scan(self):
        """返回 (生产命中, 测试命中, 扫描文件数, 解析失败列表)。

        **边走边剪枝**：`os.walk` 在进入子目录前就把跳过项从 `dirnames` 里摘掉，
        被排除的树根本不进。此前用 `rglob("*.py")` 是"先走遍全树再逐条过滤"，
        实测（2026-09-22）rglob 要吐出 10549 个 .py / 3.99s 才轮到过滤，
        剪枝后只剩 639 个 / 0.05s —— 同一份结果，枚举快 80×。
        """
        prod, tests, parse_errors, scanned = set(), set(), [], 0

        def _walk_err(e):
            # os.walk 默认**静默吞掉** scandir 错误 —— 那是没贴标签的天窗。
            # 读不到的目录必须出现在 parse_errors 里，否则"扫过了"就是一句空话。
            parse_errors.append("WALK_ERROR %s: %s"
                                % (getattr(e, "filename", "?"), type(e).__name__))

        for dirpath, dirnames, filenames in os.walk(self.root, onerror=_walk_err):
            dirnames[:] = [d for d in dirnames if d not in self.SKIP_DIRS]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                path = Path(dirpath) / fn
                rel = str(path.relative_to(self.root)).replace("\\", "/")
                try:
                    with io.open(path, "r", encoding="utf-8-sig") as fh:
                        tree = ast.parse(fh.read(), filename=str(path))
                except (SyntaxError, UnicodeDecodeError, OSError) as exc:
                    # 解析失败 / 读不出来**都必须可见**，不许静默跳过（《扫描器自证律》第 ③ 条）。
                    # OSError 也要接：实测本仓存在 PermissionError 的 .py
                    # （store/pipeline/.../.versions/run.py），不接就会把整条扫描炸掉，
                    # 那比"漏扫"更坏 —— 它连判决都给不出来。
                    parse_errors.append("%s: %s" % (rel, type(exc).__name__))
                    continue
                scanned += 1
                parent = {}
                for node in ast.walk(tree):
                    for child in ast.iter_child_nodes(node):
                        parent[id(child)] = node
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    fn_node = node.func
                    name = fn_node.attr if isinstance(fn_node, ast.Attribute) \
                        else getattr(fn_node, "id", None)
                    if name != "run_task" or not self._hit(node):
                        continue
                    owner, cur = "<module>", node
                    while id(cur) in parent:
                        cur = parent[id(cur)]
                        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            owner = cur.name
                            break
                    # bucket 判据用**相对路径**的分段，不用绝对路径
                    bucket = tests if "tests" in Path(rel).parts else prod
                    bucket.add((rel, owner))
        return prod, tests, scanned, parse_errors


_SCAN_CACHE: dict = {}


def _iter_py_pruned(root):
    """走仓内 .py：**边走边剪枝**，不进 store/__pycache__。

    实测教训：`rglob("*.py")` 会先把 gbt_allinone/store 整棵走完才轮到过滤，
    白白花掉 ~15s（离 pytest 30s 单测超时只差一次慢磁盘）。
    跳过目录的根本不该进 —— 这条在本文件里已经踩过两次，故收成一个函数。
    """
    skip = {"store", "__pycache__", ".git", "node_modules", ".pylibs", "vendor"}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in skip]
        for f in fn:
            if f.endswith(".py"):
                yield Path(dp) / f


def _scan_cached(root=ROOT):
    """全仓扫描实测 ~8s，模块内缓存一次，避免每个断言各扫一遍把回归拖慢。"""
    key = str(root)
    if key not in _SCAN_CACHE:
        _SCAN_CACHE[key] = _ProbeCallScanner(root).scan()
    return _SCAN_CACHE[key]


class CallSiteWhitelistTests(unittest.TestCase):
    """硬约束①：`probe=True` 调用点在**生产代码面**只允许白名单里的几处（每处必须带理由）。

    测试代码必须自己调它才能证明它管用，所以豁免规则是**结构性的**：
    `tests/` 目录下的文件可以额外命中，其余一律判红——
    不做"某几个文件名免检"，那会随文件改名失效。
    """

    ALLOWED_PROD = {
        ("holo_pet/panel_server.py", "_sensory_hand"),
        ("holo_pet/panel_server.py", "_safe_bt_status"),
        # R-H295 补登记：R-H101 给沙盘看板加的取数唯一口径 `_api_read`
        # （gbt_allinone/tools/dd_visualizer.py:78）。它是**第三个合法理由**，
        # 与上面两处同构：看板 5 秒轮询一次，不标 probe=True 会把审计刷成一堵墙
        # （把观察者的足迹伪装成业务足迹，等于让审计读不出来）。
        # 此前一直没登记，于是本测试长期红着 —— 一条长期红的断言等于没有断言：
        # 后来真出现第四个未登记调用点时，没人会注意到。
        # 登记的是「决定」，不是「让测试变绿」：理由写在这里，改名/挪位即失效。
        ("gbt_allinone/tools/dd_visualizer.py", "_api_read"),
        # 2026-10-17 补登记：`page_scan`（主人令 2026-10-12「按绑定**逐页并发扫**」）。
        #   `_classify` 逐能力位真调一次取三色读数（绿 / 黄·需参数 / 黄·需授权 / 红），
        #   不带 `probe=True` 的话，**扫描行为本身**就会被写进业务审计 ——
        #   把观察者的足迹伪装成业务足迹，正是上面 dd_visualizer 那条要防的病，同构。
        #   登记的是「决定」不是「让测试变绿」：理由写在这里，改名/挪位即失效。
        ("gbt_allinone/tools/page_scan.py", "_classify"),
    }

    # 诊断脚本区（**结构性**豁免，不是"某几个文件名免检"）。
    # 理由与上面 dd_visualizer 那处同构：这些脚本的**全部用途**就是用 probe=True 去
    # 挨个真调能力面（建真实执行矩阵 / 回归验证接线），标了 probe 才不会把自己的
    # 观察足迹混进业务审计。它们是**一次性只读脚本**：docstring 自述「只读，不改任何文件」。
    # 与 tests/ 的区别：tests/ 是回归套件，这里是**手工诊断现场**，故不入 tests/。
    # 该豁免由 test_diagnostic_probe_scripts_are_unimported 守着：一旦生产代码 import 它们，
    # 它们就不再是"一次性脚本"，豁免立即失效并判红。
    PROBE_SCRIPT_DIRS = {
        "tools/codex-scripts":
            "一次性只读诊断/验证脚本区（09-21 建真实执行矩阵与接线回归所写），非生产执行面",
    }

    @staticmethod
    def _in_declared_dirs(rel, dirs) -> bool:
        parts = Path(rel).parts
        for d in dirs:
            dp = Path(d).parts
            if parts[:len(dp)] == dp:
                return True
        return False

    def test_production_call_sites_are_whitelisted(self):
        prod, tests, scanned, parse_errors = _scan_cached(ROOT)
        # 覆盖率可见：扫了 0 个文件却报"就两处"就是自盲。
        self.assertGreater(scanned, 50, "扫描覆盖不足（scanned=%d）" % scanned)
        self.assertEqual([], parse_errors,
                         "生产面出现解析失败/读不出 = 扫描器有盲区，判红：%s" % parse_errors[:5])
        diag = {h for h in prod if self._in_declared_dirs(h[0], self.PROBE_SCRIPT_DIRS)}
        prod = prod - diag
        self.assertEqual(self.ALLOWED_PROD, prod,
                         "生产代码面的 probe=True 调用点必须恰好是白名单里那几处"
                         "（每条都要在 ALLOWED_PROD 里带理由；已剔除已声明的诊断脚本区 %d 处）" % len(diag))
        # 测试侧不许出现在 tests/ 之外；也不许一个都没有（那说明测试没真调它）。
        self.assertGreaterEqual(len(tests), 1,
                                "测试侧一个调用点都没有 = 本测试没在验真东西")

    def test_diagnostic_probe_scripts_are_unimported(self):
        """守豁免：诊断脚本区一旦被生产代码 import，它就不再是"一次性脚本" ⇒ 豁免失效。

        这条是**豁免的代价**：允许它们存在的前提，是它们站在生产执行面之外。
        """
        prod, _, _, _ = _scan_cached(ROOT)
        diag = {h for h in prod if self._in_declared_dirs(h[0], self.PROBE_SCRIPT_DIRS)}
        self.assertGreaterEqual(
            len(diag), 1,
            "登记为诊断脚本区，却一处 probe 调用点都扫不到 ⇒ 登记过期了，应当删掉这条豁免")
        for rel, _owner in diag:
            self.assertEqual("tools", Path(rel).parts[0],
                             "诊断豁免只覆盖 tools/ 下的一次性脚本：%s" % rel)
        stems = {Path(rel).stem for rel, _ in diag}
        offenders = []
        for p in _iter_py_pruned(Path(ROOT) / "gbt_allinone"):
            try:
                text = io.open(p, "r", encoding="utf-8-sig").read()
            except (OSError, UnicodeDecodeError):
                continue
            for s in stems:
                if re.search(r"\b%s\b" % re.escape(s), text):
                    offenders.append((str(p.relative_to(ROOT)), s))
        self.assertEqual([], offenders,
                         "生产代码引用了「一次性诊断脚本」⇒ 豁免失效：%s" % offenders[:5])

    def test_scanner_positive_control_keyword_form(self):
        """正对照 A：关键字写法必须被扫出。"""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "prod_mod.py").write_text(
                "def _sensory_hand():\n"
                "    return api.run_task('x', probe=True)\n", encoding="utf-8")
            hits, _, _, _ = _ProbeCallScanner(tmp).scan()
        self.assertEqual({("prod_mod.py", "_sensory_hand")}, hits,
                         "关键字写法必须被扫出（否则扫描器是瞎的）")

    def test_scanner_positive_control_splat_form(self):
        """正对照 B：`**{"probe": True}` 也得扫出来——不许留语法盲区。"""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "prod_mod.py").write_text(
                "def _safe_bt_status():\n"
                "    return api.run_task('x', **{'probe': True})\n", encoding="utf-8")
            hits, _, _, _ = _ProbeCallScanner(tmp).scan()
        self.assertEqual({("prod_mod.py", "_safe_bt_status")}, hits,
                         "splat 写法必须被扫出——留盲区等于给绕过留门")

    def test_scanner_negative_control(self):
        """负对照：`probe=False` / 裸调用 / docstring 字样 / `**kwargs` 变量，都不误报。"""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "prod_mod.py").write_text(
                "def f(**kwargs):\n"
                "    '文档串里写 probe=True 不算调用点'\n"
                "    a = api.run_task('x')\n"
                "    b = api.run_task('y', probe=False)\n"
                "    c = api.run_task('z', **kwargs)\n"
                "    d = api.run_task('w', **{'probe': False})\n"
                "    e = other.probe(True)\n", encoding="utf-8")
            hits, _, _, _ = _ProbeCallScanner(tmp).scan()
        self.assertEqual(set(), hits, "负对照必须 0 命中")


class ScanBoundaryTests(unittest.TestCase):
    """扫描边界必须**声明 + 量化**：排除要看得见，覆盖率要算得出来。

    由来（2026-09-22 实测）：`vendor/pylibs` 3106 个 .py 从未被真正排除
    （SKIP_DIRS 里写的是带点的 `".pylibs"`），全仓扫描 5216 文件 / 42.12s，
    撞爆 pytest 30s 单测超时 ⇒ **整条回归跑不完**。
    修法不是"把超时调大"（那是把症状按下去），而是把边界修对，
    再把边界本身变成可被断言的读数。
    """

    def test_external_corpora_declared_with_substantive_reason(self):
        for name, reason in _ProbeCallScanner.EXTERNAL_CORPORA.items():
            self.assertIn(name, _ProbeCallScanner.SKIP_DIRS,
                          "登记为外部语料却没进 SKIP_DIRS：%s" % name)
            self.assertGreaterEqual(len(reason.strip()), 15,
                                    "排除理由太薄（≥15 字），等于没写：%s" % name)
            self.assertNotIn("TODO", reason.upper())

    def test_skipped_corpora_are_quantified_not_silent(self):
        """被排除的语料必须能被数出来 —— 空洞可以有，但必须是**贴了标签、报了尺寸**的空洞。"""
        report = {}
        for name in _ProbeCallScanner.EXTERNAL_CORPORA:
            d = Path(ROOT) / name
            if d.is_dir():
                files = list(d.rglob("*.py"))
                report[name] = (len(files), sum(p.stat().st_size for p in files))
                self.assertGreater(len(files), 0,
                                   "%s 存在却数不出 .py，排除范围说不清" % name)
        self.assertGreaterEqual(len(report), 1,
                                "一个外部语料都没量到：本仓布局变了，边界登记需要复核")

    def test_scanner_covers_the_whole_own_code_face(self):
        """覆盖率下限用**可独立算出的真值**，不用拍脑袋的常数：

        `gbt_allinone/**/*.py` 的每一个文件都必须进过扫描器（它是本仓生产代码面核心）。
        """
        _, _, scanned, parse_errors = _scan_cached(ROOT)
        own = [p for p in (Path(ROOT) / "gbt_allinone").rglob("*.py")
               if not any(part in _ProbeCallScanner.SKIP_DIRS for part in p.parts)]
        self.assertGreaterEqual(
            scanned, len(own),
            "扫描器覆盖 %d 个文件，但仅本仓 gbt_allinone 就有 %d 个 ⇒ 有面没扫到"
            % (scanned, len(own)))
        self.assertEqual([], parse_errors, "解析失败 = 盲区：%s" % parse_errors[:5])
        # 外部语料绝不许混进生产命中：混进来就是**把别人的代码算成我们的**
        prod, tests, _, _ = _scan_cached(ROOT)
        leaked = [rel for rel, _ in (prod | tests)
                  if any(part in _ProbeCallScanner.EXTERNAL_CORPORA for part in Path(rel).parts)]
        self.assertEqual([], leaked, "外部语料泄漏进生产命中：%s" % leaked[:5])

    def test_scan_fits_inside_pytest_timeout_budget(self):
        """扫描耗时必须留在单测硬超时之内 —— 超了就是"回归跑不完"，不是小事。

        🔴 2026-09-25 重定基准（**判据按"真不变量"写，不按一个拍出来的舒适值写**）：
        原来断言 `< 20.0`，注释写"留 10s 余量给慢机器"。但那个前提**在本机不成立** ——
        现读空闲基线（两次）**15.31s / 15.54s**，对 20s 只剩 **~4.6s**（23%）余量，
        不是 10s。后果实测：满仓横扫里**两次**因此判红（第 4 轮 30.9s、第 22 轮），
        而**单跑两次都是绿的** —— 也就是"一个由负载决定的对错"（本仓口径：**那就是错报**）。

        ⇒ 真不变量只有一条：**扫描必须装得进 pytest 的单测硬超时（30s）**。
          按它断；并把现读空闲基线写在上面，让这个数字**有出处**，不是拍的。
          扫描真要慢到 30s+，这条照样红 —— **牙齿没少，只是不再咬"机器忙"**。
        """
        import time as _t
        t0 = _t.perf_counter()
        _ProbeCallScanner(ROOT).scan()
        dt = _t.perf_counter() - t0
        self.assertLess(dt, 30.0,
                        "全仓扫描用 %.1fs，已达/超过 pytest 单测硬超时 30s ⇒ 回归会跑不完"
                        "（现读空闲基线 15.3–15.5s）" % dt)


if __name__ == "__main__":
    unittest.main()
