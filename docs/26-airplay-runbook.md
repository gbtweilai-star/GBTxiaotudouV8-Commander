# 投屏落地手册（把手机画面真打到墙上）

> 2026-10-27 ｜ 结论先说：**iOS 不开放屏幕镜像的 API**，命令行只能准备内容，按镜像是人手动作。
> 但接收端可以是开源的 —— 不必买 Apple TV。

## 一、三条路，按代价排序

| 路 | 需要的设备 | 代价 | 画质/延迟 |
|---|---|---|---|
| **A. 支持 AirPlay 的投影仪 / Apple TV** | 已有或买 | 最省事 | 最好 |
| **B. 电脑跑开源接收端（UxPlay）** | 一台电脑 + 投影仪/大屏 | 免费，要装 | 好，延迟 0.2–1s |
| **C. Lightning/USB-C 转 HDMI** | 转换器 | 最便宜最稳 | 无损、零延迟（但拖着线） |

**没设备也想投到墙上：物理上不存在。** 手机没有光学投影器。

## 二、路 B 的具体做法（开源，推荐给没有 Apple TV 的场景）

### 接收端在一台 Linux / macOS 电脑上

```bash
# Debian/Ubuntu
sudo apt install cmake libplist-dev libssl-dev libavahi-compat-libdnssd-dev \
                 libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev gstreamer1.0-libav
git clone https://github.com/FDH2/UxPlay && cd UxPlay
mkdir build && cd build && cmake .. && make -j4
sudo ./uxplay -n "GBT-Screen" -nh -vs glimagesink     # 起一个名为 GBT-Screen 的接收端
```

- `-n` 是广播出去的名字，手机上会看到它
- `-nh` 不隐藏光标；`-vs` 是视频显示后端（glimagesink 最顺）
- 项目：`FDH2/UxPlay` ★3,273（原 `antimof/UxPlay` ★2,141，同一份代码的旧仓）

### 手机端

```
控制中心 → 屏幕镜像 → GBT-Screen
```

### 三条必踩的坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 手机里看不到设备名 | 两台不在同一网段 / 路由器开了 AP 隔离 | 连同一个 WiFi，关掉"访客网络隔离" |
| 看得到但连不上 | 防火墙挡了 mDNS(5353) 和 RTP 端口 | 放行 5353/udp 和 7000-7100 |
| 画面卡成幻灯片 | 电脑 GPU 弱 + 1080p 镜像 | 用 `-vs ximagesink` 降负载，或改 720p |

## 三、路 A（有 Apple TV / AirPlay 投影仪）

```
控制中心 → 屏幕镜像 → 选设备
```
或只投视频（更省带宽、更稳）：
```
gbt cinema <视频文件>    → 原生播放器 → 右上角 AirPlay 图标 → 选设备
```

## 四、投屏前该准备什么（这些是我能做的部分）

```bash
# 1. 内容：演示台（1080p 横屏 + 提词 + 计时）
gbt deck --spec deck.json --images assets/ --script --mp4 --burn-subs --review

# 2. 验收：自动八项
gbt deckcheck <目录> --expect-audio --expect-subs

# 3. 审片：三帧拼图，人看一眼
#    确认配图贴题、字幕不挡内容

# 4. 播放：片子用原生播放器起（AirPlay 按钮在里面）
gbt cinema <目录>/deck.mp4
```

## 五、边界（写死在脑子里）

1. **我不能替你镜像** —— 系统 UI，无 API。
2. **我不能替你选设备** —— 同上。
3. **我能保证的是**：内容 1080p 对齐、字幕烧好、旁白在轨、验收八项过、审片图给你。
4. **手机自己发光投墙** —— 没有这个硬件，任何说法都是假的。

---

## 七、自己部署接收端（零成本，不用买硬件）

iOS 能"发"AirPlay，但**必须有人"收"**。接收端可以是你已有的设备：

| 接收端 | 怎么开 | 成本 |
|---|---|---|
| **Mac（macOS 12+）** | 系统设置 → 通用 → 隔空投送与接力 → **隔空播放接收器** → 打开 | ¥0（已有电脑） |
| **Windows / Linux 电脑** | 装 UxPlay（见第二节），或装 AirServer / LetsView 等 | ¥0 |
| **安卓电视 / 智能电视** | 大多自带 AirPlay 或"多屏互动" | ¥0（已有电视） |
| **Apple TV** | 插上就行 | 要买 |

### Mac 当接收端（最省事）

```
① 系统设置 → 通用 → 隔空投送与接力 → 隔空播放接收器 → 打开
② Mac 接显示器 / 电视 / 投影（HDMI 或 AirPlay 串联）
③ iPhone：控制中心 → 屏幕镜像 → 选你的 Mac 名字
```

Mac 自带的接收端**不需要装任何软件**，画质与延迟都比第三方好。

### 为什么不在 iPhone 上"自己部署"接收端

iOS 不向第三方开放 AirPlay **接收**能力：
- `ReplayKit` 只能"发"（录屏/串流），不能收；
- 没有 mDNS 广播 + RTP 收流的权限；
- iSH 里也没有 GStreamer/Avahi。

⇒ **同一台 iPhone 既当发送端又当接收端，在系统层面就被封死了。**
所以"自己部署"的落点是：**用你已有的电脑/电视当接收端**，而不是在手机上再造一个。
