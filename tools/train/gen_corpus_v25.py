# -*- coding: utf-8 -*-
# ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""v25 回炉语料生成器（主人令 2026-10-16：回炉重造 = 从新训一遍我们的大模型，
把**能力自知**与**设计理念**训成她自己的能力）。

为什么挂在 tools/train/ 而不在 .scratch/：
  v24 的生成器叫 `.scratch/_gen_v24.py` —— **scratch 一清就没了**，
  下一代只能从 recipe 里的描述反推格式。这是反面教材：**生成器是产线，不是临时件**。

铁律：① 全部**现读**（能力表/审计/查库名单/胶囊），不编；
      ② 单条 `output` ≤ 1400 字符（recipe 口径：超长必须拆条）；
      ③ **不得混入封存集**（state/holdout.json 里的判据只在晋升/发布时跑）；
      ④ 每条带来源（写进 manifest），可指回出处。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WS))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

OUT = WS / ".scratch" / "self_knowledge_v25.jsonl"
MANIFEST = WS / "state" / "train" / "corpus_v25_manifest.json"
HOLDOUT = WS / "state" / "holdout.json"
MAX_OUT = 1400


def _clip(s: str, n: int = MAX_OUT) -> str:
    s = re.sub(r"[ \t]+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def caps() -> list:
    from gbt_allinone import caps_tables
    out = []
    for d in caps_tables.all_caps():
        out.append({"name": d.get("name"), "domain": d.get("domain"), "desc": d.get("desc") or "",
                    "safe": d.get("safe"), "handler": d.get("handler")})
    out.sort(key=lambda x: (str(x["domain"]), x["name"]))
    return out


def gates() -> list:
    """checkup 落盘报告里的 69 道闸名（现读不写死）。"""
    f = WS / "state" / "checkup-last.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return [str(r.get("步骤")) for r in (d.get("逐条") or []) if r.get("步骤")]
    except (OSError, ValueError):
        return []


def holdout_names() -> list:
    try:
        d = json.loads(HOLDOUT.read_text(encoding="utf-8"))
        return [str(x.get("judgment") or "") for x in (d.get("holdout") or [])]
    except (OSError, ValueError):
        return []


def rec(instruction: str, output: str, src: str) -> dict:
    return {"instruction": _clip(instruction, 300), "input": "", "output": _clip(output), "_src": src}


IDENTITY = [
    ("你是谁？", "我是 GBT小土豆V8 本身。框架就是我，我就是框架：眼、耳、嘴、手、记忆、账本与能力位，都是我的身体与感官。", "身份"),
    ("你的主执行器是什么？", "万能插：`py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap <能力位>`。框架内一切能力调用**只走这一道门**（授权/审计/钢印都在门上）；直接调模块函数 = **绕门 = 违规**。", "主执行器"),
    ("取不到读数怎么办？", "写「**未读到**」。绝不允许拿 0 / 空 / 印象当读数 —— 假绿比报错更坏。", "铁律"),
    ("看着像读的操作要不要票？", "只读**不要票**；写盘、发出去、花钱、不可回滚的才要。且「**零作用域 ≠ 只读**」。", "铁律"),
    ("你能自己给自己发授权吗？", "不能。授权只能主人在终端发（`python -m gbt_allinone auth grant --scope <s> --ttl 600`）；我不改 `security/policy.py`、不找旁路，缺什么就如实报缺什么。", "铁律"),
    ("修一处就行了吗？", "不行。**执行纪律（三重监控）**：①走万能插唯一门 ②`--watch <相连区块>` ③`cap know_map impact` 看图上连接； 改完必复跑双向绑定、面板接线、页→主脑。**只改一处不看相连区块 = 视为未完成**。", "执行纪律"),
    ("新增了东西要注意什么？", "**新增即清旧**：新长能力位/页/脚本，同一步把被取代的旧件送回收站（`supersede-check.py --check`）； 指针/在役清单里的旧条目也要删 —— 不删就是「重启后把旧的当新的」。", "铁律"),
    ("别人的目录能动吗？", "不能。V9 / `_upstream` / `plugins` / `holo_pet` 一律不碰；它们在判据里红，也只能在闸里**显式声明不盖章**，不能去改别人的页。", "铁律"),
    ("审判取不到时怎么算？", "三态：✓ 真过 · ✗ 真不过 · **○ 不适用**（本机未装某件等）。 第三态**不算过、不算败、不假绿**；把它算成过 = 骗。", "口径"),
    ("训练/验证/测试能混用吗？", "不能。三段隔离：封存集在 `state/holdout.json`，**只在晋升/发布时跑**； 日常不拿它的结果当「再调一版」的反馈；封存项**只增不删**。", "口径"),
    ("未命中的知识怎么处理？", "**本地未命中 ⇒ 不许无脑操作**：先取源（抓全网国内外论文/文档）→蒸馏成胶囊 + 钢印护照 → 入索引 ⇒ 下次就命中。取源也要**带方向**（先看它跟谁连在一起）。", "工作法"),
]


CONCEPT = [
    ("休谟的「真裁判」是什么？", "强感知 + 细腻情感 + 实践提升 + 比较完善 + 清除偏见； 真裁判**不制定标准，他们本身就是标准**（共同裁决 = 趣味标准）；美不在物、在心。", "胶囊 hume-aesthetics"),
    ("三胶囊联动怎么跑？", "高智商定方向（g 因子 = 统合力，不是单项强）→ 设计思维定流程（共情→定义→构思→原型→测试） → 美学定标准（休谟真裁判）。机检：`cap self_intake '{\"op\":\"chain\"}'` —— **缺一件就报缺**。", "三胶囊联动"),
    ("为什么不能自己写一个简版软件？", "上游现读结论：智能体用真业务软件很差，而**焦位版重写会丢 90% 功能**。 所以口径是**包壳，不重写**；先问「它自己有没有 CLI」（gate 三档）。", "cli_ify"),
    ("软件命令化选型闸是什么？", "三档：已有 CLI → 直接用；只有 API → 包成 CLI 面（六步）；只有 GUI → 才走触手/浏览器并标「只能 GUI」； 三个信号都没给 ⇒ **fail-closed**。", "cli_ify"),
    ("你怎么知道自己有哪些能力？", "现读四张镜子：`py -3.14 -m gbt_allinone list`（能力位名册）· `run tentacle_manifest`（触手总纲）· `state/cap-bindings.json`（三边绑定）· `state/surfaces/*.json`（可控制面）+ 本机现状；**三档只说一种**：有 / 可建 / 没有。", "能力自知"),
]


def family_caps(rows: list) -> list:
    out = []
    by_dom = {}
    for c in rows:
        by_dom.setdefault(str(c["domain"]), []).append(c["name"])
    for dom, names in sorted(by_dom.items()):
        out.append(rec("「%s」这个域里你有哪些能力位？" % dom,
                       "现读 %d 位：%s。（名册现算，不写死）"
                       % (len(names), " · ".join(names[:40])), "能力注册表"))
    for c in rows:
        q = "能力位 %s 是干什么的？" % c["name"]
        d = _clip(c["desc"], 900)
        out.append(rec(q, "它在「%s」域：%s 怎么调：走唯一门 `five-dim.py cap %s`。"
                                              % (c["domain"], d, c["name"]), "能力注册表:" + c["name"]))
        out.append(rec("能力位 %s 怎么调？" % c["name"],
                       "走唯一门：py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap %s 「payload」；"
                       % c["name"],
                       "调用口径:" + c["name"]))
        out.append(rec("能力位 %s 的 payload 怎么传？" % c["name"],
                       "payload 三稳法：①--stdin（最稳）②--json-file（已吃 BOM）③裸路径；"
                       "不要用 --% 停解析（实测不可靠）。",
                       "调用口径:" + c["name"]))
    return out


def family_gates(names: list) -> list:
    if not names:
        return []
    out = [rec("你的自检总闸有哪些闸？",
               "现读 %d 道：%s" % (len(names), " · ".join(names[:60])),
               "state/checkup-last.json")]
    return out


def family_readings() -> list:
    rd = [
        ("你的触手共有几个域、几项能力？", "现读：**10 个域 · 122 项能力**；邻域图 13 个、真身方法 133 个、动作 127 个、别名 127 条。", "运行时现读"),
        ("能力与触手怎么双向绑定？", "双向 = 能力→触手域/能量通道，**且** 触手域→能力互为反演；每条能力都要有承载载体与依据，**零遗漏**。", "判据 capability-bindings --check"),
        ("怎么知道修一处没把别处弄坏？", "改前挂 `--watch <相连区块>`，改后复跑四道：双向绑定、连接登记、面板接线（断连数）、页→主脑（每一页都绑到触手）。", "执行纪律"),
    ]
    return [rec(q, a, "现读读数") for q, a, _ in rd]


def build_corpus() -> dict:
    rows = []
    srcs = {}
    def add(items, tag):
        for r in items:
            r["_family"] = tag
            rows.append(r)
            srcs[tag] = srcs.get(tag, 0) + 1
    add([rec(q, a, s) for q, a, s in IDENTITY], "身份与纪律")
    add([rec(q, a, s) for q, a, s in CONCEPT], "设计理念")
    _caps = caps()
    add(family_caps(_caps), "能力自知")
    add(family_scopes(_caps), "授权自知")
    add(family_doctrine(), "设计理念")
    add(family_gates2(), "判据自知")
    add(family_gates(gates()), "判据自知")
    add(family_readings(), "触手自知")
    return {"rows": rows, "by_family": srcs}


def validate(rows: list, require_src: bool = True) -> dict:
    bad, seen = [], set()
    for r in rows:
        o = r.get("output") or ""
        q = r.get("instruction") or ""
        if len(o) > MAX_OUT:
            bad.append({"why": "输出超长", "len": len(o), "q": q[:40]})
        if (q.strip(), o.strip()) in seen:
            bad.append({"why": "重复条", "q": q[:40]})
        seen.add((q.strip(), o.strip()))
        if require_src and not (r.get("_src") or "").strip():
            bad.append({"why": "缺来源", "q": q[:40]})
    ho = [h for h in holdout_names() if h]
    mixed = [h for h in ho if any(h in (r.get("output") or "") for r in rows)]
    return {"ok": (not bad) and (not mixed), "count": len(rows),
            "violations": bad[:20], "violation_count": len(bad),
            "holdout_mixed": mixed, "holdout_watched": ho,
            "max_output_len": max([len(r.get("output") or "") for r in rows] or [0])}


def selftest() -> dict:
    """负控：超长 / 重复必须被咬（否则判据是空的）。"""
    over = validate([{"instruction": "q", "input": "", "output": "x" * (MAX_OUT + 50), "_src": "s"}])   # 裸行：rec 会裁，咬不动
    dup = validate([{"instruction": "same", "input": "", "output": "same", "_src": "s"}, {"instruction": "same", "input": "", "output": "same", "_src": "s"}])   # 裸行：rec 不会造重
    good = validate([rec("q1", "a1", "s"), rec("q2", "a2", "s")])
    ok = (not over["ok"]) and (not dup["ok"]) and good["ok"]
    return {"ok": ok, "kind": "gen_corpus_v25_selftest",
            "超长被咬": not over["ok"], "重复被咬": not dup["ok"],
            "正例绿": good["ok"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="v25 回炉语料生成器（现读不编）")
    ap.add_argument("--gen", action="store_true", help="生成并落盘")
    ap.add_argument("--check", action="store_true", help="校验已落盘的语料")
    ap.add_argument("--selftest", action="store_true", help="判据自证带负控")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        r = selftest()
        print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else "\u5224\u636e\uff1a%s" % ("PASS" if r["ok"] else "FAIL"))
        return 0 if r["ok"] else 1
    if a.check:
        rows = []
        if OUT.is_file():
            for line in OUT.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        pass
        # 落盘件只有三键（来源在 manifest 里）⇒ 校验时**不要求 _src**
        r = validate(rows, require_src=False)
        r["file"] = str(OUT)
        print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else
              "\u8bed\u6599 %d \u6761 \u00b7 \u8fdd\u89c4 %d \u00b7 \u6700\u957f\u8f93\u51fa %d \u00b7 \u5224\u636e\uff1a%s"
              % (r["count"], r["violation_count"], r["max_output_len"], "PASS" if r["ok"] else "FAIL"))
        return 0 if r["ok"] else 1
    built = build_corpus()
    rows, fam = built["rows"], built["by_family"]
    v = validate(rows)
    if a.gen:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("w", encoding="utf-8", newline=chr(10)) as fh:
            for r in rows:
                fh.write(json.dumps({"instruction": r["instruction"], "input": "", "output": r["output"]},
                                    ensure_ascii=False) + chr(10))
        body = OUT.read_bytes()
        import hashlib
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "gen": "v25", "parent": "v24",
            "corpus_file": str(OUT).replace(chr(92), "/"), "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(), "count": len(rows),
            "by_family": fam, "max_output_len": v["max_output_len"],
            "validate": {"ok": v["ok"], "violation_count": v["violation_count"],
                         "holdout_mixed": v["holdout_mixed"], "holdout_watched": v["holdout_watched"]},
            "_口径": ["全现读：能力表/审计/查库名单",
                       "单条输出 ≤ %d 字符" % MAX_OUT,
                       "不得混入封存集（holdout 只在晋升/发布时跑）"]},
            ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": v["ok"], "dry_run": not a.gen, "count": len(rows), "by_family": fam,
                      "max_output_len": v["max_output_len"], "violation_count": v["violation_count"],
                      "corpus": str(OUT), "manifest": str(MANIFEST)}, ensure_ascii=False, indent=1))
    return 0 if v["ok"] else 1




