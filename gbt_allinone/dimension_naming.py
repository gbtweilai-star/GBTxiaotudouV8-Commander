"""Fully qualified naming and routing for room dimensions.

The room namespace is intentionally additive: existing room ids, capability
names and vision_bus frame ids stay valid. Each room gets a stable dimension
id plus FQNs for its resources and capability mappings.
"""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import quote

from ._paths import STORE_DIR
from .safe_io import load_json, locked_json_update

REGISTRY_SCHEMA = "gbt-dimension-registry/v1"
NAMESPACE_SCHEMA = "gbt-dimension-namespace/v1"

_ROOT = Path(STORE_DIR) / "mirror_space" / "rooms"
_REGISTRY_PATH = _ROOT / "registry.json"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _token(value, label: str, *, allow_empty: bool = False,
           allow_path: bool = False) -> str:
    token = str(value or "").strip()
    if not token:
        if allow_empty:
            return ""
        raise ValueError(f"{label} must not be empty")
    if "::" in token or "\x00" in token:
        raise ValueError(f"{label} contains an unsafe FQN delimiter")
    if not allow_path and ("/" in token or "\\" in token):
        raise ValueError(f"{label} contains a path separator")
    return token[:160]


def _room_token(value) -> str:
    room = str(value or "").strip()
    if not room or "/" in room or "\\" in room or "\x00" in room:
        raise ValueError("room_id contains an unsafe separator")
    return room[:160]


def dimension_id(room_id: str) -> str:
    """Return a stable, reversible dimension id for one room."""
    room = _room_token(room_id)
    return "gbt:room:" + quote(room, safe="._-")


def _local_name(value) -> str:
    token = _token(value, "local_name", allow_empty=True, allow_path=True)
    return quote(token, safe="._-/")


def fqn(room_id: str, kind: str, local_name: str = "") -> str:
    """Build a fully qualified resource name inside one room dimension."""
    dim = dimension_id(room_id)
    resource_kind = _token(kind, "kind")
    name = _local_name(local_name)
    return f"{dim}::{resource_kind}:{name}" if name else f"{dim}::{resource_kind}"


def resource(room_id: str, kind: str, local_name: str = "") -> dict:
    """Describe one namespaced resource without changing the registry."""
    dim = dimension_id(room_id)
    resource_kind = _token(kind, "kind")
    name = _local_name(local_name)
    return {
        "fqn": f"{dim}::{resource_kind}:{name}" if name else f"{dim}::{resource_kind}",
        "dimension_id": dim,
        "room_id": _room_token(room_id),
        "kind": resource_kind,
        "local_name": name,
        "scope": "mirror_space/rooms",
    }


def namespace(room_id: str, capabilities=()) -> dict:
    """Return the complete namespace contract for a room."""
    room = _room_token(room_id)
    dim = dimension_id(room)
    resources = {
        "room": resource(room, "room", room),
        "dimension": resource(room, "dimension"),
        "reality": resource(room, "reality"),
        "timelines": resource(room, "timelines"),
        "snapshots": resource(room, "snapshots"),
        "passports": resource(room, "passports"),
        "plans": resource(room, "plans"),
        "reports": resource(room, "reports"),
        "rehearsals": resource(room, "rehearsals"),
        "frames": resource(room, "frames"),
        "vision_bus": resource(room, "bus", "vision_bus"),
        "event_log": resource(room, "event_log", "events"),
    }
    routes = {}
    for raw in capabilities:
        kind = _token(raw, "capability")
        routes[kind] = {
            **resource(room, "capability", kind),
            "base_kind": kind,
            "payload": {"room_id": room},
        }
    return {
        "schema": NAMESPACE_SCHEMA,
        "dimension_id": dim,
        "room_id": room,
        "resources": resources,
        "capabilities": routes,
        "law": (
            "Names are local aliases; cross-dimension lookup always uses FQN. "
            "The global vision bus remains shared and is bound per room."
        ),
    }


