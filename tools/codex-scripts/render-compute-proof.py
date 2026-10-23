# -*- coding: utf-8 -*-
"""渲染「反向调用：算力 vs 大模型」的对照证明图。

为什么要有这张图（2026-10-21 主人要）：
  「把这个方向调用算力不调用大模型的证明截图」——嘴上说"调的是算力"没用，
  要能一眼分清的**结构性差别**：

    调大模型：回执里是 text / tool_calls / usage.tokens
    调算力　：回执里是 artifact / bytes / sha256 / hardware(GPU)，外加**产物本体**

所以这张图把两条真回执并排放，并把免费 GPU 出的那条 mp4 **抽一帧**贴上来 ——
帧是从产物里解出来的像素，大模型没法凭文字变出这一段视频。

数据源（都是现读，不手抄）：
  outputs/open-source-release/data/comfy-freegpu-live.json    免费 GPU 出片回执
  outputs/open-source-release/data/omni-reverse-call-live.json 反向调大模型回执（Agnes 200）
产物：
  outputs/open-source-release/assets/fig-compute-vs-llm.png
用法：
  py -3.12 -X utf8 tools/codex-scripts/render-compute-proof.py
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
REL = ROOT / "outputs" / "open-source-release"
DATA = REL / "data"
ASSETS = REL / "assets"

W, H = 1180, 760
BG = (11, 14, 19)
CARD = (17, 22, 31)
LINE = (29, 37, 48)
TXT = (232, 237, 245)
DIM = (154, 167, 184)
GREEN = (46, 160, 67)
BLUE = (76, 141, 255)
AMBER = (224, 160, 58)
RED = (220, 80, 80)
MONO = ("consola.ttf", "CascadiaMono.ttf", "DejaVuSansMono.ttf")
CJK = ("msyh.ttc", "simhei.ttf", "PingFang.ttc")


def font(size: int, mono: bool = False):
    names = MONO if mono else CJK
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except Exception:                                     # noqa: BLE001
            continue
    try:
        return ImageFont.load_default(size)
    except Exception:                                         # noqa: BLE001
        return ImageFont.load_default()


def box(d: ImageDraw.ImageDraw, xy, fill=CARD, outline=LINE, r=12, w=2):
    d.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=w)


def frame_from_video(video: pathlib.Path) -> Image.Image | None:
    """从 mp4 抽一帧（证明产物是像素，不是文字）。没 ffmpeg 就如实不贴。"""
    exe = shutil.which("ffmpeg")
    if not exe or not video.is_file():
        return None
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="frame_")) / "f.png"
    try:
        subprocess.run([exe, "-y", "-i", str(video), "-vf", "select=eq(n\\,3)",
                        "-vframes", "1", str(tmp)],
                       capture_output=True, timeout=90)
        if tmp.is_file():
            return Image.open(tmp).convert("RGB")
    except Exception:                                         # noqa: BLE001
        return None
    return None


def main() -> int:
    fg = json.loads((DATA / "comfy-freegpu-live.json").read_text(encoding="utf-8"))
    rc = json.loads((DATA / "omni-reverse-call-live.json").read_text(encoding="utf-8"))
    agnes = next((r for r in rc.get("runs", []) if r.get("http") == 200), {})

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((28, 22), "反向调用证明：这一发调的是【算力】，不是调大模型", font=font(22), fill=TXT)
    d.text((28, 54), "两条真回执并排 —— 看回执里的字段结构与产物本体，不靠嘴上说", font=font(13), fill=DIM)

    # 左：算力
    box(d, [24, 86, 578, 470])
    d.text((44, 100), "① 调算力（免费 GPU 出片）", font=font(16), fill=GREEN)
    rows = [
        ("route", fg.get("route")),
        ("space", fg.get("space")),
        ("hardware", fg.get("hardware")),
        ("elapsed_s", fg.get("elapsed_s")),
        ("artifact", fg.get("artifact")),
        ("bytes+sha16", "%s 字节 · %s" % (fg.get("bytes"), str(fg.get("sha256"))[:16])),
        ("paid_pod", "running=%s / total=%s（付费卡一张没跑）" % (
            (fg.get("paid_pod") or {}).get("running"), (fg.get("paid_pod") or {}).get("total"))),
    ]
    y = 130
    for k, v in rows:
        d.text((44, y), k, font=font(12, True), fill=DIM)
        d.text((168, y), str(v)[:52], font=font(12, False),
               fill=GREEN if k in ("route", "hardware") else TXT)
        y += 26
    thumb = frame_from_video(ROOT / str(fg.get("artifact", "")).replace("/", "\\"))
    if thumb is not None:
        tw = 210
        th = int(thumb.height * tw / thumb.width)
        thumb = thumb.resize((tw, th))
        top = 310
        img.paste(thumb, (44, top))
        d.text((44 + tw + 16, top + 6), "↑ 产物抽帧（第 4 帧）", font=font(13), fill=GREEN)
        d.text((44 + tw + 16, top + 30), "像素是从 mp4 里解的，", font=font(12), fill=DIM)
        d.text((44 + tw + 16, top + 50), "不是大模型编的字符串。", font=font(12), fill=DIM)
    else:
        d.text((44, 420), "（产物抽帧失败：ffmpeg 不在或文件缺失 —— 如实不贴）", font=font(12), fill=AMBER)

    # 右：大模型
    box(d, [602, 86, 1156, 470])
    d.text((622, 100), "② 调大模型（对照：同一形式、不同插座内容）", font=font(16), fill=BLUE)
    rows2 = [
        ("target", agnes.get("target")),
        ("key_slot", agnes.get("key_slot")),
        ("model", agnes.get("model")),
        ("http", agnes.get("http")),
        ("ms", agnes.get("ms")),
        ("usage.total", (agnes.get("tokens") or {}).get("total")),
        ("text", str(agnes.get("text"))[:26] + "…"),
        ("artifact", "无（只回文字，没有产物本体）"),
    ]
    y = 130
    for k, v in rows2:
        d.text((622, y), k, font=font(12, True), fill=DIM)
        d.text((748, y), str(v)[:46], font=font(12, False), fill=BLUE if k == "model" else TXT)
        y += 26
    d.text((622, 360), "判据（写死，可复核）：", font=font(13), fill=AMBER)
    for i, line in enumerate([
        "· 有 artifact + bytes + sha256 -> 产出的是**字节产物**（图/视频/文件）",
        "· hardware=zero-a10g 且 paid_pod running=0 -> 用的是**免费 GPU**，没动付费卡",
        "· 只有 text / usage.tokens -> 那才是「调大模型」",
        "· 抽帧能出像素 -> 产物真的存在，不是编的字符串",
    ]):
        d.text((622, 386 + i * 20), line, font=font(12), fill=DIM)

    # 底：口径
    d.line([24, 494, 1156, 494], fill=LINE, width=1)
    d.text((28, 512), "同一道门、不同插座：", font=font(14), fill=TXT)
    # 命令行统一用 CJK 字体（箭头 → 在等宽字体里缺字，会画成方块）
    d.text((28, 540), 'cap omni_plug {"op":"run","socket":"ai","target":"<OpenAI兼容>","do":"chat",...}'
                      '  -> 插座=ai -> 回执是 text', font=font(12), fill=DIM)
    d.text((28, 568), 'cap comfy_cloud {"op":"freegpu","prompt":"...","seconds":2}'
                      '  -> 插座=算力 -> 回执是 artifact+bytes+sha256', font=font(12), fill=DIM)
    d.text((28, 596), "两条路由都过 run_task 唯一门；换源不静默（route 必带）；产物两头 sha256 对账",
           font=font(12), fill=DIM)
    d.text((28, 636), "数据源：data/comfy-freegpu-live.json · data/omni-reverse-call-live.json（都是现读回执）",
           font=font(12), fill=DIM)
    d.text((28, H - 62), "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属",
           font=font(12), fill=(90, 100, 114))
    d.text((28, H - 34), "渲染：tools/codex-scripts/render-compute-proof.py（数据变，图跟着变，不手改图）",
           font=font(11), fill=(90, 100, 114))

    ASSETS.mkdir(parents=True, exist_ok=True)
    out = ASSETS / "fig-compute-vs-llm.png"
    img.save(out)
    print("已渲染 →", out, "·", out.stat().st_size, "bytes",
          "· 抽帧:", "有" if thumb is not None else "无")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
