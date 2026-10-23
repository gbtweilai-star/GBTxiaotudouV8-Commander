# -*- coding: utf-8 -*-
"""刀二 · `create` 契约测试（方案稿 §八 #7/#8/#9/#11 ＋ G6 三组 ＋ G7 ＋ D4 否决判据）。

判据的判别性（《扫描器自证律》）：每组负对照都必须真红 ——
  不指定出口 -> `target_source=default` 且**出站 0 条**（published 全 False）；
  越界路径 -> 拒绝且**写入根内零新增**；
  通道不可写 -> **不动盘** ＋ 主账本**恰好 1 条** `health_channel_failed`。
隔离口径：本文件在任何 `gbt_allinone` import **之前**把 `GBT_STORE_DIR` 与
`GBT_CREATE_ROOT` 指到 `tempfile.mkdtemp()`（一次一换，不复用目录 —— O52），
并在绑定生产 store / 生产 `outputs/` 时立刻报错停下。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PKG = _HERE.parent
_ROOT = _PKG.parent
_PRODUCTION_STORE = (_PKG / "store").resolve()
_PRODUCTION_OUTPUTS = (_ROOT / "outputs").resolve()

os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_create_test_"))
os.environ.setdefault("GBT_CREATE_ROOT", tempfile.mkdtemp(prefix="gbt_create_root_"))
# 🔴 2026-09-22 第 35 轮：owner 身份不再在 **import 期**置位（详见 test_ai_audit.py 里的实测），
#     改成"只在本模块用例期间置位、tearDownModule 还原"。
#     为什么：pytest 先 collect（import）全部模块再跑用例 ⇒ import 期置位等于
#     **给整个进程发主人身份**，后续模块的用例会绕开人工授权门。
#     实测（同文件同环境，只差这一个变量）：test_framework 未置位 = 142 passed/0 failed；
#     置位后同一条命令 **挂死超时**（真发外部 LLM 请求 / 真跑 npx / 真动桌面）。
_OWNER_WAS = os.environ.get("GBT_OWNER_SESSION")


def setUpModule():
    global _OWNER_WAS
    _OWNER_WAS = os.environ.get("GBT_OWNER_SESSION")
    os.environ["GBT_OWNER_SESSION"] = "1"


def tearDownModule():
    if _OWNER_WAS is None:
        os.environ.pop("GBT_OWNER_SESSION", None)
    else:
        os.environ["GBT_OWNER_SESSION"] = _OWNER_WAS


if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gbt_allinone import _paths, api, file_operation as FO, store  # noqa: E402
from gbt_allinone.caps_registry import BENIGN_CAPS  # noqa: E402
from gbt_allinone.security import policy as POLICY  # noqa: E402

if Path(_paths.STORE_DIR).resolve() == _PRODUCTION_STORE:
    raise RuntimeError(
        "拒绝在绑定【生产 store】的进程里跑 create 契约测试：%s" % _paths.STORE_DIR)
if FO.write_root() == _PRODUCTION_OUTPUTS:
    raise RuntimeError(
        "拒绝在指向【生产 outputs】的进程里跑 create 契约测试：%s" % FO.write_root())

SAMPLE = "GBT-正文探针-A7F3C1\n第二行"
REL = "drafts/20260918-probe.md"


def _rows():
    p = FO.events_path()
    if not p.is_file():
        return []
    return [json.loads(x.decode("utf-8")) for x in p.read_bytes().split(b"\n") if x.strip()]


def _main_rows():
    log = Path(store._LOG)
    if not log.is_file():
        return []
    return [json.loads(x.decode("utf-8")) for x in log.read_bytes().split(b"\n") if x.strip()]


def _tree(root: Path):
    out = []
    if not Path(root).exists():
        return out
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            out.append(p.relative_to(root).as_posix())
    return out


def _fp(root: Path):
    """目录指纹（相对路径 -> 指纹串）—— 判「真实 outputs 一字未动」用。

    🔴 2026-10-17 翻正（留痕 · 原做法 / 为什么翻 / 现做法）：
      原做法：对 `outputs/` **每个文件**都 `read_bytes()` 求 sha256[:16]。
      为什么翻：`outputs/` 实测 **438 个文件 / 15,631 MB**，其中 4 个是 ~3.7GB 的
        `model-0000X-of-00004.safetensors`（v24 权重）⇒ 取一次指纹要**真读 15.6GB**，
        单条测试就撞穿 120s（实测 pytest 直接 `+++ Timeout +++`，整套测试因此中断）。
      现做法：**小文件（≤ 4MB）仍算内容 sha256**（能咬住"改了内容但大小没变"）；
        大文件用 `size + mtime_ns` 指纹（任何写入都会改 mtime/size ⇒ 判"一字未动"足够）。
        ⇒ 判据的牙还在，成本从 15.6GB 降到几 MB。
    """
    root = Path(root)
    out = {}
    if not root.exists():
        return out
    LIMIT = 4 * 1024 * 1024
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        try:
            st = p.stat()
        except OSError:
            continue
        if st.st_size <= LIMIT:
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        else:
            out[rel] = "big:%d:%d" % (st.st_size, st.st_mtime_ns)
    return out


def _run_child(code: str, env: dict):
    env = dict(env)
    env["PYTHONUTF8"] = "1"
    p = subprocess.run([sys.executable, "-c", code, str(_ROOT)],
                       cwd=str(_ROOT), env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=180)
    return p


class _Base(unittest.TestCase):
    def setUp(self):
        # 一次一换：每个用例一个全新写入根（O52 —— 复用目录会让上一跑残留污染下一跑）
        self.root = Path(tempfile.mkdtemp(prefix="gbt_create_root_"))
        os.environ["GBT_CREATE_ROOT"] = str(self.root)
        # 🔴 2026-10-17 加（留痕）：`see_first`「先看后动」闸要 TTL 内一份已批蓝图。
        #   它原来把目录写死成 `ROOT/state/blueprints`（生产 state），隔离测试里永远满足不了
        #   ⇒ 「走行动类」的契约测试恒红。现闸支持 `SEE_FIRST_BDIR` 只换**目录位置**
        #   （不放宽拦截逻辑）；这里给它一个隔离目录 + 一份已批蓝图，用例结束即还原。
        self.bpdir = Path(tempfile.mkdtemp(prefix="gbt_blueprint_"))
        (self.bpdir / "unit-test.approved").write_text(
            "单元测试用已批蓝图（隔离目录，不进生产 state）\n", encoding="utf-8")
        self._bp_was = os.environ.get("SEE_FIRST_BDIR")
        os.environ["SEE_FIRST_BDIR"] = str(self.bpdir)
        shutil.rmtree(FO.channel_dir(), ignore_errors=True)
        FO._STATUS_CACHE.clear()

    def tearDown(self):
        FO._STATUS_CACHE.clear()
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.bpdir, ignore_errors=True)
        if self._bp_was is None:
            os.environ.pop("SEE_FIRST_BDIR", None)
        else:
            os.environ["SEE_FIRST_BDIR"] = self._bp_was
        shutil.rmtree(FO.channel_dir(), ignore_errors=True)

    def _block_channel(self):
        """把通道落点文件名占成目录 —— 追加打开必失败（不动 channel_dir 本身）。"""
        shutil.rmtree(FO.channel_dir(), ignore_errors=True)
        FO.channel_dir().mkdir(parents=True, exist_ok=True)
        FO.events_path().mkdir()
        return FO.events_path()

    def _write(self, rel=REL, content=SAMPLE, **kw):
        payload = {"path": rel, "content": content}
        payload.update(kw)
        return FO.run("write", payload)

    def _path(self, rel=REL):
        return FO.write_root() / rel


class StatusTests(_Base):
    """§八 #7 前置：status 是**只读**面 —— 不落账、不建目录、零字节。"""

    def test_status_is_read_only_zero_bytes(self):
        out = FO.run("status", {})
        self.assertTrue(out["ok"], "%r" % (out,))
        self.assertFalse(FO.channel_dir().exists(),
                         "status 不许建通道目录：%s" % FO.channel_dir())
        self.assertEqual([], _tree(self.root), "status 不许在写入根留下任何文件")
        self.assertEqual("pending", out["text_exit"]["status"])
        self.assertFalse(out["text_exit"]["wired"])

    def test_status_ttl_cache_second_call_is_cached(self):
        FO.run("status", {})
        again = FO.run("status", {})
        self.assertTrue(again.get("cached"), "TTL 内第二次必须走缓存：%r" % (again,))


