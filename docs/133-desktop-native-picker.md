# 133 · 桌面版 UI：原生文件选择 + 结果面板

## 一、实现
- 新增 `resources/app/preload.js`：
  ```js
  contextBridge.exposeInMainWorld("gbtHand", { pick: (kind) => ipcRenderer.invoke("hand:pick", kind) });
  ```
- `main.js`：
  - `preload: path.join(__dirname, "preload.js")`；
  - `ipcMain.handle("hand:pick")` → `dialog.showOpenDialog`，按图片/视频过滤；
  - 页面按钮不再 `prompt()`，改为原生文件选择；
  - 结果不再 `alert()`，改为右下 `pre` 面板显示 JSON。

## 二、验证
- `node --check main.js` → **OK**；
- `node --check preload.js` → **OK**；
- 重启桌面版：
  - `/api/proactive?op=status` → **200**
  - `/api/dh/hand` → **200**
- 按钮调用已实测 API：`onnx_image` / `onnx_chunked`。

## 三、边界
- 仍是**桌面壳注入 + preload**，不是重打 Electron 安装包；
- 文件选择走主进程 dialog；
- 摄像头/真机仍是硬件边界。

## 四、下一步
1. 把结果面板做成可折叠；
2. `camera_chunks` 目录选择；
3. 真机/摄像头接入。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
