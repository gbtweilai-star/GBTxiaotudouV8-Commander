# 10 · GBT天真：不装 ComfyUI，也跑得动 ComfyUI 的节点契约

> **GBT天真**是本项目给「**触手自己的 ComfyUI 能力**」取的名字
> （主人 2026-10-11 命名：「触手的 ComfyUI 我们取名叫 GBT天真」）。
> 对应能力位 **`comfy_native`**（域 `creation`）。
>
> 一句话：**契约用 ComfyUI 的，算子用我们自己的。** 一张 `workflow.json` 可以直接写 ComfyUI 的节点名，
> 而机器上**不需要装 ComfyUI、不需要起 8188、不需要 GPU**。
>
> 本页读数全部来自 `data/gbt-tianzhen-live.json`（由 `tools/codex-scripts/gen-native-live.py` 每次真跑生成）。

---

## 一、为什么要自己长这一套（而不是"包一层 ComfyUI"）

原话是：「按照 ComfyUI 的节点连接个契约，同样拥有契约和触手连接，他行我们也行」。

包一层 ComfyUI 有三个躲不开的代价：

| 代价 | 具体表现 |
|---|---|
| **重壳** | 要装本体、起 8188、管理它自己的模型目录与插件生态 |
| **重模型** | 真正吃显存的不是"节点"，是节点背后的权重；本机 **AMD 无 CUDA + 7.39 GB 内存**，重模型这条路根本走不通 |
| **不可复跑** | 图形界面里点出来的连线不会自己留证；换台机器就"复现不了" |

**GBT天真 的选择**：把 ComfyUI 拆成两半 —— **契约（可移植）** 与 **算子（可自己长）**。

- **契约**照抄它的：节点名、socket 名与类型、连边语义；
- **算子**用自己的：纯 CPU、内存 < 300 MB、没有权重也能跑的传统算法面；
- **跑不动的那部分如实标"未接"**，不假装能跑。

---

## 二、工作流就是合同（这张图的形状是硬契约）

```json
{
  "nodes": [
    {"id": "n1", "node": "LoadImage",  "inputs": {"image": "reference-front.jpg"}},
    {"id": "n2", "node": "ImageScale", "inputs": {"width": 2416, "height": 4096, "upscale_method": "lanczos"}},
    {"id": "n3", "node": "SaveImage",  "inputs": {"filename_prefix": "albedo"}}
  ],
  "edges": [
    {"from": "n1", "to": "n2", "field": "image->image"},
    {"from": "n2", "to": "n3", "field": "image->image"}
  ]
}
```

> 注意这张图是**用 ComfyUI 的名字写的**（`image` / `upscale_method` / `filename_prefix`），
> 里面没有一个"我们自己的别名"。它能不能跑，就是"同契约"这句话的判据。

四条铁律（写死在实现里，不是口号）：

1. **闸是唯一真源**：产物不过闸（最短边 / 格式 / 非空 / 可解码 / 哈希）⇒ **不许落盘**；
2. **白名单 fail-closed**：不在原生表也不在契约里的节点名 ⇒ 直接报错（与 ComfyUI 的「装个插件就有任意节点」相反，这是**故意**的）；
3. **不编**：缺依赖回 `needs_dependency`，缺权重就说缺权重；
4. **证据只追加**：每次跑落 `store/comfy_native/runs.jsonl`（节点级耗时 + 产物 sha256）。

---

## 三、现读读数（这台机器上，2026-10-21）

| 项 | 读数 | 怎么读出来的 |
|---|---:|---|
| 原生算子 | **27** | `op=nodes` / `op=status` |
| 其中与 ComfyUI **同名同契约** | **18** | `op=contract.native_also_in_contract` |
| 只有我们有（ComfyUI 没同名） | **9** | `ImageLevels` · `ImageHueSaturation` · `ImageTranspose` · `MaskBlur` · `upscale_4k` · `t2i_qwen` · `copy` · `sha` · `info` |
| 对齐的契约面节点总数 | **1495** | `op=contract.contract_nodes`（读 `state/comfyui_object_info.json` 快照） |
| 原生覆盖率 | **1.2%** | 18 / 1495 —— 这个数字**很小，而且我们不修饰它** |
| ComfyUI 进程 | **0** | 全程没有 ComfyUI 在位（也不需要） |

**18 个同名同契约的算子**（可以直接拿 ComfyUI 的节点名来写图，现读列表）：

```
AddTextPrefix · AddTextSuffix · EmptyImage · ImageBatch · ImageBatchMulti · ImageBlend
ImageBlur · ImageCompositeMasked · ImageCrop · ImageInvert · ImagePadForOutpaint
ImageRotate · ImageScale · LoadImage · MaskComposite · MaskToImage · ImageToMask · SaveImage
```

