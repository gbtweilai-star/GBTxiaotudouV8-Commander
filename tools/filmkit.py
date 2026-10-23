# -*- coding: utf-8 -*-
"""filmkit · 柔性影片产线：清单制装配（任意段落增删重制）
⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印

设计：一切以 manifest.json 为唯一真相——
  · 场（scene）= 叙事单元（音频 + 3 个镜头 prompts）
  · 镜（shot）= 画面单元（图 + 运镜 + 时长）
任意场/镜都可单独重生成、替换、跳过、插入；重装配随时可跑。

命令：
  python tools/filmkit.py list  <manifest>                 # 全片状态表
  python tools/filmkit.py gen   <manifest> [--scene X05]    # 生成缺图（默认全部缺的）
  python tools/filmkit.py seg   <manifest> [--scene X05]    # 渲染镜头段
  python tools/filmkit.py build <manifest> [--skip X07] [--only X01,X02] [--audio-only]
  python tools/filmkit.py add   <manifest> --after X04 --id X04b --title "标题" --prompt "p1|p2|p3" [--audio 路径]
  python tools/filmkit.py rm    <manifest> --scene X07     # 从产线摘除（图保留）
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
W, H = 1280, 720
POLL = "https://image.pollinations.ai/prompt/"

MOVES = {
    "zoom_in":  lambda d: f"zoompan=z='1+{0.15/max(1,d):.7f}*on':x='iw/2-(iw/zoom/2)':y='ih*0.45-(ih/zoom/2)'",
    "zoom_out": lambda d: f"zoompan=z='1.18-{0.18/max(1,d):.7f}*on':x='iw/2-(iw/zoom/2)':y='ih*0.5-(ih/zoom/2)'",
    "pan_lr":   lambda d: f"zoompan=z='1.12':x='(iw-iw/zoom)*on/{max(1,d)}':y='ih*0.45-(ih/zoom/2)'",
    "pan_rl":   lambda d: f"zoompan=z='1.12':x='(iw-iw/zoom)*(1-on/{max(1,d)})':y='ih*0.45-(ih/zoom/2)'",
}
MOVE_CYCLE = ["zoom_in", "pan_lr", "zoom_out"]


def _grade_chain(style: str = "filmic", grain: int = 6) -> str:
    """调色链走**共用外观库** `tools/filmgrade.py`（一处定义，actioncam/filmkit 同款引用）。

    `style` 可以是**外观名**（filmic/做旧/潮湿阴冷/热血橙青/褪色胶片/黑白纪实/赛博霓虹/none），
    也可以是**人话**（说「潮湿阴冷」就取湿冷味——词即指令，见 filmgrade.INTENT_MAP）。
    清单里写 `"grade": "<外观名 或 人话>"` 即可切换；**不写 = filmic**。
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("filmgrade", ROOT / "tools" / "filmgrade.py")
        fg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fg)
        return fg.grade_chain(style, grain)
    except Exception:                                          # noqa: BLE001
        return (f"eq=saturation=1.08:gamma=0.97,cas=0.35,vignette=PI/5,"
                f"noise=alls={grain}:allf=t+u")



