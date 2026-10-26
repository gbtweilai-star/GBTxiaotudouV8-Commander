# 她的生图：接自建端点（契约 + 现状）

> 2026-10-26 ｜ 主人令：「换成她自己的 Qwen-Image 权重」
> 结论先说：**本机跑不了**，只能接自建端点。下面写清为什么、还差什么、怎么接。

## 一、本机跑不了（证据，不是判断）

```
运行时   torch 缺 · diffusers 缺 · transformers 缺 · onnxruntime 缺 · mlx 缺     0/5
权重     /var/minis 下没有任何 qwen-image / *.safetensors / flux 权重
端点     8188 / 8189 / 5000 / 7860 全部无监听
硬件     8 GB 统一内存 · 无 CUDA
```

Qwen-Image 是 20B 级 MMDiT（bf16 约 40 GB；4-bit 量化也要十几 GB）。
**这不是"没打开"，是这台机器装不下。** 手机端唯一可行的位置是"端点那一侧"。

## 二、节点认的契约（窄，但够用）

`comfy_native.t2i_qwen` 只认这一种：

```
POST  <GBT_T2I_ENDPOINT>
      {"prompt": "...", "size": "768x1024", "steps": 8, "seed": 29}

200   → {"image_b64": "<base64 png/jpg>"}    或   {"url": "https://…"}
非200 → 视为失败，**把回包正文原样带出**（2026-10-26 修：原来只回 "HTTP Error 501"，把原因藏了）
```

每次成功必须带回四项能源读数：**步数 / 秒 / 显存峰值 / 花费**。报不出 = 没做完。

## 三、三条接法（按"是谁的算力"排）

| 路 | 命令 | 算力归属 | 用途 |
|---|---|---|---|
| A 自建（要的那条） | `export GBT_T2I_ENDPOINT=http://<host>/v1/images/generations` | **她的权重** | 正式出图 |
| B 契约壳（本地转发） | `T2I_BACKEND=http://<host>/prompt python3 tools/t2i_endpoint.py --port 8899` | 取决后端 | 后端回包形状不规范时套一层 |
| C 免费公共对照 | `export GBT_T2I_ENDPOINT=pollinations` | **第三方** | 只做对照，不许冒充她 |

B 的壳已在跑，实测验过：

```
GET  /health            → {"ok": false, "missing": ["T2I_BACKEND（要指向你自建的出图服务）"]}
POST /v1/images/generations → 501 {"status":"needs_dependency","missing":["T2I_BACKEND"],
                                   "口径":"没有后端就不假装出图"}
```

接上节点后的失败链也验过（501 会一路带出人话，不再只说 HTTP Error）：

```json
{"ok": false, "status": "call_failed", "node": "t2i_qwen",
 "error": "HTTPError: HTTP Error 501",
 "回包": "{\"status\":\"needs_dependency\",\"missing\":[\"T2I_BACKEND\"],\"口径\":\"没有后端就不假装出图\"}"}
```

## 四、还差什么（逐项）

1. **一个能跑 Qwen-Image 的机器**（≥24 GB 显存，或 A100/H100；RunPod 单卡按需即可）。
2. **权重**：`Qwen/Qwen-Image`（bf16 约 40 GB；4-bit 量化版十几 GB）。放在那台机器上，不在手机上。
3. **一层 HTTP**：把那台机器包成上面那个契约（diffusers 脚本 / vLLM / ComfyUI 都行）。
4. 把 URL 写进 `GBT_T2I_ENDPOINT`（手机侧只需要这一条）。

## 五、闸挂在哪

`tools/taste_gate.py` 是**交付前门禁**，与端点无关：

```
出图 → taste_gate --judge <图> --profile photo
        PASS → 交付
        FAIL → 按不过的那一轴改一处（提示词/构图/色），再跑
```

已实测一轮：留白 9.7%（FAIL）→ 提示词加负空间 → 留白 30.5%（PASS），对比 30.1 → 51.1。

**闸的诚实边界**：`人体结构 / 布料走向 / 透视一致 / 材质纹理` 四轴 **not_measurable**，
它判不了画得像不像，只判有没有犯禁。

## 六、验收（端点接上后跑这三条）

```bash
curl -s $GBT_T2I_ENDPOINT/../health            # 端点自报
python3 -c "…run_task('comfy_native', {'op':'run','workflow':…})"   # 真出图 + 四项读数
python3 tools/taste_gate.py --judge <产物> --profile photo          # 过闸
```
