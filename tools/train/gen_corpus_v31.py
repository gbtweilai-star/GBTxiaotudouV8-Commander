# v31 corpus: ComfyUI family REBUILT in Chinese, teaching the API JSON contract + full worked graphs
import hashlib, io, json
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v32.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v33.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v33_manifest.json"
LIVE = ROOT / "state" / "comfyui_object_info_live.json"
info = json.loads(LIVE.read_text(encoding="utf-8"))
base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
DROP = ("秋叶版图示例", "秋叶版契约", "节点名册", "节点契约", "秋叶版规程")
keep = [r for r in base if r.get("family") not in DROP]
new = []
def add(q, a, fam):
    new.append({"instruction": q, "input": "", "output": a, "family": fam})
def req_of(v):
    r = ((v.get("input") or {}).get("required") or {})
    out = []
    for k, spec in list(r.items())[:10]:
        t = spec[0] if isinstance(spec, list) and spec else spec
        if isinstance(t, list):
            t = "\u679a\u4e3e(%d)" % len(t)
        out.append("%s:%s" % (k, t))
    return out
G = {}
for name in ("txt2img", "img2img", "txt2video"):
    G[name] = (ROOT / ".scratch" / ("graph_" + name + ".json")).read_text(encoding="utf-8").strip()
CN = {"txt2img": "\u6587\u751f\u56fe", "img2img": "\u56fe\u751f\u56fe", "txt2video": "\u6587\u751f\u89c6\u9891"}
for _rep in range(6):
  for k, cn in CN.items():
      a = ("**" + cn + "**\u7684\u5b8c\u6574 API \u683c\u5f0f\uff08\u539f\u6837\u53ef\u8fc7 cap comfy_native op=validate\uff09\uff1a" + G[k]
         + " \u8bfb\u6cd5\uff1a\u9876\u5c42\u952e\u662f**\u8282\u70b9\u7f16\u53f7**\uff1b\u6bcf\u4e2a\u8282\u70b9\u662f class_type + inputs\uff1b\u8fde\u7ebf\u5199\u6210 [\u8282\u70b9\u7f16\u53f7, \u8f93\u51fa\u5e8f\u53f7]\uff1b\u5fc5\u586b\u9879\u770b\u5951\u7ea6\u3002")
      add("\u7ed9\u6211\u4e00\u6761\u300c%s\u300d\u5de5\u4f5c\u6d41\u7684 API \u683c\u5f0f JSON\uff08\u8282\u70b9+\u8fde\u7ebf+\u5fc5\u586b\u53c2\u6570\uff09\u3002" % cn, a, "\u79cb\u53f6\u7248\u56fe\u793a\u4f8b")
      add("%s\u5de5\u4f5c\u6d41\u7684 API JSON \u600e\u4e48\u5199\uff1f\u7ed9\u6211\u53ef\u8dd1\u7684\u4e00\u4efd\u3002" % cn, a, "\u79cb\u53f6\u7248\u56fe\u793a\u4f8b")
