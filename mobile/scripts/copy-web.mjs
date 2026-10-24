// 把发布页那套静态件复制进 mobile/www（Capacitor 只认 webDir 目录）。
// 显式白名单，不整棵复制 —— 否则会把 mobile/ 自己递归拷进去。
import { cp, mkdir, rm, readdir, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

const here = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const root = path.resolve(here, "..", "..");        // 发布仓根
const out = path.resolve(here, "..", "www");

const FILES = ["index.html", "manifest.webmanifest", "sw.js", "LICENSE", "NOTICE"];
const DIRS = ["assets", "icons", "arms", "docs", "data"];

await rm(out, { recursive: true, force: true });
await mkdir(out, { recursive: true });

for (const f of FILES) {
  const src = path.join(root, f);
  if (existsSync(src)) await cp(src, path.join(out, f));
}
for (const d of DIRS) {
  const src = path.join(root, d);
  if (existsSync(src)) await cp(src, path.join(out, d), { recursive: true });
}

const walk = async (p) => {
  let n = 0, bytes = 0;
  for (const e of await readdir(p, { withFileTypes: true })) {
    const q = path.join(p, e.name);
    if (e.isDirectory()) { const r = await walk(q); n += r.n; bytes += r.bytes; }
    else { n += 1; bytes += (await stat(q)).size; }
  }
  return { n, bytes };
};
const r = await walk(out);
console.log(`www 就绪：${r.n} 个文件 / ${(r.bytes / 1048576).toFixed(1)} MB → ${out}`);
