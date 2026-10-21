"""GBT小土豆V8 · 一指定江山乾坤换位 + AI 接管部署队列。

Owner 定调（2026-09-11）：抓取→镜像→验证→晋升一条命令完成；
部署平台 AI 接管队列——一个项目上线，自动开始下一个。

一指定江山乾坤换位（one_key_deploy）：
  输入一个目标（GitHub 目录 URL / 本地目录），全自动：
    吞噬抓取 → 镜像部署区成形 → 署名注入 → 验证矩阵 → 一次性晋升生产 → 护照落盘
  任何一步失败如实报，绝不半成品上线。

AI 接管队列（deploy_queue）：
  submit  提交项目入队（target + 名字）
  tick    取下一个待部署项目，跑 one_key_deploy 全流程，成功标记 done
  status  队列全景（待部署/部署中/完成/失败）
"""
import json
import time
import urllib.request
from pathlib import Path

from . import _paths

_BASE = Path(__file__).resolve().parent
_STORE = _paths.STORE_DIR        # O35：单一来源（曾硬编码 _BASE / "store"，绕开 GBT_STORE_DIR）
_QUEUE = _STORE / "deploy" / "queue.json"
_SIGNATURE = "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"
# 只对"文本页"做解码+署名注入（与 signature.py 的页面口径一致）；其余一律逐字节镜像，
# 免得把 PNG/GLB/字体当文本读写 —— 那会把镜像里的产物当场弄成废物。
_PAGE_SUFFIX = {".md", ".html", ".htm", ".txt", ".csv"}


def _audit(event, meta):
    try:
        from .store import audit
        audit(event, meta)
    except Exception:
        pass


def _load_q() -> dict:
    if _QUEUE.exists():
        try:
            return json.loads(_QUEUE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"next_id": 1, "items": []}


def _save_q(q: dict):
    _QUEUE.parent.mkdir(parents=True, exist_ok=True)
    _QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 一指定江山乾坤换位 ──

