# 59 · GBT天真 ↔ 秋叶版 ComfyUI 一比一（2026-11-01）

> 主人口径：「现在全面补齐 GBT天真 跟秋叶版一比一」。

---

## 一、先讲清「一比一」到底能测到什么

| 参照 | 能不能离线拿到 | 本工具怎么用 |
|---|---|---|
| **秋叶整合版真快照**（约 1495 把 = ComfyUI 核心 + 插件） | ❌ 必须在装了秋叶版的机器上跑 `GET /object_info` | 放到 `state/comfyui_object_info.json`，工具**优先**读它 |
| **ComfyUI 核心面**（nodes.py + comfy_extras + comfy_api_nodes） | ✅ 可从 codeload zip 复现 | 退到 `state/comfyui_ref_nodes.json`，**输出里明确标注「非秋叶整包」** |

**绝不把「核心面 127 把」冒充成「秋叶 1495 把」** —— 这是本仓的口径线。

## 二、这一轮真做了什么

### 1. 补上运行前提（此前根本没有）

`comfy_native` 的自检写着 `PIL 缺失 / numpy 缺失` —— 也就是说**算子一个都跑不起来**。
嵌入式 Python（`pyembed`，3.12.10）没有 pip，于是：

```
① 从 PyPI 直接下 cp312-win_amd64 wheel（Pillow 13.0.0 / numpy 2.5.4）
② 解压进 pyembed\Lib\site-packages
③ python312._pth 追加 Lib\site-packages（必须无 BOM，否则连 encodings 都起不来 —— 踩过一次）
```

现在 deps：`PIL 13.0.0 / numpy 2.5.4`，**算子可跑**。

### 2. 节点 27 → 42（+15，全部纯 CPU）

第一梯队（11）：`ImageScaleBy` `ImageSharpen` `ImageSaturation` `ImageContrast`
`ImageBrightness` `ImageGamma` `ImageQuantize` `ImagePosterize` `ImageDesaturate`
`SolidMask` `ImageColorToMask`

第二梯队（4）：`LoadImageMask` `PreviewImage` `LoadImageOutput` `PreviewAny`

全部**与 ComfyUI 同名同契约**，所以她的 workflow.json 可直接写 ComfyUI 节点名，不需要 ComfyUI 在位。

### 3. 真跑了一条链（不是只看表）

```
EmptyImage(64×64 纯色) → ImageScaleBy ×2 → ImageSharpen
trace: n1 ok 29.4ms · n2 ok 2.1ms · 产物过闸（sha256 钉住）
```

## 三、读数（参照：ComfyUI 核心面 127 把）

| 指标 | 数值 |
|---|---|
| 参照节点 | 127 |
| 我们的节点 | **42** |
| 同名覆盖 | **12（9.4%）** |
| **traditional 缺口** | **0**（核心面所有纯 CPU 算子全接） |
| needs_model 缺口 | 101（采样/加载/VAE/Conditioning —— 本机无 CUDA，如实不接） |
| needs_cloud 缺口 | 2 |
| unknown | 12（真名像模型面但无法静态归类，如实标 unknown） |

**怎么读这 9.4%**：核心面 127 把里 101 把是模型/采样/条件节点，没有 GPU 与权重就接不了；
真正「纯 CPU 能干的」那一面（traditional）现在 **100% 覆盖**。这就是这轮能诚实宣称的「一比一」边界。

## 四、要做到真·一比一（下一步，一条命令）

在装了秋叶版的机器上：

```powershell
curl http://127.0.0.1:8188/object_info -o state/comfyui_object_info.json
py -3 -X utf8 tools/comfy-parity.py
```

工具会自动切到真快照，输出「秋叶整包 ~1495 把」的真实覆盖率与按类缺口。
在那之前，任何「已一比一」的说法都是假的 —— 我只报 9.4% + traditional 100%。

## 五、复跑

```powershell
py -3 -X utf8 tools/comfy-parity.py
py -3 -X utf8 -c "from gbt_allinone.tools import comfy_native as CN; print(len(CN.NODES))"
```

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 六、第三梯队：遮罩/透明通道族（同轮跟进）

又长 8 个（全部 ComfyUI 核心同名）：`InvertMask` `CropMask` `FeatherMask` `ThresholdMask`
`MaskPreview` `SplitImageWithAlpha` `JoinImageWithAlpha` `GetImageSize`。

节点总数 **42 → 50**。真跑一条遮罩链：

```
EmptyImage → SolidMask(0.7) → InvertMask → ThresholdMask(0.5) → SplitImageWithAlpha
trace: 5/5 ok（17.0 / 0.0 / 16.3 / 0.0 / 0.0 ms）· products 5
```

参照仍为核心面 127 把：同名覆盖 12（9.4%）、**traditional 缺口 0**、needs_model 101。

## 七、真快照采集脚本（给秋叶那台机器用）

新增 `tools/collect-object-info.ps1`：

```powershell
# 在装了秋叶版、ComfyUI 已启动的机器上
powershell -NoProfile -ExecutionPolicy Bypass -File tools\collect-object-info.ps1
# 默认 GET http://127.0.0.1:8188/object_info → state\comfyui_object_info.json
```

脚本三条纪律：**只读一个 GET** · 落盘写 UTF-8 **无 BOM** · 节点数 <100 时**黄字警告**
（说明可能只起了核心，不是秋叶整包）。取回来后 `tools/comfy-parity.py` 自动切真快照。

---

## 八、家族覆盖（50 个节点，按族）

| 族 | 数量 | 说明 |
|---|---|---|
| Image | **22** | 缩放/裁剪/旋转/翻转/模糊/锐化/混合/拼接/调色（亮度 对比度 饱和度 gamma 色阶 量化 去色） |
| Mask | **13** | 生成/取反/裁剪/羽化/阈值/合成/模糊/预览/与图互转/拆合透明通道 |
| Text | **4** | 前后缀/任意值透传/尺寸查询 |
| 其它 | **11** | 落盘/哈希/放大/文生图骨架/加载保存 |

统计落盘：`state/comfy-families.json`（脚本可复核）。

## 九️、纪律：**真快照到手前，不再凭感觉造节点名**

核心面 127 把里的 traditional 已全接（缺口 0）。再往下补，必须知道**秋叶版真实有哪些节点**，
否则就是"自己编名字凑覆盖率" —— 那种数字是假的。

所以顺序固定：**先采集（`tools/collect-object-info.ps1`）→ 再按真清单补 → 每批用同一把尺子量**。

## 十、记忆条已写（重启后她知道自己能做什么图）

`cap_self brief`（1033 字符，每次判决默认注入）新增一行：

> 构图：GBT天真 50 个原生节点（纯 CPU；对 ComfyUI 核心面 traditional 缺口 0），
> 模型面/采样面无 CUDA 如实不接；秋叶整包要一比一 ⇒ 在秋叶机跑 tools/collect-object-info.ps1。
