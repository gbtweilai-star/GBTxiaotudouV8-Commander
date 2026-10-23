# -*- coding: utf-8 -*-
"""GBT小土豆V8 × CLIProxyAPI · 统一模型分化路由（主人令 2026-10-04）。

## 图景（主人原话：「借助这玩意把我们自己的大模型以及现有的全部重新使用做分化和连接」）
上游项目 `router-for-me/CLIProxyAPI`（已取至 `_upstream/CLIProxyAPI`，**本机已构建** 94MB 二进制）：
把各家 CLI 账户（Codex / Claude Code / Gemini / Grok / Kimi / Muse / Devin）与**自定义 OpenAI 兼容上游**
统一成 **OpenAI / Gemini / Claude / Codex 兼容的本地端点**。
  · **分化** = 每条腿一个上游/账户（name/prefix 各自独立、各自冷却与轮换）；
  · **连接** = 我们框架（触手 / 唯一门 / 统一密钥链）只要认**一个** base-url 就能用全部腿；
  · **自家大模型** = 作为 `openai-compatibility` 上游接进去（我们那座云 Worker 的 OpenAI 兼容面）。

## 本件做什么（不吹牛的部分）
  · `up`     ：从**环境变量**取密钥 → 生成 config.yaml（落在应用数据区，**不进仓**）→ 起服务 → 健康探活
  · `status` ：探活 + 列车道（GET /v1/models，带本地 access key）
  · `probe`  ：对指定车道真发一轮 chat/completions（默认第一条车道），回执带真实读数
  · `down`   ：停服务

## 红线（与框架同口径）
  · **密钥只从环境变量/密钥服务来**：`GBT_POTATO_BASE_URL` · `GBT_POTATO_API_KEY` · `GBT_FREE_POOL_KEY`
    · `GBT_CLIPROXY_KEY`（本地客户端钥匙；不给则**本机随机生成**并只落应用数据区）；
  · **DeepSeek 官方车道**（2026-10-14 加）：`GBT_DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com/v1`）·
    `GBT_DEEPSEEK_API_KEY`（不给就回退 `DEEPSEEK_API_KEY`）· `GBT_DEEPSEEK_MODELS`
    （默认 `deepseek-flash,deepseek-v4-pro`）—— 让「我们自己的模型」与「DeepSeek 原档」同走 8317 一个口；
  · 生成物（config.yaml / 钥匙）只落 `%APPDATA%\\gbt-cliproxy\\`，**仓库里只放模板**；
  · 服务只绑 **127.0.0.1**（不外露）；
  · **本件所有出站请求只许回环**（见 `_checked_url`）：协议 http、主机白名单（127.0.0.1/localhost/::1）、
    **拒绝重定向**（防被上游引导到别处）—— 这与「服务端请求用户给的 URL」那条 SSRF 边界不同：
    本件是**本地服务的客户端**（目标由本件自己定死为回环），不做任何外部取数。

用法：
    py -3.14 tools/codex-scripts/cliproxy.py up        # 起（写配置 + 启动 + 探活）
    py -3.14 tools/codex-scripts/cliproxy.py status    # 看车道
    py -3.14 tools/codex-scripts/cliproxy.py probe     # 真发一轮
    py -3.14 tools/codex-scripts/cliproxy.py down      # 停

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / "_upstream" / "CLIProxyAPI"
EXE = UPSTREAM / "CLIProxyAPI.exe"
APPDIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "gbt-cliproxy"
CONFIG = APPDIR / "config.yaml"
KEYFILE = APPDIR / "client-key.txt"
PORT = int(os.environ.get("GBT_CLIPROXY_PORT", "8317"))
HOST = "127.0.0.1"
ALLOWED_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})


def _env(name: str, default: str = "") -> str:
    """环境变量优先；**本进程环境块缺它时回用户注册表读**。

    🔴 2026-10-14 血读（真踩）：老进程/老终端的环境块可能是旧的 ⇒ `os.environ` 里没有 GBT_*
    ⇒ 本件会拿"统一钥"当上游钥、并把缺钥的车道**整条丢掉**：实测车道 3 条 → 1 条，
    上游 RunPod 回 `401 invalid api key`。注册表那份**仍是环境变量**（持久化的一份），
    不是新凭据源 ⇒ 读它不违反"密钥只从环境变量来"。
    """
    v = (os.environ.get(name) or "").strip()
    if v or os.name != "nt":
        return v or default
    try:
        import winreg                                            # noqa: PLC0415
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return (winreg.QueryValueEx(k, name)[0] or "").strip() or default
    except Exception:                                            # noqa: BLE001
        return default


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """拒绝重定向：本地服务不该把我们导去别处（防引导型 SSRF）。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _checked_url(path: str) -> str:
    """唯一出站点：**只许回环 http**（协议/主机/重定向三重校验，配注释见模块头）。"""
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("路径必须以单个 / 开头：%r" % path[:40])
    url = "http://%s:%d%s" % (HOST, PORT, path)
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in ALLOWED_LOOPBACK:
        raise ValueError("非回环目标被拒：%s" % url[:80])
    return url


