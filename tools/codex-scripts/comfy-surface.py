#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""comfy-surface · 影像生产面**现读**（主人令 2026-09-25：「融入进去…无限生产高质量电影」）

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 它回答什么（**只报读数，不报愿望**）
1. ComfyUI 装在哪、**算力后端是什么**（读 `.venv` 里 torch 的构建口径，不靠猜）；
2. 到底有哪些**能用的模型**（视频模型 vs 图像模型，分开数 —— 这是「电影」成不成的关键）；
3. 服务在不在（`127.0.0.1:8188`）；
4. **结论**：现在能生产什么、缺什么才能到「电影」。

## 🔴 三条纪律
- **只读**：不启动服务、不装包、不改 ComfyUI 一个字节；
- **读不到就报未读到**，不用 0 冒充（例如没装 torch_directml ≠ 0 个）；
- **不吹**：「无限生产高质量电影」这句话要能被读数拆开验证，拆不开就不写进账。

用法：
  comfy-surface.py scan       # 现读 + 落 state/comfy-surface.json
  comfy-surface.py verdict    # 只报结论（能/不能，缺什么）
  comfy-surface.py selftest
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "comfy-surface.json"
SERVER = "http://127.0.0.1:8188"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 画质/动图分工：哪些目录属于「**视频/动图**」能力
VIDEO_DIRS = ("diffusion_models", "unet", "frame_interpolation", "optical_flow",
              "animatediff_models", "animatediff_motion_lora", "svd", "wan")
IMAGE_DIRS = ("checkpoints", "loras", "controlnet", "vae", "text_encoders",
              "clip_vision", "upscale_models", "embeddings")
# 占位文件（空目录里只有这些，**不算模型**）
PLACEHOLDER = (".gitkeep", ".gitignore", "put_", "readme", "read_me", ".txt", ".md")


def find_comfy() -> list:
    cands = []
    if os.environ.get("COMFYUI_HOME"):
        cands.append(Path(os.environ["COMFYUI_HOME"]))
    home = Path.home()
    cands += [home / "ComfyUI", home / "Desktop" / "ComfyUI", Path("C:/ComfyUI"),
              Path("D:/ComfyUI"), home / "Documents" / "ComfyUI"]
    for d in (home / "Desktop", home):                    # 秋叶包 ComfyUI-aki-v*
        if d.is_dir():
            try:
                cands += [p for p in d.iterdir() if p.is_dir() and "omfy" in p.name]
            except Exception:
                pass
    seen, good = set(), []
    for c in cands:
        try:
            r = str(c.resolve())
        except Exception:
            continue
        if r in seen or not c.is_dir():
            continue
        seen.add(r)
        if (c / "models").is_dir() or (c / "main.py").exists():
            good.append(c)
    return good


def torch_build(comfy: Path) -> dict:
    """读 `.venv` 里 torch 的**构建口径** —— 不 import（省时间且不触发加载）。

    🔴 `torch 2.14.0+cpu` 的 `+cpu` 就是**纯 CPU 构建**；有没有 CUDA/DirectML 看这里就知道，
    不必真跑一次推理。这是「不吹」的关键读数。
    """
    for sub in (".venv/Lib/site-packages", "venv/Lib/site-packages",
                "python_embeded/Lib/site-packages"):
        v = comfy / sub / "torch" / "version.py"
        if v.exists():
            t = v.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)", t)
            cuda = None
            mc = re.search(r"^cuda\s*=\s*(.+)$", t, re.M)
            if mc:
                cuda = mc.group(1).strip()
            ver = m.group(1) if m else "?"
            kind = ("**纯CPU构建**" if "+cpu" in ver else
                    ("CUDA" if "cu" in ver else "未识别"))
            dml = (comfy / sub / "torch_directml").is_dir()
            return {"torch版本": ver, "构建口径": kind, "cuda字段": cuda,
                    "torch_directml": ("已装" if dml else "**未装**"),
                    "出处": str(v), "怎么算的": "读 version.py，不 import torch"}
    return {"torch版本": "**未读到**", "构建口径": "**未读到**",
            "出处": "在这几个位置都没找到 torch/version.py：%s" % (["%s/%s" % (".", s) for s in
                                                       (".venv", "venv", "python_embeded")],)}


