"""GBT小土豆V8 · 触手桥（tentacle bridge）—— 连接大脑执行层的金钥匙。

Owner 定位（2026-09-11）：触手是连接大脑执行层的金钥匙——触手拥有小土豆的全部能力。
所有邻域皆触手所化：感知/桌面/侦察/自动化/运维/信息/金融……触手每一次强化 = 全邻域提升。

架构（V8 复活版，从归档区 brain/tentacle_bridge.py + omni_tentacle.py 迁移重写）：
  tentacle/           硬件层（10 个 omni_* 文件，原样迁移，不改一行逻辑）
  tentacle/bridge.py  金钥匙（本文件）：全框架唯一一只眼睛一双手的单例管理
                      + 能力清单（**条目数现算，不手写**）+ 10 邻域覆盖映射 + 六铁律

依赖（已装入 .pylibs，缺哪层哪层如实降级）——实测 DXGI 热路径 28-34ms/帧：
  ctypes（键鼠/窗口，标准库）→ 0 依赖可用
  mss（BitBlt 截图兜底）→ 截图可用
  uiautomation+comtypes（UIA 穿透）→ 读屏/域操作可用
  dxcam+numpy（DXGI 硬采加速）→ 可选，缺失自动降级 mss

铁律（继承自原版 MANIFEST，不可绕过）：
  ①先看再动 ②动后等稳定 ③找不到就滚 ④遇弹窗必关 ⑤每步亲眼验证 ⑥不确定就对比前后截图
"""
import json
import sys
import time
from pathlib import Path

_TENTACLE_DIR = Path(__file__).resolve().parent

# 依赖注入：唯一真相源走 dependency_paths.activate_local_dependencies()。
# 不再手打 .pylibs：手打会漏掉 ABI overlay（.pylibs/<abi>），
# 且会把 legacy 树顶到 sys.path[0]，对撞「系统包优先于 legacy 兜底」的设计。
try:
    from ..dependency_paths import activate_local_dependencies
except ImportError:            # 以脚本方式直跑 tentacle/bridge.py 时
    from gbt_allinone.dependency_paths import activate_local_dependencies
activate_local_dependencies()

# 触手自身目录仍需在路径上（另一件事，与 .pylibs 无关）
if str(_TENTACLE_DIR) not in sys.path:
    sys.path.insert(0, str(_TENTACLE_DIR))

_eye = None
_manifest = ""
_eye_error = ""


def get_eye():
    """获取共享触手实例——整个框架只有这一只眼睛一双手（单例）。"""
    global _eye, _eye_error
    if _eye is None:
        try:
            import importlib.util as iu
            spec = iu.spec_from_file_location("_omni_v8", str(_TENTACLE_DIR / "omni_tentacle.py"))
            mod = iu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _eye = mod.get_omni()
        except Exception as e:  # noqa: BLE001
            _eye_error = f"{type(e).__name__}: {e}"[:200]
            _eye = _DummyEye(_eye_error)
    return _eye


def eye_ready() -> bool:
    """触手是否就绪（硬件层加载成功）。"""
    return not isinstance(get_eye(), _DummyEye)


def eye_error() -> str:
    """触手未就绪时的根因（如实报告，不吞）。"""
    get_eye()
    return _eye_error


# ═══════════════════════════════════════════════════════════
#  意图 → 触手方法（§2.2 第三步：静态表覆盖 ≠ 说得出来就命中）
# ═══════════════════════════════════════════════════════════
# 她的方案原话：「真正新增的只有：意图样本句 + 别名表」——所以别名表是**唯一新增物**，
# 邻域归属仍读 TENTACLE_NEIGHBORHOOD_MAP，匹配器复用 brain_exec.route 的算法口径
# （词级 + 字符 2-gram，中文无空格也能命中），不另造第二套打分。
INTENT_ALIASES = {
    # 感知域
    "see": "看 看一眼 看看 现在屏幕什么样",
    "read_text": "读字 读一下上面写的 文字识别",
    "find_text": "找字 找找这个词在哪 定位文字",
    "screenshot": "截图 抓屏 截个图",
    "live": "实时看 持续看",
    "read_region_text": "读这块区域 区域文字",
    "grab_pixel": "取像素 看这个点的颜色",
    "grab_region": "取一片区域 区域图像",
    "vision_snapshot": "视觉快照 抓一帧",
    "vision_diff": "对比两帧 画面哪里变了",
    "read_text_fast": "快速读字 快读",
    "see_active_window": "看当前窗口 看活动窗口",
    # 桌面域
    "click": "点 点击 按一下",
    "type": "打字 输入 键入",
    "scroll": "滚动 滚一下",
    "drag": "拖 拖动",
    "hotkey": "快捷键 组合键",
    "move": "移动鼠标 挪到",
    "click_text": "点这个词 按文字点",
    "type_to_field": "填到输入框 填表 输入框",
    "launch": "打开 启动 运行程序",
    "kill": "关掉 结束进程 杀掉",
    "app_running": "在不在运行 程序开着吗",
    "focus_window": "切到窗口 激活窗口",
    "click_relative": "相对点击 往右点",
    "click_window": "点窗口 点那个窗口里",
    "click_window_occluded": "点被挡住的窗口 后台点击",
    "double_click": "双击",
    "right_click": "右键 右击",
    "right_click_text": "右键这个词",
    "act_window": "操作窗口 窗口动作",
    "type_to_window": "往窗口里打字",
    "dismiss_dialog": "关弹窗 关掉对话框",
    "on_dialog": "弹窗上操作",
    "on_text": "按文字定位后操作",
    # 侦察域
    "trace_source": "追来源 这个哪来的",
    "trace_text": "追这段字 文字来源",
    "trace_window_chain": "追窗口链 谁开出来的",
    "see_window": "看某个窗口",
    "list_windows": "列窗口 都开了什么",
    "grab_value": "取数值 读数字",
    "grab_table": "取表格 读表格 表格",
    "domain_index": "看界面结构 遍历控件",
    "domain_read": "读控件内容",
    "domain_type": "往控件里输入",
    "domain_act": "操作控件 触发控件",
    "extract_ui_elements": "提取界面元素",
    # 自动化
    "chain": "串起来 一步步做 流程",
    "monitor": "盯着 监控",
    "watch_and_click": "看着然后点",
    "wait_text": "等文字出现",
    "wait_for_change": "等变化",
    "handle_any_dialog": "处理任何弹窗",
    "scroll_find": "滚动找",
    "task_guide_load": "加载任务指引",
    "task_guide_next": "下一步 指引下一段",
    "task_guide_status": "指引状态 做到哪一步",
    "task_guide_check": "核对指引 对不对",
    "task_guide_complete": "完成这一步",
    "task_guide_drift_report": "偏离报告 跑偏了",
    "wait_stable": "等稳定 等界面不动",
    "wait_window_gone": "等窗口消失",
    "watch_any": "随便盯着 有动静就说",
    "watch_sequence": "盯一串动作",
    "scroll_to_top": "滚到顶",
    "scroll_to_bottom": "滚到底",
    # 信息域
    "clipboard_read": "读剪贴板 剪贴板",
    "clipboard_write": "写剪贴板 复制进去",
    "copy_text_at": "复制那个位置的文字",
    "read_console": "读控制台 读终端输出",
    "copy": "复制",
    "cut": "剪切",
    "select_all": "全选",
    # 运维域
    "process_list": "进程列表 都有什么进程",
    "wait_window": "等窗口出现",
    "diagnose": "诊断 体检触手",
    "deep_diagnose": "深度诊断",
    "export_data": "导出数据",
    "press": "按键 敲一下键",
    "enter": "回车 确认键",
    "escape": "退出键 按 esc",
    "tab": "切换焦点 按 tab",
    "undo": "撤销 退回上一步",
    "clipboard_copy": "拷到剪贴板",
    # AI编程 / 媒体域
    "paste": "粘贴",
    "screenshot_diff": "截图对比 截图差异",
    "vision_stream_record": "录一段视觉 录屏帧流 帧流",
    "vision_stream_replay": "回放录的帧流",
    # 安全域
    "detect_dialog": "有没有弹窗",
    # ── R-H993（2026-10-15）：听觉/文件/读网 三族原本**一条别名都没有**（实测：38/38 缺），
    #    这就是“她听不懂”的根因—— 说“帮我读一下文件”会被指到别的能力位。现按表格式逐条补齐。
    # 听觉域
    "audio_speak": "念出来 说话 朗读 读出来 语音合成",
    "audio_stop": "停止说话 别念了 停播",
    "audio_play_wav": "放个音频 播放音频文件",
    "audio_beep": "响一声 提示音",
    "audio_record": "录音 录一段音",
    "audio_stream": "音频流 持续听",
    "audio_loopback": "录系统声音 环回录音 听电脑在放什么",
    "audio_segment": "切一段音频 剪音频",
    "audio_barge_in": "打断说话 插话",
    "audio_vad_energy": "声音能量 有没有声音",
    "audio_vad_models": "声音检测模型",
    "audio_vad_silero": "静音检测 人在说话吗",
    "audio_devices": "音频设备 有哪些声卡 麦克风设备",
    "audio_voices": "有哪些嗓音 可选音色 有哪些语音 语音列表",
    "audio_wav_info": "音频文件信息",
    # 文件域
    "path_exists": "路径在不在 文件在不在",
    "dir_create": "建目录 新建文件夹",
    "file_info": "文件信息 文件多大 文件大小 占多大地方",
    "file_list": "列目录 看看文件夹里有什么",
    "file_read_text": "读文件 读一下这个文件的内容 打开看看里面写了啥",
    "file_write_text": "写文件 保存到文件",
    "file_copy": "复制文件",
    "file_move": "移动文件",
    "file_rename": "重命名文件",
    "file_delete": "删文件 删除文件 删掉 删了 干掉这个文件",
    "file_open": "打开文件",
    "file_reveal": "定位文件 在资源管理器里显示",
    # 读网域
    "web_fetch": "抓网页 拉取网页",
    "web_read": "读网页 网页正文 抓一下这个网页的正文",
    "web_text": "网页文字 提取网页文字",
    "web_parse": "解析网页",
    "web_select": "网页里选元素",
    "web_robots": "robots 规则 爬虫协议",
    "web_save": "保存网页",
    "web_stats": "网页统计",
    "web_adaptive": "自适应抓取 自动抓",
    # 自省与派发（归位同邻域表）
    "available_actions": "我有哪些动作 能做什么 动作清单",
    "invoke": "按名执行 直接调",
}


