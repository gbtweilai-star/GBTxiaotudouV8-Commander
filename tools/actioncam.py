# -*- coding: utf-8 -*-
"""actioncam · 动作镜头控制系统（触手可调 · 逐拍精准）
⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印

岗位：动作戏的**镜头语法层**——甩镜/急推/手持抖动/主观镜头(POV)/变速/打击帧停格，
拍子表（beat sheet）为唯一真相：每一拍 = 运镜 + 机位角度 + 焦点锚 + 时长 + 画质档。

设计铁律（全部来自本仓实测教训）：
  · ffmpeg 表达式**零逗号**（min/if 的逗号会打断 filter 参数解析 ⇒ 一律斜率/三角函数）；
  · 生成图**只喂英文 prompt**（中文污染画面）+ **种子锁定**（可复现=可审计）；
  · 段渲染走 subprocess、总装走 concat 清单绝对路径（bash 通道纪律）；
  · 产出即绑触手（autobind），台账留痕。

命令：
  python tools/actioncam.py plan  <manifest>              # 拍子表状态读数
  python tools/actioncam.py gen   <manifest> [--beat B1]  # 生成缺图（英文 prompt + 种子锁）
  python tools/actioncam.py seg   <manifest> [--beat B1]  # 逐拍渲染（运镜+角度+画质档）
  python tools/actioncam.py build <manifest> [--skip B3] [--only B1,B2]
  python tools/actioncam.py add   <manifest> --after B2 --id B2b --move shake --angle low --dur 0.5 --prompt "..."
  python tools/actioncam.py rm    <manifest> --beat B3
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
FPS = 25
POLL = "https://image.pollinations.ai/prompt/"

# ── 画质档位（画质参数调优 · 2026-09-27 升档：交付默认 1080p）────────
QUALITY = {
    "hd":  {"w": 1280, "h": 720,  "crf": 20, "blur": 0, "grain": 5},
    "fhd": {"w": 1920, "h": 1080, "crf": 18, "blur": 0, "grain": 6},
    "cinema": {"w": 1920, "h": 1080, "crf": 16, "blur": 0, "grain": 7},
}
# 源图超采样倍率（pollinations 固定 1024×576 ⇒ 本地 lanczos 2x + cas 提锐再渲，才是真 1080p 细节）
SUPERSAMPLE = 2

# 机位角度 → 画面重心锚（zoompan 的 y 锚点）+ 后期旋转（荷兰角）
#   low=仰拍(重心偏下·主体压顶) high=俯拍(重心偏上) eye=平视 dutch=斜角
ANGLES = {
    "eye":   {"fy": 0.45, "rot": 0.0},
    "low":   {"fy": 0.68, "rot": 0.0},
    "high":  {"fy": 0.28, "rot": 0.0},
    "dutch": {"fy": 0.45, "rot": 0.06},
}

# 动作镜头语法（运镜）。每个函数给出 zoompan 的 z/x/y 表达式（**零逗号**）+ 后处理链。
# 表达式可用变量：D=总帧数
MOVES = {
    # 急推（crash zoom）：1 → 1.55 线性冲（快到无需缓动）
    "crash_zoom": lambda d: dict(z=f"1+0.55*on/{max(1, d)}",
                                 x="(iw-iw/zoom)/2", y="(ih-ih/zoom)/2"),
    # 甩镜（whip pan）：大位移快扫 + 轻模糊（whip 的本质是模糊中的位移）
    "whip_lr": lambda d: dict(z="1.28",
                              x=f"(iw-iw/zoom)*on/{max(1, d)}", y="(ih-ih/zoom)/2",
                              post="boxblur=1.5:1"),
    "whip_rl": lambda d: dict(z="1.28",
                              x=f"(iw-iw/zoom)*(1-on/{max(1, d)})", y="(ih-ih/zoom)/2",
                              post="boxblur=1.5:1"),
    # 主观镜头（POV · 用户视角）：呼吸式起伏 + 微旋 + 轻暗角
    # 🔴 rotate **不认 on**（那是 zoompan 的变量）——只认 t（秒）/n（帧号），实测踩过
    "pov_bob": lambda d: dict(z="1.14",
                              x="(iw-iw/zoom)/2",
                              y=f"(ih-ih/zoom)/2+20*sin(2*3.14159*on/{max(1, d*0.8)})",
                              post="rotate=0.016*sin(2*3.14159*t/%.3f)" % (max(1, d) / FPS * 0.8)),
    # 手持抖动（shake）：高频小幅抖（打击/爆炸近旁）
    "shake": lambda d: dict(z="1.20",
                            x=f"(iw-iw/zoom)/2+12*sin(on*7.3)",
                            y=f"(ih-ih/zoom)/2+9*sin(on*9.1)"),
    # 推进（dolly in）：慢推 + 焦点锚可调（配合 low/high 角度）
    "dolly_in": lambda d: dict(z=f"1+0.26*on/{max(1, d)}",
                               x="(iw-iw/zoom)/2", y="@FY@"),
    # 拉出（push out）：从特写退到全景（揭示/收势）
    "push_out": lambda d: dict(z=f"1.28-0.24*on/{max(1, d)}",
                               x="(iw-iw/zoom)/2", y="@FY@"),
    # 环绕感（arc）：横移 + 纵向半波（假环绕，实拍感）
    "arc_lr": lambda d: dict(z="1.22",
                             x=f"(iw-iw/zoom)*on/{max(1, d)}",
                             y=f"(ih-ih/zoom)/2+14*sin(3.14159*on/{max(1, d)})"),
    # 打击帧（impact）：急推 + **末帧停格 + 白闪**（打击瞬间的时间冻结）
    "impact_hold": lambda d: dict(z=f"1+0.7*on/{max(1, d)}",
                                  x="(iw-iw/zoom)/2", y="(ih-ih/zoom)/2",
                                  post="fade=t=in:st=0:d=0.10:color=white",
                                  freeze_tail=0.18),
}
MOVE_CYCLE = ["pov_bob", "crash_zoom", "whip_lr", "shake", "dolly_in", "impact_hold"]
WRITE_ROOTS = ("projects", "outputs", ".scratch")
READ_OPS = ("status", "plan")
WRITE_OPS = ("gen", "seg", "build", "add", "rm")



def _stable_seed(text: str) -> int:
    """稳定种子（与进程无关）——同 filmkit，走共用件 specguard.stable_seed。"""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("specguard", ROOT / "tools" / "specguard.py")
        sg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sg)
        return sg.stable_seed(text, mod=999999)
    except Exception:                                          # noqa: BLE001
        import hashlib
        return int(hashlib.sha256(("gbt-seed:" + text).encode("utf-8")).hexdigest()[:12], 16) % 999999


def load(mp: Path) -> dict:
    return json.loads(mp.read_text(encoding="utf-8"))


def load_checked(mp: Path) -> tuple[dict | None, dict | None]:
    """**fail-fast 载入**：先过规格守卫（specguard），不合法**当场拒跑**；
    合法的顺手补 seed 族（同场固定 + 跨拍派生，可复现）。

    依据：《一句话成片·多智能体自动化架构设计》「参数下沉 = JSON Schema 强约束契约」——
    不合法 Spec 静默跑成错片，是自动化流水线最贵的失败。
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("specguard", ROOT / "tools" / "specguard.py")
        sg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sg)
    except Exception:                                          # noqa: BLE001
        return load(mp), None                                  # 守卫不可用时不阻断（如实降级）
    m = load(mp)
    v = sg.validate_manifest(m, kind="actioncam")
    if not v["ok"]:
        return None, v
    fam = sg.apply_seed_family(m, base=int(m.get("seed_base") or 20260927))
    if fam.get("added"):
        save(mp, m)                                            # 补的种子落盘（定过的就是资产）
    return m, {"ok": True, "seed_family": fam}


