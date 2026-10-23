#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DeepSeek 上游密钥的 DPAPI 保险箱（规格对齐 cloudflare / notion / 星云）。

为什么要有这个文件：
  Codex 的 config.toml 里写的是 env_key = "DEEPSEEK_API_KEY"，
  但本机 HKCU\\Environment 里并没有这个变量 —— 现在能跑，是因为密钥还有一份
  明文副本躺在 ~/.codex/auth.json 与 ~/.codex/.deepseek_key 里。
  "能在跑"不等于"落对了地方"：明文密钥放在用户目录，任何进程都能读。

本模块把密钥收进 DPAPI 保险箱，运行时再解密注入环境变量：
  * 落盘：store/secrets/deepseek_api.dpapi（DPAPI/CurrentUser + 独立熵值，0600）
  * 熵值：GBTxiaotudouV8:deepseek:v1 —— 与飞书/Notion/星云/Cloudflare 互不可解
  * 明文：只进内存（os.environ），不进 argv、不进命令行历史、不进日志

用法：
  "sk-xxx" | py -3.10 -m gbt_allinone.deepseek_key set     # 存（stdin，不回显）
  py -3.10 -m gbt_allinone.deepseek_key status             # 体检（只输出掩码）
  py -3.10 -m gbt_allinone.deepseek_key inject -- <cmd...> # 解密后带环境变量启动子进程

多 profile（2026-09-19 加）：`set|status|inject` 都支持 `--profile <名>`，
默认仍是 deepseek。每个 profile 用**各自的熵值** ⇒ 一个库解不开另一个库。
可用 profile：deepseek · agnes（agnes = apihub.agnes-ai.com 那个 Custom Provider）

开发者：自由的风 · GBT小土豆V8
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gbt_allinone._paths import STORE_DIR  # noqa: E402
from gbt_allinone.safe_io import atomic_write_bytes  # noqa: E402

