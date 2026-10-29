# -*- coding: utf-8 -*-
"""把 vendored 的 three.js addon 里的**裸模块名**改成相对路径。

## 为什么必须做这一步

`three/examples/jsm/*` 用的是**裸模块名** `from 'three'`，靠 `importmap` 解析。
而本壳的窗口跑在 `script-src 'self'` 的 CSP 下 —— **inline `<script type="importmap">` 会被 CSP 挡掉**
（importmap 按规范必须是内联的），所以这条路在壳里走不通。

⇒ 正解：把 addon 当**自己的 vendored 源码**看，把裸名改成相对路径。
   这是"vendoring"的标准动作，不是 hack —— 但**必须记下来**，否则下次升级 three 会一脸茫然。

## 用法

    py -3.14 tools/codex-scripts/vendor_three.py --check
    py -3.14 tools/codex-scripts/vendor_three.py --write
"""
import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
DST = ROOT / "holo_pet_w3" / "brain" / "vendor"
SRC = ROOT / "vendor" / "node_modules" / "three"

# 需要 vendored 的件：入口库 + 控制器 + 后处理链 + 两个 shader
FILES = {
    "three.module.min.js": "build/three.module.min.js",
    "OrbitControls.js": "examples/jsm/controls/OrbitControls.js",
 # `Pass.js` **必须单独 vendor**（首跑漏了它，页面报 4 次
    #    "Class extends value undefined" + "ShaderPass is not a constructor"）：
    #    three 的后处理链是 `ShaderPass extends Pass`、`MaskPass extends Pass` …，
    #    而 `Pass` 住在**自己的文件** `examples/jsm/postprocessing/Pass.js` 里，
    #    不在入口库的三个导出里。漏了它 ⇒ 整条后处理链起不来 ⇒ 辉光没了。
    "Pass.js": "examples/jsm/postprocessing/Pass.js",
    "EffectComposer.js": "examples/jsm/postprocessing/EffectComposer.js",
    "RenderPass.js": "examples/jsm/postprocessing/RenderPass.js",
    "ShaderPass.js": "examples/jsm/postprocessing/ShaderPass.js",
    "MaskPass.js": "examples/jsm/postprocessing/MaskPass.js",
    "UnrealBloomPass.js": "examples/jsm/postprocessing/UnrealBloomPass.js",
    "CopyShader.js": "examples/jsm/shaders/CopyShader.js",
    "LuminosityHighPassShader.js": "examples/jsm/shaders/LuminosityHighPassShader.js",
}

# 改写规则：裸名 → 相对路径；原来指向 `../shaders/` 的在扁平化后要去掉层级
RULES = [
    (re.compile(r"""(from\s+['"])three(['"])"""), r"\1./three.module.min.js\2"),
    (re.compile(r"""(from\s+['"])\.\./(?:shaders|postprocessing|controls)/([^'"]+)(['"])"""),
     r"\1./\2\3"),
]

HEADER = ("/* vendored from three@0.180.0 · 裸模块名已改为相对路径（壳的 CSP 不许 importmap）\n"
          "   来源：vendor/node_modules/three/{src}\n"
          "   重建：py -3.14 tools/codex-scripts/vendor_three.py --write\n"
          "   本文件是**第三方代码的原样拷贝 + 一处 import 改写**，不要在这里加业务逻辑。 */\n")


def _to_classic(name: str, text: str) -> str:
    """把 ESM 的 addon **机械地**转成经典脚本（挂到全局 `THREE` 上）。

    ## 为什么必须转（这是实测堵死的一条路，不是选择）

    壳的窗口走 `loadFile` ⇒ `file://`。而 **`file://` 下 `<script type="module">` 会被 CORS 挡掉**：
    实跑取证 `net::ERR_FAILED`，页面**静默空白**（画布空的、左栏停在占位符）。
    壳的 `main.cjs` 又没关 `webSecurity`（默认 true）⇒ 这条路在**真壳里也走不通**，
    不是渲染器的问题。所以：**只能经典脚本**。

    ## 转换规则（三句话，纯机械）

      ① `import {A, B} from '…'`  → `const {A, B} = THREE;`（每个 addon 的导出都挂回 `THREE`，所以互相能取到）
      ② `export {A, B};`          → `Object.assign(THREE, {A, B});`
      ③ `export class X` / `export const X` / `export function X` → 去掉 `export `，末尾统一挂回

    📌 这是"vendoring 的标准动作"，不是 hack；但**必须记下来**，否则下次升级 three 会一脸茫然。
    """
    if name == "three.module.min.js":
        return text
    text = re.sub(r"import\s*\{([^}]*)\}\s*from\s*['\"][^'\"]*['\"]\s*;",
                  lambda m: "const {%s} = THREE;" % m.group(1).strip(), text)
    declared = []

    def _decl(m):
        declared.append(m.group(1))
        return "%s %s" % (m.group(2), m.group(1))

    text = re.sub(r"export\s+(class|const|let|function)\s+([A-Za-z_$][\w$]*)",
                  lambda m: _decl(m), text)
    text = re.sub(r"export\s*\{([^}]*)\}\s*;?",
                  lambda m: "Object.assign(THREE, {%s});" % m.group(1).strip(), text)
    if declared:
        text += "\nObject.assign(THREE, {%s});\n" % ", ".join(sorted(set(declared)))
    return ("/* vendored from three@0.180.0 · **已转成经典脚本**（file:// 下 ESM 走不通）\n"
            "   来源：vendor/node_modules/three/examples/jsm/%s\n"
            "   重建：py -3.14 tools/codex-scripts/vendor_three.py --write --classic\n"
            "   第三方代码原样拷贝 + 机械 import/export 改写，不要在这里加业务逻辑。 */\n"
            "(function (THREE) {\n'use strict';\n%s\n})(THREE);\n" % (name, text))