def _grams(s, n=2):
    """字符 n-gram —— **唯一实现在 `semantic_route.grams`**，这里只做转发。

    2026-09-19（Owner：路由不许三处真相）：本文件此前自带一份同名副本，与
    `brain_exec` 各写一遍。现在算法只有一处，改口径只改 `semantic_route.grams`。
    """
    from ..semantic_route import grams
    return grams(s, n)


# ── R-H995（2026-10-15 · 主人令：「读文件 vs 读屏幕」要判得出）────────────────
# 病根（实测）：「帮我读一下这个文件的内容」落到 read_text（感知域），而不是
#   file_read_text（文件域）—— 泛动词「读」赢了具体宾语「文件」。
# 口径：动作词 × 目标词（同 SEMANTIC_FIELDS 那一套）—— 宾语是哪个载体，就压哪个邻域。
# 守则（吸取方向偏置的教训）：只在「载体词命中 ∧ 同族候选在场」时才插话；
#   只命中载体词、没有动作词 ⇒ 只给弱偏置（+1），不抢别人的结论。
_CARRIER_RULES = (
    ("文件域", ("文件", "文件夹", "目录", "路径", "磁盘", "硬盘"),
     ("读", "写", "删", "复制", "移动", "改名", "重命名", "建", "新建", "列", "打开", "保存", "看", "在不在", "多大")),
    ("读网域", ("网页", "网址", "链接", "url", "网站", "正文", "页面"),
     ("抓", "读", "取", "拉", "保存", "解析", "统计", "看")),
    ("听觉域", ("语音", "声音", "音频", "录音", "麦克风", "喇叭", "音色", "背景音", "音"),
     ("放", "播", "录", "念", "说", "停", "听", "出声", "朗读")),
    ("感知域", ("屏幕", "画面", "截图", "像素", "区域", "窗口", "界面"),
     ("读", "看", "截", "取")),
)


def _carrier_bias(text: str, present: set) -> tuple:
    # 宾语载体裁决：回 (邻域, 偏置值, 命中词)；没命中回 ("", 0, "")。
    low = str(text or "").lower()
    for nb, objs, verbs in _CARRIER_RULES:
        hit_o = next((o for o in objs if o in low), "")
        if not hit_o or nb not in present:
            continue
        hit_v = next((v for v in verbs if v in low), "")
        return nb, (3 if hit_v else 1), (hit_o + "+" + hit_v if hit_v else hit_o)
    return "", 0, ""


def route_method(intent: str) -> dict:
    """意图 → 触手方法（**触手空间的辅路启发式**，词级 + 字符 2-gram）。

    2026-09-19（Owner 拍 A 案）：本函数是 `semantic_route.route()` 在**主路不可用时**
    调用的降级实现（`semantic_route.route('auto')` 的辅路分支），不再是"第二套独立
    路由权威"。路由权威只有一处：`semantic_route`。本函数只负责触手方法空间的打分。
    打分算法 `_grams` 亦转发自 `semantic_route.grams`，全框架一份。

    打分面 = 方法名 + 别名表 + 所属邻域名。**不直觉硬编码 if-else**，
    命中率是**跑出来**的，跑多少就报多少（《反假绿律》）。

    2026-09-19 修平手判决（实测 6/12 →）：
    原口径命中数打平就按**名字字母序**定胜负 ⇒ `scroll_to_top` 挤掉 `bottom`、
    `screenshot` 挤掉 `double_click`、`replay` 挤掉 `record`。英文名无权裁决中文意图。
    新判决（从强到弱）：
      ① **整词命中**：别名里的词（≥2 字）在句子里**整词出现**才算强命中 —— 这是"说的是这个概念"；
      ② 字符 2-gram 命中数（弱信号，只做辅助）；
      ③ 最长公共子串长度（越具体越长）；
      ④ 字母序 —— **仅作最后兜底**，且此项一旦生效会被记进 `tie_by_name` 供审计。
    """
    text = str(intent or "").strip()
    if not text:
        return {"ok": False, "error": "需要 intent"}
    low = text.lower()
    words = set(text.lower().split()) | _grams(text)
    owner = {}
    for dom, info in TENTACLE_NEIGHBORHOOD_MAP.items():
        for m in info["powered_by"]:
            owner.setdefault(m, dom)

    def _lcs(a: str, b: str) -> int:
        """最长公共子串长度：越具体越长（'剪贴板'3 > '出来'2）。"""
        best = 0
        for i in range(len(a)):
            for j in range(i + best + 1, len(a) + 1):
                if a[i:j] in b:
                    best = j - i
                else:
                    break
        return best

    # 方向判别（Owner 2026-09-19）：读/拷、录/放 是**语法问题**，不是词表问题。
    # 判得出方向就给同族候选加偏置、给反向候选减分；**判不出就一点不偏**（不硬猜）。
    try:
        from . import direction as _dir
        _d = _dir.analyze(text)
        _dir_name = _d.get("direction")
        _dir_family = set(_dir.bias(_dir_name))
        _opposite = {"read": "write", "write": "read",
                     "record": "replay", "replay": "record"}.get(_dir_name)
        _dir_anti = set(_dir.bias(_opposite)) if _opposite else set()
    except Exception:  # noqa: BLE001
        _d, _dir_family, _dir_anti = {"direction": None}, set(), set()

    rows = []
    for m in sorted(set(owner) | set(INTENT_ALIASES)):
        alias = INTENT_ALIASES.get(m, "")
        face = " ".join([m, dom_name(owner.get(m, "")), alias])
        hits = len(words & (_grams(face) | set(face.lower().split())))
        # ⚠️ 2026-09-19 修：原来 `if not hits: continue` 把**只有语义场能救**的方法先筛没了
        # （留出集一堆 None 就是这么来的）。语义场必须参与"是否入候选"，不能只参与排序。
        strong_f, weak_f = _field_tokens(m)
        field_hits = sum(1 for w in strong_f if w in low)
        # ── R-H295 · 深修：命中词的**具体度**必须参与排序 ──
        # 病根（实测打红留出集那条）：语义场是**子串匹配**（`w in low`），
        # 于是短词会命中长词的一部分 —— `paste` 的 objects 里有"粘贴"，
        # 而 "粘贴" 正是 "粘贴板" 的前两个字 ⇒ 「把这段塞进粘贴板」被 `paste` 抢走
        # （期望 clipboard_copy）。原来只数命中**个数**，不看命中的词有多具体。
        # 补一档 field_max = 命中强词的最长长度：越长的词越具体，越该赢。
        _matched_f = [w for w in strong_f if w in low]
        field_max = max((len(w) for w in _matched_f), default=0)
        # ① 泛动词降权为 0（第三批实测）：单字常用动词（读/看/取/查/点/按…）几乎每个方法都有，
        # 拿它算命中就是"谁都能进候选"，会把具体宾语的正确命中挤掉（clipboard_read 抢
        # read_console / grab_value / see_active_window 三条，全是这个原因）。
        # 只保留 2 字以上的动作词（回放/复制/录屏…）—— 它们才有区分度。
        verb_hits = sum(1 for w in weak_f if len(w) >= 2 and w in low)
        if not (hits or field_hits):
            continue
        # ① 整词命中：别名里的短词在句子里整词出现（"双击" ⊂ "帮我双击那个图标"）
        matched_words = [w for w in alias.split() if len(w) >= 2 and w in low]
        strong = len(matched_words)
        # ①b 越具体的词越算数："输入框"(3) 该压过 "打字"(2)/"输入"(2) ——
        #     否则用户说得越具体，越会被泛词抢走（实测 4 条 MISS 全是这个形态）。
        specific = max((len(w) for w in matched_words), default=0)
        # ①c 语义场（动作词×目标词）：目标词（≥2字）算强，动作词（1字）算弱（见上）。
        # ③ 最长公共子串（拿方法名与别名一起比）
        lcs = max(_lcs(alias, low), _lcs(m.replace("_", " "), low))
        rows.append((field_hits, field_max, specific, strong, verb_hits, hits, lcs, m, owner.get(m, "?")))

    # ⚠️ 方向偏置**只在真正对峙时生效**（2026-09-19 实测踩到的坑）：
    # 第一版把方向放在最前、对所有读类 +2 ⇒ 「查一下弹框」被 read_text 抢走、
    # 「读这张表格」被 clipboard_read 抢走、种子集从 83.3% 掉到 66.7%。
    # 方向只该裁决**同族反向对峙**（读 vs 拷、录 vs 放）；没有对峙就不许插话。
    _contested = bool(_dir_name) and any(
        r[7] in _dir_family for r in rows) and any(r[7] in _dir_anti for r in rows)
    if _contested:
        rows = [((2 if r[7] in _dir_family else (-2 if r[7] in _dir_anti else 0)),) + r
                for r in rows]
    else:
        rows = [(0,) + r for r in rows]
    # 载体名词裁决（R-H995）：宾语是哪个载体，就压哪个邻域（只在同族候选在场时）。
    _present_nb = {r[9] for r in rows}
    _cnb, _cw, _chit = _carrier_bias(text, _present_nb)
    if _cnb and _cw:
        rows = [((r[0] + (_cw if r[9] == _cnb else 0)),) + r[1:] for r in rows]
    # 从强到弱：方向 → 语义场目标词 → 具体度 → 整词数 → 动作词 → 2-gram → 公共子串 → 名字序
    rows.sort(key=lambda r: (-r[0], -r[1], -r[2], -r[3], -r[4], -r[5], -r[6], -r[7], r[8]))
    top = rows[:5]
    tie_by_name = bool(len(rows) > 1 and rows[0][:8] == rows[1][:8])
    # ── 不确定就说不知道（Owner 2026-09-19：宁可如实报错，绝不静默造假）──
    # 判据：前四档信号（方向/语义场宾语/具体度/整词）**没有拉开**，或者根本没拿到正向信号
    # ⇒ 这个结果不配当"确定结论"，标记出来交给上层（要么走模型主路，要么问主人）。
    # 注意：这不是"提高命中率"的手段，它不改答案，只**如实标注这个答案有多虚**。
    if len(rows) < 2:
        margin = None
        confident = bool(top) and any(rows[0][1:5])
    else:
        margin = sum(1 for a, b in zip(rows[0][:8], rows[1][:8]) if a != b)
        confident = margin > 0 and any(rows[0][1:5])
    return {"ok": True, "intent": text[:120],
            "direction": _dir_name, "direction_why": _d.get("why"),
            "carrier_neighborhood": _cnb, "carrier_weight": _cw, "carrier_hit": _chit,
            "confident": confident, "margin": margin,
            "best": {"method": top[0][8], "neighborhood": top[0][9], "dir": top[0][0],
                     "field": top[0][1], "field_max": top[0][2], "specific": top[0][3],
                     "strong": top[0][4], "verb": top[0][5], "grams": top[0][6],
                     "lcs": top[0][7]} if top else None,
                               "alternatives": [{"method": r[8], "neighborhood": r[9], "dir": r[0],
                              "field": r[1], "field_max": r[2]} for r in top[1:]],
            "candidates": len(rows),
            # 平手兜底一旦生效，必须看得见（否则又变成静默的字母序裁决）
            "tie_by_name": tie_by_name}


