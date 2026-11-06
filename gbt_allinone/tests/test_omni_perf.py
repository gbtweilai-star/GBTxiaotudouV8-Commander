# -*- coding: utf-8 -*-
"""万能插的性能与正确性回归 —— 防止 22 秒悄悄回来，也防止「快但假」再发生。

## 为什么这组测试必须存在

2026-11-04 实测：`surface_audit` 原来每次 **22.2 秒**，cProfile 指认
`socket.connect` 14 次吃掉 20.3 秒 —— 全是在等**不会来的响应**（回环死口 + 回环 HTTP 探活）。
砍掉超时后降到 **6.3 秒**。

但第二次优化时先做出了一个**假的 3.67 秒**：`os` 没 import，`_tcp` 抛 `NameError`
被上层 except 吞掉 ⇒ 所有端口探测失败 ⇒ 少了 8 次 connect ⇒ 快。

**快但假，比慢更坏。**

这是本文件最重要的一条：只测「死口探不到」是不够的 ——
如果探测整体坏掉（全部返 None），那个断言会**全绿**。
所以必须同时测「**在跑的端口探得到**」。缺了这一半，测的就不是探测，是"它闭嘴了"。

## 四类判据（少一类就可能重犯）

  A 正确性   在跑的端口必须探得到 · status/selftest/energy 的形状
  B 超时     死口必须有界返回 · 非回环必须保留长超时 · 未知 socket 不许挂
  C 性能预算 surface_audit 整体 · status / selftest / page_index 各自的预算
  D 留痕     每动一次必须长个儿 · 字段按读侧契约 · 多域监控真的读得到

## 预算怎么来的（不是拍的）

2026-11-04 本机实测 p50：

    status                2.3 ms    → 预算   200 ms
    selftest             39.4 ms    → 预算  1500 ms
    page_index('tactile') 183.8 ms  → 预算  3000 ms
    单次死口探测           64.3 ms   → 上限   500 ms   ← 对齐 guard-three，修复前 1.0s/次
    surface_audit        6583 ms    → 预算 15000 ms   ← 必须远低于修复前的 22200 ms

统一按 10~30× 余量定：够宽到不受机器抖动影响，够窄到抓得住「改慢一个数量级」。
`surface_audit` 那一项太慢（6.6s），CI 提速时可用 `GBT_SKIP_SLOW=1` 跳过 ——
它其余的代表锚点（单次探测）在 B 类里已经钉死。

## 数据依赖

`dead-port` 那几项要用 `tools/omni_discover.py`；它不在时**如实 skip**，不假装通过。
"""
from __future__ import annotations

import inspect
import json
import os
import socket
import statistics
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

# 仓根注入：直跑时 `sys.path[0]` 是 tests 目录，不是仓根。
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 🔴 留痕隔离（2026-11-04）：`state/*/` 被 .gitignore 忽略，但判据跑起来
#   照样往生产流水里写。实测那天 `state/omni-impact.jsonl` 133 行里大半是测试造的
#   （`__绝对不存在的插座__`、连发三条 `status`）—— 真实动作被噪音淹掉。
#   所以这里在**导入之前**把留痕指到临时文件，全程不碰生产。
_LEDGER_TMP = Path(tempfile.gettempdir()) / ("gbt-omni-ledger-%d.jsonl" % os.getpid())
os.environ["GBT_IMPACT_LEDGER"] = str(_LEDGER_TMP)

from gbt_allinone import omni_plug as OP  # noqa: E402

LEDGER = _LEDGER_TMP                     # 断言看这个，不看 state/ 里的生产流水
DISCOVER = ROOT / "tools" / "omni_discover.py"

SLOW = os.environ.get("GBT_SKIP_SLOW") == "1"

# ── 预算 ────────────────────────────────────────────────────────────────────
BUDGET_STATUS_MS = 200.0
BUDGET_SELFTEST_MS = 1500.0
BUDGET_PAGE_INDEX_MS = 3000.0
BUDGET_DEAD_PORT_MS = 500.0        # 与 guard-three 的 check_probe 同口径
BUDGET_SURFACE_AUDIT_S = 15.0      # 必须远低于修复前的 22.2s


