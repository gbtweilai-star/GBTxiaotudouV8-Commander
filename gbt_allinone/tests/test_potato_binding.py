"""土豆大模型 · 双向互绑契约（2026-09-26 主人令「互绑双向」）· 有牙版。

钉死三条，缺一条即红：
  1. 能源池读数里有 qwen-local（endpoint=8111，接线态）——framework 侧绑定不许丢；
  2. web profile（cordis.patch.yml）里有 gbt-local（gbt-potato-v8 @ 8111）——dsh 侧绑定不许丢；
  3. 主配置（settings.yaml）llm-pi-ai.providers 里有 gbt-local——主 profile 与 web profile 同参，
     「互绑双向」= 两侧都看得见同一个模型 id，一处漂移就红。
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest

os.environ.setdefault("GBT_STORE_DIR", str(pathlib.Path(os.environ.get("TEMP", "/tmp")) / "gbt_potato_bind_store"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # 仓根入 path（直接跑文件姿势）

import yaml  # noqa: E402

from gbt_allinone.tools import energy_pool  # noqa: E402

_HOME = pathlib.Path.home()
_CORDIS = _HOME / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
_SETTINGS = _HOME / ".dsh" / "settings.yaml"


def _find_key(obj, key):
    """递归找 dict 键，返回第一个命中的值（结构漂移也不误报）。"""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


class PotatoBindingTest(unittest.TestCase):
    def test_energy_pool_has_local_source(self) -> None:
        rows = [e["name"] for e in energy_pool.list_energies()]
        self.assertIn("qwen-local", rows, "能源池丢了本地端点 —— framework 侧互绑断了")
        src = [s for s in energy_pool.build_sources() if s.source_id == "qwen-local"]
        self.assertTrue(src, "build_sources 丢了本地端点")
        self.assertEqual(src[0].endpoint, "http://127.0.0.1:8111/v1")

    def test_web_profile_has_gbt_local(self) -> None:
        d = yaml.safe_load(_CORDIS.read_text(encoding="utf-8"))
        prov = _find_key(d, "gbt-local")
        self.assertIsNotNone(prov, "web profile 丢了 gbt-local —— dsh 侧互绑断了")
        self.assertEqual(prov.get("baseURL"), "http://127.0.0.1:8111/v1")
        models = prov.get("models") or []
        self.assertIn("gbt-potato-v8", [m.get("id") for m in models])

    def test_main_settings_has_gbt_local(self) -> None:
        d = yaml.safe_load(_SETTINGS.read_text(encoding="utf-8"))
        prov = _find_key(d, "gbt-local")
        self.assertIsNotNone(prov, "主配置丢了 gbt-local —— 主 profile 与 web profile 没同参")
        self.assertIn("gbt-potato-v8", [m.get("id") for m in (prov.get("models") or [])])

    def test_two_sides_agree(self) -> None:
        """互绑双向 = 两侧指向同一个端点、同一个模型 id。"""
        a = _find_key(yaml.safe_load(_CORDIS.read_text(encoding="utf-8")), "gbt-local")
        b = _find_key(yaml.safe_load(_SETTINGS.read_text(encoding="utf-8")), "gbt-local")
        self.assertEqual(a.get("baseURL"), b.get("baseURL"), "两侧 baseURL 漂了")
        self.assertEqual([m["id"] for m in a["models"]], [m["id"] for m in b["models"]],
                         "两侧模型 id 漂了")


if __name__ == "__main__":
    unittest.main(verbosity=2)
