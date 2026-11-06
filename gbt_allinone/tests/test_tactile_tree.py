# -*- coding: utf-8 -*-
"""触手树判据 · 以触手为权重的连通图（2026-11-04）。

钉死四件事，都可机检、不靠人眼：

  A. **权重真的分开了**：边权必须按 `cap/dispatch > path > cap_mention` 排序。
     来历：原 `wiring.json` 的 `adj` 是 `set`，四类边平权，83529 行原始边里
     重复出现的共现次数被 `set.add()` 抹掉 —— 图只能说"通不通"，
     说不了"谁更该被点亮"。这条判据防止改回平权。

  B. **种子三级取证，且每级都可验证**：
       ① 字面（能力位名 / 文件名 / 页面路径）—— 命中就不再扩散，最优先
       ② 段锚（`capability_router` 判类 + 摄像头词表）
       ③ 一跳邻居扩展
     **「没有任何证据」必须落 `needs_input`**，不许猜。
     `今天天气怎么样` 是反例样本；关掉段锚后 `看看房间` 也必须落空 ——
     这一条用来证明它靠的是词表，不是隐式猜测。

     摄像头那一类补在本模块（`CAMERA_WORDS` / `CAMERA_PLACE`），
     **不动 `capability_router` 的四类契约**。来历：AGENTS.md 4.1 记的
     see_camera L1 血账依赖 `router.py` + `intent_extracted.json`，
     而这两个文件在本树不存在，所以「打开摄像头拍一张」曾被判成
     "四类都没命中 ⇒ 交给对话模型"。屏幕 / 真实世界的边界（body_eye vs
     see_camera）在这里被钉死。

  C. **加载 30 秒内不可用就红**：传播 p50 必须 < 200ms（12 迭代）。
     实测 16.6ms，留 12× 余量给机器抖动；这条是防"越改越慢"。
     它不是性能炫耀 —— 是「秒级响应」的唯一可判定形式。

  D. **不许塌缩**：不同种子必须给出不同 top1。塌缩成同一个热点 = 图退化成一个 hub。

数据源缺席（`outputs/repo-pack/edges.jsonl` 只在生产树生成、`state/model-pack/`
被 `.gitignore:419 state/*/` 忽略）时，整类跳过而不是红 ——
按裁决 B：外部/本地产物缺席用 skip，不许假装通过，也不许把"没数据"当"接线不全"。
"""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

# 仓根注入：直跑（`python gbt_allinone/tests/test_x.py`）时 `sys.path[0]` 是
# **tests 目录**而不是仓根 ⇒ `import gbt_allinone` 抛 ModuleNotFoundError。
# `run-all-tests.py` 的 docstring 记过同一个坑（第一版跑法就这么错的）。
# 在这里自补，让本文件既能被 `unittest discover` 收走，也能单文件直跑。
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gbt_allinone import tactile_tree as tt  # noqa: E402

EDGES = ROOT / "outputs" / "repo-pack" / "edges.jsonl"

DATA_READY = EDGES.is_file()


@unittest.skipUnless(DATA_READY, "缺 outputs/repo-pack/edges.jsonl（本地产物，先跑 repo-pack.py refs）")
class TestTactileWeight(unittest.TestCase):
    """A · 权重分层"""

    @classmethod
    def setUpClass(cls):
        r = tt.run("build")
        if not r.get("ok"):
            raise unittest.SkipTest("建树失败：%s" % (r.get("why") or r.get("error")))

    def test_kind_base_is_ordered(self):
        """cap/dispatch 必须重于 path，path 必须重于 cap_mention。"""
        b = tt.KIND_BASE
        self.assertGreater(b["cap"], b["cap_mention"])
        self.assertGreater(b["dispatch"], b["path"])
        self.assertGreater(b["path"], b["cap_mention"])
        self.assertGreater(b["cap_mention"], 0, "弱边不能是 0，否则等于删边")

    def test_weak_edges_not_in_strong(self):
        """cap_mention 只能算弱边 —— 与 wiring-build 的 WEAK_KINDS 同口径。"""
        self.assertEqual(tt.WEAK_KINDS, {"cap_mention"})

    def test_node_kinds_match_wiring(self):
        """cap 节点数必须等于能力位总数（427）；page/code 都要非空。"""
        meta = json.loads(tt.TREE_META.read_text(encoding="utf-8"))
        self.assertEqual(meta["kinds"]["cap"], 427,
                         "cap 节点数漂了：能力位是契约，不能多也不能少")
        self.assertGreater(meta["kinds"]["page"], 0, "page 节点为 0 = 路径解析退化成全 code")
        self.assertGreater(meta["kinds"]["code"], 0)

    def test_usage_weight_applied(self):
        """真实调用权重必须真落到节点上（覆盖率 > 0）。"""
        meta = json.loads(tt.TREE_META.read_text(encoding="utf-8"))
        self.assertGreater(meta["node_w_covered"], 50,
                           "真实调用权重覆盖太少：编排账本没读到或路径错了")


