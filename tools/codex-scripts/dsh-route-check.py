#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""dsh-route-check · 核「我们自己的大模型路由」还在不在、形对不对、钥匙有没有

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它
2026-09-25 把 GBT小土豆V8 接成宿主的一条模型路由（`gbt-potato`），当轮读数：
宿主 `llm.listProviders()` 里真有它、且**在宿主里真发过一次调用**量到了回答。
但「接上了」这件事**没有判据** —— 它躺在两个**仓外**文件里：

  · `<DSH_HOME>/profiles/<profile>/cordis.patch.yml`  ← 路由声明（唯一活载路径）
  · `<DSH_HOME>/.credentials.yaml`                     ← `apiKeyEnv` 指向的那把凭据

仓外 + 无判据 = 迟早漂。本仓同型教训三条（都真踩过）：
  ① **宣称有、代码没有**（`mesh.json` 写了 D1 落点、代码里只有内存）；
  ② **`api` 字段漏了就静默不合形**（路由看着在、其实起不来）；
  ③ **`apiKeyEnv` 指的凭据解析不到** ⇒ 协议层直接报 `No API key for provider`（`PI_AI_ERROR`）。
⇒ 本工具就是这三条的那道闸：**一次命令，把「声明 · 形状 · 钥匙」三件事分开念**。

## 三条口径（写死在这里，免得以后念混）
1. **单一真源 = composition patch**。`settings.yaml` 里的同名块是**漂移风险**（服务会用自己的
   内存态重写那个文件，我在它外面写的会被抹掉）⇒ settings 里出现同路由**不报红、但必须点名**。
2. **`api` 必须现读 pi-ai 的类型定义来判**（`dist/types.d.ts` 的 `KnownApi` 联合）——
   **不硬编码协议名单**：pi-ai 升级后名单会变，写死一次就过期一次（本仓已有同型教训）。
   🔴 判据**没跑**（读不到类型定义）时**不许念成合格**，要明写「这条判据没跑」。
3. **密钥明文永不输出**：只报「已配/未配 + 位数 + sha256 前 6 位」。落盘前再过一道
   **按已知密钥值替换**的红act（自检里有一条负控专门咬这个）。

## 用法
  python tools/codex-scripts/dsh-route-check.py check                  # 只读现读（默认 profile=web · 路由=gbt-potato）
  python tools/codex-scripts/dsh-route-check.py check --route gbt-free # 换一条路由
  python tools/codex-scripts/dsh-route-check.py live                   # 四条两态真打（见下）
  python tools/codex-scripts/dsh-route-check.py models                 # 把 patch 里声明的模型**逐个真调一次**
  python tools/codex-scripts/dsh-route-check.py models --ids a,b,c     # **候选试跑**（不判、不改 patch）
  python tools/codex-scripts/dsh-route-check.py selftest               # 26 条正/负控（全在临时靶上，不碰真配置）

`live` 打的是**四条**：带钥匙两条路都必须 200、每条路**自己两态**（不带钥匙 200=公开面 /
401=令牌面，别的码一律「说不清」），端点若自报 `auth_scope` 则**自报必须与实测一致**，
且带钥匙那一发必须**真出字**。

## 两条「不做」
- **不进 `checkup.py`**：它读的是**本机装机目录**，换机器/换 profile 会假红 ⇒ 进体检等于把
  「本机装机状态」绑进仓的合格线。它是**按需现读**件（与快照工具同类）。
- **不写**：只读。改路由要动的是 `cordis.patch.yml`（那是主人的装机文件），本件一个字都不写。
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UA = "gbt-mesh-acceptance/1.0 (+https://gbt-potato-cloud-10.lopaycn.workers.dev)"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import yaml
except Exception:                                    # pragma: no cover
    yaml = None

# 只读用的「已知密钥值」清单：任何输出在落盘前都会拿它做一次替换。
# 🔴 **它只活在内存里**，不进任何返回结构、不进 json、不进日志。
_SECRETS: list = []


def dsh_home() -> Path:
    env = os.environ.get("DSH_HOME")
    return Path(env) if env else Path(os.path.expanduser("~")) / ".dsh"


def sha6(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()[:6]


def redact(text: str) -> str:
    """落盘/打印前最后一道：把内存里已知的密钥值替换成 `****`。"""
    for s in _SECRETS:
        if s:
            text = text.replace(s, "****")
    return text


# ── YAML 载入 ───────────────────────────────────────────────────────────────
class _Lenient(yaml.SafeLoader if yaml else object):        # type: ignore[misc]
    """官方注释写「`!!js` expressions allowed」⇒ 遇到未知 tag **不许崩**。

    🔴 这条不是学术问题：patch 层真允许自定义 tag，而 `safe_load` 撞上就抛异常 ⇒
    工具会把「主人的配置里有 `!!js`」读成「配置坏了」。自检里有一条正控钉这个。
    """


def _unknown_tag(loader, tag_suffix, node):                  # noqa: ANN001
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


if yaml:
    _Lenient.add_multi_constructor("", _unknown_tag)


def load_yaml(path: Path) -> tuple:
    """返回 `(ok, 对象或原因)`。**读不到就是读不到**，不返回空对象顶替。"""
    if yaml is None:
        return False, "**未读到 PyYAML**（解释器里没有 `yaml` 模块）⇒ 判据没跑"
    if not path.is_file():
        return False, "**未读到文件**：%s" % path
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:                                 # pragma: no cover
        return False, "**读不了**：%s（%s）" % (path, type(exc).__name__)
    try:
        return True, yaml.load(text, Loader=_Lenient)
    except Exception as exc:
        return False, "**YAML 解析失败**：%s: %s" % (type(exc).__name__, str(exc).splitlines()[0][:160])


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def find_route_row(patch_obj, route: str) -> dict:
    """在 patch 里找 `llm-pi-ai` 那行的 `providers.<route>`。

    返回 `{行 id, provider 配置}` —— 找不到时 `行 id` 与配置都是 `None`（**不是空字典**）。
    """
    for d in walk(patch_obj):
        cfg = d.get("config")
        if not isinstance(cfg, dict):
            continue
        provs = cfg.get("providers")
        if not isinstance(provs, dict):
            continue
        p = provs.get(route)
        if isinstance(p, dict):
            return {"行 id": d.get("id"), "provider": p}
    return {"行 id": None, "provider": None}


def read_known_apis(pi_ai_types: Path) -> tuple:
    """从 pi-ai 的 `types.d.ts` **现读**协议名单（`KnownApi` 联合）。

    返回 `(名单 或 None, 说明)`。**读不到返回 None**，绝不退回硬编码名单。
    """
    if not pi_ai_types.is_file():
        return None, "**未读到 pi-ai 类型定义**：%s" % pi_ai_types
    text = pi_ai_types.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"export type KnownApi\s*=\s*([^;]+);", text)
    if not m:
        return None, "**在类型定义里找不到 `KnownApi`**（pi-ai 结构变了 ⇒ 判据要跟着改）"
    names = re.findall(r'"([^"]+)"', m.group(1))
    if not names:
        return None, "**`KnownApi` 解析出 0 个协议名**（不拿 0 冒充「没有协议」）"
    return names, "现读 %d 个协议" % len(names)