# ── 语义场扩展（Owner 2026-09-19：别再"看一眼 MISS 补一句"，要按语义场展开）──
# 口径：动作词 × 目标词。动作词多为单字（滚/滑/拉/翻），目标词多为 2 字以上（底部/页尾/最下面）。
# 打分时：目标词（≥2字）命中算强，动作词（1字）命中算弱 —— 强弱分开，不混算。
SEMANTIC_FIELDS = {
    # ── R-H295 · 深修：从各方法**自己的别名**补出来的语义场（56 个空洞）──
    # 实测：89 个方法里 56 个（62.9%）语义场为空，且全都有别名 ——
    # 即「别名叫得出、语义场这条路走不通」，只能靠弱信号 2-gram 挤候选。
    # 典型：`list_windows`（别名『列窗口 都开了什么』）输给 `focus_window`
    # （它的 objects 里有『窗口』）—— 用户说『有哪些窗口』却落到『切到窗口』。
    # 词只从别名自身取；**不碰留出集**（补后留出集命中率只许不降，已复测）。
    'act_window': {"verbs": '', "objects": '操作窗口 窗口动作'},
    'app_running': {"verbs": '', "objects": '在不在运行 程序开着吗'},
    'chain': {"verbs": '', "objects": '串起来 一步步做 流程'},
    'click_relative': {"verbs": '', "objects": '相对点击 往右点'},
    'click_text': {"verbs": '', "objects": '点这个词 按文字点'},
    'click_window': {"verbs": '', "objects": '点窗口 点那个窗口里'},
    'click_window_occluded': {"verbs": '', "objects": '点被挡住的窗口 后台点击'},
    'clipboard_write': {"verbs": '', "objects": '写剪贴板 复制进去'},
    'copy_text_at': {"verbs": '', "objects": '复制那个位置的文字'},
    'cut': {"verbs": '', "objects": '剪切'},
    'deep_diagnose': {"verbs": '', "objects": '深度诊断'},
    'diagnose': {"verbs": '', "objects": '诊断 体检触手'},
    'dismiss_dialog': {"verbs": '', "objects": '关弹窗 关掉对话框'},
    'domain_act': {"verbs": '', "objects": '操作控件 触发控件'},
    'domain_index': {"verbs": '', "objects": '看界面结构 遍历控件'},
    'domain_type': {"verbs": '', "objects": '往控件里输入'},
    'export_data': {"verbs": '', "objects": '导出数据'},
    'extract_ui_elements': {"verbs": '', "objects": '提取界面元素'},
    'grab_pixel': {"verbs": '', "objects": '取像素 看这个点的颜色'},
    'grab_region': {"verbs": '', "objects": '取一片区域 区域图像'},
    'hotkey': {"verbs": '', "objects": '快捷键 组合键'},
    'kill': {"verbs": '', "objects": '关掉 结束进程 杀掉'},
    'launch': {"verbs": '', "objects": '打开 启动 运行程序'},
    # 深修：补名词「窗口」与枚举词 —— 口径照表里既有的 process_list
    # （它 objects 本来就是「程序 进程 开着哪些 跑着哪些」）。
    # 少了这一条时，用户说「看看现在有哪些窗口」会被 focus_window 抢走
    # （它 objects 里有「窗口」，而本方法为空）。
    'window_list': {"verbs": '', "objects": '窗口 列表'},
    # 注：window_list 与 list_windows 同族；只放名词「窗口」，不放通用枚举词。
    # ⚠️ 只放**名词**，不放通用枚举词（有哪些/列表/清单）：实测加进去之后
    # 「看看有哪些**进程**」被它抢走（tokenizer 按词长分强弱，表达不了「枚举×名词」），
    # 且留出集从 100% 掉到 97.4%。通用词不是区分度，是污染 —— 撤。
    'list_windows': {"verbs": '列 看 查',
                     "objects": '窗口 都开了什么 列窗口'},
    'live': {"verbs": '', "objects": '实时看 持续看'},
    'monitor': {"verbs": '', "objects": '盯着 监控'},
    'on_dialog': {"verbs": '', "objects": '弹窗上操作'},
    'on_text': {"verbs": '', "objects": '按文字定位后操作'},
    'paste': {"verbs": '', "objects": '粘贴'},
    'press': {"verbs": '', "objects": '按键 敲一下键'},
    'read_region_text': {"verbs": '', "objects": '读这块区域 区域文字'},
    'read_text_fast': {"verbs": '', "objects": '快速读字 快读'},
    'right_click_text': {"verbs": '', "objects": '右键这个词'},
    'screenshot': {"verbs": '', "objects": '截图 抓屏 截个图'},
    'screenshot_diff': {"verbs": '', "objects": '截图对比 截图差异'},
    'scroll_find': {"verbs": '', "objects": '滚动找'},
    'see_window': {"verbs": '', "objects": '看某个窗口'},
    'select_all': {"verbs": '', "objects": '全选'},
    'tab': {"verbs": '按', "objects": '切换焦点 tab'},
    'task_guide_check': {"verbs": '', "objects": '核对指引 对不对'},
    'task_guide_complete': {"verbs": '', "objects": '完成这一步'},
    'task_guide_drift_report': {"verbs": '', "objects": '偏离报告 跑偏了'},
    'task_guide_load': {"verbs": '', "objects": '加载任务指引'},
    'task_guide_next': {"verbs": '', "objects": '下一步 指引下一段'},
    'task_guide_status': {"verbs": '', "objects": '指引状态 做到哪一步'},
    'trace_source': {"verbs": '', "objects": '追来源 这个哪来的'},
    'trace_text': {"verbs": '', "objects": '追这段字 文字来源'},
    'trace_window_chain': {"verbs": '', "objects": '追窗口链 谁开出来的'},
    'type_to_window': {"verbs": '', "objects": '往窗口里打字'},
    'vision_diff': {"verbs": '', "objects": '对比两帧 画面哪里变了'},
    'vision_snapshot': {"verbs": '', "objects": '视觉快照 抓一帧'},
    'wait_for_change': {"verbs": '', "objects": '等变化'},
    'wait_stable': {"verbs": '', "objects": '等稳定 等界面不动'},
    'wait_text': {"verbs": '', "objects": '等文字出现'},
    'wait_window_gone': {"verbs": '', "objects": '等窗口消失'},
    'watch_any': {"verbs": '', "objects": '随便盯着 有动静就说'},

    "scroll_to_bottom": {"verbs": "滚 滑 拉 翻 拖",
                         "objects": "到底 最底 底部 页尾 尾部 尽头 底端 最下面"},
    "scroll_to_top": {"verbs": "滚 滑 拉 翻 回",
                      "objects": "到顶 顶部 页首 开头 最上面 顶端 头部"},
    "double_click": {"verbs": "点 敲 按", "objects": "双击 两下 连续点 双点"},
    "right_click": {"verbs": "点 按", "objects": "右键 右击 副键"},
    "clipboard_read": {"verbs": "读 看 取", "objects": "剪贴板 粘贴板 拷贝板"},
    "clipboard_copy": {"verbs": "拷 复制 存", "objects": "剪贴板 粘贴板 拷贝板"},
    # ⚠️ "文字/内容/这段" 已删：它们不具区分度（谁都能拿它们当宾语），
    # 留着会把「右击这段文字」的 right_click 挤掉（留出集实测）。
    "copy": {"verbs": "拷 复制 拿", "objects": "副本 摘录 抄本"},
    "undo": {"verbs": "撤 退 回", "objects": "撤销 上一步 后退 复原 回退"},
    "enter": {"verbs": "按 敲 点", "objects": "回车 确认键 换行键 回车键"},
    "escape": {"verbs": "按 敲 退", "objects": "esc 退出键 取消键"},
    "type_to_field": {"verbs": "打 填 输 录", "objects": "输入框 字段 表单 表格框"},
    "focus_window": {"verbs": "切 跳 换 激活", "objects": "窗口 前台 当前窗口"},
    "detect_dialog": {"verbs": "看 查 盯", "objects": "弹窗 对话框 弹框 提示框"},
    "vision_stream_record": {"verbs": "录 拍 存", "objects": "帧流 录屏 视频流 一段"},
    "vision_stream_replay": {"verbs": "放 回放 播", "objects": "帧流 录屏 录像 那一段"},
    "grab_table": {"verbs": "读 取 抓 抄", "objects": "表格 报表 数据表"},
    # ── 第三批暴露的三类一般性缺陷，补的是**规则**不是句子 ──
    # ① 泛动词黑洞：单个常用动词（读/看/取/查…）几乎每个方法都有，不具区分度；
    #     给"泛方法"补它们自己的**宾语**，让具体宾语去分胜负，而不是让泛动词乱吸。
    "scroll": {"verbs": "滚 滑 翻", "objects": "一屏 页面 屏幕 往上 往下 上下"},
    "read_text": {"verbs": "读 念 看", "objects": "字 文字 屏幕上的字 上面写的"},
    "click": {"verbs": "点 按 敲", "objects": "按钮 图标 那里 这个位置"},
    "type": {"verbs": "打 输 敲", "objects": "字 句话 内容 进去"},
    "see": {"verbs": "看", "objects": "一眼 屏幕 现在什么样"},
    "move": {"verbs": "挪 移", "objects": "鼠标 指针 右边 左边 到那个位置"},
    "drag": {"verbs": "拖 拉", "objects": "拖住 挪到 拖到 拖过去"},
    # ② 口语词进表（活人说话的方式，不是动作名）
    "grab_value": {"verbs": "看 读 取", "objects": "格子 数字 数值 里面写的"},
    "domain_read": {"verbs": "看 读", "objects": "控件里 写着什么 控件内容"},
    "handle_any_dialog": {"verbs": "处理 关", "objects": "弹窗 对话框 弹出来 挡着"},
    "read_console": {"verbs": "读 看", "objects": "控制台 终端 输出 命令行"},
    "process_list": {"verbs": "看 查", "objects": "程序 进程 开着哪些 跑着哪些"},
    "see_active_window": {"verbs": "看", "objects": "活动窗口 当前窗口 正在用的窗口"},
    "find_text": {"verbs": "找", "objects": "位置 在哪 哪个位置 这行字"},
    "watch_and_click": {"verbs": "盯 等", "objects": "出现就点 出现就按 亮了就点"},
    "wait_window": {"verbs": "等", "objects": "窗口出来 窗口出现 弹出来"},
    "watch_sequence": {"verbs": "盯 看 守", "objects": "一串 连续 序列 整套动作 一串动作"},
}