def _gh_api(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "GBT-Devour", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _devour_tree_to_stage(api_url, raw_base, prefix="") -> int:
    """递归吞噬 GitHub 目录树入镜像部署区。"""
    from . import mirror_space as DG
    items = json.loads(_gh_api(api_url))
    n = 0
    for it in items:
        rel = prefix + it["name"]
        if it["type"] == "file":
            if it["name"].endswith((".map", ".md", ".gitignore", "package.json", "package-lock.json")):
                continue   # 部署无关物
            raw = _gh_api(it["download_url"])
            # 🔴 2026-09-26 修：原来对所有文件一律 utf-8 replace 解码 —— 二进制（png/glb/字体）
            #    被替换字符污染，晋升出去就是坏的。与本地模式同口径：文本页解码加工，其余逐字节 shape_bytes。
            if it["name"].endswith((".html", ".htm", ".css", ".js", ".json", ".svg", ".txt", ".xml")):
                content = raw.decode("utf-8", errors="replace")
                if it["name"].endswith((".html", ".htm")):
                    sig = f"\n<!-- {_SIGNATURE} -->\n"
                    content = content.replace("</body>", sig + "</body>", 1) if "</body>" in content else content + sig
                DG.shape(rel, content, f"乾坤换位吞噬 {rel}")
            else:
                DG.shape_bytes(rel, raw, f"乾坤换位吞噬 {rel}")
            n += 1
        elif it["type"] == "dir":
            n += _devour_tree_to_stage(it["url"], raw_base, rel + "/")
    return n


def _parse_github_target(target: str):
    """解析 GitHub 目标 → (api_url, raw_base)。支持 repo / repo/tree/branch/path。"""
    t = target.strip().rstrip("/")
    if not t.startswith("http"):
        t = "https://" + t
    # https://github.com/owner/repo/tree/branch/sub/path
    if "/tree/" in t:
        head, tail = t.split("/tree/", 1)
        parts = tail.split("/", 1)
        branch = parts[0]
        sub = parts[1] if len(parts) > 1 else ""
        api = f"{head.replace('github.com', 'api.github.com/repos')}/contents/{sub}?ref={branch}"
        raw = f"{head.replace('github.com', 'raw.githubusercontent.com')}/{branch}/{sub}"
        return api, raw
    # https://github.com/owner/repo
    api = t.replace("github.com", "api.github.com/repos") + "/contents"
    raw = t.replace("github.com", "raw.githubusercontent.com") + "/master"
    return api, raw


def _project_files(root: Path):
    """遍历项目文件；跳过版本库/临时残留（它们不是产物）。"""
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        parts = set(f.relative_to(root).parts)
        if "__pycache__" in parts or ".git" in parts:
            continue
        if f.suffix.lower() in (".pyc", ".tmp"):
            continue
        yield f, f.relative_to(root).as_posix()


def _stage_project(root: Path, write_text, write_bytes) -> int:
    """把项目搬进**某个维度**：文本页注入署名走文本路，其余逐字节。返回落盘文件数。

    `write_text(rel, text)` / `write_bytes(rel, data)` 由调用方注入 ——
    全局镜像走 `mirror_space`，隔离房间走 `room_space`，同一套搬迁逻辑不写两遍。
    """
    from . import signature as _sig
    n = 0
    for f, rel in _project_files(root):
        raw = f.read_bytes()
        if f.suffix.lower() in _PAGE_SUFFIX:
            try:
                text = raw.decode("utf-8")          # 严格解码：解不出就当二进制，不硬转
            except UnicodeDecodeError:
                text = None
            if text is not None:
                if write_text(rel, _sig.inject(text, rel)).get("ok"):
                    n += 1
                continue
        if write_bytes(rel, raw).get("ok"):
            n += 1
    return n


def _deploy_into_room(room_id: str, target: str, purpose: str, label: str,
                      owner_override: bool = False, override_reason: str = "") -> dict:
    """把项目搬进**房间维度**（镜像多维度里的隔离空间）—— 全局生产面分毫不动。

    `owner_override` / `override_reason` 一路透传给 `room_space.release` 的
    「排练/门禁未过」那一关（同一条主人授权、同一个理由，不在中间吞掉）。
    """
    from . import room_space as RS
    t0 = time.time()
    p = Path(target)
    if not (p.exists() and p.is_dir()):
        return {"ok": False, "room_id": room_id,
                "error": f"房间模式只支持本地目录（且必须存在）: {target}"}
    made = RS.create(room_id, purpose or f"一次性部署 {label}")
    if not made.get("ok"):
        return {"ok": False, "room_id": room_id, "error": f"房间不可用: {made.get('error')}"}

    files = _stage_project(
        p,
        lambda rel, txt: RS.shape(room_id, rel, txt, f"房间镜像 {rel}"),
        lambda rel, raw: RS.shape_bytes(room_id, rel, raw, f"房间镜像 {rel}"),
    )
    if not files:
        return {"ok": False, "room_id": room_id, "error": "吞噬为空（目标无可部署文件）"}

    steps = {"stage": {"ok": True, "files": files}}
    # 2026-10-21 修：入口名从 room_space.ENTRY_NAMES 取（此前这里自己又抄了一份四个字面量，
    # 与 scan/simulate 里的那份各算各的）。且**没有一个入口就别立计划** —— 此前会立一份
    # entrypoints=[] 的计划，静态推演第 4 关永远过不了，调用方只看到“静态推演未全绿”，
    # 完全不知道真实原因是“目标树里根本没有入口”。
    rels = [rel for _f, rel in _project_files(p)]
    entries = [r for r in rels if r.split("/")[-1] in RS.ENTRY_NAMES]
    if not entries:
        return {"ok": False, "room_id": room_id, "name": label, "files": files,
                "steps": steps,
                "error": ("目标树没有可识别的入口（" + " / ".join(RS.ENTRY_NAMES) + "）—— "
                          "房间体检与静态推演都要求入口；文档型产物请补一个 index.html，"
                          "或在 room_plan 里显式声明 architecture.entrypoints"),
                "law": "房间维度=隔离排练；全局生产面分毫未动"}
    # 房间还没计划 → 自动立一份（仍在同一条已授权调用内），验收命令 = **真跑**语法扫，
    # 且不往房间维度树里写任何东西（写了会被"排练改变了维度树"当场判失效）。
    try:
        RS.get_plan(room_id)
        steps["plan"] = {"ok": True, "auto": False}
    except Exception:  # noqa: BLE001
        import sys as _sys
        code = ("import ast,pathlib;"
                "[ast.parse(x.read_text(encoding='utf-8')) for x in pathlib.Path('.').rglob('*.py')];"
                "print('py-syntax-ok')")
        RS.define_plan(room_id, {
            "goal": f"一次性部署 {label}：房间维度成形 + 语法级验收",
            "assumptions": [{"id": "A1", "statement": "房间与目标环境同主机、同一运行时",
                             "verify": "environment.production.mode=same_host"}],
            "architecture": {
                "components": [{"id": "artifact", "responsibility": "待晋升的完整房间产物树",
                                "depends_on": []}],
                "entrypoints": entries, "data_flow": []},
            "steps": [{"id": "S1", "action": "固化房间维度树指纹", "depends_on": []},
                      {"id": "S2", "action": "在房间维度内跑验收命令", "depends_on": ["S1"]},
                      {"id": "S3", "action": "全绿后写入房间现实区", "depends_on": ["S2"]}],
            "services": [],
            "files": rels,
            "environment": {"required": [], "dependencies": [], "tools": ["python"],
                            "required_files": [], "production": {"mode": "same_host"}},
            "rehearsal": {
                "commands": [{"id": "py-syntax-sweep",
                              "argv": [_sys.executable, "-c", code], "timeout": 300}],
                "acceptance": ["py-syntax-sweep"]},
            "rollback": {"strategy": "room_snapshot_replay",
                         "note": "回滚到房间上一个快照；房间现实区整树替换，全局生产不受影响"},
        })
        steps["plan"] = {"ok": True, "auto": True, "acceptance": "py-syntax-sweep"}

    sc = RS.scan(room_id)
    steps["scan"] = {"ok": sc.get("ok"), "passed": sc.get("passed"), "total": sc.get("total")}
    if not sc.get("ok"):
        return {"ok": False, "room_id": room_id, "name": label, "files": files,
                "steps": steps, "error": "房间体检未过，未晋升",
                "law": "房间维度=隔离排练；全局生产面分毫未动"}

    # 排练与放行都要求房间内有计划（room_plan）。没有计划就**如实卡住**，不假装通过。
    blocked_reason = ""
    try:
        rh = RS.rehearse(room_id)
    except Exception as exc:  # noqa: BLE001
        rh = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
        blocked_reason = "房间内还没有 rehearsal 计划（先 room_plan）"
    steps["rehearse"] = {"ok": rh.get("ok"), "blockers": rh.get("blockers"),
                         "error": rh.get("error")}
    rl = {"ok": False, "blocked": True}
    if rh.get("ok"):
        try:
            rl = RS.release(room_id, purpose or f"一次性部署 {label}",
                            owner_override=owner_override, override_reason=override_reason)
        except Exception as exc:  # noqa: BLE001
            rl = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    steps["release"] = {"ok": rl.get("ok"), "blocked": rl.get("blocked"), "error": rl.get("error")}
    return {
        "ok": bool(rl.get("ok")), "room_id": room_id, "name": label, "target": target,
        "files": files, "elapsed_s": round(time.time() - t0, 1), "steps": steps,
        "blocked_reason": blocked_reason or None,
        "law": "房间维度=隔离排练现实；全局生产面分毫未动（要进全局仍需显式 into_global_production）",
    }


def one_key_deploy(target: str, purpose: str = "", plan=None, name: str = "",
                   room: str = "", into_global_production: bool = False,
                   owner_override: bool = False, override_reason: str = "") -> dict:
    """一指定江山乾坤换位：抓取→镜像→验证→晋升，一条命令一步到位。

    target: GitHub 仓库/子目录 URL（也可为本地路径——本地模式直接镜像入 stage）

    2026-09-19（Owner：**所有假设/模拟/测试都在镜像多维度里跑，只有过镜像的成品才进生产**）：
      ① 本层只做"成形 → 在**镜像区**验证 → 一次性晋升"，**不承接部署计划**；
        传了 `plan` 一律 fail-closed 并给出去处（与 `api.mirror_ascend` 同一条口径），
        免得计划被静默吞掉、变成"以为跑了其实没跑"。
      ② 本地模式此前把**每个文件都当文本读**（`errors="replace"`）⇒ 图片/模型/字体当场被
        替换字符污染，镜像里的产物直接是废的，晋升出去就是"上线了一个坏的"。
        现在分两路：**文本页**（.md/.html/.htm/.txt/.csv）解码成功后**注入署名**再入镜像
        （幂等，与 GitHub 模式的"署名注入"一致）；**其余一律逐字节**走 `shape_bytes`。
      ③ 验证矩阵（`mirror_space.scan()`）读的是**镜像维度**本身 —— 也就是"测试跑在镜像里"。
      ④ `name` 只用于口令与审计留痕，不改变部署语义。

    🔴 2026-10-13（主人令：「**技术层面不能给她有限制只保留人工授权护栏即可**」·
       「**直接改成终端YES才能使用就好了有时候我需要用到的啊**」）：
      「未声明落点」**不再是死路**。默认照旧卡住并给出怎么放行；
      主人在终端发**专用一次性钥匙** `deploy_force`（提示符 YES）+ 调用方显式
      `owner_override=true` ⇒ 按"全局生产"放行，
      且**大声落审计** `one_key_deploy_landing_overridden`（含目标与理由）。
      钥匙由**门外那道门**认（`policy.evaluate` 见 `owner_override` 就改要 `deploy_force`）⇒
      旗标不带授权，模型无法自我解锁。
      ⚠️ 这一条放行 = 不声明落点也写**全局生产**：它就是本仓唯一的生产落点保护，
      放行前请看清 `steps.landing_override.route`。
    """
    from . import mirror_space as DG
    if plan is not None:
        return {"ok": False, "blocked": True,
                "target": str(target)[:80], "cap": "one_key_deploy",
                "reason": "本层不支持 plan（部署计划属于排练门，不塞进一次性晋升）",
                "how_to": "计划/推演走 mirror_plan → mirror_simulate → mirror_rehearse；"
                          "本层只做 抓取 → 镜像 → 验证 → 晋升。"}
    t0 = time.time()
    steps = {}
    label = (name or target)[:60]

    # 0) 落点必须**显式声明**（Owner 2026-09-19：假设/模拟/测试全在镜像多维度里跑，
    #    只有过了镜像的成品才进生产）—— 不许默认把任何项目堆进全局生产面。
    if not room and not into_global_production:
        if not owner_override:
            return {
                "ok": False, "blocked": True, "cap": "one_key_deploy",
                "target": str(target)[:80], "name": label,
                "reason": "未声明落点：不许默认把项目堆进全局生产面（否则什么代码都会被送到生产）",
                "how_to": ("隔离试验走 room=\"<房间名>\" —— 只写房间维度，全局生产分毫不动；"
                           "确要写全局生产，显式传 into_global_production=true"
                           "（经 run_task 会另要 deploy_publish 人工授权）。"),
                "如何放行": ("要**不声明落点**也跑：主人在终端发**专用一次性钥匙** `deploy_force`"
                          "（python -m gbt_allinone auth grant --scope deploy_force --ttl 600，提示符敲 YES），"
                          "再带 owner_override=true 重调 —— 那会按'全局生产'放行并写审计；"
                          "但这等于绕开落点声明这一步，推荐仍用 into_global_production=true 明写。")}
        _reason = str(override_reason or purpose or "(未写理由)")[:200]
        _audit("one_key_deploy_landing_overridden",
               {"target": str(target)[:60], "reason": _reason})
        into_global_production = True
        steps["landing_override"] = {
            "ok": True, "route": "global_production",
            "reason": _reason,
            "依据": "主人终端授权（deploy_force · 专用一次性钥匙 · 提示符 YES）+ 调用方显式 owner_override",
            "note": "未声明落点被人工放行 ⇒ 目标直接写全局生产面",
        }
    if room:
        return _deploy_into_room(str(room), target, purpose, label,
                                 owner_override=owner_override,
                                 override_reason=override_reason)

    # 1) 吞噬抓取 → 镜像区
    try:
        if target.startswith(("http://", "https://")) and "github.com" in target:
            api, raw = _parse_github_target(target)
            n = _devour_tree_to_stage(api, raw)
            steps["devour"] = {"ok": n > 0, "files": n}
        else:
            # 本地目录模式：全量镜像入 stage
            p = Path(target)
            if not p.exists() or not p.is_dir():
                return {"ok": False, "error": f"目标不存在或不是目录: {target}"}
            from . import signature as _sig
            n = 0
            for f in p.rglob("*"):
                if not f.is_file():
                    continue
                parts = set(f.relative_to(p).parts)
                if "__pycache__" in parts or ".git" in parts:
                    continue          # 临时/版本库残留，不是产物
                if f.suffix.lower() in (".pyc", ".tmp"):
                    continue
                rel = f.relative_to(p).as_posix()
                raw_bytes = f.read_bytes()
                staged = None
                if f.suffix.lower() in _PAGE_SUFFIX:
                    try:
                        text = raw_bytes.decode("utf-8")     # 严格解码：解不出就当二进制，不硬转
                        staged = DG.shape(rel, _sig.inject(text, rel), f"本地镜像 {rel}")
                    except UnicodeDecodeError:
                        staged = None
                if staged is None:
                    staged = DG.shape_bytes(rel, raw_bytes, f"本地镜像 {rel}")
                if staged.get("ok"):
                    n += 1
            steps["devour"] = {"ok": n > 0, "files": n}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"吞噬抓取失败: {str(e)[:120]}", "steps": steps}

    if not steps["devour"]["ok"]:
        return {"ok": False, "error": "吞噬为空（目标无可部署文件）", "steps": steps}

    # 2) 验证矩阵
    v = DG.scan()
    steps["validate"] = {"ok": v.get("ok"), "passed": v.get("passed"), "total": v.get("total"),
                          "failed": [k for k, c in v.get("checks", {}).items() if not c.get("ok")]}
    if not v.get("ok"):
        _audit("one_key_deploy_blocked", {"target": target[:60], "failed": steps["validate"]["failed"]})
        return {"ok": False, "blocked": True, "reason": "验证未全绿", "steps": steps, "validate": v}

    # 3) 一次性晋升
    pr = DG.ascend(purpose or f"乾坤换位: {target[:60]}")
    steps["promote"] = {"ok": pr.get("ok"), "version": pr.get("version"), "files": pr.get("files")}
    if not pr.get("ok"):
        return {"ok": False, "error": "晋升失败", "steps": steps, "promote": pr}

    result = {"ok": True, "target": target, "name": label, "files": steps["devour"]["files"],
              "version": pr.get("version"), "promoted_at": pr.get("promoted_at"),
              "elapsed_s": round(time.time() - t0, 1), "steps": steps,
              "law": "生产零修改：一次性全量晋升，镜像区随便改，生产只有成品"}
    _audit("one_key_deploy", {"target": target[:60], "name": label, "files": result["files"],
                               "version": result["version"], "elapsed_s": result["elapsed_s"]})
    return result


