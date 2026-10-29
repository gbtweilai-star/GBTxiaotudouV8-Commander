# -*- coding: utf-8 -*-
"""从回收站**按元数据**精确还原（不碰 COM，不枚举 Shell 命名空间）。

## 为什么不用 Shell.Application

`Shell.Application.NameSpace(10)` 那条路在这台机器上**两次超时**（1150 项）：
逐项 `ExtendedProperty("System.Recycle.DeletedFrom")` 极慢，`InvokeVerb()` 还会阻塞。
⇒ **回收站本来就是文件系统目录**：`C:\\$Recycle.Bin\\<SID>\\`，每删一个文件留一对

    $Ixxxxxx.<ext>   ← 元数据：8B 头 + 8B 原大小 + 8B 删除时间 + 4B 名长 + UTF-16LE 原路径
    $Rxxxxxx.<ext>   ← **原始内容**（逐字节）

⇒ 解析 `$I` 拿原路径，把 `$R` 拷回去。**零 COM、零枚举、可反复跑。**

## 用法

    py -3.14 tools/codex-scripts/restore_from_recyclebin.py --list            # 只列出
    py -3.14 tools/codex-scripts/restore_from_recyclebin.py --match <子串>     # 预览
    py -3.14 tools/codex-scripts/restore_from_recyclebin.py --match <子串> --go
"""
import argparse
import struct
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
RB = Path("C:/$Recycle.Bin")


def parse_i(p: Path) -> dict:
    """解析 `$I` 元数据。解析不出来返回 `{}`（**不猜**）。

    🔴 **首版把路径读截断了**（实测：`C:\\Users\\ADMIN\\Desktop\\GBT小土豆` 后面没了）。
    真因：**名长字段的宽度随 Windows 版本不同**（4 字节 vs 8 字节），我写死 4 字节就去解码，
    长度不够 ⇒ 路径被切在半路，还会切出半个 UTF-16 字符（`GB\\ufffd`）。
    ⇒ 现在**两种布局都试**，取"看起来完整"的那份：
       · 必须有盘符 `X:`；
       · 不能含替换字符（半个 UTF-16 的痕迹）；
       · 取更长的那个。
    这是"**判据不能写死一个平台细节**"的又一例；写死了就会得到"看着有、其实是残的"数据。
    """
    try:
        b = p.read_bytes()
    except OSError:
        return {}
    if len(b) < 28:
        return {}
    size = struct.unpack("<q", b[8:16])[0]
    ts = struct.unpack("<q", b[16:24])[0]
    best = None
    for off, width in ((24, 4), (24, 8)):
        try:
            nlen = struct.unpack("<i" if width == 4 else "<q", b[off:off + width])[0]
        except struct.error:
            continue
        if nlen <= 0:
            continue
        start = off + width
        raw = b[start:start + nlen]
        if len(raw) < 6:
            continue
        name = raw.decode("utf-16-le", errors="replace").rstrip("\x00")
        if "\ufffd" in name or len(name) < 4 or ":" not in name:
            continue
        if best is None or len(name) > len(best):
            best = name
    if not best:
        # 退一步：整块按 UTF-16 扫，从盘符开始取到第一个 \x00（**标注为兜底解析**）
        try:
            s = b[24:].decode("utf-16-le", errors="replace")
            i = s.find(":\\")
            if i >= 1:
                cand = s[i - 1:].split("\x00")[0]
                if len(cand) >= 4 and "\ufffd" not in cand:
                    best = cand
        except Exception:                                           # noqa: BLE001
            pass
    if not best:
        return {}
    return {"size": size, "name": best, "deleted_ts": ts, "i_file": str(p)}


def scan() -> list:
    """扫所有 SID 目录下的 `$I*`，返回 `[{原路径, 大小, $R 内容路径}]`。"""
    out = []
    if not RB.is_dir():
        return out
    for sid in RB.iterdir():
        if not sid.is_dir():
            continue
        try:
            entries = list(sid.iterdir())
        except OSError:
            continue
        for f in entries:
            if not f.name.startswith("$I"):
                continue
            meta = parse_i(f)
            if not meta:
                continue
            r = f.with_name("$R" + f.name[2:])
            if not r.is_file():
                continue
            out.append({"path": meta["name"], "size": r.stat().st_size,
                        "content": str(r), "ts": meta["deleted_ts"]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="从回收站按元数据精确还原")
    ap.add_argument("--list", action="store_true", help="列出回收站里能解析出来的项")
    ap.add_argument("--match", default="", help="只处理原路径含这个子串的项")
    ap.add_argument("--go", action="store_true", help="真拷回去（默认只预览）")
    a = ap.parse_args()

    items = scan()
    print("=" * 78)
    print("回收站 · 按元数据还原（不走 COM）")
    print("=" * 78)
    print("  扫到可解析项 %d 个" % len(items))
    if not items:
        print("  ⚠️ 一个都解析不出来 —— 可能回收站为空，或元数据格式与预期不符（**不猜**）")
        return 2

    if a.list and not a.match:
        for it in sorted(items, key=lambda x: x["path"]):
            print("   %10d B  %s" % (it["size"], it["path"]))
        return 0

    hit = [it for it in items if a.match.lower() in it["path"].lower()] if a.match else items
    print("-" * 78)
    print("  匹配「%s」→ %d 项" % (a.match or "（全部）", len(hit)))
    done = 0
    for it in hit:
        dst = Path(it["path"])
        exists = dst.is_file()
        note = ""
        if exists:
            # **尺寸比对**（这一条是拿教训换的）：目标已在，但**尺寸不同** ⇒ 现存那份是别的版本
            cur = dst.stat().st_size
            if cur != it["size"]:
                note = "  ← 现存 %d B，**不一致**（现存是别的版本）" % cur
            else:
                note = "  ← 现存同尺寸，跳过"
        print("   %10d B  %s%s" % (it["size"], it["path"], note))
        if not a.go:
            continue
        if exists and dst.stat().st_size == it["size"]:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        Path(it["content"]).replace(dst) if False else None
 # 用**拷贝**不用搬：回收站那份留着，万一还要再取一次
        with open(it["content"], "rb") as src, open(dst, "wb") as out:
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
        done += 1
        print("        ✅ 已还原（%d B）" % dst.stat().st_size)
    print("-" * 78)
    if a.go:
        print("  真还原 %d 项" % done)
    else:
        print("  这是**预览**。要真还原：加 `--go`")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
