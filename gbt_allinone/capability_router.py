# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 对话能力路由（capability_router）

主人令 2026-11-02：「写 capability_router 接进 /api/chat：看屏幕、开网页、读写文件、看图四类，
自动调用万能插并验收」。

一句话：**把一句人话判成四类里的哪一类，再交给万能插真执行**。
本模块只做两件事 —— 「判类 + 取目标」和「把目标翻译成万能插的 payload」；
真正执行**一律**走 `api.run_task("omni_plug", payload)`（万能插唯一门：授权、审计、回执都在门里），
这里不另造第二套执行器、不绕过任何门。

四类（不新增能力位，避免动 385/388 注册表锁）：
  · screen 看屏幕   → omni_plug `app` 插座 `see`（空目标 = 整屏取帧）
  · web    开网页   → omni_plug `web` 插座 `open`（系统默认浏览器，真打开）
  · file   读写文件 → omni_plug `file` 插座 `read` / `write`（写面仍受万能插 WRITE_ROOTS 收口）
  · image  看图     → omni_plug `universal` 插座 `view`（现场判类为图片，走本机视觉）

口径（写死，可复核）：
  ① **只接祈使/任务句**：带「吗 / 呢 / ？ / 怎么 / 如何 / 会不会…」又没有「帮我 / 请 / 给我 / 现在…」
     且不以动作动词开头的，按提问处理 ⇒ handled=False，交给对话模型（不抢话、不擅自动手）；
  ② **四类之外 handled=False**，`/api/chat` 照旧走对话模型，行为与接进前一致；
  ③ **判不出目标不猜**：开网页没给网址、写文件没给路径/内容 ⇒ 如实回 `user_error`，不编造；
  ④ 每次执行都过万能插的门：回执里带 `call`（kind=omni_plug + payload）和 `capability`（万能插回执），
     被门拒时原样带回 `missing` / `how_to_grant`，不把「要票」说成「坏了」。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTER_ID = "capability_router"
INTENTS = ("screen", "web", "file", "image")
INTENT_LABELS = {"screen": "看屏幕", "web": "开网页", "file": "读写文件", "image": "看图"}
OMNI_KIND = "omni_plug"

# ── 关键词（人话侧；命中即候选，最后按命中数 + 优先级定类）────────────────────
SCREEN_KW = ("看屏幕", "看看屏幕", "看一下屏幕", "看看屏", "看下屏幕", "看一眼屏幕",
             "看桌面", "看看桌面", "截屏", "截图", "抓屏", "屏幕截图", "全屏截图",
             "截个屏", "截个图", "截一下屏", "截一下图", "抓个屏", "抓个图",
             "整屏", "桌面截图", "screenshot", "screen shot", "看屏")
WEB_KW = ("打开网页", "开网页", "打开网站", "访问网页", "打开页面", "打开链接",
          "上个网页", "打开浏览器", "浏览网页", "访问网站", "open url", "browse")
FILE_KW = ("读文件", "读取文件", "读一下文件", "看看文件", "看一下文件", "看下文件",
           "打开文件", "文件内容", "写入文件", "写文件", "保存到", "保存为", "存到",
           "创建文件", "新建文件", "追加到", "覆盖写", "写到", "read file", "write file",
           "读盘", "写盘")
IMAGE_KW = ("看图", "看看图", "看图片", "看看图片", "看一下图片", "看看这张图", "看这张图",
            "这张图片", "这张图", "识图", "分析图", "分析图片", "图片里", "图里", "照片里",
            "看图里", "look at the image", "image analysis")

QUESTION_HINTS = ("吗", "呢", "？", "?", "怎么", "如何", "为什么", "会不会", "能不能",
                  "可不可以", "是否", "有没有", "是什么", "什么")
IMPERATIVE_HINTS = ("帮我", "帮忙", "请", "给我", "替我", "麻烦", "现在", "马上", "立刻", "立即")
ACTION_STARTS = ("看", "读", "写", "打开", "开", "截", "抓", "访问", "分析", "保存",
                 "存", "识别", "浏览", "查", "把")
