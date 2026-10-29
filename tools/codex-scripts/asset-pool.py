#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模块 03 · asset-pool（素材池）—— 插件云侧素材登记与取回

## 它凭什么算"已验"
**只认"真往返"**：`put` 上传后**必须再拉回来逐字节比对 sha256**，一致才写索引；
不一致就**报错并不写索引**（fail-closed）。**不拿"写了个 index.json"冒充"已验"**。

## 云侧键（与 deploy-panel 的编号表同一命名空间）
    pipeline/assets/<kind>/<name>     素材本体（kind 必须在白名单里，不许乱分类）
    pipeline/assets/index.json        清单：{kind: {name: {bytes, sha256, at, src}}}

## 老实说三条局限（写在代码里，不藏）
  ① `index.json` 是**读-改-写**，R2 没有 compare-and-set ⇒ 两个进程同时 put **可能丢一条索引**
     （本体不会丢，只是清单少一行）。真要原子要 Queues/DO —— 那是发布动作，须主人点头。
  ② `put` **不删本地**（非破坏）。把本地大件真正搬走是 `vault-spill.py` 的事（它默认 --dry-run）。
  ③ 本工具**不部署云函数**，只读写 R2 里的对象。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
DP_PATH = ROOT / "tools" / "codex-scripts" / "deploy-panel.py"
PREFIX = "pipeline"
KINDS = ("image", "audio", "bgm", "font", "video", "model", "texture")   # 白名单：不许临时造类别
VERIFY_DIR = ROOT / "state" / "_asset_verify"

_DP = None


def _dp():
    """复用 deploy-panel 的云读写与本地替身云机制 —— **只有一份实现，三处不漂移**。"""
    global _DP
    if _DP is None:
        spec = importlib.util.spec_from_file_location("_dp_mod", DP_PATH)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _DP = m
    return _DP


def _cloud():
    dp = _dp()
    return dp, dp._load_ra()


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _bad_name(name: str) -> str | None:
    if not name or "/" in name or "\\" in name or name in (".", "..") or name.startswith("."):
        return "名字不合法（不许带路径分隔符 / 不许以点开头）：%r" % name
    return None


