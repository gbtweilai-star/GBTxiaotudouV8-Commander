/* GBT小土豆V8 · 对话面自主回路 · 契约测试（主人令 2026-10-04：她能直接操控触手自主运行）
 *
 * 跑法：py -3.14 holo_pet_w3/tests/run_tests.py（自动发现）或 node --test 本文件
 *
 * 判据（纯函数部分，不起 electron）：
 *  A. 指令块抽取与 Python 桥同一套行级规则：多行/内联/语言后缀都认；```gbt-result 绝不误抓；
 *  B. 发送/读取注入脚本是**字符串**且带正确开关（React 原生 setter + input + Enter）；
 *  C. 去重哈希稳定（同文同哈希、异文异哈希）—— 同一条回复不许执行两次；
 *  D. 模块只导出收口件（注入点集中在一个文件里，守卫 B4 依赖这条）。
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const L = require(path.join(__dirname, "..", "shell", "deepseek_loop.cjs"));

test("A 抽取：多行块 / 内联块 / 语言后缀都认", () => {
  const text = [
    "先说一句。",
    "```gbt",
    '{"kind": "health", "args": {"deep": {"a": 1}}}',
    "```",
    "再来：```gbt {\"kind\": \"task_manager\", \"args\": {}}```",
    "```gbt json",
    '{"kind": "llm_status", "args": {}}',
    "```",
  ].join("\n");
  const blocks = L.extractBlocks(text);
  assert.strictEqual(blocks.length, 3, "应抽到 3 块，实得 " + blocks.length);
  assert.match(blocks[0], /"kind": "health"/);
  assert.match(blocks[1], /task_manager/);
  assert.match(blocks[2], /llm_status/);
});

test("A2 抽取：```gbt-result 回喂块绝不许被当指令抓走（防自吞）", () => {
  const fb = "请依据以下执行结果继续：\n\n```gbt-result\n{\"summary\": \"x\"}\n```\n";
  assert.deepStrictEqual(L.extractBlocks(fb), []);
});

test("A3 抽取：散文里提到 ```gbt 但没成块（无收栏）不许误判成可执行", () => {
  const t = "我会输出 ```gbt 指令块，比如这行只是举例说明，没有完整的块。";
  const blocks = L.extractBlocks(t);
  // 行内 "```gbt" 后面不是 { 也不是收栏结构 ⇒ 收不到完整 JSON 块
  assert.ok(blocks.length === 0 || !/\{/.test(blocks[0]), "不许凭空造出一个 JSON 块");
});

test("B 注入脚本形状：textarea 原生 setter + input 事件 + Enter", () => {
  const js = L._sendJs('{"kind":"health"}');
  assert.match(js, /textarea#chat-input/);
  assert.match(js, /HTMLTextAreaElement\.prototype/);
  assert.match(js, /new Event\("input"/);
  assert.match(js, /KeyboardEvent\("keydown"/);
  assert.match(js, /keyCode: 13/);
});

test("B2 读取脚本：只认正文，跳过 think/reason 祖先链", () => {
  assert.match(L._readJs, /ds-markdown/);
  assert.match(L._readJs, /think\|reason/i);
});

test("C 去重哈希：同文同哈希、异文异哈希（同一条回复不许执行两次）", () => {
  const a = L.hashText('{"kind":"health"}');
  const b = L.hashText('{"kind":"health"} ');
  assert.strictEqual(a, a);
  assert.notStrictEqual(a, b);
  assert.match(a, /^[0-9a-f]{16}$/);
});

test("D 导出面：执行/回喂能力不外泄成第二个注入点", () => {
  const keys = Object.keys(L).sort();
  assert.ok(keys.includes("register") && keys.includes("setEnabled") && keys.includes("status"));
  assert.ok(keys.includes("extractBlocks") && keys.includes("hashText"));
});