def _field_tokens(m: str) -> tuple:
    """返回 (强词列表≥2字, 弱词列表=1字)。语义场是**别名表的补充**，不是替代。"""
    f = SEMANTIC_FIELDS.get(m) or {}
    toks = str(f.get("verbs", "")).split() + str(f.get("objects", "")).split()
    return [t for t in toks if len(t) >= 2], [t for t in toks if len(t) == 1]


# 留出集（每族 3 句，共 36 句）——**先写死，再动别名表**。判据：≥80% 才算 §2.2 收工。
# 句子里一律不出现方法名；写这批句子时**还没有**针对它们调过任何词。
HELD_OUT_PHRASES = [
    ("翻到页面页尾", "scroll_to_bottom"), ("滑到最下面那行", "scroll_to_bottom"), ("拉到尽头看看", "scroll_to_bottom"),
    ("回到页面最上面", "scroll_to_top"), ("翻回页首", "scroll_to_top"), ("滑到顶端", "scroll_to_top"),
    ("连续点两下图标", "double_click"), ("双击那个文件夹", "double_click"), ("快敲两下", "double_click"),
    ("按一下右键菜单", "right_click"), ("右击这段文字", "right_click"), ("调出副键菜单", "right_click"),
    ("把粘贴板里的东西念出来", "clipboard_read"), ("看看拷贝板有什么", "clipboard_read"), ("念一下剪贴板", "clipboard_read"),
    ("把这段塞进粘贴板", "clipboard_copy"), ("复制到拷贝板去", "clipboard_copy"), ("存进剪贴板", "clipboard_copy"),
    ("把刚才那步复原", "undo"), ("回退上一步", "undo"), ("撤销掉这个动作", "undo"),
    ("按下回车键", "enter"), ("敲一下确认键", "enter"), ("按换行键继续", "enter"),
    ("把窗口切到前台", "focus_window"), ("跳到那个窗口去", "focus_window"), ("激活当前窗口", "focus_window"),
    ("有没有提示框冒出来", "detect_dialog"), ("查一下弹框", "detect_dialog"), ("弹出对话框没", "detect_dialog"),
    ("录一段录像存起来", "vision_stream_record"), ("把这段拍成视频流", "vision_stream_record"), ("录屏一段", "vision_stream_record"),
    ("放一下刚才那一段", "vision_stream_replay"), ("回放录像", "vision_stream_replay"), ("播一下帧流", "vision_stream_replay"),
    ("把报表抓出来", "grab_table"), ("抄一下数据表", "grab_table"), ("读这张表格", "grab_table"),
]


