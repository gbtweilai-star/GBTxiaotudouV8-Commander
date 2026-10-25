"""云端点闸（`deploy/cloud-10/tools/check-endpoint-gate.mjs`）本身也要被守着。

被测对象是**本机离线**就能跑的那道闸，它盖的是 worker.js 里 2026-09-25 那 4 批改动 ——
那 4 批正是「她一句话都答不出来」的直接病根，而且因为**没部署**，云端一次都没跑过：
  ① 令牌闸（多令牌 / 常数时间 / 没配就如实说「不校验」）
  ② `/v1/models` 按作用面读数（老版一句「令牌闸已开」比事实大）
  ③ `normalizeMessages`：上游只认 `content` 字符串，块数组必须拍平
  ④ 错误分档（5021 上下文超窗 ≠ 4006 配额 ≠ 配置没填 ≠ 通用上游故障）

判据（六条，都要有牙）：
  1. node 运行体在不在 —— **不在就是红，不许记成跳过**（少了它这 4 批无法验）；
  2. 闸跑完必须退出码 0（任何一条 FAIL 都不许被吞）；
  3. `--json` 的读数自洽：`total > 0`、`failed == 0`、每行都有 name/pass/reading 三件套；
  4. **负控不许被删**（至少 10 条名字含「负控」的行都在，且都通过）——
     这是本仓的老坑：「条数不等于牙齿」，把负控删掉条数照样好看；
  5. 离线是真的：闸的源码里不许出现真出网原语（`await fetch(` / node:http / node:https / node:net）；
  6. 四批**各自都还有判据组**（不许悄悄删组把覆盖缩水）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "deploy" / "cloud-10" / "tools" / "check-endpoint-gate.mjs"

# 四批各自的可辨认锚（判据名/读数里必须出现；删组就会在这条上红）
BATCH_ANCHORS = {
    "① 令牌闸": "GBT_ENDPOINT_TOKENS",
    "② 作用面读数": "auth_scope",
    "③ 拍平块数组": "拍平",
    "④ 错误分档": "5021",
}


class EndpointGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.node = shutil.which("node")
        cls.proc: subprocess.CompletedProcess | None = None
        cls.rows: list[dict] = []
        if cls.node and GATE.exists():
            cls.proc = subprocess.run(
                [cls.node, str(GATE), "--json"],
                cwd=str(ROOT), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=240,
            )
            try:
                cls.rows = json.loads(cls.proc.stdout)["rows"]
            except Exception:
                cls.rows = []

    # ① node 运行体 —— 缺了算红，不算跳过
    def test_node_runtime_is_present(self) -> None:
        self.assertIsNotNone(
            self.node,
            "本机没有 node ⇒ 云端那 4 批改动**无法验**；缺工具算红，不许记成『跳过』",
        )

    def test_gate_file_exists(self) -> None:
        self.assertTrue(GATE.exists(), "端点闸文件不在：%s" % GATE)

    # ② 退出码：任何 FAIL 都不许被吞
    def test_gate_exits_zero(self) -> None:
        self.assertIsNotNone(self.proc, "闸没跑起来（见上一条）")
        assert self.proc is not None
        if self.proc.returncode != 0:
            bad = [r["name"] for r in self.rows if not r.get("pass")]
            self.fail("端点闸有红：rc=%s · %s\nstderr=%s"
                      % (self.proc.returncode, " / ".join(bad[:8]), self.proc.stderr[-600:]))

    # ③ 读数自洽
    def test_json_readout_is_self_consistent(self) -> None:
        self.assertTrue(self.rows, "拿不到 --json 读数（stderr=%s）"
                        % (self.proc.stderr[-300:] if self.proc else ""))
        total = len(self.rows)
        failed = [r for r in self.rows if not r.get("pass")]
        self.assertGreater(total, 20, "判据条数少得不像话：%d" % total)
        self.assertEqual(failed, [], "有红：%s" % [r["name"] for r in failed][:8])
        for r in self.rows:
            for k in ("name", "pass", "reading"):
                self.assertIn(k, r, "行缺字段 %s：%r" % (k, r))
            self.assertTrue(str(r["reading"]).strip(), "行的 reading 是空的：%s" % r["name"])

    # ④ 负控不许被删 —— 「条数不等于牙齿」
    def test_negative_controls_are_present_and_green(self) -> None:
        neg = [r for r in self.rows if "负控" in r["name"]]
        self.assertGreaterEqual(
            len(neg), 10,
            "负控只剩 %d 条（<10）⇒ 判据被削牙了：把「该红的必须红」删掉，条数照样好看" % len(neg),
        )
        self.assertEqual([r["name"] for r in neg if not r["pass"]], [],
                         "负控自己红了 —— 那就是被测行为真的坏了")

    # ⑤ 离线是真的：源码里不许有真出网原语
    def test_gate_is_offline_by_source(self) -> None:
        src = GATE.read_text(encoding="utf-8")
        for bad in ("await fetch(", "require(\"http", "from \"node:http", "from \"node:https",
                    "from \"node:net", "from 'node:http", "from 'node:https"):
            self.assertNotIn(bad, src, "闸里出现出网原语 %s ⇒ 「离线」这句话不成立" % bad)

    # ⑥ 四批覆盖不许缩水
    def test_four_batches_each_keep_a_judgment_group(self) -> None:
        names = " ".join(r["name"] for r in self.rows)
        src = GATE.read_text(encoding="utf-8")
        for label, anchor in BATCH_ANCHORS.items():
            self.assertIn(anchor, src, "%s 的锚 %s 在闸源码里没了" % (label, anchor))
            self.assertTrue(
                any(anchor in r["name"] or anchor in r["reading"] for r in self.rows),
                "%s（锚 %s）在读数里一条判据都没有 ⇒ 这一批没被盖到" % (label, anchor),
            )
        # ⚠️ 自纠：`--json` 模式**故意不打**总结行（人读才打）——
        #    第一版我拿 JSON stdout 去断总结行，是判据写错了，不是闸坏了。
        #    正确的判据：两份读数（人读总结行 / 机读 total+failed）都得在源码里存在。
        self.assertIn("端点闸本机验收", src, "人读总结行不见了")
        self.assertGreaterEqual(len(self.rows), 20, "机读读数条数不对")


if __name__ == "__main__":
    unittest.main()
