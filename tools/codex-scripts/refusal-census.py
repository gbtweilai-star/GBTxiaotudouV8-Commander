"""拒绝普查（只读）—— 主人令「千万不能出现拒绝的限制，去干净点」的**现读底账**。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 先把词分清（分不清就会去错东西）
- **授权型**：缺作用域 ⇒ 拒；**主人发一条授权就能过**。⇒ 这是**门**，不是「拒绝的限制」。
- **硬拒型**：**不管谁、怎么授权都过不去**（函数里既没有作用域、也没有授权检查）。
  ⇒ **这才是主人要清的东西**。
- **不是拒绝**：只是如实报「没实现 / 未读到 / 未接线」——那不是拒，是缺。

## 怎么量
AST 逐函数：① 函数里有**拒绝字样**的字面量（或 `raise PermissionError`）⇒ 记为「会拒」；
② 同一函数里有没有**授权线索**（作用域名 / `scope` / `grant` / `auth` / `missing_scopes`）⇒ 分两档；
③ 若那条字面量本身只是「未实现/未读到/未接线」⇒ **不算拒绝**。

## 它量不了什么
- 只看**函数粒度**：一个函数里既有授权门又有硬拒，会被算成「授权型"⇒ **保守偏宽**（宁少报不冤报）。
- 只认**字面量**：拼接出来的拒绝语（`"拒" + "绝"`）识别不到 ⇒ 会漏。
⇒ 输出是**底账 + 候选**，不是判决。

用法：
  python tools/codex-scripts/refusal-census.py scan [--roots gbt_allinone,tools/codex-scripts] [--json]
  python tools/codex-scripts/refusal-census.py selftest
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DEFAULT_ROOTS = ("gbt_allinone", "tools/codex-scripts")
BASELINE = ROOT / "state" / "refusal-census-baseline.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 「拒绝」字样（单一来源；空表 = 拒绝，见 selftest）
# 第一版漏了「不许」⇒ **漏掉了最大的一条**（`qiankun.py` 的「未声明落点：不许默认把项目
#    堆进全局生产面」）。**词表太窄 ⇒ 底账漏项**；补上后复验命中数（先量信噪比再定宽窄）。
REFUSAL = ("拒绝", "denied", "refuse", "forbidden", "不允许", "不许", "禁止", "not allowed", "拦截")
# 这些字样说明「只是没实现/没读到」，**不是拒**
NOT_REFUSAL = ("未实现", "未读到", "未接线", "没实现", "needs_dependency", "unknown capability")
# 授权线索（函数里出现任一 ⇒ 这一处拒绝是**门**）
AUTH_HINT = ("scope", "grant", "authoriz", "missing_scopes", "check_and_consume")
_SKIP = ("__pycache__", "vendor", ".git")

# **门面**（= 决定「能力许不许用」的那几处）。只有这里的硬拒才叫「限制」。
#    别处（`*/tools/check_*`、`assert_*`、`must_*`）是**质量护栏**：拦的是「产物的合规性」，
#    不是「模型不许干活」。第一版不分类 ⇒ 报了 296 条假数（把护栏全算成限制）——
#    **先量信噪比再定宽窄**（§一百五十三那条纪律）。
GATE_SURFACE = (
    "gbt_allinone/api.py",
    "gbt_allinone/run.py",
    "gbt_allinone/auth_gate.py",
    "gbt_allinone/security/",
    "gbt_allinone/caps_registry.py",
    "gbt_allinone/caps_tables.py",
    "gbt_allinone/omni.py",
    # 分派/生产写入那条链（`one_key_deploy` 的「不声明落点就拒」就在这一带）
    "gbt_allinone/qiankun.py",
    "gbt_allinone/pipeline.py",
    "gbt_allinone/mirror_space.py",
    "gbt_allinone/room_space.py",
    "gbt_allinone/deployment_rehearsal.py",
    "gbt_allinone/preflight.py",
    "gbt_allinone/safe_io.py",
    "gbt_allinone/file_operation.py",
)


def _is_gate_surface(rel: str) -> bool:
    """仓内相对路径**或**临时靶的绝对路径都认得（自检拿临时目录当靶）。"""
    r = rel.replace("\\", "/").lstrip("./")
    for g in GATE_SURFACE:
        if g.endswith("/"):                      # 目录：任一段匹配即可
            if r.startswith(g) or ("/" + g.rstrip("/") + "/") in ("/" + r):
                return True
        elif r == g or r.endswith("/" + g):      # 单件：整体相等，或以 /<路径> 结尾
            return True
    return False


# **门面硬拒认领表**（主人令「千万不能出现拒绝的限制」的处置底账）——
#    每一处门面硬拒都必须在表里有**处置 + 为什么 + 放开的后果 + 谁定的**；
#    不在表里 ⇒ 闸红（`**未认领**` 非空）。新增一处硬拒，就必须在这一行给出处置。
#    处置三档：`保留（防护）` · `保留（主人红线）` · `假阳性（不是拒法）`。
CLAIMS = {
 # 2026-10-10 补（体检 rc=1 追根因：这两处"新增门面硬拒"没认领）：
    "gbt_allinone/security/redteam.py|remote_domain": {
        "处置": "改（2026-10-13）：从「公网一律拒」改成「**终端 YES 授权才放行**」",
        "谁定的": "Owner 2026-10-13（「技术层面不能给她有限制只保留人工授权护栏即可」·"
                "「直接改成终端YES才能使用就好了有时候我需要用到的啊」）",
        "为什么": "公网 endpoint **默认照旧拒**；但当主人在**终端**发**专用一次性钥匙** `deploy_force`"
                 "（提示符敲 YES）、调用方再显式 `owner_override=true` ⇒ 才登记，"
                 "且登记行里留 `override/override_reason/override_note` 三件（谁放的、什么理由，事后查得出）",
        "放开的后果": "带主人授权的公网中继会被登记（≠ 无门槛：没那把钥匙，一个字都进不来）"},
    "gbt_allinone/security/redteam.py|_pentest_plan": {
        "处置": "假阳性（不是拒法）", "谁定的": "判据自查（2026-10-10）",
        "为什么": "_pentest_plan(target, rec) **正常返回一份五阶段计划**（ok 为 True）——"
                 "它是「出计划」不是「拒动作」；扫描器把非拒绝的返回路径也匹配进来了",
        "放开的后果": "无（它本来就不是拒绝：没有它挡着任何东西）"},
    "gbt_allinone/file_operation.py|_write_root_checked": {
        "处置": "保留（防护）", "谁定的": "框架既有纪律",
        "为什么": "进程已隔离 store 时不许写进生产 `outputs/`",
        "放开的后果": "沙箱/测试跑出来的产物会污染生产交付目录（§一百一十一 同型事故）"},
    "gbt_allinone/file_operation.py|_check_rel": {
        "处置": "保留（防护）", "谁定的": "框架既有纪律",
        "为什么": "路径不许绝对路径（防越界写盘）",
        "放开的后果": "能写到工作根以外的任何位置"},
    "gbt_allinone/file_operation.py|_require_enabled": {
        "处置": "保留（开关在主人手里）", "谁定的": "设置页开关",
        "为什么": "`create.enabled=false` ⇒ 全部动作拒",
        "放开的后果": "无（这不是硬禁：把开关打开即可，开关本身是设置页的项）"},
    "gbt_allinone/file_operation.py|_check_content": {
        "处置": "保留（防护）", "谁定的": "框架既有纪律",
        "为什么": "超上限**拒绝而不是截断**",
        "放开的后果": "静默截断内容（比拒更坏：产物看着成功、内容缺一块）"},
    "gbt_allinone/file_operation.py|_resolve_target_name": {
        "处置": "保留（防护）", "谁定的": "框架既有纪律",
        "为什么": "`target_source=default` 时不许自带 target",
        "放开的后果": "默认出口的取值能被调用方顶掉"},
    "gbt_allinone/file_operation.py|_op_write": {
        "处置": "保留（防护）", "谁定的": "框架既有纪律",
        "为什么": "`overwrite=True` 但目标不存在 ⇒ 拒",
        "放开的后果": "把「覆盖」当「新建」的暗门"},
    "gbt_allinone/deployment_rehearsal.py|_normalize_plan": {
        "处置": "保留（防护）", "谁定的": "框架既有纪律",
        "为什么": "计划里不许存**真密钥值**，只写环境变量名",
        "放开的后果": "凭据落进计划文件"},
    "gbt_allinone/deployment_rehearsal.py|release": {
        "处置": "改（2026-10-13）：未全绿从「死限」改成「终端 YES 授权才放行」",
        "谁定的": "Owner 2026-10-13（同上两条主人令）",
        "为什么": "**默认一字不变**：排练未全绿仍 return blocked，并给出「怎么放行」；"
                 "主人在终端发**专用一次性钥匙** `deploy_force`（YES）+ 调用方显式 `owner_override=true` "
                 "⇒ 放行，并写审计 `mirror_release_overridden`（含 blockers 与理由）",
        "放开的后果": "未全绿也能晋升生产 —— 但每放一次都要主人**单独**发一把 force 钥匙（与正常发布钥匙分开）"},
    "gbt_allinone/mirror_space.py|ascend": {
        "处置": "改（2026-10-13）：验证未全绿从「死限」改成「终端 YES 授权才放行」",
        "谁定的": "Owner 2026-10-13（同上两条主人令）",
        "为什么": "**默认一字不变**：仍 return blocked（并给 `如何放行`）；终端发**专用一次性钥匙** `deploy_force`（YES）"
                 "+ 显式 `owner_override=true` ⇒ 放行，写审计 `deploy_promote_overridden`，"
                 "并把「未绿的检查项 + 放行理由」刻进部署护照的 `override` 字段",
        "放开的后果": "未全绿的镜像也能晋升 —— 每次放行都留审计与护照凭据，不是静默的"},
    "gbt_allinone/room_space.py|release": {
        "处置": "改（2026-10-13）：两关（排练未全绿 / 门禁未过）都改成「终端 YES 授权才放行」",
        "谁定的": "Owner 2026-10-13（同上两条主人令）",
        "为什么": "**默认一字不变**：两处仍各自 return blocked；终端发**专用一次性钥匙** `deploy_force`（YES）"
                 "+ 显式 `owner_override=true` ⇒ 放行，写审计 `room_release_overridden`"
                 "（`blocked_by` 标明卡在哪一关）",
        "放开的后果": "房间排练未过也能写房间现实区 —— 每次都留审计、且要主人先发授权"},
    "gbt_allinone/qiankun.py|one_key_deploy": {
        "处置": "改（2026-10-13）：未声明落点从「直接拒」改成「终端 YES 授权才放行」",
        "谁定的": "Owner 2026-10-13（同上两条主人令）",
        "为什么": "**默认一字不变**：仍 return blocked，并给出「怎么放行」；终端发**专用一次性钥匙** `deploy_force`（YES）"
                 "+ 显式 `owner_override=true` ⇒ 按「全局生产」放行，"
                 "写审计 `one_key_deploy_landing_overridden`，返回里 `steps.landing_override.route` 明示落点",
        "放开的后果": "不声明落点也可能写**全局生产**面 —— 本仓唯一的生产落点保护，"
                    "放行前必须看清 `steps.landing_override.route`（AGENTS.md 那句旧口径见护照备注）"},
    "gbt_allinone/api.py|_run_benign": {
        "处置": "保留（防护）", "谁定的": "框架既有纪律",
        "为什么": "`wf_define` 的 file 只许仓内 `state/` 相对路径",
        "放开的后果": "工作流定义能指向仓外文件"},
    "gbt_allinone/security/net_guard.py|validate_url": {
        "处置": "保留（防护）", "谁定的": "框架既有纪律",
        "为什么": "URL 不许内嵌用户名/密码",
        "放开的后果": "出网请求把凭据带进 URL（会进日志/代理）"},
    "gbt_allinone/security/data_policy.py|_bad_input": {
        "处置": "保留（参数校验）", "谁定的": "框架既有纪律",
        "为什么": "入参不成形 ⇒ `denied`",
        "放开的后果": "不成形的入参继续往下走"},
    "gbt_allinone/auth_gate.py|audit_degraded": {
        "处置": "假阳性（不是拒法）", "谁定的": "—",
        "为什么": "那是**读数说明串**（「count>0 ⇒ 有授权/拒绝事件未落账」），不是拒绝决定",
        "放开的后果": "无（改措辞即可让它从底账里消失，但那属于骗判据 ⇒ 如实留着并标假阳性）"},
}


def claim_report(fps, claims=None) -> dict:
    """**纯函数**：每处门面硬拒都得在认领表里有处置；不在 ⇒ **未认领**（闸红）。"""
    claims = CLAIMS if claims is None else claims
    rows = [dict(claims[f], 指纹=f) for f in fps if f in claims]
    return {"已认领": len(rows), "**未认领（必须有处置）**": [f for f in fps if f not in claims],
            "明细": rows}


def module_uses_auth(tree) -> bool:
    """**AST 判**：这个模块有没有**真的**用授权通道（import 或调用），**不扫文本**。

    🔴 第一版写的是 `"auth_gate" in src` —— 被台架 D2/D6 判成文本判据，**判得对**：
    文本会把**注释/文档里提到** `auth_gate` 也算成"有通道"（假阳），
    而这一栏是给主人看"授权到底绕不绕得过"的，假阳会让人以为能绕。
    """
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            if (n.module or "").endswith("auth_gate"):
                return True
            # `from . import auth_gate` 这种：模块名是「.」，名字才在 alias 里（第一版漏了 ⇒ 控制当场红）
            for al in n.names:
                if al.name.endswith("auth_gate"):
                    return True
        if isinstance(n, ast.Import):
            for al in n.names:
                if al.name.endswith("auth_gate"):
                    return True
        if isinstance(n, ast.Attribute) and n.attr in ("check_and_consume", "check_and_consume_many"):
            return True
        if isinstance(n, ast.Name) and n.id == "auth_gate":
            return True
    return False


def _scope_names() -> tuple:
    """现读两侧作用域名（policy + auth_gate），**不硬编码**。"""
    names = set()
    try:
        from gbt_allinone.security import policy as P
        names |= set(P.SCOPE_DESCRIPTIONS)
    except Exception:
        pass
    try:
        from gbt_allinone import auth_gate as G
        names |= set(getattr(G, "SCOPES", {}) or {})
    except Exception:
        pass
    return tuple(sorted(names))


def _parents(tree) -> dict:
    par = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            par[id(c)] = n
    return par


def _doc_ids(tree) -> set:
    """docstring 是**文档**，不是「拒绝决定" —— 混进来会把底账淹掉（第一版 498 条假数就是这么来的）。"""
    ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(n, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def _decided(n, parents) -> bool:
    """这个字面量是不是**一次拒绝决定**（出现在 `return`/`raise` 里），而不是别处的叙述。"""
    cur = parents.get(id(n))
    while cur is not None:
        if isinstance(cur, (ast.Return, ast.Raise)):
            return True
        cur = parents.get(id(cur))
    return False


def _hints(node, scopes: tuple) -> bool:
    """函数里有没有**授权线索**：标识符含 scope/grant/auth…，或有常量**正好等于**某个作用域名。

    🔴 不用 `ast.dump(node)`：`api.py` 里有上千行的函数，dump 是**平方级**开销
    （实测：全仓扫超过 120 秒没跑完）。这里只做一次线性遍历。
    """
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and any(h in n.id.lower() for h in AUTH_HINT):
            return True
        if isinstance(n, ast.Attribute) and any(h in n.attr.lower() for h in AUTH_HINT):
            return True
        if isinstance(n, ast.arg) and any(h in n.arg.lower() for h in AUTH_HINT):
            return True
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in scopes:
            return True
    return False


def classify_function(node, scopes: tuple, parents=None, docids=None) -> dict | None:
    """一个函数的拒绝分档；**没拒绝字样就返回 None**。"""
    parents = parents if parents is not None else {}
    docids = docids if docids is not None else set()
    lits, raises_perm = [], []
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            t = n.value
            if id(n) in docids or not any(w in t for w in REFUSAL):
                continue
            if parents and not _decided(n, parents):
                continue
 # 出现在 `return {...}` / `raise` 里才算「拒绝决定」；顺带把「只是没实现」剔掉
            lits.append((n.lineno, t))
        elif isinstance(n, ast.Raise) and isinstance(n.exc, (ast.Call, ast.Name)):
            nm = getattr(getattr(n.exc, "func", n.exc), "id", "")
            if nm in ("PermissionError", "PermissionDenied"):
                raises_perm.append(n.lineno)
    if not lits and not raises_perm:
        return None
    real = [(ln, t) for ln, t in lits if not any(w in t for w in NOT_REFUSAL)]
    if not real and not raises_perm:
        return None
    authed = _hints(node, scopes)
    return {"函数": getattr(node, "name", "?"), "行": node.lineno,
            "档": "授权型（主人授权可过）" if authed else "硬拒型（谁都过不去）",
            "样例": (real or [(raises_perm[0], "raise PermissionError")])[0][1][:52]}


def scan_text(src: str, scopes: tuple, markers=REFUSAL) -> dict:
    if not markers:
        raise ValueError("**拒绝字样表是空的 = 拒绝**（空表不许念成『没有拒绝的限制』）")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"解析失败": "第 %s 行：%s" % (exc.lineno, exc.msg)}
    parents, docids = _parents(tree), _doc_ids(tree)
    rows = []
 # 只分**顶层函数**：嵌套函数会被外层一起算进去，逐个再分一次 = 重复计数 + 平方级开销
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            r = classify_function(node, scopes, parents, docids)
            if r:
                rows.append(r)
    hard = [r for r in rows if r["档"].startswith("硬拒")]
    return {"会拒的函数": len(rows), "硬拒型": hard, "授权型条数": len(rows) - len(hard)}


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except Exception:                       # 临时靶（自检用）不在仓里 ⇒ 给全路径，不抛
        return str(p)