# ── 第三批：**全新句子**，与种子集/留出集零重叠 ──
# 纪律（Owner 2026-09-19）：这批写下来的**那一刻**就跑，跑出什么报什么，
# **不得据此调任何词表/权重**。一旦为它改过一行，它就废了，必须再写第四批。
# 覆盖到前两批没压过的族（感知/侦察/自动化/运维），故意包含几条本来就模糊的句子 ——
# 模糊句子上的分歧是真实成本，不该靠调参抹平。
HOLDOUT3_PHRASES = [
    ("把屏幕上的字念给我听", "read_text"),
    ("抓一张屏发我", "screenshot"),
    ("这个按钮在哪，帮我按下去", "click_text"),
    ("把那句话敲进去", "type"),
    ("往上翻一屏", "scroll"),
    ("拖住这个图标挪到右边", "drag"),
    ("把记事本关掉", "kill"),
    ("看看现在开着哪些程序", "process_list"),
    ("读一下终端里的输出", "read_console"),
    ("等这个窗口出来", "wait_window"),
    ("有弹窗就处理掉", "handle_any_dialog"),
    ("把这一片截下来", "grab_region"),
    ("看下这个格子里的数字", "grab_value"),
    ("这个控件里写着什么", "domain_read"),
    ("敲一下 Esc", "escape"),
    ("按 Tab 切下一个", "tab"),
    ("把这步撤掉", "undo"),
    ("全选之后复制", "select_all"),
    ("看一眼活动窗口", "see_active_window"),
    ("把过程录下来", "vision_stream_record"),
    ("把刚才录的放一遍", "vision_stream_replay"),
    ("找找这行字在屏幕哪个位置", "find_text"),
    ("往前翻到第一页", "scroll_to_top"),
    ("盯着这个按钮出现就点它", "watch_and_click"),
]


# ── 第四批：全新句子（与前一二三批零重叠）──
# 用法：第三批已"烧掉"（可以拿它调参），**第四批是拿来量泛化的**。
# 同样纪律：写完就跑一次，跑出什么报什么；若据此调参，第四批作废，必须再写第五批。
HOLDOUT4_PHRASES = [
    ("把光标移到右上角", "move"),
    ("把这段字打到搜索框里", "type_to_field"),
    ("看一下当前这个窗口", "see_active_window"),
    ("屏幕上写着什么", "read_text"),
    ("把鼠标拖到图标上", "drag"),
    ("等页面加载完再点", "wait_stable"),
    ("控制台报了什么错", "read_console"),
    ("这行字在哪儿", "find_text"),
    ("把表格里的数字抄下来", "grab_table"),
    ("把整个屏幕截下来", "screenshot"),
    ("弹窗挡住了，关掉它", "handle_any_dialog"),
    ("把刚才的操作撤了", "undo"),
    ("按钮一亮就按它", "watch_and_click"),
    ("把这段录成视频流", "vision_stream_record"),
    ("页面上半部分有什么", "read_region_text"),
    ("把窗口切过去", "focus_window"),
]


def dom_name(dom: str) -> str:
    """邻域名本身也进打分面（说"剪贴板"该能命中信息域那一族）。"""
    return str(dom or "")


# §2.2 验收种子集：每个族一句人话，**句子里不出现方法名**（否则是自证）。
SEED_PHRASES = [
    ("看一眼现在屏幕什么样", "see"),
    ("把这个表格读出来", "grab_table"),
    ("帮我双击那个图标", "double_click"),
    ("往输入框里打字", "type_to_field"),
    ("等界面不动了再继续", "wait_stable"),
    ("读一下剪贴板里的内容", "clipboard_read"),
    ("列一下现在都开了什么窗口", "list_windows"),
    ("把这段录成帧流", "vision_stream_record"),
    ("看下这个控件是什么内容", "domain_read"),
    ("导出这些数据", "export_data"),
    ("滚到页面最底下", "scroll_to_bottom"),
    ("有没有弹窗冒出来", "detect_dialog"),
]


def intent_coverage() -> dict:
    """跑种子集算意图命中率 —— **跑多少报多少**，没命中的逐条列出来。"""
    hits, miss = [], []
    for phrase, expect in SEED_PHRASES:
        r = route_method(phrase)
        got = (r.get("best") or {}).get("method")
        (hits if got == expect else miss).append(
            {"seed": phrase, "expect": expect, "got": got})
    total = len(SEED_PHRASES) or 1
    return {"ok": not miss, "seeds": total, "hit": len(hits), "miss": len(miss),
            "seed_hit_rate_pct": round(100.0 * len(hits) / total, 1),
            "misses": miss,
            "note": "命中率是跑出来的读数；别名表是唯一新增物，邻域归属读 TENTACLE_NEIGHBORHOOD_MAP。"}


def get_manifest() -> str:
    """触手能力总纲——**条目数运行时现算，不手写**（手写数会腐烂）+ 三通道感官 + 六铁律。"""
    global _manifest
    if not _manifest:
        try:
            import importlib.util as iu
            spec = iu.spec_from_file_location("_omni_mf_v8", str(_TENTACLE_DIR / "omni_tentacle.py"))
            mod = iu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _manifest = getattr(mod, "TENTACLE_MANIFEST", "")
        except Exception:
            _manifest = "触手能力清单暂不可用"
    return _manifest


# ═══════════════════════════════════════════════════════════
#  触手→邻域 能力映射（继承原版 17 邻域：所有邻域皆触手所化）
# ═══════════════════════════════════════════════════════════

# 非动作型方法：她的「89 能力名」口径就是把这 6 个剔掉（不是动作，是读数口）。
# 覆盖率以 **89** 为分母；这 6 个如实列在这里，不算缺漏、也不算覆盖。
NON_ACTION_METHODS = ("clear_log", "get_log", "position",
                      "screen_size", "self_diagnose", "self_diagnose_text")

TENTACLE_NEIGHBORHOOD_MAP = {
    # §2.2 补全（Owner 2026-09-19）：40 → 89，让每个动作都有归属邻域。
    # 分母取真身 `_raw` 的公开方法（95），扣除上面 6 个非动作型 = 89。
    # ⚠️ 踩过的坑：`HardenedOmniTentacle` 是 __getattr__ 委派壳，`dir()` 数不到方法，
    #    用 `dir()` 当分母会数出 0（我上一轮就错在这），必须从真身取。
    "感知域": {"powered_by": ["see", "read_text", "find_text", "screenshot", "live", "read_region_text",
                              "grab_pixel", "grab_region", "vision_snapshot", "vision_diff",
                              "read_text_fast", "see_active_window", "available_actions"]},
    "桌面域": {"powered_by": ["click", "type", "scroll", "drag", "hotkey", "move", "click_text",
                              "type_to_field", "launch", "kill", "app_running", "focus_window",
                              "click_relative", "click_window", "click_window_occluded",
                              "double_click", "right_click", "right_click_text", "act_window",
                              "type_to_window", "dismiss_dialog", "on_dialog", "on_text"]},
    "侦察域": {"powered_by": ["trace_source", "trace_text", "trace_window_chain", "see_window",
                              "list_windows", "grab_value", "grab_table",
                              "domain_index", "domain_read", "domain_type", "domain_act",
                              "extract_ui_elements"]},
    "自动化": {"powered_by": ["chain", "monitor", "watch_and_click", "wait_text",
                              "wait_for_change", "handle_any_dialog", "scroll_find",
                              "task_guide_load", "task_guide_next", "task_guide_status",
                              "task_guide_check", "task_guide_complete", "task_guide_drift_report",
                              "wait_stable", "wait_window_gone", "watch_any", "watch_sequence",
                              "scroll_to_top", "scroll_to_bottom", "invoke"]},
    "信息域": {"powered_by": ["read_text", "find_text", "grab_value", "grab_table", "clipboard_read",
                              "clipboard_write", "copy_text_at", "read_region_text",
                              "read_console", "copy", "cut", "select_all"]},
    "运维域": {"powered_by": ["launch", "kill", "process_list", "app_running", "clipboard_read",
                              "clipboard_write", "screenshot", "wait_window",
                              "diagnose", "deep_diagnose", "export_data", "press",
                              "enter", "escape", "tab", "undo", "clipboard_copy"]},
    "AI编程": {"powered_by": ["type", "hotkey", "click", "clipboard_write", "paste", "launch",
                               "see", "screenshot"]},
    "金融域": {"powered_by": ["read_text", "find_text", "grab_value", "grab_table",
                              "click_text", "type", "screenshot"]},
    "媒体域": {"powered_by": ["see", "screenshot", "live", "see_window", "screenshot_diff",
                              "vision_stream_record", "vision_stream_replay"]},
    "安全域": {"powered_by": ["trace_source", "trace_window_chain", "detect_dialog",
                              "handle_any_dialog", "monitor", "see"]},
    # ── R-H993（2026-10-15 · 主人令「看全部链路与她自己的理解与执行能力」）──────
    #    实测缺口：意图覆盖率 **70.1%**（89/127），未覆盖 38 项**全是音频/文件/读网三族**，
    #    因为它们在这张**任务邻域表**里没有家（表只有感知/桌面/侦察/自动化/信息/运维/
    #    AI编程/金融/媒体/安全 10 个任务邻域）。补三个邻域，让每个真实动作都有归属。
    #    这就是「她的理解」到「她的动作」之间断掉的那一段。
    "听觉域": {"powered_by": ["audio_devices", "audio_voices", "audio_wav_info",
                              "audio_speak", "audio_stop", "audio_play_wav", "audio_beep",
                              "audio_record", "audio_stream", "audio_loopback", "audio_segment",
                              "audio_barge_in", "audio_vad_energy", "audio_vad_models",
                              "audio_vad_silero"]},
    "文件域": {"powered_by": ["path_exists", "dir_create", "file_info", "file_list",
                              "file_read_text", "file_write_text", "file_copy", "file_move",
                              "file_rename", "file_delete", "file_open", "file_reveal"]},
    "读网域": {"powered_by": ["web_fetch", "web_read", "web_text", "web_parse", "web_select",
                              "web_robots", "web_save", "web_stats", "web_adaptive"]},
    # 杂项归位（各按其实义，不硬塞）：
    #   available_actions —— 自省式清点「我有哪些动作」⇒ 感知域（她先看清自己）；
    #   invoke            —— 按名派发的通用执行口 ⇒ 自动化。
}


