"""密钥"自动读取"这条链的常设判据（2026-09-25 主人令之后立）。

主人令：「密钥全部部署跟双向插件一样的就好了，可以自动读取」
落点 = 本仓自己的机制：`gbt_allinone/deepseek_key.py` 的 DPAPI 保险箱
（`store/secrets/<profile>.dpapi`，DPAPI/CurrentUser + **每个 profile 各自的熵值**）
    + `deepseek_key inject --profile <名> -- <cmd>` 运行时解密注入环境变量。

立它是因为现实里出过这件事：`config/mcporter.json` 里被人直接写了一条**明文 API key**
（掩码 `b3f4****`）。光"这次搬走了"不够 —— 下次照样能被写回去，所以要有判据盯着。

判据（六条，都要有牙）：
  1. `adp` profile 在册，且**有自己独立的熵值**（"互不可解"是机制，不是约定）；
  2. 形状校验**按 profile 分**：deepseek/agnes 仍然只认 sk-/ak-（**不许被放松**），
     adp 收纯十六进制长串 —— 两边都有正/负对照；
  3. `config/mcporter.json` 里**不许有任何明文密钥**（三条靶向规则 + 反向自证）；
  4. `adp` 这条 MCP 服务必须**走保险箱注入器**（点名 deepseek_key.py / inject / --profile adp），
     且它的 `env` 是空的 —— 密钥不许在配置里；
  5. **没有密钥时必须拒绝启动子进程**（fail-closed）：真起一次子进程验，证前提再判行为；
  6. 反向自证：靶向规则本身能抓到"一条明文密钥"（否则上面那条是空转）。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "config" / "mcporter.json"
VAULT_CLI = ROOT / "gbt_allinone" / "deepseek_key.py"
sys.path.insert(0, str(ROOT))

from gbt_allinone import deepseek_key as dk  # noqa: E402

# 靶向的"这看起来就是一条密钥"规则（宁窄勿滥：只打真正的密钥形状）
SECRET_SHAPES = [
    (re.compile(r"^[A-Fa-f0-9]{24,}$"), "纯十六进制长串（如 ADP 那种）"),
    (re.compile(r"^(?:sk|ak)[-_][A-Za-z0-9_\-]{16,}$"), "sk-/ak- 开头的长串"),
    (re.compile(r"^[A-Za-z0-9_\-]{32,}$"), "32 位以上的单行长串"),
]


def _walk_strings(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_strings(v, "%s[%d]" % (path, i))
    elif isinstance(node, str):
        yield path, node


class KeyVaultProfilesTest(unittest.TestCase):
    def test_adp_profile_declared_with_its_own_entropy(self) -> None:
        self.assertIn("adp", dk._PROFILES, "adp profile 不在保险箱表里")
        spec = dk._PROFILES["adp"]
        self.assertEqual(spec["env"], "ADP_API_KEY")
        self.assertTrue(spec["entropy"].startswith(b"GBTxiaotudouV8:adp:"),
                        "adp 必须有自己的熵值前缀")

    def test_entropies_are_pairwise_distinct(self) -> None:
        ent = [v["entropy"] for v in dk._PROFILES.values()]
        self.assertEqual(len(ent), len(set(ent)), "有两个 profile 用了同一套熵值 ⇒ 互不可解不成立")

    def test_pattern_is_per_profile_and_does_not_loosen_existing(self) -> None:
        hexish = "b3f4" + "0" * 28
        # 正控：adp 收纯十六进制长串
        self.assertEqual(dk._validate(hexish, "adp"), hexish)
        # 负控：deepseek / agnes **不许**因为加了 adp 而放松
        for p in ("deepseek", "agnes"):
            with self.assertRaises(dk.DeepseekKeyError, msg="%s 被放松了" % p):
                dk._validate(hexish, p)
        # 负控：adp 也不是什么都收
        with self.assertRaises(dk.DeepseekKeyError):
            dk._validate("abc", "adp")

    def test_secret_shapes_rule_has_teeth(self) -> None:
        """第 6 条：规则本身得能抓到一条真密钥（否则第 3 条是空转）。

        ⚠️ 这里的样例必须是**编的**：第一版我把真实的 32 位值抄进来当样例，
        结果自己的"提交前凭据扫描"当场抓到（明文在暂存 diff 里出现 1 次）。
        样例只用来证明规则有牙，**不需要也不许是真钥匙**。
        """
        sample = "0123456789abcdef0123456789abcdef"
        self.assertTrue(any(r.match(sample) for r, _ in SECRET_SHAPES),
                        "靶向规则抓不到一条 32 位十六进制密钥 ⇒ 判据没牙")
        self.assertFalse(any(r.match("C:/Users/ADMIN/Desktop/GBT/repo/tools/x.js") for r, _ in SECRET_SHAPES))
        self.assertFalse(any(r.match("streamablehttp") for r, _ in SECRET_SHAPES))
        self.assertFalse(any(r.match("oauth") for r, _ in SECRET_SHAPES))

    def test_mcporter_config_has_no_plaintext_secret(self) -> None:
        cfg = json.loads(CFG.read_text(encoding="utf-8"))
        hits = []
        for path, val in _walk_strings(cfg):
            for rule, why in SECRET_SHAPES:
                if rule.match(val.strip()):
                    hits.append("%s 看着像密钥（%s）" % (path, why))
        self.assertEqual(hits, [], "配置里出现明文密钥：%s" % hits)
        # 更硬的一条：任何 mcpServers 条目的 env 都不许带值
        for name, entry in (cfg.get("mcpServers") or {}).items():
            env = entry.get("env") or {}
            self.assertEqual(env, {}, "mcpServers.%s.env 不该有内容（密钥走保险箱）" % name)

    def test_adp_routes_through_the_vault_injector(self) -> None:
        cfg = json.loads(CFG.read_text(encoding="utf-8"))
        adp = (cfg.get("mcpServers") or {}).get("adp") or {}
        joined = " ".join([str(adp.get("command", ""))] + [str(a) for a in (adp.get("args") or [])])
        self.assertIn("deepseek_key.py", joined, "adp 没走保险箱注入器")
        self.assertIn("inject", joined)
        self.assertIn("--profile", joined)
        self.assertIn("adp", joined)

    def test_inject_refuses_to_start_without_a_key(self) -> None:
        """fail-closed：先证前提（这个 profile 确实没密钥），再判行为（拒绝启动子进程）。"""
        empty_vault = str(Path(os.environ.get("TEMP", ".")) / "no-such-vault-for-test.dpapi")
        env = dict(os.environ)
        env["GBT_ADP_SECRET_FILE"] = empty_vault
        env["ADP_API_KEY"] = ""
        env.pop("GBT_ADP_KEY", None)
        env["PYTHONIOENCODING"] = "utf-8"

        # 前提：status 必须报未配置（否则下面那条就是在验别的场景）
        st = subprocess.run([sys.executable, str(VAULT_CLI), "status", "--profile", "adp"],
                            cwd=str(ROOT), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env, timeout=120)
        info = json.loads(st.stdout[st.stdout.find("{"):])
        self.assertFalse(info["configured"], "前提不成立：这个 profile 居然有密钥 ⇒ 负控选错对象了")
        self.assertEqual(info["source"], "missing")

        # 行为：必须退 3 且**子进程一次都没跑**
        marker = "CHILD-SHOULD-NOT-RUN"
        p = subprocess.run([sys.executable, str(VAULT_CLI), "inject", "--profile", "adp", "--",
                            sys.executable, "-c", "print('%s')" % marker],
                           cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=120)
        out = (p.stdout or "") + (p.stderr or "")
        self.assertEqual(p.returncode, 3, "没有密钥时居然没拒绝：rc=%s out=%s" % (p.returncode, out[-200:]))
        self.assertNotIn(marker, out, "子进程跑了 ⇒ fail-closed 不成立")
        self.assertIn("拒绝在没有密钥的情况下启动子进程", out)


if __name__ == "__main__":
    unittest.main()
