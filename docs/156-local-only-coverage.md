# 156 · 本地项目口径：cloud 节点不算目标，分母扣除

## 一、为什么改
用户口径：**这是本地项目，不要再把云端当缺口。**
ComfyUI 上游目录里确实有 368 个远端 API 节点（Kling/OpenAI/Flux/Recraft…），但它们：
- 不是本地能力；
- 需要 key；
- 不该算进“本地补齐”的分母。

## 二、改动
`comfy_native op=coverage` 增加：
```json
{"contract_total": 1033,
 "native_total": 146,
 "local_total": 665,
 "local_native": 146,
 "local_coverage": 0.2195,
 "cloud_total": 368,
 "cloud_policy": "excluded_not_local_target"}
```
- `local_total = 1033 - 368 = 665`；
- 本地真实覆盖 **146 / 665 = 21.95%**；
- cloud 只报数量，不参与本地覆盖率；
- traditional 缺口 **0**。

## 三、桌面版同步
`GET /api/tianzhen?op=coverage`：
```
status=200 contract=1033 native=146
local_total=665 local_cov=0.2195 cloud=368 trad=0
```
不再把 368 个云端节点混进“本地还差多少”。

## 四、边界
- 425 模型面仍是本地但需权重/CPU；不假装已接；
- 368 云端面明确**不接、不算本地目标**；
- 本地 ComfyUI CPU 在 8188 跑，object_info 1033 是真快照；
- 秋叶整包 ~1495 仍没有。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
