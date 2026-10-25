# -*- coding: utf-8 -*-
"""连接点体检 —— 每个「谁依赖谁」都单独判一次

主人的口径（原文）：**「确保不会修复一个地方坏一个地方而不自觉」**

为什么单件存在性检查不够：
  「文件在」不等于「接得上」。真正的回归长这样 ——
    · 页索引重建了，但分片没重建 ⇒ manifest.count 和实际片数对不上
    · 分片重建了，但 daemon 还抱着旧 manifest ⇒ 查到的邻居是上一版的
    · 路由改了，落的位名不在 341 目录里 ⇒ 执行器拿着名字找不到实现
  这三种，每个件都"在"，但连接断了。

本件只做一件事：**逐条连接点断言**，每条回 bool + 读数。

用法：
  python3 tools/conn_check.py          # 全部连接点
  python3 tools/conn_check.py -v       # 带明细
"""
from __future__ import annotations
import gzip, importlib.util, json, socket, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERBOSE = "-v" in sys.argv


def _load(p: Path, n: str):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _j(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _raw(path):
    try:
        s = socket.create_connection(("127.0.0.1", 8792), timeout=4)
        s.sendall(("GET %s HTTP/1.0\r\nHost: x\r\n\r\n" % path).encode())
        b = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            b += c
        s.close()
        return json.loads(b.split(b"\r\n\r\n", 1)[1])
    except Exception as e:
        return {"ok": False, "error": type(e).__name__}


# ─────────────── 连接点断言 ───────────────
def c_bind_vs_lazy():
    """page_bind 与 page_lazy 索引的是同一棵树 ⇒ 页集合必须一致"""
    b = _j(ROOT / "state" / "page_bind.json")
    m = _j(ROOT / "state" / "bind" / "manifest.json")
    if not b or not m:
        return False, {"缺": "page_bind.json 或 manifest.json"}
    sb, sm = set(b.get("pages", [])), set(m.get("pages", []))
    diff = sb ^ sm
    return not diff, {"bind页": len(sb), "lazy页": len(sm), "差集": len(diff),
                      "例": sorted(diff)[:2]}


def c_manifest_vs_shards():
    """manifest.count == 实际分片文件数 == shard_of 条目数"""
    m = _j(ROOT / "state" / "bind" / "manifest.json")
    if not m:
        return False, {"缺": "manifest.json"}
    files = list((ROOT / "state" / "bind" / "shards").glob("*.json"))
    # 瘦身后 manifest 不再存 shard_of ⇒ 按 pages 现算（与 page_lazy.shard_name 同算法）
    import hashlib as _h
    n_decl = m.get("count")
    n_map = len({p: _h.blake2b(p.encode(), digest_size=8).hexdigest() for p in (m.get("pages") or [])})
    ok = n_decl == n_map == len(files)
    return ok, {"声明": n_decl, "映射": n_map, "实际": len(files)}


def c_shard_self():
    """每片自报的 id 必须跟 manifest 里登记的页对得上（防错位）"""
    m = _j(ROOT / "state" / "bind" / "manifest.json")
    if not m:
        return False, {"缺": "manifest.json"}
    bad = []
    import hashlib as _h
    _so = {p: _h.blake2b(p.encode(), digest_size=8).hexdigest() + ".json" for p in (m.get("pages") or [])}
    for pid, fn in list(_so.items()):
        f = ROOT / "state" / "bind" / "shards" / fn
        if not f.is_file():
            bad.append((pid, "缺片")); continue
        d = _j(f)
        if d.get("id") != pid:
            bad.append((pid, d.get("id")))
    return not bad, {"检查": len(_so), "错位": len(bad), "例": bad[:2]}


def c_disk_covers_pages():
    """磁盘索引必须**包含**每一页（否则"全量自捡"有洞）"""
    m = _j(ROOT / "state" / "bind" / "manifest.json")
    f = ROOT / "state" / "disk_index.json.gz"
    if not m or not f.is_file():
        return False, {"缺": "manifest 或 disk_index"}
    with gzip.open(f, "rb") as fh:
        d = json.loads(fh.read())
    paths = {r[0] for r in d["rows"]}
    missing = [p for p in m.get("pages", []) if str(ROOT / p) not in paths]
    return not missing, {"页": len(m.get("pages", [])), "缺": len(missing),
                         "例": missing[:2]}


def c_caps_domains():
    """341 位每一位都要有域、且名字唯一（否则路由会拿到歧义名字）"""
    d = _j(ROOT / "data" / "capabilities.json")
    if not d:
        return False, {"缺": "capabilities.json"}
    caps = d if isinstance(d, list) else (d.get("capabilities") or d.get("caps") or [])
    no_dom = [c.get("name") for c in caps if not c.get("domain")]
    names = [c.get("name") for c in caps]
    dup = len(names) - len(set(names))
    return (not no_dom and dup == 0), {"位": len(caps), "缺域": len(no_dom), "重名": dup}


def c_route_lands_in_catalog():
    """路由落下的位名必须在 341 目录里（编造名字必须当场拒）"""
    r = _load(ROOT / "tools" / "page_route.py", "_pr")
    d = _j(ROOT / "data" / "capabilities.json")
    caps = d if isinstance(d, list) else (d.get("capabilities") or d.get("caps") or [])
    names = {c.get("name") for c in caps}
    bad = []
    for q in ("授权门 状态", "查审计账本", "把 Markdown 变成 PPT", "花费 预算"):
        res = r.route(q)
        for c in (res.get("能力位") or [])[:3]:
            if c.get("cap") not in names:
                bad.append((q, c.get("cap")))
    return not bad, {"抽查": 4, "越界": len(bad), "例": bad[:2]}


def c_omni_op_matches_direct():
    """omni_plug 的 page_route 必须和直接调 page_route.py 给同一答案"""
    sys.path.insert(0, str(ROOT))
    from gbt_allinone import omni_plug as OP
    direct = _load(ROOT / "tools" / "page_route.py", "_pr2").route("授权门 状态")
    viaop = OP.run(op="page_route", text="授权门 状态").get("route", {})
    a = [c.get("cap") for c in (direct.get("能力位") or [])][:3]
    b = [c.get("cap") for c in (viaop.get("能力位") or [])][:3]
    return a == b, {"直接": a, "走op": b}


def c_daemon_vs_disk():
    """daemon 手里那份索引必须跟盘上的一致（防重修索引后 daemon 还抱旧的）"""
    r = _raw("/stats")
    if not r.get("ok"):
        return False, {"daemon": "未起"}
    f = ROOT / "state" / "disk_index.json.gz"
    if not f.is_file():
        return False, {"缺": "disk_index"}
    with gzip.open(f, "rb") as fh:
        d = json.loads(fh.read())
    same = r.get("文件") == d.get("files") and r.get("建于") == d.get("built_at")
    return same, {"daemon文件": r.get("文件"), "盘上文件": d.get("files"),
                  "daemon建于": r.get("建于"), "盘上建于": d.get("built_at")}


def c_daemon_find_vs_local():
    """daemon 查到的命中数必须跟本地直接查一致（防倒排索引漏项）"""
    r = _raw("/find?q=omni_plug&limit=99")
    if not r.get("ok"):
        return False, {"daemon": "未起"}
    f = ROOT / "state" / "disk_index.json.gz"
    if not f.is_file():
        return False, {"缺": "disk_index"}
    with gzip.open(f, "rb") as fh:
        d = json.loads(fh.read())
    local = sum(1 for row in d["rows"] if "omni_plug" in row[0].lower())
    return r.get("命中") == local, {"daemon": r.get("命中"), "本地": local}


def c_grants_readable():
    """授权账能读、且每条可解析（读不动 ⇒ 门会误判成"没票"）"""
    p = ROOT / "store" / "auth_grants.jsonl"
    if not p.is_file():
        return True, {"状态": "无账（等价于零票，门会如实拒）"}
    bad = 0
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            json.loads(ln)
        except Exception:
            bad += 1
    return bad == 0, {"行": len(p.read_text(encoding="utf-8").splitlines()), "坏行": bad}


def c_omni_two_copies():
    """真身(gbt_allinone/) 与切片副本(runtime/gbt_allinone/) 的 op 表面必须一致。
    两份 omni_plug 并存 ⇒ 谁被调用取决于 _ROOT 层级，op 不一致就是"同一个问题两个答案"。"""
    ops = ("page_route", "page_stats", "disk_find", "disk_stats")
    out = {}
    for label, path in (("真身", ROOT / "gbt_allinone" / "omni_plug.py"),
                        ("切片", ROOT / "runtime" / "gbt_allinone" / "omni_plug.py")):
        if not path.is_file():
            out[label] = "缺"
            continue
        txt = path.read_text(encoding="utf-8", errors="replace")
        out[label] = [o for o in ops if o in txt]
    return out.get("真身") == out.get("切片") and out.get("真身") is not None, out


def c_engine_is_real():
    """行为级判据：import 出来的 omni_plug 必须来自 gbt_allinone/（真身），
    不能来自 runtime/（12 文件审计切片）。查文本会被注释骗，查 __file__ 不会。"""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from gbt_allinone import omni_plug as OP
    f = str(getattr(OP, "__file__", ""))
    ok = ("runtime" not in f) and ("gbt_allinone" in f)
    n = len(getattr(OP, "__dict__", {}))          # 真身符号多，切片少
    return ok, {"加载自": f.replace(str(ROOT) + "/", ""), "符号数": n}


def c_bridge_speaks_a19():
    """桥的默认上游必须指向手机自己的 A19（:1234）。指向云 => 车道又是别人的。"""
    import json as _j, urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:8791/health",
                                     headers={"User-Agent": "gbt-conn"})
        with urllib.request.urlopen(req, timeout=5) as r:
            d = _j.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return False, {"桥": "unreachable", "why": type(e).__name__}
    ups = {u.get("name"): u for u in (d.get("upstreams") or [])}
    sh = ups.get("selfhost") or {}
    url = str(sh.get("base_url") or "")
    ok = bool(d.get("ok")) and d.get("default") == "selfhost" and ":1234" in url
    return ok, {"默认": d.get("default"), "selfhost": url, "判定": "默认=selfhost 且指向 :1234"}