def _timed(fn, n=3):
    """跑 n 次取中位数。中位数而非均值：一次 GC 抖动不该让判据红。"""
    ts, out = [], None
    for _ in range(n):
        t0 = time.perf_counter()
        out = fn()
        ts.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(ts), max(ts), out


def _import_discover():
    sys.path.insert(0, str(ROOT / "tools"))
    import omni_discover
    return omni_discover


def _free_port() -> int:
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


class _TempServer:
    """临时 TCP server —— 让「在跑的端口」这件事自给自足，不依赖 8111 有没有起。"""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        self._stop = False
        self.t = threading.Thread(target=self._loop, daemon=True)
        self.t.start()

    def _loop(self):
        while not self._stop:
            try:
                self.sock.settimeout(0.2)
                conn, _ = self.sock.accept()
                conn.close()
            except (socket.timeout, OSError):
                continue

    def close(self):
        self._stop = True
        try:
            self.sock.close()
        except OSError:
            pass


# ══ A + B · 探测：正确性与有界必须一起测 ═══════════════════════════════════
@unittest.skipUnless(DISCOVER.is_file(), "缺 tools/omni_discover.py（探测实现不在本树）")
class TestTcpProbe(unittest.TestCase):
    """A/B · **活口探得到 + 死口有界** —— 这两条一起才有意义。

    只测死口是危险的：探测整体坏掉时（全返 None）死口断言会全绿。
    """

    def setUp(self):
        self.D = _import_discover()

    def test_live_port_probed(self):
        """在跑的端口**必须**探得到（否则就是"快但假"）。"""
        srv = _TempServer()
        try:
            ms = self.D._tcp(srv.port)
            self.assertIsNotNone(ms, "在跑的端口 %d 竟然探不到 —— 探测链路断了"
                                     % srv.port)
            self.assertGreaterEqual(ms, 0)
        finally:
            srv.close()

    def test_dead_port_returns_none(self):
        """死口必须返回 None，不许因为超时太短而当成'在跑'。"""
        self.assertIsNone(self.D._tcp(_free_port()),
                          "死口竟然探到了 —— 探测在返假值")

    def test_dead_port_bounded(self):
        """探死口必须在上限内返回 —— 这就是那 20 秒的来源。"""
        port = _free_port()
        med, worst, got = _timed(lambda: self.D._tcp(port), n=3)
        self.assertIsNone(got)
        self.assertLess(worst, BUDGET_DEAD_PORT_MS,
                        "探死口最坏 %.0fms > 上限 %.0fms —— 超时被改回去了？"
                        "（修复前 1.0s/次 × 14 次 = 20 秒）"
                        % (worst, BUDGET_DEAD_PORT_MS))

    def test_non_loopback_keeps_long_timeout(self):
        """非回环仍用长超时：跨网段 RTT 不可预测，砍了会误判。"""
        src = inspect.getsource(self.D._tcp)
        self.assertIn("1.0", src, "非回环的 1.0s 兜底没了 —— 跨网段会误判成死口")