class WiringTests(_Base):
    """注册 ≠ 丢文件（R86 教训）：注册表 + 路由派发 + policy 三处必须都在。"""

    def test_registry_entry_and_dispatch_exist(self):
        self.assertIn("create", BENIGN_CAPS)
        self.assertEqual("create", BENIGN_CAPS["create"]["handler"])
        self.assertTrue(str(BENIGN_CAPS["create"].get("desc", "")).strip())
        src = (_PKG / "api.py").read_text(encoding="utf-8")
        self.assertEqual(1, src.count('    if kind == "create":'))

    def test_policy_gates_write_op_only(self):
        d1 = POLICY.evaluate("create", {"op": "write"})
        self.assertIn("filesystem_write", d1.scopes)
        self.assertEqual("high", d1.risk)
        for op in ("status", "intent", "output", "configure"):
            d = POLICY.evaluate("create", {"op": op})
            self.assertEqual((), tuple(d.scopes), "%s 不该收口：%r" % (op, d.scopes))

    def test_untrusted_session_cannot_write(self):
        old = os.environ.pop("GBT_OWNER_SESSION", None)
        try:
            out = api.run_task("create", {"op": "write", "path": REL, "content": SAMPLE})
            body = out.get("result") or out.get("gbt_result") or {}
            self.assertFalse(out.get("ok"), "未受信会话不许写盘：%r" % (out,))
            self.assertEqual("denied", body.get("status"), "%r" % (body,))
            self.assertTrue(body.get("denied"))
            self.assertFalse(self._path().exists(),
                             "被拒时一次写盘都不许有：%s" % self._path())
            self.assertEqual([], _tree(self.root), "被拒时写入根必须零新增")
        finally:
            if old is not None:
                os.environ["GBT_OWNER_SESSION"] = old

    def test_trusted_session_dispatches_through_api(self):
        out = api.run_task("create", {"op": "write", "path": REL, "content": SAMPLE})
        self.assertTrue(out.get("ok"), "%r" % (out,))
        inner = (out.get("result") or {}).get("result") or {}
        self.assertTrue(inner.get("wrote"), "派发到了能力但没写盘：%r" % (inner,))
        self.assertEqual(SAMPLE.encode("utf-8"), self._path().read_bytes())

    def test_unknown_op_is_user_error(self):
        with self.assertRaises(FO.CreateError):
            FO.run("no_such_op", {})
        out = api.run_task("create", {"op": "no_such_op"})
        body = out.get("result") or {}
        self.assertFalse(out.get("ok"))
        self.assertEqual("user_error", body.get("error_class"), "%r" % (body,))