WRITE_KW = ("写文件", "写入文件", "写入", "写到", "写进", "保存到", "保存为", "保存成",
            "存到", "存进", "创建文件", "新建文件", "追加到", "覆盖写", "写盘",
            "write file", "save to", "append to")
READ_KW = ("读文件", "读取文件", "读一下", "读一读", "读读", "读盘", "看看文件",
           "打开文件", "文件内容", "读出", "read file", "cat ")
# 泛化动作词：只有**同时给出路径**时，才允许它把句子抬进 file/image 类（F5 修法）
# 「裸路径抬类」的动作词表（只有同时给出路径才用；单说路径不等于要读它）
GENERIC_ACTION_RX = re.compile(r"(读|写|保存|存|打开|查看|创建|新建|追加|覆盖|看看|看|识|分析)", re.I)
WEB_VERB_RX = re.compile(r"(打开|访问|浏览|开|goto|open|browse)", re.I)
# F1 修法（独立验收抓出）：write 判定**不许**只看一个「写」字 ——
#   必须命中这些显式写动词/句式；否则「读文件 X 里写的结论」会被判成覆盖写。
WRITE_RX = re.compile(r"(写文件|写入文件|写入|写到|写进|保存到|保存为|保存成|存到|存进|"
                      r"创建文件|新建文件|追加到|覆盖写|写盘|write file|save to|append to)", re.I)
# N1 修法（复验抓出回归）：句首/分句首的**裸写动词**也是写（「写 outputs/x.txt 内容 你好」）。
#   但必须卡在「子句开头」（^ 或标点/换行之后）——「读文件 X 里写的结论」里的「写」在句中，不算。
BARE_WRITE_RX = re.compile(
    r"(?:^|[，,。；;！!？?\n])\s*(?:请|帮我|帮忙|麻烦|给我|然后|再|接着)?\s*"
    r"(?:写|保存|新建|追加|覆盖)\s*(?=\S)")
READ_RX = re.compile(r"(读文件|读取文件|读一下|读一读|读读|读盘|看看文件|看一下文件|看下文件|"
                     r"打开文件|文件内容|读出|read file)", re.I)
PLACEHOLDER_TEXTS = ("这段文字", "这些文字", "上面的内容", "上面的话", "刚才的内容",
                     "刚才说的", "那个内容", "这个内容", "它", "这", "那", "xxx", "…")

IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".ico")
# 文本/数据类扩展名：用于「裸文件名」判定（避免把普通英文句子里的点当成路径）
DOC_EXTS = (".txt", ".md", ".json", ".jsonl", ".csv", ".log", ".py", ".js", ".ts",
            ".html", ".htm", ".css", ".yml", ".yaml", ".toml", ".ini", ".cfg",
            ".xml", ".sql", ".sh", ".ps1", ".bat", ".cmd", ".mp4", ".mp3", ".wav",
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".pptx")
PATH_EXTS = IMG_EXTS + DOC_EXTS

_URL_RE = re.compile(r"(https?://[^\s\"'<>（）()【】\[\]，。；;！!？?]+)", re.I)
_WWW_RE = re.compile(r"(www\.[^\s\"'<>（）()【】\[\]，。；;！!？?]+)", re.I)
_DOMAIN_RE = re.compile(
    r"(?<![A-Za-z0-9-])"
    r"([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.(?:com|cn|org|net|io|ai|dev|app|co|"
    r"info|top|xyz|me|edu|gov|tv|cc|so)(?:/[^\s\"'<>（）()【】\[\]，。；;！!？?]*)?)",
    re.I)
_EXT_ALT = "|".join(re.escape(e.lstrip(".")) for e in PATH_EXTS)
# F5 修法（独立验收抓出）：本仓路径含空格（`...\Lenovo E14 Gen 5\...`），
#   原来 `到空白即止` 会把 `C:\Users\Lenovo` 当整条路径。带扩展名的盘符/UNC 路径
#   用「盘符/UNC 起、已知扩展名止」的非贪婪匹配，空格照收；无扩展名的再看盘上是否存在。
_DRIVE_EXT_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]:[\\/][^\"'<>|\r\n]*?\.(?:%s))" % _EXT_ALT, re.I)
_UNC_EXT_RE = re.compile(r"(\\\\[^\"'<>|\r\n]*?\.(?:%s))" % _EXT_ALT, re.I)
_WIN_PATH_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]:[\\/][^\s\"'<>|，。；;！!？?]+)")
_REL_PATH_RE = re.compile(
    r"((?:\.{1,2}[\\/])?[\w\u4e00-\u9fff.\\/-]+\.(?:%s))" % _EXT_ALT, re.I)
