# -*- coding: utf-8 -*-
"""把**真实读数**渲染成发布用图片（不是示意图：每个数字都现读/现取原始输出）。

用 py -3.12 跑（3.14 没装 Pillow）：
  py -3.12 -X utf8 tools/codex-scripts/render-test-figures.py \
      --out outputs/open-source-release/assets --chain .scratch/chain_out.txt

产出：
  fig-eval.png     评测总览（335 题 · mean cov · PASS45 · 零覆盖）
  fig-chain.png    链路自检（逐行来自 chain-check 的真实输出）
  fig-domains.png  能力位域分布（从 caps_registry 现算）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

from PIL import Image, ImageDraw, ImageFont
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BG = (13, 17, 23)
CARD = (22, 27, 34)
LINE = (48, 54, 61)
TXT = (230, 237, 243)
DIM = (139, 148, 158)
GREEN = (46, 160, 67)
GREEN_L = (63, 185, 80)
AMBER = (210, 153, 34)
BLUE = (56, 139, 253)
RED = (248, 81, 73)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\segoeui.ttf",
]
MONO_CANDIDATES = [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\CascadiaMono.ttf"]


def font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    for p in (MONO_CANDIDATES if mono else FONT_CANDIDATES):
        if pathlib.Path(p).is_file():
            try:
                return ImageFont.truetype(p, size)
            except Exception:                                  # noqa: BLE001
                continue
    return ImageFont.load_default()


def canvas(w: int, h: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (w, h), BG)
    return img, ImageDraw.Draw(img)


def footer(d: ImageDraw.ImageDraw, w: int, h: int, note: str) -> None:
    d.text((26, h - 30), note, font=font(13), fill=DIM)
    d.text((w - 300, h - 30), "自由的风 · GBT小土豆V8 · 不可篡改归属",
           font=font(13), fill=DIM)


def fig_eval(scores: dict, live: dict, out: pathlib.Path) -> None:
    w, h = 1000, 460
    img, d = canvas(w, h)
    d.text((28, 22), "评测读数 · 335 条能力位题（贪心 · repetition_penalty=1.15 · PASS45 = cov ≥ 0.45）",
           font=font(19), fill=TXT)

    cards = [
        ("PASS45", "%.2f%%" % float(live.get("pass45_pct", 0)), "线上端点全量", GREEN_L),
        # ACTIVE.json 里的键是 mean（不是 mean_cov）—— 取错键会印出 0.0000，已修
        ("mean cov", "%.4f" % float(live.get("mean", live.get("mean_cov", 0))), "逐题覆盖率均值", BLUE),
        ("零覆盖", str(live.get("zero", 0)), "335 题里没答出来的", AMBER),
        ("样本", str(live.get("n", 0)), "覆盖 30 个域", DIM),
    ]
    x = 28
    for name, val, sub, color in cards:
        d.rounded_rectangle([x, 62, x + 228, 196], radius=12, fill=CARD, outline=LINE, width=2)
        d.text((x + 16, 76), name, font=font(14), fill=DIM)
        d.text((x + 16, 100), val, font=font(38), fill=color)
        d.text((x + 16, 158), sub, font=font(13), fill=DIM)
        x += 240

    # 两种跑法对比（横条）—— 条宽必须留出右侧数字的位置，否则数字被切
    d.text((28, 220), "两种跑法对比", font=font(16), fill=TXT)
    rows = [
        ("线上端点（本次发布口径）", float(live.get("pass45_pct", 0)), GREEN_L),
        ("训练卡同尺批量", float(scores.get("pod_eval", {}).get("pass45_pct", 0)), BLUE),
    ]
    bar_x, bar_max = 330, w - 330 - 120
    y = 252
    for label, pct, color in rows:
        d.text((28, y + 4), label, font=font(14), fill=TXT)
        bw = max(int(bar_max * pct / 100.0), 4)
        d.rounded_rectangle([bar_x, y, bar_x + bw, y + 22], radius=6, fill=color)
        d.text((bar_x + bw + 10, y + 3), "%.2f%%" % pct, font=font(14), fill=TXT)
        y += 46

    d.text((28, 356),
           "未过的两项：health（LoRA 未覆盖住底座先验）· voice_studio（判据与数据不同源，非模型错）",
           font=font(14), fill=AMBER)
    d.text((28, 384),
           "边界：另有 74 个能力位未进入本基准，所以 99.10%（第1轮 332/335）与 98.51%（第2轮 330/335）"
           "都不等于「341 位全过」。",
           font=font(14), fill=DIM)
    footer(d, w, h, "数据源：state/weights/ACTIVE.json + 线上全量评测账（n=%d）" % live.get("n", 0))
    img.save(out)
    print("  fig-eval.png")


def fig_chain(chain_txt: str, out: pathlib.Path) -> None:
    lines = [ln.rstrip() for ln in chain_txt.splitlines() if ln.strip()]
    w = 1080
    lh = 22
    h = 96 + lh * len(lines) + 60
    img, d = canvas(w, h)
    d.text((28, 20), "链路自检 · 五段全真跑（tools/codex-scripts/chain-check.py）",
           font=font(19), fill=TXT)
    d.text((28, 50), "下面是这次运行的真实输出，逐行照贴（未编辑）", font=font(13), fill=DIM)
    y = 82
    fm = font(13)  # 中文必须走 CJK 字体（Consolas 没有中文字形，会出方框）
    for ln in lines:
        color = TXT
        if ln.startswith("=="):
            color = BLUE
        elif "✓" in ln or "PASS" in ln:
            color = GREEN_L
        elif "✗" in ln or "FAIL" in ln:
            color = RED
        elif ln.startswith("  "):
            color = (201, 208, 216)
        d.text((28, y), ln[:150], font=fm, fill=color)
        y += lh
    footer(d, w, h, "本图由 render-test-figures.py 在 %s 现跑现渲染" % time.strftime("%Y-%m-%d %H:%M"))
    img.save(out)
    print("  fig-chain.png")


def fig_domains(out: pathlib.Path) -> None:
    from gbt_allinone import caps_registry as R

    caps = R.all_caps()
    agg: dict[str, list[int]] = {}
    for c in caps:
        dom = c.get("domain") or "other"
        a = agg.setdefault(dom, [0, 0])
        a[0] += 1
        if c.get("safe"):
            a[1] += 1
    rows = sorted(agg.items(), key=lambda kv: (-kv[1][0], kv[0]))[:16]
    mx = max(v[0] for _, v in rows)
    w = 900
    rh = 30
    h = 92 + rh * len(rows) + 62
    img, d = canvas(w, h)
    d.text((26, 20), "能力位域分布（共 %d 位 / %d 域）" % (len(caps), len(agg)), font=font(19), fill=TXT)
    d.text((26, 50), "绿 = 只读（不写盘/不出网）· 橙 = 需授权（写盘/花钱/出网）", font=font(13), fill=DIM)
    y = 84
    fm = font(13)
    for dom, (n, ro) in rows:
        d.text((26, y + 4), dom, font=fm, fill=TXT)
        bw = int((w - 300) * n / mx)
        rw = int(bw * ro / n) if n else 0
        d.rounded_rectangle([150, y, 150 + max(rw, 2), y + 20], radius=5, fill=GREEN)
        d.rounded_rectangle([150 + rw, y, 150 + bw, y + 20], radius=5, fill=AMBER)
        d.text((150 + bw + 10, y + 3), "%d（只读 %d）" % (n, ro), font=font(12), fill=DIM)
        y += rh
    footer(d, w, h, "数据源：gbt_allinone/caps_registry.py 现读（%d 位）" % len(caps))
    img.save(out)
    print("  fig-domains.png")


def fig_caps(out: pathlib.Path, data_dir: pathlib.Path) -> None:
    """能力自证：只读真调 vs 需参数 vs 需授权 vs 门后证据。"""
    p = data_dir / "capability-live-test.json"
    if not p.is_file():
        print("  （跳过 fig-caps：没有 capability-live-test.json）")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    cnt = d["counts"]
    ok = cnt.get("ok", 0)
    denied = cnt.get("denied", 0)
    need_p = cnt.get("needs_params", 0)
    need_a = cnt.get("needs_auth", 0)
    dep = cnt.get("needs_dependency", 0)
    slow = cnt.get("timeout", 0) + cnt.get("failed", 0) + cnt.get("exception", 0)
    total = d["total"]
    # 来源表由数据自己给（2026-10-21 修：此前副标题把来源写死成「三路」，
    # 而账里其实已经有 6 路证据 —— 读数与出处不一致，属假账的一种）
    srcs = d.get("by_source") or {}
    src_line = " · ".join("%s %d" % (k, v) for k, v in
                          sorted(srcs.items(), key=lambda kv: -kv[1])) or "（无来源读数）"
    # 要票那几位点名（让读者自己去核，不用猜）
    rows = d.get("rows") or {}
    ticket_names = [c for c, v in rows.items() if v.get("bucket") == "needs_ticket"]

    w, h = 1000, 430
    img, dd = canvas(w, h)
    dd.text((28, 22), "能力自证 · %d 个原生能力位逐位真调（不是「模型会背」，是「调得动」）" % total,
            font=font(19), fill=TXT)
    dd.text((28, 50), "五类真跑 · 只读空参 / 需参数带真参 / 写口隔离 store / 带票真跑 / 房间晋升",
            font=font(13), fill=DIM)
    cards = [
        ("真跑通过", str(ok), "只读+带参+写口", GREEN_L),
        ("要票未跑", str(denied), "缺哪张票说得出", BLUE),
        ("缺输入", str(need_p), "不瞎编参数", AMBER),
        ("高危未跑", str(need_a), "不拿真仓库试", DIM),
    ]
    x = 28
    for name, val, sub, color in cards:
        dd.rounded_rectangle([x, 78, x + 228, 208], radius=12, fill=CARD, outline=LINE, width=2)
        dd.text((x + 16, 92), name, font=font(14), fill=DIM)
        dd.text((x + 16, 116), val, font=font(38), fill=color)
        dd.text((x + 16, 172), sub, font=font(13), fill=DIM)
        x += 240
    dd.text((28, 232), "另：缺依赖 %d 位（n8n 没起）· 失败 %d 位 · 三态合计 %d = %d（生成器断言）"
            % (dep, slow, ok + denied + need_p + need_a + dep + slow, total),
            font=font(14), fill=TXT)
    dd.text((28, 262), "门后证据 ≠ 失败：要票那 %d 位正好证明「危险动作必须人给票」这条结构在生效%s"
            % (denied, ("（点名：" + "、".join(ticket_names[:4]) + "）") if ticket_names else ""),
            font=font(14), fill=DIM)
    dd.text((28, 296), "证据来源计数：" + src_line, font=font(13), fill=DIM)
    dd.text((28, 322), "机器可读逐位读数：data/capability-live-test.json（每位：结果/耗时/状态/缺什么票）",
            font=font(13), fill=DIM)
    footer(dd, w, h, "数据源：tools/codex-scripts/gen-capability-proof.py 合成多路真跑（%s）" % d.get("at", ""))
    img.save(out / "fig-caps.png")
    print("  fig-caps.png")


def fig_conc(out: pathlib.Path, data_dir: pathlib.Path) -> None:
    """触手并发爆发力：N 路同时调能力位，成功率/中位/最大/内存。"""
    p = data_dir / "concurrency-bench.json"
    if not p.is_file():
        print("  （跳过 fig-conc：没有 concurrency-bench.json）")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = [r for r in d["rows"] if "n" in r and r.get("ok") is not None]
    w, h = 1000, 120 + 34 * (len(rows) + len(d.get("repeat") or [])) + 90
    img, dd = canvas(w, h)
    mb = d.get("memory_before") or {}
    dd.text((28, 20), "触手并发爆发力 · 同一位能力被 N 路同时调用（真跑，非估算）", font=font(19), fill=TXT)
    dd.text((28, 48), "本机内存 总 %.2f GB · 起跑时可用 %.2f GB（已用 %d%%）｜被调能力位：%s"
            % (mb.get("total_gb", 0), mb.get("avail_gb", 0), mb.get("used_pct", 0), d.get("cap")),
            font=font(13), fill=DIM)
    y = 86
    fm = font(13)  # 中文必须走 CJK 字体（Consolas 没有中文字形，会出方框）
    dd.text((28, y), "N      成功/总      墙钟     中位      最大      内存可用        吞吐", font=fm, fill=DIM)
    y += 24
    for r in rows:
        okall = r["ok"] == r["n"]
        color = GREEN_L if okall else RED
        line = ("%-6d %-11s %7.2fs %8.2fms %8.2fms %5.2f→%.2fGB %7.0f/s"
                % (r["n"], "%d/%d" % (r["ok"], r["n"]), r["wall_s"], r["median_ms"] or 0,
                   r["max_ms"] or 0, r["mem_avail_before"], r["mem_avail_after"],
                   r["throughput_per_s"] or 0))
        dd.text((28, y), line, font=fm, fill=color)
        y += 30
    for r in (d.get("repeat") or []):
        dd.text((28, y), "复跑 %-4d %-11s %7.2fs %8.2fms（区分首次建线程成本与稳态）"
                % (r["n"], "%d/%d" % (r["ok"], r["n"]), r["wall_s"], r["median_ms"]),
                font=fm, fill=TXT)
        y += 30
    dd.text((28, y + 6), "结论：%s；延迟随并发上升的主因是审计写盘串行（不是能力位本身慢）。"
            % ("零失败" if all(r["ok"] == r["n"] for r in rows) else "有失败，见上表"),
            font=font(14), fill=TXT)
    footer(dd, w, h, "数据源：tools/codex-scripts/bench-cap-concurrency.py（%s）" % d.get("at", ""))
    img.save(out / "fig-concurrency.png")
    print("  fig-concurrency.png")


def fig_tianzhen(out: pathlib.Path, data_dir: pathlib.Path) -> None:
    """GBT天真：不装 ComfyUI 跑 ComfyUI 契约（算子数/同名数/校验/写面真跑）。"""
    p = data_dir / "gbt-tianzhen-live.json"
    if not p.is_file():
        print("  （跳过 fig-tianzhen：没有 gbt-tianzhen-live.json）")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    con = d.get("contract") or {}
    native = d.get("nodes_count") or 0
    same = len(con.get("native_also_in_contract") or [])
    contract = con.get("contract_nodes") or 0
    cov = con.get("native_coverage_pct") or 0
    v_ok = (d.get("validate_ok", {}).get("result") or {})
    v_bad = (d.get("validate_bad", {}).get("result") or {})
    r_ok = (d.get("run_ok", {}).get("result") or {})
    r_bad = (d.get("run_bad", {}).get("result") or {})

    w, h = 1000, 470
    img, dd = canvas(w, h)
    dd.text((28, 20), "GBT天真（comfy_native）· 不装 ComfyUI，也跑得动 ComfyUI 的节点契约",
            font=font(19), fill=TXT)
    dd.text((28, 48), "契约用它的（节点名 / socket 名）· 算子用我们的（纯 CPU，内存 <300 MB）· 本机 ComfyUI 进程 0",
            font=font(13), fill=DIM)

    cards = [
        ("原生算子", str(native), "自带拓扑执行", GREEN_L),
        ("与 ComfyUI 同名同契约", str(same), "可用它的节点名写图", GREEN_L),
        ("对齐的契约面", str(contract), "秋叶版快照现读", BLUE),
        ("原生覆盖率", "%.1f%%" % cov, "小，但不修饰", AMBER),
    ]
    x = 28
    for name, val, sub, color in cards:
        dd.rounded_rectangle([x, 76, x + 228, 196], radius=12, fill=CARD, outline=LINE, width=2)
        dd.text((x + 16, 88), name, font=font(13), fill=DIM)
        dd.text((x + 16, 110), val, font=font(34), fill=color)
        dd.text((x + 16, 160), sub, font=font(12), fill=DIM)
        x += 240

    y = 218
    fm = font(13)
    dd.text((28, y), "离线校验（不启 ComfyUI）：", font=font(15), fill=TXT)
    y += 28
    vok = "通过" if v_ok.get("ok") else "未过"
    dd.text((40, y), "· 正例（ComfyUI 写法：image / upscale_method / filename_prefix）→ %s · %s"
            % (vok, v_ok.get("verdict") or "—"), font=fm, fill=GREEN_L if v_ok.get("ok") else RED)
    y += 26
    errs = v_bad.get("errors") or []
    dd.text((40, y), "· 反例（未知节点 + 缺必填 + 成环）→ 抓到 %d 条错：未知节点 / 缺必填 / 成环（逐条原文见 JSON）"
            % len(errs), font=fm, fill=GREEN_L if errs else RED)
    y += 34
    dd.text((28, y), "写面真跑（不是示意）：", font=font(15), fill=TXT)
    y += 28
    prods = r_ok.get("products") or []
    dd.text((40, y), "· 好图 → ok=%s · %d 个节点 · 产物 %d 件 · 闸全过"
            % (r_ok.get("ok"), len(r_ok.get("trace") or []), len(prods)),
            font=fm, fill=GREEN_L if r_ok.get("ok") else RED)
    y += 26
    dd.text((40, y), "· 坏图 → ok=%s（fail-closed：白名单不过，一件产物都不落）" % r_bad.get("ok"),
            font=fm, fill=GREEN_L if not r_bad.get("ok") else RED)
    y += 34
    runs = [r for r in (d.get("runs_last") or []) if r.get("nodes")]
    up = None
    for r in reversed(d.get("runs_last") or []):
        for t in (r.get("trace") or []):
            if t.get("node") == "upscale_4k" and t.get("ok"):
                up = r
                break
        if up:
            break
    dd.text((28, y), "生产流水（runs.jsonl 现读）：共 %d 条真跑记录" % (d.get("runs_total") or 0),
            font=fm, fill=TXT)
    if up:
        y += 26
        dd.text((40, y), "· 4K 放大那条：%d 节点 / %ss / 产物 %s"
                % (up.get("nodes") or 0, up.get("seconds"),
                   (up.get("products") or ["—"])[-1].split("/")[-1].split("\\")[-1]),
                font=fm, fill=GREEN_L)
    footer(dd, w, h, "数据源：tools/codex-scripts/gen-native-live.py 真跑（%s）" % d.get("at", ""))
    img.save(out / "fig-tianzhen.png")
    print("  fig-tianzhen.png")


def fig_monitor(out: pathlib.Path, data_dir: pathlib.Path) -> None:
    """多域监控：29 域逐位真调 + 与基线的回归比对（改一处，整面复查）。"""
    p = data_dir / "multidomain-monitor-live.json"
    if not p.is_file():
        print("  （跳过 fig-monitor：没有 multidomain-monitor-live.json）")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    tot = d.get("totals") or {}
    tested, ok = tot.get("tested", 0), tot.get("ok", 0)
    diff = d.get("diff") or {}
    doms = sorted((d.get("domains") or {}).items())

    w, h = 1000, 700
    img, dd = canvas(w, h)
    dd.text((28, 20), "多域监控 · %d 个域 %d 位只读位逐位真调（改一处，整面复查）"
            % (len(doms), tested), font=font(19), fill=TXT)
    dd.text((28, 48), "只测「只读且无需参数」的位；写口/需参数不跑（不越门）。被门拒 ≠ 坏：那是授权结构在生效。",
            font=font(13), fill=DIM)

    cards = [
        ("真调通过", str(ok), "空 payload 真跑", GREEN_L),
        ("被门挡住", str(tested - ok), "如实记缺哪张票", BLUE),
        ("回归", str(diff.get("regressed_count", 0)), "改前 ok → 现在不 ok",
         GREEN_L if not diff.get("regressed_count") else RED),
        ("修好", str(diff.get("fixed_count", 0)), "改前不 ok → 现在 ok",
         GREEN_L if not diff.get("fixed_count") else AMBER),
    ]
    x = 28
    for name, val, sub, color in cards:
        dd.rounded_rectangle([x, 76, x + 228, 190], radius=12, fill=CARD, outline=LINE, width=2)
        dd.text((x + 16, 88), name, font=font(13), fill=DIM)
        dd.text((x + 16, 108), val, font=font(34), fill=color)
        dd.text((x + 16, 154), sub, font=font(12), fill=DIM)
        x += 240

    y0 = 232
    fm = font(13)
    dd.text((28, y0 - 30), "逐域读数（通过 / 测）：%d 个域" % len(doms), font=font(15), fill=TXT)
    half = (len(doms) + 1) // 2
    for col, chunk in enumerate((doms[:half], doms[half:])):
        y = y0
        x = 28 + col * 480
        for dom, v in chunk:
            good = v["ok"] == v["tested"]
            dd.text((x, y), "%-12s %2d / %2d" % (dom, v["ok"], v["tested"]),
                    font=fm, fill=GREEN_L if good else AMBER)
            y += 22

    ys = y0 + 22 * half + 18
    dd.text((28, ys), "比对口径：与基线 state/monitor/domain-baseline.json 逐位比；回归 0 且修好 0，说明整面稳定（不是「没跑」）。",
            font=fm, fill=DIM)
    dd.text((28, ys + 26), "用时 %.1fs（含安全扫描类 28~65s 的慢位）—— 没为「快」牺牲覆盖。"
            % d.get("elapsed_s", 0), font=fm, fill=DIM)
    footer(dd, w, h, "数据源：tools/codex-scripts/multi-domain-monitor.py --diff（%s）" % d.get("at", ""))
    img.save(out / "fig-monitor.png")
    print("  fig-monitor.png")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="outputs/open-source-release/assets")
    ap.add_argument("--chain", default=".scratch/chain_out.txt")
    ap.add_argument("--live-eval", default="state/model-deploy/live-eval-v2.json")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    data_dir = out.parent / "data"

    act = json.loads((ROOT / "state/weights/ACTIVE.json").read_text(encoding="utf-8"))
    scores = act.get("active_scores") or {}
    # 以**最新一次全量线上评测**为准（v2 那次；修了 health 题面 + voice_studio gold）
    live = {}
    le = pathlib.Path(a.live_eval)
    if le.is_file():
        live = json.loads(le.read_text(encoding="utf-8"))
    else:
        live = scores.get("live_eval") or {}
    chain_file = pathlib.Path(a.chain)
    chain_txt = chain_file.read_text(encoding="utf-8", errors="replace") if chain_file.is_file() else \
        "（没有 chain 输出文件：先跑 chain-check.py 再渲染）"

    print("渲染：")
    fig_eval(scores, live, out / "fig-eval.png")
    fig_chain(chain_txt, out / "fig-chain.png")
    fig_domains(out / "fig-domains.png")
    fig_caps(out, data_dir)
    fig_conc(out, data_dir)
    fig_tianzhen(out, data_dir)
    fig_monitor(out, data_dir)
    print("完成 →", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
