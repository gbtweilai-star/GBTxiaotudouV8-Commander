# gbt-capability: libtv_skill
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""LibTV 技能（libtv_skill）· R-H204 只读骨架。

**它是"门"（external），不是内调件**：为 Agent 设计的创作平台入口
（剧本 → 分镜 → 图片 → 视频 → 成片 → 发布）。

三条红线（做成机械闸）：
  ① 返回值带明文 key ⇒ 拒 ② 不经 `model_key_pool` 取 key ⇒ 拒 ③ 结果不落 trace ⇒ 拒。

本骨架只读：**不装技能包、不复制脚本、不调 API、不落盘、不出网**。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

SKILL_SOURCE = "libtv-labs/libtv-skills"      # 引用，不复制
CAP_KIND = "libtv_skill"
DOMAIN = "video"
CAP_TYPE = "external"                          # 它是门，不是内调型

# 功能面（技能包提供）
ACTIONS = (
    {"key": "session_progress", "cn": "查询会话进展", "note": "支持**增量轮询**（拿增量，不拿全量）"},
    {"key": "switch_project", "cn": "切换当前绑定的项目", "note": "多项目并行的上下文切换"},
    {"key": "download_assets", "cn": "批量下载图片/视频", "note": "成片与素材回收"},
)

EXTERNAL_KEY_ENVS = ("LIBTV_ACCESS_KEY", "LIBTV_API_KEY", "LIBTV_TOKEN")
KEY_ENV_NAMES = ("LIBTV_ACCESS_KEY",)          # 只用于"检测有没有第二套路径"，不用于取值

_PLAINTEXT_KEY_RX = re.compile(r"\b(?:sk|ak|lt)[-_][A-Za-z0-9_\-]{16,}\b")

RED_LINES = (
    "返回值带明文 key ⇒ 拒（只回 key_id / masked / leased）",
    "不经密钥池取 key ⇒ 拒（第二套密钥路径 = 绕过 DPAPI + 绕过池 + 明文）",
    "生成结果不落 trace_store ⇒ 拒（无痕即未发生）",
)

# ── R-H205 · 契约蒸馏：官方《LibTV CLI 使用指南》的要领（**引用，不复制原文**）──
# 来源：飞书 wiki `RjelwT2UoidnTMka2nCc2chGnud`（《LibTV CLI 使用指南》· 更新 2026-05-27）
# 取法：抓 SSR 页面 → 还原文档 block_map → **蒸馏成结构化契约**（原文不进代码）
CLI_COMMANDS = (
    {"cmd": "libtv login", "cn": "登录：会在浏览器里打开登录页，登录态再回传给 Agent"},
    {"cmd": "libtv logout", "cn": "取消登录 + 解除绑定与授权（本机凭据被清除、目录绑定被解除）"},
    {"cmd": "libtv project list", "cn": "查项目列表（-w/--workspace 指定空间；也会读当前目录绑定的项目）"},
    {"cmd": "libtv project create", "cn": "建项目（-w/--workspace 指定落点空间）"},
    {"cmd": "libtv project use / unuse", "cn": "绑定 / 解绑「当前工作目录 ↔ 项目」"},
    {"cmd": "libtv node --run", "cn": "跑节点（官方明确：**避免调用方无意义轮循**，省的是调用方 token）"},
    {"cmd": "libtv node / state query", "cn": "查节点与任务状态（长任务先查状态，**别重复提交任务**）"},
)

# 节点引用语法：上游产物要在 prompt 里被显式引用，模型才知道「哪张图是什么」
NODE_REF = {
    "key_form": "{{Node <Node Key>}}",
    "name_form": "{{Node \"节点名\"}}",
    "rule": "引用要写在「用途」的位置上（谁当角色、谁当场景、谁当道具），"
            "不是把节点名罗列一遍；混合参考要说明每张图的用途",
    "why": "不说清用途 ⇒ 模型会混淆身份 / 融合人脸 / 改掉空间方向",
}

# 失败诊断分类学（六类 · 官方给的常见原因归并）
FAILURE_CLASSES = (
    ("prompt_unclear", "prompt 没写清生成目标 / 参考图用途 / 视频节点要求",
     ("没写清楚", "不明白", "用途", "requirement")),
    ("asset_missing", "素材缺失：节点空的、没有结果 URL、参考图没上传",
     ("空节点", "没有结果", "缺少素材", "未上传")),
    ("ref_order", "引用顺序错：连线变了、参考顺序漂移、引用失效",
     ("引用", "顺序", "连线", "错位")),
    ("model_limit", "模型能力不足：复杂多图 / 多角色 / 多步骤理解不了",
     ("模型", "多角色", "复杂", "能力")),
    ("safety_review", "安全审核拦截（Seedance 类自动合规检测）",
     ("审核", "合规", "拦截", "安全")),
    ("transient", "网络波动 / 临时服务不稳定 / 模型异常（可重试类）",
     ("网络", "超时", "临时", "异常", "波动")),
)

# 画布分区模板（模板项目用 · 让新人打开就看得懂流程）
CANVAS_ZONES = (
    ("input", "输入区", "用户需求 / 参考素材 / 品牌与风格约束"),
    ("plan", "规划区", "故事大纲 / 剧本 / 分镜 / 角色与场景设定"),
    ("assets", "视觉资产区", "角色 / 场景 / 道具参考（跨 Unit 一致性的来源）"),
    ("unit_image", "Unit 图片区", "每个 Unit 的图片参考"),
    ("unit_video", "Unit 视频区", "每个 Unit 的视频节点（**继承分镜语言，不许只写剧情摘要**）"),
    ("qc", "质检与重跑区", "失败节点 / 空节点 / 引用错误 / 一致性问题的收容处"),
    ("final", "最终成片区", "成片与交付物"),
)

# 交付契约（官方示例反复要求的「七件」）
DELIVERY_ITEMS = (
    "项目链接", "最终视频链接", "Unit 列表", "主要视觉资产清单",
    "失败节点与修复记录", "剧本/脚本摘要", "下一步可继续编辑的建议",
)

# 口径三条（官方文档明说，不是我们猜的）
POLICIES = {
    "credits": "通过 CLI / Skill 发起的调用，消耗的是**所登录账户的积分**，"
               "与在画布中生成对应节点相同；**失败是否返还以平台当前规则为准** —— "
               "不许把「失败一定不消耗」当承诺（官方原话口径）",
    "workspace": "CLI 的登录态与可访问项目**取决于登录 CLI 时浏览器里的账号与空间**；"
                 "在浏览器里切账号 / 切团队空间 / 切个人空间，都会影响 CLI 后续状态 ⇒ "
                 "要切就**先在浏览器切、再重新登录**，并把期望的个人 ID / 团队 ID 交给 Agent 核对",
    "human_login": "登录这一步要人在浏览器里点 ⇒ **Agent 不代签**（人类视角执行律）",
}

