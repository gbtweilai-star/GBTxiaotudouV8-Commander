# 138 · 桌面版「录相机5s」端到端实测（CDP 触发 IPC）

## 一、怎么验的
- 桌面版以 `--remote-debugging-port=9222` 重启；
- Chrome DevTools Protocol 在页面执行：
  ```js
  window.gbtHand.record("C:\\Users\\Public\\gbt-rec-test")
  ```
- 不是靠“按钮看起来在”。

## 二、结果
`record` 返回：
```json
{"ok": true, "code": 0, "dir": "C:\\Users\\Public\\gbt-rec-test", "error": ""}
```
目录产出 **5 个 chunk**：
| 文件 | 大小 |
|---|---|
| chunk-0001.mp4 | 384,089 B |
| chunk-0002.mp4 | 331,665 B |
| chunk-0003.mp4 | 329,710 B |
| chunk-0004.mp4 | 328,050 B |
| chunk-0005.mp4 | 330,768 B |

说明：**Electron 主进程 → PowerShell WinRT 录制子进程**能开相机、能写 chunk；不是 Python 子进程那条失败路径。

## 三、接着 camera_watch
`POST /api/dh/hand {"op":"camera_watch","dir":"C:\\Users\\Public\\gbt-rec-test",...}`
| 项 | 读数 |
|---|---|
| files | 5 |
| frames | **26** |
| detected | **0** |
| moved | 0 |
| fps（处理） | **34.38** |
| realtime_ok | false |

- 录制/读目录/ONNX 都跑通；
- 画面里没有手，所以 detected=0，不伪造；
- 手入镜后才有 moved。

## 四、结论
- 「录相机5s」按钮的 IPC 路径 **端到端可用**；
- 相机不再需要用户手动跑 PowerShell；
- 但当前镜头内容没有手，手部检测需要手入镜。

## 五、清理
- 测试目录 `C:\Users\Public\gbt-rec-test` 已删除；
- 桌面版恢复普通启动（不带 9222 调试端口）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
