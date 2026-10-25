# -*- coding: utf-8 -*-
"""四路对齐判据（《M9判据收口.md》§3.2）的回归 —— 全在临时根跑，不碰真账本。

逐条验权威口径：
  · PASS          同一条请求（同一 raw_tid）在四路都有记录，且帧指纹集合一致
  · FAIL(指纹)    四路都有记录但指纹不一致（帧被改 / 被截断 / 漏记）
  · FAIL(长度)    指纹一致但 frame_bytes 不等 —— 按异常处理
  · INCONCLUSIVE  任一路没有该键的行 —— 自成一档，不许折算 PASS
  · 无关联键      四路都没盖 raw_tid/round_id ⇒ 必须说"没得比"，不许报"一致"
  · 一 thread 多请求：按集合比对，不许"每路取最后一行"（那是在比两条不同请求）
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
LEDGER_DIR = ROOT / "holo_pet_w3" / "ledger"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

spec = importlib.util.spec_from_file_location("ls", LEDGER_DIR / "ledger_store.py")
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)

ok = fail = 0


def chk(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("  ✓ %-50s %s" % (name, detail))
    else:
        fail += 1
        print("  ✗ %-50s %s" % (name, detail))


def seed(root, layer, rows):
    for r in rows:
        ls.append(layer, r, root)


with tempfile.TemporaryDirectory(prefix="gbt_m9_verify_") as tmp:
    root = Path(tmp)
    (root / "gbt_allinone" / "store").mkdir(parents=True, exist_ok=True)

    # ① 四路同键同指纹 → PASS
    for lay in ls.LAYERS:
        seed(root, lay, [{"event": "x", "layer": lay, "raw_tid": "t1",
                          "frame_bytes": 128, "frame_bytes_hash": "aaaa1111bbbb2222"}])
    v = ls.verify("t1", root=root)
    chk("① 四路同键同指纹 → PASS", v["verdict"] == "PASS",
        "key_field=%s rows=%s" % (v.get("key_field"), v.get("rows")))

    # ② 一路指纹被改 → FAIL
    seed(root, "mock.recv", [{"event": "x", "layer": "mock.recv", "raw_tid": "t2",
                              "frame_bytes": 128, "frame_bytes_hash": "aaaa1111bbbb2222"}])
    for lay in ("panel.send", "bridge", "route.recv"):
        seed(root, lay, [{"event": "x", "layer": lay, "raw_tid": "t2",
                          "frame_bytes": 128, "frame_bytes_hash": "aaaa1111bbbb2222"}])
    seed(root, "bridge", [{"event": "x", "layer": "bridge", "raw_tid": "t2",
                           "frame_bytes": 120, "frame_bytes_hash": "deadbeefdeadbeef"}])
    v = ls.verify("t2", root=root)
    chk("② 一路指纹不一致 → FAIL", v["verdict"] == "FAIL", str(v.get("note"))[:40])

    # ③ 指纹一致但长度不等 → FAIL（二次核对）—— 四路都要有行，否则会（正确地）先报 INCONCLUSIVE
    for lay in ls.LAYERS:
        _fb = 999 if lay == "panel.send" else 128
        seed(root, lay, [{"event": "x", "layer": lay, "raw_tid": "t3",
                          "frame_bytes": _fb, "frame_bytes_hash": "cccc3333dddd4444"}])
    v = ls.verify("t3", root=root)
    chk("③ 指纹同但 frame_bytes 不等 → FAIL", v["verdict"] == "FAIL",
        str(v.get("note"))[:44])

    # ④ 缺一路 → INCONCLUSIVE
    for lay in ("panel.send", "bridge"):
        seed(root, lay, [{"event": "x", "layer": lay, "raw_tid": "t4",
                          "frame_bytes": 64, "frame_bytes_hash": "eeee5555ffff6666"}])
    v = ls.verify("t4", root=root)
    chk("④ 缺观测点 → INCONCLUSIVE（不许折算 PASS）", v["verdict"] == "INCONCLUSIVE",
        "missing=%s" % v.get("missing"))

    # ⑤ 谁都没盖关联键 → 必须说"没得比"
    for lay in ls.LAYERS:
        seed(root, lay, [{"event": "x", "layer": lay,
                          "frame_bytes": 10, "frame_bytes_hash": "9999"}])
    v = ls.verify("nosuchkey", root=root)
    chk("⑤ 无关联键 → INCONCLUSIVE 且说明「没得比」",
        v["verdict"] == "INCONCLUSIVE" and "没得比" in str(v.get("note")),
        "key_field=%s" % v.get("key_field"))

    # ⑥ 一条 thread 上两条请求：按集合比对
    for lay in ls.LAYERS:
        seed(root, lay, [{"event": "x", "layer": lay, "raw_tid": "t6",
                          "frame_bytes": 100, "frame_bytes_hash": "h-one"},
                         {"event": "x", "layer": lay, "raw_tid": "t6",
                          "frame_bytes": 200, "frame_bytes_hash": "h-two"}])
    v = ls.verify("t6", root=root)
    chk("⑥ 同 thread 多请求按集合比对 → PASS",
        v["verdict"] == "PASS" and v.get("rows", {}).get("bridge") == 2,
        "rows=%s hashes=%s" % (v.get("rows"), v.get("hashes")))
    # 6b：同样的多请求，但一路少记了一条 → 集合不等 ⇒ FAIL（不是"一致"）
    seed(root, "route.recv", [{"event": "x", "layer": "route.recv", "raw_tid": "t7",
                               "frame_bytes": 100, "frame_bytes_hash": "h-one"}])
    for lay in ("panel.send", "bridge", "mock.recv"):
        seed(root, lay, [{"event": "x", "layer": lay, "raw_tid": "t7",
                          "frame_bytes": 100, "frame_bytes_hash": "h-one"},
                         {"event": "x", "layer": lay, "raw_tid": "t7",
                          "frame_bytes": 200, "frame_bytes_hash": "h-two"}])
    v = ls.verify("t7", root=root)
    chk("⑥b 一路漏记一条 → FAIL（集合不等）", v["verdict"] == "FAIL",
        "rows=%s" % v.get("rows"))

# self_test 仍须通过（它用 round_id 作键，走回退路径）
st = ls.self_test()
chk("⑦ self_test 仍 PASS（round_id 回退路径）", st["ok"] is True,
    "key_field=%s" % st["verdict"].get("key_field"))

print("\n" + "-" * 78)
print("通过 %d · 失败 %d" % (ok, fail))
sys.exit(0 if fail == 0 else 1)
