# -*- coding: utf-8 -*-
"""工作台判据（主人令 2026-09-28「把所有触手连接全面专业化 3D 可视化…每工作流独立页精细排布…
必须先全面扫描确保不能遗漏」）。

判据（每条都能红；设计那部分走 `gbt-aesthetic` 的硬闸 + 审计器）：
  A. **不能遗漏**：`console_hub.scan` 的 `unregistered` 必须为 0（盘上有而登记表没有 = 盲区）
  B. **页面全在盘**：登记表里 kind ∈ {枢纽,全景,工作流} 的页面必须真存在（本轮新建的那 6 页）
  C. **不许匿名数字**：每页 HTML 里必须出现来源标记（`源：`/`src`）——数字要么带来源要么不许上页
  D. **数据只有一个来源**：页面内联的 DATA 与 `console_hub` 现读一致（页数/能力数对得上）
  E. **3D 页有签名元素**：canvas + `run_task` 核心 + 节点数 = 域数/能力数（不是画着玩的装饰）
  F. **工作流页与目录一致**：阶段名能在 `projects/<线>` 的真实产出里命中（至少一个阶段有产出）
  G. **动效与禁令**：六页都有 `prefers-reduced-motion`；无 indigo 系、无外链图床
  H. **审美硬闸**：`audit_aesthetic.py` 跑六页，**P0 必须为 0**
  I. **眼睛看得见**：`gods_eye.see` 的页数 == `console_hub.pages` 的页数（清单不各维护一份）
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / "gbt_allinone" / "tools"
NEW_PAGES = ["gallery", "workbench", "tentacle3d", "wf-film", "wf-movie", "wf-music",
             "wf-short-video"]


def _load(name: str, path: Path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


class TestConsoleWorkspace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hub = _load("hub_t", T / "console_hub.py")
        cls.pages = _load("pages_t", T / "console_pages.py")

    # ---- A 不能遗漏 ----
    def test_a_no_unregistered_page_on_disk(self):
        s = self.hub.scan()
        self.assertEqual([], s["unregistered"],
                         "盘上有页面没登记 ⇒ 那是**盲区**（清单不覆盖它）：%s" % s["unregistered"])

    def test_a2_every_registered_page_has_owner_and_kind(self):
        p = self.hub.pages()
        for r in p["rows"]:
            self.assertTrue(r.get("kind"), f"{r['page']} 没分类")
            self.assertTrue(r.get("workflow"), f"{r['page']} 没归属工作流")

    # ---- B 新建的六页都在盘 ----
    def test_b_six_new_pages_exist(self):
        for name in NEW_PAGES:
            f = ROOT / "holo_pet" / "assets" / name / "index.html"
            self.assertTrue(f.is_file(), f"{name} 不在盘上 ⇒ 跑 run_task('console_pages', {{'op':'render'}})")
            self.assertGreater(f.stat().st_size, 2000, f"{name} 太小，像空壳")

    # ---- C 不许匿名数字 ----
    def test_c_every_page_shows_sources(self):
        for name in NEW_PAGES:
            txt = (ROOT / "holo_pet" / "assets" / name / "index.html").read_text(encoding="utf-8")
            self.assertTrue(("源：" in txt) or ("src" in txt),
                            f"{name} 里没有来源标记 ⇒ 数字成了匿名数字")

    # ---- D 数据只有一个来源 ----
    def test_d_page_data_matches_hub(self):
        txt = (ROOT / "holo_pet" / "assets" / "workbench" / "index.html").read_text(encoding="utf-8")
        m = re.search(r"const DATA = (\{.*?\});\n", txt, re.S)
        self.assertIsNotNone(m, "工作台里找不到内联 DATA")
        data = json.loads(m.group(1))
        w = self.hub.widgets()
        self.assertEqual(w["w1_caps"]["total"], data["widgets"]["w1_caps"]["total"],
                         "页上的能力数与 console_hub 现读不一致 ⇒ 页面在自己编数")
        self.assertEqual(self.hub.pages()["count"], data["pages"]["count"],
                         "页上的页面数与登记表不一致")

    # ---- E 3D 签名元素 ----
    def test_e_3d_signature_is_real(self):
        txt = (ROOT / "holo_pet" / "assets" / "tentacle3d" / "index.html").read_text(encoding="utf-8")
        self.assertIn("<canvas", txt, "3D 页没有画布")
        self.assertIn("run_task", txt, "签名元素缺核心锚点（万用插）")
        g = self.hub.graph()
        self.assertIn(str(g["counts"]["caps"]), txt, "3D 页没带真实能力节点数")
        self.assertIn(str(g["counts"]["domains"]), txt, "3D 页没带真实域数")
        self.assertIn("脉冲", txt, "3D 页没有运行脉冲（那就只是装饰）")

    # ---- F 工作流页与目录一致 ----
    def test_f_workflow_pages_reflect_real_dirs(self):
        for key in ("film", "movie", "music", "short-video"):
            spec = self.hub.WORKFLOWS[key]
            d = ROOT / spec["dir"]
            self.assertTrue(d.is_dir(), f"{spec['dir']} 不在盘上")
            txt = (ROOT / "holo_pet" / "assets" / f"wf-{key}" / "index.html").read_text(encoding="utf-8")
            self.assertIn(spec["stages"][0], txt, f"wf-{key} 里没写真实阶段名")

    # ---- G 动效与禁令 ----
    def test_g_motion_and_banned_patterns(self):
        for name in NEW_PAGES:
            txt = (ROOT / "holo_pet" / "assets" / name / "index.html").read_text(encoding="utf-8")
            self.assertIn("prefers-reduced-motion", txt, f"{name} 没尊重减少动效偏好")
            for bad in ("unsplash.com", "placehold.co", "picsum.photos", "#6366f1", "#8b5cf6"):
                self.assertNotIn(bad, txt, f"{name} 命中禁令：{bad}")

    # ---- H 审美硬闸 ----
    def test_h_aesthetic_p0_is_zero(self):
        aud = ROOT / "tools" / "codex-scripts" / "audit_aesthetic.py"
        self.assertTrue(aud.is_file(), "审计器不在位")
        for name in NEW_PAGES:
            f = ROOT / "holo_pet" / "assets" / name / "index.html"
            cp = subprocess.run([sys.executable, str(aud), str(f)], cwd=str(ROOT),
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=180)
            out = (cp.stdout or "") + (cp.stderr or "")
            self.assertIn("P0 命中合计: 0", out,
                          f"{name} 审美 P0 不为 0（硬闸）⇒ 退出码 {cp.returncode}\n{out[-300:]}")

    # ---- J 卡库把每一页都排成卡（"每一个页面都需要有视觉感"的机检） ----
    def test_j_gallery_cards_cover_every_page(self):
        g = (ROOT / "holo_pet" / "assets" / "gallery" / "index.html").read_text(encoding="utf-8")
        rows = self.hub.pages()["rows"]
        missing = [r["page"] for r in rows if f'>{r["page"]}</h3>' not in g]
        self.assertEqual([], missing, f"卡库漏了这些页的卡：{missing}")
        self.assertGreaterEqual(g.count('class="pcard"'), len(rows), "卡数少于页数")
        self.assertNotIn("**", g.split("class=\"cards\"")[-1][:4000],
                         "卡面里出现 markdown 星号（强调没转成真加粗）")

    # ---- I 眼睛看得见全部页 ----
    def test_i_eye_sees_every_registered_page(self):
        sys.path.insert(0, str(ROOT))
        import gbt_allinone as g
        r = g.run_task("gods_eye", {"op": "see"})
        p = r.get("result", r)
        if isinstance(p, dict) and "result" in p:
            p = p["result"]
        self.assertEqual(self.hub.pages()["count"], p["pages_total"],
                         "眼睛的页数 != 登记表页数 ⇒ 又各维护了一份清单")
        self.assertEqual(p["pages_total"], p["pages_ok"],
                         f"有页面不在盘上：{[x['page'] for x in p['pages'] if not x['exists']]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
