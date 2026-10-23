# gbt-capability: offload_distill
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""offload_distill —— **内存墙蒸馏件**（把 Edge0 的思路翻成我们自己的运行纪律 + **触手映射**）。

## 来历（主人令：「这才是我们需要蒸馏提炼的核心思路了」+「这个配合我们的触手连接就是无敌」）

上游 **`Edge0-AI/Edge0`**（★4612 · **Apache-2.0** · 4.2 MB · 自带论文 `arXiv 2609.18063`）——
题眼一句话：**《内存墙的另一半：用训练好的路由预判从 SSD 服务 35B MoE》**。
它做到「35B 只吃 ~2.5 GB 内存」。**本件不搬它的代码，只把它的思路蒸成我们的口径。**

## 四条机制 → 我们的话（原文在 `mechanism` 里逐条给）

① **权重离芯**：专家权重按需从 SSD 流式读 ⇒ **峰值内存由"激活集"决定，不由参数量决定**。
② **槽位 + LRU + 双缓冲**：固定 slot + 溢出零槽；路由索引**不出 GPU**（每层每步零主机同步）；
   重复集合不重建图。
③ **prerouter 跨 token 预判**：小头**提前一步**预测下一层在下一 token 要哪些专家 ⇒
   装载与前向**重叠**（实测吞吐**最高 +59%**），槽位**永远提前就绪 ⇒ 零丢弃**。
④ **Recover-LoRA**：冻结 int4 基模，**FP teacher 蒸馏**训 LoRA 补回量化损失；**适配器不合并**
   ⇒ 一份只读基模服务多套适配器。

## 🔴 触手映射（主人要的那一层）—— 一句话：

    **触手不该把整座仓搬回家，只把"这一步要用的那一块"拿进来；下一块提前预判、并行取。**

| 它的机制 | 触手语言 |
|---|---|
| mmap 懒读（按需拿字节区间） | 触手**按需伸手**，不预占 |
| 固定 slot + LRU | 触手手上的**停车位**与**肌肉记忆**（常用的留手上） |
| prerouter 提前一步预测 | 触手的**预判神经** —— 我们"先看再动"那条铁律的机器版 |
| IO 与前向重叠 | 一根触手取、另一根算，**不等** |
| Recover-LoRA 不合并 | 一套底座 + **多套岗位技能**（正对"每根触手一个职业"） |

## 铁律

1. **只蒸思路 · 不搬它的代码**（Apache-2.0 允许学，但我们的产物是自己的口径）。
2. **只读上游 · 零执行**：不装它的依赖、不跑它、不下载 23 GB 权重。
3. **边界不许说反**：本机是 **Windows/AMD + torch CPU**，它的 Python 路线是 **Apple Silicon + MLX**
   ⇒ **本机跑不了那条**；Windows 那条是 **C++ + Vulkan**（要单独编译 + 23 GB 权重）。**本件不假装能跑。**
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_UP = _ROOT / "_upstream" / "Edge0"
_OPS = ("status", "where", "mechanism", "map", "probe")

_UPSTREAM = {"repo": "Edge0-AI/Edge0", "stars": 4612, "license": "Apache-2.0",
             "paper": "arXiv 2609.18063 · The Other Half of the Memory Wall: "
                      "Serving 35B MoEs from SSD with Trained Routing Prediction",
             "claim": "35B MoE 跑在 ~2.5 GB 内存"}

