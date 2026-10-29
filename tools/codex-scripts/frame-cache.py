#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模块 04 · frame-cache（帧缓存）—— 本地放不下的帧进云，取回逐字节可验

## 它为什么必须存在（主人要的"长视频自动化"卡在这）
`Remotion 默认并发 6×` 是**内存放大器**；本机物理 7.39 GB、页面文件峰值 **12,727 MB**。
长视频的帧在本地**装不下** ⇒ 帧必须能**进云、按作业分桶、取回可验**，本地只留渲染这一格。

## 云侧键
    pipeline/cache/frames/<job_id>/<name>        帧本体（按作业分桶，互不越界）
    pipeline/cache/frames/<job_id>/index.json    该作业的帧清单
    pipeline/cache/frames/index.json             作业总表

## 分布式正确性闸（这是"永远不会出错"的实处）
多终端共用缓存时，**同名不同内容**是最危险的形态：别的终端会读到错的帧而不报错。
所以 `put` 撞名时：
  · 同名**同 sha** ⇒ **幂等跳过**（rc=0，不重写）
  · 同名**不同 sha** ⇒ **拒**（rc=7）—— 要么换名，要么显式 `--force`（留痕）。
**绝不静默覆盖别人的帧。**

## 老实说的局限
索引是**读-改-写**（R2 没有 compare-and-set）⇒ 并发 put 可能丢一条索引行（帧本体不丢）。
真原子要 Queues/DO —— 发布动作，须主人点头。本工具**不部署云函数**。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
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
FRAMES = "pipeline/cache/frames"
_DP = None


def _dp():
    global _DP
    if _DP is None:
        spec = importlib.util.spec_from_file_location("_dp_mod2", DP_PATH)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _DP = m
    return _DP


def _cloud():
    dp = _dp()
    return dp, dp._load_ra()


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _bad(s: str, what: str) -> str | None:
    if not s or "/" in s or "\\" in s or s.startswith("."):
        return "%s 不合法（不许带路径分隔符 / 不许以点开头）：%r" % (what, s)
    return None


