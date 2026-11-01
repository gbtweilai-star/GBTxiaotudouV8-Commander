# gbt-capability: drama_forge
"""drama_forge 判据（纯函数；不跑 TTS/ffmpeg）。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "gbt_allinone" / "tentacle" / "drama_forge.py"
FAILED = []

SCRIPT = """0s – 4s（标题）大特写 冷蓝 黑屏里浮起一行字：醒来
4s – 9s（睁眼）特写 推近 一颗锈迹小土豆在冷却液池底缓缓睁眼
9s – 14s（对视）近景 环绕 控制台前的影子回头，两张脸对上
"""


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def load():
    spec = importlib.util.spec_from_file_location("drama_forge_mod", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    D = load()
    print("[1] SRT 时间")
    check("1.5s", D._srt_ts(1.5) == "00:00:01,500", D._srt_ts(1.5))
    check("65.25s", D._srt_ts(65.25) == "00:01:05,250", D._srt_ts(65.25))
    s = D._srt([(0, 2, "第一句"), (2, 4, "第二句")])
    check("SRT 段数", s.count("-->") == 2, s)

    print("[2] 剧本→分镜（复用 drama 链头）")
    r = D.run("storyboard", script=SCRIPT)
    check("storyboard ok", r.get("ok") is True, r.get("error"))
    check("三镜", len(r.get("shots") or []) == 3, len(r.get("shots") or []))
    if r.get("ok"):
        sh = r["shots"][0]
        check("有时间码", sh["t0"] == 0 and sh["t1"] == 4, sh)
        check("六字段在", all(k in sh for k in ("shot_size", "camera", "dur", "emotion", "subject", "desc")))

    print("[3] 其他")
    check("wrap 可见", isinstance(D._wrap("一二三四五六七八九十"), list))
    check("status 列 ops", "make" in D.STATUS["ops"] and "series" in D.STATUS["ops"])
    check("五拍模板", [x[0] for x in D._BEATS] == ["钩子", "铺垫", "冲突", "反转", "悬念"])
    check("unknown op fail-closed", D.run("xxx").get("ok") is False)

    print("[9] AI 画面适配器（无命令 → needs_model）")
    g = D.run("gen", script=SCRIPT)
    check("gen 有边界", g.get("status") in ("needs_model", "generated", "failed", "not_writable"), g)
    check("无 GBT_T2I_CMD 就 needs_model", g.get("status") in ("needs_model", "not_writable"), g)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
