# -*- coding: utf-8 -*-
"""桌面壳 · 「不破坏 DSH」守卫（2026-09-23 立）。

## 为什么要这件

Owner 的硬约束是「**不能破坏 DeepSeek Harness（我们现在对话的页面），以这个为底层**」。
这种话**不能靠"我小心"**——必须有**可判的边界**，否则"没破坏"只是我嘴上说的。
本件把《一体式桌面APP-架构与路线图》§2 的 B1–B5 变成**能跑的判据**。

## 四态，不许只有两态

    PASS     已证实成立
    FAIL     已证实不成立（**出现任一 FAIL ⇒ 退出码 1，不许打包**）
    PENDING  **还没建/还没测**（例如"窗 A 还没做"）——
            ⚠️ PENDING **不算 PASS**。只有两态的话，"还没做"会被读成"没问题"，
            那正是本仓最恨的假绿。
    NA       **不适用**（明确不需要，不算欠账）——
            2026-10-28 补。此前只有三态，于是「窗 A 早改载本地页、DSH 旧路不再需要」
            这种**明确不需要**的事只能挂在 PENDING 上，把"还没做"和"不用做"混成一堆黄灯。
            主人口径是五档（真坏/缺依赖/未配置/**不适用**/好），那 NA 就得存在。
            NA **不影响退出码**，但必须在汇总里显式打印个数 —— 悄悄算进 PASS 才是假绿。

## 判据（逐条对应 §2）

    B1a DSH web 在听：3080 有监听           （2026-10-04 起为旧路；窗 A 已改载本地页 ⇒ NA）
    B1b 窗 A 真载对话面：现读=直载白名单外部 DeepSeek 网页（主人令 2026-10-04）
    B1c 不代理：壳里没有实现/转发对话协议的代码（不许在壳里重做 DSH）
    B2  不动 DSH 配置：~/.dsh 下关键文件的哈希与基线一致
    B3  不占 DSH 端口：壳自身不新增监听；面板服务仍是 8765
    B4  不注入：壳对 3080 那个窗不做 executeJavaScript / 不改写请求
    B5  不依赖内部：壳里不出现 DSH 源码/包路径（只许依赖 URL + 公开 HTTP）

## 用法

    py -3.14 tools/codex-scripts/desktop-shell-guard.py                  # 只查（默认）
    py -3.14 tools/codex-scripts/desktop-shell-guard.py --record-baseline # 记一次基线（B2 用）
    py -3.14 tools/codex-scripts/desktop-shell-guard.py --json out.json

基线文件：`state/desktop-shell-baseline.json`（只记哈希与端口，**不记内容、不记密钥**）。
"""
import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
SHELL_DIR = ROOT / "holo_pet_w3"
SHELL_SOURCES = [SHELL_DIR / "shell" / n for n in
                 ("main.cjs", "layout.cjs", "features.cjs", "preload.cjs",
                  "url-policy.cjs", "windows.json", "connect.html", "blocked.html",
                  "deepseek_loop.cjs",
                  # 2026-10-07 加：DSH 自接入（壳自己拉起 `dsh web` 读就绪行）。
                  # **必须进这个名单** —— 它会 spawn 一条外部命令，正是 B1c「不重做对话协议」
                  # 与 B5「不依赖 DSH 内部」最该盯的新面；不进名单 = 让它绕过守卫。
                  "dsh-launch.cjs")]
SHELL_SOURCES += [SHELL_DIR / n for n in ("index.html", "window.js", "window.css")]

# B8 的取证面：快照页 + 立体层（2026-09-23 风哥令「3D 立体视觉感要做出来」后新加）。
# 为什么不并进 SHELL_SOURCES：那批是**壳逻辑**（B1c/B3x/B4 按脚本语义判），
# 而这几件是**死页面 + 样式**，该按"惰性 + 真三维"判 —— 判据不同，取证面就分开。
DECK_DIRS = ("exec-deck", "code-deck")
INERT_SOURCES = [SHELL_DIR / d / "index.html" for d in DECK_DIRS]
INERT_SOURCES += [SHELL_DIR / "deck3d.css"]

DSH_PORT = 3080
PANEL_PORT = 8765
# 外部点名白名单（2026-10-04 · 主人令：对话窗直载原生 DeepSeek 网页）。
# 与 holo_pet_w3/shell/url-policy.cjs 的 EXTERNAL_ALLOWED_HOSTS **同名单互绑**：
#    改任何一边必须同步另一边，两边不一致 = 守卫假红/假绿。
ALLOWED_EXTERNAL_HOSTS = frozenset({"chat.deepseek.com"})
BASELINE = ROOT / "state" / "desktop-shell-baseline.json"

# B2：DSH 的配置面（**只取哈希**，绝不读内容进报告）
DSH_HOME = Path(os.path.expanduser("~")) / ".dsh"
# 2026-10-26：0.2.x 把配置**迁进了 profile** ⇒ 取证面必须跟着搬家。
#   实测：全局 `~/.dsh/settings.yaml` **已不存在**（只剩 settings.yaml.bak-002108，9-23 的）；
#   `profiles/{web,desktop,headless}` 都没有 settings.yaml；
#   唯一还带 `defaultPreset: danger-full-access` 的是 `profiles/gbt-official/settings.yaml`。
#   只盯全局那份 ⇒ B2 会**永远红**，而且红得没有意义（真正该守的那份没人看）。
#
# 特意**不盯** `profiles/*/cordis.yml`：它是 223 字节的空壳（内容恒为 `[]`），
#      dsh **每次启动都重写它**（实测 mtime 每次起服务都变）⇒ 盯它等于跑一次红一次。
#      真正手工定制的是 `cordis.patch.yml`（11.5KB，文件里自己写着
#      "Edit cordis.patch.yml, not this file"），那条才是该守的。
# 也**不盯** `profiles/*/cordis.patch.yml.bak-*` / `package.json.bak-*` 等备份：
#      备份增删是正常操作，盯了只会制造噪声。
DSH_PROFILE = "gbt-official"          # 主人 2026-10-26 选定（带 danger-full-access）
DSH_SETTINGS_REL = "profiles/%s/settings.yaml" % DSH_PROFILE
DSH_WATCH = ["settings.yaml", "settings.yaml.bak", "agent-presets", ".agent-presets",
             DSH_SETTINGS_REL,
             "profiles/%s/cordis.patch.yml" % DSH_PROFILE]


def _preset_of(structs: dict):
    """当前权限档取值：**优先**读 profile 里那份（0.2.x 起真正的落点），退回全局那份。"""
    for rel in (DSH_SETTINGS_REL, "settings.yaml"):
        v = (structs.get(rel) or {}).get("defaultPreset")
        if v:
            return v
    return None


