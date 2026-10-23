# -*- coding: utf-8 -*-
"""checkpoint（阶段级检查点打点器）契约测试 —— 落生产 ③ 的随行契约。

守的是《阶段检查点打点器设计》里那几条会被"悄悄放宽"的口径：

  * 退出码即结论：0 / 10 / 11 / 12 / 13 / 22；20·21 是探针族专用，**不许复用**
  * 三态互斥：缺失(10 灰) / 损坏(11) / 自盲(12) —— 「抓不到」必须报 12，不许报 0 或 10
  * 撕裂拷贝必报错(13)：拷完重算指纹，必须与源指纹相等
  * 恢复默认只读，**显式 --go 才写**；恢复后指纹必须回到记录，且不动 timelines / 护照
  * 未识别条目**显式登记**，不许静默跳过（《空不等于不存在律》）
  * 自证臂的结论必须互相不同（否则"全绿"没有判别性）
  * 对 dimension / reality **只读**

测试隔离：整套只在 tempfile 里造 store，绝不碰生产 `gbt_allinone/store/`。
"""
import importlib.util
import os
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

_HERE = Path(__file__).resolve().parent
_PKG = _HERE.parent            # gbt_allinone/
_ROOT = _PKG.parent            # 项目根
CHECKPOINT_PY = _PKG / "checkpoint.py"
MIRROR_PY = _PKG / "mirror_space.py"
MIRROR_PY_TWIN = _ROOT / "mirror_space.py"


