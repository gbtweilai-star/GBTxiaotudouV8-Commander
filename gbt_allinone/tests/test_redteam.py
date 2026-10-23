"""授权红队内核的绊线（Owner 2026-09-25 令后的验收）。

守四件事，每一件都是**可机检**的，不是文档承诺：

  ① **接线三处在位** —— 12 位登记在 BENIGN_CAPS；每一位真调**不许**落到 `_run_benign`
     末尾那条兜底（`status: not_wired` = 登记了没接门 = 假绿）。
  ② **红线①目标边界** —— 未登记目标一律拒；公网中继端点一律拒。
  ③ **红线②不外传** —— `security/redteam.py` **不许 import 任何 HTTP 客户端**
     （AST 真扫，不是 grep 文本）。采集到的东西没有出网路径。
  ④ **红线③可见可关** —— 监控类必须能被 status 看到、被 stop 停掉、被 purge 清掉。

另守两条边界（Owner 令里那五位的诚实交代）：
  · `credential_steal` 的返回值里**不许出现凭据文件内容**（只有位置/体积/权限/环境变量名）。
  · `social_eng` / `paywallbuster` 只有"判"的分支，**没有"造"/"绕"的分支**。

测试隔离：`GBT_STORE_DIR` 指到临时目录（仓里标准做法）——
**本文件永远不会碰生产审计账本与授权账本**。
"""
import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_test_store_"))

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)

import gbt_allinone as gbt                                     # noqa: E402
from gbt_allinone import auth_gate as AG                       # noqa: E402
from gbt_allinone.caps_registry import (                       # noqa: E402
    BENIGN_CAPS, DISABLED_CAPS, UNIMPLEMENTED_CAPS)
from gbt_allinone.security import policy as Pol                # noqa: E402
from gbt_allinone.security import redteam as RT                # noqa: E402

# Owner 2026-09-25 令要补齐的那 11 位（名字不许丢）
LEGACY_11 = {
    "paywallbuster", "data_hijack", "remote_domain", "onboarding_gate",
    "keylogger", "screen_sniff", "device_takeover", "pentest",
    "asset_vault_freeze", "credential_steal", "social_eng",
}
# 实际接上的 12 位（多出来的是侦察面总入口）
REDTEAM = sorted(LEGACY_11 | {"redteam_recon"})

# 采集到的东西**不许**有出网的腿。
# ⚠️ 判据按**全路径**判，不按顶层名 —— `urllib.parse` 是纯字符串解析（安全），
#    `urllib.request` 才是出网客户端。只按顶层 `urllib` 判 = **误伤 + 漏放**两错并存。
#    （第一版就是按顶层名写的，被这条测试自己咬出来了。）
_NO_EXFIL_TOP = {"requests", "urllib3", "httpx", "aiohttp", "pycurl", "paramiko",
                 "ftplib", "smtplib", "telnetlib", "websocket", "websockets", "socketio"}
_NO_EXFIL_EXACT = {"urllib.request", "urllib.error", "urllib.response",
                   "http.client", "http.server", "http.cookiejar"}


def _is_exfil(mod: str) -> bool:
    """这个 import 出来的模块能不能出网？按**全路径**判。"""
    if mod.split(".")[0] in _NO_EXFIL_TOP:
        return True
    if mod in _NO_EXFIL_EXACT:
        return True
    return mod in ("urllib", "http")      # 裸 import：拿到的就是全模块本身


def _inner(env):
    """从 run_task 信封里取能力自身的返回（仓里叫 gbt_result 那层）。"""
    r = env
    for _ in range(3):
        if isinstance(r, dict) and isinstance(r.get("result"), dict):
            r = r["result"]
        else:
            break
    return r if isinstance(r, dict) else {}


