#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pack —— 把“今天能演示的东西”打成一个包（拷齐 + 一份 README）。

为什么：演示现场最怕“东西散在七八个目录里，找不到哪个是最新的”。
这里只做搬运与清单，不改内容；每个文件都记 sha256 与大小。

用法：
    python3 tools/pack.py --deck /var/minis/attachments/deckG --out /var/minis/shared/gbtv8/dist
"""
import argparse, hashlib, json, os, shutil, subprocess, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha(p, n=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(n), b""):
            h.update(b)
    return h.hexdigest()[:16]



CONSOLE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>演示控制台 · GBT小土豆V8</title>
<style>
:root{--bg:#0a0e15;--panel:#111823;--ink:#e9eef4;--dim:#93a3b8;--accent:#3fb950;--line:#18222e}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,"PingFang SC",system-ui,sans-serif;
     padding:6vh 6vw;min-height:100vh}
h1{font-size:clamp(22px,3.4vw,34px);letter-spacing:-.02em;margin-bottom:6px}
.sub{color:var(--dim);font-size:15px;margin-bottom:5vh}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;max-width:1100px}
a.card{display:block;background:var(--panel);border-radius:14px;padding:20px 22px;text-decoration:none;
       color:var(--ink);transition:transform .15s ease,background .15s}
a.card:hover{transform:translateY(-2px);background:#182131}
a.card .k{color:var(--accent);font-size:12px;letter-spacing:.12em;text-transform:uppercase}
a.card .t{font-size:19px;font-weight:700;margin:8px 0 6px}
a.card .d{color:var(--dim);font-size:14px;line-height:1.5}
.note{margin-top:6vh;color:var(--dim);font-size:13px;max-width:820px;line-height:1.7}
.note b{color:var(--ink);font-weight:600}
</style></head><body>
<h1>演示控制台</h1>
<div class="sub">GBT小土豆V8 · 框架 8.0.0 · 开发者：自由的风 · 守护者：公主土豆</div>
<div class="grid">
  <a class="card" href="deck.mp4"><div class="k">01 放片</div><div class="t">成片（90 秒无声）</div>
    <div class="d">现场讲用。每页停 18 秒，你按讲稿念，画面自己走。</div></a>
  <a class="card" href="deck.html"><div class="k">02 现场讲</div><div class="t">翻页版</div>
    <div class="d">方向键翻页，N 键出提词、T 键计时。8 秒自动前进可关。</div></a>
  <a class="card" href="kaleido.html"><div class="k">03 视觉装置</div><div class="t">万花筒</div>
    <div class="d">相机 / 图片 / 轮播四源。注意：相机权限只在 Safari 里给。</div></a>
  <a class="card" href="deck-single.html"><div class="k">02b 单文件</div><div class="t">一个文件走天下</div>
    <div class="d">配图已内联，发微信/邮件只发这一个 html，双击就开，不用带目录。</div></a>
  <a class="card" href="script.md"><div class="k">04 讲稿</div><div class="t">怎么讲</div>
    <div class="d">开场、逐页口播、追问答法、禁语，以及播放提示表。</div></a>
  <a class="card" href="review.png"><div class="k">05 审片</div><div class="t">三帧抽检</div>
    <div class="d">放之前看一眼：配图贴不贴题、字幕挡不挡内容。</div></a>
  <a class="card" href="README.md"><div class="k">06 说明</div><div class="t">投屏三条路</div>
    <div class="d">AirPlay 镜像 / 电脑当接收端 / 透镜与胶片，零成本怎么投。</div></a>
</div>
<div class="note">
  <b>投屏：</b>控制中心 → 屏幕镜像 → 选接收端（Mac、电视、投影仪）。<br>
  <b>视觉装置要相机：</b>用 Safari 打开本页的「03 视觉装置」，App 内嵌浏览器不给相机权限。<br>
  <b>没有接收端时：</b>手机全屏就是幕布；或按 README 里的透镜方案投墙。
</div>
</body></html>"""