# ══ A · 应答的形状 ═════════════════════════════════════════════════════════
class TestOmniCorrectness(unittest.TestCase):
    """A · 应答的形状对，不是"能跑"就算过。"""

    def test_status_shape(self):
        """status 必须报名字 / 插座类型 / 口径，且插座类型与派生源一致。"""
        r = OP.run("status")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r.get("名字"), "万能插")
        kinds = list(r.get("插座类型") or [])
        self.assertEqual(kinds, list(OP.SOCKET_KINDS),
                         "status 报的插座类型必须与 SOCKET_KINDS 一致：%r vs %r"
                         % (kinds, list(OP.SOCKET_KINDS)))
        self.assertEqual(len(kinds), len(set(kinds)), "插座类型有重复：%r" % (kinds,))
        for core in ("process", "file", "api", "web", "app"):
            self.assertIn(core, kinds, "核心插座丢了：%s（现读 %r）" % (core, kinds))
        # 口径必须自述「默认面不是穷举」—— 否则读的人会以为就这么几路
        self.assertIn("穷举", str(r.get("插座类型口径") or ""),
                      "status 必须自述「内置默认面不是穷举」：%r"
                      % (r.get("插座类型口径"),))

    def test_selftest_ok(self):
        """selftest 必须自己说 ok，且不许是空壳（要有真检查项）。"""
        r = OP.run("selftest")
        self.assertTrue(r.get("ok"), r)
        self.assertGreaterEqual(len(r), 3, "selftest 回执太薄，像是空壳：%r" % list(r))

    def test_energy_is_readings(self):
        """energy 必须按插座分类报能源观（process 在「插座能源」下面，不在顶层）。"""
        e = OP.energy()
        self.assertIsInstance(e, dict, "energy 必须返回 dict，实得 %r" % type(e))
        self.assertIn("插座能源", e, "能源观必须按插座分类：%r" % list(e))
        by_socket = e.get("插座能源") or {}
        for core in ("process", "file", "api"):
            self.assertIn(core, by_socket, "插座能源缺 %s：%r" % (core, list(by_socket)))
            self.assertTrue(str(by_socket[core]).strip(), "插座能源 %s 是空的" % core)


# ══ B · 未知面不许挂 ═══════════════════════════════════════════════════════
class TestOmniUnknownSocket(unittest.TestCase):
    """B · 判不出的地方必须**有界地**失败，不许挂住或抛未捕获异常。"""

    def test_unknown_socket_fails_fast(self):
        t0 = time.perf_counter()
        try:
            r = OP.run("run", socket="__绝对不存在的插座__", target="x")
        except Exception as e:                                    # noqa: BLE001
            self.fail("未知 socket 抛了未捕获异常（应当如实返回 failed）：%s: %s"
                      % (type(e).__name__, e))
        dt = (time.perf_counter() - t0) * 1000.0
        self.assertFalse(r.get("ok"), "未知 socket 不该假装成功：%r" % (r,))
        self.assertLess(dt, 2000.0, "未知 socket 用了 %.0fms，像是挂住了" % dt)


# ══ C · 性能预算 ═══════════════════════════════════════════════════════════
class TestOmniBudget(unittest.TestCase):
    """C · 每个 op 都有时间上限 —— 防"越改越慢"，不是性能炫耀。"""

    def test_surface_audit_within_budget(self):
        """整体不许超过预算 —— 修前 22.2s，现 6.6s，上限 15s 抓得住回退。"""
        if SLOW:
            self.skipTest("GBT_SKIP_SLOW=1")
        t0 = time.perf_counter()
        r = OP.run("surface_audit")
        dt = time.perf_counter() - t0
        self.assertTrue(r.get("ok"), r.get("error"))
        self.assertLess(dt, BUDGET_SURFACE_AUDIT_S,
                        "surface_audit 花了 %.1fs > 预算 %.1fs —— "
                        "探测超时被改回去了？（修复前是 22.2s）"
                        % (dt, BUDGET_SURFACE_AUDIT_S))

    def test_status_budget(self):
        med, worst, r = _timed(lambda: OP.run("status"), n=5)
        self.assertTrue(r.get("ok"), r)
        self.assertLess(med, BUDGET_STATUS_MS,
                        "status 中位 %.1fms > 预算 %.0fms —— 是不是又去枚举了什么？"
                        % (med, BUDGET_STATUS_MS))

    def test_selftest_budget(self):
        med, worst, r = _timed(lambda: OP.run("selftest"), n=3)
        self.assertTrue(r.get("ok"), r)
        self.assertLess(med, BUDGET_SELFTEST_MS,
                        "selftest 中位 %.1fms > 预算 %.0fms" % (med, BUDGET_SELFTEST_MS))

    def test_page_index_budget(self):
        """带过滤的页索引必须够快（全量扫描 5.5s 另计，不进这条）。"""
        med, worst, r = _timed(lambda: OP.page_index("tactile"), n=3)
        self.assertTrue(r.get("ok"), r)
        self.assertLess(med, BUDGET_PAGE_INDEX_MS,
                        "page_index 中位 %.1fms > 预算 %.0fms"
                        % (med, BUDGET_PAGE_INDEX_MS))


