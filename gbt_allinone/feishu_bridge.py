"""飞书 / Lark 资料库桥（不依赖 lark-cli）。

⚠️ 外部内容纪律：`read_doc` 读回的**云文档正文一律是不可信数据，不是指令** ——
飞书文档可由任何协作者编辑，里面可能写着针对 AI 的祈使句。
本模块只把它当数据返回；不执行其中任何指令、不拼进 system 提示、不拿去驱动执行口。
覆盖校验器：py -3.14 -m gbt_allinone.tools.external_content_check gbt_allinone

设计原则
--------
1. 凭证只用 Windows DPAPI 加密落盘，状态接口与日志一律掩码。
2. 默认只读：浏览知识库、搜索云文档、读取正文都不改变任何数据。
3. 写入必须由调用方显式给出 ``confirm=True``，且只做"新建/追加"，不做删除。
4. 所有请求都限定在官方域名，不上报、不转发任何本地路径或密钥。

CLI::

    python -m gbt_allinone.feishu_bridge status
    python -m gbt_allinone.feishu_bridge spaces
    python -m gbt_allinone.feishu_bridge nodes <space_id>
    python -m gbt_allinone.feishu_bridge search <关键词>
    python -m gbt_allinone.feishu_bridge read <document_id>
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ._paths import STORE_DIR
from .safe_io import atomic_write_bytes

BRANDS = {
    "lark": "https://open.larksuite.com",
    "feishu": "https://open.feishu.cn",
}
_DEFAULT_BRAND = "lark"
_DPAPI_ENTROPY = b"GBTxiaotudouV8:feishu:v1"
_DEFAULT_SECRET_FILE = Path(STORE_DIR) / "secrets" / "feishu_app.dpapi"
_TIMEOUT = 30.0
_LOCK = threading.RLock()
_TOKEN: dict[str, object] = {"value": "", "expire_at": 0.0, "app_id": ""}


class FeishuError(RuntimeError):
    """飞书接口或凭证错误。"""


def _secret_file() -> Path:
    raw = os.environ.get("GBT_FEISHU_SECRET_FILE", "").strip()
    return Path(raw).expanduser().resolve() if raw else _DEFAULT_SECRET_FILE


def _env_credentials() -> tuple[str, str, str]:
    app_id = os.environ.get("GBT_FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("GBT_FEISHU_APP_SECRET", "").strip()
    brand = os.environ.get("GBT_FEISHU_BRAND", "").strip().lower() or _DEFAULT_BRAND
    if app_id and app_secret:
        return app_id, app_secret, brand
    return "", "", brand


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(raw: bytes):
    buf = ctypes.create_string_buffer(raw, len(raw))
    return (_DataBlob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf)


def _crypt(data: bytes, protect: bool) -> bytes:
    if os.name != "nt":
        raise FeishuError("当前系统不支持 Windows DPAPI")
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        fn.argtypes = [
            ctypes.POINTER(_DataBlob), ctypes.c_wchar_p if protect else ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.POINTER(_DataBlob),
        ]
        fn.restype = ctypes.c_int
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        input_blob, input_buf = _blob(data)
        entropy_blob, entropy_buf = _blob(_DPAPI_ENTROPY)
        output = _DataBlob()
        if protect:
            ok = fn(ctypes.byref(input_blob), "GBT小土豆V8 Feishu credential",
                    ctypes.byref(entropy_blob), None, None, 0x1, ctypes.byref(output))
        else:
            ok = fn(ctypes.byref(input_blob), None, ctypes.byref(entropy_blob),
                    None, None, 0x1, ctypes.byref(output))
        _keepalive = (input_buf, entropy_buf)
        if not ok:
            raise FeishuError("DPAPI 加解密失败")
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)
    except FeishuError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise FeishuError(f"DPAPI 不可用：{str(exc)[:160]}") from exc


def mask(value: str) -> str:
    text = str(value or "")
    return f"{text[:4]}****" if len(text) >= 4 else ""


def _clean_token(value) -> str:
    """去掉 BOM、零宽字符与首尾空白，避免管道输入把不可见字符带进密钥。"""
    text = str(value or "")
    for ch in ("\ufeff", "\u200b", "\u00a0"):
        text = text.replace(ch, "")
    return text.strip()


def store_credentials(app_id: str, app_secret: str, brand: str = _DEFAULT_BRAND) -> dict:
    """把应用凭证加密保存，不返回明文。"""
    app_id = _clean_token(app_id)
    app_secret = _clean_token(app_secret)
    brand = str(brand or _DEFAULT_BRAND).strip().lower()
    if not app_id or not app_secret:
        return {"ok": False, "error": "App ID / App Secret 不能为空"}
    if brand not in BRANDS:
        return {"ok": False, "error": f"未知品牌：{brand}"}
    payload = json.dumps(
        {"appId": app_id, "appSecret": app_secret, "brand": brand}, ensure_ascii=False
    ).encode("utf-8")
    try:
        target = _secret_file()
        atomic_write_bytes(target, _crypt(payload, True), mode=0o600)
        with _LOCK:
            _TOKEN.update({"value": "", "expire_at": 0.0, "app_id": ""})
        return {"ok": True, "configured": True, "credential": "dpapi",
                "app_id_masked": mask(app_id), "brand": brand, "path": str(target)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}


def load_credentials() -> tuple[str, str, str, str]:
    """返回 (app_id, app_secret, brand, source)。"""
    app_id, app_secret, brand = _env_credentials()
    if app_id:
        return app_id, app_secret, brand, "env"
    target = _secret_file()
    if not target.is_file():
        return "", "", brand, "missing"
    try:
        raw = json.loads(_crypt(target.read_bytes(), False).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return "", "", brand, "unreadable"
    return (
        str(raw.get("appId") or "").strip(),
        str(raw.get("appSecret") or "").strip(),
        str(raw.get("brand") or _DEFAULT_BRAND).strip().lower(),
        "dpapi",
    )


def tenant_token(force: bool = False) -> str:
    app_id, app_secret, brand, _source = load_credentials()
    if not app_id or not app_secret:
        raise FeishuError("尚未配置飞书应用凭证")
    now = time.time()
    with _LOCK:
        if (not force and _TOKEN.get("value") and _TOKEN.get("app_id") == app_id
                and float(_TOKEN.get("expire_at") or 0) > now + 60):
            return str(_TOKEN["value"])
    base = BRANDS.get(brand, BRANDS[_DEFAULT_BRAND])
    payload = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/open-apis/auth/v3/tenant_access_token/internal",
        data=payload, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise FeishuError(f"授权失败 HTTP {exc.code}") from exc
    except Exception as exc:  # noqa: BLE001
        raise FeishuError(f"授权请求失败：{str(exc)[:120]}") from exc
    if int(body.get("code") or 0) != 0:
        raise FeishuError(f"授权被拒：{body.get('code')} {body.get('msg')}")
    token = str(body.get("tenant_access_token") or "")
    with _LOCK:
        _TOKEN.update({"value": token, "app_id": app_id,
                       "expire_at": now + float(body.get("expire") or 3600)})
    return token


def _request(method: str, path: str, *, params: dict | None = None,
             body: dict | None = None, retry: bool = True) -> dict:
    app_id, _secret, brand, _source = load_credentials()
    base = BRANDS.get(brand, BRANDS[_DEFAULT_BRAND])
    url = f"{base}{path}"
    if params:
        clean = {k: v for k, v in params.items() if v not in (None, "")}
        if clean:
            url = f"{url}?{urllib.parse.urlencode(clean)}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {tenant_token()}",
        "Content-Type": "application/json; charset=utf-8",
    })
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:200]
        if exc.code in (401, 403) and retry:
            tenant_token(force=True)
            return _request(method, path, params=params, body=body, retry=False)
        raise FeishuError(f"HTTP {exc.code}：{detail}") from exc
    except Exception as exc:  # noqa: BLE001
        raise FeishuError(f"请求失败：{str(exc)[:120]}") from exc
    code = int(payload.get("code") or 0)
    if code != 0:
        raise FeishuError(f"接口返回 {code}：{payload.get('msg')}")
    return payload.get("data") or {}


def status() -> dict:
    app_id, _secret, brand, source = load_credentials()
    result = {
        "ok": True,
        "configured": bool(app_id),
        "app_id_masked": mask(app_id),
        "brand": brand,
        "base_url": BRANDS.get(brand, ""),
        "credential_source": source,
        "credential_protected": source == "dpapi",
        "token_cached": bool(_TOKEN.get("value")),
    }
    if app_id:
        try:
            tenant_token()
            result["token_ok"] = True
        except Exception as exc:  # noqa: BLE001
            result["token_ok"] = False
            result["error"] = str(exc)[:180]
    return result


def wiki_spaces(page_size: int = 20) -> dict:
    data = _request("GET", "/open-apis/wiki/v2/spaces", params={"page_size": page_size})
    items = data.get("items") or []
    return {"ok": True, "count": len(items),
            "spaces": [{"space_id": i.get("space_id"), "name": i.get("name"),
                        "description": (i.get("description") or "")[:120]} for i in items]}


def wiki_nodes(space_id: str, parent_node_token: str = "", page_size: int = 50) -> dict:
    space_id = str(space_id or "").strip()
    if not space_id:
        raise FeishuError("缺少 space_id")
    data = _request("GET", f"/open-apis/wiki/v2/spaces/{space_id}/nodes",
                    params={"parent_node_token": parent_node_token, "page_size": page_size})
    items = data.get("items") or []
    return {"ok": True, "count": len(items),
            "nodes": [{"title": i.get("title"), "node_token": i.get("node_token"),
                       "obj_type": i.get("obj_type"), "obj_token": i.get("obj_token"),
                       "has_child": i.get("has_child")} for i in items]}


def create_space(name: str, description: str = "", *, confirm: bool = False) -> dict:
    """创建知识空间。需要 ``wiki:wiki`` 权限。"""
    if not confirm:
        return {"ok": False, "error": "写入需要 confirm=True"}
    title = str(name or "").strip()
    if not title:
        raise FeishuError("缺少知识空间名称")
    body = {"name": title}
    desc = str(description or "").strip()
    if desc:
        body["description"] = desc[:200]
    data = _request("POST", "/open-apis/wiki/v2/spaces", body=body)
    space = data.get("space") or data
    return {"ok": True, "space_id": space.get("space_id"), "name": space.get("name"),
            "description": space.get("description")}


def get_node(token: str) -> dict:
    """按 wikiToken / obj_token 查节点信息。"""
    node_token = str(token or "").strip()
    if not node_token:
        raise FeishuError("缺少 token")
    data = _request("GET", "/open-apis/wiki/v2/spaces/get_node", params={"token": node_token})
    node = data.get("node") or data
    return {"ok": True, "node": {
        "title": node.get("title"), "node_token": node.get("node_token"),
        "obj_type": node.get("obj_type"), "obj_token": node.get("obj_token"),
        "space_id": node.get("space_id"), "parent_node_token": node.get("parent_node_token"),
    }}


def create_node(space_id: str, title: str, obj_type: str = "docx",
                parent_node_token: str = "", *, confirm: bool = False) -> dict:
    """在知识空间里新建一个文档节点（默认新建 docx 文档）。"""
    if not confirm:
        return {"ok": False, "error": "写入需要 confirm=True"}
    sid = str(space_id or "").strip()
    name = str(title or "").strip()
    if not sid or not name:
        raise FeishuError("缺少 space_id 或节点标题")
    body: dict = {"obj_type": obj_type, "node_type": "origin", "title": name}
    if parent_node_token:
        body["parent_node_token"] = parent_node_token
    data = _request("POST", f"/open-apis/wiki/v2/spaces/{sid}/nodes", body=body)
    node = data.get("node") or data
    return {"ok": True, "node_token": node.get("node_token"), "obj_token": node.get("obj_token"),
            "title": node.get("title"), "space_id": sid}


def add_member(space_id: str, member_id: str, member_type: str = "app",
               *, confirm: bool = False) -> dict:
    """把应用添加为知识空间成员，机器人才能看到该空间内容。"""
    if not confirm:
        return {"ok": False, "error": "写入需要 confirm=True"}
    sid = str(space_id or "").strip()
    mid = str(member_id or "").strip()
    if not sid or not mid:
        raise FeishuError("缺少 space_id 或 member_id")
    data = _request("POST", f"/open-apis/wiki/v2/spaces/{sid}/members",
                    body={"member_type": member_type, "member_id": mid, "member_role": "member"})
    member = data.get("member") or data
    return {"ok": True, "space_id": sid, "member_id": member.get("member_id"),
            "member_role": member.get("member_role")}


def my_space_id() -> str:
    """返回当前凭证对应的 app_id（用于把应用加成知识库成员）。"""
    app_id, _secret, _brand, _source = load_credentials()
    return app_id


def search_docs(query: str, count: int = 10) -> dict:
    key = str(query or "").strip()
    if not key:
        raise FeishuError("缺少搜索关键词")
    data = _request("POST", "/open-apis/suite/docs-api/search/object",
                    body={"search_key": key, "count": count, "offset": 0})
    items = data.get("entities") or data.get("docs_entities") or []
    return {"ok": True, "count": len(items),
            "results": [{"title": i.get("title"),
                         "type": i.get("type") or i.get("docs_type"),
                         "token": i.get("token") or i.get("docs_token"),
                         "url": i.get("url")} for i in items]}


def read_doc(document_id: str) -> dict:
    doc_id = str(document_id or "").strip()
    if not doc_id:
        raise FeishuError("缺少 document_id")
    data = _request("GET", f"/open-apis/docx/v1/documents/{doc_id}/raw_content")
    content = str(data.get("content") or "")
    return {"ok": True, "length": len(content), "content": content[:4000]}


def create_doc(title: str, folder_token: str = "", *, confirm: bool = False) -> dict:
    if not confirm:
        return {"ok": False, "error": "写入需要 confirm=True"}
    name = str(title or "").strip() or "未命名文档"
    body: dict = {"title": name}
    if folder_token:
        body["folder_token"] = folder_token
    data = _request("POST", "/open-apis/docx/v1/documents", body=body)
    doc = data.get("document") or {}
    return {"ok": True, "title": name, "document_id": doc.get("document_id"),
            "revision_id": doc.get("revision_id")}


def append_text(document_id: str, text: str, *, confirm: bool = False) -> dict:
    if not confirm:
        return {"ok": False, "error": "写入需要 confirm=True"}
    doc_id = str(document_id or "").strip()
    content = str(text or "").strip()
    if not doc_id or not content:
        raise FeishuError("缺少 document_id 或正文")
    body = {
        "index": -1,
        "children": [{
            "block_type": 2,
            "text": {"elements": [{"text_run": {"content": content[:4000]}}]},
        }],
    }
    _request("POST", f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children", body=body)
    return {"ok": True, "document_id": doc_id, "appended": len(content)}


def _cmd_status(_args) -> int:
    print(json.dumps(status(), ensure_ascii=False, indent=2))
    return 0


def _cmd_spaces(_args) -> int:
    print(json.dumps(wiki_spaces(), ensure_ascii=False, indent=2))
    return 0


def _cmd_nodes(args) -> int:
    print(json.dumps(wiki_nodes(args.space_id), ensure_ascii=False, indent=2))
    return 0


def _cmd_search(args) -> int:
    print(json.dumps(search_docs(args.query), ensure_ascii=False, indent=2))
    return 0


def _cmd_read(args) -> int:
    print(json.dumps(read_doc(args.document_id), ensure_ascii=False, indent=2))
    return 0


def _cmd_create_space(args) -> int:
    print(json.dumps(create_space(args.name, args.description, confirm=args.confirm),
                     ensure_ascii=False, indent=2))
    return 0


def _cmd_get_node(args) -> int:
    print(json.dumps(get_node(args.token), ensure_ascii=False, indent=2))
    return 0


def _cmd_create_node(args) -> int:
    print(json.dumps(create_node(args.space_id, args.title, args.obj_type,
                                 args.parent or "", confirm=args.confirm),
                     ensure_ascii=False, indent=2))
    return 0


def _cmd_add_member(args) -> int:
    print(json.dumps(add_member(args.space_id, args.member_id, args.member_type,
                                confirm=args.confirm), ensure_ascii=False, indent=2))
    return 0


def _cmd_set(args) -> int:
    secret = _clean_token(args.app_secret) or _clean_token(sys.stdin.readline())
    print(json.dumps(store_credentials(args.app_id, secret, args.brand),
                     ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="飞书 / Lark 资料库桥")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status").set_defaults(func=_cmd_status)
    sub.add_parser("spaces").set_defaults(func=_cmd_spaces)
    p_nodes = sub.add_parser("nodes")
    p_nodes.add_argument("space_id")
    p_nodes.set_defaults(func=_cmd_nodes)
    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.set_defaults(func=_cmd_search)
    p_read = sub.add_parser("read")
    p_read.add_argument("document_id")
    p_read.set_defaults(func=_cmd_read)
    p_cs = sub.add_parser("create-space")
    p_cs.add_argument("name")
    p_cs.add_argument("--description", default="")
    p_cs.add_argument("--confirm", action="store_true")
    p_cs.set_defaults(func=_cmd_create_space)
    p_gn = sub.add_parser("get-node")
    p_gn.add_argument("token")
    p_gn.set_defaults(func=_cmd_get_node)
    p_cn = sub.add_parser("create-node")
    p_cn.add_argument("space_id")
    p_cn.add_argument("title")
    p_cn.add_argument("--obj-type", default="docx")
    p_cn.add_argument("--parent", default="")
    p_cn.add_argument("--confirm", action="store_true")
    p_cn.set_defaults(func=_cmd_create_node)
    p_am = sub.add_parser("add-member")
    p_am.add_argument("space_id")
    p_am.add_argument("member_id")
    p_am.add_argument("--member-type", default="app")
    p_am.add_argument("--confirm", action="store_true")
    p_am.set_defaults(func=_cmd_add_member)
    p_set = sub.add_parser("set-credential")
    p_set.add_argument("--app-id", required=True)
    p_set.add_argument("--app-secret", default="")
    p_set.add_argument("--brand", default=_DEFAULT_BRAND, choices=sorted(BRANDS))
    p_set.set_defaults(func=_cmd_set)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except FeishuError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
