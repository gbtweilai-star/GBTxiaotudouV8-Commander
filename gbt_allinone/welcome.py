# -*- coding: utf-8 -*-
r'''GBT小土豆V8 · 数字人启动欢迎语（单一真源）

口径（主人令 2026-10-10）：「启动APP数字人的欢迎语，你来看看说什么，
  要有 GBT小土豆V8 和 开发者：自由的风，其他你来想，要有未来感的语言」

必含项（判据会咬）：'GBT小土豆V8' 与 '开发者：自由的风'。
事实核对（不许编）：646 是**语言数**（VoiceStudio 引擎口径），不是语音数；
  '我不猜' = 验收闸口径。
🔴 触手**不写数字**（2026-10-30 深度对齐）：本仓「域」有四种粒度、四个数 ——
  manifest 域段 10（`omni_tentacle.TENTACLE_MANIFEST`）· 邻域 13（`bridge.TENTACLE_NEIGHBORHOOD_MAP`）·
  能力大类 12（`cap_taxonomy.CATEGORIES`）· 绑定台账 10（`state/cap-bindings.json`）。
  原句写死「十域触手」= 挑一个数当真、另三个当不存在 ⇒ 自我介绍只称「触手」，**不报数**。
'''

WELCOME = "系统唤醒。\n\n我是 GBT小土豆V8 —— 你的指挥官框架。\n六百四十六种语言在我体内，满身触手听你调度，神经末梢已经接通。\n\n我看得见屏幕，听得见房间，动得了界面。\n我不猜 —— 我只跑通闭环。\n\n开发者：自由的风。\n\n说一句，剩下的交给我。"

# 短版：只够出声用（CPU 造声约 150 倍慢于实时，长文本要几十分钟）
WELCOME_SHORT = "系统唤醒。我是 GBT小土豆V8，你的指挥官框架。我不猜，只跑通闭环。开发者：自由的风。"

REQUIRED = ("GBT小土豆V8", "开发者：自由的风")


AUDIO = ROOT_AUDIO = None  # 见 run()：音频是**预生成缓存**，不在启动时现造


def run(op: str = "text", **kw) -> dict:
    r"""能力位入口（走唯一门 run_task）。

    op:
      · **text**   取欢迎语全文 + 必含项判据（默认）
      · **audio**  预生成音频的**落点与状态**（在不在盘、多大、多少秒）
      · **boot**   启动用：要显示什么 + 要播哪个文件（**一次给全**，界面不用再问）

    🔴 为什么音频是**预生成**：本机 TTS 走 CPU，约 **150 倍慢于实时**
    （实测：2.36 秒音频用 327 秒）⇒ **启动时现造要等几十分钟**，那是坑不是功能。
    ⇒ 欢迎语音频**造一次、缓存到盘**，启动直接播缓存；文件不在就**如实报没造**，
    界面退化成只显示文字 —— 不许静默、也不许假装播了。
    """
    op = (op or "text").lower()
    if op == "text":
        c = check()
        return {"ok": True, "op": "text", **c,
                "口径": "必含项 " + " 与 ".join(REQUIRED) + "；判据在 welcome.check()"}
    if op in ("audio", "boot"):
        import pathlib
        d = pathlib.Path(__file__).resolve().parents[1] / "holo_pet_w3" / "digital-human"
        cands = sorted(d.glob("welcome-*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not cands:
            info = {"ok": False, "state": "**未造**",
                    "怎么造": "py -3.14 -X utf8 tools/codex-scripts/voicestudio.py speak "
                              "--text <WELCOME_SHORT> --instruct \"female, young adult, "
                              "moderate pitch, chinese accent\" --language zh"}
        else:
            f = cands[0]
            import struct
            b = f.read_bytes()
            sr, ch, bits = struct.unpack_from("<IHH", b, 24)[0], struct.unpack_from("<H", b, 22)[0], struct.unpack_from("<H", b, 34)[0]
            info = {"ok": True, "state": "已造", "文件": str(f),
                    "字节": len(b), "秒": round(len(b) / max(1, sr * ch * bits // 8), 2)}
        if op == "audio":
            return dict({"op": "audio"}, **info)
        c = check()
        return {"ok": True, "op": "boot", "显示": c["全文"], "必含项齐": c["ok"],
                "播": info, "口径": "启动：先显示「显示」全文，再播「播」里的文件；没造就只显示"}
    return {"ok": False, "op": op, "error": "unknown op", "known": ["text", "audio", "boot"]}


def check(text: str = WELCOME) -> dict:
    miss = [r for r in REQUIRED if r not in text]
    return {"ok": not miss, "缺必含项": miss, "字数": len(text), "全文": text}


if __name__ == "__main__":
    import sys
    r = check()
    print(r["全文"])
    print()
    print("字数 %d · 必含项 %s · 判据 %s" % (r["字数"], "齐" if r["ok"] else r["缺必含项"], "PASS" if r["ok"] else "FAIL"))
    raise SystemExit(0 if r["ok"] else 1)