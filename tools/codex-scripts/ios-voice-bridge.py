# -*- coding: utf-8 -*-
"""ios-voice-bridge -- 苹果语音操控桥接（Siri/快捷指令 + 服务端）。

落三件：① 可导入的快捷指令菜单说明（JSON，手机上照着建一次即可）
        ② 服务端契约 POST /v1/voice {text} -> {reply, action, url}（落 state/voice-bridge-contract.json）
        ③ 语音→能力位映射（命令表；动手类一律 fail-closed）
--check 校验三件齐 + 命令表非空 + 动手类全部需钥匙
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "voice-bridge"
CMDS = [
    {"说": "打开能力面板", "走": "page", "url": "state/mobile-pack/index.html", "动手": False},
    {"说": "看看台账 / 能力现读", "走": "cap", "位": "capability-audit", "动手": False},
    {"说": "定海神针现在怎么样", "走": "cap", "位": "context-anchor check", "动手": False},
    {"说": "记一笔今天的事", "走": "cap", "位": "paper_loop write", "动手": False},
    {"说": "看一眼页面直达怎么样", "走": "cap", "位": "page-reach --check", "动手": False},
    {"说": "跳一炉训练 / 点火", "走": "cap", "位": "pod_link run", "动手": True, "需": "process_execute"},
    {"说": "发布 / 部署到生产", "走": "cap", "位": "one_key_deploy", "动手": True, "需": "deploy_publish"},
]


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "shortcuts-recipe.json").write_text(json.dumps({
        "name": "小土豆V8 语音桥",
        "trigger": ["呼叫 Siri：小土豆", "或快捷指令 App 点运行", "或加到主屏/锁屏小组件"],
        "steps": [
            "1. 「文本」→ 「听写文本」（Dictate Text，语言设置中文）",
            "2. 「获取 URL 内容」：POST 到 <我们的服务端>/v1/voice，请求体 {\"text\": <听写结果>}",
            "3. 「获取字典值\"回复\"」→ 「朗读文本」（Speak Text）",
            "4. 若返回里有 \"url\"：「打开 URL」（直达那一页）",
            "5. 若返回里 action=\"need_key\"：「显示提醒」——请在电脑端发钥匙",
        ],
        "note": "手机端只听与说；脑在框架；**动手类一律回 need_key**（手机不发授权）"}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "voice-bridge-contract.json").write_text(json.dumps({
        "endpoint": "POST /v1/voice",
        "request": {"text": "语音转文本结果"},
        "response": {"reply": "回答人话", "action": "名词 | need_key", "url": "可选，直达页面",
                     "need_scope": "当 action=need_key 时告知缺哪把钥匙"},
        "security": {"owner_only_actions": ["pod_link run", "one_key_deploy", "pipeline_submit"],
                     "rule": "动手类一律 fail-closed；钥匙只能在主人终端发",
                     "no_credentials_on_phone": True},
        "deploy": {"建议": "把 /v1/voice 挂到我们已有的云端入口（Cloudflare Worker），手机只带访问令牌不带秘钥"}}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "commands.json").write_text(json.dumps({"commands": CMDS}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("语音桥已出：" + str(OUT.relative_to(ROOT)) + " · 命令 %d 条（其中动手类 %d 条需钥匙）"
          % (len(CMDS), sum(1 for c in CMDS if c.get("动手"))))
    return 0


def check():
    need = ["shortcuts-recipe.json", "voice-bridge-contract.json", "commands.json"]
    miss = [n for n in need if not (OUT / n).is_file()]
    cmds = json.loads((OUT / "commands.json").read_text(encoding="utf-8"))["commands"] if (OUT / "commands.json").is_file() else []
    risky = [c for c in cmds if c.get("动手") and not c.get("需")]
    print("语音桥校验：件 %d/%d · 命令 %d · 动手类无钥匙 %d" % (len(need) - len(miss), len(need), len(cmds), len(risky)))
    for m in miss:
        print("   RED 缺 " + m)
    for r in risky:
        print("   RED 动手类未标钥匙: " + r["说"])
    return 0 if (not miss and cmds and not risky) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.build:
        build()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
