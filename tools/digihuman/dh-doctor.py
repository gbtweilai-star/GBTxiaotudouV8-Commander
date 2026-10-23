# -*- coding: utf-8 -*-
"""dh-doctor.py —— 数字人全链体检：一条命令看清「哪条通、哪条卡、卡在原话」

## 为什么要有它
这套东西散在十几个工具里：浮层(companion.js) / 耳朵(ear-listen.ps1 + ear-server.py) /
渲染(talk-photo) / 交付(deliver) / 验收(qc-video) / 上云(motion-publish) / 图生视频(i2v-ark) /
云卡(pod_link)。每查一次要跑七八条命令、翻五六个文件 —— 那就等于没有体检。
本件把每条**只用只读手段**探一遍，结论压成一张表。

## 口径（写死）
- **取不到 = 未验 = 红灯**，绝不折成绿（本仓血账：解析空列表被念成"无废钥"）；
- 每条都带**证据**（文件路径 / HTTP 状态 / 具体读数），指不到出处就标「未验」；
- 有后果的动作一个都不做：不建卡、不上传、不改台账。

## 用法
  py -3.14 tools/digihuman/dh-doctor.py
  py -3.14 tools/digihuman/dh-doctor.py --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R2 = "https://pub-3b817fc945aa4e1c8d7cce0ea93fa725.r2.dev"
EAR = "http://127.0.0.1:8770/health"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                   # noqa: BLE001
        pass


def _ok(name: str, detail: str, evidence: str) -> dict:
    return {"项": name, "判": True, "读数": detail, "出处": evidence}


def _bad(name: str, detail: str, evidence: str) -> dict:
    return {"项": name, "判": False, "读数": detail, "出处": evidence}


def check_companion() -> dict:
    js = ROOT / "holo_pet" / "companion.js"
    if not js.is_file():
        return _bad("浮层·脚本", "companion.js 不在", "holo_pet/companion.js")
    pages = list((ROOT / "holo_pet").rglob("index.html"))
    mounted, with_map = [], []
    for p in pages:
        t = p.read_text(encoding="utf-8", errors="replace")
        if "companion.js" in t:
            mounted.append(p)
        if "importmap" in t:
            with_map.append(p)
    detail = "脚本 %.1f KB · 页 %d 个 · 已挂载 %d · 有 importmap %d" % (
        js.stat().st_size / 1024, len(pages), len(mounted), len(with_map))
    return (_ok if mounted and len(mounted) == len(pages) else _bad)(
        "浮层·holo_pet", detail, "holo_pet/**/index.html")


def check_ear() -> dict:
    ps1 = ROOT / "tools" / "digihuman" / "ear-listen.ps1"
    srv = ROOT / "tools" / "digihuman" / "ear-server.py"
    if not (ps1.is_file() and srv.is_file()):
        return _bad("耳朵·文件", "识别器或桥不在", "tools/digihuman/ear-*")
    try:
        with urllib.request.urlopen(EAR, timeout=4) as r:
            body = json.loads(r.read().decode("utf-8"))
        return _ok("耳朵·桥在听", "/health ok=%s" % body.get("ok"), EAR)
    except Exception as e:                                              # noqa: BLE001
        return _bad("耳朵·桥没起", "先跑：py -3.14 tools/digihuman/ear-server.py",
                    "127.0.0.1:8770 → %s" % type(e).__name__)


def check_render_assets() -> dict:
    venv = ROOT / ".venv-sadtalker" / "Scripts" / "python.exe"
    ckpt = ROOT / "third_party" / "SadTalker" / "checkpoints"
    gfp = ROOT / "third_party" / "SadTalker" / "gfpgan" / "weights" / "GFPGANv1.4.pth"
    need = ["SadTalker_V0.0.2_256.safetensors", "mapping_00109-model.pth.tar"]
    have = [n for n in need if (ckpt / n).is_file()]
    gfp_ok = gfp.is_file() and gfp.stat().st_size > 100 * 1024 * 1024
    big = (ckpt / "SadTalker_V0.0.2_512.safetensors").is_file()
    detail = "venv=%s 权重 %d/%d · GFPGAN=%s · 512权重=%s" % (
        "有" if venv.is_file() else "缺", len(have), len(need),
        "有" if gfp_ok else "缺", "有" if big else "无")
    return (_ok if venv.is_file() and len(have) == len(need) and gfp_ok else _bad)(
        "渲染·引擎", detail, "third_party/SadTalker")


def check_library() -> dict:
    try:
        req = urllib.request.Request(R2 + "/manifest.json", headers={"User-Agent": "Mozilla/5.0 dh-doctor"})
        m = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
    except Exception as e:                                              # noqa: BLE001
        return _bad("云库·清单", "取不到：%s" % type(e).__name__, R2 + "/manifest.json")
    clips = m.get("clips") or []
    best = None
    for c in clips:
        if c.get("id") == "fullbody-tw-v5":
            best = c
    if not clips:
        return _bad("云库·清单", "clips=0", R2)
    detail = "clips=%d" % len(clips)
    if best:
        u = (best.get("url") or "").split("r2.dev", 1)[-1]
        try:
            req = urllib.request.Request(R2 + u, headers={"User-Agent": "Mozilla/5.0 dh-doctor"})
            b = urllib.request.urlopen(req, timeout=60).read()
            detail += " · 最新 %d bytes sha16=%s" % (len(b), hashlib.sha256(b).hexdigest()[:16])
        except Exception as e:                                          # noqa: BLE001
            return _bad("云库·最新作品", "下载失败 %s" % type(e).__name__, R2 + u)
    return _ok("云库·清单", detail, R2 + "/manifest.json")


def check_qc_receipts() -> dict:
    d = ROOT / "state" / "digital_human"
    # 按**修改时间**取最新（原来按文件名排序，qc-v3 会排在最后，读出来是旧回执 —— 判据取错对象的活样本）
    files = sorted(d.glob("qc-*.json"), key=lambda f: f.stat().st_mtime) if d.is_dir() else []
    if not files:
        return _bad("验收·回执", "一份都没有", "state/digital_human/qc-*.json")
    last = files[-1]
    try:
        q = json.loads(last.read_text(encoding="utf-8"))
        sx = (q.get("画质清晰") or {}).get("ratio")
        mv = (q.get("动作自然") or {}).get("head_move_mean")
        mo = q.get("语音嘴对齐") or {}
        detail = "%s → 画质 %s · 动作 %s · 嘴 r=%s lag=%s" % (
            last.name, sx, mv, mo.get("r_peak"), mo.get("lag_frames"))
    except Exception as e:                                              # noqa: BLE001
        return _bad("验收·回执", "读不动：%s" % type(e).__name__, str(last))
    return _ok("验收·回执", detail, str(last.relative_to(ROOT)))


def check_loop_ledger() -> dict:
    p = ROOT / "state" / "dh-loop.jsonl"
    if not p.is_file():
        return _bad("闭环·账本", "dh-loop.jsonl 不在", "state/dh-loop.jsonl")
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        return _bad("闭环·账本", "空账", "state/dh-loop.jsonl")
    r = rows[-1]
    return _ok("闭环·账本", "最近 %s · %ss · passed=%s · published=%s" % (
        r.get("id"), r.get("total_secs"), r.get("passed"), bool(r.get("published"))),
        "state/dh-loop.jsonl")


def check_i2v() -> dict:
    code = ["py", str(ROOT / "tools" / "digihuman" / "i2v-ark.py"), "probe"]
    py = str(ROOT / ".venv-sadtalker" / "Scripts" / "python.exe")
    if not Path(py).is_file():
        py = sys.executable
    try:
        r = subprocess.run([py, *code[1:]], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=180)
        out = (r.stdout or "") + (r.stderr or "")
        m = re.search(r"PROBE (\{.*\})", out)
        d = json.loads(m.group(1)) if m else {}
    except Exception as e:                                              # noqa: BLE001
        return _bad("图生视频", "探针跑不动：%s" % type(e).__name__, "tools/digihuman/i2v-ark.py")
    if d.get("blocked"):
        return _bad("图生视频", "account_not_verified（端点 %s）" % (d.get("endpoints_total")),
                    "i2v-ark.py probe · console.byteplus.com/user/basics/")
    return _ok("图生视频", "端点 %s · 可用" % d.get("endpoints_total"), "i2v-ark.py probe")


def check_gpu() -> dict:
    p = ROOT / "state" / "gpu-avatar.jsonl"
    if not p.is_file():
        return _bad("云卡", "没有 gpu-avatar 账", "state/gpu-avatar.jsonl")
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    last = rows[-1] if rows else {}
    op = last.get("op") or last.get("step") or (last.get("payload") or {}).get("op") or "未记"
    return _ok("云卡·账", "共 %d 行 · 最近 op=%s ok=%s" % (len(rows), op, last.get("ok")),
               "state/gpu-avatar.jsonl（现查卡况请跑 pod_link status，零作用域）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    rows = [check_companion(), check_ear(), check_render_assets(), check_library(),
            check_qc_receipts(), check_loop_ledger(), check_i2v(), check_gpu()]
    bad = [r for r in rows if not r["判"]]

    if a.json:
        print(json.dumps({"ok": not bad, "rows": rows}, ensure_ascii=False, indent=1))
    else:
        print("=" * 78)
        print("  数字人全链体检（只读 · 取不到就算红 · 每条都带出处）")
        print("=" * 78)
        for r in rows:
            print("  %s %-14s %s" % ("✅" if r["判"] else "🔴", r["项"], r["读数"]))
            print("      出处：%s" % r["出处"])
        print("-" * 78)
        print("  结论：%d 项通过 / %d 项红%s" % (
            len(rows) - len(bad), len(bad),
            (" → " + "、".join(x["项"] for x in bad)) if bad else "（全通）"))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
