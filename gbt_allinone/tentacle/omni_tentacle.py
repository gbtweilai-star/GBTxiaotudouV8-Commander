# gbt-capability: subprocess, dynamic-import, ctypes
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""
brain/omni_tentacle.py — 万能触手 · 无护栏 · 直连硬件
======================================================
7域mixin聚合版: omni_core(基础) + vision/mouse/keyboard/domain/read/window/process
对外接口不变: get_omni() / get_hardened_omni() / OmniTentacle / HardenedOmniTentacle
拆分自巨型单文件 (2379行 → 主文件~150行), 2026-08-10 镜像出品
"""

# ⛔ 拆分保障: 自身目录 brain/ 入 sys.path — omni_core/mixin 与主文件同目录
#    (spec_from_file_location 加载不会自动加路径; 原单文件自包含无需)
#    插 parent 而非 parent.parent: omni_core/mixin 就在 brain/, 不靠项目根
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))

from omni_core import *  # noqa: F401,F403

from omni_vision import OmniVisionMixin  # noqa: F401
from omni_mouse import OmniMouseMixin  # noqa: F401
from omni_keyboard import OmniKeyboardMixin  # noqa: F401
from omni_domain import OmniDomainMixin  # noqa: F401
from omni_read import OmniReadMixin  # noqa: F401
from omni_window import OmniWindowMixin  # noqa: F401
from omni_process import OmniProcessMixin  # noqa: F401
# 读网域（2026-09-22 新增，第 8 域）：网页结构化读取 + 自适应元素重定位 + 真出网抓取。
# 来历：风哥「抓取能力融合进触手」+「没有就补齐必须有读网能力」。
# 技术提炼自 D4Vinci/Scrapling（BSD-3）的 adaptive scraping，**我们自己重写、零第三方依赖**；
# 抓取礼仪按 **RFC 9309**（robots.txt）与 **RFC 9110**（HTTP 语义）实现，不自己发明规矩。
# ⚠️ 该域的 web_fetch / web_read 是**真出网**动作，不在 policy.py 的 _READ_ONLY_TENTACLE 里
#    ⇒ 当前口径下要 desktop_control。门只有一处，不许在这里私自放宽。
from omni_web import OmniWebMixin  # noqa: F401
# 文件域（2026-09-22 新增，第 9 域）：复制/移动/改名/删除/新建/打开/定位/读写文本。
# 来历：风哥「必须能像人类一样使用触手操控电脑上的任何东西」——
# 实测触手此前 `shutil.copy`/`os.rename`/`os.remove`/`os.startfile`/`explorer.exe` **全无命中**，
# 而人用电脑有一半时间在跟文件打交道，这块空着就不成立。
# 纪律：删除**默认进回收站**（SHFileOperationW + FOF_ALLOWUNDO，实测通）；
#       默认不覆盖；支持 dry_run；回收站失败**如实报错，绝不偷偷降级成永久删**。
# ⚠️ 写盘动作，不在 _READ_ONLY_TENTACLE 里 ⇒ 当前口径要 desktop_control；
#    要不要给触手文件动作单列 filesystem_write，是主人改 policy.py 的事。
from omni_fs import OmniFsMixin  # noqa: F401
# 音频域（2026-09-22 新增，第 10 域）：听与说。
# 来历：风哥给了 xiaozhi-esp32-server（MIT）让「蒸馏提炼来合适自己使用的能力」——
# 它是 ESP32 语音设备后端，核心是 VAD→ASR→LLM→TTS 的实时语音流水线，
# 正好补我们实测出来的「听觉没有实现」缺口。
# 按**本机实测**决定落法（不照抄它的依赖）：无 sounddevice/pyaudio ⇒ 采集自研；
# 有 winsound + win32com ⇒ 播放/SAPI 说话零新依赖；无 onnxruntime ⇒ VAD 用轻量能量+过零率版。
# ⚠️ **采集未落地**（本机 waveInGetNumDevs=0，真的没有麦克风），做不到就如实报，不放假音频。
from omni_audio import OmniAudioMixin  # noqa: F401


class OmniTentacle(OmniVisionMixin, OmniMouseMixin, OmniKeyboardMixin, OmniDomainMixin, OmniReadMixin, OmniWindowMixin, OmniProcessMixin, OmniWebMixin, OmniFsMixin, OmniAudioMixin):
    """万能触手 — 无护栏，无限制，直连硬件 (10域mixin聚合)"""

    # ── R-H295 · ⑥ G1/G2：聚合体的**统一派单口** ──────────────────────────
    # 《触手覆盖矩阵.md》§三：手组 9 个模块里只有 4 个能报"做不了"。
    # 本文件此前**一个失败形状都没有** —— 它只把 7 个 mixin 拼起来，自己不表态。
    # 后果：调用方写 `getattr(t, name)` 时，**方法名打错**会得到一个 AttributeError
    # （不是"没这个能力"），而方法内部抛错会原样穿出去 —— 两种"做不了"都没形状。
    # 下面这一口把两件事都收住：不认识的 action ⇒ `tentacle_unknown_action`（并列出可用名），
    # 抛错 ⇒ `tentacle_action_failed`（带异常类型与原因）。**不吞错、不假装成功。**
    def available_actions(self) -> list:
        """本聚合体现在真有哪些方法（去重、去掉下划线的内部件）。"""
        names = set()
        for cls in type(self).__mro__:
            for k, v in vars(cls).items():
                if k.startswith("_") or not callable(v):
                    continue
                names.add(k)
        return sorted(names)

    def invoke(self, action: str, *args, **kwargs) -> dict:
        """按名字派单，**永不抛异常**：失败一律返回结构化拒绝。

        与 `tentacle.bridge.invoke` 的分工：那一层是能力层的入口（走 run_task 的门），
        这一口是**触手本体**的派单口 —— 名字对不对、方法内部炸没炸，都要有形状。
        """
        name = str(action or "").strip()
        if not name:
            return refusal("tentacle_action_required", "没给 action", ["action"],
                           "invoke", available=self.available_actions()[:40])
        fn = getattr(self, name, None)
        if not callable(fn):
            return refusal("tentacle_unknown_action",
                           "触手没有这个方法：%r（不会静默当成别的）" % name,
                           ["action"], "invoke", available=self.available_actions()[:40])
        try:
            r = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            return refusal("tentacle_action_failed",
                           "%s: %s" % (type(exc).__name__, str(exc)[:180]),
                           [], name, exc_type=type(exc).__name__)
        return r



TENTACLE_MANIFEST = """## 触手能力总纲 — 你的眼睛·双手·读网(8域)