@unittest.skipUnless(DATA_READY, "缺 edges.jsonl")
class TestTactileSeed(unittest.TestCase):
    """B · 种子只认字面证据"""

    def test_no_guess_without_any_evidence(self):
        """字面、段锚都没有时，必须返回空，不许猜。"""
        seeds, _ = tt.seed_from_query("今天天气怎么样")
        self.assertEqual(seeds, {}, "没有任何证据时必须返回空，不许猜")

    def test_literal_only_when_router_off(self):
        """关掉判类后，「看看房间」必须落空 —— 证明它靠的是段锚词表，不是猜。"""
        seeds, _ = tt.seed_from_query("看看房间", use_router=False)
        self.assertEqual(seeds, {}, "关掉判类还有命中 = 有未声明的隐式猜测")

    def test_camera_anchor(self):
        """摄像头 / 真实世界 → see_camera（capability_router 四类里没有这一类）。"""
        for q in ("打开摄像头拍一张", "看看房间", "看看外面"):
            r = tt.run("route", query=q, topk=1)
            self.assertTrue(r.get("ok"), "%r 没命中：%s" % (q, r.get("why")))
            self.assertEqual(r["top"][0]["node"], "see_camera", "%r 判错了" % q)

    def test_screen_anchor(self):
        """屏幕 → body_eye。屏幕与真实世界的边界是 AGENTS.md 4.1 钉死的。"""
        for q in ("帮我看下屏幕", "截个屏"):
            r = tt.run("route", query=q, topk=1)
            self.assertTrue(r.get("ok"), "%r 没命中" % q)
            self.assertEqual(r["top"][0]["node"], "body_eye", "%r 判错了" % q)

    def test_camera_words_need_verb(self):
        """「整理房间的待办」没有"看"类动词，不该被 camera 词抢走。"""
        r = tt.run("route", query="整理房间的待办", topk=1)
        self.assertEqual(r["status"], "needs_input",
                         "被 camera 词误伤了：%s" % (r.get("top") or r.get("why")))

    def test_literal_beats_anchor(self):
        """字面命中优先于段锚：句子里有能力位名时不许被判类改道。"""
        r = tt.run("route", query="看看 look_grade 的调色", topk=1)
        self.assertEqual(r["top"][0]["node"], "look_grade")

    def test_cap_name_hits(self):
        seeds, _ = tt.seed_from_query("look_grade 调色不对")
        self.assertIn("cap:look_grade", seeds)

    def test_filename_hits(self):
        seeds, _ = tt.seed_from_query("wiring-build.py 坏了")
        self.assertTrue(any(n.endswith("wiring-build.py") for n in seeds),
                        "文件名没被认成种子：%s" % sorted(seeds))

    def test_longer_cap_name_wins(self):
        """body_eye 不该被更短的 body 抢走。"""
        seeds, _ = tt.seed_from_query("body_eye 截图")
        self.assertIn("cap:body_eye", seeds)


@unittest.skipUnless(DATA_READY, "缺 edges.jsonl")
class TestTactileContract(unittest.TestCase):
    """三态契约"""

    def test_empty_query_is_needs_input(self):
        r = tt.run("route", query="")
        self.assertEqual(r["status"], "needs_input")
        self.assertFalse(r["ok"])

    def test_unknown_op_is_needs_input(self):
        r = tt.run("no_such_op")
        self.assertEqual(r["status"], "needs_input")

    def test_missing_node_is_needs_input(self):
        r = tt.run("neighbors", node="cap:never_exists_xyz")
        self.assertEqual(r["status"], "needs_input")

    def test_missing_tree_is_needs_dependency(self):
        """没建树时不许抛裸异常，要落 needs_dependency。"""
        saved = dict(tt._CACHE)
        try:
            tt._CACHE.clear()
            mp = tt.TREE_META
            bak = mp.with_suffix(".meta.bak")
            if mp.is_file():
                mp.rename(bak)
            try:
                r = tt.run("stats")
                self.assertEqual(r["status"], "needs_dependency")
            finally:
                if bak.is_file():
                    bak.rename(mp)
        finally:
            tt._CACHE.clear()
            tt._CACHE.update(saved)

    def test_route_shape(self):
        r = tt.run("route", target="cap:impact_check", topk=5)
        self.assertTrue(r["ok"])
        self.assertLessEqual(len(r["top"]), 5)
        for row in r["top"]:
            for k in ("node", "score", "activation", "usage_w", "share"):
                self.assertIn(k, row)