# R-H205 新增四条红线（R-H204 那三条一并保留）
RED_LINES_CLI = (
    "不许重建整张画布 ⇒ 拒（先定位失败节点，给最小修复方案）",
    "不许无脑重复提交 ⇒ 拒（**先查状态再重跑**，把调用方 token 当成本）",
    "答不出的失败原因不许瞎猜 ⇒ 拒（归类不出就 unknown，如实上报）",
    "交付不许只回一个视频链接 ⇒ 拒（缺项目链接 / Unit 列表 / 失败节点即不完整）",
)

# ── R-H207 · 交互面（**人的位置**）──
INTERACTION = {
    "canvas": "无限画布",
    "authoring": "手动拖拽节点",
    "who": "人",
    "boundary": "画布布局与观感是**人摆的**；Agent 负责建节点 / 连线 / 跑任务 / 查状态，"
                "**不许假装能替人做排版审美**（好看只能人判）。",
}

# 要求面四条（每条**带判据** —— 判据不写清，要求就只是口号）
REQUIREMENTS = (
    {"key": "upload_ref", "cn": "上传参考图 / 视频",
     "criteria": "素材必须带用途（谁当角色 / 谁当场景 / 谁当道具）；"
                 "只上传、不写用途 ⇒ 拒"},
    {"key": "poll_progress", "cn": "轮询生成进展（**增量**）",
     "criteria": "轮询必须**带游标**（增量，不拿全量）；不带游标 ⇒ 拒；"
                 "「这一轮没有变化」**不算失败**，只是还没出新"},
    {"key": "batch_download", "cn": "批量下载结果到本地",
     "criteria": "**每一项都要有本地落点**；只留 OSS 链接 ⇒ 拒；空清单 ⇒ 拒"},
    {"key": "switch_project", "cn": "切换当前绑定的项目",
     "criteria": "切换后必须**显式绑定**（bound_project）；没绑定就操作 ⇒ 拒，"
                 "不许靠「我记得是那个项目」"},
)

# R-H207 新增第三条带牙红线：**必须走 skill 脚本，不许自己拼 API 请求**
RED_LINES_SKILL = (
    "必须走 libtv-skill 脚本 ⇒ 自己拼 API 请求一律拒（绕开技能包 = 绕开它的校验与留痕）",
)

# ── R-H221 · 官方**三条带牙用例**（3/3 与我们已落的一致）──
TEETH_CASES = (
    {"n": 1, "official": "返回值不许带明文 **LIBTV_ACCESS_KEY**",
     "our_gates": ("plaintext_key_in_return", "must_mask_key"),
     "match": True,
     "increment": "官方把『key』**具体化**成 `LIBTV_ACCESS_KEY`（比我们写的泛称更精确）"},
    {"n": 2, "official": "生成结果必须下载到本地，**不许只留 OSS 链接**",
     "our_gates": ("must_localize_oss", "link_only_result", "must_trace"),
     "match": True,
     "increment": "措辞更全：点明了『OSS 链接』这个具体形态"},
    {"n": 3, "official": "**不绕过官方入口**",
     "our_gates": ("handmade_api_request", "not_via_skill_script"),
     "match": True,
     "increment": "**层次差**：官方写的是**原理**（不绕过官方入口），"
                  "我们落的是**形态**（自己拼请求就拒）⇒ **原理↔形态配对**，"
                  "不是两条不同的红线"},
)

# ── R-H212 · 接入安全与合规红线 9 条（主人逐条给 · 三簇）──
# ⚠️ 主人**未口头确认"就这些"** ⇒ 清单标 closed=False，留出追加位。
ACCESS_REDLINES = (
    {"n": 1, "group": "key", "cn": "密钥只存 DPAPI",
     "gate": "check_key_storage → key_must_be_dpapi"},
    {"n": 2, "group": "key", "cn": "LIBTV_ACCESS_KEY 必须走密钥池，不许明文落盘",
     "gate": "check_key_storage + check_key_injection"},
    {"n": 3, "group": "identity", "cn": "不绕验证",
     "gate": "check_no_bypass → bypass_verification"},
    {"n": 4, "group": "identity", "cn": "走官方 OpenAPI，不绕过平台验证",
     "gate": "must_use_skill_script（handmade_api_request / not_via_skill_script）"},
    {"n": 5, "group": "identity", "cn": "一 AI 一号",
     "gate": "check_identity_keys → missing_owner_ai_id"},
    {"n": 6, "group": "key", "cn": "多个 AI 身份使用时，各自独立密钥",
     "gate": "check_identity_keys → shared_key_across_identities"},
    {"n": 7, "group": "trace", "cn": "每次调用留痕",
     "gate": "must_trace_call → call_not_traced"},
    {"n": 8, "group": "trace",
     "cn": '生成记录写入 trace_store，带 source_kind="libtv"',
     "gate": "must_trace_call(source_kind) → bad_source_kind"},
    {"n": 9, "group": "trace", "cn": "输出必须过审",
     "gate": "must_pass_review → review_required"},
)
ACCESS_REDLINES_CLOSED = False      # 主人未确认齐全 ⇒ 不许当定稿
TRACE_SOURCE_KIND = "libtv"         # 契约里钉死的取值
ACCESS_REDLINE_GROUPS = ("key", "identity", "trace")   # 9 条其实是三簇，不是九件散事
# R-H219：追加要求也出自官方（主人给的 6→9 与 ⑥⑦⑧⑨ 逐条一致）
EXTRA_REQUIREMENTS_SOURCE = "官方（《LibTV Skill 使用指南》『追加要求』一节）"

# ── R-H218 · 标签修正：官方正式版是**五条红线** ──
# 依据：主人给的《LibTV Skill 使用指南》里「五条红线（写死）」，
# 且与本表 **前 5 条连顺序都一致** ⇒ 前 5 = 官方五条；后 4 = 主人另给的追加要求。
OFFICIAL_REDLINE_COUNT = 5
ACCESS_REDLINES_NOTE = (
    "**前 5 条 = 官方《五条红线》**（有第二出处）；"
    "**后 4 条 = 官方追加要求**（出处已落实，R-H219 修正）。"
    "⇒ 两者**都出自官方**，但**分属两节**："
    "『五条红线（写死）』与『追加要求』；"
    "**报数时要分开说**（不许笼统称『官方九条红线』）。"
)

