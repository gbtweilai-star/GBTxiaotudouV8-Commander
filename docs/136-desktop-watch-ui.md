# 136 · 桌面版 UI：监视相机目录按钮

## 一、实现
- `main.js` 注入第 4 个按钮「**监视相机目录**」；
- 复用 `pickDir()` 选目录；
- 调用：
  ```json
  {"op":"camera_watch","dir":"<selected>","seconds":3,"max_chunks":20}
  ```
- 结果仍在右下可关闭面板显示。

## 二、验证
- `node --check main.js` → OK；
- 重启桌面版：`/api/proactive?op=status` → **200**、`/api/dh/hand` → **200**；
- `camera_watch` API 已实测：150帧 / detected150 / moved150 / **45.29fps** / realtime true。

## 三、当前 UI 四个入口
| 按钮 | 输入 | op |
|---|---|---|
| 手部ONNX图片 | 图片 | `onnx_image` |
| 手部长视频 | 视频 | `onnx_chunked` |
| 相机chunk目录 | 目录 | `camera_chunks` |
| 监视相机目录 | 目录 | `camera_watch` |

## 四、边界
- WinRT 录制仍由外部 PowerShell；桌面 UI 不直接开相机；
- `camera_watch` 只处理目录中新出现的 chunk；
- 真机/摄像头硬件边界不变。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
