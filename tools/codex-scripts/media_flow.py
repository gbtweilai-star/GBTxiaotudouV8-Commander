# -*- coding: utf-8 -*-
r"""三方向（AI短剧 / AI电影 / AI音乐）专业级流程台 · 只读

为什么要有这一件（2026-09-23 现读后的缺口盘点）：

**已有的（不重造，直接引用）**
  · `gbt_allinone/tools/media_pipeline.py` —— 编排与审查层：
      `KINDS` 工序 · `MEDIA_KNOWLEDGE`（objective/roles/craft/quality/metrics）
      · `COMMON_GATES` 十道闸 · `plan`/`collaborate`/`launch_cycle`/`compose`/`self_review`/`publish`
      · `self_review` 九项检查 · `publish` **拒绝自带令牌绕门**
  · `projects/` 本地创作车间：三方向 × 6 格 = 18 格抽屉 + 命名规则 + 三条硬规矩
  · 各方向 `_intel/README.md`：6 个调研维度 + **固定产物文件名**（含一条绝对红线）

**缺的（本件补的就是这一层）**
  1. 本地 18 格 ↔ 框架 5/6 工序的映射**只写在散文里**（README 自认"上一版靠看着像写下的，结果三处不对"）
  2. **没有一格有"这一格什么样算合格"的判据** —— 于是 12 格空着也没有推进信号
  3. 命名规则、`_intel` 固定文件名、绝对红线 —— **全是散文，无机检**
  4. 没有一条命令能看"三条流程 × 18 格"的现状与卡点

**纪律**：只读。不改任何产物、不建目录、不抓网。
空就是空 —— **不许拿示意数据顶替**（照抄家规）。

用法:
  py -3.14 tools/codex-scripts/media_flow.py status          # 三方向 × 18 格现状 + 卡点
  py -3.14 tools/codex-scripts/media_flow.py status film     # 只看一个方向
  py -3.14 tools/codex-scripts/media_flow.py gate            # 只跑验收判据（退出码即门）
  py -3.14 tools/codex-scripts/media_flow.py spec music      # 现读该方向的专业规格（来自框架）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
PROJ = ROOT / "projects"

# ── 本地 18 格 ↔ 框架工序 的**权威映射**（来源：projects/README.md §与框架对应，实测过的那张表）
#    mp = media_pipeline.KINDS 里的工序名；None = 框架无对应格（本地更细）
#    每格带**可机检的验收判据**（不是形容词，是能跑出来的布尔量）
KIND_DIR = {"short-video": "short_video", "film": "film", "music": "music"}

STAGES: dict[str, list[dict]] = {
    "short-video": [
        {"drawer": "01-script", "mp": "script",
         "must": ["选题", "口播稿/脚本", "标题", "钩子"],
         "ext": [".md", ".txt"],
         "gate": "脚本文件在场，且首 3 秒钩子写在文内（人工复核项，见 spec）"},
        {"drawer": "02-storyboard", "mp": "storyboard",
         "must": ["分镜表", "景别/运镜/时长/情绪"],
         "ext": [".md", ".json", ".csv"],
         "gate": "分镜表在场，且每镜带 景别+运镜+时长+情绪 四个字段"},
        {"drawer": "03-raw", "mp": "assets",
         "must": ["生成原始素材（图/视频/配音）"],
         "ext": [".png", ".jpg", ".mp4", ".mov", ".wav", ".mp3", ".glb"],
         "gate": "原始素材在场；**每件都要能追到授权或自产声明**"},
        {"drawer": "04-cut", "mp": "edit",
         "must": ["剪辑工程与成片"],
         "ext": [".mp4", ".mov", ".prproj", ".fcpxml", ".json"],
         "gate": "成片在场 + 无黑帧/无静音段读数（技术读数须落盘）",
         "license_required": True},
        {"drawer": "05-publish", "mp": "export",
         "must": ["发布版成片 + 平台文案"],
         "ext": [".mp4", ".md", ".json"],
         "gate": "发布版在场；**`_shared/licenses` 必须有对应许可**（无许可不许进这一格）",
         "license_required": True},
        {"drawer": "06-cover", "mp": None,
         "must": ["封面图、首帧图"],
         "ext": [".png", ".jpg", ".webp"],
         "gate": "封面在场且**首屏可读**（框架 quality 明文）"},
    ],
    "film": [
        {"drawer": "01-screenplay", "mp": "script",
         "must": ["剧本", "人物小传", "场次表"],
         "ext": [".md", ".txt", ".fdx"],
         "gate": "剧本 + 场次表在场；每场必须改变信息或关系（框架 craft）"},
        {"drawer": "02-storyboard", "mp": "shots",
         "must": ["分镜", "镜头表", "调度"],
         "ext": [".md", ".json", ".csv"],
         "gate": "镜头表在场；**角色形象/声音/服饰/场景的连续性护照**必须同格或引用"},
        {"drawer": "03-shoot", "mp": None,
         "must": ["拍摄/生成的原始素材"],
         "ext": [".png", ".jpg", ".mp4", ".mov", ".wav", ".glb"],
         "gate": "原始素材在场；框架无对应工序（并入 shots），**本地保留以便复盘**"},
        {"drawer": "04-assets", "mp": "sound",
         "must": ["归类素材", "音效", "配乐", "字幕"],
         "ext": [".wav", ".mp3", ".srt", ".ass", ".json"],
         "gate": "音效/配乐/字幕在场；框架只单列 sound，**本地含字幕**",
         "license_required": True},
        {"drawer": "05-edit", "mp": "edit",
         "must": ["剪辑工程", "粗剪/精剪"],
         "ext": [".mp4", ".mov", ".prproj", ".fcpxml", ".json"],
         "gate": "粗剪或精剪在场 + 声画同步读数",
         "license_required": True},
        {"drawer": "06-final", "mp": "export",
         "must": ["终版 + DCP/发行母版"],
         "ext": [".mp4", ".mov", ".mxf", ".dcp", ".json"],
         "gate": "终版在场；**版权与人物授权完整**（框架 quality 明文）",
         "license_required": True},
    ],
    "music": [
        {"drawer": "01-lyrics", "mp": "lyrics",
         "must": ["歌词", "主题", "情绪线"],
         "ext": [".md", ".txt"],
         "gate": "歌词在场 + 情绪曲线/速度/调性写在文内（框架 craft：先定义这三样）"},
        {"drawer": "02-compose", "mp": None,
         "must": ["旋律/MIDI/主旋律草稿"],
         "ext": [".mid", ".midi", ".wav", ".mp3", ".json"],
         "gate": "旋律草稿在场；框架无对应工序（并入 arrangement）"},
        {"drawer": "03-arrange", "mp": "arrangement",
         "must": ["编曲工程", "分轨"],
         "ext": [".mid", ".wav", ".flac", ".json", ".als", ".flp"],
         "gate": "编曲/分轨在场；配器须为人声与核心动机留空间（框架 craft）"},
        {"drawer": "04-mix", "mp": "audio",
         "must": ["混音工程与混音版"],
         "ext": [".wav", ".flac", ".aiff", ".json"],
         "gate": "混音版在场 + **响度与真峰值合格**读数（须落盘）",
         "license_required": True},
        {"drawer": "05-master", "mp": "master",
         "must": ["母带成品"],
         "ext": [".wav", ".flac", ".aiff"],
         "gate": "母带在场 + 无爆音/削波/异常噪声读数",
         "license_required": True},
        {"drawer": "06-release", "mp": "export",
         "must": ["发行版 + 元数据（ISRC/曲目信息）"],
         "ext": [".wav", ".flac", ".json", ".csv"],
         "gate": "发行版 + **样本/声纹/旋律来源可追溯**（框架 quality 明文）",
         "license_required": True},
    ],
}

# 命名规则（projects/README.md §命名一律带日期前缀）
# 2026-09-23 自查抓到的误报：初版只允许 `<NN工序>`，把文档明文允许的**彩排件**
#   （第 4 段写 `rehearsal`，例 `20260921-film-彩排样板-rehearsal.md`）
#   判成"命名不合规" —— **检查器比文档更严**。现按文档补上 `rehearsal` 这一形态。
NAME_RE = re.compile(
    r"^\d{8}-(?:short-video|film|music)-.+-(\d{2}[a-z]+|rehearsal)(?:-v\d+)?\.[A-Za-z0-9]+$")
REHEARSAL_RE = re.compile(r"-rehearsal(?:-v\d+)?\.[A-Za-z0-9]+$", re.I)

# _intel 六维固定文件名（照抄各方向 _intel/README.md，**不许改名**）
INTEL_DIMS = ["compliance_redlines", "approval_rules", "traffic_trend",
              "audience_profile", "competitor_watch", "forbidden_lists"]
INTEL_EXT = {"compliance_redlines": ".json", "approval_rules": ".md",
             "traffic_trend": ".json", "audience_profile": ".json",
             "competitor_watch": ".json", "forbidden_lists": ".md"}
INTEL_ABSOLUTE = "forbidden_lists"      # 绝对红线（README 标 absolute）


def _files(d: Path) -> list[Path]:
    if not d.is_dir():
        return []
    return [p for p in sorted(d.rglob("*"))
            if p.is_file() and p.name not in (".gitkeep", ".cleared")]


LIC_DIR = PROJ / "_shared" / "licenses"


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return ""


def _license_index() -> dict:
    """现读素材许可账 → {仓内相对路径: sha256}。

    账由能力位 `media_license` 写（`gbt_allinone/tools/media_license.py`），
    **本器只读**：判定归门，登记归能力位 —— 一件事实一处实现（本仓老规矩）。
    ⚠️ 账读不动（文件坏/没生成）时返回 `{}` ⇒ 逐件判据自然判红，**不静默放过**。
    """
    try:
        d = json.loads((LIC_DIR / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for e in d.get("entries") or []:
        f = e.get("file")
        if f:
            out[str(f)] = str(e.get("sha256") or "")
    return out


def _mp_kinds() -> dict:
    """现读框架的权威工序定义（**不手抄**）。"""
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.tools import media_pipeline as mp
        return {"ok": True, "kinds": {k: list(v[1]) for k, v in mp.KINDS.items()},
                "labels": {k: v[0] for k, v in mp.KINDS.items()},
                "gates": list(mp.COMMON_GATES),
                "external_generators_connected": mp.knowledge().get(
                    "external_generators_connected"),
                "policy": mp.run("status").get("policy")}
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "why": "%s: %s" % (type(e).__name__, str(e)[:120])}


def check_one(kind: str, st: dict) -> dict:
    d = PROJ / kind / st["drawer"]
    fs = _files(d)
    named_bad = [p.name for p in fs if not NAME_RE.match(p.name)]
    wrong_ext = [p.name for p in fs
                 if st["ext"] and p.suffix.lower() not in st["ext"]]
 # 彩排件 ≠ 该工序成品（README：彩排是**动作**不是抽屉；真实工序由它所在抽屉决定）
    reel = [p.name for p in fs if REHEARSAL_RE.search(p.name)]
    real = [p.name for p in fs if not REHEARSAL_RE.search(p.name)]
    r = {"kind": kind, "drawer": st["drawer"], "mp": st["mp"],
         "dir_exists": d.is_dir(), "files": len(fs),
         "deliverables": len(real), "rehearsals": len(reel),
         "names_ok": not named_bad, "names_bad": named_bad[:4],
         "ext_ok": not wrong_ext, "ext_bad": wrong_ext[:4],
         "gate": st["gate"], "must": st["must"]}
    if not d.is_dir():
        r["state"] = "缺目录"
    elif not fs:
        r["state"] = "空"
    elif not real:
        r["state"] = "仅彩排"
    else:
        r["state"] = "有货"
    # 授权闸：成品格必须有许可 —— **逐件核对**（2026-09-23 第 49 轮改）
    #
 # 为什么必须改（本轮实测抓到的"判据太松会主动遮丑"）：
    #   旧判据是 `license_ok = len(_files(licenses)) > 0` —— **目录里随便有个文件就算过**。
    #   本轮我按新机制往 `_shared/licenses/` 写了一份 **0 条的 manifest.json**，
 # 旧判据**立刻**就把 `short-video/04-cut` 的 P0 报成"许可 "了 ——
    #   而那一格里 6 个件**一条记录都没有**。
    #   ⇒ 松判据不只是"抓不到"，它会**把红遮掉**。而"素材授权清单"（十道闸之一）
    #     问的本来就是**每一件**素材的授权。
    #   ⇒ 现在：该格里每一件都要在 `manifest.json` 里有 **sha256 对得上**的记录。
    if st.get("license_required"):
        man = _license_index()
        r["license_required"] = True
        r["license_dir_files"] = len(_files(LIC_DIR))   # 目录里几个文件（旧读数，留作对照）
        r["license_entries"] = len(man)                 # 账上有几条记录
        need = list(fs)
        missing = [p.name for p in need if _rel(p) not in man]
        r["license_need"] = len(need)
        r["license_registered"] = len(need) - len(missing)
        r["license_ok"] = bool(need) and not missing
        r["license_missing"] = missing[:4]
    return r


def check_intel(kind: str) -> dict:
    d = PROJ / kind / "_intel"

 # 第 97 轮补：原来 `got` 是**数文件个数**（`.exists()`）—— **丢一个 0 字节的空文件进去，
    #    维数就会涨**，而实际什么都没调研。这和第 96 轮刚堵的那条是**同一个病**：
    #    **在场被当成了合格**。⇒ 空文件不算一维（读不动也不算）。
 # 本判据只到"非空"为止 —— **每一维各自的内容契约本机没有权威口径，
    #    我不替它们编**（编了就是拿我的规矩替上游立规矩）。
    def _nonempty(n: str) -> bool:
        p = d / (n + INTEL_EXT[n])
        if not p.exists():
            return False
        try:
            return len(p.read_text(encoding="utf-8", errors="replace").strip()) > 0
        except OSError:
            return False

    got = [n for n in INTEL_DIMS if _nonempty(n)]
    empty_files = [n for n in INTEL_DIMS
                   if (d / (n + INTEL_EXT[n])).exists() and n not in got]
    red_name = INTEL_ABSOLUTE + INTEL_EXT[INTEL_ABSOLUTE]
    red = d / red_name
 # 第 96 轮补：原来只判 `.exists()` —— **在场判据**。
    #    第 95 轮我把红线文件填上、警告就消了；可**空文件或空壳同样会让警告消失** ——
    #    那就是我刚亲手造出来的一个**假绿通道**。按本仓一贯做法推成**契约判据**：
    #    非空 · 带署名 · 红线条数达标 · **写明它没覆盖什么**（留白 ≠ 没问题）。
    rc, why = {}, []
    if not red.exists():
        why.append("文件不在")
    else:
        try:
            txt = red.read_text(encoding="utf-8", errors="replace")
        except OSError as e:                                          # noqa: BLE001
            txt = ""
            why.append("读不动：%s" % str(e)[:40])
        rc = {"非空": len(txt.strip()) >= 200,
              "带署名": "开发者：自由的风" in txt,
              "红线条数": txt.count("| **"),
              "写明未覆盖": ("不收" in txt) or ("留白" in txt)}
        if not rc["非空"]:
            why.append("内容太短（%d 字符）" % len(txt.strip()))
        if not rc["带署名"]:
            why.append("没带署名")
        if rc["红线条数"] < 5:
            why.append("红线只有 %d 条（< 5）" % rc["红线条数"])
        if not rc["写明未覆盖"]:
            why.append("**没写明它没覆盖什么**（留白 ≠ 没问题）")
    return {"kind": kind, "dir": str(d.relative_to(ROOT)),
            "expected_n": len(INTEL_DIMS), "present_n": len(got),
            "missing": [n for n in INTEL_DIMS if n not in got] + (
                ["%s（在场但不合格：%s）" % (INTEL_ABSOLUTE, "、".join(why))] if why else []),
            "empty_files": empty_files,
            "absolute_redline_present": red_name in [n + INTEL_EXT[n] for n in got],
            "absolute_redline_ok": red.exists() and not why,
            "absolute_redline_why": why, "absolute_redline_checks": rc,
            "state": "已调研" if len(got) == len(INTEL_DIMS) else "未调研（保持为空，不准拿示意数据顶替）"}


def gate_report(kinds: list[str], mp: dict) -> dict:
    """把现状变成**可机检的门**（不是形容词）。"""
    problems, notes = [], []
    for k in kinds:
        for st in STAGES[k]:
            r = check_one(k, st)
            tag = "%s/%s" % (k, st["drawer"])
            if r["state"] == "缺目录":
                problems.append(("%s 抽屉不存在（README 的 18 格表里列了）" % tag, "P1"))
            elif r["state"] == "仅彩排":
 # 第 94 轮补：这条注意原来**只说"没有成品"，不说怎么才能有成品** ——
                #    读的人拿到一条**照着做不了的警告**。而答案第 79 轮就有了（`release=True`）。
                #    警告必须可行动，否则它就只是噪音。
 # 命令里的 `kind` 要**下划线**（`short_video`）—— 循环变量 `k` 是**目录名**
                #    （`short-video`，连字符）。第一版我直接把 `k` 塞进命令 ⇒ 复制粘贴**会失败**
                #    （`media_run` 不认 `short-video` 这个方向）。**可行动的提示，命令必须真的是对的。**
                notes.append("%s 只有彩排件（%d 件），**没有该工序成品** —— "
                             "彩排是动作不是成品。**怎么产出成品**："
                             "链执行器加 `release=true` 就落工序成品名（`NNstep` 形式）："
                             "`run_task(\"media_run\", {\"op\":\"run\",\"kind\":\"%s\","
                             "\"work\":\"<作品名>\",\"release\":true})`"
                             "；⚠️ 成品名 **≠ 可发布**，发布提交仍卡主人授权门。"
                             % (tag, r["rehearsals"], k.replace("-", "_")))
            elif r["files"] and not r["names_ok"]:
                problems.append(("%s 命名不合规：%s（规则 YYYYMMDD-<方向>-<作品>-<工序|rehearsal>[-vN].ext）"
                                 % (tag, ", ".join(r["names_bad"])), "P1"))
            if r["files"] and not r["ext_ok"]:
                problems.append(("%s 里放了不属于该格的类型：%s（该格收 %s）"
                                 % (tag, ", ".join(r["ext_bad"]), "/".join(st["ext"])), "P2"))
            if st.get("license_required") and r["files"] and not r.get("license_ok"):
                problems.append(("%s 是成品格，但许可**没记到件**：%d/%d 已登记（缺 %s）—— "
                                 "家规第 2 条：没有许可的素材不许进这一格"
                                 % (tag, r.get("license_registered", 0), r.get("license_need", r["files"]),
                                    "、".join(r.get("license_missing") or []) or "全部"), "P0"))
        it = check_intel(k)
        if not it["absolute_redline_present"]:
            notes.append("%s/_intel：**绝对红线文件 `forbidden_lists.md` 缺** —— "
                         "它是唯一标 absolute 的维度，喂生成端当约束、发布前当闸" % k)
    # 映射机检：本地写的 mp 工序名，必须真在框架 KINDS 里
    if mp.get("ok"):
        known = {k: set(v) for k, v in mp["kinds"].items()}
        for k in kinds:
            for st in STAGES[k]:
                if st["mp"] and st["mp"] not in known.get(KIND_DIR[k], set()):
                    problems.append(("%s/%s 声称对应框架工序 `%s`，"
                                     "但 `media_pipeline.KINDS[%s]` 里没有它 —— **映射表过时**"
                                     % (k, st["drawer"], st["mp"], KIND_DIR[k]), "P1"))
    return {"problems": problems, "notes": notes,
            "total": len(problems), "p0": sum(1 for _, s in problems if s == "P0")}


def cmd_status(kinds: list[str]) -> int:
    mp = _mp_kinds()
    print("=" * 74)
    print("三方向专业级流程台 · 现读")
    print("=" * 74)
    if mp.get("ok"):
        print("框架编排层（现读，非手抄）：")
        print("  工序  %s" % json.dumps(mp["kinds"], ensure_ascii=False))
        print("  十道闸 %s" % " · ".join(mp["gates"][:5]) + " …（共 %d 道）" % len(mp["gates"]))
        print("  发布策略 %s" % mp["policy"])
        print("  ⚠️ 外部生成端已接线 = %s —— **这是编排/审查层，不是生成服务**"
              % mp["external_generators_connected"])
    else:
        print("🔴 框架编排层读不到：%s" % mp.get("why"))
    print()
    tot = {"有货": 0, "仅彩排": 0, "空": 0, "缺目录": 0}
    for k in kinds:
        print("── %s ──" % k)
        for st in STAGES[k]:
            r = check_one(k, st)
            tot[r["state"]] = tot.get(r["state"], 0) + 1
            mark = {"有货": "✅", "仅彩排": "🟡", "空": "⚠ ", "缺目录": "❌"}[r["state"]]
            mpname = st["mp"] or "（框架无对应格）"
            extra = ""
            if r.get("license_required"):
 # 空格子**不该显示" 缺全部"**：没有件就没有素材要许可（第 49 轮自查抓到的读数缺陷）
                if not r.get("license_need"):
                    extra = "  许可 —（空格，无需许可）"
                elif r.get("license_ok"):
                    extra = "  许可 ✅ %d/%d 已登记" % (r.get("license_registered", 0),
                                                  r.get("license_need", 0))
                else:
                    extra = "  许可 ❌ %d/%d（缺 %s）" % (r.get("license_registered", 0),
                                                    r.get("license_need", 0),
                                                    "、".join(r.get("license_missing") or []) or "全部")
            print("  %s %-14s ↔ %-14s %s  成品 %d / 彩排 %d%s"
                  % (mark, st["drawer"], mpname, r["state"],
                     r["deliverables"], r["rehearsals"], extra))
            if r["files"] and not r["names_ok"]:
                print("        命名不合规：%s" % ", ".join(r["names_bad"]))
        it = check_intel(k)
        print("  📊 _intel  %d/%d 维  %s%s"
              % (it["present_n"], it["expected_n"], it["state"],
                 ("" if it["absolute_redline_ok"] else
                  ("  ⚠️ 绝对红线 forbidden_lists.md **在场但不合格**（%s）"
                   % "、".join(it["absolute_redline_why"])) if it["absolute_redline_present"]
                  else "  ⚠️ 绝对红线 forbidden_lists.md 缺")))
        print()
    print("汇总：有货 %d · 仅彩排 %d · 空 %d · 缺目录 %d（共 18 格）"
          % (tot["有货"], tot["仅彩排"], tot["空"], tot["缺目录"]))
    g = gate_report(kinds, mp)
    print("-" * 74)
    print("验收判据：%d 条问题（P0 %d）" % (g["total"], g["p0"]))
    for t, s in g["problems"][:20]:
        print("  [%s] %s" % (s, t))
    for n in g["notes"][:5]:
        print("  [注意] %s" % n)
    print("-" * 74)
    print("没做的（诚实账）：")
    print("  · 每一格的『人工复核项』（首 3 秒钩子/连续性护照/情绪曲线）**机器判不了**，")
    print("    只能判『该文件在不在、命名对不对、许可有没有』——**在场 ≠ 合格**。")
    print("    例外（第 65 轮起）：**件本身**另有契约判据，由链执行器在收件时过 ——")
    print("    （下面这份清单是**现算**的，不是我手写的；分镜那格 %s）" % _storyboard_criteria_n())
    for _ln in _validator_lines():
        print("      · %s" % _ln)
    print("    判不过 ⇒ `input_rejected`；**本机判不了** ⇒ `input_unjudged`（独立状态，")
    print("    既不许冒充合格、也不算它不合格）。面板上逐步标着『契约判据 / 仅在场』：`media-console.html`。")
    print("  · 本件**不生成任何东西**；生成端未接线（框架自己标 external_generators_connected=False）。")
    print("  · `_intel` 三格全空 = **未调研**，不是『没问题』。要填必须走出网授权。")
    return 1 if g["p0"] else (2 if g["total"] else 0)


def _storyboard_criteria_n() -> str:
    """分镜契约**一共几条判据** —— 现算，不手抄（本仓纪律：数字不许手抄）。

    拿一个**空件**去问校验器：它会逐条报出所有判据的通过与否，条数就是判据面的大小。
    读不到就如实说读不到，**不许填一个我记得的数**。

    ⚠️ 必须**按包**导入（`sys.path` + `from gbt_allinone.tools import …`）：
    本器第一版用 `spec_from_file_location` 按**路径**加载，`media_run` 里的相对导入
    当场报「attempted relative import with no known parent package」，
    于是这行印出「判据条数读不到」——**看着像没实现，其实是加载姿势不对**
    （本仓第 N 次"读数对不上，先怀疑自己怎么把它读出来的"）。
    """
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from gbt_allinone.tools import media_run as _mr
        n = len(_mr._validate_storyboard('{"shots": []}').get("criteria") or [])
        return "现算 %d 条判据" % n if n else "判据条数读不到"
    except Exception:                                                 # noqa: BLE001
        return "判据条数读不到（不敢填一个我记得的数）"


def _validator_lines():
    """**现算**「哪几步的人写件要过契约判据」—— 一个词都不手写。

    🔴 这一行原来是**手写清单**（只列了 script/screenplay/storyboard），
    于是第 66 轮接上 `lyrics`、第 69 轮接上 `arrangement` 之后，
    **闸门的诚实账没跟着长** —— 账不实比账不全更糟。
    ⇒ 改成从 `media_run._VALIDATORS` 现读。读不到就说读不到。
    """
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from gbt_allinone.tools import media_run as _mr
        src = dict(getattr(_mr, "_VALIDATOR_SRC", {}) or {})
        return ["`%s` → %s" % (k, v) for k, v in sorted(src.items())]
    except Exception:                                                 # noqa: BLE001
        return ["读不到（不填我记得的那几个）"]


def cmd_gate(kinds: list[str]) -> int:
    mp = _mp_kinds()
    g = gate_report(kinds, mp)
    print(json.dumps(g, ensure_ascii=False, indent=1))
    return 1 if g["p0"] else (2 if g["total"] else 0)


def cmd_spec(kind: str) -> int:
    """现读该方向的**专业规格**（来自框架 MEDIA_KNOWLEDGE，不手抄）。"""
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.tools import media_pipeline as mp
    except Exception as e:                                   # noqa: BLE001
        print("读不到 media_pipeline：%s" % type(e).__name__)
        return 3
    k = KIND_DIR.get(kind, kind)
    if k not in mp.KINDS:
        print("未知方向：%s（可填 short-video / film / music）" % kind)
        return 2
    label, stages = mp.KINDS[k]
    kn = mp.MEDIA_KNOWLEDGE[k]
    print("=" * 74)
    print("%s（%s）· 专业规格 · 现读自 media_pipeline" % (label, k))
    print("=" * 74)
    print("目标：%s" % kn["objective"])
    print("\n专业角色（%d 人）：" % len(kn["roles"]))
    for i, r in enumerate(kn["roles"], 1):
        print("  %2d. %s" % (i, r))
    print("\n手艺判据（craft）：")
    for c in kn["craft"]:
        print("  · %s" % c)
    print("\n质量判据（quality）：")
    for c in kn["quality"]:
        print("  · %s" % c)
    print("\n成效指标（metrics）：")
    for c in kn["metrics"]:
        print("  · %s" % c)
    print("\n框架工序（%d 格）：%s" % (len(stages), " → ".join(stages)))
    print("十道通用闸：%s" % " → ".join(mp.COMMON_GATES))
    print("\n本地抽屉 ↔ 框架工序：")
    for st in STAGES[kind]:
        print("  %-14s ↔ %s" % (st["drawer"], st["mp"] or "（框架无对应格·本地更细）"))
        print("      该格必须放：%s" % " / ".join(st["must"]))
        print("      机检判据：%s" % st["gate"])
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("kind", nargs="?", default="")
    ns = ap.parse_args(argv)
    kinds = [ns.kind] if ns.kind in STAGES else list(STAGES)
    if ns.kind and ns.kind not in STAGES and ns.cmd in ("status", "gate"):
        print("未知方向：%s（可填 short-video / film / music）" % ns.kind)
        return 2
    if ns.cmd == "status":
        return cmd_status(kinds)
    if ns.cmd == "gate":
        return cmd_gate(kinds)
    if ns.cmd == "spec":
        return cmd_spec(ns.kind or "")
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
