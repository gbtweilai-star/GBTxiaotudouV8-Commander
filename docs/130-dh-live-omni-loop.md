# 130 · 数字人整页重做 · 触手细节操控 · 眼手脑实时闭环

日期：2026-11-02 · 入口：数字人页 `/dh-live/`（console「数字人」页签）· 截图：`dh-loop-wave.png`

## 1. 页面重做
- 一整页只有数字人：全身 3D、暗场、脚底阴影、无分栏、无按钮堆；
- 只保留一个小语音球 + 一行字幕；点页面/点语音球说话；
- 语音走本机离线识别（Windows 桌面识别器，`/api/asr`，零密钥），不用浏览器 SpeechRecognition（Electron 不可用）；
- 回复用系统 TTS 播报；没有说话口型骨（资产无 jaw/morph），说话用头颈节律+手势表达，不假装口型。

## 2. 动作细节（22 个动作）
- 骨头/轴/正负号全部来自实测骨位表 `holo_pet_w3/digital-human/bone-map.js`（65 骨，由 `dh-bone-map.py` 反查实测位移生成）；
- 每个动作是多骨骼关键帧：预备 → 主动作 → 收尾回正；例如 wave 有 11 条轨道（右臂外展/前摆、右前臂、右手腕摆动、头转/点/侧、上胸侧弯、左臂平衡、骨盆微转）；
- 服务端按 30fps 采样成帧，前端只按帧叠骨，不在前端写死姿势；
- 动作清单：ready / wave / nod / shake / bow / hug / heart / clap / think / shy / angry / surprise / laugh / stretch / point / salute / shrug / turn / squat / dance / talk / walk。

## 3. 万能插执行（omni_plug）
- `gbt_allinone/omni_plug.py` 新增 dh 插座：`register_actuator("dh:rig", fn)`，`plug_and_run("dh:rig", kind="dh", args={...})`；
- 每帧目标角度都经万能插执行器推进 rig，不绕过：`/api/dh/frame` 返回 `omni:{ok, applied, via}`；
- `/api/dh/status` 里可看 `omni_plug.plugged=true`、执行器插着。

## 4. 眼手脑实时同步（边看边做）
- 眼：前端每帧把实测骨骼角度按 `bone.axis` 上报 `/api/dh/frame`（40ms 节流，不阻塞渲染）；
- 手：服务端立刻返回目标角度并经万能插执行，前端当帧叠骨；
- 脑：后台线程每 100ms 根据跟踪误差调 kp/kd（误差大→加大反馈，误差小→放松），不参与阻塞等待；
- 前馈+反馈：目标 = 计划角 + 限幅(kp×误差)（±0.12 rad），是连续闭环，不是先看再停再动。

## 5. 3D 免费工具部署
- 已把 Blender 便携版（383MB zip）下载到 `tools/3d/`（后台任务仍在下载/解压中；完成后 `dh_tentacle.status()` 显示 blender=true）；
- 仓库已有 Blender 绑定/骨架脚本：`tools/codex-scripts/blender/dh_rig.py`、`dh-bone-map.py`、`spring-bones.py`；
- FreeCAD 未安装（只做检测，不假装有）。

## 6. 实测
- `/api/dh/status`：bones=65 · actions=22 · omni_plug=true · blender=false（下载中）；
- `/api/dh/action {gesture:wave}`：11 条轨道、3.0s；
- `/api/dh/frame`：返回 11 个目标、err、omni applied 成功；
- 浏览器实测：`window.__DH.gesture('wave')` → active=true phase≈1.5 dur=3 targets=11，手臂抬起，无 JS 异常。

## 7. 吞入件「灵巧手」已接上（2026-11-02 补）

没有不见：仓库里就有 2026-11-01 吞入蒸馏的 **dexterous-hand 能力**：
- `gbt_allinone/tentacle/hand_retarget.py`（21 点手部跟踪 → 15/20-DOF 关节角，带限位）；
- `gbt_allinone/tentacle/hand_bridge.py`（灵巧手 HAL：loopback 仿真 / Modbus TCP / 串口 / CAN，会话/限位/dry_run/confirm）。

现在的用法：
- `dh_tentacle.hand_pose()` 调 hand_retarget 做**限位与单位换算**，得到 15-DOF 目标；
- `hand_tracks()` 把 15-DOF 映射到 Mixamo 手指骨（每指 4 段，3 段驱动 + 末端跟随），左右手各 15 轨 ⇒ 双手 30 轨；
- 新增动作：grip / pinch / ok_sign / thumbs_up / open_palm（每个动作 45 条轨道 = 15 身体 + 30 手指）；
- 动作表扩到 **27 个**；wave/open_palm 用 open 手，grip 用 fist，pinch/ok/thumbs_up 各自手型；
- `dh_omni_loop` 在切到手部动作时，经 **hand_bridge HAL（loopback）** 真跑：connect → move → read_state，session 写进回执；
- `GET /api/dh/hand` 返回 models / profiles / status / 最近一次 hand 状态。

实测：
- `POST /api/dh/action {"gesture":"grip"}` → `tracks=45`、`hand=fist`、`hand_bridge={pose:fist, ok:true, session:hb0001, transport:loopback}`；
- `GET /api/dh/hand` → `models=2`、`lastPose=fist`、`handOk=true`；
- 真机手需要 register_map + confirm（HAL 自身的边界，未假装驱动真硬件）。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
