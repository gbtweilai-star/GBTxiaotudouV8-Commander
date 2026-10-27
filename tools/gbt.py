#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gbt —— 唯一入口。九个子系统收成一条命令，不用记九个脚本名。

    gbt status                     一眼看全：容器 / 桥 / 内核 / 队列
    gbt a19 status|up|ask|chat|accept|t2i …
    gbt test                       她的人格五项体检（--full 用全量人格对照）
    gbt gate <图> [--profile photo|poster]
    gbt fix <图> [--reframe] [--declutter] [--out x.png]
    gbt batch '<glob>' [--out DIR] [--video f.mp4] [--limit N]
    gbt gen "<提示词>" [--seed N] [--gate photo]
    gbt loop "<题材>" [--rounds N]
    gbt grab [--tags a,b] [--desc 说明] [--pattern 'beam-*.png']   抓最新截图入库
    gbt assets                     素材台账（大小/指纹/标签）
    gbt ingest <文件…> [--tags a,b] [--prefix deck-]   把文件收进素材库并登记清单
    gbt beam [--check] [--auto] [--imgs a,b] [--img x] [--hold 4]
                                   一键起视觉装置（相机/单图/轮播均可）
    gbt judge                      判断"开源现成方案"能否落到本机（四问）
    gbt receiver                   自己部署接收端（Mac 自带 / UxPlay / 智能电视）
    gbt freeproject                零成本投墙（A 透镜 / B 拆旧LCD / C 已有大屏）
    gbt projector                  买投影仪时的参数参考（当前不建议花钱）
    gbt project                    投屏能力自检（不假装已连设备）
    gbt deckcheck <目录> [--expect-audio --expect-subs]   演示台成品验收
    gbt deck --spec d.json --out DIR  投影演示台（HTML + 翻页，AirPlay 即投屏）
    gbt cinema <视频>               投影看电影（转码 + 原生全屏播放，AirPlay 可用）
    gbt video K1 K2 [K3] --out f.mp4 [--total 5.0]
    gbt doc                        列出手册

