# 93 · 图片 → 21 点 → IK → loopback 手（已跑通）

> 下一步：手部视觉入口。摄像头仍被系统/后端卡住；先用**本地图片**把整链跑通，不拿“装了库”冒充。

## 一、链路
```
本地手图
  → MediaPipe Hands（本机 tflite，0.10.21）
  → 21×[x,y,z] + 左右手
  → hand_retarget op=ik（generic_20dof）
  → hand_bridge loopback.move
  → read_state
```

## 二、实测（test_hand_image）
| 项 | 读数 |
|---|---|
| 检测 | 21 点，right |
| 关节 | 20 |
| IK | 每指残差（index≈0.0011 m，middle≈0.0001 m） |
| 动作 | move 成功 |
| 回读 | read_state 成功 |
| 传输 | loopback（simulated） |
| 测试 | `tests/test_hand_image.py` 输出 **ALL PASS**（MediaPipe 原生日志会让进程 stderr 有噪声，非链路失败） |

## 三、摄像头为什么还没接
- OpenCV MSMF/DSHOW/ANY 都打不开；
- ffmpeg dshow：`Unable to BindToObject for Integrated Camera`；
- 设备管理器 Integrated Camera 状态 OK。
⇒ 不是没设备，是 Windows 相机隐私/占用/采集后端绑定问题。`hand_vision camera` 仍返回 `needs_camera`，不伪造。

## 四、下一步
1. 打开 设置→隐私→相机→允许桌面应用；关掉占用程序；
2. 通了以后，把 `hand_vision camera` 的帧直接喂 `hand_realtime`，目标 15–30Hz；
3. 摄像头未通前，用图片/视频文件继续验证 IK 与 loopback；
4. 真机仍缺 register_map/confirm、力/触觉。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
