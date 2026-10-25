# -*- coding: utf-8 -*-
# gbt-capability: hunyuan_video
"""混元视频（HunyuanVideo 1.5）· R-H484 **只读骨架**（图纸：docs/混元视频技能设计.md）。

定性（主人逐字）：
    · 视频能力 HunyuanVideo 1.5 = **8.3B** 参数 · **7G 显存可跑（6GB 方案）**
    · 五原语：T2V / I2V / ENHANCE / AUDIO / EXPORT
    · 能力位：`hunyuan_video`（`domain=video` · `type=internal`）
    · 部署路径：ComfyUI（v0.3.10+）**或** Wan2GP · FP8 量化权重 · **分块交换 + 8 步蒸馏** · 480p 起步再 720p

三条**带牙用例**（主人点名 · 本模块把它们做成机械闸）：
    ① **结果必须落盘**——只给远程链接 = 拒（not_landed）
    ② **显存不超限**——调用前检查（vram_exceeded）
    ③ **每次操作写 trace_store**——没带 source_kind = 拒（no_trace）

边界：**只读骨架** —— 不装 ComfyUI / 不下权重 / 不联网 / 不生成任何视频 /
      未登记能力位（未接线）。所有真正执行一律 `not_implemented`。
"""
from __future__ import annotations

import sys
from pathlib import Path

CAP_KIND = "hunyuan_video"
DOMAIN = "video"
CAP_TYPE = "internal"          # 视频域里**第一个 internal**（既有 4 个视频能力位全是 external）
SOURCE_KIND = "hunyuan_video"  # 留痕口径（每次操作写 trace_store 的 source_kind）

# 五原语（逐字）
PRIMITIVES = (
    {"name": "T2V", "cn": "文生视频", "writes": False},
    {"name": "I2V", "cn": "图生视频", "writes": False},
    {"name": "ENHANCE", "cn": "后处理超分", "writes": False},
    {"name": "AUDIO", "cn": "音频（生成/配音）", "writes": False},
    {"name": "EXPORT", "cn": "结果落盘", "writes": False},
)

# 红线（逐字要点）
RED_LINES = (
    "**结果必须落盘**（不许只留远程链接）",
    "**显存不超限**（调用前检查 —— 本机 4GB 专用 / 7833MB Display）",
    "**每次操作写 `trace_store`**（`source_kind=\"hunyuan_video\"`）",
    "不碰面板 8765 · 不碰信号环 · 不碰写路径（除产物落盘）",
)

HONEST_BOUNDARY = (
    "本模块是**只读骨架**：五原语一条都**没实现**（一律 not_implemented）；"
    "它保证的是「**三条带牙用例成了机械闸**」，不保证「能生成视频」。"
)


def must_land_on_disk(local_path: str = "", remote_url: str = "") -> dict:
    """牙①：**结果必须落盘** —— 只有远程链接、没有本地落点 ⇒ 拒。"""
    if str(local_path).strip():
        return {"ok": True, "readonly": True, "landed": str(local_path).strip()}
    return {"ok": False, "denied": True, "rule": "not_landed",
            "why": "结果必须落盘：只给远程链接不算完成（remote_url=%r）" % (remote_url or "")}


def must_vram_within(need_mb: int, reading: dict | None = None) -> dict:
    """牙②：**显存不超限** —— 调用前检查（读数取不到就**不判**，如实报）。"""
    rd = reading if isinstance(reading, dict) else gpu_vram_reading()
    avail = rd.get("dedicated_mb") or rd.get("display_mb")
    if not avail:
        return {"ok": False, "denied": True, "rule": "vram_unknown",
                "why": "显存读数取不到 ⇒ 不许当「够用」（reading=%r）" % rd}
    if int(need_mb) > int(avail):
        return {"ok": False, "denied": True, "rule": "vram_exceeded",
                "need_mb": int(need_mb), "available_mb": int(avail),
                "why": "显存不超限：本机可用 %d MB，需求 %d MB" % (int(avail), int(need_mb))}
    return {"ok": True, "readonly": True, "need_mb": int(need_mb), "available_mb": int(avail)}


