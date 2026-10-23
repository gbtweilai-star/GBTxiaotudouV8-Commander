r"""提交前凭据自审（`tools/codex-scripts/precommit-secret-scan.py`）自己的判据。

立它的理由（一手账，第 52 轮）：**这份"强制自审"此前根本不在仓里** ——
它只存在于 `%TEMP%\precommit-secret-scan.py`（34 行，sha256 `9A5580CD****`，
修改时间 2026-09-26 04:19:20）。于是：

  · 重启即消失 ⇒ 「强制」全靠我的记忆执行，而主人明确要求的是「重启之后自动读取」；
  · `git` 看不见它、开机自检点不到它、别人拿不到它 ⇒ 它是**私有的、不可复核的**；
  · 更糟：它的 ① 号判据要读 `%TEMP%\mcporter.json.before-dpapi.bak`（1231 字节，
    里面 `adp.ADP_API_KEY` 是 32 位**明文**）—— **防明文落盘的工具自己依赖一份明文落盘**。
    而开机自检里那条「密钥不许明文落盘」当时是绿的：尺子只量了仓这半个屋子。

所以这一轮：工具进仓 + ① 改成**当场从 DPAPI 保险箱解密、只在内存里过**（不读任何明文参照），
并把「不许报绿」的条件写进契约。判据守的就是这些，一条都不许写成快照。
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "codex-scripts" / "precommit-secret-scan.py"
PY = sys.executable


def _load():
    spec = importlib.util.spec_from_file_location("precommit_secret_scan", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _code_only(path: Path) -> str:
    """剥掉模块 docstring 与 `#` 注释，只留**会真跑的那部分**。

    这一步不是为了让判据好过，而是为了让判据**逮对东西**：这一组要逮的是
    「谁把调用指到了 TEMP」，而本工具与这条判据**必须**在文档里写明来由
    （第 52 轮为什么把它搬进仓里）。逮文档 = 逼着下一个人删掉来由才绿 ——
    那正是本仓打过的那种假判据（「红的是记录，不是代码」）。
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r'"""(?:.|\n)*?"""', "", text)
    text = re.sub(r"'''(?:.|\n)*?'''", "", text)
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


# 在**真保险箱**（不设 GBT_STORE_DIR）里读一次密钥、把密钥只留在子进程里做泄露检查。
# 写成子进程的理由：判据进程自己**从不持有**真密钥 ⇒ 它连"打印出密钥"的机会都没有。
# 只回布尔与 profile 名，绝不回密钥、也绝不回密钥的前缀。
_LEAK_PROBE = """
import contextlib, importlib.util, io, json, sys
sys.path.insert(0, %(root)r)
spec = importlib.util.spec_from_file_location("pss", %(tool)r)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
keys, failed = m.vault_keys()
if not keys:
    print(json.dumps({"ran": False, "why": "保险箱里没有可读密钥", "unreadable": failed}))
    raise SystemExit(0)
name = sorted(keys)[0]
# 路一：直接调 scan()，把**真密钥种进 diff**，看它会不会漏进报告
rep = m.scan('+k = "%%s"\\n' %% keys[name], keys)
blob = json.dumps(rep, ensure_ascii=False)
leaked = sorted(n for n, v in keys.items() if v and v in blob)
# 路二：跑 CLI 本体（`--json`），把它的 stdout/stderr 也收进来查同一件事
buf_out, buf_err = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
    rc = m.main(["--json"])
cli_blob = buf_out.getvalue() + buf_err.getvalue()
cli_leaked = sorted(n for n, v in keys.items() if v and v in cli_blob)
try:
    cli_compared = json.loads(buf_out.getvalue())["profiles_compared"]
except Exception:
    cli_compared = -1
print(json.dumps({"ran": True, "profiles": len(keys), "leaked": leaked,
                  "cli_leaked": cli_leaked, "cli_compared": cli_compared, "cli_rc": rc,
                  "hit_profiles": [h["profile"] for h in rep["exact_hits"]],
                  "exit": rep["exit"]}))
"""