def _emit_three_global(src: Path, dst: Path) -> tuple:
    """把 `three.cjs`（CommonJS）包成经典脚本：`var THREE = (function(){var exports={};…})()`。

    实测形态：`'use strict'` + **422 个 `exports.X =`** + **0 个 `require(`** + **0 个 `module.exports`**
    ⇒ 给它一个本地 `exports` 就能自洽，不需要真的模块系统。
    """
    cjs = src / "build" / "three.cjs"
    if not cjs.is_file():
        return False, "缺 build/three.cjs"
    body = cjs.read_text(encoding="utf-8", errors="replace")
    if re.search(r"\bmodule\.exports\b", body) or re.search(r"\brequire\(", body):
        return False, "three.cjs 里出现了 module.exports / require —— 形态变了，本器要重看"
    dst.write_text(
        "/* three@0.180.0 · CommonJS 构建**包成经典脚本**（file:// 下 ESM 走不通）。\n"
        "   重建：py -3.14 tools/codex-scripts/vendor_three.py --write --classic\n"
        "   形态实测：422 个 exports.X= · 0 个 require( · 0 个 module.exports ⇒ 给个本地 exports 即自洽。 */\n"
        "var THREE = (function () {\nvar exports = {};\n" + body + "\nreturn exports;\n})();\n",
        encoding="utf-8")
    return True, ""


def main() -> int:
    ap = argparse.ArgumentParser(description="vendor three.js 到壳里并改掉裸模块名")
    ap.add_argument("--write", action="store_true", help="真写（默认只检查）")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--classic", action="store_true",
                    help="另出经典脚本版（three.global.js + *.global.js）—— **壳里必须用这一版**")
    a = ap.parse_args()

    print("=" * 74)
    print("three.js vendoring · 壳内自包含（零 CDN）")
    print("=" * 74)
    print("  源 %s（%s）" % (SRC, (SRC / "package.json").is_file() and "在" or "**缺**"))
    if not SRC.is_dir():
        print("  🔴 源没有 —— 先确认 vendor/node_modules/three 在不在")
        return 2

    DST.mkdir(parents=True, exist_ok=True)
    bad, wrote = [], 0
    for name, rel in FILES.items():
        s = SRC / rel
        if not s.is_file():
            bad.append("源缺 %s" % rel)
            continue
        text = s.read_text(encoding="utf-8", errors="replace")
        # three.module.min.js 里没有裸名，不需要加头（加了会破坏 sourceMappingURL 之外的体积统计）
        if name != "three.module.min.js":
            for rx, rep in RULES:
                text = rx.sub(rep, text)
        out = DST / name
        if a.write:
            hdr = "" if name == "three.module.min.js" else HEADER.format(src=rel)
            out.write_text(hdr + text, encoding="utf-8")
            wrote += 1
        left = len(re.findall(r"""from\s+['"]three['"]""", text))
        left += len(re.findall(r"""from\s+['"]\.\./""", text))
        print("  %-30s %8.1f KB  残留裸名/上层引用 %d %s"
              % (name, len(text) / 1024.0, left, "✅" if left == 0 else "🔴"))
        if left:
            bad.append("%s 还有 %d 处裸名/上层引用" % (name, left))

    print("-" * 74)
    if a.classic:
        # 顺序 = 依赖序：先入口库，再 shader，再 pass，最后控制器
        order = ["Pass.js", "CopyShader.js", "LuminosityHighPassShader.js", "MaskPass.js",
                 "ShaderPass.js", "RenderPass.js", "EffectComposer.js", "UnrealBloomPass.js",
                 "OrbitControls.js"]
        ok, why = (True, "")
        if a.write:
            ok, why = _emit_three_global(SRC, DST / "three.global.js")
        print("  %-30s %s" % ("three.global.js", "✅ 已写" if (a.write and ok) else ("🔴 " + why if why else "可写")))
        if why:
            bad.append(why)
        for n in order:
            if not (DST / n).is_file():
                bad.append("缺 %s（先不加 --classic 跑一次 --write）" % n)
                continue
            out = _to_classic(n, (DST / n).read_text(encoding="utf-8"))
            if a.write:
                (DST / n.replace(".js", ".global.js")).write_text(out, encoding="utf-8")
            left = len(re.findall(r"^\s*export\s|^\s*import\s", out, re.M))
            print("  %-30s %8.1f KB  残留 import/export %d %s"
                  % (n.replace(".js", ".global.js"), len(out) / 1024.0, left,
                     "✅" if left == 0 else "🔴"))
            if left:
                bad.append("%s 还有 %d 处 import/export" % (n, left))
    print("-" * 74)
    if bad:
        print("  🔴 %d 处问题：%s" % (len(bad), bad))
        print("  ⚠️ 有一条已知例外：three.module.min.js 内部用 `import.meta`/相对 chunk，"
              "本器只判 addon 的裸名 —— 入口库残留计数为 0 才算过。")
        return 1
    print("  %s：%d 件%s" % ("已写入" if a.write else "可写（加 --write 落盘）",
                           wrote if a.write else len(FILES), "" if a.write else "，全部无裸名"))
    print("  落地 %s" % DST)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
