# gbt-capability: filesystem, process_execute
"""GBT小土豆V8 · 生产前镜像排练门。

Owner 定调（2026-09-14）：架构设计、假设、规划、模拟、依赖与配置一致性、
业务闭环和发布演练，全部必须在镜像多维度空间完成。只有当前镜像与计划
指纹一致且排练全绿，才允许一次性晋升生产。

这不是替代原有 mirror_space，而是给它补上生产前的四层证据：
  1. plan       计划（假设、架构、步骤、服务契约、环境契约、回滚）
  2. simulate   静态推演（文件、依赖图、端口、入口、验收定义）
  3. parity     环境镜像（平台/Python/依赖/工具/环境变量存在性/路径契约）
  4. rehearse   沙盒闭环（在镜像目录内运行受控命令并核验预期结果）

假设不再只是"收集"，而是被机器校验（假设证伪层）：
  - `path=value`（对计划内字段实测比对）/ `env:NAME` / `file:REL` / `command:ID`
    可判定的假设会被判为 verified 或 contradicted；contradicted 直接阻断晋升；
  - 无法机器判定的假设记为 unverified（不伪造通过）；计划声明
    `strict_assumptions=true` 时 unverified 同样阻断。

沙盒 ≡ 生产不是声明，而是实测：
  - parity 的 same_host 模式仍可携带显式断言（os/python/tools/dependencies/
    env_present/paths/services），断言逐项与沙盒实测值比对；
  - gate 在晋升那一刻重新捕获运行环境 profile，与排练时的沙盒 profile
    逐字段比对——排练后环境漂移（依赖/工具/环境变量/路径/服务契约变化）
    一律阻断，做到"排练全绿那一刻 = 生产晋升那一刻"。

硬规则：
  - 计划只保存环境变量名，不保存密钥值；
  - 排练命令不使用 shell，限制工作目录在镜像维度内；
  - 排练报告绑定镜像树 SHA 与计划 SHA，镜像或计划一变即自动失效；
  - 未通过 gate 时不得调用生产晋升。
"""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ._paths import STORE_DIR
from .safe_io import (
    FileLock,
    atomic_write_json,
    load_json,
    safe_relative_path,
)

_ROOT = Path(STORE_DIR) / "mirror_space"
_PLANS = _ROOT / "plans"
_REPORTS = _ROOT / "rehearsals"
_PROFILES = _ROOT / "profiles"
_RUNTIMES = _ROOT / "rehearsal_runtimes"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
_CODE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
    ".cs", ".cpp", ".c", ".h", ".php", ".rb", ".swift", ".kt",
}
_SECRET_KEY_WORDS = (
    "passphrase", "password", "secret", "token", "api_key", "apikey",
    "private_key", "mnemonic",
)
_SAFE_PLACEHOLDERS = {
    "", "<redacted>", "redacted", "required", "present", "same_host",
    "true", "false",
}
_ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ENV_REF_KEYS = (
    "env", "env_name", "env_var", "variable", "key_name", "secret_name",
    "name", "ref", "reference", "envs", "names", "refs", "references",
)
_ASSUMPTION_COMPARE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_.\[\]]*)\s*(?:==|=|equals)\s*(.+?)\s*$"
)
# 只有明确指向计划内已知字段的断言才允许判定为"被推翻"，
# 其余像 `KEY=value` 的自由文本一律记 unverified，避免误判成证伪。
_PLAN_FIELD_ROOTS = frozenset({
    "goal", "assumptions", "architecture", "steps", "services", "files",
    "environment", "rehearsal", "rollback", "production", "plan_version",
    "simulation_waves", "strict_assumptions", "static_only",
})
# 晋升时刻环境复检：只比较稳定字段，排除 captured_at 这类时间戳。
_PROFILE_STABLE_FIELDS = (
    "platform", "os", "machine", "python", "python_implementation",
    "python_executable", "python_bits", "path_style", "shell", "tools",
    "dependencies", "env_present", "paths", "services",
)


class RehearsalError(ValueError):
    """计划、推演、镜像一致性或排练失败。"""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _audit(event: str, meta: dict) -> None:
    try:
        from .store import audit
        audit(event, meta)
    except Exception:
        pass


def _canonical_name(value, default="default") -> str:
    name = str(value or default).strip()
    if (not name or name in (".", "..") or "/" in name or "\\" in name
            or "\x00" in name):
        raise RehearsalError("排练名必须是非空文件名，不能包含路径分隔符")
    return name


def _json_sha(value) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _dimension_state() -> tuple[dict, str]:
    from . import mirror_space as MS
    tree = MS.dimension_tree().get("stage") or {}
    return tree, _json_sha(tree)


def _plan_path(name: str) -> Path:
    return safe_relative_path(_PLANS, f"{_canonical_name(name)}.json")


def _profile_path(name: str) -> Path:
    return safe_relative_path(_PROFILES, f"{_canonical_name(name)}.json")


def _report_dir(name: str) -> Path:
    return safe_relative_path(_REPORTS, _canonical_name(name))


def _is_env_reference(key_l: str, value) -> bool:
    """环境变量名/引用不是秘密值；只允许名字和引用语法，不保存真实内容。"""
    if not isinstance(value, str):
        return False
    raw = value.strip()
    if not raw:
        return True
    if raw.startswith("${") and raw.endswith("}"):
        return bool(_ENV_NAME_RE.fullmatch(raw[2:-1]))
    if raw.startswith("$") and len(raw) > 1:
        return bool(_ENV_NAME_RE.fullmatch(raw[1:]))
    if any(key_l.endswith(suffix) for suffix in _ENV_REF_KEYS):
        return bool(_ENV_NAME_RE.fullmatch(raw))
    return False


def _secret_paths(value, path="$", secret_context=False,
                  key_hint="") -> list[str]:
    """找出计划中试图保存真实密钥值的字段，只返回路径，不回显值。"""
    leaks = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_l = str(key).lower()
            here = f"{path}.{key}"
            key_is_secret = secret_context or any(
                word in key_l for word in _SECRET_KEY_WORDS)
            if key_is_secret and isinstance(item, (str, int, float)):
                raw = str(item).strip()
                if (raw.lower() not in _SAFE_PLACEHOLDERS
                        and not _is_env_reference(key_l, item)):
                    leaks.append(here)
            leaks.extend(_secret_paths(item, here, key_is_secret, key_l))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            leaks.extend(_secret_paths(
                item, f"{path}[{idx}]", secret_context, key_hint))
    elif secret_context and isinstance(value, (str, int, float)):
        raw = str(value).strip()
        if (raw.lower() not in _SAFE_PLACEHOLDERS
                and not _is_env_reference(key_hint, value)):
            leaks.append(path)
    return leaks