def _b2_verdict(base: dict, base_struct: dict, now: dict, now_struct: dict) -> tuple:
    """B2 的**判定本体**（纯函数，不碰文件系统 —— 这样负对照才喂得进去）。

    🔴 为什么必须抽出来（2026-10-26）：这条判据原来长在 `main()` 里、直接读真环境，
       于是"权限档被改会不会红"这件事**从来没有被证明过** —— 一个只会在真环境里
       说话的判据，等价于没有负对照。本仓纪律：**读真文件的判据，判定本体必须是纯函数**
       （守卫 B2 到 2026-10-26 前一条负对照都没有，就是这么漏的）。
    """
    diff = [k for k in now if base.get(k) != now[k]]
    struct_diff = [rel for rel in now_struct
                   if (base_struct.get(rel) or {}).get("keys_sha256")
                   != now_struct[rel].get("keys_sha256")]
    perm_diff = [rel for rel in now_struct
                 if (base_struct.get(rel) or {}).get("defaultPreset")
                 != now_struct[rel].get("defaultPreset")]
    if perm_diff:
        return ("FAIL",
                "**安全相关键被改**：%s —— 结构指纹 %s；默认档 基线=%s 现读=%s"
                % (perm_diff, "变了" if struct_diff else "没变",
                   [(base_struct.get(r) or {}).get("defaultPreset") for r in perm_diff],
                   [now_struct[r].get("defaultPreset") for r in perm_diff]))
    if diff and not struct_diff:
        return ("PASS",
                "哈希变了但**结构指纹与安全相关键都一致** ⇒ 是值级/空白级改动（%s）；"
                "默认档仍是 %s" % (",".join(sorted(diff)), _preset_of(now_struct)))
    if struct_diff:
        return ("PENDING",
                "**结构变了**（键增删/缩进）：%s —— 需人看一眼；默认档 %s"
                % (struct_diff, _preset_of(now_struct)))
    return ("PASS", "DSH 配置面哈希与基线一致（%d 项）；默认档 %s"
            % (len(now), _preset_of(now_struct)))

# B5：DSH 的内部标识 —— 壳里出现这些就说明它伸手进了 DSH 内部
# 2026-10-26：`@deepseek-ai/` 从**前缀匹配**改为**按包名精确判**（见 `_dsh_internal_hits`）。
#    原因：前缀匹配会把官方 CLI 包名 `@deepseek-ai/dsh` 也判成"内部包"，
#    而那条 CLI 是主人 2026-10-23 明确放行的（壳靠它起对话面）。
DSH_INTERNAL = ("dsh-compaction", "dsh-command-",
                "node_modules/@deepseek-ai", "__DSH_BOOT__")
# 唯一放行的官方 CLI 包（`@deepseek-ai/dsh`）。除它以外的 `@deepseek-ai/<x>` 仍算内部包。
ALLOWED_DSH_NPM = "dsh"


def _dsh_internal_hits(text: str) -> list:
    """一段源码里命中的 DSH 内部标识（**精确到包名**，不是前缀）。

    抽成函数是为了能单测/喂负对照：`@deepseek-ai/dsh` 必须放过，
    `@deepseek-ai/dsh-compaction` / `@deepseek-ai/other` / `node_modules/@deepseek-ai` 必须命中。
    """
    hits = [t for t in DSH_INTERNAL if t in text]
    for m in re.finditer(r"@deepseek-ai/([A-Za-z0-9._-]+)", text):
        if m.group(1) != ALLOWED_DSH_NPM:
            hits.append("@deepseek-ai/" + m.group(1))
    return sorted(set(hits))


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    if p.is_dir():
        for f in sorted(x for x in p.rglob("*") if x.is_file()):
            h.update(f.relative_to(p).as_posix().encode())
            h.update(b"\0")
            try:
                h.update(f.read_bytes())
            except OSError:
                h.update(b"<unreadable>")
            h.update(b"\0")
    else:
        try:
            h.update(p.read_bytes())
        except OSError:
            return "<unreadable>"
    return h.hexdigest()


# B2 加的这一层（2026-09-23）：**哈希只能证"被改过"，证不了"改了什么"**。
# 实测触发：`~/.dsh/settings.yaml` 在 07:08 被改，守卫只能报"被改过"——
# 我为了判断性质，得另外去翻备份、做键级 diff（还得小心别把值打出来）。
# ⇒ 把**结构指纹**与**安全相关键{的值}**一起记进基线：
#    · 结构指纹 = 排序后的"键名 + 缩进"再取哈希 ⇒ 只动值不动结构时它不变；
#    · 安全相关键 = **只挑权限/默认档这类**（下面白名单），**不含任何凭据**。
SENSITIVE_KEYS = ("defaultPreset", "default", "sandbox", "danger-full-access")


def _settings_structure(p: Path) -> dict:
    """settings.yaml 的**结构指纹 + 安全相关键**（不落内容、不落凭据）。"""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"keys_sha256": "<unreadable>"}
    pairs = []
    vals = {}
    for line in text.splitlines():
        m = re.match(r"^(\s*)([A-Za-z0-9_.-]+)\s*:", line)
        if m:
            pairs.append("%s|%s" % (len(m.group(1)), m.group(2)))
        for k in ("defaultPreset",):
            mm = re.match(r"^\s*%s\s*:\s*(.*)$" % re.escape(k), line)
            if mm:
                vals[k] = mm.group(1).strip()
    out = {"keys_sha256": hashlib.sha256("\n".join(pairs).encode()).hexdigest()[:16],
           "keys_n": len(pairs), "lines_n": len(text.splitlines())}
    out.update(vals)
    return out


def _listening(port: int) -> list:
    """谁会听这个端口。Windows 走 netstat（不依赖 psutil）。"""
    pids = []
    try:
        # 2026-10-04 修：netstat 输出是 ANSI(GBK)；text=True 无编码在 UTF-8 模式下
        # 读线程直接 UnicodeDecodeError ⇒ 守卫的 B1a/FAIL 详情被吞。按 mbcs 解。
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                             capture_output=True, encoding="mbcs", errors="replace",
                             timeout=30)
        for line in (out.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
                if parts[1].rstrip(":").endswith(":%d" % port):
                    pids.append(parts[4])
    except Exception:                                               # noqa: BLE001
        pass
    return sorted(set(pids))


def _read_sources() -> dict:
    out = {}
    for p in SHELL_SOURCES + INERT_SOURCES:
        try:
            out[str(p.relative_to(ROOT))] = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            pass
    return out


def _http_status(url: str, timeout: float = 6.0):
    """取一个 URL 的状态码（取不到返回 None）。只发一个 GET，不带任何凭据。"""
    import urllib.error
    import urllib.request
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "gbt-shell-guard"}),
                                   timeout=timeout)
        return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:                                               # noqa: BLE001
        return None


def _window_a_local(srcs: dict) -> tuple:
    """窗 A 现在载**本地页**吗 → (是否本地, windows.json 里登记的 file)。

    判据只认注册表里的实参：`url` 为空 + `file` 非空 = 改道本地。**不看"出现过 3080"**。
    """
    for k, v in (srcs or {}).items():
        if not k.endswith("windows.json"):
            continue
        try:
            reg = json.loads(v)
        except Exception:                                           # noqa: BLE001
            return False, ""
        for w in (reg.get("windows") or []):
            if w.get("id") == "dsh-chat":
                u, f = str(w.get("url") or ""), str(w.get("file") or "")
                return (not u and bool(f)), f
    return False, ""


def _page_ok(rel: str) -> tuple:
    """窗 A 声明的本地页**真的在盘上且非空**吗 → (ok, 字节数)。

    改道的代价是"页可能根本没打包进去"。所以 NA 之前必须核这一格，
    否则"不适用"就成了替一个坏页面打掩护。
    """
    name = rel.replace("\\", "/").lstrip("./")
    for base in (SHELL_DIR, ROOT):
        p = base / name
        if p.is_file():
            n = p.stat().st_size
            return (n > 0), n
    return False, 0


