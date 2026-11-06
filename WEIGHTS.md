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

## 依赖包（Release v1.0.0）

| 文件 | 片数 | 大小 | sha256 |
|---|---|---|---|
| _upstream.tar | 8 | 11.10 GB | dc2f2bd721331e6cefa3e297973058eee7c8bebe65586113c504735b8b3ca65a |
| _deps.tar（.pylibs + vendor + third_party） | 3 | 3.41 GB | a0b76af68741b3571ff8d1e3e1d8a12ca4e6ee1277f0dc7a149b9a6c6413ffce |

解包：把各片按序合并成 .tar，再 tar -xf 解到仓库根
（_upstream/ 334,805 文件，78 个模块引用它；_deps/ 含 _pylibs·vendor·third_party）。

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

## Q4_K_M 实测否决（2026-11-04）

**结论：弃。保留 Q5_0 作主道。** 别只看速度那三行就又切一遍 —— 下面是完整对拍。

同一台机、同一组三个探针、切前切后各跑一次（`state/weights/ACTIVE.json`
指针切换 + `start-local-llm.py --stop`/重启，文件 sha256 切换前现算一致）：

| 探针 | Q5_0 | Q4_K_M | 速度 | Q4 答得对不对 |
|---|---|---|---|---|
| 基础事实（骰子最大点数） | 3.98–7.80s | 2.82s | **快 1.4–2.8×** | ❌ 答「**300**」（Q5 答「六」） |
| 中文短答 | 30.9–32.0s | 9.60s | **快 3.3×** | 答得通顺，但已不是同一套内容 |
| 不编坐标（问屏幕鼠标坐标） | 7.9–8.2s | 5.89s | 0.8×（没快） | ❌ 编造「x=364, y=259」（它根本看不到屏幕） |

**速度是真的，质量也是真的坏了。**

判据不是"快不快"，是这两条必须同时成立：

1. **基础事实不许答错** —— 骰子最大点数答 300，这不是"精度损失"，是**答错**。
2. **不知道必须说不知道** —— 它没有屏幕读取能力，却报了一个具体坐标。
   这条比第一条更危险：**编造的坐标会被拿去点鼠标**。

「快但假，比慢更坏」是本仓写死的纪律。Q4_K_M 快 3.3 倍，但它会把
"我不知道"变成"x=364, y=259" —— 这种提速是负收益。

### 为什么 K-quant 还是更快

Q5_0 是 legacy 量化，没走 SIMD 路径；K-quant（Q4_K_M）有 SIMD 快路径，
所以少 12% 体积还能快 1.4–3.3×。**但省下的比特直接来自质量。**

### 想再试的话

Q4_K_M 文件还在盘上（4.295 GB，`sha256 1214d307ce890ac10f6ed2772bad760bbcac2e86c964a125dbcad6da457ea91d`），
切换与回滚一键：

    python .scratch/switch-weights.py --dry       # 只验文件 + 测当期基线，不动
    python .scratch/switch-weights.py --apply     # 真切（任一步失败自动回滚）
    python .scratch/switch-weights.py --rollback  # 切回 .prev 并重启

**要再切，必须重跑上面那三个探针**，尤其是「不编坐标」那条 ——
它是这次否决的唯一硬证据。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

## 手机 / PC

- PC：Electron 壳 + 本安装器，本地推理。
- 手机：index.html / sw.js 是 PWA 客户端，连 PC 或服务器的 :8791 桥；7.6B / 4.88 GB 无法在手机上本地推理。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
