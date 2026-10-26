# 19 · GBT天真 使用手册（comfy_native）

> 设计原理见 [10-gbt-tianzhen.md](10-gbt-tianzhen.md)；本页只讲**怎么用**，
> 每条命令都在本机（iPhone · iSH）实跑过，读数原样贴出。
>
> 一句话：**契约用 ComfyUI 的，算子用我们自己的。**
> 不装 ComfyUI、不起 8188、不要 GPU、不下任何权重。

---

## 一、三种调用方式

### ① Python 直接调（最快）

```python
import sys; sys.path.insert(0, '.')
from gbt_allinone.tools import comfy_native as cn

cn.run({"op": "status"})      # 能力自述：27 个算子、依赖状态、能做什么/不能做什么
cn.run({"op": "nodes"})       # 27 个算子的输入输出契约
cn.run({"op": "contract"})    # 对齐全 ComfyUI 契约面（1495 个节点名）
```

### ② 跑一张工作流（ComfyUI 名字直接写）

```python
wf = {
  "nodes": [
    {"id": "n1", "node": "LoadImage",   "inputs": {"image": "in.png"}},
    {"id": "n2", "node": "ImageScale",  "inputs": {"width": 1208, "height": 2048,
                                                   "upscale_method": "lanczos",
                                                   "out": "scaled.png"}},
    {"id": "n3", "node": "ImageLevels", "inputs": {"black": 4, "white": 251, "gamma": 1.08,
                                                   "out": "levels.png"}},
    {"id": "n4", "node": "SaveImage",   "inputs": {"out": "final.png"}},
  ],
  "edges": [
    {"from": "n1", "to": "n2", "field": "IMAGE->image"},
    {"from": "n2", "to": "n3", "field": "IMAGE->image"},
    {"from": "n3", "to": "n4", "field": "IMAGE->image"},
  ],
}
r = cn.run({"op": "run", "workflow": wf})
# → {"ok": True, "products": ["final.png"], "trace": [...每节点耗时...],
#    "seconds": 10.48, "note": "证据已追加到 store/comfy_native/runs.jsonl"}
```

**边上的 `field` 写 `输出名->输入名`。** 两套名都认：
ComfyUI 的 socket 名（`IMAGE`）和我们的产物名（`image` / `out`）都能通。

### ③ 单跑一个算子

```python
cn.run({"op": "upscale_4k",
        "inputs": {"image": "in.png", "size": 4096,
                   "sharpen": 0.6, "usm_radius": 2, "out": "big.png"}})
```

> 🔴 **参数一定包在 `inputs` 里。** 写成 `{"op":"LoadImage","image":"x.png"}`
> 会报 `图不在：None` —— 单节点入口只读 `payload["inputs"]`。

### ④ 经模型桥派活（给页面/外部调用）

```sh
curl -X POST http://127.0.0.1:8791/v1/dispatch \
  -H 'Content-Type: application/json' \
  -d '{"capability":"comfy_native","op":"status"}'
```
**写盘/花钱/出网类会过 `run_task` 唯一门**，缺票就如实回 `denied`，不绕。

---

## 二、27 个原生算子（`op=nodes` 实读）

**图像**：`LoadImage` `SaveImage` `ImageScale` `ImageCrop` `ImageRotate`
`ImageTranspose` `ImageInvert` `ImageBlur` `ImageLevels` `ImageHueSaturation`
`ImageBlend` `ImageCompositeMasked` `ImageBatch` `ImageBatchMulti`
`ImagePadForOutpaint` `EmptyImage` `upscale_4k`

**遮罩**：`MaskBlur` `MaskComposite` `MaskToImage` `ImageToMask`

**文本**：`AddTextPrefix` `AddTextSuffix`

**工具**：`sha` `info` `copy` `t2i_qwen`

其中 **18 个与 ComfyUI 同名同契约**，9 个只有我们有
（`ImageLevels` · `ImageHueSaturation` · `ImageTranspose` · `MaskBlur` ·
`upscale_4k` · `t2i_qwen` · `copy` · `sha` · `info`）。

**白名单 fail-closed：** 不在表里也不是契约节点的名字，直接报错，不猜。
（这与 ComfyUI「装个插件就有任意节点」相反，**是故意的**。）

---

## 三、本机实跑读数（iPhone · A19 Pro · iSH）

一条四节点链（源图 2416×4096 · 2.7 MB）：

```
LoadImage            458 ms
ImageScale → 1208×2048 lanczos    6813 ms
ImageLevels (gamma 1.08)          2132 ms
SaveImage              44 ms
────────────────────────────────
整链                 10.48 s     闸全过 ✅
```

**真出 4K（`upscale_4k` 默认 `size=4096`）：**

```
256×256 源图 → 4096×4096（6700 万像素）· LANCZOS + USM 锐化
实测 127 秒 · 纯 CPU · 显存 0
```

> ⚠️ 这 127 秒是**模拟层的成本**。iSH 是 x86 翻译执行，不是 A19 硬件的真实速度。

**每个写节点产物都过闸**（最短边 / 格式 / 非空 / 可解码 / 哈希），
**不过闸不落盘、不认账**。证据逐次追加到 `store/comfy_native/runs.jsonl`。

