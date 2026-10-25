# -*- coding: utf-8 -*-
"""gbt_allinone.deploy.selfcheck_configs — 用标准库校验部署配置(本机无 PyYAML 也能跑)。

校验: docker-compose.yml(YAML 子集解析)、Dockerfile、Caddyfile、gbt-wallet.service、
env.example(占位符与"不含真实密钥"断言)、以及 gbt_wallet/api.py 的最小接入痕迹。

用法:  python gbt_allinone/deploy/selfcheck_configs.py
退出码: 0=全部通过; 1=存在失败项
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FAILS = []
OKS = []


def check(name, cond, detail=""):
    if cond:
        OKS.append(name)
        print(f"[OK]   {name}" + (f" — {detail}" if detail else ""))
    else:
        FAILS.append(name + (f" — {detail}" if detail else ""))
        print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


# --------------------------------------------------------------------------
# 极简 YAML 子集解析: 只支持本仓库 compose 用到的语法(缩进映射/列表/行内列表/标量)
# 不引入第三方依赖(PyYAML 不在 requirements.txt 内); 复杂 YAML 请用真解析器。
# --------------------------------------------------------------------------
def _scalar(v: str):
    v = v.strip()
    if v == "":
        return None
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in inner.split(",")] if inner else []
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def _strip_comment(line: str) -> str:
    """去掉整行/行内注释(YAML: ' #' 才算行内注释), 引号内的 '#' 保留。"""
    if line.lstrip().startswith("#"):
        return ""
    inq = None
    for i, ch in enumerate(line):
        if inq:
            if ch == inq:
                inq = None
            continue
        if ch in "\"'":
            inq = ch
        elif ch == "#" and i > 0 and line[i - 1] in " \t":
            return line[:i]
    return line


def _split_kv(s: str):
    """按 YAML 规则找 key: value 的分隔冒号(必须后跟空格或行尾), 跳过引号/括号内的冒号。"""
    inq = None
    depth = 0
    for i, ch in enumerate(s):
        if inq:
            if ch == inq:
                inq = None
            continue
        if ch in "\"'":
            inq = ch
            continue
        if ch in "[{":
            depth += 1
            continue
        if ch in "]}":
            depth -= 1
            continue
        if ch == ":" and depth == 0 and (i + 1 == len(s) or s[i + 1] in " \t"):
            return s[:i], s[i + 1:]
    return None, None


def parse_yaml_subset(text: str):
    """返回嵌套 dict/list; 仅支持: k: v, k:, '- item', '- k: v', 行内 [..], 行内 # 注释。"""
    lines = []
    for raw in text.splitlines():
        s = _strip_comment(raw).rstrip()
        if not s.strip():
            continue
        lines.append((len(s) - len(s.lstrip(" ")), s.strip()))
    root: dict = {}
    stack = [(-1, root, None)]

    for idx, (indent, content) in enumerate(lines):
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        node = stack[-1][1]
        if content.startswith("- ") or content == "-":
            item = content[2:].strip() if content.startswith("- ") else ""
            if not isinstance(node, list):
                raise ValueError(f"列表项出现在非列表上下文: {content!r}")
            k, v = _split_kv(item) if item and item[0] not in "\"'" else (None, None)
            if k is not None and v is not None:
                d = {k.strip(): _scalar(v)}
                node.append(d)
                stack.append((indent, d, None))
            else:
                node.append(_scalar(item))
            continue
        key, val = _split_kv(content)
        if key is None:
            raise ValueError(f"无法解析的行: {content!r}")
        key = key.strip()
        val = (val or "").strip()
        if val == "":
            nxt = lines[idx + 1] if idx + 1 < len(lines) else None
            child = [] if (nxt and nxt[1].startswith("- ")) else {}
            node[key] = child
            stack.append((indent, child, key))
        else:
            node[key] = _scalar(val)
    return root


