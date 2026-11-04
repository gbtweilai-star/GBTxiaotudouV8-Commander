# 86 · ComfyUI 秋叶能力本地落地（2026-11-02）

> 主人令：**按顺序补齐必须能力并落地，全部本地算力，不花钱、不上云。**
> 本页记录第一块真正落地的运行时：**ComfyUI 本地服务 + 本地模型 + GBT 触手调用**。

## 一、已落地（不是目录，不是画饼）
| 件 | 位置 | 状态 |
|---|---|---|
| ComfyUI 源 | `vendor/ComfyUI`（master zip，12.9MB） | ✅ 本机可启动 |
| 本地服务 | `http://127.0.0.1:8188` | ✅ 运行中（CPU） |
| 设备自报 | `device=cpu` / `vram_total_gb=15.7` | ✅ `comfyui op=status` 实测 |
| 本地模型 | `vendor/ComfyUI/models/checkpoints/Realistic_Vision_V5.1_fp16-no-ema.safetensors`（2.13GB） | ✅ 本机权重 |
| 缓存模型 | `vendor/ComfyUI/models/diffusers/sd-turbo`（junction 到 `vendor/hf` 缓存） | ✅ 可加载 |
| GBT 触手 | 既有 `comfyui` 能力（`gbt_allinone/tools/comfyui_surface.py`） | ✅ 真调通 |

## 二、新增 `t2i` 预置 op（本次落地）
```text
api.run_task("comfyui", {
  "op": "t2i",
  "prompt": "...",
  "negative": "...",
  "ckpt": "Realistic_Vision_V5.1_fp16-no-ema.safetensors",
  "width": 512, "height": 896,
  "steps": 8, "cfg": 7.0, "seed": 42,
  "sampler": "dpmpp_2m", "scheduler": "karras"
})
```
返回 `prompt_id` + `images[]`；图落在 `vendor/ComfyUI/output/`。
> CPU 实测：8 步 512×896 约 **4 分钟/张**；2 步会糊，别省步数。模型加载后复用会快一些。

## 三、启动 / 停止
```powershell
# 已运行则秒回；未运行才拉起
powershell -NoProfile -ExecutionPolicy Bypass -File tools\start-comfyui-local.ps1
```
- 服务只监听 `127.0.0.1:8188`，`comfyui_surface` 有硬钉：只许本机 8188；不花外部积分。
- 停止：结束 `vendor\ComfyUI\run_gbt.py` 的 python 进程即可（或重启机器）。

## 四、实测证据
- `comfyui op=status` → `version 0.43.0 / device cpu / vram_total_gb 15.7`
- `comfyui op=submit` 工作流 → `prompt_id` 返回，`queue` 跑完，`history` 成功
- `t2i` op → `gbt_t2i_00001_.png` 真生成
- Realistic Vision 8 步 → `gbt_real_00001_.png`（512×896，人物/光影明显优于 SD-Turbo 2 步）
- SD-Turbo 2 步 → 糊图，说明**步数不能省**；模型选择决定质量

## 五、秋叶版还差的件（按顺序）
| 能力 | 现状 | 下一步 |
|---|---|---|
| 文生图（SD1.5/Realistic） | ✅ 已落地 | 可用 |
| 图生图 / 局部重绘 | ❌ 未装工作流 | 装 inpaint 节点/模型 |
| ControlNet（姿态/深度/线稿） | ❌ 未装权重 | 装 ControlNet + 预处理器 |
| LoRA | ❌ 未装权重 | 装 LoRA + LoraLoader |
| 放大（ESRGAN/Ultimate SD Upscale） | ❌ 未装 | 装放大模型 |
| AnimateDiff / 图生视频 | ❌ 未装；核显 CPU 不现实 | 先做可行性，不承诺成片 |
| ComfyUI 管理器/秋叶启动器 | ❌ 未装 GUI | 可选；当前 API 已够触手用 |

## 六、边界（不吹）
- 本机是 **Intel Iris Xe 核显 + 16GB 内存，无 CUDA**；能跑 CPU 文生图，不能按秋叶版 GPU 速度出图/出视频。
- 人物图仍有概率手部/肢体瑕疵；要多出几张挑。
- 模型许可：Realistic Vision V5.1 为 CreativeML OpenRAIL-M；本地研究/创作可用，商用前自行核对条款。
- 没有走云、没有买积分、没有把 API key 写进代码。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