class ToolResidencyTest(unittest.TestCase):
    """工具必须**留在仓里** —— 这一组守的正是 F17 的根因。"""

    def test_tool_is_in_the_repo(self) -> None:
        self.assertTrue(TOOL.is_file(), "提交前自审工具不在仓里：%s" % TOOL)

    def test_readme_style_docstring_says_why(self) -> None:
        src = TOOL.read_text(encoding="utf-8")
        self.assertIn("%TEMP%", src, "得写明它此前为什么只在 TEMP 里、以及那等于没有")
        self.assertIn("F17", src, "得指回台账里的故障号，否则下一个人不知道来由")

    def test_no_plaintext_reference_file_dependency(self) -> None:
        """① 号判据不许再依赖 TEMP 里那份明文备份（**看会跑的代码，不看说明**）。"""
        code = _code_only(TOOL)
        self.assertNotIn("before-dpapi.bak", code,
                         "自审工具的代码里不许读明文参照文件（防明文的工具自己依赖明文）")
        self.assertIn("load_from_vault", code,
                      "① 必须当场从 DPAPI 保险箱取，且用 load_from_vault（忽略环境变量）")

    def test_it_does_not_shell_out_to_a_temp_copy(self) -> None:
        """真跑的时候跑的必须是仓里这一份，不是 TEMP 里那份。"""
        code = _code_only(TOOL)
        self.assertNotIn("tempfile.gettempdir", code)
        self.assertNotIn("TEMP", code, "代码里不许再碰 TEMP（说明里写来由不算）")