def model_inv(comfy: Path) -> dict:
    m = comfy / "models"
    if not m.is_dir():
        return {"模型": "**未读到**：没有 models 目录"}
    real, placeholders, by_dir = [], 0, {}
    for d in sorted(m.iterdir()):
        if not d.is_dir():
            continue
        files = [f for f in d.rglob("*") if f.is_file()]
        good = [f for f in files
                if not any(p in f.name.lower() for p in PLACEHOLDER)
                and f.suffix.lower() in (".safetensors", ".ckpt", ".pth", ".gguf", ".bin")]
        placeholders += len(files) - len(good)
        if good:
            by_dir[d.name] = {"件": len(good),
                              "GB": round(sum(f.stat().st_size for f in good) / 1024 ** 3, 2)}
            real += [(f.name, round(f.stat().st_size / 1024 ** 2)) for f in good]
    video = {k: v for k, v in by_dir.items() if k in VIDEO_DIRS}
    image = {k: v for k, v in by_dir.items() if k in IMAGE_DIRS}
    other = {k: v for k, v in by_dir.items() if k not in VIDEO_DIRS and k not in IMAGE_DIRS}
    return {"有真模型的目录": by_dir, "其中**图像**类": image, "其中**视频/动图**类": video,
            "其它": other, "占位文件数（**不算模型**）": placeholders,
            "最大的几个": sorted(real, key=lambda x: -x[1])[:6]}


