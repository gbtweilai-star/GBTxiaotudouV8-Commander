# 129 · AI 朋友圈 · 数字人 · 全能力自检

日期：2026-11-02 · 截图：`tab-moments-final.png`、`tab-dh.png`

## 1. AI 朋友圈（新接）
- 后端：`GET/POST /api/moments`（post / like），落 `state/moments.json`，首次自动种 3 条 AI 动态；
- 前端：console 新页签「AI 朋友圈」——动态流卡片（头像/作者/时间/正文/标签/点赞）、底部发布框、刷新与 15s 自动刷新；
- 实测：GET 返回 3 条种子（41 赞）；UI 发布一条中文后卡片数 4，文案正确；点赞走 POST 持久化。

## 2. 数字人（新接）
- console 新页签「数字人」：iframe 懒加载 `/voice-theater/`（3D 语音剧场，3 个 canvas 正常）；
- 补了缺失的 `voice-theater/vendor/three.min.js`，并把 33MB 语音剧场资产打进桌面包；
- iframe 加载后 `contentDocument.title` = 「GBT小土豆V8 · 语音剧场（设计稿 v1）」。

## 3. 全能力自检（对桌面包 8766 实测）
| 面 | 结果 |
|---|---|
| ping / state / data | PASS |
| settings GET / POST / 持久化 | PASS |
| 触手绑定 + 覆盖 | PASS · 裁剪后 1059 资产 / 1913 对 / 缺失 0 / **能力覆盖 385/385** |
| 蓝图 API | PASS（16 任务，0/16 未批准） |
| 万能插 status / sockets | PASS |
| 记忆 stats / verify / recall / write | PASS（verify 565 条全绿；写入 version 565） |
| 对话 | PASS（“正常”，2 tok，2996ms） |
| 自己的模型通路 | PASS（`/api/model-test` 走 OpenAI 兼容 `/v1/chat/completions`，9.3s 返回 OK） |
| 12 个原有视图切换 | PASS（无 JS 异常，视图容器正确显示） |
| 设置弹窗打开 / 保存 | PASS（“已保存 · 08:45:55”） |
| AI 朋友圈发布 / 点赞 | PASS（4 条，中文正常） |
| 数字人 iframe | PASS（3 canvas，标题正确） |

## 4. 顺手修的问题
- 桌面包内 846 条绑定指向没打包的文件 → `prune` 剪掉（GBT_BIND_ALLOW_SHRINK=1，台账可追溯）；
- `echo` 能力因剪枝掉到 384/385 → 补绑 `holo_pet_w3/brain/caps/echo.html`，恢复 385/385；
- `voice-theater` 缺 `vendor/three.min.js` → 用仓库 `brain/vendor/three.global.js` 补上；
- 便携版/压缩包已用新 payload 重建（55.1MB，含朋友圈/数字人）。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