def _gateway_call(kind: str, payload: dict) -> dict:
    """走**唯一门**调框架能力（不绕过授权门）：本件只调 key_gateway 的读类/mint。"""
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import run_task
        env = run_task(kind, payload, safe=True)
        x = env
        for _ in range(4):
            if isinstance(x, dict) and isinstance(x.get("result"), dict) and "ok" not in x:
                x = x["result"]
            elif isinstance(x, dict) and "gbt_result" in x:
                x = x["gbt_result"]
            else:
                break
        return x if isinstance(x, dict) else {}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "error": "门不可用：%s" % str(exc)[:160]}


def _unified_key() -> dict:
    """**统一密钥**（主人令：「不做密钥填充，直接双向绑定在统一一个密钥生成」）。

    口径：一把钥两边用 —— 路由器 `access.api-keys`（我们→路由器）与云端 `GW_AUTH`（路由器→云端）
    是同一个值。来源顺序：
      ① 环境变量 `GBT_CLIPROXY_KEY`（主人已设，最优先）
      ② 本地文件 `%APPDATA%\\gbt-cliproxy\\client-key.txt`（明文只落应用数据区）
      ③ **走唯一门请 key_gateway 铸一把**（`op=mint label=cliproxy-unified`）⇒ 明文落 ②、库里只留摘要，
         并把该值 `setx GBT_CLIPROXY_KEY`（框架侧读得到，与路由器同一把）。
    返回 `{key, source, key_id, verified}`；铸不出就如实报缺（不编）。
    """
    env = _env("GBT_CLIPROXY_KEY")
    if env:
        return {"key": env, "source": "env:GBT_CLIPROXY_KEY"}
    if KEYFILE.is_file():
        s = KEYFILE.read_text(encoding="utf-8").strip()
        if s:
            # 🔴 自愈（实测踩坑）：文件里可能是**早先随机生成、没过门**的钥 ⇒ 门不认 ⇒ 双向绑定只绑了一半。
            #    拿到文件钥先**请门核验**；核不过就把它改名留存（不删），走 mint 重铸一把。
            ver = _gateway_call("key_gateway", {"op": "verify", "key": s})
            if ver.get("ok"):
                return {"key": s, "source": "file:" + str(KEYFILE), "key_id": ver.get("key_id")}
            try:
                os.replace(KEYFILE, str(KEYFILE) + ".unbound-" + time.strftime("%Y%m%d-%H%M%S"))
            except OSError:
                pass
    res = _gateway_call("key_gateway", {"op": "mint", "label": "cliproxy-unified",
                                        "scopes": "llm.chat"})
    raw = (res or {}).get("key") or (res or {}).get("raw") or ""
    if not raw:
        return {"key": "", "source": "未铸成", "error": (res or {}).get("error") or str(res)[:160]}
    APPDIR.mkdir(parents=True, exist_ok=True)
    KEYFILE.write_text(raw, encoding="utf-8")
    if os.name == "nt":
        try:                                                   # 框架侧（新进程）也读得到同一把
            subprocess.run(["setx", "GBT_CLIPROXY_KEY", raw],
                           capture_output=True, text=True, encoding="mbcs", errors="replace", timeout=15)
        except Exception:                                      # noqa: BLE001
            pass
    return {"key": raw, "source": "gateway:mint", "key_id": (res or {}).get("key_id")}


