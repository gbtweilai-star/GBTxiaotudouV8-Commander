"""Probe every capability through the single gate (run_task), each in its own subprocess.

Safety envelope:
  * caps flagged side-effect by the repo's own preflight.is_side_effect  -> skipped
  * caps that fire network / spawn GUI / capture screen                   -> skipped (manual list)
  * everything else runs with an empty payload + probe=True (no audit rows written)
  * hard timeout per call, child killed
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# 收编进仓后（2026-11-01）：本文件在 tools/ 下，仓库根 = tools/ 的上一级。
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = BASE
# 解释器：优先环境变量 GBT_PYTHON；否则用工作区的 embeddable（pyembed 与仓库同级）
PY = os.environ.get("GBT_PYTHON") or os.path.join(os.path.dirname(BASE), "pyembed", "python.exe")
PROBE = os.path.join(BASE, "tools", "probe-one.py")
TIMEOUT = 20
WORKERS = 8

SKIP_NETWORK_UI = {
    # network / cloud / keys
    "osint_scan", "scrapling", "cloud_llm", "warm_switch", "repo_publish", "image_scout",
    "hf_voice", "i2v_agnes", "genoffice_bridge", "key_gateway", "multimodal_port",
    # desktop / screen / audio / GUI
    "body_map", "body_see", "tentacle", "tentacle_manifest", "desktop_commander",
    "mcp_connect", "mcp_tools", "task_manager", "comfyui", "comfy_native",
    "tentacle_comfy_bridge", "digital_human", "voice_studio", "blender", "genoffice",
    "lobehub", "freebuff_term", "install_selfcheck", "browser",
    # heavy full-tree scans
    "selfscan", "cross_scan", "penetrating_cross_scan", "hook_enforcer", "omission_detector",
    "page_scan", "sec_sweeper", "truth_scan", "ghost_guard", "signature_guard",
    "file_hygiene", "devour_scan",
}


def probe(kind):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run(
            [PY, "-X", "utf8", PROBE, REPO, kind],
            cwd=REPO, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=TIMEOUT, env=env,
        )
        txt = (r.stdout or "").strip()
        if not txt:
            return {"kind": kind, "status": "no_output", "stderr": (r.stderr or "")[-300:]}
        return json.loads(txt.splitlines()[-1])
    except subprocess.TimeoutExpired:
        return {"kind": kind, "status": "timeout", "ms": TIMEOUT * 1000}
    except Exception as e:  # noqa: BLE001
        return {"kind": kind, "status": "driver_error", "error": "%s: %s" % (type(e).__name__, str(e)[:200])}


def main():
    limit = int(os.environ.get("PROBE_LIMIT") or 0)
    # 能力清单：仓内快照（data/capabilities.json）——不再依赖工作区根的临时 JSON
    inv = json.load(open(os.path.join(REPO, "data", "capabilities.json"), encoding="utf-8"))
    names = [c["name"] for c in inv["capabilities"]]

    side = set()
    try:
        pf = json.load(open(os.path.join(BASE, "preflight.json"), encoding="utf-8"))
        side = {x["kind"] for x in pf if x.get("side") is True}
    except Exception:
        pass

    if limit:
        names = names[:limit]
    todo, skipped = [], []
    for n in names:
        if n in side:
            skipped.append({"kind": n, "why": "side_effect"})
        elif n in SKIP_NETWORK_UI:
            skipped.append({"kind": n, "why": "network_ui_heavy"})
        else:
            todo.append(n)

    print("probe:", len(todo), "skip:", len(skipped), flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(probe, n): n for n in todo}
        for i, f in enumerate(as_completed(futs), 1):
            results.append(f.result())
            if i % 40 == 0:
                print("  done", i, "/", len(todo), flush=True)

    results.sort(key=lambda r: r["kind"])
    out = {"probed": len(todo), "skipped": skipped, "results": results}
    with open(os.path.join(BASE, "caps-probe.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    buckets = {}
    for r in results:
        buckets[r.get("status")] = buckets.get(r.get("status"), 0) + 1
    print(json.dumps(buckets, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
