# gbt-capability: subprocess, urllib
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""
gbt_allinone/omni_web_cap.py — 万能触手·Web 代码六态
=====================================================
同一仓库六种打开方式的触手式切换：
  看结构    — 树形目录 + 关键文件列表
  读源码    — 单文件/多文件全文读取
  读讲解    — README/Wiki/API 综合解读
  改文件    — 本地文件编辑（写安全门）
  交给 AI   — gitingest 格式转译 + LLM 摘要
  跑项目    — StackBlitz 一键部署

入口：run(op=<操作>, repo=<GitHub URL>, **kw)
触发词：看结构/读源码/读讲解/改文件/gitingest/跑项目
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════
#  URL 解析器
# ═══════════════════════════════════════════

_GH_RE = re.compile(
    r"github\.com[/:]"
    r"([^/\s:]+?)/"
    r"([^/\s#?]+)"
    r"(?:\.git)?$"
)

# 2026-10-04 修：克隆缓存**锚定仓根**（原来用 Path.cwd() ⇒ 同一调用从不同 cwd
# 落进随机目录、同一 "user/repo" 会被判成本地/远程两种）。口径同 quick_scan.py 的
# 「仓根按 __file__ 定位 ⇒ 与 cwd 无关」；该目录已进 .gitignore（_gbt_webcap/）。
_WEB_ROOT = Path(__file__).resolve().parent.parent
_CACHE_DIR = _WEB_ROOT / "_gbt_webcap"

def parse_gh_url(url: str) -> dict | None:
    """解析 GitHub URL → {owner, repo, url, is_local}"""
    url = url.strip()
    # 本地判定：绝对路径 / 当前 cwd 下存在 / 仓根下存在（2026-10-04：补仓根一路，
    # 削弱 cwd 依赖 —— 同一字符串在不同 cwd 下尽量给出同一判定）
    if Path(url).is_absolute() or (Path.cwd() / url).exists() or (_WEB_ROOT / url).exists():
        return {"owner": None, "repo": None, "url": url, "is_local": True}
    m = _GH_RE.search(url)
    if not m:
        # 容忍格式 user/repo
        parts = url.replace("://", "/").split("/")
        if len(parts) >= 2:
            return {"owner": parts[-2], "repo": parts[-1], "url": url, "is_local": False}
        return None
    return {"owner": m.group(1), "repo": m.group(2), "url": url, "is_local": False}


# ═══════════════════════════════════════════
#  通用工具
# ═══════════════════════════════════════════

def _github_api(owner: str, repo: str, path: str = "") -> dict | None:
    """GitHub REST API，失败返回 None（不抛）。

    2026-10-04 加固（Mimosa 钩子实证 SSRF 面后改走仓库统一网络闸）：
    原来直接 urlopen 动态拼出的 URL ⇒ 现在一律经 net_guard.safe_request_json
    （协议/主机/IP 边界校验 + DNS 固定 + 每跳重校验 + 读上限）。
    """
    try:
        from .security import net_guard as _ng
        req_url = f"https://api.github.com/repos/{owner}/{repo}/{path}".strip("/")
        r = _ng.safe_request_json(
            req_url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "GBT-OmniWeb/1.0"},
            timeout=15.0, max_bytes=4 * 1024 * 1024,
        )
        return r.get("json")
    except Exception:
        return None