API = [
    ("ComfyUI \u7684 API \u683c\u5f0f\u957f\u4ec0\u4e48\u6837\uff1f", "\u4e00\u4e2a\u5b57\u5178\uff1a**\u952e\u662f\u8282\u70b9\u7f16\u53f7**\uff08\u5b57\u7b26\u4e32\uff0c\u5982 \'1'\uff09\uff0c**\u503c\u662f \{class_type, inputs\}**\uff1bclass_type \u662f\u8282\u70b9\u540d\uff08\u5fc5\u987b\u5728\u5951\u7ea6\u91cc\uff09\uff0cinputs \u662f\u8be5\u8282\u70b9\u7684\u8f93\u5165\u9879\u3002\u4e0d\u662f nodes/kwargs \u90a3\u79cd DSL\u3002"),
    ("\u8fde\u7ebf\u600e\u4e48\u5199\uff1f", "\u8fde\u7ebf = **[\u4e0a\u6e38\u8282\u70b9\u7f16\u53f7, \u8f93\u51fa\u5e8f\u53f7]**\uff0c\u4f8b\u5982 model \u63a5\u7b2c 1 \u4e2a\u8282\u70b9\u7684 0 \u53f7\u8f93\u51fa\u5199 ['1', 0]\uff1b\u666e\u901a\u53c2\u6570\u76f4\u63a5\u5199\u503c\uff08\u6570\u5b57/\u5b57\u7b26\u4e32/\u5e03\u5c14\uff09\u3002"),
    ("\u54ea\u4e9b\u8f93\u5165\u662f\u5fc5\u586b\uff1f", "\u770b\u8282\u70b9\u5951\u7ea6\u7684 **input.required**\uff1b\u5fc5\u586b\u7f3a\u4e00\u9879\u5c31\u4e0d\u80fd\u8dd1\uff08validate \u4f1a\u62a5\u7f3a\u5fc5\u586b\uff09\u3002\u9009\u586b\u5728 input.optional\u3002"),
    ("\u7f16\u6392\u5b8c\u8981\u505a\u4ec0\u4e48\uff1f", "**\u5148 validate \u518d run**\uff1acap comfy_native \{op: validate, workflow: \u56fe\} \u68c0\u4e09\u7c7b\u2014\u2014\u672a\u77e5\u8282\u70b9 \u00b7 \u7f3a\u5fc5\u586b \u00b7 \u6210\u73af\uff1b\u8fc7\u4e86\u624d\u8dd1\u3002"),
    ("\u6587\u751f\u56fe\u6700\u5c11\u8981\u54ea\u51e0\u4e2a\u8282\u70b9\uff1f", "\u516d\u4ef6\uff1aCheckpointLoaderSimple \u00b7 CLIPTextEncode \u00b7 EmptyLatentImage \u00b7 KSampler \u00b7 VAEDecode \u00b7 SaveImage\u3002"),
    ("\u6587\u751f\u89c6\u9891\u6bd4\u6587\u751f\u56fe\u591a\u4ec0\u4e48\uff1f", "\u591a\u4e24\u4ef6\uff1a**\u8fd0\u52a8\u6a21\u5757\u52a0\u8f7d**\uff08ADE_AnimateDiff* \u6216 SVD/Wan \u4e13\u7528\u8282\u70b9\uff09\u4e0e**\u89c6\u9891\u5408\u6210**\uff08\u5982 VHS_VideoCombine\uff09\uff1b\u4e14 EmptyLatentImage \u7684 batch_size \u8981\u7b49\u4e8e**\u5e27\u6570**\u3002"),
]
for _rep in range(6):
  for q, a in API:
      add(q, a, "\u79cb\u53f6\u7248\u5951\u7ea6")
bycat = defaultdict(list)
for name, v in info.items():
    bycat[str(v.get("category") or "\u672a\u5206\u7c7b")].append(name)
for c in sorted(bycat, key=lambda x: -len(bycat[x]))[:30]:
    ns = bycat[c]
    body = "\u300c%s\u300d\u7c7b\u73b0\u8bfb\u5171 **%d \u4e2a\u8282\u70b9**\uff1a%s\u3002" % (c, len(ns), " ".join("%d.%s" % (i + 1, n) for i, n in enumerate(ns)))
    add("\u300c%s\u300d\u7c7b\u6709\u54ea\u4e9b\u8282\u70b9\uff1f" % c, body, "\u8282\u70b9\u540d\u518c")
KW = ("KSampler", "CheckpointLoader", "CLIPTextEncode", "VAEDecode", "VAEEncode", "EmptyLatent",
      "SaveImage", "LoadImage", "LoraLoader", "ADE_AnimateDiff", "VHS_VideoCombine")
for n in sorted([x for x in info if any(k.lower() in x.lower() for k in KW)])[:80]:
    v = info[n]
    body = ("\u8282\u70b9 **%s**\uff08%s\u7c7b\uff09\uff1a\u5fc5\u586b = %s\uff1b\u53ef\u9009 = %s\uff1b\u8f93\u51fa = %s\u3002"
            % (n, v.get("category") or "\u672a\u5206\u7c7b", "\uff0c".join(req_of(v)) or "\u65e0",
               "\uff0c".join(list(((v.get("input") or {}).get("optional") or {}))[:6]) or "\u65e0",
               "\uff0c".join(map(str, v.get("output") or [])) or "\u65e0"))
    add("\u300c%s\u300d\u8282\u70b9\u7684\u5fc5\u586b\u8f93\u5165\u6709\u54ea\u4e9b\uff1f\u8f93\u51fa\u4ec0\u4e48\uff1f" % n, body, "\u8282\u70b9\u5951\u7ea6")
