"""R-H609（2026-09-25）· **排查台账的字段契约**（Owner 令：「重启之后自动读取」）。

背景（Owner 原话的意思）：
    「你必须要有个习惯：今天做到哪里、哪里没做、问题故障、排查记录以及时间点，
      全部都要记得清清楚楚；重启之后自动读取。」
⇒ 台账 `state/排查台账.json` 由宿主插件 `plugins/gbt-master/lib/host.js` 渲染成会话头的
   第三块上下文（与「总面板」「数字人工作流」同一机制、同一刷新节奏）。

为什么需要这条用例（**渲染器只渲染、不编造**）：
    渲染器对缺字段的处理是**写「（未写）」**——这对人是诚实的，但**对机器是静默的**：
    台账哪天丢了一个 `id` 或 `severity`，注入出来的块照样"看着正常"，只是内容变成占位符。
    ⇒ 所以字段契约必须由**判据**守着，而不是靠"我会记得写"。

判据（四条，都要有牙）：
  1. 台账能解析，且顶层键齐全（`updated_at` / `rounds_done` / `in_progress` / `not_done` /
     `open_faults` / `owner_decisions` / `today_done` / `log`）；
  2. `updated_at` 是**可解析的 ISO 时间**（"时间点"是 Owner 明确要的，不许写成"昨天"）；
  3. 三个清单里每一项都必须有**稳定 id**，`open_faults` 还必须有 `severity`
     （渲染器要读它，缺了就变占位符）；
  4. `log` 每笔都要有 `at`（时间点）与 `what`，且**时间不倒流**（后一笔不早于前一笔）。
"""
from __future__ import annotations

import json
import re
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "state" / "排查台账.json"
HOST_JS = ROOT / "plugins" / "gbt-master" / "lib" / "host.js"

REQUIRED_TOP = ("updated_at", "rounds_done", "in_progress", "not_done",
                "open_faults", "owner_decisions", "today_done", "log")


def _load() -> dict:
    with LEDGER.open(encoding="utf-8") as fh:
        return json.load(fh)


class LedgerContractTest(unittest.TestCase):
    def test_file_exists_and_parses(self) -> None:
        self.assertTrue(LEDGER.is_file(), "台账文件不存在：%s" % LEDGER)
        self.assertIsInstance(_load(), dict)

    def test_required_top_keys(self) -> None:
        led = _load()
        missing = [k for k in REQUIRED_TOP if k not in led]
        self.assertEqual([], missing,
                         "台账缺顶层键：%s ⇒ 注入块会静默变成『（未写）』" % missing)

    def test_updated_at_is_a_real_timestamp(self) -> None:
        raw = str(_load().get("updated_at") or "")
        self.assertTrue(raw, "updated_at 空了 —— 时间点是 Owner 明确要的")
        # 允许 `2026-09-25T18:05:00+08:00` / `2026-09-25 18:05` 两种写法
        text = raw.replace(" ", "T")
        try:
            datetime.fromisoformat(text)
        except ValueError:
            self.fail("updated_at 不是可解析的时间戳：%r（不许写『昨天』这类相对说法）" % raw)

    def test_items_have_stable_ids(self) -> None:
        led = _load()
        for key in ("not_done", "open_faults", "owner_decisions"):
            items = led.get(key) or []
            self.assertIsInstance(items, list, "%s 必须是列表" % key)
            for it in items:
                self.assertIsInstance(it, dict, "%s 里出现非对象项：%r" % (key, it))
                self.assertTrue(str(it.get("id") or "").strip(),
                                "%s 里有一项没有 id（渲染器按 id 点名，缺了就没法引用）" % key)
        for it in led.get("open_faults") or []:
            self.assertTrue(str(it.get("severity") or "").strip(),
                            "未清故障 %s 没写 severity" % it.get("id"))

    def test_log_entries_have_time_and_are_monotonic(self) -> None:
        log = _load().get("log") or []
        self.assertTrue(log, "log 空 —— 台账就退化成一张清单，不是『排查记录』")
        seen = []
        for row in log:
            self.assertTrue(str(row.get("at") or "").strip(), "有记录没写时间点：%r" % row)
            self.assertTrue(str(row.get("what") or "").strip(), "有记录没写做了什么：%r" % row)
            seen.append(row["at"].replace(" ", "T"))
        parsed = [_as_aware(t) for t in seen]
        for a, b in zip(parsed, parsed[1:]):
            self.assertLessEqual(a, b, "排查记录时间倒流：%s → %s" % (a, b))


class InjectionIsWiredTest(unittest.TestCase):
    """台账必须真的被插件读并注入 —— 否则"重启自动读取"只是愿望。"""

    def test_host_js_reads_the_ledger_and_injects_it(self) -> None:
        src = HOST_JS.read_text(encoding="utf-8", errors="replace")
        self.assertIn("state/排查台账.json", src, "插件没去读台账文件")
        self.assertIn("gbt-progress-ledger", src, "插件没注册台账那块注入")
        self.assertRegex(src, re.escape("ctx.systemPrompt.context({"),
                         "没有走既有的 systemPrompt.context 注入机制")
        # 与数字人状态同一条口径：读不到就说读不到，不许猜
        self.assertIn("台账文件读不到", src, "读不到台账时没有如实上报")

    def test_renderer_reads_exactly_the_fields_this_test_guards(self) -> None:
        """渲染器读哪些字段 ⇒ 本文件就守哪些字段（防两边慢慢漂开）。"""
        src = HOST_JS.read_text(encoding="utf-8", errors="replace")
        for field in ("not_done", "open_faults", "owner_decisions", "today_done",
                      "log", "updated_at", "rounds_done", "in_progress"):
            self.assertIn(field, src, "渲染器不再读 %s ⇒ 本用例守的字段该同步改" % field)


