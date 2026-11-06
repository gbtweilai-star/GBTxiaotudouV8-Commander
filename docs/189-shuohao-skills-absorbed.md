# 189 · 吞噬 shuohao-skills：GBT天真短剧制作层 + 首个 AI 漫剧成片

## 一、吸收内容
- 来源：`eternityspring/shuohao-skills`（main，2026-11-02）
- 已复制进：`gbt_allinone/skills/shuohao/`
- 7 个 skill：
  - novel-outline
  - novel-characters
  - character-refs
  - novel-art
  - novel-script
  - novel-staging
  - novel-storyboard
- 全部自带 Node 脚本，零 npm 依赖。

## 二、自测（Node 26.13）
| skill | 结果 |
|---|---|
| character-refs | ✓ 233 项 |
| novel-art | ✓ 151 项 |
| novel-characters | ✓ 337 项 |
| novel-outline | ✓ 249 项 |
| novel-script | ✓ 154 项 |
| novel-staging | ✓ 99 项 |
| novel-storyboard | ✓ 336 项 |

全部 **exit 0**。

## 三、GBT天真节点
- 新节点：`shuohao_skill`
- 输入：`skill, script, args`
- 实测 `novel-outline/selftest.mjs`：`ok=True`，输出 `✓ 249 项自测全部通过`
- 节点总数：**170**
- 不碰云端/ComfyUI

## 四、首个 AI 漫剧成片
- 路径：`交付成片/AI漫剧-红瞳/AI漫剧-红瞳-1080x1920.mp4`
- 画幅：**1080×1920**
- 时长：**26.52s**
- 结构：2s 片头 + 22.52s 正片（四镜全 SVD 真运动）+ 2s 片尾
- 旁白：Hanhan zh-TW
- 环境音：本地合成
- 大小：**8,512,292 B**

## 五、边界
- shuohao-skills 是**策划/质检/报告层**（大纲、角色、美术、剧本、站位、分镜），不直接渲染视频；
- 本片画面来自本地 SVD 真运动帧，不是 skill 自动生成分镜后渲染；
- 真·全自动“小说→分镜→出片”仍需把 skill JSON 接到 t2i/i2v 渲染器；
- 不碰云端，不是秋叶权重。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
