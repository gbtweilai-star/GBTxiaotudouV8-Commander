# -*- coding: utf-8 -*-
"""dagrun · DAG 编排引擎（确定性编译 + 状态机 + 断点续跑 + 差异化重试）
⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印

立项依据：《一句话成片·多智能体自动化架构设计》三条下沉之①（**步骤下沉 = DAG 任务图**）
与十条关键点之 3（**幂等与断点续跑**）、之 8（**预算/重试上限**）、之 10（**能力边界显式化**）。

本件补的是我们此前**没有**的三样：
  · **确定性编译**：`compile_spec()` —— 同一 Spec 两次编译产出**同一 DAG**（节点排序 + 边排序 + canonical sha256）；
  · **状态机 + 断点续跑**：`run_dag()` —— 每节点状态 pending/running/done/failed/retrying/skipped；
    状态落 `*.state.json`；**中断后重跑自动跳过已完成**（完成判据 = 状态 done **且** 产出仍在）；
  · **差异化重试**：失败分两类 —— `mechanical`（超时/瞬时 IO）⇒ 有界重试；
    `fatal`（输入缺失/规格非法）⇒ **判死**（不带病重试）。
另含关键点 10：**每个节点声明能力边界**（能做/需降级/不能做）——节点不知道边界就会幻觉调用。

并发纪律（关键点 2 的本地对应物）：**并发受物理机约束**，默认 4 路（内存压强派单制的本机口径）。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
LEDGER = ROOT / "state" / "dag_runs.jsonl"
DEFAULT_WORKERS = 4                 # 本机 7.39GB 内存硬顶 ⇒ 默认 4 路（不追并发，追跑得完）

TERMINAL = ("done", "failed", "skipped")


def compile_spec(spec: dict) -> dict:
    """**确定性编译**：同一 Spec ⇒ 同一 DAG（哈希相同）。

    规范化三件事：① 节点按 id 排序 ② 依赖列表排序去重 ③ 只保留执行必需字段再哈希
    （注释/备注之类的空字段不进哈希——否则"改个说明"就成新 DAG）。
    """
    raw = spec.get("nodes") or []
    nodes, edges = {}, []
    for n in raw:
        nid = str(n.get("id") or "").strip()
        if not nid:
            raise ValueError("节点缺 id")
        if nid in nodes:
            raise ValueError(f"节点 id 重复：{nid}")
        deps = sorted({str(d) for d in (n.get("depends_on") or [])})
        nodes[nid] = {
            "id": nid, "cmd": list(n.get("cmd") or []),
            "depends_on": deps,
            "boundary": n.get("boundary") or {},
            "retries": int(n.get("retries", 1)),
            "verify_size": int(n.get("verify_size", 0)),
            # ⚠️ 产出路径**必须显式给**（2026-09-27 实测教训：拿 `cmd[-1]` 当产出路径，
            #    而命令末参是 `B1` 这种 id ⇒ 判"产出缺失"误报 mechanical，
            #    真跑成功也被判失败。产出路径不许猜。）
            "out_path": str(n.get("out_path") or ""),
        }
        edges += [f"{d}->{nid}" for d in deps]
    for nid, n in nodes.items():
        for d in n["depends_on"]:
            if d not in nodes:
                raise ValueError(f"{nid} 依赖不存在的节点 {d}")
    # 环检测（拓扑排序必须能走完）
    indeg = {k: len(v["depends_on"]) for k, v in nodes.items()}
    order, q = [], [k for k, v in indeg.items() if v == 0]
    while q:
        cur = q.pop(0)
        order.append(cur)
        for k, v in nodes.items():
            if cur in v["depends_on"]:
                indeg[k] -= 1
                if indeg[k] == 0:
                    q.append(k)
    if len(order) != len(nodes):
        raise ValueError("DAG 有环（拓扑排序走不完）")
    canon = json.dumps({"nodes": [nodes[k] for k in sorted(nodes)], "edges": sorted(edges)},
                       ensure_ascii=False, sort_keys=True)
    return {"hash": hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16],
            "nodes": nodes, "order": order, "edges": sorted(edges),
            "max_workers": int(spec.get("max_workers", DEFAULT_WORKERS)),
            "budget": spec.get("budget") or {}}


def _state_path(dag: dict) -> Path:
    return ROOT / ".scratch" / "dag" / f"{dag['hash']}.state.json"


def _load_state(dag: dict) -> dict:
    p = _state_path(dag)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                      # noqa: BLE001
            pass
    return {"dag": dag["hash"], "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "nodes": {k: {"state": "pending", "tries": 0} for k in dag["nodes"]}}


def _save_state(dag: dict, st: dict) -> None:
    p = _state_path(dag)
    p.parent.mkdir(parents=True, exist_ok=True)
    st["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    p.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def _classify(rc: int, out: str, verify_size: int, out_path: str) -> str:
    """失败分类（关键点 3 的"差异化重试"）：`mechanical` 可重试 · `fatal` 判死。"""
    low = (out or "").lower()
    if "no such file" in low or "不存在" in out or "invalid" in low or "用法" in out:
        return "fatal"
    if rc in (124, 125) or "timeout" in low or "timed out" in low:
        return "mechanical"
    if verify_size and out_path:
        p = Path(out_path)
        if not p.is_file() or p.stat().st_size < verify_size:
            return "mechanical"          # 产出不合格 ⇒ 参数扰动重试（这里=重跑一次）
    return "mechanical" if rc != 0 else "ok"


def _run_node(n: dict, dry: bool = False) -> dict:
    t0 = time.time()
    if dry:
        return {"ok": True, "rc": 0, "ms": 0, "out": "(dry-run)", "cls": "ok"}
    cmd = [str(c) for c in n["cmd"]]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=int(n.get("timeout", 1800)),
                           cwd=str(ROOT))
        out = ((r.stdout or "") + (r.stderr or ""))[-600:]
        cls = _classify(r.returncode, out, n.get("verify_size", 0),
                        n.get("out_path") or (str(cmd[-1]) if cmd else ""))
        return {"ok": r.returncode == 0 and cls == "ok", "rc": r.returncode,
                "ms": round((time.time() - t0) * 1000), "out": out, "cls": cls}
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": 124, "ms": round((time.time() - t0) * 1000),
                "out": "timeout", "cls": "mechanical"}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "rc": -1, "ms": round((time.time() - t0) * 1000),
                "out": f"{type(exc).__name__}: {str(exc)[:160]}", "cls": "fatal"}


def run_dag(dag: dict, only: list | None = None, dry: bool = False,
            verbose: bool = True) -> dict:
    """执行（**幂等 + 断点续跑**）：done 且产出仍在的节点直接跳过。"""
    st = _load_state(dag)
    def _node_done(nid: str) -> bool:
        s = st["nodes"].get(nid, {})
        if s.get("state") != "done":
            return False
        n = dag["nodes"][nid]
        if n.get("verify_size"):
            last = n.get("out_path") or s.get("out_path") or (n["cmd"][-1] if n["cmd"] else "")
            p = Path(last)
            if not p.is_absolute():
                p = ROOT / last
            return p.is_file() and p.stat().st_size >= n["verify_size"]
        return True

    # 逐波执行（拓扑序）
    levels, done_set = [], set()
    for nid in dag["order"]:
        lv = 0
        for d in dag["nodes"][nid]["depends_on"]:
            lv = max(lv, next((i + 1 for i, L in enumerate(levels) if d in L), 0))
        while len(levels) <= lv:
            levels.append([])
        levels[lv].append(nid)
    results = {}
    for li, level in enumerate(levels):
        todo = [nid for nid in level
                if (not only or nid in only) and not _node_done(nid)
                and all(st["nodes"].get(d, {}).get("state") in ("done", "skipped")
                        for d in dag["nodes"][nid]["depends_on"])]
        skip = [nid for nid in level if nid not in todo]
        for nid in skip:
            if _node_done(nid):
                st["nodes"][nid]["state"] = "done"
                results[nid] = {"ok": True, "skipped": True}
                if verbose:
                    print(f"  ⏭ {nid} 已完成（断点续跑跳过）")
        if not todo:
            continue
        if verbose:
            print(f"  ── 第 {li} 波 · {len(todo)} 个并行（max_workers={dag['max_workers']}）")

        def _one(nid):
            n = dag["nodes"][nid]
            tries, last = 0, None
            while tries <= n["retries"]:
                tries += 1
                st["nodes"][nid].update({"state": "running", "tries": tries})
                r = _run_node(n, dry=dry)
                last = r
                if r["ok"]:
                    st["nodes"][nid]["state"] = "done"
                    st["nodes"][nid]["out_path"] = n.get("out_path") or (n["cmd"][-1] if n["cmd"] else "")
                    break
                if r["cls"] == "fatal":
                    st["nodes"][nid].update({"state": "failed", "why": "fatal（判死，不重试）",
                                             "out": r["out"][-160:]})
                    break
                st["nodes"][nid].update({"state": "retrying", "why": r["cls"],
                                         "out": r["out"][-160:]})
                time.sleep(0.4 * tries)
            if st["nodes"][nid]["state"] != "done":
                st["nodes"][nid]["state"] = "failed"
            return nid, r if last else r

        with ThreadPoolExecutor(max_workers=dag["max_workers"]) as ex:
            for nid, r in ex.map(_one, todo):
                results[nid] = r
                mark = "✔" if st["nodes"][nid]["state"] == "done" else "✘"
                if verbose:
                    print(f"  {mark} {nid} [{st['nodes'][nid]['state']}] "
                          f"{r.get('ms', 0)}ms {('· ' + r.get('cls')) if r.get('cls') != 'ok' else ''}")
        _save_state(dag, st)

    failed = [k for k, v in st["nodes"].items() if v["state"] == "failed"]
    done = [k for k, v in st["nodes"].items() if v["state"] in ("done", "skipped")]
    _log(dag, done=len(done), failed=failed)
    _save_state(dag, st)
    return {"ok": not failed, "dag": dag["hash"], "nodes": len(dag["nodes"]),
            "done": len(done), "failed": failed,
            "state_file": str(_state_path(dag)),
            "口径": "done 且产出仍在 = 跳过（幂等）；fatal 判死不重试；mechanical 有界重试"}


def _log(dag: dict, **kw) -> None:
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "dag": dag["hash"],
               "source_kind": "dagrun", **kw}
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def spec_from_actioncam(manifest: str, max_workers: int = DEFAULT_WORKERS) -> dict:
    """从动作拍子表生成 DAG：**每拍一节点**（互不依赖 ⇒ 同波并行）+ 总装节点（依赖全部拍）。

    节点边界（关键点 10：能力边界显式化）写在每个节点上，执行器据此知道"能做/需降级/不能做"。
    """
    mp = ROOT / manifest
    m = json.loads(mp.read_text(encoding="utf-8"))
    beats = m.get("beats") or []
    work = m.get("work_dir")
    segs_dir = f"{work}/segs"
    nodes = []
    for b in beats:
        out = f"{segs_dir}/{b['id']}.mp4"
        nodes.append({
            "id": f"seg-{b['id']}",
            "cmd": ["python", "tools/actioncam.py", "seg", manifest, "--beat", b["id"]],
            "depends_on": [],
            "verify_size": 20000,
            "out_path": out,
            "retries": 1,
            "boundary": {"can": f"渲染单拍（{b.get('move')}/{b.get('angle')}）",
                         "degrade": "渲染失败可降档（cinema→fhd→hd）后重试",
                         "cannot": "源图缺失时不能凭空出段（先 gen）"},
        })
    nodes.append({
        "id": "build",
        "cmd": ["python", "tools/actioncam.py", "build", manifest],
        "depends_on": [f"seg-{b['id']}" for b in beats],
        "verify_size": 500000,
        "out_path": f"{m.get('out_dir')}/{m.get('output')}",
        "retries": 0,
        "boundary": {"can": "总装（拼段+调色+音效床）", "degrade": "无",
                     "cannot": "缺段时不能装（先跑完 seg）"},
    })
    return {"nodes": nodes, "max_workers": max_workers,
            "budget": m.get("budget") or {}}


def spec_from_filmkit(manifest: str, max_workers: int = DEFAULT_WORKERS) -> dict:
    """从影视线清单生成 DAG：**每场一节点**（互不依赖 ⇒ 同波并行）+ 总装节点（依赖全部场）。

    🔴 产出路径**问 filmkit 自己**（`seg_path()`），不许猜（2026-09-27 第二次踩：
    我按 `work_dir/segs/<shot>.mp4` 猜，而它写在 `work_dir/<shot>.mp4` ⇒ 渲染成功被判失败）。
    """
    mp = ROOT / manifest
    m = json.loads(mp.read_text(encoding="utf-8"))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("filmkit", ROOT / "tools" / "filmkit.py")
        fk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fk)
        mm = fk.load(mp)

        def _seg_of(scene_id: str) -> str:
            sc = next(x for x in mm["scenes"] if x["id"] == scene_id)
            return fk.seg_path(mm, sc["shots"][0]["id"]).relative_to(ROOT).as_posix()
    except Exception:                                          # noqa: BLE001
        def _seg_of(scene_id: str) -> str:                     # 兜底：按 filmkit 的实际规则拼
            return f"{m.get('work_dir')}/{scene_id}_s1.mp4"
    scenes = m.get("scenes") or []
    nodes = []
    for sc in scenes:
        nodes.append({
            "id": f"seg-{sc['id']}",
            "cmd": ["python", "tools/filmkit.py", "seg", manifest, "--scene", sc["id"]],
            "depends_on": [],
            "verify_size": 20000,
            "out_path": _seg_of(sc["id"]),
            "retries": 1,
            "boundary": {"can": f"渲染本场 {len(sc.get('shots') or [])} 镜",
                         "degrade": "渲染慢可降档（cinema→fhd→hd）",
                         "cannot": "缺图时不能凭空出段（先 gen）"},
        })
    nodes.append({
        "id": "build",
        "cmd": ["python", "tools/filmkit.py", "build", manifest],
        "depends_on": [f"seg-{sc['id']}" for sc in scenes],
        "verify_size": 1000000,
        "out_path": f"{m.get('out_dir')}/{m.get('output')}",
        "retries": 0,
        "boundary": {"can": "总装（拼段+调色+指纹）", "degrade": "无", "cannot": "缺段时不能装"},
    })
    return {"nodes": nodes, "max_workers": max_workers, "budget": m.get("budget") or {}}


def main(argv: list) -> int:
    import sys
    if len(argv) < 2:
        print(__doc__); return 2
    cmd = argv[1]
    if cmd in ("compile", "run", "status") and len(argv) >= 3:
        name = argv[2].lower()
        if name.endswith(".json") and "manifest-actioncam" in name:
            spec = spec_from_actioncam(argv[2])
        elif name.endswith(".json") and "manifest" in name and "dag" not in name:
            spec = spec_from_filmkit(argv[2])          # 影视线清单（scenes）
        else:
            spec = json.loads((ROOT / argv[2]).read_text(encoding="utf-8"))
        dag = compile_spec(spec)
        if cmd == "compile":
            print(json.dumps({"dag": dag["hash"], "nodes": len(dag["nodes"]),
                              "edges": len(dag["edges"]), "order": dag["order"][:6],
                              "edges_sample": dag["edges"][:4]}, ensure_ascii=False, indent=1))
            return 0
        if cmd == "status":
            print(json.dumps(status(dag), ensure_ascii=False, indent=1)); return 0
        only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
        r = run_dag(dag, only=only, dry="--dry" in argv)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    print(__doc__); return 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