# ── R-H208 · 平台面（官方给的：它到底是什么）──
PLATFORM = {
    "name": "LibTV（LiblibAI 推出的 AI 视频创作平台）",
    "dual_entry": {
        "human": "无限画布：搭剧本 / 分镜 / 镜头 / 剪辑流程",
        "agent": "Skill 接口：理解任务 → 调用模型 → 编排工作流 → 自动完成创作",
    },
    # R-H218：能力按**官方三分类**重构（此前是平铺 10 项）
    "capability_classes": {
        "generate": ("文生图", "文生视频", "图生视频", "视频续写"),
        "edit": ("局部修改", "元素替换（把纸船换成爱心）", "镜头调整", "风格迁移"),
        "complex": ("一句话生成完整短剧（剧本→分镜→成片）",
                    "复刻视频风格做 TVC", "用音乐生成 MV", "产品展示片制作"),
    },
    "agent_entry": "通过 Skill 调用 OpenAPI，自主编排工作流",
    "coverage": ("文生图/视频", "图生图/视频", "视频续写", "风格迁移", "局部编辑",
                 "短剧 / MV / TVC", "角色三视图", "分镜设计", "首尾帧视频",
                 "音频生视频"),
    "coverage_note": "coverage 是 R-H208 的**平铺版**（保留兼容）；"
                     "capability_classes 是 R-H218 的**官方三分类版**（更好用）",
    "models": ("Seedance 2.0", "Kling 3.0 / O3", "Wan 2.6", "NanoBanana",
               "Midjourney", "Seedream 5.0"),
    "why_we_care": "**双入口**：人用画布、Agent 用 Skill —— 同一条创作链上人和 Agent "
                   "各有位置（这也是 INTERACTION 里『画布是人摆的』的由来）",
}

# 安装面（官方给的两种方式 + 依赖口径）
INSTALL = {
    "method_npx": "npx skills add libtv-labs/libtv-skills --skill libtv-skill",
    "method_clone": "git clone https://github.com/libtv-labs/libtv-skills.git "
                    "→ 解压到 ~/.openclaw/skills/",
    "landing": "~/.openclaw/skills/（OpenClaw 技能规范）",
    "deps": "**无需额外依赖：仅用 Python 标准库**",
    "requires_network": True,           # npx / git clone 都要出网
    "needs_owner_authorization": True,  # 装技能 = 往家目录写东西 ⇒ 要主人点头
    "status": "未安装（R-H208 取证：三个技能目录里都没有 libtv）",
}

# 🔴 口径撞车点与解法（本刀最重要的收口）
KEY_INJECTION = {
    "conflict": "官方配置口径是**环境变量** `LIBTV_ACCESS_KEY`（从网站项目设置取）；"
                "我们的红线是**密钥只走 DPAPI / 密钥池、不许明文落盘**。",
    "resolution": "**取**与**放**分开 —— 取 = 只从 model_key_pool / DPAPI 保险箱取；"
                  "放 = **只在该次子进程的环境里注入**（技能包只认 env），进程结束即弃。",
    "forbidden": ("把 LIBTV_ACCESS_KEY 写进 .env / 配置文件 / 脚本（= 明文落盘）",
                  "从 os.environ 读密钥当『来源』（= 第二套密钥路径）",
                  "把密钥贴进对话 / 日志 / trace（= 明文外泄）"),
    "why": "技能包的接口是既定的（它只认 env）；**我们能决定的是密钥从哪来** —— "
           "来源归池、注入归进程、用完即弃。两条纪律都不破："
           "既没绕开官方接入方式，也没把密钥明文落盘。",
}

# ── R-H209 · 技能包的 **5 个脚本**（官方：这是 Agent-IM 会话技能）──
# ── R-H220 · 官方**五原语**（干的是"能力维度"，与脚本是"文件清单"不同层）──
LIBTV_PRIMITIVES = (
    {"n": 1, "primitive": "SESSION", "script": "create_session.py",
     "cn": "创建会话 / 发送指令"},
    {"n": 2, "primitive": "UPLOAD", "script": "upload_file.py",
     "cn": "上传素材到 OSS"},
    {"n": 3, "primitive": "QUERY", "script": "query_session.py",
     "cn": "查询进展（增量轮询）"},
    {"n": 4, "primitive": "DOWNLOAD", "script": "download_results.py",
     "cn": "批量下载结果到本地"},
    {"n": 5, "primitive": "PROJECT", "script": "change_project.py",
     "cn": "切换当前绑定的项目"},
)

# 🔴 R-H220 · **两套顺序不同**（如实并排，不擅自对齐）
ORDER_NOTE = (
    "官方五原语顺序：SESSION → UPLOAD → QUERY → DOWNLOAD → PROJECT；"
    "技能包脚本顺序：create_session → query_session → change_project → "
    "upload_file → download_results。**两套顺序不同** ⇒ "
    "原语是『能力维度』、脚本是『文件清单』，**不许当同一个排序**，也不擅自重排。"
)

# 采集纪律：**只抄不猜**；名字有、作用没说的 ⇒ 标 `evidenced=False`（推定），不许当已证。
SKILL_SCRIPTS = (
    {"n": 1, "script": "create_session.py", "cn": "创建会话 / 发送生成指令",
     "note": "会话**入口**：一条创作任务从这里开始（如「生一个动漫视频」）",
     "usage": 'python3 scripts/create_session.py "生一个动漫视频"',
     "evidenced": True},
    {"n": 2, "script": "query_session.py", "cn": "查询会话进展（**增量轮询**）",
     "note": "长任务不阻塞；必须带游标（增量），不拿全量",
     "usage": "python3 scripts/query_session.py <SESSION_ID> --after-seq 5",
     # R-H220：官方五原语 QUERY 点名 query_session.py ⇒ 这是它的**第二出处**
     # （第一出处是 R-H210 的实测调用形态 --after-seq）
     "evidenced": True},
    {"n": 3, "script": "change_project.py", "cn": "切换当前绑定的项目",
     "note": "多项目并行的上下文切换；切完必须显式绑定",
     "usage": "",
     "evidenced": False},
    {"n": 4, "script": "upload_file.py", "cn": "上传图片 / 视频到 OSS",
     "note": "**素材进 OSS** ⇒ 这正是「不许只留 OSS 链接」这条红线的由来："
             "结果也在 OSS，地址会失效，所以必须下载到本地",
     # R-H218：第二出处补上的**前置条件**
     "precondition": "**编辑已有视频 / 图片前必须先上传**（否则没有可引用的 OSS 素材）",
     "usage": "",
     "evidenced": True},
    {"n": 5, "script": "download_results.py", "cn": "批量下载结果到本地",
     "note": "成片与素材回收；每一项都要有本地落点",
     "usage": "",
     "evidenced": False},
)

