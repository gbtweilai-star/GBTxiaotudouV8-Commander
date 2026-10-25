# -*- coding: utf-8 -*-
"""comfy_cloud 判据件（不起卡、不出网、不烧钱）—— 只验"接线与门"。

跑法：py -3.10 -m pytest gbt_allinone/tests/test_comfy_cloud.py -q
      （没装 pytest 就直接 `py -3.10 gbt_allinone/tests/test_comfy_cloud.py`）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gbt_allinone.security import policy                    # noqa: E402
from gbt_allinone.tools import comfy_cloud as cc            # noqa: E402


def test_ops_listed():
    for op in ("status", "nodes", "models", "queue", "history", "submit", "video", "fetch", "free"):
        assert op in cc._OPS, op


def test_unknown_op_fails_closed():
    r = cc.run_dispatch("rm_rf_everything")
    assert r["ok"] is False and r["fail_closed"] is True
    assert "available" in r


def test_video_needs_brief():
    r = cc.run_dispatch("video", brief="")
    assert r["ok"] is False and r["fail_closed"] is True


def test_submit_needs_graph():
    r = cc.run_dispatch("submit")
    assert r["ok"] is False and r["fail_closed"] is True


def test_defaults_avoid_the_bad_checkpoint():
    """卡上 mm_sd_v15_v2.ckpt 实测认不出类型 ⇒ 默认不许用它。"""
    assert cc.SD15 != cc.BAD_CKPT
    assert cc.SD15 == "v1-5-pruned-emaonly-fp16.safetensors"
    assert cc.SVD == "svd_xt.safetensors"


def test_policy_scopes():
    """读类要 process_execute（本机到 8188 没路，读也得在卡里读）；写类再叠 filesystem_write。"""
    for op in ("status", "nodes", "models", "queue", "history"):
        s = set(policy.evaluate("comfy_cloud", {"op": op}).scopes)
        assert "process_execute" in s, (op, s)
    assert set(policy.evaluate("comfy_cloud", {"op": "video"}).scopes) >= {
        "process_execute", "filesystem_write"}
    assert set(policy.evaluate("comfy_cloud", {"op": "fetch"}).scopes) == {"filesystem_write"}
    unknown = set(policy.evaluate("comfy_cloud", {"op": "whatever"}).scopes)
    assert unknown >= {"process_execute", "data_export", "filesystem_write"}   # fail-closed


def _main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        try:
            fn()
            print("PASS %s" % fn.__name__)
            ok += 1
        except AssertionError as exc:
            print("FAIL %s -> %s" % (fn.__name__, exc))
    print("%d/%d 通过" % (ok, len(fns)))
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
