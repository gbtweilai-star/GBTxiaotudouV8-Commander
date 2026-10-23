# gbt-capability: tripo
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""tripo 能力 — AI 生成 3D 数字人 + 自动绑骨 + 100+ 动作（Tripo3D API）。

用户要求的"随便什么动作都可以完成"的实现路径：
  1. 文本/图片 → AI 生成 3D 美少女模型（text-to-model / image-to-model）
  2. 自动绑骨 rig（biped 人形骨骼，约 30 秒）
  3. 动画重定向 retarget（100+ 预设：idle/walk/run/jump/climb/slash/shoot…）
  4. 下载绑骨+动画 GLB → 桌宠渲染层直接播放任意动作

API（developers.tripo3d.ai 实测文档）：
  Base URL: https://openapi.tripo3d.ai/v3（国内站 developers.tripo3d.com）
  认证: Authorization: Bearer {TRIPO_API_KEY}
  端点: POST /generation/text-to-model → task_id → GET /tasks/{task_id} 轮询
        POST /animations/rig-check（免费预检）→ POST /animations/rig（25 积分）
        POST /animations/retarget（10 积分/个，批量最多 5）
  状态: queued → running → success/failed/cancelled

需要 TRIPO_API_KEY（Tripo 控制台创建）。未配置时如实报告。
"""
from __future__ import annotations

import os
import time

from .security import net_guard, policy

BASE = os.environ.get("TRIPO_BASE_URL", "https://openapi.tripo3d.ai/v3")


def _gbt_key_from_official_cli():
    """★ 2026-10-15 加：**第三级**取 key —— 读 Tripo **官方 CLI 的配置**。

    为什么必须加（实测）：
      本文件原来的两级是「环境变量 → DPAPI 保险箱」。本机 `~/.tripo/config.json`（167 B）
      里**确实有 tsk_ 键**（前缀 `tsk_` · 长度 47），但这条链读不到它 ⇒ 一律 **401**。
      官方报错原文：*API key must start with 'tsk_'. If you are sending a client_id
      (tcli_...), use the secret key instead*。

      这与她 2026-09-25 写下的那条是**同一类坑** ——
        *"原来只有 os.environ 这一级 …… 看起来'密钥没配'，其实配了、只是读不到"*。

    纪律：**不回显密钥**，只回报来源（`official-cli:profiles.default` 这样）。
    """
    import json as _j, os as _o
    try:
        with open(_o.path.expanduser("~/.tripo/config.json"), encoding="utf-8") as fh:  # ★ 内置 open（不是 os.open！）
            cfg = _j.load(fh)
    except Exception as _e:
        # ★ 不许静默吞：把原因带出去（**不回显路径以外的敏感信息**）
        return "", "read_failed:%s" % type(_e).__name__
    ap = cfg.get("active_profile") or "default"
    pool = cfg.get("profiles") or {}
    for nm, src in (("profiles[%s]" % ap, pool.get(ap) or {}),
                    ("profiles.default", pool.get("default") or {}),
                    ("root", cfg)):
        k = str(src.get("api_key") or src.get("apiKey") or "").strip()
        if k.startswith("tsk_"):
            return k, "official-cli:%s" % nm
    return "", ""


def _key():
    """取 Tripo 密钥：**环境变量 → DPAPI 保险箱**，两级。

    🔴 2026-09-25 修（F2 的现场）：原来只有 `os.environ.get("TRIPO_API_KEY")` 这一级。
    而本机的 Tripo 密钥**只配在 Windows 的 User 作用域**，本机进程是在那些变量写入**之前**
    起的 ⇒ `os.environ` 里**一个都没有** ⇒ 这条链看起来"密钥没配"，其实配了、只是**读不到**。
    （这正是 F2 那条故障的机制：**不是没配，是没继承**。）

    修法与主人令一致（「密钥跟双向插件一样、可以自动读取」）：先看环境变量（谁先给谁优先），
    环境里没有就**从保险箱解**（`store/secrets/tripo_api.dpapi`，DPAPI/CurrentUser）。
    **明文只进内存**，不进日志、不进读数；本函数返回的是密钥本身，调用方不许把它打出来。
    """
    # ★ 2026-10-15：**第三级（官方 CLI 配置）优先试** ——
    #   它必须排在最前：上一版插在两级 return 之后 / 插进 docstring 里，
    #   **永不执行** ⇒ 加完仍 401（两次都实测咬到）。
    _k3, _src3 = _gbt_key_from_official_cli()
    if _k3:
        return _k3

    env = os.environ.get("TRIPO_API_KEY", "").strip()
    if env:
        return env
    try:
        from . import deepseek_key as _dk

        key, _source = _dk.load_from_vault("tripo")
        return (key or "").strip()
    except Exception:  # noqa: BLE001
        # 保险箱不可用（非 Windows / 库不在 / 解不开）不许把整条链弄崩 —— 如实退回"没有"
        return ""


def _headers():
    return {"Authorization": f"Bearer {_key()}",
            "Content-Type": "application/json"}


# 🔴 2026-10-19 修（主人点破「她的密钥不是存有吗」）：
#    密钥**确实存着**（`~/.tripo/config.json` 里的 `tsk_Ge…BEzE`，第三级取钥读到的就是它），
#    但 `TRIPO_BASE_URL` 指到了 **`openapi.tripo3d.com`（中国站）**，而账号是 **`.ai`（国际站）** 的
#    ⇒ 同一把钥在 `.com` 上就是 `HTTP 401 Invalid API key`。
#    实测：同一把钥打 `.ai` **不返 401**（返 404 是因为我猜错了路径），打 `.com` 才 401。
#    所以这里做成**双域名回退**：先打配置的那个；401/无法解析时自动换另一个，并在回执里记下用了哪个。
BASE_ALT = ("https://openapi.tripo3d.ai/v3" if "tripo3d.com" in BASE
            else "https://openapi.tripo3d.com/v3")
BASE_USED = {"base": BASE, "switched": False, "why": ""}


def _try_bases(fn):
    """先试 BASE，失败（401/接不通）再试 BASE_ALT；两边都失败就把两条原始报错一起抛。"""
    first_err = None
    for i, b in enumerate((BASE, BASE_ALT)):
        try:
            out = fn(b)
            if i == 1:
                BASE_USED.update({"base": b, "switched": True,
                                  "why": "配置的 %s 报错，换到 %s 成功" % (BASE, b)})
            else:
                BASE_USED.update({"base": b, "switched": False, "why": ""})
            return out
        except Exception as e:                                    # noqa: BLE001
            msg = str(e)
            if first_err is None:
                first_err = "%s → %s" % (b, msg[:160])
            # 只有 401/403/连接类错误值得换域名；业务错误（400/422）换域名没意义
            if not any(t in msg for t in ("401", "403", "无法", "connection", "Timeout", "timed out")):
                raise
    raise RuntimeError("两个域名都失败：%s" % first_err)


def _post(path, body):
    import json

    def _do(base):
        response = net_guard.safe_request_json(
            base + path, method="POST", headers=_headers(),
            body=json.dumps(body).encode("utf-8"), timeout=60,
            max_bytes=8_000_000, allow_private=policy.is_trusted(),
        )
        if response["status"] >= 400:
            raise RuntimeError(f"HTTP {response['status']}: {response.get('text', '')[:300]}")
        data = response.get("json")
        if not isinstance(data, dict):
            raise RuntimeError("Tripo 返回非 JSON 对象")
        return data

    return _try_bases(_do)


def _get(path):
    def _do(base):
        response = net_guard.safe_request_json(
            base + path, headers=_headers(), timeout=60,
            max_bytes=8_000_000, allow_private=policy.is_trusted(),
        )
        if response["status"] >= 400:
            raise RuntimeError(f"HTTP {response['status']}: {response.get('text', '')[:300]}")
        data = response.get("json")
        if not isinstance(data, dict):
            raise RuntimeError("Tripo 返回非 JSON 对象")
        return data

    return _try_bases(_do)


def balance():
    """查积分余额（验证密钥有效性）。"""
    if not _key():
        return {"ok": False, "status": "needs_dependency",
                "missing": "TRIPO_API_KEY",
                # 🔴 提示语也要改：原来只教 `setx` —— 而 `setx` 写的是 User 作用域，
                #    **当前进程读不到**（要重启才有），这就是 F2 那个坑。
                #    现在补上"不用重启"的那条路：收进保险箱。
                "hint": "Tripo 控制台 platform.tripo3d.ai 创建 API Key，然后二选一："
                        "① 收进本仓保险箱（**不用重启**）："
                        "`\"<key>\" | python -m gbt_allinone.deepseek_key set --profile tripo`；"
                        "② 或者 setx TRIPO_API_KEY <key>（写 User 作用域，**要重启宿主进程才读得到**）"}
    try:
        r = _get("/account/balance")
        return {"ok": True, "balance": r.get("data", {})}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:200]}


def text_to_model(prompt, out_format="glb"):
    """文本生成 3D 模型（美少女数字人等），返回 task_id。"""
    if not _key():
        return {"ok": False, "status": "needs_dependency", "missing": "TRIPO_API_KEY"}
    r = _post("/generation/text-to-model", {"prompt": prompt, "format": out_format})
    return {"ok": r.get("code") == 0, "task_id": r.get("data", {}).get("task_id"),
            "raw": r}


def upload_file(image_path):
    """上传本地图片到 Tripo，返回 file_token（多视图/单视图都复用它）。

    Tripo v3 实测：`POST /files` 返回 `data.file_token`（旧文档写的 image_token 已作废）。
    """
    if not _key():
        return {"ok": False, "status": "needs_dependency", "missing": "TRIPO_API_KEY"}
    boundary = "----gbttripo"
    with open(image_path, "rb") as f:
        img_data = f.read()
    ext = os.path.splitext(image_path)[1].lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"{os.path.basename(image_path)}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n").encode() + img_data + \
        f"\r\n--{boundary}--\r\n".encode()
    # 🔴 2026-10-19：上传这条也要**双域名回退**（上一版只改了 _get/_post，upload_file 还直拼 BASE
    #    ⇒ `image_to_model` 仍然 401，因为 upload 先打 .com 就死了）。
    def _upload(base):
        return net_guard.safe_request_json(
            base + "/files", method="POST", body=body,
            headers={"Authorization": f"Bearer {_key()}",
                     "Content-Type": f"multipart/form-data; boundary={boundary}"},
            timeout=120, max_bytes=8_000_000,
            allow_private=policy.is_trusted(),
        )

    def _do(base):
        r = _upload(base)
        if r["status"] >= 400:
            raise RuntimeError(f"HTTP {r['status']}: {r.get('text', '')[:300]}")
        return r

    response = _try_bases(_do)
    if response["status"] >= 400:
        return {"ok": False,
                "error": f"HTTP {response['status']}: {response.get('text', '')[:300]}"}
    up = response.get("json") or {}
    token = up.get("data", {}).get("file_token") or up.get("data", {}).get("image_token")
    if not token:
        return {"ok": False, "error": "上传失败", "raw": up}
    return {"ok": True, "file_token": token, "raw": up}


def image_to_model(image_path, out_format="glb", model="v3.1-20260211"):
    """图片生成 3D 模型（先上传文件再引用 file_token）。"""
    if not _key():
        return {"ok": False, "status": "needs_dependency", "missing": "TRIPO_API_KEY"}
    up = upload_file(image_path)
    if not up.get("ok"):
        return up
    # 图生 3D（Tripo v3: file 字段用 file_token，不要包成 {"image_token": ...}）
    r = _post("/generation/image-to-model", {"file": {"file_token": up["file_token"]},
                                             "model": model})
    return {"ok": r.get("code") == 0, "task_id": r.get("data", {}).get("task_id"),
            "raw": r}


def multiview_to_model(image_paths, model="v3.1-20260211"):
    """多视图生成 3D 模型（正/侧/背… 一起喂，几何比单视图准）。

    image_paths: 2–4 张图，建议顺序 [front, left, back, right]。返回 task_id。
    """
    if not _key():
        return {"ok": False, "status": "needs_dependency", "missing": "TRIPO_API_KEY"}
    if not 2 <= len(image_paths) <= 4:
        return {"ok": False, "error": "多视图需要 2–4 张图"}
    files = []
    for p in image_paths:
        up = upload_file(p)
        if not up.get("ok"):
            return {"ok": False, "error": f"上传失败 {p}: {up.get('error')}"}
        files.append({"type": "png", "file_token": up["file_token"]})
    r = _post("/generation/multiview-to-model", {"files": files, "model": model})
    return {"ok": r.get("code") == 0, "task_id": r.get("data", {}).get("task_id"),
            "raw": r}


def task_status(task_id):
    """查任务状态（queued/running/success/failed）。"""
    if not _key():
        return {"ok": False, "status": "needs_dependency", "missing": "TRIPO_API_KEY"}
    r = _get(f"/tasks/{task_id}")
    d = r.get("data", {})
    return {"ok": r.get("code") == 0, "status": d.get("status"),
            "progress": d.get("progress"), "output": d.get("output", {})}


def rig_check(task_id):
    """绑骨前检查（免费）：确认模型可绑骨 + 推荐绑骨类型。"""
    if not _key():
        return {"ok": False, "status": "needs_dependency", "missing": "TRIPO_API_KEY"}
    r = _post("/animations/rig-check", {"original_model_task_id": task_id})
    d = r.get("data", {})
    # Tripo v3: rig-check 也是异步的，返回 task_id，需轮询
    check_task_id = d.get("task_id")
    if check_task_id:
        st = wait_task(check_task_id, max_wait_s=180, poll_s=5)
        if st.get("status") == "success":
            out = st.get("output", {})
            return {"ok": True, "rig_type": out.get("rig_type"),
                    "eligible": out.get("riggable", False)}
        else:
            return {"ok": False, "error": f"rig-check 失败: {str(st)[:300]}"}
    return {"ok": r.get("code") == 0, "rig_type": d.get("rig_type"),
            "eligible": d.get("eligible", False)}


def rig(task_id, rig_type="biped", out_format="glb"):
    """自动绑骨（25 积分，约 30 秒）：给模型加人形骨骼+权重。"""
    if not _key():
        return {"ok": False, "status": "needs_dependency", "missing": "TRIPO_API_KEY"}
    r = _post("/animations/rig", {"original_model_task_id": task_id,
                                  "rig_type": rig_type,
                                  "out_format": out_format})
    return {"ok": r.get("code") == 0, "task_id": r.get("data", {}).get("task_id")}


def animate(rig_task_id, animation="idle", out_format="glb", in_place=True):
    """动画重定向（10 积分/个）：给绑骨模型套预设动作。

    animation: idle/walk/run/dive/climb/jump/slash/shoot/hurt/fall/turn…
    可传 list 批量（最多 5 个）。
    """
    if not _key():
        return {"ok": False, "status": "needs_dependency", "missing": "TRIPO_API_KEY"}
    body = {"original_model_task_id": rig_task_id,
            "bake_animation": True, "animate_in_place": in_place}
    if isinstance(animation, list):
        body["animations"] = animation[:5]
    else:
        body["animation"] = animation
    r = _post("/animations/retarget", body)
    return {"ok": r.get("code") == 0, "task_id": r.get("data", {}).get("task_id")}


def wait_task(task_id, max_wait_s=300, poll_s=5):
    """轮询任务到完成（success/failed），返回最终输出。"""
    t0 = time.time()
    while time.time() - t0 < max_wait_s:
        st = task_status(task_id)
        if st.get("status") in ("success", "failed", "cancelled"):
            return st
        time.sleep(poll_s)
    return {"ok": False, "error": f"超时 {max_wait_s}s", "last": st if 'st' in dir() else {}}


def full_pipeline(prompt="二次元美少女桌宠数字人，全身，Q版比例，青蓝色全息服装，素模，T-pose",
                  animations=None):
    """一条龙：文生模型 → 绑骨 → 动画 → 返回 GLB 下载地址。"""
    if not _key():
        return {"ok": False, "status": "needs_dependency", "missing": "TRIPO_API_KEY",
                "hint": "platform.tripo3d.ai 注册（送免费积分）→ 创建 Key → setx TRIPO_API_KEY"}
    # 1. 生成
    g = text_to_model(prompt)
    if not g.get("ok"):
        return g
    st = wait_task(g["task_id"], max_wait_s=600)
    if st.get("status") != "success":
        return {"ok": False, "error": "生成失败", "detail": st}
    model_task_id = g["task_id"]
    # 2. 绑骨
    rc = rig_check(model_task_id)
    rg = rig(model_task_id, rig_type=rc.get("rig_type") or "biped")
    if not rg.get("ok"):
        return rg
    rst = wait_task(rg["task_id"], max_wait_s=300)
    if rst.get("status") != "success":
        return {"ok": False, "error": "绑骨失败", "detail": rst}
    # 3. 动画
    outputs = []
    if animations:
        an = animate(rg["task_id"], animations)
        if an.get("ok"):
            ast_ = wait_task(an["task_id"], max_wait_s=300)
            outputs = ast_.get("output", {})
    return {"ok": True, "model_task": model_task_id, "rig_task": rg["task_id"],
            "output": rst.get("output", {}), "animations": outputs}


def status():
    """tripo 状态：配置/余额/能力清单。"""
    if not _key():
        return {"ok": True, "configured": False,
                "capability": "文生3D→绑骨→100+动作（配置 TRIPO_API_KEY 后可用）",
                "hint": "platform.tripo3d.ai 注册（送免费积分）→ 创建 Key → setx TRIPO_API_KEY"}
    bal = balance()
    return {"ok": True, "configured": True, "balance": bal.get("balance"),
            "ops": ["text_to_model", "image_to_model", "multiview_to_model", "upload_file",
                    "rig_check", "rig", "animate", "wait_task", "full_pipeline"]}


def run(op="status", **params):
    """tripo 统一入口：status/balance/text_to_model/image_to_model/multiview_to_model/
    upload_file/rig_check/rig/animate/wait_task/full_pipeline。"""
    if op == "status":
        if not _key():
            return {"ok": True, "configured": False,
                    "hint": "配置 TRIPO_API_KEY 后可：文生3D→绑骨→100+动作"}
        return balance()
    if op == "balance":
        return balance()
    if op == "text_to_model":
        return text_to_model(params.get("prompt", ""), params.get("out_format", "glb"))
    if op == "image_to_model":
        return image_to_model(params.get("image_path", ""))
    if op == "multiview_to_model":
        return multiview_to_model(params.get("image_paths", []))
    if op == "upload_file":
        return upload_file(params.get("image_path", ""))
    if op == "task_status":
        return task_status(params.get("task_id", ""))
    if op == "rig_check":
        return rig_check(params.get("task_id", ""))
    if op == "rig":
        return rig(params.get("task_id", ""), params.get("rig_type", "biped"))
    if op == "animate":
        return animate(params.get("task_id", ""), params.get("animation", "idle"))
    if op == "wait_task":
        return wait_task(params.get("task_id", ""), int(params.get("max_wait_s", 300)))
    if op == "full_pipeline":
        return full_pipeline(params.get("prompt", ""), params.get("animations"))
    raise ValueError(f"未知 op: {op}（可用: status/balance/text_to_model/image_to_model/"
                     f"multiview_to_model/upload_file/task_status/rig_check/rig/animate/"
                     f"wait_task/full_pipeline）")