**1495 里没接的 1477 个，按原因分类（不混成一句"暂不支持"）**：

| 未接原因 | 把数 | 含义 |
|---|---:|---|
| 传统算法面：**可原生** | 809 | 纯 CPU 就能长出来，按需再接 |
| 重生成 / 模型面 | 359 | 要权重与 GPU（本机无 CUDA、内存 7.39 GB） |
| 控图 / 检测面 | 290 | 部分可原生（预处理已接），其余需权重 |
| 云端 API 节点 | 19 | 要出网与凭据 |

> **为什么把"覆盖率 1.2%"写在这么显眼的地方**：因为把 1477 个说成"已支持"是最容易的骗法。
> 这里的口径是：**能用 ComfyUI 的节点名写图 = 契约通了；能真跑 = 算子长出来了。** 两件事分开报。

---

## 四、离线校验：不装 ComfyUI 也能验一张图对不对

`op=validate` 用**我们自己的契约**离线判三件事：**未知节点 / 缺必填 / 成环**。

| 用例 | 图 | 结果 |
|---|---|---|
| ✅ 正例（**按 ComfyUI 的写法**） | `LoadImage(image) → ImageScale(width/height/upscale_method) → SaveImage(filename_prefix)` | `verdict=可跑（全在原生表内）` · `errors=[]` |
| ❌ 反例 | 缺必填 `image` + 未知节点 `ImageFantasy` + 缺必填 `height` + `n1↔n2` 成环 | 逐条报错 3 条：未知节点 / 缺必填 / **成环** —— 都被抓到 |

反例是**故意喂的坏图**：它就是"判据自己有没有牙"的负对照 —— 一个只会返回 ok 的校验器等于没有校验器。

### 4.1 为了让"ComfyUI 的图能直接跑"，当场修掉的三处契约失真

> 这一节是整页最值的部分：**自称"同契约"，要拿一张真图去试，试不过就是自称。**

| # | 病 | 根因 | 修法 | 修后读数 |
|---|---|---|---|---|
| 1 | 标准 ComfyUI 图被判「缺必填 `path`」 | `LoadImage` 只登记了内部别名 `path`，而 ComfyUI 的必填 socket 叫 **`image`** | 改成 `image` 必填 + `path?` 选填别名（算子本来就两名都认） | 正例 `errors=[]` |
| 2 | 标准图被判「缺必填 `out`」 | 把**落点**当成必填输入；ComfyUI 里落点叫 `filename_prefix`，且可以不给 | `out` 不参与必填判定；新增 `filename_prefix` 识别，缺省自动落 `store/comfy_native/` | 同上 |
| 3 | 图明明连通，跑到 `SaveImage` 却报「要 image」 | 连边按**字面名**取上一节点输出：边写 `image->image`，而算子把产物回在 `out` 上 ⇒ 取不到 | 取不到字面名时按 socket 名退化（`image` / `text` / `out`） | 写面真跑 3/3 节点 ok |

这三条不是"顺手改的"，是**判据（validate）与执行（run）对不上**的实证：
先由正例被判否暴露，再修到**正例通过、反例仍被抓**。

---

## 五、真跑过的流水（含 sha256，未编辑）

### 5.1 生产资产上的三次真跑（`store/comfy_native/runs.jsonl`，2026-10-18）

| 跑法 | 图（节点） | 结果 | 耗时 | 产物 |
|---|---|---|---|---:|
| 电平归一 | `LoadImage → ImageLevels → SaveImage` | 3/3 节点 ok · 闸 3/3 通过 | 0.21s | 497,986 B · `levels-normalized.png` |
| 放大到 albedo | `LoadImage → ImageScale(2416×4096) → SaveImage` | 3/3 ok · 闸 3/3 | 1.26s | 2,689,801 B · `albedo-2416x4096.png` |
| 4K 重采样 | `LoadImage → upscale_4k(4096) → SaveImage` | 3/3 ok · 闸 3/3 | **8.97s** | **5,337,385 B** · `HERO-4096.png` |

4K 那条的回执细节：

```
from [2416, 4096] → to [4096, 6944]
engine: PIL.lanczos + USM（knobs: size=4096, sharpen=1.0, usm_radius=1, usm_threshold=2）
node 耗时 7958.3 ms（整图 8.97 s）
sha256: 9ff91cefa4468fb5cd3149eaf33c98f6daec5291f7079d3f4441caf48f24d26c
```

> 这就是"传统算法面"的价值：**没有一张显卡，也能把 736×1248 的参考图一路放大到 4096×6944 并留证。**

### 5.2 本页生成时又真跑了一次（写面也跑）

