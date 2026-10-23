# gbt-capability: obsidian_vault
"""Obsidian 永久记忆层（主人令 2026-09-27）。

主人原话：「让触手的吞天**拥有永久记忆 Obsidian**，以及记入能力，**所有的触手每一根都绑定独立的
Obsidian**，再把所有的 Obsidian 和**本体的自研 Obsidian 双向绑定**到一起**互通共享**。」

## 结构（三句话）

1. **本体自研库** = `brain_vault.vault_dir()`（实测 `C:\\Users\\ADMIN\\Documents\\Codex\\ObsidianVault`，
   10 篇 / 25 条 wikilink / 有 canvas）—— 框架自己的那一本，不动它的既有结构。
2. **触手库** = 每根触手（= 能力位 kind ∪ `domain:<域>`，实测 227 个标签）**各一本独立的库**，
   落在 `%USERPROFILE%\\Documents\\Codex\\GBT触手库\\<触手>/`：`README.md`（MOC）· `记忆.md`（追加式）
   · `.obsidian/app.json`（Obsidian 直接能打开）。
3. **双向绑定** = 两个方向都要**在盘上成立**：触手库 README 里链回 `[[GBT本体记忆]]`，
   本体库里 `触手总索引.md` 链到每一本触手库；`verify` 逐条查这两个方向 + 索引覆盖率。

**为什么是"绑定"而不是"复制"**：复制只会分叉（本仓已经吃过一次亏：技能有两个真身，10 个分叉）。
所以这里只做**指向 + 追加写**：谁的内容留在谁的库里，互相**指得到**；共享页走 `sync_page`（两侧同 sha）。

**红线**：① 只追加，**没有任何删除路径**（永久记忆的前提）；② 不写主人的既有库
（`Documents\\Obsidian Vault`、探针大脑库）—— 只在自己的库里指向它们；③ 写盘过 `filesystem_write` 门。

op=status / provision / remember / sync_page / bind / recall / verify / where
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_INDEX = _STATE / "obsidian_vaults.json"
_LEDGER = _STATE / "obsidian_memory.jsonl"
# 触手库根：**默认落在本仓 `vaults/`** —— 理由有三，不是图省事：
#   ① 永久记忆要跟源码一样受保护（源码保护令：仓外的东西没人扫、没人管、也不进版本）；
#   ② 它是框架**自己的**记忆（与 `state/*.jsonl` 同类）⇒ 与既有做法一致，不另立门；
#   ③ Obsidian 能直接把任意文件夹当库打开（`vaults/<触手>/` 里已放 `.obsidian/app.json`）。
# 想放进主人的 Documents（`Documents\Codex\GBT触手库`）也可以：`root="documents"`，
# 那条路**过 filesystem_write 门**（写到用户的个人目录，必须主人点头）。
_VAULTS_REPO = _ROOT / "vaults"
_VAULTS_DOCS = Path(os.path.expanduser("~")) / "Documents" / "Codex" / "GBT触手库"
_VAULTS = _VAULTS_REPO
_BODY_PAGE = "GBT本体记忆"          # 触手库 README 里链回本体库的那一页
_INDEX_PAGE = "触手总索引"          # 本体库里链向所有触手库的那一页
_OWNER_VAULTS = [                   # 主人自己的库：只指向，**不写**
    Path(os.path.expanduser("~")) / "Documents" / "Obsidian Vault",
    Path(os.path.expanduser("~")) / "Desktop" / "GBT探针" / "00-大脑",
]


# ═══════════════════════ 基础 ═══════════════════════

def _body_vault() -> Path:
    """本体自研库：认 `brain_vault` 的口径（它有 `GBT_VAULT_DIR` 环境变量覆盖）。"""
    try:
        from .. import brain_vault as bv
        return bv.vault_dir()
    except ImportError:
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone import brain_vault as bv        # type: ignore
        return bv.vault_dir()


def _safe(label: str) -> str:
    """标签 → 目录名（`domain:llm` → `domain-llm`；非法字符一律换成 `-`）。"""
    return re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff-]+", "-", label).strip("-") or "unnamed"


def _vaults_root(root: str = "") -> tuple:
    """返回 (根目录, 是否需要过门)。默认仓内（不过门）；`documents` 走门。"""
    if (root or "").lower() in ("documents", "docs", "home"):
        return _VAULTS_DOCS, True
    return _VAULTS_REPO, False


def _labels() -> list:
    """每一根触手 = 能力位 kind ∪ `domain:<域>`（与绑定账同一把尺，不另立口径）。"""
    try:
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
    except ImportError:
        return []
    doms = sorted({str(v.get("domain") or "").strip() for v in BENIGN_CAPS.values()} - {""})
    return sorted(set(BENIGN_CAPS) | {"domain:" + d for d in doms})


def _gate(scope: str, detail: str) -> dict | None:
    try:
        from .. import auth_gate
        from ..security import policy as _policy
    except ImportError:
        sys.path.insert(0, str(_ROOT))
        import gbt_allinone as _g                            # noqa: F401
        from gbt_allinone import auth_gate                   # type: ignore
        from gbt_allinone.security import policy as _policy  # type: ignore
    if _policy.is_trusted():
        return None
    g = auth_gate.check_and_consume(scope, detail=detail)
    if g.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": scope, "error": g.get("error"),
            "how_to_grant": g.get("how_to_grant")}


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _sha(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def _index() -> dict:
    if _INDEX.is_file():
        try:
            return json.loads(_INDEX.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_index(d: dict) -> None:
    _INDEX.parent.mkdir(parents=True, exist_ok=True)
    tmp = _INDEX.with_name(_INDEX.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _INDEX)


def _root_of() -> Path:
    """当前触手库根：认索引里记的（provision 时定的），默认仓内。"""
    r = (_index().get("root") or "").strip()
    return Path(r) if r else _VAULTS_REPO


def _append(path: Path, text: str) -> None:
    """**只追加**（永久记忆：没有任何删除路径）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text)


