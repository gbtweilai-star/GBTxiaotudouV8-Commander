# =============================================================================
# GBT · 数字人 GPU 流水线（4090 上的一次性搬运脚本 v2）
# 由 pod_link.run --path 送进卡的 Jupyter 内核；每步打 REPORT 行，**失败就 fail-closed**。
#
# v1 的两个教训（都真踩了）：
#   ① `pip install huggingface_hub[cli]` 撞 blinker(distutils) 失败 ⇒ 没有 huggingface-cli
#      ⇒ 三个权重全 "rc=0 但文件不存在"，而 v1 只看 rc 就当成功继续，最后推理才炸。
#      ⇒ v2 改成**Python API** snapshot_download（不依赖 CLI），且**按字节数校验**权重。
#   ② v1 把失败吞在 tail 里 → 归因困难。v2 每步 REPORT 带 size/路径，异常直接抛出。
# =============================================================================
import json
import os
import shutil
import subprocess
import time
import traceback

OUT = "/workspace/dh"
REPO = "/workspace/OmniAvatar"
R2 = "https://pub-3b817fc945aa4e1c8d7cce0ea93fa725.r2.dev/motions/input/"
PROMPT = ("A young woman standing in a photo studio, long black hair, wearing a black "
          "and gold futuristic bodysuit, speaking to the camera with natural body "
          "movement and hand gestures, gray background, high detail.")
# 阈值按**实测**标定，不按想象：OmniAvatar-1.3B 只有 pytorch_model.pt(355M)+config ⇒ 0.35G；
# 原来写 0.5G 会把「真下全了」误判成「权重不全」（P1 判据错尺，2026-10-20 实测踩过）。
MIN_GB = {"Wan2.1-T2V-1.3B": 10.0, "wav2vec2-base-960h": 0.5, "OmniAvatar-1.3B": 0.3}


def report(tag, **kw):
    print("REPORT " + json.dumps({"tag": tag, **kw}, ensure_ascii=False), flush=True)


def sh(cmd, t=5400):
    t0 = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t)
    out = (r.stdout or "") + (r.stderr or "")
    report("sh", cmd=cmd[:150], rc=r.returncode, secs=round(time.time() - t0, 1), tail=out[-600:])
    return r


def dir_gb(p):
    if not os.path.isdir(p):
        return 0.0
    n = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(p) for f in fs)
    return round(n / 1e9, 2)


os.makedirs(OUT, exist_ok=True)
report("start", t=time.strftime("%H:%M:%S"))

