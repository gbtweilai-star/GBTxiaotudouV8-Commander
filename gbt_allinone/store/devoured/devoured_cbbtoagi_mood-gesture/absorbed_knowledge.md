# cbbtoagi/Mood-Gesture 吞噬记录 — devour_tentacle
> 吞噬日期: 2026-11-01T07:31:59 | 来源: https://github.com/cbbtoagi/Mood-Gesture
> Stars: 0 | 语言: Python | 许可: NOASSERTION

## 项目概览
- 描述: 情指传暖 Mood-Gesture — 基于单只开源灵巧手的人脸情绪感知与虚实双轨情感陪伴系统：Face emotion → LLM blessing → dexterous-hand gesture → AI postcard
- 主题: dexterous-hand, emotion-recognition, fastapi, human-robot-interaction, llm, mediapipe, robotics, websocket
- 分支: main | 最近推送: 2026-09-05

## README 摘要
# 情指传暖 Mood‑Gesture

基于单只开源灵巧手（softsync 六自由度 / FlexHand）的**人脸情绪感知与虚实双轨情感陪伴系统**。

用户面向摄像头 → 系统实时识别情绪（疲惫 / 焦虑 / 低落 / 平静 / 愉悦）→ 大模型生成个性化暖心祝福 → 灵巧手做出适配的实体手势（安抚 / 呼吸引导 / 点赞 / 轻挥 / 比心）→ 自动生成专属 AI 艺术明信片，手机扫码即可保存这份情绪纪念品。

```
┌────────────┐   摄像头帧    ┌──────────────────────────────┐
│  浏览器 UI  │─────────────▶│  MediaPipe FaceLandmarker    │
│  (web/)    │◀─────────────│  52维 blendshapes 规则情绪引擎 │
└─────┬──────┘   情绪/事件   └──────────────────────────────┘
      │ WebSocket /ws/agent（全流程事件流）
      ▼
┌────────────────────────────────────────────────────────────┐
│  FastAPI 编排器 (server/app.py)                              │
│  ① LLM 流式祝福（OpenAI 兼容；断网自动切本地模板兜底）          │
│  ② FlexHand 驱动：10Hz 插值下发手势（server/hand/）           │
│  ③ Pillow 程序化艺术明信片 + 二维码（server/postcard.py）      │
└────────────────────────────────────────────────────────────┘
```

**无硬件也可完整演示**：灵巧手驱动内置模拟模式，页面上的 SVG 手掌与实体手同源驱动；页面右下角有演示模式与调试面板。

---

## 一、快速开始

### Windows（推荐用启动脚本）

