# -*- coding: utf-8 -*-
"""genrouter · 生成后端**轮询调度器**（图 / 视频 / 通用）

主人令 2026-09-23：「那就安装 50 个轮询使用就好了」
⇒ 50 个**后端来源**（各家服务 / 本机 / 开源端点）注册成一张表，轮询着用：
   谁还免费、谁还活着、谁快 ⇒ 就用谁；都到顶 ⇒ **回落本机**（这条永远不拒绝你）。

三条设计口径（写死，别改）：
 ① **未验的后端不许用**。表里可以列 50 个候选，但每个都带 `probe`；
    **probe 没过就永远排在候选之外** —— 宁可用得少，不用假的。
 ② **同一家的多个账号不算"多个后端"**。这张表按**服务来源**去重；
    一家开多号吃多份免费额度是平台条款禁止的，封的是主人的号 —— 这条不解释第二遍。
 ③ **每一次调用都留痕**：哪家、耗时、消耗、成没成，落 `state.json` + 审计账本。

用法：
    python tools/codex-scripts/genrouter.py --list              # 看 50 个后端 + 现读状态
    python tools/codex-scripts/genrouter.py --probe comfy_local # 验一个后端（真跑一次）
    python tools/codex-scripts/genrouter.py image --prompt "..." --n 3   # 轮询出图
    python tools/codex-scripts/genrouter.py --selftest          # 只验调度逻辑，不调外部

退出码：0=成功 · 2=没有任何可用后端 · 3=全部到顶/挂了 · 4=被拒（缺凭据）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".scratch" / "_genrouter_state.json"

# ══════════════════════════════════════════════════════════════════════════════
# 后端注册表：**按服务来源**一行一个（不是"按账号"）。
#   kind    : image / video / llm / tts（这一版只接 image；其余先登记形状）
#   free    : 免费额度口径（**必须是一手查到的**，查不到就写"未查"）
#   needs   : 需要什么凭据（env 变量名）；空 = 不需要（本机/公开端点）
#   probe   : 怎么验它活着（None = 还没写探针 ⇒ 永远排在候选之外）
#   adapter : 用哪个适配器（openai_image / cf_ai / comfy_local / none）
# ══════════════════════════════════════════════════════════════════════════════
B = []
def add(**kw): B.append(kw)


# ── 本机（真无限，慢）──────────────────────────────────────────────────────
add(id="comfy_local", name="本机 ComfyUI（SD1.5 · CPU）", kind="image", adapter="comfy_local",
    free="真无限（本地）", needs=[], unit="586 秒/张（实测）", probe="http://127.0.0.1:8188/system_stats")

# ── Cloudflare Workers AI（一手查过：10,000 神经元/天）─────────────────────
add(id="cf_flux_schnell", name="Cloudflare · flux-1-schnell", kind="image", adapter="cf_ai",
    free="免费 10,000 神经元/天 · 43.2/张 ⇒ 约 231 张/天",
    needs=["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"], unit="秒级",
    model="@cf/black-forest-labs/flux-1-schnell", probe=None)
add(id="cf_flux2_klein", name="Cloudflare · flux-2-klein-4b", kind="image", adapter="cf_ai",
    free="同上额度池", needs=["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"], unit="秒级",
    model="@cf/black-forest-labs/flux-2-klein-4b", probe=None)
add(id="cf_leonardo_phoenix", name="Cloudflare · leonardo/phoenix-1.0", kind="image", adapter="cf_ai",
    free="同上额度池（636 神经元/张，贵）", needs=["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"],
    unit="秒级", model="@cf/leonardo/phoenix-1.0", probe=None)

# ── OpenAI 兼容端点（一个适配器覆盖一大片：换 base_url + key 就是一家）────
_OA = [
    ("openai_images",   "OpenAI · gpt-image",        "OPENAI_API_KEY",     "https://api.openai.com/v1"),
    ("azure_openai",    "Azure OpenAI",              "AZURE_OPENAI_KEY",   "由 AZURE_OPENAI_ENDPOINT 给"),
    ("google_ai",       "Google AI Studio / Gemini", "GOOGLE_API_KEY",     "https://generativelanguage.googleapis.com/v1beta"),
    ("hf_inference",    "HuggingFace Inference",     "HF_TOKEN",           "https://api-inference.huggingface.co"),
    ("replicate",       "Replicate",                 "REPLICATE_API_TOKEN", "https://api.replicate.com/v1"),
    ("fal",             "fal.ai",                     "FAL_KEY",            "https://fal.run"),
    ("venice",          "Venice.ai",                  "VENICE_API_KEY",     "https://api.venice.ai/api/v1"),
    ("together",        "Together AI",                "TOGETHER_API_KEY",   "https://api.together.xyz/v1"),
    ("deepinfra",       "DeepInfra",                  "DEEPINFRA_API_KEY",  "https://api.deepinfra.com/v1"),
    ("novita",          "Novita AI",                  "NOVITA_API_KEY",     "https://api.novita.ai/v3"),
    ("siliconflow",     "SiliconFlow 硅基流动",        "SILICONFLOW_API_KEY", "https://api.siliconflow.cn/v1"),
    ("modelscope",      "ModelScope 魔搭",             "MODELSCOPE_API_KEY", "https://api-inference.modelscope.cn/v1"),
    ("dashscope",       "阿里云百炼 / 通义万相",        "DASHSCOPE_API_KEY",  "https://dashscope.aliyuncs.com/api/v1"),
    ("volc_ark",        "火山方舟 Ark（本仓有 arkcli 规程）", "ARK_API_KEY",  "https://ark.ap-southeast.bytepluses.com/api/v3"),
    ("baidu_qianfan",   "百度千帆",                    "QIANFAN_AK",         "https://aip.baidubce.com"),
    ("zhipu",           "智谱 GLM",                    "ZHIPU_API_KEY",      "https://open.bigmodel.cn/api/paas/v4"),
    ("moonshot",        "月之暗面 Kimi",               "MOONSHOT_API_KEY",   "https://api.moonshot.cn/v1"),
    ("minimax",         "MiniMax 海螺",                "MINIMAX_API_KEY",    "https://api.minimax.chat/v1"),
    ("stepfun",         "阶跃星辰 Step",               "STEPFUN_API_KEY",    "https://api.stepfun.com/v1"),
    ("baichuan",        "百川智能",                    "BAICHUAN_API_KEY",   "https://api.baichuan-ai.com/v1"),
    ("sensetime",       "商汤日日新",                  "SENSETIME_API_KEY",  "https://api.sensenova.cn/v1"),
    ("xfyun",           "讯飞星火",                    "XF_APP_ID",          "https://spark-api.xf-yun.com/v1"),
    ("hunyuan",         "腾讯混元",                    "HUNYUAN_SECRET_ID",  "https://hunyuan.tencentcloudapi.com"),
    ("stability",       "Stability AI",                "STABILITY_API_KEY",  "https://api.stability.ai"),
    ("bfl",             "Black Forest Labs（FLUX 官方）", "BFL_API_KEY",       "https://api.bfl.ai/v1"),
    ("ideogram",        "Ideogram",                    "IDEOGRAM_API_KEY",   "https://api.ideogram.ai"),
    ("recraft",         "Recraft",                     "RECRAFT_API_KEY",    "https://external.api.recraft.ai/v1"),
    ("luma",            "Luma AI（图/视频）",           "LUMA_API_KEY",      "https://api.lumalabs.ai/dream-machine/v1"),
    ("runway",          "Runway（视频）",              "RUNWAY_API_KEY",     "https://api.dev.runwayml.com/v1"),
    ("pika",            "Pika（视频）",                "PIKA_API_KEY",       "https://api.pika.art"),
    ("kling",           "可灵 Kling（视频）",           "KLING_ACCESS_KEY",  "https://api.klingai.com"),
    ("vidu",            "Vidu（视频）",                "VIDU_API_KEY",       "https://api.vidu.cn"),
    ("hailuo",          "海螺 MiniMax（视频）",         "HAILUO_API_KEY",    "见 MiniMax"),
    ("higgsfield",      "Higgsfield（视频）",          "HIGGSFIELD_KEY",     "未查"),
    ("stability_video", "Stability · SVD（视频）",      "STABILITY_API_KEY", "https://api.stability.ai"),
    ("lightricks",      "Lightricks LTX（视频）",       "LTX_API_KEY",       "未查"),
    ("wavespeed",       "WaveSpeedAI",                 "WAVESPEED_API_KEY", "https://api.wavespeed.ai"),
    ("comet",           "CometAPI（聚合）",             "COMETAPI_KEY",      "https://api.cometapi.com/v1"),
    ("openrouter",      "OpenRouter（聚合）",           "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
    ("aihubmix",        "AiHubMix（聚合）",             "AIHUBMIX_KEY",      "https://aihubmix.com/v1"),
    ("ohmygpt",         "OhMyGPT（聚合）",              "OHMYGPT_KEY",       "https://api.ohmygpt.com/v1"),
    ("gptgod",          "GPTGOD（聚合）",               "GPTGOD_KEY",        "未查"),
    ("sdwebui_local",   "本机 Stable Diffusion WebUI",  "",                  "http://127.0.0.1:7860"),
    ("fooocus_local",   "本机 Fooocus",                 "",                  "http://127.0.0.1:7865"),
    ("invokeai_local",  "本机 InvokeAI",                "",                  "http://127.0.0.1:9090"),
    ("ollama_local",    "本机 Ollama（LLM，本地兜底）",  "",                  "http://127.0.0.1:11434"),
    ("lmstudio_local",  "本机 LM Studio",               "",                  "http://127.0.0.1:1234/v1"),
    ("localai_local",   "本机 LocalAI",                 "",                  "http://127.0.0.1:8080/v1"),
]
for i, (bid, nm, env, base) in enumerate(_OA):
    kind = "video" if any(k in bid for k in ("runway", "pika", "kling", "vidu", "hailuo",
                                             "higgsfield", "lightricks", "luma", "stability_video")) else (
           "llm" if bid in ("ollama_local", "lmstudio_local", "localai_local", "openrouter",
                            "comet", "aihubmix", "ohmygpt", "gptgod") else "image")
    add(id=bid, name=nm, kind=kind, adapter="openai_image" if kind == "image" else "none",
        free="未查（不编额度）", needs=([env] if env else []), unit="未查",
        base=base, probe=(base if base.startswith("http://127.0.0.1") else None))

# Pollinations：**不需要任何凭据的公开图端点** ⇒ 轮询池里唯一"现在就能用的云腿"。
# 它的探针必须**真取一张图**（只 GET 首页会给 404，探不出真假）。
add(id="pollinations", name="Pollinations（公开端点，无需 key）", kind="image",
    adapter="pollinations", free="公开端点 · 无 key（用它即接受其条款与限速）",
    needs=[], unit="秒级", base="https://image.pollinations.ai",
    probe="https://image.pollinations.ai/prompt/hello?width=64&height=64&nologo=true",
    probe_kind="image")

# 🔴 登记表 → 适配器**接线修正**（离线核对 `--dry-adapters` 当场抓出来的错）：
#    `_OA` 那一圈默认都套了通用 `openai_image`（POST {base}/images/generations），
#    可事实是：HF 有自己的走法（我为它写了 `gen_hf` 却**没接上**）、Google 的图接口不是这个形状、
#    fal 也不认这条路。**接错线的后果**是"看着写好了、一给钥匙就 404" —— 比没写更坏。
#    ⇒ 一家一家明确接线；**没写对适配器的一律标 none**（不入池、不假装）。
ADAPTER_FIX = {
    "hf_inference": "hf_inference",                       # 用 gen_hf（新老双域名逐条试）
    "dashscope": "openai_image",                          # 百炼确有 OpenAI 兼容模式
    "siliconflow": "openai_image",                        # /v1/images/generations，通用形状对
    "modelscope": "openai_image",                         # 同上
    "volc_ark": "openai_image",                           # Ark /api/v3/images/generations
    "google_ai": "google_ai",                             # 真实形状：:generateContent（已写）
    "fal": "fal",                                         # 真实形状：fal.run/<model> + Key 方案（已写）
}
BASE_FIX = {"dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1"}
for _b in B:
    if _b["id"] in ADAPTER_FIX:
        _b["adapter"] = ADAPTER_FIX[_b["id"]]
    if _b["id"] in BASE_FIX:
        _b["base"] = BASE_FIX[_b["id"]]

# 主人 2026-09-23 最终口径：「其他云平台只要是**官方插件**都可以按一下，没事，偶尔会用到」
# ⇒ **池子放开到官方插件那一档**（云后端 0 磁盘、0 成本）；路由**只用探针通过的**。
POOL = [
    "comfy_local",       # ① 本机兜底：真无限、真离线、已验（586 秒/张）
    "pollinations",      # ② 无 key 云腿：已验真出图（秒级）
    "cf_flux_schnell",   # ③ Cloudflare（官方插件卡）· 免费 10,000 神经元/天 ≈ 231 张/天
    "hf_inference",      # ④ HuggingFace 推理 API（官方插件卡）
    "google_ai",         # ⑤ Google AI Studio
    "siliconflow",       # ⑥ 硅基流动
    "modelscope",        # ⑦ 魔搭 ModelScope
    "volc_ark",          # ⑧ 火山方舟（端点已验：只差凭据）
    "dashscope",         # ⑨ 阿里百炼 / 通义万相
    "fal",               # ⑩ fal.ai（图与视频都在它这）
]

# 端点候选矩阵：**不靠记忆猜 URL**，逐条试，谁回 401/403/200 谁就是对的。
# 为什么用 `/v1/models` 当探针：OpenAI 兼容端点几乎都实现了它，
# 无 key 回 401（= 端点对、只差凭据）、有 key 回 200（= 通）—— 一试就分明。
CAND = {
    "hf_inference": ["https://router.huggingface.co/v1/models",
                     "https://api-inference.huggingface.co/models",
                     "https://huggingface.co/api/models?limit=1"],
    "google_ai": ["https://generativelanguage.googleapis.com/v1beta/models",
                  "https://generativelanguage.googleapis.com/v1/models"],
    "siliconflow": ["https://api.siliconflow.cn/v1/models",
                    "https://api.siliconflow.com/v1/models"],
    "modelscope": ["https://api-inference.modelscope.cn/v1/models",
                   "https://modelscope.cn/api/v1/models"],
    "volc_ark": ["https://ark.ap-southeast.bytepluses.com/api/v3/models",
                 "https://ark.cn-beijing.volces.com/api/v3/models"],
    "dashscope": ["https://dashscope.aliyuncs.com/compatible-mode/v1/models",
                  "https://dashscope.aliyuncs.com/api/v1/models"],
    "fal": ["https://fal.run/fal-ai/flux/schnell",
            "https://queue.fal.run/fal-ai/flux/schnell",
            "https://rest.alpha.fal.ai/tokens/"],
    "cf_flux_schnell": ["https://api.cloudflare.com/client/v4/user/tokens/verify"],
}

# ══════════════════════════════════════════════════════════════════════════════


def load_state():
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"day": time.strftime("%Y-%m-%d"), "calls": {}, "down": {}, "ok": {}}


def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def today():
    return time.strftime("%Y-%m-%d")


def env_ok(b):
    """凭据齐不齐 —— **只看环境变量在不在，不读值、不打印值**。"""
    import os
    missing = [k for k in (b.get("needs") or []) if not os.environ.get(k)]
    return (not missing), missing


def live_probe(b, timeout=5):
    u = b.get("probe")
    if not u or not str(u).startswith("http"):
        return None                      # 没探针 ⇒ 不表态（也就不许被选中）
    try:
        with urllib.request.urlopen(u, timeout=timeout) as r:
            if b.get("probe_kind") == "image":      # 图端点：**必须真拿到图**才算活
                blob = r.read(2048)
                return r.status < 400 and len(blob) > 256
            return r.status < 500
    except Exception:  # noqa: BLE001
        return False


def _sniff(blob):
    """按**魔数**认格式（不靠猜、不靠 URL 后缀）。
    🔴 第 1 版栽在这：Pollinations 回的是 **JPEG**，我却把文件写成 `.png` ⇒
       扩展名与实际字节不符，产物当场变成"废物"（本仓明令：二进制不许当文本、
       也不许张冠李戴）。读图器一眼就把它挡了 —— 这就是"真验"的价值。"""
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if blob[:2] == b"\xff\xd8":
        return "jpg"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return "webp"
    if blob[:3] == b"GIF":
        return "gif"
    return "bin"


def gen_pollinations(b, prompt, outdir, idx):
    """Pollinations 出图：GET 一个 URL 就返回图。**无 key、无额度**（按其条款与限速）。"""
    import urllib.parse
    q = urllib.parse.urlencode({"width": 512, "height": 512, "nologo": "true",
                                "seed": int(time.time()) % 99999 + idx})
    url = "%s/prompt/%s?%s" % (b["base"], urllib.parse.quote(prompt[:180]), q)
    t0 = time.time()
    with urllib.request.urlopen(url, timeout=120) as r:
        blob = r.read()
    if len(blob) < 1024:
        return {"ok": False, "error": "返回太小（%d 字节），不像图" % len(blob)}
    fmt = _sniff(blob)
    if fmt == "bin":
        return {"ok": False, "error": "认不出图片格式（前 12 字节 %r）" % blob[:12]}
    outdir.mkdir(parents=True, exist_ok=True)
    dst = outdir / ("%s-%d.%s" % (b["id"], int(t0), fmt))
    dst.write_bytes(blob)
    import hashlib
    return {"ok": True, "backend": b["id"], "file": str(dst), "bytes": len(blob),
            "format": fmt, "elapsed_s": round(time.time() - t0, 2),
            "sha256_head": hashlib.sha256(blob).hexdigest()[:16]}


def _need(b):
    """凭据齐不齐 —— 只报**变量名**，永远不读值、不打印值。"""
    import os
    miss = [k for k in (b.get("needs") or []) if not os.environ.get(k)]
    return miss


def _save(blob, b, outdir, t0):
    fmt = _sniff(blob)
    if fmt == "bin":
        return {"ok": False, "error": "返回认得不是图片（前 12 字节 %r）" % blob[:12]}
    outdir.mkdir(parents=True, exist_ok=True)
    dst = outdir / ("%s-%d.%s" % (b["id"], int(t0), fmt))
    dst.write_bytes(blob)
    import hashlib
    return {"ok": True, "backend": b["id"], "file": str(dst), "bytes": len(blob),
            "format": fmt, "elapsed_s": round(time.time() - t0, 2),
            "sha256_head": hashlib.sha256(blob).hexdigest()[:16]}


def _post(url, body, headers, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.headers.get("Content-Type", ""), r.read()


def gen_cf(b, prompt, outdir, idx):
    """Cloudflare Workers AI：`POST /accounts/{id}/ai/run/{model}`。
       响应两种形态都要吃：**直接回图片字节**，或 **JSON 里带 base64**（`result.image`）。"""
    import base64
    import os
    miss = _need(b)
    if miss:
        return {"ok": False, "status": "needs_credential", "backend": b["id"], "missing": miss}
    acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    tok = os.environ["CLOUDFLARE_API_TOKEN"]
    url = "https://api.cloudflare.com/client/v4/accounts/%s/ai/run/%s" % (acct, b["model"])
    t0 = time.time()
    try:
        ctype, raw = _post(url, {"prompt": prompt[:400]},
                           {"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    except urllib.error.HTTPError as e:
        return {"ok": False, "backend": b["id"], "http": e.code,
                "error": e.read().decode("utf-8", "replace")[:200]}
    if "image" in ctype or raw[:2] == b"\xff\xd8" or raw[:8] == b"\x89PNG\r\n\x1a\n":
        return _save(raw, b, outdir, t0)
    try:
        j = json.loads(raw.decode("utf-8", "replace"))
        img = ((j.get("result") or {}).get("image")) or ""
        if img:
            return _save(base64.b64decode(img), b, outdir, t0)
        return {"ok": False, "backend": b["id"], "error": "JSON 里没有 result.image：%s" % str(j)[:180]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "backend": b["id"], "error": "响应解析失败：%s" % str(e)[:120]}


# HuggingFace 推理端点有**新老两个域名**（现读：新域名通、老域名不通）⇒ 逐条试，
# 谁先回图片字节就用谁，并把"是哪条成的"记进结果 —— 不猜。
HF_URLS = [
    "https://router.huggingface.co/hf-inference/models/%s",
    "https://api-inference.huggingface.co/models/%s",
]


def gen_hf(b, prompt, outdir, idx):
    import os
    miss = _need(b)
    if miss:
        return {"ok": False, "status": "needs_credential", "backend": b["id"], "missing": miss}
    tok = os.environ["HF_TOKEN"]
    model = b.get("model") or "black-forest-labs/FLUX.1-schnell"
    t0 = time.time()
    tried = []
    for tpl in HF_URLS:
        url = tpl % model
        try:
            ctype, raw = _post(url, {"inputs": prompt[:400]},
                               {"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
            if raw[:2] == b"\xff\xd8" or raw[:8] == b"\x89PNG\r\n\x1a\n" or "image" in ctype:
                out = _save(raw, b, outdir, t0)
                out["endpoint"] = url
                out["tried"] = tried + ["%s → 成" % url[:56]]
                return out
            tried.append("%s → 不是图（%s）" % (url[:56], ctype[:24]))
        except urllib.error.HTTPError as e:
            tried.append("%s → %d" % (url[:56], e.code))
        except Exception as e:  # noqa: BLE001
            tried.append("%s → %s" % (url[:56], type(e).__name__))
    return {"ok": False, "backend": b["id"], "error": "两条端点都没出图", "tried": tried}


def gen_openai_image(b, prompt, outdir, idx):
    """**OpenAI 兼容**出图：`POST {base}/images/generations`。
       一个适配器覆盖一大片（硅基流动 / 魔搭 / 百炼兼容模式 / 火山 / OpenAI…）——
       差别只在 base 与 model，所以这些字段都从注册表取，不写死。"""
    import base64
    import os
    miss = _need(b)
    if miss:
        return {"ok": False, "status": "needs_credential", "backend": b["id"], "missing": miss}
    key = os.environ[b["needs"][0]]
    base = (b.get("base") or "").rstrip("/")
    if not base.startswith("http"):
        return {"ok": False, "backend": b["id"], "error": "base 未登记（%s）" % base}
    url = base + "/images/generations"
    t0 = time.time()
    body = {"model": b.get("model") or "flux", "prompt": prompt[:400], "n": 1}
    try:
        ctype, raw = _post(url, body,
                           {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    except urllib.error.HTTPError as e:
        return {"ok": False, "backend": b["id"], "http": e.code,
                "error": e.read().decode("utf-8", "replace")[:200]}
    if raw[:2] == b"\xff\xd8" or raw[:8] == b"\x89PNG\r\n\x1a\n":
        return _save(raw, b, outdir, t0)
    try:
        j = json.loads(raw.decode("utf-8", "replace"))
        d0 = (j.get("data") or [{}])[0]
        if d0.get("b64_json"):
            return _save(base64.b64decode(d0["b64_json"]), b, outdir, t0)
        if d0.get("url"):
            with urllib.request.urlopen(d0["url"], timeout=120) as r:
                return _save(r.read(), b, outdir, t0)
        return {"ok": False, "backend": b["id"], "error": "既无 b64_json 也无 url：%s" % str(j)[:180]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "backend": b["id"], "error": "响应解析失败：%s" % str(e)[:120]}


def gen_google(b, prompt, outdir, idx):
    """Google AI Studio：图走 `:generateContent`，**不是** OpenAI 那个形状。
       两处防坑：
         · 密钥走 **`x-goog-api-key` 头**，不放 URL 查询串 —— 免得密钥进日志/进别人截图。
         · 回包里图可能在 `inlineData.data`，也可能在 `predictions[].bytesBase64Encoded`
           （不同模型两种形态）⇒ **两种都认**，认不出来就如实报，不猜。
       ⚠️ 模型 id 会变，所以 model 从注册表取；现读给的是一个通用占位，**换模型不用改代码**。"""
    import base64
    import os
    miss = _need(b)
    if miss:
        return {"ok": False, "status": "needs_credential", "backend": b["id"], "missing": miss}
    key = os.environ["GOOGLE_API_KEY"]
    model = b.get("model") or "gemini-2.0-flash-preview-image-generation"
    url = ("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model)
    t0 = time.time()
    try:
        ctype, raw = _post(url, {"contents": [{"parts": [{"text": prompt[:400]}]}]},
                           {"x-goog-api-key": key, "Content-Type": "application/json"})
    except urllib.error.HTTPError as e:
        return {"ok": False, "backend": b["id"], "http": e.code,
                "error": e.read().decode("utf-8", "replace")[:200]}
    try:
        j = json.loads(raw.decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "backend": b["id"], "error": "响应不是 JSON：%s" % str(e)[:100]}
    b64 = ""
    for cand in (j.get("candidates") or []):
        for part in (((cand.get("content") or {}).get("parts")) or []):
            d = ((part.get("inlineData") or {}).get("data")) or ((part.get("inline_data") or {}).get("data"))
            if d:
                b64 = d
                break
        if b64:
            break
    if not b64:
        for pred in (j.get("predictions") or []):
            if pred.get("bytesBase64Encoded"):
                b64 = pred["bytesBase64Encoded"]
                break
    if not b64:
        return {"ok": False, "backend": b["id"],
                "error": "回包里没找到图（认过 inlineData / predictions 两种形态）：%s" % str(j)[:200]}
    return _save(base64.b64decode(b64), b, outdir, t0)


def gen_fal(b, prompt, outdir, idx):
    """fal.ai：`POST https://fal.run/<model-id>`，鉴权头是 **`Authorization: Key <FAL_KEY>`**
       （fal 用的是 `Key` 方案，不是 `Bearer` —— 写错了是 401，很容易误判成"钥匙不对"）。
       回包：`{"images":[{"url": ...}]}` ⇒ 再取那个 url 的字节。"""
    import os
    miss = _need(b)
    if miss:
        return {"ok": False, "status": "needs_credential", "backend": b["id"], "missing": miss}
    key = os.environ["FAL_KEY"]
    model = b.get("model") or "fal-ai/flux/schnell"
    url = "https://fal.run/" + model
    t0 = time.time()
    try:
        ctype, raw = _post(url, {"prompt": prompt[:400]},
                           {"Authorization": "Key " + key, "Content-Type": "application/json"})
    except urllib.error.HTTPError as e:
        return {"ok": False, "backend": b["id"], "http": e.code,
                "error": e.read().decode("utf-8", "replace")[:200]}
    if raw[:2] == b"\xff\xd8" or raw[:8] == b"\x89PNG\r\n\x1a\n":
        return _save(raw, b, outdir, t0)
    try:
        j = json.loads(raw.decode("utf-8", "replace"))
        u = ((j.get("images") or [{}])[0]).get("url")
        if not u:
            return {"ok": False, "backend": b["id"], "error": "回包里没有 images[0].url：%s" % str(j)[:180]}
        with urllib.request.urlopen(u, timeout=120) as r:
            return _save(r.read(), b, outdir, t0)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "backend": b["id"], "error": "响应解析失败：%s" % str(e)[:120]}


def gen_comfy(b, prompt, outdir, idx):
    """本机 ComfyUI：把它并进**同一个池**（原来它只活在 `comfy-run.py` 那个独立脚本里 ——
       两条路等于两套口径，本仓最贵的教训）。五步：探活 → 认模型 → 提交 → 等 → 取图。"""
    import urllib.parse
    import uuid
    base = (b.get("base") or "http://127.0.0.1:8188").rstrip("/")
    t0 = time.time()
    try:
        get_json(base, "/system_stats", timeout=8)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "backend": b["id"], "status": "server_down",
                "error": "%s: %s" % (type(e).__name__, str(e)[:100]),
                "hint": "起服务：pwsh -File tools/codex-scripts/comfy-serve.ps1"}
    ckpt = b.get("ckpt") or ""
    if not ckpt:
        names = ((((get_json(base, "/object_info/CheckpointLoaderSimple", 20).get(
            "CheckpointLoaderSimple") or {}).get("input") or {}).get("required") or {}
        ).get("ckpt_name") or [[]])[0]
        cand = [n for n in (names or []) if "fp16" in n.lower()] or (names or [])
        if not cand:
            return {"ok": False, "backend": b["id"], "status": "no_checkpoint"}
        ckpt = cand[0]
    seed = int(time.time()) % 2_000_000_000
    wf = build_comfy_workflow(ckpt, prompt, b.get("negative") or "lowres, blurry, watermark, text",
                              int(b.get("steps") or 20), int(b.get("size") or 512), seed)
    try:
        res = post_json(base, "/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())}, timeout=60)
    except urllib.error.HTTPError as e:
        return {"ok": False, "backend": b["id"], "http": e.code,
                "error": e.read().decode("utf-8", "replace")[:200]}
    pid = res.get("prompt_id")
    deadline = t0 + float(b.get("timeout_s") or 1800)
    while time.time() < deadline:
        time.sleep(3)
        try:
            h = get_json(base, "/history/" + urllib.parse.quote(pid), timeout=15)
        except Exception:  # noqa: BLE001
            continue
        if pid in h and h[pid]:
            hist = h[pid]
            for _nid, out in (hist.get("outputs") or {}).items():
                for im in (out.get("images") or []):
                    q = urllib.parse.urlencode({"filename": im.get("filename", ""),
                                                "subfolder": im.get("subfolder", ""),
                                                "type": im.get("type", "output")})
                    with urllib.request.urlopen(base + "/view?" + q, timeout=120) as r:
                        saved = _save(r.read(), b, outdir, t0)
                    saved["ckpt"] = ckpt
                    saved["seed"] = seed
                    return saved
            return {"ok": False, "backend": b["id"], "status": "no_image",
                    "status_str": (hist.get("status") or {}).get("status_str")}
    return {"ok": False, "backend": b["id"], "status": "timeout",
            "waited_s": round(time.time() - t0, 1), "prompt_id": pid}


def build_comfy_workflow(ckpt, prompt, negative, steps, size, seed):
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": 7.0, "sampler_name": "euler",
            "scheduler": "normal", "denoise": 1.0, "model": ["4", 0], "positive": ["6", 0],
            "negative": ["7", 0], "latent_image": ["5", 0]}},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": size, "height": size, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "gbt", "images": ["8", 0]}},
    }


ADAPTERS = {"pollinations": gen_pollinations, "cf_ai": gen_cf, "hf_inference": gen_hf,
            "openai_image": gen_openai_image, "google_ai": gen_google, "fal": gen_fal,
            "comfy_local": gen_comfy}


def call_with_deadline(fn, args, deadline_s):
    """给**每一次后端调用**加硬截止时间（第 22 轮加）。

    ## 为什么非加不可（实测事故）
    主人令那一轮跑 `image --n 2`，**600 秒被耗光**：pollinations 那次请求**挂住不返回**。
    而我的冷却机制只在"后端**返回了错误**"时才触发 ⇒ **挂住 = 不返回 = 永远不切腿**，
    主循环就那样干等。这是真缺陷，不是环境问题。

    ## 做法与代价（说清）
    · 守护线程跑调用，主线程 `join(deadline)`；超时即返回 `timeout` 记录，
      **主循环立刻切下一条腿**并把这条记进冷却。
    · ⚠️ **被放弃的那条线程不会被杀死**（Python 杀不了线程）—— 它会飘着直到自己超时退出。
      所以这是"**不阻塞调度**"，不是"**消灭那个请求**"。这条不许说成后者。
    · `daemon=True` 保证进程能正常退出（非守护线程会让 Python 卡在退出）。
    """
    import threading
    box = {}

    def run():
        try:
            box["r"] = fn(*args)
        except Exception as e:                                        # noqa: BLE001
            box["e"] = e

    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(deadline_s)
    if th.is_alive():
        return {"ok": False, "status": "timeout",
                "error": "后端在 %.1fs 内没返回（挂住）—— 已记冷却并切下一条腿" % deadline_s,
                "_口径": "被放弃的线程不会被杀死，只是不再阻塞调度"}
    if "e" in box:
        raise box["e"]
    return box["r"]


def _fetch_bounded(url, max_s=60.0, max_bytes=32 << 20, timeout=15):
    """有**墙钟上限**的下载：`urlopen(timeout=)` 只管 socket 单次操作，
    服务器慢速滴数据时每次 read 都重置计时 ⇒ 墙钟可能远超 timeout（第 22 轮实测 600s）。
    ⇒ 这里自己数墙钟，超了就抛。"""
    t0 = time.time()
    chunks, n = [], 0
    with urllib.request.urlopen(url, timeout=timeout) as r:
        while True:
            if time.time() - t0 > max_s:
                raise TimeoutError("下载超过 %.0fs 墙钟上限" % max_s)
            b = r.read(65536)
            if not b:
                break
            chunks.append(b)
            n += len(b)
            if n > max_bytes:
                raise ValueError("响应超过 %d 字节上限" % max_bytes)
    return b"".join(chunks)


def get_json(base, path, timeout=20):
    """🔴 第 22 轮我在这里犯过一个**很隐蔽**的错：改文件时把 `def get_json(...)` 那一行
    当旧串替换掉了，而它的**函数体缩进正好接在 `_fetch_bounded` 后面** ⇒
    Python **照样解析通过**（语法检查全绿），只是这两行成了 `_fetch_bounded` 里
    `return` 之后的**不可达死代码**，而 `get_json` **根本不存在了** ⇒
    `gen_comfy` 一调就 NameError。
    ⇒ 教训：**"语法过了"不等于"函数还在"**。删/改函数头之后要按**函数名**复核一遍调用方。"""
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def post_json(base, path, obj, timeout=60):
    req = urllib.request.Request(base + path, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def cmd_dry_adapters():
    """**不发一个请求**，把每个后端"将要发出的真实请求"打出来。
       为什么要它：没钥匙的时候，"适配器写好了"这句话无法验证；
       而请求的 method/url/body/要有哪些 header 是**可以离线核对**的 —— 这就是证据。"""
    print("=" * 96)
    print("适配器离线核对（**不发请求、不读凭据值**，只看它将要发什么）")
    print("=" * 96)
    for bid in POOL:
        b = next((x for x in B if x["id"] == bid), None)
        if not b:
            continue
        ad = b.get("adapter")
        miss = _need(b)
        if ad == "comfy_local":
            spec = "POST http://127.0.0.1:8188/prompt（工作流 JSON）→ GET /history → GET /view"
        elif ad == "pollinations":
            spec = "GET %s/prompt/<url-encoded prompt>?width=512&height=512&nologo=true" % b.get("base")
        elif ad == "cf_ai":
            spec = ("POST https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai/run/%s"
                    " · header: Authorization: Bearer <CLOUDFLARE_API_TOKEN> · body {\"prompt\"}"
                    % b.get("model"))
        elif ad == "hf_inference":
            spec = ("POST https://router.huggingface.co/hf-inference/models/%s（老域名作备选）"
                    " · header: Authorization: Bearer <HF_TOKEN> · body {\"inputs\"}"
                    % (b.get("model") or "black-forest-labs/FLUX.1-schnell"))
        elif ad == "openai_image":
            spec = ("POST %s/images/generations · header: Authorization: Bearer <%s>"
                    " · body {\"model\",\"prompt\",\"n\"}" % (b.get("base"), (b.get("needs") or ["KEY"])[0]))
        elif ad == "google_ai":
            spec = ("POST generativelanguage.googleapis.com/v1beta/models/<MODEL>:generateContent"
                    " · header: **x-goog-api-key**（密钥不进 URL） · body {\"contents\":[…]}"
                    " · 两种回包形态都认：inlineData.data / predictions[].bytesBase64Encoded")
        elif ad == "fal":
            spec = ("POST https://fal.run/%s · header: **Authorization: Key <FAL_KEY>**"
                    "（fal 用 Key 方案，不是 Bearer） · body {\"prompt\"} → images[0].url → 取字节"
                    % (b.get("model") or "fal-ai/flux/schnell"))
        elif ad == "comfy_local":
            spec = ("POST http://127.0.0.1:8188/prompt（工作流 JSON：KSampler/Checkpoint/…）"
                    " → 轮询 /history/<id> → GET /view 取字节（**已并入同一个池**）")
        else:
            spec = "❗未接适配器（%s）" % ad
        flag = "缺 " + "、".join(miss) if miss else "凭据齐 ⇒ 可直接跑"
        print("\n%-18s [%s]" % (bid, flag))
        print("   %s" % spec)
    print("\n" + "=" * 96)
    print("口径：这一段**只证明请求形状对**，不证明对方会答应 —— 后者只有真跑一次才算数。")
    return 0


def status_of(b, st):
    """一个后端此刻能不能用：**三态说清**（能用 / 等凭据 / 未验）。"""
    if b["id"] not in POOL:
        return "备选在册", "不在轮询池（主人定 10 个）—— 池子小才好管"
    if st.get("down", {}).get(b["id"], 0) > time.time():
        return "冷却中", "刚失败过，等冷却"
    ok, missing = env_ok(b)
    if not ok:
        return "等凭据", "缺 " + "、".join(missing)
    if b.get("probe"):
        lp = live_probe(b)
        if lp is False:
            return "没起来", "探针不通：" + str(b["probe"])
    if b.get("adapter") in (None, "none"):
        return "未接适配器", "形状已登记，适配器还没写"
    if not b.get("probe"):
        return "未验", "没有探针 ⇒ 按口径①不参与路由"
    return "可用", ""


def probe_endpoint(b, timeout=8):
    """**不带凭据**打它的端点（先试候选矩阵），看返回什么 —— 三种结果必须分得开：
         401/403 ⇒ 端点登记对了，**只差凭据**（开关一开就能用）
         404     ⇒ 端点路径我登记错了（得改，不是缺 key）
         超时/DNS ⇒ **出网不通**（要主人放行，加多少 key 都没用）
       为什么要有它：口头说"只差一个 key"没有说服力；这条是**读数**。"""
    urls = CAND.get(b["id"]) or ([b["base"]] if str(b.get("base") or "").startswith("http") else [])
    if not urls:
        return {"reachable": None, "http": None, "tried": [],
                "note": "没有 HTTP 端点（%s）" % (b.get("base") or "未登记")}
    tried, last, saw_http = [], None, False
    for u in urls:
        try:
            with urllib.request.urlopen(urllib.request.Request(u), timeout=timeout) as r:
                tried.append("%s → %d ✅" % (u[:56], r.status))
                return {"reachable": True, "http": r.status, "url": u, "tried": tried,
                        "note": "端点可达（%d）· 就是这条" % r.status}
        except urllib.error.HTTPError as e:
            # 🔴 **"端点回了话" ≠ "出网不通"**（第 1 版把 400 判成出网不通，是混口径）。
            #    只要有 HTTP 状态码，就说明**网络到达了对方**；区别只在凭据/参数/路径。
            saw_http = True
            tried.append("%s → %d" % (u[:56], e.code))
            if e.code in (401, 403):
                return {"reachable": True, "http": e.code, "url": u, "tried": tried,
                        "note": "**只差凭据**（%d）· 端点就在这：%s" % (e.code, u[:64])}
            if e.code == 400:
                return {"reachable": True, "http": e.code, "url": u, "tried": tried,
                        "note": "端点可达（400：它要凭据/参数才肯答）· %s" % u[:64]}
            if e.code == 404:
                last = "404（这条路径不对）"
                continue                      # 换下一条候选
            last = "端点回了 %d（网是通的）" % e.code
        except Exception as e:  # noqa: BLE001
            tried.append("%s → %s" % (u[:56], type(e).__name__))
            last = "出网不通：%s" % type(e).__name__
    return {"reachable": saw_http, "http": None, "tried": tried,
            "note": last or "全试完了都不通"}


def cmd_verify_pool(st):
    """逐个体检轮询池：**端点可达性 + 缺什么 + 结论**（不动任何外部状态）。"""
    import os
    print("=" * 92)
    print("轮询池体检（**不带凭据**打端点，看它到底卡在哪一步）")
    print("=" * 92)
    rows = []
    for bid in POOL:
        b = next((x for x in B if x["id"] == bid), None)
        if not b:
            continue
        miss = [k for k in (b.get("needs") or []) if not os.environ.get(k)]
        # 🔴 守卫写错过一次：原来只在"登记了 base"时才探 ⇒ 把 cf_flux_schnell（只有 model、
        #    端点写在 CAND 里）和候选矩阵整个跳过，报成"本机服务"。有 CAND 就该探。
        pe = (probe_endpoint(b)
              if (b["id"] in CAND or str(b.get("base") or "").startswith("http"))
              else {"note": "本机服务（不走 HTTP 探针）"})
        if not miss and b.get("needs"):
            verdict = "凭据已配 ⇒ 可直接用"
        elif pe.get("http") in (401, 403):
            verdict = "只差凭据（端点已验）"
        elif pe.get("reachable") is False:
            verdict = "出网不通"
        elif pe.get("http") == 404:
            verdict = "端点登记要改"
        else:
            verdict = "待验"
        rows.append((bid, b["name"], pe.get("note", ""), "、".join(miss) or "—", verdict))
    print("%-18s %-26s %-30s %s" % ("后端", "现状", "缺什么", "结论"))
    print("-" * 92)
    for bid, nm, note, miss, verdict in rows:
        print("%-18s %-26s %-30s %s" % (bid, nm[:24], note[:28], verdict))
        if miss != "—":
            print("%-18s   ↑ 缺：%s" % ("", miss))
    print("-" * 92)
    print("口径：401/403 = 端点对、只差凭据；404 = 我登记错了；超时 = 出网被挡。三者不许混成一句")
    return 0


def write_status(st):
    """把池子状态**落成一份机器可读的件**，好让面板/脑窗不用起进程就能读。
    为什么要有它：面板要显示"池子几条腿、今天出了几张"，不该为此去 spawn 一个 Python；
    读一个 JSON 文件既便宜又不会挂。路径固定 `state/genpool.json`（**不是 .scratch**——
    它是给别人读的口径件，不能放在会被清掉的目录里）。"""
    import os
    pool = []
    for bid in POOL:
        b = next((x for x in B if x["id"] == bid), None)
        if not b:
            continue
        s, why = status_of(b, st)
        miss = [k for k in (b.get("needs") or []) if not os.environ.get(k)]
        pool.append({"id": bid, "name": b["name"], "kind": b["kind"], "status": s, "why": why,
                     "free": b.get("free"), "adapter": b.get("adapter"),
                     "missing": miss, "is_local": str(bid).endswith("_local")})
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "pool_size": len(POOL),
           "usable": sum(1 for p in pool if p["status"] == "可用"),
           "waiting": sum(1 for p in pool if p["status"] == "等凭据"),
           "pool": pool,
           "calls_today": st.get("calls", {}).get(today(), {}),
           "calls_today_total": sum((st.get("calls", {}).get(today(), {}) or {}).values()),
           "cooldown": [k for k, v in (st.get("down") or {}).items() if v > time.time()],
           "_口径": "同一家的多个账号不算多个后端；未验的不参与路由；云后端不占本地磁盘"}
    out = ROOT / "state" / "genpool.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def cmd_list(st):
    print("=" * 88)
    print("genrouter · 轮询池 **%d 个**（主人定）· 另有 %d 个备选在册（不参与路由）"
          % (len(POOL), len(B) - len(POOL)))
    print("=" * 88)
    buckets = {}
    for b in B:
        s, why = status_of(b, st)
        buckets.setdefault(s, []).append((b, why))
    order = ["可用", "冷却中", "未验", "没起来", "等凭据", "未接适配器"]
    for s in order:
        rows = buckets.get(s) or []
        if not rows:
            continue
        print("\n【%s】%d 个" % (s, len(rows)))
        for b, why in rows:
            print("  %-20s %-30s %-6s %s" % (b["id"], b["name"][:28], b["kind"],
                                             (b.get("free") or "")[:30]))
            if why:
                print("        ← %s" % why)
    n_ok = len(buckets.get("可用") or [])
    print("\n轮询池合计：%d 个 · **可用 %d 个** · 备选在册 %d 个（不路由）"
          % (len(POOL), n_ok, len(buckets.get("备选在册") or [])))
    print("口径：未验的不参与路由（宁可少用，不用假的）；同一家的多个账号不算多个后端")
    return 0


def cmd_probe(bid, st):
    b = next((x for x in B if x["id"] == bid), None)
    if not b:
        print("没有这个后端：%s（--list 看全部）" % bid)
        return 2
    s, why = status_of(b, st)
    lp = live_probe(b, timeout=8)
    out = {"id": bid, "name": b["name"], "status": s, "why": why,
           "probe_url": b.get("probe"), "probe_alive": lp,
           "needs": b.get("needs") or [], "have_creds": env_ok(b)[0],
           "free": b.get("free"), "adapter": b.get("adapter")}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if s == "可用" else 4


def cmd_selftest(st):
    """只验**调度逻辑**：不调任何外部服务，也不花钱。"""
    cands = [b for b in B if status_of(b, st)[0] == "可用"]
    print("调度自检：候选 %d 个" % len(cands))
    print("  轮询池：%s" % ([b["id"] for b in cands] or "(空)"))
    print("  全到顶时的回落：%s" % ("comfy_local（本机，永远在）"
                            if any(b["id"] == "comfy_local" for b in B) else "❗没有本机回落"))
    st["day"] = today()
    save_state(st)
    print("  状态文件：%s（今天计数 %s）" % (STATE, st["calls"].get(today(), {})))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="生成后端轮询调度器")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--verify-pool", action="store_true")
    ap.add_argument("--dry-adapters", action="store_true")
    ap.add_argument("--json", action="store_true", help="只吐口径件 JSON（给面板读）")
    ap.add_argument("--probe", default="")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("cmd", nargs="?", default="")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=90.0,
                    help="**每一次后端调用的墙钟上限**（秒）。超时即记冷却并切下一条腿")
    ap.add_argument("--clear-cooldown", action="store_true",
                    help="清掉冷却记录（用于'那次冷却是我人为测试造成的'这种情形；不是真故障）")
    a = ap.parse_args()
    st = load_state()
    if st.get("day") != today():          # 跨天：免费额度重置（00:00 UTC 由各家自己算）
        st = {"day": today(), "calls": {}, "down": {}, "ok": {}}
    if a.clear_cooldown:
        n = len(st.get("down") or {})
        st["down"] = {}
        save_state(st)
        print(json.dumps({"ok": True, "cleared": n,
                          "note": "冷却已清。**只在'那次冷却是人为/测试造成'时这么干**；"
                                  "真故障应当让它自己冷却满 5 分钟。"},
                         ensure_ascii=False, indent=1))
        return 0
    # 每次调用都刷一遍口径件（便宜：只有本机与 pollinations 会真发探针）
    doc = write_status(st)
    if a.json:
        print(json.dumps(doc, ensure_ascii=False, indent=1))
        return 0
    if a.list:
        return cmd_list(st)
    if a.verify_pool:
        return cmd_verify_pool(st)
    if a.dry_adapters:
        return cmd_dry_adapters()
    if a.probe:
        return cmd_probe(a.probe, st)
    if a.selftest or a.cmd == "selftest":
        return cmd_selftest(st)
    if a.cmd == "image":
        # 轮询池 = **可用** 且 **有适配器** 的后端（没适配器的登记项不冒充能出图）
        cands = [b for b in B if b["kind"] == "image"
                 and status_of(b, st)[0] == "可用" and b.get("adapter") in ADAPTERS]
        # 🔴 排序修正：**快的先上，本机只做兜底**。
        #    原来按池子顺序轮询 ⇒ `comfy_local` 排第一，`--n 1` 会先挑最慢的那条（实测 586 秒），
        #    而云腿只要几秒。所以：非本机（云）优先，本机排最后；组内按池序。
        cands.sort(key=lambda x: (1 if str(x["id"]).endswith("_local") else 0,
                                  POOL.index(x["id"]) if x["id"] in POOL else 99))
        if not cands:
            print(json.dumps({"ok": False, "status": "no_backend",
                              "detail": "没有一个「可用且有适配器」的图后端（--list 看每个卡在哪）",
                              "fallback_hint": "本机 ComfyUI 要先起服务："
                                               "pwsh -File tools/codex-scripts/comfy-serve.ps1"},
                             ensure_ascii=False, indent=1))
            return 2
        if not a.prompt:
            print(json.dumps({"ok": False, "status": "no_prompt", "hint": "要 --prompt"},
                             ensure_ascii=False, indent=1))
            return 3
        outdir = ROOT / "render" / "router"
        results, order = [], []
        for i in range(a.n):
            # 🔴 **每根触手可能"挂住不返回"**（第 22 轮实测：pollinations 挂住把 600 秒耗光，
            #    而冷却只在"返回了错误"时触发 ⇒ 挂住 = 永远不切腿）。
            #    ⇒ 一律经 `call_with_deadline`：超时即记 `timeout` 记录、进冷却、**立刻切下一条腿**，
            #       并在这一轮里**重试下一个可用后端**（不再干等）。
            rec = None
            tried = []
            for k in range(len(cands)):
                b = cands[(i + k) % len(cands)]
                tried.append(b["id"])
                rec = call_with_deadline(ADAPTERS[b["adapter"]],
                                         (b, a.prompt, outdir, i), a.timeout)
                if rec and rec.get("ok"):
                    break
                st.setdefault("down", {})[b["id"]] = time.time() + 300   # 失败/挂住 ⇒ 冷却 5 分钟
                st.setdefault("calls", {}).setdefault(today(), {})
                st["calls"][today()][b["id"]] = st["calls"][today()].get(b["id"], 0) + 1
            if tried:
                order.append("→".join(tried))
            results.append(rec)      # 记账已在重试循环里做过（别在这里记第二遍）
        save_state(st)
        ok = sum(1 for r in results if r.get("ok"))
        print(json.dumps({"ok": ok == a.n, "status": "done",
                          "pool": [c["id"] for c in cands], "轮询顺序": order,
                          "成功": ok, "共": a.n, "images": results,
                          "今日计数": st["calls"].get(today(), {}),
                          "_口径": "轮询按可用池取模；失败的后端进 5 分钟冷却，不重复踩同一个坑"},
                         ensure_ascii=False, indent=1))
        return 0 if ok == a.n else 3
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