class SelfTestTest(unittest.TestCase):
    """离线自证：种进去必须逮住，且**不许恒真**。"""

    def test_selftest_is_green(self) -> None:
        out = subprocess.run([PY, str(TOOL), "--selftest", "--json"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", cwd=str(ROOT), timeout=120)
        self.assertEqual(0, out.returncode, out.stdout[-800:] + out.stderr[-400:])
        rep = json.loads(out.stdout)
        self.assertTrue(rep["ok"], "自证没过：%s" % rep)
        self.assertGreaterEqual(rep["total"], 10)
        self.assertEqual(rep["passed"], rep["total"])
        names = [c["control"] for c in rep["controls"]]
        for needed in ("①逐字比对能逮住且数得对", "②形状扫描能逮住",
                       "③空保险箱不许报绿", "③命中与没跑成不同码"):
            self.assertIn(needed, names, "自证少了这条控制：%s" % needed)

    def test_selftest_has_a_control_that_can_fail(self) -> None:
        """**反恒真**：自证自己也得能被弄红。

        做法：把 `exact_hits` 换成一个"永远回空"的桩，自证的 ③命中与没跑成不同码
        必须变成红。如果换成桩之后自证照样全绿，那这 10 条控制就是摆设。
        """
        mod = _load()
        real = mod.exact_hits
        try:
            mod.exact_hits = lambda diff, keys: []  # 桩：永远说"没命中"
            rep = mod.selftest()
        finally:
            mod.exact_hits = real
        self.assertFalse(rep["ok"], "把逐字比对换成永远回空的桩之后自证竟然还是绿的")
        failed = [c["control"] for c in rep["controls"] if not c["ok"]]
        self.assertIn("③命中与没跑成不同码", failed,
                      "该红的那条没红：%s" % failed)


class ContractTest(unittest.TestCase):
    """退出码契约：0 干净 · 1 命中 · 2 自审没跑成（含反空洞）。"""

    def setUp(self) -> None:
        self.mod = _load()
        self.fake = "sk-" + "Zq7" * 12

    def test_clean_is_zero(self) -> None:
        r = self.mod.scan("+hello\n", {"synthetic": self.fake})
        self.assertEqual(0, r["exit"])
        self.assertTrue(r["exact_ran"], "① 得真比过才算干净")

    def test_hit_is_one(self) -> None:
        r = self.mod.scan("+k = \"%s\"\n" % self.fake, {"synthetic": self.fake})
        self.assertEqual(1, r["exit"])
        self.assertFalse(r["ok"])

    def test_unrun_is_two(self) -> None:
        r = self.mod.scan("+hello\n", {}, failed=["deepseek"])
        self.assertEqual(2, r["exit"])
        self.assertFalse(r["exact_ran"])
        self.assertTrue(any("根本没比" in p for p in r["problems"]))

    def test_allow_empty_vault_must_be_explicit(self) -> None:
        r = self.mod.scan("+hello\n", {}, failed=["deepseek"], allow_empty_vault=True)
        self.assertEqual(0, r["exit"])
        self.assertFalse(r["exact_ran"], "放行了也得如实标出①没比过")

    def test_unregistered_secret_still_caught_by_shape(self) -> None:
        """**① 的盲区就是 ② 的存在理由**：没登记进保险箱的凭据 ① 一律逮不住。"""
        unregistered = "b3f4" + "0a" * 14
        r = self.mod.scan("+k = \"%s\"\n" % unregistered, {"synthetic": self.fake})
        self.assertEqual([], r["exact_hits"], "这种串本来就不该被①逮住")
        self.assertEqual(1, len(r["shape_hits"]), "② 必须兜住①的盲区")
        self.assertEqual(0, r["exit"], "② 只报形状，不改退出码（形状串可能是误报）")


class NoLeakTest(unittest.TestCase):
    """输出里**不许有密钥原文** —— 只许掩码。"""

    def test_json_report_never_contains_a_real_key(self) -> None:
        mod = _load()
        keys, _failed = mod.vault_keys()
        if not keys:
            self.skipTest("保险箱里一个密钥都没有 ⇒ 这条判据今天没东西可验")
        r = mod.scan("+k = \"%s\"\n" % list(keys.values())[0], keys)
        blob = json.dumps(r, ensure_ascii=False)
        # 🔴 故意**不用** assertNotIn：它失败时会把 needle（真密钥）打进报告里。
        leaked = sorted(n for n, k in keys.items() if k and k in blob)
        self.assertEqual([], leaked, "这些 profile 的密钥明文进了报告（只报名字）：%s" % leaked)

    def test_shape_scan_output_is_masked(self) -> None:
        mod = _load()
        secret = "b3f4" + "0a" * 14
        shapes = mod.shape_hits("+k = \"%s\"\n" % secret)
        self.assertEqual(1, len(shapes))
        self.assertTrue(shapes[0]["masked"].endswith("****"))
        self.assertNotIn(secret, json.dumps(shapes, ensure_ascii=False))

    def test_real_vault_keys_never_reach_the_report(self) -> None:
        """在**真保险箱**上跑两条路：直接调 `scan()` 与跑 CLI 本体。

        ⚠️ 这里**故意把 `GBT_STORE_DIR` 摘掉**：满仓横扫默认把 store 指到临时目录，
        保险箱里就是空的 ⇒ 这条判据会以「保险箱没有密钥」跳过，等于没查。
        摘掉之后读的是本仓真保险箱（现读 8 个 profile），这条才真跑。
        """
        probe = _LEAK_PROBE % {"root": str(ROOT), "tool": str(TOOL)}
        env = {k: v for k, v in os.environ.items() if k != "GBT_STORE_DIR"}
        out = subprocess.run([PY, "-c", probe], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", cwd=str(ROOT),
                             env=env, timeout=180)
        self.assertEqual(0, out.returncode, out.stdout[-400:] + out.stderr[-400:])
        rep = json.loads(out.stdout.strip().splitlines()[-1])
        if not rep.get("ran"):
            self.skipTest("真保险箱里没有可读密钥：%s" % rep.get("unreadable"))
        self.assertGreaterEqual(rep["profiles"], 1)
        # 路一：scan() 的报告里不许有明文
        self.assertEqual([], rep["leaked"],
                         "这些 profile 的密钥明文进了报告（只报名字）：%s" % rep["leaked"])
        # 路二：CLI 的 stdout/stderr 里同样不许有明文
        self.assertEqual([], rep["cli_leaked"],
                         "CLI 输出里出现了这些 profile 的明文（只报名字）：%s" % rep["cli_leaked"])
        self.assertGreaterEqual(rep["cli_compared"], 1,
                                "CLI 那次 ① 得真比过（否则这条输出检查是空跑）")
        self.assertIn(rep["cli_rc"], (0, 1, 2), "CLI 退出码必须在契约内：%s" % rep["cli_rc"])
        # 顺带证一次"①真比过"：种进 diff 的那条必须被逮住，否则这次泄露检查是空跑
        self.assertTrue(rep["hit_profiles"],
                        "把真密钥种进 diff 却没被①逮住 ⇒ 这次泄露检查其实什么都没查")
        self.assertEqual(1, rep["exit"])


class JudgmentWiringTest(unittest.TestCase):
    """接进开机自检 —— 否则它又是一条"我嘴上说强制"的东西。"""

    def test_boot_selfcheck_names_this_judgment(self) -> None:
        boot = (ROOT / "tools" / "codex-scripts" / "boot-selfcheck.py").read_text(encoding="utf-8")
        self.assertIn("test_precommit_secret_scan", boot,
                      "开机自检没点名这条判据 ⇒ 「强制」还是只靠记忆")

    def test_no_tool_still_points_at_the_temp_copy(self) -> None:
        """仓里不许再有别的地方把**调用**指向 TEMP 那份。

        三条口径，都写明白（这一条改过两次，两次都是**假阳性**逼出来的）：
          · **剥文档**：本工具与这条判据都必须写明来由（F17 是什么、当初错在哪），
            所以 `.py` 只查"会跑的代码"。
          · **不查 `.md` / `.json`**：这两类在本仓是**文档与数据**。
            F17 那条记录必须能引用旧路径才能讲清当年错在哪 ——
            要是连引用都算"指向 TEMP"，那就只剩"删掉故障记录才绿"这一条路，
            正是本仓打过的那种假判据（红的是记录，不是代码）。
            🔴 但**别把牙齿也拔了**：JSON 里真能藏命令的地方是 `package.json` 的 `scripts`，
            那条单列在 `test_package_json_scripts_do_not_invoke_the_temp_copy`。
          · **排除本文件自己**：下面那三条正则**就是**「指向 TEMP」的定义，
            它当然会匹配到自己。这是定义，不是调用。排除面必须**恰好这一个** ——
            断言写死 file 集合，防止以后有人把排除面悄悄放大。
        """
        # 🔴 2026-10-17 修（挂死根因 · 留痕 · 原口径 / 为什么翻 / 现口径）：
        #   原口径：用 `p.resolve()`（= `os.path.realpath`）判"这个文件是不是本文件"，
        #     而本判据要**全仓 `ROOT.rglob("*")`**（18 万级文件）。
        #   为什么翻：`.scratch/_baseline_wt` 是 **git worktree**（junction 族），
        #     `ntpath.realpath` 在它上面会**卡死** —— 实测整套测试连环两轮都死在
        #     `test_precommit_secret_scan.py:277 → Path.resolve() → ntpath.realpath`（pytest Timeout）。
        #   原期望【不变】：排除面**恰好一条** = "写着这三条正则的本文件"（下面的断言继续咬它）。
        #   现口径：改用 **abspath + normcase** 比较 —— 不跟软链、不踩 worktree，语义不变。
        me = Path(__file__).resolve()
        excluded = {me}
        self_abs = os.path.normcase(os.path.abspath(str(me)))
        points_at_temp = (
            re.compile(r"%TEMP%[^\n]{0,20}precommit-secret-scan", re.I),
            re.compile(r"gettempdir\(\)[^\n]{0,40}precommit-secret-scan", re.I),
            re.compile(r"[Aa]ppData[^\n]{0,40}precommit-secret-scan", re.I),
        )
        offenders = []

        def _iter_code_files():
            """遍历**本仓代码树**（剪枝）：跳过的目录根本不进去。

            🔴 2026-10-17 修（挂死 · 留痕 · 原口径 / 为什么翻 / 现口径）：
              原口径：`ROOT.rglob("*")` —— 先**遍历全仓**，再在循环体里按 parts 跳过。
              为什么翻：跳过写在循环体里对 rglob **无效**（它已经走下去了）。`_upstream/`
                （第三方仓 · node_modules 十万级）与 `.scratch/_baseline_wt`（git worktree）
                在**遍历阶段**就把判据卡死 —— 实测 Timeout 栈先后落在
                `ntpath.realpath` 与 `glob.py::scandir`。
              现口径：`os.walk` + **剪枝** `dirnames`（跳过的目录根本不进），
                语义与原来那组 skip parts 相同，成本从"遍历 18 万"降到"只走本仓代码树"。
            """
            exts = (".py", ".mjs", ".js", ".cjs", ".ts", ".ps1", ".sh", ".bat", ".cmd")
            skip = (".git", "node_modules", "__pycache__", "archive", ".scratch", "_upstream")
            for dirpath, dirnames, filenames in os.walk(str(ROOT)):
                dirnames[:] = [d for d in dirnames if d not in skip]
                for name in filenames:
                    if Path(name).suffix.lower() in exts:
                        yield Path(dirpath) / name

        for p in _iter_code_files():
            if os.path.normcase(os.path.abspath(str(p))) == self_abs:
                continue
            # 🔴 2026-10-10 修（**扫描盲区，有证据**）：
            #    实测本判据红在 offenders = ['.scratch/_baseline_wt/gbt_allinone/tests/test_precommit_secret_scan.py']。
            #    那不是"有件指向 TEMP"，那是**框架门基线 worktree 里的整仓副本** ——
            #    .scratch/_baseline_wt 是 git worktree（git worktree list 里挂着，detached HEAD），
            #    **本身就不该被当成"仓内代码"扫**：它存在即副本，扫它只会扫到自己的影子。
            #    ⇒ 跳过名单加 ".scratch"（与 .git/node_modules/__pycache__/archive 同理）。
            #    注意：**不动 excluded** —— 排除面仍恰好是"定义正则的本文件"一条（下面那条断言继续咬）。
            # 🔴 2026-10-11 加 "_upstream"（**治根，实测有据**）：
            #    本判据全仓 rglob，而 _upstream/ 是**第三方仓**（本仓口径：「第三方依赖树，
            #    不是资产」，与 .venv/site-packages 同族）。实测：克隆一个外部件进
            #    _upstream/ 之后，本判据单跑从 **220s 涨到 382s**，直接顶穿 boot-selfcheck
            #    给的 300s 超时 ⇒ 以 "timeout>300s" 的形式**假红**。
            #    它扫的是"仓内代码有没有把自审指向 TEMP"，第三方仓的 README/assets
            #    与这件事无关 ⇒ 跳过（≠ 放行：scan 本体审的是 git diff，不受影响）。
            if any(part in (".git", "node_modules", "__pycache__", "archive", ".scratch",
                            "_upstream")
                   for part in p.parts):
                continue
            try:
                text = _code_only(p) if p.suffix.lower() == ".py" else p.read_text(
                    encoding="utf-8", errors="replace")
            except OSError:
                continue
            if any(pat.search(text) for pat in points_at_temp):
                offenders.append(str(p.relative_to(ROOT)))
        self.assertEqual([], sorted(offenders),
                         "这些地方还把自审指向 TEMP 副本：%s" % sorted(offenders))
        self.assertEqual(1, len(excluded), "排除面只许有这一个（定义正则的本文件）")

    def test_package_json_scripts_do_not_invoke_the_temp_copy(self) -> None:
        """JSON 里唯一能真"跑东西"的地方是 `scripts` —— 那里仍然要有牙。

        这条是上面那条"不查 .json"的对价：放宽了数据文件的排查面，
        就必须在**真能执行**的那一格里补一道。
        """
        offenders = []

        def _iter_package_json():
            """同上面那条：os.walk **剪枝**，跳过的目录不进（rglob 的"循环体里跳过"无效）。"""
            skip = (".git", "node_modules", "__pycache__", "archive", ".scratch", "_upstream")
            for dirpath, dirnames, _filenames in os.walk(str(ROOT)):
                dirnames[:] = [d for d in dirnames if d not in skip]
                if "package.json" in _filenames:
                    yield Path(dirpath) / "package.json"

        for pkg in _iter_package_json():
            # 同上：_upstream 是第三方仓，与"本仓有没有把自审指向 TEMP"无关；
            # 扫它会拖慢判据（见上一条注释的 220s→382s 实测）。
            if any(part in (".git", "node_modules", "__pycache__", "archive", "_upstream")
                   for part in pkg.parts):
                continue
            try:
                doc = json.loads(pkg.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                continue
            scripts = doc.get("scripts") if isinstance(doc, dict) else None
            if not isinstance(scripts, dict):
                continue
            for name, cmd in scripts.items():
                if "precommit-secret-scan" in str(cmd) and "%TEMP%" in str(cmd).upper():
                    offenders.append("%s:scripts.%s" % (pkg.relative_to(ROOT), name))
        self.assertEqual([], sorted(offenders), "package.json 的 scripts 指向 TEMP 副本：%s" % offenders)


if __name__ == "__main__":
    unittest.main()