class TestWiring(unittest.TestCase):
    """① 接线三处在位 —— 少一处就是"登记了没接门"的假绿。"""

    def test_all_twelve_are_benign(self):
        missing = [k for k in REDTEAM if k not in BENIGN_CAPS]
        self.assertEqual(missing, [], f"这几位没登记进 BENIGN_CAPS：{missing}")
        for k in REDTEAM:
            self.assertEqual(BENIGN_CAPS[k].get("handler"), k,
                             f"{k} 的 handler 名与能力名不一致")

    def test_legacy_eleven_names_conserved(self):
        """名字守恒：从"未实现"迁进"良性"不算丢。"""
        known = set(BENIGN_CAPS) | set(UNIMPLEMENTED_CAPS) | set(DISABLED_CAPS)
        self.assertEqual(sorted(LEGACY_11 - known), [], "红队 11 名有丢失")
        self.assertEqual(len(UNIMPLEMENTED_CAPS), 0,
                         "11 位已全部接上实现，UNIMPLEMENTED_CAPS 应为空")
        self.assertEqual(len(DISABLED_CAPS), 0, "DISABLED_CAPS 应保持为 0")

    def test_none_falls_through_to_not_wired(self):
        """每一位真调都不许落到 `_run_benign` 末尾那条兜底。

        那条兜底回 `status: not_wired` + `error_class: not_wired` —— 它是**止血**
        （比隐式 `result: None` 诚实），但落到它上面就说明**这一位还没接线**。

        ⚠️ 判据**认字段不认词**：早先我按"返回体里出现 not_wired 这个词"判，
        结果被自己命名的 `not_wired` 字段（意思是"某个子探测没读到"）误报了三处。
        同一个词两个意思 = 假红。现在只认 `error_class`。
        """
        bad = []
        for k in REDTEAM:
            env = gbt.run_task(k, {})
            inner = _inner(env)
            if env.get("error_class") == "not_wired" or inner.get("error_class") == "not_wired":
                bad.append(k)
            elif "没有分派分支" in json.dumps(env, ensure_ascii=False):
                bad.append(k)
        self.assertEqual(bad, [], f"这几位真调落到 not_wired 兜底：{bad}")

    def test_three_cli_agents_are_wired_too(self):
        """顺带修掉的三位存量假绿（它们此前**真的**返回过 `status:ok + result:None`）。"""
        for k in ("claude_code", "codebuddy", "ul_tars_desktop"):
            env = gbt.run_task(k, {"op": "status"})
            inner = _inner(env)
            self.assertNotIn("not_wired", json.dumps(env, ensure_ascii=False), k)
            self.assertIn("available", inner, f"{k} 的 status 必须真探 PATH")