# 一个 profile 一套（熵值 · 落盘文件名 · 主环境变量 · 代理环境变量 · 覆盖落盘路径的环境变量
#                · 可选的密钥形状正则）。
# 熵值互不相同 ⇒ 甲库密文在乙库里解不开，这是"互不可解"的**机制**，不是约定。
#
# `pattern` 为什么做成**每个 profile 各带一条**（2026-09-25 主人令「密钥全部部署跟双向插件一样、
# 可以自动读取」时加）：原来全库共用一条 `^(?:sk|ak)[-_]…`，而不同上游的密钥形状本来就不同 ——
# ADP（来也）的 key 是纯十六进制长串，**不以 sk-/ak- 开头** ⇒ 共用一条就会把合法密钥判成格式错。
# 给 profile 各带一条（不写就落回下面那条默认的），既收得住"贴错东西/多行粘贴"，又不误杀。
_PROFILES: dict[str, dict] = {
    "deepseek": {
        "entropy": b"GBTxiaotudouV8:deepseek:v1",
        "file": "deepseek_api.dpapi",
        "env": "DEEPSEEK_API_KEY",
        "proxy": "GBT_DEEPSEEK_KEY",
        "file_env": "GBT_DEEPSEEK_SECRET_FILE",
    },
    "agnes": {
        "entropy": b"GBTxiaotudouV8:agnes:v1",
        "file": "agnes_api.dpapi",
        "env": "AGNES_API_KEY",
        "proxy": "",
        "file_env": "GBT_AGNES_SECRET_FILE",
    },
    "adp": {
        "entropy": b"GBTxiaotudouV8:adp:v1",
        "file": "adp_api.dpapi",
        "env": "ADP_API_KEY",
        "proxy": "",
        "file_env": "GBT_ADP_SECRET_FILE",
        # 来也 ADP 的 key 是纯十六进制长串，不带 sk-/ak- 前缀 ⇒ 这条只保证"是单行长串"
        "pattern": r"^[A-Za-z0-9_\-]{20,}$",
    },
    # ── 2026-10-04 迁移清单配套（主人点名「2」：明文令牌迁进 DPAPI 箱）────────────
    # 这四档是"落脚点"：把用户环境里的明文令牌迁进箱（`store/secrets/<档>_api.dpapi`），
    # 环境变量只留引用名。**形状不写死**——它们是不透明的第三方令牌/口令（非 sk-/ak- 前缀），
    # 只保证"单行、8–256 字符、无空白"；写死形状会把没见过的合法值拒之门外（adp 那条的同类教训）。
    # 清单与命令：`state/secret_migration_plan.md`。
    "potato": {
        "entropy": b"GBTxiaotudouV8:potato:v1",
        "file": "potato_api.dpapi",
        "env": "GBT_POTATO_API_KEY",
        "proxy": "",
        "file_env": "GBT_POTATO_SECRET_FILE",
        "pattern": r"^\S{8,256}$",
    },
    "custom": {
        "entropy": b"GBTxiaotudouV8:custom:v1",
        "file": "custom_api.dpapi",
        "env": "GBT_LLM_API_KEY",
        "proxy": "",
        "file_env": "GBT_CUSTOM_SECRET_FILE",
        "pattern": r"^\S{8,256}$",
    },
    "imap": {
        "entropy": b"GBTxiaotudouV8:imap:v1",
        "file": "imap_api.dpapi",
        "env": "GBT_IMAP_PASS",
        "proxy": "",
        "file_env": "GBT_IMAP_SECRET_FILE",
        "pattern": r"^\S{8,256}$",
    },
    "gateway": {
        "entropy": b"GBTxiaotudouV8:gateway:v1",
        "file": "gateway_api.dpapi",
        "env": "GBT_GATEWAY_TOKEN",
        "proxy": "",
        "file_env": "GBT_GATEWAY_SECRET_FILE",
        "pattern": r"^\S{8,256}$",
    },
    # ── 2026-09-25 第二批（主人令「密钥**全部**部署跟双向插件一样、可以自动读取」）────────
    #    背景：这些密钥**只配在 Windows 的 User 作用域**，而本机进程是在那些变量写入**之前**
    #    起的 ⇒ `os.environ` 里一个都没有（F2 就是这条）。收进保险箱后，
    #    框架走 `deepseek_key` 就能自动读到，**不再依赖"进程有没有继承到环境变量"**。
    #    注：注册表里的值**照旧不删** —— 那是主人的配置，别的工具可能在用；
    #    这里只是让框架多一条**不依赖继承**的读法。
    "moonshot": {
        "entropy": b"GBTxiaotudouV8:moonshot:v1",
        "file": "moonshot_api.dpapi",
        "env": "MOONSHOT_API_KEY",
        "proxy": "",
        "file_env": "GBT_MOONSHOT_SECRET_FILE",
    },
    "kimi": {
        "entropy": b"GBTxiaotudouV8:kimi:v1",
        "file": "kimi_api.dpapi",
        "env": "KIMI_API_KEY",
        "proxy": "",
        "file_env": "GBT_KIMI_SECRET_FILE",
    },
    "openai": {
        "entropy": b"GBTxiaotudouV8:openai:v1",
        "file": "openai_api.dpapi",
        "env": "OPENAI_API_KEY",
        "proxy": "",
        "file_env": "GBT_OPENAI_SECRET_FILE",
    },
    "tripo": {
        "entropy": b"GBTxiaotudouV8:tripo:v1",
        "file": "tripo_api.dpapi",
        "env": "TRIPO_API_KEY",
        "proxy": "",
        "file_env": "GBT_TRIPO_SECRET_FILE",
        # 实测形状：`tcli` 开头、不带 sk-/ak- ⇒ 走"单行长串"那条
        "pattern": r"^[A-Za-z0-9_\-]{20,}$",
    },
    # 2026-10-21 新增：Hugging Face（免费算力那条腿的钥位）。
    # 为什么放进保险箱而不是只读环境变量：`hf_voice` 现在只认 env（HF_TOKEN_1/2/3），
    # 而"免费优先"的算力路由需要一把**可被多个能力位取到**的钥 ⇒ 统一收进 DPAPI，
    # 由调用方 `load_key("hf")` 现取（只报已配/未配，永不回显）。
    "hf": {
        "entropy": b"GBTxiaotudouV8:hf:v1",
        "file": "hf_api.dpapi",
        "env": "HF_TOKEN",
        "proxy": "",
        "file_env": "GBT_HF_SECRET_FILE",
        # 形状：hf_ + 34~40 位字母数字（实测 hf_ueyx…Zvuv）
        "pattern": r"^hf_[A-Za-z0-9]{20,}$",
    },
    "freellmapi": {
        "entropy": b"GBTxiaotudouV8:freellmapi:v1",
        "file": "freellmapi_api.dpapi",
        "env": "FREELLMAPI_API_KEY",
        "proxy": "",
        "file_env": "GBT_FREELLMAPI_SECRET_FILE",
        # 实测形状：`free` 开头、不带 sk-/ak- ⇒ 同上
        "pattern": r"^[A-Za-z0-9_\-]{20,}$",
    },
    # ── 2026-10-03 四触手独立 Agnes 密钥 profile（每根触手独立配额，互不干扰）────────
    "neural_agnes": {
        "entropy": b"GBTxiaotudouV8:neural_agnes:v1",
        "file": "neural_agnes_api.dpapi",
        "env": "NEURAL_AGNES_API_KEY",
        "proxy": "",
        "file_env": "GBT_NEURAL_AGNES_SECRET_FILE",
        # Agnes key 无固定前缀，允许任意非空字符（>=8位）
        "pattern": r"^.{8,}$",
    },
    "vision_agnes": {
        "entropy": b"GBTxiaotudouV8:vision_agnes:v1",
        "file": "vision_agnes_api.dpapi",
        "env": "VISION_AGNES_API_KEY",
        "proxy": "",
        "file_env": "GBT_VISION_AGNES_SECRET_FILE",
        "pattern": r"^.{8,}$",
    },
    "devour_agnes": {
        "entropy": b"GBTxiaotudouV8:devour_agnes:v1",
        "file": "devour_agnes_api.dpapi",
        "env": "DEVOUR_AGNES_API_KEY",
        "proxy": "",
        "file_env": "GBT_DEVOUR_AGNES_SECRET_FILE",
        "pattern": r"^.{8,}$",
    },
    "omni_agnes": {
        "entropy": b"GBTxiaotudouV8:omni_agnes:v1",
        "file": "omni_agnes_api.dpapi",
        "env": "OMNI_AGNES_API_KEY",
        "proxy": "",
        "file_env": "GBT_OMNI_AGNES_SECRET_FILE",
        "pattern": r"^.{8,}$",
    },
}
_DEFAULT_PROFILE = "deepseek"
# 默认形状：sk-/ak- 开头的单行长串（deepseek / agnes 用它，**行为与加多 profile 之前一字不差**）
_KEY_PATTERN = re.compile(r"^(?:sk|ak)[-_][A-Za-z0-9_\-]{16,}$")


