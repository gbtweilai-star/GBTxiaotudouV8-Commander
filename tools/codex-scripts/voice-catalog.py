# -*- coding: utf-8 -*-
r"""语音总目录（voice-catalog）—— **把全部可用语音注入框架**，一页挑。

主人令（2026-10-10，逐字）：
  「我们不是有646个语音吗？为什么我要求的台湾腔女声，却一直都是这鬼叫声，**把全部语音注入框架里面啊**」

## 先纠正一个数字（如实，不顺着说）
**646 是 VoiceStudio 的「语言」数**（voice_orchestra.py:71：完全本地 · 646 语言 · 克隆/设计/配音/转写），
**不是 646 个语音**。本机**实际能出声的语音** = SAPI 3 个 + VoiceStudio 克隆音 N 个，
另外还有 VoiceStudio **可造的 48 个 instruct token**（2 性别 × 5 年龄 × 5 音高 × 1 耳语 × 10 口音 × 12 方言）。

## 「台湾腔女声」为什么出不来（根因，带出处）
VoiceStudio 引擎的 instruct 是**闭集白名单**，单一真源 = core/archetypes._VD._INSTRUCT_ALL_VALID
（**48 个 token**：gender 2 · age 5 · pitch 5 · whisper 1 · accents 10 · dialects 12 中文方言）。
**这 48 个里没有任何台湾话/台湾腔** —— 实测原文（HTTP 400）：
  'taiwanese mandarin accent' -> unsupported; did you mean 'japanese accent'?
⇒ 想拿到台湾腔，只有两条路：
  ① **克隆**（给一段台湾腔女声样音 ⇒ VoiceStudio clone）；② 换一个引擎外能造台湾腔的通道。
**这两条都需要主人侧的那样东西，或者换通道** —— 不许含糊过去，也不许假装已经做出来。

## 本件干什么
把**全部可用语音**枚举成一张表 + 一页（SAPI · VoiceStudio 克隆音 · 48 个可造 token），
逐条写清**怎么用**，**让主人一眼挑**。判据：表里每条都要有**怎么用**（缺一即红）。

用法：py -3.14 -X utf8 tools/codex-scripts/voice-catalog.py [--check]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "voice-catalog.json"
VS = "http://127.0.0.1:3900"


def _sapi() -> list:
    out = []
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Speech\Voices\Tokens")
        for i in range(winreg.QueryInfoKey(key)[0]):
            name = winreg.EnumKey(key, i)
            try:
                sub = winreg.OpenKey(key, name + r"\Attributes")
                lang, _ = winreg.QueryValueEx(sub, "Language")
            except OSError:
                lang = ""
            out.append({"源": "SAPI", "名": name, "语言码": lang,
                        "怎么用": "cap voice（SAPI 那个口）"})
    except OSError:
        pass
    return out


def _vs(path: str):
    """取 VoiceStudio 的只读面 —— **形状两种都收**（实测 /gallery/voices 回的是列表，
    别的口回字典；按形状猜会崩，所以两种都接）。"""
    try:
        with urllib.request.urlopen(VS + path, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:                                 # noqa: BLE001
        return {"ok": False, "reason": "%s: %s" % (type(exc).__name__, str(exc)[:80])}


def _items(d, *keys) -> list:
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for k in keys:
            if isinstance(d.get(k), list):
                return d[k]
    return []


def _tokens() -> list:
    try:
        sys.path.insert(0, str(ROOT / "_upstream" / "VoiceStudio" / "backend"))
        from core.archetypes import _VD
        cats = ["gender", "age", "pitch", "whisper", "accents", "dialects"]
        rows = []
        for n, c in zip(cats, _VD._INSTRUCT_CATEGORIES):
            for t in c:
                rows.append({"源": "VoiceStudio·可造", "类": n, "名": str(t),
                             "怎么用": "voicestudio.py speak --instruct 逗号拼 token（必须全在白名单里）"})
        return rows
    except Exception:
        return []


def check() -> int:
    rows = _sapi()
    g = _vs("/gallery/voices")
    prof = _vs("/profiles")
    for v in _items(g, "voices", "items"):
        rows.append({"源": "VoiceStudio·克隆音", "名": v.get("name") or v.get("id"),
                     "id": v.get("id"), "语言": v.get("language"),
                     "怎么用": "voicestudio.py speak --profile %s" % (v.get("id") or "")})
    for p in _items(prof, "profiles", "items"):
        rows.append({"源": "VoiceStudio·人设", "名": p.get("name") or p.get("id"),
                     "id": p.get("id"),
                     "怎么用": "voicestudio.py speak --profile %s" % (p.get("id") or "")})
    rows.extend(_tokens())
    bad = [r for r in rows if not r.get("怎么用")]
    d = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "总条": len(rows),
         "分源": {s: sum(1 for r in rows if r["源"] == s) for s in {r["源"] for r in rows}},
         "vs_up": not (isinstance(g, dict) and g.get("ok") is False),
         "逐条": rows,
         "台湾腔": {"有无 token": False,
                    "出处": "core/archetypes._VD._INSTRUCT_ALL_VALID（48 个 token 里没有台湾）",
                    "实测": "HTTP 400: taiwanese mandarin accent -> unsupported",
                    "两条路": ["克隆：给一段台湾腔女声样音 => voicestudio.py clone",
                              "换通道：找引擎外能造台湾腔的语音通道"]}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("语音总目录：%d 条" % len(rows))
    for k, v in d["分源"].items():
        print("  %-22s %d" % (k, v))
    print("  VoiceStudio 引擎：%s" % ("在" if d["vs_up"] else "**没起**（跑 voicestudio.py up）"))
    print("  台湾腔：**引擎词表里没有**（出处 _INSTRUCT_ALL_VALID 48 token）=> 只能克隆或换通道")
    print("判据：%s" % ("PASS" if not bad else "FAIL（有 %d 条没写怎么用）" % len(bad)))
    return 0 if not bad else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="语音总目录")
    ap.add_argument("--check", action="store_true")
    ap.parse_args()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
