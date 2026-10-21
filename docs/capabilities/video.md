# 视频 · `video`（14 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。

| 能力位 | 类型 | 需参数 | 它做什么 |
|---|---|---|---|
| `actioncam` | **需授权** | — | 动作镜头控制系统（拍子表制）：10 种动作运镜语法（POV 主观/甩镜/急推/手持抖/推拉/环绕/打击帧停格）× 4 种机位角度（仰/俯/平/荷兰角）× 画质档（hd/fhd/cinema）；拍子表 manifest 为唯一真相，逐拍渲染 + 总装调色；零逗号表达式纪律 + 种子… |
| `audio_extract` | **需授权** | — | 从视频里取出声音（本机 ffmpeg，**零出网**）：probe/tracks 读流与音轨（只读）；extract 真出音频件（mp3/aac/m4a/wav/flac/ogg/opus/wma 八种，可切段/调音量/响度归一）。**产出即验证**：落盘后 ffprobe 回读… |
| `audio_mix` | **需授权** | — | 混音与母带（本机 ffmpeg，**零出网**）：`mix` 多轨合成（amix，逐路音量，显式 normalize=0）；`master` 响度归一（**两遍法 loudnorm**：先量后施加，第一遍的四个测量值随结果返回）。响度标准表 streaming -14 / pod… |
| `digital_human` | 只读 | — | 数字人「以图生视频」（本地 SadTalker，零账号/零验证）：**一张照片 + 一段配音 ⇒ 带头部动作与口型同步的说话视频**。ops：status/probe 只读（引擎·权重·venv 缺件如实报）· capabilities 读边界 · render 写（异步出片回… |
| `edit_pipeline` | **需授权** | — | 剪辑引擎（蒸馏剪映时间线语义）：轨道→片段→目标/源时间区间→变速/音量/转场/文本，真渲染 1080x1920 成片（ffmpeg + libass 烧字幕）或导出剪映草稿；写面自收窄到 projects/·outputs/·.scratch/（policy 无条目 ⇒ 门内零… |
| `h3_video_gen` | 只读 | — | H3mini 视频生成（只读骨架·门）：四原语 T2VA/I2VA/FL2VA/Ref2VA + 三条带牙用例（密钥不走明文 / 结果必须落盘 / 提示词必须走官方六段式不接受散文式）+ 五条红线（密钥DPAPI/结果落盘/不绕官方入口/硬件门槛先验/每次留痕）；**引用官方仓库… |
| `libtv_skill` | 只读 | — | LibTV 技能（只读骨架·门）：Agent 创作平台入口（会话进展/增量轮询 + 切项目 + 批量下载）；密钥走 model_key_pool、结果必须落 trace_store |
| `libtv_workflow` | 只读 | — | LibTV 节点式工作流（只读骨架·门）：五动作 create_node/connect/set_params/run/batch_run + 五大基础节点 + 参数契约（-s 走 schema / -u 顶层）+ 两条避坑（资源组绑定 / 终点抑制 stdout）；四条红线引用… |
| `look_grade` | **需授权** | — | 外观库触手（词即指令）：一处定义多样的味道（电影感/做旧/潮湿阴冷/热血橙青/褪色胶片/黑白纪实/赛博霓虹/**原样**…**条数现算，见 `op=list`，本描述不写数**）+ 人话取味（pick：说「潮湿阴冷」「热血一点」「像老照片」即取到对应味，认不出如实标回落）+ 单帧… |
| `media_license` | **需授权** | — | 素材许可账（三方向流程台「家规第 2 条：没有许可的素材不许进成品格」的数据源）：`register` 逐件登记（**现算 sha256** + 出处 + 授权 + 时间）、`unregister` 撤销（**必须写 why**，留档在 removed）、`status`/`li… |
| `media_pipeline` | 只读 | — | AI短视频/电影/音乐流水线：镜像房间编排、产物自审、版权/安全/品牌/质量检查、主人授权后发布 |
| `media_publish` | **需授权** | — | 三方向**发布到赚钱平台**的准备与授权门：`platforms <方向>` 读平台口径（**音乐复用能力位 `music_publishing` 的 13 平台，不另造**；短视频 7 / 电影 6 为内置候选表，**全部标「未核实」**）· `prepare` 备发布包（产物… |
| `media_run` | **需授权** | — | 三方向自动化工作流**执行器**：一次调用把一条链从头走到尾，每步落真件 + 同批登记许可。链取自 `media_pipeline.KINDS`（music: lyrics→arrangement→audio→master→export · short_video: script… |
| `media_stamp` | **需授权** | — | 音视频**钢印**（作品出处）：把署名写进**容器元数据**（title/artist/album/comment/description）并用 ffprobe **回读校验**。op=status/tags/verify 为**读类直连**（status 报可打类型；tags… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `actioncam`

- **域**：`video`（视频）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：动作镜头控制系统（拍子表制）：10 种动作运镜语法（POV 主观/甩镜/急推/手持抖/推拉/环绕/打击帧停格）× 4 种机位角度（仰/俯/平/荷兰角）× 画质档（hd/fhd/cinema）；拍子表 manifest 为唯一真相，逐拍渲染 + 总装调色；零逗号表达式纪律 + 种子锁定；plan/seg/build/add/rm/qc
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap actioncam '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `audio_extract`

- **域**：`video`（视频）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：从视频里取出声音（本机 ffmpeg，**零出网**）：probe/tracks 读流与音轨（只读）；extract 真出音频件（mp3/aac/m4a/wav/flac/ogg/opus/wma 八种，可切段/调音量/响度归一）。**产出即验证**：落盘后 ffprobe 回读产物，把真读数一并返回。写面自收窄到 projects/·outputs/·.scratch/（policy 无该 kind ⇒ 门内零作用域，故自钉）。格式知识来自 online-audio-converter.com/blog/audio-formats（容器≠编解码器 / 有损与无损两族）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap audio_extract '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `audio_mix`

- **域**：`video`（视频）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：混音与母带（本机 ffmpeg，**零出网**）：`mix` 多轨合成（amix，逐路音量，显式 normalize=0）；`master` 响度归一（**两遍法 loudnorm**：先量后施加，第一遍的四个测量值随结果返回）。响度标准表 streaming -14 / podcast -16 / broadcast -23 / cinema -27 LUFS + 曲风动态预算（**与托管技能 music-production 的 -14 LUFS 口径对齐**，不另立第二套）。填的是 media_flow 的 music/04-mix、music/05-master、film/04-assets 三格。写面自收窄到 projects/·outputs/·.scratch/（policy 无该 kind ⇒ 门内零作用域，故自钉）；复用 audio_extract 的写面守卫与验证器（**不重写**）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap audio_mix '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `digital_human`

- **域**：`video`（视频）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：数字人「以图生视频」（本地 SadTalker，零账号/零验证）：**一张照片 + 一段配音 ⇒ 带头部动作与口型同步的说话视频**。ops：status/probe 只读（引擎·权重·venv 缺件如实报）· capabilities 读边界 · render 写（异步出片回 task_id；写面自收窄在 outputs/dh-talk/ 与 state/digital_human/）· task/jobs 读任务账 · socket start/stop/status 把本能力包成 **OpenAI 兼容端点**（只监听回环），主脑用 omni_plug.ai_control（远端 https）或 _local_ai_call（回环）反向调用 —— **对面跑的是我们自己的权重，借的只是 CPU/GPU**，换远端只改 base_url。实测边界（2026-10-20 全量重测，覆盖 2026-10-19 的旧读数）：① **全身可行**，取景不再是上限 —— 全身竖屏源图 `outputs/ref/character-ref.png`(736×1248) 已实测出片 **1472×2496**；② **高清来自 `--enhancer gfpgan` 的 GFPGANer(upscale=2)**（736×1248 → 1472×2496 的 2 倍还原），不是编码参数：去掉它画质 ratio 从 1.3781 掉到 0.5438；③ **必须 `--no-still`**，否则 head_move 只有 0.05（像照片贴了张会动的嘴）；④ 台湾腔女声走 edge-tts `zh-TW-HsiaoChenNeural` @+15%；⑤ 云动作库 = R2 桶 `gbt-motion`（manifest.json + 自包含零部署播放页）；⑥ 六段流水线工具：talk-photo → body-motion(逐行 S 形重心转移) → deliver(一次编码+按画面宽算字幕) → qc-video(三条口径) → motion-publish(公网回下载比 sha256)，整套规程已收进技能 `gbt-digital-human-video`（图鉴 406 条内，`omni ask` 实测 18.0 分居技能通道首位）；⑦ 本机纯 CPU 实测：全身 342 帧 ≈ 60 分钟生成 **+ 55 分钟 GFPGAN 增强**（增强阶段是 `list(gen)` 收齐才落盘，中途目录里只有半分辨率 `_full.mp4`，别当成品抓走）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap digital_human '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `edit_pipeline`

- **域**：`video`（视频）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：剪辑引擎（蒸馏剪映时间线语义）：轨道→片段→目标/源时间区间→变速/音量/转场/文本，真渲染 1080x1920 成片（ffmpeg + libass 烧字幕）或导出剪映草稿；写面自收窄到 projects/·outputs/·.scratch/（policy 无条目 ⇒ 门内零作用域，故自钉）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap edit_pipeline '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `h3_video_gen`

- **域**：`video`（视频）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：H3mini 视频生成（只读骨架·门）：四原语 T2VA/I2VA/FL2VA/Ref2VA + 三条带牙用例（密钥不走明文 / 结果必须落盘 / 提示词必须走官方六段式不接受散文式）+ 五条红线（密钥DPAPI/结果落盘/不绕官方入口/硬件门槛先验/每次留痕）；**引用官方仓库技能，不复制 SKILL.md**；type=external
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap h3_video_gen '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `libtv_skill`

- **域**：`video`（视频）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：LibTV 技能（只读骨架·门）：Agent 创作平台入口（会话进展/增量轮询 + 切项目 + 批量下载）；密钥走 model_key_pool、结果必须落 trace_store
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap libtv_skill '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `libtv_workflow`

- **域**：`video`（视频）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：LibTV 节点式工作流（只读骨架·门）：五动作 create_node/connect/set_params/run/batch_run + 五大基础节点 + 参数契约（-s 走 schema / -u 顶层）+ 两条避坑（资源组绑定 / 终点抑制 stdout）；四条红线引用已有，不重造
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap libtv_workflow '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `look_grade`

- **域**：`video`（视频）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：外观库触手（词即指令）：一处定义多样的味道（电影感/做旧/潮湿阴冷/热血橙青/褪色胶片/黑白纪实/赛博霓虹/**原样**…**条数现算，见 `op=list`，本描述不写数**）+ 人话取味（pick：说「潮湿阴冷」「热血一点」「像老照片」即取到对应味，认不出如实标回落）+ 单帧试看（preview：定了再上全片；支持 grain 颗粒 与 adjust 补光四旋钮 brightness/contrast/saturation/gamma）+ 生产审计（qc 黑帧/卡帧/亮度）；actioncam 与 filmkit 同款引用
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap look_grade '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `media_license`

- **域**：`video`（视频）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：素材许可账（三方向流程台「家规第 2 条：没有许可的素材不许进成品格」的数据源）：`register` 逐件登记（**现算 sha256** + 出处 + 授权 + 时间）、`unregister` 撤销（**必须写 why**，留档在 removed）、`status`/`list`/`check` 只读核对（账↔盘：陈旧 / sha 对不上 / 漏登）。🔴 **source 与 license 为空一律拒绝**——空着的许可记录比没有记录更坏（让人以为查过了）。只登记盘上真有的仓内素材；写面只落 `projects/_shared/licenses/`。**只登记与核对，不判定授权是否真实/充分**（那是主人的事）。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap media_license '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `media_pipeline`

- **域**：`video`（视频）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：AI短视频/电影/音乐流水线：镜像房间编排、产物自审、版权/安全/品牌/质量检查、主人授权后发布
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap media_pipeline '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `media_publish`

- **域**：`video`（视频）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：三方向**发布到赚钱平台**的准备与授权门：`platforms <方向>` 读平台口径（**音乐复用能力位 `music_publishing` 的 13 平台，不另造**；短视频 7 / 电影 6 为内置候选表，**全部标「未核实」**）· `prepare` 备发布包（产物 sha256 + 许可摘录 + 元数据模板 + 目标平台 + 闸清单，落 `projects/_shared/publish/`，**不污染 18 格抽屉**）· `submit` **永远 blocked**（发布=不可逆外部动作，需主人 `deploy_publish` 一次性授权；本机零平台凭据；`media_pipeline.publish` 明写「不接受自带令牌绕门」）。**零出网、不发任何请求、绝不返回「已发布」** —— 自动化的终点站是主人的门。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap media_publish '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `media_run`

- **域**：`video`（视频）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：三方向自动化工作流**执行器**：一次调用把一条链从头走到尾，每步落真件 + 同批登记许可。链取自 `media_pipeline.KINDS`（music: lyrics→arrangement→audio→master→export · short_video: script→storyboard→assets→edit→export · film: concept→script→shots→sound→edit→export）。🔴 **没有实现器的步如实标 `not_implemented`**（人/未实现的活不许当成跑过了）；自产输入（本机 ffmpeg 合成）⇒ 许可可如实写自有。落点只在 `projects/<方向>/<格>/`，命名合家规。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap media_run '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `media_stamp`

- **域**：`video`（视频）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **它做什么**：音视频**钢印**（作品出处）：把署名写进**容器元数据**（title/artist/album/comment/description）并用 ffprobe **回读校验**。op=status/tags/verify 为**读类直连**（status 报可打类型；tags 现读一件；verify 逐件报「带/不带钢印」**不报合计**）；stamp 为**写类**（过 filesystem_write 门；写面自收窄到 projects/ · outputs/ · .scratch/）。由来：主人 2026-10-09 问「元数据给她接入了吗」——当时只是 media_run 的内部维度、不能单独点名；现补齐三处（能力表 + api 分派 + 门作用域）。文本页钢印仍走 signature。
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap media_stamp '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