---

## 四、出图流水线（免费路）

```
提示词 → 天真 t2i_qwen → 自动 taste 体检 → 不过就改提示词/参数 → 再跑
              ↑                                      |
              └──────────── gen_loop.py ─────────────┘
```

**`t2i_qwen` 要一个端点**，本机不自带生成权重（无 CUDA、显存不够）：

```sh
export GBT_T2I_ENDPOINT="https://你的端点/v1/images"
```

没配就拿不到图，会如实报 `needs_dependency` —— **不编**。

本地这一侧能做的、也是实测撑得住的，是**传统算法放大**：

```
665×886  →  2048×2729   本地 LANCZOS + USM
```

毛发、毛孔、金饰反射都撑得住 —— 这是免费路能拿到的最高一档。

### 两条硬约束（实测，不是不肯做）

| 约束 | 读数 | 说明 |
|---|---|---|
| **45 秒一张** | `1 image every 45 seconds` | 免费额度实测，闭环每轮之间必须睡 50 秒，三轮 ≈ 3 分钟 |
| **627×940 封顶** | — | 清晰度只能靠**原生大图**，免费路给不了 |

**要是有端点，把 `GBT_T2I_ENDPOINT` 换掉，这套闭环立刻能跑原生 2K、
无水印、不排队 —— 代码一行都不用改。**

---

## 五、证据（`docs/gallery/`）

| 图 | 是什么 |
|---|---|
| [00-poster.jpg](gallery/00-poster.jpg) | 开源海报：341 位能力 / 20000 路并发 / 4.88 GB 手机能跑 |
| [01-a19-selfcheck.png](gallery/01-a19-selfcheck.png) | 本机 A19 自检（`gbt-v8-v82-q5_0` · 257/4096 上下文） |
| [02-tianzhen-upscale-2048x2729.png](gallery/02-tianzhen-upscale-2048x2729.png) | **665×886 → 2048×2729**，本地 LANCZOS+USM 放大 |
| [03-tianzhen-product-closeup.png](gallery/03-tianzhen-product-closeup.png) | 放大后的特写：毛孔 / 毛发走向 / 耳朵血管 / 眼睛高光 |
| [04-tianzhen-pipeline-constraints.png](gallery/04-tianzhen-pipeline-constraints.png) | 流水线形状 + 两条硬约束原文 |
| [05-tianzhen-3frame-strip.png](gallery/05-tianzhen-3frame-strip.png) | 三帧拼条 `1080×540`：蓄势→甩击→撞击，看动效连不连贯 |
| [06-tianzhen-product-p5.png](gallery/06-tianzhen-product-p5.png) | P5 产物 |
| [07-capability-doc-alignment.png](gallery/07-capability-doc-alignment.png) | 能力文档对齐复盘：触发词可搜性实测（放大/洗图/高清/4K） |

---

## 六、踩过的坑（都在这台机上真踩的）

### ① PIL 缺失 ⇒ 27 个算子里图像类全废

`op=status` 的 `deps` 会如实报 `"PIL": "缺失(ModuleNotFoundError)"`。

```sh
apk add py3-pillow          # iSH/Alpine：走系统包，别 pip install
```
装完 `deps` 立刻变 `"PIL": "11.0.0"`。

### ② 单节点调用必须包 `inputs`

```python
cn.run({"op":"LoadImage", "image":"x.png"})            # 🔴 报「图不在：None」
cn.run({"op":"LoadImage", "inputs":{"image":"x.png"}}) # ✅
```

### ③ `upscale_4k` 默认就拉满 4096 宽

256×256 的图进去也会被拉到 4096×4096（6700 万像素），单张 127 秒。
**想快就显式给 `size`**：

```python
{"image": "in.png", "size": 2048, "out": "out.png"}   # 2048 宽，约 32 秒
```

### ④ `sharpen: 0` 曾经被吞成 0.6

已修：三个旋钮（`sharpen` / `usm_radius` / `usm_threshold`）现在**传 0 就是 0**，
不传才走默认。

### ⑤ 并发压不上去，跟算子无关

- **线程栈**：iSH 默认 **128 MB/线程**（不是 8 MB）⇒ 4.1 GB / 128 MB = 32。
  压到 512 KB 后同样内存能开数千连接。
- **监听队列**：`socketserver` 默认 **backlog = 5** ⇒ 96 路就开始假崩。
  已改成按压力自适应（见 [17 · 第十二节](17-phone-a19-runtime.md)）。

---

## 七、不能做的（如实标，不假装）

| 不能做 | 原因 |
|---|---|
| 文生图 / 图生图（本地） | 要生成权重 + GPU，本机没有 |
| 神经超分（spandrel 那类） | 要权重 + 内存 |
| 任意 ComfyUI 第三方节点 | 白名单 fail-closed，**故意不开放** |

**27 个算子对 1495 个契约节点的覆盖率是 1.2% —— 这个数字很小，我们不修饰它。**

---

**开发者：自由的风 · 守护者：公主土豆**
**本署名不可删除、不可篡改归属。**
