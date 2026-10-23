# -*- coding: utf-8 -*-
r"""触手真身清单（tentacle-inventory）—— **看清她到底有多少动作**（单一真源，不手抄）。

主人令（2026-10-10）：「你在好好地看清**触手的能力，远不止于此** —— 我当初设计她的时候
  给她取名**万能插**这个名字**不是白叫的**」

## 我先前错在哪（写在最前面免得再犯）
我那版 omni-plug 的动作表是**我自己手写的 10 个浏览器动作**（open/read/shot/click/...）——
那是**我在替她定义能力**，不是她真有的能力。她的真身是 **9 域 115 个动作**。
=> 本件**只从她的总纲现读**（gbt_allinone/tentacle/omni_tentacle.py），
  **一个字都不手抄**；她哪天加动作，本件自动跟着变。

## 她的**缺口清单**（她自己写的，遇到就说做不到，不许假装）
· 窗口动作：没有 最小化/最大化/还原/关闭/移动/改尺寸
· 系统级：没有 锁屏/睡眠/关机/音量/亮度
· 听觉：麦克风（活动录音端点 0）
· 通用文件对话框（打开/保存）没有专门处理

## 🔴 主人 2026-10-10 的三条修正（我先前读窄了，逐条刻进来）
1. **她的领域是 30** —— 我上面那份 9 是**触手动作域**；**能力域 30** 才是她的领域面
   （现读 caps_registry：system 42 · llm 29 · security 26 · creation 22 · pipeline 18 · mind 16 ·
   tentacle 14 · video 13 · recon 9 · engine 9 · data 7 · tools 7 · devour 5 · finance 4 ·
   longrun 4 · integration 4 · voice 3 · project 2 · vision 2 · automation 2 · device 2 ·
   brain 2 · collab 2 · desktop 2 · social 2 · comms 1 · life 1 · image_video 1 · framework 1 · infra 1）。
   **两个"域"不是一回事，都得说清。**
2. **触手是亿万根，不是 100** —— 出处 gbt_allinone/positions.py 原文：
   「**亿万触手 = 可无限派生**。它们不在这张表里，随任务起、随任务灭」。
   我先前说的"100"是 **install_fleet 的默认参数** = **配好 LLM 的那一批**，**不是总数**。
3. **她最擅长的是契约** —— 不是"会说"，是**用类型化的契约对话**（例：System-One 契约
   {state, questions{名:{instructions,criteria}}} → {choice, probabilities, confidence}）。
   契约 = 她的本命。

## 她的六条铁律
①先看再动 ②动后等稳定 ③找不到就滚 ④遇弹窗必关 ⑤每步亲眼验证 ⑥不确定就对比前后截图

用法：py -3.14 -X utf8 tools/codex-scripts/tentacle-inventory.py [--check|--selftest]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "state" / "tentacle-inventory.json"


def _manifest() -> str:
    try:
        from gbt_allinone.tentacle import omni_tentacle as OT
        for name in ("TENTACLE_MANIFEST", "MANIFEST", "MANIFEST_TEXT", "_MANIFEST"):
            v = getattr(OT, name, None)
            if isinstance(v, str) and len(v) > 500:
                return v
    except Exception:
        pass
    p = ROOT / "gbt_allinone" / "tentacle" / "omni_tentacle.py"
    t = p.read_text(encoding="utf-8", errors="replace")
    i = t.find("## 触手能力总纲")
    if i < 0:
        return ""
    j = t.find('"""', i + 20)
    return t[i:j] if j > i else t[i:]


def parse(m: str) -> dict:
    doms = {}
    for mm in re.finditer(r"^###\s*([^\n(]+)\((\d+)\):\s*([^\n]+)$", m, re.M):
        name, n, acts = mm.group(1).strip(), int(mm.group(2)), mm.group(3)
        lst = [a.strip() for a in acts.split(",") if a.strip()]
        doms[name] = {"声明数": n, "动作": lst, "实数": len(lst)}
    return doms