# ── R-H210 · 会话契约（实测口径）──
SKILL_SCRIPTS_DIR = "scripts/"
SESSION_CONTRACT = {
    "invocation": "python3 scripts/<脚本> …（脚本在技能包的 scripts/ 目录下）",
    "returns": ("projectUuid", "sessionId"),
    "why": "**这两个是后续一切操作的钥匙**：查进展、下载结果都要带它们；"
           "丢了就只能重建会话（= 白花钱）",
    "poll_cursor": "--after-seq <N>（**增量轮询的游标**：只拿第 N 条之后的新增，不拿全量）",
    "creation_style": "**所有创作通过发送自然语言消息完成**，Agent 自己编排工作流 —— "
                      "不许绕过这条去自己拼参数/拼请求",
}

_SESSION_ID_KEYS = ("session_id", "sessionId")
_PROJECT_ID_KEYS = ("project_uuid", "projectUuid")

# 盘上取证快照（R-H204 实测 · 带出处）
FORENSICS = {
    "as_of": "2026-09-20T12:5x",
    "libtv_hits_on_disk": 0,
    "skill_dirs": {"~/.openclaw/skills": True, "~/.openclaw-autoclaw/skills": True,
                   "~/.agents/skills": True},
    "key_configured": False,
    "source": "tools/libtv_skill.py 取证（.scratch/_rh204_libtv_forensics.py）",
}


def assert_no_plaintext(payload: Any, where: str = "") -> dict:
    """红线①：**返回值里出现明文 key ⇒ 拒**。"""
    import json
    blob = json.dumps(payload, ensure_ascii=False, default=str)
    if _PLAINTEXT_KEY_RX.search(blob):
        return {"ok": False, "denied": True, "rule": "plaintext_key_in_return",
                "where": str(where or ""),
                "why": "密钥只从 model_key_pool 借；返回值不许带明文（只回 key_id/掩码/leased）"}
    return {"ok": True, "readonly": True}


def lease_key(owner_ai_id: str, tentacle_id: str = "libtv") -> dict:
    """红线②：**只从密钥池借** —— 不许读环境变量、不许明文落盘。"""
    if not str(owner_ai_id or "").strip():
        return {"ok": False, "denied": True, "rule": "missing_owner_ai_id",
                "why": "LibTV 的密钥也要按一 AI 一号借（触手不是身份）"}
    try:
        from . import model_key_pool as mkp        # 唯一合法来源
        got = mkp.ModelKeyPool().lease(tentacle_id, owner_ai_id)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "denied": True, "rule": "key_pool_unavailable",
                "why": "密钥池不可用：%s" % str(e)[:80]}
    if not got.get("ok"):
        return {"ok": False, "denied": True, "rule": got.get("rule") or "no_key_for_owner",
                "why": got.get("why") or "该 AI 身份尚未在密钥池配置 LibTV 密钥（拒执行并上报）"}
    out = {"ok": True, "readonly": True, "lease_id": got.get("lease_id"),
           "key_id": got.get("owner_ai_id"), "leased": True,
           "key_masked": "****（池内持有，不出池）"}
    guard = assert_no_plaintext(out, where="lease_key.return")
    return out if guard.get("ok") else guard


def must_trace(result: Optional[Dict] = None, trace_ref: str = "") -> dict:
    """红线③：**生成结果必须落 trace**（无痕即未发生）。"""
    ref = str(trace_ref or (result or {}).get("trace_ref") or "").strip()
    if not ref:
        return {"ok": False, "denied": True, "rule": "no_trace",
                "why": "生成结果没有 trace_ref：无痕即未发生，不许当产出"}
    return {"ok": True, "readonly": True, "trace_ref": ref}


def classify_failure(text: str) -> dict:
    """失败归类（六类）。**答不出就如实说答不出**——不许瞎猜（红线⑥）。

    诚实口径：这是**关键词归类**，不是官方诊断器；它的价值是"逼出一次诊断"，
    不是"替代人判断"。
    """
    blob = str(text or "")
    if not blob.strip():
        return {"ok": False, "denied": True, "rule": "empty_failure_text",
                "why": "没有失败信息可归 ⇒ 先去读报错与失败节点，别凭空猜"}
    hits = []
    for key, cn, kws in FAILURE_CLASSES:
        if any(k in blob for k in kws):
            hits.append({"key": key, "cn": cn})
    if not hits:
        return {"ok": False, "denied": True, "rule": "unknown_failure_class",
                "classes": [k for k, _c, _w in FAILURE_CLASSES],
                "why": "归不进现有六类 ⇒ **如实报 unknown**，不许硬塞一个原因"}
    return {"ok": True, "readonly": True, "classes": hits,
            "note": "关键词归类：只用于逼出一次诊断，不替代人判断"}


def must_diagnose_before_rerun(plan: Optional[Dict] = None) -> dict:
    """红线④⑤：**不许重建整张画布 / 不许无脑重跑** —— 重跑前必须有诊断 + 最小范围。

    调用方得给出：`diagnosed`（诊断结论）与 `scope`（要动哪几个节点）。
    """
    p = dict(plan or {})
    if p.get("rebuild_canvas") or p.get("redo_all"):
        return {"ok": False, "denied": True, "rule": "canvas_rebuild",
                "why": "失败先定位**失败节点**，不许重建整张画布（一条报错不该赔掉整张图）"}
    if not str(p.get("diagnosed") or "").strip():
        return {"ok": False, "denied": True, "rule": "rerun_without_diagnosis",
                "why": "**先诊断再重跑**：不查状态就重提任务 = 烧调用方 token，且问题照旧"}
    scope = p.get("scope") or []
    if isinstance(scope, str):
        scope = [s for s in scope.replace(",", " ").split() if s]
    if not scope:
        return {"ok": False, "denied": True, "rule": "scope_unspecified",
                "why": "要给**最小修复范围**（哪几个节点补内容 / 重连 / 重跑），"
                       "不许「全部重跑」这种含糊范围"}
    return {"ok": True, "readonly": True, "diagnosed": str(p["diagnosed"]),
            "scope": list(scope),
            "note": "先定位失败节点 → 最小修复 → 等确认后执行"}


