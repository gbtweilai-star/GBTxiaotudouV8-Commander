# -*- coding: utf-8 -*-
"""GPU 车道：用 llama.cpp 的 Vulkan 后端把部分层塞进显卡。

为什么不用最新版：llama.cpp b11840 的 Vulkan 后端在这台机器上**输出乱码**
（"北京GGGGGG"），而 b6000 同一份权重、同一块卡输出正确。已单独验过：
  b6000 + ngl12 = 5.40 tok/s 正确
  b11840 + ngl12 = 5.45 tok/s 乱码
所以版本钉死在 b6000。

还有一条硬纪律：**起了先自检**。不通就杀掉、如实报失败，让桥回落到 CPU 车道
—— 宁可慢，不许答错。

🔴 2026-10-28 换档（RX 6500M 4 GB 显存路线）：
  · 原来的 q5_0（4.88 GB）**装不进 4 GB 显存**，只能 ngl=12 半卸载、5.40 tok/s。
  · 新出 q3_k_m（3.55 GB）可整份上卡：llama-bench 实测 pp512 183.20 t/s、tg128 23.43 t/s。
  · 🔴 **2026-10-28 二次修正：ngl=99 撑不住环形窗口**。ctx 4096 就只剩 73 MB 余量，
    而 8192 全卸载直接 OOM（`alloc_tensor_range: failed to allocate Vulkan0 buffer
    of size 469762048`）。环形窗口预算是 12000 字符 ≈ **7011 token** ⇒ ctx 必须 ≥ 8192。
    实测 **ngl=24 + ctx=8192** 显存只要 3,727 MB，并能吃下满窗口：
    prompt 8078 token、事实埋在正中仍**命中**、生成 17.05 t/s。
    ⇒ 默认改成 **long 档（8192/24）**；`GBT_GPU_PROFILE=fast` 可回到 2048/99（23.19 t/s，
    但结构上装不下满预算窗口，短对话才用）。
  · 自检改打 **/v1/chat/completions**（APP 真实调用面）。原来打裸 /completion，
    模型在这个面上连 `1+1=` 都答 `4 ③ 侧`，把一条能跑的车道判死。
    判据本身的负对照见 `judge_selftest()`。

用法：
  python gpu_lane.py --start     起服务并自检（通了保持运行）
  python gpu_lane.py --check     只自检，通了退出 0
  python gpu_lane.py --selftest  只跑判据负对照（不起模型，秒出）
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
BIN_DIR = os.path.join(HERE, "bin", "llama-vulkan")
EXE = os.path.join(BIN_DIR, "llama-server.exe")
TAG = "b6000"
URL = "https://github.com/ggml-org/llama.cpp/releases/download/%s/llama-%s-bin-win-vulkan-x64.zip" % (TAG, TAG)
MODEL = os.environ.get("GBT_GPU_MODEL") or r"C:\gbtv8\state\weights\gbt-v8-v82-q3_k_m.gguf"
PORT = int(os.environ.get("GBT_GPU_PORT", "8793"))

# 两档都在这块卡上实测过（RX 6500M · 报告上限 4,080 MB）：
#   long：ctx 8192 / ngl 24 -> 满窗口针尖测试（12015 字 / 8078 token，事实埋在正中）
#         **命中**，生成 17.05 t/s，显存 3,727 MB，满窗口一发约 58 s
#   fast：ctx 2048 / ngl 99 -> 生成 23.19 t/s，显存 3,809 MB，
#         但 **装不下环形窗口的满预算**（12000 字符 = 7011 token）⇒ 会直接 500
# 🔴 所以默认取长档：环形窗口预算是 12000 字符，fast 档结构上撑不住它。
_PROFILE = (os.environ.get("GBT_GPU_PROFILE") or "long").strip().lower()
_PROFILES = {"long": (8192, 24), "fast": (2048, 99)}
_DEF_CTX, _DEF_NGL = _PROFILES.get(_PROFILE, _PROFILES["long"])
NGL = int(os.environ.get("GBT_GPU_NGL") or _DEF_NGL)


def log(msg):
    sys.stderr.write("[gpu] %s\n" % msg)
    sys.stderr.flush()


def ensure_bin() -> bool:
    if os.path.isfile(EXE):
        return True
    os.makedirs(BIN_DIR, exist_ok=True)
    z = os.path.join(BIN_DIR, "_dl.zip")
    log("下载 %s（约 22 MB）…" % TAG)
    r = subprocess.run(["curl.exe", "-L", "--fail", "-s", "-o", z, URL], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(z):
        log("下载失败：%s" % (r.stderr or "")[:120])
        return False
    with zipfile.ZipFile(z) as zf:
        zf.extractall(BIN_DIR)
    os.remove(z)
    log("解包到 %s" % BIN_DIR)
    return os.path.isfile(EXE)


_LOOP_IMPL = None


def _loop_impl():
    """回环探测实现：**优先用仓内唯一实现** `net_guard.loopback_open`，取不到才内联兜底。

    🔴 2026-10-28 实测：本机 `HTTP_PROXY=http://127.0.0.1:28016` 是全局的，而裸
    `urllib.request.urlopen` 对 127.0.0.1 **不自动 bypass** ⇒ 没人监听的端口被代理
    回成 `HTTPError 502 Bad Gateway`，与「服务在跑但报错」压成同一个错误类型。
    （判别证据与影响面见 `gbt_allinone/security/net_guard.py` 的 LOOPBACK_HOSTS 注释。）

    兜底**只复刻「强制直连」这一个姿势**；失败分档的判断不在这里重写。
    解析结果缓存在 `_LOOP_IMPL`：`healthy()` 在启动循环里每 2 秒调一次，不能每次都 import 包。
    """
    global _LOOP_IMPL
    if _LOOP_IMPL is not None:
        return _LOOP_IMPL
    try:
        if REPO not in sys.path:
            sys.path.insert(0, REPO)
        from gbt_allinone.security.net_guard import loopback_open as _f   # noqa: WPS433
        _LOOP_IMPL = _f
        return _LOOP_IMPL
    except Exception:                                            # noqa: BLE001
        pass
    _direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _fallback(url, timeout=1.5, **_kw):
        try:
            with _direct.open(url, timeout=timeout) as r:
                return {"ok": 200 <= r.status < 300, "kind": "ok", "status": r.status}
        except Exception as exc:                                 # noqa: BLE001
            return {"ok": False, "kind": "other", "status": None,
                    "detail": "%s: %s" % (type(exc).__name__, str(exc)[:80])}

    _LOOP_IMPL = _fallback
    return _LOOP_IMPL


def healthy(timeout=1.5) -> bool:
    return bool(_loop_impl()("http://127.0.0.1:%d/health" % PORT, timeout=timeout).get("ok"))


def _clean(txt) -> str:
    """剥掉模型爱加的 markdown 强调再判。

    `**北京**` 里的 `**` 是排版不是内容：不剥会把**完全正确**的回答判成"有噪声"。
    """
    return (txt or "").replace("**", "").replace("__", "").strip()


def judge(txt, expect_any, max_len: int = 24) -> tuple:
    """单条答案判脏/干净 —— **纯函数**，这样负对照才喂得进来。

    🔴 2026-10-28 为什么重写：原判据是 `len(txt) <= 12`，它拿"长度"当"没跑偏"
    的代理。同一个车道、同一份权重（q5_0，5243397568 字节），模型改答
    「北京，这在任何时间轴上都成立。」—— 14 字、语义完全正确 —— 就被判死。
    后果不是"报了个红"，是 `--start` **永远退 3**，GPU 车道一直是死的，
    而它真正想防的是"前半句对、后半句胡说"。现在改判三件事，每件都有真样本：
      ① 必须出现期望词；
      ② 剥 markdown 后 ≤ max_len（防往下胡写一整段）；
      ③ 不许有 ASCII 字母（历史脏样本 `它与idepressent…` / `zbx_brain` 都死在这条）。
    """
    t = _clean(txt)
    if not any(e in t for e in expect_any):
        return False, "缺期望词"
    if len(t) > max_len:
        return False, "答太长(%d>%d)" % (len(t), max_len)
    if any(c.isascii() and c.isalpha() for c in t):
        return False, "混入拉丁乱码"
    return True, "OK"


# 判据自己的负对照 + 干净对，每条都标出处。改 judge 必须先过这张表。
_JUDGE_CASES = [
    ("中国的首都是**北京**。", ["北京"], True, "chat 面正常回答（带 markdown 强调，必须剥）"),
    ("北京，这在任何时间轴上都成立。", ["北京"], True,
     "2026-10-28 实测：语义对、只是话多 —— 旧判据把这条判死，是判据自伤"),
    ("北京，那么 'zbx_brain' 这个", ["北京"], False, "2026-10-28 q3_k_m 裸补全实测脏样本"),
    ("北京；它与idepressent（有效的抗抑郁药）…", ["北京"], False,
     "2026-10-24 历史脏样本：旧判据靠长度抓到的正是这条"),
    ("4 ③ 侧", ["2", "二"], False, "2026-10-28 q5_0 裸补全答错样本"),
    ("2", ["2", "二"], True, "正确答案"),
]


def judge_selftest() -> int:
    bad = 0
    for txt, exp, want, why in _JUDGE_CASES:
        got, detail = judge(txt, exp)
        if got != want:
            bad += 1
            print("🔴 判错：%r 期望 %s 实得 %s（%s）" % (txt, want, got, detail))
    print("judge 自检：%d/%d 符合预期（负对照 %d 条）"
          % (len(_JUDGE_CASES) - bad, len(_JUDGE_CASES),
             sum(1 for c in _JUDGE_CASES if not c[2])))
    return 0 if bad == 0 else 1


def probe() -> tuple[bool, str]:
    """正确性自检：**严判**，不是「包含关键词」就算过。

    2026-10-24 教训：一开始只查「输出里有没有北京」，结果 GPU 答出
    「中国的首都是**北京**；它与**idepressent**（有效的抗抑郁药）…」，
    前半句对、后半句乱，照样判成通过。所以要严。

    🔴 2026-10-28 第二个教训：**严的方向错了**。原来打裸 `/completion`，
    模型在这个面上本来就答不好（实测 q5_0 源档答 `4 ③ 侧`、q3_k_m 答 `？`），
    于是"严"变成了"把一条能跑的车道判死"。而 APP 实际调用的是 chat 面 ——
    同一个 q3_k_m 在 chat 面答 `北京` / `2`，全对。
    ⇒ 判据必须判**应用真实调用面**，并有能力自证（见 judge_selftest）。
    """
    cases = [("中国的首都是哪里？只回答城市名", ["北京"], 16),
             ("1+1=？只回答数字", ["2", "二"], 8)]
    lines = []
    for prompt, expect_any, max_tok in cases:
        body = json.dumps({"messages": [{"role": "user", "content": prompt}],
                           "max_tokens": max_tok, "temperature": 0}).encode()
        req = urllib.request.Request("http://127.0.0.1:%d/v1/chat/completions" % PORT, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace"))
            msg = (d.get("choices") or [{}])[0].get("message") or {}
            txt = msg.get("content") or ""
        except Exception as exc:                                 # noqa: BLE001
            return False, "%s 请求失败 %s" % (prompt, type(exc).__name__)
        ok, why = judge(txt, expect_any)
        lines.append("%r→%r %s" % (prompt, txt.strip()[:24], "OK" if ok else "脏:" + why))
        if not ok:
            return False, "；".join(lines)
    return True, "；".join(lines)


CHECK_TOKENS = int(os.environ.get("GBT_GPU_CHECK_TOKENS", "2600"))
_UNIT = "上下文必须真实进入模型，否则回答就是胡话。"


def _tok_count(text: str) -> int:
    body = json.dumps({"content": text}).encode()
    req = urllib.request.Request("http://127.0.0.1:%d/tokenize" % PORT, data=body,
                                 headers={"Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace"))
    return len(d.get("tokens") or [])


def longcheck() -> tuple[bool, str]:
    """验「上下文到底吃进去多少」—— **HTTP 200 不算证据，只有 prompt_n 算**。

    🔴 2026-10-28 为什么必须有这一条：同一份 12015 字文档，
      · ctx=8192 时 prompt_n=**8078**、答案正确（命中埋点）；
      · ctx=2048 时 **HTTP 仍回 200**、但 prompt_n 只有 **1934**（被静默截断），答案变成胡话。
    ⇒ 只问「中国的首都是」这种短问答的自检，**结构上永远发现不了截断**——那是一种假绿。
       唯一能发现的办法：按**已知长度**发一发，再把服务端回的 prompt_n 对回来。

    负载默认 2600 token（刚好越过 fast 档 2048，长档下约 18 s）；可用
    `GBT_GPU_CHECK_TOKENS` 调大，做发布前全窗口验证。
    """
    need_chars = int(CHECK_TOKENS * 1.8)                 # 中文约 1.714 字符/token，留余量
    text = _UNIT * (need_chars // len(_UNIT) + 1)
    expect = _tok_count(text)
    if expect < CHECK_TOKENS:
        return False, "负载没造够：只分词出 %d token（要 %d），判不了" % (expect, CHECK_TOKENS)
    body = json.dumps({"prompt": text, "n_predict": 1, "temperature": 0}).encode()
    req = urllib.request.Request("http://127.0.0.1:%d/completion" % PORT, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    got = int((d.get("timings") or {}).get("prompt_n") or 0)
    ok = got >= int(expect * 0.98)
    return ok, ("发 %d token（/tokenize 数出来的）→ 服务端实收 prompt_n=**%d**（%.1fs）%s"
                % (expect, got, time.time() - t0,
                   "" if ok else " ⇒ **被截断**：HTTP 200 但上下文没吃全，答案会是胡话"))


def start(skip_longcheck: bool = False) -> int:
    if not ensure_bin():
        return 2
    if healthy():
        ok, detail = probe()
        log("已在跑：自检 %s → %s" % ("通过" if ok else "失败", detail))
        return 0 if ok else 3
    if not os.path.isfile(MODEL):
        log("模型不在：%s" % MODEL)
        return 2
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    log("起 llama-server（ngl=%d, ctx=%s, port=%d）…"
        % (NGL, os.environ.get("GBT_GPU_CTX") or str(_DEF_CTX), PORT))
    subprocess.Popen([EXE, "-m", MODEL, "-c", os.environ.get("GBT_GPU_CTX") or str(_DEF_CTX),
                      "-t", os.environ.get("GBT_GPU_THREADS", "8"), "-ngl", str(NGL),
                      # 🔴 2026-10-28 实测：不加这个开关，prompt 超过 ctx 时**不报错**，
                      #   只把 prompt 静默截断到 ctx 以内、仍返回 200，模型基于残缺上下文作答
                      #   （12015 字在 ctx2048 下只吃进 1934 token，答案从「赤鳞-7391」变成「genoffice」）。
                      #   加上之后，超长请求直接 **HTTP 400**
                      #   "the request exceeds the available context size" ⇒ 宁可报错，不许胡说。
                      #   这也是**服务器级**保护：对所有调用方生效，不依赖哪段应用代码写没写对。
                      "--no-context-shift",
                      "--port", str(PORT), "--host", "127.0.0.1"],
                     cwd=BIN_DIR, creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 120:
        if healthy():
            break
        time.sleep(2)
    if not healthy():
        log("120 秒没起来")
        return 2
    ok, detail = probe()
    log("自检 %s → %s" % ("通过" if ok else "失败", detail))
    if not ok:
        subprocess.run(["powershell", "-NoProfile", "-c",
                        "(Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue).OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }" % PORT],
                       capture_output=True)
        return 3
    # 第二道自检：**截断自检**（短问答发现不了的那一类）
    if not skip_longcheck:
        okc, dc = longcheck()
        log("截断自检 %s → %s" % ("通过" if okc else "失败", dc))
        if not okc:
            subprocess.run(["powershell", "-NoProfile", "-c",
                            "(Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue).OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }" % PORT],
                           capture_output=True)
            return 4
        detail = detail + "；截断自检 OK（" + dc + "）"
    else:
        log("截断自检 **已跳过**（--skip-longcheck / GBT_GPU_SKIP_LONGCHECK=1）"
            " —— 此时不能声称「上下文读全了」")
        detail = detail + "；截断自检 已跳过（不构成读全的证明）"
    # 🔴 2026-10-28 补（**这是假绿，我自己踩的**）：自检通过 ≠ 服务还在。
    #   实测：`--start` 退 0、语义与截断自检都过；**退出那一刻还探得到**（alive_at_exit=true），
    #   但几秒后 `--check` 就是 false —— `netstat :8793` 只剩 TIME_WAIT、`tasklist` 里 0 个 llama-server。
    #   ⇒ 子进程用 DETACHED_PROCESS 起，被**把这条命令当子进程管的宿主**在命令结束后回收
    #   （工具文档原话：detached 进程 may be reclaimed when the shell, sandbox, session, or CLI exits）。
    #   ⚠️ 正因为回收发生在**命令结束之后**，在 start() 里面**永远探不到**它 —— 所以这里
    #   `alive_at_exit` 只声明"退出那一刻"，**不许**被读成"正在服务"。
    #   真正的"还在不在"由下一次 `--check` 回答，靠 `state/gpu-lane.json` 分清三态
    #   （serving / died_after_start / never_started）。主人在自己终端里跑则恒为 serving。
    alive = _alive_after(grace=2.0, tries=3)
    _write_state({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "port": PORT, "pid": _listen_pid(),
        "ngl": NGL, "ctx": os.environ.get("GBT_GPU_CTX") or _DEF_CTX, "profile": _PROFILE,
        "selfcheck": "pass", "longcheck": "skipped" if skip_longcheck else "pass",
        "alive_at_exit": alive,
    })
    out = {"ok": True, "port": PORT, "ngl": NGL,
           "ctx": os.environ.get("GBT_GPU_CTX") or _DEF_CTX,
           "profile": _PROFILE, "detail": detail,
           "started": True, "alive_at_exit": alive,
           "_口径": "started=起过并自检过 · alive_at_exit=退出那一刻 · "
                    "**「现在还在不在」问 --check**（回收发生在命令结束之后，这里探不到）"}
    print(json.dumps(out, ensure_ascii=False))
    return 0


STATE = os.path.join(REPO, "state", "gpu-lane.json")


def _write_state(row: dict) -> None:
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as fh:
            json.dump(row, fh, ensure_ascii=False, indent=1)
    except OSError:
        pass                                    # 落不了账不影响起车，但不能因此崩


def _read_state() -> dict:
    try:
        with open(STATE, encoding="utf-8-sig") as fh:
            return json.load(fh) or {}
    except Exception:                                             # noqa: BLE001
        return {}


def _listen_pid() -> int | None:
    """8793 的监听 pid（读不到就 None，不猜）。"""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=15).stdout or ""
        for ln in out.splitlines():
            if "LISTENING" in ln and (":%d " % PORT) in ln:
                tail = ln.split()[-1]
                if tail.isdigit():
                    return int(tail)
    except Exception:                                             # noqa: BLE001
        pass
    return None


def _alive_after(grace: float = 2.0, tries: int = 3) -> bool:
    """退出**前**复核存活：隔 grace 秒探一次，最多 tries 次；任一成功即算活。

    ⚠️ 它只能回答"退出那一刻"，**回答不了"命令结束后还在不在"** —— 见上面 start() 的注释。
    """
    for i in range(max(1, tries)):
        time.sleep(grace if i == 0 else 0.5)
        if healthy():
            return True
    return False


def status() -> dict:
    """三态：serving / died_after_start / never_started。

    为什么必须分三态：`--start` 退 0 之后进程可能**在命令结束那一刻被宿主回收**，
    此时"起过"和"在服务"是两件不同的事。把两者混成一个 ok，就是在制造假绿。
    """
    live = healthy()
    st = _read_state()
    if live:
        return {"state": "serving", "ok": True, "port": PORT, "pid": _listen_pid(),
                "started_at": st.get("at"), "profile": st.get("profile") or _PROFILE}
    if st:
        return {"state": "died_after_start", "ok": False, "port": PORT,
                "started_at": st.get("at"), "pid_then": st.get("pid"),
                "why": "起过并自检通过，但端口现在没有监听 —— 进程已被回收（或崩了）",
                "hint": "在自己的终端里重跑 `--start`；被别的程序当子进程调起时会被宿主回收"}
    return {"state": "never_started", "ok": False, "port": PORT,
            "why": "没有起车记录（state/gpu-lane.json 不存在）"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="只问「现在在不在听」")
    ap.add_argument("--status", action="store_true",
                    help="三态：serving / died_after_start / never_started（起过但被回收能看出来）")
    ap.add_argument("--longcheck", action="store_true",
                    help="只对**已在跑**的服务做截断自检（按已知长度发一发，核 prompt_n）")
    ap.add_argument("--skip-longcheck", action="store_true",
                    help="--start 时跳过截断自检（跳过就不能声称上下文读全了）")
    ap.add_argument("--selftest", action="store_true", help="只跑判据自己的负对照（不起模型）")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(judge_selftest())
    if a.check:
        print(json.dumps({"ok": healthy(), "port": PORT}))
        raise SystemExit(0)
    if a.status:
        st = status()
        print(json.dumps(st, ensure_ascii=False))
        # 0=在服务 · 1=起过但没了 · 2=从没起过（判不了服务状态，但也不是错）
        raise SystemExit(0 if st["state"] == "serving" else (1 if st["state"] == "died_after_start" else 2))
    if a.longcheck:
        ok, detail = longcheck()
        print(json.dumps({"ok": ok, "port": PORT, "detail": detail}, ensure_ascii=False))
        raise SystemExit(0 if ok else 1)
    skip = a.skip_longcheck or bool(os.environ.get("GBT_GPU_SKIP_LONGCHECK"))
    raise SystemExit(start(skip_longcheck=skip))