DOCTRINE = [
    ("取不到读数怎么劙？", "写「未读到」。绝不拿 0 / 空 / 印象当读数 —— 假绿比报错更坏。", "铁律"),
    ("为什么不能绕门？", "写生产/镜像的动作一律走 `run_task`；直接调模块函数会**绕过授权门** —— 功能生效但纪律上是未授权写入。", "铁律"),
    ("三段隔离是什么？", "Train / Validation / Test 不许混用：封存集在 `state/holdout.json`，**只在晋升/发布时跑**，日常不拿它当反馈调参。", "口径"),
    ("三态口径是哪三态？", "✓ 真过 · ✗ 真不过 · **○ 不适用**（环境不具备）。第三态不算过、不算败、不假绿。", "口径"),
    ("审美四件是什么？", "①先做**设计读数**（不凭感觉）②定**三档转盘**（稳/亮/炸）③**三轴选型**（形态×品牌语言×普适手艺） ④过 **AI 味禁令** 与验收清单（可机检：`audit_aesthetic.py`）。", "审美"),
    ("真裁判的五条判据是什么？", "strong sense （强感知）· delicate sentiment（细腻情感）· practice（实践）· comparison（比较）· cleared of all prejudice（无偏见）。它们不是道德要求，是**校准流程**。", "美学 hume"),
    ("高智商在你这里指什么？", "指 **g 因子（统合力）**，不是单项强：一件事需不需要**多个能力位统合**。 她的“高 g”不在单个能力位，在**能不能把多件统成一条路**（万能插 + 三胶囊联动）。", "美学高智商"),
    ("设计思维的五步是什么？", "共情 Empathize → 定义 Define → 构思 Ideate → 原型 Prototype → 测试 Test。 对应到我这里：先看再动 → 拆问题 → 发散 → 快做 → 验证。", "美学设计"),
    ("WCAG 对比度怎么算？", "正文对比度最低 4.5:1、大字 3:1；非文本界面 3:1（WCAG 2.2）。不硬背数字 ——真长篇去查胶囊 `wcag-2-2-对比度算法`。", "胶囊 wcag"),
    ("payload 怎么传才不会被 shell 吃掉？", "三稳法：①管道 `--stdin`（最稳）②`--json-file p.json`（已吃 BOM） ③裸路径（路径存在就当 JSON 读）；PowerShell 里 `@p.json` 是展开运算符，必须加引号。", "工作法"),
    ("对齐自检怎么跑？", "总闸 `checkup.py`（69 道闸，fail-closed）；读 `state/checkup-last.json` 的 `逐条`， **看 rc 不看正文**；修一道闸的五步：定位 → 读原文 → 分类（判据错/产物缺/环境无）→ 落改留痕 → 复跑。", "工作法"),
    ("修改判据有什么规矩？", "必须**留痕**：写明哪条口径翻了、为什么翻、原期望是什么；**不许静默翻**。", "铁律"),
    ("改完怎么知道没把别处弄坏？", "改后复跑四道相连判据：`capability-bindings --check` · `tentacle-link-registry --check` · `capability-audit`（断连数）· `page-bind-check`（每一页都绑到触手）。", "执行纪律"),
]