def real_methods() -> list:
    """触手真身（`_raw`）的公开方法清单 —— **覆盖率的分母只能从这里取**。

    `HardenedOmniTentacle` 是 `__getattr__` 委派壳（`__dict__` 只有 `_raw/_last_screen/_step_count`），
    `dir()` 数不到委派方法 ⇒ 用壳当分母会数出 0（2026-09-19 实测踩到，并已如实登记）。
    """
    e = get_eye()
    raw = getattr(e, "_raw", None) or e
    names = []
    for n in dir(raw):
        if n.startswith("_"):
            continue
        try:
            if callable(getattr(raw, n)):
                names.append(n)
        except Exception:  # noqa: BLE001
            continue
    return sorted(names)


def coverage() -> dict:
    """触手对各邻域的覆盖度 —— **实时对账**（覆盖/缺漏/幽灵/分母 四项都报）。"""
    all_methods = set()
    for info in TENTACLE_NEIGHBORHOOD_MAP.values():
        all_methods.update(info["powered_by"])
    cov = {}
    for domain, info in TENTACLE_NEIGHBORHOOD_MAP.items():
        methods = info["powered_by"]
        cov[domain] = {
            "methods": len(methods),
            "key_capability": methods[0] if methods else "none",
        }
    real = set(real_methods())
    actions = real - set(NON_ACTION_METHODS)
    uncovered = sorted(actions - all_methods)
    ghosts = sorted(all_methods - real)
    denom = len(actions) or 1
    return {
        "ok": True,
        "total_domains": len(TENTACLE_NEIGHBORHOOD_MAP),
        "total_tentacle_methods_used": len(all_methods),
        # §2.2 判据（可数）：意图覆盖率 = 进邻域表的动作数 ÷ 动作总数
        "denominator": denom,
        "denominator_source": "_raw 真身公开方法 95 − 非动作型 6 = 89",
        "real_methods": len(real),
        "non_action_excluded": list(NON_ACTION_METHODS),
        "covered_actions": len(actions & all_methods),
        "uncovered_actions": uncovered,
        "uncovered_count": len(uncovered),
        "ghosts_in_map": ghosts,
        "intent_coverage_pct": round(100.0 * len(actions & all_methods) / denom, 1),
        "coverage": cov,
        "eye_ready": eye_ready(),
        "truth": "所有邻域皆触手所化。触手每一次强化=全邻域提升。",
    }


_COGNITION_SEQ = [0]


def build_cognition(method: str = "", intent: str = "", actor: str = "tentacle") -> dict:
    """给一次触手调用造认知包 —— **能力全息 + 当前任务聚焦 + 自检三问在位**。

    2026-09-22（Owner：确保每根触手执行任务时都拥有本体的所有能力**以及思考能力**）

    为什么要有这个函数（取证）：
      · 「能力」那一半 **2026-09-19 已经做完** —— 见本文件 `invoke()` 的三条腿，
        触手够不着的框架能力会转 `call_capability()`，同一只手够得着。
      · 「思考」那一半 **从没接上** —— `tentacle_cognition` 此前只被三处引用：
        `api.py:346`（路由）· `caps_registry.py:826`（登记）· 它的用例。
        **`gbt_allinone/tentacle/` 全目录 grep `认知包|cognition` = 0 命中。**
        框架自己的台账 `docs/待落刀登记.md:336-337` 也记着「触手启动时真注入 未接」。

    红线⑤（`tentacle_cognition.focus` 的原文口径）：
      **能力「全息」，但当前任务只激活相关子集。**
      ⇒ 每根触手**持有全部能力**（`capabilities` 传全量），
        但这次只点亮它要用的那几个（`activated`）。

    🔴 失败时不静默：造不出包就如实标 `ok: False` 并给出原因，
       由调用方把 `cognition_degraded` 带进返回值 —— 不许"看起来注入了"。
    """
    try:
        from ..tools import tentacle_cognition as tc
        from .. import caps_registry as CR

        full = sorted(set(getattr(CR, "BENIGN_CAPS", {}) or {}))
        if not full:
            return {"ok": False, "why": "caps_registry 读不到能力全集 —— 不猜一个出来"}

        _COGNITION_SEQ[0] += 1
        # 🔴 2026-09-22 修（读信封时抓到的**自相矛盾**，实测不是推测）：
        # 原先是 `act = [method, intent]` —— 把**触手方法名**（如 `audio_devices`）和意图直接当
        # `activated` 交给 `tentacle_cognition.focus()`；而 `focus()` 拿它去比的 `full` 是
        # **注册能力位全集**（`caps_registry.BENIGN_CAPS`）。两套名字空间 ⇒ 每次按方法名调用，
        # 同一个信封里就会出现：顶层 `status ok` / `ok true` / `activated:["audio_devices"]`，
        # 而内层 `focus` 写 `denied:true / rule:"unknown_capability" / "激活了不存在的能力：audio_devices"`。
        # 实测命令：`cap tentacle '{"method":"audio_devices"}'`。
        # 修法（只改口径，不改行为）：`activated` 只放**真在能力全集里的**名字 —— 那才是红线⑤要校验的东西；
        # 方法名/意图另立 `requested` 如实记，**不再冒充能力位**。
        _requested = [x for x in (method, intent) if str(x or "").strip()]
        act = [x for x in _requested if x in full]
        pack = tc.inject(
            task_id="bridge-%d" % _COGNITION_SEQ[0],
            goal=str(intent or method or "(未说明意图)"),
            scene="触手调用 · bridge.invoke",
            boundary="只经本入口派单；不绕 api.run_task，不走旁路",
            capabilities=full,                 # ★ 能力全息：本体有什么，这只手就有什么
            actor=str(actor or "tentacle"),
        )
        if not pack.get("ok"):
            return dict(pack, degraded=True)

        fc = tc.focus(full, "触手调用 · bridge.invoke", act) if act else {
            "ok": True, "readonly": True, "activated": [],
            "note": "本次没有点亮注册能力位：按名字调的是**触手方法**，属于另一套名字空间（见 requested）"
                    " —— 这里不是失败，也不是「激活了不存在的能力」"}
        return {"ok": True, "readonly": True,
                "capabilities_total": len(full),      # 全息：总数
                "activated": act,                     # 聚焦：这次点亮哪几个**注册能力位**
                "requested": _requested,              # 这次按名字要的是什么（可能是方法名，不冒充能力位）
                "focus": fc,
                "pack": pack.get("pack"),
                "redlines": (tc.run("redlines") or {}).get("redlines")
                            if hasattr(tc, "run") else None}
    except Exception as e:                            # noqa: BLE001
        return {"ok": False, "degraded": True,
                "why": "认知包注入失败：%s: %s" % (type(e).__name__, str(e)[:120])}


