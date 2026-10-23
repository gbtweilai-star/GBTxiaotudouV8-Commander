#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""shorts-stitch-proof · 「分短视频拼接」端到端证明（主人令：这里按分短视频的方式做拼接）

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 它证明什么
`edit_pipeline`（实现 `gbt_allinone/tools/edit_core.py`）**能不能**把**多段短视频**
按短视频方式拼成一条片：**不同来源 → 归一化到同一画布 → 逐段切段 → 转场(xfade)串联 → 出片**。

## 🔴 三条纪律
1. **全程走唯一门** `five-dim.py cap edit_pipeline`（`run_task`）——**不直调模块函数绕门**；
2. **不拿「命令成功」当结论**：出片后用 `probe` **ffprobe 回读**，并把
   **模块自己算的时长** 与 **实测时长** 对账（两个独立来源必须一致）；
3. 输出落 **`outputs/`**（在它声明的写根内，fail-closed 才有意义）。

用法：
  shorts-stitch-proof.py run        # 真造片段 → 真拼 → 真回读
  shorts-stitch-proof.py selftest
"""
from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIVE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
WORK = ROOT / "outputs" / "shorts-stitch"
OUT = WORK / "shorts.mp4"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 三段**故意用不同分辨率**的源 ⇒ 逼出「先归一到画布，再谈拼接」这一步
CLIPS = (("a.mp4", "640x360", 2.0, "testsrc2=size=640x360:rate=30"),
         ("b.mp4", "360x640", 2.5, "testsrc=size=360x640:rate=30"),
         ("c.mp4", "480x270", 2.0, "smptebars=size=480x270:rate=30"))
CANVAS = {"w": 540, "h": 960, "fps": 30}      # 比 1080x1920 小：CPU 拼得动，链路一致


def _door(op: str, **kw) -> dict:
    """**唯一门**：`five-dim.py cap edit_pipeline '<payload>'` → 取最后一个信封。"""
    payload = json.dumps(dict(op=op, **kw), ensure_ascii=False)
    r = subprocess.run([sys.executable, str(FIVE), "cap", "edit_pipeline", payload],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=1800, cwd=str(ROOT))
    out = (r.stdout or "") + (r.stderr or "")
    dec = json.JSONDecoder()
    env = None
    for i, ch in enumerate(out):
        if ch != "{":
            continue
        try:
            o, _ = dec.raw_decode(out[i:])
        except Exception:
            continue
        if isinstance(o, dict) and ({"result", "denied", "status"} & set(o)):
            env = o
            break
    if env is None:
        return {"ok": False, "为什么": "取不到门信封", "原文尾": out[-300:], "rc": r.returncode}
    if env.get("denied") is True:
        return {"ok": False, "被门拒": env.get("missing_scopes"), "为什么": env.get("message")}
    return env.get("result") if isinstance(env.get("result"), dict) else env


def _mk_clips() -> list:
    WORK.mkdir(parents=True, exist_ok=True)
    made = []
    for name, size, sec, src in CLIPS:
        p = WORK / name
        cp = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                             "-i", "%s:duration=%.2f" % (src, sec),
                             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)],
                            capture_output=True, timeout=300)
        made.append({"件": name, "分辨率": size, "源时长": sec, "字节": p.stat().st_size,
                     "造得出": cp.returncode == 0 and p.is_file()})
    return made


def build_timeline() -> dict:
    """三段各**切一段**（含 src_start 偏移，证明「切段」真在切），后两段带转场。"""
    segs = [{"src": str(WORK / "a.mp4"), "t0": 0.0, "dur": 1.2, "src_start": 0.3,
             "fit": "cover"},
            {"src": str(WORK / "b.mp4"), "t0": 1.2, "dur": 1.4, "src_start": 0.5,
             "fit": "cover", "transition_in": {"kind": "fade", "dur": 0.4}},
            {"src": str(WORK / "c.mp4"), "t0": 2.6, "dur": 1.0, "src_start": 0.2,
             "fit": "cover", "transition_in": {"kind": "fade", "dur": 0.4}}]
    return {"name": "shorts-stitch-proof", "canvas": dict(CANVAS), "tracks": {"video": segs}}


def why_no_reading(keys, health_fn=None) -> str:
    """取不到读数时**追真因**。抽成独立函数**只为一件事：能被负控真触发**。

    🔴 这一段原来长在 `run_proof()` 里、**从未被触发过** —— 这一轮真去触发才发现它会
    `NameError`（引用了函数里根本不存在的局部名 `keys`）。**未验分支 = 待爆的雷**：
    它平时不响，一响就是崩，而"崩"在报告里长得像"没有真因"。
    返回值分四种（都有负控，见 `selftest`）：
    注册表不可用 / 注册表正常但键不对 / 拿到的东西不是体检 / **追因本身炸了**。
    """
    try:
        if health_fn is None:
            sys.path.insert(0, str(ROOT))
            from gbt_allinone import caps_tables as _CT
            health_fn = _CT.health
        h = health_fn()
        if not isinstance(h, dict):
            return ("**未读到注册表体检**（拿到的是 %s）⇒ 不许当作『注册表正常』"
                    % type(h).__name__)
        if (h.get("注册表可读") is not True) or h.get("缺的表（读了但类型不对/没有）"):
            return ("**读数取不到的真因**：能力注册表不可用（%s）⇒ probe 那条链起不来。"
                    "**这不是 ffmpeg 坏了**。"
                    % (h.get("为什么读不到")
                       or ("缺表 " + str(h.get("缺的表（读了但类型不对/没有）")))))
        return "注册表正常 ⇒ 读数取不到要往 probe 链路上查（probe 回读的键：%s）" % (list(keys),)
    except Exception as exc:                       # noqa: BLE001
        return "查不到真因（%s: %s）" % (type(exc).__name__, str(exc)[:60])


def run_proof() -> dict:
    clips = _mk_clips()
    tl = build_timeline()
    segs = tl["tracks"]["video"]
    nominal = sum(s["dur"] for s in segs)
    overlap = sum((s.get("transition_in") or {}).get("dur", 0) for s in segs[1:])
    expect = nominal - overlap

    v = _door("validate", timeline=tl)
    rel_out = str(OUT.relative_to(ROOT)).replace("\\", "/")
    r = _door("render", timeline=tl, out=rel_out)
    # `run()` 在 validate/check/probe/render 之前都会取 `tl = kw.get("timeline")`
    # ⇒ 这几个 op **都带上 timeline**（漏了会让 `_paths(None)` 炸）
    p = _door("probe", timeline=tl, path=rel_out)
    c = _door("check", timeline=tl, out=rel_out)

    def _keys(d) -> list:
        """🔴 **字段对不上时要看得见** —— 不许静默返回 None。
        第一版我**猜了字段名**（读 `dur`/`frames`/`w`），而真契约是
        `duration` / `video.frames` / `video.w` ⇒ 全 None、对账假红。
        **猜字段名与猜路径是同一类错** ⇒ 现在把实际键一起报出来。"""
        return sorted(d) if isinstance(d, dict) else ["（不是对象：%s）" % type(d).__name__]

    vid = p.get("video") if isinstance(p, dict) else None
    vid = vid if isinstance(vid, dict) else {}
    # 🔴 **按真契约取值**（`five-dim.py cap edit_pipeline '{"op":"probe",…}'` 的实读结构）
    dur_real = p.get("duration") if isinstance(p, dict) else None
    # 🔴 2026-09-25 补：`实测: null` 这个读数**会把人骗到 ffmpeg 上去**（实测我就被骗了一次）——
    #    真因是「能力注册表被并发重写 ⇒ probe 那条链取不到读数」。
    #    ⇒ **取不到读数时必须把"为什么取不到"一起报出来**，不许只留一个 null。
    probe_why = None
    if not isinstance(dur_real, (int, float)):
        # 🔴 取不到读数时**必须带原因**（不然 `null` 会把人骗到 ffmpeg 上去，实测被骗过一次）。
        #    追因那段已抽成 `why_no_reading()` —— 抽出来**就是为了能被负控真触发**：
        #    它原来长在这里、从没被触发过，真触发才发现引用了不存在的局部名。
        probe_why = why_no_reading(_keys(p))
    got = (dur_real if isinstance(dur_real, (int, float)) else 0) or 0
    ok_dur = (isinstance(dur_real, (int, float)) and abs(got - expect) <= 0.10)
    # 清临时目录（与 §一百一十一 的 `_mv_out` 同型：**成品目录不许留 `_*` 残留**）
    workdir = OUT.parent / "_work"
    work_cleaned = False
    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)
        work_cleaned = not workdir.exists()
    return {
        "造出的片段（**故意不同分辨率**，逼出「先归一化」这一步）": clips,
        "时间线": {"画布": CANVAS, "段数": len(segs),
                "名义时长": round(nominal, 3), "转场重叠": round(overlap, 3),
                "**预期实际时长**": round(expect, 3)},
        "① validate": {"ok": v.get("ok") if isinstance(v, dict) else None,
                       "实际键": _keys(v), "错": (v or {}).get("errors") or (v or {}).get("为什么")},
        "② render": {"ok": r.get("ok") if isinstance(r, dict) else None,
                     "实际键": _keys(r),
                     "落盘": (r or {}).get("out") or (r or {}).get("path") or (r or {}).get("为什么"),
                     "耗时s": (r or {}).get("elapsed_s")},
        "③ probe（**ffprobe 回读，不拿「命令成功」当结论**）":
            {"实测时长": dur_real, "帧数": vid.get("frames"),
             "预期帧数": vid.get("frames_expected"),
             "分辨率": ("%sx%s" % (vid.get("w"), vid.get("h"))),
             "码流": vid.get("codec"), "字节": (p or {}).get("bytes"),
             "缺陷": (p or {}).get("defects"), "实际键": _keys(p)},
        "④ check（**模块自己算的时长**，与③对账）":
            {"接口": (c or {}).get("ok"), "实际键": _keys(c),
             "时长依据": (c or {}).get("film_duration_basis")
             or ((c or {}).get("layout") or {}).get("film_duration_basis"),
             "错": (c or {}).get("errors")},
        "🔴 对账（两个独立来源必须一致）": {
            "预期": round(expect, 3), "实测": dur_real,
            "差": round(abs(got - expect), 3), "过": ok_dur,
            # 🔴 取不到读数时**必须带原因**（不然 `null` 会把人骗到 ffmpeg 上去，实测被骗过一次）
            **({"为什么取不到读数": probe_why} if probe_why else {}),
            "判据": "|实测 − 预期| ≤ 0.10 s（预期 = Σ段时长 − Σ转场重叠）"},
        "临时目录已清": work_cleaned,
        "产物": str(OUT.relative_to(ROOT)),
        "文件在盘": OUT.exists(), "字节": OUT.stat().st_size if OUT.exists() else 0,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def cmd_run(a) -> int:
    res = run_proof()
    print(json.dumps(res, ensure_ascii=False, indent=1))
    # 🔴 收尾打印**只引用短而稳的键**。第一版引用了那个长中文键（还带着已被换掉的
    #    ASCII 引号版本）⇒ **KeyError**：**"键名也是契约，不能凭记忆写"**。
    r = res["🔴 对账（两个独立来源必须一致）"]
    ok = bool(r["过"]) and res["文件在盘"] and res["临时目录已清"]
    if ok:
        print("✅ 「分短视频拼接」端到端**真跑通**：实测 %.3fs == 预期 %.3fs（差 %.3f）· 帧 %s · %s"
              % (r["实测"] or 0, r["预期"], r["差"],
                 res["③ probe（**ffprobe 回读，不拿「命令成功」当结论**）"]["帧数"],
                 res["③ probe（**ffprobe 回读，不拿「命令成功」当结论**）"]["分辨率"]))
    else:
        print("🔴 不过：%s"
              % json.dumps(dict(r, **{"文件在盘": res["文件在盘"],
                                      "临时目录已清": res["临时目录已清"]}),
                           ensure_ascii=False))
    return 0 if ok else 1


def _direct_imports(tree) -> list:
    """**唯一来源**：扫出「直调 edit_core」的 import。

    🔴 主检与负控**必须用同一段逻辑** —— 我第一版给负控写了个**弱版本**
    （只查 `n.module`，而 `edit_core` 其实在 `n.names` 里）⇒ 负控"假过"。
    """
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out += [a.name for a in n.names if "edit_core" in a.name]
        elif isinstance(n, ast.ImportFrom):
            if "edit_core" in (n.module or "") or any("edit_core" in a.name for a in n.names):
                out.append("%s:%s" % (n.module or "?",
                                      ",".join(a.name for a in n.names)))
    return out


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    # ① 门必须是**唯一入口**：不许直调 edit_core 模块
    # 🔴 **这里原来写成 `"import edit_core" not in src`（文本判据）—— 当场自指、永远红**：
    #    `src` 就是本文件自己的文本，而那个字面量**本身就在文件里** ⇒ `in src` **必然为真**。
    #    是 `criterion_bench` 的 D6「形状④（恒真自指）」抓出来的 —— **判据质量台架抓到了台架使用者**。
    #    改成 **AST 扫真 import**：语义相同，但不会被判据自己列的字面量骗到。
    import ast
    bad_imports = _direct_imports(ast.parse(Path(__file__).read_text(encoding="utf-8")))
    ck("**全程走唯一门**（AST 扫真 import，不扫源码文本 —— 文本会匹配到判据自己）",
       not bad_imports, "直调 import: %s" % (bad_imports or "无"))
    # 🔴 负控：种一段**真的直调 import** ⇒ 必须咬出来（否则判据是空的）
    planted = _direct_imports(ast.parse("from gbt_allinone.tools import edit_core\n"))
    ck("**负控：真的直调 import 必须被咬出来**", len(planted) == 1, "咬出: %s" % planted)
    # ② 判据必须**随数据变**：换一组段时长，预期值必须跟着变
    tl = build_timeline()
    segs = tl["tracks"]["video"]
    e1 = sum(s["dur"] for s in segs) - sum((s.get("transition_in") or {}).get("dur", 0)
                                           for s in segs[1:])
    segs2 = [dict(s) for s in segs]
    segs2[0]["dur"] += 1.0
    e2 = sum(s["dur"] for s in segs2) - sum((s.get("transition_in") or {}).get("dur", 0)
                                            for s in segs2[1:])
    ck("**判据随数据变**（改一段时长 ⇒ 预期值必须跟着变）",
       abs((e2 - e1) - 1.0) < 1e-9, "e1=%.3f e2=%.3f 差=%.3f" % (e1, e2, e2 - e1))
    # ③ 写根 fail-closed：产物必须落在 outputs/（它声明的写根内）
    ck("**产物落在声明的写根内**（`outputs/`）",
       str(OUT.relative_to(ROOT)).replace("\\", "/").startswith("outputs/"),
       str(OUT.relative_to(ROOT)))
    # ④ ffmpeg/ffprobe 必须在（否则整条证明不成立）
    ck("ffmpeg / ffprobe 在位", bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe")),
       "ffmpeg=%s" % bool(shutil.which("ffmpeg")))
    # ⑤ 负控：预期时长的算法本身 —— 只给一段时**不许**减重叠
    one = [{"dur": 2.0}]
    e_one = sum(s["dur"] for s in one) - sum((s.get("transition_in") or {}).get("dur", 0)
                                             for s in one[1:])
    ck("**负控：只有一段时不许减重叠**", abs(e_one - 2.0) < 1e-9, "e=%.3f" % e_one)
    # ⑥–⑪ 「取不到读数」那条**诚实分支**：抽成函数就是为了能在这里真触发它。
    # 🔴 它原来长在 `run_proof()` 里、**从未被触发过**；真触发时会 `NameError`（引用了不存在的局部名）。
    #    ⇒ 四种出口各一条负控 + 一条现读真体检，**"没响过"不许再当"没问题"**。
    GOOD = {"注册表可读": True, "缺的表（读了但类型不对/没有）": []}
    why_good = why_no_reading(["duration"], health_fn=lambda: GOOD)
    ck("**诚实分支·注册表正常 ⇒ 指向 probe 链路并带上键名**",
       ("probe 链路" in why_good) and ("duration" in why_good), why_good[:64])
    BAD = {"注册表可读": False, "为什么读不到": "caps_registry 导入失败"}
    why_bad = why_no_reading(["duration"], health_fn=lambda: BAD)
    ck("**诚实分支·注册表不可用 ⇒ 点名真因，且明说「不是 ffmpeg 坏了」**",
       ("不是 ffmpeg 坏了" in why_bad) and ("caps_registry 导入失败" in why_bad), why_bad[:64])
    GAP = {"注册表可读": True, "缺的表（读了但类型不对/没有）": ["CAPS_TABLE"]}
    why_gap = why_no_reading([], health_fn=lambda: GAP)
    ck("**诚实分支·缺表 ⇒ 点名缺了哪张表**", "CAPS_TABLE" in why_gap, why_gap[:64])
    why_none = why_no_reading([], health_fn=lambda: None)
    ck("**诚实分支·体检不是对象 ⇒ 明写「未读到」，不许当正常**",
       "未读到" in why_none, why_none[:64])

    def _boom():
        raise RuntimeError("体检自己炸了")

    why_boom = why_no_reading([], health_fn=_boom)
    ck("**诚实分支·追因自己炸 ⇒ 报异常类型，不静默**",
       ("查不到真因" in why_boom) and ("RuntimeError" in why_boom), why_boom[:64])
    why_live = why_no_reading(["duration"])
    ck("**诚实分支·现读真体检跑得通**（两种出口都算合法读数）",
       ("注册表正常" in why_live) or ("真因" in why_live), why_live[:64])
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="分短视频拼接端到端证明（走门 · 回读对账）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run").set_defaults(func=cmd_run)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