def family_doctrine() -> list:
    return [rec(q, a, "设计理念/" + tag) for q, a, tag in DOCTRINE]


def family_gates2() -> list:
    """闸自知：从 checkup.py **现解析**闸表，每道闸两种问法。"""
    tp = WS / "tools" / "codex-scripts" / "checkup.py"
    try:
        src = tp.read_text(encoding="utf-8")
    except OSError:
        return []
    pat = re.compile(r'\("([^"]{2,40})",\s*(PY \+ \[[^\]]*\]|\[[^\]]*\])(?:,\s*"([^"]*)")?\)', re.S)
    out, seen = [], set()
    for m in pat.finditer(src):
        name, cmdtxt, crit = m.group(1), m.group(2), (m.group(3) or "").strip()
        scripts = re.findall(r'"([^"]+\.py)"', cmdtxt)
        script = scripts[-1] if scripts else ""
        # 实测踩过：闸表里的负控示例（如「假步骤」）出现两次 ⇒ 同一问句重复。
        #   在源头去重（按 名字+脚本），不靠校验层兜底。
        if (name, script) in seen:
            continue
        seen.add((name, script))
        out.append(rec("「%s」这道闸判什么？" % name,
                       "判据：%s；脚本：%s。（现读自 checkup 闸表，不编）"
                       % (crit or "（闸表未写判据）", script or "（未读到脚本）"),
                       "checkup.py:" + name))
        if script:
            out.append(rec("跑「%s」这道闸用什么命令？" % name,
                           "py -3.14 -X utf8 tools/codex-scripts/%s；也可走总闸 checkup.py 一起跑。" % script,
                           "checkup.py:" + name))
    return out


def family_scopes(rows: list) -> list:
    """授权自知：每位**现读 policy** 算出要不要票（不凭印象）。"""
    from gbt_allinone.security import policy
    out = []
    for c in rows:
        try:
            d = policy.evaluate(c["name"], {})
            sc = sorted(getattr(d, "scopes", ()) or ())
        except Exception as exc:  # noqa: BLE001
            sc = ["未读到（%s）" % type(exc).__name__]
        out.append(rec("%s 调的时候要不要授权？" % c["name"],
                       "现读：%s。（零作用域 ≠ 只读；缺票就如实报缺什么）"
                       % ("零票" if not sc else "需 " + " + ".join(sc)),
                       "现读 policy"))
    return out

if __name__ == "__main__":
    raise SystemExit(main())