class DeepseekKeyError(RuntimeError):
    """密钥处理错误。"""


def _profile(name: str | None = None) -> tuple[str, dict]:
    """取 profile 规格；名字不认识 -> **显式报错**（不静默退回默认，免得写错库还不知道）。"""
    key = str(name or _DEFAULT_PROFILE).strip().lower() or _DEFAULT_PROFILE
    spec = _PROFILES.get(key)
    if not spec:
        raise DeepseekKeyError("未知保险箱 profile：%s（可选：%s）"
                               % (key, " / ".join(sorted(_PROFILES))))
    return key, spec


def _secret_file(profile: str | None = None) -> Path:
    _name, spec = _profile(profile)
    raw = os.environ.get(spec["file_env"], "").strip()
    return (Path(raw).expanduser().resolve() if raw
            else Path(STORE_DIR) / "secrets" / spec["file"])


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _blob(raw: bytes):
    buf = ctypes.create_string_buffer(raw, len(raw))
    return (_DataBlob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf)


def _protect_dpapi(data: bytes, profile: str | None = None) -> bytes:
    if os.name != "nt":
        raise DeepseekKeyError("当前系统不支持 Windows DPAPI")
    _name, spec = _profile(profile)
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(_DataBlob), ctypes.c_wchar_p,
            ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.POINTER(_DataBlob),
        ]
        crypt32.CryptProtectData.restype = ctypes.c_int
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        input_blob, input_buf = _blob(data)
        entropy_blob, entropy_buf = _blob(spec["entropy"])
        output = _DataBlob()
        ok = crypt32.CryptProtectData(
            ctypes.byref(input_blob),
            "GBT小土豆V8 %s credential" % _name,
            ctypes.byref(entropy_blob),
            None,
            None,
            0x1,
            ctypes.byref(output),
        )
        _keepalive = (input_buf, entropy_buf)
        if not ok:
            raise DeepseekKeyError("DPAPI 加密失败")
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)
    except DeepseekKeyError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DeepseekKeyError(f"DPAPI 不可用：{str(exc)[:160]}") from exc


