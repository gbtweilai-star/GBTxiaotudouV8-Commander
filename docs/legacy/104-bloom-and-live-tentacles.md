# 104 · 3D 星图加 Bloom 辉光 + 按真实调用点亮触手

> 主人 2026-11-01「可以」：上一轮 3D 已是密集网络（385 节点 / 15,400 根视觉触手），
> 这一刀补上"参考图那种辉光"，并且让**真实调用过的能力位把触手点亮**。

## 一、加了什么

| 项 | 做法 |
|---|---|
| **Bloom 辉光** | 内置 three 后处理（`EffectComposer + RenderPass + UnrealBloomPass`，strength 0.75 / radius 0.65 / threshold 0.55），全部本地 vendor，不挂 CDN |
| **按真实调用点亮** | `tools/gen-console-data.py` 读 `gbt_allinone/store/audit.jsonl` 最近 800 条 → 按 `event`（=能力位名）聚合出 `pulse`；3D 里取真实存在的能力位，叠加"暖金呼吸"线段层（`sin` 呼吸透明度） |
| **可巡检标记** | `data-space3d = ok:<能力位>+<域>+<视觉触手>+<点亮数>` |

## 二、实测（刚跑）

```
data-space3d = ok:385+30+15400+4
pulse（最近 800 条审计聚合）= 12 类，Top: inventory(117) · signature_guard(113) · auth_denied(7) …
点亮能力位 = 4 个（确实存在且有真实调用的那些；"ok/call" 这类非能力位事件会过滤掉）
```

截图：`assets/panels/console-space.webp`（Bloom + 点亮层都在）。

## 三、口径（不糊弄）

- 15,400 根 = **视觉展开**（每能力位 40 根），是"亿万根触手"的密度示意；
- 真实触手 = 每次 `run_task` 调用时按需展开并落 `audit.jsonl`；
- 点亮层来自**真实审计**，不是随机动画；
- 缺失依赖/加载失败都有明确兜底（`no-webgl` / `import-err` / `error:...`）。

## 四、依赖（全部本地）

```
holo_pet_w3/assets/vendor/three/
  three.module.js
  controls/OrbitControls.js
  postprocessing/{EffectComposer,RenderPass,ShaderPass,MaskPass,UnrealBloomPass,Pass}.js
  shaders/{CopyShader,LuminosityHighPassShader}.js
```
`tools/console-server.py` + 相对 importmap 直接可用；`file://` 下 ES Module 被浏览器拦时会显示"请用 http 打开"的兜底文案。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