def check_node_ref(prompt: str) -> dict:
    """节点引用自检：`{{Node ...}}` 语法 + 「说了用途没有」。"""
    s = str(prompt or "")
    if not s.strip():
        return {"ok": False, "denied": True, "rule": "empty_prompt"}
    # 节点名**可以是中文**（实测：把判据写窄成 [A-Za-z0-9_-] 会把 {{Node 角色A}} 误判成坏语法）
    found = re.findall(r"\{\{\s*[Nn]ode\s+(?:\"[^\"]+\"|[^\"{}]+?)\s*\}\}", s)
    dangling = re.findall(r"\{\{.*?\}\}", s)
    # 坏形状 = 用了 {{...}} 但不是 `Node <有名字>`（如 `{{节点A}}` / `{{Node}}`）
    bad = [d for d in dangling
           if not re.match(r"^\{\{\s*[Nn]ode\s+\S", d)]
    if bad:
        return {"ok": False, "denied": True, "rule": "bad_node_ref_syntax",
                "bad": bad[:5],
                "expected": [NODE_REF["key_form"], NODE_REF["name_form"]],
                "why": "引用语法要写成 {{Node <Key>}} 或 {{Node \"节点名\"}}"}
    out = {"ok": True, "readonly": True, "refs": found}
    if found and not any(k in s for k in ("用途", "当角色", "当场景", "参考", "用于")):
        out["hint"] = ("有引用但**没说每张图的用途** ⇒ 容易混淆角色/融合人脸/改空间方向；"
                       "把「谁当角色、谁当场景」写进 prompt")
    return out


def delivery_check(payload: Optional[Dict] = None) -> dict:
    """红线⑦：交付不许只回一个视频链接。缺件**如实列出**，不算完整交付。"""
    got = dict(payload or {})
    missing = [k for k in DELIVERY_ITEMS if not got.get(k)]
    if missing:
        return {"ok": False, "denied": True, "rule": "incomplete_delivery",
                "missing": missing, "required": list(DELIVERY_ITEMS),
                "why": "只返回一个视频链接 ⇒ 后续很难修改、追踪、复用"}
    return {"ok": True, "readonly": True, "items": list(DELIVERY_ITEMS)}


def must_use_skill_script(call: Optional[Dict] = None) -> dict:
    """红线⑧（R-H207）：**必须走 libtv-skill 脚本，不许自己拼 API 请求**。

    为什么这条是红线：自己拼请求 = 绕开技能包的参数校验与留痕，
    出了问题**既查不到、也复现不了**——它把"可追踪"变成"猜"。
    """
    c = dict(call or {})
    via = str(c.get("via") or c.get("script") or "").strip()
    raw = " ".join(str(c.get(k) or "") for k in
                   ("url", "endpoint", "raw_url", "http", "path"))
    if re.search(r"https?://|/open-apis/|/api/", raw, re.I):
        return {"ok": False, "denied": True, "rule": "handmade_api_request",
                "seen": raw.strip()[:120],
                "why": "不许自己拼 API 请求：绕过 libtv-skill 脚本 = "
                       "绕过它的校验与留痕（出问题查不到、复现不了）"}
    if not via.lower().startswith("libtv-skill"):
        return {"ok": False, "denied": True, "rule": "not_via_skill_script",
                "via": via or "（未声明）",
                "why": "必须显式声明走 libtv-skill 脚本（via=\"libtv-skill ...\"）"}
    return {"ok": True, "readonly": True, "via": via}


def must_localize_oss(result: Optional[Dict] = None,
                      local_path: str = "") -> dict:
    """红线⑨（R-H207）：结果**必须下载到本地**，只留 OSS 链接 ⇒ 拒。"""
    r = dict(result or {})
    p = str(local_path or r.get("local_path") or "").strip()
    if not p:
        return {"ok": False, "denied": True, "rule": "oss_link_only",
                "oss_url": str(r.get("oss_url") or r.get("url") or "")[:120],
                "why": "只留 OSS 链接不算产出（链接会失效）⇒ 必须落本地并给出 local_path"}
    return {"ok": True, "readonly": True, "local_path": p}


_SECRETISH_KEYS = ("key", "api_key", "apikey", "token", "secret", "access_key")
# ⚠️ 收窄（本次实测踩过）：`key_id` / `key_masked` / `key_ref` 是**标识与脱敏字段**，
# 不是密钥 —— 把它们当明文抓，就是"判据扩大化"（会天天误报，最后被绕过）。
_SECRETISH_SKIP = ("key_id", "key_ref", "key_masked", "key_state", "leased",
                   "owner_ai_id", "via", "trace_ref", "local_path", "cursor",
                   "bound_project", "key_envs")


def must_mask_key(payload: Any, where: str = "") -> dict:
    """红线①的加强面：**返回值不许带明文密钥** —— 连"命名字段里塞明文"也抓。

    两道一起上：形状扫描（`sk-/ak-/lt-`）+ **字段名扫描**（key/token/secret 的值不是掩码）。
    """
    shape = assert_no_plaintext(payload, where=where)
    if not shape.get("ok"):
        return shape
    if isinstance(payload, dict):
        for k, v in payload.items():
            kn = str(k).lower()
            if not any(s in kn for s in _SECRETISH_KEYS):
                continue
            if kn in _SECRETISH_SKIP or kn.endswith(("_id", "_ref", "_masked", "_state")):
                continue
            s = v.strip() if isinstance(v, str) else ""
            if not s or "****" in s or "*" in s[:1]:
                continue
            # 只有"**像密钥**"才算：够长 + 纯 token 形状（判据卡在真问题上）
            if len(s) >= 16 and re.fullmatch(r"[A-Za-z0-9_\-]{16,}", s):
                return {"ok": False, "denied": True,
                        "rule": "plaintext_key_in_return", "field": str(k),
                        "why": "命名字段（%s）里塞了疑似明文密钥 ⇒ 只许回掩码 / key_id" % k}
    return {"ok": True, "readonly": True}


def must_poll_incrementally(cursor: str = "", full_refetch: bool = False) -> dict:
    """要求面②的判据：轮询必须**带游标**（增量）；「没有变化」不算失败。"""
    if full_refetch:
        return {"ok": False, "denied": True, "rule": "poller_without_cursor",
                "why": "全量重拉 = 烧调用方 token；要拿增量（带 since / cursor）"}
    c = str(cursor or "").strip()
    if not c:
        return {"ok": False, "denied": True, "rule": "poller_without_cursor",
                "why": "轮询必须带游标（since / cursor），否则无法判断『增量』"}
    return {"ok": True, "readonly": True, "cursor": c,
            "note": "这一轮没有变化 != 失败：长任务十几分钟到更久是常态"}


def must_project_bound(bound_project: str = "") -> dict:
    """要求面④的判据：操作前必须**显式绑定**项目（不许靠"我记得"）。"""
    b = str(bound_project or "").strip()
    if not b:
        return {"ok": False, "denied": True, "rule": "no_project_bound",
                "why": "没绑定项目就操作 ⇒ 可能在**错的项目**里建节点/花钱；"
                       "先 project use 显式绑定（unuse 解绑）"}
    return {"ok": True, "readonly": True, "bound_project": b}


