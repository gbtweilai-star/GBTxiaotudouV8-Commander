# =============================================================================
# 🔴 已退役（Owner 2026-10-21 拍板「甲」）—— 别再拿它跑钱。
#    退役理由（§75 实证，不是"跑不通"）：全身 400×720 取景下嘴只有 ~40×12 px，
#    口型物理不可达；单窗口实测「静音段嘴照样大动」⇒ 音频根本没驱动嘴唇。
#    在役交付线改走 SadTalker（tools/digihuman/finish-clip.py → fullbody-tw-v5/v6）。
#    本文件留着只为：pod-hud.py launch / gpu-avatar.py 两个入口还指着它（删了会砸入口）；
#    要复活这条线，先读 journal §75 的四条阻断事实，别重复烧卡。
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
LOGF = "/workspace/dh/run.log"          # 卡上落一份日志：本机不必占着内核通道也能看进度（用 op=down 取回，零作用域）
R2 = "https://pub-3b817fc945aa4e1c8d7cce0ea93fa725.r2.dev/motions/input/"
PROMPT = ("A young woman standing in a photo studio, long black hair, wearing a black "
          "and gold futuristic bodysuit, speaking to the camera with natural body "
          "movement and hand gestures, gray background, high detail.")
# 阈值按**实测**标定，不按想象：OmniAvatar-1.3B 只有 pytorch_model.pt(355M)+config ⇒ 0.35G；
# 原来写 0.5G 会把「真下全了」误判成「权重不全」（P1 判据错尺，2026-10-20 实测踩过）。
MIN_GB = {"Wan2.1-T2V-1.3B": 10.0, "wav2vec2-base-960h": 0.5, "OmniAvatar-1.3B": 0.3}