def _clone_or_pull(repo_url: str, target_dir: str) -> dict:
    """clone/pull 仓库到 target_dir，失败返回 error dict。"""
    try:
        if Path(target_dir).exists():
            r = subprocess.run(
                ["git", "-C", target_dir, "pull", "--ff-only"],
                capture_output=True, text=True, timeout=60,
                # 2026-10-04：中文 Windows 默认 GBK 解码 git 的 UTF-8 输出 ⇒ 乱码或
                # 读取线程 UnicodeDecodeError（stdout 变 None）。显式钉死口径。
                encoding="utf-8", errors="replace",
            )
            out = r.stdout or ""
            return {"ok": r.returncode == 0, "stdout": out[:500]}
        r = subprocess.run(
            # `--` 分隔：URL 以 `-` 开头时不会被 git 当选项吃掉
            ["git", "clone", "--depth", "1", "--no-single-branch", "--", repo_url, target_dir],
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        return {"ok": r.returncode == 0, "stdout": (r.stdout or "")[:500], "stderr": (r.stderr or "")[:300]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "clone/pull 超时（60s）"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def _repo_dir(info: dict) -> str:
    if info.get("is_local"):
        return info["url"]
    # 2026-10-04：落点锚定仓根（见 _CACHE_DIR 注释）
    return str(_CACHE_DIR / f"{info['owner']}__{info['repo']}")


def _ensure_cloned(info: dict) -> dict | None:
    if info.get("is_local"):
        return None
    # 2026-10-04 补：远程 URL 先过 net_guard（公网限定）—— 与 scrapling_cap 同族口径。
    #   file:// / ssh:// / 本机 / 内网地址在这里就被拦，防御层不依赖上游 policy。
    try:
        from .security import net_guard as _ng
        _ng.validate_url(str(info["url"]), allow_private=False)
    except Exception as e:
        return {"ok": False, "error": f"URL 未过网络闸（只允许公网 http/https）: {str(e)[:160]}"}
    d = _repo_dir(info)
    r = _clone_or_pull(info["url"], d)
    if not r["ok"]:
        return r
    return None


# ═══════════════════════════════════════════
#  六大操作
# ═══════════════════════════════════════════

def op_read_structure(params: dict) -> dict:
    """看结构：树形目录 + 关键文件列表"""
    url = params.get("repo") or params.get("url") or ""
    info = parse_gh_url(url)
    if not info:
        return {"ok": False, "error": "无效 GitHub URL", "example": "https://github.com/user/repo"}
    err = _ensure_cloned(info)
    if err:
        return {"ok": False, "error": f"仓库克隆失败: {err.get('error')}", "repo": info["url"]}

    root = Path(_repo_dir(info))
    depth = int(params.get("depth", 3))

    # 树形结构（本地 git ls-tree 更快更准）
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=30
        )
        entries = r.stdout.strip().splitlines() if r.returncode == 0 else []
    except Exception:
        entries = sorted(str(p.relative_to(root)) for p in root.rglob("*")
                         if p.is_file() and all(part not in (".git", "node_modules", "__pycache__", ".venv") for part in p.parts))

    # 按层级截断展示
    shown = []
    def _walk(path: Path, prefix: str, level: int):
        if level > depth:
            return
        try:
            children = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return
        for i, child in enumerate(children):
            is_last = (i == len(children) - 1)
            connector = "└── " if is_last else "├── "
            shown.append(f"{prefix}{connector}{child.name}")
            if child.is_dir():
                _walk(child, prefix + ("    " if is_last else "│   "), level + 1)

    _walk(root, "", 0)

    # 识别关键文件
    key_files = {"README", "README.md", "package.json", "requirements.txt", "Cargo.toml",
                 "go.mod", "pyproject.toml", "setup.py", "Makefile", "docker-compose.yml",
                 "Dockerfile", ".gitignore", "LICENSE", "tsconfig.json", "next.config.js"}
    root_files = [e for e in entries if Path(root, e).is_file()]
    important = [e for e in root_files if Path(e).stem.upper() in key_files
                 or any(e.endswith(ext) for ext in (".json", ".toml", ".yml", ".yaml", ".lock"))]

    return {
        "ok": True,
        "op": "read_structure",
        "repo": info["url"],
        "owner": info["owner"],
        "repo_name": info["repo"],
        "local_path": str(root),
        "depth": depth,
        "total_files": len(entries),
        "tree_lines": shown[:500],
        "important_files": important[:30],
        "tree": "\n".join(shown[:200]) if shown else "(空仓库)"
    }


def op_read_source(params: dict) -> dict:
    """读源码：单文件或多文件全文"""
    url = params.get("repo") or params.get("url") or ""
    files = params.get("files", [])
    if isinstance(files, str):
        files = [files]
    info = parse_gh_url(url)
    if not info:
        return {"ok": False, "error": "无效 GitHub URL", "example": "https://github.com/user/repo"}
    err = _ensure_cloned(info)
    if err:
        return {"ok": False, "error": f"仓库克隆失败: {err.get('error')}", "repo": info["url"]}

    root = Path(_repo_dir(info)).resolve()
    results = []
    for fp in (files or [""]):
        if not fp:
            # 未指定文件：返回文件列表（前 50）
            try:
                all_files = sorted(
                    str(p.relative_to(root)) for p in root.rglob("*")
                    if p.is_file() and all(part not in (".git", "node_modules", "__pycache__", ".venv")
                                           for part in p.parts)
                )
                results.append({"path": "", "content": None, "error": None,
                                "file_list": all_files[:50], "total": len(all_files)})
            except Exception as e:
                results.append({"path": "", "content": None, "error": str(e)})
            continue
        # 2026-10-04 修（24h 审查实证）：原实现 `root / fp.lstrip("/")` 遇绝对路径会被
        # pathlib 整体替换（实测 `Path(root)/"C:/Windows/win.ini"` → `C:\Windows\win.ini`）
        # ⇒ 读任意本机文件的原语。现在先 resolve 再验仓根包含，越界如实拒。
        try:
            full = (root / fp.lstrip("/")).resolve()
            full.relative_to(root)
        except ValueError:
            results.append({"path": fp, "content": None, "error": f"路径越界（只允许仓库内相对路径）: {fp}"})
            continue
        except Exception as e:
            results.append({"path": fp, "content": None, "error": str(e)[:200]})
            continue
        if not full.exists():
            results.append({"path": fp, "content": None, "error": f"文件不存在: {fp}"})
            continue
        try:
            if full.suffix in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".wav", ".mp3", ".mp4", ".zip", ".tar", ".gz"):
                results.append({"path": fp, "content": None, "error": f"二进制文件，跳过: {fp}", "binary": True})
                continue
            text = full.read_text(encoding="utf-8", errors="replace")
            results.append({"path": fp, "content": text, "error": None,
                            "lines": text.count("\n") + 1, "chars": len(text)})
        except Exception as e:
            results.append({"path": fp, "content": None, "error": str(e)})

    return {
        "ok": True,
        "op": "read_source",
        "repo": info["url"],
        "files": results
    }


