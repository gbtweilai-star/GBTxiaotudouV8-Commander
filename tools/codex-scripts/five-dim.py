# -*- coding: utf-8 -*-
"""五维合一同步执行 + 万能插 · **DSH 侧默认入口**（一条命令，消除摩擦）

为什么不直接敲 sync_exec：它自己的注释写着「一条没人愿意用的纪律等于没有纪律」。
本包装器把两件事并成一条命令：
  · 五维合一（脑-眼-耳-嘴-手）：open / close / ruler / run
  · 万能插（能力位唯一门）：    cap <kind> [payload]

用法:
  python tools/codex-scripts/five-dim.py ruler
  python tools/codex-scripts/five-dim.py open  "这一步干什么" [观察目标路径...]
  python tools/codex-scripts/five-dim.py run   "目标" [观察目标路径...]
  python tools/codex-scripts/five-dim.py close <step_id> "证据1" ["证据2"...]
  python tools/codex-scripts/five-dim.py check <step_id> <名> --contains "..." -- <命令...>
  python tools/codex-scripts/five-dim.py wrap  -- <任意外部命令...>
  python tools/codex-scripts/five-dim.py cap   auth_gate_status
  python tools/codex-scripts/five-dim.py cap   ledger_note '{"op":"preview"}'
  python tools/codex-scripts/five-dim.py cap   selfscan --watch 某文件
  python tools/codex-scripts/five-dim.py cap   count_words '{"text":"a b"}' --no-envelope

🔴 `cap` 的返回里带 `_信封`：**这次调用进没进账本**由审计账本末尾现读回填
   （`synced` / `entry`：`auto`=门口默认同步 · `outer`=本包装器主动开 · `off`=负对照）。
   不用去翻 37 MB 的 audit.jsonl。理由：看不见就没人核，"默认同步"就只是文档承诺。

🔴 `cap` 默认**自动信封**（Owner 2026-09-23 定：三主线道设为默认，不用每次点名）：
   同进程进五维合一信封 + 自动开步 + 按真实返回自动收步。证据取自调用结果，**不伪造机检 check**
   ⇒ 自动收步多半判 `partial`，那是**如实**；要判 ok 就自己再跑
   `check <sid> <名> --contains "..." -- <命令>` 补一条机器能判的证据。
   开关：`--watch <路径...>` 给收步的「眼」指定观察目标；`--no-envelope` 整条关掉（对照用）。
   为什么非做不可：`api.py` 记的 `meta.synced` 是**进程内 contextvar**，而 `cap` 是独立进程 ⇒
   不主动进信封就永远是 `synced:false`。实测 `brainless_ratio 0.9926`（2289 次只 17 次在内）。

口径：cap 一律走 gbt_allinone.run_task（唯一门）；被门拒绝就**如实报缺什么作用域**，不绕路。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴🔴 **框架的护栏（主人令 2026-10-10，逐字）—— 只有三道，除此外一律放行**

  ① **黑客全能力使用** ⇒ 要**人工授权**
  ② **付款**           ⇒ 要**人工授权**
  ③ **镜像多维度空间可以跑任何东西** —— 唯独**「生成代码」禁止入生产面板**

  🔴 而这三道**之外**：**所有的规则都是人定的。我自己的规则，我们自己定。**
     这一句**必须出现在万能插的解释里** —— 因为它是**解释的一部分，不是免责声明**：
     **主人操作自己的东西，不需要任何人管。**
     （与既有律并不冲突：**AI 永远无权给自己发授权** —— 那条也是主人定的规则之一。
       护栏只有三道，是因为其余的事**本就该由主人说了算**，而不是因为门可以绕。）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴🔴 **部署法制（同一次主人令）—— 只出品生产，不出品废物**

  · **不管多大的项目，拆开模块化部署**
  · 一个模块 ⇒ **先在镜像多维度空间跑通闭环** ⇒ **跑通了才落盘**
  · ⇒ 用户看到的是 **V8 一次性部署直接生产**，
      而**不是到处涂改、搞得一片混乱**

  🔴 **镜像多维度空间的最大能力：只出品生产，不出品废物。**
     落点：mirror_shape → scan → plan → simulate → parity → rehearse → **release/ascend（一次性全量，需主人发 deploy_publish）**
     房间（room_space）是**隔离排练现实**：假设/推演/打磨全在房间里跑，**不覆盖全局 mirror_space/reality**。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴🔴 **交付律（主人令 2026-10-10，逐字）—— 没有亲自跑通的东西不许交付**

  「所有的验证我只看**实质性跑通闭环证据**，**不接受任何口述说完成了**」
  「把这个验证方式也给框架绑死了，**没有亲自跑通的东西不许交付**」

  · **每一项交付声明，都必须带一条「可复跑的命令」与「期望读数」** ⇒ 落 state/delivery-claims.jsonl
  · 判据 tools/codex-scripts/proof-of-run-check.py：**当场复跑**那条命令并比对读数
      ① 只有口述、没带命令/期望读数  ⇒ 🔴 红（口述不算证据）
      ② 带了命令、复跑跑不通        ⇒ 🔴 红（没跑通就是没跑通）
      ③ 复跑通过且读数一致          ⇒ ✅ 绿（亲自跑通了）
  · 已接进开机自检（boot-selfcheck.py 的 EXTRA_JUDGMENTS）
  · 自检带**真植入负控**：口述必红 · 命令跑不通必红 · 读数对不上必红

  🔴 而这条律**自己就咬过我一次**（实证）：我把「恒真判据」那条声明写成不带隔离 store 的命令，
     复跑当场红 —— 本仓守卫**拒绝在绑定生产 store 的进程里跑测试**。
     ⇒ 正是「在**不等价条件**下验证过」这种假交付，被它抓出来。
"""
import json
import sys
import time
from pathlib import Path

# 🔴 2026-09-22 补（深蒸 system 域时抓到的**假故障**）：GBK 控制台下 `cap alerts` 会直接崩 ——
# `UnicodeEncodeError: 'gbk' codec can't encode '\u21d2'`、退出码 1。
# 那**不是能力位坏了**，是这个包装器没把 stdout 转成 utf-8（`omni.py` 早转了、它没转）。
# 结果：读的人以为"这个能力跑不了"，实际只是打不出来。修法：出口一律 utf-8 + errors=replace。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))     # 工作区根 = 可导入 gbt_allinone


def _sync():
    from gbt_allinone.tools import sync_exec
    return sync_exec


def _ensure_hook_marker():
    """落"机械钩子起始时刻"标记（只写一次）。ruler 的 since_hook 用它算**装钩子之后**的现读覆盖。

    🔴 为什么抽成助手：一开始只有 `cap` 落标记，于是"先跑 wrap 再跑 cap"时
    since 窗口的起点会**偏晚**，把中间的调用漏掉。`cap` 与 `wrap` 都必须调它。
    为什么必须只写一次：它定义的是"钩子生效的起点"，反复覆盖会把历史算进来。
    """
    try:
        import pathlib as _pl
        _m = _pl.Path(__file__).resolve().parents[2] / "gbt_allinone" / "store" / "sync_hook_since.txt"
        if not _m.is_file():
            _m.parent.mkdir(parents=True, exist_ok=True)
            _m.write_text(repr(time.time()), encoding="utf-8")
    except Exception as _me:                                         # noqa: BLE001
        # 🔴 不许静默吞：这里第一次写的时候漏了 `import time`，
        # 被 `except: pass` 吞掉 ⇒ 标记永远不落、ruler 报"钩子没被触发过"。
        # 教训（2026-09-23 当场抓到）：**吞异常可以，但必须留一行字**。
        sys.stderr.write("[five-dim] 钩子标记写入失败: %s: %s\n"
                         % (type(_me).__name__, str(_me)[:80]))