def c_page_bridge_port():
    """她的对话页里写的桥端口，必须是桥真在听的那一个。"""
    import re
    f = ROOT / "holo_pet_w3" / "model-chat" / "index.html"
    if not f.is_file():
        return False, {"缺": "model-chat/index.html"}
    t = f.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'BRIDGE\s*=\s*["\']([^"\']+)["\']', t)
    if not m:
        return False, {"判定": "页面里没找到 BRIDGE 常量"}
    url = m.group(1)
    return (":8791" in url), {"页面 BRIDGE": url, "判定": "应指向 :8791"}


def c_manifest_start_url():
    """PWA 清单里的 start_url 必须真存在 —— 不然装到桌面点开是 404。"""
    import json as _j
    f = ROOT / "holo_pet_w3" / "manifest.webmanifest"
    if not f.is_file():
        return False, {"缺": "manifest.webmanifest"}
    try:
        d = _j.loads(f.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        return False, {"解析失败": type(e).__name__}
    su = str(d.get("start_url") or "")
    target = (ROOT / "holo_pet_w3" / su.lstrip("./")).resolve()
    return (bool(su) and target.is_file()), {
        "start_url": su, "落点存在": target.is_file(), "name": d.get("name")}


CONNS = [
    ("桥 speaks A19", c_bridge_speaks_a19),
    ("页面 ⇄ 桥 端口", c_page_bridge_port),
    ("PWA start_url", c_manifest_start_url),
    ("bind ⇄ lazy 页集合", c_bind_vs_lazy),
    ("manifest ⇄ 分片数", c_manifest_vs_shards),
    ("分片自报 id ⇄ manifest", c_shard_self),
    ("磁盘索引 ⊇ 每一页", c_disk_covers_pages),
    ("341 位 ⇄ 域/唯一名", c_caps_domains),
    ("路由 ⇄ 341 目录", c_route_lands_in_catalog),
    ("omni.page_route ⇄ 直调", c_omni_op_matches_direct),
    ("daemon ⇄ 盘上索引", c_daemon_vs_disk),
    ("daemon.find ⇄ 本地查", c_daemon_find_vs_local),
    ("授权账 ⇄ 可解析", c_grants_readable),
    ("omni 真身 ⇄ 切片", c_omni_two_copies),
    ("工具加载的是真身", c_engine_is_real),
]


def main() -> int:
    bad = 0
    for name, fn in CONNS:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, {"异常": "%s: %s" % (type(e).__name__, str(e)[:90])}
        mark = "✅" if ok else "🔴"
        print("  %s %-26s %s" % (mark, name, "" if ok else json.dumps(detail, ensure_ascii=False)[:110]))
        if ok and VERBOSE:
            print("     %s" % json.dumps(detail, ensure_ascii=False)[:110])
        if not ok:
            bad += 1
    print("\n  %d 个连接点 · 通过 %d · 断链 %d" % (len(CONNS), len(CONNS) - bad, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
