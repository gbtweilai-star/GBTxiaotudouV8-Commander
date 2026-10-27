#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_polish —— 本地算力的正确定位：**批量精修 + 过闸 + 出片**（不含生成）。

一段跑完四件事，全程本机、零外部调用：
    ① 精修：局部对比 + 边缘感知锐化 + 分离色调（复用 polish2 的三步）
    ② 过闸：taste_gate 判定（精修前/后各一次，看有没有变好）
    ③ 留痕：每张的读数写进报告 JSON
    ④ 出片：--video 时把成品拼成带 Ken Burns 与化合的短片（2:1 遮幅）

用法：
    python3 tools/batch_polish.py --glob '/var/minis/attachments/tz_*.jpg' --out /tmp/polished
    python3 tools/batch_polish.py --glob '…' --out … --video /var/minis/attachments/reel.mp4
"""
import argparse, glob, importlib.util, json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageFilter, ImageChops, ImageEnhance

TOOLS = os.path.dirname(os.path.abspath(__file__))


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(TOOLS, name + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def metrics(p, ref_w=627):
    im = Image.open(p).convert("L")
    if im.size[0] != ref_w:
        im = im.resize((ref_w, int(im.size[1]*ref_w/im.size[0])), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float32)
    blur = np.asarray(im.filter(ImageFilter.GaussianBlur(3)), dtype=np.float32)
    return {"高频": round(float(np.abs(a-blur).mean()), 2),
            "均值": round(float(a.mean()), 1), "标准差": round(float(a.std()), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", required=True)
    ap.add_argument("--out", default="/tmp/polished")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--scale", type=float, default=1.5)
    ap.add_argument("--video")
    ap.add_argument("--reframe", action="store_true", help="先做构图修复（焦点收敛+扩画布，带自检回退）")
    ap.add_argument("--maxw", type=int, default=900, help="处理前把长边压到这个宽度（iSH 慢，必设）")
    ap.add_argument("--declutter", action="store_true", help="加一道降杂乱（压边缘密度，带自检）")
    a = ap.parse_args()

    p2 = load("polish2"); tg = load("taste_gate"); rf = load("reframe"); dc = load("declutter")
    os.makedirs(a.out, exist_ok=True)
    files = sorted(glob.glob(a.glob))[:a.limit]
    rows = []
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0]
        dst = os.path.join(a.out, base + "_fix.png")
        try:
            # iSH 上所有像素操作都要按秒算：先把长边压到 maxw，再进流水线
            _im = Image.open(f).convert("RGB")
            if _im.size[0] > a.maxw:
                _h = int(_im.size[1] * a.maxw / _im.size[0])
                _small = os.path.join(a.out, base + "_src.jpg")
                _im.resize((a.maxw, _h), Image.LANCZOS).save(_small, quality=95)
                f = _small
            b = tg.judge(f, "photo")
            m0 = metrics(f)
            # 🔴 逐步"只采纳更好"是贪心的：先降杂乱改好了，扩留白就不再"更优" ⇒ 被拒，
            #    结果丢掉了一个本来能 PASS 的组合（P1 就这么丢的）。
            #    改成：**三条路线全跑完，再整体择优** —— 原图 / 降杂乱→扩留白 / 扩留白→降杂乱。
            def _apply(cur, order):
                for _i, step in enumerate(order):
                    try:
                        if step == "bf":
                            o = os.path.join(a.out, base + "_bf%s.png" % "".join(order))
                            im2 = Image.open(cur).convert("RGB")
                            rf.boost_focus(im2).save(o, "PNG")
                            cur = o
                        elif step == "dc":
                            o = os.path.join(a.out, base + "_dc%s.png" % "".join(order))
                            im2 = Image.open(cur).convert("RGB")
                            o_im, _ = dc.declutter(im2, 12, 45, 0.75); o_im.save(o, "PNG")
                            cur = o
                        else:
                            o = os.path.join(a.out, base + "_rf%s.png" % "".join(order))
                            im2 = Image.open(cur).convert("RGB")
                            # 🔴 已经提亮过主光（bf）就**不能再压暗**：两者目标相反，
                            #    实测会把 P2 从 PASS 打回 FAIL（bf 提亮的正是 converge 要压的那块）。
                            if "bf" not in order[:_i]:
                                im2, _ = rf.converge_focus(im2)
                            im2, _v, _q = rf.pad_space(im2); im2.save(o, "PNG")
                            cur = o
                    except Exception:                             # noqa: BLE001
                        return None
                return cur

            cands = [(f, ("none",))]
            for order in (("dc", "rf"), ("rf", "dc"), ("bf", "rf"), ("bf", "dc", "rf")):
                c = _apply(f, order)
                if c:
                    cands.append((c, order))
            best = None
            for src_c, order in cands:
                tmp = os.path.join(a.out, base + "_try_%s.png" % "".join(order))
                try:
                    p2.run(src_c, tmp, a.scale, 0.22, 0.05, 0.55)
                except Exception:                                 # noqa: BLE001
                    continue
                gt = tg.judge(tmp, "photo")
                hf = metrics(tmp)["高频"]
                key = (len(gt["fails"]), -hf)
                if best is None or key < best[0]:
                    best = (key, tmp, gt, order)
            _key, dst, aft, order_won = best
            stage1 = dst
            dc_used = "dc" in order_won
            reverted = order_won == ("none",)
            m1 = metrics(dst)
            rows.append({"file": os.path.basename(f), "out": dst, "reverted": reverted, "declutter": dc_used, "order": "".join(order_won),
                         "before": {"verdict": b["verdict"], "fails": b["fails"], **m0},
                         "after": {"verdict": aft["verdict"], "fails": aft["fails"], **m1},
                         "hf_delta": round(m1["高频"] - m0["高频"], 2)})
            print("%-22s %-4s→%-4s  高频 %5.2f→%5.2f (%+0.2f)  %s余 %s"
                  % (base[:22], b["verdict"], aft["verdict"], m0["高频"], m1["高频"],
                     rows[-1]["hf_delta"], "回退 " if reverted else "      ",
                     ",".join(aft["fails"]) or "-"))
        except Exception as exc:                                  # noqa: BLE001
            print("%-22s 失败 %s: %s" % (base[:22], type(exc).__name__, str(exc)[:60]))

    ok = [r for r in rows if r["after"]["verdict"] == "PASS"]
    print("-"*74)
    saved = [r for r in rows if len(r["after"]["fails"]) < len(r["before"]["fails"])]
    rev = [r for r in rows if r.get("reverted")]
    print("批 %d 张 · 过闸 %d · 判据改善 %d · 回退 %d · 高频平均 %+.2f"
          % (len(rows), len(ok), len(saved), len(rev),
             (sum(r["hf_delta"] for r in rows)/len(rows)) if rows else 0))
    json.dump(rows, open("/tmp/batch_report.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("报告 /tmp/batch_report.json")

    if a.video and len(rows) >= 2:
        # 过闸的优先；不足 2 张就用全部精修件（闸管构图，拼片不等于交付）
        pool = (ok if len(ok) >= 2 else rows)[:6]
        make_reel([r["out"] for r in pool], a.video)


def make_reel(paths, out, w=360, h=640, fps=20, per=1.1, fade=0.4):
    """本地出片：每张 1.6s，慢推 + 交叉化合，2:1 遮幅。"""
    tmp = "/tmp/reel"
    os.makedirs(tmp, exist_ok=True)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    imgs = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        s = max(w/im.size[0], h/im.size[1])
        im = im.resize((int(im.size[0]*s+1), int(im.size[1]*s+1)), Image.LANCZOS)
        x = (im.size[0]-w)//2; y = (im.size[1]-h)//2
        imgs.append(im.crop((x, y, x+w, y+h)))
    vis = int(w/2.0); bar = (h-vis)//2
    def lb(im):
        out = Image.new("RGB", (w, h), (0,0,0))
        out.paste(im.crop((0, bar, w, bar+vis)), (0, bar)); return out
    n_per = int(per*fps); n_fade = int(fade*fps); idx = 0
    for i in range(len(imgs)):
        cur = imgs[i]; nxt = imgs[(i+1) % len(imgs)] if len(imgs) > 1 else cur
        for k in range(n_per):
            z = 1.0 + 0.06*(k/n_per)
            cw, ch = int(w/z), int(h/z)
            cx, cy = (w-cw)//2, (h-ch)//2
            fr = cur.crop((cx, cy, cx+cw, cy+ch)).resize((w, h), Image.LANCZOS)
            if k > n_per - n_fade:
                q = (k-(n_per-n_fade))/n_fade
                cw2, ch2 = int(w/(1.0+0.06)), int(h/(1.0+0.06))
                fr = Image.blend(fr, nxt.crop(((w-cw2)//2,(h-ch2)//2,(w-cw2)//2+cw2,(h-ch2)//2+ch2)).resize((w,h), Image.LANCZOS), q)
            lb(fr).save(os.path.join(tmp, "f%04d.png" % idx)); idx += 1
    subprocess.run(["ffmpeg","-y","-v","error","-framerate",str(fps),
                    "-i",os.path.join(tmp,"f%04d.png"),"-c:v","libx264",
                    "-pix_fmt","yuv420p","-crf","20","-movflags","+faststart",out], check=True)
    print("短片 %s · %.0f KB" % (out, os.path.getsize(out)/1024))


if __name__ == "__main__":
    sys.exit(main())