class PathGateTests(_Base):
    """§八 #9：写入根只有一个 —— 越界一律拒，且**盘上零新增**。"""

    ESCAPES = ("../evil.md", "..\\evil.md", "/abs.md", "C:/abs.md", "c:\\abs.md",
               ".backup/x.md", "a/../../b.md", "..", "a/./../b.md")

    def test_escape_paths_are_rejected_and_disk_untouched(self):
        for rel in self.ESCAPES:
            with self.subTest(rel=rel):
                with self.assertRaises(FO.CreateError, msg="越界路径没被拒：%r" % rel):
                    self._write(rel=rel)
        self.assertEqual([], _tree(self.root), "越界路径不许在写入根留下任何文件")
        self.assertFalse((self.root.parent / "evil.md").exists(),
                         "越界路径不许写到写入根之外")

    def test_missing_or_nonstring_path_is_rejected(self):
        for bad in (None, "", "   "):
            with self.assertRaises(FO.CreateError):
                self._write(rel=bad)
        self.assertEqual([], _tree(self.root))

    def test_nonstring_content_is_rejected(self):
        with self.assertRaises(FO.CreateError):
            self._write(content=123)
        self.assertEqual([], _tree(self.root))


class TextExitTests(_Base):
    """G6 组 1 ＋ D4 否决判据：默认出口**不能凭自己把内容发出去**。"""

    def test_eigenflux_is_registered_as_readonly(self):
        """eigenflux 必须在册，且必须是**只读位**（safe=True）—— 不许变成能自己往外发内容的出口。

        🔴 2026-10-17 翻正（留痕 · 原断言 / 为什么翻 / 原期望不变的部分）：
          原断言：`eigenflux` **不许在 BENIGN_CAPS**、也不许出现在 api.py
          （那是这一刀当时的临时禁令：「没取证的不建」）。
          现读事实：它已按主人令 2026-10-08 登记为**只读能力位**
          （`caps_registry` 里 `^'eigenflux': {... 'safe': True}`；desc 明写零写面/零出网/零 policy 条目）。
          原期望【不变】：默认出口**不能凭自己把内容发出去**。现口径改成直接钉住这条：
          在册 + safe + 只读 op（status/feed/friends/candidates/digest/metadata/where）。
        """
        self.assertIn("eigenflux", BENIGN_CAPS, "eigenflux 应按 2026-10-08 主人令在册（只读位）")
        self.assertTrue(BENIGN_CAPS["eigenflux"].get("safe"),
                        "eigenflux 必须是 safe（只读）：它不该成为能自己发内容的出口")
        self.assertEqual("eigenflux", BENIGN_CAPS["eigenflux"].get("handler"))

    def test_default_target_and_zero_outbound(self):
        out = FO.run("output", {"content": SAMPLE})
        self.assertFalse(out["ok"], "%r" % (out,))
        self.assertEqual("pending", out["status"])
        self.assertEqual("default", out["target_source"])
        self.assertEqual(FO.TEXT_EXIT_TARGET_DEFAULT, out["target"])
        self.assertFalse(out["published"])
        self.assertFalse(out["network_attempted"], "本刀一次网络请求都不许发")
        rows = [r for r in _rows() if r["event"] == "create_output"]
        self.assertEqual(1, len(rows))
        self.assertEqual("pending", rows[0]["meta"]["result"])
        self.assertEqual([], [r for r in _rows() if r["meta"].get("published")],
                         "出站 0 条：账里不许有 published=True")

    def test_default_target_comes_from_settings_not_module_constant(self):
        FO.run("configure", {"target": "my_circle_v2"})
        out = FO.run("output", {"content": SAMPLE})
        self.assertEqual("my_circle_v2", out["target"], "默认出口必须来自设置页")
        self.assertEqual("default", out["target_source"])
        self.assertNotEqual(FO.TEXT_EXIT_TARGET_DEFAULT, out["target"])

    def test_default_source_cannot_smuggle_its_own_target(self):
        with self.assertRaises(FO.CreateError):
            FO.run("output", {"content": SAMPLE, "target_source": "default",
                              "target": "someone_else"})

    def test_explicit_target_still_never_publishes(self):
        out = FO.run("output", {"content": SAMPLE, "target": "agent_picked",
                                "target_source": "agent_suggested"})
        self.assertEqual("agent_suggested", out["target_source"])
        self.assertFalse(out["published"])
        self.assertFalse(out["network_attempted"])

    def test_output_superlimit_is_rejected_not_truncated(self):
        with self.assertRaises(FO.CreateError):
            FO.run("output", {"content": "x" * (FO.CONTENT_MAX + 1)})


