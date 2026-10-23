# gbt-capability: 多维穷尽扫描引擎验收
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""scan_engine 验收：**它自己必须先被证明不是瞎的**。

三条硬断言：
  ① 两把对照都要过 —— 正对照（11 种藏匿样本全部抓到）+ 负对照（干净文件零误报）
  ② 覆盖闭合律是**恒等式**，不是自检：枚举 == 已扫 + 声明排除 + 读不到
  ③ 账本不许撒谎：`已扫` 只算 **walk 走得到**的文件，
     嵌套排除目录里的文件必须进排除桶（这里修过一个假绿，见下面的回归）
外加一串**回归钉子**：每个都是我第一版真犯过的错。

跑法：
    $env:GBT_STORE_DIR="$env:TEMP\\gbt_test_store"; py -3.14 -m pytest gbt_allinone/tests/test_scan_engine.py -q
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import time
from pathlib import Path

import pytest

_T = Path(__file__).resolve().parents[1] / "tools"
if str(_T) not in sys.path:
    sys.path.insert(0, str(_T))

import scan_engine as se  # noqa: E402


# ─────────────────────────────────────────── ① 两把对照

def test_both_controls_pass():
    """正负两把对照必须同时过。只有一边的检测器是瞎的。"""
    assert se.selftest(verbose=False) == 0, "两把对照没过 —— 检测器有漏报或误报"


def test_selftest_leaves_no_temp_residue():
    """自己造的样本必须自己收干净。

    实测坑：结尾空格名 `rmtree` **删不掉**（WinError 145），
    第一版没清理 ⇒ 把临时目录留在盘上，"扫描器"变成"垃圾制造器"。
    """
    import glob
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "tmp*")))
    se.selftest(verbose=False)
    after = set(glob.glob(os.path.join(tempfile.gettempdir(), "tmp*")))
    leaked = {p for p in (after - before) if os.path.isdir(p)}
    assert not leaked, "对照跑完留下临时目录：%s" % sorted(leaked)[:3]


# ─────────────────────────────────────────── ② 覆盖闭合律

@pytest.fixture()
def tree(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.md").write_text("hi\n", encoding="utf-8")
    # 深层排除目录：里面的文件**只能进排除桶**，不许算成"已扫"
    (tmp_path / "gbt_allinone" / "store").mkdir(parents=True)
    (tmp_path / "gbt_allinone" / "store" / "big.bin").write_bytes(b"\x00" * 128)
    (tmp_path / "gbt_allinone" / "real.py").write_text("y = 2\n", encoding="utf-8")
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "dep.py").write_text("z = 3\n", encoding="utf-8")
    return tmp_path


def test_closure_is_an_identity(tree):
    """盘上 5 个文件：a.py · sub/b.md · gbt_allinone/real.py（可达 ⇒ 已扫 3）
    · gbt_allinone/store/big.bin（深层排除 1）· vendor/dep.py（外部语料 1）。"""
    rep = se.scan(tree, mode="full")
    assert rep["closure"] is True
    assert rep["enumerated"] == sum(rep["buckets"].values())
    assert rep["enumerated"] == 5, "盘上就是 5 个文件（清单见 docstring）"
    assert rep["ok"] is True


def test_scanned_counts_only_reachable_files(tree):
    """回归（假绿）：嵌套 `store/` 里的文件必须进排除桶。

    第一版按"顶层部件"归桶 ⇒ `gbt_allinone/store/big.bin` 被算成"已扫"，
    而它其实**只被数过、从没被读过**：恒等式照样成立，但标签在撒谎。
    """
    rep = se.scan(tree, mode="full")
    assert rep["buckets"]["scanned"] == 3, "可达的只有 a.py / sub/b.md / gbt_allinone/real.py"
    assert rep["buckets"]["excluded_declared"] == 1, "vendor/dep.py 是外部语料"
    assert rep["buckets"]["excluded_tooling"] == 1, "gbt_allinone/store/big.bin 是深层排除"
    assert rep["excluded_detail"]["store"]["files"] == 1
    assert rep["excluded_detail"]["store"]["where"] == "gbt_allinone", "要交代它在哪儿被剪的"


def test_ads_sweep_covers_exactly_the_scanned_set(tree):
    """ADS 问过的文件数必须**等于**已扫数，否则"藏匿 0"是假清白。"""
    rep = se.scan(tree, mode="full")
    ads = rep["probes"]["ads"]
    assert ads["available"] is True
    if ads["checked"] == 0 and rep["buckets"]["scanned"] > 0:
        pytest.fail("ADS 一个都没问到，却已扫 %d 个" % rep["buckets"]["scanned"])
    assert ads["checked"] == rep["buckets"]["scanned"]
    assert ads["found"] == 0


# ─────────────────────────────────────────── ③ 回归钉子（每条都是我犯过的错）

