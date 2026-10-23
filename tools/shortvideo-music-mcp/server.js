#!/usr/bin/env node
/**
 * shortvideo-music-workflow MCP server (zero-dependency, stdio)
 *
 * Tools:
 *   doctor          - environment check (node/ffmpeg/arkcli auth/keys, keys masked)
 *   plan_workflow   - deterministic short-video blueprint (scenes/prompts/subtitles/music brief)
 *   generate_video  - arkcli +gen video (BILLED - requires arkcli auth)
 *   generate_image  - arkcli +gen image (BILLED - requires arkcli auth)
 *   generate_music  - fal.ai music queue API (requires FAL_KEY, not configured = honest error)
 *   tts_voiceover   - Windows SAPI TTS to wav (offline, free; also listVoices)
 *   mix_audio       - ffmpeg mixing: volume/fade/voice-ducking
 *   burn_subtitles  - ffmpeg subtitles filter (.srt/.ass)
 *   assemble_video  - ffmpeg mux video+audio, -shortest / duration
 */
"use strict";

const { exec } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const SERVER_INFO = { name: "shortvideo-music-workflow", version: "0.1.0" };
const SUPPORTED_PROTOCOLS = new Set(["2025-06-18", "2024-11-05"]);

/* ---------------- helpers ---------------- */

function send(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
}

function execP(cmd, opts = {}) {
  return new Promise((resolve) => {
    exec(
      cmd,
      {
        windowsHide: true,
        timeout: opts.timeout || 120000,
        maxBuffer: 64 * 1024 * 1024,
        cwd: opts.cwd,
        env: { ...process.env, ...(opts.env || {}) },
      },
      (err, stdout, stderr) => {
        resolve({
          ok: !err,
          code: err ? (err.code == null ? 1 : err.code) : 0,
          killed: err ? Boolean(err.killed) : false,
          stdout: (stdout || "").toString(),
          stderr: (stderr || "").toString(),
        });
      }
    );
  });
}

