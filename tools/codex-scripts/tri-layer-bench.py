# -*- coding: utf-8 -*-
"""三层操作流畅度基准台 · 把「流畅」从感觉变成**能复跑的读数**。

测三层（Owner 指定默认主线道，全部同步）：
  · 大脑执行层  `gbt_allinone/engine.py`   并行 DAG 编排（同进程，无冷启动）
  · 万能插      `tools/codex-scripts/omni.py`  人话 → 落点 → 真跑
  · 五维合一    `tools/codex-scripts/five-dim.py`  脑-眼-耳-嘴-手信封 + 能力位入口

四把尺子（每一把都**可证伪**，不是"看着挺好"）：

  尺1 能用吗  三个入口各真跑一次，报退出码与状态。
  尺2 快吗    冷/热两档毫秒数**分开量** —— 合起来量会把冷启动摊掉，看不出瓶颈。
  尺3 顺吗    四个卡点逐个机检（F1 名字打偏 / F2 出口自证信封 / F3 提示别撒谎 / F4 默认输出别收走答案）。
  尺4 骗不骗  一票**负对照**：`--no-envelope` 必须读出 `synced:false`。
              尺子测不出假，就不算尺子。

用法:
  py -3.14 tools/codex-scripts/tri-layer-bench.py
  py -3.14 tools/codex-scripts/tri-layer-bench.py --json     # 只吐 JSON
  py -3.14 tools/codex-scripts/tri-layer-bench.py --quick    # 跳过最慢的脉搏面

退出码 = 0 全过；1 有 FAIL。**PENDING 不计入 PASS。**
"""
import json
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
# 2026-09-23 磨（本台第一次跑就抓到自己，连抓两次）：
#   第一版死写 `[PY, "-3.14", ...]` —— `sys.executable` 是**解释器本体**，对它传 `-3.14`
#   会被当非法选项 ⇒ 每条探针 15 ms 就 exit 2（若把 exit 2 读成"跑完了"，整台就是**假绿**）。
#   第二版想修，写的判据是 `Path(PY).name.lower().startswith("py")` —— 而
#   **"python.exe" 也是以 "py" 开头的**，`-3.14` 照样被加给解释器本体，症状一模一样。
#   ⇒ 教训：**前缀匹配不是相等匹配**。只认 `stem == "py"`（py 启动器）。
_PY = sys.executable or "py"
LAUNCH = [_PY, "-3.14"] if Path(_PY).stem.lower() == "py" else [_PY]
FIVE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
OMNI = ROOT / "tools" / "codex-scripts" / "omni.py"
AUDIT = ROOT / "gbt_allinone" / "store" / "audit.jsonl"

ROWS = []


def _run(argv, timeout=180):
    """跑一条命令，返回 (退出码, 原始输出, 毫秒)。输出永远拿到手，不因非零退出丢证据。"""
    t0 = time.time()
    try:
        p = subprocess.run([*LAUNCH, "-u", *argv], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, cwd=str(ROOT))
        out = (p.stdout or "") + (p.stderr or "")
        rc = p.returncode
    except subprocess.TimeoutExpired:
        out, rc = "[超时]", -9
    return rc, out, int((time.time() - t0) * 1000)


def _load_json(out):
    """从输出里把那个 JSON 对象捞出来（前面可能夹着提示行）。"""
    s = out.find("{")
    while s != -1:
        try:
            return json.loads(out[s:])
        except Exception:                                        # noqa: BLE001
            s = out.find("{", s + 1)
    return None


def row(name, layer, ok, detail, ms=None, pending=False, ev=None):
    """记一行读数。

    `ev` = FAIL 时的**原始输出尾巴**。为什么要它：一个只有结论没有证据的 FAIL，
    下一个人只能靠猜（本台自己前两次 FAIL 就吃了这个亏 —— exit=2、15 ms，
    看不出是"命令坏了"还是"尺子写错了"）。**失败的项必须自带证据。**
    """
    if ev and not ok:
        tail = " ".join(str(ev).split())[-180:]
        detail = "%s ｜ 原始输出: %s" % (detail, tail or "(空)")
    ROWS.append({"尺": name.split("·")[0].strip(), "项": name, "层": layer,
                 "结论": "PENDING" if pending else ("PASS" if ok else "FAIL"),
                 "读数": detail, "ms": ms})