_QUOTED_RE = re.compile(r"[\"'“”「」『』]([^\"'“”「」『』]{1,260})[\"'“”「」『』]")


# 2026-11-07（主人令「帧直接给模型看」）：问「屏幕上有什么」= 要一帧给模型看；
# 问「你会看屏幕吗」= 在问能力，**不许**当成指令。两者只靠词面分开，不做语义猜测。
_ASK_SCREEN_RX = re.compile(r"(屏幕|桌面|界面|画面)(?:上|中|里)?[^，。；？?]{0,8}"
                            r"(有什么|有啥|是什么|是啥|显示(?:的)?(?:是)?什么|显示(?:的)?啥|谁|哪里|哪个)")
_ASK_ABILITY_RX = re.compile(r"(会不会|能不能|可不可以|能否|支持|你会|会看|可以看|能用|行不行)")


# ── 纯文本工具 ─────────────────────────────────────────────────────────────
def _hits(text: str, words) -> list:
    return [w for w in words if w in text]


def _looks_like_question(text: str) -> bool:
    low = text.strip()
    if not any(q in low for q in QUESTION_HINTS):
        return False
    if any(w in low for w in IMPERATIVE_HINTS):
        return False
    head = low.lstrip(" 　,，。:：")
    return not any(head.startswith(v) for v in ACTION_STARTS)


def _looks_like_path(cand: str) -> bool:
    c = str(cand or "").strip().strip("\"'“”「」『』 ")
    if not c or len(c) > 300:
        return False
    ext = Path(c).suffix.lower()
    if ext in PATH_EXTS:
        return True
    return ("/" in c or "\\" in c) and "." in Path(c).name


def _find_url(text: str) -> str:
    m = _URL_RE.search(text)
    if m:
        return m.group(1).rstrip(".,;:!?)]}>，。；：！？）】》")
    m = _WWW_RE.search(text)
    if m:
        return "https://" + m.group(1).rstrip(".,;:!?)]}>，。；：！？）】》")
    m = _DOMAIN_RE.search(text)
    if m:
        return "https://" + m.group(1).rstrip(".,;:!?)]}>，。；：！？）】》")
    return ""


def _path_key(p: str) -> str:
    try:
        return str(Path(_abs_target(p))).lower()
    except Exception:                                            # noqa: BLE001
        return str(p).lower()


def _find_paths(text: str) -> list:
    """取全部路径候选（顺序：引号 > 带扩展名盘符/UNC > 无扩展名盘符 > 相对路径；去重）。

    为什么要「全部」：F1 的另一个变体是「把 A 里的内容保存到 B」——
    只取第一个路径会把**源文件**当目标写掉。多路径写必须拒，不能猜。
    """
    out = []

    def push(p: str) -> None:
        p = str(p or "").strip().strip("\"'“”「」『』 ")
        if not p:
            return
        if all(_path_key(p) != _path_key(x) for x in out):
            out.append(p)

    for seg in _QUOTED_RE.findall(text):
        if _looks_like_path(seg):
            push(seg)
    for rx in (_DRIVE_EXT_RE, _UNC_EXT_RE):
        for m in rx.finditer(text):
            push(m.group(1))
    for m in _WIN_PATH_RE.finditer(text):
        cand = m.group(1)
        raw = re.search(r"([A-Za-z]:[\\/][^\"'<>|\r\n，。；;！!？?]+)", text[m.start():])
        if raw:
            probe = raw.group(1).strip()
            while probe and not Path(probe).exists() and (" " in probe or "\\" in probe[3:]):
                cut = max(probe.rfind(" "), probe.rfind("\\"), probe.rfind("/"))
                if cut <= 2:
                    break
                probe = probe[:cut].rstrip(" \\/")
            if probe and Path(probe).exists():
                push(probe)
                continue
        push(cand)
    for m in _REL_PATH_RE.finditer(text):
        cand = m.group(1)
        if _looks_like_path(cand):
            push(cand)
    return out