@unittest.skipUnless(DATA_READY, "缺 edges.jsonl")
class TestTactileLatency(unittest.TestCase):
    """C/D · 秒级 + 不塌缩"""

    def test_propagation_is_subsecond(self):
        r = tt.run("bench", rounds=12)
        self.assertTrue(r["ok"])
        self.assertLess(r["p50_ms"], 200.0,
                        "传播 p50=%s ms，超过 200ms 守门线（实测应 ~17ms）" % r["p50_ms"])

    def test_no_collapse(self):
        """不同种子 → 不同 top1。全撞同一个节点 = 图退化。"""
        names = tt._load()["nodes"]
        caps = [n for n in names if n.startswith("cap:")]
        step = max(1, len(caps) // 20)
        tops = []
        for i in range(0, len(caps), step):
            r = tt.run("route", target=caps[i], topk=1)
            if r.get("ok") and r["top"]:
                tops.append(r["top"][0]["node"])
        self.assertGreaterEqual(len(tops), 10, "样本太少，判据无意义")
        uniq = len(set(tops))
        self.assertEqual(uniq, len(tops),
                         "塌缩了：%d 个样本只给出 %d 个不同的 top1" % (len(tops), uniq))


@unittest.skipUnless(DATA_READY, "缺 edges.jsonl")
class TestTactileHint(unittest.TestCase):
    """E · 提示层（接进 /api/chat 的那个）。三条判据：

      · 明确的句子要给候选，且 top1 对
      · 模糊的句子要**承认不知道**（needs_input），不许硬给
      · `confident` 只是「值得提示」，代码里写死了不许拿去执行 ——
        这条测不了执行，但可以钉住"它不随明确度乱跳"
    """

    def test_confident_on_clear_query(self):
        r = tt.run("hint", query="impact_check 看一下 api.py")
        self.assertTrue(r.get("ok"), r.get("why"))
        self.assertTrue(r["confident"], "明确句没给 confident：%s" % r.get("judge"))
        self.assertEqual(r["top"][0]["node"], "impact_check")

    def test_needs_input_on_vague_query(self):
        """模糊句必须落 needs_input —— 宁可说不知道，也不硬给候选。"""
        for q in ("看看这个", "帮我弄一下", "那个东西怎么样了", "今天天气怎么样"):
            r = tt.run("hint", query=q)
            self.assertEqual(r["status"], "needs_input",
                             "%r 竟然给了候选：%s" % (q, r.get("top")))

    def test_hint_is_cheap(self):
        """提示层接在 LLM 之前，不许成为新瓶颈（对照 energy_core 21.6s）。"""
        lat = []
        for i in range(10):
            t0 = time.perf_counter()
            tt.run("hint", query="打开摄像头拍一张")
            lat.append((time.perf_counter() - t0) * 1000)
        lat.sort()
        self.assertLess(lat[len(lat) // 2], 200.0,
                        "hint p50=%s ms，超 200ms 就会拖慢对话" % lat[len(lat) // 2])

    def test_hint_carries_judge(self):
        """回执必须自带判据，否则事后无法复核为什么给了/没给候选。"""
        r = tt.run("hint", query="截个屏")
        self.assertIn("judge", r)
        for k in ("share", "ratio", "min_share", "min_ratio"):
            self.assertIn(k, r["judge"])


@unittest.skipUnless(DATA_READY, "缺 edges.jsonl")
class TestTactilePulse(unittest.TestCase):
    """F · 脉冲直达（主人令：运行不按原来的跑法，按触手互通精准直达）。

    三条硬判据，缺一条这条路就不安全：
      · 该直达的必须直达，且 **op 与参数都对**（选错 op = 成功返回一个没被问的东西）
      · 不在只读白名单的必须 `denied`（摄像头 / 写盘那一类永远不许直达）
      · 参数抽不到必须 `needs_input`，不许拿"猜"补参数
    """

    def test_pulse_ready_with_path(self):
        r = tt.run("pulse", query="impact_check 看一下 gbt_allinone/api.py 会影响谁")
        self.assertTrue(r.get("ok"), r.get("why"))
        self.assertEqual(r["status"], "ready")
        self.assertEqual(r["cap"], "impact_check")
        self.assertEqual(r["op"], "impact", "有路径时必须走 impact，不是 status")
        self.assertIn("api.py", r["params"]["target"])

    def test_pulse_denied_outside_whitelist(self):
        """摄像头不在只读白名单 —— 走直达等于跳过门禁，必须拒。"""
        for q in ("打开摄像头拍一张", "看看房间"):
            r = tt.run("pulse", query=q)
            self.assertFalse(r.get("ok"))
            self.assertEqual(r["status"], "denied", "%r 竟然放行：%s" % (q, r))
            self.assertIn("白名单", r.get("why", ""))

    def test_pulse_needs_input_without_params(self):
        """命中了但抽不到路径 —— 必须 needs_input，不许猜一个 target。"""
        r = tt.run("pulse", query="impact_check 看一下")
        self.assertFalse(r.get("ok"))
        self.assertEqual(r["status"], "needs_input")

    def test_pulse_needs_input_on_vague(self):
        self.assertEqual(tt.run("pulse", query="今天天气怎么样")["status"], "needs_input")


@unittest.skipUnless(DATA_READY, "缺 edges.jsonl")
class TestTactileWholePage(unittest.TestCase):
    """G · 整页脉冲（主人令：「触手覆盖每一页整页脉冲推进」）。

    判据只有一条但很硬：**定位过程不许读整页**。
    4769 个页面共 109.4 MB，逐页 open 就是慢的根源；
    `locate` 必须只靠内存索引给「哪一页 · 第几行」。
    """

    def test_locate_returns_page_and_line(self):
        r = tt.run("locate", query="脉冲直达是怎么实现的", topk=4)
        self.assertTrue(r.get("ok"), r.get("why"))
        self.assertEqual(r.get("read_files"), 0, "定位过程读了文件，退回了逐页读")
        hits = r.get("hits") or []
        self.assertTrue(hits, "没有命中任何页内段落")
        self.assertTrue(any(h.get("line") for h in hits), "命中没带行号，等于还得再找")

    def test_locate_covers_non_python_pages(self):
        """非 .py 页面（.md/.html/.json）必须能命中 —— 这是"覆盖每一页"的定义。"""
        r = tt.run("locate", query="脉冲直达", topk=8)
        pages = [str(h.get("page") or "") for h in (r.get("hits") or [])]
        self.assertTrue(any(p.endswith(".md") for p in pages),
                        "文档页没进索引：%s" % pages[:5])

    def test_locate_latency(self):
        """热调用必须够快（冷加载 11MB 索引另计）。"""
        tt.run("locate", query="预热", topk=2)          # 先付一次冷加载
        t0 = time.perf_counter()
        tt.run("locate", query="脉冲直达", topk=4)
        ms = (time.perf_counter() - t0) * 1000
        self.assertLess(ms, 500.0, "locate 热调用 %s ms，定位本身不该这么慢" % ms)

    def test_tree_comes_from_wiring(self):
        """传播图必须与多域监控同一张（否则"打通没"根本答不了）。"""
        d = tt.run("diag")
        self.assertEqual(d.get("tree_source"), "wiring.json",
                         "还在用自建的旧图，与 impact_check 漂了")
        self.assertEqual(d.get("weight_rule_drift"), False,
                         "wiring.json 与本地口径不一致")

    def test_graph_fully_connected(self):
        """全部关联打通：目录树层补齐后，不该再有多个连通分量。"""
        meta = json.loads(tt.TREE_META.read_text(encoding="utf-8"))
        self.assertEqual(meta.get("source"), "wiring.json")
        self.assertGreater(meta.get("dirs", 0), 0, "没有目录节点 = 目录树层没生效")
        self.assertGreaterEqual(meta["nodes"], 6000, "节点数没涨 = 孤儿文件还没接进来")


if __name__ == "__main__":
    unittest.main(verbosity=2)