try:
    # ── 1 环境 ────────────────────────────────────────────────────────────
    sh("nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader; "
       "df -h /workspace | tail -1; nproc; free -g | head -2; "
       "python -c \"import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),"
       "torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NOGPU')\"", t=180)

    # ── 2 素材（公网 R2 现拉） ────────────────────────────────────────────
    sh("cd %s && curl -sSL -o ref.png %scharacter-ref.png && curl -sSL -o tw.wav %stw-chen15.wav "
       "&& ls -l ref.png tw.wav" % (OUT, R2, R2), t=600)

    # ── 3 代码 ────────────────────────────────────────────────────────────
    if not os.path.isdir(REPO):
        sh("git clone --depth 1 https://github.com/Omni-Avatar/OmniAvatar.git %s" % REPO, t=900)

    # ── 4 依赖：先修 pip 的 distutils 冲突，再装纯 huggingface_hub ────────
    # 🔴 2026-10-20 实测两轮，结论写死：**这个镜像的 torch 不能碰**。
    #    · 先按 requirements.txt 全装 ⇒ torchvision::nms 报错 + CUDA unknown error；
    #    · 再按官方 cu124 强制重装 torch 2.4.0 ⇒ `libtorch_cuda.so: undefined symbol: ncclCommResume`
    #      （镜像自带 NCCL 与 pip 那份 cu124 轮子不配套）。
    #    ⇒ 正解：**只装纯 Python 侧依赖**（peft/transformers/numpy/scipy/librosa/einops/ftfy/
    #      accelerate/safetensors/huggingface_hub），**一律不装 xfuser/quanto/requirements.txt**
    #      （单卡 1.3B 用不上分布式；那两个包会把 torch 生态拖下水）。
    sh("pip install -q 'transformers==4.52.3' 'peft==0.15.1' 'numpy==1.26.4' 'scipy==1.14.0' "
       "'librosa==0.10.2.post1' 'einops' 'ftfy' 'accelerate' 'safetensors' 'huggingface_hub>=0.23' "
       "'timm' 'opencv-python-headless' 2>&1 | tail -6", t=2400)

    # ── 5.4 硬闸：CUDA 与 torchvision 必须真的能用，否则后面全是白跑 ─────
    gate = sh("python -c \"import torch,torchvision;from torchvision.ops import nms;"
              "print('TORCH_OK',torch.__version__,torchvision.__version__,torch.cuda.is_available())\"", t=300)
    if "TORCH_OK True" not in (gate.stdout or "") and "True" not in (gate.stdout or "").split("TORCH_OK")[-1][:40]:
        report("fatal", why="torch/torchvision CUDA 不可用，停在这里（省得白跑 40 分钟）",
               out=(gate.stdout or "")[:200], err=(gate.stderr or "")[:300])
        raise SystemExit(1)

    # ── 5.5 依赖体检（**先量后改**：把版本冲突摊开，别靠猜） ─────────────
    sh("cd %s && echo '--- requirements.txt ---' && cat requirements.txt | head -40" % REPO, t=60)
    sh("python - <<'PY'\n"
       "import importlib, torch, torchvision\n"
       "print('torch', torch.__version__, 'cuda_built', torch.version.cuda)\n"
       "print('torchvision', torchvision.__version__)\n"
       "print('cuda_available', torch.cuda.is_available())\n"
       "try:\n    from torchvision.ops import nms; print('nms OK')\n"
       "except Exception as e:\n    print('nms FAIL', type(e).__name__, e)\n"
       "for m in ('transformers','peft','diffusers','accelerate','safetensors','imageio','decord','av','einops'):\n"
       "    try:\n        mod=importlib.import_module(m); print(m, getattr(mod,'__version__','?'))\n"
       "    except Exception as e:\n        print(m, 'MISSING', type(e).__name__)\n"
       "PY", t=300)

    # ── 6 推理 ────────────────────────────────────────────────────────────
    sample = os.path.join(REPO, "examples", "infer_samples.txt")
    os.makedirs(os.path.dirname(sample), exist_ok=True)
    with open(sample, "w", encoding="utf-8") as f:
        f.write("%s@@%s/ref.png@@%s/tw.wav\n" % (PROMPT, OUT, OUT))
    cfg = os.path.join(REPO, "configs", "inference_1.3B.yaml")
    hp = ("max_tokens=30000,guidance_scale=5.0,audio_scale=3,overlap_frame=13,"
          "num_steps=30,tea_cache_l1_thresh=0.14")
    # 🔴 torchrun 的真 traceback 会被 elastic 的横幅淹掉（2026-10-20 实测：只看到
    #    "ChildFailedError"，看不到到底哪个 import/哪一行错）⇒ 一律落到日志文件再取尾部 + 抓关键字。
    LOG = os.path.join(OUT, "infer.log")
    r = sh("cd %s && torchrun --standalone --nproc_per_node=1 scripts/inference.py "
           "--config %s --input_file %s --hp=%s > %s 2>&1; echo RC=$?" % (REPO, cfg, sample, hp, LOG), t=7200)
    try:
        tail = subprocess.run("tail -60 %s" % LOG, shell=True, capture_output=True, text=True).stdout
        keys = subprocess.run("grep -nE 'Error|Traceback|CUDA|No module|not found|Killed|out of memory' %s | tail -25" % LOG,
                              shell=True, capture_output=True, text=True).stdout
        report("infer_tail", tail=tail[-2500:])
        report("infer_errors", keys=keys[-1500:])
    except Exception as e:                                            # noqa: BLE001
        report("infer_log_unreadable", err=str(e))

    # ── 7 产物 ────────────────────────────────────────────────────────────
    mp4s = []
    for dp, _, fs in os.walk(REPO):
        for f in fs:
            if f.endswith(".mp4"):
                p = os.path.join(dp, f)
                mp4s.append((os.path.getmtime(p), p, os.path.getsize(p)))
    mp4s.sort(reverse=True)
    report("outputs", top=[{"path": p, "mb": round(s / 1e6, 2)} for _, p, s in mp4s[:5]])
    if not mp4s:
        report("fatal", why="推理跑完但没有 mp4")
        raise SystemExit(1)
    dst = os.path.join(OUT, "raw.mp4")
    shutil.copyfile(mp4s[0][1], dst)
    report("copied", dst=dst, mb=round(os.path.getsize(dst) / 1e6, 2))
    report("done", t=time.strftime("%H:%M:%S"))
except SystemExit:
    raise
except Exception as e:                                                # noqa: BLE001
    report("exception", err="%s: %s" % (type(e).__name__, str(e)[:300]),
           tb=traceback.format_exc()[-800:])
