# 131 · Blender 重绑骨（触手驱动）+ 按住空格说话

日期：2026-11-02 · 截图：`rerig-repaired.png`

## 1. 分工（主人令：Blender 干活，绑骨听触手）
- 触手层：`gbt_allinone/dh_tentacle.py` 的 65 骨骨位表（骨名 / 父子 / 轴 / 正负）导出成 `state/hd/rerig/bone-map.json`；
- Blender 4.2.3 LTS（`tools/3d/blender/blender.exe`，926MB，便携）：**由万能插 process 插座启动**（回执 ok=true / rc=0 / plug=plugged），
  按骨位表清旧蒙皮 → automatic weights 重新蒙皮 → 对无名顶点按最近骨段补权 → 归一化 / 限 4 骨 → 导出 `state/hd/rerig/dh-tentacle-rerig.glb`；
- 动作仍由触手引擎运行时叠骨（Blender 只负责“绑”，触手负责“怎么动”）。

## 2. 重绑结果（report.json）
| 项 | 值 |
|---|---|
| 骨骼 | 65 |
| 蒙皮 | automatic weights（Bone Heat 有告警，已如实记录） |
| 未绑顶点 | 42 → 修补后 **0** |
| 动画 | 保留 idle / walk（idle_Armature / walk_Armature） |
| 产物 | `dh-tentacle-rerig.glb` 6.4MB |

页面已切到这份 Blender 重绑模型；截图里站立/面部正常。

## 3. 语音改为按住空格（圆点已删）
- 删除页面上的圆形麦克风按钮；
- **按住空格**开始录音（浏览器 AudioContext 采集 → 16k WAV），**松开空格**上传 `/api/asr` 走本机离线识别；
- 录音期间状态“在听…松开空格发送”，识别中显示“识别中…”，没听清会提示重试；
- Electron 主进程已允许 media 权限。

## 4. 姿势稳定
- 每帧保存 mixer 输出快照（CLEAN），下一帧先回到快照再叠动作 ⇒ 任何骨都不会累积旋转；
- Hips / Head / Neck 每帧回正（头正脸平视）；动作结束/超时自动清残留。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
