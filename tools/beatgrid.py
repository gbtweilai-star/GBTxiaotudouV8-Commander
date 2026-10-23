# -*- coding: utf-8 -*-
"""beatgrid · 时间基层（BPM → 帧率反推 → 网格 JSON → 段落能量）
⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印

立项依据：WorkBuddy《三套工作流工程手册》第 1 节 L3：
「**同步必须"算出来"，不是"测出来"**」——先定时间基（BPM / 帧率），再让内容服从它；
每个时刻的值是**算出来的实数**、可导出为**单一数据源**、且可回读证伪。

三条硬纪律（手册原文，本件照抄）：
  ① **帧率必须由 BPM 反推**：每拍不是整数帧 ⇒ 切换点落在两帧之间，编码器就近取整＝误差注入；
  ② 时刻用 **`t = round(i × BEAT, 6)`（按索引乘法）**，**绝不用 `t += BEAT` 累加**（800 拍会累出可测漂移）；
  ③ 段落**能量 0–1 同时驱动配器与剪辑密度**（`小节/镜`：能量越高每镜越短）。

命令：
  python tools/beatgrid.py derive --bpm 100              # 帧率反推表（每拍是否整数帧）
  python tools/beatgrid.py plan --bpm 100 --minutes 8 --fps 30 [--out state/beat_grid.json]
  python tools/beatgrid.py check <grid.json>             # 拍间隔 min==max · 总帧数整数（断言）
  python tools/beatgrid.py align <manifest.json> --bpm 100   # 把拍子表时长吸附到整拍（写回前先备份）
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")

# 段落能量 → 剪辑密度（手册实测表：能量越高，一小节内的镜头越多）
ENERGY_TABLE = [
    #  (名称,   能量,  小节/镜, 观感)
    ("intro",  0.22, 4, "一个镜头停 4 小节，让观众进入"),
    ("build",  0.45, 3, "逐渐加速"),
    ("verse",  0.62, 2, "稳定推进"),
    ("break",  0.34, 2, "抽空，多用特写"),
    ("chorus", 0.92, 1, "每小节换镜，密度最高"),
    ("outro",  0.50, 3, "递减收束"),
]
# 曲式模板（8 分钟 @ BPM100 = 200 小节；手册实测曲式 A-B-A'-B'-C）
FORM_8MIN = [("intro", 8), ("build", 16), ("verse1", 32), ("chorus1", 32),
             ("break", 8), ("verse2", 32), ("chorus2", 48), ("outro", 24)]
# 景别 → zoom 区间与纵向锚点（手册实测）
SHOT_SIZE = {"full": (1.00, 1.06, 0.50), "medium": (1.26, 1.34, 0.16), "close": (1.62, 1.74, 0.08)}


def derive_fps(bpm: float, cands=(24, 25, 30, 60)) -> dict:
    """**帧率反推**：每拍帧数必须是整数，否则切点落在帧间。"""
    beat = 60.0 / float(bpm)
    rows = []
    for f in cands:
        fpb = f * beat
        rows.append({"fps": f, "frames_per_beat": round(fpb, 3),
                     "ok": abs(fpb - round(fpb)) < 1e-6,
                     "note": "常用最优解" if f == 30 and abs(fpb - round(fpb)) < 1e-6 else ""})
    good = [r["fps"] for r in rows if r["ok"]]
    rec = 30 if 30 in good else (good[0] if good else None)   # 手册：30fps 常用最优解
    return {"ok": bool(good), "bpm": bpm, "beat_sec": round(beat, 6), "rows": rows,
            "recommend": rec,
            "口径": "先算这张表再定帧率；反过来「先定 24fps 再想同步」是死路"}


def energy_of(section: str) -> tuple[float, int]:
    base = section.rstrip("0123456789'")
    for name, e, spb, _ in ENERGY_TABLE:
        if base == name:
            return e, spb
    return 0.5, 3


def plan(bpm: float = 100.0, minutes: float = 8.0, fps: int = 30,
         beats_per_bar: int = 4, form: list | None = None) -> dict:
    """出网格：**乘法算时刻** + 段落表（含能量与密度）。"""
    beat = 60.0 / float(bpm)
    bar = beat * beats_per_bar
    total_sec = round(minutes * 60.0, 6)
    n_bars = int(round(total_sec / bar))
    if abs(n_bars * bar - total_sec) > 1e-6:
        return {"ok": False, "error": f"时长对不齐小节：{minutes}min 不是 {bar:.3f}s 的整数倍",
                "hint": "换 BPM 或换片长（手册：小节数×每小节秒数 == 目标时长，零余数）"}
    der = derive_fps(bpm, (fps,))
    if not der["rows"][0]["ok"]:
        return {"ok": False, "error": f"{fps}fps 下每拍 {der['rows'][0]['frames_per_beat']} 帧（非整数）",
                "hint": "换帧率（见 derive）"}
    form = form or [(n, c) for n, c in FORM_8MIN]
    scale = n_bars / sum(c for _, c in form)
    sections, beats, bi = [], [], 0
    for name, bars in form:
        b = max(1, int(round(bars * scale)))
        e, spb = energy_of(name)
        start_bar = bi // beats_per_bar + 1
        end_bar = (bi + b * beats_per_bar - 1) // beats_per_bar + 1
        sections.append({"name": name, "bars": b, "energy": e, "shots_per_bar": spb,
                         "start_bar": start_bar, "end_bar": end_bar,
                         "start_t": round(start_bar * bar - bar, 6),
                         "end_t": round(end_bar * bar, 6)})
        for k in range(b * beats_per_bar):
            idx = bi + k
            beats.append({"i": idx, "t": round(idx * beat, 6),          # ← 乘法，不累加
                          "bar": idx // beats_per_bar + 1,
                          "beat_in_bar": idx % beats_per_bar + 1,
                          "downbeat": (idx % beats_per_bar == 0),
                          "section": name})
        bi += b * beats_per_bar
    tot_frames = len(beats) * (fps * beat)
    if abs(tot_frames - round(tot_frames)) > 1e-6:
        return {"ok": False, "error": "总帧数非整数"}
    return {"ok": True, "bpm": float(bpm), "beats_per_bar": beats_per_bar,
            "beat_sec": round(beat, 6), "bar_sec": round(bar, 6),
            "total_beats": len(beats), "total_bars": n_bars, "duration": total_sec,
            "fps": fps, "frames_total": int(round(tot_frames)),
            "sections": sections, "beats": beats,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "口径": "t=round(i×BEAT,6) 按索引乘法（禁累加）；能量驱动密度；单一数据源"}


def check(grid: dict) -> dict:
    """**回读证伪**（离散断，不只自证）：拍间隔 min==max · 总帧数整数 · 段落闭合。"""
    beats = grid.get("beats") or []
    if len(beats) < 2:
        return {"ok": False, "error": "拍数不足"}
    ts = [b["t"] for b in beats]
    diffs = [round(ts[i + 1] - ts[i], 6) for i in range(len(ts) - 1)]
    mn, mx = min(diffs), max(diffs)
    fps, beat = grid.get("fps"), grid.get("beat_sec")
    issues = []
    if abs(mn - mx) > 1e-6:
        issues.append(f"拍间隔不恒定：min={mn} max={mx}")
    if abs(mn - beat) > 1e-6:
        issues.append(f"拍间隔 {mn} ≠ beat_sec {beat}")
    if fps and abs(fps * beat - round(fps * beat)) > 1e-6:
        issues.append(f"每拍 {fps * beat} 帧非整数")
    tot = (beats[-1]["t"] - beats[0]["t"]) + beat
    if abs(tot - grid.get("duration", tot)) > 1e-6:
        issues.append(f"网格总长 {round(tot,6)} ≠ duration {grid.get('duration')}")
    secs = grid.get("sections") or []
    if secs and abs(secs[-1]["end_t"] - grid.get("duration", 0)) > 1e-6:
        issues.append("段落表未闭合到 duration")
    return {"ok": not issues, "beats": len(beats), "beat_sec": beat,
            "min_interval": mn, "max_interval": mx, "total_frames": grid.get("frames_total"),
            "issues": issues,
            "口径": "回读证伪：拍间隔 min==max、每拍整数帧、段落闭合；**不通过不许进入下一步**"}


def align(manifest_path: Path, bpm: float, backup: bool = True) -> dict:
    """把拍子表/清单的每拍时长**吸附到整拍**（BPM 对齐），并回报改了几处。

    只在"声明了 bpm"时才做；改前自动备份（`.bak-beatgrid-<时间>`）。
    """
    mp = Path(manifest_path)
    m = json.loads(mp.read_text(encoding="utf-8"))
    beat = 60.0 / float(bpm)
    changed = []
    items = m.get("beats") or []
    for b in items:
        d = float(b.get("dur", 0) or 0)
        if d <= 0:
            continue
        n = max(1, int(round(d / beat)))
        nd = round(n * beat, 6)
        if abs(nd - d) > 1e-6:
            changed.append({"id": b.get("id"), "old": d, "new": nd, "beats": n})
            b["dur"] = nd
    m["bpm"] = float(bpm)
    if backup and changed:
        bak = mp.with_suffix(mp.suffix + f".bak-beatgrid-{time.strftime('%Y%m%d-%H%M%S')}")
        bak.write_text(json.dumps(json.loads(mp.read_text(encoding="utf-8")), ensure_ascii=False, indent=1),
                       encoding="utf-8")
        m["_beatgrid_backup"] = bak.name
    if changed:
        mp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "manifest": str(mp), "bpm": bpm, "beat_sec": round(beat, 6),
            "changed": changed, "count": len(changed),
            "口径": "时长吸附到整拍（切换点落在拍上）；改前自动备份"}


def beat_times(grid: dict, upto: float | None = None) -> list[float]:
    """给音频打点用：**落在网格上的时刻表**（乘法算，不累加）。"""
    return [b["t"] for b in grid.get("beats", []) if upto is None or b["t"] < upto + 1e-9]


def main(argv: list) -> int:
    if len(argv) < 2:
        print(__doc__); return 2
    cmd = argv[1]
    def opt(k, d=None):
        return argv[argv.index(k) + 1] if k in argv else d
    if cmd == "derive":
        print(json.dumps(derive_fps(float(opt("--bpm", 100))), ensure_ascii=False, indent=1)); return 0
    if cmd == "plan":
        g = plan(float(opt("--bpm", 100)), float(opt("--minutes", 8)), int(opt("--fps", 30)))
        if not g["ok"]:
            print(json.dumps(g, ensure_ascii=False, indent=1)); return 1
        out = Path(opt("--out", "state/beat_grid.json"))
        out = out if out.is_absolute() else ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        slim = dict(g); slim["beats"] = g["beats"]
        out.write_text(json.dumps(slim, ensure_ascii=False, indent=1), encoding="utf-8")
        c = check(g)
        print(f"网格 {out.name} · {g['total_beats']} 拍 / {g['total_bars']} 小节 · "
              f"{g['duration']}s · {g['fps']}fps · 帧数 {g['frames_total']} · 校验 {'通过' if c['ok'] else '✘ ' + str(c['issues'])}")
        return 0 if c["ok"] else 1
    if cmd == "check" and len(argv) >= 3:
        g = json.loads((ROOT / argv[2]).read_text(encoding="utf-8"))
        c = check(g)
        print(json.dumps(c, ensure_ascii=False, indent=1))
        return 0 if c["ok"] else 1
    if cmd == "align" and len(argv) >= 3:
        r = align(ROOT / argv[2], float(opt("--bpm", 100)))
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