设计原则：**只做分发，不重实现**。每个子命令直接调用既有脚本，避免两份真相。
"""
import argparse, glob, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, "tools")
P = sys.executable


def run(script, args, cwd=None):
    cmd = [P, os.path.join(T, script)] + args
    return subprocess.call(cmd, cwd=cwd or ROOT)


def status():
    import socket, json
    def up(port):
        s = socket.socket(); s.settimeout(0.8)
        try: s.connect(("127.0.0.1", port)); return True
        except Exception: return False
        finally: s.close()
    a19 = up(1234); br = up(8791)
    q = 0
    qp = "/tmp/a19_queue.jsonl"
    if os.path.exists(qp):
        q = sum(1 for l in open(qp, encoding="utf-8") if l.strip())
    ledger = os.path.join(ROOT, "state", "her_transcript.jsonl")
    n = sum(1 for l in open(ledger, encoding="utf-8") if l.strip()) if os.path.exists(ledger) else 0
    print("容器 A19 :1234   %s" % ("UP" if a19 else "DOWN"))
    print("模型桥 :8791    %s" % ("UP" if br else "DOWN"))
    print("队列             %d 条" % q)
    print("账本             %d 行" % n)
    for f, label in (("state/taste_kernel.txt", "品味内核"),
                     ("docs/23-local-repair-playbook.md", "修复手册")):
        p = os.path.join(ROOT, f)
        print("%-14s %s" % (label, "在" if os.path.exists(p) else "缺"))


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 0
    sub = sys.argv[1]; rest = sys.argv[2:]

    if sub == "pack":
        return run("pack.py", rest)
    if sub == "doctor":
        return run("doctor.py", rest)
    if sub == "status":
        status(); return 0
    if sub == "persona":
        root = os.path.join(ROOT, "state")
        lite = os.path.join(root, "her_persona_lite.txt")
        full = os.path.join(root, "her_persona.txt")
        which = rest[0] if rest else "show"
        if which == "lite":
            print(open(lite, encoding="utf-8").read()); return 0
        if which == "full":
            print(open(full, encoding="utf-8").read()); return 0
        # 默认：两版字数/token 对照
        for f, tag in ((lite, "精简（默认）"), (full, "全量")):
            if os.path.exists(f):
                t = open(f, encoding="utf-8").read()
                est = round(len(t) / 1.6)
                print("%-12s %4d 字 · 约 %3d token · 占 4096 的 %.0f%%"
                      % (tag, len(t), est, est / 4096 * 100))
        print("\n用法：gbt persona lite|full  （打印内容）")
        return 0
    if sub == "doc":
        for f in sorted(glob.glob(os.path.join(ROOT, "docs", "*.md"))):
            print(os.path.basename(f))
        return 0
    if sub == "test":
        return run("a19_persona_test.py", rest)
    if sub == "gate":
        return run("taste_gate.py", ["--judge"] + rest)
    if sub == "fix":
        ap = argparse.ArgumentParser(); ap.add_argument("img")
        ap.add_argument("--out"); ap.add_argument("--reframe", action="store_true")
        ap.add_argument("--declutter", action="store_true")
        a, _ = ap.parse_known_args(rest)
        cur = a.img
        if a.declutter:
            out = (a.out or a.img.rsplit(".",1)[0] + "_gbt.png").replace(".png","_dc.png")
            run("declutter.py", [cur, "--out", out]); cur = out
        if a.reframe:
            out = (a.out or a.img.rsplit(".",1)[0] + "_gbt.png")
            run("reframe.py", [cur, "--out", out]); cur = out
        run("polish2.py", [cur, "--out", (a.out or a.img.rsplit(".",1)[0] + "_gbt.png")])
        return run("taste_gate.py", ["--judge", (a.out or a.img.rsplit(".",1)[0] + "_gbt.png")])
    if sub == "batch":
        return run("batch_polish.py", rest)
    if sub == "gen":
        return run("a19_t2i.py", rest)
    if sub == "loop":
        return run("gen_loop.py", rest)
    if sub == "deck":
        return run("deck.py", rest)
    if sub == "grab":
        # 从浏览器下载目录里捞最新一张（装置点「截图」后落在这里），交给 ingest 入库
        import glob as _g
        pat = "beam-*.png"
        tags = ""
        desc = ""
        i = 0
        while i < len(rest):
            if rest[i] == "--tags" and i + 1 < len(rest): tags = rest[i+1]; i += 2
            elif rest[i] == "--desc" and i + 1 < len(rest): desc = rest[i+1]; i += 2
            elif rest[i] == "--pattern" and i + 1 < len(rest): pat = rest[i+1]; i += 2
            else: i += 1
        cands = []
        for d in ("/var/minis/workspace", "/var/minis/offloads", "/var/minis/browser"):
            cands += _g.glob(os.path.join(d, pat))
        if not cands:
            print("没找到 %s（先在装置里点📷截图）" % pat); return 2
        newest = max(cands, key=os.path.getmtime)
        print("取最新：%s · %.0f KB" % (newest, os.path.getsize(newest)/1024))
        args = [newest]
        if tags: args += ["--tags", tags]
        if desc: args += ["--desc", desc]
        return run("ingest.py", args)
    if sub == "assets":
        import json as _j
        mp = "/var/minis/attachments/assets/manifest.json"
        try:
            man = _j.load(open(mp, encoding="utf-8"))
        except Exception:
            print("没有素材清单：%s" % mp); return 1
        tot = sum(e.get("bytes") or 0 for e in man)
        print("%-24s %9s  %-16s %s" % ("文件", "大小", "sha256", "标签"))
        print("-" * 78)
        for e in man:
            print("%-24s %7.1f KB  %-16s %s"
                  % (e.get("file", "?"), (e.get("bytes") or 0) / 1024,
                     e.get("sha256") or "(缺)", ",".join(e.get("tags") or []) or "-"))
        print("-" * 78)
        nohash = [e["file"] for e in man if not e.get("sha256")]
        adir = "/var/minis/attachments/assets"
        have = set(os.listdir(adir)) - {"manifest.json"} if os.path.isdir(adir) else set()
        reg = {e.get("file") for e in man}
        orphans = sorted(have - reg)
        lost = sorted(reg - have)
        print("%-24s" % "" )
        print("清单 %d 条 · 目录 %d 个 · 合计 %.1f MB" % (len(man), len(have), tot / 1048576))
        print("指纹    %s" % ("齐全" if not nohash else "缺 %d 条：%s" % (len(nohash), ",".join(nohash))))
        print("孤儿    %s" % ("无" if not orphans else "%d 个：%s" % (len(orphans), ",".join(orphans))))
        print("缺失    %s" % ("无" if not lost else "%d 个：%s" % (len(lost), ",".join(lost))))
        return 0 if not (orphans or lost or nohash) else 1
    if sub == "ingest":
        return run("ingest.py", rest)
    if sub == "beam":
        # 一条命令起“视觉装置”：页面服务 + 打开 Safari（相机只在 Safari 里给）+ 投屏提示
        import socket, subprocess as _sp, time as _t
        def up(port):
            s2 = socket.socket(); s2.settimeout(0.8)
            try: s2.connect(("127.0.0.1", port)); return True
            except Exception: return False
            finally: s2.close()
        page = os.path.join(ROOT, "holo_pet_w3")
        if not up(8080):
            _sp.Popen([P, "-m", "http.server", "8080"], cwd=page,
                      stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, start_new_session=True)
            for _ in range(20):
                _t.sleep(0.3)
                if up(8080): break
        # --imgs "a.png,b.png" 轮播 / --img 单图 / 默认相机
        q = ""
        i = 0
        while i < len(rest):
            if rest[i] in ("--imgs", "--img", "--hold", "--src") and i + 1 < len(rest):
                k = rest[i].lstrip("-")
                q += ("&" if q else "?") + k + "=" + rest[i+1]
                i += 2
            else:
                i += 1
        url = "http://127.0.0.1:8080/kaleido/v12b.html" + q
        ok = up(8080)
        print("页面服务  :8080 %s" % ("在线" if ok else "起不来"))
        print("视觉装置  %s" % url)
        # --auto：起一个后台轮询，每 5 秒看 workspace 有没有新的 beam-*.png，
        #        有就自动 ingest 入库（省掉手动 gbt grab）
        if "--auto" in rest:
            import glob as _g2
            tag = "装置,截图"
            for i2, v2 in enumerate(rest):
                if v2 == "--tags" and i2 + 1 < len(rest):
                    tag = rest[i2 + 1]
            seen = set(_g2.glob("/var/minis/workspace/beam-*.png"))
            script = (
                "import glob,os,subprocess,sys,time\n"
                "seen=set(%r)\n"
                "for _ in range(720):\n"
                "    time.sleep(5)\n"
                "    for f in glob.glob('/var/minis/workspace/beam-*.png'):\n"
                "        if f in seen: continue\n"
                "        seen.add(f)\n"
                "        print('入库', f, flush=True)\n"
                "        subprocess.run([sys.executable, %r, f, '--tags', %r])\n"
            ) % (seen, os.path.join(ROOT, "tools", "ingest.py"), tag)
            _sp.Popen([P, "-c", script], stdout=open("/tmp/beam_auto.log", "w"),
                      stderr=subprocess.STDOUT, start_new_session=True)
            print("自动入库  已开启（每 5 秒扫一次，日志 /tmp/beam_auto.log）")
        if "--check" not in rest:
            _sp.run(["apple-open", url], capture_output=True)
            print("已交给 Safari 打开（相机权限只在这里会给）")
        print("\n接着三步：")
        print("  ① Safari 弹权限 → 允许相机")
        print("  ② 双指捏合/旋转；预设 2/3/4/6/8·慢旋·特写；效果 万花筒/隧道/对称镜/色散")
        print("     录制：点「● 录制」→ 停止 → 点「下载」存到手机")
        print("  ③ 控制中心 → 屏幕镜像 → 选接收端（Mac / 电视 / 投影仪）")
        return 0
    if sub == "judge":
        print("这类\"开源有现成的\"能不能落到这台 iPhone —— 四问")
        print("  ① 要不要光？      要 → 光只能来自屏幕/投影仪/胶片，摄像头永远不行")
        print("  ② 要不要实时相机？要 → iOS 只能写成原生 App（脚本无解）")
        print("  ③ 要不要无线投屏？要 → 只有 AirPlay，且接收端必须存在")
        print("  ④ 视频里的效果？  先查那台机器有没有光机（Galaxy Beam / Moto Mod）")
        print("  详细评估 docs/29-spacebeam-to-ios.md")
        return 0
    if sub == "receiver":
        print("自己部署投屏接收端（零成本，不用买硬件）")
        print("  Mac(macOS 12+)  系统设置→通用→隔空投送与接力→隔空播放接收器→打开")
        print("  Win/Linux       跑 UxPlay：cmake .. && make -j4 && ./uxplay -n \"GBT-Screen\" -nh")
        print("  安卓/智能电视    多数自带 AirPlay 或『多屏互动』")
        print("  手机端          控制中心 → 屏幕镜像 → 选设备（系统 UI，我无法代按）")
        print("  前提            两台在同一 WiFi，关掉路由器的『访客隔离』")
        print("  手册            docs/26-airplay-runbook.md（第七节）")
        return 0
    if sub == "freeproject":
        print("零成本投墙（三条路，都不花钱）")
        print("  A 屏幕+凸透镜     gbt lens --f 20 --dist 1      ¥0（找片放大镜）全黑房 39x84cm")
        print("  B 拆旧LCD手机+LED 见 docs/28                       ¥0（用旧机）亮度高 50 倍量级")
        print("  C 已有大屏+投屏   电脑跑 UxPlay → 镜像              ¥0 画质最好，最稳")
        print("  前提  LCD 才透光；OLED（现役 iPhone）不能拆出背光")
        print("  手册  docs/28-free-projection.md")
        return 0
    if sub == "projector":
        print("外接微型投影仪 · 接法与验收")
        print("  接法  A AirPlay 直投（无线）｜B 投屏棒 + 任意投影（便宜）｜C HDMI 转接（最稳）")
        print("  四参数 亮度(ANSI)/原生分辨率/投射比1.2:1/必须有 HDMI")
        print("  三档    ¥300-500 入门 · ¥800-1500 主力(1080p+400ANSI) · ¥2000+ 激光")
        print("  验收    白场·对焦·亮度·分辨率·延迟·噪音·过热·梯形（8 项，见手册）")
        print("  内容    gbt deck ... --mp4 --burn-subs → gbt deckcheck → gbt cinema")
        print("  手册    docs/27-projector-buy-and-setup.md")
        return 0
    if sub == "project":
        # 投屏不是一条命令能"接上"的：这里只报**当前能做什么**，不假装已连设备
        print("投屏能力自检")
        print("  镜像 API      iOS 不开放 —— 命令行无法发起屏幕镜像")
        print("  内容就绪      deck.html / deck.mp4 / cinema 播放器里的 AirPlay 按钮")
        print("  三条路        A 支持 AirPlay 的投影仪/Apple TV")
        print("                B 电脑跑 UxPlay 接收端（开源，★3.2k）")
        print("                C USB-C/Lightning 转 HDMI")
        print("  手册          docs/26-airplay-runbook.md")
        return 0
    if sub == "deckcheck":
        return run("deck_check.py", rest)
    if sub == "cinema":
        return run("cinema.py", rest)
    if sub == "video":
        return run("strike_video.py", rest)
    if sub == "a19":
        if not rest: return run("a19_ctl.py", ["status"])
        act = rest[0]
        m = {"status": ("a19_ctl.py", ["status"]),
             "up": ("a19_ctl.py", ["up"] + rest[1:]),
             "ask": ("her.py", rest[1:]),
             "chat": ("her_chat.py", ["--ask"] + rest[1:]),
             "accept": ("a19_accept.sh", []),
             "t2i": ("a19_t2i.py", rest[1:])}
        if act not in m:
            print("a19 子命令：status/up/ask/chat/accept/t2i"); return 2
        script, args = m[act]
        if script.endswith(".sh"):
            return subprocess.call([os.path.join(T, script)], cwd=T)
        return run(script, args)
    print("不认的子命令：%s\n%s" % (sub, __doc__))
    return 2


if __name__ == "__main__":
    sys.exit(main())