def read_known_providers(pi_ai_types: Path) -> tuple:
    if not pi_ai_types.is_file():
        return None, "**未读到 pi-ai 类型定义**"
    text = pi_ai_types.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"export type KnownProvider\s*=\s*([^;]+);", text)
    if not m:
        return None, "**在类型定义里找不到 `KnownProvider`**"
    return re.findall(r'"([^"]+)"', m.group(1)), "现读"


def judge_provider(p: dict, route: str, known_apis) -> tuple:
    """判 provider 配置的**形状**。返回 `(问题清单, 读数)`。"""
    bad, reading = [], {}
    reading["api"] = p.get("api")
    reading["baseURL"] = p.get("baseURL")
    reading["apiKeyEnv"] = p.get("apiKeyEnv")
    reading["displayName"] = p.get("displayName")

    models = p.get("models")
    if not isinstance(models, list) or not models:
        bad.append("`models` **未读到或为空**（路由必须至少声明一个模型 id）")
        reading["模型 id"] = None
    else:
        ids = [m.get("id") for m in models if isinstance(m, dict) and m.get("id")]
        reading["模型 id"] = ids
        if len(ids) != len(models):
            bad.append("`models` 里有条目**没有 `id`**（%d 条里只有 %d 条有 id）" % (len(models), len(ids)))

    api = reading["api"]
    if not isinstance(api, str) or not api.strip():
        bad.append("🔴 **缺 `api`**（pi-ai 的协议名）—— 本仓真踩过：漏了它路由**静默不合形**")
    elif known_apis is None:
        reading["api 合法性"] = "**判据没跑**（未读到 pi-ai 的协议名单）"
    elif api not in known_apis:
        bad.append("`api=%s` **不在 pi-ai 现读的协议名单里**" % api)
    else:
        reading["api 合法性"] = "在名单里（%d 个协议现读）" % len(known_apis)

    base = reading["baseURL"]
    if not isinstance(base, str) or not base.strip():
        bad.append("**缺 `baseURL`**")
    else:
        loopback = bool(re.match(r"^http://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?/", base))
        if not base.startswith("https://") and not loopback:
            bad.append("`baseURL` **不是 https 也不是回环**（%s…）⇒ 明文出网，拒" % base[:14])
        elif loopback:
            reading["回环明文"] = "允许（只在本机回环上，不出网）"
        if "/v1" not in base:
            bad.append("`baseURL` **不含 `/v1`**（OpenAI 兼容面的约定路径）")

    if not isinstance(reading["apiKeyEnv"], str) or not reading["apiKeyEnv"].strip():
        bad.append("**缺 `apiKeyEnv`**（没有它协议层取不到钥匙）")
    return bad, reading


def lookup_secret(name: str) -> tuple:
    """按**凭据服务自己的层次**找一把值：进程环境 → 用户级环境（Windows）→ 凭据文件。

    返回 `(值 或 None, 来源说明)`。**值只回给调用方做调用**，绝不进读数。
    🔴 为什么必须查环境：本机免费路由那把 key 就是**用户级环境变量**（现读 59 位），
    凭据服务报 `source=env, writable=false` ⇒ 只查凭据文件会把「已配」判成「未配」（假红）。
    """
    if not isinstance(name, str) or not name.strip():
        return None, None
    v = os.environ.get(name)
    if isinstance(v, str) and v:
        return v, "进程环境"
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                val, _ = winreg.QueryValueEx(k, name)
            if isinstance(val, str) and val:
                return val, "用户级环境（新进程可见）"
        except Exception:
            pass
    return None, None


def judge_credentials(env_name, creds_obj) -> dict:
    """只报「已配/未配 + 来源 + 位数 + 指纹」。**明文永不进返回结构。**"""
    if not isinstance(env_name, str) or not env_name.strip():
        return {"状态": "**未判**（没读到 `apiKeyEnv` 名字）", "位数": None, "指纹": None, "来源": None}
    value, source = lookup_secret(env_name)
    if value:
        _SECRETS.append(value)
        return {"状态": "已配", "来源": source, "位数": len(value), "指纹": sha6(value) + "****"}
    if not isinstance(creds_obj, dict):
        return {"状态": "🔴 **未配**（环境与凭据文件里都没有 %s）" % env_name,
                "位数": None, "指纹": None, "来源": None}
    refs = creds_obj.get("refs")
    if not isinstance(refs, dict):
        return {"状态": "🔴 **未配**（凭据文件里没有 `refs` 段）", "位数": None, "指纹": None,
                "来源": None}
    val = refs.get(env_name)
    if not isinstance(val, str) or not val:
        return {"状态": "🔴 **未配**（环境与 `refs` 里都没有 %s）" % env_name,
                "位数": None, "指纹": None, "来源": None}
    _SECRETS.append(val)
    return {"状态": "已配", "来源": "凭据文件", "位数": len(val), "指纹": sha6(val) + "****"}


