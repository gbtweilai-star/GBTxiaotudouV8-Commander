# 130 · 引擎直连 GPU：自动补齐 Vulkan 后端并跑通闭环

> 主人 2026-11-03：「没有就自动补齐并跑通闭环，而不是跟我说不行。」
> 已做：下载 Vulkan 后端 → 探测 GPU → 加载本机权重 → 面板对话走通 → 一键切换 → 实测对比。

## 一、补齐了什么

| 项 | 结果 |
|---|---|
| 后端二进制 | `vendor/vulkan-b12032/`（llama.cpp b12032，36MB，Vulkan x64） |
| 设备探测 | `Vulkan0: Intel(R) Iris(R) Xe Graphics (8028 MiB, 7371 MiB free)` |
| 模型 | `state/weights/gbt-v8-v82-q5_0.gguf`（本地，-ngl 99 全 offload） |
| 切换工具 | `tools/engine-switch.py --backend cpu|vulkan`（停旧起新、健康检查、写 `state/engine-backend.json`） |
| 面板链路 | 切换后 `/api/chat` 仍走本机 8792，实测 ok=true |

## 二、实测数字（同一模型、同一 prompt）

```
CPU   （旧构建 b12020，-t 12，-ngl 0） ：约 4.1 tok/s（热）
Vulkan（新构建 b12032，-ngl 99，-t 8） ：约 3.2–3.5 tok/s（热）
```

- Vulkan 后端**能跑、能出正确回答、GPU 确实加载了权重**（Vulkan0 设备、-ngl 99、props 正常）；
- 但这台机器是 **Intel Iris Xe 核显（共享内存）**，对这个 5.24GB Q4/Q5 权重的解码速度**比 CPU 慢**；
- 结论：**默认 CPU，GPU 后端保留可一键切换**；换独显（NVIDIA/AMD）时同一套切换工具直接生效。

## 三、闭环验证

```
1) sudo? 不需要 —— vendor/vulkan-b12032 已就位
2) python tools/engine-switch.py --backend vulkan → healthy=true，/v1/models 有本机权重
3) /api/chat（面板）→ ok=true，正常回答
4) python tools/engine-switch.py --backend cpu → healthy=true，面板继续可用
```

## 四、边界（如实）

- 核显显存 8GB（共享）：模型勉强装下，速度受共享内存带宽限制 → 不是“上了 GPU 就快”；
- 独显（CUDA/Vulkan）会有实质提升，切换工具已就绪；
- 全程本地：不接任何外部 API/模型。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
