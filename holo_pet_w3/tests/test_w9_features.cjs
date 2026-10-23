/* GBT小土豆V8 · W9 · 数字人召唤台 + AI 朋友圈 · 纯函数层契约
 *
 * 为什么这组必须有：`shell/features.cjs` 是 W9 唯一能被 `node --test` 钉住的一层
 * （main.cjs 顶部就 require("electron")，在 node --test 里根本 require 不动）。
 * 所以「脱敏、归一化、去重、就绪表、召唤计划」这些行为，只要没被本文件钉住，
 * 就等于没有任何判据 —— 想怎么漂就怎么漂。
 *
 * 判据纪律：
 *   1) 每条正对照都要配负对照，且两臂结果**必须不同**（相同 = 扫描器瞎，不许报 PASS）。
 *   2) 断言 reason / message，不只断言类型 —— 同型不同因的用例什么也证明不了（O51 #15 教训）。
 *   3) 最后一条守「纯函数层」这块牌子：零 electron、零子进程、零网络，
 *      并用 main.cjs 做负对照证明这条扫描器有牙。
 *
 * 跑法：`py -3.10 holo_pet_w3\tests\run_tests.py`（入口显式列举 test_*.cjs）
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const W3 = path.join(__dirname, "..");
const SHELL = path.join(W3, "shell");
const FEATURES = path.join(SHELL, "features.cjs");
const SRC = fs.readFileSync(FEATURES, "utf8");
const F = require(FEATURES);

/* ── 一 · 脱敏层 ── */

test("1. 正对照：五类敏感文本全部被替换，且命中数如实报出来", () => {
  const raw = [
    "私钥在此 -----BEGIN RSA PRIVATE KEY----- MIIEowIBAAKCAQEA -----END RSA PRIVATE KEY-----",
    "日志落在 C:\\Users\\ADMIN\\Desktop\\secret\\token.txt",
    "配置里 api_key=AbCdEf0123456789 是旧的",
    "旧令牌 sk-abcdefgh12345678 早就该换",
    "有事找我 someone@example.com",
  ].join("\n");
  const out = F.redact(raw);
  assert.ok(out.redactions >= 5, "命中数应当 >= 5，实得 " + out.redactions);
  assert.ok(out.text.indexOf("BEGIN RSA PRIVATE KEY") < 0, "私钥块没被吃掉");
  assert.ok(out.text.indexOf("ADMIN") < 0, "Windows 路径没被吃掉");
  assert.ok(out.text.indexOf("AbCdEf0123456789") < 0, "api_key 值没被吃掉");
  assert.ok(out.text.indexOf("sk-abcdefgh12345678") < 0, "sk- 前缀令牌没被吃掉");
  assert.ok(out.text.indexOf("someone@example.com") < 0, "邮箱没被吃掉");
  const names = out.rules.join(",");
  ["private_key_block", "windows_path", "credential_kv", "prefixed_secret", "email"].forEach((r) => {
    assert.ok(names.indexOf(r) >= 0, "规则 " + r + " 没在命中名单里：" + names);
  });
  assert.ok(out.text.indexOf(F.REDACT_PLACEHOLDER) >= 0, "占位符没上屏");
});

test("2. 负对照：正常中文文本零命中、逐字不变（与用例 1 判别）", () => {
  const clean = "今天天气不错，土豆公主在写代码，朋友圈里都是正经内容。";
  const out = F.redact(clean);
  assert.strictEqual(out.redactions, 0, "正常文本被误伤，命中 " + out.redactions + " 次");
  assert.deepStrictEqual(out.rules, [], "正常文本被误判进规则名单：" + out.rules.join(","));
  assert.strictEqual(out.text, clean, "正常文本被改动过 —— 脱敏层不许动干净内容");
  /* 判别性：干净文本与用例 1 的脏文本结果必须不同，否则两条用例都在空转 */
  assert.notStrictEqual(out.redactions, F.redact("api_key=AbCdEf0123456789").redactions);
});

test("3. clip 截断加省略号 / toIso 秒与毫秒都吃、坏值报 null", () => {
  assert.strictEqual(F.clip("abcdef", 3), "abc…", "超长未截断");
  assert.strictEqual(F.clip("abc", 3), "abc", "未超长不该动");
  assert.strictEqual(F.clip(null, 3), "", "null 应当当空串");

  const sec = F.toIso(1700000000);
  const ms = F.toIso(1700000000000);
  assert.strictEqual(sec, ms, "秒与毫秒两种单位应当落到同一时刻");
  assert.strictEqual(F.toIso(0), null, "0 不是合法时间戳");
  assert.strictEqual(F.toIso("不是时间"), null, "非数字应当报 null，不许编一个时间");
});