def _find_path(text: str) -> str:
    """取主路径（第一个候选）。"""
    paths = _find_paths(text)
    return paths[0] if paths else ""


def _abs_target(target: str) -> str:
    """相对路径按仓根解析（万能插 file 插座与 vision 都以仓为基准，不靠进程 CWD）。"""
    p = Path(str(target or ""))
    return str(p if p.is_absolute() else (ROOT / p))


def _clean_content(c: str) -> str:
    c = str(c or "").strip().strip("\"'“”「」『』 ")
    if not c or c in PLACEHOLDER_TEXTS:
        return ""
    # 「把这段文字/上面的内容」这类指代词不能当正文（F2 修法：没上下文就如实报缺，不静默写占位词）
    if re.fullmatch(r"(?:把)?(?:这段|这些|上面(?:的)?|刚才(?:的)?|那个|这个|那|这)?"
                    r"(?:文字|话|内容|字)", c):
        return ""
    return c


def _find_write_text(text: str, path: str) -> str:
    """从人话里取要写入的内容。取不到就返回空串（不拿整句去写，也不拿占位词去写）。"""
    # ① 显式标记：内容 xxx / 内容：xxx（冒号或空白至少一个 —— 否则「把上面的内容存到 X」
    #    里的「内容」会被当成标记，把「存到 X」当正文。这是 F2 的第二道修法。）
    m = re.search(r"(?:内容|正文)\s*(?:[:：]\s*|\s+)(?P<c>.+)$", text)
    if m:
        return _clean_content(m.group("c"))
    m = re.search(r"文字是\s*(?P<c>.+)$", text)
    if m:
        return _clean_content(m.group("c"))
    # ② 把<内容>写到/写进<路径>
    m = re.search(r"把(?P<c>.+?)(?:写到|写入|写进|保存到|保存为|存到|存进|放进|放到)\s*.+$", text)
    if m:
        return _clean_content(m.group("c"))
    # ③ 写到<路径>内容<内容>
    m = re.search(r"(?:写到|写入|写进|保存到|保存为|存到|存进|放进|放到)\s*.+?\s*"
                  r"(?:内容|文字|正文)\s*[:：]?\s*(?P<c>.+)$", text)
    if m:
        return _clean_content(m.group("c"))
    # ④ 路径后面直接跟内容：「写文件 outputs/a.txt 你好世界」（仅显式写句式才用这条）
    if path:
        for needle in (path, path.strip("\"'“”「」『』 ")):
            idx = text.find(needle)
            if idx >= 0:
                tail = text[idx + len(needle):].strip(" 　，,：:。；;")
                tail = re.sub(r"^(?:内容|文字|正文)\s*[:：]?\s*", "", tail)
                # 尾巴是命令/叮嘱（「然后告诉我」「请确认」）不是正文 ⇒ 不当内容写
                if tail and not re.match(r"^(?:然后|再|并|请|帮|告诉|发|给|结果|之后|随后|把)", tail):
                    return _clean_content(tail)
    return ""