def _jidx(ra, jid: str) -> dict:
    tmp = ROOT / "state" / ("_frames_%s.json" % jid)
    ok, _ = ra._get("%s/%s/index.json" % (FRAMES, jid), tmp)
    if not ok:
        return {}
    try:
        d = json.loads(tmp.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _jidx_put(ra, jid: str, idx: dict) -> bool:
    tmp = ROOT / "state" / ("_frames_put_%s.json" % jid)
    tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    ok, _ = ra._put(tmp, "%s/%s/index.json" % (FRAMES, jid))
    return ok


def _jobs(ra) -> dict:
    tmp = ROOT / "state" / "_frames_jobs.json"
    ok, _ = ra._get("%s/index.json" % FRAMES, tmp)
    if not ok:
        return {}
    try:
        d = json.loads(tmp.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def cmd_put(a) -> int:
    src = pathlib.Path(a.frame)
    if not src.is_file():
        print(json.dumps({"ok": False, "why": "帧文件不存在", "path": str(src)}, ensure_ascii=False))
        return 2
    for val, what in ((a.job_id, "job_id"), (a.name or src.name, "name")):
        bad = _bad(val, what)
        if bad:
            print(json.dumps({"ok": False, "why": bad}, ensure_ascii=False))
            return 2
    name = a.name or src.name
    _, ra = _cloud()
    sha, nbytes = sha256_file(src), src.stat().st_size
    idx = _jidx(ra, a.job_id)
    old = idx.get(name)

 # 撞名闸：同 sha 幂等跳过 / 不同 sha 拒（绝不静默覆盖）
    if old and old.get("sha256") == sha:
        print(json.dumps({"ok": True, "判决": "**幂等跳过**：该作业已有同名同内容帧，不重传",
                          "job_id": a.job_id, "name": name, "sha256_前16": sha[:16]},
                         ensure_ascii=False, indent=1))
        return 0
    if old and not a.force:
        print(json.dumps({"ok": False, "拒单": "**撞名不同内容**：绝不静默覆盖别人的帧",
                          "job_id": a.job_id, "name": name,
                          "已有": {"bytes": old.get("bytes"), "sha256_前16": str(old.get("sha256"))[:16]},
                          "本次": {"bytes": nbytes, "sha256_前16": sha[:16]},
                          "两条路": "换个 name，或显式 --force（会留痕覆盖）"},
                         ensure_ascii=False, indent=1))
        return 7

    key = "%s/%s/%s" % (FRAMES, a.job_id, name)
    ok, tail = ra._put(src, key)
    if not ok:
        print(json.dumps({"ok": False, "why": "上传失败", "键": key, "tail": tail}, ensure_ascii=False))
        return 3
    back = ROOT / "state" / "_frame_verify" / name
    back.parent.mkdir(parents=True, exist_ok=True)
    gok, gtail = ra._get(key, back)
    if not gok or sha256_file(back) != sha:
        print(json.dumps({"ok": False, "why": "**往返不符** ⇒ 不写索引（fail-closed）",
                          "键": key, "tail": gtail}, ensure_ascii=False))
        return 5
    back.unlink(missing_ok=True)

    idx[name] = {"bytes": nbytes, "sha256": sha, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "被覆盖": bool(old and a.force)}
    iok = _jidx_put(ra, a.job_id, idx)
    j = _jobs(ra)
    j[a.job_id] = {"帧数": len(idx), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    jt = ROOT / "state" / "_frames_jobs_put.json"
    jt.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    jok, _ = ra._put(jt, "%s/index.json" % FRAMES)
    print(json.dumps({"ok": iok, "键": key, "job_id": a.job_id, "name": name, "bytes": nbytes,
                      "sha256_前16": sha[:16], "往返": "✅ 拉回逐字节一致",
                      "该作业帧数": len(idx), "已进总表": jok,
                      "覆盖": bool(old and a.force)}, ensure_ascii=False, indent=1))
    return 0 if iok else 6


def cmd_get(a) -> int:
    bad = _bad(a.name, "name")
    if bad:
        print(json.dumps({"ok": False, "why": bad}, ensure_ascii=False))
        return 2
    _, ra = _cloud()
    ent = _jidx(ra, a.job_id).get(a.name)
    if not ent:
        print(json.dumps({"ok": False, "why": "该作业索引里没有这帧 ⇒ 拒（不猜 sha）",
                          "job_id": a.job_id, "name": a.name,
                          "有这些帧": sorted(_jidx(ra, a.job_id))[:20]}, ensure_ascii=False))
        return 2
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ok, tail = ra._get("%s/%s/%s" % (FRAMES, a.job_id, a.name), out)
    if not ok:
        print(json.dumps({"ok": False, "why": "下载失败", "tail": tail}, ensure_ascii=False))
        return 3
    same = sha256_file(out) == ent.get("sha256")
    print(json.dumps({"ok": same, "落盘": str(out), "bytes": out.stat().st_size,
                      "验": "✅ 与索引 sha 一致" if same else "✗ **与索引 sha 不符**",
                      "索引sha": ent.get("sha256")}, ensure_ascii=False, indent=1))
    return 0 if same else 5


def cmd_ls(a) -> int:
    _, ra = _cloud()
    if a.job_id:
        idx = _jidx(ra, a.job_id)
        print(json.dumps({"job_id": a.job_id, "帧数": len(idx),
                          "帧": [{"name": k, "bytes": v.get("bytes"),
                                 "sha256_前16": str(v.get("sha256"))[:16], "at": v.get("at")}
                                for k, v in sorted(idx.items())]},
                         ensure_ascii=False, indent=1))
        return 0
    j = _jobs(ra)
    print(json.dumps({"作业总表": j, "作业数": len(j),
                      "帧合计": sum(int(v.get("帧数") or 0) for v in j.values())},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_verify(a) -> int:
    _, ra = _cloud()
    j = _jobs(ra)
    if a.job_id:
        j = {a.job_id: j.get(a.job_id, {})}
    bad, rows = 0, []
    vd = ROOT / "state" / "_frame_verify"
    vd.mkdir(parents=True, exist_ok=True)
    for jid in sorted(j):
        idx = _jidx(ra, jid)
        if not idx:
            bad += 1
            rows.append({"job_id": jid, "结果": "✗ 总表有它但索引取不到/为空"})
            continue
        for name in sorted(idx):
            out = vd / ("%s__%s" % (jid, name))
            ok, _ = ra._get("%s/%s/%s" % (FRAMES, jid, name), out)
            if not ok:
                bad += 1
                rows.append({"job_id": jid, "name": name, "结果": "✗ 拉不回来"})
                continue
            same = sha256_file(out) == idx[name].get("sha256")
            bad += 0 if same else 1
            rows.append({"job_id": jid, "name": name,
                         "结果": "✅ 一致" if same else "✗ **sha 不符**"})
            out.unlink(missing_ok=True)
    print(json.dumps({"逐条复核": rows, "合计": {"条数": len(rows), "不符": bad},
                      "判据": "全部拉回逐字节一致才算帧缓存可用"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 5


def cmd_selftest(a) -> int:
    """真身自检：**2 正 + 5 负**，跑在本地替身云上（同一段代码，不碰真云）。"""
    dp = _dp()
    keep = dp.LOCAL_CLOUD
    lines, bad = [], 0

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    with tempfile.TemporaryDirectory() as td:
        tdp = pathlib.Path(td)
        f1 = tdp / "f0001.png"
        f1.write_bytes(b"\x89PNG\r\n\x1a\n" + b"frame-one" * 2048)
        f2 = tdp / "f0002.png"
        f2.write_bytes(b"\x89PNG\r\n\x1a\n" + b"frame-two" * 2048)
        dp.LOCAL_CLOUD = str(tdp / "cloud")

        class P:
            frame, job_id, name, force = str(f1), "job-x", "f0001.png", False
        rc1 = cmd_put(P())
        ck("正控①·put 往返一致并进索引", rc1 == 0, "rc=%d（期望 0）" % rc1)

        class P2:
            frame, job_id, name, force = str(f1), "job-x", "f0001.png", False
        rc2 = cmd_put(P2())
        ck("正控②·同名同内容 ⇒ 幂等跳过", rc2 == 0, "rc=%d（期望 0）" % rc2)

        class P3:
            frame, job_id, name, force = str(f2), "job-x", "f0001.png", False
        rc3 = cmd_put(P3())
        ck("负控①·同名**不同内容** ⇒ 拒（绝不静默覆盖）", rc3 == 7, "rc=%d（期望 7）" % rc3)

        class P4:
            frame, job_id, name, force = str(f2), "job-x", "f0001.png", True
        rc4 = cmd_put(P4())
        ck("负控②·显式 --force 才允许覆盖并留痕", rc4 == 0, "rc=%d（期望 0）" % rc4)

        class G:
            job_id, name, out = "job-x", "f0001.png", str(tdp / "back.png")
        rc5 = cmd_get(G())
        rcT = _tamper_and_get(dp, tdp)          # 先量出来，再断言（读数要出现在判据里）
        ck("负控③·云上被改坏 ⇒ get 报不符", rcT == 5, "rc=%d（期望 5）" % rcT)

        class G2:
            job_id, name, out = "job-x", "没这帧.png", str(tdp / "x.png")
        rc6 = cmd_get(G2())
        ck("负控④·索引没有 ⇒ 拒", rc6 == 2, "rc=%d（期望 2）" % rc6)

        class P5:
            frame, job_id, name, force = str(f1), "job-x", "../逃逸.png", False
        rc7 = cmd_put(P5())
        ck("负控⑤·帧名带路径分隔符 ⇒ 拒", rc7 == 2, "rc=%d（期望 2）" % rc7)

        idx = _jidx(_cloud()[1], "job-x")
        ck("正控③·索引记下了覆盖留痕", bool(idx.get("f0001.png", {}).get("被覆盖")) and rc5 == 0,
           "被覆盖=%s · get rc=%d（覆盖后内容应为 f2 且一致）"
           % (idx.get("f0001.png", {}).get("被覆盖"), rc5))

    dp.LOCAL_CLOUD = keep
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines,
                      "口径": "跑在**本地替身云**上；负控证明**坏数据/坏协作拦得住**"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def _tamper_and_get(dp, tdp: pathlib.Path) -> int:
    """把替身云上的帧改坏，再 get —— 必须报不符。"""
    p = pathlib.Path(dp.LOCAL_CLOUD) / FRAMES / "job-x" / "f0001.png"
    if p.is_file():
        p.write_bytes(b"TAMPERED" * 100)

    class G:
        job_id, name, out = "job-x", "f0001.png", str(tdp / "tampered.png")
    return cmd_get(G())


def main() -> int:
    ap = argparse.ArgumentParser(description="模块 04 · frame-cache（帧缓存，按作业分桶 + 撞名闸）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("put")
    p.add_argument("job_id")
    p.add_argument("frame")
    p.add_argument("--name", default="")
    p.add_argument("--force", action="store_true", help="显式覆盖同名不同内容的帧（留痕）")
    p.set_defaults(func=cmd_put)
    g = sub.add_parser("get")
    g.add_argument("job_id")
    g.add_argument("name")
    g.add_argument("--out", required=True)
    g.set_defaults(func=cmd_get)
    ln = sub.add_parser("ls")
    ln.add_argument("job_id", nargs="?", default="")
    ln.set_defaults(func=cmd_ls)
    v = sub.add_parser("verify")
    v.add_argument("job_id", nargs="?", default="")
    v.set_defaults(func=cmd_verify)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