def scan_roots(roots: list[str], scopes: tuple, surface_only: bool = False) -> dict:
    gate_rows, rail_rows, unread = [], [], []
    gate_hard = rail_hard = func_total = 0
    for rel in roots:
        base = ROOT / rel
        if not base.is_dir():
            unread.append(rel)                  # 🔴 根不在盘上 ⇒ 写「未读到」，不静默当 0
            continue
        for p in sorted(base.rglob("*.py")):
            if any(s in p.parts for s in _SKIP) or p.name.startswith("_"):
                continue
            relf = _rel(p)
            on_gate = _is_gate_surface(relf)
 # 棘轮/自检只看**门面**（十几件 ⇒ 秒级）；全仓底账由 `scan` 按需跑（30+ 秒）
            if surface_only and not on_gate:
                continue
            try:
                src = p.read_text(encoding="utf-8", errors="replace")
            except Exception:                   # 🔴 读不开 ⇒ 进「未读到」，不当作"没有拒绝"
                unread.append(relf)
                continue
            r = scan_text(src, scopes)
            func_total += r.get("会拒的函数", 0)
            hard = r["硬拒型"] if "硬拒型" in r else []
            if not hard:
                continue
            module_auth = module_uses_auth(ast.parse(src))
            for h in hard:
                h["授权能绕过吗"] = ("函数里有授权线索" if not h["档"].startswith("硬拒")
                               else ("模块里有授权通道（可能可授权）" if module_auth
                                     else "**授权也绕不过**（函数与模块都没有授权线索）"))
            row = {"文件": relf, "域": rel, "会拒函数": r["会拒的函数"], "硬拒型": hard}
            if on_gate:
                gate_hard += len(hard)
                gate_rows.append(row)
            else:
                rail_hard += len(hard)
                rail_rows.append(row)
    gate_rows.sort(key=lambda x: (-len(x["硬拒型"]), x["文件"]))
    rail_rows.sort(key=lambda x: (-len(x["硬拒型"]), x["文件"]))
    claims = claim_report(_fps(gate_rows))
    return {"口径": "**授权型 = 门（主人授权可过）· 门面上的硬拒 = 谁都过不去（这才是要清的）· "
            "护栏 = 质量判据（拦产物合规性，不算限制）**；只看函数粒度、只认字面量 ⇒ 底账不是判决",
            "扫的根": roots, "现读作用域名数": len(scopes),
            "**未读到（读不开的件/根）**": unread,
            "会拒的函数（合计）": func_total,
            "**门面上的硬拒（= 限制）**": gate_hard,
            "护栏里的硬拒（不算限制）": rail_hard,
            "门面逐件": gate_rows, "护栏逐件（前 12）": rail_rows[:12],
            "**未认领（必须有处置）**": claims["**未认领（必须有处置）**"],
            "认领明细": claims["明细"]}


