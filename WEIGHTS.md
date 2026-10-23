# 权重与依赖

源码在本仓库；**大文件不放进 git**（单文件上限 2 GB），统一走 Release v1.0.0 分片。

## 一键安装

    powershell -ExecutionPolicy Bypass -File .\install.ps1

装依赖 → 探测下载 1..9 分片 → 合并 → 起服务（:8792）。

## 四种权重（Release v1.0.0）

| 模型 | 片数 | 大小 |
|---|---|---|
| gbt-v8-v82-q5_0.gguf | 4 | 4.88 GB |
| gbt-v8-v82-q4_0-fixed.gguf | 3 | 4.00 GB |
| gbt-v8-v82-q8_0.gguf | 5 | 7.54 GB |
| gbt-v8-v82-fp16-fixed.gguf | 9 | 14.19 GB |

## 依赖包

| 文件 | 片数 | 大小 | sha256 |
|---|---|---|---|
| _upstream.tar | 8 | 11.10 GB | dc2f2bd721331e6cefa3e297973058eee7c8bebe65586113c504735b8b3ca65a |

解包：把 8 片按序合并成 _upstream.tar，然后

    tar -xf _upstream.tar

会在仓库根生成 _upstream/（334,805 文件），78 个模块引用它。

## 各模型 sha256

22:22:04 SHA256 gbt-v8-v82-q5_0.gguf = 983f19a66928aa6927a6b42ae4ab28ac0889e015788e4553303df01c0fcd262f
22:29:07 SHA256 gbt-v8-v82-q4_0-fixed.gguf = 9801fbccbe7f23d849c65a59bed7fa6f56be86dd11ac9091d1aab238e2dc1de8
22:43:58 SHA256 gbt-v8-v82-q8_0.gguf = ad1d7119eaa1d7699493c1e15e529d76ba32fa9b529fdfe93fb56e8497ea3f81
23:09:37 SHA256 gbt-v8-v82-fp16-fixed.gguf = 3298a02e8e4207089863c6a9597486d12985bba1fdaf4f63d007057a4c43b765

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