/* ── 二 · 归一化：值永不回显 ── */

test("4. normalizeProfile：邮箱只出布尔，值本身永不回显（判别性断言）", () => {
  const raw = {
    agent_name: "土豆",
    agent_id: "agent-001",
    email: "owner@example.com",
    bio: "联系我 C:\\Users\\ADMIN\\secret 或 sk-abcdefgh12345678",
  };
  const out = F.normalizeProfile(raw);
  assert.strictEqual(out.agent_name, "土豆");
  assert.strictEqual(out.email_bound, true, "绑了邮箱却没报 true");
  const dump = JSON.stringify(out);
  assert.ok(dump.indexOf("owner@example.com") < 0, "邮箱值回显了 —— 只许出布尔");
  assert.ok(dump.indexOf("ADMIN") < 0, "bio 里的绝对路径回显了");
  assert.ok(dump.indexOf("sk-abcdefgh") < 0, "bio 里的令牌回显了");
  assert.ok(out.redactions >= 2, "bio 命中数应当 >= 2，实得 " + out.redactions);

  /* 判别性：没绑邮箱的人必须报 false —— 若是恒 true，这条用例什么也没证明 */
  const bare = F.normalizeProfile({ agent_name: "甲", email: "" });
  assert.strictEqual(bare.email_bound, false, "没邮箱却报已绑定");
  assert.notStrictEqual(bare.email_bound, out.email_bound);
});

test("5. normalizeFeedItem / normalizeMessage / normalizeFriend：脱敏 + 截断到限长", () => {
  const item = F.normalizeFeedItem({
    item_id: "i1", display_name: "某某", author_agent_id: "a9", author_relation: "friend",
    broadcast_type: "post", created_at: 1700000000, domains: ["ai", "design"],
    keywords: ["k1"], expected_response: "求点评",
    raw_content: "x".repeat(900) + " C:\\Users\\ADMIN\\leak",
    raw_content_truncated: true,
  });
  assert.ok(item.content.length <= F.LIMITS.content_chars + 1, "正文没截断：" + item.content.length);
  assert.ok(item.content.indexOf("ADMIN") < 0, "正文里的绝对路径没脱敏");
  assert.strictEqual(item.truncated_at_source, true, "源自带截断标记应当如实带出来");
  assert.deepStrictEqual(item.domains, ["ai", "design"]);

  const msg = F.normalizeMessage({
    msg_id: "m1", conv_id: "c1", sender_id: "s1", sender_name: "乙",
    content: "密件 -----BEGIN OPENSSH PRIVATE KEY----- AAA -----END OPENSSH PRIVATE KEY-----",
    created_at: 1700000000000, sender_is_official: true,
  });
  assert.ok(msg.content.indexOf("PRIVATE KEY-----") < 0, "私信里的私钥块没脱敏");
  assert.strictEqual(msg.is_official, true);
  assert.strictEqual(msg.created_at, F.toIso(1700000000000));

  const friend = F.normalizeFriend({ agent_id: "f1", agent_name: "丙", remark: "见 someone@example.com", friend_since: 1700000000 });
  assert.ok(friend.remark.indexOf("someone@example.com") < 0, "备注里的邮箱没脱敏");
  assert.ok(friend.redactions >= 1, "备注命中数没报");
});

/* ── 三 · 私信合并 ── */

test("6. mergeMessages：按 msg_id 去重 + 时间倒序 + 截断（判别性：不去重会多出 1 条）", () => {
  const a = { msg_id: "a", created_at: 1000, content: "一" };
  const b = { msg_id: "b", created_at: 2000, content: "二" };
  const c = { msg_id: "c", created_at: 3000, content: "三" };

  const merged = F.mergeMessages([[a, b], [b, c]]);
  assert.strictEqual(merged.length, 3, "重复的 b 没有被去掉：实得 " + merged.length + " 条（不去重会是 4）");
  assert.deepStrictEqual(merged.map((m) => m.msg_id), ["c", "b", "a"], "不是时间倒序");

  const capped = F.mergeMessages([[a, b], [b, c]], { messages: 1 });
  assert.strictEqual(capped.length, 1, "限长没生效");
  assert.strictEqual(capped[0].msg_id, "c", "限长后留下的不是最新那条");

  /* 没有 msg_id 的行按 (sender, created_at, content) 兜底去重 —— 不许因为缺 id 就全留 */
  const noId = F.mergeMessages([[[{ sender_id: "s", created_at: 5, content: "同" }]],
                                [[{ sender_id: "s", created_at: 5, content: "同" }]]]);
  assert.strictEqual(noId.length, 1, "缺 msg_id 的重复行没被兜底去重");
});