def _key_fingerprint(key: str) -> str:
    """只回形状（前 4 + 长度），**绝不回明文**。"""
    return (key[:4] + "****(" + str(len(key)) + ")") if key else "（无）"


def _lanes() -> list:
    """车道清单（分化）：自家大模型 + 本机免费池。

    每条车道 = 一个 OpenAI 兼容上游 + **显式模型名**（实测：不列 models 路由器不认）。
    密钥一律从环境变量来；免费池没在跑就 `disabled: true` —— 不编「活着」。
    """
    lanes = []
    potato_base = _env("GBT_POTATO_BASE_URL").rstrip("/")
    potato_key = _env("GBT_POTATO_API_KEY")
    potato_models = [m.strip() for m in
                     (os.environ.get("GBT_POTATO_MODELS") or "gbt-potato-v8").split(",") if m.strip()]
    # 🔴 统一密钥口径：自家车道的上游钥 = **同一把统一密钥**（云端 GW_AUTH 也设成这个值）
    #    ——「不做密钥填充，双向绑定在一个密钥上」。环境变量给了别的值就以其为准（主人显式覆盖）。
    unified = (_unified_key().get("key") or "")
    # 🔴 2026-10-14 补（真跑咬出来的）：**车道上游钥可显式覆盖**。
    #    实测病案：本车道 base 指 RunPod 自托管端点，钥却取了「统一钥」（那把是给**云端 Worker** 的
    #    `GW_AUTH` 用的）⇒ 上游回 `401 invalid api key`；同一条链上 Worker 自己也一样 401。
    #    两者**不是同一把**钥 ⇒ 给车道留一个显式口：`GBT_POTATO_LANE_KEY`（不设时行为与改前逐字节相同）。
    lane_key = _env("GBT_POTATO_LANE_KEY")
    if potato_base:
        # 🔴 优先级：**统一密钥优先**（主人令「一个密钥两边用」）。实测坑：环境里的旧钥
        #    （setx 只对新进程生效 ⇒ 本进程仍拿旧值）会被优先写进配置 ⇒ 云端 401。
        # 🔴 2026-10-14 再修（真跑咬出来的第二个坑）：**这条车道的 base 是 RunPod 自托管端点**
        #    ⇒ 它要的是 `rpa_…`（`GBT_POTATO_API_KEY`），**不是**那把"统一钥"（统一钥是给**云端 Worker**
        #    的 `GW_AUTH` 用的）。拿统一钥打 RunPod 端点 = `401 invalid api key`（本机实测）。
        #    ⇒ 车道钥优先级改成：显式覆盖 > **本车道自己的钥** > 统一钥。
        lanes.append({"name": "gbt-potato", "base": potato_base,
                      "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
                      "key": lane_key or potato_key or unified or "none",
                      "models": potato_models})
    # ── 2026-10-14 追加：DeepSeek 官方车道（主人令「B：一个入口走全部模型」）──────────────
    #   为什么加它：Codex 桌面版的模型选择器**只带 model、不带 provider**（实测：App 持久状态
    #   `composer-recent-model-configurations-v1` 每条只有 model/reasoningEffort/serviceTier），
    #   而 config.toml 的 `model_provider` 是**全局一格** ⇒ 选「GBT小土豆V8 v24（自托管）」时
    #   请求仍发去 api.deepseek.com，DeepSeek 原样回 `but you passed gbt-potato-v8`（今天三次实测）。
    #   解法：把 DeepSeek 也接成**同一入口（8317）下的一条车道**，`model_provider` 固定 gbt-potato
    #   ⇒ App 里选哪个模型都从这个口出去，模型名自己分流（两边的 wire_api=responses 都实测 200）。
    #   密钥来源：`GBT_DEEPSEEK_API_KEY`，回退到已有的 `DEEPSEEK_API_KEY`（都走环境变量，不落盘）。
    #   没给钥就**不加这条车道**（如实缺，不编一条空车道）。
    ds_base = _env("GBT_DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    ds_key = _env("GBT_DEEPSEEK_API_KEY") or _env("DEEPSEEK_API_KEY")
    if ds_key:
        lanes.append({"name": "deepseek", "base": ds_base, "key": ds_key,
                      "models": [m.strip() for m in
                                 (os.environ.get("GBT_DEEPSEEK_MODELS")
                                  or "deepseek-flash,deepseek-v4-pro").split(",") if m.strip()]})
    # 本机 Ollama 车道（组1）：权重本地、回环；在听就启用，不在听就如实 disabled
    ollama_base = (os.environ.get("GBT_LOCAL_LLM_BASE_URL") or "http://127.0.0.1:11434/v1").rstrip("/")
    lanes.append({"name": "gbt-local-ollama", "base": ollama_base, "key": "ollama",
                  "models": [m.strip() for m in
                             (os.environ.get("GBT_LOCAL_LLM_MODELS") or "qwen3:latest,qwen3:0.6b").split(",") if m.strip()],
                  "disabled": not _port_open(ollama_base)})
    pool_base = (os.environ.get("GBT_FREE_POOL_BASE") or "http://127.0.0.1:31415/v1").rstrip("/")
    pool_alive = _port_open(pool_base)
    lanes.append({"name": "gbt-free-pool", "base": pool_base,
                  "key": (os.environ.get("GBT_FREE_POOL_KEY") or "none").strip() or "none",
                  "models": [m.strip() for m in
                             (os.environ.get("GBT_FREE_POOL_MODELS") or "gbt-free-pool").split(",") if m.strip()],
                  "disabled": not pool_alive})
    return lanes


def _port_open(base_url: str) -> bool:
    """只读探一下本机服务在不在（**只许回环**：非回环地址一律当不在，且不发起请求）。"""
    try:
        parts = urllib.parse.urlsplit(base_url)
        if parts.hostname not in ALLOWED_LOOPBACK:
            return False
        import socket
        with socket.create_connection((parts.hostname, parts.port or 80), timeout=0.6):
            return True
    except Exception:                                          # noqa: BLE001
        return False


def write_config() -> dict:
    """生成 config.yaml（v8 布局）。

    🔴 2026-10-04 实测踩坑（两处，都靠服务日志才看出来 —— 它对未知字段**静默忽略**）：
      ① `openai-compatibility` 的正确层级是 **顶层 `api-keys:`**（与 `access:` 平级），
         写成 `upstream.api-keys.*` 会得到 `0 OpenAI-compat`、车道恒空；
      ② 自定义上游**必须显式列 `models`**（路由器不替你猜模型名）。
    """
    uk = _unified_key()
    key = uk.get("key") or ""
    lanes = _lanes()
    lines = [
        "# 本文件由 tools/codex-scripts/cliproxy.py 生成（勿手改：改环境变量再重跑 up）",
        "# 只落应用数据区；仓库里只放模板 deploy/cliproxy/config.gbt.example.yaml",
        "config-version: 8",
        "server:",
        '  host: "127.0.0.1"',                     # 只绑回环：不外露（红线）
        "  port: %d" % PORT,
        "access:",
        "  api-keys:",
        '    - "%s"' % key,
        "api-keys:",                       # 顶层、与 access 平级（实测口径，见 docstring）
        "  openai-compatibility:",
    ]
    for ln in lanes:
        lines += [
            '    - name: "%s"' % ln["name"],          # 缩进与实测跑通的那份一致（4/6/8）
            '      base-url: "%s"' % ln["base"],
            "      keys:",
            '        - api-key: "%s"' % ln["key"],
        ]
        if ln.get("ua"):
            # 🔴 实测坑（两个）：① 云端 Worker 在 CF 边缘后面，**非浏览器 UA 会被判 bot（403 code 1010）**
            #    ⇒ 给上游加常规浏览器 UA；② **headers 必须写在 models 之前** —— 上一版我插在
            #    `models:` 与模型项之间，YAML 直接断链（`line 17: did not find expected key`）。
            lines += ["      headers:",
                      '        User-Agent: "%s"' % ln["ua"]]
        lines.append("      models:")
        for m in ln["models"]:
            lines += ['        - name: "%s"' % m]
        if ln.get("disabled"):
            lines.append("      disabled: true")
    APPDIR.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"config": str(CONFIG), "lanes": [ln["name"] for ln in lanes], "key_file": str(KEYFILE)}