def _b1a_verdict(dsh_pids: list, window_a_local: bool) -> tuple:
    """B1a 的**判定本体**（纯函数 —— 读真环境的判据必须抽出来，负对照才喂得进去）。"""
    if dsh_pids:
        return ("PASS", "DSH web 在 %d 听，pid=%s —— 旧路活着，没被壳弄坏"
                % (DSH_PORT, ",".join(dsh_pids)))
    if window_a_local:
        return ("NA", "窗 A 已改载本地页（不经 DSH）⇒ 「DSH 在听」对本产品**不适用**，"
                      "不是欠账。旧路保留：主人起 `dsh web` 时这一条会自动回到 PASS")
    return ("PENDING", "DSH web 未启动（%d 无监听）—— 环境态，不是壳破坏" % DSH_PORT)


def _b1d_verdict(status, dsh_pids: list, window_a_local: bool,
                 page_ok: bool, page_rel: str, page_bytes: int) -> tuple:
    """B1d 的**判定本体**（纯函数）。

    这一条守的是「窗 A 到底载得进来吗」。窗 A 改道本地页之后，真正该判的是
    **那个本地页在不在、空不空**；旧路的 200/401 只在主人走 DSH 时才有意义。
    """
    if status == 200:
        return ("PASS", "对话面裸 URL 就回 200 —— 可以直接嵌")
    if status == 401:
        return ("PENDING",
                "对话面回 **401**（`dsh web authentication required`）⇒ 要 **`dsh web` 打印的带 token URL**；"
                "守卫**不碰凭据**，这一格只能由「主人真接上一次」来关 —— 那是 B1e 的事")
    if dsh_pids:
        return ("FAIL", "DSH web 在跑但状态码异常：%s（既不是 200 也不是 401）" % status)
    if window_a_local:
        if page_ok:
            return ("NA", "窗 A 载本地页 %s（%d 字节，非空且可读）⇒ 旧路对话面可载性**不适用**；"
                          "该页存在性由本条实际核过" % (page_rel, page_bytes))
        return ("FAIL", "窗 A 声明载本地页 %s，但**盘上找不到或为空** —— 那是真坏（不是不适用）"
                % (page_rel or "<未登记>"))
    return ("PENDING", "DSH web 没在跑（状态=%s）—— 无可探，且窗 A 没登记本地页" % status)