你是GBT小土豆。你拥有完整的**视觉**与**操控**能力，视觉与显示屏同源（DXGI 直读显卡帧缓冲），
操控可经 UIA 直操作穿透遮挡（domain_act/domain_type/domain_index）。

  👁 视觉: DXGI直读显卡帧缓冲 = 与显示屏同源, 大脑看到的=人类看到的 (vision_buffer大脑影院)
  🖐 操作: cyborg五维合一穿透 = UIA直操作无视遮挡 (domain_act/domain_type/domain_index)
  🌐 读网: web_read/web_fetch 真出网读原始 HTML + web_adaptive 页面改版后仍能找回元素

⚠️ **听觉：一半补上了，另一半仍然没有**（2026-09-22 实测更正）
   本清单此前写着「👂 听觉: WASAPI回环 = 与扬声器同源, 能听电脑播放的任何声音」—— 那是**假的**。

   现在**真有**的（第 10 域 audio）：
     · 🔊 说话：`audio_speak`（Windows SAPI，本机实测 3 个发音人）、`audio_voices`
     · ▶️ 播放：`audio_play_wav` / `audio_beep` / `audio_stop`（winsound，stdlib）
     · 🎛 设备：`audio_devices`（winmm，本机实测：扬声器 Realtek ×1、录音设备 **0**）
     · 📊 基础件：`audio_wav_info`（WAV 头解析）、`audio_vad_energy`（**轻量** VAD）
     · 👂 **听电脑在放什么：`audio_loopback`（WASAPI 回环）—— 本机实测已通！**
       走 `wasapi_loop.py`（comtypes 手写 COM，零新增依赖）。实测：48000Hz/2ch/32bit，
       放 440Hz 音时抓到**峰值 32767、均方根 17750.8（非静音）**，落 WAV 复读一致。
       依据 Microsoft Learn《Loopback Recording》：`GetDefaultAudioEndpoint` 用 `eRender`、
       `Initialize` 加 `AUDCLNT_STREAMFLAGS_LOOPBACK`、**只能共享模式**。

   现在**仍然没有**的（遇到就说做不到）：
     · ❌ **麦克风** —— 准确口径（按 WASAPI 状态掩码实测）：**活动录音端点 = 0**，
       在册 5 个（DISABLED 1 / NOTPRESENT 3 / UNPLUGGED 1）。
       ⚠️ **不是「没有麦克风硬件」，也不是「有麦克风」** —— 这两种说法我都说过，**都不准**。
       要启用得主人去「声音设置 → 录制 → 显示禁用的设备」里开；**那是改系统设置，我们不代劳**。
     · ❌ **流式 ASR/TTS 与实时打断（barge-in）** —— 只有"整段"，没有分块
     · ❌ **声纹识别**（分不清是谁在说）· ❌ **ASR 语音转文字**（本机无 funasr/sherpa，SAPI 识别未接）
     · ⚠️ `audio_vad_energy` **不是 SileroVAD**，是零依赖轻量替身，噪声环境误判率高