def _get(path: str, timeout: float = 8.0) -> tuple:
    req = urllib.request.Request(_checked_url(path),
                                 headers={"Authorization": "Bearer " + (_unified_key().get("key") or "")})
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:300]
    except Exception as exc:                                   # noqa: BLE001
        return 0, "连不上：%s" % str(exc)[:160]


def _post(path: str, body: dict, timeout: float = 120.0) -> tuple:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(_checked_url(path), data=data, method="POST",
                                 headers={"Authorization": "Bearer " + (_unified_key().get("key") or ""),
                                          "Content-Type": "application/json"})
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:500]
    except Exception as exc:                                   # noqa: BLE001
        return 0, "连不上：%s" % str(exc)[:160]


def cmd_bind(_a) -> int:
    """双向绑定一条口令：**一个密钥、两边用**（不逐条填钥）。

    做三件（都可复核）：
      ① 取/铸统一密钥（key_gateway 铸 ⇒ 库里只留摘要；明文落应用数据区 + setx）；
      ② 请门核验这把钥在库里的摘要（key_gateway op=verify）—— 绑没绑上，**门说了算**；
      ③ 用同一把钥重写路由器配置并重启 ⇒ 我们→路由器、路由器→云端 是同一条口令。
    """
    uk = _unified_key()
    if not uk.get("key"):
        print("🔴 统一密钥取不到（环境变量/本地/门都失败）：%s" % (uk.get("error") or ""))
        return 2
    print("统一密钥：%s（来源：%s）" % (_key_fingerprint(uk["key"]), uk.get("source")))
    ver = _gateway_call("key_gateway", {"op": "verify", "key": uk["key"]})
    print("门侧核验：%s %s" % ("✅ 库里认这把钥" if ver.get("ok") else "⛔ 库里不认",
                               (ver.get("key_id") or ver.get("error") or "")[:80]))
    print()
    print("云端那半（主人敲一次，把**同一个值**设成 Worker 的网关钥）：")
    print("   cd deploy/cloud-10 && npx wrangler secret put GW_AUTH      # 粘贴上面对话里那把（脚本不会打印明文）")
    print("   或本机设环境变量后由脚本读： setx GW_AUTH <同一个值>")
    print()
    return cmd_up(_a)