def _source_checks(srcs: dict, dsh_port: int) -> list:
    """只依赖壳源码的那几条（B1b/B1c/B3-listen/B4/B5/B6）。

    单独抽出来是为了**能被负对照喂假输入** —— 一个只会说 PASS 的守卫等于没有守卫。
    """
    import urllib.parse as _up
    out = []

    def add(cid, state, detail):
        out.append({"id": cid, "state": state, "detail": detail})

    # ── B1b 窗 A 的**真实状态**（不许拿"出现过 3080 这个数字"当嵌入成功）──
 # 自查：第一版判据是 `str(3080) in 源码` —— 于是 windows.json 里一句 `"port": 3080`
    # 就让它报"对话面已嵌入"。**那是假的**：那个窗打开的是本地引导页（connect.html），
    # 真页面要带 token 的 URL 才载得进来。判据必须看 **`url` 实参**与 `needs_url` 声明。
    # 2026-10-04 起窗 A 改载**原生 DeepSeek 网页**（主人令，旧 DSH 链 :3080 留档）——
    # 判据跟进：窗 A 的 url 必须是**白名单内**的外部主机（否则任何人都可能把对话窗
    # 指到任意站点还让 B1b 报绿）。
    wreg, said = None, None
    for k, v in srcs.items():
        if k.endswith("windows.json"):
            try:
                wreg = json.loads(v)
            except Exception:                                       # noqa: BLE001
                pass
    if wreg is not None:
        wins = wreg.get("windows") or []
        real = [w for w in wins
                if (w.get("url") or "") and str(dsh_port) in str(w.get("url"))]
        needs = [w for w in wins if w.get("needs_url")]
        chat = [w for w in wins if w.get("id") == "dsh-chat"]
        chat_url = str((chat[0].get("url") or "")) if chat else ""
        chat_file = str((chat[0].get("file") or "")) if chat else ""
        chat_host = (_up.urlparse(chat_url).hostname if chat_url else "") or ""
        if chat_url and chat_host in ALLOWED_EXTERNAL_HOSTS:
            said = ("PASS", "窗 A(dsh-chat) 已直载白名单外部对话面 https://%s（主人令 2026-10-04）"
                    % chat_host)
        elif not chat_url and chat_file:
            # 2026-10-04 定性改道：DeepSeek 风控判 Electron 环境异常（无痕/持久档同弹，
            # 对照见 shell/chat-probe.cjs）⇒ 窗 A 改载**本地 GBT 对话面**，外部对话移主人 Chrome。
            said = ("PASS", "窗 A(dsh-chat) 载**本地 GBT 对话面** %s（DeepSeek 判 Electron 环境异常后改道；"
                            "外部对话在主人 Chrome + Nanobrowser）" % chat_file)
        elif chat_url and chat_host:
            said = ("FAIL", "窗 A(dsh-chat) 的 url 指向白名单外的主机 %s —— 外部点名制不许这么指"
                    % chat_host)
        elif real:
            said = ("PASS", "注册表里已有指向 %d 的**真 URL** 窗：%s"
                    % (dsh_port, [w.get("id") for w in real]))
        elif needs:
            said = ("PENDING", "窗 A%s 已登记，但**走的是本地引导页**（`needs_url`）—— "
                              "真页面要 `dsh web` 打印的**带 token URL** 才载得进来（见 B1d）"
                    % [w.get("id") for w in needs])
        else:
            said = ("PENDING", "注册表里还没有对话面的窗（P1 期产物）")
    else:
        said = ("PENDING", "读不到 windows.json ⇒ 判不了（不猜）")
    add("B1b", said[0], said[1])

    proxy_hits = [k for k, v in srcs.items()
                  if re.search(r"(proxy|转发|forward)\w*[^\n]{0,40}(%d|dsh)" % dsh_port, v, re.I)]
    add("B1c", "FAIL" if proxy_hits else "PASS",
        "壳里%s代理/重做对话协议" % ("**有**" + str(proxy_hits) if proxy_hits else "没有"))

    bad = [k for k, v in srcs.items() if re.search(r"listen\s*\(\s*%d" % dsh_port, v)]
    shell_server = [k for k, v in srcs.items() if re.search(r"createServer\s*\(|\.listen\s*\(", v)]
    add("B3x", "FAIL" if bad else "PASS",
        "壳自身%s监听 DSH 端口" % ("**新增了**" + str(bad) if bad else "没有新增")
        + ("；壳内出现 createServer/listen：%s（需人确认不是给 DSH 添端口）" % shell_server
           if shell_server else ""))

    inject = [k for k, v in srcs.items()
              if re.search(r"executeJavaScript|insertCSS|webRequest\.onBeforeRequest", v)]
    # 2026-10-04 主人令「她能直接操控触手能力来实现自主运行」⇒ 判据从「一律不许注入」
    # 改为**注入收口到一个模块**：只允许 deepseek_loop.cjs（只读她的正文回复 +
    # 写回输入框；执行腿全在 Python 桥的唯一门里）。别的文件出现注入一律 FAIL ——
    # 尤其防「顺手往别的窗也塞脚本」这种扩散。
    allowed = [k for k in inject if k.endswith("deepseek_loop.cjs")]
    bad_inject = [k for k in inject if k not in allowed]
    if bad_inject:
        add("B4", "FAIL",
            "**注入越界**（允许名单外）：%s —— 只许收口在 deepseek_loop.cjs" % bad_inject)
    elif allowed:
        add("B4", "PASS", "注入收口：只出现在自主回路模块 deepseek_loop.cjs（主人令授权的自主运行件）")
    else:
        add("B4", "PASS", "壳里没有任何注入（自主回路模块未装或已摘）")

 # 2026-10-26 精确化：`@deepseek-ai/` 作为**前缀**会把官方 CLI 包名
    #    `@deepseek-ai/dsh` 一起判红 —— 而那条 CLI 正是**主人 2026-10-23 明确放行**的
    #    （壳要用它起对话面；2026-10-26 又按主人令改用 npx 形式，命令里必然出现这个包名）。
    #    "不许依赖 DSH 内部源码路径"的本意仍在：`node_modules/@deepseek-ai`（源码路径）、
    #    `@deepseek-ai/<其它内部包>` 一律照旧红。⇒ 只在**包名第二段**上开一个精确口子。
    hits = {k: _dsh_internal_hits(v) for k, v in srcs.items()}
    hits = {k: v for k, v in hits.items() if v}
    add("B5", "FAIL" if hits else "PASS",
        "壳里%s DSH 内部包/源码路径%s"
        % ("**出现**" + str(sorted(hits)) if hits else "没有",
           "（已按主人 2026-10-23 令放行官方 CLI 包名 `@deepseek-ai/dsh`）" if not hits else ""))

    # ── B6：URL 白名单 —— 壳不许变成"通用浏览器" ──
    # `loadURL` 一旦不限域，这个常驻托盘壳就能打开任意网页（不同安全面）。
    # 规则（2026-10-04 起）：**回环 ∪ 点名外部白名单（仅 https）**；注册表里任何
    # 白名单外的 url 都判 FAIL。白名单 = ALLOWED_EXTERNAL_HOSTS（与 url-policy.cjs 互绑）。
    off_loop = []
    for k, v in srcs.items():
        if not k.endswith("windows.json"):
            continue
        try:
            reg = json.loads(v)
        except Exception:                                           # noqa: BLE001
            add("B6", "FAIL", "windows.json 解析失败 —— 注册表坏了，不许打包")
            return out
        for w in (reg.get("windows") or []):
            u = w.get("url")
            if not u:
                continue
            try:
                host = _up.urlparse(u).hostname or ""
                scheme = _up.urlparse(u).scheme or ""
            except Exception:                                       # noqa: BLE001
                host, scheme = "", ""
            if host in ("127.0.0.1", "localhost", "::1"):
                continue
            if host in ALLOWED_EXTERNAL_HOSTS:
                if scheme != "https":
                    off_loop.append("%s -> %s（白名单外部主机必须 https）" % (w.get("id"), u))
                continue
            off_loop.append("%s -> %s" % (w.get("id"), u))
    guard_present = any("LOOPBACK_HOSTS" in v and "loopbackUrlOnly" in v for v in srcs.values())
    add("B6", "FAIL" if off_loop else ("PASS" if guard_present else "PENDING"),
        ("注册表里**有白名单外的 url**：" + str(off_loop)) if off_loop
        else ("url 白名单在壳里（回环 ∪ 点名外部主机）" if guard_present
              else "窗里还没有 url，白名单也还没装（PENDING）"))

    # ── B7：**带 token 的 URL 不许回显**（凭据卫生）──
    # 窗 A 的 URL 里带 DSH 的会话令牌。它一旦被回给渲染进程，就会进界面/日志/截图。
    # 这一格钉两件事：口子存在（`loadURL`）、且返回值**只给 host 不给 url**。
 # 这是**钉子**不是安全边界（文本级判定，可以被绕过）—— 它的价值是"改的人当场看见"。
    port_hits = []
    for k, v in srcs.items():
        if not k.endswith("main.cjs"):
            continue
        i = v.find("function w3ConnectDsh(")
        if i < 0:
            port_hits.append("缺少 w3ConnectDsh（运行时接对话面的口子）")
            continue
        body = v[i:i + 1600]
        if "loadURL(" not in body:
            port_hits.append("w3ConnectDsh 里没有 loadURL —— 那它没在接对话面")
        if "loopbackUrlOnly(" not in body:
            port_hits.append("w3ConnectDsh 没过回环白名单")
        if "host:" not in body:
            port_hits.append("返回值没有 host —— 那它多半把整条 URL 回显了")
 # 2026-10-26 修：原来这里是 `if "url:" in body` —— 全文匹配，会把
        #    `lastDshEntry = { url: chk.url, host: … }` 这种**内部存储**也判成"回显"。
        #    主进程**必须**留下入口 URL（`w3:dsh-mount` 要用它去 loadURL 那个 webview；
        #    2026-10-26 起 URL 干脆不进渲染进程了）。把它判红，只会逼人把变量改名来绕判据 ——
        #    **那才是假绿**（判据看着还在，其实被绕过去了）。
        #    ⇒ 只认**`return` 出去的**那段里有没有 `url` 键：
        #       "回显给渲染进程"才叫回显，"主进程自己记着"不是。
        #    负对照钉着这条（`_selftest` 里那条 "返回值带上 url 必须见红"）。
        returns = [m.group(1) for m in re.finditer(r"\breturn\b([^;]{0,300})", body)]
        if any(re.search(r"\burl\s*:", seg) for seg in returns):
            port_hits.append("返回值里出现 `url:` —— **带 token 的 URL 不许回显**")
    add("B7", "FAIL" if port_hits else "PASS",
        ("口子有问题：" + str(port_hits)) if port_hits
        else "窗 A 的口子：过白名单 · loadURL · **只回 host、不回显 URL**")

    # ── B8：快照页惰性 + 立体层真三维（2026-09-23 加）──
    out.extend(_inert_checks(srcs))
    return out


def _root_split(css: str) -> tuple:
    """把 CSS 拆成 `(第一个 :root 块内容, 其余)`。解析不出来返回 `(None, None)`。

    与 `holo_pet_w3/tests/test_brand_tokens.cjs` **同一套判据**（取第一个 `:root{…}`）——
    一处定义、两处引用；口径不同就会互相打架（本仓最贵的教训）。
    """
    i = css.find(":root")
    if i < 0:
        return None, None
    o = css.find("{", i)
    c = css.find("}", o) if o >= 0 else -1
    if o < 0 or c < 0:
        return None, None
    return css[o + 1:c], css[:o] + css[c + 1:]


