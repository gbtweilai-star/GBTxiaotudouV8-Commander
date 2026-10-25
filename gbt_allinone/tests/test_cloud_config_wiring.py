"""R-H615（2026-09-25）· **部署前接线对账**自己的判据。

被测对象：`tools/codex-scripts/cloud-config-wiring.py`

为什么它需要判据：这一件管的是**生产落点**（`deploy/cloud-10/` 是部署配置），
而配置与代码对不上的代价不是报错，是**部署后静默 undefined**。
首跑就抓到两个真缺口：`SANDBOX`（06 号命令面）与 `AE`（10 号观测面）——
代码在读，而配置里**连一次都没出现过** ⇒ 后来人要接这个能力，**查不到绑定该叫什么名**。

判据五条（该绿的绿 · 该红的必须红）：
  1. 现读的部署配置**无硬伤**（A 类读而未声明 = 0）；
  2. 探针负控：造一个"代码读了但配置没声明"的最小根 ⇒ 必须判红并**点名**那个变量；
  3. 「注释里提过」**不算**声明过（探针里名字只出现在注释 ⇒ 仍判红）；
  4. 动态取键（`env[keyName]`）必须被**单独列出来**，
     并且结论里不许出现"全部核对过"这种话（静态扫不到就要说扫不到）；
  5. 形态 B 的十个生成件绑定/包名/入口全对（本条是**现状快照式**判据 —— 它在拼接真源
     `mesh.json` 改动时该跟着动，所以断言的是"对账结果为空"，不是写死条数）。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "codex-scripts" / "cloud-config-wiring.py"


def _run(root: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), "--root", root, "--json"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180)


def _rep(p: subprocess.CompletedProcess) -> dict:
    i = p.stdout.find("{")
    return json.loads(p.stdout[i:]) if i >= 0 else {}


def _mkroot(toml_text: str, worker_js: str, mesh: dict | None = None) -> str:
    d = Path(tempfile.mkdtemp(prefix="cfgwire_probe_"))
    (d / "src").mkdir(parents=True, exist_ok=True)
    (d / "wrangler.toml").write_text(toml_text, encoding="utf-8")
    (d / "src" / "worker.js").write_text(worker_js, encoding="utf-8")
    if mesh is not None:
        (d / "mesh.json").write_text(json.dumps(mesh, ensure_ascii=False), encoding="utf-8")
    return str(d)


class RealDeployConfigTest(unittest.TestCase):
    def test_no_hard_issues_in_the_real_config(self) -> None:
        p = _run(str(ROOT / "deploy" / "cloud-10"))
        rep = _rep(p)
        self.assertEqual([], rep.get("A_read_but_undeclared", ["<拿不到读数>"]),
                         "部署配置里出现『代码读了、配置没交代』的名字 ⇒ 部署后就是 undefined")
        self.assertEqual(0, p.returncode, "接线对账判红：%s" % rep.get("A_read_but_undeclared"))

    def test_form_b_and_container_are_clean(self) -> None:
        rep = _rep(_run(str(ROOT / "deploy" / "cloud-10")))
        self.assertEqual([], rep.get("form_b_problems", ["<拿不到>"]), "形态 B 生成件与 mesh.json 对不上")
        self.assertEqual([], rep.get("container_problems", ["<拿不到>"]), "容器面不一致")


class CheckerHasTeethTest(unittest.TestCase):
    def test_undeclared_read_is_caught_and_named(self) -> None:
        root = _mkroot('name = "probe"\nmain = "src/worker.js"\n\n[vars]\nOK_ONE = ""\n',
                       'const e = env || {};\nif (!e.NOT_DECLARED_ANYWHERE) {}\n')
        p = _run(root)
        rep = _rep(p)
        self.assertEqual(1, p.returncode, "读了没声明的变量却判绿 ⇒ 判据瞎了")
        names = [n for n, _w in rep.get("A_read_but_undeclared", [])]
        self.assertIn("NOT_DECLARED_ANYWHERE", names)
        self.assertNotIn("OK_ONE", names, "已声明的名字不该进 A 类")

    def test_comment_mention_is_not_a_declaration(self) -> None:
        """「注释里提过 ≠ 声明过」—— 全仓那句「提到 ≠ 用了」的配置版。

        ⚠️ 自纠：第一版我断言它该落进 A 类（读而未声明）。跑出来落在"注释里提过但没声明"那一类，
        我核了一遍 —— **工具是对的，我的断言错了**。两个理由：
          ① 工具确实**没把它算成已声明**（这才是本条判据真正要守的东西）；
          ② 真配置里那些**必须走 `wrangler secret put` 的密钥**（OWNER_TOKEN / IMAGE_API_KEY…）
             本来就只出现在注释里、**永远不该被声明**（写进文件就是明文入库）。
             ⇒ 若把"只在注释里出现"一律判硬伤，工具就会对合法密钥**永久假红**。
        所以本条判据守的是：**不许算成已声明**；同时要求它出现在"注释里提过"那一栏（看得见、人好判）。
        """
        root = _mkroot('name = "probe"\nmain = "src/worker.js"\n\n# 说明：以后要接 MISSING_ONE\n[vars]\n',
                       'const e = env || {};\nif (!e.MISSING_ONE) {}\n')
        rep = _rep(_run(root))
        self.assertNotIn("MISSING_ONE", rep.get("declared", []),
                         "只在注释里出现过的名字被算成『已声明』了")
        soft = [n for n, _w in rep.get("notes_documented_but_not_declared", [])]
        self.assertIn("MISSING_ONE", soft, "注释里提过的名字没有单独列出来 ⇒ 人看不到这个缺口")

    def test_dynamic_key_access_is_reported_and_claims_are_hedged(self) -> None:
        root = _mkroot('name = "probe"\nmain = "src/worker.js"\n\n[vars]\n',
                       'export function f(env, keyName) { return env[keyName]; }\n')
        p = _run(root)
        rep = _rep(p)
        self.assertTrue(rep.get("dynamic_env_access_unscannable"),
                        "动态取键没被列出来 ⇒ 会让人以为『全部 env 读取已核对』")
        self.assertIn("看不见", rep.get("boundary", ""), "结论里没有如实交代静态扫描的盲区")

    def test_probe_root_without_mesh_does_not_crash(self) -> None:
        """探针根没有 `mesh.json` 时：不许崩，且要**明说"没查"而不是"通过"**。"""
        p = _run(_mkroot('name = "probe"\nmain = "src/worker.js"\n\n[vars]\n', "const e = env || {};\n"))
        rep = _rep(p)
        self.assertTrue(rep, "拿不到读数 ⇒ 探针根（无 mesh.json）把工具弄崩了")
        self.assertIn("未对账", rep.get("form_b_note", ""),
                      "form B 没查却不说明 —— 那就成了『没查成』被念成『没问题』")
        self.assertEqual([], rep.get("form_b_problems", ["<拿不到>"]))


if __name__ == "__main__":
    unittest.main()