def cmd_up(_a) -> int:
    if not EXE.is_file():
        print("🔴 二进制不在：%s（先在 _upstream/CLIProxyAPI 跑 go build -o CLIProxyAPI.exe ./cmd/server）" % EXE)
        return 2
    info = write_config()
    print("配置：%s（车道：%s）" % (info["config"], "、".join(info["lanes"])))
    st, _body = _get("/v1/models", timeout=3.0)
    if st == 200:
        # 🔴 实测踩坑：服务在跑时**不重启** ⇒ 刚写的配置根本没被加载（车道恒空、看着像"没配"）。
        # 本工具是"把配置变成活车道"的入口 ⇒ `up` 一律**重启**（`--keep-running` 才沿用现有进程）。
        if getattr(_a, "keep_running", False):
            print("服务已在跑（保持不动，--keep-running）")
            return cmd_status(None)
        print("服务在跑 —— 重启以加载新配置（要沿用现有进程加 --keep-running）")
        cmd_down(None)
        time.sleep(1.2)
    creationflags = 0x00000008 if os.name == "nt" else 0      # DETACHED_PROCESS：别拖住本进程
    APPDIR.mkdir(parents=True, exist_ok=True)
    log = open(APPDIR / "cliproxy.log", "ab")
    subprocess.Popen([str(EXE), "--config", str(CONFIG)], cwd=str(UPSTREAM),
                     stdout=log, stderr=log, creationflags=creationflags, close_fds=True)
    for _ in range(20):
        time.sleep(0.6)
        st, _b = _get("/v1/models", timeout=3.0)
        if st in (200, 401):                                   # 401 = 起来了但钥匙不对（也算活着）
            print("服务已起：http://%s:%d（回环）" % (HOST, PORT))
            return cmd_status(None)
    print("🔴 起了但探活没通 —— 看日志：%s" % (APPDIR / "cliproxy.log"))
    return 1