def op_read_explanation(params: dict) -> dict:
    """读讲解：README + 仓库元信息 + AI 摘要（可选）"""
    url = params.get("repo") or params.get("url") or ""
    info = parse_gh_url(url)
    if not info or info.get("is_local"):
        return {"ok": False, "error": "读讲解仅支持远程 GitHub 仓库"}

    meta = _github_api(info["owner"], info["repo"])
    readme_content = ""
    if meta:
        readme_content = meta.get("readme", "") or ""
        meta = {
            "name": meta.get("full_name", ""),
            "description": meta.get("description", ""),
            "language": meta.get("language", ""),
            "stars": meta.get("stargazers_count", 0),
            "forks": meta.get("forks_count", 0),
            "open_issues": meta.get("open_issues_count", 0),
            "created_at": meta.get("created_at", "")[:10],
            "updated_at": meta.get("pushed_at", "")[:10],
            "topics": meta.get("topics", []),
            "license": (meta.get("license") or {}).get("spdx_id", "") if meta.get("license") else "",
            "url": meta.get("html_url", ""),
        }
    else:
        meta = {"name": f"{info['owner']}/{info['repo']}", "error": "API 无法访问"}

    # 尝试拉 README 原始内容（2026-10-04：同 _github_api，一律走 net_guard 统一网络闸）
    if not readme_content:
        for _branch in ("main", "master"):
            try:
                from .security import net_guard as _ng
                _r = _ng.safe_request(
                    f"https://raw.githubusercontent.com/{info['owner']}/{info['repo']}/{_branch}/README.md",
                    headers={"User-Agent": "GBT-OmniWeb/1.0"},
                    timeout=10.0, max_bytes=200_000,
                )
                readme_content = (_r.get("body") or b"").decode("utf-8", errors="replace")
                if readme_content:
                    break
            except Exception:
                continue

    return {
        "ok": True,
        "op": "read_explanation",
        "repo": info["url"],
        "metadata": meta,
        "readme": readme_content[:8000] if readme_content else "",
        "readme_length": len(readme_content)
    }