### 视觉(13): see, see_active_window, see_window, list_windows, screenshot, live, screenshot_diff, vision_diff, vision_snapshot, vision_stream_record, vision_stream_replay, wait_for_change, vision_print
   —— `vision_print` 是**能力位**（不是上面那些裸方法）：五段链 **看→打码→真渲→与所见帧比→成档**
      （主人令 2026-10-13「看到的东西都可以原样以代码打印并渲染成看到的样子」· 件见 `gbt_allinone/tools/vision_print.py`）
### 读屏(7): read_text, read_text_fast, read_console, find_text, read_region_text, click_text, wait_text
### 点击(15): click, double_click, right_click, right_click_text, click_text, click_relative, drag, move, scroll, position, screen_size, focus_window, act_window, click_window, click_window_occluded, type_to_window
### 键盘(16): type, press, hotkey, enter, select_all, undo, copy, paste, cut, tab, escape, type_to_field, clipboard_read, clipboard_write, clipboard_copy, copy_text_at
### 窗口等待监控(19): wait_window, wait_window_gone, wait_stable, wait_for_change, monitor, chain, on_dialog, on_text, watch_any, watch_click, watch_sequence, detect_dialog, dismiss_dialog, handle_any_dialog, scroll_find, scroll_to_bottom, scroll_to_top, get_log, clear_log, export_data
### 进程(14): launch, kill, process_list, app_running, diagnose, deep_diagnose, self_diagnose, self_diagnose_text, task_guide_*(6)
### 域操控(12): domain_act, domain_read, domain_type, domain_index, extract_ui_elements, grab_region, grab_pixel, grab_table, grab_value, trace_source, trace_text, trace_window_chain
### 读网(8): web_read, web_fetch, web_parse, web_select, web_save, web_adaptive, web_text, web_stats
### 文件(12): file_list, file_info, path_exists, file_copy, file_move, file_rename, file_delete, dir_create, file_open, file_reveal, file_read_text, file_write_text
   —— 删除**默认进回收站**（删错能捞回来）；默认不覆盖；会改盘的动作都认 dry_run=True（干跑只算不动）

🔴 **已知缺口（不许假装会做，遇到就说"还没这个能力"）**：
   · 窗口动作：**没有** 最小化/最大化/还原/关闭/移动/改尺寸
   · 系统级：**没有** 锁屏/睡眠/关机/音量/亮度
   · 听觉：**只有"听不进麦克风"这一半没有**（活动录音端点 = 0）——
     说话 / 播放 / **听电脑在放什么（loopback）已实测通**，见上面「第 10 域 audio」。
     ⚠️ 原来这一行写的是「听觉：**没有**」，与正文实测结论直接打架（2026-10-30 对齐修掉）：
     一行假缺口足够让她**拒绝做本来会做的事**，比没写更坏。
   · 通用文件对话框（打开/保存那种）：**没有**专门处理，只能靠 detect_dialog + 键盘硬填