def _compact(value, budget=200):
    """把一个值压成"还能用"的小样子：**小的原样留，大的只报形状**。

    和 `json.dumps(x)[:N]` 的区别：那会把结构切碎（读的人 json.loads 报"line 84 断裂"，
    看着像能力坏了）。这里永远返回**合法 JSON**，且"截了就说截了"。
    """
    def _size(v):
        try:
            return len(json.dumps(v, ensure_ascii=False, default=str))
        except Exception:                                        # noqa: BLE001
            return 10 ** 6

    if _size(value) <= budget:
        return value
    if isinstance(value, list):
        return {"_len": len(value), "_head": [_compact(x, budget // 2) for x in value[:2]]}
    if isinstance(value, dict):
        keep, fold = {}, []
        for k, v in value.items():
            if _size(v) <= budget and len(keep) < 8:
                keep[k] = _compact(v, budget // 2)
            else:
                fold.append(k)
        out = dict(keep)
        out["_len"] = len(value)
        if fold:
            out["_其余键"] = fold[:12]
            if len(fold) > 12:
                out["_其余键数"] = len(fold)
        return out
    return str(value)[:200]


def _summarize(value):
    """把过大的 result 收成一段**可读且不撒谎**的摘要。

    🔴 2026-09-22 立（voice 域深蒸时抓到的真缺陷）：原来是 `json.dumps(out)[:1500]` ——
    **硬切字符**会把 JSON 切在字符串中间，读的人 `json.loads` 报"line 84 断裂"，
    看着像"能力坏了"，其实只是包装器截断（实测 `cap voice_orchestra '{"op":"list"}'`
    的 CLONE 那一段正好被切掉、连 `count` 都看不到）。
    修法：**截断只截 result 的内容，整份输出永远是合法 JSON**，并把"怎么拿全"写在明面上。

    🔴 2026-09-23 再磨（三层操作流畅度）：原来收窄后**只报键名** —— 于是
    `cap wf_status '{"include_workflows":true}'` 告诉你"有 runs / workflows / count 三个键"，
    却**不告诉你工作流叫什么**，而那正是你唯一想要的东西。
    收窄的本意是"别淹掉终端"，不是"把答案也一起收走"。现在补一层**小值速览**：
    小的键原样带上，大键只报形状，整段仍有硬预算（≤1100 字符）。
    """
    if isinstance(value, dict):
        keys = list(value.keys())
        base = {"_摘要": "result 过大，已收窄：**小值原样保留，大值只报形状**；要全量请加 --full",
                "keys": keys[:40], "key_count": len(keys)}
        preview, dropped = {}, []
        for k in keys[:12]:
            preview[k] = _compact(value[k])
            probe = dict(base)
            probe["preview"] = preview
            if len(json.dumps(probe, ensure_ascii=False, default=str)) > 1100:
                preview.pop(k)
                dropped.append(k)
        if preview:
            base["preview"] = preview
        if dropped:
            base["_未展开的键"] = dropped
        return base
    if isinstance(value, list):
        return {"_摘要": "result 是列表，已收窄；要全量请加 --full 或收窄 payload",
                "len": len(value), "head": [_compact(x) for x in value[:5]]}
    text = str(value)
    return {"_摘要": "result 过长，已收窄；要全量请加 --full 或收窄 payload",
            "chars": len(text), "head": text[:600]}


# 真命令清单**只写一处**：`未知命令` 提示、`--help` 用法都从它取。
# 🔴 2026-09-23 磨（三层流畅度）：这里原先是**手写死**的 ["open","close","ruler","run","cap"]，
# 而 `check` 与 `wrap` 早就实现了却不在表里 —— 于是打错一个字的人被告知
# "支持的命令"里**根本没有那两个真命令**。**提示本身在撒谎，比不提示更坏。**
COMMANDS = ("ruler", "open", "close", "run", "check", "wrap", "cap", "multi")


def _ledger_echo(kind, t0, tail_bytes=262144):
    """从**审计账本末尾现读**这次调用，把「门亲笔写的信封状态」还给终端上的人。

    为什么非做不可（2026-09-23 磨三层流畅度时实测）：`cap` 打出来的信封只有
    `gate / kind / status / stamp / denied / result` —— **没有 `synced`**。
    于是"我这次到底进没进信封"只能去翻 **37 MB** 的 `audit.jsonl`
    （`omni run` 会报这一格，`five-dim.py cap` 不报 —— 同一件事两个入口两种可见度）。
    看不见就没人核；没人核，"默认同步"就只是一句文档承诺。

    为什么**不**直接报"我自己开了信封"：那是调用方的**声明**。账本里那条才是门的**记录**。
    这条函数只认记录。
    为什么只 seek 末尾 256 KB：这次调用刚发生，记录必在末尾；口径要真，代价要小。
    """
    try:
        import pathlib as _pl
        f = _pl.Path(__file__).resolve().parents[2] / "gbt_allinone" / "store" / "audit.jsonl"
        if not f.is_file():
            return {"found": False, "note": "账本不在，如实报缺（不猜成 True）"}
        size = f.stat().st_size
        with f.open("rb") as fh:
            fh.seek(max(0, size - tail_bytes))
            raw = fh.read().decode("utf-8", errors="replace")
        lines = raw.splitlines()
        if size > tail_bytes and lines:
            lines = lines[1:]                    # 首行多半被 seek 切在半截，丢掉
        hit = None
        for ln in lines:
            if '"synced"' not in ln:             # 便宜预筛
                continue
            try:
                e = json.loads(ln)
            except Exception:                    # noqa: BLE001
                continue
            if e.get("event") != "call":         # 一次调用有两条带 synced 的记录，只认入口那条
                continue
            m = e.get("meta") or {}
            if m.get("kind") != kind:
                continue
            if float(e.get("ts") or 0) < t0:     # 只要**本次**的，不吃旧的
                continue
            hit = m
        if hit is None:
            return {"found": False, "note": "账本末尾没找到本次 call 记录（如实报缺，不猜成 True）"}
        return {"found": True,
                "synced": bool(hit.get("synced")),
                "entry": hit.get("synced_entry"),        # auto 门口默认 / outer 外层主动
                "via": hit.get("synced_via"),            # ctx 同进程 / env 继承标记
                "来源": "审计账本末尾现读（门亲笔，不是本包装器的自述）"}
    except Exception as e:                       # noqa: BLE001
        return {"found": False, "note": "读账本失败：%s" % type(e).__name__}


# ═══════════════════════════════════════════════════════════════════════════
# multi · 多职业**同时**执行（第 116 轮加的一等口）
#
# 为什么非做不可：在此之前「三条链同时跑」**只活在 `.scratch/_probe_multi.py`
# 那份一次性探针里** —— 探针会被清、会过期，而纪律不能只活在临时文件里。
#
# 三条硬纪律（都写死在这里）：
#   ① 每个职业仍然走**唯一门** `gbt_allinone.api.run_task`，**不绕、不直接调模块函数**；
#   ② 「同时」必须是**读数**不是形容词：每个职业落 `t_start/t_end`，父进程用
#      **扫描线**算峰值并发，并打出两两**重叠秒数**；
#   ③ 必须有**反向对照** `--serial`：同样的活串行跑，峰值并发必须是 1。
#      没有对照，"三个区间重叠"可能只是时钟粒度或调度抖动造出来的假象。
# ═══════════════════════════════════════════════════════════════════════════
def _multi_digest(kind, res):
    """从能力的真实返回里取**最小可判**的摘要（不猜、不补）。

    🔴 第 48 轮修：第一版只挑 summary/counts/ok/score/verdict 几个键 ⇒
    `auth_gate_status` / `mirror_status` 这种"内容在别的键里"的位**只印出一个 `{"ok": true}`**，
    等于**看不到实质读数**；`room_create` 回的 `how_to_list` 提示也照样被吃掉。
    ⇒ 现在一律带上**结果原文头部**（截断），宁可多印几十字，不许把提示吞掉。
    """
    if not isinstance(res, dict):
        return {"_head": str(res)[:400]}
    inner = res.get("result") if isinstance(res.get("result"), dict) else res
    head = json.dumps(inner, ensure_ascii=False, default=str)[:700]
    if kind == "media_run" and isinstance(inner, dict):
        # 🔴 第 49 轮修：**按 op 分形状**。原版只按"跑一次链的报告"取键 ⇒ `op=status`
        #    （返回的是三条链的定义 + 可跑步，不是 report）被印成空摘要，
        #    读的人会以为"媒体域没读数"。同一个能力位不同 op 返回**不同形状**，
        #    摘要器必须跟着分。
        if "report" in inner or "summary" in inner:
            rep = inner.get("report") or []
            st = {}
            for x in rep:
                if isinstance(x, dict) and x.get("status"):
                    st[x["status"]] = st.get(x["status"], 0) + 1
            return {"op": "run", "kind_of_work": inner.get("kind"), "work": inner.get("work"),
                    "步骤状态分布": st,
                    "ran 的步": [x.get("step") for x in rep
                               if isinstance(x, dict) and x.get("status") == "ran"]}
        if "chains" in inner:
            chains = inner.get("chains") or {}
            rn = inner.get("runnable_steps") or {}
            return {"op": "status",
                    "三条链": {k: (len(v) if isinstance(v, list) else v) for k, v in chains.items()},
                    "可跑步数": {k: (len(v) if isinstance(v, list) else v) for k, v in rn.items()}}
        return {"op": inner.get("op") or "?", "_head": head}
    return {"_head": head}


def _multi_worker(job):
    """**子进程**里跑一个职业的一次能力调用。仍走唯一门；异常如实回传，不吞。"""
    import time as _t
    kind = job.get("kind")
    payload = job.get("payload") or {}
    rec = {"label": job.get("label") or kind, "kind": kind, "ok": False,
           "status": "unknown", "denied": False, "t_start": _t.time()}
    # 隔离位：子进程把它设成环境变量，并在自己这边**确认它在**（不在就如实记，不假装有）
    _iso = job.get("_iso_dir")
    if _iso:
        import os as _os
        _os.environ["GBT_MULTI_JOB_DIR"] = _iso
        rec["iso_dir"] = _iso
        rec["iso_ok"] = _os.path.isdir(_iso)
    try:
        from gbt_allinone import api as _api
        # 每个子进程**自己进信封**：`api.py` 的 synced 是**进程内 contextvar**，
        # 不跨进程传播 —— 不在子进程里进一次，这里每次调用都会记成信封外。
        se = None
        try:
            from gbt_allinone.tools import sync_exec as se      # noqa: F811
        except Exception:                                        # noqa: BLE001
            se = None
        if se is not None:
            try:
                with se.envelope():
                    r = _api.run_task(kind, payload)
            except Exception:                                    # noqa: BLE001
                r = _api.run_task(kind, payload)
        else:
            r = _api.run_task(kind, payload)
        gr = r.get("gbt_result") or (r if isinstance(r, dict) else {})
        # 授权拒绝返回的是**扁平错误信封**（没有 gbt_result）⇒ 顶层当 body 看。
        rec["status"] = gr.get("status") or ("ok" if r.get("ok") else "unknown")
        rec["stamp"] = bool(r.get("gbt_stamp"))
        rec["denied"] = (gr.get("status") == "denied" or gr.get("denied") is True
                         or bool(gr.get("missing")) or bool(gr.get("missing_scopes")))
        rec["digest"] = _multi_digest(kind, gr.get("result") if isinstance(gr, dict) else None)
        rec["ok"] = (not rec["denied"]) and rec["status"] in ("ok", "success")
        if rec["denied"]:
            rec["missing_scopes"] = gr.get("missing") or gr.get("missing_scopes") or []
            rec["how_to_grant"] = gr.get("how_to_grant") or []
            rec["reason"] = str(gr.get("reason") or gr.get("message") or "")[:160]
    except Exception as e:                                       # noqa: BLE001
        rec["error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
    rec["t_end"] = _t.time()
    rec["elapsed"] = round(rec["t_end"] - rec["t_start"], 3)
    return rec


def _peak_concurrency(recs):
    """扫描线算峰值并发。**同名时刻先算结束再算开始** —— 只是相碰不算重叠，
    宁可少报也不许把"擦肩而过"说成"同时在跑"。"""
    ev = []
    for r in recs:
        ev.append((r["t_start"], 1))
        ev.append((r["t_end"], -1))
    ev.sort(key=lambda x: (x[0], x[1]))          # -1 排在 +1 前面
    cur = peak = 0
    for _t, d in ev:
        cur += d
        peak = max(peak, cur)
    return peak


def _overlap_pairs(recs):
    """两两重叠秒数（>0 = 这两件真的同时在跑）。"""
    out = []
    for i in range(len(recs)):
        for j in range(i + 1, len(recs)):
            a, b = recs[i], recs[j]
            ov = min(a["t_end"], b["t_end"]) - max(a["t_start"], b["t_start"])
            out.append({"对": "%s×%s" % (a["label"], b["label"]), "重叠秒": round(ov, 3),
                        "同时": ov > 0})
    return out


def _parse_jobs(raw):
    """收三种写法：{"jobs":[{...}]} · [{...}] · {"jobs":[["kind",{payload}]]}。"""
    obj = json.loads(raw) if isinstance(raw, str) else raw
    items = obj.get("jobs") if isinstance(obj, dict) else obj
    if not isinstance(items, list) or not items:
        raise ValueError("jobs 必须是非空数组")
    jobs = []
    for it in items:
        if isinstance(it, dict):
            jobs.append({"kind": it.get("kind") or it.get("cap"),
                         "payload": it.get("payload") or {},
                         "label": it.get("label") or it.get("kind") or it.get("cap")})
        elif isinstance(it, (list, tuple)) and it:
            jobs.append({"kind": it[0], "payload": (it[1] if len(it) > 1 else {}),
                         "label": it[0]})
        else:
            raise ValueError("每个 job 要么是对象，要么是 [kind, payload]")
    for j in jobs:
        if not j["kind"]:
            raise ValueError("job 缺 kind")
    return jobs


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    # 2026-10-17 加：装信号收尾钩子（SIGTERM/SIGINT ⇒ SystemExit ⇒ api 的 BaseException 分支落 error 收尾）
    try:
        _install_signal_closers()
    except Exception:                                            # noqa: BLE001
        pass
    cmd = argv[0].strip().lower()

    if cmd == "ruler":
        a = _sync().audit_sync()
        keys = ("brainless_ratio", "verdict", "cap_calls_total", "inside_envelope",
                "outside_envelope", "agent_steps_opened", "agent_steps_closed",
                "agent_close_rate", "agent_unclosed_on_disk", "agent_verdict")
        out_r = {k: a.get(k) for k in keys}
        # 🔴 2026-09-23 补：全史尺子会被**历史**压住。
        # 实测：装上机械钩子后跑一次 cap，`inside_envelope` 17→19 确实涨了，
        # 但 `brainless_ratio` 只从 0.9926 动到 0.9917 —— 因为窗口里压着 2285 条历史调用。
        # ⇒ 单看全史比率会得出"钩子没用"的错觉。这里**再给一把"自钩子安装以来"的尺**，
        #   数的是**此后**每一次能力调用的 meta.synced（入口亲笔），不是猜。
        try:
            import pathlib as _pl
            _store = _pl.Path(__file__).resolve().parents[2] / "gbt_allinone" / "store"
            _mark = _store / "sync_hook_since.txt"
            _auditf = _store / "audit.jsonl"
            if _mark.is_file() and _auditf.is_file():
                # 标记存的是 **epoch 浮点**（审计行有 `ts`），做数值比较而不是字符串匹配 —— 精确。
                since = float(_mark.read_text(encoding="utf-8-sig").strip() or 0)
                ins = outs = 0
                via = {"ctx": 0, "env": 0}
                # 2026-09-23 加：信封**是谁开的**。默认同步（`api._run_task_core` 门口替你开）
                # 与主动信封（五维合一亲手开）**不是一回事**；不分格，"我把默认打开了"
                # 就会被读成"纪律执行得好"。`unknown` = 本条记录写在加这一格之前。
                ent = {"auto": 0, "outer": 0, "off": 0, "unknown": 0}

                with _auditf.open("r", encoding="utf-8", errors="replace") as fh:
                    for ln in fh:
                        if '"synced"' not in ln:                     # 先做便宜的预筛
                            continue
                        try:
                            e = json.loads(ln)
                        except Exception:                            # noqa: BLE001
                            continue
                        if float(e.get("ts") or 0) < since:
                            continue
                        meta = e.get("meta") or {}
                        if not meta.get("kind"):
                            continue
                        # 只数 `call` —— 一次能力调用会产生两条带 synced 的 kind 事件
                        # （`call` 入口一条 + `ok`/`error`/`denied` 结果一条），
                        # 两条都数会把"调用次数"翻倍。按 `call` 计才叫次数。
                        if e.get("event") != "call":
                            continue
                        if meta.get("synced"):
                            ins += 1
                            _v = meta.get("synced_via")
                            if _v in via:
                                via[_v] += 1
                            _e = str(meta.get("synced_entry") or "unknown")
                            ent[_e if _e in ent else "unknown"] += 1
                        else:
                            outs += 1
                tot = ins + outs
                out_r["since_hook"] = {
                    "since_epoch": since,
                    "since_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(since)),
                    "calls": tot, "inside": ins, "outside": outs,
                    "rate_inside": round(ins / tot, 4) if tot else None,
                    # ctx = 同进程真信封；env = 继承来的标记（跨进程传播，可伪造，只当传播机制）
                    "inside_via": via,
                    # auto = 门口默认同步（谁调都算）· outer = 外层主动信封 · off = 负对照（显式不进）
                    # unknown = 这一格是 2026-09-23 才加的，之前的记录没这格
                    "inside_entry": ent,
                    "note": ("★ 自机械钩子安装以来的**现读**覆盖：%d/%d 在信封内"
                             "（同进程 %d · 继承标记 %d ｜ 默认同步 %d · 主动信封 %d · 未分格 %d）"
                             % (ins, tot, via["ctx"], via["env"],
                                ent["auto"], ent["outer"], ent["unknown"])) if tot
                    else "★ 钩子装好后还没有新的能力调用",
                }
            else:
                out_r["since_hook"] = {"since": None,
                                       "note": "★ 钩子还没被触发过（跑一次 cap 就会落标记）"}
        except Exception:                                            # noqa: BLE001
            out_r["since_hook"] = {"note": "★ 现读覆盖算不出来（如实报缺，不猜）"}
        out_r["_口径"] = ("brainless_ratio 是**全史**（窗口内全部调用）；"
                        "since_hook 是**装钩子之后**的现读。两个一起看才不会被历史误导。")
        print(json.dumps(out_r, ensure_ascii=False, indent=1))
        return 0

    if cmd == "open":
        if len(argv) < 2:
            print(json.dumps({"ok": False, "note": "用法: open \"目标\" [观察目标...]"}, ensure_ascii=False))
            return 2
        r = _sync().step_open(argv[1], watch=argv[2:])
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1

    if cmd == "close":
        if len(argv) < 3:
            print(json.dumps({"ok": False, "note": "用法: close <step_id> \"证据\"..."}, ensure_ascii=False))
            return 2
        r = _sync().step_close(argv[1], evidence=argv[2:])
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1

    if cmd == "run":
        if len(argv) < 2:
            print(json.dumps({"ok": False, "note": "用法: run \"目标\" [观察目标...]"}, ensure_ascii=False))
            return 2
        r = _sync().run(argv[1], watch=argv[2:] or None)
        print(json.dumps({"ok": r.get("ok"), "verdict": r.get("verdict"),
                          "elapsed_ms": r.get("elapsed_ms"),
                          "channels": {k: (v.get("ok") if isinstance(v, dict) else None)
                                       for k, v in (r.get("channels") or {}).items()},
                          "dims": r.get("dims")}, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1

    if cmd == "check":
        # check <step_id> <name> --contains "<输出里必须出现>" [--argv-has "<命令行里必须出现>"]... -- <命令...>
        try:
            sep = argv.index("--")
        except ValueError:
            print(json.dumps({"ok": False, "note": "用法: check <sid> <name> --contains \"...\" [--argv-has \"...\"] -- <命令...>"},
                             ensure_ascii=False))
            return 2
        head, tail = argv[1:sep], argv[sep + 1:]
        if len(head) < 2 or not tail:
            print(json.dumps({"ok": False, "note": "缺 step_id / name / 命令"}, ensure_ascii=False))
            return 2
        sid, name = head[0], head[1]
        contains, argv_has = "", []
        i = 2
        while i < len(head):
            if head[i] == "--contains" and i + 1 < len(head):
                contains = head[i + 1]
                i += 2
            elif head[i] == "--argv-has" and i + 1 < len(head):
                argv_has.append(head[i + 1])
                i += 2
            else:
                i += 1
        expect = {"contains": contains, "argv_contains": argv_has}
        r = _sync().run_check(sid, name, tail, expect=expect)
        print(json.dumps({k: r.get(k) for k in ("ok", "name", "exit_code", "problems", "note")},
                         ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1

    if cmd == "wrap":
        # 🔴 2026-09-23 加（Owner：把"绕过"也堵上）：
        #   `wrap -- <命令...>` 把**任意外部命令**放进信封里跑。
        #   信封标记会写进环境变量 ⇒ 该命令起的**所有子进程**都算在信封内。
        #   为什么需要它：`python -m gbt_allinone ...` 这类入口本来绕过信封；
        #   有了 wrap，绕过的就只剩"故意不走主线道"。
        if "--" not in argv:
            print(json.dumps({"ok": False, "note": "用法: wrap -- <命令...>"}, ensure_ascii=False))
            return 2
        tail = argv[argv.index("--") + 1:]
        if not tail:
            print(json.dumps({"ok": False, "note": "缺命令"}, ensure_ascii=False))
            return 2
        import subprocess
        from gbt_allinone.tools import sync_exec as _se
        sid = None
        try:
            op = _se.step_open("wrap:%s" % " ".join(tail)[:60], watch=[])
            sid = op.get("step_id") if op.get("ok") else None
        except Exception:                                            # noqa: BLE001
            _se, sid = None, None
        if _se is not None:
            with _se.envelope():
                p = subprocess.run(tail, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace")
        else:
            p = subprocess.run(tail, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        if sid and _se is not None:
            try:
                _se.step_close(sid,
                               evidence=["wrap rc=%d" % p.returncode,
                                         "cmd=%s" % " ".join(tail)[:120]],
                               note="五维合一 wrap：外部命令在信封内执行")
            except Exception as _ce:                                 # noqa: BLE001
                sys.stderr.write("[five-dim] wrap 收步失败: %s\n" % type(_ce).__name__)
        sys.stdout.write(p.stdout or "")
        sys.stderr.write(p.stderr or "")
        return p.returncode

    if cmd == "multi":
        # 用法：
        #   multi '{"jobs":[{"kind":"media_run","payload":{"op":"run","kind":"short_video","work":"x"}}]}'
        #   multi --file jobs.json [--serial] [--workers N]
        a = list(argv[1:])
        serial = "--serial" in a
        a = [x for x in a if x != "--serial"]
        workers = 0
        if "--workers" in a:
            i = a.index("--workers")
            workers = int(a[i + 1])
            del a[i:i + 2]
        raw = None
        if "--file" in a:
            i = a.index("--file")
            raw = Path(a[i + 1]).read_text(encoding="utf-8")
            del a[i:i + 2]
        elif a:
            raw = a[0]
        if not raw:
            print(json.dumps({"ok": False, "note":
                              "用法: multi '<json>' 或 multi --file <路径> [--serial] [--workers N]；"
                              "json 形如 {\"jobs\":[{\"kind\":\"media_run\",\"payload\":{...}}]}"},
                             ensure_ascii=False))
            return 2
        try:
            jobs = _parse_jobs(raw)
        except Exception as e:                                   # noqa: BLE001
            print(json.dumps({"ok": False, "note": "jobs 解析失败：%s" % e}, ensure_ascii=False))
            return 2

        # ── `--dry-run`：**只报计划，一件都不跑**（第 39 轮加）────────────────
        # 为什么要它：这是"一次发多件"的口 —— 发错了就是几条链一起跑。本仓既有纪律是
        # "试改（不落盘）→ 真改"（`code_patch` 的 `dry_run`/`apply` 同型）。
        # **判据：dry-run 期间审计账上不许新增调用**（不是"我说没跑"，是账上能查）。
        if "--dry-run" in a or "--plan" in a:
            plan = []
            for i, j in enumerate(jobs, 1):
                pl = j.get("payload") or {}
                plan.append({
                    "序号": i, "标签": j.get("label"), "能力位": j.get("kind"),
                    "payload 的键": sorted(pl) if isinstance(pl, dict) else "(不是对象)",
                    "会走哪条门": "gbt_allinone.api.run_task（唯一门）",
                })
            out = {
                "ok": True, "mode": "dry-run（未执行任何调用）", "jobs": len(jobs),
                "计划": plan,
                "对照的真命令": "把 --dry-run 去掉即真跑；真跑会**真落盘**（产物 + 许可登记）",
                "_口径": ("dry-run 只解析与列计划，**不 import 能力模块、不调 run_task**；"
                          "要确认它真没跑，查审计账本在这次前后有没有新增调用。"),
            }
            print("=" * 78)
            print("多职业同时执行 · **试跑（不落盘）**")
            print("=" * 78)
            for p in plan:
                print("   %-22s %-14s payload 键：%s"
                      % (str(p["标签"])[:22], str(p["能力位"])[:14], "、".join(map(str, p["payload 的键"])) or "(空)"))
            print("\n   ⚠️ 本命令**一件都没跑** —— 去掉 --dry-run 才真跑（会真落盘）")
            print()
            print(json.dumps(out, ensure_ascii=False, indent=1))
            return 0

        # ── 隔离：**N 根触手 ⇒ N 个隔离位**（主人 2026-09-23 令：「免得协作的时候混乱了」）──
        # 我们能自己做到的三层（不需任何新授权）：
        #   ① **进程级**：每根触手一个独立进程（本来就是）；
        #   ② **工作目录级**：每根一个独占的 `.scratch/_multi/<本次>/jobNN/`；
        #   ③ **写面不撞的机械闸**：先算每根的"写面签名"，**撞了就整批拒跑**（fail-closed，
        #      一件都不执行）—— 这才是"免得混乱"里真正会出事的那一条。
        # ⚠️ **镜像级隔离**（`mirror_*` 那一族）要主人发作用域，现在 `grants_available` 全 0 ⇒ 做不到。
        #    所以本件**不假装**做了镜像隔离：输出里只报"进程/目录/写面"这三层，
        #    镜像那一层如实写 `mirror_isolation: false`。
        run_id = time.strftime("%m%d-%H%M%S") + "-" + str(int(time.time() * 1000) % 1000)
        iso_root = Path(__file__).resolve().parents[2] / ".scratch" / "_multi" / run_id
        iso, seen, conflicts = [], {}, []
        for i, j in enumerate(jobs, 1):
            pl = j.get("payload") or {}
            if j.get("kind") == "media_run":
                # 媒体链最容易撞的就是「同方向同作品」——那是同一个活，不该同时跑两遍
                sig = "media_run:%s:%s" % (pl.get("kind"), pl.get("work"))
            else:
                sig = "%s:%s" % (j.get("kind"), json.dumps(pl, sort_keys=True, ensure_ascii=False)[:60])
            # 🔴 第 50 轮补：**目录要真建、真交给子进程、真留痕**。
            #    上一轮只把目录名印进报告 ⇒ 那只是**标签**，不是隔离。
            #    现在：① 主进程 mkdir；② 路径随 job 传给子进程（子进程设成环境变量）；
            #          ③ 每个隔离位落一份 `_marker.json` ⇒ **盘上可查**，不用信报告里的字。
            d = iso_root / ("job%02d" % i)
            d.mkdir(parents=True, exist_ok=True)
            (d / "_marker.json").write_text(
                json.dumps({"序号": i, "标签": j.get("label"), "能力位": j.get("kind"),
                            "写面签名": sig, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "run_id": run_id,
                            "口径": "本目录是这一根触手的独占隔离位；N 根触手 ⇒ N 个位"},
                           ensure_ascii=False, indent=1), encoding="utf-8")
            j["_iso_dir"] = str(d)
            iso.append({"序号": i, "标签": j.get("label"), "隔离目录": "job%02d" % i, "写面签名": sig})
            if sig in seen:
                conflicts.append({"写面": sig, "撞的两根": [seen[sig], j.get("label")]})
            else:
                seen[sig] = j.get("label")

        if conflicts and "--dry-run" not in a and "--plan" not in a:
            print("=" * 78)
            print("🔴 **拒跑**：有触手的写面撞在一起 —— 按隔离规矩 fail-closed，一件都没执行")
            print("=" * 78)
            for c in conflicts:
                print("   写面 %s ← %s" % (c["写面"], " × ".join(map(str, c["撞的两根"]))))
            print("\n   为什么拒：同写面并发＝同一个活被跑两遍，最容易出的不是报错而是**互相覆盖**。")
            print("   改法：给每一根**不同的 work / 不同的目标**，让 N 根触手各有各的隔离位。")
            print()
            print(json.dumps({"ok": False, "refused": True, "reason": "写面冲突（隔离规矩 fail-closed）",
                              "conflicts": conflicts, "isolation": {"jobs": len(jobs),
                                                                    "isolated": len(jobs), "mirror_isolation": False}},
                             ensure_ascii=False, indent=1))
            return 2

        import multiprocessing as _mp
        _mp.freeze_support()
        n = workers or len(jobs)
        head = "多职业**同时**执行" if not serial else "多职业**串行**执行（反向对照）"
        print("=" * 78)
        print("%s · 逐个仍走唯一门 api.run_task（不绕门）" % head)
        print("=" * 78)
        print("  职业 %d 个：%s ｜ 进程 %d ｜ 模式 %s"
              % (len(jobs), "、".join(str(j["label"]) for j in jobs), n,
                 "serial（对照）" if serial else "parallel"))
        print("  隔离：N 根触手 ⇒ **N 个隔离位**（进程级 + 独占工作目录 %s）｜ 写面冲突：%s"
              % (".scratch/_multi/%s/jobNN" % run_id, "无 ✅" if not conflicts else conflicts))
        print("        ⚠️ 镜像级隔离（mirror_*）**未做**：其写面全带锁且待用授权为 0（要主人发）。")
        t0 = time.time()
        if serial:
            recs = [_multi_worker(j) for j in jobs]
        else:
            with _mp.Pool(min(n, len(jobs))) as pool:
                recs = pool.map(_multi_worker, jobs)
        wall = round(time.time() - t0, 3)

        peak = _peak_concurrency(recs)
        pairs = _overlap_pairs(recs)
        bad = [r for r in recs if not r["ok"]]
        serial_sum = round(sum(r["elapsed"] for r in recs), 3)
        print()
        for r in recs:
            print("   %-22s %-8s %7.3fs  %s"
                  % (str(r["label"])[:22], r["status"], r["elapsed"],
                     ("❌ " + r.get("error", r.get("reason", ""))[:60]) if not r["ok"] else ""))
            if r.get("digest"):
                print("        %s" % json.dumps(r["digest"], ensure_ascii=False)[:700])
        print()
        print("  ⏱ 墙钟 %.3fs ｜ 各件耗时之和 %.3fs ｜ 峰值并发 **%d**" % (wall, serial_sum, peak))
        print("  两两重叠：%s"
              % "、".join("%s %+.3fs%s" % (p["对"], p["重叠秒"], "✅同时" if p["同时"] else "—")
                         for p in pairs))
        # ── 判据（含反向对照）─────────────────────────────────────────────
        want_peak = 1 if serial else len(jobs)
        crit = {
            "所有职业都没抛异常": not bad,
            "峰值并发=期望(%d)" % want_peak: peak == want_peak,
            "墙钟 < 各件之和（真有重叠）" if not serial else "墙钟 ≥ 各件之和（对照：不重叠）":
                (wall < serial_sum) if not serial else (wall >= serial_sum * 0.98),
        }
        print()
        for k, v in crit.items():
            print("   %s %s" % ("✔" if v else "✗", k))
        out = {"ok": all(crit.values()), "mode": "serial" if serial else "parallel",
               "jobs": len(jobs), "wall_s": wall, "sum_elapsed_s": serial_sum,
               "peak_concurrency": peak, "expect_peak": want_peak,
               "isolation": {"jobs": len(jobs), "isolated": len(jobs), "run_id": run_id,
                             "per_job_dirs": [x["隔离目录"] for x in iso],
                             "dirs_on_disk": sum(1 for x in iso if (iso_root / x["隔离目录"]).is_dir()),
                             "markers": sum(1 for x in iso
                                            if (iso_root / x["隔离目录"] / "_marker.json").is_file()),
                             "each_job_confirmed": all(r.get("iso_ok") for r in recs),
                             "conflicts": conflicts, "mirror_isolation": False,
                             "mirror_note": "镜像级隔离要主人发作用域（mirror_* 全带锁，grants_available=0）"},
               "overlaps": pairs,
               "per_job": [{k: r.get(k) for k in
                            ("label", "kind", "status", "denied", "elapsed", "ok", "error")}
                           for r in recs],
               "_口径": ("峰值并发用扫描线算；同名时刻先算结束再算开始 ⇒ 只是相碰不算重叠。"
                       "`--serial` 是反向对照，它的期望峰值是 1。")}
        print()
        print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
        return 0 if out["ok"] else 1

    if cmd == "cap":
        # `--full`：不再收窄 result（默认仍收窄，为的是别把终端和上下文淹掉）。
        # 🔴 2026-09-23 新增（Owner：三主线道设为默认，不用每次点名）：
        #   `--no-envelope` 关掉自动信封；`--watch <path...>` 给收步时的「眼」指定观察目标。
        full = "--full" in argv
        no_env = "--no-envelope" in argv

        def _take(flag):
            """取走 `--flag v1 v2 …`（直到下一个 `--*`）；**先取长名的**，免得互相吞值。"""
            nonlocal argv
            if flag not in argv:
                return []
            i = argv.index(flag)
            vals, j = [], i + 1
            while j < len(argv) and not argv[j].startswith("--"):
                vals.append(argv[j])
                j += 1
            del argv[i:j]
            return vals

        # 🔴 `--watch`：给收步的「眼」指定观察目标（进信封），**并且**在同一发执行里
        #    做邻域同视护栏（guard_pre → run_task → guard_post）。Owner 令：
        #    「改一个区块时同时有触手监控相关区块，不会出现修一个地方坏一个地方」。
        #    `--expect`：这次**有意**改动的文件（邻域里其余的都不许变）。
        watch = _take("--watch")
        expect = _take("--expect")
        # 🔴 2026-10-17 固定接线（Owner 令逐字：「多路视觉监视台必须与万能插同步执行 ——
        #    万能插的**每一次操作**，触手网络都全方位监控该区块的所有分路，确保修改/部署
        #    不溅伤其他地方」「这个能力是必须同步执行的…不是的话给她固定一下，免得每次都要
        #    我提醒很累」）。
        #    原状：只有 `--watch` 才监控 ⇒ **靠记性 = 会忘**（等于没接线）。
        #    现口径：**默认每一发 cap 都做**邻域同视；观察目标默认 = 该能力位的**实现模块**
        #    （"该区块"），由注册表 handler 现读定位；`--watch` 只**追加**，`--no-neighbor`
        #    才关（负对照专用，且关这件事会写进读数，不静默）。
        no_nb = "--no-neighbor" in argv
        enforce_flag = "--enforce" in argv
        argv = [a for a in argv if a not in ("--full", "--no-envelope",
                                             "--no-neighbor", "--enforce")]
        if len(argv) < 2:
            print(json.dumps({"ok": False, "note": "用法: cap <kind> [payload_json] [--full] [--watch 路径...] [--no-envelope]"}, ensure_ascii=False))
            return 2
        _raw = argv[2] if len(argv) > 2 else ""
        import gbt_allinone as g
        import sys as _sys
        from pathlib import Path as _P
        # R-H1003（2026-10-15 实测）：三条**不靠 shell 引号**的入口。
        #   病因：PowerShell 吃内层双引号（`{"op":...}` ⇒ `{op:...}`）；
        #         `@p.json` 在 PS 里是展开运算符（未加引号必炸）；
        #         PS 5.1 的 `Set-Content -Encoding utf8` **写 BOM** ⇒ 读文件必须 utf-8-sig。
        # 🔴 2026-10-19 二次修（主人当场撞上）：`--stdin` 原先**只有当它出现在 payload 位**才被认。
        #    于是最容易写错的那种调用 `cap <kind> '{…}' --stdin`（既给位置参数、又给 --stdin）
        #    会被当成"位置参数不是 JSON"直接拒 —— 而它该用管道里那份。现在：**只要 argv 里
        #    出现 `--stdin`，就以 stdin 为准**（旗标是"从管道取"的意思，不该被位置参数压住），
        #    并且位置参数被忽略时**在回执里说明**，不静默丢东西。
        _stdin_flag = ("--stdin" in argv) or (_raw.strip() == "--stdin")
        _dropped = ""
        if _stdin_flag:
            # 🔴 2026-10-19 实测：`sys.stdin.read()` 走的是**系统 locale**（Windows 中文机 = GBK），
            #    于是管道里送进来的 UTF-8 中文被按 GBK 解码 ⇒ `全绿数` 变成 `鍏ㄧ豢鏁?`，
            #    回执里 key 对不上、误差永远判红（P1 判据错尺的变种：拿错码表量同一串字）。
            #    正解：**按字节读、显式 utf-8 解**（BOM 也吃掉）；解不了就 replace，不静默。
            if _raw.strip() and _raw.strip() != "--stdin":
                _dropped = _raw[:80]
            _buf = getattr(_sys.stdin, "buffer", None)
            if _buf is not None:
                _raw = _buf.read().decode("utf-8-sig", errors="replace")
            else:
                _raw = _sys.stdin.read()
            if _dropped:
                print("[five-dim] 给了 --stdin ⇒ 以管道为准，位置参数已忽略：%r" % _dropped,
                      file=_sys.stderr)
        if _raw.strip().startswith("@"):
            _p = _P(_raw.strip()[1:])
            try:
                payload = json.loads(_p.read_text(encoding="utf-8-sig"))
            except Exception as _e:
                print(json.dumps({"ok": False, "note": "读不到 @文件：%s" % _p,
                                  "detail": type(_e).__name__}, ensure_ascii=False))
                return 2
        elif _raw.strip():
            try:
                payload = json.loads(_raw)
            except Exception as _e:
                if _raw.lstrip()[:1] in ("{", "["):
                    print(json.dumps({"ok": False,
                                      "note": "payload 不是合法 JSON（%s）" % type(_e).__name__,
                                      "detail": _raw[:140],
                                      "why_通常只有一种": "PowerShell 把内层双引号吃掉了"
                                                          "（`\"` 在 PS 单引号里才留得住）",
                                      "how": [
                                          "✅ PowerShell 最稳写法（整段用单引号包住 json，再管道给 --stdin）：",
                                          "   '{\"op\":\"status\"}' | py -3.14 tools/codex-scripts/five-dim.py cap impact_check --stdin",
                                          "   例：'{\"op\":\"impact\",\"target\":\"code:gbt_allinone/api.py\"}' | py -3.14 tools/codex-scripts/five-dim.py cap impact_check --stdin",
                                          "文件：cap <kind> \"@payload.json\"（PS 里 @ 必须加引号）"]},
                                     ensure_ascii=False))
                    return 2
                payload = {"text": _raw}
        else:
            payload = {}

        # ── 邻域同视护栏（**和执行同步**）：装载本仓的区块邻域闸 ────────────────
        # Owner 令：「比如你在修复一个区块，同时有触手监控相关区块，
        #            不会出现修一个地方坏一个地方」。光有独立命令 = 靠记性；
        # 焊进这一发执行里才是同步：guard_pre → run_task → guard_post。
        # ── 邻域同视护栏（**和执行同步** · 默认开）：装载本仓的区块邻域闸 ────────────
        # 默认观察目标 = 该能力位的实现模块（"该区块"）；`--watch` 追加；`--no-neighbor` 关。
        _meta: dict = {}
        if not no_nb:
            try:
                from gbt_allinone.caps_registry import BENIGN_CAPS as _BC
                _meta = dict(_BC.get(argv[1]) or {})
            except Exception:                                    # noqa: BLE001
                _meta = {}
            _h = str(_meta.get("handler") or argv[1])
            _root = _P(__file__).resolve().parents[2]
            for _n in (_h, argv[1]):
                for _c in (_root / "gbt_allinone" / (_n + ".py"),
                           _root / "gbt_allinone" / "tools" / (_n + ".py")):
                    if _c.is_file():
                        _rel = str(_c.relative_to(_root)).replace("\\", "/")
                        if _rel not in watch:
                            watch.insert(0, _rel)
                        break
                if watch:
                    break
            if not watch:                                        # 兜底：门本体（唯一门所在区块）
                watch = ["gbt_allinone/api.py"]
        _nh = None
        if watch and not no_nb:
            try:
                import importlib.util as _iu
                _sp = _iu.spec_from_file_location(
                    "block_neighborhood_watch",
                    _P(__file__).resolve().parents[2] / "tools" / "codex-scripts"
                    / "block-neighborhood-watch.py")
                _nh = _iu.module_from_spec(_sp)
                _sp.loader.exec_module(_nh)
            except Exception as _we:                             # noqa: BLE001
                sys.stderr.write("[five-dim] 邻域同视闸装载失败（照跑，但如实说）：%s\n" % str(_we)[:120])
                _nh = None
        _nh_pre = None
        if _nh is not None:
            try:
                _nh_pre = _nh.guard_pre(watch, expect=expect)
            except Exception as _we:                             # noqa: BLE001
                sys.stderr.write("[five-dim] 邻域基线拍不下（照跑，但如实说）：%s\n" % str(_we)[:120])

        # 🔴 `--no-envelope` 必须**真的**关掉信封（2026-09-23 补）：
        # `api._run_task_core` 现在门口默认开信封，若不把这个开关置上，
        # `--no-envelope` 就变成废话 —— 那条负对照会记成 `synced=True entry=auto`，
        # 而它本来要证明的是"信封外确实算信封外"。**测不出假的尺子不是尺子。**
        if no_env:
            import os as _os
            _os.environ["GBT_ENVELOPE_OFF"] = "1"

        # ── 机械钩子：同进程进信封 + 自动开步 ──────────────────────────────
        # 为什么必须在这里做：`api.py` 记的 `meta.synced = in_envelope()` 是**进程内 contextvar**；
        # 而 `cap` 自己是独立进程，不主动进信封 ⇒ synced 恒为 False ⇒ 实测
        # brainless_ratio 0.9926（2289 次调用只 17 次在信封内）。
        # 靠"记得先 open"是纪律；在这里做是机械。信封坏了**不能把能力调用弄崩**。
        _se, sid = None, None
        if not no_env:
            try:
                from gbt_allinone.tools import sync_exec as _se
                op = _se.step_open("cap:%s" % argv[1], watch=watch)
                sid = op.get("step_id") if op.get("ok") else None
                # 落"钩子起始时刻"标记（只写一次）：ruler 用它算**装钩子之后**的现读覆盖，
                # 免得被窗口里几千条历史调用压住、得出"钩子没用"的错觉。
                try:
                    import pathlib as _pl2
                    _m = _pl2.Path(__file__).resolve().parents[2] / "gbt_allinone" / "store" / "sync_hook_since.txt"
                    if not _m.is_file():
                        _m.parent.mkdir(parents=True, exist_ok=True)
                        _m.write_text(repr(time.time()), encoding="utf-8")
                except Exception as _me:                             # noqa: BLE001
                    # 🔴 不许静默吞：这里第一次写的时候漏了 `import time`，
                    # 被 `except: pass` 吞掉 ⇒ 标记永远不落、ruler 报"钩子没被触发过"。
                    # 教训（2026-09-23 当场抓到）：**吞异常可以，但必须留一行字**。
                    sys.stderr.write("[five-dim] 钩子标记写入失败: %s: %s\n"
                                     % (type(_me).__name__, str(_me)[:80]))
            except Exception:                                        # noqa: BLE001
                _se, sid = None, None
        # 记下"本次调用"的时间下界：`_ledger_echo` 用它把**旧记录**挡在外面。
        # 不记这个就只能"取账本最后一条同名记录"，而那只在连跑两次之间才不出错。
        _t0 = time.time()
        if _se is not None:
            try:
                with _se.envelope():
                    r = g.run_task(argv[1], payload)
            except Exception:                                        # noqa: BLE001
                r = g.run_task(argv[1], payload)
        else:
            r = g.run_task(argv[1], payload)
        # 🔴 R-H299（2026-09-22 实测抓到）：**授权拒绝返回的是扁平错误信封，没有 `gbt_result`**。
        # 原来只从 `r["gbt_result"]` 里读 ⇒ 被门拒绝时 gr 为空 ⇒ 打印出
        # `status: unknown · denied: false` —— **门明明说"拒了"，报表却说"未知、没拒"**。
        # 这正是"给故障喘息"：读的人以为只是没跑通，不会去看缺什么授权。
        # 修法：没有 gbt_result 就把**顶层**当 body 看（denied/missing/scopes/how_to_grant 都在顶层），
        #      并把缺的作用域与**怎么授权**原样打出来。
        gr = r.get("gbt_result") or (r if isinstance(r, dict) else {})
        denied = (gr.get("status") == "denied"
                  or gr.get("denied") is True
                  or bool(gr.get("missing"))
                  or bool(gr.get("missing_scopes")))
        out = {"gate": "run_task", "kind": argv[1],
               "status": gr.get("status") or ("ok" if r.get("ok") else "unknown"),
               "stamp": bool(r.get("gbt_stamp")),
               "denied": denied,
               "result": gr.get("result") if isinstance(gr.get("result"), (dict, list, str)) else str(gr)[:400]}
        # 🔴 2026-09-23 磨：把「这次进没进信封」**打在结果里**，不用翻 37 MB 账本。
        # `--no-envelope` 时它是负对照的活证据（应当 found=True 且 synced=False）。
        # 🔴 2026-10-17 加固：信封回填失败不许把整发调用弄崩 —— 它一崩，下面的收步就执行不到，
        #    盘上就留孤儿步（实测攒出 16 个）。吞异常可以，但必须留一行字。
        try:
            out["_信封"] = _ledger_echo(argv[1], _t0)
        except Exception as _ee:                                 # noqa: BLE001
            out["_信封"] = {"error": "%s: %s" % (type(_ee).__name__, str(_ee)[:100])}
            sys.stderr.write("[five-dim] 信封回填失败: %s: %s\n"
                             % (type(_ee).__name__, str(_ee)[:80]))
        # ── 同步护栏收步：这一发执行有没有把**关联区块**弄坏 ──────────────────
        if _nh is not None and _nh_pre is not None:
            try:
                _post = _nh.guard_post(watch, expect=expect)
                # 拦不拦的分档（写清，免得"写类 op 被误拦"或"只读 op 漏拦"）：
                #   只读能力位（safe=True）· 显式 --enforce · 声明了 --expect ⇒ **拦**（非零退出）；
                #   写类 op 未声明 ⇒ **只报不拦**（变动照实列出，读的人自己判）。
                _enforce = bool(enforce_flag or _meta.get("safe") or expect)
                out["_邻域同视"] = {
                    "ok": bool(_post.get("ok")),
                    "enforced": _enforce,
                    "watch": list(watch),
                    "pre": _nh_pre.get("blocks"),
                    "changed": _post.get("changed"),
                    "missing": _post.get("missing"),
                    "added": _post.get("added"),
                    "unexpected": _post.get("unexpected"),
                    "expect": _post.get("expect"),
                    "note": ("关联区块有**意外变动** ⇒ 这就是『修一个地方坏一个地方』，必须交代或回退"
                             if not _post.get("ok") else "邻域无意外变动"),
                }
                if not _post.get("ok") and not _enforce:
                    out["_邻域同视"]["note"] += "（写类 op：**只报不拦**；要拦加 --enforce 或 --expect）"
            except Exception as _we:                             # noqa: BLE001
                out["_邻域同视"] = {"ok": False, "enforced": False,
                                    "note": "比对跑不动：%s" % str(_we)[:120]}
        if denied:
            # 拒绝要说全：缺哪个作用域、怎么授权、谁有权授 —— 不然人不知道下一步做什么
            out["missing_scopes"] = gr.get("missing") or gr.get("missing_scopes") or []
            out["reason"] = str(gr.get("reason") or gr.get("message") or "")[:200]
            out["how_to_grant"] = gr.get("how_to_grant") or []
            out["note"] = str(gr.get("note") or "")[:160]

        # ── 机械钩子收步：证据取自**真实返回**，不伪造机检 check ─────────────
        # 为什么证据只放这几条：`step_close` 的纪律是硬证据优先、自由文本一律判 partial。
        # 这里**不编造** `check:<名>=pass`（那需要账上有真执行记录，编了就是造假），
        # 所以自动收步多半判 partial —— 那是**如实**，不是失败：
        #   · 信封覆盖率（brainless_ratio）由这一步真正修好；
        #   · 要判 ok 就再跑 `check <sid> <名> --contains "..." -- <命令>` 补机检。
        if sid and _se is not None:
            try:
                _ev = ["cap:%s=%s" % (argv[1], out["status"]),
                       "gate=run_task stamp=%s denied=%s" % (out["stamp"], out["denied"])]
                if out.get("missing_scopes"):
                    _ev.append("missing_scopes=%s" % ",".join(map(str, out["missing_scopes"])))
                if out.get("_邻域同视"):
                    _n = out["_邻域同视"]
                    _ev.append("neighbor_watch=%s changed=%d unexpected=%d" % (
                        "ok" if _n.get("ok") else "red",
                        len(_n.get("changed") or []), len(_n.get("unexpected") or [])))
                _se.step_close(sid, evidence=_ev,
                               note="五维合一·万能插 自动信封（cap 入口亲笔）")
            except Exception as _ce:                                 # noqa: BLE001
                # 收步失败不能反过来把调用弄崩；但**不许静默** —— 吞异常可以，必须留一行字
                # （仓内纪律；2026-10-17 实测此处静默攒出 16 个孤儿步）。
                sys.stderr.write("[five-dim] 自动收步失败（步 %s 会留在盘上）: %s: %s\n"
                                 % (sid, type(_ce).__name__, str(_ce)[:80]))
        body = json.dumps(out, ensure_ascii=False, indent=1, default=str)
        LIMIT = 1500
        if not full and len(body) > LIMIT:
            out["result"] = _summarize(out.get("result"))
            out["_truncated"] = {"原始字符数": len(body), "默认上限": LIMIT,
                                 "说明": "为让输出**始终是合法 JSON**，这里把 result 收窄成摘要；"
                                 "要全量请加 `--full`，或收窄 payload（例如指定 op/domain）"}
            body = json.dumps(out, ensure_ascii=False, indent=1, default=str)
        print(body)
        _rc = 0 if out["status"] in ("ok", "success") else 1
        # 邻域有意外变动 ⇒ 只有**该拦**的那一档才非零（写类未声明只报不拦，见 `_邻域同视.enforced`）
        if (out.get("_邻域同视") and not out["_邻域同视"].get("ok")
                and out["_邻域同视"].get("enforced")):
            _rc = 1
        return _rc

    # 提示必须**跟真命令对齐**：命中就打最近邻，没命中就把完整名单给出来。
    import difflib
    near = difflib.get_close_matches(cmd, COMMANDS, n=1, cutoff=0.5)
    _note = f"未知命令 {cmd}"
    if near:
        _note += f"。你是不是要：{near[0]}"
    print(json.dumps({"ok": False, "note": _note, "supported": list(COMMANDS)},
                     ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