def save(mp: Path, m: dict) -> None:
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def sh(cmd, timeout=900):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, cwd=str(ROOT))


def q(p: Path) -> dict:
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
            "default=nw=1:nk=1", str(p)], timeout=60)
    try:
        return {"ok": True, "dur": round(float(r.stdout.strip()), 3)}
    except Exception:
        return {"ok": False, "err": (r.stderr or r.stdout)[-160:]}


def beat_img(m: dict, b: dict) -> Path:
    return ROOT / m["work_dir"] / "imgs" / f"{b['id']}.png"


def beat_prep(m: dict, b: dict) -> Path:
    """超采样后的源图（lanczos 2x + cas 提锐）——渲染从它出发，而不是软的 1024 原图。"""
    return ROOT / m["work_dir"] / "prep" / f"{b['id']}.png"


def beat_seg(m: dict, b: dict) -> Path:
    return ROOT / m["work_dir"] / "segs" / f"{b['id']}.mp4"


def quality(m: dict) -> dict:
    return QUALITY.get(m.get("quality", "hd"), QUALITY["hd"])


def still_filter(m: dict, b: dict) -> str:
    """一拍 = 运镜 + 角度锚 + 画质。返回 ffmpeg -vf 链（零逗号表达式）。

    源图口径：从 **prep（超采样后）** 出发，内部只做"变焦余量归一化"（缩到 W*1.6），
    不再无脑放大——无脑放大 = 软（2026-09-27 修，起因：主人判"图质差"）。
    """
    qa = quality(m)
    W, H = qa["w"], qa["h"]
    D = max(1, int(round(float(b.get("dur", 0.8)) * FPS)))
    move = MOVES[b.get("move", "dolly_in")](D)
    ang = ANGLES.get(b.get("angle", "eye"), ANGLES["eye"])
    fy = move.get("y", "(ih-ih/zoom)/2").replace("@FY@", f"(ih-ih/zoom)*{ang['fy']}")
    head = int(round(W * 1.6))             # 变焦余量归一化（最大 zoom 1.6）
    chain = [f"scale={head}:-2:flags=lanczos",
             f"zoompan=z='{move['z']}':x='{move['x']}':y='{fy}':d=1:s={W}x{H}:fps={FPS}"]
    if ang.get("rot"):
        # 🔴 rotate **不认 on**（zoompan 的变量）——只认 t（秒）/n（帧号），实测 B1/B8 整段 0 帧；
        #    填充色也**不许写 c=none**（yuv 管线 Invalid argument）——默认黑边即可
        chain.append(f"rotate={ang['rot']}*sin(3.14159*t/{D / FPS:.3f})")
    if move.get("post"):
        chain.append(move["post"])
    return ",".join(chain), D, move


