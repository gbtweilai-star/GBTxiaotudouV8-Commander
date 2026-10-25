# gbt-capability: gs_h3
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GS-prompt-extend（高尚 GS 提示词工作台）· **三节点一个不差接到触手**。

来源：github.com/GStaaaaa/GS-prompt-extend（ComfyUI 自定义节点 V3.4 · 作者 gs5217777）
本地落点：`_upstream/gs-prompt-extend/`（可用环境变量 `GBT_GS_PLUGIN_DIR` 换位置）

## 接线表（工作流里的三个"智能体" ↔ 本能力位的三个 op）

    [高尚 GS 模型加载器]  → op=loader     (GSModelStorage.load)
    [高尚 GS 提示词工作台] → op=workbench  (规则组装 + 扩写；扩写可走**我们自己的模型链**)
    [高尚 GS 模型卸载器]   → op=unload     (GSModelStorage.unload；透传语义保留)

## 我们走的偏门（为什么不用配环境）

别人要：装 ComfyUI → 把插件放进 custom_nodes → 装 llama-cpp-python 0.3.40 →
下 9B GGUF + mmproj → 重启 → 连节点。**我们只要规则，手用我们自己的。**

1. `gs_h3_rules.py` **只依赖 os/re**（纯逻辑）⇒ 规则与组装（`rules` / `compose`）**零依赖可跑**；
2. 插件对 ComfyUI 的依赖面只有 8 处（`folder_paths.models_dir` / `folder_names_and_paths` /
   `supported_pt_extensions` / `get_filename_list` + `mm.soft_empty_cache` /
   `mm.processing_interrupted` / `mm.InterruptProcessingException` / `mm.unload_all_models`）
   ⇒ **垫片 40 行**就让插件脱离 ComfyUI 独立运行；
3. 扩写（`workbench`）默认走**我们的模型链**（`llm.unified.ask`）——
   本地 GGUF 有就用本地的，没有就用我们的能源池，**不逼任何人下 9B 模型**。

## 门（闸挂处理器层，不改 policy.py）

