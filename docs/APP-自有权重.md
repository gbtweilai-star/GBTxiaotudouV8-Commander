# APP · 自有权重按需激活

本文只讲一件事：**APP 里的对话，什么时候、怎么用上我们自己的 Q5_0 权重。**

## 一、链路

    页面 model-chat/index.html
      → 桥 :8791（server.py，唯一出口，钥只在桥里）
      → 权重服务 :8792（local_llm_server.py，llama.cpp + use_extra_bufts=False）
      → state/weights/gbt-v8-v82-q5_0.gguf（4.88 GB）

回包带 gbt.weights_ours：true = 我们的权重答的；false = 按设计回落别人的模型，页面会标黄。

## 二、按需激活时序

1. 打开壳 → 只起桥（:8791），**权重不加载**，内存不占；
2. 第一条消息 → 桥发现 :8792 没监听 → 现拉权重服务 → 等 /health 就绪（最长 150s）；
3. 正常对话 → 每轮 10s 量级（Q5_0 / ctx 256 / 8 线程）；
4. 闲置 GBT_SELFHOST_IDLE（默认 900s）→ 权重服务自己退出，4.88 GB 还给系统；
5. 再发消息 → 重新拉起（又是一次冷启）。

## 三、实测数字

| 场景 | 耗时 | 说明 |
|---|---|---|
| 冷启（8792 未监听 → 首个 token） | **169.9s** | 含模型加载（7.4 GB 机器） |
| 温启动（服务已在，不传 upstream） | **10.4s** | 答「中国的首都是北京。」 |
| 闲置退出（测试值 90s） | 130s 后监听数 0 | 内存释放 |
| 修复前（DEFAULT=cfai） | 0.6s | **答的是 Cloudflare 的模型，不是我们的** |

## 四、页面上的三档提示

    2.5s    …正在唤醒本机权重…
    15s     …首次加载 4.88 GB 权重，约 1–2 分钟，别关页面…
    60s     …仍在加载（7.4 GB 内存的机器冷启动偏慢，属正常）…

首字一到就撤掉提示。没有这层提示时，用户看到的就是「卡死」。

## 五、旋钮（环境变量，改完重启桥）

| 变量 | 默认 | 作用 |
|---|---|---|
| GBT_ENABLE_SELFHOST_LANE | 未设 | =1 才启用 selfhost 车道，并把默认车道切成它 |
| GBT_OURS_BASE_URL | 空 | 权重服务地址，本机 = http://127.0.0.1:8792/v1 |
| GBT_SELFHOST_IDLE | 900 | 空闲多少秒退 |
| GBT_SELFHOST_CTX | 256 | 上下文 |
| GBT_SELFHOST_THREADS | 8 | 线程 |
| GBT_OURS_WEIGHTS | state/weights/gbt-v8-v82-q5_0.gguf | 权重路径 |
| GBT_LLM_PY | C:\Python312\python.exe | 用哪个解释器加载 |

## 六、排障

| 现象 | 先看什么 |
|---|---|
| 回答快得反常（<2s） | gbt.weights_ours 是不是 false，gbt.lane 是不是 cfai |
| 一直转圈 | :8792 起了没；桥 stderr 里有没有 [activate] 行 |
| 冷启超过 3 分钟 | 内存够不够（模型 mmap 需要余量） |
| 每次都要冷启 | GBT_SELFHOST_IDLE 是不是被设得太小 |
| 页面没提示「正在唤醒」 | 是不是旧页面缓存（Ctrl+F5） |

## 七、这个设计的代价

- **首次慢**：冷启 170s，换来的是一直不占 4.88 GB 内存；
- 若更在意首字速度：把 GBT_SELFHOST_IDLE 设很大（如 86400），等于常驻；
- 折中值 900s 适合「一天聊几轮」的用法。