AY = [
    ("\u79cb\u53f6\u7248\u6574\u5408\u5305\u600e\u4e48\u8d77\uff1f", "\u81ea\u5e26\u542f\u52a8\u5668\uff1b\u670d\u52a1\u9ed8\u8ba4\u76d1\u542c **8188**\uff1b\u63a5\u53e3\uff1a/prompt \u63d0\u4ea4\u3001/object_info \u8282\u70b9\u5951\u7ea6\u3001/history \u53d6\u7ed3\u679c\u3002\u542f\u52a8\u540e**\u5148\u8bfb /object_info** \u518d\u7f16\u6392\u3002"),
    ("\u6a21\u578b\u653e\u54ea\uff1f", "\u5927\u6a21\u578b models/checkpoints \u00b7 VAE models/vae \u00b7 LoRA models/loras \u00b7 ControlNet models/controlnet \u00b7 \u653e\u5927 models/upscale_models\uff1b\u81ea\u5b9a\u4e49\u8282\u70b9 custom_nodes\u3002**\u653e\u9519\u76ee\u5f55 = \u52a0\u8f7d\u5668\u8282\u70b9\u627e\u4e0d\u5230\u6a21\u578b**\u3002"),
    ("\u8282\u70b9\u4e0d\u8ba4\u8bc6\u600e\u4e48\u529e\uff1f", "\u5148\u67e5\u5951\u7ea6\uff1acap comfy_forge \u627e\u4ef6 + \u73b0\u8bfb state/comfyui_object_info_live.json\uff1b**\u672a\u77e5\u8282\u70b9\u4e0d\u8bb8\u786c\u8fde**\uff0c\u5148 validate\u3002"),
    ("\u7f16\u6392\u524d\u5fc5\u987b\u5148\u8dd1\u54ea\u4e2a\u5224\u636e\uff1f", "cap comfy_native op=validate\uff1b\u5b83\u68c0\u4e09\u7c7b\uff1a**\u672a\u77e5\u8282\u70b9 \u00b7 \u7f3a\u5fc5\u586b \u00b7 \u6210\u73af**\u3002\u8fc7\u4e86\u624d run\u3002"),
]
for q, a in AY:
    add(q, a, "\u79cb\u53f6\u7248\u89c4\u7a0b")
WIRE = [
    ("CheckpointLoaderSimple 的输出序号是什么？", "输出三个：**0=MODEL · 1=CLIP · 2=VAE**。model 接 0，clip 接 1，vae 接 2。"),
    ("CLIPTextEncode / EmptyLatentImage / KSampler / VAEDecode 的输出序号？", "CLIPTextEncode → **0=CONDITIONING**；EmptyLatentImage → **0=LATENT**；KSampler → **0=LATENT**；VAEDecode → **0=IMAGE**。"),
    ("文生图的正确连线怎么接？", "model←CheckpointLoaderSimple[0] · clip←[1] · vae←[2]；positive←正提示 CLIPTextEncode[0] · negative←负提示[0]；latent_image←EmptyLatentImage[0]；VAEDecode.samples←KSampler[0] · VAEDecode.vae←CheckpointLoaderSimple[2]；SaveImage.images←VAEDecode[0]。"),
    ("连线接错会怎样？", "接错序号（例如把 MODEL 接成 [\"1\",2]）会报类型不匹配或直接跑不起；**上机前必须 validate**。"),
]
for _rep in range(6):
  for q, a in WIRE:
    add(q, a, "节点连线语义")
out = keep + new
OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
blob = OUT.read_bytes()
fam = defaultdict(int)
for r in out:
    fam[r.get("family") or "?"] += 1
MAN.write_text(json.dumps({"gen": "v31", "parent": "v30", "count": len(out), "bytes": len(blob),
                           "sha256": hashlib.sha256(blob).hexdigest(),
                           "by_family": dict(sorted(fam.items(), key=lambda x: -x[1]))},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print("v31", len(out), "| new", len(new), "| dropped", len(base) - len(keep), "| bytes", len(blob), "| sha", hashlib.sha256(blob).hexdigest()[:16])
print("\u65b0\u65cf:", [(k, fam[k]) for k in ("\u79cb\u53f6\u7248\u56fe\u793a\u4f8b", "\u79cb\u53f6\u7248\u5951\u7ea6", "\u8282\u70b9\u540d\u518c", "\u8282\u70b9\u5951\u7ea6", "\u79cb\u53f6\u7248\u89c4\u7a0b")])
