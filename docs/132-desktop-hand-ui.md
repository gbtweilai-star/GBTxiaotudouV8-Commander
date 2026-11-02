# 132 · 桌面版 UI 手部入口（注入按钮）

## 一、实现
`GBT小土豆V8桌面版\resources\app\main.js` 在页面加载后注入：
- 「手部ONNX图片」按钮 → `POST /api/dh/hand {"op":"onnx_image","image":...}`
- 「手部长视频」按钮 → `POST /api/dh/hand {"op":"onnx_chunked","video":...,"frames":150,"chunk":60}`
- 路径用 `prompt()` 输入绝对路径；结果显示 JSON。

## 二、验证
- `node --check main.js` → 语法 OK；
- 重启桌面版后：
  - `/api/proactive?op=status` → **200**
  - `/api/dh/hand` → **200**
- 按钮注入在 `did-finish-load` 里，已有 `gbt-hand-panel` 去重，不会重复添加。

## 三、边界
- 是**桌面壳注入**，不是重新打 Electron 包；
- 路径要绝对路径；
- 摄像头/真机仍是硬件边界；
- UI 按钮调用的是已实测的 API，不是新假接口。

## 四、下一步
1. 把 `prompt` 换成原生文件选择框；
2. 按钮结果做右侧面板，不弹 `alert`；
3. 接 `camera_chunks` 目录选择。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