def _index_read(ra) -> dict:
    tmp = ROOT / "state" / "_asset_index.json"
    ok, _ = ra._get("%s/assets/index.json" % PREFIX, tmp)
    if not ok:
        return {}
    try:
        d = json.loads(tmp.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _index_write(ra, idx: dict) -> tuple[bool, str]:
    tmp = ROOT / "state" / "_asset_index_put.json"
    tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    return ra._put(tmp, "%s/assets/index.json" % PREFIX)


def cmd_put(a) -> int:
    src = pathlib.Path(a.local)
    if not src.is_file():
        print(json.dumps({"ok": False, "why": "本地文件不存在", "path": str(src)}, ensure_ascii=False))
        return 2
    if a.kind not in KINDS:
        print(json.dumps({"ok": False, "why": "kind 不在白名单（不许乱分类）",
                          "你给的": a.kind, "白名单": list(KINDS)}, ensure_ascii=False))
        return 2
    name = a.name or src.name
    bad = _bad_name(name)
    if bad:
        print(json.dumps({"ok": False, "why": bad}, ensure_ascii=False))
        return 2

    dp, ra = _cloud()
    sha = sha256_file(src)
    nbytes = src.stat().st_size
    key = "%s/assets/%s/%s" % (PREFIX, a.kind, name)

    up_ok, up_tail = ra._put(src, key)
    if not up_ok:
        print(json.dumps({"ok": False, "why": "上传失败", "键": key, "tail": up_tail},
                         ensure_ascii=False))
        return 3

 # 真往返：拉回来逐字节比对，一致才算数
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    back = VERIFY_DIR / name
    down_ok, down_tail = ra._get(key, back)
    if not down_ok:
        print(json.dumps({"ok": False, "why": "**往返失败**：拉不回来 ⇒ 不写索引",
                          "键": key, "tail": down_tail}, ensure_ascii=False))
        return 4
    back_sha = sha256_file(back)
    back_bytes = back.stat().st_size
    if back_sha != sha or back_bytes != nbytes:
        print(json.dumps({"ok": False, "why": "**往返不符** ⇒ 不写索引（fail-closed）",
                          "本地": {"bytes": nbytes, "sha256": sha},
                          "拉回": {"bytes": back_bytes, "sha256": back_sha}},
                         ensure_ascii=False, indent=1))
        return 5

    idx = _index_read(ra)
    idx.setdefault(a.kind, {})[name] = {
        "bytes": nbytes, "sha256": sha, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "src": str(src.relative_to(ROOT)) if src.is_relative_to(ROOT) else src.name,
    }
    iok, itail = _index_write(ra, idx)
    back.unlink(missing_ok=True)
    print(json.dumps({"ok": True, "键": key, "kind": a.kind, "name": name,
                      "bytes": nbytes, "sha256_前16": sha[:16],
                      "往返": "✅ 拉回逐字节一致", "已进索引": iok,
                      "索引键": "%s/assets/index.json" % PREFIX,
                      "本地替身云": bool(dp.LOCAL_CLOUD), "tail": None if iok else itail},
                     ensure_ascii=False, indent=1))
    return 0 if iok else 6


def cmd_get(a) -> int:
    bad = _bad_name(a.name)
    if bad:
        print(json.dumps({"ok": False, "why": bad}, ensure_ascii=False))
        return 2
    _, ra = _cloud()
    idx = _index_read(ra)
    ent = (idx.get(a.kind) or {}).get(a.name)
    if not ent:
        print(json.dumps({"ok": False, "why": "索引里没有这条 ⇒ 拒（fail-closed，不猜 sha）",
                          "kind": a.kind, "name": a.name,
                          "索引里有的": {k: sorted(v) for k, v in idx.items()}},
                         ensure_ascii=False, indent=1))
        return 2
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ok, tail = ra._get("%s/assets/%s/%s" % (PREFIX, a.kind, a.name), out)
    if not ok:
        print(json.dumps({"ok": False, "why": "下载失败", "tail": tail}, ensure_ascii=False))
        return 3
    got = sha256_file(out)
    same = got == ent.get("sha256")
    print(json.dumps({"ok": same, "落盘": str(out), "bytes": out.stat().st_size,
                      "验": ("✅ 与索引 sha 一致" if same else "✗ **与索引 sha 不符**"),
                      "索引sha": ent.get("sha256"), "实得sha": got},
                     ensure_ascii=False, indent=1))
    return 0 if same else 5


def cmd_ls(a) -> int:
    _, ra = _cloud()
    idx = _index_read(ra)
    rows, tot = [], 0
    for kind in sorted(idx):
        for name in sorted(idx[kind]):
            e = idx[kind][name]
            tot += int(e.get("bytes") or 0)
            rows.append({"kind": kind, "name": name, "bytes": e.get("bytes"),
                         "sha256_前16": str(e.get("sha256"))[:16], "at": e.get("at")})
    print(json.dumps({"素材": rows,
                      "合计": {"条数": len(rows), "总字节": tot,
                             "按类": {k: len(v) for k, v in sorted(idx.items())}},
                      "索引键": "%s/assets/index.json" % PREFIX},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_verify(a) -> int:
    """把索引里**每条**都拉回来比对 sha —— 这才是"素材池能用"的真判据。"""
    _, ra = _cloud()
    idx = _index_read(ra)
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    bad, rows = 0, []
    for kind in sorted(idx):
        for name in sorted(idx[kind]):
            e = idx[kind][name]
            back = VERIFY_DIR / ("v_%s_%s" % (kind, name))
            ok, tail = ra._get("%s/assets/%s/%s" % (PREFIX, kind, name), back)
            if not ok:
                bad += 1
                rows.append({"kind": kind, "name": name, "结果": "✗ 拉不回来", "tail": tail})
                continue
            same = sha256_file(back) == e.get("sha256")
            bad += 0 if same else 1
            rows.append({"kind": kind, "name": name,
                         "结果": "✅ 一致" if same else "✗ **sha 不符**",
                         "bytes": back.stat().st_size})
            back.unlink(missing_ok=True)
    print(json.dumps({"逐条复核": rows, "合计": {"条数": len(rows), "不符": bad},
                      "判据": "全部拉回逐字节一致才算素材池可用"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 5


def cmd_selftest(a) -> int:
    """真身自检：**1 正 + 4 负**，跑在本地替身云上（不碰真云，走的却是同一段代码）。"""
    dp = _dp()
    keep = dp.LOCAL_CLOUD
    lines, bad = [], 0

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    with tempfile.TemporaryDirectory() as td:
        src = pathlib.Path(td) / "real.bin"
        src.write_bytes(b"GBT-asset-pool-selftest" * 4096)      # 真内容，~90KB
        dp.LOCAL_CLOUD = str(pathlib.Path(td) / "cloud")

        class P:  # 正控：正常 put
            local, kind, name = str(src), "image", "selftest.bin"
        rc1 = cmd_put(P())
        _, ra = _cloud()
        idx = _index_read(ra)
        ent = (idx.get("image") or {}).get("selftest.bin") or {}
        ck("正控·put 往返一致并进索引", rc1 == 0 and ent.get("sha256") == sha256_file(src),
           "rc=%d · 索引 sha %s…" % (rc1, str(ent.get("sha256"))[:16]))

        class G:
            kind, name, out = "image", "selftest.bin", str(pathlib.Path(td) / "back.bin")
        rc2 = cmd_get(G())
        ck("正控·get 拉回与索引一致", rc2 == 0, "rc=%d（期望 0）" % rc2)

        # 负控①：云端本体被改坏 ⇒ get 必须报不符（验的是**校验逻辑**，不是运气）
        remote = pathlib.Path(dp.LOCAL_CLOUD) / "pipeline/assets/image/selftest.bin"
        remote.write_bytes(b"TAMPERED" * 1000)
        rc3 = cmd_get(G())
        ck("负控①·云上被改坏 ⇒ get 报不符", rc3 == 5, "rc=%d（期望 5）" % rc3)

        # 负控②：索引里没有的键 ⇒ get 必须拒（不许猜 sha）
        class G2:
            kind, name, out = "image", "不存在.bin", str(pathlib.Path(td) / "x.bin")
        rc4 = cmd_get(G2())
        ck("负控②·索引没有 ⇒ 拒单", rc4 == 2, "rc=%d（期望 2）" % rc4)

        # 负控③：本地文件不存在 ⇒ put 拒，且**不许写索引**
        before = json.dumps(_index_read(_cloud()[1]), sort_keys=True)

        class P2:
            local, kind, name = str(pathlib.Path(td) / "没有这个.bin"), "image", "x.bin"
        rc5 = cmd_put(P2())
        after = json.dumps(_index_read(_cloud()[1]), sort_keys=True)
        ck("负控③·源不存在 ⇒ 拒且索引未动", rc5 == 2 and before == after,
           "rc=%d · 索引未变=%s" % (rc5, before == after))

        # 负控④：kind 不在白名单 ⇒ 拒
        class P3:
            local, kind, name = str(src), "随便造个类", "x.bin"
        rc6 = cmd_put(P3())
        ck("负控④·kind 不在白名单 ⇒ 拒", rc6 == 2, "rc=%d（期望 2）" % rc6)

    dp.LOCAL_CLOUD = keep
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines,
                      "口径": "跑在**本地替身云**上；正控证明能通，负控证明**坏数据拦得住**"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="模块 03 · asset-pool（素材池，只认真往返）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("put")
    p.add_argument("local")
    p.add_argument("--kind", required=True)
    p.add_argument("--name", default="")
    p.set_defaults(func=cmd_put)
    g = sub.add_parser("get")
    g.add_argument("kind")
    g.add_argument("name")
    g.add_argument("--out", required=True)
    g.set_defaults(func=cmd_get)
    sub.add_parser("ls").set_defaults(func=cmd_ls)
    sub.add_parser("verify").set_defaults(func=cmd_verify)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
