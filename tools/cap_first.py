#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cap_first —— 动手之前先查能力面（血训工具）

## 为什么有这个

2026-10-28 主人的话：「为什么你每次都在走传统路线，我们有一万种方式可以使用
我们自己的原生能力进行万物皆可插、万物皆可控来实现，你却一直在使用传统方式
浪费时间浪费金钱？」

那天我为了"让 3D 数字人动起来"，手搓了几小时 WebGL 降质、抗锯齿、单帧模式 ——
而能力面里本来就摆着 `digital_human` / `dh_pose` / `screen_sniff` / `vision_print`。
**先查一遍只要几秒。**

本工具就干这一件事：一句中文需求 → 能力面里最相关的几位 + 它们的**真实可用性**
（不是"有没有登记"，是"空 payload 调下去到底行不行"）。

## 用法

    python3 tools/cap_first.py "让数字人的身体动起来"
    python3 tools/cap_first.py --top 12 "把画面投到墙上"

**口径**：本工具只**读**能力面，绝不替你决定用哪个。
它给出的 `probe` 是空 payload 试调的结果，`denied` 表示要授权、`failed` 表示实现有缺口。
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 同义扩展：主人的说法和代码里的用词往往对不上
SYN = {
    "动": ["pose", "action", "move", "骨架", "动作", "anim"],
    "身体": ["body", "dh_", "数字人", "骨架"],
    "数字人": ["dh_", "digital_human", "数字人", "骨架", "pose"],
    "投": ["project", "投影", "投墙", "cast", "display"],
    "墙": ["投影", "project"],
    "看": ["see", "vision", "screen", "视觉", "截"],
    "屏": ["screen", "截", "capture", "视觉"],
    "说": ["voice", "say", "tts", "发声", "嘴"],
    "听": ["ear", "asr", "speech", "麦克风"],
    "画": ["image", "render", "绘", "出图", "visual"],
    "渲染": ["render", "显示", "visual", "画面"],
    "并发": ["concurrency", "qps", "并发"],
    "上下文": ["context", "ring", "窗口", "溢出"],
    "镜像": ["mirror", "维度", "晋升"],
    "授权": ["auth", "scope", "gate", "门"],
    "记忆": ["memory", "vault", "上下文", "知识"],
}


def expand(q: str) -> list:
    terms = [q]
    low = q.lower()
    for k, vs in SYN.items():
        if k in q:
            terms.extend(vs)
    terms = [t for t in dict.fromkeys(terms) if t]
    return terms


def search(q: str, top: int = 10) -> list:
    from gbt_allinone.caps_registry import all_caps
    terms = expand(q)
    scored = []
    for c in all_caps():
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "")
        desc = str(c.get("desc") or "")
        blob = (name + " " + desc).lower()
        score = 0
        for t in terms:
            tl = t.lower()
            if tl in name.lower():
                score += 3
            elif tl in blob:
                score += 1
        if score:
            scored.append({"name": name, "domain": c.get("domain"),
                           "score": score, "desc": desc[:120]})
    scored.sort(key=lambda x: -x["score"])
    return scored[:top]


def probe(name: str) -> str:
    """空 payload 试一下，如实报状态。"""
    import subprocess
    code = ("import sys, json; sys.path.insert(0, %r)\n"
            "from gbt_allinone.api import run_task\n"
            "try:\n"
            "    r = run_task(%r, {})\n"
            "    g = (r.get('gbt_result') or {}).get('result') or r.get('result') or {}\n"
            "    st = (r.get('gbt_result') or {}).get('status') or r.get('status')\n"
            "    print(json.dumps({'st': st, 'ok': (g or {}).get('ok'),\n"
            "                      'err': str((g or {}).get('error') or (g or {}).get('message') or '')[:90]},\n"
            "                     ensure_ascii=False))\n"
            "except Exception as e:\n"
            "    print(json.dumps({'st': 'exc', 'err': type(e).__name__ + ': ' + str(e)[:90]}))\n"
            % (str(ROOT), name))
    try:
        cp = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, timeout=40, cwd=str(ROOT))
        for ln in (cp.stdout or "").splitlines():
            if ln.startswith("{"):
                d = json.loads(ln)
                st = str(d.get("st") or "?")
                if st == "denied":
                    return "🔒 要授权"
                if d.get("ok") is False:
                    return "🔴 " + (d.get("err") or "失败")[:40]
                return "✅ 可跑"
        return "? 无输出"
    except subprocess.TimeoutExpired:
        return "⏱ 超时"
    except Exception as exc:                                  # noqa: BLE001
        return "? " + type(exc).__name__


def main() -> int:
    ap = argparse.ArgumentParser(description="动手之前先查能力面")
    ap.add_argument("query", nargs="+", help="你要干的那件事，用大白话说")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--no-probe", action="store_true", help="不试调（快，但看不出可不可用）")
    a = ap.parse_args()
    q = " ".join(a.query)

    hits = search(q, a.top)
    if not hits:
        print("  能力面里没找到相关的 —— 如实说没有，不编一条给你")
        return 1

    print("  需求：%s" % q)
    print("  能力面命中 %d 位（先看这里，别再手搓）\n" % len(hits))
    for i, h in enumerate(hits, 1):
        state = "—" if a.no_probe else probe(h["name"])
        print("  %d. %-22s %-12s %s" % (i, h["name"], h["domain"], state))
        print("     %s" % h["desc"])
        print()
    print("  口径：✅ 可跑 / 🔒 要授权 / 🔴 实现有缺口。**这不是替你决定用哪个。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