/* ── 四 · 形象库真扫盘 ── */

function fakeFs(tree) {
  return {
    existsSync: (p) => Object.prototype.hasOwnProperty.call(tree, p),
    readdirSync: (p) => {
      if (!tree[p]) throw new Error("ENOENT");
      return tree[p].children || [];
    },
    statSync: (p) => {
      const n = tree[p];
      if (!n) throw new Error("ENOENT");
      return { isDirectory: () => n.dir === true, size: n.size || 0 };
    },
  };
}

test("7. scanPetResources：齐件绿 / 缺贴图红 / 缺 moc3 红，三种结果互不相同", () => {
  const ROOTD = path.join("R", "resources");
  const full = path.join(ROOTD, "haru");
  const noTex = path.join(ROOTD, "nn");
  const noMoc = path.join(ROOTD, "bad");
  const tree = {};
  tree[ROOTD] = { dir: true, children: ["haru", "nn", "bad"] };
  tree[full] = { dir: true, children: ["haru.model3.json", "haru.moc3", "haru.2048"] };
  tree[path.join(full, "haru.model3.json")] = { size: 100 };
  tree[path.join(full, "haru.moc3")] = { size: 200 };
  tree[path.join(full, "haru.2048")] = { dir: true, children: ["t.png", "u.png"] };
  tree[noTex] = { dir: true, children: ["nn.model3.json", "nn.moc3"] };
  tree[path.join(noTex, "nn.model3.json")] = { size: 10 };
  tree[path.join(noTex, "nn.moc3")] = { size: 20 };
  tree[noMoc] = { dir: true, children: ["bad.model3.json"] };
  tree[path.join(noMoc, "bad.model3.json")] = { size: 5 };

  const rows = F.scanPetResources(fakeFs(tree), ROOTD);
  const by = {};
  rows.forEach((r) => { by[r.name] = r; });
  assert.strictEqual(rows.length, 3, "应当扫出 3 个形象，实得 " + rows.length);

  assert.strictEqual(by.haru.ready, true, "齐件形象被判不就绪");
  assert.deepStrictEqual(by.haru.issues, [], "齐件形象不该有 issues");
  assert.strictEqual(by.haru.textures, 2, "贴图数没数对");
  assert.strictEqual(by.haru.bytes, 300, "model3 + moc3 字节数没累加对");

  assert.strictEqual(by.nn.ready, false, "缺贴图形象被判就绪");
  assert.ok(by.nn.issues.join("|").indexOf("无贴图目录") >= 0, "缺贴图的 reason 没报出来：" + by.nn.issues.join("|"));

  assert.strictEqual(by.bad.ready, false, "缺 moc3 形象被判就绪");
  assert.ok(by.bad.issues.join("|").indexOf("moc3") >= 0, "缺 moc3 的 reason 没报出来：" + by.bad.issues.join("|"));

  /* 判别性：三种结果必须互不相同，否则这条用例只是在数数 */
  assert.notDeepStrictEqual(by.haru.issues, by.nn.issues);
  assert.notDeepStrictEqual(by.nn.issues, by.bad.issues);

  /* 负对照：目录不存在时报空数组，不许凭默认值编出形象 */
  assert.deepStrictEqual(F.scanPetResources(fakeFs({}), ROOTD), [], "目录不存在时不该编出形象");
});

/* ── 五 · 就绪表与召唤计划 ── */

