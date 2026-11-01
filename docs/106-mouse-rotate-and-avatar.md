# 106 · 鼠标转动她 + 中心放她的头像（顺带修掉 /icons 404）

> 主人 2026-11-01：「不能使用鼠标转动她吗？」——能，而且这次做了三件事：
> 整块都能拖、中心放她的头像、给"拖动真的生效"加了可验证的检测。

## 一、鼠标转动（已实测）

| 项 | 做法 |
|---|---|
| 拖拽区域 | OrbitControls 从只绑 `<canvas>` 改为绑 **整个 `.space3d-wrap`**（整块 3D 区域都能抓） |
| 参数 | `rotateSpeed 0.75` · `zoomSpeed 0.9` · 滚轮缩放 · 左键拖动旋转 · 禁用平移（避免误拖飞） |
| 光标 | `.space3d-wrap { cursor: grab }` / `:active { cursor: grabbing }` |
| 触屏 | `touch-action: none`（触摸也能拖） |
| **自检** | `?selftest=1` 时程序化派发 pointerdown/move/up，比较相机位移：`data-space3d-drag = ok:14.491`（真的转了 14.49 单位，不是"绑了就算"） |

## 二、中心是"她"

- 中心放**她的头像球**（`icons/avatar.png`），深底圆盘贴图（去白底，避免 Bloom 炸成白团）；
- 她自己在慢速自转（`rotation.y += 0.006`），鼠标拖动时随场景一起转；
- 加载成功写标记 `data-space3d-avatar = ok`（失败写 `load-failed`，不装）。

## 三、顺带抓到的真 bug：/icons 404

console-server 的静态根是 `holo_pet_w3/`，而头像在仓库根 `icons/` ⇒ 用 **http 打开时**
`/icons/avatar.png` 一直 404（左栏品牌头像空白、3D 中心头像加载失败）。
**修法**：console-server 增加 `/icons/*` 白名单路由（限制在 `icons/` 目录内，防穿越）。
修完实测：`/icons/avatar.png → 200 · 228KB · image/png`。

> 说明：无头截图对 WebGL 的合成有限制（Bloom 会糊），但"转动是否生效""头像是否加载"都有 DOM 标记可查，
> 不靠截图猜。

## 四、怎么用

```
http://127.0.0.1:8766/console/index.html#space
```
- 按住**鼠标左键拖动** = 转动整片星图（她随场景转）；
- **滚轮** = 拉近/拉远；
- 点其他页签（对话/功能表/技能栏/仪表盘）不影响已加载的 3D 状态。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
