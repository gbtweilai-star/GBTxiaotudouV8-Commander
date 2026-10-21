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

> 表格里是**摘要**（超过 140 字截断）；完整原文见 [`data/capabilities.json`](../../data/capabilities.json) 的 `desc` 字段。

---

返回 [能力总表](../03-capabilities.md)