def must_trace(source_kind: str = "") -> dict:
    """牙③：**每次操作留痕** —— 没有 source_kind ⇒ 拒。"""
    if str(source_kind).strip():
        return {"ok": True, "readonly": True, "source_kind": str(source_kind).strip()}
    return {"ok": False, "denied": True, "rule": "no_trace",
            "why": "每次操作写 trace_store：source_kind 不能为空"}


def gpu_vram_reading() -> dict:
    """**只读**取显卡与显存（两条路：注册表 → 失败就返回 {}；**绝不猜**）。

    为什么不用 WMI：本机实测 `Get-CimInstance Win32_VideoController` **拒绝访问**；
    `nvidia-smi` 不在 PATH（且本机是 **AMD**，本来也不适用）。
    """
    try:
        import winreg  # type: ignore
    except Exception:  # noqa: BLE001
        return {}
    key_path = (r"SYSTEM\CurrentControlSet\Control\Class"
                r"\{4d36e968-e325-11ce-bfc1-08002be10318}")
    out, best = {}, 0
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as root:
            for i in range(0, 8):
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                try:
                    with winreg.OpenKey(root, sub) as k:
                        desc = str(winreg.QueryValueEx(k, "DriverDesc")[0])
                        qw = 0
                        for name in ("HardwareInformation.qwMemorySize",
                                     "HardwareInformation.MemorySize"):
                            try:
                                qw = int(winreg.QueryValueEx(k, name)[0])
                                break
                            except OSError:
                                continue
                        mb = int(qw / (1024 * 1024)) if qw else 0
                        out[sub] = {"desc": desc, "vram_mb": mb}
                        best = max(best, mb)
                except OSError:
                    continue
    except OSError:
        return {}
    if not out:
        return {}
    return {"adapters": out, "dedicated_mb": best, "note": "注册表口径（只读）；共享内存另计"}


def check_gates(params: dict | None = None) -> dict:
    """三条带牙用例的总闸（给能力目录/面板做只读投影用）。"""
    p = dict(params or {})
    results = {
        "landed": must_land_on_disk(p.get("local_path", ""), p.get("remote_url", "")),
        "vram": must_vram_within(int(p.get("need_mb") or 0), p.get("reading")),
        "trace": must_trace(p.get("source_kind", "")),
    }
    denied = {k: v for k, v in results.items() if v.get("denied")}
    return {"ok": not denied, "readonly": True, "gates": results,
            "denied": sorted(denied), "note": "三条带牙用例：结果落盘 / 显存不超限 / 每次留痕"}


def run(op: str = "status", **params) -> dict:
    """只读入口：status / primitives / redlines / gates / gpu / plan（**执行面一律 not_implemented**）。"""
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE, "source_kind": SOURCE_KIND,
                "registerd": False, "wired": False,
                "primitives": [dict(p) for p in PRIMITIVES],
                "red_lines": list(RED_LINES), "boundary": HONEST_BOUNDARY,
                "deploy_path": ("ComfyUI v0.3.10+ **或** Wan2GP · FP8 量化权重 · "
                                "分块交换 + 8 步蒸馏 · 480p 起步再 720p（**均未装**）")}
    if op == "primitives":
        return {"ok": True, "readonly": True, "primitives": [dict(p) for p in PRIMITIVES]}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "gates":
        return check_gates(params)
    if op == "gpu":
        return {"ok": True, "readonly": True, "gpu": gpu_vram_reading()}
    if op == "plan":
        return {"ok": True, "readonly": True, "plan": [
            "① 先取证：显卡型号 / 显存（7GB 还是 8GB）/ ComfyUI 或 Wan2GP / 系统内存",
            "② 装 ComfyUI（v0.3.10+）或 Wan2GP —— **需主人单独授权出网**",
            "③ 下 FP8 量化权重（8.3B 轻量级）",
            "④ 启用分块交换 + 8 步蒸馏 · 480p 起步",
            "⑤ 过三闸：结果落盘 / 显存不超限 / 每次留痕",
        ], "not_implemented": True}
    return {"ok": False, "readonly": True, "reason": "not_implemented",
            "why": "只读骨架：执行面（T2V/I2V/ENHANCE/AUDIO/EXPORT）**一条都没实现**",
            "op": op}


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    import json
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else "status"),
                     ensure_ascii=False, indent=1))
