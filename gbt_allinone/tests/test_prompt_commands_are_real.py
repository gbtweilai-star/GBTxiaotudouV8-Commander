"""R-H608（2026-09-25）· 注入给模型的 prompt 里，**不许出现"盘上没有的命令"**。

被测故障（现读实测，不是推演）：
    `_build_cap_digest()` 的表尾原本教了模型两条调用法：
        > 直接调用: python caps/<cap_id>/run.py <action> '{"k":"v"}'
        > N8N入口: POST http://localhost:5678/webhook/gbt {...}
    而现读：`caps/` 顶层**只有 2 个目录、全库只有 1 个 `run.py`**（`caps/design_brain/run.py`）
    ⇒ `caps/health/run.py` / `caps/mirror_status/run.py` / `caps/echo/run.py` **统统不存在**；
    5678 端口**无监听**。**⇒ 自我认知教了模型两条调用法，两条都是死的。**

    后果比"少一句说明"重得多：模型照着走 ⇒ 文件不存在 ⇒ 它得出"这框架调不动"的结论，
    而**真正的入口只有一道门**（`run_task` / `five-dim.py cap`），那条路它反而没被告知。

判据（三条，都要有牙）：
  1. prompt 里出现的每一发 `python <路径>`，**那个文件必须在盘上**（本判据自动覆盖本次这类病）；
  2. prompt 里出现的每一发 `python -m <模块>`，**`<模块>.py` 必须在盘上**；
  3. prompt 里**不许出现模板式假路径**（形如 `caps/<cap_id>/run.py`）——
   它是"教一条不存在的路"的典型形态，模板占位符永远不会解析成真文件。
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from gbt_allinone.llm import cloud_llm as cl

ROOT = Path(__file__).resolve().parents[2]
PROMPT = cl._build_system()

# `python <path>` / `python -m <mod>`；path 允许含 `/`、`\`、`.`、`-`、`_`、字母数字
_PATH_CMD = re.compile(r"\bpython\s+((?:[\w.\-]+[\\/])*[\w.\-]+\.(?:py|cjs|js))\b")
_MOD_CMD = re.compile(r"\bpython\s+-m\s+([\w.]+)")
_TEMPLATE_PATH = re.compile(r"[\w/\\.\-]*<[^>\s]+>[\w/\\.\-]*")


class PromptCommandsAreRealTest(unittest.TestCase):
    def test_prompt_is_not_empty(self) -> None:
        self.assertGreater(len(PROMPT), 500, "prompt 读不出来 ⇒ 后面几条判据会空转（假绿）")

    def test_every_python_path_command_exists_on_disk(self) -> None:
        seen = sorted(set(_PATH_CMD.findall(PROMPT)))
        self.assertTrue(seen, "一条路径式命令都没解析到 —— 判据失效（比崩溃更坏）")
        missing = [p for p in seen if not (ROOT / p).is_file()]
        self.assertEqual([], missing,
                         "prompt 教了盘上没有的命令：%s（现读解析到：%s）" % (missing, seen))

    def test_every_python_m_module_exists_on_disk(self) -> None:
        seen = sorted(set(_MOD_CMD.findall(PROMPT)))
        self.assertTrue(seen, "一条 `python -m` 都没解析到 —— 判据失效")

        def _exists(mod: str) -> bool:
            # 🔴 2026-09-25 修我自己的过窄判据：`python -m <名>` 既可以是**模块**（`<名>.py`），
            #    也可以是**包**（`<名>/__init__.py`）。第一版只认前者 ⇒ 对
            #    `python -m gbt_allinone auth grant …`（合法包）判红。**这是判据的错，不是那行的错。**
            base = ROOT.joinpath(*mod.split("."))
            return base.with_suffix(".py").is_file() or (base / "__init__.py").is_file()

        missing = [m for m in seen if not _exists(m)]
        self.assertEqual([], missing, "prompt 点名了不存在的模块/包：%s" % missing)

    def test_no_template_path_is_advertised_as_a_real_command(self) -> None:
        """模板式假路径（`caps/<cap_id>/run.py`）不许当作"直接调用"教出去。"""
        offenders = []
        for line in PROMPT.splitlines():
            if "python" not in line:
                continue
            for m in _TEMPLATE_PATH.finditer(line):
                if m.group(0).endswith((".py", ".js", ".cjs")):
                    offenders.append(line.strip()[:120])
        self.assertEqual([], offenders,
                         "prompt 里出现模板式假路径当命令：%s" % offenders)

    def test_advertises_the_one_real_gate(self) -> None:
        """换掉假入口之后，必须真的把**唯一门**说出来。"""
        self.assertIn("run_task", PROMPT, "prompt 没告诉模型真正的入口是 run_task")
        self.assertIn("five-dim.py", PROMPT, "prompt 没给 CLI 那条同一道门的命令")


if __name__ == "__main__":
    unittest.main(verbosity=2)
