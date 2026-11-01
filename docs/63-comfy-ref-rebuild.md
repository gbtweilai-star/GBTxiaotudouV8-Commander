# 63 · 参照重建 + 分类升级 + 批次 A（2026-11-01）

> 上一轮"核心面 127 把"是**解析漏了**：新版 ComfyUI 用 v3 API，节点名写在
> `node_id="X"`（不是旧的 `NODE_CLASS_MAPPINGS` 字典）。修好解析后参照从 127 → **1000**。

---

## 一、参照重建（解析修到位）

| 解析方式 | 命中文件 | 节点数 |
|---|---|---|
| 旧：只认 `NODE_CLASS_MAPPINGS` 字典字面量 | 11 / 172 | 103 |
| 新：`node_id="X"`（v3 API）+ 旧方式兜底 | 275 文件 | **1000** |

样例：`AdjustBrightness` `CenterCropImages` `ImageFlip` `ImageStitch` `ImageGrid`…

## 二、分类升级（不然"可补"清单全是云端）

首版取食把 `Bria*`/`ByteDance*`/`ElevenLabs*`/`FishAudio*`/`HappyHorse*` 全判成"可补"——
它们是**云端 API 节点**。规则改成五级（三个工具同步改）：

```
① 以 Node 结尾（且不是 Image/Mask/Batch/Empty 开头） ⇒ 云端（v3 API 节点都这样命名）
② 厂商前缀（Bria/ByteDance/ElevenLabs/FishAudio/Grok/Kling/Luma/Minimax/…）或含 Api ⇒ 云端
③ 3D/几何（Mesh/Voxel/Texture/Bone/Rig/UV） ⇒ unknown（本机没有几何管线）
④ 模型词（sampler/loader/vae/conditioning/merge/encode/decode…） ⇒ 模型面
⑤ 传统动词（Image/Mask/Adjust/Center/Crop/Resize/Flip/Color/RGB/Audio…） ⇒ 可补
```

效果：**可补 130 条**（上轮 214 里混着云端），云端 371、模型 277、unknown 183。

## 三、批次 A：12 个纯 CPU 传统算子

从清单里挑能纯 PIL 实现的，**同名同契约**：

`AdjustBrightness` · `AdjustContrast` · `CaseConverter` · `CenterCropImages` ·
`ColorToRGBInt` · `ComfyNumberConvert` · `GrowMask` · `ImageFlip` · `ImageFromBatch` ·
`ImageGrid` · `ImageScaleToMaxDimension` · `ImageStitch`

节点数 **56 → 68**。真跑一条混合链（7 节点）：

```
EmptyImage → AdjustBrightness → CenterCropImages → ImageStitch → ImageGrid
           → ImageScaleToMaxDimension → GrowMask
workflow ok=True · products=7
```

**踩坑记录**：`AdjustBrightness/AdjustContrast` 首次跑报 `NameError: Image`（只 import 了
`ImageEnhance` 没 import `Image`）——回滚机制又把半成品删干净了。补 import 后复跑通过。

## 四、读数（参照变真之后，覆盖率反而降了）

| 指标 | 参照 127 时 | 参照 1000 时（现在） |
|---|---|---|
| 参照节点 | 127 | **1000** |
| 我们 | 56 | **68** |
| 同名覆盖 | 17（13.4%） | **51（5.1%）** |
| traditional 缺口 | 0 | **118** |

**覆盖率从 13.4% 降到 5.1% 不是退步，是分母变真了**——之前那个 13.4% 是拿残缺参照算的。
这才是能拿去和秋叶整包对比的底座。

## 五、下一步

1. 从 118 条 traditional 缺口里继续挑（但**先看契约**：有些是音频/条件节点，需要精确 schema）；
2. 用 `--from-harvest` 一次性生成待审骨架 → 逐个填 → 跑判据；
3. 秋叶真快照到手后，把参照换成整包（~1495），覆盖率会再变一次——同样如实报。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 六、批次 B：又 10 个纯 CPU 算子（68 → 78）

从 106 条 traditional 缺口里挑能纯 CPU 实现的：

`ConvertArrayToString` `ConvertDictionaryToString` `CropByBBoxes` `ImageHistogram` `ImageCropV2`
`EmptyAudio`（stdlib wave 生成静音 wav）`ImageCompare`（平均绝对差）`ColorTransfer`（numpy 均值/方差）
`ImageCropToMask`（裁块 + 遮罩）`ImageColorSpace`（RGB/HSV/LAB/L/CMYK）

实测 6 节点链（裁剪/bbox/裁块出遮罩/颜色空间/静音音频）：

```
EmptyImage → ImageCropV2 → CropByBBoxes → ImageCropToMask → ImageColorSpace → EmptyAudio
workflow ok=True · products=6
```

