# 交接文档（换会话从这里接上）

> 2026-10-27 ｜ 本文件只写**现在是什么状态、怎么跑、卡在哪**。历史细节见 `docs/17–29`。

## 一、三条主线，各自的状态

| 主线 | 状态 | 一句话 |
|---|---|---|
| **她（A19 本地权重）** | ⏸ **容器 DOWN** | 接线全通，只差 LM Pocket 点一次 `Load & Start Server` |
| **图像（生成/修复/出片）** | ✅ 可用 | 5 轴修复 4 路线择优，6 张里 4 张能过闸 |
| **投屏/演示** | ✅ 可用（零成本） | 网页装置 v8 + 三种零成本投墙法 |

## 二、所有命令（`gbt <子命令>`）

```bash
gbt doctor                全套体检（11 项带读数，未通则退出码 1）
gbt status                一眼看全（容器/桥/队列/账本）
gbt judge                 “开源现成方案”能不能落到本机（四问）
gbt project               投屏能力自检（不假装已连设备）
gbt receiver              自己部署接收端（Mac 自带 / UxPlay / 智能电视）
gbt freeproject           零成本投墙（透镜 / 拆旧 LCD / 已有大屏）
gbt beam [--check]        起视觉装置 v8 + 交给 Safari
gbt assets                素材台账（大小/指纹/标签 + 孤儿/缺失自检）
gbt grab --tags a,b       把最新截图自动入库
gbt ingest <文件…>        手工入库（查重 + 算 sha256）
gbt deck --spec/--topic   出片（HTML/MP4/讲稿/旁白/字幕）
gbt deckcheck <目录>      成品八项验收
gbt cinema <视频>         转码 + 原生播放器起片（AirPlay 就在里面）
gbt fix <图>              单图修复（--declutter --reframe）
gbt batch '<glob>'        批量修复 + 报告（--video 出片）
gbt video K1 K2 [K3]      静帧 → 动作镜头（甩镜/尘环/速度线/音效）
gbt gate <图>             品味判据（7 轴可量 + 4 轴如实标不可判）
gbt persona               她的人格两版字数/token 对照
gbt a19 status|up|ask|chat|test     她的嘴/脑/体检
gbt test                  人格五项（防编造/情绪/边界）
gbt doc                   手册清单
```

## 三、三个卡点（每个只要一个动作）

| 卡点 | 现象 | 谁来解 | 解开后我做什么 |
|---|---|---|---|
| A19 容器 | `:1234` 一直 DOWN，8 条深链全证伪 | **你**：LM Pocket → Load & Start Server（顺带开「启动时自动加载」） | 跑 `a19_accept.sh`：身份自述 + 五项体检 + prefill 预算 + 切换判定 |
| 相机 | App 内 WebView 里 `getUserMedia` 挂起（既不回也不报错） | **你**：Safari 打开 `http://127.0.0.1:8080/kaleido/v8.html` | 若通，补“录制直传/多效果/场景预设” |
| 原生 App | `ios/SpaceBeamLite` 代码完整 612 行，未编译 | **你**：任一 Mac 或 GitHub Actions 跑 `xcodebuild` | 按报错改，直到能装到真机 |

## 四、关键文件地图

```
tools/            全部执行件（gbt 是唯一入口）
state/            taste_kernel.txt（品味内核）· her_persona*.txt（人格）
                  her_transcript.jsonl（她的对话账本）
runtime/          model_bridge.py（桥，10 车道）· gbt_allinone/（完整包）
holo_pet_w3/      她的原生页面 · window.css（重建的壳层）· kaleido/（网页装置 v8）
ios/SpaceBeamLite/ 原生工程（Swift + Metal + xcodegen + Actions 工作流）
docs/17–29        口径/手册/评估，每份都有“为什么这么做”
/var/minis/attachments/assets/  素材库 + manifest.json（带 sha256）
```

## 五、十条教训（都是真金白银踩出来的）

1. **WebView 按 URL 缓存 CSS/JS/HTML** —— 改完看不到效果，先换文件名或加版本号。
2. **`border:1px solid transparent` 仍是 1px 边框** —— 判据看宽度不看颜色。
3. **特异性**：`button.ghost` 压得过 `.ghost`，覆盖要写全。
4. **逐步贪心会丢最优解** —— 修复路线要“全跑完再择优”。
5. **LAB 的 a/b 通道不能平移** —— 撞极值出紫绿噪斑。
6. **放大≠变清晰** —— 同尺寸高频不升反降就是假细节。
7. **文件名规则判不了相关性** —— 自动配图只认 `assets/`，否则会抓私人照片。
8. **`subprocess.run([...], shell=True)` 只执行第一个词** —— 列表配 argv，字符串配 shell。
9. **iSH 里每步都要按秒算** —— 像素流水线必须 `--maxw 900`，否则批次必超时。
10. **没有读数的判断等于没判断** —— 每条修复都先量、再改、再量。

## 六、下次接上时，先跑这三条

```bash
gbt doctor                     # 全套体检：管路/素材/判据/文档/工程一次看全
gbt status                     # 容器/桥/队列是否活着
gbt assets                     # 素材库是否干净（指纹/孤儿/缺失）
gbt judge                      # 若有人提出新方案，先四问过一遍
```

## 七、边界（写死，别再犯）

- **手机摄像头永远不发光**：成像器件，不能出图。
- **闪光灯能照亮胶片，不能成像**：所以是“闪光灯+胶片+透镜”，不是“闪光灯投影”。
- **iPhone 是 OLED**：拆机强背光那套（Hackaday）不适用，只有 LCD 机型能玩。
- **iOS 不支持 Miracast**：无线只有 AirPlay，且接收端必须存在。
- **本机编不动 sd.cpp**：301 个目标，实测 1 个/2 分钟，ETA ~9 小时，已放弃。
