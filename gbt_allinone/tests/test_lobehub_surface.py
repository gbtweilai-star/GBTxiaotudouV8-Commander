"""LobeHub 可控制面判据（主人令 2026-09-27）。

主人原话：「把 `C:\\Users\\ADMIN\\Desktop\\LobeHub.lnk` 做成**可执行的插件**安装到**工具区**，
这个玩意功能是真的多，**都要跟触手双向绑定**，只要是**可控制的都要绑上**。」

**判据（都可判定，且都写明了"红了怎么办"）**：
  A. **三处齐**：`caps_registry` 登记 · 图鉴收录 · `api.py` 有分派 —— 少一处，门就看不见它；
  B. **面非空**：清单里设置键/可控制按键/接口操作/助理各达阈值（阈值来自实测，见模块 docstring）；
  C. **消失即断连**（**反向自检**）：喂一份"键被删掉/数量缩水"的清单，`verify` 必须红 ——
     不然 B 只证明"现在好看"，不证明"真丢了会喊"；
  D. **凭据永不回值**：把设置文件里 `encryptedTokens` 的真实密文拿来比对，`settings` 的输出里
     **一个字都不许出现**（血账：掩码按**值**判过一次，DPAPI 密文被原样打出来）；
  E. **写有闸**：安全姿态类键（gateway/代理/令牌）与含凭据字样的键一律**拒写**；
  F. **动作有门**：拿一个不存在的 pid 关进程，**绝不许报成功**（缺票就如实说缺哪张票）；
  G. **出网钉死**：模块里只许有一个出口且主机写死 127.0.0.1；非法端口/相对路径一律拒。
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "gbt_allinone" / "tools" / "lobehub.py"
REG = ROOT / "gbt_allinone" / "caps_registry.py"
API = ROOT / "gbt_allinone" / "api.py"
ATLAS = ROOT / "state" / "skill_atlas.json"
MANIFEST = ROOT / "state" / "surfaces" / "lobehub.json"
SETTINGS = Path(r"C:\Users\ADMIN\AppData\Roaming\lobehub\lobehub-settings.json")


def _load():
    spec = importlib.util.spec_from_file_location("lobehub_probe", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestLobehubSurface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    # ---- A 三处齐 ----
    def test_a_registered_in_three_places(self):
        reg = REG.read_text(encoding="utf-8")
        api = API.read_text(encoding="utf-8")
        self.assertIn('"lobehub"', reg, "caps_registry 没登记")
        self.assertIn('kind == "lobehub"', api, "api.py 没有分派分支（登记了却调不到）")
        atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
        kinds = {c["kind"] for c in atlas["caps"]}
        self.assertIn("lobehub", kinds, "图鉴没收录（三处齐才算接上）")

    # ---- B 面非空 ----
    def test_b_surface_meets_thresholds(self):
        r = self.m.surface()
        self.assertTrue(r.get("ok"), f"探面失败：{r}")
        c = r["counts"]
        self.assertGreaterEqual(c["settings"], self.m.MIN_SETTINGS, "设置键太少（有漏）")
        self.assertGreaterEqual(c["shortcuts"], self.m.MIN_SHORTCUTS, "可控制按键太少")
        self.assertGreaterEqual(c["api_ops"], self.m.MIN_OPS, "接口操作太少")
        self.assertGreaterEqual(c["agents"], self.m.MIN_AGENTS, "助理数为 0（账号面变了？）")
        self.assertTrue(self.m.verify().get("ok"), "verify 报红")

    # ---- C 反向自检：判据自己会红吗 ----
    def test_c_verify_turns_red_on_shrunk_surface(self):
        import tempfile
        real = self.m._MANIFEST
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "lobehub.json"
            good = json.loads(real.read_text(encoding="utf-8"))
            # ① 键数缩水（设置只剩 1 个）
            bad = json.loads(json.dumps(good))
            bad["counts"] = dict(good["counts"], settings=1)
            fake.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            self.m._MANIFEST = fake
            try:
                self.assertFalse(self.m.verify().get("ok"), "缩水了竟然还报绿 ⇒ 阈值形同虚设")
                # ② 有键消失（断连）
                bad2 = json.loads(json.dumps(good))
                bad2["gone"] = ["shortcuts.quickComposer"]
                fake.write_text(json.dumps(bad2, ensure_ascii=False), encoding="utf-8")
                self.assertFalse(self.m.verify().get("ok"), "断连了竟然还报绿")
            finally:
                self.m._MANIFEST = real
        # 真清单必须是绿的（不然上面两条是假红）
        self.m._MANIFEST = real
        self.assertTrue(self.m.verify().get("ok"), f"真清单报红：{self.m.verify().get('problems')}")

    # ---- D 凭据永不回值 ----
    def test_d_secrets_never_come_back(self):
        if not SETTINGS.is_file():
            self.skipTest("本机没有 LobeHub 设置文件")
        real = json.loads(SETTINGS.read_text(encoding="utf-8"))
        secrets = []

        def walk(o, key=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, k)
            elif isinstance(o, str) and any(s in key.lower() for s in
                                            ("token", "key", "secret", "password", "credential")):
                if len(o) > 16:
                    secrets.append(o)

        walk(real)
        self.assertTrue(secrets, "设置里没有凭据字段？那这条判据没验到东西（别放它过）")
        out = json.dumps(self.m.settings(), ensure_ascii=False)
        for s in secrets:
            self.assertNotIn(s, out, "**凭据被回值了** —— 只许回形状 + 掩码")
        self.assertIn("掩码", out, "读设置时该出现掩码标记（说明真掩了）")

    # ---- E 写有闸 ----
    def test_e_writes_are_gated_and_whitelisted(self):
        for key in ("gatewayEnabled", "networkProxy.enableProxy", "encryptedTokens.accessToken",
                    "storagePath"):
            r = self.m.settings(key=key, set_value="x")
            self.assertFalse(r.get("ok"), f"{key} 竟然可写 ⇒ 安全姿态被能力位改了口子")
            self.assertTrue(r.get("refused") or r.get("denied"), f"{key} 拒绝理由不清：{r}")
        self.assertNotIn("gatewayEnabled", self.m.WRITABLE, "白名单里混进了安全姿态键")

    # ---- F 动作有门 ----
    def test_f_actions_never_fake_success(self):
        r = self.m.close(pid=999999)
        self.assertFalse(r.get("ok"), f"关一个不存在的进程竟报成功：{r}")
        self.assertTrue(r.get("denied") or r.get("errors") or r.get("error"), "被拒/失败都要说清")

    # ---- G 出网钉死 ----
    def test_g_egress_is_pinned(self):
        src = TOOL.read_text(encoding="utf-8")
        urls = set(re.findall(r'https?://[^\s"\')]+', src))
        hosts = {u.split("//", 1)[1].split("/")[0] for u in urls}
        self.assertTrue(all(h.startswith("127.0.0.1") for h in hosts),
                        f"出口主机必须是 127.0.0.1（实测：{sorted(hosts)}）")
        self.assertFalse(self.m._bridge_get(0, "/").get("ok"), "非法端口没拦住")
        self.assertFalse(self.m._bridge_get(33250, "no-slash").get("ok"), "非绝对路径没拦住")


if __name__ == "__main__":
    unittest.main(verbosity=2)