def _inert_checks(srcs: dict) -> list:
    """B8：快照页与立体层必须**惰性**，且立体必须是**真三维**（不是"加了个阴影"）。

    两件事各管一半：

    **惰性** —— 这个壳是常驻托盘的。快照页一旦带了 `<script>`、内联事件、或任何远端引用，
    就等于在桌面上长期开了一条可执行/可出网的面。加这一格是为了让"为了再炫一点塞段 JS"
    这个动作**当场变红**，而不是等谁哪天注意到。
    立体观感因此**全部由 CSS 完成** —— 这不是将就，是本层能成立的前提。

    **真三维** —— 风哥要的是立体**冲击**，不是投影。所以下面五项是**契约**，缺一项就说明
    退化成了平面：`perspective`（透视）· `preserve-3d`（分层）· `translateZ`（层距）·
    `@keyframes`（自转）· `prefers-reduced-motion`（有人管前庭敏感与耗电）。
    最后一项不是可选项：持续动画不理会系统偏好，对人是伤害、对笔记本是白耗电。

    另守《holo_petUI规格》§2.1：**裸色值只允许在第一个 `:root` 块里**（对立体层同样生效）。
    """
    out = []

    def add(cid, state, detail):
        out.append({"id": cid, "state": state, "detail": detail})

    decks = {k: v for k, v in srcs.items() if k.endswith("index.html") and "deck" in k}
    css = ""
    css_key = ""
    for k, v in srcs.items():
        if k.endswith("deck3d.css"):
            css, css_key = v, k
    if not decks and not css:
        add("B8", "PENDING", "还没有快照页/立体层（P1 期产物）")
        return out

    bad = []
    for k, v in sorted(decks.items()):
        if re.search(r"<script", v, re.I):
            bad.append("%s 里有 <script> —— 快照页必须是死的" % k)
        if re.search(r"\son[a-z]+\s*=", v, re.I):
            bad.append("%s 里有内联事件处理（on*=）—— 那是换了写法的脚本" % k)
        if re.search(r"https?://", v, re.I):
            bad.append("%s 里有远端引用 —— 断网就会坏，且多一条出网面" % k)
        if css_key and "deck3d.css" not in v:
            bad.append("%s 宣称立体，却没引 %s —— 那它其实是平面"
                       % (k, Path(css_key).name))

    if css:
        if re.search(r"@import", css, re.I):
            bad.append("立体层里有 @import —— 外链样式表能把远端拉进来")
        if re.search(r"url\(\s*['\"]?https?:", css, re.I):
            bad.append("立体层里有远端 url() —— 同上")
        if re.search(r"<script", css, re.I):
            bad.append("立体层里有 <script> —— CSS 文件不该有脚本")
        for token, why in (("perspective", "没有 perspective ⇒ 没有透视"),
                           ("preserve-3d", "没有 preserve-3d ⇒ 分了层也不成立（最常见的哑火点）"),
                           ("translateZ", "没有 translateZ ⇒ 所有层都在同一平面"),
                           ("@keyframes", "没有 @keyframes ⇒ 是静止的，没有「冲击」"),
                           ("prefers-reduced-motion", "没有 prefers-reduced-motion ⇒ 无视系统偏好")):
            if token not in css:
                bad.append("立体层 %s" % why)
        inner, outer = _root_split(css)
        if inner is None:
            bad.append("立体层读不出 :root 块 —— 判不了裸色值（不猜）")
        else:
            raw = re.findall(r"(#[0-9a-fA-F]{3,8}\b|rgba?\()", outer)
            if raw:
                bad.append("立体层在 :root 之外出现 %d 处裸色值（%s…）—— 违反《holo_petUI规格》§2.1"
                           % (len(raw), ", ".join(sorted(set(raw))[:4])))

    add("B8", "FAIL" if bad else "PASS",
        ("**有 %d 处**：" % len(bad) + "；".join(bad[:4]) + ("…" if len(bad) > 4 else "")) if bad
        else ("快照页 %d 个**零脚本零外链**，立体层真三维（透视/分层/层距/自转/无障碍五项齐）"
              "，且裸色值只在 :root 里" % len(decks)))
    return out


# B8 负对照用的**假样本**（故意做成"合格的"，再逐项破坏一项看守卫认不认）。
# 它们是**合成文本**，不是真文件 —— 所以不会因为真页面改版而失效。
_FAKE_CSS_OK = (
    ":root{--gbt-cyan:#00E5FF;--gbt-glass:rgba(14,19,40,.52)}\n"
    ".gbt-stage{perspective:1200px}\n"
    ".gbt-board{transform-style:preserve-3d}\n"
    ".z-near{transform:translateZ(40px)}\n"
    "@keyframes gbt-orbit{0%{opacity:1}100%{opacity:.6}}\n"
    "@media (prefers-reduced-motion: reduce){.gbt-board{animation:none}}\n"
)
_FAKE_DECK_OK = (
    "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
    "<link rel=\"stylesheet\" href=\"../deck3d.css\"></head>"
    "<body class=\"gbt-stage\"><div class=\"gbt-board\"></div></body></html>"
)