test("8. buildCarriers：就绪态可判别、未探测就说未探测、取不到一律不显绿", () => {
  const unProbed = F.buildCarriers({ electronPresent: false, panelReachable: false, models: 4 });
  assert.strictEqual(unProbed.primary, null, "两条腿都不就绪时不许给 primary");
  assert.strictEqual(unProbed.carriers.length, 2, "载体会话应当固定两条腿");
  const pet = unProbed.carriers.filter((c) => c.id === "live2d-pet")[0];
  assert.strictEqual(pet.ready, false, "未探测的腿被判就绪 —— 这就是猜");
  assert.ok(pet.reason.indexOf("未探测") >= 0, "未探测的腿必须如实说未探测，实得：" + pet.reason);
  const shell0 = unProbed.carriers.filter((c) => c.id === "desktop-shell")[0];
  assert.ok(shell0.reason.indexOf("Electron") >= 0, "缺 Electron 的原因没报：" + shell0.reason);

  const shellOk = F.buildCarriers({
    electronPresent: true, panelReachable: true, electronBytes: 235706368, models: 4,
  });
  assert.strictEqual(shellOk.primary, "desktop-shell", "两条件都满足却没选桌面壳");
  assert.strictEqual(shellOk.carriers[0].ready, true);
  assert.ok(shellOk.carriers[0].note.indexOf("225 MB") >= 0, "运行时体量没报：" + shellOk.carriers[0].note);

  const panelDown = F.buildCarriers({ electronPresent: true, panelReachable: false });
  assert.strictEqual(panelDown.primary, null, "面板没起来却给了 primary —— 会起出一个白页");
  assert.ok(panelDown.carriers[0].reason.indexOf("8765") >= 0, "面板未就绪的原因没报出端口");

  const pyOk = F.buildCarriers({ python: { checked: true, pyside6: true, live2d: true, interpreter: "py -3.10" } });
  assert.strictEqual(pyOk.primary, "live2d-pet", "Python 腿就绪时应当可当主载体");
  const pyBad = F.buildCarriers({ python: { checked: true, pyside6: false, live2d: false } });
  assert.ok(pyBad.carriers[1].reason.indexOf("PySide6") >= 0, "缺依赖没点名：" + pyBad.carriers[1].reason);
  assert.notStrictEqual(pyOk.primary, pyBad.carriers[1].ready);
});

test("9. summonPlan：三种载体出对命令，未知载体与缺仓库根必须红", () => {
  const shell = F.summonPlan({ carrier: "desktop-shell", repoRoot: "R", electronExe: "E" });
  assert.strictEqual(shell.ok, true);
  assert.strictEqual(shell.exe, "E");
  assert.deepStrictEqual(shell.argv, [path.join("R", "holo_pet", "desktop", "main.cjs")]);
  assert.strictEqual(shell.cwd, path.join("R", "holo_pet"));
  assert.strictEqual(shell.detached, true, "召唤必须脱离父进程，否则壳一退数字人跟着死");

  const pet = F.summonPlan({ carrier: "live2d-pet", repoRoot: "R" });
  assert.strictEqual(pet.ok, true);
  assert.strictEqual(pet.exe, "py");
  assert.deepStrictEqual(pet.argv, ["-3.10", path.join("R", "potato_pet", "main.py")]);

  const unknown = F.summonPlan({ carrier: "没这回事", repoRoot: "R" });
  assert.strictEqual(unknown.ok, false, "未知载体必须红 —— 不许回落到随便一条腿");
  assert.ok(unknown.reason.indexOf("未知载体") >= 0, "未知载体的 reason 没报：" + unknown.reason);

  const noRoot = F.summonPlan({ carrier: "desktop-shell", electronExe: "E" });
  assert.strictEqual(noRoot.ok, false, "缺仓库根必须红");
  assert.ok(noRoot.reason.indexOf("仓库根") >= 0, "缺仓库根的 reason 没报：" + noRoot.reason);

  const noExe = F.summonPlan({ carrier: "desktop-shell", repoRoot: "R" });
  assert.strictEqual(noExe.ok, false, "缺 Electron 运行时必须红");
  assert.notStrictEqual(shell.ok, unknown.ok);
});

test("10. isAlive：ESRCH / 非法 pid 一律当不在（失败方向安全）", () => {
  assert.strictEqual(F.isAlive(0), false, "pid 0 应当当不在");
  assert.strictEqual(F.isAlive(-1), false, "负 pid 应当当不在");
  assert.strictEqual(F.isAlive("不是数字"), false, "非数字 pid 应当当不在");
  assert.strictEqual(F.isAlive(1234, () => {}), true, "不抛错应当当活着");
  assert.strictEqual(F.isAlive(1234, () => { throw new Error("ESRCH"); }), false, "抛错应当当不在");
  assert.notStrictEqual(F.isAlive(1234, () => {}), F.isAlive(1234, () => { throw new Error("ESRCH"); }));
});