class IntentTests(_Base):
    """§八 #8：`create_intent` 必记 `target` ＋ `target_source`（D4）。"""

    def test_intent_records_target_and_source(self):
        out = FO.run("intent", {"content": SAMPLE, "target": "friend_page",
                                "target_source": "user"})
        self.assertTrue(out["ok"], "%r" % (out,))
        self.assertFalse(out["published"])
        rows = [r for r in _rows() if r["event"] == "create_intent"]
        self.assertEqual(1, len(rows))
        meta = rows[0]["meta"]
        self.assertEqual("friend_page", meta["target"])
        self.assertEqual("user", meta["target_source"])

    def test_intent_defaults_to_settings_target(self):
        FO.run("configure", {"target": "my_circle_v2"})
        out = FO.run("intent", {"content": SAMPLE})
        self.assertEqual("my_circle_v2", out["target"])
        self.assertEqual("default", out["target_source"])

    def test_intent_rejects_unknown_target_source(self):
        with self.assertRaises(FO.CreateError):
            FO.run("intent", {"target_source": "whatever"})

    def test_intent_requires_target_when_source_is_explicit(self):
        with self.assertRaises(FO.CreateError):
            FO.run("intent", {"target_source": "user"})


class WriteTests(_Base):
    """§八 #11：`create_write` 是唯一可逆后果动作 —— 覆盖必带令牌 ＋ 写前备份 ＋ 双向 SHA。"""

    def test_new_file_written_and_audited(self):
        out = self._write()
        self.assertTrue(out["ok"], "%r" % (out,))
        self.assertTrue(out["wrote"])
        self.assertFalse(out["overwrote"])
        self.assertIsNone(out["backup"])
        on_disk = self._path().read_bytes()
        self.assertEqual(SAMPLE.encode("utf-8"), on_disk)
        self.assertEqual(hashlib.sha256(on_disk).hexdigest(), out["sha256"])
        rows = [r for r in _rows() if r["event"] == "create_write"]
        self.assertEqual(1, len(rows))
        self.assertEqual(REL, rows[0]["meta"]["path"])
        self.assertTrue(rows[0]["meta"]["wrote"])

    def test_content_never_lands_in_ledger(self):
        self._write()
        blob = FO.events_path().read_bytes()
        self.assertNotIn(SAMPLE.encode("utf-8"), blob, "创作原文不许进账本")
        self.assertNotIn("第二行".encode("utf-8"), blob)

    def test_superlimit_content_rejected_not_truncated(self):
        with self.assertRaises(FO.CreateError):
            self._write(content="x" * (FO.CONTENT_MAX + 1))
        self.assertEqual([], _tree(self.root))

    def test_overwrite_without_token_rejected_bytes_unchanged(self):
        self._write()
        before = self._path().read_bytes()
        with self.assertRaises(FO.CreateError):
            self._write(content=SAMPLE + "\n新的一行", overwrite=True)
        self.assertEqual(before, self._path().read_bytes(),
                         "无令牌覆盖必须真红：盘上一个字节都不许变")
        self.assertEqual(1, len(_tree(self.root)), "拒绝路径不许留备份 / 半成品")

    def test_overwrite_true_without_existing_target_rejected(self):
        with self.assertRaises(FO.CreateError):
            self._write(content="first", overwrite=True)
        self.assertEqual([], _tree(self.root))

    def test_overwrite_with_token_backs_up_and_double_sha(self):
        self._write()
        old_bytes = self._path().read_bytes()
        new_text = SAMPLE + "\n追加一行"
        new_sha = hashlib.sha256(new_text.encode("utf-8")).hexdigest()
        out = self._write(content=new_text, overwrite=True,
                          confirm_token=FO.build_confirm_token(REL, new_sha))
        self.assertTrue(out["ok"], "%r" % (out,))
        self.assertTrue(out["overwrote"])
        self.assertTrue(out["verify_new_sha"], "盘上 sha 必须 == 新内容 sha")
        self.assertTrue(out["verify_backup_sha"], "备份 sha 必须 == 原内容 sha")
        self.assertIsNotNone(out["backup"])
        backup = FO.write_root() / out["backup"]
        self.assertTrue(backup.is_file())
        self.assertEqual(old_bytes, backup.read_bytes(), "备份必须是覆盖前的原字节")
        self.assertEqual(new_text.encode("utf-8"), self._path().read_bytes())

    def test_token_is_content_bound(self):
        self._write()
        token = FO.build_confirm_token(
            REL, hashlib.sha256((SAMPLE + "\nA").encode("utf-8")).hexdigest())
        with self.assertRaises(FO.CreateError):
            self._write(content=SAMPLE + "\nB", overwrite=True, confirm_token=token)
        self.assertEqual(SAMPLE.encode("utf-8"), self._path().read_bytes())

    def test_token_is_path_bound(self):
        self._write()
        other = "drafts/other.md"
        (FO.write_root() / "drafts").mkdir(parents=True, exist_ok=True)
        (FO.write_root() / other).write_bytes(b"old")
        new_sha = hashlib.sha256(b"new").hexdigest()
        with self.assertRaises(FO.CreateError):
            self._write(rel=other, content="new", overwrite=True,
                        confirm_token=FO.build_confirm_token(REL, new_sha))
        self.assertEqual(b"old", (FO.write_root() / other).read_bytes())

    def test_idempotent_repeat_does_not_overwrite_again(self):
        """G7：同一 create_write 重复提交不产生第二次覆盖。"""
        first = self._write()
        self.assertTrue(first["wrote"])
        second = self._write()
        self.assertTrue(second["ok"], "%r" % (second,))
        self.assertTrue(second["idempotent"])
        self.assertFalse(second["wrote"])
        self.assertFalse(second["overwrote"])
        self.assertEqual(SAMPLE.encode("utf-8"), self._path().read_bytes())
        baks = [p for p in _tree(self.root) if p.startswith(FO.BACKUP_DIRNAME + "/")]
        self.assertEqual([], baks, "幂等重复不许产生备份")
        rows = [r for r in _rows() if r["event"] == "create_write"]
        self.assertEqual(2, len(rows))
        self.assertFalse(rows[1]["meta"]["wrote"])
        self.assertTrue(rows[1]["meta"]["idempotent"])


