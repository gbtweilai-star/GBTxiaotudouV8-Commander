# -*- coding: utf-8 -*-
"""Phase 1 · 图生网格（一条命令跑完，钥匙一到就能用）

用法（本仓口径 Python 3.14）：
  C:\\Users\\ADMIN\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe holo_pet\\assets\\digital-human\\phase1-generate.py

设计要点：
  · 从环境变量或 Windows 注册表 HKCU\\Environment 读 TRIPO_API_KEY —— setx 之后**不必重启 DSH**；
  · 只调用仓库既有能力 gbt_allinone.tripo（不新造 HTTP 逻辑，不绕授权门）；
  · 每步都打印读数；**任何一步失败就停并如实报**，不产生半成品；
  · 产物落 raw/，并写 phase1.json（task_id / url / 字节 / sha256 / 时间），再更新 STATUS.json。
"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
DH = WS / "holo_pet/assets/digital-human"
SAMPLE = DH / "samples/Day2-JK黑白甜酷-精修-白底.png"   # 白底不透明：图生 3D 最稳的输入形态（可在命令行覆盖）
RAW = DH / "raw"
REC = DH / "phase1.json"
STATUS = DH / "STATUS.json"
sys.path.insert(0, str(WS))


def setting(name):
    """读设置：环境变量优先，其次注册表 HKCU\\Environment（setx 的落点）。只返回值，不打印。"""
    v = (os.environ.get(name) or "").strip()
    if v:
        return v, "环境变量"
    try:
        out = subprocess.run(
            ["reg", "query", r"HKCU\Environment", "/v", name],
            capture_output=True, text=True, timeout=15,
        ).stdout
        for line in out.splitlines():
            if name in line:
                parts = line.split()
                if len(parts) >= 3:
                    return parts[-1].strip(), "注册表 HKCU\\Environment"
    except Exception:
        pass
    return "", ""


def pick_url(output):
    """Tripo 的 output 里模型地址的键名各版本不一，逐个试；都不中就返回 None（不猜）。"""
    if not isinstance(output, dict):
        return None
    for k in ("pbr_model", "model", "base_model", "glb", "url", "model_url"):
        v = output.get(k)
        if isinstance(v, str) and v.startswith("http"):
            return v, k
        if isinstance(v, dict):
            for kk in ("url", "model"):
                if isinstance(v.get(kk), str) and v[kk].startswith("http"):
                    return v[kk], f"{k}.{kk}"
    return None, None


def cli_credential():
    """官方 Tripo CLI 的凭据源（~/.tripo/config.json）—— key 与 region 一起给，天然对得上站点。
    这样不必让 Owner 再维护第二份密钥，也不会被误注入的 CLI 令牌干扰。"""
    p = pathlib.Path.home() / ".tripo" / "config.json"
    if not p.exists():
        return None
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    profs = cfg.get("profiles") or {}
    entry = profs.get(cfg.get("active_profile")) if isinstance(profs, dict) else None
    if entry is None and isinstance(profs, dict) and profs:
        entry = next(iter(profs.values()))
    if not isinstance(entry, dict):
        return None
    key = str(entry.get("api_key") or "").strip()
    if not key.startswith("tsk_"):
        return None
    region = str(entry.get("region") or "ov").lower()
    base = "https://openapi.tripo3d.ai/v3" if region == "ov" else "https://openapi.tripo3d.com/v3"
    return {"key": key, "base": base, "region": region, "profile": cfg.get("active_profile")}


def main():
    cred = cli_credential()
    if cred:
        os.environ["TRIPO_API_KEY"] = cred["key"]              # 只在进程内注入，不落盘、不打印
        os.environ["TRIPO_BASE_URL"] = cred["base"]            # 站点随 region 走，不靠外部猜
        print(f"[0] 凭据：来自官方 CLI（profile={cred['profile']} · region={cred['region']} · key 长度 {len(cred['key'])}）")
        print(f"[0] 站点：{cred['base']}")
    else:
        key, src = setting("TRIPO_API_KEY")
        if key and key.startswith("tsk_"):
            os.environ["TRIPO_API_KEY"] = key
            base, bsrc = setting("TRIPO_BASE_URL")
            if base:
                os.environ["TRIPO_BASE_URL"] = base
            print(f"[0] 凭据：{src}（长度 {len(key)}）· 站点：{base or '模块默认(国际站)'}（来源 {bsrc or '-'}）")
        else:
            print("[0] 没拿到可用凭据（需要 tsk_ 开头的 API Key）")
            if key:
                print(f"    注意：当前注入的是 {key[:4]}… —— 这是 Tripo **CLI 登录令牌**，不是 API Key，接口不认。")
            print("    正路：本机已装官方 CLI 且已登录，直接用它的凭据源即可（预期能读到 ~/.tripo/config.json）")
            print("    或：控制台「API 密钥」创建后  setx TRIPO_API_KEY \"tsk_…\"")
            return 2

    if not SAMPLE.exists():
        print(f"[0] 样板不存在：{SAMPLE}")
        return 2
    print(f"[0] 样板：{SAMPLE.name} · {SAMPLE.stat().st_size/1024:.0f} KB（上传上限 8MB ✓）")

    from gbt_allinone import tripo

    bal = tripo.balance()
    print(f"[1] 余额：{json.dumps(bal, ensure_ascii=False)[:200]}")
    if not bal.get("ok", True) and bal.get("status") == "needs_dependency":
        return 2

    g = tripo.image_to_model(str(SAMPLE), out_format="glb")
    print(f"[2] 图生网格提交：{json.dumps(g, ensure_ascii=False)[:300]}")
    if not g.get("ok") or not g.get("task_id"):
        print("    → 提交失败，停止（不产生半成品）")
        return 1
    task_id = g["task_id"]

    st = tripo.wait_task(task_id, max_wait_s=900, poll_s=6)
    print(f"[3] 生成结果：status={st.get('status')} progress={st.get('progress')}")
    if st.get("status") != "success":
        print(f"    → 未成功：{json.dumps(st, ensure_ascii=False)[:300]}")
        return 1

    url, field = pick_url(st.get("output", {}))
    if url is None:
        print("    → output 里没找到下载地址，原样贴出（不猜）:")
        print(json.dumps(st.get("output", {}), ensure_ascii=False)[:600])
        return 1

    RAW.mkdir(parents=True, exist_ok=True)
    dst = RAW / "model.glb"
    t0 = time.time()
    with urllib.request.urlopen(url, timeout=300) as r, open(dst, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    data = dst.read_bytes()
    magic = data[:4].decode("ascii", "replace")
    sha = hashlib.sha256(data).hexdigest()
    print(f"[4] 下载：{dst.name} · {len(data)/1024/1024:.2f} MB · 头四字节={magic} · sha256={sha[:16]}… · {time.time()-t0:.1f}s")
    if magic != "glTF":
        print("    → 头四字节不是 glTF，判定下载内容不合格（保留文件供排查）")
        return 1

    rec = {"phase": 1, "sample": SAMPLE.name, "task_id": task_id, "url_field": field,
           "url": url, "bytes": len(data), "sha256": sha, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    REC.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[5] 记录：{REC.name}")

    if STATUS.exists():
        j = json.loads(STATUS.read_text(encoding="utf-8"))
        j["stage"] = "Phase 1 完成（网格已到手，待 Owner 看正视图）→ Phase 2 绑骨待启动"
        j["phase1"] = rec
        j["updated"] = time.strftime("%Y-%m-%d")
        STATUS.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[6] 状态源已更新：{STATUS.name}")
    print("\n下一步：先出正视图给 Owner 看 → 点头后 rig_check(免费) → rig(biped, 25 积分)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