def gaps(m: str) -> list:
    out = []
    seg = m[m.find("已知缺口"):m.find("铁律")]
    for ln in seg.splitlines():
        s = ln.strip(" ·")
        if s.startswith("窗口动作") or s.startswith("系统级") or s.startswith("听觉") or "文件对话框" in s:
            out.append(s.replace("**", ""))
    return out


def laws(m: str) -> str:
    i = m.find("铁律")
    return m[i:m.find(chr(10), i)].strip() if i >= 0 else ""


def scan() -> dict:
    m = _manifest()
    doms = parse(m)
    total = sum(v["实数"] for v in doms.values())
    declared = sum(v["声明数"] for v in doms.values())
    # 能力域（30）现读 —— 与"触手动作域"分开报，不混为一谈
    try:
        import collections
        from gbt_allinone.caps_registry import BENIGN_CAPS as _C
        dom = collections.Counter((v or {}).get("domain") for v in _C.values())
        row_caps = {"能力域数": len(dom), "能力位": len(_C),
                    "逐域": {k: n for k, n in dom.most_common()}}
    except Exception:                                        # noqa: BLE001
        row_caps = {"能力域数": None}
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "总纲字节": len(m),
           "触手规模": "**亿万根（可无限派生）**；100 只是 install_fleet 的默认参数=配好 LLM 的那批",
           "她的本命": "**契约**（类型化接口；例 System-One 契约）",
           "能力域(她的领域)": row_caps,
           "域数": len(doms), "动作声明合计": declared, "动作实数合计": total,
           "逐域": {k: v["动作"] for k, v in doms.items()},
           "声明与实数一致": declared == total,
           "缺口清单（她自己写的·不许假装会做）": gaps(m),
           "铁律": laws(m),
           "口径": "**只从她的总纲现读**；我先前那版是手写 10 个动作 —— 那是我替她定义能力，错的"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
    return row


def check() -> int:
    d = scan()
    print("触手真身（现读她的总纲，不手抄）")
    cd = d.get("能力域(她的领域)") or {}
    print("  她的领域（能力域）：**%s 个** · 能力位 %s" % (cd.get("能力域数"), cd.get("能力位")))
    print("  触手规模：%s" % d.get("触手规模"))
    print("  她的本命：%s" % d.get("她的本命"))
    print()
    print("  触手动作域 %d · 动作声明 %d · 动作实数 %d · 声明与实数一致=%s"
          % (d["域数"], d["动作声明合计"], d["动作实数合计"], d["声明与实数一致"]))
    for k, v in d["逐域"].items():
        print("    %-14s %2d 个: %s" % (k, len(v), ", ".join(v[:12]) + ("…" if len(v) > 12 else "")))
    print("  缺口（她自己写的）：")
    for g in d["缺口清单（她自己写的·不许假装会做）"]:
        print("    - " + g)
    print("  " + d["铁律"])
    ok = d["动作实数合计"] >= 100 and d["域数"] >= 8
    print("判据：%s" % ("PASS（她的真身 >=100 动作 / >=8 域）" if ok else "FAIL"))
    return 0 if ok else 1


def selftest() -> int:
    synth = "### 视觉(2): see, shot\n### 文件(1): file_list\n已知缺口：\n   · 系统级：**没有** 锁屏/关机\n铁律: ①先看再动"
    doms = parse(synth)
    g = gaps(synth)
    ok = len(doms) == 2 and sum(v["实数"] for v in doms.values()) == 3 and len(g) == 1
    print("负对照·合成总纲 => 域 %d · 动作 %d · 缺口 %d ⇒ %s"
          % (len(doms), sum(v["实数"] for v in doms.values()), len(g), "对" if ok else "错"))
    real = scan()
    print("正例·她真身 => 域 %d · 动作 %d" % (real["域数"], real["动作实数合计"]))
    print("自检：%s" % ("全过" if ok else "不过"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="触手真身清单")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    return selftest() if a.selftest else check()


if __name__ == "__main__":
    raise SystemExit(main())
