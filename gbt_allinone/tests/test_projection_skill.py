# -*- coding: utf-8 -*-
"""空间投射技能只读卡片的契约测试（R-H108 · 第 1 步）。

锁四件事：
  ① 卡片是**只读定义**：5 条原语全标"未核实"，且模块源码里**没有任何执行/写路径**
     （不靠口号 —— 直接查源码，同 `dig_snapshot` / `ring_snapshot` 那两条的查法）；
  ② 红线写在卡片里：**ARM ≠ LIVE**（准备态永不点亮 · GO LIVE 只能操作者按键 · 硬件门禁未全绿不 LIVE）；
  ③ 清单里只放**引用**：两处对不上 = 漂移 ⇒ 如实报出来（**含喂坏负对照**，证明这条有牙）；
  ④ 沙盘只呈现：`/api/data` 带卡片、页面有卡片钩子，且**没有任何写入口**。
"""
from __future__ import annotations

import contextlib
import inspect
import io
import json
import socketserver
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import dd_visualizer as DD  # noqa: E402
from gbt_allinone.tools import projection_skill as PS  # noqa: E402

MANIFEST = ROOT / ".cluster" / "dd_squad" / "toolchain_manifest.json"


class ProjectionCardTests(unittest.TestCase):
    # ── ① 卡片诚实：5/5 未核实 ──────────────────────────────────────────
    def test_card_marks_every_primitive_unverified(self):
        card = PS.skill_card()
        self.assertIs(card["readonly"], True)
        self.assertIs(card["verified"], False, "硬件门禁一次都没跑过，卡片不许自报已核实")
        self.assertEqual(card["primitive_count"], 5)
        self.assertEqual(card["unverified_count"], 5, "5 条原语必须**全**标未核实")
        self.assertEqual([p["key"] for p in card["primitives"]],
                         ["CAPTURE", "MASK", "MAP", "FUSE", "OUTPUT"])
        for p in card["primitives"]:
            self.assertEqual(p["status"], PS.UNVERIFIED)
            self.assertTrue(p["why_unverified"].strip(), f"{p['name']} 标了未核实却没说为什么")
            self.assertTrue(p["layer"].strip(), f"{p['name']} 没归到层")
            self.assertTrue(p["upstream"].strip() and p["downstream"].strip())
        self.assertTrue(card["honest_status_note"].strip())
        self.assertTrue(card["execution"].strip())

    # ── ② 红线：ARM ≠ LIVE ─────────────────────────────────────────────
    def test_arm_is_not_live(self):
        card = PS.skill_card()
        phases = {p["key"]: p for p in card["phases"]}
        self.assertEqual(set(phases), {"ARM", "LIVE"})
        self.assertIs(phases["ARM"]["lights_screen"], False,
                      "准备态**永不点亮** —— 这是红线，不是文案")
        self.assertIs(phases["LIVE"]["lights_screen"], True)
        self.assertIn("按钮", phases["LIVE"]["who_can_enter"])
        joined = " ".join(card["constraints"])
        self.assertIn("ARM ≠ LIVE", joined)
        self.assertIn("按钮", joined)
        self.assertIn("硬件门禁未全绿", joined)
        # 同构口径：LIVE ≈ 生产写入 · 按键 ≈ 授权门（Owner 定的口径类比）
        self.assertIn("授权门", card["gate_analogy"]["operator_button"])
        self.assertIn("生产写入", card["gate_analogy"]["LIVE"])

    # ── ①b 只读是查得出来的，不是自称的 ────────────────────────────────
    def test_module_has_no_execution_or_write_path(self):
        src = inspect.getsource(PS)
        for bad in ("run_task(", "_api_read(", "os.remove", "shutil", "subprocess",
                    "write_text", "write_bytes", "urlopen", "socket", "os.system"):
            self.assertNotIn(bad, src, f"只读卡片里出现了执行/写路径：{bad}")
        self.assertNotIn("from gbt_allinone", src, "只读卡片不该导入能力层")
        self.assertNotIn("import gbt_allinone", src, "只读卡片不该导入能力层")

    def test_card_is_json_serializable_and_the_cli_prints_it(self):
        card = PS.skill_card()
        self.assertIn("ARM ≠ LIVE", json.dumps(card, ensure_ascii=False))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = PS.main(["--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue()), card, "CLI 打出来的必须与卡片逐字段一致")
        human = "\n".join(PS.render_lines(card))
        self.assertIn("未核实", human)
        for p in card["primitives"]:
            self.assertIn(p["name"], human)

    # ── ③ 清单只放引用；漂移必须报出来 ────────────────────────────────
    def test_manifest_holds_exactly_one_reference_without_drift(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = [r for r in (data.get("skills") or [])
                if r.get("source_of_truth") == DD.PROJECTION_MODULE]
        self.assertEqual(len(rows), 1, "清单里必须**只有一条**引用（多了就是两处真相）")
        row, card = rows[0], PS.skill_card()
        self.assertEqual(row["status"], card["status"])
        self.assertEqual(int(row["primitives"]), card["primitive_count"])
        self.assertIs(row["verified"], False)
        self.assertIs(row["readonly"], True)
        self.assertTrue((ROOT / row["source_of_truth"]).is_file(), "引用指向的文件不在盘上")
        self.assertTrue(str(row.get("registered_by") or "").strip(), "登记必须能追到护照")

    def test_drift_is_reported_when_manifest_disagrees(self):
        """喂坏负对照：造一份"清单说已核实 / 原语 3 条"的假清单 ⇒ 必须报漂移。"""
        with tempfile.TemporaryDirectory(prefix="gbt_proj_drift_") as tmp:
            root = Path(tmp)
            squad = root / ".cluster" / "dd_squad"
            squad.mkdir(parents=True)
            (squad / "toolchain_manifest.json").write_text(json.dumps({
                "skills": [{"source_of_truth": DD.PROJECTION_MODULE, "status": "已核实",
                            "primitives": 3, "verified": True}]}, ensure_ascii=False),
                encoding="utf-8")
            snap = DD.projection_snapshot(root)
            self.assertIs(snap["registered_in_manifest"], True)
            joined = "；".join(snap["drift"])
            self.assertIn("状态漂移", joined)
            self.assertIn("原语条数漂移", joined)
            self.assertIn("核实状态漂移", joined)
            # 卡片本身以**定义**为准：仍然 5/5 未核实（清单说好话也不许跟着走）
            self.assertEqual(snap["unverified_count"], 5)
            self.assertIs(snap["verified"], False)
            self.assertEqual(snap["card"]["status"], PS.UNVERIFIED)

    def test_sandbox_reports_missing_manifest_not_invented(self):
        with tempfile.TemporaryDirectory(prefix="gbt_proj_") as tmp:
            snap = DD.projection_snapshot(Path(tmp))
            self.assertTrue(snap["ok"], "卡片本体来自包内模块，清单缺失不该把卡片也装死")
            self.assertIs(snap["registered_in_manifest"], False)
            self.assertTrue(snap["manifest_note"].strip(), "没登记就如实说，不许沉默")
            self.assertEqual(snap["unverified_count"], 5)
            self.assertIs(snap["readonly"], True)

    def test_sandbox_card_on_the_real_tree_is_readonly_and_unverified(self):
        snap = DD.projection_snapshot(ROOT)
        self.assertTrue(snap["ok"], snap)
        self.assertIs(snap["readonly"], True)
        self.assertIs(snap["verified"], False)
        self.assertEqual(snap["primitive_count"], 5)
        self.assertEqual(snap["unverified_count"], 5)
        self.assertIs(snap["registered_in_manifest"], True, "清单里登记了，沙盘却说没登记")
        self.assertEqual(snap["drift"], [], "卡片与清单漂移了：%s" % snap["drift"])

    # ── ④ 沙盘只呈现 ────────────────────────────────────────────────────
    def test_page_has_projection_card_and_stays_readonly(self):
        page = DD._PAGE
        for needle in ('id="projpanel"', 'id="proj"', "drawProjection", "ARM ≠ LIVE",
                       "GO LIVE 只能操作者按钮", "未核实", "只呈现 · 不执行"):
            self.assertIn(needle, page, f"页面缺少空间投射钩子：{needle}")
        self.assertNotIn("POST", page)
        self.assertFalse(hasattr(DD.Handler, "do_POST"), "Handler 不许有写入口")

    def test_server_serves_projection_card(self):
        with tempfile.TemporaryDirectory(prefix="gbt_proj_srv_") as tmp:
            root = Path(tmp)
            (root / ".cluster" / "dd_squad").mkdir(parents=True)
            DD.Handler.root = root
            srv = socketserver.TCPServer(("127.0.0.1", 0), DD.Handler)
            port = srv.server_address[1]
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/data", timeout=10) as r:
                    data = json.loads(r.read().decode("utf-8"))
                proj = data["projection"]
                self.assertIs(proj["readonly"], True)
                self.assertEqual(proj["unverified_count"], 5)
                # 隔离树里没有清单 ⇒ 必须**如实报"没登记"**，不许编一份顶上
                self.assertIs(proj["registered_in_manifest"], False)
                self.assertTrue(proj["manifest_note"].strip())
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as r2:
                    page = r2.read().decode("utf-8")
                self.assertIn('id="projpanel"', page)
                self.assertIn("空间投射", page)
                self.assertNotIn("POST", page)
            finally:
                srv.shutdown()
                srv.server_close()


if __name__ == "__main__":
    unittest.main()
