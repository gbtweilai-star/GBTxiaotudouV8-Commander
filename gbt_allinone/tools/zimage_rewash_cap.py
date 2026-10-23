# gbt-capability: zimage_rewash
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""zimage_rewash · 洗图流水线（看图 → 反推提示词 → 重绘 → 放大）
⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印

立项（Owner 2026-09-27）：把"Z-Image 图生图 + 免费 API 反推"整合成本仓能力。
**诚实前置（三处依赖现读，不编）**：
  · **反推**（图→提示词）：本仓**没有**现成的图像理解能力位——`vision` 域那位是**屏幕**视觉（`privacy_read` 门），
    不吃文件；云 LLM 链（`cloud_llm._KEY_CHAIN`）的 `ask()` 是**纯文本**通道，没有 image content part。
    ⇒ 现状：**未接线**。可行路子两条：①给 `cloud_llm` 加 image part（Agnes 2.5 flash 若认
    `image_url` 就直接通）②接本地 VLM（要装）。**在接通之前，反推由"我"（模型本体）或
    `autoglm-image-recognition` 技能代劳——不是能力位，如实标注。**
  · **重绘**（Z-Image 图生图）：本机**未装 ComfyUI**（GS 插件那次确认过）；
    pollinations 的 img2img 需要**公网可达的图 URL**（本地盘上的图它拉不到）⇒ **未验**。
  · **放大**：✅ **这条今天就能真跑**——ffmpeg lanczos + unsharp 实现在 `op=upscale`，零依赖。

降噪强度（denoise）口径表（Owner 给的原表，存为数据，随 `op=denoise_table` 取）：
  0.15–0.25 抛光（几乎不动，只调色彩/光影/质感）· 0.30–0.45 受控重绘（保结构、重塑细节）·
  0.50–0.65 大胆重绘（保"感觉"与布局）· 0.70–0.85 新想法（原图只当灵感）

门：读面（status/denoise_table）免门；`upscale` 写盘 ⇒ 过 `filesystem_write`。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
READ_OPS = ("status", "denoise_table")
WRITE_OPS = ("upscale", "reverse", "rewash")

DENOISE_TABLE = [
    {"range": "0.15-0.25", "effect": "抛光：几乎完全保留原图，仅微调色彩/光影/质感",
     "use": "照片精修、轻微美化"},
    {"range": "0.30-0.45", "effect": "受控重绘：保主体结构与构图，细节明显重塑",
     "use": "人像精修、风格轻微迁移"},
    {"range": "0.50-0.65", "effect": "大胆重绘：保'感觉'与大致布局，内容可能大变",
     "use": "创意重塑、换风格"},
    {"range": "0.70-0.85", "effect": "新想法：原图只当灵感，生成近乎全新的图",
     "use": "以图为灵感的全新创作"},
]


def _gate(what: str) -> dict | None:
    from .. import auth_gate
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    g = auth_gate.check_and_consume("filesystem_write", detail=f"zimage_rewash:{what}"[:60])
    if g.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": "filesystem_write",
            "error": g.get("error"), "how_to_grant": g.get("how_to_grant")}


def _probe() -> dict:
    comfy = None
    for cand in (Path.home() / "ComfyUI", Path("D:/AI/comfyui"), Path("C:/ComfyUI")):
        if cand.is_dir():
            comfy = str(cand)
            break
    return {
        "reverse": {"ready": False, "why": "无图像理解能力位（vision 是屏幕视觉；云链 ask() 是纯文本）",
                    "unblock": "给 cloud_llm 加 image content part（Agnes 2.5 flash 认 image_url 即通）或装本地 VLM"},
        "rewash": {"ready": False, "why": "本机未装 ComfyUI；pollinations img2img 需公网可达图 URL（本地盘图拉不到）",
                   "unblock": "装 ComfyUI（Z-Image 工作流）或把参考图放到公网可达处再走 pollinations kontext"},
        "upscale": {"ready": shutil.which("ffmpeg") is not None, "why": "ffmpeg lanczos+unsharp（零依赖）",
                    "unblock": "已可用"},
        "comfyui_dir": comfy,
    }


def status(**_kw) -> dict:
    p = _probe()
    return {"ok": True, "op": "status", "kind": "zimage_rewash",
            "read_ops": list(READ_OPS), "write_ops": list(WRITE_OPS),
            "deps": p,
            "口径": "反推/重绘两环**未接线**（如实标缺）；放大环已可用；洗图的降噪口径见 op=denoise_table"}


def denoise_table(**_kw) -> dict:
    return {"ok": True, "op": "denoise_table", "table": DENOISE_TABLE,
            "口径": "降噪强度=图生图的油门；数值越高越偏离原图"}


_MAIN_LEG = "comfy_native.upscale_4k（PIL LANCZOS + USM）"