1. 安装 [Python 3.10+](https://www.python.org/downloads/)，安装时**勾选 "Add python.exe to PATH"**；
2. 解压本压缩包到任意目录（建议路径不含特殊字符），**双击 `start.bat`**；
   - 首次运行需联网安装依赖（约 25MB，一次性），之后启动不再联网安装；
   - 浏览器会自动打开 `http://localhost:8000`；Windows 防火墙首次弹窗时选「允许访问」；
   - 停止：在黑色命令行窗口按 `Ctrl+C` 或直接关窗。

命令行用户等效操作：

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python run.py
```

### macOS / Linux

```bash
./start.sh          # 或手动：
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py                            # 默认 http://0.0.0.0:8000
```

浏览器打开 `http://localhost:8000`：

1. 点 **「开启摄像头」** 授权 → 面向镜头，情绪仪表开始跳动；
2. 保持某一种稳定情绪约 3 秒 → 出现 3 秒倒计时 → 自动开始一次完整陪伴；
3. 也可以点右侧 **「手动体验」** 五个按钮直接触发，或点 **「演示模式」**（自动循环五种情绪，无需摄像头）。

表情模型（MediaPipe FaceLandmarker，约 11MB）已全部本地化在 `web/vendor/mediapipe/`，**演示不依赖外网**；只有调用大模型 / 图像 API 时才需要联网。

> Windows 下明信片使用系统自带微软雅黑（msyh.ttc）排版，无需额外字体；如需特殊字体，可将 TTF 命名为 `fonts/font.ttf` 放入项目根目录优先使用。

## 一点五、继续开发

本项目即开发即部署一体：无硬件时用模拟手开发，接手后只换连接配置。

```bash
python run.py --mock --reload   # 开发模式：模拟灵巧手 + 后端热重载
python run.py --mock            # 模拟手演示（不尝试连实体手）
python -m pytest                # 测试套件（21 例，无硬件无外网，约 6s）
python run.py --port 8010       # 指定端口
```

- Windows：`dev.bat`（开发模式）/ `dev.bat test`（测试）；macOS/Linux：`dev.sh` 同理；VS Code 可直接 F5。
- **开发指南（架构、WS 协议、手势编写、情绪调参、灵巧手迁移步骤）见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**。

## 二、配置

复制 `config.example.json` 为 `config.json`（已被 git 忽略），或用环境变量覆盖（`LLM_API_KEY` 等）：

| 配置项 | 说明 |
|---|---|
| `flexhand_url` | FlexHand WebSocket 地址，默认 `ws://192.168.4.1:81/` |
| `flexhand_mode` | `auto`（先试真实连接，失败自动模拟）/ `real` / `mock` |
| `flexhand_invert` | 通道语义反向标定时设 `true`（见「四、灵巧手联调」） |
| `flexhand_period_ms` | 控制周期，默认 100ms（协议建议值） |
| `llm_base_url` / `llm_api_key` / `llm_model` | 任意 OpenAI 兼容接口：智谱 `https://open.bigmodel.cn/api/paas/v4` + `glm-4-flash`、DeepSeek、Qwen、OpenAI…。**留空则用本地祝福模板**（演示可用） |
| `img_base_url` / `img_api_key` / `img_model` | 可选图像生成 API（OpenAI `/images/generations` 兼容）。留空则用内置程序化艺术生成（离线可用、按情绪配色） |
| `public_base_url` | 明信片二维码指向的地址。留空自动探测本机局域网 IP，如 `http://192.168.1.5:8000` |

## 三、页面功能

- **情绪感知**：摄像头 + 本地 blendshapes 规则引擎（微笑/皱眉/眨眼/瞪眼/抿嘴等时序特征 + 疲惫的持续闭眼与「平淡表情」累积检测），2.6s 稳定窗口去抖。
- **自动陪伴**：稳定情绪保持 3s 且距上次陪伴 18s 以上 → 3 秒倒计时（可点击取消）→ 触发。演示模式节奏更快。
- **暖暖的手**：SVG 手掌 1:1 复现实体六通道状态；下方进度条与真实动作时长同步。
- **情绪明信片**：按情绪配色生成 1080×1440 明信片（极光底纹 + 祝福语 + 日期 + 落款 + 二维码），右下角扫码 → 手机落地页（长按保存）。
- **调试面板**（右下角抽屉）：
  - 连接：填地址直连 / 切模拟模式 / PING 测试 / 紧急停止(STOP) / HOME_ALL 归零；
  - 通道控制：6 个滑条实时驱动实体手，同步显示 ST 广播值；
  - 原始指令：可发 `S:3:50`、`REFRESH`、`PLAY_G:xxx` 等任意协议指令；
  - 手势触发：五个情绪手势 + 归零；事件日志实时滚动。

## 四、灵巧手部署联调指南

### 1. 网络拓扑（重要）

FlexHand 自建热点且**只允许 1 台终端接入**，电脑连上它的 Wi‑Fi 后就没有剩余名额给手机了。推荐两种接法：

- **方案 A（推荐）**：电脑用 **USB 网线转换器 / 第二块 USB Wi‑Fi 网卡** 接入路由器，内置 Wi‑Fi 连 FlexHand 热点。手机与电脑同处路由器网络 → 扫码可打开明信片落地页。
- **方案 B（纯离线演示）**：只连 FlexHand 热点。系统一切功能可用，但二维码指向的落地页手机打不开——明信片本身仍会生成，可全屏后截图/长按保存，或投影展示。

二维码基座地址可在 `config.json` 的 `public_base_url` 中显式指定（如 `http://192.168.1.5:8000`）。

### 2. 联调步骤

```bash
# ① 电脑连接 FlexHandV1_AP（密码 12345678），确认设备已关闭「展览模式」
#    （展览模式会拦截实时 S 指令且可能无错误回复）
# ② 协议冒烟测试（对应协议 §11 验收清单 01–06）
.venv/bin/pip install websocket-client
.venv/bin/python scripts/flexhand_smoke.py
# ③ 启动主程序，右上角灵巧手状态应变为「已连接」
.venv/bin/python run.py
# ④ 打开调试面板：先 PING 测试 → 拖动每个滑条确认六通道方向 → 归零
# ⑤ 逐个触发五个手势，观察幅度与节奏，需要则调整 server/hand/gestures.py
```

### 3. 通道语义与标定

- 软件内部统一语义：**0 = 伸展（张开），100 = 屈曲（握拢）**；
  通道 1 拇指屈伸 / 2 拇指辅助 / 3 食指 / 4 中指 / 5 无名指 / 6 小指。
- 若实机方向相反（如 100 才是张开），把 `config.json` 中 `flexhand_invert` 设为 `true` 即可整体翻转，**无需改手势库**。
- 手势库在 `server/hand/gestures.py`，每个手势是若干关键帧（姿态 + 时长），驱动按 100ms 周期在帧间插值、只下发变化 ≥1% 的通道、固定 1→6 顺序——与协议 §8 的建议一致。
- 驱动已内置：心跳 PING（11s）、断线 1.5s 重连 + REFRESH 重同步、退出前 HOME_ALL、ST 按广播处理（不与单条指令强绑定）、未知消息忽略。

### 4. 手势一览

| 情绪 | 手势 | 设计 |
|---|---|---|
| 疲惫 | 轻抚安抚 | 张开的手掌缓慢轻合两次，如轻拍安抚 |
| 焦虑 | 呼吸引导 | 4-4 节奏的开合三次，手掌即呼吸拍子 |
| 低落 | 点赞 | 握拳立拇指并轻顶两次 |
| 平静 | 轻挥 | 四指波浪轻挥两轮 |
| 愉悦 | 比心 | 拇指食指相触成心，带心跳式轻压 |

## 五、验收清单

- [ ] 无硬件：演示模式完整跑通 感知→祝福→手势→明信片→扫码落地页
- [ ] 冒烟测试 01–06 全过（`scripts/flexhand_smoke.py`）
- [ ] 调试面板六滑条方向正确（必要时 `flexhand_invert: true`）
- [ ] 五个手势幅度/节奏自然，必要时调 `gestures.py` 关键帧
- [ ] 配置 LLM 后祝福为实时生成（顶栏「大模型」变绿）；断网自动回退本地模板并提示
- [ ] 手机扫码能打开明信片落地页（方案 A 网络下）
- [ ] 10 分钟连续运行无断连、无消息堆积（协议验收 05）

## 六、目录结构

```
Mood-Gesture/
├── start.bat / start.sh       # 一键启动（演示/部署用）
├── dev.bat / dev.sh           # 一键开发模式（模拟手 + 热重载；dev.bat test 跑测试）
├── run.py                     # 启动入口（--mock / --reload / --port / --host）
├── config.example.json        # 配置样例（复制为 config.json）
├── requirements.txt           # 运行依赖
├── requirements-dev.txt       # 开发依赖（pytest）
├── pytest.ini / conftest.py / test/   # 测试套件（21 例，无硬件可跑）
├── docs/DEVELOPMENT.md        # 开发指南（架构/协议/手势/情绪调参/灵巧手迁移）
├── scripts/flexhand_smoke.py  # FlexHand 协议冒烟测试（联调日使用）
├── server/
│   ├── app.py                 # FastAPI：编排 + WS 事件流 + 落地页
│   ├── config.py              # 配置加载
│   ├── llm.py                 # LLM 流式祝福 + 本地兜底
│   ├── postcard.py            # 明信片艺术生成 + 二维码
│   └── hand/
│       ├── flexhand.py        # FlexHand WS 驱动（真实/模拟双模式）
│       └── ge

## 对 GBT 的启示
- 可吸收点: 结合仓库定位与 README 技术栈, 提炼可注入 GBT cap 的知识