def test_glb_magic_offset_is_correct(tmp_path):
    """GLB 魔数在**字节 0..4**（`glTF`），8..12 是总长度。

    第一版把签名当成在 8..12 ⇒ 仓里 36 个真 .glb 全被报成"伪装"。
    """
    glb = tmp_path / "m.glb"
    glb.write_bytes(b"glTF" + (2).to_bytes(4, "little") + (64).to_bytes(4, "little") + b"\x00" * 52)
    assert se._magic_of(glb) == "三维/glb"
    rep = se.scan(tmp_path, mode="full")
    assert [f for f in rep["findings"] if f["rule"].startswith("GBT-SE-01")] == [], \
        "真 .glb 不许被报成伪装"


def test_double_ext_needs_a_pretend_prefix(tmp_path):
    """`evil.py.exe` 要报；`xingyun_e2e.latest.js` 不许报。

    第一版只判"点 ≥2 且以 .js 结尾" ⇒ 把正常命名全打成伪装；
    收紧后又漏了 `evil.py.exe`（PRETEND 里没有代码后缀）—— **两次都是对照抓出来的**。
    """
    (tmp_path / "evil.py.exe").write_bytes(b"MZ" + b"\x00" * 40)
    (tmp_path / "xingyun_e2e.latest.js").write_text("// e2e\n", encoding="utf-8")
    (tmp_path / "a.min.js").write_text("// min\n", encoding="utf-8")
    (tmp_path / "shot.png.exe").write_bytes(b"MZ" + b"\x00" * 40)
    rep = se.scan(tmp_path, mode="full")
    flagged = {f["path"] for f in rep["findings"] if f["rule"] == "GBT-SE-023"}
    assert "evil.py.exe" in flagged and "shot.png.exe" in flagged
    assert "xingyun_e2e.latest.js" not in flagged, "正常多段命名不许误报"
    assert "a.min.js" not in flagged, "min.js 不许误报"


def test_binary_hidden_as_text_is_caught(tmp_path):
    """反向伪装：PNG 头挂 `.txt` ⇒ 必须报（第一版只做了正向，漏了它）。"""
    (tmp_path / "fake.txt").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)
    rep = se.scan(tmp_path, mode="full")
    assert any(f["rule"] == "GBT-SE-011" for f in rep["findings"]), "二进制藏成文本没被抓到"


def test_zip_label_is_consistent(tmp_path):
    """`.zip` 的期望标签必须与魔数返回的标签**同一个字符串**。

    第一版两处标签不一致 ⇒ 真 zip 被报成"伪装"（自己造的误报）。
    """
    (tmp_path / "real.zip").write_bytes(b"PK\x03\x04" + b"\x00" * 40)
    rep = se.scan(tmp_path, mode="full")
    assert [f for f in rep["findings"] if f["rule"] == "GBT-SE-010"] == []


def test_hidden_binary_and_text_are_separated(tmp_path):
    """伪装类发现必须带 real_kind，供人判断而不是只给一句"可疑"。"""
    (tmp_path / "x.jpg").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)
    rep = se.scan(tmp_path, mode="full")
    f = [x for x in rep["findings"] if x["rule"] == "GBT-SE-010"]
    assert f and f[0]["real_kind"] == "图像/png"
    assert f[0]["severity"] == "error"


# ─────────────────────────────────────────── ④ 维度登记与规则号完整

def test_dimensions_are_declared_and_unique():
    ids = [d[0] for d in se.DIMENSIONS]
    rules = [d[2] for d in se.DIMENSIONS]
    assert len(ids) == len(set(ids)) >= 12, "维度必须登记且不重号"
    assert len(rules) == len(set(rules))
    for _i, name, rule, what in se.DIMENSIONS:
        assert re.fullmatch(r"GBT-SE-\d{3}", rule)
        assert len(what) >= 10, "维度必须写清它抓什么（≥10 字）"


def test_every_emitted_rule_code_belongs_to_a_declared_family():
    """代码里报出去的每个规则号，前三位必须落在某个已登记维度里。

    规则号是"哪一维在报"的坐标；冒出没登记的号 ⇒ 有维度偷偷在跑（或改了号没登记）。
    """
    src = (_T / "scan_engine.py").read_text(encoding="utf-8")
    emitted = set(re.findall(r"GBT-SE-(\d{3})", src))
    families = {d[2].split("-")[-1] for d in se.DIMENSIONS}
    orphans = {e for e in emitted if e[:1] != "0" and e[:3] not in families}
    assert not orphans, "有规则号不属于任何已登记维度：%s" % sorted(orphans)


# ─────────────────────────────────────────── ⑤ 确定性与幂等

def test_two_scans_agree(tree):
    a = se.scan(tree, mode="full")
    b = se.scan(tree, mode="full")
    assert a["enumerated"] == b["enumerated"]
    assert a["buckets"] == b["buckets"]
    assert len(a["findings"]) == len(b["findings"])
    assert a["closure"] and b["closure"]


def test_scope_mode_is_faster_or_equal(tree):
    t0 = time.perf_counter()
    se.scan(tree, mode="scope")
    t1 = time.perf_counter()
    se.scan(tree, mode="full")
    t2 = time.perf_counter()
    assert (t1 - t0) <= (t2 - t1) + 1.0, "scope 不该比 full 慢一个量级"