class ChannelGateTests(_Base):
    """G6 组 3：通道不可写 -> **不动盘** ＋ 主账本恰好 1 条；正对照同 payload 必须过。"""

    def test_channel_blocked_write_aborts_and_main_ledger_exactly_one(self):
        self._block_channel()
        main_before = len(_main_rows())
        out = self._write()
        self.assertFalse(out["ok"], "%r" % (out,))
        self.assertEqual("blocked", out["status"])
        self.assertEqual("channel_write_failed", out["reason"])
        self.assertFalse(out["wrote"])
        self.assertEqual([], _tree(self.root), "通道不可写 -> 一个字节都不许落盘")
        new = [r for r in _main_rows()[main_before:]
               if r["event"] == "health_channel_failed"]
        self.assertEqual(1, len(new), "主账本必须恰好 1 条故障：%r" % (new,))
        self.assertEqual("create", new[0]["meta"]["channel"])

    def test_channel_writable_positive_control(self):
        main_before = len(_main_rows())
        out = self._write()
        self.assertTrue(out["ok"], "正对照臂自己坏了：%r" % (out,))
        self.assertEqual(1, len(_rows()), "通道可写 -> 通道落 1 条")
        self.assertEqual([], [r for r in _main_rows()[main_before:]
                              if r["event"] == "health_channel_failed"],
                         "通道可写 -> 主账本 0 条故障")

    def test_blocked_channel_also_stops_overwrite_and_backup(self):
        self._write()
        old = self._path().read_bytes()
        self._block_channel()
        new_text = SAMPLE + "\nZL"
        token = FO.build_confirm_token(
            REL, hashlib.sha256(new_text.encode("utf-8")).hexdigest())
        out = self._write(content=new_text, overwrite=True, confirm_token=token)
        self.assertFalse(out["ok"], "%r" % (out,))
        self.assertEqual(old, self._path().read_bytes(), "通道不可写 -> 原文件必须原样")
        baks = [p for p in _tree(self.root) if p.startswith(FO.BACKUP_DIRNAME + "/")]
        self.assertEqual([], baks, "通道不可写 -> 连备份都不许产生")