README = """# 演示包 · {date}

> 由 `gbt pack` 生成。**这个目录是自包含的**：拷到别的机器也能演。

## 一、先看这个

| 文件 | 是什么 |
|---|---|
| `deck.mp4` | 成片（1080p · 旁白 · 硬字幕），双击即播 |
| `deck.html` | 现场讲版（方向键翻页 / N 提词 / T 计时） |
| `script.md` | 讲稿（开场 / 逐页 / 追问 / 禁语） |
| `review.png` | 审片图（三帧拼一张，先肉眼过一遍） |
| `kaleido.html` | 视觉装置（万花筒 · 五源 · 录制截图），**相机需 Safari** |
| `assets-manifest.json` | 素材台账快照（每张图的 sha256 与标签） |

## 二、三条投屏路（都不花钱）

1. **AirPlay**：控制中心 → 屏幕镜像 → 选已有电脑/电视（电脑端跑 UxPlay，或 Mac 开隔空播放接收器）
2. **屏幕 + 凸透镜**：`gbt lens --f 20 --dist 1` → 全黑房间，投 39×84cm
3. **闪光灯 + 透明胶片**：`gbt slide "标题"` → 打印到胶片 → 闪光灯 + 匀光纸 + 透镜

## 三、装置怎么跑

```bash
cd {deck_parent}                     # 与包同级
python3 -m http.server 8080          # 起服务
# Safari 打开 http://127.0.0.1:8080/kaleido/v12b.html → 允许相机
```

## 四、边界（别在台上说错）

- 摄像头**不发光**，闪光灯只有光没有图；投墙的光来自屏幕/投影仪/胶片。
- iPhone 是 OLED，拆机强背光那套不适用。
- iOS 不支持 Miracast，无线只有 AirPlay 且接收端必须存在。
"""


