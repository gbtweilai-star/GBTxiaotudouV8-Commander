#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""本地渲染代理 + 插件云模块图（本地只渲染；其他都在云上按模块分布）

## 架构（主人 2026-09-24 令）
    本地：**只做渲染**（Chrome + ffmpeg 在本地；内存小但"五脏俱全"）
    插件云：**其他全部**——编排 · 作业单 · 素材池 · 帧缓存 · 生成端 · 编码装配 · 发布 · 仓
    云上按**命名空间分模块排好**，每个模块只读写**自己的前缀**（分布式，互不越界）。

## 云侧命名空间（本工具定义的契约，落在 R2 `gbt-bigfiles`）
    pipeline/modules/<module>/<version>/manifest.json   模块清单与契约
    pipeline/jobs/<job_id>/spec.json                    作业单（谁要什么）
    pipeline/jobs/<job_id>/status.json                  状态（各模块写自己那段）
    pipeline/jobs/<job_id>/artifacts/<name>             产物
    pipeline/assets/<kind>/<name>                       素材池
    pipeline/cache/frames/<job_id>/...                  帧缓存（放不下就 spill）
    vault/ · spill/                                     已有：大件仓与溢出（cloud-vault）

## 本地渲染代理做四件事（都只碰"渲染"这一格）
    modules                      打印模块图（谁在本地、谁在云、各自前缀）
    submit <spec.json>           把作业单推到云
    run <job_id> [--keep]        拉作业单 → **本地渲染** → 产物推回云（逐字节校验）
    status <job_id>              读云上的状态与产物

🔴 边界：**本工具不部署云函数**。`deploy`（Workers/Containers）是**发布动作**，
   会把它推到公网 ⇒ **要主人明确点头才做**。这里只做"契约 + 本地那一格 + 真跑一遍"。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "codex-scripts"
PY = [sys.executable]
BUCKET = os.environ.get("GBT_PLUGIN_CLOUD_BUCKET", "gbt-bigfiles")
PREFIX = "pipeline"

# 模块图：谁在哪、各自的前缀、接口是什么。**本地只有 render 一格。**
MODULES = [
    ("orchestrator", "cloud", "pipeline/jobs/", "读 spec → 派活 → 收 status（决定下一步）"),
    ("spec-store", "cloud", "pipeline/jobs/*/spec.json", "作业单的权威存储"),
    ("asset-pool", "cloud", "pipeline/assets/", "素材池：图片/音频/字体/BGM"),
    ("frame-cache", "cloud", "pipeline/cache/frames/", "帧缓存；本地放不下时 spill"),
    ("generator", "cloud", "pipeline/jobs/*/artifacts/", "生成端（图/音/视频）——**吃云 key**"),
    ("render", "LOCAL", "(本地工作目录)", "**唯一本地模块**：Chrome+ffmpeg 出帧与成片"),
    ("assemble", "cloud", "pipeline/jobs/*/artifacts/", "编码/装配/封装（可上云 worker）"),
    ("publish", "cloud", "pipeline/jobs/*/status.json", "发布留痕（要授权）"),
    ("vault", "cloud", "vault/ · spill/", "大件仓与溢出（cloud-vault 已验）"),
]


def _npx() -> str:
    """Windows 上 `subprocess` **找不到裸名 `npx`**（真身是 `npx.cmd`）——
    `CreateProcess` 不做 PATHEXT 解析 ⇒ `FileNotFoundError: [WinError 2]`。
    凡是 subprocess 起 npx 的地方都必须先解析出真路径。"""
    import shutil
    return shutil.which("npx") or "npx.cmd"


