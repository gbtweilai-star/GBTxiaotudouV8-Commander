#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""写口位（safe=False）真跑一轮：能证明"写得动"，且**不碰生产路径**。

做法与边界（写死）：
  · 隔离 store（GBT_STORE_DIR 指到临时目录）⇒ 落 store 的写入全在临时账上；
  · 非主人会话 ⇒ deploy_publish / process_execute / external_llm / data_export 这类护栏当场 denied（正好当证据）；
  · **高危白名单不跑**（下面 BLOCK）：会写生产交付区 / 起外部进程 / 打外部网络 / 改版本库 / 渲染大件的那批，
    一律标 `skipped_high_risk` 并写清原因 —— 不拿主人的仓库当试验场；
  · payload 一律 {}(+必要的 op=status)，**不硬编参数**：缺参就如实记 needs_input。

产出：outputs/open-source-release/data/write-face-probe.json
用法：py -3.12 tools/codex-scripts/probe-caps-write.py
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import pathlib
import sys
import tempfile
import time
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.environ["GBT_STORE_DIR"] = str(pathlib.Path(tempfile.mkdtemp(prefix="gbt_write_store_")))
os.environ.pop("GBT_OWNER_SESSION", None)
sys.path.insert(0, str(ROOT))

from gbt_allinone import caps_registry as R          # noqa: E402
from gbt_allinone.api import run_task                # noqa: E402

OUT = ROOT / "outputs" / "open-source-release" / "data" / "write-face-probe.json"

# 高危：会写生产交付区 / 起进程 / 出网 / 改版本库 / 渲染大件 —— 不拿真仓库试
BLOCK = {
    "one_key_deploy", "qiankun", "deployment_rehearsal", "mirror_shape", "mirror_release",
    "mirror_ascend", "mirror_rewind", "mirror_rehearse", "room_create", "room_shape",
    "room_plan", "room_simulate", "room_parity", "room_rehearse", "room_release",
    "pipeline_submit", "pipeline_rollback", "git_write", "code_patch", "auto_publish",
    "devour_github", "devour_crawl", "devour_reflect", "devour_fusion", "coze_mail",
    "cloud_pc", "remote_domain", "voice", "vision", "tentacle", "ul_tars_desktop",
    "browser", "native_browser", "omni_web", "codex_turn_send", "codex_thread_new",
    "codex_interrupt", "cli_chat", "h3_video_gen", "media_pipeline", "film_factory",
    "digital_human", "dh_build", "video_render", "create", "drama", "music_publishing",
    "brand_outro", "code_art", "render_evolution", "scene_anchor", "emotion_projection",
    "a1art_skill", "libtv_skill", "libtv_workflow", "tripo", "blender",
}
TIMEOUT = 25


def unwrap(resp):
    b = resp.get("gbt_result", resp) if isinstance(resp, dict) else {}
    inner = b.get("result") if isinstance(b, dict) else None
    return (b if isinstance(b, dict) else {}), (inner if isinstance(inner, dict) else {})


def classify(b, i):
    if b.get("denied") or i.get("denied"):
        miss = b.get("missing") or i.get("missing") or []
        return "needs_ticket", "缺票：" + ",".join(miss)
    st = str(b.get("status") or "")
    msg = str(b.get("error") or b.get("message") or i.get("error") or i.get("reason") or "")
    if st == "ok" and i.get("ok") is not False:
        return "ok", "真跑通过（写入落临时 store）"
    if st == "needs_dependency" or "needs_dependency" in msg:
        return "needs_dependency", msg[:150]
    if "user_error" in str(b.get("error_class") or "") or any(
            k in msg for k in ("需要", "缺少", "必填", "不能为空")):
        return "needs_input", msg[:150]
    return "failed", (msg or st)[:150]


def one(cap: str) -> dict:
    t0 = time.time()
    try:
        with cf.ThreadPoolExecutor(max_workers=1) as ex:
            resp = ex.submit(run_task, cap, {}).result(timeout=TIMEOUT)
        b, i = unwrap(resp)
        v, note = classify(b, i)
        st = b.get("status")
    except cf.TimeoutError:
        v, note, st = "timeout", "> %ds" % TIMEOUT, "timeout"
    except Exception as e:                                    # noqa: BLE001
        v, note, st = "failed", "%s: %s" % (type(e).__name__, str(e)[:140]), "exception"
    return {"cap": cap, "status": st, "verdict": v, "note": note,
            "elapsed_s": round(time.time() - t0, 2)}


def main() -> int:
    caps = [c["name"] for c in R.all_caps() if not c.get("safe")]
    run = [c for c in caps if c not in BLOCK]
    skipped = [c for c in caps if c in BLOCK]
    print("写口位 %d 个：真跑 %d · 高危未跑 %d" % (len(caps), len(run), len(skipped)))
    rows = []
    for c in run:
        r = one(c)
        rows.append(r)
        print("  %-24s %-16s %s" % (r["cap"], r["verdict"], r["note"][:60]))
    cnt: dict[str, int] = {}
    for r in rows:
        cnt[r["verdict"]] = cnt.get(r["verdict"], 0) + 1
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "store": os.environ["GBT_STORE_DIR"],
           "total_write_face": len(caps), "ran": len(run), "skipped_high_risk": len(skipped),
           "counts": cnt, "rows": rows, "skipped": sorted(skipped),
           "口径": "隔离 store + 非主人会话；空 payload 不硬编参数；高危白名单不动真仓库"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n计数：", cnt)
    print("落账 →", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
