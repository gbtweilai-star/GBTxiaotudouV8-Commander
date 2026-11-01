# wgpu/_retired —— 本机推理攻关期的中间页（2026-10-30 收编）

**四个页都被 `local-llm.html`（统一入口）取代，没有代码依赖。**
保留它们是因为每一步都留下了一条真读数，删了等于把结论一起丢掉。

| 文件 | 当时证明了什么 | 被谁取代 |
|---|---|---|
| `gguf-parse.html` | 浏览器内零依赖解析 GGUF v3：272 张量 / 37 KV / dataStart；**并暴露了一个真 bug**——张量数据段必须按 `general.alignment`(32) 对齐，差 8 字节就读出 -15045 | `gguf-llm.js`（内建同一解析） |
| `tokenizer.html` | 从元数据现做 GPT2 BPE：词表 49152 / merges 48900；英文往返一致；**中文为空 ⇒ SmolLM2 是英文模型**（如实报，不掩饰） | `local-llm.js` 的 makeTokenizer |
| `infer.html` | JS 标量前向跑通："The capital of France is Paris." 1.39→9.83 tok/s（**持久 KV + 增量解码**修掉 O(n²)） | `local-llm.js` 的 js 后端 |
| `wgpu-infer.html` | 全 GPU 流水线跑通：42.52 tok/s（4.3×），权重 513MiB 常驻；**修 4 个静默 bug**（缓冲缺 COPY_SRC/COPY_DST、GQA kvOff 写死 0、WGSL f32×u32、h 定义顺序） | `local-llm.js` 的 gpu 后端 |

## 现役件（不是重复）

```
local-llm.html   统一入口页（五条自检，阈值按后端分开 gpu≥30 / js≥8 tok/s）
local-llm.js     一套 API（chat/nextToken/model），auto 选后端；显式 gpu 失败则报错不降级
gguf-llm.js      GGUF 解析 + 反量化 + matvec/rmsnorm/rope/softmax
wgpu-llm.js      7 个 WGSL 算子 + 前向编排（一个 encoder，一次 fence）
bench-matvec.html JS vs WebGPU 基准（单算子亏、批量 10× 的账就是在这量的）
probe.html       COOP/COEP 与 SharedArrayBuffer/WebGPU 可用性探针
models/          tiny.gguf（SmolLM2-135M-Instruct，100.6MB）
vendor/          three.min / GLTFLoader / BufferGeometryUtils（本地，零 CDN）
```