def _waves(items: list[dict], label="节点") -> list[list[str]]:
    deps = {}
    for item in items:
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            raise RehearsalError(f"{label}缺少 id")
        if item_id in deps:
            raise RehearsalError(f"{label} id 重复: {item_id}")
        deps[item_id] = {
            str(dep) for dep in (item.get("depends_on") or []) if str(dep)
        }
    known = set(deps)
    for item_id, item_deps in deps.items():
        missing = sorted(item_deps - known)
        if missing:
            raise RehearsalError(f"{label} {item_id} 依赖不存在: {missing}")
    done, levels = set(), []
    while deps:
        ready = sorted(item_id for item_id, item_deps in deps.items()
                       if item_deps <= done)
        if not ready:
            raise RehearsalError(f"{label}依赖成环，无法排练")
        levels.append(ready)
        for item_id in ready:
            done.add(item_id)
            deps.pop(item_id)
    return levels


def _resolve_plan_field(plan: dict, dotted: str):
    """按点路径取计划内字段；不存在返回 (False, None)。"""
    node = plan
    for part in str(dotted).split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return False, None
    return True, node


def _loose_equal(expected, actual) -> bool:
    """断言字面量与计划实测值的宽比较（不改变任何判定所需信息）。"""
    if isinstance(actual, bool):
        return str(expected).strip().lower() == str(actual).lower()
    if actual is None:
        return str(expected).strip().lower() in ("none", "null")
    if isinstance(actual, (list, tuple, set, frozenset)):
        return any(_loose_equal(expected, item) for item in actual)
    if isinstance(actual, (int, float)) and not isinstance(actual, bool):
        try:
            return float(str(expected).strip()) == float(actual)
        except (TypeError, ValueError):
            return False
    text = str(expected).strip().strip("\"'")
    return text.lower() == str(actual).strip().lower()


def _verify_assumption(plan: dict, item: dict, tree: dict) -> dict:
    """把一条假设的 verify 条件落成 verified / contradicted / unverified。

    只对可机器判定的条件下结论；其余如实记 unverified，绝不伪造成通过。
    """
    verify = str(item.get("verify") or "").strip()
    base = {
        "id": item.get("id"),
        "statement": item.get("statement"),
        "verify": verify,
    }
    if not verify:
        return {**base, "status": "unverified", "detail": "未提供验证条件"}

    low = verify.lower()
    if low.startswith("env:"):
        key = verify.split(":", 1)[1].strip()
        matched = bool(os.environ.get(key))
        return {
            **base,
            "status": "verified" if matched else "contradicted",
            "detail": f"环境变量 {key} {'存在' if matched else '缺失'}",
        }
    if low.startswith("file:"):
        rel = verify.split(":", 1)[1].strip().replace("\\", "/")
        matched = rel in tree
        return {
            **base,
            "status": "verified" if matched else "contradicted",
            "detail": f"镜像文件 {rel} {'存在' if matched else '缺失'}",
        }
    if low.startswith("command:"):
        cmd_id = verify.split(":", 1)[1].strip()
        declared = {
            str(c.get("id"))
            for c in (plan.get("rehearsal") or {}).get("commands") or []
        }
        matched = cmd_id in declared
        return {
            **base,
            "status": "verified" if matched else "contradicted",
            "detail": f"验收命令 {cmd_id} {'已声明' if matched else '未声明'}",
        }

    match = _ASSUMPTION_COMPARE_RE.match(verify)
    if match:
        field_path, expected = match.group(1), match.group(2)
        if field_path.split(".", 1)[0] not in _PLAN_FIELD_ROOTS:
            return {
                **base,
                "status": "unverified",
                "detail": f"验证条件不指向计划字段: {field_path}",
            }
        found, actual = _resolve_plan_field(plan, field_path)
        if not found:
            return {
                **base,
                "status": "contradicted",
                "detail": f"计划中不存在字段 {field_path}",
            }
        if isinstance(actual, dict):
            return {
                **base,
                "status": "unverified",
                "detail": f"复合字段 {field_path} 无法直接比对",
            }
        matched = _loose_equal(expected, actual)
        return {
            **base,
            "status": "verified" if matched else "contradicted",
            "detail": (
                f"{field_path}={actual!r} 与断言 {expected.strip()!r} "
                f"{'一致' if matched else '不一致'}"
            ),
        }
    return {**base, "status": "unverified", "detail": "验证条件无法机器判定"}


def _assumption_rows(plan: dict, tree: dict) -> list[dict]:
    return [
        _verify_assumption(plan, item, tree)
        for item in plan.get("assumptions") or []
    ]


def _stable_profile(profile: dict | None) -> dict | None:
    if not isinstance(profile, dict):
        return None
    return {field: profile.get(field) for field in _PROFILE_STABLE_FIELDS}


def _profile_drift(before: dict | None, after: dict | None) -> list[dict]:
    """排练时 profile 与晋升时 profile 的稳定字段漂移。"""
    old = _stable_profile(before)
    new = _stable_profile(after)
    if old is None or new is None:
        return []
    return [
        {"field": field, "expected": old.get(field), "actual": new.get(field)}
        for field in _PROFILE_STABLE_FIELDS
        if old.get(field) != new.get(field)
    ]


