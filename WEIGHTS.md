# 权重

源码在本仓库；权重不放进 git（单文件 4.88 GB，超过 GitHub 单文件上限 2 GB）。

## 一键安装

    powershell -ExecutionPolicy Bypass -File .\install.ps1

装依赖 → 按 1..9 探测下载分片 → 合并成 gbt-v8-v82-q5_0.gguf → 起服务（:8792）。

## 已上传（Release v1.0.0）

| 模型 | 分片 | 大小 | sha256 |
|---|---|---|---|
| gbt-v8-v82-q5_0.gguf | part1 1621MB · part2 1621MB · part3 1621MB · part4 136MB | 4.88 GB | 983f19a66928aa6927a6b42ae4ab28ac0889e015788e4553303df01c0fcd262f |
| gbt-v8-v82-q4_0-fixed.gguf | 3 片 | 4.00 GB | 9801fbccbe7f23d849c65a59bed7fa6f56be86dd11ac9091d1aab238e2dc1de8 |
| gbt-v8-v82-q8_0.gguf | 5 片 | 7.54 GB | 上传中 |
| gbt-v8-v82-fp16-fixed.gguf | 9 片 | 14.19 GB | 上传中 |

合并后自检：PowerShell 跑 Get-FileHash -Algorithm SHA256，比对上面那一列。

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
