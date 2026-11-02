# 137 · 桌面版 UI：录相机5s + catalog

## 一、新增
- `payload/tools/camera-winrt-record-loop.ps1`、`camera-winrt-video.ps1` 已随桌面版；
- `preload.js` 新增 `record(dir)`；
- `main.js` 新增 `ipcMain.handle("hand:record")`：
  - 跑 `powershell camera-winrt-record-loop.ps1 -OutDir <dir> -Chunks 5 -SecondsPerChunk 0.5`；
  - 返回 `{ok,code,dir,error}`。
- UI 新增「**录相机5s**」按钮：
  - 选输出目录 → 录 5×0.5s → 自动 `camera_watch` 处理。

## 二、验证
- `node --check main.js` → OK；
- `node --check preload.js` → OK；
- 重启桌面版：`/api/proactive?op=status` → **200**；
- WinRT 录制脚本本身已实测：0.3s/1s chunk 可录；
- **UI 按钮未做自动点击测试**，只验证了接线/语法/服务存活，不冒充端到端已验证。

## 三、边界
- WinRT 录制依赖桌面版用户会话；如果子进程 WinRT 被系统拒绝，按钮会返回错误而不是假成功；
- `camera_watch` 仍只处理已完成 chunk；
- 真机/摄像头硬件边界不变。

## 四、下一步
1. 手动点「录相机5s」，看 `record` 返回；
2. 若 WinRT 子进程失败，退回外部 PowerShell 录制；
3. 真机接入。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