def check_key_injection(plan: Optional[Dict] = None) -> dict:
    """R-H208 · 密钥口径闸：**来源归池，注入归进程，用完即弃**。

    官方只认 env，我们不许明文落盘 —— 这两条不矛盾：**分的是"从哪来"和"往哪放"**。
    """
    p = dict(plan or {})
    src = str(p.get("source") or "").strip().lower()
    if src in ("env", "environment", "environ", "dotenv", ".env", "file",
               "config", "配置文件"):
        return {"ok": False, "denied": True, "rule": "key_source_not_pool",
                "source": src,
                "why": "密钥来源只许是 model_key_pool / DPAPI 保险箱；"
                       "从 env / 配置文件取 = 第二套密钥路径"}
    if src != "model_key_pool":
        return {"ok": False, "denied": True, "rule": "key_source_unspecified",
                "source": src or "（未声明）",
                "why": "要说清密钥**从哪来**：只认 source=\"model_key_pool\""}
    if p.get("persist") or p.get("write_file") or p.get("save_to"):
        return {"ok": False, "denied": True, "rule": "key_persisted_to_file",
                "why": "不许把密钥写进 .env / 配置 / 脚本（= 明文落盘）——"
                       "只在**该次子进程**的环境里注入，进程结束即弃"}
    if not p.get("inject_to_child_env"):
        return {"ok": False, "denied": True, "rule": "injection_channel_unspecified",
                "why": "技能包只认 env ⇒ 要显式声明 inject_to_child_env=True"
                       "（**注入 ≠ 落盘**：注入是运行时内存，落盘才是明文）"}
    return {"ok": True, "readonly": True, "source": "model_key_pool",
            "injection": "child_process_env_only",
            "note": "用完即弃：子进程结束，注入的环境随进程消失"}


def check_install(method: str = "") -> dict:
    """R-H208 · 安装闸：只认官方两种方式，且**要出网 + 要主人点头**。"""
    m = str(method or "").strip().lower()
    known = {"npx": "method_npx", "skills-add": "method_npx",
             "clone": "method_clone", "git": "method_clone"}
    if not m:
        return {"ok": False, "denied": True, "rule": "missing_install_method",
                "known": ["npx", "clone"],
                "why": "要说清用哪种官方方式装，不许「随便搞一个」"}
    if m not in known:
        return {"ok": False, "denied": True, "rule": "unknown_install_method",
                "method": m, "known": ["npx", "clone"],
                "why": "官方只给了两种（npx skills add / git clone）——别的路子不认"}
    return {"ok": True, "readonly": True, "method": known[m],
            "landing": INSTALL["landing"], "requires_network": True,
            "needs_owner_authorization": True,
            "note": "装技能 = 往家目录写东西 ⇒ **本骨架不装**，要主人点头"}


def check_script(script: str = "") -> dict:
    """R-H209 · 脚本白名单闸：**只认技能包里的这 5 个**，不许自己造脚本。"""
    s = str(script or "").strip()
    if not s:
        return {"ok": False, "denied": True, "rule": "missing_script",
                "known": [x["script"] for x in SKILL_SCRIPTS],
                "why": "要说清调哪个脚本；技能包只有这 5 个"}
    s = s.replace("\\", "/").split("/")[-1].lower()
    for x in SKILL_SCRIPTS:
        if x["script"].lower() == s:
            out = {"ok": True, "readonly": True, "script": x["script"],
                   "cn": x["cn"], "evidenced": x["evidenced"]}
            if not x["evidenced"]:
                out["hint"] = "该脚本的**作用**是推定（无主人原话）⇒ 以实际技能包为准"
            return out
    return {"ok": False, "denied": True, "rule": "unknown_script",
            "script": s, "known": [x["script"] for x in SKILL_SCRIPTS],
            "why": "自己造脚本名 = 自己拼链路：技能包之外一律不认"}


def check_poll_args(session_id: str = "", after_seq: Any = None) -> dict:
    """R-H210 · 轮询参数闸：**必须带 session_id + `--after-seq <N>`**。

    依据实测调用形态：`python3 scripts/query_session.py <SESSION_ID> --after-seq 5`
    ⇒ 「增量」不是形容词，是**一个必填的游标参数**。
    """
    sid = str(session_id or "").strip()
    if not sid:
        return {"ok": False, "denied": True, "rule": "missing_session_id",
                "why": "轮询必须带 session_id（create_session 返回的那个）"}
    if after_seq is None or str(after_seq).strip() == "":
        return {"ok": False, "denied": True, "rule": "poller_without_cursor",
                "why": "轮询必须带 `--after-seq <N>`（增量游标）——不带就是全量重拉，"
                       "烧的是调用方 token"}
    s = str(after_seq).strip()
    if not re.fullmatch(r"\d+", s):
        return {"ok": False, "denied": True, "rule": "bad_after_seq",
                "after_seq": s,
                "why": "`--after-seq` 必须是非负整数（第 N 条之后的新增）"}
    return {"ok": True, "readonly": True, "session_id": sid,
            "after_seq": int(s), "cursor": "--after-seq %s" % s,
            "note": "这一轮没有新增 != 失败：长任务是常态"}


def check_session_refs(project_uuid: str = "", session_id: str = "") -> dict:
    """R-H210 · 会话钥匙闸：查进展 / 下载前**必须带 projectUuid + sessionId**。

    依据原话：「返回的 projectUuid 和 sessionId 用于后续查询和下载」。
    """
    p = str(project_uuid or "").strip()
    s = str(session_id or "").strip()
    missing = []
    if not p:
        missing.append("projectUuid")
    if not s:
        missing.append("sessionId")
    if missing:
        return {"ok": False, "denied": True, "rule": "missing_session_refs",
                "missing": missing,
                "why": "这两个是后续一切操作的钥匙；丢了只能**重建会话**（= 白花钱）"}
    return {"ok": True, "readonly": True, "projectUuid": p, "sessionId": s}


