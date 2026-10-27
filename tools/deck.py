#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deck —— 投影演示台：一句话 → 一套能投出去的片子（HTML + PNG + MP4）。

为什么用 HTML 而不是 Pillow 画：**本机一个中文字体都没有**（fc-list 为空），
PIL 画中文会全是方块。浏览器的 WebView 有系统字体，排版才是真的。

产出三样，按需要挑：
  deck.html   全屏演示（方向键/自动播放，AirPlay 镜像即投屏）
  slides/*.png 每页 1920×1080（可入库、可拼视频）
  deck.mp4    无声版成片（ffmpeg 交叉化合）

用法：
    python3 tools/deck.py --spec deck.json --out /var/minis/attachments/deck
"""
import argparse, glob, importlib.util, json, os, shutil, subprocess, sys

HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{title}</title>
<style>
 :root{{--ink:#0b0f16;--paper:#f7f5f0;--accent:#c8452d;}}
 *{{box-sizing:border-box;margin:0;padding:0}}
 html,body{{height:100%}}
 body{{background:var(--ink);color:var(--paper);font-family:-apple-system,"PingFang SC",system-ui,sans-serif;overflow:hidden}}
 .slide{{position:absolute;inset:0;display:none;padding:8vh 8vw;flex-direction:column;justify-content:center}}
 .slide.on{{display:flex}}
 .kicker{{font-size:1.6vh;letter-spacing:.12em;color:#9aa6b6;margin-bottom:2.2vh}}
 h1{{font-size:6.4vh;line-height:1.12;letter-spacing:-.02em;font-weight:700;max-width:78%}}
 h2{{font-size:4.2vh;line-height:1.2;letter-spacing:-.015em;max-width:82%}}
 p{{font-size:2.6vh;line-height:1.65;color:#cfd6e0;margin-top:2.4vh;max-width:62ch}}
 ul{{margin-top:2.6vh;display:flex;flex-direction:column;gap:1.6vh;max-width:64ch}}
 li{{font-size:2.5vh;line-height:1.5;color:#dfe5ee;list-style:none;padding-left:3.2vh;position:relative}}
 li:before{{content:"";position:absolute;left:0;top:1.15vh;width:1.5vh;height:.28vh;background:var(--accent)}}
 .fig{{position:absolute;right:0;bottom:0;top:0;width:42%;background-size:contain;background-repeat:no-repeat;background-position:center;opacity:.92}}  /* 🔴 2026-10-27：原来是 cover。手机长截图（比例 0.46）塞进 42% 宽 × 全高的     容器里，cover 会把高度放大到 1700+ 像素，中间裁出来只剩一条键盘——     证据图看不到证据。改成 contain：整张可见，比例不同自动留边。 */
 .num{{position:absolute;right:7vw;bottom:6vh;font-size:1.8vh;color:#7f8b9b;letter-spacing:.08em}}
 .bar{{position:absolute;left:0;bottom:0;height:.5vh;background:var(--accent);width:0;transition:width .4s}}
 /* 2026-10-27：原来只按 16:9 横屏排，竖屏时右侧图幅压住标题（截图为证）。
    竖屏改成"图在下三分一、字在上"，字号同步收一档。 */
 @media (orientation: portrait){{
   .fig{{left:0;right:0;top:auto;bottom:0;width:100%;height:34%;opacity:.9}}
   .slide{{padding:7vh 7vw 40vh}}
   h1{{font-size:9vh}} h2{{font-size:6.4vh}}
   p{{font-size:3.6vh}} li{{font-size:3.4vh}} ul{{gap:1.2vh}}
   .num{{bottom:2vh;right:6vw}}
 }}
 /* 提词条：默认隐藏，按 N 显示/隐藏。投屏时别开，彩排时开 */
 .note{{display:none;position:absolute;left:8vw;right:8vw;bottom:9vh;font-size:2.2vh;line-height:1.6;
        color:#ffe9c9;background:rgba(0,0,0,.62);padding:1.6vh 2vh;border-left:.4vh solid var(--accent)}}
 body.notes .note{{display:block}}
 /* 计时器：按 T 显示，记本页停留与被讲过的总时长 */
 /* 硬字幕：烧进画面，静音播放也能读。--burn-subs 时给 body 加 subs 类 */
 .sub{{display:none;position:absolute;left:10vw;right:10vw;bottom:4.5vh;text-align:center;
       font-size:2.6vh;line-height:1.5;color:#fff;
       text-shadow:0 2px 10px rgba(0,0,0,.9),0 0 2px #000}}
 body.subs .sub{{display:block}}
 .clock{{display:none;position:absolute;left:8vw;top:5vh;font-size:1.9vh;color:#9aa6b6;letter-spacing:.06em}}
 body.timer .clock{{display:block}}
</style></head><body>
{slides}
<div class="bar" id="bar"></div>
 <div class="clock" id="clock">00:00 · 本页 00:00</div>
<script>
const S=[...document.querySelectorAll('.slide')];let i=0;
function show(n){{i=(n+S.length)%S.length;S.forEach((s,k)=>s.classList.toggle('on',k===i));
 document.getElementById('bar').style.width=((i+1)/S.length*100)+'%';}}
addEventListener('keydown',e=>{{if(e.key==='ArrowRight'||e.key===' ')show(i+1);if(e.key==='ArrowLeft')show(i-1);}});
let t=setInterval(()=>show(i+1), 8000);
/* 提词与计时：N 切提词条，T 切计时，空格/方向键翻页 */
let t0=null, pageT=null;
function tick(){{
  const now=Date.now();
  if(t0){{ document.getElementById('clock').textContent =
    fmt((now-t0)/1000)+' · 本页 '+fmt((now-(pageT||now))/1000); }}
  requestAnimationFrame(tick);
}}
function fmt(s){{const m=Math.floor(s/60),x=Math.floor(s%60);return String(m).padStart(2,'0')+':'+String(x).padStart(2,'0');}}
addEventListener('keydown',e=>{{
  if(e.key==='n'||e.key==='N')document.body.classList.toggle('notes');
  if(e.key==='t'||e.key==='T'){{document.body.classList.toggle('timer');t0=t0||Date.now();pageT=Date.now();}}
}});
const _show=show; show=function(n){{_show(n);pageT=Date.now();}};
tick();
addEventListener('click',()=>{{clearInterval(t);show(i+1);}});
show(0);
</script></body></html>"""


def slide_html(s, idx, total):
    fig = ""
    if s.get("image"):
        fig = '<div class="fig" style="background-image:url(%s)"></div>' % s["image"]
    body = ""
    if s.get("body"):
        body = "<p>%s</p>" % s["body"]
    if s.get("bullets"):
        body += "<ul>" + "".join("<li>%s</li>" % b for b in s["bullets"]) + "</ul>"
    head = "<h1>%s</h1>" % s["title"] if idx == 0 else "<h2>%s</h2>" % s["title"]
    kicker = '<div class="kicker">%s</div>' % s["kicker"] if s.get("kicker") else ""
    note = ('<div class="note">%s</div>' % s["narration"]) if s.get("narration") else ""
    sub = ('<div class="sub">%s</div>' % s["narration"]) if s.get("narration") else ""
    return ('<section class="slide" data-note="%s">%s%s%s%s%s%s<div class="num">%02d / %02d</div></section>'
            % ((s.get("narration") or "").replace('"', "&quot;"), fig, kicker, head, body, note, sub, idx + 1, total))


def build(spec, out, burn=False):
    os.makedirs(out, exist_ok=True)
    slides = spec["slides"]
    html = HTML.format(title=spec.get("title", "GBT"),
                       slides="\n".join(slide_html(s, i, len(slides))
                                        for i, s in enumerate(slides)))
    if burn:
        html = html.replace("<body>", '<body class="subs">')
    p = os.path.join(out, "deck.html")
    open(p, "w", encoding="utf-8").write(html)
    return p


WRITER_SYS = """你把一个主题写成演示片的 JSON。只输出 JSON，不要解释、不要 markdown 代码块。
结构：{"title":"片名","slides":[{"title":"页标题","kicker":"01 小标题","bullets":["要点一","要点二","要点三"],"narration":"一句口播"}]}
规则：5 页；每页标题不超过 14 字；每条要点不超过 22 字；口播一句话不超过 40 字；不要感叹号；不吹能力。"""


def write_slides(topic, writer="a19"):
    """按主题生成 slides。writer=a19 用她的权重（诚实：不在就报错）；deepseek 是第三方起草，会标注。"""
    import urllib.request
    prompt = "主题：" + topic
    if writer == "a19":
        spec = importlib.util.spec_from_file_location("c", os.path.join(os.path.dirname(os.path.abspath(__file__)), "a19_ctl.py"))
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        if m.status_dict().get("container") != "UP":
            raise SystemExit("A19 不在（:1234 无监听）—— 不拿第三方模型冒充她写稿。要第三方起草请显式加 --writer deepseek")
        r = m.chat_dict([{"role": "system", "content": WRITER_SYS},
                         {"role": "user", "content": prompt}], 900, 0.6)
        txt = r.get("answer") or ""
    else:
        key = os.environ.get("DEEPSEEK_API_KEY") or ""
        if not key:
            raise SystemExit("没有 DEEPSEEK_API_KEY")
        body = json.dumps({"model": "deepseek-flash", "messages": [
            {"role": "system", "content": WRITER_SYS},
            {"role": "user", "content": prompt}], "max_tokens": 1200, "effort": "low"}).encode()
        req = urllib.request.Request("https://api.deepseek.com/v1/chat/completions", data=body,
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        d = json.loads(urllib.request.urlopen(req, timeout=120).read())
        txt = d["choices"][0]["message"].get("content") or ""
        print("（稿子由第三方模型起草，非她的权重）")
    i, j = txt.find("{"), txt.rfind("}")
    if i < 0 or j < 0:
        raise SystemExit("没拿到合法 JSON：" + txt[:200])
    return json.loads(txt[i:j + 1])


BAD_NAME = ("screenshot", "截图", "crop", "_try_", "_cand", "_src", "_dc", "_rf", "_bf", "mock")


def pick_images(folder, min_w=500, portrait=(0.55, 0.98), landscape=(1.15, 2.3), min_kb=120):
    """只在**你整理过的目录**里挑：必须是 <folder>/assets/ 下的，或文件名以 deck- 开头。

    🔴 2026-10-27 的教训：上一版只按"排除截图"过滤，结果把用户相册里的私人照片（船上一张）
    配到了封面。文件名规则判不了"相关"，只能判"格式"。所以改成**必须显式整理**：
    没整理过的目录，宁可**不配图**，也不乱抓。
    """
    """挑能上投屏的素材：排除截图、缩略、调试中间件，以及长宽比不对的画。

    为什么要有这条：上一次自动配图把一张抖音截图放到了封面上。
    不是排版问题，是素材没分类 —— 这里补的是分类规则，不是修图。
    """
    from PIL import Image as _I
    ok = []
    roots = [os.path.join(folder, "assets")] if os.path.isdir(os.path.join(folder, "assets")) else []
    cands = []
    for r in roots:
        cands += sorted(glob.glob(os.path.join(r, "*")))
    cands += sorted(glob.glob(os.path.join(folder, "deck-*")))
    for f in cands:
        n = os.path.basename(f).lower()
        if not n.endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        if any(b in n for b in BAD_NAME):
            continue
        try:
            if os.path.getsize(f) < min_kb * 1024:
                continue
            w, h = _I.open(f).size
        except Exception:                                         # noqa: BLE001
            continue
        if w < min_w:
            continue
        r = w / max(h, 1)
        # 右侧图幅是竖的（约 806×1080，比例 0.75）⇒ 竖图正好贴合；横图也能用但要够宽
        if not (portrait[0] <= r <= portrait[1] or landscape[0] <= r <= landscape[1]):
            continue
        ok.append(f)
    return ok


def load_manifest(folder):
    p = os.path.join(folder, "assets", "manifest.json")
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:                                         # noqa: BLE001
            return []
    return []


def write_script(spec, out_md):
    """按片子生成讲稿：开场/逐页口播/收尾/固定演出说明。全是确定性的，不再叫模型。"""
    L = []
    L.append("# 演示讲稿 · %s\n" % spec.get("title", ""))
    L.append("> 每页 40–60 秒，全程 4–5 分钟。一条铁律：**不吹能力，只报读数；做不成就说做不成。**\n")
    L.append("## 开场（30 秒，站定再说）\n")
    L.append("> 「这不是云端产品。这几分钟讲她能干什么，讲完你随便问——问到我答不上来，我就说答不上来。」\n")
    L.append("**停顿两秒。** 后面所有可信度都建立在这句话上。\n")
    for i, s in enumerate(spec.get("slides") or [], 1):
        L.append("\n## 第 %d 页 · %s" % (i, s.get("title", "")))
        if s.get("kicker"):
            L.append("`%s`\n" % s["kicker"])
        for b in (s.get("bullets") or []):
            L.append("- 讲这个：%s" % b)
        if s.get("body"):
            L.append("- 讲这个：%s" % s["body"])
        if s.get("narration"):
            L.append("\n**口播**：%s" % s["narration"])
    L.append("\n## 收尾（30 秒内，不要拖）\n")
    L.append("> 「不吹能力，只报读数。今天能做到的我列了读数，做不到的我列了原因。\n> 有兴趣可以现场跑一条给你看——成或不成，当场见。」\n")
    L.append("## 现场要演示就这五条（时间不够只跑前两条）\n")
    L.append("| 想展示 | 跑什么 | 耗时 |\n|---|---|---|")
    L.append("| 整体状态 | `gbt status` | 1 秒 |")
    L.append("| 判据 | `gbt gate <图>` | 2 秒 |")
    L.append("| 修图 | `gbt fix <图> --declutter --reframe` | 40–70 秒 |")
    L.append("| 出片 | `gbt video K1 K2 K3 --out x.mp4` | 3–5 分钟 |")
    L.append("| 演示台 | 打开 deck.html 全屏 | 即时 |\n")
    L.append("## 三句不要说\n")
    L.append("1. 不说「AI 会思考」——说她按判据判断。")
    L.append("2. 不说「完全自主」——说卡住会停下来报错。")
    L.append("3. 不说「本地就能出照片级图」——现在做不到，做到了我再说。\n")
    L.append("## 答不上来时\n")
    L.append("> 「这个我不知道，我记下来，回去查。」\n")
    L.append("不要说「应该可以」「理论上支持」「下次一定」——这三句一出口，前面四分钟白讲。")
    open(out_md, "w", encoding="utf-8").write("\n".join(L))
    return out_md


def narrate_audio(spec, workdir="/tmp/decktts"):
    """逐页生成中文旁白音频，返回 (concat_wav, [每页时长])。

    为什么用 espeak 而不是美嘉：AVSpeechSynthesizer 只能"播"，不能导出文件（CLI 没有 --out）。
    所以成片里的旁白用 espeak（机械但可落盘），现场讲仍用美嘉。
    这条区别必须在文档里写明，不许混。
    """
    import wave
    os.makedirs(workdir, exist_ok=True)
    wavs, durs = [], []
    for i, sl in enumerate(spec.get("slides") or []):
        text = sl.get("narration") or sl.get("body") or ""
        if not text:
            text = sl.get("title") or ""
        w = os.path.join(workdir, "n%02d.wav" % i)
        subprocess.run(["espeak", "-v", "zh", "-s", "155", "-p", "55", "-w", w, text],
                       capture_output=True)
        if not os.path.exists(w):
            return None, []
        try:
            with wave.open(w, "rb") as fh:
                d = fh.getnframes() / float(fh.getframerate())
        except Exception:                                         # noqa: BLE001
            d = 3.0
        wavs.append(w)
        durs.append(round(max(3.0, d + 0.9), 2))
    if not wavs:
        return None, []
    # 串成一轨：不用 concat demuxer（实测在这台机器上打不开绝对路径文件），
    # 改成把每个 wav 当独立输入，用 filter 的 concat 拼。
    out = os.path.join(workdir, "narration.wav")
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for w in wavs:
        cmd += ["-i", w]
    fc = "".join("[%d:a]" % i for i in range(len(wavs))) + "concat=n=%d:v=0:a=1[out]" % len(wavs)
    cmd += ["-filter_complex", fc, "-map", "[out]", "-ar", "44100", "-ac", "1", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(out):
        print("旁白拼接失败：%s" % (r.stderr or "")[-200:])
        return None, []
    return out, durs


def review_sheet(mp4, out_png, n=3):
    """抽 n 帧拼成一张审片图 —— 这是**人**要看的那一眼。

    为什么必须有人这一步：验收件能查"有没有图"，查不出"图配得对不对"。
    封面配一张不相干的照片，命中率照样 100%。
    实现用 PIL 拼（ffmpeg 的 hstack 滤镜串容易写错，而且这里不需要视频流）。
    """
    from PIL import Image
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", mp4], capture_output=True, text=True).stdout.strip()
    try:
        dur = float(d)
    except Exception:                                             # noqa: BLE001
        return None
    frames = []
    for i in range(n):
        t = max(0.2, dur * (0.1 + 0.8 * i / max(n - 1, 1)))
        f = "/tmp/rev_%d.png" % i
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", mp4,
                        "-frames:v", "1", f], check=False)
        if os.path.exists(f):
            frames.append(Image.open(f).convert("RGB"))
    if not frames:
        return None
    w = 640
    scaled = [im.resize((w, int(im.size[1] * w / im.size[0])), Image.LANCZOS) for im in frames]
    H = scaled[0].size[1]
    canvas = Image.new("RGB", (w * len(scaled) + 8 * (len(scaled) - 1), H), (8, 10, 14))
    x = 0
    for im in scaled:
        canvas.paste(im, (x, 0)); x += w + 8
    canvas.save(out_png, "PNG")
    return out_png


def capture(slides, html_path, workdir="/tmp/deckslides", size=(1920, 1080)):
    """逐页调用浏览器截图（1920x1080）。没有字体问题，因为渲的是真浏览器。"""
    import time
    os.makedirs(workdir, exist_ok=True)
    # 🔴 2026-10-27 实锤 bug：原来硬编码 attachments/deck/deck.html，
    #    结果 --out 到别的目录时，截图抓的是上一次的旧页面（字幕/配图全都没进去）。
    rel = os.path.relpath(html_path, "/var/minis")
    url = "minis://" + rel.replace(os.sep, "/")
    subprocess.run(["minis-browser-use", "set_viewport",
                    "--width", str(size[0]), "--height", str(size[1])],
                   capture_output=True)
    subprocess.run(["minis-browser-use", "navigate", "--url", url], capture_output=True)
    outs = []
    for i in range(slides):
        subprocess.run(["minis-browser-use", "execute_js", "--script",
                        "document.querySelectorAll('.slide').forEach((s,k)=>s.classList.toggle('on',k===%d));'ok'" % i],
                       capture_output=True)
        time.sleep(0.5)
        r = subprocess.run(["minis-browser-use", "screenshot"], capture_output=True, text=True)
        try:
            path = json.loads(r.stdout)["data"]["image_path"]
        except Exception:                                         # noqa: BLE001
            continue
        dst = os.path.join(workdir, "s%02d.png" % i)
        shutil.copy(path, dst)
        outs.append(dst)
    return outs


def to_mp4(pngs, out, per=3.2, fade=0.35, size="1920x1080", durs=None, audio=None):
    if not pngs:
        return None
    durs = durs or [per] * len(pngs)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for p, d in zip(pngs, durs):
        cmd += ["-loop", "1", "-t", str(d), "-i", p]
    if audio:
        cmd += ["-i", audio]
    parts = []
    for i, d in enumerate(durs):
        parts.append("[%d:v]scale=%s,setsar=1,fade=t=in:st=0:d=%.2f,fade=t=out:st=%.2f:d=%.2f,format=yuv420p[v%d]"
                     % (i, size, fade, max(d - fade, 0.1), fade, i))
    concat = "".join("[v%d]" % i for i in range(len(pngs)))
    fc = ";".join(parts) + ";%sconcat=n=%d:v=1:a=0[out]" % (concat, len(pngs))
    cmd += ["-filter_complex", fc, "-map", "[out]"]
    if audio:
        cmd += ["-map", "%d:a" % len(pngs), "-c:a", "aac", "-b:a", "128k", "-shortest"]
    cmd += ["-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec")
    ap.add_argument("--topic", help="给主题，自动写稿（默认用她的权重）")
    ap.add_argument("--writer", default="a19", choices=["a19", "deepseek"])
    ap.add_argument("--out", default="/var/minis/attachments/deck")
    ap.add_argument("--mp4", action="store_true", help="逐页截图并导出成片")
    ap.add_argument("--per", type=float, default=0, help="无声成片每页停留秒数（现场讲用，默认 3.2）")
    ap.add_argument("--portrait", action="store_true",
                    help="出竖屏成片 1080x1920（配 gbt lens 透镜投墙用）")
    ap.add_argument("--images", help="素材目录：只认 <dir>/assets/ 或 deck-* 命名的图（不整理就不配）")
    ap.add_argument("--image", action="append", default=[], help="显式指定：--image 1=path --image 3=path")
    ap.add_argument("--script", action="store_true", help="同时生成讲稿 script.md（--topic 时默认开）")
    ap.add_argument("--review", action="store_true", help="生成审片图（抽三帧拼一张），交人过目")
    ap.add_argument("--burn-subs", action="store_true", help="把旁白烧成硬字幕（静音也能读）")
    ap.add_argument("--narration-audio", action="store_true",
                    help="用 espeak 生成逐页旁白并混进成片（美嘉不能导出文件，这是唯一可落盘的）")
    ap.add_argument("--narrate", action="store_true", help="逐页朗读旁白（narration 字段）")
    a = ap.parse_args()
    if a.topic:
        spec = write_slides(a.topic, a.writer)
        print("按主题成稿：%s · %d 页" % (spec.get("title"), len(spec.get("slides") or [])))
    elif a.spec:
        spec = json.load(open(a.spec, encoding="utf-8"))
    else:
        print("要么 --spec 给 JSON，要么 --topic 给主题"); sys.exit(2)
    for kv in a.image:
        try:
            idx, path = kv.split("=", 1)
            spec["slides"][int(idx) - 1]["image"] = "minis://" + os.path.relpath(path, "/var/minis")
        except Exception:                                         # noqa: BLE001
            print("忽略无效的 --image：%s" % kv)
    if a.images:
        pool = pick_images(a.images)
        man = load_manifest(a.images)
        if man:
            used = set()
            for sl in spec.get("slides") or []:
                if sl.get("image"):
                    continue
                text = " ".join([sl.get("title",""), sl.get("kicker","")]
                                + list(sl.get("bullets") or [])) + " " + (sl.get("body") or "")
                best, score = None, 0
                for m in man:
                    hit = sum(1 for t in m.get("tags", []) if t and t in text)
                    if hit > score and m["file"] not in used:
                        best, score = m["file"], hit
                if best:
                    used.add(best)
                    sl["image"] = "minis://" + os.path.relpath(os.path.join(a.images, "assets", best), "/var/minis")
            print("按描述匹配配图 %d 页（清单 %d 条）" % (len(used), len(man)))
        if not pool:
            print("该目录没有整理过的素材（需要 assets/ 子目录或 deck-* 命名）—— 本次不配图")
        if pool:
            k = 0
            for sl in spec.get("slides") or []:
                if not sl.get("image"):
                    sl["image"] = "minis://" + os.path.relpath(pool[k % len(pool)], "/var/minis")
                    k += 1
            print("自动配图 %d 页（素材库 %d 张）" % (k, len(pool)))
    p = build(spec, a.out, burn=a.burn_subs)
    print("演示台 %s · %d 页" % (p, len(spec["slides"])))
    VW, VH = (1080, 1920) if a.portrait else (1920, 1080)
    CUE = [""]
    if a.mp4 or a.narration_audio:
        pngs = capture(len(spec["slides"]), p, size=(VW, VH))
    if a.mp4:
        durs = audio = None
        if a.narration_audio:
            audio, durs = narrate_audio(spec)
            if audio:
                print("旁白音轨 %s（espeak · zh · 机械音，不是美嘉）" % audio)
        if a.per and not audio:
            durs = [a.per] * len(pngs)      # 无声版：每页固定停留，够讲完一段
        name = "deck_portrait.mp4" if a.portrait else "deck.mp4"
        mp4 = to_mp4(pngs, os.path.join(a.out, name), durs=durs, audio=audio,
                     size="%dx%d" % (VW, VH))
        if mp4:
            if a.review:
                rv = review_sheet(mp4, os.path.join(a.out, "review.png"))
                if rv:
                    print("审片图 %s —— 请肉眼看三帧再决定要不要归档" % rv)
            # 无声版：给一张"第几秒该讲哪句"的提示表，贴在讲稿末尾
            if not a.narration_audio:
                per = a.per or 3.2
                lines = ["", "## 播放提示（无声成片 · 每页 %.1f 秒）" % per, "",
                         "| 起止 | 页 | 你要说的话 |", "|---|---|---|"]
                for i, sl in enumerate(spec.get("slides") or [], 1):
                    t0 = (i - 1) * per
                    txt = (sl.get("narration") or sl.get("body") or sl.get("title") or "")
                    lines.append("| %.0f–%.0f s | %d | %s |"
                                 % (t0, t0 + per, i, txt.replace("|", "/")[:40]))
                CUE[0] = "\n".join(lines) + "\n"      # 先存着，等讲稿写完再追加
            print("成片 %s · %.1f MB（%d 页%s）"
                  % (mp4, os.path.getsize(mp4) / 1024 / 1024, len(pngs),
                     "，含旁白" if a.narration_audio else "，无声"))
        else:
            print("截图失败，没成片（浏览器可能没在前台）")
    if a.script or a.topic:
        md = write_script(spec, os.path.join(a.out, "script.md"))
        print("讲稿 %s · %d 行" % (md, sum(1 for _ in open(md, encoding="utf-8"))))
    # 讲稿写完后，再把"播放提示"追加进去（顺序错了会被覆盖，实测踩过）
    if CUE[0]:
        md = os.path.join(a.out, "script.md")
        with open(md, "a", encoding="utf-8") as fh:
            fh.write(CUE[0])
        print("讲者提示表已追加到 script.md")
    if a.narrate:
        import time
        for i, sl in enumerate(spec["slides"], 1):
            line = sl.get("narration") or sl.get("body") or ""
            if not line:
                continue
            print("[%d] %s" % (i, line[:40]))
            subprocess.run(["apple-speak", "speak", "--voice",
                            "com.apple.voice.super-compact.zh-TW.Meijia",
                            "--rate", "0.46", "--text", line], capture_output=True)
            time.sleep(max(2.0, len(line) / 6.0))
    print("投屏：minis-open %s（方向键翻页，8 秒自动前进）" % p)