def cmd_status(_a) -> int:
    st, body = _get("/v1/models")
    print("GET /v1/models → HTTP %s" % st)
    if st != 200:
        print("读数：%s" % body[:200])
        return 1
    try:
        data = json.loads(body)
    except Exception:                                          # noqa: BLE001
        print("回包不是 JSON：%s" % body[:200])
        return 1
    ids = [m.get("id") for m in (data.get("data") or [])]
    print("车道（模型 id）%d 条：" % len(ids))
    for i in ids[:40]:
        print("   -", i)
    if len(ids) > 40:
        print("   … 其余 %d 条" % (len(ids) - 40))
    if not ids:
        print("   （空：上游还没配或都未登录 —— 如实报缺，不编）")
    return 0


def cmd_probe(a) -> int:
    model = a.model or (os.environ.get("GBT_CLIPROXY_PROBE_MODEL") or "").strip()
    if not model:
        st, body = _get("/v1/models")
        ids = []
        if st == 200:
            try:
                ids = [m.get("id") for m in (json.loads(body).get("data") or [])]
            except Exception:                                  # noqa: BLE001
                ids = []
        model = ids[0] if ids else ""
    if not model:
        print("🔴 没有可用车道模型（先 up 并配上游）—— 不编模型名")
        return 2
    print("真发一轮：model=%s" % model)
    st, body = _post("/v1/chat/completions", {
        "model": model,
        "messages": [{"role": "user", "content": a.ask or "只回两个字：在的"}],
        "max_tokens": 64, "stream": False,
    })
    print("POST /v1/chat/completions → HTTP %s" % st)
    print(body[:600])
    return 0 if st == 200 else 1


def cmd_down(_a) -> int:
    if os.name != "nt":
        print("非 Windows：请手动停")
        return 2
    r = subprocess.run(["taskkill", "/F", "/IM", "CLIProxyAPI.exe"],
                       capture_output=True, text=True, encoding="mbcs", errors="replace")
    print((r.stdout or r.stderr or "").strip()[:200] or "已尝试停止")
    return 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                      # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="GBT × CLIProxyAPI 统一模型路由（回环）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("up")
    up.add_argument("--keep-running", action="store_true",
                    help="服务在跑就沿用（默认重启以加载新配置）")
    up.set_defaults(fn=cmd_up)
    sub.add_parser("bind", help="双向绑定：一个统一密钥、两边用（会重启服务）").set_defaults(fn=cmd_bind)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    p = sub.add_parser("probe")
    p.add_argument("--model", default="", help="指定车道模型名（默认取第一条）")
    p.add_argument("--ask", default="", help="要问的内容（默认：只回两个字：在的）")
    p.set_defaults(fn=cmd_probe)
    sub.add_parser("down").set_defaults(fn=cmd_down)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