def supersample_factor(m: dict) -> int:
    """超采样倍率：让源图宽度 ≥ 输出宽 ×1.6（变焦余量），最少 2x。"""
    qa = quality(m)
    need = qa["w"] * 1.6
    return max(2, int(-(-need // 1024)))    # ceil(need/1024)


def _gen_one(m: dict, b: dict, img: Path) -> bool:
    """出一张图。`manifest.source` 选源（2026-09-27 补）：

    · `pollinations`（默认 · 免费）：硬顶 1024×576 + 水印 ⇒ 后面靠超采样+调色补；
    · `genoffice`（Genspark · **要积分**）：16:9 / 1k–4k / 无水印 / 支持 `--ref` 参考图 ——
      实测**当前被额度挡住**（`requires a paid plan or a credit balance of at least 500`），
      解锁后**零代码改动**即换源（只改清单里一个词）。
    走 `genoffice` 时**过它自己的门**（`filesystem_write`，闸只有一处）。
    """
    src = str(m.get("source", "pollinations")).lower()
    prompt = (f"{b['prompt']}, {b.get('angle', 'eye')} angle shot, dynamic action composition, "
              f"cinematic still, motion energy")
    if src == "genoffice":
        try:
            from gbt_allinone import api as _api                      # noqa: PLC0415
            r = _api.run_task("genoffice", {
                "op": "run",
                "args": ["image", prompt, "--out", str(img),
                         "--aspect", "16:9", "--size", str(m.get("size", "1k")), "--force"]})
            out = (r.get("result") or {}) if isinstance(r, dict) else {}
            inner = out.get("result") if isinstance(out.get("result"), dict) else out
            if inner.get("denied"):
                print(f"  ⛔ {b['id']} genoffice 被门拦下：{inner.get('gate')}（要授权）")
                return False
            ok = bool(inner.get("ok")) and img.is_file() and img.stat().st_size > 8000
            if not ok:
                print(f"  ✘ {b['id']} genoffice 未出图：{str(inner.get('out') or inner.get('error'))[:120]}")
            return ok
        except Exception as exc:                                      # noqa: BLE001
            print(f"  ✘ {b['id']} genoffice 调用失败：{type(exc).__name__}: {str(exc)[:100]}")
            return False
    seed = b.get("seed") or _stable_seed(b["id"])
    url = POLL + quote(prompt) + f"?width=1280&height=720&seed={seed}&nologo=true"
    sh(["curl", "-sL", "--max-time", "120", "-o", str(img), url], timeout=150)
    return img.is_file() and img.stat().st_size > 8000


def cmd_gen(mp: Path, only: str = "", force: bool = False) -> int:
    m, guard = load_checked(mp)
    if m is None:
        print("✘ 规格不合法，拒跑：")
        for e in guard["errors"]:
            print("   ·", e)
        return 2
    n = 0
    for b in m["beats"]:
        if only and b["id"] != only:
            continue
        img = beat_img(m, b)
        if img.is_file() and img.stat().st_size > 8000 and not force:
            continue
        img.parent.mkdir(parents=True, exist_ok=True)
        ok = _gen_one(m, b, img)
        seed = b.get("seed") or _stable_seed(b["id"])
        print(f"  {'✔' if ok else '✘'} 生成 {b['id']}（源={m.get('source', 'pollinations')}"
              f"{' seed=' + str(seed) if m.get('source', 'pollinations') == 'pollinations' else ''}）"
              f"{img.stat().st_size if img.is_file() else 0}B")
        n += 1 if ok else 0
    _autobind([beat_img(m, b) for b in m["beats"] if beat_img(m, b).is_file()], "actioncam")
    print(f"  生成 {n} 张")
    return 0


def _render_one(m: dict, b: dict) -> dict:
    img = beat_img(m, b)
    src = beat_prep(m, b) if beat_prep(m, b).is_file() else img     # 优先用超采样图
    if not src.is_file():
        return {"ok": False, "why": "缺图（先 gen）"}
    seg = beat_seg(m, b)
    seg.parent.mkdir(parents=True, exist_ok=True)
    vf, D, move = still_filter(m, b)
    r = sh(["ffmpeg", "-y", "-loop", "1", "-i", str(src), "-vf", vf,
            "-t", str(round(D / FPS, 3)), "-r", str(FPS),
            "-c:v", "libx264", "-preset", "medium", "-crf", str(quality(m)["crf"]),
            "-pix_fmt", "yuv420p", str(seg)], timeout=600)
    info = q(seg)
    ok = r.returncode == 0 and info.get("ok")
    return {"ok": ok, "dur": info.get("dur"), "err": (r.stderr or "")[-200:] if not ok else ""}


def cmd_seg(mp: Path, only: str = "") -> int:
    m, guard = load_checked(mp)
    if m is None:
        print("✘ 规格不合法，拒跑：")
        for e in guard["errors"]:
            print("   ·", e)
        return 2
    bad = 0
    # 先做超采样 prep（源图软 ⇒ 2x lanczos + cas 提锐；渲染从 prep 出发）
    for b in m["beats"]:
        if only and b["id"] != only:
            continue
        src, dst = beat_img(m, b), beat_prep(m, b)
        if not src.is_file():
            continue
        if dst.is_file() and dst.stat().st_mtime >= src.stat().st_mtime:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        sup = supersample_factor(m)
        r = sh(["ffmpeg", "-y", "-i", str(src),
                "-vf", f"scale=iw*{sup}:ih*{sup}:flags=lanczos,cas=0.4",
                "-q:v", "2", str(dst)], timeout=300)
        print(f"  {'✔' if r.returncode == 0 else '✘'} 超采样 {b['id']} → {sup}x")
    for b in m["beats"]:
        if only and b["id"] != only:
            continue
        r = _render_one(m, b)
        print(f"  {'✔' if r['ok'] else '✘'} 拍 {b['id']} [{b.get('move')}/{b.get('angle')}] "
              f"{r.get('dur', '?')}s {r.get('err', '')}")
        bad += 0 if r["ok"] else 1
    segs = [beat_seg(m, b) for b in m["beats"] if beat_seg(m, b).is_file()]
    _autobind(segs, "actioncam")
    print(f"  渲染完成 · 缺 {bad}")
    return 1 if bad else 0


def cmd_build(mp: Path, skip: list, only: list) -> int:
    m, guard = load_checked(mp)
    if m is None:
        print("✘ 规格不合法，拒跑：")
        for e in guard["errors"]:
            print("   ·", e)
        return 2
    beats = [b for b in m["beats"]
             if (not only or b["id"] in only) and b["id"] not in skip]
    missing = [b["id"] for b in beats if not beat_seg(m, b).is_file()]
    if missing:
        print(f"✘ 缺段：{missing}（先 seg）")
        return 2
    out = ROOT / m["out_dir"] / m.get("output", "actioncam.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    lst = out.parent / f"{out.stem}-concat.txt"
    qa = quality(m)
    lines = []
    for b in beats:
        s = beat_seg(m, b)
        lines.append("file '" + str(s).replace("'", "'\\''") + "'")
    lst.write_text("\n".join(lines), encoding="utf-8")

    # ── 电影级调色链（修饰工坊·科目二）——**共用件**：与 filmkit 同款配方 ──
    # ACES 式近似（AAA 手册配方）：S 曲线 → 双色调（冷阴影/暖中间调）→ 饱和 → CAS 提锐
    # → 辉光（bloom）→ 暗角 → 胶片颗粒。**零逗号表达式纪律**照旧。
    grade = _grade_chain(m.get("grade", "filmic"), qa["grain"])

    # ── 音效层（修饰工坊·科目三：完整音轨，无声片段禁入正片）──────────
    bed = _audio_bed(m, beats)
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst)]
    if bed:
        cmd += ["-i", str(bed)]
        cmd += ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    # 交付编码三必查（手册口径）：-g 按 fps 取 2 秒；-level 按分辨率（1080p→4.0 / 720p→3.1）
    cmd += ["-vf", grade, "-c:v", "libx264", "-preset", "medium",
            "-crf", str(qa["crf"]), "-g", str(int(FPS * 2)),
            "-level", "4.0" if qa["h"] >= 1080 else "3.1",
            "-pix_fmt", "yuv420p", str(out)]
    r = sh(cmd, timeout=1800)
    info = q(out)
    # 🔴 **退出码必须进判据**（2026-09-27 修同款假绿）：只看"文件在"会拿上一版旧片报 ✔，
    #    还给旧片打新指纹（filmkit 那条线就是这么骗过我的）。
    if r.returncode != 0:
        print(f"  ✘ 总装失败（rc={r.returncode}）：{(r.stderr or '').strip()[-300:]}")
        return 1
    if out.is_file():
        print(f"  ✔ 成片 {out.name} · {info.get('dur')}s · {out.stat().st_size/1048576:.1f}MB"
              f"{' · 含音轨' if bed else ' · 无音轨'}")
        # 成片指纹（关键点 7：可复现/可回归）——清单 hash + 工具 hash + 引擎版本 + seed 表
        try:
            import importlib.util
            sp = importlib.util.spec_from_file_location("specguard", ROOT / "tools" / "specguard.py")
            sg = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(sg)
            fpr = sg.fingerprint(mp, out, extra={"beats": len(beats), "audio": bool(bed)})
            print(f"  ✔ 指纹 {Path(str(fpr.get('written') or '?')).name}"
                  f" · 清单 {fpr['manifest_sha16']} · 成片 {fpr['film_sha16']}")
        except Exception as exc:                               # noqa: BLE001
            print(f"  ⚠️ 指纹未落：{exc}")
    else:
        print(f"  ✘ {r.stderr[-300:]}")
    _autobind([out, bed] if bed else [out], "actioncam")
    return 0 if info.get("ok") else 1


def _audio_bed(m: dict, beats: list) -> Path | None:
    """合成音效床（零外购素材）：雨底噪 + 低频垫 + 甩镜 whoosh + 打击帧 thump。

    - 雨：`anoisesrc` 粉噪 + 低通 6k + 高通 300（贴在耳边的雨）；
    - 垫：55Hz 正弦（动作戏的心跳低频）；
    - whoosh：白噪短促 + 快速扫频感（用带通扫不划算，改用"噪声爆发 + 淡入淡出"）；
    - thump：60Hz 正弦短衰减 + 噪声瞬态（打击帧）。
    混完过 `loudnorm`（streaming -14 LUFS，与 audio_mix 响度表同口径）。
    """
    if not m.get("audio", True):
        return None
    total = sum(float(b.get("dur", 0.8)) for b in beats)
    work = ROOT / m["work_dir"] / "audio"
    work.mkdir(parents=True, exist_ok=True)
    bed = work / "bed.wav"
    # 图层 1：雨（全片）
    rain = work / "rain.wav"
    sh(["ffmpeg", "-y", "-f", "lavfi", "-i",
        f"anoisesrc=color=pink:duration={total:.2f}:amplitude=0.06",
        "-af", "highpass=300,lowpass=6000", "-ar", "44100", str(rain)], timeout=300)
    ins = [["-i", str(rain)]]
    filters = ["[0:a]volume=0.9[r]"]
    labels = ["[r]"]
    idx = 1
    t0 = 0.0
    # 时刻口径（时间基层纪律）：声明了 bpm ⇒ **整拍计数 × beat_sec 逐拍乘法**（禁累加：
    # 800 拍累加会累出可测漂移）；没声明 ⇒ 每拍圆整的累计和兜底。
    _bpm = float(m.get("bpm") or 0)
    _beat = (60.0 / _bpm) if _bpm else 0.0
    _k = 0
    for b in beats:
        dur = float(b.get("dur", 0.8))
        if _beat:
            t0 = round(_k * _beat, 6)
            _k += max(1, int(round(dur / _beat)))
        else:
            t0 = round(t0, 6)
        mv = b.get("move", "")
        if mv in ("whip_lr", "whip_rl", "crash_zoom"):
            ins.append(["-f", "lavfi", "-t", "0.45", "-i",
                        "anoisesrc=color=white:amplitude=0.25"])
            filters.append(f"[{idx}:a]highpass=800,lowpass=4500,afade=t=in:d=0.08,"
                           f"afade=t=out:st=0.22:d=0.23,adelay={int(t0*1000)}|{int(t0*1000)}[w{idx}]")
            labels.append(f"[w{idx}]")
            idx += 1
        if mv == "impact_hold":
            ins.append(["-f", "lavfi", "-t", "0.5", "-i",
                        f"sine=frequency=58:duration=0.5:beep_factor=0"])
            filters.append(f"[{idx}:a]volume=0.9,afade=t=out:st=0.05:d=0.45,"
                           f"adelay={int(t0*1000)}|{int(t0*1000)}[t{idx}]")
            labels.append(f"[t{idx}]")
            idx += 1
        if not _beat:
            t0 += dur                # 只有没声明 bpm 时才累加（有 bpm 时上一步已按整拍乘法取值）
    filters.append("sine=frequency=55:duration=%.2f,volume=0.10,lowpass=120[d]" % total)
    labels.append("[d]")
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0[mx]")
    filters.append("[mx]loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    cmd = ["ffmpeg", "-y"]
    for i in ins:
        cmd += i
    cmd += ["-filter_complex", ";".join(filters), "-map", "[out]",
            "-ar", "44100", "-ac", "2", str(bed)]
    r = sh(cmd, timeout=600)
    if r.returncode != 0 or not bed.is_file():
        print(f"  ⚠️ 音效床合成失败（不影响画面）：{(r.stderr or '')[-160:]}")
        return None
    print(f"  ✔ 音效床 {bed.name} · {q(bed).get('dur')}s（雨 + 低频垫 + whoosh/打击，loudnorm -14 LUFS）")
    return bed


# ── 生产审计（总监令工作流第 1 步机械化）：黑帧/卡帧/亮度读数 ──────────
def cmd_qc(mp: Path, out_name: str = "") -> int:
    m = load(mp)
    film = ROOT / m["out_dir"] / (out_name or m.get("output", "actioncam.mp4"))
    if not film.is_file():
        print(f"✘ 成片不在：{film}")
        return 2
    r = sh(["ffmpeg", "-hide_banner", "-i", str(film), "-vf",
            "blackdetect=d=0.10:pix_th=0.06,freezedetect=n=-60dB:d=0.45,"
            "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
            "-f", "null", "-"], timeout=900)
    err = r.stderr or ""
    black = [x for x in err.splitlines() if "black_start" in x]
    freeze = [x for x in err.splitlines() if "freeze_start" in x]
    yavg = [float(x.split("=")[-1]) for x in err.splitlines() if "YAVG=" in x and x.split("=")[-1].strip()]
    verdict = "通过" if not black and not freeze else "不通过"
    print(f"生产审计（{film.name}）· 黑帧段 {len(black)} · 卡帧段 {len(freeze)} · "
          f"亮度均值 {min(yavg) if yavg else '?'}-{max(yavg) if yavg else '?'} ⇒ **{verdict}**")
    for x in black[:5]:
        print("   🔴 黑帧:", x.strip()[:110])
    for x in freeze[:5]:
        print("   🔴 卡帧（>0.45s 静止）:", x.strip()[:110])
    _log_qc(m, film, black, freeze, yavg, verdict)
    return 0 if verdict == "通过" else 1


def _log_qc(m: dict, film: Path, black, freeze, yavg, verdict) -> None:
    try:
        p = ROOT / "state" / "actioncam_qc.jsonl"
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "film": str(film),
               "black_segments": len(black), "freeze_segments": len(freeze),
               "yavg_min": min(yavg) if yavg else None, "yavg_max": max(yavg) if yavg else None,
               "verdict": verdict}
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def cmd_plan(mp: Path) -> int:
    m, guard = load_checked(mp)
    if m is None:
        print("✘ 规格不合法，拒跑：")
        for e in guard["errors"]:
            print("   ·", e)
        return 2
    qa = quality(m)
    total = sum(float(b.get("dur", 0.8)) for b in m["beats"])
    print(f"动作戏《{m.get('title', '?')}》 · {len(m['beats'])} 拍 · {total:.1f}s · 画质 {m.get('quality')}"
          f"（{qa['w']}x{qa['h']}@{FPS} crf{qa['crf']}）")
    for b in m["beats"]:
        img = "✔" if beat_img(m, b).is_file() else "…"
        seg = "✔" if beat_seg(m, b).is_file() else "…"
        print(f"  {img}{seg} {b['id']:6} [{b.get('move'):10}/{b.get('angle'):5}] {b.get('dur')}s  {b.get('prompt', '')[:44]}")
    return 0


def cmd_add(mp: Path, after: str, bid: str, move: str, angle: str, dur: float, prompt: str) -> int:
    m = load(mp)
    if any(b["id"] == bid for b in m["beats"]):
        print(f"已存在 {bid}")
        return 2
    if move not in MOVES:
        print(f"未知运镜 {move}（可用：{'/'.join(MOVES)}）")
        return 2
    b = {"id": bid, "move": move, "angle": angle if angle in ANGLES else "eye",
         "dur": dur, "prompt": prompt}
    idx = next((i for i, x in enumerate(m["beats"]) if x["id"] == after), len(m["beats"]) - 1)
    m["beats"].insert(idx + 1, b)
    save(mp, m)
    print(f"已插入 {bid}（{after} 之后）· {move}/{b['angle']} · {dur}s")
    return 0


def cmd_rm(mp: Path, bid: str) -> int:
    m = load(mp)
    m["beats"] = [b for b in m["beats"] if b["id"] != bid]
    save(mp, m)
    print(f"已摘除 {bid}（图与段保留，可加回）")
    return 0


def _grade_chain(spec: str = "filmic", grain: int = 6) -> str:
    """调色链走**共用外观库** `tools/filmgrade.py`（与 filmkit 同款；一条定义两线下发）。

    `spec` 支持外观名或人话（词即指令）；拍子表里写 `"grade": "热血橙青"` 即可换味。
    """
    try:
        import importlib.util
        spec_m = importlib.util.spec_from_file_location("filmgrade", ROOT / "tools" / "filmgrade.py")
        fg = importlib.util.module_from_spec(spec_m)
        spec_m.loader.exec_module(fg)
        return fg.grade_chain(spec, grain)
    except Exception:                                          # noqa: BLE001
        return ("curves=preset=medium_contrast,"
                "colorbalance=rs=-0.05:bs=0.09:rm=0.03:bm=-0.02,"
                "eq=saturation=1.08:gamma=0.97,cas=0.35,"
                "split[a][b];[b]gblur=sigma=10[bb];[a][bb]blend=all_mode=screen:all_opacity=0.10,"
                f"vignette=PI/5,noise=alls={grain}:allf=t+u")


def _autobind(paths, tentacle: str, note: str = "actioncam") -> None:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("tb", ROOT / "tools" / "tentacle_bind.py")
        tb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tb)
        for p in paths:
            try:
                tb.bind(p, tentacle, note=note, quiet=True)
            except Exception:
                pass
    except Exception:
        pass


def main(argv: list) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, mp = argv[1], ROOT / argv[2]
    if cmd == "gen":
        return cmd_gen(mp, only=argv[4] if "--beat" in argv else "",
                       force="--force" in argv)
    if cmd == "seg":
        return cmd_seg(mp, only=argv[4] if "--beat" in argv else "")
    if cmd == "build":
        skip = argv[argv.index("--skip") + 1].split(",") if "--skip" in argv else []
        only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else []
        return cmd_build(mp, skip, only)
    if cmd == "plan":
        return cmd_plan(mp)
    if cmd == "qc":
        return cmd_qc(mp, out_name=(argv[argv.index("--film") + 1] if "--film" in argv else ""))
    if cmd == "add" and "--after" in argv:
        return cmd_add(mp, argv[argv.index("--after") + 1],
                       argv[argv.index("--id") + 1],
                       argv[argv.index("--move") + 1],
                       argv[argv.index("--angle") + 1] if "--angle" in argv else "eye",
                       float(argv[argv.index("--dur") + 1]) if "--dur" in argv else 0.8,
                       argv[argv.index("--prompt") + 1] if "--prompt" in argv else "")
    if cmd == "rm" and "--beat" in argv:
        return cmd_rm(mp, argv[argv.index("--beat") + 1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
