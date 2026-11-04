# 159 · 第一部原生 SD-Turbo 竖屏成片《夜灯》

## 一、成片
- 文件：`交付成片\夜灯-Native\夜灯-Native-1080x1920.mp4`
- 时长：**15.84s**
- 画幅：**1080×1920**，25fps
- 视频：H.264；音频：AAC 160k
- 旁白：**Microsoft Hanhan Desktop（zh-TW 女声，本地 SAPI）**
- 字幕：ASS 烧录
- 分镜：6 镜（雨夜街道 / 便利店 / 店员 / 流浪猫 / 开门 / 微笑）
- 引擎：**本地 Diffusers SD-Turbo CPU**
- ComfyUI：**已删，无 8188**
- 云端：**无**

## 二、链路
```
SCENES(prompt) → t2i_sdturbo(512, 1step, CPU)
→ ffmpeg 1080×1920 竖屏（模糊背景+居中画面）
→ concat 6 镜
→ Hanhan SAPI 旁白
→ ASS 字幕烧录
→ MP4
```

## 三、实测
| 项 | 读数 |
|---|---|
| 旁白时长 | 15.84s |
| 每镜 | 3.0s |
| ffprobe 视频 | 1080×1920 / 25fps |
| MP4 大小 | 1,230,960 B |
| 预览 | 4s / 9s / 12s 帧均非黑 |
| 字幕 | 中文正常烧录 |

## 四、踩坑与修复
1. SAPI 从 Python 拉起时偶发 0 字节 WAV → 用已验证 WAV，并加重试/大小检查；
2. `subtitles=subs.ass:fontsdir=C\:/...` 参数解析错 → 改为 cwd 下 `subtitles=subs.ass`；
3. 每镜淡入淡出导致切镜处黑帧 → 改为硬切，黑帧消失；
4. Python 脚本被 PowerShell 写出 BOM → 重写 UTF-8 no BOM。

## 五、运动版（回应“这不还是图片吗”）
- 第一版确实是静态图轮播；
- 已改为每镜 **Ken Burns 推拉**（zoompan，1080×1920/25fps），硬切不黑帧；
- 当前主文件 `夜灯-Native-1080x1920.mp4` = **运动版**（2,907,780 B）；
- 旧静态版保留为 `夜灯-Native-Slideshow.mp4`；
- 但这是“静帧运镜”，**不是人物真实运动**；真人物运动需要视频模型/GPU，SD-Turbo 做不到，不冒充。

## 六、边界
- SD-Turbo 1-step 512，画面是本地 CPU 生成，不保证角色跨镜完全一致；
- 不是秋叶 GPU 整包/插件生态；
- 这是 15.84s 短片，不是长片；
- 仍然不碰云端。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