def _fps(gate_rows: list) -> list:
    """门面硬拒的**指纹**（文件|函数，**路径统一正斜杠**）—— 改措辞不算新限制。"""
    return sorted("%s|%s" % (r["文件"].replace("\\", "/"), h["函数"])
                  for r in gate_rows for h in r["硬拒型"])


def census_or_settle(roots: list[str], scopes: tuple, note: str | None,
                     base: Path | None = None, claims: dict | None = None) -> tuple[int, dict]:
    """**只算不打印**：`settle`（带 note 立基线）或 `gate`（门面硬拒不许变多）。"""
    base = base or BASELINE
    r = scan_roots(roots, scopes, surface_only=True)
    fps = _fps(r["门面逐件"])
    if note is not None:
        if not note.strip():
            return 2, {"ok": False, "类别": "未写原因",
                       "拒绝": "**重立基线必须写原因**（每一处硬拒都要有人认领）"}
        base.parent.mkdir(parents=True, exist_ok=True)
        base.write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    "门面硬拒": len(fps), "指纹": fps, "原因": note},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
        return 0, {"ok": True, "类别": "已立基线", "门面硬拒": len(fps), "原因": note,
                   "落盘": (str(base.relative_to(ROOT)) if str(base).startswith(str(ROOT))
                          else str(base))}
    if not base.is_file():
        return 2, {"类别": "未立基线", "判决": "🔴 **未立基线** ⇒ 先 `settle --note <原因>`",
                   "现门面硬拒": len(fps)}
    try:
        b = json.loads(base.read_text(encoding="utf-8"))
        before = set(b["指纹"])
    except Exception as exc:                       # 🔴 读不到/缺字段 ⇒ 拒，不拿空基线当基准
        return 2, {"类别": "未读到基线内容", "判决": "🔴 **未读到基线内容**（%s）⇒ 拒" % str(exc)[:50]}
    new = [f for f in fps if f not in before]
    unclaimed = claim_report(fps, claims)["**未认领（必须有处置）**"]
    ok = not new and not unclaimed
    if ok:
        verdict = "✅ 门面上没有新增「谁都过不去」的拒绝，且每一处都有处置"
    elif unclaimed:
        verdict = ("🔴 **有 %d 处门面硬拒没被认领**（认领表里没有它的处置）⇒ "
                   "补处置：保留（防护）/ 保留（主人红线）/ 假阳性" % len(unclaimed))
    else:
        verdict = ("🔴 **门面上多出 %d 处硬拒**（谁都过不去的那种）⇒ 要么改成人可授权的门，"
                   "要么 `settle --note` 说明为什么必须拒" % len(new))
    return (0 if ok else 1), {
        "类别": ("没变坏" if ok else ("有未认领的硬拒" if unclaimed else "多出硬拒")),
        "基线": b.get("at"), "基线门面硬拒": len(before), "现门面硬拒": len(fps),
        "新增（按指纹）": new[:10], "新增条数": len(new),
        "**未认领（必须有处置）**": unclaimed, "判决": verdict}