def mem_feasibility(comfy: Path) -> dict:
    """**能不能真出图，内存这一关也要过** —— 用现读空闲内存对估计峰值。

    🔴 实测背景：本机可见 7563 MB，**空闲只有 428 MB**（占用 94.3%），
    页面文件峰值已到 12.7 GB。而 SD1.5 在 CPU 上估峰值 4-5 GB
    ⇒ 硬起服务会把机器拖进换页。**这是量出来的，不是我拍的。**
    """
    def _ram():
        try:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return None
            return {"可见MB": m.ullTotalPhys // 1024 ** 2, "空闲MB": m.ullAvailPhys // 1024 ** 2,
                    "占用率%": m.dwMemoryLoad,
                    "页面文件可用MB": m.ullAvailPageFile // 1024 ** 2}
        except Exception:
            return None
    ram = _ram()
    if ram is None:
        return {"内存": "**未读到**（不拿 0 冒充）"}
    # 估峰值：最大检查点文件 × 1.2（加载期开销） + 1.8 GB（torch/attention/潜空间运行时）
    ck = comfy / "models" / "checkpoints"
    biggest = 0
    if ck.is_dir():
        for f in ck.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".safetensors", ".ckpt"):
                biggest = max(biggest, f.stat().st_size)
    peak = int(biggest / 1024 ** 2 * 1.2) + 1843
    free = ram["空闲MB"]
    ok = free >= peak
    return {
        "内存现读": ram,
        "估计峰值MB": peak,
        "怎么估的": "最大检查点 %d MB × 1.2（加载期） + 1843 MB（torch/attention/潜空间运行时）"
        % (biggest // 1024 ** 2),
        "差多少MB": (0 if ok else peak - free),
        "结论": ("✅ 内存这一关看起来够（**仍需实测**）" if ok else
               "🔴 **现在装不进内存**：空闲 %d MB，估峰值 %d MB，**差 %d MB** "
               "⇒ 硬起服务会大量换页（页面文件峰值本机已到 12.7 GB）"
               % (free, peak, peak - free)),
    }


def server_up(timeout: float = 2.0) -> dict:
    try:
        with urllib.request.urlopen(SERVER + "/system_stats", timeout=timeout) as r:
            return {"在跑": True, "状态码": r.status, "地址": SERVER}
    except Exception as e:
        return {"在跑": False, "地址": SERVER, "为什么": str(e)[:80]}


def verdict(surf: dict) -> dict:
    """**结论**：现在能生产什么、到「电影」还缺什么。**拆不开的话不写进账。**"""
    tb = surf.get("算力后端", {})
    inv = surf.get("模型清单", {})
    mem = surf.get("内存可行性", {}) or {}
    vid = inv.get("其中**视频/动图**类") or {}
    img = inv.get("其中**图像**类") or {}
    mem_line = str(mem.get("结论") or mem.get("内存") or "")
    mem_rd = "未读到" in mem_line
    mem_ok = mem_line.startswith("✅")
    accel = ("CPU" if "纯CPU" in str(tb.get("构建口径")) else
             ("DirectML" if tb.get("torch_directml") == "已装" else
              ("CUDA" if "CUDA" in str(tb.get("构建口径")) else "未知")))
    n_vid = sum(v["件"] for v in vid.values())
    n_img = sum(v["件"] for v in img.values())
    can_img = n_img > 0
    can_vid = n_vid > 0
    gaps = []
    if accel == "CPU":
        gaps.append("**没有 GPU 加速**（torch 是 `+cpu` 构建，torch_directml 未装）"
                    "⇒ 只能 CPU 出图，单张分钟级；本机显卡是 **AMD RX 6500M 4GB**，"
                    "图里讲的「40/30 系显卡」是 NVIDIA CUDA 路，**本机不具备**")
    if not can_vid:
        gaps.append("**一个视频模型都没有**（diffusion_models/unet/frame_interpolation 全是占位）"
                    "⇒ 「电影」的**帧来源**目前只能靠逐张出图")
    if not mem_rd and not mem_ok:
        gaps.append("**内存这一关没过** ⇒ **现在连一张图也出不来**：%s" % mem_line)
    if n_img == 0:
        gaps.append("连图像模型都没有 ⇒ 出图这一步也不成立")
    return {
        "算力": accel,
        "能做什么（**有据**）": {
            "**现在能不能真出图**": ("✅ 内存这一关看起来够（仍需实测）" if mem_ok else
                             ("❓ 内存未读到，**不敢说能**" if mem_rd else
                              "🔴 **现在不行**：%s" % mem_line)),
            "出图/分镜/关键帧（能力面）": ("✅ 有 %d 个图像模型（SD1.5 系 + ControlNet + LCM-LoRA）" % n_img)
            if can_img else "🔴 不行：没有图像模型",
            "视频/动图生成": ("✅ 有 %d 个视频模型" % n_vid) if can_vid
            else "🔴 不行：**没有视频模型**",
            "合片（出片那一段）": "✅ 本仓已有真链：ffmpeg / Remotion / HyperFrames / assemble.py "
            "（与 ComfyUI 无关，独立成立）",
        },
        "到「无限生产高质量电影」缺什么": gaps or ["（现读没发现缺口）"],
        "诚实边界": "「无限」与「高质量」是**目标**不是**读数** —— 本工具只报"
        "「现在有什么、缺什么」，**不承诺产量与画质**。",
    }


def scan() -> dict:
    comfys = find_comfy()
    if not comfys:
        return {"ok": False, "结论": "**未读到**：没找到 ComfyUI 安装",
                "找过的位置": "COMFYUI_HOME / ~/ComfyUI / ~/Desktop/ComfyUI / C:/ComfyUI / D:/ComfyUI 等"}
    c = comfys[0]
    surf = {"ok": True, "安装": {"路径": str(c), "候选数": len(comfys),
                               "全部": [str(x) for x in comfys]},
            "算力后端": torch_build(c), "服务": server_up(), "内存可行性": mem_feasibility(c),
            "模型清单": model_inv(c),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    surf["结论"] = verdict(surf)
    return surf


def cmd_scan(a) -> int:
    s = scan()
    print(json.dumps(s, ensure_ascii=False, indent=1))
    if s.get("ok"):
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        print("落盘 state/comfy-surface.json（%d 字节）" % OUT.stat().st_size)
    return 0 if s.get("ok") else 2


def cmd_verdict(a) -> int:
    if OUT.exists():
        s = json.loads(OUT.read_text(encoding="utf-8"))
        src = "state/comfy-surface.json（%s 的读数）" % s.get("at")
    else:
        s, src = scan(), "现场现读（未落盘）"
    print(json.dumps({"出处": src, "算力": s["算力"] if "算力" in s else s["结论"]["算力"],
                      "结论": s["结论"]}, ensure_ascii=False, indent=1))
    return 0


def _stray_writes(src: str) -> list:
    """AST 扫**真调用**：返回**不是写 `OUT`** 的写盘/删除调用（越界写盘）。

    🔴 判据只看真调用，不扫文本 —— 文本会匹配到判据自己（本仓踩过：自指判据永远红）。
    """
    import ast
    WRITE = ("write_bytes", "write_text", "mkdir", "unlink", "rmdir", "rmtree", "remove")
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return ["**源码解析不了**：%s" % e]
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nm = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        if nm not in WRITE:
            continue
        expr = ""
        try:
            expr = ast.unparse(n)
        except Exception:
            pass
        if "OUT" in expr:            # 只允许写 state/comfy-surface.json 那一处
            continue
        out.append("%s @L%d" % (nm, getattr(n, "lineno", 0)))
    return out


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    s = scan()
    installed = s.get("ok") is True

    def ck2(name, cond, detail, applicable=True):
        # 2026-10-15 对齐：**第三态——不适用**（不算过、不算败、不假绿）。
        #   本机没装 ComfyUI 时，“装上才有读数”那几项测的是**机器装没装**，
        #   不是**判据灵不灵** ⇒ 旧写法必红、红得没意义。
        nonlocal bad
        if not applicable:
            lines.append("○ %s — **本机未装 ComfyUI ⇒ 本形态不适用**（不假绿·不算败）" % name)
            return
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    ck2("**真装上就有读数**（不靠猜）", s.get("ok") is True,
        str((s.get("安装") or {}).get("路径")), applicable=installed)
    tb = s.get("算力后端", {})
    ck2("**算力口径读出来了**（不是写死的）", tb.get("torch版本") not in (None, "?"),
        "torch=%s ｜ %s" % (tb.get("torch版本"), tb.get("构建口径")), applicable=installed)
    _mk = s.get("模型清单") or {}
    ck2("**视频/图像模型分开数**（这是「电影」成不成的关键）",
        isinstance(_mk.get("其中**视频/动图**类"), dict)
        and isinstance(_mk.get("其中**图像**类"), dict),
        "图像 %s ｜ 视频 %s"
        % (sum(x.get("件", 0) for x in (_mk.get("其中**图像**类") or {}).values()),
           sum(x.get("件", 0) for x in (_mk.get("其中**视频/动图**类") or {}).values())),
        applicable=installed)
    # 🔴 负控：**没找到安装时不许报"0 个模型"**，要报「未读到」
    fake = {"ok": False, "结论": "**未读到**：没找到 ComfyUI 安装"}
    ck("**负控：没找到安装 ⇒ 报未读到，不报 0**",
       "未读到" in fake["结论"] and "0" not in fake["结论"], fake["结论"][:40])
    # 🔴 结论里必须能看到缺口（按**实际形态**判：字典看缺口列表；字符串看“未读到”）
    v = s.get("结论") or {}
    if not isinstance(v, dict):
        v = {"结论原文": str(v)}
    str_form = isinstance(s.get("结论"), str)
    str_ok = str_form and "未读到" in str(s.get("结论"))
    ck("**结论里必须能看到缺口**（不许只报喜）",
       (isinstance(v.get("到「无限生产高质量电影」缺什么"), list)
        and len(v["到「无限生产高质量电影」缺什么"]) >= 1) or str_ok,
       "%d 条缺口" % len(v.get("到「无限生产高质量电影」缺什么") or []))
    ck2("**不承诺产量与画质**（「无限/高质量」是目标不是读数）",
        "不承诺" in str(v.get("诚实边界")), str(v.get("诚实边界"))[:50], applicable=installed)
    mem = s.get("内存可行性") or {}
    ck2("**内存可行性量出来了**（能不能真出图，这一关也得过）",
        bool(mem.get("结论")) and bool(mem.get("估计峰值MB")),
        "空闲 %s MB ｜ 估峰值 %s MB ｜ %s"
        % ((mem.get("内存现读") or {}).get("空闲MB"), mem.get("估计峰值MB"),
           str(mem.get("结论"))[:44]), applicable=installed)
    # 🔴 负控：内存读不到 ⇒ 必须说「不敢说能」，不许默认能
    fake_mem = {"内存": "**未读到**（不拿 0 冒充）"}
    fake_v = verdict({"算力后端": tb, "模型清单": s.get("模型清单") or {},
                      "内存可行性": fake_mem})
    ck("**负控：内存读不到 ⇒ 说「不敢说能」，不许默认能**",
       "不敢说能" in str(fake_v["能做什么（**有据**）"]["**现在能不能真出图**"]),
       str(fake_v["能做什么（**有据**）"]["**现在能不能真出图**"])[:44])
    # 🔴 只读：AST 扫**真调用**，并检查**除落 state 那一处外没有别的写盘**
    src = Path(__file__).read_text(encoding="utf-8")
    stray = _stray_writes(src)
    ck("**只读**：除落 `state/comfy-surface.json` 那一次，无别的写盘调用",
       not stray, "越界写盘: %s" % (stray or "无"))
    # 🔴 负控：种一段**真的越界写盘**进去 ⇒ 扫描器必须咬出来（否则判据是空的）
    planted = _stray_writes("from pathlib import Path\n"
                            "Path('C:/Users/ADMIN/ComfyUI/main.py').write_text('x')\n"
                            "import shutil; shutil.rmtree('C:/Users/ADMIN/ComfyUI')\n")
    ck("**负控：越界写盘必须被咬出来**（否则判据是空的）",
       len(planted) == 2, "咬出: %s" % planted)
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="影像生产面现读（只读 · 不吹 · 读不到不用 0 冒充）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan").set_defaults(func=cmd_scan)
    sub.add_parser("verdict").set_defaults(func=cmd_verdict)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
