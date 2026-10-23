# -*- coding: utf-8 -*-
"""判据 · **入口契约与「没跑到 ≠ 跑失败」** · 2026-10-21 立。

## 为什么要有这条（两次真实的假账）

第一次真跑 `one_key_deploy`（房间落点）时，回执是：

    scan 3/3 · rehearse=False · blockers=['静态推演未全绿', "未通过验收命令: ['py-syntax-sweep']"]

两条都是假账的引信：

  ① **入口契约只认一份手抄的字面量**。`room_space.scan` / `room_space.simulate` /
     `qiankun._deploy_into_room` **各抄了一遍** `("index.html","main.py","app.py","start.ps1")`；
     而 `simulate` 更狠：它只看计划里声明的 `architecture.entrypoints`，**根本没看树**。
     于是任何没手填 entrypoints 的计划，静态推演第 4 关**永远**报“未声明入口”，
     而且读数不说该怎么办 ⇒ 调用方只能一遍遍重试、白烧一次性票。
  ② **`rehearse` 把「命令一次都没跑」写成「未通过验收命令」**。它的执行条件是
     `if execute and not blockers`：静态推演一红就**跳过全部验收命令**，可回执里
     把没跑的用例照样列进 `未通过`。于是同一次失败被记成两笔，看起来像坏了两处。

## 它咬什么（四条，都要有牙）

  1. 树里有入口、计划没声明 ⇒ `simulate` 的 `entrypoints` **必须绿**，且 detail 明写
     “入口未声明，按树内识别”（不能靠放宽判据混过去：它仍要求**真有一个入口**）。
  2. 树里没有任何入口 ⇒ 必须红，且 detail 把可识别名报出来（不叫人猜）。
  3. 静态未过 ⇒ `rehearse` 的 blocker 必须是**「验收命令未执行」**，并带跳过原因，
     且 `commands_skipped=True`；**反向断言**：不许出现 “未通过验收命令”
     —— 这一条是负控，防本判据对“跑失败”也放行。
  4. `qiankun._deploy_into_room` 对着没有入口的树必须**当场如实拒绝**，
     不再立一份永远过不了的计划；对着有入口的树必须**真跑通全链**
     （stage → plan → scan → rehearse → release），release 后房间现实区里有那份 index.html。

## 口径

每个用例在**独立子进程 + 临时 store**（`GBT_STORE_DIR`）里跑，绝不碰生产 store；
`GBT_STORE_DIR` 只在 import 时刻读一次（`_paths.py` O53 甲案的绑定快照），所以必须换进程。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_BOOT = r"""
import json, sys
sys.path.insert(0, r"{root}")
"""

_PLAN = r"""
plan = {{
  "goal": "入口契约判据房间",
  "assumptions": [{{"id": "A1", "statement": "同主机同运行时",
                    "verify": "environment.production.mode=same_host"}}],
  "architecture": {{"components": [{{"id": "artifact", "responsibility": "产物树",
                                   "depends_on": []}}],
                    "entrypoints": [], "data_flow": []}},
  "steps": [{{"id": "S1", "action": "固化指纹", "depends_on": []}},
            {{"id": "S2", "action": "跑验收命令", "depends_on": ["S1"]}}],
  "files": {files},
  "environment": {{"required": [], "dependencies": [], "tools": ["python"],
                   "required_files": [], "production": {{"mode": "same_host"}}}},
  "rehearsal": {{"commands": [{{"id": "echo-ok",
                              "argv": [sys.executable, "-c", "print('ok')"],
                              "timeout": 60}}],
                 "acceptance": ["echo-ok"]}},
  "rollback": {{"strategy": "room_snapshot_replay", "note": "回滚到上一快照"}},
}}
"""


def _run(body: str) -> dict:
    """在独立子进程 + 临时 store 里跑一段程序，取它打印的最后一坨 JSON。"""
    with tempfile.TemporaryDirectory(prefix="gbt_entry_") as store:
        env = dict(os.environ)
        env["GBT_STORE_DIR"] = store
        env["PYTHONIOENCODING"] = "utf-8"
        env.pop("GBT_HOME", None)
        code = _BOOT.format(root=str(ROOT)) + body
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(ROOT), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180,
        )
        if proc.returncode != 0:
            raise AssertionError(
                "子进程非零退出 rc=%s\nstdout:\n%s\nstderr:\n%s"
                % (proc.returncode, proc.stdout[-3000:], proc.stderr[-3000:])
            )
        tail = proc.stdout.strip().splitlines()
        for line in reversed(tail):
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
        raise AssertionError("子进程没打印 JSON：\n%s" % proc.stdout[-3000:])


# ── 用例 1/2：静态推演对入口的两面（有入口要绿、没入口要红且报名字）────────────
def _prog(body: str) -> str:
    """把用例主体加上引导（把仓根塞进 sys.path）。"""
    return _BOOT.format(root=str(ROOT)) + body


_WITH_ENTRY = _prog(r"""
from gbt_allinone import room_space as RS
import json, sys
RS.create("entry-a")
RS.shape("entry-a", "index.html", "<!doctype html><title>a</title>")
RS.define_plan("entry-a", %s)
sim = RS.simulate("entry-a")
print(json.dumps({"sim_ok": sim["ok"], "entry_check": sim["checks"]["entrypoints"]},
                 ensure_ascii=False))