class TestRedLines(unittest.TestCase):
    """② 目标边界 · ③ 不外传 · ④ 可见可关。"""

    def test_no_http_client_imported_in_redteam(self):
        """红线②：AST 真扫 import —— 被采集的数据没有出网路径。

        为什么用 AST 不用文本匹配：一句注释或一个字符串字面量就能骗过文本匹配
        （本仓 `security_brain` 的 `"os.replace" in src` 就是这么假绿过的）。
        """
        src = (Path(_ROOT) / "gbt_allinone" / "security" / "redteam.py").read_text(
            encoding="utf-8-sig")
        tree = ast.parse(src)
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    mods.add(a.name)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mods.add(node.module)
        hit = sorted(m for m in mods if _is_exfil(m))
        self.assertEqual(hit, [], f"redteam.py 里出现了出网客户端 import：{hit}")
        # 反向控制：判据要会咬，而且**不许误伤** urllib.parse
        for must_bite in ("requests", "urllib.request", "urllib", "http.client", "httpx"):
            self.assertTrue(_is_exfil(must_bite), f"判据咬不动 {must_bite}（假绿）")
        for must_spare in ("urllib.parse", "json", "hashlib", "socket", "ssl"):
            self.assertFalse(_is_exfil(must_spare), f"判据误伤了 {must_spare}")

    def test_target_classification(self):
        self.assertEqual(RT._classify("127.0.0.1")[0], "local")
        self.assertEqual(RT._classify("192.168.1.10")[0], "private")
        self.assertEqual(RT._classify("8.8.8.8")[0], "public")
        self.assertEqual(RT._classify("")[0], "invalid")

    def test_pentest_refuses_unregistered_target(self):
        env = gbt.run_task("pentest", {"action": "plan", "target": "example.com"})
        inner = _inner(env)
        self.assertTrue(inner.get("denied"), inner)
        self.assertIn("未登记", json.dumps(inner, ensure_ascii=False))

    def test_remote_domain_refuses_public_endpoint(self):
        """红线①：公网中继端点一律拒 —— 那正是"无授权远控"的形状。"""
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(RT, "_STATE", Path(td)):
                r = RT.remote_domain(action="add", name="evil", endpoint="8.8.8.8:4444")
                self.assertFalse(r.get("ok"), r)
                self.assertTrue(r.get("denied"), r)
                # 反向控制：本机端点**能**登记（否则"拒公网"可能只是"全都拒"）
                ok = RT.remote_domain(action="add", name="self", endpoint="127.0.0.1:9000")
                self.assertTrue(ok.get("ok"), ok)

    def test_credential_steal_returns_no_file_content(self):
        """诚实边界：只报位置/体积/权限，**绝不读取文件内容**。"""
        r = RT._recon_creds()
        allowed = {"path", "label", "bytes", "is_dir", "mtime", "error"}
        for row in r.get("files") or []:
            extra = set(row) - allowed
            self.assertEqual(extra, set(), f"凭据审计多出了字段（可能是内容）：{extra}")
        # env 只许给**变量名**，不许给值
        for name in r.get("env_var_names") or []:
            self.assertIsInstance(name, str)
            self.assertNotIn("=", name, f"环境变量条目里像是有值：{name[:40]}")
        self.assertIn("绝不读取", r.get("口径", ""))

    def test_defense_side_has_no_attack_branch(self):
        """social_eng 只判不造；paywallbuster 只判不绕。"""
        src = (Path(_ROOT) / "gbt_allinone" / "security" / "redteam.py").read_text(
            encoding="utf-8-sig")
        tree = ast.parse(src)
        for kind, forbidden in (("social_eng", ("generate", "compose", "craft", "forge")),
                                ("paywallbuster", ("bypass", "circumvent", "spoof",
                                                   "unlock", "fake_ua", "forge_cookie"))):
            node = next(n for n in ast.walk(tree)
                        if isinstance(n, ast.FunctionDef) and n.name == kind)
            body_src = ast.get_source_segment(src, node) or ""
            self.assertGreater(len(body_src), 200, f"{kind} 的源码段没取到（判据失效）")
            for word in forbidden:
                self.assertNotIn(word, body_src, f"{kind} 里出现了攻击侧字样：{word}")
            # 反向控制：拿同一把尺子量一段**确实有**攻击侧字样的源码，必须咬得动
            fake = ast.get_source_segment(
                "def social_eng(action='x'):\n    return generate_phishing_page()\n",
                next(n for n in ast.walk(ast.parse(
                    "def social_eng(action='x'):\n    return generate_phishing_page()\n"))
                    if isinstance(n, ast.FunctionDef) and n.name == "social_eng")) or ""
            self.assertIn("generate", fake, "反向控制的样本本身没造对（判据等于没验）")

    def test_monitor_is_visible_and_stoppable(self):
        """红线③：监控类必须**真能**列 / 停 / 取走 / 清掉 —— 不存在开了找不着的开关。

        这条**真起一次记录器再停掉**（不是只看 action 名单）：只看名单的话，
        "start 写没写 pid" 这件事根本没被验过 —— 而这正是"可关"的唯一凭据。
        """
        import time as _t
        made = []
        try:
            st0 = RT.keylogger(action="status")
            self.assertTrue(st0.get("ok"))
            self.assertIn("sessions", st0)
            self.assertIn("落点", st0)

            r = RT.keylogger(action="start", seconds=120, session="unittest-visible")
            self.assertTrue(r.get("ok"), r)
            made.append(r.get("session"))
            pid = int(r.get("pid") or 0)
            self.assertGreater(pid, 0, "start 必须回一个真 pid，否则停不掉")
            _t.sleep(1.5)

            st1 = RT.keylogger(action="status")
            row = next((x for x in st1["sessions"] if x.get("session") == "unittest-visible"),
                       None)
            self.assertIsNotNone(row, f"起了记录器却在 status 里看不见：{st1['sessions']}")
            self.assertTrue(row.get("running"), f"status 说它没在跑：{row}")

            killed = RT.keylogger(action="stop", session="unittest-visible")
            self.assertIn(pid, killed.get("stopped") or [],
                          f"stop 没真的结束那个 pid：{killed}")
            self.assertFalse(RT._pid_alive(pid), "stop 之后进程还活着 —— 「可关」不成立")

            d = RT.keylogger(action="dump", session="unittest-visible")
            self.assertTrue(d.get("ok"), d)
            self.assertGreaterEqual(d["sessions"][0]["lines"], 1, "记录器一行都没写")
        finally:
            RT.keylogger(action="stop", session="unittest-visible")
            RT.keylogger(action="purge")
        self.assertFalse(RT._pid_alive(0))
        self.assertTrue(RT.screen_sniff(action="list").get("ok"))