def check_key_storage(key_ref: str = "", from_pool: bool = False) -> dict:
    """R-H212 红线①②：**密钥只存 DPAPI** + **LIBTV_ACCESS_KEY 只走密钥池**。"""
    ref = str(key_ref or "").strip().replace("\\", "/")
    if ref and not ref.endswith(".dpapi"):
        return {"ok": False, "denied": True, "rule": "key_must_be_dpapi",
                "key_ref": ref[:120],
                "why": "密钥只存 DPAPI（形如 …/secrets/<name>.dpapi）；"
                       "明文 / .env / .json 里的密钥一律不认"}
    if not from_pool:
        return {"ok": False, "denied": True, "rule": "key_source_not_pool",
                "why": "`LIBTV_ACCESS_KEY` 必须走密钥池（`model_key_pool.lease`）——"
                       "不许从环境变量 / 配置文件当『来源』"}
    return {"ok": True, "readonly": True, "key_ref": ref, "source": "model_key_pool"}


def check_no_bypass(bypass: bool = False, what: str = "") -> dict:
    """R-H212 红线③：**不绕验证**（人机验证 / 风控 / 平台校验一律不绕）。"""
    if bypass:
        return {"ok": False, "denied": True, "rule": "bypass_verification",
                "what": str(what or ""),
                "why": "不绕验证是**合规底座**，不是技术选择："
                       "验证码 / 风控 / 平台校验撞上就停下上报，不许想办法绕过"}
    return {"ok": True, "readonly": True, "what": str(what or "")}


def check_identity_keys(pairs: Optional[List] = None) -> dict:
    """R-H212 红线⑤⑥：**一 AI 一号** + **多身份各自独立密钥**。"""
    rows = list(pairs or [])
    if not rows:
        return {"ok": False, "denied": True, "rule": "missing_identity_keys",
                "why": "要说清「哪个 AI 身份用哪把密钥」；一 AI 一号，不是一触手一号"}
    seen: dict = {}
    for r in rows:
        d = dict(r or {})
        owner = str(d.get("owner_ai_id") or "").strip()
        key = str(d.get("key_id") or "").strip()
        if not owner:
            return {"ok": False, "denied": True, "rule": "missing_owner_ai_id",
                    "row": d, "why": "密钥必须挂到某个 AI 身份上，不许挂到触手上"}
        if key:
            if key in seen and seen[key] != owner:
                return {"ok": False, "denied": True,
                        "rule": "shared_key_across_identities",
                        "key_id": key, "owners": sorted({seen[key], owner}),
                        "why": "多个 AI 身份共用一把密钥 ⇒ 会被平台按单账号限流、"
                               "互相挤占；**各自独立密钥**"}
            seen[key] = owner
    return {"ok": True, "readonly": True, "identities": len({str((r or {}).get(
        "owner_ai_id") or "") for r in rows}), "pairs": len(rows)}


def must_trace_call(trace_ref: str = "", source_kind: str = "") -> dict:
    """R-H212 红线⑦⑧：**每次调用留痕** + `source_kind="libtv"`。

    注意粒度：这是**调用级**（每次调用），比 R-H204 的"结果级"更严一档。
    """
    ref = str(trace_ref or "").strip()
    if not ref:
        return {"ok": False, "denied": True, "rule": "call_not_traced",
                "why": "**每次调用**都要留痕（调用级，不只是结果级）——"
                       "没写 trace 的调用等于没发生"}
    sk = str(source_kind or "").strip()
    if sk != TRACE_SOURCE_KIND:
        return {"ok": False, "denied": True, "rule": "bad_source_kind",
                "source_kind": sk or "（未给）", "expected": TRACE_SOURCE_KIND,
                "why": '生成记录写入 trace_store 时必须带 source_kind="%s"'
                       "（否则事后按来源筛不出来）" % TRACE_SOURCE_KIND}
    return {"ok": True, "readonly": True, "trace_ref": ref, "source_kind": sk}