def _stable_seed(text: str) -> int:
    """稳定种子（与进程无关）——走共用件 `tools/specguard.py` 的 `stable_seed`。

    🔴 2026-09-27 修：原来用 `abs(hash(id))`，而 Python 的 `hash()` 对 str **每进程随机**
    ⇒ 同一镜重跑换种子 = 图变了 = 不可复现（实测两进程两值：93696526 / 22297706）。
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("specguard", ROOT / "tools" / "specguard.py")
        sg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sg)
        return sg.stable_seed(text, mod=99999)
    except Exception:                                          # noqa: BLE001
        import hashlib
        return int(hashlib.sha256(("gbt-seed:" + text).encode("utf-8")).hexdigest()[:12], 16) % 99999


def load(mp: Path) -> dict:
    return json.loads(mp.read_text(encoding="utf-8"))


def save(mp: Path, m: dict) -> None:
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def sh(cmd, timeout=900):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, cwd=str(ROOT))


def dur(p: Path) -> float:
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(p)], timeout=60)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def scene_dirs(m: dict) -> tuple[Path, Path]:
    work = ROOT / m["work_dir"]
    out = ROOT / m["out_dir"]
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    return work, out


def img_path(m: dict, sc: dict, shot: dict) -> Path:
    work, _ = scene_dirs(m)
    return work / f"{shot['id']}.jpg"


def seg_path(m: dict, shot_id: str) -> Path:
    work, _ = scene_dirs(m)
    return work / f"{shot_id}.mp4"


def scene_audio(m: dict, sc: dict) -> Path | None:
    if not sc.get("audio"):
        return None
    p = ROOT / sc["audio"]
    return p if p.is_file() else None


# ── gen：生成缺图（flux）──────────────────────────────────────────────
def cmd_gen(mp: Path, only_scene: str = "", force: bool = False) -> int:
    m = load(mp)
    from scrapling import Fetcher
    f = Fetcher(auto_match=False)
    todo = []
    for sc in m["scenes"]:
        if only_scene and sc["id"] != only_scene:
            continue
        for i, shot in enumerate(sc["shots"]):
            p = img_path(m, sc, shot)
            if force or not (p.is_file() and p.stat().st_size > 8000):
                todo.append((sc, shot, p, i))
    print(f"待生成 {len(todo)} 张")
    ok = 0
    for sc, shot, p, i in todo:
        pr = shot.get("prompt") or sc.get("prompts", [""] * 3)[i] or sc.get("title", "")
        url = (POLL + quote(pr + m.get("style_suffix", ", cinematic, film grain")) +
               f"?width={W}&height={H}&nologo=true&model=flux&seed={_stable_seed(shot['id'])}")
        for attempt in range(3):
            try:
                r = f.get(url, timeout=180)
                body = r.body if isinstance(r.body, bytes) else str(r.body or "").encode("utf-8", "replace")
                if len(body) > 8000:
                    p.write_bytes(body)
                    ok += 1
                    print(f"  OK {shot['id']} {len(body)//1024}KB")
                    break
            except Exception as e:                             # noqa: BLE001
                print(f"  retry {shot['id']} {attempt} {type(e).__name__}")
                time.sleep(4)
        else:
            print(f"  FAIL {shot['id']}")
    print(f"完成 {ok}/{len(todo)}")
    _autobind([str(p) for _, _, p, _ in todo], "image_gen", "filmkit:gen")
    return 0 if ok == len(todo) else 1


# ── seg：渲染镜头段（按音频时长三镜均分）────────────────────────────────
def cmd_seg(mp: Path, only_scene: str = "") -> int:
    m = load(mp)
    ok = miss = 0
    for sc in m["scenes"]:
        if only_scene and sc["id"] != only_scene:
            continue
        aud = scene_audio(m, sc)
        if aud is None and sc.get("require_audio", True):
            print(f"  skip {sc['id']}（无音频 {sc.get('audio')}）")
            miss += 1
            continue
        total = (dur(aud) if aud else float(sc.get("dur", 12))) + 0.8
        per = total / max(1, len(sc["shots"]))
        d = int(per * FPS)
        for i, shot in enumerate(sc["shots"]):
            img = img_path(m, sc, shot)
            if not (img.is_file() and img.stat().st_size > 8000):
                print(f"  skip {shot['id']}（无图）")
                miss += 1
                continue
            seg = seg_path(m, shot["id"])
            move = MOVES.get(shot.get("move") or MOVE_CYCLE[i % 3], MOVES["zoom_in"])(d)
            r = sh(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS),
                    "-i", str(img), "-filter_complex",
                    # 超采样（2026-09-27 修饰推进）：源图 1024×576 直接拉 1280×720 = 软；
                    # 先 3x lanczos + cas 提锐再 zoompan，出真细节（与 actioncam 同款口径）。
                    f"[0:v]scale={W*3}:-2:flags=lanczos,cas=0.4,"
                    f"{move}:d={d}:s={W}x{H}:fps={FPS},noise=alls=5:allf=t[v]",
                    "-map", "[v]", "-t", f"{per:.2f}", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "18", "-pix_fmt", "yuv420p", str(seg)])
            if seg.is_file() and seg.stat().st_size > 30000:
                ok += 1
                print(f"  ✔ {shot['id']} {per:.1f}s")
            else:
                miss += 1
                print(f"  ✘ {shot['id']} {r.stderr.strip()[:120]}")
    print(f"段渲染 {ok} 成 / {miss} 缺")
    _autobind([str(seg_path(m, s["id"])) for sc in m["scenes"] for s in sc["shots"]],
              "filmkit", "filmkit:seg")
    return 0 if miss == 0 else 1


# ── build：拼接 + 音频 + 终渲染 ────────────────────────────────────────
def cmd_build(mp: Path, skip: list, only: list, audio_only: bool = False) -> int:
    m = load(mp)
    # 规格守卫（fail-fast）：坏清单不许开跑（依据《单句成片》架构「参数下沉=强契约」）
    try:
        import importlib.util
        sg_spec = importlib.util.spec_from_file_location("specguard", ROOT / "tools" / "specguard.py")
        sg = importlib.util.module_from_spec(sg_spec)
        sg_spec.loader.exec_module(sg)
        v = sg.validate_manifest(m, kind="filmkit")
        if not v["ok"]:
            print("✘ 规格不合法，拒跑：")
            for e in v["errors"]:
                print("   ·", e)
            return 2
    except Exception:                                          # noqa: BLE001
        pass
    work, out = scene_dirs(m)
    segs, auds = [], []
    for sc in m["scenes"]:
        sid = sc["id"]
        if only and sid not in only:
            continue
        if sid in skip:
            continue
        shot_segs = [seg_path(m, sh_) for sh_ in [s["id"] for s in sc["shots"]] if seg_path(m, sh_).is_file()]
        if len(shot_segs) < len(sc["shots"]):
            print(f"  ⚠ {sid} 镜头不全（{len(shot_segs)}/{len(sc['shots'])}）——跳过（先 seg）")
            continue
        segs.extend(shot_segs)
        aud = scene_audio(m, sc)
        if aud:
            auds.append(aud)
    if not segs:
        print("无可拼段"); return 2
    lst = work / "shots.txt"
    lst.write_text("\n".join(f"file '{p.as_posix()}'" for p in segs), encoding="utf-8")
    total = sum(dur(p) for p in segs)
    alist = work / "audio.txt"
    alist.write_text("\n".join(f"file '{p.as_posix()}'" for p in auds), encoding="utf-8")
    out_audio = work / "film_audio.m4a"
    if auds:
        sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
            "-i", str(alist), "-c:a", "aac", "-b:a", "160k", str(out_audio)])
    final = out / m.get("output", "film.mp4")
    if audio_only:
        print("音轨就绪:", out_audio); return 0
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-f", "lavfi", "-i", f"gradients=s={W}x{H}:c0=0x1a2a33:c1=0x0a1218:c2=0x33221a:c3=0x101c26:duration={int(total)+2}:speed=0.07"]
    # 🔴 标签前**不许有逗号**：`f1,f2[v0]` 合法，`f1,f2,[v0]` = **空滤镜** ⇒ `No such filter: ''`
    #    （2026-09-27 实测：我加了 `,[v0]` 就把总装打挂，而 build 当时不查退出码 ⇒ **假绿两连**）。
    fc = ("[0:v]" + _grade_chain(m.get("grade", "filmic")).rstrip(",") + "[v0];"
          "[1:v]format=rgba,colorchannelmixer=aa=0.16[fg];[v0][fg]overlay=shortest=1[v]")
    maps = ["-map", "[v]"]
    if auds:
        cmd += ["-i", str(out_audio)]
        fc += ";[2:a]apad[aout]"
        maps += ["-map", "[aout]"]
        cmd += ["-shortest"]
    cmd += [# 交付编码三必查（手册口径）：-g 按 fps 取 2 秒（25fps→50）；-level 按分辨率给（720p→3.1）
    "-filter_complex", fc, *maps, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
    "-g", str(int(FPS * 2)), "-level", "3.1",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final)]
    r = sh(cmd, timeout=1800)
    # 🔴 **退出码必须进判据**（2026-09-27 修假绿）：原来只看"文件在且>1MB"，
    #    ffmpeg 失败时会**拿上一版旧片当新片报 ✔**，甚至还给旧片打新指纹。
    if r.returncode != 0:
        print(f"✘ 总装失败（rc={r.returncode}）：{(r.stderr or '').strip()[-400:]}")
        return 1
    ok = final.is_file() and final.stat().st_size > 1_000_000
    print(f"{'✔' if ok else '✘'} {final.name} {round(final.stat().st_size/1048576,1) if ok else 0}MB "
          f"{'· ' + str(round(dur(final),1)) + 's / ' + str(len(segs)) + ' 镜' if ok else r.stderr.strip()[:160]}")
    if ok:
        # 成片指纹（可复现/可回归）——与 actioncam 同款共用件
        try:
            sg_spec2 = importlib.util.spec_from_file_location("specguard", ROOT / "tools" / "specguard.py")
            sg2 = importlib.util.module_from_spec(sg_spec2)
            sg_spec2.loader.exec_module(sg2)
            fpr = sg2.fingerprint(mp, final, extra={"scenes": len(m["scenes"]),
                                                    "grade": m.get("grade", "filmic")})
            print(f"   ✔ 指纹 {Path(str(fpr.get('written') or '?')).name} · 清单 {fpr['manifest_sha16']}")
        except Exception as exc:                               # noqa: BLE001
            print(f"   ⚠️ 指纹未落：{exc}")
    _autobind([final], "filmkit")
    return 0 if ok else 1


# ── list：状态表 ───────────────────────────────────────────────────────
def cmd_list(mp: Path) -> int:
    m = load(mp)
    print(f"影片：{m.get('title', m.get('film'))}  共 {len(m['scenes'])} 场")
    for sc in m["scenes"]:
        imgs = sum(1 for s in sc["shots"] if (p := img_path(m, sc, s)).is_file() and p.stat().st_size > 8000)
        segs = sum(1 for s in sc["shots"] if seg_path(m, s["id"]).is_file())
        aud = scene_audio(m, sc)
        ad = f"{dur(aud):.1f}s" if aud else "无音频"
        flag = "✔" if (imgs == len(sc["shots"]) and segs == len(sc["shots"]) and aud) else "…"
        print(f"  {flag} {sc['id']:5} {sc.get('title','')[:18]:20} 图 {imgs}/{len(sc['shots'])} · 段 {segs}/{len(sc['shots'])} · {ad}")
    out = ROOT / m["out_dir"] / m.get("output", "film.mp4")
    print(f"成片：{'✔ ' + str(round(out.stat().st_size/1048576,1)) + 'MB' if out.is_file() else '（未构建）'}  {out}")
    return 0


# ── add / rm：段落增删 ─────────────────────────────────────────────────
def cmd_add(mp: Path, after: str, sid: str, title: str, prompt: str, audio: str, move: str) -> int:
    m = load(mp)
    if any(sc["id"] == sid for sc in m["scenes"]):
        print(f"已存在 {sid}"); return 2
    prompts = [p.strip() for p in prompt.split("|") if p.strip()]
    if not prompts:
        print("需要 --prompt \"镜1|镜2|镜3\""); return 2
    moves = [move] * len(prompts) if move else [MOVE_CYCLE[i % 3] for i in range(len(prompts))]
    sc = {"id": sid, "title": title or sid, "audio": audio,
          "shots": [{"id": f"{sid}_s{i+1}", "prompt": pr, "move": mv}
                    for i, (pr, mv) in enumerate(zip(prompts, moves))]}
    idx = next((i for i, s in enumerate(m["scenes"]) if s["id"] == after), len(m["scenes"]) - 1)
    m["scenes"].insert(idx + 1, sc)
    save(mp, m)
    print(f"已插入 {sid}（{after} 之后）· {len(prompts)} 镜 · 音频 {audio or '（无）'}")
    return 0


def cmd_rm(mp: Path, sid: str) -> int:
    m = load(mp)
    before = len(m["scenes"])
    m["scenes"] = [s for s in m["scenes"] if s["id"] != sid]
    if len(m["scenes"]) == before:
        print(f"没有 {sid}"); return 2
    save(mp, m)
    print(f"已摘除 {sid}（图与段文件保留，可加回）· 现 {len(m['scenes'])} 场")
    return 0


def _autobind(paths, tentacle: str, note: str = "filmkit") -> None:
    """产出即绑定：每个新资产自动连到触手（主人令：穿透式连接，新增自动补绑）。"""
    try:
        from pathlib import Path as _P
        import importlib.util as _iu
        spec = _iu.spec_from_file_location("tentacle_bind", _P(__file__).with_name("tentacle_bind.py"))
        mod = _iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for p in paths:
            if _P(p).is_file():
                mod.bind(str(p), tentacle, note=note, quiet=True)
    except Exception:                                          # noqa: BLE001
        pass                                                   # 绑定失败不许打断产出


def main(argv: list) -> int:
    if len(argv) < 3:
        print(__doc__); return 2
    cmd, mp = argv[1], Path(argv[2])
    if not mp.is_file():
        print(f"清单不存在: {mp}"); return 2
    opts = argv[3:]
    def opt(name, default=""):
        return opts[opts.index(name) + 1] if name in opts and opts.index(name) + 1 < len(opts) else default
    if cmd == "list":
        return cmd_list(mp)
    if cmd == "gen":
        return cmd_gen(mp, only_scene=opt("--scene"), force="--force" in opts)
    if cmd == "seg":
        return cmd_seg(mp, only_scene=opt("--scene"))
    if cmd == "build":
        skip = [s for s in opt("--skip").split(",") if s]
        only = [s for s in opt("--only").split(",") if s]
        return cmd_build(mp, skip, only, audio_only="--audio-only" in opts)
    if cmd == "add":
        return cmd_add(mp, opt("--after"), opt("--id"), opt("--title"), opt("--prompt"),
                       opt("--audio"), opt("--move"))
    if cmd == "rm":
        return cmd_rm(mp, opt("--scene"))
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
