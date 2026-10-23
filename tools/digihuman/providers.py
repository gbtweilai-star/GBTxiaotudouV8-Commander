# -*- coding: utf-8 -*-
"""后端注册表（模型无关层）—— Owner 2026-09-22：「蒸馏成用什么模型都能完成，而不是规定模型」。

设计：
- **契约与门是固定的**（阶段/输入输出/判据 —— 见 references/full-pipeline.md）。
- **"谁来干"是可换的**：每个后端声明自己**能干什么（caps）**、**怎么探活（probe）**、
  **命令模板（cmds）**、**代价与坑（cost/notes）**。
- 编排器只认**能力位**（`geom.generate` / `mesh.decimate` / `rig.auto` …），
  按「显式指定 → 配置顺序 → 可用性」解析出一个后端；都不行时给**人工指引**，绝不假装能跑。

新增后端只要往 `PROVIDERS` 里加一条，不需要改流水线任何阶段。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

WS = pathlib.Path(__file__).resolve().parents[2]
CFG = WS / ".digihuman/config.json"

# 能力位（阶段只认这些名字）
CAPS = {
    "geom.generate": "图/文 → 3D 网格（含初版贴图）",
    "geom.texture": "重烘/升清贴图（PBR 三件套）",
    "mesh.decimate": "减面/重拓扑（可保 UV）",
    "mesh.convert": "格式转换（glb/fbx/obj/ply）",
    "mesh.spring": "次级动力学（弹簧骨/链）",
    "skin.auto": "自动蒙皮权重",
    "rig.auto": "自动绑骨（人形）",
    "anim.make": "关键帧动画（循环）",
    # 🔴 2026-09-26 自纠："anim.retarget" 键原来写了两次，dict 字面量会静默用后者 —— 删掉重复行
    "anim.retarget": "动捕/动画库重定向",
    "expr.make": "表情/BlendShape",
    "pack.vrm": "封装标准格式（VRM 1.0 / GLB）",
    "render.shot": "棚拍渲染出图",
    "gate.check": "机检门（引用/骨架/权重/体积）",
}

# ── 后端注册表 ───────────────────────────────────────────────────────────
PROVIDERS = {
    "local": {
        "caps": ["mesh.decimate", "mesh.convert", "mesh.spring", "skin.auto", "rig.auto", "anim.make",
                 "expr.make", "pack.vrm", "render.shot", "gate.check", "anim.retarget"],
        "probe": ["python", "-c", "import numpy"],          # 本机脚本：numpy 在即可
        "auth": "无需（本机脚本）",
        "cost": "0（算力本机）",
        "notes": "本仓 tools/ 脚本：pymeshlab/trimesh/numpy。减面走 **PLY 二进制**通道（OBJ 文本会毁网格）",
        "cmds": {
            "mesh.decimate": "python tools/digihuman/qem-decimate.py \"{in}\" \"{out}\" {faces}",
            "mesh.spring": "python tools/digihuman/spring-chains.py",
            "skin.auto": "python tools/codex-scripts/autorig-skin.py",
            "anim.make": "python tools/codex-scripts/anim-make.py",
            "expr.make": "python tools/digihuman/expr-make.py",
            "anim.retarget": "python tools/digihuman/vrma-export.py \"{in}\" \"{out}\" {clip}",
            "pack.vrm": "python tools/digihuman/vrm-pack.py",
            "render.shot": "python tools/codex-scripts/shot-glb.py \"{in}\" \"{out}\" -1.5708",
            "gate.check": "python tools/digihuman/pipeline.py verify",
        },
    },
    "tripo": {
        "caps": ["geom.generate", "geom.texture", "mesh.decimate", "mesh.convert", "rig.auto"],
        "probe": ["tripo", "whoami"],
        "auth": "~/.tripo/config.json（api_key 以 tsk_ 开头；tcli_ 令牌接口不认）",
        "cost": "积分制：make=40 · decimate=30 · convert=10（非默认参数走 complex 档）",
        "notes": "decimate 上限 2 万面；**自家 rig 骨名无语义（14 关节）⇒ 不要用它的 rig**",
        "cmds": {
            "geom.generate": "tripo make \"{in}\" --then texture -o \"{out_dir}\" --json --yes --no-open",
            "geom.texture": "tripo make \"{task}\" --then \"texture:detailed,convert:gltf,texture_size=4096\" -o \"{out_dir}\"",
            "mesh.decimate": "tripo make \"{in}\" --then \"decimate:{faces},convert:gltf,texture_size=2048\" -o \"{out_dir}\"",
            "mesh.convert": "tripo make \"{task}\" --then \"convert:gltf\" -o \"{out_dir}\"",
            "rig.auto": "tripo make \"{task}\" --then \"rig\" -o \"{out_dir}\"",
        },
    },
    "meshy": {
        "caps": ["geom.generate", "geom.texture", "mesh.decimate", "rig.auto", "anim.retarget"],
        "probe": ["meshy", "--version"],
        "auth": "MESHY_API_KEY",
        "cost": "信用点制（按任务）",
        "notes": "有官方 rig+动画库；骨名需映射到 VRM Humanoid 后才算合规",
        "cmds": {"geom.generate": "meshy text-to-3d / image-to-3d --api-key $env:MESHY_API_KEY"},
    },
    "hunyuan3d": {
        "caps": ["geom.generate", "geom.texture", "mesh.decimate"],
        "probe": ["python", "-c", "import hy3dgen"],
        "auth": "本地权重（HuggingFace 下载）",
        "cost": "0（本机 GPU）",
        "notes": "需要 GPU 显存；产出无骨骼，后续接 local rig",
        "cmds": {"geom.generate": "python -m hy3dgen.shapegen + texgen"},
    },
    "comfyui": {
        "caps": ["geom.generate", "geom.texture", "rig.auto", "skin.auto", "mesh.decimate"],
        "probe": ["python", "-c", "import folder_paths"],   # 在 ComfyUI 环境里探活
        "auth": "本机 ComfyUI 目录",
        "cost": "0（本机 GPU）",
        "notes": "插件即能力：ComfyUI-SkinTokens（自动绑骨/蒙皮，**要求 Blender 4.2+ 在 PATH**）",
        "cmds": {"rig.auto": "（ComfyUI 图：SkinTokens 节点 + bpy_server 无头 Blender）"},
    },
    "blender": {
        "caps": ["mesh.decimate", "mesh.convert", "rig.auto", "skin.auto", "anim.retarget", "render.shot"],
        "probe": ["blender", "--version"],
        "auth": "无需",
        "cost": "0",
        "notes": "**保 UV 减面/重拓扑的唯一稳妥解**（Decimate Collapse）；也解 SkinTokens 的硬依赖",
        "cmds": {"mesh.decimate": "blender -b --python tools/digihuman/blender-decimate.py -- \"{in}\" \"{out}\" {faces}"},
    },
    "mixamo": {
        "caps": ["rig.auto", "anim.retarget"],
        "probe": None,                                     # 需浏览器上传，无法本机探测
        "auth": "网页登录",
        "cost": "免费",
        "notes": "需 T-pose + FBX；骨名 Mixamo 规范，映射到 VRM 即可互换动画",
        "cmds": {"rig.auto": "（人工：上传 T-pose FBX → 自动绑骨 → 下载 FBX）"},
    },
}


def _probe(provider: str):
    p = PROVIDERS[provider]
    if p.get("probe") is None:
        return None, "需人工/浏览器（无法本机探测）"
    exe = p["probe"][0]
    found = shutil.which(exe)
    if found:
        exe = found                     # ← 必须用 which 给的全路径（.CMD 裸名 subprocess 不认）
    else:
        # 允许 npm 全局命令（tripo.cmd 等）：按 %APPDATA%\npm 找
        import os
        cand = [pathlib.Path(os.environ.get("APPDATA", "")) / "npm" / f"{exe}.cmd",
                pathlib.Path(os.environ.get("APPDATA", "")) / "npm" / f"{exe}.ps1",
                pathlib.Path.home() / "AppData" / "Roaming" / "npm" / f"{exe}.cmd"]
        hit = next((c for c in cand if c.exists()), None)
        if hit is None:
            return False, f"命令不在 PATH：{exe}"
        exe = str(hit)
    try:
        argv = [exe] + list(p["probe"][1:])
        need_shell = exe.lower().endswith((".cmd", ".bat", ".ps1"))
        r = subprocess.run(" ".join(f'"{x}"' if " " in x else x for x in argv) if need_shell else argv,
                           shell=need_shell, capture_output=True, text=True,
                           timeout=30, encoding="utf-8", errors="replace")
        return (r.returncode == 0), (r.stdout or r.stderr or "").strip().splitlines()[-1][:80] if (r.stdout or r.stderr) else ""
    except Exception as e:
        return False, f"探测异常：{type(e).__name__}"


def availability():
    out = {}
    for k in PROVIDERS:
        ok, note = _probe(k)
        out[k] = {"ok": ok, "note": note, "caps": PROVIDERS[k]["caps"]}
    return out


def load_config():
    if CFG.exists():
        try:
            return json.loads(CFG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(cfg):
    CFG.parent.mkdir(parents=True, exist_ok=True)
    CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")


def resolve(cap: str, prefer: str | None = None, probe: bool = True):
    """解析某能力位用哪个后端：显式指定 → 配置 → 注册表顺序（只看可用）。"""
    order = []
    if prefer:
        order.append(prefer)
    cfg = load_config()
    if cfg.get(cap):
        order.append(cfg[cap])
    order += [k for k in PROVIDERS if k not in order]
    tried = []
    for k in order:
        if k not in PROVIDERS or cap not in PROVIDERS[k]["caps"]:
            continue
        if probe:
            ok, note = _probe(k)
            if ok is not True:
                tried.append(f"{k}({note})")
                continue
        return k, None
    return None, "无可用后端；已试：" + ("; ".join(tried) if tried else "无（该能力无后端声明）")