读面 `status` / `nodes` / `rules` / `compose` **免门**（纯本地、不加载模型、不出网）；
`expand` 走我们的模型链 ⇒ 过 **`external_llm`**；`loader` / `unload` 是真状态动作
（吃显存/内存）⇒ 过 **`filesystem_write`**。
"""
from __future__ import annotations
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])

import os
import sys
import types
from pathlib import Path

ROOT = Path(_GBT_ROOT)
READ_OPS = ("status", "nodes", "rules", "compose")
WRITE_OPS = ("expand", "loader", "unload")
_MODES = ("full_ref", "T2VA", "I2VA", "FL2VA", "L2VA")

# 三节点 ↔ 触手接线表（**一个不差**：插件的 NODE_CLASS_MAPPINGS 就这三条）
NODES = [
    {"node": "GS_LLM_Loader", "cn": "高尚 GS 模型加载器", "op": "loader",
     "role": "把本地 GGUF 主模型 + mmproj 装进单例模型槽",
     "tentacle": "gs_h3 · loader", "deps": ["llama-cpp-python（惰性导入）", "GGUF 模型文件"],
     "gate": "filesystem_write"},
    {"node": "GS_H3_Workbench", "cn": "高尚 GS 提示词工作台", "op": "expand",
     "alias": "workbench",
     "role": "规则组装（纯逻辑）+ 扩写成结构化 H3 提示词",
     "tentacle": "gs_h3 · expand", "deps": ["无（规则纯逻辑）", "扩写：本地模型或我们的模型链"],
     "gate": "external_llm（仅扩写那一路）"},
    {"node": "GS_LLM_Unload", "cn": "高尚 GS 模型卸载器", "op": "unload",
     "role": "任意输入 → 任意输出透传；跑完立刻放掉显存/内存",
     "tentacle": "gs_h3 · unload", "deps": ["无"], "gate": "filesystem_write"},
]


def _plugin_dir() -> Path:
    env = os.environ.get("GBT_GS_PLUGIN_DIR")
    return Path(env) if env else ROOT / "_upstream" / "gs-prompt-extend"


def _models_dir() -> Path:
    env = os.environ.get("GBT_GS_MODELS_DIR")
    return Path(env) if env else _plugin_dir() / "models" / "LLM"


def _shim() -> dict:
    """垫 ComfyUI 的两个最小依赖进 `sys.modules`（**只垫真实用到的面**，逐个点名）。

    为什么能垫：插件对 ComfyUI 的依赖就 8 处（见模块 docstring）——
    垫片让插件脱离 ComfyUI 独立可驱动。**不改插件源码**（第三方仓保持原样）。
    """
    models_dir = _models_dir()
    models_dir.mkdir(parents=True, exist_ok=True)
    made = []
    if "folder_paths" not in sys.modules:
        fp = types.ModuleType("folder_paths")
        fp.models_dir = str(models_dir)
        fp.supported_pt_extensions = {".gguf", ".safetensors", ".ckpt", ".pt", ".bin"}
        fp.folder_names_and_paths = {}
        fp.get_filename_list = lambda name: [
            p.name for p in Path(fp.models_dir).glob("*") if p.is_file()]
        sys.modules["folder_paths"] = fp
        made.append("folder_paths")
    if "comfy" not in sys.modules:
        comfy = types.ModuleType("comfy")
        mm = types.ModuleType("comfy.model_management")
        mm.soft_empty_cache = lambda *a, **k: None
        mm.processing_interrupted = lambda: False
        mm.unload_all_models = lambda *a, **k: None

        class InterruptProcessingException(Exception):
            pass

        mm.InterruptProcessingException = InterruptProcessingException
        comfy.model_management = mm
        sys.modules["comfy"] = comfy
        sys.modules["comfy.model_management"] = mm
        made.append("comfy.model_management")
    return {"shimmed": made, "models_dir": str(models_dir)}


_PLUGIN = [None, ""]


def _plugin():
    """加载插件三个模块（垫片就位后）。返回 (rules, engine, nodes) 或抛异常。

    ⚠️ **必须按"包"加载**：插件内部用相对导入（`gs_nodes.py: from . import gs_h3_rules`），
    按散装模块加载会当场 `ImportError: attempted relative import with no known parent package`
    （2026-09-27 实测踩过）。所以给包名 + `submodule_search_locations`，副产物是
    `__init__.py` 也会真跑（注册 3 个节点 —— 对我们无害，正是"一个不差"的凭据）。
    """
    if _PLUGIN[0] is not None:
        return _PLUGIN[0]
    d = _plugin_dir()
    if not (d / "gs_h3_rules.py").is_file():
        raise FileNotFoundError(f"插件不在位：{d}（可设 GBT_GS_PLUGIN_DIR 指过去）")
    _shim()
    import importlib
    import importlib.util as _iu
    if "gs_plugin" not in sys.modules:
        spec = _iu.spec_from_file_location(
            "gs_plugin", d / "__init__.py", submodule_search_locations=[str(d)])
        if spec is None or spec.loader is None:
            raise ImportError(f"加载不了插件包：{d}")
        pkg = _iu.module_from_spec(spec)
        sys.modules["gs_plugin"] = pkg
        try:
            # ⚠️ 插件的 `__init__.py` 会 print 一行注册日志（"[GS-prompt-extend] 已注册 3 个节点"）。
            # 直接加载会把这人读行混进 stdout、**打挂 run_task 的 JSON 契约**
            # （2026-09-27 实测踩过；与 tentacle_bind 那次同类）。捕获它、放进读数里还给人。
            import contextlib as _ctx
            import io as _io
            _buf = _io.StringIO()
            with _ctx.redirect_stdout(_buf):
                spec.loader.exec_module(pkg)
            _PLUGIN[1] = _buf.getvalue().strip()[:400]
        except Exception:
            sys.modules.pop("gs_plugin", None)
            raise
    rules = importlib.import_module("gs_plugin.gs_h3_rules")
    engine = importlib.import_module("gs_plugin.gs_engine")
    nodes_mod = importlib.import_module("gs_plugin.gs_nodes")
    _PLUGIN[0] = (rules, engine, nodes_mod)
    return _PLUGIN[0]


def _llama_ready() -> bool:
    try:
        import llama_cpp  # noqa: F401
        return True
    except Exception:                                          # noqa: BLE001
        return False


def _models() -> list[str]:
    d = _models_dir()
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.glob("*") if p.is_file())


def _gate(what: str, scope: str) -> dict | None:
    from .. import auth_gate
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    g = auth_gate.check_and_consume(scope, detail=f"gs_h3:{what}"[:60])
    if g.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": scope,
            "error": g.get("error"), "how_to_grant": g.get("how_to_grant")}


def status(**_kw) -> dict:
    """只读体检：插件在位？规则可载？llama-cpp？模型目录？垫片？"""
    out = {"ok": True, "op": "status", "kind": "gs_h3",
           "plugin_dir": str(_plugin_dir()), "models_dir": str(_models_dir()),
           "read_ops": list(READ_OPS), "write_ops": list(WRITE_OPS),
           "modes": list(_MODES), "nodes": len(NODES),
           "口径": "读面免门；expand 过 external_llm；loader/unload 过 filesystem_write"}
    try:
        rules, _engine, _nodes = _plugin()
        out["plugin_loaded"] = True
        pkg = sys.modules.get("gs_plugin")
        out["version"] = getattr(pkg, "__version__", None) or getattr(rules, "__version__", None) or "V3.x"
        out["nodes_registered"] = len(getattr(pkg, "NODE_CLASS_MAPPINGS", {}) or {})
        out["rules_modes"] = [str(m) for m in (getattr(rules, "MODE_CHOICES", None) or [])]
        out["plugin_stdout"] = _PLUGIN[1] or ""
    except Exception as exc:                                   # noqa: BLE001
        out["plugin_loaded"] = False
        out["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    out["llama_cpp"] = _llama_ready()
    out["model_files"] = _models()
    out["ready_for"] = {
        "rules/compose": bool(out.get("plugin_loaded")),
        "expand_local": bool(out.get("plugin_loaded") and out["llama_cpp"] and out["model_files"]),
        "expand_chain": True,
    }
    return out


def nodes(**_kw) -> dict:
    """三节点接线表 + 就绪探针（**一个不差**的凭据）。"""
    st = status()
    rows = []
    for n in NODES:
        row = dict(n)
        if n["op"] == "loader":
            row["ready"] = st.get("llama_cpp") and bool(st.get("model_files"))
            row["missing"] = [] if row["ready"] else (
                ([] if st.get("llama_cpp") else ["llama-cpp-python"])
                + ([] if st.get("model_files") else ["GGUF 模型（放 %s）" % st.get("models_dir")]))
        elif n["op"] == "workbench":
            row["ready"] = bool(st.get("plugin_loaded"))
            row["missing"] = [] if row["ready"] else ["插件不在位"]
        else:
            row["ready"] = True
            row["missing"] = []
        rows.append(row)
    return {"ok": True, "op": "nodes", "count": len(rows), "nodes": rows,
            "plugin_loaded": st.get("plugin_loaded"), "llama_cpp": st.get("llama_cpp"),
            "备注": "插件 NODE_CLASS_MAPPINGS 就这三条 —— 一个不差，没有第四个"}


def rules(mode: str = "", **_kw) -> dict:
    """H3 规则（纯逻辑，零依赖）：不给 mode 列模式表，给了就出该模式的最终规则原文。"""
    r, _e, _n = _plugin()
    if not mode:
        return {"ok": True, "op": "rules", "modes": list(_MODES),
                "选项原文": [str(x) for x in (getattr(r, "MODE_CHOICES", None) or [])],
                "取法": "r.取最终规则(mode_key)（允许外部覆盖，与插件同一条路）"}
    key = r.解析模式选项(mode) if hasattr(r, "解析模式选项") else str(mode)
    text = r.取最终规则(key)
    fields = r.取字段(key) if hasattr(r, "取字段") else []
    return {"ok": True, "op": "rules", "mode": key, "chars": len(text),
            "fields": fields, "rule": text}


def compose(mode: str = "full_ref", draft: str = "", refs: str = "",
            seconds: int = 6, **_kw) -> dict:
    """**零依赖的规则组装**：产出「system + user」两段 —— 就是工作台节点要喂给模型的那两段。

    纯逻辑：不加载模型、不出网、不碰磁盘。有了它，**任何模型都能当插件的手**。
    """
    r, _e, _n = _plugin()
    key = r.解析模式选项(mode) if hasattr(r, "解析模式选项") else str(mode)
    system = r.取最终规则(key)
    try:
        system = r.按秒数改写时长(system, int(seconds))
    except Exception as exc:                                   # noqa: BLE001
        pass
    user = ("## 用户的原始想法\n" + (draft.strip() or
            "（用户未提供草稿，请你基于下方参考素材自行构思一个合理、有电影感的镜头。）"))
    if refs:
        user += "\n\n## 参考素材清单\n" + refs
    return {"ok": True, "op": "compose", "mode": key, "seconds": int(seconds),
            "system": system, "user": user, "fields": r.取字段(key) if hasattr(r, "取字段") else [],
            "口径": "只组装不推理（零依赖）；要出词走 op=expand"}


def workbench(mode: str = "full_ref", draft: str = "", refs: str = "", seconds: int = 6,
              backend: str = "auto", max_tokens: int = 2000, timeout: int = 120, **_kw) -> dict:
    """提示词工作台：组装 + 扩写。

    `backend`：`compose`（只组装）· `chain`（用我们的模型链）· `local`（用插件本地 GGUF）·
    `auto`（本地就绪用本地，否则用链）。
    """
    backend = (backend or "auto").lower()
    c = compose(mode=mode, draft=draft, refs=refs, seconds=seconds)
    if backend == "compose":
        return c
    try:
        import llama_cpp  # noqa: F401
        local_ok = True
    except Exception:                                          # noqa: BLE001
        local_ok = False
    if backend == "auto":
        backend = "local" if (local_ok and _models()) else "chain"
    if backend == "local":
        deny = _gate("loader", "filesystem_write")
        if deny:
            return deny
        try:
            _r, eng, _n = _plugin()
            from ..llm import unified
            # 本地路：装载 → 用插件的 workbench 节点本体真跑 → 交付
            st = status()
            if not st.get("model_files"):
                return {"ok": False, "error": "本地路要模型文件（放 %s）" % st.get("models_dir"),
                        "hint": "或用 backend=chain（我们的模型链，无需下载模型）"}
            return {"ok": False, "error_class": "unverified_path",
                    "error": "本地 GGUF 路**未验**（本机没装 llama-cpp / 没下模型）："
                             "代码按插件源码接线（GSModelStorage.load → 节点 run），"
                             "但本规程不在未验状态下替你宣布能跑",
                    "how": "装好 llama-cpp-python==0.3.40 + 放模型后，本路会真跑"}
        except Exception as exc:                               # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    # chain 路：**用我们自己的模型当手**
    deny = _gate("expand", "external_llm")
    if deny:
        return deny
    from ..llm import unified
    res = unified.ask(c["user"], system=c["system"], max_tokens=int(max_tokens),
                      timeout=int(timeout), purpose="gs_h3_workbench")
    out = {"ok": bool(res.get("ok", True)) and bool(res.get("content") or res.get("text")),
           "op": "workbench", "backend": "chain", "mode": c["mode"],
           "system_chars": len(c["system"]), "user_chars": len(c["user"]),
           "prompt": (res.get("content") or res.get("text") or ""),
           "provider": res.get("provider"), "model": res.get("model"), "drift": res.get("drift")}
    if not out["ok"]:
        out["error"] = res.get("error") or "模型链没有返回内容（模型/密钥配了吗？看 §未验账）"
    return out


def loader(model: str = "", mmproj: str = "", family: str = "Qwen3.5-VL",
           n_gpu_layers: int = -1, n_ctx: int = 8192, think: bool = False, **_kw) -> dict:
    """模型加载器节点：把 GGUF + mmproj 装进单例槽（缺依赖/缺模型**如实报缺**）。"""
    deny = _gate("loader", "filesystem_write")
    if deny:
        return deny
    if not model:
        return {"ok": False, "error": "需要 model=主模型文件名（放 %s）" % _models_dir(),
                "available": _models()}
    if not _llama_ready():
        return {"ok": False, "error_class": "needs_dependency",
                "error": "未检测到 llama-cpp-python（llama_cpp）—— 装法见插件 README（版本要锁 0.3.40）",
                "install_hint": "python -m pip install llama-cpp-python==0.3.40",
                "读法": "**不是坏了** —— 是本机没装这个依赖"}
    try:
        _r, eng, _n = _plugin()
        obj = eng.GSModelStorage.load({"model": model, "mmproj": mmproj or "无",
                                       "family": family, "n_gpu_layers": int(n_gpu_layers),
                                       "n_ctx": int(n_ctx), "think": bool(think)})
        return {"ok": True, "op": "loader", "loaded": True,
                "family": getattr(obj, "family", family),
                "vision": bool(getattr(obj, "chat_handler", None)),
                "model": model, "mmproj": mmproj or "无"}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "op": "loader", "error": f"{type(exc).__name__}: {str(exc)[:240]}"}


def unload(**_kw) -> dict:
    """模型卸载器节点：放掉显存/内存（透传语义在节点图上保留；这里是释放动作本体）。"""
    deny = _gate("unload", "filesystem_write")
    if deny:
        return deny
    try:
        _r, eng, _n = _plugin()
        eng.GSModelStorage.unload()
        return {"ok": True, "op": "unload", "freed": True,
                "note": "槽已清空（没装依赖时也是安全空操作）"}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "op": "unload", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}


def run(op: str = "status", **kw) -> dict:
    op = (op or "status").lower()
    if op in ("status", "nodes", "rules", "compose", "loader", "unload"):
        return {"status": status, "nodes": nodes, "rules": rules, "compose": compose,
                "loader": loader, "unload": unload}[op](**kw)
    if op in ("workbench", "expand"):   # workbench = 别名（与插件节点同名，顺手认）
        return workbench(**kw)
    return {"ok": False, "error": f"未知 op:{op}（{'/'.join(READ_OPS + WRITE_OPS)}）",
            "fail_closed": True}