class TestGate(unittest.TestCase):
    """门：碰隐私载体/设备/写盘的一律挂作用域；纯离线判定不挂。"""

    def test_pure_analysis_is_not_gated(self):
        for kind, payload in (("social_eng", {"action": "analyze", "text": "hi"}),
                              ("paywallbuster", {"action": "detect", "html": "<p>x</p>"}),
                              ("asset_vault_freeze", {"action": "audit"}),
                              ("onboarding_gate", {"op": "gaps"})):
            d = Pol.evaluate(kind, payload)
            self.assertEqual(list(d.scopes), [],
                             f"{kind} 是纯离线判定，不该挂作用域：{list(d.scopes)}")

    def test_private_touching_is_gated(self):
        cases = [
            ("redteam_recon", {"op": "creds"}, ["privacy_read"]),
            ("credential_steal", {}, ["privacy_read"]),
            ("keylogger", {"action": "status"}, ["privacy_read"]),
            ("screen_sniff", {"action": "capture"}, ["privacy_read", "filesystem_write"]),
            ("data_hijack", {"action": "baseline"}, ["filesystem_write"]),
            ("device_takeover", {"action": "take"}, ["device_control"]),
            ("remote_domain", {"action": "add"}, ["remote_device", "filesystem_write"]),
            ("pentest", {"action": "verify"}, ["network_private"]),
        ]
        for kind, payload, expect in cases:
            got = sorted(Pol.evaluate(kind, payload).scopes)
            self.assertEqual(got, sorted(expect), f"{kind} 的作用域不对")

    def test_denied_without_grant_and_passes_with_one(self):
        """无授权 ⇒ 拒（并说清缺什么）；有授权 ⇒ 放行。全在临时 store 里做。"""
        gf = Path(AG._GRANTS)
        before = gf.read_bytes() if gf.exists() else b""
        self.assertFalse(Pol.is_trusted(), "本用例必须在非主人会话下跑")
        try:
            if gf.exists():
                gf.unlink()
            env = gbt.run_task("keylogger", {"action": "status"})
            self.assertTrue(_inner(env).get("denied"), "无授权时必须拒")

            # 合法途径：主人手写授权行（本仓测试的标准做法；落点是临时 store）
            row = {"id": "g-redteam-test", "scope": "privacy_read", "operator": "owner-manual",
                   "purpose": "redteam 用例", "mode": "window", "used": 0,
                   "granted_at": "2026-09-25T00:00:00",
                   "expires_at": float(9e9)}
            gf.parent.mkdir(parents=True, exist_ok=True)
            gf.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
            env2 = gbt.run_task("keylogger", {"action": "status"})
            self.assertFalse(_inner(env2).get("denied"),
                             f"发了授权后仍被拒：{_inner(env2)}")
        finally:
            if before:
                gf.write_bytes(before)
            elif gf.exists():
                gf.unlink()


class TestCliAgents(unittest.TestCase):
    """顺带修的三位假绿：探测必须**真查 PATH**，缺件必须**如实报缺**。"""

    def test_probe_all_shape(self):
        from gbt_allinone import cli_agents as CA
        r = CA.probe_all()
        self.assertTrue(r.get("ok"))
        self.assertEqual(sorted(r["agents"]), ["claude_code", "codebuddy", "ul_tars_desktop"])
        for k, v in r["agents"].items():
            self.assertIn("available", v)
            self.assertIn("searched", v)

    def test_missing_cli_reports_needs_dependency(self):
        """缺件必须**如实报缺**，而不是假 ok。

        ⚠️ 判据要看**执行侧**（op=exec），不能看 op=status：
        status 对"没装"这个事实**回答成功了**，回 `ok: true` 是对的
        （第一版拿 status 断言 `ok is False`，是**我测试写错了**，不是实现错了）。
        """
        from gbt_allinone import cli_agents as CA
        with mock.patch.dict(CA._AGENTS, {"_ghost": {
                "bins": ["__definitely_not_a_real_binary_xyz__"], "label": "幽灵",
                "install": "n/a", "prompt_flag": ""}}):
            st = CA.run("_ghost", {"op": "status"})
            self.assertTrue(st.get("ok"), st)
            self.assertFalse(st.get("available"), "探不到就该说探不到")
            self.assertEqual(st.get("found"), [])

            ex = CA.run("_ghost", {"op": "exec", "prompt": "hi"})
            self.assertFalse(ex.get("ok"), ex)
            self.assertEqual(ex.get("status"), "needs_dependency")
            self.assertIn("missing", ex)
            self.assertIn("install_hint", ex)

    def test_exec_without_prompt_is_refused(self):
        from gbt_allinone import cli_agents as CA
        r = CA.run("claude_code", {"op": "exec"})
        self.assertFalse(r.get("ok"))
        self.assertIn("prompt", json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