def _pulse_tail(kinds, tail_bytes=524288):
    """从审计账本末尾现读：刚才那几个 kind 有没有留下 `call` 记录（= 触手脉冲有没有流出来）。"""
    if not AUDIT.is_file():
        return None, "账本不在"
    size = AUDIT.stat().st_size
    with AUDIT.open("rb") as fh:
        fh.seek(max(0, size - tail_bytes))
        raw = fh.read().decode("utf-8", errors="replace")
    lines = raw.splitlines()
    if size > tail_bytes and lines:
        lines = lines[1:]
    seen = {}
    for ln in lines:
        if '"call"' not in ln:
            continue
        try:
            e = json.loads(ln)
        except Exception:                                        # noqa: BLE001
            continue
        if e.get("event") != "call":
            continue
        m = e.get("meta") or {}
        k = m.get("kind")
        if k in kinds:
            seen[k] = {"synced": bool(m.get("synced")), "entry": m.get("synced_entry")}
    return seen, None


def main(argv):
    as_json = "--json" in argv
    quick = "--quick" in argv
    t_start = time.time()

    # ── 尺1/尺2：三层能不能用、冷热各多快 ──────────────────────────────
    layers = [
        ("五维合一", [str(FIVE), "ruler"]),
        ("万能插", [str(OMNI), "caliber"]),
        ("大脑执行层", [str(FIVE), "cap", "wf_status", '{"limit":1}']),
    ]
    timings = {}
    for label, cmd in layers:
        rc1, out1, ms1 = _run(cmd)                     # 冷（本进程第一次）
        rc2, out2, ms2 = _run(cmd)                     # 热（再来一次）
        timings[label] = {"冷_ms": ms1, "热_ms": ms2, "exit": rc2}
        ok = rc2 == 0
        row("尺1·能用 %s" % label, label, ok, "exit=%d" % rc2, ms2, ev=out2)
        row("尺2·延迟 %s" % label, label, ms2 < 3000,
            "冷 %d ms → 热 %d ms" % (ms1, ms2), ms2, ev=out2)

    # ── 尺3：四个卡点（都是本会话实测撞到并磨掉的）──────────────────────
    # F1 名字打偏：必须给最近邻，否则是死路
    rc, out, ms = _run([str(FIVE), "cap", "wf_list"])
    j = _load_json(out) or {}
    r = j.get("result") or {}
    near = r.get("did_you_mean") or []
    row("尺3·F1 名字打偏给最近邻", "五维合一", "wf_status" in near,
        "wf_list → %s" % (near or "无提示（死路）"), ms)

    # F2 出口自证信封：结果里必须带 _信封，且是**账本读回来的**
    rc, out, ms = _run([str(FIVE), "cap", "health"])
    j = _load_json(out) or {}
    env = j.get("_信封") or {}
    row("尺3·F2 出口自证信封", "五维合一", bool(env.get("found")) and "synced" in env,
        "synced=%s entry=%s" % (env.get("synced"), env.get("entry")), ms)

    # F3 提示别撒谎：未知子命令给的 supported 必须等于真命令表
    rc, out, ms = _run([str(FIVE), "__nope__"])
    j = _load_json(out) or {}
    sup = set(j.get("supported") or [])
    want = {"ruler", "open", "close", "run", "check", "wrap", "cap"}
    row("尺3·F3 提示与真命令一致", "五维合一", sup == want,
        "缺 %s · 多 %s" % (sorted(want - sup) or "无", sorted(sup - want) or "无"), ms)

    # F4 默认输出别把答案收走：不夹 --full 也要看得到人真正要的东西
    rc, out, ms = _run([str(FIVE), "cap", "wf_status", '{"include_workflows":true,"limit":1}'])
    j = _load_json(out) or {}
    res = j.get("result") or {}
    has = bool((res.get("preview") or {}).get("workflows"))
    row("尺3·F4 默认输出带答案", "五维合一", has,
        "preview.workflows %s" % ("在" if has else "被收走了（只报键名）"), ms)

    # ── 尺4：负对照 —— 尺子测得出假吗 ─────────────────────────────────
    rc, out, ms = _run([str(FIVE), "cap", "health", "--no-envelope"])
    j = _load_json(out) or {}
    env = j.get("_信封") or {}
    row("尺4·负对照 --no-envelope", "五维合一",
        env.get("found") is True and env.get("synced") is False,
        "found=%s synced=%s entry=%s" % (env.get("found"), env.get("synced"), env.get("entry")), ms)

    # ── 大脑执行层真干活：整条 DAG 跑通 ───────────────────────────────
 # 加 `--full` 的理由（本台第三次抓到自己）：默认出口会**收窄 result**，
    # 于是 `nodes` 落在 `result.preview.nodes` 而不是 `result.nodes` ——
    # 我第一版探针直接读 `result.nodes`，拿到 0 节点，报了个**假 FAIL**。
    # 教训：**机器消费方用 --full**（收窄是给人看的，给人看的东西不该被脚本当契约）。
    rc, out, ms = _run([str(FIVE), "cap", "wf_run", '{"name":"三层并联体检"}', "--full"])
    j = _load_json(out) or {}
    r = j.get("result") or {}
    nodes = r.get("nodes") or (r.get("preview") or {}).get("nodes") or {}
    allok = bool(nodes) and all(v == "ok" for v in nodes.values())
    row("尺1·大脑执行层真跑 DAG", "大脑执行层", j.get("status") == "ok" and allok,
        "%d 节点 · DAG 内 elapsed_s=%s · 墙钟 %d ms" % (len(nodes), r.get("elapsed_s"), ms),
        ms, ev=out)

    # ── 脉搏面：刚才这些调用有没有真流到触手脉冲上 ─────────────────────
    if not quick:
        kinds = {"wf_run", "wf_status", "health", "transfer"}
        seen, err = _pulse_tail(kinds)
        if err:
            row("尺3·触手脉冲可读", "万能插", False, err)
        else:
            hit = sorted(k for k in kinds if k in seen)
            insync = [k for k in hit if seen[k]["synced"]]
            row("尺3·触手脉冲流出且同步", "万能插", len(hit) >= 3 and len(insync) == len(hit),
                "末尾账本命中 %d/%d 个 kind，全 synced=%s"
                % (len(hit), len(kinds), len(insync) == len(hit)))

    npass = sum(1 for r in ROWS if r["结论"] == "PASS")
    nfail = sum(1 for r in ROWS if r["结论"] == "FAIL")
    npend = sum(1 for r in ROWS if r["结论"] == "PENDING")
    summary = {"总耗时_s": round(time.time() - t_start, 1),
               "PASS": npass, "FAIL": nfail, "PENDING": npend,
               "口径": "PENDING ≠ PASS；负对照不过则整台作废（尺子测不出假就不是尺子）"}

    if as_json:
        print(json.dumps({"尺子": ROWS, "总账": summary}, ensure_ascii=False, indent=1))
    else:
        print("=" * 78)
        print("三层操作流畅度基准台")
        print("=" * 78)
        for r in ROWS:
            mark = {"PASS": "PASS", "FAIL": "FAIL", "PENDING": "PEND"}[r["结论"]]
            ms = ("%6d ms" % r["ms"]) if r.get("ms") is not None else "        "
            print("  [%s] %-26s %-12s %s  %s" % (mark, r["项"], r["层"], ms, r["读数"]))
        print("-" * 78)
        for k, v in timings.items():
            print("  延迟档位 %-12s 冷 %5d ms  热 %5d ms" % (k, v["冷_ms"], v["热_ms"]))
        print("-" * 78)
        print("  合计 PASS %d · FAIL %d · PENDING %d · %s s" %
              (npass, nfail, npend, summary["总耗时_s"]))
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