def _normalize_list(value, label: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RehearsalError(f"{label}必须是列表")
    return value


def _normalize_plan(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise RehearsalError("plan 必须是 JSON 对象")
    plan = copy.deepcopy(raw)
    leaks = _secret_paths(plan)
    if leaks:
        raise RehearsalError(
            "计划中禁止保存真实密钥值，只写环境变量名；可疑字段: "
            + ", ".join(leaks[:5]))

    goal = str(plan.get("goal") or "").strip()
    if not goal:
        raise RehearsalError("计划缺少 goal")

    assumptions = _normalize_list(plan.get("assumptions"), "assumptions")
    if not assumptions:
        raise RehearsalError("计划至少要有 1 条可验证 assumption")
    normalized_assumptions = []
    for idx, item in enumerate(assumptions, 1):
        if isinstance(item, str):
            item = {"id": f"A{idx}", "statement": item, "verify": "需要人工补充验证条件"}
        if not isinstance(item, dict):
            raise RehearsalError(f"assumption #{idx} 必须是对象或字符串")
        statement = str(item.get("statement") or item.get("text") or "").strip()
        verify = str(item.get("verify") or item.get("evidence") or "").strip()
        if not statement or not verify:
            raise RehearsalError(f"assumption #{idx} 需要 statement 与 verify/evidence")
        normalized_assumptions.append({
            **item,
            "id": str(item.get("id") or f"A{idx}"),
            "statement": statement,
            "verify": verify,
        })
    plan["assumptions"] = normalized_assumptions

    architecture = plan.get("architecture")
    if not isinstance(architecture, dict):
        raise RehearsalError("计划缺少 architecture 对象")
    components = _normalize_list(
        architecture.get("components"), "architecture.components")
    if not components:
        raise RehearsalError("architecture.components 不能为空")
    normalized_components = []
    for idx, item in enumerate(components, 1):
        if isinstance(item, str):
            item = {"id": item, "responsibility": item}
        if not isinstance(item, dict):
            raise RehearsalError(f"architecture component #{idx} 必须是对象")
        comp_id = str(item.get("id") or item.get("name") or "").strip()
        responsibility = str(item.get("responsibility") or item.get("desc") or "").strip()
        if not comp_id or not responsibility:
            raise RehearsalError(f"architecture component #{idx} 缺少 id/responsibility")
        normalized_components.append({
            **item,
            "id": comp_id,
            "responsibility": responsibility,
            "depends_on": [str(x) for x in (item.get("depends_on") or [])],
        })
    architecture["components"] = normalized_components
    _waves(normalized_components, "架构组件")
    entrypoints = [
        str(x).replace("\\", "/")
        for x in _normalize_list(
            architecture.get("entrypoints"), "architecture.entrypoints")
        if str(x).strip()
    ]
    data_flow = _normalize_list(
        architecture.get("data_flow"), "architecture.data_flow")
    component_ids = {item["id"] for item in normalized_components}
    for idx, edge in enumerate(data_flow, 1):
        if not isinstance(edge, dict):
            raise RehearsalError(f"data_flow #{idx} 必须是对象")
        src = str(edge.get("from") or edge.get("source") or "").strip()
        dst = str(edge.get("to") or edge.get("target") or "").strip()
        if src not in component_ids or dst not in component_ids:
            raise RehearsalError(
                f"data_flow #{idx} 引用了不存在的组件: {src} -> {dst}")
    plan["architecture"] = architecture

    steps = _normalize_list(plan.get("steps"), "steps")
    if not steps:
        raise RehearsalError("计划至少要有一个 deployment step")
    for idx, item in enumerate(steps, 1):
        if isinstance(item, str):
            item = {"id": f"S{idx}", "action": item}
        if not isinstance(item, dict):
            raise RehearsalError(f"step #{idx} 必须是对象或字符串")
        if not str(item.get("action") or item.get("description") or "").strip():
            raise RehearsalError(f"step #{idx} 缺少 action/description")
    plan["steps"] = steps
    plan["simulation_waves"] = _waves(steps, "部署步骤")

    services = _normalize_list(plan.get("services"), "services")
    port_seen = {}
    service_names = set()
    for idx, svc in enumerate(services, 1):
        if not isinstance(svc, dict):
            raise RehearsalError(f"service #{idx} 必须是对象")
        name = str(svc.get("name") or svc.get("id") or "").strip()
        if not name:
            raise RehearsalError(f"service #{idx} 缺少 name")
        if name in service_names:
            raise RehearsalError(f"service 名重复: {name}")
        service_names.add(name)
        port = int(svc.get("port") or 0)
        if port:
            if not (0 < port < 65536):
                raise RehearsalError(f"service {name} 端口非法: {port}")
            if port in port_seen:
                raise RehearsalError(
                    f"service 端口冲突: {port} ({port_seen[port]}, {name})")
            port_seen[port] = name
        component = str(svc.get("component") or "").strip()
        if component and component not in component_ids:
            raise RehearsalError(
                f"service {name} 引用了不存在的 component: {component}")
        checkable = bool(
            svc.get("health_url") or svc.get("heartbeat_file")
            or str(svc.get("kind") or "").lower() == "windows_service"
        )
        if not checkable:
            raise RehearsalError(
                f"service {name} 缺少可验证信号（health_url/heartbeat_file/windows_service）")
    plan["services"] = services

    files = {
        str(item).replace("\\", "/")
        for item in _normalize_list(plan.get("files"), "files")
        if str(item).strip()
    }
    files.update(entrypoints)
    plan["files"] = sorted(files)
    plan["architecture"]["entrypoints"] = entrypoints

    environment = plan.get("environment")
    if environment is None:
        environment = {}
    if not isinstance(environment, dict):
        raise RehearsalError("environment 必须是对象")
    required_env = environment.get("required", environment.get("requires_env", []))
    if isinstance(required_env, dict):
        required_env = list(required_env)
    environment["required"] = [
        str(x) for x in _normalize_list(required_env, "environment.required")
        if str(x).strip()
    ]
    for key in environment["required"]:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise RehearsalError(f"环境变量名非法: {key}")
    environment["dependencies"] = [
        str(x) for x in _normalize_list(
            environment.get("dependencies"), "environment.dependencies")
        if str(x).strip()
    ]
    environment["tools"] = [
        str(x) for x in _normalize_list(
            environment.get("tools"), "environment.tools")
        if str(x).strip()
    ]
    environment["required_files"] = [
        str(x) for x in _normalize_list(
            environment.get("required_files"), "environment.required_files")
        if str(x).strip()
    ]
    production = environment.get("production") or plan.get("production")
    if not isinstance(production, dict):
        raise RehearsalError(
            "environment.production 必须声明 same_host 或显式 production profile")
    mode = str(production.get("mode") or "").strip().lower()
    if mode != "same_host" and not isinstance(production.get("profile"), dict):
        raise RehearsalError(
            "environment.production 需要 mode=same_host 或 profile 对象")
    environment["production"] = production
    plan["environment"] = environment

    rehearsal = plan.get("rehearsal")
    if rehearsal is None:
        rehearsal = {}
    if not isinstance(rehearsal, dict):
        raise RehearsalError("rehearsal 必须是对象")
    commands = _normalize_list(rehearsal.get("commands"), "rehearsal.commands")
    command_ids = set()
    for idx, spec in enumerate(commands, 1):
        if not isinstance(spec, dict):
            raise RehearsalError(f"rehearsal command #{idx} 必须是对象")
        cmd_id = str(spec.get("id") or f"C{idx}").strip()
        if cmd_id in command_ids:
            raise RehearsalError(f"rehearsal command id 重复: {cmd_id}")
        command_ids.add(cmd_id)
        argv = spec.get("argv")
        if (not isinstance(argv, list) or not argv
                or not all(isinstance(x, (str, int, float)) for x in argv)):
            raise RehearsalError(f"rehearsal command {cmd_id} 需要非空 argv 列表")
        if float(spec.get("timeout", 120) or 120) <= 0:
            raise RehearsalError(f"rehearsal command {cmd_id} timeout 必须是正数")
    static_only = bool(rehearsal.get("static_only") or plan.get("static_only"))
    acceptance = [
        str(x) for x in _normalize_list(
            rehearsal.get("acceptance") or plan.get("acceptance"),
            "rehearsal.acceptance")
        if str(x).strip()
    ]
    if commands and not acceptance:
        acceptance = sorted(command_ids)
    unknown_acceptance = sorted(set(acceptance) - command_ids)
    if unknown_acceptance:
        raise RehearsalError(f"acceptance 引用了不存在的命令: {unknown_acceptance}")
    if not static_only and not acceptance:
        raise RehearsalError(
            "代码/服务部署必须定义 rehearsal.acceptance 闭环；"
            "纯静态产物可显式设置 static_only=true")
    rehearsal["commands"] = commands
    rehearsal["acceptance"] = acceptance
    rehearsal["static_only"] = static_only
    plan["rehearsal"] = rehearsal

    rollback = plan.get("rollback")
    if (not isinstance(rollback, dict)
            or not str(rollback.get("strategy") or rollback.get("action")
                       or "").strip()):
        raise RehearsalError(
            "计划缺少可执行 rollback.strategy/action")
    plan["rollback"] = rollback
    plan["plan_version"] = 1
    return plan


def define_plan(name: str, plan: dict) -> dict:
    """定义/覆盖镜像排练计划。只保存契约和环境变量名，不保存密钥值。"""
    name = _canonical_name(name)
    normalized = _normalize_plan(plan)
    record = {
        "name": name,
        "defined_at": _now(),
        "plan_sha": _json_sha(normalized),
        "plan": normalized,
    }
    atomic_write_json(_plan_path(name), record)
    _audit("mirror_plan_defined", {
        "name": name,
        "plan_sha": record["plan_sha"][:12],
        "steps": len(normalized["steps"]),
        "services": len(normalized["services"]),
    })
    return {"ok": True, **record}


def get_plan(name: str = "default") -> dict:
    name = _canonical_name(name)
    record = load_json(_plan_path(name), None)
    if not isinstance(record, dict) or not isinstance(record.get("plan"), dict):
        raise RehearsalError(f"排练计划不存在: {name}")
    normalized = _normalize_plan(record["plan"])
    plan_sha = _json_sha(normalized)
    return {
        "ok": True,
        "name": name,
        "defined_at": record.get("defined_at"),
        "plan_sha": plan_sha,
        "plan": normalized,
    }


def _check(ok: bool, detail: str, **meta) -> dict:
    return {"ok": bool(ok), "detail": detail, **meta}


def simulate(name: str = "default", plan: dict | None = None) -> dict:
    """静态推演：不启动服务、不写生产，只验证计划与镜像是否闭合。"""
    from . import mirror_space as MS

    name = _canonical_name(name)
    if plan is not None:
        define_plan(name, plan)
    plan_record = get_plan(name)
    normalized = plan_record["plan"]
    tree, dimension_sha = _dimension_state()
    checks = {}

    scan_result = MS.scan()
    checks["dimension_scan"] = _check(
        scan_result.get("ok"),
        f"{scan_result.get('passed')}/{scan_result.get('total')} 镜像体检通过",
        failed=[k for k, value in (scan_result.get("checks") or {}).items()
                if not value.get("ok")],
    )

    # 假设证伪层：可判定的假设必须被实测证实，绝不留在"声明即通过"。
    assumption_rows = _assumption_rows(normalized, tree)
    contradicted = [
        row for row in assumption_rows if row["status"] == "contradicted"
    ]
    unverified = [
        row for row in assumption_rows if row["status"] == "unverified"
    ]
    verified = [
        row for row in assumption_rows if row["status"] == "verified"
    ]
    strict_assumptions = bool(normalized.get("strict_assumptions"))
    assumption_detail = (
        f"假设 {len(assumption_rows)} 条：已验证 {len(verified)}"
        + (f"，被推翻 {len(contradicted)}" if contradicted else "")
        + (f"，待人工验证 {len(unverified)}" if unverified else "")
    )
    if contradicted:
        assumption_detail += "；被推翻: " + ", ".join(
            str(row.get("id")) for row in contradicted[:5])
    checks["assumptions_verified"] = _check(
        not contradicted and not (strict_assumptions and unverified),
        assumption_detail,
        assumptions=assumption_rows,
        contradicted=[row.get("id") for row in contradicted],
        unverified=[row.get("id") for row in unverified],
        strict=strict_assumptions,
    )

    missing_files = []
    for rel in normalized.get("files") or []:
        try:
            path = safe_relative_path(MS._DIM, rel)
        except ValueError:
            missing_files.append(f"{rel} (路径越界)")
            continue
        if not path.exists():
            missing_files.append(rel)
    checks["files_present"] = _check(
        not missing_files,
        "计划引用的镜像文件全部存在" if not missing_files
        else f"缺失或越界: {missing_files[:8]}",
        missing=missing_files[:20],
    )

    entrypoints = normalized["architecture"].get("entrypoints") or []
    missing_entrypoints = [
        rel for rel in entrypoints
        if rel not in tree
    ]
    checks["entrypoints"] = _check(
        bool(entrypoints) and not missing_entrypoints,
        "入口契约完整" if entrypoints and not missing_entrypoints
        else f"入口缺失: {missing_entrypoints}" if entrypoints
        else "未声明 architecture.entrypoints",
        entrypoints=entrypoints,
    )

    try:
        component_waves = _waves(
            normalized["architecture"]["components"], "架构组件")
        step_waves = _waves(normalized["steps"], "部署步骤")
        graph_error = ""
    except RehearsalError as exc:
        component_waves, step_waves, graph_error = [], [], str(exc)
    checks["dependency_graph"] = _check(
        not graph_error,
        graph_error or "架构组件与部署步骤均无环",
        component_waves=component_waves,
        step_waves=step_waves,
    )

    services = normalized.get("services") or []
    ports = [int(svc.get("port") or 0) for svc in services]
    duplicate_ports = sorted({p for p in ports if p and ports.count(p) > 1})
    checks["service_contract"] = _check(
        not duplicate_ports,
        "服务端口唯一且均有验证信号" if not duplicate_ports
        else f"端口冲突: {duplicate_ports}",
        services=len(services),
        ports=[p for p in ports if p],
    )

    environment = normalized["environment"]
    missing_env = [
        key for key in environment.get("required") or []
        if not os.environ.get(key)
    ]
    missing_external_files = [
        key for key in environment.get("required_files") or []
        if not Path(os.path.expanduser(os.path.expandvars(key))).exists()
    ]
    checks["environment_contract"] = _check(
        not missing_env and not missing_external_files,
        "环境变量名与外部路径契约可满足"
        if not missing_env and not missing_external_files
        else f"缺环境变量={missing_env}, 缺路径={missing_external_files}",
        missing_env=missing_env,
        missing_files=missing_external_files,
    )

    acceptance = normalized["rehearsal"].get("acceptance") or []
    static_only = bool(normalized["rehearsal"].get("static_only"))
    checks["closed_loop_defined"] = _check(
        bool(acceptance) or static_only,
        f"验收命令 {len(acceptance)} 条" if acceptance
        else "显式静态产物，无需运行命令" if static_only
        else "未定义验收闭环",
        acceptance=acceptance,
    )
    checks["rollback_defined"] = _check(
        bool(normalized.get("rollback")),
        "回滚策略已声明",
    )

    passed = sum(1 for item in checks.values() if item["ok"])
    result = {
        "ok": passed == len(checks),
        "name": name,
        "passed": passed,
        "total": len(checks),
        "checks": checks,
        "plan_sha": plan_record["plan_sha"],
        "dimension_sha": dimension_sha,
        "files": len(tree),
        "simulated_at": _now(),
    }
    report_dir = _report_dir(name)
    atomic_write_json(report_dir / "simulate-latest.json", result)
    _audit("mirror_simulated", {
        "name": name,
        "ok": result["ok"],
        "passed": passed,
        "total": len(checks),
        "dimension_sha": dimension_sha[:12],
    })
    return result


def _python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _shell_name() -> str:
    raw = os.environ.get("COMSPEC") or os.environ.get("SHELL") or ""
    return Path(raw).name if raw else ""


def _tool_present(value) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    if raw.lower() in ("python", "python3", "py"):
        return bool(sys.executable and Path(sys.executable).exists())
    path = Path(os.path.expanduser(os.path.expandvars(raw)))
    if path.is_absolute():
        return path.exists()
    return bool(shutil.which(raw))


def _tool_name(argv_item) -> str:
    raw = str(argv_item or "").strip()
    if raw.lower() in ("python", "python3", "py"):
        return "python"
    return Path(raw).name


def capture_profile(name: str = "default", plan: dict | None = None) -> dict:
    """捕获当前运行环境契约；只记录存在性/版本，不记录环境变量值。"""
    name = _canonical_name(name)
    if plan is not None:
        define_plan(name, plan)
    plan_record = get_plan(name)
    normalized = plan_record["plan"]
    environment = normalized["environment"]

    dependencies = {}
    for dep in environment.get("dependencies") or []:
        try:
            dependencies[dep] = importlib.metadata.version(dep)
        except importlib.metadata.PackageNotFoundError:
            dependencies[dep] = None
        except Exception:
            dependencies[dep] = None

    tools = set(environment.get("tools") or [])
    for spec in normalized["rehearsal"].get("commands") or []:
        argv = spec.get("argv") or []
        if argv:
            tools.add(_tool_name(argv[0]))

    profile = {
        "captured_at": _now(),
        "platform": sys.platform,
        "os": platform.system().lower(),
        "machine": platform.machine().lower(),
        "python": _python_version(),
        "python_implementation": platform.python_implementation().lower(),
        "python_executable": str(Path(sys.executable).resolve()),
        "python_bits": 64 if sys.maxsize > 2**32 else 32,
        "path_style": "windows" if os.name == "nt" else "posix",
        "shell": _shell_name(),
        "tools": {tool: _tool_present(tool) for tool in sorted(tools)},
        "dependencies": dependencies,
        "env_present": {
            key: bool(os.environ.get(key))
            for key in environment.get("required") or []
        },
        "paths": {
            key: Path(os.path.expanduser(os.path.expandvars(key))).exists()
            for key in environment.get("required_files") or []
        },
        "services": {
            str(svc.get("name")): {
                "port": int(svc.get("port") or 0),
                "signal": bool(
                    svc.get("health_url") or svc.get("heartbeat_file")
                    or str(svc.get("kind") or "").lower() == "windows_service"
                ),
            }
            for svc in normalized.get("services") or []
        },
    }
    record = {
        "ok": True,
        "name": name,
        "profile": profile,
        "profile_sha": _json_sha(profile),
        "note": "只含契约与存在性，不含密钥值",
    }
    atomic_write_json(_profile_path(name), record)
    return record


def _compare_value(blockers: list, field: str, expected, actual,
                   severity="blocker") -> None:
    if expected is None:
        return
    if expected != actual:
        blockers.append({
            "field": field,
            "expected": expected,
            "actual": actual,
            "severity": severity,
        })


def compare_profiles(sandbox: dict, production: dict) -> dict:
    """比较沙盒与生产 profile。只比较生产明确声明的字段。"""
    blockers = []
    warnings = []
    for field in (
        "platform", "os", "machine", "python", "python_implementation",
        "python_executable", "python_bits", "path_style", "shell",
    ):
        _compare_value(
            blockers, field, production.get(field), sandbox.get(field))

    expected_tools = production.get("tools") or {}
    if isinstance(expected_tools, list):
        expected_tools = {key: True for key in expected_tools}
    for key, expected in expected_tools.items():
        actual = bool((sandbox.get("tools") or {}).get(key))
        if isinstance(expected, bool):
            _compare_value(blockers, f"tools.{key}", expected, actual)
        elif expected not in (None, "", "*"):
            blocked = not actual
            if blocked:
                blockers.append({
                    "field": f"tools.{key}",
                    "expected": expected,
                    "actual": None,
                    "severity": "blocker",
                })

    for key, expected in (production.get("dependencies") or {}).items():
        actual = (sandbox.get("dependencies") or {}).get(key)
        if expected in (None, "", "*"):
            if actual is None:
                blockers.append({
                    "field": f"dependencies.{key}",
                    "expected": "installed",
                    "actual": None,
                    "severity": "blocker",
                })
        else:
            _compare_value(
                blockers, f"dependencies.{key}", str(expected), actual)

    for key, expected in (production.get("env_present") or {}).items():
        actual = bool((sandbox.get("env_present") or {}).get(key))
        _compare_value(blockers, f"env_present.{key}", bool(expected), actual)

    for key, expected in (production.get("paths") or {}).items():
        actual = bool((sandbox.get("paths") or {}).get(key))
        if isinstance(expected, dict):
            expected = bool(expected.get("exists", expected))
        _compare_value(blockers, f"paths.{key}", bool(expected), actual)

    expected_services = production.get("services") or {}
    actual_services = sandbox.get("services") or {}
    for key, expected in expected_services.items():
        actual = actual_services.get(key)
        if not isinstance(expected, dict):
            if not actual:
                blockers.append({
                    "field": f"services.{key}",
                    "expected": expected,
                    "actual": None,
                    "severity": "blocker",
                })
            continue
        for sub_key in ("port", "signal"):
            if sub_key in expected:
                _compare_value(
                    blockers,
                    f"services.{key}.{sub_key}",
                    expected.get(sub_key),
                    (actual or {}).get(sub_key),
                )
    return {"ok": not blockers, "blockers": blockers, "warnings": warnings}


def parity(name: str = "default", production: dict | None = None,
           plan: dict | None = None) -> dict:
    """比较镜像沙盒与生产契约；same_host 是显式同机假设，不静默推断。"""
    name = _canonical_name(name)
    if plan is not None:
        define_plan(name, plan)
    plan_record = get_plan(name)
    normalized = plan_record["plan"]
    tree, dimension_sha = _dimension_state()
    sandbox = capture_profile(name)["profile"]
    production_spec = production or normalized["environment"]["production"]
    mode = str(production_spec.get("mode") or "").strip().lower()
    if mode == "same_host":
        # same_host 是显式同机声明；若同时携带显式断言，则逐项与沙盒实测比对，
        # 让"沙盒与生产一致"从口头声明变成可证伪证据。
        declared = {
            key: value for key, value in production_spec.items()
            if key not in ("mode", "profile", "note", "notes", "detail")
        }
        production_profile = copy.deepcopy(sandbox)
        if declared:
            production_profile.update(declared)
            comparison = compare_profiles(sandbox, declared)
            comparison["warnings"].append({
                "field": "production.mode",
                "detail": "same_host 同机声明 + 显式断言；断言已逐项实测比对",
            })
        else:
            comparison = {"ok": True, "blockers": [], "warnings": [{
                "field": "production.mode",
                "detail": (
                    "显式声明沙盒与生产同机同环境（未附显式断言，"
                    "由 gate 在晋升时刻复检环境漂移）；"
                    "非同机部署必须改用 profile"
                ),
            }]}
    else:
        production_profile = production_spec.get("profile") or production_spec
        if not isinstance(production_profile, dict):
            raise RehearsalError("生产 profile 必须是对象")
        comparison = compare_profiles(sandbox, production_profile)

    result = {
        "ok": comparison["ok"],
        "name": name,
        "mode": mode or "explicit_profile",
        "sandbox": sandbox,
        "production": production_profile,
        "blockers": comparison["blockers"],
        "warnings": comparison["warnings"],
        "plan_sha": plan_record["plan_sha"],
        "dimension_sha": dimension_sha,
        "files": len(tree),
        "checked_at": _now(),
    }
    atomic_write_json(_report_dir(name) / "parity-latest.json", result)
    _audit("mirror_parity_checked", {
        "name": name,
        "ok": result["ok"],
        "mode": result["mode"],
        "blockers": len(result["blockers"]),
        "dimension_sha": dimension_sha[:12],
    })
    return result


def _redact_output(value: str) -> str:
    text = str(value or "")
    return re.sub(
        r"(?i)(api[_-]?key|token|passphrase|password|secret)\s*[:=]\s*\S+",
        r"\1=<redacted>", text,
    )


def _tree_changes(before: dict, after: dict) -> list[dict]:
    changes = []
    for key in sorted(set(before) | set(after)):
        old = before.get(key)
        new = after.get(key)
        if old is None:
            changes.append({"file": key, "kind": "added"})
        elif new is None:
            changes.append({"file": key, "kind": "deleted"})
        elif old.get("sha") != new.get("sha"):
            changes.append({"file": key, "kind": "modified"})
    return changes


def _run_command(spec: dict, run_dir: Path, runtime_root: Path,
                 dimension_sha: str, inherited_env_keys=None) -> dict:
    from . import mirror_space as MS

    cmd_id = str(spec.get("id") or "command")
    argv = [str(x) for x in (spec.get("argv") or [])]
    timeout = min(300.0, max(0.1, float(spec.get("timeout", 120) or 120)))
    cwd_raw = str(spec.get("cwd") or "").strip()
    cwd = run_dir if not cwd_raw else safe_relative_path(run_dir, cwd_raw)
    if not cwd.exists() or not cwd.is_dir():
        raise RehearsalError(f"rehearsal command {cmd_id} cwd 不存在: {cwd_raw}")
    if argv and argv[0].lower() in ("python", "python3", "py"):
        argv[0] = sys.executable

    sandbox_store = runtime_root / f"{cmd_id}-{time.time_ns()}" / "store"
    pycache = runtime_root / f"{cmd_id}-{time.time_ns()}" / "pycache"
    sandbox_store.mkdir(parents=True, exist_ok=True)
    pycache.mkdir(parents=True, exist_ok=True)
    keep = (
        "PATH", "Path", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP",
        "USERPROFILE", "HOME", "PATHEXT", "COMSPEC",
    )
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env.update({
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(pycache),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "GBT_REHEARSAL": "1",
        "GBT_REHEARSAL_DIMENSION_SHA": dimension_sha,
        "GBT_STORE_DIR": str(sandbox_store),
    })
    env_keys = list(inherited_env_keys or []) + list(spec.get("env_keys") or [])
    for key in env_keys:
        key = str(key)
        if key in os.environ:
            env[key] = os.environ[key]

    before = MS._tree_fingerprint(run_dir)
    t0 = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW | _CREATE_NEW_PROCESS_GROUP,
        )
        exit_code = int(proc.returncode)
        stdout, stderr = proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = -1
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
    after = MS._tree_fingerprint(run_dir)
    changes = _tree_changes(before, after)
    elapsed_ms = round((time.time() - t0) * 1000, 1)

    expect = spec.get("expect") or {}
    expected_code = int(expect.get("exit_code", 0))
    checks = {
        "exit_code": exit_code == expected_code,
        "not_timed_out": not timed_out,
    }
    if "stdout_contains" in expect:
        checks["stdout_contains"] = str(expect["stdout_contains"]) in stdout
    if "stderr_contains" in expect:
        checks["stderr_contains"] = str(expect["stderr_contains"]) in stderr
    if "stdout_not_contains" in expect:
        checks["stdout_not_contains"] = str(expect["stdout_not_contains"]) not in stdout
    if "stderr_not_contains" in expect:
        checks["stderr_not_contains"] = str(expect["stderr_not_contains"]) not in stderr
    for rel in expect.get("files_exist") or []:
        try:
            exists = safe_relative_path(run_dir, str(rel)).exists()
        except ValueError:
            exists = False
        checks[f"file_exists:{rel}"] = exists

    expected_changes = {
        str(item).replace("\\", "/")
        for item in (spec.get("expected_changes") or [])
    }
    if spec.get("allow_workspace_changes"):
        workspace_ok = True
    else:
        workspace_ok = all(
            change["kind"] != "deleted"
            and change["file"] in expected_changes
            for change in changes
        )
    checks["workspace_isolated"] = workspace_ok
    passed = all(checks.values())
    return {
        "id": cmd_id,
        "ok": passed,
        "passed_checks": checks,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "elapsed_ms": elapsed_ms,
        "stdout": _redact_output(stdout[-4000:]),
        "stderr": _redact_output(stderr[-4000:]),
        "workspace_changes": changes[:40],
    }


def rehearse(name: str = "default", plan: dict | None = None,
             execute: bool = True) -> dict:
    """执行完整生产前排练：计划→推演→环境镜像→沙盒闭环。"""
    name = _canonical_name(name)
    if plan is not None:
        define_plan(name, plan)
    plan_record = get_plan(name)
    normalized = plan_record["plan"]
    tree_before, dimension_before = _dimension_state()
    simulation = simulate(name)
    parity_result = parity(name)
    command_results = []
    gate_blockers = []

    if not simulation.get("ok"):
        gate_blockers.append("静态推演未全绿")
    if not parity_result.get("ok"):
        gate_blockers.append("沙盒与生产环境契约不一致")

    runtime_root = _RUNTIMES / name / str(time.time_ns())
    runtime_root.mkdir(parents=True, exist_ok=True)
    if execute and not gate_blockers:
        from . import mirror_space as MS
        run_dir = Path(MS._DIM)
        for spec in normalized["rehearsal"].get("commands") or []:
            try:
                command_results.append(_run_command(
                    spec, run_dir,
                    runtime_root, dimension_before,
                    inherited_env_keys=normalized["environment"].get("required"),
                ))
            except RehearsalError as exc:
                command_results.append({
                    "id": str(spec.get("id") or "command"),
                    "ok": False,
                    "error": str(exc)[:300],
                })
    elif normalized["rehearsal"].get("static_only") and not execute:
        gate_blockers.append("static_only 计划也需执行静态排练门以生成报告")

    failed_commands = [
        row.get("id") for row in command_results if not row.get("ok")
    ]
    if failed_commands:
        gate_blockers.append(f"闭环命令失败: {failed_commands}")

    acceptance = normalized["rehearsal"].get("acceptance") or []
    passed_commands = {
        row.get("id") for row in command_results if row.get("ok")
    }
    missing_acceptance = [
        item for item in acceptance if item not in passed_commands
    ]
    if missing_acceptance:
        gate_blockers.append(f"未通过验收命令: {missing_acceptance}")

    tree_after, dimension_after = _dimension_state()
    if (dimension_after != dimension_before
            and not normalized.get("allow_rehearsal_artifacts")):
        gate_blockers.append("排练改变了镜像树，报告失效")

    report_id = time.strftime("%Y%m%dT%H%M%S") + f"-{time.time_ns()}"
    result = {
        "ok": not gate_blockers,
        "name": name,
        "report_id": report_id,
        "plan_sha": plan_record["plan_sha"],
        "dimension_sha": dimension_after,
        "dimension_files": len(tree_after),
        "simulation": simulation,
        "parity": parity_result,
        "commands": command_results,
        "acceptance": acceptance,
        "blockers": gate_blockers,
        "rehearsed_at": _now(),
        "law": "镜像排练全绿 + 树/计划指纹绑定；任何变更都会使本次报告失效",
    }
    report_dir = _report_dir(name)
    atomic_write_json(report_dir / f"{report_id}.json", result)
    atomic_write_json(report_dir / "latest.json", result)
    _audit("mirror_rehearsed", {
        "name": name,
        "ok": result["ok"],
        "report_id": report_id,
        "commands": len(command_results),
        "blockers": len(gate_blockers),
        "dimension_sha": dimension_after[:12],
    })
    return result


def gate(name: str = "default") -> dict:
    """生产晋升门：报告/镜像/计划指纹一致，且晋升时刻环境仍与排练一致。"""
    name = _canonical_name(name)
    report_dir = _report_dir(name)
    latest = load_json(report_dir / "latest.json", None)
    blockers = []
    plan_record: dict = {}
    environment = {"ok": True, "checked": False, "drift": []}
    if not isinstance(latest, dict):
        blockers.append("没有排练报告")
    else:
        if not latest.get("ok"):
            blockers.append("最新排练未通过")
        try:
            plan_record = get_plan(name)
        except RehearsalError as exc:
            plan_record = {}
            blockers.append(str(exc))
        _, current_dimension_sha = _dimension_state()
        if latest.get("dimension_sha") != current_dimension_sha:
            blockers.append("镜像树在排练后发生变化，报告已失效")
        if (plan_record.get("plan_sha")
                and latest.get("plan_sha") != plan_record.get("plan_sha")):
            blockers.append("计划在排练后发生变化，报告已失效")

        # 环境一致性复检：排练全绿那一刻的环境必须等于晋升这一刻的环境。
        rehearsed_profile = (latest.get("parity") or {}).get("sandbox")
        if isinstance(rehearsed_profile, dict) and plan_record:
            try:
                current_profile = capture_profile(name)["profile"]
                drift = _profile_drift(rehearsed_profile, current_profile)
                environment = {
                    "ok": not drift,
                    "checked": True,
                    "drift": drift[:10],
                }
                if drift:
                    blockers.append(
                        "生产环境在排练后发生变化: "
                        + ", ".join(str(row["field"]) for row in drift[:6])
                    )
            except Exception as exc:  # noqa: BLE001
                environment = {
                    "ok": False,
                    "checked": False,
                    "error": str(exc)[:200],
                }
                blockers.append(f"晋升前环境复检失败: {str(exc)[:120]}")
    return {
        "ok": not blockers,
        "name": name,
        "blockers": blockers,
        "environment": environment,
        "report": latest,
        "gate_at": _now(),
    }


def baseline_plan(purpose: str = "", files: list[str] | None = None) -> dict:
    """为简单产物生成最小计划；代码文件没有测试时会如实阻断，不伪造闭环。"""
    from . import mirror_space as MS
    tree = MS.dimension_tree().get("stage") or {}
    all_files = sorted(files or tree.keys())
    code_files = [f for f in all_files if Path(f).suffix.lower() in _CODE_SUFFIXES]
    entries = [
        f for f in all_files
        if Path(f).name.lower() in (
            "index.html", "main.py", "app.py", "start.ps1",
            "package.json", "main.js", "app.js",
        )
    ]
    if not entries and all_files:
        entries = [all_files[0]]
    py_tests = [
        f for f in all_files
        if (f.startswith("tests/") or "/tests/" in f)
        and f.endswith(".py")
    ]
    commands = []
    acceptance = []
    static_only = not code_files
    if py_tests:
        # ⚠️ 2026-09-19 修（甲方案 · 门该用**产物自己的测试入口**）：
        # 产物可以在 `tests/` 下自带统一入口 `run_tests.py` —— 它自己知道怎么跑
        # （W3 这个就是：内部调 `node --test` 跑两个 .cjs，退出码 0/1/2 定义清楚，
        #  且它在自己的 docstring 里明写「编程调用 from run_tests import run → 返回 dict
        #  （回归框架可直接接）」——**这个入口本来就是为被门调用而写的**）。
        # 旧写法一律套 `python -m unittest discover`，等于拿 Python 的标准去量 Node 产物：
        # 那个目录既没有 `__init__.py` 也没有 `test_*.py` ⇒ 结构上必挂 ⇒ 门永远关着。
        # 实测：`py -3.10 holo_pet_w3/tests/run_tests.py` → 24 通过 / 0 失败 / exit 0。
        _own = [f for f in all_files
                if Path(f).name == "run_tests.py"
                and (f.startswith("tests/") or "/tests/" in f)]
        if _own:
            commands.append({
                "id": "python-regression",
                # ⚠️ 不要给 cwd：runner 默认就在 run_dir，而 argv 已是相对 run_dir 的路径。
                # 2026-09-19 实测：同时给 cwd 会把相对路径**拼两遍**
                #   → .../holo_pet_w3/tests/holo_pet_w3/tests/run_tests.py（不存在）。
                "argv": [sys.executable, _own[0]],
                "timeout": 180,
                "expect": {"exit_code": 0},
            })
        else:
            # ⚠️ 2026-09-19 修（一道从来没开过的门 · 由排练实测挖出）：
            # 旧写法把 discover 起点**写死成 "tests"**；改用真测试模块所在目录推起点。
            #   `tests/test_x.py`            → -s tests              -t .
            #   `holo_pet_w25/tests/test.py` → -s holo_pet_w25/tests -t holo_pet_w25
            # 不引绝对路径（跨机器迁移会再断）。
            _dirs = sorted({str(Path(f).parent.as_posix()) for f in py_tests})
            _start = os.path.commonpath(_dirs) if len(_dirs) > 1 else _dirs[0]
            _parts = Path(_start).parts
            _top = _parts[0] if len(_parts) > 1 else "."
            commands.append({
                "id": "python-regression",
                "argv": [sys.executable, "-m", "unittest", "discover",
                         "-s", _start, "-t", _top, "-v"],
                "timeout": 180,
                "expect": {"exit_code": 0},
            })
        acceptance = ["python-regression"]
        static_only = False
    return {
        "goal": purpose or "镜像产物一次性晋升生产",
        "assumptions": [{
            "id": "A1",
            "statement": "沙盒与本次生产目标为同一主机、同一运行时",
            "verify": "environment.production.mode=same_host",
        }],
        "architecture": {
            "components": [{
                "id": "artifact",
                "responsibility": "待晋升的完整镜像产物树",
                "depends_on": [],
            }],
            "entrypoints": entries,
            "data_flow": [],
        },
        "steps": [
            {"id": "S1", "action": "固化镜像树指纹", "depends_on": []},
            {"id": "S2", "action": "执行静态推演与沙盒闭环", "depends_on": ["S1"]},
            {"id": "S3", "action": "一次性全量晋升生产", "depends_on": ["S2"]},
        ],
        "services": [],
        "files": all_files,
        "environment": {
            "required": [],
            "dependencies": [],
            "tools": ["python"] if code_files else [],
            "required_files": [],
            "production": {"mode": "same_host"},
        },
        "rehearsal": {
            "commands": commands,
            "acceptance": acceptance,
            "static_only": static_only,
        },
        "rollback": {
            "strategy": "mirror_rewind",
            "note": "回滚到上一时间线，整树一次性替换",
        },
    }


def release(name: str = "default", purpose: str = "",
            plan: dict | None = None,
            owner_override: bool = False, override_reason: str = "") -> dict:
    """排练全绿后一次性晋升生产；任何未过门因素都会阻断。

    🔴 2026-10-13（主人令：「**技术层面不能给她有限制只保留人工授权护栏即可**」·
       「**直接改成终端YES才能使用就好了有时候我需要用到的啊**」）：
      「排练未全绿」**不再是死路**。默认照旧卡住；主人在终端发**专用一次性钥匙**
      `deploy_force`（提示符 YES）+ 调用方显式 `owner_override=true`
      ⇒ 放行并**大声落审计** `mirror_release_overridden`。
      钥匙由**门外那道门**认（`policy.evaluate` 见 `owner_override` 就改要 `deploy_force`）⇒
      旗标不带授权，模型无法自我解锁。
    """
    from . import mirror_space as MS

    if plan is not None:
        define_plan(name, plan)
    rehearsal = rehearse(name)
    if not rehearsal.get("ok"):
        if not owner_override:
            _audit("mirror_release_blocked",
                   {"name": name, "blockers": rehearsal.get("blockers")})
            return {
                "ok": False,
                "blocked": True,
                "name": name,
                "reason": "生产前排练未全绿，禁止晋升",
                "rehearsal": rehearsal,
                "如何放行": ("这不是技术层死限：主人在终端发**专用一次性钥匙** `deploy_force`"
                          "（python -m gbt_allinone auth grant --scope deploy_force --ttl 600，"
                          "提示符敲 YES），再带 owner_override=true 重调即可放行；"
                          "放行会写审计 mirror_release_overridden。"),
            }
        _audit("mirror_release_overridden",
               {"name": name, "blockers": rehearsal.get("blockers"),
                "reason": str(override_reason or purpose or "(未写理由)")[:200]})
    # R-H95 · 实测修（2026-09-19）：本行原为
    #     MS.ascend(purpose, require_rehearsal=True, rehearsal_name=name)
    # 而 `mirror_space.ascend()` 的真身签名是 `ascend(purpose: str = "")`——只有单形参。
    # 于是 `mirror_release` **每次必抛 TypeError**，生产发布这条路**结构上从来没开过**
    # （同族：R113 在 api 层给了同样的绕行说明）。排练门在本函数**上面**已经跑过
    # （`rehearse(name)` 不过就 return blocked），不需要再往唯一写 production 的
    # 函数里塞第二个门 —— 门有两处，就会有一处是坏的。
    promotion = MS.ascend(purpose or f"镜像排练晋升: {name}",
                          owner_override=owner_override,
                          override_reason=override_reason)
    return {
        "ok": bool(promotion.get("ok")),
        "name": name,
        "rehearsal": {
            "report_id": rehearsal.get("report_id"),
            "dimension_sha": rehearsal.get("dimension_sha"),
            "plan_sha": rehearsal.get("plan_sha"),
        },
        "promotion": promotion,
    }


def status(name: str = "default") -> dict:
    name = _canonical_name(name)
    plan_record = load_json(_plan_path(name), None)
    latest = load_json(_report_dir(name) / "latest.json", None)
    return {
        "ok": True,
        "name": name,
        "plan": plan_record,
        "latest_rehearsal": latest,
        "gate": gate(name),
    }