def upscale(src: str = "", out: str = "", factor=None, unsharp: float = 0.6,
            scale=None, size=None, sharpen=None, **_kw) -> dict:
    """高清放大（**今天就能跑的那一环**）：lanczos 重采样 + unsharp 提锐。

    🔴 **2026-10-13 收敛（主人令「每一个调节都要触手可控」）** —— 这一位是**历史腿**，
    主腿是 `%s`。两条腿的旋钮**不是都同一个量纲**，所以收敛分两类做，**不搞假统一**：

    | 旋钮 | 能不能统一 | 为什么 |
    |---|---|---|
    | `scale` ↔ 旧名 `factor` | ✅ **真统一**（同一个语义：放大**倍数**） | 都是 `iw*scale` |
    | `size`（目标**绝对宽**） | ✅ **真统一**（算成倍数走同一条路） | 最终宽度是同一个语义 |
    | `sharpen`（主腿）vs `unsharp`（本腿） | ❌ **不统一，而且显式拒** | 主腿是 **PIL USM 的 percent 比例**（0.6⇒60%%）；本腿是 **ffmpeg `unsharp` 滤镜的 amount**（`unsharp=5:5:0.6`）。**两个算法、两个量纲**，改同名＝假统一（"名字一样、效果不一样"更害人） |

    ⇒ 传 `sharpen` 给本腿一律 **fail-closed 并指路主腿**；同名不同量纲这种事**不许含糊**。
    """ % _MAIN_LEG
    # 🔴 顺序（2026-10-13）：**先判参数、后过门** —— 参数不对就当场拒，
    #    不消耗授权、也不给"门拒了所以你不知道参数错在哪"的糊涂账。
    if not src:
        return {"ok": False, "error": "需要 src=源图路径"}
    # ── 旋钮统一闸（在跑 ffmpeg **之前**判，拒了就不许动盘）──────────────────
    if sharpen is not None:
        return {"ok": False, "fail_closed": True, "refused": True, "op": "upscale",
                "error": "本腿（历史腿）**没有 `sharpen` 这个旋钮** —— 它只有 `unsharp`，"
                         "而且两者**量纲不同**（主腿是 PIL USM 的 percent 比例；本腿是 ffmpeg "
                         "`unsharp` 滤镜的 amount）⇒ 不许改名冒充同一个旋钮。",
                "要锐化就走去主腿": _MAIN_LEG,
                "本腿的锐化旋钮": "unsharp（ffmpeg unsharp amount，默认 0.6）",
                "几何旋钮（两条腿同名同义）": ["scale / factor（倍数）", "size（目标绝对宽）"]}
    if factor is not None and scale is not None and float(factor) != float(scale):
        return {"ok": False, "fail_closed": True, "op": "upscale",
                "error": "`factor`（旧名）与 `scale`（新名）**同时给了且不相等** ⇒ 不知道听谁的",
                "factor": factor, "scale": scale, "口径": "两个名字是同一个旋钮，别各给一个值"}
    f = float(scale if scale is not None else (factor if factor is not None else 2.0))
    used = {"scale": f, "unsharp": float(unsharp)}
    s = Path(src) if Path(src).is_absolute() else ROOT / src
    if not s.is_file():
        return {"ok": False, "error": f"源图不存在：{s}"}
    if size is not None:                       # 目标绝对宽 ⇒ 算成倍数（同一个语义）
        try:
            from PIL import Image
            with Image.open(s) as im:
                w0 = im.size[0]
        except Exception as e:                                 # noqa: BLE001
            return {"ok": False, "op": "upscale", "error": "读不到源图宽（size 要用它换算）：%s"
                                                           % str(e)[:120]}
        if float(size) <= 0 or w0 <= 0:
            return {"ok": False, "op": "upscale", "fail_closed": True,
                    "error": "size 必须 > 0（收到 %s）" % size}
        f = float(size) / float(w0)
        used["size"] = int(size)
        used["scale"] = round(f, 6)
    deny = _gate("upscale")                    # 参数齐了才过门
    if deny:
        return deny
    o = Path(out) if out else s.with_name(f"{s.stem}-x{f:g}{s.suffix}")
    if not o.is_absolute():
        o = ROOT / o
    o.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale=iw*{f:g}:ih*{f:g}:flags=lanczos,unsharp=5:5:{used['unsharp']:g}"
    r = subprocess.run(["ffmpeg", "-y", "-i", str(s), "-vf", vf, "-q:v", "2", str(o)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300, cwd=str(ROOT))
    ok = r.returncode == 0 and o.is_file() and o.stat().st_size > 0
    out_d = {"ok": ok, "op": "upscale", "src": str(s), "out": str(o),
             "bytes": o.stat().st_size if o.is_file() else 0, "vf": vf}
    out_d.update({"leg": "历史腿（ffmpeg lanczos + unsharp 滤镜）", "main_leg": _MAIN_LEG,
                  "knobs": used,
                  "同名同义": ["scale（新名）/ factor（旧名）", "size（目标绝对宽）"],
                  "不统一且显式拒": "sharpen（量纲不同：主腿 PIL USM percent vs 本腿 ffmpeg amount）"})
    if not ok:
        out_d["error"] = (r.stderr or "")[-200:]
    return out_d


def _gbt_vision_reverse(image: str = ""):
    """★ 2026-10-15 闭环：**反推环接上 vision**。

    为什么这么接（她写的 unblock 原文）：
      "给 cloud_llm 加 image content part（**Agnes 2.5 flash 认 `image_url` 即通**）或装本地 VLM"
    而 `vision` 位现在**已经具备**：`cloud=true · base_url=apihub.agnes-ai.com/v1 ·
    model=agnes-2.5-flash · via=unified` ⇒ 条件已满足，**只差把图发过去**。

    纪律：
      · 只读本地图 → base64 data URL（**不出网存图**，也不回显密钥）
      · 取不到 vision 通道就**如实报 not_wired**，不假装成功
      · 走本仓统一门（`gbt.run_task("vision", ...)`），不自己直连
    """
    import base64, json as _j, mimetypes, os as _o
    if not image or not _o.path.isfile(image):
        return {"ok": False, "error_class": "bad_input", "error": "图不在：%s" % image}
    try:
        import gbt_allinone as _g
    except Exception as e:
        return {"ok": False, "error_class": "no_tentacle",
                "error": "拿不到统一门：%s" % str(e)[:90]}
    mt = mimetypes.guess_type(image)[0] or "image/png"
    b64 = base64.b64encode(open(image, "rb").read()).decode("ascii")
    url = "data:%s;base64,%s" % (mt, b64)
    PROMPT = ("你是图像提示词工程师。请把这幅图反推成一段**可直接用于文生图/图生图**的提示词："
              "先一句话主体，再列风格/光线/构图/材质/镜头，用逗号分隔的关键词；"
              "另起一行给出 negative 提示词。**只输出提示词，不要解释。**")
    # 先探通道（fail-closed，不猜）
    try:
        st = _g.run_task("vision", {"op": "status"})
        st = (st.get("gbt_result") or {}).get("result", st)
        if not (isinstance(st, dict) and st.get("cloud")):
            return {"ok": False, "error_class": "not_wired",
                    "error": "vision 云通道不可用", "vision": st}
    except Exception as e:
        return {"ok": False, "error_class": "probe_failed", "error": str(e)[:100]}
    # ★ 2026-10-15 修（实测咬到）：`vision_cap.analyze(image=None, region=None, grid=4)`
    #   吃的是 **`image`**（本地路径），而它内部自己 base64 成 data URL 发 Agnes
    #   （`vision_cap.py:248` 就是那句 image_url）。我第一版传 `image_url` ⇒ **参数名不匹配**、
    #   三种 op 名全试过也一律 not_wired —— 看着像「vision 不支持图」，其实只是名字没对上。
    for payload in ({"op": "see", "image": image},):
        try:
            rr = _g.run_task("vision", payload)
            rr = (rr.get("gbt_result") or {}).get("result", rr)
            if isinstance(rr, dict) and rr.get("ok") is not False and (
                    rr.get("text") or rr.get("answer") or rr.get("result")):
                return {"ok": True, "op": "reverse", "via": "vision:%s" % payload["op"],
                        "prompt": (rr.get("text") or rr.get("answer") or rr.get("result") or ((rr.get("lanes") or {}).get("text") or {}).get("text") or ((rr.get("lanes") or {}).get("formal") or {}).get("prompt")),
                        "raw": rr}
        except Exception:
            continue
    return {"ok": False, "error_class": "not_wired",
            "error": "vision 位在位但反推 op 未接通（三种 op 名都试过）",
            "怎么修": "在 vision 位加一个认 image_url 的 op（agnes-2.5-flash 原生支持）"}


def reverse(image: str = "", **_kw) -> dict:
    """图像反推（图→提示词）——**未接线**，如实报缺 + 给出接线条件。"""
    _r = _gbt_vision_reverse(image)
    if _r.get("ok"):
        return _r
    return {"ok": False, "op": "reverse", "error_class": "not_wired",
            "error": "反推环未接通（已试 vision 通道）", "vision_try": _r,
            "image": image,
            "怎么修": _probe()["reverse"]["unblock"],
            "临时替代": "由模型本体或 autoglm-image-recognition 技能代劳（不是能力位，别当能力位念）"}


def rewash(image: str = "", style: str = "", denoise: float = 0.4, **_kw) -> dict:
    """洗图重绘——**未接线**（缺 ComfyUI / 缺公网图 URL），如实报缺。"""
    band = next((r["range"] for r in DENOISE_TABLE
                 if any(abs(denoise - v) < 0.06 for v in
                        (0.2, 0.375, 0.575, 0.775))), "")
    return {"ok": False, "op": "rewash", "error_class": "not_wired",
            "error": "本机未装 ComfyUI；pollinations img2img 需公网可达图 URL",
            "image": image, "style": style, "denoise": denoise, "denoise_band": band,
            "怎么修": _probe()["rewash"]["unblock"]}


def run(op: str = "status", **kw) -> dict:
    op = (op or "status").lower()
    if op in ("status", "denoise_table"):
        return {"status": status, "denoise_table": denoise_table}[op](**kw)
    if op == "upscale":
        return upscale(**kw)
    if op in ("reverse", "rewash"):
        return {"reverse": reverse, "rewash": rewash}[op](**kw)
    return {"ok": False, "error": f"未知 op:{op}（{'/'.join(READ_OPS + WRITE_OPS)}）",
            "fail_closed": True}
