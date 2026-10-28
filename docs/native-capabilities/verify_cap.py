# -*- coding: utf-8 -*-
"""原生能力 · 逐位独立查阅与验证工具（只读 AST，不导入、不执行引擎）。

## 为什么要有它

`docs/native-capabilities/` 里的 25 篇文档是**人写的叙述**。叙述会腐烂 ——
注册表加了一位、改了一个作用域，文档不会自动跟着变。

这个脚本把文档钉到**源码本身**上：直接解析 `gbt_allinone/caps_registry.py` 的
AST，逐位读出 `domain / desc / safe / external`，与文档声称的条目对账。
谁改了注册表，这里当场红，而不是等读者相信我们。

## 跑法（零依赖，只要 Python 3.10+）

    python docs/native-capabilities/verify_cap.py list            # 按域列出全部能力位
    python docs/native-capabilities/verify_cap.py show <能力位>    # 看某一位的完整登记
    python docs/native-capabilities/verify_cap.py domain <域名>    # 看某域全部能力位
    python docs/native-capabilities/verify_cap.py check            # 逐位与文档覆盖面对账
    python docs/native-capabilities/verify_cap.py check-calls      # 文档里的调用名是否真实存在
    python docs/native-capabilities/verify_cap.py stats            # 域统计
    python docs/native-capabilities/verify_cap.py json             # 机器可读全量导出

## 退出码

0 = 通过；1 = 对账有条目不过（逐条打印原因）。

## 边界（写死）

- **只读**：`ast.parse` 解析源码，**绝不 import 包、绝不执行任何能力**。
- **不猜**：注册表没登记 `requires_params` 就报「未登记」，不脑补。
- **不假绿**：对账失败就红，不因为「文档写得挺像」而放过。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REGISTRY = ROOT / "gbt_allinone" / "caps_registry.py"

# ── 文档覆盖面（与 README.md 索引表同源，逐域对照**真实**注册表域）────────
# 键必须是 caps_registry.py 里真有的 domain 值；写错就是假账，check 会当场红。
DOMAIN_DOC = {
    "system": "01-system-data.md",
    "data": "01-system-data.md",
    "framework": "01-system-data.md",
    "engine": "02-engine.md",
    "pipeline": "05-pipeline.md",
    "brain": "06-brain-exec.md",
    "llm": "08-llm-gateway.md",
    "tentacle": "09-tentacle.md",
    "desktop": "09-tentacle.md",
    "security": "10-security.md",
    "devour": "11-devour.md",
    "mind": "12-mind-engine.md",
    "life": "12-mind-engine.md",
    "longrun": "13-longrun.md",
    "recon": "14-recon.md",
    "device": "15-device.md",
    "vision": "16-vision.md",
    "voice": "17-voice.md",
    "automation": "18-browser.md",
    "finance": "19-finance.md",
    "project": "19-finance.md",
    "infra": "23-deployment.md",
    "creation": "25-creation.md",
    "video": "26-video-media.md",
    "image_video": "26-video-media.md",
    "tools": "27-tools.md",
    "integration": "28-integration.md",
    "collab": "28-integration.md",
    "social": "28-integration.md",
    "comms": "28-integration.md",
}

# ── 跨域文档：按**能力位名**归入（这些文档讲横切主题，不是单个域）──────────
CAP_DOC = {
    # 镜像多维度空间（能力位登记在 pipeline 域，语义自成一域）
    **{n: "03-mirror-space.md" for n in (
        "mirror_shape", "mirror_scan", "mirror_plan", "mirror_simulate",
        "mirror_parity", "mirror_rehearse", "mirror_release", "mirror_ascend",
        "mirror_status", "mirror_rewind")},
    # 房间空间（**单个能力位**，19 个 op —— 不是 19 个位）
    "room_space": "04-room-space.md",
    # 授权门 / 脑库 / 记录网格
    "auth_gate_status": "20-auth-gate.md",
    "brain_vault": "21-brain-vault.md",
    "record_grid": "22-record-grid.md",
    # 部署系统（pipeline 域里属于部署语义的那几位）
    "one_key_deploy": "23-deployment.md",
    "deploy_queue": "23-deployment.md",
    "svc_inspect": "23-deployment.md",
    "ghost_guard": "23-deployment.md",
    # 数字人（横切 video / creation / device 三域）
    "digital_human": "24-digital-human.md",
    "dh_brain": "24-digital-human.md",
    "dh_pose": "24-digital-human.md",
    "dh_realism": "24-digital-human.md",
    "dh_asset_gate": "24-digital-human.md",
    **{n: "24-digital-human.md" for n in (
        "body_see", "body_say", "body_click", "body_type",
        "body_open", "body_volume", "body_map")},
    # 浏览器（横切 automation / tentacle / system 三域）
    "browser": "18-browser.md",
    "omni_web": "18-browser.md",
    "scrapling": "18-browser.md",
    "page_scan": "18-browser.md",
    "topic_web": "18-browser.md",
    # 设备
    "bluetooth": "15-device.md",
    "bt_control": "15-device.md",
}


class RegistryError(Exception):
    pass


def doc_for(name: str, domain: str) -> str:
    """某能力位归入哪篇文档。**能力位级覆盖优先于域级**（跨域主题靠这条）。"""
    return CAP_DOC.get(name) or DOMAIN_DOC.get(domain) or ""


def _parse_registry() -> dict:
    """只读解析 caps_registry.py 的 BENIGN_CAPS 字面量。

    用 AST 而不是 import：import 会触发包级副作用（`api.py` 会建 store、
    `caps_tables` 会读盘），而我们只想读表。
    """
    if not REGISTRY.exists():
        raise RegistryError("找不到注册表: %s" % REGISTRY)

    src = REGISTRY.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src, filename=str(REGISTRY))

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "BENIGN_CAPS":
                value = node.value
                if not isinstance(value, ast.Dict):
                    raise RegistryError("BENIGN_CAPS 不是字典字面量，无法只读解析")
                return _dict_from_ast(value)
    raise RegistryError("注册表里找不到 BENIGN_CAPS 赋值")


def _dict_from_ast(node: ast.Dict) -> dict:
    """把 ast.Dict 的键值（都是字符串/简单字面量）取出来。"""
    out = {}
    for k, v in zip(node.keys, node.values):
        if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
            continue
        out[k.value] = _literal(v)
    return out


def _literal(node):
    """把 AST 节点还原成 Python 值。

    支持 Constant / Dict / List / Tuple / **字符串加法拼接** —— 注册表里 `desc`
    常写成 `"前半" "后半"` 或 `"a" + "b"`（隐式/显式拼接），只用 `ast.literal_eval`
    会在 `BinOp` 上炸掉，把整条登记读成占位符（实测 `replan_loop` 就是这么丢的）。
    取不出的如实返回占位字符串，不猜。
    """
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Dict):
        return {_literal(k): _literal(v) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.List):
        return [_literal(e) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_literal(e) for e in node.elts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _literal(node.left), _literal(node.right)
        if isinstance(left, str) and isinstance(right, str):
            return left + right
        if isinstance(left, list) and isinstance(right, list):
            return left + right
        return "<非字面量，无法只读取值>"
    return "<非字面量，无法只读取值>"


def load_caps() -> dict:
    return _parse_registry()


# ── 视图 ────────────────────────────────────────────────────────────

def _norm(meta) -> dict:
    """统一取元数据；登记项不是字典就回空 dict（如实，不编）。"""
    return meta if isinstance(meta, dict) else {}


def cmd_list(caps: dict) -> int:
    by_domain: dict = {}
    for name, meta in caps.items():
        by_domain.setdefault(_norm(meta).get("domain", "（未登记域）"), []).append(name)

    for d in sorted(by_domain):
        names = sorted(by_domain[d])
        print("\n[%s] %d 位 · 文档: %s" % (
            d, len(names), DOMAIN_DOC.get(d, "（无域级文档）")))
        for n in names:
            print("   %s" % n)
    print("\n合计 %d 位 / %d 域" % (len(caps), len(by_domain)))
    return 0


def cmd_show(caps: dict, name: str) -> int:
    if name not in caps:
        # 同前缀兜底：让人至少看得到同族有哪些，不至于连方向都没有
        pre = name.split("_")[0]
        fam = sorted(p for p in caps if p.startswith(pre + "_"))
        print("没有登记这个能力位: %s" % name, file=sys.stderr)
        if fam:
            print("同族候选: %s" % ", ".join(fam[:8]), file=sys.stderr)
        return 1

    m = _norm(caps[name])
    if not m:
        print("%s ⇒ 登记项不是字典，读不出元数据" % name)
        return 1

    safe = m.get("safe")
    domain = m.get("domain", "（未登记）")
    print("能力位  : %s" % name)
    print("域      : %s" % domain)
    print("类型    : %s" % ("只读" if safe is True else ("需授权" if safe is False else "（未登记）")))
    print("处理器  : %s" % m.get("handler", "（未登记）"))
    if m.get("external"):
        print("外部模块: %s（未挂载时如实报 needs_dependency）" % m["external"])
    print("需参数  : %s" % ("是" if m.get("requires_params") else "否（注册表：无必填）"))
    doc = doc_for(name, domain)
    print("文档    : %s" % ("docs/native-capabilities/" + doc if doc else "（无专属文档）"))
    print("\n说明：")
    desc = str(m.get("desc", "（无说明）"))
    for i in range(0, len(desc), 76):
        print("  " + desc[i:i + 76])
    return 0


def cmd_domain(caps: dict, domain: str) -> int:
    hit = {n: _norm(m) for n, m in caps.items() if _norm(m).get("domain") == domain}
    if not hit:
        known = sorted({_norm(m).get("domain", "?") for m in caps.values()})
        print("没有这个域: %s" % domain, file=sys.stderr)
        print("已知域: %s" % ", ".join(known), file=sys.stderr)
        return 1

    ro = sum(1 for m in hit.values() if m.get("safe") is True)
    need = sum(1 for m in hit.values() if m.get("safe") is False)
    print("域 [%s] · %d 位 · 只读 %d · 需授权 %d" % (domain, len(hit), ro, need))
    print("文档: docs/native-capabilities/%s\n" % DOMAIN_DOC.get(domain, "（无域级文档）"))
    for n in sorted(hit):
        m = hit[n]
        tag = "只读  " if m.get("safe") is True else "需授权"
        print("  %s  %-26s  %s" % (tag, n, str(m.get("desc", ""))[:64]))
    return 0


def cmd_stats(caps: dict) -> int:
    by_domain: dict = {}
    for name, meta in caps.items():
        m = _norm(meta)
        d = m.get("domain", "（未登记域）")
        v = by_domain.setdefault(d, {"total": 0, "ro": 0, "need": 0})
        v["total"] += 1
        if m.get("safe") is True:
            v["ro"] += 1
        elif m.get("safe") is False:
            v["need"] += 1

    print("%-18s %6s %6s %8s  %s" % ("域", "总数", "只读", "需授权", "文档"))
    print("-" * 82)
    for d in sorted(by_domain, key=lambda x: (-by_domain[x]["total"], x)):
        v = by_domain[d]
        print("%-18s %6d %6d %8d  %s" % (
            d, v["total"], v["ro"], v["need"], DOMAIN_DOC.get(d, "—")))
    print("-" * 82)
    tot = sum(v["total"] for v in by_domain.values())
    ro = sum(v["ro"] for v in by_domain.values())
    need = sum(v["need"] for v in by_domain.values())
    print("%-18s %6d %6d %8d" % ("合计", tot, ro, need))
    print("\n域数: %d" % len(by_domain))
    return 0


def cmd_check(caps: dict) -> int:
    """逐位对账：**每个能力位都要指得到一篇存在的文档**。

    旧版是"域级对账"，会漏掉两件事：① 域名写错（如把 pipeline 写成 mirror）只在
    域清单里红，说不出影响哪些位；② 横切文档（镜像/房间/授权门/数字人/浏览器）
    压根不在域表里。改成逐位对账后，任一能力位指不到文档就红。
    """
    fails = []
    by_domain: dict = {}

    for name, meta in caps.items():
        m = _norm(meta)
        d = m.get("domain", "（未登记域）")
        by_domain.setdefault(d, 0)
        by_domain[d] += 1

        doc = doc_for(name, d)
        if not doc:
            fails.append((name, d, "无文档归属"))
        elif not (HERE / doc).exists():
            fails.append((name, d, "文档不存在: %s" % doc))

    total = len(caps)
    covered = total - len(fails)
    print("对账 1/2 · 逐位文档归属（%d 位）" % total)
    if fails:
        for name, d, why in fails[:40]:
            print("  FAIL  %-26s [%-12s] %s" % (name, d, why))
        if len(fails) > 40:
            print("  … 另有 %d 条" % (len(fails) - 40))
    else:
        print("  PASS  全部 %d 位都指得到文档" % total)

    print("\n对账 2/2 · 域级覆盖（%d 域）" % len(by_domain))
    warns = []
    for d in sorted(by_domain):
        doc = DOMAIN_DOC.get(d)
        if doc and (HERE / doc).exists():
            print("  PASS  %-14s → %-22s（%d 位）" % (d, doc, by_domain[d]))
        else:
            print("  WARN  %-14s → 无域级文档（%d 位，靠能力位级覆盖）" % (d, by_domain[d]))
            warns.append(d)

    print("\n结果: %d/%d 位有文档 · %d 域无域级文档 · %d 条不过"
          % (covered, total, len(warns), len(fails)))
    if fails:
        print("不过清单见上（FAIL 行）")
        return 1
    return 0


def cmd_json(caps: dict) -> int:
    """机器可读全量导出（供 CI / 面板 / 其他工具消费）。"""
    out = {}
    for name, meta in sorted(caps.items()):
        m = _norm(meta)
        d = m.get("domain", "")
        out[name] = {
            "domain": d,
            "type": "read_only" if m.get("safe") is True else (
                "needs_grant" if m.get("safe") is False else "unregistered"),
            "handler": m.get("handler", ""),
            "external": m.get("external", ""),
            "requires_params": bool(m.get("requires_params")),
            "doc": doc_for(name, d),
            "desc": m.get("desc", ""),
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


# ── 文档里的调用名对账（抓"写了个不存在的能力位"这类错）──────────────────
_CALL_RE = re.compile(r'run_task\(\s*["\']([A-Za-z_][A-Za-z0-9_]*)["\']')


def cmd_check_calls(caps: dict) -> int:
    """把**所有文档里出现的 `run_task("名字", …)`** 抽出来，逐个核对是否真在注册表里。

    为什么要有这一条：`check` 只验"每个能力位有没有文档"，
    验不了"文档里写的能力位名是不是真的"。上一版就有 4 个假名
    （`room_create` / `native_browser` / `scrapling_cap` / `dh_rig`）靠人眼才发现。
    这一条把它们变成机器可抓。
    """
    known = set(caps)
    bad = []
    total_calls = 0

    for path in sorted(HERE.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.split("\n"), 1):
            for name in _CALL_RE.findall(line):
                total_calls += 1
                if name not in known:
                    bad.append((path.name, lineno, name))

    print("对账 · 文档里的 run_task 调用名（共 %d 处）" % total_calls)
    if not bad:
        print("  PASS  全部调用名都能在注册表里找到")
        print("\n结果: %d 处调用 · 0 条假名" % total_calls)
        return 0

    print("  发现 %d 处调用名在注册表里**不存在**：" % len(bad))
    for fn, ln, name in bad:
        # 同前缀兜底：给出真名候选，别让人只看到"错了"
        pre = name.split("_")[0]
        fam = sorted(p for p in known if p.startswith(pre + "_"))[:3]
        hint = ("（同族: %s）" % ", ".join(fam)) if fam else ""
        print("  FAIL  %-24s:%-4d  %s%s" % (fn, ln, name, hint))
    print("\n结果: %d 处调用 · %d 条假名" % (total_calls, len(bad)))
    return 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0

    try:
        caps = load_caps()
    except RegistryError as e:
        print("注册表读取失败: %s" % e, file=sys.stderr)
        return 1

    op = argv[0]
    if op == "list":
        return cmd_list(caps)
    if op == "show":
        if len(argv) < 2:
            print("用法: verify_cap.py show <能力位>", file=sys.stderr)
            return 1
        return cmd_show(caps, argv[1])
    if op == "domain":
        if len(argv) < 2:
            print("用法: verify_cap.py domain <域名>", file=sys.stderr)
            return 1
        return cmd_domain(caps, argv[1])
    if op == "stats":
        return cmd_stats(caps)
    if op == "check":
        return cmd_check(caps)
    if op == "check-calls":
        return cmd_check_calls(caps)
    if op == "json":
        return cmd_json(caps)

    print("未知操作: %s（可用: list / show / domain / stats / check / check-calls / json）"
          % op, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