function shq(s) {
  // quote for cmd.exe double-quote context; forbid embedded quotes
  // 🔴 2026-09-26 修：cmd.exe 在双引号内照样展开 %VAR%，prompt/路径里的 % 会被静默替换成
  //    环境变量值再传给 arkcli/ffmpeg（参数篡改面）。% 在合法输入里罕见，直接剔除。
  const clean = String(s).replace(/["\r\n%]/g, " ").trim();
  return `"${clean}"`;
}

function maskKey(v) {
  if (!v) return null;
  return v.slice(0, 4) + "****(configured)";
}

function mustExist(p, label) {
  if (!p || !fs.existsSync(p)) {
    throw new Error(`${label || "文件"}不存在: ${p}`);
  }
  return p;
}

function outDir(p) {
  const d = path.dirname(path.resolve(p));
  fs.mkdirSync(d, { recursive: true });
  return p;
}

function textResult(text, isError = false) {
  return { content: [{ type: "text", text }], isError };
}

function jsonResult(obj, isError = false) {
  return textResult(JSON.stringify(obj, null, 2), isError);
}

/* ---------------- tool implementations ---------------- */

async function toolDoctor() {
  const r = {};
  r.node = (await execP("node --version")).stdout.trim() || null;
  const ff = await execP("ffmpeg -version");
  r.ffmpeg = ff.ok ? ff.stdout.split("\n")[0].trim() : null;
  r.arkcli = (await execP("arkcli --version")).stdout.trim() || null;
  const auth = await execP("arkcli auth status --format json", { timeout: 60000 });
  let authParsed = null;
  try { authParsed = JSON.parse(auth.stdout); } catch { /* keep raw */ }
  r.arkcliAuth = auth.ok && authParsed
    ? authParsed
    : { ok: auth.ok, note: "unparsed", raw: (auth.stdout + auth.stderr).slice(0, 300) };
  r.keys = {
    ARK_API_KEY: maskKey(process.env.ARK_API_KEY),
    FAL_KEY: maskKey(process.env.FAL_KEY),
    VENICE_API_KEY: maskKey(process.env.VENICE_API_KEY),
  };
  r.musicChannel = process.env.FAL_KEY
    ? "fal.ai queue API (available)"
    : "未接线：需要 FAL_KEY（venice 备选），当前如实不可用";
  // 🔴 2026-09-26 修：原三元在 arkcli 未安装（r.arkcli=null）时整体 falsy 落进 else，
  //    把"缺失"谎报成"可用"—— doctor 的本分是如实报告。三种状态分开报。
  r.videoChannel = !r.arkcli
    ? "未接线：arkcli 未安装 —— 视频/图片生成当前不可用"
    : (r.arkcliAuth && r.arkcliAuth.authenticated
      ? "arkcli 视频/图片生成（计费）"
      : "arkcli 已装但未登录：生成类调用会被拒绝（需 arkcli auth login）");
  return r;
}

async function toolPlanWorkflow(args) {
  const topic = String(args.topic || "").trim();
  if (!topic) throw new Error("topic 必填：一句话主题");
  const durationSec = Math.max(5, Math.min(600, Number(args.durationSec) || 30));
  const sceneCount = Math.max(1, Math.min(12, Number(args.sceneCount) || 3));
  const ratio = String(args.ratio || "9:16");
  const style = String(args.style || "电影感、节奏快、高对比");

  const per = Math.floor((durationSec / sceneCount) * 10) / 10;
  const scenes = [];
  for (let i = 0; i < sceneCount; i++) {
    const start = Math.round(i * per * 10) / 10;
    scenes.push({
      index: i + 1,
      startSec: start,
      durationSec: per,
      videoPrompt: `${topic}，${style}，镜头 ${i + 1}/${sceneCount}，竖屏构图 ${ratio}，动态感强，无文字水印`,
      subtitle: `${topic}（第${i + 1}段字幕，替换成口播文案）`,
    });
  }
  return {
    topic,
    durationSec,
    ratio,
    scenes,
    music: {
      durationSec,
      brief: `${topic} 氛围 BGM，${style}，纯音乐无人声，尾部 2 秒淡出`,
      channel: process.env.FAL_KEY ? "generate_music 可用" : "generate_music 需要 FAL_KEY（未配）",
    },
    voiceover: {
      engine: "tts_voiceover（Windows SAPI，离线免费，音质一般，正式成片建议真人/云 TTS）",
      estChars: Math.round(durationSec * 4.5),
    },
    pipeline: [
      "generate_video ×" + sceneCount + "（或 generate_image 做封面）",
      "generate_music 出 BGM",
      "tts_voiceover 出口播",
      "mix_audio 混音（BGM 自动闪避人声）",
      "assemble_video 合成",
      "burn_subtitles 烧字幕",
    ],
  };
}

async function toolGenerateVideo(args) {
  const prompt = String(args.prompt || "").trim();
  if (!prompt) throw new Error("prompt 必填");
  const dur = Math.max(1, Math.min(60, Number(args.duration) || 5));
  const ratio = String(args.ratio || "9:16");
  const resolution = String(args.resolution || "720p");
  const wait = args.wait !== false;
  const saveTo = args.saveTo ? path.resolve(args.saveTo) : process.cwd();
  fs.mkdirSync(saveTo, { recursive: true });

  const parts = [
    "arkcli +gen", shq(prompt),
    "--modality video",
    `--duration ${dur}`,
    `--ratio ${shq(ratio)}`,
    `--resolution ${shq(resolution)}`,
    `--save-to ${shq(saveTo)}`,
    "--no-open",
  ];
  if (args.model) parts.push(`--model ${shq(args.model)}`);
  if (args.inputRefs && args.inputRefs.length) {
    for (const ref of args.inputRefs.slice(0, 4)) {
      mustExist(ref.startsWith("@") ? ref.slice(1) : ref, "参考素材");
      parts.push(`--input ${shq(ref)}`);
    }
  }
  if (wait) parts.push("--wait");
  if (args.draft) parts.push("--draft");

  const r = await execP(parts.join(" "), { timeout: wait ? 600000 : 90000 });
  let parsed = null;
  try { parsed = JSON.parse(r.stdout); } catch { /* raw */ }
  return {
    ok: r.ok,
    billed: true,
    note: "视频生成按量计费（BytePlus ModelArk）。若失败多为未登录或额度问题。",
    task: parsed || null,
    raw: (r.stdout + "\n" + r.stderr).slice(0, 4000),
  };
}

async function toolGenerateImage(args) {
  const prompt = String(args.prompt || "").trim();
  if (!prompt) throw new Error("prompt 必填");
  const saveTo = args.saveTo ? path.resolve(args.saveTo) : process.cwd();
  fs.mkdirSync(saveTo, { recursive: true });

  const parts = [
    "arkcli +gen", shq(prompt),
    "--modality image",
    `--save-to ${shq(saveTo)}`,
    "--no-open",
  ];
  if (args.model) parts.push(`--model ${shq(args.model)}`);
  if (args.size) parts.push(`--size ${shq(args.size)}`);
  if (args.count && Number(args.count) > 1) parts.push(`--image-count ${Number(args.count)}`);

  const r = await execP(parts.join(" "), { timeout: 300000 });
  let parsed = null;
  try { parsed = JSON.parse(r.stdout); } catch { /* raw */ }
  return {
    ok: r.ok,
    billed: true,
    result: parsed || null,
    raw: (r.stdout + "\n" + r.stderr).slice(0, 4000),
  };
}

async function falMusic(args) {
  const key = process.env.FAL_KEY;
  if (!key) {
    return {
      ok: false,
      needsDependency: true,
      message: "音乐生成需要 FAL_KEY（fal.ai）。当前未配置，本工具如实拒绝执行。配置后在 env 里注入 FAL_KEY 即可用。",
    };
  }
  const prompt = String(args.prompt || "").trim();
  if (!prompt) throw new Error("prompt 必填：音乐描述，如 epic cinematic trailer music");
  const seconds = Math.max(5, Math.min(300, Number(args.durationSec) || 30));
  const model = String(args.model || "fal-ai/stable-audio");

  const submit = await fetch(`https://queue.fal.run/${model}`, {
    method: "POST",
    headers: { Authorization: `Key ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, seconds_total: seconds }),
  });
  const sub = await submit.json();
  if (!submit.ok) return { ok: false, stage: "submit", status: submit.status, body: sub };

  const statusUrl = sub.status_url;
  const responseUrl = sub.response_url;
  const deadline = Date.now() + 5 * 60 * 1000;
  let status = null;
  while (Date.now() < deadline) {
    await new Promise((res) => setTimeout(res, 4000));
    const st = await fetch(statusUrl, { headers: { Authorization: `Key ${key}` } });
    status = await st.json();
    if (status.status === "COMPLETED") break;
    if (status.status === "FAILED") return { ok: false, stage: "run", status };
  }
  if (!status || status.status !== "COMPLETED") {
    return { ok: false, stage: "timeout", lastStatus: status };
  }
  const fin = await fetch(responseUrl, { headers: { Authorization: `Key ${key}` } });
  const out = await fin.json();
  const url = out && out.audio && (out.audio.url || out.audio_file && out.audio_file.url);
  return { ok: true, billed: true, audioUrl: url || null, raw: out };
}

async function toolGenerateMusic(args) {
  return falMusic(args);
}

async function sapiVoices() {
  const r = await execP(
    `powershell -NoProfile -Command "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name + '|' + $_.VoiceInfo.Culture }"`
  );
  return r.stdout.trim().split("\n").map((l) => l.trim()).filter(Boolean);
}

async function toolTts(args) {
  if (args.listVoices) {
    return { ok: true, voices: await sapiVoices() };
  }
  const text = String(args.text || "").trim();
  if (!text) throw new Error("text 必填（或传 listVoices=true 列出可用音色）");
  const out = outDir(path.resolve(String(args.outFile || path.join(process.cwd(), "voiceover.wav"))));
  if (!/\.wav$/i.test(out)) throw new Error("outFile 必须是 .wav");
  const voice = args.voice ? String(args.voice) : null;
  const rate = Math.max(-10, Math.min(10, Number(args.rate) || 0));

  const ps = [
    "Add-Type -AssemblyName System.Speech",
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
    voice ? `$s.SelectVoice('${String(voice).replace(/'/g, "")}')` : null,
    `$s.Rate = ${rate}`,
    "$s.SetOutputToWaveFile($env:TTS_OUT)",
    "$s.Speak($env:TTS_TEXT)",
    "$s.Dispose()",
    "Write-Output 'TTS_OK'",
  ].filter(Boolean).join("; ");

  const r = await execP(`powershell -NoProfile -Command ${shq(ps)}`, {
    timeout: 180000,
    env: { TTS_TEXT: text, TTS_OUT: out },
  });
  const ok = r.ok && r.stdout.includes("TTS_OK") && fs.existsSync(out);
  return { ok, outFile: ok ? out : null, engine: "Windows SAPI", raw: (r.stderr || "").slice(0, 800) };
}

async function toolMixAudio(args) {
  const tracks = Array.isArray(args.tracks) ? args.tracks : [];
  if (tracks.length < 2) throw new Error("至少需要 2 条音轨 tracks:[{path, kind:music|voice, volume?, fadeOutSec?}]");
  const out = outDir(path.resolve(String(args.outFile || "mixed.wav")));
  const ducking = Boolean(args.ducking);

  const inputs = tracks.map((t) => `-i ${shq(path.resolve(t.path))}`).join(" ");
  const filters = [];
  const labels = [];

  tracks.forEach((t, i) => {
    const vol = Math.max(0, Math.min(2, Number(t.volume != null ? t.volume : (t.kind === "music" ? 0.35 : 1.0))));
    let chain = `[${i}:a]`;
    const ch = [];
    if (vol !== 1) ch.push(`volume=${vol}`);
    if (t.fadeOutSec) {
      const dur = Number(t.durationSec) || 60;
      ch.push(`afade=t=out:st=${Math.max(0, dur - Number(t.fadeOutSec))}:d=${Number(t.fadeOutSec)}`);
    }
    filters.push(chain + (ch.length ? ch.join(",") : "anull") + `[a${i}]`);
    labels.push(`[a${i}]`);
  });

  let filterComplex;
  if (ducking) {
    const mi = tracks.findIndex((t) => t.kind === "music");
    const vi = tracks.findIndex((t) => t.kind === "voice");
    if (mi < 0 || vi < 0) throw new Error("ducking=true 需要 kind=music 与 kind=voice 各至少一条");
    filters.push(`[a${mi}][a${vi}]sidechaincompress=threshold=0.03:ratio=8:attack=60:release=500[mduck]`);
    filterComplex = filters.join(";") + `;[mduck][a${vi}]amix=inputs=2:duration=longest:normalize=0[out]`;
  } else {
    filterComplex = filters.join(";") + `;${labels.join("")}amix=inputs=${tracks.length}:duration=longest:normalize=0[out]`;
  }

  const cmd = `ffmpeg -y ${inputs} -filter_complex ${shq(filterComplex)} -map ${shq("[out]")} ${shq(out)}`;
  const r = await execP(cmd, { timeout: 300000, cwd: path.dirname(out) });
  return { ok: r.ok, outFile: r.ok ? out : null, ducking, cmd, stderr: r.stderr.slice(-1500) };
}

async function toolBurnSubtitles(args) {
  const video = mustExist(args.video, "视频");
  const subs = mustExist(args.subtitles, "字幕文件（.srt/.ass）");
  const out = outDir(path.resolve(String(args.outFile || "")));
  const font = String(args.font || "Microsoft YaHei").replace(/'/g, "");
  const fontSize = Math.max(8, Math.min(72, Number(args.fontSize) || 14));
  const marginV = Math.max(0, Math.min(400, Number(args.marginV) || 40));

  // work in the video's directory so subtitles filter gets a relative path (no Windows colon escaping)
  const dir = path.dirname(video);
  const subAbs = path.resolve(subs);
  const subLocal = path.basename(subAbs);
  if (path.dirname(subAbs) !== dir) fs.copyFileSync(subAbs, path.join(dir, subLocal));

  const style = `FontName=${font},FontSize=${fontSize},MarginV=${marginV},Outline=1,Shadow=0`;
  const vf = `subtitles='${subLocal}':force_style='${style}'`;
  const cmd = `ffmpeg -y -i ${shq(path.basename(video))} -vf ${shq(vf)} -c:a copy ${shq(path.basename(out))}`;
  const r = await execP(cmd, { timeout: 600000, cwd: dir });
  return { ok: r.ok, outFile: r.ok ? out : null, cmd, stderr: r.stderr.slice(-1500) };
}

async function toolAssembleVideo(args) {
  const video = mustExist(args.video, "视频");
  const audio = mustExist(args.audio, "音频");
  const out = outDir(path.resolve(String(args.outFile || "")));
  const dir = path.dirname(video);
  const audioLocal = path.basename(path.resolve(audio)) === path.basename(audio)
    ? path.basename(audio)
    : path.basename(audio);
  if (path.dirname(path.resolve(audio)) !== dir) fs.copyFileSync(path.resolve(audio), path.join(dir, audioLocal));

  const parts = [`ffmpeg -y -i ${shq(path.basename(video))} -i ${shq(audioLocal)}`];
  parts.push("-map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k");
  if (args.durationSec) parts.push(`-t ${Number(args.durationSec)}`);
  parts.push("-shortest");
  parts.push(shq(path.basename(out)));
  const cmd = parts.join(" ");
  const r = await execP(cmd, { timeout: 600000, cwd: dir });
  return { ok: r.ok, outFile: r.ok ? out : null, cmd, stderr: r.stderr.slice(-1500) };
}

/* ---------------- tool registry ---------------- */

const TOOLS = [
  {
    name: "doctor",
    description: "体检：node/ffmpeg/arkcli 版本与登录态、各密钥是否配置（只报前4位掩码，不泄明文）。只读、免费。",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
  },
  {
    name: "plan_workflow",
    description: "输入主题，产出短视频分镜蓝图：每镜头时长/视频生成提示词/字幕文案位/BGM 简报/口播字数估算/流水线顺序。纯本地计算、免费。",
    inputSchema: {
      type: "object",
      properties: {
        topic: { type: "string", description: "一句话主题" },
        durationSec: { type: "number", description: "总时长秒，默认30" },
        sceneCount: { type: "number", description: "镜头数，默认3" },
        ratio: { type: "string", description: "画幅，默认9:16" },
        style: { type: "string", description: "风格描述" },
      },
      required: ["topic"],
    },
  },
  {
    name: "generate_video",
    description: "⚠️计费：arkcli 调 BytePlus ModelArk 生成视频（Seedance 等）。需 arkcli 已登录。支持参考图、时长/画幅/分辨率、--wait 阻塞等待。",
    inputSchema: {
      type: "object",
      properties: {
        prompt: { type: "string" },
        duration: { type: "number", description: "秒，默认5" },
        ratio: { type: "string", description: "默认9:16" },
        resolution: { type: "string", description: "默认720p" },
        model: { type: "string", description: "模型名或endpoint，留空用profile默认" },
        saveTo: { type: "string", description: "保存目录" },
        wait: { type: "boolean", description: "默认true阻塞到完成" },
        draft: { type: "boolean", description: "草稿模式：更快更便宜画质低" },
        inputRefs: { type: "array", items: { type: "string" }, description: "参考素材路径或URL，最多4个" },
      },
      required: ["prompt"],
    },
  },
  {
    name: "generate_image",
    description: "⚠️计费：arkcli 调 BytePlus ModelArk 生成图片（Seedream 等），返回URL并存本地。",
    inputSchema: {
      type: "object",
      properties: {
        prompt: { type: "string" },
        model: { type: "string" },
        size: { type: "string", description: "如 1024x1024" },
        count: { type: "number" },
        saveTo: { type: "string" },
      },
      required: ["prompt"],
    },
  },
  {
    name: "generate_music",
    description: "⚠️计费：fal.ai 生成音乐（默认 fal-ai/stable-audio）。需要环境变量 FAL_KEY；未配置时如实拒绝并说明，不会假装成功。",
    inputSchema: {
      type: "object",
      properties: {
        prompt: { type: "string", description: "音乐描述" },
        durationSec: { type: "number", description: "默认30，5-300" },
        model: { type: "string", description: "默认 fal-ai/stable-audio" },
      },
      required: ["prompt"],
    },
  },
  {
    name: "tts_voiceover",
    description: "Windows SAPI 离线TTS 出 .wav 口播（免费、无密钥；音质一般）。listVoices=true 可列出已装音色。",
    inputSchema: {
      type: "object",
      properties: {
        text: { type: "string" },
        outFile: { type: "string", description: "必须.wav" },
        voice: { type: "string", description: "音色名，如 Microsoft Huihui Desktop" },
        rate: { type: "number", description: "-10..10" },
        listVoices: { type: "boolean" },
      },
    },
  },
  {
    name: "mix_audio",
    description: "ffmpeg 混音：多轨音量/尾部淡出/人声闪避（ducking=true 时 BGM 自动压低给人声让路）。免费本地。",
    inputSchema: {
      type: "object",
      properties: {
        tracks: {
          type: "array",
          items: {
            type: "object",
            properties: {
              path: { type: "string" },
              kind: { type: "string", enum: ["music", "voice"] },
              volume: { type: "number" },
              fadeOutSec: { type: "number" },
              durationSec: { type: "number" },
            },
            required: ["path", "kind"],
          },
        },
        outFile: { type: "string" },
        ducking: { type: "boolean", description: "默认false；true 需要 music+voice 各一条" },
      },
      required: ["tracks"],
    },
  },
  {
    name: "burn_subtitles",
    description: "ffmpeg 把 .srt/.ass 字幕烧进视频，可指定字体/字号/底部边距。免费本地。",
    inputSchema: {
      type: "object",
      properties: {
        video: { type: "string" },
        subtitles: { type: "string" },
        outFile: { type: "string" },
        font: { type: "string", description: "默认 Microsoft YaHei" },
        fontSize: { type: "number", description: "默认14" },
        marginV: { type: "number", description: "默认40" },
      },
      required: ["video", "subtitles", "outFile"],
    },
  },
  {
    name: "assemble_video",
    description: "ffmpeg 合成：视频+音频轨封装（视频流不重编码），-shortest 对齐时长。免费本地。",
    inputSchema: {
      type: "object",
      properties: {
        video: { type: "string" },
        audio: { type: "string" },
        outFile: { type: "string" },
        durationSec: { type: "number" },
      },
      required: ["video", "audio", "outFile"],
    },
  },
];

async function callTool(params) {
  const name = params && params.name;
  const args = (params && params.arguments) || {};
  try {
    switch (name) {
      case "doctor": return jsonResult(await toolDoctor());
      case "plan_workflow": return jsonResult(await toolPlanWorkflow(args));
      case "generate_video": return jsonResult(await toolGenerateVideo(args));
      case "generate_image": return jsonResult(await toolGenerateImage(args));
      case "generate_music": return jsonResult(await toolGenerateMusic(args));
      case "tts_voiceover": return jsonResult(await toolTts(args));
      case "mix_audio": return jsonResult(await toolMixAudio(args));
      case "burn_subtitles": return jsonResult(await toolBurnSubtitles(args));
      case "assemble_video": return jsonResult(await toolAssembleVideo(args));
      default:
        return textResult(`unknown tool: ${name}`, true);
    }
  } catch (e) {
    return textResult("ERROR: " + (e && e.message ? e.message : String(e)), true);
  }
}

/* ---------------- MCP stdio loop ---------------- */

const readline = require("readline");
const rl = readline.createInterface({ input: process.stdin, terminal: false });

async function handleMessage(msg) {
  const id = msg.id;
  const method = msg.method;
  if (!method) return; // response to us? ignore
  if (method === "initialize") {
    const requested = msg.params && msg.params.protocolVersion;
    return send({
      jsonrpc: "2.0",
      id,
      result: {
        protocolVersion: SUPPORTED_PROTOCOLS.has(requested) ? requested : "2025-06-18",
        capabilities: { tools: {} },
        serverInfo: SERVER_INFO,
      },
    });
  }
  if (id === undefined || id === null) return; // notification (initialized, cancelled, ...)
  if (method === "ping") return send({ jsonrpc: "2.0", id, result: {} });
  if (method === "tools/list") return send({ jsonrpc: "2.0", id, result: { tools: TOOLS } });
  if (method === "tools/call") {
    const result = await callTool(msg.params);
    return send({ jsonrpc: "2.0", id, result });
  }
  return send({ jsonrpc: "2.0", id, error: { code: -32601, message: "Method not found: " + method } });
}

rl.on("line", (line) => {
  const t = line.trim();
  if (!t) return;
  let msg;
  try { msg = JSON.parse(t); } catch { return; }
  handleMessage(msg).catch((e) => {
    if (msg && msg.id != null) {
      send({ jsonrpc: "2.0", id: msg.id, error: { code: -32603, message: String(e && e.message || e) } });
    }
  });
});

process.on("SIGINT", () => process.exit(0));