判据补 [11] 组 3 条（链跑通 / 静音 wav 真生成且有体量 / harvest 分类不回退）。

---

## 七、批次 C：音频/文本/缩放补边又 14 个（78 → 92）

`AudioAdjustVolume` `AudioConcat` `TrimAudioDuration`（都用 stdlib `wave`+`array`，不装 ffmpeg）
`ImageCompositor` `ImageDeduplication`（8×8 灰度指纹）`NormalizeImages` `RepeatImageBatch`
`ResizeImagesByLongerEdge` `ResizeAndPadImage` `TextOverlay`（PIL 写字）
`TextToLowercase` `TextToUppercase` `TruncateText` `ReplaceText`

实测 8 节点混合链：

```
EmptyImage → NormalizeImages → ResizeAndPadImage → ResizeImagesByLongerEdge → TextOverlay
→ EmptyAudio → AudioAdjustVolume → TrimAudioDuration
workflow ok=True · products=8
```

判据补 [12] 组 3 条（音频链跑通 / 音量文件生成 / 文本替换有读数）。

---

## 八、批次 D：音频通道/裁切/文本落盘又 11 个（92 → 103）

`LoadAudio` `SaveAudio` `PreviewAudio` `SplitAudioChannels` `JoinAudioChannels`
`AudioEqualizer3Band`（numpy FFT 三频段）`RebatchImages` `RandomCropImages`（seed 可复现）
`ResizeImagesByShorterEdge` `ImageScaleToTotalPixels` `SaveText`

实测 7 节点混合链（音频均衡 + 随机裁剪 + 总像素缩放 + 文本落盘）：

```
EmptyAudio → AudioEqualizer3Band → SaveAudio
EmptyImage → RandomCropImages → ImageScaleToTotalPixels
SaveText
workflow ok=True · products=7
```

判据补 [13] 组 3 条（链跑通 / 均衡产物 / 文本落盘内容一致）。

**消化纪律**（主人 2026-11-01：「吞噬一次、消化一次、固化好，别制造垃圾」）：
每批只挑**真能实现**的，不凑数；每批必跑链 + 判据 + 记账 + 文档；跑完清临时件。

---

## 九、批次 E/F + 分类复核（103 → 118，可补缺口 83 → 0）

### 复核对：先把「假缺口」清掉

用分类器把**做不到的**从待补清单剔除（不是假装能补）：

| 族 | 为什么不做 | 归到哪 |
|---|---|---|
| 视频（LoadVideo/SaveVideo/VideoCrop/Wan*/LTXV*/Hunyuan*） | 本机没有 av/ffmpeg | 模型面 |
| 3D（Load3D*/Preview3D*/SaveGLB/PointCloud/GaussianSplat） | 没有几何管线 | 模型面 |
| TextEncode*（11 个） | 要模型权重 | 模型面 |
| 训练数据集 | 要 torch 张量 | 模型面 |
| MP3/Opus/WEBM | 要 ffmpeg | 模型面（节点里如实报 needs_dependency） |
| 云端音效/音乐/文生图 | 要 key | 云端 |

剔除后：**可补 83 → 14 → 补 11（E）→ 剩 4（F）→ 0**。

### 批次 E（11）：数据集/瓦片/SVG

`FlipSigmas` `BatchImagesNode` `BatchMasksNode` `SplitImageToTileList` `SaveImageAdvanced`
`LoadImageDataSetFromFolder` `LoadImageTextDataSetFromFolder` `SaveImageDataSetToFolder`
`SaveImageTextDataSetToFolder` `ShuffleImageTextDataset` `QuiverTextToSVGNodeV2`

### 批次 F（4）：合成/动图/音频高级

`PorterDuffImageComposite`（over/multiply/screen/add/difference）· `SaveAnimatedPNG`（APNG）
`SaveAnimatedWEBP` · `SaveAudioAdvanced`（只接 wav，MP3/Opus 明确报 needs_dependency）

实测链：`EmptyImage ×2 → PorterDuffImageComposite(screen) → SaveAnimatedPNG` ⇒ ok=True，4 产物。

## 十、收尾读数（诚实版）

| 指标 | 数值 |
|---|---|
| 参照 | 1000（ComfyUI 核心面） |
| 我们节点 | **118** |
| traditional 可补缺口 | **0** |
| needs_model | 398+ |
| needs_cloud | 371 |

**这不是「做完了」，是「纯 CPU 能做的做完了」**：剩下 700+ 条要么要 GPU 与权重，
要么要云端 key，要么要 av/ffmpeg 与几何管线 —— 全都在清单里**写明原因**，不是消失。
