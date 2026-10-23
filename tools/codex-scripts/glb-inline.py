# -*- coding: utf-8 -*-
"""把 .glb **内联成经典脚本**（`window.GBT_GLB_B64="…"`），给 `file://` 下的舞台兜底。

## 为什么需要这一件（2026-10-18 实测，不是猜的）

语音剧场要把工程里的绑骨资产 `dh-v2-rigged.glb` 真渲染出来。但：

- 壳的窗口走 `loadFile` ⇒ `file://`；`GLTFLoader.load('assets/x.glb')` 走 **fetch**，
  而 Chromium 在 `file://` 下默认**拦 fetch**（实测：`Failed to fetch`，页面照样渲染但模型空）。
- 三条路里：① 关 `webSecurity` = 拆安全面（不干）；② 起本地 HTTP 服务 = 多一个常驻面（不干）；
  ③ **把字节内联进一个 <script>** = 零常驻面、零安全放宽、打包件里也能跑。
  ⇒ 走 ③：`.glb` 仍是**唯一真源**，本器生成的 `.b64.js` 是**派生件**。

## 判据（防"派生件悄悄过期"——本仓 P9：账没有写手必烂）

    py -3.14 tools/codex-scripts/glb-inline.py --check      # 与 .glb 的 sha256 对不上就非零退出
    py -3.14 tools/codex-scripts/glb-inline.py --write      # 重建派生件

派生件里**写死**源文件的 sha256 与字节数；`--check` 解回字节重算，不一致 ⇒ 红。
这条闸挡的是"改了模型忘了重跑本器"——那种情况下页面会静默用旧模型，而且**长得一样**。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
import argparse
import base64
import hashlib
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
GLB = ROOT / "holo_pet_w3" / "voice-theater" / "assets" / "dh-v2-rigged.glb"
OUT = GLB.with_suffix(GLB.suffix + ".b64.js")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build(glb: Path) -> str:
    raw = glb.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return (
        "/* 自动生成，别手改 —— 源：holo_pet_w3/voice-theater/assets/dh-v2-rigged.glb\n"
        "   重建：py -3.14 tools/codex-scripts/glb-inline.py --write\n"
        "   为什么有它：file:// 下 fetch 被 Chromium 拦（实测 Failed to fetch）⇒ 模型字节内联走 <script>。\n"
        "   源 sha256：%s\n"
        "   源字节数：%d\n"
        "   本件内容 = 源字节的 base64，**不含任何业务逻辑**。 */\n"
        "window.GBT_GLB_B64 = \"%s\";\n"
        "window.GBT_GLB_META = { sha256: \"%s\", bytes: %d, src: \"assets/dh-v2-rigged.glb\" };\n"
        % (_sha(raw), len(raw), b64, _sha(raw), len(raw))
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="把 GLB 内联成经典脚本（+ 对账）")
    ap.add_argument("--write", action="store_true", help="重建派生件")
    ap.add_argument("--check", action="store_true", help="只对账（默认）")
    a = ap.parse_args()

    if not GLB.is_file():
        print("🔴 源不在：%s" % GLB)
        return 2
    raw = GLB.read_bytes()
    print("源 %s · %d 字节 · sha256 %s" % (GLB.name, len(raw), _sha(raw)[:16]))

    if a.write:
        OUT.write_text(build(GLB), encoding="utf-8")
        print("✅ 已写 %s（%.1f MB）" % (OUT.name, OUT.stat().st_size / 1024.0 / 1024.0))
        return 0

    if not OUT.is_file():
        print("🔴 派生件不在：%s（跑 --write）" % OUT.name)
        return 1

    text = OUT.read_text(encoding="utf-8", errors="replace")
    m = __import__("re").search(r'window\.GBT_GLB_B64 = "([A-Za-z0-9+/=]+)"', text)
    if not m:
        print("🔴 派生件里找不到 GBT_GLB_B64 载荷（形状变了？）")
        return 1
    got = base64.b64decode(m.group(1))
    if got != raw:
        print("🔴 派生件与源不一致：源 %d 字节 / 派生 %d 字节 · 源 sha %s / 派生 sha %s"
              % (len(raw), len(got), _sha(raw)[:16], _sha(got)[:16]))
        print("   ⇒ 跑 --write 重建（否则页面会静默用旧模型，而且长得一样）")
        return 1
    print("✅ 对账一致（%d 字节）· 派生件 %s" % (len(got), OUT.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