def _load(path: Path, name: str):
    """按路径加载被测模块（与 tests/test_mirror_space.py 同路：避开包的重依赖）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CK = _load(CHECKPOINT_PY, "checkpoint_under_test")
MS = _load(MIRROR_PY, "mirror_space_under_test")


def _mk_store(base: Path, passports=(1, 9, 20)):
    """造一个够用的临时 store：维度 2 文件 / 现实 2 文件 / 护照 v1·v9·v20。"""
    paths = CK.Paths(base / "store")
    paths.dimension.mkdir(parents=True, exist_ok=True)
    paths.reality.mkdir(parents=True, exist_ok=True)
    paths.passports.mkdir(parents=True, exist_ok=True)
    paths.timelines.mkdir(parents=True, exist_ok=True)
    for root in (paths.dimension, paths.reality):
        (root / "index.html").write_text("A" * 32, encoding="utf-8")
        (root / "holo_pet_w3").mkdir(exist_ok=True)
        (root / "holo_pet_w3" / "main.cjs").write_text("M" * 64, encoding="utf-8")
    for v in passports:
        (paths.passports / ("v%d.json" % v)).write_text("{}", encoding="utf-8")
    return paths


class _TmpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gbt_checkpoint_"))
        # 生产树隔离：与 GBT_STORE_DIR 同构。不设的话，测试会去打**真实**生产树的指纹。
        self._prod_env_backup = os.environ.get("GBT_PROD_ROOT")
        os.environ["GBT_PROD_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._prod_env_backup is None:
            os.environ.pop("GBT_PROD_ROOT", None)
        else:
            os.environ["GBT_PROD_ROOT"] = self._prod_env_backup
        shutil.rmtree(self.tmp, ignore_errors=True)

    def store(self, **kw):
        return _mk_store(self.tmp, **kw)

    def fp(self, root: Path) -> str:
        return CK.tree_hash(CK.tree_fingerprint(root))


class TestExitCodeFamily(unittest.TestCase):
    """退出码即结论：族约定不许被后来的改动悄悄挪动。"""

    def test_codes_are_exactly_as_designed(self):
        codes = {CK.RC_OK, CK.RC_MISSING, CK.RC_DAMAGED,
                 CK.RC_BLIND, CK.RC_INTEGRITY, CK.RC_NO_VERDICT}
        self.assertEqual(codes, {0, 10, 11, 12, 13, 22})

    def test_probe_family_codes_are_not_reused(self):
        """20/21 是 W2.5 探针族的（进程不活 / 流断了）——本工具不许占用。"""
        codes = {CK.RC_OK, CK.RC_MISSING, CK.RC_DAMAGED,
                 CK.RC_BLIND, CK.RC_INTEGRITY, CK.RC_NO_VERDICT}
        self.assertNotIn(20, codes)
        self.assertNotIn(21, codes)


class TestThreeStatesAreMutuallyExclusive(_TmpCase):
    """缺失(10 灰) / 损坏(11) / 自盲(12) —— 三个状态互斥，且都不许退化成"没问题"。"""

    def test_empty_checkpoints_is_grey_missing(self):
        p = self.store()
        rc, pay = CK.do_status(p)
        self.assertEqual(rc, CK.RC_MISSING)
        self.assertEqual(pay["state"], "MISSING")
        self.assertFalse(pay["ok"])

    def test_unreadable_root_is_blind_not_missing(self):
        """「抓不到」≠「没有」：路径读不到必须 12，不许 0、不许 10。"""
        p = CK.Paths(self.tmp / "never_created")
        rc, pay = CK.do_status(p)
        self.assertEqual(rc, CK.RC_BLIND)
        self.assertEqual(pay["state"], "BLIND")
        self.assertFalse(p.store.exists(), "自盲路径下不许留下任何痕迹")

    def test_corrupt_record_is_damaged(self):
        p = self.store()
        bad = p.checkpoints / "00001"
        bad.mkdir(parents=True)
        (bad / "record.json").write_text("{ this is not json", encoding="utf-8")
        rc, pay = CK.do_status(p)
        self.assertEqual(rc, CK.RC_DAMAGED)
        self.assertEqual(pay["state"], "DAMAGED")

    def test_the_three_codes_are_pairwise_distinct(self):
        p = self.store()
        rc_missing, _ = CK.do_status(p)

        pc = self.store()
        bad = pc.checkpoints / "00001"
        bad.mkdir(parents=True)
        (bad / "record.json").write_text("{ nope", encoding="utf-8")
        rc_damaged, _ = CK.do_status(pc)

        pb = CK.Paths(self.tmp / "nope")
        rc_blind, _ = CK.do_status(pb)

        self.assertEqual(len({rc_missing, rc_damaged, rc_blind}), 3,
                         "三个状态码必须互不相同，否则没法诊断")


class TestCheckpointMakesRollbackPoint(_TmpCase):
    """打点：只读源树，只写 checkpoints/。"""

    def test_artifacts_and_copy_fingerprints(self):
        p = self.store()
        src_dim = self.fp(p.dimension)
        src_real = self.fp(p.reality)
        rc, pay = CK.do_checkpoint(p, "P07-01", goal="契约测试")
        self.assertEqual(rc, CK.RC_OK)
        self.assertTrue(pay["ok"])
        cid = pay["checkpoint_id"]
        root = p.checkpoints / cid
        self.assertTrue((root / "record.json").is_file())
        self.assertTrue((root / "dimension" / "index.html").is_file())
        self.assertTrue((root / "reality" / "index.html").is_file())
        self.assertEqual(self.fp(root / "dimension"), src_dim)
        self.assertEqual(self.fp(root / "reality"), src_real)
        rec = CK.get_record(p, cid)
        self.assertEqual(CK.verify_record(p, rec)["ok"], True)

    def test_sources_are_read_only(self):
        """打点不许改 dimension / reality，也不许动 timelines / 护照。"""
        p = self.store()
        before = (self.fp(p.dimension), self.fp(p.reality),
                  sorted(x.name for x in p.passports.iterdir()),
                  sorted(x.name for x in p.timelines.iterdir()))
        rc, _ = CK.do_checkpoint(p, "P07-02")
        self.assertEqual(rc, CK.RC_OK)
        after = (self.fp(p.dimension), self.fp(p.reality),
                 sorted(x.name for x in p.passports.iterdir()),
                 sorted(x.name for x in p.timelines.iterdir()))
        self.assertEqual(before, after)

    def test_timeline_version_is_numeric_max(self):
        """v1·v9·v20 → 20。《版本号字符串序陷阱》在这里同样适用。"""
        p = self.store(passports=(1, 9, 20))
        rc, pay = CK.do_checkpoint(p, "P07-03")
        self.assertEqual(rc, CK.RC_OK)
        self.assertEqual(pay["timeline_version"], 20)
        self.assertEqual(CK.timeline_version(p), 20)
        # 反证：字符串序会取到 v9 —— 证明上面那条不是空跑
        names = sorted(x.name for x in p.passports.glob("v*.json"))
        self.assertEqual(names[-1], "v9.json")
        self.assertNotEqual(names[-1], "v20.json")

    def test_same_phase_is_reused_not_overwritten(self):
        """回滚点不许被悄悄挪动：同 phase_id 再打 → 复用，目录数不变。"""
        p = self.store()
        rc1, pay1 = CK.do_checkpoint(p, "P07-04")
        rc2, pay2 = CK.do_checkpoint(p, "P07-04")
        self.assertEqual((rc1, rc2), (CK.RC_OK, CK.RC_OK))
        self.assertTrue(pay2.get("reused"))
        self.assertEqual(pay1["checkpoint_id"], pay2["checkpoint_id"])
        self.assertEqual(sorted(x.name for x in p.checkpoints.iterdir()
                                if x.is_dir() and x.name.isdigit()),
                         [pay1["checkpoint_id"]])

    def test_unrecognized_entries_are_listed_not_skipped(self):
        p = self.store()
        (p.checkpoints / "not_a_number").mkdir(parents=True)
        (p.checkpoints / "note.txt").write_text("x", encoding="utf-8")
        rc, pay = CK.do_status(p)
        names = pay["unrecognized"]
        self.assertIn("not_a_number", names)
        self.assertIn("note.txt", names)
        self.assertTrue(names, "未识别条目必须显式登记，不许静默跳过")


class TestTornCopyIsCaught(_TmpCase):
    """拷完重算指纹：相等才算数。不等 → 13（撕裂拷贝）。"""

    def test_tampered_copy_returns_integrity_failure(self):
        p = self.store()

        def tamper(root: Path) -> None:
            (Path(root) / "dimension" / "index.html").write_text("TAMPERED", encoding="utf-8")

        rc, pay = CK.do_checkpoint(p, "P07-05", on_copied=tamper)
        self.assertEqual(rc, CK.RC_INTEGRITY)
        self.assertEqual(pay.get("reason_code"), "torn_copy")

    def test_the_same_fixture_passes_without_tampering(self):
        """负对照的反面：同一 fixture、不注入故障 → 必须 0。
        证明上面那条红的是"注入"，不是 fixture 自己就红。"""
        p = self.store()
        rc, _ = CK.do_checkpoint(p, "P07-05")
        self.assertEqual(rc, CK.RC_OK)


class TestRestoreIsGatedBehindGo(_TmpCase):
    """默认只读，显式 --go 才写；恢复后指纹回到记录，且不动 timelines / 护照。"""

    def _dirty(self, p):
        rc, pay = CK.do_checkpoint(p, "P07-06")
        self.assertEqual(rc, CK.RC_OK)
        (p.dimension / "index.html").write_text("CHANGED-DIM", encoding="utf-8")
        (p.reality / "index.html").write_text("CHANGED-REAL", encoding="utf-8")
        return pay["checkpoint_id"]

    def test_default_restore_writes_nothing(self):
        p = self.store()
        cid = self._dirty(p)
        dim_before, real_before = self.fp(p.dimension), self.fp(p.reality)
        rc, pay = CK.do_restore(p, cid, go=False)
        self.assertEqual(rc, CK.RC_OK)
        self.assertTrue(pay.get("dry_run"))
        self.assertEqual(self.fp(p.dimension), dim_before)
        self.assertEqual(self.fp(p.reality), real_before)

    def test_go_restores_to_the_record(self):
        p = self.store()
        cid = self._dirty(p)
        rc, pay = CK.do_restore(p, cid, go=True)
        self.assertEqual(rc, CK.RC_OK)
        self.assertEqual(pay["fingerprint_ok"], True)
        rec = CK.get_record(p, cid)
        self.assertEqual(CK.tree_fingerprint(p.dimension), rec["dimension_manifest"])
        self.assertEqual(CK.tree_fingerprint(p.reality), rec["reality_manifest"])

    def test_restore_leaves_timelines_and_passports_alone(self):
        """回滚走的是检查点，不是 rewind() 那条时间线路径 —— 两套不许互相搅。"""
        p = self.store()
        cid = self._dirty(p)
        before = (sorted(x.name for x in p.passports.iterdir()),
                  sorted(x.name for x in p.timelines.iterdir()))
        CK.do_restore(p, cid, go=True)
        after = (sorted(x.name for x in p.passports.iterdir()),
                 sorted(x.name for x in p.timelines.iterdir()))
        self.assertEqual(before, after)


class TestSelftestIsDiscriminating(_TmpCase):
    """自带自证：全绿 + 结论互相不同。结论全一样 = 没有判别性 = 假绿。"""

    def test_selftest_passes_and_codes_differ(self):
        out = self.tmp / "selftest.json"
        rc, pay = CK.do_selftest(str(out))
        self.assertEqual(rc, CK.RC_OK)
        self.assertTrue(pay["ok"], pay)
        codes = [str(a["rc"]) for a in pay["arms"]]
        self.assertGreater(len(set(codes)), 1, "自证臂结论全一样 → 没有判别性")
        self.assertTrue(out.is_file())


class TestPublicAlias(_TmpCase):
    """设计 §九②：打点器不许靠私有名 tree_fingerprint ← 加公开别名，不复制逻辑。"""

    def test_mirror_space_exposes_the_alias(self):
        self.assertTrue(hasattr(MS, "tree_fingerprint"))
        self.assertIs(MS.tree_fingerprint, MS._tree_fingerprint,
                      "别名必须指向同一实现，不许另写一份")

    def test_both_mirror_copies_stay_byte_identical(self):
        """家根不许有影子；两份并存时才做逐字节比对（O49 归档后口径）。

        R118 修正：原断言无条件读家根 `mirror_space.py` —— 那是 **O49 家根影子
        大扫（2026-09-17）之前**的口径。归档后家根顶层 .py = 0，本用例恒
        `FileNotFoundError`（报的是 ERROR 不是 FAIL，且不在任何回归清单里）。
        常驻防线已改为 gbt_allinone/tools/shadow_check.py（门禁 W 维）。
        与 test_mirror_space.TestTwoCopiesStayInSync 同一口径，改法一致。
        """
        self.assertTrue(MIRROR_PY.exists(), str(MIRROR_PY))
        # 判别性自证：把"两份副本比对"喂给一对故意分叉的合成文件，必须看得出差。
        # 否则"家根无副本"的正常态下，下面那段比对等于空转（判据没牙）。
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a.py"
            b = Path(td) / "b.py"
            a.write_bytes(MIRROR_PY.read_bytes())
            b.write_bytes(a.read_bytes() + b"\n# drift\n")
            self.assertNotEqual(hashlib.sha256(a.read_bytes()).hexdigest(),
                                hashlib.sha256(b.read_bytes()).hexdigest(),
                                "合成分叉文件必须判得出不同 —— 判据没牙")
        if not MIRROR_PY_TWIN.exists():
            return   # O49 归档后的正常态：家根没有同名副本
        self.assertEqual(MIRROR_PY.read_bytes(), MIRROR_PY_TWIN.read_bytes(),
                         "两处副本分叉了——必须同步修")

    def test_checkpoint_uses_the_public_name(self):
        p = self.store()
        self.assertEqual(CK.tree_hash(CK.tree_fingerprint(p.dimension)),
                         CK.tree_hash(MS.tree_fingerprint(p.dimension)))


class TestProductionTreeManifest(_TmpCase):
    """规格 docs/checkpoint生产树指纹规格.md v1 —— C1–C5 五道闸门。

    这一节守的是：生产树**只读**、排除六条一条不许省、生成失败不静默、
    复算路径活着（改一个文件必须看得见，改回来必须消失）。
    """

    def prod(self):
        """造一棵够用的假生产树（含全部排除项 + 一个超限文件）。"""
        # 生产树与 store 分开：这样 C2 能主张"整棵假生产树一个字节都没动"，
        # 而不是"只动了 store/"。真实世界里 store 在树内 —— 靠 E5 排除规则挡住。
        r = self.tmp / "prod"
        os.environ["GBT_PROD_ROOT"] = str(r)
        (r / "holo_pet" / "shell").mkdir(parents=True, exist_ok=True)
        (r / "holo_pet" / "shell" / "main.cjs").write_text("M" * 64, encoding="utf-8")
        (r / "holo_pet" / "panel_server.py").write_text("P" * 48, encoding="utf-8")
        (r / "gbt_allinone").mkdir(exist_ok=True)
        (r / "gbt_allinone" / "api.py").write_text("A" * 32, encoding="utf-8")
        (r / "config").mkdir(exist_ok=True)
        (r / "config" / "mcporter.json").write_text("{}", encoding="utf-8")
        for junk, payload in (
                ("holo_pet/node_modules/x/index.js", "X"),
                ("gbt_allinone/store/mirror_space/audit.jsonl", "Y"),
                ("gbt_allinone/__pycache__/api.cpython-310.pyc", "Z"),
                ("holo_pet/.scratch/scratch.py", "S"),
                ("gbt_allinone/.pylibs/numpy/core.py", "V")):
            d = r / Path(junk).parent
            d.mkdir(parents=True, exist_ok=True)
            (r / junk).write_text(payload, encoding="utf-8")
        (r / "holo_pet" / "big.bin").write_bytes(b"0" * (CK.PROD_TREE_MAX_BYTES + 1))
        return r

    def paths(self):
        return self.store()

    def take(self, phase="PROD-MANIFEST"):
        p = self.paths()
        rc, payload = CK.do_checkpoint(p, phase, "C1..C5")
        self.assertEqual(rc, CK.RC_OK, payload)
        return p, Path(payload["dir"]), payload

    # C1 落盘且可解析 ------------------------------------------------------
    def test_c1_manifest_lands_next_to_record_and_parses(self):
        self.prod()
        p, d, payload = self.take()
        mp = d / CK.PROD_MANIFEST_NAME
        self.assertTrue(mp.is_file(), "manifest 必须与 record.json 同级")
        man = json.loads(mp.read_text(encoding="utf-8"))
        self.assertEqual(man["schema"], CK.PROD_TREE_SCHEMA)
        rec = json.loads((d / "record.json").read_text(encoding="utf-8"))
        self.assertTrue(rec["production_tree_manifest"]["ok"])
        self.assertEqual(rec["production_tree_manifest"]["files"],
                         man["summary"]["files"])
        self.assertGreater(man["summary"]["files"], 0)
        self.assertEqual(payload["production_tree"]["ok"], True)

    # C3 覆盖正确：排除六条一条都不许进去 --------------------------------
    def test_c3_exclusions_and_spot_check(self):
        self.prod()
        _p, d, _payload = self.take()
        man = json.loads((d / CK.PROD_MANIFEST_NAME).read_text(encoding="utf-8"))
        paths = [f["path"] for f in man["files"]]
        self.assertIn("holo_pet/shell/main.cjs", paths)
        self.assertIn("config/mcporter.json", paths)
        for banned in ("node_modules", "__pycache__", "store", ".scratch"):
            self.assertFalse([x for x in paths if banned in x],
                             f"排除项 {banned} 漏进 manifest")
        self.assertEqual(sorted(man["summary"]["excluded_dirs"]),
                         sorted(["node_modules", "__pycache__", "store", ".scratch",
                                 ".pylibs"]))
        # E7：规则要带"为什么"，不是写死路径（将来 vendored 依赖迁移只改规则行）
        rules = {r["dir"]: r["reason"] for r in man["summary"]["exclude_rules"]}
        self.assertIn(".pylibs", rules)
        self.assertIn("pip 生成的 vendored 依赖目录", rules[".pylibs"])
        self.assertEqual([s["path"] for s in man["summary"]["skipped_too_large"]],
                         ["holo_pet/big.bin"])
        self.assertEqual(man["root_source"], "GBT_PROD_ROOT")
        # 抽查：manifest 里的 sha256 与磁盘实测一致（不是抄来的）
        live = hashlib.sha256((Path(man["root"]) / "holo_pet" / "shell" / "main.cjs")
                              .read_bytes()).hexdigest()
        recorded = {f["path"]: f for f in man["files"]}["holo_pet/shell/main.cjs"]
        self.assertEqual(recorded["sha256"], live)
        self.assertIn("mtime", recorded)

    def test_missing_root_is_registered_not_silently_skipped(self):
        self.prod()          # 故意不造 potato_pet/
        self.prod()          # 故意不造 potato_pet/
        _p, d, _payload = self.take()
        man = json.loads((d / CK.PROD_MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual(man["summary"]["missing_roots"], ["potato_pet"],
                         "白名单根缺失必须显式登记（《空不等于不存在律》）")

    # C2 只读 --------------------------------------------------------------
    def test_c2_production_tree_is_read_only(self):
        r = self.prod()
        before = {}
        for f in sorted(r.rglob("*")):
            if f.is_file():
                before[str(f.relative_to(r))] = (f.stat().st_size,
                                                 hashlib.sha256(f.read_bytes()).hexdigest())
        self.take()
        after = {}
        for f in sorted(r.rglob("*")):
            if f.is_file():
                after[str(f.relative_to(r))] = (f.stat().st_size,
                                                hashlib.sha256(f.read_bytes()).hexdigest())
        self.assertEqual(before, after, "生产树被写过了 —— 规格 §三.1 只读")

    # C4 失败不静默 --------------------------------------------------------
    def test_c4_generation_failure_does_not_block_but_must_be_recorded(self):
        self.prod()
        p = self.paths()
        original = CK.production_tree_manifest

        def boom(_root):
            raise RuntimeError("人为打断")

        CK.production_tree_manifest = boom
        try:
            rc, payload = CK.do_checkpoint(p, "PROD-MANIFEST-BOOM", "失败不静默")
        finally:
            CK.production_tree_manifest = original
        self.assertEqual(rc, CK.RC_OK, "生成失败不许拖垮检查点本身")
        d = Path(payload["dir"])
        rec = json.loads((d / "record.json").read_text(encoding="utf-8"))
        self.assertFalse(rec["production_tree_manifest"]["ok"])
        self.assertIn("人为打断", rec["production_tree_manifest"]["error"])
        self.assertFalse((d / CK.PROD_MANIFEST_NAME).exists())
        # 负对照：同一个 phase 在修好后必须能打出 ok=True（两组结果不同）
        rc2, payload2 = CK.do_checkpoint(p, "PROD-MANIFEST-OK", "修好后")
        self.assertEqual(rc2, CK.RC_OK)
        self.assertTrue(payload2["production_tree"]["ok"])

    # C5 可复算 ------------------------------------------------------------
    def test_c5_recompute_sees_modified_added_removed_and_clean_again(self):
        r = self.prod()
        p, d, payload = self.take()
        cid = payload["checkpoint_id"]

        def drift():
            rc, out = CK.do_diff(p, cid)
            self.assertEqual(rc, CK.RC_OK)
            return {x["file"]: x["kind"] for x in out["production_tree"]["drift"]}

        self.assertEqual(drift(), {}, "刚打完点就报差异 = 判据坏了")

        (r / "holo_pet" / "shell" / "main.cjs").write_text("M" * 63 + "X",
                                                           encoding="utf-8")
        got = drift()
        self.assertEqual(got.get("holo_pet/shell/main.cjs"), "modified")
        self.assertEqual(len(got), 1, "只改一个文件，只许报一条")

        (r / "holo_pet" / "new_file.txt").write_text("N", encoding="utf-8")
        self.assertEqual(drift().get("holo_pet/new_file.txt"), "added")

        (r / "config" / "mcporter.json").unlink()
        self.assertEqual(drift().get("config/mcporter.json"), "removed")

        # 改回来 → 差异必须消失（两组结果不同，判据才有判别性）
        (r / "holo_pet" / "shell" / "main.cjs").write_text("M" * 64, encoding="utf-8")
        (r / "holo_pet" / "new_file.txt").unlink()
        (r / "config" / "mcporter.json").write_text("{}", encoding="utf-8")
        self.assertEqual(drift(), {})

    def test_status_reports_production_tree_only_when_recorded(self):
        self.prod()
        p, _d, _payload = self.take()
        rc, out = CK.do_status(p)
        self.assertEqual(rc, CK.RC_OK)
        self.assertTrue(out["production_tree"]["ok"])
        self.assertEqual(out["production_tree"]["drift_count"], 0)

    # 边界 2：排除之后不许"什么都报不出来"（否则排除变成静默失效）----------
    def test_boundary2_exclusion_does_not_blind_the_drift_check(self):
        """正对照：改**手写文件** → 报 modified；负对照：改 `.pylibs/` → **不许报**。

        两组结果必须不同（《扫描器自证律》）：排除规则生效，但漂移判据还活着。
        """
        r = self.prod()
        p, _d, payload = self.take("PROD-MANIFEST-E7")
        cid = payload["checkpoint_id"]

        def drift():
            rc, out = CK.do_diff(p, cid)
            self.assertEqual(rc, CK.RC_OK)
            return out["production_tree"]["drift"]

        self.assertEqual(drift(), [], "刚打完点就有差异 = 判据坏了")

        # 正对照 A：手写文件被改
        (r / "holo_pet" / "panel_server.py").write_text("P" * 47 + "Q", encoding="utf-8")
        arm_a = drift()
        self.assertEqual([(x["file"], x["kind"]) for x in arm_a],
                         [("holo_pet/panel_server.py", "modified")])
        (r / "holo_pet" / "panel_server.py").write_text("P" * 48, encoding="utf-8")
        self.assertEqual(drift(), [])

        # 负对照 B：vendored 依赖被改（在排除目录里）
        (r / "gbt_allinone" / ".pylibs" / "numpy" / "core.py").write_text(
            "V" * 99, encoding="utf-8")
        arm_b = drift()
        self.assertEqual(arm_b, [], "排除目录里的改动不许进 drift")

        # 判别性：两臂结果必须不同
        self.assertNotEqual(len(arm_a), len(arm_b))
        self.assertTrue(all(".pylibs" not in x["path"]
                            for x in json.loads((Path(payload["dir"]) /
                                                 CK.PROD_MANIFEST_NAME)
                                                .read_text(encoding="utf-8"))["files"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