def run(home: Path, profile: str, route: str, pi_ai_types: Path | None, model_id: str | None) -> dict:
    """纯现读：**不写任何东西**。返回结构化读数（`ok` 是唯一判决）。"""
    patch = home / "profiles" / profile / "cordis.patch.yml"
    creds_path = home / ".credentials.yaml"
    settings_path = home / "settings.yaml"
    if pi_ai_types is None:
        pi_ai_types = home / "profiles" / "node_modules" / "@earendil-works" / "pi-ai" / "dist" / "types.d.ts"

    rep: dict = {"落点": {
        "patch": str(patch), "凭据": str(creds_path),
        "settings（只查漂移）": str(settings_path), "pi-ai 类型": str(pi_ai_types)},
        "路由": route, "profile": profile}

    ok, patch_obj = load_yaml(patch)
    if not ok:
        rep["**判决**"] = "未读到"
        rep["为什么"] = patch_obj
        rep["ok"] = False
        rep["退出码口径"] = 2
        return rep
    rep["patch sha256"] = hashlib.sha256(patch.read_bytes()).hexdigest()[:12]

    if not isinstance(patch_obj, list):
        rep["**判决**"] = "形状不对"
        rep["为什么"] = ("patch 层必须是**顶层 YAML 数组**（官方注释的口径），"
                      "现读到的是 %s" % type(patch_obj).__name__)
        rep["ok"] = False
        rep["退出码口径"] = 2
        return rep
    rep["patch 条目数"] = len(patch_obj)

    known_apis, api_note = read_known_apis(pi_ai_types)
    known_provs, _ = read_known_providers(pi_ai_types)
    rep["协议名单判据"] = api_note
    rep["pi-ai 认识「自己人」吗"] = ("是（%s 在 KnownProvider 里）" % route
                             if known_provs and route in known_provs
                             else "否（自定义路由名，靠 config 声明即可）")

    row = find_route_row(patch_obj, route)
    rep["承载行"] = row["行 id"]
    if row["provider"] is None:
        rep["**判决**"] = "路由不在 patch 里"
        rep["为什么"] = ("patch 里没有任何 `config.providers.%s`（路由的唯一活载路径就是这里；"
                      "只写 settings.yaml **不生效** —— 宿主只在启动读，且服务会重写那个文件）" % route)
        rep["ok"] = False
        rep["退出码口径"] = 1
        return rep

    bad, reading = judge_provider(row["provider"], route, known_apis)
    rep["provider 读数"] = reading

    creds_obj = None
    if creds_path.is_file():
        cok, creds_obj = load_yaml(creds_path)
        if not cok:
            creds_obj = None
    rep["凭据"] = judge_credentials(reading.get("apiKeyEnv"), creds_obj)
    if str(rep["凭据"]["状态"]).startswith("🔴"):
        bad.append("🔴 **`apiKeyEnv` 指的凭据在装机凭据里不存在** ⇒ 协议层会直接报 "
                   "`No API key for provider`（本仓真踩过）")

    if model_id and isinstance(reading.get("模型 id"), list) and model_id not in reading["模型 id"]:
        bad.append("`--model %s` 不在 `models` 里（现读：%s）" % (model_id, ", ".join(reading["模型 id"])))

    drift = None
    if settings_path.is_file():
        sok, settings_obj = load_yaml(settings_path)
        if sok and isinstance(settings_obj, dict):
            hit = find_route_row(settings_obj, route)
            if hit["provider"] is not None:
                drift = ("⚠️ **settings.yaml 里也有一份 `%s`** ⇒ 单一真源被破坏："
                         "服务会用自己的内存态重写那个文件，两份迟早打架" % route)
    rep["漂移"] = drift or "无（settings.yaml 里没有同名路由，符合预期）"

    rep["**判决**"] = "形状合规" if not bad else "有问题"
    rep["问题"] = bad
    rep["ok"] = not bad
    rep["退出码口径"] = 0 if not bad else 1
    return rep


MINI_PROMPT = "只回两个字：收到"


def _soft_json(raw: bytes):
    """回包解不出 JSON ⇒ 返回 `None`（**未读到**），**不返回 `{}`** 冒充「空对象」。"""
    try:
        v = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return None
    return v if isinstance(v, dict) else None


def _key_from_install(home: Path, env):
    """取钥匙：**先环境后凭据文件**（与凭据服务同层次）。取不到返回 `None`。"""
    value, _src = lookup_secret(env)
    if value:
        return value
    if not home:
        return None
    creds_path = home / ".credentials.yaml"
    if not creds_path.is_file():
        return None
    cok, cobj = load_yaml(creds_path)
    if cok and isinstance(cobj, dict) and isinstance(cobj.get("refs"), dict):
        v = cobj["refs"].get(env)
        if isinstance(v, str) and v:
            return v
    return None


def live_check(rep: dict, home: Path, timeout: float = 60.0) -> dict:
    """四发两态真打：**公开面**（`/v1/models` 不带钥匙必须 200）· **令牌面**
    （`/v1/chat/completions` 不带钥匙必须 401 · 带钥匙必须 200 且**真出字**）。

    🔴 为什么必须是「两条路 × 两态」：
      ① 只有一态时，「闸没开」与「闸开着且我带对了钥匙」读数**长得一模一样**
         （本仓同型教训：判据分辨不出它分辨了什么）；
      ② 只知道「闸已开」而不问**管哪一条路**，就会把公开的 `/v1/models` 读成「全局已锁」——
         2026-09-25 本工具**第一次跑就当场咬出这个错**（老版自报只写一句「令牌闸已开」）。
    """
    prov = rep.get("provider 读数") or {}
    base, ids, env = prov.get("baseURL"), prov.get("模型 id"), prov.get("apiKeyEnv")
    key = _key_from_install(home, env)
    if not isinstance(base, str) or not base:
        return {"live": "**未读到 baseURL** ⇒ 没打", "ok": False}
    root = base.rstrip("/")
    mid = ids[0] if isinstance(ids, list) and ids else "gbt-potato-v8"

    def probe(path: str, auth: bool, payload=None) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(root + path, data=data, method=("POST" if data else "GET"),
                                     headers={"User-Agent": UA, "Accept": "application/json"})
        if data:
            req.add_header("Content-Type", "application/json")
        if auth:
            if not key:
                return {"http": None, "error": "**未读到钥匙** ⇒ 这一发没打", "json": None}
            req.add_header("Authorization", "Bearer " + key)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {"http": resp.status, "json": _soft_json(resp.read())}
        except urllib.error.HTTPError as exc:
            return {"http": exc.code, "json": _soft_json(exc.read())}
        except Exception as exc:
            return {"http": None, "json": None, "error": "%s: %s" % (type(exc).__name__, str(exc)[:160])}

    chat_body = {"model": mid, "messages": [{"role": "user", "content": MINI_PROMPT}], "max_tokens": 64}
    m_no = probe("/models", False)
    m_yes = probe("/models", True)
    c_no = probe("/chat/completions", False, chat_body)
    c_yes = probe("/chat/completions", True, chat_body)
    bad, reading = judge_live(m_no, m_yes, c_no, c_yes, ids)
    reading.update({"live 落点": root, "问题": bad, "ok": not bad,
                    "口径": ("① 带钥匙两条路都必须 200 · ② 每条路自己两态（不带钥匙 200=公开面 / "
                           "401=令牌面，别的码一律「说不清」）· ③ 端点自报 `auth_scope` 时"
                           "**自报必须与实测一致** · ④ 带钥匙那一发必须真出字")})
    return reading


