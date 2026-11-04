# 160 · 真实权重融合（公共底座）：RV5.1 × Tiny-SD → gbt-fused-sd15

## 一、说明
- 秋叶 v3.2 最新整合包已验：**不带模型权重**，只有运行环境/节点/启动器；
- 所以这次用**公共兼容权重**做真实融合底座，不是秋叶权重，明确标注，不冒充。

## 二、融合
- base：Realistic Vision V5.1（diffusers 分片，SD1.5）
- other：本地 Tiny-SD（SD1.5）
- alpha：0.5
- UNet keys：base 686 / other 358 / 共同 148
- 共同 key 按 `0.5*base + 0.5*other` 融合，其余保留 base
- 输出：`vendor/hf/gbt-fused-sd15`（4,071 MB / 12 文件）

## 三、真出图验证
- 底座 RV 先单独出图：256×256 红苹果，正常；
- 融合权重再出图：`fused-preview.png`，正常苹果，不是花屏；
- 融合后加载 91.71s，生成 128.43s（CPU）。
- 证据：`vendor/hf/gbt-fused-sd15/fusion.json`

## 四、清理
- 回收站/下载分卷/临时 chunk 清理；
- RV 源分片在融合完成后删除；
- 没有常驻 SD1.5/SVD 推理进程；
- C 盘可用约 108.5GB。

## 五、边界
- 这是 **RV × Tiny-SD** 融合，不是秋叶权重；
- 共同 key 只有 148，融合是部分层融合，不是全量同架构；
- 真·秋叶融合仍需她的 checkpoint；
- 不碰云端。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
