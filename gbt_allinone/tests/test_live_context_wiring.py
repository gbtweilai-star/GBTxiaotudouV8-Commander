r"""「三块会话上下文**真的进了进程**」这条尺子自己的判据（第 53 轮 · F18）。

立它的理由（一手账，代价 10 小时）：

  · 宿主半边（`plugins/gbt-master/lib/host.js`）**只在进程启动时装载**，而注入上下文是
    每次开新会话喂给模型的第一段字；
  · 台账块（`gbt-progress-ledger`）2026-09-25 21:03:15 加进宿主半边，**版本号没跟着动**
    （仓库自己的规矩写在 host.js 里：「每次改宿主半边必须动这个版本号」）；
  · 进程是 2026-09-25 10:33:32 启动的 ⇒ **进程里根本没有台账块**；
  · 而验收单 ① 读「进程 1.8.1 == 源稿 1.8.1」判 ✅。
  · 用 Cordis 探针现读进程内已注册上下文（`systemPrompt.assemble()`），只有 4 块：
    `sandbox:policy` / `approval:policy` / `gbt-master-panels` / `gbt-digital-human`。
    ⇒ 主人要的「重启之后自动读取」**一直没生效**，而所有闸全绿。

根因不是"漏了一个块"，是**所有闸都从盘上渲染，没有一条问过进程**。所以这一组判据守的是那条
"问进程"的路：宿主自报 `contexts` · 验收单 ⑨ 比对 · 且**两边的名单不许各写一份**。
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "plugins" / "gbt-master" / "lib" / "host.js"
SHEET = ROOT / "plugins" / "gbt-master" / "tools" / "verify-after-restart.py"
INSTALLED = (Path.home() / ".dsh" / "profiles" / "web" / "node_modules"
             / "gbt-potato-master-v9" / "lib" / "host.js")

# host.js 里注册会话上下文的调用点：`ctx.systemPrompt.context({ name: '…', order: N, … })`
_REG = re.compile(r"systemPrompt\.context\(\{\s*\n\s*name:\s*'([^']+)',\s*\n\s*order:\s*(\d+)")
# 验收单里期望的名单
_EXPECT = re.compile(r"EXPECT_CONTEXTS\s*=\s*\(([^)]*)\)")


def _registered_in_host() -> dict:
    return {name: int(order) for name, order in _REG.findall(HOST.read_text(encoding="utf-8"))}


def _expected_in_sheet() -> list:
    m = _EXPECT.search(SHEET.read_text(encoding="utf-8"))
    if not m:
        return []
    # 名单里单双引号都认：写死一种引号风格等于给自己埋一个"读不到就当没写"的坑
    return re.findall(r"""['"]([^'"]+)['"]""", m.group(1))


class LiveContextWiringTest(unittest.TestCase):
    """宿主必须**自报**它注册了哪几块 —— 这是唯一一条"问进程"的路。"""

    def test_host_exposes_contexts_in_the_payload(self) -> None:
        src = HOST.read_text(encoding="utf-8")
        self.assertIn("contexts: contextRegistry", src,
                      "/gbt-master 的 payload 必须自报进程内注册成功的上下文名单")

    def test_every_registration_site_is_recorded(self) -> None:
        """注册点与记录点必须**一一对应**：三处注册 ⇒ 三处成功记录 + 三处失败记录。"""
        src = HOST.read_text(encoding="utf-8")
        names = list(_registered_in_host())
        self.assertGreaterEqual(len(names), 3, "至少应有面板/数字人/台账三块：%s" % names)
        ok_calls = re.findall(r"noteContext\('([^']+)',\s*\d+\)", src)
        err_calls = re.findall(r"noteContext\('([^']+)',\s*\d+,\s*err\)", src)
        self.assertEqual(sorted(names), sorted(ok_calls),
                         "注册了却没记录成功：注册点 %s vs 记录点 %s" % (names, ok_calls))
        self.assertEqual(sorted(names), sorted(err_calls),
                         "有注册点没有失败记录 ⇒ 注册抛错时名单会漏报：%s" % err_calls)

    def test_registration_is_wrapped_in_try_catch(self) -> None:
        """每处注册都要包在 try/catch 里 —— 「没进去」与「进去但内容是空的」得分得开。"""
        src = HOST.read_text(encoding="utf-8")
        names = _registered_in_host()
        wrapped = src.count("ctx.effect(() => ctx.systemPrompt.context({")
        self.assertEqual(len(names), wrapped,
                         "注册点 %d 处，包在 ctx.effect 里的只有 %d 处" % (len(names), wrapped))
        # 成功记录与失败记录必须成对：三处注册 ⇒ 三条 ok 记录 + 三条 err 记录
        self.assertEqual(len(re.findall(r"noteContext\('([^']+)',\s*\d+\)", src)), len(names))
        self.assertEqual(len(re.findall(r"noteContext\('([^']+)',\s*\d+,\s*err\)", src)), len(names))
        # 逐处确认：成功记录前面那段窗口里必须出现 catch，否则抛错会被静默吞掉
        for name in names:
            i = src.find("noteContext('%s'" % name)
            self.assertGreater(i, 0, "找不到 %s 的记录点" % name)
            self.assertIn("} catch (err) {", src[max(0, i - 500):i],
                          "%s 这处注册没包 try/catch ⇒ 抛错会被静默吞掉" % name)


class SheetAgreementTest(unittest.TestCase):
    """验收单与实际注册的名单必须**同源**，不许各写一份（写死一次过期一次）。"""

    def test_sheet_expects_exactly_what_host_registers(self) -> None:
        got = set(_registered_in_host())
        want = set(_expected_in_sheet())
        self.assertTrue(want, "验收单里读不到 EXPECT_CONTEXTS")
        self.assertEqual(got, want,
                         "宿主注册的 %s 与验收单期望的 %s 不一致 ⇒ 加了块没人验，或验了不存在的块"
                         % (sorted(got), sorted(want)))

    def test_sheet_reads_contexts_from_the_live_payload(self) -> None:
        src = SHEET.read_text(encoding="utf-8")
        self.assertIn('cat.get("contexts")', src,
                      "⑨ 必须读**活的那份 payload**，不是从盘上渲染 —— 否则又是「盘上对 ≠ 进进程」")

    def test_sheet_item_nine_tells_you_to_restart(self) -> None:
        src = SHEET.read_text(encoding="utf-8")
        self.assertIn("三块上下文进了进程", src)
        self.assertIn("重启", src[src.find("三块上下文进了进程"):][:1200],
                      "⑨ 的说明里要写清「缺了就是宿主代码没换版 ⇒ 重启」")

    def test_conclusion_does_not_hardcode_the_item_count(self) -> None:
        """这张单从 5 项长到 9 项：结论不许写死项数。"""
        src = SHEET.read_text(encoding="utf-8")
        self.assertNotIn("五项都到位", src, "结论里还写着「五项」⇒ 加项后它就在骗人")

    def test_installed_copy_carries_the_field(self) -> None:
        """装机副本（重启后真正加载的那份）也得有 `contexts`，否则改了源稿也白搭。"""
        if not INSTALLED.is_file():
            self.skipTest("装机副本不在：%s" % INSTALLED)
        text = INSTALLED.read_text(encoding="utf-8")
        self.assertIn("contexts: contextRegistry", text,
                      "装机副本没有 contexts ⇒ 跑一遍 verify-installed-copy.mjs --fix")
        self.assertEqual(_REG.findall(text), _REG.findall(HOST.read_text(encoding="utf-8")),
                         "装机副本的注册点与源稿不一致 —— 又是那种「看起来改了、其实没改」")


class VersionDisciplineTest(unittest.TestCase):
    """版本号是"进程跑的是哪一版"的**唯一**现读信号 ⇒ 它不许被漏动。"""

    def test_version_moved_past_the_pre_f18_value(self) -> None:
        src = HOST.read_text(encoding="utf-8")
        m = re.search(r"version:\s*'([\d.]+)'", src)
        self.assertIsNotNone(m, "host.js 里读不到 version")
        got = tuple(int(x) for x in m.group(1).split("."))
        self.assertGreater(got, (1, 8, 1),
                           "F18 之后版本号必须高过 1.8.1（台账块就是在 1.8.1 上偷偷加的）")

    def test_sheet_still_judges_by_the_version(self) -> None:
        src = SHEET.read_text(encoding="utf-8")
        self.assertIn('cat.get("version")', src, "① 必须仍按进程自报的 version 判")


if __name__ == "__main__":
    unittest.main()
