# 64 · 原生 workflow 导入（秋叶的图能直接进来）（2026-11-01）

> 之前 `validate/run` 只认**我们自己的**图格式 `{"nodes":[{"id","node","inputs"}],"edges":[...]}`；
> 秋叶版保存的图是 ComfyUI **原生格式**（`nodes[].type` + `widgets_values` + `links`），直接喂会报"未知节点"。
> 这一轮把两种格式打通。

---

## 一、打通了什么

新增只读 `op=import`（也可直接在 `validate`/`run` 里传原生图，内部自动转换）：

```
原生：{"nodes":[{"id":1,"type":"EmptyImage","widgets_values":[512,512,0]}, ...],
       "links":[[link_id, origin_id, origin_slot, target_id, target_slot, "IMAGE"], ...]}

转换：type → node；widgets_values 按我们节点声明的输入顺序对位；
      links → edges（源字段用类型名 IMAGE/MASK，我们的引擎两种写法都认）
```

## 二、`widget_mapping=best_effort`（诚实标注）

ComfyUI 的 `widgets_values` 是**位置数组**，没有 schema 时无法 100% 知道哪个值对应哪个输入。
所以我们**按输入声明顺序对位**，并在返回里标 `widget_mapping: "best_effort"`；
widgets 多于声明输入时会记 notes（多出几个、已忽略）——**不装作精确**。

## 三、实测（合成一张"秋叶风格"的图）

```
输入：EmptyImage(widgets 16,16,0) → KSampler → MaskBlur(widgets 2)，两条 links
导入：converted = {nodes: 3, edges: 2} · widget_mapping = best_effort
校验：native_used   = [EmptyImage, MaskBlur]      ← 我们能跑
      contract_only = [KSampler]                  ← 契约里有、我们没接
      unwired       = [{KSampler, category: model, how: 要 GPU/权重（本机不接）}]
      verdict       = 部分节点要 ComfyUI
```

意思是：**秋叶的图进来，我们能立刻说清"哪几个节点我能跑、哪几个要 GPU、有没有未知节点"**，
而不是一句"未知节点"就打回去。

## 四、判据（`test_comfy_engine` 第 [15] 组 3 条）

- 原生图被转换（3 节点 / 2 边）
- 原生节点被认出来（EmptyImage/MaskBlur）
- 未实现的 KSampler 归到 contract_only 且**带不能跑的原因**

## 五、边界（不吹）

1. 只做**转换与校验**；`run` 跑原生图时仍要求节点都在我们的 `NODES` 里（否则如实报未接线）；
2. `widgets_values` 映射是 best-effort，**真要精确**得等秋叶真快照（`/object_info` 里带 input schema）；
3. 原生图里的 `Reroute`/`Note` 这类纯前端节点没有实现 —— 会出现在 unknown 里，如实报。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