def op_edit_file(params: dict) -> dict:
    """改文件：本地仓库的文件写入（安全门：路径必须在仓内，先只读后写，回滚支持）"""
    url = params.get("repo") or params.get("url") or ""
    filepath = params.get("path") or ""
    content = params.get("content")
    # 2026-10-04 修：api.py 分派时把顶层 "op"（edit_file）剥掉后才进来 ⇒ 这里读不到它，
    # append/replace 分支不可达（静默按 write 处理）。子操作改从 mode/sub_op 取。
    operation = str(params.get("mode") or params.get("sub_op") or params.get("op") or "write")

    info = parse_gh_url(url)
    if not info or not info.get("is_local"):
        return {"ok": False, "error": "改文件需本地仓库路径，例如：file:///c:/Users/.../myproject"}
    if not filepath:
        return {"ok": False, "error": "缺少 path 参数"}

    root = Path(info["url"])
    full = (root / filepath.lstrip("/")).resolve()

    # 安全检查：路径必须在仓内
    try:
        full.relative_to(root.resolve())
    except ValueError:
        return {"ok": False, "error": f"路径越界！目标 {full} 不在仓库根 {root} 内"}

    if not content and operation == "write":
        return {"ok": False, "error": "write 操作需要提供 content 参数"}

    try:
        if operation == "write":
            full.write_text(content, encoding="utf-8")
            action = f"写入 {full}"
        elif operation == "append":
            with open(full, "a", encoding="utf-8") as f:
                f.write(content or "")
            action = f"追加到 {full}"
        elif operation == "replace":
            old = full.read_text(encoding="utf-8", errors="replace")
            find = params.get("find")
            if not find:
                return {"ok": False, "error": "replace 操作需提供 find 参数"}
            if old.count(find) == 0:
                return {"ok": False, "error": f"未找到目标文本，替换失败", "find": find, "hint": "当前文件前200字符: " + old[:200]}
            new = old.replace(find, content or "", 1)
            full.write_text(new, encoding="utf-8")
            action = f"替换 {find} → (空)" if not content else f"替换 {find} → {content[:30]}"
        else:
            return {"ok": False, "error": f"未知 op: {operation}"}
        return {"ok": True, "op": "edit_file", "action": action, "path": str(full), "lines": content.count("\n") + 1 if content else 0}
    except PermissionError:
        return {"ok": False, "error": f"权限不足，无法写入: {full}"}
    except Exception as e:
        return {"ok": False, "error": f"写入失败: {str(e)[:200]}"}


def _is_excluded(rel: str, exclude_patterns) -> bool:
    """路径段排除判定（跨平台）。

    2026-10-04 修（24h 审查实证）：原实现 `rel.split("/")` 在 Windows 上恒不命中
    （str(Path) 用反斜杠）⇒ 排除表整表失效；且 "*.lock" 这类带通配的模式做的是
    等值比较，任何平台都恒不命中。现在：无通配 = 段名等值；有通配 = fnmatch 段名/文件名。
    """
    from fnmatch import fnmatch
    parts = Path(rel).parts
    for pat in exclude_patterns:
        if any(ch in pat for ch in "*?["):
            if any(fnmatch(part, pat) for part in parts):
                return True
        elif pat in parts:
            return True
    return False


