#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模块 07 · assemble（装配）—— 云上的帧 → 编码 → 产物回云，逐字节校验

## 它在链条里的位置
    04 frame-cache（帧进云）→ 06 render（本地出帧/出片）→ **07 assemble（编码装配）** → 08 publish

主人要的"自动化长视频"卡在这一格：帧在云上，得有人把它们**编成成片再放回云**。

## 边界（说清楚，不含糊）
主人令是「**本地只渲染，其他都在插件云分布式运行**」。但**云函数（Workers/Containers）是发布动作，
须主人点头**，我还没得到那个点头。所以现在的诚实形态是：

    **数据面在云**（帧从云取、产物回云、逐字节校验）· **执行面在本地触手槽**（`state/tentacle-slots/T0k`）
    ⇒ 面板上 07 落点仍写 `cloud`，但**执行地如实标 LOCAL-触手**，等主人点头再换成云 worker。

不把"数据在云"念成"跑在云上"。

## 工序
    run <job_id> [--fps N] [--apply]
      ① 读云上该作业的帧清单（没有帧 ⇒ **拒**，fail-closed）
      ② 帧按名字**排序**下载到触手隔离位（顺序确定，不随机）
      ③ ffmpeg 编码成 MP4
      ④ 产物推回云 `pipeline/jobs/<jid>/artifacts/<name>` 并**拉回逐字节校验**
      ⑤ 写 `status.json`（带 worker = 触手槽）
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
DP_PATH = ROOT / "tools" / "codex-scripts" / "deploy-panel.py"
FC_PATH = ROOT / "tools" / "codex-scripts" / "frame-cache.py"
PREFIX = "pipeline"
_DP = _FC = None


