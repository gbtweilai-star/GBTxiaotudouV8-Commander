# -*- coding: utf-8 -*-
"""死指令判据 · **打印给别人照抄的命令，必须在本机真能跑**。

## 为什么立这条（2026-11-05 实测）

`tools/codex-scripts/audit-skill-roots.py` 的结论里印的是：

    ⇒ 重扫：`py -3.14 tools/codex-scripts/omni.py build`

而本机 `py -0` 只有 `-V:3.15[-64]`，跑 `py -3.14` 得到：

    [ERROR] No runtime installed that matches 3.14. Try running "py install 3.14".

⇒ 用户/agent 照着跑**就是一条废命令**。这一层"修法"比不给修法更坏：
它把"修不好"归因到"你没照做"，而不是"我印错了"。

同类前科：`启动-GBT.cmd` 曾写死 `py -3.14` / `C:\\Python312\\python.exe`，
本机三者全无 —— 脚本是写给另一个环境的。

## 口径（刻意窄，避免一上来 1700 条红得没人看）

只查两处**别人会照抄**的地方：

- **A 打印层**：任何 `print(...)` 行里的 `py -3.x` / `C:\\Python3xx` / `Python312\\python.exe`
- **B 人读入口**：`README.md` `CHARTER.md` `AGENTS.md` `LAYOUT.md`
  `CONTRIBUTING.md` `SECURITY.md` `demo.py`

**不在范围内的**（改了反而是篡改档案）：

- `CHANGELOG.md` / `PROJECT_BLUEPRINT.md` —— 那里写的是"当初坏过"，是取证凭证
- `.scratch/` `.archive/` —— 探针与历史快照
- 能力位 `desc` 里的示例与由它生成的 `docs/capabilities/*.md` —— 另一层盘子，
  单独治理，不与本判据混在一起（混了就永远红）

## 正确的写法

    .\\pyembed\\python.exe tools\\codex-scripts\\xxx.py      # PowerShell
    ./pyembed/python.exe  tools/codex-scripts/xxx.py      # 通用（本文档用法）

仓内一切 python 都用 `pyembed/`：系统别处的解释器没有 `mss` / `uiautomation` /
`pyautogui`，用它就等于"屏幕采集全灭"（AGENTS.md §6）。
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 命中的三种死法：py 启动器指定的版本、系统级 Python 目录、钉死的 python.exe
DEAD = re.compile(
    r"py\s+-3\.\d+"                          # py -3.14 / py -3.12
    r"|C:\\\\?Python3\d\d"                   # C:\Python312
    r"|Python3\d\d\\\\?python\.exe"          # Python312\python.exe
)

SKIP_PARTS = {"pyembed", "__pycache__", "node_modules", ".git", "state",
              "outputs", ".scratch", ".archive", "store"}

# B 类：人读入口（会被人直接复制粘贴的那几份）
ENTRY_DOCS = ["README.md", "CHARTER.md", "AGENTS.md", "LAYOUT.md",
              "CONTRIBUTING.md", "SECURITY.md", "demo.py"]

# 历史档案：明确豁免，理由写在模块 docstring 里
HISTORY = {"CHANGELOG.md", "PROJECT_BLUEPRINT.md"}

SELF = pathlib.Path(__file__).resolve()


def _dead_in_print_lines(path: pathlib.Path) -> list:
    """A 类：只查 `print(...)` 行 —— 这些是工具**亲口印给用户**的。"""
    out = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return out
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s.startswith("print("):
            continue
        if DEAD.search(s):
            out.append({"file": str(path), "line": i, "text": s[:120]})
    return out


def _dead_in_doc(name: str) -> list:
    """B 类：人读入口整份查（它们本来就短，且每行都可能被照抄）。"""
    p = ROOT / name
    if not p.is_file():
        return []
    out = []
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if DEAD.search(line):
            out.append({"file": name, "line": i, "text": line.strip()[:120]})
    return out


class TestNoDeadCommand(unittest.TestCase):
    def test_print_layer_has_no_dead_interpreter(self):
        """A. 工具打印出来的命令，本机必须真能跑。"""
        bad = []
        for p in ROOT.rglob("*.py"):
            if SKIP_PARTS & set(p.parts) or p.resolve() == SELF:
                continue
            bad.extend(_dead_in_print_lines(p))
        if bad:
            detail = "\n".join("  %s:%d  %s" % (b["file"].replace(str(ROOT), "."),
                                                b["line"], b["text"]) for b in bad[:15])
            self.fail(f"有 {len(bad)} 处 print 印着本机跑不了的命令"
                      f"（本机 `py -0` 只有 3.15，没有 3.14）：\n{detail}\n"
                      f"⇒ 修法：换成 `./pyembed/python.exe <脚本> <参数>`"
                      f"（仓内一切 python 都用 pyembed，见 AGENTS.md §6）")

    def test_entry_docs_have_no_dead_interpreter(self):
        """B. 人读入口（README / CHARTER / AGENTS / LAYOUT …）里的命令必须能跑。"""
        bad = []
        for name in ENTRY_DOCS:
            bad.extend(_dead_in_doc(name))
        if bad:
            detail = "\n".join("  %s:%d  %s" % (b["file"], b["line"], b["text"]) for b in bad[:15])
            self.fail(f"人读入口有 {len(bad)} 处死指令：\n{detail}\n"
                      f"⇒ 修法：换成 `./pyembed/python.exe ...`")

    def test_data_driven_commands_are_runnable(self):
        """**数据里的命令也是命令。** `LOCAL_TOOLS` / 能力位的 `invoke` 会被原样印给人照抄。

        血账（2026-11-05）：第二十批只扫了 `print(...)` 行与 7 份人读入口，
        于是 `LOCAL_TOOLS` 里那 **11 条** `invoke: "py -3.14 …"` **整轮没被发现** ——
        `omni ask` 会印出「→ py -3.14 …  ✅ 可达」：**标着可达、命令却是死的**。

        两条不变量：
          A. **任何**印出来的命令都不许含本机跑不了的写法（`py -3.x` / `C:\\Python3xx`）；
          B. 本地工具的首 token 若本机解析不到，**这一条必须已经标 🔴 并写明原因** ——
             也就是说「命令能跑」和「标没标红」不许自相矛盾。
             （`desktop-shell` 的 `electron` 本机没装，它标着 🔴 并给了理由，这属于诚实；
               真正要挡的是"✅ + 死命令"那种组合。）
        """
        import importlib.util
        import shutil

        spec = importlib.util.spec_from_file_location(
            "omni_for_cmdcheck", ROOT / "tools" / "codex-scripts" / "omni.py")
        omni = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(omni)          # type: ignore[union-attr]

        def _head(cmd):
            s = (cmd or "").strip()
            return s.split()[0] if s else ""

        def _resolvable(h):
            if not h:
                return False
            if h.replace("\\", "/").endswith("pyembed/python.exe"):
                return True
            return (ROOT / h).exists() or bool(shutil.which(h))

        # A. 任何命令都不许含死写法
        dead = []
        for t in omni.local_tools():
            if DEAD.search(t.get("invoke") or ""):
                dead.append("[local-tool %s] %s" % (t["name"], t.get("invoke")))
        for c in omni.load_atlas()["caps"]:
            if DEAD.search(c.get("invoke") or ""):
                dead.append("[cap %s] %s" % (c.get("kind"), c.get("invoke")))
        self.assertEqual(
            dead, [],
            "有 %d 条**印给人照抄的命令**含本机跑不了的写法：\n  %s\n"
            "⇒ 一律改成 `./pyembed/python.exe …`（仓内解释器）"
            % (len(dead), "\n  ".join(dead[:10])))

        # B. 命令跑不了 ⇒ 必须已经标红并给理由（不许"✅ + 死命令"）
        contradict = []
        for t in omni.local_tools():
            head = _head(t.get("invoke"))
            if _resolvable(head):
                continue
            if t.get("reachable") and not (t.get("reach_note") or "").strip():
                contradict.append("[%s] 命令首 token「%s」解析不到，却标 ✅ 且无说明 → %s"
                                  % (t["name"], head, t.get("invoke")))
        self.assertEqual(
            contradict, [],
            "这些条目自相矛盾（命令跑不了却标可达、且不说为什么）：\n  %s"
            % "\n  ".join(contradict[:8]))

    def test_local_tools_paths_are_real(self):
        """`LOCAL_TOOLS` 每一条的 `path` **必须真实存在**，且**不许落在临时目录**。

        血账（2026-11-05）：11 条里有 2 条指向 `.scratch/scan-20260923/*.py`（**整个目录已不存在**），
        1 条指向 `holo_pet_w3/shell/preflight.cjs`（**文件不存在**，同目录 23 个文件逐个核过）。
        登记幽灵的后果：`omni ask "深扫一遍"` 推一条跑不了的命令；`.scratch` 一清就永久失效。
        """
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "omni_for_toolpaths", ROOT / "tools" / "codex-scripts" / "omni.py")
        omni = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(omni)          # type: ignore[union-attr]

        bad = []
        for t in omni.LOCAL_TOOLS:
            rel = t.get("path") or ""
            if rel.replace("\\", "/").startswith(".scratch/"):
                bad.append("[%s] 登记在临时目录：%s" % (t["name"], rel))
                continue
            if not (ROOT / rel).is_file():
                bad.append("[%s] 文件不存在：%s" % (t["name"], rel))
        self.assertEqual(
            bad, [],
            "`LOCAL_TOOLS` 里有 %d 条**登记的实物不存在**：\n  %s\n"
            "⇒ 要么改指向真入口，要么摘掉登记（功能若还在，换成正式件）"
            % (len(bad), "\n  ".join(bad)))

    def test_npm_scripts_reference_real_files(self):
        """`holo_pet_w3/package.json` 的 scripts：引用文件必须存在，或明确标成 UNIMPLEMENTED。

        血账（2026-11-05）：28 个 script 里 **17 个引用的 .py 不存在**、**4 个 shell/*.cjs 不存在**、
        **19 个用 `py -3.14`**（本机没有 3.14）。`npm run verify` / `pack` / `release:*` 全在里面。
        处理：解释器改 `../pyembed/python.exe`；死链改成会**明确报错**的哨兵
        （`node -e "console.error('UNIMPLEMENTED: …')"`），既不假装能跑，也不删掉产品面。
        """
        import json
        import re

        pj = ROOT / "holo_pet_w3" / "package.json"
        if not pj.is_file():
            self.skipTest("没有 holo_pet_w3/package.json")
        scripts = json.loads(pj.read_text(encoding="utf-8")).get("scripts") or {}

        dead_interp, dead_ref = [], []
        for k, v in scripts.items():
            s = str(v)
            if DEAD.search(s):
                dead_interp.append("%s → %s" % (k, s[:70]))
            if "UNIMPLEMENTED" in s:
                continue                      # 已声明的哨兵：它本来就该失败
            for f in re.findall(r"(\.\./[\w./-]+\.(?:py|cjs|js|mjs)|shell/[\w./-]+\.cjs)", s):
                if not (ROOT / "holo_pet_w3" / f).resolve().is_file():
                    dead_ref.append("%s → 缺 %s" % (k, f))
        self.assertEqual(dead_interp, [],
                         "这些 npm script 还写着本机跑不了的写法：\n  %s"
                         % "\n  ".join(dead_interp[:10]))
        self.assertEqual(dead_ref, [],
                         "这些 npm script 引用的文件不存在，却没标 UNIMPLEMENTED：\n  %s\n"
                         "⇒ 改成明确报错的哨兵，别让 `npm run xxx` 含糊失败"
                         % "\n  ".join(dead_ref[:10]))

    def test_judge_itself_can_go_red(self):
        """负对照：喂一条假行，判据必须认出来（否则这条判据只是装饰）。"""
        # 用拼接避免本文件自己被 A 类扫到
        fake = "print('" + "py" + " " + "-3" + ".99 tools/x.py')"
        self.assertIsNotNone(DEAD.search(fake), "判据认不出死指令 —— 正则坏了")
        fake_ok = "print('" + "./pyembed/python" + ".exe tools/x.py')"
        self.assertIsNone(DEAD.search(fake_ok), "判据把正确写法误判成死指令")


if __name__ == "__main__":
    unittest.main(verbosity=2)
