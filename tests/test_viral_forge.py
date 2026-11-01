# gbt-capability: viral_forge
"""viral_forge 判据（纯文本；不联网/不读视频）。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "gbt_allinone" / "tentacle" / "viral_forge.py"
FAILED = []

SRT = """1
00:00:00,000 --> 00:00:02,000
你绝对想不到，这个 99 块的耳机

2
00:00:02,000 --> 00:00:05,000
竟然比 1000 块的还好

3
00:00:05,000 --> 00:00:09,000
我拆开给你看

4
00:00:09,000 --> 00:00:13,000
单元、调音、续航全都不虚

5
00:00:13,000 --> 00:00:16,000
想买的点左下角

6
00:00:16,000 --> 00:00:18,000
关注我，下期拆别的
"""


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def load():
    spec = importlib.util.spec_from_file_location("viral_forge_mod", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    V = load()
    print("[1] 解析 SRT")
    cues = V.parse_srt(SRT)
    check("6 条 cue", len(cues) == 6, len(cues))
    check("时间连续", cues[0]["start"] == 0 and cues[-1]["end"] == 18.0, (cues[0], cues[-1]))

    print("[2] teardown")
    r = V.run("teardown", text=SRT, duration=18,
              brief={"product": "百元耳机", "audience": "学生", "pain": "预算低",
                     "promise": "千元音质", "twist": "比千元还好"},
              variants=3)
    check("ok", r.get("ok") is True, r.get("error"))
    rd = r["reading"]
    check("时长 18", rd["duration_s"] == 18.0, rd["duration_s"])
    check("钩子抓到", "想不到" in rd["hook"], rd["hook"])
    check("钩子类型明确", rd["hook_type"] in ("number", "contrast", "curiosity", "command"), rd["hook_type"])
    check("语速 > 0", rd["wpm"] and rd["wpm"] > 0, rd["wpm"])
    check("5 秒节奏非空", len(rd["pacing_every_5s"]) >= 2, rd["pacing_every_5s"])
    roles = [s["role"] for s in rd["segments"]]
    check("段落含 hook", "hook" in roles, roles)
    check("CTA 抓到", "左下角" in rd.get("cta", "") or "关注" in rd.get("cta", ""), rd.get("cta"))

    print("[3] recipe / variants")
    rec = r["recipe"]
    check("配方格式", rec["format"] == "viral_clone_v1", rec.get("format"))
    check("词锚", rec["anchor"] == "word", rec.get("anchor"))
    check("场景非空", len(rec["segments"]) >= 3, len(rec["segments"]))
    check("三个变体", len(rec["variants"]) == 3, rec["variants"])
    check("变体带角度", all(v.get("angle") and v.get("hook") for v in rec["variants"]), rec["variants"])
    check("红线在配方里", len(rec.get("guardrails") or []) >= 3, rec.get("guardrails"))

    print("[4] blueprint / 错误")
    b = V.run("blueprint", text=SRT, variants=5)
    check("blueprint ok", b.get("ok") is True)
    check("blueprint 5 变体", len(b["recipe"]["variants"]) == 5)
    need = V.run("teardown")
    check("缺输入 needs_input", need.get("ok") is False and need.get("status") == "needs_input", need)
    check("未知 op fail-closed", V.run("xxx").get("ok") is False)
    check("status 列边界", "不是" in V.STATUS["not_implemented"][0] or V.STATUS["not_implemented"], V.STATUS)

    print("[5] 视频帧分析（解析器，无需 ffmpeg）")
    check("showinfo 切点解析", V._parse_showinfo("... pts_time:1.234 ... pts_time:2.500 ...") == [1.234, 2.5],
          V._parse_showinfo("... pts_time:1.234 ... pts_time:2.500 ..."))
    vol = V._parse_volumedetect("mean_volume: -18.5 dB\nmax_volume: -1.2 dB")
    check("音量解析", vol == {"mean_volume_db": -18.5, "max_volume_db": -1.2}, vol)
    st = V._shot_stats([5, 10], 20)
    check("镜头统计", st["cuts"] == 2 and st["shots"] == 3 and st["first_shot_s"] == 5.0, st)
    check("缺 ffprobe 如实 needs_dependency（有则跳过）",
          V._find_bin("ffprobe") != "" or V.analyze_video("x.mp4").get("status") == "needs_dependency",
          V.analyze_video("x.mp4"))

    print("[6] 画面色彩 / 关键帧解析")
    vs = V._parse_visual("lavfi.signalstats.YAVG=100.0\nlavfi.signalstats.YAVG=120.0\nlavfi.signalstats.SATAVG=10.0")
    check("亮度统计", vs["yavg"]["n"] == 2 and vs["yavg"]["mean"] == 110.0, vs)
    check("饱和度统计", vs["satavg"]["mean"] == 10.0, vs)
    kf = V._parse_keyframes("0.0,I\n2.0,P\n4.0,I\n")
    check("关键帧只取 I", kf == [0.0, 4.0], kf)
    check("色/帧解析器齐", hasattr(V, "_visual_stats") and hasattr(V, "_keyframes"))

    print("[7] 切点对齐 / 镜头字幕 / 导帧 / pipeline")
    al = V._align_cues([{"start": 0.0, "end": 3.0, "text": "abcdef"}], [1.5])
    check("切点拆字幕 2 段", len(al) == 2, al)
    check("拆后对齐切点", al[1]["start"] == 1.5 and al[0]["end"] == 1.5, al)
    shots = V._shot_captions([{"start": 0, "end": 2, "text": "a"}, {"start": 2, "end": 4, "text": "b"}], [2], 4)
    check("镜头字幕 2 镜", len(shots) == 2 and shots[0]["caption"] == "a", shots)
    fr = V._extract_frames("x.mp4", [1.0])
    if V._find_bin("ffmpeg"):
        check("导帧结构", "files" in fr, fr)
    else:
        check("缺 ffmpeg 导帧如实报缺", fr.get("status") == "needs_dependency", fr)
    pipe = V.run("pipeline", text=SRT, variants=1)
    check("pipeline 串联", pipe.get("ok") is True and "analysis" in pipe and "forge" in pipe, pipe)
    check("pipeline 链名", pipe.get("chain") == ["analyze", "teardown", "recipe"], pipe.get("chain"))

    print("[8] inbox 目录投放")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "a.mp4"
        p.write_bytes(b"fake")
        got = V._scan_inbox(Path(td))
        check("扫到视频", len(got) == 1 and got[0].name == "a.mp4", got)
        check("done key 稳定", V._done_key(p) == V._done_key(p))
        empty = Path(td) / "empty"
        empty.mkdir()
        r = V.run("inbox", inbox=str(empty))
        check("空目录不报错", r.get("ok") is True and r.get("status") == "empty", r)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