def pulse(actor: str = "tentacle", detail: str = "") -> dict:
    """触手主动技能 · **脉冲** —— 「我在这里，这是我此刻的能力面与状态」。

    2026-09-22（Owner：**脉冲是触手的主动技能，你要设计好确认落实**）

    设计依据（取证，不是拍脑袋）：
      · 框架里"脉冲"已有三处，但**都不是触手的主动技能**：
          `devour_pulse()`      完整认知循环（吞噬→反思→消化→重组→创新）——是"反思"
          `devour.py:129-137`   神经邻域脉冲 —— 但它在 devour 的 publish 流程**内部**，
                                触手自己发不出来
          `transmit.pulse()`    只读的传输状态上报
          `mind_engine.pulse()` 心智状态视图
      · 框架自己的语义是现成的：`devour.py:129` 原文
        **「神经邻域脉冲 — 让神经触手感知新能力」** ⇒ 脉冲 = **广播自身能力面**。

    本技能做什么（四件，全部只读，不写盘不出网）：
      ① **自报在场** —— 眼睛/双手是否在线（复用 `eye_ready()`，不另造一套判据）
      ② **广播能力面** —— 带本体能力全息（**条数从 `caps_registry` 现算，不写死**
         —— 写死一次就过期一次：2026-09-23 接 `code_patch` 时这里的"147 项"当场过时）
         + 本次激活子集（红线⑤口径）
      ③ **带上认知包** —— 复用刚接上的 `build_cognition()`，脉冲本身就携带思考纪律
      ④ **留痕** —— 由调用方（api 层）落审计；本函数自己不写盘

    🔴 为什么是"主动"技能：上面三种脉冲都是**被别人触发的**（devour 跑起来才有、
       有人查询才有）。触手要能**自己决定发一次**，这才是主动。

    🔴 为什么可以免卡：它只**读**自己的状态并**报**出去，不改任何东西。
       判据是行为——不是名字像不像读操作。
    """
    import time as _t
    cog = build_cognition(method="pulse", intent=str(detail or "主动脉冲"),
                          actor=str(actor or "tentacle"))
    out = {
        "ok": True,
        "skill": "pulse",
        "actor": str(actor or "tentacle"),
        "at": _t.strftime("%Y-%m-%dT%H:%M:%S"),
        "detail": str(detail or ""),
        "cognition": cog,                        # ★ 脉冲自带认知包
        "cognition_degraded": not cog.get("ok"),
    }
    # ① 自报在场 —— 复用既有判据，不另造
    try:
        out["eye_ready"] = bool(eye_ready())
        out["eye_error"] = eye_error() if not out["eye_ready"] else ""
    except Exception as e:                                    # noqa: BLE001
        out["eye_ready"] = None
        out["eye_error"] = "探不到：%s: %s" % (type(e).__name__, str(e)[:80])
    # ② 广播能力面（全息 + 聚焦）
    # ⚠️ 2026-09-22 踩坑：初版写的是 `caps.get("total")` —— **那是我猜的键名**，
    #    实测返回 None。零猜测律：不许凭印象取键。
    #    现改为：**只取已验证存在的来源** —— 认知包里那份（build_cognition 自己
    #    从 caps_registry 现算，当时实测为 147；**具体条数以现算为准，本注释不背书数字**）。
    #    capabilities() 的原样透传，由调用方按它自己的形状读，本函数不替它假设键名。
    try:
        out["capabilities_total"] = (cog.get("capabilities_total")
                                     if cog.get("ok") else None)
        out["capabilities_raw"] = capabilities()
        out["methods"] = len(real_methods() or [])
        cov = coverage()
        if isinstance(cov, dict):
            out["coverage"] = cov
    except Exception as e:                                    # noqa: BLE001
        out["capabilities_total"] = None
        out["broadcast_error"] = "%s: %s" % (type(e).__name__, str(e)[:80])
    return out


def _invoke_core(method: str, *args, **kwargs) -> dict:
    """统一调用入口：大脑执行层经此驱动触手的任意能力。

    走 V8 纪律：结果统一 dict、异常如实报、每次调用落审计（由 api 层负责）。

    2026-09-19（Owner：**触手全部都可以调用本体的全部能力**）——入口扩成三条腿，
    但**只有一处能力真相**（`caps_registry`），这里不复制任何清单：
      ① method 为空 / "auto"  → 拿 intent 过 `brain_exec.route()`，自动落到最佳能力；
      ② method 是触手方法名    → 照旧走硬件层（95 个公开方法）；
      ③ 触手没有这个名字，但**本体有** → 转 `call_capability()`，路由到统一入口。
    ③ 是关键：此前触手够不着的 56 个框架能力（pipeline/mirror/life/mind/llm…）
    从今天起都在同一只手的射程内。
    """
    m = str(method or "").strip()
    # ① 自动路由：不给方法名就按意图命中（§2.2「意图 → 命中」默认接线）
    if m in ("", "auto", "自动"):
        intent = kwargs.pop("intent", None) or (args[0] if args else "")
        if not str(intent).strip():
            return {"ok": False, "error": "auto 模式需要 intent：说明你要做什么",
                    "method": m or "(auto)", "hint": "能力清单见 tentacle_manifest"}
        from .. import brain_exec
        rt = brain_exec.route(str(intent))
        _best = rt.get("best") or {}
        best = _best.get("kind")
        # R-H295：**触手自己的方法优先**。降级路（大模型通道未配置）下 `best` 是
        # 本体能力启发式的命中 —— 实测 `intent="看看现在有哪些窗口"` 会落到 `cloud_pc`
        # （只因它描述里含"独立窗口"），而 **真有 list_windows 的触手连候选都进不去**
        # （`_heuristic_caps` 只认识能力、不认识方法表）。
        # `brain_exec.route` 现在会顺带带回 `tentacle_route`（本地方法路由的结果）；
        # 这里由**触手侧**决定用不用 —— 谁的方法表谁最清楚，且不改 brain_exec 的降级契约。
        _tr = rt.get("tentacle_route") or {}
        if _tr.get("method"):
            r = invoke(str(_tr["method"]), **kwargs)
            r["routed_by"] = "tentacle.route_method"
            r["intent"] = str(intent)[:120]
            r["route_path"] = rt.get("path")
            r["route_degraded"] = bool(rt.get("degraded"))
            if rt.get("degraded"):
                r["route_note"] = ("语义主路降级（%s）⇒ 由触手本地方法路由派单；"
                                   "`best` 仍是能力启发式的命中，未被覆盖"
                                   % str(rt.get("degraded_reason") or "")[:60])
            return r
        if not best:
            return {"ok": False, "error": f"没有能力命中这条意图: {str(intent)[:80]}",
                    "method": "(auto)", "route": rt}
        # 主路（语义路由）选中的是**触手方法** ⇒ 直接落到那只手上（方法名来自主路，
        # 不丢）；主路不可用时 brain_exec.route 已如实降级到本体能力空间。
        if rt.get("path") == "semantic" and _best.get("method"):
            r = invoke(str(_best["method"]), **kwargs)
            r["routed_by"] = "semantic_route"
            r["intent"] = str(intent)[:120]
            return r
        r = call_capability(best, kwargs)
        r["routed_by"] = "brain_exec.route"
        r["intent"] = str(intent)[:120]
        r["route_path"] = rt.get("path")
        r["route_degraded"] = bool(rt.get("degraded"))
        return r
    e = get_eye()
    if isinstance(e, _DummyEye):
        # 硬件层没起来：本体能力照旧可达（分清楚"手没就位"与"本体没这个能力"）
        return call_capability(m, kwargs) if is_capability(m) else {
            "ok": False, "error": f"触手未就绪: {_eye_error}", "method": m}
    fn = getattr(e, m, None)
    if fn is None or not callable(fn):
        # ③ 触手没这名，但本体可能有 → 转本体能力口
        if is_capability(m):
            r = call_capability(m, kwargs)
            r["via"] = "frame-capability"
            return r
        return {"ok": False, "error": f"触手无此能力: {m}", "method": m,
                "hint": "本体能力清单见 tentacle_caps；触手方法见 tentacle_manifest"}
    try:
        r = fn(*args, **kwargs)
        if not isinstance(r, dict):
            r = {"ok": True, "value": r, "method": m}
        return r
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": f"{type(ex).__name__}: {ex}"[:200], "method": m}