# 四条机制：**原文**（引上游文档）+ **我们的话** + **对我们的用处** + **判据**
_MECH = (
    {
        "n": 1, "name": "权重离芯（SSD 流式 + mmap 懒读）", "src": "docs/streaming.md",
        "原文": "keep the weights on SSD, mmap them into the GPU on demand … "
                "峰值内存由**激活**专家集而非参数量决定",
        "我们的话": "**把家底放盘上，一次只把这一步要用的那一块搬进内存**；峰值常驻 = 激活集，不是总参数。",
        "用处": "直打我们要的『内存压到极致、人手一个』——7B fp16 约 15 GB 能被切成『一次一层』。",
        "判据": "峰值常驻内存 ≤ 激活集 × 单块大小（**不是**总参数量）；且读进来的字节可追到具体 tensor 名。",
    },
    {
        "n": 2, "name": "槽位 + LRU + 双缓冲（staged）", "src": "docs/streaming.md",
        "原文": "fixed slots + overflow zero slot；『indices never leave the GPU』"
                "（zero host synchronization per layer per step）；`asm_cache` 免得重复集合重建图",
        "我们的话": "**给搬进来的块配固定停车位**；常用块留在手上（LRU）；同一组块再来时不重建流水线。",
        "用处": "把『每步搬几十 MB』变成『几乎不搬』——省的不只是内存，是**每步的抖动**。",
        "判据": "每步**主机同步次数 = 0**；同一专家集二次到来时不重建执行图；未就绪要能**退回**稳妥路。",
    },
    {
        "n": 3, "name": "prerouter 跨 token 预判（IO 与计算重叠）", "src": "docs/prerouter.md",
        "原文": "a small per-layer network predicts the routing **one token ahead** …"
                "装载与前向重叠；解码吞吐**最高 +59%**；`staged_replace` ⇒ **零丢弃**",
        "我们的话": "**先用小代价预判下一步要什么，提前取进来；取和算并行，不等**。",
        "用处": "这条是**触手化**的关键：把『等 IO』变成『一边取一边算』。",
        "判据": "墙钟 ≈ max(取, 算) 而**不是**取 + 算；预判命中率与丢弃数都要有读数。",
    },
    {
        "n": 4, "name": "Recover-LoRA（压得狠 + 小适配器补回）", "src": "README_zh.md · docs/moe.md",
        "原文": "冻结 int4 基模，用 FP teacher **蒸馏**训练 LoRA 恢复量化损失；"
                "**适配器不合并**，一份只读基模服务多套适配器",
        "我们的话": "**底座压到 int4，再用蒸馏出的小 LoRA 把质量补回来**；而且适配器**不焊死在底座上**。",
        "用处": "我们本来就在做 LoRA（模型卡：rank16 → 合并全权重）——**换成『不合并』就能一套底座服务多种岗位**。",
        "判据": "同底座多适配器可**热切**；量化前后**都要有读数**（退化必须看得见）。",
    },
)

# 触手映射（主人要的那一层）
_MAP = (
    ("一句话", "触手不该把整座仓搬回家，只把**这一步要用的那一块**拿进来；下一块**提前预判、并行取**。"),
    ("mmap 懒读", "触手**按需伸手**，不预占"),
    ("固定 slot + LRU", "触手手上的**停车位**与**肌肉记忆**（常用的留手上）"),
    ("prerouter 预判", "触手的**预判神经** —— 我们『先看再动』那条铁律的机器版"),
    ("IO 与前向重叠", "一根触手取、另一根算，**不等**"),
    ("Recover-LoRA 不合并", "一套底座 + **多套岗位技能**（正对『每根触手一个职业』）"),
)


def _ram() -> dict:
    """现读本机内存（**只读 API，不起进程**）。Windows 走 GlobalMemoryStatusEx，其余尽力而为。"""
    try:
        import ctypes

        class _M(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = _M()
        m.dwLength = ctypes.sizeof(_M)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            g = 1024 ** 3
            return {"total_gb": round(m.ullTotalPhys / g, 2), "free_gb": round(m.ullAvailPhys / g, 2),
                    "load_pct": int(m.dwMemoryLoad)}
    except Exception as e:                                   # noqa: BLE001
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}
    return {}