def _load(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _dp():
    global _DP
    if _DP is None:
        _DP = _load(DP_PATH, "_dp_mod4")
    return _DP


def _fc():
    """复用 frame-cache 的索引读写 —— **只有一份实现，不各写一套**。"""
    global _FC
    if _FC is None:
        _FC = _load(FC_PATH, "_fc_mod")
    return _FC


def _ra():
    return _dp()._load_ra()


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def _ffprobe(p: pathlib.Path) -> dict:
    """🔴 必须带 `-count_frames`：不带时 `nb_frames` 取自容器元数据，
    拿到的是"写进去几个"而不是"真能解出几个" —— 我要的是**真解出来的帧数**。"""
    r = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-count_frames",
                        "-select_streams", "v:0",
                        "-show_entries", "stream=nb_frames,nb_read_frames,width,height,"
                                         "r_frame_rate,duration",
                        "-of", "json", str(p)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    try:
        return json.loads(r.stdout)["streams"][0]
    except Exception:
        return {}


def assemble(jid: str, fps: int, work: pathlib.Path, slot: str, apply_upload: bool = True) -> dict:
    """核心工序（自检与真跑走**同一条**代码路径）。"""
    ra = _ra()
    idx = _fc()._jidx(ra, jid)
    if not idx:
        return {"ok": False, "why": "**云上该作业没有帧 ⇒ 拒**（fail-closed，不装配空链）",
                "job_id": jid, "查的键": "%s/%s/index.json" % ("pipeline/cache/frames", jid)}
    names = sorted(idx)                                  # 顺序确定：按名字排，不随机
    exts = {pathlib.Path(n).suffix.lower() for n in names}
    if len(exts) != 1:
        return {"ok": False, "why": "帧扩展名不统一 ⇒ 拒（不猜编码顺序）", "扩展名": sorted(exts)}

    work.mkdir(parents=True, exist_ok=True)
    for old in work.glob("f*%s" % list(exts)[0]):
        old.unlink(missing_ok=True)
    ext = list(exts)[0]
    got = []
    for i, n in enumerate(names, 1):
        dst = work / ("f%05d%s" % (i, ext))
        ok, tail = ra._get("%s/%s/%s" % ("pipeline/cache/frames", jid, n), dst)
        if not ok:
            return {"ok": False, "why": "帧拉不下来", "帧": n, "tail": tail}
        got.append(dst)

    out = work / "out.mp4"
 # F34：这里**必须给 image2 的 `%05d` 模式**，给首帧文件名只会编出**1 帧**。
    #    我第一版就是给了 `f00001.png` ⇒ 5 帧的输入编成 1 帧的成片，而自检**居然绿了**
    #    （因为判据只查了"往返 sha 一致"，1 帧的片子同样满足）。判据太弱 = 假绿。
    pattern = str(work / ("f%05d" + ext))
    cmd = [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-framerate", str(fps),
           "-i", pattern, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        return {"ok": False, "why": "**编码失败 ⇒ fail-closed，不写状态**",
                "rc": r.returncode, "日志尾": ((r.stdout or "") + (r.stderr or ""))[-300:]}
    probe = _ffprobe(out)
    try:
        n_read = int(probe.get("nb_read_frames") or 0)
    except Exception:
        n_read = 0
    if n_read != len(got):                      # ← 判据必须**咬住帧数**，不能只看"有产物"
        return {"ok": False, "why": "**帧数不符 ⇒ 拒**（说明编码吞了帧）",
                "输入帧数": len(got), "成片真解出帧数": n_read, "探针": probe,
                "命令": " ".join(cmd[:8]) + " …"}
    sha, nbytes = sha256_file(out), out.stat().st_size
    res = {"ok": True, "job_id": jid, "帧数": len(got), "成片真解出帧数": n_read, "fps": fps,
           "产物": out.name, "bytes": nbytes, "sha256": sha,
           "探针": {k: probe.get(k) for k in ("nb_frames", "nb_read_frames", "width", "height",
                                            "r_frame_rate", "duration")},
           "执行地": "LOCAL-触手（云函数未授权）", "数据面": "CLOUD"}
    if not apply_upload:
        return res
    key = "%s/jobs/%s/artifacts/%s" % (PREFIX, jid, out.name)
    pok, ptail = ra._put(out, key)
    back = work / "_back.mp4"
    gok, gtail = ra._get(key, back)
    same = gok and sha256_file(back) == sha
    res.update({"推回云": pok, "云上键": key,
                "往返": "✅ 拉回逐字节一致" if same else "✗ **往返不符**",
                "tail": None if (pok and same) else (ptail or gtail)})
    if not (pok and same):
        return {**res, "ok": False}
    st = {"job_id": jid, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "engine": "assemble",
          "artifact": key, "bytes": nbytes, "sha256": sha, "worker": slot,
          "帧数": len(got), "fps": fps, "done": True,
          "执行地": "LOCAL-触手（数据面在云）"}
    sp = work / "status.json"
    sp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    sok, _ = ra._put(sp, "%s/jobs/%s/status.json" % (PREFIX, jid))
    res["状态已回写"] = sok
    back.unlink(missing_ok=True)
    return res


def cmd_run(a) -> int:
    n = _dp()._tentacles()[0]
    if not n:
        print(json.dumps({"ok": False, "why": "触手根数未声明 ⇒ 不装配（fail-closed）"},
                         ensure_ascii=False))
        return 2
    slot = a.slot or "T01"
    if slot not in ["T%02d" % (i + 1) for i in range(n)]:
        print(json.dumps({"ok": False, "why": "触手槽不在编制内（不许临时造槽）",
                          "编制": ["T%02d" % (i + 1) for i in range(n)]}, ensure_ascii=False))
        return 2
    work = ROOT / "state" / "tentacle-slots" / slot / "assemble" / a.job_id
    res = assemble(a.job_id, a.fps, work, slot, apply_upload=a.apply)
    res["触手槽"] = slot
    res["隔离位"] = str(work.relative_to(ROOT))
    res["模式"] = "真跑（推回云）" if a.apply else "彩排（只编码，不推云、不写状态）"
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res.get("ok") else 5


def cmd_selftest(a) -> int:
    """真身自检：**真 ffmpeg + 真帧**，1 正控 + 3 负控。跑在本地替身云上。"""
    dp = _dp()
    fc = _fc()
    keep = dp.LOCAL_CLOUD
    lines, bad = [], 0

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    with tempfile.TemporaryDirectory() as td:
        tdp = pathlib.Path(td)
        dp.LOCAL_CLOUD = str(tdp / "cloud")
        src = tdp / "src"
        src.mkdir()
        # 用真 ffmpeg 造 5 张真帧（不是随手写的假二进制）
        r = subprocess.run([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                            "-i", "testsrc=size=64x64:rate=5", "-frames:v", "5",
                            "-y", str(src / "s%05d.png")], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        frames = sorted(src.glob("s*.png"))
        ck("预备·真 ffmpeg 造出 5 张真帧", r.returncode == 0 and len(frames) == 5,
           "rc=%d · 帧数=%d" % (r.returncode, len(frames)))

        ra = _ra()
        for f in frames:
            b = tdp / f.name
            shutil.copyfile(f, b)
            ok, _ = ra._put(b, "pipeline/cache/frames/job-enc/%s" % f.name)
            if not ok:
                break
        idx = {f.name: {"bytes": f.stat().st_size, "sha256": sha256_file(f),
                        "at": time.strftime("%Y-%m-%dT%H:%M:%S")} for f in frames}
        fc._jidx_put(ra, "job-enc", idx)

        res = assemble("job-enc", 5, tdp / "work", "T01", apply_upload=True)
        ck("正控·云上帧 ⇒ 编码 ⇒ 产物回云且往返一致",
           bool(res.get("ok")) and res.get("往返", "").startswith("✅"),
           "帧数=%s · %s 字节 · 探针 %s · %s"
           % (res.get("帧数"), res.get("bytes"), res.get("探针"), res.get("往返")))
 # F34 回归判据：**帧数必须对得上**（只查"有产物/sha 一致"会放过吞帧的假绿）
        ck("正控②·成片真解出帧数 == 输入帧数（F34 回归）",
           res.get("成片真解出帧数") == 5 and res.get("帧数") == 5,
           "输入 %s 帧 ⇒ 真解出 %s 帧（期望 5）" % (res.get("帧数"), res.get("成片真解出帧数")))

        # 负控①：作业没有帧 ⇒ 拒
        res2 = assemble("job-没有帧", 5, tdp / "w2", "T01", apply_upload=False)
        ck("负控①·没有帧 ⇒ 拒（不装配空链）", res2.get("ok") is False and "没有帧" in res2.get("why", ""),
           res2.get("why", "")[:70])

        # 负控②：帧是坏文件 ⇒ 编码失败必须 fail-closed，不写状态
        fc._jidx_put(ra, "job-bad", {"f00001.png": {"bytes": 7, "sha256": "x"}})
        bad_png = tdp / "f00001.png"
        bad_png.write_bytes(b"NOTPNG!")
        ra._put(bad_png, "pipeline/cache/frames/job-bad/f00001.png")
        res3 = assemble("job-bad", 5, tdp / "w3", "T01", apply_upload=False)
        ck("负控②·坏帧 ⇒ 编码失败 fail-closed", res3.get("ok") is False and "编码失败" in res3.get("why", ""),
           "rc=%s · %s" % (res3.get("rc"), str(res3.get("why"))[:50]))

        # 负控③：扩展名混用 ⇒ 拒
        fc._jidx_put(ra, "job-mix", {"a.png": {"sha256": "x"}, "b.jpg": {"sha256": "y"}})
        res4 = assemble("job-mix", 5, tdp / "w4", "T01", apply_upload=False)
        ck("负控③·帧扩展名不统一 ⇒ 拒", res4.get("ok") is False and "不统一" in res4.get("why", ""),
           res4.get("why", "")[:70])

    dp.LOCAL_CLOUD = keep
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines,
                      "口径": "真 ffmpeg + 真帧 + 本地替身云；负控证明**坏输入/空链拦得住**"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="模块 07 · assemble（云帧 → 编码 → 产物回云）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("job_id")
    r.add_argument("--fps", type=int, default=30)
    r.add_argument("--slot", default="", help="触手槽（须在编制内）")
    r.add_argument("--apply", action="store_true", help="真跑：推回云并写状态")
    r.set_defaults(func=cmd_run)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