class CreateRootBindingTests(_Base):
    """**持久化守门用例** —— O53 甲案的镜像。

    O53 守的是 store：`_paths.STORE_DIR` 在 import 期绑成常量，之后改 env **无效**，
    只能 fail-fast。写入根走的是**另一条**口径：`write_root()` **每次调用都重新读 env**，
    所以结构上不存在「绑定后改 env 静默写旧根」的窗口。

    这条口径以前只在 `.scratch` 里活体跑过 —— 现在落成**仓内回归**：
    两臂判别性 = 换 env 之后，新根必须拿到写入，**旧根必须零新增**。
    将来谁把 `write_root()` 改成 import 期常量（或加缓存），这条当场红。
    """

    def test_write_root_follows_env_change_immediately(self):
        first = self.root / "rootA"
        second = self.root / "rootB"
        first.mkdir()
        second.mkdir()
        os.environ["GBT_CREATE_ROOT"] = str(first)
        self.assertEqual(first.resolve(), FO.write_root())
        self._write(rel="a.md", content="A")
        self.assertTrue((first / "a.md").is_file(), "臂 A：写入没落进当时的根")
        os.environ["GBT_CREATE_ROOT"] = str(second)
        self.assertEqual(second.resolve(), FO.write_root(),
                         "写入根没有跟着 env 走 —— 出现 import 期绑定")
        self._write(rel="b.md", content="B")
        self.assertTrue((second / "b.md").is_file(), "臂 B：换根后写入没落到新根")
        self.assertFalse((first / "b.md").exists(),
                         "臂 B：旧根被静默写入 —— 陈旧绑定复活了")
        self.assertEqual(["a.md"], _tree(first), "旧根必须保持换根前的原样")

    def test_isolated_root_can_be_switched_back_and_forth(self):
        """同一进程内来回换根，每次都按当时 env 落 —— 两臂数值必须不同。"""
        for name in ("x", "y"):
            sub = self.root / name
            sub.mkdir()
            os.environ["GBT_CREATE_ROOT"] = str(sub)
            out = self._write(rel="%s.md" % name, content=name.upper())
            self.assertTrue(out["wrote"], "%r" % (out,))
        self.assertEqual(["x.md"], _tree(self.root / "x"))
        self.assertEqual(["y.md"], _tree(self.root / "y"))


class ProductionOutputsIsolationTests(_Base):
    """**持久化守门用例** —— `TestProductionStoreIsolation` 的 outputs 镜像。

    测试面绝不许碰真实 `<家根>/outputs/`。两臂判别性：
      · 臂 A（**不设** `GBT_CREATE_ROOT`）：模块报的写入根必须 == 真实 outputs，
        且只读 `status` 之后真实 outputs 指纹一字未动（默认根不许被"猜错"）；
      · 臂 B（设 `GBT_CREATE_ROOT`）：`write` 必须落进隔离根，真实 outputs 指纹**不变**。
    臂 A 的存在是必要的 —— 没有它，臂 B 全绿也可能只是因为默认根本来就指错了地方。
    子进程一律显式设 `GBT_STORE_DIR`：否则 `import gbt_allinone` 会把 store 绑到
    **生产** store，`write` 的通道预检就会在生产 `store/health/create/` 里建目录。
    """

    def _child_env(self):
        env = dict(os.environ)
        env["GBT_STORE_DIR"] = tempfile.mkdtemp(prefix="gbt_create_iso_store_")
        return env

    def test_arm_a_default_root_is_production_outputs_and_status_writes_nothing(self):
        before = _fp(_PRODUCTION_OUTPUTS)
        env = self._child_env()
        env.pop("GBT_CREATE_ROOT", None)
        code = ("import json, sys; sys.path.insert(0, sys.argv[1]); "
                "from gbt_allinone import file_operation as FO; "
                "r = FO.run('status', {}); "
                "print(json.dumps({'ok': r['ok'], 'root': r['write_root'], "
                "'exists': r['write_root_exists']}))")
        p = _run_child(code, env)
        self.assertEqual(0, p.returncode, p.stderr.decode("utf-8", "replace")[-400:])
        data = json.loads(p.stdout.decode("utf-8", "replace").strip().splitlines()[-1])
        self.assertTrue(data["ok"], "%r" % (data,))
        self.assertEqual(_PRODUCTION_OUTPUTS, Path(data["root"]).resolve(),
                         "默认写入根不是真实 outputs —— 臂 B 的隔离结论会失效")
        self.assertTrue(data["exists"])
        self.assertEqual(before, _fp(_PRODUCTION_OUTPUTS),
                         "只读 status 碰了真实 outputs")

    def test_arm_b_isolated_write_never_touches_production_outputs(self):
        before = _fp(_PRODUCTION_OUTPUTS)
        iso_root = Path(tempfile.mkdtemp(prefix="gbt_create_iso_root_"))
        self.addCleanup(shutil.rmtree, iso_root, ignore_errors=True)
        env = self._child_env()
        env["GBT_CREATE_ROOT"] = str(iso_root)
        code = ("import json, sys; sys.path.insert(0, sys.argv[1]); "
                "from gbt_allinone import file_operation as FO; "
                "r = FO.run('write', {'path': 'drafts/iso.md', 'content': 'iso-probe'}); "
                "print(json.dumps({'wrote': r['wrote'], 'root': r['abs']}))")
        p = _run_child(code, env)
        self.assertEqual(0, p.returncode, p.stderr.decode("utf-8", "replace")[-400:])
        data = json.loads(p.stdout.decode("utf-8", "replace").strip().splitlines()[-1])
        self.assertTrue(data["wrote"], "臂 B：隔离根里没写成 —— 对臂 A 无判别性")
        self.assertTrue((iso_root / "drafts" / "iso.md").is_file())
        self.assertEqual(before, _fp(_PRODUCTION_OUTPUTS),
                         "测试面写进了真实 outputs")


