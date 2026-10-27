#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ingest —— 把文件收进素材库：拷贝 + sha256 + 登记清单（deck 用）。

为什么需要：网页版录完的片子、拍的照片，落在「文件/相册」里，
不登记就没法被 deck 自动配图用上。这一步把"散件"变成"素材"。

用法：
    python3 tools/ingest.py 视频.mp4 --tags 万花筒,演示
    python3 tools/ingest.py 图1.jpg 图2.png --prefix deck- --tags 封面
    python3 tools/ingest.py --from-photos          # 从相册取最近一张
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = "/var/minis/attachments/assets"
MANIFEST = os.path.join(ASSETS, "manifest.json")


def sha256(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()[:16]


def load_manifest():
    try:
        return json.load(open(MANIFEST, encoding="utf-8"))
    except Exception:                                             # noqa: BLE001
        return []


def save_manifest(m):
    os.makedirs(ASSETS, exist_ok=True)
    json.dump(m, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def from_photos():
    try:
        d = json.loads(subprocess.run(["apple-photos", "list", "--limit", "1"],
                                      capture_output=True, text=True).stdout)
        items = d.get("data", {}).get("photos") or d.get("data", {}).get("assets") or []
        if not items:
            return None
        e = json.loads(subprocess.run(["apple-photos", "export", items[0]["id"]],
                                      capture_output=True, text=True).stdout)
        return (e.get("data") or {}).get("path")
    except Exception:                                             # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--prefix", default="deck-")
    ap.add_argument("--tags", default="")
    ap.add_argument("--desc", default="")
    ap.add_argument("--from-photos", action="store_true")
    ap.add_argument("--backfill", action="store_true", help="给缺 sha256 的旧条目补指纹")
    a = ap.parse_args()

    if a.backfill:
        man = load_manifest()
        filled = 0
        for e in man:
            p = os.path.join(ASSETS, e.get("file", ""))
            if not e.get("sha256") and os.path.exists(p):
                e["sha256"] = sha256(p)
                e["bytes"] = os.path.getsize(p)
                filled += 1
                print("  补 %-22s %s" % (e["file"], e["sha256"]))
            elif not os.path.exists(p):
                print("  缺文件 %s（清单里留着，但不补）" % e.get("file"))
        save_manifest(man)
        print("回填 %d 条 · 清单共 %d 条" % (filled, len(man)))
        return 0

    files = list(a.files)
    if a.from_photos:
        p = from_photos()
        if p:
            files.append(p)
        else:
            print("相册里没拿到（需要照片权限）")

    if not files:
        print("没有文件可入库"); return 1

    os.makedirs(ASSETS, exist_ok=True)
    man = load_manifest()
    tags = [t.strip() for t in a.tags.split(",") if t.strip()]
    n = 0
    for f in files:
        if not os.path.exists(f):
            print("跳过（不在）：%s" % f); continue
        # 🔴 入库先查重：同指纹就不再拷贝，只合并标签。
        #    起因：deck-hero 与 deck-06-1027 指纹相同（就是我复制了两次），
        #    名字不同骗得过人，sha256 骗不过。
        h0 = sha256(f)
        dup = next((m for m in man if m.get("sha256") == h0), None)
        if dup:
            merged = sorted(set(dup.get("tags") or []) | set(tags))
            dup["tags"] = merged
            if a.desc and not dup.get("desc"):
                dup["desc"] = a.desc
            save_manifest(man)
            print("已存在   %-24s（指纹相同，跳过拷贝，标签合并为：%s）"
                  % (dup["file"], ",".join(merged) or "-"))
            continue
        ext = os.path.splitext(f)[1].lower()
        # 🔴 原来用 len(man)+1 编号：合并重复后清单会变短 ⇒ 将来必然撞名（deck-06 出现两次）。
        #    现在取「已有编号最大值 + 1」，再带时分，彻底不撞。
        import re as _re
        nums = [int(m.group(1)) for x in os.listdir(ASSETS)
                if (m := _re.match(_re.escape(a.prefix) + r"(\d+)", x))]
        seq = (max(nums) + 1) if nums else 1
        name = "%s%02d-%s%s" % (a.prefix, seq, time.strftime("%m%d-%H%M"), ext)
        dst = os.path.join(ASSETS, name)
        shutil.copy(f, dst)
        h = sha256(dst)
        entry = {"file": name, "tags": tags, "desc": a.desc or os.path.basename(f),
                 "sha256": h, "bytes": os.path.getsize(dst),
                 "added": time.strftime("%Y-%m-%dT%H:%M:%S")}
        man = [m for m in man if m.get("file") != name] + [entry]
        n += 1
        print("%-26s %7.1f KB  sha %s  tags %s"
              % (name, entry["bytes"] / 1024, h, ",".join(tags) or "-"))
    save_manifest(man)
    print("清单 %s · 共 %d 条" % (MANIFEST, len(man)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