def cmd_gate(roots: list[str], scopes: tuple, note: str | None) -> int:
    rc, d = census_or_settle(roots, scopes, note)
    print(json.dumps(d, ensure_ascii=False, indent=1))
    return rc


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    sc = ("deploy_publish", "filesystem_write")
    gated = ("def g():\n"
             "    d = policy.evaluate('k')\n"
             "    if d.scopes:\n"
             "        return {'ok': False, '拒绝': '缺作用域 deploy_publish'}\n")
    ck("**正控：带作用域的拒绝 ⇒ 归『授权型（门）』**",
       scan_text(gated, sc)["授权型条数"] == 1 and not scan_text(gated, sc)["硬拒型"], "")
    hard = "def h():\n    return {'ok': False, '拒绝': '这里谁都别想过'}\n"
    r = scan_text(hard, sc)
    ck("**正控：没有授权线索的拒绝 ⇒ 归『硬拒型』**",
       len(r["硬拒型"]) == 1 and r["硬拒型"][0]["函数"] == "h", str(r["硬拒型"])[:60])
    soft = "def s():\n    return {'状态': '未接线', '为什么': '还没实现'}\n"
    ck("**负控：只是『未实现/未接线』⇒ 不算拒绝**",
       scan_text(soft, sc)["会拒的函数"] == 0, "")
    perm = "def p():\n    raise PermissionError('nope')\n"
    ck("**正控：`raise PermissionError` 也算会拒**",
       len(scan_text(perm, sc)["硬拒型"]) == 1, "")
    try:
        scan_text(hard, sc, markers=())
        ck("**边界：拒绝字样表空 ⇒ 拒绝**", False, "居然没拒")
    except ValueError as exc:
        ck("**边界：拒绝字样表空 ⇒ 拒绝**", "拒绝" in str(exc), str(exc)[:40])
    ck("**边界：语法坏掉的件 ⇒ 如实报『读不了』**",
       "解析失败" in scan_text("def broken(:\n", sc), "")
    live = scan_roots(list(DEFAULT_ROOTS), _scope_names(), surface_only=True)
    ck("**现读真仓跑得动**（作用域名现读非空 · 门面/护栏两个数都读得到）",
       live["现读作用域名数"] > 0 and isinstance(live["**门面上的硬拒（= 限制）**"], int)
       and isinstance(live["护栏里的硬拒（不算限制）"], int),
       "作用域 %d ｜ 门面硬拒 %d ｜ 护栏硬拒 %d"
       % (live["现读作用域名数"], live["**门面上的硬拒（= 限制）**"],
          live["护栏里的硬拒（不算限制）"]))
    ck("**门面判定本身对**（`security/` 算门面 · `*/tools/` 算护栏）",
       _is_gate_surface("gbt_allinone/security/policy.py")
       and not _is_gate_surface("gbt_allinone/tools/libtv_skill.py"),
       "policy=门面 ｜ libtv_skill=护栏")
    # ⑧b 认领表（纯函数）：**每一处门面硬拒都必须有处置**，没处置的要被点名
    ck("**认领：全在表里 ⇒ 未认领为空**",
       claim_report(["a|f"], {"a|f": {"处置": "保留（防护）"}})["**未认领（必须有处置）**"] == [], "")
    ck("**负控：有一处不在表里 ⇒ 必须点名未认领**",
       claim_report(["a|f", "b|g"], {"a|f": {"处置": "保留（防护）"}})
       ["**未认领（必须有处置）**"] == ["b|g"], "")
    ck("**边界：表为空 ⇒ 全部未认领**（不许念成「都已处置」）",
       len(claim_report(["a|f", "b|g"], {})["**未认领（必须有处置）**"]) == 2, "")
    # ⑦b 「授权能绕过吗」这一栏的判据（主人令真正要问的就是这个）
    ck("**授权栏：模块里用了 `auth_gate` ⇒ 判「模块里有授权通道」**",
       module_uses_auth(ast.parse("from . import auth_gate\n")) is True, "")
    ck("**授权栏：模块里没有授权线索 ⇒ 判「授权也绕不过」**",
       module_uses_auth(ast.parse("def f():\n    return 1\n")) is False, "")
    ck("**授权栏：空源码 ⇒ 也不抛**（如实判 False）", module_uses_auth(ast.parse("")) is False, "")
    live_row = [h for r in scan_roots(list(DEFAULT_ROOTS), _scope_names(), surface_only=True)
                ["门面逐件"] for h in r["硬拒型"]]
    ck("**授权栏：现读每一处门面硬拒都带这一栏**",
       bool(live_row) and all(("授权能绕过吗" in h) for h in live_row),
       "%d 处" % len(live_row))
    # ⑨–⑫ 棘轮（基线可注入 ⇒ 四条出口都能真触发；判据建在**结构**上，不建在打印文本上）
    import tempfile as _tf

    with _tf.TemporaryDirectory() as tds:
        bd = Path(tds) / "base.json"
        hard_dir = Path(tds) / "gbt_allinone"
        hard_dir.mkdir()
        (hard_dir / "api.py").write_text(
            "def f():\n    return {'ok': False, '拒绝': '这里谁都别想过'}\n", encoding="utf-8")
        roots = [str(hard_dir)]
 # 合成靶的指纹也得**在认领表里**（否则红的原因是"未认领"而不是"新增"，
        #    控制就咬错了地方 —— 这一条我第一版没做，两条控制当场红给我看）
        fp_api = "%s|f" % str(hard_dir / "api.py").replace("\\", "/")
        fp_gate = "%s|g" % str(hard_dir / "auth_gate.py").replace("\\", "/")
        claims = {fp_api: {"处置": "保留（防护）"}, fp_gate: {"处置": "保留（防护）"}}
        rc, d = census_or_settle(roots, sc, None, bd, claims)
        ck("**棘轮：没立基线 ⇒ rc=2**", rc == 2 and d.get("类别") == "未立基线", d.get("类别"))
        rc, d = census_or_settle(roots, sc, "   ", bd, claims)
        ck("**棘轮：settle 不写原因 ⇒ rc=2**", rc == 2 and d.get("类别") == "未写原因", d.get("类别"))
        rc, d = census_or_settle(roots, sc, "自检用：临时靶立基线", bd, claims)
        ck("**棘轮：正常 settle ⇒ rc=0**",
           rc == 0 and d.get("类别") == "已立基线" and bd.is_file(), d.get("类别"))
        bd.write_text("这不是 json", encoding="utf-8")
        rc, d = census_or_settle(roots, sc, None, bd, claims)
        ck("**棘轮：基线读不成 JSON ⇒ rc=2 且类别=未读到基线内容**",
           rc == 2 and d.get("类别") == "未读到基线内容", d.get("类别"))
        census_or_settle(roots, sc, "自检用：再立一次基线", bd, claims)      # 复原基线
        rc, d = census_or_settle(roots, sc, None, bd, claims)
        ck("**棘轮：没多出来 ⇒ rc=0（没变坏）**",
           rc == 0 and d.get("类别") == "没变坏", d.get("类别"))
        # ⑬ 负控：**认领表里没有它** ⇒ 必须点名「有未认领的硬拒」（哪怕基线里早有它）
        rc, d = census_or_settle(roots, sc, None, bd, {})
        ck("**负控：硬拒没被认领 ⇒ rc=1 且类别=有未认领的硬拒**",
           rc == 1 and d.get("类别") == "有未认领的硬拒" and d.get("**未认领（必须有处置）**"),
           "类别=%s 未认领=%s" % (d.get("类别"), d.get("**未认领（必须有处置）**")))
        (hard_dir / "auth_gate.py").write_text(
            "def g():\n    return {'ok': False, '拒绝': '新加的一处硬拒'}\n", encoding="utf-8")
        rc, d = census_or_settle(roots, sc, None, bd, claims)
        ck("**棘轮：新增一处门面硬拒 ⇒ rc=1 且点名**",
           rc == 1 and d.get("类别") == "多出硬拒" and d.get("新增条数") == 1,
           "类别=%s 新增=%s" % (d.get("类别"), d.get("新增条数")))

    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["scan", "gate", "settle", "selftest"])
    ap.add_argument("--roots", default=",".join(DEFAULT_ROOTS))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--note", help="settle 专用：这次为什么重立基线（**必写**）")
    a = ap.parse_args()
    roots = [x.strip() for x in a.roots.split(",") if x.strip()]
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "gate":
        return cmd_gate(roots, _scope_names(), None)
    if a.cmd == "settle":
        return cmd_gate(roots, _scope_names(), a.note if a.note is not None else "")
    r = scan_roots(roots, _scope_names())
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print("会拒的函数 %d ｜ **门面上的硬拒（= 限制）%d** ｜ 护栏里的硬拒（不算限制）%d ｜ 作用域名 %d"
              % (r["会拒的函数（合计）"], r["**门面上的硬拒（= 限制）**"],
                 r["护栏里的硬拒（不算限制）"], r["现读作用域名数"]))
        for row in r["门面逐件"]:
            print("  【门面】%-44s 会拒 %-3d 硬拒 %d"
                  % (row["文件"], row["会拒函数"], len(row["硬拒型"])))
            for h in row["硬拒型"][:5]:
                print("      L%-5d %-22s %s" % (h["行"], h["函数"], h["样例"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
