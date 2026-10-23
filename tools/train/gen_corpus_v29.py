# v29 corpus: turn Qiuye(Akizuki) ComfyUI contracts and nodes into her own txt2img/video ability
import hashlib, io, json
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v28.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v29.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v29_manifest.json"
LIVE = ROOT / "state" / "comfyui_object_info_live.json"
CORE = ROOT / "state" / "comfyui_object_info.json"
info = json.loads((LIVE if LIVE.is_file() else CORE).read_text(encoding="utf-8"))
base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
new = []
def add(q, a, fam):
    new.append({"instruction": q, "input": "", "output": a, "family": fam})
def req_of(v):
    r = ((v.get("input") or {}).get("required") or {})
    out = []
    for k, spec in list(r.items())[:10]:
        t = spec[0] if isinstance(spec, list) and spec else spec
        if isinstance(t, list):
            t = "enum(%d)" % len(t)
        out.append("%s:%s" % (k, t))
    return out
def opt_of(v):
    return list(((v.get("input") or {}).get("optional") or {}))[:6]
bycat = defaultdict(list)
for name, v in info.items():
    bycat[str(v.get("category") or "none")].append(name)
cats = sorted(bycat, key=lambda c: -len(bycat[c]))[:40]
for c in cats:
    ns = bycat[c]
    body = "category %s has %d nodes (live read): %s." % (c, len(ns), " ".join("%d.%s" % (i + 1, n) for i, n in enumerate(ns)))
    for q in ("what nodes are in category %s ?" % c, "list every node of the %s category" % c):
        add(q, body, "node_roster")
KW = ("KSampler", "CheckpointLoader", "CLIPTextEncode", "VAEDecode", "VAEEncode", "EmptyLatent",
      "SaveImage", "LoadImage", "ControlNet", "LoraLoader", "UNETLoader", "DualCLIPLoader",
      "ADE_", "AnimateDiff", "VHS_", "SVD", "CogVideo", "WanImageToVideo", "ModelSampling",
      "LatentUpscale", "ImageScale", "ConditioningCombine", "CLIPSetLastLayer")
pick = [n for n in info if any(k.lower() in n.lower() for k in KW)][:120]
for n in sorted(pick):
    v = info[n]
    outs = v.get("output") or []
    body = ("node %s (category %s, display %s): required inputs = %s ; optional = %s ; outputs = %s."
            % (n, v.get("category") or "none", v.get("display_name") or n,
               " , ".join(req_of(v)) or "none", " , ".join(opt_of(v)) or "none", " , ".join(map(str, outs)) or "none"))
    add("what does node %s require and output ?" % n, body, "node_contract")
    add("give the input/output contract of %s" % n, body, "node_contract")
WF = [
 ("txt2img", "1 CheckpointLoaderSimple load the checkpoint; 2 CLIPTextEncode positive and negative prompt; 3 EmptyLatentImage width height batch; 4 KSampler model plus both conditionings plus latent with steps cfg sampler scheduler seed; 5 VAEDecode; 6 SaveImage. Judge: node names and contracts must pass comfy_native validate, no unknown node, no missing required, no cycle."),
 ("img2img", "1 CheckpointLoaderSimple; 2 LoadImage; 3 VAEEncode image to latent; 4 CLIPTextEncode; 5 KSampler with denoise below 1.0 to keep the original structure; 6 VAEDecode; 7 SaveImage. Judge: denoise must be explicit, default 1.0 repaints everything."),
 ("txt2video", "1 CheckpointLoaderSimple; 2 ADE_AnimateDiffLoaderWithContext or ADE_AnimateDiffLoaderGen1 to attach the motion module; 3 CLIPTextEncode; 4 EmptyLatentImage with batch equal to frame count; 5 KSampler; 6 VAEDecode; 7 VHS_VideoCombine to write the video. Judge: frame count must match the context length, missing motion node fails."),
 ("hires_fix", "1 decoded image; 2 ImageScale or LatentUpscale with a factor; 3 KSampler with low denoise; 4 VAEDecode; 5 SaveImage. Judge: factor must fit VRAM, otherwise tile it."),
]
for name, body in WF:
    for q in ("how do you wire the %s workflow ?" % name, "give the node chain and judges for %s" % name):
        add(q, "%s workflow: %s All steps go through the only gate: cap comfy_native for validate and run, cap comfy_forge to find nodes." % (name, body), "workflow_recipe")
AY = [
 ("how do you start the Akizuki integrated package ?", "It ships its own launcher; the service listens on 8188; endpoints are /prompt submit, /object_info contracts, /history results. Always read /object_info before wiring."),
 ("where do models live ?", "checkpoints under models/checkpoints, VAE under models/vae, LoRA under models/loras, ControlNet under models/controlnet, upscalers under models/upscale_models, custom nodes under custom_nodes. Wrong folder means the loader node cannot find the model."),
 ("what if a node is unknown ?", "Read the contract first: cap comfy_forge to find the node family, then read state/comfyui_object_info_live.json. Never wire an unknown node, validate first."),
 ("what must happen before running any graph ?", "Validate then run: cap comfy_native op=validate checks unknown nodes, missing required inputs and cycles; only after it passes may you run."),
 ("which nodes are mandatory for txt2img ?", "Six at minimum: CheckpointLoaderSimple, CLIPTextEncode, EmptyLatentImage, KSampler, VAEDecode, SaveImage."),
 ("what does video add on top of txt2img ?", "Two: a motion module loader (ADE_AnimateDiff or SVD/Wan specific nodes) and a video combiner such as VHS_VideoCombine; the latent batch must equal the frame count."),
]
for q, a in AY:
    add(q, a, "akizuki_rules")
out = base + new
OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
blob = OUT.read_bytes()
fam = defaultdict(int)
for r in out:
    fam[r.get("family") or "?"] += 1
MAN.write_text(json.dumps({"gen": "v29", "parent": "v28", "count": len(out), "bytes": len(blob),
                           "sha256": hashlib.sha256(blob).hexdigest(),
                           "comfy_source": str(LIVE if LIVE.is_file() else CORE), "comfy_nodes": len(info),
                           "by_family": dict(sorted(fam.items(), key=lambda x: -x[1]))},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print("v29 count", len(out), "| new", len(new), "| nodes", len(info), "| bytes", len(blob), "| sha", hashlib.sha256(blob).hexdigest()[:16])