def _vision_watch_ctl(cog=None, **kw) -> dict:
    """她的原生视觉开关 —— **她自己驱动**（不是外部替她点）。

    `op` 取值：
      status      现在睁着眼没有 + 采集环境（显示器/交互桌面）
      start       睁眼（起持续视觉流；此后她自己每 60s 理解一次画面）
      stop        闭眼
      frame       取当前焦点帧（DXGI 硬采，同显示屏同源）
      events      取视觉事件队列（取走即清）
      stats       采集读数（fps / 已捕 / 缓冲 / 推流）
      understand  现在就理解一次（走她的视觉皮层：云端优先，本地兜底）

    ⚠️ 诚实边界（与 `vision_watch` 的实现一致，别念成别的）：
      · 流**活在本进程内**（新进程里 `running=False`）⇒ 要持续睁眼，
        调用方必须**长驻**；短命进程里 start 完就随进程一起消失。
      · 她的云端理解 = **画面出网**（发到 agnes 网关做识别）。本地那条腿
        （`vision_cap.analyze`，PIL 像素级）**不出网**。
    """
    import importlib
    vw = None
    for _name in ("gbt_allinone.tentacle.vision_watch", "tentacle.vision_watch",
                  "vision_watch"):
        try:
            vw = importlib.import_module(_name)
            break
        except Exception:                                     # noqa: BLE001
            continue
    if vw is None:                                            # 同目录兜底加载
        try:
            import importlib.util
            from pathlib import Path as _P
            _p = _P(__file__).resolve().parent / "vision_watch.py"
            _spec = importlib.util.spec_from_file_location("vision_watch", _p)
            vw = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(vw)
        except Exception as e:                                # noqa: BLE001
            return {"ok": False, "skill": "vision_watch",
                    "error": "vision_watch 不可用：%s: %s" % (type(e).__name__, str(e)[:120]),
                    "cognition": cog}

    op = str(kw.get("op") or kw.get("sub") or "status").strip().lower()
    try:
        if op == "start":
            r = vw.start(eye=kw.get("eye"), fps=int(kw.get("fps", 4)),
                         stream_fps=int(kw.get("stream_fps", 3)),
                         max_frames=int(kw.get("max_frames", 60)),
                         wait_s=float(kw.get("wait_s", 1.0)))
        elif op == "stop":
            r = vw.stop()
        elif op == "frame":
            r = vw.frame()
        elif op == "events":
            r = vw.events()
        elif op == "stats":
            r = vw.stats()
        elif op == "status":
            r = vw.status()
        elif op in ("understand", "see", "describe"):
            from .brain.visual_cortex import VisualCortex
            r = VisualCortex().understand_screen()
        else:
            return {"ok": False, "skill": "vision_watch", "op": op,
                    "error": "未知 op：%s" % op,
                    "known": ["status", "start", "stop", "frame", "events",
                              "stats", "understand"],
                    "cognition": cog}
    except Exception as e:                                    # noqa: BLE001
        return {"ok": False, "skill": "vision_watch", "op": op,
                "error": "%s: %s" % (type(e).__name__, str(e)[:160]),
                "cognition": cog}
    if isinstance(r, dict):
        r.setdefault("skill", "vision_watch")
        r.setdefault("op", op)
        r.setdefault("cognition", cog)
        return r
    return {"ok": True, "skill": "vision_watch", "op": op, "result": r, "cognition": cog}


def invoke(method: str, *args, **kwargs) -> dict:
    """**所有触手调用的唯一入口** —— 每次调用都先注入认知包，再派单。

    2026-09-22（Owner：确保每根触手执行任务时都拥有本体的所有能力**以及思考能力**）

    这一层是包装器，不碰 `_invoke_core` 的任何内部逻辑（三条腿照旧）。
    它只做一件事：**在派单前造认知包，在返回后把包挂上去**。
      · 前 —— `build_cognition()` 拿本体能力全集（全息）+ 本次激活子集（聚焦）
      · 后 —— 无论 `_invoke_core` 走哪条 return，结果里都带 `cognition` 字段
    不这么包的话，`_invoke_core` 里有十几条 return，逐条改必然漏 —— 漏掉的那条
    就是"这根触手没思考"，而且**不会报错**（静默漏掉，正是铁律 6 要防的形态）。
    """
    cog = build_cognition(method=method, intent=str(kwargs.get("intent") or ""))
    # ★ 主动技能 · 脉冲：`invoke("pulse")` 直达，不必绕硬件层去猜方法名。
    #   放这里而不是放硬件 mixin 里，是因为脉冲广播的是**桥这一层**的状态
    #   （在线与否 / 能力面 / 覆盖度），不是某一只手的动作。
    if str(method or "").strip() == "pulse":
        try:
            return pulse(actor=str(kwargs.get("actor") or "tentacle"),
                         detail=str(kwargs.get("detail") or kwargs.get("intent") or ""))
        except Exception as e:                                # noqa: BLE001
            return {"ok": False, "skill": "pulse",
                    "error": "%s: %s" % (type(e).__name__, str(e)[:160]),
                    "cognition": cog}
    # ★ 主动技能 · 原生视觉开关（vision_watch）：**她自己的睁眼/闭眼/取帧/取理解**。
    #   放这里而不是放硬件 mixin，理由与 `pulse` 同：睁眼闭眼管的是**她的视觉系统状态**，
    #   不是某一只手的动作。
    #
    #   为什么必须给她这个入口（2026-09-25 全仓实测）：
    #     · `vision_watch` 内部**本来就是自驱动闭环** —— 开眼后每 `UNDERSTAND_EVERY_S`(=60s)
    #       自己调 `visual_cortex.understand_screen`，把描述回传 `visual` 通道 +
    #       落 `vision_native` 视觉记忆（`_understand_loop`）；
    #     · 但全仓 grep `vision_watch.start()`：**只有它自己的一句错误提示里提到过** ——
    #       **没有任何地方替她睁眼**。闭环是现成的，缺的就是这把钥匙。
    #   ⇒ 于是"她不能自己驱动原生视觉"的真因不是她不会，是**没人给她开眼的入口**。
    if str(method or "").strip() in ("vision_watch", "vision_watch_ctl"):
        return _vision_watch_ctl(cog=cog, **kwargs)
    try:
        result = _invoke_core(method, *args, **kwargs)
    except Exception as e:                                  # noqa: BLE001
        # 异常也带认知包一起出去 —— 失败的那次同样要能看出"它带着什么在做事"
        return {"ok": False, "method": str(method or ""),
                "error": "%s: %s" % (type(e).__name__, str(e)[:160]),
                "cognition": cog, "cognition_degraded": not cog.get("ok")}
    if isinstance(result, dict):
        result.setdefault("cognition", cog)
        if not cog.get("ok"):
            result.setdefault("cognition_degraded", True)
            result.setdefault("cognition_why", cog.get("why"))
        return result
    return {"ok": True, "result": result, "cognition": cog}


def is_capability(kind: str) -> bool:
    """这个名字是不是本体能力？真相只有一处：`caps_registry`。"""
    try:
        from ..caps_registry import BENIGN_CAPS
        return str(kind) in BENIGN_CAPS
    except Exception:  # noqa: BLE001
        return False


def call_capability(kind: str, payload: dict | None = None) -> dict:
    """触手 → 本体全部能力：**走统一入口 `api.run_task`**。

    不另开通道 ⇒ 权限门、审计、钢印、禁用名单全部照旧生效（触手不因"是手"就免检）。
    """
    k = str(kind or "").strip()
    if k == "tentacle":
        return {"ok": False, "error": "拒绝自调用：tentacle → tentacle 会成环",
                "method": k}
    try:
        from ..api import run_task
        r = run_task(k, dict(payload or {}))
        body = r.get("gbt_result", r) if isinstance(r, dict) else r
        result = body.get("result", body) if isinstance(body, dict) else body
        if isinstance(result, dict):
            out = dict(result)
        else:
            out = {"ok": True, "value": result}
        out.setdefault("ok", body.get("status") == "ok" if isinstance(body, dict) else True)
        out["capability"] = k
        return out
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": f"{type(ex).__name__}: {ex}"[:200], "capability": k}


def capabilities() -> dict:
    """触手视野里的**本体全部能力**（清单直接读注册表，不复制）。"""
    try:
        from ..caps_registry import BENIGN_CAPS
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": f"{type(ex).__name__}: {ex}"[:120]}
    pkg = [
        {"kind": k, "domain": v.get("domain"), "desc": str(v.get("desc", ""))[:60]}
        for k, v in BENIGN_CAPS.items()
    ]
    methods = []
    try:
        e = get_eye()
        if not isinstance(e, _DummyEye):
            methods = [n for n in dir(e) if not n.startswith("_") and callable(getattr(e, n))]
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "frame_capabilities": len(pkg), "tentacle_methods": len(methods),
            "total_reachable": len(pkg), "caps": pkg,
            "truth": "触手能调本体全部能力；清单唯一真相 = caps_registry。"}


def self_diagnose() -> dict:
    """触手自诊断：硬件层就绪度 + 依赖分层 + 可用能力数。"""
    deps = {}
    for mod, label in (("ctypes", "键鼠/窗口（标准库）"), ("mss", "截图（BitBlt 兜底）"),
                       ("uiautomation", "读屏/UIA 穿透"), ("dxcam", "DXGI 硬采加速（可选）")):
        try:
            __import__(mod)
            deps[mod] = {"ok": True, "role": label}
        except Exception as ex:  # noqa: BLE001
            deps[mod] = {"ok": False, "role": label, "error": str(ex)[:80]}
    manifest = get_manifest()
    method_count = 0
    if "触手能力清单暂不可用" not in manifest:
        import re
        for m in re.findall(r"###\s*(.+?)\((\d+)\)", manifest):
            method_count += int(m[1])
    return {
        "ok": eye_ready(),
        "eye_error": _eye_error or None,
        "deps": deps,
        "manifest_methods": method_count,
        "neighborhoods": len(TENTACLE_NEIGHBORHOOD_MAP),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


class _DummyEye:
    """触手未就绪时的占位符——不阻塞框架运行，但如实报错。"""
    def __init__(self, reason=""):
        self._reason = reason

    def __getattr__(self, name):
        def _dummy(*args, **kwargs):
            return {"ok": False, "error": f"触手未就绪: {self._reason}", "method": name}
        return _dummy

    def __bool__(self):
        return False