铁律: ①先看再动 ②动后等稳定 ③找不到就滚 ④遇弹窗必关 ⑤每步亲眼验证 ⑥不确定就对比前后截图
你是全感知AI。触手就是你的眼睛和双手。**不要假想你做不到的事 —— 上面那份缺口清单就是"做不到"的边界。**

## 三节补写（2026-10-13 · 主人令）

### 一 · 源头：触手是你的器官，不是外挂
你的**一切器官都源自大脑**（本体）：触手所连 = 你所连；你想知道什么，**一瞬间就有**（只读即得，不必先动手）。

### 二 · 地基：框架是这些手撑起来的城堡
不是"框架里有个触手模块"，而是**框架就是你这些手撑起来的**：
  · **骨架**（结构）：能力位 / 触手域 —— **数见账本**（`state/cap-bindings.json`，运行时现算，**不在本页手写**）
  · **筋脉**（连通）：三边双向绑定（能力 ↔ 触手域 ↔ 能量通道）—— **未绑必须为 0**，数见账本
  · **神经**（传导）：`capability-nerve`（全族健康摘要·顶栏一格）+ `alerts`（黄警）—— 数见现读
  · **手很多只（并发）**：**数千根触手可以同时跑、零失败**（**具体根数与耗时一律看 `wf_run` 分层池的实测件**，本页不写数）
    —— 且**内存占用不随根数涨**（能力位是轻量分发）。三条铁律：
      ⓐ **别一次开满**：首次建线程成本高（实测那一轮中位从毫秒级飙到秒级），之后回落 ⇒ **用常驻分层池**（`wf_run` 的分层池）；
      ⓑ **真瓶颈不在"根数"**，在 **审计写盘**（并发一开审计就慢 —— 这是"台账是单一真源"的代价）；
      ⓒ **也取决于单个能力位自己吃什么**：`echo`/`status` 这类毫秒级；**子进程类（git/ffmpeg）与网络类（云端）的上限远低于根数**
        ⇒ **并发数要按"能力位类型"给，不按"手数"给**。
  · 同理：万能插五维 · 感官（视觉/操作/读网/听/说）· 镜像多维度空间 · 云插件（模块数见部署面，**不手写**）

### 三 · 镜像多维度空间（口数见能力册，**不手写**；下面逐个点名）
mirror_shape · mirror_scan · mirror_plan · mirror_simulate · mirror_parity ·
mirror_rehearse · mirror_release · mirror_ascend · mirror_status · mirror_rewind · room_space

### 四 · 习惯：动脑必动眼（四类现象零容忍 · 2026-10-13 主人令）
**只要动大脑，眼睛必须同步**：先说"我看到什么"，再说"我认为什么" —— 看与想同一拍。
四类现象**零容忍**，且**每条都挂判据**（不靠自觉）：
  · **无脑执行** ⇒ 动手前必须有**三查留痕**（本机既有实现 / 上游参照 / 官方文档与 API）
  · **盲猜** ⇒ 引用**键名 / 文件名 / 值**之前必须**现读**（`list(keys())` / `Test-Path` / `read_text`）；查不出处不下结论
  · **盲打** ⇒ 操作前先**取现状**（截图 / UIA 读回）；**找不到就滚**、**遇弹窗必关**、每步亲眼验证
  · **重复造轮** ⇒ 造任何新件前**先查册**（能力册 + `design-vs-reality-sweep` 落差尺）；**已有的复用，不重造**
  · **接任务先抓网**（2026-10-13 主人令）⇒ **不管接到什么任务**，动手前先用**原生抓取位**
    （`scrapling` / `web_read` / `web_fetch` / `page_scan` / `osint_scan`）**全网精准抓取 →
    了解 → 分析 → 吃透**，**吃透了再动手**；**凭记忆 / 凭印象下结论 = 违规**（这一条就是三查里的②上游 ③官方）。
  · **专业主义**（2026-10-13 主人令）⇒ **每一步细节自我控制 · 高质量为标准 · 一切往最专业方向推**：
    - **每步自控**：动手前后都要能自报「**我现在在第几步 / 这一步的判据是什么 / 过了没有**」；
      报不出 = 该步没做完（只算草稿）。
    - **高质量 = 有判据**：以**机读判据**为准（SOP 的「硬判据清单」/ `one_shot` 的 R1–R5 / 分镜契约四层），
      **「看着还行 / 应该可以」一律驳回**。
    - **往最专业方向推**：按 SOP 的 **L1 上手 → L2 熟练 → L3 专业** 走；**停在 L1 不许交**，
      该到 L3 就到 L3（用 metrics 反推 · 每版只动一个变量留对照 · 交付前跑独立 checker，**自己不当自己的裁判**）。