def report(tag, **kw):
    line = "REPORT " + json.dumps({"tag": tag, **kw}, ensure_ascii=False)
    print(line, flush=True)
    try:                                    # 卡上再落一份：本机掉线/通道断也能事后看（2026-10-20 加）
        with open(LOGF, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:                                            # noqa: BLE001
        pass


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
    # 🔴 2026-10-20 第四轮实测修正：**必须按仓库 requirements.txt 的钉版本装**，不许装最新。
    #   仓库钉的是：librosa==0.10.2.post1 · peft==0.15.1 · transformers==4.52.3 · scipy==1.14.0 ·
    #                numpy==1.26.4 · xfuser==0.4.1 · ftfy · einops
    #   我第一次装 latest xfuser + 升级 peft，结果 import 到 `flash_attn` 签名不匹配直接 TypeError。
    #   另配 diffusers==0.31.0（跟 peft 0.15.1 同代；更新的 diffusers 会要求 peft>=0.17，把仓库钉版顶掉）。
    #   全程 --no-deps：**绝不碰镜像自带的 torch 2.4.1+cu124**（前两轮就是被 pip 拖下水）。
    # 🔴 2026-10-20 第五轮定稿（把「在卡上逐个人肉补」的清单**全部固化进这里**，新卡一次到位）：
    #    huggingface_hub 必须钉 0.30.2（装 >=0.23 会解析成 2.x，diffusers 0.31 直接报
    #    "huggingface-hub>=0.30.0,<1.0 is required … found 2.2.0"）；
    #    tokenizers 钉 0.21.1（transformers 4.52.3 要 >=0.21,<0.22）；
    #    lazy_loader（librosa 依赖，--no-deps 会漏）、distvae/yunchang（xfuser 依赖）、
    #    msgpack、numba+llvmlite、nvidia-ml-py（pynvml）、joblib+cloudpickle+threadpoolctl+
    #    scikit-learn+narwhals（scipy 生态缺一不可）。
    sh("pip install -q --no-deps 'librosa==0.10.2.post1' 'peft==0.15.1' 'transformers==4.52.3' "
       "'scipy==1.14.0' 'numpy==1.26.4' 'xfuser==0.4.1' 'ftfy' 'einops' 'tqdm' "
       "'diffusers==0.31.0' 'imageio' 'imageio-ffmpeg' 'av' 'decord' 'accelerate' 'safetensors' "
       "'timm' 'opencv-python-headless' 'huggingface_hub==0.30.2' 'tokenizers==0.21.1' "
       "'lazy_loader' 'soundfile' 'pooch' 'soxr' 'audioread' 'distvae' 'yunchang' 'msgpack' "
       "'numba==0.60.0' 'llvmlite==0.43.0' 'nvidia-ml-py' 'joblib' 'cloudpickle' "
       "'threadpoolctl' 'scikit-learn' 'narwhals' 2>&1 | tail -6", t=2400)

    # ── 4.1 ffmpeg：镜像里没有，模型内部会直接 `ffmpeg` 写视频 ⇒ 必须自己铺一条 ──
    #    （2026-10-20 实测：不铺就 `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'`）
    sh("python -c \"import imageio_ffmpeg, shutil, os; src=imageio_ffmpeg.get_ffmpeg_exe(); "
       "dst='/usr/local/bin/ffmpeg'; shutil.copy(src, dst); os.chmod(dst, 0o755); print('FFMPEG', "
       "os.path.getsize(dst))\"", t=300)

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

    # ── 5.6 自愈式依赖补齐（2026-10-20 第三次实测：光补 imageio 不够，`wan_video_dit.py` 第 10 行还硬 import xfuser）──
    # 做法：**逐个 import 到通为止**——把 OmniAvatar 的入口模块真 import 一次，谁缺就装谁（一律 --no-deps，
    # 绝不让 pip 动 torch/torchvision，这是前两轮炸机的根源），最多补 6 轮。缺谁一眼能从 REPORT 里看到。
    PKG = {"imageio": "imageio", "decord": "decord", "av": "av", "xfuser": "xfuser", "quanto": "quanto",
           "diffusers": "diffusers", "timm": "timm", "ftfy": "ftfy", "einops": "einops", "msgpack": "msgpack",
           "yunchang": "yunchang", "imageio_ffmpeg": "imageio-ffmpeg"}
    probe = ("cd %s && python -c \"import OmniAvatar.models.model_manager as m; print('IMPORT_OK')\"" % REPO)
    for k in range(6):
        r = sh(probe, t=600)
        out = (r.stdout or "") + (r.stderr or "")
        if "IMPORT_OK" in out:
            report("import_gate", ok=True, rounds=k)
            break
        miss = ""
        for line in out.splitlines():
            if "ModuleNotFoundError" in line and "No module named" in line:
                miss = line.split("No module named")[-1].strip().strip("'\"").split(".")[0]
        # 版本门（2026-10-20 第三次实测）：diffusers 的 `dep_version_check("peft")` 会因为版本太老直接抛，
        # 形状长得像"缺包"但其实是**版本** ⇒ 解析出包名后 `-U` 升级（仍 --no-deps，不碰 torch）。
        if not miss:
            for line in out.splitlines():
                for tag in ("dep_version_check(\"", "dep_version_check('", "require_version(\""):
                    if tag in line:
                        miss = line.split(tag)[-1].split("\")")[0].split("')")[0].strip()
                        break
                if miss:
                    break
        report("import_gate", ok=False, round=k + 1, missing=miss or "未解析出模块名", tail=out[-400:])
        if not miss:
            # 2026-10-20 第四轮：走到这里通常是**版本/签名**问题（不是缺包）——钉版本那一步已经装齐，
            # 再瞎装只会越装越乱。把完整 traceback 留在日志里，人看一次就够。
            report("fatal", why="import 不通且不是缺包（多为版本/签名不匹配）⇒ 停，不再瞎装",
                   tail=out[-1500:])
            raise SystemExit(3)
        pkg = PKG.get(miss, miss)
        # 缺的包只装不升（不 -U），避免把 requirements 的钉版本顶掉
        sh("pip install -q --no-deps %s 2>&1 | tail -3" % pkg, t=1200)
    else:
        report("fatal", why="依赖补到 6 轮还没 import 通，停（省得白跑）")
        raise SystemExit(1)

    # ── 5.7 权重：**payload 自己下**（2026-10-20 实测：不写这一步，新卡必然
    #    `assert os.path.exists(ckpt_path), "pytorch_model.pt not found"`）──────────
    #    repo 名认准 `OmniAvatar/OmniAvatar-1.3B`（带连字符的 `Omni-Avatar/…` 是 401 不存在）。
    #    已存在且够大就跳过，避免二次启动重复拉 19GB。
    WANT = [("Wan-AI/Wan2.1-T2V-1.3B", "Wan2.1-T2V-1.3B", 10.0),
            ("facebook/wav2vec2-base-960h", "wav2vec2-base-960h", 0.5),
            ("OmniAvatar/OmniAvatar-1.3B", "OmniAvatar-1.3B", 0.3)]
    dl_code = ("import os, shutil\n"
               "from huggingface_hub import snapshot_download\n"
               "base = %r\n"
               "jobs = %r\n"
               "for repo, name, min_gb in jobs:\n"
               "    dst = os.path.join(base, name)\n"
               "    have = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(dst) for f in fs) / 1e9 if os.path.isdir(dst) else 0\n"
               "    if have >= min_gb:\n"
               "        print('DL_SKIP', name, round(have, 2)); continue\n"
               "    p = snapshot_download(repo_id=repo, cache_dir='/workspace/hf', max_workers=8)\n"
               "    shutil.copytree(p, dst, dirs_exist_ok=True)\n"
               "    got = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(dst) for f in fs) / 1e9\n"
               "    print('DL_OK', name, round(got, 2))\n"
               % (os.path.join(REPO, "pretrained_models"), WANT))
    dlp = os.path.join(OUT, "dl_weights.py")
    with open(dlp, "w", encoding="utf-8") as f:
        f.write(dl_code)
    sh("python %s" % dlp, t=5400)

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
