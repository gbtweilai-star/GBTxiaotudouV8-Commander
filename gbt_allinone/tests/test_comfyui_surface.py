# -*- coding: utf-8 -*-
"""comfyui_surface 判据：**节点配置那一格必须原样落盘、可复算、不留残件** + 断连判据有牙。

跑法：`py -3.14 gbt_allinone/tests/test_comfyui_surface.py`
（**全程不联网**：只喂合成 payload 给纯函数，并把落盘路径改到临时目录 —— 不碰真 state/。）
"""
import ast
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import comfyui_surface as CS                # noqa: E402


class TestComfySurface(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="gbt_comfy_test_"))
        self._old_manifest, self._old_oi = CS._MANIFEST, CS._OBJECT_INFO
        CS._MANIFEST = self._tmp / "comfyui_surface.json"
        CS._OBJECT_INFO = self._tmp / "comfyui_object_info.json"

    def tearDown(self):
        CS._MANIFEST, CS._OBJECT_INFO = self._old_manifest, self._old_oi

    def test_persist_object_info_roundtrip(self):
        payload = {"KSampler": {"input": {"required": {"seed": ["INT", {"default": 0}]}},
                                "output": ["LATENT"], "output_name": ["LATENT"]},
                   "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["a.safetensors"]]}},
                                              "output": ["MODEL", "CLIP", "VAE"]}}
        r = CS._persist_object_info(payload)
        p = CS._OBJECT_INFO
        self.assertTrue(p.is_file(), "节点配置必须落盘")
        raw = p.read_bytes()
        self.assertEqual(r["bytes"], len(raw), r)
        self.assertEqual(r["sha16"], hashlib.sha256(raw).hexdigest()[:16], "sha 必须可复算")
        self.assertEqual(r["nodes"], 2, r)
        self.assertIn("input", r["样例字段"], r)
        back = json.loads(raw.decode("utf-8"))
        self.assertEqual(back["KSampler"]["output"], ["LATENT"], "必须**原样**落盘（不裁字段）")
        self.assertFalse(list(p.parent.glob("*.tmp")), "原子写不许留 .tmp 残件")

    def test_persist_is_overwrite_not_append(self):
        CS._persist_object_info({"A": {"output": ["X"]}})
        first = CS._OBJECT_INFO.read_bytes()
        CS._persist_object_info({"B": {"output": ["Y"]}})
        second = CS._OBJECT_INFO.read_bytes()
        self.assertNotEqual(first, second, "本体一变，这一格必须跟着变")
        self.assertEqual(list(json.loads(second.decode("utf-8"))), ["B"], "不是追加，是覆盖")

    def test_verify_has_teeth_on_missing_nodes_and_disconnect(self):
        # ① 没清单 ⇒ 必须报
        self.assertFalse(CS.verify()["ok"], "没清单不许判合格")
        # ② 节点数低于阈值 ⇒ 必须报「有漏」
        CS._MANIFEST.write_text(json.dumps({"nodes": ["a"], "counts": {"nodes": 1}, "gone": []}),
                                encoding="utf-8")
        v = CS.verify()
        self.assertFalse(v["ok"], v)
        self.assertTrue(any("阈值" in p for p in v["problems"]), v)
        # ③ 有节点消失 ⇒ 必须报「断连」（负控：不许静默）
        CS._MANIFEST.write_text(json.dumps(
            {"nodes": ["a"] * CS.MIN_NODES, "counts": {"nodes": CS.MIN_NODES}, "gone": ["X"]}),
            encoding="utf-8")
        v2 = CS.verify()
        self.assertFalse(v2["ok"], v2)
        self.assertTrue(any("断连" in p for p in v2["problems"]), v2)
        # ④ 阈值够 + 无消失 ⇒ 才算合格
        CS._MANIFEST.write_text(json.dumps(
            {"nodes": ["a"] * CS.MIN_NODES, "counts": {"nodes": CS.MIN_NODES}, "gone": []}),
            encoding="utf-8")
        self.assertTrue(CS.verify()["ok"], CS.verify())

    def test_contract_face(self):
        ops = {"status", "nodes", "models", "submit", "queue", "history", "free",
               "interrupt", "surface", "verify"}
        for op in ops:
            self.assertIsNotNone(getattr(CS, op, None), "缺 op：%s" % op)
        paths = {p for p, _w, _k in CS.API_ENDPOINTS}
        self.assertIn("/object_info", paths, "节点注册表必须在端点白名单里")
        kinds = {p: k for p, _w, k in CS.API_ENDPOINTS}
        self.assertEqual(kinds.get("/object_info"), "read", "读类端点不许标成写")
        self.assertIn("/prompt", paths)
        self.assertEqual(kinds.get("/prompt"), "write", "提交工作流是写类")
        self.assertGreaterEqual(len(CS.LAUNCH_FLAGS), 10, "启动开关面不许缩水")

    def test_surface_writes_object_info_when_body_answers(self):
        """surface() 里那一行必须真接上（用桩替掉 _http ⇒ **不联网**也能判它接没接）。"""
        seen = {}
        old_http = CS._http

        def fake_http(path, payload=None, timeout=300):
            seen.setdefault("paths", []).append(path)      # surface 之后还会取模型家族 ⇒ 记**全部**
            if path == "/object_info":
                return {"ok": True, "data": {"KSampler": {"output": ["LATENT"]}}}
            return {"ok": False, "error": "stub"}

        CS._http = fake_http
        try:
            r = CS.surface()
        finally:
            CS._http = old_http
        self.assertIn("/object_info", seen.get("paths") or [], seen)
        self.assertTrue(r["ok"], r)
        self.assertIn("节点配置", r, "surface 的返回里必须带这一格（不然等于没接）")
        self.assertEqual(r["节点配置"]["nodes"], 1, r["节点配置"])
        self.assertTrue(CS._OBJECT_INFO.is_file(), "surface 必须真把它落盘")

    def test_no_cut_fields_static(self):
        """静态判据：那一格是**原样落盘**，不许出现"只存名字"的写法。"""
        src = (_REPO / "gbt_allinone" / "tools" / "comfyui_surface.py").read_text(encoding="utf-8")
        ast.parse(src)
        self.assertIn("_persist_object_info(r[\"data\"])", src,
                      "surface() 必须把 /object_info 的**原始 data** 交给落盘函数")


if __name__ == "__main__":
    unittest.main(verbosity=2)