test("11. 本机路径与最新文件选取", () => {
  assert.strictEqual(F.resolveHome({}, "C:\\Users\\X"), path.join("C:\\Users\\X", ".eigenflux"));
  assert.strictEqual(F.resolveHome({ EIGENFLUX_HOME: "D:\\ef" }, "C:\\Users\\X"), "D:\\ef",
                     "显式 EIGENFLUX_HOME 没被尊重");
  assert.strictEqual(F.homeLabel("D:\\ef"), "ef");
  assert.strictEqual(F.homeLabel(""), "(未解析)");

  const p = F.eigenfluxPaths("H", "eigenflux");
  assert.strictEqual(p.profile, path.join("H", "servers", "eigenflux", "profile.json"));
  assert.strictEqual(p.contacts, path.join("H", "servers", "eigenflux", "contacts.json"));
  assert.strictEqual(p.broadcasts, path.join("H", "servers", "eigenflux", "data", "broadcasts"));
  assert.strictEqual(F.eigenfluxPaths("H").profile.indexOf("eigenflux") >= 0, true,
                     "缺省 server 名应当是 eigenflux");

  const rows = [{ name: "旧", mtimeMs: 10 }, { name: "新", mtimeMs: 20 }];
  assert.strictEqual(F.pickLatest(rows).name, "新", "没按 mtime 取最新");
  assert.strictEqual(F.pickLatest([]), null, "空列表应当给 null");
  assert.notStrictEqual(F.pickLatest(rows).name, rows[0].name);
});

/* ── 六 · 这块牌子本身 ── */

test("12. 纯函数层契约：features.cjs 零 electron / 零子进程 / 零网络", () => {
  const MAIN = fs.readFileSync(path.join(SHELL, "main.cjs"), "utf8");
  const probes = [
    /require\("electron"\)/,
    /require\("child_process"\)/,
    /fetch\(/,
    /writeFileSync/,
    /spawn\(/,
  ];

  /* 自伤留档（写这条用例时连踩两脚，都是用例侧，不是被判对象侧）：
   *   ① 初版拿 main.cjs 当**全部 5 条**探针的负对照，但 main.cjs 只 require 了
   *      electron + child_process，既没有 fetch(/writeFileSync/spawn(，于是负对照自己先红
   *      —— 用例断言了一个被判对象不成立的不变量。
   *   ② 修完①之后，探针在 features.cjs 上仍然命中 —— 因为 features.cjs 的**注释里**
   *      写着「shell/main.cjs 顶部就 require("electron")」。纯文本扫描把注释当真代码。
   * 修法：拆两层 —— 先剥注释再扫（对"代码"断言，不对"文本"断言），
   *       合成样本证明「正则本身不瞎」，main.cjs 只点名它确实有的两条。 */
  const stripComments = (src) => String(src)
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1 ");

  const SAMPLE = 'const { app } = require("electron");' +
    'const { spawn } = require("child_process");' +
    'fetch("http://127.0.0.1/x"); fs.writeFileSync("a", "b"); spawn("x");';
  probes.forEach((re) => {
    assert.ok(re.test(SAMPLE), "探针 " + re.source + " 在合成样本上零命中 —— 正则本身是死的，本用例无意义");
  });

  /* 剥注释层自己的正负对照：注释里的 require 必须被剥掉，真代码里的必须留着 */
  const NOTE_ONLY = '// const { app } = require("electron");';
  assert.strictEqual(probes[0].test(stripComments(NOTE_ONLY)), false,
                     "剥注释层没牙：注释里的 require 仍被当真代码");
  assert.strictEqual(probes[0].test(stripComments(SAMPLE)), true,
                     "剥注释层剥过头：真代码里的 require 也被剥掉了");

  const CODE = stripComments(SRC);
  const CODE_MAIN = stripComments(MAIN);
  assert.ok(probes[0].test(CODE_MAIN) && probes[1].test(CODE_MAIN),
            "main.cjs 剥注释后没同时命中 electron / child_process —— 拿它当对照的前提不成立");
  probes.forEach((re) => {
    assert.ok(!re.test(CODE), "features.cjs 的**代码**命中 " + re.source + " —— 纯函数层的牌子破了");
  });
  assert.ok(SRC.indexOf('"use strict"') >= 0, "features.cjs 缺 use strict");
});