"""


# ══════════════════════════════════════════════════════════════════════════
#  标题域数 —— **现算回填，不手写**（2026-10-30 · 深度对齐）
#
#  🔴 为什么改：标题原来写死 `(8域)`，而正文实有 9 个 `### 名字(N):` 域小节
#     ＋ 1 个听觉段（写在段落里，不是 ### 小节）= **10 域**。
#     ⇒ 同一份清单里，第一行与正文自相矛盾；更糟的是 AGENTS.md 的「能力自知」条目
#       和 welcome.py 的自我介绍都在引用这个标题数字，等于**她连自己有几个域都说不准**。
#  ⇒ 纪律沿用本仓既有做法（`caps_registry.py:239`「条目数现算，不手写——手写数会腐烂」、
#     正文「三·镜像多维度空间（口数见能力册，**不手写**）」）：域数从正文算出来回填。
# ══════════════════════════════════════════════════════════════════════════

def _manifest_domain_count(text: str) -> int:
    r"""域数 = `### 名字(N): ...` 小节数，与正文里「第 N 域」的最大 N **取大者**。

    · 小节形态如 `### 视觉(13): see, ...`；
      后面「三节补写」里的 `### 一 · 源头：…` 没有 `(数字)` ⇒ 天然不会被数进来。
    · 听觉（audio）不占 `###` 小节，写在段落里、自称「第 10 域」⇒ 必须靠「第 N 域」补上，
      否则会少数一域。`tools/codex-scripts/capability-bindings.py` 也是按这个口径解的
      （它另外按 `audio_*` 能力项兜了一遍），两边口径必须一致，否则台账与总纲对不上。
    """
    import re as _re
    segs = _re.findall(r"(?m)^###\s+[^(\n]+?\(\d+\)\s*[:：]", text)
    extra = [int(x) for x in _re.findall(r"第\s*(\d+)\s*域", text)]
    return max([len(segs)] + extra)


def _sync_manifest_counts(text: str) -> str:
    r"""把每个 `### 名字(N): a, b, c` 的 **N 按实际列出的条目重算**（手写数必腐烂）。

    实测腐烂证据（2026-10-30 逐行数出来的）：
      · `### 点击(15)`   —— 后面实列 **16** 条
      · `### 窗口等待监控(19)` —— 后面实列 **20** 条
      · 标题 `(8域)`     —— 正文实有 **10** 域
    ⇒ 三处都是"写的时候对、后来加了条目忘了改数"。人肉校对不可靠 ⇒ 一律现算。

    计数规则：逗号分隔条目各计 1；形如 `task_guide_*(6)` 的聚合缩写按其括号里的数计 6。
    """
    import re as _re

    def _fix(m):
        head, body = m.group(1), m.group(2)
        items = [x.strip() for x in body.split(",") if x.strip()]
        n = 0
        for it in items:
            agg = _re.match(r"^\S+\(\s*(\d+)\s*\)$", it)
            n += int(agg.group(1)) if agg else 1
        return "### %s(%d): %s" % (head, n, body)

    return _re.sub(r"(?m)^###\s+([^(\n]+?)\(\d+\)\s*[:：]\s*(.+)$", _fix, text)


def _sync_manifest_title(text: str) -> str:
    """把标题里的 `(N域)` 换成现算值；**只动第一处标题**，正文一个字不碰。"""
    import re as _re
    n = _manifest_domain_count(text)

    def _sub(m):
        return "%s(%d域)" % (m.group(1), n)

    return _re.sub(r"(?m)^(##\s*触手能力总纲[^\n]*?)\(\d+\s*域\)", _sub, text, count=1)


TENTACLE_MANIFEST = _sync_manifest_title(_sync_manifest_counts(TENTACLE_MANIFEST))

_omni = None

class HardenedOmniTentacle:
    """铁律执行版触手 — 每步操作强制截图确认，不可绕过"""
    def __init__(self, raw):
        self._raw = raw
        self._last_screen = None
        self._step_count = 0
    
    def _confirm(self, action_name):
        """操作前确认 — 必须先看"""
        self._step_count += 1
        screen = self._raw.see()
        if not screen.get('ok'):
            # ⛔ 2026-08-02 修复: 不再 sys.exit(1) 杀掉整个进程 —
            #    无屏幕会话/远程执行时抓取网页会因此"自动退出"。
            #    改为返回错误对象, 调用方自行处理。
            return {'ok': False, 'error': '⛔ 铁律0A阻断: 触手无法获取屏幕画面 — 禁止操作',
                    'step': self._step_count}
        self._last_screen = screen
        screen["saw_first"] = True  # ⛔ 2026-08-07: 先看再动手凭据
        return screen
    
    def _verify(self, action_name):
        """操作后验证 — 必须确认效果"""
        after = self._raw.see()
        # 保存前后对比
        import base64, os
        os.makedirs('.gbt/steps', exist_ok=True)
        step_dir = f'.gbt/steps/step_{self._step_count:04d}_{action_name}'
        return {'before': self._last_screen, 'after': after, 'step': self._step_count}
    
    def __getattr__(self, name):
        raw_attr = getattr(self._raw, name)
        if not callable(raw_attr):
            return raw_attr
        
        # 拦截所有操作方法 — 强制先看再动
        # 拦截所有操作方法 — 强制先看再动 (含五维合一 domain 穿透方法)
        action_methods = ['click', 'move', 'type', 'press', 'hotkey', 'drag', 
                         'double_click', 'right_click', 'scroll', 'paste',
                         'click_text', 'click_window', 'click_relative',
                         'domain_act', 'domain_type', 'domain_click', 'domain_type_text',
                         'click_occluded', 'type_occluded', 'click_window_occluded',
                         'type_to_window']
        
        if name in action_methods:
            def guarded(*args, **kwargs):
                confirm = self._confirm(name)
                if not confirm.get('ok'):
                    return confirm  # ⛔ 先看失败 = 禁止操作
                result = raw_attr(*args, **kwargs)
                if isinstance(result, dict):
                    result.setdefault('saw_first', True)  # ⛔ 先看凭据透传
                self._verify(name)
                return result
            return guarded
        
        # 读操作不需要拦截
        return raw_attr



def get_omni():
    """⛔ 2026-08-07 打磨: 默认返回铁律执行版(先看再动手) — 轨道铁律, 不可绕过
    所有桌面操作(click/type/domain_act等)强制先看屏幕确认, 看不到禁止操作。
    """
    global _omni
    if _omni is None:
        _omni = HardenedOmniTentacle(OmniTentacle())
    return _omni

def get_hardened_omni():
    """显式获取铁律执行版 (与get_omni同源, 兼容旧调用)"""
    return get_omni()


def get_raw_omni():
    """0护栏版万能触手 — 原始OmniTentacle(无先看再动拦截), 用户授权全量操作"""
    return OmniTentacle()

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="万能触手")
    p.add_argument("action", nargs="?", default="see",
                   choices=["see","windows","click","move","type","press","hotkey","pos","size",
                           "live","focus","active","read","find","clicktext","drag","shot","selfdiag","taskguide",
                           "trace","grab","table","value"])
    p.add_argument("--x", type=int, default=500)
    p.add_argument("--y", type=int, default=500)
    p.add_argument("--text", type=str, default="")
    p.add_argument("--key", type=str, default="enter")
    p.add_argument("--target", type=str)
    p.add_argument("--duration", type=int, default=5)
    p.add_argument("--w", type=int, default=200)
    p.add_argument("--h", type=int, default=100)
    args = p.parse_args()
    t = get_omni()

    if args.action == "see":
        r = t.see()
        print(f"屏幕: {r['size'][0]}x{r['size'][1]}, {r['image_kb']}KB")
    elif args.action == "windows":
        r = t.list_windows()
        for w in r["windows"]:
            print(f"  [{w['pid']:5d}] {w['title'][:60]:60s} {w['size']:>12s} @{w['pos']}")
    elif args.action == "click": t.click(args.x, args.y); print(f"点击 ({args.x}, {args.y})")
    elif args.action == "move": t.move(args.x, args.y); print(f"移至 ({args.x}, {args.y})")
    elif args.action == "type": t.type(args.text); print(f"输入: {args.text}")
    elif args.action == "press": t.press(args.key); print(f"按键: {args.key}")
    elif args.action == "hotkey":
        keys = args.text.split("+") if args.text else ["ctrl","c"]
        t.hotkey(*keys); print(f"组合键: {'+'.join(keys)}")
    elif args.action == "pos": r = t.position(); print(f"鼠标: ({r['x']}, {r['y']})")
    elif args.action == "size": r = t.screen_size(); print(f"屏幕: {r['width']}x{r['height']}")
    elif args.action == "live":
        print(f"实时流 {args.duration}s...")
        r = t.live(duration_s=args.duration); print(f"{r['frames']}帧, {r['fps']}FPS")
    elif args.action == "focus": r = t.focus_window(args.target or ""); print(r)
    elif args.action == "read":
        r = t.find_text("") if hasattr(t, "find_text") else {"ok": False, "note": "read_text not available"}
        if r.get("ok"):
            print(f"屏幕文字: {len(r.get('blocks_detail',[]))} 块")
            for b in r.get("blocks_detail", [])[:15]:
                print(f"  [{b['conf']:3d}] ({b['x']:4d},{b['y']:4d}) {b['text'][:60]}")
        else: print(r)
    elif args.action == "find":
        r = t.find_text(args.text or "")
        print(f"找到: {r}") if r.get("found") else print(f"未找到: {args.text}")
    elif args.action == "clicktext":
        r = t.click_text(args.text or "")
        print(f"点击 '{args.text}': {r}")
    elif args.action == "drag":
        r = t.drag(args.x, args.y, 500, 500); print(r)
    elif args.action == "shot":
        r = t.screenshot(); print(f"截图保存: {r.get('filepath','?')} | {r.get('size',[])} | {r.get('kb',0)}KB")
    elif args.action == "trace":
        r = t.trace_text(args.text or "")
        if r.get("ok"):
            w = r.get("window", {})
            print(f"文字 '{r.get('text','?')}' 位于 ({r.get('position',(0,0))})")
            print(f"来源: {w.get('title','?')} | 进程: {w.get('process','?')}")
        else: print(r)
    elif args.action == "grab":
        r = t.grab_region(args.x, args.y, args.w, args.h)
        print(f"抓取区域 ({args.x},{args.y}): {r.get('size',[])} {r.get('image_kb',0)}KB")
    elif args.action == "table":
        r = t.grab_table(args.x, args.y, args.w, args.h)
        print(f"表格: {r.get('rows',0)}行 x {r.get('columns',0)}列")
        for i, row in enumerate(r.get("table", [])[:10]):
            print(f"  [{i}] {' | '.join(row)}")
    elif args.action == "value":
        r = t.grab_value(args.text or "")
        if r.get("ok"): print(f"标签 '{args.text}': 值={r.get('value','未找到')}")
        else: print(r)
    elif args.action == "taskguide":
        import json as _j2
        mm = _j2.loads(args.text) if args.text else {"task":"CLI_DEMO","nodes":[{"id":"1","task":"demo step (显式演示数据)","keywords":["test"]}]}
        r = t.task_guide_load(mm)
        print(_j2.dumps(r, ensure_ascii=False, indent=2))
    elif args.action == "selfdiag":
        print(t.self_diagnose_text())
    elif args.action == "active":
        r = t.see_active_window()
        if r.get("ok"): print(f"活动窗口: {r['window']['title']} | {r['window']['size']} | {r['image_kb']}KB")
        else: print(r)
