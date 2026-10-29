#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GBT 四触手 Agnes 账号自动注册与密钥配置脚本

功能：
  1. 为每根触手（神经/视觉/吞噬/万能）生成一次性邮箱并打开 Agnes 注册页
  2. 引导用户完成注册，获取 API Key
  3. 将每个 key 存入 DPAPI 保险箱，自动注入环境变量

使用方法：
  python tools/codex-scripts/register_tentacle_agnes.py          # 交互式配置全部4个
  python tools/codex-scripts/register_tentacle_agnes.py neural   # 仅配置神经触手
  python tools/codex-scripts/register_tentacle_agnes.py --skip-browser  # 跳过浏览器，手动粘贴key
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 2026-10-04：本脚本大量 print // 等符号。中文 Windows 下 stdout 走管道时默认 GBK
# ⇒ 第一个 emoji print 就 UnicodeEncodeError（脚本崩在"密钥已存好"的确认打印处）。
# 守卫写法与 five-dim.py / quick_scan.py 同族（hasattr 兜底 + 吞异常安全）。
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── 触手映射配置 ────────────────────────────────────────────────────────────────
# purpose → profile_name → display_name
TENTACLE_MAP = {
    "neural": {
        "profile": "neural_agnes",
        "env": "NEURAL_AGNES_API_KEY",
        "display": "神经触手",
        "purpose_example": "neural.consult",
    },
    "vision": {
        "profile": "vision_agnes",
        "env": "VISION_AGNES_API_KEY",
        "display": "视觉触手",
        "purpose_example": "vision.analyze",
    },
    "devour": {
        "profile": "devour_agnes",
        "env": "DEVOUR_AGNES_API_KEY",
        "display": "吞噬触手",
        "purpose_example": "devour.consult",
    },
    "omni": {
        "profile": "omni_agnes",
        "env": "OMNI_AGNES_API_KEY",
        "display": "万能触手",
        "purpose_example": "omni.execute",
    },
}

# 目标注册页和 API 管理页
AGNES_REGISTER_URL = "https://apihub.agnes-ai.com/register"
AGNES_API_KEYS_URL = "https://apihub.agnes-ai.com/dashboard/api-keys"
AGNES_DOCS_URL = "https://docs.agnes-ai.com"

# 一次性邮箱服务（可选，用户可自行替换）
TEMP_EMAIL_SERVICES = [
    ("temp-mail.org", "https://temp-mail.org"),
    ("guerrillamail.com", "https://www.guerrillamail.com"),
    ("mail.tm", "https://mail.tm"),
]


def open_browser(url: str) -> None:
    """跨平台打开浏览器。"""
    system = platform.system()
    if system == "Windows":
        os.startfile(url)
    elif system == "Darwin":  # macOS
        subprocess.run(["open", url], check=False)
    else:  # Linux
        subprocess.run(["xdg-open", url], check=False)


def print_welcome() -> None:
    """打印欢迎信息和说明。"""
    print("=" * 60)
    print("  GBT 四触手 Agnes 账号配置助手")
    print("=" * 60)
    print()
    print("本脚本将为以下四根触手分别配置独立的 Agnes.ai API Key：")
    print()
    for key, info in TENTACLE_MAP.items():
        print(f"  [{key.upper():>8}] {info['display']:4s}  "
              f"purpose='{info['purpose_example']}'")
    print()
    print("操作步骤：")
    print("  1. 打开 Agnes 注册页，用一次性邮箱注册账号")
    print("  2. 在 Dashboard 创建 API Key")
    print("  3. 复制 Key 粘贴到本脚本（自动加密存储）")
    print("  4. 重复以上步骤，为每根触手配置独立账号")
    print()
    print(f"Agnes 注册页: {AGNES_REGISTER_URL}")
    print(f"API Key 管理: {AGNES_API_KEYS_URL}")
    print()


def get_temp_email_hint() -> None:
    """提示一次性邮箱服务。"""
    print("推荐一次性邮箱服务（任选其一）：")
    for name, url in TEMP_EMAIL_SERVICES:
        print(f"  • {name} → {url}")
    print()


