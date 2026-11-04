# 127 · 黑色皮肤 · 完整设置 · 便携打包

日期：2026-11-02 · 截图：`dark-chat.png`、`settings-model.png`、`settings-behavior.png`

## 1. 皮肤回到深色
保持新版结构（无衬线 / 高密度 / 胶囊输入 / 下划线页签），底色换回 `#161718`，卡片 `#1d1e20`，1px 白 7% 细边，陶土色 `#c96442` 点缀；无背景特效、不挡对话框。

## 2. 设置（⚙）补全
弹窗五个页签，全部读写 `state/app-settings.json`：

| 页签 | 内容 |
|---|---|
| 模型 | 提供方（OpenAI 兼容）、Base URL、API Key、模型名、temperature、max_tokens、timeout、系统提示词、**测试连接**、保存后 `/api/chat` 立刻走你的模型 |
| 外观 | 主题、字号缩放、信息密度（舒适/紧凑）、减少动画 |
| 行为 | 界面语言、Enter 发送、系统通知、提示音、开机自启 |
| 数据 | 数据目录、记忆链开关、自动备份目录、导出/导入设置、导出记忆索引 |
| 高级 | 网络代理、失败重试、上下文模式、窗口字符数 |

接口：`GET/POST /api/settings`、`POST /api/model-test`；聊天：`/api/chat` 先读设置，有 `base_url`+`name` 就走 OpenAI 兼容 `/chat/completions`，否则走本机 `energy_core` 兜底。

## 3. 便携打包
| 项 | 路径 |
|---|---|
| 文件夹 | `dist/GBT小土豆V8/`（57.9 MB，2519 个文件） |
| 压缩包 | `dist/GBT小土豆V8-portable.zip`（**25.5 MB**） |
| 启动 | 双击 `启动.bat`（起服务 + 开浏览器） |
| 停止 | 双击 `停止.bat` |
| 内置 | `pyembed`（Python 3.13.9）、服务、工具、界面、state、icons |
| 排除 | `holo_pet_w3/kaleido`（29.6MB demo 视频）、`holo_pet_w3/voice-theater`（33MB GLB 模型） |

### 用自己的模型
1. 启动后点右上角 **⚙ 设置 → 模型**；
2. Base URL 填 OpenAI 兼容地址（llama.cpp / Ollama / vLLM / LM Studio / Claude 代理 / OpenAI 均可），填 API Key（本地可空）和模型名；
3. **测试连接** → 通过后 **保存设置**；
4. 对话即走自己的模型。也可直接改 `state/app-settings.json` 后重启。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