def judge_live(m_no: dict, m_yes: dict, c_no: dict, c_yes: dict, ids) -> tuple:
    """把「四发」判成 `(问题清单, 读数)`。

    🔴 特意做成**纯函数**：自检能拿**合成靶**逐条钉住每一个判决分支
    （本仓纪律：每条诚实/降级分支都必须有一条能被真触发的控制）。

    判据是**通用的**，不假设谁家端点长什么样（我们自己的云 Worker 与本机免费路由
    **形状不同**，同一套判据必须都能判）：
      · **形状**：带钥匙打 `/v1/models` 与 `/v1/chat/completions` 都必须 200；
      · **面**：每条路**自己两态**（不带钥匙 200 = 公开面 · 401 = 令牌面）；
        🔴 不带钥匙回了别的码（500/403/超时）⇒ 点名 —— 「说不清」不许被念成「面」；
      · 🔴 **声明必须与实测一致**：端点自报 `auth_scope` 时，自报的面必须与**测出来的面**
        逐条对上。这就是「宣称有、代码没有」那类错的机器判据 —— 2026-09-25 本工具
        **第一次跑就靠它咬出**「自报全局已锁、其实 `/v1/models` 公开」。
      · **功能**：带钥匙那一发必须**真出字**（`choices[0].message.content` 非空）。
    """
    gbt = ((m_no.get("json") or {}).get("gbt") or {})
    scope = gbt.get("auth_scope")
    ids_seen = [m.get("id") for m in ((m_yes.get("json") or {}).get("data") or []) if isinstance(m, dict)]
    choices = ((c_yes.get("json") or {}).get("choices") or [])
    content = None
    if choices and isinstance(choices[0], dict):
        content = ((choices[0].get("message") or {}).get("content"))
    content = content if isinstance(content, str) and content.strip() else None

    models_public = (m_no.get("http") == 200)
    chat_gated = (c_no.get("http") == 401)
    face_models = "公开面（不带钥匙也 200）" if models_public else "令牌面（不带钥匙 401）"
    face_chat = "令牌面（不带钥匙 401）" if chat_gated else (
        "公开面（不带钥匙也 200）" if c_no.get("http") == 200 else "说不清")

    bad = []
    if m_yes.get("http") != 200:
        bad.append("带钥匙打 `/v1/models` **没回 200**（现读 %s）" % m_yes.get("http"))
    if c_yes.get("http") != 200:
        bad.append("带钥匙打 `/v1/chat/completions` **没回 200**（现读 %s）" % c_yes.get("http"))
    if m_no.get("http") not in (200, 401):
        bad.append("**说不清**：不带钥匙打 `/v1/models` 回的码是 %s（既非公开面 200、也非令牌面 401）"
                   % m_no.get("http"))
    if c_no.get("http") not in (200, 401):
        bad.append("**说不清**：不带钥匙打 `/v1/chat/completions` 回的码是 %s" % c_no.get("http"))
    if content is None:
        bad.append("令牌面：带钥匙那一发**没读出正文**（`choices[0].message.content` 未读到）"
                   "⇒ 别把「接线通了」念成「模型答了」")
    if ids_seen and not all(i in ids_seen for i in (ids or [])):
        bad.append("`/v1/models` 自报的模型 id %s **不含 patch 声明的** %s" % (ids_seen, ids))

    declared = "未自报（不算问题：这一条判据没跑）"
    if not isinstance(scope, dict):
        declared = "未自报"
    else:
        declared = scope
        if scope.get("models") == "public" and not models_public:
            bad.append("🔴 **自报与实测打架**：自报 `models=public`，实测不带钥匙回 %s"
                       % m_no.get("http"))
        if scope.get("models") == "gated" and models_public:
            bad.append("🔴 **自报与实测打架**：自报 `models=gated`，实测不带钥匙回 200")
        if scope.get("chat") == "bearer" and not chat_gated:
            bad.append("🔴 **自报与实测打架**：自报 `chat=bearer`（要 Bearer），实测不带钥匙回 %s"
                       "⇒ **令牌闸没开**，这个端点现在谁都能调" % c_no.get("http"))
        if scope.get("chat") == "none" and chat_gated:
            bad.append("🔴 **自报与实测打架**：自报 `chat=none`（不校验），实测不带钥匙回 401")

    reading = {"① 带钥匙 · `/v1/models`": {"http": m_yes.get("http"), "自报模型数": len(ids_seen)},
               "② 带钥匙 · `/v1/chat/completions`": {"http": c_yes.get("http"), "正文": content,
                                                  "字数": (len(content) if content else None),
                                                  "上游": gbt.get("upstream"),
                                                  "权重是我们的吗": gbt.get("weights_ours")},
               "③ 不带钥匙 · `/v1/models`": {"http": m_no.get("http"), "判成": face_models,
                                         "自报 auth": gbt.get("auth")},
               "④ 不带钥匙 · `/v1/chat/completions`": {
                   "http": c_no.get("http"), "判成": face_chat,
                   "回包": ((c_no.get("json") or {}).get("error") or {})},
               "端点自报的面": declared}
    return bad, reading