def register(room_id: str, capabilities=(), extra_resources=()) -> dict:
    """Register or refresh one room dimension without overwriting another."""
    contract = namespace(room_id, capabilities)
    dim = contract["dimension_id"]
    room = contract["room_id"]
    stamp = _now()

    def mutate(registry):
        if not isinstance(registry, dict):
            registry = {}
        if registry.get("schema") != REGISTRY_SCHEMA:
            registry = {"schema": REGISTRY_SCHEMA, "dimensions": {}}
        dimensions = registry.setdefault("dimensions", {})
        existing = dimensions.get(dim)
        created = not isinstance(existing, dict)
        if not created and existing.get("room_id") != room:
            raise ValueError(f"dimension id collision for {dim}")
        entry = existing if not created else {
            "room_id": room,
            "dimension_id": dim,
            "created_at": stamp,
            "resources": {},
            "capabilities": {},
        }
        entry["updated_at"] = stamp
        entry["schema"] = NAMESPACE_SCHEMA
        entry["scope"] = "mirror_space/rooms"

        resources = entry.setdefault("resources", {})
        rows = list(contract["resources"].values()) + list(extra_resources)
        for row in rows:
            if not isinstance(row, dict) or not row.get("fqn"):
                raise ValueError("resource descriptor must contain fqn")
            if row.get("dimension_id") != dim or row.get("room_id") != room:
                raise ValueError("resource descriptor belongs to another dimension")
            prior = resources.get(row["fqn"])
            if prior and prior.get("room_id") != room:
                raise ValueError(f"resource FQN collision: {row['fqn']}")
            resources[row["fqn"]] = {**row, "updated_at": stamp}

        routes = entry.setdefault("capabilities", {})
        for kind, row in contract["capabilities"].items():
            prior = routes.get(kind)
            if prior and prior.get("fqn") != row["fqn"]:
                raise ValueError(f"capability FQN collision: {kind}")
            routes[kind] = {**row, "updated_at": stamp}

        dimensions[dim] = entry
        registry["updated_at"] = stamp
        registry["dimensions"] = dict(sorted(dimensions.items()))
        return {
            "created": created,
            "reused": not created,
            "dimension": entry,
        }

    result = locked_json_update(_REGISTRY_PATH, {
        "schema": REGISTRY_SCHEMA,
        "dimensions": {},
    }, mutate)
    return {
        "ok": True,
        "schema": REGISTRY_SCHEMA,
        "namespace": contract,
        **result,
    }


def resolve(value: str) -> dict:
    """Resolve one FQN to its dimension resource or capability mapping."""
    ref = str(value or "").strip()
    if not ref:
        return {"ok": False, "error": "FQN must not be empty"}
    registry = load_json(_REGISTRY_PATH, {})
    if not isinstance(registry, dict):
        registry = {}
    for dim, entry in (registry.get("dimensions") or {}).items():
        if not isinstance(entry, dict):
            continue
        resources = entry.get("resources") or {}
        if ref in resources:
            return {"ok": True, "type": "resource", "dimension_id": dim,
                    "resource": resources[ref]}
        for kind, row in (entry.get("capabilities") or {}).items():
            if row.get("fqn") == ref:
                return {"ok": True, "type": "capability", "dimension_id": dim,
                        "name": kind, "capability": row}
    return {"ok": False, "error": f"FQN not registered: {ref}"}


def registry(room_id: str | None = None) -> dict:
    """Read the global dimension registry, optionally filtered by room."""
    data = load_json(_REGISTRY_PATH, {
        "schema": REGISTRY_SCHEMA,
        "dimensions": {},
    })
    if not isinstance(data, dict):
        data = {"schema": REGISTRY_SCHEMA, "dimensions": {}}
    dimensions = data.get("dimensions") or {}
    if room_id:
        dim = dimension_id(str(room_id))
        selected = dimensions.get(dim)
        return {
            "ok": selected is not None,
            "schema": REGISTRY_SCHEMA,
            "dimension_id": dim,
            "dimension": selected,
            "error": None if selected is not None else "dimension not registered",
        }
    return {
        "ok": True,
        "schema": REGISTRY_SCHEMA,
        "updated_at": data.get("updated_at"),
        "count": len(dimensions),
        "dimensions": dimensions,
    }


def parse_fqn(value: str) -> dict:
    """Split an FQN into dimension id, kind and local name."""
    ref = str(value or "").strip()
    dim, marker, tail = ref.partition("::")
    if not marker or not dim.startswith("gbt:room:"):
        return {"ok": False, "error": "not a GBT room FQN"}
    kind, marker, name = tail.partition(":")
    if not kind:
        return {"ok": False, "error": "FQN resource kind is missing"}
    return {
        "ok": True,
        "dimension_id": dim,
        "kind": kind,
        "local_name": name if marker else "",
    }