def probe(**_kw) -> dict:
    """**本机就绪面**（只读现读）：内存 / 磁盘 / 工具面 → **逐条路线给能不能走**（不许含糊）。"""
    import platform
    tools = {t: (shutil.which(t) or "") for t in
             ("ollama", "llama-cli", "llama-server", "vulkaninfo", "cmake", "cl", "g++", "node")}
    du = shutil.disk_usage(str(_ROOT))
    free_gb = round(du.free / (1024 ** 3), 1)
    mac_arm = (platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64"))
    routes = [
        {"路": "Python（上游主力路线）", "要求": "macOS + Apple Silicon + MLX",
         "本机": ("%s/%s" % (platform.system(), platform.machine())),
         "能走": bool(mac_arm),
         "为什么不能": "" if mac_arm else "它的 Python 路线绑 MLX（Apple Silicon 专用）⇒ **本机跑不了这条**"},
        {"路": "Windows 引擎（C++ + Vulkan）", "要求": "Vulkan 运行时 + C++ 工具链 + ~23 GB 磁盘",
         "本机": {"vulkaninfo": bool(tools["vulkaninfo"]), "cmake": bool(tools["cmake"]),
                  "cl": bool(tools["cl"]), "g++": bool(tools["g++"]), "free_disk_gb": free_gb},
         "能走": bool(tools["vulkaninfo"] and (tools["cl"] or tools["g++"]) and free_gb > 25),
         "为什么不能": ("工具面/磁盘不齐（要 prove 时再逐个现读）")},
    ]
    return {"ok": True, "op": "probe", "kind": "offload_distill",
            "platform": "%s/%s" % (platform.system(), platform.machine()),
            "python": platform.python_version(), "ram": _ram(), "disk_free_gb": free_gb,
            "tools": tools, "routes": routes,
            "_口径": "**只读探针**：只用 `shutil.which` 与系统只读 API，**不起任何进程、不下载权重**；"
                     "『能走』= 三件硬条件齐；**不齐就如实说不齐**（不许拿'应该可以'顶替）"}


def status(**_kw) -> dict:
    return {"ok": True, "op": "status", "kind": "offload_distill", "ops": list(_OPS),
            "上游": dict(_UPSTREAM), "在上游盘上": _UP.is_dir(),
            "蒸馏条目": [{"n": m["n"], "机制": m["name"], "出处": m["src"]} for m in _MECH],
            "触手映射条数": len(_MAP),
            "本机": probe()["platform"],
            "_口径": "**只蒸思路 · 不搬代码 · 零执行**；本机（Windows/AMD）跑不了上游的 MLX 路线，"
                     "Windows/Vulkan 那条要单独编译 + 23 GB 权重 —— **本件不假装能跑**"}


def mechanism(n: int = 0, **_kw) -> dict:
    """逐条看：**上游原文** → **我们的话** → **对我们的用处** → **判据**。"""
    items = _MECH if not n else [m for m in _MECH if int(m["n"]) == int(n)]
    if not items:
        return {"ok": False, "fail_closed": True, "error": "没有这条机制：%s" % n,
                "有哪些": [m["n"] for m in _MECH]}
    return {"ok": True, "op": "mechanism", "n": n, "items": items, "共": len(_MECH),
            "出处文件": str((_UP / "docs").relative_to(_ROOT)) + "/…（在 `_upstream/Edge0/` 下）"}


def map_tentacle(**_kw) -> dict:
    """**触手映射**：这套东西用我们的话怎么说。"""
    return {"ok": True, "op": "map", "kind": "offload_distill", "条数": len(_MAP),
            "映射": [{"它的": a, "我们的触手语言": b} for a, b in _MAP],
            "_口径": "映射是**我们的口径**（可复核可改），不是对外部件的断言；"
                     "照这条走，取件就变成『按需伸手 + 预判 + 并行』，而不是『整座仓搬回家』"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "offload_distill",
            "entry": "run_task('offload_distill', {'op':'map'})", "ops": list(_OPS),
            "what": "把 Edge0 的『内存墙另一半』蒸成我们自己的运行纪律与**触手映射**（不搬代码）",
            "四条": [m["name"] for m in _MECH],
            "hard_rules": ["只蒸思路 · 不搬它的代码", "只读上游 · 零执行（不装依赖、不下载 23 GB 权重）",
                           "**边界不许说反**：本机 = Windows/AMD + torch CPU；上游 Python 路线绑 MLX(Apple Silicon)"
                           " ⇒ 本机跑不了那条；Windows 那条是 C++/Vulkan，要单独编译",
                           "**我们是 7B dense，不是 MoE**：它的 prerouter 预测的是『专家路由』，"
                           "搬到我们身上要**退化成按层顺序预取**，收益远小于 MoE —— 这条必须说清"],
            "上游": "Edge0-AI/Edge0（Apache-2.0 · ★4612 · arXiv 2609.18063）落 `_upstream/Edge0`",
            "下游": "我们自己的推理链（llama.cpp / ollama / 自建）：**权重离芯 + 槽位 LRU + 预取重叠 + 不合并适配器**"}


def run(op: str = "status", **params) -> dict:
    op = str(op or "status").lower()
    for nm, fn in (("status", status), ("where", where), ("mechanism", mechanism),
                   ("map", map_tentacle), ("probe", probe)):
        if op == nm:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": "未知 op：%s" % op, "ops": list(_OPS)}


if __name__ == "__main__":                                   # 主人的终端入口
    import argparse
    import json
    try:                        # 本机控制台默认 GBK ⇒ 中文直接打会 UnicodeEncodeError
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                    # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="内存墙蒸馏件（Edge0 思路 → 我们的纪律 + 触手映射）")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--json", default="{}")
    a = ap.parse_args()
    print(json.dumps(run(a.cmd, **json.loads(a.json or "{}")), ensure_ascii=False, indent=1))

# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