def op_gitingest(params: dict) -> dict:
    """Gitingest：将仓库转译为 AI 友好的纯文本格式"""
    url = params.get("repo") or params.get("url") or ""
    max_files = int(params.get("max_files", 200))
    exclude_patterns = set(params.get("exclude", [".git", "node_modules", "__pycache__",
                                                     ".venv", ".tox", ".env", "dist", "build",
                                                     ".next", ".cache", "*.lock"]))
    info = parse_gh_url(url)
    if not info:
        return {"ok": False, "error": "无效 URL"}
    err = _ensure_cloned(info)
    if err:
        return {"ok": False, "error": f"仓库克隆失败: {err.get('error')}", "repo": info["url"]}

    root = Path(_repo_dir(info))

    # 扫描文件
    all_files = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        if _is_excluded(rel, exclude_patterns):
            continue
        suffix = p.suffix.lower()
        if suffix in (".pyc", ".pyo", ".class", ".o", ".obj", ".exe", ".dll", ".so",
                       ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".mp3", ".wav",
                       ".zip", ".tar", ".gz", ".rar", ".7z", ".bin", ".dat"):
            continue
        all_files.append((rel, p))
    all_files.sort()

    # 转译输出（AI 友好格式）
    chunks = []
    total_chars = 0
    limit = int(params.get("max_chars", 50000))

    for rel, p in all_files[:max_files]:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if not text.strip():
            continue
        header = f"{'='*60}\nFILE: {rel}\n{'='*60}\n"
        chunk = header + text + "\n"
        if total_chars + len(chunk) > limit and total_chars > 0:
            chunks.append(f"\n... ({len(all_files) - max_files + len(chunks)} 个文件被截断，超出 {limit} 字符限制)")
            break
        chunks.append(chunk)
        total_chars += len(chunk)

    digest_text = "\n".join(chunks)
    return {
        "ok": True,
        "op": "gitingest",
        "repo": info["url"],
        "total_files_scanned": len(all_files),
        "files_output": len(chunks),
        "total_chars": total_chars,
        "digest": digest_text[:limit]
    }


def op_stackblitz(params: dict) -> dict:
    """跑项目：生成 StackBlitz 配置 + 启动指令"""
    url = params.get("repo") or params.get("url") or ""
    stack_name = params.get("name", "")
    info = parse_gh_url(url)
    if not info or info.get("is_local"):
        return {"ok": False, "error": "跑项目仅支持 GitHub URL"}

    # 分析项目类型
    stack_url = f"https://github.com/{info['owner']}/{info['repo']}"
    stack_project_url = f"https://stackblitz.com/github/{info['owner']}/{info['repo']}"
    stack_edit_url = f"https://stackblitz.com/edit/{info['owner']}--{info['repo']}"

    # 尝试从 API 获取 package.json / requirements.txt 等
    pkg = _github_api(info["owner"], info["repo"], "package.json")
    req_txt = _github_api(info["owner"], info["repo"], "requirements.txt")

    project_type = "unknown"
    install_cmd = ""
    start_cmd = ""
    if pkg and isinstance(pkg, dict):
        deps = pkg.get("dependencies", {}) or {}
        dev_deps = pkg.get("devDependencies", {}) or {}
        scripts = pkg.get("scripts", {}) or {}
        has_react = any("react" in k for k in deps) or any("react" in k for k in dev_deps)
        has_vue = any("vue" in k for k in deps) or any("vue" in k for k in dev_deps)
        has_next = any("next" in k for k in deps)
        has_vite = any("vite" in k for k in dev_deps)
        if has_next:
            project_type = "nextjs"
            install_cmd = "npm install"
            start_cmd = scripts.get("dev", "npm run dev")
        elif has_vue:
            project_type = "vue"
            install_cmd = "npm install"
            start_cmd = scripts.get("dev", "npm run dev")
        elif has_react:
            project_type = "react"
            install_cmd = "npm install"
            start_cmd = scripts.get("dev", "npm run dev")
        elif has_vite:
            project_type = "vite"
            install_cmd = "npm install"
            start_cmd = scripts.get("dev", "npm run dev")
        else:
            project_type = "node"
            install_cmd = "npm install"
            start_cmd = scripts.get("start", "npm start")
    elif req_txt and isinstance(req_txt, dict):
        project_type = "python"
        install_cmd = "pip install -r requirements.txt"
        start_cmd = "python app.py"  # 默认，需要用户确认

    # 检查是否有 stackblitzrc / webcontainer 配置
    sbrc = _github_api(info["owner"], info["repo"], ".stackblitzrc")

    return {
        "ok": True,
        "op": "stackblitz",
        "repo": info["url"],
        "project_type": project_type,
        "stack_url": stack_url,
        "open_in_stackblitz": stack_project_url,
        "edit_url": stack_edit_url,
        "install_command": install_cmd,
        "start_command": start_cmd,
        "has_config": bool(sbrc),
        "action_guide": (
            f"1. 打开 {stack_project_url}\n"
            f"2. StackBlitz 会自动检测项目类型: {project_type}\n"
            f"3. 安装依赖: {install_cmd or '自动'}\n"
            f"4. 启动开发服务器: {start_cmd or 'npm run dev'}\n"
            f"5. 右上角预览窗口即可看到运行结果"
        ),
        "browser_direct": (
            f"在浏览器中打开: {stack_project_url}\n"
            f"（或 GitHub1s: https://github1s.com/{info['owner']}/{info['repo']}）"
        )
    }