def register_single_tentacle(tentacle_key: str) -> bool:
    """注册单根触手的 Agnes 账号并存储 Key。

    返回 True 表示成功，False 表示用户跳过。
    """
    info = TENTACLE_MAP[tentacle_key]
    profile = info["profile"]
    display = info["display"]
    env = info["env"]

    print(f"\n{'=' * 60}")
    print(f"  配置 {display}（{tentacle_key.upper()}）")
    print(f"{'=' * 60}")
    print(f"  用途：purpose='{info['purpose_example']}'")
    print(f"  环境变量：{env}")
    print(f"  存储文件：{profile}_api.dpapi")
    print()

    # 检查是否已配置
    from gbt_allinone.deepseek_key import _secret_file
    secret_path = _secret_file(profile)
    if secret_path.exists():
        print(f"  ⚠️  已存在密钥文件：{secret_path.name}")
        resp = input("  是否重新配置？(y/N): ").strip().lower()
        if resp != "y":
            print(f"  跳过 {display}")
            return True

    # 打开注册页
    print(f"  正在打开注册页: {AGNES_REGISTER_URL}")
    try:
        open_browser(AGNES_REGISTER_URL)
        print("  请在浏览器中完成注册...")
    except Exception as e:
        print(f"  无法自动打开浏览器: {e}")
        print(f"  请手动访问: {AGNES_REGISTER_URL}")

    # 提示临时邮箱
    get_temp_email_hint()

    # 等待用户完成注册
    print(f"  注册完成后，请访问: {AGNES_API_KEYS_URL}")
    print("  在 Dashboard 中创建新的 API Key，并复制完整 Key")
    print()

    # 输入 API Key
    api_key = input(f"  请输入 {display} 的 Agnes API Key: ").strip()

    if not api_key:
        print(f"  ⚠️  Key 为空，跳过 {display}")
        return False

    # 验证 Key 格式（基本检查）
    if len(api_key) < 16:
        print(f"  ⚠️  Key 长度过短（{len(api_key)} 字符），请确认是否正确")
        resp = input("  仍要继续？(y/N): ").strip().lower()
        if resp != "y":
            return False

    # 存储密钥
    try:
        from gbt_allinone.deepseek_key import store_key
        result = store_key(api_key, profile=profile)
        print(f"  ✅ {display} 密钥已加密存储 → {result.get('path', result.get('file', 'unknown'))}")
        print(f"     掩码: {result.get('masked', 'N/A')}")
    except Exception as e:
        print(f"  ❌ 存储失败: {e}")
        return False

    # 提示注入环境变量（当前会话）
    os.environ[env] = api_key
    print(f"  📌 当前会话已注入环境变量: {env}={api_key[:8]}****")
    print()
    return True


def register_all_tentacles(skip_browser: bool = False) -> None:
    """依次配置所有四根触手。"""
    print_welcome()

    if not skip_browser:
        print("将自动打开浏览器引导注册流程。")
        print("按 Enter 继续...")
        input()

    success_count = 0
    for tentacle_key in TENTACLE_MAP:
        if register_single_tentacle(tentacle_key):
            success_count += 1

    print(f"\n{'=' * 60}")
    print(f"  配置完成：{success_count}/4 根触手已配置")
    print(f"{'=' * 60}")

    # 显示当前状态
    show_status()


def show_status() -> None:
    """显示四根触手的配置状态。"""
    from gbt_allinone.deepseek_key import _secret_file, _unprotect_dpapi, mask as dpapi_mask

    print("\n当前配置状态：")
    print(f"  {'触手':<10} {'状态':<12} {'掩码Key':<20} {'环境变量'}")
    print(f"  {'-'*10} {'-'*12} {'-'*20} {'-'*25}")

    for key, info in TENTACLE_MAP.items():
        profile = info["profile"]
        secret_path = _secret_file(profile)
        exists = secret_path.exists()

        if exists:
            try:
                # 2026-10-04 修：原实现漏传 profile ⇒ 用默认熵解密必失败 ⇒ 恒显示"已加密"。
                raw_key = _unprotect_dpapi(secret_path.read_bytes(), profile=profile).decode().strip()
                key_display = dpapi_mask(raw_key)
            except Exception:
                key_display = "已加密"
        else:
            key_display = "未设置"

        status_str = "✅ 已配置" if exists else "⬜ 未配置"
        print(f"  {info['display']:<10} {status_str:<12} {key_display:<20} {info['env']}")