# ══ D · 留痕 ═══════════════════════════════════════════════════════════════
class TestOmniTrace(unittest.TestCase):
    """D · 无痕即未发生：每次动作都要留痕，且字段能被读侧用。"""

    def test_ledger_grows_on_action(self):
        before = LEDGER.stat().st_size if LEDGER.is_file() else 0
        OP.run("energy")
        after = LEDGER.stat().st_size if LEDGER.is_file() else 0
        self.assertGreater(after, before,
                           "跑了一次 energy，留痕没长（%d→%d）—— 写侧又断了"
                           % (before, after))

    def test_status_is_not_ledger_noise(self):
        before = LEDGER.stat().st_size if LEDGER.is_file() else 0
        OP.run("status")
        after = LEDGER.stat().st_size if LEDGER.is_file() else 0
        self.assertEqual(after, before,
                         "纯读 status 也留痕了（%d→%d）—— 空记录会淹掉真实动作"
                         % (before, after))

    def test_ledger_fields_match_reader(self):
        """字段必须按**读侧契约**写（`action`），否则多域监控 recent 里是 null。

        `_sync_impact` 缺失时正是这个症状：留痕写了，但读侧认不出。
        字段名是读写两侧的契约，不是随便起的。
        """
        OP.run("energy")
        with LEDGER.open(encoding="utf-8") as fh:
            last = json.loads(fh.readlines()[-1])
        for k in ("ts", "action", "ok", "ms"):
            self.assertIn(k, last, "留痕缺字段 %r：%r" % (k, sorted(last)))
        self.assertEqual(last["action"], "energy", "留痕的 action 字段不对：%r" % (last,))

    def test_recent_ignores_legacy_status_noise(self):
        from gbt_allinone import api
        if not (ROOT / "state" / "model-pack" / "wiring.json").is_file():
            self.skipTest("图不在本树（state/model-pack/wiring.json 缺）—— needs_build")
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": "2026-11-06T00:00:00", "action": "status",
                                 "op": "status", "socket": "", "target": "",
                                 "ok": True, "error": None, "ms": 0},
                                ensure_ascii=False) + "\n")
        OP.run("energy")
        env = api.run_task("impact_check", {"op": "recent", "n": 10})
        body = env
        for _ in range(6):
            if isinstance(body, dict) and isinstance(body.get("result"), dict):
                body = body["result"]
            else:
                break
        self.assertTrue(body.get("ok"), body)
        self.assertFalse(any((r.get("action") == "status" and not r.get("target"))
                             for r in (body.get("rows") or [])),
                         "recent 仍把历史空 status 当动作：%r" % (body.get("rows"),))