# ── AI 接管部署队列 ──

def queue_submit(target: str, name: str = "") -> dict:
    """提交项目入队。AI 部署完一个自动取下一个。"""
    q = _load_q()
    item = {"id": f"Q{q['next_id']:04d}", "target": target, "name": name or target.split("/")[-1][:40],
            "status": "pending", "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    q["next_id"] += 1
    q["items"].append(item)
    _save_q(q)
    _audit("deploy_queue_submit", {"id": item["id"], "target": target[:60]})
    return {"ok": True, "queued": item["id"], "name": item["name"], "position": len(q["items"])}


def queue_tick() -> dict:
    """取下一个待部署项目，跑一指定江山全流程（AI 接管：部署完这个自动可下一个）。"""
    q = _load_q()
    pending = [i for i in q["items"] if i["status"] == "pending"]
    if not pending:
        return {"ok": True, "idle": True, "note": "队列空——全部完成或无待部署项"}
    item = pending[0]
    item["status"] = "deploying"
    item["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save_q(q)

    # 🔴 2026-09-26 修（死队列）：原来不传 room/into_global_production ⇒ one_key_deploy
    #    按「未声明落点」fail-closed 拒绝 ⇒ 每个队列项必然 failed，AI 接管部署队列整条链路是死的。
    #    现在队列项必须自带 room（生产面红线：不声明落点不许部署）；没带的如实记 blocked，不冒充 failed。
    room = str(item.get("room") or "").strip()
    if not room:
        item["status"] = "blocked"
        item["result"] = {"ok": False,
                          "error": "未声明落点：队列项缺 room 字段（生产面红线 —— 给队列项补 room 后重试）"}
        item["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _save_q(q)
        _audit("deploy_queue_tick", {"id": item["id"], "status": "blocked", "reason": "no_room"})
        return {"ok": False, "blocked": item["id"],
                "reason": "队列项未声明 room，按红线不开部署",
                "next_pending": len([i for i in q["items"] if i["status"] == "pending"])}
    r = one_key_deploy(item["target"], room=room, purpose=f"队列 {item['id']}: {item['name']}")
    item["result"] = {"ok": r.get("ok"), "version": r.get("version"), "files": r.get("files"),
                       "elapsed_s": r.get("elapsed_s"),
                       "error": r.get("error") or r.get("reason")}
    item["status"] = "done" if r.get("ok") else "failed"
    item["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save_q(q)
    _audit("deploy_queue_tick", {"id": item["id"], "status": item["status"], "version": r.get("version")})
    return {"ok": True, "deployed": item["id"], "status": item["status"],
            "next_pending": len([i for i in q["items"] if i["status"] == "pending"]),
            "result": r}


def queue_status() -> dict:
    q = _load_q()
    from collections import Counter
    by = dict(Counter(i["status"] for i in q["items"]))
    return {"ok": True, "total": len(q["items"]), "by_status": by, "items": q["items"][-20:]}
