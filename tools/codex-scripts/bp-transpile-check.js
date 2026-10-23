// gbt-capability: none
// bp-transpile-check.js —— 用**预览同款 Babel**（@babel/standalone@7.26.4）
// 把「原件」与「补丁件」各转译一遍，逐文件报 OK / 报错。
//
// 为什么必须做这一步：补丁"看着对"和"真能编译"是两件事。
// 本会话已经在别处栽过同型跟头（跑法错、参数被静默丢），
// 所以补丁也要过机器，而不是靠读。
//
// 用法：node tools/codex-scripts/bp-transpile-check.js <.scratch/bp-verify>
const fs = require("node:fs");
const path = require("node:path");

const verifyDir = process.argv[2] || ".scratch/bp-verify";
const babelPath = path.join(verifyDir, "babel.min.js");

let Babel;
try {
  Babel = require(path.resolve(babelPath));
} catch (e) {
  console.error("取不到 babel：", e.message);
  process.exit(2);
}
console.log("Babel 版本:", Babel.version);

function check(dirLabel) {
  const dir = path.join(verifyDir, dirLabel);
  const files = fs.readdirSync(dir).filter((f) => f.endsWith(".tsx") || f.endsWith(".ts"));
  let ok = 0;
  const bad = [];
  for (const f of files) {
    const src = fs.readFileSync(path.join(dir, f), "utf8");
    // 还原成带目录的 filename，让 Babel 按 .tsx 选 preset
    const filename = f.replace(/__/g, "/");
    try {
      Babel.transform(src, {
        filename,
        presets: [["react", {}], ["typescript", {}]],
        sourceType: "module",
      });
      ok++;
    } catch (e) {
      bad.push({ file: filename, msg: String(e.message).split("\n")[0].slice(0, 160) });
    }
  }
  console.log("\n=== %s ：%d 个文件，编译通过 %d，失败 %d ===", dirLabel, files.length, ok, bad.length);
  for (const b of bad) console.log("   ❌ %s\n        %s", b.file, b.msg);
  return { total: files.length, ok, bad };
}

const orig = check("src.orig");
const patched = check("src.patched");

console.log("\n" + "=".repeat(70));
console.log("对照：原件通过 %d/%d ；补丁件通过 %d/%d",
  orig.ok, orig.total, patched.ok, patched.total);
if (patched.bad.length) {
  console.log("\n补丁件仍然编译不过 —— 补丁必须改；不许带着编译错误交出去。");
  process.exit(1);
}
if (patched.ok === orig.ok && patched.total === orig.total) {
  console.log("\n✅ 补丁件与原件编译通过数一致 ⇒ 补丁没有引入编译错误。");
} else if (patched.ok > orig.ok) {
  console.log("\n✅ 补丁件比原件还多通过 %d 个 —— 补丁顺带修好了编译问题。", patched.ok - orig.ok);
} else {
  console.log("\n⚠️ 补丁件比原件少通过 %d 个 —— 必须查清。", orig.ok - patched.ok);
  process.exit(1);
}
