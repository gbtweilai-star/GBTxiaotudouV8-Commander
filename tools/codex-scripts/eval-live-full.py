# -*- coding: utf-8 -*-
"""修题库 + 线上全量重测（335 题，同判据同解码参数），逐条留读数。

修订两处（都留痕，不静默改）：
  ① voice_studio：gold 476 字（旧改写）→ 786 字（注册表 desc，唯一真源）
  ② health：题面消歧 ——「系统域的能力位 health 返回什么信息？」
     原题面「能力位 health 是干什么的？」实测会把「面板 /api/state 的 health」当成它
     （答 currentTime/uptime/frames…），三种问法实测已记在 state 台账。

产出：
  .scratch/caps_full_test_v2.json     修订后的题库（与 v1 的差异单独记日志）
  state/model-deploy/live-eval-v2.json 全量读数（逐条 rows）
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gbt_allinone import caps_registry as R  # noqa: E402

RKEY = (ROOT / ".scratch/.runpod_key").read_text(encoding="utf-8").strip()
EP = "https://api.runpod.ai/v2/qnnqf9w8xcefj8/openai/v1/chat/completions"
MODEL = "/runpod-volume/gbt-v8-v83"
TEST_IN = ROOT / ".scratch/caps_full_test.json"
TEST_OUT = ROOT / ".scratch/caps_full_test_v2.json"
OUT = ROOT / "state/model-deploy/live-eval-v2.json"


def segments(gold):
    parts = re.split(r"[。；;！!？?\n]", gold or "")
    segs = [re.sub(r"\s+", "", p) for p in parts]
    return [s for s in segs if len(s) >= 6][:8] or [re.sub(r"\s+", "", gold or "")[:40]]


def budget(gold):
    return min(900, max(180, int(len(gold or "") * 1.1) + 60))


def rebuild():
    tests = json.loads(TEST_IN.read_text(encoding="utf-8"))
    reg = {c["name"]: (c.get("desc") or "") for c in R.all_caps()}
    diffs = []
    for t in tests:
        name = t.get("name") or ""
        desc = reg.get(name)
        if desc and re.sub(r"\s+", "", t.get("gold") or "") != re.sub(r"\s+", "", desc):
            diffs.append({"name": name, "why": "gold≠desc → 用注册表 desc",
                          "old_len": len(t.get("gold") or ""), "new_len": len(desc)})
            t["gold"] = desc
        if name == "health":
            old_q = t.get("q")
            t["q"] = "系统域的能力位 health 返回什么信息？"
            diffs.append({"name": name, "why": "题面消歧（原题面与面板 /api/state 的 health 混淆）",
                          "old_q": old_q, "new_q": t["q"]})
    TEST_OUT.write_text(json.dumps(tests, ensure_ascii=False, indent=1), encoding="utf-8")
    return tests, diffs


def ask(q, mt):
    body = {"model": MODEL, "messages": [{"role": "user", "content": q}],
            "max_tokens": mt, "temperature": 0, "repetition_penalty": 1.15, "stream": False}
    req = urllib.request.Request(EP, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "gbt/1.0",
                                          "Authorization": "Bearer " + RKEY}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            d = json.loads(r.read())
        return (((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""), round(time.time() - t0, 1), None
    except urllib.error.HTTPError as e:
        return "", round(time.time() - t0, 1), "HTTP %s %s" % (e.code, e.read()[:120].decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return "", round(time.time() - t0, 1), "%s: %s" % (type(e).__name__, str(e)[:120])


def main() -> int:
    tests, diffs = rebuild()
    print("题库修订 %d 处：" % len(diffs))
    for d in diffs:
        print("  -", json.dumps(d, ensure_ascii=False)[:160])
    print("开始线上全量：%d 题（并发 4）" % len(tests))

    rows = [None] * len(tests)
    t0 = time.time()
    done = 0

    def work(i):
        t = tests[i]
        q = t.get("q") or ""
        gold = t.get("gold") or ""
        a, el, err = ask(q, budget(gold))
        segs = segments(gold)
        an = re.sub(r"\s+", "", a)
        hit = sum(1 for s in segs if s in an)
        cov = hit / len(segs) if segs else 0.0
        return i, {"name": t.get("name") or "", "cov": round(cov, 4), "elapsed": el,
                   "err": err, "ans": a[:300], "gold_len": len(gold), "segments": len(segs),
                   "named": bool(t.get("name")) and (t.get("name") in a)}

    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for i, row in ex.map(work, range(len(tests))):
            rows[i] = row
            done += 1
            if done % 25 == 0:
                print("  ... %d/%d  (%.1fs)" % (done, len(tests), time.time() - t0), flush=True)

    n = len(rows)
    ok_rows = [r for r in rows if not r["err"]]
    zeros = [r["name"] for r in ok_rows if r["cov"] == 0]
    mean = sum(r["cov"] for r in rows) / n
    pass45 = sum(1 for r in rows if r["cov"] >= 0.45)
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "endpoint": EP, "model": MODEL,
           "n": n, "mean_cov": round(mean, 4), "zero": len(zeros), "zero_names": zeros,
           "pass45": pass45, "pass45_pct": round(pass45 * 100.0 / n, 2),
           "errors": sum(1 for r in rows if r["err"]), "elapsed_s": round(time.time() - t0, 1),
           "test_file": str(TEST_OUT.relative_to(ROOT)), "revisions": diffs, "rows": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("=" * 60)
    print("n=%d · mean=%.4f · PASS45=%d(%.2f%%) · zero=%d · errors=%d · %.1fs"
          % (n, mean, pass45, pass45 * 100.0 / n, len(zeros), out["errors"], out["elapsed_s"]))
    if zeros:
        print("零覆盖：", zeros)
    print("落盘：", OUT.relative_to(ROOT))
    return 0 if not zeros and out["errors"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