class RootCausePatternTableTest(unittest.TestCase):
    """Owner 令 2026-09-28：「知道故障每次都是这么出的，固化登记到记录里面在**大模型必读名单**里面」。

    2026-10-04 查实（本轮一对一追踪发现的真缺陷）：表曾在台账里，但 `host.js` 的
    `renderLedger` **从不读它**（连同基线版也从不读）⇒ 表躺在文件里、**模型永远看不到**
    = P8 型「修复件没接上驱动」的"假必读"。所以这里两条都要咬住：
      ① 台账里表在、条目够、无空条目（防再被换代带走）；
      ② 渲染器必须真读它（接线判据——驱动不读，写了等于没写）。
    """

    def test_table_exists_with_enough_entries(self) -> None:
        pm = _load().get("根因模式表")
        self.assertIsInstance(pm, dict, "台账缺 `根因模式表` 节（又被换代带走？见根因追踪-2026-10-04）")
        entries = [k for k in pm if not str(k).startswith("_")]
        self.assertGreaterEqual(len(entries), 20,
                                "根因模式表条目太少（现 %d 条）—— 该表只许增不许丢" % len(entries))
        empty = [k for k in entries if not str(pm[k]).strip()]
        self.assertEqual([], empty, "有空条目的模式：%s" % empty)

    def test_renderer_really_reads_the_table(self) -> None:
        src = HOST_JS.read_text(encoding="utf-8", errors="replace")
        self.assertIn("function renderLedger", src, "渲染器不在了？")
        body = src.split("function renderLedger", 1)[1]
        self.assertIn("根因模式表", body,
                      "`renderLedger` 体内没读 `根因模式表` ⇒ 必读名单只是愿望（P8 型假必读）")


def _as_aware(t: str):
    """把台账里的时间点**统一成 aware** 再比 —— 因为历史条目里两制混着（第 48 轮 F15 的副产物）。

    - 写了偏移的（`…+07:00` / `…+08:00`）⇒ 就是那个时刻；
    - **没写偏移的**（更早的条目是裸 `2026-09-25T17:05`）⇒ 按「当时当刻的当地墙上时间」理解，
      附上**机器当前本地时区**。这是**近似**：本机旧条目的偏移还写错过（见 F15），
      所以本函数只用来判**顺序**，不用来判"那一刻到底是几点"。
    """
    d = datetime.fromisoformat(t.replace(" ", "T"))
    return d.astimezone() if d.tzinfo is None else d


class TimestampOffsetIsRealTest(unittest.TestCase):
    """🔴 第 48 轮加（F15 的成因就在这里）：**时间点的偏移必须是机器真实偏移，不许是编的**。

    实据（2026-09-26 第 48 轮实测）：本机时区是 **+07:00**（东南亚标准时间），
    而我历轮把台账时间戳写成 `+08:00`，还把 harness 显示的**UTC**当成当地时间
    ⇒ 那些条目**作为绝对时刻约差 8 小时**。
    **为什么一直没被抓到**：上面那条判据只查「时间不倒流」——
    **单调性对 ≠ 时刻对**：一串全部偏移写错的时间戳，顺序照样是单调的。

    ⇒ 本判据只钉**最新一笔**（历史条目不追改，已在 `_口径` 里写明那次缺陷）：
    它的偏移必须是 **机器真实本地偏移** 或 **UTC**，不许是"看起来像那么回事"的编造值。
    """

    def test_latest_log_entry_offset_is_the_machine_offset_or_utc(self) -> None:
        import datetime as dt

        local_off = dt.datetime.now().astimezone().strftime("%z")
        at = str((_load().get("log") or [{}])[-1].get("at") or "")
        m = re.search(r"([+-]\d{2}:?\d{2}|Z)$", at)
        self.assertIsNotNone(m, "最新一笔 log 没写时区偏移（跨机器读就会读错）：%r" % at)
        got = m.group(1).replace(":", "")
        allowed = {local_off, "+0000", "-0000", "Z"}
        self.assertIn(got, allowed,
                      "最新一笔 log 的偏移是 %s，而机器真实偏移是 %s —— "
                      "**编一个偏移比不写偏移更坏**（它看起来是权威的）" % (got, local_off))

    def test_updated_at_offset_is_the_machine_offset_or_utc(self) -> None:
        import datetime as dt

        local_off = dt.datetime.now().astimezone().strftime("%z")
        up = str(_load().get("updated_at") or "")
        m = re.search(r"([+-]\d{2}:?\d{2}|Z)$", up)
        self.assertIsNotNone(m, "`updated_at` 没写时区偏移：%r" % up)
        self.assertIn(m.group(1).replace(":", ""), {local_off, "+0000", "-0000", "Z"},
                      "`updated_at` 的偏移 %s 与机器真实偏移 %s 不符" % (m.group(1), local_off))

    def test_ledger_documents_the_historical_offset_defect(self) -> None:
        """历史条目不追改，但**缺陷必须写在台账里**（否则下一个人会拿旧时间戳当绝对时刻）。"""
        kou = str(_load().get("_口径") or "")
        self.assertIn("+07:00", kou, "台账口径里没写明历史偏移写错这件事（F15）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
