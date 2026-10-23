# -*- coding: utf-8 -*-
"""判据 · **房间原语必须真在门上**（F12 防回退）· 2026-10-18 立。

## 为什么要有这条

2026-10-18 实锤的断口：`room_space.py` 里 `simulate / parity / rehearse / release / scan /
sync / status / snapshot` 八个原语**早就实现**，但 `api.py` 的 `kind == "room_space"` 分支
**从不路由它们** ⇒ 门永远跑不到。后果不是"少个功能"，而是：

    room_space.gate() 永远报「没有房间排练报告」 ⇒ 「排练 → 盖章 → 原子替换」这条正路
    在门上走不完 ⇒ 模型只能回到生产面上直接涂改（那次事故就是这么来的）。

同族已记在台账 F12：「能力注册表没有收录一整套真在生产上跑、真过门、真能成功的操作」。

## 它咬什么（三件事，都要有牙）

  1. **模块有的、门上就得有**：从 `room_space.py` 里扫出全部公开函数，
     断言每一个都能在 `api.py` 的 room_space 分支里找到 `_rs.<name>(` 调用。
     ⇒ 以后谁再加一个原语却忘了接线，这条当场红（而不是等门报"未知 op"）。
  2. **`_known` 名单与真分支同源**：`_known` 里的 op 必须真有一个 `if op == "<op>"` 分支，
     反之亦然（防"名单写着能做、其实没接"—— 那正是 2026-10-09 那条护照的同型病）。
  3. **负控（判据自己不许恒真）**：`observe` / `registry` / `resolve` / `replay` 这几个
     **有意不路由**（会写全局视觉总线 / 是命名空间内部件）⇒ 断言它们**不在**路由里。
     如果本判据对什么都说"接了"，第三项就会红。

## 口径

只读：读两份源码，不写盘、不起进程。`GBT_API_PY` / `GBT_ROOM_PY` 环境变量可替换被量的文件
（用于"对着候选件先量一遍"的排练，不改生产也能验）。
"""
from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = Path(os.environ.get("GBT_API_PY") or (ROOT / "gbt_allinone" / "api.py"))
ROOM = Path(os.environ.get("GBT_ROOM_PY") or (ROOT / "gbt_allinone" / "room_space.py"))

# 必须被路由的原语（房间那条"排练 → 盖章 → 原子替换"闭环用到的全在这里）
REQUIRED = ("create", "enter", "shape", "define_plan", "get_plan", "scan",
            "simulate", "parity", "rehearse", "gate", "release",
            "sync", "status", "snapshot", "namespace", "frame")
# 有意**不**路由（每条都有理由；负控用）。改了这张表就等于改口径，必须写明。
EXEMPT = {
    "observe": "会把帧推到**全局视觉总线**共享给所有房间 —— 不经主人点头不接",
    "registry": "命名空间注册表的内部件（给 _register_namespace 用），不是房间动作",
    "resolve": "同一族：把 FQN 解析成房间路径的内部件",
    "replay": "快照回放目前只给内部/人读用，没进闭环；要接先补验收口径",
    "shape_bytes": "二进制落盘（逐字节）；走 JSON 需要 base64 载荷契约，本轮不接",
}
NOT_ROUTED = tuple(EXEMPT)


def _api_room_branch() -> str:
    src = API.read_text(encoding="utf-8", errors="replace")
    i = src.find('if kind == "room_space"')
    if i < 0:
        raise AssertionError("api.py 里找不到 room_space 分支（它被改名/删了？）")
    j = src.find('if kind == "collab_gateway"', i)
    return src[i:j if j > 0 else i + 8000]


def _public_room_functions() -> set:
    src = ROOM.read_text(encoding="utf-8", errors="replace")
    return {m.group(1) for m in re.finditer(r"^def (\w+)\(", src, re.M)
            if not m.group(1).startswith("_")}


class RoomOpsWiredTest(unittest.TestCase):
    def test_every_public_room_primitive_is_routed(self) -> None:
        """模块有的原语，门上必须都能调到 —— 除了 EXEMPT 里点名豁免的。"""
        branch = _api_room_branch()
        routed = set(re.findall(r"_rs\.(\w+)\(", branch))
        pub = _public_room_functions()
        self.assertTrue(pub, "room_space.py 里一个公开函数都没扫到（路径不对？）")
        missing = sorted(pub - routed - set(EXEMPT))
        self.assertEqual([], missing,
                         "room_space 里有这些原语、但 api.py 没路由，也不在豁免表里"
                         " ⇒ 门跑不到它们：%s" % missing)

    def test_required_loop_primitives_are_routed(self) -> None:
        """闭环必需的那几个，逐个点名（比"全部都在"更早给出人话）。"""
        branch = _api_room_branch()
        routed = set(re.findall(r"_rs\.(\w+)\(", branch))
        missing = [op for op in REQUIRED if op not in routed]
        self.assertEqual([], missing,
                         "「排练 → 盖章 → 原子替换」闭环缺这些 op：%s" % missing)

    def test_known_list_matches_real_branches(self) -> None:
        """`_known` 名单不许比真分支多（多了＝名单撒谎），也不许少。"""
        branch = _api_room_branch()
        m = re.search(r"_known = \[([^\]]+)\]", branch, re.S)
        self.assertIsNotNone(m, "api.py 的 room_space 分支里找不到 _known 名单")
        listed = set(re.findall(r'"(\w+)"', m.group(1)))
        branches = set(re.findall(r'if op == "(\w+)"', branch))
        self.assertEqual(sorted(listed - branches), [],
                         "名单里有、但没有真分支（名单撒谎）：%s" % sorted(listed - branches))
        self.assertEqual(sorted(branches - listed), [],
                         "有分支、但名单里没写（门报可用 op 时会漏）：%s" % sorted(branches - listed))

    def test_negative_control_not_routed_stay_not_routed(self) -> None:
        """负控：有意不接的那几个，必须仍然不接 —— 否则本判据是在"什么都说接上了"。"""
        branch = _api_room_branch()
        routed = set(re.findall(r"_rs\.(\w+)\(", branch))
        leaked = [op for op in NOT_ROUTED if op in routed]
        self.assertEqual([], leaked,
                         "这些原语有意不路由（写全局视觉总线/内部件），却被接上了：%s" % leaked)


if __name__ == "__main__":
    unittest.main(verbosity=2)
