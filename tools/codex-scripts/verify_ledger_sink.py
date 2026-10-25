# -*- coding: utf-8 -*-
"""验证「四路账本承载物切换」真的生效 —— 全程在**临时根**里跑，不碰真账本。

验四件事：
  ① 未开启常驻化：行落 .scratch（行为与改前一致）
  ② 开启常驻化：行落 store/ledger/<lane>.jsonl，且层名映射正确（panel→panel.send 等）
  ③ 不开就不建目录：store/ledger/ 不许被凭空建出来（《反空壳律》）
  ④ 四个探针的 _SINK **真能解析到**（抽它们文件里那段 _load_sink 原文来跑，不用副本）
另加：④ 跑完确认**真账本目录仍不存在**（没被验证过程污染）。
"""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
LEDGER_DIR = ROOT / "holo_pet_w3" / "ledger"
SINK_PY = LEDGER_DIR / "sink.py"
MIRROR = ROOT / ".scratch" / "codex_v2_mirror"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = fail = 0


def chk(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("  ✓ %-52s %s" % (name, detail))
    else:
        fail += 1
        print("  ✗ %-52s %s" % (name, detail))


def load_sink():
    spec = importlib.util.spec_from_file_location("gbt_ledger_sink", SINK_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LANES = ("panel", "bridge", "route", "mock")
EXPECT_LAYER = {"panel": "panel.send", "bridge": "bridge",
                "route": "route.recv", "mock": "mock.recv"}

REAL_STORE = ROOT / "gbt_allinone" / "store" / "ledger"
real_existed_before = REAL_STORE.exists()
print("真账本目录（验证前）存在: %s" % real_existed_before)

with tempfile.TemporaryDirectory(prefix="gbt_sink_verify_") as tmp:
    fake_root = Path(tmp)
    (fake_root / "gbt_allinone" / "store").mkdir(parents=True, exist_ok=True)
    scratch = fake_root / ".scratch"
    scratch.mkdir(parents=True, exist_ok=True)

    # ── ① 未开启：落 .scratch ──
    os.environ.pop("GBT_LEDGER_PERSIST", None)
    sink = load_sink()
    chk("① 默认 persist_enabled=False", sink.persist_enabled() is False, "")
    rec = {"event": "test.off", "layer": "panel", "frame_bytes_hash": "deadbeefdeadbeef"}
    r1 = sink.write(rec, scratch / "panel.jsonl", "panel", root=fake_root)
    chk("① 未开启时落 .scratch", str(scratch) in str(r1.get("path", "")),
        Path(r1.get("path", "")).name)
    chk("① 未开启时**不**建 store/ledger",
        not (fake_root / "gbt_allinone" / "store" / "ledger").exists(), "")

    # ── ② 开启：落 store/ledger，层名映射正确 ──
    os.environ["GBT_LEDGER_PERSIST"] = "1"
    sink = load_sink()
    chk("② persist_enabled=True", sink.persist_enabled() is True, "")
    for lane in LANES:
        rr = sink.write({"event": "test.on." + lane, "layer": lane,
                         "frame_bytes_hash": "cafebabe0000000" + str(len(lane))},
                        scratch / (lane + ".jsonl"), lane, root=fake_root)
        p = Path(str(rr.get("path", "")))
        chk("② %-6s 落 store/ledger/%s" % (lane, EXPECT_LAYER[lane]),
            p.parent.name == "ledger" and p.name ==
            {"panel": "panel.send.jsonl", "bridge": "bridge.jsonl",
             "route": "route.recv.jsonl", "mock": "mock.recv.jsonl"}[lane],
            p.name)

    # ── ③ 四路各有行、可被 ledger_store 读回 ──
    store_mod = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("ls", LEDGER_DIR / "ledger_store.py"))
    importlib.util.spec_from_file_location(
        "ls", LEDGER_DIR / "ledger_store.py").loader.exec_module(store_mod)
    rows = {lay: len(store_mod.tail(lay, 50, root=fake_root)) for lay in store_mod.LAYERS}
    chk("③ 四路各 1 行（读回）", all(v == 1 for v in rows.values()), json.dumps(rows))

    # ── ④ 四个探针的 _SINK 真能解析（抽原文那一段来跑）──
    for fname, lane in (("panel_probe.py", "panel"), ("bridge_probe.py", "bridge"),
                        ("route_probe.py", "route"), ("mock_v2_server.py", "mock")):
        p = MIRROR / fname
        src = io.open(p, encoding="utf-8", errors="replace").read()
        m = ast.parse(src)
        seg = None
        for node in m.body:
            if isinstance(node, ast.FunctionDef) and node.name == "_load_sink":
                seg = ast.get_source_segment(src, node)
                break
        assigned = "_SINK = _load_sink()" in src and '_SINK_LANE = "%s"' % lane in src
        got = False
        detail = "未抽到 _load_sink"
        if seg:
            ns = {"__file__": str(p)}
            try:
                exec(compile(seg, str(p), "exec"), ns)
                got = ns["_load_sink"]() is not None
                detail = "_load_sink() -> %s" % ("sink 模块" if got else "None")
            except Exception as e:  # noqa: BLE001
                detail = "执行失败: %s" % str(e)[:60]
        chk("④ %-18s _SINK 可解析且 lane=%s" % (fname, lane),
            got and assigned, detail)

os.environ.pop("GBT_LEDGER_PERSIST", None)

# ── 真账本没被污染 ──
chk("真账本目录未被建出（验证全程用临时根）",
    REAL_STORE.exists() == real_existed_before,
    "exists=%s" % REAL_STORE.exists())

shutil.rmtree(Path(tempfile.gettempdir()) / "gbt_sink_verify_", ignore_errors=True)
print("\n" + "-" * 78)
print("通过 %d · 失败 %d" % (ok, fail))
sys.exit(0 if fail == 0 else 1)