def _unprotect_dpapi(data: bytes, profile: str | None = None) -> bytes:
    if os.name != "nt":
        raise DeepseekKeyError("当前系统不支持 Windows DPAPI")
    _name, spec = _profile(profile)
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(_DataBlob), ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.POINTER(_DataBlob),
        ]
        crypt32.CryptUnprotectData.restype = ctypes.c_int
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        input_blob, input_buf = _blob(data)
        entropy_blob, entropy_buf = _blob(spec["entropy"])
        output = _DataBlob()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob),
            None,
            ctypes.byref(entropy_blob),
            None,
            None,
            0x1,
            ctypes.byref(output),
        )
        _keepalive = (input_buf, entropy_buf)
        if not ok:
            raise DeepseekKeyError("DPAPI 解密失败")
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)
    except DeepseekKeyError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DeepseekKeyError(f"DPAPI 不可用：{str(exc)[:160]}") from exc


def mask(value: str) -> str:
    text = str(value or "")
    return f"{text[:5]}****" if len(text) >= 5 else ""


def _validate(key: str, profile: str | None = None) -> str:
    text = str(key or "").strip().strip('"').strip("'")
    name, spec = _profile(profile)
    pattern = spec.get("pattern") or _KEY_PATTERN.pattern
    if not re.match(pattern, text):
        raise DeepseekKeyError("密钥格式不符（profile=%s 的形状是 %s）" % (name, pattern))
    return text


def store_key(key: str, profile: str | None = None) -> dict:
    """把密钥加密落到 DPAPI 文件，返回报告；任何路径都不返回明文。"""
    name, spec = _profile(profile)
    try:
        safe = _validate(key, name)
    except DeepseekKeyError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        target = _secret_file(name)
        atomic_write_bytes(target, _protect_dpapi(safe.encode("utf-8"), name), mode=0o600)
        return {
            "ok": True,
            "configured": True,
            "credential": "dpapi",
            "profile": name,
            "entropy": spec["entropy"].decode("ascii"),
            "masked": mask(safe),
            "path": str(target),
            "bytes": target.stat().st_size,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}


def load_key(profile: str | None = None) -> tuple[str, str]:
    """返回 (key, source)。source ∈ env:… / dpapi / missing / unreadable。"""
    name, spec = _profile(profile)
    env = os.environ.get(spec["env"], "").strip()
    if not env and spec["proxy"]:
        env = os.environ.get(spec["proxy"], "").strip()
    if env:
        return env, "env:" + (spec["env"] if os.environ.get(spec["env"]) else spec["proxy"])
    target = _secret_file(name)
    if not target.is_file():
        return "", "missing"
    try:
        key = _unprotect_dpapi(target.read_bytes(), name).decode("utf-8").strip()
    except Exception:  # noqa: BLE001
        return "", "unreadable"
    if not key:
        return "", "missing"
    return key, "dpapi"


def load_from_vault(profile: str | None = None) -> tuple[str, str]:
    """只从 DPAPI 保险箱取密钥，忽略环境变量。

    给"必须以保险箱为准"的调用方用（例如看门狗拉起中继时）：
    环境里来路不明的一份 key 不应该悄悄顶掉保险箱里的那一份。

    🔴 2026-10-08 修的真缺陷（蓝图 §9.1 · Q2 登记在案）：**「解不开」不许伪装成「没有」**。
      原来这一句是 `except Exception: return "", "unreadable"` —— DPAPI 解不开时调用方
      收到一个空 key，往下走就变成「上游 401」，人去追 401 追到天亮，真正的原因
      （保险箱读不出来）一个字都没露。这就是《静默失效律》的教科书形态。
      ⇒ 现在分两种：**文件不在**（真的没有）照旧 `("", "missing")`——那是合法状态不是故障；
        **有文件但解不开**（DPAPI 坏了 / 换了机器 / 换了用户）**抛 DeepseekKeyError**，
        报错里带 profile 与文件路径。让故障当场像故障。
      调用方口径：要降级的必须**显式** catch（本仓四处调用方本来就都包在 try 里，
      所以改这行不会让任何链崩），但至少记一行原因，不许静默吞。
    """
    name, _spec = _profile(profile)
    target = _secret_file(name)
    if not target.is_file():
        return "", "missing"
    try:
        key = _unprotect_dpapi(target.read_bytes(), name).decode("utf-8").strip()
    except Exception as exc:  # noqa: BLE001
        raise DeepseekKeyError(
            "DPAPI 保险箱**解不开**（profile=%s · 文件=%s）：%s —— 这不是「没有密钥」，"
            "是「有密钥但读不出来」（DPAPI 换了用户/机器，或文件被改过）。"
            "别当上游 401 去追：先修保险箱，或重新写入这份密钥。" % (name, target, str(exc)[:160])
        ) from exc
    return (key, "dpapi") if key else ("", "missing")