def judge_models(rows: dict, ids) -> tuple:
    """判「patch 里声明的每个模型是不是**真能答**」。返回 `(问题清单, 读数)`。

    🔴 为什么必须逐个真打：本机免费路由的 `GET /v1/models` 里，
    `kimi-k3` 自报 `available: true`，**真调却回** `no_providers_configured`
    （"no key configured for their platform"）—— **它的 available 是乐观值**。
    ⇒ 「它说可用」不算数，**一次真调用**才算数（本仓口径：声明 ≠ 已验证）。
    """
    bad, passing, failing = [], [], []
    for mid in (ids or []):
        r = rows.get(mid) or {}
        http, chars = r.get("http"), r.get("字数")
        if http == 200 and isinstance(chars, int) and chars > 0:
            passing.append(mid)
        else:
            failing.append({"模型": mid, "http": http, "字数": chars,
                            "报错": (r.get("报错") or "")[:120]})
    if failing:
        bad.append("🔴 **patch 里声明了 %d 个模型，其中 %d 个真调不通** ⇒ 用户在下拉里选中它就会当场失败"
                   % (len(ids or []), len(failing)))
    return bad, {"总声明": len(ids or []), "真答得出": passing, "真答不出": failing,
                 "逐个读数": rows}


def _one_call(base: str, key, mid: str, timeout: float = 120.0) -> dict:
    """对某个模型发**一次最小真调用**，回 `{http, 字数, 毫秒, 报错}`（**正文不回**，太长没用）。"""
    import time
    url = base.rstrip("/") + "/chat/completions"
    body = json.dumps({"model": mid, "messages": [{"role": "user", "content": "只回两个字：收到"}],
                       "max_tokens": 32}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"User-Agent": UA, "Content-Type": "application/json",
                                          "Accept": "application/json"})
    if key:
        req.add_header("Authorization", "Bearer " + key)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = _soft_json(resp.read())
            http = resp.status
    except urllib.error.HTTPError as exc:
        payload, http = _soft_json(exc.read()), exc.code
    except Exception as exc:
        return {"http": None, "字数": None, "毫秒": int((time.time() - t0) * 1000),
                "报错": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
    ms = int((time.time() - t0) * 1000)
    content = None
    choices = ((payload or {}).get("choices") or [])
    if choices and isinstance(choices[0], dict):
        content = ((choices[0].get("message") or {}).get("content"))
    if not isinstance(content, str) or not content.strip():
        return {"http": http, "字数": 0, "毫秒": ms,
                "报错": (((payload or {}).get("error") or {}).get("message") or "回包里没有正文")}
    return {"http": http, "字数": len(content.strip()), "毫秒": ms, "报错": None}


def cmd_models(a) -> int:
    home = Path(a.home)
    rep = run(home, a.profile, a.route, None, None)
    prov = rep.get("provider 读数") or {}
    base, env = prov.get("baseURL"), prov.get("apiKeyEnv")
    if not isinstance(base, str) or not base:
        print(redact(json.dumps({"ok": False, "为什么": "**未读到 baseURL**（路由不在 patch 里？）"},
                                ensure_ascii=False)))
        return 2
    key = _key_from_install(home, env)
    if not key:
        print(redact(json.dumps({"ok": False,
                                 "为什么": "**未读到钥匙**（`apiKeyEnv=%s` 环境与凭据文件里都没有）" % env},
                                ensure_ascii=False)))
        return 2

    # `--ids` = **候选试跑**：只量这些，**不当判据、不改 patch**（先测再决定要不要写进去）
    candidates = [x.strip() for x in (a.ids or "").split(",") if x.strip()]
    ids = candidates or (prov.get("模型 id") or [])
    rows = {mid: _one_call(base, key, mid, timeout=a.timeout) for mid in ids}
    bad, reading = judge_models(rows, ids)
    if candidates:
        bad = []                                     # 候选试跑不构成判决
    out = {"路由": a.route, "落点": base, "模式": ("候选试跑（不判、不改）" if candidates else "验收 patch 声明"),
           "ok": not bad, "问题": bad, **reading}
    print(redact(json.dumps(out, ensure_ascii=False, indent=1)))
    if candidates:
        print("候选试跑：答得出 %d / %d —— 要把哪个写进 patch 由我按读数决定"
              % (len(reading["真答得出"]), reading["总声明"]))
    else:
        print("✅ 声明的模型逐个真答得出（%d/%d）" % (len(reading["真答得出"]), reading["总声明"])
              if not bad else "🔴 有模型**真调不通**（见上）—— 别把它留在下拉里")
    return 0 if not bad else 1


def cmd_check(a) -> int:
    rep = run(Path(a.home), a.profile, a.route, Path(a.pi_ai) if a.pi_ai else None, a.model)
    if a.live and rep.get("ok"):
        rep = dict(rep)
        rep["live"] = live_check(rep, Path(a.home))
        rep["ok"] = bool(rep["ok"]) and bool(rep["live"].get("ok"))
    text = redact(json.dumps(rep, ensure_ascii=False, indent=1))
    print(text)
    if rep.get("ok"):
        print("✅ 路由可核：声明在 patch 里 · 形状合规 · 钥匙已配")
    else:
        print("🔴 路由**没核过**（见上面的「判决」与「问题」）—— 别把它念成「接好了」")
    return 0 if rep.get("ok") else int(rep.get("退出码口径") or 1)


# ── 自检（全在临时靶上，**不碰真配置**）─────────────────────────────────────
GOOD_PROVIDER = {
    "apiKeyEnv": "FAKE_API_KEY",
    "api": "openai-completions",
    "baseURL": "https://example.invalid/v1",
    "displayName": "假靶",
    "models": [{"id": "fake-model", "name": "假靶"}],
}
FAKE_SECRET = "deadbeef" * 6                                   # 48 位，形状与真钥匙一致


def _fixture_home(td: Path, provider=None, *, patch=True, top_list=True, creds=True,
                  refs=None, with_js=False, no_route=False) -> Path:
    home = td / ("h%d" % len(list(td.iterdir())))
    (home / "profiles" / "web").mkdir(parents=True)
    if patch:
        if no_route:                                     # 靶：patch 在，但里面**没有**这条路由
            body = {"insert": [{"id": "gbt-master", "name": "x", "config": {}}]}
        else:
            prov = GOOD_PROVIDER if provider is None else provider
            body = {"insert": [{"id": "llm-pi-ai", "config": {"providers": {"gbt-potato": prov}}}]}
        obj = [body] if top_list else body
        if with_js:
            (home / "profiles" / "web" / "cordis.patch.yml").write_text(
                "# 带自定义 tag 的靶\n- insert:\n    - id: llm-pi-ai\n      config:\n"
                "        providers:\n          gbt-potato:\n"
                "            api: openai-completions\n"
                "            baseURL: https://example.invalid/v1\n"
                "            apiKeyEnv: FAKE_API_KEY\n"
                "            note: !!js process.env.X\n"
                "            models: [{id: fake-model}]\n",
                encoding="utf-8")
        else:
            (home / "profiles" / "web" / "cordis.patch.yml").write_text(
                yaml.safe_dump(obj, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if creds:
        r = {"FAKE_API_KEY": FAKE_SECRET} if refs is None else refs
        (home / ".credentials.yaml").write_text(
            yaml.safe_dump({"version": 1, "refs": r}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return home


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    pi = None
    real_types = dsh_home() / "profiles" / "node_modules" / "@earendil-works" / "pi-ai" / "dist" / "types.d.ts"
    if real_types.is_file():
        pi = real_types
    types = pi or (Path(tempfile.gettempdir()) / "no-such-types.d.ts")

    with tempfile.TemporaryDirectory() as tds:
        td = Path(tds)

        # ① 正控：形状合规 + 钥匙已配 ⇒ ok
        h = _fixture_home(td)
        r = run(h, "web", "gbt-potato", types, None)
        ck("**正控：合规 patch + 已配钥匙 ⇒ ok**", r["ok"] is True and r["承载行"] == "llm-pi-ai",
           "判决=%s ｜ 凭据=%s" % (r.get("**判决**"), (r.get("凭据") or {}).get("状态")))

        # ①b `--model` 断言的语义：**只有显式给了**才当判据（不给 ⇒ 不许自己塞一个）
        r1b = run(h, "web", "gbt-potato", types, None)
        r1c = run(h, "web", "gbt-potato", types, "fake-model")
        r1d = run(h, "web", "gbt-potato", types, "别的路由的模型名")
        ck("**正控：不给 `--model` ⇒ 不自己塞默认值（不产生假红）**",
           r1b["ok"] is True and not any("不在 `models` 里" in x for x in r1b["问题"]),
           "问题=%s" % r1b["问题"])
        ck("**正控：显式给对 `--model` ⇒ 过；给错 ⇒ 点名**",
           r1c["ok"] is True and r1d["ok"] is False
           and any("不在 `models` 里" in x for x in r1d["问题"]),
           "对=%s ｜ 错=%s" % (r1c["ok"], r1d.get("问题")))

        # ② 负控：读不到 patch ⇒ **未读到**（rc 口径 2），不许当「没有路由」以外的任何东西
        h2 = _fixture_home(td, patch=False)
        r2 = run(h2, "web", "gbt-potato", types, None)
        ck("**负控：patch 不在盘上 ⇒ 未读到（rc=2），不是 rc=1**",
           r2["ok"] is False and r2["退出码口径"] == 2 and r2["**判决**"] == "未读到",
           "判决=%s ｜ rc=%s" % (r2["**判决**"], r2["退出码口径"]))

        # ③ 负控：顶层不是数组（官方口径是「顶层数组」）⇒ rc=2 点名
        h3 = _fixture_home(td, top_list=False)
        r3 = run(h3, "web", "gbt-potato", types, None)
        ck("**负控：patch 顶层不是数组 ⇒ 点名且 rc=2**",
           r3["ok"] is False and r3["退出码口径"] == 2 and "数组" in str(r3.get("为什么")),
           str(r3.get("为什么"))[:52])

        # ④ 负控：**缺 `api`**（本仓真踩过：漏了静默不合形）⇒ 必须点名
        p = dict(GOOD_PROVIDER)
        p.pop("api")
        r4 = run(_fixture_home(td, provider=p), "web", "gbt-potato", types, None)
        ck("**负控：缺 `api` ⇒ 必须点名（真踩过的那种坏法）**",
           r4["ok"] is False and any("缺 `api`" in x for x in r4["问题"]), str(r4.get("问题"))[:60])

        # ⑤ 负控：`api` 不在 pi-ai 现读名单里 ⇒ 点名
        p = dict(GOOD_PROVIDER, api="not-a-real-protocol")
        r5 = run(_fixture_home(td, provider=p), "web", "gbt-potato", types, None)
        ck("**负控：`api` 不在 pi-ai 名单里 ⇒ 点名**",
           r5["ok"] is False and any("不在 pi-ai 现读的协议名单里" in x for x in r5["问题"]),
           str(r5.get("问题"))[:60])

        # ⑥ 负控：`apiKeyEnv` 指的凭据不存在 ⇒ 点名（真踩过的 `No API key for provider`）
        r6 = run(_fixture_home(td, refs={"别的键": "x"}), "web", "gbt-potato", types, None)
        ck("**负控：钥匙未配 ⇒ 点名且判决不过**",
           r6["ok"] is False and str((r6.get("凭据") or {}).get("状态")).startswith("🔴"),
           str((r6.get("凭据") or {}).get("状态"))[:52])

        # ⑥b 正控：**环境里配的凭据也算已配**（本机免费路由那把 key 就是用户级环境变量）
        env_name, env_val = "GBT_SELFTEST_ENVKEY", "z" * 24
        os.environ[env_name] = env_val
        try:
            p6b = dict(GOOD_PROVIDER, apiKeyEnv=env_name)
            r6b = run(_fixture_home(td, provider=p6b, refs={"别的键": "x"}), "web", "gbt-potato", types, None)
            cred6b = r6b.get("凭据") or {}
            printed6b = redact(json.dumps(r6b, ensure_ascii=False))
            ck("**正控：环境变量里的凭据也算「已配」，且来源要写清**",
               r6b["ok"] is True and cred6b.get("来源") == "进程环境" and cred6b.get("位数") == 24,
               "来源=%s ｜ 位数=%s" % (cred6b.get("来源"), cred6b.get("位数")))
            ck("**🔴 负控：环境来的密钥同样不许出现在读数里**",
               env_val not in printed6b, "指纹=%s" % cred6b.get("指纹"))
        finally:
            os.environ.pop(env_name, None)

        # ⑦ 负控：baseURL 是 http / 不含 /v1 ⇒ 两条都要点名
        p = dict(GOOD_PROVIDER, baseURL="http://plain.example.com")
        r7 = run(_fixture_home(td, provider=p), "web", "gbt-potato", types, None)
        ck("**负控：http + 不含 `/v1` ⇒ 两条都点名**",
           r7["ok"] is False and sum("baseURL" in x for x in r7["问题"]) == 2,
           str(r7.get("问题"))[:60])

        # ⑦b 正控：**回环明文放行**（本机免费路由就是 `http://127.0.0.1:31415/v1`）
        p = dict(GOOD_PROVIDER, baseURL="http://127.0.0.1:31415/v1")
        r7b = run(_fixture_home(td, provider=p), "web", "gbt-potato", types, None)
        ck("**正控：回环 `http://127.0.0.1:…/v1` 放行（本机路由必需）**",
           r7b["ok"] is True and (r7b["provider 读数"] or {}).get("回环明文", "").startswith("允许"),
           "判决=%s ｜ %s" % (r7b.get("**判决**"), (r7b["provider 读数"] or {}).get("回环明文")))
        ck("**负控：长得像回环但不是（`127.0.0.1.evil.com`）⇒ 仍要拒**",
           run(_fixture_home(td, provider=dict(GOOD_PROVIDER, baseURL="http://127.0.0.1.evil.com/v1")),
               "web", "gbt-potato", types, None)["ok"] is False,
           "非回环 http 必须被拒")

        # ⑧ 🔴 负控（本仓红线）：**打印里不许出现密钥明文**
        h8 = _fixture_home(td)
        r8 = run(h8, "web", "gbt-potato", types, None)
        printed = redact(json.dumps(r8, ensure_ascii=False))
        ck("**🔴 负控：读数里不许出现密钥明文（真值必须在内存里被替换掉）**",
           FAKE_SECRET not in printed and "****" in str((r8.get("凭据") or {}).get("指纹")),
           "指纹=%s" % (r8.get("凭据") or {}).get("指纹"))

        # ⑨ 正控：patch 里有 `!!js` 自定义 tag ⇒ **不许崩**（官方注释明说允许）
        h9 = _fixture_home(td, with_js=True)
        r9 = run(h9, "web", "gbt-potato", types, None)
        ck("**正控：`!!js` 自定义 tag 不许把配置读成坏的**",
           r9.get("**判决**") not in ("未读到", "形状不对") and r9.get("承载行") == "llm-pi-ai",
           "判决=%s" % r9.get("**判决**"))

        # ⑨b 负控：**读不到 pi-ai 类型定义 ⇒ 那条判据必须明说「没跑」**，不许默不作声地过
        r9b = run(_fixture_home(td), "web", "gbt-potato", td / "__没有这个__.d.ts", None)
        ck("**负控：读不到 pi-ai 类型定义 ⇒ 明写「判据没跑」（不许当合格）**",
           "判据没跑" in str((r9b.get("provider 读数") or {}).get("api 合法性"))
           or "未读到 pi-ai" in str(r9b.get("协议名单判据")),
           "api 合法性=%s" % (r9b.get("provider 读数") or {}).get("api 合法性"))

        # ⑨c 负控：`models` 为空 ⇒ 必须点名（不许"路由看起来在"就完事）
        r9c = run(_fixture_home(td, provider=dict(GOOD_PROVIDER, models=[])), "web", "gbt-potato", types, None)
        ck("**负控：`models` 为空 ⇒ 点名**",
           r9c["ok"] is False and any("未读到或为空" in x for x in r9c["问题"]), str(r9c["问题"])[:60])

        # ⑨d 负控：`cmd_models` 在「路由不在 patch 里」时**必须 rc=2 并明说未读到 baseURL**
        class _NS:
            home = str(_fixture_home(td, no_route=True))
            profile, route, ids, timeout = "web", "gbt-free", None, 5.0

        class _NS2:
            home = str(_fixture_home(td, refs={"别的键": "x"}))
            profile, route, ids, timeout = "web", "gbt-potato", None, 5.0

        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            rc9d = cmd_models(_NS)
        _buf2 = io.StringIO()
        with contextlib.redirect_stdout(_buf2):
            rc9e = cmd_models(_NS2)
        ck("**负控：没这条路由时 `models` 子命令 ⇒ rc=2 且说「未读到 baseURL」**",
           rc9d == 2 and "未读到 baseURL" in _buf.getvalue(), "rc=%d" % rc9d)
        ck("**负控：钥匙解不出来时 `models` 子命令 ⇒ rc=2（不许硬发）**",
           rc9e == 2 and "未读到钥匙" in _buf2.getvalue(),
           "rc=%d ｜ %s" % (rc9e, _buf2.getvalue().strip()[:60]))

        # ⑨f 负控：`live_check` 在**没钥匙**时「带钥匙那一发」要如实记「未读到钥匙」而不是抛异常
        fake_rep = {"provider 读数": {"baseURL": "http://127.0.0.1:1/v1", "模型 id": ["x"],
                                    "apiKeyEnv": "GBTSELFTEST_NO_SUCH_KEY"}}
        live9f = live_check(fake_rep, td / "没有这个家", timeout=2.0)
        ck("**负控：没钥匙时 `live` 如实记「未读到钥匙」，不许崩**",
           live9f.get("ok") is False and "live 落点" in live9f,
           "ok=%s ｜ 问题数=%d" % (live9f.get("ok"), len(live9f.get("问题") or [])))

        # ⑩ 纯函数 `judge_live` 的合成靶：每条判决分支都要有一条能被真触发的控制
        def live_fx(scope=..., m_no=200, m_yes=200, c_no=401, c_yes=200, content="收到"):
            sc = {"chat": "bearer", "models": "public"} if scope is ... else scope
            gbt = {"auth": "…"} if sc is None else {"auth": "…", "auth_scope": sc}
            return ({"http": m_no, "json": {"gbt": gbt}},
                    {"http": m_yes, "json": {"data": [{"id": "gbt-potato-v8"}]}},
                    {"http": c_no, "json": {"error": {"message": "Authorization 不对"}}},
                    {"http": c_yes, "json": {"choices": [{"message": {"content": content}}]}})

        badA, _ = judge_live(*live_fx(), ["gbt-potato-v8"])
        ck("**正控A：云 Worker 形状（自报 public/bearer + 两态对得上）⇒ 不报**",
           badA == [], str(badA)[:60])

        badB, _ = judge_live(*live_fx(scope=None, m_no=401), ["gbt-potato-v8"])
        ck("**正控B：另一种形状（不自报 · 两条路都是令牌面）⇒ 不报**"
           "（判据不许只认我们那一家的样子）",
           badB == [], str(badB)[:60])

        badC, _ = judge_live(*live_fx(m_no=401), ["gbt-potato-v8"])
        ck("**负控：自报 `models=public` 而实测不带钥匙 401 ⇒ 打架点名**",
           any("自报与实测打架" in x for x in badC), str(badC)[:66])

        badD, _ = judge_live(*live_fx(scope={"chat": "none", "models": "public"}), ["gbt-potato-v8"])
        ck("**负控：自报 `chat=none` 而实测要 401 ⇒ 打架点名**",
           any("自报与实测打架" in x for x in badD), str(badD)[:66])

        badE, _ = judge_live(*live_fx(c_no=200), ["gbt-potato-v8"])
        ck("**🔴 负控：自报 `chat=bearer` 却不带钥匙也 200 ⇒ 必须点名（闸没开）**",
           any("令牌闸没开" in x for x in badE), str(badE)[:66])

        badF, _ = judge_live(*live_fx(c_no=500), ["gbt-potato-v8"])
        ck("**负控：不带钥匙回 500（说不清的面）⇒ 必须点名，不许念成「面」**",
           any("说不清" in x for x in badF), str(badF)[:66])

        badG, _ = judge_live(*live_fx(content="   "), ["gbt-potato-v8"])
        ck("**负控：带钥匙回了 200 但没有正文 ⇒ 必须点名**",
           any("没读出正文" in x for x in badG), str(badG)[:66])

        # ⑪ `judge_models` 的合成靶（"它说可用" 不算数，"真调一次" 才算数）
        badH, _ = judge_models({"a": {"http": 200, "字数": 3}, "b": {"http": 200, "字数": 5}}, ["a", "b"])
        ck("**正控：声明的模型逐个真答得出 ⇒ judge_models 不报**", badH == [], str(badH)[:56])

        badI, readI = judge_models(
            {"a": {"http": 200, "字数": 3}, "b": {"http": 503, "字数": None, "报错": "no key"}}, ["a", "b"])
        ck("**🔴 负控：某个模型真调不通（哪怕目录自报 available）⇒ 必须点名**",
           any("真调不通" in x for x in badI) and readI["真答不出"][0]["模型"] == "b",
           str(badI)[:66])

        badJ, _ = judge_models({"a": {"http": 200, "字数": 0}}, ["a"])
        ck("**负控：回了 200 但正文是空的 ⇒ 也算不通**",
           any("真调不通" in x for x in badJ), str(badJ)[:56])

    # ⑩ 现读真装机（只读）：只判「跑没跑成」，**不把真密钥带进自检输出**
    rep = run(dsh_home(), "web", "gbt-potato", real_types if real_types.is_file() else None, "gbt-potato-v8")
    ck("**现读真装机**（只读现读：路由在不在 · 形状 · 钥匙）",
       rep.get("承载行") == "llm-pi-ai" and isinstance(rep.get("问题"), list),
       "判决=%s ｜ 承载行=%s ｜ 凭据=%s ｜ 可核=%s"
       % (rep.get("**判决**"), rep.get("承载行"), (rep.get("凭据") or {}).get("状态"), rep.get("ok")))

    _SECRETS.clear()
    print(redact(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                             "逐条": checks}, ensure_ascii=False, indent=1)))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="核 DSH 自有模型路由：声明 · 形状 · 钥匙")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "live", "models"):
        s = sub.add_parser(name)
        s.add_argument("--home", default=str(dsh_home()))
        s.add_argument("--profile", default="web")
        s.add_argument("--route", default="gbt-potato")
        s.add_argument("--model", default=None, help="额外断言这个模型 id 在 models 里")
        s.add_argument("--pi-ai", default=None, help="pi-ai 的 types.d.ts（默认从 home 推）")
        s.add_argument("--timeout", type=float, default=120.0, help="单次调用超时（秒）")
        s.add_argument("--ids", default=None,
                       help="只试跑这些模型 id（逗号分隔）——**候选试跑，不判、不改 patch**")
        s.add_argument("--json", action="store_true", help="只输出 JSON（默认也是 JSON，留个明示位）")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "models":
        return cmd_models(a)
    a.live = (a.cmd == "live")
    # 🔴 **不要**在这里给 `--model` 塞默认值：早先写死了 `gbt-potato-v8`，
    #    结果 `live --route gbt-free` 会拿**别人家的模型名**去断言，报出一条**假红**
    #    （本仓最忌的「写死」类错误，而且是我自己犯的）。`live` 自己会用 patch 里
    #    声明的**第一个**模型去真打；`--model` 只在**用户显式给了**时才当判据。
    return cmd_check(a)


if __name__ == "__main__":
    raise SystemExit(main())
