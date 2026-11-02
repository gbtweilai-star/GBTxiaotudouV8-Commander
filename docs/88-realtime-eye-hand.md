# 88 · 眼手脑同拍（实时闭环）· 第一版落地

> 主人令：「眼手脑必须实时同步操作，不许看一下再动手，必须边看边做。」
> 本页不是概念：`body_realtime` 已挂进万能插 `run_task`，采集线程持续看，控制环小步闭环动。

## 一、旧路径为什么不对
旧 `body_see` / `body_click` 是两个独立子进程：
```
截一张图 → 子进程退出 → 大脑决定 → 再点一下
```
中间没有"动作中继续看"，也没有反馈；这就是"看一下再动手"。

## 二、新路径（已落地）
`tools/model-bridge/realtime_eye_hand.py`：

```
mss 采集线程（持续，ring/latest） ──► 控制环只读最新帧
                                      │
                              误差 = 目标 - 光标
                                      │
                              小步 moveRel（不是盲点）
                                      │
                              立刻取下一帧（动作中采集不停）
```

- 采集线程和控制环**分离**；动作不阻塞采集；
- 每次只移动一小步，下一帧重新算误差（闭环微步）；
- 输出可审计：`capture_fps / action_rate_hz / vision_latency_ms / error_px / converged`。

## 三、挂进万能插（不是旁路脚本）
新增能力位 `body_realtime`（domain=device）：
```python
api.run_task("body_realtime", {
  "op": "servo",
  "target": "red",
  "seconds": 4,
  "gain": 0.35,
  "max_step": 70,
  "dry_run": False
})
```
- `op=status` 只读；`op=servo` 真闭环；
- `dry_run=True` 只测眼+脑，不动手；
- 代码：`gbt_allinone/tentacle/body_realtime.py`，dispatch 在 `api.py`，注册在 `caps_registry.py`。

## 四、实测（2026-11-02）
| 场景 | capture_fps | action_rate | vision_latency mean/p95 | 结果 |
|---|---|---|---|---|
| dry-run（只测感知/决策，不移动） | **18.25** | 18.97 Hz | **8.97 / 14.17 ms** | 看清、算准 |
| 真闭环（同时 ComfyUI CPU 在跑） | **3.2** | 7.75 Hz | 32.44 / 164.04 ms | 动 31 次，未收敛 |

**结论**：架构是"边看边做"，但当前**不是 30fps 实时**。瓶颈不在"看"，在：
1. `pyautogui.moveRel` 每次调用有固定开销，拖慢控制环；
2. ComfyUI/模型推理占满 CPU，采集线程被饿；
3. 全屏 1920×1200 每帧 9MB，numpy 拷贝重；
4. 目标色检测会被屏幕其它红色干扰（实测目标坐标漂）。

## 五、下一步（按顺序，不吹）
1. **手**：`pyautogui` → `ctypes SendInput`（原生鼠标事件，微秒级），动作不再阻塞；
2. **眼**：只抓 ROI/降采样（目标附近），采集从 3fps 提到 30fps；
3. **脑**：控制环固定优先级；重模型推理让出 CPU/独立进程，避免饿死眼；
4. **判据**：目标色 + 形状/模板双验证，减少误检；
5. **再测**：目标 30fps 采集、<10ms 视觉延迟、闭环 2s 内收敛；
6. 达标后才接"点击/拖拽/输入"等真实操作，不拿未收敛的闭环去点生产界面。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