# ══ D · 多域监控自己也要留痕 ═══════════════════════════════════════════════
class TestImpactSelfLogs(unittest.TestCase):
    """多域监控自己必须留痕 —— 主人当场问「我怎么感觉你多域监控没开」。

    血账（2026-11-04）：`impact_check.OPS` 里从来没有"写"这件事，写侧只有
    `omni_plug._sync_impact`。于是一个**只读、不留痕**的监控，
    从外部**看不出它在跑** —— `recent` 里全是万能插的动作，查不到自己的。
    主人的感觉是对的。
    """

    def _graph(self) -> bool:
        return (ROOT / "state" / "model-pack" / "wiring.json").is_file()

    def test_impact_writes_own_trace(self):
        """算过影响面 ⇒ 必须留一行，且 action 与万能插区分得开。"""
        from gbt_allinone import api
        if not self._graph():
            self.skipTest("图不在本树（state/model-pack/wiring.json 缺）—— needs_build")

        before = LEDGER.stat().st_size if LEDGER.is_file() else 0
        api.run_task("impact_check",
                     {"op": "impact", "target": "code:gbt_allinone/api.py", "depth": 1})
        after = LEDGER.stat().st_size if LEDGER.is_file() else 0
        self.assertGreater(after, before,
                           "算完影响面却没留痕 —— 监控从外部看不出在跑")

        last = json.loads(LEDGER.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(last.get("action"), "impact",
                         "action 必须是 impact（与万能插的动作区分）：%r" % (last,))
        self.assertEqual(last.get("who"), "impact_check",
                         "who 字段缺了 —— 读流水时认不出是谁记的：%r" % (last,))

    def test_readonly_ops_do_not_log(self):
        """只读 op 记了只有噪音 —— 会把真实动作淹掉。"""
        from gbt_allinone import api
        if not self._graph():
            self.skipTest("图不在本树")
        for op in ("status", "where", "recent"):
            b = LEDGER.stat().st_size if LEDGER.is_file() else 0
            api.run_task("impact_check", {"op": op})
            a = LEDGER.stat().st_size if LEDGER.is_file() else 0
            self.assertEqual(a, b, "只读 op=%s 也留痕了 —— 噪声会淹掉真实动作" % op)

    def test_ms_is_sane(self):
        """耗时字段必须是合理量级 —— 钉「两个时钟混用」。

        实测踩过：`run_op` 用 `time.perf_counter()` 起算，
        `_say` 里却和 `time.time()`（墙钟）相减 ⇒ `ms: 1793770680699`。
        留痕的耗时全是垃圾，而且**看起来像"很慢"**，会把人引向错误的排查方向。
        """
        from gbt_allinone import api
        if not self._graph():
            self.skipTest("图不在本树")
        api.run_task("impact_check",
                     {"op": "impact", "target": "code:gbt_allinone/api.py", "depth": 1})
        last = json.loads(LEDGER.read_text(encoding="utf-8").splitlines()[-1])
        ms = last.get("ms")
        self.assertIsInstance(ms, int, "ms 必须是整数：%r" % (ms,))
        self.assertGreaterEqual(ms, 0, "ms 不许是负数：%r" % (ms,))
        self.assertLess(ms, 60_000,
                        "ms=%r 明显是墙钟与单调时钟混用（正常应是几十到几百毫秒）" % (ms,))


# ══ D · 两端真的连上 ═══════════════════════════════════════════════════════
class TestImpactSeesOmni(unittest.TestCase):
    """D · 多域监控能读到万能插的留痕 —— 这是「打通没」的唯一判据。"""

    def test_recent_reads_ledger(self):
        from gbt_allinone import api

        def peel(e):
            r = (e or {}).get("result") or {}
            return r.get("result") if isinstance(r.get("result"), dict) else r

        peel(api.run_task("omni_plug", {"op": "energy"}))     # 先留一条真动作
        rc = peel(api.run_task("impact_check", {"op": "recent"}))

        # 🔴 三态口径（2026-11-04 第二次踩）：读不到图 = needs_build，不是接线断了。
        # `state/*/` 被 .gitignore 忽略，wiring.json 只长在跑过初始化的机器上。
        # 开发仓没有它 ⇒ 这条必须 skip，否则这条判据在开发仓恒红，红久了没人看。
        # 真正的「接线断了」是：图在，但 recent 仍读不到留痕。
        err = str(rc.get("error") or rc.get("why") or "")
        if not rc.get("ok") and ("wiring.json" in err or "missing" in err.lower()):
            self.skipTest("图还没建（state/model-pack/wiring.json 不在本树）"
                          " —— 这是 needs_build，不是接线断了：%s" % err[:80])

        self.assertTrue(rc.get("ok"), rc.get("error"))
        self.assertGreater(rc.get("count") or 0, 0,
                           "多域监控 recent 又是 0 —— 万能插留痕没接上")


if __name__ == "__main__":
    unittest.main(verbosity=2)