# ── 判类 ───────────────────────────────────────────────────────────────────
def classify(text: str) -> dict:
    """一句人话 → 四类之一 + 目标 + 动作。**纯文本分析**：不执行、不联网、不写盘。"""
    raw = str(text or "").strip()
    out = {"input": raw, "intent": "", "action": "", "target": "", "target_abs": "",
           "matched": [], "missing": [], "confidence": 0.0, "question": False,
           "error": "", "reason": ""}
    if not raw:
        out["error"] = "user_error: 空输入"
        return out

    low = raw.lower()
    hits = {
        "screen": _hits(low, SCREEN_KW),
        "image": _hits(low, IMAGE_KW),
        "web": _hits(low, WEB_KW),
        "file": _hits(low, FILE_KW),
    }
    url = _find_url(raw)
    paths = _find_paths(raw)
    path = paths[0] if paths else ""
    # F3 修法（独立验收抓出）：只有「显式 web 动作/关键词 + 没有任何更具体的类」时，
    #   URL 才把句子抬进 web —— 否则「读文件 X 里 https://example.com 那段」会被抢去开浏览器。
    # 只有 URL、没有打开/访问/浏览类动词的句子（例如单贴一条链接）**不**算开网页指令。
    explicit_other = bool(hits["screen"] or hits["image"] or hits["file"])
    if url and not hits["web"] and not explicit_other and WEB_VERB_RX.search(low):
        hits["web"] = ["URL"]
    # 裸路径也要有动作词才抬类（单说一个文件路径不等于"读它"）
    if path and not hits["file"] and not hits["image"]:
        ext = Path(path).suffix.lower()
        if ext in IMG_EXTS and re.search(r"(看|识|分析|查看|打开|看图)", low):
            hits["image"] = ["路径"]
        elif ext in PATH_EXTS and re.search(r"(读|写|保存|存|打开|查看|创建|新建|追加|覆盖|看看)", low):
            hits["file"] = ["路径"]

    # 「屏幕上有什么」本身就是一个看屏意图（只读取帧）；只在四类都没命中时才抬，
    # 不去抢已经有动作词的句子（读文件 / 写文件 / 开网页照旧优先）。
    if not any(hits.values()) and _ASK_SCREEN_RX.search(low) and not _ASK_ABILITY_RX.search(low):
        hits["screen"] = ["屏幕内容问句"]

    # 判类优先级：screen > image > web > file（同分时按此顺序；「看屏幕」最具体）
    order = ("screen", "image", "web", "file")
    best = sorted(order, key=lambda k: (-len(hits[k]), order.index(k)))[0]
    if not hits[best]:
        out["reason"] = "四类都没命中 ⇒ 交给对话模型"
        return out

    out["question"] = _looks_like_question(raw)
    if out["question"]:
        _ask_screen = (best == "screen" and _ASK_SCREEN_RX.search(raw)
                       and not _ASK_ABILITY_RX.search(raw))
        if not _ask_screen:
            out["reason"] = "看着像提问（带问句、无祈使词）⇒ 不擅自动手，交给对话模型"
            return out
        # 只开给「屏幕内容」这一类：动作仍是 see（只读取帧，隐私门照旧）
        out["reason"] = "问句但在问屏幕内容 ⇒ 只读取一帧交给模型看"

    out["intent"] = best
    out["matched"] = hits[best][:8]
    out["confidence"] = round(min(1.0, 0.4 + 0.2 * len(hits[best])), 2)

    if best == "screen":
        out["action"] = "see"
        return out

    if best == "web":
        out["action"] = "open"
        if not url:
            out["missing"] = ["url"]
            out["error"] = "user_error: 开网页需要一个网址（例：打开 https://example.com）"
            return out
        out["target"] = url
        return out

    if best == "image":
        out["action"] = "view"
        if not path:
            out["missing"] = ["path"]
            out["error"] = "user_error: 看图需要给出图片路径（例：看图 icons/avatar.png）"
            return out
        if Path(path).suffix.lower() not in IMG_EXTS:
            out["missing"] = ["image_file"]
            out["error"] = "user_error: 看图只接图片文件（%s），给的是：%s" % (
                " / ".join(IMG_EXTS), path)
            return out
        out["target"] = path
        out["target_abs"] = _abs_target(path)
        return out

    # file：**读/写判定只认显式句式**（F1 修法：一个「写」字不再等于写文件）。
    # 两个显式标记都没有时**默认 read**（安全侧）：绝不因为句子里出现「写/保存」这类字就写盘。
    # N1：句首/分句首的裸写动词（写/保存/新建/追加/覆盖）也算 write。
    w = bool(WRITE_RX.search(low)) or bool(BARE_WRITE_RX.search(raw))
    r = bool(READ_RX.search(low))
    if w and r:
        out["missing"] = ["action"]
        out["error"] = "user_error: 一句话里同时像读又像写，请分开说（例：先读 A，再写到 B）"
        return out
    out["action"] = "write" if w else "read"
    if not path:
        out["missing"] = ["path"]
        out["error"] = "user_error: 读写文件需要给出文件路径（例：读文件 outputs/a.txt）"
        return out
    if out["action"] == "write":
        # 复制/搬移语义（「把 A 里的内容保存到 B」）没有两条执行腿，不猜目标。
        if re.search(r"把.+?里(?:面)?的?(?:内容|东西|文字).{0,12}?(?:保存|写|存|放)到", raw):
            out["missing"] = ["copy_unsupported"]
            out["error"] = ("user_error: 复制/搬移语义暂不支持（复制要两条执行腿）；"
                            "请分开说：先读 A，再写到 B")
            return out
        # N3 修法：内容区里出现的路径不算「目标冲突」——只有**正文标记之前**的路径才是候选目标。
        _marks = [m.start() for m in re.finditer(r"(?:内容|正文|文字是)", raw)]
        _content_from = min(_marks) if _marks else None
        _target_paths = [p for p in paths
                         if _content_from is None or raw.find(p) < _content_from]
        if len(_target_paths) > 1:
            out["missing"] = ["single_target"]
            out["error"] = ("user_error: 一句话里出现多个文件路径（%s），写语义不猜目标；"
                            "请分开说：先读 A，再写到 B" % " / ".join(_target_paths[:3]))
            return out
    out["target"] = path
    out["target_abs"] = _abs_target(path)
    if out["action"] == "write":
        content = _find_write_text(raw, path)
        if not content:
            out["missing"] = ["content"]
            out["error"] = ("user_error: 写文件需要内容（例：写文件 outputs/a.txt 内容 你好）")
            return out
        out["write_text"] = content
    return out