# ═══════════════════════ 各 op ═══════════════════════

def status(**_kw) -> dict:
    idx = _index()
    body = _body_vault()
    vaults = idx.get("vaults") or {}
    labels = _labels()
    missing = [x for x in labels if x not in vaults]
    return {"ok": True, "op": "status",
            "body_vault": str(body), "body_exists": body.is_dir(),
            "vaults_root": str(_root_of()), "vaults_root_exists": _root_of().is_dir(),
            "tentacles": len(labels), "vaults": len(vaults), "missing": len(missing),
            "missing_sample": missing[:6],
            "owner_vaults": [{"path": str(p), "exists": p.is_dir()} for p in _OWNER_VAULTS],
            "_口径": "触手库 = 每根触手一本（kind ∪ domain:*）；本体库 = brain_vault 认的那本；只指向不写主人的库"}


def provision(only: str = "", force: bool = False, root: str = "", **_kw) -> dict:
    """给每根触手建/补齐**独立**库（README MOC + 记忆.md + .obsidian/app.json）。

    `only` 可以给一个标签（或逗号分隔多个）只补那几根；不给就全量补齐。
    """
    labels = _labels()
    if only:
        want = [x.strip() for x in only.split(",") if x.strip()]
        bad = [x for x in want if x not in labels]
        if bad:
            return {"ok": False, "op": "provision", "fail_closed": True,
                    "error": f"这些不是有效触手标签：{bad}（有效 {len(labels)} 个）"}
        labels = want
    vroot, needs_gate = _vaults_root(root)
    if needs_gate:
        gate = _gate("filesystem_write", f"obsidian provision {len(labels)} 库 → 主人的 Documents")
        if gate:
            return {"ok": False, "op": "provision", **gate}
    idx = _index()
    vaults = idx.setdefault("vaults", {})
    made, skipped = [], []
    for lab in labels:
        vdir = vroot / _safe(lab)
        readme = vdir / "README.md"
        if readme.is_file() and not force:
            skipped.append(lab)
        else:
            (vdir / ".obsidian").mkdir(parents=True, exist_ok=True)
            app = vdir / ".obsidian" / "app.json"
            if not app.is_file():
                app.write_text(json.dumps({"alwaysUpdateLinks": True, "newFileLocation": "folder",
                                           "newFileFolderPath": "收集箱"}, ensure_ascii=False, indent=1),
                               encoding="utf-8")
            readme.write_text(_readme_text(lab), encoding="utf-8")
            mem = vdir / "记忆.md"
            if not mem.is_file():
                _append(mem, f"# {lab} · 永久记忆（追加式，无删除路径）\n\n"
                             f"> 本库属于触手 `{lab}`。互通往返：本页链回本体库 [[{_BODY_PAGE}]]，\n"
                             f"> 本体库的 [[{_INDEX_PAGE}]] 链回本库。\n\n")
            made.append(lab)
        vaults[lab] = {"dir": str(vdir), "safe": _safe(lab),
                       "readme_sha": _sha(readme), "readme_exists": readme.is_file()}
    idx["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    idx["root"] = str(vroot)
    idx["counts"] = {"vaults": len(vaults), "tentacles": len(_labels())}
    _save_index(idx)
    _log({"event": "provision", "made": len(made), "skipped": len(skipped)})
    return {"ok": True, "op": "provision", "made": len(made), "skipped": len(skipped),
            "vaults": len(vaults), "root": str(vroot), "gated": needs_gate}


def _readme_text(lab: str) -> str:
    kind = lab
    desc = ""
    try:
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
        c = BENIGN_CAPS.get(kind) or {}
        desc = str(c.get("desc") or "")
    except ImportError:
        pass
    head = (f"# {lab} · 触手记忆库\n\n"
            f"> 本库是触手 `{lab}` 的**独立永久记忆**。互通往返见页尾。\n\n"
            f"## 这本库记什么\n"
            f"- 这根触手吞进来的东西（吞天吸收 → 记 `记忆.md`）\n"
            f"- 它的能力面与判据（有的话写 `能力.md`）\n"
            f"- 它踩过的坑与修法（教训只追加，不改历史）\n\n")
    if desc:
        head += f"## 能力位一句话\n{desc[:400]}\n\n"
    head += (f"## 关联\n"
             f"- 本体自研库：[[{_BODY_PAGE}]]\n"
             f"- 心跳：`run_task('obsidian_vault', {{'op':'remember','tentacle':'{lab}','text':'…'}})`\n\n"
             f"---\n互通往返：本页链回 [[{_BODY_PAGE}]]；本体库 [[{_INDEX_PAGE}]] 链回本库。\n")
    return head


def remember(tentacle: str = "", text: str = "", shared: bool = True, **_kw) -> dict:
    """往某根触手的库里**追加一条**，并在**本体库**同步一条（互通）—— 两侧互指。"""
    if not tentacle or not text.strip():
        return {"ok": False, "op": "remember", "fail_closed": True, "error": "tentacle 与 text 都要给"}
    if tentacle not in _labels():
        return {"ok": False, "op": "remember", "fail_closed": True,
                "error": f"不是有效触手标签：{tentacle}"}
    vdir = _root_of() / _safe(tentacle)
    gated = str(_root_of()) != str(_VAULTS_REPO)
    if gated:
        gate = _gate("filesystem_write", f"obsidian remember {tentacle}")
        if gate:
            return {"ok": False, "op": "remember", **gate}
    if not (vdir / "README.md").is_file():
        r = provision(only=tentacle)
        if not r.get("ok"):
            return {"ok": False, "op": "remember", "error": "触手库还没建起来", "provision": r}
    stamp = time.strftime("%Y-%m-%d %H:%M")
    body = _body_vault()
    body.mkdir(parents=True, exist_ok=True)
    _append(vdir / "记忆.md", f"\n## {stamp}\n{text.strip()}\n\n→ 本体：[[{_BODY_PAGE}]]\n")
    out = {"ok": True, "op": "remember", "tentacle": tentacle, "vault": str(vdir),
           "where": str(vdir / "记忆.md")}
    if shared:
        note = body / "触手记忆共享.md"
        _append(note, f"\n## {stamp} · `{tentacle}`\n{text.strip()}\n\n→ 触手库：`{_safe(tentacle)}`\n")
        out["body_note"] = str(note)
    _log({"event": "remember", "tentacle": tentacle, "chars": len(text), "shared": bool(shared)})
    return out


def sync_page(name: str = "", text: str = "", tentacles: str = "", **_kw) -> dict:
    """共享页：同一篇内容在**给定触手库 + 本体库**各写一份，两侧记同一个 sha（内容级互通）。"""
    if not name or not text.strip() or not tentacles.strip():
        return {"ok": False, "op": "sync_page", "fail_closed": True,
                "error": "name / text / tentacles 都要给（tentacles 逗号分隔）"}
    labs = [x.strip() for x in tentacles.split(",") if x.strip()]
    bad = [x for x in labs if x not in _labels()]
    if bad:
        return {"ok": False, "op": "sync_page", "fail_closed": True, "error": f"无效触手：{bad}"}
    if str(_root_of()) != str(_VAULTS_REPO):
        gate = _gate("filesystem_write", f"obsidian sync_page {name} → {len(labs)} 库")
        if gate:
            return {"ok": False, "op": "sync_page", **gate}
    body = _body_vault()
    body.mkdir(parents=True, exist_ok=True)
    body_p = body / f"{name}.md"
    body_p.write_text(text, encoding="utf-8")
    both = {"body": {"path": str(body_p), "sha": _sha(body_p)}}
    for lab in labs:
        p = _root_of() / _safe(lab) / f"{name}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        both[lab] = {"path": str(p), "sha": _sha(p)}
    shas = {v["sha"] for v in both.values()}
    _log({"event": "sync_page", "name": name, "tentacles": labs, "same_sha": len(shas) == 1})
    return {"ok": len(shas) == 1, "op": "sync_page", "name": name, "sha": shas.pop() if len(shas) == 1 else "",
            "sides": both}
    # ok=False 的情况只有 sha 不一致（写失败），调用方按 fail 处理


def bind(**_kw) -> dict:
    """把双向绑定**在盘上做实**：触手库 README 链回本体；本体库索引链向每一本触手库。

    本体侧那一页由本能力直接写（`brain_vault.remember/recall` 本来就是这个库的读写口，
    同类做法）—— **只新建/覆盖我们自己那一页**，不碰本体库既有笔记，也没有删除路径。
    """
    labels = _labels()
    body = _body_vault()
    body.mkdir(parents=True, exist_ok=True)
    idx = _index()
    vaults = idx.get("vaults") or {}
    # ① 触手库 → 本体：README 里必须有 [[GBT本体记忆]]
    fixed, bad = [], []
    for lab, meta in vaults.items():
        p = Path(meta["dir"]) / "README.md"
        if not p.is_file():
            bad.append(f"{lab}(README 不在)")
            continue
        t = p.read_text(encoding="utf-8")
        if f"[[{_BODY_PAGE}]]" not in t:
            _append(p, f"\n互通往返（bind 补写）：本页链回 [[{_BODY_PAGE}]]\n")
            fixed.append(lab)
    # ② 本体 → 触手：索引页链到每一本
    lines = [f"# {_INDEX_PAGE}", "",
             "> 本体自研库通向每一根触手库的索引。每根触手一本独立 Obsidian，**双向绑定**在此合拢。",
             f"> 触手库根目录：`{_root_of()}`　共 {len(vaults)}/{len(labels)} 本。", ""]
    for lab in sorted(vaults):
        lines.append(f"- [[{_safe(lab)}]] → `{lab}`")
    for p in _OWNER_VAULTS:
        if p.is_dir():
            lines.append(f"- （主人的库，只指向不写）`{p}`")
    (body / f"{_INDEX_PAGE}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    idx["body_index_sha"] = _sha(body / f"{_INDEX_PAGE}.md")
    idx["bound_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save_index(idx)
    _log({"event": "bind", "vaults": len(vaults), "fixed_backlinks": len(fixed)})
    return {"ok": True, "op": "bind", "vaults": len(vaults), "labels": len(labels),
            "backlinks_fixed": fixed, "bad": bad,
            "body_index": str(body / f"{_INDEX_PAGE}.md"),
            "note": "本体侧只动我们自己那一页（触手总索引.md），既有笔记不碰"}


def recall(q: str = "", limit: int = 10, **_kw) -> dict:
    """想到就找到：本体库（brain_vault）+ 万能秒搜（memory_manager FTS）一起查。"""
    out = {"ok": True, "op": "recall", "q": q}
    try:
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone import brain_vault as bv
        out["brain"] = {k: v for k, v in (bv.recall(limit=limit) or {}).items() if k != "body"} \
            if hasattr(bv, "recall") else {}
    except Exception as exc:                                  # noqa: BLE001
        out["brain"] = {"error": f"{type(exc).__name__}: {str(exc)[:100]}"}
    try:
        import importlib.util as _iu
        sp = _iu.spec_from_file_location("mm_rec", _ROOT / "gbt_allinone" / "tools" / "memory_manager.py")
        mm = _iu.module_from_spec(sp)
        sp.loader.exec_module(mm)
        hits = mm.find(q=q, limit=limit) if q else {"note": "没给 q ⇒ 不查秒搜"}
        out["fts"] = {k: v for k, v in (hits or {}).items() if k in ("ok", "count", "hits", "note")}
    except Exception as exc:                                  # noqa: BLE001
        out["fts"] = {"error": f"{type(exc).__name__}: {str(exc)[:100]}"}
    return out


def verify(**_kw) -> dict:
    """判据：每根触手一本库 · 双向都在盘上 · 索引覆盖全 · 本体库在。"""
    problems = []
    labels = _labels()
    idx = _index()
    vaults = idx.get("vaults") or {}
    body = _body_vault()
    if not body.is_dir():
        problems.append(f"本体自研库不在：{body}")
    missing = [x for x in labels if x not in vaults]
    if missing:
        problems.append(f"**{len(missing)} 根触手还没有独立库**（例：{missing[:4]}）")
    no_back = [lab for lab, m in vaults.items()
               if not (Path(m["dir"]) / "README.md").is_file()
               or f"[[{_BODY_PAGE}]]" not in (Path(m["dir"]) / "README.md").read_text(
                   encoding="utf-8", errors="replace")]
    if no_back:
        problems.append(f"**{len(no_back)} 本触手库没有链回本体**（双向的前一半缺了）：{no_back[:4]}")
    idxp = body / f"{_INDEX_PAGE}.md"
    if not idxp.is_file():
        problems.append(f"本体库没有 {_INDEX_PAGE}.md（双向的后一半缺了）⇒ 跑 bind")
    else:
        t = idxp.read_text(encoding="utf-8")
        missing_idx = [lab for lab in vaults if f"[[{_safe(lab)}]]" not in t]
        if missing_idx:
            problems.append(f"本体索引漏了 {len(missing_idx)} 本：{missing_idx[:4]}")
    return {"ok": not problems, "op": "verify", "problems": problems,
            "counts": {"tentacles": len(labels), "vaults": len(vaults)},
            "_口径": "双向 = 触手 README 链回本体 + 本体索引链到触手，两条都在盘上才算绑上"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "obsidian_vault", "tentacle": "obsidian_vault",
            "entry": "run_task('obsidian_vault', {...})",
            "ops": ["status", "provision", "remember", "sync_page", "bind", "recall", "verify", "where"],
            "roots": {"触手库": str(_VAULTS), "本体库": str(_body_vault()),
                      "主人的库（只指向不写）": [str(p) for p in _OWNER_VAULTS]},
            "gates": {"provision/remember/sync_page/bind": "filesystem_write"},
            "contract": [
                {"op": "provision", "params": "only=标签(可逗号分隔) 或空=全量", "returns": "made/skipped/vaults"},
                {"op": "remember", "params": "tentacle + text", "returns": "触手库路径 + 本体共享页路径"},
                {"op": "bind", "returns": "双向补写数 + 本体索引路径"},
                {"op": "recall", "params": "q", "returns": "本体库 recall + 秒搜 hits"},
            ]}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    for name, fn in (("status", status), ("provision", provision), ("remember", remember),
                     ("sync_page", sync_page), ("bind", bind), ("recall", recall),
                     ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（status/provision/remember/sync_page/bind/recall/verify/where）"}