def must_pass_review(status: str = "") -> dict:
    """R-H212 红线⑨：**输出必须过审** —— 没过审不许标"可发布"。"""
    s = str(status or "").strip().lower()
    if s not in ("approved", "passed", "pass", "通过", "已过审"):
        return {"ok": False, "denied": True, "rule": "review_required",
                "status": s or "（未给）",
                "why": "结果回传大脑 → **内容审核** → 发布队列："
                       "没过审不许进发布队列，也不许标「可发布」"}
    return {"ok": True, "readonly": True, "status": s,
            "note": "过审是**发布的前置条件**，不是发布后的补救"}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / redlines / actions / forensics / contract
    / cli / canvas / delivery / policies / diagnose。不装、不调、不出网。"""
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE, "skill_source": SKILL_SOURCE,
                "actions": len(ACTIONS), "key_envs": list(EXTERNAL_KEY_ENVS),
                "forensics": FORENSICS,
                "note": "技能包与密钥均**未接**（取证：libtv 命中 0 · 密钥未配）"}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES),
                "red_lines_cli": list(RED_LINES_CLI),
                "red_lines_skill": list(RED_LINES_SKILL),
                "note": "R-H204 三条（密钥/明文/留痕）+ R-H205 四条（画布/重跑/归因/交付）"
                        "+ R-H207 一条（必须走 skill 脚本，不许自己拼 API）"}
    if op == "actions":
        return {"ok": True, "readonly": True, "actions": [dict(a) for a in ACTIONS]}
    if op == "forensics":
        return {"ok": True, "readonly": True, **FORENSICS}
    # ── R-H205 · 蒸馏面（只读知识，不是执行）──
    if op == "cli":
        return {"ok": True, "readonly": True, "commands": [dict(c) for c in CLI_COMMANDS],
                "node_ref": dict(NODE_REF),
                "note": "命令面来自官方指南蒸馏；**本骨架不执行任何 CLI 命令**"}
    if op == "canvas":
        return {"ok": True, "readonly": True,
                "zones": [{"key": k, "cn": cn, "what": w} for k, cn, w in CANVAS_ZONES],
                "rule": "先搭好完整画布结构 ⇒ 等确认 ⇒ 再开始生成"}
    if op == "delivery":
        return {"ok": True, "readonly": True, "required": list(DELIVERY_ITEMS)}
    if op == "policies":
        return {"ok": True, "readonly": True, **POLICIES}
    if op == "contract":
        return {"ok": True, "readonly": True, "cli": [dict(c) for c in CLI_COMMANDS],
                "node_ref": dict(NODE_REF),
                "failure_classes": [{"key": k, "cn": c} for k, c, _w in FAILURE_CLASSES],
                "canvas_zones": [k for k, _c, _w in CANVAS_ZONES],
                "delivery": list(DELIVERY_ITEMS), "policies": dict(POLICIES)}
    if op == "diagnose":
        return classify_failure(params.get("text") or params.get("error") or "")
    if op == "prepare_rerun":
        return must_diagnose_before_rerun(params)
    if op == "check_ref":
        return check_node_ref(params.get("prompt") or "")
    if op == "check_delivery":
        return delivery_check(params)
    # ── R-H207 · 交互面 / 要求面（只读知识 + 判据闸）──
    if op == "interaction":
        return {"ok": True, "readonly": True, **INTERACTION}
    if op == "requirements":
        return {"ok": True, "readonly": True,
                "requirements": [dict(r) for r in REQUIREMENTS]}
    if op == "gate_skill_script":
        return must_use_skill_script(params)
    if op == "gate_localize":
        return must_localize_oss(params, params.get("local_path") or "")
    if op == "gate_mask":
        return must_mask_key(params, where="gate_mask")
    if op == "gate_poll":
        return must_poll_incrementally(params.get("cursor") or "",
                                       bool(params.get("full_refetch")))
    if op == "gate_project":
        return must_project_bound(params.get("bound_project") or "")
    # ── R-H208 · 平台面 / 安装面 / 密钥口径 ──
    if op == "platform":
        return {"ok": True, "readonly": True, **PLATFORM}
    if op == "install":
        return {"ok": True, "readonly": True, **INSTALL}
    if op == "key_policy":
        return {"ok": True, "readonly": True, **KEY_INJECTION}
    if op == "gate_key_injection":
        return check_key_injection(params)
    if op == "gate_install":
        return check_install(params.get("method") or "")
    # ── R-H209 · 技能包的 5 个脚本 ──
    if op == "scripts":
        ev = [x["script"] for x in SKILL_SCRIPTS if x["evidenced"]]
        return {"ok": True, "readonly": True,
                "scripts": [dict(x) for x in SKILL_SCRIPTS],
                "count": len(SKILL_SCRIPTS),
                "evidenced": ev, "inferred": len(SKILL_SCRIPTS) - len(ev),
                "second_source": "**第二出处**：《LibTV Skill 使用指南》"
                                 "5/5 逐条一致（R-H218）",
                "primitive_map": {x["script"]: x["primitive"]
                                  for x in LIBTV_PRIMITIVES},
                "note": "**只抄不猜**：作用没实证的标 evidenced=False（推定）"}
    # ── R-H220 · 官方五原语 ──
    if op == "primitives":
        return {"ok": True, "readonly": True,
                "primitives": [dict(x) for x in LIBTV_PRIMITIVES],
                "count": len(LIBTV_PRIMITIVES),
                "order_note": ORDER_NOTE,
                "publish_chain": "生成的图片/视频**进内容审核队列**，"
                                 "**确认合规后才发布**（闸：review_required）",
                "domain": DOMAIN,
                "note": "官方五原语 5/5 与 R-H209 的 5 个脚本**一一对上**"}
    # ── R-H221 · 官方三条带牙用例 ──
    if op == "teeth_cases":
        return {"ok": True, "readonly": True,
                "cases": [dict(x) for x in TEETH_CASES],
                "count": len(TEETH_CASES),
                "all_match": all(x["match"] for x in TEETH_CASES),
                "note": "官方三条与我方三条**逐条一致**；"
                        "第 3 条是**原理↔形态**配对（不是两条不同的红线）"}
    if op == "gate_script":
        return check_script(params.get("script") or "")
    # ── R-H210 · 会话契约 / 调用形态 ──
    if op == "session_contract":
        return {"ok": True, "readonly": True, "scripts_dir": SKILL_SCRIPTS_DIR,
                **SESSION_CONTRACT}
    if op == "gate_poll_args":
        return check_poll_args(params.get("session_id") or params.get("sessionId") or "",
                               params.get("after_seq"))
    if op == "gate_session_refs":
        return check_session_refs(params.get("project_uuid")
                                  or params.get("projectUuid") or "",
                                  params.get("session_id")
                                  or params.get("sessionId") or "")
    # ── R-H212 · 接入安全与合规红线 9 条 ──
    if op == "access_redlines":
        official = [dict(x) for x in ACCESS_REDLINES[:OFFICIAL_REDLINE_COUNT]]
        extra = [dict(x) for x in ACCESS_REDLINES[OFFICIAL_REDLINE_COUNT:]]
        return {"ok": True, "readonly": True,
                "redlines": [dict(x) for x in ACCESS_REDLINES],
                "count": len(ACCESS_REDLINES),
                "groups": list(ACCESS_REDLINE_GROUPS),
                "closed": ACCESS_REDLINES_CLOSED,
                "official_count": OFFICIAL_REDLINE_COUNT,
                "official": official,
                "extra_requirements": extra,
                "extra_source": EXTRA_REQUIREMENTS_SOURCE,
                "note": ACCESS_REDLINES_NOTE}
    if op == "gate_key_storage":
        return check_key_storage(params.get("key_ref") or "",
                                 bool(params.get("from_pool")))
    if op == "gate_no_bypass":
        return check_no_bypass(bool(params.get("bypass")),
                               params.get("what") or "")
    if op == "gate_identity_keys":
        return check_identity_keys(params.get("pairs"))
    if op == "gate_trace_call":
        return must_trace_call(params.get("trace_ref") or "",
                               params.get("source_kind") or "")
    if op == "gate_review":
        return must_pass_review(params.get("status") or "")
    raise ValueError("未知 op %r（可用：status/redlines/actions/forensics/contract/"
                     "cli/canvas/delivery/policies/diagnose/prepare_rerun/"
                     "check_ref/check_delivery/interaction/requirements/"
                     "gate_skill_script/gate_localize/gate_mask/gate_poll/"
                     "gate_project/platform/install/key_policy/"
                     "gate_key_injection/gate_install/scripts/gate_script/"
                     "session_contract/gate_poll_args/gate_session_refs/"
                     "access_redlines/gate_key_storage/gate_no_bypass/"
                     "gate_identity_keys/gate_trace_call/gate_review/"
                     "primitives/teeth_cases）" % (op,))


HONEST_BOUNDARY = (
    "本骨架只保证『密钥只从池借、返回值不带明文、结果必须留痕』三条判据可执行。"
    "它不保证『LibTV 真的能用』—— 技能包未装、密钥未配（取证实测），"
    "『在』不等于『能用』。"
)

# R-H205 补一句边界：契约蒸馏**不是**执行能力
HONEST_BOUNDARY_CLI = (
    "本模块把官方指南**蒸馏成契约**（命令面 / 引用语法 / 失败分类 / 画布分区 / 交付七件 / "
    "积分与空间口径），它保证『该怎么做才不犯低级错』可查、可判。"
    "它**不保证**：CLI 已安装、账号已登录、积分够用、生成结果好看 —— "
    "那四件事里，前三件是环境，最后一件只能由人判。"
    "失败归类是**关键词归类**，只用于逼出一次诊断，不替代人判断。"
)