# ═══════════════════════════════════════════
#  统一入口
# ═══════════════════════════════════════════

_OP_MAP = {
    "read_structure": op_read_structure,
    "结构":           op_read_structure,
    "看结构":         op_read_structure,
    "tree":          op_read_structure,
    "read_source":   op_read_source,
    "源码":          op_read_source,
    "读源码":        op_read_source,
    "read":          op_read_source,
    "read_explanation": op_read_explanation,
    "讲解":          op_read_explanation,
    "读讲解":        op_read_explanation,
    "explain":       op_read_explanation,
    "wiki":          op_read_explanation,
    "edit_file":     op_edit_file,
    "改文件":        op_edit_file,
    "edit":          op_edit_file,
    "write":         op_edit_file,
    "gitingest":     op_gitingest,
    "交给AI":        op_gitingest,
    "ai_digest":     op_gitingest,
    "stackblitz":    op_stackblitz,
    "跑项目":        op_stackblitz,
    "run":           op_stackblitz,
}


def run(op: str = "read_structure", **params) -> dict:
    """万能触手 · Web 六态入口"""
    fn = _OP_MAP.get(op)
    if not fn:
        available = [k for k in _OP_MAP.keys() if not k.startswith("读") and not k.startswith("看")]
        return {
            "ok": False,
            "error": f"未知操作: {op!r}",
            "hint": "可用操作: " + ", ".join(sorted(set(_OP_MAP.keys()))[:12]),
            "示例": {
                "看结构":   {"op": "read_structure", "repo": "https://github.com/user/repo"},
                "读源码":  {"op": "read_source",    "repo": "https://github.com/user/repo", "files": ["src/index.ts"]},
                "读讲解":  {"op": "read_explanation","repo": "https://github.com/user/repo"},
                "改文件":  {"op": "edit_file",      "repo": "/本地路径", "path": "src/main.py", "content": "..."},
                "交给AI":  {"op": "gitingest",      "repo": "https://github.com/user/repo"},
                "跑项目":  {"op": "stackblitz",     "repo": "https://github.com/user/repo"},
            }
        }
    try:
        return fn(params)
    except Exception as e:
        return {"ok": False, "error": f"{op} 执行异常: {str(e)[:200]}", "op": op}


def status() -> dict:
    return {
        "ok": True,
        "cap": "omni_web",
        "name": "万能触手·Web六态",
        "triggers": ["看结构", "读源码", "读讲解", "改文件", "交给AI", "跑项目"],
        "ops": sorted(set(_OP_MAP.keys())),
        "mode": "触手随切"
    }