# ── 判类 → 万能插 payload（白名单：只有四种形状，且形状之外还验语义）──────────
def build_call(route: dict) -> dict:
    """只按四类拼 omni_plug payload；别的形状一律抛错（路由不是万能插的任意口）。

    F7 修法（独立验收抓出）：光验形状不够 —— 直连 `execute()` 时 target/target_abs 可以被
    拼成任意东西（把 image 的 target 写成 whoami.exe，形状仍是合法的 universal/view）。
    所以这里再验**语义**：image 必须是图片扩展名、web 必须是 http(s)、file 读写要齐。
    """
    intent = str(route.get("intent") or "")
    action = str(route.get("action") or "")
    target = str(route.get("target") or "")
    abs_target = str(route.get("target_abs") or target)
    if intent == "screen":
        return {"op": "run", "socket": "app", "target": "", "do": "see"}
    if intent == "web":
        if not re.match(r"^https?://", str(target or ""), re.I):
            raise ValueError("web 目标必须是 http(s) URL（实际：%r）" % (target,))
        return {"op": "run", "socket": "web", "target": target, "do": "open"}
    if intent == "file":
        if action not in ("read", "write") or not str(abs_target or "").strip():
            raise ValueError("file 路由不完整：action=%r target=%r" % (action, abs_target))
        payload = {"op": "run", "socket": "file", "target": abs_target, "do": action}
        if action == "write":
            text = str(route.get("write_text") or "")
            if not _clean_content(text):
                raise ValueError("写文件缺内容，拒绝拼 payload")
            payload["args"] = {"text": text}
        return payload
    if intent == "image":
        if Path(str(abs_target or "")).suffix.lower() not in IMG_EXTS:
            raise ValueError("看图目标不是图片文件（实际：%r）" % (abs_target,))
        return {"op": "universal", "target": abs_target, "do": "view"}
    raise ValueError("不是四类之一，拒绝拼万能插 payload：%r" % (intent,))


# ── 执行：走万能插唯一门 ──────────────────────────────────────────────────
_BIG_KEYS = ("image_base64", "gbt_stamp")


def _trim(obj, depth: int = 0):
    """裁掉大块字段（截图 base64 / 钢印），回执保留可核对的部分，不把整张图塞进聊天响应。"""
    if depth > 6:
        return "…"
    if isinstance(obj, dict):
        return {k: _trim(v, depth + 1) for k, v in obj.items() if k not in _BIG_KEYS}
    if isinstance(obj, (list, tuple)):
        return [_trim(x, depth + 1) for x in list(obj)[:30]]
    if isinstance(obj, str) and len(obj) > 1200:
        return obj[:1200] + "…"
    return obj


