# 权重

源码在本仓库；权重不放进 git（单文件 4.88 GB，超过 GitHub 单文件上限 2 GB）。

## 一键安装

    powershell -ExecutionPolicy Bypass -File .\install.ps1

装依赖 → 下 3 个分片 → 合并成 gbt-v8-v82-q5_0.gguf → 起服务（:8792）。

## 分片

| 文件 | 大小 |
|---|---|
| gbt-v8-v82-q5_0.gguf.part1 | 1.63 GB |
| gbt-v8-v82-q5_0.gguf.part2 | 1.63 GB |
| gbt-v8-v82-q5_0.gguf.part3 | 1.63 GB |

合并后 sha256 = 983f19a66928aa6927a6b42ae4ab28ac0889e015788e4553303df01c0fcd262f

## 档位实测

| 格式 | 大小 | 输出 |
|---|---|---|
| Q4_0 | 4.00 GB | vana × 16，永不收尾（弃） |
| Q5_0 | 4.88 GB | 中国的首都是**北京**。（主道） |
| Q8_0 | 7.54 GB | 与 fp16 逐 token 相同 |
| fp16 | 14.19 GB | 同上 |

## 手机 / PC

- PC：Electron 壳 + 本安装器，本地推理。
- 手机：index.html / sw.js 是 PWA 客户端，连 PC 或服务器的 :8791 桥；7.6B / 4.88 GB 无法在手机上本地推理。