class CreateWriteRootIsolationHookTests(_Base):
    """R107 · `GBT_CREATE_ROOT` 一次性隔离钩子（甲案 + 乙案）契约。

    判别性（旧实现必红）：改动前，「隔离 store ＋ 不设 GBT_CREATE_ROOT ＋ import 测试包」
    的进程里 `write_root()` 直接返回生产 `outputs/` —— 忘了设 env 就会写生产。
    """

    def _child_env(self, create_root=None):
        env = dict(os.environ)
        env["GBT_STORE_DIR"] = tempfile.mkdtemp(prefix="gbt_r107_iso_store_")
        env["PYTHONUTF8"] = "1"
        env.pop("GBT_CREATE_ROOT", None)
        if create_root is not None:
            env["GBT_CREATE_ROOT"] = str(create_root)
        return env

    def test_arm_c_hook_pins_isolated_root_when_env_absent(self):
        """臂 C（甲案）：不设 env 的测试进程，钩子必须把写根钉到隔离目录 —— 旧实现必红。

        🔴 2026-10-17 翻正（留痕 · 原断言 / 为什么翻 / 现口径）：
          原断言：子进程退出后，**父进程**再 `Path(data["abs"]).is_file()`。
          为什么翻：`gbt_allinone/tests/__init__.py` 的 O56 清理（2026-10-16）会在
            `atexit` 删掉**本进程自己造的隔离根**（修的是实测堆到 2146 个的
            `%TEMP%/gbt_test_create_root_*` 残留）⇒ 子进程一退出目录就没了，
            父进程的 `is_file()` **结构上必然 False**。是断言位置错了，不是钩子坏了。
          现口径：**证据在子进程内取**（写没写 / 文件在不在 / 内容对不对当场判），
            父进程验三个布尔 + 生产 outputs 指纹未变。判据的牙一条不少。
        """
        before = _fp(_PRODUCTION_OUTPUTS)
        env = self._child_env()
        code = ("import json, os, sys; sys.path.insert(0, sys.argv[1]); "
                "import gbt_allinone.tests; "
                "from gbt_allinone import file_operation as FO; "
                "r = FO.run('write', {'path': 'drafts/hook.md', 'content': 'hook-probe'}); "
                "ap = str(r.get('abs') or ''); "
                "ok = bool(ap) and os.path.isfile(ap); "
                "print(json.dumps({'root': str(FO.write_root()), 'wrote': r.get('wrote'), "
                "'abs': ap, 'exists_in_child': ok, "
                "'content_ok': bool(ok and open(ap, encoding='utf-8').read() == 'hook-probe')}))")
        p = _run_child(code, env)
        self.assertEqual(0, p.returncode, p.stderr.decode("utf-8", "replace")[-400:])
        data = json.loads(p.stdout.decode("utf-8", "replace").strip().splitlines()[-1])
        self.assertNotEqual(Path(data["root"]).resolve(), _PRODUCTION_OUTPUTS,
                            "测试包没把写根钉到隔离目录 —— 钩子失效（改动前即此形态）")
        self.assertTrue(data["wrote"], "%r" % (data,))
        self.assertTrue(data["exists_in_child"], "子进程内文件都不在：%r" % (data,))
        self.assertTrue(data["content_ok"], "写进去的内容不对：%r" % (data,))
        self.assertEqual(before, _fp(_PRODUCTION_OUTPUTS), "测试面写进了真实 outputs")

    def test_arm_b_hook_refuses_when_env_points_at_production_outputs(self):
        """臂 B（甲案负对照）：显式把写根指生产 outputs -> 导入测试包必须报错停下。"""
        env = self._child_env(create_root=_PRODUCTION_OUTPUTS)
        p = _run_child("import gbt_allinone.tests; print('SHOULD_NOT_RUN')", env)
        err = p.stderr.decode("utf-8", "replace")
        self.assertNotEqual(p.returncode, 0, "指向生产 outputs 居然跑通了 —— 钩子失效")
        self.assertIn("RuntimeError", err)
        self.assertIn("outputs", err)

    def test_arm_d_isolated_write_lands_in_iso_root_and_prod_outputs_untouched(self):
        """臂 D：隔离根里真写成，生产 outputs / store 通道 / 主账本三项零扰动。"""
        before = _fp(_PRODUCTION_OUTPUTS)
        audit = _PKG / "store" / "audit.jsonl"
        audit_sha = hashlib.sha256(audit.read_bytes()).hexdigest()[:16]
        # 🔴 2026-09-22 第 36 轮修（错报治理）：通道那条原来写成
        #     `assertFalse((_PKG/"store"/"health"/"create").exists(), "生产 store 通道被污染")`
        #     —— 一个**绝对存在性**判据，而它声称的是"**我这次**零扰动"，与它同测试的
        #     另两条（outputs 指纹、主账本 sha）都是**前后对比(delta)**。形状与声称不匹配。
        #     实测代价：`store/health/create/events.jsonl` **确实存在**，但查生产主账本
        #     （37297462 字节）该时段记录，它是 `2026-09-22T22:02:39/40` 两次**真实生产调用**
        #     `create`（payload_keys=[op,title] / [op,answer…] 均 `ok`，且 22:00:17 有
        #     `auth_granted desktop_control · operator=human-terminal`）留下的**正常产物**，
        #     **不是测试污染**。⇒ 一条"它不许存在"的判据会被**主人的正常使用**弄红，
        #     而且每次都红（假红会训练人忽略红字）。改成和它兄弟一样的 delta。
        chan = _PKG / "store" / "health" / "create"
        chan_before = _fp(chan)
        iso_root = Path(tempfile.mkdtemp(prefix="gbt_r107_iso_root_"))
        self.addCleanup(shutil.rmtree, iso_root, ignore_errors=True)
        env = self._child_env(create_root=iso_root)
        code = ("import json, sys; sys.path.insert(0, sys.argv[1]); "
                "import gbt_allinone.tests; "
                "from gbt_allinone import file_operation as FO; "
                "r = FO.run('write', {'path': 'drafts/iso.md', 'content': 'iso-probe'}); "
                "print(json.dumps({'wrote': r['wrote'], 'sha256': r['sha256'], "
                "'idempotent': r['idempotent']}))")
        p = _run_child(code, env)
        self.assertEqual(0, p.returncode, p.stderr.decode("utf-8", "replace")[-400:])
        data = json.loads(p.stdout.decode("utf-8", "replace").strip().splitlines()[-1])
        self.assertTrue(data["wrote"] and not data["idempotent"], "%r" % (data,))
        on_disk = (iso_root / "drafts" / "iso.md").read_bytes()
        self.assertEqual(hashlib.sha256(on_disk).hexdigest(), data["sha256"],
                         "盘上字节与返回值不符")
        self.assertEqual(before, _fp(_PRODUCTION_OUTPUTS), "测试面写进了真实 outputs")
        self.assertEqual(chan_before, _fp(chan), "测试面动了生产 store 通道（前后对比）")
        self.assertEqual(audit_sha, hashlib.sha256(audit.read_bytes()).hexdigest()[:16],
                         "生产主账本被动过")

    def test_arm_e_write_gate_blocks_production_root_without_test_package(self):
        """臂 E（乙案判别性）：绕过测试包钩子、直接 import 能力层，写入口必须拦下。"""
        before = _fp(_PRODUCTION_OUTPUTS)
        env = self._child_env(create_root=_PRODUCTION_OUTPUTS)
        code = ("import json, sys; sys.path.insert(0, sys.argv[1]); "
                "from gbt_allinone import file_operation as FO; "
                "out = {'root': str(FO.write_root())}\n"
                "try:\n"
                "    FO.run('write', {'path': 'drafts/bypass.md', 'content': 'x'})\n"
                "    out['blocked'] = False\n"
                "except Exception as exc:\n"
                "    out['blocked'] = True\n"
                "    out['err'] = type(exc).__name__\n"
                "print(json.dumps(out))")
        p = _run_child(code, env)
        self.assertEqual(0, p.returncode, p.stderr.decode("utf-8", "replace")[-400:])
        data = json.loads(p.stdout.decode("utf-8", "replace").strip().splitlines()[-1])
        self.assertTrue(data["blocked"], "写入口闸门没拦住：%r" % (data,))
        self.assertEqual("WriteRootError", data["err"], "%r" % (data,))
        self.assertFalse((_PRODUCTION_OUTPUTS / "drafts" / "bypass.md").exists())
        self.assertEqual(before, _fp(_PRODUCTION_OUTPUTS), "写入口闸门漏了盘")

    def test_arm_f_no_write_path_bypasses_the_gate(self):
        """臂 F（覆盖范围静态判据）：能力层里所有 `write_root()` 调用只许出现在
        ① `_write_root_checked`（闸门本体）② `_op_status`（只读上报）。
        别处出现 = 有落盘路径绕过了闸门（Owner 补充的落点要求）。
        """
        import ast
        src = Path(FO.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        hits = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                            and sub.func.id == "write_root"):
                        hits[node.name] = hits.get(node.name, 0) + 1
        self.assertEqual(sorted(hits), ["_op_status", "_write_root_checked"],
                         "有写盘路径绕过闸门（直接调 write_root）：%r" % (hits,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
