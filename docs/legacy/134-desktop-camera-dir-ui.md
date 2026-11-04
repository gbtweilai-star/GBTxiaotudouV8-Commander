# 134 · 桌面版 UI：相机 chunks 目录选择 + 可关闭结果面板

## 一、实现
- `preload.js` 新增 `pickDir`：
  ```js
  pickDir: () => ipcRenderer.invoke("hand:pickDir")
  ```
- `main.js` 新增 `ipcMain.handle("hand:pickDir")` → `dialog.showOpenDialog({properties:["openDirectory"]})`；
- UI 新增「**相机chunk目录**」按钮：
  - 选目录 → `POST /api/dh/hand {"op":"camera_chunks","dir":...,"max_chunks":3}`；
- 结果面板改为右下 `pre`，点击面板可关闭，不再 `alert`。

## 二、验证
- `node --check main.js` → OK
- `node --check preload.js` → OK
- 重启桌面版：`/api/proactive?op=status` → **200**
- 三个入口：`onnx_image` / `onnx_chunked` / `camera_chunks` 都已实测 API。

## 三、边界
- 仍然没有 WinRT 直连桌面内；`camera_chunks` 需要外部先录 chunk 目录；
- 真机/摄像头硬件边界不变。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