def export_env(profile: str | None = None, *, override: bool = False) -> str:
    """把密钥从保险箱解出来注入当前进程环境。返回 source（不打印密钥）。

    override=False 时不覆盖已有的环境变量（谁先注入谁优先，避免把外部明确
    指定的值悄悄换掉 —— 静默改写也是静默失效的一种）。
    """
    name, spec = _profile(profile)
    if not override and os.environ.get(spec["env"], "").strip():
        return "env:" + spec["env"]
    key, source = load_key(name)
    if not key:
        return source
    os.environ[spec["env"]] = key
    # 中继代理读的是 GBT_DEEPSEEK_KEY（优先级高于它的 .deepseek_key 文件）
    if spec["proxy"] and (override or not os.environ.get(spec["proxy"], "").strip()):
        os.environ[spec["proxy"]] = key
    return source


def status(profile: str | None = None) -> dict:
    name, _spec = _profile(profile)
    key, source = load_key(name)
    target = _secret_file(name)
    return {
        "ok": bool(key),
        "configured": bool(key),
        "profile": name,
        "source": source,
        "masked": mask(key),
        "vault_exists": target.is_file(),
        "vault_path": str(target),
        "vault_bytes": target.stat().st_size if target.is_file() else 0,
    }


def _read_stdin_secret() -> str:
    raw = sys.stdin.buffer.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    # 密钥本身不含空白；顺带吃掉 PowerShell 管道带的 BOM/CRLF/引号
    return "".join(text.split()).strip('"').strip("'")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM 上游密钥 DPAPI 保险箱（多 profile）")
    sub = parser.add_subparsers(dest="action")
    setter = sub.add_parser("set", help="从 stdin 读密钥并加密保存")
    setter.add_argument("--profile", default=_DEFAULT_PROFILE,
                        choices=sorted(_PROFILES), help="保险箱名（默认 deepseek）")
    checker = sub.add_parser("status", help="输出掩码体检结果")
    checker.add_argument("--profile", default=_DEFAULT_PROFILE,
                         choices=sorted(_PROFILES), help="保险箱名（默认 deepseek）")
    inject = sub.add_parser("inject", help="解密注入环境变量后启动子进程")
    inject.add_argument("--profile", default=_DEFAULT_PROFILE,
                        choices=sorted(_PROFILES), help="保险箱名（默认 deepseek）")
    inject.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    action = args.action or "status"
    profile = getattr(args, "profile", _DEFAULT_PROFILE)

    if action == "set":
        report = store_key(_read_stdin_secret(), profile)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ok") else 1

    if action == "status":
        print(json.dumps(status(profile), ensure_ascii=False, indent=2))
        return 0 if status(profile).get("ok") else 1

    if action == "inject":
        command = [c for c in args.command if c != "--"]
        if not command:
            print("inject 需要子进程命令，例如：inject -- codex exec \"echo OK\"",
                  file=sys.stderr)
            return 2
        source = export_env(profile)
        if source in ("missing", "unreadable") or source.startswith("missing"):
            print("密钥不可用（source=%s），拒绝在没有密钥的情况下启动子进程" % source,
                  file=sys.stderr)
            return 3
        try:
            return subprocess.call(command)
        except FileNotFoundError:
            print("找不到命令：%s" % command[0], file=sys.stderr)
            return 4

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