def _dispatch(payload: dict) -> dict:
    """**唯一执行口**：run_task(kind="omni_plug", payload)。授权/审计/回执都在门里。"""
    try:
        from . import api as _api
        return _api.run_task(OMNI_KIND, payload, safe=True)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "kind": OMNI_KIND,
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:160]), "result": {}}


def _why(receipt: dict) -> str:
    """回执 → 一句原因。

    2026-11-06 修：信封 `ok` 只说明分派成功，**本体可能在里面说 ok:false**
    （AGENTS §2.2）。原先只看第一层，于是「看屏幕」失败时把上游写好的
    `看.why` / `看.rule` 全吐掉，主人只看到一句「原因未报」—— 如实报错变成了
    如实报「不知道」。现在第一层没有就往下钻一层，并带上缺件清单。
    """
    keys = ("reason", "error", "why", "evidence", "message", "note", "rule", "status")

    def _pick(d: dict) -> str:
        for k in keys:
            v = d.get(k)
            if v:
                return str(v)
        return ""

    hit = _pick(receipt)
    if not hit:
        for v in receipt.values():
            if isinstance(v, dict) and v.get("ok") is False:
                hit = _pick(v)
                if hit:
                    miss = v.get("missing") or []
                    if miss:
                        hit += "（缺：%s）" % " / ".join(map(str, miss[:6]))
                    break
    if not hit:
        for v in receipt.values():
            if isinstance(v, dict):
                hit = _pick(v)
                if hit:
                    break
    return hit[:240] if hit else "原因未报（回执里没有 reason/error/why 字段）"


def _summarize(route: dict, receipt: dict) -> str:
    """万能插回执 → 一句人话（只陈述回执里有的，不编）。"""
    intent = route.get("intent")
    label = INTENT_LABELS.get(intent, intent or "能力")
    target = route.get("target") or ""
    ok = bool(receipt.get("ok"))
    if not ok:
        return "%s没成：%s" % (label, _why(receipt))
    if intent == "screen":
        look = receipt.get("看") or {}
        size = look.get("size") or receipt.get("size")
        where = look.get("window") or {}
        bits = ["已取到屏幕帧"]
        if size:
            bits.append("%sx%s" % (size[0], size[1]))
        if isinstance(where, dict) and where.get("title"):
            bits.append("窗口=%s" % str(where.get("title"))[:40])
        return "看屏幕：%s（经万能插 app 插座）" % " · ".join(bits)
    if intent == "web":
        return "开网页：%s（backend=%s）" % (receipt.get("url") or target,
                                            receipt.get("backend") or "?")
    if intent == "image":
        inner = receipt.get("result") if isinstance(receipt.get("result"), dict) else {}
        size = inner.get("size") or []
        bits = []
        if size:
            bits.append("%sx%s" % (size[0], size[1]))
        if inner.get("brightness") is not None:
            bits.append("亮度=%s" % inner.get("brightness"))
        if inner.get("contrast") is not None:
            bits.append("对比度=%s" % inner.get("contrast"))
        return "看图：%s%s" % (target, ("（" + " · ".join(bits) + "）") if bits else "")
    if route.get("action") == "write":
        return "写文件：%s（%s 字节）" % (target, receipt.get("wrote_bytes"))
    text = str(receipt.get("read") or "")
    return "读文件：%s%s" % (target, ("（前 200 字）" + text[:200]) if text else "（空文件或未读到内容）")


def _unwrap(receipt) -> dict:
    """剥掉 `api.run_task` 外面那层信封：{status,kind,result:{万能插回执},authorization}。

    只剥一层，且**只在外面这层没有 socket/op 时剥**——万能插自己的回执本来就可能带
    `result`（如「看图」的视觉分析结果），不能继续往下挖（会把真回执挖掉）。
    """
    if isinstance(receipt, dict) and "socket" not in receipt and "op" not in receipt:
        inner = receipt.get("result")
        if isinstance(inner, dict):
            return inner
    return receipt if isinstance(receipt, dict) else {}