# --------------------------------------------------------------------------
def main() -> int:
    # ---------- docker-compose.yml ----------
    compose_path = os.path.join(HERE, "docker-compose.yml")
    compose = parse_yaml_subset(read(compose_path))
    check("compose 可被标准库解析(YAML 子集)", isinstance(compose, dict) and "services" in compose)
    svc = (compose.get("services") or {}).get("gbt-wallet") or {}
    check("compose: 定义了服务 gbt-wallet", bool(svc))
    build = svc.get("build") or {}
    ctx = build.get("context")
    check("compose: build.context 指向仓库根", ctx == "../..", f"context={ctx!r}")
    df_rel = build.get("dockerfile") or ""
    # Docker Compose 的 dockerfile 是相对 **构建上下文** 解析的(不是相对 compose 文件);
    # 兼容旧行为: 两处都试。
    ctx_dir = os.path.normpath(os.path.join(HERE, ctx or "."))
    df_path = os.path.join(ctx_dir, df_rel)
    df_alt = os.path.join(HERE, df_rel)
    check("compose: dockerfile 相对构建上下文存在",
          os.path.isfile(df_path) or os.path.isfile(df_alt), f"{df_rel} @ {ctx}")
    check("compose: 构建上下文存在", os.path.isdir(ctx_dir), str(ctx_dir))
    ports = svc.get("ports") or []
    check("compose: 端口只发布到宿主回环", ports == ["127.0.0.1:8097:8097"], f"ports={ports}")
    vols = svc.get("volumes") or []
    check("compose: 数据卷挂到 /data", any(str(v).endswith(":/data") for v in vols), f"volumes={vols}")
    check("compose: 声明命名卷 wallet-data", "wallet-data" in (compose.get("volumes") or {}))
    check("compose: 根文件系统只读", svc.get("read_only") is True, f"read_only={svc.get('read_only')!r}")
    check("compose: 丢弃全部 capability", svc.get("cap_drop") == ["ALL"], f"cap_drop={svc.get('cap_drop')}")
    check("compose: no-new-privileges", any("no-new-privileges" in str(x) for x in (svc.get("security_opt") or [])))
    env = svc.get("environment") or {}
    check("compose: 容器内数据根=/data", env.get("GBT_WALLET_DIR") == "/data", f"env={env}")
    hc = (svc.get("healthcheck") or {}).get("test")
    check("compose: 定义 healthcheck", bool(hc), f"test={str(hc)[:60]}…")
    check("compose: env_file 指向 .env", svc.get("env_file") == [".env"], f"env_file={svc.get('env_file')}")
    # 只断言"没有赋值语句", 允许出现变量名(如 healthcheck 里读取 GBT_WALLET_API_TOKEN)
    check("compose: 未写入口令/令牌赋值",
          re.search(r"GBT_WALLET_(PASS|API_TOKEN)\s*[:=]", read(compose_path)) is None)

    # ---------- Dockerfile ----------
    dockerfile = read(os.path.join(HERE, "Dockerfile"))
    dfl = [l.strip() for l in dockerfile.splitlines() if l.strip() and not l.strip().startswith("#")]
    check("Dockerfile: 基于官方 python 镜像", any(l.startswith("FROM python:") for l in dfl),
          next((l for l in dfl if l.startswith("FROM")), ""))
    check("Dockerfile: pip install requirements", "pip install" in dockerfile and "requirements.txt" in dockerfile)
    req_path = os.path.join(ROOT, "gbt_allinone", "requirements.txt")
    check("Dockerfile: requirements.txt 实际存在", os.path.isfile(req_path))
    for pkg in ("gbt_wallet", "gbt_allinone"):
        check(f"Dockerfile: COPY {pkg}/ 且源目录存在",
              re.search(rf"^COPY\s+{pkg}\s", dockerfile, re.M) is not None and os.path.isdir(os.path.join(ROOT, pkg)))
    check("Dockerfile: EXPOSE 8097", "EXPOSE 8097" in dockerfile)
    check("Dockerfile: 非 root 用户", re.search(r"^USER\s+(?!root)\S+", dockerfile, re.M) is not None,
          (re.search(r"^USER\s+\S+", dockerfile, re.M) or [""])[0] if re.search(r"^USER\s+\S+", dockerfile, re.M) else "")
    check("Dockerfile: 声明 VOLUME /data", "VOLUME" in dockerfile and "/data" in dockerfile)
    check("Dockerfile: 定义 HEALTHCHECK", "HEALTHCHECK" in dockerfile)
    check("Dockerfile: 定义 CMD", re.search(r"^CMD\s", dockerfile, re.M) is not None)
    check("Dockerfile: 不写入口令/令牌赋值",
          re.search(r"GBT_WALLET_(PASS|API_TOKEN)\s*=", dockerfile) is None)

    # ---------- Caddyfile ----------
    caddy = read(os.path.join(HERE, "Caddyfile"))
    check("Caddyfile: 反代到 127.0.0.1:8097",
          re.search(r"reverse_proxy\s+/api/gbtwallet/\*\s+127\.0\.0\.1:8097", caddy) is not None)
    check("Caddyfile: 上游不含 0.0.0.0/公网地址", "0.0.0.0" not in caddy)
    check("Caddyfile: 内部路由边缘 403", "respond @internal" in caddy and "403" in caddy)
    for p in ("/api/gbtwallet/ops/*", "/api/gbtwallet/engine/*", "/api/gbtwallet/monitor",
              "/api/gbtwallet/orders/*/internal"):
        check(f"Caddyfile: 拦截内部路径 {p}", p in caddy)

    # ---------- systemd 单元 ----------
    unit = read(os.path.join(HERE, "gbt-wallet.service"))
    for sec in ("[Unit]", "[Service]", "[Install]"):
        check(f"systemd: 含 {sec}", sec in unit)
    for key in ("EnvironmentFile=", "ExecStart=", "Restart=on-failure", "NoNewPrivileges=yes",
                "ReadWritePaths=", "User=", "ProtectSystem=strict", "CapabilityBoundingSet="):
        check(f"systemd: {key}", key in unit)
    exec_line = next((l for l in unit.splitlines() if l.startswith("ExecStart=")), "")
    check("systemd: 只绑 127.0.0.1", "127.0.0.1" in exec_line and "0.0.0.0" not in exec_line, exec_line)
    check("systemd: 不写入口令/令牌", "GBT_WALLET_PASS=" not in unit and "GBT_WALLET_API_TOKEN=" not in unit)

    # ---------- env.example ----------
    envtext = read(os.path.join(HERE, "env.example"))
    for var in ("GBT_WALLET_PASS", "GBT_WALLET_DIR", "GBT_WALLET_PORT", "GBT_WALLET_API_TOKEN",
                "GBT_CORS_ORIGINS", "ALCHEMY_RPC_URL", "GBT_EVM_RPC"):
        check(f"env.example: 含 {var}", re.search(rf"^{var}=", envtext, re.M) is not None)
    check("env.example: 口令值为占位符", re.search(r"^GBT_WALLET_PASS=<", envtext, re.M) is not None)
    check("env.example: 令牌值为占位符", re.search(r"^GBT_WALLET_API_TOKEN=<", envtext, re.M) is not None)
    check("env.example: 不含真实 Alchemy key 形态",
          re.search(r"alch_[A-Za-z0-9]{10,}", envtext) is None)

    # ---------- 钱包侧最小接入痕迹 ----------
    api_path = os.path.join(ROOT, "gbt_wallet", "api.py")
    api = read(api_path)
    check("api.py: 接入 install_middleware", "gbt_allinone.integration.auth import install_middleware" in api)
    check("api.py: 保留默认 CORS 降级分支", 'allow_origins=["*"]' in api)
    check("api.py: 未硬编码令牌/口令", "GBT_WALLET_API_TOKEN=" not in api)

    print(f"\n==== 配置自检: {len(OKS)} 通过 / {len(FAILS)} 失败 ====")
    for f in FAILS:
        print("  FAIL " + f)
    return 0 if not FAILS else 1


if __name__ == "__main__":
    raise SystemExit(main())