""" % (_PLAN.format(files='["index.html"]'),))

_WITHOUT_ENTRY = _prog(r"""
from gbt_allinone import room_space as RS
import json, sys
RS.create("entry-b")
RS.shape("entry-b", "notes.md", "# 只有文档，没有入口")
RS.define_plan("entry-b", %s)
sim = RS.simulate("entry-b")
rh = RS.rehearse("entry-b")
print(json.dumps({"sim_ok": sim["ok"],
                  "entry_check": sim["checks"]["entrypoints"],
                  "rehearse_ok": rh["ok"],
                  "blockers": rh["blockers"],
                  "commands_skipped": rh.get("commands_skipped"),
                  "skip_reason": rh.get("commands_skip_reason"),
                  "commands": rh.get("commands")}, ensure_ascii=False))
""" % (_PLAN.format(files='["notes.md"]'),))

_ROOM_WITH_ENTRY_FULL = _prog(r"""
from gbt_allinone import room_space as RS
import json, sys
RS.create("entry-c")
RS.shape("entry-c", "index.html", "<!doctype html><title>c</title>")
RS.define_plan("entry-c", %s)
sim = RS.simulate("entry-c")
rh = RS.rehearse("entry-c")
print(json.dumps({"sim_ok": sim["ok"], "rehearse_ok": rh["ok"],
                  "blockers": rh["blockers"],
                  "commands_skipped": rh.get("commands_skipped"),
                  "commands": rh.get("commands")}, ensure_ascii=False))
""" % (_PLAN.format(files='["index.html"]'),))

_QK_NO_ENTRY = _prog(r"""
from gbt_allinone import qiankun as Q
from pathlib import Path
import json, tempfile
tgt = Path(tempfile.mkdtemp(prefix="qk_noentry_"))
(tgt / "notes.md").write_text("# 没入口", encoding="utf-8")
res = Q._deploy_into_room("qk-noentry", str(tgt), "判据：无入口", "qk-noentry")
print(json.dumps({"ok": res.get("ok"), "error": res.get("error"),
                  "steps": res.get("steps")}, ensure_ascii=False))
""")

_QK_WITH_ENTRY = _prog(r"""
from gbt_allinone import qiankun as Q, room_space as RS
from pathlib import Path
import json, tempfile
tgt = Path(tempfile.mkdtemp(prefix="qk_entry_"))
(tgt / "index.html").write_text("<!doctype html><title>rel</title>", encoding="utf-8")
(tgt / "README.md").write_text("# 说明", encoding="utf-8")
res = Q._deploy_into_room("qk-entry", str(tgt), "判据：有入口", "qk-entry")
reality_index = RS._ROOT / "qk-entry" / "reality" / "index.html"
print(json.dumps({"ok": res.get("ok"), "steps": res.get("steps"),
                  "error": res.get("error"),
                  "reality_has_index": reality_index.exists()},
                 ensure_ascii=False))
""")


class TestEntryContractHasTeeth(unittest.TestCase):

    def test_entry_found_in_tree_even_if_plan_declares_none(self):
        """① 树里有入口 ⇒ 静态推演必须绿（此前这里必红：只认计划里的 entrypoints）。"""
        out = _run(_WITH_ENTRY)
        self.assertTrue(out["sim_ok"], out)
        self.assertTrue(out["entry_check"]["ok"], out)
        self.assertIn("按树内识别", out["entry_check"]["detail"])

    def test_no_entry_is_red_and_names_what_counts(self):
        """② 树里没入口 ⇒ 必须红，而且要把可识别名报出来（不叫人猜）。"""
        out = _run(_WITHOUT_ENTRY)
        self.assertFalse(out["sim_ok"], out)
        self.assertFalse(out["entry_check"]["ok"], out)
        for name in ("index.html", "main.py", "app.py", "start.ps1"):
            self.assertIn(name, out["entry_check"]["detail"])

    def test_skipped_commands_are_not_reported_as_failed(self):
        """③ 静态未过 ⇒ 报「没跑到」，不许报「跑失败」（带负控）。"""
        out = _run(_WITHOUT_ENTRY)
        self.assertFalse(out["rehearse_ok"], out)
        self.assertTrue(out["commands_skipped"], out)
        self.assertTrue(out["skip_reason"], out)
        self.assertEqual(out["commands"], [], "静态未过就不该真跑命令")
        joined = "\n".join(out["blockers"])
        self.assertIn("验收命令未执行", joined)
        self.assertNotIn("未通过验收命令", joined,
                         "负控：没跑过就不许写成未通过")

    def test_green_room_actually_runs_the_command(self):
        """正控：入口齐了，验收命令必须**真跑**并判绿（否则上面两条只是形状对）。"""
        out = _run(_ROOM_WITH_ENTRY_FULL)
        self.assertTrue(out["sim_ok"], out)
        self.assertTrue(out["rehearse_ok"], out)
        self.assertFalse(out["commands_skipped"], out)
        self.assertEqual([c.get("id") for c in out["commands"]], ["echo-ok"], out)
        self.assertTrue(out["commands"][0].get("ok"), out)

    def test_qiankun_refuses_tree_without_entry_instead_of_lying(self):
        """④ 没有入口 ⇒ 当场如实拒绝，且错误里说清怎么办。"""
        out = _run(_QK_NO_ENTRY)
        self.assertFalse(out["ok"], out)
        self.assertIn("没有可识别的入口", out["error"] or "")
        self.assertIn("index.html", out["error"] or "")

    def test_qiankun_room_route_runs_whole_chain(self):
        """正控：有入口 ⇒ 全链真跑通（stage → plan → scan → rehearse → release）。"""
        out = _run(_QK_WITH_ENTRY)
        self.assertTrue(out["ok"], out)
        steps = out["steps"]
        for name in ("stage", "plan", "scan", "rehearse", "release"):
            self.assertTrue(steps.get(name, {}).get("ok"), (name, steps))
        self.assertTrue(out["reality_has_index"], "晋升后房间现实区里必须有入口页")


if __name__ == "__main__":
    unittest.main()
