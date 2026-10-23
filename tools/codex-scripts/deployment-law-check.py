# -*- coding: utf-8 -*-
"""部署法制审查 —— **只出品生产，不出品废物**（主人令 2026-10-10，逐字）

主人原话：
  「我们有我们的部署法制，不管多大的项目拆开模块化部署，一个模块部署在镜像多维度空间
    跑通闭环之后再落盘，这样用户就会看到V8是一次性部署直接生产，而不是到处涂改搞得一片混乱。
    镜像多维度空间的最大能力就是只出品生产，不出品废物。」

## 三查（都走本仓既有信号，不手搓指标）
  ① **镜像干净**：mirror_status 的 clean / dimension_vs_reality / production_drift 全空
     ⇒ 现实与镜像一致 = **没人在镜像外面涂改**
  ② **镜像体检**：mirror_scan 5/5（非空 / 无空件 / 署名 / 纪律 / 入口）
  ③ **生成代码禁入**：落盘生产的件清单 **必须都在镜像维度里**
     ⇒ 多出来的那一个 = **绕过镜像直接落盘的生成代码** ⇒ 红

## 负控（真植入）
  在两个临时目录里各放一份同样的件，再**往 reality 多塞一个** ⇒ ③ 必须点出那个多出来的。

用法: py -3.14 -X utf8 tools/codex-scripts/deployment-law-check.py [--selftest]
"""
import os
import pathlib
import subprocess
import sys
import tempfile


def _isolated_store() -> str:
    """**开机自检/测试是在隔离 store 里跑的**（进程启动前设 GBT_STORE_DIR，本仓口径）——
    那时镜像维度与生产面都是**空的临时屋**，本件**不适用**。

    🔴 2026-10-10 自纠：我第一版没处理这件事，结果接进 boot-selfcheck 后**当场报红**
       （读数「镜像 25 件 · 生产 25 件」，而那是隔离屋里的假读数）。
       本仓既有口径：**rc=3 = 不适用 ≠ 失败**（同 vrm-runtime-check 服务没起时的做法）。
    """
    sd = os.environ.get("GBT_STORE_DIR") or ""
    if not sd:
        return ""
    try:
        p = pathlib.Path(sd).resolve()
        ws = WS.resolve()
        if ws == p or ws in p.parents:
            return ""          # 还在仓里 ⇒ 当它作数
        return str(p)
    except Exception:
        return sd

WS = pathlib.Path(__file__).resolve().parents[2]
MIRROR = WS / "gbt_allinone" / "store" / "mirror_space"
FIVE = WS / "tools" / "codex-scripts" / "five-dim.py"


def _cap(kind):
    """走万能插（本仓唯一门）取能力位返回；不直连模块，免得绕过门。"""
    p = subprocess.run([sys.executable, "-X", "utf8", str(FIVE), "cap", kind],
                       capture_output=True, cwd=str(WS))
    import json
    try:
        return json.loads(p.stdout.decode("utf-8", "replace"))
    except Exception:
        return {"status": "unreadable", "raw": p.stdout.decode("utf-8", "replace")[:200]}


def _files(root: pathlib.Path):
    if not root.is_dir():
        return None
    return sorted(str(x.relative_to(root)).replace(chr(92), "/")
                  for x in root.rglob("*") if x.is_file())


def compare(dim_root, prod_root):
    """生产里**多出来的**件 = 绕过镜像落盘的生成代码。"""
    d = _files(pathlib.Path(dim_root))
    p = _files(pathlib.Path(prod_root))
    if d is None or p is None:
        return None, "目录不在（dim=%s · prod=%s）" % (dim_root, prod_root)
    return sorted(set(p) - set(d)), ""


def audit(dim_root=None, prod_root=None):
    dim_root = dim_root or (MIRROR / "dimension")
    prod_root = prod_root or (MIRROR / "reality")
    st = _cap("mirror_status").get("result") or {}
    sc = _cap("mirror_scan").get("result") or {}
    extra, err = compare(dim_root, prod_root)
    return {
        "镜像干净": bool(st.get("clean") is True)
        and not (st.get("dimension_vs_reality") or [])
        and not (st.get("production_drift") or []),
        "镜像体检通过": bool(sc.get("passed")) and sc.get("passed") == sc.get("total"),
        "体检读数": "%s/%s" % (sc.get("passed"), sc.get("total")),
        "镜像件数": len(_files(pathlib.Path(dim_root)) or []),
        "生产件数": len(_files(pathlib.Path(prod_root)) or []),
        "绕过镜像多出来的件": extra,
        "比对错误": err,
    }


def render(r):
    print("=" * 74)
    print("部署法制审查 · 只出品生产，不出品废物（主人令 2026-10-10）")
    print("=" * 74)
    print("  ① 镜像干净（现实与镜像一致，没人在外面涂改）: %s" % ("✅" if r["镜像干净"] else "❌"))
    print("  ② 镜像体检（%s）: %s" % (r["体检读数"], "✅" if r["镜像体检通过"] else "❌"))
    print("  ③ 生成代码禁入（生产里多出来的件必须为空）: %s" % ("✅" if not r["绕过镜像多出来的件"] else "❌"))
    print("     镜像 %s 件 · 生产 %s 件" % (r["镜像件数"], r["生产件数"]))
    if r["比对错误"]:
        print("     " + r["比对错误"])
    for x in (r["绕过镜像多出来的件"] or [])[:12]:
        print("     🔴 绕过镜像落盘: " + x)
    print("")


def selftest():
    ok = []
    real = audit()
    ok.append(("真件·镜像干净", real["镜像干净"], "clean"))
    ok.append(("真件·镜像体检 5/5", real["镜像体检通过"], real["体检读数"]))
    ok.append(("真件·没有绕过镜像落盘的件", not real["绕过镜像多出来的件"],
               "%d 处" % len(real["绕过镜像多出来的件"] or [])))
    # 真植入：两份同样的件放临时目录，再往 prod 多塞一个
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td) / "dim"; p = pathlib.Path(td) / "prod"
        d.mkdir(); p.mkdir()
        (d / "a.html").write_text("x", encoding="utf-8")
        (p / "a.html").write_text("x", encoding="utf-8")
        (p / "偷偷加进来的.py").write_text("print(1)", encoding="utf-8")
        extra, _ = compare(d, p)
        ok.append(("真植入负控·往生产多塞一个件 ⇒ 必须被点出",
                   extra == ["偷偷加进来的.py"], "点出: %s" % extra))
    bad = [n for n, c, _ in ok if not c]
    for n, c, d in ok:
        print("  %-50s %s  (%s)" % (n, "✅" if c else "❌", d))
    print("")
    print("deployment-law-check 自检: %s（%d 条）"
          % ("全部通过" if not bad else "%d 条失败" % len(bad), len(ok)))
    return 0 if not bad else 1


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    iso = _isolated_store()
    if iso:
        print("=" * 74)
        print("部署法制审查 · **不适用**（rc=3 ≠ 失败）")
        print("=" * 74)
        print("  当前跑在**隔离 store** 里：%s" % iso)
        print("  隔离屋里镜像维度与生产面都是空的临时屋 ⇒ 本件**量不到真东西**，")
        print("  照本仓口径报 **不适用**，不报红也不报绿（以免把假读数当真）。")
        print("  要真量：在仓内正常环境跑本脚本（不设 GBT_STORE_DIR）。")
        print("")
        return 3
    r = audit()
    render(r)
    return 0 if (r["镜像干净"] and r["镜像体检通过"] and not r["绕过镜像多出来的件"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())