def _selftest() -> int:
    """负对照：故意喂"已经破坏了 DSH"的假壳源，守卫**必须逐条喊出来**。

    分辨不出"破坏"的守卫 = `SCANNER_BLIND`，不许报 PASS（《扫描器自证律》）。
    """
    cases = [
        ("干净", {"a.cjs": 'loadURL("http://127.0.0.1:3080")'}, {}),
        ("代理对话协议", {"a.cjs": "const dshProxy = proxyTo(3080)"}, {"B1c": "FAIL"}),
        ("自己监听 DSH 端口", {"a.cjs": "srv.listen(3080)"}, {"B3x": "FAIL"}),
        ("往对话窗注入脚本", {"a.cjs": "win.webContents.executeJavaScript('x')"}, {"B4": "FAIL"}),
        # 2026-10-04 收口制：注入只许在 deepseek_loop.cjs；同一行代码换个文件就红/绿
        ("注入收口在自主回路模块", {"deepseek_loop.cjs":
            "win.webContents.executeJavaScript(READ_JS, true)"}, {"B4": "PASS"}),
        ("注入扩散到别的文件", {"deepseek_loop.cjs":
            "win.webContents.executeJavaScript(READ_JS, true)",
            "features.cjs": "win.webContents.executeJavaScript('偷看')"}, {"B4": "FAIL"}),
        ("依赖 DSH 内部包", {"a.cjs": 'require("@deepseek-ai/dsh-compaction")'}, {"B5": "FAIL"}),
        ("没建对话窗", {"a.cjs": "loadFile('x.html')"}, {"B1b": "PENDING"}),
        # B6：壳不许变成通用浏览器
        ("注册了外部站点", {"windows.json": json.dumps(
            {"windows": [{"id": "evil", "url": "https://example.com/"}]})}, {"B6": "FAIL"}),
        ("只注册回环站点", {"a.cjs": "const LOOPBACK_HOSTS=new Set();function loopbackUrlOnly(u){}",
                       "windows.json": json.dumps(
                           {"windows": [{"id": "ok", "url": "http://127.0.0.1:3080/"}]})}, {"B6": "PASS"}),
        # 2026-10-04 白名单点名制：白名单内 https 外部主机合法；http 或白名单外主机都红
        ("注册白名单内 DeepSeek", {"a.cjs": "const LOOPBACK_HOSTS=new Set();function loopbackUrlOnly(u){}",
                           "windows.json": json.dumps(
                               {"windows": [{"id": "dsh-chat",
                                             "url": "https://chat.deepseek.com/"}]})},
         {"B1b": "PASS", "B6": "PASS"}),
        ("白名单主机走了 http", {"a.cjs": "const LOOPBACK_HOSTS=new Set();function loopbackUrlOnly(u){}",
                          "windows.json": json.dumps(
                              {"windows": [{"id": "dsh-chat",
                                            "url": "http://chat.deepseek.com/"}]})},
         {"B6": "FAIL"}),
        ("对话窗指向白名单外", {"a.cjs": "const LOOPBACK_HOSTS=new Set();function loopbackUrlOnly(u){}",
                         "windows.json": json.dumps(
                             {"windows": [{"id": "dsh-chat",
                                           "url": "https://evil.example.net/"}]})},
         {"B1b": "FAIL", "B6": "FAIL"}),
        # B7：带 token 的 URL 不许回显
        ("回显了带 token 的 URL", {"main.cjs":
            "function w3ConnectDsh(p){const chk=loopbackUrlOnly(p.url);"
            "win.loadURL(chk.url);return {ok:true,host:'x',url:chk.url}}"}, {"B7": "FAIL"}),
        ("只回 host", {"main.cjs":
            "function w3ConnectDsh(p){const chk=loopbackUrlOnly(p.url);"
            "win.loadURL(chk.url);return {ok:true,host:'127.0.0.1:3080'}}"}, {"B7": "PASS"}),
 # 2026-10-26 改判据后的**边界对**（内部存储 vs 真回显）——
        #    判据从「全文找 `url:`」改成「只看 `return` 出去的那段」，那就**必须**证明
        #    "放宽的只有内部存储，回显照旧红"。没有这一对，这次改动就是"把判据改宽了"。
        ("内部记着入口 url、但只回 host（合法：主进程要留 URL 去 loadURL 那个 webview）",
         {"main.cjs":
             "function w3ConnectDsh(p){const chk=loopbackUrlOnly(p.url);"
             "lastDshEntry={url:chk.url,host:'h'};"
             "win.loadURL(chk.url);return {ok:true,host:'h'}}"}, {"B7": "PASS"}),
        ("内部记着 url **且 return 里也带 url**（负对照：真回显必须红）",
         {"main.cjs":
             "function w3ConnectDsh(p){const chk=loopbackUrlOnly(p.url);"
             "lastDshEntry={url:chk.url,host:'h'};"
             "win.loadURL(chk.url);return {ok:true,host:'h',url:chk.url}}"}, {"B7": "FAIL"}),
 # B5 的**边界对**（2026-10-26 判据从"前缀"改"包名"之后必须证明放宽有边界）：
        #    官方 CLI 包名 `@deepseek-ai/dsh` 放行（主人 2026-10-23 令，壳靠它起对话面）；
        #    其余 `@deepseek-ai/<x>` 与源码路径照旧红。
        ("B5 放行官方 CLI 包名 @deepseek-ai/dsh（壳要用它起对话面）",
         {"dsh-launch.cjs": 'const DSH_CLI = "npx --yes @deepseek-ai/dsh";'},
         {"B5": "PASS"}),
        ("B5 负对照：@deepseek-ai/ 下**别的包**仍必须红",
         {"a.cjs": 'require("@deepseek-ai/dsh-compaction")'}, {"B5": "FAIL"}),
        ("B5 负对照：DSH 源码路径 node_modules/@deepseek-ai 仍必须红",
         {"a.cjs": 'const p = "node_modules/@deepseek-ai/x/index.js";'}, {"B5": "FAIL"}),
        # B8：快照页惰性 + 立体层真三维（五项契约）
 # 每条负对照都带**第二个样本 = 干净对**：既要证明"改坏了守卫会红"，
        #    也要证明"没改坏时守卫不红"。首跑就是靠这条抓到"内联事件那条根本没改到"——
        #    `replace("<body>", …)` 打不中 `<body class="gbt-stage">`，样本没变 ⇒ 检查看着像瞎的。
        ("立体层齐活的干净对", {"deck3d.css": _FAKE_CSS_OK,
                           "exec-deck/index.html": _FAKE_DECK_OK}, {"B8": "PASS"},
         {"deck3d.css": _FAKE_CSS_OK, "exec-deck/index.html": _FAKE_DECK_OK}),
        ("快照页塞了脚本", {"deck3d.css": _FAKE_CSS_OK,
                       "exec-deck/index.html": _FAKE_DECK_OK + "<script>alert(1)</script>"},
         {"B8": "FAIL"}, {"deck3d.css": _FAKE_CSS_OK, "exec-deck/index.html": _FAKE_DECK_OK}),
        ("快照页用内联事件", {"deck3d.css": _FAKE_CSS_OK,
                        "exec-deck/index.html": _FAKE_DECK_OK.replace(
                            "<body", '<body onload="go()"', 1)},
         {"B8": "FAIL"}, {"deck3d.css": _FAKE_CSS_OK, "exec-deck/index.html": _FAKE_DECK_OK}),
        ("快照页引远端资源", {"deck3d.css": _FAKE_CSS_OK,
                        "exec-deck/index.html": _FAKE_DECK_OK + '<img src="https://cdn.x/a.png">'},
         {"B8": "FAIL"}, {"deck3d.css": _FAKE_CSS_OK, "exec-deck/index.html": _FAKE_DECK_OK}),
        ("宣称立体却没引立体层", {"deck3d.css": _FAKE_CSS_OK,
                          "exec-deck/index.html": _FAKE_DECK_OK.replace("deck3d.css", "x.css")},
         {"B8": "FAIL"}, {"deck3d.css": _FAKE_CSS_OK, "exec-deck/index.html": _FAKE_DECK_OK}),
        ("立体层少了 preserve-3d", {"deck3d.css": _FAKE_CSS_OK.replace("preserve-3d", "flat"),
                              "exec-deck/index.html": _FAKE_DECK_OK}, {"B8": "FAIL"},
         {"deck3d.css": _FAKE_CSS_OK, "exec-deck/index.html": _FAKE_DECK_OK}),
        ("立体层少了无障碍照顾", {"deck3d.css": _FAKE_CSS_OK.replace("prefers-reduced-motion", "x"),
                           "exec-deck/index.html": _FAKE_DECK_OK}, {"B8": "FAIL"},
         {"deck3d.css": _FAKE_CSS_OK, "exec-deck/index.html": _FAKE_DECK_OK}),
        ("立体层外链了远端样式", {"deck3d.css": _FAKE_CSS_OK + "@import url(https://x/a.css);",
                          "exec-deck/index.html": _FAKE_DECK_OK}, {"B8": "FAIL"},
         {"deck3d.css": _FAKE_CSS_OK, "exec-deck/index.html": _FAKE_DECK_OK}),
        ("立体层 :root 之外写裸色值", {"deck3d.css": _FAKE_CSS_OK + ".x{color:#ff0000}",
                             "exec-deck/index.html": _FAKE_DECK_OK}, {"B8": "FAIL"},
         {"deck3d.css": _FAKE_CSS_OK, "exec-deck/index.html": _FAKE_DECK_OK}),
    ]
    bad = []
    print("=" * 78)
    print("负对照 · 守卫必须能分辨「破坏」")
    print("=" * 78)
    for case in cases:
        name, srcs, want = case[0], case[1], case[2]
        clean = case[3] if len(case) > 3 else None
        got = {r["id"]: r["state"] for r in _source_checks(srcs, DSH_PORT)}
        ok = all(got.get(k) == v for k, v in want.items())
        why = ""
        # ── 元检查①：这条负对照**真的改了东西**吗？──
        # 首跑实测：`replace("<body>", …)` 打不中 `<body class="gbt-stage">`，
        # 样本一字未变 ⇒ 检查报 PASS，看着像"守卫是瞎的"，其实是**负对照自己失效**。
        # 所以"改了没有"必须由守卫自己验，不能靠写的人记得。
        # 元检查只对**负对照**（期望出现非 PASS 态）生效：正对照本来就该"样本 = 干净对"。
        must_mutate = any(v != "PASS" for v in (want or {}).values())
        if ok and clean is not None and must_mutate and srcs == clean:
            ok, why = False, "样本与干净对**一字不差** —— 这条负对照没改到东西，它的结论不算数"
        # ── 元检查②：干净对**不许**报出同一条 FAIL（否则是误报）──
        if ok and clean is not None and must_mutate:
            cgot = {r["id"]: r["state"] for r in _source_checks(clean, DSH_PORT)}
            over = {k: cgot.get(k) for k, v in want.items() if v == "FAIL" and cgot.get(k) == "FAIL"}
            if over:
                ok, why = False, "干净对也被判 %s —— 那是**误报**，不是抓到了破坏" % over
        if not ok:
            bad.append((name, want, got, why))
        print("  %s %-16s 期望 %s ⇒ 实得 %s%s"
              % ("✅" if ok else "🔴", name, want or "（无 FAIL/PENDING）",
                 {k: got[k] for k in (want or got)}, ("  ← " + why) if why else ""))

    # ── B2 的负对照（2026-10-26 补）──
    # 为什么以前是空的：B2 的判定长在 `main()` 里、只读真环境 ⇒ 假输入**喂不进去** ⇒
    # "权限档被降级会不会红"从来没被证过。抽成 `_b2_verdict()` 纯函数才补得上这一组。
    print("-" * 78)
    print("负对照 · B2（权限档/结构 → 三态；判定本体已抽成纯函数才喂得进来）")
    print("-" * 78)
    REL = DSH_SETTINGS_REL
    _ok = {REL: {"defaultPreset": "danger-full-access", "keys_sha256": "s1"}}
    b2_cases = [
        # (名字, 基线哈希, 基线结构, 现哈希, 现结构, 期望)
        ("B2 一致（干净对）", {REL: "h1"}, _ok, {REL: "h1"}, _ok, "PASS"),
        ("B2 权限档被降级", {REL: "h1"}, _ok, {REL: "h1"},
         {REL: {"defaultPreset": "default", "keys_sha256": "s1"}}, "FAIL"),
        ("B2 仅值级改动", {REL: "h1"}, _ok, {REL: "h9"}, _ok, "PASS"),
        ("B2 结构变了", {REL: "h1"}, _ok, {REL: "h2"},
         {REL: {"defaultPreset": "danger-full-access", "keys_sha256": "s2"}}, "PENDING"),
        ("B2 新建了带权限档的配置（原来没有）", {REL: "<absent>"},
         {REL: {"keys_sha256": "<unreadable>"}}, {REL: "h1"}, _ok, "FAIL"),
    ]
    clean_in = (b2_cases[0][1], b2_cases[0][2], b2_cases[0][3], b2_cases[0][4])
    for name, bh, bs, nh, ns, want in b2_cases:
        state, detail = _b2_verdict(bh, bs, nh, ns)
        ok2 = (state == want)
        why2 = ""
        # 元检查：负对照必须**真的改了东西**（否则它证明的是"没改也不变"，不是"改了会红"）。
 # 比的是**四个输入全体**（基线哈希/基线结构/现哈希/现结构），不是只比现侧 ——
        #    首跑就把这条元检查自己照出了问题：有一条负对照的差异在**基线侧**（"原来没有该文件"），
        #    只比现侧会被误判成"没改到东西"。元检查写窄了，也会变成假红源。
        if ok2 and want != "PASS" and (bh, bs, nh, ns) == clean_in:
            ok2, why2 = False, "样本与干净对一字不差 —— 这条负对照没改到东西，结论不算数"
        if not ok2:
            bad.append((name, want, state, why2))
        print("  %s %-34s 期望 %-7s ⇒ 实得 %-7s%s"
              % ("✅" if ok2 else "🔴", name, want, state,
                 ("  ← " + why2) if why2 else " ｜ " + str(detail)[:58]))

    # ── B1a / B1d 的负对照（2026-10-28 补）──
    # 为什么必须有：这两条刚被改成四态，**NA 是新增的"放行"态** —— 放行态最容易被写成橡皮图章。
    # 下面第 ⑥ 条是这条新判据的**命门**：窗 A 声明载本地页、但那页不在 ⇒ 必须 FAIL，
    # 不许顺手判 NA。没有这一条，"不适用"就能替一个坏页面打掩护。
    print("-" * 78)
    print("负对照 · B1a/B1d 四态（NA 不许替坏页面打掩护）")
    print("-" * 78)
    b1_cases = [
        ("B1a DSH 在听", _b1a_verdict(["4321"], False), "PASS"),
        ("B1a 窗 A 改道本地页", _b1a_verdict([], True), "NA"),
        ("B1a 没 DSH 也没本地页", _b1a_verdict([], False), "PENDING"),
        ("B1d 裸 URL 回 200", _b1d_verdict(200, [], True, True, "x.html", 10), "PASS"),
        ("B1d 回 401（要主人给 token）", _b1d_verdict(401, ["1"], False, False, "", 0), "PENDING"),
        ("B1d DSH 在跑却回怪码", _b1d_verdict(None, ["1"], False, False, "", 0), "FAIL"),
        ("B1d 窗 A 本地页在且非空 ⇒ NA", _b1d_verdict(None, [], True, True, "connect.html", 11035), "NA"),
        ("B1d 窗 A 声明本地页但页不在 ⇒ 必须 FAIL（不许 NA）",
         _b1d_verdict(None, [], True, False, "connect.html", 0), "FAIL"),
    ]
    for name, (state, _detail), want in b1_cases:
        ok3 = (state == want)
        if not ok3:
            bad.append((name, want, state, ""))
        print("  %s %-40s 期望 %-7s ⇒ 实得 %-7s"
              % ("✅" if ok3 else "🔴", name, want, state))

    print("-" * 78)
    if bad:
        print("  🔴 负对照不过：守卫分辨不出破坏 ⇒ 它的 PASS 不算数")
        for n, w, g, why in bad:
            print("     %s: 期望 %s，实得 %s%s" % (n, w, g, ("  ← " + why) if why else ""))
        return 1
    print("  ✅ 负对照全过：守卫**能红**、且**改坏了才红**（每条都验过「改了没有」与「干净对不误报」）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="桌面壳 · 不破坏 DSH 守卫")
    ap.add_argument("--record-baseline", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="负对照：证明守卫真能红")
    ap.add_argument("--allow-pending", action="store_true",
                    help="开发期用：把 PENDING 当 0（**打包前不许加这个**）")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    if a.selftest:
        return _selftest()

    srcs = _read_sources()
    res = []

    def add(cid, state, detail):
        res.append({"id": cid, "state": state, "detail": detail})

    # ── B1a DSH 在听 ──
    # 2026-10-04 起窗 A 直载原生/本地对话页，DSH web 是**旧路**（保留、非必需）。
    # 2026-10-28 起：窗 A 走本地页时判 **NA（不适用）**，不再挂 PENDING ——
    #   「不用做」和「还没做」是两件事，混成一个黄灯就是在制造永久噪音。
    dsh_pids = _listening(DSH_PORT)
    a_local, a_file = _window_a_local(srcs)
    add("B1a", *_b1a_verdict(dsh_pids, a_local))

    # ── 只依赖壳源码的那几条（B1b/B1c/B3x/B4/B5）──
    res.extend(_source_checks(srcs, DSH_PORT))

    # ── B2 不动 DSH 配置（哈希比对）──
    now = {}
    for rel in DSH_WATCH:
        p = DSH_HOME / rel
        now[rel] = _sha(p) if p.exists() else "<absent>"
    base = {}
    if BASELINE.is_file():
        try:
            base = (json.loads(BASELINE.read_text(encoding="utf-8"))
                    .get("dsh_config_hashes") or {})
        except Exception:                                           # noqa: BLE001
            base = {}
    if a.record_baseline or not base:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps({
            "at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
            "dsh_config_hashes": now,
            "dsh_structure": {rel: _settings_structure(DSH_HOME / rel) for rel in DSH_WATCH},
            "ports": {"dsh": DSH_PORT, "panel": PANEL_PORT},
            "note": "只记哈希 + 结构指纹 + 安全相关键（defaultPreset 等），**不记内容/凭据**。B2/B3 拿它比。",
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        add("B2", "PASS", "首次记录基线（%d 项哈希 + 结构指纹）—— 此后拿它比" % len(now))
    else:
        # 哈希变了 ⇒ 再看**结构与安全相关键**变了没有：
        #   "值变了、结构没变、权限档没变" 与 "权限档被改" 是**两个量级**的事，
        #   糊成一句"被改过"，读的人只能自己去翻备份（2026-09-23 实测就是这样）。
 # 判定本体已抽到 `_b2_verdict()`（纯函数）：这里只取数、只落结论。
        #    抽出去的理由见那个函数的 docstring —— 一句话：不抽就永远没有负对照。
        st_base = (json.loads(BASELINE.read_text(encoding="utf-8")).get("dsh_structure") or {})
        st_now = {rel: _settings_structure(DSH_HOME / rel) for rel in DSH_WATCH}
        state, detail = _b2_verdict(base, st_base, now, st_now)
        add("B2", state, detail)

    # ── B3 端口面（源码侧的"有没有监听 DSH 端口"已由 B3x 报；这里只看端口实况）──
    panel_pids = _listening(PANEL_PORT)
    add("B3", "PASS" if panel_pids else "FAIL",
        "面板服务 %d %s（pid=%s）—— 桌面壳必须复用这个面，不许另起一个"
        % (PANEL_PORT, "在听" if panel_pids else "**未监听**", ",".join(panel_pids) or "无"))

    # ── B1d 对话面**可载性** ──
    # 裸 URL 回 401 ⇒ 窗 A 不是"loadURL 就完事"，它要 `dsh web` 打印的**带 token URL**。
    # 判据（2026-10-28 四态化）：200=PASS；401=PENDING（**要主人运行时给 URL，守卫不碰凭据**）；
    # DSH 在跑却回怪码=FAIL；DSH 没在跑**且窗 A 已改载本地页**=NA（但先核那个页在不在、空不空，
    #   不在 ⇒ FAIL ——「不适用」不许替一个坏页面打掩护）。
    st = _http_status("http://127.0.0.1:%d/" % DSH_PORT)
    p_ok, p_bytes = _page_ok(a_file) if a_file else (False, 0)
    add("B1d", *_b1d_verdict(st, dsh_pids, a_local, p_ok, a_file, p_bytes))

    # ── B1e 真接上过一次没有（读**不含凭据**的回执）──
    # 2026-10-08 修两处误判（实测 127.0.0.1:60463 被读成 FAIL）：
    #   ① 回执 host 只要**回环地址 + 数字端口**即算接上 —— 自动接龙在 3080 被占时
    #      按设计回退到动态口；旧口径「必须含 3080」会把它误判成 FAIL。
    #      「3080 老路活没活」另有 B1a 专盯，不必在回执里再要求一次。
    #   ② 「疑似含 URL/token」旧判据把回执**脚注里的字**当凭据（脚注写「不含 URL/token」
    #      ⇒ 命中 'token' ⇒ 自证式假红）。改成只认真凭据形状：[?&]token=<值>。
    import re as _re_b1e
    rc = ROOT / "state" / "desktop-dsh-connect-receipt.json"
    if rc.is_file():
        try:
            txt = rc.read_text(encoding="utf-8")
            j = json.loads(txt)
            h = str(j.get("host") or "")
            ok = bool(_re_b1e.match(r"^(127\.0\.0\.1|localhost|\[::1\]):\d{2,5}$", h))
            tok_like = bool(_re_b1e.search(r"[?&]token=[^\s&#\"']+", txt))
            add("B1e", "PASS" if (ok and not tok_like) else "FAIL",
                "接上过：host=%s at=%s（回环口 %s · %s；回执%s凭据参数）"
                % (h, j.get("at"),
                   "✓" if ok else "✗（不是回环 host:port）",
                   "3080 正路" if str(DSH_PORT) in h else "回退动态口",
                   "**疑似含**" if tok_like else "不含"))
        except Exception as e:                                      # noqa: BLE001
            add("B1e", "FAIL", "回执存在但读不动：%s" % str(e)[:80])
    else:
        add("B1e", "PENDING", "还没有接过（没有回执 `state/desktop-dsh-connect-receipt.json`）")

    # ── 报告 ──
    print("=" * 78)
    print("桌面壳 · 「不破坏 DSH」守卫（B1–B5）")
    print("=" * 78)
    print("  仓根 %s" % ROOT)
    print("  看的壳源：%d 个文件 %s" % (len(srcs), sorted(srcs)))
    print("-" * 78)
    for r in res:
        mark = {"PASS": "✅", "FAIL": "🔴", "PENDING": "⏳", "NA": "—"}[r["state"]]
        print("  %s %-5s %s" % (mark, r["id"], r["detail"]))
    n_fail = sum(1 for r in res if r["state"] == "FAIL")
    n_pend = sum(1 for r in res if r["state"] == "PENDING")
    n_na = sum(1 for r in res if r["state"] == "NA")
    n_pass = sum(1 for r in res if r["state"] == "PASS")
 # 先把退出码算出来、**打印出来**，最后再 return（2026-10-26 加）。
    #   为什么：`py guard.py | tail` / `| grep` / `> log` 这类写法会**吞掉进程退出码**，
    #   终端里 `echo $?` 拿到的是管道最后一环的 0 ⇒ 明明 FAIL 1，看着像"退出码 0 能打包"。
    #   实测已经骗过两次（一次是我自己看 --check，一次是主人看打包闸）。
    #   ⇒ 让守卫自己把真实值打在这一行，管道怎么接都改不了它。
    code = 1 if n_fail else (2 if (n_pend and not a.allow_pending) else 0)
    print("-" * 78)
    print("  PASS %d · FAIL %d · PENDING %d · NA %d" % (n_pass, n_fail, n_pend, n_na))
    print("  — NA = 明确不需要（不算欠账，也不算 PASS）。" if n_na else "")
    print("  ⚠️ PENDING **不算 PASS**（「还没做」不许读成「没问题」）。" if n_pend else "")
    print("  退出码：**0=全过可打包 · 1=有破坏不许打包 · 2=还没做完（不许宣称完成）**")
    print("  → **本次退出码 = %d**（这行是守卫自己打的；`| tail` / `| grep` / `> log` 都吞不掉它）"
          % code)
    if a.json:
        Path(a.json).write_text(json.dumps({"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
                                            "results": res, "fail": n_fail, "pending": n_pend},
                                           ensure_ascii=False, indent=1), encoding="utf-8")
        print("  产物: %s" % a.json)
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
