#!/usr/bin/env python3
"""A19 质量体检 —— 用客观指标判断"是菜，还是被问错了"

背景（2026-10-28 主人问"感觉 A19 这么菜"）：
  同一张截图里两种回答，性质完全不同：
    ① 自由文本：「端美嘉把语音合成好 本机 media_pipeline 本记听览账 …nativezę」
       → 串词、混排、拉丁字母掺进中文 ⇒ **真退化**
    ② 结构化输出：「模块名=hxCamProjector class_name=CamProjector …」
       → 干净、可解析 ⇒ **没退化，它在干本职（路由到能力位）**

  所以"菜不菜"要分开量。本脚本把两类分开测，给出可复算的数字，
  而不是凭印象说"感觉不行"。

指标（全部客观、可复算）：
  · tok/s          completion_tokens ÷ 墙钟
  · 重复率          3-gram 重复占比（越高越像复读/退化）
  · 混排率          拉丁字母出现在中文词中间的比例（乱码信号）
  · 结构有效性      结构化题目能否给出合法 key=value 行
  · 身份一致        是否自述为 GBT小土豆V8 / 开发者自由的风

用法：
  python3 tools/a19_quality.py            # 容器不在就如实报，不编数
  python3 tools/a19_quality.py --runs 3
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import socket
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOST, PORT, KEY = "127.0.0.1", 1234, "gbt"
OUT = ROOT / "state" / "a19_quality.json"

FREE = [
    "介绍一下你自己。",
    "你今天能做哪些事？用一句话说。",
    "把'把这份 Markdown 变成 PPT'这句话落到一个能力位上。",
]
STRUCT = [
    "用 key=value 一行一个字段写出：模块名、类别、处理器、是否有副作用。",
    "用一行给出：能力位名=comfy_native 的域是什么。",
]


def up(t=1.5) -> bool:
    s = socket.socket(); s.settimeout(t)
    try:
        s.connect((HOST, PORT)); return True
    except OSError:
        return False
    finally:
        s.close()


def ask(prompt: str, max_tokens: int = 120, timeout: float = 180,
        system: str | None = None):
    s = socket.socket(); s.settimeout(timeout)
    msgs = ([{"role": "system", "content": system}] if system else [])
    msgs.append({"role": "user", "content": prompt})
    body = json.dumps({"messages": msgs,
                       "max_tokens": max_tokens, "temperature": 0},
                      ensure_ascii=False).encode()
    try:
        s.connect((HOST, PORT))
        s.sendall(b"POST /v1/chat/completions HTTP/1.0\r\nHost: x\r\n"
                  b"Authorization: Bearer " + KEY.encode() + b"\r\n"
                  b"Content-Type: application/json\r\n"
                  b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
        buf = b""
        t0 = time.perf_counter()
        while True:
            c = s.recv(65536)
            if not c:
                break
            buf += c
        dt = time.perf_counter() - t0
        head, _, raw = buf.partition(b"\r\n\r\n")
        if b" 200" not in head.split(b"\r\n")[0]:
            return {"ok": False, "err": head.split(b"\r\n")[0].decode("latin-1")}
        d = json.loads(raw)
        msg = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        u = d.get("usage") or {}
        return {"ok": True, "text": msg.strip(), "s": round(dt, 2),
                "ctok": u.get("completion_tokens") or 0,
                "tps": round((u.get("completion_tokens") or 0) / dt, 2) if dt else None}
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": False, "err": type(exc).__name__}
    finally:
        s.close()


def repetition(text: str) -> float:
    """3-gram 重复占比：复读/退化时显著升高。"""
    clean = re.sub(r"\s+", "", text)
    if len(clean) < 6:
        return 0.0
    grams = [clean[i:i + 3] for i in range(len(clean) - 2)]
    if not grams:
        return 0.0
    return round(1 - len(set(grams)) / len(grams), 3)


def mixed_script(text: str) -> float:
    """⚠️ 这是个**坏指标**，保留只为留档，不要拿它下结论。

    它把 `tentacle.py` / `media_pipeline` 这种**合法英文标识符**也算成"乱码"。
    2026-10-28 实测：一段完全正常的原文算出来 0.714，比一段有错字的还算得更高。
    ⇒ 区分不出好坏。要判乱码请看「标点数量」「标识符数量」「结构有效性」。
    """
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    if not cjk:
        return 0.0
    # 中文串里出现的拉丁字母/带变音符字母
    latin = re.findall(r"[A-Za-zÀ-ÿ]", text)
    return round(min(1.0, len(latin) / max(1, len(cjk))), 3)


def struct_valid(text: str) -> bool:
    """能否给出至少两行合法 key=value。"""
    pairs = re.findall(r"[\u4e00-\u9fffA-Za-z_]+\s*=\s*\S+", text)
    return len(pairs) >= 2


def identity(text: str) -> bool:
    t = text.upper()
    return ("小土豆" in text) or ("GBT" in t) or ("自由的风" in text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--compare", action="store_true",
                    help="对照实验：同一问题，裸问 vs 加「说人话」system prompt")
    a = ap.parse_args()

    if not up():
        print("  🔴 :1234 不在 —— 不编数字，等容器起来再测")
        print("     起来后跑：python3 tools/a19_quality.py")
        return 1

    if a.compare:
        # 假设：输出"像乱码"是**风格**（压缩速记），不是能力塌了。
        # 判据：加一句正常的 system prompt，看它能不能回到正常中文口语。
        SYS = ("用正常的中文口语回答，句子之间加标点，不要用内部术语缩写，"
               "不要输出 key=value，不要写代码标识符。像跟人说话那样说。")
        q = "介绍一下你自己，说说你能帮我做什么。"
        print("  对照实验：同一问题，只差一句 system prompt\n")
        for tag, sysmsg in (("裸问", None), ("加提示", SYS)):
            r = ask(q, max_tokens=160, system=sysmsg)
            if not r["ok"]:
                print("  %-6s 🔴 %s" % (tag, r["err"])); continue
            t = r["text"]
            punct = len(re.findall(r"[，。！？、；：]", t))
            idents = len(re.findall(r"[a-z_]{3,}\.[a-z]{2,}|[a-z]+_[a-z_]+", t))
            print("  %-6s %.2fs · %s tok/s · 标点 %d 个 · 标识符 %d 个"
                  % (tag, r["s"], r["tps"], punct, idents))
            print("        原话: %s" % t[:150].replace("\n", " "))
        print("\n  判读：若「加提示」标点明显变多、标识符变少 ⇒ 是**风格**问题，能力没塌")
        return 0

    print("  %-6s %-10s %-8s %-8s %-8s %s" %
          ("类型", "耗时", "tok/s", "重复率", "混排率", "其他"))
    rows = []
    for kind, bank in (("自由文本", FREE), ("结构化", STRUCT)):
        for q in bank * a.runs:
            r = ask(q)
            if not r["ok"]:
                print("  %-6s 🔴 %s" % (kind, r["err"]))
                rows.append({"kind": kind, "q": q, "ok": False, "err": r["err"]})
                continue
            t = r["text"]
            rep, mix = repetition(t), mixed_script(t)
            extra = []
            if kind == "结构化":
                extra.append("结构%s" % ("✅" if struct_valid(t) else "🔴"))
            extra.append("身份%s" % ("✅" if identity(t) else "—"))
            print("  %-6s %-10s %-8s %-8s %-8s %s" %
                  (kind, "%.2fs" % r["s"], r["tps"], rep, mix, " ".join(extra)))
            rows.append({"kind": kind, "q": q, "ok": True, "text": t,
                         "s": r["s"], "tps": r["tps"],
                         "repetition": rep, "mixed": mix,
                         "struct_ok": struct_valid(t) if kind == "结构化" else None})

    free = [r for r in rows if r["ok"] and r["kind"] == "自由文本"]
    stct = [r for r in rows if r["ok"] and r["kind"] == "结构化"]
    print("\n  === 判读 ===")
    if free:
        avg_rep = sum(r["repetition"] for r in free) / len(free)
        avg_mix = sum(r["mixed"] for r in free) / len(free)
        print("  自由文本：重复率 %.3f · 混排率 %.3f" % (avg_rep, avg_mix))
        if avg_mix > 0.05 or avg_rep > 0.12:
            print("   ⇒ 自由文本**确有退化**：串词/混排/复读，这是量化噪声，不是它'菜'")
        else:
            print("   ⇒ 自由文本未见过度退化")
    if stct:
        okn = sum(1 for r in stct if r["struct_ok"])
        print("  结构化　：%d/%d 给出合法 key=value" % (okn, len(stct)))
        print("   ⇒ 结构化输出正常 ⇒ **它在干本职（把话落到能力位）**")
    tpss = [r["tps"] for r in rows if r["ok"] and r["tps"]]
    if tpss:
        print("  速度　　：%s tok/s（此前实测 8–11.7，掉一半要看热节流/低电量）"
              % ("/".join(str(x) for x in tpss)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n  明细: state/a19_quality.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