def verify(dst):
    """校验一个已打的包：文件齐不齐、指纹对不对、有没有绝对地址、视频能不能解。"""
    man = os.path.join(dst, "pack.json")
    if not os.path.exists(man):
        print("不是包（没有 pack.json）：%s" % dst); return 2
    meta = json.load(open(man, encoding="utf-8"))
    ok = True
    print("%-22s %-5s %s" % ("项", "结果", "读数"))
    print("-" * 62)
    for f in meta.get("files", []):
        name = f["file"]
        if name.endswith("/"):
            d = os.path.join(dst, name.strip("/"))
            n = len(os.listdir(d)) if os.path.isdir(d) else 0
            good = n > 0
            print("%-22s %-5s %d 个文件" % (name, "OK" if good else "FAIL", n))
            ok = ok and good
            continue
        p = os.path.join(dst, name)
        if not os.path.exists(p):
            print("%-22s %-5s 缺文件" % (name, "FAIL")); ok = False; continue
        good = sha(p) == f.get("sha256")
        print("%-22s %-5s 指纹%s" % (name, "OK" if good else "FAIL",
                                     "一致" if good else "不一致（被改过）"))
        ok = ok and good
    # 绝对地址
    dh = os.path.join(dst, "deck.html")
    if os.path.exists(dh):
        import re as _re
        n = len(_re.findall(r"minis://\S+", open(dh, encoding="utf-8").read()))
        print("%-22s %-5s %d 处" % ("绝对地址残留", "OK" if n == 0 else "FAIL", n))
        ok = ok and n == 0
    # 视频可解
    vp = os.path.join(dst, "deck.mp4")
    if os.path.exists(vp):
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "default=nw=1:nk=1", vp],
                           capture_output=True, text=True)
        dur = r.stdout.strip()
        good = bool(dur) and float(dur or 0) > 5
        print("%-22s %-5s %s 秒" % ("deck.mp4 可解", "OK" if good else "FAIL", dur or "解不开"))
        ok = ok and good
    print("-" * 62)
    print("判定 %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", default="", help="指定一个 deck 目录；不给就自动扫 deck* 取各自最新的")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    ap.add_argument("--verify", help="只校验已存在的包，不重新打包")
    a = ap.parse_args()

    if a.verify:
        return verify(a.verify)

    stamp = time.strftime("%Y%m%d")
    dst = os.path.join(a.out, "demo-" + stamp)
    os.makedirs(dst, exist_ok=True)

    # 🔴 打包暴露的真问题：没有哪一个目录是齐的
    #    （deckG 有 mp4/审片图但没讲稿；deckH 有讲稿但没 mp4/审片图）
    #    ⇒ 改成“跨目录各取最新”，打出来的包才是完整的一份。
    import glob as _g
    def newest(fname):
        cands = []
        if a.deck:
            cands = [os.path.join(a.deck, fname)]
        else:
            cands = _g.glob("/var/minis/attachments/deck*/" + fname)
        cands = [c for c in cands if os.path.exists(c)]
        return max(cands, key=os.path.getmtime) if cands else None

    files = []
    for name in ("deck.mp4", "deck.html", "script.md", "review.png"):
        src = newest(name)
        if src:
            shutil.copy(src, os.path.join(dst, name))
            files.append({"file": name, "bytes": os.path.getsize(src), "sha256": sha(src),
                          "from": src})
            print("  + %-22s %8.1f KB  %s  ← %s"
                  % (name, os.path.getsize(src) / 1024, files[-1]["sha256"],
                     os.path.basename(os.path.dirname(src))))
        else:
            print("  - %-22s 全目录里都没找到" % name)

    for name, src in (
        ("kaleido.html", os.path.join(ROOT, "holo_pet_w3", "kaleido", "v12b.html")),
        ("assets-manifest.json", "/var/minis/attachments/assets/manifest.json"),
    ):
        if os.path.exists(src):
            shutil.copy(src, os.path.join(dst, name))
            files.append({"file": name, "bytes": os.path.getsize(src), "sha256": sha(src)})
            print("  + %-22s %8.1f KB  %s" % (name, os.path.getsize(src) / 1024, files[-1]["sha256"]))
        else:
            print("  - %-22s 缺（跳过）" % name)

    # 🔴 可移植性：deck.html 里的图是 minis://attachments/... 绝对地址，
    #    拷到别的机器全失效（5 页的配图全没了）。这里把引用到的图一并拷进 media/ 并改相对路径。
    dh = os.path.join(dst, "deck.html")
    if os.path.exists(dh):
        import re as _re
        html = open(dh, encoding="utf-8").read()
        refs = sorted(set(_re.findall(r"minis://attachments/([^\"')\s]+)", html)))
        media = os.path.join(dst, "media")
        os.makedirs(media, exist_ok=True)
        moved = 0
        for rel in refs:
            src = os.path.join("/var/minis/attachments", rel)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(media, os.path.basename(rel)))
                html = html.replace("minis://attachments/" + rel, "media/" + os.path.basename(rel))
                moved += 1
        open(dh, "w", encoding="utf-8").write(html)
        # 🔴 校验抓到的真 bug：deck.html 的指纹是在"相对化之前"算的，
        #    改完文件就与记录不一致（校验一跑就报"被改过"）。
        #    这里在改写后重算一次，覆盖原记录。
        for f0 in files:
            if f0.get("file") == "deck.html":
                f0["bytes"] = os.path.getsize(dh)
                f0["sha256"] = sha(dh)
                print("  ~ deck.html 指纹已按改写后的内容重算")
        if refs:
            print("  ~ 相对化 %d 张配图 → media/（原引用 %d 处）" % (moved, len(refs)))
        files.append({"file": "media/", "bytes": sum(os.path.getsize(os.path.join(media, f))
                      for f in os.listdir(media)) if os.path.isdir(media) else 0,
                      "sha256": "(%d 张配图)" % moved})

    # 装置命名统一为 kaleido.html（控制台链接的就是它）
    for old, new in (("kaleido-v12b.html", "kaleido.html"),):
        o = os.path.join(dst, old)
        if os.path.exists(o) and not os.path.exists(os.path.join(dst, new)):
            os.rename(o, new)

    # 单文件版：把 media/ 里的图 base64 内联，产出 deck-single.html（发微信/邮件直接发一个文件）
    dh2 = os.path.join(dst, "deck.html")
    if os.path.exists(dh2):
        try:
            import importlib.util as _iu
            sp = _iu.spec_from_file_location("sf", os.path.join(ROOT, "tools", "single_file.py"))
            sf = _iu.module_from_spec(sp); sp.loader.exec_module(sf)
            out_single = os.path.join(dst, "deck-single.html")
            r = sf.inline(dh2, out_single)
            files.append({"file": "deck-single.html", "bytes": r["bytes"],
                          "sha256": sha(out_single)})
            print("  + deck-single.html        %.1f MB  %s  （内联 %d 张图）"
                  % (r["bytes"] / 1048576, sha(out_single), len(r["inlined"])))
        except Exception as exc:                                  # noqa: BLE001
            print("  ! 单文件版生成失败：%s: %s" % (type(exc).__name__, exc))

    # 统一入口 + 双击启动脚本（给非技术场景用）
    open(os.path.join(dst, "index.html"), "w", encoding="utf-8").write(CONSOLE)
    sh_p = os.path.join(dst, "serve.sh")
    open(sh_p, "w", encoding="utf-8").write(
        "#!/bin/sh\n# 双击或在终端执行：起本地服务，然后打开 index.html\n"
        "cd \"$(dirname \"$0\")\" && python3 -m http.server 8099 &\n"
        "sleep 1\n"
        "echo \"打开 http://127.0.0.1:8099/index.html\"\n"
        "python3 -c \"import webbrowser;webbrowser.open('http://127.0.0.1:8099/index.html')\" 2>/dev/null || true\n"
        "wait\n")
    os.chmod(sh_p, 0o755)
    open(os.path.join(dst, "serve.command"), "w", encoding="utf-8").write(
        "#!/bin/sh\ncd \"$(dirname \"$0\")\" && sh ./serve.sh\n")
    os.chmod(os.path.join(dst, "serve.command"), 0o755)

    open(os.path.join(dst, "README.md"), "w", encoding="utf-8").write(
        README.format(date=stamp, deck_parent=a.deck))
    json.dump({"date": stamp, "files": files}, open(os.path.join(dst, "pack.json"), "w",
              encoding="utf-8"), ensure_ascii=False, indent=1)
    total = sum(f["bytes"] for f in files)
    print("-" * 60)
    print("包 %s · %d 个文件 · %.1f MB" % (dst, len(files), total / 1048576))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