def verify_routing() -> None:
    """验证路由逻辑是否正确加载。"""
    try:
        from gbt_allinone.llm import cloud_llm
        routing_map = cloud_llm._PURPOSE_ROUTING_MAP
        print("\n路由映射验证：")
        for kw, prof in routing_map.items():
            from gbt_allinone.deepseek_key import _secret_file
            exists = _secret_file(prof).exists()
            icon = "✅" if exists else "⬜"
            print(f"  {icon} purpose 含 '{kw}' → profile '{prof}' ({'已配置' if exists else '未配置'})")
    except Exception as e:
        print(f"  ❌ 路由验证失败: {e}")


def cmd_set_key(args: argparse.Namespace) -> None:
    """直接设置单个触手的 Key（非交互模式，用于自动化）。"""
    tentacle = args.tentacle
    api_key = args.api_key

    if tentacle not in TENTACLE_MAP:
        print(f"错误：未知触手 '{tentacle}'，可选：{', '.join(TENTACLE_MAP.keys())}")
        sys.exit(1)

    info = TENTACLE_MAP[tentacle]
    profile = info["profile"]
    env = info["env"]

    from gbt_allinone.deepseek_key import store_key
    result = store_key(api_key, profile=profile)
    if not result.get("ok"):
        print(f"❌ 存储失败: {result.get('error')}")
        sys.exit(1)
    print(f"✅ {info['display']} Key 已存储 → {result.get('path', 'unknown')}")
    print(f"   掩码: {result.get('masked')}")
    print(f"   环境变量: {env}")

    # 同时注入当前进程
    os.environ[env] = api_key
    print(f"   当前会话已注入: {env}={api_key[:8]}****")

    verify_routing()


def main():
    parser = argparse.ArgumentParser(
        description="GBT 四触手 Agnes 账号注册与密钥配置",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 交互式配置全部四根触手
  python tools/codex-scripts/register_tentacle_agnes.py

  # 仅配置神经触手
  python tools/codex-scripts/register_tentacle_agnes.py neural

  # 非交互式：直接设置 Key（适用于自动化）
  python tools/codex-scripts/register_tentacle_agnes.py set-key neural "sk-xxx..."

  # 查看配置状态
  python tools/codex-scripts/register_tentacle_agnes.py status

  # 跳过浏览器引导
  python tools/codex-scripts/register_tentacle_agnes.py --skip-browser
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 默认交互模式
    subparsers.add_parser("all", help="交互式配置全部四根触手")

    for key in TENTACLE_MAP:
        subparsers.add_parser(key, help=f"仅配置{TENTACLE_MAP[key]['display']}")

    # status 子命令
    subparsers.add_parser("status", help="显示配置状态")

    # set-key 子命令（非交互）
    setkey_parser = subparsers.add_parser("set-key", help="直接设置单个触手的 API Key")
    setkey_parser.add_argument("tentacle", choices=list(TENTACLE_MAP.keys()),
                               help="触手名称")
    setkey_parser.add_argument("api_key", help="Agnes API Key")

    parser.add_argument(
        "--skip-browser",
        action="store_true",
        help="跳过浏览器自动打开，手动访问注册页",
    )

    args = parser.parse_args()

    if args.command is None:
        # 无子命令时，默认执行 all
        args.command = "all"

    if args.command == "status":
        show_status()
        verify_routing()
        return

    if args.command == "set-key":
        cmd_set_key(args)
        return

    # 交互注册模式
    if args.command == "all":
        register_all_tentacles(skip_browser=args.skip_browser)
    else:
        register_single_tentacle(args.command)
        show_status()


if __name__ == "__main__":
    main()