def execute(route: dict) -> dict:
    """执行一条已判好的路由：拼 payload → 过万能插门 → 统一回执。"""
    t0 = time.time()
    intent = str(route.get("intent") or "")
    if intent not in INTENTS:
        return {"ok": False, "handled": False, "intent": intent, "route": _trim(route),
                "text": "", "via": ROUTER_ID, "ms": int((time.time() - t0) * 1000)}
    if route.get("error"):
        return {"ok": False, "handled": True, "intent": intent,
                "action": route.get("action"), "route": _trim(route),
                "error": route["error"], "text": route["error"],
                "via": ROUTER_ID, "ms": int((time.time() - t0) * 1000)}
    try:
        payload = build_call(route)
    except ValueError as exc:
        return {"ok": False, "handled": True, "intent": intent,
                "action": route.get("action"), "route": _trim(route),
                "error": "user_error: %s" % str(exc)[:240],
                "text": "没执行：%s" % str(exc)[:240],
                "via": ROUTER_ID, "ms": int((time.time() - t0) * 1000)}
    envelope = _dispatch(payload)
    receipt = _unwrap(envelope.get("result") if isinstance(envelope, dict) else {})
    envelope_ok = bool(envelope.get("ok", False))
    receipt_ok = bool(receipt.get("ok", envelope_ok))
    ok = envelope_ok and receipt_ok
    out = {
        "ok": ok,
        "handled": True,
        "intent": intent,
        "action": route.get("action"),
        "label": INTENT_LABELS.get(intent),
        "route": _trim(route),
        "call": {"kind": OMNI_KIND, "payload": payload},
        "capability": _trim(receipt),
        "text": _summarize(route, receipt),
        "via": ROUTER_ID,
        "ms": int((time.time() - t0) * 1000),
    }
    if intent == "screen":
        # 2026-11-07: single frame is fallback only; default lane is native realtime
        # (state/vision-policy.json). Never present this as the realtime chain.
        out["lane"] = "single_frame_fallback"
        out["degraded"] = True
        out["policy"] = "state/vision-policy.json"
    if not ok:
        out["error"] = str(envelope.get("error") or _why(receipt))[:300]
        for k in ("denied", "missing", "how_to_grant"):
            if envelope.get(k) is not None:
                out[k] = envelope[k]
    return out


def run(text: str, *, context: str = "console-web") -> dict:
    """一句人话 → 判类 → 自动调用万能插。`handled=False` 表示不归四类管（交给对话模型）。"""
    t0 = time.time()
    route = classify(text)
    if not route.get("intent"):
        return {"ok": False, "handled": False, "intent": "", "route": _trim(route),
                "text": "", "via": ROUTER_ID, "ms": int((time.time() - t0) * 1000),
                "reason": route.get("reason") or route.get("error") or "四类都没命中"}
    result = execute(route)
    result["context"] = {"mode": "capability-router", "name": context}
    return result


def capabilities() -> dict:
    """自述（给面板/验收读）：四类、各自落在万能插哪个插座、门要什么。只读。"""
    return {
        "ok": True,
        "name": "capability_router",
        "intents": [
            {"intent": "screen", "label": "看屏幕",
             "omni": {"op": "run", "socket": "app", "do": "see"},
             "scopes": ["desktop_control", "privacy_read"]},
            {"intent": "web", "label": "开网页",
             "omni": {"op": "run", "socket": "web", "do": "open"},
             "scopes": ["desktop_control", "privacy_read"]},
            {"intent": "file", "label": "读写文件",
             "omni": {"op": "run", "socket": "file", "do": "read|write"},
             "scopes": ["filesystem_write（仅写）"]},
            {"intent": "image", "label": "看图",
             "omni": {"op": "universal", "do": "view"},
             "scopes": ["读类（本机视觉，无写面）"]},
        ],
        "handled_false": "四类之外 / 像提问的句子 ⇒ 交回对话模型",
        "executor": "api.run_task(kind='omni_plug') —— 万能插唯一门",
    }


__all__ = ["INTENTS", "INTENT_LABELS", "classify", "build_call", "execute", "run",
           "capabilities", "ROUTER_ID"]