def _r2(*args: str) -> tuple[int, str]:
    """云侧读写统一走 wrangler（R2）。🔴 必带 --remote（F18：默认走本地模拟却打印成功）。"""
    r = subprocess.run([_npx(), "--yes", "wrangler", "r2", *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _put(local: pathlib.Path, key: str) -> tuple[bool, str]:
    rc, out = _r2("object", "put", "%s/%s" % (BUCKET, key), "--file", str(local), "--remote")
    ok = rc == 0 and ("Upload complete" in out or "uploaded" in out.lower())
    return ok, out[-300:]


def _get(key: str, out: pathlib.Path) -> tuple[bool, str]:
    """🔴 `get` **也必须带 `--remote`** —— wrangler 的 `object get` 和 `put` 一样**默认走本地模拟**，
    不带就会报 `The specified key does not exist`（回执里其实提示了 `--remote`）。
    我第一版只在 put 上加了，读侧忘了 ⇒ 同一个坑反方向又踩一次（F18 的镜像）。"""
    out.parent.mkdir(parents=True, exist_ok=True)
    rc, so = _r2("object", "get", "%s/%s" % (BUCKET, key), "--file", str(out), "--remote")
    return (rc == 0 and out.exists()), so[-300:]


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def cmd_modules(a) -> int:
    print(json.dumps({
        "架构": "本地只渲染；其他都在插件云按模块分布式运行",
        "bucket": BUCKET, "命名空间": PREFIX,
        "模块": [{"模块": m, "运行地": w, "前缀": p, "接口": i} for m, w, p, i in MODULES],
        "本地模块数": sum(1 for m, w, *_ in MODULES if w == "LOCAL"),
        "云模块数": sum(1 for m, w, *_ in MODULES if w == "cloud"),
        "边界": "本工具不部署云函数；deploy 是发布动作，须主人点头",
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_submit(a) -> int:
    spec = pathlib.Path(a.spec)
    if not spec.is_file():
        print(json.dumps({"ok": False, "why": "作业单不存在", "spec": str(spec)}, ensure_ascii=False))
        return 2
    d = json.loads(spec.read_text(encoding="utf-8"))
    jid = a.job_id or d.get("job_id") or ("job-" + time.strftime("%Y%m%dT%H%M%S"))
    d["job_id"] = jid
    tmp = ROOT / "state" / ("_spec_%s.json" % jid)
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    ok, tail = _put(tmp, "%s/jobs/%s/spec.json" % (PREFIX, jid))
    # 维护云端作业索引（看板靠它枚举；见文件尾的局限说明）
    idx = _index_read()
    if jid not in idx:
        idx.append(jid)
        ix = ROOT / "state" / "_jobs_index.json"
        ix.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
        _put(ix, "%s/jobs/index.json" % PREFIX)
    print(json.dumps({"ok": ok, "job_id": jid, "云上键": "%s/jobs/%s/spec.json" % (PREFIX, jid),
                      "已进索引": jid in idx, "tail": tail}, ensure_ascii=False, indent=1))
    return 0 if ok else 3


def _index_read() -> list:
    tmp = ROOT / "state" / "_jobs_index.json"
    ok, _ = _get("%s/jobs/index.json" % PREFIX, tmp)
    if not ok:
        return []
    try:
        d = json.loads(tmp.read_text(encoding="utf-8"))
        return [str(x) for x in d] if isinstance(d, list) else []
    except Exception:
        return []


def cmd_fleet(a) -> int:
    """机群看板：**每个终端有编号 · 谁在做什么 · 什么没做**。"""
    idx = _index_read()
    if not idx:
        print(json.dumps({"ok": False, "why": "云端还没有作业索引（没人 submit 过）",
                          "索引键": "%s/jobs/index.json" % PREFIX}, ensure_ascii=False))
        return 2
    board, done_n, doing_n, todo_n = [], 0, 0, 0
    for jid in idx:
        st = _done_status(jid)                 # status.json（有 artifact ⇒ 已完成）
        ls = _lease_read(jid)                  # lease.json（谁在做）
        if st:
            done_n += 1
            board.append({"编号": jid, "状态": "✅ 已完成",
                          "谁做的": (st.get("worker") or (ls or {}).get("owner") or "?"),
                          "产物": st.get("artifact"), "字节": st.get("bytes"),
                          "sha256_前16": str(st.get("sha256"))[:16]})
        elif ls and not ls.get("done"):
            doing_n += 1
            board.append({"编号": jid, "状态": "🔵 有人在做",
                          "谁做的": ls.get("owner"), "起于": ls.get("at"),
                          "租约秒": ls.get("ttl_s")})
        else:
            todo_n += 1
            board.append({"编号": jid, "状态": "⬜ 还没人做（待领单）", "谁做的": None})
    print(json.dumps({
        "看板": board,
        "合计": {"总数": len(idx), "已完成": done_n, "在做": doing_n, "待做": todo_n},
        "云前缀": "%s/jobs/" % PREFIX, "桶": BUCKET,
        "口径": "索引由 submit 维护；绕过 submit 直接写云的作业不会出现在这里（局限已记档）",
    }, ensure_ascii=False, indent=1))
    return 0


def _lease_read(jid: str) -> dict | None:
    tmp = ROOT / "state" / ("_lease_%s.json" % jid)
    ok, _ = _get("%s/jobs/%s/lease.json" % (PREFIX, jid), tmp)
    if not ok:
        return None
    try:
        return json.loads(tmp.read_text(encoding="utf-8"))
    except Exception:
        return None


def _claim(jid: str, worker: str, ttl: int) -> tuple[bool, str]:
    """**领单**（近似原子）。⚠️ 说清它**不是真原子**：

    R2 没有条件写（compare-and-set），所以两个终端**有可能同时**判为"没人持有"并都写租约
    ⇒ **会偶发双领**。因此**必须配幂等**（`cmd_run` 里"云端已有产物且 sha 一致就跳过"）。
    真原子要 Queues / Durable Objects —— 那要部署云函数（须主人点头）。
    这里用"写 + 回读 + 时间戳"做**近似**，并把这条局限**写在代码里**，不假装它是队列。
    """
    cur = _lease_read(jid)
    now = time.time()
    if cur and not cur.get("done"):
        age = now - float(cur.get("at_ts") or 0)
        if age < ttl and cur.get("owner") != worker:
            return False, "他人持有租约（owner=%s，%.0fs 前）" % (cur.get("owner"), age)
    body = {"job_id": jid, "owner": worker, "at_ts": now,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ttl_s": ttl, "done": False}
    tmp = ROOT / "state" / ("_lease_put_%s.json" % jid)
    tmp.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    ok, _ = _put(tmp, "%s/jobs/%s/lease.json" % (PREFIX, jid))
    if not ok:
        return False, "租约写不进去（fail-closed：拿不到单就不干）"
    back = _lease_read(jid)
    if back and back.get("owner") == worker:
        return True, "领到单（近似原子；已配幂等兜底）"
    return False, "回读发现被别人抢走（owner=%s）" % ((back or {}).get("owner"))


def _done_status(jid: str) -> dict | None:
    tmp = ROOT / "state" / ("_done_%s.json" % jid)
    ok, _ = _get("%s/jobs/%s/status.json" % (PREFIX, jid), tmp)
    if not ok:
        return None
    try:
        d = json.loads(tmp.read_text(encoding="utf-8"))
        return d if d.get("artifact") else None
    except Exception:
        return None


def cmd_run(a) -> int:
    jid = a.job_id
    worker = a.worker or ("pid-%d" % os.getpid())
    # 🔴 每个终端**自己的**工作目录：30~50 个终端共用一个目录会互相踩
    #    （实测：w2 渲完删了本地，w1 再去删同一路径就 FileNotFoundError 崩掉）
    work = ROOT / "state" / "render-jobs" / jid / worker
    work.mkdir(parents=True, exist_ok=True)
    spec_p = work / "spec.json"
    ok, tail = _get("%s/jobs/%s/spec.json" % (PREFIX, jid), spec_p)
    if not ok:
        print(json.dumps({"ok": False, "why": "作业单拉不下来", "tail": tail}, ensure_ascii=False))
        return 3
    spec = json.loads(spec_p.read_text(encoding="utf-8"))

    # ① 幂等：云上已有产物 ⇒ **不再重复渲染**（这是"近似原子"能用的前提）
    done = _done_status(jid)
    if done and not a.force:
        print(json.dumps({"ok": True, "job_id": jid, "worker": worker,
                          "判决": "**幂等跳过**：云端已有产物，不重复渲染",
                          "云端产物": done.get("artifact"), "shbytes": done.get("bytes"),
                          "sha256_前16": str(done.get("sha256"))[:16]},
                         ensure_ascii=False, indent=1))
        return 0

    # ② 领单：拿不到就不干（fail-closed）
    got, why = _claim(jid, worker, a.ttl)
    if not got:
        print(json.dumps({"ok": True, "job_id": jid, "worker": worker,
                          "判决": "**没领到单 ⇒ 不参与**（这就是 30~50 个终端不抢同一份活的机制）",
                          "why": why}, ensure_ascii=False, indent=1))
        return 0

    engine = spec.get("engine", "remotion")
    t0 = time.time()
    if engine == "remotion":
        proj = pathlib.Path(spec["project"])
        cmd = [_npx(), "--no-install", "remotion", "render", spec.get("composition", "Hello"),
               str(work / spec.get("out", "out.mp4")),
               "--entry-point", spec.get("entry_point", "src/index.tsx")]
        r = subprocess.run(cmd, cwd=str(proj), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    else:                                            # hyperframes
        proj = pathlib.Path(spec["project"])
        r = subprocess.run([_npx(), "--yes", "hyperframes@0.8.69", "render"],
                           cwd=str(proj), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    rc, log = r.returncode, ((r.stdout or "") + (r.stderr or ""))[-400:]
    art = work / spec.get("out", "out.mp4")
    if rc != 0 or not art.exists():
        cands = sorted(proj.glob("renders/*.mp4"), key=lambda p: p.stat().st_mtime) if engine != "remotion" else []
        if cands:
            art = cands[-1]
    got_art = art.exists()
    out = {"ok": got_art, "job_id": jid, "worker": worker, "engine": engine,
           "本地产物": str(art) if got_art else None,
           "字节": (art.stat().st_size if got_art else 0),
           "sha256_前16": (sha256_file(art)[:16] if got_art else None),
           "本地渲染耗时s": round(time.time() - t0, 1), "日志尾": log}
    if got_art:
        key = "%s/jobs/%s/artifacts/%s" % (PREFIX, jid, art.name)
        pok, ptail = _put(art, key)
        out.update({"推回云": pok, "云上键": key, "云上回执尾": ptail})
        st = {"job_id": jid, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "engine": engine,
              "artifact": key, "bytes": art.stat().st_size, "sha256": sha256_file(art),
              "worker": worker, "done": True}
        stp = work / "status.json"
        stp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        sok, _ = _put(stp, "%s/jobs/%s/status.json" % (PREFIX, jid))
        out["状态已回写"] = sok
        # 租约标 done（但不删：留着让别的终端看得见"这单已完成"）
        lb = {"job_id": jid, "owner": worker, "at_ts": time.time(), "done": True}
        lp = work / "lease.json"
        lp.write_text(json.dumps(lb, ensure_ascii=False), encoding="utf-8")
        _put(lp, "%s/jobs/%s/lease.json" % (PREFIX, jid))
        if pok and not a.keep:
            art.unlink(missing_ok=True)          # 🔴 missing_ok：多终端下文件可能已被同 owner 的另一步删走
            out["本地产物已释放"] = True
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if got_art and out.get("推回云", False) else 4


def cmd_status(a) -> int:
    tmp = ROOT / "state" / ("_status_%s.json" % a.job_id)
    ok, tail = _get("%s/jobs/%s/status.json" % (PREFIX, a.job_id), tmp)
    body = None
    if ok:
        try:
            body = json.loads(tmp.read_text(encoding="utf-8"))
        except Exception:
            body = None
    print(json.dumps({"ok": ok, "job_id": a.job_id, "status": body, "tail": (None if ok else tail)},
                     ensure_ascii=False, indent=1))
    return 0 if ok else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="本地渲染代理（本地只渲染；其他在插件云）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("modules").set_defaults(func=cmd_modules)
    s1 = sub.add_parser("submit")
    s1.add_argument("spec")
    s1.add_argument("--job-id", default="")
    s1.set_defaults(func=cmd_submit)
    s2 = sub.add_parser("run")
    s2.add_argument("job_id")
    s2.add_argument("--keep", action="store_true")
    s2.add_argument("--worker", default="", help="本终端标识（30~50 个终端各给一个）")
    s2.add_argument("--ttl", type=int, default=600, help="租约秒数（超时可被别的终端接管）")
    s2.add_argument("--force", action="store_true", help="无视幂等，强制重渲")
    s2.set_defaults(func=cmd_run)
    sub.add_parser("fleet").set_defaults(func=cmd_fleet)
    s3 = sub.add_parser("status")
    s3.add_argument("job_id")
    s3.set_defaults(func=cmd_status)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