`gen-native-live.py` 每次都会真跑一张小图（落点在被 git 忽略的 `.scratch/`，不进交付树）：

```
LoadImage  ok  56.9ms
ImageScale ok  37.8ms  闸 pass  sha256 3a6fb8cede62a1ff…
SaveImage  ok   0.0ms  闸 pass  sha256 3a6fb8cede62a1ff…
产物 2 个：store/comfy_native/scale_597724.png · .scratch/comfy-live-check/out.png
```

同一支脚本再拿**坏图**跑一次：`ok=false`，`error=user_error: 白名单里没有这些节点：['ImageFantasy']`，
**一件产物都没落** —— 这就是 fail-closed 的负对照：白名单/缺必填/成环任一不过，盘上不留东西。

---

## 六、写面到底要不要票（口径如实说清）

| op | 门 | 结果 |
|---|---|---|
| `status` `nodes` `graph` `gate` `contract` `validate` | 只读，免门 | ✅ 真跑 |
| `run`（真跑图、真落盘） | 走**同一道** `run_task` 门，落审计 + `runs.jsonl` | ✅ 真跑（见 5.2） |

**为什么写面不用票**：主人 2026-10-19 令「除了黑客全能力和转账要票其他都去掉」，现行
`ENFORCED_SCOPES` 只剩**浏览器/桌面/设备/内网/隐私/进程/远端/发声/数据外发/外部大模型/生产发布/强制放行**这一组；
`filesystem_write` 已**不在**要票集合里 ⇒ 写盘由门放行，但**仍然过闸、仍然留痕**。

> 别把这条读成"没有护栏"：闸（产物必须可解码/非空/尺寸合规）是**唯一真源**，过不了闸就不认这一跑。

---

## 七、边界（先说清，别让读者猜）

1. **重生成模型一律未接**：文生图 / 图生图 / 神经超分要权重 + GPU，本机 AMD 无 CUDA、内存 7.39 GB ⇒ 跑不动。这条写在 `status.unable` 与 `status.honest` 里，不是本页临时说的。
2. **`t2i_qwen` 是"接线位"**：它把文生图请求转到我们的模型链上（不本地跑权重），本地不产图 ⇒ 不算"原生出图能力"。
3. **解释器口径**：图算子依赖 **Pillow 12.3.0**，现装在本机 `py 3.12`；`py 3.14` 里 Pillow 缺位 ⇒ 在 3.14 口下 `status.deps` 会如实报 `PIL 缺失`。**跑图用 3.12，跑门用 3.14**。
4. **1495 是快照**，不是"现在连着 ComfyUI 的实时节点表"（快照 ≠ 在线）。
5. **契约同名 ≠ 行为逐位相同**：同名同 socket 只保证"图能连通、参数能对上"；个别算子的重采样滤波/边界处理与上游实现可能有细微差异。
6. **覆盖率 1.2% 就是 1.2%**：1477 个未接节点按原因分类列出，不并成"基本都支持"。

---

## 八、怎么自己跑一遍

```bash
# 只读面（免门，随便调）
py -3.14 -m gbt_allinone run comfy_native '{"op":"status"}'
py -3.14 -m gbt_allinone run comfy_native '{"op":"contract"}'
py -3.14 -m gbt_allinone run comfy_native '{"op":"validate","workflow":"my_workflow.json"}'

# 写面（要 Pillow ⇒ 用 3.12 口；不需要发票，但产物必须过闸才会被认账）
py -3.12 -m gbt_allinone run comfy_native '{"op":"run","workflow":"my_workflow.json"}'
```

配套的**创作融合台** `comfy_forge`（同一份 1495 节点快照，按创作用途分 7 族）负责回答
"我想做 X，该用哪些节点" —— 只读、零作用域。

---

## 九、和别的三处 ComfyUI 面的边界

| 能力位 | 它是什么 | 什么时候用它 |
|---|---|---|
| **`comfy_native`（GBT天真）** | 我们自己的算子在跑我们的契约，**不需要 ComfyUI** | 传统算法面（放大/裁剪/拼贴/格式/校验/哈希/锐化） |
| `comfyui` | 外部 ComfyUI 本体的**全控**（起停、队列、模型） | 本机真装了 ComfyUI，要管它 |
| `tentacle_comfy_bridge`（第 1530 根触手） | 把外部 ComfyUI 当**贴图工厂 / 概念工厂**，双向绑定 | 要用它那些重模型 |
| `comfy_forge` | 1495 节点的**分族地图**（只读快照） | 想知道"这个用途有哪些节点" |

> 别把四者混成一句"支持 ComfyUI"。**能跑自己的算子**和**能指挥别人的 ComfyUI** 是两种能力。
